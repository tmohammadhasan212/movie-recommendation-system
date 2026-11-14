from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.v1.catalog import MovieResponse, movie_response
from backend.app.core.cache import get_or_reserve as cache_get_or_reserve
from backend.app.core.cache import set_value as cache_set
from backend.app.core.db import as_utc, get_db, utcnow
from backend.app.core.metrics import MODEL_LOAD_FAILURES, RECOMMENDATIONS
from backend.app.core.models import (
    GenrePreference,
    ImportedRating,
    LoginSession,
    ModelVersion,
    Movie,
    Rating,
    User,
    WatchlistItem,
)
from backend.app.modules.identity.security import verify_access_token
from backend.app.modules.recommendations.service import (
    Candidate,
    genre_similarity,
    rank,
    smoothed_popularity,
)
from backend.ml.serve import ModelBundle, app_user_scores, load_bundle, normalized

router = APIRouter(tags=["recommendations"])
DB = Annotated[Session, Depends(get_db)]


class RecommendationItem(BaseModel):
    movie: MovieResponse
    source: str
    explanation_code: str


class RecommendationFeed(BaseModel):
    items: list[RecommendationItem]
    model_version: str | None
    fallback_reason: str


def _recommendation_cache_key(
    *,
    user_id: str | None,
    profile_version: int,
    model_version: str | None,
    limit: int,
    include_watchlist: bool,
) -> str:
    version = model_version or "fallback"
    if user_id is None:
        return f"recommendations:anonymous:{version}:{limit}"
    return (
        f"recommendations:user:{user_id}:{profile_version}:"
        f"{version}:{limit}:{int(include_watchlist)}"
    )


def _session(request: Request, db: Session) -> LoginSession | None:
    session_id = verify_access_token(request.cookies.get("access", ""))
    if session_id is None:
        return None
    session = db.get(LoginSession, session_id)
    if session is None or session.revoked_at or as_utc(session.expires_at) <= utcnow():
        return None
    return session


def _candidates(db: Session) -> tuple[list[Candidate], dict[int, Movie], float]:
    movies = list(db.scalars(select(Movie).where(Movie.active.is_(True))))
    aggregates = db.execute(
        select(ImportedRating.movielens_id, func.sum(ImportedRating.rating), func.count())
        .group_by(ImportedRating.movielens_id)
    ).all()
    by_source = {movie_id: (float(total), count) for movie_id, total, count in aggregates}
    total_sum = sum(value[0] for value in by_source.values())
    total_count = sum(value[1] for value in by_source.values())
    global_mean = total_sum / total_count if total_count else 3.0
    candidates = [
        Candidate(
            movie.id,
            frozenset(movie.genres),
            *by_source.get(movie.movielens_id, (0.0, 0)),
        )
        for movie in movies
    ]
    return candidates, {movie.id: movie for movie in movies}, global_mean


@lru_cache(maxsize=2)
def _load_version(version: str, artifact_uri: str) -> ModelBundle:
    bundle = load_bundle(Path(artifact_uri))
    if bundle.version != version:
        raise ValueError("Model registry and artifact version differ")
    return bundle


def _active_bundle(db: Session) -> tuple[ModelBundle | None, str | None]:
    version = db.scalar(select(ModelVersion).where(ModelVersion.active.is_(True)))
    if version is None:
        return None, "no_active_model"
    try:
        return _load_version(version.version_id, version.artifact_uri), None
    except (OSError, ValueError, KeyError):
        MODEL_LOAD_FAILURES.labels("invalid_artifact").inc()
        return None, "model_artifact_invalid"


@router.get("/recommendations", response_model=RecommendationFeed)
def recommendations(
    request: Request,
    db: DB,
    limit: int = Query(20, ge=1, le=100),
    include_watchlist: bool = False,
) -> RecommendationFeed:
    session = _session(request, db)
    active_version = db.scalar(select(ModelVersion.version_id).where(ModelVersion.active.is_(True)))
    if session:
        profile_version = db.scalar(select(User.profile_version).where(User.id == session.user_id)) or 0
        cache_key = _recommendation_cache_key(
            user_id=str(session.user_id),
            profile_version=profile_version,
            model_version=active_version,
            limit=limit,
            include_watchlist=include_watchlist,
        )
    else:
        cache_key = _recommendation_cache_key(
            user_id=None,
            profile_version=0,
            model_version=active_version,
            limit=limit,
            include_watchlist=False,
        )
    cached, reservation_token = cache_get_or_reserve(cache_key)
    if cached:
        return RecommendationFeed.model_validate_json(cached)
    preferred: set[str] = set()
    seen: set[int] = set()
    ratings: list[Rating] = []
    if session:
        preferred.update(db.scalars(select(GenrePreference.genre).where(GenrePreference.user_id == session.user_id)))
        ratings = list(db.scalars(select(Rating).where(Rating.user_id == session.user_id)))
        seen.update(row.movie_id for row in ratings)
        if not include_watchlist:
            seen.update(db.scalars(select(WatchlistItem.movie_id).where(WatchlistItem.user_id == session.user_id)))
        liked_ids = [row.movie_id for row in ratings if row.rating >= 4]
        if liked_ids:
            for genres in db.scalars(select(Movie.genres).where(Movie.id.in_(liked_ids))):
                preferred.update(genres)
    candidates, movie_map, mean = _candidates(db)
    bundle: ModelBundle | None = None
    fallback_reason: str | None = None
    if ratings:
        bundle, fallback_reason = _active_bundle(db)
    if bundle:
        by_internal = {movie.id: movie.movielens_id for movie in movie_map.values()}
        positive = [(by_internal[row.movie_id], row.rating) for row in ratings if row.rating >= 4]
        negative = [(by_internal[row.movie_id], row.rating) for row in ratings if row.rating <= 2.5]
        collaborative = app_user_scores(bundle, positive, negative)
        if collaborative is not None:
            collab = normalized(collaborative)
            scored: list[tuple[float, int]] = []
            for candidate in candidates:
                if candidate.movie_id in seen:
                    continue
                source_id = by_internal[candidate.movie_id]
                index = bundle.index.get(source_id)
                if index is None:
                    continue
                popularity = smoothed_popularity(candidate.rating_sum, candidate.rating_count, mean) / 5
                overlap = genre_similarity(candidate.genres, frozenset(preferred))
                scored.append((0.65 * float(collab[index]) + 0.2 * overlap + 0.15 * popularity, candidate.movie_id))
            scored.sort(key=lambda row: (-row[0], row[1]))
            items = [
                RecommendationItem(
                    movie=movie_response(movie_map[movie_id]),
                    source="hybrid_model",
                    explanation_code="similar_to_high_ratings",
                )
                for _, movie_id in scored[:limit]
            ]
            RECOMMENDATIONS.labels("hybrid_model", "none").inc()
            response = RecommendationFeed(items=items, model_version=bundle.version, fallback_reason="")
            cache_set(cache_key, response.model_dump_json(), reservation_token)
            return response
        fallback_reason = "insufficient_positive_ratings"
    ranked = rank(candidates, global_mean=mean, preferred_genres=frozenset(preferred), seen_ids=frozenset(seen), limit=limit)
    reason = fallback_reason or "insufficient_app_history"
    source = ranked[0].source if ranked else "empty"
    RECOMMENDATIONS.labels(source, reason).inc()
    response = RecommendationFeed(
        items=[
            RecommendationItem(
                movie=movie_response(movie_map[item.movie_id]),
                source=item.source,
                explanation_code=item.explanation_code,
            )
            for item in ranked
        ],
        model_version=None,
        fallback_reason=reason,
    )
    cache_set(cache_key, response.model_dump_json(), reservation_token)
    return response


@router.get("/movies/{movie_id}/similar", response_model=RecommendationFeed)
def similar(movie_id: int, db: DB, limit: int = Query(12, ge=1, le=100)) -> RecommendationFeed:
    source = db.get(Movie, movie_id)
    if source is None or not source.active:
        raise HTTPException(404, "Movie not found")
    candidates, movie_map, mean = _candidates(db)
    bundle, fallback_reason = _active_bundle(db)
    scored = []
    source_genres = frozenset(source.genres)
    source_embedding = bundle.index.get(source.movielens_id) if bundle else None
    for candidate in candidates:
        if candidate.movie_id == movie_id:
            continue
        overlap = genre_similarity(source_genres, candidate.genres)
        embedding_score = 0.0
        if bundle and source_embedding is not None:
            other_source_id = movie_map[candidate.movie_id].movielens_id
            other_embedding = bundle.index.get(other_source_id)
            if other_embedding is not None:
                left, right = bundle.embeddings[source_embedding], bundle.embeddings[other_embedding]
                denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
                embedding_score = max(0.0, float(left @ right) / denominator) if denominator else 0.0
        if overlap or embedding_score:
            popularity = smoothed_popularity(candidate.rating_sum, candidate.rating_count, mean) / 5
            scored.append((0.55 * overlap + 0.35 * embedding_score + 0.1 * popularity, candidate.movie_id))
    scored.sort(key=lambda row: (-row[0], row[1]))
    source_name = "hybrid_similarity" if bundle else "genre_similarity"
    return RecommendationFeed(
        items=[
            RecommendationItem(
                movie=movie_response(movie_map[other_id]),
                source=source_name,
                explanation_code="shared_genres",
            )
            for _, other_id in scored[:limit]
        ],
        model_version=bundle.version if bundle else None,
        fallback_reason=fallback_reason or "",
    )

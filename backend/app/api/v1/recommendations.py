from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.v1.catalog import MovieResponse
from backend.app.core.db import get_db, utcnow
from backend.app.core.models import (
    GenrePreference,
    ImportedRating,
    LoginSession,
    Movie,
    Rating,
    WatchlistItem,
)
from backend.app.modules.identity.security import verify_access_token
from backend.app.modules.recommendations.service import (
    Candidate,
    genre_similarity,
    rank,
    smoothed_popularity,
)

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


def _session(request: Request, db: Session) -> LoginSession | None:
    session_id = verify_access_token(request.cookies.get("access", ""))
    if session_id is None:
        return None
    session = db.get(LoginSession, session_id)
    if session is None or session.revoked_at or session.expires_at <= utcnow():
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
    candidates = [Candidate(movie.id, frozenset(movie.genres), *by_source.get(movie.movielens_id, (0.0, 0))) for movie in movies]
    return candidates, {movie.id: movie for movie in movies}, global_mean


@router.get("/recommendations", response_model=RecommendationFeed)
def recommendations(
    request: Request,
    db: DB,
    limit: int = Query(20, ge=1, le=100),
    include_watchlist: bool = False,
) -> RecommendationFeed:
    session = _session(request, db)
    preferred: set[str] = set()
    seen: set[int] = set()
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
    ranked = rank(candidates, global_mean=mean, preferred_genres=frozenset(preferred), seen_ids=frozenset(seen), limit=limit)
    return RecommendationFeed(items=[RecommendationItem(movie=MovieResponse.model_validate(movie_map[item.movie_id]), source=item.source, explanation_code=item.explanation_code) for item in ranked], model_version=None, fallback_reason="no_active_model")


@router.get("/movies/{movie_id}/similar", response_model=RecommendationFeed)
def similar(movie_id: int, db: DB, limit: int = Query(12, ge=1, le=100)) -> RecommendationFeed:
    source = db.get(Movie, movie_id)
    if source is None or not source.active:
        raise HTTPException(404, "Movie not found")
    candidates, movie_map, mean = _candidates(db)
    scored = []
    source_genres = frozenset(source.genres)
    for candidate in candidates:
        if candidate.movie_id == movie_id:
            continue
        overlap = genre_similarity(source_genres, candidate.genres)
        if overlap:
            popularity = smoothed_popularity(candidate.rating_sum, candidate.rating_count, mean) / 5
            scored.append((0.8 * overlap + 0.2 * popularity, candidate.movie_id))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return RecommendationFeed(items=[RecommendationItem(movie=MovieResponse.model_validate(movie_map[other_id]), source="genre_similarity", explanation_code="shared_genres") for _, other_id in scored[:limit]], model_version=None, fallback_reason="no_active_model")

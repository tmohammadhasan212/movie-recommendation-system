from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.api.v1.catalog import MovieResponse, movie_response
from backend.app.api.v1.identity import CsrfSession, SessionDep
from backend.app.core.db import get_db
from backend.app.core.models import (
    GenrePreference,
    IdempotencyRecord,
    Movie,
    OutboxEvent,
    Rating,
    User,
    WatchlistItem,
)

router = APIRouter(tags=["interactions"])
DB = Annotated[Session, Depends(get_db)]


class RatingInput(BaseModel):
    rating: float = Field(ge=0.5, le=5)

    @field_validator("rating")
    @classmethod
    def half_step(cls, value: float) -> float:
        if value * 2 != int(value * 2):
            raise ValueError("Rating must be in half-star increments")
        return value


class RatingOutput(BaseModel):
    movie_id: int
    rating: float
    profile_version: int


class GenreInput(BaseModel):
    genres: list[str] = Field(max_length=20)


class WatchlistMovieResponse(BaseModel):
    movie: MovieResponse
    added_at: datetime


class WatchlistPage(BaseModel):
    items: list[WatchlistMovieResponse]
    page: int
    limit: int
    total: int


def _active_movie(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None or not movie.active:
        raise HTTPException(404, "Movie not found")
    return movie


def _user_locked(db: Session, user_id: uuid.UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)).with_for_update())
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user


def _outbox(db: Session, user_id: uuid.UUID, movie_id: int, kind: str, version: int) -> None:
    db.add(OutboxEvent(id=uuid.uuid4(), aggregate_ref=f"user:{user_id}", event_type=kind, payload={"schema_version": 1, "movie_id": movie_id, "profile_version": version}))


@router.put("/me/ratings/{movie_id}", response_model=RatingOutput)
def put_rating(
    movie_id: int,
    body: RatingInput,
    session: CsrfSession,
    db: DB,
    idempotency_key: Annotated[str | None, Header(min_length=8, max_length=100)] = None,
) -> RatingOutput:
    _active_movie(db, movie_id)
    user = _user_locked(db, session.user_id)
    action = f"rating:{movie_id}"
    key = idempotency_key or str(uuid.uuid4())
    request_hash = hashlib.sha256(f"{movie_id}:{body.rating}".encode()).hexdigest()
    existing = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.user_id == user.id, IdempotencyRecord.action == action, IdempotencyRecord.key == key))
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key used for another request")
        return RatingOutput.model_validate(existing.response)
    statement = insert(Rating).values(user_id=user.id, movie_id=movie_id, rating=body.rating)
    db.execute(statement.on_conflict_do_update(index_elements=[Rating.user_id, Rating.movie_id], set_={"rating": body.rating}))
    user.profile_version += 1
    _outbox(db, user.id, movie_id, "rating.upserted", user.profile_version)
    result = RatingOutput(movie_id=movie_id, rating=body.rating, profile_version=user.profile_version)
    db.add(IdempotencyRecord(user_id=user.id, action=action, key=key, request_hash=request_hash, response=result.model_dump()))
    db.commit()
    return result


@router.delete("/me/ratings/{movie_id}", status_code=204)
def delete_rating(movie_id: int, session: CsrfSession, db: DB) -> Response:
    user = _user_locked(db, session.user_id)
    rating = db.get(Rating, (user.id, movie_id))
    if rating:
        db.delete(rating)
        user.profile_version += 1
        _outbox(db, user.id, movie_id, "rating.removed", user.profile_version)
        db.commit()
    return Response(status_code=204)


@router.get("/me/ratings")
def my_ratings(session: SessionDep, db: DB) -> list[dict[str, int | float]]:
    rows = db.scalars(select(Rating).where(Rating.user_id == session.user_id).order_by(Rating.updated_at.desc()))
    return [{"movie_id": row.movie_id, "rating": row.rating} for row in rows]


@router.put("/me/watchlist/{movie_id}", status_code=204)
def add_watchlist(movie_id: int, session: CsrfSession, db: DB) -> Response:
    _active_movie(db, movie_id)
    user = _user_locked(db, session.user_id)
    if db.get(WatchlistItem, (user.id, movie_id)) is None:
        db.add(WatchlistItem(user_id=user.id, movie_id=movie_id))
        user.profile_version += 1
        _outbox(db, user.id, movie_id, "watchlist.added", user.profile_version)
        db.commit()
    return Response(status_code=204)


@router.delete("/me/watchlist/{movie_id}", status_code=204)
def remove_watchlist(movie_id: int, session: CsrfSession, db: DB) -> Response:
    user = _user_locked(db, session.user_id)
    item = db.get(WatchlistItem, (user.id, movie_id))
    if item:
        db.delete(item)
        user.profile_version += 1
        _outbox(db, user.id, movie_id, "watchlist.removed", user.profile_version)
        db.commit()
    return Response(status_code=204)


@router.get("/me/watchlist")
def my_watchlist(session: SessionDep, db: DB, limit: int = Query(100, ge=1, le=100)) -> list[int]:
    return list(db.scalars(select(WatchlistItem.movie_id).where(WatchlistItem.user_id == session.user_id).order_by(WatchlistItem.created_at.desc()).limit(limit)))


@router.get("/me/watchlist/movies", response_model=WatchlistPage)
def my_watchlist_movies(
    session: SessionDep,
    db: DB,
    genre: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: Literal["recent", "title", "year_desc", "rating_desc"] = "recent",
) -> WatchlistPage:
    statement = (
        select(WatchlistItem, Movie)
        .join(Movie, Movie.id == WatchlistItem.movie_id)
        .where(WatchlistItem.user_id == session.user_id, Movie.active.is_(True))
    )
    if genre:
        statement = statement.where(Movie.genres.contains([genre]))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    ordering = {
        "recent": (WatchlistItem.created_at.desc(), Movie.id.asc()),
        "title": (Movie.title.asc(), Movie.id.asc()),
        "year_desc": (Movie.release_year.desc().nullslast(), Movie.id.asc()),
        "rating_desc": (
            func.coalesce(Movie.imdb_rating, Movie.tmdb_rating).desc().nullslast(),
            Movie.id.asc(),
        ),
    }
    rows = db.execute(
        statement.order_by(*ordering[sort]).offset((page - 1) * limit).limit(limit)
    ).all()
    return WatchlistPage(
        items=[
            WatchlistMovieResponse(movie=movie_response(movie), added_at=item.created_at)
            for item, movie in rows
        ],
        page=page,
        limit=limit,
        total=total,
    )


@router.put("/me/genres")
def save_genres(body: GenreInput, session: CsrfSession, db: DB) -> dict[str, object]:
    user = _user_locked(db, session.user_id)
    allowed = {genre for genres in db.scalars(select(Movie.genres).where(Movie.active.is_(True))) for genre in genres}
    requested = set(body.genres)
    if len(requested) != len(body.genres) or not requested.issubset(allowed):
        raise HTTPException(422, "Unknown or duplicate genre")
    current = set(db.scalars(select(GenrePreference.genre).where(GenrePreference.user_id == user.id)))
    if requested != current:
        for genre in current - requested:
            db.delete(db.get(GenrePreference, (user.id, genre)))
        for genre in requested - current:
            db.add(GenrePreference(user_id=user.id, genre=genre))
        user.profile_version += 1
        _outbox(db, user.id, 0, "genres.changed", user.profile_version)
        db.commit()
    return {"genres": sorted(requested), "profile_version": user.profile_version}

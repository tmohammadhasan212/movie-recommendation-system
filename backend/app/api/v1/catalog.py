import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.db import get_db
from backend.app.core.models import Movie
from backend.app.modules.catalog.service import list_movies

router = APIRouter(tags=["catalog"])
DB = Annotated[Session, Depends(get_db)]


class ExternalRating(BaseModel):
    source: Literal["IMDb", "TMDB"]
    score: float
    scale: int = 10
    vote_count: int | None
    url: str
    updated_at: datetime | None


class MovieResponse(BaseModel):
    id: int
    title: str
    release_year: int | None
    genres: list[str]
    source: str
    poster_url: str | None
    poster_source: str | None
    summary: str | None
    summary_source: str | None
    ratings: list[ExternalRating]

    model_config = {"from_attributes": True}


POSTER_PATH = re.compile(r"^/[A-Za-z0-9_.-]{1,199}$")


def movie_response(movie: Movie) -> MovieResponse:
    poster_url = None
    if movie.poster_source == "TMDB" and movie.poster_path and POSTER_PATH.fullmatch(movie.poster_path):
        poster_url = f"{get_settings().tmdb_image_base_url.rstrip('/')}{movie.poster_path}"
    ratings: list[ExternalRating] = []
    if movie.imdb_rating is not None and movie.imdb_id and movie.imdb_id.isdigit():
        ratings.append(
            ExternalRating(
                source="IMDb",
                score=movie.imdb_rating,
                vote_count=movie.imdb_vote_count,
                url=f"https://www.imdb.com/title/tt{movie.imdb_id}/",
                updated_at=movie.imdb_rating_updated_at,
            )
        )
    if movie.tmdb_rating is not None and movie.tmdb_id is not None and movie.tmdb_id > 0:
        ratings.append(
            ExternalRating(
                source="TMDB",
                score=movie.tmdb_rating,
                vote_count=movie.tmdb_vote_count,
                url=f"https://www.themoviedb.org/movie/{movie.tmdb_id}",
                updated_at=movie.tmdb_metadata_updated_at,
            )
        )
    return MovieResponse(
        id=movie.id,
        title=movie.title,
        release_year=movie.release_year,
        genres=movie.genres,
        source=movie.source,
        poster_url=poster_url,
        poster_source=movie.poster_source if poster_url else None,
        summary=movie.overview,
        summary_source=movie.overview_source if movie.overview else None,
        ratings=ratings,
    )


class MoviePage(BaseModel):
    items: list[MovieResponse]
    page: int
    limit: int
    total: int
    catalog_seeded: bool


@router.get("/movies", response_model=MoviePage)
def movies(
    db: DB,
    q: str | None = Query(None, min_length=1, max_length=100),
    genre: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: Literal["title", "year_asc", "year_desc"] = "title",
) -> MoviePage:
    rows, total = list_movies(db, query=q, genre=genre, page=page, limit=limit, sort=sort)
    return MoviePage(items=[movie_response(row) for row in rows], page=page, limit=limit, total=total, catalog_seeded=bool(db.scalar(select(Movie.id).limit(1))))


@router.get("/movies/{movie_id}", response_model=MovieResponse)
def movie_detail(movie_id: int, db: DB) -> MovieResponse:
    movie = db.get(Movie, movie_id)
    if movie is None or not movie.active:
        raise HTTPException(404, "Movie not found")
    return movie_response(movie)


@router.get("/genres", response_model=list[str])
def genres(db: DB) -> list[str]:
    genre_set = {genre for genres in db.scalars(select(Movie.genres).where(Movie.active.is_(True))) for genre in genres}
    return sorted(genre_set)

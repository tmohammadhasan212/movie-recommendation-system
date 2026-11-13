"""Strict, streaming MovieLens CSV parsing."""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

YEAR_PATTERN = re.compile(r"^(?P<title>.*?) \((?P<year>\d{4})\)$")
VALID_RATINGS = {step / 2 for step in range(1, 11)}


@dataclass(frozen=True)
class SourceMovie:
    movie_id: int
    title: str
    year: int | None
    genres: tuple[str, ...]


@dataclass(frozen=True)
class SourceRating:
    user_id: int
    movie_id: int
    rating: float
    occurred_at: datetime


@dataclass(frozen=True)
class SourceLink:
    movie_id: int
    imdb_id: str | None
    tmdb_id: int | None
    ambiguous_tmdb: bool = False


def _rows(path: Path, headers: tuple[str, ...]) -> Iterator[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if tuple(reader.fieldnames or ()) != headers:
                raise ValueError(f"{path.name}: expected columns {headers}, found {reader.fieldnames}")
            for line, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"{path.name}:{line}: malformed CSV row")
                yield row
    except UnicodeDecodeError as error:
        raise ValueError(f"{path.name}: invalid UTF-8") from error


def movies(path: Path) -> Iterator[SourceMovie]:
    seen: set[int] = set()
    for line, row in enumerate(_rows(path, ("movieId", "title", "genres")), start=2):
        try:
            movie_id = int(row["movieId"])
        except ValueError as error:
            raise ValueError(f"movies.csv:{line}: invalid movieId") from error
        if movie_id <= 0 or movie_id in seen:
            raise ValueError(f"movies.csv:{line}: duplicate or nonpositive movieId {movie_id}")
        seen.add(movie_id)
        raw_title = row["title"].strip()
        if not raw_title or len(raw_title) > 500:
            raise ValueError(f"movies.csv:{line}: invalid title length")
        matched = YEAR_PATTERN.match(raw_title)
        year = int(matched["year"]) if matched else None
        title = matched["title"] if matched else raw_title
        genres = tuple(sorted({g for g in row["genres"].split("|") if g != "(no genres listed)"}))
        if any(not 0 < len(genre) <= 60 for genre in genres):
            raise ValueError(f"movies.csv:{line}: invalid genre")
        yield SourceMovie(movie_id, title, year, genres)


def ratings(path: Path, known_movie_ids: set[int]) -> Iterator[SourceRating]:
    seen: set[tuple[int, int]] = set()
    headers = ("userId", "movieId", "rating", "timestamp")
    for line, row in enumerate(_rows(path, headers), start=2):
        try:
            user_id = int(row["userId"])
            movie_id = int(row["movieId"])
            rating = float(row["rating"])
            occurred_at = datetime.fromtimestamp(int(row["timestamp"]), UTC)
        except (ValueError, OverflowError) as error:
            raise ValueError(f"ratings.csv:{line}: invalid numeric field") from error
        if user_id <= 0 or movie_id not in known_movie_ids:
            raise ValueError(f"ratings.csv:{line}: unknown movie or invalid user")
        if rating not in VALID_RATINGS:
            raise ValueError(f"ratings.csv:{line}: invalid rating {rating}")
        key = (user_id, movie_id)
        if key in seen:
            raise ValueError(f"ratings.csv:{line}: duplicate user/movie pair")
        seen.add(key)
        yield SourceRating(user_id, movie_id, rating, occurred_at)


def links(path: Path, known_movie_ids: set[int], *, omit_ambiguous_tmdb: bool = False) -> Iterator[SourceLink]:
    rows = list(_rows(path, ("movieId", "imdbId", "tmdbId")))
    tmdb_counts = Counter(row["tmdbId"] for row in rows if row["tmdbId"])
    seen: set[int] = set()
    imdb_seen: set[str] = set()
    tmdb_seen: set[int] = set()
    for line, row in enumerate(rows, start=2):
        try:
            movie_id = int(row["movieId"])
            tmdb_id = int(row["tmdbId"]) if row["tmdbId"] else None
        except ValueError as error:
            raise ValueError(f"links.csv:{line}: invalid ID") from error
        imdb_id = row["imdbId"].strip() or None
        if movie_id not in known_movie_ids or movie_id in seen:
            raise ValueError(f"links.csv:{line}: unknown or duplicate movie ID")
        if (imdb_id and (not imdb_id.isdigit() or imdb_id in imdb_seen)) or (tmdb_id is not None and (tmdb_id <= 0 or (tmdb_id in tmdb_seen and not omit_ambiguous_tmdb))):
            raise ValueError(f"links.csv:{line}: duplicate or invalid external ID")
        ambiguous_tmdb = bool(row["tmdbId"] and tmdb_counts[row["tmdbId"]] > 1)
        if ambiguous_tmdb and omit_ambiguous_tmdb:
            tmdb_id = None
        seen.add(movie_id)
        if imdb_id:
            imdb_seen.add(imdb_id)
        if tmdb_id is not None:
            tmdb_seen.add(tmdb_id)
        yield SourceLink(movie_id, imdb_id, tmdb_id, ambiguous_tmdb)

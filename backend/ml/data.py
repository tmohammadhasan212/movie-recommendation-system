"""Strict, streaming MovieLens CSV parsing."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

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
            occurred_at = datetime.fromtimestamp(int(row["timestamp"]), timezone.utc)
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

"""Refresh catalog ratings from IMDb's official non-commercial dataset."""

from __future__ import annotations

import argparse
import gzip
import tempfile
from pathlib import Path

import httpx
from sqlalchemy import select

from backend.app.core.db import SessionLocal, utcnow
from backend.app.core.models import Movie
from backend.app.modules.catalog.imdb import ratings

IMDB_RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


def _download(destination: Path) -> None:
    downloaded = 0
    with httpx.stream("GET", IMDB_RATINGS_URL, follow_redirects=False, timeout=60) as response:
        response.raise_for_status()
        if response.url.host != "datasets.imdbws.com":
            raise ValueError("IMDb dataset download was redirected to an unexpected host")
        with destination.open("wb") as stream:
            for chunk in response.iter_bytes():
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    raise ValueError("IMDb ratings dataset exceeded the download limit")
                stream.write(chunk)


def enrich(path: Path | None = None) -> dict[str, int]:
    with SessionLocal() as db:
        movies = list(
            db.execute(
                select(Movie.id, Movie.imdb_id).where(Movie.imdb_id.is_not(None))
            ).all()
        )
    movie_by_imdb_id = {imdb_id: movie_id for movie_id, imdb_id in movies}
    if not movie_by_imdb_id:
        return {"catalog_ids": 0, "matched": 0}

    with tempfile.TemporaryDirectory(prefix="recsys-imdb-") as directory:
        dataset = path or Path(directory) / "title.ratings.tsv.gz"
        if path is None:
            _download(dataset)
        try:
            with gzip.open(dataset, "rt", encoding="utf-8", newline="") as stream:
                matched = list(ratings(stream, set(movie_by_imdb_id)))
        except (OSError, UnicodeError) as error:
            raise ValueError("IMDb ratings dataset is not a valid gzip TSV file") from error

    refreshed_at = utcnow()
    updates = [
        {
            "id": movie_by_imdb_id[item.imdb_id],
            "imdb_rating": item.rating,
            "imdb_vote_count": item.vote_count,
            "imdb_rating_updated_at": refreshed_at,
        }
        for item in matched
    ]
    with SessionLocal.begin() as db:
        if updates:
            db.bulk_update_mappings(Movie, updates)
    return {"catalog_ids": len(movie_by_imdb_id), "matched": len(updates)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        type=Path,
        help="Use a local title.ratings.tsv.gz instead of downloading the official dataset",
    )
    args = parser.parse_args()
    try:
        print(enrich(args.file))
    except (ValueError, httpx.HTTPError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()

"""Idempotent, operator-triggered import of verified local MovieLens CSV files."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from backend.app.core.db import SessionLocal
from backend.app.core.models import DataImport, ImportedRating, Movie
from backend.ml.data import links, movies, ratings

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BATCH_SIZE = 1000


def _batches(items, size: int = BATCH_SIZE):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _verified_manifest() -> dict:
    path = DATA_DIR / "manifest.json"
    if not path.exists():
        raise ValueError("No local manifest; run make data-download first")
    manifest = json.loads(path.read_text())
    for name in ("movies.csv", "links.csv", "ratings.csv"):
        file = DATA_DIR / "ml-latest-small" / name
        if not file.exists():
            raise ValueError(f"Missing {name}; rerun make data-download")
        with file.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != manifest.get("files", {}).get(name):
            raise ValueError(f"{name} differs from verified download manifest")
    return manifest


def import_data() -> dict[str, int]:
    manifest = _verified_manifest()
    root = DATA_DIR / "ml-latest-small"
    catalog = list(movies(root / "movies.csv"))
    if not catalog:
        raise ValueError("Movie catalog is unexpectedly empty")
    known = {movie.movie_id for movie in catalog}
    external = {link.movie_id: link for link in links(root / "links.csv", known)}
    counts = {"movies": 0, "links": len(external), "ratings": 0}
    with SessionLocal.begin() as db:
        for batch in _batches(catalog):
            values = [
                {
                    "movielens_id": movie.movie_id,
                    "title": movie.title,
                    "release_year": movie.year,
                    "genres": list(movie.genres),
                    "imdb_id": external[movie.movie_id].imdb_id if movie.movie_id in external else None,
                    "tmdb_id": external[movie.movie_id].tmdb_id if movie.movie_id in external else None,
                    "active": True,
                    "source": "MovieLens",
                }
                for movie in batch
            ]
            statement = insert(Movie).values(values)
            db.execute(statement.on_conflict_do_update(index_elements=[Movie.movielens_id], set_={key: getattr(statement.excluded, key) for key in ("title", "release_year", "genres", "imdb_id", "tmdb_id", "active")}))
            counts["movies"] += len(batch)
        for batch in _batches(ratings(root / "ratings.csv", known)):
            values = [
                {"source_user_id": row.user_id, "movielens_id": row.movie_id, "rating": row.rating, "occurred_at": row.occurred_at}
                for row in batch
            ]
            statement = insert(ImportedRating).values(values)
            db.execute(statement.on_conflict_do_update(index_elements=[ImportedRating.source_user_id, ImportedRating.movielens_id], set_={"rating": statement.excluded.rating, "occurred_at": statement.excluded.occurred_at}))
            counts["ratings"] += len(batch)
        if not counts["ratings"]:
            raise ValueError("Ratings file is unexpectedly empty")
        statement = insert(DataImport).values(source_name="MovieLens", source_version="ml-latest-small", checksum=manifest["sha256"], counts=counts, imported_at=datetime.now(UTC), status="complete")
        db.execute(statement.on_conflict_do_update(index_elements=[DataImport.checksum], set_={"counts": counts, "imported_at": statement.excluded.imported_at, "status": "complete"}))
    manifest["imported_at"] = datetime.now(UTC).isoformat()
    manifest["counts"] = counts
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return counts


if __name__ == "__main__":
    try:
        print(import_data())
    except ValueError as error:
        raise SystemExit(str(error)) from error

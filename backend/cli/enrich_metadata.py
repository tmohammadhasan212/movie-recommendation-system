"""Explicit, bounded TMDB poster enrichment command."""

from __future__ import annotations

import argparse
import json
import time
from datetime import timedelta

from sqlalchemy import or_, select, update

from backend.app.core.config import get_settings
from backend.app.core.db import SessionLocal, utcnow
from backend.app.core.models import Movie
from backend.app.modules.catalog.tmdb import TmdbClient, TmdbMetadataError


def enrich(*, limit: int, stale_days: int, delay: float) -> dict[str, int]:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not 0 <= stale_days <= 3650:
        raise ValueError("stale-days must be between 0 and 3650")
    if not 0 <= delay <= 5:
        raise ValueError("delay must be between 0 and 5 seconds")

    settings = get_settings()
    cutoff = utcnow() - timedelta(days=stale_days)
    with SessionLocal() as db:
        candidates = list(
            db.execute(
                select(Movie.id, Movie.tmdb_id)
                .where(
                    Movie.tmdb_id.is_not(None),
                    or_(Movie.poster_updated_at.is_(None), Movie.poster_updated_at < cutoff),
                )
                .order_by(Movie.id)
                .limit(limit)
            ).all()
        )

    results: list[tuple[int, str | None]] = []
    failed = 0
    with TmdbClient(settings.tmdb_api_token, settings.tmdb_api_base_url) as client:
        client.validate_image_base(settings.tmdb_image_base_url)
        for movie_id, tmdb_id in candidates:
            try:
                results.append((movie_id, client.poster_path(tmdb_id)))
            except TmdbMetadataError as error:
                failed += 1
                print(f"movie {movie_id}: {error}")
            if delay:
                time.sleep(delay)

    refreshed_at = utcnow()
    with SessionLocal.begin() as db:
        for movie_id, poster_path in results:
            db.execute(
                update(Movie)
                .where(Movie.id == movie_id)
                .values(
                    poster_path=poster_path,
                    poster_source="TMDB",
                    poster_updated_at=refreshed_at,
                )
            )
    return {
        "selected": len(candidates),
        "updated": len(results),
        "with_posters": sum(path is not None for _, path in results),
        "without_posters": sum(path is None for _, path in results),
        "failed": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()
    try:
        print(json.dumps(enrich(limit=args.limit, stale_days=args.stale_days, delay=args.delay)))
    except (ValueError, TmdbMetadataError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()

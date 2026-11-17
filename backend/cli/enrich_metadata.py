"""Explicit, bounded TMDB movie metadata enrichment command."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update

from backend.app.core.config import get_settings
from backend.app.core.db import SessionLocal, utcnow
from backend.app.core.models import Movie
from backend.app.modules.catalog.tmdb import TmdbClient, TmdbMetadataError, TmdbMovieMetadata


def enrich(
    *,
    limit: int,
    stale_days: int,
    delay: float,
    workers: int = 1,
    cutoff: datetime | None = None,
) -> dict[str, int]:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not 0 <= stale_days <= 3650:
        raise ValueError("stale-days must be between 0 and 3650")
    if not 0 <= delay <= 5:
        raise ValueError("delay must be between 0 and 5 seconds")
    if not 1 <= workers <= 16:
        raise ValueError("workers must be between 1 and 16")

    settings = get_settings()
    cutoff = cutoff or utcnow() - timedelta(days=stale_days)
    with SessionLocal() as db:
        candidates = list(
            db.execute(
                select(Movie.id, Movie.tmdb_id)
                .where(
                    Movie.tmdb_id.is_not(None),
                    or_(
                        Movie.tmdb_metadata_updated_at.is_(None),
                        Movie.tmdb_metadata_updated_at < cutoff,
                    ),
                )
                .order_by(Movie.title, Movie.id)
                .limit(limit)
            ).all()
        )

    results: list[tuple[int, TmdbMovieMetadata | None]] = []
    failed = 0
    with TmdbClient(
        settings.tmdb_api_token,
        settings.tmdb_api_base_url,
        api_key=settings.tmdb_api_key,
    ) as client:
        client.validate_image_base(settings.tmdb_image_base_url)

        def fetch(candidate: tuple[int, int]) -> tuple[int, TmdbMovieMetadata | None, str | None]:
            movie_id, tmdb_id = candidate
            try:
                return movie_id, client.movie_metadata(tmdb_id), None
            except TmdbMetadataError as error:
                return movie_id, None, str(error)
            finally:
                if delay:
                    time.sleep(delay)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for movie_id, metadata, error in executor.map(fetch, candidates):
                if error:
                    failed += 1
                    print(f"movie {movie_id}: {error}", flush=True)
                else:
                    results.append((movie_id, metadata))

    refreshed_at = utcnow()
    with SessionLocal.begin() as db:
        for movie_id, metadata in results:
            db.execute(
                update(Movie)
                .where(Movie.id == movie_id)
                .values(
                    poster_path=metadata.poster_path if metadata else None,
                    poster_source="TMDB",
                    poster_updated_at=refreshed_at,
                    overview=metadata.overview if metadata else None,
                    overview_source="TMDB" if metadata and metadata.overview else None,
                    tmdb_rating=metadata.vote_average if metadata else None,
                    tmdb_vote_count=metadata.vote_count if metadata else None,
                    tmdb_collection_id=metadata.collection_id if metadata else None,
                    tmdb_collection_name=metadata.collection_name if metadata else None,
                    tmdb_metadata_updated_at=refreshed_at,
                )
            )
    return {
        "selected": len(candidates),
        "updated": len(results),
        "with_posters": sum(item is not None and item.poster_path is not None for _, item in results),
        "without_posters": sum(item is None or item.poster_path is None for _, item in results),
        "with_overviews": sum(item is not None and item.overview is not None for _, item in results),
        "with_tmdb_ratings": sum(
            item is not None and item.vote_average is not None for _, item in results
        ),
        "failed": failed,
    }


def enrich_all(*, limit: int, stale_days: int, delay: float, workers: int) -> dict[str, int]:
    totals = {
        "batches": 0,
        "selected": 0,
        "updated": 0,
        "with_posters": 0,
        "without_posters": 0,
        "with_overviews": 0,
        "with_tmdb_ratings": 0,
        "failed": 0,
    }
    cutoff = utcnow() - timedelta(days=stale_days)
    while True:
        batch = enrich(
            limit=limit,
            stale_days=stale_days,
            delay=delay,
            workers=workers,
            cutoff=cutoff,
        )
        if batch["selected"] == 0:
            break
        totals["batches"] += 1
        for key in totals.keys() - {"batches"}:
            totals[key] += batch[key]
        print(json.dumps({"batch": totals["batches"], **batch}), flush=True)
        if batch["updated"] == 0:
            break
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Continue checkpointed batches until every eligible movie has been attempted",
    )
    args = parser.parse_args()
    try:
        if args.all:
            result = enrich_all(
                limit=args.limit,
                stale_days=args.stale_days,
                delay=args.delay,
                workers=args.workers,
            )
        else:
            result = enrich(
                limit=args.limit,
                stale_days=args.stale_days,
                delay=args.delay,
                workers=args.workers,
            )
        print(json.dumps(result))
    except (ValueError, TmdbMetadataError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()

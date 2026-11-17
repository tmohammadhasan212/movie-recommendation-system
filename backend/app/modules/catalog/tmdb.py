"""Small, explicit TMDB client for optional catalog metadata enrichment."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self

import httpx

POSTER_PATH = re.compile(r"^/[A-Za-z0-9_.-]{1,199}$")


class TmdbMetadataError(RuntimeError):
    pass


@dataclass(frozen=True)
class TmdbMovieMetadata:
    poster_path: str | None
    overview: str | None
    vote_average: float | None
    vote_count: int | None
    collection_id: int | None
    collection_name: str | None


def _json_object(response: httpx.Response, description: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as error:
        raise TmdbMetadataError(f"TMDB returned invalid JSON for {description}") from error
    if not isinstance(payload, dict):
        raise TmdbMetadataError(f"TMDB returned an invalid {description} response")
    return payload


def parse_poster_path(payload: dict[str, Any], expected_id: int) -> str | None:
    if payload.get("id") != expected_id:
        raise TmdbMetadataError("TMDB response ID did not match the requested movie")
    path = payload.get("poster_path")
    if path is None:
        return None
    if not isinstance(path, str) or not POSTER_PATH.fullmatch(path):
        raise TmdbMetadataError("TMDB returned an invalid poster path")
    return path


def parse_movie_metadata(payload: dict[str, Any], expected_id: int) -> TmdbMovieMetadata:
    poster_path = parse_poster_path(payload, expected_id)
    overview = payload.get("overview")
    if overview is not None:
        if not isinstance(overview, str) or len(overview) > 10_000:
            raise TmdbMetadataError("TMDB returned an invalid movie overview")
        overview = overview.strip() or None

    vote_average = payload.get("vote_average")
    if vote_average is not None:
        if isinstance(vote_average, bool) or not isinstance(vote_average, (int, float)):
            raise TmdbMetadataError("TMDB returned an invalid vote average")
        vote_average = float(vote_average)
        if not 0 <= vote_average <= 10:
            raise TmdbMetadataError("TMDB returned an invalid vote average")

    vote_count = payload.get("vote_count")
    if vote_count is not None and (
        isinstance(vote_count, bool) or not isinstance(vote_count, int) or vote_count < 0
    ):
        raise TmdbMetadataError("TMDB returned an invalid vote count")

    collection = payload.get("belongs_to_collection")
    collection_id = None
    collection_name = None
    if collection is not None:
        if not isinstance(collection, dict):
            raise TmdbMetadataError("TMDB returned invalid collection metadata")
        collection_id = collection.get("id")
        collection_name = collection.get("name")
        if (
            isinstance(collection_id, bool)
            or not isinstance(collection_id, int)
            or collection_id <= 0
            or not isinstance(collection_name, str)
            or not collection_name.strip()
            or len(collection_name) > 500
        ):
            raise TmdbMetadataError("TMDB returned invalid collection metadata")
        collection_name = collection_name.strip()

    return TmdbMovieMetadata(
        poster_path,
        overview,
        vote_average,
        vote_count,
        collection_id,
        collection_name,
    )


class TmdbClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        *,
        api_key: str = "",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        token = token.strip()
        api_key = api_key.strip()
        if not token and not api_key:
            raise ValueError(
                "TMDB_API_TOKEN or TMDB_API_KEY is required for metadata enrichment"
            )
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/",
            headers=headers,
            params={"api_key": api_key} if api_key else None,
            timeout=httpx.Timeout(15, connect=5),
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    def _get(self, path: str) -> httpx.Response:
        last_error = "TMDB request failed"
        for attempt in range(3):
            try:
                response = self._client.get(path)
            except httpx.RequestError as error:
                last_error = f"TMDB request failed: {error.__class__.__name__}"
            else:
                if response.status_code == 404:
                    return response
                if response.status_code < 400:
                    return response
                last_error = f"TMDB returned HTTP {response.status_code}"
                if response.status_code != 429 and response.status_code < 500:
                    raise TmdbMetadataError(last_error)
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = min(5.0, max(0.0, float(retry_after)))
                except ValueError:
                    delay = 0.0
                if delay:
                    self._sleep(delay)
            if attempt < 2:
                self._sleep(2**attempt)
        raise TmdbMetadataError(last_error)

    def validate_image_base(self, configured_base: str) -> None:
        response = self._get("configuration")
        payload = _json_object(response, "configuration")
        images = payload.get("images", {})
        secure_base = images.get("secure_base_url")
        sizes = images.get("poster_sizes", [])
        if not isinstance(secure_base, str) or "w500" not in sizes:
            raise TmdbMetadataError("TMDB image configuration is missing the w500 poster size")
        expected = f"{secure_base.rstrip('/')}/w500"
        if configured_base.rstrip("/") != expected:
            raise TmdbMetadataError(
                f"TMDB_IMAGE_BASE_URL must match the current TMDB configuration: {expected}"
            )

    def movie_metadata(self, tmdb_id: int) -> TmdbMovieMetadata | None:
        response = self._get(f"movie/{tmdb_id}?language=en-US")
        if response.status_code == 404:
            return None
        payload = _json_object(response, "movie")
        return parse_movie_metadata(payload, tmdb_id)

    def poster_path(self, tmdb_id: int) -> str | None:
        metadata = self.movie_metadata(tmdb_id)
        return metadata.poster_path if metadata else None

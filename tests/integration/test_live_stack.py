"""Run against the local Compose stack with ``LIVE_STACK=1``."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import httpx
import pytest

pytestmark = pytest.mark.skipif(os.getenv("LIVE_STACK") != "1", reason="requires local Compose stack")


def _csrf(client: httpx.Client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["csrf"]}


def test_registered_user_journey() -> None:
    email = f"live-{uuid.uuid4()}@example.test"
    password = "correct horse battery staple"
    with httpx.Client(base_url="http://localhost:8000/api/v1", timeout=10) as client:
        registration = client.post("/auth/register", json={"email": email, "password": password})
        assert registration.status_code == 202
        signed_in = client.post("/auth/login", json={"email": email, "password": password})
        assert signed_in.status_code == 200
        assert client.cookies.get("access")
        assert client.cookies.get("refresh")
        assert client.cookies.get("csrf")

        previous_refresh = client.cookies["refresh"]
        previous_csrf = client.cookies["csrf"]
        client.cookies.delete("access")
        refreshed = client.post("/auth/refresh", headers=_csrf(client))
        assert refreshed.status_code == 200
        assert client.cookies.get("access")
        assert client.cookies["refresh"] != previous_refresh
        assert client.cookies["csrf"] != previous_csrf

        genres = client.get("/genres")
        assert genres.status_code == 200
        assert "Action" in genres.json()
        selected = client.put("/me/genres", json={"genres": ["Action"]}, headers=_csrf(client))
        assert selected.status_code == 200

        catalog = client.get("/movies", params={"genre": "Action", "limit": 2})
        assert catalog.status_code == 200
        movies = catalog.json()["items"]
        assert len(movies) == 2
        rated_id, saved_id = movies[0]["id"], movies[1]["id"]

        headers = {**_csrf(client), "Idempotency-Key": f"live-rating-{uuid.uuid4()}"}
        first_rating = client.put(f"/me/ratings/{rated_id}", json={"rating": 4.5}, headers=headers)
        assert first_rating.status_code == 200
        repeated = client.put(f"/me/ratings/{rated_id}", json={"rating": 4.5}, headers=headers)
        assert repeated.json() == first_rating.json()
        saved = client.put(f"/me/watchlist/{saved_id}", headers=_csrf(client))
        assert saved.status_code == 204

        event_id = str(uuid.uuid4())
        event = client.post(
            "/events",
            headers=_csrf(client),
            json={
                "id": event_id,
                "movie_id": rated_id,
                "event_type": "detail_view",
                "occurred_at": datetime.now(UTC).isoformat(),
                "consent": True,
            },
        )
        assert event.status_code == 202

        feed = client.get("/recommendations", params={"limit": 10})
        assert feed.status_code == 200
        payload = feed.json()
        assert payload["items"]
        returned_ids = {item["movie"]["id"] for item in payload["items"]}
        assert rated_id not in returned_ids
        assert saved_id not in returned_ids
        assert payload["model_version"].startswith("mf-")
        assert payload["fallback_reason"] == ""
        assert all(item["source"] == "hybrid_model" for item in payload["items"])

        exported = client.get("/me/export")
        assert exported.status_code == 200
        assert exported.json()["profile"]["email"] == email
        deleted = client.delete("/me", headers=_csrf(client))
        assert deleted.status_code == 204
        assert client.get("/me").status_code == 401

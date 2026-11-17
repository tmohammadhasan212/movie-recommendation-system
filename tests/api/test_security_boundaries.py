from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.db import get_db, utcnow
from backend.app.core.models import (
    GenrePreference,
    InteractionEvent,
    LoginSession,
    Rating,
    User,
    WatchlistItem,
)
from backend.app.main import app
from backend.app.modules.identity.security import hash_secret, sign_access_token


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    session_id: uuid.UUID
    csrf: str


@pytest.fixture
def security_api() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (
        User,
        LoginSession,
        Rating,
        WatchlistItem,
        GenrePreference,
        InteractionEvent,
    ):
        model.__table__.create(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_principal(
    sessions: sessionmaker[Session],
    label: str,
    *,
    expires_in: timedelta = timedelta(days=1),
    revoked: bool = False,
) -> Principal:
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    csrf = f"csrf-{label}"
    now = utcnow()
    with sessions.begin() as db:
        db.add(
            User(
                id=user_id,
                email=f"{label}@example.test",
                password_hash="not-used-in-boundary-tests",
                profile_version=0,
            )
        )
        db.add(
            LoginSession(
                id=session_id,
                user_id=user_id,
                refresh_hash=hash_secret(f"refresh-{label}"),
                csrf_hash=hash_secret(csrf),
                expires_at=now + expires_in,
                authenticated_at=now,
                revoked_at=now if revoked else None,
            )
        )
    return Principal(user_id=user_id, session_id=session_id, csrf=csrf)


def authenticate(client: TestClient, principal: Principal) -> dict[str, str]:
    client.cookies.clear()
    client.cookies.set("access", sign_access_token(principal.session_id))
    client.cookies.set("csrf", principal.csrf)
    return {"X-CSRF-Token": principal.csrf}


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("GET", "/api/v1/me", None),
        ("GET", "/api/v1/me/ratings", None),
        ("GET", "/api/v1/me/watchlist", None),
        ("GET", "/api/v1/me/watchlist/movies", None),
        ("PUT", "/api/v1/me/ratings/101", {"rating": 4.5}),
        ("DELETE", "/api/v1/me/watchlist/101", None),
    ],
)
def test_user_routes_reject_unauthenticated_requests(
    security_api: tuple[TestClient, sessionmaker[Session]],
    method: str,
    path: str,
    json: dict[str, float] | None,
) -> None:
    client, _ = security_api

    response = client.request(method, path, json=json)

    assert response.status_code == 401
    assert response.json()["code"] == "http_401"


@pytest.mark.parametrize(
    ("expires_in", "revoked"),
    [(timedelta(seconds=-1), False), (timedelta(days=1), True)],
)
def test_expired_or_revoked_database_sessions_are_rejected(
    security_api: tuple[TestClient, sessionmaker[Session]],
    expires_in: timedelta,
    revoked: bool,
) -> None:
    client, sessions = security_api
    principal = create_principal(
        sessions,
        f"invalid-{revoked}-{expires_in.total_seconds()}",
        expires_in=expires_in,
        revoked=revoked,
    )
    authenticate(client, principal)

    response = client.get("/api/v1/me")

    assert response.status_code == 401


def test_forged_access_cookie_is_rejected(
    security_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = security_api
    principal = create_principal(sessions, "forged")
    client.cookies.set("access", f"{sign_access_token(principal.session_id)}tampered")

    response = client.get("/api/v1/me")

    assert response.status_code == 401


def test_mutation_requires_the_current_sessions_csrf_token(
    security_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = security_api
    principal = create_principal(sessions, "csrf-owner")
    authenticate(client, principal)

    missing = client.delete("/api/v1/me/ratings/101")
    wrong = client.delete(
        "/api/v1/me/ratings/101",
        headers={"X-CSRF-Token": "csrf-from-another-session"},
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert missing.json()["message"] == "CSRF token required"


@pytest.mark.parametrize(
    "provenance",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Referer": "https://evil.example/account"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_origin_mutation_is_rejected_before_business_logic(
    security_api: tuple[TestClient, sessionmaker[Session]],
    provenance: dict[str, str],
) -> None:
    client, sessions = security_api
    principal = create_principal(sessions, "origin-owner")
    headers = {**authenticate(client, principal), **provenance}

    response = client.delete("/api/v1/me/ratings/101", headers=headers)

    assert response.status_code == 403
    assert response.json()["message"] == "Cross-origin request rejected"


def test_same_origin_mutation_is_allowed(
    security_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = security_api
    principal = create_principal(sessions, "same-origin-owner")
    headers = {**authenticate(client, principal), "Origin": "http://testserver"}

    response = client.delete("/api/v1/me/ratings/101", headers=headers)

    assert response.status_code == 204


def test_user_cannot_read_or_delete_another_users_interactions(
    security_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = security_api
    owner = create_principal(sessions, "owner")
    other = create_principal(sessions, "other")
    with sessions.begin() as db:
        db.add(Rating(user_id=owner.user_id, movie_id=101, rating=5.0))
        db.add(WatchlistItem(user_id=owner.user_id, movie_id=202))

    headers = authenticate(client, other)
    ratings = client.get("/api/v1/me/ratings")
    watchlist = client.get("/api/v1/me/watchlist")
    exported = client.get("/api/v1/me/export")
    delete_rating = client.delete("/api/v1/me/ratings/101", headers=headers)
    delete_watchlist = client.delete("/api/v1/me/watchlist/202", headers=headers)

    assert ratings.json() == []
    assert watchlist.json() == []
    assert exported.json()["ratings"] == []
    assert exported.json()["watchlist"] == []
    assert delete_rating.status_code == 204
    assert delete_watchlist.status_code == 204
    with sessions() as db:
        assert db.get(Rating, (owner.user_id, 101)) is not None
        assert db.get(WatchlistItem, (owner.user_id, 202)) is not None
        assert db.scalar(select(User.profile_version).where(User.id == other.user_id)) == 0

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.api.v1 import identity
from backend.app.main import app


def test_liveness_is_independent_of_database() -> None:
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["X-Request-ID"]


def test_catalog_query_validation_has_consistent_problem_shape() -> None:
    response = TestClient(app).get("/api/v1/movies?limit=101")
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["request_id"]


def test_rate_limit_response_preserves_retry_after(monkeypatch) -> None:
    def limited(*args, **kwargs) -> None:
        raise HTTPException(
            429,
            "Too many attempts; try again later",
            headers={"Retry-After": "42"},
        )

    monkeypatch.setattr(identity, "enforce_rate_limit", limited)
    response = TestClient(app).post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert response.json()["code"] == "http_429"

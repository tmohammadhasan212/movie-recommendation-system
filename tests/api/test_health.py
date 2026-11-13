from fastapi.testclient import TestClient

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

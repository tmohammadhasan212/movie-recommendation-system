from __future__ import annotations

import redis
from fastapi import HTTPException
from prometheus_client import generate_latest

from backend.app.core.metrics import RATE_LIMIT_DECISIONS, REDIS_ERRORS
from backend.app.core.rate_limit import enforce_rate_limit


class FakeRedis:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.call: tuple[str, int, tuple[object, ...]] | None = None

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.call = (script, numkeys, keys_and_args)
        if self.error:
            raise self.error
        return self.result


def metric_value(scope: str, outcome: str) -> float:
    return RATE_LIMIT_DECISIONS.labels(scope, outcome)._value.get()


def test_allowed_decision_uses_atomic_window_and_bounded_labels() -> None:
    connection = FakeRedis([1, 60])
    before = metric_value("login", "allowed")

    enforce_rate_limit("private:key", "login", 10, connection=connection)

    assert connection.call is not None
    script, numkeys, arguments = connection.call
    assert "INCR" in script and "EXPIRE" in script
    assert numkeys == 1
    assert arguments == ("private:key", 60)
    assert metric_value("login", "allowed") == before + 1


def test_limited_decision_returns_window_ttl() -> None:
    before = metric_value("register", "limited")

    try:
        enforce_rate_limit("private:key", "register", 5, connection=FakeRedis([6, 37]))
    except HTTPException as error:
        assert error.status_code == 429
        assert error.headers == {"Retry-After": "37"}
    else:
        raise AssertionError("expected the request to be rate limited")

    assert metric_value("register", "limited") == before + 1


def test_redis_outage_fails_closed_and_records_both_metrics() -> None:
    decisions_before = metric_value("password", "unavailable")
    redis_errors_before = REDIS_ERRORS.labels("rate_limit")._value.get()

    try:
        enforce_rate_limit(
            "private:key",
            "password",
            5,
            connection=FakeRedis(error=redis.ConnectionError("private details")),
        )
    except HTTPException as error:
        assert error.status_code == 503
        assert error.detail == "Abuse protection unavailable"
    else:
        raise AssertionError("expected the limiter to fail closed")

    assert metric_value("password", "unavailable") == decisions_before + 1
    assert REDIS_ERRORS.labels("rate_limit")._value.get() == redis_errors_before + 1


def test_malformed_redis_result_fails_closed() -> None:
    try:
        enforce_rate_limit("private:key", "profile", 5, connection=FakeRedis([1]))
    except HTTPException as error:
        assert error.status_code == 503
    else:
        raise AssertionError("expected malformed state to fail closed")


def test_invalid_policy_is_rejected_before_redis() -> None:
    connection = FakeRedis([1, 60])

    try:
        enforce_rate_limit("private:key", "login", 0, connection=connection)
    except ValueError as error:
        assert str(error) == "rate-limit maximum and window must be positive"
    else:
        raise AssertionError("expected an invalid policy error")

    assert connection.call is None


def test_all_bounded_series_exist_before_their_first_event() -> None:
    metrics = generate_latest().decode()

    for scope in ("register", "login", "password", "profile", "events"):
        for outcome in ("allowed", "limited", "unavailable"):
            assert f'outcome="{outcome}",scope="{scope}"' in metrics

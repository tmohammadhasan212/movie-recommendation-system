"""Fail-closed Redis rate limits with atomic windows and bounded metric labels."""

from __future__ import annotations

from typing import Literal, Protocol, cast, get_args

import redis
from fastapi import HTTPException

from backend.app.core.config import get_settings
from backend.app.core.metrics import RATE_LIMIT_DECISIONS, REDIS_ERRORS

RateLimitScope = Literal["register", "login", "password", "profile", "events"]
RateLimitOutcome = Literal["allowed", "limited", "unavailable"]

# Pre-create the bounded series so Prometheus can calculate an increase on the
# first outage instead of discovering that counter only after the failure.
for _scope in get_args(RateLimitScope):
    for _outcome in get_args(RateLimitOutcome):
        RATE_LIMIT_DECISIONS.labels(_scope, _outcome)

_INCREMENT_WINDOW = """
local current = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if current == 1 or ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {current, ttl}
"""


class RedisRateLimitClient(Protocol):
    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object: ...


def _client() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


def enforce_rate_limit(
    key: str,
    scope: RateLimitScope,
    maximum: int,
    window: int = 60,
    *,
    connection: RedisRateLimitClient | None = None,
) -> None:
    if maximum < 1 or window < 1:
        raise ValueError("rate-limit maximum and window must be positive")
    try:
        result = cast(
            list[int],
            (connection or _client()).eval(_INCREMENT_WINDOW, 1, key, window),
        )
        count, ttl = int(result[0]), max(1, int(result[1]))
    except (redis.RedisError, TypeError, ValueError, IndexError):
        RATE_LIMIT_DECISIONS.labels(scope, "unavailable").inc()
        REDIS_ERRORS.labels("rate_limit").inc()
        raise HTTPException(503, "Abuse protection unavailable") from None

    if count > maximum:
        RATE_LIMIT_DECISIONS.labels(scope, "limited").inc()
        raise HTTPException(
            429,
            "Too many attempts; try again later",
            headers={"Retry-After": str(ttl)},
        )
    RATE_LIMIT_DECISIONS.labels(scope, "allowed").inc()

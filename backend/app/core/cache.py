from __future__ import annotations

from functools import lru_cache
from time import time

import redis

from backend.app.core.config import get_settings
from backend.app.core.metrics import CACHE_REQUESTS, REDIS_ERRORS

WORKER_HEARTBEAT_KEY = "operations:worker-heartbeat"


@lru_cache(maxsize=1)
def client() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=0.25,
        socket_timeout=0.25,
        decode_responses=True,
    )


def get(key: str) -> str | None:
    try:
        value = client().get(key)
        CACHE_REQUESTS.labels("recommendations", "hit" if value else "miss").inc()
        return value
    except redis.RedisError:
        CACHE_REQUESTS.labels("recommendations", "error").inc()
        REDIS_ERRORS.labels("get").inc()
        return None


def set_value(key: str, value: str, ttl_seconds: int = 300) -> None:
    try:
        client().set(key, value, ex=ttl_seconds)
    except redis.RedisError:
        CACHE_REQUESTS.labels("recommendations", "error").inc()
        REDIS_ERRORS.labels("set").inc()


def record_worker_heartbeat() -> None:
    try:
        client().set(WORKER_HEARTBEAT_KEY, str(time()), ex=120)
    except redis.RedisError:
        REDIS_ERRORS.labels("worker_heartbeat_set").inc()


def worker_heartbeat() -> float:
    try:
        return float(client().get(WORKER_HEARTBEAT_KEY) or 0)
    except (redis.RedisError, ValueError):
        REDIS_ERRORS.labels("worker_heartbeat_get").inc()
        return 0

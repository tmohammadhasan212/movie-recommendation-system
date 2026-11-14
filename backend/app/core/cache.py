from __future__ import annotations

from functools import lru_cache
from time import sleep, time
from uuid import uuid4

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


def get_or_reserve(key: str, wait_seconds: float = 2.0) -> tuple[str | None, str | None]:
    lock_key = f"{key}:lock"
    token = uuid4().hex
    try:
        connection = client()
        value = connection.get(key)
        if value:
            CACHE_REQUESTS.labels("recommendations", "hit").inc()
            return value, None
        CACHE_REQUESTS.labels("recommendations", "miss").inc()
        if connection.set(lock_key, token, nx=True, ex=10):
            return None, token
        deadline = time() + wait_seconds
        while time() < deadline:
            sleep(0.02)
            value = connection.get(key)
            if value:
                CACHE_REQUESTS.labels("recommendations", "coalesced_hit").inc()
                return value, None
        CACHE_REQUESTS.labels("recommendations", "coalescing_timeout").inc()
        return None, None
    except redis.RedisError:
        CACHE_REQUESTS.labels("recommendations", "error").inc()
        REDIS_ERRORS.labels("get").inc()
        return None, None


def set_value(
    key: str, value: str, reservation_token: str | None, ttl_seconds: int = 300
) -> None:
    try:
        connection = client()
        connection.set(key, value, ex=ttl_seconds)
        if reservation_token:
            connection.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then "
                "return redis.call('del', KEYS[1]) else return 0 end",
                1,
                f"{key}:lock",
                reservation_token,
            )
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

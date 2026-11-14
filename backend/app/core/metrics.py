from prometheus_client import Counter, Gauge, Histogram, Info

HTTP_REQUESTS = Counter(
    "recsys_http_requests_total", "HTTP requests", ("method", "route", "status")
)
HTTP_DURATION = Histogram(
    "recsys_http_request_duration_seconds",
    "HTTP request latency",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
RECOMMENDATIONS = Counter(
    "recsys_recommendations_total", "Recommendation responses", ("source", "fallback_reason")
)
MODEL_LOAD_FAILURES = Counter(
    "recsys_model_load_failures_total", "Model artifact load failures", ("reason",)
)
OUTBOX_DISPATCHED = Counter(
    "recsys_outbox_dispatched_total", "Outbox events published to the broker"
)
OUTBOX_DEAD_LETTERS = Counter(
    "recsys_outbox_dead_letters_total", "Outbox events moved to dead letter state"
)
WORKER_HEARTBEAT = Gauge(
    "recsys_worker_heartbeat_unixtime", "Last successful worker task time"
)
CACHE_REQUESTS = Counter(
    "recsys_cache_requests_total", "Cache lookups", ("cache", "result")
)
DATABASE_ERRORS = Counter("recsys_database_errors_total", "Database operation failures")
REDIS_ERRORS = Counter("recsys_redis_errors_total", "Redis operation failures", ("operation",))
RATE_LIMIT_DECISIONS = Counter(
    "recsys_rate_limit_decisions_total",
    "Application rate-limit decisions",
    ("scope", "outcome"),
)
OUTBOX_BACKLOG = Gauge("recsys_outbox_backlog", "Pending outbox events")
OUTBOX_OLDEST_AGE = Gauge(
    "recsys_outbox_oldest_age_seconds", "Age of the oldest pending outbox event"
)
OUTBOX_RETRY_ATTEMPTS = Gauge(
    "recsys_outbox_retry_attempts", "Accumulated attempts on pending outbox events"
)
OUTBOX_DEAD_LETTER_COUNT = Gauge(
    "recsys_outbox_dead_letter_count", "Current dead-letter outbox events"
)
ACTIVE_MODEL = Info("recsys_active_model", "Currently active recommendation model")

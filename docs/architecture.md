# Architecture

RecSys is a modular monolith. FastAPI modules share one PostgreSQL transaction boundary; Redis is disposable cache/broker state; Celery runs the durable outbox work; React is served through the same origin in production. Offline training reads only imported MovieLens ratings and publishes immutable artifacts.

```mermaid
flowchart LR
  Browser --> Caddy
  Caddy --> Web[React static site]
  Caddy --> API[FastAPI modular monolith]
  API --> DB[(PostgreSQL)]
  API --> Redis[(Redis)]
  Scheduler --> DB
  Scheduler --> Redis
  Redis --> Worker
  Worker --> DB
  Train[Offline PyTorch command] --> Artifact[Versioned model files]
  Artifact --> API
  Prometheus --> API
  Grafana --> Prometheus
```

## Rating and event sequence

```mermaid
sequenceDiagram
  Browser->>API: PUT rating + idempotency key + CSRF
  API->>DB: lock user, upsert rating, increment profile version, insert outbox
  DB-->>API: commit
  API-->>Browser: rating + profile version
  Scheduler->>DB: claim due rows SKIP LOCKED
  Scheduler->>Redis: publish event ID
  Worker->>DB: insert processed marker and complete event
```

The browser never receives source user IDs. Redis failure cannot lose the committed interaction because the outbox is in PostgreSQL. The worker can receive duplicates; `(event_id, consumer)` is unique. Dead letters are replayed only through an explicit, batch-validated operator command; `outbox_replays` preserves the reason and prior delivery state. Recommendation cache keys include user ID, profile version, active model version, limit, and watchlist behavior. Entries expire after five minutes. A short token-owned Redis reservation coalesces concurrent cold misses; Redis failure remains a direct-scoring, fail-open path.

## Session renewal

The access cookie expires after 15 minutes while the refresh session lasts up to 30 days. When an authenticated API request returns `401`, the browser client sends the refresh cookie with the current CSRF token, accepts the rotated access, refresh, and CSRF cookies, then retries the original request once. Concurrent requests on the same page share one refresh operation, and requests that receive a delayed `401` after renewal retry against the newer session revision. Login, registration, and refresh failures never recursively trigger renewal. A failed refresh preserves the original authentication error so the UI can return to sign-in normally.

Browser authentication and state changes reject a cross-site Fetch Metadata signal or an Origin/Referer authority that differs from the target host. The Vite development proxy and Caddy production proxy preserve the browser-facing authority; standard forwarded host/protocol headers are also understood. This check runs alongside the per-session CSRF token; origin-less non-browser clients remain supported. Registration, login, account changes, and event ingestion use shared Redis fixed-window limits. A Lua operation atomically increments the counter and establishes its expiry, including repair of a legacy key with no TTL. Redis errors fail closed for protected actions. Metrics use only fixed scope/outcome labels; client-derived hashes and user IDs remain exclusively in Redis keys.

Registration computes one Argon2id hash before deciding whether an account can be inserted, and always returns the same generic response. Login performs one Argon2id verification against either the stored hash or a static dummy hash generated with the same policy. This removes the dominant account-existence timing signal without claiming that database scheduling is constant-time.

## Recommendation sequence

For users with ratings, the API loads the single active model registry row, verifies checksums, and constructs an app-user vector from positively rated item embeddings. Negative ratings suppress related embeddings. Anonymous and no-rating requests skip model loading and use deterministic popularity/content ranking. Scores blend collaborative, genre, and popularity signals and filter rated/watchlisted items. A missing, corrupt, or inapplicable artifact returns fallback results with `fallback_reason`; training never runs in a request.

The single-host Compose deployment is a demo architecture with a host-level failure domain. It is not high availability.

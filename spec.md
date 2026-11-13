# RecSys: Master Implementation Specification

> **Role:** You are an autonomous coding agent building a complete, reviewable engineering portfolio project. Execute this specification in a new project directory. Treat it as the implementation contract, not as a request for a plan or a prototype. Work through the phases in order, run the stated checks, fix failures, and record honest results. Ask the human only for a decision that cannot be safely inferred, such as deployment credentials or legal permission for a different data source. Never invent test results, deployment status, performance numbers, commits, or product usage.

## 1. Product goal and boundaries

Build **RecSys**, a production-oriented, full-stack, personalized **movie recommendation platform**. A visitor can browse and search a real movie catalog. A registered user can choose favorite genres, rate movies, maintain a watchlist, view recommendations and similar movies, and understand at a high level why an item was suggested. The project must demonstrate backend, frontend, data, ML, operations, and security engineering through working code and measurable evidence.

Use a **modular monolith**: one FastAPI codebase with clear modules, one PostgreSQL database, one Redis instance, a separate asynchronous worker and scheduler process, a React frontend, and an offline PyTorch training command. Do not add microservices, Kafka, Kubernetes, vector databases, cloud-managed services, or paid APIs merely for appearance. The application must run locally with Docker Compose without credentials for a third-party movie API or cloud platform.

### Required stack and defaults

| Concern | Default | Reason |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic | Typed HTTP API and explicit persistence |
| Data | PostgreSQL 16, Redis 7 | Transactions, search indexes, cache, broker |
| Jobs | Celery with Redis broker; PostgreSQL transactional outbox | Async work without losing committed interaction events |
| ML | PyTorch CPU-compatible matrix factorization, NumPy, scikit-learn for a simple content representation | Reproducible collaborative and content-based components |
| Web | React, TypeScript, Vite, React Router, TanStack Query | Responsive SPA with typed API client |
| Packaging | Dockerfiles, Docker Compose, Python lockfile, npm lockfile | Repeatable setup |
| CI/CD | GitHub Actions, GHCR images, opt-in manual deployment to a VPS | Visible gates; deployment requires real credentials |
| Monitoring | JSON logs, OpenTelemetry-compatible trace IDs, Prometheus metrics, Grafana dashboards | Inspectable behavior |

Choose maintained compatible **patch versions at implementation time**, pin direct dependencies and commit resolved lockfiles. Record the actual versions in the README. Do not copy guessed version numbers into manifests. Use `uv` for Python dependency/lock management and `npm` for the frontend. If a selected dependency has an incompatibility, use the nearest compatible maintained version and document the change.

### Scope

**Required:** catalog browsing and search; registration and login; safe session management; genre onboarding; rating creation/update/removal; watchlist; recommendation feed; similar movies; cold-start behavior; ingestion of real MovieLens data; offline training/evaluation; versioned model publication; reliable events and async work; caching; tests; load tests; deployment artifacts; observability; full documentation.

**Out of scope unless all required gates pass:** payments, social features, user-uploaded posters, real-time streaming, external identity providers, A/B testing claims, live business analytics, and extra model families. A polished usable product matters more than a large feature list.

## 2. Start with Git; working rules

**The first implementation action is to initialize a Git repository in the new project directory.** If a valid repository already exists, inspect it and use that repository instead of nesting another. Do this before scaffolding or generating application files:

```bash
mkdir recsys && cd recsys
git init -b main
git status --short --branch
```

Copy this specification to the repository root as `spec.md`. Add a practical `.gitignore` and commit the specification, `.gitignore`, and initial project skeleton as the first meaningful commit. Never commit secrets, raw downloaded archives, database dumps, local caches, virtual environments, build outputs, model binaries, or generated personal data. Use a tracked `data/README.md`, `models/README.md`, and `.env.example` instead.

Make **at least 15 real, feature-scoped commits** over the implementation. Commit after a coherent, tested increment, with a descriptive message such as `feat(catalog): add paginated movie search`. The initial commit counts if it contains a meaningful foundation. Do not split one tiny edit into artificial filler commits, fabricate history, batch all work into one commit, or rewrite history to create a count. Check `git log --oneline` before delivery. Every commit must leave the repository in a reasonably buildable state; when a phase spans commits, keep incomplete functionality behind an internal boundary rather than breaking existing flows. Record the actual commit sequence and checks in the implementation log.

Use `main` for the integrated product. Branches/PRs are optional for a solo portfolio project. Keep `spec.md` current only if a justified deviation is needed; record the decision in `docs/decisions/`. Work autonomously: inspect errors, fix them, rerun relevant checks, then move to the next phase. Do not mark a phase complete merely because files exist.

## 3. Source data, metadata, and rights

### Required default dataset

Use **MovieLens `ml-latest-small`**, downloaded on demand from [the GroupLens archive](https://files.grouplens.org/datasets/movielens/ml-latest-small.zip), for the local demo and offline training. Its documented fields are `movies.csv` (`movieId,title,genres`), `links.csv` (`movieId,imdbId,tmdbId`), `ratings.csv` (`userId,movieId,rating,timestamp`), and `tags.csv`. The source README describes 100,836 ratings, 3,683 tags, 9,742 movies, and 610 anonymized users in its September 2018 generation. These counts are source descriptions, **not** a promise about a later download; record the actual archive checksum, source URL, download date, parsed counts, and validation counts at ingestion time. The “latest” dataset is meant for development and may change; do not call its offline evaluation a stable research benchmark. [GroupLens dataset page](https://grouplens.org/datasets/movielens/latest/) · [MovieLens small README and license](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html).

The MovieLens README restricts commercial or revenue-bearing use without permission, requires acknowledgment in resulting publications, allows redistribution under its conditions, and disallows implied GroupLens endorsement. Treat this project as a **non-commercial portfolio/demo**. Put attribution and the dataset citation in `README.md`, `docs/data.md`, and an in-app Credits page. Do not bundle the archive or transformed rating rows in the source repository or container images. If deploying a public demo, review current source terms first and avoid presenting dataset users as real app users. Do not publish imported anonymized user IDs through the API. For commercial use, obtain the necessary permission or replace the dataset with one licensed for that use.

### Optional metadata enrichment

The default catalog uses MovieLens titles, genres, extracted year, and generated local color/typographic placeholders. **Posters, descriptions, cast, and popularity are not in MovieLens `movies.csv`**; never silently invent them. `links.csv` gives external IDs but does not grant rights to third-party metadata. An optional, disabled-by-default TMDB enrichment adapter may fetch metadata only when the developer supplies a valid API token and enables it. Implement attribution, a Credits page with the required notice and approved TMDB logo, source/refresh metadata, rate limiting, cache expiry, and removal/fallback behavior if this adapter is built. TMDB states its API is free for non-commercial use with attribution and requires separate commercial arrangements. Do not check in fetched images, API keys, or derived metadata dumps without verifying current terms. [TMDB FAQ and attribution](https://developer.themoviedb.org/docs/faq) · [TMDB API getting started](https://developer.themoviedb.org/docs/getting-started).

Import `tags.csv` only if used: sanitize free text, limit length, avoid exposing individual tag authors, and treat tags as untrusted user-generated content. The simplest compliant implementation may omit tags from serving. Document that choice. The mandatory content model can use genres plus normalized title tokens, so enrichment is **not** a prerequisite.

### Import contract

Implement `make data-download` and `make data-import`. The download command must use HTTPS, an explicit source URL, a checksum verified against a pinned value or an operator-supplied expected SHA-256, retries with timeouts, and safe ZIP extraction. If GroupLens provides only another checksum type for this artifact, record and verify the strongest published checksum available and also compute SHA-256 for provenance; do not falsely claim upstream SHA-256 verification. Import with streaming/batched upserts, UTF-8 CSV parsing, idempotency, and row-level validation. A rerun must not duplicate catalog items or imported training events. Fail with actionable diagnostics for malformed headers, invalid ratings, unknown movie references, duplicate external IDs, or an unexpected empty dataset. Save only a local manifest (not the raw dataset) with file hashes, counts, date, and parser version. Restrict download and import to an explicit operator command; startup must not silently download data.

## 4. Architecture and service contracts

```text
Browser (React)
    | same-origin HTTPS /api/v1
Reverse proxy (Caddy in production)
    |----------------------> static frontend
    +----------------------> FastAPI modular monolith
                               | PostgreSQL: catalog, accounts, ratings,
                               | watchlist, outbox, model registry
                               | Redis: cache, rate limits, Celery broker
                               +--> outbox dispatcher/scheduler --> Celery worker
                               +--> immutable active model artifacts (read-only)
Offline CLI: MovieLens download/import --> train/evaluate --> publish model version
Prometheus --> internal metrics endpoints; Grafana --> Prometheus
```

Keep modules separate: `identity`, `catalog`, `interactions`, `events`, `recommendations`, `ml`, `operations`. Route handlers validate input and delegate to services; services own business rules; repositories encapsulate SQL. Do not import FastAPI objects into the ML training package. Use explicit dependency injection for database session, cache, clock, model registry, and configuration. Database state is the source of truth for accounts and interactions. Redis is disposable. Model artifacts are immutable and versioned; activation is an atomic pointer change in PostgreSQL, with serving processes reloading safely.

### Data flow and failure behavior

1. The browser fetches a catalog page; PostgreSQL serves filtered, indexed, paginated results. Redis may cache public hot queries.
2. A user submits a rating. In **one PostgreSQL transaction**, upsert the current rating, increment that user's `profile_version`, and insert an outbox event. Return only after commit. A retry with the same idempotency key must not create a second logical action.
3. The dispatcher claims pending outbox rows with `FOR UPDATE SKIP LOCKED`, publishes work, and marks dispatch state. A worker handles an event idempotently, records its result, updates inexpensive profile/cache state, and acknowledges it. Retry transient failures with bounded exponential backoff and jitter; move exhausted events to a dead-letter state visible to operators. Handle the crash window between publish and status update through idempotent processing.
4. Recommendation serving loads the active model version (never trains in a request), gets the user's current preferences/interactions, generates candidates, scores/re-ranks, filters seen/unavailable movies, and returns a result with model version and an honest explanation code. A cache entry is keyed by user, `profile_version`, model version, and relevant request parameters; use TTL as a backup. Changes invalidate naturally through versioning, even if worker dispatch is delayed.
5. If Redis is unavailable, cached reads can fall back to PostgreSQL/direct scoring and outbox events remain durable; do not silently drop an event. Fail closed for login rate limits if abuse controls cannot be enforced. If a model artifact is missing or corrupt, serve the deterministic non-ML fallback and emit an alertable metric. Do not claim such degraded responses were model-powered.

## 5. Domain and database design

Create Alembic migrations for these tables (names may vary if semantics stay exact):

| Entity | Required fields and constraints |
|---|---|
| `users` | UUID PK, unique normalized email, Argon2id password hash, created/updated timestamps, `profile_version`, `deleted_at`; no plaintext password |
| `sessions` | UUID PK, user FK, hashed refresh-token identifier, expiry, rotation/revocation timestamps, device label; cascade/delete rules documented |
| `movies` | internal ID, unique MovieLens ID, title, optional release year, genres, optional IMDb/TMDB IDs, active flag, source/provenance timestamps; index title search and genres |
| `imported_ratings` | source user integer + MovieLens movie key + rating + UTC event time; unique source-user/movie; **never** FK to `users` |
| `ratings` | user/movie unique pair, rating in 0.5 increments from 0.5 to 5, timestamps; unique index |
| `watchlist_items` | user/movie unique pair, created timestamp |
| `genre_preferences` | user/genre unique pair, created timestamp |
| `interaction_events` | UUID PK, nullable app-user FK or pseudonymous session ID as policy permits, movie FK, event type, occurred/received time, request id, consent/source; append-only, bounded retention |
| `outbox_events` | UUID PK, aggregate reference, event type, JSON payload with schema version, status, attempt count, next attempt, created/processed timestamps, error code; indexes for due work |
| `processed_events` | event UUID unique, consumer name, processed timestamp; unique(event, consumer) |
| `model_versions` | immutable version ID, artifact URI, SHA-256, training manifest URI, evaluation JSON, creation time, status, active flag; enforce one active version transactionally |
| `data_imports` | source name/version, checksum, counts, imported timestamp, status |

Use UTC-aware timestamps, explicit foreign keys, transaction boundaries, and least-privilege database roles where practical. Avoid hard deletes that leave orphaned events; implement account deletion as a coordinated operation that removes user data, sessions, ratings, preferences, and identifiable event payloads, then invalidates cache. If user data is ever included in training, deletion must also trigger retraining/removal from active artifacts; the default design trains **only on imported MovieLens ratings**, which keeps the deletion contract tractable. Do not retain emails or raw access tokens in logs, metrics, jobs, or model artifacts.

Use a stable internal movie ID in API responses. Keep the MovieLens ID as provenance, not an API primary key. Normalize year parsing cautiously; titles without a parseable year remain valid. Index `movies` for case-insensitive title search (PostgreSQL `pg_trgm` or full-text search) and validate/measure query plans. Document migration rollback limits for destructive migrations.

## 6. API and frontend behavior

Use `/api/v1` and generate OpenAPI from running code. Define Pydantic request/response models and consistent problem responses (`code`, `message`, `request_id`, optional field errors). Validate pagination limits (default 20, maximum 100), all IDs, sort keys, text length, and rating increments. Return 401 for unauthenticated, 403 for forbidden, 404 for absent resources, 409 for idempotency conflicts, 422 for validation failures, and 429 for rate limits. Never leak whether an email exists through registration or recovery flows.

| Endpoint | Contract |
|---|---|
| `GET /health/live`, `GET /health/ready` | Liveness does not depend on downstream services; readiness checks DB, critical configuration, and active model/fallback availability |
| `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` | Session cookies, token rotation/revocation, rate limits, CSRF enforcement |
| `GET /me`, `PATCH /me`, `DELETE /me`, `PUT /me/password` | Own profile only; password change/deletion require recent authentication, revoke sessions as appropriate; deletion clears user data |
| `GET /genres`, `PUT /me/genres` | Browse and save constrained genre selections |
| `GET /movies`, `GET /movies/{id}` | Search, filter, sort, paginate; include source-aware metadata and safe placeholders |
| `PUT /me/ratings/{movie_id}`, `DELETE /me/ratings/{movie_id}`, `GET /me/ratings` | Upsert/remove current rating, idempotency and event creation |
| `PUT /me/watchlist/{movie_id}`, `DELETE /me/watchlist/{movie_id}`, `GET /me/watchlist` | Own watchlist |
| `POST /events` | Strict allowlist for `impression`, `click`, `detail_view`; bounded event size, deduplication, consent rules, no client-controlled user ID |
| `GET /recommendations?limit=20`, `GET /movies/{id}/similar?limit=12` | Ranked, deduplicated, unseen/available items; source/explanation code, model version or fallback reason |

Expose safe browser-facing API documentation in development; protect or disable interactive docs in public production as appropriate. Return a clear empty state rather than an error when a new user has no ratings.

The React app must have: landing/discovery page, search and filters, movie detail, onboarding/genre selection, login/register, rating control, watchlist, personalized feed, account/privacy page, and Credits page. Use semantic HTML, keyboard-accessible controls, visible focus, labels and errors, responsive layout, loading/empty/error states, and image placeholders. Ratings and watchlist updates should feel immediate but roll back on failed requests. Display recommendations as suggestions, not guarantees. Show a truthful explanation such as “Based on your selected genres,” “Similar to movies you rated highly,” or “Popular in this catalog”; do not fabricate per-item causality.

Generate or maintain a typed frontend API client from the OpenAPI schema (or hand-write one with contract tests). Never store access or refresh tokens in `localStorage`. Prefer same-origin deployment to simplify cookies and CORS.

## 7. Recommendation design

Implement the entire path, from baseline to hybrid serving. Keep interfaces testable and allow deterministic fallback.

### 7.1 Baselines and candidate generation

1. Compute a **Bayesian-smoothed popularity** score from imported ratings (global mean plus a documented prior count), with a minimum-support rule. This is the default for anonymous visitors and a fallback for all users. Treat historical MovieLens rating counts as a catalog popularity proxy, not current popularity.
2. Build a content representation from MovieLens genres and optionally normalized title tokens. Use TF-IDF or sparse multi-hot features; fit only on training/catalog data as appropriate. For new/low-interaction users, rank by selected genres and recent positive ratings, with a popularity prior.
3. Train an offline PyTorch **implicit-feedback matrix-factorization** model on imported MovieLens ratings: map source user/movie IDs to contiguous indices; treat ratings >=4 as positives, <=2.5 as explicit negatives, omit 3/3.5 from preference loss; sample unseen negatives from each user's training-only candidate pool with a fixed seed. Document that an unobserved movie is not necessarily disliked. Include regularization, seed control, early stopping, CPU execution, saved item embeddings and maps.
4. Expose collaborative candidates from item embeddings. **Registered app users are not MovieLens source users.** For an app user with positive ratings, construct an online user vector from the embeddings of positively rated movies (weighted mean or a documented regularized projection), with negative ratings used for suppression/re-ranking. This must work without retraining or mapping app user IDs into the imported training user table. Compare against content candidates when few rated items have embeddings.
5. Merge popularity, content, collaborative, and exploration candidates; score with fixed, documented weights or a small deterministic rule set. Re-rank for diversity (e.g., cap consecutive same-genre items), exclude rated/watchlisted if user preference says so, exclude inactive items, and deduplicate. New catalog movies with no collaborative embedding must remain eligible through content/popularity. Keep explanations tied to actual candidate sources.

### 7.2 Cold-start contract

| State | Required behavior |
|---|---|
| Anonymous | Smoothed-popularity feed; no fabricated personalization |
| New account, no genres/ratings | Same feed; invitation to choose genres and rate movies |
| Genres chosen, no ratings | Content + popularity blend |
| 1–4 ratings | Content blend and online projection if eligible; display conservative explanation |
| 5+ useful ratings | Hybrid including collaborative candidates; still diversify/filter |
| New movie without interactions | Content route; do not require a model retrain to appear |
| Model missing or corrupt | Deterministic content/popularity fallback with explicit `fallback_reason` |

Specify whether watchlist items are suppressed from the main recommendation feed; default to suppress them. Keep a request flag if a user wants them included, validated and reflected in cache keys. For `similar`, use content similarity plus embedding similarity where available, excluding the query movie; this endpoint must work for anonymous visitors.

### 7.3 Offline evaluation and publication

Use a reproducible **per-source-user temporal split** for users with sufficient history. Reserve each eligible user's most recent positive interaction for test and preceding positive for validation; keep enough prior training positives (e.g., at least five) and document exclusions. Build negative-sampling pools from **training observations only**. Evaluate ranking against the full eligible catalog if feasible for `ml-latest-small`, masking training/validation items as appropriate. Report Recall@10, NDCG@10, coverage, catalog diversity, and segment metrics for short histories. Compare popularity, content, collaborative, and hybrid under the same split. Do not report sampled-negative ranking metrics as if they were full-catalog results. Treat the MovieLens “latest” split as a development measure, not a publication benchmark or live uplift.

Save each immutable model under `models/versions/<version>/` outside Git with embeddings, ID maps, content vectors/metadata, feature schema, source manifest, code commit SHA, hyperparameters, evaluation JSON, creation time, and checksums. Use a safe serialization format (`safetensors` or NumPy arrays and JSON); do not load untrusted pickle. Validate artifacts and run a serving smoke test before atomically activating a new version. Keep at least the previous known-good version for rollback. Loading must verify checksum/schema compatibility. Training is an explicit offline command or scheduled operator job, never triggered by a user request. A scheduled retrain is optional; if present, publish only after all evaluation/serving gates pass. Document data/model drift signals and when a human should retrain.

Do not require an arbitrary metric improvement that may be impossible on a tiny dataset. Require valid, nonzero outputs, no leakage, baseline comparison, and an explicit discussion of any regression. If hybrid underperforms its baseline, retain the stronger active strategy or adjust documented weights using validation only, then evaluate once on test.

## 8. Privacy and security

- Use Argon2id password hashing, short-lived access cookie, rotating refresh cookie with hashed server-side token identifiers, `HttpOnly`, `Secure` in HTTPS, `SameSite=Lax` or stricter, explicit expiry, revocation, and logout. Protect state-changing cookie-authenticated requests with a CSRF token or verified origin plus a documented defense; test the chosen design. Never include credentials in URLs.
- Restrict CORS to exact configured origins; default to same-origin. Add security headers, HTTPS at the edge, request-size limits, input validation, and parameterized queries. Escape user-derived strings in the UI. Do not create public administrative write endpoints.
- Rate-limit login, registration, password changes, and event ingestion using Redis. Add separate anonymous and authenticated limits. Keep abuse controls effective on multiple API replicas. Log failed attempts without plaintext secrets.
- Use least-privilege database/application users, non-root containers where practical, pinned image versions, dependency/security scans in CI, and environment-based secrets. `.env.example` contains names and safe placeholder values only. Production secrets live in the deployment environment or a secret manager, never Git or images.
- Define a privacy policy in `docs/privacy.md`: imported anonymized dataset scope, app data collected, purposes, event retention (default 30 days for raw app events), account export/deletion route, cache expiry, backup retention, and model-training boundary. Do not describe the app as GDPR-compliant without an actual legal and operational review. Implement an account export command or endpoint returning user-owned profile, ratings, watchlist, and events; test deletion/export. Avoid tracking users before consent where required by the deployment context.
- Keep event payloads minimal: event ID, authenticated user or short-lived pseudonym, movie ID, event type, timestamp, request ID. No IP in durable event payload; if web server logs IPs for security, set and document limited retention. Do not ingest raw free-text search terms into analytics by default.
- Add a threat-model note (`docs/threat-model.md`) covering credential theft, CSRF, enumeration, event forgery, broken object authorization, dependency compromise, and poisoned model artifacts, with corresponding tests/controls.

## 9. Observability, reliability, and performance

Emit structured JSON logs with timestamp, level, service, request/trace ID, route template, status, duration, model version, and error code. Redact tokens, passwords, email, raw event payloads, and query text. Propagate correlation IDs into queued jobs. Expose Prometheus metrics for request rate/errors/latency, DB and Redis errors, recommendation source/fallback counts, cache hit ratio, outbox backlog/age/retries/dead letters, training/publication duration, active model version, and worker heartbeat. Keep metrics labels low-cardinality (never user/movie IDs or email). Supply a Grafana dashboard JSON and alert rules for rising 5xx, prolonged outbox backlog, dead letters, no worker heartbeat, model-load failures, and readiness failure. Include an operator runbook for inspection, rollback, replay, and backup restore.

Set **test targets**, not claims: with the small dataset loaded, one API process on a documented machine should aim for recommendation p95 <=300 ms on warm cache and <=800 ms on cold cache under 50 concurrent users; catalog search p95 <=500 ms; 5xx <1% during a five-minute test. Record real machine/container resources, data size, test script, concurrency, achieved p50/p95/p99, throughput, errors, and bottleneck. If targets are missed, profile and fix a material bottleneck, then report final measurements honestly. Do not imply these numbers are internet-scale or a formal SLA. Use a bounded Redis TTL (e.g., 5 minutes) and cap cache keys/items. Avoid N+1 queries and evaluate indexes with `EXPLAIN (ANALYZE, BUFFERS)` on representative data.

Production Compose must include health checks, restart policies, persistent named volumes for PostgreSQL/model artifacts, resource limits where supported, a network boundary that does not publish DB/Redis/Prometheus to the public, and a migration step before traffic switches. Provide `pg_dump`/restore instructions and perform one local restore rehearsal. Explain that a single VPS is a demo deployment with single-host failure risk, not high availability.

## 10. Required repository structure

Use this layout unless a concrete dependency forces a small documented adjustment:

```text
recsys/
  .github/workflows/ci.yml
  .github/workflows/release.yml
  .github/workflows/deploy.yml
  .env.example
  .gitignore
  Makefile
  README.md                       # write fully at delivery phase
  spec.md
  pyproject.toml
  uv.lock
  docker-compose.yml             # local app + db + redis + worker + scheduler
  docker-compose.prod.yml        # deployment overrides + reverse proxy
  docker-compose.monitoring.yml  # optional local Prometheus/Grafana profile
  Dockerfile.api
  Dockerfile.web
  alembic.ini
  migrations/versions/
  backend/app/
    main.py
    core/{config,db,security,logging,metrics}.py
    modules/{identity,catalog,interactions,events,recommendations,operations}/
    api/v1/
    workers/{celery_app,outbox,handlers}.py
  backend/ml/
    data.py
    features.py
    models.py
    train.py
    evaluate.py
    artifacts.py
    serve.py
  backend/cli/{download_data,import_data,train_model,publish_model}.py
  frontend/
    package.json
    package-lock.json
    src/{app,components,features,lib,styles}/
    tests/
  tests/{unit,integration,api,e2e,performance}/
  infra/{caddy,prometheus,grafana}/
  docs/{architecture,data,model,privacy,threat-model,operations,deployment}.md
  docs/decisions/
  docs/implementation-log.md
  data/README.md                 # downloaded data ignored
  models/README.md               # generated artifacts ignored
```

Use `docs/architecture.md` for a component diagram, sequence diagrams for rating/outbox/recommendation paths, and explicit trade-offs. Keep migrations, schema diagrams, and API examples consistent with code.

### Required developer commands

Provide these exact `Makefile` targets, document prerequisites, and keep them working. Target recipes may invoke `uv`, `npm`, Docker, and scripts as appropriate, but should be noninteractive except where secrets or production action are involved.

```bash
make help                 # describe all targets
make bootstrap            # install locked local dependencies, copy .env.example if absent
make up                   # local Compose services, including API/web/worker/scheduler
make down                 # stop services without deleting volumes
make migrate              # apply migrations
make data-download        # explicit, verified dataset download
make data-import          # idempotent catalog/training-data import
make train                # deterministic offline training + evaluation
make model-publish        # validate and activate an artifact
make test                 # unit, integration, API, frontend tests
make test-e2e             # browser-level flow against running stack
make lint                 # Python and frontend lint/type checks
make load-test            # bounded local load scenario; save report
make monitoring-up        # local monitoring profile
make build                # build production container images
make smoke                # HTTP and worker/model sanity checks
```

`make up` must handle a fresh checkout predictably: create/configure the database and run migrations, but **must not** silently download MovieLens or train. Before import, show a clear “catalog not seeded” state with setup guidance. Document the first-run sequence exactly: `make bootstrap`, `make up`, `make data-download`, `make data-import`, `make train`, `make model-publish`, `make smoke`. The app remains usable with a fallback after import and before model publication.

## 11. Step-by-step implementation phases and gates

For every phase: implement it, add focused tests, run the relevant command, inspect outputs, fix failures, update documentation, then make a meaningful commit. Keep a short `docs/implementation-log.md` with date, commit SHA, checks run, and any remaining issue; do not invent entries.

### Phase 0 — Repository and decisions

Initialize Git as the first action. Copy `spec.md`; add `.gitignore`, license for **your source code** (clearly separate from dataset rights), `.env.example`, `Makefile` help, directories, and architecture decision notes. Record why modular monolith, MovieLens-small, PostgreSQL outbox, Redis/Celery, and offline training were selected. Commit the foundation.

**Gate:** `git status` is understood; no secrets/data in tracked files; first real commit exists; tree matches the planned layout.

### Phase 1 — Runnable skeleton

Create locked Python/frontend projects, typed configuration, FastAPI `/health/live`, React shell, development Dockerfiles, Compose API/web/PostgreSQL/Redis/worker/scheduler. Add startup health checks and a migration command. Make local startup deterministic and document environment variables. Commit backend/infra and frontend increments separately where coherent.

**Gate:** `make bootstrap`, `make up`, `make migrate`; browser renders shell; API health succeeds; clean restart works.

### Phase 2 — Schema and import

Implement migrations, constraints, repositories, dataset downloader, manifest, batch importer, catalog seed checks, title/genre indexes, and Credits content. Keep source users in `imported_ratings`, separate from `users`. Include transactional import behavior or resumable batches with an explicit import status. Test repeated import, malformed CSV, missing links, unusual titles, and source count reconciliation. Commit schema and importer as independent features.

**Gate:** `make data-download && make data-import`; actual row counts recorded; rerun changes no counts; no raw data tracked.

### Phase 3 — Identity and catalog API

Implement password hashing, registration/login/refresh/logout, session persistence, CSRF defense, authorization dependencies, account profile/deletion/export. Implement catalog list/detail/search/filter/pagination with indexes. Add API contract tests and security negative cases. Commit identity and catalog separately.

**Gate:** authentication and catalog routes work from clean DB; unauthorized access is rejected; search is indexed and paginated.

### Phase 4 — Usable frontend MVP

Build responsive catalog, search, detail, authentication, onboarding, error/loading/empty states, Credits and account views. Use a typed client, accessible controls, and real API responses. Add component and browser tests for primary paths. Commit UI increments by user-visible feature.

**Gate:** a new user can register, browse/search, log out and back in, and inspect a movie without manual API calls.

### Phase 5 — Interactions and durable events

Implement ratings, watchlist, genre preferences, `profile_version`, event ingestion, transactional outbox, dispatcher, idempotent handlers, bounded retry/dead-letter/replay tooling. Add unique idempotency keys scoped to user/action and a retention/purge job. Show rating/watchlist state in the UI. Test transaction rollback, duplicate request, duplicate delivery, worker crash/retry, exhausted retry, and Redis outage. Commit domain interactions and outbox/worker separately.

**Gate:** app state survives restart; one logical rating change produces one durable action; no event disappears during a simulated broker outage.

### Phase 6 — Deterministic recommendations

Implement smoothed popularity, content features, cold-start behavior, similar movies, filtering, diversity, truthful source labels, and versioned cache keys. Expose endpoints and build feed UI. Test empty/new user, genre preference, positive/negative rating, missing metadata, new movie, cache invalidation, and fallback when Redis is down.

**Gate:** all user states in the cold-start table return a valid, deduplicated feed; no model is required yet.

### Phase 7 — PyTorch training and evaluation

Implement deterministic dataset preparation, temporal split, negative sampling, matrix factorization training, baseline comparison, full-catalog ranking evaluation, artifact serialization/checksums, manifest and report. Add tests for leakage, ID mapping, reproducibility within sensible tolerance, empty/unknown items, and artifact corruption. Train on CPU with `ml-latest-small`; record actual training time/resources/results. Commit pipeline and evaluation/artifact work in coherent increments.

**Gate:** `make train` produces an inspectable valid candidate artifact and comparison report; test set was untouched during tuning.

### Phase 8 — Hybrid serving and safe model publication

Implement online app-user vector, candidate merge, scoring/re-ranking, model registry, validation, atomic activation, cache/version behavior, safe reload and rollback. Add integration tests for multiple API processes or reload simulations, unknown movie IDs, bad artifact, and mid-request model switch. Publish a real trained version using `make model-publish`; verify the UI changes source labels honestly. Commit serving and publication separately.

**Gate:** personalized recommendations work for an app user never present in MovieLens; rollback restores prior version; artifact corruption triggers safe fallback.

### Phase 9 — Hardening and observability

Add structured/redacted logging, traces/correlation, metrics, dashboards, alerts, request limits, scans, threat model, retention job, export/deletion verification, and operational runbook. Test security cases and metrics without high-cardinality labels. Commit security and observability separately.

**Gate:** monitoring shows real traffic, worker backlog and model status; account deletion removes live user data and invalidates recommendations.

### Phase 10 — Performance and deployment

Create a repeatable load scenario (e.g., Locust or k6) with realistic anonymous search, authenticated recommendation, rating, and watchlist traffic. Use seeded test accounts; avoid modifying the real imported dataset. Capture machine, data size, response distribution and errors. Profile material slow paths and optimize. Build production images; create Caddy HTTPS Compose deployment, GHCR publish on `main` **only after CI succeeds**, and a **manual** deployment workflow requiring a protected GitHub environment and configured host/SSH secrets. The workflow must pull immutable image digests, back up the database, apply migrations, start the new stack, run smoke/readiness checks, and restore the previous image/model pointer on failure; document the limits of reversing a database migration. Do not hardcode a server address or pretend a deployment occurred. Run migration, smoke and rollback checks in a staging/local production-like environment. Rehearse backup restore. Commit load/performance and deployment/CI changes separately.

**Gate:** CI passes from a clean checkout; production-like stack passes smoke; measured load report exists; CD workflow is verifiable but do not assert it actually deployed without a real target and evidence.

### Phase 11 — Final documentation and delivery

Only after the product is implemented, write a **complete `README.md`** describing the actual project and verified behavior. It must include: overview and architecture diagram; feature list; stack with actual versions; prerequisites; exact local setup and commands; environment variable table; dataset provenance/license and citation; optional metadata rights/attribution; schema and API summary with sample requests; recommendation and cold-start design; training/evaluation procedure and actual results; testing commands and actual status; performance methodology and actual numbers; security/privacy choices; deployment/CD setup and whether deployment really happened; monitoring/runbook links; known limitations; screenshots only if captured from the real app; and portfolio-friendly, evidence-based summary. Mark unavailable results “not run” or “not deployed,” with the reason. Do not use placeholders in final README except variables the operator must supply.

Run the full gate below, inspect `git log --oneline` and tracked files, resolve critical failures, commit README and final fixes meaningfully, and provide a concise handoff with real commands, achieved checks, live URL **only if one exists**, and limitations.

## 12. Test matrix and quality gates

| Layer | Minimum meaningful coverage |
|---|---|
| Unit | Rating constraints, genre parsing, rank/filter/diversity, cold-start transitions, score normalization, cache key versioning, model-user projection |
| DB integration | Alembic upgrade from empty DB, constraints/indexes, import idempotency, rating+outbox atomicity, account deletion/export |
| API | Auth/session/CSRF, ownership, pagination, event validation/idempotency, recommendation semantics, health and error format |
| Worker | Duplicate delivery, transient retry/backoff, dead-letter, replay, Redis outage, retention job |
| ML | Temporal split no leakage, mappings, negative sampling, deterministic seed behavior, baseline evaluation, artifact checksum/schema, safe fallback |
| Frontend | Form errors, accessible controls, catalog search, rating/watchlist state, onboarding, recommendation empty/error states |
| Browser E2E | Fresh user registers, selects genres, rates movies, sees updated feed, saves watchlist, logs out/in, deletes account |
| Performance | Documented five-minute mixed workload and measured latency/error report on loaded small dataset |
| Security | Dependency/container scan, secret scan, object authorization, CSRF and rate-limit tests, no sensitive logs |

Use pytest/pytest-asyncio and isolated PostgreSQL/Redis test services (Testcontainers or Compose), React Testing Library/Vitest, and Playwright for the critical browser path. Mock only external boundaries; use a real DB/broker for transaction and worker integration behavior. Tests must not rely on the public MovieLens server, TMDB, GHCR, or a cloud deployment. Provide a tiny synthetic fixture for CI; run a separate local/full-data smoke against the downloaded real dataset. Report coverage by package; target **>=80% backend line coverage and >=70% frontend statement coverage** for owned application code, but do not game thresholds with trivial tests or include generated/migration code. If thresholds are missed, list uncovered risk and add useful tests. CI must gate on formatting/lint, type checks, backend/frontend tests, migrations, build, dependency/secret scans, and a smoke test. E2E and full-data/load jobs may be separately triggered if runtime is too high, but their latest real result must be documented before delivery.

### Final acceptance checklist

The project is complete only when all of the following are true:

1. Git was initialized before project scaffolding and `git log` contains **at least 15 genuine, meaningful commits**; there are no fabricated or filler commits.
2. `make bootstrap`, `make up`, `make data-download`, `make data-import`, `make train`, `make model-publish`, `make smoke`, `make lint`, `make test`, and `make test-e2e` work on the documented environment, or any environmental block is stated precisely with evidence.
3. Real MovieLens data imports idempotently; source, checksum, counts, attribution and license boundaries are documented; no raw dataset or secrets are tracked.
4. A browser user can complete the entire registration → genre selection → search → rate/watchlist → recommendation → logout/login → deletion journey.
5. Cold-start, personalized, similar-movie, and model-failure routes behave as specified; an app user receives personalization without sharing an ID namespace with MovieLens users.
6. Interaction writes and outbox records are atomic; retries and duplicate delivery do not duplicate logical effects; dead letters are inspectable/replayable.
7. Offline training and evaluation are reproducible, leakage-checked, versioned, and honestly compared with baselines; serving never trains in request path.
8. Cookies/session, CSRF, rate limits, authorization, deletion/export, input validation, secret handling, and redacted logs have tests.
9. CI passes; production images build; deployment workflow, monitoring dashboard, alerts, backup/restore, and rollback procedure are present and locally exercised where possible.
10. Load report contains real observed metrics and context, including missed targets. The final README is complete, accurate, and written **after** implementation, with no invented outcomes.

## 13. Implementation decisions and honesty rules

When details are unspecified, choose the simplest option consistent with the contracts above; document it in `docs/decisions/` and continue. If time or infrastructure limits prevent a requirement, implement the greatest valid subset, mark the precise unmet criterion in the README and handoff, and do not label the project complete. A local production-like Compose deployment is useful evidence, but it is not proof of public availability. “Production-oriented” describes architecture and quality practices; claim “production-grade” or specific reliability only when real deployment and operational evidence support it. Do not present synthetic test accounts, historical MovieLens ratings, offline ranking scores, or locally generated load as real customer activity or online recommendation uplift.

Before every external dependency or data-source integration, recheck its current primary documentation and terms. If a source or API cannot be accessed, preserve the runnable no-credential path, explain the limitation, and continue. Deliver working software and inspectable evidence rather than a polished description of unfinished code.

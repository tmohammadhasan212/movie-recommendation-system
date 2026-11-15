# RecSys

RecSys is a production-oriented movie recommendation portfolio project. It runs a FastAPI modular monolith, PostgreSQL, Redis/Celery outbox processing, a responsive React catalog, verified MovieLens import, deterministic fallbacks, and an offline PyTorch model with checksum-verified publication.

## Verified features

- Checksum-verified, idempotent import of 9,742 movies and 100,836 ratings from MovieLens `ml-latest-small`
- Catalog search, genre filtering, detail and similar-movie pages
- Optional TMDB poster enrichment with lazy images and deterministic placeholders
- Argon2id accounts, secure session rotation and renewal, CSRF, rate limits, export and deletion
- Genres, ratings, watchlist, consented events, transactional outbox, idempotent worker, and audited dead-letter replay
- Popularity/genre cold start plus a published matrix-factorization hybrid for app users
- Versioned five-minute recommendation caching with cold-miss coalescing
- JSON request logs, live-state Prometheus metrics, Grafana dashboard and alert rules

## First run

Prerequisites: Python 3.12, `uv` 0.13.8, Node 22/npm, Docker Compose, and 4 GB available container memory.

```bash
make bootstrap
make up
make data-download
make data-import
# Optional: set TMDB_API_TOKEN or TMDB_API_KEY in .env, then enrich a bounded batch.
make metadata-enrich
make train
make model-publish
make smoke
```

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs` in development. Raw data, local manifests, secrets, and model binaries are ignored by Git. Poster enrichment is optional and never runs during startup or import. Each `make metadata-enrich` run refreshes at most 250 stale TMDB-linked movies; rerun it to continue through the catalog.

Production uses a separate fail-closed configuration. Copy `.env.production.example` to the target host's ignored `.env`, replace every placeholder, and follow [the deployment guide](docs/deployment.md). Development defaults are rejected when `APP_ENV=production`.

## Stack versions

Direct Python and npm dependencies are exactly pinned in `pyproject.toml`, `uv.lock`, `frontend/package.json`, and `frontend/package-lock.json`. Core observed versions include Python 3.12, FastAPI 0.162.7, SQLAlchemy 2.1.8, PyTorch 2.15.0, React 19.3.1, TypeScript 7.0.2, PostgreSQL 16, and Redis 7.

## Local verification

```bash
make lint                 # Python and frontend static checks
make test                 # Python and frontend unit/API tests
make test-e2e             # two browser journeys; requires the local stack
make smoke                # liveness, readiness, Redis, and active model
docker-compose run --rm api alembic check
make monitoring-up        # Prometheus on :9090 and Grafana on :3000
```

The opt-in live API test runs with `LIVE_STACK=1 uv run pytest tests/integration/test_live_stack.py -q`. A clean release database must pass both `alembic upgrade head` and `alembic check`; CI enforces that migration chain and schema parity.

## Data rights

This is a non-commercial demo. MovieLens data has separate terms from the MIT-licensed project source. GroupLens does not endorse this project. Optional poster paths and remotely served images come from TMDB under its separate API terms and attribution requirements. See [data provenance and rights](docs/data.md) and the in-app Credits page.

## Recommendation evidence

The locally trained hybrid achieved Recall@10 `0.0490`, NDCG@10 `0.0248`, and catalog coverage `0.0779` across 592 eligible source users. These are offline development results, not online uplift. See [model design and full baseline table](docs/model.md).

## Release-candidate checks observed on 2026-11-15

- Locked installs, Ruff, TypeScript, and the production frontend build passed.
- Python unit/API/ML/security tests: 83 passed, with one opt-in live-stack test skipped; all six Vitest tests passed.
- The live API journey passed; both Playwright journeys passed, including TMDB attribution and the complete account lifecycle.
- A clean isolated production database replayed migrations `0001` through `0005`; `alembic check` reported no schema drift on both clean and existing databases.
- Docker API/web/worker/scheduler were healthy. Non-root production API/web images carried exact revision labels; API liveness/readiness and disabled production docs passed, and the web image served root and deep links with security headers.
- Prometheus and Grafana were healthy; the API scrape target was `up`, and all seven alert rules parsed, loaded, and evaluated successfully.
- `npm audit` found zero vulnerabilities; the Python production lock had no known vulnerabilities in the local advisory audit.
- GitHub-hosted CI passed on Ubuntu 26.04, including tests, clean migrations, schema parity, production image builds, advisory audits, and a full-history Gitleaks scan with no leaks. The release workflow published both revision-labelled images to GHCR.

Historical data import, model, restore, search-plan, and performance evidence is retained in [the implementation log](docs/implementation-log.md) and the linked evidence documents.

## Performance evidence

On a 12-logical-CPU Apple Silicon host with Colima limited to 2 CPUs and 4 GiB RAM, one API process handled a five-minute mixed read test at 50 concurrent clients: 90,450 requests, 301.5 requests/second, no errors, 161.4 ms overall p95, 149.8 ms recommendation p95, and 170.2 ms search p95. A separate 50-way preconnected cold-cache burst had 233.4 ms p95 and no errors. The original uncached baseline was 20.2 requests/second with 2,483 ms p95; the measured bottleneck was repeated aggregation over 100,836 ratings. These are local development measurements, not an SLA or internet-scale claim. See [performance evidence](docs/performance.md) and the committed JSON reports.

A public VPS deployment, rollback rehearsal, and container/SBOM signing have not occurred. The production deployment therefore remains an opt-in demo design, not a production-grade or highly available service.

Architecture, privacy, threat model, operations, and deployment notes are under [`docs/`](docs/).

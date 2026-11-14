# RecSys

RecSys is a production-oriented movie recommendation portfolio project. It runs a FastAPI modular monolith, PostgreSQL, Redis/Celery outbox processing, a responsive React catalog, verified MovieLens import, deterministic fallbacks, and an offline PyTorch model with checksum-verified publication.

## Verified features

- Checksum-verified, idempotent import of 9,742 movies and 100,836 ratings from MovieLens `ml-latest-small`
- Catalog search, genre filtering, detail and similar-movie pages
- Argon2id accounts, secure session rotation, CSRF, rate limits, export and deletion
- Genres, ratings, watchlist, consented events, transactional outbox and idempotent worker
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
make train
make model-publish
make smoke
```

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs` in development. Raw data, local manifests, secrets, and model binaries are ignored by Git.

## Stack versions

Direct Python and npm dependencies are exactly pinned in `pyproject.toml`, `uv.lock`, `frontend/package.json`, and `frontend/package-lock.json`. Core observed versions include Python 3.12, FastAPI 0.162.7, SQLAlchemy 2.1.8, PyTorch 2.15.0, React 19.3.1, TypeScript 7.0.2, PostgreSQL 16, and Redis 7.

## Data rights

This is a non-commercial demo. MovieLens data has separate terms from the MIT-licensed project source. GroupLens does not endorse this project. See [data provenance and rights](docs/data.md) and the in-app Credits page.

## Recommendation evidence

The locally trained hybrid achieved Recall@10 `0.0490`, NDCG@10 `0.0248`, and catalog coverage `0.0779` across 592 eligible source users. These are offline development results, not online uplift. See [model design and full baseline table](docs/model.md).

## Checks observed on 2026-11-14

- Python unit/API/ML tests: 26 passed, one opt-in live-stack test skipped
- Frontend TypeScript check: passed; frontend tests: 2 passed; production build: passed
- Live Compose journey: passed registration through account deletion
- Playwright browser journey: 1 passed, covering the complete account flow
- Real import rerun: counts stayed at 9,742 movies, 100,836 source ratings, one import record
- Docker API/web/worker/scheduler: healthy; production API/web images built and web image smoke-tested
- Prometheus/Grafana: healthy; API scrape target `up=1`; six alert rules loaded successfully
- Isolated PostgreSQL restore rehearsal: source/restored counts matched at migration `0003`
- Selective title search: trigram bitmap-index plan, 0.097 ms execution on the local catalog

## Performance evidence

On a 12-logical-CPU Apple Silicon host with Colima limited to 2 CPUs and 4 GiB RAM, one API process handled a five-minute mixed read test at 50 concurrent clients: 90,450 requests, 301.5 requests/second, no errors, 161.4 ms overall p95, 149.8 ms recommendation p95, and 170.2 ms search p95. A separate 50-way preconnected cold-cache burst had 233.4 ms p95 and no errors. The original uncached baseline was 20.2 requests/second with 2,483 ms p95; the measured bottleneck was repeated aggregation over 100,836 ratings. These are local development measurements, not an SLA or internet-scale claim. See [performance evidence](docs/performance.md) and the committed JSON reports.

GitHub-hosted CI/audit jobs, a public VPS deployment, rollback rehearsal, and container/SBOM signing have not occurred. The production deployment therefore remains an opt-in demo design, not a production-grade or highly available service.

Architecture, privacy, threat model, operations, and deployment notes are under [`docs/`](docs/).

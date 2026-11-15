# Implementation log

All entries below are observed repository history and local checks, not planned results. The delivery-documentation commit containing this file necessarily follows the implementation commits listed here.

## Commit sequence

1. `cb602d1` — initialize repository and architecture decisions
2. `abb1753` — verify MovieLens archives and source CSV structure
3. `616f014` — add transactional domain schema
4. `e564095` — batch-upsert catalog and imported ratings
5. `02eed67` — expose catalog and cookie-backed account routes
6. `9f167b9` — build accessible catalog discovery UI
7. `d8eded9` — add locked Docker runtime and offline ML dependency group
8. `222476c` — persist ratings, watchlists, preferences, and outbox rows
9. `31da03d` — add deterministic popularity and genre recommendations
10. `49fa435` — dispatch the durable outbox through idempotent Celery work
11. `0d5659d` — add onboarding, ratings, watchlist, and feed UI
12. `04c1c73` — verify the published GroupLens checksum and provenance
13. `099d81c` — handle ambiguous TMDB links during real import
14. `15ad007` — parse the published GroupLens MD5 format
15. `32a055d` — add consented events, export, deletion, and recent-auth controls
16. `473ac3a` — include the Celery Redis transport dependency
17. `6fb09f6` — verify the live registered-user API journey
18. `c5b2052` — train and evaluate reproducible matrix factorization
19. `13e8a43` — publish and serve checksum-verified hybrid models
20. `ca846ac` — add caching, operational metrics, retention, and trigram search
21. `c1c8013` — add frontend unit and browser account journeys
22. `278b11c` — add production images, monitoring, and CI/CD delivery files
23. `a962d45` — coalesce cold recommendation cache misses
24. `a1f9dde` — record architecture, operations, and measured evidence
25. `3291a46` — add optional TMDB poster enrichment
26. `7d7af4f` — record poster enrichment verification
27. `766571e` — support TMDB v3 API keys
28. `1e73d6b` — bind releases to verified revisions
29. `d64c3a2` — reject unsafe production defaults
30. `9c86553` — renew expired browser sessions
31. `3ac01e6` — add audited dead-letter replay
32. `d9216bd` — expose rate-limit health metrics and alerts
33. `02e1b5d` — enforce API ownership boundaries in tests
34. `51922ae` — reject cross-origin session requests
35. `0e48bd2` — reduce account timing signals
36. `f108278` — verify clean database bootstrap and schema parity
37. `2e54476` — update hosted Actions and restore the security audit
38. `023d906` — pin the published setup-uv release tag
39. `908bab9` — use Docker Compose v2 on Ubuntu 26 hosted runners

## Observed gates on 2026-11-14

- Locked Python install and frontend install completed; local stack runs under Colima/Docker.
- MovieLens SHA-256: `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436`.
- Import and idempotent rerun: 9,742 movies, 100,836 ratings, one import record.
- Offline training: 592 eligible users, 113,557 examples, eight epochs, 0.820 seconds.
- Hybrid evaluation: Recall@10 0.04899, NDCG@10 0.02480, coverage 0.07791.
- Published model `mf-20261114T082603Z` passed checksum/schema validation and became the sole active registry row.
- Python: Ruff passed; Pytest reported 26 passed and one opt-in live-stack skip.
- Frontend: TypeScript passed; two Vitest tests passed; Vite production build passed.
- Live API journey and Playwright account journey passed; Playwright reported one test passed in 3.5 seconds on the final rerun.
- `make smoke` passed liveness, readiness, Redis, and active-model checks.
- Production API and web images built; the non-root web image returned the SPA root and deep link with security headers.
- Prometheus 3.7.3 and Grafana 12.3.0 started healthy; the API target reported `up=1` and all six alert rules loaded with healthy evaluation state.
- Five-minute load and 50-way cold burst passed the documented targets; see `docs/performance.md`.
- Selective trigram query used a bitmap index scan and completed in 0.097 ms.
- Isolated `pg_dump`/`pg_restore` rehearsal matched source counts and migration revision, then temporary state was removed.

## Poster enrichment gates on 2026-11-15

- Alembic revision `0004` applied to the live PostgreSQL database and added the three nullable poster metadata columns.
- The live catalog API returned the new poster fields and preserved the placeholder fallback while no TMDB token was configured.
- The explicit enrichment command rejected the missing token without changing catalog data.
- Python: Ruff passed; Pytest reported 31 passed and one opt-in live-stack skip.
- Frontend: TypeScript passed; two Vitest tests and two Playwright journeys passed; the Vite production build passed.
- `make smoke` passed liveness, readiness, Redis, and active-model checks.
- Production images built; the web image served the `/credits` deep link with a CSP allowing only the configured TMDB image and logo hosts.

## Release-candidate gates on 2026-11-15

- Locked Python and npm dependency checks passed; Ruff, TypeScript, and the Vite production build passed.
- Pytest reported 83 passed and one opt-in live-stack skip; Vitest reported six passed; the opt-in live API test reported one passed; Playwright reported two passed.
- The full Compose stack rebuilt successfully. API liveness/readiness, Redis, active-model, worker, scheduler, and migration-job checks passed.
- An isolated empty PostgreSQL instance replayed migrations `0001` through `0005` under production configuration. `alembic check` found no drift there or on the existing stack.
- The release audit found that revision `0001` imported mutable application metadata. It now owns a frozen original-schema snapshot, preventing later revisions from colliding during clean installs; CI now checks both migration replay and schema parity.
- Production API and web images ran as non-root users and carried the exact source-revision label. The API passed production liveness/readiness with `/docs` disabled; the web image served `/` and `/account` with its CSP and cache policy.
- Prometheus found seven valid rules, scraped the API target as healthy, and evaluated every loaded rule successfully; Grafana reported its database healthy.
- `npm audit --audit-level=high` found zero vulnerabilities. The Python production lock had no known vulnerabilities when audited with Python 3.12 and dependency resolution disabled.
- Tracked secret-filename inspection found only the two committed example environment files.
- GitHub Actions CI run `43725323834` passed both jobs on Ubuntu 26.04. The test job completed in 2m23s after running Ruff, 83 Python tests, six frontend tests, the production frontend build, clean migrations plus schema parity, Compose validation, production image builds, and revision-label checks.
- The hosted audit reported no known Python or npm vulnerabilities and no secrets in the full Git history; Gitleaks produced a SARIF artifact with a “No leaks detected” result.
- Release-images run `43725534896` verified the CI-tested revision and published the API and web images for `908bab930ce5dcf1a35de18968ea52581a082957` to GHCR.

## Remaining external gates

No VPS credentials were supplied, and no public deploy or rollback rehearsal occurred. Container/SBOM signing also remains external work.

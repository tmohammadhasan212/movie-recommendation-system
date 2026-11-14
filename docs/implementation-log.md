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

## Remaining external gates

GitHub-hosted workflows and their dependency/secret audits have not run, no VPS credentials were supplied, and no public deploy or rollback rehearsal occurred.

# Performance evidence

These are local development measurements, not a formal SLA or an internet-scale capacity claim.

## Environment and workload

- Host: Apple Silicon macOS 26.5, 12 logical CPUs
- Container runtime: Colima, 2 vCPUs, 4 GiB RAM, 20 GiB disk
- Serving: one Uvicorn API process, PostgreSQL 16, Redis 7
- Data: 9,742 movies, 100,836 imported ratings, one active model
- Sustained workload: `tests/performance/load.py`, 50 threads, five minutes, equal rotation through catalog, title search, and anonymous recommendations
- Cold workload: `tests/performance/cold_cache.py`, 50 preconnected clients released simultaneously after deleting the exact recommendation result/reservation keys

Preconnecting the cold clients excludes a macOS-to-Colima port-forward artifact: opening 50 brand-new TCP connections at exactly the same instant added about five seconds before requests reached Uvicorn. API logs showed 179–282 ms server duration during that diagnostic run. Sustained testing still measures ordinary end-to-end connection behavior.

## Results

| Run | Requests | Throughput | Errors | p50 | p95 | p99 |
|---|---:|---:|---:|---:|---:|---:|
| Uncached mixed baseline | 6,050 | 20.2 req/s | 0 | 1,407.7 ms | 2,483.1 ms | 2,805.7 ms |
| Cached mixed final | 90,450 | 301.5 req/s | 0 | 109.4 ms | 161.4 ms | 181.7 ms |
| Cold recommendation burst | 50 | n/a | 0 | 210.7 ms | 233.4 ms | 234.3 ms |

Final sustained route p95 was 157.7 ms for catalog browsing, 170.2 ms for title search, and 149.8 ms for recommendations. All stated targets passed: warm recommendation p95 at most 300 ms, cold recommendation p95 at most 800 ms, catalog search p95 at most 500 ms, and server errors below 1%.

## Bottlenecks and fixes

The uncached feed grouped all 100,836 imported ratings on every request. A five-minute, versioned Redis result cache removed that repeated work. Profile and model versions provide natural invalidation. A subsequent cold burst exposed a stampede and unnecessary model artifact load for anonymous users; token-owned request coalescing and skipping unused model loading reduced application-level cold p95 below the target. Redis failures still fall back to direct deterministic scoring.

PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` on selective `%interstellar%` title search used `ix_movies_title_trgm` through a bitmap index scan and completed in 0.097 ms after migration `0003`. The planner may still prefer a sequential scan for broad terms on this deliberately small catalog.

Raw results are in `performance-baseline.json`, `performance-results.json`, and `performance-cold-cache.json`.

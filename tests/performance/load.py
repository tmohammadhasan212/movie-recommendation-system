"""Bounded mixed read load; set LOAD_SECONDS=300 for the acceptance run."""

from __future__ import annotations

import json
import os
import platform
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

BASE_URL = os.getenv("LOAD_BASE_URL", "http://localhost:8000")
DURATION = int(os.getenv("LOAD_SECONDS", "300"))
CONCURRENCY = int(os.getenv("LOAD_CONCURRENCY", "50"))
PATHS = ("/api/v1/movies?limit=20", "/api/v1/movies?q=toy&limit=20", "/api/v1/recommendations?limit=20")


def one(index: int) -> tuple[str, float, bool]:
    path = PATHS[index % len(PATHS)]
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=10) as response:
            ok = response.status < 500
            response.read()
    except (OSError, urllib.error.URLError):
        ok = False
    return path, (time.perf_counter() - start) * 1000, ok


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * quantile))]


def summarize(results: list[tuple[str, float, bool]], elapsed: float) -> dict[str, object]:
    latency = [row[1] for row in results]
    errors = sum(not row[2] for row in results)
    return {
        "requests": len(results),
        "throughput_rps": len(results) / elapsed,
        "errors": errors,
        "error_rate": errors / len(results),
        "latency_ms": {
            "mean": statistics.mean(latency),
            "p50": percentile(latency, 0.50),
            "p95": percentile(latency, 0.95),
            "p99": percentile(latency, 0.99),
        },
    }


if __name__ == "__main__":
    started = time.monotonic()
    results: list[tuple[str, float, bool]] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        batch = 0
        while time.monotonic() - started < DURATION:
            results.extend(pool.map(one, range(batch, batch + CONCURRENCY)))
            batch += CONCURRENCY
    elapsed = time.monotonic() - started
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "base_url": BASE_URL,
        "duration_seconds": elapsed,
        "concurrency": CONCURRENCY,
        "machine": {
            "platform": platform.platform(),
            "logical_cpus": os.cpu_count(),
        },
        "overall": summarize(results, elapsed),
        "routes": {
            path: summarize([row for row in results if row[0] == path], elapsed)
            for path in PATHS
        },
    }
    target = Path(os.getenv("LOAD_REPORT", "docs/performance-results.json"))
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

"""Measure one simultaneous cold-cache recommendation burst."""

from __future__ import annotations

import json
import os
import platform
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

BASE_URL = os.getenv("LOAD_BASE_URL", "http://localhost:8000")
CONCURRENCY = int(os.getenv("LOAD_CONCURRENCY", "50"))
BARRIER = threading.Barrier(CONCURRENCY)
TARGET = urlsplit(BASE_URL)


def one() -> tuple[float, bool]:
    connection = HTTPConnection(TARGET.hostname, TARGET.port or 80, timeout=15)
    connection.connect()
    BARRIER.wait()
    start = time.perf_counter()
    try:
        connection.request("GET", "/api/v1/recommendations?limit=20")
        response = connection.getresponse()
        ok = response.status < 500
        response.read()
    except OSError:
        ok = False
    finally:
        connection.close()
    return (time.perf_counter() - start) * 1000, ok


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * quantile))]


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(lambda _: one(), range(CONCURRENCY)))
    latency = [row[0] for row in results]
    errors = sum(not row[1] for row in results)
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "base_url": BASE_URL,
        "scenario": "single simultaneous preconnected anonymous recommendation burst after key deletion",
        "concurrency": CONCURRENCY,
        "machine": {"platform": platform.platform(), "logical_cpus": os.cpu_count()},
        "requests": len(results),
        "errors": errors,
        "error_rate": errors / len(results),
        "latency_ms": {
            "mean": statistics.mean(latency),
            "p50": percentile(latency, 0.50),
            "p95": percentile(latency, 0.95),
            "p99": percentile(latency, 0.99),
        },
    }
    target = Path("docs/performance-cold-cache.json")
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

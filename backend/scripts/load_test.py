#!/usr/bin/env python3
"""
Ente Naadu - API Performance & Load Testing Suite
Lightweight, multi-threaded benchmarking tool using standard library (concurrent.futures + urllib).
Zero external dependencies required.
"""

import sys
import time
import statistics
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_HOST = "http://127.0.0.1:8000"
ENDPOINTS = [
    ("/api/v1/directory/services/", "Public Directory API"),
    ("/api/v1/shops/", "Public Shops List API"),
    ("/api/v1/events/notices/", "Community Notices API"),
]

def make_request(url: str, timeout: float = 10.0):
    start_time = time.perf_counter()
    status_code = 0
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EnteNaadu-LoadTester/1.0",
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
            _ = response.read()
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return (True, status_code, elapsed_ms)
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return (e.code < 500, e.code, elapsed_ms)
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return (False, 0, elapsed_ms)

def run_benchmark(base_url: str, path: str, label: str, total_requests: int = 100, concurrency: int = 10):
    full_url = f"{base_url.rstrip('/')}{path}"
    print(f"\n" + "=" * 70)
    print(f"BENCHMARK: {label}")
    print(f"Target:      {full_url}")
    print(f"Requests:    {total_requests} | Concurrency: {concurrency}")
    print("-" * 70)

    latencies = []
    success_count = 0
    fail_count = 0
    status_distribution = {}

    start_bench = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, full_url) for _ in range(total_requests)]
        for future in as_completed(futures):
            ok, status, ms = future.result()
            latencies.append(ms)
            status_distribution[status] = status_distribution.get(status, 0) + 1
            if ok and status in (200, 201, 301, 302):
                success_count += 1
            else:
                fail_count += 1

    total_duration_sec = time.perf_counter() - start_bench
    rps = total_requests / total_duration_sec if total_duration_sec > 0 else 0

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    avg_latency = statistics.mean(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    print(f"Total Time:      {total_duration_sec:.2f} s")
    print(f"Throughput:      {rps:.2f} req/sec")
    print(f"Success/Fail:    {success_count} passed / {fail_count} failed")
    print(f"Status Codes:    {dict(status_distribution)}")
    print(f"Latency Min:     {min_latency:.2f} ms")
    print(f"Latency Avg:     {avg_latency:.2f} ms")
    print(f"Latency P50:     {p50:.2f} ms")
    print(f"Latency P95:     {p95:.2f} ms")
    print(f"Latency P99:     {p99:.2f} ms")
    print(f"Latency Max:     {max_latency:.2f} ms")
    print("=" * 70)

def main():
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    requests_num = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    concurrency_num = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    print("*" * 70)
    print(f"ENTE NAADU LOAD & API PERFORMANCE TESTING")
    print(f"Testing against base host: {host}")
    print("*" * 70)

    for path, label in ENDPOINTS:
        run_benchmark(host, path, label, total_requests=requests_num, concurrency=concurrency_num)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Run VFS readiness benchmark and enforce threshold gates."""

from __future__ import annotations

import argparse
import json
import os
import sys

from ipfs_kit_py.vfs_readiness_benchmark import run_vfs_readiness_benchmark, write_benchmark_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VFS readiness throughput benchmark")
    parser.add_argument("--samples", type=int, default=int(os.environ.get("IPFS_KIT_VFS_BENCH_SAMPLES", "20")))
    parser.add_argument(
        "--mutation-p95-ms",
        type=float,
        default=float(os.environ.get("IPFS_KIT_VFS_BENCH_MUTATION_P95_MS", "500")),
    )
    parser.add_argument(
        "--queue-lag-p95-ms",
        type=float,
        default=float(os.environ.get("IPFS_KIT_VFS_BENCH_QUEUE_LAG_P95_MS", "3000")),
    )
    parser.add_argument(
        "--queue-wait-timeout-sec",
        type=float,
        default=float(os.environ.get("IPFS_KIT_VFS_BENCH_QUEUE_WAIT_TIMEOUT_SEC", "5.0")),
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("IPFS_KIT_VFS_BENCHMARK_OUT", "build/vfs_readiness_benchmark.json"),
    )
    args = parser.parse_args()

    result = run_vfs_readiness_benchmark(
        samples=args.samples,
        queue_wait_timeout_sec=args.queue_wait_timeout_sec,
        mutation_p95_threshold_ms=args.mutation_p95_ms,
        queue_lag_p95_threshold_ms=args.queue_lag_p95_ms,
    )

    output_path = write_benchmark_result(result, args.output)
    print(json.dumps({"output": output_path, **result}, indent=2, sort_keys=True))

    if not result.get("success", False):
        print("VFS readiness benchmark thresholds failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

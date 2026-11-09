"""VFS readiness throughput benchmark helpers.

This module provides a lightweight benchmark focused on:
- mutation-to-index latency (write path)
- async enrichment queue lag

The benchmark intentionally uses in-memory VFS mounts and metadata-index polling so
it can run in CI without external daemons.
"""

from __future__ import annotations

import datetime
import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(float(v) for v in values)
    rank = (len(ordered) - 1) * max(0.0, min(100.0, pct)) / 100.0
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _wait_for_queue_settle(manager: Any, *, key: str, timeout_sec: float) -> Optional[float]:
    deadline = time.time() + max(0.1, timeout_sec)
    while time.time() < deadline:
        with manager._index_lock:
            entry = manager.metadata_index.get(key)
        status = entry.get("accelerate_status") if isinstance(entry, dict) else None
        reason = status.get("reason") if isinstance(status, dict) else None
        if reason not in {"queued", "queue_full"}:
            return float((time.time() - (deadline - timeout_sec)) * 1000.0)
        time.sleep(0.01)
    return None


def run_vfs_readiness_benchmark(
    *,
    samples: int = 20,
    queue_wait_timeout_sec: float = 5.0,
    mutation_p95_threshold_ms: float = 500.0,
    queue_lag_p95_threshold_ms: float = 3000.0,
) -> Dict[str, Any]:
    # Local imports keep benchmark module cheap to import in unrelated code paths.
    from ipfs_kit_py.ipfs_datasets_integration import IPFSDatasetsManager
    from ipfs_kit_py.ipfs_fsspec import get_vfs, vfs_write

    with tempfile.TemporaryDirectory(prefix="vfs_readiness_bench_") as tmp_dir:
        home_dir = Path(tmp_dir) / "home"
        home_dir.mkdir(parents=True, exist_ok=True)

        old_env = {
            "HOME": os.environ.get("HOME"),
            "IPFS_KIT_ACCELERATE_ASYNC_ENRICH": os.environ.get("IPFS_KIT_ACCELERATE_ASYNC_ENRICH"),
            "IPFS_KIT_ASYNC_BACKEND": os.environ.get("IPFS_KIT_ASYNC_BACKEND"),
        }
        os.environ["HOME"] = str(home_dir)
        os.environ["IPFS_KIT_ACCELERATE_ASYNC_ENRICH"] = "1"
        os.environ["IPFS_KIT_ASYNC_BACKEND"] = "asyncio"

        manager = IPFSDatasetsManager(enable=False)
        vfs = get_vfs()
        for mount in list(vfs.mounts.keys()):
            vfs.unmount(mount)

        vfs.configure_integrations(datasets_manager=manager, accelerate_module=None)
        vfs.mount("/tmp/vfs-benchmark", "memory", "/")

        mutation_ms: List[float] = []
        queue_lag_ms: List[float] = []
        failures = 0

        try:
            for i in range(max(1, int(samples))):
                path = f"/tmp/vfs-benchmark/sample-{i}.txt"
                payload = f"sample-{i}-at-{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
                t0 = time.perf_counter()
                result = vfs_write(path, payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                mutation_ms.append(elapsed_ms)

                if not result.get("success"):
                    failures += 1
                    continue

                key = manager._index_key(path=path)
                queue_start = time.time()
                lag = _wait_for_queue_settle(
                    manager,
                    key=key,
                    timeout_sec=queue_wait_timeout_sec,
                )
                if lag is None:
                    queue_lag_ms.append((time.time() - queue_start) * 1000.0)
                    failures += 1
                else:
                    queue_lag_ms.append(lag)
        finally:
            manager.stop_async_enrichment(drain=True, timeout_sec=2.0)
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    mutation_p95 = _percentile(mutation_ms, 95.0)
    queue_p95 = _percentile(queue_lag_ms, 95.0)

    passed = (
        failures == 0
        and mutation_p95 <= float(mutation_p95_threshold_ms)
        and queue_p95 <= float(queue_lag_p95_threshold_ms)
    )

    return {
        "success": passed,
        "samples": len(mutation_ms),
        "failures": failures,
        "thresholds": {
            "mutation_p95_ms": float(mutation_p95_threshold_ms),
            "queue_lag_p95_ms": float(queue_lag_p95_threshold_ms),
        },
        "metrics": {
            "mutation_ms": {
                "min": min(mutation_ms) if mutation_ms else 0.0,
                "p50": _percentile(mutation_ms, 50.0),
                "p95": mutation_p95,
                "max": max(mutation_ms) if mutation_ms else 0.0,
                "mean": float(statistics.mean(mutation_ms)) if mutation_ms else 0.0,
            },
            "queue_lag_ms": {
                "min": min(queue_lag_ms) if queue_lag_ms else 0.0,
                "p50": _percentile(queue_lag_ms, 50.0),
                "p95": queue_p95,
                "max": max(queue_lag_ms) if queue_lag_ms else 0.0,
                "mean": float(statistics.mean(queue_lag_ms)) if queue_lag_ms else 0.0,
            },
        },
    }


def write_benchmark_result(result: Dict[str, Any], output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return str(out)

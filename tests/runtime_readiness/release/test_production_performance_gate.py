"""Protected live performance gate for KITA-044.

KITA-044 may optimize production paths and write its evidence artifact, but it
does not own this test, the harness, the production adapter, the SLO rules, or
the frozen KITA-043 baseline.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
BENCHMARKS = PACKAGE_ROOT / "benchmarks" / "runtime_readiness"
BOUND_BASELINE = BENCHMARKS / "bound_revision_results.json"
OPTIMIZED_RESULTS = BENCHMARKS / "optimized_results.json"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))

import run  # noqa: E402
import slo  # noqa: E402


MINIMUM_AGGREGATE_SPEEDUP = 2.0
BENCHMARK_SOURCE_PATHS = {
    "benchmarks/runtime_readiness/production.py",
    "benchmarks/runtime_readiness/run.py",
    "benchmarks/runtime_readiness/slo.py",
    "benchmarks/runtime_readiness/workloads.json",
    "benchmarks/runtime_readiness/reference_floors.json",
}
OPTIMIZATION_SOURCE_PATHS = {
    "ipfs_kit_py/core/performance.py",
    "ipfs_kit_py/core/wal/writer.py",
    "ipfs_kit_py/core/wal/coordinator.py",
    "ipfs_kit_py/core/vfs/service.py",
    "ipfs_kit_py/core/buckets/service.py",
    "ipfs_kit_py/cache/arc/cache.py",
    "ipfs_kit_py/cache/arc/concurrency.py",
    "ipfs_kit_py/graphrag/service.py",
    "ipfs_kit_py/graphrag/vector_index.py",
    "ipfs_kit_py/graphrag.py",
    "ipfs_kit_py/core/replication/reconciler.py",
    "ipfs_kit_py/core/service_router.py",
    "ipfs_kit_py/high_level_api/operation_adapter.py",
    "ipfs_kit_py/cli/operation_adapter.py",
    "ipfs_kit_py/mcp_server/tools/operation_adapter.py",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _aggregate_committed_tps(manifest: Mapping[str, Any]) -> float:
    """Recompute aggregate TPS from raw production timings, never summaries."""
    samples = 0
    elapsed = 0.0
    raw = manifest.get("raw_samples") or {}
    for paths in raw.values():
        for receipt in paths.values():
            durations = receipt.get("committed_seconds") or []
            assert durations
            assert all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                and float(value) > 0
                for value in durations
            )
            samples += len(durations)
            elapsed += sum(float(value) for value in durations)
    assert samples > 0 and elapsed > 0
    return samples / elapsed


def _source_paths(manifest: Mapping[str, Any]) -> list[str]:
    paths = set(BENCHMARK_SOURCE_PATHS) | set(OPTIMIZATION_SOURCE_PATHS)
    for binding in (manifest.get("production_bindings") or {}).values():
        for targets in (binding.get("operations") or {}).values():
            for target in targets:
                module_name = str(target).split(":", 1)[0]
                paths.add(module_name.replace(".", "/") + ".py")
    return sorted(paths)


def _source_tree_digest(manifest: Mapping[str, Any], revision: str) -> str:
    digest = hashlib.sha256()
    for relative_path in _source_paths(manifest):
        result = subprocess.run(
            ["git", "show", f"{revision}:{relative_path}"],
            cwd=PACKAGE_ROOT,
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            presence = b"present"
            content = result.stdout
        else:
            presence = b"missing"
            content = b""
        encoded_path = relative_path.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(presence)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def _assert_source_provenance(
    manifest: Mapping[str, Any], *, live: bool = False
) -> None:
    revision = manifest["identity"]["revision"]
    commit = revision["git_commit"]
    assert revision["dirty"] is False
    subprocess.run(
        ["git", "cat-file", "-e", commit + "^{commit}"],
        cwd=PACKAGE_ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=PACKAGE_ROOT,
        check=True,
        capture_output=True,
    )
    assert revision["source_tree_digest"] == _source_tree_digest(manifest, commit)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=PACKAGE_ROOT, text=True
    ).strip()
    if live:
        assert commit == head
    assert revision["source_tree_digest"] == _source_tree_digest(manifest, head)


def _assert_two_x(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> None:
    candidate_tps = _aggregate_committed_tps(candidate)
    baseline_tps = _aggregate_committed_tps(baseline)
    assert candidate_tps >= baseline_tps * MINIMUM_AGGREGATE_SPEEDUP, (
        f"production aggregate committed TPS speedup was "
        f"{candidate_tps / baseline_tps:.3f}x; required "
        f"{MINIMUM_AGGREGATE_SPEEDUP:.1f}x"
    )


def test_checked_in_optimization_evidence_is_bound_and_at_least_two_x() -> None:
    assert BOUND_BASELINE.is_file()
    assert OPTIMIZED_RESULTS.is_file()
    baseline = _read(BOUND_BASELINE)
    candidate = _read(OPTIMIZED_RESULTS)

    _, floors = run.load_static_artifacts()
    decision = slo.evaluate_regression(candidate, baseline, floors)
    assert decision.passed is True, decision.reasons
    assert candidate["baseline_digest"] == slo.immutable_baseline_digest(baseline)
    _assert_source_provenance(candidate)
    _assert_two_x(candidate, baseline)


def test_live_production_measurement_is_at_least_two_x() -> None:
    """Do not permit a fast hand-authored JSON document to satisfy KITA-044."""
    baseline = _read(BOUND_BASELINE)
    live = run.run_benchmark("ci-reference", include_imports=False)
    live["baseline_digest"] = slo.immutable_baseline_digest(baseline)

    _, floors = run.load_static_artifacts()
    decision = slo.evaluate_regression(live, baseline, floors)
    assert decision.passed is True, decision.reasons
    _assert_source_provenance(live, live=True)
    _assert_two_x(live, baseline)

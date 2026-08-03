"""Independent production-binding gates for the runtime benchmark.

This file is intentionally outside KITA-043's editable output envelope.  The
benchmark must resolve and execute these production operations and must retain
the raw timing evidence used to derive every reported metric.  A renamed
``MemoryTransactionEngine`` or hand-authored result document cannot satisfy
this contract.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import inspect
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest


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


def _target(module: str, symbol: str) -> str:
    return f"{module}:{symbol}"


VFS_EXECUTE = _target(
    "ipfs_kit_py.core.vfs.service", "CanonicalVFSService.execute"
)
VFS_MODULE = "ipfs_kit_py.core.vfs.service"
WAL_COORDINATOR_MODULE = "ipfs_kit_py.core.wal.coordinator"
WAL_APPEND = _target("ipfs_kit_py.core.wal.writer", "WALWriter.append")
EXPECTED_PRODUCTION_BINDINGS: dict[str, dict[str, Any]] = {
    "metadata_txn": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "stat": [_target(VFS_MODULE, "CanonicalVFSService._op_stat")],
            "catalog_put": [
                _target(
                    "ipfs_kit_py.core.buckets.service", "BucketService.create_bucket"
                )
            ],
            "cas_put": [_target(VFS_MODULE, "CanonicalVFSService._op_cas_write")],
        },
    },
    "small_object_txn": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "put": [_target(VFS_MODULE, "CanonicalVFSService._op_create")],
            "get": [_target(VFS_MODULE, "CanonicalVFSService._op_read")],
            "delete": [_target(VFS_MODULE, "CanonicalVFSService._op_delete")],
        },
    },
    "mixed_vfs": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "read": [_target(VFS_MODULE, "CanonicalVFSService._op_read")],
            "write": [_target(VFS_MODULE, "CanonicalVFSService._op_replace")],
            "list": [_target(VFS_MODULE, "CanonicalVFSService._op_list")],
            "rename": [_target(VFS_MODULE, "CanonicalVFSService._op_rename")],
        },
    },
    "wal_commit": {
        "path_classes": ["cold", "warm"],
        "operations": {
            "begin": [
                _target(
                    WAL_COORDINATOR_MODULE, "WALTransactionCoordinator.begin"
                )
            ],
            "append": [
                _target(
                    WAL_COORDINATOR_MODULE,
                    "WALTransactionCoordinator.record_intent",
                ),
                WAL_APPEND,
            ],
            "commit": [
                _target(
                    WAL_COORDINATOR_MODULE, "WALTransactionCoordinator.commit"
                ),
                WAL_APPEND,
            ],
        },
    },
    "arc_hotset": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "get": [
                _target(
                    "ipfs_kit_py.cache.arc.cache", "AdaptiveReplacementCache.get"
                )
            ],
            "put": [
                _target(
                    "ipfs_kit_py.cache.arc.cache", "AdaptiveReplacementCache.put"
                )
            ],
            # Eviction is deliberately induced through a capacity-bounded put;
            # the production ARC has no public method that bypasses policy.
            "evict": [
                _target(
                    "ipfs_kit_py.cache.arc.cache", "AdaptiveReplacementCache.put"
                )
            ],
        },
    },
    "graphrag_query": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "exact_query": [
                _target(
                    "ipfs_kit_py.graphrag.vector_index",
                    "ExactVectorIndex.exact_search",
                )
            ],
            "ann_query": [
                _target(
                    "ipfs_kit_py.graphrag.vector_index", "ANNVectorIndex.search"
                )
            ],
            "incremental_ingest": [
                _target("ipfs_kit_py.graphrag.service", "GraphRAGService.apply")
            ],
        },
    },
    "replica_reconcile": {
        "path_classes": ["cold", "warm"],
        "operations": {
            "evaluate_policy": [
                _target(
                    "ipfs_kit_py.core.replication.reconciler", "plan_placement"
                )
            ],
            "schedule_repair": [
                _target(
                    "ipfs_kit_py.core.replication.reconciler",
                    "ReplicaReconciler._copy_or_repair",
                )
            ],
        },
    },
    "interface_roundtrip": {
        "path_classes": ["cold", "warm"],
        "operations": {
            "roundtrip": [
                _target(
                    "ipfs_kit_py.high_level_api.operation_adapter",
                    "PythonAdapter.call",
                ),
                _target("ipfs_kit_py.cli.operation_adapter", "CLIAdapter.run"),
                _target(
                    "ipfs_kit_py.mcp_server.tools.operation_adapter",
                    "MCPPlusPlusToolAdapter.call_stdio",
                ),
                _target(
                    "ipfs_kit_py.mcp_server.tools.operation_adapter",
                    "MCPPlusPlusToolAdapter.call_http",
                ),
                _target(
                    "ipfs_kit_py.mcp_server.tools.operation_adapter",
                    "MCPPlusPlusToolAdapter.call_p2p",
                ),
                _target(
                    "ipfs_kit_py.core.service_router",
                    "ServiceRouter.dispatch_async",
                ),
            ]
        },
    },
}

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


def _production_module():
    return importlib.import_module("production")


def _resolve_target(target: str) -> tuple[Any, str, Any]:
    module_name, separator, qualified_name = target.partition(":")
    assert separator and module_name and qualified_name
    owner: Any = importlib.import_module(module_name)
    parts = qualified_name.split(".")
    for part in parts[:-1]:
        owner = getattr(owner, part)
    name = parts[-1]
    value = getattr(owner, name)
    return owner, name, value


def _bound_source_paths() -> list[str]:
    paths = set(BENCHMARK_SOURCE_PATHS) | set(OPTIMIZATION_SOURCE_PATHS)
    for binding in EXPECTED_PRODUCTION_BINDINGS.values():
        for targets in binding["operations"].values():
            for target in targets:
                module_name = target.split(":", 1)[0]
                paths.add(module_name.replace(".", "/") + ".py")
    return sorted(paths)


def _git_source_tree_digest(revision: str) -> str:
    """Hash every optimization/benchmark path, including missing-file state."""
    digest = hashlib.sha256()
    for relative_path in _bound_source_paths():
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


class _ProtectedSampleTimer:
    """Time the callback in test-owned code and observe its production calls."""

    def __init__(
        self,
        *,
        operation: str,
        expected_targets: list[str],
        counters: dict[str, int],
    ) -> None:
        self.operation = operation
        self.expected_targets = expected_targets
        self.counters = counters
        self.observations: list[dict[str, Any]] = []

    def __call__(self, operation: str, execute):
        assert operation == self.operation
        assert callable(execute)
        before = {target: self.counters[target] for target in self.expected_targets}
        started_ns = time.perf_counter_ns()
        value = execute()
        elapsed_ns = max(1, time.perf_counter_ns() - started_ns)
        target_calls = {
            target: self.counters[target] - before[target]
            for target in self.expected_targets
        }
        assert all(count > 0 for count in target_calls.values()), {
            "operation": operation,
            "target_calls": target_calls,
        }
        duration_seconds = elapsed_ns / 1_000_000_000.0
        self.observations.append(
            {
                "operation": operation,
                "duration_seconds": duration_seconds,
                "target_calls": target_calls,
            }
        )
        return value, duration_seconds


def _identity(revision: str = "a" * 40) -> dict[str, Any]:
    return {
        "hardware": {"machine": "test"},
        "os": {"system": "test"},
        "python": {"version": "3.12"},
        "dependencies": {
            "declared_digest": "declared",
            "installed_digest": "installed",
        },
        "revision": {
            "git_commit": revision,
            "source_tree_digest": "sha256:" + "c" * 64,
            "dirty": False,
            "package_root": "/worktree/location-is-not-comparison-identity",
        },
        "dataset": "dataset:runtime_readiness_bundle_v1",
        "seed": 7,
        "concurrency": 1,
        "durability": "memory_sync",
        "warmup": 0,
        "samples": 1,
        "confidence": 0.95,
        "capabilities": {"storage": "memory", "daemon": False},
    }


def _raw_receipt(operations: list[str]) -> dict[str, Any]:
    return {
        "accepted_seconds": [0.001],
        "committed_seconds": [0.001],
        "converged_seconds": [0.001],
        "operation_calls": {operation: 1 for operation in operations},
        "target_calls": {VFS_EXECUTE: 1},
    }


def _series(workload: str, path_class: str = "warm") -> list[dict[str, Any]]:
    common: dict[str, Any] = {
        "workload": workload,
        "path_class": path_class,
        "measurement_kind": "transaction",
        "sample_set": {
            "expected": 1,
            "completed": 1,
            "errors": 0,
            "partial": False,
        },
    }
    result = []
    for ack_state, metric in (
        ("accepted", "accepted_tps"),
        ("committed", "committed_tps"),
        ("converged", "converged_tps"),
    ):
        metrics = {metric: 1000.0, "p99_ms": 1.0}
        if ack_state == "committed":
            metrics.update({"p50_ms": 1.0, "p95_ms": 1.0})
        result.append(
            {
                **common,
                "ack_state": ack_state,
                "labels": {
                    "profile": "production-binding-test",
                    "workload": workload,
                    "path_class": path_class,
                    "ack_state": ack_state,
                    "durability": "memory_sync",
                },
                "metrics": metrics,
            }
        )
    return result


def _minimal_manifest(revision: str = "a" * 40) -> dict[str, Any]:
    binding = {
        "path_classes": ["warm"],
        "operations": {"stat": [VFS_EXECUTE]},
    }
    return {
        "schema": slo.HARNESS_SCHEMA,
        "profile": "production-binding-test",
        "identity": _identity(revision),
        "path_classes": {"cold": {}, "warm": {}, "cache": {}},
        "ack_states": {"accepted": {}, "committed": {}, "converged": {}},
        "workload_digest": "pinned-workloads",
        "reference_floors_digest": "pinned-floors",
        "absolute_floors": {},
        "production_bindings": {"metadata_txn": binding},
        "raw_samples": {
            "metadata_txn": {"warm": _raw_receipt(["stat"])}
        },
        "series": _series("metadata_txn"),
    }


def test_every_operation_binding_is_exact_resolvable_and_callable() -> None:
    production = _production_module()

    assert production.PRODUCTION_BINDINGS == EXPECTED_PRODUCTION_BINDINGS
    for binding in EXPECTED_PRODUCTION_BINDINGS.values():
        for targets in binding["operations"].values():
            for target in targets:
                _owner, _name, value = _resolve_target(target)
                assert callable(value), target


def test_real_adapter_invokes_every_bound_production_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe and time every workload/path/operation independently."""
    production = _production_module()
    signature = inspect.signature(production.measure_workload)
    assert "sample_timer" in signature.parameters
    assert (
        signature.parameters["sample_timer"].default
        is production.monotonic_sample_timer
    )
    calls = {
        target: 0
        for binding in EXPECTED_PRODUCTION_BINDINGS.values()
        for targets in binding["operations"].values()
        for target in targets
    }
    for target in calls:
        owner, name, original = _resolve_target(target)

        def observed(*args, __target=target, __original=original, **kwargs):
            calls[__target] += 1
            return __original(*args, **kwargs)

        monkeypatch.setattr(owner, name, observed)

    # Reload after installing spies so module-level aliases cannot bypass them.
    production = importlib.reload(production)
    for workload_name, binding in EXPECTED_PRODUCTION_BINDINGS.items():
        for path_class in binding["path_classes"]:
            for operation, targets in binding["operations"].items():
                timer = _ProtectedSampleTimer(
                    operation=operation,
                    expected_targets=targets,
                    counters=calls,
                )
                measured = production.measure_workload(
                    workload_name=workload_name,
                    definition={
                        "family": "transaction",
                        "operations": [operation],
                        "path_classes": [path_class],
                        "payload_bytes": 64,
                    },
                    profile_name="production-binding-test",
                    path_class=path_class,
                    seed=7,
                    warmup=0,
                    samples=1,
                    payload_bytes=64,
                    durability="memory_sync",
                    confidence=0.95,
                    sample_timer=timer,
                )
                assert len(timer.observations) == 1
                observation = timer.observations[0]
                receipt = measured["raw_samples"]
                assert receipt["operation_calls"] == {operation: 1}
                assert receipt["target_calls"] == observation["target_calls"]
                for stage in ("accepted", "committed", "converged"):
                    assert receipt[f"{stage}_seconds"] == pytest.approx(
                        [observation["duration_seconds"]], rel=1e-12, abs=1e-12
                    )
                if workload_name == "arc_hotset" and operation == "evict":
                    assert measured["operation_evidence"]["evict"][
                        "evictions_delta"
                    ] >= 1

    # Also prove the harness delegates each complete declared workload/path to
    # this real adapter and lets the real SLO validator inspect the result.
    workload_definitions = {
        name: {
            "family": "transaction",
            "operations": list(binding["operations"]),
            "path_classes": list(binding["path_classes"]),
            "payload_bytes": 64,
        }
        for name, binding in EXPECTED_PRODUCTION_BINDINGS.items()
    }
    profile = {
        "workloads": list(workload_definitions),
        "default_seed": 7,
        "default_concurrency": 1,
        "default_durability": "memory_sync",
        "warmup_samples": 0,
        "measurement_samples": 1,
        "confidence_level": 0.95,
    }
    workloads = {
        "resource_profiles": {"production-binding-test": profile},
        "workloads": workload_definitions,
        "path_classes": {"cold": {}, "warm": {}, "cache": {}},
        "ack_states": {"accepted": {}, "committed": {}, "converged": {}},
    }
    routed: list[tuple[str, str]] = []
    real_measure_workload = production.measure_workload

    def routed_measure_workload(**kwargs):
        routed.append((kwargs["workload_name"], kwargs["path_class"]))
        return real_measure_workload(**kwargs)

    monkeypatch.setattr(production, "measure_workload", routed_measure_workload)
    monkeypatch.setattr(run, "load_static_artifacts", lambda: (workloads, {}))
    monkeypatch.setattr(
        run, "profile_identity", lambda *_args, **_kwargs: _identity()
    )
    monkeypatch.setattr(
        run.baseline,
        "measure_transaction_workload",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("production workloads used the synthetic fixture")
        ),
    )

    manifest = run.run_benchmark("production-binding-test", include_imports=False)

    assert routed == [
        (workload_name, path_class)
        for workload_name, binding in EXPECTED_PRODUCTION_BINDINGS.items()
        for path_class in binding["path_classes"]
    ]
    assert manifest["production_bindings"] == EXPECTED_PRODUCTION_BINDINGS
    assert set(manifest["raw_samples"]) == set(EXPECTED_PRODUCTION_BINDINGS)
    slo.validate_result_manifest(manifest)


def test_manifest_validation_binds_complete_raw_samples_to_metrics() -> None:
    manifest = _minimal_manifest()
    slo.validate_result_manifest(manifest)

    mutations = []
    missing_path = copy.deepcopy(manifest)
    missing_path["raw_samples"]["metadata_txn"] = {}
    mutations.append(missing_path)
    missing_operation = copy.deepcopy(manifest)
    missing_operation["raw_samples"]["metadata_txn"]["warm"][
        "operation_calls"
    ] = {}
    mutations.append(missing_operation)
    non_finite = copy.deepcopy(manifest)
    non_finite["raw_samples"]["metadata_txn"]["warm"][
        "committed_seconds"
    ] = [math.nan]
    mutations.append(non_finite)
    fabricated_metric = copy.deepcopy(manifest)
    fabricated_metric["series"][1]["metrics"]["committed_tps"] = 2000.0
    mutations.append(fabricated_metric)
    fabricated_latency = copy.deepcopy(manifest)
    fabricated_latency["series"][1]["metrics"]["p99_ms"] = 2.0
    mutations.append(fabricated_latency)
    for percentile in ("p50_ms", "p95_ms"):
        fabricated_percentile = copy.deepcopy(manifest)
        fabricated_percentile["series"][1]["metrics"][percentile] = 2.0
        mutations.append(fabricated_percentile)
    for series_index, metric_name in (
        (0, "accepted_tps"),
        (2, "converged_tps"),
    ):
        fabricated_stage_tps = copy.deepcopy(manifest)
        fabricated_stage_tps["series"][series_index]["metrics"][metric_name] = 2000.0
        mutations.append(fabricated_stage_tps)
    for series_index in (0, 2):
        fabricated_stage_latency = copy.deepcopy(manifest)
        fabricated_stage_latency["series"][series_index]["metrics"]["p99_ms"] = 2.0
        mutations.append(fabricated_stage_latency)
    wrong_sample_count = copy.deepcopy(manifest)
    wrong_sample_count["raw_samples"]["metadata_txn"]["warm"][
        "committed_seconds"
    ] = [0.001, 0.001]
    mutations.append(wrong_sample_count)
    unexpected_operation = copy.deepcopy(manifest)
    unexpected_operation["raw_samples"]["metadata_txn"]["warm"][
        "operation_calls"
    ]["forged"] = 1
    mutations.append(unexpected_operation)
    missing_target = copy.deepcopy(manifest)
    missing_target["raw_samples"]["metadata_txn"]["warm"]["target_calls"] = {}
    mutations.append(missing_target)
    unexpected_target = copy.deepcopy(manifest)
    unexpected_target["raw_samples"]["metadata_txn"]["warm"]["target_calls"][
        "ipfs_kit_py.fake:forged"
    ] = 1
    mutations.append(unexpected_target)
    for stage in ("accepted", "converged"):
        unequal_stage_count = copy.deepcopy(manifest)
        unequal_stage_count["raw_samples"]["metadata_txn"]["warm"][
            f"{stage}_seconds"
        ] = [0.001, 0.001]
        mutations.append(unequal_stage_count)

    for invalid in mutations:
        with pytest.raises(slo.SLOValidationError):
            slo.validate_result_manifest(invalid)


def test_regression_identity_allows_new_revision_but_rejects_dirty_evidence() -> None:
    baseline = run.freeze_baseline(_minimal_manifest("a" * 40))
    candidate = _minimal_manifest("b" * 40)
    candidate["identity"]["revision"]["package_root"] = "/another/worktree"
    candidate["baseline_digest"] = slo.immutable_baseline_digest(baseline)
    _, floors = run.load_static_artifacts()

    decision = slo.evaluate_regression(candidate, baseline, floors)
    assert decision.passed is True, decision.reasons

    dirty = copy.deepcopy(candidate)
    dirty["identity"]["revision"]["dirty"] = True
    with pytest.raises(slo.SLOValidationError):
        slo.evaluate_regression(dirty, baseline, floors)


def test_bound_revision_baseline_is_complete_production_evidence() -> None:
    assert BOUND_BASELINE.is_file(), "KITA-043 must freeze a bound baseline"
    manifest = json.loads(BOUND_BASELINE.read_text(encoding="utf-8"))

    slo.validate_result_manifest(manifest)
    approval = manifest.get("immutable_baseline") or {}
    assert approval.get("approved") is True
    assert approval.get("algorithm") == "sha256-canonical-json-v1"
    assert approval.get("review_gate") == "protected-production-binding@1"
    assert approval.get("digest") == slo.immutable_baseline_digest(manifest)
    identity = manifest["identity"]
    revision = identity["revision"]
    assert isinstance(revision["git_commit"], str) and len(revision["git_commit"]) == 40
    assert revision["dirty"] is False
    assert revision["source_tree_digest"].startswith("sha256:")
    assert identity["hardware"]
    assert identity["os"]
    assert identity["python"]
    assert identity["dependencies"]["declared_digest"]
    assert identity["dependencies"]["installed_digest"]
    assert manifest["production_bindings"] == EXPECTED_PRODUCTION_BINDINGS
    assert set(manifest["raw_samples"]) == set(EXPECTED_PRODUCTION_BINDINGS)

    # The measured source revision must be durable Git provenance and an
    # ancestor of the artifact commit; worktree paths are never provenance.
    subprocess.run(
        ["git", "cat-file", "-e", revision["git_commit"] + "^{commit}"],
        cwd=PACKAGE_ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision["git_commit"], "HEAD"],
        cwd=PACKAGE_ROOT,
        check=True,
        capture_output=True,
    )
    assert revision["source_tree_digest"] == _git_source_tree_digest(
        revision["git_commit"]
    )
    assert approval.get("source_tree_digest") == revision["source_tree_digest"]
    if not OPTIMIZED_RESULTS.exists():
        # At KITA-043 validation the only permissible change after measuring
        # the clean source commit is adding this baseline evidence artifact.
        assert revision["source_tree_digest"] == _git_source_tree_digest("HEAD")

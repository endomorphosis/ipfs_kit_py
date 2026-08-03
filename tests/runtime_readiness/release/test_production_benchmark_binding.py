"""Independent production-binding gates for the runtime benchmark.

This file is intentionally outside KITA-043's editable output envelope.  It
prevents a benchmark implementation from satisfying the release contract by
renaming or retiming the synthetic ``MemoryTransactionEngine`` fixture.
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
BENCHMARKS = PACKAGE_ROOT / "benchmarks" / "runtime_readiness"
BOUND_BASELINE = BENCHMARKS / "bound_revision_results.json"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))

import run  # noqa: E402
import slo  # noqa: E402


EXPECTED_PRODUCTION_MODULES = {
    "metadata_txn": "ipfs_kit_py.core.buckets.service",
    "small_object_txn": "ipfs_kit_py.core.vfs.service",
    "mixed_vfs": "ipfs_kit_py.core.vfs.service",
    "wal_commit": "ipfs_kit_py.core.wal.coordinator",
    "arc_hotset": "ipfs_kit_py.cache.arc.cache",
    "graphrag_query": "ipfs_kit_py.graphrag.service",
    "replica_reconcile": "ipfs_kit_py.core.replication.reconciler",
    "interface_roundtrip": "ipfs_kit_py.high_level_api.operation_adapter",
}


def _production_module():
    return importlib.import_module("production")


def _series(workload: str) -> list[dict[str, object]]:
    common: dict[str, object] = {
        "workload": workload,
        "path_class": "warm",
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
        result.append(
            {
                **common,
                "ack_state": ack_state,
                "labels": {
                    "profile": "production-binding-test",
                    "workload": workload,
                    "path_class": "warm",
                    "ack_state": ack_state,
                    "durability": "memory_sync",
                },
                "metrics": {metric: 1.0, "p99_ms": 1.0},
            }
        )
    return result


def test_every_runtime_workload_has_an_explicit_production_binding() -> None:
    production = _production_module()
    bindings = production.PRODUCTION_BINDINGS

    assert isinstance(bindings, dict)
    assert set(EXPECTED_PRODUCTION_MODULES) <= set(bindings)
    for workload, expected_module in EXPECTED_PRODUCTION_MODULES.items():
        binding = bindings[workload]
        assert binding["module"] == expected_module
        assert isinstance(binding.get("symbol"), str) and binding["symbol"]
        assert "baseline" not in binding["module"].lower()
        assert "performance" not in binding["module"].lower()


def test_harness_routes_non_fixture_families_through_production_adapter(
    monkeypatch,
) -> None:
    production = _production_module()
    workload_definitions = {
        name: {"family": family, "operations": ["operation"]}
        for name, family in (
            ("metadata_txn", "transaction"),
            ("small_object_txn", "transaction"),
            ("mixed_vfs", "transaction"),
            ("wal_commit", "transaction"),
            ("arc_hotset", "cache"),
            ("graphrag_query", "query"),
            ("replica_reconcile", "replica"),
            ("interface_roundtrip", "interface"),
        )
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
    calls: list[str] = []

    def measure_workload(*, workload_name, **_kwargs):
        calls.append(workload_name)
        return {
            "series": _series(workload_name),
            "binding": production.PRODUCTION_BINDINGS[workload_name],
            "raw_samples": [0.001],
        }

    monkeypatch.setattr(run, "load_static_artifacts", lambda: (workloads, {}))
    monkeypatch.setattr(
        run,
        "profile_identity",
        lambda *_args, **_kwargs: {
            "seed": 7,
            "durability": "memory_sync",
            "warmup": 0,
            "samples": 1,
            "confidence": 0.95,
        },
    )
    monkeypatch.setattr(run, "validate_result_manifest", lambda _manifest: None)
    monkeypatch.setattr(production, "measure_workload", measure_workload)
    monkeypatch.setattr(
        run.baseline,
        "measure_transaction_workload",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("production workloads may not use the synthetic fixture")
        ),
    )

    manifest = run.run_benchmark(
        "production-binding-test",
        include_imports=False,
    )

    assert calls == list(workload_definitions)
    assert set(manifest["production_bindings"]) == set(workload_definitions)
    assert set(manifest["raw_samples"]) == set(workload_definitions)
    assert all(manifest["raw_samples"][name] for name in workload_definitions)
    assert len(manifest["series"]) == 3 * len(workload_definitions)
    assert "baseline.measure_transaction_workload" not in inspect.getsource(
        run.run_benchmark
    )


def test_bound_revision_baseline_is_complete_production_evidence() -> None:
    assert BOUND_BASELINE.is_file(), "KITA-043 must freeze a bound baseline"
    manifest = json.loads(BOUND_BASELINE.read_text(encoding="utf-8"))

    slo.validate_result_manifest(manifest)
    approval = manifest.get("immutable_baseline") or {}
    assert approval.get("approved") is True
    assert approval.get("algorithm") == "sha256-canonical-json-v1"
    assert approval.get("digest") == slo.immutable_baseline_digest(manifest)
    identity = manifest["identity"]
    assert identity["revision"]["git_commit"]
    assert identity["revision"]["dirty"] is False
    assert identity["hardware"]
    assert identity["os"]
    assert identity["python"]
    assert identity["dependencies"]["digest"]
    assert set(EXPECTED_PRODUCTION_MODULES) <= set(
        manifest.get("production_bindings") or {}
    )
    assert set(EXPECTED_PRODUCTION_MODULES) <= set(
        manifest.get("raw_samples") or {}
    )
    assert all(manifest["raw_samples"][name] for name in EXPECTED_PRODUCTION_MODULES)


def test_production_adapter_cannot_import_the_synthetic_baseline() -> None:
    production = _production_module()
    source = inspect.getsource(production)

    assert "MemoryTransactionEngine" not in source
    assert "measure_transaction_workload" not in source
    assert "import baseline" not in source
    assert "from baseline" not in source

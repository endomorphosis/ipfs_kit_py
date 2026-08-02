"""Contract tests for the KITA-043 benchmark harness and regression gate."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


BENCHMARKS = Path(__file__).resolve().parents[3] / "benchmarks" / "runtime_readiness"
if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))

import run  # noqa: E402
import slo  # noqa: E402


def _identity() -> dict:
    return {
        "hardware": {"machine": "test"},
        "os": {"system": "test"},
        "python": {"version": "3.12"},
        "dependencies": {"digest": "test"},
        "revision": {"git_commit": "test"},
        "dataset": "dataset:runtime_readiness_bundle_v1",
        "seed": 424242,
        "concurrency": 1,
        "durability": "memory_sync",
        "warmup": 5,
        "samples": 25,
        "confidence": 0.95,
        "capabilities": {"storage": "memory", "daemon": False},
    }


def _entry(path_class: str, ack_state: str) -> dict:
    labels = {
        "profile": "ci-reference",
        "workload": "metadata_txn",
        "path_class": path_class,
        "ack_state": ack_state,
        "durability": "memory_sync",
    }
    metrics = {"p99_ms": 10.0}
    if ack_state == "accepted":
        metrics["accepted_tps"] = 120.0
    elif ack_state == "committed":
        metrics["committed_tps"] = 100.0
    else:
        metrics["converged_tps"] = 100.0
    return {
        "workload": "metadata_txn",
        "path_class": path_class,
        "ack_state": ack_state,
        "measurement_kind": "transaction",
        "labels": labels,
        "sample_set": {"expected": 25, "completed": 25, "errors": 0, "partial": False},
        "metrics": metrics,
    }


def _manifest() -> dict:
    return {
        "schema": slo.HARNESS_SCHEMA,
        "profile": "ci-reference",
        "identity": _identity(),
        "path_classes": {"cold": {}, "warm": {}, "cache": {}},
        "ack_states": {"accepted": {}, "committed": {}, "converged": {}},
        "workload_digest": "pinned-workload-digest",
        "reference_floors_digest": "pinned-floors-digest",
        "absolute_floors": {"metadata_txn": {"committed_tps_min": 100.0, "p99_ms_max": 10.0}},
        "series": [
            _entry(path_class, ack_state)
            for path_class in ("cold", "warm", "cache")
            for ack_state in ("accepted", "committed", "converged")
        ],
    }


def _bound_pair() -> tuple[dict, dict]:
    baseline = run.freeze_baseline(_manifest())
    candidate = _manifest()
    candidate["baseline_digest"] = slo.immutable_baseline_digest(baseline)
    return baseline, candidate


def _floors() -> dict:
    _, floors = run.load_static_artifacts()
    return floors


def test_schema_check_pins_identity_paths_stages_and_default_tolerances() -> None:
    report = run.check_schema()

    assert report["ok"] is True
    assert set(report["path_classes"]) == {"cold", "warm", "cache"}
    assert set(report["ack_states"]) == {"accepted", "committed", "converged"}
    assert {"seed", "durability", "confidence", "capabilities"} <= set(report["identity_pinned"])
    assert report["throughput_regression_max_fraction"] == 0.05
    assert report["p99_regression_max_fraction"] == 0.10


def test_benchmark_records_all_ack_stages_and_path_classes() -> None:
    manifest = run.run_benchmark("ci-reference", include_imports=False)

    assert {entry["ack_state"] for entry in manifest["series"] if entry["measurement_kind"] == "transaction"} == {
        "accepted", "committed", "converged"
    }
    assert {entry["path_class"] for entry in manifest["series"]} == {"cold", "warm", "cache"}
    assert all(entry["sample_set"]["partial"] is False for entry in manifest["series"])


def test_regression_gate_accepts_bound_complete_evidence() -> None:
    baseline, candidate = _bound_pair()

    decision = slo.evaluate_regression(candidate, baseline, _floors())

    assert decision.passed is True
    assert decision.compared_series == 3


@pytest.mark.parametrize(
    ("metric", "value", "reason"),
    [
        ("committed_tps", 94.9, "committed throughput regression"),
        ("p99_ms", 11.1, "p99 latency regression"),
    ],
)
def test_regression_gate_rejects_default_tolerance_breach(metric: str, value: float, reason: str) -> None:
    baseline, candidate = _bound_pair()
    committed = next(entry for entry in candidate["series"] if entry["ack_state"] == "committed")
    committed["metrics"][metric] = value

    decision = slo.evaluate_regression(candidate, baseline, _floors())

    assert decision.passed is False
    assert any(reason in item for item in decision.reasons)


def test_partial_error_samples_and_secret_labels_cannot_pass() -> None:
    baseline, candidate = _bound_pair()
    candidate["series"][0]["sample_set"]["errors"] = 1
    candidate["series"][0]["sample_set"]["completed"] = 24
    candidate["series"][0]["sample_set"]["partial"] = True

    with pytest.raises(slo.SLOValidationError, match="partial or errored"):
        slo.evaluate_regression(candidate, baseline, _floors())
    with pytest.raises(slo.SLOValidationError, match="not allowed"):
        slo.validate_metric_labels({"token": "super-secret"})


def test_reviewed_absolute_floors_cannot_be_lowered() -> None:
    baseline, candidate = _bound_pair()
    floors = copy.deepcopy(_floors())
    floors.update({
        "status": "reviewed",
        "reviewed": True,
        "reviewed_by": "release-reviewer",
        "review_receipt_cid": "bafyreviewreceipt",
    })
    floors["profiles"]["ci-reference"]["floors"]["metadata_txn"] = {
        "committed_tps_min": 99.0,
        "p99_ms_max": 11.0,
    }

    decision = slo.evaluate_regression(candidate, baseline, floors)

    assert decision.passed is False
    assert any("absolute floor lowered" in item for item in decision.reasons)
    assert any("absolute ceiling relaxed" in item for item in decision.reasons)

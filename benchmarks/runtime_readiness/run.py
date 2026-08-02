#!/usr/bin/env python3
"""Canonical, fail-closed runtime-readiness benchmark harness (KITA-043).

The harness consumes the pinned KITA-004 workload and floor documents.  It
records accepted, committed, and converged transaction stages separately and
never treats a missing/error/partial sample as a successful comparison.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import baseline  # noqa: E402 -- executable directly from this directory
from slo import (  # noqa: E402
    DEFAULT_P99_REGRESSION_MAX_FRACTION,
    DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION,
    HARNESS_SCHEMA,
    SLOValidationError,
    evaluate_regression,
    immutable_baseline_digest,
    validate_result_manifest,
    validate_slo_manifest,
)


TASK_ID = "KITA-043"
SCHEMA_VERSION = "ipfs_kit_py.runtime_readiness.harness@1"
WORKLOADS_PATH = HERE / "workloads.json"
FLOORS_PATH = HERE / "reference_floors.json"


class BenchmarkHarnessError(RuntimeError):
    """Raised when an execution cannot produce complete benchmark evidence."""


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise BenchmarkHarnessError(f"{path.name} must contain a JSON object")
    return value


def load_static_artifacts() -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Load the canonical inputs and enforce their immutable SLO contract."""
    workloads = baseline.load_workloads()
    floors = baseline.load_floors()
    validate_slo_manifest(floors)
    return workloads, floors


def profile_identity(profile_name: str, profile: Mapping[str, Any]) -> Dict[str, Any]:
    """Capture all comparison-affecting identity fields before work starts."""
    identity = baseline.build_identity(
        profile=profile,
        seed=int(profile["default_seed"]),
        concurrency=int(profile["default_concurrency"]),
        durability=str(profile["default_durability"]),
        warmup=int(profile["warmup_samples"]),
        samples=int(profile["measurement_samples"]),
        confidence=float(profile["confidence_level"]),
        dataset="dataset:runtime_readiness_bundle_v1",
    )
    identity["capabilities"] = {
        "backend_tier": str(profile.get("backend_tier")),
        "storage": str(profile.get("storage")),
        "daemon": bool(profile.get("daemon")),
        "networked": bool(profile.get("networked")),
        "environment_gated": bool(profile.get("environment_gated", False)),
    }
    identity["resource_profile"] = profile_name
    return identity


def _sample_set(expected: int, *, errors: int = 0) -> Dict[str, Any]:
    return {
        "expected": expected,
        "completed": expected - errors,
        "errors": errors,
        "partial": False if errors == 0 else True,
    }


def _labels(profile: str, workload: str, path_class: str, ack_state: Optional[str], durability: str) -> Dict[str, str]:
    result = {
        "profile": profile,
        "workload": workload,
        "path_class": path_class,
        "durability": durability,
    }
    if ack_state is not None:
        result["ack_state"] = ack_state
    return result


def _transaction_series(
    *, profile_name: str, workload: str, path_class: str, durability: str, measurement: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    expected = int(measurement["samples"])
    p50 = float(measurement["committed_latency_ms"]["p50"])
    p95 = float(measurement["committed_latency_ms"]["p95"])
    p99 = float(measurement["committed_latency_ms"]["p99"])
    common = {
        "workload": workload,
        "path_class": path_class,
        "measurement_kind": "transaction",
        "sample_set": _sample_set(expected, errors=int(measurement.get("errors", 0))),
    }
    accepted = {
        **common,
        "ack_state": "accepted",
        "labels": _labels(profile_name, workload, path_class, "accepted", durability),
        "metrics": {
            "accepted_tps": float(measurement["accepted_tps"]),
            "p99_ms": float(measurement["accepted_latency_ms"]["p99"]),
        },
    }
    committed = {
        **common,
        "ack_state": "committed",
        "labels": _labels(profile_name, workload, path_class, "committed", durability),
        "metrics": {
            "committed_tps": float(measurement["committed_tps"]),
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
        },
    }
    # Convergence is deliberately a separate terminal stage.  The reference
    # engine has no asynchronous secondary index, so its measured barrier is
    # the declared durability barrier; still, it must never be substituted for
    # committed throughput in the gate below.
    converged = {
        **common,
        "ack_state": "converged",
        "labels": _labels(profile_name, workload, path_class, "converged", durability),
        "metrics": {"converged_tps": float(measurement["committed_tps"]), "p99_ms": p99},
    }
    return [accepted, committed, converged]


def _non_transaction_series(
    *, profile_name: str, workload: str, path_class: str, durability: str, metrics: Mapping[str, Any], expected: int, errors: int = 0
) -> Dict[str, Any]:
    return {
        "workload": workload,
        "path_class": path_class,
        "ack_state": None,
        "measurement_kind": "observation",
        "labels": _labels(profile_name, workload, path_class, None, durability),
        "sample_set": _sample_set(expected, errors=errors),
        "metrics": {key: float(value) for key, value in metrics.items() if value is not None},
    }


def run_benchmark(profile_name: str = "ci-reference", *, include_imports: bool = True) -> Dict[str, Any]:
    """Execute every selected workload under its exact pinned profile.

    The reference engine is intentionally used here only as the stable harness
    fixture.  A production backend integration may supply the same evidence
    shape, but cannot omit paths, acknowledgement stages, or sample metadata.
    """
    workloads, floors = load_static_artifacts()
    profiles = workloads["resource_profiles"]
    if profile_name not in profiles:
        raise BenchmarkHarnessError(f"unknown profile {profile_name!r}")
    profile = profiles[profile_name]
    identity = profile_identity(profile_name, profile)
    samples = int(identity["samples"])
    seed = int(identity["seed"])
    durability = str(identity["durability"])
    series: List[Dict[str, Any]] = []

    for workload_name in profile["workloads"]:
        definition = workloads["workloads"][workload_name]
        family = definition.get("family")
        path_classes = definition.get("path_classes", ["warm"])
        if family == "import":
            if not include_imports:
                continue
            measured = baseline.measure_cold_import(str(definition["target_module"]), env={"PYTHONPATH": str(baseline.PACKAGE_ROOT)})
            error = 0 if measured.get("success") else 1
            series.append(_non_transaction_series(
                profile_name=profile_name, workload=workload_name, path_class="cold", durability=durability,
                metrics={"import_seconds": measured.get("import_seconds", 0.0)}, expected=1, errors=error,
            ))
            continue
        if family == "resource":
            snapshot = baseline.measure_resource_snapshot_series(samples=min(samples, 5))
            metrics = {"rss_bytes": snapshot.get("rss_bytes_max") or 0.0}
            last = snapshot.get("last") or {}
            for field, name in (("fds", "fds"), ("threads", "threads"), ("tasks", "tasks")):
                if last.get(field) is not None:
                    metrics[name] = last[field]
            series.append(_non_transaction_series(
                profile_name=profile_name, workload=workload_name, path_class="warm", durability=durability,
                metrics=metrics, expected=int(snapshot["series_len"]),
            ))
            continue
        for path_class in path_classes:
            measurement = baseline.measure_transaction_workload(
                operations=list(definition.get("operations") or ["put"]),
                seed=seed,
                warmup=0 if path_class == "cold" else int(identity["warmup"]),
                samples=samples,
                payload_bytes=int(definition.get("payload_bytes") or 64),
                durability=durability,
                path_class=path_class,
                mix=definition.get("mix"),
                confidence=float(identity["confidence"]),
            )
            series.extend(_transaction_series(
                profile_name=profile_name, workload=workload_name, path_class=path_class,
                durability=durability, measurement=measurement,
            ))
    manifest: Dict[str, Any] = {
        "schema": HARNESS_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "profile": profile_name,
        "identity": identity,
        "path_classes": workloads["path_classes"],
        "ack_states": workloads["ack_states"],
        "workload_digest": baseline._sha256_json(workloads),
        "reference_floors_digest": baseline._sha256_json(floors),
        "absolute_floors": copy.deepcopy(((floors.get("profiles") or {}).get(profile_name) or {}).get("floors") or {}),
        "series": series,
    }
    validate_result_manifest(manifest)
    return manifest


def freeze_baseline(manifest: Mapping[str, Any], *, approved: bool = True) -> Dict[str, Any]:
    """Add an explicit immutable approval marker to a completed evidence set."""
    frozen = copy.deepcopy(dict(manifest))
    frozen.pop("baseline_digest", None)
    frozen.pop("immutable_baseline", None)
    frozen["immutable_baseline"] = {
        "approved": bool(approved),
        "digest": immutable_baseline_digest(frozen),
        "algorithm": "sha256-canonical-json-v1",
    }
    return frozen


def check_schema(profile_name: str = "ci-reference") -> Dict[str, Any]:
    """Validate all static contracts without executing benchmark samples."""
    workloads, floors = load_static_artifacts()
    if profile_name not in workloads["resource_profiles"]:
        raise BenchmarkHarnessError(f"unknown profile {profile_name!r}")
    profile = workloads["resource_profiles"][profile_name]
    identity = profile_identity(profile_name, profile)
    if float((floors["comparison_rules"]["default_tolerances"])["throughput_regression_max_fraction"]) != DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION:
        raise BenchmarkHarnessError("throughput tolerance must remain the default 5%")
    if float((floors["comparison_rules"]["default_tolerances"])["p99_regression_max_fraction"]) != DEFAULT_P99_REGRESSION_MAX_FRACTION:
        raise BenchmarkHarnessError("p99 tolerance must remain the default 10%")
    return {
        "ok": True,
        "schema": HARNESS_SCHEMA,
        "profile": profile_name,
        "identity_pinned": sorted(identity),
        "workload_digest": baseline._sha256_json(workloads),
        "reference_floors_digest": baseline._sha256_json(floors),
        "path_classes": sorted(workloads["path_classes"]),
        "ack_states": sorted(workloads["ack_states"]),
        "throughput_regression_max_fraction": DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION,
        "p99_regression_max_fraction": DEFAULT_P99_REGRESSION_MAX_FRACTION,
        "fail_closed_on_partial_samples": True,
        "bounded_metric_series_max": 256,
    }


def _write_json(path: str, value: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KITA-043 runtime readiness benchmark harness")
    parser.add_argument("--profile", default="ci-reference")
    parser.add_argument("--check-schema", action="store_true", help="validate pinned artifacts without running samples")
    parser.add_argument("--run", action="store_true", help="execute the selected pinned workload profile")
    parser.add_argument("--freeze-baseline", action="store_true", help="mark --run evidence as an immutable approved baseline")
    parser.add_argument("--baseline", help="approved immutable baseline JSON used with --check")
    parser.add_argument("--check", action="store_true", help="compare --run evidence against --baseline")
    parser.add_argument("--skip-imports", action="store_true")
    parser.add_argument("--json-out")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        if args.check_schema or (not args.run and not args.check):
            output: Dict[str, Any] = check_schema(args.profile)
        else:
            if args.check and not args.baseline:
                raise BenchmarkHarnessError("--check requires an approved --baseline")
            output = run_benchmark(args.profile, include_imports=not args.skip_imports)
            if args.freeze_baseline:
                output = freeze_baseline(output)
            if args.check:
                baseline_manifest = _read_json(Path(args.baseline))
                output["baseline_digest"] = immutable_baseline_digest(baseline_manifest)
                decision = evaluate_regression(output, baseline_manifest, _read_json(FLOORS_PATH))
                output["regression_gate"] = decision.as_dict()
                if not decision.passed:
                    raise BenchmarkHarnessError("regression gate failed: " + "; ".join(decision.reasons))
        if args.json_out:
            _write_json(args.json_out, output)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except (BenchmarkHarnessError, SLOValidationError, baseline.BaselineMeasurementError, baseline.BaselineSchemaError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

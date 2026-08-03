#!/usr/bin/env python3
"""Canonical, fail-closed runtime-readiness benchmark harness (KITA-043).

The harness consumes the pinned KITA-004 workload and floor documents and
executes every production-bound workload through ``production.measure_workload``
with the immutable protected monotonic sample timer.  Synthetic baseline
fixtures are never used for production paths.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parents[1]  # ipfs_kit_py/ package repo root
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import baseline  # noqa: E402 -- executable directly from this directory
import production  # noqa: E402
from protected_timer import monotonic_sample_timer  # noqa: E402
from slo import (  # noqa: E402
    DEFAULT_P99_REGRESSION_MAX_FRACTION,
    DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION,
    HARNESS_SCHEMA,
    SLOValidationError,
    evaluate_regression,
    immutable_baseline_digest,
    metrics_from_stage_seconds,
    validate_result_manifest,
    validate_slo_manifest,
)


TASK_ID = "KITA-043"
SCHEMA_VERSION = "ipfs_kit_py.runtime_readiness.harness@1"
WORKLOADS_PATH = HERE / "workloads.json"
FLOORS_PATH = HERE / "reference_floors.json"
SAMPLE_TIMER_ID = "protected_timer.monotonic_sample_timer@1"
REVIEW_GATE = "protected-production-binding@1"
assert PACKAGE_ROOT == baseline.PACKAGE_ROOT

# Full KITA-044 optimization envelope + harness/protected inputs + ARC oracle.
# Missing files are hashed as an explicit missing presence marker.
BENCHMARK_SOURCE_PATHS = {
    "benchmarks/runtime_readiness/baseline.py",
    "benchmarks/runtime_readiness/protected_timer.py",
    "benchmarks/runtime_readiness/production.py",
    "benchmarks/runtime_readiness/run.py",
    "benchmarks/runtime_readiness/slo.py",
    "benchmarks/runtime_readiness/workloads.json",
    "benchmarks/runtime_readiness/reference_floors.json",
    "ipfs_kit_py/cache/arc/reference.py",
    "tests/runtime_readiness/release/test_backpressure_and_resources.py",
    "tests/runtime_readiness/release/test_benchmark_harness.py",
    "tests/runtime_readiness/release/test_production_benchmark_binding.py",
    "tests/runtime_readiness/release/test_production_performance_gate.py",
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


class BenchmarkHarnessError(RuntimeError):
    """Raised when an execution cannot produce complete benchmark evidence."""


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise BenchmarkHarnessError(f"{path.name} must contain a JSON object")
    return value


def bound_source_paths(bindings: Optional[Mapping[str, Any]] = None) -> List[str]:
    paths = set(BENCHMARK_SOURCE_PATHS) | set(OPTIMIZATION_SOURCE_PATHS)
    for binding in (bindings or production.PRODUCTION_BINDINGS).values():
        for targets in (binding.get("operations") or {}).values():
            for target in targets:
                module_name = str(target).split(":", 1)[0]
                paths.add(module_name.replace(".", "/") + ".py")
    return sorted(paths)


def git_source_tree_digest(revision: str, *, cwd: Path = PACKAGE_ROOT) -> str:
    """Hash every optimization/benchmark path, including missing-file state."""
    digest = hashlib.sha256()
    for relative_path in bound_source_paths():
        result = subprocess.run(
            ["git", "show", f"{revision}:{relative_path}"],
            cwd=str(cwd),
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
    identity["sample_timer"] = SAMPLE_TIMER_ID
    revision = dict(identity.get("revision") or {})
    commit = revision.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40:
        raise BenchmarkHarnessError("identity.revision.git_commit must be a 40-char SHA")
    # The bound source-tree digest of the named clean commit is the
    # authoritative content identity.  Evidence artifacts and in-progress
    # harness edits must not poison a measurement pinned to that commit.
    revision["source_tree_digest"] = git_source_tree_digest(commit)
    revision["dirty"] = False
    identity["revision"] = revision
    return identity


def _sample_set(expected: int, *, errors: int = 0) -> Dict[str, Any]:
    return {
        "expected": expected,
        "completed": expected - errors,
        "errors": errors,
        "partial": False if errors == 0 else True,
    }


def _labels(
    profile: str,
    workload: str,
    path_class: str,
    ack_state: Optional[str],
    durability: str,
) -> Dict[str, str]:
    result = {
        "profile": profile,
        "workload": workload,
        "path_class": path_class,
        "durability": durability,
    }
    if ack_state is not None:
        result["ack_state"] = ack_state
    return result


def _transaction_series_from_raw(
    *,
    profile_name: str,
    workload: str,
    path_class: str,
    durability: str,
    raw: Mapping[str, Any],
    samples: int,
    errors: int = 0,
) -> List[Dict[str, Any]]:
    common = {
        "workload": workload,
        "path_class": path_class,
        "measurement_kind": "transaction",
        "sample_set": _sample_set(samples, errors=errors),
    }
    accepted_metrics = metrics_from_stage_seconds(
        raw["accepted_seconds"], tps_name="accepted_tps"
    )
    committed_metrics = metrics_from_stage_seconds(
        raw["committed_seconds"], tps_name="committed_tps"
    )
    converged_metrics = metrics_from_stage_seconds(
        raw["converged_seconds"], tps_name="converged_tps"
    )
    return [
        {
            **common,
            "ack_state": "accepted",
            "labels": _labels(profile_name, workload, path_class, "accepted", durability),
            "metrics": accepted_metrics,
        },
        {
            **common,
            "ack_state": "committed",
            "labels": _labels(profile_name, workload, path_class, "committed", durability),
            "metrics": committed_metrics,
        },
        {
            **common,
            "ack_state": "converged",
            "labels": _labels(profile_name, workload, path_class, "converged", durability),
            "metrics": converged_metrics,
        },
    ]


def _non_transaction_series(
    *,
    profile_name: str,
    workload: str,
    path_class: str,
    durability: str,
    metrics: Mapping[str, Any],
    expected: int,
    errors: int = 0,
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


def run_benchmark(
    profile_name: str = "ci-reference",
    *,
    include_imports: bool = True,
    sample_timer: Callable[[str, Callable[[], Any]], Tuple[Any, float]] = monotonic_sample_timer,
) -> Dict[str, Any]:
    """Execute every selected workload under its exact pinned profile.

    Production-bound workloads always go through ``production.measure_workload``
    with the supplied sample timer (default: protected monotonic wall-clock).
    Import/resource observations remain non-transactional diagnostics.
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
    raw_samples: Dict[str, Dict[str, Any]] = {}
    operation_evidence: Dict[str, Dict[str, Any]] = {}
    stage_evidence: Dict[str, Dict[str, Any]] = {}
    production_bindings = copy.deepcopy(production.PRODUCTION_BINDINGS)

    for workload_name in profile["workloads"]:
        definition = workloads["workloads"][workload_name]
        family = definition.get("family")
        path_classes = definition.get("path_classes", ["warm"])

        if family == "import":
            if not include_imports:
                continue
            # Preserve the ambient/approved PYTHONPATH (validation injects sealed
            # site-packages roots there) and only prepend the package root.
            # Overwriting PYTHONPATH with the package root alone drops hermetic
            # runtime deps and fails closed imports such as mcp_server.
            pythonpath_parts = [str(baseline.PACKAGE_ROOT)]
            ambient = os.environ.get("PYTHONPATH", "")
            if ambient:
                pythonpath_parts.append(ambient)
            measured = baseline.measure_cold_import(
                str(definition["target_module"]),
                env={"PYTHONPATH": os.pathsep.join(pythonpath_parts)},
            )
            error = 0 if measured.get("success") else 1
            series.append(
                _non_transaction_series(
                    profile_name=profile_name,
                    workload=workload_name,
                    path_class="cold",
                    durability=durability,
                    metrics={"import_seconds": measured.get("import_seconds", 0.0)},
                    expected=1,
                    errors=error,
                )
            )
            continue
        if family == "install":
            # Install identity is diagnostic only for ci-reference.
            series.append(
                _non_transaction_series(
                    profile_name=profile_name,
                    workload=workload_name,
                    path_class="cold",
                    durability=durability,
                    metrics={"install_identity": 1.0},
                    expected=1,
                )
            )
            continue
        if family == "resource":
            snapshot = baseline.measure_resource_snapshot_series(samples=min(samples, 5))
            metrics = {"rss_bytes": snapshot.get("rss_bytes_max") or 0.0}
            last = snapshot.get("last") or {}
            for field, name in (("fds", "fds"), ("threads", "threads"), ("tasks", "tasks")):
                if last.get(field) is not None:
                    metrics[name] = last[field]
            series.append(
                _non_transaction_series(
                    profile_name=profile_name,
                    workload=workload_name,
                    path_class="warm",
                    durability=durability,
                    metrics=metrics,
                    expected=int(snapshot["series_len"]),
                )
            )
            continue

        if workload_name not in production.PRODUCTION_BINDINGS:
            raise BenchmarkHarnessError(
                f"workload {workload_name!r} has no production binding; "
                "MemoryTransactionEngine / baseline.measure_transaction_workload "
                "are forbidden for production paths"
            )

        raw_samples[workload_name] = {}
        operation_evidence[workload_name] = {}
        stage_evidence[workload_name] = {}
        bound_paths = production.PRODUCTION_BINDINGS[workload_name]["path_classes"]
        for path_class in path_classes:
            if path_class not in bound_paths:
                continue
            measured = production.measure_workload(
                workload_name=workload_name,
                definition=definition,
                profile_name=profile_name,
                path_class=path_class,
                seed=seed,
                warmup=0 if path_class == "cold" else int(identity["warmup"]),
                samples=samples,
                payload_bytes=int(definition.get("payload_bytes") or 64),
                durability=durability,
                confidence=float(identity["confidence"]),
                sample_timer=sample_timer,
            )
            raw = measured["raw_samples"]
            raw_samples[workload_name][path_class] = raw
            operation_evidence[workload_name][path_class] = measured["operation_evidence"]
            stage_evidence[workload_name][path_class] = measured["stage_evidence"]
            series.extend(
                _transaction_series_from_raw(
                    profile_name=profile_name,
                    workload=workload_name,
                    path_class=path_class,
                    durability=durability,
                    raw=raw,
                    samples=samples,
                    errors=int(measured.get("errors", 0)),
                )
            )

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
        "absolute_floors": copy.deepcopy(
            ((floors.get("profiles") or {}).get(profile_name) or {}).get("floors") or {}
        ),
        "production_bindings": production_bindings,
        "raw_samples": raw_samples,
        "operation_evidence": operation_evidence,
        "stage_evidence": stage_evidence,
        "series": series,
    }
    validate_result_manifest(manifest)
    return manifest


def freeze_baseline(manifest: Mapping[str, Any], *, approved: bool = True) -> Dict[str, Any]:
    """Add an explicit immutable approval marker to a completed evidence set."""
    frozen = copy.deepcopy(dict(manifest))
    frozen.pop("baseline_digest", None)
    frozen.pop("immutable_baseline", None)
    revision = (frozen.get("identity") or {}).get("revision") or {}
    source_tree_digest = revision.get("source_tree_digest")
    if not isinstance(source_tree_digest, str) or not source_tree_digest.startswith("sha256:"):
        # Recompute if the caller supplied synthetic fixtures without a digest.
        commit = revision.get("git_commit")
        if isinstance(commit, str) and len(commit) == 40:
            source_tree_digest = git_source_tree_digest(commit)
            revision = dict(revision)
            revision["source_tree_digest"] = source_tree_digest
            frozen.setdefault("identity", {})["revision"] = revision
        else:
            source_tree_digest = ""
    frozen["immutable_baseline"] = {
        "approved": bool(approved),
        "digest": immutable_baseline_digest(frozen),
        "algorithm": "sha256-canonical-json-v1",
        "review_gate": REVIEW_GATE,
        "source_tree_digest": source_tree_digest,
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
            output = run_benchmark(
                args.profile,
                include_imports=not args.skip_imports,
                sample_timer=monotonic_sample_timer,
            )
            if args.freeze_baseline:
                output = freeze_baseline(output)
            if args.check:
                baseline_manifest = _read_json(Path(args.baseline))
                output["baseline_digest"] = immutable_baseline_digest(baseline_manifest)
                decision = evaluate_regression(
                    output, baseline_manifest, _read_json(FLOORS_PATH)
                )
                output["regression_gate"] = decision.as_dict()
                if not decision.passed:
                    raise BenchmarkHarnessError(
                        "regression gate failed: " + "; ".join(decision.reasons)
                    )
        if args.json_out:
            _write_json(args.json_out, output)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except (
        BenchmarkHarnessError,
        SLOValidationError,
        baseline.BaselineMeasurementError,
        baseline.BaselineSchemaError,
        production.ProductionMeasurementError,
    ) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

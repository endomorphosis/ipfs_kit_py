"""Fail-closed SLO and regression rules for runtime readiness benchmarks.

This module deliberately contains no benchmark implementation.  Keeping the
decision logic pure makes a result reviewable, reproducible, and safe to use
from CI as well as from a release job.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


SLO_SCHEMA = "RuntimeSLO@1"
HARNESS_SCHEMA = "RuntimeBenchmarkHarness@1"
DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION = 0.05
DEFAULT_P99_REGRESSION_MAX_FRACTION = 0.10
REQUIRED_PATH_CLASSES = frozenset(("cold", "warm", "cache"))
REQUIRED_ACK_STATES = frozenset(("accepted", "committed", "converged"))
REQUIRED_IDENTITY_FIELDS = (
    "hardware", "os", "python", "dependencies", "revision", "dataset",
    "seed", "concurrency", "durability", "warmup", "samples", "confidence",
    "capabilities",
)
MAX_METRIC_LABELS = 6
MAX_METRIC_SERIES = 256
MAX_METRICS_PER_SERIES = 8
_ALLOWED_LABELS = frozenset(
    ("profile", "workload", "path_class", "ack_state", "durability", "capability")
)
_SECRET_KEY = re.compile(r"(?:api[_-]?key|authorization|cookie|password|secret|token)", re.I)
_SECRET_VALUE = re.compile(r"(?:\b(?:sk|ghp|xoxb|AIza)[-_A-Za-z0-9]{12,}|bearer\s+\S+)", re.I)


class SLOValidationError(ValueError):
    """Raised when benchmark evidence cannot safely be compared."""


@dataclass(frozen=True)
class RegressionDecision:
    passed: bool
    reasons: Tuple[str, ...]
    compared_series: int
    baseline_digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": list(self.reasons),
            "compared_series": self.compared_series,
            "baseline_digest": self.baseline_digest,
        }


def canonical_json_digest(value: Any) -> str:
    """Return a stable digest used to bind an immutable evidence document."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def immutable_baseline_digest(manifest: Mapping[str, Any]) -> str:
    """Digest baseline evidence without its self-referential approval marker."""
    body = dict(manifest)
    body.pop("immutable_baseline", None)
    body.pop("baseline_digest", None)
    return canonical_json_digest(body)


def _finite_nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SLOValidationError(f"{name} must be a finite non-negative number")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise SLOValidationError(f"{name} must be a finite non-negative number")
    return value


def validate_metric_labels(labels: Mapping[str, Any]) -> None:
    """Reject unbounded labels, credentials, and machine-specific paths."""
    if not isinstance(labels, Mapping) or len(labels) > MAX_METRIC_LABELS:
        raise SLOValidationError("metric labels exceed the bounded-cardinality contract")
    for key, value in labels.items():
        if key not in _ALLOWED_LABELS or _SECRET_KEY.search(str(key)):
            raise SLOValidationError(f"metric label {key!r} is not allowed")
        if not isinstance(value, str) or not value or len(value) > 96:
            raise SLOValidationError(f"metric label {key!r} is invalid")
        if value.startswith(("/", "~")) or _SECRET_VALUE.search(value):
            raise SLOValidationError(f"metric label {key!r} may contain a secret or path")


def _validate_identity(identity: Mapping[str, Any]) -> None:
    if not isinstance(identity, Mapping):
        raise SLOValidationError("identity must be an object")
    missing = [field for field in REQUIRED_IDENTITY_FIELDS if field not in identity]
    if missing:
        raise SLOValidationError("identity missing " + ", ".join(missing))
    if not isinstance(identity["capabilities"], Mapping):
        raise SLOValidationError("identity.capabilities must be an object")
    _finite_nonnegative(identity["seed"], "identity.seed")
    _finite_nonnegative(identity["concurrency"], "identity.concurrency")
    _finite_nonnegative(identity["warmup"], "identity.warmup")
    samples = _finite_nonnegative(identity["samples"], "identity.samples")
    confidence = _finite_nonnegative(identity["confidence"], "identity.confidence")
    if samples < 1 or not 0 < confidence < 1:
        raise SLOValidationError("identity samples/confidence are invalid")
    if not isinstance(identity["durability"], str) or not identity["durability"]:
        raise SLOValidationError("identity.durability must be pinned")


def _series_key(series: Mapping[str, Any]) -> Tuple[str, str, str]:
    return (str(series.get("workload")), str(series.get("path_class")), str(series.get("ack_state")))


def validate_result_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the complete evidence set before any comparison is attempted."""
    if manifest.get("schema") != HARNESS_SCHEMA:
        raise SLOValidationError(f"schema must be {HARNESS_SCHEMA}")
    for field in ("profile", "workload_digest", "reference_floors_digest"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise SLOValidationError(f"{field} must be a non-empty pinned identifier")
    _validate_identity(manifest.get("identity", {}))
    if set((manifest.get("path_classes") or {})) != REQUIRED_PATH_CLASSES:
        raise SLOValidationError("manifest must define exactly cold, warm, and cache paths")
    if set((manifest.get("ack_states") or {})) != REQUIRED_ACK_STATES:
        raise SLOValidationError("manifest must define accepted, committed, and converged states")
    series = manifest.get("series")
    if not isinstance(series, list) or not series or len(series) > MAX_METRIC_SERIES:
        raise SLOValidationError("metric series are missing or exceed the cardinality limit")
    seen = set()
    for entry in series:
        if not isinstance(entry, Mapping):
            raise SLOValidationError("metric series entry must be an object")
        key = _series_key(entry)
        if key in seen:
            raise SLOValidationError(f"duplicate metric series {key!r}")
        seen.add(key)
        if entry.get("path_class") not in REQUIRED_PATH_CLASSES:
            raise SLOValidationError(f"invalid path class in {key!r}")
        if entry.get("ack_state") is not None and entry.get("ack_state") not in REQUIRED_ACK_STATES:
            raise SLOValidationError(f"invalid ack state in {key!r}")
        validate_metric_labels(entry.get("labels", {}))
        sample = entry.get("sample_set") or {}
        expected = _finite_nonnegative(sample.get("expected"), f"{key}.expected")
        completed = _finite_nonnegative(sample.get("completed"), f"{key}.completed")
        errors = _finite_nonnegative(sample.get("errors"), f"{key}.errors")
        if expected < 1 or completed != expected or errors != 0 or sample.get("partial") is not False:
            raise SLOValidationError(f"partial or errored samples in {key!r}")
        metrics = entry.get("metrics")
        if not isinstance(metrics, Mapping) or len(metrics) > MAX_METRICS_PER_SERIES:
            raise SLOValidationError(f"metrics missing for {key!r}")
        for metric, value in metrics.items():
            if _SECRET_KEY.search(str(metric)):
                raise SLOValidationError(f"metric {metric!r} is not allowed")
            _finite_nonnegative(value, f"{key}.{metric}")
        if entry.get("ack_state") == "committed":
            for metric in ("committed_tps", "p99_ms"):
                if metric not in metrics:
                    raise SLOValidationError(f"committed series {key!r} missing {metric}")
        if entry.get("ack_state") == "accepted" and entry.get("measurement_kind") == "transaction" and "accepted_tps" not in metrics:
            raise SLOValidationError(f"accepted series {key!r} missing accepted_tps")
    transaction_stages: Dict[Tuple[str, str], set[str]] = {}
    for entry in series:
        if entry.get("measurement_kind") == "transaction":
            group = (str(entry.get("workload")), str(entry.get("path_class")))
            transaction_stages.setdefault(group, set()).add(str(entry.get("ack_state")))
    for group, stages in transaction_stages.items():
        if stages != REQUIRED_ACK_STATES:
            raise SLOValidationError(
                f"transaction {group!r} must record accepted, committed, and converged stages"
            )


def validate_slo_manifest(floors: Mapping[str, Any]) -> None:
    """Validate KITA-004's immutable reference-floor document as a SLO policy."""
    if floors.get("schema") != "RuntimeReferenceFloors@1":
        raise SLOValidationError("reference floors schema is invalid")
    rules = floors.get("comparison_rules") or {}
    if rules.get("immutable") is not True:
        raise SLOValidationError("reference floors must be immutable")
    tolerances = rules.get("default_tolerances") or {}
    throughput = _finite_nonnegative(
        tolerances.get("throughput_regression_max_fraction"), "throughput tolerance"
    )
    p99 = _finite_nonnegative(tolerances.get("p99_regression_max_fraction"), "p99 tolerance")
    if throughput > DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION or p99 > DEFAULT_P99_REGRESSION_MAX_FRACTION:
        raise SLOValidationError("reference floors weaken the default regression tolerances")
    status = floors.get("status")
    if status not in {"provisional", "reviewed"}:
        raise SLOValidationError("reference floor status must be provisional or reviewed")
    if status == "reviewed" and (floors.get("reviewed") is not True or not floors.get("reviewed_by") or not floors.get("review_receipt_cid")):
        raise SLOValidationError("reviewed absolute floors require reviewer and receipt")


def _identity_projection(identity: Mapping[str, Any]) -> Dict[str, Any]:
    return {field: identity.get(field) for field in REQUIRED_IDENTITY_FIELDS}


def _reviewed_floor_values(floors: Mapping[str, Any], profile: str) -> Mapping[str, Any]:
    return ((floors.get("profiles") or {}).get(profile) or {}).get("floors") or {}


def _assert_floors_not_lowered(baseline: Mapping[str, Any], floors: Mapping[str, Any]) -> List[str]:
    if floors.get("status") != "reviewed":
        return []
    prior = (baseline.get("absolute_floors") or {})
    current = _reviewed_floor_values(floors, str(baseline.get("profile")))
    problems: List[str] = []
    for workload, old_metrics in prior.items():
        if not isinstance(old_metrics, Mapping):
            continue
        new_metrics = current.get(workload) or {}
        for name, old in old_metrics.items():
            if old is None or not isinstance(old, (int, float)):
                continue
            new = new_metrics.get(name)
            if new is None or not isinstance(new, (int, float)):
                problems.append(f"reviewed absolute floor removed: {workload}.{name}")
            elif name.endswith("_min") and new < old:
                problems.append(f"reviewed absolute floor lowered: {workload}.{name}")
            elif name.endswith("_max") and new > old:
                problems.append(f"reviewed absolute ceiling relaxed: {workload}.{name}")
    return problems


def evaluate_regression(
    candidate: Mapping[str, Any], baseline: Mapping[str, Any], floors: Mapping[str, Any]
) -> RegressionDecision:
    """Compare committed evidence only; this function never grants a partial pass."""
    validate_slo_manifest(floors)
    validate_result_manifest(baseline)
    validate_result_manifest(candidate)
    reasons: List[str] = []
    baseline_digest = immutable_baseline_digest(baseline)
    marker = baseline.get("immutable_baseline") or {}
    if marker.get("digest") != baseline_digest or marker.get("approved") is not True:
        reasons.append("baseline is not an approved immutable evidence document")
    if candidate.get("baseline_digest") != baseline_digest:
        reasons.append("candidate is not bound to the immutable baseline digest")
    if candidate.get("profile") != baseline.get("profile"):
        reasons.append("resource profile mismatch")
    if candidate.get("workload_digest") != baseline.get("workload_digest"):
        reasons.append("pinned workload manifest mismatch")
    if candidate.get("reference_floors_digest") != baseline.get("reference_floors_digest"):
        reasons.append("pinned reference-floor manifest mismatch")
    if candidate.get("absolute_floors") != baseline.get("absolute_floors"):
        reasons.append("absolute floor evidence mismatch")
    if _identity_projection(candidate["identity"]) != _identity_projection(baseline["identity"]):
        reasons.append("environment/workload/seed/capability/durability/confidence identity mismatch")
    reasons.extend(_assert_floors_not_lowered(baseline, floors))
    tolerances = (floors.get("comparison_rules") or {}).get("default_tolerances") or {}
    throughput_tolerance = float(tolerances["throughput_regression_max_fraction"])
    p99_tolerance = float(tolerances["p99_regression_max_fraction"])
    base_series = {_series_key(s): s for s in baseline["series"]}
    candidate_series = {_series_key(s): s for s in candidate["series"]}
    missing = set(base_series) - set(candidate_series)
    unexpected = set(candidate_series) - set(base_series)
    for key in sorted(missing):
        reasons.append(f"candidate missing pinned benchmark series {key!r}")
    for key in sorted(unexpected):
        reasons.append(f"candidate has unpinned benchmark series {key!r}")
    compared = 0
    for key, old in base_series.items():
        if key[2] != "committed":
            continue
        new = candidate_series.get(key)
        if new is None:
            reasons.append(f"candidate missing committed series {key!r}")
            continue
        compared += 1
        old_metrics, new_metrics = old["metrics"], new["metrics"]
        if new_metrics["committed_tps"] < old_metrics["committed_tps"] * (1.0 - throughput_tolerance):
            reasons.append(f"committed throughput regression in {key!r}")
        if new_metrics["p99_ms"] > old_metrics["p99_ms"] * (1.0 + p99_tolerance):
            reasons.append(f"p99 latency regression in {key!r}")
    if compared == 0:
        reasons.append("no committed metric series were comparable")
    return RegressionDecision(not reasons, tuple(reasons), compared, baseline_digest)

"""Release-readiness policy and evidence validation for the Iroh backend.

The packaged report is deliberately stage-aware.  A release may be approved
with Iroh disabled without implying that the same evidence is sufficient for
experimental, canary, or supported operation.
"""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any, Mapping


READINESS_RESOURCE = "iroh-release-readiness.json"
RECEIPTS_RESOURCE = "iroh-release-receipts.json"
RELEASE_STAGES = ("disabled", "experimental", "canary", "supported")
REQUIRED_RECEIPT_TYPES = ("test", "benchmark", "security")


class ReleaseReadinessError(ValueError):
    """Raised when release evidence is incomplete, unsafe, or inconsistent."""


def _load_resource(name: str) -> dict[str, Any]:
    resource = files("ipfs_kit_py.resources").joinpath(name)
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReleaseReadinessError(f"{name} must contain a JSON object")
    return value


def load_release_readiness() -> dict[str, Any]:
    """Load and validate the immutable, packaged readiness report."""

    report = _load_resource(READINESS_RESOURCE)
    receipts = _load_resource(RECEIPTS_RESOURCE)
    validate_release_readiness(report, receipts)
    return report


def load_release_receipts() -> dict[str, Any]:
    """Load and validate the packaged test, benchmark, and security receipts."""

    report = _load_resource(READINESS_RESOURCE)
    receipts = _load_resource(RECEIPTS_RESOURCE)
    validate_release_readiness(report, receipts)
    return receipts


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseReadinessError(message)


def _strings(value: Any, label: str, *, minimum: int = 1) -> list[str]:
    _require(isinstance(value, list), f"{label} must be an array")
    _require(len(value) >= minimum, f"{label} must contain at least {minimum} item(s)")
    _require(
        all(isinstance(item, str) and item.strip() for item in value),
        f"{label} must contain non-empty strings",
    )
    return value


def _validate_receipts(receipts: Mapping[str, Any]) -> None:
    _require(receipts.get("schema_version") == 1, "unsupported receipt schema version")
    _require(receipts.get("kind") == "ipfs-kit-iroh-release-receipts", "invalid receipt kind")
    _require(receipts.get("task_id") == "IROH-027", "receipt task_id must be IROH-027")
    entries = receipts.get("receipts")
    _require(isinstance(entries, list), "receipts.receipts must be an array")
    ids: set[str] = set()
    types: set[str] = set()
    for entry in entries:
        _require(isinstance(entry, Mapping), "each receipt must be an object")
        receipt_id = entry.get("id")
        _require(isinstance(receipt_id, str) and receipt_id, "receipt id is required")
        _require(receipt_id not in ids, f"duplicate receipt id: {receipt_id}")
        ids.add(receipt_id)
        receipt_type = entry.get("type")
        _require(receipt_type in {*REQUIRED_RECEIPT_TYPES, "operations", "packaging", "interoperability"}, f"invalid receipt type: {receipt_type}")
        types.add(receipt_type)
        status = entry.get("status")
        _require(status in {"passed", "not_run", "conditional"}, f"invalid receipt status: {status}")
        _strings(entry.get("evidence"), f"receipt {receipt_id} evidence")
        command = entry.get("command")
        if command is not None:
            _strings(command, f"receipt {receipt_id} command")
        if status != "passed":
            _require(
                isinstance(entry.get("limitation"), str) and bool(entry["limitation"].strip()),
                f"non-passing receipt {receipt_id} requires a limitation",
            )
    _require(set(REQUIRED_RECEIPT_TYPES) <= types, "test, benchmark, and security receipts are required")

    findings = receipts.get("security_findings")
    _require(isinstance(findings, Mapping), "security_findings must be an object")
    for severity in ("critical", "high", "medium", "low"):
        count = findings.get(f"unresolved_{severity}")
        _require(isinstance(count, int) and not isinstance(count, bool) and count >= 0, f"unresolved_{severity} must be a non-negative integer")
    _require(findings["unresolved_critical"] == 0, "unresolved critical security findings block release")
    _require(findings["unresolved_high"] == 0, "unresolved high security findings block release")


def validate_release_readiness(
    report: Mapping[str, Any], receipts: Mapping[str, Any]
) -> None:
    """Validate cross-artifact safety and stage-gate invariants.

    This validation is intentionally independent of ``jsonschema`` so it also
    runs in a base installation.  The JSON Schema remains the serialization
    contract for CI and external release tooling.
    """

    _validate_receipts(receipts)
    _require(report.get("schema_version") == 1, "unsupported readiness schema version")
    _require(report.get("kind") == "ipfs-kit-iroh-release-readiness", "invalid readiness kind")
    _require(report.get("task_id") == "IROH-027", "readiness task_id must be IROH-027")
    _require(report.get("receipt_resource") == RECEIPTS_RESOURCE, "receipt resource does not match packaged ledger")

    decision = report.get("release_decision")
    _require(isinstance(decision, Mapping), "release_decision must be an object")
    approved_stage = decision.get("approved_stage")
    _require(approved_stage in RELEASE_STAGES, "invalid approved release stage")
    _require(decision.get("decision") in {"go", "no_go"}, "decision must be go or no_go")
    blockers = decision.get("blockers")
    _require(isinstance(blockers, list), "release blockers must be an array")
    _require(
        (decision.get("decision") == "go") == (len(blockers) == 0),
        "go requires no blockers and blockers require no_go",
    )

    rollout = report.get("rollout")
    _require(isinstance(rollout, Mapping), "rollout must be an object")
    _require(rollout.get("default_enabled") is False, "Iroh must remain disabled by default")
    stages = rollout.get("stages")
    _require(isinstance(stages, list) and len(stages) == len(RELEASE_STAGES), "all four rollout stages are required")
    _require([item.get("name") for item in stages if isinstance(item, Mapping)] == list(RELEASE_STAGES), "rollout stages must be ordered disabled, experimental, canary, supported")
    for index, stage in enumerate(stages):
        _require(isinstance(stage, Mapping), "each rollout stage must be an object")
        _require(stage.get("order") == index, f"stage {RELEASE_STAGES[index]} has an invalid order")
        _require(stage.get("automatic_promotion") is False, "automatic stage promotion is forbidden")
        _strings(stage.get("entry_criteria"), f"stage {stage.get('name')} entry_criteria")
        _strings(stage.get("exit_criteria"), f"stage {stage.get('name')} exit_criteria")
        _strings(stage.get("rollback_triggers"), f"stage {stage.get('name')} rollback_triggers")

    rollback = report.get("rollback")
    _require(isinstance(rollback, Mapping), "rollback must be an object")
    for invariant in (
        "disable_before_rollback",
        "preserve_blob_data",
        "preserve_manifests",
        "preserve_identity_backup",
        "require_pre_migration_snapshot",
        "forbid_destructive_uninstall",
    ):
        _require(rollback.get(invariant) is True, f"rollback invariant {invariant} must be true")
    _strings(rollback.get("procedure"), "rollback procedure", minimum=5)
    _strings(rollback.get("verification"), "rollback verification", minimum=3)

    slos = report.get("slos")
    _require(isinstance(slos, list) and len(slos) >= 4, "at least four SLOs are required")
    for slo in slos:
        _require(isinstance(slo, Mapping), "each SLO must be an object")
        _require(slo.get("operator") in {"gte", "lte", "eq"}, "invalid SLO operator")
        _require(isinstance(slo.get("target"), (int, float)) and not isinstance(slo.get("target"), bool), "SLO target must be numeric")
        _require(isinstance(slo.get("unit"), str) and slo["unit"], "SLO unit is required")
        _require(isinstance(slo.get("window"), str) and slo["window"], "SLO window is required")

    for section in ("compatibility", "migration", "deprecation", "data_portability", "support"):
        _require(isinstance(report.get(section), Mapping), f"{section} must be an object")
    _require(report["compatibility"].get("minimum_window_days", 0) >= 90, "compatibility window must be at least 90 days")
    _require(report["deprecation"].get("minimum_notice_days", 0) >= 90, "deprecation notice must be at least 90 days")
    _require(report["data_portability"].get("export_without_sidecar") is True, "portable export must not require a running sidecar")
    _strings(report["support"].get("owners"), "support owners")
    _require(isinstance(report["support"].get("escalation"), str) and report["support"]["escalation"], "support escalation is required")

    receipt_ids = set(decision.get("receipt_ids", []))
    known_ids = {entry["id"] for entry in receipts["receipts"]}
    _require(receipt_ids and receipt_ids <= known_ids, "release decision references missing receipts")
    required = {entry["id"] for entry in receipts["receipts"] if entry.get("required_for") == approved_stage}
    passing = {entry["id"] for entry in receipts["receipts"] if entry.get("status") == "passed"}
    _require(required <= receipt_ids, "release decision omits a required receipt")
    _require(required <= passing, "approved stage has a non-passing required receipt")


def promotion_blockers(
    target_stage: str,
    *,
    report: Mapping[str, Any] | None = None,
    receipts: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return stable blockers for an explicit promotion review.

    The function never changes configuration or stage.  Operators attach new
    immutable receipts, then invoke this check as part of a human sign-off.
    """

    if target_stage not in RELEASE_STAGES:
        raise ReleaseReadinessError(f"unknown rollout stage: {target_stage}")
    report = deepcopy(dict(report)) if report is not None else _load_resource(READINESS_RESOURCE)
    receipts = deepcopy(dict(receipts)) if receipts is not None else _load_resource(RECEIPTS_RESOURCE)
    validate_release_readiness(report, receipts)
    target_index = RELEASE_STAGES.index(target_stage)
    blockers: list[str] = []
    for entry in receipts["receipts"]:
        required_for = entry.get("required_for")
        if required_for not in RELEASE_STAGES:
            continue
        if RELEASE_STAGES.index(required_for) <= target_index and entry.get("status") != "passed":
            blockers.append(f"receipt:{entry['id']}:{entry['status']}")
    approved_index = RELEASE_STAGES.index(report["release_decision"]["approved_stage"])
    if target_index > approved_index:
        blockers.append(f"signoff:stage-{target_stage}-not-approved")
    return sorted(set(blockers))


__all__ = [
    "READINESS_RESOURCE",
    "RECEIPTS_RESOURCE",
    "RELEASE_STAGES",
    "REQUIRED_RECEIPT_TYPES",
    "ReleaseReadinessError",
    "load_release_readiness",
    "load_release_receipts",
    "validate_release_readiness",
    "promotion_blockers",
]

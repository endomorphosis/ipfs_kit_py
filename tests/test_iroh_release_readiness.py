"""IROH-027 staged rollout and release-sign-off contracts."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from ipfs_kit_py.iroh.config import IrohServiceConfig
from ipfs_kit_py.iroh.release import (
    RELEASE_STAGES,
    ReleaseReadinessError,
    load_release_readiness,
    load_release_receipts,
    promotion_blockers,
    validate_release_readiness,
)


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "ipfs_kit_py" / "resources"
READINESS_PATH = RESOURCES / "iroh-release-readiness.json"
READINESS_SCHEMA_PATH = RESOURCES / "iroh-release-readiness.schema.json"
RECEIPTS_PATH = RESOURCES / "iroh-release-receipts.json"
RECEIPTS_SCHEMA_PATH = RESOURCES / "iroh-release-receipts.schema.json"
DOC_PATH = ROOT / "docs" / "iroh" / "release-readiness.md"
NOTES_PATH = ROOT / "docs" / "iroh" / "release-notes.md"
VERIFY_PATH = ROOT / "scripts" / "ci" / "verify_iroh_release_readiness.py"


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_readiness_and_receipt_resources_validate_against_draft_2020_12() -> None:
    readiness_schema = _json(READINESS_SCHEMA_PATH)
    receipt_schema = _json(RECEIPTS_SCHEMA_PATH)
    for schema, value in (
        (readiness_schema, _json(READINESS_PATH)),
        (receipt_schema, _json(RECEIPTS_PATH)),
    ):
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def test_packaged_evidence_cross_validates_and_has_required_receipts() -> None:
    report = load_release_readiness()
    receipts = load_release_receipts()
    assert report["release_decision"]["decision"] == "go"
    assert report["release_decision"]["approved_stage"] == "disabled"
    assert report["release_decision"]["blockers"] == []
    assert {item["type"] for item in receipts["receipts"]} >= {
        "test",
        "benchmark",
        "security",
    }
    assert receipts["security_findings"]["unresolved_critical"] == 0
    assert receipts["security_findings"]["unresolved_high"] == 0


def test_every_configuration_boundary_remains_disabled_by_default() -> None:
    assert IrohServiceConfig.default().enabled is False
    example = (ROOT / "config" / "iroh-backend.example.yaml").read_text(encoding="utf-8")
    assert "enabled: false" in example
    assert load_release_readiness()["rollout"]["default_enabled"] is False


def test_rollout_is_ordered_manual_and_higher_stages_are_not_signed_off() -> None:
    report = load_release_readiness()
    stages = report["rollout"]["stages"]
    assert tuple(stage["name"] for stage in stages) == RELEASE_STAGES
    assert [stage["order"] for stage in stages] == list(range(4))
    assert all(stage["automatic_promotion"] is False for stage in stages)
    assert promotion_blockers("disabled") == []
    assert promotion_blockers("experimental") == [
        "signoff:stage-experimental-not-approved"
    ]
    canary = promotion_blockers("canary")
    assert "receipt:iroh-packaging-source-pinned-20260713:conditional" in canary
    assert "receipt:iroh-real-multinode-pending-20260713:not_run" in canary
    assert "signoff:stage-canary-not-approved" in canary
    assert promotion_blockers("supported")


@pytest.mark.parametrize(
    "field",
    [
        "preserve_blob_data",
        "preserve_manifests",
        "preserve_identity_backup",
        "require_pre_migration_snapshot",
        "forbid_destructive_uninstall",
    ],
)
def test_rollback_cannot_discard_manifests_data_or_recovery_material(field: str) -> None:
    report = copy.deepcopy(load_release_readiness())
    receipts = load_release_receipts()
    report["rollback"][field] = False
    with pytest.raises(ReleaseReadinessError, match=field):
        validate_release_readiness(report, receipts)


@pytest.mark.parametrize("severity", ["critical", "high"])
def test_critical_or_high_unresolved_finding_forces_validation_failure(severity: str) -> None:
    report = load_release_readiness()
    receipts = copy.deepcopy(load_release_receipts())
    receipts["security_findings"][f"unresolved_{severity}"] = 1
    with pytest.raises(ReleaseReadinessError, match=f"unresolved {severity}"):
        validate_release_readiness(report, receipts)


def test_non_passing_receipts_cannot_be_used_for_the_approved_stage() -> None:
    report = load_release_readiness()
    receipts = copy.deepcopy(load_release_receipts())
    receipt = next(item for item in receipts["receipts"] if item["type"] == "security")
    receipt["status"] = "conditional"
    receipt["limitation"] = "review incomplete"
    with pytest.raises(ReleaseReadinessError, match="non-passing required receipt"):
        validate_release_readiness(report, receipts)


def test_slos_compatibility_deprecation_portability_and_support_are_explicit() -> None:
    report = load_release_readiness()
    slos = {item["id"]: item for item in report["slos"]}
    assert slos["read-integrity"]["target"] == 100.0
    assert slos["recovery-point"]["target"] == 0
    assert slos["availability"]["target"] >= 99.9
    assert report["compatibility"]["minimum_window_days"] >= 90
    assert report["deprecation"]["minimum_notice_days"] >= 90
    assert report["migration"]["automatic"] is False
    assert report["data_portability"]["export_without_sidecar"] is True
    assert report["support"]["owners"] and report["support"]["escalation"]


def test_release_documentation_and_notes_disclose_stage_and_limitations() -> None:
    readiness = DOC_PATH.read_text(encoding="utf-8")
    notes = NOTES_PATH.read_text(encoding="utf-8")
    for heading in (
        "## Rollout stages",
        "## SLOs and rollback triggers",
        "## Non-destructive rollback",
        "## Compatibility, migration, and deprecation",
        "## Data portability and ownership",
    ):
        assert heading in readiness
    combined = readiness + notes
    assert "iroh.enabled=false" in combined
    assert "source-pinned" in combined
    assert "not_run" in combined
    assert "critical" in combined and "high" in combined
    assert "manifests" in combined and "blobs" in combined


def test_ci_verifier_emits_a_machine_readable_disabled_stage_receipt(tmp_path: Path) -> None:
    output = tmp_path / "release-verification.json"
    result = subprocess.run(
        [sys.executable, str(VERIFY_PATH), "--target-stage", "disabled", "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = _json(output)
    assert receipt["decision"] == "go"
    assert receipt["approved_stage"] == "disabled"
    assert receipt["blockers"] == []
    assert receipt["unresolved_critical"] == receipt["unresolved_high"] == 0


def test_ci_verifier_fails_closed_for_unsigned_canary() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_PATH), "--target-stage", "canary"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 1
    receipt = json.loads(result.stdout)
    assert receipt["decision"] == "no_go"
    assert any("multinode" in blocker and "not_run" in blocker for blocker in receipt["blockers"])

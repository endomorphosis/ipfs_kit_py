"""PCPR-023 fail-closed VFS/WAL/current-root recovery qualification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import CertificationDisposition
from ipfs_kit_py.assurance.local_backend_qualification import QualificationProbe
from ipfs_kit_py.assurance.vfs_wal_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    LIVE_DRIVER_OPERATIONS,
    PCPR_023_GOAL_ID,
    PCPR_023_TASK_ID,
    QUALIFICATION_INTERFACE,
    REQUIRED_RECOVERY_OPERATIONS,
    VfsWalQualificationError,
    probe_linux_fuse,
    qualify_current_head_vfs_wal,
    refuse_simulated_as_live,
    run_hermetic_vfs_wal_suite,
    sealed_which,
    validate_pcpr_023_outer_receipt,
)
from ipfs_kit_py.assurance.vfs_wal_recovery import (
    BACKEND_ID,
    GENESIS_PARENT,
    LIVE_SUPPORT_CLAIM,
    SUPPORT_CLASS,
    DurableCurrentRootCAS,
    HermeticVfsWalRecoveryAdapter,
    VfsWalRecoveryError,
)
from ipfs_kit_py.core.operation_contracts import ErrorCode


NOW = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)


def test_closed_vocabularies_match_pcpr_023_requirements() -> None:
    assert PCPR_023_TASK_ID == "PCPR-023"
    assert PCPR_023_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "VfsWalQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert "non_promoted_live_storage_gap" in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_vfs_wal_qualification.py"
    )
    assert "current_root_cas" in REQUIRED_RECOVERY_OPERATIONS
    assert "wal_recovery" in REQUIRED_RECOVERY_OPERATIONS
    assert "arc_coherence" in REQUIRED_RECOVERY_OPERATIONS
    assert "crash_recovery" in REQUIRED_RECOVERY_OPERATIONS
    assert "stale_root_rejection" in REQUIRED_RECOVERY_OPERATIONS
    assert "linux_fuse" in LIVE_DRIVER_OPERATIONS
    assert "windows_winfsp" in LIVE_DRIVER_OPERATIONS
    assert "container_fuse" in LIVE_DRIVER_OPERATIONS
    assert LIVE_SUPPORT_CLAIM is False
    assert SUPPORT_CLASS == "hermetic_qualified"


def test_hermetic_adapter_cannot_mint_live_qualification() -> None:
    class _Hermetic:
        backend_id = BACKEND_ID
        live_provider = False
        is_hermetic = True
        simulated = False
        live_support_claim = False

    with pytest.raises(VfsWalQualificationError):
        refuse_simulated_as_live(_Hermetic())

    class _Simulated:
        backend_id = BACKEND_ID
        live_provider = True
        is_hermetic = False
        simulated = True
        live_support_claim = False

    with pytest.raises(VfsWalQualificationError):
        refuse_simulated_as_live(_Simulated())


def test_secret_configuration_is_rejected_without_retention(tmp_path: Path) -> None:
    secret = "pcpr-023-do-not-retain-this-secret"
    with pytest.raises(VfsWalRecoveryError) as caught:
        HermeticVfsWalRecoveryAdapter(
            tmp_path / "secret", configuration={"api_token": secret}
        )
    assert caught.value.error.code is ErrorCode.SECRET_MATERIAL
    assert secret not in str(caught.value)
    assert not (tmp_path / "secret").exists()


def test_stale_parent_and_corruption_fail_closed(tmp_path: Path) -> None:
    store = DurableCurrentRootCAS(tmp_path / "cas")
    first = store.compare_and_swap(GENESIS_PARENT, b"root-1")
    assert first.swapped is True
    with pytest.raises(VfsWalRecoveryError) as stale:
        store.compare_and_swap(GENESIS_PARENT, b"stale")
    assert stale.value.error.code is ErrorCode.PRECONDITION_FAILED
    store.close()

    corrupt = tmp_path / "cas" / "current-root.json"
    corrupt.write_bytes(b'{"generation": 99}')
    with pytest.raises(VfsWalRecoveryError) as integrity:
        DurableCurrentRootCAS.reopen(tmp_path / "cas")
    assert integrity.value.error.code is ErrorCode.INTEGRITY_FAILURE


def test_hermetic_suite_observes_recovery_and_does_not_claim_live(
    tmp_path: Path,
) -> None:
    observations = run_hermetic_vfs_wal_suite(tmp_path / "suite")
    ops = {item["operation"]: item for item in observations}
    assert set(ops) == set(REQUIRED_RECOVERY_OPERATIONS)
    for operation in REQUIRED_RECOVERY_OPERATIONS:
        item = ops[operation]
        assert item["status"] == "passed"
        assert item["environment"] == "hermetic"
        assert item["source"] == "hermetic_observed"
        assert item["signature_valid"] is True
        assert "hermetic_not_live" in item["limitations"]


def test_linux_fuse_probe_is_not_live_mount() -> None:
    probe = probe_linux_fuse()
    assert probe.probe_id == "linux_fuse_doctor"
    assert probe.live is False
    assert probe.simulated_represented_as_live is False
    assert probe.details.get("mounted") is False
    fusermount = sealed_which("fusermount")
    if fusermount == "unavailable" or not Path("/dev/fuse").exists():
        assert probe.present is False
        assert probe.evidence_kind == "unavailable"


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_vfs_wal(now=NOW)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.vfs_live_qualified is False
    assert verdict.suite_complete is False
    assert verdict.live_support_claim is False
    assert verdict.support_class == SUPPORT_CLASS
    assert verdict.certification_disposition in {
        CertificationDisposition.CONDITIONAL.value,
        CertificationDisposition.UNAVAILABLE.value,
    }
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.hermetic_results_represented_as_live is False
    assert verdict.interface_parity_qualified is False
    assert verdict.linux_fuse_live_qualified is False
    assert verdict.windows_winfsp_live_qualified is False
    assert verdict.container_fuse_live_qualified is False
    assert verdict.live_fuse_evidence_kind == "unavailable"
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("b")
    hermetic_ops = {item["operation"] for item in verdict.hermetic_operations}
    assert hermetic_ops == set(REQUIRED_RECOVERY_OPERATIONS)
    for item in verdict.hermetic_operations:
        assert item["live"] is False
        assert item["simulated_represented_as_live"] is False
        assert item["hermetic_represented_as_live"] is False
    extra_ops = {item["operation"] for item in verdict.live_driver_operations}
    assert extra_ops == set(LIVE_DRIVER_OPERATIONS)
    for item in verdict.live_driver_operations:
        assert item["evidence_kind"] == "unavailable"
        assert item["live"] is False
    probe_ids = {item.probe_id for item in verdict.probes}
    assert "hermetic_vfs_wal_adapter" in probe_ids
    assert "linux_fuse_doctor" in probe_ids
    assert "windows_winfsp_doctor" in probe_ids
    assert "container_fuse" in probe_ids
    assert "cli_vfs_parity" in probe_ids
    assert "mcp_vfs_parity" in probe_ids
    assert "mcpp_vfs_parity" in probe_ids
    assert "proof_seal_not_in_scope" in probe_ids
    if verdict.hermetic_vfs_observed:
        assert verdict.certification_disposition == (
            CertificationDisposition.CONDITIONAL.value
        )


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(VfsWalQualificationError):
        validate_pcpr_023_outer_receipt(
            {
                "task_id": "PCPR-023",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )
    with pytest.raises(VfsWalQualificationError):
        validate_pcpr_023_outer_receipt(
            {
                "task_id": "PCPR-023",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "vfs_live_qualified": True,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": False,
                },
            }
        )
    with pytest.raises(VfsWalQualificationError):
        validate_pcpr_023_outer_receipt(
            {
                "task_id": "PCPR-023",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "vfs_live_qualified": False,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": True,
                    "live_fuse_evidence_kind": "unavailable",
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_023_outer_receipt(
        {
            "task_id": "PCPR-023",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
                "vfs_live_qualified": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "vfs_live_qualified": False,
                "simulated_results_represented_as_live": False,
                "hermetic_results_represented_as_live": False,
                "live_support_claim": False,
                "live_fuse_evidence_kind": "unavailable",
            },
        }
    )


def test_unavailable_probe_fixture_shape() -> None:
    probe = QualificationProbe(
        probe_id="fixture",
        present=None,
        evidence_kind="unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason="fixture unavailable",
    )
    mapping = probe.to_mapping()
    assert mapping["evidence_kind"] == "unavailable"
    assert mapping["live"] is False
    assert json.loads(json.dumps(mapping))["probe_id"] == "fixture"


def test_backend_id_is_vfs_wal() -> None:
    assert BACKEND_ID == "vfs_wal_current_root"
    assert HermeticVfsWalRecoveryAdapter.backend_id == "vfs_wal_current_root"
    assert HermeticVfsWalRecoveryAdapter.production_authorized is False
    assert HermeticVfsWalRecoveryAdapter.simulated is False
    assert HermeticVfsWalRecoveryAdapter.live_support_claim is False
    assert HermeticVfsWalRecoveryAdapter.is_hermetic is True
    assert HermeticVfsWalRecoveryAdapter.live_provider is False

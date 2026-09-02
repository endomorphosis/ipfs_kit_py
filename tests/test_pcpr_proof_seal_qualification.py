"""PCPR-024 fail-closed proof-seal store qualification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import CertificationDisposition
from ipfs_kit_py.assurance.local_backend_qualification import QualificationProbe
from ipfs_kit_py.assurance.proof_seal import (
    BACKEND_ID,
    LIVE_SUPPORT_CLAIM,
    SUPPORT_CLASS,
    HermeticProofSealQualificationSurface,
    ProofSealSurfaceError,
)
from ipfs_kit_py.assurance.proof_seal_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    LIVE_UNAVAILABLE_OPERATIONS,
    PCPR_024_GOAL_ID,
    PCPR_024_TASK_ID,
    QUALIFICATION_INTERFACE,
    REQUIRED_PROOF_SEAL_OPERATIONS,
    ProofSealQualificationError,
    probe_live_ipfs_transport,
    qualify_current_head_proof_seal,
    refuse_simulated_as_live,
    run_hermetic_proof_seal_suite,
    sealed_which,
    validate_pcpr_024_outer_receipt,
)
from ipfs_kit_py.core.operation_contracts import ErrorCode
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ForbiddenArtifactError,
    ForbiddenArtifactKind,
)
from ipfs_kit_py.proof_seal_store.local_store import LocalStoreReason


NOW = datetime(2026, 9, 2, 6, 0, tzinfo=timezone.utc)


def test_closed_vocabularies_match_pcpr_024_requirements() -> None:
    assert PCPR_024_TASK_ID == "PCPR-024"
    assert PCPR_024_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "ProofSealQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert "non_promoted_live_storage_gap" in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_proof_seal_qualification.py"
    )
    assert "exact_bytes" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "candidate_vs_current" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "fresh_verification_before_reuse" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "witness_key_protection" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "wal" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "restart" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "stale_parent" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "concurrent_writers" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "tombstone" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "invalidation" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "legacy_certificate_staging" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "corruption" in REQUIRED_PROOF_SEAL_OPERATIONS
    assert "live_ipfs_transport" in LIVE_UNAVAILABLE_OPERATIONS
    assert "interface_parity" in LIVE_UNAVAILABLE_OPERATIONS
    assert LIVE_SUPPORT_CLAIM is False
    assert SUPPORT_CLASS == "hermetic_qualified"


def test_hermetic_adapter_cannot_mint_live_qualification() -> None:
    class _Hermetic:
        backend_id = BACKEND_ID
        live_provider = False
        is_hermetic = True
        simulated = False
        live_support_claim = False

    with pytest.raises(ProofSealQualificationError):
        refuse_simulated_as_live(_Hermetic())

    class _Simulated:
        backend_id = BACKEND_ID
        live_provider = True
        is_hermetic = False
        simulated = True
        live_support_claim = False

    with pytest.raises(ProofSealQualificationError):
        refuse_simulated_as_live(_Simulated())


def test_secret_configuration_is_rejected_without_retention(tmp_path: Path) -> None:
    secret = "pcpr-024-do-not-retain-this-secret"
    with pytest.raises(ProofSealSurfaceError) as caught:
        HermeticProofSealQualificationSurface(
            tmp_path / "secret", configuration={"api_token": secret}
        )
    assert caught.value.error.code is ErrorCode.SECRET_MATERIAL
    assert secret not in str(caught.value)
    assert not (tmp_path / "secret").exists()


def test_forbidden_kinds_are_not_stored(tmp_path: Path) -> None:
    surface = HermeticProofSealQualificationSurface(tmp_path / "store")
    try:
        for forbidden in (
            ForbiddenArtifactKind.PROVING_KEY.value,
            ForbiddenArtifactKind.WITNESS.value,
        ):
            result = surface.objects.put_immutable_result(
                forbidden, b"must-not-persist"
            )
            assert not result.stored
            assert result.reason is LocalStoreReason.FORBIDDEN_KIND
        with pytest.raises(ForbiddenArtifactError):
            surface.stage_legacy_blob(
                b'{"legacy":true}',
                claimed_kind=ForbiddenArtifactKind.WITNESS.value,
            )
    finally:
        surface.close()


def test_hermetic_suite_observes_proof_seal_and_does_not_claim_live(
    tmp_path: Path,
) -> None:
    observations = run_hermetic_proof_seal_suite(tmp_path / "suite")
    ops = {item["operation"]: item for item in observations}
    assert set(ops) == set(REQUIRED_PROOF_SEAL_OPERATIONS)
    for operation in REQUIRED_PROOF_SEAL_OPERATIONS:
        item = ops[operation]
        assert item["status"] == "passed"
        assert item["environment"] == "hermetic"
        assert item["source"] == "hermetic_observed"
        assert item["signature_valid"] is True
        assert item["live"] is False
        assert "hermetic_not_live" in item["limitations"]


def test_live_ipfs_probe_is_not_a_daemon_session() -> None:
    probe = probe_live_ipfs_transport()
    assert probe.probe_id == "live_ipfs_transport"
    assert probe.live is False
    assert probe.simulated_represented_as_live is False
    assert probe.details.get("live_daemon_started") is False
    if sealed_which("ipfs") == "unavailable":
        assert probe.present is False
        assert probe.evidence_kind == "unavailable"


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_proof_seal(now=NOW)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.proof_seal_live_qualified is False
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
    assert verdict.live_ipfs_transport_qualified is False
    assert verdict.live_ipfs_evidence_kind == "unavailable"
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("b")
    hermetic_ops = {item["operation"] for item in verdict.hermetic_operations}
    assert hermetic_ops == set(REQUIRED_PROOF_SEAL_OPERATIONS)
    for item in verdict.hermetic_operations:
        assert item["live"] is False
        assert item["simulated_represented_as_live"] is False
        assert item["hermetic_represented_as_live"] is False
    extra_ops = {item["operation"] for item in verdict.live_unavailable_operations}
    assert extra_ops == set(LIVE_UNAVAILABLE_OPERATIONS)
    for item in verdict.live_unavailable_operations:
        assert item["evidence_kind"] == "unavailable"
        assert item["live"] is False
    probe_ids = {item.probe_id for item in verdict.probes}
    assert "hermetic_proof_seal_surface" in probe_ids
    assert "live_ipfs_transport" in probe_ids
    assert "cli_proof_seal_parity" in probe_ids
    assert "mcp_proof_seal_parity" in probe_ids
    assert "mcpp_proof_seal_parity" in probe_ids
    assert "vfs_wal_not_reopened" in probe_ids
    if verdict.hermetic_proof_seal_observed:
        assert verdict.certification_disposition == (
            CertificationDisposition.CONDITIONAL.value
        )
        assert verdict.witness_key_protection_observed is True


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(ProofSealQualificationError):
        validate_pcpr_024_outer_receipt(
            {
                "task_id": "PCPR-024",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )
    with pytest.raises(ProofSealQualificationError):
        validate_pcpr_024_outer_receipt(
            {
                "task_id": "PCPR-024",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "proof_seal_live_qualified": True,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": False,
                },
            }
        )
    with pytest.raises(ProofSealQualificationError):
        validate_pcpr_024_outer_receipt(
            {
                "task_id": "PCPR-024",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "proof_seal_live_qualified": False,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": True,
                    "live_ipfs_evidence_kind": "unavailable",
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_024_outer_receipt(
        {
            "task_id": "PCPR-024",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
                "proof_seal_live_qualified": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "proof_seal_live_qualified": False,
                "simulated_results_represented_as_live": False,
                "hermetic_results_represented_as_live": False,
                "live_support_claim": False,
                "live_ipfs_evidence_kind": "unavailable",
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


def test_backend_id_is_proof_seal_store() -> None:
    assert BACKEND_ID == "proof_seal_store"
    assert HermeticProofSealQualificationSurface.backend_id == "proof_seal_store"
    assert HermeticProofSealQualificationSurface.production_authorized is False
    assert HermeticProofSealQualificationSurface.simulated is False
    assert HermeticProofSealQualificationSurface.live_support_claim is False
    assert HermeticProofSealQualificationSurface.is_hermetic is True
    assert HermeticProofSealQualificationSurface.live_provider is False

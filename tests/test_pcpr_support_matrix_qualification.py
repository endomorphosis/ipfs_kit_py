"""PCPR-027 fail-closed authoritative support-matrix qualification."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import CertificationDisposition
from ipfs_kit_py.assurance.local_backend_qualification import QualificationProbe
from ipfs_kit_py.assurance.support_matrix import (
    BACKEND_ID,
    LIVE_SUPPORT_CLAIM,
    POLICY,
    README_BEGIN_MARKER,
    README_END_MARKER,
    SUPPORT_CLASS,
    SUPPORT_CLASSES,
    SupportMatrixError,
    check_readme_against_matrix,
    generate_authoritative_support_matrix,
    matrix_contract,
    refuse_simulated_as_live,
    render_readme_claims,
)
from ipfs_kit_py.assurance.support_matrix_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    LIVE_UNAVAILABLE_OPERATIONS,
    PCPR_027_GOAL_ID,
    PCPR_027_TASK_ID,
    QUALIFICATION_INTERFACE,
    REQUIRED_MATRIX_OPERATIONS,
    SupportMatrixQualificationError,
    probe_live_ipfs_transport,
    probe_live_mcp_server,
    qualify_current_head_support_matrix,
    run_hermetic_matrix_suite,
    sealed_which,
    validate_pcpr_027_outer_receipt,
)


NOW = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)
KIT_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_027_requirements() -> None:
    assert PCPR_027_TASK_ID == "PCPR-027"
    assert PCPR_027_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "SupportMatrixQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_support_matrix_qualification.py"
    )
    assert "closed_vocabulary_admitted" in REQUIRED_MATRIX_OPERATIONS
    assert "every_row_uses_closed_class" in REQUIRED_MATRIX_OPERATIONS
    assert "live_qualified_requires_live_evidence" in REQUIRED_MATRIX_OPERATIONS
    assert "hermetic_not_represented_as_live" in REQUIRED_MATRIX_OPERATIONS
    assert "simulated_not_represented_as_live" in REQUIRED_MATRIX_OPERATIONS
    assert "readme_claims_agree" in REQUIRED_MATRIX_OPERATIONS
    assert "missing_environments_typed_unavailable" in REQUIRED_MATRIX_OPERATIONS
    assert "zero_live_qualified_surfaces" in REQUIRED_MATRIX_OPERATIONS
    assert "live_ipfs_transport" in LIVE_UNAVAILABLE_OPERATIONS
    assert "live_iroh_sidecar" in LIVE_UNAVAILABLE_OPERATIONS
    assert "live_linux_fuse_mount" in LIVE_UNAVAILABLE_OPERATIONS
    assert "live_mcp_server" in LIVE_UNAVAILABLE_OPERATIONS
    assert LIVE_SUPPORT_CLAIM is False
    assert SUPPORT_CLASS == "conditional"
    assert POLICY == "AuthoritativeSupportMatrixPolicy@1"
    assert SUPPORT_CLASSES == (
        "hermetic_qualified",
        "live_qualified",
        "conditional",
        "configuration_only",
        "experimental",
        "unavailable",
        "unsupported",
    )


def test_hermetic_adapter_cannot_mint_live_qualification() -> None:
    class _Hermetic:
        backend_id = BACKEND_ID
        live_provider = False
        is_hermetic = True
        simulated = False
        live_support_claim = False

    with pytest.raises(SupportMatrixError):
        refuse_simulated_as_live(_Hermetic())

    class _Simulated:
        backend_id = BACKEND_ID
        live_provider = True
        is_hermetic = False
        simulated = True
        live_support_claim = False

    with pytest.raises(SupportMatrixError):
        refuse_simulated_as_live(_Simulated())


def test_matrix_uses_closed_vocabulary_and_is_not_a_release() -> None:
    contract = matrix_contract()
    assert contract["live_support_claim"] is False
    assert contract["production_authorized"] is False
    assert contract["simulated"] is False
    assert contract["live_provider"] is False
    assert contract["is_hermetic"] is True
    assert contract["live_qualified_row_count"] == 0
    assert contract["policy"] == POLICY
    used = {row["support_class"] for row in contract["rows"]}
    assert used <= set(SUPPORT_CLASSES)
    assert "hermetic_qualified" in used
    assert "conditional" in used
    assert "configuration_only" in used
    assert "experimental" in used
    assert "unavailable" in used
    assert "unsupported" in used
    assert "live_qualified" not in used
    for row in contract["rows"]:
        assert row["live"] is False
        assert row["live_support_claim"] is False
        assert row["simulated"] is False
    assert contract["matrix_cid"].startswith("b")


def test_live_qualified_row_without_live_evidence_is_rejected() -> None:
    matrix = generate_authoritative_support_matrix()
    live_row = matrix.rows[0]
    with pytest.raises(SupportMatrixError):
        live_row.__class__(
            surface_id="forged_live",
            display_name="Forged",
            support_class="live_qualified",
            live_support_claim=True,
            evidence_kind="simulated",
            live=False,
            simulated=True,
            hermetic=False,
            producing_task="PCPR-027",
            schema="forged",
            interface="forged",
            reason="forged",
        ).to_mapping()


def test_hermetic_suite_observes_matrix_and_does_not_claim_live() -> None:
    observations = run_hermetic_matrix_suite(kit_root=KIT_ROOT)
    ops = {item["operation"]: item for item in observations}
    assert set(ops) == set(REQUIRED_MATRIX_OPERATIONS)
    for operation in REQUIRED_MATRIX_OPERATIONS:
        item = ops[operation]
        assert item["status"] == "passed"
        assert item["environment"] == "hermetic"
        assert item["source"] == "hermetic_observed"
        assert item["signature_valid"] is True
        assert item["live"] is False
        assert "hermetic_not_live" in item["limitations"]


def test_readme_claims_are_generated_from_the_matrix() -> None:
    matrix = generate_authoritative_support_matrix()
    readme = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
    assert README_BEGIN_MARKER in readme
    assert README_END_MARKER in readme
    agreement = check_readme_against_matrix(readme, matrix)
    assert agreement["agrees"] is True
    assert agreement["live_qualified_row_count"] == 0
    rendered = render_readme_claims(matrix)
    assert "`live_qualified`" in rendered
    assert "not a closed PCPR release" in rendered
    with pytest.raises(SupportMatrixError):
        check_readme_against_matrix("no markers and production ready", matrix)


def test_live_ipfs_probe_is_not_a_daemon_session() -> None:
    probe = probe_live_ipfs_transport()
    assert probe.probe_id == "live_ipfs_transport"
    assert probe.live is False
    assert probe.simulated_represented_as_live is False
    assert probe.details.get("live_daemon_started") is False
    if sealed_which("ipfs") == "unavailable":
        assert probe.present is False
        assert probe.evidence_kind == "unavailable"


def test_live_mcp_server_probe_is_unavailable() -> None:
    probe = probe_live_mcp_server()
    assert probe.present is False
    assert probe.live is False
    assert probe.evidence_kind == "unavailable"
    assert probe.details.get("stdio_server_started") is False


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_support_matrix(now=NOW, kit_root=KIT_ROOT)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.support_matrix_live_qualified is False
    assert verdict.suite_complete is False
    assert verdict.live_support_claim is False
    assert verdict.support_class == SUPPORT_CLASS
    assert verdict.certification_disposition in {
        CertificationDisposition.CONDITIONAL.value,
        CertificationDisposition.UNAVAILABLE.value,
    }
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.hermetic_results_represented_as_live is False
    assert verdict.live_ipfs_transport_qualified is False
    assert verdict.live_ipfs_evidence_kind == "unavailable"
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("b")
    assert verdict.matrix_cid.startswith("b")
    assert verdict.live_qualified_row_count == 0
    hermetic_ops = {item["operation"] for item in verdict.hermetic_operations}
    assert hermetic_ops == set(REQUIRED_MATRIX_OPERATIONS)
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
    assert "authoritative_support_matrix" in probe_ids
    assert "live_ipfs_transport" in probe_ids
    assert "live_iroh_sidecar" in probe_ids
    assert "live_linux_fuse_mount" in probe_ids
    assert "live_mcp_server" in probe_ids
    assert "interface_parity_not_reopened" in probe_ids
    assert verdict.support_matrix_generated is True
    assert verdict.readme_claims_agree is True
    assert verdict.certification_disposition == (
        CertificationDisposition.CONDITIONAL.value
    )
    assert "live_ipfs_transport" in verdict.operations_missing
    assert "live_mcp_server" in verdict.operations_missing


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(SupportMatrixQualificationError):
        validate_pcpr_027_outer_receipt(
            {
                "task_id": "PCPR-027",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )
    with pytest.raises(SupportMatrixQualificationError):
        validate_pcpr_027_outer_receipt(
            {
                "task_id": "PCPR-027",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "support_matrix_live_qualified": True,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": False,
                },
            }
        )
    with pytest.raises(SupportMatrixQualificationError):
        validate_pcpr_027_outer_receipt(
            {
                "task_id": "PCPR-027",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "support_matrix_live_qualified": False,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": True,
                    "live_ipfs_evidence_kind": "unavailable",
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_027_outer_receipt(
        {
            "task_id": "PCPR-027",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
                "support_matrix_live_qualified": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "support_matrix_live_qualified": False,
                "simulated_results_represented_as_live": False,
                "hermetic_results_represented_as_live": False,
                "live_support_claim": False,
                "live_qualified_row_count": 0,
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

"""PCPR-026 fail-closed Python/CLI/MCP/MCP++ parity qualification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import CertificationDisposition
from ipfs_kit_py.assurance.interface_parity import (
    BACKEND_ID,
    LIVE_SUPPORT_CLAIM,
    POLICY,
    SUPPORT_CLASS,
    InterfaceParityError,
    build_parity_stack,
    parity_cid,
    parity_contract,
    refuse_simulated_as_live,
)
from ipfs_kit_py.assurance.interface_parity_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    LIVE_UNAVAILABLE_OPERATIONS,
    PCPR_026_GOAL_ID,
    PCPR_026_TASK_ID,
    QUALIFICATION_INTERFACE,
    REQUIRED_PARITY_OPERATIONS,
    InterfaceParityQualificationError,
    probe_live_ipfs_transport,
    probe_live_mcp_server,
    qualify_current_head_interface_parity,
    run_adapter_parity_suite,
    sealed_which,
    validate_pcpr_026_outer_receipt,
)
from ipfs_kit_py.assurance.local_backend_qualification import QualificationProbe


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def test_closed_vocabularies_match_pcpr_026_requirements() -> None:
    assert PCPR_026_TASK_ID == "PCPR-026"
    assert PCPR_026_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "InterfaceParityQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_interface_parity_qualification.py"
    )
    assert "python_write_read_digest_delete" in REQUIRED_PARITY_OPERATIONS
    assert "cli_write_read_digest_delete" in REQUIRED_PARITY_OPERATIONS
    assert "mcp_write_read_digest_delete" in REQUIRED_PARITY_OPERATIONS
    assert "mcpp_write_read_digest_delete" in REQUIRED_PARITY_OPERATIONS
    assert "semantic_payload_parity" in REQUIRED_PARITY_OPERATIONS
    assert "cid_identity_parity" in REQUIRED_PARITY_OPERATIONS
    assert "error_parity" in REQUIRED_PARITY_OPERATIONS
    assert "live_mcp_server" in LIVE_UNAVAILABLE_OPERATIONS
    assert "live_ipfs_transport" in LIVE_UNAVAILABLE_OPERATIONS
    assert LIVE_SUPPORT_CLAIM is False
    assert SUPPORT_CLASS == "conditional"
    assert POLICY == "AllInterfaceParityPolicy@1"


def test_hermetic_adapter_cannot_mint_live_qualification() -> None:
    class _Hermetic:
        backend_id = BACKEND_ID
        live_provider = False
        is_hermetic = True
        simulated = False
        live_support_claim = False

    with pytest.raises(InterfaceParityError):
        refuse_simulated_as_live(_Hermetic())

    class _Simulated:
        backend_id = BACKEND_ID
        live_provider = True
        is_hermetic = False
        simulated = True
        live_support_claim = False

    with pytest.raises(InterfaceParityError):
        refuse_simulated_as_live(_Simulated())


def test_parity_contract_is_not_a_release() -> None:
    contract = parity_contract()
    assert contract["live_support_claim"] is False
    assert contract["production_authorized"] is False
    assert contract["simulated"] is False
    assert contract["live_mcp_server"] is False
    assert contract["live_ipfs"] is False
    assert contract["policy"] == POLICY
    assert parity_cid().startswith("bafk")


def test_adapter_suite_observes_parity_and_does_not_claim_live_servers(
    tmp_path: Path,
) -> None:
    observations = run_adapter_parity_suite(tmp_path / "store")
    ops = {item["operation"]: item for item in observations}
    assert set(ops) == set(REQUIRED_PARITY_OPERATIONS)
    for operation in REQUIRED_PARITY_OPERATIONS:
        item = ops[operation]
        assert item["status"] == "passed"
        assert item["signature_valid"] is True
        assert item["simulated_represented_as_live"] is False
        assert item["hermetic_represented_as_live"] is False
        if operation == "python_write_read_digest_delete":
            assert item["live"] is True
            assert item["evidence_kind"] == "measured_live"
        else:
            assert item["live"] is False
            assert "adapter_not_live_server" in item["limitations"]


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
    verdict = qualify_current_head_interface_parity(now=NOW)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.interface_parity_live_qualified is False
    assert verdict.suite_complete is False
    assert verdict.live_support_claim is False
    assert verdict.support_class == SUPPORT_CLASS
    assert verdict.certification_disposition in {
        CertificationDisposition.CONDITIONAL.value,
        CertificationDisposition.UNAVAILABLE.value,
    }
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.hermetic_results_represented_as_live is False
    assert verdict.live_server_parity_qualified is False
    assert verdict.live_ipfs_transport_qualified is False
    assert verdict.live_ipfs_evidence_kind == "unavailable"
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("b")
    adapter_ops = {item["operation"] for item in verdict.adapter_operations}
    assert adapter_ops == set(REQUIRED_PARITY_OPERATIONS)
    for item in verdict.adapter_operations:
        assert item["live"] is False
        assert item["simulated_represented_as_live"] is False
        assert item["hermetic_represented_as_live"] is False
    extra_ops = {item["operation"] for item in verdict.live_unavailable_operations}
    assert extra_ops == set(LIVE_UNAVAILABLE_OPERATIONS)
    for item in verdict.live_unavailable_operations:
        assert item["evidence_kind"] == "unavailable"
        assert item["live"] is False
    probe_ids = {item.probe_id for item in verdict.probes}
    assert "interface_parity_surface" in probe_ids
    assert "live_ipfs_transport" in probe_ids
    assert "live_mcp_server" in probe_ids
    assert "cli_adapter_session" in probe_ids
    assert "mcp_adapter_session" in probe_ids
    assert "mcpp_adapter_session" in probe_ids
    assert "python_adapter_session" in probe_ids
    assert "support_matrix_not_generated" in probe_ids
    assert verdict.adapter_parity_observed is True
    assert verdict.interface_parity_qualified is True
    assert verdict.certification_disposition == (
        CertificationDisposition.CONDITIONAL.value
    )
    assert "live_mcp_server" in verdict.operations_missing
    assert "live_ipfs_transport" in verdict.operations_missing


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(InterfaceParityQualificationError):
        validate_pcpr_026_outer_receipt(
            {
                "task_id": "PCPR-026",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )
    with pytest.raises(InterfaceParityQualificationError):
        validate_pcpr_026_outer_receipt(
            {
                "task_id": "PCPR-026",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "interface_parity_live_qualified": True,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": False,
                },
            }
        )
    with pytest.raises(InterfaceParityQualificationError):
        validate_pcpr_026_outer_receipt(
            {
                "task_id": "PCPR-026",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "interface_parity_live_qualified": False,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": True,
                    "live_ipfs_evidence_kind": "unavailable",
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_026_outer_receipt(
        {
            "task_id": "PCPR-026",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
                "interface_parity_live_qualified": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "interface_parity_live_qualified": False,
                "simulated_results_represented_as_live": False,
                "hermetic_results_represented_as_live": False,
                "live_support_claim": False,
                "live_server_parity_qualified": False,
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


def test_backend_id_is_interface_parity(tmp_path: Path) -> None:
    assert BACKEND_ID == "interface_parity"
    contract = parity_contract()
    assert contract["backend_id"] == "interface_parity"
    stack = build_parity_stack(tmp_path / "store")
    try:
        assert stack.store.backend_id == "local_filesystem"
        assert stack.store.live_provider is True
        assert stack.store.simulated is False
        assert stack.store.production_authorized is False
    finally:
        stack.close()

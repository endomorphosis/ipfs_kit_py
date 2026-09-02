"""PCPR-025 fail-closed sibling test-tree decoupling qualification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import CertificationDisposition
from ipfs_kit_py.assurance.local_backend_qualification import QualificationProbe
from ipfs_kit_py.assurance.sibling_test_tree import (
    BACKEND_ID,
    LIVE_SUPPORT_CLAIM,
    SUPPORT_CLASS,
    decoupling_contract,
)
from ipfs_kit_py.assurance.sibling_test_tree_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    LIVE_UNAVAILABLE_OPERATIONS,
    PCPR_025_GOAL_ID,
    PCPR_025_TASK_ID,
    QUALIFICATION_INTERFACE,
    REQUIRED_DECOUPLING_OPERATIONS,
    SiblingTestTreeQualificationError,
    probe_live_ipfs_transport,
    qualify_current_head_sibling_test_tree,
    refuse_simulated_as_live,
    run_hermetic_decoupling_suite,
    sealed_which,
    validate_pcpr_025_outer_receipt,
)


NOW = datetime(2026, 9, 2, 6, 0, tzinfo=timezone.utc)
KIT_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_025_requirements() -> None:
    assert PCPR_025_TASK_ID == "PCPR-025"
    assert PCPR_025_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "SiblingTestTreeQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert "non_promoted_packaging_gap" in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_sibling_test_tree_qualification.py"
    )
    assert "sitecustomize_no_sibling_sys_path" in REQUIRED_DECOUPLING_OPERATIONS
    assert "runtime_readiness_harness_no_sys_path" in REQUIRED_DECOUPLING_OPERATIONS
    assert (
        "runtime_readiness_harness_no_test_tree_requirement"
        in REQUIRED_DECOUPLING_OPERATIONS
    )
    assert "kernel_vfs_harness_no_sys_path" in REQUIRED_DECOUPLING_OPERATIONS
    assert "datasets_vectors_packaged" in REQUIRED_DECOUPLING_OPERATIONS
    assert "coordination_vectors_no_monorepo_sibling" in REQUIRED_DECOUPLING_OPERATIONS
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

    with pytest.raises(SiblingTestTreeQualificationError):
        refuse_simulated_as_live(_Hermetic())

    class _Simulated:
        backend_id = BACKEND_ID
        live_provider = True
        is_hermetic = False
        simulated = True
        live_support_claim = False

    with pytest.raises(SiblingTestTreeQualificationError):
        refuse_simulated_as_live(_Simulated())


def test_sitecustomize_does_not_insert_sys_path() -> None:
    source = (KIT_ROOT / "sitecustomize.py").read_text(encoding="utf-8")
    assert "sys.path.insert" not in source
    assert "sys.path.append" not in source


def test_runtime_readiness_harness_does_not_couple_sibling_tests() -> None:
    source = (
        KIT_ROOT / "benchmarks" / "runtime_readiness" / "run.py"
    ).read_text(encoding="utf-8")
    assert "sys.path.insert" not in source
    assert "tests/runtime_readiness" not in source


def test_packaged_vectors_do_not_walk_datasets_tests_tree() -> None:
    source = (
        KIT_ROOT
        / "tests"
        / "adversarial_assurance_store"
        / "datasets_test_fixtures.py"
    ).read_text(encoding="utf-8")
    assert "spec_from_file_location" not in source
    assert "normative_vectors" in source
    contract = decoupling_contract()
    assert contract["sibling_tests_package_required"] is False
    assert contract["sibling_checkout_required"] is False
    assert contract["live_support_claim"] is False


def test_hermetic_suite_observes_decoupling_and_does_not_claim_live() -> None:
    observations = run_hermetic_decoupling_suite()
    ops = {item["operation"]: item for item in observations}
    assert set(ops) == set(REQUIRED_DECOUPLING_OPERATIONS)
    for operation in REQUIRED_DECOUPLING_OPERATIONS:
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
    verdict = qualify_current_head_sibling_test_tree(now=NOW)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.sibling_test_tree_live_qualified is False
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
    assert verdict.sibling_tests_package_required is False
    assert verdict.sibling_checkout_required is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("b")
    hermetic_ops = {item["operation"] for item in verdict.hermetic_operations}
    assert hermetic_ops == set(REQUIRED_DECOUPLING_OPERATIONS)
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
    assert "hermetic_sibling_test_tree_surface" in probe_ids
    assert "live_ipfs_transport" in probe_ids
    assert "cli_sibling_tree_parity" in probe_ids
    assert "mcp_sibling_tree_parity" in probe_ids
    assert "mcpp_sibling_tree_parity" in probe_ids
    assert "proof_seal_not_reopened" in probe_ids
    assert verdict.hermetic_decoupling_observed is True
    assert verdict.certification_disposition == (
        CertificationDisposition.CONDITIONAL.value
    )


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(SiblingTestTreeQualificationError):
        validate_pcpr_025_outer_receipt(
            {
                "task_id": "PCPR-025",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )
    with pytest.raises(SiblingTestTreeQualificationError):
        validate_pcpr_025_outer_receipt(
            {
                "task_id": "PCPR-025",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "sibling_test_tree_live_qualified": True,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": False,
                },
            }
        )
    with pytest.raises(SiblingTestTreeQualificationError):
        validate_pcpr_025_outer_receipt(
            {
                "task_id": "PCPR-025",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "sibling_test_tree_live_qualified": False,
                    "simulated_results_represented_as_live": False,
                    "hermetic_results_represented_as_live": True,
                    "live_ipfs_evidence_kind": "unavailable",
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_025_outer_receipt(
        {
            "task_id": "PCPR-025",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
                "sibling_test_tree_live_qualified": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "sibling_test_tree_live_qualified": False,
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


def test_backend_id_is_sibling_test_tree() -> None:
    assert BACKEND_ID == "sibling_test_tree"
    contract = decoupling_contract()
    assert contract["backend_id"] == "sibling_test_tree"
    assert contract["production_authorized"] is False
    assert contract["simulated"] is False
    assert contract["live_support_claim"] is False
    assert contract["is_hermetic"] is True
    assert contract["live_provider"] is False

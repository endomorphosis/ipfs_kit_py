"""PCPR-069: Kit binding to Accelerate stale rejection and PlanDelta."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.assurance.stale_rejection import (
    CLOSED_RELEASE_OUTCOMES,
    CURRENT_HEAD_NON_PROMOTION_VERDICT_CID,
    ESCALATION_ORDER,
    HERMETIC_CANDIDATE_SUITES,
    INTERFACE,
    OPERATOR_BLOCKING_TASK_ID,
    OBJECTIVE_KIND,
    OutcomeProbe,
    PCPR_069_GOAL_ID,
    PCPR_069_TASK_ID,
    PINNED_BINDING_CID,
    PINNED_CURRENT_ROOT_CID,
    PINNED_IDEA_DIGEST,
    PINNED_OBJECTIVE_CID,
    PINNED_PACK_CID,
    PINNED_PATCH_CID,
    PINNED_ROUTE_CID,
    PINNED_RUN_CID,
    SCHEMA,
    SEALED_PATH,
    SEALED_PYTHON,
    KitStaleRejectionError,
    current_head_static_probes,
    pcpr_069_receipt_promotion,
    qualify_current_head_stale_rejection,
    qualify_stale_rejection,
    refuse_current_root_remint,
    refuse_history_mutation,
    refuse_live_storage,
    refuse_model_completion,
    refuse_pack_cid_remint,
    refuse_patch_cid_remint,
    refuse_route_cid_remint,
    refuse_run_cid_remint,
    render_declared_binding,
    verify_stale_rejection_files,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_069_requirements() -> None:
    assert PCPR_069_TASK_ID == "PCPR-069"
    assert PCPR_069_GOAL_ID == "PCPR-G700"
    assert INTERFACE == "KitStaleRejectionAndPlanDeltaBinding@1"
    assert SCHEMA == "ipfs_kit_py/assurance/stale-rejection-binding@1"
    assert OBJECTIVE_KIND == "declared_stale_rejection_binding"
    assert OPERATOR_BLOCKING_TASK_ID == (
        "pcpr-069-operator-live-stale-rejection-and-plan-delta"
    )
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_069_stale_rejection.py"
    )
    assert SEALED_PATH == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
    assert SEALED_PYTHON == "/usr/bin/python3.12"
    binding = render_declared_binding()
    assert binding["applied"] is False
    assert binding["live"] is False
    assert binding["release_claim"] is False
    assert binding["closed_release_outcome"] is None
    assert binding["context_pack"]["constructed"] is True
    assert binding["context_pack"]["constructed_by"] == "ipfs_datasets_py"
    assert binding["context_pack"]["reminted"] is False
    assert binding["context_pack"]["rejected"] is True
    assert binding["storage"]["stored"] is True
    assert binding["storage"]["stored_by"] == "ipfs_kit_py"
    assert binding["storage"]["current_root_published"] is True
    assert binding["route"]["executed"] is True
    assert binding["route"]["executed_by"] == "ipfs_accelerate_py"
    assert binding["bounded_patch"]["produced"] is True
    delta = binding["stale_rejection"]
    assert delta["kind"] == "stale_rejection_and_plan_delta"
    assert delta["classified_by"] == "ipfs_accelerate_py"
    assert delta["stored"] is False
    assert delta["live"] is False
    assert delta["stale_rejected"] is True
    assert delta["history_mutated"] is False
    assert binding["duckdb_or_quack_state_written"] is False
    assert binding["objective_cid"] == PINNED_OBJECTIVE_CID
    assert binding["idea_digest"] == PINNED_IDEA_DIGEST
    assert binding["context_pack"]["pack_cid"] == PINNED_PACK_CID
    assert binding["storage"]["current_root_cid"] == PINNED_CURRENT_ROOT_CID
    assert binding["route"]["route_cid"] == PINNED_ROUTE_CID
    assert binding["bounded_patch"]["patch_cid"] == PINNED_PATCH_CID
    assert binding["selected_tests"]["run_cid"] == PINNED_RUN_CID
    assert binding["binding_cid"] == PINNED_BINDING_CID
    assert binding["operator_blocking_task"]["status"] == "typed_blocked"
    assert tuple(binding["escalation_order"]) == ESCALATION_ORDER
    assert refuse_pack_cid_remint(PINNED_PACK_CID) == PINNED_PACK_CID
    assert refuse_current_root_remint(PINNED_CURRENT_ROOT_CID) == PINNED_CURRENT_ROOT_CID
    assert refuse_route_cid_remint(PINNED_ROUTE_CID) == PINNED_ROUTE_CID
    assert refuse_patch_cid_remint(PINNED_PATCH_CID) == PINNED_PATCH_CID
    assert refuse_run_cid_remint(PINNED_RUN_CID) == PINNED_RUN_CID
    with pytest.raises(KitStaleRejectionError, match="remints"):
        refuse_pack_cid_remint(
            "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
    with pytest.raises(KitStaleRejectionError, match="cannot complete"):
        refuse_model_completion("frontier_model")
    with pytest.raises(KitStaleRejectionError, match="history"):
        refuse_history_mutation(mutated=True)
    with pytest.raises(KitStaleRejectionError, match="live durable"):
        refuse_live_storage(stored=True)


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_stale_rejection()
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.sibling_source_required is False
    assert verdict.live_application is False
    assert verdict.live_storage is False
    assert verdict.operator_blocking_task == OPERATOR_BLOCKING_TASK_ID
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("baguqeera")
    assert verdict.verdict_cid == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID
    assert verdict.pack_cid == PINNED_PACK_CID
    assert verdict.binding_cid == PINNED_BINDING_CID
    assert verdict.patch_cid == PINNED_PATCH_CID
    assert verdict.route_cid == PINNED_ROUTE_CID
    assert verdict.current_root_cid == PINNED_CURRENT_ROOT_CID
    assert verdict.run_cid == PINNED_RUN_CID
    assert verdict.blockers == ()
    section = pcpr_069_receipt_promotion(verdict)
    assert section["promotion_status"] == "rnd_non_promoted"
    assert section["closed_release_outcome"] is None
    assert section["release_claim"] is False
    assert section["verdict_cid"] == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID


def test_static_probes_show_declared_binding_constraints() -> None:
    probes = {item.probe_id: item for item in current_head_static_probes()}
    assert probes["binding_files_match_generator"].present is True
    assert probes["pyproject_stale_rejection_table"].present is True
    assert probes["owner_pack_cid_matches_pin"].present is True
    assert probes["kit_current_root_bound_not_minted"].present is True
    assert probes["delta_owned_by_accelerate"].present is True
    assert probes["delta_not_stored_as_live_bytes"].present is True
    assert probes["model_assertion_cannot_complete_work"].present is True
    assert probes["sibling_import_observed"].present is False
    assert probes["datasets_identity_reminted"].present is False
    assert probes["kit_identity_reminted"].present is False
    assert probes["live_application"].evidence_kind == "unavailable"
    assert probes["live_storage"].evidence_kind == "unavailable"
    for probe in probes.values():
        assert probe.live is False
        assert probe.simulated_represented_as_live is False


def test_committed_files_match_generator() -> None:
    verified = verify_stale_rejection_files()
    assert verified["ok"] is True
    pyproject = (_PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'interface = "KitStaleRejectionAndPlanDeltaBinding@1"' in pyproject


def test_simulated_live_probe_is_rejected() -> None:
    dummy = "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    with pytest.raises(KitStaleRejectionError, match="simulated"):
        qualify_stale_rejection(
            (
                OutcomeProbe(
                    probe_id="bogus",
                    present=False,
                    evidence_kind="simulated",
                    live=False,
                    simulated_represented_as_live=True,
                    reason="must fail",
                ),
            ),
            pack_cid=dummy,
            binding_cid=dummy,
            patch_cid=dummy,
            route_cid=dummy,
            current_root_cid=dummy,
            run_cid=dummy,
            objective_cid=dummy,
            idea_digest_cid=dummy,
        )
    with pytest.raises(KitStaleRejectionError, match="measured_live"):
        qualify_stale_rejection(
            (
                OutcomeProbe(
                    probe_id="bogus",
                    present=True,
                    evidence_kind="measured",
                    live=True,
                    simulated_represented_as_live=False,
                    reason="must fail",
                ),
            ),
            pack_cid=dummy,
            binding_cid=dummy,
            patch_cid=dummy,
            route_cid=dummy,
            current_root_cid=dummy,
            run_cid=dummy,
            objective_cid=dummy,
            idea_digest_cid=dummy,
        )

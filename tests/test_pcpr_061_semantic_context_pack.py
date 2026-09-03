"""PCPR-061: Kit binding to the Datasets semantic ContextPack."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.assurance.semantic_context_pack import (
    CLOSED_RELEASE_OUTCOMES,
    CURRENT_HEAD_NON_PROMOTION_VERDICT_CID,
    HERMETIC_CANDIDATE_SUITES,
    INTERFACE,
    OPERATOR_BLOCKING_TASK_ID,
    OBJECTIVE_KIND,
    OutcomeProbe,
    PCPR_061_GOAL_ID,
    PCPR_061_TASK_ID,
    PINNED_BINDING_CID,
    PINNED_IDEA_DIGEST,
    PINNED_OBJECTIVE_CID,
    PINNED_PACK_CID,
    SCHEMA,
    SEALED_PATH,
    SEALED_PYTHON,
    KitSemanticContextPackError,
    current_head_static_probes,
    pcpr_061_receipt_promotion,
    qualify_current_head_semantic_context_pack,
    qualify_semantic_context_pack,
    refuse_pack_cid_remint,
    render_declared_binding,
    verify_semantic_context_pack_files,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_061_requirements() -> None:
    assert PCPR_061_TASK_ID == "PCPR-061"
    assert PCPR_061_GOAL_ID == "PCPR-G700"
    assert INTERFACE == "KitSemanticContextPackBinding@1"
    assert SCHEMA == "ipfs_kit_py/assurance/semantic-context-pack-binding@1"
    assert OBJECTIVE_KIND == "declared_semantic_context_pack_binding"
    assert OPERATOR_BLOCKING_TASK_ID == (
        "pcpr-061-operator-live-context-pack-admission"
    )
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_061_semantic_context_pack.py"
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
    assert binding["storage"]["stored"] is False
    assert binding["storage"]["current_root_published"] is False
    assert binding["duckdb_or_quack_state_written"] is False
    assert binding["lock_cid"] == "baguqeerawsekbbbt5ccctjt4tydzeahfkahsatb6q5x7k6cy4inrii5lhqmq"
    assert binding["objective_cid"] == PINNED_OBJECTIVE_CID
    assert binding["idea_digest"] == PINNED_IDEA_DIGEST
    assert binding["context_pack"]["pack_cid"] == PINNED_PACK_CID
    assert binding["binding_cid"] == PINNED_BINDING_CID
    assert binding["operator_blocking_task"]["status"] == "typed_blocked"
    assert refuse_pack_cid_remint(PINNED_PACK_CID) == PINNED_PACK_CID
    with pytest.raises(KitSemanticContextPackError, match="remints"):
        refuse_pack_cid_remint(
            "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_semantic_context_pack()
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.sibling_source_required is False
    assert verdict.live_objective_submission is False
    assert verdict.live_materialization is False
    assert verdict.live_storage is False
    assert verdict.operator_blocking_task == OPERATOR_BLOCKING_TASK_ID
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("baguqeera")
    assert verdict.verdict_cid == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID
    assert verdict.pack_cid == PINNED_PACK_CID
    assert verdict.binding_cid == PINNED_BINDING_CID
    assert verdict.blockers == ()
    section = pcpr_061_receipt_promotion(verdict)
    assert section["promotion_status"] == "rnd_non_promoted"
    assert section["closed_release_outcome"] is None
    assert section["release_claim"] is False
    assert section["verdict_cid"] == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID


def test_static_probes_show_declared_binding_constraints() -> None:
    probes = {item.probe_id: item for item in current_head_static_probes()}
    assert probes["binding_files_match_generator"].present is True
    assert probes["pyproject_semantic_context_pack_table"].present is True
    assert probes["owner_pack_cid_matches_pin"].present is True
    assert probes["storage_not_performed"].present is True
    assert probes["current_root_not_published"].present is True
    assert probes["current_root_published"].present is False
    assert probes["sibling_import_observed"].present is False
    assert probes["datasets_identity_reminted"].present is False
    assert probes["live_materialization"].evidence_kind == "unavailable"
    for probe in probes.values():
        assert probe.live is False
        assert probe.simulated_represented_as_live is False


def test_committed_files_match_generator() -> None:
    verified = verify_semantic_context_pack_files()
    assert verified["ok"] is True
    pyproject = (_PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'interface = "KitSemanticContextPackBinding@1"' in pyproject


def test_simulated_live_probe_is_rejected() -> None:
    with pytest.raises(KitSemanticContextPackError, match="simulated"):
        qualify_semantic_context_pack(
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
            pack_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            binding_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            objective_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            idea_digest_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
    with pytest.raises(KitSemanticContextPackError, match="measured_live"):
        qualify_semantic_context_pack(
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
            pack_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            binding_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            objective_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            idea_digest_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

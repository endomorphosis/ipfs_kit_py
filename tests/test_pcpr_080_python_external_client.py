"""PCPR-080: Kit binding to Accelerate Python external client."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.assurance.python_external_client import (
    CLOSED_RELEASE_OUTCOMES,
    CURRENT_HEAD_NON_PROMOTION_VERDICT_CID,
    ESCALATION_ORDER,
    HERMETIC_CANDIDATE_SUITES,
    INTERFACE,
    OPERATOR_BLOCKING_TASK_ID,
    OBJECTIVE_KIND,
    OutcomeProbe,
    PCPR_080_GOAL_ID,
    PCPR_080_TASK_ID,
    PINNED_BINDING_CID,
    PINNED_CHAIN_CID,
    PINNED_CURRENT_ROOT_CID,
    PINNED_IDEA_DIGEST,
    PINNED_OBJECTIVE_CID,
    PINNED_PACK_CID,
    SCHEMA,
    SEALED_PATH,
    SEALED_PYTHON,
    KitPythonExternalClientError,
    current_head_static_probes,
    pcpr_080_receipt_promotion,
    qualify_current_head_python_external_client,
    qualify_python_external_client,
    refuse_current_root_remint,
    refuse_database_edit,
    refuse_live_storage,
    refuse_memory_reconstruction,
    refuse_model_completion,
    refuse_pack_cid_remint,
    render_declared_binding,
    verify_python_external_client_files,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_080_requirements() -> None:
    assert PCPR_080_TASK_ID == "PCPR-080"
    assert PCPR_080_GOAL_ID == "PCPR-G800"
    assert INTERFACE == "KitPythonExternalClientBinding@1"
    assert SCHEMA == "ipfs_kit_py/assurance/python-external-client-binding@1"
    assert OBJECTIVE_KIND == "declared_python_external_client_binding"
    assert OPERATOR_BLOCKING_TASK_ID == "pcpr-080-operator-live-python-external-client"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_080_python_external_client.py"
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
    assert binding["storage"]["survives_client"] is True
    assert binding["storage"]["reconstructed_from"] == "disk"
    assert binding["storage"]["reconstructed_from_memory"] is False
    assert binding["storage"]["idempotent"] is True
    assert binding["route"]["executed"] is True
    assert binding["route"]["executed_by"] == "ipfs_accelerate_py"
    assert binding["bounded_patch"]["produced"] is True
    chain = binding["final_receipt_chain"]
    assert chain["kind"] == "final_proof_carrying_receipt_chain"
    assert chain["classified_by"] == "ipfs_accelerate_py"
    assert chain["stored"] is False
    assert chain["live"] is False
    client = binding["python_external_client"]
    assert client["kind"] == "python_external_client_demonstration"
    assert client["classified_by"] == "ipfs_accelerate_py"
    assert client["stored"] is False
    assert client["live"] is False
    assert client["stale_rejected"] is True
    assert client["survives_client"] is True
    assert client["idempotent"] is True
    assert client["history_mutated"] is False
    assert binding["duckdb_or_quack_state_written"] is False
    assert binding["objective_cid"] == PINNED_OBJECTIVE_CID
    assert binding["idea_digest"] == PINNED_IDEA_DIGEST
    assert binding["context_pack"]["pack_cid"] == PINNED_PACK_CID
    assert binding["storage"]["current_root_cid"] == PINNED_CURRENT_ROOT_CID
    assert binding["final_receipt_chain"]["chain_cid"] == PINNED_CHAIN_CID
    assert binding["binding_cid"] == PINNED_BINDING_CID
    assert binding["operator_blocking_task"]["status"] == "typed_blocked"
    assert tuple(binding["escalation_order"]) == ESCALATION_ORDER
    assert refuse_pack_cid_remint(PINNED_PACK_CID) == PINNED_PACK_CID
    assert refuse_current_root_remint(PINNED_CURRENT_ROOT_CID) == PINNED_CURRENT_ROOT_CID
    with pytest.raises(KitPythonExternalClientError, match="remints"):
        refuse_pack_cid_remint(
            "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
    with pytest.raises(KitPythonExternalClientError, match="cannot complete"):
        refuse_model_completion("frontier_model")
    with pytest.raises(KitPythonExternalClientError, match="DuckDB"):
        refuse_database_edit(edited=True)
    with pytest.raises(KitPythonExternalClientError, match="memory"):
        refuse_memory_reconstruction(from_memory=True)
    with pytest.raises(KitPythonExternalClientError, match="live durable"):
        refuse_live_storage(stored=True)


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_python_external_client()
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.live_application is False
    assert verdict.live_storage is False
    assert verdict.live_client is False
    assert verdict.operator_blocking_task == OPERATOR_BLOCKING_TASK_ID
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.verdict_cid == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID
    assert verdict.pack_cid == PINNED_PACK_CID
    assert verdict.binding_cid == PINNED_BINDING_CID
    assert verdict.chain_cid == PINNED_CHAIN_CID
    assert verdict.blockers == ()
    section = pcpr_080_receipt_promotion(verdict)
    assert section["promotion_status"] == "rnd_non_promoted"
    assert section["closed_release_outcome"] is None


def test_static_probes_show_declared_binding_constraints() -> None:
    probes = {item.probe_id: item for item in current_head_static_probes()}
    assert probes["binding_files_match_generator"].present is True
    assert probes["pyproject_python_external_client_table"].present is True
    assert probes["owner_pack_cid_matches_pin"].present is True
    assert probes["kit_current_root_bound_not_minted"].present is True
    assert probes["client_owned_by_accelerate"].present is True
    assert probes["current_root_survives_client_from_disk"].present is True
    assert probes["client_not_stored_as_live_bytes"].present is True
    assert probes["idempotent_current_root"].present is True
    assert probes["datasets_identity_reminted"].present is False
    assert probes["kit_identity_reminted"].present is False
    assert probes["chain_identity_reminted"].present is False
    assert probes["memory_reconstruction_accepted"].present is False
    assert probes["live_application"].evidence_kind == "unavailable"
    assert probes["live_client"].evidence_kind == "unavailable"
    for probe in probes.values():
        assert probe.live is False
        assert probe.simulated_represented_as_live is False


def test_committed_files_match_generator() -> None:
    verified = verify_python_external_client_files()
    assert verified["ok"] is True
    assert verified["binding_cid"] == PINNED_BINDING_CID
    pyproject = (_PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'interface = "KitPythonExternalClientBinding@1"' in pyproject


def test_simulated_live_probe_is_rejected() -> None:
    dummy = "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    with pytest.raises(KitPythonExternalClientError, match="simulated"):
        qualify_python_external_client(
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
            current_root_cid=dummy,
            chain_cid=dummy,
            objective_cid=dummy,
            idea_digest_cid=dummy,
        )
    with pytest.raises(KitPythonExternalClientError, match="measured_live"):
        qualify_python_external_client(
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
            current_root_cid=dummy,
            chain_cid=dummy,
            objective_cid=dummy,
            idea_digest_cid=dummy,
        )

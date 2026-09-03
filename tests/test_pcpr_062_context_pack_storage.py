"""PCPR-062: Kit persist and publish of the current ContextPack root."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.assurance.context_pack_storage import (
    CLOSED_RELEASE_OUTCOMES,
    CURRENT_HEAD_NON_PROMOTION_VERDICT_CID,
    GENESIS_PARENT,
    HERMETIC_CANDIDATE_SUITES,
    HermeticContextPackRootStore,
    INTERFACE,
    OPERATOR_BLOCKING_TASK_ID,
    OBJECTIVE_KIND,
    OutcomeProbe,
    PCPR_062_GOAL_ID,
    PCPR_062_TASK_ID,
    PINNED_BYTES_CID,
    PINNED_CURRENT_ROOT_CID,
    PINNED_DOCUMENT_CID,
    PINNED_IDEA_DIGEST,
    PINNED_OBJECTIVE_CID,
    PINNED_PACK_CID,
    SCHEMA,
    SEALED_PATH,
    SEALED_PYTHON,
    KitContextPackStorageError,
    canonical_pack_bytes,
    current_head_static_probes,
    pcpr_062_receipt_promotion,
    persist_and_publish_current_root,
    qualify_context_pack_storage,
    qualify_current_head_context_pack_storage,
    refuse_current_root_remint,
    refuse_pack_cid_remint,
    render_declared_root,
    verify_context_pack_storage_files,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_062_requirements() -> None:
    assert PCPR_062_TASK_ID == "PCPR-062"
    assert PCPR_062_GOAL_ID == "PCPR-G700"
    assert INTERFACE == "KitContextPackStorage@1"
    assert SCHEMA == "ipfs_kit_py/assurance/context-pack-storage@1"
    assert OBJECTIVE_KIND == "declared_context_pack_root"
    assert OPERATOR_BLOCKING_TASK_ID == "pcpr-062-operator-live-context-pack-root"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_062_context_pack_storage.py"
    )
    assert SEALED_PATH == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
    assert SEALED_PYTHON == "/usr/bin/python3.12"
    document = render_declared_root()
    assert document["applied"] is False
    assert document["live"] is False
    assert document["release_claim"] is False
    assert document["closed_release_outcome"] is None
    assert document["context_pack"]["constructed"] is True
    assert document["context_pack"]["constructed_by"] == "ipfs_datasets_py"
    assert document["context_pack"]["reminted"] is False
    assert document["storage"]["stored"] is True
    assert document["storage"]["live"] is False
    assert document["storage"]["current_root_published"] is True
    assert document["current_root"]["live"] is False
    assert document["current_root"]["cas"] is True
    assert document["execution"]["performed"] is False
    assert document["duckdb_or_quack_state_written"] is False
    assert document["lock_cid"] == "baguqeerawsekbbbt5ccctjt4tydzeahfkahsatb6q5x7k6cy4inrii5lhqmq"
    assert document["objective_cid"] == PINNED_OBJECTIVE_CID
    assert document["idea_digest"] == PINNED_IDEA_DIGEST
    assert document["context_pack"]["pack_cid"] == PINNED_PACK_CID
    assert document["storage"]["bytes_cid"] == PINNED_BYTES_CID
    assert document["current_root"]["current_cid"] == PINNED_CURRENT_ROOT_CID
    assert document["document_cid"] == PINNED_DOCUMENT_CID
    assert document["operator_blocking_task"]["status"] == "typed_blocked"
    assert refuse_pack_cid_remint(PINNED_PACK_CID) == PINNED_PACK_CID
    assert refuse_current_root_remint(PINNED_CURRENT_ROOT_CID) == PINNED_CURRENT_ROOT_CID
    with pytest.raises(KitContextPackStorageError, match="remints"):
        refuse_pack_cid_remint(
            "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_context_pack_storage()
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.sibling_source_required is False
    assert verdict.live_storage is False
    assert verdict.live_storage_evidence_kind == "unavailable"
    assert verdict.live_current_root is False
    assert verdict.live_ipfs is False
    assert verdict.operator_blocking_task == OPERATOR_BLOCKING_TASK_ID
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("baguqeera")
    assert verdict.verdict_cid == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID
    assert verdict.pack_cid == PINNED_PACK_CID
    assert verdict.bytes_cid == PINNED_BYTES_CID
    assert verdict.current_root_cid == PINNED_CURRENT_ROOT_CID
    assert verdict.document_cid == PINNED_DOCUMENT_CID
    assert verdict.blockers == ()
    section = pcpr_062_receipt_promotion(verdict)
    assert section["promotion_status"] == "rnd_non_promoted"
    assert section["closed_release_outcome"] is None
    assert section["release_claim"] is False
    assert section["verdict_cid"] == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID


def test_static_probes_show_declared_storage_constraints() -> None:
    probes = {item.probe_id: item for item in current_head_static_probes()}
    assert probes["root_files_match_generator"].present is True
    assert probes["pyproject_context_pack_storage_table"].present is True
    assert probes["owner_pack_cid_matches_pin"].present is True
    assert probes["exact_bytes_verified"].present is True
    assert probes["hermetic_bytes_stored"].present is True
    assert probes["hermetic_current_root_published"].present is True
    assert probes["restart_reopen_verified"].present is True
    assert probes["stale_parent_rejected"].present is True
    assert probes["sibling_import_observed"].present is False
    assert probes["datasets_identity_reminted"].present is False
    assert probes["live_storage"].evidence_kind == "unavailable"
    assert probes["live_current_root"].evidence_kind == "unavailable"
    for probe in probes.values():
        assert probe.live is False
        assert probe.simulated_represented_as_live is False


def test_hermetic_cas_restart_and_stale_parent(tmp_path: Path) -> None:
    result = persist_and_publish_current_root(tmp_path / "root")
    assert result["stored"] is True
    assert result["current_root_published"] is True
    assert result["live"] is False
    assert result["bytes_cid"] == PINNED_BYTES_CID
    assert result["restart_verified"] is True
    assert result["stale_parent_rejected"] is True
    assert result["current_root"]["generation"] == 1
    assert result["current_root"]["current_cid"] == PINNED_CURRENT_ROOT_CID
    store = HermeticContextPackRootStore.reopen(tmp_path / "root")
    recovered = store.get(PINNED_CURRENT_ROOT_CID)
    assert recovered == canonical_pack_bytes()
    with pytest.raises(KitContextPackStorageError, match="stale parent"):
        store.compare_and_swap(GENESIS_PARENT, recovered)
    store.close()


def test_committed_files_match_generator() -> None:
    verified = verify_context_pack_storage_files()
    assert verified["ok"] is True
    pyproject = (_PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'interface = "KitContextPackStorage@1"' in pyproject


def test_simulated_live_probe_is_rejected() -> None:
    with pytest.raises(KitContextPackStorageError, match="simulated"):
        qualify_context_pack_storage(
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
            bytes_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            current_root_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            document_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            objective_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            idea_digest_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
    with pytest.raises(KitContextPackStorageError, match="measured_live"):
        qualify_context_pack_storage(
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
            bytes_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            current_root_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            document_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            objective_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            idea_digest_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

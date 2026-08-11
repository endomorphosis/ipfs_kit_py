"""Structural reopen-cost regressions for durable semantic-state roots."""

from __future__ import annotations

from pathlib import Path

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)


def _artifact(label: str) -> dict[str, str]:
    return {"schema": "datasets/semantic-state@1", "label": label}


def _publish(root: Path) -> tuple[str, str]:
    first, second = _artifact("one"), _artifact("two")
    first_cid, second_cid = cid_for_artifact(first), cid_for_artifact(second)
    with DurableCoordinationStore(root) as store:
        store.put(first, expected_cid=first_cid)
        store.put(second, expected_cid=second_cid)
        store.compare_and_swap_root(
            "semantic/reopen", expected_revision=0, expected_root_cid=None,
            new_root_cid=first_cid, operation_id="one",
        )
        store.compare_and_swap_root(
            "semantic/reopen", expected_revision=1, expected_root_cid=first_cid,
            new_root_cid=second_cid, operation_id="two",
        )
    return first_cid, second_cid


def test_healthy_reopen_verifies_without_root_index_rebuild_mutations(tmp_path: Path) -> None:
    root = tmp_path / "healthy"
    _, second_cid = _publish(root)

    with DurableCoordinationStore(root) as reopened:
        assert reopened.current_root("semantic/reopen")["root_cid"] == second_cid
        assert reopened.root_recovery_metrics() == {
            "root_index_verifications": 1,
            "root_index_rebuild_mutations": 0,
        }


def test_orphan_transition_evidence_reconstructs_root_indexes(tmp_path: Path) -> None:
    root = tmp_path / "orphan"
    _, second_cid = _publish(root)
    with DurableCoordinationStore(root) as store:
        store._connection.execute("DELETE FROM state_roots")
        store._connection.execute("DELETE FROM state_root_transitions")
        store._connection.commit()

    with DurableCoordinationStore(root) as reopened:
        assert reopened.current_root("semantic/reopen")["root_cid"] == second_cid
        metrics = reopened.root_recovery_metrics()
    assert metrics["root_index_verifications"] == 2
    assert metrics["root_index_rebuild_mutations"] == 3

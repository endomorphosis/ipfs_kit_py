from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    STATE_ROOT_TRANSITION_SCHEMA,
    cid_for_artifact,
)
from ipfs_kit_py.mcp_server.mcplusplus.state_root_contracts import RootUpdateStatus


def _artifact(label: str) -> dict[str, object]:
    return {"schema": "semantic-state@1", "label": label}


def _stored(store: DurableCoordinationStore, label: str) -> str:
    artifact = _artifact(label)
    return store.put(artifact, expected_cid=cid_for_artifact(artifact), replicate=False)["cid"]


def test_root_cas_publishes_verified_transition_and_replays_idempotently(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        successor = _stored(store, "one")
        assert store.current_state_root("semantic/example").revision == 0

        result = store.compare_and_swap_state_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="publish-1",
        )
        assert result.status is RootUpdateStatus.UPDATED
        assert result.before.revision == 0
        assert result.after.root_cid == successor
        assert result.after.revision == 1
        assert result.transition_cid == result.after.transition_cid
        transition = store.get(result.transition_cid)
        assert transition["schema"] == STATE_ROOT_TRANSITION_SCHEMA
        assert transition["expected_revision"] == 0
        assert transition["successor_revision"] == 1

        replay = store.compare_and_swap_state_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="publish-1",
        )
        assert replay.status is RootUpdateStatus.UNCHANGED
        assert replay.before == result.after == replay.after
        assert store.status()["counts"]["root_transitions"] == 1


def test_missing_or_corrupt_successor_never_becomes_current(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        missing = cid_for_artifact(_artifact("missing"))
        with pytest.raises(ArtifactNotFound):
            store.compare_and_swap_state_root(
                "semantic/example", expected_revision=0, expected_root_cid=None,
                new_root_cid=missing, operation_id="missing-1",
            )
        assert store.current_state_root("semantic/example").revision == 0

        corrupt = _stored(store, "corrupt")
        store._block_path(corrupt).write_bytes(b"not the declared artifact")
        with pytest.raises(ArtifactIntegrityError):
            store.compare_and_swap_state_root(
                "semantic/example", expected_revision=0, expected_root_cid=None,
                new_root_cid=corrupt, operation_id="corrupt-1",
            )
        assert store.current_state_root("semantic/example").revision == 0


def test_stale_cid_or_revision_cannot_overwrite_current_root(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        first, second = _stored(store, "first"), _stored(store, "second")
        accepted = store.compare_and_swap_state_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="first-1",
        )
        stale = store.compare_and_swap_state_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=second, operation_id="second-1",
        )
        assert accepted.status is RootUpdateStatus.UPDATED
        assert stale.status is RootUpdateStatus.CONFLICT
        assert stale.after == accepted.after


def test_root_indexes_rebuild_from_verified_transition_blocks(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as store:
        successor = _stored(store, "one")
        accepted = store.compare_and_swap_state_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="publish-1",
        )
    database = root / "coordination.sqlite3"
    database.unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with DurableCoordinationStore(root) as store:
        assert store.current_state_root("semantic/example") == accepted.after
        assert store.status()["counts"]["root_transitions"] == 1


def test_concurrent_writers_with_one_expectation_have_one_distinct_winner(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as setup:
        first, second = _stored(setup, "first"), _stored(setup, "second")

    def attempt(cid: str, operation_id: str) -> RootUpdateStatus:
        with DurableCoordinationStore(root) as store:
            return store.compare_and_swap_state_root(
                "semantic/example", expected_revision=0, expected_root_cid=None,
                new_root_cid=cid, operation_id=operation_id,
            ).status

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda args: attempt(*args), ((first, "first-1"), (second, "second-1"))))
    assert statuses.count(RootUpdateStatus.UPDATED) == 1
    assert statuses.count(RootUpdateStatus.CONFLICT) == 1
    with DurableCoordinationStore(root) as store:
        assert store.current_state_root("semantic/example").revision == 1

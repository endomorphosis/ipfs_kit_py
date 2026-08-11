"""Recovery assurance for immutable, revisioned coordination roots."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    ROOT_CAS_INTERRUPTION_POINTS,
    STATE_ROOT_TRANSITION_SCHEMA,
)


class InjectedInterruption(RuntimeError):
    """A recoverable stand-in for a process stopping at a durable boundary."""


def _successor(store: DurableCoordinationStore, label: str) -> str:
    return store.put({"schema": "example/state@1", "label": label})["cid"]


def _restart(root: Path) -> DurableCoordinationStore:
    return DurableCoordinationStore(root)


@pytest.mark.parametrize("boundary", ROOT_CAS_INTERRUPTION_POINTS)
def test_every_interruption_boundary_recovers_to_prior_or_unique_successor(
    tmp_path: Path, boundary: str
) -> None:
    root = tmp_path / boundary

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        successor = _successor(store, "successor")
        with pytest.raises(InjectedInterruption, match=boundary):
            store.compare_and_swap_state_root(
                "semantic/recovery", expected_revision=0, expected_root_cid=None,
                new_root_cid=successor, operation_id="interrupted-publish",
            )

    # An interruption before the transition is made durable leaves the prior
    # root.  Once its immutable block is fsynced, reconstruction makes the
    # sole transition visible even if the SQLite transaction did not commit.
    with _restart(root) as recovered:
        current = recovered.current_root("semantic/recovery")
        if boundary in {"before_transaction", "after_expectation_verification"}:
            assert current["root_cid"] is None
            assert current["revision"] == 0
        else:
            assert current["root_cid"] == successor
            assert current["revision"] == 1

        replay = recovered.compare_and_swap_root(
            "semantic/recovery", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="interrupted-publish",
        )
        expected_status = "updated" if boundary in {"before_transaction", "after_expectation_verification"} else "unchanged"
        assert replay["status"] == expected_status
        assert recovered.current_root("semantic/recovery")["revision"] == 1


def test_reconstruction_rejects_ambiguous_successors_without_picking_a_winner(tmp_path: Path) -> None:
    root = tmp_path / "ambiguous"
    with DurableCoordinationStore(root) as store:
        first, second = _successor(store, "first"), _successor(store, "second")
        for operation_id, successor in (("fork-a", first), ("fork-b", second)):
            store.put({
                "schema": STATE_ROOT_TRANSITION_SCHEMA,
                "namespace": "semantic/fork",
                "operation_id": operation_id,
                "expected_root_cid": None,
                "expected_revision": 0,
                "new_root_cid": successor,
                "new_revision": 1,
                "created_at_ms": 1,
            })

    (root / "coordination.sqlite3").unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with pytest.raises(ArtifactIntegrityError, match="breaks its namespace chain"):
        _restart(root)


def test_corrupt_successor_fails_closed_on_reconstruction(tmp_path: Path) -> None:
    root = tmp_path / "corrupt-successor"
    with DurableCoordinationStore(root) as store:
        successor = _successor(store, "valid")
        store.compare_and_swap_root(
            "semantic/corrupt", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="publish",
        )
        transition = store.current_root("semantic/corrupt")["transition_cid"]
        assert transition is not None
        store._block_path(successor).write_bytes(b"tampered")

    (root / "coordination.sqlite3").unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with pytest.raises(ArtifactIntegrityError, match="corrupt blocks"):
        _restart(root)


def test_corrupt_transition_fails_closed_on_reconstruction(tmp_path: Path) -> None:
    root = tmp_path / "corrupt-transition"
    with DurableCoordinationStore(root) as store:
        successor = _successor(store, "valid")
        store.compare_and_swap_root(
            "semantic/corrupt", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="publish",
        )
        transition = store.current_root("semantic/corrupt")["transition_cid"]
        assert transition is not None
        store._block_path(transition).write_bytes(b"tampered")

    (root / "coordination.sqlite3").unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with pytest.raises(ArtifactIntegrityError, match="corrupt blocks"):
        _restart(root)


@pytest.mark.parametrize("tamper", ("indexed-field", "broken-predecessor-fork"))
def test_live_indexed_chain_rejects_field_mismatches_and_forks(tmp_path: Path, tamper: str) -> None:
    with DurableCoordinationStore(tmp_path / tamper) as store:
        first, second, fork = (_successor(store, label) for label in ("one", "two", "fork"))
        store.compare_and_swap_root(
            "semantic/live", expected_revision=0, expected_root_cid=None, new_root_cid=first, operation_id="one"
        )
        store.compare_and_swap_root(
            "semantic/live", expected_revision=1, expected_root_cid=first, new_root_cid=second, operation_id="two"
        )
        if tamper == "indexed-field":
            store._connection.execute(
                "UPDATE state_root_transitions SET operation_id='not-the-block' "
                "WHERE namespace='semantic/live' AND new_revision=2"
            )
        else:
            transition = {
                "schema": STATE_ROOT_TRANSITION_SCHEMA,
                "namespace": "semantic/live",
                "operation_id": "fork",
                "expected_root_cid": None,
                "expected_revision": 0,
                "new_root_cid": fork,
                "new_revision": 1,
                "created_at_ms": 0,
            }
            transition_cid = store.put(transition)["cid"]
            store._connection.execute(
                """INSERT INTO state_root_transitions
                   (transition_cid,namespace,operation_id,expected_root_cid,expected_revision,
                    new_root_cid,new_revision,created_at_ms) VALUES(?,?,?,?,?,?,?,?)""",
                (transition_cid, "semantic/live", "fork", None, 0, fork, 1, 0),
            )
        store._connection.commit()

        with pytest.raises(ArtifactIntegrityError):
            store.current_root("semantic/live")

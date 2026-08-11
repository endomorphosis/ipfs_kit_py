"""Focused concurrency and integrity tests for coordination-store root CAS."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    STATE_ROOT_TRANSITION_SCHEMA,
)


def _overlong_version(cid: str) -> str:
    wire = base64.b32decode(cid[1:].upper() + "=" * ((8 - len(cid[1:]) % 8) % 8))
    return "b" + base64.b32encode(bytes((wire[0] | 0x80, 0)) + wire[1:]).decode("ascii").lower().rstrip("=")


def _successor(store: DurableCoordinationStore, name: str) -> str:
    return store.put({"schema": "example/state@1", "name": name})["cid"]


def test_root_starts_empty_and_publishes_a_verified_revisioned_successor(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        successor = _successor(store, "one")
        assert store.current_state_root("semantic/worker-1") == {
            "namespace": "semantic/worker-1", "root_cid": None, "revision": 0, "transition_cid": None,
        }

        result = store.compare_and_swap_state_root(
            "semantic/worker-1", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="publish-1",
        )

        assert result["status"] == "updated"
        assert result["before"]["revision"] == 0
        assert result["after"]["revision"] == 1
        assert result["after"]["root_cid"] == successor
        assert store.current_root("semantic/worker-1") == result["after"]
        transition = store.get(result["transition_cid"])
        assert transition["schema"] == STATE_ROOT_TRANSITION_SCHEMA
        assert transition["new_root_cid"] == successor
        assert store.root_transitions("semantic/worker-1")[0]["operation_id"] == "publish-1"


def test_missing_or_corrupt_successor_never_becomes_current(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        existing = _successor(store, "existing")
        missing = existing[:-2] + ("a" if existing[-2] != "a" else "b") + existing[-1]
        with pytest.raises(ArtifactNotFound):
            store.compare_and_swap_state_root(
                "semantic", expected_revision=0, expected_root_cid=None,
                new_root_cid=missing, operation_id="missing-1",
            )
        store._block_path(existing).write_bytes(b"corrupt")
        with pytest.raises(ArtifactIntegrityError):
            store.compare_and_swap_state_root(
                "semantic", expected_revision=0, expected_root_cid=None,
                new_root_cid=existing, operation_id="corrupt-1",
            )
        assert store.current_state_root("semantic")["revision"] == 0


def test_store_rejects_the_same_noncanonical_cid_aliases_as_root_contracts(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        successor = _successor(store, "canonical")
        alias = _overlong_version(successor)
        with pytest.raises(ValueError):
            store.get_bytes(alias)
        with pytest.raises(ValueError):
            store.has(alias)
        with pytest.raises(ValueError):
            store.compare_and_swap_state_root(
                "semantic", expected_revision=0, expected_root_cid=None,
                new_root_cid=alias, operation_id="alias-1",
            )
        with pytest.raises(ValueError):
            store.put({"schema": "example/state@1", "name": "expected"}, expected_cid=alias)


def test_stale_cid_or_revision_cannot_overwrite_and_replay_does_not_increment(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        first, second, third = (_successor(store, name) for name in ("one", "two", "three"))
        updated = store.compare_and_swap_state_root(
            "semantic", expected_revision=0, expected_root_cid=None, new_root_cid=first, operation_id="op-1"
        )
        replay = store.compare_and_swap_state_root(
            "semantic", expected_revision=0, expected_root_cid=None, new_root_cid=first, operation_id="op-1"
        )
        stale_revision = store.compare_and_swap_state_root(
            "semantic", expected_revision=0, expected_root_cid=None, new_root_cid=second, operation_id="op-2"
        )
        stale_cid = store.compare_and_swap_state_root(
            "semantic", expected_revision=1, expected_root_cid=second, new_root_cid=third, operation_id="op-3"
        )

        assert updated["status"] == "updated"
        assert replay["status"] == "unchanged"
        assert stale_revision["status"] == stale_cid["status"] == "conflict"
        assert store.current_state_root("semantic") == updated["after"]
        assert len(store.root_transitions("semantic")) == 1


def test_two_independent_store_connections_have_one_distinct_winner(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as setup:
        one, two = _successor(setup, "one"), _successor(setup, "two")

    def attempt(cid: str, operation_id: str) -> dict[str, object]:
        with DurableCoordinationStore(root) as store:
            return store.compare_and_swap_state_root(
                "semantic", expected_revision=0, expected_root_cid=None,
                new_root_cid=cid, operation_id=operation_id,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: attempt(*args), ((one, "writer-1"), (two, "writer-2"))))

    assert sorted(result["status"] for result in results) == ["conflict", "updated"]
    with DurableCoordinationStore(root) as store:
        current = store.current_state_root("semantic")
        assert current["revision"] == 1
        assert current["root_cid"] in (one, two)
        assert len(store.root_transitions("semantic")) == 1


def test_root_indexes_rebuild_from_the_immutable_transition(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as store:
        successor = _successor(store, "rebuild")
        expected = store.compare_and_swap_state_root(
            "semantic", expected_revision=0, expected_root_cid=None,
            new_root_cid=successor, operation_id="rebuild-1",
        )["after"]

    database = root / "coordination.sqlite3"
    database.unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with DurableCoordinationStore(root) as store:
        assert store.current_state_root("semantic") == expected
        assert len(store.root_transitions("semantic")) == 1


def test_live_root_and_cas_refuse_a_corrupt_current_block_without_mutation(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        first, second = (_successor(store, name) for name in ("one", "two"))
        store.compare_and_swap_root(
            "semantic", expected_revision=0, expected_root_cid=None, new_root_cid=first, operation_id="one"
        )
        store._block_path(first).write_bytes(b"tampered")
        indexed_before = store._connection.execute(
            "SELECT root_cid,revision,transition_cid FROM state_roots WHERE namespace='semantic'"
        ).fetchone()
        transitions_before = len(store.root_transitions("semantic"))

        with pytest.raises(ArtifactIntegrityError, match="immutable evidence"):
            store.current_root("semantic")
        with pytest.raises(ArtifactIntegrityError, match="immutable evidence"):
            store.compare_and_swap_root(
                "semantic", expected_revision=1, expected_root_cid=first, new_root_cid=second, operation_id="two"
            )

        assert tuple(store._connection.execute(
            "SELECT root_cid,revision,transition_cid FROM state_roots WHERE namespace='semantic'"
        ).fetchone()) == tuple(indexed_before)
        assert len(store.root_transitions("semantic")) == transitions_before


@pytest.mark.parametrize("corruption", ("swapped-current-transition", "tampered-root-revision", "raw-transition"))
def test_live_root_rejects_tampered_sqlite_or_raw_transition_evidence(
    tmp_path: Path, corruption: str
) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        first, second = (_successor(store, name) for name in ("one", "two"))
        store.compare_and_swap_root(
            "semantic", expected_revision=0, expected_root_cid=None, new_root_cid=first, operation_id="one"
        )
        store.compare_and_swap_root(
            "semantic", expected_revision=1, expected_root_cid=first, new_root_cid=second, operation_id="two"
        )
        rows = store.root_transitions("semantic")
        if corruption == "swapped-current-transition":
            store._connection.execute(
                "UPDATE state_roots SET transition_cid=? WHERE namespace='semantic'", (rows[0]["transition_cid"],)
            )
        elif corruption == "tampered-root-revision":
            store._connection.execute("UPDATE state_roots SET revision=99 WHERE namespace='semantic'")
        else:
            transition = store.get(rows[-1]["transition_cid"])
            raw_cid = store.put(transition, codec="raw")["cid"]
            store._connection.execute(
                "UPDATE state_root_transitions SET transition_cid=? WHERE transition_cid=?",
                (raw_cid, rows[-1]["transition_cid"]),
            )
            store._connection.execute(
                "UPDATE state_roots SET transition_cid=? WHERE namespace='semantic'", (raw_cid,)
            )
        store._connection.commit()

        with pytest.raises(ArtifactIntegrityError):
            store.current_root("semantic")

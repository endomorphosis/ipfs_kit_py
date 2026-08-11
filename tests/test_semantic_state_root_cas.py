"""Concurrency and integrity coverage for durable state-root publication."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
)
from ipfs_kit_py.mcp_server.mcplusplus.state_root_contracts import RootUpdateStatus


def _artifact(store: DurableCoordinationStore, value: str) -> str:
    return store.put({"schema": "example/state@1", "value": value})["cid"]


def test_root_starts_at_zero_and_advances_once_per_accepted_transition(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        first = _artifact(store, "first")
        assert store.current_root("semantic/example").revision == 0

        accepted = store.compare_and_swap_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="first-write",
        )
        assert accepted.status is RootUpdateStatus.UPDATED
        assert accepted.after.revision == 1

        replay = store.compare_and_swap_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="first-write",
        )
        assert replay.status is RootUpdateStatus.UNCHANGED
        assert store.current_root("semantic/example") == accepted.after


def test_missing_or_corrupt_successor_cannot_become_current(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        cid = _artifact(store, "candidate")
        store._block_path(cid).unlink()
        with pytest.raises(ArtifactNotFound):
            store.compare_and_swap_root(
                "semantic/example", expected_revision=0, expected_root_cid=None,
                new_root_cid=cid, operation_id="missing",
            )
        assert store.current_root("semantic/example").revision == 0

        cid = _artifact(store, "corrupt")
        store._block_path(cid).write_bytes(b"bad")
        with pytest.raises(ArtifactIntegrityError):
            store.compare_and_swap_root(
                "semantic/example", expected_revision=0, expected_root_cid=None,
                new_root_cid=cid, operation_id="corrupt",
            )
        assert store.current_root("semantic/example").revision == 0


def test_stale_revision_or_root_never_overwrites(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "store") as store:
        first, second = _artifact(store, "first"), _artifact(store, "second")
        store.compare_and_swap_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="first",
        )
        stale = store.compare_and_swap_root(
            "semantic/example", expected_revision=0, expected_root_cid=None,
            new_root_cid=second, operation_id="stale",
        )
        assert stale.status is RootUpdateStatus.CONFLICT
        assert store.current_root("semantic/example").root_cid == first


def test_concurrent_distinct_successors_have_one_winner(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as seed:
        left, right = _artifact(seed, "left"), _artifact(seed, "right")

    gate = threading.Barrier(2)
    statuses: list[RootUpdateStatus] = []
    errors: list[BaseException] = []

    def writer(cid: str, operation: str) -> None:
        try:
            with DurableCoordinationStore(root) as store:
                gate.wait()
                statuses.append(store.compare_and_swap_root(
                    "semantic/example", expected_revision=0, expected_root_cid=None,
                    new_root_cid=cid, operation_id=operation,
                ).status)
        except BaseException as exc:  # propagate failures after both threads finish
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(left, "left")), threading.Thread(target=writer, args=(right, "right"))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert sorted(status.value for status in statuses) == ["conflict", "updated"]
    with DurableCoordinationStore(root) as store:
        assert store.current_root("semantic/example").revision == 1


def test_concurrent_identical_successors_do_not_advance_twice(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as seed:
        successor = _artifact(seed, "shared")

    gate = threading.Barrier(2)
    statuses: list[RootUpdateStatus] = []

    def writer(operation: str) -> None:
        with DurableCoordinationStore(root) as store:
            gate.wait()
            statuses.append(store.compare_and_swap_root(
                "semantic/example", expected_revision=0, expected_root_cid=None,
                new_root_cid=successor, operation_id=operation,
            ).status)

    threads = [threading.Thread(target=writer, args=("one",)), threading.Thread(target=writer, args=("two",))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(status.value for status in statuses) == ["unchanged", "updated"]
    with DurableCoordinationStore(root) as store:
        assert store.current_root("semantic/example").revision == 1

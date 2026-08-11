"""Recovery assurance for immutable, revisioned coordination roots."""

from __future__ import annotations

from pathlib import Path
import threading

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    ROOT_CAS_INTERRUPTION_POINTS,
    STATE_ROOT_TRANSITION_SCHEMA,
)
from ipfs_kit_py.mcp_server.mcplusplus.state_root_adapter import DurableStateRootAdapter


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


def test_raw_transition_evidence_fails_before_rebuild_mutates_indexes(tmp_path: Path) -> None:
    """A raw CID may be generic storage, never a root-transition wire CID."""

    with DurableCoordinationStore(tmp_path / "raw-transition") as store:
        successor = _successor(store, "successor")
        transition = {
            "schema": STATE_ROOT_TRANSITION_SCHEMA,
            "namespace": "semantic/raw-transition",
            "operation_id": "raw-transition",
            "expected_root_cid": None,
            "expected_revision": 0,
            "new_root_cid": successor,
            "new_revision": 1,
            "created_at_ms": 0,
        }
        raw_transition = store.put(transition, codec="raw", replicate=False)["cid"]
        artifacts_before = list(store._connection.execute("SELECT * FROM artifacts ORDER BY cid"))
        transitions_before = store.root_transitions()
        roots_before = list(store._connection.execute("SELECT * FROM state_roots ORDER BY namespace"))
        metrics_before = store.root_recovery_metrics()
        with pytest.raises(ArtifactIntegrityError, match="non-dag-json"):
            store.recover(rebuild=True)
        assert list(store._connection.execute("SELECT * FROM artifacts ORDER BY cid")) == artifacts_before
        assert store.root_transitions() == transitions_before
        assert list(store._connection.execute("SELECT * FROM state_roots ORDER BY namespace")) == roots_before
        assert store.root_recovery_metrics() == metrics_before
        assert raw_transition


def test_semantic_recovery_projects_raw_reconstructed_root_as_closed_corruption(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "raw-root") as store:
        raw = b"generic raw root"
        raw_cid = store.put(
            {"schema": "example/state@1", "label": "raw"}, codec="raw", replicate=False
        )["cid"]
        store.compare_and_swap_root(
            "semantic/raw-root", expected_revision=0, expected_root_cid=None,
            new_root_cid=raw_cid, operation_id="generic-raw-root",
        )
        report = DurableStateRootAdapter(store).recover_roots()
    assert report.reconstructed_roots == ()
    assert report.errors and report.errors[0]["code"] == "corrupt"


def test_explicit_rebuild_counts_committed_root_deletes_and_inserts(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "metrics") as store:
        first, second = _successor(store, "one"), _successor(store, "two")
        store.compare_and_swap_root(
            "semantic/metrics", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="one",
        )
        store.compare_and_swap_root(
            "semantic/metrics", expected_revision=1, expected_root_cid=first,
            new_root_cid=second, operation_id="two",
        )
        store.recover(rebuild=True)
        assert store.root_recovery_metrics()["root_index_rebuild_mutations"] == 6


def test_recovery_scan_before_cas_cannot_replace_the_later_committed_root(tmp_path: Path) -> None:
    """The recovery scan itself is fenced, not merely its index writes."""

    root = tmp_path / "scan-before-cas"
    with DurableCoordinationStore(root) as store:
        first, second = _successor(store, "one"), _successor(store, "two")
        store.compare_and_swap_root(
            "semantic/race", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="one",
        )

    with _restart(root) as recovering, _restart(root) as publisher:
        scanned = threading.Event()
        release_recovery = threading.Event()
        published = threading.Event()
        failures: list[BaseException] = []
        original_iter = recovering._iter_local_blocks

        def paused_scan():
            for item in original_iter():
                yield item
                if not scanned.is_set():
                    scanned.set()
                    assert release_recovery.wait(5)

        recovering._iter_local_blocks = paused_scan  # type: ignore[method-assign]

        def rebuild() -> None:
            try:
                recovering.recover(rebuild=True)
            except BaseException as exc:  # pragma: no cover - reported below
                failures.append(exc)

        def publish() -> None:
            try:
                publisher.compare_and_swap_root(
                    "semantic/race", expected_revision=1, expected_root_cid=first,
                    new_root_cid=second, operation_id="two",
                )
                published.set()
            except BaseException as exc:  # pragma: no cover - reported below
                failures.append(exc)

        recovery_thread = threading.Thread(target=rebuild)
        recovery_thread.start()
        assert scanned.wait(5)
        publisher_thread = threading.Thread(target=publish)
        publisher_thread.start()
        # The CAS cannot commit while recovery owns the SQLite writer epoch.
        assert not published.wait(0.1)
        release_recovery.set()
        recovery_thread.join(5)
        publisher_thread.join(5)
        assert not recovery_thread.is_alive()
        assert not publisher_thread.is_alive()
        assert not failures
        assert recovering.current_root("semantic/race")["revision"] == 2
        assert publisher.current_root("semantic/race")["root_cid"] == second


def test_recovery_scan_during_cas_waits_for_its_committed_transition(tmp_path: Path) -> None:
    root = tmp_path / "scan-during-cas"
    transition_written = threading.Event()
    release_cas = threading.Event()

    def pause_after_transition(point: str) -> None:
        if point == "after_transition_block_fsync":
            transition_written.set()
            assert release_cas.wait(5)

    with DurableCoordinationStore(root) as store:
        first, second = _successor(store, "one"), _successor(store, "two")
        store.compare_and_swap_root(
            "semantic/race", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="one",
        )

    with DurableCoordinationStore(root, crash_injector=pause_after_transition) as publisher, _restart(root) as recovering:
        scanned = threading.Event()
        failures: list[BaseException] = []
        original_iter = recovering._iter_local_blocks

        def observed_scan():
            scanned.set()
            yield from original_iter()

        recovering._iter_local_blocks = observed_scan  # type: ignore[method-assign]

        def publish() -> None:
            try:
                publisher.compare_and_swap_root(
                    "semantic/race", expected_revision=1, expected_root_cid=first,
                    new_root_cid=second, operation_id="two",
                )
            except BaseException as exc:  # pragma: no cover - reported below
                failures.append(exc)

        def rebuild() -> None:
            try:
                recovering.recover(rebuild=True)
            except BaseException as exc:  # pragma: no cover - reported below
                failures.append(exc)

        publisher_thread = threading.Thread(target=publish)
        publisher_thread.start()
        assert transition_written.wait(5)
        recovery_thread = threading.Thread(target=rebuild)
        recovery_thread.start()
        # The immutable transition is visible on disk but uncommitted; recovery
        # must wait on the publisher's writer fence before it can enumerate it.
        assert not scanned.wait(0.1)
        release_cas.set()
        publisher_thread.join(5)
        recovery_thread.join(5)
        assert not publisher_thread.is_alive()
        assert not recovery_thread.is_alive()
        assert not failures
        assert recovering.current_root("semantic/race")["revision"] == 2


def test_rebuild_after_a_committed_cas_retains_every_committed_transition(tmp_path: Path) -> None:
    root = tmp_path / "commit-before-rebuild"
    with DurableCoordinationStore(root) as store:
        first, second = _successor(store, "one"), _successor(store, "two")
        store.compare_and_swap_root(
            "semantic/race", expected_revision=0, expected_root_cid=None,
            new_root_cid=first, operation_id="one",
        )
        store.compare_and_swap_root(
            "semantic/race", expected_revision=1, expected_root_cid=first,
            new_root_cid=second, operation_id="two",
        )
        store.recover(rebuild=True)
        assert store.current_root("semantic/race")["root_cid"] == second
        assert [row["new_revision"] for row in store.root_transitions("semantic/race")] == [1, 2]


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

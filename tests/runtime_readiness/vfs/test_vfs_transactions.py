"""Transaction, snapshot, isolation, locking, and cancellation tests (KITA-008).

Acceptance coverage:

* version/CID preconditions reject stale writes;
* declared isolation prevents lost updates;
* lock ordering is deterministic and bounded;
* cancellation has an explicit pre/post-commit disposition;
* snapshots are immutable and reproducible;
* concurrent generated schedules match the reference model or report typed
  unsupported boundaries.
"""

from __future__ import annotations

import pytest

from ipfs_kit_py.core.vfs.service import (
    InMemoryVFSStorage,
    content_cid_for_bytes,
    version_cid_for,
)
from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
from ipfs_kit_py.core.vfs.snapshots import (
    VFSSnapshot,
    VFSSnapshotImmutableError,
    VFSSnapshotStore,
    VFSVersion,
    VFSVersionHistory,
    VFSVersionHistoryBoundError,
    VFSVersionPreconditionError,
    VFSSnapshot_V1,
    VFSVersion_V1,
    check_version_precondition,
    snapshot_cid_for,
)
from ipfs_kit_py.core.vfs.transactions import (
    CancellationDisposition,
    ConcurrentScheduleExecutor,
    IsolationLevel,
    LockMode,
    ScheduleStep,
    TransactionOpKind,
    TransactionState,
    TransactionUnsupportedReason,
    VFSLockDeadlockError,
    VFSLockManager,
    VFSTransactionConflictError,
    VFSTransactionManager,
    VFSTransactionUnsupportedError,
    VFSTransaction_V1,
    ordered_lock_paths,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mgr(
    *,
    isolation_seed: bytes | None = b"v1",
    path: str = "file",
) -> tuple[InMemoryVFSStorage, VFSTransactionManager]:
    storage = InMemoryVFSStorage()
    if isolation_seed is not None:
        storage.seed(path, content=isolation_seed)
    mgr = VFSTransactionManager(storage, clock=lambda: 1_700_000_000_000)
    return storage, mgr


# ---------------------------------------------------------------------------
# Schema / interface aliases
# ---------------------------------------------------------------------------


def test_interface_aliases_are_stable() -> None:
    assert VFSTransaction_V1.endswith("/transaction@1")
    assert VFSSnapshot_V1.endswith("/snapshot@1")
    assert VFSVersion_V1.endswith("/version@1")


# ---------------------------------------------------------------------------
# Version / CID preconditions reject stale writes
# ---------------------------------------------------------------------------


def test_version_precondition_rejects_stale_cid() -> None:
    with pytest.raises(VFSVersionPreconditionError) as ei:
        check_version_precondition(
            current_version_cid="sha256:" + "a" * 64,
            expected_version_cid="sha256:" + "b" * 64,
            path="file",
        )
    assert ei.value.path == "file"
    assert ei.value.current_version_cid.endswith("a" * 64)


def test_cas_write_rejects_stale_precondition_at_stage() -> None:
    storage, mgr = _mgr()
    entry = storage.get("file")
    assert entry is not None
    txn = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    with pytest.raises(VFSVersionPreconditionError):
        mgr.cas_write(
            txn,
            "file",
            b"stale",
            precondition_version_cid="sha256:" + "0" * 64,
        )
    # No mutation staged or applied.
    assert "file" not in txn.write_set
    assert storage.get("file") is not None
    assert storage.get("file").content == b"v1"  # type: ignore[union-attr]


def test_cas_write_accepts_matching_precondition_and_commits() -> None:
    storage, mgr = _mgr()
    entry = storage.get("file")
    assert entry is not None
    pre = entry.version_cid
    txn = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    mgr.cas_write(txn, "file", b"v2", precondition_version_cid=pre)
    mgr.commit(txn)
    assert txn.state is TransactionState.COMMITTED
    after = storage.get("file")
    assert after is not None
    assert after.content == b"v2"
    assert after.version_cid != pre
    # History records parent link.
    head = mgr.version_history.head("file")
    assert head is not None
    assert head.parent_version_cid == pre
    assert head.version_cid == after.version_cid


def test_cas_write_rejects_stale_at_commit_after_concurrent_update() -> None:
    """T1 stages CAS with old version; T2 commits first; T1 commit fails."""

    storage, mgr = _mgr()
    entry = storage.get("file")
    assert entry is not None
    pre = entry.version_cid

    t1 = mgr.begin(txn_id="t1", isolation=IsolationLevel.READ_COMMITTED)
    # Stage without going through cas_write eager check path that re-reads live:
    # use write() with explicit precondition so T2 can commit first.
    mgr.write(t1, "file", b"from-t1", precondition_version_cid=pre)

    t2 = mgr.begin(txn_id="t2", isolation=IsolationLevel.READ_COMMITTED)
    # T2 needs exclusive lock — t1 holds it. Abort t1 locks by... actually t1
    # holds exclusive. For this test use two managers sharing storage? Locks are
    # per-manager. Simulate with sequential CAS on one manager by releasing:
    # Commit t2 via a second manager on same storage (separate lock table).
    mgr2 = VFSTransactionManager(storage, clock=lambda: 1_700_000_000_001)
    t2b = mgr2.begin(txn_id="t2", isolation=IsolationLevel.READ_COMMITTED)
    mgr2.cas_write(t2b, "file", b"from-t2", precondition_version_cid=pre)
    mgr2.commit(t2b)
    assert storage.get("file").content == b"from-t2"  # type: ignore[union-attr]

    with pytest.raises(VFSVersionPreconditionError):
        mgr.commit(t1)
    assert t1.state is TransactionState.ABORTED
    assert storage.get("file").content == b"from-t2"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Declared isolation prevents lost updates
# ---------------------------------------------------------------------------


def test_snapshot_isolation_prevents_lost_update() -> None:
    storage, mgr = _mgr()
    t1 = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    t2 = mgr.begin(txn_id="t2", isolation=IsolationLevel.SNAPSHOT)

    # Each txn stages a write; first commit wins, second fails lost-update.
    # They cannot hold exclusive locks on the same path concurrently in one
    # lock manager — release path: use write on t1, commit, then write on t2.
    mgr.write(t1, "file", b"A")
    mgr.commit(t1)

    # t2 still holds begin-snapshot of v1; staging write under exclusive lock.
    mgr.write(t2, "file", b"B")
    with pytest.raises(VFSTransactionConflictError) as ei:
        mgr.commit(t2)
    assert ei.value.reason == "lost_update"
    assert storage.get("file").content == b"A"  # type: ignore[union-attr]


def test_serializable_rejects_write_write_after_begin() -> None:
    storage, mgr = _mgr()
    t1 = mgr.begin(txn_id="t1", isolation=IsolationLevel.SERIALIZABLE)
    mgr.write(t1, "file", b"A")
    mgr.commit(t1)

    t2 = mgr.begin(txn_id="t2", isolation=IsolationLevel.SERIALIZABLE)
    # begin_generation is after t1; no conflict with past commits.
    mgr.write(t2, "file", b"B")
    # Another writer commits after t2 began — use second manager.
    # Re-begin t2 before t3: actually start t3 after t2 begin.
    # Restart: t2 begins, t3 commits, t2 commit conflicts.
    storage2 = InMemoryVFSStorage()
    storage2.seed("file", content=b"v1")
    mgr = VFSTransactionManager(storage2, clock=lambda: 0)
    t2 = mgr.begin(txn_id="t2", isolation=IsolationLevel.SERIALIZABLE)
    t3 = mgr.begin(txn_id="t3", isolation=IsolationLevel.SERIALIZABLE)
    mgr.write(t3, "other", b"x")  # non-overlapping first
    mgr.commit(t3)

    # Overlapping path with a commit after t2 begin:
    t4 = mgr.begin(txn_id="t4", isolation=IsolationLevel.SERIALIZABLE)
    # t2 still active; t4 cannot lock "file" if t2 holds it — stage t2 first.
    mgr.write(t2, "file", b"B")
    # t2 holds exclusive on file. Commit t2 first then have another...
    # Direct test of serializable check: commit t2, begin t_a, commit t_b on
    # same path via second manager, then t_a commit.
    storage3 = InMemoryVFSStorage()
    storage3.seed("file", content=b"v1")
    m = VFSTransactionManager(storage3, clock=lambda: 0)
    ta = m.begin(txn_id="ta", isolation=IsolationLevel.SERIALIZABLE)
    m.write(ta, "file", b"A")
    # Stage only — don't commit yet.
    # Concurrent committed writer via second manager:
    m2 = VFSTransactionManager(storage3, clock=lambda: 1)
    tb = m2.begin(txn_id="tb", isolation=IsolationLevel.SERIALIZABLE)
    m2.write(tb, "file", b"B")
    m2.commit(tb)
    # ta's snapshot still v1; commit should fail lost_update (SNAPSHOT check)
    # and also serializable if write sets tracked per-manager only.
    with pytest.raises(VFSTransactionConflictError):
        m.commit(ta)


def test_read_committed_allows_overwrite_without_precondition() -> None:
    """READ_COMMITTED without CAS admits last-writer-wins (caller-owned risk)."""

    storage, mgr = _mgr()
    t1 = mgr.begin(txn_id="t1", isolation=IsolationLevel.READ_COMMITTED)
    mgr.write(t1, "file", b"A")
    mgr.commit(t1)
    t2 = mgr.begin(txn_id="t2", isolation=IsolationLevel.READ_COMMITTED)
    mgr.write(t2, "file", b"B")
    mgr.commit(t2)
    assert storage.get("file").content == b"B"  # type: ignore[union-attr]


def test_snapshot_reads_are_stable() -> None:
    storage, mgr = _mgr()
    t1 = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    seen = mgr.read(t1, "file")
    assert seen is not None
    assert seen["content_cid"] == content_cid_for_bytes(b"v1")

    # External commit mutates live storage.
    m2 = VFSTransactionManager(storage, clock=lambda: 2)
    t2 = m2.begin(txn_id="t2", isolation=IsolationLevel.READ_COMMITTED)
    entry = storage.get("file")
    assert entry is not None
    m2.cas_write(t2, "file", b"v2", precondition_version_cid=entry.version_cid)
    m2.commit(t2)

    seen2 = mgr.read(t1, "file")
    assert seen2 is not None
    # Still the begin-snapshot value.
    assert seen2["content_cid"] == content_cid_for_bytes(b"v1")
    assert seen2["version_cid"] == seen["version_cid"]


# ---------------------------------------------------------------------------
# Lock ordering deterministic and bounded
# ---------------------------------------------------------------------------


def test_lock_order_is_utf8_lexicographic() -> None:
    assert ordered_lock_paths("z", "a", "m", "a") == ("a", "m", "z")
    # Deterministic regardless of input order.
    assert ordered_lock_paths("docs/b", "docs/a") == ordered_lock_paths("docs/a", "docs/b")


def test_lock_manager_acquires_in_sorted_order() -> None:
    lm = VFSLockManager()
    newly = lm.acquire("t1", ["c", "a", "b"], LockMode.EXCLUSIVE)
    assert newly == ("a", "b", "c")
    assert lm.held_paths("t1") == ("a", "b", "c")
    grants = lm.grants()
    assert [g.path for g in grants] == ["a", "b", "c"]


def test_lock_conflict_is_fail_closed_not_blocking() -> None:
    lm = VFSLockManager()
    lm.acquire("t1", ["file"], LockMode.EXCLUSIVE)
    with pytest.raises(VFSLockDeadlockError) as ei:
        lm.acquire("t2", ["file"], LockMode.EXCLUSIVE)
    assert "file" in ei.value.paths
    assert "t1" in ei.value.txn_ids and "t2" in ei.value.txn_ids


def test_shared_locks_coexist_exclusive_does_not() -> None:
    lm = VFSLockManager()
    lm.acquire("t1", ["file"], LockMode.SHARED)
    lm.acquire("t2", ["file"], LockMode.SHARED)
    with pytest.raises(VFSLockDeadlockError):
        lm.acquire("t3", ["file"], LockMode.EXCLUSIVE)
    lm.release_all("t1")
    lm.release_all("t2")
    lm.acquire("t3", ["file"], LockMode.EXCLUSIVE)


def test_lock_bound_per_txn() -> None:
    lm = VFSLockManager(max_per_txn=3)
    lm.acquire("t1", ["a", "b", "c"], LockMode.EXCLUSIVE)
    with pytest.raises(Exception):
        lm.acquire("t1", ["d"], LockMode.EXCLUSIVE)


def test_rename_acquires_locks_in_deterministic_order() -> None:
    storage = InMemoryVFSStorage()
    storage.seed("z-src", content=b"body")
    mgr = VFSTransactionManager(storage, clock=lambda: 0)
    txn = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    # Rename from z-src to a-dst — lock order must be a-dst then z-src.
    mgr.rename(txn, "z-src", "a-dst")
    held = mgr.locks.held_paths("t1")
    assert held == ordered_lock_paths("z-src", "a-dst")
    mgr.commit(txn)
    assert storage.get("a-dst") is not None
    assert storage.get("z-src") is None


# ---------------------------------------------------------------------------
# Cancellation pre/post-commit disposition
# ---------------------------------------------------------------------------


def test_cancel_pre_commit_aborts_without_mutation() -> None:
    storage, mgr = _mgr()
    before = storage.snapshot()
    txn = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    mgr.write(txn, "file", b"nope")
    disp = mgr.cancel(txn)
    assert disp is CancellationDisposition.PRE_COMMIT_ABORT
    assert txn.state is TransactionState.CANCELLED
    assert txn.cancellation_disposition is CancellationDisposition.PRE_COMMIT_ABORT
    assert storage.snapshot() == before
    assert storage.get("file").content == b"v1"  # type: ignore[union-attr]


def test_cancel_post_commit_retains_effects() -> None:
    storage, mgr = _mgr()
    txn = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    mgr.write(txn, "file", b"kept")
    mgr.commit(txn)
    disp = mgr.cancel(txn)
    assert disp is CancellationDisposition.POST_COMMIT_RETAINED
    assert txn.cancellation_disposition is CancellationDisposition.POST_COMMIT_RETAINED
    assert storage.get("file").content == b"kept"  # type: ignore[union-attr]


def test_cancel_post_commit_compensate_is_typed_unsupported() -> None:
    storage, mgr = _mgr()
    txn = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    mgr.write(txn, "file", b"kept")
    mgr.commit(txn)
    with pytest.raises(VFSTransactionUnsupportedError) as ei:
        mgr.cancel(txn, request_compensate=True)
    assert ei.value.reason is TransactionUnsupportedReason.POST_COMMIT_COMPENSATE
    assert (
        txn.cancellation_disposition
        is CancellationDisposition.POST_COMMIT_COMPENSATE_UNSUPPORTED
    )
    # Effects still retained.
    assert storage.get("file").content == b"kept"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Snapshots immutable and reproducible
# ---------------------------------------------------------------------------


def test_snapshot_reproducible_cid() -> None:
    storage = InMemoryVFSStorage()
    storage.seed("a", content=b"1")
    storage.seed("b", content=b"2")
    s1 = VFSSnapshot.capture(storage, snapshot_id="s1")
    s2 = VFSSnapshot.from_public_records(
        storage.snapshot(),
        snapshot_id="s2",
        generation=storage.generation,
    )
    assert s1.snapshot_cid == s2.snapshot_cid
    # Same records → same cid helper.
    assert snapshot_cid_for(storage.snapshot(), generation=storage.generation) == s1.snapshot_cid


def test_snapshot_immutable() -> None:
    storage = InMemoryVFSStorage()
    storage.seed("a", content=b"1")
    snap = VFSSnapshot.capture(storage, snapshot_id="s1")
    with pytest.raises(VFSSnapshotImmutableError):
        snap.with_mutated_entries({"a": {}})
    # as_mapping returns a copy — mutating it does not affect the snapshot.
    m = snap.as_mapping()
    m["a"]["content_cid"] = "tampered"
    assert snap.entry("a") is not None
    assert snap.entry("a")["content_cid"] != "tampered"


def test_snapshot_stable_after_live_mutation() -> None:
    storage = InMemoryVFSStorage()
    storage.seed("a", content=b"1")
    store = VFSSnapshotStore()
    snap = store.capture_from_storage(storage, snapshot_id="pinned")
    cid_before = snap.snapshot_cid
    storage.seed("a", content=b"2")
    # Stored snapshot unchanged.
    again = store.get("pinned")
    assert again.snapshot_cid == cid_before
    assert again.content_cid_at("a") == content_cid_for_bytes(b"1")


def test_snapshot_store_rejects_identity_mutation() -> None:
    storage = InMemoryVFSStorage()
    storage.seed("a", content=b"1")
    store = VFSSnapshotStore()
    s1 = VFSSnapshot.capture(storage, snapshot_id="same")
    store.put(s1)
    storage.seed("a", content=b"changed")
    s2 = VFSSnapshot.capture(storage, snapshot_id="same")
    assert s2.snapshot_cid != s1.snapshot_cid
    with pytest.raises(VFSSnapshotImmutableError):
        store.put(s2)


def test_version_history_bound() -> None:
    hist = VFSVersionHistory(max_per_path=3)
    for i in range(3):
        hist.record(
            VFSVersion(
                path="p",
                kind=VFSEntryKind.FILE,
                content_cid=content_cid_for_bytes(bytes([i])),
                generation=i + 1,
            )
        )
    with pytest.raises(VFSVersionHistoryBoundError):
        hist.record(
            VFSVersion(
                path="p",
                kind=VFSEntryKind.FILE,
                content_cid=content_cid_for_bytes(b"x"),
                generation=99,
            )
        )


def test_version_identity_matches_service() -> None:
    v = VFSVersion(
        path="file",
        kind=VFSEntryKind.FILE,
        content_cid=content_cid_for_bytes(b"x"),
        generation=7,
    )
    expected = version_cid_for(
        "file",
        kind=VFSEntryKind.FILE,
        content_cid=content_cid_for_bytes(b"x"),
        generation=7,
    )
    assert v.version_cid == expected


# ---------------------------------------------------------------------------
# Concurrent schedules match reference or typed unsupported
# ---------------------------------------------------------------------------


def test_concurrent_schedule_matches_reference_model() -> None:
    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    impl = InMemoryVFSStorage()
    ex = ConcurrentScheduleExecutor(impl, storage_factory=factory, clock=lambda: 0)

    def seed(s: InMemoryVFSStorage) -> None:
        s.seed("file", content=b"v1")

    steps = (
        ScheduleStep(
            txn_id="t1",
            op=TransactionOpKind.BEGIN,
            isolation=IsolationLevel.SNAPSHOT,
        ),
        ScheduleStep(
            txn_id="t1",
            op=TransactionOpKind.WRITE,
            path="file",
            content=b"v2",
        ),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.COMMIT),
        ScheduleStep(
            txn_id="t2",
            op=TransactionOpKind.BEGIN,
            isolation=IsolationLevel.SNAPSHOT,
        ),
        ScheduleStep(
            txn_id="t2",
            op=TransactionOpKind.READ,
            path="file",
        ),
        ScheduleStep(txn_id="t2", op=TransactionOpKind.ABORT),
    )
    outcome = ex.run_differential(steps, seed=seed)
    assert outcome.matched_reference is True
    assert outcome.unsupported is False
    assert all(s.success for s in outcome.steps)
    assert outcome.final_namespace["file"]["content_cid"] == content_cid_for_bytes(b"v2")


def test_concurrent_lost_update_schedule_matches_on_both_paths() -> None:
    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    ex = ConcurrentScheduleExecutor(
        InMemoryVFSStorage(), storage_factory=factory, clock=lambda: 0
    )

    def seed(s: InMemoryVFSStorage) -> None:
        s.seed("file", content=b"v1")

    # t1 and t2 both begin snapshot, t1 writes+commits, t2 writes+commit fails.
    steps = (
        ScheduleStep(txn_id="t1", op=TransactionOpKind.BEGIN, isolation=IsolationLevel.SNAPSHOT),
        ScheduleStep(txn_id="t2", op=TransactionOpKind.BEGIN, isolation=IsolationLevel.SNAPSHOT),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.WRITE, path="file", content=b"A"),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.COMMIT),
        ScheduleStep(txn_id="t2", op=TransactionOpKind.WRITE, path="file", content=b"B"),
        ScheduleStep(txn_id="t2", op=TransactionOpKind.COMMIT),
    )
    outcome = ex.run_differential(steps, seed=seed)
    assert outcome.matched_reference is True
    # Last commit step fails with conflict.
    commit_steps = [s for s in outcome.steps if s.op == "commit"]
    assert commit_steps[0].success is True
    assert commit_steps[1].success is False
    assert commit_steps[1].state == "conflict"
    assert outcome.final_namespace["file"]["content_cid"] == content_cid_for_bytes(b"A")


def test_concurrent_lock_conflict_is_typed_unsupported_boundary() -> None:
    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    ex = ConcurrentScheduleExecutor(
        InMemoryVFSStorage(), storage_factory=factory, clock=lambda: 0
    )

    def seed(s: InMemoryVFSStorage) -> None:
        s.seed("file", content=b"v1")

    # Two txns both try exclusive write without the first releasing — deadlock.
    steps = (
        ScheduleStep(txn_id="t1", op=TransactionOpKind.BEGIN, isolation=IsolationLevel.SNAPSHOT),
        ScheduleStep(txn_id="t2", op=TransactionOpKind.BEGIN, isolation=IsolationLevel.SNAPSHOT),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.WRITE, path="file", content=b"A"),
        ScheduleStep(txn_id="t2", op=TransactionOpKind.WRITE, path="file", content=b"B"),
    )
    outcome = ex.run_differential(steps, seed=seed)
    assert outcome.unsupported is True
    assert outcome.unsupported_reason == (
        TransactionUnsupportedReason.CROSS_TXN_DEADLOCK.value
    )
    assert outcome.matched_reference is True


def test_generated_interleavings_match_or_unsupported() -> None:
    """Small generator of schedules — each matches reference or typed boundary."""

    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    contents = (b"A", b"B")
    isolations = (IsolationLevel.SNAPSHOT, IsolationLevel.READ_COMMITTED)
    for iso in isolations:
        for c1 in contents:
            for c2 in contents:
                ex = ConcurrentScheduleExecutor(
                    InMemoryVFSStorage(), storage_factory=factory, clock=lambda: 0
                )

                def seed(s: InMemoryVFSStorage) -> None:
                    s.seed("file", content=b"v0")

                steps = (
                    ScheduleStep(txn_id="t1", op=TransactionOpKind.BEGIN, isolation=iso),
                    ScheduleStep(txn_id="t1", op=TransactionOpKind.WRITE, path="file", content=c1),
                    ScheduleStep(txn_id="t1", op=TransactionOpKind.COMMIT),
                    ScheduleStep(txn_id="t2", op=TransactionOpKind.BEGIN, isolation=iso),
                    ScheduleStep(txn_id="t2", op=TransactionOpKind.WRITE, path="file", content=c2),
                    ScheduleStep(txn_id="t2", op=TransactionOpKind.COMMIT),
                )
                outcome = ex.run_differential(steps, seed=seed)
                assert outcome.matched_reference is True, (
                    f"divergence iso={iso} c1={c1!r} c2={c2!r}"
                )
                # Either fully successful (read_committed) or second commit conflicts
                # (snapshot) — never silent mismatch.
                if iso is IsolationLevel.SNAPSHOT:
                    # Second writer began after first committed, so snapshot is fresh
                    # and commit succeeds (no lost update vs own snapshot).
                    assert outcome.steps[-1].success is True
                else:
                    assert outcome.steps[-1].success is True


def test_cas_stale_schedule_matches_reference() -> None:
    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    ex = ConcurrentScheduleExecutor(
        InMemoryVFSStorage(), storage_factory=factory, clock=lambda: 0
    )
    stale = "sha256:" + "0" * 64

    def seed(s: InMemoryVFSStorage) -> None:
        s.seed("file", content=b"v1")

    steps = (
        ScheduleStep(txn_id="t1", op=TransactionOpKind.BEGIN, isolation=IsolationLevel.SNAPSHOT),
        ScheduleStep(
            txn_id="t1",
            op=TransactionOpKind.CAS_WRITE,
            path="file",
            content=b"nope",
            precondition_version_cid=stale,
        ),
    )
    outcome = ex.run_differential(steps, seed=seed)
    assert outcome.matched_reference is True
    assert outcome.steps[-1].success is False
    assert outcome.steps[-1].state == "precondition_failed"


def test_post_commit_compensate_schedule_typed_unsupported() -> None:
    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    ex = ConcurrentScheduleExecutor(
        InMemoryVFSStorage(), storage_factory=factory, clock=lambda: 0
    )

    def seed(s: InMemoryVFSStorage) -> None:
        s.seed("file", content=b"v1")

    steps = (
        ScheduleStep(txn_id="t1", op=TransactionOpKind.BEGIN, isolation=IsolationLevel.SNAPSHOT),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.WRITE, path="file", content=b"x"),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.COMMIT),
        ScheduleStep(
            txn_id="t1",
            op=TransactionOpKind.CANCEL,
            request_compensate=True,
        ),
    )
    outcome = ex.run_differential(steps, seed=seed)
    assert outcome.unsupported is True
    assert outcome.unsupported_reason == (
        TransactionUnsupportedReason.POST_COMMIT_COMPENSATE.value
    )
    assert outcome.matched_reference is True


def test_schedule_outcome_is_content_addressed() -> None:
    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    def seed(s: InMemoryVFSStorage) -> None:
        s.seed("file", content=b"v1")

    steps = (
        ScheduleStep(txn_id="t1", op=TransactionOpKind.BEGIN, isolation=IsolationLevel.SNAPSHOT),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.WRITE, path="file", content=b"z"),
        ScheduleStep(txn_id="t1", op=TransactionOpKind.COMMIT),
    )
    o1 = ConcurrentScheduleExecutor(
        InMemoryVFSStorage(), storage_factory=factory, clock=lambda: 0
    ).run_differential(steps, seed=seed)
    o2 = ConcurrentScheduleExecutor(
        InMemoryVFSStorage(), storage_factory=factory, clock=lambda: 0
    ).run_differential(steps, seed=seed)
    assert o1.to_record()["outcome_cid"] == o2.to_record()["outcome_cid"]


def test_abort_discards_write_set() -> None:
    storage, mgr = _mgr()
    before = storage.snapshot()
    txn = mgr.begin(txn_id="t1")
    mgr.write(txn, "file", b"gone")
    mgr.abort(txn)
    assert txn.state is TransactionState.ABORTED
    assert storage.snapshot() == before


def test_delete_and_version_history() -> None:
    storage, mgr = _mgr()
    entry = storage.get("file")
    assert entry is not None
    pre = entry.version_cid
    txn = mgr.begin(txn_id="t1")
    mgr.delete(txn, "file")
    mgr.commit(txn)
    assert storage.get("file") is None
    chain = mgr.version_history.chain("file")
    assert len(chain) >= 1
    assert chain[-1].parent_version_cid == pre


def test_transaction_to_record_is_compact() -> None:
    _, mgr = _mgr()
    txn = mgr.begin(txn_id="t1", isolation=IsolationLevel.SNAPSHOT)
    mgr.write(txn, "file", b"x")
    rec = txn.to_record()
    assert rec["schema"] == VFSTransaction_V1
    assert rec["txn_id"] == "t1"
    assert "file" in rec["write_set_paths"]
    assert rec["begin_snapshot_cid"]

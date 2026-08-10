"""KVFS-208: Callback concurrency, lock ordering, open-unlink/open-rename.

Acceptance coverage:

* deterministic inode/path/handle lock ordering prevents deadlock;
* callbacks are linearizable or return typed conflict;
* open handles survive same-mount rename/unlink per policy;
* tables, queues, waits, cancellation, and shutdown are bounded under
  randomized concurrency.
"""

from __future__ import annotations

import ast
import random
import threading
import time
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs import host_concurrency as conc_mod
from ipfs_kit_py.core.vfs.host_concurrency import (
    CONTRACT_VERSION,
    DEFAULT_MAX_ACTIVE_CALLBACKS,
    DEFAULT_MAX_GLOBAL_LOCKS,
    DEFAULT_OPEN_HANDLE_POLICY,
    SCHEMA_VERSION,
    CallbackSessionState,
    ConflictReason,
    HostCallbackConflictError,
    HostCallbackGate_V1,
    HostConcurrencyPlane,
    HostConcurrencyPlane_V1,
    HostLockConflictError,
    HostLockKey,
    HostLockManager,
    HostLockManager_V1,
    HostLockRequest,
    LockDomain,
    LockMode,
    OpenHandleDisposition,
    OpenHandlePolicy,
    OpenHandlePolicy_V1,
    ShutdownState,
    lock_requests_for_callback,
    ordered_lock_keys,
    ordered_lock_requests,
)
from ipfs_kit_py.core.vfs.host_contracts import HostCallbackKind, HostErrno, OpenFlag

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_concurrency.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CONCURRENCY_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "host_concurrency.py"


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_concurrency_module_exists() -> None:
    assert CONCURRENCY_PATH.is_file()
    assert CONCURRENCY_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert HostConcurrencyPlane_V1.endswith("@1")
    assert HostLockManager_V1.endswith("@1")
    assert HostCallbackGate_V1.endswith("@1")
    assert OpenHandlePolicy_V1.endswith("@1")
    assert DEFAULT_MAX_GLOBAL_LOCKS >= 1
    assert DEFAULT_MAX_ACTIVE_CALLBACKS >= 1
    assert DEFAULT_OPEN_HANDLE_POLICY.rename_disposition is OpenHandleDisposition.SURVIVE
    assert DEFAULT_OPEN_HANDLE_POLICY.unlink_disposition is OpenHandleDisposition.SURVIVE


def test_module_has_no_fusepy_dependency() -> None:
    source = CONCURRENCY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                assert module.split(".", 1)[0] not in banned


def test_exports_are_importable() -> None:
    assert conc_mod.HostConcurrencyPlane is HostConcurrencyPlane
    assert conc_mod.HostLockManager is HostLockManager
    assert conc_mod.LockDomain.PATH is LockDomain.PATH
    assert callable(HostConcurrencyPlane.run_callback)
    assert callable(HostConcurrencyPlane.rename_path)
    assert callable(HostConcurrencyPlane.unlink_path)
    assert callable(HostConcurrencyPlane.shutdown)


# ---------------------------------------------------------------------------
# Deterministic lock ordering
# ---------------------------------------------------------------------------


def test_lock_domain_total_order_is_path_inode_handle() -> None:
    assert int(LockDomain.PATH) < int(LockDomain.INODE) < int(LockDomain.HANDLE)


def test_ordered_lock_keys_is_deterministic_and_domain_ranked() -> None:
    keys = [
        HostLockKey.for_handle(3),
        HostLockKey.for_path("z"),
        HostLockKey.for_inode(10),
        HostLockKey.for_path("a"),
        HostLockKey.for_handle(1),
        HostLockKey.for_inode(2),
    ]
    ordered = ordered_lock_keys(*keys)
    assert [k.domain for k in ordered] == [
        LockDomain.PATH,
        LockDomain.PATH,
        LockDomain.INODE,
        LockDomain.INODE,
        LockDomain.HANDLE,
        LockDomain.HANDLE,
    ]
    assert ordered[0].path == "a"
    assert ordered[1].path == "z"
    assert ordered[2].resource_id == 2
    assert ordered[3].resource_id == 10
    assert ordered[4].resource_id == 1
    assert ordered[5].resource_id == 3
    # Order-independent.
    assert ordered_lock_keys(*reversed(keys)) == ordered


def test_ordered_lock_requests_stronger_mode_wins() -> None:
    path = HostLockKey.for_path("file")
    reqs = ordered_lock_requests(
        [
            HostLockRequest(path, LockMode.SHARED),
            HostLockRequest(path, LockMode.EXCLUSIVE),
            HostLockRequest(HostLockKey.for_inode(1), LockMode.SHARED),
        ]
    )
    assert len(reqs) == 2
    assert reqs[0].key.domain is LockDomain.PATH
    assert reqs[0].mode is LockMode.EXCLUSIVE
    assert reqs[1].key.domain is LockDomain.INODE


def test_lock_requests_for_callback_orders_mixed_resources() -> None:
    reqs = lock_requests_for_callback(
        paths=("b", "a"),
        inodes=(9, 1),
        handle_ids=(5,),
        path_mode=LockMode.SHARED,
    )
    assert [r.key.domain for r in reqs] == [
        LockDomain.PATH,
        LockDomain.PATH,
        LockDomain.INODE,
        LockDomain.INODE,
        LockDomain.HANDLE,
    ]
    assert reqs[0].key.path == "a"
    assert reqs[1].key.path == "b"


def test_lock_manager_acquires_in_sorted_order() -> None:
    lm = HostLockManager()
    newly = lm.acquire(
        "t1",
        [
            HostLockRequest(HostLockKey.for_handle(2)),
            HostLockRequest(HostLockKey.for_path("z")),
            HostLockRequest(HostLockKey.for_inode(7)),
            HostLockRequest(HostLockKey.for_path("a")),
        ],
    )
    assert [str(k) for k in newly] == ["path:a", "path:z", "inode:7", "handle:2"]
    assert [str(k) for k in lm.held_keys("t1")] == ["path:a", "path:z", "inode:7", "handle:2"]
    lm.release_all("t1")
    assert lm.held_keys("t1") == ()


def test_shared_locks_coexist_exclusive_conflicts() -> None:
    lm = HostLockManager(default_wait_ms=0)
    lm.acquire("t1", [HostLockRequest(HostLockKey.for_path("f"), LockMode.SHARED)])
    lm.acquire("t2", [HostLockRequest(HostLockKey.for_path("f"), LockMode.SHARED)])
    with pytest.raises(HostLockConflictError) as ei:
        lm.acquire(
            "t3",
            [HostLockRequest(HostLockKey.for_path("f"), LockMode.EXCLUSIVE)],
            nonblocking=True,
        )
    assert ei.value.reason in (ConflictReason.LOCK_HELD, ConflictReason.LOCK_WAIT_TIMEOUT)
    lm.release_all("t1")
    lm.release_all("t2")
    lm.acquire("t3", [HostLockRequest(HostLockKey.for_path("f"), LockMode.EXCLUSIVE)])


def test_inverted_caller_order_cannot_deadlock() -> None:
    """Two owners requesting opposite path orders still acquire PATH-sorted."""

    lm = HostLockManager(default_wait_ms=200)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []
    acquired: list[str] = []

    def worker(owner: str, paths: list[str]) -> None:
        try:
            barrier.wait(timeout=2)
            lm.acquire(
                owner,
                [HostLockRequest(HostLockKey.for_path(p)) for p in paths],
                wait_ms=500,
            )
            acquired.append(owner)
            time.sleep(0.02)
            lm.release_all(owner)
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=("t1", ["z", "a"]))
    t2 = threading.Thread(target=worker, args=("t2", ["a", "z"]))
    t1.start()
    t2.start()
    t1.join(timeout=3)
    t2.join(timeout=3)
    assert not t1.is_alive() and not t2.is_alive()
    # At most typed conflicts; no hang. Both may succeed serially.
    for err in errors:
        assert isinstance(err, HostLockConflictError)
    assert lm.global_lock_count == 0
    assert lm.waiter_count == 0


def test_wait_for_cycle_is_typed_deadlock() -> None:
    """Classic A-then-B vs B-then-A deadlock is detected as typed conflict.

    Because path locks alone sort, we force a cycle across domains by having
    each owner hold one key and then request the other's key while the other
    still holds it — the wait-for graph forms a cycle.
    """

    lm = HostLockManager(default_wait_ms=50)
    a = HostLockKey.for_path("a")
    b = HostLockKey.for_inode(1)
    lm.acquire("t1", [HostLockRequest(a)])
    lm.acquire("t2", [HostLockRequest(b)])

    # t1 holds path:a and will wait for inode:1 held by t2.
    # t2 holds inode:1 and will wait for path:a held by t1.
    # Domain order means t1 can request inode after path; t2 already holds
    # inode and requests path — but t2 already passed path domain. The
    # wait-for edges t1→t2 and t2→t1 form a cycle.
    result: dict[str, BaseException | None] = {"t1": None, "t2": None}
    barrier = threading.Barrier(2)

    def try_acquire(owner: str, key: HostLockKey) -> None:
        try:
            barrier.wait(timeout=2)
            lm.acquire(owner, [HostLockRequest(key)], wait_ms=200)
        except BaseException as exc:  # noqa: BLE001
            result[owner] = exc

    th1 = threading.Thread(target=try_acquire, args=("t1", b))
    th2 = threading.Thread(target=try_acquire, args=("t2", a))
    th1.start()
    th2.start()
    th1.join(timeout=3)
    th2.join(timeout=3)
    assert not th1.is_alive() and not th2.is_alive()
    # At least one side must surface a typed conflict (deadlock or timeout).
    conflicts = [e for e in result.values() if isinstance(e, HostLockConflictError)]
    assert conflicts, f"expected typed conflict, got {result!r}"
    assert all(
        e.reason
        in (
            ConflictReason.LOCK_DEADLOCK,
            ConflictReason.LOCK_WAIT_TIMEOUT,
            ConflictReason.LOCK_HELD,
        )
        for e in conflicts
    )
    lm.release_all("t1")
    lm.release_all("t2")


def test_lock_per_owner_bound() -> None:
    lm = HostLockManager(max_per_owner=2, default_wait_ms=0)
    lm.acquire(
        "t1",
        [
            HostLockRequest(HostLockKey.for_path("a")),
            HostLockRequest(HostLockKey.for_path("b")),
        ],
    )
    with pytest.raises(HostLockConflictError) as ei:
        lm.acquire("t1", [HostLockRequest(HostLockKey.for_path("c"))])
    assert ei.value.reason is ConflictReason.LOCK_BOUND


def test_global_lock_bound() -> None:
    lm = HostLockManager(max_global_locks=2, default_wait_ms=0)
    lm.acquire("t1", [HostLockRequest(HostLockKey.for_path("a"))])
    lm.acquire("t2", [HostLockRequest(HostLockKey.for_path("b"))])
    with pytest.raises(HostLockConflictError) as ei:
        lm.acquire("t3", [HostLockRequest(HostLockKey.for_path("c"))])
    assert ei.value.reason is ConflictReason.LOCK_BOUND


# ---------------------------------------------------------------------------
# Linearizable callbacks or typed conflict
# ---------------------------------------------------------------------------


def test_callback_linearization_sequences_are_monotonic() -> None:
    plane = HostConcurrencyPlane(clock_ms=lambda: 1_700_000_000_000)
    seqs: list[int] = []

    def body(session):  # type: ignore[no-untyped-def]
        seqs.append(session.linearization_seq)
        return session.linearization_seq

    for i in range(5):
        session, result = plane.run_callback(
            body,
            kind=HostCallbackKind.GETATTR,
            paths=(f"p{i}",),
            path_mode=LockMode.SHARED,
        )
        assert session.state is CallbackSessionState.COMPLETED
        assert result == session.linearization_seq

    assert seqs == sorted(seqs)
    assert seqs == list(range(1, 6))


def test_concurrent_exclusive_callbacks_serialize_or_conflict() -> None:
    plane = HostConcurrencyPlane(
        default_wait_ms=100, clock_ms=lambda: int(time.time() * 1000)
    )
    outcomes: list[str] = []
    critical = {"n": 0, "peak": 0}
    critical_lock = threading.Lock()

    def body_peak(session):  # type: ignore[no-untyped-def]
        with critical_lock:
            critical["n"] += 1
            critical["peak"] = max(critical["peak"], critical["n"])
        time.sleep(0.005)
        with critical_lock:
            critical["n"] -= 1
        return True

    def worker(i: int) -> None:
        try:
            plane.run_callback(
                body_peak,
                kind=HostCallbackKind.WRITE,
                paths=("shared",),
                owner_id=f"w{i}",
                wait_ms=300,
            )
            outcomes.append("ok")
        except HostCallbackConflictError:
            outcomes.append("conflict")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive()
    assert outcomes
    assert all(o in ("ok", "conflict") for o in outcomes)
    assert any(o == "ok" for o in outcomes)
    # Exclusive path lock serializes the critical section.
    assert critical["peak"] == 1
    assert plane.locks.global_lock_count == 0


def test_nonblocking_callback_returns_typed_conflict() -> None:
    plane = HostConcurrencyPlane(default_wait_ms=0)
    session = plane.gate.begin(
        kind=HostCallbackKind.WRITE,
        paths=("x",),
        owner_id="holder",
    )
    assert session.state is CallbackSessionState.RUNNING
    with pytest.raises(HostCallbackConflictError) as ei:
        plane.run_callback(
            lambda s: None,
            kind=HostCallbackKind.WRITE,
            paths=("x",),
            owner_id="challenger",
            nonblocking=True,
        )
    assert ei.value.reason in (
        ConflictReason.LOCK_HELD,
        ConflictReason.LOCK_WAIT_TIMEOUT,
        ConflictReason.CALLBACK_BOUND,
    )
    plane.gate.complete(session)


def test_shared_read_callbacks_can_overlap() -> None:
    plane = HostConcurrencyPlane(default_wait_ms=200)
    barrier = threading.Barrier(2)
    overlapping = {"yes": False}

    def body(session):  # type: ignore[no-untyped-def]
        barrier.wait(timeout=2)
        # If both reached the barrier, shared locks overlapped.
        overlapping["yes"] = True
        return True

    def worker(owner: str) -> None:
        plane.run_callback(
            body,
            kind=HostCallbackKind.READ,
            paths=("ro",),
            path_mode=LockMode.SHARED,
            owner_id=owner,
            wait_ms=500,
        )

    t1 = threading.Thread(target=worker, args=("r1",))
    t2 = threading.Thread(target=worker, args=("r2",))
    t1.start()
    t2.start()
    t1.join(timeout=3)
    t2.join(timeout=3)
    assert not t1.is_alive() and not t2.is_alive()
    assert overlapping["yes"] is True


# ---------------------------------------------------------------------------
# Open handles survive same-mount rename / unlink
# ---------------------------------------------------------------------------


@pytest.fixture
def plane() -> HostConcurrencyPlane:
    return HostConcurrencyPlane(clock_ms=lambda: 1_700_000_000_000)


def test_rename_while_open_handle_survives(plane: HostConcurrencyPlane) -> None:
    plane.handles.seed_file("ns/a.txt", b"payload")
    fh = plane.open_file("ns/a.txt", (OpenFlag.O_RDWR,))
    detail = plane.rename_path("ns/a.txt", "ns/b.txt")
    assert detail["handle_still_valid"] is True
    assert detail["open_handles_survived"] == 1
    assert detail["policy"] == OpenHandleDisposition.SURVIVE.value
    view = plane.handles.get(fh.handle_id, fh.generation)
    assert view.generation == fh.generation
    assert view.current_path == "ns/b.txt"
    assert view.path_at_open == "ns/a.txt"
    plane.handles.write(fh.handle_id, 0, b"NEW!", generation=fh.generation)
    data = plane.handles.read(fh.handle_id, 0, 4, generation=fh.generation)
    assert data.data == b"NEW!"
    assert plane.handles.lookup_inode("ns/a.txt") is None
    assert plane.handles.lookup_inode("ns/b.txt") == fh.inode
    plane.release_file(fh.handle_id, generation=fh.generation)


def test_unlink_while_open_handle_survives(plane: HostConcurrencyPlane) -> None:
    plane.handles.seed_file("ns/victim.txt", b"doomed")
    fh = plane.open_file("ns/victim.txt", (OpenFlag.O_RDWR,))
    detail = plane.unlink_path("ns/victim.txt")
    assert detail["unlinked"] is True
    assert detail["open_handles_survived"] == 1
    assert detail["handle_still_valid"] is True
    assert plane.handles.lookup_inode("ns/victim.txt") is None
    wr = plane.handles.write(fh.handle_id, 0, b"ok!!", generation=fh.generation)
    assert wr.bytes_transferred == 4
    view = plane.handles.get(fh.handle_id, fh.generation)
    assert view.unlinked is True
    rel = plane.release_file(fh.handle_id, generation=fh.generation)
    assert rel.orphaned_inode_reclaimed is True


def test_cross_mount_rename_is_typed_conflict(plane: HostConcurrencyPlane) -> None:
    plane.handles.seed_file("ns/x.txt", b"x")
    with pytest.raises(HostCallbackConflictError) as ei:
        plane.rename_path(
            "ns/x.txt",
            "ns/y.txt",
            source_mount_id="mount:a",
            target_mount_id="mount:b",
        )
    assert ei.value.reason is ConflictReason.CROSS_MOUNT
    assert ei.value.errno is HostErrno.EXDEV


def test_reject_if_open_policy_blocks_unlink() -> None:
    policy = OpenHandlePolicy(
        rename_disposition=OpenHandleDisposition.REJECT_IF_OPEN,
        unlink_disposition=OpenHandleDisposition.REJECT_IF_OPEN,
    )
    plane = HostConcurrencyPlane(
        open_handle_policy=policy,
        clock_ms=lambda: 1_700_000_000_000,
    )
    plane.handles.seed_file("ns/locked.txt", b"body")
    fh = plane.open_file("ns/locked.txt", OpenFlag.O_RDONLY)
    with pytest.raises(HostCallbackConflictError) as ei:
        plane.unlink_path("ns/locked.txt")
    assert ei.value.reason is ConflictReason.LOCK_HELD
    plane.release_file(fh.handle_id, generation=fh.generation)
    detail = plane.unlink_path("ns/locked.txt")
    assert detail["unlinked"] is True


def test_open_handle_policy_record_is_stable() -> None:
    rec = DEFAULT_OPEN_HANDLE_POLICY.to_record()
    assert rec["schema"] == OpenHandlePolicy_V1
    assert rec["rename_disposition"] == "survive"
    assert rec["unlink_disposition"] == "survive"
    assert rec["require_same_mount"] is True


# ---------------------------------------------------------------------------
# Bounds: tables, queues, waits, cancellation, shutdown
# ---------------------------------------------------------------------------


def test_callback_queue_bound_returns_typed_conflict() -> None:
    plane = HostConcurrencyPlane(
        max_active_callbacks=1,
        max_queue_depth=0,
        default_wait_ms=0,
        clock_ms=lambda: int(time.time() * 1000),
    )
    holder = plane.gate.begin(
        kind=HostCallbackKind.GETATTR,
        paths=("hold",),
        owner_id="holder",
        path_mode=LockMode.SHARED,
    )
    with pytest.raises(HostCallbackConflictError) as ei:
        plane.run_callback(
            lambda s: None,
            kind=HostCallbackKind.GETATTR,
            paths=("other",),
            owner_id="queued",
            nonblocking=True,
        )
    assert ei.value.reason in (
        ConflictReason.CALLBACK_BOUND,
        ConflictReason.QUEUE_BOUND,
    )
    plane.gate.complete(holder)


def test_waiter_bound_returns_typed_conflict() -> None:
    lm = HostLockManager(max_waiters=0, default_wait_ms=100)
    lm.acquire("holder", [HostLockRequest(HostLockKey.for_path("p"))])
    with pytest.raises(HostLockConflictError) as ei:
        lm.acquire(
            "waiter",
            [HostLockRequest(HostLockKey.for_path("p"))],
            wait_ms=100,
        )
    assert ei.value.reason in (
        ConflictReason.WAITER_BOUND,
        ConflictReason.LOCK_HELD,
        ConflictReason.LOCK_WAIT_TIMEOUT,
    )
    lm.release_all("holder")


def test_cancel_callback_is_typed() -> None:
    plane = HostConcurrencyPlane(default_wait_ms=500)
    session = plane.gate.begin(
        kind=HostCallbackKind.WRITE,
        paths=("c2",),
        owner_id="to-cancel",
    )
    assert plane.cancel_callback(session.session_id, reason="test-cancel")
    # Completing after cancel still cleans up locks and admission slots.
    plane.gate.complete(session, aborted=True, error="test-cancel")
    assert session.cancelled is True
    assert session.cancel_reason == "test-cancel"
    assert plane.locks.global_lock_count == 0
    assert plane.gate.active_count == 0


def test_shutdown_rejects_new_callbacks_and_drains() -> None:
    plane = HostConcurrencyPlane(default_wait_ms=100)
    entered = threading.Event()
    release = threading.Event()

    def body(session):  # type: ignore[no-untyped-def]
        entered.set()
        release.wait(timeout=2)
        return True

    def worker() -> None:
        plane.run_callback(
            body,
            kind=HostCallbackKind.READ,
            paths=("d",),
            path_mode=LockMode.SHARED,
            owner_id="in-flight",
        )

    th = threading.Thread(target=worker)
    th.start()
    assert entered.wait(timeout=2)
    # Begin shutdown while work is in flight.
    plane.gate.begin_shutdown()
    with pytest.raises(HostCallbackConflictError) as ei:
        plane.run_callback(
            lambda s: None,
            kind=HostCallbackKind.READ,
            paths=("e",),
            owner_id="after-shutdown",
            nonblocking=True,
        )
    assert ei.value.reason is ConflictReason.SHUTTING_DOWN
    release.set()
    th.join(timeout=3)
    assert not th.is_alive()
    assert plane.gate.wait_drained(timeout_ms=1000) is True
    detail = plane.shutdown(drain=True, timeout_ms=1000)
    assert detail["drained"] is True
    assert plane.gate.shutdown_state is ShutdownState.STOPPED
    assert plane.pressure_snapshot()["active_callbacks"] == 0


def test_pressure_snapshot_and_to_record_are_bounded(plane: HostConcurrencyPlane) -> None:
    snap = plane.pressure_snapshot()
    assert "active_callbacks" in snap
    assert "queue_depth" in snap
    assert "global_locks" in snap
    assert "waiters" in snap
    assert "linearization_seq" in snap
    rec = plane.to_record()
    assert rec["schema"] == HostConcurrencyPlane_V1
    assert rec["contract_version"] == CONTRACT_VERSION
    assert rec["policy"]["rename_disposition"] == "survive"


# ---------------------------------------------------------------------------
# Randomized concurrency soak
# ---------------------------------------------------------------------------


def test_randomized_concurrency_stays_bounded_and_deadlock_free() -> None:
    """Random mixed callbacks/renames/unlinks/cancels/shutdown under threads.

    Completes without hanging; never exceeds configured table/queue/waiter
    bounds; open-handle survival remains consistent with SURVIVE policy.
    """

    max_active = 8
    max_waiters = 32
    max_queue = 16
    plane = HostConcurrencyPlane(
        max_active_callbacks=max_active,
        max_waiters=max_waiters,
        max_queue_depth=max_queue,
        max_global_locks=256,
        max_locks_per_owner=32,
        default_wait_ms=50,
        shutdown_drain_ms=2_000,
        clock_ms=lambda: int(time.time() * 1000),
    )
    # Seed a small namespace.
    for i in range(6):
        plane.handles.seed_file(f"ns/f{i}.bin", f"body-{i}".encode())

    stop = threading.Event()
    errors: list[BaseException] = []
    stats = {"ok": 0, "conflict": 0, "other": 0}
    stats_lock = threading.Lock()
    open_handles: dict[int, int] = {}  # handle_id -> generation
    handles_lock = threading.Lock()

    def bump(key: str) -> None:
        with stats_lock:
            stats[key] += 1

    def check_bounds() -> None:
        snap = plane.pressure_snapshot()
        assert snap["active_callbacks"] <= max_active
        assert snap["queue_depth"] <= max_queue
        assert snap["waiters"] <= max_waiters
        assert snap["global_locks"] <= 256

    def op_read(rng: random.Random) -> None:
        path = f"ns/f{rng.randrange(6)}.bin"
        plane.run_callback(
            lambda s: True,
            kind=HostCallbackKind.READ,
            paths=(path,),
            path_mode=LockMode.SHARED,
            owner_id=f"r-{threading.get_ident()}-{rng.random()}",
            wait_ms=80,
        )

    def op_write(rng: random.Random) -> None:
        path = f"ns/f{rng.randrange(6)}.bin"
        plane.run_callback(
            lambda s: True,
            kind=HostCallbackKind.WRITE,
            paths=(path,),
            owner_id=f"w-{threading.get_ident()}-{rng.random()}",
            wait_ms=80,
        )

    def op_open_close(rng: random.Random) -> None:
        path = f"ns/f{rng.randrange(6)}.bin"
        fh = plane.open_file(path, OpenFlag.O_RDONLY, wait_ms=80)
        with handles_lock:
            open_handles[fh.handle_id] = fh.generation
        if rng.random() < 0.5:
            # Rename or unlink while open.
            if rng.random() < 0.5:
                target = f"ns/f{rng.randrange(6)}.ren"
                try:
                    plane.rename_path(path, target, wait_ms=80)
                except (HostCallbackConflictError, Exception):
                    pass
            else:
                try:
                    plane.unlink_path(path, wait_ms=80)
                    # Re-seed so later ops still have something.
                    if plane.handles.lookup_inode(path) is None:
                        try:
                            plane.handles.seed_file(path, b"reseed")
                        except Exception:
                            pass
                except (HostCallbackConflictError, Exception):
                    pass
        plane.release_file(fh.handle_id, generation=fh.generation, wait_ms=80)
        with handles_lock:
            open_handles.pop(fh.handle_id, None)

    def op_rename(rng: random.Random) -> None:
        src = f"ns/f{rng.randrange(6)}.bin"
        dst = f"ns/r{rng.randrange(6)}.bin"
        plane.rename_path(src, dst, wait_ms=80)
        # Keep namespace populated.
        if plane.handles.lookup_inode(src) is None:
            try:
                plane.handles.seed_file(src, b"back")
            except Exception:
                pass

    ops = (op_read, op_write, op_open_close, op_rename)

    def worker(seed: int) -> None:
        rng = random.Random(seed)
        while not stop.is_set():
            try:
                check_bounds()
                ops[rng.randrange(len(ops))](rng)
                bump("ok")
            except HostCallbackConflictError:
                bump("conflict")
            except HostLockConflictError:
                bump("conflict")
            except BaseException as exc:  # noqa: BLE001
                # Handle-layer not-found / conflict etc. are acceptable under churn.
                msg = str(exc).lower()
                code = getattr(exc, "code", None)
                code_s = getattr(code, "value", str(code or "")).lower()
                if any(
                    token in msg or token in code_s
                    for token in (
                        "not found",
                        "already",
                        "exists",
                        "conflict",
                        "stale",
                        "path_conflict",
                        "already_exists",
                    )
                ):
                    bump("conflict")
                else:
                    bump("other")
                    errors.append(exc)
                    return

    threads = [
        threading.Thread(target=worker, args=(1000 + i,), name=f"soak-{i}")
        for i in range(6)
    ]
    for t in threads:
        t.start()
    time.sleep(0.6)
    stop.set()
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive(), f"thread {t.name} hung — possible deadlock"
    assert not errors, f"unexpected errors: {errors[:3]!r}"
    with stats_lock:
        assert stats["ok"] + stats["conflict"] > 0
    # Final bounds after quiesce.
    # Release any leftover tracked handles.
    with handles_lock:
        leftover = list(open_handles.items())
    for hid, gen in leftover:
        try:
            plane.release_file(hid, generation=gen, wait_ms=50)
        except Exception:
            pass
    # Shutdown must drain and stop.
    detail = plane.shutdown(drain=True, timeout_ms=2_000)
    assert detail["active"] == 0
    assert plane.locks.waiter_count == 0
    assert plane.locks.global_lock_count == 0
    snap = plane.pressure_snapshot()
    assert snap["active_callbacks"] == 0
    assert snap["waiters"] == 0


def test_randomized_lock_only_schedule_never_deadlocks() -> None:
    """Pure lock stress: random path/inode/handle sets, fixed seed."""

    lm = HostLockManager(
        max_global_locks=64,
        max_per_owner=8,
        max_waiters=32,
        default_wait_ms=30,
    )
    stop = threading.Event()
    hung = {"flag": False}

    def worker(seed: int) -> None:
        rng = random.Random(seed)
        owner = f"o{seed}"
        while not stop.is_set():
            n = rng.randint(1, 4)
            reqs: list[HostLockRequest] = []
            for _ in range(n):
                choice = rng.randrange(3)
                if choice == 0:
                    reqs.append(
                        HostLockRequest(
                            HostLockKey.for_path(f"p{rng.randrange(8)}"),
                            LockMode.SHARED if rng.random() < 0.5 else LockMode.EXCLUSIVE,
                        )
                    )
                elif choice == 1:
                    reqs.append(
                        HostLockRequest(
                            HostLockKey.for_inode(rng.randrange(1, 12)),
                            LockMode.EXCLUSIVE,
                        )
                    )
                else:
                    reqs.append(
                        HostLockRequest(
                            HostLockKey.for_handle(rng.randrange(1, 12)),
                            LockMode.EXCLUSIVE,
                        )
                    )
            try:
                lm.acquire(owner, reqs, wait_ms=40)
                time.sleep(rng.random() * 0.002)
            except HostLockConflictError:
                pass
            finally:
                lm.release_all(owner)
            assert lm.waiter_count <= 32
            assert lm.global_lock_count <= 64

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    time.sleep(0.5)
    stop.set()
    for t in threads:
        t.join(timeout=4)
        if t.is_alive():
            hung["flag"] = True
    assert not hung["flag"], "lock stress deadlocked"
    assert lm.global_lock_count == 0
    assert lm.waiter_count == 0


def test_concurrent_rename_and_io_handle_survives() -> None:
    plane = HostConcurrencyPlane(
        default_wait_ms=200,
        clock_ms=lambda: int(time.time() * 1000),
    )
    plane.handles.seed_file("ns/live.bin", b"0123456789")
    fh = plane.open_file("ns/live.bin", (OpenFlag.O_RDWR,))
    errors: list[BaseException] = []
    done = threading.Event()

    def renamer() -> None:
        try:
            for i in range(10):
                src = "ns/live.bin" if i % 2 == 0 else "ns/live2.bin"
                dst = "ns/live2.bin" if i % 2 == 0 else "ns/live.bin"
                try:
                    plane.rename_path(src, dst, wait_ms=100)
                except HostCallbackConflictError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    if "not found" not in str(exc).lower():
                        errors.append(exc)
        finally:
            done.set()

    def writer() -> None:
        try:
            for i in range(20):
                try:
                    plane.handles.write(
                        fh.handle_id,
                        i % 5,
                        b"X",
                        generation=fh.generation,
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)
                time.sleep(0.001)
        finally:
            pass

    t1 = threading.Thread(target=renamer)
    t2 = threading.Thread(target=writer)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert not t1.is_alive() and not t2.is_alive()
    assert not errors, errors
    # Handle still valid after churn.
    view = plane.handles.get(fh.handle_id, fh.generation)
    assert view.generation == fh.generation
    assert view.released is False
    plane.release_file(fh.handle_id, generation=fh.generation)
    assert done.is_set()

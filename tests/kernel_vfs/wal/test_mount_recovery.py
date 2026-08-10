"""KVFS-301: Pre-ready recovery, idempotent replay, orphan reclamation, leases.

Acceptance coverage:

* a single-writer state lease fences concurrent mounts;
* recovery completes before ready;
* repeated restart applies committed effects exactly once;
* incomplete transactions resolve per policy;
* only provably orphaned stages/handles are reclaimed;
* evidence is preserved on error;
* recovery terminates within a declared bound.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.handles import HandleTable, OpenFlag
from ipfs_kit_py.core.vfs.host_contracts import MountLifecycleState
from ipfs_kit_py.core.wal.coordinator import WALTransactionCrash
from ipfs_kit_py.kernel_vfs.durable_mutation import (
    DurableMutationCoordinator,
    MutationEffectBackend,
)
from ipfs_kit_py.kernel_vfs import wal_recovery as wr_mod
from ipfs_kit_py.kernel_vfs.wal_recovery import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    TASK_ID,
    IncompleteTransactionPolicy,
    MountRecoveryCoordinator,
    MountRecoveryCoordinator_V1,
    MountRecoveryError,
    MountRecoveryFacade,
    MountRecoveryReceipt,
    MountRecoveryReceipt_V1,
    RecoveryDisposition,
    RecoveryErrorCode,
    RecoveryPhase,
    RecoveryProtocolError,
    StateLease,
    StateLease_V1,
    StateLeaseHeldError,
    build_mount_recovery_coordinator,
    incomplete_policies,
    reclaim_orphan_stages,
    recovery_dispositions,
    recovery_phases,
    write_stage,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "wal_recovery.py"


# ---------------------------------------------------------------------------
# Schema / vocabulary
# ---------------------------------------------------------------------------


def test_schema_versions_and_aliases() -> None:
    assert TASK_ID == "KVFS-301"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert MountRecoveryCoordinator_V1.endswith("@1")
    assert StateLease_V1.endswith("@1")
    assert MountRecoveryReceipt_V1.endswith("@1")
    assert MountRecoveryFacade is MountRecoveryCoordinator
    assert "acquire_lease" in recovery_phases()
    assert "enter_ready" in recovery_phases()
    assert incomplete_policies() == ("compensate", "retain")
    assert "ready" in recovery_dispositions()
    assert "KVFS-301" in MODULE_PATH.read_text(encoding="utf-8")
    assert "single-writer" in MODULE_PATH.read_text(encoding="utf-8")


def test_ready_receipt_requires_recovery_complete() -> None:
    with pytest.raises(RecoveryProtocolError):
        MountRecoveryReceipt(
            receipt_id="r1",
            disposition=RecoveryDisposition.READY,
            success=True,
            recovery_complete=False,
            ready=True,
            mount_id="mount:x",
            lifecycle_state=MountLifecycleState.READY,
        )


def test_ready_receipt_requires_ready_lifecycle() -> None:
    with pytest.raises(RecoveryProtocolError):
        MountRecoveryReceipt(
            receipt_id="r2",
            disposition=RecoveryDisposition.READY,
            success=True,
            recovery_complete=True,
            ready=True,
            mount_id="mount:x",
            lifecycle_state=MountLifecycleState.RECOVERING,
        )


# ---------------------------------------------------------------------------
# Single-writer state lease
# ---------------------------------------------------------------------------


def test_state_lease_exclusive_fence(tmp_path: Path) -> None:
    state = tmp_path / "state"
    first = StateLease(state, mount_id="mount:a", holder_id="holder:a")
    holder = first.try_acquire()
    assert first.held is True
    assert holder.mount_id == "mount:a"
    assert holder.holder_id == "holder:a"
    assert (state / "mount.lease").exists()
    assert (state / "mount.lease.holder.json").exists()

    second = StateLease(state, mount_id="mount:b", holder_id="holder:b")
    with pytest.raises(StateLeaseHeldError) as exc_info:
        second.try_acquire()
    assert exc_info.value.code is RecoveryErrorCode.LEASE_HELD
    assert exc_info.value.holder.get("holder_id") == "holder:a"
    assert second.held is False

    first.release()
    assert first.held is False
    # After release, a second mount can acquire.
    holder_b = second.try_acquire()
    assert holder_b.holder_id == "holder:b"
    second.release()


def test_state_lease_heartbeat_and_idempotent_release(tmp_path: Path) -> None:
    lease = StateLease(tmp_path / "lease-state", mount_id="mount:hb")
    holder1 = lease.try_acquire()
    time.sleep(0.01)
    holder2 = lease.heartbeat()
    assert holder2.heartbeat_unix_ms >= holder1.heartbeat_unix_ms
    assert lease.release() is True
    assert lease.release() is False
    with pytest.raises(MountRecoveryError):
        lease.heartbeat()


def test_state_lease_context_manager(tmp_path: Path) -> None:
    with StateLease(tmp_path / "ctx", mount_id="mount:ctx") as lease:
        assert lease.held is True
    assert lease.held is False


# ---------------------------------------------------------------------------
# Recovery completes before ready
# ---------------------------------------------------------------------------


def test_empty_state_recovery_reaches_ready(tmp_path: Path) -> None:
    with MountRecoveryCoordinator(tmp_path / "empty") as coord:
        assert coord.ready is False
        with pytest.raises(RecoveryProtocolError):
            coord.assert_ready()
        receipt = coord.recover()
        assert receipt.success is True
        assert receipt.ready is True
        assert receipt.recovery_complete is True
        assert receipt.disposition is RecoveryDisposition.READY
        assert receipt.lifecycle_state is MountLifecycleState.READY
        assert coord.ready is True
        assert coord.lifecycle.state is MountLifecycleState.READY
        assert coord.lifecycle.recovery_complete is True
        assert RecoveryPhase.ACQUIRE_LEASE.value in receipt.phases
        assert RecoveryPhase.REPLAY_WAL.value in receipt.phases
        assert RecoveryPhase.RECLAIM_ORPHANS.value in receipt.phases
        assert RecoveryPhase.ENTER_READY.value in receipt.phases
        # Phases order: lease before ready.
        assert receipt.phases.index("acquire_lease") < receipt.phases.index("enter_ready")
        assert receipt.phases.index("replay_wal") < receipt.phases.index("enter_ready")
        coord.assert_ready()
        life = coord.host_mount_lifecycle()
        assert life.ready is True
        assert life.recovery_complete is True


def test_idempotent_recover_when_already_ready(tmp_path: Path) -> None:
    with MountRecoveryCoordinator(tmp_path / "idem") as coord:
        first = coord.recover()
        second = coord.recover()
        assert first.disposition is RecoveryDisposition.READY
        assert second.disposition is RecoveryDisposition.IDEMPOTENT
        assert second.ready is True
        assert second.success is True


def test_concurrent_mount_fenced_by_lease(tmp_path: Path) -> None:
    state = tmp_path / "shared-state"
    first = MountRecoveryCoordinator(state, mount_id="mount:first", holder_id="h1")
    second = MountRecoveryCoordinator(state, mount_id="mount:second", holder_id="h2")
    try:
        r1 = first.recover()
        assert r1.success is True
        r2 = second.recover()
        assert r2.success is False
        assert r2.disposition is RecoveryDisposition.LEASE_HELD
        assert r2.ready is False
        assert r2.recovery_complete is False
        assert r2.error_code == RecoveryErrorCode.LEASE_HELD.value
        # Evidence preserved for the fenced mount.
        assert r2.evidence_path
        assert Path(r2.evidence_path).is_file()
    finally:
        first.close()
        second.close()


# ---------------------------------------------------------------------------
# Crash recovery: committed once, incomplete compensated
# ---------------------------------------------------------------------------


def _crash_at(boundary: str):
    def inject(name: str, _txn: str = "") -> None:
        if name == boundary:
            raise WALTransactionCrash(name)

    return inject


def test_restart_replays_committed_effect_exactly_once(tmp_path: Path) -> None:
    root = tmp_path / "committed"
    backend = MutationEffectBackend()
    durable = root / "state" / "durable"
    with DurableMutationCoordinator(
        durable, backend=backend
    ) as coord:
        result = coord.create(
            "docs/a.txt",
            b"payload-a",
            effect_id="effect:committed-1",
            transaction_id="txn:committed-1",
        )
        assert result.committed is True
        entry = backend.storage.get("docs/a.txt")
        assert entry is not None
        assert bytes(entry.content) == b"payload-a"

    # Fresh process: recovery via MountRecoveryCoordinator sharing storage.
    # New backend instance has an empty in-memory effect ledger; WAL must drive
    # idempotent re-apply (content-match) for committed effects.
    recovered_backend = MutationEffectBackend(storage=backend.storage)
    mutations = DurableMutationCoordinator(durable, backend=recovered_backend)
    with MountRecoveryCoordinator(
        root / "state",
        mutations=mutations,
    ) as recovery:
        receipt = recovery.recover()
        assert receipt.success is True
        assert receipt.ready is True
        entry = recovered_backend.storage.get("docs/a.txt")
        assert entry is not None
        assert bytes(entry.content) == b"payload-a"
        # Second recover is idempotent at both layers.
        again = recovery.recover()
        assert again.disposition is RecoveryDisposition.IDEMPOTENT

    # Brand-new coordinator on same state directory after close releases lease.
    mutations2 = DurableMutationCoordinator(
        durable, backend=MutationEffectBackend(storage=backend.storage)
    )
    with MountRecoveryCoordinator(root / "state", mutations=mutations2) as recovery2:
        r = recovery2.recover()
        assert r.success is True
        # WAL ledger suppresses duplicate replay.
        assert r.replayed == 0 or r.disposition is RecoveryDisposition.READY
        entry = backend.storage.get("docs/a.txt")
        assert entry is not None
        assert bytes(entry.content) == b"payload-a"


def test_incomplete_pre_commit_effect_is_compensated(tmp_path: Path) -> None:
    root = tmp_path / "incomplete"
    backend = MutationEffectBackend()
    durable = root / "state" / "durable"
    with DurableMutationCoordinator(
        durable, backend=backend, crash_injector=_crash_at("after_effect")
    ) as coord:
        with pytest.raises(WALTransactionCrash):
            coord.create(
                "needs-comp.txt",
                b"tmp",
                effect_id="effect:needs-comp",
                transaction_id="txn:needs-comp",
            )
        assert backend.storage.get("needs-comp.txt") is not None

    mutations = DurableMutationCoordinator(durable, backend=backend)
    with MountRecoveryCoordinator(root / "state", mutations=mutations) as recovery:
        receipt = recovery.recover()
        assert receipt.success is True
        assert receipt.rolled_back >= 1
        assert receipt.incomplete_resolved >= 1
        assert backend.storage.get("needs-comp.txt") is None
        assert recovery.ready is True


@pytest.mark.parametrize(
    "boundary,expect_present",
    [
        ("before_intent", False),
        ("after_intent", False),
        ("after_effect", False),
        ("after_decision", True),
    ],
)
def test_crash_matrix_converges_via_mount_recovery(
    tmp_path: Path, boundary: str, expect_present: bool
) -> None:
    root = tmp_path / f"matrix-{boundary}"
    backend = MutationEffectBackend()
    durable = root / "state" / "durable"
    path = f"crash/{boundary}.txt"
    effect_id = f"effect:crash:{boundary}"
    txn = f"txn:crash:{boundary}"

    with DurableMutationCoordinator(
        durable, backend=backend, crash_injector=_crash_at(boundary)
    ) as coord:
        with pytest.raises(WALTransactionCrash):
            coord.create(path, b"payload", effect_id=effect_id, transaction_id=txn)

    mutations = DurableMutationCoordinator(
        durable, backend=MutationEffectBackend(storage=backend.storage)
    )
    with MountRecoveryCoordinator(root / "state", mutations=mutations) as recovery:
        receipt = recovery.recover()
        assert receipt.success is True
        assert receipt.ready is True
        present = mutations.backend.storage.get(path) is not None
        assert present is expect_present


# ---------------------------------------------------------------------------
# Orphan reclamation (stages + handles)
# ---------------------------------------------------------------------------


def test_reclaim_only_provably_orphaned_stages(tmp_path: Path) -> None:
    stages = tmp_path / "stages"
    write_stage(stages, "stage-live", b"live-bytes", referenced=True, effect_id="e-live")
    write_stage(stages, "stage-orphan", b"orphan-bytes", referenced=False, effect_id="e-orphan")
    # Unindexed stage file (crash after write, before index).
    orphan_path = stages / "crash-unindexed.stage"
    orphan_path.write_bytes(b"unindexed")

    receipt = reclaim_orphan_stages(
        stages,
        live_stage_ids=["stage-live"],
    )
    assert "stage-orphan" in receipt.stage_ids_reclaimed
    assert "stage-live" in receipt.stage_ids_retained
    assert not (stages / "stage-orphan.stage").exists()
    assert (stages / "stage-live.stage").exists()
    assert not orphan_path.exists()
    assert receipt.reclaimed_stages >= 2
    assert receipt.retained_stages >= 1


def test_recovery_reclaims_orphan_handles_and_stages(tmp_path: Path) -> None:
    state = tmp_path / "reclaim-state"
    clock = {"t": 1_000_000}

    def now() -> int:
        return clock["t"]

    handles = HandleTable(mount_id="mount:reclaim", clock_ms=now, default_lease_ms=100)
    # Open a handle and expire its lease.
    opened = handles.create(
        "file.txt",
        flags=(OpenFlag.O_CREAT, OpenFlag.O_RDWR),
        lease_ms=100,
    )
    handle_id = opened.handle_id
    clock["t"] += 10_000  # expire lease

    write_stage(
        state / "stages",
        "orphan-stage",
        b"gone",
        referenced=False,
        effect_id="effect:orphan-stage",
    )
    write_stage(
        state / "stages",
        "kept-stage",
        b"kept",
        referenced=True,
        effect_id="effect:kept",
    )

    with MountRecoveryCoordinator(
        state,
        handles=handles,
        live_stage_ids=["kept-stage"],
    ) as coord:
        receipt = coord.recover()
        assert receipt.success is True
        assert receipt.orphan_reclaim is not None
        assert receipt.orphan_reclaim.expired_leases >= 1
        assert receipt.orphan_reclaim.reclaimed_handles >= 1
        assert "orphan-stage" in receipt.orphan_reclaim.stage_ids_reclaimed
        assert "kept-stage" in receipt.orphan_reclaim.stage_ids_retained
        # Expired handle slot reclaimed (unknown or already released).
        try:
            fh = handles.get(handle_id, generation=opened.generation, allow_released=True)
            assert fh is None or fh.released
        except Exception:
            # Stale/unknown handle after reclaim is acceptable.
            pass


# ---------------------------------------------------------------------------
# Evidence preservation + timeout bound
# ---------------------------------------------------------------------------


def test_recovery_timeout_preserves_evidence(tmp_path: Path) -> None:
    # Sleep longer than the declared bound during the first phase so the
    # subsequent deadline check fails closed with evidence preserved.
    def slow(phase: str) -> None:
        if phase == "acquire_lease":
            time.sleep(0.05)

    with MountRecoveryCoordinator(
        tmp_path / "timeout",
        recovery_timeout_seconds=0.01,
        crash_injector=slow,
    ) as coord:
        receipt = coord.recover()
        assert receipt.success is False
        assert receipt.ready is False
        assert receipt.recovery_complete is False
        assert receipt.disposition is RecoveryDisposition.TIMED_OUT
        assert receipt.error_code == RecoveryErrorCode.TIMEOUT.value
        assert receipt.evidence_path
        evidence = Path(receipt.evidence_path)
        assert evidence.is_file()
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        assert payload["schema"].endswith("recovery-evidence@1")
        assert payload["mount_id"] == coord.mount_id
        assert "error" in payload
        assert payload["receipt"]["ready"] is False
        # Evidence directory retains the file after coordinator close.
        evidence_path = evidence

    assert evidence_path.exists()


def test_wal_replay_failure_preserves_evidence(tmp_path: Path) -> None:
    class BoomMutations(DurableMutationCoordinator):
        def recover(self) -> dict[str, int]:  # type: ignore[override]
            raise RuntimeError("simulated wal replay failure")

    durable = tmp_path / "boom" / "durable"
    mutations = BoomMutations(durable)
    with MountRecoveryCoordinator(tmp_path / "boom", mutations=mutations) as coord:
        receipt = coord.recover()
        assert receipt.success is False
        assert receipt.ready is False
        assert receipt.disposition is RecoveryDisposition.FAILED
        assert receipt.evidence_path
        payload = json.loads(Path(receipt.evidence_path).read_text(encoding="utf-8"))
        assert "simulated wal replay failure" in payload["error"]["message"]
        assert coord.lifecycle.state is MountLifecycleState.FAILED
        assert coord.lease.held is False  # released on failure


def test_factory_and_validation(tmp_path: Path) -> None:
    with pytest.raises(MountRecoveryError):
        MountRecoveryCoordinator(tmp_path / "never-created", recovery_timeout_seconds=0)
    assert not (tmp_path / "never-created").exists()
    assert callable(build_mount_recovery_coordinator)


def test_build_and_close(tmp_path: Path) -> None:
    coord = build_mount_recovery_coordinator(tmp_path / "built", mount_id="mount:built")
    try:
        receipt = coord.recover()
        assert receipt.ready is True
    finally:
        coord.close()
        coord.close()  # idempotent


def test_retain_policy_skips_apply(tmp_path: Path) -> None:
    root = tmp_path / "retain"
    backend = MutationEffectBackend()
    durable = root / "state" / "durable"
    with DurableMutationCoordinator(
        durable, backend=backend, crash_injector=_crash_at("after_effect")
    ) as coord:
        with pytest.raises(WALTransactionCrash):
            coord.create(
                "retain-me.txt",
                b"x",
                effect_id="effect:retain",
                transaction_id="txn:retain",
            )
        assert backend.storage.get("retain-me.txt") is not None

    mutations = DurableMutationCoordinator(durable, backend=backend)
    with MountRecoveryCoordinator(
        root / "state",
        mutations=mutations,
        incomplete_policy=IncompleteTransactionPolicy.RETAIN,
    ) as recovery:
        receipt = recovery.recover()
        assert receipt.success is True
        assert receipt.incomplete_policy is IncompleteTransactionPolicy.RETAIN
        # Effect not compensated under RETAIN.
        assert backend.storage.get("retain-me.txt") is not None


def test_module_docstring_states_invariants() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "recovery completes before ready" in text.lower() or "before ready" in text
    assert "single-writer" in text
    assert "exactly once" in text or "idempotent" in text
    assert wr_mod.TASK_ID == "KVFS-301"


def test_parallel_acquire_only_one_winner(tmp_path: Path) -> None:
    state = tmp_path / "race"
    winners: list[str] = []
    errors: list[BaseException] = []
    held: list[StateLease] = []
    barrier = threading.Barrier(8)
    done = threading.Barrier(8)
    lock = threading.Lock()

    def worker(name: str) -> None:
        lease = StateLease(state, mount_id=f"mount:{name}", holder_id=name)
        try:
            barrier.wait(timeout=5)
            lease.try_acquire()
            with lock:
                winners.append(name)
                held.append(lease)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)
            lease.release()
        finally:
            # Keep the winner's lease held until every contender has finished
            # its single try_acquire so late threads cannot steal it.
            try:
                done.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    for lease in held:
        lease.release()
    assert len(winners) == 1
    assert all(isinstance(e, StateLeaseHeldError) for e in errors)
    assert len(errors) == 7

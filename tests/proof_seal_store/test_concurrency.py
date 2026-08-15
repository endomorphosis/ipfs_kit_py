"""Concurrent-writer and deterministic-replay conformance (IPS-026).

Acceptance:

* exactly one concurrent CAS writer wins;
* a stale writer cannot overwrite the current pointer;
* repeated recovery against the same durable state is deterministic;
* uncommitted work never becomes current under concurrent recovery.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    CurrentSealPointer,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    HermeticProofSealStore,
    content_cid_for_bytes,
)
from ipfs_kit_py.proof_seal_store.pointer import (
    CurrentSealRepository,
    PointerDisposition,
    PointerReason,
)
from ipfs_kit_py.proof_seal_store.recovery import (
    RecoveryDisposition,
    recover_seal_transitions,
)
from ipfs_kit_py.proof_seal_store.wal import (
    PHASE_ORDER,
    SealTransitionWal,
    begin_transition,
)

EVIDENCE_SUBSET = "ips/kit-concurrency@1"


def _cid(tag: bytes) -> str:
    return content_cid_for_bytes(b'{"concurrency":"' + tag + b'"}')


def _pointer(
    seal_cid: str,
    *,
    generation: int = 0,
    parent_seal_cid: str = "",
) -> CurrentSealPointer:
    return CurrentSealPointer(
        repository_id="repo:kit",
        branch_id="main",
        seal_cid=seal_cid,
        seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        generation=generation,
        parent_seal_cid=parent_seal_cid,
    )


def _intent(transition_id: str) -> SealTransitionRecord:
    return SealTransitionRecord(
        transition_id=transition_id,
        repository_id="repo:kit",
        branch_id="main",
        phase=SealTransitionPhase.INTENT,
        state=SealTransitionState.OPEN,
    )


def test_evidence_subset_constant() -> None:
    assert EVIDENCE_SUBSET == "ips/kit-concurrency@1"


def test_exactly_one_concurrent_cas_writer_wins(tmp_path: Path) -> None:
    repo = CurrentSealRepository(tmp_path)
    parent = _pointer(_cid(b"parent"), generation=0)
    assert repo.compare_and_swap_current_seal(None, parent) is True

    contenders = [
        _pointer(_cid(f"w{index}".encode()), generation=1, parent_seal_cid=parent.seal_cid)
        for index in range(8)
    ]

    def attempt(pointer: CurrentSealPointer) -> bool:
        return repo.compare_and_swap_current_seal(parent, pointer)

    winners: list[CurrentSealPointer] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(attempt, item): item for item in contenders}
        for future in as_completed(futures):
            if future.result():
                winners.append(futures[future])

    assert len(winners) == 1
    current = repo.get_current_seal("repo:kit", "main")
    assert current == winners[0]
    assert current is not None
    assert current.generation == 1
    assert current.parent_seal_cid == parent.seal_cid


def test_stale_writer_never_overwrites_current(tmp_path: Path) -> None:
    repo = CurrentSealRepository(tmp_path)
    first = _pointer(_cid(b"s0"))
    second = _pointer(_cid(b"s1"), generation=1, parent_seal_cid=first.seal_cid)
    stale = _pointer(_cid(b"stale"), generation=1, parent_seal_cid=first.seal_cid)
    assert repo.compare_and_swap_current_seal(None, first) is True
    assert repo.compare_and_swap_current_seal(first, second) is True

    results = []

    def stale_write() -> None:
        results.append(repo.compare_and_swap_current_seal_result(first, stale))

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(stale_write) for _ in range(8)]
        for fut in futs:
            fut.result()

    assert all(not item.swapped for item in results)
    assert all(item.disposition is PointerDisposition.STALE for item in results)
    assert all(item.reason is PointerReason.STALE_PARENT for item in results)
    assert repo.get_current_seal("repo:kit", "main") == second


def test_concurrent_recovery_is_deterministic(tmp_path: Path) -> None:
    store = HermeticProofSealStore(tmp_path)
    wal = SealTransitionWal(tmp_path)
    begin_transition(wal, _intent("txn:open"))
    wal.record_phase("txn:open", SealTransitionPhase.PROOF_EXECUTION)
    wal.close()

    def recover_once() -> tuple[str, str]:
        report = recover_seal_transitions(tmp_path, store=store)
        decision = report.decision_for("txn:open")
        return decision.disposition.value, decision.reason.value

    with ThreadPoolExecutor(max_workers=4) as pool:
        observed = list(pool.map(lambda _: recover_once(), range(4)))
    assert len(set(observed)) == 1
    assert observed[0][0] == RecoveryDisposition.FULL_REPROOF.value


def test_uncommitted_work_cannot_become_current_under_replay(tmp_path: Path) -> None:
    wal = SealTransitionWal(tmp_path)
    begin_transition(wal, _intent("txn:partial"))
    wal.record_phase("txn:partial", SealTransitionPhase.PROOF_EXECUTION)
    first = recover_seal_transitions(tmp_path, wal=wal)
    second = recover_seal_transitions(tmp_path, wal=wal)
    assert first.decision_for("txn:partial").disposition is (
        second.decision_for("txn:partial").disposition
    )
    assert wal.is_current_eligible("txn:partial") is False
    assert wal.committed_transitions() == ()
    wal.close()


def test_committed_replay_order_is_stable(tmp_path: Path) -> None:
    wal = SealTransitionWal(tmp_path)
    seals: list[str] = []
    for index in range(3):
        tid = f"txn:{index}"
        seal = _cid(f"seal-{index}".encode())
        seals.append(seal)
        begin_transition(wal, _intent(tid))
        current = wal.get_transition(tid)
        assert current is not None
        start = PHASE_ORDER.index(current.phase)
        end = PHASE_ORDER.index(SealTransitionPhase.SEAL_PERSISTENCE)
        for phase in PHASE_ORDER[start + 1 : end + 1]:
            kwargs: dict[str, object] = {}
            if phase is SealTransitionPhase.SEAL_PERSISTENCE:
                kwargs["new_seal_cid"] = seal
                kwargs["new_seal_kind"] = ArtifactKind.CHECKPOINT_SEAL
            wal.record_phase(tid, phase, **kwargs)
        wal.commit_transition(
            tid,
            new_seal_cid=seal,
            new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        )
    first = [view.transition_id for view in wal.replay_committed()]
    wal.close()
    reopened = SealTransitionWal(tmp_path)
    second = [view.transition_id for view in reopened.replay_committed()]
    assert first == second == ["txn:0", "txn:1", "txn:2"]
    assert [view.new_seal_cid for view in reopened.replay_committed()] == seals
    reopened.close()

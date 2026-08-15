"""Seven-phase crash-recovery matrix for the kit seal store (IPS-026).

Each plan §9 failure point is injected, recovered, and recovered again.
Committed current pointers are never lost; ambiguous prover outcomes never
become success; repeated recovery is deterministic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

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
from ipfs_kit_py.proof_seal_store.pointer import CurrentSealRepository
from ipfs_kit_py.proof_seal_store.recovery import (
    RecoveryDisposition,
    RecoveryReason,
    recover_seal_transitions,
)
from ipfs_kit_py.proof_seal_store.wal import (
    CRASH_BOUNDARIES,
    PHASE_ORDER,
    SealTransitionWal,
    SealTransitionWalCrash,
    begin_transition,
)

EVIDENCE_SUBSET = "ips/kit-crash-matrix@1"

# Plan §9 seven joined crash boundaries and the expected recovery decision.
SEVEN_PHASE_MATRIX: tuple[tuple[str, SealTransitionPhase, RecoveryDisposition], ...] = (
    ("before_proof_execution", SealTransitionPhase.INTENT, RecoveryDisposition.RESUME),
    (
        "after_proof_execution",
        SealTransitionPhase.PROOF_EXECUTION,
        RecoveryDisposition.VERIFY_EXISTING,
    ),
    (
        "after_receipt_persistence",
        SealTransitionPhase.RECEIPT_PERSISTENCE,
        RecoveryDisposition.REPLAY,
    ),
    (
        "after_forest_update",
        SealTransitionPhase.FOREST_UPDATE,
        RecoveryDisposition.VERIFY_EXISTING,
    ),
    (
        "after_aggregate_generation",
        SealTransitionPhase.AGGREGATE_GENERATION,
        RecoveryDisposition.VERIFY_EXISTING,
    ),
    (
        "after_seal_persistence",
        SealTransitionPhase.SEAL_PERSISTENCE,
        RecoveryDisposition.VERIFY_EXISTING,
    ),
    (
        "after_current_root_cas",
        SealTransitionPhase.CURRENT_ROOT_CAS,
        RecoveryDisposition.REPAIR,
    ),
)


def _cid(tag: bytes) -> str:
    return content_cid_for_bytes(b'{"crash-matrix":"' + tag + b'"}')


def _intent(transition_id: str = "txn:crash") -> SealTransitionRecord:
    return SealTransitionRecord(
        transition_id=transition_id,
        repository_id="repo:kit",
        branch_id="main",
        phase=SealTransitionPhase.INTENT,
        state=SealTransitionState.OPEN,
    )


def _advance_to(
    wal: SealTransitionWal,
    transition_id: str,
    target: SealTransitionPhase,
    *,
    artifacts: dict[SealTransitionPhase, tuple[str, ...]],
    seal_cid: str | None = None,
) -> SealTransitionRecord:
    current = wal.get_transition(transition_id)
    assert current is not None
    start = PHASE_ORDER.index(current.phase)
    end = PHASE_ORDER.index(target)
    record = current
    for index in range(start + 1, end + 1):
        phase = PHASE_ORDER[index]
        kwargs: dict[str, Any] = {}
        if phase in artifacts:
            kwargs["artifact_cids"] = artifacts[phase]
        if phase in {
            SealTransitionPhase.SEAL_PERSISTENCE,
            SealTransitionPhase.CURRENT_ROOT_CAS,
            SealTransitionPhase.CLEANUP,
        }:
            kwargs["new_seal_cid"] = seal_cid
            kwargs["new_seal_kind"] = ArtifactKind.CHECKPOINT_SEAL
        record = wal.record_phase(transition_id, phase, **kwargs)
    return record


def _admit_phase_artifacts(
    store: HermeticProofSealStore,
) -> tuple[dict[SealTransitionPhase, tuple[str, ...]], str]:
    kinds = {
        SealTransitionPhase.PROOF_EXECUTION: (ArtifactKind.PROOF_OBJECT, b"proof"),
        SealTransitionPhase.RECEIPT_PERSISTENCE: (ArtifactKind.PROOF_RECEIPT, b"receipt"),
        SealTransitionPhase.FOREST_UPDATE: (ArtifactKind.MERKLE_NODE, b"forest"),
        SealTransitionPhase.AGGREGATE_GENERATION: (ArtifactKind.PROOF_MANIFEST, b"agg"),
    }
    artifacts: dict[SealTransitionPhase, tuple[str, ...]] = {}
    for phase, (kind, tag) in kinds.items():
        ref = store.put_immutable(kind, b'{"crash":"' + tag + b'"}')
        artifacts[phase] = (ref.cid,)
    seal = store.put_immutable(
        ArtifactKind.CHECKPOINT_SEAL, b'{"crash":"seal"}'
    )
    return artifacts, seal.cid


def test_seven_phase_boundaries_are_named() -> None:
    assert EVIDENCE_SUBSET == "ips/kit-crash-matrix@1"
    for boundary, _phase, _disposition in SEVEN_PHASE_MATRIX:
        assert boundary in CRASH_BOUNDARIES


@pytest.mark.parametrize(
    ("boundary", "durable_phase", "expected"),
    SEVEN_PHASE_MATRIX,
    ids=[item[0] for item in SEVEN_PHASE_MATRIX],
)
def test_seven_phase_crash_recovery_matches_policy(
    tmp_path: Path,
    boundary: str,
    durable_phase: SealTransitionPhase,
    expected: RecoveryDisposition,
) -> None:
    store = HermeticProofSealStore(tmp_path)
    pointers = CurrentSealRepository(tmp_path)
    artifacts, seal_cid = _admit_phase_artifacts(store)

    crash_at = {"hit": False}

    def inject(name: str, transition_id: str, phase: Any = None) -> None:
        del transition_id, phase
        if name == boundary and not crash_at["hit"]:
            crash_at["hit"] = True
            raise SealTransitionWalCrash(name)

    wal = SealTransitionWal(tmp_path, crash_injector=inject)
    begin_transition(wal, _intent())
    if durable_phase is SealTransitionPhase.INTENT:
        # Crash before the first proof-execution record is durable.
        with pytest.raises(SealTransitionWalCrash):
            wal.record_phase(
                "txn:crash",
                SealTransitionPhase.PROOF_EXECUTION,
                artifact_cids=artifacts[SealTransitionPhase.PROOF_EXECUTION],
            )
    else:
        predecessor = PHASE_ORDER[PHASE_ORDER.index(durable_phase) - 1]
        if predecessor is not SealTransitionPhase.INTENT:
            _advance_to(
                wal,
                "txn:crash",
                predecessor,
                artifacts=artifacts,
                seal_cid=seal_cid,
            )
        with pytest.raises(SealTransitionWalCrash):
            kwargs: dict[str, Any] = {}
            if durable_phase in artifacts:
                kwargs["artifact_cids"] = artifacts[durable_phase]
            if durable_phase in {
                SealTransitionPhase.SEAL_PERSISTENCE,
                SealTransitionPhase.CURRENT_ROOT_CAS,
            }:
                kwargs["new_seal_cid"] = seal_cid
                kwargs["new_seal_kind"] = ArtifactKind.CHECKPOINT_SEAL
            wal.record_phase("txn:crash", durable_phase, **kwargs)

        # after_* injectors fire after the phase record is durable.
        leftover = wal.get_transition("txn:crash")
        assert leftover is not None
        if boundary.startswith("after_"):
            assert leftover.phase is durable_phase

    if durable_phase is SealTransitionPhase.CURRENT_ROOT_CAS:
        # Simulate successful CAS then crash before WAL commit/cleanup.
        leftover = wal.get_transition("txn:crash")
        assert leftover is not None
        if leftover.phase is SealTransitionPhase.CURRENT_ROOT_CAS:
            pointers.compare_and_swap_current_seal(
                None,
                CurrentSealPointer(
                    repository_id="repo:kit",
                    branch_id="main",
                    seal_cid=seal_cid,
                    seal_kind=ArtifactKind.CHECKPOINT_SEAL,
                    generation=0,
                ),
            )

    first = recover_seal_transitions(
        tmp_path, wal=wal, store=store, pointers=pointers
    )
    second = recover_seal_transitions(
        tmp_path, wal=wal, store=store, pointers=pointers
    )
    decision = first.decision_for("txn:crash")
    replay = second.decision_for("txn:crash")
    assert decision.disposition is expected
    assert replay.disposition is expected
    assert wal.is_current_eligible("txn:crash") is (
        expected is RecoveryDisposition.REPAIR
    )
    wal.close()


def test_committed_pointer_survives_later_crash(tmp_path: Path) -> None:
    store = HermeticProofSealStore(tmp_path)
    pointers = CurrentSealRepository(tmp_path)
    artifacts, seal_cid = _admit_phase_artifacts(store)
    wal = SealTransitionWal(tmp_path)
    begin_transition(wal, _intent("txn:committed"))
    _advance_to(
        wal,
        "txn:committed",
        SealTransitionPhase.CURRENT_ROOT_CAS,
        artifacts=artifacts,
        seal_cid=seal_cid,
    )
    wal.commit_transition(
        "txn:committed",
        new_seal_cid=seal_cid,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        phase=SealTransitionPhase.CLEANUP,
    )
    pointers.compare_and_swap_current_seal(
        None,
        CurrentSealPointer(
            repository_id="repo:kit",
            branch_id="main",
            seal_cid=seal_cid,
            seal_kind=ArtifactKind.CHECKPOINT_SEAL,
            generation=0,
        ),
    )

    def inject(name: str, transition_id: str, phase: Any = None) -> None:
        del phase
        if name == "before_begin" and transition_id == "txn:later":
            raise SealTransitionWalCrash(name)

    wal._crash_injector = inject
    with pytest.raises(SealTransitionWalCrash):
        begin_transition(wal, _intent("txn:later"))

    report = recover_seal_transitions(
        tmp_path, wal=wal, store=store, pointers=pointers
    )
    committed = report.decision_for("txn:committed")
    assert committed.disposition is RecoveryDisposition.REPAIR
    assert wal.is_current_eligible("txn:committed") is True
    current = pointers.get_current_seal("repo:kit", "main")
    assert current is not None
    assert current.seal_cid == seal_cid
    wal.close()


def test_after_proof_without_durable_artifact_is_full_reproof(tmp_path: Path) -> None:
    def inject(name: str, transition_id: str, phase: Any = None) -> None:
        del transition_id, phase
        if name == "after_proof_execution":
            raise SealTransitionWalCrash(name)

    wal = SealTransitionWal(tmp_path, crash_injector=inject)
    begin_transition(wal, _intent())
    with pytest.raises(SealTransitionWalCrash):
        wal.record_phase("txn:crash", SealTransitionPhase.PROOF_EXECUTION)
    report = recover_seal_transitions(tmp_path, wal=wal)
    decision = report.decision_for("txn:crash")
    assert decision.disposition is RecoveryDisposition.FULL_REPROOF
    assert decision.reason is RecoveryReason.AMBIGUOUS_PROVER
    assert wal.is_current_eligible("txn:crash") is False
    wal.close()


def test_crash_before_proof_does_not_infer_success(tmp_path: Path) -> None:
    wal = SealTransitionWal(tmp_path)

    def inject(name: str, transition_id: str, phase: Any = None) -> None:
        del transition_id, phase
        if name == "before_proof_execution":
            raise SealTransitionWalCrash(name)

    wal._crash_injector = inject
    begin_transition(wal, _intent())
    with pytest.raises(SealTransitionWalCrash):
        wal.record_phase("txn:crash", SealTransitionPhase.PROOF_EXECUTION)
    report = recover_seal_transitions(tmp_path, wal=wal)
    decision = report.decision_for("txn:crash")
    assert decision.disposition is RecoveryDisposition.RESUME
    assert decision.reason is RecoveryReason.UNSTARTED
    assert wal.is_current_eligible("txn:crash") is False
    wal.close()

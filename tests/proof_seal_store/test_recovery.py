"""Regression tests for deterministic seal-transition recovery (IPS-025).

Acceptance coverage:

* every required disposition is produced by the closed phase policy;
* external prover success is never inferred;
* recovery is idempotent across repeated restarts;
* post-CAS cleanup recognizes a committed current pointer;
* stale parent after pre-CAS seal persistence rejects publication.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    CurrentSealPointer,
    ExplicitRootRequiredError,
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
    EVIDENCE_SUBSET,
    RECOVERY_INTERFACE,
    REQUIRED_RECOVERY_DISPOSITIONS,
    AmbiguousProverPolicy,
    RecoveryDisposition,
    RecoveryPolicy,
    RecoveryReason,
    closed_recovery_disposition_values,
    disposition_for_phase,
    recover_seal_transitions,
)
from ipfs_kit_py.proof_seal_store.wal import (
    PHASE_ORDER,
    SealTransitionWal,
    begin_transition,
    record_phase,
)


def _cid(tag: bytes) -> str:
    return content_cid_for_bytes(b'{"seal-recovery":"' + tag + b'"}')


def _intent(
    *,
    transition_id: str = "txn:1",
    repository_id: str = "repo:kit",
    branch_id: str = "main",
    parent: str = "",
    generation: int = 0,
    artifact_cids: tuple[str, ...] = (),
) -> SealTransitionRecord:
    return SealTransitionRecord(
        transition_id=transition_id,
        repository_id=repository_id,
        branch_id=branch_id,
        phase=SealTransitionPhase.INTENT,
        state=SealTransitionState.OPEN,
        expected_parent_seal_cid=parent,
        generation=generation,
        artifact_cids=artifact_cids,
    )


def _wal(tmp_path: Path, **kwargs: Any) -> SealTransitionWal:
    return SealTransitionWal(tmp_path, **kwargs)


def _store(tmp_path: Path) -> HermeticProofSealStore:
    return HermeticProofSealStore(tmp_path)


def _pointers(tmp_path: Path) -> CurrentSealRepository:
    return CurrentSealRepository(tmp_path)


def _advance_to(
    wal: SealTransitionWal,
    transition_id: str,
    target: SealTransitionPhase,
    *,
    seal_cid: str | None = None,
    seal_kind: ArtifactKind = ArtifactKind.CHECKPOINT_SEAL,
    extra_artifacts: dict[SealTransitionPhase, tuple[str, ...]] | None = None,
) -> SealTransitionRecord:
    extras = extra_artifacts or {}
    current = wal.get_transition(transition_id)
    assert current is not None
    start = PHASE_ORDER.index(current.phase)
    end = PHASE_ORDER.index(target)
    record = current
    for index in range(start + 1, end + 1):
        phase = PHASE_ORDER[index]
        kwargs: dict[str, Any] = {}
        if phase in extras:
            kwargs["artifact_cids"] = extras[phase]
        if phase in {
            SealTransitionPhase.SEAL_PERSISTENCE,
            SealTransitionPhase.CURRENT_ROOT_CAS,
            SealTransitionPhase.CLEANUP,
        }:
            kwargs["new_seal_cid"] = seal_cid or _cid(b"seal")
            kwargs["new_seal_kind"] = seal_kind
        if phase is SealTransitionPhase.RECEIPT_PERSISTENCE and "artifact_cids" not in kwargs:
            kwargs["artifact_cids"] = (_cid(b"receipt"),)
        if phase is SealTransitionPhase.PROOF_EXECUTION and "artifact_cids" not in kwargs:
            kwargs["artifact_cids"] = (_cid(b"proof"),)
        if phase is SealTransitionPhase.FOREST_UPDATE and "artifact_cids" not in kwargs:
            kwargs["artifact_cids"] = (_cid(b"forest"),)
        if phase is SealTransitionPhase.AGGREGATE_GENERATION and "artifact_cids" not in kwargs:
            kwargs["artifact_cids"] = (_cid(b"aggregate"),)
        record = wal.record_phase(transition_id, phase, **kwargs)
    return record


def _pointer(
    *,
    seal_cid: str,
    generation: int = 0,
    parent_seal_cid: str = "",
    repository_id: str = "repo:kit",
    branch_id: str = "main",
) -> CurrentSealPointer:
    return CurrentSealPointer(
        repository_id=repository_id,
        branch_id=branch_id,
        seal_cid=seal_cid,
        seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        generation=generation,
        parent_seal_cid=parent_seal_cid,
    )


# ---------------------------------------------------------------------------
# Closed surface
# ---------------------------------------------------------------------------


def test_schema_and_closed_dispositions() -> None:
    assert EVIDENCE_SUBSET == "ips/transition-recovery@1"
    assert RECOVERY_INTERFACE == "recover_seal_transitions@1"
    values = closed_recovery_disposition_values()
    assert values == REQUIRED_RECOVERY_DISPOSITIONS
    assert values == {
        "resume",
        "replay",
        "verify-existing",
        "discard-uncommitted",
        "repair",
        "full-reproof",
    }


def test_explicit_root_is_mandatory() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        recover_seal_transitions(None)
    with pytest.raises(ExplicitRootRequiredError):
        recover_seal_transitions("relative/recovery")
    with pytest.raises(ExplicitRootRequiredError):
        recover_seal_transitions("~/proof-seals")


def test_phase_policy_covers_seven_failure_points() -> None:
    policy = AmbiguousProverPolicy.FULL_REPROOF
    open_state = SealTransitionState.IN_PROGRESS

    resume, reason = disposition_for_phase(
        SealTransitionPhase.INTENT,
        has_verified_artifact=False,
        pointer_matches_seal=False,
        parent_is_current=True,
        ambiguous_prover=policy,
        state=SealTransitionState.OPEN,
    )
    assert resume is RecoveryDisposition.RESUME
    assert reason is RecoveryReason.UNSTARTED

    reproof, reason = disposition_for_phase(
        SealTransitionPhase.PROOF_EXECUTION,
        has_verified_artifact=False,
        pointer_matches_seal=False,
        parent_is_current=True,
        ambiguous_prover=policy,
        state=open_state,
    )
    assert reproof is RecoveryDisposition.FULL_REPROOF
    assert reason is RecoveryReason.AMBIGUOUS_PROVER

    replay, _reason = disposition_for_phase(
        SealTransitionPhase.RECEIPT_PERSISTENCE,
        has_verified_artifact=True,
        pointer_matches_seal=False,
        parent_is_current=True,
        ambiguous_prover=policy,
        state=open_state,
    )
    assert replay is RecoveryDisposition.REPLAY

    verify_forest, _reason = disposition_for_phase(
        SealTransitionPhase.FOREST_UPDATE,
        has_verified_artifact=True,
        pointer_matches_seal=False,
        parent_is_current=True,
        ambiguous_prover=policy,
        state=open_state,
    )
    assert verify_forest is RecoveryDisposition.VERIFY_EXISTING

    verify_agg, _reason = disposition_for_phase(
        SealTransitionPhase.AGGREGATE_GENERATION,
        has_verified_artifact=True,
        pointer_matches_seal=False,
        parent_is_current=True,
        ambiguous_prover=policy,
        state=open_state,
    )
    assert verify_agg is RecoveryDisposition.VERIFY_EXISTING

    stale, reason = disposition_for_phase(
        SealTransitionPhase.SEAL_PERSISTENCE,
        has_verified_artifact=True,
        pointer_matches_seal=False,
        parent_is_current=False,
        ambiguous_prover=policy,
        state=open_state,
    )
    assert stale is RecoveryDisposition.DISCARD_UNCOMMITTED
    assert reason is RecoveryReason.STALE_PARENT

    cleanup, reason = disposition_for_phase(
        SealTransitionPhase.CURRENT_ROOT_CAS,
        has_verified_artifact=True,
        pointer_matches_seal=True,
        parent_is_current=False,
        ambiguous_prover=policy,
        state=open_state,
    )
    assert cleanup is RecoveryDisposition.REPAIR
    assert reason is RecoveryReason.POINTER_MATCHES_SEAL


# ---------------------------------------------------------------------------
# Never infer prover success
# ---------------------------------------------------------------------------


def test_ambiguous_prover_never_inferred_as_success(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    begin_transition(wal, _intent())
    record_phase(wal, "txn:1", SealTransitionPhase.PROOF_EXECUTION)
    report = recover_seal_transitions(tmp_path, wal=wal, store=_store(tmp_path))
    decision = report.decision_for("txn:1")
    assert decision.disposition is RecoveryDisposition.FULL_REPROOF
    assert decision.reason is RecoveryReason.AMBIGUOUS_PROVER
    assert decision.verified_artifact_cids == ()
    leftover = wal.get_transition("txn:1")
    assert leftover is not None
    assert leftover.state is not SealTransitionState.COMMITTED
    assert wal.is_current_eligible("txn:1") is False
    wal.close()


def test_ambiguous_prover_discard_policy_aborts(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    begin_transition(wal, _intent())
    record_phase(wal, "txn:1", SealTransitionPhase.PROOF_EXECUTION)
    report = recover_seal_transitions(
        tmp_path,
        wal=wal,
        store=_store(tmp_path),
        policy=RecoveryPolicy(
            ambiguous_prover=AmbiguousProverPolicy.DISCARD_UNCOMMITTED
        ),
    )
    decision = report.decision_for("txn:1")
    assert decision.disposition is RecoveryDisposition.DISCARD_UNCOMMITTED
    assert decision.applied is True
    aborted = wal.get_transition("txn:1")
    assert aborted is not None
    assert aborted.state is SealTransitionState.ABORTED
    assert wal.is_current_eligible("txn:1") is False
    wal.close()


def test_verified_prover_artifact_is_verify_existing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    payload = b'{"kind":"proof_object","tag":"durable-prover"}'
    reference = store.put_immutable(ArtifactKind.PROOF_OBJECT, payload)
    wal = _wal(tmp_path)
    begin_transition(wal, _intent())
    record_phase(
        wal,
        "txn:1",
        SealTransitionPhase.PROOF_EXECUTION,
        artifact_cids=(reference.cid,),
    )
    report = recover_seal_transitions(tmp_path, wal=wal, store=store)
    decision = report.decision_for("txn:1")
    assert decision.disposition is RecoveryDisposition.VERIFY_EXISTING
    assert reference.cid in decision.verified_artifact_cids
    leftover = wal.get_transition("txn:1")
    assert leftover is not None
    assert leftover.state is SealTransitionState.IN_PROGRESS
    wal.close()


def test_intent_only_resumes_unstarted_job(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    begin_transition(wal, _intent())
    report = recover_seal_transitions(tmp_path, wal=wal)
    decision = report.decision_for("txn:1")
    assert decision.disposition is RecoveryDisposition.RESUME
    assert decision.reason is RecoveryReason.UNSTARTED
    assert wal.get_transition("txn:1") is not None
    assert wal.is_current_eligible("txn:1") is False
    wal.close()


def test_receipt_phase_replays_when_receipt_rehashes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    receipt = store.put_immutable(
        ArtifactKind.PROOF_RECEIPT, b'{"kind":"proof_receipt","tag":"r1"}'
    )
    wal = _wal(tmp_path)
    begin_transition(wal, _intent())
    _advance_to(
        wal,
        "txn:1",
        SealTransitionPhase.RECEIPT_PERSISTENCE,
        extra_artifacts={
            SealTransitionPhase.RECEIPT_PERSISTENCE: (receipt.cid,),
        },
    )
    report = recover_seal_transitions(tmp_path, wal=wal, store=store)
    assert report.decision_for("txn:1").disposition is RecoveryDisposition.REPLAY
    wal.close()


# ---------------------------------------------------------------------------
# Idempotent restart
# ---------------------------------------------------------------------------


def test_repeated_recovery_converges(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    begin_transition(wal, _intent())
    record_phase(wal, "txn:1", SealTransitionPhase.PROOF_EXECUTION)
    first = recover_seal_transitions(tmp_path, wal=wal, store=_store(tmp_path))
    second = recover_seal_transitions(tmp_path, wal=wal, store=_store(tmp_path))
    assert first.decision_for("txn:1").disposition is second.decision_for(
        "txn:1"
    ).disposition
    assert first.decision_for("txn:1").reason is second.decision_for("txn:1").reason
    assert first.to_dict()["decisions"][0]["disposition"] == (
        second.to_dict()["decisions"][0]["disposition"]
    )
    wal.close()


# ---------------------------------------------------------------------------
# Post-CAS cleanup recognizes committed pointer
# ---------------------------------------------------------------------------


def test_post_cas_cleanup_recognizes_committed_pointer(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    pointers = _pointers(tmp_path)
    store = _store(tmp_path)
    seal_bytes = b'{"kind":"checkpoint_seal","tag":"cas-done"}'
    seal_ref = store.put_immutable(ArtifactKind.CHECKPOINT_SEAL, seal_bytes)
    begin_transition(wal, _intent())
    _advance_to(
        wal,
        "txn:1",
        SealTransitionPhase.CURRENT_ROOT_CAS,
        seal_cid=seal_ref.cid,
    )
    published = _pointer(seal_cid=seal_ref.cid, generation=0)
    assert pointers.compare_and_swap_current_seal(None, published) is True

    first = recover_seal_transitions(
        tmp_path, wal=wal, store=store, pointers=pointers
    )
    decision = first.decision_for("txn:1")
    assert decision.disposition is RecoveryDisposition.REPAIR
    assert decision.reason is RecoveryReason.POINTER_MATCHES_SEAL
    assert decision.pointer_recognized is True
    assert decision.applied is True
    committed = wal.get_transition("txn:1")
    assert committed is not None
    assert committed.state is SealTransitionState.COMMITTED
    assert committed.phase is SealTransitionPhase.CLEANUP
    assert wal.is_current_eligible("txn:1") is True

    second = recover_seal_transitions(
        tmp_path, wal=wal, store=store, pointers=pointers
    )
    again = second.decision_for("txn:1")
    assert again.disposition is RecoveryDisposition.REPAIR
    assert again.pointer_recognized is True
    assert again.applied is False
    current = pointers.get_current_seal("repo:kit", "main")
    assert current is not None
    assert current.seal_cid == seal_ref.cid
    wal.close()


# ---------------------------------------------------------------------------
# Stale parent rejects publication
# ---------------------------------------------------------------------------


def test_stale_parent_after_seal_persistence_rejects_publication(
    tmp_path: Path,
) -> None:
    wal = _wal(tmp_path)
    pointers = _pointers(tmp_path)
    store = _store(tmp_path)
    other = store.put_immutable(
        ArtifactKind.CHECKPOINT_SEAL, b'{"kind":"checkpoint_seal","tag":"other"}'
    )
    intended = store.put_immutable(
        ArtifactKind.CHECKPOINT_SEAL, b'{"kind":"checkpoint_seal","tag":"intended"}'
    )
    # A concurrent writer already published a different current seal.
    assert (
        pointers.compare_and_swap_current_seal(
            None, _pointer(seal_cid=other.cid, generation=0)
        )
        is True
    )
    begin_transition(wal, _intent(parent="", generation=0))
    _advance_to(
        wal,
        "txn:1",
        SealTransitionPhase.SEAL_PERSISTENCE,
        seal_cid=intended.cid,
    )
    report = recover_seal_transitions(
        tmp_path, wal=wal, store=store, pointers=pointers
    )
    decision = report.decision_for("txn:1")
    assert decision.disposition is RecoveryDisposition.DISCARD_UNCOMMITTED
    assert decision.reason is RecoveryReason.STALE_PARENT
    assert decision.publication_rejected is True
    assert decision.applied is True
    aborted = wal.get_transition("txn:1")
    assert aborted is not None
    assert aborted.state is SealTransitionState.ABORTED
    assert wal.is_current_eligible("txn:1") is False
    current = pointers.get_current_seal("repo:kit", "main")
    assert current is not None
    assert current.seal_cid == other.cid
    wal.close()


def test_stale_parent_before_cas_does_not_publish(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    pointers = _pointers(tmp_path)
    store = _store(tmp_path)
    parent = store.put_immutable(
        ArtifactKind.CHECKPOINT_SEAL, b'{"kind":"checkpoint_seal","tag":"parent"}'
    )
    winner = store.put_immutable(
        ArtifactKind.CHECKPOINT_SEAL, b'{"kind":"checkpoint_seal","tag":"winner"}'
    )
    intended = store.put_immutable(
        ArtifactKind.CHECKPOINT_SEAL, b'{"kind":"checkpoint_seal","tag":"lost"}'
    )
    assert (
        pointers.compare_and_swap_current_seal(
            None, _pointer(seal_cid=parent.cid, generation=0)
        )
        is True
    )
    assert (
        pointers.compare_and_swap_current_seal(
            _pointer(seal_cid=parent.cid, generation=0),
            _pointer(seal_cid=winner.cid, generation=1, parent_seal_cid=parent.cid),
        )
        is True
    )
    begin_transition(wal, _intent(parent=parent.cid, generation=1))
    _advance_to(
        wal,
        "txn:1",
        SealTransitionPhase.CURRENT_ROOT_CAS,
        seal_cid=intended.cid,
    )
    report = recover_seal_transitions(
        tmp_path, wal=wal, store=store, pointers=pointers
    )
    decision = report.decision_for("txn:1")
    assert decision.publication_rejected is True
    assert decision.disposition is RecoveryDisposition.DISCARD_UNCOMMITTED
    current = pointers.get_current_seal("repo:kit", "main")
    assert current is not None
    assert current.seal_cid == winner.cid
    assert wal.is_current_eligible("txn:1") is False
    wal.close()


# ---------------------------------------------------------------------------
# Restart after close uses durable state only
# ---------------------------------------------------------------------------


def test_recover_after_process_restart_reads_durable_wal(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    begin_transition(wal, _intent(transition_id="txn:restart"))
    record_phase(wal, "txn:restart", SealTransitionPhase.PROOF_EXECUTION)
    wal.close()

    first = recover_seal_transitions(tmp_path)
    second = recover_seal_transitions(tmp_path)
    assert first.decision_for("txn:restart").disposition is RecoveryDisposition.FULL_REPROOF
    assert second.decision_for("txn:restart").disposition is RecoveryDisposition.FULL_REPROOF
    assert first.decision_for("txn:restart").to_dict()["phase"] == "proof_execution"


def test_empty_root_recovers_with_no_decisions(tmp_path: Path) -> None:
    report = recover_seal_transitions(tmp_path)
    assert report.decisions == ()
    assert report.repaired_tail is False

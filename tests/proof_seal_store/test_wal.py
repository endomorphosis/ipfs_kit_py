"""Regression tests for the WAL-backed seal transition state machine (IPS-024).

Acceptance coverage:

* partial / uncommitted records cannot become current;
* committed replay is deterministic across restarts;
* corrupt tail preserves the verified valid prefix;
* durable intent precedes phase effects;
* phase order is fail-closed;
* crash-injection hooks fire at named boundaries.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ExplicitRootRequiredError,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
)
from ipfs_kit_py.proof_seal_store.local_store import content_cid_for_bytes
from ipfs_kit_py.proof_seal_store.wal import (
    CRASH_BOUNDARIES,
    EVIDENCE_SUBSET,
    PHASE_ORDER,
    WAL_STORE_INTERFACE,
    CommittedTransitionView,
    SealTransitionWal,
    SealTransitionWalCrash,
    SealTransitionWalStateError,
    WalDisposition,
    WalEntryKind,
    WalReason,
    abort_transition,
    begin_transition,
    commit_transition,
    committed_transition_views,
    frame_bytes,
    is_current_eligible,
    next_phase,
    phase_index,
    record_phase,
    recover_wal_bytes,
)


def _cid(tag: bytes) -> str:
    return content_cid_for_bytes(b'{"seal-wal":"' + tag + b'"}')


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


def _advance_to(
    wal: SealTransitionWal,
    transition_id: str,
    target: SealTransitionPhase,
    *,
    seal_cid: str | None = None,
    seal_kind: ArtifactKind = ArtifactKind.CHECKPOINT_SEAL,
) -> SealTransitionRecord:
    """Advance phase-by-phase from the current position up to ``target``."""

    current = wal.get_transition(transition_id)
    assert current is not None
    start = phase_index(current.phase)
    end = phase_index(target)
    record = current
    for index in range(start + 1, end + 1):
        phase = PHASE_ORDER[index]
        kwargs: dict[str, Any] = {}
        if phase in {
            SealTransitionPhase.SEAL_PERSISTENCE,
            SealTransitionPhase.CURRENT_ROOT_CAS,
            SealTransitionPhase.CLEANUP,
        }:
            kwargs["new_seal_cid"] = seal_cid or _cid(b"seal")
            kwargs["new_seal_kind"] = seal_kind
        if phase is SealTransitionPhase.RECEIPT_PERSISTENCE:
            kwargs["artifact_cids"] = (_cid(b"receipt"),)
        if phase is SealTransitionPhase.PROOF_EXECUTION:
            kwargs["artifact_cids"] = (_cid(b"proof"),)
        if phase is SealTransitionPhase.FOREST_UPDATE:
            kwargs["artifact_cids"] = (_cid(b"forest"),)
        if phase is SealTransitionPhase.AGGREGATE_GENERATION:
            kwargs["artifact_cids"] = (_cid(b"aggregate"),)
        record = wal.record_phase(transition_id, phase, **kwargs)
    return record


# ---------------------------------------------------------------------------
# Construction / constants
# ---------------------------------------------------------------------------


def test_schema_and_evidence_constants() -> None:
    assert EVIDENCE_SUBSET == "ips/seal-transition-wal@1"
    assert WAL_STORE_INTERFACE == "SealTransitionWal@1"
    assert "before_begin" in CRASH_BOUNDARIES
    assert "after_current_root_cas" in CRASH_BOUNDARIES
    assert PHASE_ORDER[0] is SealTransitionPhase.INTENT
    assert PHASE_ORDER[-1] is SealTransitionPhase.CLEANUP


def test_explicit_root_is_mandatory() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        SealTransitionWal(None)
    with pytest.raises(ExplicitRootRequiredError):
        SealTransitionWal("relative/wal")
    with pytest.raises(ExplicitRootRequiredError):
        SealTransitionWal("~/seal-wal")


def test_phase_helpers() -> None:
    assert phase_index(SealTransitionPhase.INTENT) == 0
    assert next_phase(SealTransitionPhase.INTENT) is SealTransitionPhase.PROOF_EXECUTION
    assert next_phase(SealTransitionPhase.CLEANUP) is None


# ---------------------------------------------------------------------------
# Happy path: begin / phase / commit / abort
# ---------------------------------------------------------------------------


def test_begin_record_commit_round_trip(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    begun = begin_transition(wal, _intent())
    assert begun.phase is SealTransitionPhase.INTENT
    assert begun.state is SealTransitionState.OPEN
    assert begun.transition_id == "txn:1"

    seal = _cid(b"new-seal")
    advanced = _advance_to(
        wal, "txn:1", SealTransitionPhase.CURRENT_ROOT_CAS, seal_cid=seal
    )
    assert advanced.phase is SealTransitionPhase.CURRENT_ROOT_CAS
    assert advanced.state is SealTransitionState.IN_PROGRESS
    assert advanced.new_seal_cid == seal

    committed = commit_transition(
        wal,
        "txn:1",
        new_seal_cid=seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        phase=SealTransitionPhase.CLEANUP,
    )
    assert committed.state is SealTransitionState.COMMITTED
    assert committed.phase is SealTransitionPhase.CLEANUP
    assert wal.is_current_eligible("txn:1") is True
    views = wal.current_eligible_seals("repo:kit", "main")
    assert len(views) == 1
    assert views[0].new_seal_cid == seal
    wal.close()


def test_module_level_aliases_and_abort(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    begin_transition(wal, _intent(transition_id="txn:abort"))
    record_phase(wal, "txn:abort", SealTransitionPhase.PROOF_EXECUTION)
    aborted = abort_transition(wal, "txn:abort")
    assert aborted.state is SealTransitionState.ABORTED
    assert wal.is_current_eligible("txn:abort") is False
    assert wal.committed_transitions() == ()
    assert wal.open_transitions() == ()
    wal.close()


def test_duplicate_begin_rejected(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent(transition_id="txn:dup"))
    result = wal.begin_transition_result(_intent(transition_id="txn:dup"))
    assert result.disposition is WalDisposition.REJECTED
    assert result.reason is WalReason.ALREADY_EXISTS
    wal.close()


def test_phase_skip_and_regression_rejected(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent())
    with pytest.raises(SealTransitionWalStateError):
        wal.record_phase("txn:1", SealTransitionPhase.FOREST_UPDATE)
    wal.record_phase("txn:1", SealTransitionPhase.PROOF_EXECUTION)
    result = wal.record_phase_result("txn:1", SealTransitionPhase.INTENT)
    assert result.disposition is WalDisposition.REJECTED
    assert result.reason is WalReason.PHASE_ORDER
    wal.close()


def test_commit_without_seal_rejected(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent())
    result = wal.commit_transition_result("txn:1")
    assert result.disposition is WalDisposition.REJECTED
    assert result.reason is WalReason.MISSING_SEAL
    wal.close()


def test_abort_of_committed_rejected(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent())
    seal = _cid(b"s")
    _advance_to(wal, "txn:1", SealTransitionPhase.SEAL_PERSISTENCE, seal_cid=seal)
    wal.commit_transition(
        "txn:1",
        new_seal_cid=seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    result = wal.abort_transition_result("txn:1")
    assert result.disposition is WalDisposition.REJECTED
    assert result.reason is WalReason.ALREADY_TERMINAL
    wal.close()


# ---------------------------------------------------------------------------
# Acceptance: partial/uncommitted cannot become current
# ---------------------------------------------------------------------------


def test_partial_uncommitted_records_cannot_become_current(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    seal = _cid(b"partial-seal")

    # Open intent only.
    wal.begin_transition(_intent(transition_id="txn:open"))
    assert wal.is_current_eligible("txn:open") is False

    # Advanced through seal persistence with a seal CID bound, but not committed.
    wal.begin_transition(_intent(transition_id="txn:partial"))
    _advance_to(
        wal,
        "txn:partial",
        SealTransitionPhase.SEAL_PERSISTENCE,
        seal_cid=seal,
    )
    partial = wal.get_transition("txn:partial")
    assert partial is not None
    assert partial.new_seal_cid == seal
    assert partial.state is SealTransitionState.IN_PROGRESS
    assert wal.is_current_eligible("txn:partial") is False

    # Aborted after CAS phase still cannot become current.
    wal.begin_transition(_intent(transition_id="txn:aborted"))
    _advance_to(
        wal,
        "txn:aborted",
        SealTransitionPhase.CURRENT_ROOT_CAS,
        seal_cid=_cid(b"aborted-seal"),
    )
    wal.abort_transition("txn:aborted")
    assert wal.is_current_eligible("txn:aborted") is False

    # Only a fully committed transition is eligible.
    wal.begin_transition(_intent(transition_id="txn:ok"))
    committed_seal = _cid(b"ok-seal")
    _advance_to(
        wal,
        "txn:ok",
        SealTransitionPhase.CURRENT_ROOT_CAS,
        seal_cid=committed_seal,
    )
    wal.commit_transition(
        "txn:ok",
        new_seal_cid=committed_seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        phase=SealTransitionPhase.CLEANUP,
    )

    eligible = wal.current_eligible_seals()
    assert [view.transition_id for view in eligible] == ["txn:ok"]
    assert all(view.is_current_eligible for view in eligible)
    assert is_current_eligible(wal.entries(), "txn:partial") is False
    assert is_current_eligible(wal.entries(), "txn:ok") is True

    # Pure projection over entries agrees.
    projected = committed_transition_views(wal.entries())
    assert len(projected) == 1
    assert projected[0].new_seal_cid == committed_seal
    wal.close()


def test_commit_without_begin_never_becomes_current(tmp_path: Path) -> None:
    """A synthetic commit frame without durable intent is ignored for current."""

    wal = _wal(tmp_path)
    # Manually craft entries via a second path: only begin+commit pairs count.
    # Using the public API, commit without begin is rejected.
    result = wal.commit_transition_result(
        "missing",
        new_seal_cid=_cid(b"x"),
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    assert result.disposition is WalDisposition.REJECTED
    assert result.reason is WalReason.NOT_FOUND
    assert wal.current_eligible_seals() == ()
    wal.close()


# ---------------------------------------------------------------------------
# Acceptance: committed replay is deterministic
# ---------------------------------------------------------------------------


def test_committed_replay_is_deterministic_across_restarts(tmp_path: Path) -> None:
    seal_a = _cid(b"seal-a")
    seal_b = _cid(b"seal-b")

    with _wal(tmp_path) as wal:
        for transition_id, seal, generation in (
            ("txn:a", seal_a, 0),
            ("txn:b", seal_b, 1),
        ):
            wal.begin_transition(
                _intent(
                    transition_id=transition_id,
                    parent="" if generation == 0 else seal_a,
                    generation=generation,
                )
            )
            _advance_to(
                wal,
                transition_id,
                SealTransitionPhase.CURRENT_ROOT_CAS,
                seal_cid=seal,
                seal_kind=(
                    ArtifactKind.CHECKPOINT_SEAL
                    if generation == 0
                    else ArtifactKind.DELTA_SEAL
                ),
            )
            wal.commit_transition(
                transition_id,
                new_seal_cid=seal,
                new_seal_kind=(
                    ArtifactKind.CHECKPOINT_SEAL
                    if generation == 0
                    else ArtifactKind.DELTA_SEAL
                ),
                phase=SealTransitionPhase.CLEANUP,
            )
        first = wal.replay_committed()
        first_dicts = [view.to_dict() for view in first]

    with _wal(tmp_path) as reopened:
        second = reopened.replay_committed()
        second_dicts = [view.to_dict() for view in second]
        third = reopened.replay_committed()
        third_dicts = [view.to_dict() for view in third]

    assert first_dicts == second_dicts == third_dicts
    assert [view.transition_id for view in first] == ["txn:a", "txn:b"]
    assert first[0].new_seal_cid == seal_a
    assert first[1].new_seal_cid == seal_b
    # Sequence order is stable and strictly increasing.
    assert first[0].sequence < first[1].sequence
    assert all(isinstance(view, CommittedTransitionView) for view in first)


def test_idempotent_commit_and_abort(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent(transition_id="txn:idem"))
    seal = _cid(b"idem")
    _advance_to(wal, "txn:idem", SealTransitionPhase.SEAL_PERSISTENCE, seal_cid=seal)
    first = wal.commit_transition(
        "txn:idem",
        new_seal_cid=seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    second = wal.commit_transition_result(
        "txn:idem",
        new_seal_cid=seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    assert second.disposition is WalDisposition.COMMITTED
    assert second.diagnostics.get("idempotent") is True
    assert second.record == first

    wal.begin_transition(_intent(transition_id="txn:ab-idem"))
    aborted = wal.abort_transition("txn:ab-idem")
    again = wal.abort_transition_result("txn:ab-idem")
    assert again.disposition is WalDisposition.ABORTED
    assert again.diagnostics.get("idempotent") is True
    assert again.record == aborted
    wal.close()


# ---------------------------------------------------------------------------
# Acceptance: corrupt tail preserves valid prefix
# ---------------------------------------------------------------------------


def test_corrupt_tail_preserves_valid_prefix(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    seal = _cid(b"prefix-seal")
    wal.begin_transition(_intent(transition_id="txn:prefix"))
    _advance_to(
        wal, "txn:prefix", SealTransitionPhase.SEAL_PERSISTENCE, seal_cid=seal
    )
    wal.commit_transition(
        "txn:prefix",
        new_seal_cid=seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    # Uncommitted second transition still in the valid prefix.
    wal.begin_transition(_intent(transition_id="txn:open-tail"))
    wal.record_phase("txn:open-tail", SealTransitionPhase.PROOF_EXECUTION)
    valid_entries = wal.entries()
    valid_count = len(valid_entries)
    segment = wal.segment_path
    wal.close()

    original = segment.read_bytes()
    # Torn tail: incomplete magic / garbage after the valid prefix.
    segment.write_bytes(original + b"\x00\x01TORN-TAIL-GARBAGE")

    scanned = recover_wal_bytes(segment.read_bytes())
    assert scanned.tail_corrupt is True
    assert scanned.valid_bytes == len(original)
    assert len(scanned.entries) == valid_count
    assert [entry.record.transition_id for entry in scanned.entries[:1]] == [
        "txn:prefix"
    ]

    # Reopen: valid prefix retained; committed still eligible; refuse append.
    reopened = _wal(tmp_path)
    assert reopened.is_current_eligible("txn:prefix") is True
    assert reopened.is_current_eligible("txn:open-tail") is False
    assert len(reopened.entries()) == valid_count
    scan = reopened.scan()
    assert scan.tail_corrupt is True
    assert scan.valid_bytes == len(original)

    # Append is refused while torn tail remains.
    result = reopened.begin_transition_result(_intent(transition_id="txn:after-corrupt"))
    assert result.disposition is WalDisposition.ERROR
    assert result.reason is WalReason.CORRUPTED

    # Truncate restores append capability while preserving the prefix.
    cleaned = reopened.recover_and_truncate_tail()
    assert cleaned.tail_corrupt is False
    assert cleaned.valid_bytes == len(original)
    assert segment.stat().st_size == len(original)
    assert reopened.is_current_eligible("txn:prefix") is True
    reopened.begin_transition(_intent(transition_id="txn:after-repair"))
    assert reopened.get_transition("txn:after-repair") is not None
    reopened.close()


def test_checksum_mismatch_is_corrupt_tail_not_prefix_loss(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent(transition_id="txn:good"))
    wal.begin_transition(_intent(transition_id="txn:will-corrupt"))
    entries = wal.entries()
    wal.close()

    # Rebuild segment: keep first frame intact, flip a byte in the second digest.
    frames = [frame_bytes(entry) for entry in entries]
    first = frames[0]
    second = bytearray(frames[1])
    second[-1] ^= 0xFF
    segment = tmp_path / "seal_wal" / "transitions.stwal"
    segment.write_bytes(first + bytes(second))

    scanned = recover_wal_bytes(segment.read_bytes())
    assert scanned.tail_corrupt is True
    assert scanned.error == "frame checksum mismatch"
    assert len(scanned.entries) == 1
    assert scanned.entries[0].record.transition_id == "txn:good"
    assert scanned.valid_bytes == len(first)


def test_short_frame_payload_preserves_prefix(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent())
    frame = frame_bytes(wal.entries()[0])
    wal.close()
    segment = tmp_path / "seal_wal" / "transitions.stwal"
    # Valid frame + a new magic and length claiming a large payload that is missing.
    torn = frame + b"STWAL1" + struct.pack(">I", 100) + b"short"
    segment.write_bytes(torn)
    scanned = recover_wal_bytes(segment.read_bytes())
    assert scanned.tail_corrupt is True
    assert "short frame" in scanned.error
    assert len(scanned.entries) == 1
    assert scanned.valid_bytes == len(frame)


# ---------------------------------------------------------------------------
# Crash injection hooks
# ---------------------------------------------------------------------------


def test_crash_injector_fires_at_begin_and_commit(tmp_path: Path) -> None:
    seen: list[str] = []

    def inject(name: str, transition_id: str, phase: Any = None) -> None:
        del phase
        seen.append(name)
        if name == "before_commit" and transition_id == "txn:crash":
            raise SealTransitionWalCrash(name)

    wal = _wal(tmp_path, crash_injector=inject)
    wal.begin_transition(_intent(transition_id="txn:crash"))
    assert "before_begin" in seen
    assert "after_begin" in seen
    seal = _cid(b"crash-seal")
    _advance_to(
        wal, "txn:crash", SealTransitionPhase.SEAL_PERSISTENCE, seal_cid=seal
    )
    with pytest.raises(SealTransitionWalCrash):
        wal.commit_transition(
            "txn:crash",
            new_seal_cid=seal,
            new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        )
    # Commit never became durable, so not current-eligible.
    assert wal.is_current_eligible("txn:crash") is False
    assert wal.get_transition("txn:crash") is not None
    assert wal.get_transition("txn:crash").state is not SealTransitionState.COMMITTED
    wal.close()


def test_phase_boundary_injection_names(tmp_path: Path) -> None:
    seen: list[str] = []

    def inject(name: str, transition_id: str, phase: Any = None) -> None:
        del transition_id, phase
        seen.append(name)

    wal = _wal(tmp_path, crash_injector=inject)
    wal.begin_transition(_intent())
    wal.record_phase("txn:1", SealTransitionPhase.PROOF_EXECUTION)
    assert "before_proof_execution" in seen
    assert "after_proof_execution" in seen
    assert "before_phase" in seen
    assert "after_phase" in seen
    wal.close()


# ---------------------------------------------------------------------------
# Durability / identity surface
# ---------------------------------------------------------------------------


def test_entries_rehash_and_frame_identity(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent(artifact_cids=(_cid(b"a1"),)))
    entry = wal.entries()[0]
    assert entry.kind is WalEntryKind.BEGIN
    frame = frame_bytes(entry)
    assert frame.startswith(b"STWAL1")
    # Digest binds exact payload.
    payload_len = struct.unpack(">I", frame[6:10])[0]
    payload = frame[10 : 10 + payload_len]
    digest = frame[10 + payload_len :]
    assert hashlib.sha256(payload).digest() == digest
    assert entry.canonical_bytes() == payload
    wal.close()


def test_open_transitions_excludes_terminal(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    wal.begin_transition(_intent(transition_id="txn:open"))
    wal.begin_transition(_intent(transition_id="txn:done"))
    seal = _cid(b"done")
    _advance_to(wal, "txn:done", SealTransitionPhase.SEAL_PERSISTENCE, seal_cid=seal)
    wal.commit_transition(
        "txn:done",
        new_seal_cid=seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    open_ids = {record.transition_id for record in wal.open_transitions()}
    assert open_ids == {"txn:open"}
    wal.close()


def test_artifact_cids_accumulate_across_phases(tmp_path: Path) -> None:
    wal = _wal(tmp_path)
    proof = _cid(b"proof")
    receipt = _cid(b"receipt")
    wal.begin_transition(_intent())
    wal.record_phase(
        "txn:1",
        SealTransitionPhase.PROOF_EXECUTION,
        artifact_cids=(proof,),
    )
    mid = wal.record_phase(
        "txn:1",
        SealTransitionPhase.RECEIPT_PERSISTENCE,
        artifact_cids=(receipt,),
    )
    assert mid.artifact_cids == (proof, receipt)
    # Re-recording same phase with a duplicate CID is idempotent on the set.
    same = wal.record_phase(
        "txn:1",
        SealTransitionPhase.RECEIPT_PERSISTENCE,
        artifact_cids=(proof,),
    )
    assert same.artifact_cids == (proof, receipt)
    wal.close()

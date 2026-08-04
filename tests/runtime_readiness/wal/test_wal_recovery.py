"""Runtime-readiness coverage for replay, checkpoints, and WAL recovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.core.wal import checkpoint as checkpoint_module
from ipfs_kit_py.core.wal.checkpoint import (
    CheckpointStore,
    WALArchiveError,
    archive_completed,
    create_checkpoint,
)
from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALRecord,
    WALRecordKind,
    WALRecordState,
    make_committed_record,
)
from ipfs_kit_py.core.wal.recovery import (
    WALNonIdempotentHandlerError,
    WALRecovery,
)
from ipfs_kit_py.core.wal.segments import WALSegmentFile, recover_segment


GENERATION = "recovery-generation"


def _append_transaction(
    path: Path,
    *,
    segment_id: str,
    first_sequence: int,
    transaction_id: str,
    effect_key: str,
    seal: bool,
) -> object:
    """Append a complete transaction and return its descriptor when sealed."""

    segment = WALSegmentFile(
        path,
        generation_id=GENERATION,
        segment_id=segment_id,
        first_sequence=first_sequence,
    )
    try:
        segment.append(
            WALRecord(
                generation_id=GENERATION,
                sequence_number=first_sequence,
                kind=WALRecordKind.BEGIN,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id=transaction_id,
                segment_id=segment_id,
            )
        )
        segment.append(
            WALRecord(
                generation_id=GENERATION,
                sequence_number=first_sequence + 1,
                kind=WALRecordKind.MUTATE,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id=transaction_id,
                segment_id=segment_id,
                record_key=effect_key,
            )
        )
        segment.append(
            make_committed_record(
                generation_id=GENERATION,
                sequence_number=first_sequence + 2,
                transaction_id=transaction_id,
                fsync_receipt_id=f"fsync-{effect_key}",
                segment_id=segment_id,
            )
        )
        return segment.seal() if seal else segment.descriptor
    finally:
        segment.close()


def _append_incomplete_transaction(
    path: Path, *, segment_id: str, first_sequence: int
) -> None:
    segment = WALSegmentFile(
        path,
        generation_id=GENERATION,
        segment_id=segment_id,
        first_sequence=first_sequence,
    )
    try:
        segment.append(
            WALRecord(
                generation_id=GENERATION,
                sequence_number=first_sequence,
                kind=WALRecordKind.BEGIN,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id="incomplete",
                segment_id=segment_id,
            )
        )
        segment.append(
            WALRecord(
                generation_id=GENERATION,
                sequence_number=first_sequence + 1,
                kind=WALRecordKind.MUTATE,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id="incomplete",
                segment_id=segment_id,
                record_key="must-not-run",
            )
        )
    finally:
        segment.close()


def test_recovery_replays_only_fully_committed_transactions_once(tmp_path: Path) -> None:
    complete = tmp_path / "complete.wal"
    incomplete = tmp_path / "incomplete.wal"
    _append_transaction(
        complete,
        segment_id="complete-segment",
        first_sequence=0,
        transaction_id="complete",
        effect_key="apply-once",
        seal=False,
    )
    _append_incomplete_transaction(
        incomplete, segment_id="incomplete-segment", first_sequence=3
    )

    applied: list[str] = []
    ledger = tmp_path / "effects.json"
    first = WALRecovery((complete, incomplete), effect_ledger=ledger).recover(
        lambda record: applied.append(record.record_key)
    )
    second = WALRecovery((complete, incomplete), effect_ledger=ledger).recover(
        lambda record: applied.append(record.record_key)
    )

    assert applied == ["apply-once"]
    assert first.committed_transactions == ("complete",)
    assert first.replayed_count == 1
    assert second.replayed_count == 0
    assert second.skipped_effect_keys == ("apply-once",)


def test_non_idempotent_handlers_need_verified_reconciliation(tmp_path: Path) -> None:
    path = tmp_path / "transaction.wal"
    _append_transaction(
        path,
        segment_id="transaction-segment",
        first_sequence=0,
        transaction_id="transaction",
        effect_key="external-effect",
        seal=False,
    )
    recovery = WALRecovery(path, effect_ledger=tmp_path / "effects.json")
    with pytest.raises(WALNonIdempotentHandlerError):
        recovery.recover(lambda record: None, handler_idempotent=False)

    externally_applied: set[str] = set()

    def apply(record: WALRecord) -> None:
        externally_applied.add(record.record_key)

    def reconciled(key: str, record: WALRecord) -> bool:
        assert record.record_key == key
        return key in externally_applied

    first = recovery.recover(
        apply,
        handler_idempotent=False,
        effect_key=lambda record: record.record_key,
        reconciliation=reconciled,
    )
    second = WALRecovery(path, effect_ledger=tmp_path / "effects.json").recover(
        apply,
        handler_idempotent=False,
        effect_key=lambda record: record.record_key,
        reconciliation=reconciled,
    )

    assert first.replayed_count == 1
    assert second.replayed_count == 0
    assert externally_applied == {"external-effect"}


def test_checkpoint_binds_exact_sealed_segments_and_keeps_later_append(tmp_path: Path) -> None:
    covered_path = tmp_path / "covered.wal"
    covered = _append_transaction(
        covered_path,
        segment_id="covered-segment",
        first_sequence=0,
        transaction_id="covered",
        effect_key="already-compacted",
        seal=True,
    )
    bundle = create_checkpoint(
        "checkpoint-1", GENERATION, [covered], state=b"compacted state"
    )
    published = CheckpointStore(tmp_path / "checkpoint-store").publish(
        bundle, b"compacted state"
    )

    later_path = tmp_path / "later.wal"
    _append_transaction(
        later_path,
        segment_id="later-segment",
        first_sequence=3,
        transaction_id="later",
        effect_key="must-not-be-skipped",
        seal=False,
    )
    applied: list[str] = []
    receipt = WALRecovery((covered_path, later_path), checkpoint=published).recover(
        lambda record: applied.append(record.record_key)
    )

    assert applied == ["must-not-be-skipped"]
    assert receipt.committed_transactions == ("later",)


def test_compacted_state_pointer_is_atomic_when_publication_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    segment_path = tmp_path / "segment.wal"
    segment = _append_transaction(
        segment_path,
        segment_id="segment",
        first_sequence=0,
        transaction_id="transaction",
        effect_key="effect",
        seal=True,
    )
    store = CheckpointStore(tmp_path / "checkpoint-store")
    initial = create_checkpoint("checkpoint-1", GENERATION, [segment], state=b"before")
    store.publish(initial, b"before")
    replacement = create_checkpoint(
        "checkpoint-2",
        GENERATION,
        [segment],
        state=b"after",
        previous_checkpoint_id="checkpoint-1",
    )
    real_atomic_write = checkpoint_module._atomic_write

    def fail_at_pointer(path: Path, data: bytes) -> None:
        if path == store.current_path:
            raise OSError("injected pointer publication failure")
        real_atomic_write(path, data)

    monkeypatch.setattr(checkpoint_module, "_atomic_write", fail_at_pointer)
    with pytest.raises(OSError, match="pointer publication"):
        store.publish(replacement, b"after")

    loaded = store.load_current()
    assert loaded is not None
    loaded_bundle, state = loaded
    assert loaded_bundle.checkpoint.checkpoint_id == "checkpoint-1"
    assert state == b"before"


def test_completed_sources_are_not_deleted_until_archive_is_durable(tmp_path: Path) -> None:
    completed = tmp_path / "completed.wal"
    missing = tmp_path / "missing.wal"
    completed.write_bytes(b"complete WAL bytes")

    with pytest.raises(WALArchiveError):
        archive_completed(
            (completed, missing), tmp_path / "archive", delete_source=True
        )

    assert completed.exists()
    receipt = archive_completed((completed,), tmp_path / "archive", delete_source=True)
    assert receipt.archived_paths
    assert not completed.exists()


def test_torn_tail_is_bounded_and_valid_prefix_remains_replayable(tmp_path: Path) -> None:
    path = tmp_path / "torn.wal"
    _append_transaction(
        path,
        segment_id="torn-segment",
        first_sequence=0,
        transaction_id="transaction",
        effect_key="valid-prefix",
        seal=True,
    )
    with path.open("ab") as stream:
        stream.write(b"partial-frame")

    applied: list[str] = []
    receipt = WALRecovery(path).recover(lambda record: applied.append(record.record_key))
    recovered = recover_segment(path)

    assert applied == ["valid-prefix"]
    assert receipt.corruption_issues
    assert receipt.corruption_issues[0].valid_bytes > 0
    assert recovered.tail_corrupt
    assert [record.record_key for record in recovered.records if record.kind is WALRecordKind.MUTATE] == [
        "valid-prefix"
    ]

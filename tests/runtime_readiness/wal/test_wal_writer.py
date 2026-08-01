"""Runtime-readiness tests for the durable WAL append path."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest

from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALCorruptionDisposition,
    WALRecord,
    WALRecordKind,
    WALRecordState,
    WALSegmentState,
)
from ipfs_kit_py.core.wal.segments import (
    WALSegmentFile,
    WALSegmentSealedError,
    recover_segment,
)
from ipfs_kit_py.core.wal.writer import (
    GroupCommitPolicy,
    WALAppendCancelled,
    WALQueueFullError,
    WALShutdownIncompleteError,
    WALWriter,
    WALWriterError,
)


class RecordingDurability:
    """Portable durability spy: no test relies on host fsync implementation."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.fail_parent = False

    def write(self, handle: object, data: bytes) -> int:
        self.events.append("write")
        return handle.write(data)  # type: ignore[union-attr]

    def flush(self, handle: object) -> None:
        self.events.append("flush")
        handle.flush()  # type: ignore[union-attr]

    def fsync_file(self, handle: object) -> None:
        self.events.append("file")

    def fsync_directory(self, directory: Path) -> None:
        self.events.append("parent")
        if self.fail_parent:
            raise OSError("injected parent fsync failure")


class BlockingDurability(RecordingDurability):
    def __init__(self) -> None:
        super().__init__()
        self.write_started = threading.Event()
        self.release_write = threading.Event()

    def write(self, handle: object, data: bytes) -> int:
        self.write_started.set()
        assert self.release_write.wait(5), "test did not release blocked WAL write"
        return super().write(handle, data)


def test_acknowledgements_follow_the_requested_durability_boundary(tmp_path: Path) -> None:
    durability = RecordingDurability()
    writer = WALWriter(tmp_path, durability=durability)
    try:
        appended = writer.append(
            acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED
        )
        assert appended.record.state is WALRecordState.APPENDED
        assert appended.append_observed
        assert durability.events == ["write"]

        file_synced = writer.append(
            acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC
        )
        assert file_synced.record.state is WALRecordState.FILE_SYNCED
        assert file_synced.fsync_receipt is not None
        assert file_synced.fsync_receipt.file_fsync_observed
        assert not file_synced.fsync_receipt.parent_directory_fsync_observed
        assert durability.events[-2:] == ["flush", "file"]

        parent_synced = writer.append(
            acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC_PARENT
        )
        assert parent_synced.record.state is WALRecordState.PARENT_SYNCED
        assert parent_synced.durable
        assert parent_synced.fsync_receipt is not None
        assert parent_synced.fsync_receipt.parent_directory_fsync_observed
        assert durability.events[-3:] == ["flush", "file", "parent"]
    finally:
        writer.close()


def test_group_commit_flushes_one_batch_before_all_durable_acks(tmp_path: Path) -> None:
    durability = RecordingDurability()
    writer = WALWriter(
        tmp_path,
        durability=durability,
        policy=GroupCommitPolicy(max_delay_seconds=0.05, max_batch_size=8),
    )
    try:
        tickets = [
            writer.submit(acknowledgement_mode=WALAcknowledgementMode.GROUP_COMMIT)
            for _ in range(4)
        ]
        results = [ticket.future.result(timeout=2) for ticket in tickets]
        assert [result.record.sequence_number for result in results] == [0, 1, 2, 3]
        assert all(result.durable for result in results)
        assert durability.events.count("flush") == 1
        assert durability.events.count("file") == 1
        assert durability.events.count("parent") == 1
    finally:
        writer.close()


def test_parent_fsync_failure_refuses_ack_and_shutdown_reports_incomplete(
    tmp_path: Path,
) -> None:
    durability = RecordingDurability()
    durability.fail_parent = True
    writer = WALWriter(tmp_path, durability=durability)
    with pytest.raises(WALWriterError):
        writer.append(
            acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC_PARENT,
            timeout=2,
        )
    assert "file" in durability.events
    assert "parent" in durability.events
    with pytest.raises(WALShutdownIncompleteError):
        writer.close()

    # The failed close leaves a stopped worker and permits a retry once the
    # actual durability boundary is available again.
    durability.fail_parent = False
    writer.close()
    assert writer.closed
    assert not writer._worker.is_alive()


def test_concurrent_appends_receive_unique_ordered_sequence_ids(tmp_path: Path) -> None:
    writer = WALWriter(
        tmp_path,
        policy=GroupCommitPolicy(max_delay_seconds=0.02, max_batch_size=32),
    )
    barrier = threading.Barrier(17)

    def append_from_worker(_: int) -> int:
        barrier.wait()
        return writer.append(
            acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC
        ).record.sequence_number

    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(append_from_worker, item) for item in range(16)]
            barrier.wait()
            sequence_ids = [future.result(timeout=5) for future in futures]
        assert sorted(sequence_ids) == list(range(16))
        recovered = recover_segment(next(tmp_path.glob("*.wal")))
        assert [record.sequence_number for record in recovered.records] == list(range(16))
    finally:
        writer.close()


def test_rotation_seals_checkpointed_segment_before_new_appends(tmp_path: Path) -> None:
    writer = WALWriter(tmp_path)
    try:
        first = writer.append(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
        checkpoint = writer.rotate(checkpoint_id="checkpoint-1")
        assert checkpoint is not None
        assert checkpoint.state is WALSegmentState.CHECKPOINTED
        assert checkpoint.sealed
        second = writer.append(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
        assert first.record.segment_id != second.record.segment_id
        assert all(segment.sealed for segment in writer.sealed_segments)
    finally:
        writer.close()

    segment = WALSegmentFile(
        tmp_path / "direct.wal",
        generation_id="generation-direct",
        segment_id="segment-direct",
    )
    record = WALRecord(
        generation_id="generation-direct",
        sequence_number=0,
        kind=WALRecordKind.MUTATE,
        state=WALRecordState.APPENDED,
        acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
        segment_id="segment-direct",
    )
    segment.append(record)
    sealed = segment.checkpoint("checkpoint-direct")
    assert sealed.state is WALSegmentState.CHECKPOINTED
    with pytest.raises(WALSegmentSealedError):
        segment.append(record)


def test_torn_tail_preserves_verified_prefix_and_can_be_durably_truncated(
    tmp_path: Path,
) -> None:
    durability = RecordingDurability()
    writer = WALWriter(tmp_path, durability=durability)
    try:
        writer.append(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
        writer.append(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
    finally:
        writer.close()

    path = next(tmp_path.glob("*.wal"))
    valid_size = path.stat().st_size
    with path.open("ab") as handle:
        handle.write(b"IWAL1\x00\x00")
    recovery = recover_segment(path)
    assert recovery.tail_corrupt
    assert recovery.valid_bytes == valid_size
    assert [record.sequence_number for record in recovery.records] == [0, 1]

    truncated = recover_segment(
        path,
        disposition=WALCorruptionDisposition.TRUNCATE_TO_VALID_PREFIX,
        durability=durability,
    )
    assert truncated.tail_corrupt
    assert path.stat().st_size == valid_size
    assert durability.events[-3:] == ["flush", "file", "parent"]


def test_queue_is_bounded_and_cancellation_is_typed_without_poisoning_order(
    tmp_path: Path,
) -> None:
    durability = BlockingDurability()
    writer = WALWriter(
        tmp_path,
        durability=durability,
        policy=GroupCommitPolicy(max_queue_items=1, max_delay_seconds=0),
    )
    try:
        first = writer.submit(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
        assert durability.write_started.wait(2)
        cancelled = writer.submit(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
        with pytest.raises(WALQueueFullError):
            writer.submit(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
        assert cancelled.cancel()
        with pytest.raises(WALAppendCancelled):
            cancelled.future.result(timeout=1)

        durability.release_write.set()
        assert first.future.result(timeout=2).record.sequence_number == 0
        final = writer.append(acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC)
        assert final.record.sequence_number == 2
        assert [segment.first_sequence for segment in writer.sealed_segments] == [0]
    finally:
        durability.release_write.set()
        writer.close()

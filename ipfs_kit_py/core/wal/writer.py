"""Bounded group-commit WAL writer.

The writer deliberately separates admission from durability.  A caller gets a
``QUEUED`` acknowledgement immediately only when it asked for one; every mode
which claims file or parent-directory durability waits for the corresponding
injected operation to succeed.
"""

from __future__ import annotations

from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field, replace
from pathlib import Path
import queue
import threading
import time
from typing import Callable
from uuid import uuid4

from .contracts import (
    WALAcknowledgementError,
    WALAcknowledgementMode,
    WALContractError,
    WALFsyncReceipt,
    WALRecord,
    WALRecordKind,
    WALRecordState,
    WALSegment as WALSegmentDescriptor,
    assert_ack_allows_state,
    ack_requirements_for,
)
from .segments import (
    DurabilityOperations,
    WALDurabilityError,
    WALSegmentFile,
)


__all__ = [
    "GroupCommitPolicy",
    "WALAppendCancelled",
    "WALAppendResult",
    "WALAppendTicket",
    "WALQueueFullError",
    "WALShutdownIncompleteError",
    "WALWriter",
    "WALWriterError",
]


class WALWriterError(WALContractError):
    """Base error raised by the runtime WAL writer."""


class WALQueueFullError(WALWriterError):
    """Admission failed because the bounded writer queue is full."""


class WALAppendCancelled(WALWriterError):
    """A queued append was cancelled before it reached durable storage."""


class WALShutdownIncompleteError(WALWriterError):
    """The worker did not finish and durably flush during shutdown."""


@dataclass(frozen=True, slots=True)
class GroupCommitPolicy:
    """Hard resource and latency bounds for the single WAL worker."""

    max_queue_items: int = 1024
    max_batch_size: int = 64
    max_delay_seconds: float = 0.010
    max_segment_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.max_queue_items <= 0:
            raise ValueError("max_queue_items must be positive")
        if self.max_batch_size <= 0:
            raise ValueError("max_batch_size must be positive")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds cannot be negative")
        if self.max_segment_bytes <= 0:
            raise ValueError("max_segment_bytes must be positive")


@dataclass(frozen=True, slots=True)
class WALAppendResult:
    """Result returned after the selected acknowledgement boundary."""

    record: WALRecord
    acknowledgement_mode: WALAcknowledgementMode
    fsync_receipt: WALFsyncReceipt | None = None
    append_observed: bool = False

    @property
    def durable(self) -> bool:
        return bool(
            self.fsync_receipt
            and self.fsync_receipt.satisfies(
                ack_requirements_for(self.acknowledgement_mode)
            )
        )


@dataclass(slots=True)
class WALAppendTicket:
    """A cancellable admission handle for a WAL append."""

    queued_record: WALRecord
    acknowledgement_mode: WALAcknowledgementMode
    _future: Future[WALAppendResult] = field(default_factory=Future, repr=False)
    _cancelled: bool = field(default=False, init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def future(self) -> Future[WALAppendResult]:
        return self._future

    def cancel(self) -> bool:
        """Cancel only before the worker has begun the physical append."""
        with self._lock:
            if self._started or self._future.done():
                return False
            self._cancelled = True
            self._future.set_exception(WALAppendCancelled("WAL append cancelled before write"))
            return True

    def _claim(self) -> bool:
        with self._lock:
            if self._cancelled:
                return False
            self._started = True
            return True

    @property
    def queued_result(self) -> WALAppendResult:
        state = (
            WALRecordState.BUFFERED
            if self.acknowledgement_mode is WALAcknowledgementMode.BUFFERED
            else WALRecordState.QUEUED
        )
        return WALAppendResult(
            record=replace(self.queued_record, state=state),
            acknowledgement_mode=self.acknowledgement_mode,
            append_observed=False,
        )


_STOP = object()


class WALWriter:
    """One generation's ordered, bounded, stoppable WAL append stream."""

    def __init__(
        self,
        directory: str | Path,
        *,
        generation_id: str | None = None,
        policy: GroupCommitPolicy | None = None,
        durability: DurabilityOperations | None = None,
        backend_effect: Callable[[WALRecord], str | None] | None = None,
        start_sequence: int = 0,
    ) -> None:
        if start_sequence < 0:
            raise ValueError("start_sequence cannot be negative")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.generation_id = generation_id or f"wal-generation-{uuid4().hex}"
        self.policy = policy or GroupCommitPolicy()
        self._durability = durability
        self._backend_effect = backend_effect
        self._next_sequence = start_sequence
        self._admission_lock = threading.RLock()
        self._io_lock = threading.RLock()
        self._queue: queue.Queue[WALAppendTicket | object] = queue.Queue(
            maxsize=self.policy.max_queue_items
        )
        self._closing = False
        self._closed = False
        self._segment: WALSegmentFile | None = None
        self._sealed_segments: list[WALSegmentDescriptor] = []
        self._worker = threading.Thread(
            target=self._run,
            name=f"wal-group-commit-{self.generation_id[-12:]}",
            daemon=False,
        )
        self._worker.start()

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def sealed_segments(self) -> tuple[WALSegmentDescriptor, ...]:
        with self._io_lock:
            return tuple(self._sealed_segments)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def submit(
        self,
        kind: WALRecordKind | WALRecord | str = WALRecordKind.MUTATE,
        *,
        acknowledgement_mode: WALAcknowledgementMode | str | None = None,
        transaction_id: str = "",
        record_key: str = "",
        payload: object | None = None,
        payload_cid: str = "",
        checksum: str = "",
        encoding: str = "",
        operation_id: str = "",
        principal_id: str = "",
        created_at_unix_ms: int = 0,
        notes: str = "",
    ) -> WALAppendTicket:
        """Admit an append without waiting for the requested ack boundary."""
        with self._admission_lock:
            if self._closing or self._closed:
                raise WALWriterError("WAL writer is closing or closed")
            template = kind if isinstance(kind, WALRecord) else None
            chosen_mode = acknowledgement_mode
            if chosen_mode is None:
                chosen_mode = template.acknowledgement_mode if template else WALAcknowledgementMode.WAL_FSYNC_PARENT
            if not isinstance(chosen_mode, WALAcknowledgementMode):
                chosen_mode = WALAcknowledgementMode(chosen_mode)
            chosen_kind = template.kind if template else (
                kind if isinstance(kind, WALRecordKind) else WALRecordKind(kind)
            )
            sequence = self._next_sequence
            record = WALRecord(
                generation_id=self.generation_id,
                sequence_number=sequence,
                kind=chosen_kind,
                state=WALRecordState.QUEUED,
                acknowledgement_mode=chosen_mode,
                transaction_id=template.transaction_id if template else transaction_id,
                record_key=template.record_key if template else record_key,
                payload=template.payload if template else payload,
                payload_cid=template.payload_cid if template else payload_cid,
                checksum=template.checksum if template else checksum,
                previous_sequence=sequence - 1 if sequence else -1,
                encoding=template.encoding if template else encoding,
                operation_id=template.operation_id if template else operation_id,
                principal_id=template.principal_id if template else principal_id,
                created_at_unix_ms=(template.created_at_unix_ms if template else created_at_unix_ms),
                notes=template.notes if template else notes,
            )
            ticket = WALAppendTicket(record, chosen_mode)
            try:
                self._queue.put_nowait(ticket)
            except queue.Full as exc:
                raise WALQueueFullError(
                    f"WAL queue is bounded at {self.policy.max_queue_items} items"
                ) from exc
            # Sequence ownership changes only after successful admission, so a
            # full queue cannot create gaps in durable record identities.
            self._next_sequence += 1
            return ticket

    def append(
        self,
        kind: WALRecordKind | WALRecord | str = WALRecordKind.MUTATE,
        *,
        acknowledgement_mode: WALAcknowledgementMode | str | None = None,
        timeout: float | None = None,
        cancel_event: threading.Event | None = None,
        **record_fields: object,
    ) -> WALAppendResult:
        """Append and wait exactly as far as ``acknowledgement_mode`` permits."""
        ticket = self.submit(
            kind,
            acknowledgement_mode=acknowledgement_mode,
            **record_fields,
        )
        if ticket.acknowledgement_mode in (
            WALAcknowledgementMode.BUFFERED,
            WALAcknowledgementMode.QUEUED,
        ):
            return ticket.queued_result

        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if cancel_event is not None and cancel_event.is_set() and ticket.cancel():
                raise WALAppendCancelled("WAL append cancelled before write")
            wait_for = 0.025
            if deadline is not None:
                wait_for = max(0.0, min(wait_for, deadline - time.monotonic()))
                if wait_for == 0.0:
                    if ticket.cancel():
                        raise WALAppendCancelled("WAL append timed out before write")
                    raise TimeoutError("WAL append did not reach its acknowledgement boundary")
            try:
                return ticket.future.result(timeout=wait_for)
            except FutureTimeoutError:
                continue

    def rotate(self, *, checkpoint_id: str = "") -> WALSegmentDescriptor | None:
        """Seal the current segment; queued later records use a new one."""
        # Admission is held while the I/O lock is acquired.  A record admitted
        # before this point either finishes in the old segment or observes the
        # new ``None`` target; neither can append after it has been sealed.
        with self._admission_lock, self._io_lock:
            if self._segment is None:
                return None
            descriptor = (
                self._segment.checkpoint(checkpoint_id)
                if checkpoint_id
                else self._segment.seal()
            )
            self._sealed_segments.append(descriptor)
            self._segment = None
            return descriptor

    def flush(self) -> None:
        """Flush/sync the current segment under the writer's I/O lock."""
        with self._io_lock:
            if self._segment is not None:
                self._segment.flush()
                self._segment.sync_file()
                self._segment.sync_parent()

    def _new_segment(self, first_sequence: int) -> WALSegmentFile:
        segment_id = f"wal-segment-{uuid4().hex}"
        return WALSegmentFile(
            self.directory / f"{segment_id}.wal",
            generation_id=self.generation_id,
            segment_id=segment_id,
            first_sequence=first_sequence,
            durability=self._durability,
        )

    def _append_one(self, ticket: WALAppendTicket) -> tuple[WALAppendTicket, WALRecord, WALSegmentFile]:
        if self._segment is None:
            self._segment = self._new_segment(ticket.queued_record.sequence_number)
        elif (
            self._segment.record_count
            and ticket.queued_record.sequence_number
            != self._segment.descriptor.last_sequence + 1
        ):
            # A ticket may be cancelled while still queued.  Its sequence ID
            # remains owned (and therefore is never reused), but there must
            # not be an unexplained hole inside a physical segment: recovery
            # validates each segment's contiguous prefix.  Seal the old
            # prefix and make the next persisted sequence the first record of
            # a fresh segment.
            self._sealed_segments.append(self._segment.seal())
            self._segment = self._new_segment(ticket.queued_record.sequence_number)
        provisional = replace(ticket.queued_record, segment_id=self._segment.segment_id)
        frame_size = len(WALSegmentFile.frame_bytes(provisional))
        if self._segment.record_count and self._segment.size_bytes + frame_size > self.policy.max_segment_bytes:
            self._sealed_segments.append(self._segment.seal())
            self._segment = self._new_segment(ticket.queued_record.sequence_number)
            provisional = replace(provisional, segment_id=self._segment.segment_id)
        receipt_id = f"wal-fsync-{uuid4().hex}"
        persisted = replace(
            provisional,
            state=WALRecordState.APPENDING,
            fsync_receipt_id=receipt_id,
        )
        # APPENDING is intentionally serialized in the actual record only for
        # construction validation; the immutable bytes use APPENDED, which is
        # the truthful post-write state visible to recovery.
        persisted = replace(persisted, state=WALRecordState.APPENDED)
        self._segment.append(persisted)
        return ticket, persisted, self._segment

    def _complete_batch(self, batch: list[WALAppendTicket]) -> None:
        active: list[tuple[WALAppendTicket, WALRecord, WALSegmentFile]] = []
        for ticket in batch:
            if not ticket._claim():
                continue
            active.append(self._append_one(ticket))
        if not active:
            return

        requirements = [ack_requirements_for(ticket.acknowledgement_mode) for ticket, _, _ in active]
        need_file = any(item.requires_file_fsync for item in requirements)
        need_parent = any(item.requires_parent_directory_fsync for item in requirements)
        touched: dict[str, WALSegmentFile] = {segment.segment_id: segment for _, _, segment in active}
        if need_file:
            for segment in touched.values():
                segment.flush()
                segment.sync_file()
        if need_parent:
            for segment in touched.values():
                segment.sync_parent()

        for (ticket, record, segment), requirement in zip(active, requirements):
            backend_effect_id = ""
            if requirement.requires_backend_effect:
                if self._backend_effect is None:
                    raise WALAcknowledgementError(
                        "selected acknowledgement mode requires a backend effect callback"
                    )
                backend_effect_id = self._backend_effect(record) or ""
                if not backend_effect_id:
                    raise WALAcknowledgementError(
                        "backend effect callback did not return an effect identifier"
                    )
            receipt = WALFsyncReceipt(
                receipt_id=record.fsync_receipt_id,
                generation_id=record.generation_id,
                sequence_number=record.sequence_number,
                file_fsync_observed=need_file,
                parent_directory_fsync_observed=need_parent,
                segment_id=segment.segment_id,
                path_ref=segment.descriptor.path_ref,
                backend_effect_id=backend_effect_id,
            )
            if not receipt.satisfies(requirement):
                raise WALAcknowledgementError(
                    "WAL writer cannot acknowledge before selected durability policy"
                )
            if requirement.requires_parent_directory_fsync:
                state = WALRecordState.PARENT_SYNCED
            elif requirement.requires_file_fsync:
                state = WALRecordState.FILE_SYNCED
            else:
                state = WALRecordState.APPENDED
            result_record = replace(record, state=state, backend_effect_id=backend_effect_id)
            assert_ack_allows_state(
                ticket.acknowledgement_mode,
                result_record.state,
                fsync_receipt=receipt,
                append_observed=True,
            )
            if not ticket.future.done():
                ticket.future.set_result(
                    WALAppendResult(
                        record=result_record,
                        acknowledgement_mode=ticket.acknowledgement_mode,
                        fsync_receipt=receipt,
                        append_observed=True,
                    )
                )

    def _run(self) -> None:
        stopping = False
        while not stopping:
            item = self._queue.get()
            batch: list[WALAppendTicket] = []
            try:
                if item is _STOP:
                    stopping = True
                    continue
                assert isinstance(item, WALAppendTicket)
                batch.append(item)
                deadline = time.monotonic() + self.policy.max_delay_seconds
                while len(batch) < self.policy.max_batch_size:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        next_item = self._queue.get(timeout=remaining)
                    except queue.Empty:
                        break
                    if next_item is _STOP:
                        stopping = True
                        self._queue.task_done()
                        break
                    assert isinstance(next_item, WALAppendTicket)
                    batch.append(next_item)
                try:
                    with self._io_lock:
                        self._complete_batch(batch)
                except BaseException as exc:
                    error = exc if isinstance(exc, WALWriterError) else WALWriterError(str(exc))
                    for ticket in batch:
                        if not ticket.future.done():
                            ticket.future.set_exception(error)
            finally:
                self._queue.task_done()
                # Entries taken while forming a batch have one additional
                # task_done call here; the first item is the outer task.
                for _ in batch[1:]:
                    self._queue.task_done()

    def close(self, *, timeout: float | None = 5.0) -> None:
        """Stop admission, drain the worker, then durably flush or report failure."""
        with self._admission_lock:
            if self._closed:
                return
            self._closing = True
            try:
                self._queue.put(_STOP, timeout=timeout)
            except queue.Full as exc:
                raise WALShutdownIncompleteError("unable to enqueue WAL worker stop marker") from exc
        self._worker.join(timeout=timeout)
        if self._worker.is_alive():
            raise WALShutdownIncompleteError("WAL group-commit worker did not stop")
        try:
            with self._io_lock:
                if self._segment is not None:
                    self._segment.flush()
                    self._segment.sync_file()
                    self._segment.sync_parent()
                    self._segment.close()
        except (WALDurabilityError, OSError) as exc:
            raise WALShutdownIncompleteError("WAL worker stopped without durable shutdown") from exc
        self._closed = True

    shutdown = close

    def __enter__(self) -> "WALWriter":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

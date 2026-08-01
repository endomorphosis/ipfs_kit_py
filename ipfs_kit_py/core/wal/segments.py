"""Durable, append-only WAL segment files.

The wire format deliberately has a small independently verifiable frame around
each canonical :class:`WALRecord`.  It lets recovery retain a valid prefix when
a process is interrupted halfway through a write, without treating a corrupt
tail as a valid record.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import threading
from typing import BinaryIO, Protocol
from uuid import uuid4

from .contracts import (
    WALContractError,
    WALCorruptionDisposition,
    WALRecord,
    WALSegment as WALSegmentDescriptor,
    WALSegmentState,
)


__all__ = [
    "DurabilityOperations",
    "SegmentRecovery",
    "WALDurabilityError",
    "WALSegment",
    "WALSegmentError",
    "WALSegmentCorruptionError",
    "WALSegmentFile",
    "WALSegmentSealedError",
    "WALShortWriteError",
    "recover_segment",
]


_MAGIC = b"IWAL1"
_LENGTH = struct.Struct(">I")
_DIGEST_BYTES = 32
_MAX_FRAME_PAYLOAD = 64 * 1024 * 1024


class WALSegmentError(WALContractError):
    """Base exception raised by the segment storage implementation."""


class WALSegmentSealedError(WALSegmentError):
    """Raised when an append is attempted after a segment is sealed."""


class WALShortWriteError(WALSegmentError):
    """Raised when the underlying writer cannot write a complete frame."""


class WALDurabilityError(WALSegmentError):
    """Raised when flush, file fsync, or parent-directory fsync fails."""


class WALSegmentCorruptionError(WALSegmentError):
    """Raised for a malformed or checksum-invalid segment frame."""


class DurabilityOperations(Protocol):
    """Injectable OS operations used by segments.

    Tests and embedders can provide an object implementing these four methods
    to observe or fault-inject every durability boundary.  ``write`` may make
    a short write; the segment retries until the entire frame is written.
    """

    def write(self, handle: BinaryIO, data: bytes) -> int: ...

    def flush(self, handle: BinaryIO) -> None: ...

    def fsync_file(self, handle: BinaryIO) -> None: ...

    def fsync_directory(self, directory: Path) -> None: ...


class _SystemDurabilityOperations:
    def write(self, handle: BinaryIO, data: bytes) -> int:
        return handle.write(data)

    def flush(self, handle: BinaryIO) -> None:
        handle.flush()

    def fsync_file(self, handle: BinaryIO) -> None:
        os.fsync(handle.fileno())

    def fsync_directory(self, directory: Path) -> None:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        try:
            descriptor = os.open(str(directory), flags)
        except OSError as exc:
            raise WALDurabilityError(
                "unable to open WAL parent directory for fsync: "
                f"{directory}"
            ) from exc
        try:
            os.fsync(descriptor)
        except OSError as exc:
            raise WALDurabilityError(
                f"unable to fsync WAL parent directory: {directory}"
            ) from exc
        finally:
            os.close(descriptor)


DEFAULT_DURABILITY_OPERATIONS: DurabilityOperations = _SystemDurabilityOperations()


@dataclass(frozen=True, slots=True)
class SegmentRecovery:
    """The verified prefix recovered from a segment file."""

    records: tuple[WALRecord, ...]
    valid_bytes: int
    tail_corrupt: bool = False
    error: str = ""


def _path_ref(path: Path) -> str:
    return "wal-path:" + sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def _segment_checksum(digest: "sha256") -> str:
    return "sha256:" + digest.hexdigest()


class WALSegmentFile:
    """One open append-only WAL segment.

    A segment owns one file handle and is intentionally not reopened for
    writing after ``seal``.  This is stronger than trusting a file name or a
    caller convention and prevents a checkpointed segment from being appended
    to by a later writer operation.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        generation_id: str,
        segment_id: str | None = None,
        first_sequence: int = 0,
        durability: DurabilityOperations | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.generation_id = generation_id
        self.segment_id = segment_id or f"wal-segment-{uuid4().hex}"
        self._first_sequence = first_sequence
        self._last_sequence = first_sequence - 1
        self._record_count = 0
        self._digest = sha256()
        self._durability = durability or DEFAULT_DURABILITY_OPERATIONS
        self._state = WALSegmentState.OPEN
        self._sealed = False
        self._checkpoint_id = ""
        self._lock = threading.RLock()
        self._handle: BinaryIO | None = open(self.path, "a+b", buffering=0)

        # A newly constructed writer normally starts with an empty file.  The
        # recovery path is explicit so callers never accidentally append after
        # an unexamined torn tail.
        if self._handle.tell() != 0:
            self._handle.close()
            self._handle = None
            raise WALSegmentError(
                "refusing to append through a fresh segment object to a "
                f"non-empty file: {self.path}"
            )

    @property
    def state(self) -> WALSegmentState:
        return self._state

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def size_bytes(self) -> int:
        with self._lock:
            return self._handle.tell() if self._handle is not None else self.path.stat().st_size

    @property
    def record_count(self) -> int:
        return self._record_count

    @property
    def descriptor(self) -> WALSegmentDescriptor:
        last = self._last_sequence if self._record_count else self._first_sequence
        return WALSegmentDescriptor(
            segment_id=self.segment_id,
            generation_id=self.generation_id,
            state=self._state,
            first_sequence=self._first_sequence,
            last_sequence=last,
            checksum=_segment_checksum(self._digest) if self._record_count else "",
            path_ref=_path_ref(self.path),
            sealed=self._sealed,
            checkpoint_id=self._checkpoint_id,
            record_count=self._record_count,
        )

    @staticmethod
    def frame_bytes(record: WALRecord) -> bytes:
        payload = record.canonical_bytes()
        if len(payload) > _MAX_FRAME_PAYLOAD:
            raise WALSegmentError(
                f"WAL record frame exceeds {_MAX_FRAME_PAYLOAD} bytes"
            )
        return _MAGIC + _LENGTH.pack(len(payload)) + payload + sha256(payload).digest()

    def append(self, record: WALRecord) -> int:
        """Append a complete verified frame and return its byte length."""
        with self._lock:
            if self._sealed or self._state is not WALSegmentState.OPEN:
                raise WALSegmentSealedError(
                    f"segment {self.segment_id} is {self._state.value} and cannot accept appends"
                )
            if self._handle is None:
                raise WALSegmentSealedError(f"segment {self.segment_id} is closed")
            if record.generation_id != self.generation_id:
                raise WALSegmentError("record generation does not match segment generation")
            if record.segment_id != self.segment_id:
                raise WALSegmentError("record segment_id does not match append target")
            expected = self._first_sequence if not self._record_count else self._last_sequence + 1
            if record.sequence_number != expected:
                raise WALSegmentError(
                    f"non-contiguous WAL sequence: expected {expected}, got {record.sequence_number}"
                )

            frame = self.frame_bytes(record)
            offset = 0
            try:
                while offset < len(frame):
                    written = self._durability.write(self._handle, frame[offset:])
                    if written is None or written <= 0:
                        raise WALShortWriteError(
                            f"short WAL write at {offset} of {len(frame)} bytes"
                        )
                    if written > len(frame) - offset:
                        raise WALShortWriteError(
                            f"writer reported {written} bytes for only "
                            f"{len(frame) - offset} available bytes"
                        )
                    offset += written
            except WALSegmentError:
                raise
            except Exception as exc:
                raise WALShortWriteError("unable to write WAL frame") from exc

            self._digest.update(frame)
            self._last_sequence = record.sequence_number
            self._record_count += 1
            return len(frame)

    def flush(self) -> None:
        with self._lock:
            if self._handle is None:
                return
            try:
                self._durability.flush(self._handle)
            except WALDurabilityError:
                raise
            except Exception as exc:
                raise WALDurabilityError(f"unable to flush WAL segment {self.path}") from exc

    def sync_file(self) -> None:
        with self._lock:
            if self._handle is None:
                return
            try:
                self._durability.fsync_file(self._handle)
            except WALDurabilityError:
                raise
            except Exception as exc:
                raise WALDurabilityError(f"unable to fsync WAL segment {self.path}") from exc

    def sync_parent(self) -> None:
        try:
            self._durability.fsync_directory(self.path.parent)
        except WALDurabilityError:
            raise
        except Exception as exc:
            raise WALDurabilityError(
                f"unable to fsync WAL parent directory {self.path.parent}"
            ) from exc

    def seal(self) -> WALSegmentDescriptor:
        """Flush and durably seal this segment exactly once."""
        with self._lock:
            if self._sealed:
                return self.descriptor
            if self._handle is None:
                raise WALSegmentSealedError(f"segment {self.segment_id} is closed")
            self._state = WALSegmentState.SEALING
            self.flush()
            self.sync_file()
            self._sealed = True
            self._state = WALSegmentState.SEALED
            self._handle.close()
            self._handle = None
            self.sync_parent()
            return self.descriptor

    def checkpoint(self, checkpoint_id: str) -> WALSegmentDescriptor:
        if not checkpoint_id:
            raise WALSegmentError("checkpoint_id is required")
        with self._lock:
            self.seal()
            self._checkpoint_id = checkpoint_id
            self._state = WALSegmentState.CHECKPOINTED
            return self.descriptor

    def close(self) -> None:
        with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None


# A short public spelling is useful to callers already using the contract
# descriptor under a different name.
WALSegment = WALSegmentFile


def _corruption(
    path: Path,
    records: list[WALRecord],
    valid_bytes: int,
    message: str,
    disposition: WALCorruptionDisposition,
    durability: DurabilityOperations,
) -> SegmentRecovery:
    recovery = SegmentRecovery(tuple(records), valid_bytes, True, message)
    if disposition is WALCorruptionDisposition.FAIL_CLOSED:
        raise WALSegmentCorruptionError(f"{path}: {message}")
    if disposition is WALCorruptionDisposition.TRUNCATE_TO_VALID_PREFIX:
        try:
            with open(path, "r+b", buffering=0) as handle:
                handle.truncate(valid_bytes)
                durability.flush(handle)
                durability.fsync_file(handle)
            durability.fsync_directory(path.parent)
        except Exception as exc:
            raise WALDurabilityError(
                f"unable to truncate corrupt WAL tail in {path}"
            ) from exc
    elif disposition is WALCorruptionDisposition.QUARANTINE_SEGMENT:
        target = path.with_name(path.name + ".corrupt")
        try:
            os.replace(path, target)
            durability.fsync_directory(path.parent)
        except Exception as exc:
            raise WALDurabilityError(f"unable to quarantine corrupt WAL {path}") from exc
    return recovery


def recover_segment(
    path: str | Path,
    *,
    disposition: WALCorruptionDisposition = WALCorruptionDisposition.BOUND_AND_REPORT,
    durability: DurabilityOperations | None = None,
) -> SegmentRecovery:
    """Read the verified prefix of *path*.

    A short frame, invalid JSON/record, checksum mismatch, or non-contiguous
    sequence is a corrupt tail.  The valid prefix is always returned (or,
    under ``FAIL_CLOSED``, attached to the raised error's context) and may be
    explicitly truncated or quarantined through ``disposition``.
    """
    segment_path = Path(path)
    ops = durability or DEFAULT_DURABILITY_OPERATIONS
    records: list[WALRecord] = []
    valid_bytes = 0
    expected_sequence: int | None = None
    generation_id: str | None = None

    try:
        handle = open(segment_path, "rb", buffering=0)
    except OSError as exc:
        raise WALSegmentError(f"unable to read WAL segment {segment_path}") from exc

    with handle:
        while True:
            header = handle.read(len(_MAGIC))
            if not header:
                return SegmentRecovery(tuple(records), valid_bytes)
            if header != _MAGIC:
                return _corruption(segment_path, records, valid_bytes, "invalid frame magic", disposition, ops)
            length_bytes = handle.read(_LENGTH.size)
            if len(length_bytes) != _LENGTH.size:
                return _corruption(segment_path, records, valid_bytes, "short frame length", disposition, ops)
            length = _LENGTH.unpack(length_bytes)[0]
            if length > _MAX_FRAME_PAYLOAD:
                return _corruption(segment_path, records, valid_bytes, "frame length exceeds limit", disposition, ops)
            payload = handle.read(length)
            digest = handle.read(_DIGEST_BYTES)
            if len(payload) != length or len(digest) != _DIGEST_BYTES:
                return _corruption(segment_path, records, valid_bytes, "short frame payload", disposition, ops)
            if sha256(payload).digest() != digest:
                return _corruption(segment_path, records, valid_bytes, "frame checksum mismatch", disposition, ops)
            try:
                parsed = json.loads(payload.decode("utf-8"))
                record = WALRecord.from_dict(parsed)
            except (UnicodeDecodeError, json.JSONDecodeError, WALContractError, TypeError, ValueError) as exc:
                return _corruption(segment_path, records, valid_bytes, f"invalid WAL record: {exc}", disposition, ops)
            if generation_id is None:
                generation_id = record.generation_id
                expected_sequence = record.sequence_number
            if record.generation_id != generation_id or record.sequence_number != expected_sequence:
                return _corruption(segment_path, records, valid_bytes, "non-contiguous record sequence", disposition, ops)
            expected_sequence += 1
            records.append(record)
            valid_bytes += len(_MAGIC) + _LENGTH.size + length + _DIGEST_BYTES

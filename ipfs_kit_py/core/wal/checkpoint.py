"""Durable checkpoint, compaction, and archive support for the WAL.

Checkpoints deliberately name the *exact* sealed segment contents they cover.
That makes a checkpoint a safe optimisation rather than an instruction to skip
everything with an older sequence number: a segment that was replaced, or that
received additional bytes, no longer matches the checkpoint identity.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Iterable, Mapping, Sequence

from .contracts import (
    WALCheckpoint,
    WALCheckpointState,
    WALSegment,
    WALSegmentState,
)


class WALCheckpointError(RuntimeError):
    """A checkpoint, compaction, or archive invariant was not satisfied."""


class WALCheckpointIdentityError(WALCheckpointError):
    """A checkpoint did not identify exactly the sealed bytes it claims."""


class WALArchiveError(WALCheckpointError):
    """Archiving failed before the archive became durable."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _fsync_directory(directory: Path) -> None:
    """Persist directory-entry changes on platforms that support directory fsync."""

    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` atomically and durably enough for crash recovery.

    The final rename is intentionally the last visible operation.  Readers of a
    current-checkpoint pointer therefore see either the previous complete state
    or the newly complete state, never an intermediate compacted snapshot.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


@dataclass(frozen=True)
class SealedSegmentIdentity:
    """The immutable identity of one checkpointed WAL segment."""

    segment_id: str
    generation_id: str
    first_sequence: int
    last_sequence: int
    record_count: int
    checksum: str

    def __post_init__(self) -> None:
        if not self.segment_id or not self.generation_id:
            raise WALCheckpointIdentityError("sealed segment identity is incomplete")
        if self.first_sequence < 0 or self.last_sequence < self.first_sequence:
            raise WALCheckpointIdentityError("sealed segment sequence range is invalid")
        if self.record_count <= 0:
            raise WALCheckpointIdentityError("sealed segment has no records")
        if not self.checksum.startswith("sha256:"):
            raise WALCheckpointIdentityError("sealed segment checksum must be sha256")

    @classmethod
    def from_segment(cls, segment: WALSegment) -> "SealedSegmentIdentity":
        if not segment.sealed or segment.state not in {
            WALSegmentState.SEALED,
            WALSegmentState.CHECKPOINTED,
            WALSegmentState.ARCHIVED,
        }:
            raise WALCheckpointIdentityError(
                "only sealed segments can be included in a checkpoint"
            )
        return cls(
            segment_id=segment.segment_id,
            generation_id=segment.generation_id,
            first_sequence=segment.first_sequence,
            last_sequence=segment.last_sequence,
            record_count=segment.record_count,
            checksum=segment.checksum,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "generation_id": self.generation_id,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "record_count": self.record_count,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "SealedSegmentIdentity":
        return cls(
            segment_id=str(value["segment_id"]),
            generation_id=str(value["generation_id"]),
            first_sequence=int(value["first_sequence"]),
            last_sequence=int(value["last_sequence"]),
            record_count=int(value["record_count"]),
            checksum=str(value["checksum"]),
        )


@dataclass(frozen=True)
class CheckpointBundle:
    """A published checkpoint and the immutable segments it covers."""

    checkpoint: WALCheckpoint
    sealed_segments: tuple[SealedSegmentIdentity, ...]
    state_digest: str
    snapshot_ref: str = ""

    def __post_init__(self) -> None:
        if self.checkpoint.state not in {
            WALCheckpointState.PUBLISHED,
            WALCheckpointState.ARCHIVED,
            WALCheckpointState.SUPERSEDED,
        }:
            raise WALCheckpointIdentityError("checkpoint is not published")
        if not self.state_digest.startswith("sha256:"):
            raise WALCheckpointIdentityError("checkpoint state digest must be sha256")
        segment_ids = tuple(segment.segment_id for segment in self.sealed_segments)
        if len(segment_ids) != len(set(segment_ids)):
            raise WALCheckpointIdentityError("checkpoint repeats a sealed segment")
        if tuple(self.checkpoint.sealed_segment_ids) != segment_ids:
            raise WALCheckpointIdentityError(
                "checkpoint segment ids do not exactly match its identities"
            )
        if any(
            segment.generation_id != self.checkpoint.generation_id
            for segment in self.sealed_segments
        ):
            raise WALCheckpointIdentityError("checkpoint spans different generations")
        if self.sealed_segments and self.checkpoint.through_sequence != max(
            segment.last_sequence for segment in self.sealed_segments
        ):
            raise WALCheckpointIdentityError(
                "checkpoint through-sequence must end at its final sealed segment"
            )
        if self.checkpoint.checksum != self.identity_checksum(
            self.checkpoint.checkpoint_id,
            self.checkpoint.generation_id,
            self.checkpoint.through_sequence,
            self.state_digest,
            self.sealed_segments,
            self.checkpoint.previous_checkpoint_id,
        ):
            raise WALCheckpointIdentityError("checkpoint checksum does not bind segment identities")

    @staticmethod
    def identity_checksum(
        checkpoint_id: str,
        generation_id: str,
        through_sequence: int,
        state_digest: str,
        segments: Sequence[SealedSegmentIdentity],
        previous_checkpoint_id: str = "",
    ) -> str:
        return _sha256(
            _canonical_bytes(
                {
                    "checkpoint_id": checkpoint_id,
                    "generation_id": generation_id,
                    "through_sequence": through_sequence,
                    "state_digest": state_digest,
                    "previous_checkpoint_id": previous_checkpoint_id,
                    "sealed_segments": [segment.to_dict() for segment in segments],
                }
            )
        )

    def matches(self, identity: SealedSegmentIdentity) -> bool:
        return identity in self.sealed_segments

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint": self.checkpoint.to_dict(),
            "sealed_segments": [segment.to_dict() for segment in self.sealed_segments],
            "state_digest": self.state_digest,
            "snapshot_ref": self.snapshot_ref,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "CheckpointBundle":
        checkpoint_value = value["checkpoint"]
        if not isinstance(checkpoint_value, Mapping):
            raise WALCheckpointIdentityError("checkpoint manifest has no checkpoint")
        segment_values = value["sealed_segments"]
        if not isinstance(segment_values, list):
            raise WALCheckpointIdentityError("checkpoint manifest segments are invalid")
        if not all(isinstance(item, Mapping) for item in segment_values):
            raise WALCheckpointIdentityError(
                "checkpoint manifest contains an invalid sealed segment identity"
            )
        return cls(
            checkpoint=WALCheckpoint.from_dict(dict(checkpoint_value)),
            sealed_segments=tuple(
                SealedSegmentIdentity.from_dict(item)
                for item in segment_values
            ),
            state_digest=str(value["state_digest"]),
            snapshot_ref=str(value.get("snapshot_ref", "")),
        )


def create_checkpoint(
    checkpoint_id: str,
    generation_id: str,
    sealed_segments: Iterable[WALSegment | SealedSegmentIdentity],
    *,
    state: bytes | str | Mapping[str, object] = b"",
    previous_checkpoint_id: str = "",
    created_at_unix_ms: int | None = None,
) -> CheckpointBundle:
    """Create a published checkpoint whose checksum binds every sealed segment."""

    identities = tuple(
        item if isinstance(item, SealedSegmentIdentity) else SealedSegmentIdentity.from_segment(item)
        for item in sealed_segments
    )
    if not identities:
        raise WALCheckpointIdentityError("a checkpoint requires at least one sealed segment")
    if any(identity.generation_id != generation_id for identity in identities):
        raise WALCheckpointIdentityError("checkpoint segments must have one generation")
    if len({identity.segment_id for identity in identities}) != len(identities):
        raise WALCheckpointIdentityError("checkpoint contains duplicate segment ids")
    if isinstance(state, bytes):
        state_bytes = state
    elif isinstance(state, str):
        state_bytes = state.encode("utf-8")
    else:
        state_bytes = _canonical_bytes(state)
    state_digest = _sha256(state_bytes)
    through_sequence = max(identity.last_sequence for identity in identities)
    checksum = CheckpointBundle.identity_checksum(
        checkpoint_id,
        generation_id,
        through_sequence,
        state_digest,
        identities,
        previous_checkpoint_id,
    )
    checkpoint = WALCheckpoint(
        checkpoint_id=checkpoint_id,
        generation_id=generation_id,
        through_sequence=through_sequence,
        state=WALCheckpointState.PUBLISHED,
        sealed_segment_ids=tuple(identity.segment_id for identity in identities),
        checksum=checksum,
        previous_checkpoint_id=previous_checkpoint_id,
        created_at_unix_ms=created_at_unix_ms or int(time.time() * 1000),
    )
    return CheckpointBundle(checkpoint, identities, state_digest)


@dataclass(frozen=True)
class ArchiveReceipt:
    archive_receipt_id: str
    archived_paths: tuple[str, ...]


class CheckpointStore:
    """Filesystem store that publishes snapshots and checkpoint pointers atomically."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.checkpoint_directory = self.root / "checkpoints"
        self.snapshot_directory = self.root / "snapshots"
        self.current_path = self.root / "current.json"

    def publish(self, bundle: CheckpointBundle, state: bytes | str | Mapping[str, object]) -> CheckpointBundle:
        if isinstance(state, bytes):
            state_bytes = state
        elif isinstance(state, str):
            state_bytes = state.encode("utf-8")
        else:
            state_bytes = _canonical_bytes(state)
        if _sha256(state_bytes) != bundle.state_digest:
            raise WALCheckpointIdentityError("compacted state does not match checkpoint digest")
        snapshot_ref = hashlib.sha256(bundle.checkpoint.checksum.encode("ascii")).hexdigest() + ".snapshot"
        published = CheckpointBundle(
            bundle.checkpoint, bundle.sealed_segments, bundle.state_digest, snapshot_ref
        )
        _atomic_write(self.snapshot_directory / snapshot_ref, state_bytes)
        manifest_name = hashlib.sha256(
            bundle.checkpoint.checkpoint_id.encode("utf-8")
        ).hexdigest() + ".json"
        manifest_path = self.checkpoint_directory / manifest_name
        _atomic_write(manifest_path, _canonical_bytes(published.to_dict()))
        # Publishing this pointer last is the commit point for the compacted state.
        _atomic_write(
            self.current_path,
            _canonical_bytes({"manifest": manifest_name, "checksum": bundle.checkpoint.checksum}),
        )
        return published

    publish_compacted_state = publish

    def load_current(self) -> tuple[CheckpointBundle, bytes] | None:
        try:
            pointer = json.loads(self.current_path.read_text("utf-8"))
            manifest_name = pointer["manifest"]
            if not isinstance(manifest_name, str) or Path(manifest_name).name != manifest_name:
                raise WALCheckpointIdentityError("invalid current checkpoint pointer")
            manifest = json.loads((self.checkpoint_directory / manifest_name).read_text("utf-8"))
            bundle = CheckpointBundle.from_dict(manifest)
            if pointer.get("checksum") != bundle.checkpoint.checksum:
                raise WALCheckpointIdentityError("checkpoint pointer checksum mismatch")
            snapshot = (self.snapshot_directory / bundle.snapshot_ref).read_bytes()
            if _sha256(snapshot) != bundle.state_digest:
                raise WALCheckpointIdentityError("compacted snapshot digest mismatch")
            return bundle, snapshot
        except FileNotFoundError:
            return None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise WALCheckpointIdentityError("current checkpoint manifest is corrupt") from exc

    def compact(
        self,
        bundle: CheckpointBundle,
        state: bytes | str | Mapping[str, object],
        *,
        completed_paths: Iterable[str | os.PathLike[str]] = (),
        archive_directory: str | os.PathLike[str] | None = None,
        delete_completed: bool = False,
    ) -> tuple[CheckpointBundle, ArchiveReceipt | None]:
        """Publish first, then archive completed source files if requested."""

        published = self.publish(bundle, state)
        completed = tuple(completed_paths)
        if not completed:
            return published, None
        if archive_directory is None:
            raise WALArchiveError("archive directory is required for completed WAL files")
        return published, archive_completed(
            completed, archive_directory, delete_source=delete_completed
        )


def archive_completed(
    paths: Iterable[str | os.PathLike[str]],
    archive_directory: str | os.PathLike[str],
    *,
    delete_source: bool = False,
) -> ArchiveReceipt:
    """Durably archive every completed file before deleting any source file."""

    source_paths = tuple(Path(path) for path in paths)
    if not source_paths:
        raise WALArchiveError("no completed files supplied for archival")
    archive_root = Path(archive_directory)
    archive_root.mkdir(parents=True, exist_ok=True)
    archived: list[Path] = []
    try:
        for source in source_paths:
            if not source.is_file():
                raise WALArchiveError(f"completed WAL source is unavailable: {source}")
            name = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()
            destination = archive_root / (name + ".wal")
            temporary = archive_root / ("." + name + ".tmp")
            with source.open("rb") as input_stream, temporary.open("wb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
                output_stream.flush()
                os.fsync(output_stream.fileno())
            os.replace(temporary, destination)
            _fsync_directory(archive_root)
            if _sha256(destination.read_bytes()) != _sha256(source.read_bytes()):
                raise WALArchiveError(f"archived WAL copy differs from source: {source}")
            archived.append(destination)
    except BaseException as exc:
        if isinstance(exc, WALArchiveError):
            raise
        raise WALArchiveError("failed to durably archive completed WAL files") from exc
    if delete_source:
        for source in source_paths:
            source.unlink()
            _fsync_directory(source.parent)
    receipt = _sha256(_canonical_bytes([str(path) for path in archived]))
    return ArchiveReceipt(receipt, tuple(str(path) for path in archived))

"""WAL-backed seal transition state machine (IPS-024).

Durable journal for repository/branch seal transitions.  Kit never decides
proof validity: every phase binds opaque immutable CIDs only.  Semantics follow
modern ``core/wal`` committed-only recovery:

* durable intent (begin) precedes every later phase record;
* partial / uncommitted transitions never become current-seal authority;
* fully committed transitions replay deterministically and idempotently;
* a corrupt / torn tail preserves the verified valid prefix;
* file and parent-directory fsync close every append;
* crash-injection hooks expose every phase boundary for later matrices.

Interfaces: ``SealTransitionWal``, ``begin_transition``, ``record_phase``,
``commit_transition``, ``abort_transition``.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Final, Protocol

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ExplicitRootRequiredError,
    ProofSealStoreContractError,
    SealTransitionError,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
    StoreRoot,
    SEAL_TRANSITION_PHASES,
    coerce_artifact_kind,
    validate_explicit_root_path,
)

EVIDENCE_SUBSET: Final[str] = "ips/seal-transition-wal@1"
WAL_STORE_SCHEMA: Final[str] = "ipfs_kit_py/proof_seal_store/wal@1"
WAL_STORE_INTERFACE: Final[str] = "SealTransitionWal@1"
WAL_ENTRY_SCHEMA: Final[str] = (
    "ipfs_kit_py/proof_seal_store/seal-transition-wal-entry@1"
)
CONTRACT_VERSION: Final[int] = 1

_WAL_DIR: Final[str] = "seal_wal"
_SEGMENT_NAME: Final[str] = "transitions.stwal"
_MAGIC: Final[bytes] = b"STWAL1"
_LENGTH: Final[struct.Struct] = struct.Struct(">I")
_DIGEST_BYTES: Final[int] = 32
_MAX_FRAME_PAYLOAD: Final[int] = 256 * 1024
_MAX_SEGMENT_BYTES: Final[int] = 64 * 1024 * 1024

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()

# Closed phase order used by the state machine (plan §9).
PHASE_ORDER: Final[tuple[SealTransitionPhase, ...]] = SEAL_TRANSITION_PHASES
_PHASE_INDEX: Final[dict[SealTransitionPhase, int]] = {
    phase: index for index, phase in enumerate(PHASE_ORDER)
}

# Named crash-injection boundaries for the seal-transition protocol.
CRASH_BOUNDARIES: Final[tuple[str, ...]] = (
    "before_begin",
    "after_begin",
    "before_phase",
    "after_phase",
    "before_commit",
    "after_commit",
    "before_abort",
    "after_abort",
    # Plan §9 failure points (seven joined crash boundaries).
    "before_proof_execution",
    "after_proof_execution",
    "before_receipt_persistence",
    "after_receipt_persistence",
    "before_forest_update",
    "after_forest_update",
    "before_aggregate_generation",
    "after_aggregate_generation",
    "before_seal_persistence",
    "after_seal_persistence",
    "before_current_root_cas",
    "after_current_root_cas",
    "before_cleanup",
    "after_cleanup",
)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class WalEntryKind(str, Enum):
    """Closed kinds of framed seal-transition WAL entries."""

    BEGIN = "begin"
    PHASE = "phase"
    COMMIT = "commit"
    ABORT = "abort"


class WalDisposition(str, Enum):
    """Closed outcomes for seal-transition WAL operations."""

    ACCEPTED = "accepted"
    COMMITTED = "committed"
    ABORTED = "aborted"
    REJECTED = "rejected"
    ERROR = "error"


class WalReason(str, Enum):
    """Closed diagnostic reasons for seal-transition WAL outcomes."""

    OK = "ok"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    ALREADY_TERMINAL = "already_terminal"
    PHASE_ORDER = "phase_order"
    MISSING_SEAL = "missing_seal"
    MALFORMED = "malformed"
    CORRUPTED = "corrupted"
    INTEGRITY_FAILED = "integrity_failed"
    OVER_BUDGET = "over_budget"
    SHORT_WRITE = "short_write"
    FSYNC_FAILED = "fsync_failed"
    SYMLINK_REJECTED = "symlink_rejected"
    PATH_ESCAPE = "path_escape"
    IO_ERROR = "io_error"
    UNCOMMITTED = "uncommitted"
    CRASH_INJECTED = "crash_injected"


# ---------------------------------------------------------------------------
# Errors / results
# ---------------------------------------------------------------------------


class SealTransitionWalError(ProofSealStoreContractError):
    """A seal-transition WAL operation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        reason: WalReason = WalReason.IO_ERROR,
        disposition: WalDisposition | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.disposition = disposition


class SealTransitionWalCrash(SealTransitionWalError):
    """Raised by an optional test crash injector at a named protocol boundary."""

    def __init__(self, boundary: str) -> None:
        super().__init__(
            f"injected seal-transition WAL crash at {boundary}",
            reason=WalReason.CRASH_INJECTED,
            disposition=WalDisposition.ERROR,
        )
        self.boundary = boundary


class SealTransitionWalIntegrityError(SealTransitionWalError):
    """WAL frame bytes failed rehash or structural integrity checks."""


class SealTransitionWalStateError(SealTransitionWalError):
    """Illegal phase / lifecycle transition for an open seal transition."""


@dataclass(frozen=True)
class WalEntry:
    """One framed, content-bound seal-transition journal entry."""

    sequence: int
    kind: WalEntryKind
    record: SealTransitionRecord
    schema: str = WAL_ENTRY_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise SealTransitionWalError(
                "sequence must be an integer",
                reason=WalReason.MALFORMED,
                disposition=WalDisposition.REJECTED,
            )
        if self.sequence < 0:
            raise SealTransitionWalError(
                "sequence must be non-negative",
                reason=WalReason.MALFORMED,
                disposition=WalDisposition.REJECTED,
            )
        kind = self.kind
        if isinstance(kind, str):
            try:
                kind = WalEntryKind(kind)
            except ValueError as exc:
                raise SealTransitionWalError(
                    f"unknown WAL entry kind: {self.kind!r}",
                    reason=WalReason.MALFORMED,
                    disposition=WalDisposition.REJECTED,
                ) from exc
            object.__setattr__(self, "kind", kind)
        if not isinstance(self.kind, WalEntryKind):
            raise SealTransitionWalError(
                "kind must be a closed WalEntryKind",
                reason=WalReason.MALFORMED,
                disposition=WalDisposition.REJECTED,
            )
        if not isinstance(self.record, SealTransitionRecord):
            if isinstance(self.record, Mapping):
                object.__setattr__(
                    self, "record", SealTransitionRecord.from_dict(self.record)
                )
            else:
                raise SealTransitionWalError(
                    "record must be a SealTransitionRecord",
                    reason=WalReason.MALFORMED,
                    disposition=WalDisposition.REJECTED,
                )
        if self.schema != WAL_ENTRY_SCHEMA:
            raise SealTransitionWalError(
                "WAL entry schema mismatch",
                reason=WalReason.MALFORMED,
                disposition=WalDisposition.REJECTED,
            )
        if self.contract_version != CONTRACT_VERSION:
            raise SealTransitionWalError(
                "WAL entry contract_version mismatch",
                reason=WalReason.MALFORMED,
                disposition=WalDisposition.REJECTED,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "sequence": self.sequence,
            "kind": self.kind.value,
            "record": self.record.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> WalEntry:
        if not isinstance(payload, Mapping):
            raise SealTransitionWalError(
                "WAL entry payload must be an object",
                reason=WalReason.CORRUPTED,
                disposition=WalDisposition.ERROR,
            )
        return cls(
            sequence=payload.get("sequence"),  # type: ignore[arg-type]
            kind=payload.get("kind"),  # type: ignore[arg-type]
            record=payload.get("record"),  # type: ignore[arg-type]
            schema=payload.get("schema", WAL_ENTRY_SCHEMA),
            contract_version=payload.get("contract_version", CONTRACT_VERSION),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_dict())


@dataclass(frozen=True)
class WalScanResult:
    """Verified prefix recovered from the seal-transition WAL segment."""

    entries: tuple[WalEntry, ...]
    valid_bytes: int
    tail_corrupt: bool = False
    error: str = ""

    @property
    def sequences(self) -> tuple[int, ...]:
        return tuple(entry.sequence for entry in self.entries)


@dataclass(frozen=True)
class WalOperationResult:
    """Structured outcome of a seal-transition WAL mutation."""

    disposition: WalDisposition
    reason: WalReason
    record: SealTransitionRecord | None = None
    entry: WalEntry | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition in {
            WalDisposition.ACCEPTED,
            WalDisposition.COMMITTED,
            WalDisposition.ABORTED,
        }


@dataclass(frozen=True)
class CommittedTransitionView:
    """Committed-only projection used for deterministic replay.

    Uncommitted / aborted / in-progress transitions never appear here and
    therefore cannot become current-seal authority through the WAL surface.
    """

    transition_id: str
    repository_id: str
    branch_id: str
    new_seal_cid: str
    new_seal_kind: ArtifactKind
    generation: int
    expected_parent_seal_cid: str
    artifact_cids: tuple[str, ...]
    phase: SealTransitionPhase
    sequence: int
    record: SealTransitionRecord

    @property
    def namespace_key(self) -> str:
        return f"{self.repository_id}#{self.branch_id}"

    @property
    def is_current_eligible(self) -> bool:
        """Committed seal bindings are the only WAL-eligible current roots."""

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "repository_id": self.repository_id,
            "branch_id": self.branch_id,
            "new_seal_cid": self.new_seal_cid,
            "new_seal_kind": self.new_seal_kind.value,
            "generation": self.generation,
            "expected_parent_seal_cid": self.expected_parent_seal_cid,
            "artifact_cids": list(self.artifact_cids),
            "phase": self.phase.value,
            "sequence": self.sequence,
            "record": self.record.to_dict(),
        }


# ---------------------------------------------------------------------------
# Durability injection
# ---------------------------------------------------------------------------


class DurabilityOperations(Protocol):
    """Injectable OS operations used by the seal-transition WAL.

    Tests can fault-inject every durability boundary.  ``write`` may make a
    short write; the append path retries until the entire frame is written.
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
            raise SealTransitionWalError(
                f"unable to open WAL parent directory for fsync: {directory}",
                reason=WalReason.FSYNC_FAILED,
                disposition=WalDisposition.ERROR,
            ) from exc
        try:
            os.fsync(descriptor)
        except OSError as exc:
            raise SealTransitionWalError(
                f"unable to fsync WAL parent directory: {directory}",
                reason=WalReason.FSYNC_FAILED,
                disposition=WalDisposition.ERROR,
            ) from exc
        finally:
            os.close(descriptor)


DEFAULT_DURABILITY_OPERATIONS: DurabilityOperations = _SystemDurabilityOperations()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _thread_lock(root: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(root))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def frame_bytes(entry: WalEntry) -> bytes:
    """Return the independently verifiable on-disk frame for ``entry``."""

    payload = entry.canonical_bytes()
    if len(payload) > _MAX_FRAME_PAYLOAD:
        raise SealTransitionWalError(
            f"WAL entry frame exceeds {_MAX_FRAME_PAYLOAD} bytes",
            reason=WalReason.OVER_BUDGET,
            disposition=WalDisposition.REJECTED,
        )
    return _MAGIC + _LENGTH.pack(len(payload)) + payload + hashlib.sha256(payload).digest()


def phase_index(phase: SealTransitionPhase | str) -> int:
    """Return the closed ordinal of a seal-transition phase."""

    if isinstance(phase, str):
        phase = SealTransitionPhase(phase)
    if not isinstance(phase, SealTransitionPhase):
        raise SealTransitionWalError(
            "phase must be a closed SealTransitionPhase",
            reason=WalReason.MALFORMED,
            disposition=WalDisposition.REJECTED,
        )
    return _PHASE_INDEX[phase]


def next_phase(phase: SealTransitionPhase) -> SealTransitionPhase | None:
    """Return the successor phase, or ``None`` when ``phase`` is terminal."""

    index = phase_index(phase)
    if index + 1 >= len(PHASE_ORDER):
        return None
    return PHASE_ORDER[index + 1]


def _optional_cid_list(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SealTransitionWalError(
            f"{field_name} must be a sequence of CIDs",
            reason=WalReason.MALFORMED,
            disposition=WalDisposition.REJECTED,
        )
    # SealTransitionRecord validates CID shape and uniqueness.
    return tuple(value)


def _merge_artifact_cids(
    existing: Sequence[str], added: Sequence[str]
) -> tuple[str, ...]:
    merged: list[str] = list(existing)
    seen = set(existing)
    for cid in added:
        if cid in seen:
            continue
        merged.append(cid)
        seen.add(cid)
    return tuple(merged)


def _is_terminal(state: SealTransitionState) -> bool:
    return state in {
        SealTransitionState.COMMITTED,
        SealTransitionState.ABORTED,
        SealTransitionState.FAILED,
    }


def _phase_boundary_name(phase: SealTransitionPhase, when: str) -> str:
    return f"{when}_{phase.value}"


# ---------------------------------------------------------------------------
# Scan / committed-only projection (pure functions over entries)
# ---------------------------------------------------------------------------


def recover_wal_bytes(
    data: bytes,
    *,
    disposition_label: str = "bound_and_report",
) -> WalScanResult:
    """Recover the verified prefix of raw segment bytes.

    A short frame, invalid JSON/record, checksum mismatch, or non-contiguous
    sequence is a corrupt tail.  The valid prefix is always retained.
    """

    del disposition_label  # reserved for future truncate/quarantine policies
    entries: list[WalEntry] = []
    valid_bytes = 0
    expected_sequence = 0
    offset = 0
    length = len(data)

    while offset < length:
        remaining = length - offset
        if remaining < len(_MAGIC):
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error="short frame magic",
            )
        header = data[offset : offset + len(_MAGIC)]
        if header != _MAGIC:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error="invalid frame magic",
            )
        length_start = offset + len(_MAGIC)
        length_end = length_start + _LENGTH.size
        if length_end > length:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error="short frame length",
            )
        payload_len = _LENGTH.unpack(data[length_start:length_end])[0]
        if payload_len > _MAX_FRAME_PAYLOAD:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error="frame length exceeds limit",
            )
        payload_start = length_end
        payload_end = payload_start + payload_len
        digest_end = payload_end + _DIGEST_BYTES
        if digest_end > length:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error="short frame payload",
            )
        payload = data[payload_start:payload_end]
        digest = data[payload_end:digest_end]
        if hashlib.sha256(payload).digest() != digest:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error="frame checksum mismatch",
            )
        try:
            parsed = json.loads(payload.decode("utf-8"))
            entry = WalEntry.from_dict(parsed)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ProofSealStoreContractError,
            SealTransitionError,
            TypeError,
            ValueError,
        ) as exc:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error=f"invalid WAL entry: {exc}",
            )
        if entry.sequence != expected_sequence:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error=(
                    f"non-contiguous sequence: expected {expected_sequence}, "
                    f"got {entry.sequence}"
                ),
            )
        # Rehash binding: payload must equal canonical encoding.
        if entry.canonical_bytes() != payload:
            return WalScanResult(
                tuple(entries),
                valid_bytes,
                tail_corrupt=True,
                error="entry bytes failed canonical rehash binding",
            )
        entries.append(entry)
        expected_sequence += 1
        valid_bytes = digest_end
        offset = digest_end

    return WalScanResult(tuple(entries), valid_bytes, tail_corrupt=False)


def project_transition_states(
    entries: Sequence[WalEntry],
) -> dict[str, SealTransitionRecord]:
    """Fold journal entries into the latest durable state per transition_id."""

    latest: dict[str, SealTransitionRecord] = {}
    for entry in entries:
        transition_id = entry.record.transition_id
        prior = latest.get(transition_id)
        if prior is not None and _is_terminal(prior.state):
            # Terminal states are sticky: later frames for the same id are
            # ignored so a torn post-commit append cannot revive or mutate them.
            continue
        if entry.kind is WalEntryKind.BEGIN and prior is not None:
            # Duplicate begin after any progress is ignored (fail closed later
            # on the write path; scan still retains the first durable begin).
            continue
        latest[transition_id] = entry.record
    return latest


def committed_transition_views(
    entries: Sequence[WalEntry],
) -> tuple[CommittedTransitionView, ...]:
    """Return committed-only views in deterministic journal order.

    A transition becomes current-eligible only when a durable ``commit`` entry
    exists.  Partial phase records and aborted transitions are omitted.
    """

    # Track begin presence and whether an abort precedes commit.
    seen_begin: set[str] = set()
    aborted: set[str] = set()
    committed: list[CommittedTransitionView] = []
    committed_ids: set[str] = set()

    for entry in entries:
        transition_id = entry.record.transition_id
        if entry.kind is WalEntryKind.BEGIN:
            seen_begin.add(transition_id)
            continue
        if entry.kind is WalEntryKind.ABORT:
            if transition_id not in committed_ids:
                aborted.add(transition_id)
            continue
        if entry.kind is WalEntryKind.COMMIT:
            if transition_id in committed_ids:
                continue
            if transition_id in aborted:
                continue
            if transition_id not in seen_begin:
                # Commit without durable intent never becomes current.
                continue
            record = entry.record
            if record.state is not SealTransitionState.COMMITTED:
                continue
            if not record.new_seal_cid or record.new_seal_kind is None:
                continue
            committed.append(
                CommittedTransitionView(
                    transition_id=transition_id,
                    repository_id=record.repository_id,
                    branch_id=record.branch_id,
                    new_seal_cid=record.new_seal_cid,
                    new_seal_kind=record.new_seal_kind,
                    generation=record.generation,
                    expected_parent_seal_cid=record.expected_parent_seal_cid,
                    artifact_cids=record.artifact_cids,
                    phase=record.phase,
                    sequence=entry.sequence,
                    record=record,
                )
            )
            committed_ids.add(transition_id)
    return tuple(committed)


def is_current_eligible(
    entries: Sequence[WalEntry], transition_id: str
) -> bool:
    """Return whether ``transition_id`` may become current via committed replay."""

    return any(view.transition_id == transition_id for view in committed_transition_views(entries))


# ---------------------------------------------------------------------------
# SealTransitionWal
# ---------------------------------------------------------------------------


class SealTransitionWal:
    """Append-only WAL state machine for durable seal transitions.

    Construction requires an explicit :class:`StoreRoot`.  There is no default
    under ``~``, ``$XDG_*``, ``~/.ipfs``, or any daemon path.
    """

    __test__ = False

    def __init__(
        self,
        root: StoreRoot | str | Path | os.PathLike[str] | None,
        *,
        create: bool = True,
        crash_injector: Callable[..., Any] | None = None,
        durability: DurabilityOperations | None = None,
    ) -> None:
        if root is None:
            raise ExplicitRootRequiredError(
                "SealTransitionWal requires an explicit StoreRoot; "
                "no default user-state or daemon root exists"
            )
        if isinstance(root, StoreRoot):
            store_root = root
        else:
            store_root = StoreRoot.require(root)
        validate_explicit_root_path(store_root.root_path, field_name="root_path")

        self._root = store_root
        self._root_path = Path(store_root.root_path)
        self._lock = _thread_lock(self._root_path)
        self._crash_injector = crash_injector
        self._durability = durability or DEFAULT_DURABILITY_OPERATIONS
        self._handle: BinaryIO | None = None
        self._next_sequence = 0
        self._entries: list[WalEntry] = []
        self._latest: dict[str, SealTransitionRecord] = {}
        self._closed = False
        self._tail_corrupt = False
        self._valid_bytes = 0
        self._scan_error = ""

        if self._root_path.exists() and self._root_path.is_symlink():
            raise SealTransitionWalError(
                "store root must not be a symlink",
                reason=WalReason.SYMLINK_REJECTED,
                disposition=WalDisposition.ERROR,
            )
        if create:
            self._ensure_root()
        self._load_existing()

    # -- protocol surface ---------------------------------------------------

    @property
    def root(self) -> StoreRoot:
        """Return the mandatory explicit store root."""

        return self._root

    @property
    def root_path(self) -> Path:
        return self._root_path

    @property
    def segment_path(self) -> Path:
        return self._root_path / _WAL_DIR / _SEGMENT_NAME

    @property
    def sequence_count(self) -> int:
        with self._lock:
            return self._next_sequence

    def begin_transition(
        self, record: SealTransitionRecord
    ) -> SealTransitionRecord:
        """Journal durable intent for a new seal transition.

        The begin marker is the durable intent that precedes every later phase
        effect.  Partial work without this marker cannot become current.
        """

        result = self.begin_transition_result(record)
        if not result or result.record is None:
            raise SealTransitionWalStateError(
                f"begin_transition rejected: {result.reason.value}",
                reason=result.reason,
                disposition=result.disposition,
            )
        return result.record

    def begin_transition_result(
        self, record: SealTransitionRecord
    ) -> WalOperationResult:
        if not isinstance(record, SealTransitionRecord):
            return WalOperationResult(
                WalDisposition.REJECTED,
                WalReason.MALFORMED,
                diagnostics={"error": "record must be a SealTransitionRecord"},
            )
        if record.phase is not SealTransitionPhase.INTENT:
            return WalOperationResult(
                WalDisposition.REJECTED,
                WalReason.PHASE_ORDER,
                record=record,
                diagnostics={"error": "begin_transition requires INTENT phase"},
            )
        if record.state not in {
            SealTransitionState.OPEN,
            SealTransitionState.IN_PROGRESS,
        }:
            return WalOperationResult(
                WalDisposition.REJECTED,
                WalReason.MALFORMED,
                record=record,
                diagnostics={"error": "begin_transition requires OPEN/IN_PROGRESS state"},
            )

        with self._lock:
            if self._closed:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    WalReason.IO_ERROR,
                    diagnostics={"error": "WAL is closed"},
                )
            if record.transition_id in self._latest:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.ALREADY_EXISTS,
                    record=self._latest[record.transition_id],
                    diagnostics={"error": "transition_id already journaled"},
                )

            begun = SealTransitionRecord(
                transition_id=record.transition_id,
                repository_id=record.repository_id,
                branch_id=record.branch_id,
                phase=SealTransitionPhase.INTENT,
                state=SealTransitionState.OPEN,
                expected_parent_seal_cid=record.expected_parent_seal_cid,
                new_seal_cid=record.new_seal_cid,
                new_seal_kind=record.new_seal_kind,
                generation=record.generation,
                artifact_cids=record.artifact_cids,
            )
            try:
                self._boundary("before_begin", begun.transition_id)
                entry = self._append(WalEntryKind.BEGIN, begun)
                self._boundary("after_begin", begun.transition_id)
            except SealTransitionWalCrash:
                raise
            except SealTransitionWalError as exc:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    exc.reason,
                    record=begun,
                    diagnostics={"error": str(exc)},
                )
            return WalOperationResult(
                WalDisposition.ACCEPTED,
                WalReason.OK,
                record=entry.record,
                entry=entry,
            )

    def record_phase(
        self,
        transition_id: str,
        phase: SealTransitionPhase | str,
        *,
        artifact_cids: Sequence[str] = (),
        new_seal_cid: str = "",
        new_seal_kind: ArtifactKind | str | None = None,
        generation: int | None = None,
        expected_parent_seal_cid: str | None = None,
    ) -> SealTransitionRecord:
        """Journal a sealed phase advance with immutable CID bindings."""

        result = self.record_phase_result(
            transition_id,
            phase,
            artifact_cids=artifact_cids,
            new_seal_cid=new_seal_cid,
            new_seal_kind=new_seal_kind,
            generation=generation,
            expected_parent_seal_cid=expected_parent_seal_cid,
        )
        if not result or result.record is None:
            raise SealTransitionWalStateError(
                f"record_phase rejected: {result.reason.value}",
                reason=result.reason,
                disposition=result.disposition,
            )
        return result.record

    def record_phase_result(
        self,
        transition_id: str,
        phase: SealTransitionPhase | str,
        *,
        artifact_cids: Sequence[str] = (),
        new_seal_cid: str = "",
        new_seal_kind: ArtifactKind | str | None = None,
        generation: int | None = None,
        expected_parent_seal_cid: str | None = None,
    ) -> WalOperationResult:
        if type(transition_id) is not str or not transition_id.strip():
            return WalOperationResult(
                WalDisposition.REJECTED,
                WalReason.MALFORMED,
                diagnostics={"error": "transition_id must be a non-empty string"},
            )
        try:
            target_phase = (
                phase
                if isinstance(phase, SealTransitionPhase)
                else SealTransitionPhase(phase)
            )
        except (TypeError, ValueError):
            return WalOperationResult(
                WalDisposition.REJECTED,
                WalReason.MALFORMED,
                diagnostics={"error": f"unknown phase: {phase!r}"},
            )

        try:
            added_cids = _optional_cid_list(artifact_cids, "artifact_cids")
        except SealTransitionWalError as exc:
            return WalOperationResult(
                WalDisposition.REJECTED,
                exc.reason,
                diagnostics={"error": str(exc)},
            )

        with self._lock:
            if self._closed:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    WalReason.IO_ERROR,
                    diagnostics={"error": "WAL is closed"},
                )
            current = self._latest.get(transition_id)
            if current is None:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.NOT_FOUND,
                    diagnostics={"error": f"unknown transition_id: {transition_id}"},
                )
            if _is_terminal(current.state):
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.ALREADY_TERMINAL,
                    record=current,
                    diagnostics={"error": "transition is already terminal"},
                )

            current_index = phase_index(current.phase)
            target_index = phase_index(target_phase)
            # Allow re-recording the same phase (idempotent CID accumulation)
            # or advancing exactly one step; never skip or reverse.
            if target_index < current_index:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.PHASE_ORDER,
                    record=current,
                    diagnostics={
                        "error": (
                            f"phase regression forbidden: {current.phase.value} "
                            f"-> {target_phase.value}"
                        )
                    },
                )
            if target_index > current_index + 1:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.PHASE_ORDER,
                    record=current,
                    diagnostics={
                        "error": (
                            f"phase skip forbidden: {current.phase.value} "
                            f"-> {target_phase.value}"
                        )
                    },
                )

            kind = new_seal_kind
            if kind is None or kind == "":
                kind = current.new_seal_kind
            elif not isinstance(kind, ArtifactKind):
                try:
                    kind = coerce_artifact_kind(kind, field_name="new_seal_kind")
                except ProofSealStoreContractError as exc:
                    return WalOperationResult(
                        WalDisposition.REJECTED,
                        WalReason.MALFORMED,
                        record=current,
                        diagnostics={"error": str(exc)},
                    )

            seal_cid = new_seal_cid if new_seal_cid else current.new_seal_cid
            gen = current.generation if generation is None else generation
            parent = (
                current.expected_parent_seal_cid
                if expected_parent_seal_cid is None
                else expected_parent_seal_cid
            )
            merged_cids = _merge_artifact_cids(current.artifact_cids, added_cids)

            try:
                advanced = SealTransitionRecord(
                    transition_id=current.transition_id,
                    repository_id=current.repository_id,
                    branch_id=current.branch_id,
                    phase=target_phase,
                    state=SealTransitionState.IN_PROGRESS,
                    expected_parent_seal_cid=parent,
                    new_seal_cid=seal_cid,
                    new_seal_kind=kind,
                    generation=gen,
                    artifact_cids=merged_cids,
                )
            except (ProofSealStoreContractError, SealTransitionError) as exc:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.MALFORMED,
                    record=current,
                    diagnostics={"error": str(exc)},
                )

            try:
                self._boundary("before_phase", transition_id, phase=target_phase)
                self._boundary(
                    _phase_boundary_name(target_phase, "before"),
                    transition_id,
                    phase=target_phase,
                )
                entry = self._append(WalEntryKind.PHASE, advanced)
                self._boundary(
                    _phase_boundary_name(target_phase, "after"),
                    transition_id,
                    phase=target_phase,
                )
                self._boundary("after_phase", transition_id, phase=target_phase)
            except SealTransitionWalCrash:
                raise
            except SealTransitionWalError as exc:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    exc.reason,
                    record=advanced,
                    diagnostics={"error": str(exc)},
                )
            return WalOperationResult(
                WalDisposition.ACCEPTED,
                WalReason.OK,
                record=entry.record,
                entry=entry,
            )

    def commit_transition(
        self,
        transition_id: str,
        *,
        new_seal_cid: str | None = None,
        new_seal_kind: ArtifactKind | str | None = None,
        phase: SealTransitionPhase | str | None = None,
        artifact_cids: Sequence[str] = (),
        generation: int | None = None,
    ) -> SealTransitionRecord:
        """Journal a durable commit.  Only committed records become current-eligible."""

        result = self.commit_transition_result(
            transition_id,
            new_seal_cid=new_seal_cid,
            new_seal_kind=new_seal_kind,
            phase=phase,
            artifact_cids=artifact_cids,
            generation=generation,
        )
        if not result or result.record is None:
            raise SealTransitionWalStateError(
                f"commit_transition rejected: {result.reason.value}",
                reason=result.reason,
                disposition=result.disposition,
            )
        return result.record

    def commit_transition_result(
        self,
        transition_id: str,
        *,
        new_seal_cid: str | None = None,
        new_seal_kind: ArtifactKind | str | None = None,
        phase: SealTransitionPhase | str | None = None,
        artifact_cids: Sequence[str] = (),
        generation: int | None = None,
    ) -> WalOperationResult:
        if type(transition_id) is not str or not transition_id.strip():
            return WalOperationResult(
                WalDisposition.REJECTED,
                WalReason.MALFORMED,
                diagnostics={"error": "transition_id must be a non-empty string"},
            )

        with self._lock:
            if self._closed:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    WalReason.IO_ERROR,
                    diagnostics={"error": "WAL is closed"},
                )
            current = self._latest.get(transition_id)
            if current is None:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.NOT_FOUND,
                    diagnostics={"error": f"unknown transition_id: {transition_id}"},
                )
            if current.state is SealTransitionState.COMMITTED:
                return WalOperationResult(
                    WalDisposition.COMMITTED,
                    WalReason.OK,
                    record=current,
                    diagnostics={"idempotent": True},
                )
            if _is_terminal(current.state):
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.ALREADY_TERMINAL,
                    record=current,
                    diagnostics={"error": "cannot commit a terminal non-committed transition"},
                )

            seal_cid = new_seal_cid if new_seal_cid is not None else current.new_seal_cid
            kind: ArtifactKind | str | None = (
                new_seal_kind if new_seal_kind is not None else current.new_seal_kind
            )
            if not seal_cid or kind is None or kind == "":
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.MISSING_SEAL,
                    record=current,
                    diagnostics={
                        "error": "commit requires new_seal_cid and new_seal_kind"
                    },
                )
            if not isinstance(kind, ArtifactKind):
                try:
                    kind = coerce_artifact_kind(kind, field_name="new_seal_kind")
                except ProofSealStoreContractError as exc:
                    return WalOperationResult(
                        WalDisposition.REJECTED,
                        WalReason.MALFORMED,
                        record=current,
                        diagnostics={"error": str(exc)},
                    )

            if phase is None:
                commit_phase = current.phase
                if commit_phase not in {
                    SealTransitionPhase.SEAL_PERSISTENCE,
                    SealTransitionPhase.CURRENT_ROOT_CAS,
                    SealTransitionPhase.CLEANUP,
                }:
                    # Default terminal phase when commit is requested after CAS work.
                    commit_phase = SealTransitionPhase.CLEANUP
            else:
                try:
                    commit_phase = (
                        phase
                        if isinstance(phase, SealTransitionPhase)
                        else SealTransitionPhase(phase)
                    )
                except (TypeError, ValueError):
                    return WalOperationResult(
                        WalDisposition.REJECTED,
                        WalReason.MALFORMED,
                        record=current,
                        diagnostics={"error": f"unknown phase: {phase!r}"},
                    )
            if commit_phase not in {
                SealTransitionPhase.SEAL_PERSISTENCE,
                SealTransitionPhase.CURRENT_ROOT_CAS,
                SealTransitionPhase.CLEANUP,
            }:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.PHASE_ORDER,
                    record=current,
                    diagnostics={
                        "error": "commit phase must be seal_persistence, "
                        "current_root_cas, or cleanup"
                    },
                )

            try:
                added = _optional_cid_list(artifact_cids, "artifact_cids")
            except SealTransitionWalError as exc:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    exc.reason,
                    record=current,
                    diagnostics={"error": str(exc)},
                )
            merged = _merge_artifact_cids(current.artifact_cids, added)
            gen = current.generation if generation is None else generation

            try:
                committed = SealTransitionRecord(
                    transition_id=current.transition_id,
                    repository_id=current.repository_id,
                    branch_id=current.branch_id,
                    phase=commit_phase,
                    state=SealTransitionState.COMMITTED,
                    expected_parent_seal_cid=current.expected_parent_seal_cid,
                    new_seal_cid=seal_cid,
                    new_seal_kind=kind,
                    generation=gen,
                    artifact_cids=merged,
                )
            except (ProofSealStoreContractError, SealTransitionError) as exc:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.MALFORMED,
                    record=current,
                    diagnostics={"error": str(exc)},
                )

            try:
                self._boundary("before_commit", transition_id)
                entry = self._append(WalEntryKind.COMMIT, committed)
                self._boundary("after_commit", transition_id)
            except SealTransitionWalCrash:
                raise
            except SealTransitionWalError as exc:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    exc.reason,
                    record=committed,
                    diagnostics={"error": str(exc)},
                )
            return WalOperationResult(
                WalDisposition.COMMITTED,
                WalReason.OK,
                record=entry.record,
                entry=entry,
            )

    def abort_transition(
        self,
        transition_id: str,
        *,
        phase: SealTransitionPhase | str | None = None,
    ) -> SealTransitionRecord:
        """Journal a durable abort.  Aborted transitions never become current."""

        result = self.abort_transition_result(transition_id, phase=phase)
        if not result or result.record is None:
            raise SealTransitionWalStateError(
                f"abort_transition rejected: {result.reason.value}",
                reason=result.reason,
                disposition=result.disposition,
            )
        return result.record

    def abort_transition_result(
        self,
        transition_id: str,
        *,
        phase: SealTransitionPhase | str | None = None,
    ) -> WalOperationResult:
        if type(transition_id) is not str or not transition_id.strip():
            return WalOperationResult(
                WalDisposition.REJECTED,
                WalReason.MALFORMED,
                diagnostics={"error": "transition_id must be a non-empty string"},
            )

        with self._lock:
            if self._closed:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    WalReason.IO_ERROR,
                    diagnostics={"error": "WAL is closed"},
                )
            current = self._latest.get(transition_id)
            if current is None:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.NOT_FOUND,
                    diagnostics={"error": f"unknown transition_id: {transition_id}"},
                )
            if current.state is SealTransitionState.ABORTED:
                return WalOperationResult(
                    WalDisposition.ABORTED,
                    WalReason.OK,
                    record=current,
                    diagnostics={"idempotent": True},
                )
            if current.state is SealTransitionState.COMMITTED:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.ALREADY_TERMINAL,
                    record=current,
                    diagnostics={"error": "refusing to abort a committed transition"},
                )

            abort_phase = current.phase if phase is None else phase
            try:
                abort_phase_enum = (
                    abort_phase
                    if isinstance(abort_phase, SealTransitionPhase)
                    else SealTransitionPhase(abort_phase)
                )
            except (TypeError, ValueError):
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.MALFORMED,
                    record=current,
                    diagnostics={"error": f"unknown phase: {phase!r}"},
                )

            try:
                aborted = SealTransitionRecord(
                    transition_id=current.transition_id,
                    repository_id=current.repository_id,
                    branch_id=current.branch_id,
                    phase=abort_phase_enum,
                    state=SealTransitionState.ABORTED,
                    expected_parent_seal_cid=current.expected_parent_seal_cid,
                    new_seal_cid=current.new_seal_cid,
                    new_seal_kind=current.new_seal_kind,
                    generation=current.generation,
                    artifact_cids=current.artifact_cids,
                )
            except (ProofSealStoreContractError, SealTransitionError) as exc:
                return WalOperationResult(
                    WalDisposition.REJECTED,
                    WalReason.MALFORMED,
                    record=current,
                    diagnostics={"error": str(exc)},
                )

            try:
                self._boundary("before_abort", transition_id)
                entry = self._append(WalEntryKind.ABORT, aborted)
                self._boundary("after_abort", transition_id)
            except SealTransitionWalCrash:
                raise
            except SealTransitionWalError as exc:
                return WalOperationResult(
                    WalDisposition.ERROR,
                    exc.reason,
                    record=aborted,
                    diagnostics={"error": str(exc)},
                )
            return WalOperationResult(
                WalDisposition.ABORTED,
                WalReason.OK,
                record=entry.record,
                entry=entry,
            )

    # -- read / replay surface ----------------------------------------------

    def get_transition(self, transition_id: str) -> SealTransitionRecord | None:
        """Return the latest durable record for ``transition_id``, if any."""

        with self._lock:
            return self._latest.get(transition_id)

    def scan(self) -> WalScanResult:
        """Read the verified prefix of the on-disk segment."""

        with self._lock:
            return self._scan_unlocked()

    def entries(self) -> tuple[WalEntry, ...]:
        """Return the verified in-memory journal prefix (committed and not)."""

        with self._lock:
            return tuple(self._entries)

    def committed_transitions(self) -> tuple[CommittedTransitionView, ...]:
        """Return committed-only projections in deterministic order."""

        with self._lock:
            return committed_transition_views(self._entries)

    def replay_committed(self) -> tuple[CommittedTransitionView, ...]:
        """Deterministic committed-only replay (identical across restarts)."""

        return self.committed_transitions()

    def open_transitions(self) -> tuple[SealTransitionRecord, ...]:
        """Return non-terminal transitions (recovery input; never current)."""

        with self._lock:
            open_records = [
                record
                for record in self._latest.values()
                if not _is_terminal(record.state)
            ]
            open_records.sort(key=lambda item: (item.repository_id, item.branch_id, item.transition_id))
            return tuple(open_records)

    def is_current_eligible(self, transition_id: str) -> bool:
        """Whether ``transition_id`` may become current (committed-only)."""

        with self._lock:
            return is_current_eligible(self._entries, transition_id)

    def current_eligible_seals(
        self, repository_id: str | None = None, branch_id: str | None = None
    ) -> tuple[CommittedTransitionView, ...]:
        """Committed seal bindings eligible to become current.

        Partial / uncommitted / aborted records are never returned.
        """

        views = self.committed_transitions()
        if repository_id is None and branch_id is None:
            return views
        filtered: list[CommittedTransitionView] = []
        for view in views:
            if repository_id is not None and view.repository_id != repository_id:
                continue
            if branch_id is not None and view.branch_id != branch_id:
                continue
            filtered.append(view)
        return tuple(filtered)

    def close(self) -> None:
        with self._lock:
            if self._handle is not None:
                try:
                    self._handle.close()
                except OSError:
                    pass
                self._handle = None
            self._closed = True

    def __enter__(self) -> SealTransitionWal:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internal durability ------------------------------------------------

    def _ensure_root(self) -> None:
        self._root_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        wal_dir = self._root_path / _WAL_DIR
        wal_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in (self._root_path, wal_dir):
            if path.is_symlink():
                raise SealTransitionWalError(
                    "WAL path must not be a symlink",
                    reason=WalReason.SYMLINK_REJECTED,
                    disposition=WalDisposition.ERROR,
                )

    def _load_existing(self) -> None:
        path = self.segment_path
        if not path.exists():
            self._entries = []
            self._latest = {}
            self._next_sequence = 0
            self._tail_corrupt = False
            self._valid_bytes = 0
            self._scan_error = ""
            return
        if path.is_symlink():
            raise SealTransitionWalError(
                "WAL segment must not be a symlink",
                reason=WalReason.SYMLINK_REJECTED,
                disposition=WalDisposition.ERROR,
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise SealTransitionWalError(
                f"unable to read WAL segment: {path}",
                reason=WalReason.IO_ERROR,
                disposition=WalDisposition.ERROR,
            ) from exc
        if len(data) > _MAX_SEGMENT_BYTES:
            raise SealTransitionWalError(
                "WAL segment exceeds size bound",
                reason=WalReason.OVER_BUDGET,
                disposition=WalDisposition.ERROR,
            )
        scanned = recover_wal_bytes(data)
        self._entries = list(scanned.entries)
        self._latest = project_transition_states(self._entries)
        self._next_sequence = len(self._entries)
        # Open for append at the valid prefix.  A corrupt tail is left in place
        # so operators can inspect it; new frames append after valid_bytes only
        # when the file ends exactly at valid_bytes.  If a torn tail remains,
        # refuse to append through it (fail closed) — callers must reopen after
        # explicit truncate via recover_and_truncate_tail().
        self._tail_corrupt = scanned.tail_corrupt
        self._valid_bytes = scanned.valid_bytes
        self._scan_error = scanned.error

    def recover_and_truncate_tail(self) -> WalScanResult:
        """Truncate a corrupt tail to the verified prefix and reopen for append."""

        with self._lock:
            scanned = self._scan_unlocked()
            if not scanned.tail_corrupt:
                return scanned
            path = self.segment_path
            try:
                if self._handle is not None:
                    self._handle.close()
                    self._handle = None
                with open(path, "r+b", buffering=0) as handle:
                    handle.truncate(scanned.valid_bytes)
                    self._durability.flush(handle)
                    self._durability.fsync_file(handle)
                self._durability.fsync_directory(path.parent)
            except SealTransitionWalError:
                raise
            except Exception as exc:
                raise SealTransitionWalError(
                    f"unable to truncate corrupt WAL tail in {path}",
                    reason=WalReason.FSYNC_FAILED,
                    disposition=WalDisposition.ERROR,
                ) from exc
            self._tail_corrupt = False
            self._valid_bytes = scanned.valid_bytes
            self._scan_error = ""
            self._entries = list(scanned.entries)
            self._latest = project_transition_states(self._entries)
            self._next_sequence = len(self._entries)
            return WalScanResult(
                tuple(self._entries),
                self._valid_bytes,
                tail_corrupt=False,
                error="",
            )

    def _scan_unlocked(self) -> WalScanResult:
        path = self.segment_path
        if not path.exists():
            return WalScanResult((), 0)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise SealTransitionWalError(
                f"unable to read WAL segment: {path}",
                reason=WalReason.IO_ERROR,
                disposition=WalDisposition.ERROR,
            ) from exc
        return recover_wal_bytes(data)

    def _ensure_handle(self) -> BinaryIO:
        if self._tail_corrupt:
            raise SealTransitionWalError(
                "refusing to append through a corrupt WAL tail; "
                "call recover_and_truncate_tail() first",
                reason=WalReason.CORRUPTED,
                disposition=WalDisposition.ERROR,
            )
        if self._handle is not None and not self._handle.closed:
            return self._handle
        path = self.segment_path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = open(path, "a+b", buffering=0)
        # Position at end; size must match valid prefix when no corrupt tail.
        handle.seek(0, os.SEEK_END)
        self._handle = handle
        return handle

    def _append(self, kind: WalEntryKind, record: SealTransitionRecord) -> WalEntry:
        entry = WalEntry(
            sequence=self._next_sequence,
            kind=kind,
            record=record,
        )
        frame = frame_bytes(entry)
        handle = self._ensure_handle()
        offset = 0
        try:
            while offset < len(frame):
                written = self._durability.write(handle, frame[offset:])
                if written is None or written <= 0:
                    raise SealTransitionWalError(
                        f"short WAL write at {offset} of {len(frame)} bytes",
                        reason=WalReason.SHORT_WRITE,
                        disposition=WalDisposition.ERROR,
                    )
                if written > len(frame) - offset:
                    raise SealTransitionWalError(
                        f"writer reported {written} bytes for only "
                        f"{len(frame) - offset} available bytes",
                        reason=WalReason.SHORT_WRITE,
                        disposition=WalDisposition.ERROR,
                    )
                offset += written
            try:
                self._durability.flush(handle)
                self._durability.fsync_file(handle)
                self._durability.fsync_directory(self.segment_path.parent)
            except SealTransitionWalError:
                raise
            except Exception as exc:
                raise SealTransitionWalError(
                    f"unable to durable-sync WAL append: {exc}",
                    reason=WalReason.FSYNC_FAILED,
                    disposition=WalDisposition.ERROR,
                ) from exc
        except SealTransitionWalError:
            raise
        except Exception as exc:
            raise SealTransitionWalError(
                "unable to write WAL frame",
                reason=WalReason.SHORT_WRITE,
                disposition=WalDisposition.ERROR,
            ) from exc

        self._entries.append(entry)
        self._latest[record.transition_id] = record
        self._next_sequence += 1
        self._valid_bytes += len(frame)
        return entry

    def _boundary(
        self,
        name: str,
        transition_id: str,
        *,
        phase: SealTransitionPhase | None = None,
    ) -> None:
        if self._crash_injector is None:
            return
        try:
            if phase is not None:
                self._crash_injector(name, transition_id, phase)
            else:
                self._crash_injector(name, transition_id)
        except TypeError:
            try:
                self._crash_injector(name, transition_id)
            except TypeError:
                self._crash_injector(name)
        except SealTransitionWalCrash:
            raise
        # Allow injectors to raise arbitrary exceptions; wrap known crash type
        # only when the injector returns a boundary name string.
        return


# ---------------------------------------------------------------------------
# Module-level helpers matching pointer.py style
# ---------------------------------------------------------------------------


def begin_transition(
    wal: SealTransitionWal, record: SealTransitionRecord
) -> SealTransitionRecord:
    """Module-level alias for :meth:`SealTransitionWal.begin_transition`."""

    return wal.begin_transition(record)


def record_phase(
    wal: SealTransitionWal,
    transition_id: str,
    phase: SealTransitionPhase | str,
    **kwargs: Any,
) -> SealTransitionRecord:
    """Module-level alias for :meth:`SealTransitionWal.record_phase`."""

    return wal.record_phase(transition_id, phase, **kwargs)


def commit_transition(
    wal: SealTransitionWal, transition_id: str, **kwargs: Any
) -> SealTransitionRecord:
    """Module-level alias for :meth:`SealTransitionWal.commit_transition`."""

    return wal.commit_transition(transition_id, **kwargs)


def abort_transition(
    wal: SealTransitionWal, transition_id: str, **kwargs: Any
) -> SealTransitionRecord:
    """Module-level alias for :meth:`SealTransitionWal.abort_transition`."""

    return wal.abort_transition(transition_id, **kwargs)


__all__ = [
    "CONTRACT_VERSION",
    "CRASH_BOUNDARIES",
    "DEFAULT_DURABILITY_OPERATIONS",
    "EVIDENCE_SUBSET",
    "PHASE_ORDER",
    "WAL_ENTRY_SCHEMA",
    "WAL_STORE_INTERFACE",
    "WAL_STORE_SCHEMA",
    "CommittedTransitionView",
    "DurabilityOperations",
    "SealTransitionWal",
    "SealTransitionWalCrash",
    "SealTransitionWalError",
    "SealTransitionWalIntegrityError",
    "SealTransitionWalStateError",
    "WalDisposition",
    "WalEntry",
    "WalEntryKind",
    "WalOperationResult",
    "WalReason",
    "WalScanResult",
    "abort_transition",
    "begin_transition",
    "commit_transition",
    "committed_transition_views",
    "frame_bytes",
    "is_current_eligible",
    "next_phase",
    "phase_index",
    "project_transition_states",
    "record_phase",
    "recover_wal_bytes",
]

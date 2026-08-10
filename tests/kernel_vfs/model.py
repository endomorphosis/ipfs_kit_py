"""KVFS-800: Independent model, generators, shrinkers, and differential harness.

``KernelVFSReferenceModel@1`` is a pure deterministic oracle for host-shaped
VFS operations. It does **not** import or wrap production
:class:`~ipfs_kit_py.core.vfs.service.CanonicalVFSService` or
:class:`~ipfs_kit_py.kernel_vfs.operations.KernelVFSOperations` as an oracle;
shared contract enums and path normalization helpers are used only for
vocabulary alignment.

Generators emit reproducible sequential and concurrent traces from integer
seeds. Shrinkers reduce failing traces deterministically. Differential
identity records compare state / result / errno / effect across the model,
CanonicalVFSService, KernelVFSOperations, and platform projections.

Legacy compatibility carries an explicit closed disposition table so
admitted and rejected legacy names never silently drift.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final

# Contract vocabulary only — not production service/operations implementations.
from ipfs_kit_py.core.vfs.adapters import LEGACY_VFS_OPERATION_KINDS
from ipfs_kit_py.core.vfs.host_contracts import (
    EXPLICIT_UNSUPPORTED_CALLBACKS,
    REQUIRED_SUPPORTED_CALLBACKS,
    CallbackDisposition,
    HostCallbackKind,
    HostErrno,
    HostPlatform,
    OpenFlag,
    callback_disposition,
    default_unsupported_errno,
    errno_number,
)
from ipfs_kit_py.core.vfs.contracts import (
    VFSErrorCode,
    normalize_vfs_path,
)

# ---------------------------------------------------------------------------
# Schema / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-800"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.0.0"
MODEL_NAMESPACE: Final[str] = "ipfs_kit_py/tests/kernel_vfs/model"
KERNEL_VFS_REFERENCE_MODEL_SCHEMA: Final[str] = (
    f"{MODEL_NAMESPACE}/kernel-vfs-reference-model@{SCHEMA_MAJOR}"
)
KernelVFSReferenceModel_V1: Final[str] = KERNEL_VFS_REFERENCE_MODEL_SCHEMA
DIFFERENTIAL_IDENTITY_SCHEMA: Final[str] = (
    f"{MODEL_NAMESPACE}/differential-identity@{SCHEMA_MAJOR}"
)
LEGACY_DISPOSITION_SCHEMA: Final[str] = (
    f"{MODEL_NAMESPACE}/legacy-differential-disposition@{SCHEMA_MAJOR}"
)

MAX_TRACE_STEPS: Final[int] = 256
MAX_PATH_COMPONENT: Final[int] = 32
MAX_PAYLOAD_BYTES: Final[int] = 4_096
MAX_CONCURRENT_THREADS: Final[int] = 8
MAX_SHRINK_ROUNDS: Final[int] = 64
FIXED_CLOCK_MS: Final[int] = 1_700_000_000_000

# Closed alphabets for reproducible generators.
_PATH_NAMES: Final[tuple[str, ...]] = (
    "a",
    "b",
    "c",
    "docs",
    "tmp",
    "note",
    "file",
    "x",
    "y",
    "z",
)
_PAYLOADS: Final[tuple[bytes, ...]] = (
    b"",
    b"x",
    b"hello",
    b"payload-01",
    b"ABCDEFGH",
    b"\x00\x01\x02\x03",
)
_RANGE_SIZES: Final[tuple[int, ...]] = (0, 1, 2, 4, 8, 16)
_MODES: Final[tuple[int, ...]] = (0o644, 0o755, 0o600, 0o444)
_FLAG_SETS: Final[tuple[tuple[str, ...], ...]] = (
    ("O_RDONLY",),
    ("O_WRONLY",),
    ("O_RDWR",),
    ("O_RDWR", "O_CREAT"),
    ("O_WRONLY", "O_CREAT", "O_EXCL"),
    ("O_RDWR", "O_TRUNC"),
    ("O_WRONLY", "O_APPEND"),
    ("O_RDWR", "O_CREAT", "O_TRUNC"),
)
_WINDOWS_NAME_POOL: Final[tuple[str, ...]] = (
    "ok.txt",
    "ReadMe",
    "CON",
    "nul.log",
    "file.",
    "dir ",
    "a<b",
    "café",
    "COM1",
    "good_name-1",
    "trailing...",
    "star*",
)
_ARC_KEYS: Final[tuple[str, ...]] = tuple(f"k{i}" for i in range(8))
_ARC_SIZES: Final[tuple[int, ...]] = (1, 2, 4, 8, 16, 32)

# Map model/service error codes onto host errno names (aligned with host_service).
VFS_ERROR_TO_ERRNO: Final[Mapping[str, str]] = {
    VFSErrorCode.NOT_FOUND.value: HostErrno.ENOENT.value,
    VFSErrorCode.ALREADY_EXISTS.value: HostErrno.EEXIST.value,
    VFSErrorCode.NOT_DIRECTORY.value: HostErrno.ENOTDIR.value,
    VFSErrorCode.IS_DIRECTORY.value: HostErrno.EISDIR.value,
    VFSErrorCode.NOT_EMPTY.value: HostErrno.ENOTEMPTY.value,
    VFSErrorCode.READ_ONLY.value: HostErrno.EROFS.value,
    VFSErrorCode.PERMISSION_DENIED.value: HostErrno.EACCES.value,
    VFSErrorCode.UNSUPPORTED.value: HostErrno.ENOSYS.value,
    VFSErrorCode.PRECONDITION_FAILED.value: HostErrno.EAGAIN.value,
    VFSErrorCode.STAT_ERROR.value: HostErrno.EIO.value,
    VFSErrorCode.INTERNAL.value: HostErrno.EIO.value,
    # Service projects same-path rename as NO_STATE_CHANGE; host maps unknown → EIO.
    VFSErrorCode.NO_STATE_CHANGE.value: HostErrno.EIO.value,
    # Host façade does not map INVALID_PATH explicitly (defaults to EIO).
    VFSErrorCode.INVALID_PATH.value: HostErrno.EIO.value,
}

# Metadata times are bounded by MAX_SAFE_INTEGER (~2^53-1). Realistic unix-ms
# values overflow true ns scaling; project the same way host_service does.
_MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
_MS_TO_NS: Final[int] = 1_000_000
_MAX_MS_FOR_TRUE_NS: Final[int] = _MAX_SAFE_INTEGER // _MS_TO_NS


def ms_to_metadata_ns(clock_ms: int) -> int:
    """Map model/host clock milliseconds into metadata's bounded ns domain.

    Prefer true ms→ns when the product fits; otherwise use the millisecond
    tick itself so realistic unix-ms clocks never raise EOVERFLOW.
    """

    try:
        ms = int(clock_ms)
    except (TypeError, ValueError):
        return 0
    if ms <= 0:
        return 0
    if ms > _MAX_SAFE_INTEGER:
        return _MAX_SAFE_INTEGER
    if ms <= _MAX_MS_FOR_TRUE_NS:
        return ms * _MS_TO_NS
    return ms


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ModelOpKind(str, Enum):
    """Closed host-shaped operation vocabulary for model traces."""

    MKDIR = "mkdir"
    CREATE = "create"
    WRITE = "write"
    READ = "read"
    TRUNCATE = "truncate"
    GETATTR = "getattr"
    READDIR = "readdir"
    UNLINK = "unlink"
    RENAME = "rename"
    RMDIR = "rmdir"
    OPEN = "open"
    ACCESS = "access"
    UTIMENS = "utimens"
    # Crash/replay control points (model-only intents).
    CRASH_BEFORE_COMMIT = "crash_before_commit"
    REPLAY = "replay"


class EntryKind(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


class LegacyDispositionKind(str, Enum):
    """Explicit differential disposition for a legacy operation name."""

    ADMITTED = "admitted"
    UNSUPPORTED = "unsupported"
    REJECTED = "rejected"


class ShrinkDomain(str, Enum):
    """Property domains that must shrink reproducibly."""

    FLAGS = "flags"
    RANGES = "ranges"
    METADATA = "metadata"
    RENAME_UNLINK = "rename_unlink"
    CRASH_REPLAY = "crash_replay"
    ARC = "arc"
    WINDOWS_NAMES = "windows_names"
    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelEntry:
    """One namespace entry in the pure reference model."""

    kind: EntryKind
    content: bytes = b""
    mode: int = 0o644
    mtime_ms: int = 0
    atime_ms: int = 0

    def public(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "size_bytes": 0 if self.kind is EntryKind.DIRECTORY else len(self.content),
            "mode": self.mode,
            "mtime_ms": self.mtime_ms,
            "atime_ms": self.atime_ms,
        }


@dataclass(frozen=True)
class ModelAction:
    """One generated host-shaped action in a differential trace."""

    kind: ModelOpKind
    path: str = ""
    target_path: str = ""
    data: bytes = b""
    offset: int = 0
    size: int = 0
    mode: int = 0o644
    flags: tuple[str, ...] = ()
    mask: int = 0
    atime_ms: int = 0
    mtime_ms: int = 0
    thread_id: int = 0
    intent_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "path": self.path,
            "target_path": self.target_path,
            "data_hex": self.data.hex(),
            "data_len": len(self.data),
            "offset": self.offset,
            "size": self.size,
            "mode": self.mode,
            "flags": list(self.flags),
            "mask": self.mask,
            "atime_ms": self.atime_ms,
            "mtime_ms": self.mtime_ms,
            "thread_id": self.thread_id,
            "intent_id": self.intent_id,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ModelAction":
        data_hex = str(record.get("data_hex") or "")
        data = bytes.fromhex(data_hex) if data_hex else b""
        flags = tuple(str(f) for f in (record.get("flags") or ()))
        return cls(
            kind=ModelOpKind(str(record["kind"])),
            path=str(record.get("path") or ""),
            target_path=str(record.get("target_path") or ""),
            data=data,
            offset=int(record.get("offset") or 0),
            size=int(record.get("size") or 0),
            mode=int(record.get("mode") or 0o644),
            flags=flags,
            mask=int(record.get("mask") or 0),
            atime_ms=int(record.get("atime_ms") or 0),
            mtime_ms=int(record.get("mtime_ms") or 0),
            thread_id=int(record.get("thread_id") or 0),
            intent_id=str(record.get("intent_id") or ""),
        )


@dataclass(frozen=True)
class ModelStepResult:
    """Outcome of one model step."""

    success: bool
    errno: str = HostErrno.OK.value
    effect: bool = False
    data: bytes = b""
    dir_entries: tuple[str, ...] = ()
    size_bytes: int = 0
    mode: int = 0
    message: str = ""
    pending_intent: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "errno": self.errno,
            "effect": self.effect,
            "data_len": len(self.data),
            "data_hex": self.data.hex(),
            "dir_entries": list(self.dir_entries),
            "size_bytes": self.size_bytes,
            "mode": self.mode,
            "message": self.message,
            "pending_intent": self.pending_intent,
        }


@dataclass(frozen=True)
class DifferentialIdentity:
    """Compact cross-surface identity for one step.

    Compared fields: abstract namespace state, success, errno, observed effect.
    """

    SCHEMA: ClassVar[str] = DIFFERENTIAL_IDENTITY_SCHEMA

    index: int
    op: str
    path: str
    success: bool
    errno: str
    effect: bool
    state: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    surface: str = "model"
    platform: str = HostPlatform.HERMETIC.value
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "index": self.index,
            "op": self.op,
            "path": self.path,
            "success": self.success,
            "errno": self.errno,
            "effect": self.effect,
            "state": {k: dict(v) for k, v in sorted(self.state.items())},
            "surface": self.surface,
            "platform": self.platform,
            "extra": dict(self.extra),
        }

    def core_identity(self) -> dict[str, Any]:
        """Identity fields used for cross-surface equality."""

        return {
            "index": self.index,
            "op": self.op,
            "path": self.path,
            "success": self.success,
            "errno": self.errno,
            "effect": self.effect,
            "state": {k: dict(v) for k, v in sorted(self.state.items())},
        }


@dataclass(frozen=True)
class LegacyDifferentialDisposition:
    """Explicit disposition for one legacy compatibility operation name."""

    SCHEMA: ClassVar[str] = LEGACY_DISPOSITION_SCHEMA

    operation: str
    disposition: LegacyDispositionKind
    canonical_kind: str = ""
    notes: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "operation": self.operation,
            "disposition": self.disposition.value,
            "canonical_kind": self.canonical_kind,
            "notes": self.notes,
        }


# Explicit closed legacy dispositions — admitted names map 1:1 onto the
# canonical vocabulary; everything else is unsupported and must fail closed.
_LEGACY_NOTES: Final[Mapping[str, str]] = {
    "ls": "legacy list projects onto VFSOperationKind.LIST",
    "cat": "legacy read projects onto VFSOperationKind.READ",
    "write": "legacy write projects onto VFSOperationKind.REPLACE",
    "mkdir": "legacy mkdir projects onto VFSOperationKind.MKDIR",
    "rmdir": "legacy rmdir projects onto VFSOperationKind.RMDIR",
    "rm": "legacy rm projects onto VFSOperationKind.DELETE",
    "info": "legacy info projects onto VFSOperationKind.STAT",
    "rename": "legacy rename projects onto VFSOperationKind.RENAME",
    "move": "legacy move projects onto VFSOperationKind.MOVE",
}


def legacy_differential_dispositions() -> tuple[LegacyDifferentialDisposition, ...]:
    """Return the closed explicit legacy differential disposition table."""

    admitted: list[LegacyDifferentialDisposition] = []
    for name, kind in sorted(LEGACY_VFS_OPERATION_KINDS.items()):
        admitted.append(
            LegacyDifferentialDisposition(
                operation=name,
                disposition=LegacyDispositionKind.ADMITTED,
                canonical_kind=kind.value,
                notes=_LEGACY_NOTES.get(name, "admitted legacy vocabulary"),
            )
        )
    # Representative unsupported names that must never become silent successes.
    unsupported_names = (
        "chmod",
        "chown",
        "symlink",
        "link",
        "mknod",
        "getattr",  # host callback name, not legacy manager name
        "execute",
        "unknown_op",
        "delete",  # use "rm" not "delete"
        "stat",  # use "info" not "stat"
        "list",  # use "ls" not "list"
        "read",  # use "cat" not "read"
    )
    rejected = [
        LegacyDifferentialDisposition(
            operation=name,
            disposition=LegacyDispositionKind.UNSUPPORTED,
            canonical_kind="",
            notes="unsupported legacy name; adapter must return unsupported_legacy_operation",
        )
        for name in unsupported_names
    ]
    return tuple(admitted + rejected)


def disposition_for_legacy(operation: str) -> LegacyDifferentialDisposition:
    """Lookup disposition for one legacy name (unknown → unsupported)."""

    for item in legacy_differential_dispositions():
        if item.operation == operation:
            return item
    return LegacyDifferentialDisposition(
        operation=operation,
        disposition=LegacyDispositionKind.UNSUPPORTED,
        notes="unknown legacy name defaults to unsupported",
    )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _norm(path: str) -> str:
    if path in ("", "/"):
        return ""
    return normalize_vfs_path(path).path


def _parent(path: str) -> str:
    if not path or "/" not in path:
        return ""
    return path.rsplit("/", 1)[0]


def _join(parent: str, name: str) -> str:
    if not parent:
        return name
    return f"{parent}/{name}"


def abstract_state_from_entries(
    entries: Mapping[str, ModelEntry | Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Project entries into the cross-surface abstract state view."""

    out: dict[str, dict[str, Any]] = {}
    for path, entry in sorted(entries.items()):
        if isinstance(entry, ModelEntry):
            rec = entry.public()
        else:
            kind = str(entry.get("kind") or "file")
            if kind in ("directory", "dir"):
                kind = EntryKind.DIRECTORY.value
            elif kind in ("file",):
                kind = EntryKind.FILE.value
            size = int(entry.get("size_bytes") or 0)
            if kind == EntryKind.DIRECTORY.value:
                size = 0
            rec = {
                "kind": kind,
                "size_bytes": size,
                "mode": int(entry.get("mode") or 0),
                "mtime_ms": int(entry.get("mtime_ms") or entry.get("mtime_unix_ms") or 0),
                "atime_ms": int(entry.get("atime_ms") or 0),
            }
        # Cross-surface identity uses kind + size only (mode/mtime may differ
        # across planes that do not share a single metadata clock).
        out[path] = {
            "kind": rec["kind"],
            "size_bytes": rec["size_bytes"],
        }
    return out


def abstract_state_from_service_snapshot(
    snapshot: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Normalize a CanonicalVFSService / storage snapshot."""

    return abstract_state_from_entries(snapshot)


# ---------------------------------------------------------------------------
# Independent reference model
# ---------------------------------------------------------------------------


class KernelVFSReferenceModel:
    """Pure deterministic host-shaped VFS state machine.

    Interface alias: ``KernelVFSReferenceModel@1``.

    Implements the production callback semantics needed for differential
    identity without calling production service or operations code.
    """

    SCHEMA: ClassVar[str] = KERNEL_VFS_REFERENCE_MODEL_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(self, *, clock_ms: int = FIXED_CLOCK_MS) -> None:
        self._clock_ms = int(clock_ms)
        self._generation = 0
        self._entries: dict[str, ModelEntry] = {
            "": ModelEntry(
                kind=EntryKind.DIRECTORY,
                mode=0o755,
                mtime_ms=self._clock_ms,
                atime_ms=self._clock_ms,
            )
        }
        # Crash/replay: durable intents not yet committed.
        self._pending: dict[str, ModelAction] = {}
        self._committed_intents: set[str] = set()
        self._handles: dict[int, str] = {}
        self._next_handle = 1
        self._trace: list[dict[str, Any]] = []

    # -- inspection ---------------------------------------------------------

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def pending_intents(self) -> Mapping[str, ModelAction]:
        return dict(self._pending)

    @property
    def committed_intents(self) -> frozenset[str]:
        return frozenset(self._committed_intents)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {path: entry.public() for path, entry in sorted(self._entries.items())}

    def abstract_state(self) -> dict[str, dict[str, Any]]:
        return abstract_state_from_entries(self._entries)

    def get(self, path: str) -> ModelEntry | None:
        return self._entries.get(_norm(path))

    def seed(
        self,
        path: str,
        *,
        kind: EntryKind = EntryKind.FILE,
        content: bytes = b"",
        mode: int = 0o644,
    ) -> ModelEntry:
        path = _norm(path)
        if path:
            self._ensure_parents(path)
        self._generation += 1
        entry = ModelEntry(
            kind=kind,
            content=content if kind is EntryKind.FILE else b"",
            mode=mode if kind is EntryKind.FILE else 0o755,
            mtime_ms=self._clock_ms + self._generation,
            atime_ms=self._clock_ms + self._generation,
        )
        self._entries[path] = entry
        return entry

    # -- execution ----------------------------------------------------------

    def apply(self, action: ModelAction) -> ModelStepResult:
        """Apply one action and append a differential-trace step."""

        result = self._apply_inner(action)
        self._trace.append(
            {
                "action": action.to_record(),
                "result": result.to_record(),
                "state": self.abstract_state(),
            }
        )
        return result

    def run_trace(self, actions: Sequence[ModelAction]) -> list[DifferentialIdentity]:
        if len(actions) > MAX_TRACE_STEPS:
            raise ValueError(f"trace exceeds MAX_TRACE_STEPS ({MAX_TRACE_STEPS})")
        identities: list[DifferentialIdentity] = []
        for index, action in enumerate(actions):
            result = self.apply(action)
            identities.append(
                DifferentialIdentity(
                    index=index,
                    op=action.kind.value,
                    path=action.path or action.target_path,
                    success=result.success,
                    errno=result.errno,
                    effect=result.effect,
                    state=self.abstract_state(),
                    surface="model",
                )
            )
        return identities

    def trace_records(self) -> list[dict[str, Any]]:
        return list(self._trace)

    def clone(self) -> "KernelVFSReferenceModel":
        other = KernelVFSReferenceModel(clock_ms=self._clock_ms)
        other._generation = self._generation
        other._entries = dict(self._entries)
        other._pending = dict(self._pending)
        other._committed_intents = set(self._committed_intents)
        other._handles = dict(self._handles)
        other._next_handle = self._next_handle
        return other

    # -- internals ----------------------------------------------------------

    def _fail(
        self,
        errno: HostErrno | str,
        message: str = "",
        *,
        effect: bool = False,
    ) -> ModelStepResult:
        code = errno.value if isinstance(errno, HostErrno) else str(errno)
        return ModelStepResult(
            success=False, errno=code, effect=effect, message=message
        )

    def _ok(
        self,
        *,
        effect: bool = False,
        data: bytes = b"",
        dir_entries: tuple[str, ...] = (),
        size_bytes: int = 0,
        mode: int = 0,
        pending_intent: str = "",
    ) -> ModelStepResult:
        return ModelStepResult(
            success=True,
            errno=HostErrno.OK.value,
            effect=effect,
            data=data,
            dir_entries=dir_entries,
            size_bytes=size_bytes,
            mode=mode,
            pending_intent=pending_intent,
        )

    def _bump(self) -> int:
        self._generation += 1
        return self._generation

    def _ensure_parents(self, path: str) -> HostErrno | None:
        """Create missing parent directories (seed helper only)."""

        parent = _parent(path)
        segments: list[str] = []
        if parent:
            parts = parent.split("/")
            acc: list[str] = []
            for part in parts:
                acc.append(part)
                segments.append("/".join(acc))
        for seg in segments:
            existing = self._entries.get(seg)
            if existing is None:
                self._entries[seg] = ModelEntry(
                    kind=EntryKind.DIRECTORY,
                    mode=0o755,
                    mtime_ms=self._clock_ms,
                    atime_ms=self._clock_ms,
                )
            elif existing.kind is not EntryKind.DIRECTORY:
                return HostErrno.ENOTDIR
        return None

    def _require_parent(self, path: str) -> HostErrno | None:
        """Fail closed unless the immediate parent directory already exists."""

        parent = _parent(path)
        entry = self._entries.get(parent)
        if entry is None:
            return HostErrno.ENOENT
        if entry.kind is not EntryKind.DIRECTORY:
            return HostErrno.ENOTDIR
        return None

    def _children(self, path: str) -> tuple[str, ...]:
        prefix = "" if path == "" else path + "/"
        names: set[str] = set()
        for key in self._entries:
            if key == path or key == "":
                continue
            if path == "":
                names.add(key.split("/", 1)[0])
            elif key.startswith(prefix):
                rest = key[len(prefix) :]
                if rest:
                    names.add(rest.split("/", 1)[0])
        return tuple(sorted(names))

    def _apply_inner(self, action: ModelAction) -> ModelStepResult:
        kind = action.kind
        if kind is ModelOpKind.MKDIR:
            return self._mkdir(action)
        if kind is ModelOpKind.CREATE:
            return self._create(action)
        if kind is ModelOpKind.WRITE:
            return self._write(action)
        if kind is ModelOpKind.READ:
            return self._read(action)
        if kind is ModelOpKind.TRUNCATE:
            return self._truncate(action)
        if kind is ModelOpKind.GETATTR:
            return self._getattr(action)
        if kind is ModelOpKind.READDIR:
            return self._readdir(action)
        if kind is ModelOpKind.UNLINK:
            return self._unlink(action)
        if kind is ModelOpKind.RENAME:
            return self._rename(action)
        if kind is ModelOpKind.RMDIR:
            return self._rmdir(action)
        if kind is ModelOpKind.OPEN:
            return self._open(action)
        if kind is ModelOpKind.ACCESS:
            return self._access(action)
        if kind is ModelOpKind.UTIMENS:
            return self._utimens(action)
        if kind is ModelOpKind.CRASH_BEFORE_COMMIT:
            return self._crash_before_commit(action)
        if kind is ModelOpKind.REPLAY:
            return self._replay(action)
        return self._fail(HostErrno.ENOSYS, f"unsupported model op {kind}")

    def _mkdir(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        if not path:
            return self._fail(HostErrno.EEXIST, "cannot mkdir root")
        if path in self._entries:
            return self._fail(HostErrno.EEXIST, f"exists: {path}")
        parent_err = self._require_parent(path)
        if parent_err is not None:
            return self._fail(parent_err, "parent missing or not directory")
        self._bump()
        self._entries[path] = ModelEntry(
            kind=EntryKind.DIRECTORY,
            mode=action.mode or 0o755,
            mtime_ms=self._clock_ms + self._generation,
            atime_ms=self._clock_ms + self._generation,
        )
        return self._ok(effect=True)

    def _create(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        if not path:
            return self._fail(HostErrno.EEXIST, "cannot create root")
        if path in self._entries:
            return self._fail(HostErrno.EEXIST, f"exists: {path}")
        parent_err = self._require_parent(path)
        if parent_err is not None:
            return self._fail(parent_err, "parent missing or not directory")
        data = bytes(action.data[:MAX_PAYLOAD_BYTES])
        self._bump()
        self._entries[path] = ModelEntry(
            kind=EntryKind.FILE,
            content=data,
            mode=action.mode or 0o644,
            mtime_ms=self._clock_ms + self._generation,
            atime_ms=self._clock_ms + self._generation,
        )
        return self._ok(effect=True, size_bytes=len(data), mode=action.mode or 0o644)

    def _write(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        entry = self._entries.get(path)
        if entry is None:
            # O_CREAT allows create-on-write when flagged.
            if OpenFlag.O_CREAT.value in action.flags:
                created = self._create(
                    ModelAction(
                        kind=ModelOpKind.CREATE,
                        path=path,
                        data=b"",
                        mode=action.mode,
                    )
                )
                if not created.success:
                    return created
                entry = self._entries[path]
            else:
                return self._fail(HostErrno.ENOENT, f"missing: {path}")
        if entry.kind is not EntryKind.FILE:
            return self._fail(HostErrno.EISDIR, f"is directory: {path}")
        content = bytearray(entry.content)
        data = bytes(action.data[:MAX_PAYLOAD_BYTES])
        offset = max(0, int(action.offset))
        if OpenFlag.O_APPEND.value in action.flags:
            offset = len(content)
        if OpenFlag.O_TRUNC.value in action.flags and offset == 0 and not action.offset:
            content = bytearray()
        end = offset + len(data)
        if end > len(content):
            content.extend(b"\x00" * (end - len(content)))
        content[offset:end] = data
        self._bump()
        self._entries[path] = ModelEntry(
            kind=EntryKind.FILE,
            content=bytes(content),
            mode=entry.mode,
            mtime_ms=self._clock_ms + self._generation,
            atime_ms=entry.atime_ms,
        )
        return self._ok(effect=True, size_bytes=len(content))

    def _read(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        entry = self._entries.get(path)
        if entry is None:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        if entry.kind is not EntryKind.FILE:
            return self._fail(HostErrno.EISDIR, f"is directory: {path}")
        offset = max(0, int(action.offset))
        size = int(action.size) if action.size > 0 else len(entry.content)
        size = max(0, min(size, MAX_PAYLOAD_BYTES))
        data = entry.content[offset : offset + size]
        return self._ok(data=data, size_bytes=len(entry.content))

    def _truncate(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        entry = self._entries.get(path)
        if entry is None:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        if entry.kind is not EntryKind.FILE:
            return self._fail(HostErrno.EISDIR, f"is directory: {path}")
        new_size = max(0, int(action.size))
        content = entry.content
        if new_size < len(content):
            content = content[:new_size]
        elif new_size > len(content):
            content = content + (b"\x00" * (new_size - len(content)))
        self._bump()
        self._entries[path] = ModelEntry(
            kind=EntryKind.FILE,
            content=content,
            mode=entry.mode,
            mtime_ms=self._clock_ms + self._generation,
            atime_ms=entry.atime_ms,
        )
        return self._ok(effect=True, size_bytes=new_size)

    def _getattr(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        entry = self._entries.get(path)
        if entry is None:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        size = 0 if entry.kind is EntryKind.DIRECTORY else len(entry.content)
        return self._ok(size_bytes=size, mode=entry.mode)

    def _readdir(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        entry = self._entries.get(path)
        if entry is None:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        if entry.kind is not EntryKind.DIRECTORY:
            return self._fail(HostErrno.ENOTDIR, f"not a directory: {path}")
        return self._ok(dir_entries=self._children(path))

    def _unlink(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        entry = self._entries.get(path)
        if entry is None:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        if entry.kind is EntryKind.DIRECTORY:
            return self._fail(HostErrno.EISDIR, f"is directory: {path}")
        del self._entries[path]
        self._bump()
        return self._ok(effect=True)

    def _rmdir(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        if not path:
            return self._fail(HostErrno.EACCES, "cannot rmdir root")
        entry = self._entries.get(path)
        if entry is None:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        if entry.kind is not EntryKind.DIRECTORY:
            return self._fail(HostErrno.ENOTDIR, f"not a directory: {path}")
        if self._children(path):
            return self._fail(HostErrno.ENOTEMPTY, f"not empty: {path}")
        del self._entries[path]
        self._bump()
        return self._ok(effect=True)

    def _rename(self, action: ModelAction) -> ModelStepResult:
        source = _norm(action.path)
        target = _norm(action.target_path)
        if not source or not target:
            # Service: INVALID_PATH → host/model projection EIO.
            return self._fail(HostErrno.EIO, "rename requires source and target")
        if source not in self._entries:
            return self._fail(HostErrno.ENOENT, f"missing: {source}")
        # Match CanonicalVFSService: identical source/target is not a no-op
        # success — it projects as a typed failure (NO_STATE_CHANGE → EIO).
        if target == source:
            return self._fail(HostErrno.EIO, "rename source and target are identical")
        parent_err = self._require_parent(target)
        if parent_err is not None:
            return self._fail(parent_err, "target parent missing or not directory")
        # Match service: any existing target is ALREADY_EXISTS (no replace).
        if target in self._entries:
            return self._fail(HostErrno.EEXIST, f"target already exists: {target}")
        # Refuse to move a directory into its own descendant (INVALID_PATH → EIO).
        src_entry = self._entries[source]
        if src_entry.kind is EntryKind.DIRECTORY and target.startswith(source + "/"):
            return self._fail(HostErrno.EIO, "cannot move directory into its descendant")
        # Move source and descendants.
        moves: list[tuple[str, str, ModelEntry]] = []
        for key, entry in list(self._entries.items()):
            if key == source or key.startswith(source + "/"):
                suffix = key[len(source) :]
                moves.append((key, target + suffix, entry))
        for old, _new, _entry in moves:
            del self._entries[old]
        for _old, new, entry in moves:
            self._entries[new] = entry
        self._bump()
        return self._ok(effect=True)

    def _open(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        flags = set(action.flags)
        entry = self._entries.get(path)
        if entry is None:
            if OpenFlag.O_CREAT.value in flags:
                created = self._create(
                    ModelAction(
                        kind=ModelOpKind.CREATE,
                        path=path,
                        data=b"",
                        mode=action.mode,
                    )
                )
                if not created.success:
                    return created
                entry = self._entries[path]
            else:
                return self._fail(HostErrno.ENOENT, f"missing: {path}")
        elif OpenFlag.O_CREAT.value in flags and OpenFlag.O_EXCL.value in flags:
            return self._fail(HostErrno.EEXIST, f"exists: {path}")
        if entry.kind is EntryKind.DIRECTORY and OpenFlag.O_DIRECTORY.value not in flags:
            # Opening a directory as a regular file fails closed.
            if OpenFlag.O_RDONLY.value in flags or not flags:
                # Allow pure directory open only with O_DIRECTORY; otherwise EISDIR.
                if OpenFlag.O_DIRECTORY.value not in flags and (
                    OpenFlag.O_WRONLY.value in flags
                    or OpenFlag.O_RDWR.value in flags
                    or OpenFlag.O_TRUNC.value in flags
                    or OpenFlag.O_APPEND.value in flags
                    or OpenFlag.O_CREAT.value in flags
                ):
                    return self._fail(HostErrno.EISDIR, f"is directory: {path}")
                if (
                    OpenFlag.O_WRONLY.value not in flags
                    and OpenFlag.O_RDWR.value not in flags
                    and OpenFlag.O_TRUNC.value not in flags
                ):
                    # RDONLY without O_DIRECTORY still projects EISDIR (host tests).
                    return self._fail(HostErrno.EISDIR, f"is directory: {path}")
        if entry.kind is EntryKind.FILE and OpenFlag.O_TRUNC.value in flags:
            # Truncate is applied, but host open acknowledgements never claim
            # observed_effect (create/trunc side effects are internal).
            self._entries[path] = ModelEntry(
                kind=EntryKind.FILE,
                content=b"",
                mode=entry.mode,
                mtime_ms=self._clock_ms + self._bump(),
                atime_ms=entry.atime_ms,
            )
        handle = self._next_handle
        self._next_handle += 1
        self._handles[handle] = path
        return self._ok(effect=False)

    def _access(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        if path not in self._entries:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        return self._ok()

    def _utimens(self, action: ModelAction) -> ModelStepResult:
        path = _norm(action.path)
        entry = self._entries.get(path)
        if entry is None:
            return self._fail(HostErrno.ENOENT, f"missing: {path}")
        atime = action.atime_ms or (self._clock_ms + self._generation)
        mtime = action.mtime_ms or (self._clock_ms + self._generation)
        self._entries[path] = ModelEntry(
            kind=entry.kind,
            content=entry.content,
            mode=entry.mode,
            mtime_ms=mtime,
            atime_ms=atime,
        )
        self._bump()
        return self._ok(effect=True, mode=entry.mode)

    def _crash_before_commit(self, action: ModelAction) -> ModelStepResult:
        """Record a durable intent without applying the effect (crash point)."""

        intent_id = action.intent_id or f"intent:{self._generation + 1}:{action.path}"
        if intent_id in self._committed_intents:
            return self._ok(effect=False, pending_intent=intent_id)
        # ``flags[0]`` carries the staged mutation kind when present.
        staged_kind_name = action.flags[0] if action.flags else ModelOpKind.CREATE.value
        try:
            staged_kind = ModelOpKind(staged_kind_name)
        except ValueError:
            staged_kind = ModelOpKind.CREATE
        if staged_kind in (ModelOpKind.CRASH_BEFORE_COMMIT, ModelOpKind.REPLAY):
            staged_kind = ModelOpKind.CREATE
        staged = ModelAction(
            kind=staged_kind,
            path=action.path,
            target_path=action.target_path,
            data=action.data,
            offset=action.offset,
            size=action.size,
            mode=action.mode,
            intent_id=intent_id,
        )
        self._pending[intent_id] = staged
        return self._ok(effect=False, pending_intent=intent_id)

    def _replay(self, action: ModelAction) -> ModelStepResult:
        """Replay pending intents exactly once (idempotent recovery)."""

        intent_id = action.intent_id
        if intent_id:
            pending = self._pending.get(intent_id)
            if pending is None:
                if intent_id in self._committed_intents:
                    return self._ok(effect=False, pending_intent=intent_id)
                return self._fail(HostErrno.ENOENT, f"no intent: {intent_id}")
            result = self._apply_inner(pending)
            if result.success:
                del self._pending[intent_id]
                self._committed_intents.add(intent_id)
            return ModelStepResult(
                success=result.success,
                errno=result.errno,
                effect=result.effect,
                data=result.data,
                dir_entries=result.dir_entries,
                size_bytes=result.size_bytes,
                mode=result.mode,
                message=result.message,
                pending_intent=intent_id,
            )
        # Replay all pending in stable order.
        any_effect = False
        for iid in sorted(self._pending):
            staged = self._pending[iid]
            result = self._apply_inner(staged)
            if result.success:
                any_effect = any_effect or result.effect
                self._committed_intents.add(iid)
        self._pending.clear()
        return self._ok(effect=any_effect)


# ---------------------------------------------------------------------------
# Generators (seeded, reproducible)
# ---------------------------------------------------------------------------


def _rng(seed: int) -> random.Random:
    return random.Random(int(seed) & 0xFFFFFFFF)


def _pick_path(rng: random.Random, *, depth: int = 2, prefix: str = "") -> str:
    parts = []
    if prefix:
        parts.append(prefix.rstrip("/"))
    n = 1 + rng.randrange(max(1, depth))
    for _ in range(n):
        parts.append(_PATH_NAMES[rng.randrange(len(_PATH_NAMES))])
    # Dedup accidental empty.
    path = "/".join(p for p in parts if p)
    return path[:MAX_PATH_COMPONENT * depth]


def generate_sequential_trace(
    seed: int,
    *,
    max_ops: int = 24,
    domain: ShrinkDomain = ShrinkDomain.SEQUENTIAL,
) -> list[ModelAction]:
    """Emit a reproducible sequential host-op trace from an integer seed."""

    if max_ops < 1 or max_ops > MAX_TRACE_STEPS:
        raise ValueError(f"max_ops out of bounds: {max_ops}")
    rng = _rng(seed)
    n = 1 + rng.randrange(max_ops)
    actions: list[ModelAction] = []

    # Always start with a stable scaffold so later ops have parents.
    actions.append(ModelAction(kind=ModelOpKind.MKDIR, path="docs", mode=0o755))
    actions.append(ModelAction(kind=ModelOpKind.MKDIR, path="tmp", mode=0o755))

    for i in range(n):
        roll = rng.randrange(100)
        if domain is ShrinkDomain.FLAGS:
            path = _join("docs", f"f{rng.randrange(4)}")
            flags = _FLAG_SETS[rng.randrange(len(_FLAG_SETS))]
            actions.append(
                ModelAction(
                    kind=ModelOpKind.OPEN,
                    path=path,
                    flags=flags,
                    mode=_MODES[rng.randrange(len(_MODES))],
                    data=_PAYLOADS[rng.randrange(len(_PAYLOADS))],
                )
            )
            if OpenFlag.O_CREAT.value in flags:
                actions.append(
                    ModelAction(
                        kind=ModelOpKind.WRITE,
                        path=path,
                        data=_PAYLOADS[rng.randrange(len(_PAYLOADS))],
                        offset=rng.randrange(8),
                        flags=flags,
                    )
                )
        elif domain is ShrinkDomain.RANGES:
            path = _join("docs", f"r{rng.randrange(3)}")
            payload = _PAYLOADS[rng.randrange(len(_PAYLOADS))]
            actions.append(ModelAction(kind=ModelOpKind.CREATE, path=path, data=payload))
            off = rng.randrange(0, max(1, len(payload)))
            size = _RANGE_SIZES[rng.randrange(len(_RANGE_SIZES))]
            actions.append(
                ModelAction(kind=ModelOpKind.READ, path=path, offset=off, size=size)
            )
            actions.append(
                ModelAction(
                    kind=ModelOpKind.WRITE,
                    path=path,
                    data=b"Z" * max(1, size or 1),
                    offset=off,
                )
            )
            actions.append(
                ModelAction(
                    kind=ModelOpKind.TRUNCATE,
                    path=path,
                    size=_RANGE_SIZES[rng.randrange(len(_RANGE_SIZES))],
                )
            )
        elif domain is ShrinkDomain.METADATA:
            path = _join("docs", f"m{rng.randrange(3)}")
            actions.append(
                ModelAction(
                    kind=ModelOpKind.CREATE,
                    path=path,
                    data=b"meta",
                    mode=_MODES[rng.randrange(len(_MODES))],
                )
            )
            actions.append(ModelAction(kind=ModelOpKind.GETATTR, path=path))
            actions.append(
                ModelAction(
                    kind=ModelOpKind.UTIMENS,
                    path=path,
                    atime_ms=FIXED_CLOCK_MS + rng.randrange(1000),
                    mtime_ms=FIXED_CLOCK_MS + rng.randrange(1000),
                )
            )
            actions.append(ModelAction(kind=ModelOpKind.ACCESS, path=path, mask=0))
            actions.append(ModelAction(kind=ModelOpKind.READDIR, path="docs"))
        elif domain is ShrinkDomain.RENAME_UNLINK:
            src = _join("docs", f"s{rng.randrange(3)}")
            dst = _join("tmp", f"d{rng.randrange(3)}")
            actions.append(
                ModelAction(
                    kind=ModelOpKind.CREATE,
                    path=src,
                    data=_PAYLOADS[rng.randrange(len(_PAYLOADS))],
                )
            )
            if roll < 50:
                actions.append(
                    ModelAction(kind=ModelOpKind.RENAME, path=src, target_path=dst)
                )
                actions.append(ModelAction(kind=ModelOpKind.UNLINK, path=dst))
            else:
                actions.append(ModelAction(kind=ModelOpKind.UNLINK, path=src))
        elif domain is ShrinkDomain.CRASH_REPLAY:
            path = _join("docs", f"c{rng.randrange(3)}")
            intent = f"intent:{seed}:{i}"
            actions.append(
                ModelAction(
                    kind=ModelOpKind.CRASH_BEFORE_COMMIT,
                    path=path,
                    data=_PAYLOADS[rng.randrange(len(_PAYLOADS))],
                    flags=(ModelOpKind.CREATE.value,),
                    intent_id=intent,
                )
            )
            if roll < 70:
                actions.append(ModelAction(kind=ModelOpKind.REPLAY, intent_id=intent))
            else:
                actions.append(ModelAction(kind=ModelOpKind.REPLAY))
        else:
            # Mixed sequential domain. Prefer paths under scaffolded parents.
            if roll < 20:
                actions.append(
                    ModelAction(
                        kind=ModelOpKind.MKDIR,
                        path=_join(
                            "docs" if rng.random() < 0.5 else "tmp",
                            _PATH_NAMES[rng.randrange(len(_PATH_NAMES))],
                        ),
                        mode=0o755,
                    )
                )
            elif roll < 45:
                actions.append(
                    ModelAction(
                        kind=ModelOpKind.CREATE,
                        path=_join("docs", f"n{rng.randrange(6)}"),
                        data=_PAYLOADS[rng.randrange(len(_PAYLOADS))],
                        mode=_MODES[rng.randrange(len(_MODES))],
                    )
                )
            elif roll < 60:
                path = _join("docs", f"n{rng.randrange(6)}")
                actions.append(
                    ModelAction(
                        kind=ModelOpKind.WRITE,
                        path=path,
                        data=_PAYLOADS[rng.randrange(len(_PAYLOADS))],
                        offset=rng.randrange(4),
                    )
                )
            elif roll < 72:
                path = _join("docs", f"n{rng.randrange(6)}")
                actions.append(
                    ModelAction(
                        kind=ModelOpKind.READ,
                        path=path,
                        offset=rng.randrange(4),
                        size=_RANGE_SIZES[rng.randrange(len(_RANGE_SIZES))],
                    )
                )
            elif roll < 80:
                actions.append(
                    ModelAction(kind=ModelOpKind.GETATTR, path=_join("docs", f"n{rng.randrange(6)}"))
                )
            elif roll < 88:
                src = _join("docs", f"n{rng.randrange(6)}")
                dst = _join("tmp", f"t{rng.randrange(4)}")
                actions.append(
                    ModelAction(kind=ModelOpKind.RENAME, path=src, target_path=dst)
                )
            elif roll < 94:
                actions.append(
                    ModelAction(kind=ModelOpKind.UNLINK, path=_join("docs", f"n{rng.randrange(6)}"))
                )
            else:
                actions.append(ModelAction(kind=ModelOpKind.READDIR, path="docs"))

    # Bound total length.
    return actions[:MAX_TRACE_STEPS]


def generate_concurrent_trace(
    seed: int,
    *,
    threads: int = 3,
    ops_per_thread: int = 6,
) -> list[ModelAction]:
    """Emit a deterministic concurrent interleaving across independent prefixes.

    Each thread mutates under ``t{N}/`` so linearizability reduces to
    per-prefix sequential composition for final-state identity.
    """

    threads = max(1, min(int(threads), MAX_CONCURRENT_THREADS))
    ops_per_thread = max(1, min(int(ops_per_thread), MAX_TRACE_STEPS // threads))
    rng = _rng(seed ^ 0xC0FFEE)
    per_thread: list[list[ModelAction]] = []
    for t in range(threads):
        prefix = f"t{t}"
        local: list[ModelAction] = [
            ModelAction(kind=ModelOpKind.MKDIR, path=prefix, mode=0o755, thread_id=t)
        ]
        for i in range(ops_per_thread):
            path = _join(prefix, f"f{i % 3}")
            roll = rng.randrange(100)
            if roll < 35:
                local.append(
                    ModelAction(
                        kind=ModelOpKind.CREATE,
                        path=path,
                        data=_PAYLOADS[rng.randrange(len(_PAYLOADS))],
                        thread_id=t,
                    )
                )
            elif roll < 55:
                local.append(
                    ModelAction(
                        kind=ModelOpKind.WRITE,
                        path=path,
                        data=b"W",
                        offset=rng.randrange(3),
                        thread_id=t,
                    )
                )
            elif roll < 70:
                local.append(
                    ModelAction(
                        kind=ModelOpKind.READ,
                        path=path,
                        offset=0,
                        size=8,
                        thread_id=t,
                    )
                )
            elif roll < 85:
                local.append(
                    ModelAction(
                        kind=ModelOpKind.RENAME,
                        path=path,
                        target_path=_join(prefix, f"g{i % 3}"),
                        thread_id=t,
                    )
                )
            else:
                local.append(
                    ModelAction(kind=ModelOpKind.UNLINK, path=path, thread_id=t)
                )
        per_thread.append(local)

    # Deterministic interleave: round-robin with occasional rng skip.
    indices = [0] * threads
    actions: list[ModelAction] = []
    while any(indices[t] < len(per_thread[t]) for t in range(threads)):
        order = list(range(threads))
        rng.shuffle(order)
        progress = False
        for t in order:
            if indices[t] < len(per_thread[t]):
                actions.append(per_thread[t][indices[t]])
                indices[t] += 1
                progress = True
                if rng.random() < 0.35:
                    break
        if not progress:
            break
    return actions[:MAX_TRACE_STEPS]


def generate_windows_name_cases(seed: int, *, count: int = 12) -> list[str]:
    """Reproducible Windows name pool sample for shrinkable validation."""

    rng = _rng(seed ^ 0xA11)
    n = max(1, min(int(count), len(_WINDOWS_NAME_POOL)))
    # Shuffle a copy deterministically then take prefix.
    pool = list(_WINDOWS_NAME_POOL)
    rng.shuffle(pool)
    return pool[:n]


def generate_arc_ops(
    seed: int,
    *,
    max_ops: int = 12,
    capacity_bytes: int = 128,
) -> list[dict[str, Any]]:
    """Reproducible minimal ARC op records (independent of production ARC)."""

    rng = _rng(seed ^ 0xA12)
    del capacity_bytes  # documented for callers; generator stays key/size bounded
    n = 1 + rng.randrange(max(1, max_ops))
    ops: list[dict[str, Any]] = []
    for _ in range(n):
        roll = rng.randrange(100)
        key = _ARC_KEYS[rng.randrange(len(_ARC_KEYS))]
        size = _ARC_SIZES[rng.randrange(len(_ARC_SIZES))]
        if roll < 50:
            ops.append(
                {
                    "kind": "put",
                    "key": key,
                    "value_hex": bytes([rng.randrange(256) for _ in range(size)]).hex(),
                }
            )
        elif roll < 80:
            ops.append({"kind": "get", "key": key})
        else:
            ops.append({"kind": "delete", "key": key})
    return ops


# ---------------------------------------------------------------------------
# Shrinkers (deterministic delta-debugging)
# ---------------------------------------------------------------------------


def shrink_trace(
    actions: Sequence[ModelAction],
    is_interesting: Callable[[Sequence[ModelAction]], bool],
    *,
    max_rounds: int = MAX_SHRINK_ROUNDS,
) -> list[ModelAction]:
    """Shrink a trace while preserving ``is_interesting``; deterministic.

    Uses linear deletion passes (remove one action at a time from left to
    right) so the same input always yields the same minimal subsequence.
    """

    current = list(actions)
    if not is_interesting(current):
        return current
    rounds = 0
    changed = True
    while changed and rounds < max_rounds and len(current) > 1:
        changed = False
        rounds += 1
        i = 0
        while i < len(current) and len(current) > 1:
            candidate = current[:i] + current[i + 1 :]
            if is_interesting(candidate):
                current = candidate
                changed = True
                # Do not advance i: next element shifted into position i.
            else:
                i += 1
    return current


def shrink_windows_names(
    names: Sequence[str],
    is_interesting: Callable[[Sequence[str]], bool],
) -> list[str]:
    """Shrink a Windows-name list while preserving interest; deterministic."""

    current = list(names)
    if not is_interesting(current):
        return current
    changed = True
    rounds = 0
    while changed and rounds < MAX_SHRINK_ROUNDS and len(current) > 1:
        changed = False
        rounds += 1
        i = 0
        while i < len(current) and len(current) > 1:
            candidate = current[:i] + current[i + 1 :]
            if is_interesting(candidate):
                current = candidate
                changed = True
            else:
                i += 1
    return current


def shrink_arc_ops(
    ops: Sequence[Mapping[str, Any]],
    is_interesting: Callable[[Sequence[Mapping[str, Any]]], bool],
) -> list[dict[str, Any]]:
    """Shrink an ARC op list while preserving interest; deterministic."""

    current = [dict(op) for op in ops]
    if not is_interesting(current):
        return current
    changed = True
    rounds = 0
    while changed and rounds < MAX_SHRINK_ROUNDS and len(current) > 1:
        changed = False
        rounds += 1
        i = 0
        while i < len(current) and len(current) > 1:
            candidate = current[:i] + current[i + 1 :]
            if is_interesting(candidate):
                current = candidate
                changed = True
            else:
                i += 1
    return current


def shrink_domains() -> tuple[str, ...]:
    return tuple(d.value for d in ShrinkDomain)


# ---------------------------------------------------------------------------
# Identity comparison
# ---------------------------------------------------------------------------


def identities_match(
    left: Sequence[DifferentialIdentity | Mapping[str, Any]],
    right: Sequence[DifferentialIdentity | Mapping[str, Any]],
    *,
    compare_state: bool = True,
) -> bool:
    """Compare core identity fields across two differential traces."""

    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        ra = a.core_identity() if isinstance(a, DifferentialIdentity) else dict(a)
        rb = b.core_identity() if isinstance(b, DifferentialIdentity) else dict(b)
        keys = ("index", "op", "path", "success", "errno", "effect")
        for key in keys:
            if ra.get(key) != rb.get(key):
                return False
        if compare_state and ra.get("state") != rb.get("state"):
            return False
    return True


def final_state_match(
    left: Sequence[DifferentialIdentity | Mapping[str, Any]],
    right: Sequence[DifferentialIdentity | Mapping[str, Any]],
) -> bool:
    if not left or not right:
        return left == right
    la = left[-1]
    ra = right[-1]
    sa = (
        la.core_identity()["state"]
        if isinstance(la, DifferentialIdentity)
        else dict(la).get("state")
    )
    sb = (
        ra.core_identity()["state"]
        if isinstance(ra, DifferentialIdentity)
        else dict(ra).get("state")
    )
    return sa == sb


def result_errno_effect_match(
    left: Sequence[DifferentialIdentity | Mapping[str, Any]],
    right: Sequence[DifferentialIdentity | Mapping[str, Any]],
) -> bool:
    """Compare success/errno/effect only (ignore abstract state)."""

    return identities_match(left, right, compare_state=False)


def canonical_identity_step(step: DifferentialIdentity | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(step, DifferentialIdentity):
        return step.core_identity()
    return {
        "index": step.get("index"),
        "op": step.get("op"),
        "path": step.get("path"),
        "success": step.get("success"),
        "errno": step.get("errno"),
        "effect": step.get("effect"),
        "state": step.get("state"),
    }


def content_id_for(record: Mapping[str, Any]) -> str:
    """Stable content identity for golden/shrink witnesses."""

    import json

    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def map_service_error_to_errno(error_code: str | None) -> str:
    if not error_code:
        return HostErrno.EIO.value
    return VFS_ERROR_TO_ERRNO.get(str(error_code), HostErrno.EIO.value)


def platform_errno_projection(
    errno_name: str,
    platform: HostPlatform | str,
) -> int:
    """Project a symbolic errno onto a platform integer."""

    plat = platform if isinstance(platform, HostPlatform) else HostPlatform(platform)
    try:
        errno = HostErrno(errno_name)
    except ValueError:
        errno = HostErrno.EIO
    return errno_number(errno, plat)


def callback_dispositions_table() -> dict[str, str]:
    """Closed host-callback disposition map for differential checks."""

    out: dict[str, str] = {}
    for kind in REQUIRED_SUPPORTED_CALLBACKS:
        out[kind.value] = CallbackDisposition.REQUIRED_SUPPORTED.value
    for kind in EXPLICIT_UNSUPPORTED_CALLBACKS:
        out[kind.value] = CallbackDisposition.EXPLICIT_UNSUPPORTED.value
        # Touch default errno so the table is executable.
        _ = default_unsupported_errno(kind)
    return out


# ---------------------------------------------------------------------------
# Minimal ARC reference (for shrink domain; independent of production ARC)
# ---------------------------------------------------------------------------


class MinimalARCModel:
    """Tiny byte-budget cache for ARC shrink/property domain tests.

    Not a full ARC implementation — only admits/gets/deletes under a capacity
    so shrinkable traces remain meaningful without encoding production ARC.
    """

    def __init__(self, capacity_bytes: int = 128) -> None:
        self.capacity_bytes = int(capacity_bytes)
        self._store: dict[str, bytes] = {}
        self._order: list[str] = []

    @property
    def current_size(self) -> int:
        return sum(len(v) for v in self._store.values())

    def apply(self, op: Mapping[str, Any]) -> dict[str, Any]:
        kind = str(op.get("kind") or "")
        key = str(op.get("key") or "")
        if kind == "put":
            value = bytes.fromhex(str(op.get("value_hex") or ""))
            if len(value) > self.capacity_bytes:
                return {"success": False, "admitted": False, "key": key}
            while self.current_size + len(value) > self.capacity_bytes and self._order:
                old = self._order.pop(0)
                self._store.pop(old, None)
            if key in self._store:
                self._order.remove(key)
            self._store[key] = value
            self._order.append(key)
            return {"success": True, "admitted": True, "key": key, "size": len(value)}
        if kind == "get":
            found = key in self._store
            if found:
                self._order.remove(key)
                self._order.append(key)
            return {"success": found, "found": found, "key": key}
        if kind == "delete":
            found = key in self._store
            if found:
                self._store.pop(key, None)
                self._order.remove(key)
            return {"success": found, "found": found, "key": key}
        return {"success": False, "error": "unknown"}

    def run(self, ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [self.apply(op) for op in ops]

    def snapshot(self) -> dict[str, Any]:
        return {
            "keys": list(self._order),
            "sizes": {k: len(self._store[k]) for k in self._order},
            "current_size": self.current_size,
            "capacity_bytes": self.capacity_bytes,
        }


# ---------------------------------------------------------------------------
# Windows name model (pure; no WinFsp)
# ---------------------------------------------------------------------------

_WINDOWS_RESERVED: Final[frozenset[str]] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
_WINDOWS_INVALID_CHARS: Final[frozenset[str]] = frozenset('<>:"/\\|?*')


def model_validate_windows_name(name: str) -> dict[str, Any]:
    """Independent Windows name gate for differential name shrink tests."""

    if not name:
        return {"ok": False, "reason": "empty", "errno": HostErrno.EINVAL.value}
    base = name.split(".", 1)[0]
    if base.upper() in _WINDOWS_RESERVED or name.upper().split(".")[0] in _WINDOWS_RESERVED:
        # Also catch CON.txt style.
        stem = name.split(":", 1)[0]
        stem_base = stem.split(".", 1)[0].upper()
        if stem_base in _WINDOWS_RESERVED:
            return {
                "ok": False,
                "reason": "reserved_device",
                "errno": HostErrno.EINVAL.value,
            }
    if name.endswith(".") or name.endswith(" "):
        return {
            "ok": False,
            "reason": "trailing_dot_space",
            "errno": HostErrno.EINVAL.value,
        }
    if any(ch in _WINDOWS_INVALID_CHARS for ch in name):
        return {"ok": False, "reason": "invalid_char", "errno": HostErrno.EINVAL.value}
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in name):
        return {"ok": False, "reason": "surrogate", "errno": HostErrno.EINVAL.value}
    return {
        "ok": True,
        "reason": "",
        "errno": HostErrno.OK.value,
        "display_spelling": name,
        "lookup_identity": name.casefold(),
    }


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "KERNEL_VFS_REFERENCE_MODEL_SCHEMA",
    "KernelVFSReferenceModel_V1",
    "DIFFERENTIAL_IDENTITY_SCHEMA",
    "LEGACY_DISPOSITION_SCHEMA",
    "MAX_TRACE_STEPS",
    "FIXED_CLOCK_MS",
    "ModelOpKind",
    "EntryKind",
    "LegacyDispositionKind",
    "ShrinkDomain",
    "ModelEntry",
    "ModelAction",
    "ModelStepResult",
    "DifferentialIdentity",
    "LegacyDifferentialDisposition",
    "KernelVFSReferenceModel",
    "MinimalARCModel",
    "legacy_differential_dispositions",
    "disposition_for_legacy",
    "abstract_state_from_entries",
    "abstract_state_from_service_snapshot",
    "generate_sequential_trace",
    "generate_concurrent_trace",
    "generate_windows_name_cases",
    "generate_arc_ops",
    "shrink_trace",
    "shrink_windows_names",
    "shrink_arc_ops",
    "shrink_domains",
    "identities_match",
    "final_state_match",
    "result_errno_effect_match",
    "canonical_identity_step",
    "content_id_for",
    "map_service_error_to_errno",
    "platform_errno_projection",
    "callback_dispositions_table",
    "model_validate_windows_name",
    "VFS_ERROR_TO_ERRNO",
]

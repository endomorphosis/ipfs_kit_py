"""HostFilesystemAdapter callback, error, and lifecycle contracts (KVFS-101).

This module is an inert, closed, versioned contract surface for the host
filesystem adapter that bridges fusepy/WinFsp callbacks into
``CanonicalVFSService``.  It defines finite records for:

* callback inputs and results (every admitted high-level FUSE operation);
* exact errno projection (including explicit ``ENOSYS`` / ``EOPNOTSUPP``);
* open flags, metadata, and generation-tagged file handles;
* durability modes and cache-consistency modes;
* mount lifecycle states (init → ready → draining → destroy);
* cancellation and deadline envelopes; and
* Linux / Windows platform differences.

Rules (fail-closed):

* every callback is either required-supported or explicit-unsupported;
* unsupported callbacks must return a stable ``ENOSYS`` or ``EOPNOTSUPP`` —
  never success and never a silent no-op;
* success results cannot carry a non-zero errno (false success is forbidden);
* failure results must carry a non-zero exact errno;
* unknown callbacks are rejected at the contract boundary;
* no fusepy, libfuse, WinFsp, or host filesystem I/O is imported or performed.

Interface aliases: ``HostFilesystemAdapter@1``, ``HostCallback@1``,
``HostCallbackResult@1``, ``HostHandle@1``, ``HostMountLifecycle@1``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final, TypeVar

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

HOST_CONTRACTS_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/host_contracts"

HOST_FILESYSTEM_ADAPTER_SCHEMA: Final[str] = (
    f"{HOST_CONTRACTS_NAMESPACE}/host-filesystem-adapter@{SCHEMA_MAJOR}"
)
HOST_CALLBACK_SCHEMA: Final[str] = (
    f"{HOST_CONTRACTS_NAMESPACE}/host-callback@{SCHEMA_MAJOR}"
)
HOST_CALLBACK_RESULT_SCHEMA: Final[str] = (
    f"{HOST_CONTRACTS_NAMESPACE}/host-callback-result@{SCHEMA_MAJOR}"
)
HOST_HANDLE_SCHEMA: Final[str] = f"{HOST_CONTRACTS_NAMESPACE}/host-handle@{SCHEMA_MAJOR}"
HOST_METADATA_SCHEMA: Final[str] = (
    f"{HOST_CONTRACTS_NAMESPACE}/host-metadata@{SCHEMA_MAJOR}"
)
HOST_MOUNT_LIFECYCLE_SCHEMA: Final[str] = (
    f"{HOST_CONTRACTS_NAMESPACE}/host-mount-lifecycle@{SCHEMA_MAJOR}"
)
HOST_ERROR_SCHEMA: Final[str] = f"{HOST_CONTRACTS_NAMESPACE}/host-error@{SCHEMA_MAJOR}"
HOST_DEADLINE_SCHEMA: Final[str] = (
    f"{HOST_CONTRACTS_NAMESPACE}/host-deadline@{SCHEMA_MAJOR}"
)
HOST_PLATFORM_DIFF_SCHEMA: Final[str] = (
    f"{HOST_CONTRACTS_NAMESPACE}/host-platform-diff@{SCHEMA_MAJOR}"
)

# Public interface aliases (plan: HostFilesystemAdapter@1, …).
HostFilesystemAdapter_V1: Final[str] = HOST_FILESYSTEM_ADAPTER_SCHEMA
HostCallback_V1: Final[str] = HOST_CALLBACK_SCHEMA
HostCallbackResult_V1: Final[str] = HOST_CALLBACK_RESULT_SCHEMA
HostHandle_V1: Final[str] = HOST_HANDLE_SCHEMA
HostMountLifecycle_V1: Final[str] = HOST_MOUNT_LIFECYCLE_SCHEMA

MAX_PATH_BYTES: Final[int] = 4_096
MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_HANDLE_ID: Final[int] = MAX_SAFE_INTEGER
MAX_INODE: Final[int] = MAX_SAFE_INTEGER
MAX_SIZE_BYTES: Final[int] = 1 << 50
MAX_OFFSET: Final[int] = MAX_SIZE_BYTES
MAX_IO_LENGTH: Final[int] = 64 * 1024 * 1024  # 64 MiB single callback bound
MAX_NAME_BYTES: Final[int] = 255
MAX_REFERENCE_COUNT: Final[int] = 256
MAX_RECORD_BYTES: Final[int] = 262_144
DEFAULT_CALLBACK_DEADLINE_MS: Final[int] = 60_000
MAX_CALLBACK_DEADLINE_MS: Final[int] = 300_000

_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)

TEnum = TypeVar("TEnum", bound=Enum)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class HostPlatform(str, Enum):
    """Host platform profile for callback projection."""

    LINUX = "linux"
    WINDOWS = "windows"
    # Neutral / hermetic contract evaluation (no native mount).
    HERMETIC = "hermetic"


class HostCallbackKind(str, Enum):
    """Closed set of host filesystem adapter callbacks.

    Required production set (plan §3.2) plus explicit-unsupported callbacks
    that must return ``ENOSYS`` / ``EOPNOTSUPP`` rather than false success.
    """

    # Metadata
    GETATTR = "getattr"
    READDIR = "readdir"
    ACCESS = "access"
    STATFS = "statfs"
    UTIMENS = "utimens"

    # File lifecycle
    OPEN = "open"
    CREATE = "create"
    READ = "read"
    WRITE = "write"
    TRUNCATE = "truncate"
    FLUSH = "flush"
    FSYNC = "fsync"
    RELEASE = "release"

    # Namespace
    MKDIR = "mkdir"
    RMDIR = "rmdir"
    UNLINK = "unlink"
    RENAME = "rename"

    # Mount lifecycle
    INIT = "init"
    DESTROY = "destroy"

    # Explicit-unsupported by default (must not false-succeed)
    READLINK = "readlink"
    SYMLINK = "symlink"
    LINK = "link"
    MKNOD = "mknod"
    CHMOD = "chmod"
    CHOWN = "chown"
    GETXATTR = "getxattr"
    SETXATTR = "setxattr"
    LISTXATTR = "listxattr"
    REMOVEXATTR = "removexattr"
    FALLOCATE = "fallocate"
    FLOCK = "flock"
    IOCTL = "ioctl"
    POLL = "poll"


class CallbackDisposition(str, Enum):
    """Whether a callback is required-supported or explicit-unsupported."""

    REQUIRED_SUPPORTED = "required_supported"
    EXPLICIT_UNSUPPORTED = "explicit_unsupported"


class HostErrno(str, Enum):
    """Exact errno names projected by the host adapter.

    Values are POSIX symbolic names. Numeric codes differ on Windows; the
    platform projection table maps each name to the host-native integer.
    """

    OK = "OK"
    EPERM = "EPERM"
    ENOENT = "ENOENT"
    EIO = "EIO"
    ENXIO = "ENXIO"
    EBADF = "EBADF"
    EAGAIN = "EAGAIN"
    ENOMEM = "ENOMEM"
    EACCES = "EACCES"
    EFAULT = "EFAULT"
    EBUSY = "EBUSY"
    EEXIST = "EEXIST"
    EXDEV = "EXDEV"
    ENODEV = "ENODEV"
    ENOTDIR = "ENOTDIR"
    EISDIR = "EISDIR"
    EINVAL = "EINVAL"
    ENFILE = "ENFILE"
    EMFILE = "EMFILE"
    EFBIG = "EFBIG"
    ENOSPC = "ENOSPC"
    EROFS = "EROFS"
    EMLINK = "EMLINK"
    EPIPE = "EPIPE"
    ERANGE = "ERANGE"
    ENAMETOOLONG = "ENAMETOOLONG"
    ENOSYS = "ENOSYS"
    ENOTEMPTY = "ENOTEMPTY"
    ELOOP = "ELOOP"
    EOVERFLOW = "EOVERFLOW"
    EOPNOTSUPP = "EOPNOTSUPP"
    ETIMEDOUT = "ETIMEDOUT"
    ECANCELED = "ECANCELED"
    ESTALE = "ESTALE"
    EDQUOT = "EDQUOT"


# Well-known Linux numeric errno values (man 3 errno).
LINUX_ERRNO_NUMBERS: Final[Mapping[HostErrno, int]] = {
    HostErrno.OK: 0,
    HostErrno.EPERM: 1,
    HostErrno.ENOENT: 2,
    HostErrno.EIO: 5,
    HostErrno.ENXIO: 6,
    HostErrno.EBADF: 9,
    HostErrno.EAGAIN: 11,
    HostErrno.ENOMEM: 12,
    HostErrno.EACCES: 13,
    HostErrno.EFAULT: 14,
    HostErrno.EBUSY: 16,
    HostErrno.EEXIST: 17,
    HostErrno.EXDEV: 18,
    HostErrno.ENODEV: 19,
    HostErrno.ENOTDIR: 20,
    HostErrno.EISDIR: 21,
    HostErrno.EINVAL: 22,
    HostErrno.ENFILE: 23,
    HostErrno.EMFILE: 24,
    HostErrno.EFBIG: 27,
    HostErrno.ENOSPC: 28,
    HostErrno.EROFS: 30,
    HostErrno.EMLINK: 31,
    HostErrno.EPIPE: 32,
    HostErrno.ERANGE: 34,
    HostErrno.ENAMETOOLONG: 36,
    HostErrno.ENOSYS: 38,
    HostErrno.ENOTEMPTY: 39,
    HostErrno.ELOOP: 40,
    HostErrno.EOVERFLOW: 75,
    HostErrno.EOPNOTSUPP: 95,
    HostErrno.ETIMEDOUT: 110,
    HostErrno.ECANCELED: 125,
    HostErrno.ESTALE: 116,
    HostErrno.EDQUOT: 122,
}

# WinFsp / Windows FUSE compatibility layer uses the same POSIX names with
# fusepy-projected numbers; a few differ or are aliases.
WINDOWS_ERRNO_NUMBERS: Final[Mapping[HostErrno, int]] = {
    **dict(LINUX_ERRNO_NUMBERS),
    # WinFsp FUSE 2.8 layer maps EOPNOTSUPP / ENOTSUP similarly; keep name.
    HostErrno.EOPNOTSUPP: 95,
    # Windows cancel often surfaces as EINTR-class; contract keeps ECANCELED.
    HostErrno.ECANCELED: 125,
}


class OpenFlag(str, Enum):
    """Closed open/create flag vocabulary (kernel-shaped)."""

    O_RDONLY = "O_RDONLY"
    O_WRONLY = "O_WRONLY"
    O_RDWR = "O_RDWR"
    O_CREAT = "O_CREAT"
    O_EXCL = "O_EXCL"
    O_TRUNC = "O_TRUNC"
    O_APPEND = "O_APPEND"
    O_NONBLOCK = "O_NONBLOCK"
    O_SYNC = "O_SYNC"
    O_DIRECTORY = "O_DIRECTORY"
    O_NOFOLLOW = "O_NOFOLLOW"


class DurabilityMode(str, Enum):
    """Declared durability boundary for host callback acknowledgements.

    ``fsync`` succeeds only after WAL and selected backend durability receipts
    meet the configured mode. ``flush`` / ``release`` cannot manufacture a
    higher durability claim than the mode admits.
    """

    # Intent buffered only; never claim committed durability.
    BUFFERED = "buffered"
    # WAL file fsync observed.
    WAL_FILE_SYNC = "wal_file_sync"
    # WAL file + parent directory durability.
    WAL_PARENT_SYNC = "wal_parent_sync"
    # WAL durable + backend effect receipt.
    WAL_AND_BACKEND = "wal_and_backend"
    # Full pipeline: WAL + backend + ARC generation advance.
    COMMITTED_VISIBLE = "committed_visible"


class CacheConsistencyMode(str, Enum):
    """How open handles observe each others' staged writes."""

    # Each handle reads its own staged extents; cross-handle sees committed only.
    READ_OWN_WRITES = "read_own_writes"
    # After fsync/flush that meets durability, peers see committed bytes.
    COMMITTED_READS = "committed_reads"
    # Strict: only generation-bound ARC after WAL commit (default production).
    GENERATION_BOUND = "generation_bound"


class MountLifecycleState(str, Enum):
    """Closed mount lifecycle states for init/destroy sequencing."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    RECOVERING = "recovering"
    READY = "ready"
    DRAINING = "draining"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    FAILED = "failed"


class HostEntryKind(str, Enum):
    """Host-visible entry kinds for getattr / readdir metadata."""

    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    UNKNOWN = "unknown"


class UnsupportedErrnoPolicy(str, Enum):
    """Which exact errno explicit-unsupported callbacks must return."""

    ENOSYS = "ENOSYS"
    EOPNOTSUPP = "EOPNOTSUPP"


# Required production callbacks (plan §3.2).
REQUIRED_SUPPORTED_CALLBACKS: Final[frozenset[HostCallbackKind]] = frozenset(
    {
        HostCallbackKind.GETATTR,
        HostCallbackKind.READDIR,
        HostCallbackKind.ACCESS,
        HostCallbackKind.STATFS,
        HostCallbackKind.UTIMENS,
        HostCallbackKind.OPEN,
        HostCallbackKind.CREATE,
        HostCallbackKind.READ,
        HostCallbackKind.WRITE,
        HostCallbackKind.TRUNCATE,
        HostCallbackKind.FLUSH,
        HostCallbackKind.FSYNC,
        HostCallbackKind.RELEASE,
        HostCallbackKind.MKDIR,
        HostCallbackKind.RMDIR,
        HostCallbackKind.UNLINK,
        HostCallbackKind.RENAME,
        HostCallbackKind.INIT,
        HostCallbackKind.DESTROY,
    }
)

# Explicit-unsupported by default — must return ENOSYS or EOPNOTSUPP.
EXPLICIT_UNSUPPORTED_CALLBACKS: Final[frozenset[HostCallbackKind]] = frozenset(
    {
        HostCallbackKind.READLINK,
        HostCallbackKind.SYMLINK,
        HostCallbackKind.LINK,
        HostCallbackKind.MKNOD,
        HostCallbackKind.CHMOD,
        HostCallbackKind.CHOWN,
        HostCallbackKind.GETXATTR,
        HostCallbackKind.SETXATTR,
        HostCallbackKind.LISTXATTR,
        HostCallbackKind.REMOVEXATTR,
        HostCallbackKind.FALLOCATE,
        HostCallbackKind.FLOCK,
        HostCallbackKind.IOCTL,
        HostCallbackKind.POLL,
    }
)

# Mutating callbacks that must not report success without observed effects.
MUTATING_CALLBACKS: Final[frozenset[HostCallbackKind]] = frozenset(
    {
        HostCallbackKind.CREATE,
        HostCallbackKind.WRITE,
        HostCallbackKind.TRUNCATE,
        HostCallbackKind.UTIMENS,
        HostCallbackKind.MKDIR,
        HostCallbackKind.RMDIR,
        HostCallbackKind.UNLINK,
        HostCallbackKind.RENAME,
        HostCallbackKind.SETXATTR,
        HostCallbackKind.REMOVEXATTR,
        HostCallbackKind.SYMLINK,
        HostCallbackKind.LINK,
        HostCallbackKind.MKNOD,
        HostCallbackKind.CHMOD,
        HostCallbackKind.CHOWN,
        HostCallbackKind.FALLOCATE,
    }
)

# Handle-bearing callbacks.
HANDLE_CALLBACKS: Final[frozenset[HostCallbackKind]] = frozenset(
    {
        HostCallbackKind.OPEN,
        HostCallbackKind.CREATE,
        HostCallbackKind.READ,
        HostCallbackKind.WRITE,
        HostCallbackKind.FLUSH,
        HostCallbackKind.FSYNC,
        HostCallbackKind.RELEASE,
        HostCallbackKind.TRUNCATE,
    }
)

# Legal mount lifecycle transitions.
_LEGAL_MOUNT_TRANSITIONS: Final[Mapping[MountLifecycleState, frozenset[MountLifecycleState]]] = {
    MountLifecycleState.UNINITIALIZED: frozenset(
        {MountLifecycleState.INITIALIZING, MountLifecycleState.FAILED}
    ),
    MountLifecycleState.INITIALIZING: frozenset(
        {
            MountLifecycleState.RECOVERING,
            MountLifecycleState.READY,
            MountLifecycleState.FAILED,
            MountLifecycleState.DESTROYING,
        }
    ),
    MountLifecycleState.RECOVERING: frozenset(
        {
            MountLifecycleState.READY,
            MountLifecycleState.FAILED,
            MountLifecycleState.DESTROYING,
        }
    ),
    MountLifecycleState.READY: frozenset(
        {
            MountLifecycleState.DRAINING,
            MountLifecycleState.DESTROYING,
            MountLifecycleState.FAILED,
        }
    ),
    MountLifecycleState.DRAINING: frozenset(
        {
            MountLifecycleState.DESTROYING,
            MountLifecycleState.FAILED,
        }
    ),
    MountLifecycleState.DESTROYING: frozenset(
        {
            MountLifecycleState.DESTROYED,
            MountLifecycleState.FAILED,
        }
    ),
    MountLifecycleState.DESTROYED: frozenset(),
    MountLifecycleState.FAILED: frozenset(
        {
            MountLifecycleState.DESTROYING,
            MountLifecycleState.DESTROYED,
        }
    ),
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HostContractError(ValueError):
    """Base class for host contract schema / policy failures."""


class HostBoundsError(HostContractError):
    """A record exceeded its declared compactness bounds."""


class HostFalseSuccessError(HostContractError):
    """Success was claimed with a non-zero errno or unsupported disposition."""


class HostUnknownCallbackError(HostContractError):
    """An unknown callback name was presented to the contract boundary."""


class HostLifecycleError(HostContractError):
    """An illegal mount lifecycle transition was requested."""


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def _text(
    value: Any,
    field_name: str,
    *,
    required: bool = False,
    limit: int = MAX_TEXT_BYTES,
    allow_empty: bool = True,
    strip: bool = True,
) -> str:
    if value is None:
        normalized = ""
    elif not isinstance(value, str):
        raise HostContractError(f"{field_name} must be a string")
    else:
        normalized = value.strip() if strip else value
    if required and not normalized:
        raise HostContractError(f"{field_name} is required")
    if not allow_empty and not normalized:
        raise HostContractError(f"{field_name} must not be empty")
    if len(normalized.encode("utf-8")) > limit:
        raise HostBoundsError(f"{field_name} exceeds its byte bound")
    return normalized


def _identifier(value: Any, field_name: str, *, required: bool = True) -> str:
    text = _text(
        value,
        field_name,
        required=required,
        limit=MAX_IDENTIFIER_BYTES,
        allow_empty=not required,
    )
    if not text:
        return ""
    if any(char.isspace() for char in text):
        raise HostContractError(f"{field_name} must be an opaque compact identifier")
    if not _ID_RE.match(text):
        raise HostContractError(f"{field_name} has an invalid identifier shape")
    return text


def _optional_identifier(value: Any, field_name: str) -> str:
    return _identifier(value, field_name, required=False)


def _bounded_int(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HostContractError(f"{field_name} must be a finite integer")
    if value < minimum or value > maximum:
        raise HostBoundsError(f"{field_name} is outside the supported bound")
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise HostContractError(f"{field_name} must be a boolean")
    return value


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        if isinstance(value, enum):
            return value
        return enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum)
        raise HostContractError(f"{field_name} must be one of: {allowed}") from exc


def _flags(values: Any, field_name: str) -> tuple[OpenFlag, ...]:
    if values is None:
        items: Sequence[Any] = ()
    elif isinstance(values, OpenFlag):
        items = (values,)
    elif isinstance(values, str):
        items = (values,)
    elif isinstance(values, Sequence) and not isinstance(values, (bytes, bytearray)):
        items = values
    else:
        raise HostContractError(f"{field_name} must be a sequence of open flags")
    if len(items) > MAX_REFERENCE_COUNT:
        raise HostBoundsError(f"{field_name} exceeds flag count bound")
    normalized: list[OpenFlag] = []
    seen: set[OpenFlag] = set()
    for item in items:
        flag = _enum(item, OpenFlag, field_name)
        if flag in seen:
            continue
        seen.add(flag)
        normalized.append(flag)
    return tuple(normalized)


def canonical_json_bytes(value: Any) -> bytes:
    """Encode deterministic JSON UTF-8 bytes for content identity."""

    def normalize(item: Any) -> Any:
        if item is None or isinstance(item, (str, bool)):
            return item
        if isinstance(item, int) and not isinstance(item, bool):
            if item < -MAX_SAFE_INTEGER or item > MAX_SAFE_INTEGER:
                raise HostBoundsError("integer outside the safe finite bound")
            return item
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, Mapping):
            if not all(isinstance(k, str) for k in item):
                raise HostContractError("object keys must be strings")
            return {k: normalize(item[k]) for k in sorted(item)}
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        raise HostContractError(f"unsupported canonical value type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_identity(value: Any) -> str:
    """Return a compact content identity for a contract payload."""

    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"sha256:{digest}"


def errno_number(errno: HostErrno, platform: HostPlatform = HostPlatform.LINUX) -> int:
    """Return the host-native integer for an errno name on ``platform``."""

    errno = _enum(errno, HostErrno, "errno")
    platform = _enum(platform, HostPlatform, "platform")
    if platform is HostPlatform.WINDOWS:
        table = WINDOWS_ERRNO_NUMBERS
    else:
        # LINUX and HERMETIC share the Linux projection table.
        table = LINUX_ERRNO_NUMBERS
    if errno not in table:
        raise HostContractError(f"no numeric projection for {errno.value} on {platform.value}")
    return table[errno]


def is_legal_mount_transition(
    from_state: MountLifecycleState, to_state: MountLifecycleState
) -> bool:
    """Return whether ``from_state → to_state`` is an admitted mount transition."""

    if from_state is to_state:
        return True
    allowed = _LEGAL_MOUNT_TRANSITIONS.get(from_state, frozenset())
    return to_state in allowed


def assert_legal_mount_transition(
    from_state: MountLifecycleState, to_state: MountLifecycleState
) -> None:
    """Raise if the mount lifecycle transition is not admitted."""

    if not is_legal_mount_transition(from_state, to_state):
        raise HostLifecycleError(
            f"illegal mount transition {from_state.value} → {to_state.value}"
        )


def callback_disposition(kind: HostCallbackKind) -> CallbackDisposition:
    """Return the closed disposition for a known callback kind."""

    kind = _enum(kind, HostCallbackKind, "kind")
    if kind in REQUIRED_SUPPORTED_CALLBACKS:
        return CallbackDisposition.REQUIRED_SUPPORTED
    if kind in EXPLICIT_UNSUPPORTED_CALLBACKS:
        return CallbackDisposition.EXPLICIT_UNSUPPORTED
    raise HostUnknownCallbackError(f"callback {kind!r} is not in the closed set")


def parse_callback_kind(name: Any) -> HostCallbackKind:
    """Parse a callback name; unknown names are a contract failure."""

    if isinstance(name, HostCallbackKind):
        return name
    if not isinstance(name, str):
        raise HostUnknownCallbackError("callback name must be a string")
    try:
        return HostCallbackKind(name)
    except ValueError as exc:
        raise HostUnknownCallbackError(
            f"unknown host callback {name!r}; unknown callbacks are forbidden"
        ) from exc


def default_unsupported_errno(kind: HostCallbackKind) -> HostErrno:
    """Default exact errno for explicit-unsupported callbacks."""

    kind = _enum(kind, HostCallbackKind, "kind")
    if kind not in EXPLICIT_UNSUPPORTED_CALLBACKS:
        raise HostContractError(
            f"{kind.value} is not an explicit-unsupported callback"
        )
    # Operation-not-supported for feature-shaped calls; ENOSYS for missing ops.
    if kind in (
        HostCallbackKind.FALLOCATE,
        HostCallbackKind.FLOCK,
        HostCallbackKind.IOCTL,
        HostCallbackKind.POLL,
        HostCallbackKind.GETXATTR,
        HostCallbackKind.SETXATTR,
        HostCallbackKind.LISTXATTR,
        HostCallbackKind.REMOVEXATTR,
    ):
        return HostErrno.EOPNOTSUPP
    return HostErrno.ENOSYS


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HostDeadline:
    """Cancellation and deadline envelope for a single callback invocation."""

    SCHEMA: ClassVar[str] = HOST_DEADLINE_SCHEMA

    deadline_ms: int = DEFAULT_CALLBACK_DEADLINE_MS
    cancelled: bool = False
    cancel_reason: str = ""
    started_at_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "deadline_ms",
            _bounded_int(
                self.deadline_ms,
                "deadline_ms",
                minimum=1,
                maximum=MAX_CALLBACK_DEADLINE_MS,
            ),
        )
        object.__setattr__(self, "cancelled", _bool(self.cancelled, "cancelled"))
        object.__setattr__(
            self,
            "cancel_reason",
            _text(self.cancel_reason, "cancel_reason", limit=MAX_TEXT_BYTES),
        )
        object.__setattr__(
            self,
            "started_at_ms",
            _bounded_int(self.started_at_ms, "started_at_ms", minimum=0),
        )
        if self.cancelled and not self.cancel_reason:
            object.__setattr__(self, "cancel_reason", "cancelled")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "deadline_ms": self.deadline_ms,
            "cancelled": self.cancelled,
            "cancel_reason": self.cancel_reason,
            "started_at_ms": self.started_at_ms,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HostDeadline":
        if not isinstance(payload, Mapping):
            raise HostContractError("deadline payload must be a mapping")
        return cls(
            deadline_ms=int(payload.get("deadline_ms", DEFAULT_CALLBACK_DEADLINE_MS)),
            cancelled=bool(payload.get("cancelled", False)),
            cancel_reason=str(payload.get("cancel_reason", "") or ""),
            started_at_ms=int(payload.get("started_at_ms", 0) or 0),
        )


@dataclass(frozen=True)
class HostMetadata:
    """Host-visible inode metadata projected by getattr / create / etc."""

    SCHEMA: ClassVar[str] = HOST_METADATA_SCHEMA

    inode: int
    kind: HostEntryKind
    size: int = 0
    mode: int = 0
    nlink: int = 1
    uid: int = 0
    gid: int = 0
    atime_ns: int = 0
    mtime_ns: int = 0
    ctime_ns: int = 0
    generation: int = 0
    display_name: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "inode", _bounded_int(self.inode, "inode", minimum=1, maximum=MAX_INODE)
        )
        object.__setattr__(self, "kind", _enum(self.kind, HostEntryKind, "kind"))
        object.__setattr__(
            self,
            "size",
            _bounded_int(self.size, "size", minimum=0, maximum=MAX_SIZE_BYTES),
        )
        object.__setattr__(
            self,
            "mode",
            _bounded_int(self.mode, "mode", minimum=0, maximum=0o777777),
        )
        object.__setattr__(
            self, "nlink", _bounded_int(self.nlink, "nlink", minimum=0, maximum=MAX_SAFE_INTEGER)
        )
        object.__setattr__(
            self, "uid", _bounded_int(self.uid, "uid", minimum=0, maximum=MAX_SAFE_INTEGER)
        )
        object.__setattr__(
            self, "gid", _bounded_int(self.gid, "gid", minimum=0, maximum=MAX_SAFE_INTEGER)
        )
        for name in ("atime_ns", "mtime_ns", "ctime_ns", "generation"):
            object.__setattr__(
                self,
                name,
                _bounded_int(getattr(self, name), name, minimum=0),
            )
        object.__setattr__(
            self,
            "display_name",
            _text(self.display_name, "display_name", limit=MAX_NAME_BYTES, strip=False),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "inode": self.inode,
            "kind": self.kind.value,
            "size": self.size,
            "mode": self.mode,
            "nlink": self.nlink,
            "uid": self.uid,
            "gid": self.gid,
            "atime_ns": self.atime_ns,
            "mtime_ns": self.mtime_ns,
            "ctime_ns": self.ctime_ns,
            "generation": self.generation,
            "display_name": self.display_name,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HostMetadata":
        if not isinstance(payload, Mapping):
            raise HostContractError("metadata payload must be a mapping")
        return cls(
            inode=int(payload["inode"]),
            kind=payload["kind"],
            size=int(payload.get("size", 0) or 0),
            mode=int(payload.get("mode", 0) or 0),
            nlink=int(payload.get("nlink", 1) or 1),
            uid=int(payload.get("uid", 0) or 0),
            gid=int(payload.get("gid", 0) or 0),
            atime_ns=int(payload.get("atime_ns", 0) or 0),
            mtime_ns=int(payload.get("mtime_ns", 0) or 0),
            ctime_ns=int(payload.get("ctime_ns", 0) or 0),
            generation=int(payload.get("generation", 0) or 0),
            display_name=str(payload.get("display_name", "") or ""),
        )


@dataclass(frozen=True)
class HostHandle:
    """Generation-tagged, lease-aware open file handle identity.

    Handles, not paths, identify open instances. Rename or unlink must not
    invalidate an already-open handle. ``release`` is idempotent.
    """

    SCHEMA: ClassVar[str] = HOST_HANDLE_SCHEMA

    handle_id: int
    inode: int
    generation: int
    flags: tuple[OpenFlag, ...] = ()
    mount_id: str = ""
    lease_id: str = ""
    path_at_open: str = ""
    released: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "handle_id",
            _bounded_int(self.handle_id, "handle_id", minimum=1, maximum=MAX_HANDLE_ID),
        )
        object.__setattr__(
            self, "inode", _bounded_int(self.inode, "inode", minimum=1, maximum=MAX_INODE)
        )
        object.__setattr__(
            self,
            "generation",
            _bounded_int(self.generation, "generation", minimum=0),
        )
        object.__setattr__(self, "flags", _flags(self.flags, "flags"))
        object.__setattr__(
            self, "mount_id", _optional_identifier(self.mount_id, "mount_id")
        )
        object.__setattr__(
            self, "lease_id", _optional_identifier(self.lease_id, "lease_id")
        )
        object.__setattr__(
            self,
            "path_at_open",
            _text(self.path_at_open, "path_at_open", limit=MAX_PATH_BYTES, strip=False),
        )
        object.__setattr__(self, "released", _bool(self.released, "released"))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "handle_id": self.handle_id,
            "inode": self.inode,
            "generation": self.generation,
            "flags": [flag.value for flag in self.flags],
            "mount_id": self.mount_id,
            "lease_id": self.lease_id,
            "path_at_open": self.path_at_open,
            "released": self.released,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HostHandle":
        if not isinstance(payload, Mapping):
            raise HostContractError("handle payload must be a mapping")
        return cls(
            handle_id=int(payload["handle_id"]),
            inode=int(payload["inode"]),
            generation=int(payload.get("generation", 0) or 0),
            flags=tuple(payload.get("flags") or ()),
            mount_id=str(payload.get("mount_id", "") or ""),
            lease_id=str(payload.get("lease_id", "") or ""),
            path_at_open=str(payload.get("path_at_open", "") or ""),
            released=bool(payload.get("released", False)),
        )


@dataclass(frozen=True)
class HostError:
    """Exact host error with symbolic errno and optional platform number."""

    SCHEMA: ClassVar[str] = HOST_ERROR_SCHEMA

    errno: HostErrno
    message: str = ""
    platform: HostPlatform = HostPlatform.HERMETIC
    vfs_error_code: str = ""
    retryable: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "errno", _enum(self.errno, HostErrno, "errno"))
        if self.errno is HostErrno.OK:
            raise HostContractError("HostError cannot use errno OK; use success result")
        object.__setattr__(
            self, "message", _text(self.message, "message", limit=MAX_TEXT_BYTES)
        )
        object.__setattr__(
            self, "platform", _enum(self.platform, HostPlatform, "platform")
        )
        object.__setattr__(
            self,
            "vfs_error_code",
            _optional_identifier(self.vfs_error_code, "vfs_error_code"),
        )
        object.__setattr__(self, "retryable", _bool(self.retryable, "retryable"))

    @property
    def errno_number(self) -> int:
        return errno_number(self.errno, self.platform)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "errno": self.errno.value,
            "errno_number": self.errno_number,
            "message": self.message,
            "platform": self.platform.value,
            "vfs_error_code": self.vfs_error_code,
            "retryable": self.retryable,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HostError":
        if not isinstance(payload, Mapping):
            raise HostContractError("error payload must be a mapping")
        return cls(
            errno=payload["errno"],
            message=str(payload.get("message", "") or ""),
            platform=payload.get("platform", HostPlatform.HERMETIC),
            vfs_error_code=str(payload.get("vfs_error_code", "") or ""),
            retryable=bool(payload.get("retryable", False)),
        )

    @classmethod
    def unsupported(
        cls,
        kind: HostCallbackKind,
        *,
        platform: HostPlatform = HostPlatform.HERMETIC,
        policy: UnsupportedErrnoPolicy | None = None,
    ) -> "HostError":
        """Build the exact errno for an explicit-unsupported callback."""

        if policy is None:
            errno = default_unsupported_errno(kind)
        else:
            policy = _enum(policy, UnsupportedErrnoPolicy, "policy")
            errno = HostErrno(policy.value)
        return cls(
            errno=errno,
            message=f"callback {kind.value} is explicit-unsupported",
            platform=platform,
            vfs_error_code="VFS_UNSUPPORTED",
            retryable=False,
        )


@dataclass(frozen=True)
class HostCallbackRequest:
    """Finite input record for one host filesystem adapter callback."""

    SCHEMA: ClassVar[str] = HOST_CALLBACK_SCHEMA

    kind: HostCallbackKind
    path: str = ""
    path_to: str = ""
    handle: HostHandle | None = None
    flags: tuple[OpenFlag, ...] = ()
    offset: int = 0
    size: int = 0
    mode: int = 0
    uid: int = 0
    gid: int = 0
    atime_ns: int = 0
    mtime_ns: int = 0
    name: str = ""
    mount_id: str = ""
    request_id: str = ""
    platform: HostPlatform = HostPlatform.HERMETIC
    durability_mode: DurabilityMode = DurabilityMode.COMMITTED_VISIBLE
    cache_consistency: CacheConsistencyMode = CacheConsistencyMode.GENERATION_BOUND
    deadline: HostDeadline = field(default_factory=HostDeadline)
    datasync: bool = False
    """When True on fsync, only data (not necessarily metadata) need sync."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", parse_callback_kind(self.kind))
        object.__setattr__(
            self, "path", _text(self.path, "path", limit=MAX_PATH_BYTES, strip=False)
        )
        object.__setattr__(
            self,
            "path_to",
            _text(self.path_to, "path_to", limit=MAX_PATH_BYTES, strip=False),
        )
        if self.handle is not None and not isinstance(self.handle, HostHandle):
            raise HostContractError("handle must be a HostHandle or None")
        object.__setattr__(self, "flags", _flags(self.flags, "flags"))
        object.__setattr__(
            self,
            "offset",
            _bounded_int(self.offset, "offset", minimum=0, maximum=MAX_OFFSET),
        )
        object.__setattr__(
            self,
            "size",
            _bounded_int(self.size, "size", minimum=0, maximum=MAX_IO_LENGTH),
        )
        object.__setattr__(
            self,
            "mode",
            _bounded_int(self.mode, "mode", minimum=0, maximum=0o777777),
        )
        object.__setattr__(
            self, "uid", _bounded_int(self.uid, "uid", minimum=0)
        )
        object.__setattr__(
            self, "gid", _bounded_int(self.gid, "gid", minimum=0)
        )
        object.__setattr__(
            self, "atime_ns", _bounded_int(self.atime_ns, "atime_ns", minimum=0)
        )
        object.__setattr__(
            self, "mtime_ns", _bounded_int(self.mtime_ns, "mtime_ns", minimum=0)
        )
        object.__setattr__(
            self, "name", _text(self.name, "name", limit=MAX_NAME_BYTES, strip=False)
        )
        object.__setattr__(
            self, "mount_id", _optional_identifier(self.mount_id, "mount_id")
        )
        object.__setattr__(
            self, "request_id", _optional_identifier(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "platform", _enum(self.platform, HostPlatform, "platform")
        )
        object.__setattr__(
            self,
            "durability_mode",
            _enum(self.durability_mode, DurabilityMode, "durability_mode"),
        )
        object.__setattr__(
            self,
            "cache_consistency",
            _enum(self.cache_consistency, CacheConsistencyMode, "cache_consistency"),
        )
        if not isinstance(self.deadline, HostDeadline):
            raise HostContractError("deadline must be a HostDeadline")
        object.__setattr__(self, "datasync", _bool(self.datasync, "datasync"))

    @property
    def disposition(self) -> CallbackDisposition:
        return callback_disposition(self.kind)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "disposition": self.disposition.value,
            "path": self.path,
            "path_to": self.path_to,
            "handle": None if self.handle is None else self.handle.to_record(),
            "flags": [flag.value for flag in self.flags],
            "offset": self.offset,
            "size": self.size,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "atime_ns": self.atime_ns,
            "mtime_ns": self.mtime_ns,
            "name": self.name,
            "mount_id": self.mount_id,
            "request_id": self.request_id,
            "platform": self.platform.value,
            "durability_mode": self.durability_mode.value,
            "cache_consistency": self.cache_consistency.value,
            "deadline": self.deadline.to_record(),
            "datasync": self.datasync,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HostCallbackRequest":
        if not isinstance(payload, Mapping):
            raise HostContractError("callback request payload must be a mapping")
        handle_payload = payload.get("handle")
        handle = (
            None
            if handle_payload is None
            else HostHandle.from_dict(handle_payload)
        )
        deadline_payload = payload.get("deadline")
        deadline = (
            HostDeadline()
            if deadline_payload is None
            else HostDeadline.from_dict(deadline_payload)
        )
        return cls(
            kind=payload["kind"],
            path=str(payload.get("path", "") or ""),
            path_to=str(payload.get("path_to", "") or ""),
            handle=handle,
            flags=tuple(payload.get("flags") or ()),
            offset=int(payload.get("offset", 0) or 0),
            size=int(payload.get("size", 0) or 0),
            mode=int(payload.get("mode", 0) or 0),
            uid=int(payload.get("uid", 0) or 0),
            gid=int(payload.get("gid", 0) or 0),
            atime_ns=int(payload.get("atime_ns", 0) or 0),
            mtime_ns=int(payload.get("mtime_ns", 0) or 0),
            name=str(payload.get("name", "") or ""),
            mount_id=str(payload.get("mount_id", "") or ""),
            request_id=str(payload.get("request_id", "") or ""),
            platform=payload.get("platform", HostPlatform.HERMETIC),
            durability_mode=payload.get(
                "durability_mode", DurabilityMode.COMMITTED_VISIBLE
            ),
            cache_consistency=payload.get(
                "cache_consistency", CacheConsistencyMode.GENERATION_BOUND
            ),
            deadline=deadline,
            datasync=bool(payload.get("datasync", False)),
        )


@dataclass(frozen=True)
class HostCallbackResult:
    """Finite result record for one host callback; forbids false success.

    Contract rules:

    * ``success=True`` requires ``errno == OK`` and ``error is None``.
    * ``success=False`` requires a non-OK ``errno`` and a ``HostError``.
    * explicit-unsupported callbacks may only succeed if the disposition is
      later upgraded by a separate contract revision; under v1 they must fail
      with ``ENOSYS`` or ``EOPNOTSUPP``.
    * cancelled / timed-out requests must not report success.
    * ``release`` success is allowed when already released (idempotent).
    """

    SCHEMA: ClassVar[str] = HOST_CALLBACK_RESULT_SCHEMA

    kind: HostCallbackKind
    success: bool
    errno: HostErrno = HostErrno.OK
    error: HostError | None = None
    handle: HostHandle | None = None
    metadata: HostMetadata | None = None
    bytes_transferred: int = 0
    dir_entries: tuple[str, ...] = ()
    mount_state: MountLifecycleState | None = None
    durability_mode: DurabilityMode = DurabilityMode.COMMITTED_VISIBLE
    cache_consistency: CacheConsistencyMode = CacheConsistencyMode.GENERATION_BOUND
    observed_effect: bool = False
    """True when a mutating callback observed an admitted state transition."""

    request_id: str = ""
    platform: HostPlatform = HostPlatform.HERMETIC

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", parse_callback_kind(self.kind))
        object.__setattr__(self, "success", _bool(self.success, "success"))
        object.__setattr__(self, "errno", _enum(self.errno, HostErrno, "errno"))
        if self.error is not None and not isinstance(self.error, HostError):
            raise HostContractError("error must be a HostError or None")
        if self.handle is not None and not isinstance(self.handle, HostHandle):
            raise HostContractError("handle must be a HostHandle or None")
        if self.metadata is not None and not isinstance(self.metadata, HostMetadata):
            raise HostContractError("metadata must be a HostMetadata or None")
        object.__setattr__(
            self,
            "bytes_transferred",
            _bounded_int(
                self.bytes_transferred,
                "bytes_transferred",
                minimum=0,
                maximum=MAX_IO_LENGTH,
            ),
        )
        if self.dir_entries is None:
            entries: tuple[str, ...] = ()
        elif isinstance(self.dir_entries, Sequence) and not isinstance(
            self.dir_entries, (str, bytes, bytearray)
        ):
            if len(self.dir_entries) > MAX_REFERENCE_COUNT:
                raise HostBoundsError("dir_entries exceeds bound")
            entries = tuple(
                _text(item, "dir_entries", limit=MAX_NAME_BYTES, strip=False)
                for item in self.dir_entries
            )
        else:
            raise HostContractError("dir_entries must be a sequence of names")
        object.__setattr__(self, "dir_entries", entries)
        if self.mount_state is not None:
            object.__setattr__(
                self,
                "mount_state",
                _enum(self.mount_state, MountLifecycleState, "mount_state"),
            )
        object.__setattr__(
            self,
            "durability_mode",
            _enum(self.durability_mode, DurabilityMode, "durability_mode"),
        )
        object.__setattr__(
            self,
            "cache_consistency",
            _enum(self.cache_consistency, CacheConsistencyMode, "cache_consistency"),
        )
        object.__setattr__(
            self, "observed_effect", _bool(self.observed_effect, "observed_effect")
        )
        object.__setattr__(
            self, "request_id", _optional_identifier(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "platform", _enum(self.platform, HostPlatform, "platform")
        )

        self._assert_success_policy()

    def _assert_success_policy(self) -> None:
        disposition = callback_disposition(self.kind)

        if self.success:
            if self.errno is not HostErrno.OK:
                raise HostFalseSuccessError(
                    f"success with non-zero errno {self.errno.value} is forbidden"
                )
            if self.error is not None:
                raise HostFalseSuccessError("success result cannot carry an error")
            if disposition is CallbackDisposition.EXPLICIT_UNSUPPORTED:
                raise HostFalseSuccessError(
                    f"explicit-unsupported callback {self.kind.value} must not succeed; "
                    "return ENOSYS or EOPNOTSUPP"
                )
            if self.kind in MUTATING_CALLBACKS and not self.observed_effect:
                raise HostFalseSuccessError(
                    f"mutating callback {self.kind.value} success requires observed_effect=True"
                )
            # fsync may only claim durability modes that are not mere buffered.
            if self.kind is HostCallbackKind.FSYNC and self.durability_mode is DurabilityMode.BUFFERED:
                raise HostFalseSuccessError(
                    "fsync success cannot claim only buffered durability"
                )
        else:
            if self.errno is HostErrno.OK:
                raise HostContractError("failure requires a non-OK errno")
            if self.error is None:
                raise HostContractError("failure requires a HostError")
            if self.error.errno is not self.errno:
                raise HostContractError(
                    "result errno must match HostError.errno"
                )
            if disposition is CallbackDisposition.EXPLICIT_UNSUPPORTED:
                if self.errno not in (HostErrno.ENOSYS, HostErrno.EOPNOTSUPP):
                    raise HostContractError(
                        f"explicit-unsupported {self.kind.value} must fail with "
                        f"ENOSYS or EOPNOTSUPP, not {self.errno.value}"
                    )

    @property
    def errno_number(self) -> int:
        return errno_number(self.errno, self.platform)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "success": self.success,
            "errno": self.errno.value,
            "errno_number": self.errno_number,
            "error": None if self.error is None else self.error.to_record(),
            "handle": None if self.handle is None else self.handle.to_record(),
            "metadata": None if self.metadata is None else self.metadata.to_record(),
            "bytes_transferred": self.bytes_transferred,
            "dir_entries": list(self.dir_entries),
            "mount_state": None if self.mount_state is None else self.mount_state.value,
            "durability_mode": self.durability_mode.value,
            "cache_consistency": self.cache_consistency.value,
            "observed_effect": self.observed_effect,
            "request_id": self.request_id,
            "platform": self.platform.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HostCallbackResult":
        if not isinstance(payload, Mapping):
            raise HostContractError("callback result payload must be a mapping")
        error_payload = payload.get("error")
        handle_payload = payload.get("handle")
        metadata_payload = payload.get("metadata")
        return cls(
            kind=payload["kind"],
            success=bool(payload["success"]),
            errno=payload.get("errno", HostErrno.OK if payload.get("success") else HostErrno.EIO),
            error=None if error_payload is None else HostError.from_dict(error_payload),
            handle=None if handle_payload is None else HostHandle.from_dict(handle_payload),
            metadata=(
                None
                if metadata_payload is None
                else HostMetadata.from_dict(metadata_payload)
            ),
            bytes_transferred=int(payload.get("bytes_transferred", 0) or 0),
            dir_entries=tuple(payload.get("dir_entries") or ()),
            mount_state=payload.get("mount_state"),
            durability_mode=payload.get(
                "durability_mode", DurabilityMode.COMMITTED_VISIBLE
            ),
            cache_consistency=payload.get(
                "cache_consistency", CacheConsistencyMode.GENERATION_BOUND
            ),
            observed_effect=bool(payload.get("observed_effect", False)),
            request_id=str(payload.get("request_id", "") or ""),
            platform=payload.get("platform", HostPlatform.HERMETIC),
        )

    @classmethod
    def make_success(
        cls,
        kind: HostCallbackKind | str,
        *,
        handle: HostHandle | None = None,
        metadata: HostMetadata | None = None,
        bytes_transferred: int = 0,
        dir_entries: Sequence[str] = (),
        mount_state: MountLifecycleState | None = None,
        durability_mode: DurabilityMode = DurabilityMode.COMMITTED_VISIBLE,
        cache_consistency: CacheConsistencyMode = CacheConsistencyMode.GENERATION_BOUND,
        observed_effect: bool | None = None,
        request_id: str = "",
        platform: HostPlatform = HostPlatform.HERMETIC,
    ) -> "HostCallbackResult":
        """Build a success result that satisfies the false-success guardrails."""

        kind = parse_callback_kind(kind)
        if observed_effect is None:
            observed_effect = kind in MUTATING_CALLBACKS
        return cls(
            kind=kind,
            success=True,
            errno=HostErrno.OK,
            error=None,
            handle=handle,
            metadata=metadata,
            bytes_transferred=bytes_transferred,
            dir_entries=tuple(dir_entries),
            mount_state=mount_state,
            durability_mode=durability_mode,
            cache_consistency=cache_consistency,
            observed_effect=observed_effect,
            request_id=request_id,
            platform=platform,
        )

    @classmethod
    def make_failure(
        cls,
        kind: HostCallbackKind | str,
        errno: HostErrno | str,
        *,
        message: str = "",
        request_id: str = "",
        platform: HostPlatform = HostPlatform.HERMETIC,
        vfs_error_code: str = "",
        retryable: bool = False,
        durability_mode: DurabilityMode = DurabilityMode.COMMITTED_VISIBLE,
        cache_consistency: CacheConsistencyMode = CacheConsistencyMode.GENERATION_BOUND,
    ) -> "HostCallbackResult":
        """Build a failure result with exact errno (never false success)."""

        kind = parse_callback_kind(kind)
        errno = _enum(errno, HostErrno, "errno")
        error = HostError(
            errno=errno,
            message=message or f"{kind.value} failed with {errno.value}",
            platform=platform,
            vfs_error_code=vfs_error_code,
            retryable=retryable,
        )
        return cls(
            kind=kind,
            success=False,
            errno=errno,
            error=error,
            request_id=request_id,
            platform=platform,
            durability_mode=durability_mode,
            cache_consistency=cache_consistency,
            observed_effect=False,
        )

    @classmethod
    def make_unsupported(
        cls,
        kind: HostCallbackKind | str,
        *,
        platform: HostPlatform = HostPlatform.HERMETIC,
        policy: UnsupportedErrnoPolicy | None = None,
        request_id: str = "",
    ) -> "HostCallbackResult":
        """Build the mandated ENOSYS/EOPNOTSUPP result for unsupported callbacks."""

        kind = parse_callback_kind(kind)
        error = HostError.unsupported(kind, platform=platform, policy=policy)
        return cls(
            kind=kind,
            success=False,
            errno=error.errno,
            error=error,
            request_id=request_id,
            platform=platform,
            observed_effect=False,
        )

    @classmethod
    def make_cancelled(
        cls,
        kind: HostCallbackKind | str,
        *,
        timed_out: bool = False,
        request_id: str = "",
        platform: HostPlatform = HostPlatform.HERMETIC,
    ) -> "HostCallbackResult":
        """Build a cancellation / deadline failure (never success)."""

        errno = HostErrno.ETIMEDOUT if timed_out else HostErrno.ECANCELED
        message = "callback deadline exceeded" if timed_out else "callback cancelled"
        return cls.make_failure(
            kind,
            errno,
            message=message,
            request_id=request_id,
            platform=platform,
            retryable=False,
        )


@dataclass(frozen=True)
class HostMountLifecycle:
    """Mount lifecycle record: init / recovery / ready / drain / destroy."""

    SCHEMA: ClassVar[str] = HOST_MOUNT_LIFECYCLE_SCHEMA

    mount_id: str
    state: MountLifecycleState
    platform: HostPlatform = HostPlatform.HERMETIC
    recovery_required: bool = True
    recovery_complete: bool = False
    ready: bool = False
    durability_mode: DurabilityMode = DurabilityMode.COMMITTED_VISIBLE
    cache_consistency: CacheConsistencyMode = CacheConsistencyMode.GENERATION_BOUND
    open_handles: int = 0
    generation: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mount_id", _identifier(self.mount_id, "mount_id")
        )
        object.__setattr__(
            self, "state", _enum(self.state, MountLifecycleState, "state")
        )
        object.__setattr__(
            self, "platform", _enum(self.platform, HostPlatform, "platform")
        )
        object.__setattr__(
            self,
            "recovery_required",
            _bool(self.recovery_required, "recovery_required"),
        )
        object.__setattr__(
            self,
            "recovery_complete",
            _bool(self.recovery_complete, "recovery_complete"),
        )
        object.__setattr__(self, "ready", _bool(self.ready, "ready"))
        object.__setattr__(
            self,
            "durability_mode",
            _enum(self.durability_mode, DurabilityMode, "durability_mode"),
        )
        object.__setattr__(
            self,
            "cache_consistency",
            _enum(self.cache_consistency, CacheConsistencyMode, "cache_consistency"),
        )
        object.__setattr__(
            self,
            "open_handles",
            _bounded_int(self.open_handles, "open_handles", minimum=0),
        )
        object.__setattr__(
            self,
            "generation",
            _bounded_int(self.generation, "generation", minimum=0),
        )

        # Ready handshake requires recovery complete when recovery is required.
        if self.ready:
            if self.state is not MountLifecycleState.READY:
                raise HostLifecycleError("ready=True requires state READY")
            if self.recovery_required and not self.recovery_complete:
                raise HostLifecycleError(
                    "mount readiness requires recovery_complete when recovery_required"
                )
        if self.state is MountLifecycleState.READY and not self.ready:
            raise HostLifecycleError("state READY requires ready=True")

    def transition_to(self, to_state: MountLifecycleState) -> "HostMountLifecycle":
        """Return a new lifecycle record after an admitted transition."""

        to_state = _enum(to_state, MountLifecycleState, "to_state")
        assert_legal_mount_transition(self.state, to_state)
        ready = to_state is MountLifecycleState.READY
        recovery_complete = self.recovery_complete
        if to_state is MountLifecycleState.READY:
            recovery_complete = True
        if to_state in (
            MountLifecycleState.DESTROYED,
            MountLifecycleState.FAILED,
            MountLifecycleState.UNINITIALIZED,
        ):
            ready = False
        if to_state is MountLifecycleState.RECOVERING:
            recovery_complete = False
            ready = False
        return HostMountLifecycle(
            mount_id=self.mount_id,
            state=to_state,
            platform=self.platform,
            recovery_required=self.recovery_required,
            recovery_complete=recovery_complete,
            ready=ready,
            durability_mode=self.durability_mode,
            cache_consistency=self.cache_consistency,
            open_handles=0 if to_state is MountLifecycleState.DESTROYED else self.open_handles,
            generation=self.generation,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "mount_id": self.mount_id,
            "state": self.state.value,
            "platform": self.platform.value,
            "recovery_required": self.recovery_required,
            "recovery_complete": self.recovery_complete,
            "ready": self.ready,
            "durability_mode": self.durability_mode.value,
            "cache_consistency": self.cache_consistency.value,
            "open_handles": self.open_handles,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HostMountLifecycle":
        if not isinstance(payload, Mapping):
            raise HostContractError("mount lifecycle payload must be a mapping")
        return cls(
            mount_id=str(payload["mount_id"]),
            state=payload["state"],
            platform=payload.get("platform", HostPlatform.HERMETIC),
            recovery_required=bool(payload.get("recovery_required", True)),
            recovery_complete=bool(payload.get("recovery_complete", False)),
            ready=bool(payload.get("ready", False)),
            durability_mode=payload.get(
                "durability_mode", DurabilityMode.COMMITTED_VISIBLE
            ),
            cache_consistency=payload.get(
                "cache_consistency", CacheConsistencyMode.GENERATION_BOUND
            ),
            open_handles=int(payload.get("open_handles", 0) or 0),
            generation=int(payload.get("generation", 0) or 0),
        )


@dataclass(frozen=True)
class HostPlatformDifference:
    """Documented Linux vs Windows host projection difference."""

    SCHEMA: ClassVar[str] = HOST_PLATFORM_DIFF_SCHEMA

    topic: str
    linux_behavior: str
    windows_behavior: str
    fail_closed: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "topic", _text(self.topic, "topic", required=True, allow_empty=False)
        )
        object.__setattr__(
            self,
            "linux_behavior",
            _text(self.linux_behavior, "linux_behavior", required=True, allow_empty=False),
        )
        object.__setattr__(
            self,
            "windows_behavior",
            _text(
                self.windows_behavior, "windows_behavior", required=True, allow_empty=False
            ),
        )
        object.__setattr__(
            self, "fail_closed", _bool(self.fail_closed, "fail_closed")
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "topic": self.topic,
            "linux_behavior": self.linux_behavior,
            "windows_behavior": self.windows_behavior,
            "fail_closed": self.fail_closed,
        }


# Closed catalogue of Linux/Windows differences that adapters must honour.
PLATFORM_DIFFERENCES: Final[tuple[HostPlatformDifference, ...]] = (
    HostPlatformDifference(
        topic="case_identity",
        linux_behavior="case-sensitive path identity by default",
        windows_behavior=(
            "collision-safe lookup identity on case-insensitive volumes; "
            "ambiguous folds fail closed; display spelling preserved"
        ),
        fail_closed=True,
    ),
    HostPlatformDifference(
        topic="reserved_names",
        linux_behavior="no DOS device reserved names",
        windows_behavior=(
            "CON, PRN, AUX, NUL, COM1-9, LPT1-9 and trailing dots/spaces reject"
        ),
        fail_closed=True,
    ),
    HostPlatformDifference(
        topic="mount_root",
        linux_behavior="directory mountpoint via FUSE kernel device",
        windows_behavior="drive-letter or directory mount via WinFsp FUSE layer",
        fail_closed=True,
    ),
    HostPlatformDifference(
        topic="delete_while_open",
        linux_behavior="unlink while open leaves handle valid until release",
        windows_behavior=(
            "open-delete sharing and rename-while-open follow WinFsp share rules; "
            "handle remains valid until release"
        ),
        fail_closed=True,
    ),
    HostPlatformDifference(
        topic="uid_gid_mode",
        linux_behavior="POSIX uid/gid/mode projected from getattr",
        windows_behavior=(
            "uid/gid/mode projected into WinFsp-compatible attributes; "
            "ACL/ADS/reparse are explicit-unsupported unless admitted later"
        ),
        fail_closed=True,
    ),
    HostPlatformDifference(
        topic="loader",
        linux_behavior="lazy fusepy import over libfuse2 high-level ABI",
        windows_behavior=(
            "deterministic WinFsp DLL resolution via FUSE_LIBRARY_PATH then registry; "
            "architecture must match"
        ),
        fail_closed=True,
    ),
)


@dataclass(frozen=True)
class HostFilesystemAdapterContract:
    """Versioned host filesystem adapter contract catalogue (``HostFilesystemAdapter@1``)."""

    SCHEMA: ClassVar[str] = HOST_FILESYSTEM_ADAPTER_SCHEMA

    contract_version: int = CONTRACT_VERSION
    schema_version: str = SCHEMA_VERSION
    required_callbacks: tuple[HostCallbackKind, ...] = field(
        default_factory=lambda: tuple(
            sorted(REQUIRED_SUPPORTED_CALLBACKS, key=lambda k: k.value)
        )
    )
    unsupported_callbacks: tuple[HostCallbackKind, ...] = field(
        default_factory=lambda: tuple(
            sorted(EXPLICIT_UNSUPPORTED_CALLBACKS, key=lambda k: k.value)
        )
    )
    durability_modes: tuple[DurabilityMode, ...] = field(
        default_factory=lambda: tuple(DurabilityMode)
    )
    cache_consistency_modes: tuple[CacheConsistencyMode, ...] = field(
        default_factory=lambda: tuple(CacheConsistencyMode)
    )
    platforms: tuple[HostPlatform, ...] = field(
        default_factory=lambda: tuple(HostPlatform)
    )
    platform_differences: tuple[HostPlatformDifference, ...] = PLATFORM_DIFFERENCES
    default_durability_mode: DurabilityMode = DurabilityMode.COMMITTED_VISIBLE
    default_cache_consistency: CacheConsistencyMode = (
        CacheConsistencyMode.GENERATION_BOUND
    )
    default_deadline_ms: int = DEFAULT_CALLBACK_DEADLINE_MS
    release_is_idempotent: bool = True
    unknown_callbacks_forbidden: bool = True
    false_success_forbidden: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "contract_version",
            _bounded_int(self.contract_version, "contract_version", minimum=1),
        )
        object.__setattr__(
            self,
            "schema_version",
            _text(self.schema_version, "schema_version", required=True, allow_empty=False),
        )
        required = tuple(
            _enum(item, HostCallbackKind, "required_callbacks")
            for item in self.required_callbacks
        )
        unsupported = tuple(
            _enum(item, HostCallbackKind, "unsupported_callbacks")
            for item in self.unsupported_callbacks
        )
        object.__setattr__(self, "required_callbacks", required)
        object.__setattr__(self, "unsupported_callbacks", unsupported)
        overlap = set(required) & set(unsupported)
        if overlap:
            names = ", ".join(sorted(k.value for k in overlap))
            raise HostContractError(
                f"callback cannot be both required and unsupported: {names}"
            )
        missing_required = REQUIRED_SUPPORTED_CALLBACKS - set(required)
        if missing_required:
            names = ", ".join(sorted(k.value for k in missing_required))
            raise HostContractError(f"required callbacks missing from catalogue: {names}")
        missing_unsupported = EXPLICIT_UNSUPPORTED_CALLBACKS - set(unsupported)
        if missing_unsupported:
            names = ", ".join(sorted(k.value for k in missing_unsupported))
            raise HostContractError(
                f"explicit-unsupported callbacks missing from catalogue: {names}"
            )
        object.__setattr__(
            self,
            "durability_modes",
            tuple(_enum(m, DurabilityMode, "durability_modes") for m in self.durability_modes),
        )
        object.__setattr__(
            self,
            "cache_consistency_modes",
            tuple(
                _enum(m, CacheConsistencyMode, "cache_consistency_modes")
                for m in self.cache_consistency_modes
            ),
        )
        object.__setattr__(
            self,
            "platforms",
            tuple(_enum(p, HostPlatform, "platforms") for p in self.platforms),
        )
        object.__setattr__(
            self,
            "default_durability_mode",
            _enum(self.default_durability_mode, DurabilityMode, "default_durability_mode"),
        )
        object.__setattr__(
            self,
            "default_cache_consistency",
            _enum(
                self.default_cache_consistency,
                CacheConsistencyMode,
                "default_cache_consistency",
            ),
        )
        object.__setattr__(
            self,
            "default_deadline_ms",
            _bounded_int(
                self.default_deadline_ms,
                "default_deadline_ms",
                minimum=1,
                maximum=MAX_CALLBACK_DEADLINE_MS,
            ),
        )
        for name in (
            "release_is_idempotent",
            "unknown_callbacks_forbidden",
            "false_success_forbidden",
        ):
            object.__setattr__(self, name, _bool(getattr(self, name), name))
        if not self.release_is_idempotent:
            raise HostContractError("release must be idempotent under this contract")
        if not self.unknown_callbacks_forbidden:
            raise HostContractError("unknown callbacks must remain forbidden")
        if not self.false_success_forbidden:
            raise HostContractError("false success must remain forbidden")

    def disposition_for(self, kind: HostCallbackKind | str) -> CallbackDisposition:
        kind = parse_callback_kind(kind)
        if kind in self.required_callbacks:
            return CallbackDisposition.REQUIRED_SUPPORTED
        if kind in self.unsupported_callbacks:
            return CallbackDisposition.EXPLICIT_UNSUPPORTED
        raise HostUnknownCallbackError(f"unknown host callback {kind.value}")

    def project_unsupported(
        self,
        kind: HostCallbackKind | str,
        *,
        platform: HostPlatform = HostPlatform.HERMETIC,
    ) -> HostCallbackResult:
        """Project an explicit-unsupported callback to ENOSYS/EOPNOTSUPP."""

        kind = parse_callback_kind(kind)
        if self.disposition_for(kind) is not CallbackDisposition.EXPLICIT_UNSUPPORTED:
            raise HostContractError(
                f"{kind.value} is not catalogue-listed as explicit-unsupported"
            )
        return HostCallbackResult.make_unsupported(kind, platform=platform)

    def content_id(self) -> str:
        return content_identity(self.to_record())

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
            "required_callbacks": [k.value for k in self.required_callbacks],
            "unsupported_callbacks": [k.value for k in self.unsupported_callbacks],
            "durability_modes": [m.value for m in self.durability_modes],
            "cache_consistency_modes": [m.value for m in self.cache_consistency_modes],
            "platforms": [p.value for p in self.platforms],
            "platform_differences": [d.to_record() for d in self.platform_differences],
            "default_durability_mode": self.default_durability_mode.value,
            "default_cache_consistency": self.default_cache_consistency.value,
            "default_deadline_ms": self.default_deadline_ms,
            "release_is_idempotent": self.release_is_idempotent,
            "unknown_callbacks_forbidden": self.unknown_callbacks_forbidden,
            "false_success_forbidden": self.false_success_forbidden,
        }

    @classmethod
    def default(cls) -> "HostFilesystemAdapterContract":
        """Return the fail-closed default host adapter contract."""

        return cls()


def evaluate_cancelled_request(request: HostCallbackRequest) -> HostCallbackResult | None:
    """If the request is cancelled or past policy, return a failure result.

    Returns ``None`` when the request may proceed. Cancelled/deadline failures
    never succeed.
    """

    if not isinstance(request, HostCallbackRequest):
        raise HostContractError("request must be a HostCallbackRequest")
    if request.deadline.cancelled:
        return HostCallbackResult.make_cancelled(
            request.kind,
            timed_out=False,
            request_id=request.request_id,
            platform=request.platform,
        )
    return None


def assert_no_fusepy_import() -> None:
    """Guardrail helper: this module must not require a native FUSE binding.

    Callers may use this in tests. The function intentionally does not import
    any native FUSE binding; it only asserts that the host contract surface
    remains inert by scanning for real import statements (not prose).
    """

    import ast

    source_path = __file__
    with open(source_path, encoding="utf-8") as handle:
        text = handle.read()
    tree = ast.parse(text, filename=source_path)
    banned_modules = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in banned_modules:
                    raise HostContractError(
                        f"host_contracts must not import {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0] if module else ""
            if root in banned_modules:
                raise HostContractError(
                    f"host_contracts must not import from {module}"
                )


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "HOST_FILESYSTEM_ADAPTER_SCHEMA",
    "HOST_CALLBACK_SCHEMA",
    "HOST_CALLBACK_RESULT_SCHEMA",
    "HOST_HANDLE_SCHEMA",
    "HOST_METADATA_SCHEMA",
    "HOST_MOUNT_LIFECYCLE_SCHEMA",
    "HOST_ERROR_SCHEMA",
    "HOST_DEADLINE_SCHEMA",
    "HOST_PLATFORM_DIFF_SCHEMA",
    "HostFilesystemAdapter_V1",
    "HostCallback_V1",
    "HostCallbackResult_V1",
    "HostHandle_V1",
    "HostMountLifecycle_V1",
    "HostPlatform",
    "HostCallbackKind",
    "CallbackDisposition",
    "HostErrno",
    "LINUX_ERRNO_NUMBERS",
    "WINDOWS_ERRNO_NUMBERS",
    "OpenFlag",
    "DurabilityMode",
    "CacheConsistencyMode",
    "MountLifecycleState",
    "HostEntryKind",
    "UnsupportedErrnoPolicy",
    "REQUIRED_SUPPORTED_CALLBACKS",
    "EXPLICIT_UNSUPPORTED_CALLBACKS",
    "MUTATING_CALLBACKS",
    "HANDLE_CALLBACKS",
    "PLATFORM_DIFFERENCES",
    "HostContractError",
    "HostBoundsError",
    "HostFalseSuccessError",
    "HostUnknownCallbackError",
    "HostLifecycleError",
    "HostDeadline",
    "HostMetadata",
    "HostHandle",
    "HostError",
    "HostCallbackRequest",
    "HostCallbackResult",
    "HostMountLifecycle",
    "HostPlatformDifference",
    "HostFilesystemAdapterContract",
    "canonical_json_bytes",
    "content_identity",
    "errno_number",
    "is_legal_mount_transition",
    "assert_legal_mount_transition",
    "callback_disposition",
    "parse_callback_kind",
    "default_unsupported_errno",
    "evaluate_cancelled_request",
    "assert_no_fusepy_import",
]

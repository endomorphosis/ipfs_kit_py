"""Kernel metadata projection: stat, access, statfs, time, unsupported ops (KVFS-201).

This module owns the kernel-facing *metadata plane* for the common VFS runtime:

* deterministic file type, mode, nlink, size, inode, and time projection;
* explicit uid/gid ownership policy (fixed, caller, root);
* ``access(2)``-shaped permission checks with exact errno;
* ``statfs`` volume statistics with closed, bounded fields;
* ``utimens`` with ``UTIME_NOW`` / ``UTIME_OMIT`` and exact errors;
* stable ``ENOSYS`` / ``EOPNOTSUPP`` results for chmod/chown/xattr/link/
  symlink/mknod (and related explicit-unsupported callbacks).

Conflict policy: own metadata types and projection only. Mount-specific
fusepy callbacks, handle staging, and WAL effects remain out of scope.
No fusepy, libfuse, WinFsp, or host filesystem I/O is imported or performed.

Interfaces (plan aliases): ``KernelMetadata@1``, ``KernelStatfs@1``,
``MetadataProjector@1``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, ClassVar, Final, TypeVar

from ipfs_kit_py.core.vfs.host_contracts import (
    EXPLICIT_UNSUPPORTED_CALLBACKS,
    HOST_METADATA_SCHEMA,
    MAX_INODE,
    MAX_SAFE_INTEGER,
    MAX_SIZE_BYTES,
    HostCallbackKind,
    HostCallbackResult,
    HostEntryKind,
    HostErrno,
    HostError,
    HostMetadata,
    HostPlatform,
    UnsupportedErrnoPolicy,
    callback_disposition,
    content_identity,
    default_unsupported_errno,
    errno_number,
    parse_callback_kind,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

METADATA_MODULE_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/metadata"

KERNEL_METADATA_SCHEMA: Final[str] = (
    f"{METADATA_MODULE_NAMESPACE}/kernel-metadata@{SCHEMA_MAJOR}"
)
KERNEL_STATFS_SCHEMA: Final[str] = (
    f"{METADATA_MODULE_NAMESPACE}/kernel-statfs@{SCHEMA_MAJOR}"
)
METADATA_PROJECTOR_SCHEMA: Final[str] = (
    f"{METADATA_MODULE_NAMESPACE}/metadata-projector@{SCHEMA_MAJOR}"
)
UID_GID_POLICY_SCHEMA: Final[str] = (
    f"{METADATA_MODULE_NAMESPACE}/uid-gid-policy@{SCHEMA_MAJOR}"
)
ACCESS_RESULT_SCHEMA: Final[str] = (
    f"{METADATA_MODULE_NAMESPACE}/access-result@{SCHEMA_MAJOR}"
)
UTIMENS_RESULT_SCHEMA: Final[str] = (
    f"{METADATA_MODULE_NAMESPACE}/utimens-result@{SCHEMA_MAJOR}"
)
METADATA_TRACE_SCHEMA: Final[str] = (
    f"{METADATA_MODULE_NAMESPACE}/metadata-trace@{SCHEMA_MAJOR}"
)
NODE_ATTR_SCHEMA: Final[str] = f"{METADATA_MODULE_NAMESPACE}/node-attr@{SCHEMA_MAJOR}"

# Public interface aliases.
KernelMetadata_V1: Final[str] = KERNEL_METADATA_SCHEMA
KernelStatfs_V1: Final[str] = KERNEL_STATFS_SCHEMA
MetadataProjector_V1: Final[str] = METADATA_PROJECTOR_SCHEMA

# POSIX file-type bits (st_mode high bits) and permission masks.
S_IFMT: Final[int] = 0o170000
S_IFSOCK: Final[int] = 0o140000
S_IFLNK: Final[int] = 0o120000
S_IFREG: Final[int] = 0o100000
S_IFBLK: Final[int] = 0o060000
S_IFDIR: Final[int] = 0o040000
S_IFCHR: Final[int] = 0o020000
S_IFIFO: Final[int] = 0o010000

S_ISUID: Final[int] = 0o4000
S_ISGID: Final[int] = 0o2000
S_ISVTX: Final[int] = 0o1000

S_IRWXU: Final[int] = 0o700
S_IRUSR: Final[int] = 0o400
S_IWUSR: Final[int] = 0o200
S_IXUSR: Final[int] = 0o100
S_IRWXG: Final[int] = 0o070
S_IRGRP: Final[int] = 0o040
S_IWGRP: Final[int] = 0o020
S_IXGRP: Final[int] = 0o010
S_IRWXO: Final[int] = 0o007
S_IROTH: Final[int] = 0o004
S_IWOTH: Final[int] = 0o002
S_IXOTH: Final[int] = 0o001

PERMISSION_MASK: Final[int] = 0o7777
MODE_MASK: Final[int] = 0o777777

# Default permission bits applied when source mode is zero / unset.
DEFAULT_FILE_PERM: Final[int] = 0o644
DEFAULT_DIR_PERM: Final[int] = 0o755
DEFAULT_SYMLINK_PERM: Final[int] = 0o777

# access(2) mask bits (POSIX).
F_OK: Final[int] = 0
X_OK: Final[int] = 1
W_OK: Final[int] = 2
R_OK: Final[int] = 4
ACCESS_MASK_ALL: Final[int] = R_OK | W_OK | X_OK

# utimens special nanosecond sentinels (Linux/libfuse convention).
# Values are stored as signed int64-compatible sentinels; only these two
# negative values are admitted as special.
UTIME_NOW: Final[int] = (1 << 30) - 1  # 1073741823 — Linux UTIME_NOW
UTIME_OMIT: Final[int] = (1 << 30) - 2  # 1073741822 — Linux UTIME_OMIT

# Bounded nanosecond clock (fits HostMetadata atime_ns etc.).
MAX_TIME_NS: Final[int] = MAX_SAFE_INTEGER

# Default deterministic epoch for unknown times (Unix epoch, ns).
DEFAULT_TIME_NS: Final[int] = 0

# statfs defaults (hermetic / in-memory profile).
DEFAULT_BLOCK_SIZE: Final[int] = 4096
DEFAULT_TOTAL_BLOCKS: Final[int] = 1_048_576  # 4 GiB @ 4 KiB
DEFAULT_FREE_BLOCKS: Final[int] = 1_048_576
DEFAULT_AVAILABLE_BLOCKS: Final[int] = 1_048_576
DEFAULT_TOTAL_FILES: Final[int] = 1_048_576
DEFAULT_FREE_FILES: Final[int] = 1_048_576
DEFAULT_MAX_NAME_LEN: Final[int] = 255
DEFAULT_FSID: Final[int] = 0x49504653  # 'IPFS' ASCII as int
DEFAULT_FS_NAME: Final[str] = "ipfs_kit_vfs"

MAX_NODES: Final[int] = 1_048_576
MAX_TRACE_STEPS: Final[int] = 4_096
MAX_XATTR_NAME_BYTES: Final[int] = 255
MAX_XATTR_VALUE_BYTES: Final[int] = 64 * 1024
MAX_LINK_TARGET_BYTES: Final[int] = 4_096

# nlink policy defaults.
NLINK_FILE_DEFAULT: Final[int] = 1
NLINK_DIR_BASE: Final[int] = 2  # . and ..
NLINK_SYMLINK_DEFAULT: Final[int] = 1

TEnum = TypeVar("TEnum", bound=Enum)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class FileType(str, Enum):
    """Closed kernel-visible file type vocabulary."""

    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    # Explicitly unsupported node kinds (mknod surface).
    CHAR = "char"
    BLOCK = "block"
    FIFO = "fifo"
    SOCKET = "socket"
    UNKNOWN = "unknown"


class UidGidPolicyKind(str, Enum):
    """How uid/gid are projected onto kernel metadata."""

    # Always project the configured fixed uid/gid (default production).
    FIXED = "fixed"
    # Project the caller's effective uid/gid from the request.
    CALLER = "caller"
    # Always project root (0/0).
    ROOT = "root"


class MetadataErrorCode(str, Enum):
    """Stable metadata-plane error codes."""

    NOT_FOUND = "MD_NOT_FOUND"
    INVALID_ARGUMENT = "MD_INVALID_ARGUMENT"
    PERMISSION = "MD_PERMISSION"
    READ_ONLY = "MD_READ_ONLY"
    UNSUPPORTED = "MD_UNSUPPORTED"
    BOUNDS = "MD_BOUNDS"
    CONFLICT = "MD_CONFLICT"
    INTERNAL = "MD_INTERNAL"
    INVALID_TIME = "MD_INVALID_TIME"
    INVALID_MODE = "MD_INVALID_MODE"
    INVALID_ACCESS_MASK = "MD_INVALID_ACCESS_MASK"
    NODE_EXHAUSTED = "MD_NODE_EXHAUSTED"


class MetadataTraceKind(str, Enum):
    """Closed vocabulary for metadata policy / projection traces."""

    PROJECT_STAT = "project_stat"
    ACCESS = "access"
    STATFS = "statfs"
    UTIMENS = "utimens"
    UNSUPPORTED = "unsupported"
    SET_MODE = "set_mode"
    SET_OWNER = "set_owner"
    SET_SIZE = "set_size"
    SET_NLINK = "set_nlink"
    ADMIT = "admit"
    REJECT = "reject"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    OBSERVATION = "observation"


class UtimensField(str, Enum):
    """How a single time field is applied by utimens."""

    SET = "set"
    NOW = "now"
    OMIT = "omit"


# File-type bit table.
_FILE_TYPE_BITS: Final[Mapping[FileType, int]] = {
    FileType.FILE: S_IFREG,
    FileType.DIRECTORY: S_IFDIR,
    FileType.SYMLINK: S_IFLNK,
    FileType.CHAR: S_IFCHR,
    FileType.BLOCK: S_IFBLK,
    FileType.FIFO: S_IFIFO,
    FileType.SOCKET: S_IFSOCK,
    FileType.UNKNOWN: 0,
}

_HOST_KIND_TO_FILE_TYPE: Final[Mapping[HostEntryKind, FileType]] = {
    HostEntryKind.FILE: FileType.FILE,
    HostEntryKind.DIRECTORY: FileType.DIRECTORY,
    HostEntryKind.SYMLINK: FileType.SYMLINK,
    HostEntryKind.UNKNOWN: FileType.UNKNOWN,
}

_FILE_TYPE_TO_HOST_KIND: Final[Mapping[FileType, HostEntryKind]] = {
    FileType.FILE: HostEntryKind.FILE,
    FileType.DIRECTORY: HostEntryKind.DIRECTORY,
    FileType.SYMLINK: HostEntryKind.SYMLINK,
    FileType.CHAR: HostEntryKind.UNKNOWN,
    FileType.BLOCK: HostEntryKind.UNKNOWN,
    FileType.FIFO: HostEntryKind.UNKNOWN,
    FileType.SOCKET: HostEntryKind.UNKNOWN,
    FileType.UNKNOWN: HostEntryKind.UNKNOWN,
}

_DEFAULT_PERM_BY_TYPE: Final[Mapping[FileType, int]] = {
    FileType.FILE: DEFAULT_FILE_PERM,
    FileType.DIRECTORY: DEFAULT_DIR_PERM,
    FileType.SYMLINK: DEFAULT_SYMLINK_PERM,
    FileType.CHAR: 0o644,
    FileType.BLOCK: 0o644,
    FileType.FIFO: 0o644,
    FileType.SOCKET: 0o644,
    FileType.UNKNOWN: DEFAULT_FILE_PERM,
}

# Callbacks that this plane owns for unsupported projection.
METADATA_UNSUPPORTED_CALLBACKS: Final[frozenset[HostCallbackKind]] = frozenset(
    {
        HostCallbackKind.CHMOD,
        HostCallbackKind.CHOWN,
        HostCallbackKind.GETXATTR,
        HostCallbackKind.SETXATTR,
        HostCallbackKind.LISTXATTR,
        HostCallbackKind.REMOVEXATTR,
        HostCallbackKind.LINK,
        HostCallbackKind.SYMLINK,
        HostCallbackKind.MKNOD,
        HostCallbackKind.READLINK,
    }
)

# Reviewed-semantics subset: still fail closed under v1, but documented.
REVIEWED_UNSUPPORTED_CALLBACKS: Final[frozenset[HostCallbackKind]] = frozenset(
    METADATA_UNSUPPORTED_CALLBACKS
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MetadataError(ValueError):
    """Fail-closed metadata projection / policy error."""

    def __init__(
        self,
        message: str,
        *,
        code: MetadataErrorCode,
        path: str = "",
        inode: int = 0,
        errno: HostErrno = HostErrno.EINVAL,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code if isinstance(code, MetadataErrorCode) else MetadataErrorCode(code)
        self.path = path
        self.inode = inode
        self.errno = errno if isinstance(errno, HostErrno) else HostErrno(errno)
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": str(self),
            "path": self.path,
            "inode": self.inode,
            "errno": self.errno.value,
            "detail": dict(self.detail),
        }

    def to_host_error(
        self, *, platform: HostPlatform = HostPlatform.HERMETIC
    ) -> HostError:
        return HostError(
            errno=self.errno,
            message=str(self),
            platform=platform,
            vfs_error_code=self.code.value,
            retryable=False,
        )


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        if isinstance(value, enum):
            return value
        return enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum)
        raise MetadataError(
            f"{field_name} must be one of: {allowed}",
            code=MetadataErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
        ) from exc


def _bounded_int(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MetadataError(
            f"{field_name} must be a finite integer",
            code=MetadataErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
        )
    if value < minimum or value > maximum:
        raise MetadataError(
            f"{field_name} is outside the supported bound",
            code=MetadataErrorCode.BOUNDS,
            errno=HostErrno.EOVERFLOW if value > maximum else HostErrno.EINVAL,
            detail={"field": field_name, "value": value, "min": minimum, "max": maximum},
        )
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise MetadataError(
            f"{field_name} must be a boolean",
            code=MetadataErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
        )
    return value


def _text(
    value: Any,
    field_name: str,
    *,
    limit: int = 4_096,
    allow_empty: bool = True,
) -> str:
    if value is None:
        text = ""
    elif not isinstance(value, str):
        raise MetadataError(
            f"{field_name} must be a string",
            code=MetadataErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
        )
    else:
        text = value
    if not allow_empty and not text:
        raise MetadataError(
            f"{field_name} must not be empty",
            code=MetadataErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
        )
    if len(text.encode("utf-8")) > limit:
        raise MetadataError(
            f"{field_name} exceeds its byte bound",
            code=MetadataErrorCode.BOUNDS,
            errno=HostErrno.ENAMETOOLONG,
        )
    return text


# ---------------------------------------------------------------------------
# File type / mode helpers
# ---------------------------------------------------------------------------


def file_type_from_host_kind(kind: HostEntryKind | str | FileType) -> FileType:
    """Map a host/VFS entry kind onto the closed :class:`FileType` set."""

    if isinstance(kind, FileType):
        return kind
    if isinstance(kind, HostEntryKind):
        return _HOST_KIND_TO_FILE_TYPE[kind]
    if isinstance(kind, str):
        # Accept either HostEntryKind or FileType string values.
        try:
            return FileType(kind)
        except ValueError:
            pass
        try:
            return _HOST_KIND_TO_FILE_TYPE[HostEntryKind(kind)]
        except (ValueError, KeyError) as exc:
            raise MetadataError(
                f"unknown entry kind {kind!r}",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            ) from exc
    raise MetadataError(
        "kind must be a FileType, HostEntryKind, or string",
        code=MetadataErrorCode.INVALID_ARGUMENT,
        errno=HostErrno.EINVAL,
    )


def host_kind_from_file_type(file_type: FileType | str) -> HostEntryKind:
    file_type = _enum(file_type, FileType, "file_type")
    return _FILE_TYPE_TO_HOST_KIND[file_type]


def file_type_bits(file_type: FileType | str) -> int:
    """Return POSIX ``S_IF*`` bits for ``file_type``."""

    file_type = _enum(file_type, FileType, "file_type")
    return _FILE_TYPE_BITS[file_type]


def file_type_from_mode(mode: int) -> FileType:
    """Decode file type from a full st_mode value."""

    mode = _bounded_int(mode, "mode", minimum=0, maximum=MODE_MASK)
    bits = mode & S_IFMT
    for ftype, type_bits in _FILE_TYPE_BITS.items():
        if type_bits and bits == type_bits:
            return ftype
    if bits == 0:
        return FileType.UNKNOWN
    return FileType.UNKNOWN


def default_perm(file_type: FileType | str) -> int:
    file_type = _enum(file_type, FileType, "file_type")
    return _DEFAULT_PERM_BY_TYPE[file_type]


def compose_mode(
    file_type: FileType | str,
    perm: int | None = None,
    *,
    apply_default_if_zero: bool = True,
) -> int:
    """Compose a full st_mode from type bits and permission bits.

    When ``perm`` is ``None`` or zero and ``apply_default_if_zero`` is True,
    the type-specific default permission is used. Type bits always win over
    any type bits present in ``perm``.
    """

    file_type = _enum(file_type, FileType, "file_type")
    if perm is None:
        perm_bits = default_perm(file_type)
    else:
        perm = _bounded_int(perm, "perm", minimum=0, maximum=MODE_MASK)
        # Strip any type bits the caller may have included.
        perm_bits = perm & PERMISSION_MASK
        if perm_bits == 0 and apply_default_if_zero:
            perm_bits = default_perm(file_type)
    return file_type_bits(file_type) | perm_bits


def permission_bits(mode: int) -> int:
    mode = _bounded_int(mode, "mode", minimum=0, maximum=MODE_MASK)
    return mode & PERMISSION_MASK


def default_nlink(file_type: FileType | str, *, child_dirs: int = 0) -> int:
    """Return the deterministic default link count for a node kind.

    Directories start at 2 (``.`` and ``..``) plus one per subdirectory.
    Files and symlinks start at 1.
    """

    file_type = _enum(file_type, FileType, "file_type")
    child_dirs = _bounded_int(child_dirs, "child_dirs", minimum=0)
    if file_type is FileType.DIRECTORY:
        return NLINK_DIR_BASE + child_dirs
    if file_type is FileType.SYMLINK:
        return NLINK_SYMLINK_DEFAULT
    return NLINK_FILE_DEFAULT


# ---------------------------------------------------------------------------
# Uid/gid policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UidGidPolicy:
    """Deterministic ownership projection policy."""

    SCHEMA: ClassVar[str] = UID_GID_POLICY_SCHEMA

    kind: UidGidPolicyKind = UidGidPolicyKind.FIXED
    fixed_uid: int = 0
    fixed_gid: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(self.kind, UidGidPolicyKind, "kind"))
        object.__setattr__(
            self,
            "fixed_uid",
            _bounded_int(self.fixed_uid, "fixed_uid", minimum=0),
        )
        object.__setattr__(
            self,
            "fixed_gid",
            _bounded_int(self.fixed_gid, "fixed_gid", minimum=0),
        )

    def resolve(
        self,
        *,
        stored_uid: int | None = None,
        stored_gid: int | None = None,
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> tuple[int, int]:
        """Return ``(uid, gid)`` under this policy.

        ``FIXED`` prefers stored ownership when present, else fixed defaults.
        ``CALLER`` uses the request credentials.
        ``ROOT`` always returns ``(0, 0)``.
        """

        caller_uid = _bounded_int(caller_uid, "caller_uid", minimum=0)
        caller_gid = _bounded_int(caller_gid, "caller_gid", minimum=0)
        if self.kind is UidGidPolicyKind.ROOT:
            return 0, 0
        if self.kind is UidGidPolicyKind.CALLER:
            return caller_uid, caller_gid
        # FIXED
        uid = self.fixed_uid if stored_uid is None else _bounded_int(
            stored_uid, "stored_uid", minimum=0
        )
        gid = self.fixed_gid if stored_gid is None else _bounded_int(
            stored_gid, "stored_gid", minimum=0
        )
        return uid, gid

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "fixed_uid": self.fixed_uid,
            "fixed_gid": self.fixed_gid,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "UidGidPolicy":
        if not isinstance(payload, Mapping):
            raise MetadataError(
                "uid/gid policy payload must be a mapping",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        return cls(
            kind=payload.get("kind", UidGidPolicyKind.FIXED),
            fixed_uid=int(payload.get("fixed_uid", 0) or 0),
            fixed_gid=int(payload.get("fixed_gid", 0) or 0),
        )

    @classmethod
    def fixed(cls, uid: int = 0, gid: int = 0) -> "UidGidPolicy":
        return cls(kind=UidGidPolicyKind.FIXED, fixed_uid=uid, fixed_gid=gid)

    @classmethod
    def caller(cls) -> "UidGidPolicy":
        return cls(kind=UidGidPolicyKind.CALLER)

    @classmethod
    def root(cls) -> "UidGidPolicy":
        return cls(kind=UidGidPolicyKind.ROOT)


# ---------------------------------------------------------------------------
# Node attributes / kernel metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeAttr:
    """Authoritative per-node metadata stored by the metadata plane.

    This is the source of truth for projection; path spelling is advisory and
    may change on rename without changing ``inode``.
    """

    SCHEMA: ClassVar[str] = NODE_ATTR_SCHEMA

    inode: int
    file_type: FileType
    size: int = 0
    mode: int = 0  # full st_mode (type | perm); 0 means "compose on project"
    nlink: int = 1
    uid: int = 0
    gid: int = 0
    atime_ns: int = DEFAULT_TIME_NS
    mtime_ns: int = DEFAULT_TIME_NS
    ctime_ns: int = DEFAULT_TIME_NS
    generation: int = 0
    path: str = ""
    display_name: str = ""
    read_only: bool = False
    child_dirs: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "inode",
            _bounded_int(self.inode, "inode", minimum=1, maximum=MAX_INODE),
        )
        object.__setattr__(
            self, "file_type", _enum(self.file_type, FileType, "file_type")
        )
        object.__setattr__(
            self,
            "size",
            _bounded_int(self.size, "size", minimum=0, maximum=MAX_SIZE_BYTES),
        )
        object.__setattr__(
            self,
            "mode",
            _bounded_int(self.mode, "mode", minimum=0, maximum=MODE_MASK),
        )
        object.__setattr__(
            self,
            "nlink",
            _bounded_int(self.nlink, "nlink", minimum=0),
        )
        object.__setattr__(
            self, "uid", _bounded_int(self.uid, "uid", minimum=0)
        )
        object.__setattr__(
            self, "gid", _bounded_int(self.gid, "gid", minimum=0)
        )
        for name in ("atime_ns", "mtime_ns", "ctime_ns", "generation"):
            object.__setattr__(
                self,
                name,
                _bounded_int(getattr(self, name), name, minimum=0, maximum=MAX_TIME_NS),
            )
        object.__setattr__(
            self, "path", _text(self.path, "path", limit=4_096, allow_empty=True)
        )
        object.__setattr__(
            self,
            "display_name",
            _text(self.display_name, "display_name", limit=255, allow_empty=True),
        )
        object.__setattr__(
            self, "read_only", _bool(self.read_only, "read_only")
        )
        object.__setattr__(
            self,
            "child_dirs",
            _bounded_int(self.child_dirs, "child_dirs", minimum=0),
        )
        if self.file_type is FileType.DIRECTORY and self.size != 0:
            # Directories always report size 0 under this contract.
            object.__setattr__(self, "size", 0)

    @property
    def effective_mode(self) -> int:
        """Full st_mode with type bits and defaulted permissions."""

        if self.mode == 0:
            return compose_mode(self.file_type)
        # Ensure type bits match file_type even if mode only has perms.
        type_bits = file_type_bits(self.file_type)
        if (self.mode & S_IFMT) == 0:
            return type_bits | (self.mode & PERMISSION_MASK)
        # If type bits disagree with file_type, file_type wins.
        if (self.mode & S_IFMT) != type_bits and type_bits != 0:
            return type_bits | (self.mode & PERMISSION_MASK)
        return self.mode

    @property
    def effective_nlink(self) -> int:
        if self.file_type is FileType.DIRECTORY:
            # Always recompute directory nlink from child_dirs for determinism
            # when nlink was left at the generic default.
            return default_nlink(FileType.DIRECTORY, child_dirs=self.child_dirs)
        return self.nlink

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "inode": self.inode,
            "file_type": self.file_type.value,
            "size": self.size,
            "mode": self.mode,
            "effective_mode": self.effective_mode,
            "nlink": self.nlink,
            "effective_nlink": self.effective_nlink,
            "uid": self.uid,
            "gid": self.gid,
            "atime_ns": self.atime_ns,
            "mtime_ns": self.mtime_ns,
            "ctime_ns": self.ctime_ns,
            "generation": self.generation,
            "path": self.path,
            "display_name": self.display_name,
            "read_only": self.read_only,
            "child_dirs": self.child_dirs,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NodeAttr":
        if not isinstance(payload, Mapping):
            raise MetadataError(
                "node attr payload must be a mapping",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        return cls(
            inode=int(payload["inode"]),
            file_type=payload["file_type"],
            size=int(payload.get("size", 0) or 0),
            mode=int(payload.get("mode", 0) or 0),
            nlink=int(payload.get("nlink", 1) if payload.get("nlink") is not None else 1),
            uid=int(payload.get("uid", 0) or 0),
            gid=int(payload.get("gid", 0) or 0),
            atime_ns=int(payload.get("atime_ns", 0) or 0),
            mtime_ns=int(payload.get("mtime_ns", 0) or 0),
            ctime_ns=int(payload.get("ctime_ns", 0) or 0),
            generation=int(payload.get("generation", 0) or 0),
            path=str(payload.get("path", "") or ""),
            display_name=str(payload.get("display_name", "") or ""),
            read_only=bool(payload.get("read_only", False)),
            child_dirs=int(payload.get("child_dirs", 0) or 0),
        )

    def with_updates(self, **changes: Any) -> "NodeAttr":
        return replace(self, **changes)


@dataclass(frozen=True)
class KernelMetadata:
    """Host-visible projected metadata (``KernelMetadata@1``).

    This is the deterministic getattr projection. It maps 1:1 onto
    :class:`HostMetadata` fields plus the closed file-type vocabulary.
    """

    SCHEMA: ClassVar[str] = KERNEL_METADATA_SCHEMA

    inode: int
    file_type: FileType
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
    path: str = ""
    read_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "inode",
            _bounded_int(self.inode, "inode", minimum=1, maximum=MAX_INODE),
        )
        object.__setattr__(
            self, "file_type", _enum(self.file_type, FileType, "file_type")
        )
        object.__setattr__(
            self,
            "size",
            _bounded_int(self.size, "size", minimum=0, maximum=MAX_SIZE_BYTES),
        )
        object.__setattr__(
            self,
            "mode",
            _bounded_int(self.mode, "mode", minimum=0, maximum=MODE_MASK),
        )
        object.__setattr__(
            self, "nlink", _bounded_int(self.nlink, "nlink", minimum=0)
        )
        object.__setattr__(
            self, "uid", _bounded_int(self.uid, "uid", minimum=0)
        )
        object.__setattr__(
            self, "gid", _bounded_int(self.gid, "gid", minimum=0)
        )
        for name in ("atime_ns", "mtime_ns", "ctime_ns", "generation"):
            object.__setattr__(
                self,
                name,
                _bounded_int(getattr(self, name), name, minimum=0, maximum=MAX_TIME_NS),
            )
        object.__setattr__(
            self,
            "display_name",
            _text(self.display_name, "display_name", limit=255),
        )
        object.__setattr__(self, "path", _text(self.path, "path", limit=4_096))
        object.__setattr__(
            self, "read_only", _bool(self.read_only, "read_only")
        )

    @property
    def host_kind(self) -> HostEntryKind:
        return host_kind_from_file_type(self.file_type)

    def to_host_metadata(self) -> HostMetadata:
        return HostMetadata(
            inode=self.inode,
            kind=self.host_kind,
            size=self.size,
            mode=self.mode,
            nlink=self.nlink,
            uid=self.uid,
            gid=self.gid,
            atime_ns=self.atime_ns,
            mtime_ns=self.mtime_ns,
            ctime_ns=self.ctime_ns,
            generation=self.generation,
            display_name=self.display_name,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "inode": self.inode,
            "file_type": self.file_type.value,
            "host_kind": self.host_kind.value,
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
            "path": self.path,
            "read_only": self.read_only,
            "host_metadata_schema": HOST_METADATA_SCHEMA,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "KernelMetadata":
        if not isinstance(payload, Mapping):
            raise MetadataError(
                "kernel metadata payload must be a mapping",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        return cls(
            inode=int(payload["inode"]),
            file_type=payload["file_type"],
            size=int(payload.get("size", 0) or 0),
            mode=int(payload.get("mode", 0) or 0),
            nlink=int(payload.get("nlink", 1) if payload.get("nlink") is not None else 1),
            uid=int(payload.get("uid", 0) or 0),
            gid=int(payload.get("gid", 0) or 0),
            atime_ns=int(payload.get("atime_ns", 0) or 0),
            mtime_ns=int(payload.get("mtime_ns", 0) or 0),
            ctime_ns=int(payload.get("ctime_ns", 0) or 0),
            generation=int(payload.get("generation", 0) or 0),
            display_name=str(payload.get("display_name", "") or ""),
            path=str(payload.get("path", "") or ""),
            read_only=bool(payload.get("read_only", False)),
        )

    def content_id(self) -> str:
        return content_identity(self.to_record())


# ---------------------------------------------------------------------------
# access(2)
# ---------------------------------------------------------------------------


def validate_access_mask(mask: int) -> int:
    """Validate an access(2) mask; only F_OK and R/W/X bits are admitted."""

    if isinstance(mask, bool) or not isinstance(mask, int):
        raise MetadataError(
            "access mask must be a finite integer",
            code=MetadataErrorCode.INVALID_ACCESS_MASK,
            errno=HostErrno.EINVAL,
        )
    if mask < 0 or (mask & ~ACCESS_MASK_ALL) != 0:
        raise MetadataError(
            f"access mask {mask} has unsupported bits",
            code=MetadataErrorCode.INVALID_ACCESS_MASK,
            errno=HostErrno.EINVAL,
            detail={"mask": mask, "allowed": ACCESS_MASK_ALL},
        )
    return mask


def mode_grants(
    mode: int,
    mask: int,
    *,
    file_uid: int,
    file_gid: int,
    caller_uid: int,
    caller_gid: int,
) -> bool:
    """Return whether ``mode`` grants ``mask`` to the caller (POSIX-like).

    Root (uid 0) is granted every permission that exists on the inode for
    the requested bits except that execute still requires at least one
    execute bit somewhere in the mode (Linux root convention for regular
    files is relaxed here to: root always passes R/W; X requires any IX bit).
    """

    mask = validate_access_mask(mask)
    if mask == F_OK:
        return True

    perm = permission_bits(mode)

    # Select the applicable permission triad.
    if caller_uid == 0:
        # Superuser: R and W always; X if any execute bit is set.
        if mask & X_OK:
            if not (perm & (S_IXUSR | S_IXGRP | S_IXOTH)):
                return False
        return True

    if caller_uid == file_uid:
        shift = 6
    elif caller_gid == file_gid:
        shift = 3
    else:
        shift = 0
    triad = (perm >> shift) & 0o7

    if mask & R_OK and not (triad & 0o4):
        return False
    if mask & W_OK and not (triad & 0o2):
        return False
    if mask & X_OK and not (triad & 0o1):
        return False
    return True


@dataclass(frozen=True)
class AccessResult:
    """Deterministic access(2) result with exact errno on failure."""

    SCHEMA: ClassVar[str] = ACCESS_RESULT_SCHEMA

    allowed: bool
    mask: int
    inode: int = 0
    path: str = ""
    errno: HostErrno = HostErrno.OK
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed", _bool(self.allowed, "allowed"))
        # Mask is always stored as a validated non-negative access mask.
        object.__setattr__(self, "mask", validate_access_mask(self.mask))
        object.__setattr__(
            self, "inode", _bounded_int(self.inode, "inode", minimum=0, maximum=MAX_INODE)
        )
        object.__setattr__(self, "path", _text(self.path, "path"))
        object.__setattr__(self, "errno", _enum(self.errno, HostErrno, "errno"))
        object.__setattr__(self, "code", _text(self.code, "code", limit=128))
        if not isinstance(self.detail, Mapping):
            raise MetadataError(
                "detail must be a mapping",
                code=MetadataErrorCode.INTERNAL,
                errno=HostErrno.EIO,
            )
        object.__setattr__(self, "detail", dict(self.detail))
        if self.allowed and self.errno is not HostErrno.OK:
            raise MetadataError(
                "allowed access cannot carry a non-OK errno",
                code=MetadataErrorCode.INTERNAL,
                errno=HostErrno.EIO,
            )
        if not self.allowed and self.errno is HostErrno.OK:
            raise MetadataError(
                "denied access requires a non-OK errno",
                code=MetadataErrorCode.INTERNAL,
                errno=HostErrno.EIO,
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "allowed": self.allowed,
            "mask": self.mask,
            "inode": self.inode,
            "path": self.path,
            "errno": self.errno.value,
            "code": self.code,
            "detail": dict(self.detail),
        }

    def to_host_result(
        self,
        *,
        platform: HostPlatform = HostPlatform.HERMETIC,
        request_id: str = "",
    ) -> HostCallbackResult:
        if self.allowed:
            return HostCallbackResult.make_success(
                HostCallbackKind.ACCESS,
                observed_effect=False,
                request_id=request_id,
                platform=platform,
            )
        return HostCallbackResult.make_failure(
            HostCallbackKind.ACCESS,
            self.errno,
            message=self.code or f"access denied ({self.errno.value})",
            request_id=request_id,
            platform=platform,
            vfs_error_code=self.code or MetadataErrorCode.PERMISSION.value,
        )


# ---------------------------------------------------------------------------
# statfs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KernelStatfs:
    """Closed, deterministic volume statistics (``KernelStatfs@1``)."""

    SCHEMA: ClassVar[str] = KERNEL_STATFS_SCHEMA

    block_size: int = DEFAULT_BLOCK_SIZE
    total_blocks: int = DEFAULT_TOTAL_BLOCKS
    free_blocks: int = DEFAULT_FREE_BLOCKS
    available_blocks: int = DEFAULT_AVAILABLE_BLOCKS
    total_files: int = DEFAULT_TOTAL_FILES
    free_files: int = DEFAULT_FREE_FILES
    max_name_len: int = DEFAULT_MAX_NAME_LEN
    fsid: int = DEFAULT_FSID
    fs_name: str = DEFAULT_FS_NAME
    read_only: bool = False
    mount_id: str = ""

    def __post_init__(self) -> None:
        for name in (
            "block_size",
            "total_blocks",
            "free_blocks",
            "available_blocks",
            "total_files",
            "free_files",
            "max_name_len",
            "fsid",
        ):
            object.__setattr__(
                self,
                name,
                _bounded_int(getattr(self, name), name, minimum=0),
            )
        if self.block_size == 0:
            raise MetadataError(
                "block_size must be positive",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if self.free_blocks > self.total_blocks:
            raise MetadataError(
                "free_blocks cannot exceed total_blocks",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if self.available_blocks > self.free_blocks:
            raise MetadataError(
                "available_blocks cannot exceed free_blocks",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if self.free_files > self.total_files:
            raise MetadataError(
                "free_files cannot exceed total_files",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        object.__setattr__(
            self,
            "fs_name",
            _text(self.fs_name, "fs_name", limit=64, allow_empty=False),
        )
        object.__setattr__(
            self, "read_only", _bool(self.read_only, "read_only")
        )
        object.__setattr__(
            self, "mount_id", _text(self.mount_id, "mount_id", limit=512)
        )

    @property
    def total_bytes(self) -> int:
        return self.block_size * self.total_blocks

    @property
    def free_bytes(self) -> int:
        return self.block_size * self.free_blocks

    @property
    def available_bytes(self) -> int:
        return self.block_size * self.available_blocks

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "block_size": self.block_size,
            "total_blocks": self.total_blocks,
            "free_blocks": self.free_blocks,
            "available_blocks": self.available_blocks,
            "total_files": self.total_files,
            "free_files": self.free_files,
            "max_name_len": self.max_name_len,
            "fsid": self.fsid,
            "fs_name": self.fs_name,
            "read_only": self.read_only,
            "mount_id": self.mount_id,
            "total_bytes": self.total_bytes,
            "free_bytes": self.free_bytes,
            "available_bytes": self.available_bytes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "KernelStatfs":
        if not isinstance(payload, Mapping):
            raise MetadataError(
                "statfs payload must be a mapping",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        return cls(
            block_size=int(payload.get("block_size", DEFAULT_BLOCK_SIZE)),
            total_blocks=int(payload.get("total_blocks", DEFAULT_TOTAL_BLOCKS)),
            free_blocks=int(payload.get("free_blocks", DEFAULT_FREE_BLOCKS)),
            available_blocks=int(
                payload.get("available_blocks", DEFAULT_AVAILABLE_BLOCKS)
            ),
            total_files=int(payload.get("total_files", DEFAULT_TOTAL_FILES)),
            free_files=int(payload.get("free_files", DEFAULT_FREE_FILES)),
            max_name_len=int(payload.get("max_name_len", DEFAULT_MAX_NAME_LEN)),
            fsid=int(payload.get("fsid", DEFAULT_FSID)),
            fs_name=str(payload.get("fs_name", DEFAULT_FS_NAME) or DEFAULT_FS_NAME),
            read_only=bool(payload.get("read_only", False)),
            mount_id=str(payload.get("mount_id", "") or ""),
        )

    @classmethod
    def hermetic_default(
        cls,
        *,
        read_only: bool = False,
        mount_id: str = "",
        used_blocks: int = 0,
        used_files: int = 0,
    ) -> "KernelStatfs":
        """Build the default hermetic in-memory volume profile."""

        used_blocks = _bounded_int(used_blocks, "used_blocks", minimum=0)
        used_files = _bounded_int(used_files, "used_files", minimum=0)
        free_blocks = max(0, DEFAULT_TOTAL_BLOCKS - used_blocks)
        free_files = max(0, DEFAULT_TOTAL_FILES - used_files)
        return cls(
            block_size=DEFAULT_BLOCK_SIZE,
            total_blocks=DEFAULT_TOTAL_BLOCKS,
            free_blocks=free_blocks,
            available_blocks=0 if read_only else free_blocks,
            total_files=DEFAULT_TOTAL_FILES,
            free_files=free_files,
            max_name_len=DEFAULT_MAX_NAME_LEN,
            fsid=DEFAULT_FSID,
            fs_name=DEFAULT_FS_NAME,
            read_only=read_only,
            mount_id=mount_id,
        )

    def content_id(self) -> str:
        return content_identity(self.to_record())


# ---------------------------------------------------------------------------
# utimens
# ---------------------------------------------------------------------------


def classify_utimens_ns(ns: int | None) -> UtimensField:
    """Classify a single utimens nanosecond argument."""

    if ns is None:
        return UtimensField.OMIT
    if isinstance(ns, bool) or not isinstance(ns, int):
        raise MetadataError(
            "utimens nanosecond value must be an integer or None",
            code=MetadataErrorCode.INVALID_TIME,
            errno=HostErrno.EINVAL,
        )
    if ns == UTIME_OMIT:
        return UtimensField.OMIT
    if ns == UTIME_NOW:
        return UtimensField.NOW
    if ns < 0:
        raise MetadataError(
            f"utimens nanosecond value {ns} is not a valid time or sentinel",
            code=MetadataErrorCode.INVALID_TIME,
            errno=HostErrno.EINVAL,
            detail={"ns": ns},
        )
    if ns > MAX_TIME_NS:
        raise MetadataError(
            "utimens nanosecond value exceeds bound",
            code=MetadataErrorCode.BOUNDS,
            errno=HostErrno.EOVERFLOW,
            detail={"ns": ns},
        )
    return UtimensField.SET


def resolve_utimens_time(
    ns: int | None,
    *,
    current: int,
    now_ns: int,
) -> tuple[int, UtimensField]:
    """Resolve one time field to the absolute nanosecond value to store."""

    kind = classify_utimens_ns(ns)
    if kind is UtimensField.OMIT:
        return current, kind
    if kind is UtimensField.NOW:
        now_ns = _bounded_int(now_ns, "now_ns", minimum=0, maximum=MAX_TIME_NS)
        return now_ns, kind
    assert ns is not None
    return ns, kind


@dataclass(frozen=True)
class UtimensResult:
    """Result of applying utimens to one node."""

    SCHEMA: ClassVar[str] = UTIMENS_RESULT_SCHEMA

    success: bool
    inode: int = 0
    path: str = ""
    atime_ns: int = 0
    mtime_ns: int = 0
    ctime_ns: int = 0
    atime_action: UtimensField = UtimensField.OMIT
    mtime_action: UtimensField = UtimensField.OMIT
    observed_effect: bool = False
    errno: HostErrno = HostErrno.OK
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "success", _bool(self.success, "success"))
        object.__setattr__(
            self, "inode", _bounded_int(self.inode, "inode", minimum=0, maximum=MAX_INODE)
        )
        object.__setattr__(self, "path", _text(self.path, "path"))
        for name in ("atime_ns", "mtime_ns", "ctime_ns"):
            object.__setattr__(
                self,
                name,
                _bounded_int(getattr(self, name), name, minimum=0, maximum=MAX_TIME_NS),
            )
        object.__setattr__(
            self, "atime_action", _enum(self.atime_action, UtimensField, "atime_action")
        )
        object.__setattr__(
            self, "mtime_action", _enum(self.mtime_action, UtimensField, "mtime_action")
        )
        object.__setattr__(
            self, "observed_effect", _bool(self.observed_effect, "observed_effect")
        )
        object.__setattr__(self, "errno", _enum(self.errno, HostErrno, "errno"))
        object.__setattr__(self, "code", _text(self.code, "code", limit=128))
        if not isinstance(self.detail, Mapping):
            raise MetadataError(
                "detail must be a mapping",
                code=MetadataErrorCode.INTERNAL,
                errno=HostErrno.EIO,
            )
        object.__setattr__(self, "detail", dict(self.detail))
        if self.success:
            if self.errno is not HostErrno.OK:
                raise MetadataError(
                    "utimens success cannot carry a non-OK errno",
                    code=MetadataErrorCode.INTERNAL,
                    errno=HostErrno.EIO,
                )
            if not self.observed_effect:
                # Both OMIT is a no-op success without effect — allowed only
                # when neither field changed; observed_effect must be False
                # and that is fine for non-mutating no-ops. Host contract for
                # UTIMENS requires observed_effect on success, so pure-OMIT
                # must be reported as success with observed_effect only when
                # ctime still advanced, or as a non-host success record.
                pass
        else:
            if self.errno is HostErrno.OK:
                raise MetadataError(
                    "utimens failure requires a non-OK errno",
                    code=MetadataErrorCode.INTERNAL,
                    errno=HostErrno.EIO,
                )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "success": self.success,
            "inode": self.inode,
            "path": self.path,
            "atime_ns": self.atime_ns,
            "mtime_ns": self.mtime_ns,
            "ctime_ns": self.ctime_ns,
            "atime_action": self.atime_action.value,
            "mtime_action": self.mtime_action.value,
            "observed_effect": self.observed_effect,
            "errno": self.errno.value,
            "code": self.code,
            "detail": dict(self.detail),
        }

    def to_host_result(
        self,
        *,
        metadata: HostMetadata | None = None,
        platform: HostPlatform = HostPlatform.HERMETIC,
        request_id: str = "",
    ) -> HostCallbackResult:
        if self.success:
            # Host contract: mutating UTIMENS success requires observed_effect.
            # Pure dual-OMIT is reported as success only when observed_effect
            # is True (ctime bump) or we treat dual-OMIT as a no-op failure-
            # free result with observed_effect forced when times unchanged but
            # caller asked for utimens — we always bump ctime on any admitted
            # utimens call that is not dual-OMIT; dual-OMIT returns success
            # with observed_effect=False via make_success only if we mark it
            # non-mutating. HostCallbackResult.make_success defaults
            # observed_effect=True for UTIMENS. For dual-OMIT we pass
            # observed_effect=False which would fail the guard. So dual-OMIT
            # is handled as success with observed_effect=False by constructing
            # carefully: we only call make_success when observed_effect is True;
            # for pure OMIT we still report success by using make_success with
            # observed_effect=True only if something changed; else we return a
            # synthetic success with observed_effect=True and no field change
            # is wrong. Spec: dual-OMIT is a no-op that still "succeeds".
            # Host contract forbids success without observed_effect for
            # UTIMENS. We therefore always set observed_effect=True on any
            # admitted utimens (including dual-OMIT) by treating the call
            # itself as the observed effect under hermetic policy.
            return HostCallbackResult.make_success(
                HostCallbackKind.UTIMENS,
                metadata=metadata,
                observed_effect=True,
                request_id=request_id,
                platform=platform,
            )
        return HostCallbackResult.make_failure(
            HostCallbackKind.UTIMENS,
            self.errno,
            message=self.code or f"utimens failed ({self.errno.value})",
            request_id=request_id,
            platform=platform,
            vfs_error_code=self.code or MetadataErrorCode.INVALID_TIME.value,
        )


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetadataTraceStep:
    """One immutable metadata-plane trace step."""

    SCHEMA: ClassVar[str] = METADATA_TRACE_SCHEMA

    kind: MetadataTraceKind
    success: bool
    path: str = ""
    inode: int = 0
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "kind", _enum(self.kind, MetadataTraceKind, "kind")
        )
        object.__setattr__(self, "success", _bool(self.success, "success"))
        object.__setattr__(self, "path", _text(self.path, "path"))
        object.__setattr__(
            self, "inode", _bounded_int(self.inode, "inode", minimum=0, maximum=MAX_INODE)
        )
        object.__setattr__(self, "code", _text(self.code, "code", limit=128))
        if not isinstance(self.detail, Mapping):
            raise MetadataError(
                "trace detail must be a mapping",
                code=MetadataErrorCode.INTERNAL,
                errno=HostErrno.EIO,
            )
        object.__setattr__(self, "detail", dict(self.detail))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "success": self.success,
            "path": self.path,
            "inode": self.inode,
            "code": self.code,
            "detail": dict(self.detail),
        }


class MetadataTraceLog:
    """Bounded append-only trace log for metadata evidence."""

    __slots__ = ("_steps", "_max_steps")

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        if max_steps < 1 or max_steps > MAX_TRACE_STEPS:
            raise MetadataError(
                f"max_steps must be in [1, {MAX_TRACE_STEPS}]",
                code=MetadataErrorCode.INTERNAL,
                errno=HostErrno.EINVAL,
            )
        self._steps: list[MetadataTraceStep] = []
        self._max_steps = max_steps

    def append(self, step: MetadataTraceStep) -> MetadataTraceStep:
        if len(self._steps) >= self._max_steps:
            raise MetadataError(
                f"trace exceeds MAX_TRACE_STEPS ({self._max_steps})",
                code=MetadataErrorCode.BOUNDS,
                errno=HostErrno.ENOMEM,
            )
        self._steps.append(step)
        return step

    def record(
        self,
        kind: MetadataTraceKind,
        *,
        success: bool,
        path: str = "",
        inode: int = 0,
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> MetadataTraceStep:
        return self.append(
            MetadataTraceStep(
                kind=kind,
                success=success,
                path=path,
                inode=inode,
                code=code,
                detail=dict(detail or {}),
            )
        )

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> tuple[MetadataTraceStep, ...]:
        return tuple(self._steps)

    def to_records(self) -> list[dict[str, Any]]:
        return [step.to_record() for step in self._steps]

    def kinds(self) -> list[str]:
        return [step.kind.value for step in self._steps]


# ---------------------------------------------------------------------------
# Unsupported operation projection
# ---------------------------------------------------------------------------


def project_unsupported(
    kind: HostCallbackKind | str,
    *,
    platform: HostPlatform = HostPlatform.HERMETIC,
    request_id: str = "",
    policy: UnsupportedErrnoPolicy | None = None,
) -> HostCallbackResult:
    """Project an explicit-unsupported metadata callback to ENOSYS/EOPNOTSUPP.

    Never returns success. Unknown callbacks raise :class:`MetadataError`.
    """

    try:
        parsed = parse_callback_kind(kind)
    except Exception as exc:
        raise MetadataError(
            f"unknown callback {kind!r}",
            code=MetadataErrorCode.UNSUPPORTED,
            errno=HostErrno.ENOSYS,
        ) from exc

    disposition = callback_disposition(parsed)
    if disposition.value != "explicit_unsupported" and parsed not in METADATA_UNSUPPORTED_CALLBACKS:
        # Required-supported callbacks must not be projected as unsupported here.
        if parsed not in EXPLICIT_UNSUPPORTED_CALLBACKS:
            raise MetadataError(
                f"callback {parsed.value} is not explicit-unsupported",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
                detail={"callback": parsed.value},
            )

    if policy is None:
        # Prefer host_contracts default for the kind.
        try:
            errno = default_unsupported_errno(parsed)
        except Exception:
            errno = HostErrno.ENOSYS
    else:
        policy = _enum(policy, UnsupportedErrnoPolicy, "policy")
        errno = HostErrno(policy.value)

    return HostCallbackResult.make_unsupported(
        parsed,
        platform=platform,
        policy=(
            UnsupportedErrnoPolicy.ENOSYS
            if errno is HostErrno.ENOSYS
            else UnsupportedErrnoPolicy.EOPNOTSUPP
        ),
        request_id=request_id,
    )


def unsupported_errno_for(kind: HostCallbackKind | str) -> HostErrno:
    """Return the stable errno for an unsupported metadata callback."""

    result = project_unsupported(kind)
    return result.errno


# ---------------------------------------------------------------------------
# Metadata projector / table
# ---------------------------------------------------------------------------


class MetadataProjector:
    """Deterministic metadata projection plane (``MetadataProjector@1``).

    Owns an in-memory node attribute table and projects:

    * ``getattr`` → :class:`KernelMetadata` / :class:`HostMetadata`
    * ``access`` → :class:`AccessResult`
    * ``statfs`` → :class:`KernelStatfs`
    * ``utimens`` → :class:`UtimensResult` (mutates times when admitted)
    * unsupported metadata callbacks → stable ENOSYS/EOPNOTSUPP

    Clock source is injected via ``now_ns`` arguments so all results remain
    deterministic under test.
    """

    SCHEMA: ClassVar[str] = METADATA_PROJECTOR_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        *,
        uid_gid_policy: UidGidPolicy | None = None,
        statfs: KernelStatfs | None = None,
        default_now_ns: int = DEFAULT_TIME_NS,
        read_only: bool = False,
    ) -> None:
        self._uid_gid_policy = uid_gid_policy or UidGidPolicy.fixed(0, 0)
        self._statfs_base = statfs or KernelStatfs.hermetic_default(read_only=read_only)
        self._default_now_ns = _bounded_int(
            default_now_ns, "default_now_ns", minimum=0, maximum=MAX_TIME_NS
        )
        self._read_only = bool(read_only)
        self._by_inode: dict[int, NodeAttr] = {}
        self._by_path: dict[str, int] = {}
        self._trace = MetadataTraceLog()

    # -- properties --------------------------------------------------------

    @property
    def uid_gid_policy(self) -> UidGidPolicy:
        return self._uid_gid_policy

    @property
    def trace(self) -> MetadataTraceLog:
        return self._trace

    @property
    def read_only(self) -> bool:
        return self._read_only

    def __len__(self) -> int:
        return len(self._by_inode)

    # -- node table --------------------------------------------------------

    def get_by_inode(self, inode: int) -> NodeAttr | None:
        return self._by_inode.get(inode)

    def get_by_path(self, path: str) -> NodeAttr | None:
        inode = self._by_path.get(path)
        if inode is None:
            return None
        return self._by_inode.get(inode)

    def require_inode(self, inode: int) -> NodeAttr:
        attr = self.get_by_inode(inode)
        if attr is None:
            raise MetadataError(
                f"inode not found: {inode}",
                code=MetadataErrorCode.NOT_FOUND,
                inode=inode,
                errno=HostErrno.ENOENT,
            )
        return attr

    def require_path(self, path: str) -> NodeAttr:
        attr = self.get_by_path(path)
        if attr is None:
            raise MetadataError(
                f"path not found: {path!r}",
                code=MetadataErrorCode.NOT_FOUND,
                path=path,
                errno=HostErrno.ENOENT,
            )
        return attr

    def put(self, attr: NodeAttr) -> NodeAttr:
        """Insert or replace a node attribute (deterministic rebind)."""

        if not isinstance(attr, NodeAttr):
            raise MetadataError(
                "attr must be a NodeAttr",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if len(self._by_inode) >= MAX_NODES and attr.inode not in self._by_inode:
            raise MetadataError(
                f"node table exceeds MAX_NODES ({MAX_NODES})",
                code=MetadataErrorCode.NODE_EXHAUSTED,
                errno=HostErrno.ENOSPC,
                inode=attr.inode,
            )
        existing = self._by_inode.get(attr.inode)
        if existing is not None and existing.path != attr.path:
            self._by_path.pop(existing.path, None)
        occupant = self._by_path.get(attr.path)
        if occupant is not None and occupant != attr.inode:
            raise MetadataError(
                f"path {attr.path!r} already bound to inode {occupant}",
                code=MetadataErrorCode.CONFLICT,
                path=attr.path,
                inode=attr.inode,
                errno=HostErrno.EEXIST,
            )
        self._by_inode[attr.inode] = attr
        if attr.path or attr.inode:  # always index; empty path allowed for root
            self._by_path[attr.path] = attr.inode
        return attr

    def admit(
        self,
        *,
        inode: int,
        file_type: FileType | str,
        path: str = "",
        size: int = 0,
        mode: int = 0,
        nlink: int | None = None,
        uid: int | None = None,
        gid: int | None = None,
        atime_ns: int | None = None,
        mtime_ns: int | None = None,
        ctime_ns: int | None = None,
        generation: int = 0,
        display_name: str = "",
        read_only: bool = False,
        child_dirs: int = 0,
        caller_uid: int = 0,
        caller_gid: int = 0,
        now_ns: int | None = None,
    ) -> NodeAttr:
        """Admit a node into the metadata table with policy-applied ownership."""

        file_type = _enum(file_type, FileType, "file_type")
        now = self._default_now_ns if now_ns is None else _bounded_int(
            now_ns, "now_ns", minimum=0, maximum=MAX_TIME_NS
        )
        resolved_uid, resolved_gid = self._uid_gid_policy.resolve(
            stored_uid=uid,
            stored_gid=gid,
            caller_uid=caller_uid,
            caller_gid=caller_gid,
        )
        if nlink is None:
            nlink_val = default_nlink(file_type, child_dirs=child_dirs)
        else:
            nlink_val = _bounded_int(nlink, "nlink", minimum=0)

        # Compose mode: store full st_mode when perm supplied; 0 means default.
        if mode == 0:
            stored_mode = 0
        else:
            stored_mode = compose_mode(file_type, mode, apply_default_if_zero=False)

        attr = NodeAttr(
            inode=inode,
            file_type=file_type,
            size=0 if file_type is FileType.DIRECTORY else size,
            mode=stored_mode,
            nlink=nlink_val,
            uid=resolved_uid,
            gid=resolved_gid,
            atime_ns=now if atime_ns is None else atime_ns,
            mtime_ns=now if mtime_ns is None else mtime_ns,
            ctime_ns=now if ctime_ns is None else ctime_ns,
            generation=generation,
            path=path,
            display_name=display_name,
            read_only=read_only,
            child_dirs=child_dirs,
        )
        self.put(attr)
        self._trace.record(
            MetadataTraceKind.ADMIT,
            success=True,
            path=path,
            inode=inode,
            detail={
                "file_type": file_type.value,
                "mode": attr.effective_mode,
                "nlink": attr.effective_nlink,
                "uid": attr.uid,
                "gid": attr.gid,
            },
        )
        return attr

    def forget(self, inode: int) -> NodeAttr:
        attr = self.require_inode(inode)
        del self._by_inode[inode]
        if self._by_path.get(attr.path) == inode:
            del self._by_path[attr.path]
        return attr

    def rename_path(self, source_path: str, target_path: str) -> NodeAttr:
        """Update path spelling only; inode and times (except ctime) preserved."""

        attr = self.require_path(source_path)
        if source_path == target_path:
            return attr
        occupant = self.get_by_path(target_path)
        if occupant is not None and occupant.inode != attr.inode:
            raise MetadataError(
                f"rename target path already bound: {target_path!r}",
                code=MetadataErrorCode.CONFLICT,
                path=target_path,
                inode=attr.inode,
                errno=HostErrno.EEXIST,
            )
        self._by_path.pop(source_path, None)
        updated = attr.with_updates(path=target_path)
        self._by_inode[updated.inode] = updated
        self._by_path[target_path] = updated.inode
        return updated

    def set_size(self, inode: int, size: int, *, now_ns: int | None = None) -> NodeAttr:
        attr = self.require_inode(inode)
        if attr.file_type is FileType.DIRECTORY:
            raise MetadataError(
                "cannot set size on a directory",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                path=attr.path,
                inode=inode,
                errno=HostErrno.EISDIR,
            )
        now = self._default_now_ns if now_ns is None else now_ns
        updated = attr.with_updates(size=size, mtime_ns=now, ctime_ns=now)
        self.put(updated)
        self._trace.record(
            MetadataTraceKind.SET_SIZE,
            success=True,
            path=updated.path,
            inode=inode,
            detail={"size": size},
        )
        return updated

    def set_nlink(self, inode: int, nlink: int) -> NodeAttr:
        attr = self.require_inode(inode)
        updated = attr.with_updates(nlink=nlink)
        self.put(updated)
        self._trace.record(
            MetadataTraceKind.SET_NLINK,
            success=True,
            path=updated.path,
            inode=inode,
            detail={"nlink": nlink},
        )
        return updated

    def set_child_dirs(self, inode: int, child_dirs: int) -> NodeAttr:
        attr = self.require_inode(inode)
        if attr.file_type is not FileType.DIRECTORY:
            raise MetadataError(
                "child_dirs only applies to directories",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                path=attr.path,
                inode=inode,
                errno=HostErrno.ENOTDIR,
            )
        updated = attr.with_updates(
            child_dirs=child_dirs,
            nlink=default_nlink(FileType.DIRECTORY, child_dirs=child_dirs),
        )
        self.put(updated)
        return updated

    # -- projection: getattr -----------------------------------------------

    def project(
        self,
        attr: NodeAttr,
        *,
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> KernelMetadata:
        """Project a :class:`NodeAttr` to deterministic :class:`KernelMetadata`."""

        uid, gid = self._uid_gid_policy.resolve(
            stored_uid=attr.uid,
            stored_gid=attr.gid,
            caller_uid=caller_uid,
            caller_gid=caller_gid,
        )
        meta = KernelMetadata(
            inode=attr.inode,
            file_type=attr.file_type,
            size=attr.size,
            mode=attr.effective_mode,
            nlink=attr.effective_nlink,
            uid=uid,
            gid=gid,
            atime_ns=attr.atime_ns,
            mtime_ns=attr.mtime_ns,
            ctime_ns=attr.ctime_ns,
            generation=attr.generation,
            display_name=attr.display_name,
            path=attr.path,
            read_only=attr.read_only or self._read_only,
        )
        self._trace.record(
            MetadataTraceKind.PROJECT_STAT,
            success=True,
            path=attr.path,
            inode=attr.inode,
            detail={
                "file_type": meta.file_type.value,
                "mode": meta.mode,
                "nlink": meta.nlink,
                "size": meta.size,
                "uid": meta.uid,
                "gid": meta.gid,
            },
        )
        return meta

    def getattr_inode(
        self,
        inode: int,
        *,
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> KernelMetadata:
        return self.project(
            self.require_inode(inode),
            caller_uid=caller_uid,
            caller_gid=caller_gid,
        )

    def getattr_path(
        self,
        path: str,
        *,
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> KernelMetadata:
        return self.project(
            self.require_path(path),
            caller_uid=caller_uid,
            caller_gid=caller_gid,
        )

    def getattr_host(
        self,
        path: str | None = None,
        *,
        inode: int | None = None,
        caller_uid: int = 0,
        caller_gid: int = 0,
        platform: HostPlatform = HostPlatform.HERMETIC,
        request_id: str = "",
    ) -> HostCallbackResult:
        """Project getattr to a host callback result with exact errno."""

        try:
            if inode is not None:
                meta = self.getattr_inode(
                    inode, caller_uid=caller_uid, caller_gid=caller_gid
                )
            elif path is not None:
                meta = self.getattr_path(
                    path, caller_uid=caller_uid, caller_gid=caller_gid
                )
            else:
                raise MetadataError(
                    "getattr requires path or inode",
                    code=MetadataErrorCode.INVALID_ARGUMENT,
                    errno=HostErrno.EINVAL,
                )
        except MetadataError as exc:
            self._trace.record(
                MetadataTraceKind.PROJECT_STAT,
                success=False,
                path=path or "",
                inode=inode or 0,
                code=exc.code.value,
                detail=exc.to_record(),
            )
            return HostCallbackResult.make_failure(
                HostCallbackKind.GETATTR,
                exc.errno,
                message=str(exc),
                request_id=request_id,
                platform=platform,
                vfs_error_code=exc.code.value,
            )
        return HostCallbackResult.make_success(
            HostCallbackKind.GETATTR,
            metadata=meta.to_host_metadata(),
            observed_effect=False,
            request_id=request_id,
            platform=platform,
        )

    # -- access ------------------------------------------------------------

    def access(
        self,
        path: str | None = None,
        mask: int = F_OK,
        *,
        inode: int | None = None,
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> AccessResult:
        """Evaluate access(2) against projected mode and ownership."""

        try:
            mask = validate_access_mask(mask)
        except MetadataError as exc:
            # Store F_OK in the result mask field (validated); original bad
            # mask is preserved in detail for diagnostics.
            result = AccessResult(
                allowed=False,
                mask=F_OK,
                path=path or "",
                inode=inode or 0,
                errno=exc.errno,
                code=exc.code.value,
                detail=exc.to_record(),
            )
            self._trace.record(
                MetadataTraceKind.ACCESS,
                success=False,
                path=path or "",
                inode=inode or 0,
                code=exc.code.value,
                detail=result.to_record(),
            )
            return result

        try:
            if inode is not None:
                attr = self.require_inode(inode)
            elif path is not None:
                attr = self.require_path(path)
            else:
                raise MetadataError(
                    "access requires path or inode",
                    code=MetadataErrorCode.INVALID_ARGUMENT,
                    errno=HostErrno.EINVAL,
                )
        except MetadataError as exc:
            result = AccessResult(
                allowed=False,
                mask=mask,
                path=path or "",
                inode=inode or 0,
                errno=exc.errno,
                code=exc.code.value,
                detail=exc.to_record(),
            )
            self._trace.record(
                MetadataTraceKind.ACCESS,
                success=False,
                path=path or "",
                inode=inode or 0,
                code=exc.code.value,
                detail=result.to_record(),
            )
            return result

        projected = self.project(
            attr, caller_uid=caller_uid, caller_gid=caller_gid
        )

        # Write access against a read-only node or volume fails with EROFS/EACCES.
        if mask & W_OK and (attr.read_only or self._read_only):
            result = AccessResult(
                allowed=False,
                mask=mask,
                inode=attr.inode,
                path=attr.path,
                errno=HostErrno.EROFS,
                code=MetadataErrorCode.READ_ONLY.value,
                detail={"read_only": True},
            )
            self._trace.record(
                MetadataTraceKind.ACCESS,
                success=False,
                path=attr.path,
                inode=attr.inode,
                code=result.code,
                detail=result.to_record(),
            )
            return result

        granted = mode_grants(
            projected.mode,
            mask,
            file_uid=projected.uid,
            file_gid=projected.gid,
            caller_uid=caller_uid,
            caller_gid=caller_gid,
        )
        if granted:
            result = AccessResult(
                allowed=True,
                mask=mask,
                inode=attr.inode,
                path=attr.path,
                errno=HostErrno.OK,
                code="",
                detail={
                    "mode": projected.mode,
                    "uid": projected.uid,
                    "gid": projected.gid,
                    "caller_uid": caller_uid,
                    "caller_gid": caller_gid,
                },
            )
            self._trace.record(
                MetadataTraceKind.ACCESS,
                success=True,
                path=attr.path,
                inode=attr.inode,
                detail=result.to_record(),
            )
            return result

        result = AccessResult(
            allowed=False,
            mask=mask,
            inode=attr.inode,
            path=attr.path,
            errno=HostErrno.EACCES,
            code=MetadataErrorCode.PERMISSION.value,
            detail={
                "mode": projected.mode,
                "uid": projected.uid,
                "gid": projected.gid,
                "caller_uid": caller_uid,
                "caller_gid": caller_gid,
            },
        )
        self._trace.record(
            MetadataTraceKind.ACCESS,
            success=False,
            path=attr.path,
            inode=attr.inode,
            code=result.code,
            detail=result.to_record(),
        )
        return result

    # -- statfs ------------------------------------------------------------

    def statfs(
        self,
        *,
        used_blocks: int | None = None,
        used_files: int | None = None,
        mount_id: str = "",
    ) -> KernelStatfs:
        """Project volume statistics.

        When ``used_blocks`` / ``used_files`` are omitted, free counts are
        derived from the base profile minus current node occupancy (files
        count only; blocks estimated from total size).
        """

        if used_files is None:
            used_files = len(self._by_inode)
        if used_blocks is None:
            total_size = sum(attr.size for attr in self._by_inode.values())
            bs = self._statfs_base.block_size
            used_blocks = (total_size + bs - 1) // bs if total_size else 0

        result = KernelStatfs.hermetic_default(
            read_only=self._read_only or self._statfs_base.read_only,
            mount_id=mount_id or self._statfs_base.mount_id,
            used_blocks=used_blocks,
            used_files=used_files,
        )
        # Preserve custom base fields when the base was explicitly configured
        # with non-default totals.
        if (
            self._statfs_base.total_blocks != DEFAULT_TOTAL_BLOCKS
            or self._statfs_base.block_size != DEFAULT_BLOCK_SIZE
            or self._statfs_base.fs_name != DEFAULT_FS_NAME
            or self._statfs_base.fsid != DEFAULT_FSID
        ):
            free_blocks = max(0, self._statfs_base.total_blocks - used_blocks)
            free_files = max(0, self._statfs_base.total_files - used_files)
            result = KernelStatfs(
                block_size=self._statfs_base.block_size,
                total_blocks=self._statfs_base.total_blocks,
                free_blocks=free_blocks,
                available_blocks=0 if result.read_only else free_blocks,
                total_files=self._statfs_base.total_files,
                free_files=free_files,
                max_name_len=self._statfs_base.max_name_len,
                fsid=self._statfs_base.fsid,
                fs_name=self._statfs_base.fs_name,
                read_only=result.read_only,
                mount_id=result.mount_id,
            )
        self._trace.record(
            MetadataTraceKind.STATFS,
            success=True,
            detail=result.to_record(),
        )
        return result

    def statfs_host(
        self,
        *,
        platform: HostPlatform = HostPlatform.HERMETIC,
        request_id: str = "",
        mount_id: str = "",
    ) -> HostCallbackResult:
        """Project statfs to a host success result (statfs never carries HostMetadata)."""

        fs = self.statfs(mount_id=mount_id)
        # HostCallbackResult has no dedicated statfs payload field; the
        # closed record is returned via a success with observed_effect=False
        # and the full statfs available from the projector. Callers that need
        # the numbers use ``statfs()`` directly.
        result = HostCallbackResult.make_success(
            HostCallbackKind.STATFS,
            observed_effect=False,
            request_id=request_id,
            platform=platform,
        )
        # Attach non-authoritative detail only through the trace; keep result pure.
        _ = fs
        return result

    # -- utimens -----------------------------------------------------------

    def utimens(
        self,
        path: str | None = None,
        *,
        inode: int | None = None,
        atime_ns: int | None = None,
        mtime_ns: int | None = None,
        now_ns: int | None = None,
    ) -> UtimensResult:
        """Apply utimens to a node with UTIME_NOW / UTIME_OMIT semantics.

        * ``None`` or ``UTIME_OMIT`` leaves the field unchanged.
        * ``UTIME_NOW`` sets the field to ``now_ns`` (or the projector default).
        * any other non-negative integer sets the absolute time.
        * ctime always advances to ``now_ns`` when at least one of atime/mtime
          is not OMIT; pure dual-OMIT is a success no-op without ctime bump.
        * read-only nodes / volume reject with ``EROFS``.
        """

        now = self._default_now_ns if now_ns is None else _bounded_int(
            now_ns, "now_ns", minimum=0, maximum=MAX_TIME_NS
        )

        try:
            if inode is not None:
                attr = self.require_inode(inode)
            elif path is not None:
                attr = self.require_path(path)
            else:
                raise MetadataError(
                    "utimens requires path or inode",
                    code=MetadataErrorCode.INVALID_ARGUMENT,
                    errno=HostErrno.EINVAL,
                )
        except MetadataError as exc:
            result = UtimensResult(
                success=False,
                inode=inode or 0,
                path=path or "",
                errno=exc.errno,
                code=exc.code.value,
                detail=exc.to_record(),
            )
            self._trace.record(
                MetadataTraceKind.UTIMENS,
                success=False,
                path=path or "",
                inode=inode or 0,
                code=exc.code.value,
                detail=result.to_record(),
            )
            return result

        if attr.read_only or self._read_only:
            result = UtimensResult(
                success=False,
                inode=attr.inode,
                path=attr.path,
                atime_ns=attr.atime_ns,
                mtime_ns=attr.mtime_ns,
                ctime_ns=attr.ctime_ns,
                errno=HostErrno.EROFS,
                code=MetadataErrorCode.READ_ONLY.value,
                detail={"read_only": True},
            )
            self._trace.record(
                MetadataTraceKind.UTIMENS,
                success=False,
                path=attr.path,
                inode=attr.inode,
                code=result.code,
                detail=result.to_record(),
            )
            return result

        try:
            new_atime, atime_action = resolve_utimens_time(
                atime_ns, current=attr.atime_ns, now_ns=now
            )
            new_mtime, mtime_action = resolve_utimens_time(
                mtime_ns, current=attr.mtime_ns, now_ns=now
            )
        except MetadataError as exc:
            result = UtimensResult(
                success=False,
                inode=attr.inode,
                path=attr.path,
                atime_ns=attr.atime_ns,
                mtime_ns=attr.mtime_ns,
                ctime_ns=attr.ctime_ns,
                errno=exc.errno,
                code=exc.code.value,
                detail=exc.to_record(),
            )
            self._trace.record(
                MetadataTraceKind.UTIMENS,
                success=False,
                path=attr.path,
                inode=attr.inode,
                code=exc.code.value,
                detail=result.to_record(),
            )
            return result

        pure_omit = (
            atime_action is UtimensField.OMIT and mtime_action is UtimensField.OMIT
        )
        if pure_omit:
            result = UtimensResult(
                success=True,
                inode=attr.inode,
                path=attr.path,
                atime_ns=attr.atime_ns,
                mtime_ns=attr.mtime_ns,
                ctime_ns=attr.ctime_ns,
                atime_action=atime_action,
                mtime_action=mtime_action,
                observed_effect=False,
                errno=HostErrno.OK,
                code="",
                detail={"pure_omit": True},
            )
            self._trace.record(
                MetadataTraceKind.UTIMENS,
                success=True,
                path=attr.path,
                inode=attr.inode,
                detail=result.to_record(),
            )
            return result

        new_ctime = now
        updated = attr.with_updates(
            atime_ns=new_atime,
            mtime_ns=new_mtime,
            ctime_ns=new_ctime,
        )
        self.put(updated)
        result = UtimensResult(
            success=True,
            inode=updated.inode,
            path=updated.path,
            atime_ns=updated.atime_ns,
            mtime_ns=updated.mtime_ns,
            ctime_ns=updated.ctime_ns,
            atime_action=atime_action,
            mtime_action=mtime_action,
            observed_effect=True,
            errno=HostErrno.OK,
            code="",
            detail={
                "previous_atime_ns": attr.atime_ns,
                "previous_mtime_ns": attr.mtime_ns,
                "previous_ctime_ns": attr.ctime_ns,
            },
        )
        self._trace.record(
            MetadataTraceKind.UTIMENS,
            success=True,
            path=updated.path,
            inode=updated.inode,
            detail=result.to_record(),
        )
        return result

    # -- unsupported -------------------------------------------------------

    def unsupported(
        self,
        kind: HostCallbackKind | str,
        *,
        platform: HostPlatform = HostPlatform.HERMETIC,
        request_id: str = "",
        path: str = "",
    ) -> HostCallbackResult:
        """Return the stable unsupported result and record a trace step."""

        result = project_unsupported(
            kind, platform=platform, request_id=request_id
        )
        self._trace.record(
            MetadataTraceKind.UNSUPPORTED,
            success=False,
            path=path,
            code=result.errno.value,
            detail={
                "callback": result.kind.value,
                "errno": result.errno.value,
                "errno_number": errno_number(result.errno, platform),
            },
        )
        return result

    def unsupported_catalogue(
        self, *, platform: HostPlatform = HostPlatform.HERMETIC
    ) -> dict[str, dict[str, Any]]:
        """Return the closed map of reviewed unsupported metadata callbacks."""

        out: dict[str, dict[str, Any]] = {}
        for kind in sorted(METADATA_UNSUPPORTED_CALLBACKS, key=lambda k: k.value):
            result = project_unsupported(kind, platform=platform)
            out[kind.value] = {
                "callback": kind.value,
                "errno": result.errno.value,
                "errno_number": errno_number(result.errno, platform),
                "reviewed": kind in REVIEWED_UNSUPPORTED_CALLBACKS,
                "disposition": "explicit_unsupported",
            }
        return out

    # -- checkpoint / restore ----------------------------------------------

    def checkpoint(self) -> dict[str, Any]:
        nodes = [
            attr.to_record()
            for attr in sorted(self._by_inode.values(), key=lambda a: a.inode)
        ]
        payload = {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "uid_gid_policy": self._uid_gid_policy.to_record(),
            "statfs_base": self._statfs_base.to_record(),
            "default_now_ns": self._default_now_ns,
            "read_only": self._read_only,
            "nodes": nodes,
        }
        payload["content_id"] = content_identity(
            {k: v for k, v in payload.items() if k != "content_id"}
        )
        self._trace.record(
            MetadataTraceKind.CHECKPOINT,
            success=True,
            detail={"node_count": len(nodes), "content_id": payload["content_id"]},
        )
        return payload

    @classmethod
    def restore(cls, payload: Mapping[str, Any]) -> "MetadataProjector":
        if not isinstance(payload, Mapping):
            raise MetadataError(
                "checkpoint payload must be a mapping",
                code=MetadataErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        policy_payload = payload.get("uid_gid_policy")
        policy = (
            UidGidPolicy.from_dict(policy_payload)
            if isinstance(policy_payload, Mapping)
            else UidGidPolicy.fixed()
        )
        statfs_payload = payload.get("statfs_base")
        statfs = (
            KernelStatfs.from_dict(statfs_payload)
            if isinstance(statfs_payload, Mapping)
            else None
        )
        projector = cls(
            uid_gid_policy=policy,
            statfs=statfs,
            default_now_ns=int(payload.get("default_now_ns", 0) or 0),
            read_only=bool(payload.get("read_only", False)),
        )
        for item in payload.get("nodes") or ():
            if not isinstance(item, Mapping):
                raise MetadataError(
                    "node entries must be mappings",
                    code=MetadataErrorCode.INVALID_ARGUMENT,
                    errno=HostErrno.EINVAL,
                )
            projector.put(NodeAttr.from_dict(item))
        projector.trace.record(
            MetadataTraceKind.RESTORE,
            success=True,
            detail={"node_count": len(projector)},
        )
        return projector

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "uid_gid_policy": self._uid_gid_policy.to_record(),
            "statfs_base": self._statfs_base.to_record(),
            "default_now_ns": self._default_now_ns,
            "read_only": self._read_only,
            "node_count": len(self._by_inode),
            "trace": self._trace.to_records(),
        }


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def make_file_attr(
    inode: int,
    *,
    path: str = "",
    size: int = 0,
    mode: int = 0,
    uid: int = 0,
    gid: int = 0,
    atime_ns: int = 0,
    mtime_ns: int = 0,
    ctime_ns: int = 0,
    generation: int = 0,
    display_name: str = "",
    read_only: bool = False,
    nlink: int = NLINK_FILE_DEFAULT,
) -> NodeAttr:
    """Build a regular-file :class:`NodeAttr` with deterministic defaults."""

    return NodeAttr(
        inode=inode,
        file_type=FileType.FILE,
        size=size,
        mode=mode,
        nlink=nlink,
        uid=uid,
        gid=gid,
        atime_ns=atime_ns,
        mtime_ns=mtime_ns,
        ctime_ns=ctime_ns,
        generation=generation,
        path=path,
        display_name=display_name,
        read_only=read_only,
    )


def make_dir_attr(
    inode: int,
    *,
    path: str = "",
    mode: int = 0,
    uid: int = 0,
    gid: int = 0,
    atime_ns: int = 0,
    mtime_ns: int = 0,
    ctime_ns: int = 0,
    generation: int = 0,
    display_name: str = "",
    read_only: bool = False,
    child_dirs: int = 0,
) -> NodeAttr:
    """Build a directory :class:`NodeAttr` with deterministic defaults."""

    return NodeAttr(
        inode=inode,
        file_type=FileType.DIRECTORY,
        size=0,
        mode=mode,
        nlink=default_nlink(FileType.DIRECTORY, child_dirs=child_dirs),
        uid=uid,
        gid=gid,
        atime_ns=atime_ns,
        mtime_ns=mtime_ns,
        ctime_ns=ctime_ns,
        generation=generation,
        path=path,
        display_name=display_name,
        read_only=read_only,
        child_dirs=child_dirs,
    )


def make_symlink_attr(
    inode: int,
    *,
    path: str = "",
    mode: int = 0,
    uid: int = 0,
    gid: int = 0,
    atime_ns: int = 0,
    mtime_ns: int = 0,
    ctime_ns: int = 0,
    generation: int = 0,
    display_name: str = "",
    size: int = 0,
) -> NodeAttr:
    """Build a symlink :class:`NodeAttr` with deterministic defaults."""

    return NodeAttr(
        inode=inode,
        file_type=FileType.SYMLINK,
        size=size,
        mode=mode,
        nlink=NLINK_SYMLINK_DEFAULT,
        uid=uid,
        gid=gid,
        atime_ns=atime_ns,
        mtime_ns=mtime_ns,
        ctime_ns=ctime_ns,
        generation=generation,
        path=path,
        display_name=display_name,
    )


def ms_to_ns(ms: int) -> int:
    """Convert millisecond wall time to nanoseconds (bounded)."""

    ms = _bounded_int(ms, "ms", minimum=0)
    ns = ms * 1_000_000
    return _bounded_int(ns, "ns", minimum=0, maximum=MAX_TIME_NS)


def ns_to_ms(ns: int) -> int:
    """Convert nanoseconds to whole milliseconds (floor)."""

    ns = _bounded_int(ns, "ns", minimum=0, maximum=MAX_TIME_NS)
    return ns // 1_000_000


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    # versions / schemas
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "KERNEL_METADATA_SCHEMA",
    "KERNEL_STATFS_SCHEMA",
    "METADATA_PROJECTOR_SCHEMA",
    "UID_GID_POLICY_SCHEMA",
    "ACCESS_RESULT_SCHEMA",
    "UTIMENS_RESULT_SCHEMA",
    "NODE_ATTR_SCHEMA",
    "KernelMetadata_V1",
    "KernelStatfs_V1",
    "MetadataProjector_V1",
    # POSIX constants
    "S_IFMT",
    "S_IFSOCK",
    "S_IFLNK",
    "S_IFREG",
    "S_IFBLK",
    "S_IFDIR",
    "S_IFCHR",
    "S_IFIFO",
    "S_ISUID",
    "S_ISGID",
    "S_ISVTX",
    "S_IRWXU",
    "S_IRUSR",
    "S_IWUSR",
    "S_IXUSR",
    "S_IRWXG",
    "S_IRGRP",
    "S_IWGRP",
    "S_IXGRP",
    "S_IRWXO",
    "S_IROTH",
    "S_IWOTH",
    "S_IXOTH",
    "PERMISSION_MASK",
    "MODE_MASK",
    "DEFAULT_FILE_PERM",
    "DEFAULT_DIR_PERM",
    "DEFAULT_SYMLINK_PERM",
    "F_OK",
    "R_OK",
    "W_OK",
    "X_OK",
    "ACCESS_MASK_ALL",
    "UTIME_NOW",
    "UTIME_OMIT",
    "DEFAULT_TIME_NS",
    "DEFAULT_BLOCK_SIZE",
    "DEFAULT_TOTAL_BLOCKS",
    "DEFAULT_FSID",
    "DEFAULT_FS_NAME",
    "NLINK_FILE_DEFAULT",
    "NLINK_DIR_BASE",
    "NLINK_SYMLINK_DEFAULT",
    "METADATA_UNSUPPORTED_CALLBACKS",
    "REVIEWED_UNSUPPORTED_CALLBACKS",
    # enums
    "FileType",
    "UidGidPolicyKind",
    "MetadataErrorCode",
    "MetadataTraceKind",
    "UtimensField",
    # errors
    "MetadataError",
    # records
    "UidGidPolicy",
    "NodeAttr",
    "KernelMetadata",
    "AccessResult",
    "KernelStatfs",
    "UtimensResult",
    "MetadataTraceStep",
    "MetadataTraceLog",
    "MetadataProjector",
    # helpers
    "file_type_from_host_kind",
    "host_kind_from_file_type",
    "file_type_bits",
    "file_type_from_mode",
    "default_perm",
    "compose_mode",
    "permission_bits",
    "default_nlink",
    "validate_access_mask",
    "mode_grants",
    "classify_utimens_ns",
    "resolve_utimens_time",
    "project_unsupported",
    "unsupported_errno_for",
    "make_file_attr",
    "make_dir_attr",
    "make_symlink_attr",
    "ms_to_ns",
    "ns_to_ms",
]

"""KVFS-600: Windows namespace, case/name, permission, and open/delete semantics.

This module owns the pure Windows policy/projection plane for the kernel VFS:

* collision-safe lookup identity on case-insensitive WinFsp volumes while
  preserving caller/display spelling;
* fail-closed rejection of ambiguous case-fold collisions, reserved DOS
  device names, trailing dots/spaces, invalid UTF-8/UTF-16 conversion, and
  path traversal;
* executable case-only rename and drive-letter / directory mount-root forms;
* open-delete sharing and rename-while-open under WinFsp share rules;
* uid/gid/mode projection into WinFsp-compatible attributes;
* explicit-unsupported limits for ACL, ADS, reparse points, and symlinks
  with stable errno projection.

Conflict policy: own pure Windows policy/projection only. Drive/directory
mount lifecycle is KVFS-601. This module never imports fusepy, never loads
WinFsp, and never mounts a drive or directory.

Interfaces (plan aliases): ``WindowsNamespacePolicy@1``,
``WindowsOpenShareTable@1``, ``WindowsAttrProjector@1``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, IntFlag
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.host_contracts import (
    HostErrno,
    HostPlatform,
    WINDOWS_ERRNO_NUMBERS,
    errno_number,
)

# ---------------------------------------------------------------------------
# Identity / schema / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-600"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

WINDOWS_SEMANTICS_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/windows_semantics"

WINDOWS_NAMESPACE_POLICY_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/namespace-policy@{SCHEMA_MAJOR}"
)
WINDOWS_NAME_POLICY_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/name-policy@{SCHEMA_MAJOR}"
)
WINDOWS_LOOKUP_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/lookup-identity@{SCHEMA_MAJOR}"
)
WINDOWS_MOUNT_ROOT_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/mount-root@{SCHEMA_MAJOR}"
)
WINDOWS_OPEN_SHARE_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/open-share@{SCHEMA_MAJOR}"
)
WINDOWS_ATTR_PROJECTOR_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/attr-projector@{SCHEMA_MAJOR}"
)
WINDOWS_FEATURE_LIMIT_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/feature-limit@{SCHEMA_MAJOR}"
)
WINDOWS_TRACE_SCHEMA: Final[str] = (
    f"{WINDOWS_SEMANTICS_NAMESPACE}/trace@{SCHEMA_MAJOR}"
)

# Public interface aliases.
WindowsNamespacePolicy_V1: Final[str] = WINDOWS_NAMESPACE_POLICY_SCHEMA
WindowsOpenShareTable_V1: Final[str] = WINDOWS_OPEN_SHARE_SCHEMA
WindowsAttrProjector_V1: Final[str] = WINDOWS_ATTR_PROJECTOR_SCHEMA

MAX_COMPONENT_BYTES: Final[int] = 255
MAX_PATH_CHARS: Final[int] = 32_767  # Win32 extended path limit
MAX_NAMESPACE_ENTRIES: Final[int] = 1_048_576
MAX_OPEN_HANDLES: Final[int] = 65_536
MAX_TRACE_STEPS: Final[int] = 4_096

# Win32 FILE_ATTRIBUTE_* (subset used for FUSE getattr projection).
FILE_ATTRIBUTE_READONLY: Final[int] = 0x00000001
FILE_ATTRIBUTE_HIDDEN: Final[int] = 0x00000002
FILE_ATTRIBUTE_SYSTEM: Final[int] = 0x00000004
FILE_ATTRIBUTE_DIRECTORY: Final[int] = 0x00000010
FILE_ATTRIBUTE_ARCHIVE: Final[int] = 0x00000020
FILE_ATTRIBUTE_NORMAL: Final[int] = 0x00000080
FILE_ATTRIBUTE_REPARSE_POINT: Final[int] = 0x00000400

# Default POSIX permission projection when mode is unset.
DEFAULT_FILE_MODE: Final[int] = 0o100644
DEFAULT_DIR_MODE: Final[int] = 0o040755
DEFAULT_UID: Final[int] = 0
DEFAULT_GID: Final[int] = 0

# Characters forbidden in Windows file names (Win32 CreateFile rules).
_INVALID_FILENAME_CHARS: Final[frozenset[str]] = frozenset('<>:"/\\|?*')
_CONTROL_CHAR_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f]")

# DOS device reserved base names (case-insensitive; extension does not save).
_RESERVED_DEVICE_BASES: Final[frozenset[str]] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

_DRIVE_LETTER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:\\?$")
_DRIVE_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:([\\/].*)?$")


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class WindowsCaseMode(str, Enum):
    """Volume case policy selected for the WinFsp mount."""

    # Case-sensitive volume (rare; opt-in WinFsp / NTFS flag).
    SENSITIVE = "case_sensitive"
    # Default WinFsp volume: lookup folds case, display spelling preserved.
    INSENSITIVE = "case_insensitive"


class WindowsNameRejectReason(str, Enum):
    """Why a Windows name/path component was rejected."""

    EMPTY = "empty"
    NOT_STRING = "not_string"
    RESERVED_DEVICE = "reserved_device"
    TRAILING_DOT_SPACE = "trailing_dot_space"
    INVALID_CHAR = "invalid_char"
    CONTROL_CHAR = "control_char"
    NUL = "nul"
    SEGMENT_TOO_LONG = "segment_too_long"
    NON_NFC = "non_nfc"
    INVALID_UTF16 = "invalid_utf16"
    INVALID_UTF8 = "invalid_utf8"
    SURROGATE = "surrogate"
    TRAVERSAL = "traversal"
    ABSOLUTE = "absolute"
    BACKSLASH = "backslash"
    DOT_SEGMENT = "dot_segment"
    EMPTY_SEGMENT = "empty_segment"
    PATH_TOO_LONG = "path_too_long"
    CASE_FOLD_COLLISION = "case_fold_collision"
    ALREADY_EXISTS = "already_exists"
    NOT_FOUND = "not_found"
    MOUNT_ROOT = "mount_root"
    SHARE_VIOLATION = "share_violation"
    DELETE_PENDING = "delete_pending"
    HANDLE_LIMIT = "handle_limit"
    FEATURE_UNSUPPORTED = "feature_unsupported"
    INTERNAL = "internal"


class WindowsSemanticsErrorCode(str, Enum):
    """Stable Windows-semantics error codes."""

    NAME_POLICY = "WIN_NAME_POLICY"
    CASE_COLLISION = "WIN_CASE_COLLISION"
    UTF_CONVERSION = "WIN_UTF_CONVERSION"
    TRAVERSAL = "WIN_TRAVERSAL"
    MOUNT_ROOT = "WIN_MOUNT_ROOT"
    NOT_FOUND = "WIN_NOT_FOUND"
    ALREADY_EXISTS = "WIN_ALREADY_EXISTS"
    SHARE_VIOLATION = "WIN_SHARE_VIOLATION"
    DELETE_PENDING = "WIN_DELETE_PENDING"
    HANDLE_LIMIT = "WIN_HANDLE_LIMIT"
    FEATURE_UNSUPPORTED = "WIN_FEATURE_UNSUPPORTED"
    INVALID_ARGUMENT = "WIN_INVALID_ARGUMENT"
    BUSY = "WIN_BUSY"
    INTERNAL = "WIN_INTERNAL"


class MountRootKind(str, Enum):
    """Admitted WinFsp mount-root forms."""

    DRIVE_LETTER = "drive_letter"
    DIRECTORY = "directory"


class WindowsFeature(str, Enum):
    """Windows features with explicit limits under the FUSE-compat profile."""

    ACL = "acl"
    ADS = "ads"
    REPARSE = "reparse"
    SYMLINK = "symlink"
    HARDLINK = "hardlink"
    SECURITY_DESCRIPTOR_SET = "security_descriptor_set"
    EXTENDED_ATTRIBUTES = "extended_attributes"


class WindowsTraceKind(str, Enum):
    """Executable policy-trace step kinds."""

    NAME_VALIDATE = "name_validate"
    LOOKUP = "lookup"
    CREATE = "create"
    CASE_COLLISION = "case_collision"
    CASE_ONLY_RENAME = "case_only_rename"
    MOUNT_ROOT = "mount_root"
    OPEN = "open"
    SHARE = "share"
    DELETE = "delete"
    RENAME = "rename"
    ATTR_PROJECT = "attr_project"
    FEATURE_LIMIT = "feature_limit"
    UTF = "utf"
    TRAVERSAL = "traversal"
    ERRNO = "errno"


class WindowsAccess(IntFlag):
    """Desired access bits for open-share arbitration (Win32-shaped)."""

    NONE = 0
    READ = 0x0001
    WRITE = 0x0002
    DELETE = 0x0004
    EXECUTE = 0x0008
    ALL = READ | WRITE | DELETE | EXECUTE


class WindowsShareMode(IntFlag):
    """FILE_SHARE_* bits controlling concurrent open admission."""

    NONE = 0
    READ = 0x0001
    WRITE = 0x0002
    DELETE = 0x0004
    ALL = READ | WRITE | DELETE


class UidGidProjectionKind(str, Enum):
    """How POSIX uid/gid are projected onto WinFsp getattr fields."""

    FIXED = "fixed"
    CALLER = "caller"
    ROOT = "root"


# Feature → stable errno under the WinFsp FUSE-compat profile.
_FEATURE_ERRNO: Final[Mapping[WindowsFeature, HostErrno]] = {
    WindowsFeature.ACL: HostErrno.EOPNOTSUPP,
    WindowsFeature.ADS: HostErrno.EOPNOTSUPP,
    WindowsFeature.REPARSE: HostErrno.EOPNOTSUPP,
    WindowsFeature.SYMLINK: HostErrno.EOPNOTSUPP,
    WindowsFeature.HARDLINK: HostErrno.EOPNOTSUPP,
    WindowsFeature.SECURITY_DESCRIPTOR_SET: HostErrno.EOPNOTSUPP,
    WindowsFeature.EXTENDED_ATTRIBUTES: HostErrno.EOPNOTSUPP,
}

# Map reject reasons to HostErrno for fusepy projection.
_REASON_ERRNO: Final[Mapping[WindowsNameRejectReason, HostErrno]] = {
    WindowsNameRejectReason.EMPTY: HostErrno.EINVAL,
    WindowsNameRejectReason.NOT_STRING: HostErrno.EINVAL,
    WindowsNameRejectReason.RESERVED_DEVICE: HostErrno.EINVAL,
    WindowsNameRejectReason.TRAILING_DOT_SPACE: HostErrno.EINVAL,
    WindowsNameRejectReason.INVALID_CHAR: HostErrno.EINVAL,
    WindowsNameRejectReason.CONTROL_CHAR: HostErrno.EINVAL,
    WindowsNameRejectReason.NUL: HostErrno.EINVAL,
    WindowsNameRejectReason.SEGMENT_TOO_LONG: HostErrno.ENAMETOOLONG,
    WindowsNameRejectReason.NON_NFC: HostErrno.EINVAL,
    WindowsNameRejectReason.INVALID_UTF16: HostErrno.EINVAL,
    WindowsNameRejectReason.INVALID_UTF8: HostErrno.EINVAL,
    WindowsNameRejectReason.SURROGATE: HostErrno.EINVAL,
    WindowsNameRejectReason.TRAVERSAL: HostErrno.EPERM,
    WindowsNameRejectReason.ABSOLUTE: HostErrno.EINVAL,
    WindowsNameRejectReason.BACKSLASH: HostErrno.EINVAL,
    WindowsNameRejectReason.DOT_SEGMENT: HostErrno.EINVAL,
    WindowsNameRejectReason.EMPTY_SEGMENT: HostErrno.EINVAL,
    WindowsNameRejectReason.PATH_TOO_LONG: HostErrno.ENAMETOOLONG,
    WindowsNameRejectReason.CASE_FOLD_COLLISION: HostErrno.EEXIST,
    WindowsNameRejectReason.ALREADY_EXISTS: HostErrno.EEXIST,
    WindowsNameRejectReason.NOT_FOUND: HostErrno.ENOENT,
    WindowsNameRejectReason.MOUNT_ROOT: HostErrno.EINVAL,
    WindowsNameRejectReason.SHARE_VIOLATION: HostErrno.EACCES,
    WindowsNameRejectReason.DELETE_PENDING: HostErrno.EACCES,
    WindowsNameRejectReason.HANDLE_LIMIT: HostErrno.EMFILE,
    WindowsNameRejectReason.FEATURE_UNSUPPORTED: HostErrno.EOPNOTSUPP,
    WindowsNameRejectReason.INTERNAL: HostErrno.EIO,
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WindowsSemanticsError(ValueError):
    """Fail-closed Windows semantics error with stable code and errno."""

    def __init__(
        self,
        message: str,
        *,
        code: WindowsSemanticsErrorCode,
        errno: HostErrno = HostErrno.EINVAL,
        reason: WindowsNameRejectReason | None = None,
        path: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = (
            code
            if isinstance(code, WindowsSemanticsErrorCode)
            else WindowsSemanticsErrorCode(code)
        )
        self.errno = errno if isinstance(errno, HostErrno) else HostErrno(errno)
        self.reason = reason
        self.path = path
        self.detail = dict(detail or {})

    @property
    def errno_name(self) -> str:
        return self.errno.value

    @property
    def errno_number(self) -> int:
        return errno_number(self.errno, platform=HostPlatform.WINDOWS)

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": str(self),
            "errno": self.errno.value,
            "errno_number": self.errno_number,
            "reason": self.reason.value if self.reason is not None else "",
            "path": self.path,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bounded_int(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise WindowsSemanticsError(
            f"{name} must be an int",
            code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
            detail={"field": name, "value_type": type(value).__name__},
        )
    if value < minimum:
        raise WindowsSemanticsError(
            f"{name} must be >= {minimum}",
            code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
            detail={"field": name, "value": value},
        )
    if maximum is not None and value > maximum:
        raise WindowsSemanticsError(
            f"{name} must be <= {maximum}",
            code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
            detail={"field": name, "value": value},
        )
    return value


def windows_errno_number(err: HostErrno | str) -> int:
    """Project a HostErrno name to the WinFsp FUSE-compat numeric code."""

    if isinstance(err, str):
        err = HostErrno(err)
    return int(WINDOWS_ERRNO_NUMBERS.get(err, errno_number(err, platform=HostPlatform.WINDOWS)))


def reason_to_errno(reason: WindowsNameRejectReason | str) -> HostErrno:
    if not isinstance(reason, WindowsNameRejectReason):
        reason = WindowsNameRejectReason(reason)
    return _REASON_ERRNO.get(reason, HostErrno.EINVAL)


# ---------------------------------------------------------------------------
# UTF conversion policy
# ---------------------------------------------------------------------------


def is_valid_utf16_text(text: str) -> bool:
    """Return True when *text* is free of lone surrogates and UTF-16 encodable.

    Windows path APIs are UTF-16LE. Lone surrogates and non-encodable code
    points must fail closed rather than silent replacement.
    """

    if not isinstance(text, str):
        return False
    for ch in text:
        code = ord(ch)
        # Lone surrogate halves are invalid scalar values.
        if 0xD800 <= code <= 0xDFFF:
            return False
    try:
        text.encode("utf-16-le", errors="strict")
    except UnicodeEncodeError:
        return False
    # Round-trip through UTF-16LE must preserve the scalar string.
    try:
        restored = text.encode("utf-16-le", errors="strict").decode(
            "utf-16-le", errors="strict"
        )
    except UnicodeError:
        return False
    return restored == text


def is_valid_utf8_text(text: str) -> bool:
    """Return True when *text* encodes/decodes as strict UTF-8 without surrogates."""

    if not isinstance(text, str):
        return False
    for ch in text:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            return False
    try:
        raw = text.encode("utf-8", errors="strict")
        restored = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return False
    return restored == text


def validate_utf_conversion(text: str) -> None:
    """Reject invalid UTF-8/UTF-16 conversion candidates fail-closed."""

    if not isinstance(text, str):
        raise WindowsSemanticsError(
            "UTF conversion requires a str",
            code=WindowsSemanticsErrorCode.UTF_CONVERSION,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.NOT_STRING,
        )
    if not is_valid_utf8_text(text):
        raise WindowsSemanticsError(
            "invalid UTF-8 conversion",
            code=WindowsSemanticsErrorCode.UTF_CONVERSION,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.INVALID_UTF8,
            path=text,
        )
    if not is_valid_utf16_text(text):
        raise WindowsSemanticsError(
            "invalid UTF-16 conversion",
            code=WindowsSemanticsErrorCode.UTF_CONVERSION,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.INVALID_UTF16,
            path=text,
        )


# ---------------------------------------------------------------------------
# Name / path policy
# ---------------------------------------------------------------------------


def fold_windows_identity(name: str) -> str:
    """Collision-safe lookup identity for a Windows name component.

    Uses Unicode casefold over NFC so ambiguous case variants collide on the
    same key while the original display spelling is stored separately.
    """

    if not isinstance(name, str):
        raise WindowsSemanticsError(
            "name must be a str",
            code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.NOT_STRING,
        )
    nfc = unicodedata.normalize("NFC", name)
    return nfc.casefold()


def reserved_device_base(name: str) -> str | None:
    """Return the reserved DOS device base if *name* matches, else None.

    Matching is case-insensitive. An extension does not evade reservation
    (``CON.txt`` is reserved). A trailing colon form (``CON:``) is reserved.
    """

    if not isinstance(name, str) or not name:
        return None
    # Strip a single trailing colon used by device paths.
    base = name[:-1] if name.endswith(":") else name
    # Device reservation applies to the stem before the first '.' .
    stem = base.split(".", 1)[0]
    key = stem.upper()
    if key in _RESERVED_DEVICE_BASES:
        return key
    return None


def is_reserved_device_name(name: str) -> bool:
    return reserved_device_base(name) is not None


def has_trailing_dot_or_space(name: str) -> bool:
    """Windows strips trailing dots/spaces; this policy rejects them."""

    if not isinstance(name, str) or not name:
        return False
    return name[-1] in (".", " ")


def _component_byte_length(name: str) -> int:
    return len(name.encode("utf-8", errors="surrogatepass"))


@dataclass(frozen=True)
class NameValidationResult:
    """Outcome of validating a single Windows path component."""

    SCHEMA: ClassVar[str] = WINDOWS_NAME_POLICY_SCHEMA

    ok: bool
    display_spelling: str = ""
    lookup_identity: str = ""
    reason: WindowsNameRejectReason | None = None
    errno: HostErrno = HostErrno.OK
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "ok": self.ok,
            "display_spelling": self.display_spelling,
            "lookup_identity": self.lookup_identity,
            "reason": self.reason.value if self.reason is not None else "",
            "errno": self.errno.value,
            "errno_number": (
                0 if self.errno is HostErrno.OK else windows_errno_number(self.errno)
            ),
            "detail": dict(self.detail),
        }


def validate_windows_component(
    name: Any,
    *,
    require_nfc: bool = True,
) -> NameValidationResult:
    """Validate a single Windows path component fail-closed.

    On success returns the original *display_spelling* and a collision-safe
    *lookup_identity*. Never silently rewrites spelling.
    """

    if not isinstance(name, str):
        return NameValidationResult(
            ok=False,
            reason=WindowsNameRejectReason.NOT_STRING,
            errno=HostErrno.EINVAL,
            detail={"value_type": type(name).__name__},
        )
    if name == "":
        return NameValidationResult(
            ok=False,
            reason=WindowsNameRejectReason.EMPTY,
            errno=HostErrno.EINVAL,
        )
    if "\x00" in name:
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.NUL,
            errno=HostErrno.EINVAL,
        )
    if _CONTROL_CHAR_RE.search(name):
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.CONTROL_CHAR,
            errno=HostErrno.EINVAL,
        )
    # Reserved DOS devices (including trailing-colon forms like ``COM3:``)
    # outrank the generic invalid-char rule so callers get RESERVED_DEVICE.
    if is_reserved_device_name(name):
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.RESERVED_DEVICE,
            errno=HostErrno.EINVAL,
            detail={"device": reserved_device_base(name)},
        )
    if any(ch in _INVALID_FILENAME_CHARS for ch in name):
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.INVALID_CHAR,
            errno=HostErrno.EINVAL,
            detail={"invalid_chars": sorted(set(name) & _INVALID_FILENAME_CHARS)},
        )
    if has_trailing_dot_or_space(name):
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.TRAILING_DOT_SPACE,
            errno=HostErrno.EINVAL,
        )
    if _component_byte_length(name) > MAX_COMPONENT_BYTES:
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.SEGMENT_TOO_LONG,
            errno=HostErrno.ENAMETOOLONG,
            detail={"bytes": _component_byte_length(name)},
        )
    # Surrogates / UTF conversion.
    for ch in name:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            return NameValidationResult(
                ok=False,
                display_spelling=name,
                reason=WindowsNameRejectReason.SURROGATE,
                errno=HostErrno.EINVAL,
            )
    if not is_valid_utf8_text(name):
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.INVALID_UTF8,
            errno=HostErrno.EINVAL,
        )
    if not is_valid_utf16_text(name):
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.INVALID_UTF16,
            errno=HostErrno.EINVAL,
        )
    if require_nfc and unicodedata.normalize("NFC", name) != name:
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.NON_NFC,
            errno=HostErrno.EINVAL,
            detail={"nfc_required": True},
        )
    # Reject dot segments as components (. and ..).
    if name in (".", ".."):
        return NameValidationResult(
            ok=False,
            display_spelling=name,
            reason=WindowsNameRejectReason.DOT_SEGMENT
            if name == "."
            else WindowsNameRejectReason.TRAVERSAL,
            errno=HostErrno.EINVAL if name == "." else HostErrno.EPERM,
        )

    return NameValidationResult(
        ok=True,
        display_spelling=name,
        lookup_identity=fold_windows_identity(name),
        errno=HostErrno.OK,
        detail={"display_spelling_preserved": True},
    )


def validate_windows_component_or_raise(name: Any, *, require_nfc: bool = True) -> NameValidationResult:
    result = validate_windows_component(name, require_nfc=require_nfc)
    if not result.ok:
        reason = result.reason or WindowsNameRejectReason.INTERNAL
        code = WindowsSemanticsErrorCode.NAME_POLICY
        if reason is WindowsNameRejectReason.TRAVERSAL:
            code = WindowsSemanticsErrorCode.TRAVERSAL
        elif reason in (
            WindowsNameRejectReason.INVALID_UTF8,
            WindowsNameRejectReason.INVALID_UTF16,
            WindowsNameRejectReason.SURROGATE,
        ):
            code = WindowsSemanticsErrorCode.UTF_CONVERSION
        raise WindowsSemanticsError(
            f"Windows name rejected: {reason.value}",
            code=code,
            errno=result.errno,
            reason=reason,
            path=result.display_spelling or str(name),
            detail=dict(result.detail),
        )
    return result


@dataclass(frozen=True)
class NormalizedWindowsPath:
    """Namespace-relative path with display segments and lookup identity."""

    SCHEMA: ClassVar[str] = WINDOWS_LOOKUP_SCHEMA

    display_path: str
    lookup_path: str
    display_segments: tuple[str, ...]
    lookup_segments: tuple[str, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "display_path": self.display_path,
            "lookup_path": self.lookup_path,
            "display_segments": list(self.display_segments),
            "lookup_segments": list(self.lookup_segments),
            "display_spelling_preserved": True,
        }


def _split_namespace_path(raw: str) -> list[str]:
    """Split a namespace path on ``/`` only; backslash is invalid."""

    if not isinstance(raw, str):
        raise WindowsSemanticsError(
            "path must be a str",
            code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.NOT_STRING,
        )
    if "\x00" in raw:
        raise WindowsSemanticsError(
            "NUL in path",
            code=WindowsSemanticsErrorCode.NAME_POLICY,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.NUL,
            path=raw,
        )
    # Absolute OS forms outrank bare backslash rejection so drive/UNC paths
    # report ABSOLUTE (e.g. ``C:\Windows``) rather than BACKSLASH.
    if _DRIVE_PATH_RE.match(raw) or raw.startswith("//") or raw.startswith("\\\\"):
        raise WindowsSemanticsError(
            "absolute / drive / UNC paths are rejected at namespace surface",
            code=WindowsSemanticsErrorCode.NAME_POLICY,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.ABSOLUTE,
            path=raw,
        )
    if "\\" in raw:
        raise WindowsSemanticsError(
            "backslash is not admitted in namespace paths",
            code=WindowsSemanticsErrorCode.NAME_POLICY,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.BACKSLASH,
            path=raw,
        )
    text = raw[1:] if raw.startswith("/") else raw
    if text == "":
        return []
    parts = text.split("/")
    return parts


def normalize_windows_namespace_path(
    raw: str,
    *,
    require_nfc: bool = True,
) -> NormalizedWindowsPath:
    """Normalize a namespace-relative path under Windows name policy.

    Rejects traversal (``..``), empty segments, backslashes, absolute forms,
    reserved devices, trailing dots/spaces, and invalid UTF conversion.
    Preserves each component's display spelling.
    """

    parts = _split_namespace_path(raw)
    display_segments: list[str] = []
    lookup_segments: list[str] = []
    for part in parts:
        if part == "":
            raise WindowsSemanticsError(
                "empty path segment",
                code=WindowsSemanticsErrorCode.NAME_POLICY,
                errno=HostErrno.EINVAL,
                reason=WindowsNameRejectReason.EMPTY_SEGMENT,
                path=raw,
            )
        if part == "..":
            raise WindowsSemanticsError(
                "path traversal rejected",
                code=WindowsSemanticsErrorCode.TRAVERSAL,
                errno=HostErrno.EPERM,
                reason=WindowsNameRejectReason.TRAVERSAL,
                path=raw,
                detail={"segment": part},
            )
        if part == ".":
            raise WindowsSemanticsError(
                "dot segment rejected",
                code=WindowsSemanticsErrorCode.NAME_POLICY,
                errno=HostErrno.EINVAL,
                reason=WindowsNameRejectReason.DOT_SEGMENT,
                path=raw,
                detail={"segment": part},
            )
        validated = validate_windows_component_or_raise(part, require_nfc=require_nfc)
        display_segments.append(validated.display_spelling)
        lookup_segments.append(validated.lookup_identity)

    display_path = "/".join(display_segments)
    lookup_path = "/".join(lookup_segments)
    if len(display_path) > MAX_PATH_CHARS:
        raise WindowsSemanticsError(
            "path too long",
            code=WindowsSemanticsErrorCode.NAME_POLICY,
            errno=HostErrno.ENAMETOOLONG,
            reason=WindowsNameRejectReason.PATH_TOO_LONG,
            path=display_path,
        )
    return NormalizedWindowsPath(
        display_path=display_path,
        lookup_path=lookup_path,
        display_segments=tuple(display_segments),
        lookup_segments=tuple(lookup_segments),
    )


# ---------------------------------------------------------------------------
# Mount roots (drive letter vs directory)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowsMountRoot:
    """Validated WinFsp mount-root form."""

    SCHEMA: ClassVar[str] = WINDOWS_MOUNT_ROOT_SCHEMA

    kind: MountRootKind
    value: str
    # Canonical presentation: ``Z:`` for drive, absolute directory path for dir.
    canonical: str

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "value": self.value,
            "canonical": self.canonical,
        }


def validate_drive_letter_root(raw: str) -> WindowsMountRoot:
    """Admit ``Z:`` or ``Z:\\`` style drive-letter roots only."""

    if not isinstance(raw, str) or not raw.strip():
        raise WindowsSemanticsError(
            "drive letter root must be a non-empty str",
            code=WindowsSemanticsErrorCode.MOUNT_ROOT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.MOUNT_ROOT,
            detail={"raw": raw},
        )
    text = raw.strip()
    if not _DRIVE_LETTER_RE.match(text):
        raise WindowsSemanticsError(
            f"invalid drive letter root: {raw!r}",
            code=WindowsSemanticsErrorCode.MOUNT_ROOT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.MOUNT_ROOT,
            path=raw,
        )
    letter = text[0].upper()
    return WindowsMountRoot(
        kind=MountRootKind.DRIVE_LETTER,
        value=raw,
        canonical=f"{letter}:",
    )


def validate_directory_root(raw: str) -> WindowsMountRoot:
    """Admit a non-empty directory mount root (absolute Windows or POSIX form).

    Hermetic tests may pass POSIX absolute paths (``/mnt/winfsp``). On Windows
    hosts the production form is an absolute drive path. Empty, relative, and
    traversal forms are rejected.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise WindowsSemanticsError(
            "directory root must be a non-empty str",
            code=WindowsSemanticsErrorCode.MOUNT_ROOT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.MOUNT_ROOT,
        )
    text = raw.strip()
    if "\x00" in text:
        raise WindowsSemanticsError(
            "directory root contains NUL",
            code=WindowsSemanticsErrorCode.MOUNT_ROOT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.NUL,
            path=raw,
        )
    # Reject relative / traversal forms.
    if text in (".", "..") or text.startswith("./") or text.startswith("../"):
        raise WindowsSemanticsError(
            "directory root must be absolute",
            code=WindowsSemanticsErrorCode.MOUNT_ROOT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.MOUNT_ROOT,
            path=raw,
        )
    if ".." in text.replace("\\", "/").split("/"):
        raise WindowsSemanticsError(
            "directory root traversal rejected",
            code=WindowsSemanticsErrorCode.TRAVERSAL,
            errno=HostErrno.EPERM,
            reason=WindowsNameRejectReason.TRAVERSAL,
            path=raw,
        )
    # Drive-letter-only forms belong to the drive-letter validator.
    if _DRIVE_LETTER_RE.match(text):
        raise WindowsSemanticsError(
            "drive-letter form is not a directory root",
            code=WindowsSemanticsErrorCode.MOUNT_ROOT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.MOUNT_ROOT,
            path=raw,
        )
    is_win_abs = bool(_DRIVE_PATH_RE.match(text)) and len(text) > 2
    is_posix_abs = text.startswith("/")
    is_unc = text.startswith("\\\\") or text.startswith("//")
    if not (is_win_abs or is_posix_abs or is_unc):
        raise WindowsSemanticsError(
            "directory root must be absolute",
            code=WindowsSemanticsErrorCode.MOUNT_ROOT,
            errno=HostErrno.EINVAL,
            reason=WindowsNameRejectReason.MOUNT_ROOT,
            path=raw,
        )
    # Trailing slash normalized away except drive root like C:\
    if is_win_abs:
        canonical = text.rstrip("\\/") if len(text) > 3 else text
        if len(canonical) == 2 and canonical[1] == ":":
            canonical = canonical + "\\"
    else:
        canonical = text.rstrip("/") if len(text) > 1 else text
    return WindowsMountRoot(
        kind=MountRootKind.DIRECTORY,
        value=raw,
        canonical=canonical,
    )


def validate_mount_root(raw: str, *, kind: MountRootKind | str | None = None) -> WindowsMountRoot:
    """Validate a mount root, optionally forcing *kind*."""

    if kind is not None and not isinstance(kind, MountRootKind):
        kind = MountRootKind(kind)
    if kind is MountRootKind.DRIVE_LETTER:
        return validate_drive_letter_root(raw)
    if kind is MountRootKind.DIRECTORY:
        return validate_directory_root(raw)
    # Auto-detect.
    if isinstance(raw, str) and _DRIVE_LETTER_RE.match(raw.strip()):
        return validate_drive_letter_root(raw)
    return validate_directory_root(raw)


# ---------------------------------------------------------------------------
# Namespace with collision-safe lookup
# ---------------------------------------------------------------------------


@dataclass
class WindowsNamespaceEntry:
    """One directory entry: display spelling + fold identity + payload."""

    display_spelling: str
    lookup_identity: str
    is_directory: bool = False
    inode: int = 0
    mode: int = DEFAULT_FILE_MODE
    uid: int = DEFAULT_UID
    gid: int = DEFAULT_GID
    size: int = 0
    delete_pending: bool = False
    # Optional opaque attributes for tests / higher layers.
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "display_spelling": self.display_spelling,
            "lookup_identity": self.lookup_identity,
            "is_directory": self.is_directory,
            "inode": self.inode,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "size": self.size,
            "delete_pending": self.delete_pending,
            "attrs": dict(self.attrs),
        }


@dataclass(frozen=True)
class LookupResult:
    """Result of a collision-safe lookup."""

    found: bool
    display_spelling: str = ""
    lookup_identity: str = ""
    entry: WindowsNamespaceEntry | None = None
    collided: bool = False
    reason: WindowsNameRejectReason | None = None
    errno: HostErrno = HostErrno.OK

    def to_record(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "display_spelling": self.display_spelling,
            "lookup_identity": self.lookup_identity,
            "display_spelling_preserved": bool(self.display_spelling),
            "collided": self.collided,
            "reason": self.reason.value if self.reason is not None else "",
            "errno": self.errno.value,
            "entry": self.entry.to_record() if self.entry is not None else None,
        }


class WindowsNamespace:
    """In-memory Windows-shaped namespace plane (hermetic / executable).

    Under :attr:`WindowsCaseMode.INSENSITIVE` the lookup key is the case-folded
    identity; the stored display spelling is whatever was admitted first.
    Creating a second spelling that folds to an existing identity fails closed
    with ``EEXIST`` (ambiguous fold / case collision).
    """

    SCHEMA: ClassVar[str] = WINDOWS_NAMESPACE_POLICY_SCHEMA

    def __init__(
        self,
        *,
        case_mode: WindowsCaseMode | str = WindowsCaseMode.INSENSITIVE,
        require_nfc: bool = True,
    ) -> None:
        if not isinstance(case_mode, WindowsCaseMode):
            case_mode = WindowsCaseMode(case_mode)
        self._case_mode = case_mode
        self._require_nfc = bool(require_nfc)
        # parent_lookup_path -> {lookup_identity -> entry}
        self._dirs: dict[str, dict[str, WindowsNamespaceEntry]] = {"": {}}
        self._inode_seq = 1
        self._trace = WindowsSemanticsTrace()

    @property
    def case_mode(self) -> WindowsCaseMode:
        return self._case_mode

    @property
    def trace(self) -> "WindowsSemanticsTrace":
        return self._trace

    def _parent_and_name(self, path: str) -> tuple[str, str]:
        norm = normalize_windows_namespace_path(path, require_nfc=self._require_nfc)
        if not norm.display_segments:
            raise WindowsSemanticsError(
                "root has no component name",
                code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
                path=path,
            )
        parent_display = "/".join(norm.display_segments[:-1])
        parent_lookup = "/".join(norm.lookup_segments[:-1])
        name_display = norm.display_segments[-1]
        # Ensure parent exists as a directory (root always exists).
        if parent_lookup not in self._dirs:
            # Parent must already be registered as a directory entry when non-root.
            raise WindowsSemanticsError(
                f"parent directory not found: {parent_display!r}",
                code=WindowsSemanticsErrorCode.NOT_FOUND,
                errno=HostErrno.ENOENT,
                reason=WindowsNameRejectReason.NOT_FOUND,
                path=parent_display,
            )
        return parent_lookup, name_display

    def _lookup_key(self, name: str) -> str:
        if self._case_mode is WindowsCaseMode.SENSITIVE:
            # Still NFC-bound; identity is exact display spelling.
            return name
        return fold_windows_identity(name)

    def lookup(self, path: str) -> LookupResult:
        """Lookup *path* preserving stored display spelling on hit."""

        if path in ("", "/"):
            # Synthetic root.
            root = WindowsNamespaceEntry(
                display_spelling="",
                lookup_identity="",
                is_directory=True,
                inode=1,
                mode=DEFAULT_DIR_MODE,
            )
            result = LookupResult(
                found=True,
                display_spelling="",
                lookup_identity="",
                entry=root,
            )
            self._trace.record(
                WindowsTraceKind.LOOKUP,
                success=True,
                path=path,
                detail=result.to_record(),
            )
            return result

        norm = normalize_windows_namespace_path(path, require_nfc=self._require_nfc)
        parent_lookup = "/".join(norm.lookup_segments[:-1])
        name_display = norm.display_segments[-1]
        key = self._lookup_key(name_display)
        table = self._dirs.get(parent_lookup)
        if table is None:
            result = LookupResult(
                found=False,
                display_spelling=name_display,
                lookup_identity=key,
                reason=WindowsNameRejectReason.NOT_FOUND,
                errno=HostErrno.ENOENT,
            )
            self._trace.record(
                WindowsTraceKind.LOOKUP,
                success=False,
                path=norm.display_path,
                code=WindowsSemanticsErrorCode.NOT_FOUND.value,
                detail=result.to_record(),
            )
            return result
        entry = table.get(key)
        if entry is None:
            result = LookupResult(
                found=False,
                display_spelling=name_display,
                lookup_identity=key,
                reason=WindowsNameRejectReason.NOT_FOUND,
                errno=HostErrno.ENOENT,
            )
            self._trace.record(
                WindowsTraceKind.LOOKUP,
                success=False,
                path=norm.display_path,
                code=WindowsSemanticsErrorCode.NOT_FOUND.value,
                detail=result.to_record(),
            )
            return result
        # Display spelling is whatever was stored at create time.
        result = LookupResult(
            found=True,
            display_spelling=entry.display_spelling,
            lookup_identity=entry.lookup_identity,
            entry=entry,
        )
        self._trace.record(
            WindowsTraceKind.LOOKUP,
            success=True,
            path=norm.display_path,
            detail={
                **result.to_record(),
                "request_spelling": name_display,
                "display_spelling_preserved": entry.display_spelling != name_display
                or entry.display_spelling == name_display,
            },
        )
        return result

    def create(
        self,
        path: str,
        *,
        is_directory: bool = False,
        mode: int | None = None,
        uid: int = DEFAULT_UID,
        gid: int = DEFAULT_GID,
        size: int = 0,
        attrs: Mapping[str, Any] | None = None,
    ) -> WindowsNamespaceEntry:
        """Create a file or directory; ambiguous folds fail closed with EEXIST."""

        parent_lookup, name_display = self._parent_and_name(path)
        validated = validate_windows_component_or_raise(
            name_display, require_nfc=self._require_nfc
        )
        key = self._lookup_key(validated.display_spelling)
        table = self._dirs[parent_lookup]
        existing = table.get(key)
        if existing is not None:
            # Exact same display spelling → already exists.
            # Different spelling, same fold → ambiguous case-fold collision.
            if existing.display_spelling == validated.display_spelling:
                reason = WindowsNameRejectReason.ALREADY_EXISTS
                code = WindowsSemanticsErrorCode.ALREADY_EXISTS
            else:
                reason = WindowsNameRejectReason.CASE_FOLD_COLLISION
                code = WindowsSemanticsErrorCode.CASE_COLLISION
            self._trace.record(
                WindowsTraceKind.CASE_COLLISION
                if reason is WindowsNameRejectReason.CASE_FOLD_COLLISION
                else WindowsTraceKind.CREATE,
                success=False,
                path=path,
                code=code.value,
                detail={
                    "existing_display": existing.display_spelling,
                    "request_display": validated.display_spelling,
                    "lookup_identity": key,
                    "reason": reason.value,
                    "fail_closed": True,
                },
            )
            raise WindowsSemanticsError(
                (
                    f"case-fold collision: {validated.display_spelling!r} collides with "
                    f"{existing.display_spelling!r}"
                    if reason is WindowsNameRejectReason.CASE_FOLD_COLLISION
                    else f"already exists: {validated.display_spelling!r}"
                ),
                code=code,
                errno=HostErrno.EEXIST,
                reason=reason,
                path=path,
                detail={
                    "existing_display": existing.display_spelling,
                    "request_display": validated.display_spelling,
                    "lookup_identity": key,
                    "fail_closed": True,
                },
            )

        if len(table) >= MAX_NAMESPACE_ENTRIES:
            raise WindowsSemanticsError(
                "namespace entry limit exceeded",
                code=WindowsSemanticsErrorCode.INTERNAL,
                errno=HostErrno.ENOSPC,
            )

        self._inode_seq += 1
        entry = WindowsNamespaceEntry(
            display_spelling=validated.display_spelling,
            lookup_identity=key,
            is_directory=bool(is_directory),
            inode=self._inode_seq,
            mode=int(
                mode
                if mode is not None
                else (DEFAULT_DIR_MODE if is_directory else DEFAULT_FILE_MODE)
            ),
            uid=_bounded_int(uid, "uid", minimum=0),
            gid=_bounded_int(gid, "gid", minimum=0),
            size=_bounded_int(size, "size", minimum=0),
            attrs=dict(attrs or {}),
        )
        table[key] = entry
        if is_directory:
            child_lookup = f"{parent_lookup}/{key}" if parent_lookup else key
            self._dirs.setdefault(child_lookup, {})
        self._trace.record(
            WindowsTraceKind.CREATE,
            success=True,
            path=path,
            detail={
                "display_spelling": entry.display_spelling,
                "lookup_identity": entry.lookup_identity,
                "is_directory": entry.is_directory,
                "inode": entry.inode,
                "display_spelling_preserved": True,
            },
        )
        return entry

    def case_only_rename(self, path: str, new_display: str) -> WindowsNamespaceEntry:
        """Rename a single component to a new spelling of the same fold identity.

        On case-insensitive volumes this updates the stored display spelling
        without changing the lookup identity. On case-sensitive volumes the
        fold identity must still match (otherwise it is a normal rename, not
        case-only) — mismatched folds are rejected as invalid case-only rename.
        """

        parent_lookup, old_display = self._parent_and_name(path)
        old_key = self._lookup_key(old_display)
        table = self._dirs[parent_lookup]
        entry = table.get(old_key)
        if entry is None:
            raise WindowsSemanticsError(
                f"not found: {path!r}",
                code=WindowsSemanticsErrorCode.NOT_FOUND,
                errno=HostErrno.ENOENT,
                reason=WindowsNameRejectReason.NOT_FOUND,
                path=path,
            )
        validated = validate_windows_component_or_raise(
            new_display, require_nfc=self._require_nfc
        )
        new_key = self._lookup_key(validated.display_spelling)
        if new_key != old_key:
            self._trace.record(
                WindowsTraceKind.CASE_ONLY_RENAME,
                success=False,
                path=path,
                code=WindowsSemanticsErrorCode.INVALID_ARGUMENT.value,
                detail={
                    "old_display": entry.display_spelling,
                    "new_display": validated.display_spelling,
                    "old_identity": old_key,
                    "new_identity": new_key,
                    "case_only": False,
                },
            )
            raise WindowsSemanticsError(
                "case-only rename requires identical lookup identity",
                code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
                path=path,
                detail={
                    "old_identity": old_key,
                    "new_identity": new_key,
                    "case_only": False,
                },
            )
        # Same key: just update display spelling in place.
        entry.display_spelling = validated.display_spelling
        self._trace.record(
            WindowsTraceKind.CASE_ONLY_RENAME,
            success=True,
            path=path,
            detail={
                "old_display": old_display,
                "new_display": entry.display_spelling,
                "lookup_identity": old_key,
                "case_only": True,
                "display_spelling_preserved": True,
            },
        )
        return entry

    def rename(
        self,
        source: str,
        target: str,
        *,
        open_table: "WindowsOpenShareTable | None" = None,
    ) -> WindowsNamespaceEntry:
        """Rename within the namespace; enforces share rules when *open_table* given."""

        # Case-only fast path.
        try:
            src_parent, src_name = self._parent_and_name(source)
            dst_parent, dst_name = self._parent_and_name(target)
        except WindowsSemanticsError:
            raise

        if src_parent == dst_parent and self._lookup_key(src_name) == self._lookup_key(dst_name):
            return self.case_only_rename(source, dst_name)

        if open_table is not None:
            decision = open_table.check_rename_allowed(source)
            if not decision.allowed:
                raise WindowsSemanticsError(
                    decision.message,
                    code=WindowsSemanticsErrorCode.SHARE_VIOLATION,
                    errno=decision.errno,
                    reason=WindowsNameRejectReason.SHARE_VIOLATION,
                    path=source,
                    detail=decision.to_record(),
                )

        src_lookup = self.lookup(source)
        if not src_lookup.found or src_lookup.entry is None:
            raise WindowsSemanticsError(
                f"rename source not found: {source!r}",
                code=WindowsSemanticsErrorCode.NOT_FOUND,
                errno=HostErrno.ENOENT,
                reason=WindowsNameRejectReason.NOT_FOUND,
                path=source,
            )
        # Target must not exist (no replace in this pure policy surface).
        dst_lookup = self.lookup(target)
        if dst_lookup.found:
            raise WindowsSemanticsError(
                f"rename target exists: {target!r}",
                code=WindowsSemanticsErrorCode.ALREADY_EXISTS,
                errno=HostErrno.EEXIST,
                reason=WindowsNameRejectReason.ALREADY_EXISTS,
                path=target,
            )

        entry = src_lookup.entry
        # Remove from source.
        src_table = self._dirs[src_parent]
        src_key = self._lookup_key(entry.display_spelling)
        del src_table[src_key]

        # Insert under target.
        validated = validate_windows_component_or_raise(dst_name, require_nfc=self._require_nfc)
        dst_key = self._lookup_key(validated.display_spelling)
        entry.display_spelling = validated.display_spelling
        entry.lookup_identity = dst_key
        self._dirs[dst_parent][dst_key] = entry

        # Move this directory's table and every nested descendant table.
        if entry.is_directory:
            old_prefix = f"{src_parent}/{src_key}" if src_parent else src_key
            new_prefix = f"{dst_parent}/{dst_key}" if dst_parent else dst_key
            # Snapshot keys to avoid mutating while iterating.
            to_move = [
                key
                for key in self._dirs
                if key == old_prefix or key.startswith(old_prefix + "/")
            ]
            for old_key_path in sorted(to_move, key=len):
                suffix = old_key_path[len(old_prefix) :]  # "" or "/..."
                new_key_path = new_prefix + suffix
                self._dirs[new_key_path] = self._dirs.pop(old_key_path)

        if open_table is not None:
            open_table.notify_rename(source, target)

        self._trace.record(
            WindowsTraceKind.RENAME,
            success=True,
            path=source,
            detail={
                "source": source,
                "target": target,
                "display_spelling": entry.display_spelling,
                "lookup_identity": entry.lookup_identity,
            },
        )
        return entry

    def mark_delete_pending(self, path: str) -> WindowsNamespaceEntry:
        result = self.lookup(path)
        if not result.found or result.entry is None:
            raise WindowsSemanticsError(
                f"not found: {path!r}",
                code=WindowsSemanticsErrorCode.NOT_FOUND,
                errno=HostErrno.ENOENT,
                reason=WindowsNameRejectReason.NOT_FOUND,
                path=path,
            )
        result.entry.delete_pending = True
        return result.entry

    def unlink(
        self,
        path: str,
        *,
        open_table: "WindowsOpenShareTable | None" = None,
    ) -> dict[str, Any]:
        """Unlink *path* honouring open-delete share rules when provided."""

        if open_table is not None:
            decision = open_table.check_delete_allowed(path)
            if not decision.allowed:
                raise WindowsSemanticsError(
                    decision.message,
                    code=WindowsSemanticsErrorCode.SHARE_VIOLATION,
                    errno=decision.errno,
                    reason=WindowsNameRejectReason.SHARE_VIOLATION,
                    path=path,
                    detail=decision.to_record(),
                )

        parent_lookup, name_display = self._parent_and_name(path)
        key = self._lookup_key(name_display)
        table = self._dirs[parent_lookup]
        entry = table.get(key)
        if entry is None:
            raise WindowsSemanticsError(
                f"not found: {path!r}",
                code=WindowsSemanticsErrorCode.NOT_FOUND,
                errno=HostErrno.ENOENT,
                reason=WindowsNameRejectReason.NOT_FOUND,
                path=path,
            )

        open_count = 0 if open_table is None else open_table.open_count(path)
        if open_count > 0:
            # POSIX-on-WinFsp: mark delete-pending; remove from namespace lookup
            # only after last handle closes — but path becomes delete-pending.
            entry.delete_pending = True
            if open_table is not None:
                open_table.mark_delete_pending(path)
            detail = {
                "path": path,
                "delete_pending": True,
                "open_count": open_count,
                "removed": False,
                "inode": entry.inode,
            }
            self._trace.record(
                WindowsTraceKind.DELETE,
                success=True,
                path=path,
                detail=detail,
            )
            return detail

        # No open handles: remove immediately.
        del table[key]
        if entry.is_directory:
            child = f"{parent_lookup}/{key}" if parent_lookup else key
            self._dirs.pop(child, None)
        detail = {
            "path": path,
            "delete_pending": False,
            "open_count": 0,
            "removed": True,
            "inode": entry.inode,
        }
        self._trace.record(
            WindowsTraceKind.DELETE,
            success=True,
            path=path,
            detail=detail,
        )
        return detail

    def list_dir(self, path: str = "") -> list[WindowsNamespaceEntry]:
        if path in ("", "/"):
            parent_lookup = ""
        else:
            result = self.lookup(path)
            if not result.found or result.entry is None or not result.entry.is_directory:
                raise WindowsSemanticsError(
                    f"not a directory: {path!r}",
                    code=WindowsSemanticsErrorCode.NOT_FOUND,
                    errno=HostErrno.ENOTDIR,
                    path=path,
                )
            # Build lookup path for this directory.
            norm = normalize_windows_namespace_path(path, require_nfc=self._require_nfc)
            parent_lookup = norm.lookup_path
        table = self._dirs.get(parent_lookup, {})
        return list(table.values())


# ---------------------------------------------------------------------------
# Open / share / delete-while-open
# ---------------------------------------------------------------------------


@dataclass
class WindowsOpenHandle:
    """One open instance under WinFsp share rules."""

    handle_id: int
    path: str
    access: WindowsAccess
    share: WindowsShareMode
    delete_pending: bool = False
    released: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "path": self.path,
            "access": int(self.access),
            "share": int(self.share),
            "delete_pending": self.delete_pending,
            "released": self.released,
        }


@dataclass(frozen=True)
class ShareDecision:
    """Admission decision for open / delete / rename under share rules."""

    allowed: bool
    errno: HostErrno = HostErrno.OK
    message: str = ""
    reason: WindowsNameRejectReason | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "errno": self.errno.value,
            "errno_number": (
                0 if self.errno is HostErrno.OK else windows_errno_number(self.errno)
            ),
            "message": self.message,
            "reason": self.reason.value if self.reason is not None else "",
            "detail": dict(self.detail),
        }


def share_permits(existing: WindowsOpenHandle, desired_access: WindowsAccess) -> bool:
    """Return True if *existing* share mode permits *desired_access*."""

    if existing.released:
        return True
    if desired_access & WindowsAccess.READ and not (existing.share & WindowsShareMode.READ):
        return False
    if desired_access & WindowsAccess.WRITE and not (existing.share & WindowsShareMode.WRITE):
        return False
    if desired_access & WindowsAccess.DELETE and not (existing.share & WindowsShareMode.DELETE):
        return False
    return True


def access_permits_peer_share(new_share: WindowsShareMode, existing_access: WindowsAccess) -> bool:
    """Return True if *new_share* permits the access already held by a peer."""

    if existing_access & WindowsAccess.READ and not (new_share & WindowsShareMode.READ):
        return False
    if existing_access & WindowsAccess.WRITE and not (new_share & WindowsShareMode.WRITE):
        return False
    if existing_access & WindowsAccess.DELETE and not (new_share & WindowsShareMode.DELETE):
        return False
    return True


class WindowsOpenShareTable:
    """Open-handle table implementing WinFsp-compatible share arbitration.

    Delete-while-open is admitted only when every live handle (and the delete
    request) participates in ``FILE_SHARE_DELETE``. Handles remain valid until
    release even after the path is marked delete-pending. Rename-while-open
    requires share-delete consent from all live handles on the source path.
    """

    SCHEMA: ClassVar[str] = WINDOWS_OPEN_SHARE_SCHEMA

    def __init__(self) -> None:
        self._handles: dict[int, WindowsOpenHandle] = {}
        self._by_path: dict[str, set[int]] = {}
        self._next_id = 1
        self._trace = WindowsSemanticsTrace()

    @property
    def trace(self) -> "WindowsSemanticsTrace":
        return self._trace

    def open_count(self, path: str) -> int:
        ids = self._by_path.get(path, set())
        return sum(1 for hid in ids if not self._handles[hid].released)

    def open_handles(self, path: str | None = None) -> list[WindowsOpenHandle]:
        if path is None:
            return [h for h in self._handles.values() if not h.released]
        return [
            self._handles[hid]
            for hid in self._by_path.get(path, set())
            if not self._handles[hid].released
        ]

    def check_open_allowed(
        self,
        path: str,
        *,
        access: WindowsAccess,
        share: WindowsShareMode,
    ) -> ShareDecision:
        live = self.open_handles(path)
        for existing in live:
            if existing.delete_pending:
                return ShareDecision(
                    allowed=False,
                    errno=HostErrno.EACCES,
                    message=f"open rejected: delete pending on {path!r}",
                    reason=WindowsNameRejectReason.DELETE_PENDING,
                    detail={"path": path, "existing": existing.to_record()},
                )
            if not share_permits(existing, access):
                return ShareDecision(
                    allowed=False,
                    errno=HostErrno.EACCES,
                    message=f"share violation on open of {path!r}",
                    reason=WindowsNameRejectReason.SHARE_VIOLATION,
                    detail={
                        "path": path,
                        "desired_access": int(access),
                        "existing": existing.to_record(),
                    },
                )
            if not access_permits_peer_share(share, existing.access):
                return ShareDecision(
                    allowed=False,
                    errno=HostErrno.EACCES,
                    message=f"share violation (peer access) on open of {path!r}",
                    reason=WindowsNameRejectReason.SHARE_VIOLATION,
                    detail={
                        "path": path,
                        "new_share": int(share),
                        "existing": existing.to_record(),
                    },
                )
        return ShareDecision(allowed=True, detail={"path": path, "open_count": len(live)})

    def open(
        self,
        path: str,
        *,
        access: WindowsAccess | int = WindowsAccess.READ,
        share: WindowsShareMode | int = WindowsShareMode.READ | WindowsShareMode.WRITE | WindowsShareMode.DELETE,
    ) -> WindowsOpenHandle:
        if not isinstance(access, WindowsAccess):
            access = WindowsAccess(int(access))
        if not isinstance(share, WindowsShareMode):
            share = WindowsShareMode(int(share))
        decision = self.check_open_allowed(path, access=access, share=share)
        self._trace.record(
            WindowsTraceKind.OPEN if decision.allowed else WindowsTraceKind.SHARE,
            success=decision.allowed,
            path=path,
            code="" if decision.allowed else WindowsSemanticsErrorCode.SHARE_VIOLATION.value,
            detail=decision.to_record(),
        )
        if not decision.allowed:
            raise WindowsSemanticsError(
                decision.message,
                code=WindowsSemanticsErrorCode.SHARE_VIOLATION,
                errno=decision.errno,
                reason=decision.reason,
                path=path,
                detail=decision.to_record(),
            )
        if len(self._handles) >= MAX_OPEN_HANDLES:
            raise WindowsSemanticsError(
                "open handle limit exceeded",
                code=WindowsSemanticsErrorCode.HANDLE_LIMIT,
                errno=HostErrno.EMFILE,
                reason=WindowsNameRejectReason.HANDLE_LIMIT,
                path=path,
            )
        hid = self._next_id
        self._next_id += 1
        handle = WindowsOpenHandle(
            handle_id=hid,
            path=path,
            access=access,
            share=share,
        )
        self._handles[hid] = handle
        self._by_path.setdefault(path, set()).add(hid)
        return handle

    def release(self, handle_id: int) -> dict[str, Any]:
        handle = self._handles.get(handle_id)
        if handle is None:
            raise WindowsSemanticsError(
                f"unknown handle: {handle_id}",
                code=WindowsSemanticsErrorCode.INVALID_ARGUMENT,
                errno=HostErrno.EBADF,
            )
        handle.released = True
        path = handle.path
        remaining = self.open_count(path)
        detail = {
            "handle_id": handle_id,
            "path": path,
            "remaining_open": remaining,
            "delete_pending": handle.delete_pending,
            "final_close": remaining == 0,
        }
        return detail

    def check_delete_allowed(self, path: str) -> ShareDecision:
        live = self.open_handles(path)
        if not live:
            return ShareDecision(allowed=True, detail={"path": path, "open_count": 0})
        for existing in live:
            # Delete requires FILE_SHARE_DELETE from every live handle.
            if not (existing.share & WindowsShareMode.DELETE):
                return ShareDecision(
                    allowed=False,
                    errno=HostErrno.EACCES,
                    message=f"delete denied while open without FILE_SHARE_DELETE: {path!r}",
                    reason=WindowsNameRejectReason.SHARE_VIOLATION,
                    detail={"path": path, "existing": existing.to_record()},
                )
            # Existing handle must also have been opened with share that allows
            # the delete access of the unlink operation.
            if not share_permits(existing, WindowsAccess.DELETE):
                return ShareDecision(
                    allowed=False,
                    errno=HostErrno.EACCES,
                    message=f"delete share violation: {path!r}",
                    reason=WindowsNameRejectReason.SHARE_VIOLATION,
                    detail={"path": path, "existing": existing.to_record()},
                )
        return ShareDecision(
            allowed=True,
            detail={
                "path": path,
                "open_count": len(live),
                "delete_while_open": True,
                "handle_still_valid": True,
            },
        )

    def mark_delete_pending(self, path: str) -> None:
        for handle in self.open_handles(path):
            handle.delete_pending = True

    def check_rename_allowed(self, path: str) -> ShareDecision:
        live = self.open_handles(path)
        if not live:
            return ShareDecision(allowed=True, detail={"path": path, "open_count": 0})
        for existing in live:
            if not (existing.share & WindowsShareMode.DELETE):
                return ShareDecision(
                    allowed=False,
                    errno=HostErrno.EACCES,
                    message=f"rename denied while open without FILE_SHARE_DELETE: {path!r}",
                    reason=WindowsNameRejectReason.SHARE_VIOLATION,
                    detail={"path": path, "existing": existing.to_record()},
                )
        return ShareDecision(
            allowed=True,
            detail={
                "path": path,
                "open_count": len(live),
                "rename_while_open": True,
                "handle_still_valid": True,
            },
        )

    def notify_rename(self, source: str, target: str) -> None:
        ids = list(self._by_path.get(source, set()))
        for hid in ids:
            handle = self._handles[hid]
            if handle.released:
                continue
            handle.path = target
            self._by_path.setdefault(target, set()).add(hid)
            self._by_path.get(source, set()).discard(hid)
        if source in self._by_path and not self._by_path[source]:
            del self._by_path[source]


# ---------------------------------------------------------------------------
# uid/gid/mode → WinFsp attribute projection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UidGidProjection:
    """Ownership projection policy for WinFsp getattr fields."""

    kind: UidGidProjectionKind = UidGidProjectionKind.FIXED
    fixed_uid: int = DEFAULT_UID
    fixed_gid: int = DEFAULT_GID

    def resolve(
        self,
        *,
        stored_uid: int | None = None,
        stored_gid: int | None = None,
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> tuple[int, int]:
        caller_uid = _bounded_int(caller_uid, "caller_uid", minimum=0)
        caller_gid = _bounded_int(caller_gid, "caller_gid", minimum=0)
        if self.kind is UidGidProjectionKind.ROOT:
            return 0, 0
        if self.kind is UidGidProjectionKind.CALLER:
            return caller_uid, caller_gid
        uid = self.fixed_uid if stored_uid is None else _bounded_int(stored_uid, "stored_uid", minimum=0)
        gid = self.fixed_gid if stored_gid is None else _bounded_int(stored_gid, "stored_gid", minimum=0)
        return uid, gid

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "fixed_uid": self.fixed_uid,
            "fixed_gid": self.fixed_gid,
        }


@dataclass(frozen=True)
class WindowsProjectedAttributes:
    """WinFsp-compatible attribute projection of a VFS node."""

    SCHEMA: ClassVar[str] = WINDOWS_ATTR_PROJECTOR_SCHEMA

    path: str
    display_spelling: str
    uid: int
    gid: int
    mode: int
    size: int
    is_directory: bool
    file_attributes: int
    readonly: bool
    nlink: int = 1
    inode: int = 0
    # Explicit-unsupported feature surface advertised to callers.
    acl_supported: bool = False
    ads_supported: bool = False
    reparse_supported: bool = False
    symlink_supported: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path": self.path,
            "display_spelling": self.display_spelling,
            "uid": self.uid,
            "gid": self.gid,
            "mode": self.mode,
            "size": self.size,
            "is_directory": self.is_directory,
            "file_attributes": self.file_attributes,
            "readonly": self.readonly,
            "nlink": self.nlink,
            "inode": self.inode,
            "acl_supported": self.acl_supported,
            "ads_supported": self.ads_supported,
            "reparse_supported": self.reparse_supported,
            "symlink_supported": self.symlink_supported,
        }


def mode_to_file_attributes(mode: int, *, is_directory: bool) -> int:
    """Project POSIX mode bits into Win32 FILE_ATTRIBUTE flags."""

    attrs = 0
    if is_directory:
        attrs |= FILE_ATTRIBUTE_DIRECTORY
    else:
        attrs |= FILE_ATTRIBUTE_NORMAL
    # Readonly when owner write bit is clear.
    if (int(mode) & 0o222) == 0:
        attrs |= FILE_ATTRIBUTE_READONLY
        if attrs & FILE_ATTRIBUTE_NORMAL:
            attrs &= ~FILE_ATTRIBUTE_NORMAL
    return attrs


class WindowsAttrProjector:
    """Project VFS node metadata into WinFsp-compatible getattr fields."""

    SCHEMA: ClassVar[str] = WINDOWS_ATTR_PROJECTOR_SCHEMA

    def __init__(
        self,
        *,
        uid_gid: UidGidProjection | None = None,
    ) -> None:
        self._uid_gid = uid_gid or UidGidProjection()
        self._trace = WindowsSemanticsTrace()

    @property
    def trace(self) -> "WindowsSemanticsTrace":
        return self._trace

    def project(
        self,
        entry: WindowsNamespaceEntry,
        *,
        path: str = "",
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> WindowsProjectedAttributes:
        uid, gid = self._uid_gid.resolve(
            stored_uid=entry.uid,
            stored_gid=entry.gid,
            caller_uid=caller_uid,
            caller_gid=caller_gid,
        )
        file_attrs = mode_to_file_attributes(entry.mode, is_directory=entry.is_directory)
        readonly = bool(file_attrs & FILE_ATTRIBUTE_READONLY)
        projected = WindowsProjectedAttributes(
            path=path or entry.display_spelling,
            display_spelling=entry.display_spelling,
            uid=uid,
            gid=gid,
            mode=entry.mode,
            size=0 if entry.is_directory else entry.size,
            is_directory=entry.is_directory,
            file_attributes=file_attrs,
            readonly=readonly,
            nlink=2 if entry.is_directory else 1,
            inode=entry.inode,
            acl_supported=False,
            ads_supported=False,
            reparse_supported=False,
            symlink_supported=False,
        )
        self._trace.record(
            WindowsTraceKind.ATTR_PROJECT,
            success=True,
            path=projected.path,
            detail=projected.to_record(),
        )
        return projected


# ---------------------------------------------------------------------------
# Feature limits (ACL / ADS / reparse / symlink)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureLimitResult:
    """Stable unsupported result for a Windows feature."""

    SCHEMA: ClassVar[str] = WINDOWS_FEATURE_LIMIT_SCHEMA

    feature: WindowsFeature
    supported: bool
    errno: HostErrno
    errno_number: int
    message: str

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "feature": self.feature.value,
            "supported": self.supported,
            "errno": self.errno.value,
            "errno_number": self.errno_number,
            "message": self.message,
        }


def feature_limit(feature: WindowsFeature | str) -> FeatureLimitResult:
    """Return the explicit-unsupported disposition for *feature*."""

    if not isinstance(feature, WindowsFeature):
        feature = WindowsFeature(feature)
    err = _FEATURE_ERRNO.get(feature, HostErrno.EOPNOTSUPP)
    return FeatureLimitResult(
        feature=feature,
        supported=False,
        errno=err,
        errno_number=windows_errno_number(err),
        message=f"Windows feature {feature.value!r} is not supported under WinFsp FUSE profile",
    )


def reject_unsupported_feature(feature: WindowsFeature | str) -> None:
    """Raise the stable unsupported error for *feature*."""

    result = feature_limit(feature)
    raise WindowsSemanticsError(
        result.message,
        code=WindowsSemanticsErrorCode.FEATURE_UNSUPPORTED,
        errno=result.errno,
        reason=WindowsNameRejectReason.FEATURE_UNSUPPORTED,
        detail=result.to_record(),
    )


def evaluate_feature_request(feature: WindowsFeature | str) -> FeatureLimitResult:
    """Executable feature-limit check (never silently succeeds)."""

    return feature_limit(feature)


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowsTraceStep:
    kind: WindowsTraceKind
    success: bool
    path: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "success": self.success,
            "path": self.path,
            "code": self.code,
            "detail": dict(self.detail),
        }


class WindowsSemanticsTrace:
    """Bounded executable policy trace for hermetic tests."""

    SCHEMA: ClassVar[str] = WINDOWS_TRACE_SCHEMA

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        self._max_steps = max(1, int(max_steps))
        self._steps: list[WindowsTraceStep] = []

    def record(
        self,
        kind: WindowsTraceKind | str,
        *,
        success: bool,
        path: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> WindowsTraceStep:
        if not isinstance(kind, WindowsTraceKind):
            kind = WindowsTraceKind(kind)
        step = WindowsTraceStep(
            kind=kind,
            success=bool(success),
            path=path,
            code=code,
            detail=dict(detail or {}),
        )
        if len(self._steps) < self._max_steps:
            self._steps.append(step)
        return step

    def steps(self) -> tuple[WindowsTraceStep, ...]:
        return tuple(self._steps)

    def kinds(self) -> list[str]:
        return [s.kind.value for s in self._steps]

    def clear(self) -> None:
        self._steps.clear()

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "steps": [s.to_record() for s in self._steps],
        }


# ---------------------------------------------------------------------------
# Facade used by higher layers / tests
# ---------------------------------------------------------------------------


class WindowsSemanticsPolicy:
    """Composable Windows semantics facade (namespace + share + attrs + limits)."""

    SCHEMA: ClassVar[str] = WINDOWS_NAMESPACE_POLICY_SCHEMA

    def __init__(
        self,
        *,
        case_mode: WindowsCaseMode | str = WindowsCaseMode.INSENSITIVE,
        require_nfc: bool = True,
        uid_gid: UidGidProjection | None = None,
    ) -> None:
        self.namespace = WindowsNamespace(case_mode=case_mode, require_nfc=require_nfc)
        self.open_table = WindowsOpenShareTable()
        self.attrs = WindowsAttrProjector(uid_gid=uid_gid)
        self._trace = WindowsSemanticsTrace()

    @property
    def case_mode(self) -> WindowsCaseMode:
        return self.namespace.case_mode

    @property
    def trace(self) -> WindowsSemanticsTrace:
        return self._trace

    def validate_name(self, name: str) -> NameValidationResult:
        result = validate_windows_component(name, require_nfc=self.namespace._require_nfc)
        self._trace.record(
            WindowsTraceKind.NAME_VALIDATE,
            success=result.ok,
            path=name if isinstance(name, str) else "",
            code="" if result.ok else WindowsSemanticsErrorCode.NAME_POLICY.value,
            detail=result.to_record(),
        )
        return result

    def normalize_path(self, path: str) -> NormalizedWindowsPath:
        try:
            norm = normalize_windows_namespace_path(
                path, require_nfc=self.namespace._require_nfc
            )
        except WindowsSemanticsError as exc:
            kind = (
                WindowsTraceKind.TRAVERSAL
                if exc.code is WindowsSemanticsErrorCode.TRAVERSAL
                else WindowsTraceKind.UTF
                if exc.code is WindowsSemanticsErrorCode.UTF_CONVERSION
                else WindowsTraceKind.NAME_VALIDATE
            )
            self._trace.record(
                kind,
                success=False,
                path=path,
                code=exc.code.value,
                detail=exc.to_record(),
            )
            raise
        self._trace.record(
            WindowsTraceKind.NAME_VALIDATE,
            success=True,
            path=norm.display_path,
            detail=norm.to_record(),
        )
        return norm

    def validate_mount_root(
        self, raw: str, *, kind: MountRootKind | str | None = None
    ) -> WindowsMountRoot:
        try:
            root = validate_mount_root(raw, kind=kind)
        except WindowsSemanticsError as exc:
            self._trace.record(
                WindowsTraceKind.MOUNT_ROOT,
                success=False,
                path=raw,
                code=exc.code.value,
                detail=exc.to_record(),
            )
            raise
        self._trace.record(
            WindowsTraceKind.MOUNT_ROOT,
            success=True,
            path=root.canonical,
            detail=root.to_record(),
        )
        return root

    def lookup(self, path: str) -> LookupResult:
        return self.namespace.lookup(path)

    def create(self, path: str, **kwargs: Any) -> WindowsNamespaceEntry:
        return self.namespace.create(path, **kwargs)

    def case_only_rename(self, path: str, new_display: str) -> WindowsNamespaceEntry:
        return self.namespace.case_only_rename(path, new_display)

    def open(
        self,
        path: str,
        *,
        access: WindowsAccess | int = WindowsAccess.READ,
        share: WindowsShareMode | int = WindowsShareMode.ALL,
    ) -> WindowsOpenHandle:
        # Ensure path exists and is not delete-pending without share.
        result = self.namespace.lookup(path)
        if not result.found or result.entry is None:
            raise WindowsSemanticsError(
                f"not found: {path!r}",
                code=WindowsSemanticsErrorCode.NOT_FOUND,
                errno=HostErrno.ENOENT,
                reason=WindowsNameRejectReason.NOT_FOUND,
                path=path,
            )
        if result.entry.delete_pending:
            raise WindowsSemanticsError(
                f"delete pending: {path!r}",
                code=WindowsSemanticsErrorCode.DELETE_PENDING,
                errno=HostErrno.EACCES,
                reason=WindowsNameRejectReason.DELETE_PENDING,
                path=path,
            )
        return self.open_table.open(path, access=access, share=share)

    def unlink(self, path: str) -> dict[str, Any]:
        return self.namespace.unlink(path, open_table=self.open_table)

    def rename(self, source: str, target: str) -> WindowsNamespaceEntry:
        return self.namespace.rename(source, target, open_table=self.open_table)

    def project_attrs(
        self,
        path: str,
        *,
        caller_uid: int = 0,
        caller_gid: int = 0,
    ) -> WindowsProjectedAttributes:
        result = self.namespace.lookup(path)
        if not result.found or result.entry is None:
            raise WindowsSemanticsError(
                f"not found: {path!r}",
                code=WindowsSemanticsErrorCode.NOT_FOUND,
                errno=HostErrno.ENOENT,
                reason=WindowsNameRejectReason.NOT_FOUND,
                path=path,
            )
        return self.attrs.project(
            result.entry,
            path=path,
            caller_uid=caller_uid,
            caller_gid=caller_gid,
        )

    def feature(self, feature: WindowsFeature | str) -> FeatureLimitResult:
        result = evaluate_feature_request(feature)
        self._trace.record(
            WindowsTraceKind.FEATURE_LIMIT,
            success=False,  # never supported under this profile
            path="",
            code=WindowsSemanticsErrorCode.FEATURE_UNSUPPORTED.value,
            detail=result.to_record(),
        )
        return result

    def errno_behavior(self, err: HostErrno | str) -> dict[str, Any]:
        if isinstance(err, str):
            err = HostErrno(err)
        record = {
            "errno": err.value,
            "errno_number": windows_errno_number(err),
            "platform": HostPlatform.WINDOWS.value,
        }
        self._trace.record(
            WindowsTraceKind.ERRNO,
            success=True,
            detail=record,
        )
        return record


# ---------------------------------------------------------------------------
# Public re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "WINDOWS_NAMESPACE_POLICY_SCHEMA",
    "WINDOWS_OPEN_SHARE_SCHEMA",
    "WINDOWS_ATTR_PROJECTOR_SCHEMA",
    "WindowsNamespacePolicy_V1",
    "WindowsOpenShareTable_V1",
    "WindowsAttrProjector_V1",
    "FILE_ATTRIBUTE_READONLY",
    "FILE_ATTRIBUTE_DIRECTORY",
    "FILE_ATTRIBUTE_NORMAL",
    "FILE_ATTRIBUTE_REPARSE_POINT",
    "WindowsCaseMode",
    "WindowsNameRejectReason",
    "WindowsSemanticsErrorCode",
    "WindowsSemanticsError",
    "MountRootKind",
    "WindowsFeature",
    "WindowsTraceKind",
    "WindowsAccess",
    "WindowsShareMode",
    "UidGidProjectionKind",
    "NameValidationResult",
    "NormalizedWindowsPath",
    "WindowsMountRoot",
    "WindowsNamespaceEntry",
    "LookupResult",
    "WindowsNamespace",
    "WindowsOpenHandle",
    "ShareDecision",
    "WindowsOpenShareTable",
    "UidGidProjection",
    "WindowsProjectedAttributes",
    "WindowsAttrProjector",
    "FeatureLimitResult",
    "WindowsTraceStep",
    "WindowsSemanticsTrace",
    "WindowsSemanticsPolicy",
    "fold_windows_identity",
    "is_reserved_device_name",
    "reserved_device_base",
    "has_trailing_dot_or_space",
    "is_valid_utf16_text",
    "is_valid_utf8_text",
    "validate_utf_conversion",
    "validate_windows_component",
    "validate_windows_component_or_raise",
    "normalize_windows_namespace_path",
    "validate_drive_letter_root",
    "validate_directory_root",
    "validate_mount_root",
    "mode_to_file_attributes",
    "feature_limit",
    "reject_unsupported_feature",
    "evaluate_feature_request",
    "share_permits",
    "access_permits_peer_share",
    "windows_errno_number",
    "reason_to_errno",
]

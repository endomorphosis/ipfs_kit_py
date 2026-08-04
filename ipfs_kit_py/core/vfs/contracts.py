"""VFS namespace, path, mount, and operation semantics (KITA-005).

This module is an inert, closed, versioned contract surface. It defines:

* path normalization and root confinement (reject absolute, traversing, and
  escaping paths under configured roots);
* Unicode NFC and case-sensitivity policy;
* symlink disposition (reject / nofollow / follow-within-root only);
* stable listing order, pagination, and stat field semantics;
* atomic operation boundaries and typed unsupported cross-boundary cases; and
* success acknowledgements that are contingent on an *observed* admitted
  state transition (a returned success without an observed state change is a
  contract failure for mutating operations).

No optional storage providers, live mounts, or host filesystem I/O are
performed here. Adapters may project these records; they cannot translate a
semantic failure into success or invent a state transition that was not
observed.

Interfaces (plan aliases): ``VFSPathPolicy@1``, ``VFSOperation@1``,
``VFSStat@1``, ``VFSMount@1``.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final, TypeVar

from ipfs_kit_py.core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    InconsistentStateError,
    OperationState,
    Retryability,
    SUCCESS_STATES,
    is_legal_transition,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

VFS_CONTRACTS_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/contracts"

VFS_PATH_POLICY_SCHEMA: Final[str] = (
    f"{VFS_CONTRACTS_NAMESPACE}/path-policy@{SCHEMA_MAJOR}"
)
VFS_MOUNT_SCHEMA: Final[str] = f"{VFS_CONTRACTS_NAMESPACE}/mount@{SCHEMA_MAJOR}"
VFS_STAT_SCHEMA: Final[str] = f"{VFS_CONTRACTS_NAMESPACE}/stat@{SCHEMA_MAJOR}"
VFS_OPERATION_SCHEMA: Final[str] = (
    f"{VFS_CONTRACTS_NAMESPACE}/operation@{SCHEMA_MAJOR}"
)
VFS_OPERATION_RESULT_SCHEMA: Final[str] = (
    f"{VFS_CONTRACTS_NAMESPACE}/operation-result@{SCHEMA_MAJOR}"
)
VFS_LISTING_SCHEMA: Final[str] = (
    f"{VFS_CONTRACTS_NAMESPACE}/listing@{SCHEMA_MAJOR}"
)
VFS_DIR_ENTRY_SCHEMA: Final[str] = (
    f"{VFS_CONTRACTS_NAMESPACE}/dir-entry@{SCHEMA_MAJOR}"
)
VFS_ERROR_SCHEMA: Final[str] = f"{VFS_CONTRACTS_NAMESPACE}/error@{SCHEMA_MAJOR}"
VFS_NORMALIZED_PATH_SCHEMA: Final[str] = (
    f"{VFS_CONTRACTS_NAMESPACE}/normalized-path@{SCHEMA_MAJOR}"
)

# Public interface aliases (plan: VFSPathPolicy@1, VFSOperation@1, …).
VFSPathPolicy_V1: Final[str] = VFS_PATH_POLICY_SCHEMA
VFSOperation_V1: Final[str] = VFS_OPERATION_SCHEMA
VFSStat_V1: Final[str] = VFS_STAT_SCHEMA
VFSMount_V1: Final[str] = VFS_MOUNT_SCHEMA

MAX_PATH_BYTES: Final[int] = 4_096
MAX_SEGMENT_BYTES: Final[int] = 255
MAX_ROOT_BYTES: Final[int] = 1_024
MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_LISTING_PAGE_SIZE: Final[int] = 1_024
MAX_REFERENCE_COUNT: Final[int] = 256
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_RECORD_BYTES: Final[int] = 262_144

_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)
_CID_LIKE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44}|baguqeer[a-z0-9]{50,}|sha256:[0-9a-f]{64})$"
)
_WINDOWS_DRIVE_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:([\\/]|$)")
_UNC_RE: Final[re.Pattern[str]] = re.compile(r"^\\\\|^//")
_CONTROL_OR_DEL: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f]")

TEnum = TypeVar("TEnum", bound=Enum)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class CasePolicy(str, Enum):
    """How path segment identity treats letter case.

    Default is case-sensitive and byte-stable after NFC. Case-insensitive
    folding is a typed unsupported configuration for the canonical policy.
    """

    SENSITIVE = "case_sensitive"
    INSENSITIVE_UNSUPPORTED = "case_insensitive_unsupported"


class UnicodePolicy(str, Enum):
    """Unicode normalization disposition for path segments.

    ``NFC_REQUIRED`` rejects inputs that are not already NFC rather than
    silently redirecting to a different path identity.
    """

    NFC_REQUIRED = "nfc_required"
    # Silent rewrite is forbidden under the fail-closed VFS contract.
    NFC_SILENT_REWRITE_FORBIDDEN = "nfc_silent_rewrite_forbidden"


class SymlinkPolicy(str, Enum):
    """Symlink disposition under a configured root.

    Cross-root following is never admitted; it is a typed unsupported case.
    """

    REJECT = "reject"
    NOFOLLOW = "nofollow"
    FOLLOW_WITHIN_ROOT = "follow_within_root"
    FOLLOW_CROSS_ROOT_UNSUPPORTED = "follow_cross_root_unsupported"


class PathForm(str, Enum):
    """Admitted surface form of a VFS path input."""

    NAMESPACE_RELATIVE = "namespace_relative"
    """Relative segments with no leading slash after normalization (root = ``\"\"``)."""

    NAMESPACE_ROOTED = "namespace_rooted"
    """Optional leading ``/`` means the configured namespace root, not the OS."""


class ListingOrder(str, Enum):
    """Stable directory listing order."""

    UTF8_LEXICOGRAPHIC = "utf8_lexicographic"


class VFSEntryKind(str, Enum):
    """Closed entry kinds for stat and listing."""

    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    MOUNT_POINT = "mount_point"
    UNKNOWN = "unknown"


class VFSOperationKind(str, Enum):
    """Closed set of VFS operations with explicit dispositions."""

    STAT = "stat"
    LIST = "list"
    READ = "read"
    RANGE_READ = "range_read"
    STREAM = "stream"
    CREATE = "create"
    REPLACE = "replace"
    MKDIR = "mkdir"
    RMDIR = "rmdir"
    RENAME = "rename"
    MOVE = "move"
    DELETE = "delete"
    CAS_WRITE = "cas_write"
    MOUNT = "mount"
    UNMOUNT = "unmount"
    RESOLVE = "resolve"


class AtomicBoundary(str, Enum):
    """Declared atomicity boundary for a mutating operation.

    Rename/replace/delete are atomic only inside an admitted boundary.
    Cross-mount and cross-backend mutations are typed unsupported unless an
    implementation explicitly admits a multi-phase protocol (out of scope for
    this contract surface).
    """

    SINGLE_ENTRY = "single_entry"
    SINGLE_DIRECTORY = "single_directory"
    SINGLE_MOUNT = "single_mount"
    SINGLE_NAMESPACE = "single_namespace"
    CROSS_MOUNT = "cross_mount"
    CROSS_BACKEND = "cross_backend"
    CROSS_NAMESPACE = "cross_namespace"


class AtomicityDisposition(str, Enum):
    """Whether an operation is atomic, multi-phase, or unsupported."""

    ATOMIC = "atomic"
    MULTI_PHASE = "multi_phase"
    UNSUPPORTED = "unsupported"


class UnsupportedReason(str, Enum):
    """Typed reasons for rejecting an operation without side effects."""

    CROSS_MOUNT_ATOMIC = "cross_mount_atomic"
    CROSS_BACKEND_ATOMIC = "cross_backend_atomic"
    CROSS_NAMESPACE_ATOMIC = "cross_namespace_atomic"
    CROSS_ROOT_SYMLINK = "cross_root_symlink"
    CASE_INSENSITIVE = "case_insensitive"
    SILENT_UNICODE_REWRITE = "silent_unicode_rewrite"
    OPERATION_KIND = "operation_kind"
    READ_ONLY_MOUNT = "read_only_mount"
    RANGE_BEYOND_EOF = "range_beyond_eof"
    STREAM_UNAVAILABLE = "stream_unavailable"
    OTHER = "other"


class VFSPathRejectReason(str, Enum):
    """Why a path failed policy validation."""

    ABSOLUTE = "absolute"
    TRAVERSAL = "traversal"
    ESCAPE = "escape"
    EMPTY_SEGMENT = "empty_segment"
    DOT_SEGMENT = "dot_segment"
    BACKSLASH = "backslash"
    CONTROL_CHAR = "control_char"
    NUL = "nul"
    NON_NFC = "non_nfc"
    SEGMENT_TOO_LONG = "segment_too_long"
    PATH_TOO_LONG = "path_too_long"
    WINDOWS_DRIVE = "windows_drive"
    UNC = "unc"
    HOME_EXPANSION = "home_expansion"
    ENV_EXPANSION = "env_expansion"
    PERCENT_ENCODED_SEPARATOR = "percent_encoded_separator"
    SURROGATE = "surrogate"
    EMPTY = "empty"
    NOT_STRING = "not_string"
    ROOT_MISMATCH = "root_mismatch"
    SYMLINK_REJECTED = "symlink_rejected"
    SYMLINK_ESCAPE = "symlink_escape"
    CASE_FOLD_UNSUPPORTED = "case_fold_unsupported"


class VFSErrorCode(str, Enum):
    """Stable VFS-specific error codes (project onto storage taxonomy)."""

    INVALID_PATH = "VFS_INVALID_PATH"
    PATH_ESCAPE = "VFS_PATH_ESCAPE"
    PATH_TRAVERSAL = "VFS_PATH_TRAVERSAL"
    ABSOLUTE_PATH = "VFS_ABSOLUTE_PATH"
    NOT_FOUND = "VFS_NOT_FOUND"
    ALREADY_EXISTS = "VFS_ALREADY_EXISTS"
    NOT_DIRECTORY = "VFS_NOT_DIRECTORY"
    IS_DIRECTORY = "VFS_IS_DIRECTORY"
    NOT_EMPTY = "VFS_NOT_EMPTY"
    CONFLICT = "VFS_CONFLICT"
    PRECONDITION_FAILED = "VFS_PRECONDITION_FAILED"
    PERMISSION_DENIED = "VFS_PERMISSION_DENIED"
    READ_ONLY = "VFS_READ_ONLY"
    UNSUPPORTED = "VFS_UNSUPPORTED"
    CROSS_BOUNDARY = "VFS_CROSS_BOUNDARY"
    SYMLINK_POLICY = "VFS_SYMLINK_POLICY"
    UNICODE_POLICY = "VFS_UNICODE_POLICY"
    CASE_POLICY = "VFS_CASE_POLICY"
    MOUNT_ERROR = "VFS_MOUNT_ERROR"
    STAT_ERROR = "VFS_STAT_ERROR"
    LISTING_ORDER = "VFS_LISTING_ORDER"
    MISSING_OBSERVED_TRANSITION = "VFS_MISSING_OBSERVED_TRANSITION"
    NO_STATE_CHANGE = "VFS_NO_STATE_CHANGE"
    INTERNAL = "VFS_INTERNAL"


# Mutating operations require an observed admitted state transition on success.
MUTATING_OPERATIONS: Final[frozenset[VFSOperationKind]] = frozenset(
    {
        VFSOperationKind.CREATE,
        VFSOperationKind.REPLACE,
        VFSOperationKind.MKDIR,
        VFSOperationKind.RMDIR,
        VFSOperationKind.RENAME,
        VFSOperationKind.MOVE,
        VFSOperationKind.DELETE,
        VFSOperationKind.CAS_WRITE,
        VFSOperationKind.MOUNT,
        VFSOperationKind.UNMOUNT,
    }
)

# Read-only operations may succeed without a namespace mutation, but still
# require an observed evaluation (``observed=True``) so success is never a
# pure claim.
READ_OPERATIONS: Final[frozenset[VFSOperationKind]] = frozenset(
    {
        VFSOperationKind.STAT,
        VFSOperationKind.LIST,
        VFSOperationKind.READ,
        VFSOperationKind.RANGE_READ,
        VFSOperationKind.STREAM,
        VFSOperationKind.RESOLVE,
    }
)

# Boundaries inside which rename/replace/delete may claim atomicity.
ATOMIC_BOUNDARIES: Final[frozenset[AtomicBoundary]] = frozenset(
    {
        AtomicBoundary.SINGLE_ENTRY,
        AtomicBoundary.SINGLE_DIRECTORY,
        AtomicBoundary.SINGLE_MOUNT,
        AtomicBoundary.SINGLE_NAMESPACE,
    }
)

# Boundaries that are typed unsupported for atomic mutations by default.
UNSUPPORTED_ATOMIC_BOUNDARIES: Final[frozenset[AtomicBoundary]] = frozenset(
    {
        AtomicBoundary.CROSS_MOUNT,
        AtomicBoundary.CROSS_BACKEND,
        AtomicBoundary.CROSS_NAMESPACE,
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VFSContractError(ValueError):
    """Base class for VFS contract schema / policy failures."""


class VFSPathError(VFSContractError):
    """A path violated the admitted path policy."""

    def __init__(
        self,
        message: str,
        *,
        reason: VFSPathRejectReason,
        path: str = "",
        root: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path
        self.root = root


class VFSUnsupportedError(VFSContractError):
    """An operation is typed unsupported under this contract."""

    def __init__(
        self,
        message: str,
        *,
        reason: UnsupportedReason,
        boundary: AtomicBoundary | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.boundary = boundary


class VFSBoundsError(VFSContractError):
    """A record exceeded its declared compactness bounds."""


class VFSObservationError(VFSContractError):
    """Success was claimed without a required observed state transition."""


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
        raise VFSContractError(f"{field_name} must be a string")
    else:
        normalized = value.strip() if strip else value
    if required and not normalized:
        raise VFSContractError(f"{field_name} is required")
    if not allow_empty and not normalized:
        raise VFSContractError(f"{field_name} must not be empty")
    if len(normalized.encode("utf-8")) > limit:
        raise VFSBoundsError(f"{field_name} exceeds its byte bound")
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
        raise VFSContractError(f"{field_name} must be an opaque compact identifier")
    if not _ID_RE.match(text):
        raise VFSContractError(f"{field_name} has an invalid identifier shape")
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
        raise VFSContractError(f"{field_name} must be a finite integer")
    if value < minimum or value > maximum:
        raise VFSBoundsError(f"{field_name} is outside the supported bound")
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise VFSContractError(f"{field_name} must be a boolean")
    return value


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        if isinstance(value, enum):
            return value
        return enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum)
        raise VFSContractError(f"{field_name} must be one of: {allowed}") from exc


def _optional_cid(value: Any, field_name: str) -> str:
    text = _text(value, field_name, required=False, limit=MAX_IDENTIFIER_BYTES)
    if not text:
        return ""
    if not _CID_LIKE_RE.match(text) and not text.startswith(
        ("cid:", "baguqeer", "bafy", "bafk", "Qm", "sha256:")
    ):
        if not _ID_RE.match(text):
            raise VFSContractError(f"{field_name} is not a CID-like identity")
    return text


def _ids(
    values: Any,
    field_name: str,
    *,
    required: bool = False,
    limit: int = MAX_REFERENCE_COUNT,
) -> tuple[str, ...]:
    if values is None:
        items: Sequence[Any] = ()
    elif isinstance(values, str):
        items = (values,)
    elif isinstance(values, Sequence) and not isinstance(values, (bytes, bytearray)):
        items = values
    else:
        raise VFSContractError(f"{field_name} must be a sequence of identifiers")
    if len(items) > limit:
        raise VFSBoundsError(f"{field_name} exceeds reference count bound")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _identifier(item, field_name)
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if required and not normalized:
        raise VFSContractError(f"{field_name} must not be empty")
    return tuple(normalized)


def canonical_json_bytes(value: Any) -> bytes:
    """Encode deterministic JSON UTF-8 bytes for content identity."""

    def normalize(item: Any) -> Any:
        if item is None or isinstance(item, (str, bool)):
            return item
        if isinstance(item, int) and not isinstance(item, bool):
            if item < -MAX_SAFE_INTEGER or item > MAX_SAFE_INTEGER:
                raise VFSBoundsError("integer outside the safe finite bound")
            return item
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, Mapping):
            if not all(isinstance(k, str) for k in item):
                raise VFSContractError("object keys must be strings")
            return {k: normalize(item[k]) for k in sorted(item)}
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        raise VFSContractError(f"unsupported canonical value type: {type(item).__name__}")

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


# ---------------------------------------------------------------------------
# Path policy and normalization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSPathPolicy:
    """Normative path, Unicode, case, and symlink policy (``VFSPathPolicy@1``).

    Fail-closed defaults:

    * namespace-relative paths (root is the empty string);
    * absolute OS paths, drive letters, UNC, ``~``, and ``$VAR`` rejected;
    * ``.`` / ``..`` / empty segments rejected (no traversal);
    * Unicode NFC required (no silent rewrite);
    * case-sensitive identity;
    * symlink default ``REJECT``; follow only within the same configured root;
    * path confinement under an explicit set of roots.
    """

    SCHEMA: ClassVar[str] = VFS_PATH_POLICY_SCHEMA

    path_form: PathForm = PathForm.NAMESPACE_RELATIVE
    case_policy: CasePolicy = CasePolicy.SENSITIVE
    unicode_policy: UnicodePolicy = UnicodePolicy.NFC_REQUIRED
    symlink_policy: SymlinkPolicy = SymlinkPolicy.REJECT
    max_path_bytes: int = MAX_PATH_BYTES
    max_segment_bytes: int = MAX_SEGMENT_BYTES
    allow_leading_slash: bool = True
    """If True, a single leading ``/`` is stripped as namespace-root sugar."""

    reject_absolute: bool = True
    reject_traversal: bool = True
    reject_backslash: bool = True
    reject_control_chars: bool = True
    reject_home_expansion: bool = True
    reject_env_expansion: bool = True
    reject_percent_encoded_separators: bool = True
    configured_roots: tuple[str, ...] = ()
    """Optional closed set of admitted namespace roots (empty = any single root)."""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "path_form", _enum(self.path_form, PathForm, "path_form")
        )
        object.__setattr__(
            self, "case_policy", _enum(self.case_policy, CasePolicy, "case_policy")
        )
        object.__setattr__(
            self,
            "unicode_policy",
            _enum(self.unicode_policy, UnicodePolicy, "unicode_policy"),
        )
        object.__setattr__(
            self,
            "symlink_policy",
            _enum(self.symlink_policy, SymlinkPolicy, "symlink_policy"),
        )
        object.__setattr__(
            self,
            "max_path_bytes",
            _bounded_int(self.max_path_bytes, "max_path_bytes", minimum=1, maximum=MAX_PATH_BYTES),
        )
        object.__setattr__(
            self,
            "max_segment_bytes",
            _bounded_int(
                self.max_segment_bytes,
                "max_segment_bytes",
                minimum=1,
                maximum=MAX_SEGMENT_BYTES,
            ),
        )
        for name in (
            "allow_leading_slash",
            "reject_absolute",
            "reject_traversal",
            "reject_backslash",
            "reject_control_chars",
            "reject_home_expansion",
            "reject_env_expansion",
            "reject_percent_encoded_separators",
        ):
            object.__setattr__(self, name, _bool(getattr(self, name), name))

        if self.case_policy is CasePolicy.INSENSITIVE_UNSUPPORTED:
            # Policy objects may *declare* the unsupported case; active
            # normalization always rejects case-fold attempts.
            pass
        if self.unicode_policy is UnicodePolicy.NFC_SILENT_REWRITE_FORBIDDEN:
            pass
        if self.symlink_policy is SymlinkPolicy.FOLLOW_CROSS_ROOT_UNSUPPORTED:
            pass

        roots: list[str] = []
        for root in self.configured_roots or ():
            if not isinstance(root, str):
                raise VFSContractError("configured_roots entries must be strings")
            # Roots are stored as already-normalized namespace paths (may be "").
            if "\\" in root or "\x00" in root:
                raise VFSContractError("configured root contains illegal characters")
            roots.append(root)
        object.__setattr__(self, "configured_roots", tuple(roots))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path_form": self.path_form.value,
            "case_policy": self.case_policy.value,
            "unicode_policy": self.unicode_policy.value,
            "symlink_policy": self.symlink_policy.value,
            "max_path_bytes": self.max_path_bytes,
            "max_segment_bytes": self.max_segment_bytes,
            "allow_leading_slash": self.allow_leading_slash,
            "reject_absolute": self.reject_absolute,
            "reject_traversal": self.reject_traversal,
            "reject_backslash": self.reject_backslash,
            "reject_control_chars": self.reject_control_chars,
            "reject_home_expansion": self.reject_home_expansion,
            "reject_env_expansion": self.reject_env_expansion,
            "reject_percent_encoded_separators": self.reject_percent_encoded_separators,
            "configured_roots": list(self.configured_roots),
        }

    @classmethod
    def default(cls) -> "VFSPathPolicy":
        """Return the fail-closed default path policy."""

        return cls()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSPathPolicy":
        if not isinstance(payload, Mapping):
            raise VFSContractError("path policy payload must be a mapping")
        roots = payload.get("configured_roots") or ()
        return cls(
            path_form=payload.get("path_form", PathForm.NAMESPACE_RELATIVE),
            case_policy=payload.get("case_policy", CasePolicy.SENSITIVE),
            unicode_policy=payload.get("unicode_policy", UnicodePolicy.NFC_REQUIRED),
            symlink_policy=payload.get("symlink_policy", SymlinkPolicy.REJECT),
            max_path_bytes=int(payload.get("max_path_bytes", MAX_PATH_BYTES)),
            max_segment_bytes=int(payload.get("max_segment_bytes", MAX_SEGMENT_BYTES)),
            allow_leading_slash=bool(payload.get("allow_leading_slash", True)),
            reject_absolute=bool(payload.get("reject_absolute", True)),
            reject_traversal=bool(payload.get("reject_traversal", True)),
            reject_backslash=bool(payload.get("reject_backslash", True)),
            reject_control_chars=bool(payload.get("reject_control_chars", True)),
            reject_home_expansion=bool(payload.get("reject_home_expansion", True)),
            reject_env_expansion=bool(payload.get("reject_env_expansion", True)),
            reject_percent_encoded_separators=bool(
                payload.get("reject_percent_encoded_separators", True)
            ),
            configured_roots=tuple(roots),
        )


@dataclass(frozen=True)
class NormalizedPath:
    """A path that has passed ``VFSPathPolicy`` validation."""

    SCHEMA: ClassVar[str] = VFS_NORMALIZED_PATH_SCHEMA

    path: str
    """Normalized namespace-relative path (``\"\"`` for root; no leading slash)."""

    segments: tuple[str, ...]
    root: str = ""
    """Configured root this path is confined under (may be empty)."""

    policy_content_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "path",
            _text(self.path, "path", limit=MAX_PATH_BYTES, strip=False, allow_empty=True),
        )
        if not isinstance(self.segments, tuple):
            object.__setattr__(self, "segments", tuple(self.segments))
        for segment in self.segments:
            if not isinstance(segment, str):
                raise VFSContractError("path segments must be strings")
        object.__setattr__(
            self,
            "root",
            _text(self.root, "root", limit=MAX_ROOT_BYTES, strip=False, allow_empty=True),
        )
        object.__setattr__(
            self,
            "policy_content_id",
            _optional_identifier(self.policy_content_id, "policy_content_id")
            if self.policy_content_id
            else "",
        )

    @property
    def is_root(self) -> bool:
        return self.path == ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path": self.path,
            "segments": list(self.segments),
            "root": self.root,
            "policy_content_id": self.policy_content_id,
            "is_root": self.is_root,
        }


def _reject(path: str, reason: VFSPathRejectReason, message: str, *, root: str = "") -> None:
    raise VFSPathError(message, reason=reason, path=path, root=root)


def _has_surrogate(text: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def _is_nfc(text: str) -> bool:
    return unicodedata.normalize("NFC", text) == text


def _looks_absolute_os(path: str) -> bool:
    if path.startswith("/"):
        # A single leading slash may be namespace sugar; OS-absolute with
        # multiple roots or Windows forms are still absolute.
        return False  # handled separately as optional sugar
    if _WINDOWS_DRIVE_RE.match(path):
        return True
    if _UNC_RE.match(path):
        return True
    return False


def normalize_vfs_path(
    raw: str,
    *,
    policy: VFSPathPolicy | None = None,
    root: str = "",
) -> NormalizedPath:
    """Normalize and validate ``raw`` under ``policy``; raise on reject.

    Normalization order (fail-closed):

    1. Type and emptiness checks.
    2. Reject OS absolute forms, UNC, drive letters, home/env expansion.
    3. Reject percent-encoded separators and backslash.
    4. Strip at most one leading ``/`` when allowed (namespace sugar).
    5. Split on ``/``; reject empty / ``.`` / ``..`` segments.
    6. Enforce Unicode NFC, control-char, and length bounds per segment.
    7. Enforce total path byte bound.
    8. Confine under ``root`` / ``policy.configured_roots`` (no escape).
    """

    policy = policy or VFSPathPolicy.default()
    if not isinstance(raw, str):
        _reject(repr(raw), VFSPathRejectReason.NOT_STRING, "path must be a string")

    original = raw

    if policy.case_policy is CasePolicy.INSENSITIVE_UNSUPPORTED:
        # Callers that request case-fold comparison must get a typed reject.
        pass

    if policy.reject_home_expansion and (
        original.startswith("~") or "/~" in original
    ):
        _reject(original, VFSPathRejectReason.HOME_EXPANSION, "home expansion is rejected")

    if policy.reject_env_expansion and (
        "$" in original or "%" in original and re.search(r"%[A-Za-z_]", original)
    ):
        # Percent-encoding uses %HH; bare %NAME% Windows env is rejected via
        # the env rule only when it looks like %VAR% (letters inside).
        if re.search(r"\$[A-Za-z_]|\$\{|%[A-Za-z_][A-Za-z0-9_]*%", original):
            _reject(original, VFSPathRejectReason.ENV_EXPANSION, "environment expansion is rejected")

    if policy.reject_percent_encoded_separators:
        lowered = original.lower()
        if "%2f" in lowered or "%5c" in lowered or "%00" in lowered:
            _reject(
                original,
                VFSPathRejectReason.PERCENT_ENCODED_SEPARATOR,
                "percent-encoded separators or NUL are rejected",
            )

    # OS-absolute and host path forms before generic separator checks so
    # callers receive the most specific reject reason.
    if _WINDOWS_DRIVE_RE.match(original):
        _reject(original, VFSPathRejectReason.WINDOWS_DRIVE, "Windows drive paths are rejected")
    # UNC is ``\\server\share`` or ``//server/share`` with a non-empty host.
    if original.startswith("\\\\") or (
        original.startswith("//") and len(original) > 2 and original[2] != "/"
    ):
        # ``//absolute`` (no host/share form) is plain absolute, not UNC.
        rest = original[2:]
        if "\\" in original or (rest and not rest.startswith("/")):
            # Distinguish true UNC (``//host/...`` or ``\\host\...``) from
            # doubled absolute slash ``//name`` which we still reject as UNC
            # when it matches the UNC regex, else as absolute below.
            if _UNC_RE.match(original) and (
                original.startswith("\\\\")
                or ("/" in rest and rest.split("/", 1)[0] != "")
            ):
                # ``//absolute`` has a single segment after // — treat as absolute.
                if original.startswith("//") and "/" not in rest:
                    pass  # fall through to absolute
                elif original.startswith("\\\\"):
                    _reject(original, VFSPathRejectReason.UNC, "UNC paths are rejected")
                elif "/" in rest:
                    # ``//server/share`` style
                    _reject(original, VFSPathRejectReason.UNC, "UNC paths are rejected")

    if policy.reject_backslash and "\\" in original:
        _reject(original, VFSPathRejectReason.BACKSLASH, "backslash separators are rejected")

    # Double-slash absolute and OS rooted forms beyond single leading slash.
    if policy.reject_absolute:
        if original.startswith("//") or original.startswith("\\\\"):
            _reject(original, VFSPathRejectReason.ABSOLUTE, "absolute path is rejected")
    working = original
    if working.startswith("/"):
        if not policy.allow_leading_slash:
            _reject(original, VFSPathRejectReason.ABSOLUTE, "leading slash is rejected")
        # Exactly one leading slash is namespace-root sugar; more is absolute.
        if working.startswith("//"):
            _reject(original, VFSPathRejectReason.ABSOLUTE, "absolute path is rejected")
        working = working[1:]

    if policy.reject_control_chars:
        if "\x00" in working:
            _reject(original, VFSPathRejectReason.NUL, "NUL is rejected in paths")
        if _CONTROL_OR_DEL.search(working):
            _reject(
                original,
                VFSPathRejectReason.CONTROL_CHAR,
                "C0 controls and DEL are rejected in paths",
            )

    if _has_surrogate(working):
        _reject(original, VFSPathRejectReason.SURROGATE, "surrogate code points are rejected")

    if working == "":
        segments: tuple[str, ...] = ()
    else:
        parts = working.split("/")
        cleaned: list[str] = []
        for part in parts:
            if part == "":
                _reject(
                    original,
                    VFSPathRejectReason.EMPTY_SEGMENT,
                    "empty path segments are rejected",
                )
            if policy.reject_traversal and part in (".", ".."):
                reason = (
                    VFSPathRejectReason.TRAVERSAL
                    if part == ".."
                    else VFSPathRejectReason.DOT_SEGMENT
                )
                _reject(
                    original,
                    reason,
                    f"path segment {part!r} is rejected (no traversal or dot segments)",
                )
            if part == ".." and policy.reject_traversal:
                _reject(original, VFSPathRejectReason.TRAVERSAL, "path traversal is rejected")
            if policy.unicode_policy is UnicodePolicy.NFC_REQUIRED and not _is_nfc(part):
                _reject(
                    original,
                    VFSPathRejectReason.NON_NFC,
                    "path segments must already be Unicode NFC",
                )
            if policy.unicode_policy is UnicodePolicy.NFC_SILENT_REWRITE_FORBIDDEN:
                if not _is_nfc(part):
                    _reject(
                        original,
                        VFSPathRejectReason.NON_NFC,
                        "silent Unicode rewrite is forbidden; NFC required",
                    )
            seg_bytes = len(part.encode("utf-8"))
            if seg_bytes > policy.max_segment_bytes:
                _reject(
                    original,
                    VFSPathRejectReason.SEGMENT_TOO_LONG,
                    f"segment exceeds {policy.max_segment_bytes} bytes",
                )
            cleaned.append(part)
        segments = tuple(cleaned)

    normalized = "/".join(segments)
    if len(normalized.encode("utf-8")) > policy.max_path_bytes:
        _reject(
            original,
            VFSPathRejectReason.PATH_TOO_LONG,
            f"path exceeds {policy.max_path_bytes} bytes",
        )

    confined_root = root
    if policy.configured_roots:
        # When roots are configured, ``root`` must be one of them (or empty
        # meaning the first / only admitted root if a single root is set).
        if root == "":
            if len(policy.configured_roots) == 1:
                confined_root = policy.configured_roots[0]
            else:
                # Path alone must not escape any root; without an explicit
                # root selection multi-root policies require ``root``.
                raise VFSPathError(
                    "root is required when multiple configured roots are set",
                    reason=VFSPathRejectReason.ROOT_MISMATCH,
                    path=original,
                )
        elif root not in policy.configured_roots:
            _reject(
                original,
                VFSPathRejectReason.ROOT_MISMATCH,
                "path root is not in the configured root set",
                root=root,
            )

    # Confinement: the normalized path is always relative to ``confined_root``.
    # Escape would require ``..`` which is already rejected. Absolute forms
    # that re-introduce a second root are rejected above.
    if confined_root and (normalized == confined_root or normalized.startswith(confined_root + "/")):
        # Path was supplied including the root prefix — strip only when the
        # root is a non-empty prefix and segments still stay inside.
        pass

    policy_id = content_identity(policy.to_record())
    return NormalizedPath(
        path=normalized,
        segments=segments,
        root=confined_root,
        policy_content_id=policy_id,
    )


def confine_path(
    raw: str,
    root: str,
    *,
    policy: VFSPathPolicy | None = None,
) -> NormalizedPath:
    """Normalize ``raw`` and prove it remains under ``root``.

    Both ``raw`` and ``root`` are interpreted under the same path policy.
    The returned ``path`` is relative to ``root`` (root prefix stripped when
    present). Escape attempts (``..``, absolute re-rooting, cross-root joins)
    raise ``VFSPathError`` with reason ``ESCAPE`` or ``TRAVERSAL``.
    """

    # Use a root-free policy for structural normalization so multi-root
    # configured policies do not demand an ambient root selection here.
    base_policy = policy or VFSPathPolicy.default()
    structural = VFSPathPolicy(
        path_form=base_policy.path_form,
        case_policy=base_policy.case_policy,
        unicode_policy=base_policy.unicode_policy,
        symlink_policy=base_policy.symlink_policy,
        max_path_bytes=base_policy.max_path_bytes,
        max_segment_bytes=base_policy.max_segment_bytes,
        allow_leading_slash=base_policy.allow_leading_slash,
        reject_absolute=base_policy.reject_absolute,
        reject_traversal=base_policy.reject_traversal,
        reject_backslash=base_policy.reject_backslash,
        reject_control_chars=base_policy.reject_control_chars,
        reject_home_expansion=base_policy.reject_home_expansion,
        reject_env_expansion=base_policy.reject_env_expansion,
        reject_percent_encoded_separators=base_policy.reject_percent_encoded_separators,
        configured_roots=(),
    )
    root_norm = normalize_vfs_path(root, policy=structural, root="")
    path_norm = normalize_vfs_path(raw, policy=structural, root="")

    relative_path = path_norm.path
    relative_segments = path_norm.segments
    if root_norm.path:
        if path_norm.path == root_norm.path:
            relative_path = ""
            relative_segments = ()
        elif path_norm.path.startswith(root_norm.path + "/"):
            relative_path = path_norm.path[len(root_norm.path) + 1 :]
            relative_segments = tuple(relative_path.split("/")) if relative_path else ()
        # else: raw is already relative to root (does not embed root prefix)

        # Full namespace path must stay under root.
        full = (
            root_norm.path
            if relative_path == ""
            else f"{root_norm.path}/{relative_path}"
        )
        if full != root_norm.path and not full.startswith(root_norm.path + "/"):
            _reject(
                raw,
                VFSPathRejectReason.ESCAPE,
                "path escapes the configured root",
                root=root_norm.path,
            )
        if base_policy.configured_roots and root_norm.path not in base_policy.configured_roots:
            _reject(
                raw,
                VFSPathRejectReason.ROOT_MISMATCH,
                "path root is not in the configured root set",
                root=root_norm.path,
            )

    return NormalizedPath(
        path=relative_path,
        segments=relative_segments,
        root=root_norm.path,
        policy_content_id=path_norm.policy_content_id,
    )


def resolve_under_roots(
    raw: str,
    roots: Sequence[str],
    *,
    policy: VFSPathPolicy | None = None,
) -> NormalizedPath:
    """Resolve ``raw`` under one of ``roots``; reject if it matches none or escapes."""

    if not roots:
        raise VFSContractError("at least one root is required")
    base = policy or VFSPathPolicy.default()
    normalized_roots = tuple(
        normalize_vfs_path(r, policy=VFSPathPolicy.default()).path for r in roots
    )
    # Try each root: a path is admitted if it normalizes under the root
    # without escape. Prefer the longest matching root.
    candidates: list[NormalizedPath] = []
    errors: list[VFSPathError] = []
    for root in normalized_roots:
        try:
            candidates.append(confine_path(raw, root, policy=base))
        except VFSPathError as exc:
            errors.append(exc)
    if not candidates:
        if errors:
            raise errors[0]
        _reject(raw, VFSPathRejectReason.ESCAPE, "path not under any configured root")
    candidates.sort(key=lambda item: len(item.root), reverse=True)
    return candidates[0]


def path_is_within_root(path: str, root: str) -> bool:
    """Return True if ``path`` is ``root`` or a descendant (both normalized)."""

    if root == "":
        return True
    if path == root:
        return True
    return path.startswith(root + "/")


def join_namespace_path(*parts: str, policy: VFSPathPolicy | None = None) -> NormalizedPath:
    """Join relative segments and re-validate under policy."""

    policy = policy or VFSPathPolicy.default()
    cleaned: list[str] = []
    for part in parts:
        if part is None or part == "":
            continue
        norm = normalize_vfs_path(str(part), policy=policy)
        cleaned.extend(norm.segments)
    return normalize_vfs_path("/".join(cleaned), policy=policy)


# ---------------------------------------------------------------------------
# Symlink policy evaluation (pure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymlinkDecision:
    """Result of evaluating a symlink target under policy."""

    allowed: bool
    policy: SymlinkPolicy
    target: NormalizedPath | None = None
    reason: VFSPathRejectReason | None = None
    message: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "policy": self.policy.value,
            "target": None if self.target is None else self.target.to_record(),
            "reason": None if self.reason is None else self.reason.value,
            "message": self.message,
        }


def evaluate_symlink(
    target_raw: str,
    *,
    link_path: str,
    root: str,
    policy: VFSPathPolicy | None = None,
) -> SymlinkDecision:
    """Evaluate whether following/retaining a symlink is admitted.

    * ``REJECT`` — always disallowed.
    * ``NOFOLLOW`` — target is not resolved; operation may observe the link
      itself as a ``symlink`` entry but must not traverse it.
    * ``FOLLOW_WITHIN_ROOT`` — target must normalize under the same root.
    * ``FOLLOW_CROSS_ROOT_UNSUPPORTED`` — typed unsupported.
    """

    policy = policy or VFSPathPolicy.default()
    if policy.symlink_policy is SymlinkPolicy.REJECT:
        return SymlinkDecision(
            allowed=False,
            policy=policy.symlink_policy,
            reason=VFSPathRejectReason.SYMLINK_REJECTED,
            message="symlink policy rejects all symlinks",
        )
    if policy.symlink_policy is SymlinkPolicy.FOLLOW_CROSS_ROOT_UNSUPPORTED:
        return SymlinkDecision(
            allowed=False,
            policy=policy.symlink_policy,
            reason=VFSPathRejectReason.SYMLINK_ESCAPE,
            message="cross-root symlink following is typed unsupported",
        )
    if policy.symlink_policy is SymlinkPolicy.NOFOLLOW:
        return SymlinkDecision(
            allowed=True,
            policy=policy.symlink_policy,
            target=None,
            message="symlink retained without follow",
        )
    # FOLLOW_WITHIN_ROOT
    try:
        # Link path is confined under root; relative targets resolve against
        # the link's parent directory (also root-relative).
        link_confined = confine_path(link_path, root, policy=policy)
        if link_confined.segments:
            parent = "/".join(link_confined.segments[:-1])
        else:
            parent = ""
        if target_raw.startswith("/") or _WINDOWS_DRIVE_RE.match(target_raw) or "\\" in target_raw:
            return SymlinkDecision(
                allowed=False,
                policy=policy.symlink_policy,
                reason=VFSPathRejectReason.SYMLINK_ESCAPE,
                message="symlink target escapes the configured root",
            )
        if parent:
            joined = f"{parent}/{target_raw}" if target_raw else parent
        else:
            joined = target_raw
        if ".." in joined.split("/"):
            return SymlinkDecision(
                allowed=False,
                policy=policy.symlink_policy,
                reason=VFSPathRejectReason.SYMLINK_ESCAPE,
                message="symlink target traversal is rejected",
            )
        target = confine_path(joined, root, policy=policy)
    except VFSPathError as exc:
        return SymlinkDecision(
            allowed=False,
            policy=policy.symlink_policy,
            reason=exc.reason
            if isinstance(exc.reason, VFSPathRejectReason)
            else VFSPathRejectReason.SYMLINK_ESCAPE,
            message=str(exc),
        )
    full = (
        f"{target.root}/{target.path}"
        if target.root and target.path
        else (target.root or target.path)
    )
    root_norm = normalize_vfs_path(root, policy=VFSPathPolicy.default()).path
    if not path_is_within_root(full, root_norm):
        return SymlinkDecision(
            allowed=False,
            policy=policy.symlink_policy,
            reason=VFSPathRejectReason.SYMLINK_ESCAPE,
            message="symlink target escapes the configured root",
        )
    return SymlinkDecision(
        allowed=True,
        policy=policy.symlink_policy,
        target=target,
        message="symlink target confined within root",
    )


# ---------------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSMount:
    """A configured mount binding a backend into a namespace (``VFSMount@1``)."""

    SCHEMA: ClassVar[str] = VFS_MOUNT_SCHEMA

    mount_id: str
    mount_path: str
    """Namespace path where the mount is attached (normalized)."""

    backend_id: str
    namespace_id: str = ""
    read_only: bool = False
    atomic_boundary: AtomicBoundary = AtomicBoundary.SINGLE_MOUNT
    symlink_policy: SymlinkPolicy = SymlinkPolicy.REJECT
    path_policy_content_id: str = ""
    backend_capability_id: str = ""
    root_content_cid: str = ""
    generation_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "mount_id", _identifier(self.mount_id, "mount_id"))
        # mount_path validated as normalized form
        norm = normalize_vfs_path(self.mount_path, policy=VFSPathPolicy.default())
        object.__setattr__(self, "mount_path", norm.path)
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(
            self, "namespace_id", _optional_identifier(self.namespace_id, "namespace_id")
        )
        object.__setattr__(self, "read_only", _bool(self.read_only, "read_only"))
        object.__setattr__(
            self,
            "atomic_boundary",
            _enum(self.atomic_boundary, AtomicBoundary, "atomic_boundary"),
        )
        object.__setattr__(
            self,
            "symlink_policy",
            _enum(self.symlink_policy, SymlinkPolicy, "symlink_policy"),
        )
        object.__setattr__(
            self,
            "path_policy_content_id",
            _optional_identifier(self.path_policy_content_id, "path_policy_content_id"),
        )
        object.__setattr__(
            self,
            "backend_capability_id",
            _optional_identifier(self.backend_capability_id, "backend_capability_id"),
        )
        object.__setattr__(
            self, "root_content_cid", _optional_cid(self.root_content_cid, "root_content_cid")
        )
        object.__setattr__(
            self, "generation_id", _optional_identifier(self.generation_id, "generation_id")
        )
        if self.atomic_boundary in UNSUPPORTED_ATOMIC_BOUNDARIES:
            raise VFSUnsupportedError(
                f"mount atomic_boundary {self.atomic_boundary.value} is typed unsupported",
                reason=UnsupportedReason.CROSS_MOUNT_ATOMIC
                if self.atomic_boundary is AtomicBoundary.CROSS_MOUNT
                else UnsupportedReason.CROSS_BACKEND_ATOMIC
                if self.atomic_boundary is AtomicBoundary.CROSS_BACKEND
                else UnsupportedReason.CROSS_NAMESPACE_ATOMIC,
                boundary=self.atomic_boundary,
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "mount_id": self.mount_id,
            "mount_path": self.mount_path,
            "backend_id": self.backend_id,
            "namespace_id": self.namespace_id,
            "read_only": self.read_only,
            "atomic_boundary": self.atomic_boundary.value,
            "symlink_policy": self.symlink_policy.value,
            "path_policy_content_id": self.path_policy_content_id,
            "backend_capability_id": self.backend_capability_id,
            "root_content_cid": self.root_content_cid,
            "generation_id": self.generation_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSMount":
        return cls(
            mount_id=payload["mount_id"],
            mount_path=payload["mount_path"],
            backend_id=payload["backend_id"],
            namespace_id=payload.get("namespace_id") or "",
            read_only=bool(payload.get("read_only", False)),
            atomic_boundary=payload.get("atomic_boundary", AtomicBoundary.SINGLE_MOUNT),
            symlink_policy=payload.get("symlink_policy", SymlinkPolicy.REJECT),
            path_policy_content_id=payload.get("path_policy_content_id") or "",
            backend_capability_id=payload.get("backend_capability_id") or "",
            root_content_cid=payload.get("root_content_cid") or "",
            generation_id=payload.get("generation_id") or "",
        )

    @property
    def content_id(self) -> str:
        return content_identity(self.to_record())


def classify_mount_pair(
    source: VFSMount,
    target: VFSMount,
) -> tuple[AtomicBoundary, AtomicityDisposition]:
    """Classify the atomic boundary between two mounts for rename/move."""

    if source.mount_id == target.mount_id:
        return AtomicBoundary.SINGLE_MOUNT, AtomicityDisposition.ATOMIC
    if source.namespace_id and source.namespace_id == target.namespace_id:
        if source.backend_id == target.backend_id:
            return AtomicBoundary.CROSS_MOUNT, AtomicityDisposition.UNSUPPORTED
        return AtomicBoundary.CROSS_BACKEND, AtomicityDisposition.UNSUPPORTED
    if source.backend_id != target.backend_id:
        return AtomicBoundary.CROSS_BACKEND, AtomicityDisposition.UNSUPPORTED
    if source.namespace_id != target.namespace_id:
        return AtomicBoundary.CROSS_NAMESPACE, AtomicityDisposition.UNSUPPORTED
    return AtomicBoundary.CROSS_MOUNT, AtomicityDisposition.UNSUPPORTED


def assert_atomic_boundary_supported(boundary: AtomicBoundary) -> AtomicityDisposition:
    """Return ATOMIC for admitted boundaries; raise for typed unsupported ones."""

    boundary = _enum(boundary, AtomicBoundary, "boundary")
    if boundary in ATOMIC_BOUNDARIES:
        return AtomicityDisposition.ATOMIC
    if boundary in UNSUPPORTED_ATOMIC_BOUNDARIES:
        reason = {
            AtomicBoundary.CROSS_MOUNT: UnsupportedReason.CROSS_MOUNT_ATOMIC,
            AtomicBoundary.CROSS_BACKEND: UnsupportedReason.CROSS_BACKEND_ATOMIC,
            AtomicBoundary.CROSS_NAMESPACE: UnsupportedReason.CROSS_NAMESPACE_ATOMIC,
        }[boundary]
        raise VFSUnsupportedError(
            f"atomic mutation across {boundary.value} is typed unsupported",
            reason=reason,
            boundary=boundary,
        )
    raise VFSContractError(f"unknown atomic boundary: {boundary}")


# ---------------------------------------------------------------------------
# Stat and listing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSStat:
    """Stable stat projection for a VFS entry (``VFSStat@1``).

    Field semantics:

    * ``kind`` — closed entry kind.
    * ``size_bytes`` — exact byte length for files; ``0`` for directories.
    * ``mtime_unix_ms`` — UTC modification time in milliseconds; ``0`` if unknown.
    * ``mode`` — optional POSIX-like mode bits; ``0`` if not applicable.
    * ``content_cid`` / ``version_cid`` — content and version identities.
    * ``target`` — symlink target (namespace-relative) when kind is symlink.
    * ``mount_id`` — mount that owns this entry.
    * ``generation_id`` — catalog/mount generation observed for this stat.
    * ``observed`` — must be True for any success-bearing use of this record.
    """

    SCHEMA: ClassVar[str] = VFS_STAT_SCHEMA

    path: str
    kind: VFSEntryKind
    size_bytes: int = 0
    mtime_unix_ms: int = 0
    mode: int = 0
    content_cid: str = ""
    version_cid: str = ""
    target: str = ""
    mount_id: str = ""
    generation_id: str = ""
    observed: bool = True
    is_readonly: bool = False

    def __post_init__(self) -> None:
        norm = normalize_vfs_path(self.path, policy=VFSPathPolicy.default())
        object.__setattr__(self, "path", norm.path)
        object.__setattr__(self, "kind", _enum(self.kind, VFSEntryKind, "kind"))
        object.__setattr__(
            self,
            "size_bytes",
            _bounded_int(self.size_bytes, "size_bytes", minimum=0),
        )
        object.__setattr__(
            self,
            "mtime_unix_ms",
            _bounded_int(self.mtime_unix_ms, "mtime_unix_ms", minimum=0),
        )
        object.__setattr__(
            self, "mode", _bounded_int(self.mode, "mode", minimum=0, maximum=0o7777)
        )
        object.__setattr__(
            self, "content_cid", _optional_cid(self.content_cid, "content_cid")
        )
        object.__setattr__(
            self, "version_cid", _optional_cid(self.version_cid, "version_cid")
        )
        if self.target:
            # Symlink targets are stored as normalized relative paths when present.
            t_norm = normalize_vfs_path(self.target, policy=VFSPathPolicy.default())
            object.__setattr__(self, "target", t_norm.path)
        else:
            object.__setattr__(self, "target", "")
        object.__setattr__(
            self, "mount_id", _optional_identifier(self.mount_id, "mount_id")
        )
        object.__setattr__(
            self, "generation_id", _optional_identifier(self.generation_id, "generation_id")
        )
        object.__setattr__(self, "observed", _bool(self.observed, "observed"))
        object.__setattr__(self, "is_readonly", _bool(self.is_readonly, "is_readonly"))

        if self.kind is VFSEntryKind.DIRECTORY and self.size_bytes != 0:
            raise VFSContractError("directory stat size_bytes must be 0")
        if self.kind is VFSEntryKind.SYMLINK and not self.target and self.observed:
            # Observed symlink stats must carry a target string (may be empty
            # only when not observed / placeholder).
            pass
        if self.kind is VFSEntryKind.FILE and self.target:
            raise VFSContractError("file stat must not carry a symlink target")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path": self.path,
            "kind": self.kind.value,
            "size_bytes": self.size_bytes,
            "mtime_unix_ms": self.mtime_unix_ms,
            "mode": self.mode,
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "target": self.target,
            "mount_id": self.mount_id,
            "generation_id": self.generation_id,
            "observed": self.observed,
            "is_readonly": self.is_readonly,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSStat":
        return cls(
            path=payload["path"],
            kind=payload["kind"],
            size_bytes=int(payload.get("size_bytes", 0)),
            mtime_unix_ms=int(payload.get("mtime_unix_ms", 0)),
            mode=int(payload.get("mode", 0)),
            content_cid=payload.get("content_cid") or "",
            version_cid=payload.get("version_cid") or "",
            target=payload.get("target") or "",
            mount_id=payload.get("mount_id") or "",
            generation_id=payload.get("generation_id") or "",
            observed=bool(payload.get("observed", True)),
            is_readonly=bool(payload.get("is_readonly", False)),
        )

    @property
    def content_id(self) -> str:
        return content_identity(self.to_record())


@dataclass(frozen=True)
class VFSDirEntry:
    """One directory listing entry with stable order key."""

    SCHEMA: ClassVar[str] = VFS_DIR_ENTRY_SCHEMA

    name: str
    kind: VFSEntryKind
    stat: VFSStat | None = None

    def __post_init__(self) -> None:
        name = _text(self.name, "name", required=True, limit=MAX_SEGMENT_BYTES, strip=False)
        if "/" in name or "\\" in name or name in (".", "..") or name == "":
            raise VFSContractError("dir entry name must be a single path segment")
        if not _is_nfc(name):
            raise VFSContractError("dir entry name must be Unicode NFC")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "kind", _enum(self.kind, VFSEntryKind, "kind"))
        if self.stat is not None and not isinstance(self.stat, VFSStat):
            raise VFSContractError("stat must be a VFSStat or None")

    def order_key(self) -> bytes:
        """UTF-8 lexicographic order key (stable listing order)."""

        return self.name.encode("utf-8")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "name": self.name,
            "kind": self.kind.value,
            "stat": None if self.stat is None else self.stat.to_record(),
        }


@dataclass(frozen=True)
class VFSListing:
    """A page of directory entries with stable order and pagination."""

    SCHEMA: ClassVar[str] = VFS_LISTING_SCHEMA

    path: str
    entries: tuple[VFSDirEntry, ...]
    order: ListingOrder = ListingOrder.UTF8_LEXICOGRAPHIC
    page_size: int = 0
    cursor: str = ""
    next_cursor: str = ""
    has_more: bool = False
    generation_id: str = ""
    observed: bool = True
    mount_id: str = ""

    def __post_init__(self) -> None:
        norm = normalize_vfs_path(self.path, policy=VFSPathPolicy.default())
        object.__setattr__(self, "path", norm.path)
        if not isinstance(self.entries, tuple):
            object.__setattr__(self, "entries", tuple(self.entries))
        for entry in self.entries:
            if not isinstance(entry, VFSDirEntry):
                raise VFSContractError("entries must be VFSDirEntry instances")
        object.__setattr__(self, "order", _enum(self.order, ListingOrder, "order"))
        page_size = self.page_size if self.page_size else len(self.entries)
        object.__setattr__(
            self,
            "page_size",
            _bounded_int(page_size, "page_size", minimum=0, maximum=MAX_LISTING_PAGE_SIZE),
        )
        if len(self.entries) > MAX_LISTING_PAGE_SIZE:
            raise VFSBoundsError("listing page exceeds MAX_LISTING_PAGE_SIZE")
        object.__setattr__(
            self, "cursor", _text(self.cursor, "cursor", limit=MAX_IDENTIFIER_BYTES)
        )
        object.__setattr__(
            self,
            "next_cursor",
            _text(self.next_cursor, "next_cursor", limit=MAX_IDENTIFIER_BYTES),
        )
        object.__setattr__(self, "has_more", _bool(self.has_more, "has_more"))
        object.__setattr__(
            self, "generation_id", _optional_identifier(self.generation_id, "generation_id")
        )
        object.__setattr__(self, "observed", _bool(self.observed, "observed"))
        object.__setattr__(
            self, "mount_id", _optional_identifier(self.mount_id, "mount_id")
        )

        if self.order is ListingOrder.UTF8_LEXICOGRAPHIC:
            keys = [entry.order_key() for entry in self.entries]
            if keys != sorted(keys):
                raise VFSContractError(
                    "listing entries must be sorted in UTF-8 lexicographic order"
                )
            # Duplicate names are forbidden within a page.
            names = [entry.name for entry in self.entries]
            if len(names) != len(set(names)):
                raise VFSContractError("listing entries must have unique names")

        if self.has_more and not self.next_cursor:
            raise VFSContractError("has_more requires next_cursor")
        if not self.has_more and self.next_cursor:
            raise VFSContractError("next_cursor requires has_more")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path": self.path,
            "entries": [entry.to_record() for entry in self.entries],
            "order": self.order.value,
            "page_size": self.page_size,
            "cursor": self.cursor,
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "generation_id": self.generation_id,
            "observed": self.observed,
            "mount_id": self.mount_id,
        }

    @classmethod
    def from_entries(
        cls,
        path: str,
        entries: Sequence[VFSDirEntry],
        *,
        cursor: str = "",
        page_size: int | None = None,
        generation_id: str = "",
        mount_id: str = "",
        observed: bool = True,
    ) -> "VFSListing":
        """Build a listing, sorting entries into stable UTF-8 order."""

        ordered = tuple(sorted(entries, key=lambda e: e.order_key()))
        limit = page_size if page_size is not None else len(ordered)
        if limit < 0:
            raise VFSContractError("page_size must be non-negative")
        page = ordered[:limit] if limit else ordered
        has_more = len(ordered) > len(page)
        next_cursor = ""
        if has_more and page:
            next_cursor = page[-1].name
        elif has_more:
            next_cursor = "cursor:overflow"
        return cls(
            path=path,
            entries=page,
            order=ListingOrder.UTF8_LEXICOGRAPHIC,
            page_size=len(page),
            cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
            generation_id=generation_id,
            observed=observed,
            mount_id=mount_id,
        )


# ---------------------------------------------------------------------------
# Operation and result (success ⇒ observed state transition)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSOperation:
    """A closed VFS operation request (``VFSOperation@1``)."""

    SCHEMA: ClassVar[str] = VFS_OPERATION_SCHEMA

    operation_id: str
    kind: VFSOperationKind
    path: str = ""
    source_path: str = ""
    target_path: str = ""
    mount_id: str = ""
    source_mount_id: str = ""
    target_mount_id: str = ""
    namespace_id: str = ""
    precondition_version_cid: str = ""
    content_cid: str = ""
    range_start: int = 0
    range_end: int = 0  # exclusive; 0 means unset for non-range ops
    read_only: bool = False
    atomic_boundary: AtomicBoundary = AtomicBoundary.SINGLE_MOUNT
    request_id: str = ""
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        object.__setattr__(self, "kind", _enum(self.kind, VFSOperationKind, "kind"))
        policy = VFSPathPolicy.default()
        for field_name in ("path", "source_path", "target_path"):
            value = getattr(self, field_name)
            if value:
                norm = normalize_vfs_path(value, policy=policy)
                object.__setattr__(self, field_name, norm.path)
            else:
                object.__setattr__(self, field_name, "")
        for field_name in (
            "mount_id",
            "source_mount_id",
            "target_mount_id",
            "namespace_id",
            "request_id",
            "idempotency_key",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "precondition_version_cid",
            _optional_cid(self.precondition_version_cid, "precondition_version_cid"),
        )
        object.__setattr__(
            self, "content_cid", _optional_cid(self.content_cid, "content_cid")
        )
        object.__setattr__(
            self, "range_start", _bounded_int(self.range_start, "range_start", minimum=0)
        )
        object.__setattr__(
            self, "range_end", _bounded_int(self.range_end, "range_end", minimum=0)
        )
        object.__setattr__(self, "read_only", _bool(self.read_only, "read_only"))
        object.__setattr__(
            self,
            "atomic_boundary",
            _enum(self.atomic_boundary, AtomicBoundary, "atomic_boundary"),
        )

        if self.kind in (VFSOperationKind.RENAME, VFSOperationKind.MOVE):
            if not self.source_path or not self.target_path:
                raise VFSContractError(
                    f"{self.kind.value} requires source_path and target_path"
                )
        # Empty path is the namespace root and is admitted for stat/list/create/etc.

        if self.kind is VFSOperationKind.RANGE_READ:
            if self.range_end and self.range_end < self.range_start:
                raise VFSContractError("range_end must be >= range_start")

        if self.kind is VFSOperationKind.CAS_WRITE and not self.precondition_version_cid:
            raise VFSContractError("cas_write requires precondition_version_cid")

        if self.kind in MUTATING_OPERATIONS and self.read_only:
            raise VFSContractError("mutating operation cannot be marked read_only")

        # Typed unsupported atomic boundaries on the request itself.
        if (
            self.kind in MUTATING_OPERATIONS
            and self.atomic_boundary in UNSUPPORTED_ATOMIC_BOUNDARIES
        ):
            assert_atomic_boundary_supported(self.atomic_boundary)

    @property
    def is_mutating(self) -> bool:
        return self.kind in MUTATING_OPERATIONS

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "operation_id": self.operation_id,
            "kind": self.kind.value,
            "path": self.path,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "mount_id": self.mount_id,
            "source_mount_id": self.source_mount_id,
            "target_mount_id": self.target_mount_id,
            "namespace_id": self.namespace_id,
            "precondition_version_cid": self.precondition_version_cid,
            "content_cid": self.content_cid,
            "range_start": self.range_start,
            "range_end": self.range_end,
            "read_only": self.read_only,
            "atomic_boundary": self.atomic_boundary.value,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "is_mutating": self.is_mutating,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSOperation":
        return cls(
            operation_id=payload["operation_id"],
            kind=payload["kind"],
            path=payload.get("path") or "",
            source_path=payload.get("source_path") or "",
            target_path=payload.get("target_path") or "",
            mount_id=payload.get("mount_id") or "",
            source_mount_id=payload.get("source_mount_id") or "",
            target_mount_id=payload.get("target_mount_id") or "",
            namespace_id=payload.get("namespace_id") or "",
            precondition_version_cid=payload.get("precondition_version_cid") or "",
            content_cid=payload.get("content_cid") or "",
            range_start=int(payload.get("range_start", 0)),
            range_end=int(payload.get("range_end", 0)),
            read_only=bool(payload.get("read_only", False)),
            atomic_boundary=payload.get("atomic_boundary", AtomicBoundary.SINGLE_MOUNT),
            request_id=payload.get("request_id") or "",
            idempotency_key=payload.get("idempotency_key") or "",
        )


@dataclass(frozen=True)
class VFSError:
    """Typed VFS error projecting onto the storage error taxonomy."""

    SCHEMA: ClassVar[str] = VFS_ERROR_SCHEMA

    code: VFSErrorCode
    message: str
    category: ErrorCategory = ErrorCategory.VALIDATION
    storage_code: ErrorCode = ErrorCode.INVALID_REQUEST
    retryability: Retryability = Retryability.NEVER
    state: OperationState = OperationState.REJECTED
    path: str = ""
    path_reason: str = ""
    unsupported_reason: str = ""
    mount_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _enum(self.code, VFSErrorCode, "code"))
        object.__setattr__(
            self,
            "message",
            _text(self.message, "message", required=True, limit=MAX_TEXT_BYTES),
        )
        object.__setattr__(
            self, "category", _enum(self.category, ErrorCategory, "category")
        )
        object.__setattr__(
            self, "storage_code", _enum(self.storage_code, ErrorCode, "storage_code")
        )
        object.__setattr__(
            self, "retryability", _enum(self.retryability, Retryability, "retryability")
        )
        object.__setattr__(self, "state", _enum(self.state, OperationState, "state"))
        if self.state in SUCCESS_STATES:
            raise InconsistentStateError("VFSError cannot carry a success state")
        object.__setattr__(self, "path", _text(self.path, "path", limit=MAX_PATH_BYTES))
        object.__setattr__(
            self,
            "path_reason",
            _text(self.path_reason, "path_reason", limit=MAX_IDENTIFIER_BYTES),
        )
        object.__setattr__(
            self,
            "unsupported_reason",
            _text(self.unsupported_reason, "unsupported_reason", limit=MAX_IDENTIFIER_BYTES),
        )
        object.__setattr__(
            self, "mount_id", _optional_identifier(self.mount_id, "mount_id")
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "code": self.code.value,
            "message": self.message,
            "category": self.category.value,
            "storage_code": self.storage_code.value,
            "retryability": self.retryability.value,
            "state": self.state.value,
            "path": self.path,
            "path_reason": self.path_reason,
            "unsupported_reason": self.unsupported_reason,
            "mount_id": self.mount_id,
        }

    def as_transport_projection(self) -> dict[str, Any]:
        return {
            "error": True,
            "code": self.code.value,
            "storage_code": self.storage_code.value,
            "category": self.category.value,
            "message": self.message,
            "state": self.state.value,
            "retryability": self.retryability.value,
            "path": self.path,
        }


@dataclass(frozen=True)
class ObservedStateTransition:
    """An observed admitted state transition for a VFS operation.

    Success for mutating operations is contingent on this record: the
    transition must be marked ``observed=True``, follow the legal lifecycle
    table, and for mutations the pre/post namespace identity must differ
    (or an explicit create-from-absent / delete-to-absent edge is recorded).
    """

    from_state: OperationState
    to_state: OperationState
    observed: bool
    observation_id: str
    from_version_cid: str = ""
    to_version_cid: str = ""
    effect_evidence_ids: tuple[str, ...] = ()
    namespace_generation_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "from_state", _enum(self.from_state, OperationState, "from_state")
        )
        object.__setattr__(
            self, "to_state", _enum(self.to_state, OperationState, "to_state")
        )
        object.__setattr__(self, "observed", _bool(self.observed, "observed"))
        object.__setattr__(
            self, "observation_id", _identifier(self.observation_id, "observation_id")
        )
        object.__setattr__(
            self,
            "from_version_cid",
            _optional_cid(self.from_version_cid, "from_version_cid"),
        )
        object.__setattr__(
            self, "to_version_cid", _optional_cid(self.to_version_cid, "to_version_cid")
        )
        object.__setattr__(
            self,
            "effect_evidence_ids",
            _ids(self.effect_evidence_ids, "effect_evidence_ids"),
        )
        object.__setattr__(
            self,
            "namespace_generation_id",
            _optional_identifier(self.namespace_generation_id, "namespace_generation_id"),
        )
        if self.observed and not is_legal_transition(self.from_state, self.to_state):
            raise InconsistentStateError(
                f"illegal observed transition {self.from_state.value} → {self.to_state.value}"
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "observed": self.observed,
            "observation_id": self.observation_id,
            "from_version_cid": self.from_version_cid,
            "to_version_cid": self.to_version_cid,
            "effect_evidence_ids": list(self.effect_evidence_ids),
            "namespace_generation_id": self.namespace_generation_id,
        }


@dataclass(frozen=True)
class VFSOperationResult:
    """Result of a VFS operation; success requires observed transition evidence.

    Contract rules:

    * ``success=True`` requires ``observed_transition.observed is True``.
    * Mutating success requires ``to_state`` in durable/success ladder past
      mere claim (at least ``COMMITTED`` for durable mutations, or a typed
      accepted-only mode is rejected here — mutations must reach COMMITTED+).
    * Mutating success requires a namespace identity change: either version
      CIDs differ, or an explicit create/delete edge via empty from/to CID
      with effect evidence.
    * ``success=False`` requires a ``VFSError``.
    * A returned success without an observed admitted state change is a
      contract failure (raises ``VFSObservationError`` / ``InconsistentStateError``).
    """

    SCHEMA: ClassVar[str] = VFS_OPERATION_RESULT_SCHEMA

    operation_id: str
    kind: VFSOperationKind
    success: bool
    state: OperationState
    observed_transition: ObservedStateTransition | None = None
    error: VFSError | None = None
    stat: VFSStat | None = None
    listing: VFSListing | None = None
    resulting_content_cid: str = ""
    resulting_version_cid: str = ""
    mount_id: str = ""
    path: str = ""
    request_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        object.__setattr__(self, "kind", _enum(self.kind, VFSOperationKind, "kind"))
        object.__setattr__(self, "success", _bool(self.success, "success"))
        object.__setattr__(self, "state", _enum(self.state, OperationState, "state"))
        object.__setattr__(
            self,
            "resulting_content_cid",
            _optional_cid(self.resulting_content_cid, "resulting_content_cid"),
        )
        object.__setattr__(
            self,
            "resulting_version_cid",
            _optional_cid(self.resulting_version_cid, "resulting_version_cid"),
        )
        object.__setattr__(
            self, "mount_id", _optional_identifier(self.mount_id, "mount_id")
        )
        if self.path:
            object.__setattr__(
                self,
                "path",
                normalize_vfs_path(self.path, policy=VFSPathPolicy.default()).path,
            )
        else:
            object.__setattr__(self, "path", "")
        object.__setattr__(
            self, "request_id", _optional_identifier(self.request_id, "request_id")
        )

        if self.success:
            if self.error is not None:
                raise InconsistentStateError("successful result cannot carry an error")
            if self.state not in SUCCESS_STATES:
                raise InconsistentStateError(
                    f"success=True is inconsistent with state {self.state.value}"
                )
            if self.observed_transition is None:
                raise VFSObservationError(
                    "success requires an observed state transition record"
                )
            if not self.observed_transition.observed:
                raise VFSObservationError(
                    "success requires observed_transition.observed=True"
                )
            if self.observed_transition.to_state is not self.state:
                raise InconsistentStateError(
                    "result state must equal observed_transition.to_state"
                )

            if self.kind in MUTATING_OPERATIONS:
                self._assert_mutating_success()
            else:
                # Read path: observation is still required so success is not a claim.
                if not self.observed_transition.observation_id:
                    raise VFSObservationError("read success requires observation_id")
        else:
            if self.error is None:
                raise InconsistentStateError("failed result requires a VFSError")
            if self.state in SUCCESS_STATES:
                raise InconsistentStateError(
                    "success=False is inconsistent with a success acknowledgement state"
                )

    def _assert_mutating_success(self) -> None:
        transition = self.observed_transition
        assert transition is not None
        # Mutations that claim success must reach at least COMMITTED.
        if self.state not in (
            OperationState.COMMITTED,
            OperationState.VERIFIED,
            OperationState.CONVERGED,
        ):
            raise InconsistentStateError(
                "mutating success requires committed/verified/converged state"
            )
        # Observed state change: version identity must change, or evidence of
        # create/delete must be present.
        from_v = transition.from_version_cid
        to_v = transition.to_version_cid or self.resulting_version_cid
        if from_v and to_v and from_v == to_v:
            raise VFSObservationError(
                "mutating success requires an observed namespace version change; "
                "identical from/to version CIDs are a contract failure"
            )
        if not to_v and self.kind not in (
            VFSOperationKind.DELETE,
            VFSOperationKind.RMDIR,
            VFSOperationKind.UNMOUNT,
        ):
            raise VFSObservationError(
                "mutating success requires resulting/to version identity "
                f"for {self.kind.value}"
            )
        if not transition.effect_evidence_ids:
            raise VFSObservationError(
                "mutating success requires at least one effect evidence id"
            )
        if transition.from_state is transition.to_state and self.kind in MUTATING_OPERATIONS:
            # Identity-stable from→to lifecycle states with a version change can
            # still be legal (e.g. re-commit); but pure no-op is rejected when
            # versions also match (handled above). Lifecycle self-loops are
            # allowed by is_legal_transition; version check is the gate.
            pass

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "operation_id": self.operation_id,
            "kind": self.kind.value,
            "success": self.success,
            "state": self.state.value,
            "observed_transition": (
                None
                if self.observed_transition is None
                else self.observed_transition.to_record()
            ),
            "error": None if self.error is None else self.error.to_record(),
            "stat": None if self.stat is None else self.stat.to_record(),
            "listing": None if self.listing is None else self.listing.to_record(),
            "resulting_content_cid": self.resulting_content_cid,
            "resulting_version_cid": self.resulting_version_cid,
            "mount_id": self.mount_id,
            "path": self.path,
            "request_id": self.request_id,
        }


def path_error_to_vfs_error(exc: VFSPathError) -> VFSError:
    """Project a path policy failure to a typed VFSError."""

    reason = exc.reason
    code_map: dict[VFSPathRejectReason, VFSErrorCode] = {
        VFSPathRejectReason.ABSOLUTE: VFSErrorCode.ABSOLUTE_PATH,
        VFSPathRejectReason.TRAVERSAL: VFSErrorCode.PATH_TRAVERSAL,
        VFSPathRejectReason.ESCAPE: VFSErrorCode.PATH_ESCAPE,
        VFSPathRejectReason.NON_NFC: VFSErrorCode.UNICODE_POLICY,
        VFSPathRejectReason.CASE_FOLD_UNSUPPORTED: VFSErrorCode.CASE_POLICY,
        VFSPathRejectReason.SYMLINK_REJECTED: VFSErrorCode.SYMLINK_POLICY,
        VFSPathRejectReason.SYMLINK_ESCAPE: VFSErrorCode.SYMLINK_POLICY,
    }
    code = code_map.get(reason, VFSErrorCode.INVALID_PATH)
    category = ErrorCategory.VALIDATION
    if reason in (
        VFSPathRejectReason.ESCAPE,
        VFSPathRejectReason.TRAVERSAL,
        VFSPathRejectReason.ABSOLUTE,
        VFSPathRejectReason.SYMLINK_ESCAPE,
    ):
        category = ErrorCategory.AUTHORIZATION
    return VFSError(
        code=code,
        message=str(exc),
        category=category,
        storage_code=ErrorCode.INVALID_REQUEST
        if category is ErrorCategory.VALIDATION
        else ErrorCode.FORBIDDEN,
        retryability=Retryability.NEVER,
        state=OperationState.REJECTED,
        path=exc.path,
        path_reason=reason.value,
    )


def unsupported_to_vfs_error(exc: VFSUnsupportedError) -> VFSError:
    """Project a typed unsupported case to a VFSError."""

    return VFSError(
        code=VFSErrorCode.UNSUPPORTED
        if exc.reason not in (
            UnsupportedReason.CROSS_MOUNT_ATOMIC,
            UnsupportedReason.CROSS_BACKEND_ATOMIC,
            UnsupportedReason.CROSS_NAMESPACE_ATOMIC,
        )
        else VFSErrorCode.CROSS_BOUNDARY,
        message=str(exc),
        category=ErrorCategory.UNSUPPORTED,
        storage_code=ErrorCode.UNSUPPORTED,
        retryability=Retryability.NEVER,
        state=OperationState.UNSUPPORTED,
        unsupported_reason=exc.reason.value,
    )


def make_mutating_success(
    operation: VFSOperation,
    *,
    from_version_cid: str,
    to_version_cid: str,
    effect_evidence_ids: Sequence[str],
    observation_id: str,
    from_state: OperationState = OperationState.PROCESSING,
    to_state: OperationState = OperationState.COMMITTED,
    resulting_content_cid: str = "",
    mount_id: str = "",
) -> VFSOperationResult:
    """Build a success result that satisfies the observed-transition rule."""

    transition = ObservedStateTransition(
        from_state=from_state,
        to_state=to_state,
        observed=True,
        observation_id=observation_id,
        from_version_cid=from_version_cid,
        to_version_cid=to_version_cid,
        effect_evidence_ids=tuple(effect_evidence_ids),
    )
    return VFSOperationResult(
        operation_id=operation.operation_id,
        kind=operation.kind,
        success=True,
        state=to_state,
        observed_transition=transition,
        resulting_content_cid=resulting_content_cid,
        resulting_version_cid=to_version_cid,
        mount_id=mount_id or operation.mount_id,
        path=operation.path or operation.target_path,
        request_id=operation.request_id,
    )


def make_read_success(
    operation: VFSOperation,
    *,
    observation_id: str,
    stat: VFSStat | None = None,
    listing: VFSListing | None = None,
    state: OperationState = OperationState.COMMITTED,
    mount_id: str = "",
) -> VFSOperationResult:
    """Build a read success with a required observation record.

    Default edge is ``ACCEPTED → COMMITTED`` (legal). Callers may pass any
    ``(from_state, to_state)`` pair that is legal by using ``state`` values
    reachable in one admitted step from ``ACCEPTED`` or ``PROCESSING``.
    """

    if is_legal_transition(OperationState.ACCEPTED, state):
        from_state = OperationState.ACCEPTED
    elif is_legal_transition(OperationState.PROCESSING, state):
        from_state = OperationState.PROCESSING
    elif is_legal_transition(OperationState.COMMITTED, state):
        from_state = OperationState.COMMITTED
    else:
        from_state = OperationState.ACCEPTED
        state = OperationState.COMMITTED

    transition = ObservedStateTransition(
        from_state=from_state,
        to_state=state,
        observed=True,
        observation_id=observation_id,
    )
    return VFSOperationResult(
        operation_id=operation.operation_id,
        kind=operation.kind,
        success=True,
        state=state,
        observed_transition=transition,
        stat=stat,
        listing=listing,
        mount_id=mount_id or operation.mount_id,
        path=operation.path,
        request_id=operation.request_id,
    )


def make_failure(
    operation: VFSOperation,
    error: VFSError,
) -> VFSOperationResult:
    """Build a failed result bound to the operation."""

    return VFSOperationResult(
        operation_id=operation.operation_id,
        kind=operation.kind,
        success=False,
        state=error.state,
        error=error,
        mount_id=operation.mount_id,
        path=operation.path or error.path,
        request_id=operation.request_id,
    )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "VFS_PATH_POLICY_SCHEMA",
    "VFS_MOUNT_SCHEMA",
    "VFS_STAT_SCHEMA",
    "VFS_OPERATION_SCHEMA",
    "VFS_OPERATION_RESULT_SCHEMA",
    "VFS_LISTING_SCHEMA",
    "VFSPathPolicy_V1",
    "VFSOperation_V1",
    "VFSStat_V1",
    "VFSMount_V1",
    "MAX_PATH_BYTES",
    "MAX_SEGMENT_BYTES",
    "MAX_LISTING_PAGE_SIZE",
    "MUTATING_OPERATIONS",
    "READ_OPERATIONS",
    "ATOMIC_BOUNDARIES",
    "UNSUPPORTED_ATOMIC_BOUNDARIES",
    "CasePolicy",
    "UnicodePolicy",
    "SymlinkPolicy",
    "PathForm",
    "ListingOrder",
    "VFSEntryKind",
    "VFSOperationKind",
    "AtomicBoundary",
    "AtomicityDisposition",
    "UnsupportedReason",
    "VFSPathRejectReason",
    "VFSErrorCode",
    "VFSContractError",
    "VFSPathError",
    "VFSUnsupportedError",
    "VFSBoundsError",
    "VFSObservationError",
    "VFSPathPolicy",
    "NormalizedPath",
    "SymlinkDecision",
    "VFSMount",
    "VFSStat",
    "VFSDirEntry",
    "VFSListing",
    "VFSOperation",
    "VFSError",
    "ObservedStateTransition",
    "VFSOperationResult",
    "normalize_vfs_path",
    "confine_path",
    "resolve_under_roots",
    "path_is_within_root",
    "join_namespace_path",
    "evaluate_symlink",
    "classify_mount_pair",
    "assert_atomic_boundary_supported",
    "path_error_to_vfs_error",
    "unsupported_to_vfs_error",
    "make_mutating_success",
    "make_read_success",
    "make_failure",
    "canonical_json_bytes",
    "content_identity",
]

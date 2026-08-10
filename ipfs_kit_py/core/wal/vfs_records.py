"""Canonical VFS WAL records as the recoverable transaction source of truth (KVFS-303).

This module owns the VFS-facing durable record schema and a compatibility reader.
Canonical durable data is self-contained: recovery never depends on a sidecar for
acknowledged mutations.  Legacy marker + sidecar layouts are classified so the
marker-to-sidecar crash gap is explicit and fail-closed.

Each durable record carries:

* transaction / operation / effect identities;
* intent (closed mutation vocabulary);
* either a bounded inline payload **or** a staged content reference;
* content checksum;
* preconditions;
* decision; and
* acknowledgement evidence.

Corrupt segment tails preserve every verified prefix frame.  Secrets and
unbounded bodies are rejected at construction.  This module does not bind live
mutations (see KVFS-309); it is an inert schema + recovery reader.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final, TypeVar

from ipfs_kit_py.core.operation_contracts import (
    BodyRejectedError,
    CanonicalContract,
    ForgedIdentityError,
    InconsistentStateError,
    PayloadKind,
    PayloadReference,
    SecretMaterialError,
    canonical_json_bytes,
    content_identity,
)

from .contracts import (
    CONTRACT_VERSION as WAL_CONTRACT_VERSION,
    MAX_RECORD_BYTES as WAL_MAX_RECORD_BYTES,
    WALAcknowledgementMode,
    WALContractBoundsError,
    WALContractError,
    WALCorruptionDisposition,
    WALRecord,
    WALRecordKind,
    WALRecordState,
    checksum_for_preimage,
)
from .segments import SegmentRecovery, recover_segment


# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

VFS_WAL_NAMESPACE: Final[str] = "ipfs_kit_py/core/wal/vfs_records"

VFS_WAL_DURABLE_DATA_SCHEMA: Final[str] = (
    f"{VFS_WAL_NAMESPACE}/durable-data@{SCHEMA_MAJOR}"
)
VFS_WAL_CONTENT_SCHEMA: Final[str] = (
    f"{VFS_WAL_NAMESPACE}/content@{SCHEMA_MAJOR}"
)
VFS_WAL_PRECONDITION_SCHEMA: Final[str] = (
    f"{VFS_WAL_NAMESPACE}/precondition@{SCHEMA_MAJOR}"
)
VFS_WAL_ACK_SCHEMA: Final[str] = (
    f"{VFS_WAL_NAMESPACE}/acknowledgement@{SCHEMA_MAJOR}"
)
VFS_WAL_RECOVERY_SCHEMA: Final[str] = (
    f"{VFS_WAL_NAMESPACE}/recovery-prefix@{SCHEMA_MAJOR}"
)

# Public interface aliases.
VFSWALDurableData_V1: Final[str] = VFS_WAL_DURABLE_DATA_SCHEMA
VFSWALContent_V1: Final[str] = VFS_WAL_CONTENT_SCHEMA
VFSWALPrecondition_V1: Final[str] = VFS_WAL_PRECONDITION_SCHEMA
VFSWALAcknowledgement_V1: Final[str] = VFS_WAL_ACK_SCHEMA

MAX_RECORD_BYTES: Final[int] = min(262_144, WAL_MAX_RECORD_BYTES)
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_INLINE_PAYLOAD_BYTES: Final[int] = 4_096
MAX_PRECONDITION_COUNT: Final[int] = 64
MAX_REFERENCE_COUNT: Final[int] = 256
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_STAGED_SIZE_BOUND: Final[int] = 1 << 40  # declared bound only, never a body

# Envelope marker embedded in framed WALRecord payload so recovery can identify
# self-contained canonical VFS records without consulting a sidecar.
CANONICAL_ENVELOPE_KIND: Final[str] = "vfs_wal_durable_data@1"

_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)
_CID_LIKE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44}|baguqeer[a-z0-9]{50,}|"
    r"sha256:[0-9a-f]{64})$"
)
_HEX_CHECKSUM_RE: Final[re.Pattern[str]] = re.compile(
    r"^(sha256:)?[0-9a-fA-F]{32,128}$"
)

TEnum = TypeVar("TEnum", bound=Enum)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class VFSWALIntentKind(str, Enum):
    """Closed intent vocabulary for durable VFS mutations."""

    CREATE = "create"
    WRITE = "write"
    TRUNCATE = "truncate"
    UNLINK = "unlink"
    RENAME = "rename"
    MKDIR = "mkdir"
    RMDIR = "rmdir"
    SETATTR = "setattr"
    FSYNC = "fsync"
    COMPENSATE = "compensate"
    UNKNOWN = "unknown"


class VFSWALDecision(str, Enum):
    """Closed decision outcomes recorded with durable data."""

    INTENT_RECORDED = "intent_recorded"
    EFFECT_APPLIED = "effect_applied"
    COMMIT_PENDING = "commit_pending"
    COMMITTED = "committed"
    ABORTED = "aborted"
    COMPENSATED = "compensated"
    REJECTED = "rejected"
    FAILED = "failed"


class VFSWALContentKind(str, Enum):
    """How mutation bytes are carried — never unbounded bodies."""

    EMPTY = "empty"
    INLINE_BOUNDED = "inline_bounded"
    STAGED_CONTENT_REF = "staged_content_ref"


class MarkerSidecarGapKind(str, Enum):
    """Classification of marker ↔ sidecar crash relationships.

    Canonical self-contained records eliminate the gap.  Legacy layouts that
    split markers into the WAL and intent bodies into a sidecar are classified
    so recovery can refuse incomplete pairs rather than invent durability.
    """

    CANONICAL_SELF_CONTAINED = "canonical_self_contained"
    MARKER_AND_SIDECAR = "marker_and_sidecar"
    MARKER_WITHOUT_SIDECAR = "marker_without_sidecar"
    SIDECAR_WITHOUT_MARKER = "sidecar_without_marker"
    DECISION_ONLY = "decision_only"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VFSWALRecordError(WALContractError):
    """Base class for VFS WAL durable-record failures."""


class VFSWALRecordBoundsError(WALContractBoundsError, VFSWALRecordError):
    """A VFS WAL record exceeded its compactness bounds."""


class VFSWALRecoveryError(VFSWALRecordError):
    """Recovery could not produce a safe recoverable prefix."""


class VFSWALGapError(VFSWALRecordError):
    """A marker/sidecar crash gap prevents safe recovery of a transaction."""


# ---------------------------------------------------------------------------
# Field codecs / secret / body guards
# ---------------------------------------------------------------------------


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


_SECRET_KEY_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "client_secret",
        "cookie",
        "credential",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "secret_key",
        "session_token",
        "ssh_key",
        "auth_token",
        "bearer_token",
        "id_token",
    }
)

_SECRET_VALUE_MARKERS: Final[tuple[str, ...]] = (
    "api_key=",
    "apikey=",
    "password=",
    "secret=",
    "private_key",
    "authorization:",
    "bearer ",
    "-----begin",
    "client_secret=",
)

_BODY_KEY_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "body",
        "source_body",
        "source_text",
        "source_code",
        "contents",
        "content_bytes",
        "file_bytes",
        "file_text",
        "snippet",
        "raw_code",
        "raw_ast",
        "ast_body",
        "payload_bytes",
        "raw_payload",
        "request_body",
        "response_body",
        "proof_script",
        "prompt_body",
        "pickle_bytes",
        "marshalled",
        "executable_bytes",
        "unbounded_payload",
    }
)


def _key_looks_secret(key: str) -> bool:
    if key in _SECRET_KEY_MARKERS:
        return True
    for marker in _SECRET_KEY_MARKERS:
        if key.endswith("_" + marker) or key.startswith(marker + "_"):
            return True
        if "_" in marker and marker in key:
            return True
    return False


def _key_looks_body(key: str) -> bool:
    return key in _BODY_KEY_MARKERS or any(
        key.endswith("_" + marker) for marker in _BODY_KEY_MARKERS
    )


def _assert_no_secret_text(value: str, field_name: str) -> None:
    lowered = value.lower()
    for marker in _SECRET_VALUE_MARKERS:
        if marker in lowered:
            raise SecretMaterialError(
                f"{field_name} contains secret material markers"
            )


def _contains_secret_or_body(value: Any, *, path: str = "record") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _normalize_key(raw_key)
            child = f"{path}.{key}"
            if _key_looks_secret(key):
                raise SecretMaterialError(f"{child} is secret material")
            if _key_looks_body(key):
                raise BodyRejectedError(f"{child} smuggles a body/payload")
            _contains_secret_or_body(item, path=child)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _contains_secret_or_body(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        _assert_no_secret_text(value, path)
    if isinstance(value, (bytes, bytearray)):
        raise BodyRejectedError(f"{path} rejects raw bytes bodies")


def _text(
    value: Any,
    field_name: str,
    *,
    required: bool = False,
    limit: int = MAX_TEXT_BYTES,
    allow_empty: bool = True,
) -> str:
    if value is None:
        normalized = ""
    elif not isinstance(value, str):
        raise VFSWALRecordError(f"{field_name} must be a string")
    else:
        normalized = value.strip()
    if required and not normalized:
        raise VFSWALRecordError(f"{field_name} is required")
    if not allow_empty and not normalized:
        raise VFSWALRecordError(f"{field_name} must not be empty")
    if len(normalized.encode("utf-8")) > limit:
        raise VFSWALRecordBoundsError(f"{field_name} exceeds its byte bound")
    _assert_no_secret_text(normalized, field_name)
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
        raise VFSWALRecordError(f"{field_name} must be an opaque compact identifier")
    if not _ID_RE.match(text):
        raise VFSWALRecordError(f"{field_name} has an invalid identifier shape")
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
        raise VFSWALRecordError(f"{field_name} must be a finite integer")
    if value < minimum or value > maximum:
        raise VFSWALRecordBoundsError(f"{field_name} is outside the supported bound")
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise VFSWALRecordError(f"{field_name} must be a boolean")
    return value


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        if isinstance(value, enum):
            return value
        return enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum)
        raise VFSWALRecordError(f"{field_name} must be one of: {allowed}") from exc


def _optional_cid(value: Any, field_name: str) -> str:
    text = _text(value, field_name, required=False, limit=MAX_IDENTIFIER_BYTES)
    if not text:
        return ""
    if not _CID_LIKE_RE.match(text) and not text.startswith(
        ("cid:", "baguqeer", "bafy", "bafk", "Qm", "sha256:")
    ):
        if not _ID_RE.match(text):
            raise VFSWALRecordError(f"{field_name} is not a valid content identity")
    return text


def _checksum(value: Any, field_name: str = "checksum") -> str:
    text = _text(value, field_name, required=False, limit=128)
    if not text:
        return ""
    if not _HEX_CHECKSUM_RE.match(text) and not text.startswith("sha256:"):
        if not _CID_LIKE_RE.match(text) and not _ID_RE.match(text):
            raise VFSWALRecordError(f"{field_name} is not a valid checksum digest")
    if text.startswith("sha256:") or all(
        c in "0123456789abcdef" for c in text.lower()
    ):
        return text.lower()
    return text


def _reject_unknown_fields(
    payload: Mapping[str, Any],
    allowed: Iterable[str],
    *,
    artifact_name: str,
) -> None:
    extra = set(payload).difference(set(allowed) | {"schema", "content_id", "contract_version"})
    if extra:
        raise VFSWALRecordError(
            f"{artifact_name} contains unsupported fields; rebuild its canonical payload"
        )


def _schema(payload: Mapping[str, Any], expected: str) -> None:
    if not isinstance(payload, Mapping):
        raise VFSWALRecordError("contract payload must be an object")
    supplied = payload.get("schema")
    if supplied not in (None, "", expected):
        raise VFSWALRecordError(f"unsupported contract schema; use {expected}")


def _contract_version(payload: Mapping[str, Any]) -> None:
    supplied = payload.get("contract_version")
    if supplied not in (None, CONTRACT_VERSION):
        raise VFSWALRecordError(
            "unsupported VFS WAL contract version; rebuild with the current contract"
        )


def _bounded_record(record: CanonicalContract, name: str) -> None:
    size = len(record.canonical_bytes())
    if size > MAX_RECORD_BYTES:
        raise VFSWALRecordBoundsError(
            f"{name} exceeds MAX_RECORD_BYTES ({size} > {MAX_RECORD_BYTES})"
        )


def _verify_identity(payload: Mapping[str, Any], record: CanonicalContract) -> None:
    supplied = payload.get("content_id")
    if supplied is None:
        return
    if not isinstance(supplied, str) or not supplied:
        raise ForgedIdentityError("content_id must be a non-empty string when present")
    if supplied != record.content_id:
        raise ForgedIdentityError(
            "stored content_id does not match the canonical preimage"
        )


def _decode_fields(
    payload: Mapping[str, Any],
    schema: str,
    fields: Sequence[str],
    artifact_name: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise VFSWALRecordError(f"{artifact_name} payload must be an object")
    _schema(payload, schema)
    _contract_version(payload)
    _reject_unknown_fields(payload, fields, artifact_name=artifact_name)
    _contains_secret_or_body(payload, path=artifact_name)
    return {name: payload.get(name) for name in fields}


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise VFSWALRecordError(f"{field_name} must be an object")
    # Defensive copy with secret/body scan.
    raw = dict(value)
    _contains_secret_or_body(raw, path=field_name)
    # Bound total encoded size of free-form maps.
    encoded = canonical_json_bytes(raw)
    if len(encoded) > MAX_TEXT_BYTES:
        raise VFSWALRecordBoundsError(f"{field_name} exceeds its byte bound")
    return json.loads(encoded.decode("utf-8"))


# ---------------------------------------------------------------------------
# Content carrier (bounded inline XOR staged reference)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSWALContent(CanonicalContract):
    """Bounded inline payload or staged content reference — never both bodies.

    Exactly one of:

    * ``EMPTY`` — no mutation bytes;
    * ``INLINE_BOUNDED`` — UTF-8 payload ≤ ``MAX_INLINE_PAYLOAD_BYTES``; or
    * ``STAGED_CONTENT_REF`` — content identity of staged durable media.
    """

    SCHEMA: ClassVar[str] = VFS_WAL_CONTENT_SCHEMA

    kind: VFSWALContentKind
    inline_payload: str = ""
    staged_content_cid: str = ""
    size_bytes: int = 0
    media_type: str = ""
    staging_path_ref: str = ""  # opaque path identity, never a host absolute body

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "kind", _enum(self.kind, VFSWALContentKind, "kind")
        )
        object.__setattr__(
            self,
            "inline_payload",
            _text(
                self.inline_payload,
                "inline_payload",
                limit=MAX_INLINE_PAYLOAD_BYTES,
            ),
        )
        object.__setattr__(
            self,
            "staged_content_cid",
            _optional_cid(self.staged_content_cid, "staged_content_cid"),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _bounded_int(
                self.size_bytes, "size_bytes", maximum=MAX_STAGED_SIZE_BOUND
            ),
        )
        object.__setattr__(
            self,
            "media_type",
            _text(self.media_type, "media_type", limit=256),
        )
        object.__setattr__(
            self,
            "staging_path_ref",
            _optional_identifier(self.staging_path_ref, "staging_path_ref"),
        )

        if self.kind is VFSWALContentKind.EMPTY:
            if self.inline_payload or self.staged_content_cid or self.size_bytes:
                raise InconsistentStateError(
                    "empty content must not carry inline payload, staged cid, or size"
                )
        elif self.kind is VFSWALContentKind.INLINE_BOUNDED:
            if self.staged_content_cid:
                raise InconsistentStateError(
                    "inline_bounded content cannot also carry a staged content reference"
                )
            # Zero-length inline is allowed (explicit empty write intent).
            if self.size_bytes and self.size_bytes != len(
                self.inline_payload.encode("utf-8")
            ):
                raise InconsistentStateError(
                    "inline_bounded size_bytes must match inline_payload UTF-8 length"
                )
            if not self.size_bytes:
                object.__setattr__(
                    self,
                    "size_bytes",
                    len(self.inline_payload.encode("utf-8")),
                )
        elif self.kind is VFSWALContentKind.STAGED_CONTENT_REF:
            if not self.staged_content_cid:
                raise VFSWALRecordError(
                    "staged_content_ref requires staged_content_cid"
                )
            if self.inline_payload:
                raise BodyRejectedError(
                    "staged_content_ref cannot carry inline payload bodies"
                )
        _bounded_record(self, "vfs wal content")

    def _payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "inline_payload": self.inline_payload,
            "staged_content_cid": self.staged_content_cid,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "staging_path_ref": self.staging_path_ref,
        }

    def to_payload_reference(self) -> PayloadReference:
        """Project into the shared PayloadReference contract."""

        if self.kind is VFSWALContentKind.EMPTY:
            return PayloadReference(kind=PayloadKind.EMPTY)
        if self.kind is VFSWALContentKind.INLINE_BOUNDED:
            return PayloadReference(
                kind=PayloadKind.INLINE_BOUNDED,
                inline_utf8=self.inline_payload,
                size_bytes=self.size_bytes,
                media_type=self.media_type,
            )
        return PayloadReference(
            kind=PayloadKind.CONTENT_CID,
            content_cid=self.staged_content_cid,
            size_bytes=self.size_bytes,
            media_type=self.media_type,
            stream_id=self.staging_path_ref,
        )

    @classmethod
    def empty(cls) -> "VFSWALContent":
        return cls(kind=VFSWALContentKind.EMPTY)

    @classmethod
    def inline(cls, payload: str, *, media_type: str = "text/plain") -> "VFSWALContent":
        return cls(
            kind=VFSWALContentKind.INLINE_BOUNDED,
            inline_payload=payload,
            media_type=media_type,
        )

    @classmethod
    def staged(
        cls,
        content_cid: str,
        *,
        size_bytes: int = 0,
        media_type: str = "application/octet-stream",
        staging_path_ref: str = "",
    ) -> "VFSWALContent":
        return cls(
            kind=VFSWALContentKind.STAGED_CONTENT_REF,
            staged_content_cid=content_cid,
            size_bytes=size_bytes,
            media_type=media_type,
            staging_path_ref=staging_path_ref,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSWALContent":
        fields = (
            "kind",
            "inline_payload",
            "staged_content_cid",
            "size_bytes",
            "media_type",
            "staging_path_ref",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "vfs wal content")
        value = cls(
            kind=raw["kind"] if raw["kind"] is not None else VFSWALContentKind.EMPTY,
            inline_payload=raw.get("inline_payload") or "",
            staged_content_cid=raw.get("staged_content_cid") or "",
            size_bytes=int(raw.get("size_bytes") or 0),
            media_type=raw.get("media_type") or "",
            staging_path_ref=raw.get("staging_path_ref") or "",
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSWALPrecondition(CanonicalContract):
    """One named precondition that must hold before applying an effect."""

    SCHEMA: ClassVar[str] = VFS_WAL_PRECONDITION_SCHEMA

    name: str
    expected: str = ""
    observed: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "name", _identifier(self.name, "name")
        )
        object.__setattr__(
            self, "expected", _text(self.expected, "expected", limit=MAX_TEXT_BYTES)
        )
        object.__setattr__(
            self, "observed", _text(self.observed, "observed", limit=MAX_TEXT_BYTES)
        )
        object.__setattr__(self, "required", _bool(self.required, "required"))
        _bounded_record(self, "vfs wal precondition")

    def _payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expected": self.expected,
            "observed": self.observed,
            "required": self.required,
        }

    def is_satisfied(self) -> bool:
        if not self.required:
            return True
        if not self.expected:
            return True
        return self.expected == self.observed

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSWALPrecondition":
        fields = ("name", "expected", "observed", "required")
        raw = _decode_fields(payload, cls.SCHEMA, fields, "vfs wal precondition")
        value = cls(
            name=raw["name"] or "",
            expected=raw.get("expected") or "",
            observed=raw.get("observed") or "",
            required=bool(raw["required"]) if raw.get("required") is not None else True,
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# Acknowledgement evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSWALAcknowledgement(CanonicalContract):
    """Durability acknowledgement evidence bound to a durable VFS record."""

    SCHEMA: ClassVar[str] = VFS_WAL_ACK_SCHEMA

    mode: WALAcknowledgementMode
    durable: bool
    fsync_receipt_id: str = ""
    parent_directory_fsync: bool = False
    file_fsync: bool = False
    backend_effect_id: str = ""
    acknowledged_at_unix_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mode", _enum(self.mode, WALAcknowledgementMode, "mode")
        )
        object.__setattr__(self, "durable", _bool(self.durable, "durable"))
        object.__setattr__(
            self,
            "fsync_receipt_id",
            _optional_identifier(self.fsync_receipt_id, "fsync_receipt_id"),
        )
        object.__setattr__(
            self,
            "parent_directory_fsync",
            _bool(self.parent_directory_fsync, "parent_directory_fsync"),
        )
        object.__setattr__(
            self, "file_fsync", _bool(self.file_fsync, "file_fsync")
        )
        object.__setattr__(
            self,
            "backend_effect_id",
            _optional_identifier(self.backend_effect_id, "backend_effect_id"),
        )
        object.__setattr__(
            self,
            "acknowledged_at_unix_ms",
            _bounded_int(
                self.acknowledged_at_unix_ms, "acknowledged_at_unix_ms", minimum=0
            ),
        )
        # Buffered/queued modes can never claim durable acknowledgement.
        if self.mode in (
            WALAcknowledgementMode.BUFFERED,
            WALAcknowledgementMode.QUEUED,
        ):
            if self.durable:
                raise InconsistentStateError(
                    f"acknowledgement mode {self.mode.value} cannot claim durable"
                )
            if self.file_fsync or self.parent_directory_fsync or self.fsync_receipt_id:
                raise InconsistentStateError(
                    f"acknowledgement mode {self.mode.value} cannot carry fsync evidence"
                )
        if self.durable and self.mode in (
            WALAcknowledgementMode.WAL_FSYNC,
            WALAcknowledgementMode.WAL_FSYNC_PARENT,
            WALAcknowledgementMode.GROUP_COMMIT,
            WALAcknowledgementMode.BACKEND_EFFECT,
            WALAcknowledgementMode.BACKEND_DURABLE,
        ):
            if not self.fsync_receipt_id and not self.file_fsync:
                raise InconsistentStateError(
                    "durable acknowledgement under fsync modes requires "
                    "fsync_receipt_id or file_fsync evidence"
                )
        _bounded_record(self, "vfs wal acknowledgement")

    def _payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "durable": self.durable,
            "fsync_receipt_id": self.fsync_receipt_id,
            "parent_directory_fsync": self.parent_directory_fsync,
            "file_fsync": self.file_fsync,
            "backend_effect_id": self.backend_effect_id,
            "acknowledged_at_unix_ms": self.acknowledged_at_unix_ms,
        }

    @classmethod
    def buffered(cls) -> "VFSWALAcknowledgement":
        return cls(mode=WALAcknowledgementMode.BUFFERED, durable=False)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSWALAcknowledgement":
        fields = (
            "mode",
            "durable",
            "fsync_receipt_id",
            "parent_directory_fsync",
            "file_fsync",
            "backend_effect_id",
            "acknowledged_at_unix_ms",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "vfs wal acknowledgement")
        value = cls(
            mode=(
                raw["mode"]
                if raw["mode"] is not None
                else WALAcknowledgementMode.BUFFERED
            ),
            durable=bool(raw["durable"]) if raw.get("durable") is not None else False,
            fsync_receipt_id=raw.get("fsync_receipt_id") or "",
            parent_directory_fsync=bool(raw.get("parent_directory_fsync") or False),
            file_fsync=bool(raw.get("file_fsync") or False),
            backend_effect_id=raw.get("backend_effect_id") or "",
            acknowledged_at_unix_ms=int(raw.get("acknowledged_at_unix_ms") or 0),
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# Canonical durable data (source of truth)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSWALDurableData(CanonicalContract):
    """Canonical recoverable transaction data for one VFS WAL record.

    This is the source of truth for recovery.  All fields required by KVFS-303
    acceptance are present and validated.  Framing into a :class:`WALRecord`
    never drops any of these fields into a sidecar.
    """

    SCHEMA: ClassVar[str] = VFS_WAL_DURABLE_DATA_SCHEMA

    transaction_id: str
    operation_id: str
    effect_id: str
    intent: VFSWALIntentKind
    content: VFSWALContent
    checksum: str
    preconditions: tuple[VFSWALPrecondition, ...]
    decision: VFSWALDecision
    acknowledgement: VFSWALAcknowledgement
    intent_detail: dict[str, Any] = field(default_factory=dict)
    path_ref: str = ""
    target_path_ref: str = ""
    generation_id: str = ""
    principal_id: str = ""
    created_at_unix_ms: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transaction_id",
            _identifier(self.transaction_id, "transaction_id"),
        )
        object.__setattr__(
            self,
            "operation_id",
            _identifier(self.operation_id, "operation_id"),
        )
        object.__setattr__(
            self, "effect_id", _identifier(self.effect_id, "effect_id")
        )
        object.__setattr__(
            self, "intent", _enum(self.intent, VFSWALIntentKind, "intent")
        )

        content = self.content
        if not isinstance(content, VFSWALContent):
            if isinstance(content, Mapping):
                content = VFSWALContent.from_dict(content)
            else:
                raise VFSWALRecordError("content must be VFSWALContent or mapping")
            object.__setattr__(self, "content", content)

        object.__setattr__(self, "checksum", _checksum(self.checksum, "checksum"))
        if not self.checksum:
            raise VFSWALRecordError("checksum is required on durable data")

        preconditions = self.preconditions
        if preconditions is None:
            preconditions = ()
        if isinstance(preconditions, Sequence) and not isinstance(
            preconditions, (str, bytes, bytearray)
        ):
            normalized: list[VFSWALPrecondition] = []
            for item in preconditions:
                if isinstance(item, VFSWALPrecondition):
                    normalized.append(item)
                elif isinstance(item, Mapping):
                    normalized.append(VFSWALPrecondition.from_dict(item))
                else:
                    raise VFSWALRecordError(
                        "preconditions must be VFSWALPrecondition or mapping"
                    )
            if len(normalized) > MAX_PRECONDITION_COUNT:
                raise VFSWALRecordBoundsError(
                    "preconditions exceeds MAX_PRECONDITION_COUNT"
                )
            object.__setattr__(self, "preconditions", tuple(normalized))
        else:
            raise VFSWALRecordError("preconditions must be a sequence")

        object.__setattr__(
            self, "decision", _enum(self.decision, VFSWALDecision, "decision")
        )

        acknowledgement = self.acknowledgement
        if not isinstance(acknowledgement, VFSWALAcknowledgement):
            if isinstance(acknowledgement, Mapping):
                acknowledgement = VFSWALAcknowledgement.from_dict(acknowledgement)
            else:
                raise VFSWALRecordError(
                    "acknowledgement must be VFSWALAcknowledgement or mapping"
                )
            object.__setattr__(self, "acknowledgement", acknowledgement)

        object.__setattr__(
            self, "intent_detail", _mapping(self.intent_detail, "intent_detail")
        )
        object.__setattr__(
            self, "path_ref", _optional_identifier(self.path_ref, "path_ref")
        )
        object.__setattr__(
            self,
            "target_path_ref",
            _optional_identifier(self.target_path_ref, "target_path_ref"),
        )
        object.__setattr__(
            self,
            "generation_id",
            _optional_identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(
            self,
            "principal_id",
            _optional_identifier(self.principal_id, "principal_id"),
        )
        object.__setattr__(
            self,
            "created_at_unix_ms",
            _bounded_int(self.created_at_unix_ms, "created_at_unix_ms", minimum=0),
        )
        object.__setattr__(
            self, "notes", _text(self.notes, "notes", limit=MAX_TEXT_BYTES)
        )

        # Decision / acknowledgement consistency.
        if self.decision is VFSWALDecision.COMMITTED:
            if not self.acknowledgement.durable:
                raise InconsistentStateError(
                    "committed decision requires durable acknowledgement"
                )
        if self.decision in (
            VFSWALDecision.INTENT_RECORDED,
            VFSWALDecision.EFFECT_APPLIED,
            VFSWALDecision.COMMIT_PENDING,
            VFSWALDecision.COMMITTED,
        ):
            # Required preconditions must be satisfied for progressive decisions.
            for precondition in self.preconditions:
                if precondition.required and not precondition.is_satisfied():
                    raise InconsistentStateError(
                        f"required precondition {precondition.name!r} is not satisfied"
                    )

        # Rename requires a target path reference.
        if self.intent is VFSWALIntentKind.RENAME and not self.target_path_ref:
            raise VFSWALRecordError("rename intent requires target_path_ref")

        # Keep effect id aligned with ack evidence when present.
        if (
            self.acknowledgement.backend_effect_id
            and self.acknowledgement.backend_effect_id != self.effect_id
        ):
            raise InconsistentStateError(
                "acknowledgement.backend_effect_id must equal effect_id when set"
            )

        _bounded_record(self, "vfs wal durable data")

    def _payload(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "operation_id": self.operation_id,
            "effect_id": self.effect_id,
            "intent": self.intent.value,
            "content": self.content.to_dict(),
            "checksum": self.checksum,
            "preconditions": [item.to_dict() for item in self.preconditions],
            "decision": self.decision.value,
            "acknowledgement": self.acknowledgement.to_dict(),
            "intent_detail": dict(self.intent_detail),
            "path_ref": self.path_ref,
            "target_path_ref": self.target_path_ref,
            "generation_id": self.generation_id,
            "principal_id": self.principal_id,
            "created_at_unix_ms": self.created_at_unix_ms,
            "notes": self.notes,
        }

    def content_checksum_matches(self) -> bool:
        """Return whether ``checksum`` matches the content preimage."""

        preimage = {
            "intent": self.intent.value,
            "content": self.content.to_dict(),
            "intent_detail": self.intent_detail,
            "path_ref": self.path_ref,
            "target_path_ref": self.target_path_ref,
        }
        return self.checksum == checksum_for_preimage(preimage)

    def verify_checksum(self) -> None:
        if not self.content_checksum_matches():
            raise InconsistentStateError(
                "durable data checksum does not match content preimage"
            )

    def is_self_contained(self) -> bool:
        """Canonical records are always self-contained (no sidecar required)."""

        return True

    def compact_dict(self) -> dict[str, Any]:
        """Return a schema-free compact encoding suitable for WAL envelopes."""

        return {
            "transaction_id": self.transaction_id,
            "operation_id": self.operation_id,
            "effect_id": self.effect_id,
            "intent": self.intent.value,
            "content": self.content._payload(),
            "checksum": self.checksum,
            "preconditions": [item._payload() for item in self.preconditions],
            "decision": self.decision.value,
            "acknowledgement": self.acknowledgement._payload(),
            "intent_detail": dict(self.intent_detail),
            "path_ref": self.path_ref,
            "target_path_ref": self.target_path_ref,
            "generation_id": self.generation_id,
            "principal_id": self.principal_id,
            "created_at_unix_ms": self.created_at_unix_ms,
            "notes": self.notes,
        }

    def to_wal_record(
        self,
        *,
        generation_id: str | None = None,
        sequence_number: int,
        segment_id: str = "",
        state: WALRecordState = WALRecordState.APPENDED,
        previous_sequence: int = -1,
    ) -> WALRecord:
        """Frame this durable data as a self-contained :class:`WALRecord`.

        The full durable payload is embedded as a bounded inline envelope inside
        the WAL record payload.  Recovery can reconstruct :class:`VFSWALDurableData`
        from the WAL alone — no sidecar is required.

        Large mutation bodies must use :attr:`VFSWALContentKind.STAGED_CONTENT_REF`
        so the framed envelope remains within the inline bound; the staged CID is
        still part of the recoverable durable data.
        """

        gen = generation_id or self.generation_id
        if not gen:
            raise VFSWALRecordError(
                "generation_id is required to frame durable data as a WAL record"
            )

        # Prefer compact content in the envelope: if inline mutation bytes would
        # overflow the envelope, require a staged content reference instead.
        content_for_envelope = self.content
        if (
            content_for_envelope.kind is VFSWALContentKind.INLINE_BOUNDED
            and len(content_for_envelope.inline_payload.encode("utf-8"))
            > MAX_INLINE_PAYLOAD_BYTES // 2
        ):
            raise VFSWALRecordBoundsError(
                "inline mutation payload is too large to frame self-contained; "
                "stage the content and use staged_content_ref"
            )

        envelope = {
            "envelope_kind": CANONICAL_ENVELOPE_KIND,
            "durable_data": self.compact_dict(),
        }
        envelope_json = json.dumps(
            envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        envelope_bytes = envelope_json.encode("utf-8")
        if len(envelope_bytes) > MAX_INLINE_PAYLOAD_BYTES:
            raise VFSWALRecordBoundsError(
                "durable data envelope exceeds inline framing bound; "
                "reduce intent_detail or use staged_content_ref for large bodies"
            )

        payload = PayloadReference(
            kind=PayloadKind.INLINE_BOUNDED,
            inline_utf8=envelope_json,
            size_bytes=len(envelope_bytes),
            media_type="application/vnd.ipfs-kit.vfs-wal-durable-data+json",
        )
        encoding = "vfs-wal-durable-data@1"

        kind = _decision_to_record_kind(self.decision, self.intent)
        ack_mode = self.acknowledgement.mode
        # Committed/prepared framed records must use states and ack modes that
        # the base WALRecord contract admits.
        framed_state = state
        if self.decision is VFSWALDecision.COMMITTED:
            if framed_state not in (
                WALRecordState.COMMITTED,
                WALRecordState.ARCHIVED,
                WALRecordState.REPLAYED,
            ):
                framed_state = WALRecordState.COMMITTED
        elif self.decision is VFSWALDecision.ABORTED:
            if framed_state not in (
                WALRecordState.ABORTED,
                WALRecordState.APPENDED,
            ):
                framed_state = WALRecordState.ABORTED

        return WALRecord(
            generation_id=gen,
            sequence_number=sequence_number,
            kind=kind,
            state=framed_state,
            acknowledgement_mode=ack_mode,
            transaction_id=self.transaction_id,
            segment_id=segment_id,
            record_key=f"vfs:{self.transaction_id}:{self.effect_id}:{self.decision.value}",
            payload=payload,
            payload_cid=(
                self.content.staged_content_cid
                if self.content.kind is VFSWALContentKind.STAGED_CONTENT_REF
                else ""
            ),
            checksum=self.checksum,
            previous_sequence=previous_sequence,
            encoding=encoding,
            fsync_receipt_id=self.acknowledgement.fsync_receipt_id,
            backend_effect_id=self.effect_id,
            operation_id=self.operation_id,
            principal_id=self.principal_id,
            created_at_unix_ms=self.created_at_unix_ms,
            notes="canonical-vfs-wal-durable-data",
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VFSWALDurableData":
        fields = (
            "transaction_id",
            "operation_id",
            "effect_id",
            "intent",
            "content",
            "checksum",
            "preconditions",
            "decision",
            "acknowledgement",
            "intent_detail",
            "path_ref",
            "target_path_ref",
            "generation_id",
            "principal_id",
            "created_at_unix_ms",
            "notes",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "vfs wal durable data")
        content_raw = raw.get("content")
        if isinstance(content_raw, Mapping):
            content = VFSWALContent.from_dict(content_raw)
        elif content_raw is None:
            content = VFSWALContent.empty()
        else:
            raise VFSWALRecordError("content must be an object")
        preconditions_raw = raw.get("preconditions") or ()
        preconditions = tuple(
            VFSWALPrecondition.from_dict(item)
            if isinstance(item, Mapping)
            else item
            for item in preconditions_raw
        )
        ack_raw = raw.get("acknowledgement")
        if isinstance(ack_raw, Mapping):
            acknowledgement = VFSWALAcknowledgement.from_dict(ack_raw)
        elif ack_raw is None:
            acknowledgement = VFSWALAcknowledgement.buffered()
        else:
            raise VFSWALRecordError("acknowledgement must be an object")
        value = cls(
            transaction_id=raw["transaction_id"] or "",
            operation_id=raw["operation_id"] or "",
            effect_id=raw["effect_id"] or "",
            intent=(
                raw["intent"] if raw["intent"] is not None else VFSWALIntentKind.UNKNOWN
            ),
            content=content,
            checksum=raw.get("checksum") or "",
            preconditions=preconditions,
            decision=(
                raw["decision"]
                if raw["decision"] is not None
                else VFSWALDecision.INTENT_RECORDED
            ),
            acknowledgement=acknowledgement,
            intent_detail=dict(raw.get("intent_detail") or {}),
            path_ref=raw.get("path_ref") or "",
            target_path_ref=raw.get("target_path_ref") or "",
            generation_id=raw.get("generation_id") or "",
            principal_id=raw.get("principal_id") or "",
            created_at_unix_ms=int(raw.get("created_at_unix_ms") or 0),
            notes=raw.get("notes") or "",
        )
        _verify_identity(payload, value)
        return value

    @classmethod
    def from_compact_dict(cls, payload: Mapping[str, Any]) -> "VFSWALDurableData":
        """Decode a compact envelope payload (schema fields optional)."""

        if not isinstance(payload, Mapping):
            raise VFSWALRecordError("compact durable data must be an object")
        content_raw = payload.get("content") or {}
        if not isinstance(content_raw, Mapping):
            raise VFSWALRecordError("content must be an object")
        content = VFSWALContent.from_dict(_with_schema(content_raw, VFS_WAL_CONTENT_SCHEMA))
        preconditions_raw = payload.get("preconditions") or ()
        preconditions: list[VFSWALPrecondition] = []
        for item in preconditions_raw:
            if not isinstance(item, Mapping):
                raise VFSWALRecordError("precondition entries must be objects")
            preconditions.append(
                VFSWALPrecondition.from_dict(
                    _with_schema(item, VFS_WAL_PRECONDITION_SCHEMA)
                )
            )
        ack_raw = payload.get("acknowledgement") or {}
        if not isinstance(ack_raw, Mapping):
            raise VFSWALRecordError("acknowledgement must be an object")
        acknowledgement = VFSWALAcknowledgement.from_dict(
            _with_schema(ack_raw, VFS_WAL_ACK_SCHEMA)
        )
        return cls(
            transaction_id=str(payload.get("transaction_id") or ""),
            operation_id=str(payload.get("operation_id") or ""),
            effect_id=str(payload.get("effect_id") or ""),
            intent=payload.get("intent") or VFSWALIntentKind.UNKNOWN,
            content=content,
            checksum=str(payload.get("checksum") or ""),
            preconditions=tuple(preconditions),
            decision=payload.get("decision") or VFSWALDecision.INTENT_RECORDED,
            acknowledgement=acknowledgement,
            intent_detail=dict(payload.get("intent_detail") or {}),
            path_ref=str(payload.get("path_ref") or ""),
            target_path_ref=str(payload.get("target_path_ref") or ""),
            generation_id=str(payload.get("generation_id") or ""),
            principal_id=str(payload.get("principal_id") or ""),
            created_at_unix_ms=int(payload.get("created_at_unix_ms") or 0),
            notes=str(payload.get("notes") or ""),
        )

    @classmethod
    def from_wal_record(cls, record: WALRecord) -> "VFSWALDurableData | None":
        """Extract canonical durable data from a framed WAL record, if present."""

        payload = record.payload
        if payload is None:
            return None
        if payload.kind is PayloadKind.INLINE_BOUNDED and payload.inline_utf8:
            try:
                envelope = json.loads(payload.inline_utf8)
            except json.JSONDecodeError:
                return None
            if not isinstance(envelope, Mapping):
                return None
            if envelope.get("envelope_kind") != CANONICAL_ENVELOPE_KIND:
                return None
            durable_raw = envelope.get("durable_data")
            if not isinstance(durable_raw, Mapping):
                return None
            # Compact envelopes omit nested schema markers; full to_dict forms
            # already carry them.
            if "schema" in durable_raw:
                return cls.from_dict(durable_raw)
            return cls.from_compact_dict(durable_raw)
        return None


def _with_schema(payload: Mapping[str, Any], schema: str) -> dict[str, Any]:
    """Inject schema/contract_version so nested from_dict accepts compact forms."""

    hydrated = dict(payload)
    hydrated.setdefault("schema", schema)
    hydrated.setdefault("contract_version", CONTRACT_VERSION)
    return hydrated


def _decision_to_record_kind(
    decision: VFSWALDecision, intent: VFSWALIntentKind
) -> WALRecordKind:
    if decision is VFSWALDecision.COMMITTED:
        return WALRecordKind.COMMIT
    if decision is VFSWALDecision.ABORTED:
        return WALRecordKind.ABORT
    if decision is VFSWALDecision.COMMIT_PENDING:
        return WALRecordKind.PREPARE
    if decision is VFSWALDecision.INTENT_RECORDED:
        return WALRecordKind.INTENT
    if decision is VFSWALDecision.COMPENSATED:
        return WALRecordKind.ABORT
    if intent is VFSWALIntentKind.FSYNC:
        return WALRecordKind.FSYNC_MARKER
    return WALRecordKind.MUTATE


def compute_content_checksum(
    *,
    intent: VFSWALIntentKind | str,
    content: VFSWALContent,
    intent_detail: Mapping[str, Any] | None = None,
    path_ref: str = "",
    target_path_ref: str = "",
) -> str:
    """Compute the required content checksum for durable data."""

    intent_value = intent.value if isinstance(intent, VFSWALIntentKind) else str(intent)
    preimage = {
        "intent": intent_value,
        "content": content.to_dict(),
        "intent_detail": dict(intent_detail or {}),
        "path_ref": path_ref,
        "target_path_ref": target_path_ref,
    }
    return checksum_for_preimage(preimage)


def make_durable_data(
    *,
    transaction_id: str,
    operation_id: str,
    effect_id: str,
    intent: VFSWALIntentKind | str,
    content: VFSWALContent | None = None,
    preconditions: Sequence[VFSWALPrecondition | Mapping[str, Any]] = (),
    decision: VFSWALDecision | str = VFSWALDecision.INTENT_RECORDED,
    acknowledgement: VFSWALAcknowledgement | None = None,
    intent_detail: Mapping[str, Any] | None = None,
    path_ref: str = "",
    target_path_ref: str = "",
    generation_id: str = "",
    principal_id: str = "",
    created_at_unix_ms: int = 0,
    notes: str = "",
    checksum: str = "",
) -> VFSWALDurableData:
    """Factory that fills checksum and default acknowledgement when omitted."""

    if not isinstance(intent, VFSWALIntentKind):
        intent = VFSWALIntentKind(intent)
    if not isinstance(decision, VFSWALDecision):
        decision = VFSWALDecision(decision)
    content = content or VFSWALContent.empty()
    # Reject secrets / bodies before hashing so failure modes stay explicit.
    detail = _mapping(intent_detail, "intent_detail") if intent_detail else {}
    if not checksum:
        checksum = compute_content_checksum(
            intent=intent,
            content=content,
            intent_detail=detail,
            path_ref=path_ref,
            target_path_ref=target_path_ref,
        )
    if acknowledgement is None:
        if decision is VFSWALDecision.COMMITTED:
            acknowledgement = VFSWALAcknowledgement(
                mode=WALAcknowledgementMode.WAL_FSYNC_PARENT,
                durable=True,
                fsync_receipt_id=f"fsync:{effect_id}",
                file_fsync=True,
                parent_directory_fsync=True,
                backend_effect_id=effect_id,
            )
        else:
            acknowledgement = VFSWALAcknowledgement.buffered()
    normalized_preconditions: list[VFSWALPrecondition] = []
    for item in preconditions:
        if isinstance(item, VFSWALPrecondition):
            normalized_preconditions.append(item)
        else:
            normalized_preconditions.append(VFSWALPrecondition.from_dict(item))
    return VFSWALDurableData(
        transaction_id=transaction_id,
        operation_id=operation_id,
        effect_id=effect_id,
        intent=intent,
        content=content,
        checksum=checksum,
        preconditions=tuple(normalized_preconditions),
        decision=decision,
        acknowledgement=acknowledgement,
        intent_detail=detail,
        path_ref=path_ref,
        target_path_ref=target_path_ref,
        generation_id=generation_id,
        principal_id=principal_id,
        created_at_unix_ms=created_at_unix_ms,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Marker / sidecar gap classification (legacy compatibility reader)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarkerSidecarObservation:
    """One observed transaction across WAL markers and optional sidecar lines."""

    transaction_id: str
    gap_kind: MarkerSidecarGapKind
    marker_kinds: tuple[str, ...] = ()
    sidecar_kinds: tuple[str, ...] = ()
    effect_ids: tuple[str, ...] = ()
    durable_data: VFSWALDurableData | None = None
    recoverable: bool = False
    reason: str = ""


def classify_marker_sidecar_gap(
    *,
    transaction_id: str,
    wal_records: Sequence[WALRecord] = (),
    sidecar_entries: Sequence[Mapping[str, Any]] = (),
    durable_data: Sequence[VFSWALDurableData] = (),
) -> MarkerSidecarObservation:
    """Classify the marker↔sidecar relationship for one transaction.

    Recovery rules (fail-closed):

    * Canonical self-contained durable data is always recoverable.
    * Legacy marker + matching sidecar intent is recoverable.
    * Marker without sidecar is **not** recoverable for intent bodies
      (the historic crash gap).
    * Sidecar without marker is **not** acknowledged durable work.
    """

    txn_records = [
        record
        for record in wal_records
        if record.transaction_id == transaction_id
    ]
    txn_sidecar = [
        entry
        for entry in sidecar_entries
        if entry.get("transaction_id") == transaction_id
    ]
    txn_durable = [
        item for item in durable_data if item.transaction_id == transaction_id
    ]
    # Prefer explicit durable data, else try extract from framed records.
    if not txn_durable:
        for record in txn_records:
            extracted = VFSWALDurableData.from_wal_record(record)
            if extracted is not None:
                txn_durable.append(extracted)

    if txn_durable:
        primary = txn_durable[-1]
        return MarkerSidecarObservation(
            transaction_id=transaction_id,
            gap_kind=MarkerSidecarGapKind.CANONICAL_SELF_CONTAINED,
            marker_kinds=tuple(record.kind.value for record in txn_records),
            sidecar_kinds=tuple(str(entry.get("kind", "")) for entry in txn_sidecar),
            effect_ids=tuple(sorted({item.effect_id for item in txn_durable})),
            durable_data=primary,
            recoverable=True,
            reason="canonical durable data is self-contained; sidecar not required",
        )

    marker_kinds = tuple(record.kind.value for record in txn_records)
    sidecar_kinds = tuple(str(entry.get("kind", "")) for entry in txn_sidecar)
    effect_ids = tuple(
        sorted(
            {
                str(entry.get("effect_id"))
                for entry in txn_sidecar
                if entry.get("effect_id")
            }
            | {
                record.backend_effect_id or record.operation_id
                for record in txn_records
                if record.backend_effect_id or record.operation_id
            }
        )
    )

    has_marker = bool(txn_records)
    has_sidecar = bool(txn_sidecar)
    has_intent_sidecar = any(entry.get("kind") == "intent" for entry in txn_sidecar)
    has_effect_marker = any(
        record.kind in (WALRecordKind.INTENT, WALRecordKind.MUTATE)
        for record in txn_records
    )
    has_only_boundary_markers = has_marker and not has_effect_marker

    if has_marker and has_intent_sidecar:
        return MarkerSidecarObservation(
            transaction_id=transaction_id,
            gap_kind=MarkerSidecarGapKind.MARKER_AND_SIDECAR,
            marker_kinds=marker_kinds,
            sidecar_kinds=sidecar_kinds,
            effect_ids=effect_ids,
            recoverable=True,
            reason="legacy marker and sidecar intent both present",
        )
    # Intent/mutate markers without a matching intent sidecar body are the
    # historic marker-to-sidecar crash gap — even if begin/commit sidecar lines
    # exist.  Recovery must not invent the missing intent body.
    if has_effect_marker and not has_intent_sidecar:
        return MarkerSidecarObservation(
            transaction_id=transaction_id,
            gap_kind=MarkerSidecarGapKind.MARKER_WITHOUT_SIDECAR,
            marker_kinds=marker_kinds,
            sidecar_kinds=sidecar_kinds,
            effect_ids=effect_ids,
            recoverable=False,
            reason=(
                "marker-to-sidecar crash gap: WAL intent/mutate marker present "
                "without sidecar intent body; not recoverable without canonical "
                "durable data"
            ),
        )
    if has_marker and not has_sidecar:
        return MarkerSidecarObservation(
            transaction_id=transaction_id,
            gap_kind=MarkerSidecarGapKind.MARKER_WITHOUT_SIDECAR,
            marker_kinds=marker_kinds,
            sidecar_kinds=sidecar_kinds,
            effect_ids=effect_ids,
            recoverable=False,
            reason=(
                "marker-to-sidecar crash gap: WAL marker present without sidecar "
                "intent body; not recoverable without canonical durable data"
            ),
        )
    if has_sidecar and not has_marker:
        return MarkerSidecarObservation(
            transaction_id=transaction_id,
            gap_kind=MarkerSidecarGapKind.SIDECAR_WITHOUT_MARKER,
            marker_kinds=marker_kinds,
            sidecar_kinds=sidecar_kinds,
            effect_ids=effect_ids,
            recoverable=False,
            reason=(
                "sidecar entry without WAL marker is not acknowledged durable work"
            ),
        )
    if has_only_boundary_markers and has_sidecar and not has_intent_sidecar:
        # begin/commit/abort markers with decision sidecar lines only.
        return MarkerSidecarObservation(
            transaction_id=transaction_id,
            gap_kind=MarkerSidecarGapKind.DECISION_ONLY,
            marker_kinds=marker_kinds,
            sidecar_kinds=sidecar_kinds,
            effect_ids=effect_ids,
            recoverable=False,
            reason="decision markers without intent body cannot reconstruct effects",
        )
    return MarkerSidecarObservation(
        transaction_id=transaction_id,
        gap_kind=MarkerSidecarGapKind.UNKNOWN,
        marker_kinds=marker_kinds,
        sidecar_kinds=sidecar_kinds,
        effect_ids=effect_ids,
        recoverable=False,
        reason="insufficient evidence to classify transaction",
    )


def read_sidecar_jsonl(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Read a legacy decision sidecar, preserving a valid line prefix on tear."""

    sidecar_path = Path(path)
    if not sidecar_path.exists():
        return ()
    entries: list[dict[str, Any]] = []
    with open(sidecar_path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                entry = json.loads(text)
            except json.JSONDecodeError:
                # Torn final line — stop; prior lines remain the valid prefix.
                break
            if isinstance(entry, dict):
                try:
                    _contains_secret_or_body(entry, path="sidecar")
                except (SecretMaterialError, BodyRejectedError):
                    # Secret/body contamination ends the trusted prefix.
                    break
                entries.append(entry)
    return tuple(entries)


# ---------------------------------------------------------------------------
# Segment recovery: corrupt tail preserves valid prefix
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSWALRecoveryPrefix(CanonicalContract):
    """Verified recoverable prefix of VFS durable data from WAL media."""

    SCHEMA: ClassVar[str] = VFS_WAL_RECOVERY_SCHEMA

    durable_records: tuple[VFSWALDurableData, ...]
    wal_records: tuple[WALRecord, ...]
    valid_bytes: int
    tail_corrupt: bool = False
    error: str = ""
    gap_observations: tuple[MarkerSidecarObservation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "valid_bytes",
            _bounded_int(self.valid_bytes, "valid_bytes", minimum=0),
        )
        object.__setattr__(
            self, "tail_corrupt", _bool(self.tail_corrupt, "tail_corrupt")
        )
        object.__setattr__(
            self, "error", _text(self.error, "error", limit=MAX_TEXT_BYTES)
        )
        # Bound counts only; nested contracts already validated.
        if len(self.durable_records) > MAX_REFERENCE_COUNT * 4:
            raise VFSWALRecordBoundsError("durable_records exceeds recovery bound")
        if len(self.wal_records) > MAX_REFERENCE_COUNT * 4:
            raise VFSWALRecordBoundsError("wal_records exceeds recovery bound")

    def _payload(self) -> dict[str, Any]:
        return {
            "durable_record_ids": [
                item.content_id for item in self.durable_records
            ],
            "wal_record_keys": [item.identity_key for item in self.wal_records],
            "valid_bytes": self.valid_bytes,
            "tail_corrupt": self.tail_corrupt,
            "error": self.error,
            "gap_kinds": [item.gap_kind.value for item in self.gap_observations],
        }

    @property
    def recoverable_transactions(self) -> tuple[str, ...]:
        return tuple(
            observation.transaction_id
            for observation in self.gap_observations
            if observation.recoverable
        )


def recover_vfs_wal_prefix(
    path: str | Path,
    *,
    disposition: WALCorruptionDisposition = WALCorruptionDisposition.BOUND_AND_REPORT,
    sidecar_path: str | Path | None = None,
) -> VFSWALRecoveryPrefix:
    """Recover the verified VFS durable prefix from a WAL segment.

    A corrupt or torn tail never discards prior valid frames.  When a legacy
    sidecar path is supplied, marker-to-sidecar crash gaps are classified so
    incomplete pairs are not treated as recoverable transactions.
    """

    segment: SegmentRecovery = recover_segment(path, disposition=disposition)
    durable: list[VFSWALDurableData] = []
    for record in segment.records:
        extracted = VFSWALDurableData.from_wal_record(record)
        if extracted is not None:
            durable.append(extracted)

    sidecar_entries: tuple[dict[str, Any], ...] = ()
    if sidecar_path is not None:
        sidecar_entries = read_sidecar_jsonl(sidecar_path)

    transaction_ids: set[str] = set()
    for record in segment.records:
        if record.transaction_id:
            transaction_ids.add(record.transaction_id)
    for entry in sidecar_entries:
        txn = entry.get("transaction_id")
        if isinstance(txn, str) and txn:
            transaction_ids.add(txn)
    for item in durable:
        transaction_ids.add(item.transaction_id)

    observations = tuple(
        classify_marker_sidecar_gap(
            transaction_id=txn_id,
            wal_records=segment.records,
            sidecar_entries=sidecar_entries,
            durable_data=durable,
        )
        for txn_id in sorted(transaction_ids)
    )

    return VFSWALRecoveryPrefix(
        durable_records=tuple(durable),
        wal_records=segment.records,
        valid_bytes=segment.valid_bytes,
        tail_corrupt=segment.tail_corrupt,
        error=segment.error,
        gap_observations=observations,
    )


def recoverable_transactions_from_prefix(
    prefix: VFSWALRecoveryPrefix,
) -> tuple[VFSWALDurableData, ...]:
    """Return only transactions that are safely recoverable from ``prefix``."""

    by_txn: dict[str, VFSWALDurableData] = {}
    for item in prefix.durable_records:
        by_txn[item.transaction_id] = item
    result: list[VFSWALDurableData] = []
    for observation in prefix.gap_observations:
        if not observation.recoverable:
            continue
        if observation.durable_data is not None:
            result.append(observation.durable_data)
        elif observation.transaction_id in by_txn:
            result.append(by_txn[observation.transaction_id])
    return tuple(result)


def assert_no_unrecoverable_gaps(
    observations: Sequence[MarkerSidecarObservation],
    *,
    allow_decision_only: bool = True,
) -> None:
    """Raise if any non-canonical gap would lose acknowledged work ambiguously.

    ``MARKER_WITHOUT_SIDECAR`` after an intent/mutate marker is the historic
    crash gap: the marker claims work that the sidecar never recorded.
    """

    for observation in observations:
        if observation.gap_kind is MarkerSidecarGapKind.CANONICAL_SELF_CONTAINED:
            continue
        if observation.gap_kind is MarkerSidecarGapKind.MARKER_AND_SIDECAR:
            continue
        if (
            allow_decision_only
            and observation.gap_kind is MarkerSidecarGapKind.DECISION_ONLY
        ):
            continue
        if observation.gap_kind is MarkerSidecarGapKind.MARKER_WITHOUT_SIDECAR:
            # BEGIN-only markers without intent are incomplete but not silent
            # data loss of an effect body; still report when intent/mutate present.
            if any(
                kind in {"intent", "mutate"} for kind in observation.marker_kinds
            ):
                raise VFSWALGapError(
                    f"transaction {observation.transaction_id}: {observation.reason}"
                )
            continue
        if observation.gap_kind is MarkerSidecarGapKind.SIDECAR_WITHOUT_MARKER:
            # Not acknowledged — not an unrecoverable *acknowledged* write.
            continue


# ---------------------------------------------------------------------------
# Compatibility: project legacy sidecar intent into durable data when complete
# ---------------------------------------------------------------------------


def project_legacy_sidecar_intent(
    entry: Mapping[str, Any],
    *,
    operation_id: str = "",
    generation_id: str = "",
    decision: VFSWALDecision = VFSWALDecision.INTENT_RECORDED,
    acknowledgement: VFSWALAcknowledgement | None = None,
) -> VFSWALDurableData:
    """Project a complete legacy sidecar intent entry into canonical durable data.

    Requires ``transaction_id``, ``effect_id``, and ``intent`` fields.  Secrets
    and unbounded bodies are rejected.
    """

    if not isinstance(entry, Mapping):
        raise VFSWALRecordError("sidecar entry must be an object")
    _contains_secret_or_body(entry, path="legacy_sidecar")
    transaction_id = _identifier(entry.get("transaction_id"), "transaction_id")
    effect_id = _identifier(entry.get("effect_id"), "effect_id")
    intent_body = entry.get("intent")
    if not isinstance(intent_body, Mapping):
        raise VFSWALRecordError("legacy sidecar intent must be an object")
    _contains_secret_or_body(intent_body, path="legacy_sidecar.intent")
    # Intent bodies may declare a kind; default to mutate-like write.
    intent_kind_raw = intent_body.get("kind") or intent_body.get("intent") or "write"
    try:
        intent_kind = VFSWALIntentKind(str(intent_kind_raw))
    except ValueError:
        intent_kind = VFSWALIntentKind.WRITE
    path_ref = str(intent_body.get("path_ref") or intent_body.get("path") or "")
    if path_ref and not _ID_RE.match(path_ref):
        # Opaque-ize free-form paths into a stable path reference identity.
        path_ref = "path:" + hashlib.sha256(path_ref.encode("utf-8")).hexdigest()[:32]
    target = str(intent_body.get("target_path_ref") or intent_body.get("target") or "")
    if target and not _ID_RE.match(target):
        target = "path:" + hashlib.sha256(target.encode("utf-8")).hexdigest()[:32]
    inline = intent_body.get("inline_payload") or intent_body.get("content") or ""
    staged = intent_body.get("staged_content_cid") or intent_body.get("content_cid") or ""
    if staged:
        content = VFSWALContent.staged(str(staged), size_bytes=int(intent_body.get("size_bytes") or 0))
    elif inline:
        if not isinstance(inline, str):
            raise BodyRejectedError("legacy inline content must be a bounded string")
        content = VFSWALContent.inline(inline)
    else:
        content = VFSWALContent.empty()
    op_id = operation_id or str(entry.get("operation_id") or f"op:{effect_id}")
    detail = {
        key: value
        for key, value in intent_body.items()
        if key
        not in {
            "kind",
            "intent",
            "path",
            "path_ref",
            "target",
            "target_path_ref",
            "inline_payload",
            "content",
            "staged_content_cid",
            "content_cid",
            "size_bytes",
        }
    }
    return make_durable_data(
        transaction_id=transaction_id,
        operation_id=op_id,
        effect_id=effect_id,
        intent=intent_kind,
        content=content,
        decision=decision,
        acknowledgement=acknowledgement,
        intent_detail=detail,
        path_ref=path_ref,
        target_path_ref=target,
        generation_id=generation_id,
    )


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "VFSWALDurableData_V1",
    "VFSWALContent_V1",
    "VFSWALPrecondition_V1",
    "VFSWALAcknowledgement_V1",
    "CANONICAL_ENVELOPE_KIND",
    "MAX_RECORD_BYTES",
    "MAX_INLINE_PAYLOAD_BYTES",
    "VFSWALIntentKind",
    "VFSWALDecision",
    "VFSWALContentKind",
    "MarkerSidecarGapKind",
    "VFSWALRecordError",
    "VFSWALRecordBoundsError",
    "VFSWALRecoveryError",
    "VFSWALGapError",
    "VFSWALContent",
    "VFSWALPrecondition",
    "VFSWALAcknowledgement",
    "VFSWALDurableData",
    "MarkerSidecarObservation",
    "VFSWALRecoveryPrefix",
    "compute_content_checksum",
    "make_durable_data",
    "classify_marker_sidecar_gap",
    "read_sidecar_jsonl",
    "recover_vfs_wal_prefix",
    "recoverable_transactions_from_prefix",
    "assert_no_unrecoverable_gaps",
    "project_legacy_sidecar_intent",
    "WAL_CONTRACT_VERSION",
    "content_identity",
    "canonical_json_bytes",
    "SecretMaterialError",
    "BodyRejectedError",
    "ForgedIdentityError",
    "InconsistentStateError",
]

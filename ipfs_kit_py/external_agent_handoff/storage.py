"""Encrypted raw-export storage and public normalized projections (EAAEF-011).

Exact exported bytes are stored only as AES-256-GCM ciphertext behind a managed
``EncryptedExportReference@1``.  The ordered normalized stream is a separate
content-addressed identity.  Public receipts carry references, never transcript
bodies, private material, or hidden chain-of-thought.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import stat
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Final, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HANDOFF_STORAGE_CONTRACT_VERSION: Final[int] = 1
CONTRACT_VERSION: Final[int] = HANDOFF_STORAGE_CONTRACT_VERSION

ENCRYPTED_EXPORT_REFERENCE_INTERFACE: Final[str] = "EncryptedExportReference@1"
ENCRYPTED_EXPORT_REFERENCE_SCHEMA: Final[str] = (
    "ipfs_accelerate_py/agent-supervisor/encrypted-export-reference@1"
)
NORMALIZED_STREAM_SCHEMA: Final[str] = (
    "ipfs_accelerate_py/agent-supervisor/handoff-normalized-stream@1"
)
KEY_ENVELOPE_INTERFACE: Final[str] = "KeyEnvelope@1"
KEY_ENVELOPE_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-handoff/key-envelope@1"
)
PUBLIC_RECEIPT_INTERFACE: Final[str] = "HandoffStoragePublicReceipt@1"
PUBLIC_RECEIPT_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-handoff/public-receipt@1"
)
PUBLIC_EXPORT_RECEIPT_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-handoff/public-export-receipt@1"
)
NORMALIZED_PROJECTION_INTERFACE: Final[str] = "HandoffNormalizedProjection@1"
NORMALIZED_PROJECTION_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-handoff/normalized-projection@1"
)

ENCRYPTION_ALGORITHM: Final[str] = "aes-256-gcm"
DISCLOSURE_ENCRYPTED_RAW: Final[str] = "encrypted_raw"
DISCLOSURE_PUBLIC_PROJECTION: Final[str] = "public_projection"
RETENTION_SESSION: Final[str] = "session"

DEFAULT_MAX_EXPORT_BYTES: Final[int] = 16_777_216
ABSOLUTE_MAX_EXPORT_BYTES: Final[int] = 67_108_864
DEFAULT_MAX_EVENTS: Final[int] = 1_024
ABSOLUTE_MAX_EVENTS: Final[int] = 4_096
ABSOLUTE_MAX_ID_BYTES: Final[int] = 256
COMPAT_MAX_EXPORT_BYTES: Final[int] = 1_048_576
AES_KEY_BYTES: Final[int] = 32
GCM_NONCE_BYTES: Final[int] = 12
GCM_TAG_BYTES: Final[int] = 16
AES_BLOCK_BYTES: Final[int] = 16

_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
_CIDV1_RE: Final[re.Pattern[str]] = re.compile(r"^b[a-z2-7]{20,}$")
_HEX64_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

_KEY_ID_INFO: Final[bytes] = b"eaaef-011.key-id.v1"

_HIDDEN_CHAIN_OF_THOUGHT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "chain_of_thought",
        "cot",
        "hidden_chain_of_thought",
        "hidden_cot",
        "hidden_reasoning",
        "hidden_thoughts",
        "internal_monologue",
        "model_thoughts",
        "private_reasoning",
        "private_thinking",
        "scratchpad",
        "thinking",
        "thinking_blocks",
        "thinking_private",
        "thinking_text",
    }
)
_PRIVATE_FIELD_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "credential",
        "hidden_witness",
        "password",
        "private_key",
        "private_premise",
        "private_witness",
        "refresh_token",
        "secret",
        "session_token",
        "transcript_body",
        "witness",
    }
)
_TRANSCRIPT_BODY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "body",
        "full_transcript",
        "raw_bytes",
        "raw_export",
        "raw_transcript",
        "transcript",
        "transcript_body",
        "transcript_text",
    }
)


class HandoffStorageError(ValueError):
    """Malformed, oversized, or unsafe handoff storage input."""


class HandoffStorageBoundsError(HandoffStorageError):
    """A stored export or projection exceeded a declared bound."""


class HandoffStorageIdentityError(HandoffStorageError):
    """A claimed content identity did not match stored bytes."""


class HandoffStorageIntegrityError(HandoffStorageError):
    """Ciphertext, tag, digest, or key envelope failed verification."""


class HandoffStorageDisclosureError(HandoffStorageError):
    """Public material embedded a transcript body or private field."""


def _normalize_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def _key_is_forbidden(key: str) -> str | None:
    normalized = _normalize_key(key)
    if normalized in _HIDDEN_CHAIN_OF_THOUGHT_KEYS:
        return "hidden_chain_of_thought"
    if normalized in _TRANSCRIPT_BODY_KEYS:
        return "transcript_body"
    if any(
        normalized == marker or normalized.endswith("_" + marker) or marker in normalized
        for marker in _PRIVATE_FIELD_MARKERS
    ):
        return "private_material"
    return None


def _reject_forbidden_keys(value: Any, *, name: str) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            reason = _key_is_forbidden(str(raw_key))
            if reason == "hidden_chain_of_thought":
                raise HandoffStorageDisclosureError(
                    f"{name} must not represent hidden chain-of-thought"
                )
            if reason == "transcript_body":
                raise HandoffStorageDisclosureError(
                    f"{name} must not embed transcript bodies; use content-addressed references"
                )
            if reason == "private_material":
                raise HandoffStorageDisclosureError(
                    f"{name} must not contain private material"
                )
            _reject_forbidden_keys(item, name=name)
        return
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        for item in value:
            _reject_forbidden_keys(item, name=name)


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return value
    if isinstance(value, float):
        raise HandoffStorageError("canonical storage contracts cannot contain floats")
    if isinstance(value, Mapping):
        if not all(isinstance(raw_key, str) for raw_key in value):
            raise HandoffStorageError("canonical object keys must be strings")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    raise HandoffStorageError(
        f"unsupported canonical storage value: {type(value).__name__}"
    )


def canonical_storage_json_bytes(value: Any) -> bytes:
    """Encode deterministic DAG-JSON-compatible UTF-8 bytes."""

    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_identity(value: Any) -> str:
    """Return a CIDv1 DAG-JSON/sha2-256 identity for ``value``."""

    digest = hashlib.sha256(canonical_storage_json_bytes(value)).digest()
    raw = b"\x01\xa9\x02\x12\x20" + digest
    return "b" + base64.b32encode(raw).decode("ascii").rstrip("=").lower()


def sha256_identity(data: bytes) -> str:
    """Return ``sha256:<hex>`` of exact bytes."""

    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise HandoffStorageError("sha256 identity requires exact bytes")
    return "sha256:" + hashlib.sha256(bytes(data)).hexdigest()


def digest_sha256(data: bytes, *, prefixed: bool = True) -> str:
    """Return the plaintext SHA-256 digest.

    The rich contract uses the prefixed identity.  ``prefixed=False`` is kept
    only for the pre-contract directory-store compatibility surface.
    """

    identity = sha256_identity(data)
    return identity if prefixed else identity[7:]


def normalized_stream_identity(event_content_ids: Sequence[str]) -> str:
    """Return the content identity of one ordered normalized event stream."""

    return content_identity(
        {
            "schema": NORMALIZED_STREAM_SCHEMA,
            "contract_version": HANDOFF_STORAGE_CONTRACT_VERSION,
            "event_content_ids": list(event_content_ids),
        }
    )


def _content_ref(value: Any, name: str, *, required: bool = True) -> str:
    if value is None:
        text = ""
    elif not isinstance(value, str):
        raise HandoffStorageError(f"{name} must be a string")
    else:
        text = value.strip()
    if required and not text:
        raise HandoffStorageError(f"{name} is required")
    if not text:
        return ""
    if _SHA256_RE.fullmatch(text) or _CIDV1_RE.fullmatch(text):
        return text
    raise HandoffStorageError(f"{name} must be a sha256 or CIDv1 identity")


def _digest_field(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise HandoffStorageError(f"{name} must be a string")
    text = value.strip()
    if _HEX64_RE.fullmatch(text):
        return f"sha256:{text}"
    if _SHA256_RE.fullmatch(text):
        return text
    raise HandoffStorageError(f"{name} must be a sha256 hex digest")


def _require_bytes(value: Any, name: str) -> bytes:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytearray):
        value = bytes(value)
    if not isinstance(value, bytes):
        raise HandoffStorageError(f"{name} must be exact bytes")
    return value


def _distinct_identities(pairs: Sequence[tuple[str, str]]) -> None:
    seen: dict[str, str] = {}
    for name, identity in pairs:
        if not identity:
            continue
        previous = seen.get(identity)
        if previous is not None and previous != name:
            raise HandoffStorageIdentityError(
                f"{name} identity must be distinct from {previous}"
            )
        seen[identity] = name


def aes_256_encrypt_block(key: bytes, block: bytes) -> bytes:
    """Encrypt one block with the maintained ``cryptography`` AES primitive."""

    key = _require_bytes(key, "key")
    if len(key) != AES_KEY_BYTES:
        raise HandoffStorageError("AES-256 key must be 32 bytes")
    block = _require_bytes(block, "block")
    if len(block) != AES_BLOCK_BYTES:
        raise HandoffStorageError("AES block must be 16 bytes")
    encryptor = Cipher(algorithms.AES256(key), modes.ECB()).encryptor()
    return encryptor.update(block) + encryptor.finalize()


def aes_256_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Return the legacy-compatible ``nonce || ciphertext || tag`` wire form."""

    key = _require_bytes(key, "key")
    nonce = _require_bytes(nonce, "nonce")
    plaintext = _require_bytes(plaintext, "plaintext")
    aad = _require_bytes(aad, "aad")
    if len(key) != AES_KEY_BYTES:
        raise HandoffStorageError("AES-256-GCM key must be 32 bytes")
    if len(nonce) != GCM_NONCE_BYTES:
        raise HandoffStorageError("AES-256-GCM nonce must be 12 bytes")
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def aes_256_gcm_decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    """Decrypt ``nonce || ciphertext || tag`` and verify the GCM tag."""

    key = _require_bytes(key, "key")
    blob = _require_bytes(blob, "ciphertext")
    aad = _require_bytes(aad, "aad")
    if len(key) != AES_KEY_BYTES:
        raise HandoffStorageError("AES-256-GCM key must be 32 bytes")
    if len(blob) < GCM_NONCE_BYTES + GCM_TAG_BYTES:
        raise HandoffStorageIntegrityError("ciphertext is truncated")
    nonce = blob[:GCM_NONCE_BYTES]
    try:
        return AESGCM(key).decrypt(nonce, blob[GCM_NONCE_BYTES:], aad)
    except InvalidTag as exc:
        raise HandoffStorageIntegrityError("ciphertext authentication failed") from exc


def _hkdf_like(master_key: bytes, info: bytes, length: int) -> bytes:
    digest = hmac.new(master_key, info, hashlib.sha256).digest()
    if length > len(digest):
        raise HandoffStorageError("derived material exceeds HMAC-SHA256 output")
    return digest[:length]


# ---------------------------------------------------------------------------
# Content-addressed blob store
# ---------------------------------------------------------------------------


class BlobStore(Protocol):
    """Content-addressed byte store for ciphertext, envelopes, and projections."""

    def put(self, cid: str, data: bytes) -> None:
        """Persist exact bytes at ``cid``."""

    def get(self, cid: str) -> bytes:
        """Return exact stored bytes for ``cid``."""

    def __contains__(self, cid: object) -> bool:
        """Return whether ``cid`` is present."""

    def items(self) -> Iterator[tuple[str, bytes]]:
        """Iterate ``(cid, exact bytes)`` pairs."""


class MemoryBlobStore:
    """In-memory CAS.  Never writes plaintext; callers supply ciphertext only."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def put(self, cid: str, data: bytes) -> None:
        payload = _require_bytes(data, "blob")
        identity = _content_ref(cid, "cid")
        existing = self._blobs.get(identity)
        if existing is not None and existing != payload:
            raise HandoffStorageIdentityError("blob identity collision")
        self._blobs[identity] = payload

    def get(self, cid: str) -> bytes:
        identity = _content_ref(cid, "cid")
        try:
            return self._blobs[identity]
        except KeyError as exc:
            raise HandoffStorageIntegrityError("blob is missing") from exc

    def __contains__(self, cid: object) -> bool:
        if not isinstance(cid, str):
            return False
        try:
            identity = _content_ref(cid, "cid")
        except HandoffStorageError:
            return False
        return identity in self._blobs

    def items(self) -> Iterator[tuple[str, bytes]]:
        return iter(self._blobs.items())


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HandoffStorageError(f"{name} must be a non-negative integer")
    return value


def _text(value: Any, name: str, *, required: bool = True, max_bytes: int = ABSOLUTE_MAX_ID_BYTES) -> str:
    if value is None:
        result = ""
    elif not isinstance(value, str):
        raise HandoffStorageError(f"{name} must be a string")
    else:
        result = value.strip()
    if required and not result:
        raise HandoffStorageError(f"{name} is required")
    if "\x00" in result:
        raise HandoffStorageError(f"{name} must not contain NUL")
    if len(result.encode("utf-8")) > max_bytes:
        raise HandoffStorageBoundsError(f"{name} exceeds {max_bytes} UTF-8 bytes")
    return result


class _CanonicalRecord:
    SCHEMA: ClassVar[str] = ""
    INTERFACE: ClassVar[str] = ""

    def _payload(self) -> dict[str, Any]:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": self.SCHEMA,
            "interface": self.INTERFACE,
            "contract_version": HANDOFF_STORAGE_CONTRACT_VERSION,
            **self._payload(),
        }
        _reject_forbidden_keys(payload, name=self.INTERFACE or "storage record")
        return _canonical_value(payload)

    def to_json(self) -> str:
        return canonical_storage_json_bytes(self.to_dict()).decode("utf-8")

    def canonical_bytes(self) -> bytes:
        return canonical_storage_json_bytes(self.to_dict())

    @property
    def content_id(self) -> str:
        return content_identity(self.to_dict())

    def to_record(self) -> dict[str, Any]:
        return {**self.to_dict(), "content_id": self.content_id}


@dataclass(frozen=True)
class EncryptedExportReference(_CanonicalRecord):
    """Content-addressed pointer to encrypted raw export bytes."""

    SCHEMA: ClassVar[str] = ENCRYPTED_EXPORT_REFERENCE_SCHEMA
    INTERFACE: ClassVar[str] = ENCRYPTED_EXPORT_REFERENCE_INTERFACE

    ciphertext_cid: str
    digest_sha256: str
    byte_count: int
    key_envelope_cid: str
    media_type: str = "application/octet-stream"
    encryption_algorithm: str = ENCRYPTION_ALGORITHM
    disclosure_class: str = DISCLOSURE_ENCRYPTED_RAW
    retention_class: str = RETENTION_SESSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "ciphertext_cid", _content_ref(self.ciphertext_cid, "ciphertext_cid")
        )
        object.__setattr__(
            self, "digest_sha256", _digest_field(self.digest_sha256, "digest_sha256")
        )
        object.__setattr__(
            self, "byte_count", _nonnegative_int(self.byte_count, "byte_count")
        )
        object.__setattr__(
            self,
            "key_envelope_cid",
            _content_ref(self.key_envelope_cid, "key_envelope_cid"),
        )
        object.__setattr__(
            self,
            "media_type",
            _text(self.media_type, "media_type", max_bytes=ABSOLUTE_MAX_ID_BYTES),
        )
        object.__setattr__(
            self,
            "encryption_algorithm",
            _text(self.encryption_algorithm, "encryption_algorithm"),
        )
        if self.encryption_algorithm != ENCRYPTION_ALGORITHM:
            raise HandoffStorageError("encrypted export references must use aes-256-gcm")
        object.__setattr__(
            self,
            "disclosure_class",
            _text(self.disclosure_class, "disclosure_class"),
        )
        if self.disclosure_class != DISCLOSURE_ENCRYPTED_RAW:
            raise HandoffStorageError(
                "encrypted export references must use encrypted_raw disclosure"
            )
        object.__setattr__(
            self, "retention_class", _text(self.retention_class, "retention_class")
        )
        _distinct_identities(
            (
                ("ciphertext", self.ciphertext_cid),
                ("digest", self.digest_sha256),
                ("key_envelope", self.key_envelope_cid),
            )
        )
        _reject_forbidden_keys(self.to_dict(), name="encrypted export reference")

    def _payload(self) -> dict[str, Any]:
        return {
            "ciphertext_cid": self.ciphertext_cid,
            "digest_sha256": self.digest_sha256,
            "byte_count": self.byte_count,
            "media_type": self.media_type,
            "key_envelope_cid": self.key_envelope_cid,
            "encryption_algorithm": self.encryption_algorithm,
            "disclosure_class": self.disclosure_class,
            "retention_class": self.retention_class,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EncryptedExportReference:
        if not isinstance(payload, Mapping):
            raise HandoffStorageError("encrypted export reference must be an object")
        schema = payload.get("schema")
        if schema not in (None, "", ENCRYPTED_EXPORT_REFERENCE_SCHEMA):
            raise HandoffStorageError("unsupported encrypted export reference schema")
        interface = payload.get("interface")
        if interface not in (None, "", ENCRYPTED_EXPORT_REFERENCE_INTERFACE):
            raise HandoffStorageError("unsupported encrypted export reference interface")
        result = cls(
            ciphertext_cid=payload.get("ciphertext_cid", ""),
            digest_sha256=payload.get("digest_sha256", ""),
            byte_count=payload.get("byte_count", 0),
            key_envelope_cid=payload.get("key_envelope_cid", ""),
            media_type=payload.get("media_type", "application/octet-stream"),
            encryption_algorithm=payload.get(
                "encryption_algorithm", ENCRYPTION_ALGORITHM
            ),
            disclosure_class=payload.get("disclosure_class", DISCLOSURE_ENCRYPTED_RAW),
            retention_class=payload.get("retention_class", RETENTION_SESSION),
        )
        claimed = payload.get("content_id") or payload.get("cid")
        if claimed not in (None, "") and claimed != result.content_id:
            raise HandoffStorageIdentityError(
                "encrypted export reference content identity does not match payload"
            )
        return result


@dataclass(frozen=True)
class NormalizedProjection(_CanonicalRecord):
    """Ordered event-identity projection with no transcript bodies."""

    SCHEMA: ClassVar[str] = NORMALIZED_PROJECTION_SCHEMA
    INTERFACE: ClassVar[str] = NORMALIZED_PROJECTION_INTERFACE

    event_content_ids: tuple[str, ...]
    normalized_stream_id: str = ""

    def __post_init__(self) -> None:
        ids = _event_content_ids(self.event_content_ids)
        object.__setattr__(self, "event_content_ids", ids)
        expected = normalized_stream_identity(ids)
        supplied = _text(
            self.normalized_stream_id,
            "normalized_stream_id",
            required=False,
        )
        if supplied and supplied != expected:
            raise HandoffStorageIdentityError(
                "normalized_stream_id does not match event_content_ids"
            )
        object.__setattr__(self, "normalized_stream_id", expected)
        _reject_forbidden_keys(self.to_dict(), name="normalized projection")

    def _payload(self) -> dict[str, Any]:
        return {
            "normalized_stream_id": self.normalized_stream_id,
            "event_content_ids": list(self.event_content_ids),
        }

    @property
    def stream_id(self) -> str:
        """Compatibility name for the canonical normalized stream identity."""

        return self.normalized_stream_id

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> NormalizedProjection:
        if not isinstance(payload, Mapping):
            raise HandoffStorageError("normalized projection must be an object")
        return cls(
            event_content_ids=payload.get("event_content_ids", ()),
            normalized_stream_id=payload.get("normalized_stream_id", ""),
        )


@dataclass(frozen=True)
class PublicHandoffReceipt(_CanonicalRecord):
    """Public storage receipt.  References only; no transcript bodies."""

    SCHEMA: ClassVar[str] = PUBLIC_RECEIPT_SCHEMA
    INTERFACE: ClassVar[str] = PUBLIC_RECEIPT_INTERFACE

    raw_export_ref: EncryptedExportReference
    normalized_stream_id: str
    event_content_ids: tuple[str, ...]
    disclosure_class: str = DISCLOSURE_PUBLIC_PROJECTION
    created_at_ms: int = 0

    def __post_init__(self) -> None:
        export_ref = self.raw_export_ref
        if not isinstance(export_ref, EncryptedExportReference):
            if isinstance(export_ref, Mapping):
                export_ref = EncryptedExportReference.from_dict(export_ref)
            else:
                raise HandoffStorageError(
                    "raw_export_ref must be an EncryptedExportReference"
                )
        object.__setattr__(self, "raw_export_ref", export_ref)
        ids = _event_content_ids(self.event_content_ids)
        object.__setattr__(self, "event_content_ids", ids)
        expected = normalized_stream_identity(ids)
        supplied = _content_ref(self.normalized_stream_id, "normalized_stream_id")
        if supplied != expected:
            raise HandoffStorageIdentityError(
                "public receipt normalized_stream_id does not match event_content_ids"
            )
        object.__setattr__(self, "normalized_stream_id", expected)
        object.__setattr__(
            self,
            "disclosure_class",
            _text(self.disclosure_class, "disclosure_class"),
        )
        if self.disclosure_class != DISCLOSURE_PUBLIC_PROJECTION:
            raise HandoffStorageError(
                "public receipts must use public_projection disclosure"
            )
        object.__setattr__(
            self, "created_at_ms", _nonnegative_int(self.created_at_ms, "created_at_ms")
        )
        _distinct_identities(
            (
                ("raw_export", export_ref.content_id),
                ("ciphertext", export_ref.ciphertext_cid),
                ("digest", export_ref.digest_sha256),
                ("key_envelope", export_ref.key_envelope_cid),
                ("normalized_stream", self.normalized_stream_id),
            )
        )
        _reject_forbidden_keys(self.to_dict(), name="public handoff receipt")

    @property
    def raw_export_id(self) -> str:
        return self.raw_export_ref.content_id

    def _payload(self) -> dict[str, Any]:
        return {
            "raw_export_ref": self.raw_export_ref.to_dict(),
            "raw_export_id": self.raw_export_id,
            "normalized_stream_id": self.normalized_stream_id,
            "event_content_ids": list(self.event_content_ids),
            "disclosure_class": self.disclosure_class,
            "created_at_ms": self.created_at_ms,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PublicHandoffReceipt:
        if not isinstance(payload, Mapping):
            raise HandoffStorageError("public receipt must be an object")
        _reject_forbidden_keys(payload, name="public handoff receipt")
        if payload.get("transcript") not in (None, "") or payload.get(
            "transcript_body"
        ) not in (None, ""):
            raise HandoffStorageDisclosureError(
                "public receipts must not embed transcript bodies"
            )
        return cls(
            raw_export_ref=payload.get("raw_export_ref"),  # type: ignore[arg-type]
            normalized_stream_id=payload.get("normalized_stream_id", ""),
            event_content_ids=payload.get("event_content_ids", ()),
            disclosure_class=payload.get(
                "disclosure_class", DISCLOSURE_PUBLIC_PROJECTION
            ),
            created_at_ms=payload.get("created_at_ms", 0),
        )


@dataclass(frozen=True)
class HandoffPreservation:
    """Paired encrypted export reference and public normalized projection."""

    export_ref: EncryptedExportReference
    projection: NormalizedProjection
    public_receipt: PublicHandoffReceipt

    @property
    def raw_export_id(self) -> str:
        return self.export_ref.content_id

    @property
    def normalized_stream_id(self) -> str:
        return self.projection.normalized_stream_id


def _event_content_ids(values: Any) -> tuple[str, ...]:
    if values is None:
        items: Sequence[Any] = ()
    elif isinstance(values, (str, bytes, bytearray, memoryview)) or not isinstance(
        values, Sequence
    ):
        raise HandoffStorageError("event_content_ids must be a sequence of identities")
    else:
        items = values
    if len(items) > ABSOLUTE_MAX_EVENTS:
        raise HandoffStorageBoundsError("event_content_ids exceeds its item-count limit")
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, Mapping):
            identity = item.get("content_id") or item.get("event_id") or item.get("cid")
        else:
            identity = item
        text = _content_ref(identity, "event_content_id")
        if text in seen:
            raise HandoffStorageError("event_content_ids must not contain duplicate identities")
        seen.add(text)
        result.append(text)
    return tuple(result)


def _coerce_export_ref(value: Any) -> EncryptedExportReference:
    if isinstance(value, EncryptedExportReference):
        return value
    if isinstance(value, Mapping):
        return EncryptedExportReference.from_dict(value)
    raise HandoffStorageError("raw_export_ref must be an EncryptedExportReference object")


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class EncryptedHandoffStore:
    """Managed AES-256-GCM store for exact export bytes and public projections.

    Ciphertext, key envelopes, and the ordered normalized stream keep distinct
    identities.  The wrapping key never appears in public receipts.  Every put
    uses a fresh data key and independent random nonces; plaintext identity is
    stable while encrypted-object identities intentionally are not.
    """

    def __init__(
        self,
        master_key: bytes,
        *,
        blobs: BlobStore | None = None,
        max_export_bytes: int = DEFAULT_MAX_EXPORT_BYTES,
        max_events: int = DEFAULT_MAX_EVENTS,
    ) -> None:
        key = _require_bytes(master_key, "master_key")
        if len(key) != AES_KEY_BYTES:
            raise HandoffStorageError("master_key must be 32 bytes")
        if (
            isinstance(max_export_bytes, bool)
            or not isinstance(max_export_bytes, int)
            or max_export_bytes < 1
            or max_export_bytes > ABSOLUTE_MAX_EXPORT_BYTES
        ):
            raise HandoffStorageBoundsError("max_export_bytes is out of range")
        if (
            isinstance(max_events, bool)
            or not isinstance(max_events, int)
            or max_events < 1
            or max_events > ABSOLUTE_MAX_EVENTS
        ):
            raise HandoffStorageBoundsError("max_events is out of range")
        self._master_key = key
        self._blobs: BlobStore = blobs if blobs is not None else MemoryBlobStore()
        self.max_export_bytes = max_export_bytes
        self.max_events = max_events
        self._key_id = sha256_identity(_hkdf_like(key, _KEY_ID_INFO, 32))

    @property
    def key_id(self) -> str:
        """Fingerprint of the managed wrapping key, never the key itself."""

        return self._key_id

    @property
    def blobs(self) -> BlobStore:
        return self._blobs

    def store_exported_bytes(
        self,
        exported: bytes,
        *,
        media_type: str = "application/octet-stream",
        retention_class: str = RETENTION_SESSION,
    ) -> EncryptedExportReference:
        """Encrypt exact exported bytes and return a managed encrypted reference."""

        plaintext = _require_bytes(exported, "exported")
        if len(plaintext) > self.max_export_bytes:
            raise HandoffStorageBoundsError("exported bytes exceed max_export_bytes")
        digest = digest_sha256(plaintext)
        digest_raw = bytes.fromhex(digest.split(":", 1)[1])
        data_key = AESGCM.generate_key(bit_length=256)
        enc_nonce = os.urandom(GCM_NONCE_BYTES)
        wrap_nonce = os.urandom(GCM_NONCE_BYTES)
        ciphertext = aes_256_gcm_encrypt(data_key, enc_nonce, plaintext, aad=digest_raw)
        wrapped_key = aes_256_gcm_encrypt(
            self._master_key, wrap_nonce, data_key, aad=digest_raw
        )
        envelope = _canonical_value(
            {
                "schema": KEY_ENVELOPE_SCHEMA,
                "interface": KEY_ENVELOPE_INTERFACE,
                "contract_version": HANDOFF_STORAGE_CONTRACT_VERSION,
                "wrapping_algorithm": ENCRYPTION_ALGORITHM,
                "key_id": self._key_id,
                "nonce": wrap_nonce.hex(),
                "wrapped_key": wrapped_key.hex(),
            }
        )
        envelope_bytes = canonical_storage_json_bytes(envelope)
        ciphertext_cid = sha256_identity(ciphertext)
        key_envelope_cid = sha256_identity(envelope_bytes)
        self._blobs.put(ciphertext_cid, ciphertext)
        self._blobs.put(key_envelope_cid, envelope_bytes)
        return EncryptedExportReference(
            ciphertext_cid=ciphertext_cid,
            digest_sha256=digest,
            byte_count=len(plaintext),
            key_envelope_cid=key_envelope_cid,
            media_type=media_type,
            retention_class=retention_class,
        )

    def retrieve_exported_bytes(
        self, reference: EncryptedExportReference | Mapping[str, Any]
    ) -> bytes:
        """Return the exact exported bytes after verifying ciphertext and digest."""

        export_ref = _coerce_export_ref(reference)
        ciphertext = self._blobs.get(export_ref.ciphertext_cid)
        if sha256_identity(ciphertext) != export_ref.ciphertext_cid:
            raise HandoffStorageIntegrityError("ciphertext identity does not match stored bytes")
        envelope_bytes = self._blobs.get(export_ref.key_envelope_cid)
        if sha256_identity(envelope_bytes) != export_ref.key_envelope_cid:
            raise HandoffStorageIntegrityError("key envelope identity does not match stored bytes")
        try:
            envelope = json.loads(envelope_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HandoffStorageIntegrityError("key envelope is malformed") from exc
        if not isinstance(envelope, Mapping):
            raise HandoffStorageIntegrityError("key envelope must be an object")
        if (
            envelope.get("schema") != KEY_ENVELOPE_SCHEMA
            or envelope.get("interface") != KEY_ENVELOPE_INTERFACE
            or envelope.get("contract_version") != HANDOFF_STORAGE_CONTRACT_VERSION
            or envelope.get("wrapping_algorithm") != ENCRYPTION_ALGORITHM
        ):
            raise HandoffStorageIntegrityError("key envelope contract is not admitted")
        if envelope.get("key_id") != self._key_id:
            raise HandoffStorageIntegrityError("key envelope is bound to a different wrapping key")
        try:
            wrapped_key = bytes.fromhex(str(envelope.get("wrapped_key", "")))
            declared_nonce = bytes.fromhex(str(envelope.get("nonce", "")))
        except ValueError as exc:
            raise HandoffStorageIntegrityError("key envelope encryption fields are malformed") from exc
        if (
            len(declared_nonce) != GCM_NONCE_BYTES
            or wrapped_key[:GCM_NONCE_BYTES] != declared_nonce
        ):
            raise HandoffStorageIntegrityError("key envelope nonce does not match wrapped key")
        digest_raw = bytes.fromhex(export_ref.digest_sha256.split(":", 1)[1])
        try:
            data_key = aes_256_gcm_decrypt(
                self._master_key, wrapped_key, aad=digest_raw
            )
        except HandoffStorageIntegrityError as exc:
            raise HandoffStorageIntegrityError("key envelope authentication failed") from exc
        try:
            plaintext = aes_256_gcm_decrypt(data_key, ciphertext, aad=digest_raw)
        except HandoffStorageIntegrityError as exc:
            raise HandoffStorageIntegrityError("ciphertext authentication failed") from exc
        if digest_sha256(plaintext) != export_ref.digest_sha256:
            raise HandoffStorageIntegrityError("plaintext digest does not match the reference")
        if len(plaintext) != export_ref.byte_count:
            raise HandoffStorageIntegrityError("plaintext length does not match the reference")
        return plaintext

    def store_normalized_projection(
        self,
        event_content_ids: Sequence[Any],
        *,
        events: Sequence[Mapping[str, Any]] | None = None,
    ) -> NormalizedProjection:
        """Persist an ordered event-identity projection without transcript bodies."""

        if events is not None:
            if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
                raise HandoffStorageError("events must be a sequence of objects")
            for event in events:
                if not isinstance(event, Mapping):
                    raise HandoffStorageError("normalized events must be objects")
                _reject_forbidden_keys(event, name="normalized event")
        ids = _event_content_ids(event_content_ids)
        if len(ids) > self.max_events:
            raise HandoffStorageBoundsError("event_content_ids exceeds max_events")
        projection = NormalizedProjection(event_content_ids=ids)
        stream = {
            "schema": NORMALIZED_STREAM_SCHEMA,
            "contract_version": HANDOFF_STORAGE_CONTRACT_VERSION,
            "event_content_ids": list(ids),
        }
        _reject_forbidden_keys(stream, name="normalized stream")
        self._blobs.put(projection.normalized_stream_id, canonical_storage_json_bytes(stream))
        self._blobs.put(projection.content_id, projection.canonical_bytes())
        return projection

    def public_receipt(
        self,
        export_ref: EncryptedExportReference | Mapping[str, Any],
        projection: NormalizedProjection | Sequence[Any],
        *,
        created_at_ms: int = 0,
    ) -> PublicHandoffReceipt:
        """Emit a public receipt with references only."""

        reference = _coerce_export_ref(export_ref)
        if isinstance(projection, NormalizedProjection):
            stream = projection
        else:
            stream = NormalizedProjection(event_content_ids=tuple(projection))
        return PublicHandoffReceipt(
            raw_export_ref=reference,
            normalized_stream_id=stream.normalized_stream_id,
            event_content_ids=stream.event_content_ids,
            created_at_ms=created_at_ms,
        )

    def preserve(
        self,
        exported: bytes,
        event_content_ids: Sequence[Any],
        *,
        media_type: str = "application/octet-stream",
        retention_class: str = RETENTION_SESSION,
        created_at_ms: int = 0,
        events: Sequence[Mapping[str, Any]] | None = None,
    ) -> HandoffPreservation:
        """Store exact export bytes and emit a separate public projection."""

        export_ref = self.store_exported_bytes(
            exported, media_type=media_type, retention_class=retention_class
        )
        projection = self.store_normalized_projection(event_content_ids, events=events)
        receipt = self.public_receipt(
            export_ref, projection, created_at_ms=created_at_ms
        )
        return HandoffPreservation(
            export_ref=export_ref,
            projection=projection,
            public_receipt=receipt,
        )

    def stored_blobs(self) -> Mapping[str, bytes]:
        """Return a read-only snapshot of stored ciphertext, envelopes, and projections."""

        return MappingProxyType(dict(self._blobs.items()))


# ---------------------------------------------------------------------------
# Directory-backed compatibility adapter
# ---------------------------------------------------------------------------


def content_cid(payload: bytes | Mapping[str, Any]) -> str:
    """Return the historical directory-store identity using canonical primitives."""

    if isinstance(payload, Mapping):
        return content_identity(payload)
    return sha256_identity(_require_bytes(payload, "payload"))


def _private_directory(path: Path) -> Path:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise HandoffStorageError("storage roots must not contain symlinks")
    absolute.mkdir(parents=True, exist_ok=True, mode=0o700)
    if absolute.resolve(strict=True) != absolute:
        raise HandoffStorageError("storage root escapes through a symlink")
    metadata = absolute.stat(follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid():
        raise HandoffStorageError("storage root must be an owned directory")
    if metadata.st_mode & 0o022:
        raise HandoffStorageError("storage root must not be group/world writable")
    os.chmod(absolute, 0o700, follow_symlinks=False)
    return absolute


def _private_filename(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9]{16,128}", value):
        raise HandoffStorageIdentityError("private object filename is not content-addressed")
    return value


def _read_private_file(directory: Path, filename: str, *, max_bytes: int) -> bytes:
    name = _private_filename(filename)
    root_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
                raise HandoffStorageError("encrypted object must be an owned regular file")
            if metadata.st_size > max_bytes:
                raise HandoffStorageBoundsError("encrypted object exceeds its byte bound")
            chunks: list[bytes] = []
            remaining = metadata.st_size
            while remaining:
                chunk = os.read(descriptor, min(remaining, 1_048_576))
                if not chunk:
                    raise HandoffStorageIntegrityError("encrypted object was truncated")
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except FileNotFoundError as exc:
        raise HandoffStorageError("encrypted export objects are missing") from exc
    finally:
        os.close(root_fd)


def _write_private_file(directory: Path, filename: str, payload: bytes) -> None:
    name = _private_filename(filename)
    data = _require_bytes(payload, "payload")
    root_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=root_fd,
            )
        except FileExistsError:
            existing = _read_private_file(directory, name, max_bytes=len(data) + 1)
            if existing != data:
                raise HandoffStorageIdentityError(f"identity collision at {name}")
            return
        try:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise HandoffStorageError("encrypted object write made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        os.close(root_fd)


@dataclass(frozen=True, slots=True)
class PublicExportReceipt:
    """Flat compatibility projection of the canonical public receipt."""

    ciphertext_cid: str
    digest_sha256: str
    byte_count: int
    key_envelope_cid: str
    normalized_stream_id: str
    event_content_ids: tuple[str, ...]
    encryption_algorithm: str = ENCRYPTION_ALGORITHM
    disclosure_class: str = DISCLOSURE_PUBLIC_PROJECTION
    media_type: str = "application/octet-stream"

    def to_dict(self) -> Mapping[str, Any]:
        payload = {
            "schema": PUBLIC_EXPORT_RECEIPT_SCHEMA,
            "contract_version": HANDOFF_STORAGE_CONTRACT_VERSION,
            "ciphertext_cid": self.ciphertext_cid,
            "digest_sha256": self.digest_sha256,
            "byte_count": self.byte_count,
            "key_envelope_cid": self.key_envelope_cid,
            "normalized_stream_id": self.normalized_stream_id,
            "event_content_ids": list(self.event_content_ids),
            "encryption_algorithm": self.encryption_algorithm,
            "disclosure_class": self.disclosure_class,
            "media_type": self.media_type,
        }
        _reject_forbidden_keys(payload, name="public export receipt")
        return MappingProxyType(payload)


def public_receipt_from_reference(
    reference: Mapping[str, Any],
    *,
    event_content_ids: Sequence[str],
) -> PublicExportReceipt:
    """Build the flat compatibility receipt from the canonical reference."""

    _reject_forbidden_keys(reference, name="encrypted export reference")
    export_ref = EncryptedExportReference.from_dict(reference)
    ids = _event_content_ids(event_content_ids)
    if not ids:
        raise HandoffStorageError("normalized projection requires at least one event")
    return PublicExportReceipt(
        ciphertext_cid=export_ref.ciphertext_cid,
        digest_sha256=export_ref.digest_sha256,
        byte_count=export_ref.byte_count,
        key_envelope_cid=export_ref.key_envelope_cid,
        normalized_stream_id=normalized_stream_identity(ids),
        event_content_ids=ids,
        encryption_algorithm=export_ref.encryption_algorithm,
        media_type=export_ref.media_type,
    )


class EncryptedExportStore:
    """Directory-backed compatibility adapter over :class:`EncryptedHandoffStore`.

    It preserves the established filesystem API without preserving the old
    deterministic encryption.  Files are content-addressed, owner-only,
    opened without following symlinks, and never contain plaintext.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = _private_directory(Path(root))
        self.ciphertext_dir = _private_directory(self.root / "ciphertext")
        self.envelope_dir = _private_directory(self.root / "envelopes")
        self.projection_dir = _private_directory(self.root / "projections")

    def store_raw_export(
        self,
        plaintext: bytes,
        *,
        master_key: bytes,
        media_type: str = "application/octet-stream",
        retention_class: str = RETENTION_SESSION,
    ) -> Mapping[str, Any]:
        data = _require_bytes(plaintext, "raw export")
        if not data:
            raise HandoffStorageError("raw export must be nonempty")
        if len(data) > COMPAT_MAX_EXPORT_BYTES:
            raise HandoffStorageBoundsError("raw export exceeds the admitted byte bound")
        store = EncryptedHandoffStore(
            master_key,
            max_export_bytes=COMPAT_MAX_EXPORT_BYTES,
        )
        reference = store.store_exported_bytes(
            data,
            media_type=media_type,
            retention_class=retention_class,
        )
        blobs = store.stored_blobs()
        _write_private_file(
            self.ciphertext_dir,
            reference.ciphertext_cid[7:],
            blobs[reference.ciphertext_cid],
        )
        _write_private_file(
            self.envelope_dir,
            reference.key_envelope_cid[7:],
            blobs[reference.key_envelope_cid],
        )
        return MappingProxyType(reference.to_dict())

    def load_raw_export(
        self,
        reference: Mapping[str, Any],
        *,
        master_key: bytes,
    ) -> bytes:
        export_ref = EncryptedExportReference.from_dict(reference)
        ciphertext = _read_private_file(
            self.ciphertext_dir,
            export_ref.ciphertext_cid[7:],
            max_bytes=COMPAT_MAX_EXPORT_BYTES + GCM_NONCE_BYTES + GCM_TAG_BYTES,
        )
        envelope = _read_private_file(
            self.envelope_dir,
            export_ref.key_envelope_cid[7:],
            max_bytes=16_384,
        )
        blobs = MemoryBlobStore()
        blobs.put(export_ref.ciphertext_cid, ciphertext)
        blobs.put(export_ref.key_envelope_cid, envelope)
        try:
            return EncryptedHandoffStore(
                master_key,
                blobs=blobs,
                max_export_bytes=COMPAT_MAX_EXPORT_BYTES,
            ).retrieve_exported_bytes(export_ref)
        except HandoffStorageIntegrityError as exc:
            raise HandoffStorageError("decryption failed") from exc

    def emit_normalized_projection(
        self,
        event_content_ids: Sequence[str],
    ) -> NormalizedProjection:
        ids = _event_content_ids(event_content_ids)
        if not ids:
            raise HandoffStorageError("normalized projection requires at least one event")
        projection = NormalizedProjection(event_content_ids=ids)
        encoded = projection.canonical_bytes()
        _write_private_file(
            self.projection_dir,
            projection.normalized_stream_id[7:],
            encoded,
        )
        return projection

    def public_receipt(
        self,
        reference: Mapping[str, Any],
        *,
        event_content_ids: Sequence[str],
    ) -> PublicExportReceipt:
        return public_receipt_from_reference(
            reference,
            event_content_ids=event_content_ids,
        )


__all__ = (
    "ABSOLUTE_MAX_EVENTS",
    "ABSOLUTE_MAX_EXPORT_BYTES",
    "CONTRACT_VERSION",
    "DEFAULT_MAX_EVENTS",
    "DEFAULT_MAX_EXPORT_BYTES",
    "DISCLOSURE_ENCRYPTED_RAW",
    "DISCLOSURE_PUBLIC_PROJECTION",
    "ENCRYPTED_EXPORT_REFERENCE_INTERFACE",
    "ENCRYPTED_EXPORT_REFERENCE_SCHEMA",
    "ENCRYPTION_ALGORITHM",
    "HANDOFF_STORAGE_CONTRACT_VERSION",
    "KEY_ENVELOPE_INTERFACE",
    "KEY_ENVELOPE_SCHEMA",
    "NORMALIZED_PROJECTION_INTERFACE",
    "NORMALIZED_PROJECTION_SCHEMA",
    "NORMALIZED_STREAM_SCHEMA",
    "PUBLIC_RECEIPT_INTERFACE",
    "PUBLIC_RECEIPT_SCHEMA",
    "RETENTION_SESSION",
    "BlobStore",
    "EncryptedExportReference",
    "EncryptedExportStore",
    "EncryptedHandoffStore",
    "HandoffPreservation",
    "HandoffStorageBoundsError",
    "HandoffStorageDisclosureError",
    "HandoffStorageError",
    "HandoffStorageIdentityError",
    "HandoffStorageIntegrityError",
    "MemoryBlobStore",
    "NormalizedProjection",
    "PublicExportReceipt",
    "PublicHandoffReceipt",
    "aes_256_encrypt_block",
    "aes_256_gcm_decrypt",
    "aes_256_gcm_encrypt",
    "canonical_storage_json_bytes",
    "content_cid",
    "content_identity",
    "digest_sha256",
    "normalized_stream_identity",
    "public_receipt_from_reference",
    "sha256_identity",
)

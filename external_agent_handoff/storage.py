"""Encrypted raw-export storage and public normalized projections (EAAEF-011).

Exact exported bytes are stored only as AES-256-GCM ciphertext.  The data
encryption key lives in a separate envelope identity.  Public receipts and
normalized projections carry content-addressed references — never transcript
bodies, raw bytes, or hidden chain-of-thought.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ENCRYPTION_ALGORITHM: Final[str] = "aes-256-gcm"
ENCRYPTED_EXPORT_REFERENCE_INTERFACE: Final[str] = "EncryptedExportReference@1"
ENCRYPTED_EXPORT_REFERENCE_SCHEMA: Final[str] = (
    "ipfs_accelerate_py/agent-supervisor/encrypted-export-reference@1"
)
NORMALIZED_STREAM_SCHEMA: Final[str] = (
    "ipfs_accelerate_py/agent-supervisor/handoff-normalized-stream@1"
)
PUBLIC_EXPORT_RECEIPT_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-handoff/public-export-receipt@1"
)
NORMALIZED_PROJECTION_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-handoff/normalized-projection@1"
)
CONTRACT_VERSION: Final[int] = 1
DISCLOSURE_ENCRYPTED_RAW: Final[str] = "encrypted_raw"
DISCLOSURE_PUBLIC_PROJECTION: Final[str] = "public_projection"
RETENTION_SESSION: Final[str] = "session"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_TRANSCRIPT_BODY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "body",
        "chain_of_thought",
        "content",
        "full_transcript",
        "hidden_chain_of_thought",
        "message",
        "raw_bytes",
        "raw_export",
        "raw_transcript",
        "reasoning",
        "text",
        "thinking",
        "transcript",
        "transcript_body",
        "transcript_text",
    }
)
_PRIVATE_FIELD_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "credential",
        "dek",
        "key",
        "password",
        "plaintext",
        "private_key",
        "raw_bytes",
        "secret",
        "session_token",
        "transcript_body",
        "unwrapped_key",
    }
)
_MAX_EXPORT_BYTES: Final[int] = 1_048_576
_NONCE_BYTES: Final[int] = 12
_KEY_BYTES: Final[int] = 32


class HandoffStorageError(ValueError):
    """Malformed, oversized, or privacy-violating handoff storage request."""


def _canonical_json_bytes(payload: Mapping[str, Any] | Sequence[Any] | str | int | bool | None) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_cid(payload: bytes | Mapping[str, Any]) -> str:
    """Return a content identity for stored bytes or a canonical mapping.

    Raw ciphertext and key envelopes use ``sha256:<hex>``.  Ordered
    projections use the same CIDv1 dag-json/sha2-256 encoding as the
    transport-neutral handoff contracts.
    """

    if isinstance(payload, Mapping):
        digest = hashlib.sha256(_canonical_json_bytes(payload)).digest()
        raw = b"\x01\xa9\x02\x12\x20" + digest
        return "b" + base64.b32encode(raw).decode("ascii").rstrip("=").lower()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def digest_sha256(payload: bytes, *, prefixed: bool = False) -> str:
    """Return the SHA-256 digest of exact bytes, optionally ``sha256:`` prefixed."""

    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


_CIDV1_RE = re.compile(r"^b[a-z2-7]{50,90}$")


def _require_cid(value: object, name: str) -> str:
    text = str(value or "").strip()
    if _SHA256_RE.fullmatch(text) or _CIDV1_RE.fullmatch(text):
        return text
    raise HandoffStorageError(f"{name} must be a sha256 or CIDv1 identity")


def _require_digest(value: object, name: str) -> str:
    text = str(value or "").strip().lower()
    if _DIGEST_RE.fullmatch(text):
        return f"sha256:{text}"
    if text.startswith("sha256:") and _DIGEST_RE.fullmatch(text[7:]):
        return text
    raise HandoffStorageError(f"{name} must be a sha256 hex digest")


def _reject_forbidden(payload: Mapping[str, Any], *, name: str) -> None:
    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            for key, value in current.items():
                normalized = str(key).strip().lower().replace("-", "_")
                if normalized in _TRANSCRIPT_BODY_KEYS:
                    raise HandoffStorageError(
                        f"{name} must not embed transcript bodies; "
                        "use content-addressed references"
                    )
                if normalized in _PRIVATE_FIELD_MARKERS:
                    raise HandoffStorageError(
                        f"{name} must not embed private material ({key})"
                    )
                stack.append(value)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing != data:
            raise HandoffStorageError(f"identity collision at {path.name}")
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, 0o600)
    tmp.replace(path)


@dataclass(frozen=True)
class PublicExportReceipt:
    """Public pointer to encrypted raw bytes plus a normalized stream identity."""

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
            "contract_version": CONTRACT_VERSION,
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
        _reject_forbidden(payload, name="public export receipt")
        return MappingProxyType(payload)


@dataclass(frozen=True)
class NormalizedProjection:
    """Ordered event identities without transcript bodies."""

    stream_id: str
    event_content_ids: tuple[str, ...]

    def to_dict(self) -> Mapping[str, Any]:
        payload = {
            "schema": NORMALIZED_PROJECTION_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "stream_id": self.stream_id,
            "event_content_ids": list(self.event_content_ids),
            "disclosure_class": DISCLOSURE_PUBLIC_PROJECTION,
        }
        _reject_forbidden(payload, name="normalized projection")
        return MappingProxyType(payload)


def public_receipt_from_reference(
    reference: Mapping[str, Any],
    *,
    event_content_ids: Sequence[str],
) -> PublicExportReceipt:
    """Build a public receipt from an encrypted-export reference and event ids."""

    _reject_forbidden(reference, name="encrypted export reference")
    event_ids = tuple(_require_cid(item, "event_content_id") for item in event_content_ids)
    stream_id = content_cid(
        {
            "schema": NORMALIZED_STREAM_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "event_content_ids": list(event_ids),
        }
    )
    ciphertext_cid = _require_cid(reference.get("ciphertext_cid"), "ciphertext_cid")
    envelope_cid = _require_cid(reference.get("key_envelope_cid"), "key_envelope_cid")
    digest = _require_digest(reference.get("digest_sha256"), "digest_sha256")
    if ciphertext_cid == envelope_cid:
        raise HandoffStorageError("ciphertext and key envelope identities must be distinct")
    digest_hex = digest[7:] if digest.startswith("sha256:") else digest
    if ciphertext_cid.endswith(digest_hex) or ciphertext_cid[7:] == digest_hex:
        raise HandoffStorageError("ciphertext identity must not equal the plaintext digest")
    byte_count = int(reference.get("byte_count") or 0)
    if byte_count < 0:
        raise HandoffStorageError("byte_count must be nonnegative")
    return PublicExportReceipt(
        ciphertext_cid=ciphertext_cid,
        digest_sha256=digest,
        byte_count=byte_count,
        key_envelope_cid=envelope_cid,
        normalized_stream_id=stream_id,
        event_content_ids=event_ids,
        encryption_algorithm=str(
            reference.get("encryption_algorithm") or ENCRYPTION_ALGORITHM
        ),
        media_type=str(reference.get("media_type") or "application/octet-stream"),
    )


class EncryptedExportStore:
    """Directory-backed store for ciphertext, key envelopes, and projections."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.ciphertext_dir = self.root / "ciphertext"
        self.envelope_dir = self.root / "envelopes"
        self.projection_dir = self.root / "projections"
        self.ciphertext_dir.mkdir(parents=True, exist_ok=True)
        self.envelope_dir.mkdir(parents=True, exist_ok=True)
        self.projection_dir.mkdir(parents=True, exist_ok=True)

    def store_raw_export(
        self,
        plaintext: bytes,
        *,
        master_key: bytes,
        media_type: str = "application/octet-stream",
        retention_class: str = RETENTION_SESSION,
    ) -> Mapping[str, Any]:
        """Encrypt exact exported bytes and persist ciphertext plus key envelope."""

        if not isinstance(plaintext, (bytes, bytearray)):
            raise HandoffStorageError("raw export must be exact bytes")
        data = bytes(plaintext)
        if not data:
            raise HandoffStorageError("raw export must be nonempty")
        if len(data) > _MAX_EXPORT_BYTES:
            raise HandoffStorageError("raw export exceeds the admitted byte bound")
        if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != _KEY_BYTES:
            raise HandoffStorageError("master key must be 32 bytes")
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = nonce + AESGCM(dek).encrypt(nonce, data, None)
        wrap_nonce = os.urandom(_NONCE_BYTES)
        wrapped = wrap_nonce + AESGCM(bytes(master_key)).encrypt(wrap_nonce, dek, None)
        ciphertext_cid = content_cid(ciphertext)
        envelope_cid = content_cid(wrapped)
        plaintext_digest = digest_sha256(data, prefixed=True)
        if ciphertext_cid[7:] == plaintext_digest[7:]:
            raise HandoffStorageError("ciphertext identity collided with plaintext digest")
        if ciphertext_cid == envelope_cid:
            raise HandoffStorageError("ciphertext and key envelope identities must be distinct")
        _write_exclusive(self.ciphertext_dir / ciphertext_cid[7:], ciphertext)
        _write_exclusive(self.envelope_dir / envelope_cid[7:], wrapped)
        reference = {
            "schema": ENCRYPTED_EXPORT_REFERENCE_SCHEMA,
            "interface": ENCRYPTED_EXPORT_REFERENCE_INTERFACE,
            "contract_version": CONTRACT_VERSION,
            "ciphertext_cid": ciphertext_cid,
            "digest_sha256": plaintext_digest,
            "byte_count": len(data),
            "media_type": str(media_type or "application/octet-stream"),
            "key_envelope_cid": envelope_cid,
            "encryption_algorithm": ENCRYPTION_ALGORITHM,
            "disclosure_class": DISCLOSURE_ENCRYPTED_RAW,
            "retention_class": str(retention_class or RETENTION_SESSION),
        }
        _reject_forbidden(reference, name="encrypted export reference")
        return MappingProxyType(reference)

    def load_raw_export(
        self,
        reference: Mapping[str, Any],
        *,
        master_key: bytes,
    ) -> bytes:
        """Decrypt exact exported bytes.  Never used for public receipts."""

        _reject_forbidden(reference, name="encrypted export reference")
        if str(reference.get("disclosure_class") or "") != DISCLOSURE_ENCRYPTED_RAW:
            raise HandoffStorageError("raw load requires encrypted_raw disclosure")
        ciphertext_cid = _require_cid(reference.get("ciphertext_cid"), "ciphertext_cid")
        envelope_cid = _require_cid(reference.get("key_envelope_cid"), "key_envelope_cid")
        expected_digest = _require_digest(reference.get("digest_sha256"), "digest_sha256")
        ciphertext_path = self.ciphertext_dir / ciphertext_cid[7:]
        envelope_path = self.envelope_dir / envelope_cid[7:]
        if not ciphertext_path.is_file() or not envelope_path.is_file():
            raise HandoffStorageError("encrypted export objects are missing")
        ciphertext = ciphertext_path.read_bytes()
        wrapped = envelope_path.read_bytes()
        if content_cid(ciphertext) != ciphertext_cid:
            raise HandoffStorageError("ciphertext identity mismatch")
        if content_cid(wrapped) != envelope_cid:
            raise HandoffStorageError("key envelope identity mismatch")
        if len(ciphertext) <= _NONCE_BYTES or len(wrapped) <= _NONCE_BYTES:
            raise HandoffStorageError("encrypted object is truncated")
        if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != _KEY_BYTES:
            raise HandoffStorageError("master key must be 32 bytes")
        try:
            dek = AESGCM(bytes(master_key)).decrypt(
                wrapped[:_NONCE_BYTES], wrapped[_NONCE_BYTES:], None
            )
            plaintext = AESGCM(dek).decrypt(
                ciphertext[:_NONCE_BYTES], ciphertext[_NONCE_BYTES:], None
            )
        except Exception as exc:  # noqa: BLE001
            raise HandoffStorageError("decryption failed") from exc
        if digest_sha256(plaintext, prefixed=True) != expected_digest:
            raise HandoffStorageError("plaintext digest mismatch")
        expected_count = int(reference.get("byte_count") or -1)
        if expected_count != len(plaintext):
            raise HandoffStorageError("plaintext byte_count mismatch")
        return plaintext

    def emit_normalized_projection(
        self,
        event_content_ids: Sequence[str],
    ) -> NormalizedProjection:
        """Persist an ordered public projection of event identities only."""

        event_ids = tuple(_require_cid(item, "event_content_id") for item in event_content_ids)
        if not event_ids:
            raise HandoffStorageError("normalized projection requires at least one event")
        stream_id = content_cid(
            {
                "schema": NORMALIZED_STREAM_SCHEMA,
                "contract_version": CONTRACT_VERSION,
                "event_content_ids": list(event_ids),
            }
        )
        projection = NormalizedProjection(stream_id=stream_id, event_content_ids=event_ids)
        encoded = _canonical_bytes(dict(projection.to_dict()))
        _write_exclusive(self.projection_dir / stream_id[7:], encoded)
        return projection

    def public_receipt(
        self,
        reference: Mapping[str, Any],
        *,
        event_content_ids: Sequence[str],
    ) -> PublicExportReceipt:
        """Public receipt: encrypted-export refs + ordered stream identity."""

        receipt = public_receipt_from_reference(
            reference, event_content_ids=event_content_ids
        )
        _reject_forbidden(dict(receipt.to_dict()), name="public export receipt")
        return receipt

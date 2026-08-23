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
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Final, Protocol

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
AES_KEY_BYTES: Final[int] = 32
GCM_NONCE_BYTES: Final[int] = 12
GCM_TAG_BYTES: Final[int] = 16
AES_BLOCK_BYTES: Final[int] = 16

_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
_CIDV1_RE: Final[re.Pattern[str]] = re.compile(r"^b[a-z2-7]{20,}$")
_HEX64_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

_DATA_KEY_INFO: Final[bytes] = b"eaaef-011.data-key.v1"
_ENC_NONCE_INFO: Final[bytes] = b"eaaef-011.enc-nonce.v1"
_WRAP_NONCE_INFO: Final[bytes] = b"eaaef-011.wrap-nonce.v1"
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


def digest_sha256(data: bytes) -> str:
    """Return the plaintext digest identity ``sha256:<hex>``."""

    return sha256_identity(data)


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


# ---------------------------------------------------------------------------
# AES-256-GCM (stdlib-only; encrypt-only block cipher)
# ---------------------------------------------------------------------------

_SBOX: Final[bytes] = bytes(
    [
        0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
        0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
        0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
        0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
        0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
        0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
        0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
        0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
        0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
        0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
        0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
        0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
        0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
        0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
        0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
        0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
    ]
)
_RCON: Final[tuple[int, ...]] = (
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D
)
_GF_R: Final[int] = 0xE1000000000000000000000000000000


def _xtime(value: int) -> int:
    value <<= 1
    if value & 0x100:
        value ^= 0x11B
    return value & 0xFF


def _mix_column(a: int, b: int, c: int, d: int) -> tuple[int, int, int, int]:
    return (
        _xtime(a) ^ _xtime(b) ^ b ^ c ^ d,
        a ^ _xtime(b) ^ _xtime(c) ^ c ^ d,
        a ^ b ^ _xtime(c) ^ _xtime(d) ^ d,
        _xtime(a) ^ a ^ b ^ c ^ _xtime(d),
    )


def _sub_word(word: int) -> int:
    return (
        (_SBOX[(word >> 24) & 0xFF] << 24)
        | (_SBOX[(word >> 16) & 0xFF] << 16)
        | (_SBOX[(word >> 8) & 0xFF] << 8)
        | _SBOX[word & 0xFF]
    )


def _rot_word(word: int) -> int:
    return ((word << 8) & 0xFFFFFFFF) | (word >> 24)


def _expand_aes256_key(key: bytes) -> list[bytes]:
    if len(key) != AES_KEY_BYTES:
        raise HandoffStorageError("AES-256 key must be 32 bytes")
    words = [int.from_bytes(key[index : index + 4], "big") for index in range(0, 32, 4)]
    for index in range(8, 60):
        temp = words[index - 1]
        if index % 8 == 0:
            temp = _sub_word(_rot_word(temp)) ^ (_RCON[index // 8] << 24)
        elif index % 8 == 4:
            temp = _sub_word(temp)
        words.append(words[index - 8] ^ temp)
    rounds: list[bytes] = []
    for round_index in range(15):
        block = b"".join(
            words[round_index * 4 + offset].to_bytes(4, "big") for offset in range(4)
        )
        rounds.append(block)
    return rounds


def aes_256_encrypt_block(key: bytes, block: bytes) -> bytes:
    """Encrypt one 16-byte block with AES-256."""

    if len(block) != AES_BLOCK_BYTES:
        raise HandoffStorageError("AES block must be 16 bytes")
    round_keys = _expand_aes256_key(key)
    state = bytearray(block[index] ^ round_keys[0][index] for index in range(16))
    for round_index in range(1, 14):
        state = bytearray(_SBOX[value] for value in state)
        state = bytearray(
            [
                state[0], state[5], state[10], state[15],
                state[4], state[9], state[14], state[3],
                state[8], state[13], state[2], state[7],
                state[12], state[1], state[6], state[11],
            ]
        )
        mixed = bytearray(16)
        for column in range(4):
            values = _mix_column(
                state[column * 4],
                state[column * 4 + 1],
                state[column * 4 + 2],
                state[column * 4 + 3],
            )
            mixed[column * 4 : column * 4 + 4] = values
        state = bytearray(
            mixed[index] ^ round_keys[round_index][index] for index in range(16)
        )
    state = bytearray(_SBOX[value] for value in state)
    state = bytearray(
        [
            state[0], state[5], state[10], state[15],
            state[4], state[9], state[14], state[3],
            state[8], state[13], state[2], state[7],
            state[12], state[1], state[6], state[11],
        ]
    )
    return bytes(state[index] ^ round_keys[14][index] for index in range(16))


def _inc32(block: bytes) -> bytes:
    counter = int.from_bytes(block[12:], "big")
    return block[:12] + ((counter + 1) & 0xFFFFFFFF).to_bytes(4, "big")


def _gf_mul(x: int, y: int) -> int:
    z = 0
    v = y
    for bit in range(128):
        if (x >> (127 - bit)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ _GF_R
        else:
            v >>= 1
    return z & ((1 << 128) - 1)


def _ghash(hash_subkey: bytes, aad: bytes, ciphertext: bytes) -> bytes:
    y = 0
    h = int.from_bytes(hash_subkey, "big")

    def update(data: bytes) -> None:
        nonlocal y
        for offset in range(0, len(data), 16):
            block = data[offset : offset + 16]
            if len(block) < 16:
                block = block + b"\x00" * (16 - len(block))
            y = _gf_mul(y ^ int.from_bytes(block, "big"), h)

    update(aad)
    update(ciphertext)
    length_block = (len(aad) * 8).to_bytes(8, "big") + (len(ciphertext) * 8).to_bytes(8, "big")
    y = _gf_mul(y ^ int.from_bytes(length_block, "big"), h)
    return y.to_bytes(16, "big")


def _gctr(key: bytes, icb: bytes, data: bytes) -> bytes:
    if not data:
        return b""
    counter = icb
    output = bytearray()
    for offset in range(0, len(data), 16):
        keystream = aes_256_encrypt_block(key, counter)
        block = data[offset : offset + 16]
        output.extend(byte ^ keystream[index] for index, byte in enumerate(block))
        counter = _inc32(counter)
    return bytes(output)


def aes_256_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Return ``nonce || ciphertext || tag`` for AES-256-GCM."""

    key = _require_bytes(key, "key")
    nonce = _require_bytes(nonce, "nonce")
    plaintext = _require_bytes(plaintext, "plaintext")
    aad = _require_bytes(aad, "aad")
    if len(key) != AES_KEY_BYTES:
        raise HandoffStorageError("AES-256-GCM key must be 32 bytes")
    if len(nonce) != GCM_NONCE_BYTES:
        raise HandoffStorageError("AES-256-GCM nonce must be 12 bytes")
    hash_subkey = aes_256_encrypt_block(key, b"\x00" * 16)
    j0 = nonce + b"\x00\x00\x00\x01"
    ciphertext = _gctr(key, _inc32(j0), plaintext)
    s = _ghash(hash_subkey, aad, ciphertext)
    tag = _gctr(key, j0, s)
    return nonce + ciphertext + tag


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
    tag = blob[-GCM_TAG_BYTES:]
    ciphertext = blob[GCM_NONCE_BYTES:-GCM_TAG_BYTES]
    hash_subkey = aes_256_encrypt_block(key, b"\x00" * 16)
    j0 = nonce + b"\x00\x00\x00\x01"
    s = _ghash(hash_subkey, aad, ciphertext)
    expected = _gctr(key, j0, s)
    if not hmac.compare_digest(tag, expected):
        raise HandoffStorageIntegrityError("ciphertext authentication failed")
    return _gctr(key, _inc32(j0), ciphertext)


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
    def from_dict(cls, payload: Mapping[str, Any]) -> "EncryptedExportReference":
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

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NormalizedProjection":
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
    def from_dict(cls, payload: Mapping[str, Any]) -> "PublicHandoffReceipt":
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
    identities.  The wrapping key never appears in public receipts.  Put paths
    are deterministic for a given master key and plaintext.
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
        data_key = _hkdf_like(self._master_key, _DATA_KEY_INFO + digest_raw, AES_KEY_BYTES)
        enc_nonce = _hkdf_like(self._master_key, _ENC_NONCE_INFO + digest_raw, GCM_NONCE_BYTES)
        wrap_nonce = _hkdf_like(
            self._master_key, _WRAP_NONCE_INFO + digest_raw, GCM_NONCE_BYTES
        )
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
        if envelope.get("key_id") != self._key_id:
            raise HandoffStorageIntegrityError("key envelope is bound to a different wrapping key")
        try:
            wrapped_key = bytes.fromhex(str(envelope.get("wrapped_key", "")))
        except ValueError as exc:
            raise HandoffStorageIntegrityError("key envelope wrapped_key is malformed") from exc
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
    "EncryptedHandoffStore",
    "HandoffPreservation",
    "HandoffStorageBoundsError",
    "HandoffStorageDisclosureError",
    "HandoffStorageError",
    "HandoffStorageIdentityError",
    "HandoffStorageIntegrityError",
    "MemoryBlobStore",
    "NormalizedProjection",
    "PublicHandoffReceipt",
    "aes_256_encrypt_block",
    "aes_256_gcm_decrypt",
    "aes_256_gcm_encrypt",
    "canonical_storage_json_bytes",
    "content_identity",
    "digest_sha256",
    "normalized_stream_identity",
    "sha256_identity",
)

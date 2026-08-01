"""Content and version verification used by replica reconciliation (KITA-027).

The verifier is deliberately independent of a storage client.  Storage
adapters provide a :class:`ReplicaContent` value after a read; only a
successful verification result may be promoted to a durable verified replica
by the reconciler.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Final


INTEGRITY_VERIFIER_SCHEMA: Final[str] = "ipfs_kit_py/core/replication/integrity-verifier@1"
IntegrityVerifier_V1: Final[str] = INTEGRITY_VERIFIER_SCHEMA
MAX_CONTENT_BYTES: Final[int] = 1 << 30
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


class IntegrityError(ValueError):
    """A replica payload or its verification expectation is invalid."""


def _bytes(value: bytes | bytearray | memoryview, field: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise IntegrityError(f"{field} must be bytes")
    result = bytes(value)
    if len(result) > MAX_CONTENT_BYTES:
        raise IntegrityError(f"{field} exceeds the supported verification bound")
    return result


def _version(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 512:
        raise IntegrityError("version_id must be a compact non-empty string")
    return value.strip()


def normalize_digest(value: str) -> str:
    """Return a canonical ``sha256:`` digest or reject ambiguous values."""

    if not isinstance(value, str):
        raise IntegrityError("digest must be a sha256 string")
    result = value.strip().lower()
    if not _SHA256_RE.fullmatch(result):
        raise IntegrityError("digest must be a sha256 digest")
    return "sha256:" + result.removeprefix("sha256:")


@dataclass(frozen=True)
class ReplicaContent:
    """Bytes and version metadata returned by a replica backend.

    ``digest`` is optional provider metadata.  When it is present, it is
    checked against the bytes as well as the requested digest; a provider
    cannot make corrupted content pass by reporting an expected digest.
    """

    payload: bytes
    version_id: str
    digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _bytes(self.payload, "payload"))
        object.__setattr__(self, "version_id", _version(self.version_id))
        if self.digest is not None:
            object.__setattr__(self, "digest", normalize_digest(self.digest))


@dataclass(frozen=True)
class IntegrityResult:
    """Non-throwing verification evidence suitable for a reconciliation receipt."""

    valid: bool
    actual_digest: str
    actual_version_id: str
    reason: str | None = None


class IntegrityVerifier:
    """Verify exact SHA-256 content and exact replica version identity."""

    interface_version: Final[str] = INTEGRITY_VERIFIER_SCHEMA

    def digest(self, payload: bytes | bytearray | memoryview) -> str:
        return "sha256:" + hashlib.sha256(_bytes(payload, "payload")).hexdigest()

    def verify(
        self,
        content: ReplicaContent,
        *,
        expected_digest: str,
        expected_version_id: str,
    ) -> IntegrityResult:
        """Verify bytes, declared digest (if any), and version without IO.

        Callers receive a structured false result for content/version mismatch;
        malformed caller input remains an exception because it cannot be made
        safe by retrying a backend operation.
        """

        if not isinstance(content, ReplicaContent):
            raise IntegrityError("content must be ReplicaContent")
        expected_digest = normalize_digest(expected_digest)
        expected_version_id = _version(expected_version_id)
        actual_digest = self.digest(content.payload)
        if content.digest is not None and not hmac.compare_digest(content.digest, actual_digest):
            return IntegrityResult(False, actual_digest, content.version_id, "declared_digest_mismatch")
        if not hmac.compare_digest(actual_digest, expected_digest):
            return IntegrityResult(False, actual_digest, content.version_id, "content_digest_mismatch")
        if not hmac.compare_digest(content.version_id, expected_version_id):
            return IntegrityResult(False, actual_digest, content.version_id, "version_mismatch")
        return IntegrityResult(True, actual_digest, content.version_id)


__all__ = [
    "INTEGRITY_VERIFIER_SCHEMA",
    "IntegrityError",
    "IntegrityResult",
    "IntegrityVerifier",
    "IntegrityVerifier_V1",
    "MAX_CONTENT_BYTES",
    "ReplicaContent",
    "normalize_digest",
]

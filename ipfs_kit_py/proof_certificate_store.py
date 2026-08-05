"""Strict optional transport for proof-backed test certificates.

The transport is deliberately smaller than the authoritative certificate
store in ``ipfs_accelerate_py``.  It moves immutable bytes by CID, but never
decides whether those bytes prove that a test may be reused.

Safety properties:

* CID text is decoded and its sha2-256 multihash is checked against the exact
  bytes.  The legacy ``ipfs_multiformats`` testing pseudo-CIDs are not used.
* Local storage is opt-in, bounded, atomically published, and rehashed after
  publication.
* IPFS is opt-in through an already-created client or explicit callables.
  This module never starts a daemon and never discovers or creates ``~/.ipfs``.
* Every IPFS exception, malformed response, oversized response, or hash
  mismatch is a typed miss.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import stat
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

TEST_CERTIFICATE_STORE_TRANSPORT_INTERFACE: Final = (
    "TestCertificateStoreTransport@1"
)
TEST_CERTIFICATE_STORE_TRANSPORT_SCHEMA: Final = (
    "ipfs_kit_py/test-certificate-store-transport@1"
)
TEST_CERTIFICATE_STORE_TRANSPORT_SCHEMA_VERSION: Final = (
    TEST_CERTIFICATE_STORE_TRANSPORT_INTERFACE
)

DEFAULT_MAX_CERTIFICATE_BYTES: Final = 1_048_576
DEFAULT_MAX_BLOB_BYTES: Final = DEFAULT_MAX_CERTIFICATE_BYTES

_CIDV1: Final = 1
_RAW_CODEC: Final = 0x55
_SHA2_256: Final = 0x12
_SHA2_256_SIZE: Final = 32
_BASE58_ALPHABET: Final = (
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)
_BASE58_INDEX: Final = {character: index for index, character in enumerate(_BASE58_ALPHABET)}
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class CertificateTransportStatus(str, Enum):
    STORED = "stored"
    HIT = "hit"
    MISS = "miss"
    REJECTED = "rejected"
    ERROR = "error"


class CertificateTransportReason(str, Enum):
    OK = "ok"
    ALREADY_EXISTS = "already_exists"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    OVER_BUDGET = "over_budget"
    CID_MISMATCH = "cid_mismatch"
    NOT_FOUND = "not_found"
    INTEGRITY_FAILED = "integrity_failed"
    SYMLINK_REJECTED = "symlink_rejected"
    PATH_ESCAPE = "path_escape"
    IO_ERROR = "io_error"
    IPFS_ERROR = "ipfs_error"
    IPFS_RESPONSE_INVALID = "ipfs_response_invalid"


class CertificateTransportError(ValueError):
    """A CID or transport configuration violates the closed contract."""


@dataclass(frozen=True)
class DecodedCertificateCID:
    """The security-relevant projection of a decoded CID."""

    text: str
    version: int
    codec: int
    multihash_code: int
    digest: bytes
    base: str

    def verifies(self, data: bytes) -> bool:
        return type(data) is bytes and hashlib.sha256(data).digest() == self.digest


@dataclass(frozen=True)
class CertificateTransportPutResult:
    stored: bool
    cid: str
    reason_code: CertificateTransportReason
    byte_length: int = 0
    local_stored: bool = False
    ipfs_stored: bool = False
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.stored


@dataclass(frozen=True)
class CertificateTransportGetResult:
    status: CertificateTransportStatus
    cid: str
    reason_code: CertificateTransportReason
    data: bytes | None = None
    byte_length: int = 0
    source: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.hit

    @property
    def hit(self) -> bool:
        return self.status is CertificateTransportStatus.HIT and self.data is not None


# Familiar aliases for callers already using the accelerator-side CAS names.
CasPutResult = CertificateTransportPutResult
CasGetResult = CertificateTransportGetResult


def _encode_varint(value: int) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CertificateTransportError("varint value must be a non-negative integer")
    encoded = bytearray()
    while value >= 0x80:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    start = offset
    for _ in range(10):
        if offset >= len(data):
            raise CertificateTransportError("CID contains a truncated varint")
        octet = data[offset]
        offset += 1
        value |= (octet & 0x7F) << shift
        if not octet & 0x80:
            if data[start:offset] != _encode_varint(value):
                raise CertificateTransportError("CID contains a non-canonical varint")
            return value, offset
        shift += 7
    raise CertificateTransportError("CID varint is too long")


def _base58_decode(text: str) -> bytes:
    if not text:
        raise CertificateTransportError("base58 payload must not be empty")
    value = 0
    try:
        for character in text:
            value = value * 58 + _BASE58_INDEX[character]
    except KeyError as exc:
        raise CertificateTransportError("CID contains invalid base58 text") from exc
    body = (
        value.to_bytes((value.bit_length() + 7) // 8, "big")
        if value
        else b""
    )
    return b"\x00" * (len(text) - len(text.lstrip("1"))) + body


def _base58_encode(data: bytes) -> str:
    leading = len(data) - len(data.lstrip(b"\x00"))
    value = int.from_bytes(data, "big")
    encoded = ""
    while value:
        value, remainder = divmod(value, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded
    return "1" * leading + encoded


def _base32_decode(text: str) -> bytes:
    if not text or text != text.lower():
        raise CertificateTransportError(
            "base32 CID must use nonempty canonical lowercase text"
        )
    if any(character not in "abcdefghijklmnopqrstuvwxyz234567" for character in text):
        raise CertificateTransportError("CID contains invalid base32 text")
    padding = "=" * ((8 - len(text) % 8) % 8)
    try:
        decoded = base64.b32decode((text.upper() + padding).encode("ascii"))
    except (binascii.Error, ValueError) as exc:
        raise CertificateTransportError("CID base32 payload is not decodable") from exc
    canonical = base64.b32encode(decoded).decode("ascii").lower().rstrip("=")
    if canonical != text:
        raise CertificateTransportError("CID is not canonical base32")
    return decoded


def decode_certificate_cid(value: str) -> DecodedCertificateCID:
    """Decode one canonical CID carrying a full sha2-256 multihash.

    Canonical lowercase base32 CIDv1 is the generated form.  Canonical
    base58btc CIDv1 and CIDv0 are accepted so externally supplied block CIDs
    can still be rehashed.  No prefix-only or synthetic CID is admitted.
    """

    if type(value) is not str or not value or value.strip() != value:
        raise CertificateTransportError("CID must be a nonempty canonical string")
    if len(value) > 256 or "/" in value or "\\" in value or "\x00" in value:
        raise CertificateTransportError("CID contains unsafe text")

    if value.startswith("b"):
        raw = _base32_decode(value[1:])
        base_name = "base32"
        version, offset = _decode_varint(raw, 0)
        if version != _CIDV1:
            raise CertificateTransportError("only CIDv1 is valid with multibase")
        codec, offset = _decode_varint(raw, offset)
    elif value.startswith("z"):
        raw = _base58_decode(value[1:])
        if "z" + _base58_encode(raw) != value:
            raise CertificateTransportError("CID is not canonical base58btc")
        base_name = "base58btc"
        version, offset = _decode_varint(raw, 0)
        if version != _CIDV1:
            raise CertificateTransportError("only CIDv1 is valid with multibase")
        codec, offset = _decode_varint(raw, offset)
    elif value.startswith("Qm"):
        raw = _base58_decode(value)
        if _base58_encode(raw) != value:
            raise CertificateTransportError("CIDv0 is not canonical base58btc")
        # CIDv0 is the bare dag-pb multihash.
        version, codec, offset, base_name = 0, 0x70, 0, "base58btc"
    else:
        raise CertificateTransportError(
            "CID must be canonical CIDv1 multibase or CIDv0 base58btc"
        )

    multihash_code, offset = _decode_varint(raw, offset)
    digest_size, offset = _decode_varint(raw, offset)
    digest = raw[offset:]
    if codec <= 0:
        raise CertificateTransportError("CID codec must be a positive multicodec")
    if multihash_code != _SHA2_256 or digest_size != _SHA2_256_SIZE:
        raise CertificateTransportError(
            "certificate CIDs require a full 32-byte sha2-256 multihash"
        )
    if len(digest) != digest_size:
        raise CertificateTransportError("CID multihash is truncated or has trailing data")
    return DecodedCertificateCID(
        value, version, codec, multihash_code, digest, base_name
    )


def cid_for_certificate_bytes(data: bytes, *, codec: int = _RAW_CODEC) -> str:
    """Return a canonical raw CIDv1 for exact bytes."""

    if type(data) is not bytes:
        raise CertificateTransportError("certificate payload must be exact bytes")
    if isinstance(codec, bool) or not isinstance(codec, int) or codec <= 0:
        raise CertificateTransportError("codec must be a positive multicodec integer")
    raw = (
        _encode_varint(_CIDV1)
        + _encode_varint(codec)
        + _encode_varint(_SHA2_256)
        + _encode_varint(_SHA2_256_SIZE)
        + hashlib.sha256(data).digest()
    )
    return "b" + base64.b32encode(raw).decode("ascii").lower().rstrip("=")


def verify_certificate_cid(cid: str, data: bytes) -> bool:
    """Return whether ``cid`` carries the sha2-256 digest of exact ``data``."""

    if type(data) is not bytes:
        return False
    try:
        return decode_certificate_cid(cid).verifies(data)
    except CertificateTransportError:
        return False


def _thread_lock(root: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(root))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def _extract_ipfs_cid(value: Any) -> str | None:
    if type(value) is str:
        return value
    if isinstance(value, Mapping):
        for key in ("cid", "CID", "Hash", "Key"):
            candidate = value.get(key)
            if type(candidate) is str:
                return candidate
            if isinstance(candidate, Mapping) and type(candidate.get("/")) is str:
                return candidate["/"]
    return None


def _extract_ipfs_bytes(value: Any, *, maximum: int) -> bytes | None:
    if type(value) is bytes:
        return value if len(value) <= maximum else None
    if isinstance(value, bytearray):
        return bytes(value) if len(value) <= maximum else None
    if isinstance(value, memoryview):
        return value.tobytes() if value.nbytes <= maximum else None
    if hasattr(value, "read"):
        try:
            data = value.read(maximum + 1)
        except BaseException:
            return None
        return data if type(data) is bytes and len(data) <= maximum else None
    return None


class IpfsKitProofCertificateStore:
    """Optional local/IPFS exact-byte transport.

    ``local_root`` and ``ipfs_client`` default to ``None``.  Consequently a
    default instance has no filesystem or network side effects.  An injected
    IPFS client is assumed to refer to an already-running service; this class
    only calls block get/put style methods and has no daemon-management path.
    """

    __test__ = False

    def __init__(
        self,
        local_root: str | os.PathLike[str] | None = None,
        *,
        ipfs_client: Any | None = None,
        ipfs_get: Callable[[str], Any] | None = None,
        ipfs_put: Callable[[bytes], Any] | None = None,
        max_blob_bytes: int = DEFAULT_MAX_BLOB_BYTES,
        cache_ipfs_reads: bool = True,
    ) -> None:
        if (
            isinstance(max_blob_bytes, bool)
            or not isinstance(max_blob_bytes, int)
            or max_blob_bytes <= 0
        ):
            raise ValueError("max_blob_bytes must be a positive integer")
        if ipfs_get is not None and not callable(ipfs_get):
            raise TypeError("ipfs_get must be callable")
        if ipfs_put is not None and not callable(ipfs_put):
            raise TypeError("ipfs_put must be callable")
        self.local_root = Path(local_root).absolute() if local_root is not None else None
        self.max_blob_bytes = max_blob_bytes
        self.cache_ipfs_reads = bool(cache_ipfs_reads)
        self._ipfs_get = ipfs_get or self._client_method(
            ipfs_client, ("block_get", "get_block", "cat")
        )
        self._ipfs_put = ipfs_put or self._client_method(
            ipfs_client, ("block_put", "put_block", "add_bytes")
        )

    @staticmethod
    def _client_method(client: Any | None, names: tuple[str, ...]) -> Callable[..., Any] | None:
        if client is None:
            return None
        for name in names:
            method = getattr(client, name, None)
            if callable(method):
                return method
        return None

    @property
    def local_enabled(self) -> bool:
        return self.local_root is not None

    @property
    def ipfs_read_enabled(self) -> bool:
        return self._ipfs_get is not None

    @property
    def ipfs_write_enabled(self) -> bool:
        return self._ipfs_put is not None

    def _blob_path(self, cid: str) -> Path:
        if self.local_root is None:
            raise CertificateTransportError("local transport is disabled")
        # Decoding makes the token path-safe; the digest shard is bounded.
        parsed = decode_certificate_cid(cid)
        shard = parsed.digest.hex()[:2]
        return self.local_root / "certificates" / shard / f"{cid}.blob"

    def _safe_local_path(self, cid: str, *, create_parent: bool) -> Path:
        if self.local_root is None:
            raise CertificateTransportError("local transport is disabled")
        root = self.local_root
        if root.is_symlink():
            raise CertificateTransportError(CertificateTransportReason.SYMLINK_REJECTED.value)
        path = self._blob_path(cid)
        if create_parent:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if root.is_symlink():
                raise CertificateTransportError(
                    CertificateTransportReason.SYMLINK_REJECTED.value
                )
        current = root
        for part in path.relative_to(root).parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise CertificateTransportError(
                    CertificateTransportReason.SYMLINK_REJECTED.value
                )
            if create_parent:
                current.mkdir(mode=0o700, exist_ok=True)
                # Check again after mkdir so a concurrently-created symlink is
                # rejected before any child path is created through it.
                if current.is_symlink():
                    raise CertificateTransportError(
                        CertificateTransportReason.SYMLINK_REJECTED.value
                    )
                if not current.is_dir():
                    raise CertificateTransportError(
                        CertificateTransportReason.PATH_ESCAPE.value
                    )
        if path.is_symlink():
            raise CertificateTransportError(
                CertificateTransportReason.SYMLINK_REJECTED.value
            )
        if path.parent.exists():
            try:
                path.parent.resolve(strict=True).relative_to(root.resolve(strict=True))
            except (OSError, ValueError) as exc:
                raise CertificateTransportError(
                    CertificateTransportReason.PATH_ESCAPE.value
                ) from exc
        return path

    def _read_local(self, cid: str) -> CertificateTransportGetResult:
        try:
            path = self._safe_local_path(cid, create_parent=False)
        except CertificateTransportError as exc:
            reason = (
                CertificateTransportReason.SYMLINK_REJECTED
                if str(exc) == CertificateTransportReason.SYMLINK_REJECTED.value
                else CertificateTransportReason.PATH_ESCAPE
            )
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS, cid, reason
            )
        if not path.exists():
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                cid,
                CertificateTransportReason.NOT_FOUND,
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    return CertificateTransportGetResult(
                        CertificateTransportStatus.MISS,
                        cid,
                        CertificateTransportReason.MALFORMED,
                    )
                if metadata.st_size > self.max_blob_bytes:
                    return CertificateTransportGetResult(
                        CertificateTransportStatus.MISS,
                        cid,
                        CertificateTransportReason.OVER_BUDGET,
                        byte_length=metadata.st_size,
                    )
                data = stream.read(self.max_blob_bytes + 1)
        except OSError:
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                cid,
                CertificateTransportReason.IO_ERROR,
            )
        if len(data) > self.max_blob_bytes:
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                cid,
                CertificateTransportReason.OVER_BUDGET,
                byte_length=len(data),
            )
        if not verify_certificate_cid(cid, data):
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                cid,
                CertificateTransportReason.INTEGRITY_FAILED,
                byte_length=len(data),
            )
        return CertificateTransportGetResult(
            CertificateTransportStatus.HIT,
            cid,
            CertificateTransportReason.OK,
            data,
            len(data),
            "local",
        )

    def _write_local(self, cid: str, data: bytes) -> CertificateTransportPutResult:
        assert self.local_root is not None
        try:
            path = self._safe_local_path(cid, create_parent=True)
        except (CertificateTransportError, OSError) as exc:
            reason = (
                CertificateTransportReason.SYMLINK_REJECTED
                if str(exc) == CertificateTransportReason.SYMLINK_REJECTED.value
                else CertificateTransportReason.PATH_ESCAPE
            )
            return CertificateTransportPutResult(False, cid, reason, len(data))

        with _thread_lock(self.local_root):
            if path.exists() or path.is_symlink():
                existing = self._read_local(cid)
                if existing.hit and existing.data == data:
                    return CertificateTransportPutResult(
                        True,
                        cid,
                        CertificateTransportReason.ALREADY_EXISTS,
                        len(data),
                        local_stored=True,
                    )
                return CertificateTransportPutResult(
                    False,
                    cid,
                    existing.reason_code,
                    len(data),
                )
            descriptor = -1
            temporary_name = ""
            try:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{cid}.", suffix=".tmp", dir=path.parent
                )
                with os.fdopen(descriptor, "wb") as stream:
                    descriptor = -1
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary_name, 0o600)
                os.replace(temporary_name, path)
                temporary_name = ""
                try:
                    directory = os.open(path.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                except OSError:
                    pass
            except OSError:
                if descriptor >= 0:
                    os.close(descriptor)
                if temporary_name:
                    try:
                        os.unlink(temporary_name)
                    except OSError:
                        pass
                return CertificateTransportPutResult(
                    False, cid, CertificateTransportReason.IO_ERROR, len(data)
                )
            readback = self._read_local(cid)
            if not readback.hit or readback.data != data:
                return CertificateTransportPutResult(
                    False,
                    cid,
                    CertificateTransportReason.INTEGRITY_FAILED,
                    len(data),
                )
            return CertificateTransportPutResult(
                True,
                cid,
                CertificateTransportReason.OK,
                len(data),
                local_stored=True,
            )

    def put_bytes(
        self,
        data: bytes,
        *,
        claimed_cid: str | None = None,
        cid: str | None = None,
    ) -> CertificateTransportPutResult:
        """Verify and publish exact bytes to the explicitly enabled backends."""

        if claimed_cid is not None and cid is not None and claimed_cid != cid:
            return CertificateTransportPutResult(
                False, claimed_cid, CertificateTransportReason.MALFORMED
            )
        claim = claimed_cid if claimed_cid is not None else cid
        if type(data) is not bytes:
            return CertificateTransportPutResult(
                False, claim or "", CertificateTransportReason.MALFORMED
            )
        if len(data) > self.max_blob_bytes:
            return CertificateTransportPutResult(
                False,
                claim or "",
                CertificateTransportReason.OVER_BUDGET,
                len(data),
            )
        target = claim or cid_for_certificate_bytes(data)
        try:
            parsed = decode_certificate_cid(target)
        except CertificateTransportError:
            return CertificateTransportPutResult(
                False, target, CertificateTransportReason.MALFORMED, len(data)
            )
        if not parsed.verifies(data):
            return CertificateTransportPutResult(
                False, target, CertificateTransportReason.CID_MISMATCH, len(data)
            )

        local_result: CertificateTransportPutResult | None = None
        if self.local_root is not None:
            local_result = self._write_local(target, data)

        ipfs_stored = False
        ipfs_reason = CertificateTransportReason.UNAVAILABLE
        if self._ipfs_put is not None:
            try:
                response_cid = _extract_ipfs_cid(self._ipfs_put(data))
            except BaseException:
                response_cid = None
                ipfs_reason = CertificateTransportReason.IPFS_ERROR
            else:
                if response_cid is None:
                    ipfs_reason = CertificateTransportReason.IPFS_RESPONSE_INVALID
                else:
                    try:
                        returned = decode_certificate_cid(response_cid)
                    except CertificateTransportError:
                        ipfs_reason = CertificateTransportReason.IPFS_RESPONSE_INVALID
                    else:
                        ipfs_stored = returned.verifies(data) and returned.digest == parsed.digest
                        ipfs_reason = (
                            CertificateTransportReason.OK
                            if ipfs_stored
                            else CertificateTransportReason.CID_MISMATCH
                        )

        stored = bool(local_result and local_result.stored) or ipfs_stored
        if stored:
            reason = (
                local_result.reason_code
                if local_result is not None and local_result.stored
                else CertificateTransportReason.OK
            )
        elif local_result is not None:
            reason = local_result.reason_code
        else:
            reason = ipfs_reason
        return CertificateTransportPutResult(
            stored,
            target,
            reason,
            len(data),
            bool(local_result and local_result.local_stored),
            ipfs_stored,
        )

    def get_bytes(self, cid: str) -> CertificateTransportGetResult:
        """Fetch bounded exact bytes; every backend fault is a safe miss."""

        try:
            parsed = decode_certificate_cid(cid)
        except CertificateTransportError:
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                cid if type(cid) is str else "",
                CertificateTransportReason.MALFORMED,
            )

        if self.local_root is not None:
            local = self._read_local(parsed.text)
            if local.hit:
                return local
            # Integrity and path failures must not be hidden by a remote fetch.
            if local.reason_code not in {
                CertificateTransportReason.NOT_FOUND,
                CertificateTransportReason.IO_ERROR,
            }:
                return local

        if self._ipfs_get is None:
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                parsed.text,
                CertificateTransportReason.NOT_FOUND,
            )
        try:
            response = self._ipfs_get(parsed.text)
        except BaseException:
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                parsed.text,
                CertificateTransportReason.IPFS_ERROR,
            )
        data = _extract_ipfs_bytes(response, maximum=self.max_blob_bytes)
        if data is None:
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                parsed.text,
                CertificateTransportReason.IPFS_RESPONSE_INVALID,
            )
        if not parsed.verifies(data):
            return CertificateTransportGetResult(
                CertificateTransportStatus.MISS,
                parsed.text,
                CertificateTransportReason.INTEGRITY_FAILED,
                byte_length=len(data),
            )
        if self.local_root is not None and self.cache_ipfs_reads:
            cached = self._write_local(parsed.text, data)
            if not cached.stored:
                return CertificateTransportGetResult(
                    CertificateTransportStatus.MISS,
                    parsed.text,
                    cached.reason_code,
                    byte_length=len(data),
                )
        return CertificateTransportGetResult(
            CertificateTransportStatus.HIT,
            parsed.text,
            CertificateTransportReason.OK,
            data,
            len(data),
            "ipfs",
        )

    def put(self, data: bytes, *, cid: str | None = None) -> str | None:
        result = self.put_bytes(data, claimed_cid=cid)
        return result.cid if result.stored else None

    def get(self, cid: str) -> bytes | None:
        return self.get_bytes(cid).data

    def has(self, cid: str) -> bool:
        return self.get_bytes(cid).hit


__all__ = [
    "CasGetResult",
    "CasPutResult",
    "CertificateTransportError",
    "CertificateTransportGetResult",
    "CertificateTransportPutResult",
    "CertificateTransportReason",
    "CertificateTransportStatus",
    "DecodedCertificateCID",
    "DEFAULT_MAX_BLOB_BYTES",
    "DEFAULT_MAX_CERTIFICATE_BYTES",
    "IpfsKitProofCertificateStore",
    "TEST_CERTIFICATE_STORE_TRANSPORT_INTERFACE",
    "TEST_CERTIFICATE_STORE_TRANSPORT_SCHEMA",
    "TEST_CERTIFICATE_STORE_TRANSPORT_SCHEMA_VERSION",
    "cid_for_certificate_bytes",
    "decode_certificate_cid",
    "verify_certificate_cid",
]

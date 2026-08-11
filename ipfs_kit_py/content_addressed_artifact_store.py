"""Local, bounded transport for canonical DAG-JSON artifacts.

The store is deliberately only a transport.  In particular, it does not
import an IPFS client, start a daemon, or grant proof/reuse authority.  Its
filesystem operations use directory file descriptors so a path which was
validated at construction cannot later be redirected by a symlink swap.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import stat
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


CID_CODEC_DAG_JSON = 0x0129
CID_MULTIHASH_SHA2_256 = 0x12
MAX_ARTIFACT_BYTES = 1_048_576
# This is deliberately substantially below Python's recursion limit.  The
# canonicalizer is iterative, but the parser used to check stored JSON is not;
# keeping the profile bounded makes the invariant explicit at both boundaries.
MAX_DAG_JSON_DEPTH = 256
MAX_DAG_JSON_NODES = 100_000
MAX_CID_TEXT_BYTES = 128
CANONICAL_ARTIFACT_STORE_INTERFACE = "CanonicalArtifactStoreTransport@2"


class ArtifactStoreReason(str, Enum):
    OK = "ok"
    NOT_FOUND = "not_found"
    INVALID_CID = "invalid_cid"
    PATH_ESCAPE = "path_escape"
    TOO_LARGE = "too_large"
    NOT_CANONICAL = "not_canonical"
    CID_MISMATCH = "cid_mismatch"
    CORRUPT = "corrupt"
    SYMLINK = "symlink"
    IO_ERROR = "io_error"


class CanonicalDagJsonError(ValueError):
    """A finite, caller-actionable canonical DAG-JSON validation failure."""


@dataclass(frozen=True)
class ArtifactPutResult:
    accepted: bool
    cid: str | None = None
    reason: ArtifactStoreReason = ArtifactStoreReason.OK
    byte_length: int = 0
    diagnostic: str | None = None


@dataclass(frozen=True)
class ArtifactGetResult:
    found: bool
    data: bytes | None = None
    cid: str | None = None
    reason: ArtifactStoreReason = ArtifactStoreReason.OK
    byte_length: int = 0
    diagnostic: str | None = None


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint cannot be negative")
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        result.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(result)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    value, shift, start = 0, 0, offset
    while offset < len(data) and shift <= 63:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if data[start:offset] != _encode_varint(value):
                raise ValueError("non-canonical varint")
            return value, offset
        shift += 7
    raise ValueError("truncated or oversized varint")


def _json_scalar(value: Any) -> str:
    """Encode one non-container without allowing JSON's implicit coercions."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.encoder.encode_basestring(value)
    if isinstance(value, int) and not isinstance(value, bool):
        # ``str`` can itself reject an absurd integer under Python's digit
        # safety limit; expose that as the same bounded input failure.
        try:
            return str(value)
        except ValueError as exc:
            raise CanonicalDagJsonError("integer is too large") from exc
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalDagJsonError("DAG-JSON floats must be finite")
        # json's scalar encoder supplies the canonical JSON spelling (notably
        # preserving ``1.0``) without traversing an application container.
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    raise CanonicalDagJsonError("DAG-JSON value has an unsupported type")


def canonical_dag_json_bytes(value: Any) -> bytes:
    """Return strict canonical DAG-JSON without depending on Python recursion.

    JSON's C and pure-Python encoders both recurse for nested arrays/objects.
    The transport accepts only a deliberately shallow profile, so serialize it
    with an explicit stack and reject cycles, excessive depth and huge shapes
    deterministically before they can exhaust the interpreter stack.
    """
    chunks: list[str] = []
    stack: list[tuple[str, Any, int]] = [("value", value, 0)]
    active: set[int] = set()
    nodes = 0
    while stack:
        action, current, depth = stack.pop()
        if action == "raw":
            chunks.append(current)
            continue
        if action == "exit":
            active.discard(current)
            continue
        nodes += 1
        if nodes > MAX_DAG_JSON_NODES:
            raise CanonicalDagJsonError("DAG-JSON has too many values")
        if depth > MAX_DAG_JSON_DEPTH:
            raise CanonicalDagJsonError("DAG-JSON nesting exceeds the profile")
        if isinstance(current, (list, dict)):
            identity = id(current)
            if identity in active:
                raise CanonicalDagJsonError("DAG-JSON cannot contain a cycle")
            active.add(identity)
            stack.append(("exit", identity, depth))
            if isinstance(current, list):
                stack.append(("raw", "]", depth))
                for index in range(len(current) - 1, -1, -1):
                    stack.append(("value", current[index], depth + 1))
                    if index:
                        stack.append(("raw", ",", depth))
                stack.append(("raw", "[", depth))
                continue
            if not all(isinstance(key, str) for key in current):
                raise CanonicalDagJsonError("DAG-JSON object keys must be strings")
            try:
                keys = sorted(current)
            except (TypeError, ValueError) as exc:
                raise CanonicalDagJsonError("DAG-JSON object keys are invalid") from exc
            stack.append(("raw", "}", depth))
            for index in range(len(keys) - 1, -1, -1):
                key = keys[index]
                stack.append(("value", current[key], depth + 1))
                stack.append(("raw", ":", depth))
                stack.append(("raw", json.encoder.encode_basestring(key), depth))
                if index:
                    stack.append(("raw", ",", depth))
            stack.append(("raw", "{", depth))
            continue
        chunks.append(_json_scalar(current))
    try:
        return "".join(chunks).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalDagJsonError("DAG-JSON strings must be valid Unicode") from exc


def is_canonical_dag_json(data: bytes) -> bool:
    if not isinstance(data, bytes):
        return False
    try:
        return canonical_dag_json_bytes(json.loads(data.decode("utf-8"))) == data
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, RecursionError):
        return False


def cid_for_canonical_bytes(data: bytes) -> str:
    if not isinstance(data, bytes) or not is_canonical_dag_json(data):
        raise CanonicalDagJsonError("CID input must be exact canonical DAG-JSON bytes")
    digest = hashlib.sha256(data).digest()
    binary = (_encode_varint(1) + _encode_varint(CID_CODEC_DAG_JSON)
              + _encode_varint(CID_MULTIHASH_SHA2_256) + _encode_varint(len(digest)) + digest)
    return "b" + base64.b32encode(binary).decode("ascii").lower().rstrip("=")


def validate_dag_json_cid(cid: str) -> bool:
    if not isinstance(cid, str) or len(cid) < 10:
        return False
    # A caller-controlled CID is text, but Python text can include lone
    # surrogates.  Treat an unencodable value as an invalid identifier rather
    # than allowing a boundary check itself to escape as UnicodeEncodeError.
    try:
        encoded = cid.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if (len(encoded) > MAX_CID_TEXT_BYTES
            or not cid.startswith("b") or cid != cid.lower()):
        return False
    token = cid[1:]
    if any(char not in "abcdefghijklmnopqrstuvwxyz234567" for char in token):
        return False
    try:
        binary = base64.b32decode(token.upper() + "=" * (-len(token) % 8), casefold=False)
        version, offset = _decode_varint(binary, 0)
        codec, offset = _decode_varint(binary, offset)
        hash_code, offset = _decode_varint(binary, offset)
        digest_length, offset = _decode_varint(binary, offset)
    except (ValueError, base64.binascii.Error):
        return False
    return ((version, codec, hash_code, digest_length) == (1, CID_CODEC_DAG_JSON, CID_MULTIHASH_SHA2_256, 32)
            and offset + digest_length == len(binary)
            and "b" + base64.b32encode(binary).decode("ascii").lower().rstrip("=") == cid)


def _cid_digest(cid: str) -> bytes:
    binary = base64.b32decode(cid[1:].upper() + "=" * (-len(cid[1:]) % 8), casefold=False)
    _, offset = _decode_varint(binary, 0)
    _, offset = _decode_varint(binary, offset)
    _, offset = _decode_varint(binary, offset)
    size, offset = _decode_varint(binary, offset)
    return binary[offset:offset + size]


_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


class _SecureDirectory:
    """A directory anchored by an fd, never by a re-resolved pathname."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(os.path.abspath(os.fspath(path)))
        self.fd: int | None = self._open_or_create_absolute(self.path)

    @staticmethod
    def _open_or_create_absolute(path: Path) -> int | None:
        if not path.is_absolute():
            return None
        fd = os.open(os.path.sep, _DIRECTORY_FLAGS)
        result: int | None = None
        try:
            for part in path.parts[1:]:
                try:
                    info = os.stat(part, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    os.mkdir(part, 0o700, dir_fd=fd)
                    info = os.stat(part, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                    return None
                next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            result = fd
            return result
        except OSError:
            return None
        finally:
            if fd >= 0 and fd != result:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def child(self, name: str, *, create: bool = False) -> int | None:
        if self.fd is None or not name or "/" in name or name in {".", ".."}:
            return None
        try:
            try:
                info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    return None
                os.mkdir(name, 0o700, dir_fd=self.fd)
                info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                return None
            return os.open(name, _DIRECTORY_FLAGS, dir_fd=self.fd)
        except OSError:
            return None

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def __del__(self) -> None:  # pragma: no cover - best-effort descriptor cleanup
        self.close()


class ContentAddressedArtifactStore:
    """A local CAS with strict CID, byte, and symlink-race boundaries."""

    interface = CANONICAL_ARTIFACT_STORE_INTERFACE
    authoritative = False

    def __init__(self, root: str | os.PathLike[str], *, max_blob_bytes: int = MAX_ARTIFACT_BYTES):
        if max_blob_bytes <= 0:
            raise ValueError("max_blob_bytes must be positive")
        self.root = Path(os.path.abspath(os.fspath(root)))
        self.max_blob_bytes = max_blob_bytes
        self.blobs_root = self.root / "blobs"
        self.quarantine_root = self.root / "quarantine"
        self._root = _SecureDirectory(self.root)
        if self._root.fd is not None:
            for name in ("blobs", "quarantine"):
                fd = self._root.child(name, create=True)
                if fd is not None:
                    os.close(fd)

    @staticmethod
    def canonical_bytes(value: Any) -> bytes:
        return canonical_dag_json_bytes(value)

    @staticmethod
    def cid_for_bytes(data: bytes) -> str:
        return cid_for_canonical_bytes(data)

    def _blob_path(self, cid: str, *, create_parent: bool = False) -> Path | None:
        if not validate_dag_json_cid(cid):
            return None
        # Compatibility/introspection only.  Security-sensitive access below
        # always uses fd-relative calls.
        directory = self._blob_dir(cid, create=create_parent)
        if directory is None:
            return None
        os.close(directory)
        return self.blobs_root / cid[1:3] / f"{cid}.json"

    def _blob_dir(self, cid: str, *, create: bool) -> int | None:
        if self._root.fd is None or not validate_dag_json_cid(cid):
            return None
        blobs = self._root.child("blobs", create=create)
        if blobs is None:
            return None
        try:
            prefix = cid[1:3]
            try:
                info = os.stat(prefix, dir_fd=blobs, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    return None
                os.mkdir(prefix, 0o700, dir_fd=blobs)
                info = os.stat(prefix, dir_fd=blobs, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                return None
            return os.open(prefix, _DIRECTORY_FLAGS, dir_fd=blobs)
        except OSError:
            return None
        finally:
            os.close(blobs)

    def _quarantine(self, blob_fd: int, filename: str, cid: str, reason: ArtifactStoreReason) -> None:
        quarantine = self._root.child("quarantine", create=True)
        if quarantine is None:
            return
        try:
            destination = f"{cid}.{reason.value}.{uuid.uuid4().hex}"
            os.replace(filename, destination, src_dir_fd=blob_fd, dst_dir_fd=quarantine)
            os.fsync(quarantine)
        except OSError:
            pass
        finally:
            os.close(quarantine)

    def put(self, value: Any, *, claimed_cid: str | None = None) -> ArtifactPutResult:
        try:
            return self.put_bytes(canonical_dag_json_bytes(value), claimed_cid=claimed_cid)
        except (TypeError, ValueError, RecursionError) as exc:
            return ArtifactPutResult(False, reason=ArtifactStoreReason.NOT_CANONICAL, diagnostic=str(exc))

    def put_bytes(self, data: bytes, *, claimed_cid: str | None = None) -> ArtifactPutResult:
        if not isinstance(data, bytes):
            return ArtifactPutResult(False, reason=ArtifactStoreReason.NOT_CANONICAL, diagnostic="bytes required")
        if len(data) > self.max_blob_bytes:
            return ArtifactPutResult(False, reason=ArtifactStoreReason.TOO_LARGE, byte_length=len(data))
        if not is_canonical_dag_json(data):
            return ArtifactPutResult(False, reason=ArtifactStoreReason.NOT_CANONICAL, byte_length=len(data))
        try:
            cid = cid_for_canonical_bytes(data)
        except (TypeError, ValueError, RecursionError) as exc:
            return ArtifactPutResult(False, reason=ArtifactStoreReason.NOT_CANONICAL,
                                     byte_length=len(data), diagnostic=str(exc))
        if claimed_cid is not None:
            if not validate_dag_json_cid(claimed_cid):
                return ArtifactPutResult(False, reason=ArtifactStoreReason.INVALID_CID, byte_length=len(data))
            if claimed_cid != cid:
                return ArtifactPutResult(False, cid=cid, reason=ArtifactStoreReason.CID_MISMATCH, byte_length=len(data))
        directory = self._blob_dir(cid, create=True)
        if directory is None:
            return ArtifactPutResult(False, cid=cid, reason=ArtifactStoreReason.PATH_ESCAPE, byte_length=len(data))
        filename, temporary = f"{cid}.json", f".artifact-{uuid.uuid4().hex}"
        try:
            try:
                info = os.stat(filename, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            if info is not None:
                existing = self.get_bytes(cid)
                return (ArtifactPutResult(True, cid=cid, byte_length=len(data)) if existing.found else
                        ArtifactPutResult(False, cid=cid, reason=existing.reason, byte_length=len(data)))
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            except FileExistsError:
                existing = self.get_bytes(cid)
                return (ArtifactPutResult(True, cid=cid, byte_length=len(data)) if existing.found else
                        ArtifactPutResult(False, cid=cid, reason=existing.reason, byte_length=len(data)))
            os.fsync(directory)
            # A pathname-visible attacker can unlink and substitute a leaf
            # after the temporary fd closes.  ``link(..., follow_symlinks=False)``
            # prevents an outbound write; this second anchored, no-follow
            # verification additionally prevents reporting such a substituted
            # leaf as a successful cache publication.
            verified = self.get_bytes(cid)
            if verified.found and verified.data == data:
                return ArtifactPutResult(True, cid=cid, byte_length=len(data))
            return ArtifactPutResult(False, cid=cid, reason=verified.reason,
                                     byte_length=len(data), diagnostic=verified.diagnostic)
        except OSError as exc:
            return ArtifactPutResult(False, cid=cid, reason=ArtifactStoreReason.IO_ERROR, byte_length=len(data), diagnostic=str(exc))
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            except OSError:
                pass
            os.close(directory)

    def get_bytes(self, cid: str) -> ArtifactGetResult:
        if not validate_dag_json_cid(cid):
            return ArtifactGetResult(False, cid=cid if isinstance(cid, str) else None, reason=ArtifactStoreReason.INVALID_CID)
        directory = self._blob_dir(cid, create=False)
        if directory is None:
            # A missing bucket is an ordinary cache miss; an unavailable root
            # is still fail-closed and indistinguishable to transport callers.
            return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.NOT_FOUND if self._root.fd is not None else ArtifactStoreReason.PATH_ESCAPE)
        filename = f"{cid}.json"
        try:
            try:
                info = os.stat(filename, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.NOT_FOUND)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                self._quarantine(directory, filename, cid, ArtifactStoreReason.SYMLINK)
                return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.SYMLINK)
            if info.st_size > self.max_blob_bytes:
                self._quarantine(directory, filename, cid, ArtifactStoreReason.TOO_LARGE)
                return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.TOO_LARGE, byte_length=info.st_size)
            fd = os.open(filename, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode):
                    self._quarantine(directory, filename, cid, ArtifactStoreReason.SYMLINK)
                    return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.SYMLINK)
                data = stream.read(self.max_blob_bytes + 1)
        except OSError as exc:
            self._quarantine(directory, filename, cid, ArtifactStoreReason.SYMLINK)
            return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.IO_ERROR, diagnostic=str(exc))
        finally:
            os.close(directory)
        if len(data) > self.max_blob_bytes:
            # Reopen the anchored directory for the quarantine move.
            directory = self._blob_dir(cid, create=False)
            if directory is not None:
                self._quarantine(directory, filename, cid, ArtifactStoreReason.TOO_LARGE)
                os.close(directory)
            return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.TOO_LARGE, byte_length=len(data))
        if not is_canonical_dag_json(data) or cid_for_canonical_bytes(data) != cid:
            directory = self._blob_dir(cid, create=False)
            if directory is not None:
                self._quarantine(directory, filename, cid, ArtifactStoreReason.CORRUPT)
                os.close(directory)
            return ArtifactGetResult(False, cid=cid, reason=ArtifactStoreReason.CORRUPT, byte_length=len(data))
        return ArtifactGetResult(True, data=data, cid=cid, byte_length=len(data))

    def get(self, cid: str) -> Any | None:
        result = self.get_bytes(cid)
        if not result.found or result.data is None:
            return None
        try:
            return json.loads(result.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            return None

    def contains(self, cid: str) -> bool:
        return self.get_bytes(cid).found

    def can_authorize_proof(self) -> bool:
        return False

    def import_from_transport(self, cid: str, payload: bytes) -> ArtifactPutResult:
        return self.put_bytes(payload, claimed_cid=cid)


KitContentAddressedArtifactStore = ContentAddressedArtifactStore

"""JSON-only, ownership-checked GraphRAG generation persistence.

The store never deserializes executable data.  Every accepted file is regular,
owned by the expected user, private, bounded, and parsed as a closed JSON
contract before it is returned to callers.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping

from .contracts import (
    GraphRAGContractError,
    GraphRAGGeneration,
    GraphRAGIndexManifest,
    canonical_json_bytes,
)


STORAGE_SCHEMA: Final[str] = "ipfs_kit_py/graphrag/storage-pointer@1"
STORAGE_VERSION: Final[int] = 1
MAX_GENERATION_BYTES: Final[int] = 16 * 1024 * 1024
MAX_POINTER_BYTES: Final[int] = 4096
_PRIVATE_FILE_MODE: Final[int] = 0o600
_PRIVATE_DIR_MODE: Final[int] = 0o700


class GraphRAGStorageError(GraphRAGContractError):
    """Base error for unsafe or malformed GraphRAG persistence."""


class GraphRAGStorageSecurityError(GraphRAGStorageError):
    """Filesystem type, owner, permission, or symlink checks failed."""


class GraphRAGStorageFormatError(GraphRAGStorageError):
    """JSON syntax, schema, digest, or size checks failed."""


class GraphRAGGenerationExistsError(GraphRAGStorageError):
    """A generation ID is immutable and was already published."""


@dataclass(frozen=True)
class GenerationReceipt:
    generation_id: str
    generation_cid: str
    size_bytes: int


def _reject_json_constant(value: str) -> None:
    raise GraphRAGStorageFormatError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GraphRAGStorageFormatError("duplicate JSON object key")
        result[key] = value
    return result


def _json_object(data: bytes, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_object, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, GraphRAGStorageFormatError) as exc:
        raise GraphRAGStorageFormatError(f"{name} is not valid canonical JSON") from exc
    if not isinstance(value, Mapping):
        raise GraphRAGStorageFormatError(f"{name} must be a JSON object")
    return value


def _canonical_json_object(data: bytes, name: str) -> Mapping[str, Any]:
    """Parse a closed JSON object and reject alternate byte encodings.

    Persisted records are written by this module with ``canonical_json_bytes``.
    Requiring the exact representation removes parser differentials (duplicate
    keys, escapes, whitespace, or numeric spellings) from the storage format.
    """

    value = _json_object(data, name)
    try:
        canonical = canonical_json_bytes(value)
    except GraphRAGContractError as exc:
        raise GraphRAGStorageFormatError(f"{name} is outside the JSON contract") from exc
    if data != canonical:
        raise GraphRAGStorageFormatError(f"{name} is not in canonical JSON form")
    return value


class SafeGraphRAGStorage:
    """Publish and read immutable GraphRAG generations under one private root."""

    def __init__(self, root: str | os.PathLike[str], *, owner_uid: int | None = None, max_generation_bytes: int = MAX_GENERATION_BYTES) -> None:
        if not isinstance(max_generation_bytes, int) or isinstance(max_generation_bytes, bool) or not 1 <= max_generation_bytes <= MAX_GENERATION_BYTES:
            raise GraphRAGStorageError("max_generation_bytes is outside the supported bound")
        self.root = Path(root).expanduser().absolute()
        self.owner_uid = os.geteuid() if owner_uid is None else owner_uid
        if not isinstance(self.owner_uid, int) or self.owner_uid < 0:
            raise GraphRAGStorageError("owner_uid must be a non-negative integer")
        self.max_generation_bytes = max_generation_bytes
        self._ensure_private_directory(self.root)
        self._ensure_private_directory(self.generations_dir)
        self._ensure_private_directory(self.staging_dir)

    @property
    def generations_dir(self) -> Path:
        return self.root / "generations"

    @property
    def staging_dir(self) -> Path:
        return self.root / ".staging"

    @property
    def current_path(self) -> Path:
        return self.root / "CURRENT.json"

    def _ensure_private_directory(self, path: Path) -> None:
        created = False
        try:
            path.mkdir(mode=_PRIVATE_DIR_MODE, parents=True, exist_ok=False)
            created = True
        except FileExistsError:
            # Existing storage is untrusted input.  Do not silently repair its
            # ownership or mode before checking it.
            pass
        except OSError as exc:
            raise GraphRAGStorageSecurityError(f"cannot create storage directory {path}") from exc
        if created:
            try:
                os.chmod(path, _PRIVATE_DIR_MODE)
            except OSError as exc:
                raise GraphRAGStorageSecurityError(
                    f"cannot set storage directory permissions for {path}"
                ) from exc
        self._check_directory(path)

    def _check_directory(self, path: Path) -> os.stat_result:
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise GraphRAGStorageSecurityError(f"cannot stat storage directory {path}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise GraphRAGStorageSecurityError(f"storage path must be a real directory: {path}")
        if info.st_uid != self.owner_uid:
            raise GraphRAGStorageSecurityError(f"storage directory has unexpected owner: {path}")
        if stat.S_IMODE(info.st_mode) != _PRIVATE_DIR_MODE:
            raise GraphRAGStorageSecurityError(f"storage directory must have mode 0700: {path}")
        return info

    def _check_file(self, path: Path, maximum: int) -> os.stat_result:
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise GraphRAGStorageSecurityError(f"cannot stat storage file {path}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise GraphRAGStorageSecurityError(f"storage file must be a regular non-symlink: {path}")
        if info.st_uid != self.owner_uid or stat.S_IMODE(info.st_mode) != _PRIVATE_FILE_MODE or info.st_nlink != 1:
            raise GraphRAGStorageSecurityError(f"storage file owner, mode, or link count is unsafe: {path}")
        if info.st_size < 0 or info.st_size > maximum:
            raise GraphRAGStorageFormatError(f"storage file exceeds its byte bound: {path}")
        return info

    def _read_private_file(self, path: Path, maximum: int) -> bytes:
        self._check_directory(path.parent)
        expected = self._check_file(path, maximum)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except OSError as exc:
            raise GraphRAGStorageSecurityError(f"cannot safely open storage file {path}") from exc
        try:
            actual = os.fstat(fd)
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                raise GraphRAGStorageSecurityError("storage file changed while being opened")
            if not stat.S_ISREG(actual.st_mode) or actual.st_uid != self.owner_uid or stat.S_IMODE(actual.st_mode) != _PRIVATE_FILE_MODE or actual.st_nlink != 1 or actual.st_size > maximum:
                raise GraphRAGStorageSecurityError("opened storage file no longer satisfies safety checks")
            chunks: list[bytes] = []
            remaining = actual.st_size
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    raise GraphRAGStorageFormatError("storage file ended before its declared size")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(fd, 1):
                raise GraphRAGStorageFormatError("storage file grew while being read")
            return b"".join(chunks)
        finally:
            os.close(fd)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(path, flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _write_new_private_file(path: Path, data: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, _PRIVATE_FILE_MODE)
        try:
            os.fchmod(fd, _PRIVATE_FILE_MODE)
            offset = 0
            while offset < len(data):
                offset += os.write(fd, data[offset:])
            os.fsync(fd)
        finally:
            os.close(fd)

    def _generation_path(self, generation_id: str) -> Path:
        # GraphRAG contracts already validate identifiers; repeating it here also
        # makes this path boundary fail closed for direct storage callers.
        if not isinstance(generation_id, str) or not generation_id or "/" in generation_id or "\\" in generation_id or generation_id in {".", ".."}:
            raise GraphRAGStorageError("generation_id is not a safe filename")
        return self.generations_dir / f"{generation_id}.json"

    def publish_generation(self, generation: GraphRAGGeneration, *, expected_manifest: GraphRAGIndexManifest | None = None) -> GenerationReceipt:
        """Durably publish a new immutable generation, then atomically advance CURRENT."""
        if not isinstance(generation, GraphRAGGeneration):
            raise GraphRAGStorageError("generation must be GraphRAGGeneration")
        if expected_manifest is not None:
            if not isinstance(expected_manifest, GraphRAGIndexManifest):
                raise GraphRAGStorageError("expected_manifest must be GraphRAGIndexManifest")
            expected_manifest.assert_compatible(generation.manifest)
        data = canonical_json_bytes(generation.to_record())
        if len(data) > self.max_generation_bytes:
            raise GraphRAGStorageFormatError("generation exceeds configured byte bound")
        self._check_directory(self.root)
        self._check_directory(self.generations_dir)
        self._check_directory(self.staging_dir)
        destination = self._generation_path(generation.manifest.generation_id)
        if os.path.lexists(destination):
            raise GraphRAGGenerationExistsError(f"generation already exists: {generation.manifest.generation_id}")
        temporary: Path | None = self.staging_dir / f"new-{secrets.token_hex(24)}.json"
        try:
            self._write_new_private_file(temporary, data)
            self._check_file(temporary, self.max_generation_bytes)
            try:
                os.link(temporary, destination, follow_symlinks=False)
            except FileExistsError as exc:
                raise GraphRAGGenerationExistsError(f"generation already exists: {generation.manifest.generation_id}") from exc
            # The final hard link is now durable.  Remove the staging name
            # before checking the permanent file's single-link invariant.
            temporary.unlink()
            temporary = None
            self._check_file(destination, self.max_generation_bytes)
            self._fsync_directory(self.generations_dir)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        pointer = {
            "schema": STORAGE_SCHEMA,
            "storage_version": STORAGE_VERSION,
            "generation_id": generation.manifest.generation_id,
            "generation_cid": generation.content_id,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        pointer_data = canonical_json_bytes(pointer)
        temporary_pointer = self.staging_dir / f"current-{secrets.token_hex(24)}.json"
        try:
            self._write_new_private_file(temporary_pointer, pointer_data)
            os.replace(temporary_pointer, self.current_path)
            self._check_file(self.current_path, MAX_POINTER_BYTES)
            self._fsync_directory(self.root)
        finally:
            try:
                temporary_pointer.unlink()
            except FileNotFoundError:
                pass
        return GenerationReceipt(generation.manifest.generation_id, generation.content_id, len(data))

    publish = publish_generation

    def _load_pointer(self) -> Mapping[str, Any]:
        raw = _canonical_json_object(self._read_private_file(self.current_path, MAX_POINTER_BYTES), "CURRENT pointer")
        required = {"schema", "storage_version", "generation_id", "generation_cid", "sha256"}
        if set(raw) != required or raw.get("schema") != STORAGE_SCHEMA or raw.get("storage_version") != STORAGE_VERSION:
            raise GraphRAGStorageFormatError("CURRENT pointer schema is not supported")
        if not all(isinstance(raw[name], str) and raw[name] for name in ("generation_id", "generation_cid", "sha256")):
            raise GraphRAGStorageFormatError("CURRENT pointer has invalid identities")
        if len(raw["sha256"]) != 64 or any(char not in "0123456789abcdef" for char in raw["sha256"]):
            raise GraphRAGStorageFormatError("CURRENT pointer digest is invalid")
        return raw

    def load_generation(self, generation_id: str | None = None, *, expected_manifest: GraphRAGIndexManifest | None = None) -> GraphRAGGeneration:
        """Load a fully validated JSON generation; no executable decoder is used."""
        if generation_id is None:
            pointer = self._load_pointer()
            generation_id = pointer["generation_id"]
        else:
            pointer = None
        path = self._generation_path(generation_id)
        data = self._read_private_file(path, self.max_generation_bytes)
        if pointer is not None and hashlib.sha256(data).hexdigest() != pointer["sha256"]:
            raise GraphRAGStorageFormatError("CURRENT pointer digest does not match generation")
        try:
            generation = GraphRAGGeneration.from_dict(_canonical_json_object(data, "generation"))
        except GraphRAGContractError as exc:
            raise GraphRAGStorageFormatError("generation does not satisfy the GraphRAG schema") from exc
        if generation.manifest.generation_id != generation_id:
            raise GraphRAGStorageFormatError("generation filename and manifest identity differ")
        if pointer is not None and generation.content_id != pointer["generation_cid"]:
            raise GraphRAGStorageFormatError("CURRENT pointer content identity does not match generation")
        if expected_manifest is not None:
            if not isinstance(expected_manifest, GraphRAGIndexManifest):
                raise GraphRAGStorageError("expected_manifest must be GraphRAGIndexManifest")
            expected_manifest.assert_compatible(generation.manifest)
        return generation

    load = load_generation


GraphRAGSafeStorage = SafeGraphRAGStorage


def publish_generation(root: str | os.PathLike[str], generation: GraphRAGGeneration, *, expected_manifest: GraphRAGIndexManifest | None = None) -> GenerationReceipt:
    return SafeGraphRAGStorage(root).publish_generation(generation, expected_manifest=expected_manifest)


def load_generation(root: str | os.PathLike[str], generation_id: str | None = None, *, expected_manifest: GraphRAGIndexManifest | None = None) -> GraphRAGGeneration:
    return SafeGraphRAGStorage(root).load_generation(generation_id, expected_manifest=expected_manifest)

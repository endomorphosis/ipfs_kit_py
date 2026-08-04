"""Bounded, data-only persistence for the ARC integration adapter.

This is intentionally JSON plus base64, never pickle, marshal, import hooks,
or a user supplied deserializer.  Files are written to a same-directory
temporary name, fsynced, and replaced atomically.  Readers reject every
malformed envelope as a cache miss without changing the target cache.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Final, Protocol


PERSISTENCE_SCHEMA: Final[str] = "ipfs_kit_py/cache/arc/persistence@1"
PERSISTENCE_VERSION: Final[int] = 1
MAX_PERSISTENCE_BYTES: Final[int] = 16 * 1024 * 1024
MAX_PERSISTED_ENTRIES: Final[int] = 16_384
MAX_PERSISTED_VALUE_BYTES: Final[int] = 8 * 1024 * 1024


class PersistenceError(ValueError):
    """A requested persistence write exceeds the bounded format."""


class _PersistenceTarget(Protocol):
    def _persistence_export(self) -> list[dict[str, Any]]: ...
    def _persistence_import(self, entries: list[dict[str, Any]]) -> bool: ...
    @property
    def metrics_collector(self) -> Any: ...


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _increment(target: Any, name: str) -> None:
    collector = getattr(target, "metrics_collector", None)
    if collector is not None:
        collector.increment(name)


def _validated_entries(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > MAX_PERSISTED_ENTRIES:
        raise ValueError("entries are not a bounded list")
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"binding", "value", "sha256"}:
            raise ValueError("invalid persisted entry shape")
        binding, encoded, checksum = item["binding"], item["value"], item["sha256"]
        if not isinstance(binding, dict) or not isinstance(encoded, str) or not isinstance(checksum, str):
            raise ValueError("invalid persisted entry types")
        if len(encoded) > (MAX_PERSISTED_VALUE_BYTES * 4 // 3) + 8:
            raise ValueError("persisted value exceeds limit")
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError("invalid base64 value") from exc
        if len(data) > MAX_PERSISTED_VALUE_BYTES or hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError("persisted value digest mismatch")
        result.append({"binding": binding, "value": data})
    return result


def save(cache: _PersistenceTarget, path: str | os.PathLike[str]) -> bool:
    """Atomically save bounded cache entries.  Raises only for write misuse."""

    source = cache._persistence_export()
    if len(source) > MAX_PERSISTED_ENTRIES:
        raise PersistenceError("too many cache entries for persistence envelope")
    entries: list[dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict) or set(item) != {"binding", "value"}:
            raise PersistenceError("cache exported an invalid persistence entry")
        data = item["value"]
        if not isinstance(data, bytes) or len(data) > MAX_PERSISTED_VALUE_BYTES:
            raise PersistenceError("cache value exceeds persistence limit")
        entries.append({
            "binding": item["binding"],
            "value": base64.b64encode(data).decode("ascii"),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    payload = {"schema": PERSISTENCE_SCHEMA, "version": PERSISTENCE_VERSION, "entries": entries}
    envelope = {**payload, "sha256": _digest(payload)}
    encoded = _canonical_json(envelope)
    if len(encoded) > MAX_PERSISTENCE_BYTES:
        raise PersistenceError("persistence envelope exceeds byte limit")

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        try:
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Directory fsync is unavailable on some platforms; replacement
            # has still completed atomically on the local filesystem.
            pass
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    _increment(cache, "persistence_writes")
    return True


def load(cache: _PersistenceTarget, path: str | os.PathLike[str]) -> bool:
    """Load a valid envelope, otherwise leave ``cache`` untouched and miss."""

    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_PERSISTENCE_BYTES + 1)
        if len(data) > MAX_PERSISTENCE_BYTES:
            raise ValueError("persistence envelope exceeds byte limit")
        decoded = json.loads(data.decode("utf-8"))
        if not isinstance(decoded, dict) or set(decoded) != {"schema", "version", "entries", "sha256"}:
            raise ValueError("invalid persistence envelope shape")
        if decoded["schema"] != PERSISTENCE_SCHEMA or decoded["version"] != PERSISTENCE_VERSION:
            _increment(cache, "persistence_schema_rejections")
            return False
        payload = {key: decoded[key] for key in ("schema", "version", "entries")}
        if not isinstance(decoded["sha256"], str) or _digest(payload) != decoded["sha256"]:
            raise ValueError("persistence envelope checksum mismatch")
        entries = _validated_entries(decoded["entries"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, RecursionError):
        _increment(cache, "persistence_corrupt")
        return False
    if not cache._persistence_import(entries):
        _increment(cache, "persistence_stale_rejections")
        return False
    _increment(cache, "persistence_loads")
    return True


class ARCPersistence:
    """Convenience object for a fixed persistence location."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def save(self, cache: _PersistenceTarget) -> bool:
        return save(cache, self.path)

    def load(self, cache: _PersistenceTarget) -> bool:
        return load(cache, self.path)


PersistenceStore = ARCPersistence
save_cache = save
load_cache = load

__all__ = [
    "PERSISTENCE_SCHEMA", "PERSISTENCE_VERSION", "MAX_PERSISTENCE_BYTES",
    "MAX_PERSISTED_ENTRIES", "MAX_PERSISTED_VALUE_BYTES", "PersistenceError",
    "ARCPersistence", "PersistenceStore", "save", "load", "save_cache", "load_cache",
]

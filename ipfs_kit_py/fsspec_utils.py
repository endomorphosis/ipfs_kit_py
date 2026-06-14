"""Shared helpers for fsspec storage backend implementations."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


INDEX_SCHEMA = "ipfs_kit_py.fsspec.index.v1"

_CID_RE = re.compile(
    r"^(?:"
    r"Qm[1-9A-HJ-NP-Za-km-z]{44}"
    r"|ba[a-z2-7]{20,}"
    r"|z[1-9A-HJ-NP-Za-km-z]{20,}"
    r")$"
)


def protocol_list(protocols: str | Iterable[str]) -> list[str]:
    """Return protocols as a list of non-empty strings."""
    if isinstance(protocols, str):
        return [protocols]
    return [protocol for protocol in protocols if protocol]


def strip_protocol(path: Any, protocols: str | Iterable[str]) -> Any:
    """Remove one of the supplied protocol prefixes from a path."""
    if isinstance(path, (list, tuple)):
        return type(path)(strip_protocol(item, protocols) for item in path)
    if not isinstance(path, str):
        return path

    for protocol in protocol_list(protocols):
        prefix = f"{protocol}://"
        if path.startswith(prefix):
            return path[len(prefix) :]
    return path


def ensure_protocol(
    path: str,
    protocol: str,
    known_protocols: Optional[str | Iterable[str]] = None,
) -> str:
    """Return a path with a protocol prefix, preserving existing known prefixes."""
    protocols = protocol_list(known_protocols or protocol)
    if any(path.startswith(f"{candidate}://") for candidate in protocols):
        return path
    return f"{protocol}://{path.lstrip('/')}"


def normalize_protocol_path(path: Any, protocol: str, known_protocols: Optional[str | Iterable[str]] = None) -> Any:
    """Normalize a path into ``protocol://name`` form."""
    if isinstance(path, (list, tuple)):
        return type(path)(normalize_protocol_path(item, protocol, known_protocols) for item in path)
    if not isinstance(path, str):
        return path
    stripped = strip_protocol(path, known_protocols or protocol).lstrip("/")
    return f"{protocol}://{stripped}" if stripped else f"{protocol}://"


def is_content_id(value: Any) -> bool:
    """Return whether a value looks like a CIDv0, CIDv1, or multibase content id."""
    if not isinstance(value, str):
        return False
    candidate = value.strip().removeprefix("/ipfs/")
    return bool(_CID_RE.match(candidate))


def normalize_metadata(
    *metadata: Optional[Mapping[str, Any]],
    include_none: bool = False,
    **overrides: Any,
) -> Dict[str, Any]:
    """Merge metadata mappings into a JSON-friendly shallow dictionary."""
    merged: Dict[str, Any] = {}
    for payload in metadata:
        if not payload:
            continue
        for key, value in payload.items():
            if value is None and not include_none:
                continue
            merged[str(key)] = value
    for key, value in overrides.items():
        if value is None and not include_none:
            continue
        merged[str(key)] = value
    return merged


def standard_file_info(
    name: str,
    *,
    protocol: Optional[str] = None,
    size: Any = 0,
    type: str = "file",
    metadata: Optional[Mapping[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a fsspec-style info dictionary with stable common fields."""
    display_name = ensure_protocol(name, protocol) if protocol else name
    info = normalize_metadata(metadata, extra)
    info["name"] = display_name
    info["type"] = type
    if size is not None:
        try:
            info["size"] = int(size)
        except (TypeError, ValueError):
            info["size"] = size
    else:
        info["size"] = None
    return info


def backend_capabilities(
    backend: str,
    *,
    protocol: Optional[str] = None,
    readable: bool = True,
    writable: bool = True,
    delete: bool = False,
    list: bool = True,
    local_index: bool = False,
    content_addressed: bool = True,
    mutable_paths: bool = False,
    **extra: Any,
) -> Dict[str, Any]:
    """Return a normalized backend capability report."""
    report = normalize_metadata(extra)
    report.update(
        {
            "backend": backend,
            "protocol": protocol or backend,
            "readable": bool(readable),
            "writable": bool(writable),
            "delete": bool(delete),
            "list": bool(list),
            "local_index": bool(local_index),
            "content_addressed": bool(content_addressed),
            "mutable_paths": bool(mutable_paths),
        }
    )
    return report


def empty_index(schema: str = INDEX_SCHEMA) -> Dict[str, Any]:
    """Return an empty local metadata index payload."""
    return {"schema": schema, "items": {}}


def read_json_index(path: os.PathLike[str] | str | None, *, schema: str = INDEX_SCHEMA) -> Dict[str, Any]:
    """Read an optional JSON index from disk."""
    if path is None:
        return empty_index(schema)
    index_path = Path(path).expanduser()
    if not index_path.exists():
        return empty_index(schema)

    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"fsspec index must be a JSON object: {index_path}")
    items = payload.get("items")
    return {
        "schema": payload.get("schema") or schema,
        "items": dict(items) if isinstance(items, Mapping) else {},
    }


def write_json_index(
    path: os.PathLike[str] | str,
    index: Mapping[str, Any],
    *,
    schema: str = INDEX_SCHEMA,
) -> None:
    """Atomically write a JSON metadata index to disk."""
    index_path = Path(path).expanduser()
    payload = {
        "schema": index.get("schema") or schema,
        "items": index.get("items") if isinstance(index.get("items"), Mapping) else {},
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=index_path.parent,
            prefix=f".{index_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, index_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


class LocalMetadataIndex:
    """Small JSON index for mapping logical names to backend metadata."""

    def __init__(
        self,
        path: os.PathLike[str] | str,
        *,
        protocol: Optional[str] = None,
        schema: str = INDEX_SCHEMA,
    ) -> None:
        self.path = Path(path).expanduser()
        self.protocol = protocol
        self.schema = schema

    def _key(self, name: str) -> str:
        stripped = strip_protocol(name, self.protocol) if self.protocol else name
        return str(stripped).lstrip("/")

    def load(self) -> Dict[str, Any]:
        return read_json_index(self.path, schema=self.schema)

    def list_items(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: dict(item)
            for name, item in self.load()["items"].items()
            if isinstance(item, Mapping)
        }

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        item = self.load()["items"].get(self._key(name))
        return dict(item) if isinstance(item, Mapping) else None

    def update(self, name: str, metadata: Mapping[str, Any]) -> Dict[str, Any]:
        index = self.load()
        key = self._key(name)
        entry = normalize_metadata(metadata)
        entry.setdefault("name", key)
        entry.setdefault("updated_at", utc_now())
        index["items"][key] = entry
        write_json_index(self.path, index, schema=self.schema)
        return dict(entry)

    def remove(self, name: str) -> Optional[Dict[str, Any]]:
        index = self.load()
        removed = index["items"].pop(self._key(name), None)
        write_json_index(self.path, index, schema=self.schema)
        return dict(removed) if isinstance(removed, Mapping) else removed


def utc_now() -> str:
    """Return the current UTC timestamp in compact ISO-8601 form."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def raise_for_fsspec_result(
    result: Mapping[str, Any],
    *,
    backend: str,
    operation: str,
    path: Optional[str] = None,
) -> None:
    """Raise a consistent fsspec exception for unsuccessful backend results."""
    if result.get("success", False):
        return

    status = result.get("status") or result.get("code") or result.get("status_code")
    error = result.get("error") or result.get("message") or "unknown error"
    target = f" for {path}" if path else ""
    message = f"{backend} {operation} failed{target}: {error}"

    if status in {404, "404", "missing", "not_found"} or "not found" in str(error).lower() or "missing" in str(error).lower():
        raise FileNotFoundError(message)
    if status in {409, "409", "exists", "already_exists"}:
        raise FileExistsError(message)
    if status in {401, 403, "401", "403", "unauthorized", "forbidden"}:
        raise PermissionError(message)
    raise OSError(message)


__all__ = [
    "INDEX_SCHEMA",
    "LocalMetadataIndex",
    "backend_capabilities",
    "empty_index",
    "ensure_protocol",
    "is_content_id",
    "normalize_metadata",
    "normalize_protocol_path",
    "protocol_list",
    "raise_for_fsspec_result",
    "read_json_index",
    "standard_file_info",
    "strip_protocol",
    "utc_now",
    "write_json_index",
]

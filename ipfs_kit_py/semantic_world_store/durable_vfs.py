"""Durable namespace for the canonical VFS service.

``CanonicalVFSService`` stays free of host I/O. This boundary is the injected
side effect: it stores the same entries as the in-memory namespace, under the
coordination-store directory, so a reopened store reads the published outbox.
It does not write a git repository and it is not supervisor acceptance.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path

from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
from ipfs_kit_py.core.vfs.service import (
    InMemoryVFSStorage,
    VFSServiceError,
    VFSStoredEntry,
)


class DurableVFSNamespace(InMemoryVFSStorage):
    """File-backed ``VFSStorageBoundary`` rooted at one coordination directory."""

    def __init__(self, directory: Path | str) -> None:
        super().__init__()
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._index_path = self._directory / "namespace.json"
        self._lock = threading.Lock()
        self._load()

    @property
    def directory(self) -> Path:
        return self._directory

    def put(self, path: str, entry: VFSStoredEntry) -> None:
        with self._lock:
            super().put(path, entry)
            self._save()

    def delete(self, path: str) -> None:
        with self._lock:
            super().delete(path)
            self._save()

    def rename(self, source: str, target: str) -> None:
        with self._lock:
            super().rename(source, target)
            self._save()

    def _load(self) -> None:
        if not self._index_path.is_file():
            return
        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise VFSServiceError(f"vfs namespace index is unreadable: {exc}") from exc
        if not isinstance(payload, dict):
            raise VFSServiceError("vfs namespace index must be an object")
        generation = payload.get("generation")
        rows = payload.get("entries")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            raise VFSServiceError("vfs namespace generation is invalid")
        if not isinstance(rows, list):
            raise VFSServiceError("vfs namespace entries must be a list")
        entries: dict[str, VFSStoredEntry] = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                raise VFSServiceError("vfs namespace entry is invalid")
            try:
                content = base64.b64decode(str(row.get("content_b64") or ""), validate=True)
                entries[row["path"]] = VFSStoredEntry(
                    kind=VFSEntryKind(str(row.get("kind") or "")),
                    content=content,
                    content_cid=str(row.get("content_cid") or ""),
                    version_cid=str(row.get("version_cid") or ""),
                    target=str(row.get("target") or ""),
                    mtime_unix_ms=int(row.get("mtime_unix_ms") or 0),
                    mode=int(row.get("mode") or 0),
                    mount_id=str(row.get("mount_id") or ""),
                    is_readonly=bool(row.get("is_readonly")),
                )
            except (TypeError, ValueError) as exc:
                raise VFSServiceError(f"vfs namespace entry is invalid: {exc}") from exc
        if "" not in entries:
            raise VFSServiceError("vfs namespace is missing its root")
        self._entries = entries
        self._generation = generation

    def _save(self) -> None:
        rows = []
        for path in sorted(self._entries):
            entry = self._entries[path]
            rows.append(
                {
                    "path": path,
                    "kind": entry.kind.value,
                    "content_b64": base64.b64encode(entry.content).decode("ascii"),
                    "content_cid": entry.content_cid,
                    "version_cid": entry.version_cid,
                    "target": entry.target,
                    "mtime_unix_ms": entry.mtime_unix_ms,
                    "mode": entry.mode,
                    "mount_id": entry.mount_id,
                    "is_readonly": entry.is_readonly,
                }
            )
        payload = json.dumps({"generation": self._generation, "entries": rows}, sort_keys=True)
        temporary = self._index_path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self._index_path)


def canonical_vfs_for_store(root: Path | str):
    """Canonical VFS whose namespace persists under ``root``."""

    from ipfs_kit_py.core.vfs.service import CanonicalVFSService

    return CanonicalVFSService(DurableVFSNamespace(Path(root) / "vfs-namespace"))

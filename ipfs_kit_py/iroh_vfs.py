"""Canonical VFS adapter for :mod:`ipfs_kit_py.iroh_fsspec`.

The fsspec implementation owns Iroh namespace and blob semantics.  This
adapter owns the much smaller translation between a VFS mount-relative path
and one immutable mount target.  Keeping that boundary explicit prevents a
mount from escaping into another namespace and keeps Iroh-specific content
identifiers out of the VFS ``cid`` fields.
"""

from __future__ import annotations

import posixpath
from collections.abc import Mapping
from typing import Any

from .iroh.errors import IrohInvalidPathError, IrohPermissionDeniedError
from .iroh_fsspec import IROH_BLOB_PROTOCOL, IROH_PROTOCOL, IrohFileSystem, IrohPath, parse_iroh_path


def _relative_path(value: str) -> str:
    """Return a safe POSIX mount-relative path."""

    if not isinstance(value, str):
        raise TypeError("VFS relative paths must be strings")
    if "\x00" in value:
        raise IrohInvalidPathError("VFS paths cannot contain NUL", operation="vfs.resolve")
    raw = value.replace("\\", "/").lstrip("/")
    normalized = posixpath.normpath(raw)
    if normalized in {"", "."}:
        return ""
    if normalized == ".." or normalized.startswith("../"):
        raise IrohInvalidPathError(
            "VFS path escapes its Iroh mount", operation="vfs.resolve"
        )
    return normalized


class IrohVFSAdapter:
    """Mount one Iroh namespace subtree (or immutable blob) in the VFS.

    Construction is inert.  In particular, creating or restoring a mount does
    not start, install, or probe an Iroh service; that remains the lazy runtime
    client's responsibility.
    """

    backend = "iroh"

    def __init__(
        self,
        filesystem: IrohFileSystem,
        target: str,
        *,
        backend_name: str | None = None,
        read_only: bool = False,
    ) -> None:
        if not isinstance(filesystem, IrohFileSystem):
            raise TypeError("filesystem must be an IrohFileSystem")
        parsed = parse_iroh_path(target)
        if filesystem._iroh_protocol != parsed.protocol:
            raise ValueError("Iroh filesystem protocol does not match the VFS mount target")
        self.filesystem = filesystem
        self.target = parsed.canonical_url
        self.address = parsed
        self.backend_name = backend_name
        self.read_only = bool(read_only or filesystem.read_only or parsed.is_blob)

    @classmethod
    def create(
        cls,
        target: str,
        *,
        filesystem: IrohFileSystem | None = None,
        backend_manager: Any = None,
        backend_name: str | None = None,
        read_only: bool = False,
        storage_options: Mapping[str, Any] | None = None,
    ) -> "IrohVFSAdapter":
        """Create a direct URL mount or resolve a validated named backend."""

        options = dict(storage_options or {})
        selected_name = backend_name
        selected_target = target

        # Restored named mounts persist their canonical URL as the target and
        # the configured name separately. Rebuild the filesystem through the
        # manager so credentials remain references and are resolved lazily.
        if selected_name and backend_manager is not None and filesystem is None:
            config = backend_manager.get_backend_config(selected_name, redact=False)
            if not isinstance(config, Mapping) or config.get("type") != "iroh":
                raise ValueError(f"named backend is not a valid Iroh backend: {selected_name}")
            namespace = config.get("namespace")
            if isinstance(namespace, Mapping):
                read_only = bool(read_only or namespace.get("access") == "read-only")
            filesystem = backend_manager.get_backend_adapter(selected_name, **options)

        if not str(target).lower().startswith(("iroh://", "iroh+blob://")):
            selected_name = selected_name or str(target)
            if backend_manager is None:
                raise ValueError(
                    "an Iroh mount target must be an iroh:// URL or a configured backend name"
                )
            config = backend_manager.get_backend_config(selected_name, redact=False)
            if not isinstance(config, Mapping) or config.get("type") != "iroh":
                raise ValueError(f"named backend is not a valid Iroh backend: {selected_name}")
            namespace = config.get("namespace")
            if not isinstance(namespace, Mapping) or not namespace.get("id"):
                raise ValueError(f"named Iroh backend has no namespace: {selected_name}")
            selected_target = f"iroh://{namespace['id']}/"
            configured_read_only = namespace.get("access") == "read-only"
            read_only = bool(read_only or configured_read_only)
            if filesystem is None:
                filesystem = backend_manager.get_backend_adapter(selected_name, **options)

        if filesystem is None:
            protocol = parse_iroh_path(selected_target).protocol
            filesystem = IrohFileSystem(protocol=protocol, read_only=read_only, **options)
        return cls(
            filesystem,
            selected_target,
            backend_name=selected_name,
            read_only=read_only,
        )

    @property
    def immutable(self) -> bool:
        return self.address.protocol == IROH_BLOB_PROTOCOL

    def resolve(self, relative_path: str = "") -> str:
        """Translate a relative path without permitting mount escape."""

        relative = _relative_path(relative_path)
        if self.address.is_blob:
            if relative:
                raise IrohInvalidPathError(
                    "an immutable Iroh blob mount has no children", operation="vfs.resolve"
                )
            return self.address.canonical_url
        base = self.address.path
        joined = posixpath.join(base, relative) if base and relative else (base or relative)
        resolved = IrohPath(
            IROH_PROTOCOL,
            namespace_id=self.address.namespace_id,
            path=joined,
        )
        return resolved.canonical_url

    def _require_writable(self) -> None:
        if self.read_only:
            raise IrohPermissionDeniedError(
                "Iroh VFS mount is read-only", operation="vfs.mutate"
            )

    def read_bytes(self, relative_path: str) -> bytes:
        return self.filesystem.cat_file(self.resolve(relative_path))

    def write_bytes(self, relative_path: str, value: bytes) -> dict[str, Any]:
        self._require_writable()
        path = self.resolve(relative_path)
        self.filesystem.pipe_file(path, value, mode="overwrite")
        self.invalidate(relative_path)
        return self.info(relative_path)

    def mkdir(self, relative_path: str, *, parents: bool = False) -> dict[str, Any]:
        self._require_writable()
        path = self.resolve(relative_path)
        self.filesystem.mkdir(path, create_parents=parents, exist_ok=parents)
        self.invalidate(relative_path)
        return self.info(relative_path)

    def remove(self, relative_path: str, *, recursive: bool = False) -> None:
        self._require_writable()
        self.filesystem.rm(self.resolve(relative_path), recursive=recursive)
        self.invalidate(relative_path)

    def info(self, relative_path: str) -> dict[str, Any]:
        info = dict(self.filesystem.info(self.resolve(relative_path)))
        info["namespace_id"] = self.address.namespace_id
        # Iroh hashes and IPFS CIDs are deliberately distinct domains.
        if info.get("blob_hash"):
            info["iroh_hash"] = info["blob_hash"]
        return info

    def exists(self, relative_path: str) -> bool:
        return bool(self.filesystem.exists(self.resolve(relative_path)))

    def list(self, relative_path: str) -> list[dict[str, Any]]:
        base = self.resolve(relative_path)
        result: list[dict[str, Any]] = []
        mount_base = self.address.path
        for raw_item in self.filesystem.ls(base, detail=True):
            item = dict(raw_item)
            parsed = parse_iroh_path(str(item["name"]))
            entry_path = parsed.path
            if mount_base:
                if entry_path == mount_base:
                    relative = ""
                elif entry_path.startswith(mount_base + "/"):
                    relative = entry_path[len(mount_base) + 1 :]
                else:
                    raise IrohInvalidPathError(
                        "Iroh listing escaped its VFS mount", operation="vfs.list"
                    )
            else:
                relative = entry_path
            item["vfs_relative_path"] = relative
            result.append(item)
        return result

    def invalidate(self, relative_path: str = "") -> None:
        # Iroh's range cache is content-hash keyed and therefore cannot return
        # stale bytes, but clearing it on VFS mutation also releases old ranges
        # promptly and gives callers deterministic invalidation behavior.
        del relative_path
        self.filesystem.clear_range_cache()

    def lineage(self, relative_path: str) -> dict[str, Any]:
        info = self.info(relative_path)
        result = {
            "backend": self.backend,
            "backend_name": self.backend_name,
            "namespace_id": self.address.namespace_id,
            "revision": info.get("revision"),
            "iroh_hash": info.get("iroh_hash"),
            "size": info.get("size"),
        }
        return {key: value for key, value in result.items() if value is not None}


__all__ = ["IrohVFSAdapter"]

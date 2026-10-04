"""Versioned directory manifests stored by the managed Iroh sidecar.

The selected compatibility bundle includes the durable ``iroh-docs`` store.
Consequently the sidecar is the namespace-head authority while this module
owns the portable JSON contract: validation, RFC 8785 canonicalization,
BLAKE3 hashing, optimistic compare-and-swap, legacy migration, and recovery.
No sidecar-private document or database representation crosses this boundary.
"""

from __future__ import annotations

import base64
import json
import math
import re
import unicodedata
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from blake3 import blake3

from .errors import (
    IrohConflictError,
    IrohIntegrityError,
    IrohInvalidManifestError,
    IrohInvalidPathError,
    IrohNotFoundError,
    IrohProtocolError,
    IrohUnsupportedVersionError,
)

MANIFEST_SCHEMA_VERSION = 1
MAX_REVISION = 2**63 - 1
MAX_ENTRIES = 1_000_000
MAX_PATH_BYTES = 4096
MAX_SEGMENT_BYTES = 255
MAX_METADATA_ITEMS = 64
MAX_METADATA_KEY_LENGTH = 64
MAX_METADATA_STRING_LENGTH = 4096

FILE_MODES = frozenset({0o400, 0o444, 0o600, 0o644})
DIRECTORY_MODES = frozenset({0o500, 0o555, 0o700, 0o755})
ENTRY_KINDS = frozenset({"file", "directory"})

_HEX_32_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.[0-9]+)?Z$"
)
_METADATA_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SECRET_METADATA_TERM_RE = re.compile(
    r"(?:^|[_.-])(?:secret|token|ticket|password|credential|private_key|node_key)(?:[_.-]|$)"
)


@runtime_checkable
class ManifestRuntimeClient(Protocol):
    """The sidecar client surface used by :class:`IrohManifestStore`."""

    async def request(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class ParentRevision:
    """Cryptographic link to the exact preceding manifest revision."""

    revision: int
    manifest_hash: str

    def __post_init__(self) -> None:
        _validate_uint(self.revision, "parent_revision.revision")
        _validate_hex_id(self.manifest_hash, "parent_revision.manifest_hash")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ParentRevision":
        if not isinstance(value, Mapping):
            raise IrohInvalidManifestError("parent_revision must be an object")
        _reject_unknown(value, {"revision", "manifest_hash"}, "parent_revision")
        return cls(
            _validate_uint(value.get("revision"), "parent_revision.revision"),
            _validate_hex_id(value.get("manifest_hash"), "parent_revision.manifest_hash"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"revision": self.revision, "manifest_hash": self.manifest_hash}


@dataclass(frozen=True, slots=True)
class ManifestPermissions:
    """Portable ACL attached to every immutable revision."""

    owner: str
    public_read: bool = False
    readers: tuple[str, ...] = ()
    writers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "readers", tuple(self.readers))
        object.__setattr__(self, "writers", tuple(self.writers))
        self.validated()

    @classmethod
    def owner_only(cls, owner: str, *, public_read: bool = False) -> "ManifestPermissions":
        return cls(owner=owner, public_read=public_read, writers=(owner,))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ManifestPermissions":
        if not isinstance(value, Mapping):
            raise IrohInvalidManifestError("permissions must be an object")
        _reject_unknown(value, {"owner", "public_read", "readers", "writers"}, "permissions")
        readers = value.get("readers")
        writers = value.get("writers")
        if not isinstance(readers, list) or not isinstance(writers, list):
            raise IrohInvalidManifestError("permission identities must be arrays")
        return cls(
            owner=value.get("owner"),
            public_read=value.get("public_read"),
            readers=tuple(readers),
            writers=tuple(writers),
        )

    def validated(self) -> "ManifestPermissions":
        _validate_hex_id(self.owner, "permissions.owner")
        if not isinstance(self.public_read, bool):
            raise IrohInvalidManifestError("permissions.public_read must be a boolean")
        if len(self.readers) > 4096 or not 1 <= len(self.writers) <= 256:
            raise IrohInvalidManifestError("permission identity list is outside its size limit")
        for identity in self.readers:
            _validate_hex_id(identity, "permissions.readers identity")
        for identity in self.writers:
            _validate_hex_id(identity, "permissions.writers identity")
        if len(set(self.readers)) != len(self.readers) or len(set(self.writers)) != len(
            self.writers
        ):
            raise IrohInvalidManifestError("permission identity arrays must not contain duplicates")
        if self.owner not in self.writers:
            raise IrohInvalidManifestError("permissions.owner must occur in permissions.writers")
        return self

    def to_dict(self) -> dict[str, Any]:
        self.validated()
        return {
            "owner": self.owner,
            "public_read": self.public_read,
            "readers": list(self.readers),
            "writers": list(self.writers),
        }


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """A normalized file, directory, or retained tombstone."""

    path: str
    kind: str
    tombstone: bool
    mode: int
    mtime: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    blob_hash: str | None = None
    size: int | None = None
    deleted_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        self.validated()

    @property
    def type(self) -> str:
        """Compatibility alias used by callers which spell kind as type."""

        return self.kind

    @property
    def is_live(self) -> bool:
        return not self.tombstone

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ManifestEntry":
        if not isinstance(value, Mapping):
            raise IrohInvalidManifestError("manifest entry must be an object")
        allowed = {
            "path",
            "kind",
            "tombstone",
            "blob_hash",
            "size",
            "mode",
            "mtime",
            "metadata",
            "deleted_at",
        }
        _reject_unknown(value, allowed, "manifest entry")
        metadata = value.get("metadata")
        if not isinstance(metadata, Mapping):
            raise IrohInvalidManifestError("entry metadata must be an object")
        return cls(
            path=value.get("path"),
            kind=value.get("kind"),
            tombstone=value.get("tombstone"),
            mode=value.get("mode"),
            mtime=value.get("mtime"),
            metadata=metadata,
            blob_hash=value.get("blob_hash"),
            size=value.get("size"),
            deleted_at=value.get("deleted_at"),
        )

    @classmethod
    def root(cls, *, mtime: str | None = None, mode: int = 0o755) -> "ManifestEntry":
        return cls("", "directory", False, mode, mtime or utc_now(), {})

    @classmethod
    def deleted(
        cls,
        path: str,
        kind: str,
        *,
        mode: int,
        mtime: str,
        deleted_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ManifestEntry":
        return cls(
            path,
            kind,
            True,
            mode,
            mtime,
            metadata or {},
            deleted_at=deleted_at or utc_now(),
        )

    def validated(self) -> "ManifestEntry":
        validate_manifest_path(self.path, allow_root=True)
        if self.kind not in ENTRY_KINDS:
            raise IrohInvalidManifestError("entry kind must be file or directory")
        if not isinstance(self.tombstone, bool):
            raise IrohInvalidManifestError("entry tombstone must be a boolean")
        allowed_modes = FILE_MODES if self.kind == "file" else DIRECTORY_MODES
        if isinstance(self.mode, bool) or self.mode not in allowed_modes:
            raise IrohInvalidManifestError("entry mode is invalid for its kind")
        _validate_timestamp(self.mtime, "entry.mtime")
        _validate_metadata(self.metadata)
        if self.tombstone:
            _validate_timestamp(self.deleted_at, "entry.deleted_at")
            if self.blob_hash is not None or self.size is not None:
                raise IrohInvalidManifestError("tombstone entries must not contain blob fields")
        elif self.deleted_at is not None:
            raise IrohInvalidManifestError("live entries must not contain deleted_at")
        elif self.kind == "file":
            _validate_hex_id(self.blob_hash, "entry.blob_hash")
            _validate_uint(self.size, "entry.size")
        elif self.blob_hash is not None or self.size is not None:
            raise IrohInvalidManifestError("directory entries must not contain blob fields")
        return self

    def to_dict(self) -> dict[str, Any]:
        self.validated()
        value: dict[str, Any] = {
            "path": self.path,
            "kind": self.kind,
            "tombstone": self.tombstone,
            "mode": self.mode,
            "mtime": self.mtime,
            "metadata": dict(self.metadata),
        }
        if self.tombstone:
            value["deleted_at"] = self.deleted_at
        elif self.kind == "file":
            value["blob_hash"] = self.blob_hash
            value["size"] = self.size
        return value


@dataclass(frozen=True, slots=True)
class DirectoryManifest:
    """One complete immutable namespace revision."""

    namespace_id: str
    revision: int
    parent_revision: ParentRevision | None
    created_at: str
    writer_id: str
    permissions: ManifestPermissions
    entries: tuple[ManifestEntry, ...]
    schema_version: int = MANIFEST_SCHEMA_VERSION
    schema_uri: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.parent_revision, Mapping):
            object.__setattr__(
                self, "parent_revision", ParentRevision.from_dict(self.parent_revision)
            )
        if isinstance(self.permissions, Mapping):
            object.__setattr__(self, "permissions", ManifestPermissions.from_dict(self.permissions))
        object.__setattr__(self, "entries", tuple(self.entries))
        self.validated()

    @property
    def author_id(self) -> str:
        """Compatibility alias for the contract's ``writer_id``."""

        return self.writer_id

    @classmethod
    def create(
        cls,
        namespace_id: str,
        writer_id: str,
        revision: int,
        entries: Iterable[ManifestEntry | Mapping[str, Any]],
        *,
        parent_revision: ParentRevision | Mapping[str, Any] | None = None,
        parent_manifest_hash: str | None = None,
        created_at: str | None = None,
        permissions: ManifestPermissions | Mapping[str, Any] | None = None,
        public_read: bool = False,
    ) -> "DirectoryManifest":
        timestamp = created_at or utc_now()
        normalized = [
            item if isinstance(item, ManifestEntry) else ManifestEntry.from_dict(item)
            for item in entries
        ]
        if not normalized and revision == 0:
            normalized.append(ManifestEntry.root(mtime=timestamp))
        if parent_revision is None and revision > 0 and parent_manifest_hash is not None:
            parent_revision = ParentRevision(revision - 1, parent_manifest_hash)
        elif isinstance(parent_revision, int) and not isinstance(parent_revision, bool):
            if parent_manifest_hash is None:
                raise IrohInvalidManifestError(
                    "parent_manifest_hash is required with an integer parent revision"
                )
            parent_revision = ParentRevision(parent_revision, parent_manifest_hash)
        if permissions is None:
            permissions = ManifestPermissions.owner_only(writer_id, public_read=public_read)
        elif isinstance(permissions, Mapping):
            permissions = ManifestPermissions.from_dict(permissions)
        return cls(
            namespace_id=namespace_id,
            revision=revision,
            parent_revision=parent_revision,
            created_at=timestamp,
            writer_id=writer_id,
            permissions=permissions,
            entries=tuple(sorted(normalized, key=lambda item: item.path.encode("utf-8"))),
        )

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, migrate_legacy: bool = True
    ) -> "DirectoryManifest":
        if not isinstance(value, Mapping):
            raise IrohInvalidManifestError("manifest must be an object")
        version = value.get("schema_version")
        if version != MANIFEST_SCHEMA_VERSION:
            if migrate_legacy and (version is None or version in (0, "0")):
                value = migrate_manifest(value)
            else:
                raise IrohUnsupportedVersionError("manifest schema version is unsupported")
        # A stale pre-contract implementation used schema_version 1 but a
        # different shape. Treat it as legacy only when its discriminator is
        # present; arbitrary malformed v1 documents still fail closed.
        elif migrate_legacy and value.get("kind") == "ipfs-kit-iroh-manifest":
            value = migrate_manifest(value)
        allowed = {
            "$schema",
            "schema_version",
            "namespace_id",
            "revision",
            "parent_revision",
            "created_at",
            "writer_id",
            "permissions",
            "entries",
        }
        _reject_unknown(value, allowed, "manifest")
        entries = value.get("entries")
        if not isinstance(entries, list):
            raise IrohInvalidManifestError("manifest entries must be an array")
        parent_value = value.get("parent_revision")
        parent = None if parent_value is None else ParentRevision.from_dict(parent_value)
        return cls(
            namespace_id=value.get("namespace_id"),
            revision=value.get("revision"),
            parent_revision=parent,
            created_at=value.get("created_at"),
            writer_id=value.get("writer_id"),
            permissions=ManifestPermissions.from_dict(value.get("permissions")),
            entries=tuple(ManifestEntry.from_dict(entry) for entry in entries),
            schema_version=value.get("schema_version"),
            schema_uri=value.get("$schema"),
        )

    @classmethod
    def from_json(
        cls, data: str | bytes | bytearray | memoryview, *, migrate_legacy: bool = True
    ) -> "DirectoryManifest":
        value = _loads_json(data)
        return cls.from_dict(value, migrate_legacy=migrate_legacy)

    def validated(self) -> "DirectoryManifest":
        if isinstance(self.schema_version, bool) or self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise IrohUnsupportedVersionError("manifest schema version is unsupported")
        _validate_hex_id(self.namespace_id, "namespace_id")
        _validate_uint(self.revision, "revision")
        _validate_timestamp(self.created_at, "created_at")
        _validate_hex_id(self.writer_id, "writer_id")
        self.permissions.validated()
        if (
            self.writer_id != self.permissions.owner
            and self.writer_id not in self.permissions.writers
        ):
            raise IrohInvalidManifestError("writer_id is not authorized by manifest permissions")
        if self.revision == 0:
            if self.parent_revision is not None:
                raise IrohInvalidManifestError("genesis parent_revision must be null")
        else:
            if self.parent_revision is None or self.parent_revision.revision != self.revision - 1:
                raise IrohInvalidManifestError("parent_revision must immediately precede revision")
            _validate_hex_id(self.parent_revision.manifest_hash, "parent_revision.manifest_hash")
        if self.schema_uri is not None and not isinstance(self.schema_uri, str):
            raise IrohInvalidManifestError("$schema must be a string")
        if not 1 <= len(self.entries) <= MAX_ENTRIES:
            raise IrohInvalidManifestError("manifest must contain between one and 1000000 entries")

        paths: dict[str, ManifestEntry] = {}
        ordered: list[bytes] = []
        for entry in self.entries:
            if not isinstance(entry, ManifestEntry):
                raise IrohInvalidManifestError("manifest entries must be ManifestEntry values")
            entry.validated()
            if entry.path in paths:
                raise IrohInvalidManifestError("manifest paths must be unique")
            paths[entry.path] = entry
            ordered.append(entry.path.encode("utf-8"))
        if ordered != sorted(ordered):
            raise IrohInvalidManifestError("manifest entries must be sorted by UTF-8 path bytes")
        root = paths.get("")
        if root is None or root.kind != "directory" or root.tombstone:
            raise IrohInvalidManifestError("manifest must contain exactly one live root directory")
        for path, entry in paths.items():
            if path == "":
                continue
            segments = path.split("/")
            # A file is never permitted to be an ancestor, including for a
            # retained tombstone below it. Live entries additionally require
            # every ancestor to be a live directory.
            for index in range(1, len(segments)):
                ancestor = paths.get("/".join(segments[:index]))
                if ancestor is not None and ancestor.kind == "file" and not ancestor.tombstone:
                    raise IrohInvalidManifestError("a live file is an ancestor of another entry")
                if not entry.tombstone and (
                    ancestor is None or ancestor.kind != "directory" or ancestor.tombstone
                ):
                    raise IrohInvalidManifestError("live entry has no live directory parent")
        return self

    def to_dict(self) -> dict[str, Any]:
        self.validated()
        value: dict[str, Any] = {
            "schema_version": self.schema_version,
            "namespace_id": self.namespace_id,
            "revision": self.revision,
            "parent_revision": (
                None if self.parent_revision is None else self.parent_revision.to_dict()
            ),
            "created_at": self.created_at,
            "writer_id": self.writer_id,
            "permissions": self.permissions.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
        }
        if self.schema_uri is not None:
            value["$schema"] = self.schema_uri
        return value

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    def to_json(self) -> str:
        return self.canonical_bytes().decode("utf-8")

    @property
    def manifest_hash(self) -> str:
        return blake3(self.canonical_bytes()).hexdigest()

    @property
    def hash(self) -> str:
        return self.manifest_hash


Manifest = DirectoryManifest


@dataclass(frozen=True, slots=True)
class ManifestHead:
    namespace_id: str
    revision: int
    manifest_hash: str

    def __post_init__(self) -> None:
        _validate_hex_id(self.namespace_id, "head.namespace_id")
        _validate_uint(self.revision, "head.revision")
        _validate_hex_id(self.manifest_hash, "head.manifest_hash")

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, namespace_id: str | None = None
    ) -> "ManifestHead":
        if not isinstance(value, Mapping):
            raise IrohProtocolError(
                "sidecar returned an invalid manifest head", operation="manifests.read"
            )
        try:
            actual_namespace = value.get("namespace_id", namespace_id)
            head = cls(
                _validate_hex_id(actual_namespace, "head.namespace_id"),
                _validate_uint(value.get("revision"), "head.revision"),
                _validate_hex_id(value.get("manifest_hash"), "head.manifest_hash"),
            )
            if namespace_id is not None and head.namespace_id != namespace_id:
                raise IrohIntegrityError(
                    "manifest head belongs to a different namespace",
                    operation="manifests.read",
                )
            return head
        except IrohInvalidManifestError as exc:
            raise IrohProtocolError(
                "sidecar returned an invalid manifest head", operation="manifests.read"
            ) from exc

    @property
    def token(self) -> tuple[int, str]:
        return self.revision, self.manifest_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace_id": self.namespace_id,
            "revision": self.revision,
            "manifest_hash": self.manifest_hash,
        }


@dataclass(frozen=True, slots=True)
class ManifestSnapshot:
    head: ManifestHead
    manifest: DirectoryManifest
    stale: bool = False


@dataclass(frozen=True, slots=True)
class RecoveryReceipt:
    namespace_id: str
    previous_head: ManifestHead | None
    recovered_head: ManifestHead
    candidates_examined: int
    valid_candidates: int
    dry_run: bool

    @property
    def changed(self) -> bool:
        return self.previous_head != self.recovered_head

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace_id": self.namespace_id,
            "previous_head": None if self.previous_head is None else self.previous_head.to_dict(),
            "recovered_head": self.recovered_head.to_dict(),
            "candidates_examined": self.candidates_examined,
            "valid_candidates": self.valid_candidates,
            "dry_run": self.dry_run,
            "changed": self.changed,
        }


class IrohManifestStore:
    """Strict manifest operations over protocol-1 sidecar RPC methods."""

    def __init__(self, client: ManifestRuntimeClient, *, timeout: float | None = None) -> None:
        if not isinstance(client, ManifestRuntimeClient):
            raise TypeError("client must provide an async request method")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive finite number")
        self.client = client
        self.timeout = None if timeout is None else float(timeout)

    async def _request(self, method: str, params: Mapping[str, Any]) -> Any:
        if self.timeout is None:
            return await self.client.request(method, params)
        return await self.client.request(method, params, timeout=self.timeout)

    async def create_namespace(
        self,
        namespace_id: str,
        writer_id: str,
        entries: Iterable[ManifestEntry | Mapping[str, Any]] = (),
        *,
        created_at: str | None = None,
        permissions: ManifestPermissions | Mapping[str, Any] | None = None,
        public_read: bool = False,
        operation_id: str | None = None,
    ) -> ManifestSnapshot:
        manifest = DirectoryManifest.create(
            namespace_id,
            writer_id,
            0,
            entries,
            created_at=created_at,
            permissions=permissions,
            public_read=public_read,
        )
        result = await self._request(
            "manifests.create",
            {
                "namespace_id": namespace_id,
                "manifest": manifest.to_dict(),
                "manifest_hash": manifest.manifest_hash,
                "operation_id": _operation_id(operation_id),
            },
        )
        return _parse_snapshot(result, expected_namespace=namespace_id, expected_manifest=manifest)

    async def open(self, namespace_id: str) -> ManifestHead:
        _validate_hex_id(namespace_id, "namespace_id")
        result = await self._request("manifests.open", {"namespace_id": namespace_id})
        obj = _require_mapping(result, "manifests.open")
        raw_head = obj.get("head", obj)
        return ManifestHead.from_dict(raw_head, namespace_id=namespace_id)

    async def read(
        self,
        namespace_id: str,
        *,
        revision: int | None = None,
        manifest_hash: str | None = None,
        migrate_legacy: bool = True,
    ) -> ManifestSnapshot:
        _validate_hex_id(namespace_id, "namespace_id")
        params: dict[str, Any] = {"namespace_id": namespace_id}
        if revision is not None:
            params["revision"] = _validate_uint(revision, "revision")
        if manifest_hash is not None:
            params["manifest_hash"] = _validate_hex_id(manifest_hash, "manifest_hash")
        result = await self._request("manifests.read", params)
        snapshot = _parse_snapshot(
            result, expected_namespace=namespace_id, migrate_legacy=migrate_legacy
        )
        if revision is not None and snapshot.head.revision != revision:
            raise IrohIntegrityError(
                "sidecar returned a different manifest revision", operation="manifests.read"
            )
        if manifest_hash is not None and snapshot.head.manifest_hash != manifest_hash:
            raise IrohIntegrityError(
                "sidecar returned a different manifest hash", operation="manifests.read"
            )
        return snapshot

    async def publish(
        self,
        manifest: DirectoryManifest | Mapping[str, Any],
        *,
        expected_head: ManifestHead | None = None,
        expected_revision: int | None = None,
        expected_manifest_hash: str | None = None,
        operation_id: str | None = None,
    ) -> ManifestSnapshot:
        value = validate_manifest(manifest)
        if expected_head is not None:
            if expected_revision is not None or expected_manifest_hash is not None:
                raise ValueError("expected_head cannot be combined with individual CAS fields")
            if expected_head.namespace_id != value.namespace_id:
                raise IrohInvalidManifestError("expected head belongs to a different namespace")
            expected_revision, expected_manifest_hash = expected_head.token
        if expected_revision is None or expected_manifest_hash is None:
            raise ValueError("publish requires an expected revision and manifest hash")
        expected_revision = _validate_uint(expected_revision, "expected_revision")
        expected_manifest_hash = _validate_hex_id(expected_manifest_hash, "expected_manifest_hash")
        expected_parent = ParentRevision(expected_revision, expected_manifest_hash)
        if value.revision != expected_revision + 1 or value.parent_revision != expected_parent:
            raise IrohInvalidManifestError(
                "published manifest does not cryptographically follow the expected head"
            )
        result = await self._request(
            "manifests.compare_and_swap",
            {
                "namespace_id": value.namespace_id,
                "expected_revision": expected_revision,
                "expected_manifest_hash": expected_manifest_hash,
                "manifest": value.to_dict(),
                "manifest_hash": value.manifest_hash,
                "operation_id": _operation_id(operation_id),
            },
        )
        return _parse_snapshot(
            result, expected_namespace=value.namespace_id, expected_manifest=value
        )

    async def update(
        self,
        namespace_id: str,
        writer_id: str,
        entries: Iterable[ManifestEntry | Mapping[str, Any]],
        *,
        expected_head: ManifestHead,
        created_at: str | None = None,
        permissions: ManifestPermissions | Mapping[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> ManifestSnapshot:
        if expected_head.revision >= MAX_REVISION:
            raise IrohConflictError("manifest revision cannot exceed signed 64-bit range")
        if permissions is None:
            # Preserve ACLs when the current verified snapshot is locally
            # available; otherwise callers must provide the intended ACL.
            current = await self.read(
                namespace_id,
                revision=expected_head.revision,
                manifest_hash=expected_head.manifest_hash,
            )
            permissions = current.manifest.permissions
        manifest = DirectoryManifest.create(
            namespace_id,
            writer_id,
            expected_head.revision + 1,
            entries,
            parent_revision=ParentRevision(*expected_head.token),
            created_at=created_at,
            permissions=permissions,
        )
        return await self.publish(manifest, expected_head=expected_head, operation_id=operation_id)

    async def history(
        self, namespace_id: str, *, limit: int | None = None
    ) -> tuple[ManifestHead, ...]:
        _validate_hex_id(namespace_id, "namespace_id")
        params: dict[str, Any] = {"namespace_id": namespace_id}
        if limit is not None:
            params["limit"] = _validate_uint(limit, "limit", minimum=1)
        result = await self._request("manifests.history", params)
        if isinstance(result, list):
            rows = result
        else:
            obj = _require_mapping(result, "manifests.history")
            rows = obj.get("heads", obj.get("history"))
        if not isinstance(rows, list):
            raise IrohProtocolError(
                "sidecar returned invalid manifest history", operation="manifests.history"
            )
        heads = tuple(ManifestHead.from_dict(row, namespace_id=namespace_id) for row in rows)
        if len({head.token for head in heads}) != len(heads):
            raise IrohIntegrityError(
                "manifest history contains duplicate heads", operation="manifests.history"
            )
        return heads

    async def recover_head(
        self, namespace_id: str, *, dry_run: bool = True, history_limit: int | None = None
    ) -> RecoveryReceipt:
        """Find the newest fully verified linear head and optionally restore it."""

        _validate_hex_id(namespace_id, "namespace_id")
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be a boolean")
        previous: ManifestHead | None
        try:
            previous = await self.open(namespace_id)
        except (IrohIntegrityError, IrohProtocolError, IrohNotFoundError):
            previous = None

        candidates = await self.history(namespace_id, limit=history_limit)
        snapshots: dict[tuple[int, str], ManifestSnapshot] = {}
        for candidate in candidates:
            try:
                snapshot = await self.read(
                    namespace_id,
                    revision=candidate.revision,
                    manifest_hash=candidate.manifest_hash,
                    migrate_legacy=False,
                )
            except (
                IrohIntegrityError,
                IrohInvalidManifestError,
                IrohUnsupportedVersionError,
                IrohProtocolError,
                IrohNotFoundError,
            ):
                continue
            snapshots[candidate.token] = snapshot

        valid: dict[tuple[int, str], ManifestHead] = {}
        for candidate in sorted(candidates, key=lambda item: (item.revision, item.manifest_hash)):
            snapshot = snapshots.get(candidate.token)
            if snapshot is None:
                continue
            parent = snapshot.manifest.parent_revision
            if candidate.revision == 0:
                valid[candidate.token] = candidate
            elif parent is not None and (parent.revision, parent.manifest_hash) in valid:
                valid[candidate.token] = candidate
        if not valid:
            raise IrohIntegrityError(
                "no verifiable manifest history is recoverable", operation="manifests.recover"
            )
        newest_revision = max(head.revision for head in valid.values())
        newest = [head for head in valid.values() if head.revision == newest_revision]
        if len(newest) != 1:
            raise IrohIntegrityError(
                "manifest history has multiple valid newest heads", operation="manifests.recover"
            )
        recovered = newest[0]

        if not dry_run and previous != recovered:
            params: dict[str, Any] = {
                "namespace_id": namespace_id,
                "expected_revision": None if previous is None else previous.revision,
                "expected_manifest_hash": None if previous is None else previous.manifest_hash,
                "recovery_head": {
                    "revision": recovered.revision,
                    "manifest_hash": recovered.manifest_hash,
                },
                "operation_id": str(uuid.uuid4()),
            }
            result = await self._request("manifests.compare_and_swap", params)
            obj = _require_mapping(result, "manifests.compare_and_swap")
            repaired = ManifestHead.from_dict(obj.get("head", obj), namespace_id=namespace_id)
            if repaired != recovered:
                raise IrohIntegrityError(
                    "sidecar repaired to an unexpected manifest head",
                    operation="manifests.recover",
                )
        return RecoveryReceipt(
            namespace_id=namespace_id,
            previous_head=previous,
            recovered_head=recovered,
            candidates_examined=len(candidates),
            valid_candidates=len(valid),
            dry_run=dry_run,
        )

    create = create_namespace
    get = read
    compare_and_swap = publish
    recover = recover_head


ManifestStore = IrohManifestStore


def validate_manifest(
    value: DirectoryManifest | Mapping[str, Any] | str | bytes | bytearray | memoryview,
    *,
    migrate_legacy: bool = True,
) -> DirectoryManifest:
    if isinstance(value, DirectoryManifest):
        return value.validated()
    if isinstance(value, (str, bytes, bytearray, memoryview)):
        return DirectoryManifest.from_json(value, migrate_legacy=migrate_legacy)
    return DirectoryManifest.from_dict(value, migrate_legacy=migrate_legacy)


def canonical_manifest_bytes(
    value: DirectoryManifest | Mapping[str, Any] | str | bytes | bytearray | memoryview,
) -> bytes:
    return validate_manifest(value).canonical_bytes()


def manifest_hash(
    value: DirectoryManifest | Mapping[str, Any] | str | bytes | bytearray | memoryview,
) -> str:
    return blake3(canonical_manifest_bytes(value)).hexdigest()


def canonical_json(value: Any) -> bytes:
    """Serialize JSON-compatible data using RFC 8785/JCS ordering and numbers."""

    return _canonical_json_text(value).encode("utf-8")


def migrate_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    """Convert the finite supported v0/pre-contract shapes into strict v1.

    Migration never invents a parent hash for a non-genesis revision. Such a
    link cannot be recovered safely from the document alone and must be
    supplied by an export containing ``parent_manifest_hash``.
    """

    if not isinstance(value, Mapping):
        raise IrohInvalidManifestError("legacy manifest must be an object")
    version = value.get("schema_version")
    if version == MANIFEST_SCHEMA_VERSION and value.get("kind") != "ipfs-kit-iroh-manifest":
        return DirectoryManifest.from_dict(value, migrate_legacy=False).to_dict()
    if version not in (None, 0, "0", MANIFEST_SCHEMA_VERSION):
        raise IrohUnsupportedVersionError("manifest schema version is unsupported")
    allowed = {
        "schema_version",
        "kind",
        "namespace_id",
        "namespace",
        "revision",
        "parent_revision",
        "parent",
        "parent_manifest_hash",
        "created_at",
        "mtime",
        "writer_id",
        "author_id",
        "author",
        "permissions",
        "entries",
        "files",
    }
    _reject_unknown(value, allowed, "legacy manifest")
    namespace_id = value.get("namespace_id", value.get("namespace"))
    writer_id = value.get("writer_id", value.get("author_id", value.get("author")))
    revision = _validate_uint(value.get("revision", 0), "revision")
    created_at = value.get("created_at", value.get("mtime"))
    _validate_timestamp(created_at, "created_at")
    _validate_hex_id(namespace_id, "namespace_id")
    _validate_hex_id(writer_id, "writer_id")

    raw_parent = value.get("parent_revision", value.get("parent"))
    parent: dict[str, Any] | None
    if revision == 0:
        if raw_parent not in (None, 0):
            raise IrohInvalidManifestError("legacy genesis manifest has a parent")
        parent = None
    elif isinstance(raw_parent, Mapping):
        parent = ParentRevision.from_dict(raw_parent).to_dict()
    else:
        parent_revision = revision - 1 if raw_parent is None else raw_parent
        _validate_uint(parent_revision, "parent_revision")
        parent_hash = value.get("parent_manifest_hash")
        if parent_hash is None:
            raise IrohInvalidManifestError(
                "legacy non-genesis manifest requires parent_manifest_hash"
            )
        parent = ParentRevision(
            parent_revision, _validate_hex_id(parent_hash, "parent_manifest_hash")
        ).to_dict()

    raw_permissions = value.get("permissions")
    permissions = (
        ManifestPermissions.owner_only(writer_id)
        if raw_permissions is None
        else ManifestPermissions.from_dict(raw_permissions)
    )
    raw_entries = value.get("entries", value.get("files", []))
    if not isinstance(raw_entries, list):
        raise IrohInvalidManifestError("legacy manifest entries must be an array")
    migrated_entries = [_migrate_entry(entry, created_at) for entry in raw_entries]
    if not any(entry["path"] == "" for entry in migrated_entries):
        migrated_entries.append(ManifestEntry.root(mtime=created_at).to_dict())
    result = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "namespace_id": namespace_id,
        "revision": revision,
        "parent_revision": parent,
        "created_at": created_at,
        "writer_id": writer_id,
        "permissions": permissions.to_dict(),
        "entries": sorted(migrated_entries, key=lambda item: item["path"].encode("utf-8")),
    }
    return DirectoryManifest.from_dict(result, migrate_legacy=False).to_dict()


def migrate_manifest_json(data: str | bytes | bytearray | memoryview) -> bytes:
    return canonical_manifest_bytes(migrate_manifest(_loads_json(data)))


def validate_manifest_path(path: str, *, allow_root: bool = True) -> str:
    if not isinstance(path, str):
        raise IrohInvalidPathError("manifest path must be a string")
    if path == "":
        if allow_root:
            return path
        raise IrohInvalidPathError("manifest path must not be empty")
    try:
        encoded = path.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise IrohInvalidPathError("manifest path is not valid UTF-8") from exc
    if len(encoded) > MAX_PATH_BYTES:
        raise IrohInvalidPathError("manifest path exceeds 4096 UTF-8 bytes")
    if unicodedata.normalize("NFC", path) != path:
        raise IrohInvalidPathError("manifest path must already be Unicode NFC")
    if path.startswith("/") or path.endswith("/") or "//" in path or "\\" in path:
        raise IrohInvalidPathError("manifest path is not a canonical relative path")
    for segment in path.split("/"):
        if segment in {"", ".", ".."}:
            raise IrohInvalidPathError("manifest path contains an invalid segment")
        if len(segment.encode("utf-8")) > MAX_SEGMENT_BYTES:
            raise IrohInvalidPathError("manifest path segment exceeds 255 UTF-8 bytes")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        raise IrohInvalidPathError("manifest path contains a control character")
    return path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_snapshot(
    value: Any,
    *,
    expected_namespace: str,
    expected_manifest: DirectoryManifest | None = None,
    migrate_legacy: bool = True,
) -> ManifestSnapshot:
    obj = _require_mapping(value, "manifests.read")
    raw_manifest: Any = obj.get("manifest", obj.get("manifest_json"))
    raw_bytes: bytes | None = None
    if raw_manifest is None and "manifest_bytes" in obj:
        encoded = obj["manifest_bytes"]
        if not isinstance(encoded, str):
            raise IrohProtocolError(
                "sidecar returned invalid manifest bytes", operation="manifests.read"
            )
        try:
            raw_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise IrohProtocolError(
                "sidecar returned invalid manifest bytes", operation="manifests.read"
            ) from exc
        manifest = DirectoryManifest.from_json(raw_bytes, migrate_legacy=migrate_legacy)
    elif isinstance(raw_manifest, Mapping):
        manifest = DirectoryManifest.from_dict(raw_manifest, migrate_legacy=migrate_legacy)
    elif isinstance(raw_manifest, (str, bytes, bytearray, memoryview)):
        raw_bytes = (
            raw_manifest.encode("utf-8") if isinstance(raw_manifest, str) else bytes(raw_manifest)
        )
        manifest = DirectoryManifest.from_json(raw_bytes, migrate_legacy=migrate_legacy)
    elif expected_manifest is not None:
        manifest = expected_manifest
    else:
        raise IrohProtocolError("sidecar returned no manifest", operation="manifests.read")
    if manifest.namespace_id != expected_namespace:
        raise IrohIntegrityError(
            "manifest belongs to a different namespace", operation="manifests.read"
        )
    raw_head = obj.get("head", obj)
    if not isinstance(raw_head, Mapping):
        raise IrohProtocolError("sidecar returned no manifest head", operation="manifests.read")
    head_value = dict(raw_head)
    head_value.setdefault("namespace_id", expected_namespace)
    head_value.setdefault("revision", manifest.revision)
    head_value.setdefault("manifest_hash", obj.get("manifest_hash"))
    head = ManifestHead.from_dict(head_value, namespace_id=expected_namespace)
    actual_hash = blake3(raw_bytes).hexdigest() if raw_bytes is not None else manifest.manifest_hash
    if head.revision != manifest.revision or head.manifest_hash != actual_hash:
        raise IrohIntegrityError(
            "manifest bytes do not match the published head",
            operation="manifests.read",
            metadata={
                "actual_revision": manifest.revision,
                "actual_manifest_hash": actual_hash,
            },
        )
    if (
        expected_manifest is not None
        and manifest.canonical_bytes() != expected_manifest.canonical_bytes()
    ):
        raise IrohIntegrityError(
            "sidecar published different manifest bytes",
            operation="manifests.compare_and_swap",
        )
    stale = obj.get("stale", False)
    if not isinstance(stale, bool):
        raise IrohProtocolError(
            "sidecar returned an invalid stale flag", operation="manifests.read"
        )
    return ManifestSnapshot(head=head, manifest=manifest, stale=stale)


def _migrate_entry(value: Any, default_timestamp: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise IrohInvalidManifestError("legacy manifest entry must be an object")
    allowed = {
        "path",
        "type",
        "kind",
        "prior_kind",
        "tombstone",
        "blob_hash",
        "hash",
        "prior_blob_hash",
        "size",
        "mode",
        "mtime",
        "modified_at",
        "metadata",
        "content_type",
        "deleted_at",
        "deleted_revision",
    }
    _reject_unknown(value, allowed, "legacy manifest entry")
    old_type = value.get("kind", value.get("type"))
    tombstone = value.get("tombstone", False) is True or old_type == "tombstone"
    kind = value.get("prior_kind") if old_type == "tombstone" else old_type
    if kind not in ENTRY_KINDS and old_type == "tombstone":
        kind = (
            "file" if value.get("prior_blob_hash", value.get("hash")) is not None else "directory"
        )
    if kind not in ENTRY_KINDS:
        raise IrohInvalidManifestError("legacy entry kind is unsupported")
    timestamp = value.get("mtime", value.get("modified_at", default_timestamp))
    metadata = value.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise IrohInvalidManifestError("legacy entry metadata must be an object")
    metadata = dict(metadata)
    if value.get("content_type") is not None:
        if "content_type" in metadata and metadata["content_type"] != value["content_type"]:
            raise IrohInvalidManifestError("legacy entry has conflicting content_type metadata")
        metadata["content_type"] = value["content_type"]
    mode = value.get("mode", 0o644 if kind == "file" else 0o755)
    result: dict[str, Any] = {
        "path": value.get("path"),
        "kind": kind,
        "tombstone": tombstone,
        "mode": mode,
        "mtime": timestamp,
        "metadata": metadata,
    }
    if tombstone:
        result["deleted_at"] = value.get("deleted_at", timestamp)
    elif kind == "file":
        result["blob_hash"] = value.get("blob_hash", value.get("hash"))
        result["size"] = value.get("size")
    return ManifestEntry.from_dict(result).to_dict()


def _validate_hex_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or _HEX_32_RE.fullmatch(value) is None:
        raise IrohInvalidManifestError(f"{name} must be 64 lowercase hexadecimal characters")
    return value


def _validate_uint(value: Any, name: str, *, minimum: int = 0) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= MAX_REVISION
    ):
        raise IrohInvalidManifestError(
            f"{name} must be an integer from {minimum} through {MAX_REVISION}"
        )
    return value


def _validate_timestamp(value: Any, name: str) -> str:
    if not isinstance(value, str) or _TIMESTAMP_RE.fullmatch(value) is None:
        raise IrohInvalidManifestError(f"{name} must be a UTC RFC 3339 timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise IrohInvalidManifestError(
            f"{name} must be a UTC RFC 3339 timestamp ending in Z"
        ) from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise IrohInvalidManifestError(f"{name} must be UTC")
    return value


def _validate_metadata(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or len(value) > MAX_METADATA_ITEMS:
        raise IrohInvalidManifestError("entry metadata must be an object with at most 64 items")
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or len(key) > MAX_METADATA_KEY_LENGTH
            or _METADATA_KEY_RE.fullmatch(key) is None
            or _SECRET_METADATA_TERM_RE.search(key) is not None
        ):
            raise IrohInvalidManifestError(
                "entry metadata contains an invalid or secret-bearing key"
            )
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, int):
            if not -(2**63) <= item <= MAX_REVISION:
                raise IrohInvalidManifestError(
                    "entry metadata integers must fit a signed 64-bit value"
                )
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise IrohInvalidManifestError("entry metadata numbers must be finite")
            continue
        if isinstance(item, str) and len(item) <= MAX_METADATA_STRING_LENGTH:
            continue
        raise IrohInvalidManifestError("entry metadata values must be bounded JSON scalars")


def _loads_json(data: str | bytes | bytearray | memoryview) -> Mapping[str, Any]:
    try:
        value = json.loads(
            data,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except IrohInvalidManifestError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise IrohInvalidManifestError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise IrohInvalidManifestError("manifest must be a JSON object")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IrohInvalidManifestError("manifest JSON contains duplicate object keys")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise IrohInvalidManifestError("manifest JSON contains a non-finite number")


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    if set(value) - allowed:
        raise IrohInvalidManifestError(f"{label} contains unknown properties")


def _require_mapping(value: Any, operation: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IrohProtocolError("sidecar manifest result must be an object", operation=operation)
    return value


def _operation_id(value: str | None) -> str:
    if value is None:
        return str(uuid.uuid4())
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValueError("operation_id must be a non-empty string of at most 255 characters")
    return value


def _canonical_json_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _canonical_float(value)
    if isinstance(value, str):
        # ensure_ascii=False produces the JCS escaping subset for valid Unicode.
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise IrohInvalidManifestError("manifest strings must be valid Unicode") from exc
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical_json_text(item) for item in value) + "]"
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise IrohInvalidManifestError("manifest object keys must be strings")
        keys = sorted(value, key=lambda key: key.encode("utf-16be", "surrogatepass"))
        return (
            "{"
            + ",".join(
                _canonical_json_text(key) + ":" + _canonical_json_text(value[key]) for key in keys
            )
            + "}"
        )
    raise IrohInvalidManifestError("manifest contains a non-JSON value")


def _canonical_float(value: float) -> str:
    if not math.isfinite(value):
        raise IrohInvalidManifestError("manifest numbers must be finite")
    if value == 0:
        return "0"
    negative = value < 0
    decimal = Decimal(repr(abs(value)))
    magnitude = abs(value)
    if 1e-6 <= magnitude < 1e21:
        result = format(decimal, "f")
        if "." in result:
            result = result.rstrip("0").rstrip(".")
    else:
        parts = decimal.as_tuple()
        digits = "".join(str(digit) for digit in parts.digits).rstrip("0") or "0"
        exponent = len(parts.digits) + parts.exponent - 1
        result = digits[0]
        if len(digits) > 1:
            result += "." + digits[1:]
        result += "e" + ("+" if exponent >= 0 else "") + str(exponent)
    return "-" + result if negative else result


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "MAX_REVISION",
    "FILE_MODES",
    "DIRECTORY_MODES",
    "ParentRevision",
    "ManifestPermissions",
    "ManifestEntry",
    "DirectoryManifest",
    "Manifest",
    "ManifestHead",
    "ManifestSnapshot",
    "RecoveryReceipt",
    "IrohManifestStore",
    "ManifestStore",
    "validate_manifest",
    "canonical_manifest_bytes",
    "manifest_hash",
    "canonical_json",
    "migrate_manifest",
    "migrate_manifest_json",
    "validate_manifest_path",
    "utc_now",
]

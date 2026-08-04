"""VFS versions and immutable snapshots (KITA-008).

``VFSVersion@1`` and ``VFSSnapshot@1`` make conditional version identities and
namespace snapshots explicit, content-addressed, and testable.

Properties:

* version records bind path, kind, content CID, generation, and optional parent
  version so CAS preconditions can reject stale writes;
* snapshots are frozen public namespace projections — never mutated after capture;
* equal namespace public records yield the same ``snapshot_cid`` (reproducible);
* version history is append-only and path-scoped with a hard bound.

No host filesystem, daemon, or network I/O is performed here. Snapshots may be
captured from an injected :class:`~ipfs_kit_py.core.vfs.service.VFSStorageBoundary`
or from already-public records.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.contracts import (
    VFSEntryKind,
    content_identity,
)
from ipfs_kit_py.core.vfs.service import (
    VFSStorageBoundary,
    VFSStoredEntry,
    content_cid_for_bytes,
    version_cid_for,
)

# ---------------------------------------------------------------------------
# Schema / bounds
# ---------------------------------------------------------------------------

SNAPSHOT_CONTRACT_VERSION: Final[int] = 1
SNAPSHOT_SCHEMA_MAJOR: Final[int] = 1
SNAPSHOT_SCHEMA_MINOR: Final[int] = 0
SNAPSHOT_SCHEMA_PATCH: Final[int] = 0
SNAPSHOT_SCHEMA_VERSION: Final[str] = (
    f"{SNAPSHOT_SCHEMA_MAJOR}.{SNAPSHOT_SCHEMA_MINOR}.{SNAPSHOT_SCHEMA_PATCH}"
)

VFS_SNAPSHOTS_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/snapshots"
VFS_VERSION_SCHEMA: Final[str] = f"{VFS_SNAPSHOTS_NAMESPACE}/version@{SNAPSHOT_SCHEMA_MAJOR}"
VFS_SNAPSHOT_SCHEMA: Final[str] = f"{VFS_SNAPSHOTS_NAMESPACE}/snapshot@{SNAPSHOT_SCHEMA_MAJOR}"
VFS_VERSION_HISTORY_SCHEMA: Final[str] = (
    f"{VFS_SNAPSHOTS_NAMESPACE}/version-history@{SNAPSHOT_SCHEMA_MAJOR}"
)

# Public interface aliases (plan: VFSVersion@1, VFSSnapshot@1).
VFSVersion_V1: Final[str] = VFS_VERSION_SCHEMA
VFSSnapshot_V1: Final[str] = VFS_SNAPSHOT_SCHEMA

MAX_SNAPSHOT_ENTRIES: Final[int] = 65_536
MAX_VERSION_HISTORY_PER_PATH: Final[int] = 4_096
MAX_SNAPSHOT_STORE: Final[int] = 1_024
MAX_IDENTIFIER_BYTES: Final[int] = 512


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VFSSnapshotError(ValueError):
    """Base class for snapshot / version contract failures."""


class VFSSnapshotImmutableError(VFSSnapshotError):
    """Raised when a caller attempts to mutate a frozen snapshot."""


class VFSVersionHistoryBoundError(VFSSnapshotError):
    """Raised when version history for a path exceeds its hard bound."""


class VFSSnapshotNotFoundError(VFSSnapshotError):
    """Raised when a snapshot id is unknown."""


class VFSSnapshotStoreBoundError(VFSSnapshotError):
    """Raised when the snapshot store exceeds its hard bound."""


# ---------------------------------------------------------------------------
# Version records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSVersion:
    """One content-addressed version of a namespace entry (``VFSVersion@1``).

    ``version_cid`` is the authoritative identity used by CAS preconditions.
    When constructed with an empty ``version_cid``, it is derived deterministically
    from path/kind/content_cid/generation/target (same function as the service).
    """

    SCHEMA: ClassVar[str] = VFS_VERSION_SCHEMA

    path: str
    kind: VFSEntryKind
    content_cid: str
    generation: int
    version_cid: str = ""
    parent_version_cid: str = ""
    target: str = ""
    mount_id: str = ""
    mtime_unix_ms: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, VFSEntryKind):
            object.__setattr__(self, "kind", VFSEntryKind(self.kind))
        if not isinstance(self.path, str):
            raise TypeError("path must be str")
        if not isinstance(self.generation, int) or self.generation < 0:
            raise VFSSnapshotError("generation must be a non-negative int")
        if not self.version_cid:
            object.__setattr__(
                self,
                "version_cid",
                version_cid_for(
                    self.path,
                    kind=self.kind,
                    content_cid=self.content_cid,
                    generation=self.generation,
                    target=self.target,
                ),
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path": self.path,
            "kind": self.kind.value,
            "content_cid": self.content_cid,
            "generation": self.generation,
            "version_cid": self.version_cid,
            "parent_version_cid": self.parent_version_cid,
            "target": self.target,
            "mount_id": self.mount_id,
            "mtime_unix_ms": self.mtime_unix_ms,
        }

    @classmethod
    def from_stored(
        cls,
        path: str,
        entry: VFSStoredEntry,
        *,
        generation: int | None = None,
        parent_version_cid: str = "",
    ) -> VFSVersion:
        """Build a version record from a stored entry."""

        gen = generation if generation is not None else 0
        return cls(
            path=path,
            kind=entry.kind,
            content_cid=entry.content_cid,
            generation=gen,
            version_cid=entry.version_cid,
            parent_version_cid=parent_version_cid,
            target=entry.target,
            mount_id=entry.mount_id,
            mtime_unix_ms=entry.mtime_unix_ms,
        )

    @classmethod
    def from_public_record(
        cls,
        path: str,
        record: Mapping[str, Any],
        *,
        generation: int | None = None,
        parent_version_cid: str = "",
    ) -> VFSVersion:
        """Build a version from a public storage snapshot record."""

        kind_raw = record.get("kind", VFSEntryKind.UNKNOWN.value)
        kind = kind_raw if isinstance(kind_raw, VFSEntryKind) else VFSEntryKind(str(kind_raw))
        gen = generation if generation is not None else int(record.get("mtime_unix_ms") or 0)
        return cls(
            path=path,
            kind=kind,
            content_cid=str(record.get("content_cid") or ""),
            generation=gen,
            version_cid=str(record.get("version_cid") or ""),
            parent_version_cid=parent_version_cid,
            target=str(record.get("target") or ""),
            mount_id=str(record.get("mount_id") or ""),
            mtime_unix_ms=int(record.get("mtime_unix_ms") or 0),
        )


def check_version_precondition(
    *,
    current_version_cid: str,
    expected_version_cid: str,
    path: str = "",
) -> None:
    """Reject a write when the caller's version precondition is stale.

    Raises:
        VFSVersionPreconditionError: when CIDs differ (including missing current).
    """

    if current_version_cid != expected_version_cid:
        raise VFSVersionPreconditionError(
            "precondition version mismatch",
            path=path,
            current_version_cid=current_version_cid,
            expected_version_cid=expected_version_cid,
        )


class VFSVersionPreconditionError(VFSSnapshotError):
    """CAS / version precondition failed (stale write)."""

    def __init__(
        self,
        message: str,
        *,
        path: str = "",
        current_version_cid: str = "",
        expected_version_cid: str = "",
    ) -> None:
        super().__init__(message)
        self.path = path
        self.current_version_cid = current_version_cid
        self.expected_version_cid = expected_version_cid


# ---------------------------------------------------------------------------
# Immutable snapshots
# ---------------------------------------------------------------------------


def _freeze_public_entries(
    entries: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Deep-copy and sort public entry records for immutability."""

    if len(entries) > MAX_SNAPSHOT_ENTRIES:
        raise VFSSnapshotError(
            f"snapshot exceeds MAX_SNAPSHOT_ENTRIES ({MAX_SNAPSHOT_ENTRIES})"
        )
    frozen: dict[str, dict[str, Any]] = {}
    for path in sorted(entries):
        rec = entries[path]
        if not isinstance(rec, Mapping):
            raise TypeError(f"entry for {path!r} must be a mapping")
        # Only public, content-addressable fields (no raw bodies).
        frozen[path] = {
            "kind": str(rec.get("kind", "")),
            "size_bytes": int(rec.get("size_bytes") or 0),
            "content_cid": str(rec.get("content_cid") or ""),
            "version_cid": str(rec.get("version_cid") or ""),
            "target": str(rec.get("target") or ""),
            "mtime_unix_ms": int(rec.get("mtime_unix_ms") or 0),
            "mode": int(rec.get("mode") or 0),
            "mount_id": str(rec.get("mount_id") or ""),
            "is_readonly": bool(rec.get("is_readonly", False)),
        }
    return frozen


def snapshot_cid_for(
    entries: Mapping[str, Mapping[str, Any]],
    *,
    generation: int = 0,
    namespace_id: str = "",
) -> str:
    """Deterministic content identity for a public namespace projection."""

    payload = {
        "schema": VFS_SNAPSHOT_SCHEMA,
        "generation": generation,
        "namespace_id": namespace_id,
        "entries": _freeze_public_entries(entries),
    }
    return content_identity(payload)


@dataclass(frozen=True)
class VFSSnapshot:
    """Immutable, reproducible namespace snapshot (``VFSSnapshot@1``).

    Instances are frozen: ``entries`` is a nested tuple of sorted items so
    callers cannot mutate the captured state. Equal inputs always produce the
    same ``snapshot_cid``.
    """

    SCHEMA: ClassVar[str] = VFS_SNAPSHOT_SCHEMA

    snapshot_id: str
    generation: int
    snapshot_cid: str
    entries: tuple[tuple[str, tuple[tuple[str, Any], ...]], ...] = ()
    namespace_id: str = ""
    captured_at_unix_ms: int = 0
    source_label: str = ""

    def __post_init__(self) -> None:
        if not self.snapshot_id or not isinstance(self.snapshot_id, str):
            raise VFSSnapshotError("snapshot_id is required")
        if len(self.snapshot_id) > MAX_IDENTIFIER_BYTES:
            raise VFSSnapshotError("snapshot_id exceeds bound")
        if self.generation < 0:
            raise VFSSnapshotError("generation must be non-negative")
        if not self.snapshot_cid:
            object.__setattr__(
                self,
                "snapshot_cid",
                snapshot_cid_for(
                    self.as_mapping(),
                    generation=self.generation,
                    namespace_id=self.namespace_id,
                ),
            )

    def as_mapping(self) -> dict[str, dict[str, Any]]:
        """Return a defensive deep copy of public entries."""

        out: dict[str, dict[str, Any]] = {}
        for path, pairs in self.entries:
            out[path] = {k: v for k, v in pairs}
        return out

    def entry(self, path: str) -> dict[str, Any] | None:
        """Look up one path without exposing a mutable view of the whole map."""

        for p, pairs in self.entries:
            if p == path:
                return {k: v for k, v in pairs}
        return None

    def paths(self) -> tuple[str, ...]:
        return tuple(p for p, _ in self.entries)

    def version_cid_at(self, path: str) -> str:
        rec = self.entry(path)
        if rec is None:
            return ""
        return str(rec.get("version_cid") or "")

    def content_cid_at(self, path: str) -> str:
        rec = self.entry(path)
        if rec is None:
            return ""
        return str(rec.get("content_cid") or "")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "snapshot_id": self.snapshot_id,
            "generation": self.generation,
            "snapshot_cid": self.snapshot_cid,
            "namespace_id": self.namespace_id,
            "captured_at_unix_ms": self.captured_at_unix_ms,
            "source_label": self.source_label,
            "entry_count": len(self.entries),
            "entries": self.as_mapping(),
        }

    def with_mutated_entries(self, *_args: Any, **_kwargs: Any) -> None:
        """Explicitly forbidden — snapshots are immutable."""

        raise VFSSnapshotImmutableError(
            "VFSSnapshot is immutable; capture a new snapshot instead"
        )

    @classmethod
    def capture(
        cls,
        storage: VFSStorageBoundary,
        *,
        snapshot_id: str,
        namespace_id: str = "",
        captured_at_unix_ms: int = 0,
        source_label: str = "",
    ) -> VFSSnapshot:
        """Capture an immutable snapshot from an injected storage boundary."""

        public = storage.snapshot()
        return cls.from_public_records(
            public,
            snapshot_id=snapshot_id,
            generation=storage.generation,
            namespace_id=namespace_id,
            captured_at_unix_ms=captured_at_unix_ms,
            source_label=source_label,
        )

    @classmethod
    def from_public_records(
        cls,
        entries: Mapping[str, Mapping[str, Any]],
        *,
        snapshot_id: str,
        generation: int = 0,
        namespace_id: str = "",
        captured_at_unix_ms: int = 0,
        source_label: str = "",
    ) -> VFSSnapshot:
        """Build a snapshot from public records (reproducible CID)."""

        frozen_map = _freeze_public_entries(entries)
        cid = snapshot_cid_for(
            frozen_map, generation=generation, namespace_id=namespace_id
        )
        return cls(
            snapshot_id=snapshot_id,
            generation=generation,
            snapshot_cid=cid,
            entries=_mapping_to_frozen_entries(frozen_map),
            namespace_id=namespace_id,
            captured_at_unix_ms=captured_at_unix_ms,
            source_label=source_label,
        )


def _mapping_to_frozen_entries(
    entries: Mapping[str, Mapping[str, Any]],
) -> tuple[tuple[str, tuple[tuple[str, Any], ...]], ...]:
    items: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
    for path in sorted(entries):
        rec = entries[path]
        pairs = tuple(sorted((str(k), rec[k]) for k in rec))
        items.append((path, pairs))
    return tuple(items)


# ---------------------------------------------------------------------------
# Version history (append-only, path-scoped)
# ---------------------------------------------------------------------------


@dataclass
class VFSVersionHistory:
    """Append-only per-path version chain with a hard bound."""

    SCHEMA: ClassVar[str] = VFS_VERSION_HISTORY_SCHEMA

    _by_path: dict[str, list[VFSVersion]] = field(default_factory=dict)
    max_per_path: int = MAX_VERSION_HISTORY_PER_PATH

    def record(self, version: VFSVersion) -> None:
        chain = self._by_path.setdefault(version.path, [])
        if len(chain) >= self.max_per_path:
            raise VFSVersionHistoryBoundError(
                f"version history for {version.path!r} exceeds bound "
                f"({self.max_per_path})"
            )
        # Link parent when not set and chain non-empty.
        if not version.parent_version_cid and chain:
            version = VFSVersion(
                path=version.path,
                kind=version.kind,
                content_cid=version.content_cid,
                generation=version.generation,
                version_cid=version.version_cid,
                parent_version_cid=chain[-1].version_cid,
                target=version.target,
                mount_id=version.mount_id,
                mtime_unix_ms=version.mtime_unix_ms,
            )
        chain.append(version)

    def chain(self, path: str) -> tuple[VFSVersion, ...]:
        return tuple(self._by_path.get(path, ()))

    def head(self, path: str) -> VFSVersion | None:
        chain = self._by_path.get(path)
        if not chain:
            return None
        return chain[-1]

    def contains_version(self, path: str, version_cid: str) -> bool:
        return any(v.version_cid == version_cid for v in self._by_path.get(path, ()))

    def paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_path))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "paths": {
                path: [v.to_record() for v in chain]
                for path, chain in sorted(self._by_path.items())
            },
        }


# ---------------------------------------------------------------------------
# Snapshot store (immutable once put)
# ---------------------------------------------------------------------------


class VFSSnapshotStore:
    """Bounded registry of immutable snapshots keyed by snapshot_id."""

    def __init__(self, *, max_snapshots: int = MAX_SNAPSHOT_STORE) -> None:
        self._by_id: dict[str, VFSSnapshot] = {}
        self._by_cid: dict[str, list[str]] = {}
        self._max = max_snapshots
        self._seq = 0

    def __len__(self) -> int:
        return len(self._by_id)

    def put(self, snapshot: VFSSnapshot) -> VFSSnapshot:
        """Insert a snapshot. Re-put of an identical id/cid is a no-op; mutation fails."""

        existing = self._by_id.get(snapshot.snapshot_id)
        if existing is not None:
            if existing.snapshot_cid != snapshot.snapshot_cid:
                raise VFSSnapshotImmutableError(
                    f"snapshot {snapshot.snapshot_id!r} already frozen with a "
                    f"different identity"
                )
            return existing
        if len(self._by_id) >= self._max:
            raise VFSSnapshotStoreBoundError(
                f"snapshot store exceeds MAX_SNAPSHOT_STORE ({self._max})"
            )
        self._by_id[snapshot.snapshot_id] = snapshot
        self._by_cid.setdefault(snapshot.snapshot_cid, []).append(snapshot.snapshot_id)
        return snapshot

    def get(self, snapshot_id: str) -> VFSSnapshot:
        try:
            return self._by_id[snapshot_id]
        except KeyError as exc:
            raise VFSSnapshotNotFoundError(
                f"unknown snapshot_id: {snapshot_id}"
            ) from exc

    def get_by_cid(self, snapshot_cid: str) -> tuple[VFSSnapshot, ...]:
        ids = self._by_cid.get(snapshot_cid, [])
        return tuple(self._by_id[i] for i in ids)

    def capture_from_storage(
        self,
        storage: VFSStorageBoundary,
        *,
        snapshot_id: str | None = None,
        namespace_id: str = "",
        captured_at_unix_ms: int = 0,
        source_label: str = "",
    ) -> VFSSnapshot:
        """Capture, freeze, and store a snapshot from storage."""

        self._seq += 1
        sid = snapshot_id or f"snap:{self._seq}"
        snap = VFSSnapshot.capture(
            storage,
            snapshot_id=sid,
            namespace_id=namespace_id,
            captured_at_unix_ms=captured_at_unix_ms,
            source_label=source_label,
        )
        return self.put(snap)

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SnapshotDisposition(str, Enum):
    """How a snapshot relates to live storage after capture."""

    LIVE_PINNED = "live_pinned"
    """Snapshot identity is independent of later live mutations."""

    DETACHED = "detached"
    """Snapshot is a fully detached immutable copy."""


def versions_equal(a: VFSVersion, b: VFSVersion) -> bool:
    return a.version_cid == b.version_cid and a.path == b.path


def empty_root_public_record() -> dict[str, Any]:
    """Public record for an empty namespace root (deterministic)."""

    cid = content_cid_for_bytes(b"")
    return {
        "kind": VFSEntryKind.DIRECTORY.value,
        "size_bytes": 0,
        "content_cid": cid,
        "version_cid": version_cid_for(
            "", kind=VFSEntryKind.DIRECTORY, content_cid="", generation=0
        ),
        "target": "",
        "mtime_unix_ms": 0,
        "mode": 0,
        "mount_id": "mount:default",
        "is_readonly": False,
    }


__all__ = [
    "SNAPSHOT_CONTRACT_VERSION",
    "SNAPSHOT_SCHEMA_VERSION",
    "VFS_VERSION_SCHEMA",
    "VFS_SNAPSHOT_SCHEMA",
    "VFS_VERSION_HISTORY_SCHEMA",
    "VFSVersion_V1",
    "VFSSnapshot_V1",
    "MAX_SNAPSHOT_ENTRIES",
    "MAX_VERSION_HISTORY_PER_PATH",
    "MAX_SNAPSHOT_STORE",
    "VFSSnapshotError",
    "VFSSnapshotImmutableError",
    "VFSVersionHistoryBoundError",
    "VFSSnapshotNotFoundError",
    "VFSSnapshotStoreBoundError",
    "VFSVersionPreconditionError",
    "VFSVersion",
    "VFSSnapshot",
    "VFSVersionHistory",
    "VFSSnapshotStore",
    "SnapshotDisposition",
    "check_version_precondition",
    "snapshot_cid_for",
    "versions_equal",
    "empty_root_public_record",
]

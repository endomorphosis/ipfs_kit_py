"""Namespace routing, mount table, stable inode identity, and path policy (KVFS-202).

This module owns the kernel-facing *namespace plane* for the common VFS runtime:

* deterministic longest-prefix mount resolution over a closed mount table;
* typed rejection of unknown-mount and cross-mount mutations;
* stable inode identity that survives process restart and same-mount rename;
* executable policy traces for root confinement, Unicode NFC, symlink
  disposition, directory pagination, and case-sensitivity.

Metadata projection (mode, uid/gid, times, statfs) remains KVFS-201. This
module does not import fusepy, open host mounts, or perform network I/O.

Interfaces (plan aliases): ``NamespaceRouter@1``, ``MountTable@1``,
``StableInodeTable@1``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.contracts import (
    MAX_LISTING_PAGE_SIZE,
    MAX_PATH_BYTES,
    MAX_SAFE_INTEGER,
    AtomicBoundary,
    AtomicityDisposition,
    ListingOrder,
    NormalizedPath,
    SymlinkDecision,
    UnicodePolicy,
    UnsupportedReason,
    VFSDirEntry,
    VFSEntryKind,
    VFSListing,
    VFSMount,
    VFSPathError,
    VFSPathPolicy,
    VFSPathRejectReason,
    VFSUnsupportedError,
    assert_atomic_boundary_supported,
    classify_mount_pair,
    confine_path,
    content_identity,
    evaluate_symlink,
    normalize_vfs_path,
    path_is_within_root,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

NAMESPACE_MODULE_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/namespace"

MOUNT_TABLE_SCHEMA: Final[str] = f"{NAMESPACE_MODULE_NAMESPACE}/mount-table@{SCHEMA_MAJOR}"
STABLE_INODE_TABLE_SCHEMA: Final[str] = (
    f"{NAMESPACE_MODULE_NAMESPACE}/stable-inode-table@{SCHEMA_MAJOR}"
)
NAMESPACE_ROUTER_SCHEMA: Final[str] = (
    f"{NAMESPACE_MODULE_NAMESPACE}/namespace-router@{SCHEMA_MAJOR}"
)
MOUNT_RESOLUTION_SCHEMA: Final[str] = (
    f"{NAMESPACE_MODULE_NAMESPACE}/mount-resolution@{SCHEMA_MAJOR}"
)
STABLE_INODE_SCHEMA: Final[str] = f"{NAMESPACE_MODULE_NAMESPACE}/stable-inode@{SCHEMA_MAJOR}"
NAMESPACE_TRACE_SCHEMA: Final[str] = (
    f"{NAMESPACE_MODULE_NAMESPACE}/namespace-trace@{SCHEMA_MAJOR}"
)

# Public interface aliases.
MountTable_V1: Final[str] = MOUNT_TABLE_SCHEMA
StableInodeTable_V1: Final[str] = STABLE_INODE_TABLE_SCHEMA
NamespaceRouter_V1: Final[str] = NAMESPACE_ROUTER_SCHEMA

# FUSE-style root inode is reserved as 1.
ROOT_INODE: Final[int] = 1
MIN_ALLOCATED_INODE: Final[int] = 2
MAX_INODE: Final[int] = MAX_SAFE_INTEGER
MAX_MOUNTS: Final[int] = 4_096
MAX_INODES: Final[int] = 1_048_576
MAX_TRACE_STEPS: Final[int] = 4_096
DEFAULT_PAGE_SIZE: Final[int] = 256
DEFAULT_MOUNT_ID: Final[str] = "mount:default"
DEFAULT_NAMESPACE_ID: Final[str] = "ns:default"
DEFAULT_BACKEND_ID: Final[str] = "backend:memory"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NamespaceErrorCode(str, Enum):
    """Stable namespace-plane error codes."""

    UNKNOWN_MOUNT = "NS_UNKNOWN_MOUNT"
    MOUNT_CONFLICT = "NS_MOUNT_CONFLICT"
    MOUNT_NOT_FOUND = "NS_MOUNT_NOT_FOUND"
    CROSS_MOUNT = "NS_CROSS_MOUNT"
    READ_ONLY_MOUNT = "NS_READ_ONLY_MOUNT"
    PATH_POLICY = "NS_PATH_POLICY"
    INODE_NOT_FOUND = "NS_INODE_NOT_FOUND"
    INODE_CONFLICT = "NS_INODE_CONFLICT"
    INODE_EXHAUSTED = "NS_INODE_EXHAUSTED"
    CASE_POLICY = "NS_CASE_POLICY"
    UNICODE_POLICY = "NS_UNICODE_POLICY"
    SYMLINK_POLICY = "NS_SYMLINK_POLICY"
    PAGINATION = "NS_PAGINATION"
    INVALID_CHECKPOINT = "NS_INVALID_CHECKPOINT"
    INTERNAL = "NS_INTERNAL"


class NamespaceError(ValueError):
    """Fail-closed namespace routing / inode / policy error."""

    def __init__(
        self,
        message: str,
        *,
        code: NamespaceErrorCode,
        path: str = "",
        mount_id: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code if isinstance(code, NamespaceErrorCode) else NamespaceErrorCode(code)
        self.path = path
        self.mount_id = mount_id
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": str(self),
            "path": self.path,
            "mount_id": self.mount_id,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Trace steps (executable evidence)
# ---------------------------------------------------------------------------


class NamespaceTraceKind(str, Enum):
    """Closed vocabulary for namespace policy / routing traces."""

    NORMALIZE = "normalize"
    CONFINE = "confine"
    RESOLVE_MOUNT = "resolve_mount"
    ALLOCATE_INODE = "allocate_inode"
    LOOKUP_INODE = "lookup_inode"
    RENAME_INODE = "rename_inode"
    ADMIT_MUTATION = "admit_mutation"
    REJECT = "reject"
    SYMLINK = "symlink"
    UNICODE = "unicode"
    CASE = "case"
    PAGINATE = "paginate"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    OBSERVATION = "observation"


@dataclass(frozen=True)
class NamespaceTraceStep:
    """One immutable, executable trace step."""

    SCHEMA: ClassVar[str] = NAMESPACE_TRACE_SCHEMA

    kind: NamespaceTraceKind
    success: bool
    path: str = ""
    mount_id: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, NamespaceTraceKind):
            object.__setattr__(self, "kind", NamespaceTraceKind(self.kind))
        if not isinstance(self.success, bool):
            raise NamespaceError(
                "trace step success must be a boolean",
                code=NamespaceErrorCode.INTERNAL,
            )
        if not isinstance(self.detail, Mapping):
            raise NamespaceError(
                "trace step detail must be a mapping",
                code=NamespaceErrorCode.INTERNAL,
            )
        object.__setattr__(self, "detail", dict(self.detail))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "success": self.success,
            "path": self.path,
            "mount_id": self.mount_id,
            "code": self.code,
            "detail": dict(self.detail),
        }


class NamespaceTraceLog:
    """Bounded append-only trace log for policy and routing evidence."""

    __slots__ = ("_steps", "_max_steps")

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        if max_steps < 1 or max_steps > MAX_TRACE_STEPS:
            raise NamespaceError(
                f"max_steps must be in [1, {MAX_TRACE_STEPS}]",
                code=NamespaceErrorCode.INTERNAL,
            )
        self._steps: list[NamespaceTraceStep] = []
        self._max_steps = max_steps

    def append(self, step: NamespaceTraceStep) -> NamespaceTraceStep:
        if len(self._steps) >= self._max_steps:
            raise NamespaceError(
                f"trace exceeds MAX_TRACE_STEPS ({self._max_steps})",
                code=NamespaceErrorCode.INTERNAL,
            )
        self._steps.append(step)
        return step

    def record(
        self,
        kind: NamespaceTraceKind,
        *,
        success: bool,
        path: str = "",
        mount_id: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> NamespaceTraceStep:
        return self.append(
            NamespaceTraceStep(
                kind=kind,
                success=success,
                path=path,
                mount_id=mount_id,
                code=code,
                detail=dict(detail or {}),
            )
        )

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> tuple[NamespaceTraceStep, ...]:
        return tuple(self._steps)

    def to_records(self) -> list[dict[str, Any]]:
        return [step.to_record() for step in self._steps]

    def kinds(self) -> list[str]:
        return [step.kind.value for step in self._steps]


# ---------------------------------------------------------------------------
# Mount resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MountResolution:
    """Result of longest-prefix mount resolution for one path."""

    SCHEMA: ClassVar[str] = MOUNT_RESOLUTION_SCHEMA

    mount: VFSMount
    absolute_path: str
    """Normalized namespace path (no leading slash)."""

    relative_path: str
    """Path relative to the matched mount_path (empty at the mount root)."""

    matched_prefix: str
    """The mount_path that won longest-prefix selection."""

    def __post_init__(self) -> None:
        if not isinstance(self.mount, VFSMount):
            raise NamespaceError(
                "mount must be a VFSMount",
                code=NamespaceErrorCode.INTERNAL,
            )
        for name in ("absolute_path", "relative_path", "matched_prefix"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise NamespaceError(
                    f"{name} must be a string",
                    code=NamespaceErrorCode.INTERNAL,
                )
            if len(value.encode("utf-8")) > MAX_PATH_BYTES:
                raise NamespaceError(
                    f"{name} exceeds path bound",
                    code=NamespaceErrorCode.PATH_POLICY,
                    path=value,
                )

    @property
    def mount_id(self) -> str:
        return self.mount.mount_id

    @property
    def read_only(self) -> bool:
        return self.mount.read_only

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "mount_id": self.mount.mount_id,
            "mount_path": self.mount.mount_path,
            "backend_id": self.mount.backend_id,
            "namespace_id": self.mount.namespace_id,
            "read_only": self.mount.read_only,
            "absolute_path": self.absolute_path,
            "relative_path": self.relative_path,
            "matched_prefix": self.matched_prefix,
        }


def _relative_to_prefix(absolute: str, prefix: str) -> str:
    if prefix == "":
        return absolute
    if absolute == prefix:
        return ""
    if absolute.startswith(prefix + "/"):
        return absolute[len(prefix) + 1 :]
    raise NamespaceError(
        "path is not under mount prefix",
        code=NamespaceErrorCode.MOUNT_NOT_FOUND,
        path=absolute,
        detail={"prefix": prefix},
    )


def _mount_prefix_key(mount: VFSMount) -> tuple[int, str, str]:
    """Sort key: longer prefix first, then mount_path, then mount_id."""

    return (-len(mount.mount_path), mount.mount_path, mount.mount_id)


class MountTable:
    """Closed, deterministic mount table with longest-prefix resolution.

    Resolution algorithm (fail-closed, deterministic):

    1. Normalize the input path under the table path policy.
    2. Collect every mount whose ``mount_path`` is a prefix of the path
       (including the empty root mount when present).
    3. Select the unique longest prefix. Ties on prefix length are broken by
       lexicographic ``mount_path`` then ``mount_id`` (stable across process
       restarts).
    4. If no mount matches, raise ``NamespaceError(UNKNOWN_MOUNT)``.
    """

    SCHEMA: ClassVar[str] = MOUNT_TABLE_SCHEMA

    def __init__(
        self,
        mounts: Sequence[VFSMount] | None = None,
        *,
        path_policy: VFSPathPolicy | None = None,
        require_root_mount: bool = False,
    ) -> None:
        self._policy = path_policy or VFSPathPolicy.default()
        self._by_id: dict[str, VFSMount] = {}
        self._by_path: dict[str, str] = {}  # mount_path -> mount_id
        self._require_root_mount = bool(require_root_mount)
        if mounts:
            for mount in mounts:
                self.add(mount)

    @classmethod
    def with_default_root(
        cls,
        *,
        mount_id: str = DEFAULT_MOUNT_ID,
        backend_id: str = DEFAULT_BACKEND_ID,
        namespace_id: str = DEFAULT_NAMESPACE_ID,
        path_policy: VFSPathPolicy | None = None,
        read_only: bool = False,
    ) -> "MountTable":
        """Construct a table with a single root mount at ``\"\"``."""

        table = cls(path_policy=path_policy)
        table.add(
            VFSMount(
                mount_id=mount_id,
                mount_path="",
                backend_id=backend_id,
                namespace_id=namespace_id,
                read_only=read_only,
                atomic_boundary=AtomicBoundary.SINGLE_MOUNT,
            )
        )
        return table

    @property
    def path_policy(self) -> VFSPathPolicy:
        return self._policy

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, mount_id: object) -> bool:
        return isinstance(mount_id, str) and mount_id in self._by_id

    def get(self, mount_id: str) -> VFSMount | None:
        return self._by_id.get(mount_id)

    def require(self, mount_id: str) -> VFSMount:
        mount = self._by_id.get(mount_id)
        if mount is None:
            raise NamespaceError(
                f"unknown mount_id: {mount_id}",
                code=NamespaceErrorCode.UNKNOWN_MOUNT,
                mount_id=mount_id,
            )
        return mount

    def mounts(self) -> tuple[VFSMount, ...]:
        """Return mounts in deterministic resolution order (longest first)."""

        return tuple(sorted(self._by_id.values(), key=_mount_prefix_key))

    def add(self, mount: VFSMount) -> VFSMount:
        if not isinstance(mount, VFSMount):
            raise NamespaceError(
                "mount must be a VFSMount",
                code=NamespaceErrorCode.INTERNAL,
            )
        if len(self._by_id) >= MAX_MOUNTS and mount.mount_id not in self._by_id:
            raise NamespaceError(
                f"mount table exceeds MAX_MOUNTS ({MAX_MOUNTS})",
                code=NamespaceErrorCode.MOUNT_CONFLICT,
                mount_id=mount.mount_id,
            )
        existing_id = self._by_path.get(mount.mount_path)
        if existing_id is not None and existing_id != mount.mount_id:
            raise NamespaceError(
                f"mount_path {mount.mount_path!r} already bound to {existing_id}",
                code=NamespaceErrorCode.MOUNT_CONFLICT,
                mount_id=mount.mount_id,
                path=mount.mount_path,
                detail={"existing_mount_id": existing_id},
            )
        if mount.mount_id in self._by_id:
            old = self._by_id[mount.mount_id]
            if old.mount_path != mount.mount_path:
                # Replacing a mount id at a different path: free old path slot.
                self._by_path.pop(old.mount_path, None)
        self._by_id[mount.mount_id] = mount
        self._by_path[mount.mount_path] = mount.mount_id
        return mount

    def remove(self, mount_id: str) -> VFSMount:
        mount = self.require(mount_id)
        del self._by_id[mount_id]
        if self._by_path.get(mount.mount_path) == mount_id:
            del self._by_path[mount.mount_path]
        return mount

    def resolve(
        self,
        raw_path: str,
        *,
        policy: VFSPathPolicy | None = None,
        mount_id: str | None = None,
    ) -> MountResolution:
        """Resolve ``raw_path`` to a mount via longest-prefix matching.

        When ``mount_id`` is supplied, the path must fall under that mount;
        an unknown id or path outside the mount is a typed reject.
        """

        active_policy = policy or self._policy
        try:
            normalized = normalize_vfs_path(raw_path, policy=active_policy)
        except VFSPathError as exc:
            raise NamespaceError(
                str(exc),
                code=NamespaceErrorCode.PATH_POLICY,
                path=getattr(exc, "path", raw_path) or raw_path,
                detail={"reason": exc.reason.value},
            ) from exc

        absolute = normalized.path

        if mount_id is not None and mount_id != "":
            mount = self.require(mount_id)
            if not path_is_within_root(absolute, mount.mount_path):
                raise NamespaceError(
                    f"path {absolute!r} is outside mount {mount_id}",
                    code=NamespaceErrorCode.MOUNT_NOT_FOUND,
                    path=absolute,
                    mount_id=mount_id,
                    detail={"mount_path": mount.mount_path},
                )
            return MountResolution(
                mount=mount,
                absolute_path=absolute,
                relative_path=_relative_to_prefix(absolute, mount.mount_path),
                matched_prefix=mount.mount_path,
            )

        candidates: list[VFSMount] = []
        for mount in self._by_id.values():
            if path_is_within_root(absolute, mount.mount_path):
                candidates.append(mount)

        if not candidates:
            if self._require_root_mount or not self._by_id:
                raise NamespaceError(
                    f"no mount covers path {absolute!r}",
                    code=NamespaceErrorCode.UNKNOWN_MOUNT,
                    path=absolute,
                )
            raise NamespaceError(
                f"no mount covers path {absolute!r}",
                code=NamespaceErrorCode.MOUNT_NOT_FOUND,
                path=absolute,
            )

        # Longest prefix; deterministic tie-break on path then mount_id.
        candidates.sort(key=_mount_prefix_key)
        winner = candidates[0]
        return MountResolution(
            mount=winner,
            absolute_path=absolute,
            relative_path=_relative_to_prefix(absolute, winner.mount_path),
            matched_prefix=winner.mount_path,
        )

    def resolve_pair(
        self,
        source_path: str,
        target_path: str,
        *,
        source_mount_id: str = "",
        target_mount_id: str = "",
        policy: VFSPathPolicy | None = None,
    ) -> tuple[MountResolution, MountResolution, AtomicBoundary, AtomicityDisposition]:
        """Resolve source/target and classify the atomic boundary between them."""

        src = self.resolve(
            source_path,
            policy=policy,
            mount_id=source_mount_id or None,
        )
        dst = self.resolve(
            target_path,
            policy=policy,
            mount_id=target_mount_id or None,
        )
        boundary, disposition = classify_mount_pair(src.mount, dst.mount)
        return src, dst, boundary, disposition

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path_policy": self._policy.to_record(),
            "require_root_mount": self._require_root_mount,
            "mounts": [mount.to_record() for mount in self.mounts()],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MountTable":
        if not isinstance(payload, Mapping):
            raise NamespaceError(
                "mount table payload must be a mapping",
                code=NamespaceErrorCode.INVALID_CHECKPOINT,
            )
        policy_payload = payload.get("path_policy")
        policy = (
            VFSPathPolicy.from_dict(policy_payload)
            if isinstance(policy_payload, Mapping)
            else VFSPathPolicy.default()
        )
        table = cls(
            path_policy=policy,
            require_root_mount=bool(payload.get("require_root_mount", False)),
        )
        for item in payload.get("mounts") or ():
            if not isinstance(item, Mapping):
                raise NamespaceError(
                    "mount entries must be mappings",
                    code=NamespaceErrorCode.INVALID_CHECKPOINT,
                )
            table.add(VFSMount.from_dict(item))
        return table


# ---------------------------------------------------------------------------
# Stable inode identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StableInode:
    """A durable inode identity independent of the current path spelling.

    ``node_key`` is the stable logical identity (content/node id). ``inode`` is
    the host-visible number. ``path`` is the current namespace location and may
    change on same-mount rename without changing ``inode`` or ``node_key``.
    """

    SCHEMA: ClassVar[str] = STABLE_INODE_SCHEMA

    inode: int
    mount_id: str
    node_key: str
    path: str
    generation: int = 0
    kind: VFSEntryKind = VFSEntryKind.FILE

    def __post_init__(self) -> None:
        if not isinstance(self.inode, int) or isinstance(self.inode, bool):
            raise NamespaceError(
                "inode must be an integer",
                code=NamespaceErrorCode.INTERNAL,
            )
        if self.inode < ROOT_INODE or self.inode > MAX_INODE:
            raise NamespaceError(
                "inode outside supported bound",
                code=NamespaceErrorCode.INODE_EXHAUSTED,
            )
        if not isinstance(self.mount_id, str) or not self.mount_id:
            raise NamespaceError(
                "mount_id is required",
                code=NamespaceErrorCode.INTERNAL,
            )
        if not isinstance(self.node_key, str) or not self.node_key:
            raise NamespaceError(
                "node_key is required",
                code=NamespaceErrorCode.INTERNAL,
            )
        if not isinstance(self.path, str):
            raise NamespaceError(
                "path must be a string",
                code=NamespaceErrorCode.INTERNAL,
            )
        if not isinstance(self.generation, int) or isinstance(self.generation, bool):
            raise NamespaceError(
                "generation must be an integer",
                code=NamespaceErrorCode.INTERNAL,
            )
        if self.generation < 0:
            raise NamespaceError(
                "generation must be non-negative",
                code=NamespaceErrorCode.INTERNAL,
            )
        if not isinstance(self.kind, VFSEntryKind):
            object.__setattr__(self, "kind", VFSEntryKind(self.kind))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "inode": self.inode,
            "mount_id": self.mount_id,
            "node_key": self.node_key,
            "path": self.path,
            "generation": self.generation,
            "kind": self.kind.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StableInode":
        if not isinstance(payload, Mapping):
            raise NamespaceError(
                "inode payload must be a mapping",
                code=NamespaceErrorCode.INVALID_CHECKPOINT,
            )
        return cls(
            inode=int(payload["inode"]),
            mount_id=str(payload["mount_id"]),
            node_key=str(payload["node_key"]),
            path=str(payload.get("path", "") or ""),
            generation=int(payload.get("generation", 0) or 0),
            kind=payload.get("kind", VFSEntryKind.FILE),
        )

    def with_path(self, path: str) -> "StableInode":
        return StableInode(
            inode=self.inode,
            mount_id=self.mount_id,
            node_key=self.node_key,
            path=path,
            generation=self.generation,
            kind=self.kind,
        )


def durable_node_key(
    *,
    mount_id: str,
    identity: str,
    namespace_id: str = "",
) -> str:
    """Derive a durable, content-addressed node key for inode binding.

    The key is independent of the current path so same-mount renames and
    restarts that restore the key map preserve inode numbers.
    """

    if not mount_id or not identity:
        raise NamespaceError(
            "mount_id and identity are required for durable_node_key",
            code=NamespaceErrorCode.INTERNAL,
        )
    payload = {
        "mount_id": mount_id,
        "namespace_id": namespace_id,
        "identity": identity,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"node:{digest}"


class StableInodeTable:
    """Stable inode allocator with restart and same-mount rename survival.

    Identity rules:

    * ``node_key`` is the durable identity; ``inode`` is assigned once per key.
    * Same-mount rename updates ``path`` only; ``inode`` and ``node_key`` stay.
    * Cross-mount rename is refused (callers must reject via mount table).
    * ``checkpoint`` / ``restore`` round-trip preserves inode numbers.
    * Root (``path == \"\"``) is always inode :data:`ROOT_INODE` when present.
    """

    SCHEMA: ClassVar[str] = STABLE_INODE_TABLE_SCHEMA

    def __init__(
        self,
        *,
        root_mount_id: str = DEFAULT_MOUNT_ID,
        next_inode: int = MIN_ALLOCATED_INODE,
    ) -> None:
        if next_inode < MIN_ALLOCATED_INODE:
            raise NamespaceError(
                f"next_inode must be >= {MIN_ALLOCATED_INODE}",
                code=NamespaceErrorCode.INTERNAL,
            )
        self._root_mount_id = root_mount_id
        self._next_inode = next_inode
        self._by_inode: dict[int, StableInode] = {}
        self._by_key: dict[str, int] = {}
        self._by_path: dict[str, int] = {}
        # Reserve root inode for the namespace root path.
        root = StableInode(
            inode=ROOT_INODE,
            mount_id=root_mount_id,
            node_key=durable_node_key(mount_id=root_mount_id, identity="root"),
            path="",
            generation=0,
            kind=VFSEntryKind.DIRECTORY,
        )
        self._index(root)

    def _index(self, entry: StableInode) -> None:
        self._by_inode[entry.inode] = entry
        self._by_key[entry.node_key] = entry.inode
        self._by_path[entry.path] = entry.inode

    def _unindex_path(self, path: str) -> None:
        self._by_path.pop(path, None)

    @property
    def next_inode(self) -> int:
        return self._next_inode

    def __len__(self) -> int:
        return len(self._by_inode)

    def get_by_inode(self, inode: int) -> StableInode | None:
        return self._by_inode.get(inode)

    def get_by_path(self, path: str) -> StableInode | None:
        inode = self._by_path.get(path)
        if inode is None:
            return None
        return self._by_inode.get(inode)

    def get_by_key(self, node_key: str) -> StableInode | None:
        inode = self._by_key.get(node_key)
        if inode is None:
            return None
        return self._by_inode.get(inode)

    def require_path(self, path: str) -> StableInode:
        entry = self.get_by_path(path)
        if entry is None:
            raise NamespaceError(
                f"inode not found for path {path!r}",
                code=NamespaceErrorCode.INODE_NOT_FOUND,
                path=path,
            )
        return entry

    def require_inode(self, inode: int) -> StableInode:
        entry = self.get_by_inode(inode)
        if entry is None:
            raise NamespaceError(
                f"inode not found: {inode}",
                code=NamespaceErrorCode.INODE_NOT_FOUND,
                detail={"inode": inode},
            )
        return entry

    def allocate(
        self,
        *,
        mount_id: str,
        node_key: str,
        path: str,
        kind: VFSEntryKind = VFSEntryKind.FILE,
        generation: int = 0,
    ) -> StableInode:
        """Allocate or rebind a stable inode for ``node_key``.

        Re-allocating an existing ``node_key`` returns the same inode number
        and updates path/kind/generation as needed (idempotent rebind).
        """

        if path == "":
            # Root is reserved.
            existing_root = self.require_inode(ROOT_INODE)
            if node_key != existing_root.node_key and node_key:
                # Allow rebinding root metadata only when key matches.
                pass
            return existing_root

        existing = self.get_by_key(node_key)
        if existing is not None:
            if existing.mount_id != mount_id:
                raise NamespaceError(
                    "node_key already bound to a different mount",
                    code=NamespaceErrorCode.INODE_CONFLICT,
                    path=path,
                    mount_id=mount_id,
                    detail={
                        "node_key": node_key,
                        "existing_mount_id": existing.mount_id,
                        "inode": existing.inode,
                    },
                )
            # Rebind path if it moved (same-mount recovery / rename restore).
            if existing.path != path:
                occupant = self.get_by_path(path)
                if occupant is not None and occupant.inode != existing.inode:
                    raise NamespaceError(
                        f"path {path!r} already bound to inode {occupant.inode}",
                        code=NamespaceErrorCode.INODE_CONFLICT,
                        path=path,
                        mount_id=mount_id,
                    )
                self._unindex_path(existing.path)
                updated = StableInode(
                    inode=existing.inode,
                    mount_id=mount_id,
                    node_key=node_key,
                    path=path,
                    generation=generation,
                    kind=kind,
                )
                self._index(updated)
                return updated
            updated = StableInode(
                inode=existing.inode,
                mount_id=mount_id,
                node_key=node_key,
                path=path,
                generation=generation,
                kind=kind,
            )
            self._index(updated)
            return updated

        occupant = self.get_by_path(path)
        if occupant is not None:
            raise NamespaceError(
                f"path {path!r} already bound to inode {occupant.inode}",
                code=NamespaceErrorCode.INODE_CONFLICT,
                path=path,
                mount_id=mount_id,
            )

        if len(self._by_inode) >= MAX_INODES:
            raise NamespaceError(
                f"inode table exceeds MAX_INODES ({MAX_INODES})",
                code=NamespaceErrorCode.INODE_EXHAUSTED,
                path=path,
                mount_id=mount_id,
            )
        if self._next_inode > MAX_INODE:
            raise NamespaceError(
                "inode number space exhausted",
                code=NamespaceErrorCode.INODE_EXHAUSTED,
                path=path,
                mount_id=mount_id,
            )

        inode_num = self._next_inode
        self._next_inode += 1
        entry = StableInode(
            inode=inode_num,
            mount_id=mount_id,
            node_key=node_key,
            path=path,
            generation=generation,
            kind=kind,
        )
        self._index(entry)
        return entry

    def rename(
        self,
        source_path: str,
        target_path: str,
        *,
        expected_mount_id: str | None = None,
    ) -> StableInode:
        """Same-mount rename: path changes, inode number is preserved."""

        if source_path == target_path:
            return self.require_path(source_path)

        entry = self.require_path(source_path)
        if expected_mount_id is not None and entry.mount_id != expected_mount_id:
            raise NamespaceError(
                "rename mount mismatch",
                code=NamespaceErrorCode.CROSS_MOUNT,
                path=source_path,
                mount_id=entry.mount_id,
                detail={"expected_mount_id": expected_mount_id},
            )
        if target_path == "":
            raise NamespaceError(
                "cannot rename onto namespace root",
                code=NamespaceErrorCode.INODE_CONFLICT,
                path=target_path,
                mount_id=entry.mount_id,
            )
        occupant = self.get_by_path(target_path)
        if occupant is not None and occupant.inode != entry.inode:
            raise NamespaceError(
                f"rename target path already bound: {target_path!r}",
                code=NamespaceErrorCode.INODE_CONFLICT,
                path=target_path,
                mount_id=entry.mount_id,
                detail={"occupant_inode": occupant.inode},
            )

        self._unindex_path(source_path)
        updated = entry.with_path(target_path)
        self._index(updated)
        return updated

    def forget(self, path: str) -> StableInode:
        """Remove path binding and free the inode number for the node_key."""

        entry = self.require_path(path)
        if entry.inode == ROOT_INODE:
            raise NamespaceError(
                "cannot forget root inode",
                code=NamespaceErrorCode.INODE_CONFLICT,
                path=path,
            )
        del self._by_inode[entry.inode]
        self._by_key.pop(entry.node_key, None)
        self._unindex_path(path)
        return entry

    def entries(self) -> tuple[StableInode, ...]:
        return tuple(
            sorted(self._by_inode.values(), key=lambda item: (item.path, item.inode))
        )

    def checkpoint(self) -> dict[str, Any]:
        """Serialize durable state so inode numbers survive restart."""

        return {
            "schema": self.SCHEMA,
            "root_mount_id": self._root_mount_id,
            "next_inode": self._next_inode,
            "entries": [entry.to_record() for entry in self.entries()],
            "content_id": content_identity(
                {
                    "root_mount_id": self._root_mount_id,
                    "next_inode": self._next_inode,
                    "entries": [entry.to_record() for entry in self.entries()],
                }
            ),
        }

    @classmethod
    def restore(cls, payload: Mapping[str, Any]) -> "StableInodeTable":
        """Restore a checkpoint; inode numbers match the serialized table."""

        if not isinstance(payload, Mapping):
            raise NamespaceError(
                "inode checkpoint must be a mapping",
                code=NamespaceErrorCode.INVALID_CHECKPOINT,
            )
        root_mount_id = str(payload.get("root_mount_id") or DEFAULT_MOUNT_ID)
        next_inode = int(payload.get("next_inode", MIN_ALLOCATED_INODE))
        table = cls.__new__(cls)
        table._root_mount_id = root_mount_id
        table._next_inode = next_inode
        table._by_inode = {}
        table._by_key = {}
        table._by_path = {}

        entries = payload.get("entries") or ()
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)):
            raise NamespaceError(
                "inode checkpoint entries must be a sequence",
                code=NamespaceErrorCode.INVALID_CHECKPOINT,
            )
        for item in entries:
            if not isinstance(item, Mapping):
                raise NamespaceError(
                    "inode checkpoint entry must be a mapping",
                    code=NamespaceErrorCode.INVALID_CHECKPOINT,
                )
            entry = StableInode.from_dict(item)
            if entry.node_key in table._by_key:
                raise NamespaceError(
                    "duplicate node_key in checkpoint",
                    code=NamespaceErrorCode.INVALID_CHECKPOINT,
                    detail={"node_key": entry.node_key},
                )
            if entry.inode in table._by_inode:
                raise NamespaceError(
                    "duplicate inode in checkpoint",
                    code=NamespaceErrorCode.INVALID_CHECKPOINT,
                    detail={"inode": entry.inode},
                )
            if entry.path in table._by_path:
                raise NamespaceError(
                    "duplicate path in checkpoint",
                    code=NamespaceErrorCode.INVALID_CHECKPOINT,
                    path=entry.path,
                )
            table._index(entry)
            if entry.inode >= table._next_inode:
                table._next_inode = entry.inode + 1

        if ROOT_INODE not in table._by_inode:
            # Ensure root always exists after restore.
            root = StableInode(
                inode=ROOT_INODE,
                mount_id=root_mount_id,
                node_key=durable_node_key(mount_id=root_mount_id, identity="root"),
                path="",
                generation=0,
                kind=VFSEntryKind.DIRECTORY,
            )
            table._index(root)
        return table

    def to_record(self) -> dict[str, Any]:
        return self.checkpoint()


# ---------------------------------------------------------------------------
# Mutation admission
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MutationAdmission:
    """Result of admitting or rejecting a namespace mutation."""

    allowed: bool
    source: MountResolution | None = None
    target: MountResolution | None = None
    boundary: AtomicBoundary | None = None
    disposition: AtomicityDisposition | None = None
    code: NamespaceErrorCode | None = None
    message: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "source": None if self.source is None else self.source.to_record(),
            "target": None if self.target is None else self.target.to_record(),
            "boundary": None if self.boundary is None else self.boundary.value,
            "disposition": None if self.disposition is None else self.disposition.value,
            "code": None if self.code is None else self.code.value,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Namespace router
# ---------------------------------------------------------------------------


class NamespaceRouter:
    """Compose path policy, mount table, and stable inodes for host routing.

    ``NamespaceRouter@1`` is the single entry point for:

    * path normalization and root confinement traces;
    * longest-prefix mount resolution;
    * mutation admission (unknown / cross-mount / read-only reject);
    * stable inode allocate / rename / restart restore;
    * symlink, Unicode, case, and pagination policy traces.
    """

    SCHEMA: ClassVar[str] = NAMESPACE_ROUTER_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        *,
        path_policy: VFSPathPolicy | None = None,
        mount_table: MountTable | None = None,
        inode_table: StableInodeTable | None = None,
        trace: NamespaceTraceLog | None = None,
    ) -> None:
        self._policy = path_policy or VFSPathPolicy.default()
        self._mounts = mount_table or MountTable.with_default_root(path_policy=self._policy)
        if path_policy is not None and mount_table is not None:
            # Prefer explicit policy on the router for normalization; mount
            # table may carry a compatible policy of its own.
            pass
        root_mount = self._mounts.get(DEFAULT_MOUNT_ID) or (
            self._mounts.mounts()[0] if len(self._mounts) else None
        )
        root_mount_id = root_mount.mount_id if root_mount is not None else DEFAULT_MOUNT_ID
        self._inodes = inode_table or StableInodeTable(root_mount_id=root_mount_id)
        self._trace = trace or NamespaceTraceLog()

    @property
    def path_policy(self) -> VFSPathPolicy:
        return self._policy

    @property
    def mounts(self) -> MountTable:
        return self._mounts

    @property
    def inodes(self) -> StableInodeTable:
        return self._inodes

    @property
    def trace(self) -> NamespaceTraceLog:
        return self._trace

    # -- path / mount -------------------------------------------------------

    def normalize(self, raw_path: str, *, root: str = "") -> NormalizedPath:
        """Normalize under the router path policy and record a trace step."""

        try:
            if root:
                norm = confine_path(raw_path, root, policy=self._policy)
            else:
                norm = normalize_vfs_path(raw_path, policy=self._policy)
        except VFSPathError as exc:
            self._trace.record(
                NamespaceTraceKind.NORMALIZE,
                success=False,
                path=getattr(exc, "path", raw_path) or raw_path,
                code=exc.reason.value,
                detail={"reason": exc.reason.value, "root": root},
            )
            raise NamespaceError(
                str(exc),
                code=NamespaceErrorCode.PATH_POLICY,
                path=getattr(exc, "path", raw_path) or raw_path,
                detail={"reason": exc.reason.value},
            ) from exc

        self._trace.record(
            NamespaceTraceKind.NORMALIZE,
            success=True,
            path=norm.path,
            detail={
                "segments": list(norm.segments),
                "root": norm.root,
                "is_root": norm.is_root,
                "unicode_policy": self._policy.unicode_policy.value,
                "case_policy": self._policy.case_policy.value,
            },
        )
        return norm

    def resolve(self, raw_path: str, *, mount_id: str | None = None) -> MountResolution:
        """Longest-prefix mount resolution with executable trace."""

        try:
            resolution = self._mounts.resolve(
                raw_path, policy=self._policy, mount_id=mount_id
            )
        except NamespaceError as exc:
            self._trace.record(
                NamespaceTraceKind.RESOLVE_MOUNT,
                success=False,
                path=exc.path or raw_path,
                mount_id=exc.mount_id,
                code=exc.code.value,
                detail=exc.detail,
            )
            raise

        self._trace.record(
            NamespaceTraceKind.RESOLVE_MOUNT,
            success=True,
            path=resolution.absolute_path,
            mount_id=resolution.mount_id,
            detail={
                "matched_prefix": resolution.matched_prefix,
                "relative_path": resolution.relative_path,
                "backend_id": resolution.mount.backend_id,
                "read_only": resolution.read_only,
            },
        )
        return resolution

    # -- mutation admission -------------------------------------------------

    def admit_create(
        self,
        raw_path: str,
        *,
        mount_id: str | None = None,
    ) -> MutationAdmission:
        """Admit a single-path create/mkdir/delete under one mount."""

        try:
            resolution = self.resolve(raw_path, mount_id=mount_id)
        except NamespaceError as exc:
            admission = MutationAdmission(
                allowed=False,
                code=exc.code,
                message=str(exc),
            )
            self._trace.record(
                NamespaceTraceKind.ADMIT_MUTATION,
                success=False,
                path=exc.path or raw_path,
                mount_id=exc.mount_id,
                code=exc.code.value,
                detail=admission.to_record(),
            )
            return admission

        if resolution.read_only:
            admission = MutationAdmission(
                allowed=False,
                source=resolution,
                code=NamespaceErrorCode.READ_ONLY_MOUNT,
                message="mount is read-only",
            )
            self._trace.record(
                NamespaceTraceKind.ADMIT_MUTATION,
                success=False,
                path=resolution.absolute_path,
                mount_id=resolution.mount_id,
                code=NamespaceErrorCode.READ_ONLY_MOUNT.value,
                detail=admission.to_record(),
            )
            return admission

        admission = MutationAdmission(
            allowed=True,
            source=resolution,
            boundary=AtomicBoundary.SINGLE_MOUNT,
            disposition=AtomicityDisposition.ATOMIC,
            message="mutation admitted within single mount",
        )
        self._trace.record(
            NamespaceTraceKind.ADMIT_MUTATION,
            success=True,
            path=resolution.absolute_path,
            mount_id=resolution.mount_id,
            detail=admission.to_record(),
        )
        return admission

    def admit_rename(
        self,
        source_path: str,
        target_path: str,
        *,
        source_mount_id: str = "",
        target_mount_id: str = "",
    ) -> MutationAdmission:
        """Admit a rename/move; reject unknown and cross-mount cases."""

        try:
            src, dst, boundary, disposition = self._mounts.resolve_pair(
                source_path,
                target_path,
                source_mount_id=source_mount_id,
                target_mount_id=target_mount_id,
                policy=self._policy,
            )
        except NamespaceError as exc:
            admission = MutationAdmission(
                allowed=False,
                code=exc.code,
                message=str(exc),
            )
            self._trace.record(
                NamespaceTraceKind.ADMIT_MUTATION,
                success=False,
                path=exc.path or source_path,
                mount_id=exc.mount_id,
                code=exc.code.value,
                detail={**admission.to_record(), "op": "rename"},
            )
            return admission

        self._trace.record(
            NamespaceTraceKind.RESOLVE_MOUNT,
            success=True,
            path=src.absolute_path,
            mount_id=src.mount_id,
            detail={"role": "source", **src.to_record()},
        )
        self._trace.record(
            NamespaceTraceKind.RESOLVE_MOUNT,
            success=True,
            path=dst.absolute_path,
            mount_id=dst.mount_id,
            detail={"role": "target", **dst.to_record()},
        )

        if src.read_only or dst.read_only:
            admission = MutationAdmission(
                allowed=False,
                source=src,
                target=dst,
                boundary=boundary,
                disposition=disposition,
                code=NamespaceErrorCode.READ_ONLY_MOUNT,
                message="rename touches a read-only mount",
            )
            self._trace.record(
                NamespaceTraceKind.ADMIT_MUTATION,
                success=False,
                path=src.absolute_path,
                mount_id=src.mount_id,
                code=NamespaceErrorCode.READ_ONLY_MOUNT.value,
                detail=admission.to_record(),
            )
            return admission

        if disposition is AtomicityDisposition.UNSUPPORTED or boundary in (
            AtomicBoundary.CROSS_MOUNT,
            AtomicBoundary.CROSS_BACKEND,
            AtomicBoundary.CROSS_NAMESPACE,
        ):
            try:
                assert_atomic_boundary_supported(boundary)
            except VFSUnsupportedError as exc:
                admission = MutationAdmission(
                    allowed=False,
                    source=src,
                    target=dst,
                    boundary=boundary,
                    disposition=AtomicityDisposition.UNSUPPORTED,
                    code=NamespaceErrorCode.CROSS_MOUNT,
                    message=str(exc),
                )
                self._trace.record(
                    NamespaceTraceKind.ADMIT_MUTATION,
                    success=False,
                    path=src.absolute_path,
                    mount_id=src.mount_id,
                    code=NamespaceErrorCode.CROSS_MOUNT.value,
                    detail={
                        **admission.to_record(),
                        "unsupported_reason": exc.reason.value,
                    },
                )
                return admission

        admission = MutationAdmission(
            allowed=True,
            source=src,
            target=dst,
            boundary=boundary,
            disposition=AtomicityDisposition.ATOMIC,
            message="same-mount rename admitted",
        )
        self._trace.record(
            NamespaceTraceKind.ADMIT_MUTATION,
            success=True,
            path=src.absolute_path,
            mount_id=src.mount_id,
            detail=admission.to_record(),
        )
        return admission

    # -- stable inodes ------------------------------------------------------

    def allocate_inode(
        self,
        raw_path: str,
        *,
        identity: str,
        kind: VFSEntryKind = VFSEntryKind.FILE,
        generation: int = 0,
        mount_id: str | None = None,
        namespace_id: str = "",
    ) -> StableInode:
        """Resolve path, allocate a durable inode, and record the step."""

        resolution = self.resolve(raw_path, mount_id=mount_id)
        key = durable_node_key(
            mount_id=resolution.mount_id,
            identity=identity,
            namespace_id=namespace_id or resolution.mount.namespace_id,
        )
        entry = self._inodes.allocate(
            mount_id=resolution.mount_id,
            node_key=key,
            path=resolution.absolute_path,
            kind=kind,
            generation=generation,
        )
        self._trace.record(
            NamespaceTraceKind.ALLOCATE_INODE,
            success=True,
            path=entry.path,
            mount_id=entry.mount_id,
            detail=entry.to_record(),
        )
        return entry

    def lookup_inode(self, raw_path: str) -> StableInode:
        norm = self.normalize(raw_path)
        entry = self._inodes.require_path(norm.path)
        self._trace.record(
            NamespaceTraceKind.LOOKUP_INODE,
            success=True,
            path=entry.path,
            mount_id=entry.mount_id,
            detail=entry.to_record(),
        )
        return entry

    def rename_inode(self, source_path: str, target_path: str) -> StableInode:
        """Same-mount rename preserving inode identity."""

        admission = self.admit_rename(source_path, target_path)
        if not admission.allowed:
            self._trace.record(
                NamespaceTraceKind.RENAME_INODE,
                success=False,
                path=source_path,
                code=(admission.code or NamespaceErrorCode.CROSS_MOUNT).value,
                detail=admission.to_record(),
            )
            raise NamespaceError(
                admission.message or "rename rejected",
                code=admission.code or NamespaceErrorCode.CROSS_MOUNT,
                path=source_path,
                mount_id=admission.source.mount_id if admission.source else "",
                detail=admission.to_record(),
            )
        assert admission.source is not None and admission.target is not None
        entry = self._inodes.rename(
            admission.source.absolute_path,
            admission.target.absolute_path,
            expected_mount_id=admission.source.mount_id,
        )
        self._trace.record(
            NamespaceTraceKind.RENAME_INODE,
            success=True,
            path=entry.path,
            mount_id=entry.mount_id,
            detail={
                "inode": entry.inode,
                "node_key": entry.node_key,
                "source_path": admission.source.absolute_path,
                "target_path": admission.target.absolute_path,
            },
        )
        return entry

    def checkpoint(self) -> dict[str, Any]:
        """Durable checkpoint of mounts + inodes for restart survival."""

        payload = {
            "schema": self.SCHEMA,
            "contract_version": self.CONTRACT_VERSION,
            "path_policy": self._policy.to_record(),
            "mount_table": self._mounts.to_record(),
            "inode_table": self._inodes.checkpoint(),
        }
        payload["content_id"] = content_identity(
            {
                "path_policy": payload["path_policy"],
                "mount_table": payload["mount_table"],
                "inode_table": payload["inode_table"],
            }
        )
        self._trace.record(
            NamespaceTraceKind.CHECKPOINT,
            success=True,
            detail={
                "content_id": payload["content_id"],
                "mount_count": len(self._mounts),
                "inode_count": len(self._inodes),
            },
        )
        return payload

    @classmethod
    def restore(
        cls,
        payload: Mapping[str, Any],
        *,
        trace: NamespaceTraceLog | None = None,
    ) -> "NamespaceRouter":
        """Restore mounts and inode numbers from a checkpoint."""

        if not isinstance(payload, Mapping):
            raise NamespaceError(
                "namespace checkpoint must be a mapping",
                code=NamespaceErrorCode.INVALID_CHECKPOINT,
            )
        policy_payload = payload.get("path_policy")
        policy = (
            VFSPathPolicy.from_dict(policy_payload)
            if isinstance(policy_payload, Mapping)
            else VFSPathPolicy.default()
        )
        mount_payload = payload.get("mount_table")
        if not isinstance(mount_payload, Mapping):
            raise NamespaceError(
                "mount_table missing from checkpoint",
                code=NamespaceErrorCode.INVALID_CHECKPOINT,
            )
        inode_payload = payload.get("inode_table")
        if not isinstance(inode_payload, Mapping):
            raise NamespaceError(
                "inode_table missing from checkpoint",
                code=NamespaceErrorCode.INVALID_CHECKPOINT,
            )
        router = cls(
            path_policy=policy,
            mount_table=MountTable.from_dict(mount_payload),
            inode_table=StableInodeTable.restore(inode_payload),
            trace=trace or NamespaceTraceLog(),
        )
        router.trace.record(
            NamespaceTraceKind.RESTORE,
            success=True,
            detail={
                "mount_count": len(router.mounts),
                "inode_count": len(router.inodes),
                "content_id": payload.get("content_id", ""),
            },
        )
        return router

    # -- policy traces ------------------------------------------------------

    def trace_root_confinement(
        self,
        raw_path: str,
        root: str,
    ) -> tuple[NormalizedPath | None, NamespaceTraceStep]:
        """Executable root-confinement trace (admit or reject)."""

        try:
            confined = confine_path(raw_path, root, policy=self._policy)
        except VFSPathError as exc:
            step = self._trace.record(
                NamespaceTraceKind.CONFINE,
                success=False,
                path=getattr(exc, "path", raw_path) or raw_path,
                code=exc.reason.value,
                detail={"root": root, "reason": exc.reason.value},
            )
            return None, step

        step = self._trace.record(
            NamespaceTraceKind.CONFINE,
            success=True,
            path=confined.path,
            detail={
                "root": confined.root,
                "segments": list(confined.segments),
                "within_root": path_is_within_root(
                    f"{confined.root}/{confined.path}" if confined.root and confined.path else (
                        confined.root or confined.path
                    ),
                    confined.root,
                ),
            },
        )
        return confined, step

    def trace_unicode_policy(self, raw_path: str) -> tuple[NormalizedPath | None, NamespaceTraceStep]:
        """Executable Unicode NFC policy trace."""

        try:
            norm = normalize_vfs_path(raw_path, policy=self._policy)
        except VFSPathError as exc:
            code = (
                NamespaceErrorCode.UNICODE_POLICY.value
                if exc.reason is VFSPathRejectReason.NON_NFC
                else exc.reason.value
            )
            step = self._trace.record(
                NamespaceTraceKind.UNICODE,
                success=False,
                path=getattr(exc, "path", raw_path) or raw_path,
                code=code,
                detail={
                    "reason": exc.reason.value,
                    "unicode_policy": self._policy.unicode_policy.value,
                },
            )
            return None, step

        step = self._trace.record(
            NamespaceTraceKind.UNICODE,
            success=True,
            path=norm.path,
            detail={
                "unicode_policy": self._policy.unicode_policy.value,
                "segments": list(norm.segments),
                "nfc_required": self._policy.unicode_policy
                is UnicodePolicy.NFC_REQUIRED,
            },
        )
        return norm, step

    def trace_case_policy(
        self,
        left: str,
        right: str,
        *,
        request_case_fold: bool = False,
    ) -> NamespaceTraceStep:
        """Executable case-policy trace.

        Case-sensitive identity is the default. Requesting case-fold comparison
        under ``INSENSITIVE_UNSUPPORTED`` is a typed reject.
        """

        # Case-fold comparison is typed unsupported under the canonical policy.
        if request_case_fold:
            return self._trace.record(
                NamespaceTraceKind.CASE,
                success=False,
                path=left,
                code=NamespaceErrorCode.CASE_POLICY.value,
                detail={
                    "case_policy": self._policy.case_policy.value,
                    "left": left,
                    "right": right,
                    "request_case_fold": True,
                    "reason": UnsupportedReason.CASE_INSENSITIVE.value,
                },
            )

        left_norm = normalize_vfs_path(left, policy=self._policy)
        right_norm = normalize_vfs_path(right, policy=self._policy)
        equal = left_norm.path == right_norm.path
        return self._trace.record(
            NamespaceTraceKind.CASE,
            success=True,
            path=left_norm.path,
            detail={
                "case_policy": self._policy.case_policy.value,
                "left": left_norm.path,
                "right": right_norm.path,
                "identity_equal": equal,
                "byte_stable": True,
            },
        )

    def trace_symlink_policy(
        self,
        target_raw: str,
        *,
        link_path: str,
        root: str,
    ) -> tuple[SymlinkDecision, NamespaceTraceStep]:
        """Executable symlink policy trace."""

        decision = evaluate_symlink(
            target_raw,
            link_path=link_path,
            root=root,
            policy=self._policy,
        )
        step = self._trace.record(
            NamespaceTraceKind.SYMLINK,
            success=decision.allowed,
            path=link_path,
            code=""
            if decision.allowed
            else (
                decision.reason.value
                if decision.reason is not None
                else NamespaceErrorCode.SYMLINK_POLICY.value
            ),
            detail={
                **decision.to_record(),
                "root": root,
                "symlink_policy": self._policy.symlink_policy.value,
            },
        )
        return decision, step

    def paginate(
        self,
        path: str,
        entries: Sequence[VFSDirEntry],
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        cursor: str = "",
        mount_id: str = "",
        generation_id: str = "",
    ) -> VFSListing:
        """Stable UTF-8 lexicographic pagination with an executable trace."""

        if page_size < 0 or page_size > MAX_LISTING_PAGE_SIZE:
            self._trace.record(
                NamespaceTraceKind.PAGINATE,
                success=False,
                path=path,
                code=NamespaceErrorCode.PAGINATION.value,
                detail={"page_size": page_size, "max": MAX_LISTING_PAGE_SIZE},
            )
            raise NamespaceError(
                f"page_size must be in [0, {MAX_LISTING_PAGE_SIZE}]",
                code=NamespaceErrorCode.PAGINATION,
                path=path,
                detail={"page_size": page_size},
            )

        norm = self.normalize(path)
        ordered = tuple(sorted(entries, key=lambda e: e.order_key()))
        start = 0
        if cursor:
            # Cursor is the last name of the previous page; resume after it.
            for index, entry in enumerate(ordered):
                if entry.name == cursor:
                    start = index + 1
                    break
            else:
                # Cursor not found: fail closed rather than silently restart.
                self._trace.record(
                    NamespaceTraceKind.PAGINATE,
                    success=False,
                    path=norm.path,
                    code=NamespaceErrorCode.PAGINATION.value,
                    detail={"cursor": cursor, "reason": "unknown_cursor"},
                )
                raise NamespaceError(
                    f"unknown pagination cursor: {cursor!r}",
                    code=NamespaceErrorCode.PAGINATION,
                    path=norm.path,
                    detail={"cursor": cursor},
                )

        window = ordered[start:]
        limit = page_size if page_size else len(window)
        page = window[:limit]
        has_more = len(window) > len(page)
        next_cursor = page[-1].name if has_more and page else ""
        listing = VFSListing(
            path=norm.path,
            entries=page,
            order=ListingOrder.UTF8_LEXICOGRAPHIC,
            page_size=len(page),
            cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
            generation_id=generation_id,
            observed=True,
            mount_id=mount_id,
        )
        self._trace.record(
            NamespaceTraceKind.PAGINATE,
            success=True,
            path=norm.path,
            mount_id=mount_id,
            detail={
                "page_size": listing.page_size,
                "cursor": listing.cursor,
                "next_cursor": listing.next_cursor,
                "has_more": listing.has_more,
                "names": [entry.name for entry in listing.entries],
                "order": listing.order.value,
                "total_available": len(window),
            },
        )
        return listing

    def run_policy_trace_suite(
        self,
        *,
        confine_path_raw: str = "a/b",
        confine_root: str = "docs",
        unicode_ok: str = "café",
        unicode_bad: str | None = None,
        case_left: str = "Docs/Readme",
        case_right: str = "docs/readme",
        symlink_target: str = "target.txt",
        symlink_link: str = "docs/link",
        symlink_root: str = "docs",
        page_names: Sequence[str] = ("c", "a", "b"),
        page_size: int = 2,
    ) -> list[dict[str, Any]]:
        """Run a closed suite of policy traces and return their records.

        Used by acceptance tests and readiness probes as executable evidence
        for root confinement, Unicode, case, symlink, and pagination policy.
        """

        import unicodedata

        self.trace_root_confinement(confine_path_raw, confine_root)
        # Escape / traversal attempt — records a reject step without raising.
        self.trace_root_confinement("../outside", confine_root)

        self.trace_unicode_policy(f"docs/{unicode_ok}")
        bad = unicode_bad
        if bad is None:
            bad = unicodedata.normalize("NFD", unicode_ok)
        if bad != unicode_ok:
            self.trace_unicode_policy(f"docs/{bad}")

        self.trace_case_policy(case_left, case_right, request_case_fold=False)
        self.trace_case_policy(case_left, case_right, request_case_fold=True)

        self.trace_symlink_policy(
            symlink_target, link_path=symlink_link, root=symlink_root
        )

        entries = tuple(
            VFSDirEntry(name=name, kind=VFSEntryKind.FILE) for name in page_names
        )
        first = self.paginate("", entries, page_size=page_size)
        if first.has_more:
            self.paginate("", entries, page_size=page_size, cursor=first.next_cursor)

        return self._trace.to_records()

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": self.CONTRACT_VERSION,
            "path_policy": self._policy.to_record(),
            "mount_table": self._mounts.to_record(),
            "inode_table": self._inodes.to_record(),
            "trace": self._trace.to_records(),
        }


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "MOUNT_TABLE_SCHEMA",
    "STABLE_INODE_TABLE_SCHEMA",
    "NAMESPACE_ROUTER_SCHEMA",
    "MountTable_V1",
    "StableInodeTable_V1",
    "NamespaceRouter_V1",
    "ROOT_INODE",
    "MIN_ALLOCATED_INODE",
    "MAX_INODE",
    "MAX_MOUNTS",
    "MAX_INODES",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_MOUNT_ID",
    "DEFAULT_NAMESPACE_ID",
    "DEFAULT_BACKEND_ID",
    "NamespaceErrorCode",
    "NamespaceError",
    "NamespaceTraceKind",
    "NamespaceTraceStep",
    "NamespaceTraceLog",
    "MountResolution",
    "MountTable",
    "StableInode",
    "StableInodeTable",
    "MutationAdmission",
    "NamespaceRouter",
    "durable_node_key",
]

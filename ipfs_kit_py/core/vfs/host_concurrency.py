"""Host callback concurrency, lock ordering, and open-rename/unlink (KVFS-208).

This module owns the kernel-facing *concurrency plane* for the common VFS
runtime:

* deterministic multi-domain lock ordering over **path**, **inode**, and
  **handle** keys that prevents deadlock by construction;
* concurrent host-callback admission that is either **linearizable** under
  that lock order or returns a **typed conflict** (never silent races);
* open-handle survival for same-mount **rename** and **unlink** under an
  explicit policy (handles, not paths, identify open instances);
* hard bounds on lock tables, active callbacks, wait queues, cancellation,
  and shutdown drain under randomized concurrency.

Conflict policy: own lock/lease primitives and open-rename/unlink policy.
Mutation integration into the operations adapter is KVFS-206 / KVFS-309.
This module does not import fusepy, open host mounts, or perform network I/O.

Interfaces (plan aliases): ``HostConcurrencyPlane@1``, ``HostLockManager@1``,
``HostCallbackGate@1``, ``OpenHandlePolicy@1``.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, ClassVar, Final, TypeVar

from ipfs_kit_py.core.vfs.handles import (
    FileHandle,
    HandleError,
    HandleErrorCode,
    HandleTable,
)
from ipfs_kit_py.core.vfs.host_contracts import (
    HostCallbackKind,
    HostErrno,
    MountLifecycleState,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

HOST_CONCURRENCY_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/host_concurrency"

HOST_CONCURRENCY_PLANE_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/host-concurrency-plane@{SCHEMA_MAJOR}"
)
HOST_LOCK_MANAGER_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/host-lock-manager@{SCHEMA_MAJOR}"
)
HOST_LOCK_KEY_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/host-lock-key@{SCHEMA_MAJOR}"
)
HOST_LOCK_GRANT_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/host-lock-grant@{SCHEMA_MAJOR}"
)
HOST_CALLBACK_GATE_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/host-callback-gate@{SCHEMA_MAJOR}"
)
HOST_CALLBACK_SESSION_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/host-callback-session@{SCHEMA_MAJOR}"
)
OPEN_HANDLE_POLICY_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/open-handle-policy@{SCHEMA_MAJOR}"
)
CONCURRENCY_TRACE_SCHEMA: Final[str] = (
    f"{HOST_CONCURRENCY_NAMESPACE}/concurrency-trace@{SCHEMA_MAJOR}"
)

# Public interface aliases.
HostConcurrencyPlane_V1: Final[str] = HOST_CONCURRENCY_PLANE_SCHEMA
HostLockManager_V1: Final[str] = HOST_LOCK_MANAGER_SCHEMA
HostCallbackGate_V1: Final[str] = HOST_CALLBACK_GATE_SCHEMA
OpenHandlePolicy_V1: Final[str] = OPEN_HANDLE_POLICY_SCHEMA

DEFAULT_MAX_GLOBAL_LOCKS: Final[int] = 16_384
DEFAULT_MAX_LOCKS_PER_OWNER: Final[int] = 1_024
DEFAULT_MAX_ACTIVE_CALLBACKS: Final[int] = 256
DEFAULT_MAX_WAITERS: Final[int] = 1_024
DEFAULT_MAX_QUEUE_DEPTH: Final[int] = 512
DEFAULT_LOCK_WAIT_MS: Final[int] = 5_000
DEFAULT_SHUTDOWN_DRAIN_MS: Final[int] = 10_000
DEFAULT_MAX_TRACE_STEPS: Final[int] = 4_096
DEFAULT_MOUNT_ID: Final[str] = "mount:default"

MAX_GLOBAL_LOCKS_HARD: Final[int] = 65_536
MAX_ACTIVE_CALLBACKS_HARD: Final[int] = 4_096
MAX_WAITERS_HARD: Final[int] = 16_384
MAX_QUEUE_DEPTH_HARD: Final[int] = 8_192
MAX_OWNER_ID_BYTES: Final[int] = 512
MAX_PATH_BYTES: Final[int] = 4_096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class LockDomain(IntEnum):
    """Lock domains in **total acquisition order**.

    Acquisition always proceeds PATH → INODE → HANDLE. Within a domain, keys
    are ordered deterministically (UTF-8 path bytes; numeric inode/handle ids).
    Callers that request locks out of order still acquire them in this order,
    so cross-callback deadlock cannot form from lock inversion.
    """

    PATH = 0
    INODE = 1
    HANDLE = 2


class LockMode(str, Enum):
    """Shared / exclusive lock modes with upgrade rules."""

    SHARED = "shared"
    EXCLUSIVE = "exclusive"


class ConflictReason(str, Enum):
    """Typed reasons when a callback cannot linearize."""

    LOCK_HELD = "lock_held"
    LOCK_DEADLOCK = "lock_deadlock"
    LOCK_WAIT_TIMEOUT = "lock_wait_timeout"
    LOCK_BOUND = "lock_bound"
    CALLBACK_BOUND = "callback_bound"
    QUEUE_BOUND = "queue_bound"
    WAITER_BOUND = "waiter_bound"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    CANCELLED = "cancelled"
    CROSS_MOUNT = "cross_mount"
    INVALID_STATE = "invalid_state"
    INVALID_ARGUMENT = "invalid_argument"
    INTERNAL = "internal"


class CallbackSessionState(str, Enum):
    """Lifecycle of one admitted callback session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CONFLICTED = "conflicted"
    CANCELLED = "cancelled"
    ABORTED = "aborted"


class ConcurrencyTraceKind(str, Enum):
    """Closed vocabulary for concurrency-plane executable traces."""

    ACQUIRE = "acquire"
    RELEASE = "release"
    CONFLICT = "conflict"
    WAIT = "wait"
    WAKE = "wake"
    BEGIN_CALLBACK = "begin_callback"
    END_CALLBACK = "end_callback"
    CANCEL = "cancel"
    RENAME = "rename"
    UNLINK = "unlink"
    SHUTDOWN = "shutdown"
    DRAIN = "drain"
    BOUND = "bound"
    LINEARIZE = "linearize"
    OBSERVATION = "observation"


class OpenHandleDisposition(str, Enum):
    """What happens to open handles under namespace mutation."""

    # Handles remain valid; path binding updates (rename) or unlinked flag (unlink).
    SURVIVE = "survive"
    # Reject the mutation while any handle is open (strict / Windows-share style).
    REJECT_IF_OPEN = "reject_if_open"


class ShutdownState(str, Enum):
    """Plane-level shutdown lifecycle."""

    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HostConcurrencyError(Exception):
    """Fail-closed concurrency-plane error with stable typed reason."""

    def __init__(
        self,
        message: str,
        *,
        reason: ConflictReason,
        errno: HostErrno = HostErrno.EBUSY,
        owner_id: str = "",
        session_id: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason if isinstance(reason, ConflictReason) else ConflictReason(reason)
        self.errno = errno if isinstance(errno, HostErrno) else HostErrno(errno)
        self.owner_id = owner_id
        self.session_id = session_id
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.reason.value,
            "message": self.message,
            "errno": self.errno.value,
            "owner_id": self.owner_id,
            "session_id": self.session_id,
            "detail": dict(self.detail),
        }


class HostLockConflictError(HostConcurrencyError):
    """Lock acquisition conflict or would-be deadlock."""

    def __init__(
        self,
        message: str,
        *,
        reason: ConflictReason = ConflictReason.LOCK_HELD,
        keys: Sequence["HostLockKey"] | Sequence[str] = (),
        owner_ids: Sequence[str] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(message, reason=reason, **kwargs)
        self.keys = tuple(keys)
        self.owner_ids = tuple(owner_ids)
        self.detail = {
            **self.detail,
            "keys": [k.to_record() if isinstance(k, HostLockKey) else str(k) for k in self.keys],
            "owner_ids": list(self.owner_ids),
        }


class HostCallbackConflictError(HostConcurrencyError):
    """Callback could not be linearized; typed conflict for the caller."""


class HostShutdownError(HostConcurrencyError):
    """Operation rejected because the plane is draining or stopped."""


# ---------------------------------------------------------------------------
# Lock keys / grants
# ---------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class HostLockKey:
    """One lockable resource under the global domain order.

    Ordering is ``(domain, path_or_empty, numeric_id)`` so path keys sort by
    UTF-8 bytes via the path field, and inode/handle keys sort by id.
    """

    SCHEMA: ClassVar[str] = HOST_LOCK_KEY_SCHEMA

    domain: LockDomain
    path: str = ""
    resource_id: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.domain, LockDomain):
            object.__setattr__(self, "domain", LockDomain(int(self.domain)))
        if self.domain is LockDomain.PATH:
            if not isinstance(self.path, str):
                raise TypeError("path lock requires a string path")
            if len(self.path.encode("utf-8")) > MAX_PATH_BYTES:
                raise ValueError(f"path exceeds MAX_PATH_BYTES ({MAX_PATH_BYTES})")
            object.__setattr__(self, "resource_id", 0)
        else:
            rid = int(self.resource_id)
            if rid < 0 or rid > MAX_SAFE_INTEGER:
                raise ValueError("resource_id out of range")
            object.__setattr__(self, "resource_id", rid)
            object.__setattr__(self, "path", "")

    @classmethod
    def for_path(cls, path: str) -> "HostLockKey":
        return cls(domain=LockDomain.PATH, path=str(path))

    @classmethod
    def for_inode(cls, inode: int) -> "HostLockKey":
        return cls(domain=LockDomain.INODE, resource_id=int(inode))

    @classmethod
    def for_handle(cls, handle_id: int) -> "HostLockKey":
        return cls(domain=LockDomain.HANDLE, resource_id=int(handle_id))

    @property
    def sort_key(self) -> tuple[int, bytes, int]:
        if self.domain is LockDomain.PATH:
            return (int(self.domain), self.path.encode("utf-8"), 0)
        return (int(self.domain), b"", int(self.resource_id))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "domain": self.domain.name.lower(),
            "path": self.path,
            "resource_id": self.resource_id,
        }

    def __str__(self) -> str:
        if self.domain is LockDomain.PATH:
            return f"path:{self.path}"
        return f"{self.domain.name.lower()}:{self.resource_id}"


@dataclass(frozen=True)
class HostLockRequest:
    """One requested lock (key + mode)."""

    key: HostLockKey
    mode: LockMode = LockMode.EXCLUSIVE

    def __post_init__(self) -> None:
        if not isinstance(self.key, HostLockKey):
            raise TypeError("key must be HostLockKey")
        if not isinstance(self.mode, LockMode):
            object.__setattr__(self, "mode", LockMode(self.mode))


@dataclass(frozen=True)
class HostLockGrant:
    """One held lock grant."""

    SCHEMA: ClassVar[str] = HOST_LOCK_GRANT_SCHEMA

    key: HostLockKey
    mode: LockMode
    owner_id: str

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "key": self.key.to_record(),
            "mode": self.mode.value,
            "owner_id": self.owner_id,
        }


def ordered_lock_keys(*keys: HostLockKey) -> tuple[HostLockKey, ...]:
    """Deterministic total order: domain rank, then path bytes / resource id."""

    unique: dict[tuple[int, bytes, int], HostLockKey] = {}
    for key in keys:
        if key is None:
            continue
        unique[key.sort_key] = key
    return tuple(unique[k] for k in sorted(unique))


def ordered_lock_requests(
    requests: Sequence[HostLockRequest] | Iterable[HostLockRequest],
) -> tuple[HostLockRequest, ...]:
    """Order requests by key; stronger mode wins on duplicates."""

    best: dict[tuple[int, bytes, int], HostLockRequest] = {}
    for req in requests:
        sk = req.key.sort_key
        prev = best.get(sk)
        if prev is None:
            best[sk] = req
        elif prev.mode is LockMode.SHARED and req.mode is LockMode.EXCLUSIVE:
            best[sk] = req
    return tuple(best[k] for k in sorted(best))


def lock_requests_for_callback(
    *,
    paths: Sequence[str] = (),
    inodes: Sequence[int] = (),
    handle_ids: Sequence[int] = (),
    path_mode: LockMode = LockMode.EXCLUSIVE,
    inode_mode: LockMode = LockMode.EXCLUSIVE,
    handle_mode: LockMode = LockMode.EXCLUSIVE,
) -> tuple[HostLockRequest, ...]:
    """Build an ordered lock request set for a typical host callback."""

    reqs: list[HostLockRequest] = []
    for p in paths:
        if p is not None and p != "":
            reqs.append(HostLockRequest(HostLockKey.for_path(p), path_mode))
    for ino in inodes:
        reqs.append(HostLockRequest(HostLockKey.for_inode(int(ino)), inode_mode))
    for hid in handle_ids:
        reqs.append(HostLockRequest(HostLockKey.for_handle(int(hid)), handle_mode))
    return ordered_lock_requests(reqs)


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConcurrencyTraceStep:
    """One executable concurrency observation."""

    SCHEMA: ClassVar[str] = CONCURRENCY_TRACE_SCHEMA

    kind: ConcurrencyTraceKind
    success: bool
    owner_id: str = ""
    session_id: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    seq: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "seq": self.seq,
            "kind": self.kind.value,
            "success": self.success,
            "owner_id": self.owner_id,
            "session_id": self.session_id,
            "detail": dict(self.detail),
        }


class ConcurrencyTraceLog:
    """Bounded ring of concurrency-plane observations."""

    def __init__(self, *, max_steps: int = DEFAULT_MAX_TRACE_STEPS) -> None:
        self._max = max(1, int(max_steps))
        self._steps: list[ConcurrencyTraceStep] = []
        self._seq = 0
        self._lock = threading.Lock()

    def record(
        self,
        kind: ConcurrencyTraceKind,
        *,
        success: bool = True,
        owner_id: str = "",
        session_id: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> ConcurrencyTraceStep:
        with self._lock:
            self._seq += 1
            step = ConcurrencyTraceStep(
                kind=kind,
                success=success,
                owner_id=owner_id,
                session_id=session_id,
                detail=dict(detail or {}),
                seq=self._seq,
            )
            self._steps.append(step)
            if len(self._steps) > self._max:
                self._steps = self._steps[-self._max :]
            return step

    def steps(self) -> tuple[ConcurrencyTraceStep, ...]:
        with self._lock:
            return tuple(self._steps)

    def kinds(self) -> list[str]:
        return [s.kind.value for s in self.steps()]

    def clear(self) -> None:
        with self._lock:
            self._steps.clear()


# ---------------------------------------------------------------------------
# Open-handle policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenHandlePolicy:
    """Policy for rename/unlink while handles are open.

    Default production policy (plan §3.3): handles identify open instances;
    same-mount rename/unlink does **not** invalidate already-open handles.
    """

    SCHEMA: ClassVar[str] = OPEN_HANDLE_POLICY_SCHEMA

    rename_disposition: OpenHandleDisposition = OpenHandleDisposition.SURVIVE
    unlink_disposition: OpenHandleDisposition = OpenHandleDisposition.SURVIVE
    require_same_mount: bool = True
    allow_cross_mount_reject: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.rename_disposition, OpenHandleDisposition):
            object.__setattr__(
                self,
                "rename_disposition",
                OpenHandleDisposition(self.rename_disposition),
            )
        if not isinstance(self.unlink_disposition, OpenHandleDisposition):
            object.__setattr__(
                self,
                "unlink_disposition",
                OpenHandleDisposition(self.unlink_disposition),
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "rename_disposition": self.rename_disposition.value,
            "unlink_disposition": self.unlink_disposition.value,
            "require_same_mount": self.require_same_mount,
            "allow_cross_mount_reject": self.allow_cross_mount_reject,
        }


DEFAULT_OPEN_HANDLE_POLICY: Final[OpenHandlePolicy] = OpenHandlePolicy()


# ---------------------------------------------------------------------------
# Host lock manager
# ---------------------------------------------------------------------------


class HostLockManager:
    """Multi-domain lock table with deterministic order and bounded waits.

    Properties:

    * acquisition always sorts requests by :func:`ordered_lock_requests`
      (PATH → INODE → HANDLE, then key);
    * shared locks coexist; exclusive is exclusive; shared→exclusive upgrade
      is admitted only when the requester is the sole holder;
    * wait-for cycles are detected and fail closed as typed deadlock conflicts;
    * global and per-owner lock counts are hard-bounded;
    * optional timed wait is bounded; unbounded blocking is forbidden.
    """

    SCHEMA: ClassVar[str] = HOST_LOCK_MANAGER_SCHEMA

    def __init__(
        self,
        *,
        max_global_locks: int = DEFAULT_MAX_GLOBAL_LOCKS,
        max_per_owner: int = DEFAULT_MAX_LOCKS_PER_OWNER,
        max_waiters: int = DEFAULT_MAX_WAITERS,
        default_wait_ms: int = DEFAULT_LOCK_WAIT_MS,
        trace: ConcurrencyTraceLog | None = None,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if not (1 <= int(max_global_locks) <= MAX_GLOBAL_LOCKS_HARD):
            raise HostConcurrencyError(
                f"max_global_locks must be in [1, {MAX_GLOBAL_LOCKS_HARD}]",
                reason=ConflictReason.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if not (1 <= int(max_per_owner) <= MAX_GLOBAL_LOCKS_HARD):
            raise HostConcurrencyError(
                f"max_per_owner must be in [1, {MAX_GLOBAL_LOCKS_HARD}]",
                reason=ConflictReason.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if not (0 <= int(max_waiters) <= MAX_WAITERS_HARD):
            raise HostConcurrencyError(
                f"max_waiters must be in [0, {MAX_WAITERS_HARD}]",
                reason=ConflictReason.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        self._max_global = int(max_global_locks)
        self._max_per_owner = int(max_per_owner)
        self._max_waiters = int(max_waiters)
        self._default_wait_ms = max(0, int(default_wait_ms))
        self._trace = trace or ConcurrencyTraceLog()
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))

        self._cond = threading.Condition()
        # key_sort -> list of (owner_id, mode)
        self._holders: dict[tuple[int, bytes, int], list[tuple[str, LockMode]]] = {}
        self._key_by_sort: dict[tuple[int, bytes, int], HostLockKey] = {}
        # owner_id -> set of key sorts
        self._owner_keys: dict[str, set[tuple[int, bytes, int]]] = {}
        # waiter owner -> set of blocker owners (wait-for edges)
        self._waiting: dict[str, set[str]] = {}
        self._waiter_count = 0
        self._shutting_down = False

    # -- observations -------------------------------------------------------

    @property
    def global_lock_count(self) -> int:
        with self._cond:
            return sum(len(v) for v in self._holders.values())

    @property
    def max_global_locks(self) -> int:
        return self._max_global

    @property
    def max_waiters(self) -> int:
        return self._max_waiters

    @property
    def waiter_count(self) -> int:
        with self._cond:
            return self._waiter_count

    def held_keys(self, owner_id: str) -> tuple[HostLockKey, ...]:
        with self._cond:
            sorts = self._owner_keys.get(owner_id, set())
            keys = [self._key_by_sort[s] for s in sorts if s in self._key_by_sort]
            return ordered_lock_keys(*keys)

    def grants(self) -> tuple[HostLockGrant, ...]:
        with self._cond:
            out: list[HostLockGrant] = []
            for sk in sorted(self._holders):
                key = self._key_by_sort[sk]
                for owner_id, mode in self._holders[sk]:
                    out.append(HostLockGrant(key=key, mode=mode, owner_id=owner_id))
            return tuple(out)

    def mark_shutting_down(self) -> None:
        with self._cond:
            self._shutting_down = True
            self._cond.notify_all()

    # -- acquire / release --------------------------------------------------

    def acquire(
        self,
        owner_id: str,
        requests: Sequence[HostLockRequest] | Iterable[HostLockRequest],
        *,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> tuple[HostLockKey, ...]:
        """Acquire ``requests`` in deterministic order.

        Returns newly acquired keys (already-held compatible locks are skipped).
        Raises :class:`HostLockConflictError` on deadlock, timeout, bound, or
        shutdown. When ``nonblocking`` is true, conflicts fail immediately.
        """

        owner_id = self._validate_owner(owner_id)
        ordered = ordered_lock_requests(requests)
        if not ordered:
            return ()

        deadline_ms: int | None
        if nonblocking:
            deadline_ms = 0
        else:
            wait = self._default_wait_ms if wait_ms is None else max(0, int(wait_ms))
            deadline_ms = self._clock_ms() + wait if wait > 0 else 0

        with self._cond:
            if self._shutting_down:
                raise HostShutdownError(
                    "lock manager is shutting down",
                    reason=ConflictReason.SHUTTING_DOWN,
                    errno=HostErrno.EBUSY,
                    owner_id=owner_id,
                )

            # Per-owner bound foresight.
            owner_held = self._owner_keys.setdefault(owner_id, set())
            new_count = sum(1 for r in ordered if r.key.sort_key not in owner_held)
            if len(owner_held) + new_count > self._max_per_owner:
                self._trace.record(
                    ConcurrencyTraceKind.BOUND,
                    success=False,
                    owner_id=owner_id,
                    detail={"bound": "per_owner", "max": self._max_per_owner},
                )
                raise HostLockConflictError(
                    f"lock set exceeds max_per_owner ({self._max_per_owner})",
                    reason=ConflictReason.LOCK_BOUND,
                    errno=HostErrno.ENOMEM,
                    owner_id=owner_id,
                )

            newly: list[HostLockKey] = []
            for req in ordered:
                key = req.key
                sk = key.sort_key
                while True:
                    if self._shutting_down:
                        # Roll back partial acquisition for this call.
                        self._release_keys_locked(owner_id, newly)
                        raise HostShutdownError(
                            "lock manager is shutting down",
                            reason=ConflictReason.SHUTTING_DOWN,
                            errno=HostErrno.EBUSY,
                            owner_id=owner_id,
                        )

                    holders = self._holders.get(sk, [])
                    mine = [(o, m) for o, m in holders if o == owner_id]
                    others = [(o, m) for o, m in holders if o != owner_id]

                    if mine:
                        current = mine[0][1]
                        if current is LockMode.EXCLUSIVE or req.mode is LockMode.SHARED:
                            break  # already sufficient
                        # upgrade shared → exclusive: require sole holder
                        if others:
                            blockers = [o for o, _ in others]
                            if self._would_deadlock(owner_id, blockers):
                                self._release_keys_locked(owner_id, newly)
                                raise HostLockConflictError(
                                    f"upgrade would deadlock on {key}",
                                    reason=ConflictReason.LOCK_DEADLOCK,
                                    keys=(key,),
                                    owner_ids=tuple(sorted({owner_id, *blockers})),
                                    owner_id=owner_id,
                                )
                            if not self._wait_for(
                                owner_id,
                                blockers,
                                key,
                                deadline_ms=deadline_ms,
                                nonblocking=nonblocking,
                            ):
                                self._release_keys_locked(owner_id, newly)
                                raise HostLockConflictError(
                                    f"lock wait timeout upgrading {key}",
                                    reason=(
                                        ConflictReason.LOCK_HELD
                                        if nonblocking or deadline_ms == 0
                                        else ConflictReason.LOCK_WAIT_TIMEOUT
                                    ),
                                    keys=(key,),
                                    owner_ids=tuple(sorted({owner_id, *blockers})),
                                    owner_id=owner_id,
                                    errno=HostErrno.EAGAIN if nonblocking else HostErrno.EBUSY,
                                )
                            continue
                        # sole holder — upgrade
                        self._holders[sk] = [(owner_id, LockMode.EXCLUSIVE)]
                        newly.append(key)
                        break

                    # Not held by me.
                    blockers: list[str] = []
                    if req.mode is LockMode.SHARED:
                        blockers = [o for o, m in others if m is LockMode.EXCLUSIVE]
                    else:
                        blockers = [o for o, _ in others]

                    if blockers:
                        if self._would_deadlock(owner_id, blockers):
                            self._release_keys_locked(owner_id, newly)
                            self._trace.record(
                                ConcurrencyTraceKind.CONFLICT,
                                success=False,
                                owner_id=owner_id,
                                detail={
                                    "reason": ConflictReason.LOCK_DEADLOCK.value,
                                    "key": key.to_record(),
                                    "blockers": blockers,
                                },
                            )
                            raise HostLockConflictError(
                                f"lock acquisition would deadlock on {key}",
                                reason=ConflictReason.LOCK_DEADLOCK,
                                keys=(key,),
                                owner_ids=tuple(sorted({owner_id, *blockers})),
                                owner_id=owner_id,
                            )
                        if not self._wait_for(
                            owner_id,
                            blockers,
                            key,
                            deadline_ms=deadline_ms,
                            nonblocking=nonblocking,
                        ):
                            self._release_keys_locked(owner_id, newly)
                            reason = (
                                ConflictReason.LOCK_HELD
                                if nonblocking or deadline_ms == 0
                                else ConflictReason.LOCK_WAIT_TIMEOUT
                            )
                            self._trace.record(
                                ConcurrencyTraceKind.CONFLICT,
                                success=False,
                                owner_id=owner_id,
                                detail={
                                    "reason": reason.value,
                                    "key": key.to_record(),
                                    "blockers": blockers,
                                },
                            )
                            raise HostLockConflictError(
                                f"could not acquire {key}",
                                reason=reason,
                                keys=(key,),
                                owner_ids=tuple(sorted({owner_id, *blockers})),
                                owner_id=owner_id,
                                errno=HostErrno.EAGAIN if nonblocking else HostErrno.EBUSY,
                            )
                        continue

                    # Free to grant.
                    global_count = sum(len(v) for v in self._holders.values())
                    if global_count >= self._max_global and sk not in self._holders:
                        self._release_keys_locked(owner_id, newly)
                        self._trace.record(
                            ConcurrencyTraceKind.BOUND,
                            success=False,
                            owner_id=owner_id,
                            detail={"bound": "global", "max": self._max_global},
                        )
                        raise HostLockConflictError(
                            f"global lock table exceeds max_global_locks ({self._max_global})",
                            reason=ConflictReason.LOCK_BOUND,
                            keys=(key,),
                            owner_id=owner_id,
                            errno=HostErrno.ENOMEM,
                        )

                    self._holders.setdefault(sk, []).append((owner_id, req.mode))
                    self._key_by_sort[sk] = key
                    owner_held.add(sk)
                    newly.append(key)
                    break

            if newly:
                self._trace.record(
                    ConcurrencyTraceKind.ACQUIRE,
                    success=True,
                    owner_id=owner_id,
                    detail={
                        "keys": [k.to_record() for k in newly],
                        "ordered": [k.to_record() for k in ordered_lock_keys(*newly)],
                    },
                )
            return tuple(newly)

    def release_all(self, owner_id: str) -> int:
        """Release every lock held by ``owner_id``. Returns count released."""

        owner_id = self._validate_owner(owner_id)
        with self._cond:
            sorts = list(self._owner_keys.pop(owner_id, set()))
            released = 0
            for sk in sorts:
                holders = self._holders.get(sk, [])
                remaining = [(o, m) for o, m in holders if o != owner_id]
                if remaining:
                    self._holders[sk] = remaining
                else:
                    self._holders.pop(sk, None)
                    self._key_by_sort.pop(sk, None)
                released += 1
            self._waiting.pop(owner_id, None)
            for waiter, deps in list(self._waiting.items()):
                deps.discard(owner_id)
                if not deps:
                    self._waiting.pop(waiter, None)
            if released:
                self._trace.record(
                    ConcurrencyTraceKind.RELEASE,
                    success=True,
                    owner_id=owner_id,
                    detail={"released": released},
                )
            self._cond.notify_all()
            return released

    def release_keys(self, owner_id: str, keys: Sequence[HostLockKey]) -> int:
        owner_id = self._validate_owner(owner_id)
        with self._cond:
            return self._release_keys_locked(owner_id, list(keys))

    # -- internals ----------------------------------------------------------

    def _validate_owner(self, owner_id: str) -> str:
        if not isinstance(owner_id, str) or not owner_id:
            raise HostConcurrencyError(
                "owner_id must be a non-empty string",
                reason=ConflictReason.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if len(owner_id.encode("utf-8")) > MAX_OWNER_ID_BYTES:
            raise HostConcurrencyError(
                f"owner_id exceeds MAX_OWNER_ID_BYTES ({MAX_OWNER_ID_BYTES})",
                reason=ConflictReason.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        return owner_id

    def _release_keys_locked(self, owner_id: str, keys: Sequence[HostLockKey]) -> int:
        owner_held = self._owner_keys.get(owner_id)
        if owner_held is None:
            return 0
        released = 0
        for key in keys:
            sk = key.sort_key
            if sk not in owner_held:
                continue
            holders = self._holders.get(sk, [])
            remaining = [(o, m) for o, m in holders if o != owner_id]
            if remaining:
                self._holders[sk] = remaining
            else:
                self._holders.pop(sk, None)
                self._key_by_sort.pop(sk, None)
            owner_held.discard(sk)
            released += 1
        if not owner_held:
            self._owner_keys.pop(owner_id, None)
        if released:
            self._cond.notify_all()
        return released

    def _would_deadlock(self, waiter: str, blockers: Sequence[str]) -> bool:
        """Return True if adding waiter→blockers edges would create a cycle.

        Tentatively installs the edges into ``_waiting`` for the check so
        concurrent acquirers observe each other; rolls them back when no cycle
        is present so ``_wait_for`` can re-install for the actual wait.
        """

        deps = self._waiting.setdefault(waiter, set())
        added: list[str] = []
        for b in blockers:
            if b not in deps:
                deps.add(b)
                added.append(b)
        cyclic = self._has_cycle(self._waiting)
        if cyclic:
            # Leave edges installed only long enough for the raise path to
            # observe them; caller raises and does not wait.
            for b in added:
                deps.discard(b)
            if not deps:
                self._waiting.pop(waiter, None)
            return True
        # Roll back tentative edges; _wait_for re-adds for the real wait.
        for b in added:
            deps.discard(b)
        if not deps:
            self._waiting.pop(waiter, None)
        return False

    def _has_cycle(self, graph: Mapping[str, set[str]]) -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {}

        def visit(node: str) -> bool:
            color[node] = GRAY
            for nxt in graph.get(node, ()):
                c = color.get(nxt, WHITE)
                if c is GRAY:
                    return True
                if c is WHITE and visit(nxt):
                    return True
            color[node] = BLACK
            return False

        for node in list(graph):
            if color.get(node, WHITE) is WHITE and visit(node):
                return True
        return False

    def _wait_for(
        self,
        owner_id: str,
        blockers: Sequence[str],
        key: HostLockKey,
        *,
        deadline_ms: int | None,
        nonblocking: bool,
    ) -> bool:
        """Wait until blockers may have released, or fail. Returns True if retry."""

        if nonblocking or deadline_ms == 0:
            return False

        if self._waiter_count >= self._max_waiters:
            self._trace.record(
                ConcurrencyTraceKind.BOUND,
                success=False,
                owner_id=owner_id,
                detail={"bound": "waiters", "max": self._max_waiters},
            )
            raise HostLockConflictError(
                f"waiter table exceeds max_waiters ({self._max_waiters})",
                reason=ConflictReason.WAITER_BOUND,
                keys=(key,),
                owner_ids=tuple(sorted({owner_id, *blockers})),
                owner_id=owner_id,
                errno=HostErrno.ENOMEM,
            )

        # Install wait-for edges and re-check for a cycle under the live graph.
        deps = self._waiting.setdefault(owner_id, set())
        for b in blockers:
            deps.add(b)
        if self._has_cycle(self._waiting):
            self._waiting.pop(owner_id, None)
            raise HostLockConflictError(
                f"lock acquisition would deadlock on {key}",
                reason=ConflictReason.LOCK_DEADLOCK,
                keys=(key,),
                owner_ids=tuple(sorted({owner_id, *blockers})),
                owner_id=owner_id,
            )

        self._waiter_count += 1
        self._trace.record(
            ConcurrencyTraceKind.WAIT,
            success=True,
            owner_id=owner_id,
            detail={"key": key.to_record(), "blockers": list(blockers)},
        )
        try:
            now = self._clock_ms()
            remaining_ms = (deadline_ms or 0) - now
            if remaining_ms <= 0:
                return False
            # Condition.wait takes seconds.
            self._cond.wait(timeout=min(remaining_ms, 1000) / 1000.0)
            if self._shutting_down:
                return False
            # Always re-check holders after wake or partial timeout.
            return True
        finally:
            self._waiter_count = max(0, self._waiter_count - 1)
            self._waiting.pop(owner_id, None)
            self._trace.record(
                ConcurrencyTraceKind.WAKE,
                success=True,
                owner_id=owner_id,
                detail={"key": key.to_record()},
            )


# ---------------------------------------------------------------------------
# Callback gate / sessions
# ---------------------------------------------------------------------------


@dataclass
class HostCallbackSession:
    """One admitted (or conflicted) host callback under the concurrency plane."""

    SCHEMA: ClassVar[str] = HOST_CALLBACK_SESSION_SCHEMA

    session_id: str
    owner_id: str
    kind: HostCallbackKind | str
    state: CallbackSessionState = CallbackSessionState.PENDING
    paths: tuple[str, ...] = ()
    inodes: tuple[int, ...] = ()
    handle_ids: tuple[int, ...] = ()
    mount_id: str = DEFAULT_MOUNT_ID
    linearization_seq: int = 0
    started_at_ms: int = 0
    finished_at_ms: int = 0
    cancelled: bool = False
    cancel_reason: str = ""
    conflict_reason: str = ""
    result: Any = None
    error: str = ""
    acquired_keys: tuple[HostLockKey, ...] = ()

    def to_record(self) -> dict[str, Any]:
        kind = self.kind.value if isinstance(self.kind, HostCallbackKind) else str(self.kind)
        return {
            "schema": self.SCHEMA,
            "session_id": self.session_id,
            "owner_id": self.owner_id,
            "kind": kind,
            "state": self.state.value,
            "paths": list(self.paths),
            "inodes": list(self.inodes),
            "handle_ids": list(self.handle_ids),
            "mount_id": self.mount_id,
            "linearization_seq": self.linearization_seq,
            "started_at_ms": self.started_at_ms,
            "finished_at_ms": self.finished_at_ms,
            "cancelled": self.cancelled,
            "cancel_reason": self.cancel_reason,
            "conflict_reason": self.conflict_reason,
            "error": self.error,
            "acquired_keys": [k.to_record() for k in self.acquired_keys],
        }


class HostCallbackGate:
    """Admits concurrent host callbacks with linearization or typed conflict.

    Each :meth:`run` call:

    1. checks shutdown / admission bounds;
    2. acquires the ordered path/inode/handle lock set;
    3. assigns a monotonic linearization sequence;
    4. runs the body;
    5. releases locks and records completion.

    Conflicts (lock, bound, cancel, shutdown) surface as
    :class:`HostCallbackConflictError` rather than silent races.
    """

    SCHEMA: ClassVar[str] = HOST_CALLBACK_GATE_SCHEMA

    def __init__(
        self,
        locks: HostLockManager,
        *,
        max_active: int = DEFAULT_MAX_ACTIVE_CALLBACKS,
        max_queue_depth: int = DEFAULT_MAX_QUEUE_DEPTH,
        trace: ConcurrencyTraceLog | None = None,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if not (1 <= int(max_active) <= MAX_ACTIVE_CALLBACKS_HARD):
            raise HostConcurrencyError(
                f"max_active must be in [1, {MAX_ACTIVE_CALLBACKS_HARD}]",
                reason=ConflictReason.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        if not (0 <= int(max_queue_depth) <= MAX_QUEUE_DEPTH_HARD):
            raise HostConcurrencyError(
                f"max_queue_depth must be in [0, {MAX_QUEUE_DEPTH_HARD}]",
                reason=ConflictReason.INVALID_ARGUMENT,
                errno=HostErrno.EINVAL,
            )
        self._locks = locks
        self._max_active = int(max_active)
        self._max_queue = int(max_queue_depth)
        self._trace = trace or ConcurrencyTraceLog()
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))

        self._guard = threading.RLock()
        self._active: dict[str, HostCallbackSession] = {}
        self._queued: list[str] = []  # session ids waiting for admission
        self._linearization_seq = 0
        self._shutdown_state = ShutdownState.RUNNING
        self._cancel_flags: dict[str, str] = {}  # session_id -> reason
        self._cond = threading.Condition(self._guard)

    @property
    def active_count(self) -> int:
        with self._guard:
            return len(self._active)

    @property
    def queue_depth(self) -> int:
        with self._guard:
            return len(self._queued)

    @property
    def max_active(self) -> int:
        return self._max_active

    @property
    def max_queue_depth(self) -> int:
        return self._max_queue

    @property
    def shutdown_state(self) -> ShutdownState:
        with self._guard:
            return self._shutdown_state

    @property
    def linearization_seq(self) -> int:
        with self._guard:
            return self._linearization_seq

    def begin(
        self,
        *,
        kind: HostCallbackKind | str,
        paths: Sequence[str] = (),
        inodes: Sequence[int] = (),
        handle_ids: Sequence[int] = (),
        mount_id: str = DEFAULT_MOUNT_ID,
        owner_id: str | None = None,
        path_mode: LockMode = LockMode.EXCLUSIVE,
        inode_mode: LockMode = LockMode.EXCLUSIVE,
        handle_mode: LockMode = LockMode.EXCLUSIVE,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> HostCallbackSession:
        """Admit a callback and acquire its ordered locks (no body yet)."""

        session_id = f"cb:{uuid.uuid4().hex}"
        owner = owner_id or session_id
        kind_val: HostCallbackKind | str = kind
        if isinstance(kind, str):
            try:
                kind_val = HostCallbackKind(kind)
            except ValueError:
                kind_val = kind

        session = HostCallbackSession(
            session_id=session_id,
            owner_id=owner,
            kind=kind_val,
            paths=tuple(paths),
            inodes=tuple(int(i) for i in inodes),
            handle_ids=tuple(int(h) for h in handle_ids),
            mount_id=mount_id or DEFAULT_MOUNT_ID,
            started_at_ms=self._clock_ms(),
        )

        with self._cond:
            if self._shutdown_state is not ShutdownState.RUNNING:
                session.state = CallbackSessionState.CONFLICTED
                session.conflict_reason = ConflictReason.SHUTTING_DOWN.value
                session.finished_at_ms = self._clock_ms()
                raise HostCallbackConflictError(
                    "callback gate is not accepting work",
                    reason=ConflictReason.SHUTTING_DOWN,
                    errno=HostErrno.EBUSY,
                    owner_id=owner,
                    session_id=session_id,
                )

            # Queue admission when at capacity.
            if len(self._active) >= self._max_active:
                if len(self._queued) >= self._max_queue:
                    session.state = CallbackSessionState.CONFLICTED
                    session.conflict_reason = ConflictReason.QUEUE_BOUND.value
                    session.finished_at_ms = self._clock_ms()
                    self._trace.record(
                        ConcurrencyTraceKind.BOUND,
                        success=False,
                        owner_id=owner,
                        session_id=session_id,
                        detail={"bound": "queue", "max": self._max_queue},
                    )
                    raise HostCallbackConflictError(
                        f"callback queue exceeds max_queue_depth ({self._max_queue})",
                        reason=ConflictReason.QUEUE_BOUND,
                        errno=HostErrno.ENOMEM,
                        owner_id=owner,
                        session_id=session_id,
                    )
                if nonblocking:
                    session.state = CallbackSessionState.CONFLICTED
                    session.conflict_reason = ConflictReason.CALLBACK_BOUND.value
                    session.finished_at_ms = self._clock_ms()
                    raise HostCallbackConflictError(
                        f"active callbacks at max_active ({self._max_active})",
                        reason=ConflictReason.CALLBACK_BOUND,
                        errno=HostErrno.EAGAIN,
                        owner_id=owner,
                        session_id=session_id,
                    )
                self._queued.append(session_id)
                deadline = None
                if wait_ms is not None:
                    deadline = self._clock_ms() + max(0, int(wait_ms))
                elif wait_ms is None:
                    deadline = self._clock_ms() + DEFAULT_LOCK_WAIT_MS
                try:
                    while (
                        len(self._active) >= self._max_active
                        and self._shutdown_state is ShutdownState.RUNNING
                    ):
                        remaining = None
                        if deadline is not None:
                            remaining = (deadline - self._clock_ms()) / 1000.0
                            if remaining <= 0:
                                self._queued = [s for s in self._queued if s != session_id]
                                session.state = CallbackSessionState.CONFLICTED
                                session.conflict_reason = ConflictReason.CALLBACK_BOUND.value
                                session.finished_at_ms = self._clock_ms()
                                raise HostCallbackConflictError(
                                    "timed out waiting for callback admission",
                                    reason=ConflictReason.CALLBACK_BOUND,
                                    errno=HostErrno.EBUSY,
                                    owner_id=owner,
                                    session_id=session_id,
                                )
                        self._cond.wait(timeout=remaining)
                    if self._shutdown_state is not ShutdownState.RUNNING:
                        self._queued = [s for s in self._queued if s != session_id]
                        session.state = CallbackSessionState.CONFLICTED
                        session.conflict_reason = ConflictReason.SHUTTING_DOWN.value
                        session.finished_at_ms = self._clock_ms()
                        raise HostCallbackConflictError(
                            "callback gate shutting down during admission",
                            reason=ConflictReason.SHUTTING_DOWN,
                            errno=HostErrno.EBUSY,
                            owner_id=owner,
                            session_id=session_id,
                        )
                finally:
                    self._queued = [s for s in self._queued if s != session_id]

            self._active[session_id] = session

        # Acquire locks outside the admission map mutation where possible, but
        # still under the session lifecycle. Lock manager has its own condition.
        requests = lock_requests_for_callback(
            paths=session.paths,
            inodes=session.inodes,
            handle_ids=session.handle_ids,
            path_mode=path_mode,
            inode_mode=inode_mode,
            handle_mode=handle_mode,
        )
        try:
            with self._guard:
                pre_cancel = self._cancel_flags.get(session_id) or self._cancel_flags.get(
                    owner
                )
            if pre_cancel:
                raise HostCallbackConflictError(
                    f"callback cancelled: {pre_cancel}",
                    reason=ConflictReason.CANCELLED,
                    errno=HostErrno.ECANCELED,
                    owner_id=owner,
                    session_id=session_id,
                    detail={"cancel_reason": pre_cancel},
                )
            newly = self._locks.acquire(
                owner,
                requests,
                wait_ms=wait_ms,
                nonblocking=nonblocking,
            )
            with self._guard:
                if session_id in self._cancel_flags:
                    self._locks.release_all(owner)
                    reason = self._cancel_flags.pop(session_id, "cancelled")
                    session.cancelled = True
                    session.cancel_reason = reason
                    session.state = CallbackSessionState.CANCELLED
                    session.finished_at_ms = self._clock_ms()
                    self._active.pop(session_id, None)
                    self._cond.notify_all()
                    raise HostCallbackConflictError(
                        f"callback cancelled: {reason}",
                        reason=ConflictReason.CANCELLED,
                        errno=HostErrno.ECANCELED,
                        owner_id=owner,
                        session_id=session_id,
                    )
                self._linearization_seq += 1
                session.linearization_seq = self._linearization_seq
                session.acquired_keys = newly
                session.state = CallbackSessionState.RUNNING
                self._trace.record(
                    ConcurrencyTraceKind.BEGIN_CALLBACK,
                    success=True,
                    owner_id=owner,
                    session_id=session_id,
                    detail={
                        "kind": session.to_record()["kind"],
                        "linearization_seq": session.linearization_seq,
                        "keys": [k.to_record() for k in newly],
                    },
                )
                self._trace.record(
                    ConcurrencyTraceKind.LINEARIZE,
                    success=True,
                    owner_id=owner,
                    session_id=session_id,
                    detail={"linearization_seq": session.linearization_seq},
                )
            return session
        except HostConcurrencyError as exc:
            with self._guard:
                session.state = CallbackSessionState.CONFLICTED
                session.conflict_reason = exc.reason.value
                session.error = exc.message
                session.finished_at_ms = self._clock_ms()
                self._active.pop(session_id, None)
                self._cond.notify_all()
            if isinstance(exc, HostCallbackConflictError):
                raise
            raise HostCallbackConflictError(
                exc.message,
                reason=exc.reason,
                errno=exc.errno,
                owner_id=owner,
                session_id=session_id,
                detail=exc.detail,
            ) from exc

    def complete(
        self,
        session: HostCallbackSession,
        *,
        result: Any = None,
        error: str = "",
        aborted: bool = False,
    ) -> HostCallbackSession:
        """Release locks and finish a running session."""

        with self._guard:
            if session.state is CallbackSessionState.RUNNING:
                session.state = (
                    CallbackSessionState.ABORTED
                    if aborted
                    else CallbackSessionState.COMPLETED
                )
            session.result = result
            if error:
                session.error = error
            session.finished_at_ms = self._clock_ms()
            self._active.pop(session.session_id, None)
            self._cancel_flags.pop(session.session_id, None)
            self._trace.record(
                ConcurrencyTraceKind.END_CALLBACK,
                success=not aborted and not error,
                owner_id=session.owner_id,
                session_id=session.session_id,
                detail={
                    "state": session.state.value,
                    "linearization_seq": session.linearization_seq,
                    "error": session.error,
                },
            )
            self._cond.notify_all()
        self._locks.release_all(session.owner_id)
        return session

    def cancel(self, session_id: str, *, reason: str = "cancelled") -> bool:
        """Request cancellation of an active or about-to-run session."""

        with self._guard:
            self._cancel_flags[session_id] = reason or "cancelled"
            session = self._active.get(session_id)
            if session is not None and session.state is CallbackSessionState.RUNNING:
                session.cancelled = True
                session.cancel_reason = reason or "cancelled"
            self._trace.record(
                ConcurrencyTraceKind.CANCEL,
                success=True,
                session_id=session_id,
                detail={"reason": reason or "cancelled"},
            )
            self._cond.notify_all()
            return session is not None

    def run(
        self,
        body: Callable[[HostCallbackSession], T],
        *,
        kind: HostCallbackKind | str,
        paths: Sequence[str] = (),
        inodes: Sequence[int] = (),
        handle_ids: Sequence[int] = (),
        mount_id: str = DEFAULT_MOUNT_ID,
        owner_id: str | None = None,
        path_mode: LockMode = LockMode.EXCLUSIVE,
        inode_mode: LockMode = LockMode.EXCLUSIVE,
        handle_mode: LockMode = LockMode.EXCLUSIVE,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> tuple[HostCallbackSession, T]:
        """Begin, run ``body``, and complete — the primary linearization path."""

        session = self.begin(
            kind=kind,
            paths=paths,
            inodes=inodes,
            handle_ids=handle_ids,
            mount_id=mount_id,
            owner_id=owner_id,
            path_mode=path_mode,
            inode_mode=inode_mode,
            handle_mode=handle_mode,
            wait_ms=wait_ms,
            nonblocking=nonblocking,
        )
        try:
            if session.cancelled or session.session_id in self._cancel_flags:
                reason = session.cancel_reason or self._cancel_flags.get(
                    session.session_id, "cancelled"
                )
                raise HostCallbackConflictError(
                    f"callback cancelled: {reason}",
                    reason=ConflictReason.CANCELLED,
                    errno=HostErrno.ECANCELED,
                    owner_id=session.owner_id,
                    session_id=session.session_id,
                )
            result = body(session)
        except HostCallbackConflictError as exc:
            self.complete(session, aborted=True, error=exc.message)
            raise
        except Exception as exc:
            self.complete(session, aborted=True, error=str(exc))
            raise
        else:
            self.complete(session, result=result)
            return session, result

    def begin_shutdown(self) -> None:
        with self._cond:
            if self._shutdown_state is ShutdownState.RUNNING:
                self._shutdown_state = ShutdownState.DRAINING
            self._locks.mark_shutting_down()
            self._trace.record(
                ConcurrencyTraceKind.SHUTDOWN,
                success=True,
                detail={"state": self._shutdown_state.value, "phase": "begin"},
            )
            self._cond.notify_all()

    def wait_drained(self, *, timeout_ms: int = DEFAULT_SHUTDOWN_DRAIN_MS) -> bool:
        """Block until no active callbacks remain or timeout. Returns True if drained."""

        deadline = self._clock_ms() + max(0, int(timeout_ms))
        with self._cond:
            while self._active:
                remaining = (deadline - self._clock_ms()) / 1000.0
                if remaining <= 0:
                    self._trace.record(
                        ConcurrencyTraceKind.DRAIN,
                        success=False,
                        detail={
                            "active": len(self._active),
                            "queued": len(self._queued),
                        },
                    )
                    return False
                self._cond.wait(timeout=remaining)
            self._trace.record(
                ConcurrencyTraceKind.DRAIN,
                success=True,
                detail={"active": 0, "queued": len(self._queued)},
            )
            return True

    def finish_shutdown(self) -> None:
        with self._cond:
            self._shutdown_state = ShutdownState.STOPPED
            self._trace.record(
                ConcurrencyTraceKind.SHUTDOWN,
                success=True,
                detail={"state": self._shutdown_state.value, "phase": "finish"},
            )
            self._cond.notify_all()

    def active_sessions(self) -> tuple[HostCallbackSession, ...]:
        with self._guard:
            return tuple(self._active.values())


# ---------------------------------------------------------------------------
# Host concurrency plane (facade)
# ---------------------------------------------------------------------------


class HostConcurrencyPlane:
    """Production facade for host callback concurrency (``HostConcurrencyPlane@1``).

    Composes:

    * :class:`HostLockManager` — deterministic path/inode/handle locks;
    * :class:`HostCallbackGate` — linearizable callbacks or typed conflict;
    * :class:`OpenHandlePolicy` + :class:`HandleTable` — same-mount open
      rename/unlink survival;
    * bounded shutdown / drain.

    Mount lifecycle transitions use the host-contract vocabulary for
    observability; this plane does not mount a filesystem.
    """

    SCHEMA: ClassVar[str] = HOST_CONCURRENCY_PLANE_SCHEMA

    def __init__(
        self,
        *,
        handle_table: HandleTable | None = None,
        open_handle_policy: OpenHandlePolicy | None = None,
        max_global_locks: int = DEFAULT_MAX_GLOBAL_LOCKS,
        max_locks_per_owner: int = DEFAULT_MAX_LOCKS_PER_OWNER,
        max_active_callbacks: int = DEFAULT_MAX_ACTIVE_CALLBACKS,
        max_waiters: int = DEFAULT_MAX_WAITERS,
        max_queue_depth: int = DEFAULT_MAX_QUEUE_DEPTH,
        default_wait_ms: int = DEFAULT_LOCK_WAIT_MS,
        shutdown_drain_ms: int = DEFAULT_SHUTDOWN_DRAIN_MS,
        mount_id: str = DEFAULT_MOUNT_ID,
        clock_ms: Callable[[], int] | None = None,
        max_trace_steps: int = DEFAULT_MAX_TRACE_STEPS,
    ) -> None:
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._trace = ConcurrencyTraceLog(max_steps=max_trace_steps)
        self._mount_id = mount_id or DEFAULT_MOUNT_ID
        self._policy = open_handle_policy or DEFAULT_OPEN_HANDLE_POLICY
        self._handles = handle_table or HandleTable(
            mount_id=self._mount_id,
            clock_ms=self._clock_ms,
        )
        self._shutdown_drain_ms = int(shutdown_drain_ms)
        self._lifecycle = MountLifecycleState.READY

        self._locks = HostLockManager(
            max_global_locks=max_global_locks,
            max_per_owner=max_locks_per_owner,
            max_waiters=max_waiters,
            default_wait_ms=default_wait_ms,
            trace=self._trace,
            clock_ms=self._clock_ms,
        )
        self._gate = HostCallbackGate(
            self._locks,
            max_active=max_active_callbacks,
            max_queue_depth=max_queue_depth,
            trace=self._trace,
            clock_ms=self._clock_ms,
        )
        self._guard = threading.RLock()

    # -- accessors ----------------------------------------------------------

    @property
    def locks(self) -> HostLockManager:
        return self._locks

    @property
    def gate(self) -> HostCallbackGate:
        return self._gate

    @property
    def handles(self) -> HandleTable:
        return self._handles

    @property
    def policy(self) -> OpenHandlePolicy:
        return self._policy

    @property
    def trace(self) -> ConcurrencyTraceLog:
        return self._trace

    @property
    def mount_id(self) -> str:
        return self._mount_id

    @property
    def lifecycle(self) -> MountLifecycleState:
        return self._lifecycle

    # -- callback entry -----------------------------------------------------

    def run_callback(
        self,
        body: Callable[[HostCallbackSession], T],
        *,
        kind: HostCallbackKind | str,
        paths: Sequence[str] = (),
        inodes: Sequence[int] = (),
        handle_ids: Sequence[int] = (),
        mount_id: str | None = None,
        owner_id: str | None = None,
        path_mode: LockMode = LockMode.EXCLUSIVE,
        inode_mode: LockMode = LockMode.EXCLUSIVE,
        handle_mode: LockMode = LockMode.EXCLUSIVE,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> tuple[HostCallbackSession, T]:
        """Linearize ``body`` under ordered path/inode/handle locks."""

        return self._gate.run(
            body,
            kind=kind,
            paths=paths,
            inodes=inodes,
            handle_ids=handle_ids,
            mount_id=mount_id or self._mount_id,
            owner_id=owner_id,
            path_mode=path_mode,
            inode_mode=inode_mode,
            handle_mode=handle_mode,
            wait_ms=wait_ms,
            nonblocking=nonblocking,
        )

    def cancel_callback(self, session_id: str, *, reason: str = "cancelled") -> bool:
        return self._gate.cancel(session_id, reason=reason)

    # -- open-rename / open-unlink ------------------------------------------

    def rename_path(
        self,
        source: str,
        target: str,
        *,
        source_mount_id: str | None = None,
        target_mount_id: str | None = None,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> dict[str, Any]:
        """Same-mount rename that preserves open handles per policy.

        Acquires path locks for source and target in deterministic order, then
        the inode lock for the source inode, and updates the handle table.
        """

        src_mount = source_mount_id or self._mount_id
        dst_mount = target_mount_id or self._mount_id
        if self._policy.require_same_mount and src_mount != dst_mount:
            raise HostCallbackConflictError(
                f"cross-mount rename rejected: {src_mount!r} -> {dst_mount!r}",
                reason=ConflictReason.CROSS_MOUNT,
                errno=HostErrno.EXDEV,
                detail={"source_mount_id": src_mount, "target_mount_id": dst_mount},
            )

        def body(session: HostCallbackSession) -> dict[str, Any]:
            # Resolve inode under path locks.
            ino = self._handles.lookup_inode(source)
            if ino is None:
                raise HandleError(
                    f"rename source not found: {source!r}",
                    code=HandleErrorCode.NOT_FOUND,
                    path=source,
                    errno=HostErrno.ENOENT,
                )
            # Take inode lock as well (already requested if known; else acquire).
            self._locks.acquire(
                session.owner_id,
                [HostLockRequest(HostLockKey.for_inode(ino), LockMode.EXCLUSIVE)],
                wait_ms=wait_ms,
                nonblocking=nonblocking,
            )
            open_count = sum(
                1
                for h in self._handles.open_handles()
                if h.inode == ino and not h.released
            )
            if (
                self._policy.rename_disposition is OpenHandleDisposition.REJECT_IF_OPEN
                and open_count > 0
            ):
                raise HostCallbackConflictError(
                    f"rename rejected while {open_count} handle(s) open",
                    reason=ConflictReason.LOCK_HELD,
                    errno=HostErrno.EBUSY,
                    owner_id=session.owner_id,
                    session_id=session.session_id,
                    detail={"open_count": open_count, "inode": ino},
                )
            detail = self._handles.notify_rename(source, target)
            detail = {
                **detail,
                "policy": self._policy.rename_disposition.value,
                "source_mount_id": src_mount,
                "target_mount_id": dst_mount,
                "open_handles_survived": open_count,
                "handle_still_valid": True
                if self._policy.rename_disposition is OpenHandleDisposition.SURVIVE
                else open_count == 0,
            }
            self._trace.record(
                ConcurrencyTraceKind.RENAME,
                success=True,
                owner_id=session.owner_id,
                session_id=session.session_id,
                detail=detail,
            )
            return detail

        # Path locks only at begin; inode acquired inside once known.
        _session, result = self.run_callback(
            body,
            kind=HostCallbackKind.RENAME,
            paths=(source, target),
            mount_id=src_mount,
            wait_ms=wait_ms,
            nonblocking=nonblocking,
        )
        return result

    def unlink_path(
        self,
        path: str,
        *,
        mount_id: str | None = None,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> dict[str, Any]:
        """Same-mount unlink that preserves open handles per policy."""

        mnt = mount_id or self._mount_id

        def body(session: HostCallbackSession) -> dict[str, Any]:
            ino = self._handles.lookup_inode(path)
            if ino is None:
                raise HandleError(
                    f"unlink path not found: {path!r}",
                    code=HandleErrorCode.NOT_FOUND,
                    path=path,
                    errno=HostErrno.ENOENT,
                )
            self._locks.acquire(
                session.owner_id,
                [HostLockRequest(HostLockKey.for_inode(ino), LockMode.EXCLUSIVE)],
                wait_ms=wait_ms,
                nonblocking=nonblocking,
            )
            open_count = sum(
                1
                for h in self._handles.open_handles()
                if h.inode == ino and not h.released
            )
            if (
                self._policy.unlink_disposition is OpenHandleDisposition.REJECT_IF_OPEN
                and open_count > 0
            ):
                raise HostCallbackConflictError(
                    f"unlink rejected while {open_count} handle(s) open",
                    reason=ConflictReason.LOCK_HELD,
                    errno=HostErrno.EBUSY,
                    owner_id=session.owner_id,
                    session_id=session.session_id,
                    detail={"open_count": open_count, "inode": ino},
                )
            detail = self._handles.notify_unlink(path)
            detail = {
                **detail,
                "policy": self._policy.unlink_disposition.value,
                "mount_id": mnt,
                "open_handles_survived": open_count,
            }
            self._trace.record(
                ConcurrencyTraceKind.UNLINK,
                success=True,
                owner_id=session.owner_id,
                session_id=session.session_id,
                detail=detail,
            )
            return detail

        _session, result = self.run_callback(
            body,
            kind=HostCallbackKind.UNLINK,
            paths=(path,),
            mount_id=mnt,
            wait_ms=wait_ms,
            nonblocking=nonblocking,
        )
        return result

    # -- handle helpers under locks -----------------------------------------

    def open_file(
        self,
        path: str,
        flags: Any,
        *,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> FileHandle:
        """Open a path under ordered path (+inode when known) locks."""

        def body(session: HostCallbackSession) -> FileHandle:
            fh = self._handles.open(path, flags)
            # Also hold handle lock for the issued id for the duration of open.
            self._locks.acquire(
                session.owner_id,
                [
                    HostLockRequest(HostLockKey.for_inode(fh.inode), LockMode.SHARED),
                    HostLockRequest(HostLockKey.for_handle(fh.handle_id), LockMode.EXCLUSIVE),
                ],
                wait_ms=wait_ms,
                nonblocking=nonblocking,
            )
            return fh

        _session, fh = self.run_callback(
            body,
            kind=HostCallbackKind.OPEN,
            paths=(path,),
            path_mode=LockMode.SHARED,
            wait_ms=wait_ms,
            nonblocking=nonblocking,
        )
        return fh

    def release_file(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
        wait_ms: int | None = None,
        nonblocking: bool = False,
    ) -> Any:
        def body(session: HostCallbackSession) -> Any:
            return self._handles.release(handle_id, generation=generation)

        _session, result = self.run_callback(
            body,
            kind=HostCallbackKind.RELEASE,
            handle_ids=(handle_id,),
            wait_ms=wait_ms,
            nonblocking=nonblocking,
        )
        return result

    # -- shutdown -----------------------------------------------------------

    def shutdown(self, *, drain: bool = True, timeout_ms: int | None = None) -> dict[str, Any]:
        """Drain in-flight callbacks (optional) and stop admitting new work."""

        with self._guard:
            self._lifecycle = MountLifecycleState.DRAINING
        self._gate.begin_shutdown()
        drained = True
        if drain:
            drained = self._gate.wait_drained(
                timeout_ms=self._shutdown_drain_ms if timeout_ms is None else int(timeout_ms)
            )
        self._gate.finish_shutdown()
        with self._guard:
            self._lifecycle = (
                MountLifecycleState.DESTROYED
                if drained
                else MountLifecycleState.FAILED
            )
        detail = {
            "drained": drained,
            "active": self._gate.active_count,
            "queue_depth": self._gate.queue_depth,
            "global_locks": self._locks.global_lock_count,
            "waiters": self._locks.waiter_count,
            "lifecycle": self._lifecycle.value,
        }
        self._trace.record(
            ConcurrencyTraceKind.SHUTDOWN,
            success=drained,
            detail=detail,
        )
        return detail

    # -- observations -------------------------------------------------------

    def pressure_snapshot(self) -> dict[str, Any]:
        return {
            "active_callbacks": self._gate.active_count,
            "queue_depth": self._gate.queue_depth,
            "max_active_callbacks": self._gate.max_active,
            "max_queue_depth": self._gate.max_queue_depth,
            "global_locks": self._locks.global_lock_count,
            "max_global_locks": self._locks.max_global_locks,
            "waiters": self._locks.waiter_count,
            "max_waiters": self._locks.max_waiters,
            "linearization_seq": self._gate.linearization_seq,
            "shutdown_state": self._gate.shutdown_state.value,
            "lifecycle": self._lifecycle.value,
            "open_handles": self._handles.open_count,
        }

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "mount_id": self._mount_id,
            "policy": self._policy.to_record(),
            "pressure": self.pressure_snapshot(),
            "lifecycle": self._lifecycle.value,
        }


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "HostConcurrencyPlane_V1",
    "HostLockManager_V1",
    "HostCallbackGate_V1",
    "OpenHandlePolicy_V1",
    "HOST_CONCURRENCY_PLANE_SCHEMA",
    "HOST_LOCK_MANAGER_SCHEMA",
    "HOST_CALLBACK_GATE_SCHEMA",
    "OPEN_HANDLE_POLICY_SCHEMA",
    "DEFAULT_MAX_GLOBAL_LOCKS",
    "DEFAULT_MAX_LOCKS_PER_OWNER",
    "DEFAULT_MAX_ACTIVE_CALLBACKS",
    "DEFAULT_MAX_WAITERS",
    "DEFAULT_MAX_QUEUE_DEPTH",
    "DEFAULT_LOCK_WAIT_MS",
    "DEFAULT_SHUTDOWN_DRAIN_MS",
    "DEFAULT_MOUNT_ID",
    "DEFAULT_OPEN_HANDLE_POLICY",
    "LockDomain",
    "LockMode",
    "ConflictReason",
    "CallbackSessionState",
    "ConcurrencyTraceKind",
    "OpenHandleDisposition",
    "ShutdownState",
    "HostConcurrencyError",
    "HostLockConflictError",
    "HostCallbackConflictError",
    "HostShutdownError",
    "HostLockKey",
    "HostLockRequest",
    "HostLockGrant",
    "ordered_lock_keys",
    "ordered_lock_requests",
    "lock_requests_for_callback",
    "ConcurrencyTraceStep",
    "ConcurrencyTraceLog",
    "OpenHandlePolicy",
    "HostLockManager",
    "HostCallbackSession",
    "HostCallbackGate",
    "HostConcurrencyPlane",
]

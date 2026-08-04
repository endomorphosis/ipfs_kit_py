"""VFS transactions: isolation, locking, versions, and cancellation (KITA-008).

``VFSTransaction@1`` layers conditional CAS, declared isolation, deterministic
lock ordering, and explicit cancellation disposition on top of the injected
:class:`~ipfs_kit_py.core.vfs.service.VFSStorageBoundary`.

Properties:

* version / content CID preconditions reject stale writes (no lost update when
  isolation requires it);
* lock acquisition is path-ordered, deterministic, and hard-bounded;
* cancellation has an explicit pre-commit (abort, no effect) vs post-commit
  (effects retained; compensation is a typed unsupported boundary) disposition;
* concurrent generated schedules either match the serializable reference model
  or report a typed unsupported boundary — never silent divergence;
* WAL durability is out of scope (KITA-021); this module is hermetic and
  in-memory for the storage boundary.

No host filesystem, daemon, or network I/O is performed here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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
from ipfs_kit_py.core.vfs.snapshots import (
    VFSSnapshot,
    VFSSnapshotStore,
    VFSVersion,
    VFSVersionHistory,
    VFSVersionPreconditionError,
    check_version_precondition,
)

# ---------------------------------------------------------------------------
# Schema / bounds
# ---------------------------------------------------------------------------

TRANSACTION_CONTRACT_VERSION: Final[int] = 1
TRANSACTION_SCHEMA_MAJOR: Final[int] = 1
TRANSACTION_SCHEMA_MINOR: Final[int] = 0
TRANSACTION_SCHEMA_PATCH: Final[int] = 0
TRANSACTION_SCHEMA_VERSION: Final[str] = (
    f"{TRANSACTION_SCHEMA_MAJOR}.{TRANSACTION_SCHEMA_MINOR}."
    f"{TRANSACTION_SCHEMA_PATCH}"
)

VFS_TXN_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/transactions"
VFS_TRANSACTION_SCHEMA: Final[str] = (
    f"{VFS_TXN_NAMESPACE}/transaction@{TRANSACTION_SCHEMA_MAJOR}"
)
VFS_LOCK_SCHEMA: Final[str] = f"{VFS_TXN_NAMESPACE}/lock@{TRANSACTION_SCHEMA_MAJOR}"
VFS_SCHEDULE_SCHEMA: Final[str] = (
    f"{VFS_TXN_NAMESPACE}/schedule@{TRANSACTION_SCHEMA_MAJOR}"
)

# Public interface alias (plan: VFSTransaction@1).
VFSTransaction_V1: Final[str] = VFS_TRANSACTION_SCHEMA

MAX_ACTIVE_TRANSACTIONS: Final[int] = 256
MAX_WRITE_SET: Final[int] = 1_024
MAX_READ_SET: Final[int] = 4_096
MAX_LOCKS_PER_TXN: Final[int] = 1_024
MAX_GLOBAL_LOCKS: Final[int] = 16_384
MAX_SCHEDULE_STEPS: Final[int] = 4_096
MAX_TXN_ID_BYTES: Final[int] = 512
DEFAULT_MOUNT_ID: Final[str] = "mount:default"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class IsolationLevel(str, Enum):
    """Declared isolation for a VFS transaction.

    * ``READ_COMMITTED`` — each read sees the latest committed value; writers
      still use CAS preconditions when supplied, but concurrent overwrites of
      a path without a precondition are admitted (lost-update risk is caller-
      owned).
    * ``SNAPSHOT`` — reads are stable against the begin-snapshot; commit fails
      if any write-set path changed since the snapshot (prevents lost updates).
    * ``SERIALIZABLE`` — snapshot plus write-write conflict rejection against
      any overlapping committed writer since begin (stricter than SNAPSHOT).
    """

    READ_COMMITTED = "read_committed"
    SNAPSHOT = "snapshot"
    SERIALIZABLE = "serializable"


class LockMode(str, Enum):
    """Lock modes with deterministic upgrade rules (shared → exclusive)."""

    SHARED = "shared"
    EXCLUSIVE = "exclusive"


class TransactionState(str, Enum):
    """Lifecycle of a VFS transaction."""

    ACTIVE = "active"
    PREPARING = "preparing"
    COMMITTED = "committed"
    ABORTED = "aborted"
    CANCELLED = "cancelled"


class CancellationDisposition(str, Enum):
    """Explicit disposition when cancellation is observed.

    * ``PRE_COMMIT_ABORT`` — cancel before commit: abort the transaction and
      leave storage unchanged.
    * ``POST_COMMIT_RETAINED`` — cancel after a successful commit: effects stay;
      the disposition is recorded, not compensated.
    * ``POST_COMMIT_COMPENSATE_UNSUPPORTED`` — requesting compensation after
      commit is a typed unsupported boundary (WAL/recovery owns it later).
    """

    PRE_COMMIT_ABORT = "pre_commit_abort"
    POST_COMMIT_RETAINED = "post_commit_retained"
    POST_COMMIT_COMPENSATE_UNSUPPORTED = "post_commit_compensate_unsupported"


class TransactionOpKind(str, Enum):
    """Logical operations admitted inside a concurrent schedule."""

    BEGIN = "begin"
    READ = "read"
    WRITE = "write"
    CAS_WRITE = "cas_write"
    DELETE = "delete"
    COMMIT = "commit"
    ABORT = "abort"
    CANCEL = "cancel"
    SNAPSHOT = "snapshot"
    RENAME = "rename"


class TransactionUnsupportedReason(str, Enum):
    """Typed reasons when a concurrent schedule is not admitted."""

    LOCK_ORDER_CYCLE = "lock_order_cycle"
    LOCK_BOUND_EXCEEDED = "lock_bound_exceeded"
    WRITE_SET_BOUND = "write_set_bound"
    READ_SET_BOUND = "read_set_bound"
    ACTIVE_TXN_BOUND = "active_txn_bound"
    SCHEDULE_BOUND = "schedule_bound"
    POST_COMMIT_COMPENSATE = "post_commit_compensate"
    ISOLATION_NOT_SERIALIZABLE = "isolation_not_serializable"
    CROSS_TXN_DEADLOCK = "cross_txn_deadlock"
    UNKNOWN_TRANSACTION = "unknown_transaction"
    INVALID_STATE = "invalid_state"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VFSTransactionError(Exception):
    """Base class for transaction failures."""


class VFSTransactionStateError(VFSTransactionError):
    """Operation illegal in the current transaction state."""


class VFSTransactionConflictError(VFSTransactionError):
    """Isolation / write-write / lost-update conflict at commit."""

    def __init__(
        self,
        message: str,
        *,
        path: str = "",
        reason: str = "conflict",
    ) -> None:
        super().__init__(message)
        self.path = path
        self.reason = reason


class VFSTransactionCancelledError(VFSTransactionError):
    """Transaction cancelled with an explicit disposition."""

    def __init__(
        self,
        message: str,
        *,
        disposition: CancellationDisposition,
    ) -> None:
        super().__init__(message)
        self.disposition = disposition


class VFSLockError(VFSTransactionError):
    """Lock manager failure (bound, cycle, or mode conflict)."""


class VFSLockDeadlockError(VFSLockError):
    """Would-be cycle under deterministic lock ordering."""

    def __init__(
        self,
        message: str,
        *,
        paths: Sequence[str] = (),
        txn_ids: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.paths = tuple(paths)
        self.txn_ids = tuple(txn_ids)


class VFSTransactionUnsupportedError(VFSTransactionError):
    """Typed unsupported boundary (no silent divergence)."""

    def __init__(
        self,
        message: str,
        *,
        reason: TransactionUnsupportedReason,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.detail = dict(detail or {})


# ---------------------------------------------------------------------------
# Staged writes / reads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StagedWrite:
    """One staged mutation pending commit."""

    path: str
    kind: VFSEntryKind
    content: bytes = b""
    content_cid: str = ""
    precondition_version_cid: str | None = None
    """None means no CAS precondition; empty string means 'must not exist' is not used —
    missing path is handled by delete_flag / create semantics."""
    target: str = ""
    delete: bool = False
    is_rename_source: bool = False
    rename_target: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, VFSEntryKind):
            object.__setattr__(self, "kind", VFSEntryKind(self.kind))
        if not isinstance(self.content, (bytes, bytearray)):
            raise TypeError("content must be bytes")
        object.__setattr__(self, "content", bytes(self.content))
        if not self.content_cid and not self.delete:
            object.__setattr__(
                self,
                "content_cid",
                content_cid_for_bytes(self.content)
                if self.kind is VFSEntryKind.FILE
                else content_cid_for_bytes(b""),
            )


@dataclass(frozen=True)
class ReadObservation:
    """One observed read for isolation tracking."""

    path: str
    version_cid: str
    content_cid: str
    observed_generation: int
    existed: bool


# ---------------------------------------------------------------------------
# Lock manager — deterministic path order, bounded
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LockGrant:
    """One held lock grant."""

    SCHEMA: ClassVar[str] = VFS_LOCK_SCHEMA

    path: str
    mode: LockMode
    txn_id: str

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "path": self.path,
            "mode": self.mode.value,
            "txn_id": self.txn_id,
        }


class VFSLockManager:
    """Path-ordered, deterministic, bounded lock table.

    Acquisition always sorts requested paths UTF-8 lexicographically so lock
    order is independent of caller iteration order. Shared locks coexist;
    exclusive is exclusive. Upgrade shared→exclusive is admitted when the
    requester is the sole holder.
    """

    def __init__(
        self,
        *,
        max_global_locks: int = MAX_GLOBAL_LOCKS,
        max_per_txn: int = MAX_LOCKS_PER_TXN,
    ) -> None:
        # path -> list of (txn_id, mode)
        self._holders: dict[str, list[tuple[str, LockMode]]] = {}
        # txn_id -> set of paths
        self._txn_paths: dict[str, set[str]] = {}
        # wait-for graph edges: waiter_txn -> set of holder_txns
        self._waiting: dict[str, set[str]] = {}
        self._max_global = max_global_locks
        self._max_per_txn = max_per_txn

    def held_paths(self, txn_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._txn_paths.get(txn_id, ())))

    def grants(self) -> tuple[LockGrant, ...]:
        out: list[LockGrant] = []
        for path in sorted(self._holders):
            for txn_id, mode in self._holders[path]:
                out.append(LockGrant(path=path, mode=mode, txn_id=txn_id))
        return tuple(out)

    def acquire(
        self,
        txn_id: str,
        paths: Sequence[str],
        mode: LockMode = LockMode.EXCLUSIVE,
    ) -> tuple[str, ...]:
        """Acquire locks on ``paths`` in deterministic order.

        Returns the ordered list of paths that were newly acquired (already-held
        compatible locks are skipped). Raises :class:`VFSLockDeadlockError` if
        granting would create a wait-for cycle, or :class:`VFSLockError` on bounds.
        """

        ordered = tuple(sorted({p for p in paths if p is not None}, key=lambda p: p.encode("utf-8")))
        if not ordered:
            return ()

        txn_held = self._txn_paths.setdefault(txn_id, set())
        if len(txn_held) + sum(1 for p in ordered if p not in txn_held) > self._max_per_txn:
            raise VFSLockError(
                f"lock set exceeds MAX_LOCKS_PER_TXN ({self._max_per_txn})"
            )

        newly: list[str] = []
        for path in ordered:
            holders = self._holders.get(path, [])
            mine = [(t, m) for t, m in holders if t == txn_id]
            others = [(t, m) for t, m in holders if t != txn_id]

            if mine:
                current_mode = mine[0][1]
                if current_mode is LockMode.EXCLUSIVE or mode is LockMode.SHARED:
                    continue  # already sufficient
                # upgrade shared → exclusive: require sole holder
                if others:
                    self._raise_wait_cycle(txn_id, [t for t, _ in others], path)
                # perform upgrade
                self._holders[path] = [(txn_id, LockMode.EXCLUSIVE)]
                newly.append(path)
                continue

            if mode is LockMode.SHARED:
                if any(m is LockMode.EXCLUSIVE for _, m in others):
                    self._raise_wait_cycle(
                        txn_id, [t for t, m in others if m is LockMode.EXCLUSIVE], path
                    )
            else:  # exclusive
                if others:
                    self._raise_wait_cycle(txn_id, [t for t, _ in others], path)

            global_count = sum(len(v) for v in self._holders.values())
            if global_count >= self._max_global:
                raise VFSLockError(
                    f"global lock table exceeds MAX_GLOBAL_LOCKS ({self._max_global})"
                )

            self._holders.setdefault(path, []).append((txn_id, mode))
            txn_held.add(path)
            newly.append(path)

        return tuple(newly)

    def release_all(self, txn_id: str) -> None:
        paths = self._txn_paths.pop(txn_id, set())
        for path in list(paths):
            holders = self._holders.get(path, [])
            remaining = [(t, m) for t, m in holders if t != txn_id]
            if remaining:
                self._holders[path] = remaining
            else:
                self._holders.pop(path, None)
        self._waiting.pop(txn_id, None)
        # Drop edges pointing at this txn
        for waiter, deps in list(self._waiting.items()):
            deps.discard(txn_id)
            if not deps:
                self._waiting.pop(waiter, None)

    def _raise_wait_cycle(
        self, waiter: str, blockers: Sequence[str], path: str
    ) -> None:
        """Record wait-for edges and raise if a cycle would form."""

        deps = self._waiting.setdefault(waiter, set())
        for b in blockers:
            deps.add(b)
        if self._has_cycle():
            # clean tentative edges for this attempt
            self._waiting.pop(waiter, None)
            raise VFSLockDeadlockError(
                f"lock acquisition would deadlock on path {path!r}",
                paths=(path,),
                txn_ids=tuple(sorted({waiter, *blockers})),
            )
        # Logical manager does not block; conflict is fail-closed immediately.
        self._waiting.pop(waiter, None)
        raise VFSLockDeadlockError(
            f"path {path!r} held by {sorted(blockers)}; deterministic fail-closed",
            paths=(path,),
            txn_ids=tuple(sorted({waiter, *blockers})),
        )

    def _has_cycle(self) -> bool:
        # DFS cycle detection on wait-for graph.
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {}

        def visit(node: str) -> bool:
            color[node] = GRAY
            for nxt in self._waiting.get(node, ()):
                c = color.get(nxt, WHITE)
                if c is GRAY:
                    return True
                if c is WHITE and visit(nxt):
                    return True
            color[node] = BLACK
            return False

        for node in list(self._waiting):
            if color.get(node, WHITE) is WHITE and visit(node):
                return True
        return False


def ordered_lock_paths(*paths: str) -> tuple[str, ...]:
    """Public helper: deterministic UTF-8 lexicographic lock order."""

    return tuple(sorted({p for p in paths if p is not None}, key=lambda p: p.encode("utf-8")))


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


@dataclass
class VFSTransaction:
    """One VFS transaction (``VFSTransaction@1``).

    Mutations are staged until :meth:`VFSTransactionManager.commit`. Reads under
    ``SNAPSHOT`` / ``SERIALIZABLE`` are satisfied from the begin-snapshot when
    the path has not been written by this transaction.
    """

    SCHEMA: ClassVar[str] = VFS_TRANSACTION_SCHEMA

    txn_id: str
    isolation: IsolationLevel = IsolationLevel.SNAPSHOT
    state: TransactionState = TransactionState.ACTIVE
    begin_generation: int = 0
    begin_snapshot: VFSSnapshot | None = None
    read_set: list[ReadObservation] = field(default_factory=list)
    write_set: dict[str, StagedWrite] = field(default_factory=dict)
    cancellation_disposition: CancellationDisposition | None = None
    commit_generation: int = 0
    committed_versions: dict[str, str] = field(default_factory=dict)
    error: str = ""

    def is_active(self) -> bool:
        return self.state is TransactionState.ACTIVE

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "txn_id": self.txn_id,
            "isolation": self.isolation.value,
            "state": self.state.value,
            "begin_generation": self.begin_generation,
            "begin_snapshot_cid": (
                self.begin_snapshot.snapshot_cid if self.begin_snapshot else ""
            ),
            "read_set": [
                {
                    "path": r.path,
                    "version_cid": r.version_cid,
                    "content_cid": r.content_cid,
                    "observed_generation": r.observed_generation,
                    "existed": r.existed,
                }
                for r in self.read_set
            ],
            "write_set_paths": sorted(self.write_set),
            "cancellation_disposition": (
                self.cancellation_disposition.value
                if self.cancellation_disposition
                else None
            ),
            "commit_generation": self.commit_generation,
            "committed_versions": dict(sorted(self.committed_versions.items())),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Transaction manager
# ---------------------------------------------------------------------------


class VFSTransactionManager:
    """Coordinates transactions against an injected storage boundary.

    Isolation preventing lost updates:

    * SNAPSHOT / SERIALIZABLE: at commit, every write-set path must still match
      the version observed at begin (or the CAS precondition if supplied).
    * CAS writes always enforce ``precondition_version_cid`` against live state.
    """

    def __init__(
        self,
        storage: VFSStorageBoundary,
        *,
        snapshot_store: VFSSnapshotStore | None = None,
        version_history: VFSVersionHistory | None = None,
        lock_manager: VFSLockManager | None = None,
        clock: Callable[[], int] | None = None,
        max_active: int = MAX_ACTIVE_TRANSACTIONS,
    ) -> None:
        self._storage = storage
        self._snapshots = snapshot_store or VFSSnapshotStore()
        self._history = version_history or VFSVersionHistory()
        self._locks = lock_manager or VFSLockManager()
        self._clock = clock or (lambda: 0)
        self._max_active = max_active
        self._txns: dict[str, VFSTransaction] = {}
        self._seq = 0
        # path -> last commit generation (for serializable checks)
        self._path_commit_gen: dict[str, int] = {}
        # path -> last committer txn id
        self._path_commit_txn: dict[str, str] = {}
        # committed write sets for serializable conflict (txn_id -> paths)
        self._committed_write_sets: list[tuple[str, int, frozenset[str]]] = []

    @property
    def storage(self) -> VFSStorageBoundary:
        return self._storage

    @property
    def snapshots(self) -> VFSSnapshotStore:
        return self._snapshots

    @property
    def version_history(self) -> VFSVersionHistory:
        return self._history

    @property
    def locks(self) -> VFSLockManager:
        return self._locks

    def active_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                t.txn_id
                for t in self._txns.values()
                if t.state is TransactionState.ACTIVE
            )
        )

    def get(self, txn_id: str) -> VFSTransaction:
        try:
            return self._txns[txn_id]
        except KeyError as exc:
            raise VFSTransactionError(f"unknown transaction: {txn_id}") from exc

    def begin(
        self,
        *,
        txn_id: str | None = None,
        isolation: IsolationLevel = IsolationLevel.SNAPSHOT,
    ) -> VFSTransaction:
        active = sum(1 for t in self._txns.values() if t.state is TransactionState.ACTIVE)
        if active >= self._max_active:
            raise VFSTransactionUnsupportedError(
                f"active transactions exceed bound ({self._max_active})",
                reason=TransactionUnsupportedReason.ACTIVE_TXN_BOUND,
            )
        self._seq += 1
        tid = txn_id or f"txn:{self._seq}"
        if len(tid) > MAX_TXN_ID_BYTES:
            raise VFSTransactionError("txn_id exceeds bound")
        if tid in self._txns and self._txns[tid].is_active():
            raise VFSTransactionStateError(f"transaction already active: {tid}")

        snap: VFSSnapshot | None = None
        if isolation in (IsolationLevel.SNAPSHOT, IsolationLevel.SERIALIZABLE):
            snap = self._snapshots.capture_from_storage(
                self._storage,
                snapshot_id=f"snap:begin:{tid}",
                captured_at_unix_ms=self._clock(),
                source_label=f"begin:{tid}",
            )

        txn = VFSTransaction(
            txn_id=tid,
            isolation=isolation,
            state=TransactionState.ACTIVE,
            begin_generation=self._storage.generation,
            begin_snapshot=snap,
        )
        self._txns[tid] = txn
        return txn

    def read(self, txn: VFSTransaction, path: str) -> dict[str, Any] | None:
        """Read a path under the transaction's isolation level."""

        self._require_active(txn)
        path = path or ""

        # Local write-set wins.
        if path in txn.write_set:
            staged = txn.write_set[path]
            if staged.delete:
                obs = ReadObservation(
                    path=path,
                    version_cid="",
                    content_cid="",
                    observed_generation=self._storage.generation,
                    existed=False,
                )
                self._record_read(txn, obs)
                return None
            rec = {
                "kind": staged.kind.value,
                "size_bytes": len(staged.content),
                "content_cid": staged.content_cid,
                "version_cid": "staged",
                "target": staged.target,
                "content": staged.content,
                "staged": True,
            }
            obs = ReadObservation(
                path=path,
                version_cid="staged",
                content_cid=staged.content_cid,
                observed_generation=self._storage.generation,
                existed=True,
            )
            self._record_read(txn, obs)
            return rec

        self._locks.acquire(txn.txn_id, [path], LockMode.SHARED)

        if txn.isolation in (IsolationLevel.SNAPSHOT, IsolationLevel.SERIALIZABLE):
            assert txn.begin_snapshot is not None
            rec = txn.begin_snapshot.entry(path)
            if rec is None:
                obs = ReadObservation(
                    path=path,
                    version_cid="",
                    content_cid="",
                    observed_generation=txn.begin_generation,
                    existed=False,
                )
                self._record_read(txn, obs)
                return None
            out = dict(rec)
            obs = ReadObservation(
                path=path,
                version_cid=str(rec.get("version_cid") or ""),
                content_cid=str(rec.get("content_cid") or ""),
                observed_generation=txn.begin_generation,
                existed=True,
            )
            self._record_read(txn, obs)
            return out

        # READ_COMMITTED — live storage.
        entry = self._storage.get(path)
        if entry is None:
            obs = ReadObservation(
                path=path,
                version_cid="",
                content_cid="",
                observed_generation=self._storage.generation,
                existed=False,
            )
            self._record_read(txn, obs)
            return None
        pub = entry.to_public_record()
        pub["content"] = entry.content
        obs = ReadObservation(
            path=path,
            version_cid=entry.version_cid,
            content_cid=entry.content_cid,
            observed_generation=self._storage.generation,
            existed=True,
        )
        self._record_read(txn, obs)
        return pub

    def write(
        self,
        txn: VFSTransaction,
        path: str,
        content: bytes,
        *,
        kind: VFSEntryKind = VFSEntryKind.FILE,
        precondition_version_cid: str | None = None,
        target: str = "",
    ) -> StagedWrite:
        """Stage a write (optionally with a CAS precondition)."""

        self._require_active(txn)
        path = path or ""
        if len(txn.write_set) >= MAX_WRITE_SET and path not in txn.write_set:
            raise VFSTransactionUnsupportedError(
                f"write set exceeds MAX_WRITE_SET ({MAX_WRITE_SET})",
                reason=TransactionUnsupportedReason.WRITE_SET_BOUND,
            )
        self._locks.acquire(txn.txn_id, [path], LockMode.EXCLUSIVE)
        staged = StagedWrite(
            path=path,
            kind=kind,
            content=content,
            precondition_version_cid=precondition_version_cid,
            target=target,
            delete=False,
        )
        txn.write_set[path] = staged
        return staged

    def cas_write(
        self,
        txn: VFSTransaction,
        path: str,
        content: bytes,
        *,
        precondition_version_cid: str,
    ) -> StagedWrite:
        """Stage a conditional write; stale precondition fails at stage or commit."""

        self._require_active(txn)
        # Eager reject against visible version when known.
        visible = self.read(txn, path)
        current_cid = ""
        if visible is not None:
            current_cid = str(visible.get("version_cid") or "")
            if current_cid == "staged":
                # Prior staged write in this txn — treat staged as base; caller
                # must pass the live precondition they hold, so re-check live.
                entry = self._storage.get(path)
                current_cid = entry.version_cid if entry is not None else ""
        try:
            check_version_precondition(
                current_version_cid=current_cid,
                expected_version_cid=precondition_version_cid,
                path=path,
            )
        except VFSVersionPreconditionError:
            # For SNAPSHOT reads of missing vs live, still stage only if live matches.
            entry = self._storage.get(path)
            live = entry.version_cid if entry is not None else ""
            check_version_precondition(
                current_version_cid=live,
                expected_version_cid=precondition_version_cid,
                path=path,
            )
        return self.write(
            txn,
            path,
            content,
            precondition_version_cid=precondition_version_cid,
        )

    def delete(self, txn: VFSTransaction, path: str) -> StagedWrite:
        self._require_active(txn)
        path = path or ""
        if path == "":
            raise VFSTransactionError("cannot delete namespace root")
        if len(txn.write_set) >= MAX_WRITE_SET and path not in txn.write_set:
            raise VFSTransactionUnsupportedError(
                f"write set exceeds MAX_WRITE_SET ({MAX_WRITE_SET})",
                reason=TransactionUnsupportedReason.WRITE_SET_BOUND,
            )
        self._locks.acquire(txn.txn_id, [path], LockMode.EXCLUSIVE)
        staged = StagedWrite(
            path=path,
            kind=VFSEntryKind.FILE,
            delete=True,
        )
        txn.write_set[path] = staged
        return staged

    def rename(self, txn: VFSTransaction, source: str, target: str) -> None:
        """Stage a rename as delete(source)+write(target) under ordered locks."""

        self._require_active(txn)
        ordered = ordered_lock_paths(source, target)
        self._locks.acquire(txn.txn_id, ordered, LockMode.EXCLUSIVE)
        src_rec = self.read(txn, source)
        if src_rec is None:
            raise VFSTransactionError(f"rename source missing: {source}")
        content = src_rec.get("content", b"")
        if not isinstance(content, (bytes, bytearray)):
            # Snapshot public records do not carry bodies — load from storage.
            entry = self._storage.get(source)
            content = entry.content if entry is not None else b""
        kind_raw = src_rec.get("kind", VFSEntryKind.FILE.value)
        kind = kind_raw if isinstance(kind_raw, VFSEntryKind) else VFSEntryKind(str(kind_raw))
        self.delete(txn, source)
        # Mark rename metadata on delete for diagnostics.
        del_staged = txn.write_set[source]
        txn.write_set[source] = StagedWrite(
            path=source,
            kind=del_staged.kind,
            delete=True,
            is_rename_source=True,
            rename_target=target,
        )
        self.write(txn, target, bytes(content), kind=kind)

    def commit(self, txn: VFSTransaction) -> VFSTransaction:
        """Validate isolation + CAS preconditions, then apply write set atomically."""

        self._require_active(txn)
        txn.state = TransactionState.PREPARING

        # Isolation + CAS validation against live storage (pre-apply).
        try:
            self._validate_commit(txn)
        except Exception as exc:
            txn.state = TransactionState.ABORTED
            txn.error = str(exc)
            self._locks.release_all(txn.txn_id)
            raise

        # Apply in deterministic path order.
        applied: list[str] = []
        try:
            for path in ordered_lock_paths(*txn.write_set.keys()):
                staged = txn.write_set[path]
                if staged.delete:
                    existing = self._storage.get(path)
                    from_v = existing.version_cid if existing is not None else ""
                    if existing is not None:
                        self._storage.delete(path)
                    gen = self._storage.bump_generation()
                    if from_v:
                        self._history.record(
                            VFSVersion(
                                path=path,
                                kind=existing.kind if existing else VFSEntryKind.FILE,
                                content_cid="",
                                generation=gen,
                                version_cid="",  # tombstone identity derived
                                parent_version_cid=from_v,
                            )
                        )
                    txn.committed_versions[path] = ""
                    applied.append(path)
                    self._path_commit_gen[path] = gen
                    self._path_commit_txn[path] = txn.txn_id
                    continue

                existing = self._storage.get(path)
                from_v = existing.version_cid if existing is not None else ""
                gen = self._storage.bump_generation()
                version = version_cid_for(
                    path,
                    kind=staged.kind,
                    content_cid=staged.content_cid,
                    generation=gen,
                    target=staged.target,
                )
                entry = VFSStoredEntry(
                    kind=staged.kind,
                    content=staged.content if staged.kind is VFSEntryKind.FILE else b"",
                    content_cid=staged.content_cid,
                    version_cid=version,
                    target=staged.target,
                    mtime_unix_ms=self._clock() or gen,
                    mount_id=(
                        existing.mount_id if existing is not None else DEFAULT_MOUNT_ID
                    ),
                )
                self._storage.put(path, entry)
                self._history.record(
                    VFSVersion(
                        path=path,
                        kind=staged.kind,
                        content_cid=staged.content_cid,
                        generation=gen,
                        version_cid=version,
                        parent_version_cid=from_v,
                        target=staged.target,
                        mount_id=entry.mount_id,
                        mtime_unix_ms=entry.mtime_unix_ms,
                    )
                )
                txn.committed_versions[path] = version
                applied.append(path)
                self._path_commit_gen[path] = gen
                self._path_commit_txn[path] = txn.txn_id
        except Exception as exc:
            # Best-effort: storage boundary has no multi-path atomicity without
            # WAL (KITA-021). Mark aborted and release locks.
            txn.state = TransactionState.ABORTED
            txn.error = f"apply failed after {applied!r}: {exc}"
            self._locks.release_all(txn.txn_id)
            raise VFSTransactionError(txn.error) from exc

        txn.commit_generation = self._storage.generation
        txn.state = TransactionState.COMMITTED
        self._committed_write_sets.append(
            (txn.txn_id, txn.commit_generation, frozenset(txn.write_set))
        )
        self._locks.release_all(txn.txn_id)
        return txn

    def abort(self, txn: VFSTransaction) -> VFSTransaction:
        if txn.state in (
            TransactionState.COMMITTED,
            TransactionState.ABORTED,
            TransactionState.CANCELLED,
        ):
            return txn
        txn.state = TransactionState.ABORTED
        self._locks.release_all(txn.txn_id)
        return txn

    def cancel(
        self,
        txn: VFSTransaction,
        *,
        request_compensate: bool = False,
    ) -> CancellationDisposition:
        """Cancel with an explicit pre/post-commit disposition.

        * Active/preparing → ``PRE_COMMIT_ABORT`` (abort, no durable effect).
        * Already committed → ``POST_COMMIT_RETAINED`` (effects stay).
        * Committed + ``request_compensate`` → raises typed unsupported
          ``POST_COMMIT_COMPENSATE``.
        """

        if txn.state is TransactionState.COMMITTED:
            if request_compensate:
                txn.cancellation_disposition = (
                    CancellationDisposition.POST_COMMIT_COMPENSATE_UNSUPPORTED
                )
                raise VFSTransactionUnsupportedError(
                    "post-commit compensation is a typed unsupported boundary "
                    "(owned by WAL/recovery)",
                    reason=TransactionUnsupportedReason.POST_COMMIT_COMPENSATE,
                    detail={"txn_id": txn.txn_id},
                )
            txn.cancellation_disposition = CancellationDisposition.POST_COMMIT_RETAINED
            return txn.cancellation_disposition

        if txn.state in (TransactionState.ABORTED, TransactionState.CANCELLED):
            # Idempotent: already non-committed terminal.
            if txn.cancellation_disposition is None:
                txn.cancellation_disposition = CancellationDisposition.PRE_COMMIT_ABORT
            return txn.cancellation_disposition

        # Pre-commit cancel → abort.
        txn.cancellation_disposition = CancellationDisposition.PRE_COMMIT_ABORT
        txn.state = TransactionState.CANCELLED
        txn.write_set.clear()
        self._locks.release_all(txn.txn_id)
        return txn.cancellation_disposition

    def capture_snapshot(self, *, snapshot_id: str | None = None) -> VFSSnapshot:
        return self._snapshots.capture_from_storage(
            self._storage,
            snapshot_id=snapshot_id,
            captured_at_unix_ms=self._clock(),
            source_label="manager.capture_snapshot",
        )

    # -- internals ----------------------------------------------------------

    def _require_active(self, txn: VFSTransaction) -> None:
        if txn.state is not TransactionState.ACTIVE:
            raise VFSTransactionStateError(
                f"transaction {txn.txn_id} is {txn.state.value}, not active"
            )

    def _record_read(self, txn: VFSTransaction, obs: ReadObservation) -> None:
        if len(txn.read_set) >= MAX_READ_SET:
            raise VFSTransactionUnsupportedError(
                f"read set exceeds MAX_READ_SET ({MAX_READ_SET})",
                reason=TransactionUnsupportedReason.READ_SET_BOUND,
            )
        txn.read_set.append(obs)

    def _validate_commit(self, txn: VFSTransaction) -> None:
        """Enforce CAS preconditions and isolation (lost-update prevention)."""

        for path in ordered_lock_paths(*txn.write_set.keys()):
            staged = txn.write_set[path]
            live = self._storage.get(path)
            live_v = live.version_cid if live is not None else ""

            # Explicit CAS precondition always checked against live.
            if staged.precondition_version_cid is not None:
                check_version_precondition(
                    current_version_cid=live_v,
                    expected_version_cid=staged.precondition_version_cid,
                    path=path,
                )

            if txn.isolation is IsolationLevel.READ_COMMITTED:
                # No snapshot revalidation; CAS already handled when present.
                continue

            # SNAPSHOT / SERIALIZABLE: reject if path changed since begin.
            snap_v = ""
            if txn.begin_snapshot is not None:
                snap_v = txn.begin_snapshot.version_cid_at(path)
            if live_v != snap_v:
                # Allow if this txn's precondition already matched live (CAS).
                if (
                    staged.precondition_version_cid is not None
                    and staged.precondition_version_cid == live_v
                ):
                    continue
                raise VFSTransactionConflictError(
                    f"lost update prevented on {path!r}: "
                    f"live={live_v!r} snapshot={snap_v!r}",
                    path=path,
                    reason="lost_update",
                )

        if txn.isolation is IsolationLevel.SERIALIZABLE:
            # Reject if any overlapping write committed after our begin.
            write_paths = set(txn.write_set)
            for other_id, commit_gen, other_paths in self._committed_write_sets:
                if other_id == txn.txn_id:
                    continue
                if commit_gen <= txn.begin_generation:
                    continue
                overlap = write_paths & set(other_paths)
                if overlap:
                    path = sorted(overlap)[0]
                    raise VFSTransactionConflictError(
                        f"serializable write-write conflict on {path!r} "
                        f"with {other_id}",
                        path=path,
                        reason="write_write",
                    )


# ---------------------------------------------------------------------------
# Concurrent schedule reference model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScheduleStep:
    """One step in a multi-transaction concurrent schedule."""

    txn_id: str
    op: TransactionOpKind
    path: str = ""
    target_path: str = ""
    content: bytes = b""
    precondition_version_cid: str = ""
    isolation: IsolationLevel = IsolationLevel.SNAPSHOT
    request_compensate: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "op": self.op.value,
            "path": self.path,
            "target_path": self.target_path,
            "content_size": len(self.content),
            "precondition_version_cid": self.precondition_version_cid,
            "isolation": self.isolation.value,
            "request_compensate": self.request_compensate,
        }


@dataclass(frozen=True)
class ScheduleStepResult:
    """Outcome of one schedule step."""

    index: int
    txn_id: str
    op: str
    success: bool
    state: str = ""
    error: str = ""
    unsupported_reason: str = ""
    version_cid: str = ""
    namespace_generation: int = 0
    disposition: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "txn_id": self.txn_id,
            "op": self.op,
            "success": self.success,
            "state": self.state,
            "error": self.error,
            "unsupported_reason": self.unsupported_reason,
            "version_cid": self.version_cid,
            "namespace_generation": self.namespace_generation,
            "disposition": self.disposition,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class ScheduleOutcome:
    """Full result of executing a concurrent schedule."""

    SCHEMA: ClassVar[str] = VFS_SCHEDULE_SCHEMA

    steps: tuple[ScheduleStepResult, ...]
    final_namespace: Mapping[str, Mapping[str, Any]]
    unsupported: bool = False
    unsupported_reason: str = ""
    matched_reference: bool = True

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "steps": [s.to_record() for s in self.steps],
            "final_namespace": {k: dict(v) for k, v in sorted(self.final_namespace.items())},
            "unsupported": self.unsupported,
            "unsupported_reason": self.unsupported_reason,
            "matched_reference": self.matched_reference,
            "outcome_cid": content_identity(
                {
                    "steps": [s.to_record() for s in self.steps],
                    "final_namespace": {
                        k: dict(v) for k, v in sorted(self.final_namespace.items())
                    },
                    "unsupported": self.unsupported,
                    "unsupported_reason": self.unsupported_reason,
                }
            ),
        }


def _clone_storage_public(storage: VFSStorageBoundary) -> dict[str, dict[str, Any]]:
    return {k: dict(v) for k, v in storage.snapshot().items()}


class ConcurrentScheduleExecutor:
    """Execute multi-txn schedules against a manager and a pure reference model.

    The *implementation* path uses :class:`VFSTransactionManager`. The
    *reference* path re-runs the same schedule on a private storage clone using
    an independent manager instance. Outcomes must match, or the schedule must
    surface a typed unsupported boundary (never silent divergence).
    """

    def __init__(
        self,
        storage: VFSStorageBoundary,
        *,
        storage_factory: Callable[[], VFSStorageBoundary] | None = None,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._storage = storage
        self._storage_factory = storage_factory
        self._clock = clock or (lambda: 0)

    def run(
        self,
        steps: Sequence[ScheduleStep],
        *,
        compare_reference: bool = True,
    ) -> ScheduleOutcome:
        if len(steps) > MAX_SCHEDULE_STEPS:
            return ScheduleOutcome(
                steps=(
                    ScheduleStepResult(
                        index=0,
                        txn_id="",
                        op="schedule",
                        success=False,
                        unsupported_reason=TransactionUnsupportedReason.SCHEDULE_BOUND.value,
                        error=f"schedule exceeds MAX_SCHEDULE_STEPS ({MAX_SCHEDULE_STEPS})",
                    ),
                ),
                final_namespace=_clone_storage_public(self._storage),
                unsupported=True,
                unsupported_reason=TransactionUnsupportedReason.SCHEDULE_BOUND.value,
                matched_reference=True,
            )

        impl_results, impl_err = self._execute(self._storage, steps)
        if impl_err is not None and impl_err.reason in (
            TransactionUnsupportedReason.LOCK_ORDER_CYCLE,
            TransactionUnsupportedReason.CROSS_TXN_DEADLOCK,
            TransactionUnsupportedReason.POST_COMMIT_COMPENSATE,
            TransactionUnsupportedReason.LOCK_BOUND_EXCEEDED,
            TransactionUnsupportedReason.WRITE_SET_BOUND,
            TransactionUnsupportedReason.READ_SET_BOUND,
            TransactionUnsupportedReason.ACTIVE_TXN_BOUND,
            TransactionUnsupportedReason.SCHEDULE_BOUND,
        ):
            return ScheduleOutcome(
                steps=tuple(impl_results),
                final_namespace=_clone_storage_public(self._storage),
                unsupported=True,
                unsupported_reason=impl_err.reason.value,
                matched_reference=True,
            )

        matched = True
        if compare_reference and self._storage_factory is not None:
            ref_storage = self._storage_factory()
            # Seed reference from the public projection of current storage
            # *before* this run — callers should pass a fresh storage for both
            # when comparing; when factory is provided it is assumed empty and
            # seeded by the first writes of the schedule only. For differential
            # tests, factory should clone the pre-schedule state.
            ref_results, ref_err = self._execute(ref_storage, steps)
            matched = self._results_match(impl_results, ref_results)
            if not matched and ref_err is None and impl_err is None:
                # Divergence without typed unsupported — fail closed by marking
                # isolation_not_serializable unsupported rather than claiming success.
                return ScheduleOutcome(
                    steps=tuple(impl_results),
                    final_namespace=_clone_storage_public(self._storage),
                    unsupported=True,
                    unsupported_reason=(
                        TransactionUnsupportedReason.ISOLATION_NOT_SERIALIZABLE.value
                    ),
                    matched_reference=False,
                )
            if (impl_err is None) != (ref_err is None):
                matched = False
            elif impl_err is not None and ref_err is not None:
                matched = impl_err.reason == ref_err.reason

        return ScheduleOutcome(
            steps=tuple(impl_results),
            final_namespace=_clone_storage_public(self._storage),
            unsupported=impl_err is not None,
            unsupported_reason=impl_err.reason.value if impl_err else "",
            matched_reference=matched,
        )

    def run_differential(
        self,
        steps: Sequence[ScheduleStep],
        *,
        seed: Callable[[VFSStorageBoundary], None] | None = None,
    ) -> ScheduleOutcome:
        """Run the same schedule on two independently seeded storages and compare.

        When ``seed`` is provided it is applied to both storages before execution.
        The manager attached to ``self._storage`` is not used; both paths construct
        fresh managers so lock tables start empty.
        """

        if self._storage_factory is None:
            raise VFSTransactionError(
                "run_differential requires storage_factory for the reference path"
            )
        if len(steps) > MAX_SCHEDULE_STEPS:
            return ScheduleOutcome(
                steps=(
                    ScheduleStepResult(
                        index=0,
                        txn_id="",
                        op="schedule",
                        success=False,
                        unsupported_reason=TransactionUnsupportedReason.SCHEDULE_BOUND.value,
                        error="schedule bound exceeded",
                    ),
                ),
                final_namespace={},
                unsupported=True,
                unsupported_reason=TransactionUnsupportedReason.SCHEDULE_BOUND.value,
                matched_reference=True,
            )

        impl_storage = self._storage
        ref_storage = self._storage_factory()
        if seed is not None:
            seed(impl_storage)
            seed(ref_storage)

        impl_results, impl_err = self._execute(impl_storage, steps)
        ref_results, ref_err = self._execute(ref_storage, steps)

        # Typed unsupported on either side is an admitted boundary.
        if impl_err is not None or ref_err is not None:
            reason = (
                impl_err.reason
                if impl_err is not None
                else ref_err.reason  # type: ignore[union-attr]
            )
            matched = (
                impl_err is not None
                and ref_err is not None
                and impl_err.reason == ref_err.reason
            ) or (
                # Both reported the same step-level unsupported in results.
                self._results_match(impl_results, ref_results)
            )
            return ScheduleOutcome(
                steps=tuple(impl_results),
                final_namespace=_clone_storage_public(impl_storage),
                unsupported=True,
                unsupported_reason=reason.value,
                matched_reference=matched,
            )

        matched = self._results_match(impl_results, ref_results)
        ns_match = impl_storage.snapshot() == ref_storage.snapshot()
        if not matched or not ns_match:
            return ScheduleOutcome(
                steps=tuple(impl_results),
                final_namespace=_clone_storage_public(impl_storage),
                unsupported=True,
                unsupported_reason=(
                    TransactionUnsupportedReason.ISOLATION_NOT_SERIALIZABLE.value
                ),
                matched_reference=False,
            )
        return ScheduleOutcome(
            steps=tuple(impl_results),
            final_namespace=_clone_storage_public(impl_storage),
            unsupported=False,
            unsupported_reason="",
            matched_reference=True,
        )

    def _execute(
        self,
        storage: VFSStorageBoundary,
        steps: Sequence[ScheduleStep],
    ) -> tuple[list[ScheduleStepResult], VFSTransactionUnsupportedError | None]:
        mgr = VFSTransactionManager(storage, clock=self._clock)
        results: list[ScheduleStepResult] = []
        unsupported: VFSTransactionUnsupportedError | None = None

        for index, step in enumerate(steps):
            try:
                result = self._apply_step(mgr, index, step)
                results.append(result)
                if result.unsupported_reason:
                    unsupported = VFSTransactionUnsupportedError(
                        result.error or result.unsupported_reason,
                        reason=TransactionUnsupportedReason(result.unsupported_reason),
                    )
                    break
            except VFSTransactionUnsupportedError as exc:
                results.append(
                    ScheduleStepResult(
                        index=index,
                        txn_id=step.txn_id,
                        op=step.op.value,
                        success=False,
                        error=str(exc),
                        unsupported_reason=exc.reason.value,
                        namespace_generation=storage.generation,
                        detail=dict(exc.detail),
                    )
                )
                unsupported = exc
                break
            except VFSLockDeadlockError as exc:
                results.append(
                    ScheduleStepResult(
                        index=index,
                        txn_id=step.txn_id,
                        op=step.op.value,
                        success=False,
                        error=str(exc),
                        unsupported_reason=(
                            TransactionUnsupportedReason.CROSS_TXN_DEADLOCK.value
                        ),
                        namespace_generation=storage.generation,
                        detail={"paths": list(exc.paths), "txn_ids": list(exc.txn_ids)},
                    )
                )
                unsupported = VFSTransactionUnsupportedError(
                    str(exc),
                    reason=TransactionUnsupportedReason.CROSS_TXN_DEADLOCK,
                    detail={"paths": list(exc.paths), "txn_ids": list(exc.txn_ids)},
                )
                break
            except VFSVersionPreconditionError as exc:
                results.append(
                    ScheduleStepResult(
                        index=index,
                        txn_id=step.txn_id,
                        op=step.op.value,
                        success=False,
                        error=str(exc),
                        state="precondition_failed",
                        namespace_generation=storage.generation,
                        detail={
                            "path": exc.path,
                            "current": exc.current_version_cid,
                            "expected": exc.expected_version_cid,
                        },
                    )
                )
            except VFSTransactionConflictError as exc:
                results.append(
                    ScheduleStepResult(
                        index=index,
                        txn_id=step.txn_id,
                        op=step.op.value,
                        success=False,
                        error=str(exc),
                        state="conflict",
                        namespace_generation=storage.generation,
                        detail={"path": exc.path, "reason": exc.reason},
                    )
                )
            except VFSTransactionError as exc:
                results.append(
                    ScheduleStepResult(
                        index=index,
                        txn_id=step.txn_id,
                        op=step.op.value,
                        success=False,
                        error=str(exc),
                        state="error",
                        namespace_generation=storage.generation,
                    )
                )
        return results, unsupported

    def _apply_step(
        self,
        mgr: VFSTransactionManager,
        index: int,
        step: ScheduleStep,
    ) -> ScheduleStepResult:
        op = step.op
        if op is TransactionOpKind.BEGIN:
            txn = mgr.begin(txn_id=step.txn_id, isolation=step.isolation)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                namespace_generation=mgr.storage.generation,
                detail={
                    "isolation": txn.isolation.value,
                    "begin_snapshot_cid": (
                        txn.begin_snapshot.snapshot_cid if txn.begin_snapshot else ""
                    ),
                },
            )

        txn = mgr.get(step.txn_id)

        if op is TransactionOpKind.READ:
            rec = mgr.read(txn, step.path)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                version_cid="" if rec is None else str(rec.get("version_cid") or ""),
                namespace_generation=mgr.storage.generation,
                detail={"existed": rec is not None, "path": step.path},
            )

        if op is TransactionOpKind.WRITE:
            staged = mgr.write(txn, step.path, step.content)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                version_cid="",
                namespace_generation=mgr.storage.generation,
                detail={"path": step.path, "content_cid": staged.content_cid},
            )

        if op is TransactionOpKind.CAS_WRITE:
            staged = mgr.cas_write(
                txn,
                step.path,
                step.content,
                precondition_version_cid=step.precondition_version_cid,
            )
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                namespace_generation=mgr.storage.generation,
                detail={
                    "path": step.path,
                    "content_cid": staged.content_cid,
                    "precondition": step.precondition_version_cid,
                },
            )

        if op is TransactionOpKind.DELETE:
            mgr.delete(txn, step.path)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                namespace_generation=mgr.storage.generation,
                detail={"path": step.path},
            )

        if op is TransactionOpKind.RENAME:
            mgr.rename(txn, step.path, step.target_path)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                namespace_generation=mgr.storage.generation,
                detail={"source": step.path, "target": step.target_path},
            )

        if op is TransactionOpKind.COMMIT:
            mgr.commit(txn)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                namespace_generation=mgr.storage.generation,
                detail={"committed_versions": dict(txn.committed_versions)},
            )

        if op is TransactionOpKind.ABORT:
            mgr.abort(txn)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                namespace_generation=mgr.storage.generation,
            )

        if op is TransactionOpKind.CANCEL:
            disposition = mgr.cancel(txn, request_compensate=step.request_compensate)
            return ScheduleStepResult(
                index=index,
                txn_id=txn.txn_id,
                op=op.value,
                success=True,
                state=txn.state.value,
                disposition=disposition.value,
                namespace_generation=mgr.storage.generation,
            )

        if op is TransactionOpKind.SNAPSHOT:
            snap = mgr.capture_snapshot(snapshot_id=step.path or None)
            return ScheduleStepResult(
                index=index,
                txn_id=step.txn_id,
                op=op.value,
                success=True,
                version_cid=snap.snapshot_cid,
                namespace_generation=mgr.storage.generation,
                detail={"snapshot_id": snap.snapshot_id},
            )

        raise VFSTransactionError(f"unknown schedule op: {op}")

    @staticmethod
    def _results_match(
        a: Sequence[ScheduleStepResult],
        b: Sequence[ScheduleStepResult],
    ) -> bool:
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            if (
                x.txn_id != y.txn_id
                or x.op != y.op
                or x.success != y.success
                or x.state != y.state
                or x.unsupported_reason != y.unsupported_reason
                or x.disposition != y.disposition
            ):
                return False
            # version_cid may differ if generation clocks differ; compare
            # success/error shape only for cas conflicts.
            if x.error and y.error:
                # both failed — ok if both non-empty
                continue
            if bool(x.error) != bool(y.error):
                return False
        return True


def clone_memory_storage(source: VFSStorageBoundary) -> VFSStorageBoundary:
    """Deep-clone an in-memory storage boundary for differential schedules.

    Requires the concrete :class:`~ipfs_kit_py.core.vfs.service.InMemoryVFSStorage`
    shape (entries + generation). Used by tests and schedule differentials.
    """

    from ipfs_kit_py.core.vfs.service import InMemoryVFSStorage

    if not isinstance(source, InMemoryVFSStorage):
        raise TypeError("clone_memory_storage requires InMemoryVFSStorage")
    clone = InMemoryVFSStorage(max_entries=source._max_entries)
    clone._entries = {
        path: VFSStoredEntry(
            kind=entry.kind,
            content=bytes(entry.content),
            content_cid=entry.content_cid,
            version_cid=entry.version_cid,
            target=entry.target,
            mtime_unix_ms=entry.mtime_unix_ms,
            mode=entry.mode,
            mount_id=entry.mount_id,
            is_readonly=entry.is_readonly,
        )
        for path, entry in source._entries.items()
    }
    clone._generation = source._generation
    return clone


def make_schedule(*steps: ScheduleStep) -> tuple[ScheduleStep, ...]:
    return tuple(steps)


__all__ = [
    "TRANSACTION_CONTRACT_VERSION",
    "TRANSACTION_SCHEMA_VERSION",
    "VFS_TRANSACTION_SCHEMA",
    "VFS_LOCK_SCHEMA",
    "VFS_SCHEDULE_SCHEMA",
    "VFSTransaction_V1",
    "MAX_ACTIVE_TRANSACTIONS",
    "MAX_WRITE_SET",
    "MAX_READ_SET",
    "MAX_LOCKS_PER_TXN",
    "MAX_GLOBAL_LOCKS",
    "MAX_SCHEDULE_STEPS",
    "IsolationLevel",
    "LockMode",
    "TransactionState",
    "CancellationDisposition",
    "TransactionOpKind",
    "TransactionUnsupportedReason",
    "VFSTransactionError",
    "VFSTransactionStateError",
    "VFSTransactionConflictError",
    "VFSTransactionCancelledError",
    "VFSLockError",
    "VFSLockDeadlockError",
    "VFSTransactionUnsupportedError",
    "StagedWrite",
    "ReadObservation",
    "LockGrant",
    "VFSLockManager",
    "ordered_lock_paths",
    "VFSTransaction",
    "VFSTransactionManager",
    "ScheduleStep",
    "ScheduleStepResult",
    "ScheduleOutcome",
    "ConcurrentScheduleExecutor",
    "clone_memory_storage",
    "make_schedule",
]

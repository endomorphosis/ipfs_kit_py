"""Hermetic VFS/WAL/current-root recovery surface (PCPR-023).

This adapter composes the current-head kernel VFS WAL, mount recovery,
ARC coherence, and a durable generation-bearing current-root CAS. It is
not a mock, not a live FUSE/WinFsp/container mount, and not a
production-authorized or closed PCPR release.

Fail-closed invariants:

* the adapter is hermetic: it never claims live FUSE, WinFsp, or container
  support;
* injected or simulated backends cannot mint live qualification;
* missing native drivers stay typed unavailable in the qualifier;
* secret-bearing configuration is rejected;
* current-root CAS rejects stale parents, concurrent losers, corruption,
  tombstones, and invalidation;
* WAL crash recovery compensates uncommitted intents and replays commits;
* process restart reconstructs the current root from disk, not memory.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Optional

from ipfs_kit_py.core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    OperationState,
    Retryability,
    StorageError,
)
from ipfs_kit_py.core.wal.coordinator import (
    WALTransactionCoordinator,
    WALTransactionCrash,
)
from ipfs_kit_py.kernel_vfs.cache_coherence import (
    CacheCoherence,
    CoherenceAction,
    CoherenceDisposition,
    CoherenceEvent,
    CoherenceMutationKind,
    CoherenceSource,
)
from ipfs_kit_py.kernel_vfs.durable_mutation import (
    DurableMutationCoordinator,
    MutationDisposition,
)
from ipfs_kit_py.kernel_vfs.wal_recovery import (
    MountRecoveryCoordinator,
    MountRecoveryReceipt,
    RecoveryDisposition,
)


SCHEMA: Final = "ipfs_kit_py/assurance/vfs-wal-recovery@1"
INTERFACE: Final = "HermeticVfsWalRecoveryAdapter@1"
CURRENT_ROOT_SCHEMA: Final = "ipfs_kit_py/assurance/current-root-pointer@1"
CURRENT_ROOT_INTERFACE: Final = "DurableCurrentRootCAS@1"
BACKEND_ID: Final = "vfs_wal_current_root"
CERTIFICATION_SCOPE: Final = (
    "pcpr-023-vfs-wal-current-root-hermetic; not a closed PCPR release"
)
SUPPORT_CLASS: Final = "hermetic_qualified"
LIVE_SUPPORT_CLAIM: Final = False
GENESIS_PARENT: Final = ""
POINTER_NAME: Final = "current-root.json"
DIGEST_NAME: Final = "current-root.json.sha256"
LOCK_NAME: Final = "current-root.lock"
OBJECTS_DIRNAME: Final = "objects"
WAL_DIRNAME: Final = "wal"

_SECRET_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
    "api_key",
    "private_key",
    "bearer",
    "witness",
    "proving_key",
)


class VfsWalRecoveryError(RuntimeError):
    """Typed VFS/WAL/current-root failure carrying a StorageError."""

    def __init__(self, error: StorageError) -> None:
        self.error = error
        super().__init__(error.message)


def _raise(
    code: ErrorCode,
    category: ErrorCategory,
    message: str,
    *,
    state: OperationState = OperationState.FAILED,
    retryability: Retryability = Retryability.NEVER,
) -> None:
    raise VfsWalRecoveryError(
        StorageError(
            code=code,
            category=category,
            message=message,
            retryability=retryability,
            state=state,
        )
    )


def _reject_secret_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if any(part in normalized for part in _SECRET_KEY_FRAGMENTS):
                _raise(
                    ErrorCode.SECRET_MATERIAL,
                    ErrorCategory.AUTHORIZATION,
                    "secret-bearing configuration is forbidden",
                    state=OperationState.REJECTED,
                )
            _reject_secret_keys(nested)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            _reject_secret_keys(nested)


def content_cid(data: bytes) -> str:
    """Return a CIDv1 raw/sha2-256 identity for exact object bytes."""

    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    multihash = b"\x01\x55\x12\x20" + hashlib.sha256(data).digest()
    return "b" + base64.b32encode(multihash).decode("ascii").rstrip("=").lower()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


@dataclass(frozen=True)
class CurrentRootPointer:
    """Generation-bearing current-root pointer."""

    schema: str
    generation: int
    current_cid: str
    parent_cid: str
    object_digest: str
    tombstoned: bool
    invalidated: bool
    invalidation_reason: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generation": self.generation,
            "current_cid": self.current_cid,
            "parent_cid": self.parent_cid,
            "object_digest": self.object_digest,
            "tombstoned": self.tombstoned,
            "invalidated": self.invalidated,
            "invalidation_reason": self.invalidation_reason,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CurrentRootPointer":
        return cls(
            schema=str(payload.get("schema") or CURRENT_ROOT_SCHEMA),
            generation=int(payload.get("generation") or 0),
            current_cid=str(payload.get("current_cid") or ""),
            parent_cid=str(payload.get("parent_cid") or ""),
            object_digest=str(payload.get("object_digest") or ""),
            tombstoned=bool(payload.get("tombstoned")),
            invalidated=bool(payload.get("invalidated")),
            invalidation_reason=str(payload.get("invalidation_reason") or ""),
        )


@dataclass(frozen=True)
class CurrentRootCasResult:
    """One current-root CAS outcome."""

    swapped: bool
    pointer: CurrentRootPointer
    object_cid: str
    wal_transaction_id: str = ""
    reason: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "swapped": self.swapped,
            "pointer": self.pointer.to_mapping(),
            "object_cid": self.object_cid,
            "wal_transaction_id": self.wal_transaction_id,
            "reason": self.reason,
        }


class DurableCurrentRootCAS:
    """Durable generation-bearing current-root compare-and-swap.

    The pointer is the only mutable current-root authority on this surface.
    Objects are immutable once published. Stale parents, concurrent losers,
    digest mismatches, tombstones, and invalidations fail closed.
    """

    schema = CURRENT_ROOT_SCHEMA
    interface = CURRENT_ROOT_INTERFACE

    def __init__(
        self,
        root: str | Path,
        *,
        create: bool = True,
        wal: WALTransactionCoordinator | None = None,
        crash_injector: Any = None,
    ) -> None:
        self.root = Path(root).resolve()
        self._objects = self.root / OBJECTS_DIRNAME
        self._pointer_path = self.root / POINTER_NAME
        self._digest_path = self.root / DIGEST_NAME
        self._lock_path = self.root / LOCK_NAME
        self._lock = threading.RLock()
        self._closed = False
        if create:
            self._objects.mkdir(parents=True, exist_ok=True)
            self.root.mkdir(parents=True, exist_ok=True)
        self._wal = wal or WALTransactionCoordinator(
            self.root / WAL_DIRNAME, crash_injector=crash_injector
        )
        self._owns_wal = wal is None
        if create and not self._pointer_path.is_file():
            genesis = CurrentRootPointer(
                schema=CURRENT_ROOT_SCHEMA,
                generation=0,
                current_cid=GENESIS_PARENT,
                parent_cid=GENESIS_PARENT,
                object_digest=_sha256_hex(b""),
                tombstoned=False,
                invalidated=False,
            )
            self._persist_pointer(genesis)

    def close(self) -> None:
        self._closed = True
        if self._owns_wal:
            try:
                self._wal.close()
            except Exception:
                pass

    @classmethod
    def reopen(cls, root: str | Path) -> "DurableCurrentRootCAS":
        store = cls(root, create=False)
        if not store._pointer_path.is_file() or not store._digest_path.is_file():
            _raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "current-root pointer is missing on reopen",
                state=OperationState.UNAVAILABLE,
            )
        store.current()
        return store

    def current(self) -> CurrentRootPointer:
        with self._lock:
            return self._load_pointer()

    def get_object(self, cid: str) -> bytes:
        with self._lock:
            if not cid:
                return b""
            path = self._objects / cid
            if not path.is_file():
                _raise(
                    ErrorCode.NOT_FOUND,
                    ErrorCategory.NOT_FOUND,
                    "current-root object is absent",
                    state=OperationState.FAILED,
                )
            data = path.read_bytes()
            if content_cid(data) != cid:
                _raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "current-root object digest mismatch",
                    state=OperationState.FAILED,
                )
            return data

    def compare_and_swap(
        self,
        expected_parent_cid: str,
        payload: bytes,
        *,
        effect_id: str | None = None,
    ) -> CurrentRootCasResult:
        """Publish ``payload`` iff the durable current CID equals expected parent."""

        if not isinstance(payload, bytes):
            _raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "current-root payload must be bytes",
                state=OperationState.REJECTED,
            )
        with self._lock:
            self._assert_open()
            pointer = self._load_pointer()
            self._assert_writable(pointer)
            if pointer.current_cid != expected_parent_cid:
                _raise(
                    ErrorCode.PRECONDITION_FAILED,
                    ErrorCategory.PRECONDITION,
                    "stale parent rejected by current-root CAS",
                    state=OperationState.REJECTED,
                )
            new_cid = content_cid(payload)
            object_digest = _sha256_hex(payload)
            new_pointer = CurrentRootPointer(
                schema=CURRENT_ROOT_SCHEMA,
                generation=pointer.generation + 1,
                current_cid=new_cid,
                parent_cid=pointer.current_cid,
                object_digest=object_digest,
                tombstoned=False,
                invalidated=False,
            )
            prior = pointer
            txn_id = ""

            def effect() -> bool:
                _atomic_write_bytes(self._objects / new_cid, payload)
                self._persist_pointer(new_pointer)
                return True

            def compensate() -> bool:
                self._persist_pointer(prior)
                return True

            result = self._wal.execute(
                {
                    "kind": "current_root_cas",
                    "expected_parent_cid": expected_parent_cid,
                    "new_cid": new_cid,
                    "generation": new_pointer.generation,
                    "object_digest": object_digest,
                    "prior_pointer": prior.to_mapping(),
                    "new_pointer": new_pointer.to_mapping(),
                },
                effect,
                compensate,
                effect_id=effect_id,
            )
            txn_id = result.transaction_id
            return CurrentRootCasResult(
                swapped=True,
                pointer=new_pointer,
                object_cid=new_cid,
                wal_transaction_id=txn_id,
            )

    def tombstone(self) -> CurrentRootPointer:
        with self._lock:
            self._assert_open()
            pointer = self._load_pointer()
            if pointer.tombstoned:
                return pointer
            updated = CurrentRootPointer(
                schema=pointer.schema,
                generation=pointer.generation,
                current_cid=pointer.current_cid,
                parent_cid=pointer.parent_cid,
                object_digest=pointer.object_digest,
                tombstoned=True,
                invalidated=pointer.invalidated,
                invalidation_reason=pointer.invalidation_reason,
            )
            self._persist_pointer(updated)
            return updated

    def invalidate(self, reason: str) -> CurrentRootPointer:
        with self._lock:
            self._assert_open()
            pointer = self._load_pointer()
            updated = CurrentRootPointer(
                schema=pointer.schema,
                generation=pointer.generation,
                current_cid=pointer.current_cid,
                parent_cid=pointer.parent_cid,
                object_digest=pointer.object_digest,
                tombstoned=pointer.tombstoned,
                invalidated=True,
                invalidation_reason=reason,
            )
            self._persist_pointer(updated)
            return updated

    def recover(self) -> dict[str, int]:
        with self._lock:
            def replay(intent: Mapping[str, Any], effect_id: str) -> bool:
                del effect_id
                payload = intent.get("new_pointer")
                if isinstance(payload, Mapping):
                    self._persist_pointer(CurrentRootPointer.from_mapping(payload))
                return True

            def rollback(intent: Mapping[str, Any], effect_id: str) -> bool:
                del effect_id
                payload = intent.get("prior_pointer")
                if isinstance(payload, Mapping):
                    self._persist_pointer(CurrentRootPointer.from_mapping(payload))
                return True

            stats = self._wal.recover(replay_effect=replay, rollback_effect=rollback)
            self._load_pointer()
            return dict(stats)

    def _assert_open(self) -> None:
        if self._closed:
            _raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "current-root CAS is closed",
                state=OperationState.UNAVAILABLE,
            )

    def _assert_writable(self, pointer: CurrentRootPointer) -> None:
        if pointer.tombstoned:
            _raise(
                ErrorCode.CONFLICT,
                ErrorCategory.CONFLICT,
                "tombstoned current root cannot be swapped",
                state=OperationState.REJECTED,
            )
        if pointer.invalidated:
            _raise(
                ErrorCode.CONFLICT,
                ErrorCategory.CONFLICT,
                "invalidated current root cannot be swapped",
                state=OperationState.REJECTED,
            )

    def _persist_pointer(self, pointer: CurrentRootPointer) -> None:
        body = _canonical_json_bytes(pointer.to_mapping())
        digest = _sha256_hex(body).encode("ascii")
        _atomic_write_bytes(self._pointer_path, body)
        _atomic_write_bytes(self._digest_path, digest)

    def _load_pointer(self) -> CurrentRootPointer:
        if not self._pointer_path.is_file() or not self._digest_path.is_file():
            _raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "current-root pointer is absent",
                state=OperationState.UNAVAILABLE,
            )
        body = self._pointer_path.read_bytes()
        recorded = self._digest_path.read_bytes().decode("ascii").strip()
        actual = _sha256_hex(body)
        if recorded != actual:
            _raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "current-root pointer corruption detected",
                state=OperationState.FAILED,
            )
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            _raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "current-root pointer is not a mapping",
                state=OperationState.FAILED,
            )
        return CurrentRootPointer.from_mapping(payload)


@dataclass
class HermeticVfsWalRecoveryAdapter:
    """Hermetic VFS/WAL/current-root recovery adapter.

    ``live_provider`` is false: this surface never mounts Linux FUSE,
    Windows WinFsp, or container FUSE. Hermetic results cannot mint live
    qualification.
    """

    backend_id = BACKEND_ID
    provider_kind = "hermetic_vfs"
    is_hermetic = True
    live_provider = False
    provider_certified = False
    production_authorized = False
    simulated = False
    live_support_claim = LIVE_SUPPORT_CLAIM
    support_class = SUPPORT_CLASS
    certification_scope = CERTIFICATION_SCOPE
    schema = SCHEMA
    interface = INTERFACE

    def __init__(
        self,
        root: str | Path,
        *,
        configuration: Optional[Mapping[str, Any]] = None,
        create: bool = True,
        simulated: bool = False,
        mutations: DurableMutationCoordinator | None = None,
        cas: DurableCurrentRootCAS | None = None,
        coherence: CacheCoherence | None = None,
    ) -> None:
        self.validate_configuration({} if configuration is None else configuration)
        self.root = Path(root).resolve()
        self.simulated = bool(simulated)
        if self.simulated:
            self.is_hermetic = True
            self.live_provider = False
        self._lock = threading.RLock()
        self._closed = False
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        self._durable_dir = self.root / "durable"
        self._recovery_dir = self.root / "recovery"
        self._cas_dir = self.root / "current-root"
        self._mutations = mutations or DurableMutationCoordinator(self._durable_dir)
        self._cas = cas or DurableCurrentRootCAS(self._cas_dir, create=create)
        self._coherence = coherence or CacheCoherence()
        self._recovery: MountRecoveryCoordinator | None = None
        self._last_recovery: MountRecoveryReceipt | None = None

    @classmethod
    def validate_configuration(cls, configuration: Mapping[str, Any]) -> bool:
        if not isinstance(configuration, Mapping):
            _raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "configuration must be a mapping",
                state=OperationState.REJECTED,
            )
        _reject_secret_keys(configuration)
        return True

    @classmethod
    def reopen(cls, root: str | Path) -> "HermeticVfsWalRecoveryAdapter":
        adapter = cls(root, create=False, cas=DurableCurrentRootCAS.reopen(Path(root) / "current-root"))
        adapter._mutations = DurableMutationCoordinator(adapter._durable_dir)
        return adapter

    def close(self) -> None:
        with self._lock:
            self._closed = True
            try:
                self._mutations.close()
            except Exception:
                pass
            try:
                self._cas.close()
            except Exception:
                pass
            if self._recovery is not None:
                try:
                    self._recovery.close()
                except Exception:
                    pass

    def create_object(self, path: str, payload: bytes, *, effect_id: str = "") -> Any:
        with self._lock:
            result = self._mutations.create(path, payload, effect_id=effect_id)
            if result.committed:
                self._coherence.publish_mutation_result(result)
            return result

    def unlink_object(self, path: str, *, effect_id: str = "") -> Any:
        with self._lock:
            result = self._mutations.unlink(path, effect_id=effect_id)
            if result.committed:
                self._coherence.publish_mutation_result(result)
            return result

    def compare_and_swap_current_root(
        self, expected_parent_cid: str, payload: bytes, *, effect_id: str | None = None
    ) -> CurrentRootCasResult:
        with self._lock:
            return self._cas.compare_and_swap(
                expected_parent_cid, payload, effect_id=effect_id
            )

    def current_root(self) -> CurrentRootPointer:
        return self._cas.current()

    def get_current_object(self, cid: str) -> bytes:
        return self._cas.get_object(cid)

    def tombstone_current_root(self) -> CurrentRootPointer:
        return self._cas.tombstone()

    def invalidate_current_root(self, reason: str) -> CurrentRootPointer:
        return self._cas.invalidate(reason)

    def recover_wal(self) -> dict[str, int]:
        with self._lock:
            mutation_stats = self._mutations.recover()
            cas_stats = self._cas.recover()
            return {
                "mutations_replayed": int(mutation_stats.get("replayed") or 0),
                "mutations_rolled_back": int(mutation_stats.get("rolled_back") or 0),
                "cas_replayed": int(cas_stats.get("replayed") or 0),
                "cas_rolled_back": int(cas_stats.get("rolled_back") or 0),
            }

    def recover_mount(self, *, mount_id: str = "mount:pcpr-023") -> MountRecoveryReceipt:
        with self._lock:
            coordinator = MountRecoveryCoordinator(
                self._recovery_dir,
                mount_id=mount_id,
                mutations=self._mutations,
            )
            self._recovery = coordinator
            receipt = coordinator.recover()
            self._last_recovery = receipt
            return receipt

    def publish_coherence(
        self,
        *,
        kind: str,
        path: str,
        disposition: str = "committed",
        effect_id: str = "",
        source: str = "mutation",
    ) -> Any:
        event = CoherenceEvent(
            kind=CoherenceMutationKind(kind),
            disposition=CoherenceDisposition(disposition),
            path=path,
            effect_id=effect_id or f"effect:{uuid.uuid4().hex}",
            source=CoherenceSource(source),
        )
        return self._coherence.publish(event)

    def active_generation(self, path: str) -> str | None:
        from ipfs_kit_py.kernel_vfs.cache_coherence import path_to_content_id

        return self._coherence.active_generation(path_to_content_id(path))

    @property
    def coherence(self) -> CacheCoherence:
        return self._coherence

    @property
    def cas(self) -> DurableCurrentRootCAS:
        return self._cas

    @property
    def mutations(self) -> DurableMutationCoordinator:
        return self._mutations

    @property
    def last_recovery(self) -> MountRecoveryReceipt | None:
        return self._last_recovery


__all__ = [
    "SCHEMA",
    "INTERFACE",
    "CURRENT_ROOT_SCHEMA",
    "CURRENT_ROOT_INTERFACE",
    "BACKEND_ID",
    "CERTIFICATION_SCOPE",
    "SUPPORT_CLASS",
    "LIVE_SUPPORT_CLAIM",
    "GENESIS_PARENT",
    "VfsWalRecoveryError",
    "CurrentRootPointer",
    "CurrentRootCasResult",
    "DurableCurrentRootCAS",
    "HermeticVfsWalRecoveryAdapter",
    "content_cid",
    "WALTransactionCrash",
    "MutationDisposition",
    "CoherenceAction",
    "RecoveryDisposition",
]

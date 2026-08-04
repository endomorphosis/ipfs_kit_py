"""Transactional bucket and object operations.

The service intentionally serializes admission, lifecycle fences, quota
calculation, and catalog publication under one lock.  Backend calls form a
small saga: a mutation becomes visible locally only after every placement
returns the literal value ``True``.  A rollback which cannot be completed is
recorded in :class:`BucketCatalog` before an error reaches the caller.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Final, Protocol, runtime_checkable

from ipfs_kit_py.core.buckets.catalog import (
    BucketCatalog,
    CatalogConflictError,
    CatalogNotFoundError,
    CompensationRecord,
)
from ipfs_kit_py.core.buckets.contracts import (
    BucketIdentity,
    BucketLifecycleState,
    BucketManifest,
    assert_legal_bucket_transition,
)


BUCKET_SERVICE_SCHEMA: Final[str] = "ipfs_kit_py/core/buckets/service@1"
BucketService_V1: Final[str] = BUCKET_SERVICE_SCHEMA
MAX_PAGE_SIZE: Final[int] = 1000


class BucketServiceError(Exception):
    """Base class for bucket runtime failures."""


class BucketNotFoundError(BucketServiceError):
    pass


class BucketStateError(BucketServiceError):
    pass


class BucketConflictError(BucketServiceError):
    pass


class BucketQuotaExceededError(BucketServiceError):
    pass


class ObjectNotFoundError(BucketServiceError):
    pass


class ObjectVersionConflictError(BucketServiceError):
    pass


class IdempotencyConflictError(BucketServiceError):
    pass


class IdempotentOperationFailedError(BucketServiceError):
    pass


class BackendOperationError(BucketServiceError):
    """A backend either raised or returned a non-``True`` result."""

    def __init__(self, backend_id: str, action: str, detail: str = "") -> None:
        self.backend_id, self.action = backend_id, action
        super().__init__(f"backend {backend_id!r} did not commit {action}" + (f": {detail}" if detail else ""))


class CompensationRequiredError(BucketServiceError):
    def __init__(self, operation_id: str, cause: Exception) -> None:
        self.operation_id, self.cause = operation_id, cause
        super().__init__(f"operation requires recovery: {operation_id}: {cause}")


@runtime_checkable
class BucketBackend(Protocol):
    """Strict backend boundary.  Success is represented by ``True`` only."""

    def create_bucket(self, manifest: BucketManifest) -> bool: ...
    def update_bucket(self, previous: BucketManifest, following: BucketManifest) -> bool: ...
    def delete_bucket(self, manifest: BucketManifest) -> bool: ...
    def put_object(self, manifest: BucketManifest, key: str, data: bytes, metadata: "ObjectMetadata") -> bool: ...
    def delete_object(self, manifest: BucketManifest, key: str, metadata: "ObjectMetadata") -> bool: ...


@dataclass(frozen=True)
class ObjectMetadata:
    bucket_key: str
    key: str
    content_id: str
    version_id: str
    size: int
    generation: int


@dataclass(frozen=True)
class BucketObject:
    metadata: ObjectMetadata
    data: bytes


@dataclass(frozen=True)
class ObjectPage:
    entries: tuple[ObjectMetadata, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class BucketPage:
    entries: tuple[BucketManifest, ...]
    next_cursor: str | None


class TransactionState(str, Enum):
    OPEN = "open"
    COMMITTED = "committed"
    COMPENSATING = "compensating"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass
class BucketTransaction:
    """Auditable state for one multi-backend service operation."""

    action: str
    bucket_key: str
    operation_id: str = ""
    state: TransactionState = TransactionState.OPEN
    applied_backend_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if not self.operation_id:
            self.operation_id = uuid.uuid4().hex
        if self.applied_backend_ids is None:
            self.applied_backend_ids = []

    def applied(self, backend_id: str) -> None:
        if self.state is not TransactionState.OPEN:
            raise BucketStateError("cannot apply a closed transaction")
        self.applied_backend_ids.append(backend_id)

    def commit(self) -> None:
        if self.state is not TransactionState.OPEN:
            raise BucketStateError("cannot commit a closed transaction")
        self.state = TransactionState.COMMITTED


@dataclass(frozen=True)
class _IdempotencyEntry:
    fingerprint: str
    result: Any = None
    error_name: str | None = None
    error_message: str | None = None


class InMemoryBucketBackend:
    """A deterministic backend suitable for integration tests and local use."""

    def __init__(self) -> None:
        self.buckets: dict[str, BucketManifest] = {}
        self.objects: dict[tuple[str, str], BucketObject] = {}
        self.calls: list[tuple[str, str]] = []

    def create_bucket(self, manifest: BucketManifest) -> bool:
        self.calls.append(("create_bucket", manifest.identity.catalog_key))
        self.buckets[manifest.identity.catalog_key] = manifest
        return True

    def update_bucket(self, previous: BucketManifest, following: BucketManifest) -> bool:
        self.calls.append(("update_bucket", following.identity.catalog_key))
        self.buckets[following.identity.catalog_key] = following
        return True

    def delete_bucket(self, manifest: BucketManifest) -> bool:
        key = manifest.identity.catalog_key
        self.calls.append(("delete_bucket", key))
        self.buckets.pop(key, None)
        for object_key in tuple(self.objects):
            if object_key[0] == key:
                self.objects.pop(object_key)
        return True

    def put_object(self, manifest: BucketManifest, key: str, data: bytes, metadata: ObjectMetadata) -> bool:
        self.calls.append(("put_object", f"{manifest.identity.catalog_key}/{key}"))
        self.objects[(manifest.identity.catalog_key, key)] = BucketObject(metadata, bytes(data))
        return True

    def delete_object(self, manifest: BucketManifest, key: str, metadata: ObjectMetadata) -> bool:
        self.calls.append(("delete_object", f"{manifest.identity.catalog_key}/{key}"))
        self.objects.pop((manifest.identity.catalog_key, key), None)
        return True


class BucketService:
    """Lock-protected lifecycle, object, quota, pagination, and recovery API."""

    SCHEMA: Final[str] = BUCKET_SERVICE_SCHEMA

    def __init__(self, backends: Mapping[str, BucketBackend], *, catalog: BucketCatalog | None = None) -> None:
        self.catalog = catalog or BucketCatalog()
        self._backends = dict(backends)
        self._objects: dict[str, dict[str, BucketObject]] = {}
        self._object_generations: dict[tuple[str, str], int] = {}
        self._object_revisions: dict[str, int] = {}
        self._idempotency: dict[str, _IdempotencyEntry] = {}
        self._page_snapshots: dict[str, tuple[Any, ...]] = {}
        self._recovery_actions: dict[str, Callable[[], bool]] = {}
        self._lock = threading.RLock()

    def create_bucket(self, manifest: BucketManifest, *, idempotency_key: str | None = None) -> BucketManifest:
        # KITA-044: bounded admission before catalog/backend work.
        from ipfs_kit_py.core.performance import HotPathGate

        with HotPathGate(payload_bytes=0, fairness_class="bucket-create"):
            self._require_manifest(manifest)
            return self._idempotent(
                "create_bucket",
                idempotency_key,
                manifest.content_id,
                lambda: self._create(manifest),
            )

    def _create(self, manifest: BucketManifest) -> BucketManifest:
        with self._lock, self.catalog.operation_lock():
            key = manifest.identity.catalog_key
            if manifest.lifecycle_state is not BucketLifecycleState.PROVISIONING:
                raise BucketStateError("a new bucket must begin in provisioning")
            try:
                self.catalog.get(key)
            except CatalogNotFoundError:
                pass
            else:
                raise BucketConflictError(f"bucket {key!r} already exists")
            active = self._transition(manifest, BucketLifecycleState.ACTIVE)
            transaction = BucketTransaction("create_bucket", key)
            try:
                for backend_id in self._backend_ids(active):
                    # A false result can be an ambiguous remote outcome.  The
                    # attempt belongs in compensation just as a true result
                    # does, because deletion is idempotent at this boundary.
                    transaction.applied(backend_id)
                    self._call(backend_id, "create_bucket", active)
            except BackendOperationError as exc:
                self._rollback(
                    transaction,
                    "rollback_create_bucket",
                    key,
                    lambda backend_id: self._try_call(backend_id, "delete_bucket", active),
                    detail={"manifest": active},
                )
                raise self._failure(transaction, exc) from exc
            self._publish(
                self.catalog.generation,
                (*self.catalog.snapshot().entries, active),
                transaction,
                active,
                rollback_action="rollback_create_bucket",
                rollback_detail={"manifest": active},
            )
            self._objects[key] = {}
            self._object_revisions[key] = 0
            transaction.commit()
            return active

    def update_bucket(self, manifest: BucketManifest, *, expected_generation: int | None = None, idempotency_key: str | None = None) -> BucketManifest:
        self._require_manifest(manifest)
        return self._idempotent("update_bucket", idempotency_key, manifest.content_id + str(expected_generation), lambda: self._update(manifest, expected_generation))

    def _update(self, following: BucketManifest, expected_generation: int | None) -> BucketManifest:
        with self._lock, self.catalog.operation_lock():
            previous = self._get(following.identity.catalog_key)
            self._check_generation(expected_generation)
            if previous.lifecycle_state is not BucketLifecycleState.ACTIVE or following.lifecycle_state is not BucketLifecycleState.ACTIVE:
                raise BucketStateError("only active bucket configurations may be updated")
            if self._backend_ids(previous) != self._backend_ids(following):
                raise BucketConflictError("placement changes require a separate migration")
            transaction = BucketTransaction("update_bucket", previous.identity.catalog_key)
            try:
                for backend_id in self._backend_ids(previous):
                    transaction.applied(backend_id)
                    self._call(backend_id, "update_bucket", previous, following)
            except BackendOperationError as exc:
                self._rollback(
                    transaction,
                    "restore_bucket_manifest",
                    previous.identity.catalog_key,
                    lambda backend_id: self._try_call(backend_id, "update_bucket", following, previous),
                    detail={"previous": previous, "following": following},
                )
                raise self._failure(transaction, exc) from exc
            entries = tuple(following if item.identity.catalog_key == previous.identity.catalog_key else item for item in self.catalog.snapshot().entries)
            self._publish(
                self.catalog.generation,
                entries,
                transaction,
                following,
                lambda backend_id: self._try_call(
                    backend_id, "update_bucket", following, previous
                ),
                rollback_action="restore_bucket_manifest",
                rollback_detail={"previous": previous, "following": following},
            )
            transaction.commit()
            return following

    def delete_bucket(self, bucket: BucketIdentity | str, *, expected_generation: int | None = None, idempotency_key: str | None = None) -> None:
        key = self._key(bucket)
        self._idempotent("delete_bucket", idempotency_key, key + str(expected_generation), lambda: self._delete(key, expected_generation))

    def _delete(self, key: str, expected_generation: int | None) -> None:
        with self._lock, self.catalog.operation_lock():
            current = self._get(key)
            self._check_generation(expected_generation)
            if current.lifecycle_state not in (BucketLifecycleState.ACTIVE, BucketLifecycleState.SUSPENDED):
                raise BucketStateError(f"bucket {key!r} is not deletable")
            deleting = self._transition(current, BucketLifecycleState.DELETING)
            entries = tuple(deleting if item.identity.catalog_key == key else item for item in self.catalog.snapshot().entries)
            self.catalog.compare_and_swap(self.catalog.generation, entries)  # deletion fence before any backend delete
            transaction = BucketTransaction("delete_bucket", key)
            try:
                for backend_id in self._backend_ids(current):
                    transaction.applied(backend_id)
                    self._call(backend_id, "delete_bucket", current)
            except BackendOperationError as exc:
                # The same idempotent deletion is replayed for every replica
                # during recovery, including a replica with an ambiguous false
                # response.
                pending = self._backend_ids(current)
                self._record_delete_recovery(transaction, current, pending)
                raise CompensationRequiredError(transaction.operation_id, exc) from exc
            try:
                self._finalize_delete(key)
            except CatalogConflictError as exc:
                # Backends have already accepted the deletion.  Do not expose
                # that ambiguous split as a completed delete: retain the
                # deletion fence and a replayable finalization record.
                transaction.state = TransactionState.RECOVERY_REQUIRED
                self._record_delete_recovery(transaction, current, self._backend_ids(current))
                raise CompensationRequiredError(transaction.operation_id, exc) from exc
            transaction.commit()

    def put_object(self, bucket: BucketIdentity | str, key: str, data: bytes, *, expected_version: str | None = None, idempotency_key: str | None = None) -> ObjectMetadata:
        bucket_key, payload = self._key(bucket), self._bytes(data)
        fingerprint = f"{bucket_key}|{key}|{expected_version}|{self._digest(payload)}"
        return self._idempotent("put_object", idempotency_key, fingerprint, lambda: self._put(bucket_key, key, payload, expected_version))

    def _put(self, bucket_key: str, key: str, data: bytes, expected_version: str | None) -> ObjectMetadata:
        with self._lock, self.catalog.operation_lock():
            manifest = self._writable(bucket_key)
            self._require_object_key(key)
            prior = self._objects.setdefault(bucket_key, {}).get(key)
            self._check_object_version(prior, expected_version)
            used = sum(item.metadata.size for item in self._objects[bucket_key].values())
            next_used = used - (prior.metadata.size if prior else 0) + len(data)
            next_count = len(self._objects[bucket_key]) + (0 if prior else 1)
            if next_used > manifest.policy.quota_bytes or next_count > manifest.policy.quota_objects:
                raise BucketQuotaExceededError(f"bucket {bucket_key!r} quota exceeded")
            metadata = self._metadata(bucket_key, key, data)
            transaction = BucketTransaction("put_object", bucket_key)
            try:
                for backend_id in self._backend_ids(manifest):
                    transaction.applied(backend_id)
                    self._call(backend_id, "put_object", manifest, key, data, metadata)
            except BackendOperationError as exc:
                if prior is None:
                    rollback = lambda backend_id: self._try_call(backend_id, "delete_object", manifest, key, metadata)
                    rollback_detail = {
                        "kind": "delete_object",
                        "manifest": manifest,
                        "key": key,
                        "metadata": metadata,
                    }
                else:
                    rollback = lambda backend_id: self._try_call(backend_id, "put_object", manifest, key, prior.data, prior.metadata)
                    rollback_detail = {
                        "kind": "put_object",
                        "manifest": manifest,
                        "key": key,
                        "data": prior.data,
                        "metadata": prior.metadata,
                    }
                self._rollback(
                    transaction,
                    "rollback_put_object",
                    bucket_key,
                    rollback,
                    detail=rollback_detail,
                )
                raise self._failure(transaction, exc) from exc
            self._objects[bucket_key][key] = BucketObject(metadata, data)
            self._object_generations[(bucket_key, key)] = metadata.generation
            self._object_revisions[bucket_key] = self._object_revisions.get(bucket_key, 0) + 1
            transaction.commit()
            return metadata

    def delete_object(self, bucket: BucketIdentity | str, key: str, *, expected_version: str | None = None, idempotency_key: str | None = None) -> None:
        bucket_key = self._key(bucket)
        self._idempotent("delete_object", idempotency_key, f"{bucket_key}|{key}|{expected_version}", lambda: self._delete_object(bucket_key, key, expected_version))

    def _delete_object(self, bucket_key: str, key: str, expected_version: str | None) -> None:
        with self._lock, self.catalog.operation_lock():
            manifest = self._writable(bucket_key)
            prior = self._objects.get(bucket_key, {}).get(key)
            if prior is None:
                raise ObjectNotFoundError(key)
            self._check_object_version(prior, expected_version)
            transaction = BucketTransaction("delete_object", bucket_key)
            try:
                for backend_id in self._backend_ids(manifest):
                    transaction.applied(backend_id)
                    self._call(backend_id, "delete_object", manifest, key, prior.metadata)
            except BackendOperationError as exc:
                self._rollback(
                    transaction,
                    "rollback_delete_object",
                    bucket_key,
                    lambda backend_id: self._try_call(backend_id, "put_object", manifest, key, prior.data, prior.metadata),
                    detail={
                        "kind": "put_object",
                        "manifest": manifest,
                        "key": key,
                        "data": prior.data,
                        "metadata": prior.metadata,
                    },
                )
                raise self._failure(transaction, exc) from exc
            self._objects[bucket_key].pop(key)
            self._object_revisions[bucket_key] = self._object_revisions.get(bucket_key, 0) + 1
            transaction.commit()

    def get_object(self, bucket: BucketIdentity | str, key: str, *, version_id: str | None = None) -> BucketObject:
        with self._lock:
            item = self._objects.get(self._key(bucket), {}).get(key)
            if item is None:
                raise ObjectNotFoundError(key)
            if version_id is not None and item.metadata.version_id != version_id:
                raise ObjectVersionConflictError("object version is no longer current")
            return item

    def list_objects(self, bucket: BucketIdentity | str, *, prefix: str = "", page_size: int = 100, cursor: str | None = None) -> ObjectPage:
        with self._lock:
            bucket_key = self._key(bucket)
            self._get(bucket_key)
            entries = self._page_entries("objects", bucket_key, prefix, cursor, tuple(sorted((item.metadata for name, item in self._objects.get(bucket_key, {}).items() if name.startswith(prefix)), key=lambda item: item.key)))
            page, next_cursor = self._page("objects", bucket_key, prefix, entries, page_size, cursor)
            return ObjectPage(tuple(page), next_cursor)

    def list_buckets(self, *, page_size: int = 100, cursor: str | None = None) -> BucketPage:
        with self._lock:
            entries = self._page_entries("buckets", "", "", cursor, self.catalog.snapshot().entries)
            page, next_cursor = self._page("buckets", "", "", entries, page_size, cursor)
            return BucketPage(tuple(page), next_cursor)

    def recover_pending(self, operation_id: str | None = None) -> tuple[str, ...]:
        """Retry recorded compensations; only completed recoveries are marked so."""
        with self._lock:
            records = self.catalog.snapshot().pending_compensations
            if operation_id is not None:
                records = tuple(item for item in records if item.operation_id == operation_id)
            recovered: list[str] = []
            for record in records:
                action = self._recovery_actions.get(record.operation_id)
                if action is None:
                    action = self._rehydrate_recovery_action(record)
                    if action is not None:
                        self._recovery_actions[record.operation_id] = action
                if action is not None and action():
                    self.catalog.mark_recovered(record.operation_id)
                    recovered.append(record.operation_id)
            return tuple(recovered)

    @property
    def pending_compensations(self) -> tuple[CompensationRecord, ...]:
        return self.catalog.snapshot().pending_compensations

    def _record_delete_recovery(self, transaction: BucketTransaction, manifest: BucketManifest, pending: tuple[str, ...]) -> None:
        key = manifest.identity.catalog_key
        record = CompensationRecord(transaction.operation_id, "delete_bucket", key, tuple(transaction.applied_backend_ids or ()), pending)
        self.catalog.record_compensation(record)
        self._recovery_actions[transaction.operation_id] = lambda: self._recover_delete_record(record)

    def _rehydrate_recovery_action(self, record: CompensationRecord) -> Callable[[], bool] | None:
        """Rebuild a journaled inverse operation after a service restart."""
        if record.action == "delete_bucket":
            return lambda: self._recover_delete_record(record)
        if record.action in {
            "rollback_create_bucket",
            "restore_bucket_manifest",
            "rollback_put_object",
            "rollback_delete_object",
        }:
            return lambda: self._recover_rollback_record(record)
        return None

    def _recover_delete_record(self, record: CompensationRecord) -> bool:
        try:
            manifest = self._get(record.bucket_key)
        except BucketNotFoundError:
            # A prior retry completed the catalog-side commit.
            return True
        if manifest.lifecycle_state is not BucketLifecycleState.DELETING:
            return False
        try:
            for backend_id in record.pending_backend_ids or self._backend_ids(manifest):
                self._call(backend_id, "delete_bucket", manifest)
            self._finalize_delete(record.bucket_key)
            return True
        except (BackendOperationError, BucketStateError, BucketNotFoundError, CatalogConflictError):
            return False

    def _recover_rollback_record(self, record: CompensationRecord) -> bool:
        """Replay an inverse operation recorded by :meth:`_rollback`.

        Only data which is part of ``CompensationRecord.detail`` is used
        here.  That keeps the recovery path independent of callbacks and of
        the service process that observed the original partial failure.
        """
        detail = record.detail
        try:
            if record.action == "rollback_create_bucket":
                manifest = detail["manifest"]
                if not isinstance(manifest, BucketManifest):
                    return False
                return all([
                    self._try_call(backend_id, "delete_bucket", manifest)
                    for backend_id in record.pending_backend_ids
                ])
            if record.action == "restore_bucket_manifest":
                previous, following = detail["previous"], detail["following"]
                if not isinstance(previous, BucketManifest) or not isinstance(following, BucketManifest):
                    return False
                return all([
                    self._try_call(backend_id, "update_bucket", following, previous)
                    for backend_id in record.pending_backend_ids
                ])
            if record.action in {"rollback_put_object", "rollback_delete_object"}:
                manifest, key, metadata = detail["manifest"], detail["key"], detail["metadata"]
                if not isinstance(manifest, BucketManifest) or not isinstance(key, str) or not isinstance(metadata, ObjectMetadata):
                    return False
                kind = detail["kind"]
                if kind == "delete_object":
                    return all([
                        self._try_call(backend_id, "delete_object", manifest, key, metadata)
                        for backend_id in record.pending_backend_ids
                    ])
                if kind == "put_object":
                    data = detail["data"]
                    if not isinstance(data, bytes):
                        return False
                    return all([
                        self._try_call(backend_id, "put_object", manifest, key, data, metadata)
                        for backend_id in record.pending_backend_ids
                    ])
        except (KeyError, TypeError):
            return False
        return False

    def _finalize_delete(self, key: str) -> None:
        deleting = self._get(key)
        tombstoned = self._transition(deleting, BucketLifecycleState.TOMBSTONED)
        deleted = self._transition(tombstoned, BucketLifecycleState.DELETED)
        _ = deleted  # transitions are deliberately checked before removal.
        self.catalog.compare_and_swap(self.catalog.generation, tuple(item for item in self.catalog.snapshot().entries if item.identity.catalog_key != key))
        self._objects.pop(key, None)
        self._object_revisions.pop(key, None)

    def _publish(
        self,
        generation: int,
        entries: tuple[BucketManifest, ...],
        transaction: BucketTransaction,
        manifest: BucketManifest,
        rollback: Callable[[str], bool] | None = None,
        *,
        rollback_action: str = "rollback_catalog_conflict",
        rollback_detail: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            self.catalog.compare_and_swap(generation, entries)
        except CatalogConflictError as exc:
            callback = rollback or (
                lambda backend_id: self._try_call(
                    backend_id, "delete_bucket", manifest
                )
            )
            self._rollback(
                transaction,
                rollback_action,
                manifest.identity.catalog_key,
                callback,
                detail=rollback_detail or {"manifest": manifest},
            )
            raise self._failure(transaction, exc) from exc

    def _rollback(
        self,
        transaction: BucketTransaction,
        action: str,
        key: str,
        callback: Callable[[str], bool],
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        transaction.state = TransactionState.COMPENSATING
        failed = [backend_id for backend_id in transaction.applied_backend_ids or () if not callback(backend_id)]
        if failed:
            transaction.state = TransactionState.RECOVERY_REQUIRED
            record = CompensationRecord(
                transaction.operation_id,
                action,
                key,
                tuple(transaction.applied_backend_ids or ()),
                tuple(failed),
                detail or {},
            )
            self.catalog.record_compensation(record)
            self._recovery_actions[transaction.operation_id] = lambda: self._recover_rollback_record(record)

    @staticmethod
    def _failure(transaction: BucketTransaction, cause: Exception) -> Exception:
        return CompensationRequiredError(transaction.operation_id, cause) if transaction.state is TransactionState.RECOVERY_REQUIRED else cause

    def _call(self, backend_id: str, action: str, *args: Any) -> None:
        try:
            backend = self._backends[backend_id]
        except KeyError as exc:
            raise BackendOperationError(backend_id, action, "backend is not registered") from exc
        try:
            result = getattr(backend, action)(*args)
        except Exception as exc:
            raise BackendOperationError(backend_id, action, str(exc)) from exc
        if result is not True:
            raise BackendOperationError(backend_id, action, f"returned {result!r}")

    def _try_call(self, backend_id: str, action: str, *args: Any) -> bool:
        try:
            self._call(backend_id, action, *args)
            return True
        except BackendOperationError:
            return False

    def _get(self, key: str) -> BucketManifest:
        try:
            return self.catalog.get(key)
        except CatalogNotFoundError as exc:
            raise BucketNotFoundError(key) from exc

    def _writable(self, key: str) -> BucketManifest:
        manifest = self._get(key)
        if manifest.lifecycle_state is not BucketLifecycleState.ACTIVE:
            raise BucketStateError(f"bucket {key!r} does not admit writes")
        return manifest

    def _backend_ids(self, manifest: BucketManifest) -> tuple[str, ...]:
        return tuple(sorted(replica.backend_id for replica in manifest.replicas))

    def _transition(self, manifest: BucketManifest, following: BucketLifecycleState) -> BucketManifest:
        assert_legal_bucket_transition(manifest.lifecycle_state, following)
        return replace(manifest, lifecycle_state=following)

    def _check_generation(self, expected: int | None) -> None:
        if expected is not None and expected != self.catalog.generation:
            raise BucketConflictError(f"expected catalog generation {expected}, actual {self.catalog.generation}")

    @staticmethod
    def _check_object_version(prior: BucketObject | None, expected: str | None) -> None:
        if expected == "" and prior is not None:
            raise ObjectVersionConflictError("object already exists")
        if expected not in (None, "") and (prior is None or prior.metadata.version_id != expected):
            raise ObjectVersionConflictError("object version is no longer current")

    def _metadata(self, bucket_key: str, key: str, data: bytes) -> ObjectMetadata:
        generation_key = (bucket_key, key)
        generation = self._object_generations.get(generation_key, 0) + 1
        content_id = self._digest(data)
        version_id = self._digest(f"{bucket_key}\0{key}\0{generation}\0{content_id}".encode())
        return ObjectMetadata(bucket_key, key, content_id, version_id, len(data), generation)

    def _idempotent(self, action: str, key: str | None, fingerprint: str, operation: Callable[[], Any]) -> Any:
        if key is not None and (not isinstance(key, str) or not key):
            raise IdempotencyConflictError("idempotency_key must be a non-empty string")
        if key:
            # Serialize the initial execution and publication of its result.
            # The operation itself uses this re-entrant lock, so matching
            # concurrent retries see the cached result instead of duplicating
            # backend side effects.
            with self._lock:
                prior = self._idempotency.get(key)
                if prior is not None:
                    if prior.fingerprint != self._digest((action + "\0" + fingerprint).encode()):
                        raise IdempotencyConflictError("idempotency key was reused for a different request")
                    if prior.error_name:
                        raise IdempotentOperationFailedError(prior.error_message or prior.error_name)
                    return prior.result
                digest = self._digest((action + "\0" + fingerprint).encode())
                try:
                    result = operation()
                except Exception as exc:
                    self._idempotency[key] = _IdempotencyEntry(digest, error_name=type(exc).__name__, error_message=str(exc))
                    raise
                self._idempotency[key] = _IdempotencyEntry(digest, result=result)
                return result
        return operation()

    def _page_entries(self, kind: str, bucket_key: str, prefix: str, cursor: str | None, fresh: tuple[Any, ...]) -> tuple[Any, ...]:
        if cursor is None:
            return fresh
        payload = self._decode_cursor(cursor)
        if payload.get("kind") != kind or payload.get("bucket") != bucket_key or payload.get("prefix") != prefix:
            raise BucketConflictError("cursor belongs to a different listing")
        try:
            return self._page_snapshots[cursor]
        except KeyError as exc:
            raise BucketConflictError("cursor snapshot is unavailable") from exc

    def _page(self, kind: str, bucket_key: str, prefix: str, entries: tuple[Any, ...], page_size: int, cursor: str | None) -> tuple[tuple[Any, ...], str | None]:
        if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= MAX_PAGE_SIZE:
            raise BucketConflictError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        offset = 0 if cursor is None else int(self._decode_cursor(cursor)["offset"])
        page = entries[offset:offset + page_size]
        following = offset + len(page)
        if following >= len(entries):
            return page, None
        payload = {"kind": kind, "bucket": bucket_key, "prefix": prefix, "offset": following, "identity": self._page_identity(entries)}
        token = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
        self._page_snapshots[token] = entries
        return page, token

    @staticmethod
    def _decode_cursor(token: str) -> dict[str, Any]:
        try:
            raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
            payload = json.loads(raw)
            if not isinstance(payload, dict) or not isinstance(payload.get("offset"), int):
                raise ValueError
            return payload
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BucketConflictError("invalid page cursor") from exc

    @staticmethod
    def _page_identity(entries: tuple[Any, ...]) -> str:
        return hashlib.sha256("|".join(getattr(item, "content_id", getattr(getattr(item, "identity", None), "catalog_key", "")) for item in entries).encode()).hexdigest()

    @staticmethod
    def _digest(value: bytes) -> str:
        return "sha256:" + hashlib.sha256(value).hexdigest()

    @staticmethod
    def _key(bucket: BucketIdentity | str) -> str:
        if isinstance(bucket, BucketIdentity):
            return bucket.catalog_key
        if not isinstance(bucket, str) or not bucket:
            raise BucketNotFoundError("bucket identity must be a BucketIdentity or catalog key")
        return bucket

    @staticmethod
    def _bytes(data: bytes) -> bytes:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise BucketServiceError("object data must be bytes")
        return bytes(data)

    @staticmethod
    def _require_manifest(manifest: BucketManifest) -> None:
        if not isinstance(manifest, BucketManifest):
            raise BucketServiceError("manifest must be a BucketManifest")

    @staticmethod
    def _require_object_key(key: str) -> None:
        if not isinstance(key, str) or not key or "\x00" in key:
            raise BucketServiceError("object key must be a non-empty string without NUL")


__all__ = [name for name in globals() if name.startswith("Bucket") or name.startswith("Object") or name.startswith("Compensation") or name in {"BackendOperationError", "IdempotencyConflictError", "IdempotentOperationFailedError", "InMemoryBucketBackend", "MAX_PAGE_SIZE", "TransactionState"}]

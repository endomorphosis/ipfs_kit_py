"""State-machine coverage for the transactional bucket runtime."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading

import pytest

from ipfs_kit_py.core.buckets.contracts import (
    BackendCapability,
    BucketIdentity,
    BucketManifest,
    BucketPolicy,
    BucketReplica,
    BucketReplicaRole,
)
from ipfs_kit_py.core.buckets.service import (
    BackendOperationError,
    BucketNotFoundError,
    BucketQuotaExceededError,
    BucketService,
    BucketStateError,
    CompensationRequiredError,
    InMemoryBucketBackend,
    ObjectMetadata,
)


def _manifest(
    name: str,
    backend_ids: tuple[str, ...] = ("primary",),
    *,
    quota_bytes: int = 1024,
    quota_objects: int = 100,
) -> BucketManifest:
    """Create a minimal valid manifest with the supplied replica topology."""

    return BucketManifest(
        identity_record=BucketIdentity("primary", name),
        policy=BucketPolicy(
            f"{name}policy",
            quota_bytes=quota_bytes,
            quota_objects=quota_objects,
            replica_count=len(backend_ids),
        ),
        backend_capability=BackendCapability(
            "primary",
            max(quota_bytes, 1024),
            max(quota_objects, 100),
        ),
        replicas=tuple(
            BucketReplica(
                backend_id,
                BucketReplicaRole.PRIMARY if index == 0 else BucketReplicaRole.REPLICA,
            )
            for index, backend_id in enumerate(backend_ids)
        ),
    )


class _FalseAfterCreateBackend(InMemoryBucketBackend):
    def create_bucket(self, manifest: BucketManifest) -> bool:
        super().create_bucket(manifest)
        return False


class _FalseOnceUpdateBackend(InMemoryBucketBackend):
    def __init__(self) -> None:
        super().__init__()
        self._false_updates_remaining = 1

    def update_bucket(self, previous: BucketManifest, following: BucketManifest) -> bool:
        super().update_bucket(previous, following)
        if self._false_updates_remaining:
            self._false_updates_remaining -= 1
            return False
        return True


class _RecoverableDeleteBackend(InMemoryBucketBackend):
    def __init__(self) -> None:
        super().__init__()
        self.accept_deletes = False

    def delete_bucket(self, manifest: BucketManifest) -> bool:
        super().delete_bucket(manifest)
        return self.accept_deletes


class _RecoverableCreateRollbackBackend(InMemoryBucketBackend):
    """Reports an ambiguous create and initially refuses its rollback ack."""

    def __init__(self) -> None:
        super().__init__()
        self.accept_deletes = False

    def create_bucket(self, manifest: BucketManifest) -> bool:
        super().create_bucket(manifest)
        return False

    def delete_bucket(self, manifest: BucketManifest) -> bool:
        super().delete_bucket(manifest)
        return self.accept_deletes


def test_false_create_result_is_rolled_back_and_never_published() -> None:
    primary = InMemoryBucketBackend()
    replica = _FalseAfterCreateBackend()
    service = BucketService({"primary": primary, "replica": replica})
    manifest = _manifest("createfailure", ("primary", "replica"))

    with pytest.raises(BackendOperationError):
        service.create_bucket(manifest)

    assert manifest.identity.catalog_key not in primary.buckets
    assert manifest.identity.catalog_key not in replica.buckets
    assert service.catalog.snapshot().entries == ()


def test_false_update_result_rolls_every_store_back() -> None:
    primary = InMemoryBucketBackend()
    replica = _FalseOnceUpdateBackend()
    service = BucketService({"primary": primary, "replica": replica})
    created = service.create_bucket(_manifest("updatefailure", ("primary", "replica")))
    following = replace(created, policy=replace(created.policy, quota_objects=2))

    with pytest.raises(BackendOperationError):
        service.update_bucket(following)

    assert service.catalog.get(created.identity.catalog_key) == created
    assert primary.buckets[created.identity.catalog_key] == created
    assert replica.buckets[created.identity.catalog_key] == created


def test_delete_fences_writes_and_persists_recovery_until_completed() -> None:
    primary = _RecoverableDeleteBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("deleterecovery"))

    with pytest.raises(CompensationRequiredError) as error:
        service.delete_bucket(created.identity)

    assert service.catalog.get(created.identity.catalog_key).lifecycle_state.value == "deleting"
    assert service.pending_compensations[0].operation_id == error.value.operation_id
    with pytest.raises(BucketStateError):
        service.put_object(created.identity, "cannot-race", b"payload")

    primary.accept_deletes = True
    # The journal, not a closure on the original service, must be sufficient
    # to resume recovery after reconstructing the service.
    restarted = BucketService({"primary": primary}, catalog=service.catalog)
    assert restarted.recover_pending() == (error.value.operation_id,)
    assert restarted.pending_compensations == ()
    with pytest.raises(BucketNotFoundError):
        service.put_object(created.identity, "gone", b"payload")


def test_create_rollback_rehydrates_from_compensation_journal() -> None:
    primary = InMemoryBucketBackend()
    replica = _RecoverableCreateRollbackBackend()
    service = BucketService({"primary": primary, "replica": replica})
    manifest = _manifest("createrecovery", ("primary", "replica"))

    with pytest.raises(CompensationRequiredError) as error:
        service.create_bucket(manifest)

    record = service.pending_compensations[0]
    assert record.operation_id == error.value.operation_id
    assert record.action == "rollback_create_bucket"
    assert record.detail["manifest"].lifecycle_state.value == "active"
    assert service.catalog.snapshot().entries == ()

    replica.accept_deletes = True
    restarted = BucketService({"primary": primary, "replica": replica}, catalog=service.catalog)
    assert restarted.recover_pending() == (error.value.operation_id,)
    assert restarted.pending_compensations == ()
    assert manifest.identity.catalog_key not in primary.buckets
    assert manifest.identity.catalog_key not in replica.buckets


def test_idempotent_concurrent_retries_apply_one_object_effect() -> None:
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("idempotency"))
    barrier = threading.Barrier(2)

    def write_once() -> ObjectMetadata:
        barrier.wait()
        return service.put_object(
            created.identity,
            "same-object",
            b"payload",
            idempotency_key="repeatable-write",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = tuple(pool.map(lambda _: write_once(), range(2)))

    assert first == second
    assert sum(action == "put_object" for action, _ in primary.calls) == 1
    assert service.list_objects(created.identity).entries == (first,)


def test_concurrent_quota_check_and_write_admit_only_one_object() -> None:
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("concurrentquota", quota_bytes=7, quota_objects=1))
    barrier = threading.Barrier(2)

    def write(name: str) -> object:
        barrier.wait()
        try:
            return service.put_object(created.identity, name, b"payload")
        except BucketQuotaExceededError:
            return "quota-rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(write, ("first", "second")))

    assert sum(isinstance(result, ObjectMetadata) for result in results) == 1
    assert results.count("quota-rejected") == 1
    assert sum(action == "put_object" for action, _ in primary.calls) == 1


def test_listing_uses_stable_sorted_snapshot_and_content_identity() -> None:
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("objectorder"))
    first_version = service.put_object(created.identity, "a", b"same")
    service.put_object(created.identity, "c", b"middle")
    service.put_object(created.identity, "z", b"last")

    first_page = service.list_objects(created.identity, page_size=2)
    repeated_content = service.put_object(
        created.identity,
        "a",
        b"same",
        expected_version=first_version.version_id,
    )
    service.put_object(created.identity, "b", b"new")
    second_page = service.list_objects(
        created.identity,
        cursor=first_page.next_cursor,
        page_size=2,
    )

    assert tuple(entry.key for entry in first_page.entries) == ("a", "c")
    assert tuple(entry.key for entry in second_page.entries) == ("z",)
    assert repeated_content.content_id == first_version.content_id
    assert repeated_content.version_id != first_version.version_id
    assert tuple(entry.key for entry in service.list_objects(created.identity).entries) == (
        "a",
        "b",
        "c",
        "z",
    )


def test_bucket_listing_is_canonically_ordered() -> None:
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    service.create_bucket(_manifest("zbucket"))
    service.create_bucket(_manifest("abucket"))

    page = service.list_buckets(page_size=10)

    assert tuple(entry.identity.name for entry in page.entries) == ("abucket", "zbucket")

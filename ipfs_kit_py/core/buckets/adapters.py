"""Compatibility adapters for pre-catalog bucket managers.

The adapter intentionally contains no second bucket implementation: all data
operations are delegated to :class:`BucketService`, whose catalog key is the
backend-qualified identity.  It also provides a small, all-or-nothing registry
migration for old name-keyed JSON registries.
"""
from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any

from .contracts import BucketIdentity, BucketManifest
from .service import BucketService


class BucketMigrationError(ValueError):
    """A legacy registry cannot be converted without losing identity."""


def migrate_legacy_bucket_registry(records: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return the v2 backend-qualified registry without mutating ``records``.

    Re-running this function is a no-op.  Conflicting aliases fail before a
    caller publishes anything, which makes a file-backed migration rollback
    safe by construction.
    """
    migrated: dict[str, dict[str, Any]] = {}
    for legacy_key, raw in records.items():
        if not isinstance(raw, Mapping):
            raise BucketMigrationError(f"registry entry {legacy_key!r} is not an object")
        item = copy.deepcopy(dict(raw))
        backend = item.get("backend") or item.get("backend_id")
        name = item.get("bucket_name") or item.get("name") or str(legacy_key).rsplit("/", 1)[-1]
        if not isinstance(backend, str) or not backend:
            raise BucketMigrationError(f"registry entry {legacy_key!r} has no backend")
        identity = BucketIdentity(backend, str(name))
        key = identity.catalog_key
        item.update({"bucket_id": key, "backend": identity.backend_id, "bucket_name": identity.name, "schema_version": 2})
        prior = migrated.get(key)
        if prior is not None and prior != item:
            raise BucketMigrationError(f"conflicting legacy entries resolve to {key!r}")
        migrated[key] = item
    return migrated


class LegacyBucketAdapter:
    """Expose legacy manager-shaped calls while using one canonical service."""

    def __init__(self, service: BucketService) -> None:
        self.service = service

    def migrate_registry(
        self,
        registry: MutableMapping[str, Mapping[str, Any]],
        *,
        publish: Callable[[Mapping[str, Mapping[str, Any]]], None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        before = copy.deepcopy(dict(registry))
        converted = migrate_legacy_bucket_registry(before)
        try:
            if publish is not None:
                publish(converted)
            registry.clear()
            registry.update(converted)
        except Exception:
            registry.clear()
            registry.update(before)
            raise
        return converted

    def create_bucket(self, manifest: BucketManifest, **kwargs: Any) -> BucketManifest:
        return self.service.create_bucket(manifest, **kwargs)

    def put_object(self, bucket: BucketIdentity | str, key: str, data: bytes, **kwargs: Any) -> Any:
        return self.service.put_object(bucket, key, data, **kwargs)

    def get_object(self, bucket: BucketIdentity | str, key: str, **kwargs: Any) -> Any:
        return self.service.get_object(bucket, key, **kwargs)


BucketManagerAdapter = LegacyBucketAdapter


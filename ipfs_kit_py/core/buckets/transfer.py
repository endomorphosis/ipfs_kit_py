"""Snapshot-bound bucket export/import.

Exports bind the manifest generation and every object version/content digest.
Imports parse and validate the complete envelope first, then publish via the
canonical service only after the staged object set is known-good.
"""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Mapping

from .contracts import BucketIdentity, BucketLifecycleState, BucketManifest
from .service import BucketService


class TransferValidationError(ValueError):
    pass


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class BucketExport:
    document: dict[str, Any]

    def to_bytes(self) -> bytes:
        return json.dumps(self.document, sort_keys=True, separators=(",", ":")).encode()


class BucketTransfer:
    def __init__(self, service: BucketService) -> None:
        self.service = service

    def export(self, bucket: BucketIdentity | str) -> BucketExport:
        bucket_key = bucket.catalog_key if isinstance(bucket, BucketIdentity) else bucket
        catalog = self.service.catalog.snapshot()
        manifest = self.service.catalog.get(bucket_key)
        entries = []
        cursor = None
        while True:
            page = self.service.list_objects(manifest.identity, page_size=1000, cursor=cursor)
            for metadata in page.entries:
                obj = self.service.get_object(manifest.identity, metadata.key, version_id=metadata.version_id)
                entries.append({"key": metadata.key, "version_id": metadata.version_id, "content_id": metadata.content_id,
                                "size": metadata.size, "data": base64.b64encode(obj.data).decode(), "sha256": _digest(obj.data)})
            cursor = page.next_cursor
            if cursor is None:
                break
        manifest_data = manifest.to_dict()
        # A content manifest deliberately includes the object version as well
        # as its digest.  A concurrent overwrite therefore fails closed while
        # exporting rather than silently binding the wrong bytes.
        if self.service.catalog.generation != catalog.generation:
            raise TransferValidationError("bucket catalog changed during export")
        snapshot = {"bucket": manifest.identity.catalog_key, "catalog_generation": catalog.generation,
                    "manifest": manifest_data, "objects": entries}
        snapshot["snapshot_digest"] = _digest(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode())
        return BucketExport({"schema_version": 1, "kind": "ipfs-kit-bucket-export", "snapshot": snapshot})

    def import_(self, payload: bytes | str | Mapping[str, Any], *, create_if_missing: bool = False) -> None:
        try:
            doc = json.loads(payload.decode() if isinstance(payload, bytes) else payload) if not isinstance(payload, Mapping) else dict(payload)
            if doc.get("schema_version") != 1 or doc.get("kind") != "ipfs-kit-bucket-export":
                raise TransferValidationError("unsupported bucket export envelope")
            snap = dict(doc["snapshot"])
            claimed = snap.pop("snapshot_digest")
            actual = _digest(json.dumps(snap, sort_keys=True, separators=(",", ":")).encode())
            if not isinstance(claimed, str) or claimed != actual:
                raise TransferValidationError("snapshot digest mismatch")
            manifest = BucketManifest.from_dict(snap["manifest"])
            if snap.get("bucket") != manifest.identity.catalog_key:
                raise TransferValidationError("snapshot bucket does not match its manifest")
            if not isinstance(snap.get("catalog_generation"), int):
                raise TransferValidationError("snapshot catalog generation is missing")
            if not isinstance(snap.get("objects"), list):
                raise TransferValidationError("content manifest objects must be a list")
            staged: list[tuple[str, bytes]] = []
            seen: set[str] = set()
            for item in snap["objects"]:
                if not isinstance(item, Mapping) or not isinstance(item.get("key"), str) or item["key"] in seen:
                    raise TransferValidationError("invalid or duplicate object key in content manifest")
                if not isinstance(item.get("data"), str) or not isinstance(item.get("sha256"), str):
                    raise TransferValidationError("content manifest data is malformed")
                if isinstance(item.get("size"), bool) or not isinstance(item.get("size"), int):
                    raise TransferValidationError("content manifest size is malformed")
                data = base64.b64decode(item["data"], validate=True)
                if _digest(data) != item["sha256"] or len(data) != item["size"]:
                    raise TransferValidationError(f"invalid content manifest for {item.get('key')!r}")
                staged.append((item["key"], data))
                seen.add(item["key"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TransferValidationError("invalid bucket export") from exc
        try:
            self.service.catalog.get(manifest.identity.catalog_key)
        except Exception:
            if not create_if_missing:
                raise
            # An export reflects the active source bucket.  Creation is a
            # lifecycle transition, so publish an equivalent provisioning
            # manifest and let BucketService activate it transactionally.
            self.service.create_bucket(replace(manifest, lifecycle_state=BucketLifecycleState.PROVISIONING))
            created = True
        else:
            created = False

        # The envelope is fully validated before publication.  If the service
        # rejects a later object, restore every overwritten value (or delete a
        # newly written value); a newly-created bucket is likewise removed.
        # This is a compensating atomic publish at the service boundary.
        previous: dict[str, bytes | None] = {}
        try:
            for key, data in staged:
                try:
                    previous[key] = self.service.get_object(manifest.identity, key).data
                except Exception:
                    previous[key] = None
            for key, data in staged:
                self.service.put_object(manifest.identity, key, data)
        except Exception:
            for key, prior in reversed(tuple(previous.items())):
                try:
                    if prior is None:
                        self.service.delete_object(manifest.identity, key)
                    else:
                        self.service.put_object(manifest.identity, key, prior)
                except Exception:
                    # BucketService records recovery for ambiguous backend
                    # outcomes; keep the original import error authoritative.
                    pass
            if created:
                try:
                    self.service.delete_bucket(manifest.identity)
                except Exception:
                    pass
            raise


def export_bucket(service: BucketService, bucket: BucketIdentity | str) -> BucketExport:
    return BucketTransfer(service).export(bucket)


def import_bucket(
    service: BucketService,
    payload: bytes | str | Mapping[str, Any],
    *,
    create_if_missing: bool = False,
) -> None:
    BucketTransfer(service).import_(payload, create_if_missing=create_if_missing)

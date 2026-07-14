"""Explicit, restart-safe synchronization between local files, IPFS, and Iroh.

IPFS CIDs and Iroh Bao hashes belong to different hash domains.  This module
never aliases one to the other: a mapping has distinct ``cid`` and
``iroh_hash`` fields, and uses a SHA-256 digest of the bytes only as a local
cross-domain integrity key.

The synchronizer operates on explicit objects rather than attempting to infer
mutable directory semantics from content-addressed stores.  A durable
checkpoint is updated after every object, making an operation safe to replay
after a process crash or partial backend failure.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import inspect
import json
import os
import re
import tempfile
import threading
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

import blake3

SYNC_SCHEMA_VERSION = 1
SYNC_MAPPING_KIND = "ipfs-kit/iroh-ipfs-sync-mappings"
SYNC_CHECKPOINT_KIND = "ipfs-kit/iroh-ipfs-sync-checkpoint"
SYNC_RECEIPT_KIND = "ipfs-kit/iroh-ipfs-sync-receipt"

_BACKENDS = frozenset({"local", "ipfs", "iroh"})
_CID_TEXT = re.compile(r"^[A-Za-z0-9]+$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class SyncError(RuntimeError):
    """Base error for an explicit synchronization operation."""


class SyncValidationError(SyncError, ValueError):
    """A sync request or persisted state document is malformed."""


class SyncConflictError(SyncError):
    """A logical path changed since its last recorded synchronization."""


class SyncIntegrityError(SyncError):
    """Backend bytes do not match their content identifier."""


class SyncCheckpointError(SyncError):
    """A checkpoint cannot be resumed with a different request."""


class ConflictPolicy(str, Enum):
    FAIL = "fail"
    SOURCE_WINS = "source-wins"
    DESTINATION_WINS = "destination-wins"
    KEEP_BOTH = "keep-both"


_POLICY_ALIASES = {
    "error": ConflictPolicy.FAIL,
    "strict": ConflictPolicy.FAIL,
    "overwrite": ConflictPolicy.SOURCE_WINS,
    "source": ConflictPolicy.SOURCE_WINS,
    "destination": ConflictPolicy.DESTINATION_WINS,
    "skip": ConflictPolicy.DESTINATION_WINS,
}


class CARStager(Protocol):
    """Optional CAR-aware transfer boundary supplied by an application.

    ``read`` extracts the requested UnixFS object from CAR staging. ``write``
    stages/imports bytes and returns the resulting IPFS CID. Implementations
    may return awaitables.
    """

    def read(self, cid: str, *, operation_id: str, logical_path: str) -> Any: ...

    def write(self, content: bytes, *, operation_id: str, logical_path: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class SyncItem:
    """One explicit logical object to reconcile."""

    logical_path: str
    source: str
    destination: str
    cid: str | None = None
    iroh_hash: str | None = None
    local_path: str | None = None
    destination_path: str | None = None
    content_sha256: str | None = None
    deleted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "logical_path", _logical_path(self.logical_path))
        if (
            not isinstance(self.source, str)
            or not isinstance(self.destination, str)
            or self.source not in _BACKENDS
            or self.destination not in _BACKENDS
        ):
            raise SyncValidationError("source and destination must be local, ipfs, or iroh")
        if self.source == self.destination:
            raise SyncValidationError("source and destination backends must differ")
        if self.cid is not None:
            validate_cid(self.cid)
        if self.iroh_hash is not None:
            _validate_iroh_hash(self.iroh_hash)
        if self.content_sha256 is not None and not _HEX_DIGEST.fullmatch(self.content_sha256):
            raise SyncValidationError("content_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.deleted, bool):
            raise SyncValidationError("deleted must be a boolean")
        if not self.deleted:
            required = {
                "ipfs": self.cid,
                "iroh": self.iroh_hash,
                "local": self.local_path,
            }[self.source]
            if not required:
                raise SyncValidationError(f"{self.source} source requires its content identifier")
        if self.destination == "local" and not self.destination_path:
            raise SyncValidationError("local destination requires destination_path")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SyncReconciliationReceipt:
    receipt_id: str
    operation_id: str
    checkpoint_id: str
    started_at: str
    completed_at: str
    status: str
    conflict_policy: str
    resumed: bool
    dry_run: bool
    total_items: int
    transferred_items: int
    deduplicated_items: int
    deleted_items: int
    skipped_items: int
    failed_items: int
    transferred_bytes: int
    entries: tuple[Mapping[str, Any], ...]
    errors: tuple[Mapping[str, Any], ...]
    schema_version: int = SYNC_SCHEMA_VERSION
    kind: str = SYNC_RECEIPT_KIND

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["entries"] = [copy.deepcopy(dict(item)) for item in self.entries]
        value["errors"] = [copy.deepcopy(dict(item)) for item in self.errors]
        return value


_MAPPING_FIELDS = (
    "logical_path",
    "cid",
    "iroh_hash",
    "local_path",
    "content_sha256",
    "size_bytes",
    "deleted",
    "updated_at",
    "lineage",
)

SYNC_MAPPING_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ipfs-kit.dev/schemas/iroh-ipfs-sync-mapping-v1.json",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "kind", "revision", "mappings"],
    "properties": {
        "schema_version": {"const": SYNC_SCHEMA_VERSION},
        "kind": {"const": SYNC_MAPPING_KIND},
        "revision": {"type": "integer", "minimum": 0},
        "mappings": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": False,
                "required": list(_MAPPING_FIELDS),
                "properties": {
                    "logical_path": {"type": "string", "minLength": 1},
                    "cid": {"type": ["string", "null"]},
                    "iroh_hash": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
                    "local_path": {"type": ["string", "null"]},
                    "content_sha256": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
                    "size_bytes": {"type": ["integer", "null"], "minimum": 0},
                    "deleted": {"type": "boolean"},
                    "updated_at": {"type": "string", "format": "date-time"},
                    "lineage": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
    },
}

SYNC_CHECKPOINT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ipfs-kit.dev/schemas/iroh-ipfs-sync-checkpoint-v1.json",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "kind",
        "checkpoint_id",
        "operation_id",
        "request_digest",
        "conflict_policy",
        "status",
        "created_at",
        "updated_at",
        "items",
    ],
    "properties": {
        "schema_version": {"const": SYNC_SCHEMA_VERSION},
        "kind": {"const": SYNC_CHECKPOINT_KIND},
        "checkpoint_id": {"type": "string", "minLength": 1},
        "operation_id": {"type": "string", "minLength": 1},
        "request_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "conflict_policy": {"enum": [item.value for item in ConflictPolicy]},
        "status": {"enum": ["running", "success", "partial", "failed"]},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["request", "state", "attempts"],
                "properties": {
                    "request": {"type": "object"},
                    "state": {"enum": ["pending", "running", "completed", "failed"]},
                    "attempts": {"type": "integer", "minimum": 0},
                    "result": {"type": ["object", "null"]},
                    "error": {"type": ["object", "null"]},
                },
            },
        },
    },
}

SYNC_RECEIPT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ipfs-kit.dev/schemas/iroh-ipfs-sync-receipt-v1.json",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "kind",
        "receipt_id",
        "operation_id",
        "checkpoint_id",
        "started_at",
        "completed_at",
        "status",
        "conflict_policy",
        "resumed",
        "dry_run",
        "total_items",
        "transferred_items",
        "deduplicated_items",
        "deleted_items",
        "skipped_items",
        "failed_items",
        "transferred_bytes",
        "entries",
        "errors",
    ],
    "properties": {
        "schema_version": {"const": SYNC_SCHEMA_VERSION},
        "kind": {"const": SYNC_RECEIPT_KIND},
        "receipt_id": {"type": "string", "minLength": 1},
        "operation_id": {"type": "string", "minLength": 1},
        "checkpoint_id": {"type": "string", "minLength": 1},
        "started_at": {"type": "string", "format": "date-time"},
        "completed_at": {"type": "string", "format": "date-time"},
        "status": {"enum": ["success", "partial", "failed"]},
        "conflict_policy": {"enum": [item.value for item in ConflictPolicy]},
        "resumed": {"type": "boolean"},
        "dry_run": {"type": "boolean"},
        "total_items": {"type": "integer", "minimum": 0},
        "transferred_items": {"type": "integer", "minimum": 0},
        "deduplicated_items": {"type": "integer", "minimum": 0},
        "deleted_items": {"type": "integer", "minimum": 0},
        "skipped_items": {"type": "integer", "minimum": 0},
        "failed_items": {"type": "integer", "minimum": 0},
        "transferred_bytes": {"type": "integer", "minimum": 0},
        "entries": {"type": "array", "items": {"type": "object"}},
        "errors": {"type": "array", "items": {"type": "object"}},
    },
}


class SyncStateStore:
    """Atomic mapping/checkpoint persistence and append-only receipts."""

    def __init__(self, state_dir: str | os.PathLike[str]) -> None:
        self.root = Path(state_dir)
        self.checkpoint_dir = self.root / "checkpoints"
        self.mapping_path = self.root / "mappings.json"
        self.receipt_path = self.root / "receipts.jsonl"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        _chmod_private(self.root, directory=True)
        _chmod_private(self.checkpoint_dir, directory=True)
        self._lock = threading.RLock()

    def mappings(self) -> dict[str, Any]:
        with self._lock:
            if not self.mapping_path.exists():
                return _empty_mappings()
            return _validate_mapping_document(_read_json(self.mapping_path))

    def get_mapping(self, logical_path: str) -> dict[str, Any] | None:
        item = self.mappings()["mappings"].get(_logical_path(logical_path))
        return copy.deepcopy(item) if item is not None else None

    def put_mapping(self, value: Mapping[str, Any]) -> dict[str, Any]:
        mapping = _validate_mapping(value)
        with self._lock:
            document = self.mappings()
            document["revision"] += 1
            document["mappings"][mapping["logical_path"]] = mapping
            _atomic_json(self.mapping_path, document)
        return copy.deepcopy(mapping)

    def checkpoint_path(self, operation_id: str) -> Path:
        digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
        return self.checkpoint_dir / f"{digest}.json"

    def get_checkpoint(self, operation_id: str) -> dict[str, Any] | None:
        with self._lock:
            path = self.checkpoint_path(operation_id)
            if not path.exists():
                return None
            value = _validate_checkpoint(_read_json(path))
            if value["operation_id"] != operation_id:
                raise SyncCheckpointError("checkpoint operation ID does not match its key")
            return value

    def put_checkpoint(self, checkpoint: Mapping[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(dict(checkpoint))
        value["updated_at"] = _now()
        value = _validate_checkpoint(value)
        with self._lock:
            _atomic_json(self.checkpoint_path(value["operation_id"]), value)
        return copy.deepcopy(value)

    def append_receipt(self, receipt: Mapping[str, Any]) -> None:
        value = _validate_receipt(copy.deepcopy(dict(receipt)))
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            descriptor = os.open(self.receipt_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())

    def list_receipts(self, operation_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if not self.receipt_path.exists():
                return []
            values = [
                _validate_receipt(json.loads(line))
                for line in self.receipt_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        if operation_id is not None:
            values = [item for item in values if item["operation_id"] == operation_id]
        return values


class IrohIPFSSyncAdapter:
    """Reconcile explicitly identified objects across local, IPFS, and Iroh."""

    ConflictPolicy = ConflictPolicy
    FAIL = ConflictPolicy.FAIL

    def __init__(
        self,
        ipfs: Any,
        iroh: Any,
        state_dir: str | os.PathLike[str],
        *,
        local_root: str | os.PathLike[str] | None = None,
        car_stager: CARStager | Any | None = None,
    ) -> None:
        self.ipfs = ipfs
        self.iroh = iroh
        self.state = SyncStateStore(state_dir)
        self.local_root = None if local_root is None else Path(local_root).resolve()
        self.car_stager = car_stager
        self._lock = asyncio.Lock()

    async def reconcile(
        self,
        items: Iterable[SyncItem | Mapping[str, Any]],
        *,
        operation_id: str | None = None,
        conflict_policy: ConflictPolicy | str = ConflictPolicy.FAIL,
        use_car: bool = False,
        dry_run: bool = False,
        continue_on_error: bool = True,
    ) -> dict[str, Any]:
        """Transfer all items and persist a reconciliation receipt.

        Reusing ``operation_id`` resumes its checkpoint. Completed items are
        replayed from the checkpoint without touching a backend. Failed items
        are attempted again and retain their attempt count.
        """

        requests = tuple(_coerce_item(item) for item in items)
        if not requests:
            raise SyncValidationError("at least one sync item is required")
        if not all(isinstance(value, bool) for value in (use_car, dry_run, continue_on_error)):
            raise SyncValidationError("use_car, dry_run, and continue_on_error must be booleans")
        if use_car and self.car_stager is None:
            raise SyncValidationError("CAR staging was requested without a CAR stager")
        policy = _conflict_policy(conflict_policy)
        op_id = _operation_id(operation_id)
        started = _now()

        async with self._lock:
            checkpoint, resumed = self._load_or_create_checkpoint(requests, op_id, policy)
            entries: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []

            for index, request in enumerate(requests):
                progress = checkpoint["items"][index]
                if progress["state"] == "completed":
                    result = copy.deepcopy(progress["result"])
                    result["replayed"] = True
                    entries.append(result)
                    continue

                progress.update(
                    {"state": "running", "attempts": progress["attempts"] + 1, "error": None}
                )
                checkpoint["status"] = "running"
                checkpoint = self.state.put_checkpoint(checkpoint)
                try:
                    result = await self._reconcile_item(
                        request, op_id, policy, use_car=use_car, dry_run=dry_run
                    )
                except Exception as exc:
                    error = _safe_error(exc, request.logical_path, index)
                    progress = checkpoint["items"][index]
                    progress.update({"state": "failed", "result": None, "error": error})
                    checkpoint = self.state.put_checkpoint(checkpoint)
                    errors.append(error)
                    if not continue_on_error:
                        break
                else:
                    progress = checkpoint["items"][index]
                    progress.update({"state": "completed", "result": result, "error": None})
                    checkpoint = self.state.put_checkpoint(checkpoint)
                    entries.append(result)

            failures = sum(item["state"] == "failed" for item in checkpoint["items"])
            pending = sum(item["state"] in {"pending", "running"} for item in checkpoint["items"])
            completed = sum(item["state"] == "completed" for item in checkpoint["items"])
            if failures or pending:
                status = "failed" if completed == 0 else "partial"
            else:
                status = "success"
            checkpoint["status"] = status
            checkpoint = self.state.put_checkpoint(checkpoint)
            receipt = self._receipt(
                op_id,
                checkpoint["checkpoint_id"],
                started,
                status,
                policy,
                resumed,
                dry_run,
                entries,
                errors,
                len(requests),
            )
            self.state.append_receipt(receipt)
            return receipt

    async def import_from_ipfs(
        self,
        cid: str,
        *,
        logical_path: str | None = None,
        operation_id: str | None = None,
        conflict_policy: ConflictPolicy | str = ConflictPolicy.FAIL,
        use_car: bool = False,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        cid = validate_cid(cid)
        item = SyncItem(
            logical_path=logical_path or cid,
            source="ipfs",
            destination="iroh",
            cid=cid,
            content_sha256=expected_sha256,
        )
        return await self.reconcile(
            [item], operation_id=operation_id, conflict_policy=conflict_policy, use_car=use_car
        )

    async def export_to_ipfs(
        self,
        iroh_hash: str,
        *,
        logical_path: str | None = None,
        operation_id: str | None = None,
        conflict_policy: ConflictPolicy | str = ConflictPolicy.FAIL,
        use_car: bool = False,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        digest = _validate_iroh_hash(iroh_hash)
        item = SyncItem(
            logical_path=logical_path or digest,
            source="iroh",
            destination="ipfs",
            iroh_hash=digest,
            content_sha256=expected_sha256,
        )
        return await self.reconcile(
            [item], operation_id=operation_id, conflict_policy=conflict_policy, use_car=use_car
        )

    async def import_from_local(
        self,
        source: str | os.PathLike[str],
        *,
        logical_path: str | None = None,
        operation_id: str | None = None,
        conflict_policy: ConflictPolicy | str = ConflictPolicy.FAIL,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        path = Path(source)
        item = SyncItem(
            logical_path=logical_path or path.name,
            source="local",
            destination="iroh",
            local_path=os.fspath(path),
            content_sha256=expected_sha256,
        )
        return await self.reconcile(
            [item], operation_id=operation_id, conflict_policy=conflict_policy
        )

    async def export_to_local(
        self,
        iroh_hash: str,
        destination: str | os.PathLike[str],
        *,
        logical_path: str | None = None,
        operation_id: str | None = None,
        conflict_policy: ConflictPolicy | str = ConflictPolicy.FAIL,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        path = Path(destination)
        self._local_destination(os.fspath(path))
        digest = _validate_iroh_hash(iroh_hash)
        item = SyncItem(
            logical_path=logical_path or path.name,
            source="iroh",
            destination="local",
            iroh_hash=digest,
            destination_path=os.fspath(path),
            content_sha256=expected_sha256,
        )
        return await self.reconcile(
            [item], operation_id=operation_id, conflict_policy=conflict_policy
        )

    # Stable aliases used by the CLI/API layers and older callers.
    import_ipfs = import_from_ipfs
    export_ipfs = export_to_ipfs
    import_local = import_from_local
    export_local = export_to_local
    sync = reconcile

    def get_mapping(self, logical_path: str) -> dict[str, Any] | None:
        return self.state.get_mapping(logical_path)

    def list_receipts(self, operation_id: str | None = None) -> list[dict[str, Any]]:
        return self.state.list_receipts(operation_id)

    def _load_or_create_checkpoint(
        self, requests: tuple[SyncItem, ...], operation_id: str, policy: ConflictPolicy
    ) -> tuple[dict[str, Any], bool]:
        payload = {"items": [item.to_dict() for item in requests], "conflict_policy": policy.value}
        digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
        existing = self.state.get_checkpoint(operation_id)
        if existing is not None:
            if existing["request_digest"] != digest or existing["conflict_policy"] != policy.value:
                raise SyncCheckpointError(
                    "operation_id already belongs to a different request or conflict policy"
                )
            return existing, True
        now = _now()
        checkpoint = {
            "schema_version": SYNC_SCHEMA_VERSION,
            "kind": SYNC_CHECKPOINT_KIND,
            "checkpoint_id": str(uuid.uuid4()),
            "operation_id": operation_id,
            "request_digest": digest,
            "conflict_policy": policy.value,
            "status": "running",
            "created_at": now,
            "updated_at": now,
            "items": [
                {
                    "request": item.to_dict(),
                    "state": "pending",
                    "attempts": 0,
                    "result": None,
                    "error": None,
                }
                for item in requests
            ],
        }
        return self.state.put_checkpoint(checkpoint), False

    async def _reconcile_item(
        self,
        request: SyncItem,
        operation_id: str,
        policy: ConflictPolicy,
        *,
        use_car: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        existing = self.state.get_mapping(request.logical_path)
        if request.deleted:
            return await self._delete_item(request, existing, operation_id, policy, dry_run)

        content, source_meta = await self._read_source(request, operation_id, use_car)
        sha256 = hashlib.sha256(content).hexdigest()
        if request.content_sha256 and request.content_sha256 != sha256:
            raise SyncIntegrityError("source bytes do not match expected content_sha256")

        effective_path = request.logical_path
        if existing and not existing.get("deleted") and existing.get("content_sha256") != sha256:
            if policy is ConflictPolicy.FAIL:
                raise SyncConflictError(f"logical path {request.logical_path} has diverged")
            if policy is ConflictPolicy.DESTINATION_WINS:
                return self._entry(
                    request,
                    existing,
                    "skipped",
                    0,
                    operation_id,
                    use_car,
                    note="destination-wins conflict policy",
                )
            if policy is ConflictPolicy.KEEP_BOTH:
                effective_path = self._conflict_path(request.logical_path, sha256)
                existing = self.state.get_mapping(effective_path)

        if existing and not existing.get("deleted") and existing.get("content_sha256") == sha256:
            if await self._destination_present(request, existing):
                return self._entry(
                    request,
                    existing,
                    "deduplicated",
                    0,
                    operation_id,
                    use_car,
                    logical_path=effective_path,
                )

        if dry_run:
            destination_meta = self._planned_destination(request, content, effective_path)
            mapping = self._build_mapping(
                request,
                existing,
                effective_path,
                source_meta,
                destination_meta,
                sha256,
                len(content),
                operation_id,
                True,
            )
            return self._entry(
                request, mapping, "planned", 0, operation_id, use_car, logical_path=effective_path
            )

        destination_meta = await self._write_destination(
            request, content, sha256, operation_id, effective_path, use_car
        )
        mapping = self._build_mapping(
            request,
            existing,
            effective_path,
            source_meta,
            destination_meta,
            sha256,
            len(content),
            operation_id,
            False,
        )
        self.state.put_mapping(mapping)
        return self._entry(
            request,
            mapping,
            "transferred",
            len(content),
            operation_id,
            use_car,
            logical_path=effective_path,
        )

    async def _read_source(
        self, item: SyncItem, operation_id: str, use_car: bool
    ) -> tuple[bytes, dict[str, Any]]:
        if item.source == "local":
            path = Path(item.local_path or "")
            if not path.is_file():
                raise FileNotFoundError(f"local source is not a file: {os.fspath(path)}")
            content = await asyncio.to_thread(path.read_bytes)
            return content, {"local_path": os.fspath(path)}
        if item.source == "ipfs":
            cid = validate_cid(item.cid or "")
            content = await (
                _car_read(self.car_stager, cid, operation_id, item.logical_path)
                if use_car
                else _ipfs_read(self.ipfs, cid)
            )
            _verify_cid_if_supported(cid, content)
            return content, {"cid": cid}
        digest = _validate_iroh_hash(item.iroh_hash)
        content = await _iroh_read(self.iroh, digest)
        actual = blake3.blake3(content).hexdigest()
        if actual != digest:
            raise SyncIntegrityError(f"Iroh content hash mismatch: expected {digest}, got {actual}")
        return content, {"iroh_hash": digest}

    async def _write_destination(
        self,
        item: SyncItem,
        content: bytes,
        sha256: str,
        operation_id: str,
        logical_path: str,
        use_car: bool,
    ) -> dict[str, Any]:
        if item.destination == "local":
            path = self._local_target(item, logical_path)
            await asyncio.to_thread(_atomic_bytes, path, content)
            actual = hashlib.sha256(await asyncio.to_thread(path.read_bytes)).hexdigest()
            if actual != sha256:
                raise SyncIntegrityError("local export failed post-write verification")
            return {"local_path": os.fspath(path)}
        if item.destination == "ipfs":
            result = await (
                _car_write(self.car_stager, content, operation_id, logical_path)
                if use_car
                else _ipfs_write(self.ipfs, content, operation_id)
            )
            cid = _extract_cid(result)
            _verify_cid_if_supported(cid, content)
            return {"cid": cid}
        expected = blake3.blake3(content).hexdigest()
        result = await _iroh_write(self.iroh, content, expected, operation_id)
        digest = _extract_iroh_hash(result)
        if digest != expected:
            raise SyncIntegrityError(
                f"Iroh ingest returned a different hash: expected {expected}, got {digest}"
            )
        return {"iroh_hash": digest}

    async def _destination_present(self, request: SyncItem, mapping: Mapping[str, Any]) -> bool:
        if request.destination == "iroh":
            digest = mapping.get("iroh_hash")
            return bool(digest and await _backend_exists(self.iroh, digest, iroh=True))
        if request.destination == "ipfs":
            cid = mapping.get("cid")
            return bool(cid and await _backend_exists(self.ipfs, cid, iroh=False))
        path_text = mapping.get("local_path") or request.destination_path
        if not path_text:
            return False
        path = self._local_destination(str(path_text))
        if not path.is_file():
            return False
        return hashlib.sha256(await asyncio.to_thread(path.read_bytes)).hexdigest() == mapping.get(
            "content_sha256"
        )

    async def _delete_item(
        self,
        request: SyncItem,
        existing: Mapping[str, Any] | None,
        operation_id: str,
        policy: ConflictPolicy,
        dry_run: bool,
    ) -> dict[str, Any]:
        if existing is None or existing.get("deleted"):
            mapping = self._tombstone(request, operation_id)
            if not dry_run:
                self.state.put_mapping(mapping)
            return self._entry(
                request, mapping, "planned" if dry_run else "deduplicated", 0, operation_id, False
            )
        if request.content_sha256 and existing.get("content_sha256") != request.content_sha256:
            if policy is ConflictPolicy.FAIL:
                raise SyncConflictError("delete precondition does not match the mapped content")
            if policy is ConflictPolicy.DESTINATION_WINS:
                return self._entry(
                    request,
                    existing,
                    "skipped",
                    0,
                    operation_id,
                    False,
                    note="destination-wins conflict policy",
                )
        if dry_run:
            return self._entry(
                request, self._tombstone(request, operation_id), "planned", 0, operation_id, False
            )

        # Iroh blobs are immutable and shared, so deletion only tombstones the
        # mapping. IPFS deletion means removing our pin, never deleting blocks.
        if request.destination == "local":
            path = self._local_destination(
                request.destination_path or existing.get("local_path") or ""
            )
            await asyncio.to_thread(path.unlink, missing_ok=True)
        elif request.destination == "ipfs" and existing.get("cid"):
            await _ipfs_unpin(self.ipfs, existing["cid"])
        mapping = copy.deepcopy(dict(existing))
        mapping.update({"deleted": True, "updated_at": _now()})
        mapping.setdefault("lineage", []).append(
            {
                "operation_id": operation_id,
                "source_backend": request.source,
                "destination_backend": request.destination,
                "action": "delete",
                "at": _now(),
            }
        )
        self.state.put_mapping(mapping)
        return self._entry(request, mapping, "deleted", 0, operation_id, False)

    def _build_mapping(
        self,
        request: SyncItem,
        existing: Mapping[str, Any] | None,
        logical_path: str,
        source_meta: Mapping[str, Any],
        destination_meta: Mapping[str, Any],
        sha256: str,
        size: int,
        operation_id: str,
        dry_run: bool,
    ) -> dict[str, Any]:
        previous = dict(existing or {})
        same_content = previous.get("content_sha256") == sha256
        cid = (
            source_meta.get("cid")
            or destination_meta.get("cid")
            or (previous.get("cid") if same_content else None)
        )
        iroh_hash = (
            source_meta.get("iroh_hash")
            or destination_meta.get("iroh_hash")
            or (previous.get("iroh_hash") if same_content else None)
        )
        local_path = (
            source_meta.get("local_path")
            or destination_meta.get("local_path")
            or (previous.get("local_path") if same_content else None)
        )
        if cid is not None:
            cid = validate_cid(cid)
        if iroh_hash is not None:
            iroh_hash = _validate_iroh_hash(iroh_hash)
        lineage = copy.deepcopy(list(previous.get("lineage", [])))
        lineage.append(
            {
                "operation_id": operation_id,
                "source_backend": request.source,
                "destination_backend": request.destination,
                "action": "plan" if dry_run else "transfer",
                "at": _now(),
            }
        )
        return {
            "logical_path": logical_path,
            "cid": cid,
            "iroh_hash": iroh_hash,
            "local_path": local_path,
            "content_sha256": sha256,
            "size_bytes": size,
            "deleted": False,
            "updated_at": _now(),
            "lineage": lineage,
        }

    def _tombstone(self, request: SyncItem, operation_id: str) -> dict[str, Any]:
        return {
            "logical_path": request.logical_path,
            "cid": request.cid,
            "iroh_hash": request.iroh_hash,
            "local_path": request.local_path,
            "content_sha256": request.content_sha256,
            "size_bytes": None,
            "deleted": True,
            "updated_at": _now(),
            "lineage": [
                {
                    "operation_id": operation_id,
                    "source_backend": request.source,
                    "destination_backend": request.destination,
                    "action": "delete",
                    "at": _now(),
                }
            ],
        }

    def _entry(
        self,
        request: SyncItem,
        mapping: Mapping[str, Any],
        status: str,
        bytes_count: int,
        operation_id: str,
        use_car: bool,
        *,
        logical_path: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        value = {
            "logical_path": logical_path or request.logical_path,
            "source_backend": request.source,
            "destination_backend": request.destination,
            "status": status,
            "size_bytes": mapping.get("size_bytes"),
            "transferred_bytes": bytes_count,
            "content_sha256": mapping.get("content_sha256"),
            "cid": mapping.get("cid"),
            "iroh_hash": mapping.get("iroh_hash"),
            "local_path": mapping.get("local_path"),
            "car_staged": bool(use_car),
            "lineage": {
                "operation_id": operation_id,
                "source_backend": request.source,
                "destination_backend": request.destination,
            },
        }
        if note:
            value["note"] = note
        return value

    def _conflict_path(self, logical_path: str, sha256: str) -> str:
        candidate = f"{logical_path}.conflict-{sha256[:12]}"
        suffix = 1
        while (mapping := self.state.get_mapping(candidate)) is not None and mapping.get(
            "content_sha256"
        ) != sha256:
            candidate = f"{logical_path}.conflict-{sha256[:12]}-{suffix}"
            suffix += 1
        return candidate

    def _local_destination(self, path_text: str) -> Path:
        path = Path(path_text)
        resolved = (
            path.resolve()
            if path.is_absolute()
            else ((self.local_root or Path.cwd()) / path).resolve()
        )
        if (
            self.local_root is not None
            and resolved != self.local_root
            and self.local_root not in resolved.parents
        ):
            raise SyncValidationError("local destination escapes configured local_root")
        return resolved

    def _local_target(self, request: SyncItem, logical_path: str) -> Path:
        path = Path(request.destination_path or "")
        if logical_path != request.logical_path:
            suffix = logical_path[len(request.logical_path) :]
            path = path.with_name(path.name + suffix)
        return self._local_destination(os.fspath(path))

    def _planned_destination(
        self, request: SyncItem, content: bytes, logical_path: str
    ) -> dict[str, Any]:
        if request.destination == "iroh":
            return {"iroh_hash": blake3.blake3(content).hexdigest()}
        if request.destination == "local":
            return {"local_path": os.fspath(self._local_target(request, logical_path))}
        return {}

    @staticmethod
    def _receipt(
        operation_id: str,
        checkpoint_id: str,
        started: str,
        status: str,
        policy: ConflictPolicy,
        resumed: bool,
        dry_run: bool,
        entries: list[dict[str, Any]],
        errors: list[dict[str, Any]],
        total: int,
    ) -> dict[str, Any]:
        return SyncReconciliationReceipt(
            receipt_id=str(uuid.uuid4()),
            operation_id=operation_id,
            checkpoint_id=checkpoint_id,
            started_at=started,
            completed_at=_now(),
            status=status,
            conflict_policy=policy.value,
            resumed=resumed,
            dry_run=dry_run,
            total_items=total,
            transferred_items=sum(item.get("status") == "transferred" for item in entries),
            deduplicated_items=sum(item.get("status") == "deduplicated" for item in entries),
            deleted_items=sum(item.get("status") == "deleted" for item in entries),
            skipped_items=sum(item.get("status") == "skipped" for item in entries),
            failed_items=len(errors),
            transferred_bytes=sum(int(item.get("transferred_bytes", 0)) for item in entries),
            entries=tuple(entries),
            errors=tuple(errors),
        ).to_dict()


def validate_cid(cid: str) -> str:
    """Validate a CID-shaped opaque identifier without confusing hash domains."""

    if not isinstance(cid, str) or not cid.strip() or "/" in cid:
        raise SyncValidationError("cid must be a non-empty bare CID string")
    if _HEX_DIGEST.fullmatch(cid):
        raise SyncValidationError("a 64-character Iroh hash must never be labeled as a CID")
    if not _CID_TEXT.fullmatch(cid):
        raise SyncValidationError("cid contains invalid characters")
    return cid


def verify_cid(content: bytes, cid: str) -> bool | None:
    """Verify supported CIDv0/v1 multihashes, returning ``None`` for unknown forms.

    Unknown codecs or hash algorithms do not make a mapping invalid; IPFS is
    authoritative for those forms. SHA-256 and SHA-512 multihashes are checked
    locally so corruption is caught before a mapping is committed.
    """

    cid = validate_cid(cid)
    try:
        if cid.startswith("Qm"):
            multihash = _base58_decode(cid)
        else:
            raw = base64.b32decode(cid.upper() + "=" * ((8 - len(cid) % 8) % 8))
            version, offset = _varint(raw, 0)
            if version != 1:
                return None
            _, offset = _varint(raw, offset)  # content codec
            multihash = raw[offset:]
        code, offset = _varint(multihash, 0)
        length, offset = _varint(multihash, offset)
        payload = multihash[offset:]
        if len(payload) != length:
            return False
        if code == 0x12:
            return hashlib.sha256(content).digest() == payload
        if code == 0x13:
            return hashlib.sha512(content).digest() == payload
        return None
    except (ValueError, UnicodeError, base64.binascii.Error):
        return None


def _verify_cid_if_supported(cid: str, content: bytes) -> None:
    if verify_cid(content, cid) is False:
        raise SyncIntegrityError(f"IPFS bytes do not match CID {cid}")


async def _ipfs_read(ipfs: Any, cid: str) -> bytes:
    for name, argument in (("cat", cid), ("cat_file", f"/ipfs/{cid}"), ("read", cid)):
        method = getattr(ipfs, name, None)
        if method is None:
            continue
        result = await _call(method, argument)
        if isinstance(result, Mapping):
            result = result.get("data", result.get("content"))
        return _bytes(result, "IPFS read")
    raise SyncValidationError("IPFS adapter must provide cat, cat_file, or read")


async def _ipfs_write(ipfs: Any, content: bytes, operation_id: str) -> str:
    for name in ("add_bytes", "add", "put"):
        method = getattr(ipfs, name, None)
        if method is None:
            continue
        if name == "add_bytes":
            return _extract_cid(await _call(method, content))
        try:
            result = await _call(method, content, operation_id=operation_id)
        except TypeError as first_error:
            try:
                result = await _call(method, content)
            except TypeError:
                path = await asyncio.to_thread(_stage_bytes, content)
                try:
                    try:
                        result = await _call(method, os.fspath(path))
                    except TypeError:
                        raise first_error
                finally:
                    path.unlink(missing_ok=True)
        return _extract_cid(result)
    raise SyncValidationError("IPFS adapter must provide add_bytes, add, or put")


async def _ipfs_unpin(ipfs: Any, cid: str) -> None:
    for owner, name in ((ipfs, "pin_rm"), (getattr(ipfs, "pin", None), "rm"), (ipfs, "remove")):
        method = getattr(owner, name, None) if owner is not None else None
        if method is not None:
            await _call(method, cid)
            return


async def _iroh_read(iroh: Any, digest: str) -> bytes:
    method = getattr(iroh, "read_range", None)
    if method is not None:
        try:
            result = await _call(method, digest, 0, None)
        except TypeError:
            try:
                result = await _call(method, digest, start=0, end=None)
            except TypeError:
                result = await _call(method, digest, offset=0, length=None)
        return _bytes(result, "Iroh read")
    for name in ("read", "get", "cat"):
        method = getattr(iroh, name, None)
        if method is not None:
            return _bytes(await _call(method, digest), "Iroh read")
    raise SyncValidationError("Iroh adapter must provide read_range, read, get, or cat")


async def _iroh_write(iroh: Any, content: bytes, expected: str, operation_id: str) -> Any:
    method = getattr(iroh, "ingest", None)
    if method is not None:
        if _accepts_keyword(method, "operation_id"):
            return await _call(method, content, expected_hash=expected, operation_id=operation_id)
        return await _call(method, content, expected_hash=expected)
    for name in ("put", "write"):
        method = getattr(iroh, name, None)
        if method is None:
            continue
        try:
            return await _call(method, expected, content, operation_id=operation_id)
        except TypeError:
            return await _call(method, expected, content)
    raise SyncValidationError("Iroh adapter must provide ingest, put, or write")


async def _backend_exists(backend: Any, identifier: str, *, iroh: bool) -> bool:
    method = getattr(backend, "exists", None)
    if method is not None:
        return bool(await _call(method, identifier))
    if iroh:
        method = getattr(backend, "stat", None)
        if method is not None:
            try:
                await _call(method, identifier)
                return True
            except Exception as exc:
                if exc.__class__.__name__ in {
                    "IrohNotFoundError",
                    "FileNotFoundError",
                    "NotFoundError",
                }:
                    return False
                raise
    # No existence API: conservatively transfer rather than claiming dedupe.
    return False


async def _car_read(stager: Any, cid: str, operation_id: str, logical_path: str) -> bytes:
    method = getattr(stager, "read", None) or getattr(stager, "stage_from_ipfs", None)
    if method is None:
        raise SyncValidationError("CAR stager must provide read or stage_from_ipfs")
    result = await _call(method, cid, operation_id=operation_id, logical_path=logical_path)
    if isinstance(result, (str, os.PathLike)):
        result = await asyncio.to_thread(Path(result).read_bytes)
    return _bytes(result, "CAR read")


async def _car_write(stager: Any, content: bytes, operation_id: str, logical_path: str) -> Any:
    method = getattr(stager, "write", None) or getattr(stager, "stage_to_ipfs", None)
    if method is None:
        raise SyncValidationError("CAR stager must provide write or stage_to_ipfs")
    return await _call(method, content, operation_id=operation_id, logical_path=logical_path)


async def _call(method: Any, *args: Any, **kwargs: Any) -> Any:
    if inspect.iscoroutinefunction(method):
        return await method(*args, **kwargs)
    value = await asyncio.to_thread(method, *args, **kwargs)
    return await value if inspect.isawaitable(value) else value


def _accepts_keyword(method: Any, name: str) -> bool:
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return True
    return name in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


def _extract_cid(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("ascii")
    if isinstance(value, str):
        return validate_cid(value)
    if isinstance(value, Mapping):
        for key in ("cid", "Hash", "hash", "Cid", "CID"):
            candidate = value.get(key)
            if isinstance(candidate, Mapping):
                candidate = candidate.get("/")
            if candidate:
                return validate_cid(
                    candidate.decode("ascii") if isinstance(candidate, bytes) else candidate
                )
    raise SyncIntegrityError("IPFS write did not return a CID")


def _extract_iroh_hash(value: Any) -> str:
    if isinstance(value, str):
        return _validate_iroh_hash(value)
    if isinstance(value, Mapping):
        for key in ("iroh_hash", "blob_hash", "hash"):
            if value.get(key):
                return _validate_iroh_hash(value[key])
    for name in ("iroh_hash", "blob_hash", "hash"):
        candidate = getattr(value, name, None)
        if candidate:
            return _validate_iroh_hash(candidate)
    raise SyncIntegrityError("Iroh ingest did not return an iroh_hash")


def _bytes(value: Any, operation: str) -> bytes:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    raise SyncIntegrityError(f"{operation} did not return bytes")


def _coerce_item(value: SyncItem | Mapping[str, Any]) -> SyncItem:
    if isinstance(value, SyncItem):
        return value
    if not isinstance(value, Mapping):
        raise SyncValidationError("sync items must be SyncItem objects or mappings")
    data = dict(value)
    if "path" in data and "logical_path" not in data:
        data["logical_path"] = data.pop("path")
    try:
        return SyncItem(**data)
    except TypeError as exc:
        raise SyncValidationError(f"invalid sync item fields: {exc}") from None


def _logical_path(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise SyncValidationError("logical_path must be a non-empty relative POSIX path")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise SyncValidationError("logical_path must be normalized and traversal-free")
    normalized = path.as_posix()
    if normalized != value:
        raise SyncValidationError("logical_path must be normalized")
    return normalized


def _validate_iroh_hash(value: Any) -> str:
    if not isinstance(value, str) or not _HEX_DIGEST.fullmatch(value):
        raise SyncValidationError("iroh_hash must be a 64-character lowercase Bao hash")
    return value


def _conflict_policy(value: ConflictPolicy | str) -> ConflictPolicy:
    if isinstance(value, ConflictPolicy):
        return value
    try:
        alias = _POLICY_ALIASES.get(str(value))
        return alias if alias is not None else ConflictPolicy(value)
    except (TypeError, ValueError):
        raise SyncValidationError("unsupported conflict policy") from None


def _operation_id(value: str | None) -> str:
    if value is None:
        return str(uuid.uuid4())
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise SyncValidationError("operation_id must be a non-empty string up to 256 characters")
    return value


def _validate_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(dict(value))
    if set(data) != set(_MAPPING_FIELDS):
        raise SyncValidationError("mapping fields do not match the versioned schema")
    data["logical_path"] = _logical_path(data["logical_path"])
    if data["cid"] is not None:
        data["cid"] = validate_cid(data["cid"])
    if data["iroh_hash"] is not None:
        data["iroh_hash"] = _validate_iroh_hash(data["iroh_hash"])
    if data["content_sha256"] is not None and not _HEX_DIGEST.fullmatch(data["content_sha256"]):
        raise SyncValidationError("mapping content_sha256 is invalid")
    if data["size_bytes"] is not None and (
        not isinstance(data["size_bytes"], int)
        or isinstance(data["size_bytes"], bool)
        or data["size_bytes"] < 0
    ):
        raise SyncValidationError("mapping size_bytes is invalid")
    if not isinstance(data["deleted"], bool) or not isinstance(data["lineage"], list):
        raise SyncValidationError("mapping deleted/lineage fields are invalid")
    if not isinstance(data["updated_at"], str) or not isinstance(
        data["local_path"], (str, type(None))
    ):
        raise SyncValidationError("mapping path/timestamp fields are invalid")
    return data


def _validate_mapping_document(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema_version") != SYNC_SCHEMA_VERSION
        or value.get("kind") != SYNC_MAPPING_KIND
    ):
        raise SyncValidationError("unsupported mapping document")
    if set(value) != {"schema_version", "kind", "revision", "mappings"}:
        raise SyncValidationError("mapping document fields do not match the schema")
    if (
        not isinstance(value["revision"], int)
        or isinstance(value["revision"], bool)
        or value["revision"] < 0
        or not isinstance(value["mappings"], Mapping)
    ):
        raise SyncValidationError("mapping document revision or mappings are invalid")
    result = copy.deepcopy(dict(value))
    result["mappings"] = {}
    for key, item in value["mappings"].items():
        mapping = _validate_mapping(item)
        if key != mapping["logical_path"]:
            raise SyncValidationError("mapping key does not match logical_path")
        result["mappings"][key] = mapping
    return result


def _validate_checkpoint(value: Mapping[str, Any]) -> dict[str, Any]:
    required = set(SYNC_CHECKPOINT_SCHEMA["required"])
    if not isinstance(value, Mapping) or set(value) != required:
        raise SyncValidationError("checkpoint fields do not match the schema")
    data = copy.deepcopy(dict(value))
    if data["schema_version"] != SYNC_SCHEMA_VERSION or data["kind"] != SYNC_CHECKPOINT_KIND:
        raise SyncValidationError("unsupported checkpoint document")
    if data["status"] not in {"running", "success", "partial", "failed"}:
        raise SyncValidationError("invalid checkpoint status")
    _conflict_policy(data["conflict_policy"])
    if not _HEX_DIGEST.fullmatch(data["request_digest"]):
        raise SyncValidationError("invalid checkpoint request digest")
    if not isinstance(data["items"], list):
        raise SyncValidationError("checkpoint items must be an array")
    for item in data["items"]:
        if not isinstance(item, Mapping) or not {"request", "state", "attempts"}.issubset(item):
            raise SyncValidationError("invalid checkpoint item")
        _coerce_item(item["request"])
        if item["state"] not in {"pending", "running", "completed", "failed"}:
            raise SyncValidationError("invalid checkpoint item state")
        if (
            not isinstance(item["attempts"], int)
            or isinstance(item["attempts"], bool)
            or item["attempts"] < 0
        ):
            raise SyncValidationError("invalid checkpoint attempt count")
    return data


def _validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    required = set(SYNC_RECEIPT_SCHEMA["required"])
    if not isinstance(value, Mapping) or set(value) != required:
        raise SyncValidationError("receipt fields do not match the schema")
    data = copy.deepcopy(dict(value))
    if data["schema_version"] != SYNC_SCHEMA_VERSION or data["kind"] != SYNC_RECEIPT_KIND:
        raise SyncValidationError("unsupported reconciliation receipt")
    if data["status"] not in {"success", "partial", "failed"}:
        raise SyncValidationError("invalid receipt status")
    _conflict_policy(data["conflict_policy"])
    if not isinstance(data["entries"], list) or not isinstance(data["errors"], list):
        raise SyncValidationError("receipt entries and errors must be arrays")
    return data


def _empty_mappings() -> dict[str, Any]:
    return {
        "schema_version": SYNC_SCHEMA_VERSION,
        "kind": SYNC_MAPPING_KIND,
        "revision": 0,
        "mappings": {},
    }


def _safe_error(exc: Exception, logical_path: str, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "logical_path": logical_path,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncValidationError(f"cannot read persisted sync state: {path.name}") from exc
    if not isinstance(value, dict):
        raise SyncValidationError("persisted sync state must be a JSON object")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_dir(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_dir(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _stage_bytes(content: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix="ipfs-kit-sync-")
    path = Path(name)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)
    return path


def _chmod_private(path: Path, *, directory: bool = False) -> None:
    try:
        os.chmod(path, 0o700 if directory else 0o600)
    except OSError:
        pass


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _varint(value: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while offset < len(value):
        byte = value[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, offset
        shift += 7
        if shift > 63:
            break
    raise ValueError("invalid varint")


def _base58_decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    for character in value:
        try:
            digit = alphabet.index(character)
        except ValueError:
            raise ValueError("invalid base58") from None
        number = number * 58 + digit
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return b"\x00" * (len(value) - len(value.lstrip("1"))) + decoded


IPFSIrohSyncAdapter = IrohIPFSSyncAdapter
IrohSyncAdapter = IrohIPFSSyncAdapter
SyncMappingStore = SyncStateStore
ReconciliationReceipt = SyncReconciliationReceipt

__all__ = [
    "SYNC_SCHEMA_VERSION",
    "SYNC_MAPPING_KIND",
    "SYNC_CHECKPOINT_KIND",
    "SYNC_RECEIPT_KIND",
    "SYNC_MAPPING_SCHEMA",
    "SYNC_CHECKPOINT_SCHEMA",
    "SYNC_RECEIPT_SCHEMA",
    "ConflictPolicy",
    "SyncItem",
    "SyncError",
    "SyncValidationError",
    "SyncConflictError",
    "SyncIntegrityError",
    "SyncCheckpointError",
    "SyncStateStore",
    "SyncMappingStore",
    "CARStager",
    "IrohIPFSSyncAdapter",
    "IPFSIrohSyncAdapter",
    "IrohSyncAdapter",
    "SyncReconciliationReceipt",
    "ReconciliationReceipt",
    "validate_cid",
    "verify_cid",
]

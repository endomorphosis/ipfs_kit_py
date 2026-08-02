"""Virtual-bucket policy and reconciliation for named storage backends.

This module is the policy boundary between virtual buckets and the canonical
named-backend/VFS layer.  It deliberately stores only content identifiers,
sizes, placement state, and audit receipts; payload bytes and credentials
remain owned by backend adapters.  Durable state uses DuckDB, matching the
Iroh storage contract.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Any

import duckdb
from blake3 import blake3

from ..backend_registry import BackendConfigError, ensure_json_compatible, validate_backend_name
from .errors import IrohConflictError, IrohIntegrityError


BUCKET_POLICY_SCHEMA_VERSION = 1
TIER_POLICY_SCHEMA_VERSION = 1
RECONCILIATION_RECEIPT_SCHEMA_VERSION = 1
RECONCILIATION_RECEIPT_KIND = "ipfs-kit-iroh-bucket-reconciliation-receipt"

_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_HASH_RE = re.compile(r"^[a-f0-9]{64}$")


class BindingRole(str, Enum):
    """The responsibility assigned to a backend within one bucket."""

    PRIMARY = "primary"
    REPLICA = "replica"
    CACHE = "cache"
    ARCHIVE = "archive"


class StorageTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"


_DEFAULT_TIER = {
    BindingRole.PRIMARY: StorageTier.HOT,
    BindingRole.REPLICA: StorageTier.WARM,
    BindingRole.CACHE: StorageTier.HOT,
    BindingRole.ARCHIVE: StorageTier.ARCHIVE,
}


def _uint(value: Any, label: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BackendConfigError(f"{label} must be a non-negative integer")
    return value


def _positive_uint(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise BackendConfigError(f"{label} must be a positive integer")
    return value


def _only(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise BackendConfigError(
            f"{label} contains unknown settings: "
            + ", ".join(repr(item) for item in sorted(unknown))
        )


def _bucket_name(value: Any) -> str:
    if not isinstance(value, str) or not _BUCKET_RE.fullmatch(value):
        raise BackendConfigError(
            "bucket must be 1-128 lowercase letters, digits, dots, underscores, or hyphens"
        )
    return value


def _content_hash(value: Any) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise BackendConfigError("iroh_hash must be a lowercase 32-byte hexadecimal BLAKE3 hash")
    return value


@dataclass(frozen=True, slots=True)
class BackendBinding:
    """One named-backend binding and its placement role."""

    backend: str
    role: BindingRole
    tier: StorageTier | None = None
    priority: int = 100
    enabled: bool = True
    quota_bytes: int | None = None
    minimum_free_bytes: int = 0
    prefix: str = ""

    def __post_init__(self) -> None:
        validate_backend_name(self.backend)
        if not isinstance(self.role, BindingRole):
            object.__setattr__(self, "role", BindingRole(self.role))
        if self.tier is None:
            object.__setattr__(self, "tier", _DEFAULT_TIER[self.role])
        elif not isinstance(self.tier, StorageTier):
            object.__setattr__(self, "tier", StorageTier(self.tier))
        _uint(self.priority, "binding.priority")
        if not isinstance(self.enabled, bool):
            raise BackendConfigError("binding.enabled must be a boolean")
        _uint(self.quota_bytes, "binding.quota_bytes", allow_none=True)
        _uint(self.minimum_free_bytes, "binding.minimum_free_bytes")
        if not isinstance(self.prefix, str) or self.prefix.startswith("/") or ".." in self.prefix.split("/"):
            raise BackendConfigError("binding.prefix must be a safe relative POSIX path")

    @property
    def storage_tier(self) -> StorageTier:
        """Return the normalized tier after dataclass validation."""

        assert self.tier is not None
        return self.tier

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BackendBinding":
        item = ensure_json_compatible(value, "binding")
        _only(
            item,
            {"backend", "role", "tier", "priority", "enabled", "quota_bytes", "minimum_free_bytes", "prefix"},
            "binding",
        )
        if "backend" not in item or "role" not in item:
            raise BackendConfigError("binding requires backend and role")
        try:
            role = BindingRole(item["role"])
            tier = StorageTier(item.get("tier", _DEFAULT_TIER[role].value))
        except (TypeError, ValueError) as exc:
            raise BackendConfigError("binding role or tier is invalid") from exc
        return cls(
            item["backend"], role, tier, item.get("priority", 100),
            item.get("enabled", True), item.get("quota_bytes"),
            item.get("minimum_free_bytes", 0), item.get("prefix", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "role": self.role.value,
            "tier": self.storage_tier.value,
            "priority": self.priority,
            "enabled": self.enabled,
            "quota_bytes": self.quota_bytes,
            "minimum_free_bytes": self.minimum_free_bytes,
            "prefix": self.prefix,
        }


# Compatibility spelling used in policy documents and early integrations.
BucketBinding = BackendBinding


@dataclass(frozen=True, slots=True)
class TierPolicy:
    """Placement and lifecycle rules shared by all objects in a bucket."""

    replication_factor: int = 1
    read_order: tuple[BindingRole, ...] = (
        BindingRole.CACHE,
        BindingRole.PRIMARY,
        BindingRole.REPLICA,
        BindingRole.ARCHIVE,
    )
    cache_on_read: bool = False
    cache_ttl_seconds: int | None = None
    archive_after_seconds: int | None = None
    schema_version: int = TIER_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != TIER_POLICY_SCHEMA_VERSION or isinstance(self.schema_version, bool):
            raise BackendConfigError("tier policy schema_version must be 1")
        _positive_uint(self.replication_factor, "tier_policy.replication_factor")
        roles: list[BindingRole] = []
        try:
            for role in self.read_order:
                roles.append(role if isinstance(role, BindingRole) else BindingRole(role))
        except (TypeError, ValueError) as exc:
            raise BackendConfigError("tier_policy.read_order contains an invalid role") from exc
        if len(roles) != len(set(roles)) or set(roles) != set(BindingRole):
            raise BackendConfigError("tier_policy.read_order must contain every binding role exactly once")
        object.__setattr__(self, "read_order", tuple(roles))
        if not isinstance(self.cache_on_read, bool):
            raise BackendConfigError("tier_policy.cache_on_read must be a boolean")
        _uint(self.cache_ttl_seconds, "tier_policy.cache_ttl_seconds", allow_none=True)
        _uint(self.archive_after_seconds, "tier_policy.archive_after_seconds", allow_none=True)
        if self.cache_on_read and self.cache_ttl_seconds == 0:
            raise BackendConfigError("cache_on_read requires a positive or unlimited cache TTL")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "TierPolicy":
        item = ensure_json_compatible(value or {}, "tier_policy")
        _only(
            item,
            {"schema_version", "replication_factor", "read_order", "cache_on_read", "cache_ttl_seconds", "archive_after_seconds"},
            "tier_policy",
        )
        return cls(
            replication_factor=item.get("replication_factor", 1),
            read_order=tuple(item.get("read_order", [role.value for role in cls().read_order])),
            cache_on_read=item.get("cache_on_read", False),
            cache_ttl_seconds=item.get("cache_ttl_seconds"),
            archive_after_seconds=item.get("archive_after_seconds"),
            schema_version=item.get("schema_version", TIER_POLICY_SCHEMA_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "replication_factor": self.replication_factor,
            "read_order": [item.value for item in self.read_order],
            "cache_on_read": self.cache_on_read,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "archive_after_seconds": self.archive_after_seconds,
        }


@dataclass(frozen=True, slots=True)
class BucketPolicy:
    """Versioned policy for one virtual bucket."""

    bucket: str
    bindings: tuple[BackendBinding, ...]
    tier_policy: TierPolicy = field(default_factory=TierPolicy)
    quota_bytes: int | None = None
    schema_version: int = BUCKET_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bucket_name(self.bucket)
        if self.schema_version != BUCKET_POLICY_SCHEMA_VERSION or isinstance(self.schema_version, bool):
            raise BackendConfigError("bucket policy schema_version must be 1")
        bindings = tuple(
            item if isinstance(item, BackendBinding) else BackendBinding.from_dict(item)
            for item in self.bindings
        )
        object.__setattr__(self, "bindings", bindings)
        if not isinstance(self.tier_policy, TierPolicy):
            object.__setattr__(self, "tier_policy", TierPolicy.from_dict(self.tier_policy))
        _uint(self.quota_bytes, "quota_bytes", allow_none=True)
        enabled = [item for item in bindings if item.enabled]
        primaries = [item for item in enabled if item.role is BindingRole.PRIMARY]
        if len(primaries) != 1:
            raise BackendConfigError("bucket policy requires exactly one enabled primary binding")
        names = [item.backend for item in bindings]
        if len(names) != len(set(names)):
            raise BackendConfigError("a backend may be bound to a bucket only once")
        durable = sum(item.role in {BindingRole.PRIMARY, BindingRole.REPLICA} for item in enabled)
        if self.tier_policy.replication_factor > durable:
            raise BackendConfigError("replication_factor exceeds enabled primary and replica bindings")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BucketPolicy":
        item = ensure_json_compatible(value, "bucket_policy")
        _only(item, {"schema_version", "bucket", "bindings", "tier_policy", "quota_bytes"}, "bucket policy")
        required = {"schema_version", "bucket", "bindings", "tier_policy"}
        if not required.issubset(item):
            raise BackendConfigError("bucket policy is missing required settings")
        if not isinstance(item["bindings"], list):
            raise BackendConfigError("bindings must be an array")
        return cls(
            item["bucket"],
            tuple(BackendBinding.from_dict(binding) for binding in item["bindings"]),
            TierPolicy.from_dict(item["tier_policy"]),
            item.get("quota_bytes"),
            item["schema_version"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bucket": self.bucket,
            "quota_bytes": self.quota_bytes,
            "bindings": [item.to_dict() for item in self.bindings],
            "tier_policy": self.tier_policy.to_dict(),
        }

    @property
    def policy_digest(self) -> str:
        return blake3(_canonical_json(self.to_dict())).hexdigest()

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]


def validate_tier_policy(value: Mapping[str, Any] | TierPolicy) -> dict[str, Any]:
    policy = value if isinstance(value, TierPolicy) else TierPolicy.from_dict(value)
    return policy.to_dict()


def validate_bucket_policy(value: Mapping[str, Any] | BucketPolicy) -> dict[str, Any]:
    policy = value if isinstance(value, BucketPolicy) else BucketPolicy.from_dict(value)
    return policy.to_dict()


def migrate_bucket_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate supported legacy bucket bindings to schema version 1.

    Legacy configurations used a single ``backend`` plus optional replication,
    cache, and archive fields.  Migration is deterministic and never resolves
    backend credentials.
    """

    source = ensure_json_compatible(value, "bucket_policy")
    version = source.get("schema_version")
    if version == BUCKET_POLICY_SCHEMA_VERSION and not isinstance(version, bool):
        return validate_bucket_policy(source)
    if version not in (None, 0) or isinstance(version, bool):
        raise BackendConfigError(f"unsupported bucket policy schema_version: {version!r}")

    allowed = {
        "schema_version", "name", "bucket", "backend", "primary_backend",
        "replication_targets", "replicas", "cache_backend", "archive_backend",
        "bindings", "quota", "quota_bytes", "max_size", "tier_policy",
        "replication_factor", "cache_policy", "retention_days",
    }
    _only(source, allowed, "legacy bucket policy")
    bucket = source.get("bucket", source.get("name"))
    _bucket_name(bucket)
    bindings: list[dict[str, Any]] = []

    if source.get("bindings") is not None:
        if not isinstance(source["bindings"], list):
            raise BackendConfigError("legacy bindings must be an array")
        for index, raw in enumerate(source["bindings"]):
            if isinstance(raw, str):
                role = "primary" if index == 0 else "replica"
                bindings.append({"backend": raw, "role": role})
            elif isinstance(raw, Mapping):
                item = dict(raw)
                item.setdefault("role", "primary" if index == 0 else "replica")
                bindings.append(item)
            else:
                raise BackendConfigError("legacy binding must be a backend name or object")
    else:
        primary = source.get("primary_backend", source.get("backend"))
        if not primary:
            raise BackendConfigError("legacy bucket policy requires backend or primary_backend")
        bindings.append({"backend": primary, "role": "primary"})

    replicas = source.get("replication_targets", source.get("replicas", [])) or []
    if isinstance(replicas, str):
        replicas = [replicas]
    if not isinstance(replicas, list):
        raise BackendConfigError("replication_targets must be an array")
    for raw in replicas:
        item = {"backend": raw, "role": "replica"} if isinstance(raw, str) else dict(raw)
        item.setdefault("role", "replica")
        bindings.append(item)
    for backend_field, role in (("cache_backend", "cache"), ("archive_backend", "archive")):
        if source.get(backend_field):
            bindings.append({"backend": source[backend_field], "role": role})

    normalized_bindings = [BackendBinding.from_dict(item).to_dict() for item in bindings]
    durable_count = sum(item["role"] in {"primary", "replica"} and item["enabled"] for item in normalized_bindings)
    tier_source = dict(source.get("tier_policy") or {})
    tier_source.setdefault("schema_version", 1)
    tier_source.setdefault("replication_factor", source.get("replication_factor", durable_count))
    cache_policy = source.get("cache_policy")
    if cache_policy not in (None, "none"):
        tier_source.setdefault("cache_on_read", True)
    if source.get("retention_days") not in (None, 0):
        tier_source.setdefault("archive_after_seconds", int(source["retention_days"]) * 86400)

    quota = source.get("quota_bytes", source.get("max_size"))
    if quota is None and isinstance(source.get("quota"), Mapping):
        quota = source["quota"].get("max_size", source["quota"].get("max_bytes"))
    migrated = {
        "schema_version": 1,
        "bucket": bucket,
        "quota_bytes": quota,
        "bindings": normalized_bindings,
        "tier_policy": TierPolicy.from_dict(tier_source).to_dict(),
    }
    return validate_bucket_policy(migrated)


def bucket_policy_schema() -> dict[str, Any]:
    return _load_schema("iroh-bucket-policy.schema.json")


def tier_policy_schema() -> dict[str, Any]:
    return _load_schema("iroh-tier-policy.schema.json")


def reconciliation_receipt_schema() -> dict[str, Any]:
    return _load_schema("iroh-bucket-reconciliation-receipt.schema.json")


def _load_schema(name: str) -> dict[str, Any]:
    resource = files("ipfs_kit_py.resources").joinpath(name)
    return json.loads(resource.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class CapacityReport:
    backend: str
    backend_type: str
    used_bytes: int
    capacity_bytes: int | None
    placement_bytes: int
    binding_quota_bytes: int | None
    minimum_free_bytes: int
    available_bytes: int | None
    healthy: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "backend_type": self.backend_type,
            "used_bytes": self.used_bytes,
            "capacity_bytes": self.capacity_bytes,
            "placement_bytes": self.placement_bytes,
            "binding_quota_bytes": self.binding_quota_bytes,
            "minimum_free_bytes": self.minimum_free_bytes,
            "available_bytes": self.available_bytes,
            "healthy": self.healthy,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationAction:
    action: str
    iroh_hash: str
    size: int
    backend: str | None
    role: str | None
    tier: str | None
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "iroh_hash": self.iroh_hash,
            "size": self.size,
            "backend": self.backend,
            "role": self.role,
            "tier": self.tier,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationReceipt:
    receipt_id: str
    bucket: str
    operation: str
    status: str
    policy_digest: str
    started_at: str
    completed_at: str
    dry_run: bool
    actions: tuple[ReconciliationAction, ...]
    logical_bytes_before: int
    logical_bytes_after: int
    quota_bytes: int | None
    duplicate_objects: int = 0
    duplicate_bytes: int = 0
    kind: str = RECONCILIATION_RECEIPT_KIND
    schema_version: int = RECONCILIATION_RECEIPT_SCHEMA_VERSION

    @property
    def success(self) -> bool:
        return self.status in {"converged", "dry-run"}

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "receipt_id": self.receipt_id,
            "bucket": self.bucket,
            "operation": self.operation,
            "status": self.status,
            "policy_digest": self.policy_digest,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "dry_run": self.dry_run,
            "logical_bytes_before": self.logical_bytes_before,
            "logical_bytes_after": self.logical_bytes_after,
            "quota_bytes": self.quota_bytes,
            "duplicate_objects": self.duplicate_objects,
            "duplicate_bytes": self.duplicate_bytes,
            "action_count": len(self.actions),
            "actions": [item.to_dict() for item in self.actions],
        }
        if include_digest:
            document["receipt_digest"] = blake3(_canonical_json(document)).hexdigest()
        return document

    @property
    def receipt_digest(self) -> str:
        return self.to_dict()["receipt_digest"]

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    def to_json(self) -> str:
        return self.canonical_bytes().decode("utf-8")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReconciliationReceipt":
        if not isinstance(value, Mapping):
            raise IrohIntegrityError("reconciliation receipt must be an object", operation="bucket.receipt")
        raw = ensure_json_compatible(value, "receipt")
        digest = raw.pop("receipt_digest", None)
        if not isinstance(digest, str) or digest != blake3(_canonical_json(raw)).hexdigest():
            raise IrohIntegrityError("reconciliation receipt digest is invalid", operation="bucket.receipt")
        try:
            if raw["schema_version"] != 1 or raw["kind"] != RECONCILIATION_RECEIPT_KIND:
                raise ValueError("unsupported receipt version")
            actions = tuple(ReconciliationAction(**item) for item in raw["actions"])
            if raw["action_count"] != len(actions):
                raise ValueError("action count mismatch")
            receipt = cls(
                raw["receipt_id"], raw["bucket"], raw["operation"], raw["status"],
                raw["policy_digest"], raw["started_at"], raw["completed_at"],
                raw["dry_run"], actions, raw["logical_bytes_before"],
                raw["logical_bytes_after"], raw["quota_bytes"],
                raw["duplicate_objects"], raw["duplicate_bytes"], raw["kind"],
                raw["schema_version"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IrohIntegrityError("reconciliation receipt is malformed", operation="bucket.receipt") from exc
        if receipt.to_dict() != value:
            raise IrohIntegrityError("reconciliation receipt fields are inconsistent", operation="bucket.receipt")
        return receipt

    def write(self, destination: str | os.PathLike[str]) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            data = self.canonical_bytes()
            view = memoryview(data)
            while view:
                count = os.write(descriptor, view)
                if count <= 0:
                    raise OSError("short receipt write")
                view = view[count:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, target)
            os.chmod(target, 0o600)
            return target
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    save = write


def verify_reconciliation_receipt(value: Any) -> ReconciliationReceipt:
    if isinstance(value, os.PathLike):
        value = Path(value).read_text(encoding="utf-8")
    elif isinstance(value, str) and not value.lstrip().startswith(("{", "[")):
        try:
            candidate = Path(value)
            if candidate.is_file():
                value = candidate.read_text(encoding="utf-8")
        except OSError:
            # It is a JSON string (or malformed input), not a viable path.
            pass
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeError as exc:
            raise IrohIntegrityError("reconciliation receipt is not UTF-8", operation="bucket.receipt") from exc
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise IrohIntegrityError("reconciliation receipt is invalid JSON", operation="bucket.receipt") from exc
    return ReconciliationReceipt.from_dict(value)


class IrohBucketTieringManager:
    """Durable role-aware placement and reconciliation for virtual buckets."""

    def __init__(
        self,
        backend_manager: Any,
        state_path: str | os.PathLike[str] | None = None,
        *,
        db_path: str | os.PathLike[str] | None = None,
        capacity_provider: Callable[[str], Mapping[str, Any]] | Mapping[str, Mapping[str, Any]] | None = None,
        placement_handler: Callable[[Mapping[str, Any], Mapping[str, Any]], Any] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.backend_manager = backend_manager
        self.capacity_provider = capacity_provider
        self.placement_handler = placement_handler
        self.clock = clock
        self._lock = threading.RLock()
        self.last_receipt: ReconciliationReceipt | None = None
        if state_path is not None and db_path is not None:
            raise ValueError("state_path and db_path are aliases; provide only one")
        state_path = state_path if state_path is not None else db_path
        target: Path | None = None
        if state_path is None:
            database = ":memory:"
        else:
            target = Path(state_path)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            database = str(target)
        self._db = duckdb.connect(database)
        if target is not None:
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass
        self._create_schema()

    def _create_schema(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS bucket_policies (
                bucket VARCHAR PRIMARY KEY, policy_json VARCHAR NOT NULL,
                policy_digest VARCHAR NOT NULL, updated_at DOUBLE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bucket_content (
                bucket VARCHAR NOT NULL, iroh_hash VARCHAR NOT NULL, size UBIGINT NOT NULL,
                metadata_json VARCHAR NOT NULL, created_at DOUBLE NOT NULL,
                PRIMARY KEY(bucket, iroh_hash)
            );
            CREATE TABLE IF NOT EXISTS bucket_placements (
                bucket VARCHAR NOT NULL, iroh_hash VARCHAR NOT NULL, backend VARCHAR NOT NULL,
                role VARCHAR NOT NULL, tier VARCHAR NOT NULL, size UBIGINT NOT NULL,
                status VARCHAR NOT NULL, updated_at DOUBLE NOT NULL,
                PRIMARY KEY(bucket, iroh_hash, backend)
            );
            CREATE TABLE IF NOT EXISTS bucket_receipts (
                receipt_id VARCHAR PRIMARY KEY, bucket VARCHAR NOT NULL,
                operation VARCHAR NOT NULL, status VARCHAR NOT NULL,
                receipt_json VARCHAR NOT NULL, created_at DOUBLE NOT NULL
            );
            -- An action is recorded *before* an external placement handler is
            -- called.  Thus a process death between the handler and catalog
            -- commit is recoverable rather than silently divergent.
            CREATE TABLE IF NOT EXISTS bucket_placement_sagas (
                saga_id VARCHAR PRIMARY KEY, bucket VARCHAR NOT NULL,
                action_json VARCHAR NOT NULL, content_json VARCHAR NOT NULL,
                inverse_json VARCHAR NOT NULL, state VARCHAR NOT NULL,
                error VARCHAR, created_at DOUBLE NOT NULL, updated_at DOUBLE NOT NULL
            )
        """)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> "IrohBucketTieringManager":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _validate_binding_backend(self, binding: BackendBinding) -> None:
        try:
            config = self.backend_manager.get_backend_config(binding.backend, redact=False)
        except TypeError:
            config = self.backend_manager.get_backend_config(binding.backend)
        if not isinstance(config, Mapping):
            raise BackendConfigError(f"backend {binding.backend!r} did not return a configuration")
        if config.get("enabled") is False:
            raise BackendConfigError(f"backend {binding.backend!r} is disabled")
        capabilities = self.backend_manager.get_backend_capabilities(binding.backend)
        if not isinstance(capabilities, Mapping):
            raise BackendConfigError(f"backend {binding.backend!r} did not report capabilities")
        if capabilities.get("write") is False:
            raise BackendConfigError(
                f"backend {binding.backend!r} is read-only and cannot be a {binding.role.value} target"
            )

    def _validate_backends(self, policy: BucketPolicy) -> None:
        for binding in policy.bindings:
            if binding.enabled:
                self._validate_binding_backend(binding)

    def create_bucket(
        self,
        bucket: str | BucketPolicy | Mapping[str, Any],
        *,
        bindings: Sequence[BackendBinding | Mapping[str, Any]] | None = None,
        primary: str | None = None,
        primary_backend: str | None = None,
        replicas: Sequence[str] = (),
        replication_targets: Sequence[str] = (),
        cache: str | None = None,
        archive: str | None = None,
        quota_bytes: int | None = None,
        tier_policy: TierPolicy | Mapping[str, Any] | None = None,
    ) -> BucketPolicy:
        if isinstance(bucket, BucketPolicy):
            policy = bucket
        elif isinstance(bucket, Mapping):
            raw = dict(bucket)
            policy = BucketPolicy.from_dict(raw) if raw.get("schema_version") == 1 else BucketPolicy.from_dict(migrate_bucket_policy(raw))
        else:
            generated: list[BackendBinding | Mapping[str, Any]] = list(bindings or ())
            selected_primary = primary_backend or primary
            if not generated:
                if not selected_primary:
                    raise BackendConfigError("create_bucket requires a primary backend or bindings")
                generated.append({"backend": selected_primary, "role": "primary"})
                generated.extend({"backend": item, "role": "replica"} for item in (*replicas, *replication_targets))
                if cache:
                    generated.append({"backend": cache, "role": "cache"})
                if archive:
                    generated.append({"backend": archive, "role": "archive"})
            normalized = tuple(item if isinstance(item, BackendBinding) else BackendBinding.from_dict(item) for item in generated)
            durable = sum(item.enabled and item.role in {BindingRole.PRIMARY, BindingRole.REPLICA} for item in normalized)
            selected_tier = tier_policy if isinstance(tier_policy, TierPolicy) else TierPolicy.from_dict(tier_policy)
            if tier_policy is None:
                selected_tier = replace(selected_tier, replication_factor=durable)
            policy = BucketPolicy(bucket, normalized, selected_tier, quota_bytes)
        self._validate_backends(policy)
        with self._lock:
            if self._db.execute("SELECT 1 FROM bucket_policies WHERE bucket=?", (policy.bucket,)).fetchone():
                raise IrohConflictError("bucket already exists", operation="bucket.create", metadata={"bucket": policy.bucket})
            self._persist_policy(policy)
        return policy

    create_virtual_bucket = create_bucket

    def _persist_policy(self, policy: BucketPolicy) -> None:
        self._db.execute(
            """INSERT INTO bucket_policies VALUES(?,?,?,?)
               ON CONFLICT(bucket) DO UPDATE SET policy_json=excluded.policy_json,
               policy_digest=excluded.policy_digest,updated_at=excluded.updated_at""",
            (policy.bucket, _canonical_json(policy.to_dict()).decode(), policy.policy_digest, self.clock()),
        )

    def _external_action(self, bucket: str, action: ReconciliationAction, content: Mapping[str, Any], sagas: list[str]) -> ReconciliationAction:
        """Apply a handler action with a durable inverse prepared first."""
        if self.placement_handler is None:
            return action
        inverse_kind = "remove" if action.action == "place" else "place"
        inverse = replace(action, action=inverse_kind, status="planned", reason="saga_compensation")
        saga_id = uuid.uuid4().hex
        now = self.clock()
        with self._lock:
            self._db.execute(
                "INSERT INTO bucket_placement_sagas VALUES(?,?,?,?,?,?,?,?,?)",
                (saga_id, bucket, _canonical_json(action.to_dict()).decode(),
                 _canonical_json(dict(content)).decode(), _canonical_json(inverse.to_dict()).decode(),
                 "prepared", None, now, now),
            )
        sagas.append(saga_id)
        try:
            outcome = self.placement_handler(action.to_dict(), copy.deepcopy(dict(content)))
            if outcome is False or (isinstance(outcome, Mapping) and outcome.get("success") is False):
                raise RuntimeError("placement_handler_failed")
        except Exception as exc:
            with self._lock:
                self._db.execute("UPDATE bucket_placement_sagas SET state='compensation_pending',error=?,updated_at=? WHERE saga_id=?", (str(exc), self.clock(), saga_id))
            return replace(action, status="failed", reason="placement_handler_failed" if str(exc) == "placement_handler_failed" else "placement_handler_error")
        with self._lock:
            self._db.execute("UPDATE bucket_placement_sagas SET state='applied',updated_at=? WHERE saga_id=?", (self.clock(), saga_id))
        return action

    def recover_pending_compensations(self, saga_ids: Sequence[str] | None = None) -> tuple[str, ...]:
        """Retry inverses for actions whose catalog transaction never committed."""
        if self.placement_handler is None:
            return ()
        clause = "state IN ('prepared','applied','compensation_pending')"
        params: tuple[Any, ...] = ()
        if saga_ids is not None:
            if not saga_ids:
                return ()
            marks = ",".join("?" for _ in saga_ids)
            clause += f" AND saga_id IN ({marks})"
            params = tuple(saga_ids)
        with self._lock:
            rows = self._db.execute(
                f"SELECT saga_id,inverse_json,content_json FROM bucket_placement_sagas WHERE {clause} ORDER BY created_at",
                params,
            ).fetchall()
        recovered: list[str] = []
        for saga_id, inverse_raw, content_raw in rows:
            try:
                outcome = self.placement_handler(json.loads(inverse_raw), json.loads(content_raw))
                if outcome is False or (isinstance(outcome, Mapping) and outcome.get("success") is False):
                    raise RuntimeError("compensation_handler_failed")
                with self._lock:
                    self._db.execute("UPDATE bucket_placement_sagas SET state='compensated',updated_at=? WHERE saga_id=?", (self.clock(), saga_id))
                recovered.append(saga_id)
            except Exception as exc:
                with self._lock:
                    self._db.execute("UPDATE bucket_placement_sagas SET state='recovery_required',error=?,updated_at=? WHERE saga_id=?", (str(exc), self.clock(), saga_id))
        return tuple(recovered)

    def _compensate_sagas(self, saga_ids: Sequence[str]) -> bool:
        if not saga_ids:
            return True
        self.recover_pending_compensations(saga_ids)
        marks = ",".join("?" for _ in saga_ids)
        with self._lock:
            row = self._db.execute(f"SELECT count(*) FROM bucket_placement_sagas WHERE saga_id IN ({marks}) AND state <> 'compensated'", tuple(saga_ids)).fetchone()
        return int(row[0]) == 0

    def get_policy(self, bucket: str) -> BucketPolicy:
        _bucket_name(bucket)
        with self._lock:
            row = self._db.execute("SELECT policy_json FROM bucket_policies WHERE bucket=?", (bucket,)).fetchone()
        if row is None:
            raise KeyError(bucket)
        raw = json.loads(row[0])
        return BucketPolicy.from_dict(raw) if raw.get("schema_version") == 1 else BucketPolicy.from_dict(migrate_bucket_policy(raw))

    def list_buckets(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(row[0] for row in self._db.execute("SELECT bucket FROM bucket_policies ORDER BY bucket").fetchall())

    def update_policy(self, bucket: str, value: BucketPolicy | Mapping[str, Any]) -> ReconciliationReceipt:
        old = self.get_policy(bucket)
        if isinstance(value, BucketPolicy):
            policy = value
        else:
            raw = dict(value)
            raw.setdefault("bucket", bucket)
            policy = BucketPolicy.from_dict(raw) if raw.get("schema_version") == 1 else BucketPolicy.from_dict(migrate_bucket_policy(raw))
        if policy.bucket != bucket:
            raise BackendConfigError("updated policy bucket does not match the existing bucket")
        self._validate_backends(policy)
        with self._lock:
            self._persist_policy(policy)
        receipt = self.reconcile(bucket, operation="policy_migration", previous_policy=old)
        if not receipt.success:
            # Desired state is authoritative: never leave a rejected candidate
            # published.  Reconciliation has already compensated its external
            # work; a second pass makes the old desired state explicit.
            with self._lock:
                self._persist_policy(old)
            rollback = self.reconcile(bucket, operation="policy_rollback", previous_policy=policy)
            if not rollback.success:
                receipt = replace(receipt, status="recovery_required", operation="policy_migration_recovery_required")
        return receipt

    def migrate_policy(
        self,
        bucket: str | Mapping[str, Any],
        value: BucketPolicy | Mapping[str, Any] | None = None,
    ) -> ReconciliationReceipt:
        """Migrate and apply a legacy policy, accepting both common call forms."""

        if isinstance(bucket, Mapping):
            if value is not None:
                raise TypeError("value must be omitted when the first argument is a policy")
            source = bucket
            name = source.get("bucket", source.get("name"))
            _bucket_name(name)
            return self.update_policy(name, source)
        if value is None:
            raise TypeError("migrate_policy(bucket, value) requires a policy value")
        return self.update_policy(bucket, value)

    def logical_usage(self, bucket: str) -> int:
        self.get_policy(bucket)
        with self._lock:
            row = self._db.execute("SELECT COALESCE(SUM(size),0) FROM bucket_content WHERE bucket=?", (bucket,)).fetchone()
        return int(row[0])

    def _binding_usage(self, backend: str) -> int:
        with self._lock:
            row = self._db.execute(
                """SELECT COALESCE(SUM(size),0) FROM (
                       SELECT MAX(size) AS size FROM bucket_placements
                       WHERE backend=? AND status='placed' GROUP BY iroh_hash
                   ) AS unique_backend_content""",
                (backend,),
            ).fetchone()
        return int(row[0])

    def _backend_has_content(self, backend: str, iroh_hash: str) -> bool:
        with self._lock:
            return bool(self._db.execute(
                "SELECT 1 FROM bucket_placements WHERE backend=? AND iroh_hash=? AND status='placed' LIMIT 1",
                (backend, iroh_hash),
            ).fetchone())

    def _raw_capacity(self, backend: str) -> Mapping[str, Any]:
        provider = self.capacity_provider
        if callable(provider):
            result = provider(backend)
        elif isinstance(provider, Mapping):
            result = provider.get(backend, {})
        else:
            result = self.backend_manager.get_backend_health(backend)
        return result if isinstance(result, Mapping) else {}

    def capacity_report(self, bucket: str | None = None, backend: str | None = None) -> dict[str, Any]:
        policies = [self.get_policy(bucket)] if bucket else [self.get_policy(item) for item in self.list_buckets()]
        selected: dict[str, BackendBinding] = {}
        for policy in policies:
            for binding in policy.bindings:
                if binding.enabled and (backend is None or backend == binding.backend):
                    previous = selected.get(binding.backend)
                    if previous is None or binding.minimum_free_bytes > previous.minimum_free_bytes:
                        selected[binding.backend] = binding
        reports: list[CapacityReport] = []
        for name, binding in sorted(selected.items()):
            raw = self._raw_capacity(name)
            storage = raw.get("storage", raw)
            if not isinstance(storage, Mapping):
                storage = {}
            used = storage.get("used_bytes", raw.get("used_bytes", 0))
            capacity = storage.get("capacity_bytes", storage.get("limit_bytes", raw.get("capacity_bytes")))
            used = int(used) if isinstance(used, (int, float)) and not isinstance(used, bool) and used >= 0 else 0
            capacity = int(capacity) if isinstance(capacity, (int, float)) and not isinstance(capacity, bool) and capacity >= 0 else None
            placement = self._binding_usage(name)
            available_candidates: list[int] = []
            if capacity is not None:
                available_candidates.append(max(0, capacity - used - binding.minimum_free_bytes))
            if binding.quota_bytes is not None:
                available_candidates.append(max(0, binding.quota_bytes - placement))
            available = min(available_candidates) if available_candidates else None
            try:
                config = self.backend_manager.get_backend_config(name, redact=True)
            except TypeError:
                config = self.backend_manager.get_backend_config(name)
            reports.append(CapacityReport(
                name, str(config.get("type", "unknown")), used, capacity, placement,
                binding.quota_bytes, binding.minimum_free_bytes, available,
                raw.get("healthy") if isinstance(raw.get("healthy"), bool) else None,
            ))
        return {
            "bucket": bucket,
            "logical_usage_bytes": self.logical_usage(bucket) if bucket else sum(self.logical_usage(item) for item in self.list_buckets()),
            "backends": [item.to_dict() for item in reports],
        }

    report_capacity = capacity_report
    get_capacity_report = capacity_report

    @staticmethod
    def _desired_bindings(policy: BucketPolicy) -> tuple[BackendBinding, ...]:
        enabled = sorted((item for item in policy.bindings if item.enabled), key=lambda item: (item.priority, item.backend))
        primary = [item for item in enabled if item.role is BindingRole.PRIMARY]
        replicas = [item for item in enabled if item.role is BindingRole.REPLICA]
        durable = primary + replicas[: max(0, policy.tier_policy.replication_factor - 1)]
        ancillary = [item for item in enabled if item.role in {BindingRole.CACHE, BindingRole.ARCHIVE}]
        return tuple(durable + ancillary)

    def select_placement(self, bucket: str, size: int, *, iroh_hash: str | None = None) -> tuple[BackendBinding, ...]:
        policy = self.get_policy(bucket)
        size = _uint(size, "size")  # type: ignore[assignment]
        duplicate = False
        if iroh_hash is not None:
            _content_hash(iroh_hash)
            with self._lock:
                row = self._db.execute("SELECT size FROM bucket_content WHERE bucket=? AND iroh_hash=?", (bucket, iroh_hash)).fetchone()
            if row is not None:
                if int(row[0]) != size:
                    raise IrohIntegrityError("an existing Iroh hash has a different size", operation="bucket.place")
                duplicate = True
        usage = self.logical_usage(bucket)
        if policy.quota_bytes is not None and usage + (0 if duplicate else size) > policy.quota_bytes:
            raise IrohConflictError(
                "virtual bucket quota would be exceeded", operation="bucket.place",
                metadata={"bucket": bucket, "usage_bytes": usage, "quota_bytes": policy.quota_bytes, "additional_bytes": 0 if duplicate else size},
            )
        selected = self._desired_bindings(policy)
        reports = {item["backend"]: item for item in self.capacity_report(bucket)["backends"]}
        for binding in selected:
            with self._lock:
                exists = bool(iroh_hash and self._db.execute(
                    "SELECT 1 FROM bucket_placements WHERE bucket=? AND iroh_hash=? AND backend=? AND status='placed'",
                    (bucket, iroh_hash, binding.backend),
                ).fetchone())
            available = reports.get(binding.backend, {}).get("available_bytes")
            if reports.get(binding.backend, {}).get("healthy") is False:
                raise IrohConflictError(
                    "backend is unhealthy", operation="bucket.place",
                    metadata={"bucket": bucket, "backend": binding.backend},
                )
            backend_duplicate = bool(iroh_hash and self._backend_has_content(binding.backend, iroh_hash))
            if not exists and not backend_duplicate and available is not None and size > available:
                raise IrohConflictError(
                    "backend capacity would be exceeded", operation="bucket.place",
                    metadata={"bucket": bucket, "backend": binding.backend, "available_bytes": available, "additional_bytes": size},
                )
        return selected

    select_placements = select_placement

    def _normalize_content(self, item: Mapping[str, Any]) -> dict[str, Any]:
        value = ensure_json_compatible(item, "content")
        digest = value.get("iroh_hash", value.get("content_hash", value.get("hash")))
        size = value.get("size", value.get("size_bytes"))
        _content_hash(digest)
        _uint(size, "content.size")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise BackendConfigError("content.metadata must be an object")
        return {"iroh_hash": digest, "size": size, "metadata": dict(metadata)}

    def reconcile(
        self,
        bucket: str,
        contents: Iterable[Mapping[str, Any]] | None = None,
        *,
        dry_run: bool = False,
        operation: str = "reconcile",
        previous_policy: BucketPolicy | None = None,
        prune: bool = False,
    ) -> ReconciliationReceipt:
        policy = self.get_policy(bucket)
        started_epoch = self.clock()
        before = self.logical_usage(bucket)
        supplied = contents is not None
        if contents is None:
            with self._lock:
                rows = self._db.execute("SELECT iroh_hash,size,metadata_json FROM bucket_content WHERE bucket=? ORDER BY iroh_hash", (bucket,)).fetchall()
            desired = [{"iroh_hash": row[0], "size": int(row[1]), "metadata": json.loads(row[2])} for row in rows]
        else:
            desired = [self._normalize_content(item) for item in contents]
        unique: dict[str, dict[str, Any]] = {}
        duplicate_objects = 0
        duplicate_bytes = 0
        deduplicated_hashes: set[str] = set()
        for item in desired:
            existing = unique.get(item["iroh_hash"])
            if existing is not None:
                if existing["size"] != item["size"]:
                    raise IrohIntegrityError("duplicate Iroh hash has inconsistent sizes", operation="bucket.reconcile")
                if item["iroh_hash"] not in deduplicated_hashes:
                    deduplicated_hashes.add(item["iroh_hash"])
                    duplicate_objects += 1
                    duplicate_bytes += item["size"]
            else:
                unique[item["iroh_hash"]] = item

        actions: list[ReconciliationAction] = []
        external_sagas: list[str] = []
        projected = before
        rejected = False
        desired_bindings = self._desired_bindings(policy)
        capacity = {item["backend"]: item for item in self.capacity_report(bucket)["backends"]}
        capacity_reserved: dict[str, int] = {}

        for digest, item in sorted(unique.items()):
            with self._lock:
                row = self._db.execute("SELECT size FROM bucket_content WHERE bucket=? AND iroh_hash=?", (bucket, digest)).fetchone()
                placed_rows = self._db.execute(
                    "SELECT backend,role,tier,size FROM bucket_placements WHERE bucket=? AND iroh_hash=? AND status='placed'",
                    (bucket, digest),
                ).fetchall()
            placed = {row[0]: row for row in placed_rows}
            existing_content = row is not None
            if existing_content:
                if int(row[0]) != item["size"]:
                    raise IrohIntegrityError("an existing Iroh hash has a different size", operation="bucket.reconcile")
                if digest not in deduplicated_hashes:
                    deduplicated_hashes.add(digest)
                    duplicate_objects += 1
                    duplicate_bytes += item["size"]
            additional = 0 if existing_content else item["size"]
            if policy.quota_bytes is not None and projected + additional > policy.quota_bytes:
                rejected = True
                actions.append(ReconciliationAction("reject", digest, item["size"], None, None, None, "rejected", "bucket_quota_exceeded"))
                continue
            object_rejected = False
            for binding in desired_bindings:
                if binding.backend in placed:
                    actions.append(ReconciliationAction("noop", digest, item["size"], binding.backend, binding.role.value, binding.storage_tier.value, "unchanged", "already_placed"))
                    continue
                backend_duplicate = self._backend_has_content(binding.backend, digest)
                if backend_duplicate:
                    if digest not in deduplicated_hashes:
                        deduplicated_hashes.add(digest)
                        duplicate_objects += 1
                        duplicate_bytes += item["size"]
                    actions.append(ReconciliationAction(
                        "place", digest, item["size"], binding.backend, binding.role.value,
                        binding.storage_tier.value, "planned" if dry_run else "placed",
                        "content_already_on_backend",
                    ))
                    continue
                if capacity.get(binding.backend, {}).get("healthy") is False:
                    object_rejected = True
                    rejected = True
                    actions.append(ReconciliationAction("reject", digest, item["size"], binding.backend, binding.role.value, binding.storage_tier.value, "rejected", "backend_unhealthy"))
                    continue
                available = capacity.get(binding.backend, {}).get("available_bytes")
                reserved = capacity_reserved.get(binding.backend, 0)
                if available is not None and item["size"] > max(0, available - reserved):
                    object_rejected = True
                    rejected = True
                    actions.append(ReconciliationAction("reject", digest, item["size"], binding.backend, binding.role.value, binding.storage_tier.value, "rejected", "backend_capacity_exceeded"))
                    continue
                status = "planned" if dry_run else "placed"
                action = ReconciliationAction("place", digest, item["size"], binding.backend, binding.role.value, binding.storage_tier.value, status, "policy_requires_placement")
                if not dry_run:
                    action = self._external_action(bucket, action, item, external_sagas)
                    if action.status == "failed":
                        rejected = True
                        object_rejected = True
                actions.append(action)
                if action.status in {"planned", "placed"}:
                    capacity_reserved[binding.backend] = reserved + item["size"]
            desired_backend_names = {binding.backend for binding in desired_bindings}
            # Never remove a known-good placement if this object's desired
            # placement failed.  Doing so was the source of data-loss windows.
            for stale_backend, stale in sorted(placed.items()) if not object_rejected else ():
                if stale_backend in desired_backend_names:
                    continue
                stale_action = ReconciliationAction(
                    "remove", digest, int(stale[3]), stale_backend, stale[1], stale[2],
                    "planned" if dry_run else "removed", "binding_no_longer_in_policy",
                )
                if not dry_run:
                    stale_action = self._external_action(bucket, stale_action, item, external_sagas)
                    if stale_action.status == "failed":
                        rejected = True
                        object_rejected = True
                actions.append(stale_action)
            if not object_rejected:
                projected += additional

        if prune and supplied:
            desired_hashes = set(unique)
            with self._lock:
                extras = self._db.execute(
                    "SELECT iroh_hash,backend,role,tier,size FROM bucket_placements WHERE bucket=? AND status='placed' ORDER BY iroh_hash,backend",
                    (bucket,),
                ).fetchall()
            for digest, backend_name, role, tier, size in extras:
                if digest not in desired_hashes:
                    actions.append(ReconciliationAction("remove", digest, int(size), backend_name, role, tier, "planned" if dry_run else "removed", "content_not_desired"))

        failed = any(item.status == "failed" for item in actions)
        # A policy migration is all-or-nothing: capacity and quota rejection
        # must not leave a subset of its desired state in the catalog.
        policy_transition_failed = operation == "policy_migration" and rejected
        if not dry_run and (failed or policy_transition_failed):
            # Handler outcomes can be ambiguous, including a false/exception
            # after the remote side has acted.  Compensate every prepared saga.
            recovered = self._compensate_sagas(external_sagas)
            if not recovered:
                operation = f"{operation}_recovery_required"
        if not dry_run and not failed and not policy_transition_failed:
            with self._lock:
                self._db.execute("BEGIN TRANSACTION")
                try:
                    for item in unique.values():
                        if any(action.iroh_hash == item["iroh_hash"] and action.status in {"reject", "rejected", "failed"} for action in actions):
                            continue
                        self._db.execute(
                            "INSERT INTO bucket_content VALUES(?,?,?,?,?) ON CONFLICT(bucket,iroh_hash) DO NOTHING",
                            (bucket, item["iroh_hash"], item["size"], _canonical_json(item["metadata"]).decode(), self.clock()),
                        )
                    for action in actions:
                        if action.backend and action.action == "place" and action.status == "placed":
                            self._db.execute(
                                """INSERT INTO bucket_placements VALUES(?,?,?,?,?,?,?,?)
                                   ON CONFLICT(bucket,iroh_hash,backend) DO UPDATE SET role=excluded.role,
                                   tier=excluded.tier,size=excluded.size,status=excluded.status,updated_at=excluded.updated_at""",
                                (bucket, action.iroh_hash, action.backend, action.role, action.tier, action.size, "placed", self.clock()),
                            )
                        elif action.backend and action.action == "remove" and action.status == "removed":
                            self._db.execute("DELETE FROM bucket_placements WHERE bucket=? AND iroh_hash=? AND backend=?", (bucket, action.iroh_hash, action.backend))
                    if prune and supplied:
                        for digest in set(row[0] for row in self._db.execute("SELECT iroh_hash FROM bucket_content WHERE bucket=?", (bucket,)).fetchall()) - set(unique):
                            remaining = self._db.execute("SELECT 1 FROM bucket_placements WHERE bucket=? AND iroh_hash=?", (bucket, digest)).fetchone()
                            if not remaining:
                                self._db.execute("DELETE FROM bucket_content WHERE bucket=? AND iroh_hash=?", (bucket, digest))
                    if external_sagas:
                        marks = ",".join("?" for _ in external_sagas)
                        self._db.execute(f"UPDATE bucket_placement_sagas SET state='committed',updated_at=? WHERE saga_id IN ({marks})", (self.clock(), *external_sagas))
                    self._db.execute("COMMIT")
                except Exception:
                    self._db.execute("ROLLBACK")
                    self._compensate_sagas(external_sagas)
                    raise

        after = projected if dry_run else self.logical_usage(bucket)
        status = "dry-run" if dry_run and not rejected else ("recovery_required" if operation.endswith("_recovery_required") else ("partial" if failed else ("rejected" if rejected else "converged")))
        receipt = ReconciliationReceipt(
            uuid.uuid4().hex, bucket, operation, status, policy.policy_digest,
            _rfc3339(started_epoch), _rfc3339(self.clock()), dry_run, tuple(actions),
            before, after, policy.quota_bytes, duplicate_objects, duplicate_bytes,
        )
        self._persist_receipt(receipt)
        self.last_receipt = receipt
        return receipt

    def _persist_receipt(self, receipt: ReconciliationReceipt) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO bucket_receipts VALUES(?,?,?,?,?,?)",
                (receipt.receipt_id, receipt.bucket, receipt.operation, receipt.status, receipt.to_json(), self.clock()),
            )

    def place_content(
        self,
        bucket: str,
        iroh_hash: str,
        size: int,
        *,
        metadata: Mapping[str, Any] | None = None,
        dry_run: bool = False,
        raise_on_rejection: bool = True,
    ) -> ReconciliationReceipt:
        receipt = self.reconcile(bucket, [{"iroh_hash": iroh_hash, "size": size, "metadata": dict(metadata or {})}], dry_run=dry_run)
        if raise_on_rejection and receipt.status in {"rejected", "partial", "recovery_required"}:
            reason = next((item.reason for item in receipt.actions if item.status in {"rejected", "failed"}), "placement_rejected")
            raise IrohConflictError(
                "bucket placement was rejected", operation="bucket.place",
                metadata={"bucket": bucket, "reason": reason, "receipt_id": receipt.receipt_id},
            )
        return receipt

    add_content = place_content

    def reconcile_inventory(
        self,
        bucket: str,
        inventory: Iterable[Mapping[str, Any]],
        **kwargs: Any,
    ) -> ReconciliationReceipt:
        return self.reconcile(bucket, inventory, **kwargs)

    def get_receipt(self, receipt_id: str) -> ReconciliationReceipt:
        with self._lock:
            row = self._db.execute("SELECT receipt_json FROM bucket_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
        if row is None:
            raise KeyError(receipt_id)
        return verify_reconciliation_receipt(row[0])

    def list_receipts(self, bucket: str | None = None) -> tuple[ReconciliationReceipt, ...]:
        with self._lock:
            if bucket is None:
                rows = self._db.execute("SELECT receipt_json FROM bucket_receipts ORDER BY created_at,receipt_id").fetchall()
            else:
                _bucket_name(bucket)
                rows = self._db.execute("SELECT receipt_json FROM bucket_receipts WHERE bucket=? ORDER BY created_at,receipt_id", (bucket,)).fetchall()
        return tuple(verify_reconciliation_receipt(row[0]) for row in rows)


BucketTieringManager = IrohBucketTieringManager
VirtualBucketTieringManager = IrohBucketTieringManager
IrohBucketManager = IrohBucketTieringManager
BucketTieringReconciler = IrohBucketTieringManager
BucketReconciliationReceipt = ReconciliationReceipt


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _rfc3339(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "BUCKET_POLICY_SCHEMA_VERSION", "TIER_POLICY_SCHEMA_VERSION",
    "RECONCILIATION_RECEIPT_SCHEMA_VERSION", "RECONCILIATION_RECEIPT_KIND",
    "BindingRole", "StorageTier", "BackendBinding", "BucketBinding", "TierPolicy",
    "BucketPolicy", "CapacityReport", "ReconciliationAction", "ReconciliationReceipt",
    "BucketReconciliationReceipt", "IrohBucketTieringManager", "BucketTieringManager",
    "VirtualBucketTieringManager", "IrohBucketManager", "BucketTieringReconciler",
    "validate_tier_policy", "validate_bucket_policy",
    "migrate_bucket_policy", "bucket_policy_schema", "tier_policy_schema",
    "reconciliation_receipt_schema", "verify_reconciliation_receipt",
]

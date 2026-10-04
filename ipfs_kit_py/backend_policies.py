"""
Backend Policy Models for IPFS Kit Storage System

This module defines policy data structures that can be applied to storage backends
to manage quotas, replication, retention, and cache policies.
"""

import time
from dataclasses import replace
from collections.abc import Mapping, Sequence
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from enum import Enum

from ipfs_kit_py.core.replication.contracts import BackendInventory, ReplicaObservation, ReplicaPolicy as CanonicalReplicaPolicy
from ipfs_kit_py.core.replication.integrity import ReplicaContent
from ipfs_kit_py.core.replication.reconciler import (
    ReplicaReconciler,
    ReconciliationActionKind,
    ReconciliationReceipt,
)


LEGACY_REPLICATION_ADAPTER_SCHEMA = "ipfs_kit_py/legacy-replication-adapter@1"
LegacyReplicationAdapter_V1 = LEGACY_REPLICATION_ADAPTER_SCHEMA


class LegacyReplicationConfigurationError(ValueError):
    """A legacy caller lacks the immutable data needed for reconciliation."""


class LegacyPolicyMigrationError(LegacyReplicationConfigurationError):
    """A legacy policy asks for semantics the canonical policy cannot express."""

    def __init__(self, unsupported_fields: Mapping[str, Any]):
        self.unsupported_fields = dict(unsupported_fields)
        fields = ", ".join(sorted(self.unsupported_fields)) or "unknown"
        super().__init__(f"legacy replication policy has unsupported fields: {fields}")


class LegacyReplicationCleanupBlockedError(LegacyReplicationConfigurationError):
    """Legacy cleanup is refused until dynamic callers have migrated."""

    def __init__(self, receipt: ReconciliationReceipt):
        self.receipt = receipt
        super().__init__(
            "legacy replication cleanup is blocked because dynamic callers have not been resolved"
        )


class QuotaUnit(str, Enum):
    """Units for quota specifications."""
    BYTES = "bytes"
    KB = "kb"
    MB = "mb"
    GB = "gb"
    TB = "tb"
    

class ReplicationStrategy(str, Enum):
    """Replication strategies for content."""
    NONE = "none"
    SIMPLE = "simple"  # Simple redundancy across backends
    ERASURE_CODING = "erasure_coding"  # Erasure coding for efficiency
    GEOGRAPHICAL = "geographical"  # Geographic distribution
    TIERED = "tiered"  # Tier-based replication


class RetentionAction(str, Enum):
    """Actions to take when retention period expires."""
    DELETE = "delete"
    ARCHIVE = "archive"
    MIGRATE = "migrate"
    NOTIFY = "notify"


class CacheEvictionPolicy(str, Enum):
    """Cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    ARC = "arc"  # Adaptive Replacement Cache
    HEAT_SCORE = "heat_score"  # Heat score based eviction


class StorageQuotaPolicy(BaseModel):
    """Storage quota policy for a backend."""
    enabled: bool = True
    max_size: Optional[int] = Field(None, description="Maximum storage size")
    max_size_unit: QuotaUnit = QuotaUnit.GB
    warn_threshold: float = Field(0.8, ge=0.0, le=1.0, description="Warning threshold (0-1)")
    max_files: Optional[int] = Field(None, description="Maximum number of files")
    max_pins: Optional[int] = Field(None, description="Maximum number of pins")
    quota_exceeded_action: str = Field("warn", description="Action when quota exceeded")


class TrafficQuotaPolicy(BaseModel):
    """Traffic quota policy for a backend."""
    enabled: bool = True
    max_bandwidth_mbps: Optional[float] = Field(None, description="Max bandwidth in Mbps")
    max_requests_per_minute: Optional[int] = Field(None, description="Max requests per minute")
    max_upload_per_day: Optional[int] = Field(None, description="Max daily upload in GB")
    max_download_per_day: Optional[int] = Field(None, description="Max daily download in GB")
    burst_allowance: bool = Field(True, description="Allow burst traffic")
    throttle_on_limit: bool = Field(True, description="Throttle instead of rejecting")


class ReplicationPolicy(BaseModel):
    """Replication policy for content."""
    enabled: bool = True
    strategy: ReplicationStrategy = ReplicationStrategy.SIMPLE
    min_redundancy: int = Field(2, ge=1, description="Minimum number of copies")
    max_redundancy: int = Field(4, ge=1, description="Maximum number of copies")
    critical_redundancy: int = Field(5, ge=1, description="Redundancy for critical content")
    geo_distribution: bool = Field(False, description="Require geographic distribution")
    preferred_backends: List[str] = Field(default_factory=list)
    excluded_backends: List[str] = Field(default_factory=list)
    replication_delay_seconds: int = Field(0, description="Delay before replication")


def _legacy_policy_values(policy: ReplicationPolicy | Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a Pydantic v1/v2 model or mapping without silently dropping keys."""

    if isinstance(policy, ReplicationPolicy):
        if hasattr(policy, "model_dump"):
            return dict(policy.model_dump())
        return dict(policy.dict())
    if isinstance(policy, Mapping):
        return dict(policy)
    raise LegacyReplicationConfigurationError(
        "legacy replication policy must be a ReplicationPolicy or mapping"
    )


def migrate_legacy_replication_policy(
    policy: ReplicationPolicy | Mapping[str, Any], *, policy_id: str = "legacy-replication"
) -> CanonicalReplicaPolicy:
    """Translate the small compatible subset of ``ReplicationPolicy`` explicitly.

    The old policy surface contained scheduling, geographic, and strategy
    semantics that are not equivalent to a replica placement contract.  Those
    fields fail closed rather than being quietly ignored.
    """

    values = _legacy_policy_values(policy)
    known = {
        "enabled",
        "strategy",
        "min_redundancy",
        "max_redundancy",
        "critical_redundancy",
        "geo_distribution",
        "preferred_backends",
        "excluded_backends",
        "replication_delay_seconds",
    }
    unsupported = {name: value for name, value in values.items() if name not in known}
    if values.get("enabled", True) is not True:
        unsupported["enabled"] = values.get("enabled")
    strategy = values.get("strategy", ReplicationStrategy.SIMPLE)
    strategy_value = strategy.value if isinstance(strategy, ReplicationStrategy) else strategy
    if strategy_value != ReplicationStrategy.SIMPLE.value:
        unsupported["strategy"] = strategy
    if values.get("geo_distribution", False) is not False:
        unsupported["geo_distribution"] = values.get("geo_distribution")
    if values.get("replication_delay_seconds", 0) != 0:
        unsupported["replication_delay_seconds"] = values.get("replication_delay_seconds")
    if unsupported:
        raise LegacyPolicyMigrationError(unsupported)

    try:
        minimum = int(values.get("min_redundancy", 2))
        maximum = int(values.get("max_redundancy", 4))
        critical = int(values.get("critical_redundancy", 5))
        return CanonicalReplicaPolicy(
            policy_id=policy_id,
            min_replicas=minimum,
            desired_replicas=minimum,
            max_replicas=maximum,
            critical_replicas=critical,
            preferred_backends=tuple(values.get("preferred_backends", ())),
            excluded_backends=tuple(values.get("excluded_backends", ())),
        )
    except (TypeError, ValueError) as exc:
        raise LegacyReplicationConfigurationError(
            f"legacy replication policy cannot be migrated: {exc}"
        ) from exc


class LegacyReplicationAdapter:
    """Caller-complete bridge from legacy entry points to ``ReplicaReconciler``.

    A queued observation is passed through to the reconciler only as evidence;
    it cannot become a counted replica.  Potential removals are first planned
    dry-run and then blocked, because legacy entry points may still have
    unresolved dynamic callers that expect the old destructive behavior.
    """

    interface_version = LEGACY_REPLICATION_ADAPTER_SCHEMA

    def __init__(
        self,
        reconciler: ReplicaReconciler,
        policy: CanonicalReplicaPolicy,
        inventory: BackendInventory,
    ) -> None:
        if not isinstance(reconciler, ReplicaReconciler):
            raise LegacyReplicationConfigurationError("reconciler must be a ReplicaReconciler")
        if not isinstance(policy, CanonicalReplicaPolicy):
            raise LegacyReplicationConfigurationError("policy must be a canonical ReplicaPolicy")
        if not isinstance(inventory, BackendInventory):
            raise LegacyReplicationConfigurationError("inventory must be a BackendInventory")
        self._reconciler = reconciler
        self._policy = policy
        self._inventory = inventory

    def reconcile(
        self,
        *,
        content_ref: str,
        content_size_bytes: int,
        expected_digest: str,
        expected_version_id: str,
        replicas: Sequence[ReplicaObservation] = (),
        source: ReplicaContent | None = None,
        target_redundancy: int | None = None,
    ) -> ReconciliationReceipt:
        policy = self._policy_for_target(target_redundancy)
        arguments = {
            "content_ref": content_ref,
            "content_size_bytes": content_size_bytes,
            "policy": policy,
            "inventory": self._inventory,
            "expected_digest": expected_digest,
            "expected_version_id": expected_version_id,
            "replicas": replicas,
            "source": source,
        }
        preview = self._reconciler.reconcile(**arguments, dry_run=True)
        if any(action.kind is ReconciliationActionKind.REMOVE for action in preview.actions):
            raise LegacyReplicationCleanupBlockedError(preview)
        return self._reconciler.reconcile(**arguments)

    def _policy_for_target(self, target_redundancy: int | None) -> CanonicalReplicaPolicy:
        if target_redundancy is None:
            return self._policy
        if isinstance(target_redundancy, bool) or not isinstance(target_redundancy, int):
            raise LegacyReplicationConfigurationError("target_redundancy must be an integer")
        if not self._policy.min_replicas <= target_redundancy <= self._policy.max_replicas:
            raise LegacyReplicationConfigurationError(
                "target_redundancy must be within the canonical policy bounds"
            )
        return replace(self._policy, desired_replicas=target_redundancy)


class RetentionPolicy(BaseModel):
    """Retention policy for content."""
    enabled: bool = True
    default_retention_days: Optional[int] = Field(None, description="Default retention period")
    max_retention_days: Optional[int] = Field(None, description="Maximum retention period")
    action_on_expiry: RetentionAction = RetentionAction.ARCHIVE
    legal_hold_supported: bool = Field(True, description="Support legal hold")
    archive_backend: Optional[str] = Field(None, description="Backend for archiving")
    delete_after_archive_days: Optional[int] = Field(None, description="Delete after archiving")
    compliance_tags: List[str] = Field(default_factory=list, description="Compliance requirements")


class CachePolicy(BaseModel):
    """Cache policy for a backend."""
    enabled: bool = True
    max_cache_size: Optional[int] = Field(None, description="Maximum cache size")
    max_cache_size_unit: QuotaUnit = QuotaUnit.GB
    eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.ARC
    ttl_seconds: Optional[int] = Field(None, description="Time to live for cached items")
    promotion_threshold: int = Field(2, description="Access count for promotion")
    demotion_threshold_days: int = Field(30, description="Days before demotion")
    prefetch_enabled: bool = Field(False, description="Enable predictive prefetching")
    compress_cache: bool = Field(False, description="Compress cached content")


class BackendPolicySet(BaseModel):
    """Complete policy set for a storage backend."""
    backend_name: str
    storage_quota: Optional[StorageQuotaPolicy] = None
    traffic_quota: Optional[TrafficQuotaPolicy] = None
    replication: Optional[ReplicationPolicy] = None
    retention: Optional[RetentionPolicy] = None
    cache: Optional[CachePolicy] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    enabled: bool = True


class PolicyViolation(BaseModel):
    """Represents a policy violation event."""
    backend_name: str
    policy_type: str  # storage_quota, traffic_quota, etc.
    violation_type: str  # exceeded, warning, etc.
    message: str
    timestamp: float = Field(default_factory=time.time)
    resolved: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def convert_size_to_bytes(size: int, unit: QuotaUnit) -> int:
    """Convert size with unit to bytes."""
    multipliers = {
        QuotaUnit.BYTES: 1,
        QuotaUnit.KB: 1024,
        QuotaUnit.MB: 1024 ** 2,
        QuotaUnit.GB: 1024 ** 3,
        QuotaUnit.TB: 1024 ** 4,
    }
    return size * multipliers[unit]


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

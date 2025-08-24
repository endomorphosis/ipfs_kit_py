"""
Backend Policy Models for IPFS Kit Storage System

This module defines policy data structures that can be applied to storage backends
to manage quotas, replication, retention, and cache policies.
"""

import time
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from enum import Enum


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
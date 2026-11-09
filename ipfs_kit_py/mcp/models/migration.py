"""
Migration models for MCP server.

This module defines the data models for the cross-backend migration functionality
as specified in the MCP roadmap Q2 2025 priorities.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class MigrationPolicy(BaseModel):
    """Migration policy definition."""
    name: str = Field(..., description="Name of the migration policy")
    description: Optional[str] = Field(None, description="Description of the policy")
    source_backend: str = Field(..., description="Source storage backend")
    target_backend: str = Field(..., description="Target storage backend")
    content_filter: Dict[str, Any] = Field({}, description="Content filter criteria")
    priority: int = Field(1, description="Priority level (1-5)")
    cost_optimized: bool = Field(False, description="Enable cost optimization")
    metadata_sync: bool = Field(True, description="Synchronize metadata")
    auto_clean: bool = Field(False, description="Remove from source after migration")
    schedule: Optional[str] = Field(
        None, description="Cron-style schedule for recurring migrations")
    retention_days: Optional[int] = Field(None, description="Days to retain migration records")


class MigrationRequest(BaseModel):
    """Migration request definition."""
    source_backend: str = Field(..., description="Source storage backend")
    target_backend: str = Field(..., description="Target storage backend")
    cid: str = Field(..., description="Content identifier to migrate")
    policy_name: Optional[str] = Field(None, description="Migration policy to apply")
    metadata_sync: bool = Field(True, description="Synchronize metadata")
    remove_source: bool = Field(False, description="Remove from source after migration")
    cost_optimized: bool = Field(False, description="Enable cost optimization")
    priority: int = Field(3, description="Priority level (1-5, where 1 is highest)")


class MigrationBatchRequest(BaseModel):
    """Batch migration request definition."""
    source_backend: str = Field(..., description="Source storage backend")
    target_backend: str = Field(..., description="Target storage backend")
    cids: List[str] = Field(..., description="Content identifiers to migrate")
    policy_name: Optional[str] = Field(None, description="Migration policy to apply")
    metadata_sync: bool = Field(True, description="Synchronize metadata")
    remove_source: bool = Field(False, description="Remove from source after migration")
    cost_optimized: bool = Field(False, description="Enable cost optimization")
    parallel_limit: Optional[int] = Field(5, description="Maximum number of parallel migrations")
    priority: int = Field(3, description="Priority level (1-5, where 1 is highest)")


class MigrationStatus(BaseModel):
    """Migration status information."""
    id: str = Field(..., description="Migration job ID")
    batch_id: Optional[str] = Field(None, description="Batch ID if part of batch migration")
    source_backend: str = Field(..., description="Source storage backend")
    target_backend: str = Field(..., description="Target storage backend")
    cid: str = Field(..., description="Content identifier")
    status: str = Field(..., description="Migration status")
    created_at: float = Field(..., description="Creation timestamp")
    updated_at: float = Field(..., description="Last update timestamp")
    progress: float = Field(0.0, description="Migration progress percentage")
    policy_applied: Optional[str] = Field(None, description="Policy applied to migration")
    error: Optional[str] = Field(None, description="Error message if failed")
    result: Optional[Dict[str, Any]] = Field(None, description="Migration result")
    metadata_sync: bool = Field(True, description="Whether metadata synchronization is enabled")
    remove_source: bool = Field(False, description="Whether to remove from source after migration")
    cost_optimized: bool = Field(False, description="Whether cost optimization is enabled")
    priority: int = Field(3, description="Priority level (1-5, where 1 is highest)")


class MigrationEstimate(BaseModel):
    """Migration cost and resource estimation."""
    estimated_cost: float = Field(..., description="Estimated total cost in USD")
    currency: str = Field("USD", description="Currency for cost estimation")
    size_bytes: int = Field(..., description="Content size in bytes")
    source_cost: float = Field(0.0, description="Cost to retrieve from source")
    target_cost: float = Field(..., description="Cost to store in target")
    transfer_cost: float = Field(..., description="Cost to transfer data")
    time_estimate_seconds: float = Field(..., description="Estimated time to complete")
    theoretical_bandwidth: str = Field("5 MB/s", description="Assumed bandwidth for estimation")
    reliability: str = Field("high", description="Reliability estimation (high/medium/low)")


class MigrationSummary(BaseModel):
    """Summary of migration operations."""
    total_migrations: int = Field(..., description="Total number of migrations")
    active_migrations: int = Field(..., description="Number of active migrations")
    completed_migrations: int = Field(..., description="Number of completed migrations")
    failed_migrations: int = Field(..., description="Number of failed migrations")
    queued_migrations: int = Field(..., description="Number of queued migrations")
    total_bytes_migrated: int = Field(..., description="Total bytes migrated")
    total_cost: float = Field(..., description="Total cost of migrations")
    active_backends: List[str] = Field(..., description="List of active backends")
    most_used_source: Optional[str] = Field(None, description="Most frequently used source backend")
    most_used_target: Optional[str] = Field(None, description="Most frequently used target backend")


class BackendMigrationCapabilities(BaseModel):
    """Capabilities of a backend for migration operations."""
    backend_id: str = Field(..., description="Backend identifier")
    supports_metadata: bool = Field(False, description="Whether backend supports metadata")
    supports_removal: bool = Field(False, description="Whether backend supports content removal")
    supports_bulk_operations: bool = Field(
        False, description="Whether backend supports bulk operations")
    cost_per_gb: float = Field(0.0, description="Cost per GB for storage")
    retrieval_cost_per_gb: float = Field(0.0, description="Cost per GB for retrieval")
    max_file_size: Optional[int] = Field(None, description="Maximum file size in bytes")
    availability: float = Field(1.0, description="Availability percentage (0.0-1.0)")
    average_latency_ms: Optional[int] = Field(None, description="Average latency in milliseconds")
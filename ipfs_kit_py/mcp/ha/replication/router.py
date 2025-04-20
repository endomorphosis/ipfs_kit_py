"""
API Router for Replication and Consistency in MCP High Availability Architecture.

This module provides REST API endpoints for the data replication and consistency
functionality, allowing nodes to synchronize data across the cluster.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ipfs_kit_py.mcp.ha.replication.consistency import (
    ConsistencyModel,
    ConsistencyService,
    ReplicatedData,
    ReplicationConfig,
    ReplicationStrategy,
    ConflictResolutionStrategy,
    VectorClock,
    DataVersion
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v0/ha/replication", tags=["replication"])


# Request and response models
class KeyItem(BaseModel):
    """Key item for batch operations."""
    
    key: str


class KeysRequest(BaseModel):
    """Request for batch key operations."""
    
    keys: List[str] = Field(..., description="List of keys")


class VersionInfo(BaseModel):
    """Version information for a key."""
    
    version_id: str
    timestamp: float
    node_id: str
    vector_clock: Dict[str, Any]
    is_deleted: bool
    content_hash: Optional[str] = None


class VersionsRequest(BaseModel):
    """Request for comparing versions."""
    
    versions: Dict[str, Dict[str, Any]] = Field(..., description="Version information keyed by key")


class SetRequest(BaseModel):
    """Request for setting a key."""
    
    key: str
    value: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: Dict[str, Any] = None
    content_type: str = "application/json"
    created_at: float = Field(default_factory=time.time)


class BatchSetRequest(BaseModel):
    """Request for setting multiple keys."""
    
    items: List[Dict[str, Any]] = Field(..., description="List of items to set")


class ConfigModel(BaseModel):
    """Configuration for replication."""
    
    consistency_model: str = "eventual"
    replication_strategy: str = "asynchronous"
    conflict_resolution: str = "vector_clock"
    sync_interval: int = 30
    quorum_size: int = 2
    read_repair: bool = True
    gossip_enabled: bool = True
    max_sync_batch: int = 1000
    priority_keys: List[str] = Field(default_factory=list)


# Get consistency service from request state
def get_consistency_service(request: Request) -> ConsistencyService:
    """
    Get consistency service from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        ConsistencyService instance
    """
    service = request.app.state.consistency_service
    if not service or not service.initialized:
        raise HTTPException(
            status_code=503,
            detail="Consistency service not initialized"
        )
    return service


@router.get("/status")
async def get_status(
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Get replication status."""
    status = service.get_consistency_status()
    return {
        "success": True,
        "status": status
    }


@router.get("/keys")
async def list_keys(
    prefix: Optional[str] = None,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """List available keys."""
    result = await service.list_keys(prefix)
    return result


@router.get("/get")
async def get_key(
    key: str,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Get value for a key."""
    result = await service.get(key)
    return result


@router.post("/get_batch")
async def get_batch(
    request: KeysRequest,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Get multiple keys in a batch."""
    items = []
    for key in request.keys:
        result = await service.get(key)
        items.append(result)
    
    return {
        "success": True,
        "items": items,
        "count": len(items)
    }


@router.get("/version")
async def get_version(
    key: str,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Get version information for a key."""
    result = await service.get(key)
    if not result.get("success"):
        return result
    
    return {
        "success": True,
        "key": key,
        "version": result.get("version")
    }


@router.post("/compare_versions")
async def compare_versions(
    request: VersionsRequest,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Compare versions with local data."""
    if not request.versions:
        return {
            "success": True,
            "remote_newer": [],
            "local_newer": [],
            "conflicts": [],
            "equal": [],
            "message": "No versions to compare"
        }
    
    remote_newer = []
    local_newer = []
    conflicts = []
    equal = []
    
    for key, remote_version_data in request.versions.items():
        # Get local data
        local_result = await service.get(key)
        
        if not local_result.get("success"):
            # We don't have this key, so remote is newer
            remote_newer.append(key)
            continue
        
        # Compare vector clocks
        local_version_data = local_result.get("version", {})
        
        # Create vector clocks
        local_vc_data = local_version_data.get("vector_clock", {})
        remote_vc_data = remote_version_data.get("vector_clock", {})
        
        local_vc = VectorClock(
            node_counters=local_vc_data.get("node_counters", {}),
            last_updated=local_vc_data.get("last_updated", 0)
        )
        
        remote_vc = VectorClock(
            node_counters=remote_vc_data.get("node_counters", {}),
            last_updated=remote_vc_data.get("last_updated", 0)
        )
        
        # Compare
        comparison = local_vc.compare(remote_vc)
        
        if comparison < 0:
            # Remote is newer
            remote_newer.append(key)
        elif comparison > 0:
            # Local is newer
            local_newer.append(key)
        elif comparison == 0:
            # Check content hash if available
            local_hash = local_version_data.get("content_hash")
            remote_hash = remote_version_data.get("content_hash")
            
            if local_hash and remote_hash and local_hash == remote_hash:
                # Equal content
                equal.append(key)
            else:
                # Potentially conflicting
                conflicts.append(key)
    
    return {
        "success": True,
        "remote_newer": remote_newer,
        "local_newer": local_newer,
        "conflicts": conflicts,
        "equal": equal,
        "count": len(request.versions)
    }


@router.post("/set")
async def set_key(
    request: SetRequest,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Set a value."""
    result = await service.set(
        key=request.key,
        value=request.value,
        metadata=request.metadata
    )
    return result


@router.post("/set_batch")
async def set_batch(
    request: BatchSetRequest,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Set multiple values in a batch."""
    results = []
    accepted_keys = []
    rejected_keys = []
    
    for item in request.items:
        key = item.get("key")
        value = item.get("value")
        metadata = item.get("metadata", {})
        
        # Handle version if provided
        incoming_version = item.get("version")
        if incoming_version:
            # Check if we need to reconstruct objects
            # For normal operation this is handled by the consistency service
            pass
        
        # Set the key
        result = await service.set(key, value, metadata)
        results.append(result)
        
        if result.get("success"):
            accepted_keys.append(key)
        else:
            rejected_keys.append(key)
    
    return {
        "success": True,
        "results": results,
        "count": len(results),
        "accepted_count": len(accepted_keys),
        "rejected_count": len(rejected_keys),
        "accepted_keys": accepted_keys,
        "rejected_keys": rejected_keys
    }


@router.delete("/delete")
async def delete_key(
    key: str,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Delete a key."""
    result = await service.delete(key)
    return result


@router.delete("/delete_batch")
async def delete_batch(
    request: KeysRequest,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Delete multiple keys in a batch."""
    results = []
    success_keys = []
    failed_keys = []
    
    for key in request.keys:
        result = await service.delete(key)
        results.append(result)
        
        if result.get("success"):
            success_keys.append(key)
        else:
            failed_keys.append(key)
    
    return {
        "success": True,
        "results": results,
        "count": len(results),
        "success_count": len(success_keys),
        "failed_count": len(failed_keys),
        "success_keys": success_keys,
        "failed_keys": failed_keys
    }


@router.get("/config")
async def get_config(
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Get current configuration."""
    config = service.config
    
    return {
        "success": True,
        "config": {
            "consistency_model": config.consistency_model,
            "replication_strategy": config.replication_strategy,
            "conflict_resolution": config.conflict_resolution,
            "sync_interval": config.sync_interval,
            "quorum_size": config.quorum_size,
            "read_repair": config.read_repair,
            "gossip_enabled": config.gossip_enabled,
            "max_sync_batch": config.max_sync_batch,
            "priority_keys": config.priority_keys
        }
    }


@router.post("/config")
async def update_config(
    config: ConfigModel,
    service: ConsistencyService = Depends(get_consistency_service)
):
    """Update configuration."""
    # Convert string values to enum values
    try:
        consistency_model = ConsistencyModel(config.consistency_model)
        replication_strategy = ReplicationStrategy(config.replication_strategy)
        conflict_resolution = ConflictResolutionStrategy(config.conflict_resolution)
        
        # Create new config
        new_config = ReplicationConfig(
            consistency_model=consistency_model,
            replication_strategy=replication_strategy,
            conflict_resolution=conflict_resolution,
            sync_interval=config.sync_interval,
            quorum_size=config.quorum_size,
            read_repair=config.read_repair,
            gossip_enabled=config.gossip_enabled,
            max_sync_batch=config.max_sync_batch,
            priority_keys=config.priority_keys
        )
        
        # Update service config
        service.config = new_config
        
        return {
            "success": True,
            "message": "Configuration updated",
            "config": {
                "consistency_model": config.consistency_model,
                "replication_strategy": config.replication_strategy,
                "conflict_resolution": config.conflict_resolution,
                "sync_interval": config.sync_interval,
                "quorum_size": config.quorum_size,
                "read_repair": config.read_repair,
                "gossip_enabled": config.gossip_enabled,
                "max_sync_batch": config.max_sync_batch,
                "priority_keys": config.priority_keys
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration value: {str(e)}"
        )


def register_with_app(app, service: ConsistencyService):
    """
    Register replication router with FastAPI app.
    
    Args:
        app: FastAPI application
        service: ConsistencyService instance
    """
    # Store service in app state
    app.state.consistency_service = service
    
    # Include router
    app.include_router(router)
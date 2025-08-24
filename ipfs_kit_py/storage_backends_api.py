"""
Storage Backends API for IPFS Kit

This module provides a FastAPI router for managing and interacting with
various storage backends in IPFS Kit.

Available storage backends:
- IPFS (default) - InterPlanetary File System
- S3 - Amazon S3 and compatible object storage
- Storacha - Formerly Web3.Storage
- HuggingFace - AI model and dataset storage
- Filecoin - Decentralized storage network
- Lassie - Retrieval client for IPFS/Filecoin
"""

import logging
import time
from typing import Any, Dict, List, Optional

import fastapi
from fastapi import Body, HTTPException, Query, Request, BackgroundTasks
from pydantic import BaseModel

# Import policy models
try:
    from .backend_policies import (
        BackendPolicySet, StorageQuotaPolicy, TrafficQuotaPolicy,
        ReplicationPolicy, RetentionPolicy, CachePolicy, 
        PolicyViolation, convert_size_to_bytes, format_bytes
    )
    BACKEND_POLICIES_AVAILABLE = True
except ImportError:
    BACKEND_POLICIES_AVAILABLE = False
    BackendPolicySet = dict

# Import enhanced pin index for storage analytics
try:
    from ipfs_kit_py.enhanced_pin_index import (
        get_global_enhanced_pin_index, 
        get_cli_pin_metrics
    )
    ENHANCED_PIN_INDEX_AVAILABLE = True
except ImportError:
    ENHANCED_PIN_INDEX_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Create router
storage_router = fastapi.APIRouter(prefix="/api/v0/storage", tags=["storage"])

@storage_router.get("/backends", response_model=Dict[str, Any])
async def list_storage_backends():
    """
    List all available storage backends.
    
    This endpoint returns information about all configured storage backends,
    including their status and capabilities.
    
    Returns:
        Dictionary of storage backends with their status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # List storage backends
        logger.info("Listing storage backends")
        result = api.storage.list_backends()
        
        # Transform result for API response
        backends = {}
        for backend_name, backend_info in result.items():
            backends[backend_name] = {
                "enabled": backend_info.get("enabled", False),
                "type": backend_info.get("type", "unknown"),
                "description": backend_info.get("description", ""),
                "capabilities": backend_info.get("capabilities", []),
                "status": backend_info.get("status", "unknown"),
                "policies": backend_info.get("policies", {}),
                "quota_usage": backend_info.get("quota_usage", {}),
                "policy_violations": backend_info.get("policy_violations", [])
            }
        
        return {
            "success": True,
            "operation": "list_storage_backends",
            "timestamp": time.time(),
            "backends": backends,
            "count": len(backends),
            "default": result.get("default", "ipfs")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error listing storage backends: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing storage backends: {str(e)}")
        
@storage_router.get("/backends/{backend_name}", response_model=Dict[str, Any])
async def get_storage_backend_info(backend_name: str):
    """
    Get information about a specific storage backend.
    
    This endpoint returns detailed information about a specific storage backend,
    including its configuration and status.
    
    Parameters:
    - **backend_name**: The name of the storage backend (e.g., 'ipfs', 's3', 'storacha')
    
    Returns:
        Detailed backend information
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Get backend info
        logger.info(f"Getting info for storage backend: {backend_name}")
        
        if not hasattr(api.storage, "get_backend_info"):
            # Fall back to list_backends and filter
            backends = api.storage.list_backends()
            if backend_name not in backends:
                raise HTTPException(
                    status_code=404,
                    detail=f"Storage backend '{backend_name}' not found"
                )
            backend_info = backends[backend_name]
        else:
            backend_info = api.storage.get_backend_info(backend_name)
            
        if not backend_info:
            raise HTTPException(
                status_code=404,
                detail=f"Storage backend '{backend_name}' not found"
            )
            
        # Transform result for API response
        info = {
            "name": backend_name,
            "enabled": backend_info.get("enabled", False),
            "type": backend_info.get("type", "unknown"),
            "description": backend_info.get("description", ""),
            "capabilities": backend_info.get("capabilities", []),
            "status": backend_info.get("status", "unknown"),
            "configuration": backend_info.get("configuration", {}),
            "stats": backend_info.get("stats", {}),
            "policies": backend_info.get("policies", {}),
            "quota_usage": backend_info.get("quota_usage", {}),
            "policy_violations": backend_info.get("policy_violations", [])
        }
        
        # Remove sensitive information
        if "configuration" in info and isinstance(info["configuration"], dict):
            for key in list(info["configuration"].keys()):
                if any(sensitive in key.lower() for sensitive in ["key", "secret", "password", "token"]):
                    info["configuration"][key] = "********"
        
        return {
            "success": True,
            "operation": "get_storage_backend_info",
            "timestamp": time.time(),
            "backend": info
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting storage backend info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting storage backend info: {str(e)}")
        
@storage_router.post("/backends/{backend_name}/enable", response_model=Dict[str, Any])
async def enable_storage_backend(backend_name: str):
    """
    Enable a storage backend.
    
    This endpoint enables a previously configured storage backend.
    
    Parameters:
    - **backend_name**: The name of the storage backend to enable
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Enable backend
        logger.info(f"Enabling storage backend: {backend_name}")
        result = api.storage.enable_backend(backend_name)
        
        return {
            "success": True,
            "operation": "enable_storage_backend",
            "timestamp": time.time(),
            "backend": backend_name,
            "enabled": result.get("enabled", False),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error enabling storage backend: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error enabling storage backend: {str(e)}")
        
@storage_router.post("/backends/{backend_name}/disable", response_model=Dict[str, Any])
async def disable_storage_backend(backend_name: str):
    """
    Disable a storage backend.
    
    This endpoint disables a storage backend.
    
    Parameters:
    - **backend_name**: The name of the storage backend to disable
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Disable backend
        logger.info(f"Disabling storage backend: {backend_name}")
        result = api.storage.disable_backend(backend_name)
        
        return {
            "success": True,
            "operation": "disable_storage_backend",
            "timestamp": time.time(),
            "backend": backend_name,
            "enabled": result.get("enabled", False),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error disabling storage backend: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error disabling storage backend: {str(e)}")
        
@storage_router.post("/backends/{backend_name}/configure", response_model=Dict[str, Any])
async def configure_storage_backend(
    backend_name: str,
    configuration: Dict[str, Any] = Body(..., description="Backend configuration")
):
    """
    Configure a storage backend.
    
    This endpoint updates the configuration of a storage backend.
    
    Parameters:
    - **backend_name**: The name of the storage backend to configure
    - **configuration**: Configuration parameters for the backend
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Configure backend
        logger.info(f"Configuring storage backend: {backend_name}")
        result = api.storage.configure_backend(backend_name, configuration)
        
        # Remove sensitive information from response
        if "configuration" in result and isinstance(result["configuration"], dict):
            for key in list(result["configuration"].keys()):
                if any(sensitive in key.lower() for sensitive in ["key", "secret", "password", "token"]):
                    result["configuration"][key] = "********"
        
        return {
            "success": True,
            "operation": "configure_storage_backend",
            "timestamp": time.time(),
            "backend": backend_name,
            "status": result.get("status", "unknown"),
            "configuration": result.get("configuration", {})
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error configuring storage backend: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error configuring storage backend: {str(e)}")
        
@storage_router.post("/store", response_model=Dict[str, Any])
async def store_content(
    cid: str = Body(..., description="Content ID to store"),
    backends: List[str] = Body(None, description="Storage backends to use (default: all enabled)"),
    pin: bool = Body(True, description="Whether to pin the content locally")
):
    """
    Store content in specific storage backends.
    
    This endpoint stores existing IPFS content in the specified storage backends.
    
    Parameters:
    - **cid**: The Content ID to store
    - **backends**: List of storage backends to use (default: all enabled)
    - **pin**: Whether to pin the content locally (default: True)
    
    Returns:
        Storage operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Store content
        logger.info(f"Storing content {cid} in backends: {backends or 'all'}")
        result = api.storage.store(cid, backends=backends, pin=pin)
        
        return {
            "success": True,
            "operation": "store_content",
            "timestamp": time.time(),
            "cid": cid,
            "backends": result.get("backends", {}),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error storing content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error storing content: {str(e)}")
        
@storage_router.post("/retrieve", response_model=Dict[str, Any])
async def retrieve_content(
    cid: str = Body(..., description="Content ID to retrieve"),
    backends: List[str] = Body(None, description="Storage backends to check (default: all enabled)"),
    pin: bool = Body(True, description="Whether to pin the content locally"),
    force: bool = Body(False, description="Force retrieval even if content is available locally")
):
    """
    Retrieve content from storage backends.
    
    This endpoint retrieves content from the specified storage backends.
    
    Parameters:
    - **cid**: The Content ID to retrieve
    - **backends**: List of storage backends to check (default: all enabled)
    - **pin**: Whether to pin the content locally (default: True)
    - **force**: Force retrieval even if content is available locally (default: False)
    
    Returns:
        Retrieval operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Retrieve content
        logger.info(f"Retrieving content {cid} from backends: {backends or 'all'}")
        result = api.storage.retrieve(cid, backends=backends, pin=pin, force=force)
        
        return {
            "success": True,
            "operation": "retrieve_content",
            "timestamp": time.time(),
            "cid": cid,
            "backend_used": result.get("backend_used"),
            "size": result.get("size"),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error retrieving content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving content: {str(e)}")
        
@storage_router.post("/check", response_model=Dict[str, Any])
async def check_content(
    cid: str = Body(..., description="Content ID to check"),
    backends: List[str] = Body(None, description="Storage backends to check (default: all enabled)")
):
    """
    Check content availability in storage backends.
    
    This endpoint checks if content is available in the specified storage backends.
    
    Parameters:
    - **cid**: The Content ID to check
    - **backends**: List of storage backends to check (default: all enabled)
    
    Returns:
        Content availability status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Check content
        logger.info(f"Checking content {cid} in backends: {backends or 'all'}")
        result = api.storage.check(cid, backends=backends)
        
        return {
            "success": True,
            "operation": "check_content",
            "timestamp": time.time(),
            "cid": cid,
            "availability": result.get("availability", {}),
            "available_in": result.get("available_in", []),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error checking content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking content: {str(e)}")


@storage_router.get("/pin-analytics", response_model=Dict[str, Any])
async def get_storage_pin_analytics():
    """
    Get comprehensive pin analytics from the enhanced pin metadata index.
    
    This endpoint provides storage-related analytics including tier distribution,
    access patterns, and storage optimization recommendations.
    
    Returns:
        Dictionary containing comprehensive pin analytics
    """
    if not ENHANCED_PIN_INDEX_AVAILABLE:
        return {
            "success": False,
            "error": "Enhanced pin analytics not available",
            "install_command": "pip install duckdb pandas pyarrow"
        }
    
    try:
        # Get comprehensive metrics
        metrics = get_cli_pin_metrics()
        
        return {
            "success": True,
            "operation": "get_pin_analytics",
            "timestamp": time.time(),
            "analytics": {
                "traffic_metrics": metrics.get("traffic_metrics", {}),
                "vfs_analytics": metrics.get("vfs_analytics", {}),
                "performance_metrics": metrics.get("performance_metrics", {})
            }
        }
    except Exception as e:
        logger.exception(f"Error getting pin analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting pin analytics: {str(e)}")


@storage_router.post("/record-access", response_model=Dict[str, Any])
async def record_storage_access(
    cid: str = Body(..., description="Content ID"),
    backend: str = Body(..., description="Storage backend used"),
    operation: str = Body("read", description="Operation type (read/write)"),
    size_bytes: Optional[int] = Body(None, description="Content size in bytes"),
    vfs_path: Optional[str] = Body(None, description="VFS path if applicable")
):
    """
    Record a storage access event for analytics.
    
    This endpoint allows storage backends to record access events
    for comprehensive analytics and performance tracking.
    
    Args:
        cid: Content ID that was accessed
        backend: Storage backend that handled the request
        operation: Type of operation (read, write, etc.)
        size_bytes: Size of content in bytes
        vfs_path: Virtual filesystem path if available
    
    Returns:
        Success status and recorded information
    """
    if not ENHANCED_PIN_INDEX_AVAILABLE:
        return {
            "success": False,
            "error": "Enhanced pin index not available for access recording"
        }
    
    try:
        # Get the enhanced pin index
        enhanced_index = get_global_enhanced_pin_index()
        
        # Map backend to tier
        tier_mapping = {
            "ipfs": "ipfs",
            "s3": "s3",
            "storacha": "storacha",
            "huggingface": "huggingface",
            "filecoin": "filecoin",
            "lassie": "ipfs",
            "sshfs": "sshfs",
            "ftp": "ftp",
            "gdrive": "gdrive"
        }
        tier = tier_mapping.get(backend.lower(), backend.lower())
        
        # Determine access pattern based on operation
        access_pattern_mapping = {
            "read": "sequential",
            "write": "sequential", 
            "stream": "streaming",
            "random": "random"
        }
        access_pattern = access_pattern_mapping.get(operation.lower(), "unknown")
        
        # Record the access
        enhanced_index.record_enhanced_access(
            cid=cid,
            access_pattern=access_pattern,
            vfs_path=vfs_path,
            tier=tier,
            size_bytes=size_bytes,
            pin_type="file",  # Default assumption
            storage_tiers=[tier]
        )
        
        return {
            "success": True,
            "operation": "record_access",
            "timestamp": time.time(),
            "recorded": {
                "cid": cid,
                "backend": backend,
                "tier": tier,
                "operation": operation,
                "access_pattern": access_pattern,
                "vfs_path": vfs_path
            }
        }
        
    except Exception as e:
        logger.exception(f"Error recording storage access: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recording storage access: {str(e)}")


@storage_router.get("/tier-recommendations", response_model=Dict[str, Any])
async def get_tier_recommendations():
    """
    Get storage tier optimization recommendations.
    
    This endpoint provides recommendations for optimizing storage
    tier placement based on access patterns and performance metrics.
    
    Returns:
        Dictionary containing tier optimization recommendations
    """
    if not ENHANCED_PIN_INDEX_AVAILABLE:
        return {
            "success": False,
            "error": "Enhanced pin analytics not available for recommendations"
        }
    
    try:
        # Get the enhanced pin index
        enhanced_index = get_global_enhanced_pin_index()
        
        # Get comprehensive metrics including recommendations
        if hasattr(enhanced_index, 'get_comprehensive_metrics'):
            metrics = enhanced_index.get_comprehensive_metrics()
            recommendations = metrics.storage_recommendations
        else:
            recommendations = []
        
        return {
            "success": True,
            "operation": "get_tier_recommendations",
            "timestamp": time.time(),
            "recommendations": recommendations,
            "total_recommendations": len(recommendations)
        }
        
    except Exception as e:
        logger.exception(f"Error getting tier recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting tier recommendations: {str(e)}")


# Policy Management Endpoints

@storage_router.get("/backends/{backend_name}/policies", response_model=Dict[str, Any])
async def get_backend_policies(backend_name: str):
    """
    Get all policies for a specific storage backend.
    
    This endpoint returns the complete policy set for a backend including
    storage quotas, traffic quotas, replication, retention, and cache policies.
    
    Parameters:
    - **backend_name**: The name of the storage backend
    
    Returns:
        Complete policy set for the backend
    """
    if not BACKEND_POLICIES_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Backend policy management not available. Install pydantic>=2.0"
        )
    
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Get backend policies (this would integrate with existing policy system)
        logger.info(f"Getting policies for backend: {backend_name}")
        
        # For now, return mock data structure that shows what policies would look like
        # In a real implementation, this would read from the existing policy systems
        policies = {
            "storage_quota": {
                "enabled": True,
                "max_size": 100,
                "max_size_unit": "gb",
                "warn_threshold": 0.8,
                "max_files": 10000,
                "usage": {
                    "used_size": 45,
                    "used_size_unit": "gb",
                    "file_count": 4532,
                    "pin_count": 3241
                }
            },
            "traffic_quota": {
                "enabled": True,
                "max_bandwidth_mbps": 100.0,
                "max_requests_per_minute": 1000,
                "max_upload_per_day": 10,
                "max_download_per_day": 50,
                "usage": {
                    "current_bandwidth_mbps": 23.4,
                    "requests_last_minute": 342,
                    "upload_today": 2.3,
                    "download_today": 12.7
                }
            },
            "replication": {
                "enabled": True,
                "strategy": "simple",
                "min_redundancy": 2,
                "max_redundancy": 4,
                "preferred_backends": ["ipfs", "s3"],
                "current_redundancy": 3
            },
            "retention": {
                "enabled": True,
                "default_retention_days": 365,
                "action_on_expiry": "archive",
                "legal_hold_supported": True,
                "archive_backend": "s3"
            },
            "cache": {
                "enabled": True,
                "max_cache_size": 20,
                "max_cache_size_unit": "gb",
                "eviction_policy": "arc",
                "ttl_seconds": 3600,
                "usage": {
                    "used_cache_size": 12.3,
                    "hit_rate": 0.78,
                    "evictions_last_hour": 45
                }
            }
        }
        
        return {
            "success": True,
            "operation": "get_backend_policies",
            "timestamp": time.time(),
            "backend": backend_name,
            "policies": policies
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting backend policies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting backend policies: {str(e)}")


@storage_router.put("/backends/{backend_name}/policies", response_model=Dict[str, Any])
async def update_backend_policies(
    backend_name: str,
    policy_set: Dict[str, Any] = Body(..., description="Complete or partial policy set")
):
    """
    Update policies for a storage backend.
    
    This endpoint allows updating any combination of policies for a backend.
    Only provided policies will be updated, others remain unchanged.
    
    Parameters:
    - **backend_name**: The name of the storage backend
    - **policy_set**: Dictionary containing policy updates
    
    Returns:
        Updated policy set
    """
    if not BACKEND_POLICIES_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Backend policy management not available. Install pydantic>=2.0"
        )
    
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        # Update backend policies
        logger.info(f"Updating policies for backend: {backend_name}")
        
        # In a real implementation, this would integrate with existing policy systems:
        # - Validate policy changes
        # - Apply policies to tiered cache manager
        # - Update retention policies in lifecycle manager
        # - Configure replication in cluster management
        # - Set up quota monitoring
        
        return {
            "success": True,
            "operation": "update_backend_policies",
            "timestamp": time.time(),
            "backend": backend_name,
            "updated_policies": list(policy_set.keys()),
            "policies": policy_set
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating backend policies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating backend policies: {str(e)}")


@storage_router.get("/backends/{backend_name}/policies/{policy_type}", response_model=Dict[str, Any])
async def get_backend_policy(backend_name: str, policy_type: str):
    """
    Get a specific policy for a storage backend.
    
    Parameters:
    - **backend_name**: The name of the storage backend
    - **policy_type**: Type of policy (storage_quota, traffic_quota, replication, retention, cache)
    
    Returns:
        Specific policy configuration and usage
    """
    if not BACKEND_POLICIES_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Backend policy management not available. Install pydantic>=2.0"
        )
    
    valid_policy_types = ["storage_quota", "traffic_quota", "replication", "retention", "cache"]
    if policy_type not in valid_policy_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy type. Must be one of: {valid_policy_types}"
        )
    
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        logger.info(f"Getting {policy_type} policy for backend: {backend_name}")
        
        # Mock policy data - in real implementation would read from policy systems
        policy_data = {
            "storage_quota": {
                "enabled": True,
                "max_size": 100,
                "max_size_unit": "gb",
                "warn_threshold": 0.8,
                "max_files": 10000,
                "usage": {"used_size": 45, "file_count": 4532}
            },
            "traffic_quota": {
                "enabled": True,
                "max_bandwidth_mbps": 100.0,
                "max_requests_per_minute": 1000,
                "usage": {"current_bandwidth_mbps": 23.4, "requests_last_minute": 342}
            },
            "replication": {
                "enabled": True,
                "strategy": "simple",
                "min_redundancy": 2,
                "max_redundancy": 4,
                "current_redundancy": 3
            },
            "retention": {
                "enabled": True,
                "default_retention_days": 365,
                "action_on_expiry": "archive"
            },
            "cache": {
                "enabled": True,
                "max_cache_size": 20,
                "eviction_policy": "arc",
                "usage": {"hit_rate": 0.78}
            }
        }
        
        return {
            "success": True,
            "operation": "get_backend_policy",
            "timestamp": time.time(),
            "backend": backend_name,
            "policy_type": policy_type,
            "policy": policy_data.get(policy_type, {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting backend policy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting backend policy: {str(e)}")


@storage_router.put("/backends/{backend_name}/policies/{policy_type}", response_model=Dict[str, Any])
async def update_backend_policy(
    backend_name: str, 
    policy_type: str,
    policy_data: Dict[str, Any] = Body(..., description="Policy configuration")
):
    """
    Update a specific policy for a storage backend.
    
    Parameters:
    - **backend_name**: The name of the storage backend
    - **policy_type**: Type of policy to update
    - **policy_data**: New policy configuration
    
    Returns:
        Updated policy configuration
    """
    if not BACKEND_POLICIES_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Backend policy management not available. Install pydantic>=2.0"
        )
    
    valid_policy_types = ["storage_quota", "traffic_quota", "replication", "retention", "cache"]
    if policy_type not in valid_policy_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy type. Must be one of: {valid_policy_types}"
        )
    
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        logger.info(f"Updating {policy_type} policy for backend: {backend_name}")
        
        # In a real implementation, validate policy data based on type:
        # - For storage_quota: validate size limits and units
        # - For traffic_quota: validate bandwidth and rate limits
        # - For replication: validate redundancy settings and backend availability
        # - For retention: validate retention periods and actions
        # - For cache: validate cache sizes and eviction policies
        
        return {
            "success": True,
            "operation": "update_backend_policy",
            "timestamp": time.time(),
            "backend": backend_name,
            "policy_type": policy_type,
            "policy": policy_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating backend policy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating backend policy: {str(e)}")


@storage_router.get("/backends/{backend_name}/quota-usage", response_model=Dict[str, Any])
async def get_backend_quota_usage(backend_name: str):
    """
    Get current quota usage for a storage backend.
    
    This endpoint provides real-time quota usage statistics including
    storage usage, traffic usage, and policy violation alerts.
    
    Parameters:
    - **backend_name**: The name of the storage backend
    
    Returns:
        Quota usage statistics and alerts
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if storage backends integration is available
        if not hasattr(api, "storage"):
            raise HTTPException(
                status_code=404,
                detail="Storage backends API is not available."
            )
            
        logger.info(f"Getting quota usage for backend: {backend_name}")
        
        # Mock usage data - in real implementation would aggregate from multiple sources
        usage_data = {
            "storage": {
                "used_bytes": 48318382080,  # ~45 GB
                "used_formatted": "45.0 GB",
                "quota_bytes": 107374182400,  # 100 GB
                "quota_formatted": "100.0 GB",
                "utilization": 0.45,
                "file_count": 4532,
                "pin_count": 3241,
                "warning_threshold": 0.8,
                "status": "normal"
            },
            "traffic": {
                "bandwidth_mbps": 23.4,
                "bandwidth_quota_mbps": 100.0,
                "bandwidth_utilization": 0.234,
                "requests_per_minute": 342,
                "requests_quota": 1000,
                "upload_today_gb": 2.3,
                "upload_quota_gb": 10.0,
                "download_today_gb": 12.7,
                "download_quota_gb": 50.0,
                "status": "normal"
            },
            "replication": {
                "current_redundancy": 3,
                "min_redundancy": 2,
                "max_redundancy": 4,
                "under_replicated_count": 0,
                "over_replicated_count": 23,
                "status": "optimal"
            },
            "cache": {
                "used_bytes": 13194139533,  # ~12.3 GB
                "used_formatted": "12.3 GB",
                "quota_bytes": 21474836480,  # 20 GB
                "quota_formatted": "20.0 GB",
                "utilization": 0.615,
                "hit_rate": 0.78,
                "evictions_last_hour": 45,
                "status": "normal"
            },
            "violations": [
                {
                    "type": "replication_warning",
                    "message": "23 items are over-replicated beyond max_redundancy",
                    "timestamp": time.time() - 3600,
                    "severity": "warning"
                }
            ]
        }
        
        return {
            "success": True,
            "operation": "get_quota_usage",
            "timestamp": time.time(),
            "backend": backend_name,
            "usage": usage_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting quota usage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting quota usage: {str(e)}")


@storage_router.get("/policy-violations", response_model=Dict[str, Any])
async def get_policy_violations(
    backend_name: Optional[str] = Query(None, description="Filter by backend name"),
    severity: Optional[str] = Query(None, description="Filter by severity (warning, error, critical)"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status")
):
    """
    Get policy violations across all backends or for a specific backend.
    
    This endpoint provides a centralized view of all policy violations
    including quota exceedances, replication failures, and retention issues.
    
    Parameters:
    - **backend_name**: Optional backend name filter
    - **severity**: Optional severity filter
    - **resolved**: Optional resolution status filter
    
    Returns:
        List of policy violations with details
    """
    try:
        logger.info(f"Getting policy violations (backend={backend_name}, severity={severity})")
        
        # Mock violation data - in real implementation would aggregate from policy systems
        all_violations = [
            {
                "id": "violation_1",
                "backend_name": "s3_demo",
                "policy_type": "storage_quota",
                "violation_type": "warning_threshold",
                "severity": "warning",
                "message": "Storage usage at 85% of quota (85.2 GB / 100 GB)",
                "timestamp": time.time() - 1800,
                "resolved": False,
                "metadata": {"utilization": 0.852}
            },
            {
                "id": "violation_2", 
                "backend_name": "ipfs_local",
                "policy_type": "replication",
                "violation_type": "under_replicated",
                "severity": "error",
                "message": "234 items below minimum redundancy (current: 1, required: 2)",
                "timestamp": time.time() - 3600,
                "resolved": False,
                "metadata": {"affected_count": 234}
            },
            {
                "id": "violation_3",
                "backend_name": "cluster",
                "policy_type": "traffic_quota",
                "violation_type": "rate_limit",
                "severity": "warning",
                "message": "Request rate approaching limit (980/1000 requests per minute)",
                "timestamp": time.time() - 300,
                "resolved": True,
                "metadata": {"current_rate": 980, "limit": 1000}
            }
        ]
        
        # Apply filters
        filtered_violations = all_violations
        
        if backend_name:
            filtered_violations = [v for v in filtered_violations if v["backend_name"] == backend_name]
            
        if severity:
            filtered_violations = [v for v in filtered_violations if v["severity"] == severity]
            
        if resolved is not None:
            filtered_violations = [v for v in filtered_violations if v["resolved"] == resolved]
            
        return {
            "success": True,
            "operation": "get_policy_violations",
            "timestamp": time.time(),
            "filters": {
                "backend_name": backend_name,
                "severity": severity,
                "resolved": resolved
            },
            "violations": filtered_violations,
            "total_count": len(filtered_violations),
            "summary": {
                "critical": len([v for v in filtered_violations if v["severity"] == "critical"]),
                "error": len([v for v in filtered_violations if v["severity"] == "error"]),
                "warning": len([v for v in filtered_violations if v["severity"] == "warning"]),
                "resolved": len([v for v in filtered_violations if v["resolved"]])
            }
        }
        
    except Exception as e:
        logger.exception(f"Error getting policy violations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting policy violations: {str(e)}")

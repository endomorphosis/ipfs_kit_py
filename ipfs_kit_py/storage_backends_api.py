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
                "status": backend_info.get("status", "unknown")
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
            "stats": backend_info.get("stats", {})
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

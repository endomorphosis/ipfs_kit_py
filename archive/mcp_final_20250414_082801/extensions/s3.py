"""
S3 extension integration with enhanced local storage.

This module integrates the enhanced S3 storage backend with the MCP server.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, HTTPException, Query

from enhanced_s3_storage import EnhancedS3Storage

# Import our enhanced S3 storage implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Configure logging
logger = logging.getLogger(__name__)

# Create S3 storage instance
s3_storage = EnhancedS3Storage()


def create_s3_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with S3 endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/s3")

    @router.get("/status")
    async def s3_status():
        """Get S3 storage backend status."""
        status = s3_storage.status()
        return status

    @router.post("/from_ipfs")
    async def s3_from_ipfs(cid: str = Form(...), key: Optional[str] = Form(None)):
        """
        Upload content from IPFS to S3.

        Args:
            cid: Content ID to upload
            key: Optional S3 object key
        """
        result = s3_storage.from_ipfs(cid, key)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.post("/to_ipfs")
    async def s3_to_ipfs(key: str = Form(...), cid: Optional[str] = Form(None)):
        """
        Upload content from S3 to IPFS.

        Args:
            key: S3 object key
            cid: Optional CID to assign (for verification)
        """
        result = s3_storage.to_ipfs(key, cid)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.get("/list")
    async def s3_list_objects(prefix: Optional[str] = Query(None), max_keys: int = Query(1000)):
        """
        List objects in the S3 bucket.

        Args:
            prefix: Optional prefix to filter objects
            max_keys: Maximum number of keys to return
        """
        result = s3_storage.list_objects(prefix, max_keys)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.post("/delete")
    async def s3_delete_object(key: str = Form(...)):
        """
        Delete an object from S3.

        Args:
            key: S3 object key
        """
        result = s3_storage.delete_object(key)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    return router


# Function to update storage_backends with actual status
def update_s3_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends dictionary with actual S3 status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    status = s3_storage.status()
    storage_backends["s3"] = {
        "available": status.get("available", False),
        "simulation": status.get("simulation", False),
        "message": status.get("message", ""),
        "error": status.get("error", None),
        "bucket": status.get("bucket", "unknown"),
        "region": status.get("region", "unknown"),
    }

    # Add local_mode flag if present
    if status.get("local_mode"):
        storage_backends["s3"]["local_mode"] = True

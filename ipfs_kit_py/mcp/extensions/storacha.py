"""
Enhanced endpoints for Storacha integration in the MCP server.

This module adds Storacha integration to the MCP server using the W3 Blob Protocol,
with proper implementation for the new endpoint structure.
"""

import logging
import os
import socket
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, HTTPException, Query

# Configure logging
logger = logging.getLogger(__name__)


def _check_dns_resolution(host):
    """Check if a hostname can be resolved via DNS."""
    try:
        socket.gethostbyname(host)
        return True
    except Exception as e:
        logger.warning(f"DNS resolution failed for {host}: {e}")
        return False


# Import our enhanced Storacha storage implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    # First try to import the enhanced version
    from enhanced_storacha_storage import (
        STORACHA_LIBRARIES_AVAILABLE,
    )
    from enhanced_storacha_storage import (
        EnhancedStorachaStorage as StorachaStorage,
    )

    logger.info("Using enhanced Storacha storage implementation with improved endpoint handling")
except ImportError:
    # Fall back to the standard version if enhanced is not available
    from storacha_storage import StorachaStorage

    logger.warning("Enhanced Storacha implementation not found, using standard version")

# Define a list of known working endpoints to try
STORACHA_ENDPOINTS = [
    "https://up.storacha.network/bridge",  # Primary endpoint
    "https://api.web3.storage",  # Legacy endpoint
    "https://api.storacha.network",  # Alternative endpoint
    "https://up.web3.storage/bridge",  # Yet another alternative
]

# Check if we have real Storacha API key
api_key = os.environ.get("STORACHA_API_KEY")
api_endpoint = os.environ.get("STORACHA_API_URL") or os.environ.get("STORACHA_API_ENDPOINT")

# Ensure we have a valid endpoint to try
if not api_endpoint:
    api_endpoint = STORACHA_ENDPOINTS[0]  # Use the primary endpoint as default

# Initialize storage with appropriate credentials
if api_key and not api_key.startswith("mock_"):
    logger.info(f"Using real Storacha API credentials with endpoint: {api_endpoint}")
    # Initialize with real credentials and all potential endpoints to try
    storacha_storage = StorachaStorage(api_key=api_key, api_endpoint=api_endpoint)
else:
    logger.info("No valid Storacha API credentials found, using mock implementation")
    # Will use mock mode automatically when no valid credentials are available
    storacha_storage = StorachaStorage()


def create_storacha_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with Storacha endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/storacha")

    @router.get("/status")
    async def storacha_status():
        """Get Storacha storage backend status."""
        status = storacha_storage.status()
        return status

    @router.post("/from_ipfs")
    async def storacha_from_ipfs(cid: str = Form(...), replication: int = Form(3)):
        """
        Store IPFS content on Storacha.

        Args:
            cid: Content ID to store
            replication: Replication factor
        """
        result = storacha_storage.from_ipfs(cid, replication)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Storacha backend is in simulation mode",
                    "instructions": "Set the STORACHA_API_KEY environment variable",
                    "configuration": "Set STORACHA_API_URL to override the default endpoint if needed",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.post("/to_ipfs")
    async def storacha_to_ipfs(storage_id: str = Form(...)):
        """
        Retrieve content from Storacha to IPFS.

        Args:
            storage_id: Storage ID for the content to retrieve
        """
        result = storacha_storage.to_ipfs(storage_id)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Storacha backend is in simulation mode",
                    "instructions": "Set the STORACHA_API_KEY environment variable",
                    "configuration": "Set STORACHA_API_URL to override the default endpoint if needed",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.get("/check_status/{storage_id}")
    async def storacha_check_status(storage_id: str):
        """
        Check the status of stored content.

        Args:
            storage_id: Storage ID to check
        """
        result = storacha_storage.check_status(storage_id)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Storacha backend is in simulation mode",
                    "instructions": "Set the STORACHA_API_KEY environment variable",
                    "configuration": "Set STORACHA_API_URL to override the default endpoint if needed",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    # New endpoints based on W3 Blob Protocol

    @router.get("/list_blobs")
    async def storacha_list_blobs(
        cursor: Optional[str] = Query(None), size: int = Query(100, gt=0, le=1000)
    ):
        """
        List blobs stored in Storacha.

        Args:
            cursor: Optional pagination cursor
            size: Maximum number of items to return
        """
        result = storacha_storage.list_blobs(cursor=cursor, size=size)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Storacha backend is in simulation mode",
                    "instructions": "Set the STORACHA_API_KEY environment variable",
                    "configuration": "Set STORACHA_API_URL to override the default endpoint if needed",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.get("/get_blob/{digest}")
    async def storacha_get_blob(digest: str):
        """
        Get information about a blob in Storacha.

        Args:
            digest: The multihash digest of the blob to get info for
        """
        result = storacha_storage.get_blob(digest)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Storacha backend is in simulation mode",
                    "instructions": "Set the STORACHA_API_KEY environment variable",
                    "configuration": "Set STORACHA_API_URL to override the default endpoint if needed",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.post("/remove_blob")
    async def storacha_remove_blob(digest: str = Form(...)):
        """
        Remove a blob from Storacha.

        Args:
            digest: The multihash digest of the blob to remove
        """
        result = storacha_storage.remove_blob(digest)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Storacha backend is in simulation mode",
                    "instructions": "Set the STORACHA_API_KEY environment variable",
                    "configuration": "Set STORACHA_API_URL to override the default endpoint if needed",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    return router


# Function to update storage_backends with actual status
def update_storacha_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends dictionary with actual Storacha status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    status = storacha_storage.status()

    # Create a more comprehensive status object
    storacha_status = {
        "available": True,  # We're always technically available since we fall back to mock mode
        "simulation": status.get("simulation", False),
        "mock": status.get("mock", False),
        "message": status.get("message", ""),
        "error": status.get("error", None),
    }

    # Add connection details when possible
    if "endpoint" in status:
        storacha_status["endpoint"] = status["endpoint"]

    # Add working endpoint info if available
    if hasattr(storacha_storage, "working_endpoint") and storacha_storage.working_endpoint:
        storacha_status["working_endpoint"] = storacha_storage.working_endpoint

    # Add service info if available
    if "service_info" in status:
        storacha_status["service_info"] = status["service_info"]

    # Add mock storage path if in mock mode
    if status.get("mock", False) and "mock_storage_path" in status:
        storacha_status["mock_storage_path"] = status["mock_storage_path"]
        if "mock_object_count" in status:
            storacha_status["mock_object_count"] = status["mock_object_count"]

    # Update the storage backends dictionary
    storage_backends["storacha"] = storacha_status

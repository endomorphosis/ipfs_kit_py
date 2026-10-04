"""
Enhanced Storacha integration for MCP server.

This module adds improved Storacha integration to the MCP server using the enhanced
storage implementation with robust endpoint management and fallback mechanisms.
"""

import logging
import os
import sys
from fastapi import APIRouter, HTTPException, Form
from typing import Dict, Any
from enhanced_storacha_storage import (

# Import our enhanced Storacha storage implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    EnhancedStorachaStorage)

# Configure logging
logger = logging.getLogger(__name__)

# Create enhanced Storacha storage instance
storacha_storage = EnhancedStorachaStorage()


def create_storacha_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with enhanced Storacha endpoints.

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
                    "instructions": "Install required libraries with: pip install requests",
                    "configuration": "Set STORACHA_API_KEY environment variable with your API key",
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
                    "instructions": "Install required libraries with: pip install requests",
                    "configuration": "Set STORACHA_API_KEY environment variable with your API key",
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
                    "instructions": "Install required libraries with: pip install requests",
                    "configuration": "Set STORACHA_API_KEY environment variable with your API key",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    # Add documentation to indicate that this is an enhanced implementation
    router.description = """
    Enhanced Storacha integration with robust endpoint management and fallback mechanisms.
    
    This module provides improved connection handling, automatic endpoint discovery,
    and graceful degradation to mock mode when real connections fail.
    """
    return router


# Function to update storage_backends with actual status
def update_storacha_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends dictionary with actual Storacha status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    status = storacha_storage.status()
    storage_backends["storacha"] = {
        "available": status.get("available", False),
        "simulation": status.get("simulation", False),
        "mock": status.get("mock", False),
        "message": status.get("message", ""),
        "error": status.get("error", None),
        "endpoint": status.get(,
            "endpoint",
            status.get("working_endpoint", status.get("fallback_endpoint", "")),
        ),
    }

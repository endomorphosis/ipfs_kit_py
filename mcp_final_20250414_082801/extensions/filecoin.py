"""
Enhanced endpoints for Filecoin integration in the MCP server.

This module adds Filecoin integration to the MCP server,
replacing the simulation with actual functionality.
"""

import logging
import os
import sys
from fastapi import APIRouter, HTTPException, Form
from typing import Optional, Dict, Any
from filecoin_storage import (

# Configure logging
logger = logging.getLogger(__name__)

# Import our Filecoin storage implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    FilecoinStorage)

# Import advanced Filecoin features
try:
    from advanced_filecoin_mcp import create_advanced_filecoin_router

    ADVANCED_FILECOIN_AVAILABLE = True
    logger.info("Advanced Filecoin features are available")
except ImportError:
    ADVANCED_FILECOIN_AVAILABLE = False
    logger.warning("Advanced Filecoin features not available. Install with: pip install -e .")

# Create Filecoin storage instance that uses real implementation if available
# Otherwise, it will automatically fall back to mock mode
# Remove the forced mock mode to allow real implementation when possible
if "MCP_USE_FILECOIN_MOCK" in os.environ:
    del os.environ["MCP_USE_FILECOIN_MOCK"]

# Check if we have real Filecoin API credentials
api_endpoint = os.environ.get("FILECOIN_API_URL") or os.environ.get("LOTUS_API_ENDPOINT")
api_token = os.environ.get("FILECOIN_API_TOKEN") or os.environ.get("LOTUS_API_TOKEN")

if api_endpoint and api_token and not (api_token.startswith("mock_")):
    logger.info("Using real Filecoin API credentials")
    # Initialize with real credentials
    filecoin_storage = FilecoinStorage(api_endpoint=api_endpoint, api_token=api_token)
else:
    logger.info("No valid Filecoin API credentials found, using mock implementation")
    # Will use mock mode automatically when no credentials are available
    filecoin_storage = FilecoinStorage()


def create_filecoin_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with Filecoin endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    # Create a parent router that will include both basic and advanced features
    router = APIRouter(prefix=f"{api_prefix}/filecoin")

    # Basic Filecoin endpoints
    @router.get("/status")
    async def filecoin_status():
        """Get Filecoin storage backend status."""
        status = filecoin_storage.status()
        return status

    @router.post("/from_ipfs")
    async def filecoin_from_ipfs(
        cid: str = Form(...),
        miner: Optional[str] = Form(None),
        duration: int = Form(518400),
    ):
        """
        Store IPFS content on Filecoin.

        Args:
            cid: Content ID to store
            miner: Optional miner address to use for storage deal
            duration: Deal duration in epochs (default 518400 = ~180 days)
        """
        result = filecoin_storage.from_ipfs(cid, miner, duration)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False
                    "error": "Filecoin backend is in simulation mode",
                    "instructions": "Install Lotus client and set the required environment variables",
                    "configuration": "Set LOTUS_API_ENDPOINT and LOTUS_API_TOKEN environment variables",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.post("/to_ipfs")
    async def filecoin_to_ipfs(deal_id: str = Form(...)):
        """
        Retrieve content from Filecoin to IPFS.

        Args:
            deal_id: Deal ID for the content to retrieve
        """
        result = filecoin_storage.to_ipfs(deal_id)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False
                    "error": "Filecoin backend is in simulation mode",
                    "instructions": "Install Lotus client and set the required environment variables",
                    "configuration": "Set LOTUS_API_ENDPOINT and LOTUS_API_TOKEN environment variables",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.get("/check_deal/{deal_id}")
    async def filecoin_check_deal(deal_id: str):
        """
        Check the status of a storage deal.

        Args:
            deal_id: Deal ID to check
        """
        result = filecoin_storage.check_deal_status(deal_id)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False
                    "error": "Filecoin backend is in simulation mode",
                    "instructions": "Install Lotus client and set the required environment variables",
                    "configuration": "Set LOTUS_API_ENDPOINT and LOTUS_API_TOKEN environment variables",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    # Add advanced Filecoin features if available
    if ADVANCED_FILECOIN_AVAILABLE:
        try:
            # Create a separate router for advanced features
            advanced_router = create_advanced_filecoin_router(api_prefix)
            logger.info("Advanced Filecoin features router created")

            # Return both routers as a list
            return [router, advanced_router]
        except Exception as e:
            logger.error(f"Error adding advanced Filecoin features: {e}")

    # If advanced features not available or error occurred, return just the basic router
    return router


# Function to update storage_backends with actual status
def update_filecoin_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends dictionary with actual Filecoin status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    status = filecoin_storage.status()
    storage_backends["filecoin"] = {
        "available": status.get("available", False),
        "simulation": status.get("simulation", True),
        "gateway": status.get("gateway", False),
        "message": (
            status.get("message", "Connected to Filecoin network via gateway")
            if status.get("gateway", False)
            else status.get("message", "")
        ),
        "error": status.get("error", None),
        "node_connection": status.get("node_connection", "unknown"),
    }

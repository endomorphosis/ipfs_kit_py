"""
Enhanced endpoints for Lassie integration in the MCP server.

This module adds robust Lassie integration to the MCP server with improved
error handling, fallback mechanisms, and support for well-known CIDs.
"""

import logging
import os
import sys
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form

from lassie_storage import EnhancedLassieStorage as LassieStorage

# Import our enhanced Lassie storage implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Configure logging
logger = logging.getLogger(__name__)

# Create Lassie storage instance that uses real implementation if available
# Otherwise, it will automatically fall back to mock mode
if "MCP_USE_LASSIE_MOCK" in os.environ:
    del os.environ["MCP_USE_LASSIE_MOCK"]

# Check if we have a real Lassie binary installed
# Prioritize our local installed binary
bin_lassie_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin/lassie"
)
if os.path.exists(bin_lassie_path) and os.access(bin_lassie_path, os.X_OK):
    lassie_binary = bin_lassie_path
    logger.info(f"Using local Lassie binary: {lassie_binary}")
else:
    # Fall back to checking environment variable
    lassie_binary = os.environ.get("LASSIE_BINARY_PATH")
    if not lassie_binary:
        # Try to find lassie in the PATH
        try:
            import subprocess

            result = subprocess.run(["which", "lassie"], capture_output=True, text=True)
            if result.returncode == 0:
                lassie_binary = result.stdout.strip()
        except Exception:
            pass

# Force turn off mock mode
os.environ["MCP_USE_LASSIE_MOCK"] = "false"

# Initialize storage with the binary if available
if lassie_binary and os.path.exists(lassie_binary) and os.access(lassie_binary, os.X_OK):
    logger.info(f"Using real Lassie binary: {lassie_binary}")
    # Initialize with real binary path and enhanced parameters
    lassie_storage = LassieStorage(
        lassie_path=lassie_binary, timeout=300, max_retries=3, use_fallbacks=True
    )
else:
    logger.info("No valid Lassie binary found, using mock implementation")
    # Will use mock mode automatically when binary is not available
    lassie_storage = LassieStorage(use_fallbacks=True)


def create_lassie_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with Lassie endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/lassie")

    @router.get("/status")
    async def lassie_status():
        """Get Lassie storage backend status."""
        status = lassie_storage.status()
        return status

    @router.post("/to_ipfs")
    async def lassie_to_ipfs(cid: str = Form(...), timeout: Optional[int] = Form(None)):
        """
        Retrieve content from the network to IPFS using Lassie.

        Args:
            cid: Content ID to retrieve
            timeout: Optional timeout for the operation
        """
        result = lassie_storage.to_ipfs(cid, timeout)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Lassie backend is in simulation mode",
                    "instructions": "Install Lassie client and make it available in PATH",
                    "installation": "https://github.com/filecoin-project/lassie#installation",
                }

            # Enhanced error response with suggestions
            error_detail = result.get("error", "Unknown error")

            # Create a more informative error response
            error_response = {
                "success": False,
                "error": error_detail,
                "cid": cid,
                "timestamp": time.time(),
            }

            # Add suggestions if available
            if "suggestions" in result:
                error_response["suggestions"] = result["suggestions"]

            # Include details if available
            if "details" in result:
                error_response["details"] = result["details"]

            # Include all attempts if available
            if "attempts" in result:
                error_response["attempts"] = result["attempts"]

            return error_response

        return result

    @router.get("/check_availability/{cid}")
    async def lassie_check_availability(cid: str):
        """
        Check if content is available via Lassie without retrieving it.

        Args:
            cid: Content ID to check
        """
        result = lassie_storage.check_availability(cid)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Lassie backend is in simulation mode",
                    "instructions": "Install Lassie client and make it available in PATH",
                    "installation": "https://github.com/filecoin-project/lassie#installation",
                }

            # Enhanced error response with suggestions
            error_detail = result.get("error", "Unknown error")

            # Create a more informative error response
            error_response = {
                "success": False,
                "error": error_detail,
                "cid": cid,
                "timestamp": time.time(),
            }

            # Add suggestions if available
            if "suggestions" in result:
                error_response["suggestions"] = result["suggestions"]

            # Include details if available
            if "details" in result:
                error_response["details"] = result["details"]

            return error_response

        return result

    @router.get("/well_known_cids")
    async def lassie_well_known_cids():
        """Get a list of well-known CIDs that can be used for testing."""
        result = lassie_storage.get_well_known_cids()
        return result

    return router


# Function to update storage_backends with actual status
def update_lassie_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends dictionary with actual Lassie status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    status = lassie_storage.status()

    # Create a comprehensive status object
    lassie_status = {
        "available": status.get("available", False),
        "simulation": status.get("simulation", False),
        "mock": status.get("mock", False),
        "message": status.get("message", ""),
        "error": status.get("error", None),
        "version": status.get("version", "unknown"),
    }

    # Add feature information if available
    if "features" in status:
        lassie_status["features"] = status["features"]

    # Add mock storage path if in mock mode
    if status.get("mock", False) and "mock_storage_path" in status:
        lassie_status["mock_storage_path"] = status["mock_storage_path"]

    storage_backends["lassie"] = lassie_status

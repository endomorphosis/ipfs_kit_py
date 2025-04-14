"""
Enhanced endpoints for HuggingFace integration in the robust MCP server.

This module adds HuggingFace integration to the existing robust MCP server,
replacing the simulation with actual functionality.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, HTTPException

from huggingface_storage import HuggingFaceStorage

# Import our HuggingFace storage implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Configure logging
logger = logging.getLogger(__name__)

# Create HuggingFace storage instance
huggingface_storage = HuggingFaceStorage()


def create_huggingface_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with HuggingFace endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/huggingface")

    @router.get("/status")
    async def huggingface_status():
        """Get HuggingFace storage backend status."""
        status = huggingface_storage.status()
        return status

    @router.post("/from_ipfs")
    async def huggingface_from_ipfs(cid: str = Form(...), path: Optional[str] = Form(None)):
        """
        Upload content from IPFS to HuggingFace.

        Args:
            cid: Content ID to upload
            path: Optional path within repository
        """
        result = huggingface_storage.from_ipfs(cid, path)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "HuggingFace backend is in simulation mode",
                    "instructions": "Install HuggingFace Hub SDK with: pip install huggingface_hub",
                    "configuration": "Set HUGGINGFACE_TOKEN environment variable with your API token",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.post("/to_ipfs")
    async def huggingface_to_ipfs(file_path: str = Form(...), cid: Optional[str] = Form(None)):
        """
        Upload content from HuggingFace to IPFS.

        Args:
            file_path: Path to file on HuggingFace
            cid: Optional CID to assign (for verification)
        """
        result = huggingface_storage.to_ipfs(file_path, cid)
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "HuggingFace backend is in simulation mode",
                    "instructions": "Install HuggingFace Hub SDK with: pip install huggingface_hub",
                    "configuration": "Set HUGGINGFACE_TOKEN environment variable with your API token",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    @router.get("/list")
    async def huggingface_list_files():
        """List files in the HuggingFace repository."""
        result = huggingface_storage.list_files()
        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "HuggingFace backend is in simulation mode",
                    "instructions": "Install HuggingFace Hub SDK with: pip install huggingface_hub",
                    "configuration": "Set HUGGINGFACE_TOKEN environment variable with your API token",
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    return router


# Function to update storage_backends with actual status
def update_huggingface_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends dictionary with actual HuggingFace status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    status = huggingface_storage.status()
    storage_backends["huggingface"] = {
        "available": status.get("available", False),
        "simulation": status.get("simulation", True),
        "message": status.get("message", ""),
        "error": status.get("error", None),
    }

"""
Lassie Controller for the MCP server.

This controller handles HTTP requests related to Lassie operations and
delegates the business logic to the Lassie model. Lassie is a tool for
retrieving content from the Filecoin/IPFS networks.
"""

import logging
import time
import os
import sys
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
import mcp_error_handling

# Configure logger
logger = logging.getLogger(__name__)

# Define Pydantic models for requests and responses
class FetchCIDRequest(BaseModel):
    """Request model for Lassie CID fetch operations."""
    cid: str = Field(..., description="Content Identifier (CID) to fetch")
    timeout_seconds: Optional[int] = Field(300, description="Timeout in seconds")
    output_dir: Optional[str] = Field(None, description="Directory to save fetched content")
    verbose: Optional[bool] = Field(False, description="Enable verbose logging")

class FetchRequest(BaseModel):
    """Request model for Lassie fetch operations."""
    cid: str = Field(..., description="Content Identifier (CID) to fetch")
    timeout_seconds: Optional[int] = Field(300, description="Timeout in seconds")
    output_dir: Optional[str] = Field(None, description="Directory to save fetched content")
    verbose: Optional[bool] = Field(False, description="Enable verbose logging")

class StatusRequest(BaseModel):
    """Request model for Lassie status operations."""
    cid: str = Field(..., description="Content Identifier (CID) to check status for")

class LassieResponse(BaseModel):
    """Base response model for Lassie operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    cid: str = Field(..., description="Content Identifier (CID)")

class FetchResponse(LassieResponse):
    """Response model for Lassie fetch operations."""
    size_bytes: Optional[int] = Field(None, description="Size of the fetched content in bytes")
    duration_ms: Optional[int] = Field(None, description="Duration of the fetch operation in milliseconds")
    output_path: Optional[str] = Field(None, description="Path where content was saved")

class StatusResponse(LassieResponse):
    """Response model for Lassie status operations."""
    status: str = Field(..., description="Status of the content retrieval")
    progress_percent: Optional[float] = Field(None, description="Progress percentage")
    bytes_received: Optional[int] = Field(None, description="Number of bytes received")
    peers: Optional[List[str]] = Field(None, description="Peers serving the content")

class LassieController:
    """
    Controller for Lassie operations.

    Handles HTTP requests related to Lassie operations and
    delegates the business logic to the Lassie model.
    """
    def __init__(self, lassie_model):
        """
        Initialize the Lassie controller.

        Args:
            lassie_model: Lassie model to use for operations
        """
        self.lassie_model = lassie_model
        logger.info("Lassie Controller initialized")

    def register_routes(self, router: APIRouter, prefix: str = ""):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Fetch content
        router.add_api_route(
            "/fetch",
            self.fetch_content,
            methods=["POST"],
            response_model=FetchResponse,
            summary="Fetch content using Lassie",
            description="Fetch content from the Filecoin/IPFS networks using Lassie"
        )

        # Check status
        router.add_api_route(
            "/status",
            self.check_status,
            methods=["POST"],
            response_model=StatusResponse,
            summary="Check Lassie retrieval status",
            description="Check the status of content retrieval using Lassie"
        )

        logger.info("Lassie Controller routes registered")

    async def fetch_content(self, request: FetchRequest) -> Dict[str, Any]:
        """
        Fetch content using Lassie.

        Args:
            request: Fetch request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Fetching content for CID: {request.cid}")
            start_time = time.time()

            # Call the model's fetch_content method
            result = self.lassie_model.fetch_content(
                cid=request.cid,
                timeout_seconds=request.timeout_seconds,
                output_dir=request.output_dir,
                verbose=request.verbose
            )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error fetching content: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "cid": request.cid,
                    "message": "Content retrieval failed"
                }

            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "success": True,
                "message": "Content fetched successfully",
                "cid": request.cid,
                "size_bytes": result.get("size_bytes"),
                "duration_ms": elapsed_ms,
                "output_path": result.get("output_path")
            }

        except Exception as e:
            logger.error(f"Error fetching content: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": request.cid,
                "message": "Content retrieval failed due to an internal error"
            }

    async def check_status(self, request: StatusRequest) -> Dict[str, Any]:
        """
        Check Lassie retrieval status.

        Args:
            request: Status request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Checking status for CID: {request.cid}")

            # Call the model's check_status method
            result = self.lassie_model.check_status(
                cid=request.cid
            )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error checking status: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "cid": request.cid,
                    "message": "Status check failed"
                }

            return {
                "success": True,
                "message": "Status retrieved successfully",
                "cid": request.cid,
                "status": result.get("status", "unknown"),
                "progress_percent": result.get("progress_percent"),
                "bytes_received": result.get("bytes_received"),
                "peers": result.get("peers", [])
            }

        except Exception as e:
            logger.error(f"Error checking status: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": request.cid,
                "message": "Status check failed due to an internal error"
            }

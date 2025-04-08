"""
IPFS Controller for the MCP server.

This controller handles HTTP requests related to IPFS operations and
delegates the business logic to the IPFS model.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile, Form, Response

# Import Pydantic models for request/response validation
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

# Define Pydantic models for requests and responses
class ContentRequest(BaseModel):
    """Request model for adding content."""
    content: str = Field(..., description="Content to add to IPFS")
    filename: Optional[str] = Field(None, description="Optional filename for the content")

class CIDRequest(BaseModel):
    """Request model for operations using a CID."""
    cid: str = Field(..., description="Content Identifier (CID)")

class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: str = Field(..., description="Unique identifier for this operation")
    duration_ms: float = Field(..., description="Duration of the operation in milliseconds")

class AddContentResponse(OperationResponse):
    """Response model for adding content."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID) of the added content")
    Hash: Optional[str] = Field(None, description="Legacy Hash field for compatibility")
    content_size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")

class GetContentResponse(OperationResponse):
    """Response model for getting content."""
    cid: str = Field(..., description="Content Identifier (CID) of the content")
    data: Optional[bytes] = Field(None, description="Content data")
    content_size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")
    cache_hit: Optional[bool] = Field(None, description="Whether the content was retrieved from cache")

class PinResponse(OperationResponse):
    """Response model for pin operations."""
    cid: str = Field(..., description="Content Identifier (CID) of the pinned content")
    pinned: Optional[bool] = Field(None, description="Whether the content is now pinned")

class ListPinsResponse(OperationResponse):
    """Response model for listing pins."""
    pins: Optional[List[Dict[str, Any]]] = Field(None, description="List of pinned content")
    count: Optional[int] = Field(None, description="Number of pinned items")

class StatsResponse(BaseModel):
    """Response model for operation statistics."""
    operation_stats: Dict[str, Any] = Field(..., description="Operation statistics")
    timestamp: float = Field(..., description="Timestamp of the statistics")


class IPFSController:
    """
    Controller for IPFS operations.
    
    Handles HTTP requests related to IPFS operations and delegates
    the business logic to the IPFS model.
    """
    
    def __init__(self, ipfs_model):
        """
        Initialize the IPFS controller.
        
        Args:
            ipfs_model: IPFS model to use for operations
        """
        self.ipfs_model = ipfs_model
        logger.info("IPFS Controller initialized")
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Add content routes
        router.add_api_route(
            "/ipfs/add",
            self.add_content,
            methods=["POST"],
            response_model=AddContentResponse,
            summary="Add content to IPFS",
            description="Add content to IPFS and return the CID"
        )
        
        router.add_api_route(
            "/ipfs/add/file",
            self.add_file,
            methods=["POST"],
            response_model=AddContentResponse,
            summary="Add a file to IPFS",
            description="Upload a file to IPFS and return the CID"
        )
        
        # Get content routes
        router.add_api_route(
            "/ipfs/cat/{cid}",
            self.get_content,
            methods=["GET"],
            response_class=Response,  # Raw response for content
            summary="Get content from IPFS",
            description="Get content from IPFS by CID and return as raw response"
        )
        
        router.add_api_route(
            "/ipfs/cat",
            self.get_content_json,
            methods=["POST"],
            response_model=GetContentResponse,
            summary="Get content from IPFS (JSON)",
            description="Get content from IPFS by CID and return as JSON"
        )
        
        # Pin management routes
        router.add_api_route(
            "/ipfs/pin/add",
            self.pin_content,
            methods=["POST"],
            response_model=PinResponse,
            summary="Pin content to IPFS",
            description="Pin content to local IPFS node by CID"
        )
        
        router.add_api_route(
            "/ipfs/pin/rm",
            self.unpin_content,
            methods=["POST"],
            response_model=PinResponse,
            summary="Unpin content from IPFS",
            description="Unpin content from local IPFS node by CID"
        )
        
        router.add_api_route(
            "/ipfs/pin/ls",
            self.list_pins,
            methods=["GET"],
            response_model=ListPinsResponse,
            summary="List pinned content",
            description="List content pinned to local IPFS node"
        )
        
        # Statistics route
        router.add_api_route(
            "/ipfs/stats",
            self.get_stats,
            methods=["GET"],
            response_model=StatsResponse,
            summary="Get IPFS operation statistics",
            description="Get statistics about IPFS operations"
        )
        
        logger.info("IPFS Controller routes registered")
    
    async def add_content(self, content_request: ContentRequest) -> Dict[str, Any]:
        """
        Add content to IPFS.
        
        Args:
            content_request: Content to add
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Adding content to IPFS, size: {len(content_request.content)} bytes")
        result = self.ipfs_model.add_content(
            content=content_request.content,
            filename=content_request.filename
        )
        return result
    
    async def add_file(self, file: UploadFile = File(...)) -> Dict[str, Any]:
        """
        Add a file to IPFS.
        
        Args:
            file: File to upload
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Adding file to IPFS: {file.filename}")
        content = await file.read()
        result = self.ipfs_model.add_content(
            content=content,
            filename=file.filename
        )
        return result
    
    async def get_content(self, cid: str) -> Response:
        """
        Get content from IPFS by CID and return as raw response.
        
        Args:
            cid: Content Identifier
            
        Returns:
            Raw response with content
        """
        logger.debug(f"Getting content from IPFS: {cid}")
        result = self.ipfs_model.get_content(cid=cid)
        
        if not result.get("success", False):
            # Handle error
            error_msg = result.get("error", "Unknown error")
            raise HTTPException(status_code=404, detail=f"Content not found: {error_msg}")
        
        # Return raw content
        headers = {
            "X-IPFS-Path": f"/ipfs/{cid}",
            "X-Operation-ID": result.get("operation_id", "unknown"),
            "X-Operation-Duration-MS": str(result.get("duration_ms", 0)),
            "X-Cache-Hit": str(result.get("cache_hit", False)).lower()
        }
        
        return Response(
            content=result.get("data", b""),
            media_type="application/octet-stream",
            headers=headers
        )
    
    async def get_content_json(self, cid_request: CIDRequest) -> Dict[str, Any]:
        """
        Get content from IPFS by CID and return as JSON.
        
        Args:
            cid_request: Request with CID
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Getting content from IPFS (JSON): {cid_request.cid}")
        return self.ipfs_model.get_content(cid=cid_request.cid)
    
    async def pin_content(self, cid_request: CIDRequest) -> Dict[str, Any]:
        """
        Pin content to local IPFS node.
        
        Args:
            cid_request: Request with CID
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Pinning content: {cid_request.cid}")
        return self.ipfs_model.pin_content(cid=cid_request.cid)
    
    async def unpin_content(self, cid_request: CIDRequest) -> Dict[str, Any]:
        """
        Unpin content from local IPFS node.
        
        Args:
            cid_request: Request with CID
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Unpinning content: {cid_request.cid}")
        return self.ipfs_model.unpin_content(cid=cid_request.cid)
    
    async def list_pins(self) -> Dict[str, Any]:
        """
        List pinned content on local IPFS node.
        
        Returns:
            Dictionary with operation results
        """
        logger.debug("Listing pinned content")
        return self.ipfs_model.list_pins()
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about IPFS operations.
        
        Returns:
            Dictionary with operation statistics
        """
        logger.debug("Getting IPFS operation statistics")
        return self.ipfs_model.get_stats()
    
    def reset(self):
        """Reset the controller state."""
        logger.info("IPFS Controller state reset")
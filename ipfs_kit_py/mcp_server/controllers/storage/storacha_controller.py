"""
Storacha (Web3.Storage) Controller for the MCP server.

This controller handles HTTP requests related to Storacha (Web3.Storage) operations and
delegates the business logic to the Storacha model.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile, Form, Response, Query

# Import Pydantic models for request/response validation
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

# Define Pydantic models for requests and responses
class StorachaSpaceCreationRequest(BaseModel):
    """Request model for Storacha space creation."""
    name: Optional[str] = Field(None, description="Optional name for the space")

class StorachaSetSpaceRequest(BaseModel):
    """Request model for setting the current Storacha space."""
    space_did: str = Field(..., description="Space DID to use")

class StorachaUploadRequest(BaseModel):
    """Request model for Storacha upload operations."""
    file_path: str = Field(..., description="Local file path to upload")
    space_did: Optional[str] = Field(None, description="Optional space DID to use")

class StorachaUploadCarRequest(BaseModel):
    """Request model for Storacha CAR upload operations."""
    car_path: str = Field(..., description="Local path to CAR file")
    space_did: Optional[str] = Field(None, description="Optional space DID to use")

class StorachaDeleteRequest(BaseModel):
    """Request model for Storacha delete operations."""
    cid: str = Field(..., description="Content identifier to delete")
    space_did: Optional[str] = Field(None, description="Optional space DID to use")

class IPFSStorachaRequest(BaseModel):
    """Request model for IPFS to Storacha operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    space_did: Optional[str] = Field(None, description="Optional space DID to use")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")
    
class StorachaIPFSRequest(BaseModel):
    """Request model for Storacha to IPFS operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    space_did: Optional[str] = Field(None, description="Optional space DID to use")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")

class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    duration_ms: Optional[float] = Field(None, description="Duration of the operation in milliseconds")

class StorachaSpaceCreationResponse(OperationResponse):
    """Response model for Storacha space creation."""
    space_did: Optional[str] = Field(None, description="DID of the created space")
    name: Optional[str] = Field(None, description="Name of the space")
    email: Optional[str] = Field(None, description="Email associated with the space")
    type: Optional[str] = Field(None, description="Type of the space")
    space_info: Optional[Dict[str, Any]] = Field(None, description="Additional space information")

class StorachaListSpacesResponse(OperationResponse):
    """Response model for listing Storacha spaces."""
    spaces: Optional[List[Dict[str, Any]]] = Field(None, description="List of spaces")
    count: Optional[int] = Field(None, description="Number of spaces")

class StorachaSetSpaceResponse(OperationResponse):
    """Response model for setting the current Storacha space."""
    space_did: Optional[str] = Field(None, description="DID of the space")
    space_info: Optional[Dict[str, Any]] = Field(None, description="Additional space information")

class StorachaUploadResponse(OperationResponse):
    """Response model for Storacha upload operations."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID)")
    size_bytes: Optional[int] = Field(None, description="Size of the uploaded file in bytes")
    root_cid: Optional[str] = Field(None, description="Root CID of the upload")
    shard_size: Optional[int] = Field(None, description="Shard size in bytes")
    upload_id: Optional[str] = Field(None, description="Upload ID")
    space_did: Optional[str] = Field(None, description="DID of the space")

class StorachaUploadCarResponse(OperationResponse):
    """Response model for Storacha CAR upload operations."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID)")
    car_cid: Optional[str] = Field(None, description="CAR file CID")
    size_bytes: Optional[int] = Field(None, description="Size of the uploaded CAR file in bytes")
    root_cid: Optional[str] = Field(None, description="Root CID of the upload")
    shard_size: Optional[int] = Field(None, description="Shard size in bytes")
    upload_id: Optional[str] = Field(None, description="Upload ID")
    space_did: Optional[str] = Field(None, description="DID of the space")

class StorachaListUploadsResponse(OperationResponse):
    """Response model for listing Storacha uploads."""
    uploads: Optional[List[Dict[str, Any]]] = Field(None, description="List of uploads")
    count: Optional[int] = Field(None, description="Number of uploads")
    space_did: Optional[str] = Field(None, description="DID of the space")

class StorachaDeleteResponse(OperationResponse):
    """Response model for Storacha delete operations."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID)")
    space_did: Optional[str] = Field(None, description="DID of the space")

class IPFSStorachaResponse(OperationResponse):
    """Response model for IPFS to Storacha operations."""
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    storacha_cid: Optional[str] = Field(None, description="Content Identifier (CID) in Storacha")
    size_bytes: Optional[int] = Field(None, description="Size of the file in bytes")
    root_cid: Optional[str] = Field(None, description="Root CID of the upload")
    upload_id: Optional[str] = Field(None, description="Upload ID")
    space_did: Optional[str] = Field(None, description="DID of the space")
    
class StorachaIPFSResponse(OperationResponse):
    """Response model for Storacha to IPFS operations."""
    storacha_cid: Optional[str] = Field(None, description="Content Identifier (CID) in Storacha")
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    size_bytes: Optional[int] = Field(None, description="Size of the file in bytes")
    space_did: Optional[str] = Field(None, description="DID of the space")


class StorachaController:
    """
    Controller for Storacha (Web3.Storage) operations.
    
    Handles HTTP requests related to Storacha operations and delegates
    the business logic to the Storacha model.
    """
    
    def __init__(self, storacha_model):
        """
        Initialize the Storacha controller.
        
        Args:
            storacha_model: Storacha model to use for operations
        """
        self.storacha_model = storacha_model
        logger.info("Storacha Controller initialized")
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Space creation endpoint
        router.add_api_route(
            "/storacha/space/create",
            self.handle_space_creation_request,
            methods=["POST"],
            response_model=StorachaSpaceCreationResponse,
            summary="Create Storacha Space",
            description="Create a new storage space in Storacha (Web3.Storage)"
        )
        
        # List spaces endpoint
        router.add_api_route(
            "/storacha/space/list",
            self.handle_list_spaces_request,
            methods=["GET"],
            response_model=StorachaListSpacesResponse,
            summary="List Storacha Spaces",
            description="List all available storage spaces in Storacha (Web3.Storage)"
        )
        
        # Set current space endpoint
        router.add_api_route(
            "/storacha/space/set",
            self.handle_set_space_request,
            methods=["POST"],
            response_model=StorachaSetSpaceResponse,
            summary="Set Storacha Space",
            description="Set the current storage space in Storacha (Web3.Storage)"
        )
        
        # Upload file endpoint
        router.add_api_route(
            "/storacha/upload",
            self.handle_upload_request,
            methods=["POST"],
            response_model=StorachaUploadResponse,
            summary="Upload to Storacha",
            description="Upload a file to Storacha (Web3.Storage)"
        )
        
        # Upload CAR file endpoint
        router.add_api_route(
            "/storacha/upload/car",
            self.handle_upload_car_request,
            methods=["POST"],
            response_model=StorachaUploadCarResponse,
            summary="Upload CAR to Storacha",
            description="Upload a CAR file to Storacha (Web3.Storage)"
        )
        
        # List uploads endpoint
        router.add_api_route(
            "/storacha/uploads",
            self.handle_list_uploads_request,
            methods=["GET"],
            response_model=StorachaListUploadsResponse,
            summary="List Storacha Uploads",
            description="List uploads in a Storacha (Web3.Storage) space"
        )
        
        # Delete upload endpoint
        router.add_api_route(
            "/storacha/delete",
            self.handle_delete_request,
            methods=["POST"],
            response_model=StorachaDeleteResponse,
            summary="Delete from Storacha",
            description="Delete an upload from Storacha (Web3.Storage)"
        )
        
        # IPFS to Storacha endpoint
        router.add_api_route(
            "/storacha/from_ipfs",
            self.handle_ipfs_to_storacha_request,
            methods=["POST"],
            response_model=IPFSStorachaResponse,
            summary="IPFS to Storacha",
            description="Transfer content from IPFS to Storacha (Web3.Storage)"
        )
        
        # Storacha to IPFS endpoint
        router.add_api_route(
            "/storacha/to_ipfs",
            self.handle_storacha_to_ipfs_request,
            methods=["POST"],
            response_model=StorachaIPFSResponse,
            summary="Storacha to IPFS",
            description="Transfer content from Storacha (Web3.Storage) to IPFS"
        )
        
        # Status endpoint for testing
        router.add_api_route(
            "/storage/storacha/status",
            self.handle_status_request,
            methods=["GET"],
            response_model=OperationResponse,
            summary="Storacha Status",
            description="Get current status of the Storacha (Web3.Storage) backend"
        )
        
        logger.info("Storacha routes registered")
    
    async def handle_space_creation_request(self, request: StorachaSpaceCreationRequest):
        """
        Handle space creation request in Storacha.
        
        Args:
            request: Space creation request parameters
            
        Returns:
            Space creation response
        """
        # Delegate to Storacha model
        result = self.storacha_model.create_space(name=request.name)
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to create space"),
                    "error_type": result.get("error_type", "SpaceCreationError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_list_spaces_request(self):
        """
        Handle list spaces request in Storacha.
        
        Returns:
            List spaces response
        """
        # Delegate to Storacha model
        result = self.storacha_model.list_spaces()
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list spaces"),
                    "error_type": result.get("error_type", "ListSpacesError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_set_space_request(self, request: StorachaSetSpaceRequest):
        """
        Handle set current space request in Storacha.
        
        Args:
            request: Set space request parameters
            
        Returns:
            Set space response
        """
        # Delegate to Storacha model
        result = self.storacha_model.set_current_space(space_did=request.space_did)
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to set space"),
                    "error_type": result.get("error_type", "SetSpaceError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_upload_request(self, request: StorachaUploadRequest):
        """
        Handle upload request to Storacha.
        
        Args:
            request: Upload request parameters
            
        Returns:
            Upload response
        """
        # Delegate to Storacha model
        result = self.storacha_model.upload_file(
            file_path=request.file_path,
            space_did=request.space_did
        )
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to upload file"),
                    "error_type": result.get("error_type", "UploadError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_upload_car_request(self, request: StorachaUploadCarRequest):
        """
        Handle CAR upload request to Storacha.
        
        Args:
            request: CAR upload request parameters
            
        Returns:
            CAR upload response
        """
        # Delegate to Storacha model
        result = self.storacha_model.upload_car(
            car_path=request.car_path,
            space_did=request.space_did
        )
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to upload CAR file"),
                    "error_type": result.get("error_type", "UploadCarError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_list_uploads_request(self, space_did: Optional[str] = None):
        """
        Handle list uploads request in Storacha.
        
        Args:
            space_did: Optional space DID to use
            
        Returns:
            List uploads response
        """
        # Delegate to Storacha model
        result = self.storacha_model.list_uploads(space_did=space_did)
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list uploads"),
                    "error_type": result.get("error_type", "ListUploadsError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_delete_request(self, request: StorachaDeleteRequest):
        """
        Handle delete request in Storacha.
        
        Args:
            request: Delete request parameters
            
        Returns:
            Delete response
        """
        # Delegate to Storacha model
        result = self.storacha_model.delete_upload(
            cid=request.cid,
            space_did=request.space_did
        )
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to delete upload"),
                    "error_type": result.get("error_type", "DeleteUploadError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_ipfs_to_storacha_request(self, request: IPFSStorachaRequest):
        """
        Handle transfer from IPFS to Storacha.
        
        Args:
            request: IPFS to Storacha request parameters
            
        Returns:
            IPFS to Storacha response
        """
        # Delegate to Storacha model
        result = self.storacha_model.ipfs_to_storacha(
            cid=request.cid,
            space_did=request.space_did,
            pin=request.pin
        )
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to transfer content from IPFS to Storacha"),
                    "error_type": result.get("error_type", "IPFSToStorachaError")
                }
            )
        
        # Return successful response
        return result
    
    async def handle_storacha_to_ipfs_request(self, request: StorachaIPFSRequest):
        """
        Handle transfer from Storacha to IPFS.
        
        Args:
            request: Storacha to IPFS request parameters
            
        Returns:
            Storacha to IPFS response
        """
        # Delegate to Storacha model
        result = self.storacha_model.storacha_to_ipfs(
            cid=request.cid,
            space_did=request.space_did,
            pin=request.pin
        )
        
        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to transfer content from Storacha to IPFS"),
                    "error_type": result.get("error_type", "StorachaToIPFSError")
                }
            )
        
        # Return successful response
        return result
        
    async def handle_status_request(self):
        """
        Handle status request for Storacha backend.
        
        Returns:
            Status response
        """
        # Get stats from the model
        stats = self.storacha_model.get_stats()
        
        # Create response with status information
        return {
            "success": True,
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": 0,
            "is_available": True,
            "backend": "storacha",
            "stats": stats,
            "timestamp": time.time()
        }
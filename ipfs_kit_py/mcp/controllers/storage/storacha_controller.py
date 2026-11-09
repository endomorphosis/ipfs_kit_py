"""
Storacha (Web3.Storage) Controller for the MCP server.

This controller handles HTTP requests related to Storacha (Web3.Storage) operations and
delegates the business logic to the Storacha model.
"""

import logging
import time
import uuid
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import error handling
from ipfs_kit_py.mcp.mcp_error_handling import (
    StorageError,
    ValidationError,
    handle_exception
)

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
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata for the file")


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
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata for the file")


class StorachaIPFSRequest(BaseModel):
    """Request model for Storacha to IPFS operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    space_did: Optional[str] = Field(None, description="Optional space DID to use")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")


class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    duration_ms: Optional[float] = Field(
        None, description="Duration of the operation in milliseconds"
    )
    error: Optional[str] = Field(None, description="Error message if operation failed")
    error_type: Optional[str] = Field(None, description="Type of error if operation failed")


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
    total: Optional[int] = Field(None, description="Total number of uploads")
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


class StorachaStatusResponse(OperationResponse):
    """Response model for Storacha status."""
    is_available: bool = Field(..., description="Whether the Storacha service is available")
    backend: str = Field("storacha", description="Backend name")
    connection_status: Optional[Dict[str, Any]] = Field(None, description="Connection status details")
    timestamp: float = Field(..., description="Current timestamp")


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

    def register_routes(self, router: APIRouter, prefix: str = ""):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
            prefix: Optional URL prefix for all routes (default: "/storacha")
        """
        # Space creation endpoint
        router.add_api_route(
            f"{prefix}/space/create",
            self.handle_space_creation_request,
            methods=["POST"],
            response_model=StorachaSpaceCreationResponse,
            summary="Create Storacha Space",
            description="Create a new storage space in Storacha (Web3.Storage)",
        )

        # List spaces endpoint
        router.add_api_route(
            f"{prefix}/space/list",
            self.handle_list_spaces_request,
            methods=["GET"],
            response_model=StorachaListSpacesResponse,
            summary="List Storacha Spaces",
            description="List all available storage spaces in Storacha (Web3.Storage)",
        )

        # Set current space endpoint
        router.add_api_route(
            f"{prefix}/space/set",
            self.handle_set_space_request,
            methods=["POST"],
            response_model=StorachaSetSpaceResponse,
            summary="Set Storacha Space",
            description="Set the current storage space in Storacha (Web3.Storage)",
        )

        # Upload file endpoint
        router.add_api_route(
            f"{prefix}/upload",
            self.handle_upload_request,
            methods=["POST"],
            response_model=StorachaUploadResponse,
            summary="Upload to Storacha",
            description="Upload a file to Storacha (Web3.Storage)",
        )

        # Upload file via form endpoint (for direct uploads)
        router.add_api_route(
            f"{prefix}/upload/form",
            self.handle_form_upload_request,
            methods=["POST"],
            response_model=StorachaUploadResponse,
            summary="Upload to Storacha via Form",
            description="Upload a file to Storacha (Web3.Storage) using multipart form",
        )

        # Upload CAR file endpoint
        router.add_api_route(
            f"{prefix}/upload/car",
            self.handle_upload_car_request,
            methods=["POST"],
            response_model=StorachaUploadCarResponse,
            summary="Upload CAR to Storacha",
            description="Upload a CAR file to Storacha (Web3.Storage)",
        )

        # List uploads endpoint
        router.add_api_route(
            f"{prefix}/uploads",
            self.handle_list_uploads_request,
            methods=["GET"],
            response_model=StorachaListUploadsResponse,
            summary="List Storacha Uploads",
            description="List uploads in a Storacha (Web3.Storage) space",
        )

        # Delete upload endpoint
        router.add_api_route(
            f"{prefix}/delete",
            self.handle_delete_request,
            methods=["POST"],
            response_model=StorachaDeleteResponse,
            summary="Delete from Storacha",
            description="Delete an upload from Storacha (Web3.Storage)",
        )

        # IPFS to Storacha endpoint
        router.add_api_route(
            f"{prefix}/from_ipfs",
            self.handle_ipfs_to_storacha_request,
            methods=["POST"],
            response_model=IPFSStorachaResponse,
            summary="IPFS to Storacha",
            description="Transfer content from IPFS to Storacha (Web3.Storage)",
        )

        # Storacha to IPFS endpoint
        router.add_api_route(
            f"{prefix}/to_ipfs",
            self.handle_storacha_to_ipfs_request,
            methods=["POST"],
            response_model=StorachaIPFSResponse,
            summary="Storacha to IPFS",
            description="Transfer content from Storacha (Web3.Storage) to IPFS",
        )

        # Status endpoint for checking backend health and connection status
        router.add_api_route(
            f"{prefix}/status",
            self.handle_status_request,
            methods=["GET"],
            response_model=StorachaStatusResponse,
            summary="Storacha Status",
            description="Get current status of the Storacha (Web3.Storage) backend and connection metrics",
        )

        logger.info(f"Storacha routes registered with prefix {prefix}")

    async def handle_space_creation_request(self, request: StorachaSpaceCreationRequest):
        """
        Handle space creation request in Storacha.

        Args:
            request: Space creation request parameters

        Returns:
            Space creation response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.create_space(name=request.name)

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to create space"),
                    "error_type": result.get("error_type", "SpaceCreationError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"Space creation failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"space_create_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to create Storacha space")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_list_spaces_request(self):
        """
        Handle list spaces request in Storacha.

        Returns:
            List spaces response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.list_spaces()

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to list spaces"),
                    "error_type": result.get("error_type", "ListSpacesError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"Listing spaces failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"space_list_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to list Storacha spaces")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_set_space_request(self, request: StorachaSetSpaceRequest):
        """
        Handle set current space request in Storacha.

        Args:
            request: Set space request parameters

        Returns:
            Set space response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.set_current_space(space_did=request.space_did)

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to set space"),
                    "error_type": result.get("error_type", "SetSpaceError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"Setting space failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"space_set_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to set current Storacha space")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_upload_request(self, request: StorachaUploadRequest):
        """
        Handle upload request to Storacha.

        Args:
            request: Upload request parameters

        Returns:
            Upload response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.upload_file(
                file_path=request.file_path, 
                space_did=request.space_did,
                metadata=request.metadata
            )

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to upload file"),
                    "error_type": result.get("error_type", "UploadError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"File upload failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"upload_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to upload file to Storacha")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_form_upload_request(
        self, 
        file: UploadFile = File(...),
        space_did: Optional[str] = Form(None),
        metadata_json: Optional[str] = Form(None)
    ):
        """
        Handle direct file upload via multipart form.

        Args:
            file: Uploaded file
            space_did: Optional space DID
            metadata_json: Optional metadata as JSON string

        Returns:
            Upload response
        """
        import tempfile
        import os
        import json
        
        try:
            # Parse metadata if provided
            metadata = None
            if metadata_json:
                try:
                    metadata = json.loads(metadata_json)
                except json.JSONDecodeError:
                    raise ValidationError("Invalid metadata JSON format")
            
            # Create a temporary file to store the upload
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
                temp_path = temp_file.name
                
                try:
                    # Write uploaded file to temporary file
                    contents = await file.read()
                    temp_file.write(contents)
                    temp_file.flush()
                    
                    # Upload using the model
                    result = self.storacha_model.upload_file(
                        file_path=temp_path,
                        space_did=space_did,
                        metadata=metadata
                    )
                    
                    # If operation failed, raise HTTP exception
                    if not result.get("success", False):
                        error_detail = {
                            "error": result.get("error", "Failed to upload file"),
                            "error_type": result.get("error_type", "UploadError")
                        }
                        raise HTTPException(
                            status_code=result.get("status_code", 500),
                            detail=f"Form file upload failed: {error_detail.get('error')}" # Added context
                        ) # Removed extra parenthesis
                    
                    # Generate operation ID if not present
                    if "operation_id" not in result:
                        result["operation_id"] = f"upload_form_{uuid.uuid4()}"
                    
                    return result
                    
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file {temp_path}: {e}")
            
        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to upload file to Storacha")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_upload_car_request(self, request: StorachaUploadCarRequest):
        """
        Handle CAR upload request to Storacha.

        Args:
            request: CAR upload request parameters

        Returns:
            CAR upload response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.upload_car(
                car_path=request.car_path, space_did=request.space_did
            )

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to upload CAR file"),
                    "error_type": result.get("error_type", "UploadCarError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"CAR file upload failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"upload_car_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to upload CAR file to Storacha")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_list_uploads_request(
        self, 
        space_did: Optional[str] = None,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0)
    ):
        """
        Handle list uploads request in Storacha.

        Args:
            space_did: Optional space DID to use
            limit: Maximum number of items to return
            offset: Offset for pagination

        Returns:
            List uploads response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.list_uploads(
                space_did=space_did,
                limit=limit,
                offset=offset
            )

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to list uploads"),
                    "error_type": result.get("error_type", "ListUploadsError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"Listing uploads failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"list_uploads_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to list Storacha uploads")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_delete_request(self, request: StorachaDeleteRequest):
        """
        Handle delete request in Storacha.

        Args:
            request: Delete request parameters

        Returns:
            Delete response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.delete_upload(cid=request.cid, space_did=request.space_did)

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to delete upload"),
                    "error_type": result.get("error_type", "DeleteUploadError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"Deleting upload failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"delete_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to delete upload from Storacha")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_ipfs_to_storacha_request(self, request: IPFSStorachaRequest):
        """
        Handle transfer from IPFS to Storacha.

        Args:
            request: IPFS to Storacha request parameters

        Returns:
            IPFS to Storacha response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.ipfs_to_storacha(
                cid=request.cid, 
                space_did=request.space_did, 
                pin=request.pin,
                metadata=request.metadata
            )

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to transfer from IPFS to Storacha"),
                    "error_type": result.get("error_type", "IPFSToStorachaError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"IPFS to Storacha transfer failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"ipfs_to_storacha_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to transfer from IPFS to Storacha")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_storacha_to_ipfs_request(self, request: StorachaIPFSRequest):
        """
        Handle transfer from Storacha to IPFS.

        Args:
            request: Storacha to IPFS request parameters

        Returns:
            Storacha to IPFS response
        """
        try:
            # Delegate to Storacha model
            result = self.storacha_model.storacha_to_ipfs(
                cid=request.cid, space_did=request.space_did, pin=request.pin
            )

            # If operation failed, raise HTTP exception
            if not result.get("success", False):
                error_detail = {
                    "error": result.get("error", "Failed to transfer from Storacha to IPFS"),
                    "error_type": result.get("error_type", "StorachaToIPFSError")
                }
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=f"Storacha to IPFS transfer failed: {error_detail.get('error')}" # Added context
                ) # Removed extra parenthesis

            # Generate operation ID if not present
            if "operation_id" not in result:
                result["operation_id"] = f"storacha_to_ipfs_{uuid.uuid4()}"

            # Return successful response
            return result

        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to transfer from Storacha to IPFS")
            raise HTTPException(status_code=status_code, detail=error_response)

    async def handle_status_request(self):
        """
        Handle status request for Storacha backend.

        Returns:
            Status response with detailed connection information
        """
        try:
            # Check if the service is available
            is_available = self.storacha_model.is_available()
            
            # Get connection status if available
            connection_status = self.storacha_model.get_connection_status()
            
            # Create response
            return {
                "success": True,
                "operation_id": f"status-{int(time.time())}",
                "duration_ms": 0,
                "is_available": is_available,
                "backend": "storacha",
                "connection_status": connection_status,
                "timestamp": time.time(),
            }
            
        except Exception as e:
            # Handle unexpected errors
            error_response, status_code = handle_exception(e, "Failed to get Storacha status")
            raise HTTPException(status_code=status_code, detail=error_response)

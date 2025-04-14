"""
Storacha (Web3.Storage) Controller AnyIO Implementation for the MCP server.

This module provides asynchronous versions of the Storacha controller operations
using AnyIO for compatibility with both asyncio and trio async frameworks.
"""

import logging
import time
import uuid
import anyio
from typing import Dict, List, Any, Optional, Callable, Union, Awaitable
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends, Query

from ipfs_kit_py.mcp.controllers.storage.storacha_controller import (
    StorachaSpaceCreationRequest,
    StorachaSetSpaceRequest,
    StorachaUploadRequest,
    StorachaUploadCarRequest,
    StorachaDeleteRequest,
    IPFSStorachaRequest,
    StorachaIPFSRequest,
    StorachaSpaceCreationResponse,
    StorachaListSpacesResponse,
    StorachaSetSpaceResponse,
    StorachaUploadResponse,
    StorachaUploadCarResponse,
    StorachaListUploadsResponse,
    StorachaDeleteResponse,
    IPFSStorachaResponse,
    StorachaIPFSResponse,
    StorachaStatusResponse
)

# Import error handling
from ipfs_kit_py.mcp.mcp_error_handling import (
    StorageError,
    ValidationError,
    handle_exception
)

# Configure logger
logger = logging.getLogger(__name__)


class StorachaControllerAnyIO:
    """
    AnyIO-compatible controller for Storacha (Web3.Storage) operations.

    This class wraps the synchronous Storacha model with async operations
    for use with async web frameworks like FastAPI.
    """
    def __init__(self, storacha_model):
        """
        Initialize the async Storacha controller.

        Args:
            storacha_model: Storacha model to use for operations
        """
        self.storacha_model = storacha_model
        logger.info("Storacha AnyIO Controller initialized")

    def register_routes(self, router: APIRouter, prefix: str = "/storacha"):
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

        logger.info(f"Storacha AnyIO routes registered with prefix {prefix}")

    async def _run_in_threadpool(self, func: Callable, *args, **kwargs) -> Any:
        """
        Run a synchronous function in a threadpool and return the result.

        Args:
            func: Synchronous function to run
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            Result of the function call
        """
        # Use AnyIO to run the sync function in a thread pool
        return await anyio.to_thread.run_sync(lambda: func(*args, **kwargs))

    async def handle_space_creation_request(self, request: StorachaSpaceCreationRequest):
        """
        Handle space creation request in Storacha.

        Args:
            request: Space creation request parameters

        Returns:
            Space creation response
        """
        try:
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.create_space,
                name=request.name
            )

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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.list_spaces
            )

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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.set_current_space,
                space_did=request.space_did
            )

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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.upload_file,
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
                    
                    # Upload using the model (in a thread pool)
                    result = await self._run_in_threadpool(
                        self.storacha_model.upload_file,
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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.upload_car,
                car_path=request.car_path, 
                space_did=request.space_did
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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.list_uploads,
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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.delete_upload,
                cid=request.cid, 
                space_did=request.space_did
            )

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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.ipfs_to_storacha,
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
            # Run the synchronous model function in a thread pool
            result = await self._run_in_threadpool(
                self.storacha_model.storacha_to_ipfs,
                cid=request.cid, 
                space_did=request.space_did, 
                pin=request.pin
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
            # Run the synchronous model functions in a thread pool
            is_available = await self._run_in_threadpool(self.storacha_model.is_available)
            connection_status = await self._run_in_threadpool(self.storacha_model.get_connection_status)
            
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

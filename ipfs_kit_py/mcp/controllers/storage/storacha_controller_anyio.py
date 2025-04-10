"""
Storacha (Web3.Storage) Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to Storacha (Web3.Storage) operations and
delegates the business logic to the Storacha model, with support for both asyncio
and trio via the AnyIO library.
"""

import logging
import time
import warnings
import sniffio
from typing import Dict, List, Any, Optional

# AnyIO import
import anyio

# Import Pydantic models for request/response validation
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile, Form, Response, Query

# Import original controller for inheritance
from ipfs_kit_py.mcp.controllers.storage.storacha_controller import (
    StorachaController,
    StorachaSpaceCreationRequest,
    StorachaSetSpaceRequest,
    StorachaUploadRequest,
    StorachaUploadCarRequest,
    StorachaDeleteRequest,
    IPFSStorachaRequest,
    StorachaIPFSRequest,
    OperationResponse,
    StorachaSpaceCreationResponse,
    StorachaListSpacesResponse,
    StorachaSetSpaceResponse,
    StorachaUploadResponse,
    StorachaUploadCarResponse,
    StorachaListUploadsResponse,
    StorachaDeleteResponse,
    IPFSStorachaResponse,
    StorachaIPFSResponse
)

# Configure logger
logger = logging.getLogger(__name__)

class StorachaControllerAnyIO(StorachaController):
    """
    Controller for Storacha (Web3.Storage) operations with AnyIO support.
    
    Handles HTTP requests related to Storacha operations and delegates
    the business logic to the Storacha model, supporting both asyncio
    and trio backends through AnyIO compatibility.
    """
    
    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version."""
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3
            )
    
    # Override synchronous methods to warn when called from async context
    
    def handle_space_creation_request(self, request: StorachaSpaceCreationRequest):
        """
        Handle space creation request in Storacha.
        
        Args:
            request: Space creation request parameters
            
        Returns:
            Space creation response
        """
        self._warn_if_async_context("handle_space_creation_request")
        # Remove async keyword as this is now a sync implementation
        return super().handle_space_creation_request(request)
    
    def handle_list_spaces_request(self):
        """
        Handle list spaces request in Storacha.
        
        Returns:
            List spaces response
        """
        self._warn_if_async_context("handle_list_spaces_request")
        return super().handle_list_spaces_request()
    
    def handle_set_space_request(self, request: StorachaSetSpaceRequest):
        """
        Handle set current space request in Storacha.
        
        Args:
            request: Set space request parameters
            
        Returns:
            Set space response
        """
        self._warn_if_async_context("handle_set_space_request")
        return super().handle_set_space_request(request)
    
    def handle_upload_request(self, request: StorachaUploadRequest):
        """
        Handle upload request to Storacha.
        
        Args:
            request: Upload request parameters
            
        Returns:
            Upload response
        """
        self._warn_if_async_context("handle_upload_request")
        return super().handle_upload_request(request)
    
    def handle_upload_car_request(self, request: StorachaUploadCarRequest):
        """
        Handle CAR upload request to Storacha.
        
        Args:
            request: CAR upload request parameters
            
        Returns:
            CAR upload response
        """
        self._warn_if_async_context("handle_upload_car_request")
        return super().handle_upload_car_request(request)
    
    def handle_list_uploads_request(self, space_did: Optional[str] = None):
        """
        Handle list uploads request in Storacha.
        
        Args:
            space_did: Optional space DID to use
            
        Returns:
            List uploads response
        """
        self._warn_if_async_context("handle_list_uploads_request")
        return super().handle_list_uploads_request(space_did)
    
    def handle_delete_request(self, request: StorachaDeleteRequest):
        """
        Handle delete request in Storacha.
        
        Args:
            request: Delete request parameters
            
        Returns:
            Delete response
        """
        self._warn_if_async_context("handle_delete_request")
        return super().handle_delete_request(request)
    
    def handle_ipfs_to_storacha_request(self, request: IPFSStorachaRequest):
        """
        Handle transfer from IPFS to Storacha.
        
        Args:
            request: IPFS to Storacha request parameters
            
        Returns:
            IPFS to Storacha response
        """
        self._warn_if_async_context("handle_ipfs_to_storacha_request")
        return super().handle_ipfs_to_storacha_request(request)
    
    def handle_storacha_to_ipfs_request(self, request: StorachaIPFSRequest):
        """
        Handle transfer from Storacha to IPFS.
        
        Args:
            request: Storacha to IPFS request parameters
            
        Returns:
            Storacha to IPFS response
        """
        self._warn_if_async_context("handle_storacha_to_ipfs_request")
        return super().handle_storacha_to_ipfs_request(request)
    
    def handle_status_request(self):
        """
        Handle status request for Storacha backend.
        
        Returns:
            Status response
        """
        self._warn_if_async_context("handle_status_request")
        return super().handle_status_request()
    
    # Async versions of all methods
    
    async def handle_space_creation_request_async(self, request: StorachaSpaceCreationRequest):
        """
        Handle space creation request in Storacha asynchronously.
        
        Args:
            request: Space creation request parameters
            
        Returns:
            Space creation response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.create_space,
            name=request.name
        )
        
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
    
    async def handle_list_spaces_request_async(self):
        """
        Handle list spaces request in Storacha asynchronously.
        
        Returns:
            List spaces response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(self.storacha_model.list_spaces)
        
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
    
    async def handle_set_space_request_async(self, request: StorachaSetSpaceRequest):
        """
        Handle set current space request in Storacha asynchronously.
        
        Args:
            request: Set space request parameters
            
        Returns:
            Set space response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.set_current_space,
            space_did=request.space_did
        )
        
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
    
    async def handle_upload_request_async(self, request: StorachaUploadRequest):
        """
        Handle upload request to Storacha asynchronously.
        
        Args:
            request: Upload request parameters
            
        Returns:
            Upload response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.upload_file,
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
    
    async def handle_upload_car_request_async(self, request: StorachaUploadCarRequest):
        """
        Handle CAR upload request to Storacha asynchronously.
        
        Args:
            request: CAR upload request parameters
            
        Returns:
            CAR upload response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.upload_car,
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
    
    async def handle_list_uploads_request_async(self, space_did: Optional[str] = None):
        """
        Handle list uploads request in Storacha asynchronously.
        
        Args:
            space_did: Optional space DID to use
            
        Returns:
            List uploads response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.list_uploads,
            space_did=space_did
        )
        
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
    
    async def handle_delete_request_async(self, request: StorachaDeleteRequest):
        """
        Handle delete request in Storacha asynchronously.
        
        Args:
            request: Delete request parameters
            
        Returns:
            Delete response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.delete_upload,
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
    
    async def handle_ipfs_to_storacha_request_async(self, request: IPFSStorachaRequest):
        """
        Handle transfer from IPFS to Storacha asynchronously.
        
        Args:
            request: IPFS to Storacha request parameters
            
        Returns:
            IPFS to Storacha response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.ipfs_to_storacha,
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
    
    async def handle_storacha_to_ipfs_request_async(self, request: StorachaIPFSRequest):
        """
        Handle transfer from Storacha to IPFS asynchronously.
        
        Args:
            request: Storacha to IPFS request parameters
            
        Returns:
            Storacha to IPFS response
        """
        # Delegate to Storacha model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.storacha_model.storacha_to_ipfs,
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
    
    async def handle_status_request_async(self):
        """
        Handle status request for Storacha backend asynchronously.
        
        Returns:
            Status response
        """
        # Get stats from the model using anyio for potentially blocking operations
        stats = await anyio.to_thread.run_sync(self.storacha_model.get_stats)
        
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
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        In AnyIO mode, registers the async versions of handlers.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Space creation endpoint
        router.add_api_route(
            "/storacha/space/create",
            self.handle_space_creation_request_async,
            methods=["POST"],
            response_model=StorachaSpaceCreationResponse,
            summary="Create Storacha Space",
            description="Create a new storage space in Storacha (Web3.Storage)"
        )
        
        # List spaces endpoint
        router.add_api_route(
            "/storacha/space/list",
            self.handle_list_spaces_request_async,
            methods=["GET"],
            response_model=StorachaListSpacesResponse,
            summary="List Storacha Spaces",
            description="List all available storage spaces in Storacha (Web3.Storage)"
        )
        
        # Set current space endpoint
        router.add_api_route(
            "/storacha/space/set",
            self.handle_set_space_request_async,
            methods=["POST"],
            response_model=StorachaSetSpaceResponse,
            summary="Set Storacha Space",
            description="Set the current storage space in Storacha (Web3.Storage)"
        )
        
        # Upload file endpoint
        router.add_api_route(
            "/storacha/upload",
            self.handle_upload_request_async,
            methods=["POST"],
            response_model=StorachaUploadResponse,
            summary="Upload to Storacha",
            description="Upload a file to Storacha (Web3.Storage)"
        )
        
        # Upload CAR file endpoint
        router.add_api_route(
            "/storacha/upload/car",
            self.handle_upload_car_request_async,
            methods=["POST"],
            response_model=StorachaUploadCarResponse,
            summary="Upload CAR to Storacha",
            description="Upload a CAR file to Storacha (Web3.Storage)"
        )
        
        # List uploads endpoint
        router.add_api_route(
            "/storacha/uploads",
            self.handle_list_uploads_request_async,
            methods=["GET"],
            response_model=StorachaListUploadsResponse,
            summary="List Storacha Uploads",
            description="List uploads in a Storacha (Web3.Storage) space"
        )
        
        # Delete upload endpoint
        router.add_api_route(
            "/storacha/delete",
            self.handle_delete_request_async,
            methods=["POST"],
            response_model=StorachaDeleteResponse,
            summary="Delete from Storacha",
            description="Delete an upload from Storacha (Web3.Storage)"
        )
        
        # IPFS to Storacha endpoint
        router.add_api_route(
            "/storacha/from_ipfs",
            self.handle_ipfs_to_storacha_request_async,
            methods=["POST"],
            response_model=IPFSStorachaResponse,
            summary="IPFS to Storacha",
            description="Transfer content from IPFS to Storacha (Web3.Storage)"
        )
        
        # Storacha to IPFS endpoint
        router.add_api_route(
            "/storacha/to_ipfs",
            self.handle_storacha_to_ipfs_request_async,
            methods=["POST"],
            response_model=StorachaIPFSResponse,
            summary="Storacha to IPFS",
            description="Transfer content from Storacha (Web3.Storage) to IPFS"
        )
        
        # Status endpoint for testing
        router.add_api_route(
            "/storage/storacha/status",
            self.handle_status_request_async,
            methods=["GET"],
            response_model=OperationResponse,
            summary="Storacha Status",
            description="Get current status of the Storacha (Web3.Storage) backend"
        )
        
        logger.info("Storacha routes registered with AnyIO support")
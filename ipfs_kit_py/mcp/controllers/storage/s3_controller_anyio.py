"""
S3 Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to S3 operations and
delegates the business logic to the S3 model, with support for both asyncio
and trio via the AnyIO library.
"""

import logging
import time
import json
import tempfile
import warnings
import sniffio
import anyio
from typing import Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from ipfs_kit_py.mcp.controllers.storage.s3_controller import (
    S3Controller,
    S3UploadRequest,
    S3DownloadRequest,
    S3DeleteRequest,
    IPFSS3Request,
    S3IPFSRequest,
    OperationResponse,
    S3UploadResponse,
    S3DownloadResponse,
    S3ListResponse,
    S3DeleteResponse,
    IPFSS3Response,
    S3IPFSResponse,
)

# Configure logger
logger = logging.getLogger(__name__)


class S3ControllerAnyIO(S3Controller):
    """
    Controller for S3 operations with AnyIO support.

    Handles HTTP requests related to S3 operations and delegates
    the business logic to the S3 model, supporting both asyncio
    and trio backends through AnyIO compatibility.
    """
    @staticmethod
    def get_backend():
        """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Get the current async backend being used."""
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
                stacklevel=3,
            )

    # Override synchronous methods to warn when called from async context

    def handle_upload_request(
        self,
        request: S3UploadRequest = None,
        file: UploadFile = File(None),
        bucket: str = Form(None),
        key: str = Form(None),
        metadata: str = Form(None),
    ):
        """
        Handle upload request to S3.

        Supports both JSON request body and form-based file uploads.

        Args:
            request: Upload request parameters (JSON body)
            file: Uploaded file (form-based)
            bucket: S3 bucket name (form-based)
            key: S3 object key (form-based)
            metadata: JSON-encoded metadata (form-based)

        Returns:
            Upload response
        """
        self._warn_if_async_context("handle_upload_request")
        return super().handle_upload_request(request, file, bucket, key, metadata)

    def handle_download_request(self, request: S3DownloadRequest):
        """
        Handle download request from S3.

        Args:
            request: Download request parameters

        Returns:
            Download response
        """
        self._warn_if_async_context("handle_download_request")
        return super().handle_download_request(request)

    def handle_list_request(self, bucket: str, prefix: Optional[str] = None):
        """
        Handle list request for S3 bucket.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix to filter objects

        Returns:
            List response
        """
        self._warn_if_async_context("handle_list_request")
        return super().handle_list_request(bucket, prefix)

    def handle_delete_request(self, request: S3DeleteRequest):
        """
        Handle delete request for S3 object.

        Args:
            request: Delete request parameters

        Returns:
            Delete response
        """
        self._warn_if_async_context("handle_delete_request")
        return super().handle_delete_request(request)

    def handle_ipfs_to_s3_request(self, request: IPFSS3Request):
        """
        Handle transfer from IPFS to S3.

        Args:
            request: IPFS to S3 request parameters

        Returns:
            IPFS to S3 response
        """
        self._warn_if_async_context("handle_ipfs_to_s3_request")
        return super().handle_ipfs_to_s3_request(request)

    def handle_s3_to_ipfs_request(self, request: S3IPFSRequest):
        """
        Handle transfer from S3 to IPFS.

        Args:
            request: S3 to IPFS request parameters

        Returns:
            S3 to IPFS response
        """
        self._warn_if_async_context("handle_s3_to_ipfs_request")
        return super().handle_s3_to_ipfs_request(request)

    def handle_status_request(self):
        """
        Handle status request for S3 backend.

        Returns:
            Status response
        """
        self._warn_if_async_context("handle_status_request")
        return super().handle_status_request()

    def handle_list_buckets_request(self):
        """
        Handle list buckets request for S3 backend.

        Returns:
            Buckets response with list of available S3 buckets
        """
        self._warn_if_async_context("handle_list_buckets_request")
        return super().handle_list_buckets_request()

    # Async versions of all methods

    async def handle_upload_request_async(
        self,
        request: S3UploadRequest = None,
        file: UploadFile = File(None),
        bucket: str = Form(None),
        key: str = Form(None),
        metadata: str = Form(None),
    ):
        """
        Handle upload request to S3 asynchronously.

        Supports both JSON request body and form-based file uploads.

        Args:
            request: Upload request parameters (JSON body)
            file: Uploaded file (form-based)
            bucket: S3 bucket name (form-based)
            key: S3 object key (form-based)
            metadata: JSON-encoded metadata (form-based)

        Returns:
            Upload response
        """
        start_time = time.time()

        # Check if this is a form-based upload or JSON request
        if file is not None:
            # Form-based upload
            if not bucket:
                mcp_error_handling.raise_http_exception(
                    code="MISSING_PARAMETER",
                    message_override={
                        "error": "Bucket name is required",
                        "endpoint": "/api/v0/s3_anyio",
                        "doc_category": "storage"
                    }
                )

            # Use filename as key if not provided
            if not key:
                key = file.filename

            # Parse metadata if provided
            metadata_dict = None
            if metadata:
                try:
                    metadata_dict = json.loads(metadata)
                except json.JSONDecodeError:
                    mcp_error_handling.raise_http_exception(
                        code="INVALID_REQUEST",
                        message_override={
                            "error": "Invalid metadata JSON",
                            "endpoint": "/api/v0/s3_anyio",
                            "doc_category": "storage"
                        }
                    )

            # Use anyio for temporary file handling
            async with await anyio.open_file(tempfile.mktemp(), "wb+") as temp_file:
                temp_path = temp_file.name

                # Copy content from upload to temporary file
                content = await file.read()
                await temp_file.write(content)
                await temp_file.flush()

                # Upload file to S3 using anyio.to_thread.run_sync for the blocking operation
                result = await anyio.to_thread.run_sync(
                    self.s3_model.upload_file,
                    file_path=temp_path,
                    bucket=bucket,
                    key=key,
                    metadata=metadata_dict,
                )

                # Clean up temporary file (done by the context manager)
        else:
            # JSON request
            if not request:
                mcp_error_handling.raise_http_exception(
                    code="MISSING_PARAMETER",
                    message_override={
                        "error": "Missing request data",
                        "endpoint": "/api/v0/s3_anyio",
                        "doc_category": "storage"
                    }
                )

            # Delegate to S3 model using anyio.to_thread.run_sync
            result = await anyio.to_thread.run_sync(
                self.s3_model.upload_file,
                file_path=request.file_path,
                bucket=request.bucket,
                key=request.key,
                metadata=request.metadata,
            )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                    "endpoint": "/api/v0/s3_anyio",
                    "doc_category": "storage"
                }
            )

        # Add duration if not already present
        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        # Return successful response
        return result

    async def handle_download_request_async(self, request: S3DownloadRequest):
        """
        Handle download request from S3 asynchronously.

        Args:
            request: Download request parameters

        Returns:
            Download response
        """
        # Delegate to S3 model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.s3_model.download_file,
            bucket=request.bucket,
            key=request.key,
            destination=request.destination,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                    "endpoint": "/api/v0/s3_anyio",
                    "doc_category": "storage"
                }
            )

        # Return successful response
        return result

    async def handle_list_request_async(self, bucket: str, prefix: Optional[str] = None):
        """
        Handle list request for S3 bucket asynchronously.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix to filter objects

        Returns:
            List response
        """
        # Delegate to S3 model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.s3_model.list_objects, bucket=bucket, prefix=prefix
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                    "endpoint": "/api/v0/s3_anyio",
                    "doc_category": "storage"
                }
            )

        # Return successful response
        return result

    async def handle_delete_request_async(self, request: S3DeleteRequest):
        """
        Handle delete request for S3 object asynchronously.

        Args:
            request: Delete request parameters

        Returns:
            Delete response
        """
        # Delegate to S3 model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.s3_model.delete_object, bucket=request.bucket, key=request.key
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                    "endpoint": "/api/v0/s3_anyio",
                    "doc_category": "storage"
                }
            )

        # Return successful response
        return result

    async def handle_ipfs_to_s3_request_async(self, request: IPFSS3Request):
        """
        Handle transfer from IPFS to S3 asynchronously.

        Args:
            request: IPFS to S3 request parameters

        Returns:
            IPFS to S3 response
        """
        # Delegate to S3 model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.s3_model.ipfs_to_s3,
            cid=request.cid,
            bucket=request.bucket,
            key=request.key,
            pin=request.pin,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                    "endpoint": "/api/v0/s3_anyio",
                    "doc_category": "storage"
                }
            )

        # Return successful response
        return result

    async def handle_s3_to_ipfs_request_async(self, request: S3IPFSRequest):
        """
        Handle transfer from S3 to IPFS asynchronously.

        Args:
            request: S3 to IPFS request parameters

        Returns:
            S3 to IPFS response
        """
        # Delegate to S3 model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(
            self.s3_model.s3_to_ipfs,
            bucket=request.bucket,
            key=request.key,
            pin=request.pin,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                    "endpoint": "/api/v0/s3_anyio",
                    "doc_category": "storage"
                }
            )

        # Return successful response
        return result

    async def handle_status_request_async(self):
        """
        Handle status request for S3 backend asynchronously.

        Returns:
            Status response
        """
        # Get stats from the model using anyio for potentially blocking operations
        stats = await anyio.to_thread.run_sync(self.s3_model.get_stats)

        # Create response with status information
        return {
            "success": True,
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": 0,
            "is_available": True,
            "backend": "s3",
            "stats": stats,
            "timestamp": time.time(),
        }

    async def handle_list_buckets_request_async(self):
        """
        Handle list buckets request for S3 backend asynchronously.

        Returns:
            Buckets response with list of available S3 buckets
        """
        start_time = time.time()

        # Delegate to S3 model using anyio.to_thread.run_sync
        result = await anyio.to_thread.run_sync(self.s3_model.list_buckets)

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                    "endpoint": "/api/v0/s3_anyio",
                    "doc_category": "storage"
                }
            )

        # Add duration if not already present
        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        # Return successful response
        return result

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        In AnyIO mode, registers the async versions of handlers.

        Args:
            router: FastAPI router to register routes with
        """
        # Register all routes under /storage/s3 prefix for consistency

        # File upload endpoint (form-based)
        router.add_api_route(
            "/storage/s3/upload",
            self.handle_upload_request_async,
            methods=["POST"],
            response_model=S3UploadResponse,
            summary="Upload to S3",
            description="Upload content to an S3 bucket",
        )

        # Download endpoint
        router.add_api_route(
            "/storage/s3/download",
            self.handle_download_request_async,
            methods=["POST"],
            response_model=S3DownloadResponse,
            summary="Download from S3",
            description="Download content from an S3 bucket",
        )

        # List objects endpoint
        router.add_api_route(
            "/storage/s3/list/{bucket}",
            self.handle_list_request_async,
            methods=["GET"],
            response_model=S3ListResponse,
            summary="List S3 objects",
            description="List objects in an S3 bucket",
        )

        # Delete object endpoint
        router.add_api_route(
            "/storage/s3/delete",
            self.handle_delete_request_async,
            methods=["POST"],
            response_model=S3DeleteResponse,
            summary="Delete from S3",
            description="Delete an object from an S3 bucket",
        )

        # IPFS to S3 endpoint
        router.add_api_route(
            "/storage/s3/from_ipfs",
            self.handle_ipfs_to_s3_request_async,
            methods=["POST"],
            response_model=IPFSS3Response,
            summary="IPFS to S3",
            description="Transfer content from IPFS to S3",
        )

        # S3 to IPFS endpoint
        router.add_api_route(
            "/storage/s3/to_ipfs",
            self.handle_s3_to_ipfs_request_async,
            methods=["POST"],
            response_model=S3IPFSResponse,
            summary="S3 to IPFS",
            description="Transfer content from S3 to IPFS",
        )

        # Status endpoint for testing
        router.add_api_route(
            "/storage/s3/status",
            self.handle_status_request_async,
            methods=["GET"],
            response_model=OperationResponse,
            summary="S3 Status",
            description="Get current status of the S3 backend",
        )

        # Add bucket operations endpoints
        router.add_api_route(
            "/storage/s3/buckets",
            self.handle_list_buckets_request_async,
            methods=["GET"],
            response_model=OperationResponse,
            summary="List S3 Buckets",
            description="List all available S3 buckets",
        )

        # Register backward compatibility routes (old /s3 prefix pattern)
        # These ensure backward compatibility with any existing code
        router.add_api_route(
            "/s3/status",
            self.handle_status_request_async,
            methods=["GET"],
            include_in_schema=False,  # Hide in OpenAPI docs to reduce clutter
        )

        logger.info("S3 routes registered with AnyIO support")
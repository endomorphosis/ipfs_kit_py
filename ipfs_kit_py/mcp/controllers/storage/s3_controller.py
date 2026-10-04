"""
S3 Controller for the MCP server.

This controller handles HTTP requests related to S3 operations and
delegates the business logic to the S3 model.
"""

import logging
import time
import os
import json
import tempfile
from typing import Dict, List, Any, Optional
from fastapi import (
    APIRouter,
    HTTPException,
    File,
    UploadFile,
    Form
)
from pydantic import BaseModel, Field

import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

# Configure logger
logger = logging.getLogger(__name__)

# Import S3Model


# Define Pydantic models for requests and responses
class S3CredentialsRequest(BaseModel):
    """Request model for S3 credentials."""
    access_key: str = Field(..., description="AWS Access Key ID")
    secret_key: str = Field(..., description="AWS Secret Access Key")
    endpoint_url: Optional[str] = Field(
        None, description="Custom endpoint URL for S3-compatible services"
    )
    region: Optional[str] = Field(None, description="AWS region")


class S3UploadRequest(BaseModel):
    """Request model for S3 upload operations."""
    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key")
    file_path: str = Field(..., description="Local file path to upload")
    metadata: Optional[Dict[str, str]] = Field(None, description="Optional metadata for the object")


class S3DownloadRequest(BaseModel):
    """Request model for S3 download operations."""
    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key")
    destination: str = Field(..., description="Local path to save the file")


class S3ListRequest(BaseModel):
    """Request model for S3 list operations."""
    bucket: str = Field(..., description="S3 bucket name")
    prefix: Optional[str] = Field(None, description="Prefix to filter objects")


class S3DeleteRequest(BaseModel):
    """Request model for S3 delete operations."""
    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key")


class IPFSS3Request(BaseModel):
    """Request model for IPFS to S3 operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    bucket: str = Field(..., description="S3 bucket name")
    key: Optional[str] = Field(None, description="S3 object key (defaults to CID if not provided)")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")


class S3IPFSRequest(BaseModel):
    """Request model for S3 to IPFS operations."""
    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")


class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    duration_ms: Optional[float] = Field(
        None, description="Duration of the operation in milliseconds"
    )


class S3UploadResponse(OperationResponse):
    """Response model for S3 upload operations."""
    bucket: Optional[str] = Field(None, description="S3 bucket name")
    key: Optional[str] = Field(None, description="S3 object key")
    etag: Optional[str] = Field(None, description="ETag of the uploaded object")
    size_bytes: Optional[int] = Field(None, description="Size of the uploaded object in bytes")


class S3DownloadResponse(OperationResponse):
    """Response model for S3 download operations."""
    bucket: Optional[str] = Field(None, description="S3 bucket name")
    key: Optional[str] = Field(None, description="S3 object key")
    destination: Optional[str] = Field(None, description="Local path where the file was saved")
    size_bytes: Optional[int] = Field(None, description="Size of the downloaded object in bytes")


class S3ListResponse(OperationResponse):
    """Response model for S3 list operations."""
    bucket: Optional[str] = Field(None, description="S3 bucket name")
    prefix: Optional[str] = Field(None, description="Prefix used to filter objects")
    objects: Optional[List[Dict[str, Any]]] = Field(None, description="List of objects")
    count: Optional[int] = Field(None, description="Number of objects")


class S3DeleteResponse(OperationResponse):
    """Response model for S3 delete operations."""
    bucket: Optional[str] = Field(None, description="S3 bucket name")
    key: Optional[str] = Field(None, description="S3 object key")


class IPFSS3Response(OperationResponse):
    """Response model for IPFS to S3 operations."""
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    bucket: Optional[str] = Field(None, description="S3 bucket name")
    key: Optional[str] = Field(None, description="S3 object key")
    etag: Optional[str] = Field(None, description="ETag of the uploaded object")
    size_bytes: Optional[int] = Field(None, description="Size of the object in bytes")


class S3IPFSResponse(OperationResponse):
    """Response model for S3 to IPFS operations."""
    bucket: Optional[str] = Field(None, description="S3 bucket name")
    key: Optional[str] = Field(None, description="S3 object key")
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    size_bytes: Optional[int] = Field(None, description="Size of the object in bytes")


class S3Controller:
    """
    Controller for S3 operations.

    Handles HTTP requests related to S3 operations and delegates
    the business logic to the S3 model.
    """
    def __init__(self, s3_model):
        """
        Initialize the S3 controller.

        Args:
            s3_model: S3 model to use for operations
        """
        self.s3_model = s3_model
        logger.info("S3 Controller initialized")

    def register_routes(self, router: APIRouter, prefix: str = ""):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Register all routes under /storage/s3 prefix for consistency

        # File upload endpoint (form-based)
        router.add_api_route(
            "/storage/s3/upload",
            self.handle_upload_request,
            methods=["POST"],
            response_model=S3UploadResponse,
            summary="Upload to S3",
            description="Upload content to an S3 bucket",
        )

        # Download endpoint
        router.add_api_route(
            "/storage/s3/download",
            self.handle_download_request,
            methods=["POST"],
            response_model=S3DownloadResponse,
            summary="Download from S3",
            description="Download content from an S3 bucket",
        )

        # List objects endpoint
        router.add_api_route(
            "/storage/s3/list/{bucket}",
            self.handle_list_request,
            methods=["GET"],
            response_model=S3ListResponse,
            summary="List S3 objects",
            description="List objects in an S3 bucket",
        )

        # Delete object endpoint
        router.add_api_route(
            "/storage/s3/delete",
            self.handle_delete_request,
            methods=["POST"],
            response_model=S3DeleteResponse,
            summary="Delete from S3",
            description="Delete an object from an S3 bucket",
        )

        # IPFS to S3 endpoint
        router.add_api_route(
            "/storage/s3/from_ipfs",
            self.handle_ipfs_to_s3_request,
            methods=["POST"],
            response_model=IPFSS3Response,
            summary="IPFS to S3",
            description="Transfer content from IPFS to S3",
        )

        # S3 to IPFS endpoint
        router.add_api_route(
            "/storage/s3/to_ipfs",
            self.handle_s3_to_ipfs_request,
            methods=["POST"],
            response_model=S3IPFSResponse,
            summary="S3 to IPFS",
            description="Transfer content from S3 to IPFS",
        )

        # Status endpoint for testing
        router.add_api_route(
            "/storage/s3/status",
            self.handle_status_request,
            methods=["GET"],
            response_model=OperationResponse,
            summary="S3 Status",
            description="Get current status of the S3 backend",
        )

        # Add bucket operations endpoints
        router.add_api_route(
            "/storage/s3/buckets",
            self.handle_list_buckets_request,
            methods=["GET"],
            response_model=OperationResponse,
            summary="List S3 Buckets",
            description="List all available S3 buckets",
        )

        # Register backward compatibility routes (old /s3 prefix pattern)
        # These ensure backward compatibility with any existing code
        router.add_api_route(
            "/s3/status",
            self.handle_status_request,
            methods=["GET"],
            include_in_schema=False,  # Hide in OpenAPI docs to reduce clutter
        )

        logger.info("S3 routes registered")

    async def handle_upload_request(
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
        start_time = time.time()

        # Check if this is a form-based upload or JSON request
        if file is not None:
            # Form-based upload
            if not bucket:
                mcp_error_handling.raise_http_exception(
                    code="MISSING_PARAMETER",
                    message_override={
                        "error": "Bucket name is required"
                    },
                    endpoint="/api/v0/s3",
                    doc_category="storage"
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
                            "error": "Invalid metadata JSON"
                        },
                        endpoint="/api/v0/s3",
                        doc_category="storage"
                    )

            # Create temporary file to store the uploaded content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

                # Copy content from upload to temporary file
                content = await file.read()
                temp_file.write(content)
                temp_file.flush()

                # Upload file to S3
                result = self.s3_model.upload_file(
                    file_path=temp_path, bucket=bucket, key=key, metadata=metadata_dict
                )

                # Clean up temporary file
                os.unlink(temp_path)
        else:
            # JSON request
            if not request:
                mcp_error_handling.raise_http_exception(
                    code="MISSING_PARAMETER",
                    message_override={
                        "error": "Missing request data"
                    },
                    endpoint="/api/v0/s3",
                    doc_category="storage"
                )

            # Delegate to S3 model
            result = self.s3_model.upload_file(
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
                    "error": result.get("error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
                endpoint="/api/v0/s3",
                doc_category="storage"
            )

        # Add duration if not already present
        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        # Return successful response
        return result

    async def handle_download_request(self, request: S3DownloadRequest):
        """
        Handle download request from S3.

        Args:
            request: Download request parameters

        Returns:
            Download response
        """
        # Delegate to S3 model
        result = self.s3_model.download_file(
            bucket=request.bucket, key=request.key, destination=request.destination
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
                endpoint="/api/v0/s3",
                doc_category="storage"
            )

        # Return successful response
        return result

    async def handle_list_request(self, bucket: str, prefix: Optional[str] = None):
        """
        Handle list request for S3 bucket.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix to filter objects

        Returns:
            List response
        """
        # Delegate to S3 model
        result = self.s3_model.list_objects(bucket=bucket, prefix=prefix)

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
                endpoint="/api/v0/s3",
                doc_category="storage"
            )

        # Return successful response
        return result

    async def handle_delete_request(self, request: S3DeleteRequest):
        """
        Handle delete request for S3 object.

        Args:
            request: Delete request parameters

        Returns:
            Delete response
        """
        # Delegate to S3 model
        result = self.s3_model.delete_object(bucket=request.bucket, key=request.key)

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
                endpoint="/api/v0/s3",
                doc_category="storage"
            )

        # Return successful response
        return result

    async def handle_ipfs_to_s3_request(self, request: IPFSS3Request):
        """
        Handle transfer from IPFS to S3.

        Args:
            request: IPFS to S3 request parameters

        Returns:
            IPFS to S3 response
        """
        # Delegate to S3 model
        result = self.s3_model.ipfs_to_s3(
            cid=request.cid, bucket=request.bucket, key=request.key, pin=request.pin
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
                endpoint="/api/v0/s3",
                doc_category="storage"
            )

        # Return successful response
        return result

    async def handle_s3_to_ipfs_request(self, request: S3IPFSRequest):
        """
        Handle transfer from S3 to IPFS.

        Args:
            request: S3 to IPFS request parameters

        Returns:
            S3 to IPFS response
        """
        # Delegate to S3 model
        result = self.s3_model.s3_to_ipfs(bucket=request.bucket, key=request.key, pin=request.pin)

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
                endpoint="/api/v0/s3",
                doc_category="storage"
            )

        # Return successful response
        return result

    async def handle_status_request(self):
        """
        Handle status request for S3 backend.

        Returns:
            Status response
        """
        # Get stats from the model
        stats = self.s3_model.get_stats()

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

    async def handle_list_buckets_request(self):
        """
        Handle list buckets request for S3 backend.

        Returns:
            Buckets response with list of available S3 buckets
        """
        start_time = time.time()

        # Delegate to S3 model
        result = self.s3_model.list_buckets()

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override={
                    "error": result.get("error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
                endpoint="/api/v0/s3",
                doc_category="storage"
            )

        # Add duration if not already present
        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        # Return successful response
        return result

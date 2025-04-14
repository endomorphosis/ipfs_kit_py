"""
Hugging Face Controller for the MCP server.

This controller handles HTTP requests related to Hugging Face Hub operations and
delegates the business logic to the Hugging Face model.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from fastapi import (
from pydantic import BaseModel, Field

APIRouter,
    HTTPException)

# Import Pydantic models for request/response validation


# Configure logger
logger = logging.getLogger(__name__)


# Define Pydantic models for requests and responses
class HuggingFaceAuthRequest(BaseModel):
    """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Request model for Hugging Face authentication."""
    token: str = Field(..., description="Hugging Face Hub API token")


class HuggingFaceRepoCreationRequest(BaseModel):
    """Request model for Hugging Face repository creation."""
    repo_id: str = Field(..., description="Repository ID (username/repo-name)")
    repo_type: str = Field("model", description="Repository type (model, dataset, space)")
    private: bool = Field(False, description="Whether the repository should be private")


class HuggingFaceUploadRequest(BaseModel):
    """Request model for Hugging Face upload operations."""
    file_path: str = Field(..., description="Local file path to upload")
    repo_id: str = Field(..., description="Repository ID (username/repo-name)")
    path_in_repo: Optional[str] = Field(None, description="Path within the repository")
    commit_message: Optional[str] = Field(None, description="Commit message for the upload")
    repo_type: str = Field("model", description="Repository type (model, dataset, space)")


class HuggingFaceDownloadRequest(BaseModel):
    """Request model for Hugging Face download operations."""
    repo_id: str = Field(..., description="Repository ID (username/repo-name)")
    filename: str = Field(..., description="Filename to download")
    destination: str = Field(..., description="Local path to save the file")
    revision: Optional[str] = Field(None, description="Git revision (branch, tag, or commit hash)")
    repo_type: str = Field("model", description="Repository type (model, dataset, space)")


class HuggingFaceListModelsRequest(BaseModel):
    """Request model for listing Hugging Face models."""
    author: Optional[str] = Field(None, description="Filter by author/organization")
    search: Optional[str] = Field(None, description="Search query")
    limit: int = Field(50, description="Maximum number of results to return")


class IPFSHuggingFaceRequest(BaseModel):
    """Request model for IPFS to Hugging Face operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    repo_id: str = Field(..., description="Repository ID (username/repo-name)")
    path_in_repo: Optional[str] = Field(None, description="Path within the repository")
    commit_message: Optional[str] = Field(None, description="Commit message for the upload")
    repo_type: str = Field("model", description="Repository type (model, dataset, space)")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")


class HuggingFaceIPFSRequest(BaseModel):
    """Request model for Hugging Face to IPFS operations."""
    repo_id: str = Field(..., description="Repository ID (username/repo-name)")
    filename: str = Field(..., description="Filename to download")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")
    revision: Optional[str] = Field(None, description="Git revision (branch, tag, or commit hash)")
    repo_type: str = Field("model", description="Repository type (model, dataset, space)")


class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    duration_ms: Optional[float] = Field(
        None, description="Duration of the operation in milliseconds"
    )


class HuggingFaceAuthResponse(OperationResponse):
    """Response model for Hugging Face authentication."""
    authenticated: Optional[bool] = Field(None, description="Whether authentication was successful")
    user_info: Optional[Dict[str, Any]] = Field(None, description="User information")


class HuggingFaceRepoCreationResponse(OperationResponse):
    """Response model for Hugging Face repository creation."""
    repo_id: Optional[str] = Field(None, description="Repository ID")
    repo_type: Optional[str] = Field(None, description="Repository type")
    private: Optional[bool] = Field(None, description="Whether the repository is private")
    url: Optional[str] = Field(None, description="Repository URL")
    repo_details: Optional[Dict[str, Any]] = Field(None, description="Repository details")


class HuggingFaceUploadResponse(OperationResponse):
    """Response model for Hugging Face upload operations."""
    repo_id: Optional[str] = Field(None, description="Repository ID")
    repo_type: Optional[str] = Field(None, description="Repository type")
    path_in_repo: Optional[str] = Field(None, description="Path within the repository")
    size_bytes: Optional[int] = Field(None, description="Size of the uploaded file in bytes")
    url: Optional[str] = Field(None, description="URL to the uploaded file")
    commit_url: Optional[str] = Field(None, description="URL to the commit")


class HuggingFaceDownloadResponse(OperationResponse):
    """Response model for Hugging Face download operations."""
    repo_id: Optional[str] = Field(None, description="Repository ID")
    repo_type: Optional[str] = Field(None, description="Repository type")
    filename: Optional[str] = Field(None, description="Filename downloaded")
    destination: Optional[str] = Field(None, description="Local path where the file was saved")
    size_bytes: Optional[int] = Field(None, description="Size of the downloaded file in bytes")
    revision: Optional[str] = Field(None, description="Git revision used")


class HuggingFaceListModelsResponse(OperationResponse):
    """Response model for listing Hugging Face models."""
    models: Optional[List[Dict[str, Any]]] = Field(None, description="List of models")
    count: Optional[int] = Field(None, description="Number of models")
    author: Optional[str] = Field(None, description="Author filter applied")
    search: Optional[str] = Field(None, description="Search query applied")


class IPFSHuggingFaceResponse(OperationResponse):
    """Response model for IPFS to Hugging Face operations."""
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    repo_id: Optional[str] = Field(None, description="Repository ID")
    repo_type: Optional[str] = Field(None, description="Repository type")
    path_in_repo: Optional[str] = Field(None, description="Path within the repository")
    size_bytes: Optional[int] = Field(None, description="Size of the file in bytes")
    url: Optional[str] = Field(None, description="URL to the uploaded file")
    commit_url: Optional[str] = Field(None, description="URL to the commit")


class HuggingFaceIPFSResponse(OperationResponse):
    """Response model for Hugging Face to IPFS operations."""
    repo_id: Optional[str] = Field(None, description="Repository ID")
    repo_type: Optional[str] = Field(None, description="Repository type")
    filename: Optional[str] = Field(None, description="Filename")
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    size_bytes: Optional[int] = Field(None, description="Size of the file in bytes")
    revision: Optional[str] = Field(None, description="Git revision used")


class HuggingFaceController:
    """
    Controller for Hugging Face Hub operations.

    Handles HTTP requests related to Hugging Face Hub operations and delegates
    the business logic to the Hugging Face model.
    """
    def __init__(self, huggingface_model):
        """
        Initialize the Hugging Face controller.

        Args:
            huggingface_model: Hugging Face model to use for operations
        """
        self.huggingface_model = huggingface_model
        logger.info("Hugging Face Controller initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Authentication endpoint
        router.add_api_route(
            "/huggingface/auth",
            self.handle_auth_request,
            methods=["POST"],
            response_model=HuggingFaceAuthResponse,
            summary="Authenticate with Hugging Face Hub",
            description="Authenticate with Hugging Face Hub using an API token",
        )

        # Repository creation endpoint
        router.add_api_route(
            "/huggingface/repo/create",
            self.handle_repo_creation_request,
            methods=["POST"],
            response_model=HuggingFaceRepoCreationResponse,
            summary="Create Hugging Face Repository",
            description="Create a new repository on Hugging Face Hub",
        )

        # Upload endpoint
        router.add_api_route(
            "/huggingface/upload",
            self.handle_upload_request,
            methods=["POST"],
            response_model=HuggingFaceUploadResponse,
            summary="Upload to Hugging Face Hub",
            description="Upload a file to a Hugging Face Hub repository",
        )

        # Download endpoint
        router.add_api_route(
            "/huggingface/download",
            self.handle_download_request,
            methods=["POST"],
            response_model=HuggingFaceDownloadResponse,
            summary="Download from Hugging Face Hub",
            description="Download a file from a Hugging Face Hub repository",
        )

        # List models endpoint
        router.add_api_route(
            "/huggingface/models",
            self.handle_list_models_request,
            methods=["GET"],
            response_model=HuggingFaceListModelsResponse,
            summary="List Hugging Face Models",
            description="List models on Hugging Face Hub with optional filters",
        )

        # IPFS to Hugging Face endpoint
        router.add_api_route(
            "/huggingface/from_ipfs",
            self.handle_ipfs_to_huggingface_request,
            methods=["POST"],
            response_model=IPFSHuggingFaceResponse,
            summary="IPFS to Hugging Face Hub",
            description="Transfer content from IPFS to Hugging Face Hub",
        )

        # Hugging Face to IPFS endpoint
        router.add_api_route(
            "/huggingface/to_ipfs",
            self.handle_huggingface_to_ipfs_request,
            methods=["POST"],
            response_model=HuggingFaceIPFSResponse,
            summary="Hugging Face Hub to IPFS",
            description="Transfer content from Hugging Face Hub to IPFS",
        )

        # Status endpoint for testing
        router.add_api_route(
            "/storage/huggingface/status",
            self.handle_status_request,
            methods=["GET"],
            response_model=OperationResponse,
            summary="Hugging Face Hub Status",
            description="Get current status of the Hugging Face Hub backend",
        )

        logger.info("Hugging Face routes registered")

    async def handle_auth_request(self, request: HuggingFaceAuthRequest):
        """
        Handle authentication request to Hugging Face Hub.

        Args:
            request: Authentication request parameters

        Returns:
            Authentication response
        """
        # Delegate to Hugging Face model
        result = self.huggingface_model.authenticate(token=request.token)

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="AUTHENTICATION_REQUIRED",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/huggingface",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "AuthenticationError"),
                },
            )

        # Return successful response
        return result

    async def handle_repo_creation_request(self, request: HuggingFaceRepoCreationRequest):
        """
        Handle repository creation request on Hugging Face Hub.

        Args:
            request: Repository creation request parameters

        Returns:
            Repository creation response
        """
        # Delegate to Hugging Face model
        result = self.huggingface_model.create_repository(
            repo_id=request.repo_id,
            repo_type=request.repo_type,
            private=request.private,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/huggingface",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "RepositoryCreationError"),
                },
            )

        # Return successful response
        return result

    async def handle_upload_request(self, request: HuggingFaceUploadRequest):
        """
        Handle upload request to Hugging Face Hub.

        Args:
            request: Upload request parameters

        Returns:
            Upload response
        """
        # Delegate to Hugging Face model
        result = self.huggingface_model.upload_file(
            file_path=request.file_path,
            repo_id=request.repo_id,
            path_in_repo=request.path_in_repo,
            commit_message=request.commit_message,
            repo_type=request.repo_type,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/huggingface",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "UploadError"),
                },
            )

        # Return successful response
        return result

    async def handle_download_request(self, request: HuggingFaceDownloadRequest):
        """
        Handle download request from Hugging Face Hub.

        Args:
            request: Download request parameters

        Returns:
            Download response
        """
        # Delegate to Hugging Face model
        result = self.huggingface_model.download_file(
            repo_id=request.repo_id,
            filename=request.filename,
            destination=request.destination,
            revision=request.revision,
            repo_type=request.repo_type,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/huggingface",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "DownloadError"),
                },
            )

        # Return successful response
        return result

    async def handle_list_models_request(
        self
        author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ):
        """
        Handle list models request from Hugging Face Hub.

        Args:
            author: Optional filter by author/organization
            search: Optional search query
            limit: Maximum number of results to return

        Returns:
            List models response
        """
        # Delegate to Hugging Face model
        result = self.huggingface_model.list_models(author=author, search=search, limit=limit)

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/huggingface",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "ListModelsError"),
                },
            )

        # Return successful response
        return result

    async def handle_ipfs_to_huggingface_request(self, request: IPFSHuggingFaceRequest):
        """
        Handle transfer from IPFS to Hugging Face Hub.

        Args:
            request: IPFS to Hugging Face Hub request parameters

        Returns:
            IPFS to Hugging Face Hub response
        """
        # Delegate to Hugging Face model
        result = self.huggingface_model.ipfs_to_huggingface(
            cid=request.cid,
            repo_id=request.repo_id,
            path_in_repo=request.path_in_repo,
            commit_message=request.commit_message,
            repo_type=request.repo_type,
            pin=request.pin,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get(,
        endpoint="/api/v0/huggingface",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "IPFSToHuggingFaceError"),
                },
            )

        # Return successful response
        return result

    async def handle_huggingface_to_ipfs_request(self, request: HuggingFaceIPFSRequest):
        """
        Handle transfer from Hugging Face Hub to IPFS.

        Args:
            request: Hugging Face Hub to IPFS request parameters

        Returns:
            Hugging Face Hub to IPFS response
        """
        # Delegate to Hugging Face model
        result = self.huggingface_model.huggingface_to_ipfs(
            repo_id=request.repo_id,
            filename=request.filename,
            pin=request.pin,
            revision=request.revision,
            repo_type=request.repo_type,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get(,
        endpoint="/api/v0/huggingface",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "HuggingFaceToIPFSError"),
                },
            )

        # Return successful response
        return result

    async def handle_status_request(self):
        """
        Handle status request for Hugging Face Hub backend.

        Returns:
            Status response
        """
        # Get stats from the model
        stats = self.huggingface_model.get_stats()

        # Create response with status information
        return {
            "success": True,
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": 0,
            "is_available": True,
            "backend": "huggingface",
            "stats": stats,
            "timestamp": time.time(),
        }

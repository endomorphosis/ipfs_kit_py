"""
Hugging Face Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to Hugging Face Hub operations and
delegates the business logic to the Hugging Face model, with support for both async-io
and trio via the AnyIO library.
"""

import logging
import time
import warnings
import sniffio
import anyio
from typing import Optional
from fastapi import (
from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import (

# AnyIO import


# Import Pydantic models for request/response validation

    APIRouter,
    HTTPException)

# Import original controller for inheritance

    HuggingFaceController,
    HuggingFaceAuthRequest,
    HuggingFaceRepoCreationRequest,
    HuggingFaceUploadRequest,
    HuggingFaceDownloadRequest,
    IPFSHuggingFaceRequest,
    HuggingFaceIPFSRequest,
    HuggingFaceAuthResponse,
    HuggingFaceRepoCreationResponse,
    HuggingFaceUploadResponse,
    HuggingFaceDownloadResponse,
    HuggingFaceListModelsResponse,
    IPFSHuggingFaceResponse,
    HuggingFaceIPFSResponse,
    OperationResponse,
)

# Configure logger
logger = logging.getLogger(__name__)


class HuggingFaceControllerAnyIO(HuggingFaceController):
    """
    Controller for Hugging Face Hub operations with AnyIO support.

    Provides endpoints for Hugging Face Hub operations supporting both async-io
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
                stacklevel=3,
            )

    # Override synchronous methods to warn when called from async context

    def handle_auth_request(self, request: HuggingFaceAuthRequest):
        """
        Handle authentication request to Hugging Face Hub.

        Args:
            request: Authentication request parameters

        Returns:
            Authentication response
        """
        self._warn_if_async_context("handle_auth_request")
        # Remove async keyword as this is now a sync implementation
        return super().handle_auth_request(request)

    def handle_repo_creation_request(self, request: HuggingFaceRepoCreationRequest):
        """
        Handle repository creation request on Hugging Face Hub.

        Args:
            request: Repository creation request parameters

        Returns:
            Repository creation response
        """
        self._warn_if_async_context("handle_repo_creation_request")
        return super().handle_repo_creation_request(request)

    def handle_upload_request(self, request: HuggingFaceUploadRequest):
        """
        Handle upload request to Hugging Face Hub.

        Args:
            request: Upload request parameters

        Returns:
            Upload response
        """
        self._warn_if_async_context("handle_upload_request")
        return super().handle_upload_request(request)

    def handle_download_request(self, request: HuggingFaceDownloadRequest):
        """
        Handle download request from Hugging Face Hub.

        Args:
            request: Download request parameters

        Returns:
            Download response
        """
        self._warn_if_async_context("handle_download_request")
        return super().handle_download_request(request)

    def handle_list_models_request(
    self,
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
        self._warn_if_async_context("handle_list_models_request")
        return super().handle_list_models_request(author, search, limit)

    def handle_ipfs_to_huggingface_request(self, request: IPFSHuggingFaceRequest):
        """
        Handle transfer from IPFS to Hugging Face Hub.

        Args:
            request: IPFS to Hugging Face Hub request parameters

        Returns:
            IPFS to Hugging Face Hub response
        """
        self._warn_if_async_context("handle_ipfs_to_huggingface_request")
        return super().handle_ipfs_to_huggingface_request(request)

    def handle_huggingface_to_ipfs_request(self, request: HuggingFaceIPFSRequest):
        """
        Handle transfer from Hugging Face Hub to IPFS.

        Args:
            request: Hugging Face Hub to IPFS request parameters

        Returns:
            Hugging Face Hub to IPFS response
        """
        self._warn_if_async_context("handle_huggingface_to_ipfs_request")
        return super().handle_huggingface_to_ipfs_request(request)

    def handle_status_request(self):
        """
        Handle status request for Hugging Face Hub backend.

        Returns:
            Status response
        """
        self._warn_if_async_context("handle_status_request")
        return super().handle_status_request()

    # Async versions of all methods

    async def handle_auth_request_async(self, request: HuggingFaceAuthRequest):
        """
        Handle authentication request to Hugging Face Hub asynchronously.

        Args:
            request: Authentication request parameters

        Returns:
            Authentication response
        """
        # Run the synchronous method in a thread using anyio
        return await anyio.to_thread.run_sync(
            lambda: self.huggingface_model.authenticate(token=request.token)
        )

    async def handle_repo_creation_request_async(self, request: HuggingFaceRepoCreationRequest):
        """
        Handle repository creation request on Hugging Face Hub asynchronously.

        Args:
            request: Repository creation request parameters

        Returns:
            Repository creation response
        """
        result = await anyio.to_thread.run_sync(
            lambda: self.huggingface_model.create_repository(
                repo_id=request.repo_id,
                repo_type=request.repo_type,
                private=request.private,
            )
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to create repository"),
                    "error_type": result.get("error_type", "RepositoryCreationError"),
                },
            )

        # Return successful response
        return result

    async def handle_upload_request_async(self, request: HuggingFaceUploadRequest):
        """
        Handle upload request to Hugging Face Hub asynchronously.

        Args:
            request: Upload request parameters

        Returns:
            Upload response
        """
        result = await anyio.to_thread.run_sync(
            lambda: self.huggingface_model.upload_file(
                file_path=request.file_path,
                repo_id=request.repo_id,
                path_in_repo=request.path_in_repo,
                commit_message=request.commit_message,
                repo_type=request.repo_type,
            )
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to upload file"),
                    "error_type": result.get("error_type", "UploadError"),
                },
            )

        # Return successful response
        return result

    async def handle_download_request_async(self, request: HuggingFaceDownloadRequest):
        """
        Handle download request from Hugging Face Hub asynchronously.

        Args:
            request: Download request parameters

        Returns:
            Download response
        """
        result = await anyio.to_thread.run_sync(
            lambda: self.huggingface_model.download_file(
                repo_id=request.repo_id,
                filename=request.filename,
                destination=request.destination,
                revision=request.revision,
                repo_type=request.repo_type,
            )
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to download file"),
                    "error_type": result.get("error_type", "DownloadError"),
                },
            )

        # Return successful response
        return result

    async def handle_list_models_request_async(
    self,
    author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ):
        """
        Handle list models request from Hugging Face Hub asynchronously.

        Args:
            author: Optional filter by author/organization
            search: Optional search query
            limit: Maximum number of results to return

        Returns:
            List models response
        """
        result = await anyio.to_thread.run_sync(
            lambda: self.huggingface_model.list_models(author=author, search=search, limit=limit)
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list models"),
                    "error_type": result.get("error_type", "ListModelsError"),
                },
            )

        # Return successful response
        return result

    async def handle_ipfs_to_huggingface_request_async(self, request: IPFSHuggingFaceRequest):
        """
        Handle transfer from IPFS to Hugging Face Hub asynchronously.

        Args:
            request: IPFS to Hugging Face Hub request parameters

        Returns:
            IPFS to Hugging Face Hub response
        """
        result = await anyio.to_thread.run_sync(
            lambda: self.huggingface_model.ipfs_to_huggingface(
                cid=request.cid,
                repo_id=request.repo_id,
                path_in_repo=request.path_in_repo,
                commit_message=request.commit_message,
                repo_type=request.repo_type,
                pin=request.pin,
            )
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get(
                        "error",
                        "Failed to transfer content from IPFS to Hugging Face Hub",
                    ),
                    "error_type": result.get("error_type", "IPFSToHuggingFaceError"),
                },
            )

        # Return successful response
        return result

    async def handle_huggingface_to_ipfs_request_async(self, request: HuggingFaceIPFSRequest):
        """
        Handle transfer from Hugging Face Hub to IPFS asynchronously.

        Args:
            request: Hugging Face Hub to IPFS request parameters

        Returns:
            Hugging Face Hub to IPFS response
        """
        result = await anyio.to_thread.run_sync(
            lambda: self.huggingface_model.huggingface_to_ipfs(
                repo_id=request.repo_id,
                filename=request.filename,
                pin=request.pin,
                revision=request.revision,
                repo_type=request.repo_type,
            )
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get(
                        "error",
                        "Failed to transfer content from Hugging Face Hub to IPFS",
                    ),
                    "error_type": result.get("error_type", "HuggingFaceToIPFSError"),
                },
            )

        # Return successful response
        return result

    async def handle_status_request_async(self):
        """
        Handle status request for Hugging Face Hub backend asynchronously.

        Returns:
            Status response
        """
        # Get stats from the model using anyio for potentially blocking operations
        stats = await anyio.to_thread.run_sync(self.huggingface_model.get_stats)

        # Create response with status information
        return {
            "success": True
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": 0
            "is_available": True
            "backend": "huggingface",
            "stats": stats
            "timestamp": time.time(),
        }

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        In AnyIO mode, registers the async versions of handlers.

        Args:
            router: FastAPI router to register routes with
        """
        # Authentication endpoint
        router.add_api_route(
            "/huggingface/auth",
            self.handle_auth_request_async,
            methods=["POST"],
            response_model=HuggingFaceAuthResponse,
            summary="Authenticate with Hugging Face Hub",
            description="Authenticate with Hugging Face Hub using an API token",
        )

        # Repository creation endpoint
        router.add_api_route(
            "/huggingface/repo/create",
            self.handle_repo_creation_request_async,
            methods=["POST"],
            response_model=HuggingFaceRepoCreationResponse,
            summary="Create Hugging Face Repository",
            description="Create a new repository on Hugging Face Hub",
        )

        # Upload endpoint
        router.add_api_route(
            "/huggingface/upload",
            self.handle_upload_request_async,
            methods=["POST"],
            response_model=HuggingFaceUploadResponse,
            summary="Upload to Hugging Face Hub",
            description="Upload a file to a Hugging Face Hub repository",
        )

        # Download endpoint
        router.add_api_route(
            "/huggingface/download",
            self.handle_download_request_async,
            methods=["POST"],
            response_model=HuggingFaceDownloadResponse,
            summary="Download from Hugging Face Hub",
            description="Download a file from a Hugging Face Hub repository",
        )

        # List models endpoint
        router.add_api_route(
            "/huggingface/models",
            self.handle_list_models_request_async,
            methods=["GET"],
            response_model=HuggingFaceListModelsResponse,
            summary="List Hugging Face Models",
            description="List models on Hugging Face Hub with optional filters",
        )

        # IPFS to Hugging Face endpoint
        router.add_api_route(
            "/huggingface/from_ipfs",
            self.handle_ipfs_to_huggingface_request_async,
            methods=["POST"],
            response_model=IPFSHuggingFaceResponse,
            summary="IPFS to Hugging Face Hub",
            description="Transfer content from IPFS to Hugging Face Hub",
        )

        # Hugging Face to IPFS endpoint
        router.add_api_route(
            "/huggingface/to_ipfs",
            self.handle_huggingface_to_ipfs_request_async,
            methods=["POST"],
            response_model=HuggingFaceIPFSResponse,
            summary="Hugging Face Hub to IPFS",
            description="Transfer content from Hugging Face Hub to IPFS",
        )

        # Status endpoint for testing
        router.add_api_route(
            "/storage/huggingface/status",
            self.handle_status_request_async,
            methods=["GET"],
            response_model=OperationResponse,
            summary="Hugging Face Hub Status",
            description="Get current status of the Hugging Face Hub backend",
        )

        logger.info("Hugging Face routes registered with AnyIO support")

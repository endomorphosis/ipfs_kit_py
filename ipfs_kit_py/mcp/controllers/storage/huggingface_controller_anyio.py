"""
Hugging Face Controller for the MCP server (AnyIO version).

This controller handles HTTP requests related to Hugging Face Hub operations and
delegates the business logic to the Hugging Face model using AnyIO for async operations.
"""

import logging
import time
import os
import sys
from typing import Dict, List, Any, Optional

# Import FastAPI components
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
import mcp_error_handling

# Configure logger
logger = logging.getLogger(__name__)

# Define Pydantic models for requests and responses
class HuggingFaceRequest(BaseModel):
    """Base request model for Hugging Face operations."""
    repo_id: str = Field(..., description="Repository ID (username/repo_name)")

class HuggingFaceRepoCreationRequest(BaseModel):
    """Request model for creating a repository on Hugging Face Hub."""
    repo_id: str = Field(..., description="Repository ID (username/repo_name)")
    private: bool = Field(False, description="Whether the repository should be private")
    repo_type: str = Field("dataset", description="Repository type (dataset, model, space)")
    exist_ok: bool = Field(True, description="Whether to proceed if the repository already exists")

class DownloadRequest(HuggingFaceRequest):
    """Request model for downloading from Hugging Face Hub."""
    filename: str = Field(..., description="Filename to download")
    revision: Optional[str] = Field(None, description="Git revision (branch, tag, commit)")
    local_path: Optional[str] = Field(None, description="Local path to save the file")

class UploadRequest(HuggingFaceRequest):
    """Request model for uploading to Hugging Face Hub."""
    filepath: str = Field(..., description="Path to the file to upload")
    path_in_repo: str = Field(..., description="Path in the repository to upload the file to")
    commit_message: str = Field("File uploaded via MCP API", description="Commit message")
    commit_description: Optional[str] = Field(None, description="Commit description")

class DeleteRequest(HuggingFaceRequest):
    """Request model for deleting from Hugging Face Hub."""
    path_in_repo: str = Field(..., description="Path in the repository to delete")
    commit_message: str = Field("File deleted via MCP API", description="Commit message")

class HuggingFaceResponse(BaseModel):
    """Base response model for Hugging Face operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    repo_id: str = Field(..., description="Repository ID")

class HuggingFaceController:
    """
    Controller for Hugging Face operations.

    Handles HTTP requests related to Hugging Face Hub operations and
    delegates the business logic to the Hugging Face model.
    """
    def __init__(self, huggingface_model):
        """
        Initialize the Hugging Face controller.

        Args:
            huggingface_model: Hugging Face model to use for operations
        """
        self.huggingface_model = huggingface_model
        logger.info("Hugging Face Controller (AnyIO) initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Create repository
        router.add_api_route(
            "/create-repo",
            self.create_repository,
            methods=["POST"],
            response_model=HuggingFaceResponse,
            summary="Create repository on Hugging Face Hub",
            description="Create a new repository on the Hugging Face Hub"
        )

        # Download file from Hugging Face Hub
        router.add_api_route(
            "/download",
            self.download_file,
            methods=["POST"],
            response_model=HuggingFaceResponse,
            summary="Download file from Hugging Face Hub",
            description="Download a file from a Hugging Face Hub repository"
        )

        # Upload file to Hugging Face Hub
        router.add_api_route(
            "/upload",
            self.upload_file,
            methods=["POST"],
            response_model=HuggingFaceResponse,
            summary="Upload file to Hugging Face Hub",
            description="Upload a file to a Hugging Face Hub repository"
        )

        # Delete file from Hugging Face Hub
        router.add_api_route(
            "/delete",
            self.delete_file,
            methods=["POST"],
            response_model=HuggingFaceResponse,
            summary="Delete file from Hugging Face Hub",
            description="Delete a file from a Hugging Face Hub repository"
        )

        logger.info("Hugging Face Controller (AnyIO) routes registered")

    async def create_repository(self, request: HuggingFaceRepoCreationRequest) -> Dict[str, Any]:
        """
        Create a repository on Hugging Face Hub.

        Args:
            request: Repository creation request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Creating repository: {request.repo_id}")

            # Call the model's create_repository method
            result = await self.huggingface_model.create_repository(
                repo_id=request.repo_id,
                private=request.private,
                repo_type=request.repo_type,
                exist_ok=request.exist_ok
            )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error creating repository: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "repo_id": request.repo_id,
                    "message": "Repository creation failed"
                }

            return {
                "success": True,
                "message": f"Repository {request.repo_id} created successfully",
                "repo_id": request.repo_id,
                "url": result.get("url")
            }

        except Exception as e:
            logger.error(f"Error creating repository: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo_id": request.repo_id,
                "message": "Repository creation failed due to an internal error"
            }

    async def download_file(self, request: DownloadRequest) -> Dict[str, Any]:
        """
        Download a file from Hugging Face Hub.

        Args:
            request: Download request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Downloading file {request.filename} from {request.repo_id}")

            # Call the model's download_file method
            result = await self.huggingface_model.download_file(
                repo_id=request.repo_id,
                filename=request.filename,
                revision=request.revision,
                local_dir=request.local_path
            )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error downloading file: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "repo_id": request.repo_id,
                    "message": "Download failed"
                }

            return {
                "success": True,
                "message": f"File {request.filename} downloaded successfully",
                "repo_id": request.repo_id,
                "local_path": result.get("local_path"),
                "file_size": result.get("file_size")
            }

        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo_id": request.repo_id,
                "message": "Download failed due to an internal error"
            }

    async def upload_file(self, request: UploadRequest) -> Dict[str, Any]:
        """
        Upload a file to Hugging Face Hub.

        Args:
            request: Upload request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Uploading file {request.filepath} to {request.repo_id}/{request.path_in_repo}")

            # Call the model's upload_file method
            result = await self.huggingface_model.upload_file(
                repo_id=request.repo_id,
                filepath=request.filepath,
                path_in_repo=request.path_in_repo,
                commit_message=request.commit_message,
                commit_description=request.commit_description
            )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error uploading file: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "repo_id": request.repo_id,
                    "message": "Upload failed"
                }

            return {
                "success": True,
                "message": f"File uploaded to {request.repo_id}/{request.path_in_repo}",
                "repo_id": request.repo_id,
                "commit_url": result.get("commit_url"),
                "file_url": result.get("file_url")
            }

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo_id": request.repo_id,
                "message": "Upload failed due to an internal error"
            }

    async def delete_file(self, request: DeleteRequest) -> Dict[str, Any]:
        """
        Delete a file from Hugging Face Hub.

        Args:
            request: Delete request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Deleting file {request.path_in_repo} from {request.repo_id}")

            # Call the model's delete_file method
            result = await self.huggingface_model.delete_file(
                repo_id=request.repo_id,
                path_in_repo=request.path_in_repo,
                commit_message=request.commit_message
            )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error deleting file: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "repo_id": request.repo_id,
                    "message": "Delete failed"
                }

            return {
                "success": True,
                "message": f"File {request.path_in_repo} deleted from {request.repo_id}",
                "repo_id": request.repo_id,
                "commit_url": result.get("commit_url")
            }

        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo_id": request.repo_id,
                "message": "Delete failed due to an internal error"
            }

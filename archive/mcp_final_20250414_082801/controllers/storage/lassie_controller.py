"""
Lassie Controller for the MCP server.

This controller handles HTTP requests related to Lassie operations and
delegates the business logic to the Lassie model. Lassie is a tool for
retrieving content from the Filecoin/IPFS networks.
"""

import logging
import time
from typing import List, Optional
from fastapi import (
from pydantic import BaseModel, Field

APIRouter,
    HTTPException)

# Import Pydantic models for request/response validation


# Configure logger
logger = logging.getLogger(__name__)

# Import LassieStorage


# Define Pydantic models for requests and responses
class FetchCIDRequest(BaseModel):
    """Request model for fetching content by CID."""
    cid: str = Field(..., description="Content Identifier (CID)")
    path: Optional[str] = Field(None, description="Path within the CID to fetch")
    block_limit: Optional[int] = Field(None, description="Maximum blocks to retrieve")
    protocols: Optional[List[str]] = Field(
        None, description="Protocols to use for retrieval (e.g., bitswap, graphsync)"
    )
    providers: Optional[List[str]] = Field(None, description="Specific provider multiaddrs to use")
    dag_scope: Optional[str] = Field(
        None, description="Scope of DAG to retrieve ('all', 'block', 'entity')"
    )
    output_file: Optional[str] = Field(None, description="File to write content to")
    filename: Optional[str] = Field(None, description="Name to use for file")


class RetrieveContentRequest(BaseModel):
    """Request model for retrieving content."""
    cid: str = Field(..., description="Content Identifier (CID)")
    destination: Optional[str] = Field(None, description="Destination path to save content")
    extract: bool = Field(True, description="Whether to extract CAR files automatically")
    verbose: bool = Field(False, description="Enable verbose logging")


class ExtractCARRequest(BaseModel):
    """Request model for extracting CAR files."""
    car_path: str = Field(..., description="Path to CAR file")
    output_dir: str = Field(..., description="Directory to extract content to")
    cid: Optional[str] = Field(None, description="Specific CID to extract")


class IPFSLassieRequest(BaseModel):
    """Request model for IPFS to Lassie operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    destination: Optional[str] = Field(None, description="Destination path for the content")
    extract: bool = Field(True, description="Whether to extract CAR files automatically")


class LassieIPFSRequest(BaseModel):
    """Request model for Lassie to IPFS operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")
    verbose: bool = Field(False, description="Enable verbose logging")


class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    duration_ms: Optional[float] = Field(
        None, description="Duration of the operation in milliseconds"
    )


class FetchCIDResponse(OperationResponse):
    """Response model for fetch CID operations."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID)")
    path: Optional[str] = Field(None, description="Path within the CID that was fetched")
    size_bytes: Optional[int] = Field(None, description="Size of the fetched content in bytes")
    block_count: Optional[int] = Field(None, description="Number of blocks retrieved")
    output_file: Optional[str] = Field(None, description="Path to the output file if saved")


class RetrieveContentResponse(OperationResponse):
    """Response model for retrieve content operations."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID)")
    destination: Optional[str] = Field(None, description="Destination where content was saved")
    extracted: Optional[bool] = Field(None, description="Whether the content was extracted")
    size_bytes: Optional[int] = Field(None, description="Size of the retrieved content in bytes")


class ExtractCARResponse(OperationResponse):
    """Response model for extract CAR operations."""
    car_path: Optional[str] = Field(None, description="Path to the CAR file")
    output_dir: Optional[str] = Field(None, description="Directory where content was extracted")
    extracted_files: Optional[List[str]] = Field(None, description="List of extracted files")
    root_cid: Optional[str] = Field(None, description="Root CID of the extracted content")
    size_bytes: Optional[int] = Field(None, description="Size of the extracted content in bytes")


class IPFSLassieResponse(OperationResponse):
    """Response model for IPFS to Lassie operations."""
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    destination: Optional[str] = Field(None, description="Destination path for the content")
    extracted: Optional[bool] = Field(None, description="Whether the content was extracted")
    size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")


class LassieIPFSResponse(OperationResponse):
    """Response model for Lassie to IPFS operations."""
    original_cid: Optional[str] = Field(None, description="Original Content Identifier (CID)")
    ipfs_cid: Optional[str] = Field(None, description="Content Identifier (CID) in IPFS")
    size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")
    pinned: Optional[bool] = Field(None, description="Whether the content was pinned in IPFS")


class LassieController:
    """
    Controller for Lassie operations.

    Handles HTTP requests related to Lassie operations and delegates
    the business logic to the Lassie model. Lassie is a tool for
    retrieving content from the Filecoin/IPFS networks.
    """
    def __init__(self, lassie_model):
        """
        Initialize the Lassie controller.

        Args:
            lassie_model: Lassie model to use for operations
        """
        self.lassie_model = lassie_model
        logger.info("Lassie Controller initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Fetch CID endpoint
        router.add_api_route(
            "/lassie/fetch",
            self.handle_fetch_cid_request,
            methods=["POST"],
            response_model=FetchCIDResponse,
            summary="Fetch CID with Lassie",
            description="Fetch content by CID from Filecoin/IPFS networks using Lassie",
        )

        # Retrieve content endpoint
        router.add_api_route(
            "/lassie/retrieve",
            self.handle_retrieve_content_request,
            methods=["POST"],
            response_model=RetrieveContentResponse,
            summary="Retrieve content with Lassie",
            description="Retrieve content from Filecoin/IPFS networks and extract if needed",
        )

        # Extract CAR endpoint
        router.add_api_route(
            "/lassie/extract",
            self.handle_extract_car_request,
            methods=["POST"],
            response_model=ExtractCARResponse,
            summary="Extract CAR file",
            description="Extract content from a CAR file",
        )

        # IPFS to Lassie endpoint
        router.add_api_route(
            "/lassie/from_ipfs",
            self.handle_ipfs_to_lassie_request,
            methods=["POST"],
            response_model=IPFSLassieResponse,
            summary="IPFS to Lassie",
            description="Transfer content from IPFS to a local file using Lassie",
        )

        # Lassie to IPFS endpoint
        router.add_api_route(
            "/lassie/to_ipfs",
            self.handle_lassie_to_ipfs_request,
            methods=["POST"],
            response_model=LassieIPFSResponse,
            summary="Lassie to IPFS",
            description="Retrieve content using Lassie and add to IPFS",
        )

        # Status endpoint for testing
        router.add_api_route(
            "/storage/lassie/status",
            self.handle_status_request,
            methods=["GET"],
            response_model=OperationResponse,
            summary="Lassie Status",
            description="Get current status of the Lassie backend",
        )

        logger.info("Lassie routes registered")

    async def handle_fetch_cid_request(self, request: FetchCIDRequest):
        """
        Handle fetch CID request with Lassie.

        Args:
            request: Fetch CID request parameters

        Returns:
            Fetch CID response
        """
        # Delegate to Lassie model
        result = self.lassie_model.fetch_cid(
            cid=request.cid,
            path=request.path,
            block_limit=request.block_limit,
            protocols=request.protocols,
            providers=request.providers,
            dag_scope=request.dag_scope,
            output_file=request.output_file,
            filename=request.filename,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_retrieve_content_request(self, request: RetrieveContentRequest):
        """
        Handle retrieve content request with Lassie.

        Args:
            request: Retrieve content request parameters

        Returns:
            Retrieve content response
        """
        # Delegate to Lassie model
        result = self.lassie_model.retrieve_content(
            cid=request.cid,
            destination=request.destination,
            extract=request.extract,
            verbose=request.verbose,
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_extract_car_request(self, request: ExtractCARRequest):
        """
        Handle extract CAR request.

        Args:
            request: Extract CAR request parameters

        Returns:
            Extract CAR response
        """
        # Delegate to Lassie model
        result = self.lassie_model.extract_car(
            car_path=request.car_path, output_dir=request.output_dir, cid=request.cid
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_ipfs_to_lassie_request(self, request: IPFSLassieRequest):
        """
        Handle transfer from IPFS to Lassie.

        Args:
            request: IPFS to Lassie request parameters

        Returns:
            IPFS to Lassie response
        """
        # Delegate to Lassie model
        result = self.lassie_model.ipfs_to_lassie(
            cid=request.cid, destination=request.destination, extract=request.extract
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_lassie_to_ipfs_request(self, request: LassieIPFSRequest):
        """
        Handle transfer from Lassie to IPFS.

        Args:
            request: Lassie to IPFS request parameters

        Returns:
            Lassie to IPFS response
        """
        # Delegate to Lassie model
        result = self.lassie_model.lassie_to_ipfs(
            cid=request.cid, pin=request.pin, verbose=request.verbose
        )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_status_request(self):
        """
        Handle status request for Lassie backend.

        Returns:
            Status response
        """
        # Check connection to Lassie
        connection_result = self.lassie_model.check_connection()

        # Get stats from the model
        stats = self.lassie_model.get_stats()

        # Create response with status information
        response = {
            "success": connection_result.get("success", False),
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": connection_result.get("duration_ms", 0),
            "is_available": connection_result.get("success", False),
            "backend": "lassie",
            "lassie_version": connection_result.get("version", "unknown"),
            "stats": stats
            "timestamp": time.time(),
        }

        # Add simulation info if applicable
        if connection_result.get("simulated", False):
            response["simulated"] = True
            response["note"] = "Lassie is operating in simulation mode"

        return response

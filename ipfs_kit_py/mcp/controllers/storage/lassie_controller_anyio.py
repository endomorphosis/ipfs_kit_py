
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

"""
Lassie Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to Lassie operations and
delegates the business logic to the Lassie model (AnyIO version). Lassie is a tool for
retrieving content from the Filecoin/IPFS networks.
"""

import logging
import time
import anyio
from fastapi import (
from ipfs_kit_py.mcp.controllers.storage.lassie_controller import (

APIRouter,
    HTTPException)

# Import Pydantic models for request/response validation

# Import models from synchronous controller for consistency

    FetchCIDRequest,
    RetrieveContentRequest,
    ExtractCARRequest,
    IPFSLassieRequest,
    LassieIPFSRequest,
    OperationResponse,
    FetchCIDResponse,
    RetrieveContentResponse,
    ExtractCARResponse,
    IPFSLassieResponse,
    LassieIPFSResponse,
)

# Configure logger
logger = logging.getLogger(__name__)


class LassieControllerAnyIO:
    """
    Controller for Lassie operations with AnyIO support.

    Handles HTTP requests related to Lassie operations and delegates
    the business logic to the Lassie model. Lassie is a tool for
    retrieving content from the Filecoin/IPFS networks.
    """
    def __init__(self, lassie_model):
        """
        Initialize the Lassie controller with AnyIO support.

        Args:
            lassie_model: Lassie model to use for operations
        """
        self.lassie_model = lassie_model
        logger.info("Lassie Controller (AnyIO) initialized")

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

        logger.info("Lassie routes registered (AnyIO)")

    async def handle_fetch_cid_request(self, request: FetchCIDRequest):
        """
        Handle fetch CID request with Lassie (async).

        Args:
            request: Fetch CID request parameters

        Returns:
            Fetch CID response
        """
        # Check if model has AnyIO version of the method
        if hasattr(self.lassie_model, "fetch_cid_async"):
            # Use AnyIO version
            result = await self.lassie_model.fetch_cid_async(
                cid=request.cid,
                path=request.path,
                block_limit=request.block_limit,
                protocols=request.protocols,
                providers=request.providers,
                dag_scope=request.dag_scope,
                output_file=request.output_file,
                filename=request.filename,
            )
        else:
            # Fallback to synchronous method in a thread
            result = await anyio.to_thread.run_sync(
                self.lassie_model.fetch_cid,
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/lassie_anyio",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_retrieve_content_request(self, request: RetrieveContentRequest):
        """
        Handle retrieve content request with Lassie (async).

        Args:
            request: Retrieve content request parameters

        Returns:
            Retrieve content response
        """
        # Check if model has AnyIO version of the method
        if hasattr(self.lassie_model, "retrieve_content_async"):
            # Use AnyIO version
            result = await self.lassie_model.retrieve_content_async(
                cid=request.cid,
                destination=request.destination,
                extract=request.extract,
                verbose=request.verbose,
            )
        else:
            # Fallback to synchronous method in a thread
            result = await anyio.to_thread.run_sync(
                self.lassie_model.retrieve_content,
                cid=request.cid,
                destination=request.destination,
                extract=request.extract,
                verbose=request.verbose,
            )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/lassie_anyio",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_extract_car_request(self, request: ExtractCARRequest):
        """
        Handle extract CAR request (async).

        Args:
            request: Extract CAR request parameters

        Returns:
            Extract CAR response
        """
        # Check if model has AnyIO version of the method
        if hasattr(self.lassie_model, "extract_car_async"):
            # Use AnyIO version
            result = await self.lassie_model.extract_car_async(
                car_path=request.car_path,
                output_dir=request.output_dir,
                cid=request.cid,
            )
        else:
            # Fallback to synchronous method in a thread
            result = await anyio.to_thread.run_sync(
                self.lassie_model.extract_car,
                car_path=request.car_path,
                output_dir=request.output_dir,
                cid=request.cid,
            )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/lassie_anyio",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_ipfs_to_lassie_request(self, request: IPFSLassieRequest):
        """
        Handle transfer from IPFS to Lassie (async).

        Args:
            request: IPFS to Lassie request parameters

        Returns:
            IPFS to Lassie response
        """
        # Check if model has AnyIO version of the method
        if hasattr(self.lassie_model, "ipfs_to_lassie_async"):
            # Use AnyIO version
            result = await self.lassie_model.ipfs_to_lassie_async(
                cid=request.cid,
                destination=request.destination,
                extract=request.extract,
            )
        else:
            # Fallback to synchronous method in a thread
            result = await anyio.to_thread.run_sync(
                self.lassie_model.ipfs_to_lassie,
                cid=request.cid,
                destination=request.destination,
                extract=request.extract,
            )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/lassie_anyio",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_lassie_to_ipfs_request(self, request: LassieIPFSRequest):
        """
        Handle transfer from Lassie to IPFS (async).

        Args:
            request: Lassie to IPFS request parameters

        Returns:
            Lassie to IPFS response
        """
        # Check if model has AnyIO version of the method
        if hasattr(self.lassie_model, "lassie_to_ipfs_async"):
            # Use AnyIO version
            result = await self.lassie_model.lassie_to_ipfs_async(
                cid=request.cid, pin=request.pin, verbose=request.verbose
            )
        else:
            # Fallback to synchronous method in a thread
            result = await anyio.to_thread.run_sync(
                self.lassie_model.lassie_to_ipfs,
                cid=request.cid,
                pin=request.pin,
                verbose=request.verbose,
            )

        # If operation failed, raise HTTP exception
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/lassie_anyio",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "UnknownError"),
                },
            )

        # Return successful response
        return result

    async def handle_status_request(self):
        """
        Handle status request for Lassie backend (async).

        Returns:
            Status response
        """
        # Check for async connection check method
        if hasattr(self.lassie_model, "check_connection_async"):
            connection_result = await self.lassie_model.check_connection_async()
        else:
            connection_result = await anyio.to_thread.run_sync(self.lassie_model.check_connection)

        # Check for async stats method
        if hasattr(self.lassie_model, "get_stats_async"):
            stats = await self.lassie_model.get_stats_async()
        else:
            stats = await anyio.to_thread.run_sync(self.lassie_model.get_stats)

        # Create response with status information
        return {
            "success": connection_result.get("success", False),
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": connection_result.get("duration_ms", 0),
            "is_available": connection_result.get("success", False),
            "backend": "lassie",
            "lassie_version": connection_result.get("version", "unknown"),
            "stats": stats,
            "timestamp": time.time(),
        }

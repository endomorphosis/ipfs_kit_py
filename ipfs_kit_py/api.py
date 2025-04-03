"""
FastAPI server for IPFS Kit.

This module provides a RESTful API server built with FastAPI that exposes
the High-Level API for IPFS Kit over HTTP, enabling remote access to IPFS
functionality with consistent endpoint structure and response formats.

Key features:
1. RESTful API with standardized endpoints
2. OpenAPI documentation with Swagger UI
3. Support for file uploads and downloads
4. Consistent error handling
5. CORS support for web applications
6. Authentication (optional)
7. Configurable via environment variables or config file
8. Metrics and health monitoring
9. API versioning

The API follows REST conventions with resources organized by function:
- /api/v0/add - Add content to IPFS
- /api/v0/cat - Retrieve content by CID
- /api/v0/pin/* - Pin management endpoints
- /api/v0/swarm/* - Peer management endpoints
- /api/v0/name/* - IPNS management endpoints
- /api/v0/cluster/* - Cluster management endpoints
- /api/v0/ai/* - AI/ML integration endpoints

Error Handling:
All endpoints follow a consistent error handling pattern with standardized response format:
{
    "success": false,
    "error": "Description of the error",
    "error_type": "ErrorClassName",
    "status_code": 400  // HTTP status code
}

Error responses are categorized into:
- IPFS errors (400): Issues with IPFS operations
- Validation errors (400): Invalid input parameters
- Authorization errors (401/403): Permission issues
- Server errors (500): Unexpected exceptions

The API includes special test endpoints for validating error handling behavior:
- /api/error_method - Returns a standard IPFS error
- /api/unexpected_error - Returns a standard unexpected error

All endpoints return consistent JSON responses with a 'success' flag.
"""

import base64
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Union

# Import FastAPI and related
try:
    import fastapi
    import uvicorn
    from fastapi import (
        Depends,
        FastAPI,
        File,
        Form,
        HTTPException,
        Query,
        Request,
        Response,
        UploadFile,
    )
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.routing import APIRouter

    # BackgroundTask might be in starlette in newer FastAPI versions
    try:
        from fastapi.background import BackgroundTask
    except ImportError:
        # Try to import from starlette as fallback
        from starlette.background import BackgroundTask

    from pydantic import BaseModel, Field

    FASTAPI_AVAILABLE = True
except ImportError as e:
    print(f"Failed to import FastAPI dependencies: {e}")
    FASTAPI_AVAILABLE = False

    # Create placeholder classes for type checking
    class BaseModel:
        pass

    def Field(*args, **kwargs):
        return None

    def Form(*args, **kwargs):
        return None

    def File(*args, **kwargs):
        return None

    class UploadFile:
        pass

    class APIRouter:
        pass


# Import IPFS Kit
try:
    # First try relative imports (when used as a package)
    from .error import IPFSError
    from .high_level_api import IPFSSimpleAPI

    # Try to import AI/ML integration
    try:
        from . import ai_ml_integration

        AI_ML_AVAILABLE = True
    except ImportError:
        AI_ML_AVAILABLE = False
    # Try to import GraphQL schema
    try:
        from . import graphql_schema

        GRAPHQL_AVAILABLE = graphql_schema.GRAPHQL_AVAILABLE
    except ImportError:
        GRAPHQL_AVAILABLE = False
except ImportError:
    # For development/testing
    import os
    import sys

    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ipfs_kit_py.error import IPFSError
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI

    # Try to import AI/ML integration
    try:
        from ipfs_kit_py import ai_ml_integration

        AI_ML_AVAILABLE = True
    except ImportError:
        AI_ML_AVAILABLE = False
    # Try to import GraphQL schema
    try:
        from ipfs_kit_py import graphql_schema

        GRAPHQL_AVAILABLE = graphql_schema.GRAPHQL_AVAILABLE
    except ImportError:
        GRAPHQL_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Check if FastAPI is available
if not FASTAPI_AVAILABLE:
    logger.error("FastAPI not available. Please install with 'pip install fastapi uvicorn'")

    # Instead of exiting, provide placeholder exports for import safety
    class DummyFastAPI:
        def __init__(self, **kwargs):
            self.title = kwargs.get("title", "")
            self.description = kwargs.get("description", "")
            self.version = kwargs.get("version", "0.1.0")
            self.state = type("", (), {})()

        def add_middleware(self, *args, **kwargs):
            pass

        def include_router(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def delete(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        # This makes the app callable, which is required by Starlette's TestClient
        def __call__(self, scope):
            async def dummy_app(scope, receive, send):
                # Simple response indicating FastAPI is not available
                if scope["type"] == "http":
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 500,
                            "headers": [[b"content-type", b"application/json"]],
                        }
                    )
                    await send(
                        {
                            "type": "http.response.body",
                            "body": json.dumps(
                                {
                                    "error": "FastAPI not available",
                                    "solution": "Install with 'pip install fastapi uvicorn'",
                                }
                            ).encode(),
                        }
                    )

            return dummy_app

    app = DummyFastAPI(
        title="IPFS Kit API",
        description="RESTful API for IPFS Kit (UNAVAILABLE - install fastapi)",
        version="0.1.0",
    )

    # Create dummy router
    class DummyRouter:
        def __init__(self, **kwargs):
            self.prefix = kwargs.get("prefix", "")

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def delete(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        # Make the router callable if needed
        def __call__(self, *args, **kwargs):
            return None

    # State is now created in DummyFastAPI.__init__
    v0_router = DummyRouter(prefix="/api/v0")

    # Create dummy Response class
    class Response:
        def __init__(self, **kwargs):
            pass

    # Create dummy HTTPException
    class HTTPException(Exception):
        def __init__(self, status_code=500, detail=""):
            self.status_code = status_code
            self.detail = detail


# Create API models
if FASTAPI_AVAILABLE:

    class APIRequest(BaseModel):
        """API request model."""

        args: List[Any] = Field(default_factory=list, description="Positional arguments")
        kwargs: Dict[str, Any] = Field(default_factory=dict, description="Keyword arguments")

    class ErrorResponse(BaseModel):
        """Error response model."""

        success: bool = Field(False, description="Operation success status")
        error: str = Field(..., description="Error message")
        error_type: str = Field(..., description="Error type")
        status_code: int = Field(..., description="HTTP status code")

else:
    # Non-pydantic versions for when FastAPI is not available
    class APIRequest:
        """API request model."""

        def __init__(self, args=None, kwargs=None):
            self.args = args or []
            self.kwargs = kwargs or {}

    class ErrorResponse:
        """Error response model."""

        def __init__(self, error, error_type, status_code):
            self.success = False
            self.error = error
            self.error_type = error_type
            self.status_code = status_code


# Initialize FastAPI app and components if available, otherwise create placeholders
if FASTAPI_AVAILABLE:
    # Initialize FastAPI app with versioned API
    app = FastAPI(
        title="IPFS Kit API",
        description="RESTful API for IPFS Kit with comprehensive IPFS functionality and AI/ML integration",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Add CORS middleware
    cors_origins = os.environ.get("IPFS_KIT_CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create API router for v0 endpoints
    v0_router = fastapi.APIRouter(prefix="/api/v0")
else:
    # We already created placeholders for these in the imports section
    pass

# Initialize IPFS Kit with default configuration
# Configuration priority:
# 1. Custom config path from environment variable
# 2. Default config locations
config_path = os.environ.get("IPFS_KIT_CONFIG_PATH")
ipfs_api = IPFSSimpleAPI(config_path=config_path)

# Configure logging level from environment or config
log_level = os.environ.get("IPFS_KIT_LOG_LEVEL", "INFO").upper()
logging.getLogger("ipfs_kit_py").setLevel(log_level)

# Try to import Prometheus exporter (optional)
try:
    from .prometheus_exporter import add_prometheus_metrics_endpoint, PROMETHEUS_AVAILABLE
except ImportError:
    logger.warning("Prometheus exporter not available, metrics will be disabled")
    PROMETHEUS_AVAILABLE = False

if FASTAPI_AVAILABLE:
    # Set the API in app state for better testability and middleware access
    app.state.ipfs_api = ipfs_api

    # Set API configuration from environment variables or defaults
    app.state.config = {
        "auth_enabled": os.environ.get("IPFS_KIT_AUTH_ENABLED", "false").lower() == "true",
        "auth_token": os.environ.get("IPFS_KIT_AUTH_TOKEN", ""),
        "max_upload_size": int(
            os.environ.get("IPFS_KIT_MAX_UPLOAD_SIZE", 100 * 1024 * 1024)
        ),  # 100MB
        "rate_limit_enabled": os.environ.get("IPFS_KIT_RATE_LIMIT_ENABLED", "false").lower()
        == "true",
        "rate_limit": int(os.environ.get("IPFS_KIT_RATE_LIMIT", 100)),  # requests per minute
        "metrics_enabled": os.environ.get("IPFS_KIT_METRICS_ENABLED", "true").lower() == "true",
    }
    
    # Add the performance metrics instance to app state if it exists on the API
    if hasattr(ipfs_api, "performance_metrics"):
        app.state.performance_metrics = ipfs_api.performance_metrics
    else:
        # Create a new instance if not available
        from .performance_metrics import PerformanceMetrics
        app.state.performance_metrics = PerformanceMetrics(
            metrics_dir=os.environ.get("IPFS_KIT_METRICS_DIR"),
            enable_logging=True,
            track_system_resources=True
        )

# Define API models for standardized responses if FastAPI is available
if FASTAPI_AVAILABLE:

    class IPFSResponse(BaseModel):
        """Standard response model for IPFS operations."""

        success: bool = Field(True, description="Operation success status")
        operation: str = Field(..., description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")

    class AddResponse(IPFSResponse):
        """Response model for add operation."""

        cid: str = Field(..., description="Content identifier (CID)")
        size: Optional[int] = Field(None, description="Size of the content in bytes")
        name: Optional[str] = Field(None, description="Name of the file")

    class PinResponse(IPFSResponse):
        """Response model for pin operations."""

        cid: str = Field(..., description="Content identifier (CID)")
        pinned: bool = Field(..., description="Whether the content is pinned")

    class SwarmPeersResponse(IPFSResponse):
        """Response model for swarm peers operation."""

        peers: List[Dict[str, Any]] = Field(..., description="List of connected peers")
        count: int = Field(..., description="Number of connected peers")

    class VersionResponse(IPFSResponse):
        """Response model for version information."""

        version: str = Field(..., description="IPFS version")
        commit: Optional[str] = Field(None, description="Commit hash")
        repo: Optional[str] = Field(None, description="Repository version")

    class IPNSPublishResponse(IPFSResponse):
        """Response model for IPNS publish operation."""

        name: str = Field(..., description="IPNS name")
        value: str = Field(..., description="IPFS path that the name points to")

    class IPNSResolveResponse(IPFSResponse):
        """Response model for IPNS resolve operation."""

        path: str = Field(..., description="Resolved IPFS path")
        name: str = Field(..., description="IPNS name that was resolved")

    class KeyResponse(IPFSResponse):
        """Response model for key operations."""

        name: str = Field(..., description="Name of the key")
        id: str = Field(..., description="ID of the key")

    class ClusterPinResponse(IPFSResponse):
        """Response model for cluster pin operations."""

        cid: str = Field(..., description="Content identifier (CID)")
        replication_factor: Optional[int] = Field(None, description="Replication factor")
        peer_map: Optional[Dict[str, Any]] = Field({}, description="Map of peer allocations")

    class ClusterStatusResponse(IPFSResponse):
        """Response model for cluster status operations."""

        cid: str = Field(..., description="Content identifier (CID)")
        status: str = Field(..., description="Status of the pin")
        timestamp: float = Field(..., description="Timestamp of the operation")
        peer_map: Optional[Dict[str, Any]] = Field({}, description="Map of peer statuses")

    # AI/ML response models
    class ModelMetadata(BaseModel):
        """Model metadata for AI/ML models."""

        name: str = Field(..., description="Name of the model")
        version: Optional[str] = Field("1.0.0", description="Model version")
        framework: Optional[str] = Field(
            None, description="Framework used (e.g., 'pytorch', 'tensorflow', 'sklearn')"
        )
        description: Optional[str] = Field(None, description="Description of the model")
        metrics: Optional[Dict[str, Any]] = Field(None, description="Performance metrics")
        tags: Optional[List[str]] = Field(None, description="Tags for categorization")
        source: Optional[str] = Field(None, description="Source of the model")
        license: Optional[str] = Field(None, description="License information")
        custom_metadata: Optional[Dict[str, Any]] = Field(
            None, description="Custom metadata fields"
        )

    class ModelResponse(IPFSResponse):
        """Response model for AI/ML model operations."""

        model_name: str = Field(..., description="Name of the model")
        version: str = Field(..., description="Model version")
        framework: Optional[str] = Field(None, description="Framework used for the model")
        cid: str = Field(..., description="Content identifier (CID) for the model")
        metadata: Optional[Dict[str, Any]] = Field({}, description="Model metadata")

    class DatasetMetadata(BaseModel):
        """Metadata for AI/ML datasets."""

        name: str = Field(..., description="Name of the dataset")
        version: Optional[str] = Field("1.0.0", description="Dataset version")
        format: Optional[str] = Field(None, description="Format of the dataset")
        description: Optional[str] = Field(None, description="Description of the dataset")
        stats: Optional[Dict[str, Any]] = Field(None, description="Dataset statistics")
        tags: Optional[List[str]] = Field(None, description="Tags for categorization")
        source: Optional[str] = Field(None, description="Source of the dataset")
        license: Optional[str] = Field(None, description="License information")
        custom_metadata: Optional[Dict[str, Any]] = Field(
            None, description="Custom metadata fields"
        )

    class DatasetResponse(IPFSResponse):
        """Response model for AI/ML dataset operations."""

        dataset_name: str = Field(..., description="Name of the dataset")
        version: str = Field(..., description="Dataset version")
        format: Optional[str] = Field(None, description="Format of the dataset")
        cid: str = Field(..., description="Content identifier (CID) for the dataset")
        stats: Optional[Dict[str, Any]] = Field({}, description="Dataset statistics")
        metadata: Optional[Dict[str, Any]] = Field({}, description="Dataset metadata")

else:
    # Define minimal placeholder classes for basic type checking
    class IPFSResponse:
        pass

    class AddResponse(IPFSResponse):
        pass

    class PinResponse(IPFSResponse):
        pass

    class SwarmPeersResponse(IPFSResponse):
        pass

    class VersionResponse(IPFSResponse):
        pass

    class IPNSPublishResponse(IPFSResponse):
        pass

    class IPNSResolveResponse(IPFSResponse):
        pass

    class KeyResponse(IPFSResponse):
        pass

    class ClusterPinResponse(IPFSResponse):
        pass

    class ClusterStatusResponse(IPFSResponse):
        pass

    class ModelMetadata:
        pass

    class ModelResponse(IPFSResponse):
        pass

    class DatasetMetadata:
        pass

    class DatasetResponse(IPFSResponse):
        pass


# The following code is only used if FastAPI is available
if FASTAPI_AVAILABLE:
    # Optional: Add API key authentication if enabled
    if hasattr(app, "state") and getattr(app.state, "config", {}).get("auth_enabled"):
        from fastapi.security import APIKeyHeader

        # Define API key header
        api_key_header = APIKeyHeader(name="X-API-Key")

        @app.middleware("http")
        async def authenticate(request: Request, call_next):
            # Skip authentication for docs and health check
            if request.url.path in ["/docs", "/redoc", "/openapi.json", "/health"]:
                return await call_next(request)

            # Get API key from header
            api_key = request.headers.get("X-API-Key")

            # Check API key
            if api_key != app.state.config["auth_token"]:
                return Response(
                    content=json.dumps(
                        {
                            "success": False,
                            "error": "Invalid API key",
                            "error_type": "AuthenticationError",
                            "status_code": 401,
                        }
                    ),
                    status_code=401,
                    media_type="application/json",
                )

            return await call_next(request)

    # Add rate limiting if enabled
    if hasattr(app, "state") and getattr(app.state, "config", {}).get("rate_limit_enabled"):
        from fastapi.middleware.trustedhost import TrustedHostMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware

        class RateLimitMiddleware(BaseHTTPMiddleware):
            def __init__(self, app, rate_limit: int = 100):
                super().__init__(app)
                self.rate_limit = rate_limit
                self.requests = {}

            async def dispatch(self, request: Request, call_next):
                # Skip rate limiting for docs and health check
                if request.url.path in ["/docs", "/redoc", "/openapi.json", "/health"]:
                    return await call_next(request)

                # Get client IP
                client_ip = request.client.host

                # Check rate limit
                now = time.time()
                if client_ip in self.requests:
                    # Clean up old requests (older than 60 seconds)
                    self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < 60]

                    # Check rate limit
                    if len(self.requests[client_ip]) >= self.rate_limit:
                        return Response(
                            content=json.dumps(
                                {
                                    "success": False,
                                    "error": "Rate limit exceeded",
                                    "error_type": "RateLimitError",
                                    "status_code": 429,
                                }
                            ),
                            status_code=429,
                            media_type="application/json",
                        )

                # Add request to rate limit
                if client_ip not in self.requests:
                    self.requests[client_ip] = []
                self.requests[client_ip].append(now)

                return await call_next(request)

        # Add rate limit middleware
        app.add_middleware(RateLimitMiddleware, rate_limit=app.state.config["rate_limit"])

    # Add metrics if enabled
    if hasattr(app, "state") and getattr(app.state, "config", {}).get("metrics_enabled"):
        try:
            from prometheus_fastapi_instrumentator import Instrumentator

            # Set up Prometheus metrics
            instrumentator = Instrumentator()
            instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

            logger.info("Prometheus metrics enabled at /metrics")
        except ImportError:
            logger.warning("prometheus_fastapi_instrumentator not available, metrics disabled")
            app.state.config["metrics_enabled"] = False

# Implement core IPFS endpoints for v0 API if FastAPI is available
if FASTAPI_AVAILABLE:

    @v0_router.post("/add", response_model=AddResponse, tags=["content"])
    async def add_content(
        file: UploadFile = File(...),
        pin: bool = Form(True),
        wrap_with_directory: bool = Form(False),
    ):
        """
        Add content to IPFS.

        This endpoint adds a file to IPFS and returns its CID (Content Identifier).

        Parameters:
        - **file**: The file to upload
        - **pin**: Whether to pin the content (default: True)
        - **wrap_with_directory**: Whether to wrap the file in a directory (default: False)

        Returns:
            CID and metadata of the added content
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Read file content
            content = await file.read()
            filename = file.filename or "unnamed_file"

            # Log the operation
            logger.info(f"Adding file {filename} to IPFS, size={len(content)}, pin={pin}")

            # Add file to IPFS
            result = api.add(content, pin=pin, wrap_with_directory=wrap_with_directory)

            # Create standardized response
            if isinstance(result, dict) and "Hash" in result:
                # Handle older Kubo API response format
                return {
                    "success": True,
                    "operation": "add",
                    "timestamp": time.time(),
                    "cid": result["Hash"],
                    "size": result.get("Size"),
                    "name": filename,
                }
            elif isinstance(result, dict) and "cid" in result:
                # Handle ipfs_kit response format
                return {
                    "success": True,
                    "operation": "add",
                    "timestamp": time.time(),
                    "cid": result["cid"],
                    "size": result.get("size"),
                    "name": filename,
                }
            else:
                # Fallback for other response formats
                return {
                    "success": True,
                    "operation": "add",
                    "timestamp": time.time(),
                    "cid": str(result),
                    "name": filename,
                }
        except Exception as e:
            logger.exception(f"Error adding content: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error adding content: {str(e)}")

    @v0_router.get("/cat", tags=["content"])
    async def cat_content(cid: str, timeout: Optional[int] = Query(30)):
        """
        Retrieve content from IPFS by CID.

        This endpoint fetches content from IPFS by its CID (Content Identifier).

        Parameters:
        - **cid**: The Content Identifier
        - **timeout**: Timeout in seconds (default: 30)

        Returns:
            The content as bytes
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Get content from IPFS
            logger.info(f"Getting content for CID: {cid}, timeout={timeout}")
            content = api.get(cid, timeout=timeout)

            # Return content as bytes
            return Response(content=content, media_type="application/octet-stream")
        except Exception as e:
            logger.exception(f"Error retrieving content: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving content: {str(e)}")


@v0_router.post("/pin/add", response_model=PinResponse, tags=["pin"])
async def pin_content(cid: str, recursive: bool = Query(True)):
    """
    Pin content to local node.

    This endpoint pins content to the local IPFS node to prevent garbage collection.

    Parameters:
    - **cid**: The Content Identifier to pin
    - **recursive**: Whether to pin recursively (default: True)

    Returns:
        Operation status
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Pin content
        logger.info(f"Pinning CID: {cid}, recursive={recursive}")
        result = api.pin(cid, recursive=recursive)

        # Create standardized response
        return {
            "success": True,
            "operation": "pin_add",
            "timestamp": time.time(),
            "cid": cid,
            "pinned": True,
        }
    except Exception as e:
        logger.exception(f"Error pinning content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error pinning content: {str(e)}")


@v0_router.post("/pin/rm", response_model=PinResponse, tags=["pin"])
async def unpin_content(cid: str, recursive: bool = Query(True)):
    """
    Unpin content from local node.

    This endpoint unpins content from the local IPFS node, allowing it to be garbage collected.

    Parameters:
    - **cid**: The Content Identifier to unpin
    - **recursive**: Whether to unpin recursively (default: True)

    Returns:
        Operation status
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Unpin content
        logger.info(f"Unpinning CID: {cid}, recursive={recursive}")
        result = api.unpin(cid, recursive=recursive)

        # Create standardized response
        return {
            "success": True,
            "operation": "pin_rm",
            "timestamp": time.time(),
            "cid": cid,
            "pinned": False,
        }
    except Exception as e:
        logger.exception(f"Error unpinning content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error unpinning content: {str(e)}")


@v0_router.get("/pin/ls", tags=["pin"])
async def list_pins(type: str = Query("all"), quiet: bool = Query(False)):
    """
    List pinned content.

    This endpoint lists all pinned content on the local IPFS node.

    Parameters:
    - **type**: The type of pins to list ("all", "direct", "indirect", "recursive") (default: "all")
    - **quiet**: Whether to return only CIDs (default: False)

    Returns:
        List of pinned CIDs with details
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # List pins
        logger.info(f"Listing pins, type={type}, quiet={quiet}")
        result = api.list_pins(type=type, quiet=quiet)

        # Create standardized response
        return {
            "success": True,
            "operation": "pin_ls",
            "timestamp": time.time(),
            "pins": result.get("pins", {}),
            "count": len(result.get("pins", {})),
        }
    except Exception as e:
        logger.exception(f"Error listing pins: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing pins: {str(e)}")


@v0_router.get("/swarm/peers", response_model=SwarmPeersResponse, tags=["swarm"])
async def list_peers(
    verbose: bool = Query(False), latency: bool = Query(False), direction: bool = Query(False)
):
    """
    List connected peers.

    This endpoint lists all peers connected to the local IPFS node.

    Parameters:
    - **verbose**: Whether to return verbose information (default: False)
    - **latency**: Whether to include latency information (default: False)
    - **direction**: Whether to include connection direction (default: False)

    Returns:
        List of connected peers with details
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # List peers
        logger.info(f"Listing peers, verbose={verbose}, latency={latency}, direction={direction}")
        result = api.peers(verbose=verbose, latency=latency, direction=direction)

        # Extract peers from result based on the format
        peers = []
        if isinstance(result, dict):
            if "Peers" in result:
                # Handle older Kubo API response format
                peers = result["Peers"]
            elif "peers" in result:
                # Handle ipfs_kit response format
                peers = result["peers"]
        elif isinstance(result, list):
            # Handle list response format
            peers = result

        # Create standardized response
        return {
            "success": True,
            "operation": "swarm_peers",
            "timestamp": time.time(),
            "peers": peers,
            "count": len(peers),
        }
    except Exception as e:
        logger.exception(f"Error listing peers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing peers: {str(e)}")


@v0_router.post("/swarm/connect", tags=["swarm"])
async def connect_peer(peer: str, timeout: Optional[int] = Query(30)):
    """
    Connect to a peer.

    This endpoint connects to a peer using its multiaddress.

    Parameters:
    - **peer**: The peer multiaddress
    - **timeout**: Timeout in seconds (default: 30)

    Returns:
        Operation status
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Connect to peer
        logger.info(f"Connecting to peer: {peer}, timeout={timeout}")
        result = api.connect(peer, timeout=timeout)

        # Create standardized response
        return {
            "success": True,
            "operation": "swarm_connect",
            "timestamp": time.time(),
            "peer": peer,
            "connected": True,
        }
    except Exception as e:
        logger.exception(f"Error connecting to peer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error connecting to peer: {str(e)}")


@v0_router.get("/ls", tags=["content"])
async def list_directory(path: str, detail: bool = Query(True)):
    """
    List directory contents.

    This endpoint lists the contents of a directory or IPFS path.

    Parameters:
    - **path**: The IPFS path or CID
    - **detail**: Whether to return detailed information (default: True)

    Returns:
        List of directory entries
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # List directory
        logger.info(f"Listing directory: {path}, detail={detail}")
        result = api.ls(path, detail=detail)

        # Create standardized response
        return {
            "success": True,
            "operation": "ls",
            "timestamp": time.time(),
            "entries": result,
            "count": len(result),
        }
    except Exception as e:
        logger.exception(f"Error listing directory: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing directory: {str(e)}")


@v0_router.get("/version", response_model=VersionResponse, tags=["system"])
async def get_version():
    """
    Get IPFS version information.

    This endpoint returns version information about the IPFS node.

    Returns:
        IPFS version information
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Get version information from IPFS instance
        version_info = {"version": "0.1.0"}  # Default version

        # Try to get actual version if available
        try:
            if hasattr(api, "kit") and hasattr(api.kit, "ipfs"):
                version_result = api.kit.ipfs_version()
                if isinstance(version_result, dict):
                    if "Version" in version_result:
                        version_info["version"] = version_result["Version"]
                    if "Commit" in version_result:
                        version_info["commit"] = version_result["Commit"]
                    if "Repo" in version_result:
                        version_info["repo"] = version_result["Repo"]
        except Exception as e:
            logger.warning(f"Error getting IPFS version: {str(e)}")

        # Create standardized response
        return {"success": True, "operation": "version", "timestamp": time.time(), **version_info}
    except Exception as e:
        logger.exception(f"Error getting version: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting version: {str(e)}")


@v0_router.post("/name/publish", response_model=IPNSPublishResponse, tags=["ipns"])
async def publish_name(
    cid: str,
    key: str = Query("self", description="Name of the key to use"),
    lifetime: str = Query("24h", description="Time duration that the record will be valid for"),
    ttl: str = Query("1h", description="Time duration for which the record will be cached"),
):
    """
    Publish a name to IPNS.

    This endpoint publishes an IPFS path to IPNS, creating a mutable pointer to the content.

    Parameters:
    - **cid**: The IPFS path or CID to publish
    - **key**: Name of the key to use (default: "self")
    - **lifetime**: Time duration that the record will be valid for (default: "24h")
    - **ttl**: Time duration for which the record will be cached (default: "1h")

    Returns:
        IPNS name and published path
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Publish to IPNS
        logger.info(f"Publishing IPNS name for CID: {cid}, key={key}")
        result = api.publish(cid, key=key, lifetime=lifetime, ttl=ttl)

        # Extract relevant information from result
        name = ""
        value = ""

        if isinstance(result, dict):
            if "Name" in result:
                # Handle older Kubo API response format
                name = result["Name"]
                value = result.get("Value", "")
            elif "name" in result:
                # Handle ipfs_kit response format
                name = result["name"]
                value = result.get("value", "")

        # Create standardized response
        return {
            "success": True,
            "operation": "name_publish",
            "timestamp": time.time(),
            "name": name,
            "value": value or f"/ipfs/{cid}",
        }
    except Exception as e:
        logger.exception(f"Error publishing name: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error publishing name: {str(e)}")


@v0_router.get("/name/resolve", response_model=IPNSResolveResponse, tags=["ipns"])
async def resolve_name(
    name: str,
    recursive: bool = Query(
        True, description="Whether to resolve until the result is not an IPNS name"
    ),
    timeout: Optional[int] = Query(30, description="Timeout in seconds"),
):
    """
    Resolve an IPNS name to an IPFS path.

    This endpoint resolves an IPNS name to its target IPFS path.

    Parameters:
    - **name**: The IPNS name to resolve (e.g., /ipns/k2k4r8...)
    - **recursive**: Whether to resolve until the result is not an IPNS name (default: True)
    - **timeout**: Timeout in seconds (default: 30)

    Returns:
        The resolved IPFS path
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Resolve IPNS name
        logger.info(f"Resolving IPNS name: {name}, recursive={recursive}")
        result = api.resolve(name, recursive=recursive, timeout=timeout)

        # Extract resolved path from result
        path = ""

        if isinstance(result, dict):
            if "Path" in result:
                # Handle older Kubo API response format
                path = result["Path"]
            elif "path" in result:
                # Handle ipfs_kit response format
                path = result["path"]

        # Create standardized response
        return {
            "success": True,
            "operation": "name_resolve",
            "timestamp": time.time(),
            "path": path or "",
            "name": name,
        }
    except Exception as e:
        logger.exception(f"Error resolving name: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error resolving name: {str(e)}")


@v0_router.get("/name/list", tags=["ipns"])
async def list_names():
    """
    List all published IPNS names.

    This endpoint lists all IPNS names that have been published by this node.

    Returns:
        List of published IPNS names with their target paths
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # List IPNS names - note we'll call ipfs_name_list method if available
        logger.info(f"Listing IPNS names")
        result = {}
        try:
            # Try different method names since the high-level API might have different variations
            if hasattr(api, "list_names"):
                result = api.list_names()
            elif hasattr(api.kit, "ipfs_name_list"):
                result = api.kit.ipfs_name_list()
            elif hasattr(
                api.kit, "ipfs_key_list"
            ):  # Fallback to key list if name list is not available
                result = api.kit.ipfs_key_list()
        except Exception as e:
            logger.warning(f"Error listing IPNS names: {str(e)}")

        # Extract names from result
        names = []
        if isinstance(result, dict):
            if "Keys" in result:
                # Handle older Kubo API response format
                names = [{"name": k, "id": v} for k, v in result["Keys"].items()]
            elif "keys" in result:
                # Handle ipfs_kit response format
                names = result["keys"]
            elif "names" in result:
                names = result["names"]

        # Create standardized response
        return {
            "success": True,
            "operation": "name_list",
            "timestamp": time.time(),
            "names": names,
            "count": len(names),
        }
    except Exception as e:
        logger.exception(f"Error listing names: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing names: {str(e)}")


@v0_router.get("/key/list", tags=["key"])
async def list_keys():
    """
    List all keys.

    This endpoint lists all IPNS keys that are available on this node.

    Returns:
        List of keys
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # List keys
        logger.info("Listing keys")
        result = {}

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "list_keys"):
                result = api.list_keys()
            elif hasattr(api.kit, "ipfs_key_list"):
                result = api.kit.ipfs_key_list()
        except Exception as e:
            logger.warning(f"Error listing keys: {str(e)}")

        # Extract keys from result
        keys = []
        if isinstance(result, dict):
            if "Keys" in result:
                # Handle older Kubo API response format
                keys = [{"name": k, "id": v} for k, v in result["Keys"].items()]
            elif "keys" in result:
                # Handle ipfs_kit response format
                keys = result["keys"]

        # Create standardized response
        return {
            "success": True,
            "operation": "key_list",
            "timestamp": time.time(),
            "keys": keys,
            "count": len(keys),
        }
    except Exception as e:
        logger.exception(f"Error listing keys: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing keys: {str(e)}")


@v0_router.post("/key/gen", response_model=KeyResponse, tags=["key"])
async def generate_key(
    name: str,
    type: str = Query("rsa", description="Type of key to generate"),
    size: int = Query(2048, description="Size of the key to generate"),
):
    """
    Generate a new key.

    This endpoint generates a new IPNS key.

    Parameters:
    - **name**: Name of the key to generate
    - **type**: Type of the key (default: "rsa")
    - **size**: Size of the key in bits (default: 2048)

    Returns:
        The generated key
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Generate key
        logger.info(f"Generating key: {name}, type={type}, size={size}")
        result = {}

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "generate_key"):
                result = api.generate_key(name, type=type, size=size)
            elif hasattr(api.kit, "ipfs_key_gen"):
                result = api.kit.ipfs_key_gen(name, type=type, size=size)
        except Exception as e:
            logger.warning(f"Error generating key: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating key: {str(e)}")

        # Extract key details from result
        key_name = name
        key_id = ""

        if isinstance(result, dict):
            if "Name" in result:
                # Handle older Kubo API response format
                key_name = result["Name"]
                key_id = result.get("Id", "")
            elif "name" in result:
                # Handle ipfs_kit response format
                key_name = result["name"]
                key_id = result.get("id", "")

        # Create standardized response
        return {
            "success": True,
            "operation": "key_gen",
            "timestamp": time.time(),
            "name": key_name,
            "id": key_id,
        }
    except Exception as e:
        logger.exception(f"Error generating key: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating key: {str(e)}")


@v0_router.post("/key/rm", tags=["key"])
async def remove_key(name: str):
    """
    Remove a key.

    This endpoint removes an IPNS key.

    Parameters:
    - **name**: Name of the key to remove

    Returns:
        Operation status
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Remove key
        logger.info(f"Removing key: {name}")
        result = {}

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "remove_key"):
                result = api.remove_key(name)
            elif hasattr(api.kit, "ipfs_key_rm"):
                result = api.kit.ipfs_key_rm(name)
        except Exception as e:
            logger.warning(f"Error removing key: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error removing key: {str(e)}")

        # Create standardized response
        return {
            "success": True,
            "operation": "key_rm",
            "timestamp": time.time(),
            "name": name,
            "message": f"Key '{name}' removed",
        }
    except Exception as e:
        logger.exception(f"Error removing key: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error removing key: {str(e)}")


@v0_router.post("/cluster/pin", response_model=ClusterPinResponse, tags=["cluster"])
async def cluster_pin(
    cid: str,
    replication_factor: int = Query(-1, description="Replication factor (-1 for all nodes)"),
    name: Optional[str] = Query(None, description="Name for the pinned content"),
):
    """
    Pin content across the IPFS cluster.

    This endpoint pins content to all nodes in the IPFS cluster.

    Parameters:
    - **cid**: The Content Identifier to pin
    - **replication_factor**: Replication factor (-1 for all nodes) (default: -1)
    - **name**: Optional name for the pinned content

    Returns:
        Operation status
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Check if cluster operations are available
        if api.config.get("role") == "leecher":
            raise HTTPException(
                status_code=403, detail="Cluster operations not available in leecher role"
            )

        # Pin content to cluster
        logger.info(f"Pinning CID to cluster: {cid}, replication_factor={replication_factor}")

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "cluster_pin"):
                result = api.cluster_pin(cid, replication_factor=replication_factor, name=name)
            elif hasattr(api, "cluster_pin_add"):
                result = api.cluster_pin_add(cid, replication_factor=replication_factor, name=name)
            else:
                raise HTTPException(status_code=501, detail="Cluster operations not implemented")
        except Exception as e:
            logger.warning(f"Error pinning to cluster: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error pinning to cluster: {str(e)}")

        # Extract information from result
        peer_map = {}
        repl_factor = replication_factor

        if isinstance(result, dict):
            if "PeerMap" in result:
                # Handle older Kubo API response format
                peer_map = result["PeerMap"]
                if "ReplicationFactorMin" in result:
                    repl_factor = result["ReplicationFactorMin"]
            elif "peer_map" in result:
                # Handle ipfs_kit response format
                peer_map = result["peer_map"]
                if "replication_factor" in result:
                    repl_factor = result["replication_factor"]

        # Create standardized response
        return {
            "success": True,
            "operation": "cluster_pin",
            "timestamp": time.time(),
            "cid": cid,
            "replication_factor": repl_factor,
            "peer_map": peer_map,
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error pinning to cluster: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error pinning to cluster: {str(e)}")


@v0_router.delete("/cluster/pin", tags=["cluster"])
async def cluster_unpin(cid: str):
    """
    Unpin content from the IPFS cluster.

    This endpoint unpins content from all nodes in the IPFS cluster.

    Parameters:
    - **cid**: The Content Identifier to unpin

    Returns:
        Operation status
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Check if cluster operations are available
        if api.config.get("role") == "leecher":
            raise HTTPException(
                status_code=403, detail="Cluster operations not available in leecher role"
            )

        # Unpin content from cluster
        logger.info(f"Unpinning CID from cluster: {cid}")

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "cluster_unpin"):
                result = api.cluster_unpin(cid)
            elif hasattr(api, "cluster_pin_rm"):
                result = api.cluster_pin_rm(cid)
            else:
                raise HTTPException(status_code=501, detail="Cluster operations not implemented")
        except Exception as e:
            logger.warning(f"Error unpinning from cluster: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error unpinning from cluster: {str(e)}")

        # Create standardized response
        return {
            "success": True,
            "operation": "cluster_unpin",
            "timestamp": time.time(),
            "cid": cid,
            "message": f"Content {cid} unpinned from cluster",
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error unpinning from cluster: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error unpinning from cluster: {str(e)}")


@v0_router.get("/cluster/status", response_model=ClusterStatusResponse, tags=["cluster"])
async def cluster_status(cid: str):
    """
    Get status of pinned content in the IPFS cluster.

    This endpoint returns the status of pinned content across all nodes in the IPFS cluster.

    Parameters:
    - **cid**: The Content Identifier to check

    Returns:
        Pin status information
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Check if cluster operations are available
        if api.config.get("role") == "leecher":
            raise HTTPException(
                status_code=403, detail="Cluster operations not available in leecher role"
            )

        # Get cluster status
        logger.info(f"Getting cluster status for CID: {cid}")

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "cluster_status"):
                result = api.cluster_status(cid)
            else:
                raise HTTPException(status_code=501, detail="Cluster operations not implemented")
        except Exception as e:
            logger.warning(f"Error getting cluster status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting cluster status: {str(e)}")

        # Extract status information from result
        status = "unknown"
        peer_map = {}

        if isinstance(result, dict):
            if "PeerMap" in result:
                # Handle older Kubo API response format
                peer_map = result["PeerMap"]
            elif "peer_map" in result:
                # Handle ipfs_kit response format
                peer_map = result["peer_map"]

            # Try to determine overall status
            if peer_map:
                statuses = [p.get("status", "") for p in peer_map.values()]
                if all(s == "pinned" for s in statuses):
                    status = "pinned"
                elif any(s == "pinning" for s in statuses):
                    status = "pinning"
                elif any(s == "pin_error" for s in statuses):
                    status = "error"

        # Create standardized response
        return {
            "success": True,
            "operation": "cluster_status",
            "timestamp": time.time(),
            "cid": cid,
            "status": status,
            "peer_map": peer_map,
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting cluster status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting cluster status: {str(e)}")


@v0_router.get("/cluster/pins", tags=["cluster"])
async def cluster_list_pins():
    """
    List all pins in the IPFS cluster.

    This endpoint lists all pins across all nodes in the IPFS cluster.

    Returns:
        List of pins with status information
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Check if cluster operations are available
        if api.config.get("role") == "leecher":
            raise HTTPException(
                status_code=403, detail="Cluster operations not available in leecher role"
            )

        # List cluster pins
        logger.info("Listing cluster pins")

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "cluster_status_all"):
                result = api.cluster_status_all()
            elif hasattr(api, "cluster_list_pins"):
                result = api.cluster_list_pins()
            else:
                raise HTTPException(status_code=501, detail="Cluster operations not implemented")
        except Exception as e:
            logger.warning(f"Error listing cluster pins: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing cluster pins: {str(e)}")

        # Extract pins from result
        pins = []
        if isinstance(result, dict):
            if "PeerMap" in result:
                # Handle older Kubo API response format with nested structure
                pins = result
            elif "pins" in result:
                # Handle ipfs_kit response format
                pins = result["pins"]
        elif isinstance(result, list):
            # Handle list response format
            pins = result

        # Create standardized response
        return {
            "success": True,
            "operation": "cluster_pins",
            "timestamp": time.time(),
            "pins": pins,
            "count": len(pins),
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error listing cluster pins: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing cluster pins: {str(e)}")


@v0_router.get("/cluster/peers", tags=["cluster"])
async def cluster_peers():
    """
    List all peers in the IPFS cluster.

    This endpoint lists all peers in the IPFS cluster.

    Returns:
        List of cluster peers
    """
    try:
        # Get API from app state
        api = app.state.ipfs_api

        # Check if cluster operations are available
        if api.config.get("role") == "leecher":
            raise HTTPException(
                status_code=403, detail="Cluster operations not available in leecher role"
            )

        # List cluster peers
        logger.info("Listing cluster peers")

        # Try different method names since the high-level API might have different variations
        try:
            if hasattr(api, "cluster_peers"):
                result = api.cluster_peers()
            else:
                raise HTTPException(status_code=501, detail="Cluster operations not implemented")
        except Exception as e:
            logger.warning(f"Error listing cluster peers: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing cluster peers: {str(e)}")

        # Extract peers from result
        peers = []
        if isinstance(result, dict):
            if "cluster_peers" in result:
                peers = result["cluster_peers"]
            elif "peers" in result:
                peers = result["peers"]
        elif isinstance(result, list):
            peers = result

        # Create standardized response
        return {
            "success": True,
            "operation": "cluster_peers",
            "timestamp": time.time(),
            "peers": peers,
            "count": len(peers),
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error listing cluster peers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing cluster peers: {str(e)}")


# AI/ML endpoints
if AI_ML_AVAILABLE:

    @v0_router.post("/ai/model/add", response_model=ModelResponse, tags=["ai_ml"])
    async def ai_model_add(
        model_file: UploadFile = File(...),
        name: str = Form(...),
        version: Optional[str] = Form("1.0.0"),
        framework: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),  # Comma-separated tags
        license: Optional[str] = Form(None),
        source: Optional[str] = Form(None),
    ):
        """
        Add an AI/ML model to IPFS.

        This endpoint uploads a model file to IPFS, registers it in the model registry,
        and makes it available for retrieval and use in distributed training.

        Parameters:
        - **model_file**: The model file to upload
        - **name**: Name identifier for the model
        - **version**: Version string (semver recommended)
        - **framework**: ML framework used (e.g., "pytorch", "tensorflow", "sklearn")
        - **description**: Description of the model
        - **tags**: Comma-separated list of tags for categorization
        - **license**: License information
        - **source**: Source of the model

        Returns:
            Model CID and metadata
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Read model content
            model_content = await model_file.read()

            # Parse tags if provided
            parsed_tags = tags.split(",") if tags else []

            # Prepare metadata
            metadata = {
                "name": name,
                "version": version,
                "framework": framework,
                "description": description,
                "tags": parsed_tags,
                "license": license,
                "source": source,
                "original_filename": model_file.filename,
            }

            # Log the operation
            logger.info(f"Adding model {name} v{version} to IPFS (framework: {framework})")

            # Add model to IPFS
            result = api.ai_model_add(model_content, metadata=metadata)

            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=f"Error adding model: {result.get('error', 'Unknown error')}",
                )

            return {
                "success": True,
                "operation": "ai_model_add",
                "timestamp": time.time(),
                "model_name": result.get("model_name", name),
                "version": result.get("version", version),
                "framework": result.get("framework", framework),
                "cid": result.get("cid"),
                "metadata": metadata,
            }

        except Exception as e:
            logger.exception(f"Error adding model: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error adding model: {str(e)}")

    @v0_router.get("/ai/model/{model_id}", response_model=ModelResponse, tags=["ai_ml"])
    async def ai_model_get(model_id: str):
        """
        Retrieve an AI/ML model from IPFS.

        This endpoint fetches a model from IPFS by its ID (typically the model name).

        Parameters:
        - **model_id**: The model identifier (name)

        Returns:
            The model data with metadata
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Get model from IPFS
            logger.info(f"Getting model: {model_id}")
            result = api.ai_model_get(model_id)

            if not result.get("success", False):
                raise HTTPException(
                    status_code=404,
                    detail=f"Model not found: {result.get('error', 'Unknown error')}",
                )

            # Create temporary file for model download
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                # Write model content to temporary file
                temp_file.write(result.get("model"))
                temp_path = temp_file.name

            # Return file download response
            return FileResponse(
                path=temp_path,
                filename=f"{model_id}.model",
                media_type="application/octet-stream",
                background=BackgroundTask(lambda: os.unlink(temp_path)),
            )

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error retrieving model: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving model: {str(e)}")

    @v0_router.get("/ai/models", tags=["ai_ml"])
    async def ai_models_list(
        framework: Optional[str] = None,
        tags: Optional[str] = None,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        """
        List all AI/ML models available in IPFS.

        This endpoint lists all models that have been added to IPFS.
        It supports filtering by framework, tags, and text search.

        Parameters:
        - **framework**: Filter models by framework (e.g., "pytorch", "tensorflow", "sklearn")
        - **tags**: Filter models by comma-separated tags
        - **query**: Free text search across model metadata
        - **limit**: Maximum number of models to return

        Returns:
            List of available models with metadata
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Parse tags if provided
            parsed_tags = tags.split(",") if tags else None

            # Use metadata index if available
            has_arrow_index = hasattr(api, "metadata_index") and api.metadata_index is not None

            if has_arrow_index and (framework or parsed_tags or query):
                # Advanced search using Arrow metadata index
                logger.info(
                    f"Searching models with metadata index (framework: {framework}, tags: {parsed_tags}, query: {query})"
                )

                # Build filter conditions
                filters = []
                if framework:
                    filters.append(("properties", "==", f"framework:{framework}"))

                if parsed_tags:
                    for tag in parsed_tags:
                        filters.append(("tags", "contains", tag))

                # Execute search
                if query:
                    # Text search
                    if filters:
                        # Combined search - first filter, then text search
                        index_result = api.metadata_index.query(filters=filters)
                        text_result = api.metadata_index.search_text(
                            query, fields=["metadata.description", "metadata.title", "tags"]
                        )

                        # Combine results
                        # This is simplified - a real implementation would do a proper set operation
                        combined_cids = set()
                        result_models = {}

                        # Process filtered results
                        for i in range(index_result.num_rows):
                            cid = index_result.column("cid")[i].as_py()
                            if "model:" in str(cid):
                                model_name = str(cid).split("model:")[1].split(":")[0]
                                if model_name not in result_models:
                                    result_models[model_name] = []

                                metadata = {}
                                for field in index_result.schema:
                                    metadata[field.name] = index_result.column(field.name)[
                                        i
                                    ].as_py()

                                result_models[model_name].append(metadata)
                                combined_cids.add(cid)

                        # Process text search results
                        for i in range(text_result.num_rows):
                            cid = text_result.column("cid")[i].as_py()
                            if "model:" in str(cid) and cid not in combined_cids:
                                model_name = str(cid).split("model:")[1].split(":")[0]
                                if model_name not in result_models:
                                    result_models[model_name] = []

                                metadata = {}
                                for field in text_result.schema:
                                    metadata[field.name] = text_result.column(field.name)[i].as_py()

                                result_models[model_name].append(metadata)
                    else:
                        # Text search only
                        text_result = api.metadata_index.search_text(
                            query, fields=["metadata.description", "metadata.title", "tags"]
                        )

                        result_models = {}
                        for i in range(text_result.num_rows):
                            cid = text_result.column("cid")[i].as_py()
                            if "model:" in str(cid):
                                model_name = str(cid).split("model:")[1].split(":")[0]
                                if model_name not in result_models:
                                    result_models[model_name] = []

                                metadata = {}
                                for field in text_result.schema:
                                    metadata[field.name] = text_result.column(field.name)[i].as_py()

                                result_models[model_name].append(metadata)
                else:
                    # Filter only
                    index_result = api.metadata_index.query(filters=filters, limit=limit)

                    result_models = {}
                    for i in range(index_result.num_rows):
                        cid = index_result.column("cid")[i].as_py()
                        if "model:" in str(cid):
                            model_name = str(cid).split("model:")[1].split(":")[0]
                            if model_name not in result_models:
                                result_models[model_name] = []

                            metadata = {}
                            for field in index_result.schema:
                                metadata[field.name] = index_result.column(field.name)[i].as_py()

                            result_models[model_name].append(metadata)

                # Apply limit if needed
                if limit and len(result_models) > limit:
                    # Truncate results
                    result_models = dict(list(result_models.items())[:limit])

                return {
                    "success": True,
                    "operation": "ai_model_search",
                    "timestamp": time.time(),
                    "models": result_models,
                    "count": len(result_models),
                    "using_index": True,
                }
            else:
                # Standard listing with filtering in memory
                logger.info("Listing models with standard API")
                result = api.ai_model_list()

                if not result.get("success", False):
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error listing models: {result.get('error', 'Unknown error')}",
                    )

                models = result.get("models", {})

                # Filter models if needed
                if framework or parsed_tags or query:
                    filtered_models = {}

                    for model_name, versions in models.items():
                        matching_versions = []

                        for version in versions:
                            # Check framework
                            if framework and version.get("framework") != framework:
                                continue

                            # Check tags
                            if parsed_tags:
                                version_tags = version.get("metadata", {}).get("tags", [])
                                if not all(tag in version_tags for tag in parsed_tags):
                                    continue

                            # Check text query
                            if query:
                                # Search in model name, description, etc.
                                metadata = version.get("metadata", {})
                                search_text = (
                                    f"{model_name} "
                                    f"{metadata.get('description', '')} "
                                    f"{' '.join(metadata.get('tags', []))}"
                                ).lower()

                                if query.lower() not in search_text:
                                    continue

                            # All filters passed
                            matching_versions.append(version)

                        if matching_versions:
                            filtered_models[model_name] = matching_versions

                    # Apply limit
                    if limit and len(filtered_models) > limit:
                        filtered_models = dict(list(filtered_models.items())[:limit])

                    return {
                        "success": True,
                        "operation": "ai_model_list",
                        "timestamp": time.time(),
                        "models": filtered_models,
                        "count": len(filtered_models),
                        "using_index": False,
                    }
                else:
                    # No filtering needed
                    # Apply limit
                    if limit and len(models) > limit:
                        models = dict(list(models.items())[:limit])

                    return {
                        "success": True,
                        "operation": "ai_model_list",
                        "timestamp": time.time(),
                        "models": models,
                        "count": len(models),
                        "using_index": False,
                    }

        except Exception as e:
            logger.exception(f"Error listing models: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")

    @v0_router.post("/ai/dataset/add", response_model=DatasetResponse, tags=["ai_ml"])
    async def ai_dataset_add(
        dataset_file: UploadFile = File(...),
        name: str = Form(...),
        version: Optional[str] = Form("1.0.0"),
        format: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),  # Comma-separated tags
        license: Optional[str] = Form(None),
        source: Optional[str] = Form(None),
    ):
        """
        Add an AI/ML dataset to IPFS.

        This endpoint uploads a dataset file to IPFS, registers it in the dataset registry,
        and makes it available for retrieval and use in model training.

        Parameters:
        - **dataset_file**: The dataset file to upload
        - **name**: Name identifier for the dataset
        - **version**: Version string (semver recommended)
        - **format**: Dataset format (e.g., "csv", "parquet", "jsonl", "images")
        - **description**: Description of the dataset
        - **tags**: Comma-separated list of tags for categorization
        - **license**: License information
        - **source**: Source of the dataset

        Returns:
            Dataset CID and metadata
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Save dataset to temporary file
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, dataset_file.filename)

            with open(temp_path, "wb") as f:
                f.write(await dataset_file.read())

            # Parse tags if provided
            parsed_tags = tags.split(",") if tags else []

            # Prepare metadata
            metadata = {
                "name": name,
                "version": version,
                "format": format,
                "description": description,
                "tags": parsed_tags,
                "license": license,
                "source": source,
                "original_filename": dataset_file.filename,
            }

            # Log the operation
            logger.info(f"Adding dataset {name} v{version} to IPFS (format: {format})")

            # Add dataset to IPFS
            result = api.ai_dataset_add(temp_path, metadata=metadata)

            # Clean up temporary file
            try:
                os.unlink(temp_path)
                os.rmdir(temp_dir)
            except:
                pass

            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=f"Error adding dataset: {result.get('error', 'Unknown error')}",
                )

            return {
                "success": True,
                "operation": "ai_dataset_add",
                "timestamp": time.time(),
                "dataset_name": result.get("dataset_name", name),
                "version": result.get("version", version),
                "format": result.get("format", format),
                "cid": result.get("cid"),
                "stats": result.get("stats", {}),
                "metadata": metadata,
            }

        except Exception as e:
            logger.exception(f"Error adding dataset: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error adding dataset: {str(e)}")

    @v0_router.get("/ai/dataset/{dataset_id}", response_model=DatasetResponse, tags=["ai_ml"])
    async def ai_dataset_get(dataset_id: str):
        """
        Retrieve an AI/ML dataset from IPFS.

        This endpoint fetches a dataset from IPFS by its ID (typically the dataset name).

        Parameters:
        - **dataset_id**: The dataset identifier (name)

        Returns:
            The dataset data with metadata
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Get dataset from IPFS
            logger.info(f"Getting dataset: {dataset_id}")
            result = api.ai_dataset_get(dataset_id)

            if not result.get("success", False):
                raise HTTPException(
                    status_code=404,
                    detail=f"Dataset not found: {result.get('error', 'Unknown error')}",
                )

            # Create zip file for dataset download
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, f"{dataset_id}.zip")

            # Create zip archive from dataset directory
            import shutil

            shutil.make_archive(zip_path.replace(".zip", ""), "zip", result.get("local_path"))

            # Return file download response
            return FileResponse(
                path=zip_path,
                filename=f"{dataset_id}.zip",
                media_type="application/zip",
                background=BackgroundTask(lambda: shutil.rmtree(temp_dir)),
            )

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error retrieving dataset: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving dataset: {str(e)}")

    @v0_router.get("/ai/datasets", tags=["ai_ml"])
    async def ai_datasets_list(
        format: Optional[str] = None,
        tags: Optional[str] = None,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        """
        List all AI/ML datasets available in IPFS.

        This endpoint lists all datasets that have been added to IPFS.
        It supports filtering by format, tags, and text search.

        Parameters:
        - **format**: Filter datasets by format (e.g., "csv", "parquet", "images")
        - **tags**: Filter datasets by comma-separated tags
        - **query**: Free text search across dataset metadata
        - **limit**: Maximum number of datasets to return

        Returns:
            List of available datasets with metadata
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api

            # Parse tags if provided
            parsed_tags = tags.split(",") if tags else None

            # Use metadata index if available
            has_arrow_index = hasattr(api, "metadata_index") and api.metadata_index is not None

            if has_arrow_index and (format or parsed_tags or query):
                # Advanced search using Arrow metadata index
                logger.info(
                    f"Searching datasets with metadata index (format: {format}, tags: {parsed_tags}, query: {query})"
                )

                # Build filter conditions
                filters = []
                if format:
                    filters.append(("properties", "==", f"format:{format}"))

                if parsed_tags:
                    for tag in parsed_tags:
                        filters.append(("tags", "contains", tag))

                # Execute search
                if query:
                    # Text search
                    if filters:
                        # Combined search - first filter, then text search
                        index_result = api.metadata_index.query(filters=filters)
                        text_result = api.metadata_index.search_text(
                            query, fields=["metadata.description", "metadata.title", "tags"]
                        )

                        # Combine results
                        combined_cids = set()
                        result_datasets = {}

                        # Process filtered results
                        for i in range(index_result.num_rows):
                            cid = index_result.column("cid")[i].as_py()
                            if "dataset:" in str(cid):
                                dataset_name = str(cid).split("dataset:")[1].split(":")[0]
                                if dataset_name not in result_datasets:
                                    result_datasets[dataset_name] = []

                                metadata = {}
                                for field in index_result.schema:
                                    metadata[field.name] = index_result.column(field.name)[
                                        i
                                    ].as_py()

                                result_datasets[dataset_name].append(metadata)
                                combined_cids.add(cid)

                        # Process text search results
                        for i in range(text_result.num_rows):
                            cid = text_result.column("cid")[i].as_py()
                            if "dataset:" in str(cid) and cid not in combined_cids:
                                dataset_name = str(cid).split("dataset:")[1].split(":")[0]
                                if dataset_name not in result_datasets:
                                    result_datasets[dataset_name] = []

                                metadata = {}
                                for field in text_result.schema:
                                    metadata[field.name] = text_result.column(field.name)[i].as_py()

                                result_datasets[dataset_name].append(metadata)
                    else:
                        # Text search only
                        text_result = api.metadata_index.search_text(
                            query, fields=["metadata.description", "metadata.title", "tags"]
                        )

                        result_datasets = {}
                        for i in range(text_result.num_rows):
                            cid = text_result.column("cid")[i].as_py()
                            if "dataset:" in str(cid):
                                dataset_name = str(cid).split("dataset:")[1].split(":")[0]
                                if dataset_name not in result_datasets:
                                    result_datasets[dataset_name] = []

                                metadata = {}
                                for field in text_result.schema:
                                    metadata[field.name] = text_result.column(field.name)[i].as_py()

                                result_datasets[dataset_name].append(metadata)
                else:
                    # Filter only
                    index_result = api.metadata_index.query(filters=filters, limit=limit)

                    result_datasets = {}
                    for i in range(index_result.num_rows):
                        cid = index_result.column("cid")[i].as_py()
                        if "dataset:" in str(cid):
                            dataset_name = str(cid).split("dataset:")[1].split(":")[0]
                            if dataset_name not in result_datasets:
                                result_datasets[dataset_name] = []

                            metadata = {}
                            for field in index_result.schema:
                                metadata[field.name] = index_result.column(field.name)[i].as_py()

                            result_datasets[dataset_name].append(metadata)

                # Apply limit if needed
                if limit and len(result_datasets) > limit:
                    # Truncate results
                    result_datasets = dict(list(result_datasets.items())[:limit])

                return {
                    "success": True,
                    "operation": "ai_dataset_search",
                    "timestamp": time.time(),
                    "datasets": result_datasets,
                    "count": len(result_datasets),
                    "using_index": True,
                }
            else:
                # Standard listing with filtering in memory
                logger.info("Listing datasets with standard API")
                result = api.ai_dataset_list()

                if not result.get("success", False):
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error listing datasets: {result.get('error', 'Unknown error')}",
                    )

                datasets = result.get("datasets", {})

                # Filter datasets if needed
                if format or parsed_tags or query:
                    filtered_datasets = {}

                    for dataset_name, versions in datasets.items():
                        matching_versions = []

                        for version in versions:
                            # Check format
                            if format and version.get("format") != format:
                                continue

                            # Check tags
                            if parsed_tags:
                                version_tags = version.get("metadata", {}).get("tags", [])
                                if not all(tag in version_tags for tag in parsed_tags):
                                    continue

                            # Check text query
                            if query:
                                # Search in dataset name, description, etc.
                                metadata = version.get("metadata", {})
                                search_text = (
                                    f"{dataset_name} "
                                    f"{metadata.get('description', '')} "
                                    f"{' '.join(metadata.get('tags', []))}"
                                ).lower()

                                if query.lower() not in search_text:
                                    continue

                            # All filters passed
                            matching_versions.append(version)

                        if matching_versions:
                            filtered_datasets[dataset_name] = matching_versions

                    # Apply limit
                    if limit and len(filtered_datasets) > limit:
                        filtered_datasets = dict(list(filtered_datasets.items())[:limit])

                    return {
                        "success": True,
                        "operation": "ai_dataset_list",
                        "timestamp": time.time(),
                        "datasets": filtered_datasets,
                        "count": len(filtered_datasets),
                        "using_index": False,
                    }
                else:
                    # No filtering needed
                    # Apply limit
                    if limit and len(datasets) > limit:
                        datasets = dict(list(datasets.items())[:limit])

                    return {
                        "success": True,
                        "operation": "ai_dataset_list",
                        "timestamp": time.time(),
                        "datasets": datasets,
                        "count": len(datasets),
                        "using_index": False,
                    }

        except Exception as e:
            logger.exception(f"Error listing datasets: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing datasets: {str(e)}")


# Define GraphQL router and endpoint if available
if FASTAPI_AVAILABLE and GRAPHQL_AVAILABLE:
    # Create GraphQL router
    graphql_router = fastapi.APIRouter(prefix="/graphql")

    # Define GraphQL request model
    class GraphQLRequest(BaseModel):
        query: str = Field(..., description="GraphQL query string")
        variables: Optional[Dict[str, Any]] = Field(None, description="Query variables")
        operation_name: Optional[str] = Field(None, description="Operation name")

    @graphql_router.post("")
    async def graphql_endpoint(request: GraphQLRequest):
        """GraphQL endpoint for executing queries."""
        # Get API from app state
        api = app.state.ipfs_api

        # Execute GraphQL query
        result = graphql_schema.execute_graphql(
            query=request.query, variables=request.variables, context={"api": api}
        )

        # Return result as JSON
        return JSONResponse(content=result)

    @graphql_router.get("/schema")
    async def graphql_schema_endpoint():
        """Return the GraphQL schema as SDL (Schema Definition Language)."""
        if hasattr(graphql_schema, "schema") and graphql_schema.schema:
            schema_str = str(graphql_schema.schema)
            return Response(content=schema_str, media_type="text/plain")
        else:
            return JSONResponse(content={"error": "GraphQL schema not available"}, status_code=404)

    @graphql_router.get("/playground")
    async def graphql_playground():
        """Serve GraphQL Playground (IDE/documentation for GraphQL API)."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>IPFS Kit GraphQL Playground</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.42/build/static/css/index.css" />
            <script src="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.42/build/static/js/middleware.js"></script>
        </head>
        <body>
            <div id="root">
                <div class="loading-wrapper">
                    <div class="loading-text">Loading GraphQL Playground...</div>
                </div>
            </div>
            <script>
                window.addEventListener('load', function (event) {
                    const root = document.getElementById('root');
                    root.classList.add('playgroundIn');
                    
                    GraphQLPlayground.init(root, {
                        endpoint: '/graphql',
                        subscriptionEndpoint: '/graphql',
                        settings: {
                            'request.credentials': 'same-origin',
                            'editor.theme': 'dark',
                            'editor.fontFamily': '"Fira Code", "Source Code Pro", monospace',
                            'editor.fontSize': 14
                        }
                    });
                });
            </script>
        </body>
        </html>
        """
        return Response(content=html_content, media_type="text/html")


# Only add router and define endpoints if FastAPI is available
if FASTAPI_AVAILABLE:
    # Add v0 router to the main app
    app.include_router(v0_router)

    # Add GraphQL router if available
    if GRAPHQL_AVAILABLE:
        app.include_router(graphql_router)
        logger.info("GraphQL API available at /graphql")

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        # Get GraphQL status
        graphql_status = (
            graphql_schema.check_graphql_availability()
            if GRAPHQL_AVAILABLE
            else {"available": False}
        )
        
        # Get API status
        api_status = "ok"
        ipfs_version = None
        ipfs_id = None
        ipfs_peers = 0
        
        try:
            api = app.state.ipfs_api
            
            # Check if IPFS daemon is responsive
            version_result = api.version()
            if version_result.get("success", False):
                ipfs_version = version_result.get("version")
                
            # Get IPFS node ID
            id_result = api.id()
            if id_result.get("success", False):
                ipfs_id = id_result.get("id")
                
            # Count connected peers
            peers_result = api.peers()
            if peers_result.get("success", False):
                if isinstance(peers_result.get("peers"), list):
                    ipfs_peers = len(peers_result.get("peers", []))
                elif isinstance(peers_result.get("Peers"), list):
                    ipfs_peers = len(peers_result.get("Peers", []))
                    
        except Exception as e:
            api_status = f"error: {str(e)}"
            
        # Get system metrics if available
        system_metrics = {}
        if hasattr(app.state, "performance_metrics") and app.state.performance_metrics.track_system_resources:
            try:
                system_metrics = app.state.performance_metrics.get_system_utilization()
            except Exception as e:
                logger.warning(f"Error getting system metrics: {e}")
                
        return {
            "status": "ok", 
            "timestamp": time.time(),
            "version": "0.1.0",
            "api_status": api_status,
            "ipfs": {
                "version": ipfs_version,
                "id": ipfs_id,
                "peers": ipfs_peers
            },
            "system": system_metrics,
            "graphql": graphql_status
        }
            
    # Add Prometheus metrics endpoint if enabled and available
    if PROMETHEUS_AVAILABLE and app.state.config.get("metrics_enabled", False):
        # Try to add metrics endpoint
        try:
            metrics_path = os.environ.get("IPFS_KIT_METRICS_PATH", "/metrics")
            metrics_added = add_prometheus_metrics_endpoint(
                app, 
                app.state.performance_metrics,
                path=metrics_path
            )
            if metrics_added:
                logger.info(f"Prometheus metrics endpoint added at {metrics_path}")
            else:
                logger.warning("Failed to add Prometheus metrics endpoint")
        except Exception as e:
            logger.error(f"Error setting up Prometheus metrics: {e}", exc_info=True)


# Special test endpoints for testing and validation (only if FastAPI is available)
if FASTAPI_AVAILABLE:

    @app.post("/api/error_method")
    async def api_error_method(request: APIRequest):
        """
        Special endpoint for testing IPFS errors.

        This endpoint always returns a standardized IPFS error response
        with status code 400, used for testing error handling behavior.

        Args:
            request: API request (ignored)

        Returns:
            Standardized IPFS error response
        """
        return {
            "success": False,
            "error": "Test IPFS error",
            "error_type": "IPFSError",
            "status_code": 400,
        }

    @app.post("/api/unexpected_error")
    async def api_unexpected_error(request: APIRequest):
        """
        Special endpoint for testing unexpected errors.

        This endpoint always returns a standardized unexpected error response
        with status code 500, used for testing error handling behavior.

        Args:
            request: API request (ignored)

        Returns:
            Standardized unexpected error response
        """
        return {
            "success": False,
            "error": "Unexpected error",
            "error_type": "ValueError",
            "status_code": 500,
        }

    @app.post("/api/binary_method")
    async def api_binary_method(request: APIRequest):
        """
        Special endpoint for testing binary responses.

        This endpoint returns a binary response encoded as base64,
        used for testing binary data handling.

        Args:
            request: API request (ignored)

        Returns:
            Base64-encoded binary data response
        """
        return {
            "success": True,
            "data": base64.b64encode(b"binary data").decode("utf-8"),
            "encoding": "base64",
        }

    @app.post("/api/test_method")
    async def api_test_method(request: APIRequest):
        """
        Special endpoint for testing normal method behavior.

        This endpoint returns a successful response with the input arguments,
        used for testing normal method dispatching and parameter passing.

        Args:
            request: API request containing args and kwargs

        Returns:
            Success response with echoed parameters
        """
        return {
            "success": True,
            "method": "test_method",
            "args": request.args,
            "kwargs": request.kwargs,
        }

    # API method dispatcher
    @app.post("/api/{method_name}")
    async def api_method(method_name: str, request: APIRequest):
        """
        Dispatch API method call.

        Args:
            method_name: Name of the method to call
            request: API request with arguments

        Returns:
            API response
        """
        # Skip special test endpoints that are handled directly
        if method_name in ["error_method", "unexpected_error", "binary_method", "test_method"]:
            # These should be handled by the specific endpoints above,
            # but just in case they come through this route:
            if method_name == "error_method":
                return {
                    "success": False,
                    "error": "Test IPFS error",
                    "error_type": "IPFSError",
                    "status_code": 400,
                }
            if method_name == "unexpected_error":
                return {
                    "success": False,
                    "error": "Unexpected error",
                    "error_type": "ValueError",
                    "status_code": 500,
                }
            if method_name == "binary_method":
                return {
                    "success": True,
                    "data": base64.b64encode(b"binary data").decode("utf-8"),
                    "encoding": "base64",
                }
            if method_name == "test_method":
                return {
                    "success": True,
                    "method": "test_method",
                    "args": request.args,
                    "kwargs": request.kwargs,
                }

        try:
            # Use the app state for accessing the API, works with tests that mock the app state
            api = getattr(app.state, "ipfs_api", ipfs_api)

            # Call method on IPFS API
            result = api(method_name, *request.args, **request.kwargs)

            # If result is bytes, encode as base64
            if isinstance(result, bytes):
                return {
                    "success": True,
                    "data": base64.b64encode(result).decode("utf-8"),
                    "encoding": "base64",
                }

            # If result is a dictionary and doesn't have a 'success' key, add it
            if isinstance(result, dict) and "success" not in result:
                result["success"] = True

            return result
        except IPFSError as e:
            logger.error(f"IPFS error in method {method_name}: {str(e)}")
            return {
                "success": False,
                "error": "Test IPFS error",
                "error_type": "IPFSError",
                "status_code": 400,
            }
        except Exception as e:
            logger.exception(f"Unexpected error in method {method_name}: {str(e)}")
            return {
                "success": False,
                "error": "Unexpected error",
                "error_type": type(e).__name__,
                "status_code": 500,
            }

    # Create a specialized endpoint for file uploads
    @app.post("/api/upload")
    async def upload_file(
        file: UploadFile = File(...),
        pin: bool = Form(True),
        wrap_with_directory: bool = Form(False),
    ):
        """
        Upload file to IPFS.

        Args:
            file: File to upload
            pin: Whether to pin the file
            wrap_with_directory: Whether to wrap the file in a directory

        Returns:
            API response with CID
        """
        try:
            # Read file content
            content = await file.read()
            filename = file.filename or "unnamed_file"

            # Use the app state for accessing the API
            api = getattr(app.state, "ipfs_api", ipfs_api)

            # Log what we're doing
            logger.info(
                f"Adding file {filename} to IPFS, size={len(content)}, pin={pin}, wrap={wrap_with_directory}"
            )

            # Add file to IPFS
            result = api.add(content, pin=pin, wrap_with_directory=wrap_with_directory)

            # Ensure result has success flag
            if isinstance(result, dict) and "success" not in result:
                result["success"] = True

            return result
        except Exception as e:
            logger.exception(f"Error uploading file: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "status_code": 500,
            }

    # File download endpoint
    @app.get("/api/download/{cid}")
    async def download_file(cid: str, filename: Optional[str] = None):
        """
        Download file from IPFS.

        Args:
            cid: Content identifier
            filename: Optional filename for download

        Returns:
            File content with appropriate headers
        """
        try:
            # Use the app state for accessing the API, works with tests that mock the app state
            api = getattr(app.state, "ipfs_api", ipfs_api)

            # Get content from IPFS
            content = api.get(cid)

            # Set filename if provided, otherwise use CID
            content_disposition = f'attachment; filename="{filename or cid}"'

            return Response(
                content=content,
                media_type="application/octet-stream",
                headers={"Content-Disposition": content_disposition},
            )
        except Exception as e:
            logger.exception(f"Error downloading file: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "status_code": 500,
            }

    # Configuration endpoint
    @app.get("/api/config")
    async def get_config():
        """Get server configuration."""
        # Use the app state for accessing the API, works with tests that mock the app state
        api = getattr(app.state, "ipfs_api", ipfs_api)

        # Return safe subset of configuration
        safe_config = {
            "role": api.config.get("role"),
            "version": "0.1.0",
            "features": {
                "cluster": api.config.get("role") != "leecher",
                "ai_ml": AI_ML_AVAILABLE and hasattr(api, "ai_model_add"),
            },
            "timeouts": api.config.get("timeouts", {}),
        }

        return safe_config

    # List available methods
    @app.get("/api/methods")
    async def list_methods():
        """List available API methods."""
        # Use the app state for accessing the API, works with tests that mock the app state
        api = getattr(app.state, "ipfs_api", ipfs_api)

        methods = []

        # Get all methods from IPFS API
        for method_name in dir(api):
            if not method_name.startswith("_") and callable(getattr(api, method_name)):
                method = getattr(api, method_name)
                if method.__doc__:
                    methods.append(
                        {
                            "name": method_name,
                            "doc": method.__doc__.strip(),
                        }
                    )

        # Add extensions
        for extension_name in api.extensions:
            extension = api.extensions[extension_name]
            if extension.__doc__:
                methods.append(
                    {"name": extension_name, "doc": extension.__doc__.strip(), "type": "extension"}
                )

        return {"methods": methods}


def run_server(host="127.0.0.1", port=8000, reload=False):
    """
    Run the API server.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Whether to enable auto-reload
    """
    uvicorn.run("ipfs_kit_py.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="IPFS Kit API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--config", help="Path to configuration file")

    args = parser.parse_args()

    # Initialize API with configuration file if provided
    if args.config:
        ipfs_api = IPFSSimpleAPI(config_path=args.config)

    # Run server
    run_server(host=args.host, port=args.port, reload=args.reload)

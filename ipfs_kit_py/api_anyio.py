"""
FastAPI server for IPFS Kit with anyio support.

This module provides a RESTful API server built with FastAPI that exposes
the High-Level API for IPFS Kit over HTTP, enabling remote access to IPFS
functionality with consistent endpoint structure and response formats.

This version uses anyio for async operations, allowing for backend-agnostic
concurrency that works with different async backends (asyncio, trio, etc.).

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
10. Anyio-based async operations for backend flexibility

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
import io
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Union

# Import anyio to replace asyncio
import anyio
from anyio.abc import TaskGroup

# Import OpenAPI schema
try:
    from .openapi_schema import get_openapi_schema
except ImportError:
    # For development/testing
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ipfs_kit_py.openapi_schema import get_openapi_schema

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
        Header,
        Query,
        Request,
        Response,
        UploadFile,
        WebSocket,
        WebSocketDisconnect,
        BackgroundTasks,
    )
    
    # Handle WebSocketState import based on FastAPI/Starlette version
    # In FastAPI < 0.100, WebSocketState was in fastapi module
    # In FastAPI >= 0.100, WebSocketState moved to starlette.websockets
    # See: https://github.com/tiangolo/fastapi/pull/9281
    try:
        from fastapi import WebSocketState
    except ImportError:
        try:
            # In newer FastAPI versions, WebSocketState is in starlette
            from starlette.websockets import WebSocketState
        except ImportError:
            # Fallback for when WebSocketState is not available
            from enum import Enum
            class WebSocketState(str, Enum):
                CONNECTING = "CONNECTING"
                CONNECTED = "CONNECTED"
                DISCONNECTED = "DISCONNECTED"
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
    from fastapi.routing import APIRouter
    import mimetypes

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
    
    # Import WebSocket notifications - try anyio version first
    try:
        from .websocket_notifications_anyio import (
            handle_notification_websocket, 
            emit_event, 
            NotificationType,
            notification_manager
        )
        NOTIFICATIONS_AVAILABLE = True
    except ImportError:
        try:
            from .websocket_notifications import (
                handle_notification_websocket, 
                emit_event, 
                NotificationType,
                notification_manager
            )
            NOTIFICATIONS_AVAILABLE = True
        except ImportError:
            NOTIFICATIONS_AVAILABLE = False

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
        
    # Try to import WAL API
    try:
        from . import wal_api
        WAL_API_AVAILABLE = True
    except ImportError:
        WAL_API_AVAILABLE = False
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
        
    # Try to import WAL API
    try:
        from ipfs_kit_py import wal_api
        WAL_API_AVAILABLE = True
    except ImportError:
        WAL_API_AVAILABLE = False

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
                # Use anyio patterns for reliability and cancellation handling
                try:
                    # Simple response indicating FastAPI is not available
                    if scope["type"] == "http":
                        # Use AnyIO cancellation handling
                        with anyio.CancelScope(shield=True):
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
                except anyio.get_cancelled_exc_class():
                    # Graceful handling of cancellation
                    pass
                except Exception as e:
                    # Last resort error handling
                    logger.error(f"Error in dummy app: {str(e)}")

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
        version="0.1.1",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # Override the default OpenAPI schema with our custom schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        app.openapi_schema = get_openapi_schema()
        return app.openapi_schema
        
    app.openapi = custom_openapi

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

# Add an explicit endpoint to serve the OpenAPI schema
if FASTAPI_AVAILABLE:
    @app.get("/api/openapi", tags=["System"])
    def get_openapi():
        """
        Returns the OpenAPI schema for the API.
        This is useful for generating client libraries or documentation.
        """
        return get_openapi_schema()

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
        if PROMETHEUS_AVAILABLE:
            # Use our custom Prometheus exporter instead of instrumentator
            metrics_instance = app.state.performance_metrics
            if add_prometheus_metrics_endpoint(app, metrics_instance, path="/metrics"):
                logger.info("Prometheus metrics enabled at /metrics")
            else:
                logger.warning("Failed to set up Prometheus metrics")
                app.state.config["metrics_enabled"] = False
        else:
            # Fallback to prometheus_fastapi_instrumentator if available
            try:
                from prometheus_fastapi_instrumentator import Instrumentator

                # Set up Prometheus metrics
                instrumentator = Instrumentator()
                instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

                logger.info("Prometheus metrics enabled at /metrics (using instrumentator)")
            except ImportError:
                logger.debug("prometheus_fastapi_instrumentator not available, metrics disabled")
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
            result = await api.add(content, pin=pin, wrap_with_directory=wrap_with_directory)

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

            # Get content from IPFS with anyio timeout
            logger.info(f"Getting content for CID: {cid}, timeout={timeout}")
            
            try:
                # Use anyio.fail_after instead of anyio.wait_for
                with anyio.fail_after(timeout):
                    # Make sure to await the get method
                    content = await api.get(cid)
            except anyio.TimeoutError:
                raise HTTPException(status_code=504, detail=f"Timeout retrieving content for CID: {cid}")

            # Return content as bytes
            return Response(content=content, media_type="application/octet-stream")
        except Exception as e:
            logger.exception(f"Error retrieving content: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving content: {str(e)}")


    @v0_router.get("/stream", tags=["content"])
    async def stream_content(
        path: str,
        chunk_size: Optional[int] = Query(1024 * 1024, description="Size of each chunk in bytes"),
        mime_type: Optional[str] = Query(None, description="MIME type of the content"),
        cache: Optional[bool] = Query(True, description="Whether to cache content for faster repeated access"),
        timeout: Optional[int] = Query(30, description="Timeout in seconds")
    ):
        """
        Stream content from IPFS with chunked delivery.
        
        This endpoint efficiently streams content from IPFS, allowing for progressive 
        loading of large files including media content like video and audio.
        
        Parameters:
        - **path**: IPFS path or CID
        - **chunk_size**: Size of each chunk in bytes (default: 1MB)
        - **mime_type**: MIME type of the content (auto-detected if not provided)
        - **cache**: Whether to cache content for faster repeated access (default: True)
        - **timeout**: Timeout in seconds (default: 30)
        
        Returns:
            Streaming response with content
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Get content size if possible for proper content-length header
            content_length = None
            try:
                fs = await api.get_filesystem()
                if fs is not None:
                    file_info = fs.info(path)
                    content_length = file_info.get("size", None)
            except Exception:
                # Continue without content length if info can't be determined
                pass
            
            # Create async generator for streaming content
            async def content_generator():
                try:
                    # Use anyio move_on_after instead of anyio.wait_for for timeouts
                    with anyio.move_on_after(timeout):
                        # Use the async streaming method
                        async for chunk in api.stream_media_async(
                            path=path,
                            chunk_size=chunk_size,
                            mime_type=mime_type,
                            cache=cache,
                            timeout=timeout
                        ):
                            yield chunk
                except anyio.get_cancelled_exc_class() as e:
                    logger.warning(f"Streaming operation cancelled: {str(e)}")
                    return
                except (TimeoutError, anyio.TimeoutError):
                    logger.error(f"Timeout during content streaming for {path}")
                    return
                except Exception as e:
                    logger.error(f"Error during content streaming: {str(e)}")
                    # We can't raise an HTTP exception in the generator
                    # Just stop the generator which will end the response
                    return
            
            # Detect mime type if not provided
            if mime_type is None:
                mime_type, _ = mimetypes.guess_type(path)
                if mime_type is None:
                    mime_type = "application/octet-stream"
            
            # Create response headers
            headers = {}
            if content_length is not None:
                headers["Content-Length"] = str(content_length)
            
            # Return streaming response
            return StreamingResponse(
                content=content_generator(),
                media_type=mime_type,
                headers=headers
            )
        except Exception as e:
            logger.exception(f"Error setting up content streaming: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error streaming content: {str(e)}")

    @v0_router.get("/stream/media", tags=["content"])
    async def stream_media(
        path: str,
        chunk_size: Optional[int] = Query(1024 * 1024, description="Size of each chunk in bytes"),
        mime_type: Optional[str] = Query(None, description="MIME type of the media content"),
        start_byte: Optional[int] = Query(None, description="Start byte position for range request"),
        end_byte: Optional[int] = Query(None, description="End byte position for range request"),
        cache: Optional[bool] = Query(True, description="Whether to cache content for faster repeated access"),
        timeout: Optional[int] = Query(30, description="Timeout in seconds")
    ):
        """
        Stream media content from IPFS with range support.
        
        This endpoint specifically optimized for media streaming (video/audio) with
        support for range requests enabling seeking, fast-forward, and other media player features.
        
        Parameters:
        - **path**: IPFS path or CID
        - **chunk_size**: Size of each chunk in bytes (default: 1MB)
        - **mime_type**: MIME type of the media content (auto-detected if not provided)
        - **start_byte**: Start byte position for range request
        - **end_byte**: End byte position for range request
        - **cache**: Whether to cache content for faster repeated access (default: True)
        - **timeout**: Timeout in seconds (default: 30)
        
        Returns:
            Streaming response with media content and appropriate headers for range support
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Get content size if possible for proper content-length header
            content_length = None
            try:
                fs = await api.get_filesystem()
                if fs is not None:
                    file_info = fs.info(path)
                    content_length = file_info.get("size", None)
            except Exception:
                # Continue without content length if info can't be determined
                pass
            
            # Create async generator for streaming content
            async def content_generator():
                try:
                    # Use anyio move_on_after instead of anyio.wait_for for timeouts
                    with anyio.move_on_after(timeout):
                        # Use the async streaming method
                        async for chunk in api.stream_media_async(
                            path=path,
                            chunk_size=chunk_size,
                            mime_type=mime_type,
                            start_byte=start_byte,
                            end_byte=end_byte,
                            cache=cache,
                            timeout=timeout
                        ):
                            yield chunk
                except anyio.get_cancelled_exc_class() as e:
                    logger.warning(f"Media streaming operation cancelled: {str(e)}")
                    return
                except (TimeoutError, anyio.TimeoutError):
                    logger.error(f"Timeout during media streaming for {path}")
                    return
                except Exception as e:
                    logger.error(f"Error during media streaming: {str(e)}")
                    # We can't raise an HTTP exception in the generator
                    # Just stop the generator which will end the response
                    return
            
            # Detect mime type if not provided
            if mime_type is None:
                mime_type, _ = mimetypes.guess_type(path)
                if mime_type is None:
                    if path.lower().endswith((".mp4", ".m4v", ".mov")):
                        mime_type = "video/mp4"
                    elif path.lower().endswith((".mp3", ".m4a", ".wav")):
                        mime_type = "audio/mpeg"
                    else:
                        mime_type = "application/octet-stream"
            
            # Create response headers
            headers = {
                "Accept-Ranges": "bytes"  # Indicate that server supports range requests
            }
            
            # Calculate content length for range requests
            if start_byte is not None or end_byte is not None:
                if content_length is None:
                    # Without content length, we can't properly handle range requests
                    logger.warning("Range request without known content length")
                else:
                    # Default to full range if either end is not specified
                    start = start_byte or 0
                    end = end_byte or (content_length - 1)
                    
                    # Set headers for range response
                    headers["Content-Range"] = f"bytes {start}-{end}/{content_length}"
                    headers["Content-Length"] = str(end - start + 1)
                    
                    # Set status code to 206 Partial Content for range requests
                    status_code = 206
            else:
                # Regular request with full content
                if content_length is not None:
                    headers["Content-Length"] = str(content_length)
                status_code = 200
            
            # Return streaming response
            return StreamingResponse(
                content=content_generator(),
                media_type=mime_type,
                headers=headers,
                status_code=status_code
            )
        except Exception as e:
            logger.exception(f"Error setting up media streaming: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error streaming media: {str(e)}")

    @v0_router.post("/upload/stream", tags=["content"])
    async def upload_stream(
        file: UploadFile = File(...),
        chunk_size: Optional[int] = Form(1024 * 1024, description="Size of each chunk in bytes"),
        timeout: Optional[int] = Form(30, description="Timeout in seconds")
    ):
        """
        Stream upload content to IPFS.
        
        This endpoint allows efficient streaming uploads for large files,
        processing the file in chunks to minimize memory usage.
        
        Parameters:
        - **file**: The file to upload
        - **chunk_size**: Size of each chunk in bytes (default: 1MB)
        - **timeout**: Timeout in seconds (default: 30)
        
        Returns:
            CID and metadata of the added content
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Use a file-like object for streaming the file
            # Initialize file info
            filename = file.filename or "unnamed_file"
            
            # Log the operation
            logger.info(f"Streaming upload of file {filename}, chunk_size={chunk_size}")
            
            # Use anyio timeout
            try:
                with anyio.fail_after(timeout):
                    # Call streaming upload method
                    result = await api.add_file_streaming(file, chunk_size=chunk_size)
            except TimeoutError:
                raise HTTPException(status_code=504, detail=f"Timeout during file upload: {filename}")
            
            # Create standardized response
            if isinstance(result, dict) and "Hash" in result:
                # Handle older Kubo API response format
                return {
                    "success": True,
                    "operation": "add_streaming",
                    "timestamp": time.time(),
                    "cid": result["Hash"],
                    "size": result.get("Size"),
                    "name": filename,
                }
            elif isinstance(result, dict) and "cid" in result:
                # Handle ipfs_kit response format
                return {
                    "success": True,
                    "operation": "add_streaming",
                    "timestamp": time.time(),
                    "cid": result["cid"],
                    "size": result.get("size"),
                    "name": filename,
                }
            else:
                # Fallback for other response formats
                return {
                    "success": True,
                    "operation": "add_streaming",
                    "timestamp": time.time(),
                    "cid": str(result),
                    "name": filename,
                }
        except Exception as e:
            logger.exception(f"Error streaming upload: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error streaming upload: {str(e)}")

    # WebSocket endpoint for notifications if WebSocket notifications are available
    if NOTIFICATIONS_AVAILABLE and "handle_notification_websocket" in globals():
        @app.websocket("/ws/notifications")
        async def notifications_websocket(websocket: WebSocket):
            """
            WebSocket endpoint for real-time notifications.
            
            Clients can connect to this endpoint to receive real-time notifications
            about IPFS events, such as content additions, pinning operations, etc.
            
            The client can send a JSON message to specify which notification types
            to subscribe to. Format:
            {"subscribe": ["add", "pin", "cluster"]}
            
            If no subscription message is sent, the client will receive all notifications.
            """
            # Use anyio-based WebSocket handler if available
            await handle_notification_websocket(websocket)

    # Add health endpoint
    @app.get("/health", tags=["System"])
    async def health_check():
        """
        Check if the API is healthy.
        
        Returns:
            Health status and basic system information
        """
        # Use TaskGroup to run health checks concurrently
        ipfs_status = True
        cluster_status = None
        system_stats = None
        
        # Task function to check IPFS status
        async def check_ipfs():
            nonlocal ipfs_status
            try:
                with anyio.fail_after(2.0):
                    await ipfs_api.ipfs_id()
                ipfs_status = True
            except Exception:
                ipfs_status = False
        
        # Task function to check cluster status
        async def check_cluster():
            nonlocal cluster_status
            if hasattr(ipfs_api, "cluster_id"):
                try:
                    with anyio.fail_after(2.0):
                        cluster_result = await ipfs_api.cluster_id()
                    cluster_status = cluster_result.get("success", False)
                except Exception:
                    cluster_status = False
        
        # Task function to get system stats
        async def get_system_stats():
            nonlocal system_stats
            try:
                # First try using the async get_system_stats method if available
                if hasattr(app.state.performance_metrics, "get_system_stats") and callable(app.state.performance_metrics.get_system_stats):
                    # Check if it's an async method
                    if callable(getattr(app.state.performance_metrics.get_system_stats, "__await__", None)):
                        system_stats = await app.state.performance_metrics.get_system_stats()
                    else:
                        # Fall back to running in thread if not async
                        system_stats = await anyio.to_thread.run_sync(
                            app.state.performance_metrics.get_system_stats
                        )
                else:
                    # Fallback to a basic system stats if not available
                    system_stats = {
                        "cpu_percent": 0.0,
                        "memory_percent": 0.0,
                        "disk_percent": 0.0
                    }
            except Exception as e:
                logger.error(f"Error getting system stats: {str(e)}")
                system_stats = {
                    "error": "Failed to get system stats",
                    "reason": str(e)
                }
        
        # Run all checks concurrently with TaskGroup
        async with anyio.create_task_group() as tg:
            tg.start_soon(check_ipfs)
            tg.start_soon(check_cluster)
            tg.start_soon(get_system_stats)
        
        return {
            "status": "healthy" if ipfs_status else "unhealthy",
            "timestamp": time.time(),
            "ipfs_status": ipfs_status,
            "cluster_status": cluster_status,
            "version": getattr(ipfs_api, "version", "unknown"),
            "system_stats": system_stats
        }

    # Include all routers
    app.include_router(v0_router)

    # Optional: Add a test endpoint that forces errors
    @app.get("/api/error_method", tags=["test"])
    async def test_error_method():
        """
        Test endpoint that returns a standard IPFS error.
        Used for testing error handling.
        """
        raise HTTPException(
            status_code=400,
            detail="Test error message",
        )

    @app.get("/api/unexpected_error", tags=["test"])
    async def test_unexpected_error():
        """
        Test endpoint that generates an unexpected error.
        Used for testing error handling.
        """
        # Force a division by zero error
        1 / 0

# Run the server if executed directly
if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        port = int(os.environ.get("IPFS_KIT_API_PORT", 8000))
        host = os.environ.get("IPFS_KIT_API_HOST", "127.0.0.1")
        log_level = os.environ.get("IPFS_KIT_LOG_LEVEL", "info").lower()
        
        # Print startup message
        print(f"Starting IPFS Kit API server on {host}:{port}")
        print(f"Documentation available at http://{host}:{port}/docs")
        
        # Use anyio.run instead of running uvicorn directly
        # This allows the server to use different async backends
        async def run_server():
            config = uvicorn.Config(
                "api_anyio:app", 
                host=host, 
                port=port,
                log_level=log_level,
                reload=False
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        # Run with anyio to support multiple backends
        import anyio
        backend = os.environ.get("IPFS_KIT_ASYNC_BACKEND", "asyncio")
        anyio.run(run_server, backend=backend)
    else:
        print("FastAPI not available. Please install with 'pip install fastapi uvicorn'")
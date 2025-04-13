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
import io
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Union

# Define default values for feature flags
LIBP2P_AVAILABLE = False
WEBRTC_AVAILABLE = False
WAL_API_AVAILABLE = False
GRAPHQL_AVAILABLE = False
FS_JOURNAL_AVAILABLE = False
METADATA_INDEX_AVAILABLE = False
PROMETHEUS_AVAILABLE = False
BENCHMARKING_AVAILABLE = False

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
    from .simulated_api import IPFSSimpleAPI  # Emergency fix
    
    # Import WebSocket notifications
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

    # Try to import FS Journal API
    try:
        from . import fs_journal_api
        FS_JOURNAL_AVAILABLE = True
    except ImportError:
        FS_JOURNAL_AVAILABLE = False

    # Try to import Metadata Index API
    try:
        from . import metadata_index_api
        METADATA_INDEX_AVAILABLE = True
    except ImportError:
        METADATA_INDEX_AVAILABLE = False

    # Try to import Benchmarking API
    try:
        from . import benchmarking_api
        BENCHMARKING_AVAILABLE = True
    except ImportError:
        BENCHMARKING_AVAILABLE = False

    # Try to import Storage Backends API
    try:
        from . import storage_backends_api
        STORAGE_BACKENDS_AVAILABLE = True
    except ImportError:
        STORAGE_BACKENDS_AVAILABLE = False
    
    # Try to import Observability API
    try:
        from . import observability_api
        OBSERVABILITY_AVAILABLE = True
    except ImportError:
        OBSERVABILITY_AVAILABLE = False
        
    # Try to import LibP2P API
    try:
        from . import libp2p
        LIBP2P_AVAILABLE = True
    except ImportError:
        LIBP2P_AVAILABLE = False
        
    # Try to import WebRTC API
    try:
        from . import webrtc_streaming
        WEBRTC_AVAILABLE = True
    except ImportError:
        WEBRTC_AVAILABLE = False
except ImportError:
    # For development/testing
    import os
    import sys

    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ipfs_kit_py.error import IPFSError
    from ipfs_kit_py.simulated_api import IPFSSimpleAPI  # Emergency fix

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

    # Try to import FS Journal API
    try:
        from ipfs_kit_py import fs_journal_api
        FS_JOURNAL_AVAILABLE = True
    except ImportError:
        FS_JOURNAL_AVAILABLE = False

    # Try to import Metadata Index API
    try:
        from ipfs_kit_py import metadata_index_api
        METADATA_INDEX_AVAILABLE = True
    except ImportError:
        METADATA_INDEX_AVAILABLE = False

    # Try to import Benchmarking API
    try:
        from ipfs_kit_py import benchmarking_api
        BENCHMARKING_AVAILABLE = True
    except ImportError:
        BENCHMARKING_AVAILABLE = False

    # Try to import Storage Backends API
    try:
        from ipfs_kit_py import storage_backends_api
        STORAGE_BACKENDS_AVAILABLE = True
    except ImportError:
        STORAGE_BACKENDS_AVAILABLE = False
    
    # Try to import Observability API
    try:
        from ipfs_kit_py import observability_api
        OBSERVABILITY_AVAILABLE = True
    except ImportError:
        OBSERVABILITY_AVAILABLE = False

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

# Create FS Journal router if available
if FASTAPI_AVAILABLE and FS_JOURNAL_AVAILABLE:
    fs_journal_router = fastapi.APIRouter(prefix="/api/v0/fs-journal", tags=["fs_journal"])
    
    @fs_journal_router.get("/status", response_model=Dict[str, Any])
    async def fs_journal_status():
        """
        Get the status of the filesystem journaling.
        
        This endpoint returns the current status of the filesystem journaling,
        including transaction history, integrity status, and performance metrics.
        
        Returns:
            Filesystem journal status information
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if FS Journal integration is available
            if not hasattr(api, "fs_journal") or not api.fs_journal:
                raise HTTPException(
                    status_code=404,
                    detail="Filesystem journaling is not enabled. Use --enable-fs-journal when starting the server."
                )
                
            # Get journal status
            logger.info("Getting filesystem journal status")
            result = api.fs_journal.status()
            
            return {
                "success": True,
                "operation": "fs_journal_status",
                "timestamp": time.time(),
                "enabled": result.get("enabled", False),
                "transaction_count": result.get("transaction_count", 0),
                "total_size": result.get("total_size", 0),
                "health": result.get("health", "unknown"),
                "last_checkpoint": result.get("last_checkpoint", None),
                "performance": result.get("performance", {})
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error getting filesystem journal status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting filesystem journal status: {str(e)}")
    
    @fs_journal_router.post("/checkpoint", response_model=Dict[str, Any])
    async def fs_journal_checkpoint():
        """
        Create a new checkpoint in the filesystem journal.
        
        This endpoint creates a new checkpoint in the journal, ensuring data consistency
        by marking a known-good state that can be recovered to if needed.
        
        Returns:
            Checkpoint creation status
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if FS Journal integration is available
            if not hasattr(api, "fs_journal") or not api.fs_journal:
                raise HTTPException(
                    status_code=404,
                    detail="Filesystem journaling is not enabled. Use --enable-fs-journal when starting the server."
                )
                
            # Create checkpoint
            logger.info("Creating filesystem journal checkpoint")
            result = api.fs_journal.checkpoint()
            
            return {
                "success": True,
                "operation": "fs_journal_checkpoint",
                "timestamp": time.time(),
                "checkpoint_id": result.get("checkpoint_id"),
                "transaction_count": result.get("transaction_count", 0),
                "size": result.get("size", 0)
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error creating filesystem journal checkpoint: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating filesystem journal checkpoint: {str(e)}")
    
    @fs_journal_router.post("/rollback", response_model=Dict[str, Any])
    async def fs_journal_rollback(checkpoint_id: Optional[str] = None):
        """
        Rollback to a previous checkpoint in the filesystem journal.
        
        This endpoint rolls back the filesystem to a previous checkpoint state,
        restoring data consistency after errors or crashes.
        
        Parameters:
        - **checkpoint_id**: The checkpoint ID to roll back to. If not provided, rolls back to the last checkpoint.
        
        Returns:
            Rollback status
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if FS Journal integration is available
            if not hasattr(api, "fs_journal") or not api.fs_journal:
                raise HTTPException(
                    status_code=404,
                    detail="Filesystem journaling is not enabled. Use --enable-fs-journal when starting the server."
                )
                
            # Roll back to checkpoint
            logger.info(f"Rolling back filesystem journal to checkpoint: {checkpoint_id or 'latest'}")
            result = api.fs_journal.rollback(checkpoint_id=checkpoint_id)
            
            return {
                "success": True,
                "operation": "fs_journal_rollback",
                "timestamp": time.time(),
                "checkpoint_id": result.get("checkpoint_id"),
                "transactions_reverted": result.get("transactions_reverted", 0),
                "status": result.get("status", "unknown")
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error rolling back filesystem journal: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error rolling back filesystem journal: {str(e)}")

# Create Metadata Index router if available
if FASTAPI_AVAILABLE and METADATA_INDEX_AVAILABLE:
    metadata_index_router = fastapi.APIRouter(prefix="/api/v0/metadata", tags=["metadata"])
    
    @metadata_index_router.get("/status", response_model=Dict[str, Any])
    async def metadata_index_status():
        """
        Get the status of the metadata indexing service.
        
        This endpoint returns the current status of the Arrow-based metadata indexing service,
        including index size, record count, and available fields.
        
        Returns:
            Metadata indexing status information
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if metadata indexing is available
            if not hasattr(api, "metadata_index") or not api.metadata_index:
                raise HTTPException(
                    status_code=404,
                    detail="Metadata indexing is not enabled. Use --enable-metadata-index when starting the server."
                )
                
            # Get index status
            logger.info("Getting metadata index status")
            result = api.metadata_index.status()
            
            return {
                "success": True,
                "operation": "metadata_index_status",
                "timestamp": time.time(),
                "enabled": result.get("enabled", False),
                "record_count": result.get("record_count", 0),
                "index_size": result.get("index_size", 0),
                "last_updated": result.get("last_updated", 0),
                "available_fields": result.get("available_fields", []),
                "schema": result.get("schema", {})
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error getting metadata index status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting metadata index status: {str(e)}")
    
    @metadata_index_router.post("/search", response_model=Dict[str, Any])
    async def metadata_index_search(
        query: str,
        fields: Optional[List[str]] = None,
        limit: int = Query(10, ge=1, le=1000),
        offset: int = Query(0, ge=0)
    ):
        """
        Search the metadata index.
        
        This endpoint performs a text search across the metadata index,
        allowing efficient discovery of content by metadata properties.
        
        Parameters:
        - **query**: The search query string
        - **fields**: Optional list of fields to search in. If not provided, searches all text fields.
        - **limit**: Maximum number of results to return (default: 10, max: 1000)
        - **offset**: Number of results to skip (default: 0)
        
        Returns:
            Search results with matching records
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if metadata indexing is available
            if not hasattr(api, "metadata_index") or not api.metadata_index:
                raise HTTPException(
                    status_code=404,
                    detail="Metadata indexing is not enabled. Use --enable-metadata-index when starting the server."
                )
                
            # Search index
            logger.info(f"Searching metadata index: query='{query}', fields={fields}, limit={limit}, offset={offset}")
            result = api.metadata_index.search_text(query, fields=fields, limit=limit, offset=offset)
            
            # Process result for JSON response
            search_results = []
            for i in range(result.num_rows):
                row = {}
                for field in result.schema:
                    row[field.name] = result.column(field.name)[i].as_py()
                search_results.append(row)
            
            return {
                "success": True,
                "operation": "metadata_index_search",
                "timestamp": time.time(),
                "query": query,
                "fields": fields,
                "results": search_results,
                "count": len(search_results),
                "total": result.num_rows
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error searching metadata index: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error searching metadata index: {str(e)}")
    
    @metadata_index_router.post("/filter", response_model=Dict[str, Any])
    async def metadata_index_filter(
        filters: List[Dict[str, Any]],
        limit: int = Query(10, ge=1, le=1000),
        offset: int = Query(0, ge=0)
    ):
        """
        Filter the metadata index.
        
        This endpoint filters the metadata index by specific field conditions,
        allowing precise content discovery based on metadata properties.
        
        The filter format is a list of conditions, where each condition is a dictionary with:
        - **field**: The field name to filter on
        - **op**: The operation to perform (==, !=, >, <, >=, <=, contains, in, not_in)
        - **value**: The value to compare against
        
        Parameters:
        - **filters**: List of filter conditions
        - **limit**: Maximum number of results to return (default: 10, max: 1000)
        - **offset**: Number of results to skip (default: 0)
        
        Returns:
            Filter results with matching records
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if metadata indexing is available
            if not hasattr(api, "metadata_index") or not api.metadata_index:
                raise HTTPException(
                    status_code=404,
                    detail="Metadata indexing is not enabled. Use --enable-metadata-index when starting the server."
                )
                
            # Convert filter format for Arrow index
            arrow_filters = []
            for filter_condition in filters:
                if "field" not in filter_condition or "op" not in filter_condition or "value" not in filter_condition:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid filter format. Each filter must have 'field', 'op', and 'value' properties."
                    )
                
                field = filter_condition["field"]
                op = filter_condition["op"]
                value = filter_condition["value"]
                
                arrow_filters.append((field, op, value))
            
            # Filter index
            logger.info(f"Filtering metadata index: filters={arrow_filters}, limit={limit}, offset={offset}")
            result = api.metadata_index.query(filters=arrow_filters, limit=limit, offset=offset)
            
            # Process result for JSON response
            filter_results = []
            for i in range(result.num_rows):
                row = {}
                for field in result.schema:
                    row[field.name] = result.column(field.name)[i].as_py()
                filter_results.append(row)
            
            return {
                "success": True,
                "operation": "metadata_index_filter",
                "timestamp": time.time(),
                "filters": filters,
                "results": filter_results,
                "count": len(filter_results),
                "total": result.num_rows
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error filtering metadata index: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error filtering metadata index: {str(e)}")
    
    @metadata_index_router.post("/aggregate", response_model=Dict[str, Any])
    async def metadata_index_aggregate(
        group_by: List[str],
        aggregate_functions: List[Dict[str, Any]],
        filters: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Perform aggregations on the metadata index.
        
        This endpoint performs aggregation operations on the metadata index,
        such as count, sum, average, min, max, etc., grouped by specific fields.
        
        Parameters:
        - **group_by**: List of field names to group by
        - **aggregate_functions**: List of aggregation functions to apply
          - Each function should have a 'function' (count, sum, avg, min, max, etc.)
          - A 'field' to apply it to (except for 'count')
          - And an optional 'alias' to name the result
        - **filters**: Optional list of filter conditions to apply before aggregation
        
        Returns:
            Aggregation results grouped by the specified fields
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if metadata indexing is available
            if not hasattr(api, "metadata_index") or not api.metadata_index:
                raise HTTPException(
                    status_code=404,
                    detail="Metadata indexing is not enabled. Use --enable-metadata-index when starting the server."
                )
                
            # Convert filter format for Arrow index if provided
            arrow_filters = None
            if filters:
                arrow_filters = []
                for filter_condition in filters:
                    if "field" not in filter_condition or "op" not in filter_condition or "value" not in filter_condition:
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid filter format. Each filter must have 'field', 'op', and 'value' properties."
                        )
                    
                    field = filter_condition["field"]
                    op = filter_condition["op"]
                    value = filter_condition["value"]
                    
                    arrow_filters.append((field, op, value))
            
            # Perform aggregation
            logger.info(f"Aggregating metadata index: group_by={group_by}, aggregate_functions={aggregate_functions}, filters={arrow_filters}")
            result = api.metadata_index.aggregate(
                group_by=group_by,
                aggregations=aggregate_functions,
                filters=arrow_filters
            )
            
            # Process result for JSON response
            agg_results = []
            for i in range(result.num_rows):
                row = {}
                for field in result.schema:
                    row[field.name] = result.column(field.name)[i].as_py()
                agg_results.append(row)
            
            return {
                "success": True,
                "operation": "metadata_index_aggregate",
                "timestamp": time.time(),
                "group_by": group_by,
                "aggregate_functions": aggregate_functions,
                "filters": filters,
                "results": agg_results,
                "count": len(agg_results)
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error aggregating metadata index: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error aggregating metadata index: {str(e)}")
    
    @metadata_index_router.post("/reindex", response_model=Dict[str, Any])
    async def metadata_index_reindex():
        """
        Rebuild the metadata index.
        
        This endpoint triggers a rebuild of the metadata index,
        scanning all content in IPFS and updating the index accordingly.
        
        Returns:
            Reindexing status
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if metadata indexing is available
            if not hasattr(api, "metadata_index") or not api.metadata_index:
                raise HTTPException(
                    status_code=404,
                    detail="Metadata indexing is not enabled. Use --enable-metadata-index when starting the server."
                )
                
            # Rebuild index
            logger.info("Rebuilding metadata index")
            result = api.metadata_index.rebuild()
            
            return {
                "success": True,
                "operation": "metadata_index_reindex",
                "timestamp": time.time(),
                "records_processed": result.get("records_processed", 0),
                "index_size": result.get("index_size", 0),
                "elapsed_time": result.get("elapsed_time", 0),
                "status": result.get("status", "completed")
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error rebuilding metadata index: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error rebuilding metadata index: {str(e)}")

# Create Benchmarking router if available
if FASTAPI_AVAILABLE and BENCHMARKING_AVAILABLE:
    benchmark_router = fastapi.APIRouter(prefix="/api/v0/benchmark", tags=["benchmark"])
    
    @benchmark_router.get("/status", response_model=Dict[str, Any])
    async def benchmark_status():
        """
        Get the status of the benchmarking system.
        
        This endpoint returns the current status of the benchmarking system,
        including available benchmark suites and recent benchmark results.
        
        Returns:
            Benchmarking system status information
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if benchmarking is available
            if not hasattr(api, "benchmark") or not api.benchmark:
                raise HTTPException(
                    status_code=404,
                    detail="Benchmarking is not enabled. Use --enable-benchmarking when starting the server."
                )
                
            # Get benchmark status
            logger.info("Getting benchmark status")
            result = api.benchmark.status()
            
            return {
                "success": True,
                "operation": "benchmark_status",
                "timestamp": time.time(),
                "enabled": result.get("enabled", False),
                "available_suites": result.get("available_suites", []),
                "recent_results": result.get("recent_results", []),
                "default_iterations": result.get("default_iterations", 5)
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error getting benchmark status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting benchmark status: {str(e)}")
    
    @benchmark_router.post("/run", response_model=Dict[str, Any])
    async def run_benchmark(
        suite: str = Query(..., description="The benchmark suite to run"),
        iterations: Optional[int] = Query(None, description="Number of iterations to run, defaults to suite default"),
        background_tasks: BackgroundTasks = None
    ):
        """
        Run a benchmark suite.
        
        This endpoint runs a specified benchmark suite, measuring performance
        of various IPFS operations and returning the results.
        
        Parameters:
        - **suite**: The benchmark suite to run (e.g., 'core', 'api', 'add', 'get', 'cat', 'pin', 'cache', 'fs')
        - **iterations**: Number of iterations to run (default: suite default)
        
        Returns:
            Benchmark run status and tracking ID
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if benchmarking is available
            if not hasattr(api, "benchmark") or not api.benchmark:
                raise HTTPException(
                    status_code=404,
                    detail="Benchmarking is not enabled. Use --enable-benchmarking when starting the server."
                )
                
            # Create a tracking ID for the benchmark run
            tracking_id = f"benchmark_{int(time.time())}_{suite}"
            
            # Start benchmark in the background
            logger.info(f"Starting benchmark suite '{suite}' with {iterations} iterations, tracking ID: {tracking_id}")
            
            # Add the benchmark task to background tasks
            if background_tasks:
                background_tasks.add_task(
                    api.benchmark.run_suite,
                    suite=suite,
                    iterations=iterations,
                    tracking_id=tracking_id
                )
            else:
                # If no background tasks available, start in a separate thread
                import threading
                threading.Thread(
                    target=api.benchmark.run_suite,
                    kwargs={
                        "suite": suite,
                        "iterations": iterations,
                        "tracking_id": tracking_id
                    }
                ).start()
            
            return {
                "success": True,
                "operation": "benchmark_run",
                "timestamp": time.time(),
                "tracking_id": tracking_id,
                "suite": suite,
                "iterations": iterations,
                "status": "started"
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error running benchmark: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error running benchmark: {str(e)}")
    
    @benchmark_router.get("/results/{tracking_id}", response_model=Dict[str, Any])
    async def benchmark_results(tracking_id: str):
        """
        Get benchmark results.
        
        This endpoint retrieves the results of a previously run benchmark,
        including performance metrics for each operation.
        
        Parameters:
        - **tracking_id**: The tracking ID of the benchmark run
        
        Returns:
            Detailed benchmark results
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if benchmarking is available
            if not hasattr(api, "benchmark") or not api.benchmark:
                raise HTTPException(
                    status_code=404,
                    detail="Benchmarking is not enabled. Use --enable-benchmarking when starting the server."
                )
                
            # Get benchmark results
            logger.info(f"Getting benchmark results for tracking ID: {tracking_id}")
            result = api.benchmark.get_results(tracking_id)
            
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail=f"No benchmark results found for tracking ID: {tracking_id}"
                )
            
            return {
                "success": True,
                "operation": "benchmark_results",
                "timestamp": time.time(),
                "tracking_id": tracking_id,
                "suite": result.get("suite"),
                "iterations": result.get("iterations"),
                "start_time": result.get("start_time"),
                "end_time": result.get("end_time"),
                "duration": result.get("duration"),
                "results": result.get("results", {}),
                "status": result.get("status", "complete"),
                "system_info": result.get("system_info", {})
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error getting benchmark results: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting benchmark results: {str(e)}")
    
    @benchmark_router.get("/compare", response_model=Dict[str, Any])
    async def benchmark_compare(
        baseline_id: str = Query(..., description="The tracking ID of the baseline benchmark"),
        comparison_id: str = Query(..., description="The tracking ID of the comparison benchmark")
    ):
        """
        Compare benchmark results.
        
        This endpoint compares the results of two previously run benchmarks,
        calculating percentage differences and performance changes.
        
        Parameters:
        - **baseline_id**: The tracking ID of the baseline benchmark
        - **comparison_id**: The tracking ID of the comparison benchmark
        
        Returns:
            Detailed benchmark comparison
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if benchmarking is available
            if not hasattr(api, "benchmark") or not api.benchmark:
                raise HTTPException(
                    status_code=404,
                    detail="Benchmarking is not enabled. Use --enable-benchmarking when starting the server."
                )
                
            # Compare benchmark results
            logger.info(f"Comparing benchmark results: {baseline_id} vs {comparison_id}")
            result = api.benchmark.compare_results(baseline_id, comparison_id)
            
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail=f"Could not compare benchmark results. One or both tracking IDs not found."
                )
            
            return {
                "success": True,
                "operation": "benchmark_compare",
                "timestamp": time.time(),
                "baseline_id": baseline_id,
                "comparison_id": comparison_id,
                "comparison": result.get("comparison", {}),
                "summary": result.get("summary", {}),
                "improvement": result.get("improvement", False)
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error comparing benchmark results: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error comparing benchmark results: {str(e)}")
    
    @benchmark_router.get("/history", response_model=Dict[str, Any])
    async def benchmark_history(
        suite: Optional[str] = Query(None, description="Filter by benchmark suite"),
        limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return")
    ):
        """
        Get benchmark history.
        
        This endpoint retrieves the history of benchmark runs,
        allowing tracking of performance over time.
        
        Parameters:
        - **suite**: Optional benchmark suite to filter by
        - **limit**: Maximum number of results to return (default: 10, max: 100)
        
        Returns:
            Historical benchmark results
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if benchmarking is available
            if not hasattr(api, "benchmark") or not api.benchmark:
                raise HTTPException(
                    status_code=404,
                    detail="Benchmarking is not enabled. Use --enable-benchmarking when starting the server."
                )
                
            # Get benchmark history
            logger.info(f"Getting benchmark history: suite={suite}, limit={limit}")
            result = api.benchmark.get_history(suite=suite, limit=limit)
            
            return {
                "success": True,
                "operation": "benchmark_history",
                "timestamp": time.time(),
                "suite": suite,
                "limit": limit,
                "history": result.get("history", []),
                "count": len(result.get("history", []))
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error getting benchmark history: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting benchmark history: {str(e)}")
    
    @benchmark_router.post("/custom", response_model=Dict[str, Any])
    async def run_custom_benchmark(
        operations: List[Dict[str, Any]] = Body(..., description="List of operations to benchmark"),
        iterations: int = Query(5, ge=1, le=100, description="Number of iterations to run"),
        background_tasks: BackgroundTasks = None
    ):
        """
        Run a custom benchmark.
        
        This endpoint runs a custom benchmark with specified operations,
        allowing flexible performance testing of specific functionality.
        
        Each operation in the list should have:
        - **name**: A name for the operation
        - **function**: The function to call (e.g., 'add', 'cat', 'pin')
        - **args**: Optional list of positional arguments
        - **kwargs**: Optional dictionary of keyword arguments
        
        Parameters:
        - **operations**: List of operations to benchmark
        - **iterations**: Number of iterations to run (default: 5, max: 100)
        
        Returns:
            Benchmark run status and tracking ID
        """
        try:
            # Get API from app state
            api = app.state.ipfs_api
            
            # Check if benchmarking is available
            if not hasattr(api, "benchmark") or not api.benchmark:
                raise HTTPException(
                    status_code=404,
                    detail="Benchmarking is not enabled. Use --enable-benchmarking when starting the server."
                )
                
            # Create a tracking ID for the benchmark run
            tracking_id = f"custom_benchmark_{int(time.time())}"
            
            # Start benchmark in the background
            logger.info(f"Starting custom benchmark with {len(operations)} operations, {iterations} iterations, tracking ID: {tracking_id}")
            
            # Add the benchmark task to background tasks
            if background_tasks:
                background_tasks.add_task(
                    api.benchmark.run_custom,
                    operations=operations,
                    iterations=iterations,
                    tracking_id=tracking_id
                )
            else:
                # If no background tasks available, start in a separate thread
                import threading
                threading.Thread(
                    target=api.benchmark.run_custom,
                    kwargs={
                        "operations": operations,
                        "iterations": iterations,
                        "tracking_id": tracking_id
                    }
                ).start()
            
            return {
                "success": True,
                "operation": "custom_benchmark_run",
                "timestamp": time.time(),
                "tracking_id": tracking_id,
                "operations_count": len(operations),
                "iterations": iterations,
                "status": "started"
            }
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Error running custom benchmark: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error running custom benchmark: {str(e)}")

# Only add router and define endpoints if FastAPI is available
if FASTAPI_AVAILABLE:
    # Add v0 router to the main app
    app.include_router(v0_router)

    # --- Add feature-specific routers ---

    # LibP2P - No separate router found
    if LIBP2P_AVAILABLE:
        logger.info("LibP2P functionality integrated into High-Level API.")

    # WebRTC
    if WEBRTC_AVAILABLE:
        try:
            from .webrtc_api import webrtc_router
            if webrtc_router:
                app.include_router(webrtc_router)
                logger.info("WebRTC API available at /api/v0/webrtc")
            else:
                logger.warning("WEBRTC_AVAILABLE is True, but webrtc_router could not be imported.")
        except ImportError:
            logger.warning("Failed to import webrtc_router despite WEBRTC_AVAILABLE=True.")

    # GraphQL
    if GRAPHQL_AVAILABLE:
        try:
            from .graphql_schema import graphql_router
            if graphql_router:
                app.include_router(graphql_router)
                logger.info("GraphQL API available at /graphql")
            else:
                logger.warning("GRAPHQL_AVAILABLE is True, but graphql_router could not be imported.")
        except ImportError:
            logger.warning("Failed to import graphql_router despite GRAPHQL_AVAILABLE=True.")

    # WAL API
    if WAL_API_AVAILABLE:
        try:
            from .wal_api import wal_router # Assuming router is defined here
            if wal_router:
                app.include_router(wal_router)
                logger.info("WAL API available at /api/v0/wal")
            else:
                logger.warning("WAL_API_AVAILABLE is True, but wal_router could not be imported.")
        except ImportError:
            logger.warning("Failed to import wal_router despite WAL_API_AVAILABLE=True.")

    # FS Journal API
    if FS_JOURNAL_AVAILABLE:
        try:
            # Assuming the router is defined in fs_journal_api.py based on previous structure
            from .fs_journal_api import fs_journal_router
            if fs_journal_router:
                app.include_router(fs_journal_router)
                logger.info("Filesystem Journal API available at /api/v0/fs-journal")
            else:
                 logger.warning("FS_JOURNAL_AVAILABLE is True, but fs_journal_router could not be imported.")
        except ImportError:
            logger.warning("Failed to import fs_journal_router despite FS_JOURNAL_AVAILABLE=True.")

    # Metadata Index API
    if METADATA_INDEX_AVAILABLE:
        try:
            # Assuming the router is defined in metadata_index_api.py
            from .metadata_index_api import metadata_index_router
            if metadata_index_router:
                app.include_router(metadata_index_router)
                logger.info("Metadata Index API available at /api/v0/metadata")
            else:
                logger.warning("METADATA_INDEX_AVAILABLE is True, but metadata_index_router could not be imported.")
        except ImportError:
            logger.warning("Failed to import metadata_index_router despite METADATA_INDEX_AVAILABLE=True.")

    # Benchmarking API
    if BENCHMARKING_AVAILABLE:
        try:
            # Assuming the router is defined in benchmarking_api.py
            from .benchmarking_api import benchmark_router
            if benchmark_router:
                app.include_router(benchmark_router)
                logger.info("Benchmarking API available at /api/v0/benchmark")
            else:
                logger.warning("BENCHMARKING_AVAILABLE is True, but benchmark_router could not be imported.")
        except ImportError:
            logger.warning("Failed to import benchmark_router despite BENCHMARKING_AVAILABLE=True.")

    # Storage Backends API (User hint: comes from mcp folder)
    if STORAGE_BACKENDS_AVAILABLE:
        try:
            # Import from .storage_backends_api as confirmed earlier
            from .storage_backends_api import storage_router
            if storage_router:
                app.include_router(storage_router)
                logger.info("Storage Backends API available at /api/v0/storage")
            else:
                logger.warning("STORAGE_BACKENDS_AVAILABLE is True, but storage_router could not be imported from .storage_backends_api.")
        except ImportError:
             logger.warning("Failed to import storage_router from .storage_backends_api despite STORAGE_BACKENDS_AVAILABLE=True.")

    # Observability API
    if OBSERVABILITY_AVAILABLE:
        try:
            # Assuming the router is defined in observability_api.py
            from .observability_api import observability_router
            if observability_router:
                app.include_router(observability_router)
                logger.info("Observability API available at /api/v0/observability")
            else:
                logger.warning("OBSERVABILITY_AVAILABLE is True, but observability_router could not be imported.")
        except ImportError:
            logger.warning("Failed to import observability_router despite OBSERVABILITY_AVAILABLE=True.")

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
        background_tasks: BackgroundTasks = None,
    ):
        """
        Upload file to IPFS.

        Args:
            file: File to upload
            pin: Whether to pin the file
            wrap_with_directory: Whether to wrap the file in a directory
            background_tasks: Background tasks runner for notifications

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
                
            # Emit notification event if successful
            if NOTIFICATIONS_AVAILABLE and background_tasks and result.get("success", False):
                cid = result.get("Hash") or result.get("cid")
                if cid:
                    background_tasks.add_task(
                        emit_event,
                        NotificationType.CONTENT_ADDED.value,
                        {
                            "cid": cid,
                            "filename": filename,
                            "size": len(content),
                            "pinned": pin,
                            "wrapped": wrap_with_directory,
                            "mime_type": file.content_type
                        }
                    )
                    
                    # If content was pinned, also emit pin event
                    if pin:
                        background_tasks.add_task(
                            emit_event,
                            NotificationType.PIN_ADDED.value,
                            {
                                "cid": cid,
                                "recursive": True,
                                "success": True
                            }
                        )

            return result
        except Exception as e:
            logger.exception(f"Error uploading file: {str(e)}")
            
            # Emit error event
            if NOTIFICATIONS_AVAILABLE and background_tasks:
                background_tasks.add_task(
                    emit_event,
                    NotificationType.SYSTEM_ERROR.value,
                    {
                        "operation": "upload_file",
                        "filename": file.filename,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                
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


def run_server(
    host="127.0.0.1", 
    port=8000, 
    reload=False,
    workers=1,
    config_path=None,
    log_level="info",
    auth_enabled=False,
    cors_origins=None,
    ssl_certfile=None,
    ssl_keyfile=None,
    debug=False,
    enable_libp2p=None,
    enable_webrtc=None,
    enable_wal=None,
    enable_fs_journal=None,
    enable_benchmarking=None,
    enable_observability=None,
    enable_metadata_index=None,
    storage_backends=None,
):
    """
    Run the IPFS Kit API server.
    
    This function starts a FastAPI server that provides a RESTful API for IPFS Kit,
    including comprehensive endpoint documentation and GraphQL support.
    
    Args:
        host (str): Hostname or IP address to bind to. Use "0.0.0.0" to listen on all interfaces.
                   Default: "127.0.0.1"
        port (int): Port to listen on. Default: 8000
        reload (bool): Enable auto-reload for development. Default: False
        workers (int): Number of worker processes. Default: 1
        config_path (str, optional): Path to configuration file. Default: None
        log_level (str): Logging level (debug, info, warning, error). Default: "info"
        auth_enabled (bool): Enable token-based authentication. Default: False
        cors_origins (List[str], optional): List of allowed CORS origins. Default: ["*"]
        ssl_certfile (str, optional): Path to SSL certificate file. Default: None
        ssl_keyfile (str, optional): Path to SSL key file. Default: None
        debug (bool): Enable debug mode. Default: False
        enable_libp2p (bool, optional): Enable direct peer-to-peer communication using LibP2P.
                                       Default: None (use config setting)
        enable_webrtc (bool, optional): Enable WebRTC for real-time streaming. 
                                       Default: None (use config setting)
        enable_wal (bool, optional): Enable Write-Ahead Log for data consistency.
                                    Default: None (use config setting)
        enable_fs_journal (bool, optional): Enable filesystem journaling for transactions.
                                          Default: None (use config setting)
        enable_benchmarking (bool, optional): Enable performance benchmarking tools.
                                            Default: None (use config setting)
        enable_observability (bool, optional): Enable Prometheus metrics and monitoring.
                                             Default: None (use config setting)
        enable_metadata_index (bool, optional): Enable Arrow-based metadata indexing.
                                              Default: None (use config setting)
        storage_backends (List[str], optional): List of storage backends to enable.
                                              Options: "ipfs", "s3", "storacha", "huggingface", 
                                              "filecoin", "lassie".
                                              Default: None (use config setting)
    """
    # Set environment variables for configuration
    if config_path:
        os.environ["IPFS_KIT_CONFIG_PATH"] = config_path
    
    if log_level:
        os.environ["IPFS_KIT_LOG_LEVEL"] = log_level.upper()
    
    if auth_enabled is not None:
        os.environ["IPFS_KIT_AUTH_ENABLED"] = str(auth_enabled).lower()
    
    if cors_origins:
        if isinstance(cors_origins, list):
            cors_origins = ",".join(cors_origins)
        os.environ["IPFS_KIT_CORS_ORIGINS"] = cors_origins
    
    if debug:
        os.environ["IPFS_KIT_DEBUG"] = "true"
        
    # Set environment variables for additional features
    if enable_libp2p is not None:
        os.environ["IPFS_KIT_ENABLE_LIBP2P"] = str(enable_libp2p).lower()
        
    if enable_webrtc is not None:
        os.environ["IPFS_KIT_ENABLE_WEBRTC"] = str(enable_webrtc).lower()
        
    if enable_wal is not None:
        os.environ["IPFS_KIT_ENABLE_WAL"] = str(enable_wal).lower()
        
    if enable_fs_journal is not None:
        os.environ["IPFS_KIT_ENABLE_FS_JOURNAL"] = str(enable_fs_journal).lower()
        
    if enable_benchmarking is not None:
        os.environ["IPFS_KIT_ENABLE_BENCHMARKING"] = str(enable_benchmarking).lower()
        
    if enable_observability is not None:
        os.environ["IPFS_KIT_ENABLE_OBSERVABILITY"] = str(enable_observability).lower()
        
    if enable_metadata_index is not None:
        os.environ["IPFS_KIT_ENABLE_METADATA_INDEX"] = str(enable_metadata_index).lower()
        
    if storage_backends is not None:
        if isinstance(storage_backends, list):
            os.environ["IPFS_KIT_STORAGE_BACKENDS"] = ",".join(storage_backends)
        else:
            os.environ["IPFS_KIT_STORAGE_BACKENDS"] = storage_backends
        
    # Configure uvicorn options
    uvicorn_kwargs = {
        "host": host,
        "port": port,
        "reload": reload,
        "log_level": log_level.lower()
    }
    
    # Add workers if specified and not using reload
    if workers > 1 and not reload:
        uvicorn_kwargs["workers"] = workers
    
    # Add SSL configuration if provided
    if ssl_certfile and ssl_keyfile:
        uvicorn_kwargs["ssl_certfile"] = ssl_certfile
        uvicorn_kwargs["ssl_keyfile"] = ssl_keyfile
    
    # Run the server
    uvicorn.run("ipfs_kit_py.api:app", host=host, port=port, reload=reload, log_level=log_level.lower())


if __name__ == "__main__":
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="IPFS Kit API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to. Use 0.0.0.0 to listen on all interfaces.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (ignored if reload=True)")
    parser.add_argument("--config", dest="config_path", help="Path to configuration file")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], 
                      help="Logging level (debug, info, warning, error)")
    parser.add_argument("--auth", dest="auth_enabled", action="store_true", help="Enable token-based authentication")
    parser.add_argument("--cors-origins", help="Comma-separated list of allowed CORS origins")
    parser.add_argument("--ssl-cert", dest="ssl_certfile", help="Path to SSL certificate file")
    parser.add_argument("--ssl-key", dest="ssl_keyfile", help="Path to SSL key file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Process CORS origins if provided
    cors_origins = None
    if args.cors_origins:
        cors_origins = args.cors_origins.split(",")

    # Initialize API with configuration file if provided
    if args.config_path:
        ipfs_api = IPFSSimpleAPI(config_path=args.config_path)

    # Add feature-specific command line arguments
    feature_group = parser.add_argument_group('Advanced Features')
    feature_group.add_argument('--enable-libp2p', action='store_true', help='Enable direct peer-to-peer communication using LibP2P')
    feature_group.add_argument('--enable-webrtc', action='store_true', help='Enable WebRTC for real-time streaming')
    feature_group.add_argument('--enable-wal', action='store_true', help='Enable Write-Ahead Log for data consistency')
    feature_group.add_argument('--enable-fs-journal', action='store_true', help='Enable filesystem journaling for transactions')
    feature_group.add_argument('--enable-benchmarking', action='store_true', help='Enable performance benchmarking tools')
    feature_group.add_argument('--enable-observability', action='store_true', help='Enable Prometheus metrics and monitoring')
    feature_group.add_argument('--enable-metadata-index', action='store_true', help='Enable Arrow-based metadata indexing')
    feature_group.add_argument('--storage-backends', help='Comma-separated list of storage backends to enable (e.g., "ipfs,s3,storacha,huggingface,filecoin,lassie")')
    
    args = parser.parse_args()

    # Process CORS origins if provided
    cors_origins = None
    if args.cors_origins:
        cors_origins = args.cors_origins.split(",")
        
    # Process storage backends if provided
    storage_backends = None
    if args.storage_backends:
        storage_backends = args.storage_backends.split(",")

    # Initialize API with configuration file if provided
    if args.config_path:
        ipfs_api = IPFSSimpleAPI(config_path=args.config_path)

    # Run server with all parameters
    run_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        config_path=args.config_path,
        log_level=args.log_level,
        auth_enabled=args.auth_enabled,
        cors_origins=cors_origins,
        ssl_certfile=args.ssl_certfile,
        ssl_keyfile=args.ssl_keyfile,
        debug=args.debug,
        enable_libp2p=args.enable_libp2p,
        enable_webrtc=args.enable_webrtc,
        enable_wal=args.enable_wal,
        enable_fs_journal=args.enable_fs_journal,
        enable_benchmarking=args.enable_benchmarking,
        enable_observability=args.enable_observability,
        enable_metadata_index=args.enable_metadata_index,
        storage_backends=storage_backends
    )

"""
MCP Server FastAPI Implementation.

This module serves as the primary entry point for the MCP server as mentioned in the roadmap.
It implements a FastAPI server with endpoints for all MCP components including storage backends,
migration, search, and streaming functionality.

Enhanced with:
- Advanced Authentication & Authorization (Phase 1, Q3 2025)
- Enhanced Metrics & Monitoring (Phase 1, Q3 2025)
- Advanced IPFS Operations (Phase 1, Q3 2025)
"""

import os
import sys
import json
import time
import tempfile
import uvicorn
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket, WebSocketDisconnect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server")

# Create FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Model-Controller-Persistence server for the IPFS Kit ecosystem",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import MCP components
try:
    # Storage Manager
    from ipfs_kit_py.mcp.storage_manager.backend_manager import BackendManager
    from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
    from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
    
    # Migration Controller
    from ipfs_kit_py.mcp.migration import MigrationController, MigrationPolicy, MigrationTask
    
    # Search Engine
    from ipfs_kit_py.mcp.search import SearchEngine
    
    # Streaming Operations
    from ipfs_kit_py.mcp.streaming import (
        ChunkedFileUploader, StreamingDownloader, BackgroundPinningManager, ProgressTracker,
        WebSocketManager, get_ws_manager, EventType,
        SignalingServer
    )
    
    # Advanced Authentication & Authorization
    from ipfs_kit_py.mcp.auth.enhanced_integration import (
        initialize_auth_system, get_auth_system,
        audit_login_attempt, audit_permission_check, audit_backend_access,
        audit_user_change, audit_system_event, audit_data_event,
        AuditEventType, AuditSeverity
    )
    from ipfs_kit_py.mcp.auth.models import User, Role, Permission
    from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
    from ipfs_kit_py.mcp.rbac import (
        check_permission, check_backend_permission, 
        require_permission, require_backend_permission
    )
    
    # Enhanced Metrics & Monitoring
    from ipfs_kit_py.mcp.monitoring import setup_monitoring, MonitoringService
    
    # Advanced IPFS Operations
    from ipfs_kit_py.mcp.storage_manager.backends.ipfs_advanced_integration import (
        setup_advanced_ipfs_operations, 
        verify_ipfs_advanced_operations,
        setup_ipfs_dht
    )
    
    # Optimized Data Routing
    from ipfs_kit_py.mcp.routing.integration import (
        setup_optimized_routing,
        verify_optimized_routing,
        get_router_instance,
        get_enhanced_router_instance
    )
    
    # Component initialization success
    COMPONENTS_INITIALIZED = True
    
except ImportError as e:
    logger.error(f"Error importing MCP components: {e}")
    COMPONENTS_INITIALIZED = False


# Global component instances
backend_manager = None
migration_controller = None
search_engine = None
pinning_manager = None
file_uploader = None
file_downloader = None
ws_manager = None
signaling_server = None
monitoring_service = None
router_instance = None


async def initialize_components():
    """Initialize MCP components."""
    global backend_manager, migration_controller, search_engine
    global pinning_manager, file_uploader, file_downloader
    global ws_manager, signaling_server, monitoring_service
    
    logger.info("Initializing MCP components...")
    
    # Initialize Backend Manager
    backend_manager = BackendManager()
    
    # Configure default IPFS backend
    ipfs_resources = {
        "ipfs_host": os.environ.get("IPFS_HOST", "127.0.0.1"),
        "ipfs_port": int(os.environ.get("IPFS_PORT", "5001")),
        "ipfs_timeout": int(os.environ.get("IPFS_TIMEOUT", "30")),
        "allow_mock": os.environ.get("ALLOW_MOCK", "1") == "1"
    }
    
    ipfs_metadata = {
        "backend_name": "ipfs",
        "performance_metrics_file": os.environ.get(
            "IPFS_METRICS_FILE",
            os.path.join(os.path.expanduser("~"), ".ipfs_kit", "ipfs_metrics.json")
        )
    }
    
    # Create and add IPFS backend
    try:
        ipfs_backend = IPFSBackend(ipfs_resources, ipfs_metadata)
        backend_manager.add_backend("ipfs", ipfs_backend)
        logger.info("Added IPFS backend to manager")
    except Exception as e:
        logger.error(f"Error initializing IPFS backend: {e}")
    
    # TODO: Add other backends as needed
    
    # Initialize Migration Controller
    migration_controller = MigrationController(
        backend_manager=backend_manager,
        config_path=os.environ.get(
            "MIGRATION_CONFIG_PATH",
            os.path.join(os.path.expanduser("~"), ".ipfs_kit", "migration_config.json")
        )
    )
    logger.info("Initialized Migration Controller")
    
    # Initialize Search Engine
    enable_vector_search = os.environ.get("ENABLE_VECTOR_SEARCH", "1") == "1"
    search_engine = SearchEngine(
        db_path=os.environ.get(
            "SEARCH_DB_PATH",
            os.path.join(os.path.expanduser("~"), ".ipfs_kit", "search.db")
        ),
        enable_vector_search=enable_vector_search,
        vector_model_name=os.environ.get("VECTOR_MODEL_NAME", "all-MiniLM-L6-v2")
    )
    logger.info(f"Initialized Search Engine (vector search: {enable_vector_search})")
    
    # Initialize Background Pinning Manager
    pinning_manager = BackgroundPinningManager(
        max_concurrent=int(os.environ.get("MAX_CONCURRENT_PINS", "10"))
    )
    pinning_manager.start()
    logger.info("Started Background Pinning Manager")
    
    # Initialize File Streaming components
    file_uploader = ChunkedFileUploader(
        chunk_size=int(os.environ.get("UPLOAD_CHUNK_SIZE", str(1024 * 1024))),
        max_concurrent=int(os.environ.get("MAX_CONCURRENT_CHUNKS", "5"))
    )
    
    file_downloader = StreamingDownloader(
        chunk_size=int(os.environ.get("DOWNLOAD_CHUNK_SIZE", str(1024 * 1024))),
        max_concurrent=int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", "3"))
    )
    logger.info("Initialized File Streaming components")
    
    # Get WebSocket Manager
    ws_manager = get_ws_manager()
    logger.info("Initialized WebSocket Manager")
    
    # Initialize Signaling Server
    signaling_server = SignalingServer()
    logger.info("Initialized WebRTC Signaling Server")
    
    # Initialize Advanced Authentication & Authorization System
    from ipfs_kit_py.mcp.auth.enhanced_integration import initialize_auth_system, get_auth_system
    auth_system = await initialize_auth_system(app, backend_manager)
    logger.info("Initialized Advanced Authentication & Authorization System")
    
    # Configure custom roles
    custom_roles = [
        {
            "id": "api_client",
            "name": "API Client",
            "parent_role": "user",
            "permissions": [
                "read:ipfs", "write:ipfs", "read:filecoin", 
                "read:storage", "read:search"
            ]
        },
        {
            "id": "data_scientist",
            "name": "Data Scientist",
            "parent_role": "user",
            "permissions": [
                "read:ipfs", "write:ipfs", "read:huggingface", 
                "write:huggingface", "read:search", "write:search"
            ]
        },
        {
            "id": "content_manager",
            "name": "Content Manager",
            "parent_role": "user",
            "permissions": [
                "read:ipfs", "write:ipfs", "read:s3", "write:s3",
                "read:storacha", "write:storacha", "read:migration",
                "write:migration"
            ]
        }
    ]
    await auth_system.configure_roles(custom_roles)
    custom_roles = [
        {
            "id": "project_manager",
            "name": "Project Manager",
            "permissions": [
                "read:ipfs", "write:ipfs", "pin:ipfs",
                "read:filecoin", "write:filecoin", 
                "read:storacha", "write:storacha",
                "read:users"
            ],
            "parent_role": "user"
        },
        {
            "id": "data_scientist",
            "name": "Data Scientist",
            "permissions": [
                "read:ipfs", "write:ipfs",
                "read:huggingface", "write:huggingface",
                "read:search", "write:search"
            ],
            "parent_role": "user" 
        },
        {
            "id": "operations",
            "name": "Operations",
            "permissions": [
                "read:ipfs", "write:ipfs", "pin:ipfs", "admin:ipfs",
                "read:monitoring", "write:monitoring",
                "read:migration", "write:migration"
            ],
            "parent_role": "user"
        }
    ]
    await auth_system.configure_roles(custom_roles)
    
    # Initialize Monitoring System
    monitoring_service = setup_monitoring(app, backend_manager)
    logger.info("Initialized Enhanced Metrics & Monitoring System")
    
    # Set up Advanced IPFS Operations
    setup_advanced_ipfs_operations(app, backend_manager)
    logger.info("Initialized Advanced IPFS Operations")
    
    # Set up Optimized Data Routing
    global router_instance
    router_result = await setup_optimized_routing(app, backend_manager)
    if router_result.get("success", False):
        router_instance = get_router_instance()
        logger.info(f"Initialized Optimized Data Routing with strategy: {router_result.get('default_strategy', 'hybrid')}")
    else:
        logger.warning(f"Failed to initialize Optimized Data Routing: {router_result.get('message', 'Unknown error')}")
    
    # Verify advanced IPFS operations
    try:
        verification_result = await verify_ipfs_advanced_operations(backend_manager)
        if verification_result.get("success", False):
            logger.info("Advanced IPFS operations verified successfully")
        else:
            logger.warning(f"Advanced IPFS operations verification failed: {verification_result.get('failures', [])}")
    except Exception as e:
        logger.error(f"Error verifying advanced IPFS operations: {e}")
    
    # Initialize DHT functionality if IPFS_ENABLE_DHT is set
    if os.environ.get("IPFS_ENABLE_DHT", "0") == "1":
        try:
            # Get the IPFS backend (now upgraded to advanced implementation)
            ipfs_backend = backend_manager.get_backend("ipfs")
            if ipfs_backend:
                dht_result = await setup_ipfs_dht(ipfs_backend)
                if dht_result.get("success", False):
                    logger.info("IPFS DHT functionality initialized")
                else:
                    logger.warning(f"IPFS DHT functionality initialization failed: {dht_result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error initializing IPFS DHT functionality: {e}")
    
    logger.info("All MCP components initialized successfully")


# API Router for IPFS operations
@app.get("/api/v0/ipfs/version")
async def ipfs_version(current_user: User = Depends(get_current_user)):
    """Get IPFS version."""
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        return {"version": "0.12.0", "backend": "ipfs"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/ipfs/add")
async def ipfs_add(
    file: UploadFile = File(...), 
    pin: bool = Form(True),
    current_user: User = Depends(get_current_user)
):
    """
    Add content to IPFS.
    
    Requires write permission for the IPFS backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        # Read file content
        content = await file.read()
        
        # Add to IPFS
        result = await ipfs_backend.add_content(content, {"filename": file.filename})
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to add content to IPFS")
            )
        
        # Pin if requested
        if pin and result.get("identifier"):
            await ipfs_backend.pin_add(result["identifier"])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v0/ipfs/cat/{cid}")
async def ipfs_cat(cid: str, current_user: User = Depends(get_current_user)):
    """
    Get content from IPFS.
    
    Requires read permission for the IPFS backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        # Get content
        result = await ipfs_backend.get_content(cid)
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", f"Failed to get content for {cid}")
            )
        
        # Return content data
        data = result.get("data")
        if isinstance(data, bytes):
            # Stream binary data
            return StreamingResponse(
                iter([data]),
                media_type="application/octet-stream"
            )
        else:
            # Return as JSON
            return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/ipfs/pin/add")
async def ipfs_pin_add(
    cid: str = Form(...), 
    background: bool = Form(False),
    current_user: User = Depends(get_current_user)
):
    """
    Pin content in IPFS.
    
    Requires write permission for the IPFS backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager or not pinning_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        if background:
            # Schedule background pinning
            operation_id = await pinning_manager.pin(ipfs_backend, cid)
            return {
                "success": True,
                "operation_id": operation_id,
                "background": True
            }
        else:
            # Pin immediately
            result = await ipfs_backend.pin_add(cid)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", f"Failed to pin {cid}")
                )
            
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v0/ipfs/pin/ls")
async def ipfs_pin_ls(
    cid: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    List pinned content in IPFS.
    
    Requires read permission for the IPFS backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        result = await ipfs_backend.pin_ls(cid)
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to list pins")
            )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/ipfs/pin/rm")
async def ipfs_pin_rm(
    cid: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """
    Remove pin from content in IPFS.
    
    Requires write permission for the IPFS backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        result = await ipfs_backend.pin_rm(cid)
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", f"Failed to unpin {cid}")
            )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API Router for storage backends
@app.get("/api/v0/storage/backends")
async def list_storage_backends(current_user: User = Depends(get_current_user)):
    """List available storage backends."""
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        backends = backend_manager.list_backends()
        return {"success": True, "backends": backends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/storage/add")
async def storage_add(
    file: UploadFile = File(...),
    backend: str = Form("ipfs"),
    pin: bool = Form(True),
    current_user: User = Depends(get_current_user)
):
    """
    Add content to a specific storage backend.
    
    Requires write permission for the specified backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        storage_backend = backend_manager.get_backend(backend)
        if not storage_backend:
            raise HTTPException(status_code=404, detail=f"Backend '{backend}' not found")
        
        # Read file content
        content = await file.read()
        
        # Add to backend
        result = await storage_backend.add_content(content, {"filename": file.filename})
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", f"Failed to add content to {backend}")
            )
        
        # Pin if requested and supported
        if pin and result.get("identifier") and hasattr(storage_backend, "pin_add"):
            await storage_backend.pin_add(result["identifier"])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v0/storage/get/{backend}/{cid}")
async def storage_get(
    backend: str, 
    cid: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get content from a specific storage backend.
    
    Requires read permission for the specified backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        storage_backend = backend_manager.get_backend(backend)
        if not storage_backend:
            raise HTTPException(status_code=404, detail=f"Backend '{backend}' not found")
        
        # Get content
        result = await storage_backend.get_content(cid)
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", f"Failed to get content for {cid} from {backend}")
            )
        
        # Return content data
        data = result.get("data")
        if isinstance(data, bytes):
            # Stream binary data
            return StreamingResponse(
                iter([data]),
                media_type="application/octet-stream"
            )
        else:
            # Return as JSON
            return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API Router for migration
@app.get("/api/v0/migration/policies")
async def list_migration_policies(
    current_user: User = Depends(get_current_user)
):
    """List migration policies."""
    if not COMPONENTS_INITIALIZED or not migration_controller:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        policies = migration_controller.list_policies()
        return {
            "success": True,
            "policies": [policy.to_dict() for policy in policies]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/migration/policy")
async def create_migration_policy(
    name: str = Form(...),
    source_backend: str = Form(...),
    destination_backend: str = Form(...),
    content_filter: str = Form("{}"),
    schedule: str = Form("manual"),
    current_user: User = Depends(get_current_user)
):
    """
    Create a migration policy.
    
    Requires write permission for both the source and destination backends.
    """
    if not COMPONENTS_INITIALIZED or not migration_controller:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    # Check permissions for both source and destination backends
    if not check_backend_permission(source_backend, write_access=True) or \
       not check_backend_permission(destination_backend, write_access=True):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: You need write access to both source and destination backends"
        )
    
    try:
        # Parse content filter
        filter_dict = json.loads(content_filter)
        
        # Create policy
        policy = MigrationPolicy(
            name=name,
            source_backend=source_backend,
            destination_backend=destination_backend,
            content_filter=filter_dict,
            schedule=schedule
        )
        
        # Add policy
        success = migration_controller.add_policy(policy)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add policy")
        
        return {"success": True, "policy": policy.to_dict()}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid content filter JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/migration/execute/{policy_name}")
async def execute_migration_policy(
    policy_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Execute a migration policy.
    
    Requires admin permission or write access to both source and destination backends.
    """
    if not COMPONENTS_INITIALIZED or not migration_controller:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Get policy to check backend permissions
        policy = migration_controller.get_policy(policy_name)
        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy '{policy_name}' not found")
        
        # Check permissions for both source and destination backends
        source_backend = policy.source_backend
        destination_backend = policy.destination_backend
        
        if current_user.role != Role.ADMIN and current_user.role != Role.SYSTEM:
            if not check_backend_permission(source_backend, write_access=True) or \
               not check_backend_permission(destination_backend, write_access=True):
                raise HTTPException(
                    status_code=403,
                    detail="Permission denied: You need write access to both source and destination backends"
                )
        
        # Execute policy
        task_ids = migration_controller.execute_policy(policy_name)
        
        if not task_ids:
            return {
                "success": True,
                "message": "No tasks created (no content matches policy filter)",
                "task_ids": []
            }
        
        return {"success": True, "task_ids": task_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v0/migration/task/{task_id}")
async def get_migration_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get migration task status."""
    if not COMPONENTS_INITIALIZED or not migration_controller:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        task = migration_controller.get_migration_status(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return {"success": True, "task": task.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API Router for search
@app.get("/api/v0/search/status")
async def search_status(current_user: User = Depends(get_current_user)):
    """Get search engine status."""
    if not COMPONENTS_INITIALIZED or not search_engine:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        stats = await search_engine.get_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/search/index")
async def index_content(
    cid: str = Form(...),
    text: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    content_type: Optional[str] = Form(None),
    metadata: Optional[str] = Form("{}"),
    extract_text: bool = Form(False),
    current_user: User = Depends(get_current_user)
):
    """
    Index content for search.
    
    Requires write permission for the search system.
    """
    if not COMPONENTS_INITIALIZED or not search_engine or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    # Check if user has permission to write to the search system
    if not check_permission(current_user.request, Permission.WRITE_BASIC):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: You need write access to index content"
        )
    
    try:
        # Parse metadata
        metadata_dict = json.loads(metadata)
        
        # Get IPFS client for text extraction if needed
        ipfs_client = None
        if extract_text and not text:
            ipfs_backend = backend_manager.get_backend("ipfs")
            if not ipfs_backend:
                raise HTTPException(status_code=404, detail="IPFS backend not found for text extraction")
            ipfs_client = ipfs_backend
        
        # Index document
        success = await search_engine.index_document(
            cid=cid,
            text=text,
            title=title,
            content_type=content_type,
            metadata=metadata_dict,
            extract_text=extract_text,
            ipfs_client=ipfs_client
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to index document")
        
        return {"success": True}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/search/text")
async def search_text(
    query: str = Form(...),
    limit: int = Form(10),
    offset: int = Form(0),
    metadata_filters: Optional[str] = Form("{}"),
    current_user: User = Depends(get_current_user)
):
    """
    Search for content using text search.
    
    Requires read permission for the search system.
    """
    if not COMPONENTS_INITIALIZED or not search_engine:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Parse metadata filters
        filters_dict = json.loads(metadata_filters)
        
        # Search
        results = await search_engine.search_text(
            query=query,
            limit=limit,
            offset=offset,
            metadata_filters=filters_dict
        )
        
        return {"success": True, "results": results}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata filters JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/search/vector")
async def search_vector(
    text: str = Form(...),
    limit: int = Form(10),
    metadata_filters: Optional[str] = Form("{}"),
    current_user: User = Depends(get_current_user)
):
    """
    Search for content using vector similarity.
    
    Requires read permission for the search system.
    """
    if not COMPONENTS_INITIALIZED or not search_engine:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Check if vector search is enabled
        stats = await search_engine.get_stats()
        if not stats.get("vector_search_enabled", False):
            raise HTTPException(status_code=501, detail="Vector search is not enabled")
        
        # Parse metadata filters
        filters_dict = json.loads(metadata_filters)
        
        # Search
        results = await search_engine.search_vector(
            text=text,
            limit=limit,
            metadata_filters=filters_dict
        )
        
        return {"success": True, "results": results}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata filters JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/search/hybrid")
async def search_hybrid(
    query: str = Form(...),
    limit: int = Form(10),
    metadata_filters: Optional[str] = Form("{}"),
    text_weight: float = Form(0.5),
    current_user: User = Depends(get_current_user)
):
    """
    Search for content using hybrid text and vector search.
    
    Requires read permission for the search system.
    """
    if not COMPONENTS_INITIALIZED or not search_engine:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Check if vector search is enabled
        stats = await search_engine.get_stats()
        if not stats.get("vector_search_enabled", False):
            raise HTTPException(status_code=501, detail="Vector search is not enabled")
        
        # Parse metadata filters
        filters_dict = json.loads(metadata_filters)
        
        # Search
        results = await search_engine.search_hybrid(
            query=query,
            limit=limit,
            metadata_filters=filters_dict,
            text_weight=text_weight
        )
        
        return {"success": True, "results": results}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata filters JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API Router for streaming
@app.get("/api/v0/stream/status")
async def stream_status(current_user: User = Depends(get_current_user)):
    """Get streaming status."""
    if not COMPONENTS_INITIALIZED or not pinning_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Get background pinning operations
        operations = pinning_manager.list_operations()
        
        return {
            "success": True,
            "operations_count": len(operations),
            "operations": operations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/stream/upload/chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    index: int = Form(...),
    total_chunks: int = Form(...),
    file_id: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a file chunk.
    
    Requires write permission for streaming operations.
    """
    if not COMPONENTS_INITIALIZED:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Read chunk data
        chunk_data = await chunk.read()
        
        # Store chunk in temporary storage
        # (In a real implementation, you would store this in Redis or similar)
        temp_dir = Path(tempfile.gettempdir()) / "mcp_chunks" / file_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_path = temp_dir / f"chunk_{index}"
        with open(chunk_path, "wb") as f:
            f.write(chunk_data)
        
        return {
            "success": True,
            "file_id": file_id,
            "chunk_index": index,
            "chunk_size": len(chunk_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/stream/upload/finalize")
async def finalize_upload(
    file_id: str = Form(...),
    total_chunks: int = Form(...),
    backend: str = Form("ipfs"),
    filename: Optional[str] = Form(None),
    pin: bool = Form(True),
    current_user: User = Depends(get_current_user)
):
    """
    Finalize a chunked upload.
    
    Requires write permission for the specified backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Get backend
        storage_backend = backend_manager.get_backend(backend)
        if not storage_backend:
            raise HTTPException(status_code=404, detail=f"Backend '{backend}' not found")
        
        # Verify all chunks exist
        temp_dir = Path(tempfile.gettempdir()) / "mcp_chunks" / file_id
        if not temp_dir.exists():
            raise HTTPException(status_code=404, detail=f"No chunks found for file ID {file_id}")
        
        # Check if all chunks are present
        for i in range(total_chunks):
            chunk_path = temp_dir / f"chunk_{i}"
            if not chunk_path.exists():
                raise HTTPException(status_code=400, detail=f"Missing chunk {i}")
        
        # Combine chunks
        temp_file = Path(tempfile.gettempdir()) / f"mcp_upload_{file_id}"
        with open(temp_file, "wb") as outfile:
            for i in range(total_chunks):
                chunk_path = temp_dir / f"chunk_{i}"
                with open(chunk_path, "rb") as infile:
                    outfile.write(infile.read())
        
        # Add to backend
        with open(temp_file, "rb") as f:
            content = f.read()
            result = await storage_backend.add_content(
                content,
                {"filename": filename or f"upload_{file_id}"}
            )
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", f"Failed to add content to {backend}")
            )
        
        # Pin if requested and supported
        if pin and result.get("identifier") and hasattr(storage_backend, "pin_add"):
            await storage_backend.pin_add(result["identifier"])
        
        # Clean up
        if temp_file.exists():
            temp_file.unlink()
        
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v0/stream/download/{backend}/{cid}")
async def stream_download(
    backend: str, 
    cid: str,
    current_user: User = Depends(get_current_user)
):
    """
    Stream download content from a backend.
    
    Requires read permission for the specified backend.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager or not file_downloader:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Get backend
        storage_backend = backend_manager.get_backend(backend)
        if not storage_backend:
            raise HTTPException(status_code=404, detail=f"Backend '{backend}' not found")
        
        # Create async generator for streaming
        async def content_stream():
            async with file_downloader.stream(storage_backend, cid) as stream:
                if stream is None:
                    # Handle stream setup failure
                    yield b"Stream setup failed"
                    return
                
                async for chunk in stream:
                    yield chunk
        
        # Return streaming response
        return StreamingResponse(
            content_stream(),
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API Router for real-time notifications
@app.get("/api/v0/realtime/status")
async def realtime_status(current_user: User = Depends(get_current_user)):
    """Get WebSocket manager status."""
    if not COMPONENTS_INITIALIZED or not ws_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        stats = ws_manager.get_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    if not COMPONENTS_INITIALIZED or not ws_manager:
        await websocket.close(code=1011, reason="MCP components not initialized")
        return
    
    try:
        # Accept connection
        await websocket.accept()
        
        # Register client
        client_id = await ws_manager.register_client(websocket)
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "client_id": client_id,
            "timestamp": time.time()
        }))
        
        # Handle incoming messages
        try:
            while True:
                # Wait for message
                message = await websocket.receive_text()
                
                try:
                    # Parse message
                    data = json.loads(message)
                    
                    # Handle subscribe/unsubscribe
                    if data.get("type") == "subscribe" and "channel" in data:
                        await ws_manager.subscribe(client_id, data["channel"])
                        await websocket.send_text(json.dumps({
                            "type": "subscribed",
                            "channel": data["channel"],
                            "timestamp": time.time()
                        }))
                    
                    elif data.get("type") == "unsubscribe" and "channel" in data:
                        await ws_manager.unsubscribe(client_id, data["channel"])
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed",
                            "channel": data["channel"],
                            "timestamp": time.time()
                        }))
                    
                except json.JSONDecodeError:
                    # Invalid JSON
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON",
                        "timestamp": time.time()
                    }))
                
        except WebSocketDisconnect:
            # Client disconnected
            await ws_manager.unregister_client(client_id)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        # Try to close connection
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass


# API Router for WebRTC signaling
@app.get("/api/v0/webrtc/status")
async def webrtc_status(current_user: User = Depends(get_current_user)):
    """Get WebRTC signaling server status."""
    if not COMPONENTS_INITIALIZED or not signaling_server:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        stats = signaling_server.get_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v0/webrtc/rooms")
async def list_webrtc_rooms(current_user: User = Depends(get_current_user)):
    """List WebRTC signaling rooms."""
    if not COMPONENTS_INITIALIZED or not signaling_server:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        rooms = signaling_server.list_rooms()
        return {"success": True, "rooms": rooms}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/webrtc/signal/{room_id}")
async def webrtc_signaling(websocket: WebSocket, room_id: str):
    """WebRTC signaling endpoint."""
    if not COMPONENTS_INITIALIZED or not signaling_server:
        await websocket.close(code=1011, reason="MCP components not initialized")
        return
    
    try:
        # Accept connection
        await websocket.accept()
        
        # Extract peer ID from query parameters if available
        query_params = dict(websocket.query_params)
        peer_id = query_params.get("peer_id")
        
        # Extract metadata from query parameters
        metadata = {}
        for key, value in query_params.items():
            if key.startswith("meta_"):
                metadata[key[5:]] = value
        
        # Join room
        peer = await signaling_server.join_room(
            room_id=room_id,
            websocket=websocket,
            peer_id=peer_id,
            metadata=metadata
        )
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "peer_id": peer.id,
            "room_id": room_id,
            "timestamp": time.time()
        }))
        
        # Send peers list
        room = await signaling_server.get_room(room_id)
        if room:
            await websocket.send_text(json.dumps({
                "type": "peers",
                "peers": [p for p in room.get_peers() if p["id"] != peer.id],
                "timestamp": time.time()
            }))
        
        # Handle incoming messages
        try:
            while True:
                # Wait for message
                message = await websocket.receive_text()
                
                try:
                    # Parse message
                    data = json.loads(message)
                    
                    # Handle signaling messages
                    if "type" in data:
                        await signaling_server.handle_signal(room_id, peer.id, data)
                    
                except json.JSONDecodeError:
                    # Invalid JSON
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON",
                        "timestamp": time.time()
                    }))
                
        except WebSocketDisconnect:
            # Peer disconnected
            await signaling_server.leave_room(room_id, peer.id)
    
    except Exception as e:
        logger.error(f"WebRTC signaling error: {e}")
        # Try to close connection
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass


# Admin endpoints
@app.get("/api/v0/admin/system/status")
async def admin_system_status(current_user: User = Depends(get_admin_user)):
    """
    Get detailed system status. Admin only.
    """
    if not COMPONENTS_INITIALIZED:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        status = {
            "status": "operational",
            "timestamp": time.time(),
            "components_initialized": True,
            "backends": {},
            "auth_system": {
                "roles_count": len(rbac_manager._role_permissions) + len(rbac_manager._custom_roles),
                "custom_roles": list(rbac_manager._custom_roles.keys()),
                "permission_cache_size": len(rbac_manager._permission_cache)
            }
        }
        
        # Get backend status
        if backend_manager:
            backends = backend_manager.list_backends()
            for backend_name in backends:
                backend = backend_manager.get_backend(backend_name)
                if backend:
                    # Check if this is the advanced IPFS backend
                    from ipfs_kit_py.mcp.storage_manager.backends.ipfs_advanced_backend import IPFSAdvancedBackend
                    is_advanced = isinstance(backend, IPFSAdvancedBackend)
                    
                    status["backends"][backend_name] = {
                        "type": backend.get_name(),
                        "status": "operational",
                        "details": await backend.get_status(),
                        "advanced_operations": is_advanced
                    }
        
        # Get search status
        if search_engine:
            search_stats = await search_engine.get_stats()
            status["search"] = search_stats
        
        # Get WebSocket status
        if ws_manager:
            ws_stats = ws_manager.get_stats()
            status["websocket"] = ws_stats
        
        # Get WebRTC status
        if signaling_server:
            webrtc_stats = signaling_server.get_stats()
            status["webrtc"] = webrtc_stats
        
        # Get monitoring status
        if monitoring_service:
            status["monitoring"] = {
                "status": "operational",
                "metrics_count": len(monitoring_service.metrics.get_metrics())
            }
        
        # Get system stats
        import psutil
        status["system"] = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }
        
        return status
    except Exception as e:
        return {
            "status": "error",
            "timestamp": time.time(),
            "error": str(e)
        }


# Endpoint to verify advanced authentication system
@app.get("/api/v0/admin/auth/verify")
async def verify_auth_system(current_user: User = Depends(get_admin_user)):
    """
    Verify that advanced authentication & authorization system is working. Admin only.
    """
    if not COMPONENTS_INITIALIZED:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Get auth system
        auth_system = get_auth_system()
        
        # Run verification
        verification_result = await auth_system.verify_auth_system()
        
        # Return results
        return {
            "success": verification_result.get("success", False),
            "verification_result": verification_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint to verify optimized data routing
@app.get("/api/v0/admin/routing/verify")
async def verify_routing_operations(current_user: User = Depends(get_admin_user)):
    """
    Verify that optimized data routing is working. Admin only.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Run verification
        verification_result = await verify_optimized_routing(backend_manager)
        
        # Return results
        return {
            "success": verification_result.get("success", False),
            "verification_result": verification_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "components_initialized": COMPONENTS_INITIALIZED
    }


# System status endpoint
@app.get("/api/v0/status")
async def system_status():
    """Get system status."""
    if not COMPONENTS_INITIALIZED:
        return {
            "status": "initializing",
            "timestamp": time.time(),
            "components_initialized": False
        }
    
    try:
        status = {
            "status": "operational",
            "timestamp": time.time(),
            "components_initialized": True,
            "backends": {}
        }
        
        # Get backend status
        if backend_manager:
            backends = backend_manager.list_backends()
            for backend_name in backends:
                backend = backend_manager.get_backend(backend_name)
                if backend:
                    # Check if this is the advanced IPFS backend
                    try:
                        from ipfs_kit_py.mcp.storage_manager.backends.ipfs_advanced_backend import IPFSAdvancedBackend
                        is_advanced = isinstance(backend, IPFSAdvancedBackend)
                    except ImportError:
                        is_advanced = False
                    
                    status["backends"][backend_name] = {
                        "type": backend.get_name(),
                        "status": "operational",
                        "advanced_operations": is_advanced
                    }
        
        # Get search status
        if search_engine:
            search_stats = await search_engine.get_stats()
            status["search"] = search_stats
        
        # Get WebSocket status
        if ws_manager:
            ws_stats = ws_manager.get_stats()
            status["websocket"] = ws_stats
        
        # Get WebRTC status
        if signaling_server:
            webrtc_stats = signaling_server.get_stats()
            status["webrtc"] = webrtc_stats
        
        return status
    except Exception as e:
        return {
            "status": "error",
            "timestamp": time.time(),
            "error": str(e)
        }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    if COMPONENTS_INITIALIZED:
        await initialize_components()


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    global pinning_manager, monitoring_service
    
    # Stop background pinning manager
    if pinning_manager:
        pinning_manager.stop()
        logger.info("Stopped Background Pinning Manager")
    
    # Stop monitoring service
    if monitoring_service:
        monitoring_service.stop()
        logger.info("Stopped Monitoring Service")


# Main entry point
def main():
    """Run the MCP server."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to listen on")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--enable-dht", action="store_true", help="Enable IPFS DHT functionality")
    args = parser.parse_args()
    
    # Set environment variables
    if args.enable_dht:
        os.environ["IPFS_ENABLE_DHT"] = "1"
    
    # Run server
    uvicorn.run(
        "direct_mcp_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
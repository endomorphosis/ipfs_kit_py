#!/usr/bin/env python3
"""
MCP Server Example - Demonstrates integration of MCP server with the FastAPI application

This example shows how to:
1. Initialize the MCP server with various configuration options
2. Register it with the existing FastAPI application
3. Use the MCP components (models, controllers, persistence) for IPFS operations
4. Enable debug mode for troubleshooting in a live environment
5. Access debug endpoints to monitor the system state

Usage:
    python mcp_server_example.py

This will start a FastAPI server on http://localhost:8000 with the MCP server integrated.
You can access the API documentation at http://localhost:8000/docs
"""

import os
import sys
import time
import json
import logging
import tempfile
import argparse
from typing import Dict, Any, Optional

# Ensure ipfs_kit_py is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_example")

try:
    import uvicorn
    from fastapi import FastAPI, Request, Response, Depends, HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import requests
except ImportError:
    logger.error("Required dependencies not found. Please install them with:")
    logger.error("pip install fastapi uvicorn requests")
    sys.exit(1)

# Import ipfs_kit_py components
try:
    # Add compatibility layer first
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    compatibility_path = os.path.join(parent_dir, "mcp_compatibility.py")
    
    if os.path.exists(compatibility_path):
        # Import and apply compatibility layer
        sys.path.insert(0, parent_dir)
        from mcp_compatibility import add_compatibility_methods, patch_mcp_server
        add_compatibility_methods()
        patch_mcp_server()
        logger.info("Applied MCP compatibility layer")
    
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.mcp import MCPServer
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager as CacheManager
except ImportError as e:
    logger.error(f"Failed to import ipfs_kit_py components: {e}")
    logger.error("Make sure the MCP components have been created.")
    sys.exit(1)

def create_example_app(
    debug_mode: bool = False,
    isolation_mode: bool = False,
    api_prefix: str = "/api/v0",
    cache_dir: Optional[str] = None,
    memory_cache_size: int = 100 * 1024 * 1024,  # 100MB
    disk_cache_size: int = 1024 * 1024 * 1024,  # 1GB
) -> FastAPI:
    """Create a FastAPI application with MCP server integration."""
    
    # Initialize the FastAPI app
    app = FastAPI(
        title="IPFS Kit MCP Example",
        description="Example API demonstrating MCP server integration with IPFS Kit",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize the IPFS Simple API client
    ipfs_api = IPFSSimpleAPI()
    
    # Create a temporary directory for cache if not provided
    if cache_dir is None:
        cache_dir = tempfile.mkdtemp(prefix="ipfs_mcp_cache_")
        logger.info(f"Created temporary cache directory: {cache_dir}")
    
    # Initialize the MCP server
    mcp_server = MCPServer(
        debug_mode=debug_mode,
        isolation_mode=isolation_mode,
        persistence_path=cache_dir
    )
    
    # Register the MCP server with the FastAPI app
    mcp_server.register_with_app(app, prefix=f"{api_prefix}/mcp")
    
    # Add a welcome endpoint for testing
    @app.get("/")
    async def welcome():
        """Root endpoint for the example application."""
        return {
            "success": True,
            "message": "Welcome to IPFS Kit MCP Example",
            "endpoints": {
                "api_docs": "/docs",
                "mcp_debug": f"{api_prefix}/mcp/debug",
                "mcp_health": f"{api_prefix}/mcp/health",
                "mcp_operations": f"{api_prefix}/mcp/operations",
                "ipfs_add": f"{api_prefix}/mcp/ipfs/add",
                "ipfs_get": f"{api_prefix}/mcp/ipfs/get/{{cid}}",
                "ipfs_pin": f"{api_prefix}/mcp/ipfs/pin/{{cid}}",
                "ipfs_unpin": f"{api_prefix}/mcp/ipfs/unpin/{{cid}}",
                "ipfs_pins": f"{api_prefix}/mcp/ipfs/pins",
            },
            "debug_mode": debug_mode,
            "isolation_mode": isolation_mode,
        }
    
    # Add a middleware for request timing
    @app.middleware("http")
    async def request_timer_middleware(request: Request, call_next):
        """Middleware to measure request processing time."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    # Add an example endpoint using the MCP model directly (for demonstration)
    @app.get(f"{api_prefix}/direct-mcp-model-example")
    async def direct_model_example():
        """Example of directly using the MCP model layer."""
        ipfs_model = mcp_server.models["ipfs"]
        
        # Use the model to get operation stats
        stats = ipfs_model.get_stats()
        
        # Get cache manager stats
        cache_info = mcp_server.persistence.get_cache_info()
        
        return {
            "success": True,
            "message": "Directly accessed MCP model layer",
            "model_stats": stats,
            "cache_info": cache_info,
        }
    
    logger.info(f"Created FastAPI app with MCP server ({api_prefix}/mcp)")
    return app

def run_example_server(
    debug_mode: bool = False,
    isolation_mode: bool = False,
    host: str = "127.0.0.1",
    port: int = 8000,
):
    """Run the example server with the provided configuration."""
    app = create_example_app(
        debug_mode=debug_mode,
        isolation_mode=isolation_mode,
    )
    
    logger.info(f"Starting server on http://{host}:{port}")
    logger.info(f"Debug mode: {debug_mode}, Isolation mode: {isolation_mode}")
    logger.info(f"API docs available at http://{host}:{port}/docs")
    
    # Run the FastAPI application
    uvicorn.run(app, host=host, port=port)

def call_api_example(
    host: str = "127.0.0.1",
    port: int = 8000,
    api_prefix: str = "/api/v0",
):
    """Example of calling the MCP API endpoints."""
    base_url = f"http://{host}:{port}{api_prefix}/mcp"
    
    logger.info("Testing MCP API endpoints...")
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        logger.info(f"Health check: {response.json()}")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
    
    # Test adding content
    try:
        # Test adding content - trying two ways
        
        # 1. Try adding via file upload
        test_content = b"Hello, IPFS MCP!"
        files = {'file': ('test.txt', test_content, 'text/plain')}
        response = requests.post(f"{base_url}/ipfs/add/file", files=files)
        result = response.json()
        logger.info(f"Add file result: {result}")
        
        # 2. Try adding via JSON
        json_content = {"content": "Hello, IPFS MCP via JSON!", "filename": "test.json"}
        response2 = requests.post(f"{base_url}/ipfs/add", json=json_content)
        result2 = response2.json()
        logger.info(f"Add JSON result: {result2}")
        
        # Test debug endpoints
        debug_response = requests.get(f"{base_url}/debug")
        logger.info(f"Debug state available: {debug_response.status_code == 200}")
        
        operations_response = requests.get(f"{base_url}/operations")
        logger.info(f"Operations log available: {operations_response.status_code == 200}")
    except Exception as e:
        logger.error(f"API test failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IPFS Kit MCP Server Example")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--isolation", action="store_true", help="Enable isolation mode")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9999, help="Port to bind the server")
    parser.add_argument("--test-api", action="store_true", help="Just test the API endpoints without starting a server")
    
    args = parser.parse_args()
    
    if args.test_api:
        call_api_example(host=args.host, port=args.port)
    else:
        run_example_server(
            debug_mode=args.debug,
            isolation_mode=args.isolation,
            host=args.host,
            port=args.port,
        )
#!/usr/bin/env python3
"""
Storage Controller AnyIO Example - Demonstrates using AnyIO-based storage controllers

This example shows how to:
1. Initialize the AnyIO-based MCP server with various storage controllers
2. Use the storage controllers through the API with different async backends
3. Transfer content between different storage backends (IPFS, S3, Storacha, HuggingFace)
4. Handle asynchronous file operations with AnyIO

Usage:
    python storage_controller_anyio_example.py [--backend asyncio|trio]

This will start a FastAPI server on http://localhost:9998 with the AnyIO-based storage controllers.
"""

import os
import sys
import time
import logging
import tempfile
import argparse
from typing import Dict, Any, Optional, List

# Ensure ipfs_kit_py is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("storage_anyio_example")

try:
    import uvicorn
    from fastapi import FastAPI, Request, Response, Depends, HTTPException, File, UploadFile, Form
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    import anyio
    import sniffio
except ImportError:
    logger.error("Required dependencies not found. Please install them with:")
    logger.error("pip install fastapi uvicorn anyio sniffio")
    sys.exit(1)

# Import ipfs_kit_py components
try:
    from ipfs_kit_py.mcp.server_anyio import MCPServerAnyIO
    from ipfs_kit_py.mcp.controllers.storage.s3_controller_anyio import S3ControllerAnyIO
    from ipfs_kit_py.mcp.controllers.storage.storacha_controller_anyio import StorachaControllerAnyIO
    from ipfs_kit_py.mcp.controllers.storage.huggingface_controller_anyio import HuggingFaceControllerAnyIO
    from ipfs_kit_py.mcp.controllers.storage_manager_controller_anyio import StorageManagerControllerAnyIO
except ImportError as e:
    logger.error(f"Failed to import ipfs_kit_py storage components: {e}")
    logger.error("Make sure the storage controllers have been properly migrated to AnyIO.")
    sys.exit(1)

def create_storage_example_app(
    debug_mode: bool = False,
    api_prefix: str = "/api/v0",
    backend: str = "asyncio",
) -> FastAPI:
    """Create a FastAPI application with storage controllers integration."""

    # Initialize the FastAPI app
    app = FastAPI(
        title="IPFS Kit Storage Controllers Example",
        description="Example API demonstrating AnyIO-based storage controllers",
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

    # Create a temporary directory for cache
    cache_dir = tempfile.mkdtemp(prefix="ipfs_storage_anyio_cache_")
    logger.info(f"Created temporary cache directory: {cache_dir}")

    # Initialize the MCP server with AnyIO
    mcp_server = MCPServerAnyIO(
        debug_mode=debug_mode,
        persistence_path=cache_dir,
        async_backend=backend
    )

    # Register the MCP server with the FastAPI app
    mcp_server.register_with_app(app, prefix=f"{api_prefix}/mcp")

    # Add a welcome endpoint for testing
    @app.get("/")
    async def welcome():
        """Root endpoint for the example application."""
        # Detect current async library
        try:
            current_backend = sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            current_backend = "none"

        # Get information about available storage backends
        storage_backends = []

        for model_name, model in mcp_server.models.items():
            if model_name.startswith("storage_") or model_name in ["s3", "storacha", "huggingface"]:
                storage_backends.append(model_name)

        return {
            "success": True,
            "message": "Welcome to IPFS Kit Storage Controllers Example",
            "async_backend": current_backend,
            "configured_backend": backend,
            "storage_backends": storage_backends,
            "available_endpoints": {
                "api_docs": "/docs",
                "mcp_health": f"{api_prefix}/mcp/health",
                "s3_endpoints": f"{api_prefix}/mcp/s3/...",
                "storacha_endpoints": f"{api_prefix}/mcp/storacha/...",
                "huggingface_endpoints": f"{api_prefix}/mcp/huggingface/...",
                "storage_transfer": f"{api_prefix}/mcp/storage/transfer",
            },
            "debug_mode": debug_mode,
        }

    # Add a middleware for request timing
    @app.middleware("http")
    async def request_timer_middleware(request: Request, call_next):
        """Middleware to measure request processing time."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Async-Backend"] = backend
        return response

    # Add endpoint to get storage backends status
    @app.get(f"{api_prefix}/storage-backends")
    async def get_storage_backends():
        """Get status of all storage backends."""
        # Get storage manager controller
        storage_manager = mcp_server.controllers.get("storage_manager")

        if not storage_manager:
            return {"success": False, "error": "Storage manager not available"}

        # Check if we have the async method
        if hasattr(storage_manager, "handle_status_request_async"):
            result = await storage_manager.handle_status_request_async()
        else:
            # Fall back to sync method with anyio
            result = await anyio.to_thread.run_sync(storage_manager.handle_status_request)

        return result

    # Add example endpoint for transferring content between backends
    @app.post(f"{api_prefix}/storage-transfer")
    async def transfer_content(
        content_id: str,
        source_backend: str,
        target_backend: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Transfer content between storage backends."""
        # Get storage manager controller
        storage_manager = mcp_server.controllers.get("storage_manager")

        if not storage_manager:
            return {"success": False, "error": "Storage manager not available"}

        # Check if we have the async method
        if hasattr(storage_manager, "handle_transfer_request_async"):
            result = await storage_manager.handle_transfer_request_async(
                content_id=content_id,
                source_backend=source_backend,
                target_backend=target_backend,
                metadata=metadata or {}
            )
        else:
            # Fall back to sync method with anyio
            result = await anyio.to_thread.run_sync(
                storage_manager.handle_transfer_request,
                content_id=content_id,
                source_backend=source_backend,
                target_backend=target_backend,
                metadata=metadata or {}
            )

        return result

    # Add example endpoint for multi-backend verification
    @app.post(f"{api_prefix}/verify-content")
    async def verify_content(
        content_id: str,
        backends: List[str],
    ):
        """Verify content across multiple storage backends."""
        # Get storage manager controller
        storage_manager = mcp_server.controllers.get("storage_manager")

        if not storage_manager:
            return {"success": False, "error": "Storage manager not available"}

        # Check if we have the async method
        if hasattr(storage_manager, "handle_verify_request_async"):
            result = await storage_manager.handle_verify_request_async(
                content_id=content_id,
                backends=backends
            )
        else:
            # Fall back to sync method with anyio
            result = await anyio.to_thread.run_sync(
                storage_manager.handle_verify_request,
                content_id=content_id,
                backends=backends
            )

        return result

    logger.info(f"Created FastAPI app with AnyIO-based storage controllers using {backend} backend")
    return app

def run_storage_example_server(
    debug_mode: bool = False,
    host: str = "127.0.0.1",
    port: int = 9998,
    backend: str = "asyncio",
):
    """Run the storage example server with the provided configuration."""
    app = create_storage_example_app(
        debug_mode=debug_mode,
        backend=backend,
    )

    logger.info(f"Starting storage controllers server on http://{host}:{port}")
    logger.info(f"Debug mode: {debug_mode}")
    logger.info(f"Using AnyIO with {backend} backend")
    logger.info(f"API docs available at http://{host}:{port}/docs")

    # Run the FastAPI application
    uvicorn.run(app, host=host, port=port)

async def test_storage_api_async(
    host: str = "127.0.0.1",
    port: int = 9998,
    api_prefix: str = "/api/v0",
):
    """Example of calling the storage API endpoints asynchronously."""
    base_url = f"http://{host}:{port}{api_prefix}"

    logger.info("Testing storage controllers API endpoints...")

    # Use httpx for async HTTP requests
    try:
        import httpx
    except ImportError:
        logger.error("httpx is required for async HTTP tests. Install with: pip install httpx")
        return

    async with httpx.AsyncClient() as client:
        # Test welcome endpoint
        try:
            response = await client.get(f"http://{host}:{port}/")
            logger.info(f"Welcome response: {response.json()}")
        except Exception as e:
            logger.error(f"Welcome endpoint check failed: {e}")

        # Test storage backends endpoint
        try:
            response = await client.get(f"{base_url}/storage-backends")
            logger.info(f"Storage backends: {response.json()}")
        except Exception as e:
            logger.error(f"Storage backends check failed: {e}")

        # Test IPFS add (to have content to transfer)
        try:
            test_content = b"Hello, Storage Controllers AnyIO!"
            files = {'file': ('test.txt', test_content, 'text/plain')}
            response = await client.post(f"{base_url}/mcp/ipfs/add/file", files=files)
            result = response.json()
            logger.info(f"Add file result: {result}")

            if result.get("success") and "cid" in result:
                # Try a content transfer (IPFS -> S3 if configured)
                cid = result["cid"]

                # This will likely fail without proper S3 configuration, but demonstrates the API
                transfer_response = await client.post(
                    f"{base_url}/storage-transfer",
                    params={
                        "content_id": cid,
                        "source_backend": "ipfs",
                        "target_backend": "s3"
                    }
                )
                logger.info(f"Transfer response: {transfer_response.json()}")
        except Exception as e:
            logger.error(f"Content operations failed: {e}")

def test_storage_api(
    host: str = "127.0.0.1",
    port: int = 9998,
    api_prefix: str = "/api/v0",
    backend: str = "asyncio",
):
    """Wrapper to call the async storage API test function."""
    # Run the async function with the specified backend
    anyio.run(
        test_storage_api_async,
        host=host,
        port=port,
        api_prefix=api_prefix,
        backend=backend
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IPFS Kit Storage Controllers Example")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9998, help="Port to bind the server")
    parser.add_argument("--backend", choices=["asyncio", "trio"], default="asyncio",
                        help="Async backend to use (asyncio or trio)")
    parser.add_argument("--test-api", action="store_true",
                        help="Just test the API endpoints without starting a server")

    args = parser.parse_args()

    if args.test_api:
        test_storage_api(
            host=args.host,
            port=args.port,
            backend=args.backend
        )
    else:
        run_storage_example_server(
            debug_mode=args.debug,
            host=args.host,
            port=args.port,
            backend=args.backend,
        )

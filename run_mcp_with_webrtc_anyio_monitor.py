#!/usr/bin/env python3
"""
MCP Server with WebRTC AnyIO and Monitoring Support

This script runs an MCP server with:
1. WebRTC capabilities (streaming, connections, etc.)
2. AnyIO support for async operations
3. Enhanced monitoring dashboard for WebRTC connections
4. Support for both asyncio and trio backends

Features:
- Real-time WebRTC connection statistics
- Monitoring visualization dashboard
- Integration with AnyIO for consistent async behavior
- Backend selection for production environments
"""

import os
import sys
import time
import logging
import argparse
import uuid
import json
from typing import Dict, List, Any, Optional, Union
import shutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("webrtc_mcp_monitor")

# Try to import required packages
try:
    import anyio
    import sniffio
    import fastapi
    from fastapi import FastAPI, APIRouter, Request, Response
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse
    
    HAS_REQUIRED_PACKAGES = True
except ImportError as e:
    HAS_REQUIRED_PACKAGES = False
    logger.error(f"Required packages not available: {e}")
    logger.error("Install with: pip install anyio sniffio fastapi uvicorn")
    sys.exit(1)

# Add the project root to Python path if needed
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Try to import the MCP server with AnyIO support
try:
    from ipfs_kit_py.mcp.server_anyio import MCPServer
    HAS_MCP_SERVER = True
except ImportError:
    HAS_MCP_SERVER = False
    logger.error("MCP server with AnyIO support not available")
    sys.exit(1)

# Try to import the WebRTC monitor integration
try:
    from fixes.webrtc_anyio_monitor_integration import apply_enhanced_fixes, WebRTCMonitor
    HAS_WEBRTC_MONITOR = True
except ImportError:
    HAS_WEBRTC_MONITOR = False
    logger.error("WebRTC monitor integration not available")
    logger.error("Check that fixes/webrtc_anyio_monitor_integration.py exists")
    sys.exit(1)

def create_server(args):
    """
    Create and configure the MCP server with WebRTC and AnyIO support.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Configured FastAPI app
    """
    # Create the FastAPI app
    app = FastAPI(
        title="WebRTC MCP Server with AnyIO and Monitoring",
        description="IPFS MCP Server with WebRTC, AnyIO, and Monitoring support",
        version="0.3.0"
    )
    
    # Create the MCP AnyIO server with the specified backend
    mcp_server = MCPServer(
        debug_mode=args.debug,
        log_level=args.log_level,
        persistence_path=args.persistence_path,
        isolation_mode=args.isolation
    )
    
    # Apply WebRTC monitoring integration
    if HAS_WEBRTC_MONITOR:
        # Create log directory for WebRTC monitoring
        log_dir = os.path.join(args.persistence_path, "webrtc_logs") if args.persistence_path else None
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Apply AnyIO fixes with monitoring
        webrtc_monitor = apply_enhanced_fixes(
            mcp_server=mcp_server,
            log_dir=log_dir,
            debug_mode=args.debug
        )
        
        if webrtc_monitor:
            logger.info("WebRTC monitoring successfully applied")
        else:
            logger.warning("Failed to apply WebRTC monitoring")
    else:
        logger.warning("WebRTC monitoring not available")
        webrtc_monitor = None
    
    # Add root endpoint that reports the active backend
    @app.get("/")
    async def read_root():
        # Detect current async library for info
        current_backend = None
        try:
            current_backend = sniffio.current_async_library()
        except (ImportError, sniffio.AsyncLibraryNotFoundError):
            current_backend = "none"
        
        return {
            "name": "IPFS Kit MCP AnyIO Server with WebRTC Monitoring",
            "version": "0.3.0",
            "status": "running",
            "webrtc_enabled": True,
            "webrtc_monitoring": webrtc_monitor is not None,
            "async_backend": args.backend,
            "detected_backend": current_backend,
            "anyio_integration": True
        }
    
    # Add monitoring dashboard endpoint
    @app.get("/monitoring/webrtc", response_class=HTMLResponse)
    async def webrtc_dashboard(request: Request):
        # Check if the WebRTC monitor is available
        if not webrtc_monitor:
            return HTMLResponse(content="<html><body><h1>WebRTC Monitoring Not Available</h1></body></html>")
        
        # Serve the dashboard HTML from the static directory
        dashboard_path = os.path.join(project_root, "static", "webrtc_dashboard.html")
        try:
            with open(dashboard_path, "r") as f:
                dashboard_html = f.read()
            return HTMLResponse(content=dashboard_html)
        except FileNotFoundError:
            return HTMLResponse(content="<html><body><h1>WebRTC Dashboard Not Found</h1></body></html>")
    
    # Add WebRTC monitor API endpoints
    @app.get("/api/v0/webrtc/monitor/status")
    async def webrtc_monitor_status():
        if not webrtc_monitor:
            return {"success": False, "error": "WebRTC monitoring not available"}
        
        # Get monitor summary
        return {
            "success": True,
            "summary": webrtc_monitor.get_summary(),
            "timestamp": time.time()
        }
    
    # Add endpoint to get connection statistics
    @app.get("/api/v0/webrtc/connections")
    async def webrtc_connections(connection_id: Optional[str] = None):
        if not webrtc_monitor:
            return {"success": False, "error": "WebRTC monitoring not available"}
        
        return webrtc_monitor.get_connection_stats(connection_id)
    
    # Add endpoint to get operation statistics
    @app.get("/api/v0/webrtc/operations")
    async def webrtc_operations():
        if not webrtc_monitor:
            return {"success": False, "error": "WebRTC monitoring not available"}
        
        return webrtc_monitor.get_active_operations()
    
    # Add endpoint to get task statistics
    @app.get("/api/v0/webrtc/tasks")
    async def webrtc_tasks():
        if not webrtc_monitor:
            return {"success": False, "error": "WebRTC monitoring not available"}
        
        return webrtc_monitor.get_pending_tasks()
    
    # Register MCP server with app
    mcp_server.register_with_app(app, prefix=args.api_prefix)
    
    # Mount static files directory
    static_dir = os.path.join(project_root, "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    return app

def main():
    """Main entry point for the server."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run MCP server with WebRTC, AnyIO, and Monitoring support")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--isolation", action="store_true", help="Run in isolation mode")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--persistence-path", help="Path for persistence files")
    parser.add_argument("--api-prefix", default="/api/v0", help="API prefix")
    parser.add_argument("--backend", default="asyncio", choices=["asyncio", "trio"], 
                        help="AnyIO backend to use")
    parser.add_argument("--run-tests", action="store_true", 
                        help="Run WebRTC tests after server starts")
    args = parser.parse_args()
    
    # Create the server
    logger.info(f"Creating server with backend: {args.backend}")
    app = create_server(args)
    
    # Configure Uvicorn
    import uvicorn
    config = uvicorn.Config(
        app=app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower()
    )
    server = uvicorn.Server(config)
    
    # Set environment variable for AnyIO backend
    os.environ["ANYIO_BACKEND"] = args.backend
    
    # Special handling for trio backend with Uvicorn
    # (Uvicorn has better support for asyncio)
    if args.backend == "trio":
        logger.info("Running server with asyncio backend for Uvicorn compatibility")
        logger.info("Trio support will be emulated within AnyIO context")
        anyio.run(server.serve, backend="asyncio")
    else:
        # For asyncio, we can use the standard approach
        anyio.run(server.serve, backend=args.backend)

if __name__ == "__main__":
    main()
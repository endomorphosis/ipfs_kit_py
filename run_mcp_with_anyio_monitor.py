#!/usr/bin/env python3
"""
Run MCP Server with WebRTC AnyIO & Monitoring Integration

This script runs the MCP server with both:
1. The AnyIO event loop fixes for WebRTC methods
2. The WebRTC monitoring capabilities

Command-line options:
--port: Port to run the server on (default: 9999)
--host: Host to bind to (default: 127.0.0.1)
--debug: Enable debug mode (default: False)
--log-dir: Directory to store WebRTC logs (default: ./logs)
--isolation: Run with isolated IPFS repository (default: False)
--webrtc-test: Include WebRTC test endpoint (default: False)
--run-tests: Run WebRTC tests after starting the server (default: False)
"""

import os
import sys
import time
import json
import argparse
import logging
import threading
import asyncio
import subprocess
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mcp_server.log")
    ]
)
logger = logging.getLogger(__name__)

# Add fixes directory to path
fixes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixes")
if fixes_dir not in sys.path:
    sys.path.append(fixes_dir)

# Check for required packages
try:
    import anyio
    import sniffio
    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False
    logger.warning("AnyIO not available. Install with: pip install anyio sniffio")

# Try to import our webrtc_anyio_monitor_integration module
try:
    from webrtc_anyio_monitor_integration import apply_enhanced_fixes
    HAS_INTEGRATION = True
except ImportError as e:
    HAS_INTEGRATION = False
    logger.error(f"Could not import webrtc_anyio_monitor_integration: {e}")

# Check for FastAPI
try:
    import fastapi
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    logger.warning("FastAPI not available. Install with: pip install fastapi uvicorn")

def create_mcp_server(debug_mode=False, isolation_mode=False, log_dir=None, include_test_endpoint=False):
    """
    Create an MCP server instance with WebRTC fixes and monitoring.
    
    Args:
        debug_mode: Enable debug mode
        isolation_mode: Run with isolated IPFS repository
        log_dir: Directory for WebRTC logs
        include_test_endpoint: Include WebRTC test endpoint
        
    Returns:
        MCP server instance
    """
    try:
        from ipfs_kit_py.mcp.server import MCPServer
        
        # Create server
        mcp_server = MCPServer(
            debug_mode=debug_mode,
            isolation_mode=isolation_mode
        )
        
        # Apply WebRTC fixes and monitoring
        if HAS_INTEGRATION:
            monitor = apply_enhanced_fixes(mcp_server, log_dir=log_dir, debug_mode=debug_mode)
            if monitor:
                logger.info("Successfully applied WebRTC fixes and monitoring")
                mcp_server.webrtc_monitor = monitor
                
                # Add monitor endpoint if debug mode is enabled
                if debug_mode and HAS_FASTAPI:
                    add_monitor_endpoints(mcp_server, monitor)
        else:
            logger.warning("WebRTC integration not available. Server will run without fixes.")
            
        # Add test endpoint if requested
        if include_test_endpoint and HAS_FASTAPI:
            add_webrtc_test_endpoint(mcp_server)
            
        return mcp_server
        
    except ImportError as e:
        logger.error(f"Error importing MCP server: {e}")
        return None

def add_monitor_endpoints(mcp_server, monitor):
    """
    Add WebRTC monitoring endpoints to the MCP server.
    
    Args:
        mcp_server: MCP server instance
        monitor: WebRTC monitor instance
    """
    from fastapi import APIRouter
    
    # Create router for monitoring endpoints
    monitor_router = APIRouter(
        prefix="/webrtc/monitor",
        tags=["webrtc_monitor"]
    )
    
    # Add monitoring endpoints
    @monitor_router.get("/summary")
    async def get_monitor_summary():
        """Get a summary of WebRTC monitoring."""
        return monitor.get_summary()
    
    @monitor_router.get("/connections")
    async def get_connections():
        """Get all tracked WebRTC connections."""
        return monitor.get_connection_stats()
    
    @monitor_router.get("/connections/{connection_id}")
    async def get_connection(connection_id: str):
        """Get a specific WebRTC connection."""
        return monitor.get_connection_stats(connection_id)
    
    @monitor_router.get("/operations")
    async def get_operations():
        """Get active WebRTC operations."""
        return monitor.get_active_operations()
    
    @monitor_router.get("/tasks")
    async def get_tasks():
        """Get pending WebRTC async tasks."""
        return monitor.get_pending_tasks()
    
    # Add the router to the server
    mcp_server.register_router(monitor_router)
    
    logger.info("Added WebRTC monitoring endpoints")

def add_webrtc_test_endpoint(mcp_server):
    """
    Add WebRTC test endpoint to the MCP server.
    
    Args:
        mcp_server: MCP server instance
    """
    from fastapi import APIRouter, HTTPException
    
    # Create router for test endpoint
    test_router = APIRouter(
        prefix="/webrtc/test",
        tags=["webrtc_test"]
    )
    
    # Add test endpoint
    @test_router.get("/")
    async def test_webrtc():
        """Test WebRTC functionality."""
        return {
            "success": True,
            "message": "WebRTC test endpoint is working",
            "timestamp": time.time()
        }
    
    @test_router.post("/close/{connection_id}")
    async def test_close_connection(connection_id: str):
        """
        Test closing a WebRTC connection.
        
        This endpoint is for testing the async WebRTC method with AnyIO fixes.
        """
        if not hasattr(mcp_server, 'models') or 'ipfs' not in mcp_server.models:
            raise HTTPException(status_code=500, detail="IPFS model not available")
            
        ipfs_model = mcp_server.models['ipfs']
        
        if not hasattr(ipfs_model, 'async_close_webrtc_connection'):
            raise HTTPException(status_code=500, detail="async_close_webrtc_connection not available")
            
        # Call the async method
        result = await ipfs_model.async_close_webrtc_connection(connection_id)
        
        if not result.get("success", False):
            raise HTTPException(status_code=404, detail=result.get("error", "Unknown error"))
            
        return result
    
    @test_router.post("/close_all")
    async def test_close_all_connections():
        """
        Test closing all WebRTC connections.
        
        This endpoint is for testing the async WebRTC method with AnyIO fixes.
        """
        if not hasattr(mcp_server, 'models') or 'ipfs' not in mcp_server.models:
            raise HTTPException(status_code=500, detail="IPFS model not available")
            
        ipfs_model = mcp_server.models['ipfs']
        
        if not hasattr(ipfs_model, 'async_close_all_webrtc_connections'):
            raise HTTPException(status_code=500, detail="async_close_all_webrtc_connections not available")
            
        # Call the async method
        result = await ipfs_model.async_close_all_webrtc_connections()
        
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
            
        return result
    
    # Add the router to the server
    mcp_server.register_router(test_router)
    
    logger.info("Added WebRTC test endpoint")

def run_webrtc_tests(host, port):
    """
    Run WebRTC tests against the running server.
    
    Args:
        host: Server host
        port: Server port
    """
    import requests
    import time
    
    # Give the server time to start
    time.sleep(2)
    
    logger.info("Running WebRTC tests...")
    
    # Base URL for API
    base_url = f"http://{host}:{port}"
    
    # Test health endpoint first
    try:
        health_response = requests.get(f"{base_url}/health")
        if health_response.status_code == 200:
            logger.info("Health check passed")
        else:
            logger.error(f"Health check failed: {health_response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error calling health endpoint: {e}")
        return False
    
    # Test WebRTC test endpoint
    try:
        test_response = requests.get(f"{base_url}/webrtc/test/")
        if test_response.status_code == 200:
            logger.info("WebRTC test endpoint check passed")
        else:
            logger.error(f"WebRTC test endpoint check failed: {test_response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error calling WebRTC test endpoint: {e}")
        return False
    
    # Test closing a connection (this will likely fail, but should fail gracefully)
    try:
        close_response = requests.post(f"{base_url}/webrtc/test/close/test-connection")
        logger.info(f"Close connection test response: {close_response.status_code}")
        logger.info(f"Close connection test content: {close_response.json() if close_response.status_code < 400 else close_response.text}")
    except Exception as e:
        logger.warning(f"Error in close connection test: {e}")
    
    # Test closing all connections
    try:
        close_all_response = requests.post(f"{base_url}/webrtc/test/close_all")
        logger.info(f"Close all connections test response: {close_all_response.status_code}")
        logger.info(f"Close all connections test content: {close_all_response.json() if close_all_response.status_code < 400 else close_all_response.text}")
    except Exception as e:
        logger.warning(f"Error in close all connections test: {e}")
    
    # Check monitor summary
    try:
        summary_response = requests.get(f"{base_url}/webrtc/monitor/summary")
        if summary_response.status_code == 200:
            logger.info("Monitor summary check passed")
            logger.info(f"Monitor summary: {json.dumps(summary_response.json(), indent=2)}")
        else:
            logger.error(f"Monitor summary check failed: {summary_response.status_code}")
    except Exception as e:
        logger.warning(f"Error in monitor summary check: {e}")
    
    logger.info("WebRTC tests completed")
    return True

def main():
    """
    Main function to parse arguments and run the server.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run MCP Server with WebRTC AnyIO & Monitoring Integration")
    parser.add_argument("--port", type=int, default=9999, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--log-dir", type=str, default="./logs", help="Directory to store WebRTC logs")
    parser.add_argument("--isolation", action="store_true", help="Run with isolated IPFS repository")
    parser.add_argument("--webrtc-test", action="store_true", help="Include WebRTC test endpoint")
    parser.add_argument("--run-tests", action="store_true", help="Run WebRTC tests after starting server")
    
    args = parser.parse_args()
    
    # Check requirements
    if not HAS_FASTAPI:
        logger.error("FastAPI is required. Install with: pip install fastapi uvicorn")
        return 1
        
    if not HAS_ANYIO:
        logger.error("AnyIO is required. Install with: pip install anyio sniffio")
        return 1
        
    if not HAS_INTEGRATION:
        logger.error("WebRTC AnyIO & Monitoring Integration module is required")
        return 1
    
    # Create log directory if it doesn't exist
    if not os.path.exists(args.log_dir):
        os.makedirs(args.log_dir, exist_ok=True)
    
    # Create MCP server
    logger.info(f"Creating MCP server (debug={args.debug}, isolation={args.isolation})")
    mcp_server = create_mcp_server(
        debug_mode=args.debug,
        isolation_mode=args.isolation,
        log_dir=args.log_dir,
        include_test_endpoint=args.webrtc_test
    )
    
    if not mcp_server:
        logger.error("Failed to create MCP server")
        return 1
    
    # Create FastAPI app
    from fastapi import FastAPI
    
    app = FastAPI(
        title="MCP Server with WebRTC AnyIO & Monitoring",
        debug=args.debug
    )
    
    # Register MCP routes with FastAPI
    mcp_server.register_with_app(app)
    
    # Run tests in a separate thread if requested
    if args.run_tests:
        def run_tests_thread():
            run_webrtc_tests(args.host, args.port)
        
        threading.Thread(target=run_tests_thread, daemon=True).start()
    
    # Run the server
    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
MCP Server Runner with WebRTC Dashboard Integration

This script runs an MCP server with WebRTC enabled and includes a comprehensive
monitoring dashboard for visualizing and controlling WebRTC connections.

The dashboard provides:
- Real-time monitoring of WebRTC connections
- Connection management (start/stop/test)
- Operation history and logging
- Task tracking with status updates

This implementation leverages the AnyIO-based event loop handling to properly
work in FastAPI's asynchronous environment.
"""

import os
import sys
import time
import logging
import argparse
import importlib
import asyncio
import multiprocessing
import webbrowser
from typing import Dict, List, Optional, Any
import uvicorn
from fastapi import FastAPI

# Add parent directory to path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Constants
DEFAULT_PORT = 8000
DEFAULT_HOST = "127.0.0.1"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("webrtc_dashboard")

# Global WebRTC monitor reference
webrtc_monitor = None


def check_webrtc_availability() -> bool:
    """Check if WebRTC dependencies are available.
    
    Returns:
        True if WebRTC is available, False otherwise
    """
    # Check for aiortc
    try:
        import aiortc
        return True
    except ImportError:
        logger.warning("aiortc not found, WebRTC streaming will not be available")
        return False


def force_webrtc_availability():
    """Force WebRTC to be available by creating minimal mock implementations."""
    import types
    
    if check_webrtc_availability():
        return
        
    logger.info("Creating mock WebRTC implementations for testing")
    
    # Create mock aiortc module
    mock_aiortc = types.ModuleType("aiortc")
    mock_aiortc.RTCPeerConnection = type("RTCPeerConnection", (), {
        "__init__": lambda self, **kwargs: None,
        "createOffer": lambda self: asyncio.Future(),
        "createAnswer": lambda self: asyncio.Future(),
        "close": lambda self: None,
    })
    sys.modules["aiortc"] = mock_aiortc
    
    # Create mock av module
    mock_av = types.ModuleType("av")
    mock_av.VideoFrame = type("VideoFrame", (), {})
    sys.modules["av"] = mock_av


def load_webrtc_monitor():
    """Load WebRTC monitor if available.
    
    Returns:
        WebRTC monitor instance or None if not available
    """
    global webrtc_monitor
    
    try:
        from fixes.webrtc_monitor import WebRTCMonitor
        from fixes.webrtc_anyio_fix import AnyIOEventLoopHandler
        
        # Create WebRTC monitor instance
        webrtc_monitor = WebRTCMonitor()
        
        # Create event loop handler
        loop_handler = AnyIOEventLoopHandler()
        
        # Apply fixes if available
        try:
            from fixes.webrtc_anyio_monitor_integration import apply_enhanced_fixes
            logger.info("Applying enhanced WebRTC fixes with monitoring integration")
            apply_enhanced_fixes(webrtc_monitor, loop_handler)
        except ImportError:
            logger.info("Enhanced fixes not available, using basic monitor")
            
        return webrtc_monitor
        
    except ImportError as e:
        logger.warning(f"WebRTC monitor not available: {e}")
        return None


def create_mcp_server(
    debug_mode=False, 
    isolation_mode=False,
    log_level="INFO",
    webrtc_model=None
):
    """Create an MCP server instance with WebRTC dashboard integration.
    
    Args:
        debug_mode: Enable debug mode for the MCP server
        isolation_mode: Run the server with isolated settings
        log_level: Logging level for the server
        webrtc_model: Optional pre-configured WebRTC model
        
    Returns:
        Tuple of (FastAPI app, MCP server instance)
    """
    try:
        # Import MCP server and related modules
        from ipfs_kit_py.mcp.server import MCPServer
        
        # Set up logging level
        level = getattr(logging, log_level.upper())
        logging.basicConfig(level=level)
        
        # Load WebRTC monitor
        monitor = load_webrtc_monitor()
        
        # Create MCP server
        logger.info("Creating MCP server")
        mcp_server = MCPServer(
            debug_mode=debug_mode,
            log_level=log_level,
            isolation_mode=isolation_mode
        )
        
        # Create FastAPI app
        app = FastAPI(title="MCP Server with WebRTC Dashboard")
        
        # Register MCP server with app
        prefix = "/api/v0"
        router = mcp_server.get_router()
        app.include_router(router, prefix=prefix)
        
        # Register WebRTC dashboard controller
        try:
            from ipfs_kit_py.mcp.controllers.webrtc_dashboard_controller import create_webrtc_dashboard_router
            from ipfs_kit_py.mcp.controllers.webrtc_video_controller import create_webrtc_video_player_router
            
            # Get WebRTC model (either provided or from MCP server)
            if not webrtc_model and hasattr(mcp_server, "models") and "ipfs" in mcp_server.models:
                webrtc_model = mcp_server.models["ipfs"]
            
            # Create dashboard router
            dashboard_router = create_webrtc_dashboard_router(
                webrtc_model=webrtc_model, 
                webrtc_monitor=monitor
            )
            
            # Add dashboard router to app
            app.include_router(dashboard_router)
            
            # Create video player router
            video_player_router = create_webrtc_video_player_router(
                webrtc_model=webrtc_model
            )
            
            # Add video player router to app (same prefix as dashboard)
            app.include_router(video_player_router)
            
            # Add root redirect to dashboard
            @app.get("/")
            async def redirect_to_dashboard():
                from fastapi.responses import RedirectResponse
                return RedirectResponse("/api/v0/webrtc/dashboard")
            
            logger.info("WebRTC dashboard and video player registered successfully")
        except ImportError as e:
            logger.warning(f"Failed to register WebRTC dashboard: {e}")
        
        return app, mcp_server
        
    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        raise


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, debug: bool = False, 
               isolation: bool = False, open_browser: bool = False):
    """Run the MCP server with WebRTC dashboard.
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        debug: Enable debug mode
        isolation: Run with isolated settings
        open_browser: Open browser automatically when server starts
    """
    # Create MCP server and FastAPI app
    app, mcp_server = create_mcp_server(
        debug_mode=debug,
        isolation_mode=isolation
    )
    
    # Configure ASGI server
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info" if not debug else "debug",
        reload=debug
    )
    
    # Create server
    server = uvicorn.Server(config)
    
    # Open browser if requested
    if open_browser:
        # Delay browser opening slightly to ensure server is ready
        def _open_browser():
            time.sleep(1.0)
            url = f"http://{host}:{port}/"
            logger.info(f"Opening dashboard in browser: {url}")
            webbrowser.open(url)
            
        # Start browser in separate process to avoid blocking
        browser_process = multiprocessing.Process(target=_open_browser)
        browser_process.daemon = True
        browser_process.start()
    
    # Run server
    logger.info(f"Starting MCP server with WebRTC dashboard on http://{host}:{port}")
    server.run()


def run_test_client(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Run a test client that simulates WebRTC connections.
    
    Args:
        host: Host where the server is running
        port: Port where the server is running
    """
    import random
    import requests
    import json
    import time
    
    # Base URL for API
    base_url = f"http://{host}:{port}/api/v0/webrtc"
    
    # Test CIDs
    test_cids = [
        "QmTestContent1",
        "QmTestContent2",
        "QmTestContent3",
        "QmReallyLongTestContentIdentifierWithLotsOfCharacters"
    ]
    
    # Start test connections
    connections = []
    
    try:
        logger.info("Starting test client")
        
        # Create some test connections
        for i in range(3):
            try:
                # Random CID from test list
                cid = random.choice(test_cids)
                
                # Random quality
                quality = random.randint(10, 100)
                
                # Start stream
                logger.info(f"Creating test connection {i+1} with CID {cid}")
                response = requests.post(
                    f"{base_url}/stream",
                    json={"cid": cid, "quality": quality}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        conn_id = result.get("connection_id")
                        connections.append(conn_id)
                        logger.info(f"Created connection: {conn_id}")
                    else:
                        logger.error(f"Failed to create connection: {result.get('error')}")
                else:
                    logger.error(f"HTTP error: {response.status_code}")
                
                # Wait a bit between connections
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error creating test connection: {e}")
        
        # Let connections run for a bit
        logger.info("Test connections running, press Ctrl+C to stop")
        
        # Simulate operations
        iteration = 0
        while True:
            iteration += 1
            try:
                if connections and iteration % 5 == 0:
                    # Every 5 iterations, modify a random connection
                    conn_id = random.choice(connections)
                    action = random.choice(["close", "quality"])
                    
                    if action == "close" and connections:
                        # Close a random connection
                        logger.info(f"Closing connection {conn_id}")
                        response = requests.post(f"{base_url}/close/{conn_id}")
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("success"):
                                connections.remove(conn_id)
                                logger.info(f"Closed connection: {conn_id}")
                            else:
                                logger.error(f"Failed to close connection: {result.get('error')}")
                    
                    elif action == "quality":
                        # Change quality of a random connection
                        quality = random.randint(10, 100)
                        logger.info(f"Setting quality to {quality} for connection {conn_id}")
                        response = requests.post(
                            f"{base_url}/quality/{conn_id}",
                            json={"quality": quality}
                        )
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("success"):
                                logger.info(f"Quality set for connection: {conn_id}")
                            else:
                                logger.error(f"Failed to set quality: {result.get('error')}")
                
                # Occasionally add a new connection
                if iteration % 10 == 0:
                    cid = random.choice(test_cids)
                    quality = random.randint(10, 100)
                    logger.info(f"Creating new test connection with CID {cid}")
                    response = requests.post(
                        f"{base_url}/stream",
                        json={"cid": cid, "quality": quality}
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            conn_id = result.get("connection_id")
                            connections.append(conn_id)
                            logger.info(f"Created connection: {conn_id}")
                
                # Sleep between iterations
                time.sleep(2)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in test client: {e}")
                time.sleep(5)  # Wait a bit longer on error
    
    finally:
        # Clean up connections
        logger.info("Cleaning up test connections")
        for conn_id in connections:
            try:
                requests.post(f"{base_url}/close/{conn_id}")
            except Exception:
                pass
        
        logger.info("Test client finished")


def main():
    """Main entry point for the script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run MCP Server with WebRTC Dashboard")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind server to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--isolation", action="store_true", help="Run with isolated settings")
    parser.add_argument("--open-browser", action="store_true", help="Open browser automatically")
    parser.add_argument("--test-client", action="store_true", help="Run a test client")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Set the logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check WebRTC availability
    webrtc_available = check_webrtc_availability()
    logger.info(f"WebRTC availability: {'Yes' if webrtc_available else 'No'}")
    
    if args.test_client:
        # Run test client
        run_test_client(host=args.host, port=args.port)
    else:
        # Run server
        run_server(
            host=args.host,
            port=args.port,
            debug=args.debug,
            isolation=args.isolation,
            open_browser=args.open_browser
        )


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Run MCP AnyIO server with WebRTC integration.

This script runs the AnyIO-based MCP server with WebRTC support,
using AnyIO primitives for proper event loop handling across
both asyncio and trio backends.
"""

import os
import sys
import time
import argparse
import logging
import signal
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mcp_webrtc_anyio.log")
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run MCP AnyIO server with WebRTC integration")
    
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--port", type=int, default=9999, help="Port for the MCP server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server to")
    parser.add_argument("--isolation", action="store_true", help="Run in isolation mode")
    parser.add_argument("--log-level", type=str, default="INFO", 
                      choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                      help="Logging level")
    parser.add_argument("--persistence-path", type=str, help="Path for MCP server persistence files")
    parser.add_argument("--run-tests", action="store_true", help="Run WebRTC tests after starting server")
    parser.add_argument("--backend", type=str, default="asyncio", 
                      choices=["asyncio", "trio"],
                      help="AnyIO backend to use (asyncio or trio)")
    
    return parser.parse_args()

def kill_stale_server(server_pid_file="server.pid"):
    """Kill any stale server processes."""
    if os.path.exists(server_pid_file):
        try:
            with open(server_pid_file, "r") as f:
                pid = int(f.read().strip())
                
            # Check if process is still running
            try:
                os.kill(pid, 0)  # Send signal 0 to check process existence
                logger.warning(f"Found stale server process (PID {pid}), terminating...")
                
                # Send SIGTERM and wait for graceful shutdown
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
                
                # Check if it's still running and force kill if needed
                try:
                    os.kill(pid, 0)
                    logger.warning(f"Process {pid} still running, sending SIGKILL...")
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    # Process already terminated
                    pass
                    
            except OSError:
                # Process not running
                pass
                
        except Exception as e:
            logger.error(f"Error killing stale server: {e}")
            
        # Remove stale PID file
        os.remove(server_pid_file)

def save_pid(pid_file="server.pid"):
    """Save the current process ID to a file."""
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"Saved PID {os.getpid()} to {pid_file}")

def signal_handler(sig, frame):
    """Handle signals for graceful shutdown."""
    logger.info(f"Received signal {sig}, shutting down...")
    # Clean up PID file
    if os.path.exists("server.pid"):
        os.remove("server.pid")
    # Exit gracefully
    sys.exit(0)

def run_server_with_anyio(args):
    """Run the MCP AnyIO server with WebRTC integration."""
    try:
        # First, kill any stale server processes
        kill_stale_server()
        
        # Save current PID
        save_pid()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Import necessary modules
        logger.info("Importing MCP AnyIO server modules...")
        
        # Apply WebRTC fixes before creating the server
        logger.info("Applying WebRTC AnyIO integration...")
        try:
            from fixes.webrtc_anyio_monitor_integration import apply_webrtc_anyio_fixes
            apply_webrtc_anyio_fixes()
            logger.info("Applied WebRTC AnyIO integration successfully")
        except Exception as e:
            logger.error(f"Error applying WebRTC AnyIO integration: {e}")
            # Continue anyway as we might not need this fix
        
        # Import and create the MCP AnyIO server
        try:
            from ipfs_kit_py.mcp.server_anyio import MCPServerAnyIO
            from fastapi import FastAPI
            import uvicorn
            import anyio
            
            # Try to import sniffio to detect current async library
            try:
                import sniffio
                has_sniffio = True
            except ImportError:
                has_sniffio = False
                
            logger.info(f"Creating MCP AnyIO server (debug={args.debug}, isolation={args.isolation}, backend={args.backend})...")
            mcp_server = MCPServerAnyIO(
                debug_mode=args.debug,
                log_level=args.log_level,
                persistence_path=args.persistence_path,
                isolation_mode=args.isolation,
                async_backend=args.backend
            )
            
            # Create FastAPI app
            app = FastAPI(title="IPFS Kit MCP AnyIO Server with WebRTC")
            
            # Register MCP server with app
            mcp_server.register_with_app(app, prefix="/api")
            
            # Add a root endpoint for easy testing
            @app.get("/")
            async def read_root():
                # Detect current async library for info
                current_backend = None
                if has_sniffio:
                    try:
                        current_backend = sniffio.current_async_library()
                    except sniffio.AsyncLibraryNotFoundError:
                        current_backend = "none"
                
                return {
                    "name": "IPFS Kit MCP AnyIO Server",
                    "version": "0.3.0",
                    "status": "running",
                    "webrtc_enabled": True,
                    "async_backend": args.backend,
                    "detected_backend": current_backend,
                    "anyio_integration": True
                }
            
            # Run WebRTC tests if requested (in background)
            if args.run_tests:
                logger.info("Starting WebRTC tests in background...")
                test_cmd = [
                    sys.executable, "-m", "test.test_webrtc_streaming_anyio",
                    f"--server-url=http://{args.host}:{args.port}"
                ]
                subprocess.Popen(
                    test_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # Start the server with the specified backend
            # Note: When using trio backend with uvicorn, it still uses asyncio internally
            # but our application code will use trio through AnyIO
            logger.info(f"Starting server on {args.host}:{args.port} with {args.backend} backend...")
            uvicorn.run(app, host=args.host, port=args.port)
            
            return True
            
        except ImportError as e:
            logger.error(f"Failed to import required modules: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error running server: {e}")
        return False

def main():
    """Main entry point."""
    args = parse_args()
    
    # Configure log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Run the server
    success = run_server_with_anyio(args)
    
    if success:
        sys.exit(0)
    else:
        logger.error("Server failed to start properly")
        sys.exit(1)

if __name__ == "__main__":
    main()
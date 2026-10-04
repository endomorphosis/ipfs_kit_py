#!/usr/bin/env python3
"""
Simplified MCP Server for Testing

This is a minimal version to test if the server can start without hanging.
"""

import os
import sys
import json
import logging
import signal
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simple_mcp_server.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("simple-mcp")

# Import FastAPI
try:
    import uvicorn
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    logger.info("✅ FastAPI imports successful")
except ImportError as e:
    logger.error(f"❌ Failed to import FastAPI components: {e}")
    sys.exit(1)

# Import JSON-RPC
try:
    import jsonrpcserver
    from jsonrpcserver import dispatch, Success, Error
    from jsonrpcserver import method as jsonrpc_method
    logger.info("✅ JSON-RPC imports successful")
except ImportError as e:
    logger.error(f"❌ Failed to import JSON-RPC components: {e}")
    sys.exit(1)

# Global state
PORT = 9998
registered_tools = {}

# Create FastAPI app
app = FastAPI(
    title="Simple MCP Server",
    description="A simplified MCP server for testing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "Simple MCP Server is running",
        "tools_count": len(registered_tools)
    }

# Ping method for JSON-RPC
@jsonrpc_method
def ping():
    """Simple ping method."""
    return "pong"

# JSON-RPC endpoint
@app.post("/jsonrpc")
async def jsonrpc_endpoint(request: Request):
    """Handle JSON-RPC requests."""
    try:
        # Get request body
        body = await request.json()
        
        # Dispatch the request
        response = dispatch(body)
        
        return JSONResponse(content=response)
    except Exception as e:
        logger.error(f"JSON-RPC error: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

# Signal handlers
def handle_sigterm(signum, frame):
    logger.info("Received SIGTERM, shutting down gracefully...")
    sys.exit(0)

def handle_sigint(signum, frame):
    logger.info("Received SIGINT, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main function."""
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(description="Simple MCP Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port (default: {PORT})")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Check if port is already in use
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((args.host, args.port))
        s.close()
    except socket.error as e:
        if e.errno == 98:  # Address already in use
            logger.error(f"Port {args.port} is already in use. Please use a different port.")
            sys.exit(1)
        else:
            logger.error(f"Socket error: {e}")
            sys.exit(1)

    # Create PID file
    pid_file = Path("simple_mcp_server.pid")
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
        logger.info(f"Starting simple server on {args.host}:{args.port}, debug={args.debug}, PID: {os.getpid()}")

        # Start the server
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info",
            timeout_keep_alive=30,
            timeout_graceful_shutdown=10
        )
    finally:
        try:
            if pid_file.exists():
                pid_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
        logger.info("Server shutdown complete.")

if __name__ == "__main__":
    main()

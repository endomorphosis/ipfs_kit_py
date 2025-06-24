#!/usr/bin/env python3
"""
Add MCP Initialize Endpoint for VS Code Integration

This script creates a simple standalone server with the initialize endpoint
required for VS Code to connect to an MCP server.
"""

import os
import sys
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MCP Initialize Endpoint",
    description="Provides the initialize endpoint for VS Code MCP integration",
    version="1.0.0"
)

# Add CORS middleware to allow VS Code to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint providing server information."""
    return {
        "name": "MCP Initialize Endpoint Server",
        "version": "1.0.0",
        "description": "Provides the VS Code MCP initialize endpoint",
        "endpoints": ["/", "/api/v0/initialize", "/api/v0/health"]
    }

@app.get("/api/v0/health")
@app.post("/api/v0/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": __import__("time").time()
    }

@app.get("/api/v0/initialize")
@app.post("/api/v0/initialize")
async def initialize():
    """
    Initialize endpoint for VS Code MCP protocol.

    This endpoint is called by VS Code when it first connects to the MCP server.
    It returns information about the server's capabilities.
    """
    logger.info("Received initialize request from VS Code")
    return {
        "capabilities": {
            "tools": ["ipfs_add", "ipfs_cat", "ipfs_pin", "storage_transfer"],
            "resources": ["ipfs://info", "storage://backends"]
        },
        "serverInfo": {
            "name": "IPFS Kit MCP Server",
            "version": "1.0.0",
            "implementationName": "ipfs-kit-py"
        }
    }

@app.get("/api/v0/jsonrpc")
@app.post("/api/v0/jsonrpc")
async def jsonrpc():
    """
    JSON-RPC endpoint for VS Code MCP protocol.

    This endpoint is called by VS Code for JSON-RPC communication.
    """
    return {"jsonrpc": "2.0", "result": "ok", "id": 1}

def main():
    """Main function to run the server."""
    # Read port from command line if provided, otherwise use default
    port = 9994
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    logger.info(f"Starting MCP Initialize Endpoint server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()

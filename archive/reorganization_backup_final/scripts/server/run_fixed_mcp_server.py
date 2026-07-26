#!/usr/bin/env python3
"""
Run MCP server with all fixes applied.
"""
import sys
import logging
import uvicorn
import anyio
from fastapi import FastAPI
from ipfs_kit_py.mcp.server_anyio import MCPServer

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("run_fixed_mcp_server")

# Create FastAPI app
app = FastAPI(
    title="Fixed MCP Server",
    description="Model-Controller-Persistence Server for IPFS Kit",
    version="1.0.0"
)

# Root endpoint
@app.get("/")
def read_root():
    """Root endpoint for the server."""
    import time
    return {
        "name": "IPFS Kit MCP Server",
        "version": "1.0.0",
        "description": "Fixed API server for IPFS Kit operations",
        "timestamp": time.time(),
        "endpoints": ["/", "/health", "/docs", "/api/v0/mcp/"]
    }

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    import time
    return {
        "status": "ok",
        "timestamp": time.time()
    }

# Create MCP server with debug mode
mcp_server = MCPServer(debug_mode=True)

# Register MCP server with FastAPI app
mcp_server.register_with_app(app, prefix="/mcp")

# Also register at /api/v0/mcp for test compatibility
mcp_server.register_with_app(app, prefix="/api/v0/mcp")

if __name__ == "__main__":
    logger.info("Starting fixed MCP server on port 9991")
    uvicorn.run(app, host="127.0.0.1", port=9991)

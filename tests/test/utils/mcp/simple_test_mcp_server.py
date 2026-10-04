"""
Simplified test server for MCP API testing.
This script creates a minimal FastAPI server with just the health endpoint and basic IPFS operations.
"""

import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Query, Path, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional, Union
import time
import os
import sys
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Simple MCP Test Server")

# Define the API prefix to match the test script's expectations
api_prefix = "/api/v0"

# Health endpoint - the most important one for initial test
@app.get(f"{api_prefix}/health")
async def health():
    """Health check endpoint."""
    return {
        "success": True,
        "healthy": True,
        "timestamp": time.time(),
        "message": "MCP Test Server is healthy"
    }

# Daemon status endpoint
@app.get(f"{api_prefix}/daemon/status")
async def daemon_status():
    """Daemon status endpoint."""
    return {
        "success": True,
        "daemon_status": {
            "ipfs": {"running": True},
            "ipfs_cluster_service": {"running": False}
        },
        "timestamp": time.time()
    }

# Basic IPFS operations for testing
@app.post(f"{api_prefix}/ipfs/add")
async def ipfs_add(file: UploadFile = File(...)):
    """Add file to IPFS."""
    # Simply return a simulated CID
    return {
        "success": True,
        "cid": "QmSimulatedCid123456789",
        "size": 1024,
        "timestamp": time.time(),
        "simulated": True
    }

@app.post(f"{api_prefix}/ipfs/add_string")
async def ipfs_add_string(request_data: dict = Body(...)):
    """Add string content to IPFS."""
    return {
        "success": True,
        "cid": "QmSimulatedStringCid123456789",
        "size": len(request_data.get("content", "")),
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/cat/{{cid}}")
async def ipfs_cat(cid: str):
    """Retrieve content from IPFS by CID."""
    return f"Simulated content for {cid}"

@app.post(f"{api_prefix}/ipfs/pin")
async def ipfs_pin(request_data: dict = Body(...)):
    """Pin content to IPFS."""
    return {
        "success": True,
        "cid": request_data.get("cid", ""),
        "pinned": True,
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/pins")
async def ipfs_pins():
    """List pinned content in IPFS."""
    return {
        "success": True,
        "pins": ["QmSimulatedCid123456789"],
        "timestamp": time.time(),
        "simulated": True
    }

@app.post(f"{api_prefix}/ipfs/unpin")
async def ipfs_unpin(request_data: dict = Body(...)):
    """Unpin content from IPFS."""
    return {
        "success": True,
        "cid": request_data.get("cid", ""),
        "unpinned": True,
        "timestamp": time.time(),
        "simulated": True
    }

# Files API (MFS) endpoints
@app.post(f"{api_prefix}/ipfs/files/mkdir")
async def ipfs_files_mkdir(request_data: dict = Body(...)):
    """Create directory in MFS."""
    return {
        "success": True,
        "path": request_data.get("path", ""),
        "created": True,
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/files/ls")
async def ipfs_files_ls(path: str = "/", long: str = "false"):
    """List files in MFS."""
    return {
        "success": True,
        "entries": [
            {"name": "test-dir", "type": "directory", "size": 0}
        ],
        "path": path,
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/files/stat")
async def ipfs_files_stat(path: str):
    """Get file stats in MFS."""
    return {
        "success": True,
        "path": path,
        "size": 0,
        "type": "directory",
        "blocks": 0,
        "timestamp": time.time(),
        "simulated": True
    }

# IPNS endpoints
@app.post(f"{api_prefix}/ipfs/name/publish")
async def ipfs_name_publish(request_data: dict = Body(...)):
    """Publish IPNS name."""
    return {
        "success": True,
        "Name": "k51qzi5uqu5dkkuju2tz5qxr1oi3xpbtot9zknkjz30xkpc7zos7u3j4816kxm",
        "Value": request_data.get("path", ""),
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/name/resolve")
async def ipfs_name_resolve(name: str):
    """Resolve IPNS name."""
    return {
        "success": True,
        "Path": "/ipfs/QmSimulatedCid123456789",
        "timestamp": time.time(),
        "simulated": True
    }

# DAG endpoints
@app.post(f"{api_prefix}/ipfs/dag/put")
async def ipfs_dag_put(request_data: dict = Body(...)):
    """Put DAG node."""
    return {
        "success": True,
        "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/dag/get")
async def ipfs_dag_get(cid: str):
    """Get DAG node."""
    return {
        "success": True,
        "data": "test data",
        "links": [],
        "timestamp": time.time(),
        "simulated": True
    }

# Block endpoints
@app.post(f"{api_prefix}/ipfs/block/put")
async def ipfs_block_put(request_data: dict = Body(...)):
    """Put IPFS block."""
    return {
        "success": True,
        "cid": "QmSimulatedBlockCid123456789",
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/block/stat")
async def ipfs_block_stat(cid: str):
    """Get IPFS block stats."""
    return {
        "success": True,
        "Key": cid,
        "Size": 1024,
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/block/get/{{cid}}")
async def ipfs_block_get(cid: str):
    """Get IPFS block."""
    return PlainTextResponse(f"Simulated block data for {cid}")

# DHT endpoints
@app.get(f"{api_prefix}/ipfs/dht/findprovs")
async def ipfs_dht_findprovs(cid: str):
    """Find providers for CID."""
    return {
        "success": True,
        "providers": [],
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/ipfs/dht/findpeer")
async def ipfs_dht_findpeer(peer_id: str):
    """Find peer by ID."""
    return {
        "success": True,
        "addresses": [],
        "timestamp": time.time(),
        "simulated": True
    }

# Controller endpoints
@app.get(f"{api_prefix}/cli/version")
async def cli_version():
    """Get CLI version."""
    return {
        "success": True,
        "version": "0.1.0",
        "timestamp": time.time(),
        "simulated": True
    }

@app.post(f"{api_prefix}/cli/command")
async def cli_command(request_data: dict = Body(...)):
    """Execute CLI command."""
    return {
        "success": True,
        "output": "Simulated command output",
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/credentials/list")
async def credentials_list():
    """List credentials."""
    return {
        "success": True,
        "credentials": [],
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/distributed/status")
async def distributed_status():
    """Get distributed status."""
    return {
        "success": True,
        "status": "idle",
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/webrtc/capabilities")
async def webrtc_capabilities():
    """Get WebRTC capabilities."""
    return {
        "success": True,
        "webrtc_available": False,
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/fs_journal/status")
async def fs_journal_status():
    """Get filesystem journal status."""
    return {
        "success": True,
        "enabled": False,
        "timestamp": time.time(),
        "simulated": True
    }

@app.get(f"{api_prefix}/debug")
async def debug():
    """Get debug state."""
    return {
        "success": True,
        "operations": [],
        "count": 0,
        "timestamp": time.time()
    }

@app.get(f"{api_prefix}/operations")
async def operations():
    """Get operation log."""
    return {
        "success": True,
        "operations": [],
        "count": 0,
        "timestamp": time.time()
    }

# Root endpoint for basic info
@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "message": "Simple MCP Test Server is running",
        "api_prefix": api_prefix,
        "endpoints": [
            f"{api_prefix}/health",
            f"{api_prefix}/daemon/status",
            f"{api_prefix}/ipfs/add",
            f"{api_prefix}/ipfs/add_string",
            f"{api_prefix}/ipfs/cat/{{cid}}",
            f"{api_prefix}/ipfs/pin",
            f"{api_prefix}/ipfs/pins",
            f"{api_prefix}/ipfs/unpin",
            f"{api_prefix}/ipfs/files/mkdir",
            f"{api_prefix}/ipfs/files/ls",
            f"{api_prefix}/ipfs/files/stat",
            f"{api_prefix}/ipfs/name/publish",
            f"{api_prefix}/ipfs/name/resolve",
            f"{api_prefix}/ipfs/dag/put",
            f"{api_prefix}/ipfs/dag/get",
            f"{api_prefix}/ipfs/block/put",
            f"{api_prefix}/ipfs/block/stat",
            f"{api_prefix}/ipfs/block/get/{{cid}}",
            f"{api_prefix}/ipfs/dht/findprovs",
            f"{api_prefix}/ipfs/dht/findpeer",
            f"{api_prefix}/cli/version",
            f"{api_prefix}/cli/command",
            f"{api_prefix}/credentials/list",
            f"{api_prefix}/distributed/status",
            f"{api_prefix}/webrtc/capabilities",
            f"{api_prefix}/fs_journal/status",
            f"{api_prefix}/debug",
            f"{api_prefix}/operations"
        ]
    }

# Function to verify route registration
def test_routes():
    """Test that all routes are properly registered."""
    print("\n=== Registered Routes ===")
    for route in app.routes:
        print(f"Path: {route.path}, Methods: {route.methods}")

# Run the server
if __name__ == "__main__":
    # Test route registration if requested
    if "--test-routes" in sys.argv:
        test_routes()
        sys.exit(0)
    
    port = int(os.environ.get("PORT", 8000))
    # Use 0.0.0.0 to listen on all interfaces (localhost, 127.0.0.1, etc.)
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"Starting simple MCP test server at {host}:{port}")
    print(f"Health endpoint at: http://localhost:{port}{api_prefix}/health")
    print(f"Health endpoint at: http://127.0.0.1:{port}{api_prefix}/health")
    uvicorn.run(app, host=host, port=port)
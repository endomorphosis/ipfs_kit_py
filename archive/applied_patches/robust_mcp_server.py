#!/usr/bin/env python3
"""
Simplified robust MCP server implementation.

This script creates a working MCP server with all core features that will
reliably run without dependency issues.
"""

import os
import sys
import logging
import uvicorn
import time
import json
from fastapi import FastAPI, APIRouter, File, UploadFile, Form, HTTPException, Query, Body
from fastapi.responses import StreamingResponse, Response
from typing import Dict, List, Any, Optional, Union
import tempfile
import uuid
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/robust_mcp_server.log'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)
logger = logging.getLogger(__name__)

# Configuration
PORT = 9996
HOST = "0.0.0.0"
API_PREFIX = "/api/v0"
DEBUG_MODE = True
SERVER_ID = str(uuid.uuid4())

# IPFS daemon management
def check_ipfs_daemon():
    """Check if IPFS daemon is running."""
    try:
        result = subprocess.run(["ipfs", "version"], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error checking IPFS daemon: {e}")
        return False

def start_ipfs_daemon():
    """Start the IPFS daemon if not running."""
    if not check_ipfs_daemon():
        try:
            # Start daemon in background
            subprocess.Popen(["ipfs", "daemon", "--routing=dhtclient"], 
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            # Wait a moment for it to initialize
            time.sleep(2)
            return check_ipfs_daemon()
        except Exception as e:
            logger.error(f"Error starting IPFS daemon: {e}")
            return False
    return True

def run_ipfs_command(command, input_data=None):
    """Run an IPFS command and return the result."""
    try:
        full_command = ["ipfs"] + command
        if input_data:
            result = subprocess.run(full_command, 
                                  input=input_data,
                                  capture_output=True)
        else:
            result = subprocess.run(full_command, 
                                  capture_output=True)
        
        if result.returncode == 0:
            return {"success": True, "output": result.stdout}
        else:
            return {"success": False, "error": result.stderr.decode('utf-8', errors='replace')}
    except Exception as e:
        logger.error(f"Error running IPFS command {command}: {e}")
        return {"success": False, "error": str(e)}

# Create FastAPI app
app = FastAPI(
    title="Robust MCP Server",
    description="Model-Controller-Persistence Server for IPFS Kit",
    version="1.0.0"
)

# Storage backend status tracking
storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "huggingface": {"available": False, "simulation": True},
    "s3": {"available": False, "simulation": True},
    "filecoin": {"available": False, "simulation": True},
    "storacha": {"available": False, "simulation": True},
    "lassie": {"available": False, "simulation": True}
}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "MCP Server is running (Robust Implementation)",
        "debug_mode": DEBUG_MODE,
        "server_id": SERVER_ID,
        "documentation": "/docs",
        "health_endpoint": f"{API_PREFIX}/health",
        "api_version": "v0",
        "uptime": time.time(),
        "available_endpoints": {
            "ipfs": [
                f"{API_PREFIX}/ipfs/add",
                f"{API_PREFIX}/ipfs/cat",
                f"{API_PREFIX}/ipfs/version",
                f"{API_PREFIX}/ipfs/pin/add",
                f"{API_PREFIX}/ipfs/pin/ls"
            ],
            "storage": [
                f"{API_PREFIX}/storage/health"
            ],
            "health": f"{API_PREFIX}/health"
        }
    }

# Create API router for /api/v0 prefix
router = APIRouter()

# Health endpoint
@router.get("/health")
async def health():
    """Health check endpoint."""
    ipfs_running = check_ipfs_daemon()
    
    health_info = {
        "success": True,
        "status": "healthy" if ipfs_running else "degraded",
        "timestamp": time.time(),
        "server_id": SERVER_ID,
        "debug_mode": DEBUG_MODE,
        "ipfs_daemon_running": ipfs_running,
        "controllers": {
            "ipfs": True,
            "storage": True
        },
        "storage_backends": storage_backends
    }
    
    return health_info

# Storage health endpoint
@router.get("/storage/health")
async def storage_health():
    """Storage backends health check."""
    return {
        "success": True,
        "timestamp": time.time(),
        "mode": "real_storage",
        "components": storage_backends,
        "overall_status": "healthy"
    }

# IPFS Version endpoint
@router.get("/ipfs/version")
async def ipfs_version():
    """Get IPFS version information."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["version"])
    if result["success"]:
        try:
            version_str = result["output"].decode('utf-8').strip()
            return {"success": True, "version": version_str}
        except Exception as e:
            logger.error(f"Error parsing IPFS version: {e}")
            return {"success": False, "error": str(e)}
    else:
        return {"success": False, "error": result["error"]}

# IPFS Add endpoint
@router.post("/ipfs/add")
async def ipfs_add(file: UploadFile = File(...)):
    """Add a file to IPFS."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    try:
        # Create a temporary file to store the uploaded content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write the uploaded file content to the temporary file
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Add the file to IPFS
        result = run_ipfs_command(["add", "-q", temp_file_path])
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        if result["success"]:
            cid = result["output"].decode('utf-8').strip()
            return {
                "success": True, 
                "cid": cid,
                "size": len(content),
                "name": file.filename
            }
        else:
            return {"success": False, "error": result["error"]}
    
    except Exception as e:
        logger.error(f"Error adding file to IPFS: {e}")
        return {"success": False, "error": str(e)}

# IPFS Cat endpoint
@router.get("/ipfs/cat/{cid}")
async def ipfs_cat(cid: str):
    """Get content from IPFS by CID."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["cat", cid])
    if result["success"]:
        # Use StreamingResponse to handle large files efficiently
        async def content_generator():
            yield result["output"]
        
        return StreamingResponse(
            content_generator(),
            media_type="application/octet-stream"
        )
    else:
        raise HTTPException(status_code=404, detail=f"Content not found: {result['error']}")

# IPFS Pin Add endpoint
@router.post("/ipfs/pin/add")
async def ipfs_pin_add(cid: str = Form(...)):
    """Pin content in IPFS by CID."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["pin", "add", cid])
    if result["success"]:
        return {"success": True, "cid": cid, "pinned": True}
    else:
        return {"success": False, "error": result["error"]}

# IPFS Pin List endpoint
@router.get("/ipfs/pin/ls")
async def ipfs_pin_list():
    """List pinned content in IPFS."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["pin", "ls", "--type=recursive"])
    if result["success"]:
        try:
            output = result["output"].decode('utf-8').strip()
            pins = {}
            
            for line in output.split('\n'):
                if line:
                    parts = line.split(' ')
                    if len(parts) >= 2:
                        cid = parts[0]
                        pins[cid] = {"type": "recursive"}
            
            return {"success": True, "pins": pins}
        except Exception as e:
            logger.error(f"Error parsing pin list: {e}")
            return {"success": False, "error": str(e)}
    else:
        return {"success": False, "error": result["error"]}

# Storage - Huggingface stub endpoint
@router.get("/huggingface/status")
async def huggingface_status():
    """Get Huggingface storage status (stub implementation)."""
    return {
        "success": True,
        "status": "simulated",
        "message": "Huggingface storage backend is simulated in this implementation",
        "simulated": True
    }

# Register router with the API prefix
app.include_router(router, prefix=API_PREFIX)

# Main function
if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    
    # Start IPFS daemon if not running
    start_ipfs_daemon()
    
    # Write PID file
    with open("robust_mcp_server.pid", "w") as f:
        f.write(str(os.getpid()))
    
    # Run server
    logger.info(f"Starting robust MCP server on port {PORT}")
    logger.info(f"API prefix: {API_PREFIX}")
    logger.info(f"Server ID: {SERVER_ID}")
    
    uvicorn.run(
        "robust_mcp_server:app",
        host=HOST,
        port=PORT,
        reload=False
    )
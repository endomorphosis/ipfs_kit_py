#!/usr/bin/env python3
"""
This test script is the properly named version of the original:
run_mcp_simulation_server.py

It has been moved to the appropriate test directory for better organization.
"""

# Original content follows:

#!/usr/bin/env python
"""
DEPRECATED: This script has been replaced by mcp_server_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

import argparse
import json
import logging
import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s: %(message)s')
logger = logging.getLogger("mcp_simulation_server")

# Create FastAPI app
app = FastAPI(
    title="IPFS MCP Simulation Server",
    description="Simulation server for IPFS MCP storage backends",
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

# Store backends status
storage_backends = {
    "filecoin": True,
    "s3": True,
    "huggingface": True,
    "storacha": True,
    "lassie": True
}

# Add routes for storage backends
@app.get("/api/v0/mcp/health")
async def health_check():
    # Health check endpoint
    return {
        "success": True,
        "status": "ok",
        "timestamp": time.time(),
        "server_id": "simulation-server-001",
        "debug_mode": True,
        "isolation_mode": True,
        "ipfs_daemon_running": True,
        "auto_start_daemons_enabled": False,
        "controllers": {
            "ipfs": True,
            "cli": True,
            "credentials": True,
            "storage_manager": True,
            "storage_huggingface": True,
            "storage_storacha": True,
            "storage_filecoin": True,
            "storage_lassie": True,
            "distributed": True,
            "fs_journal": True,
            "peer_websocket": True,
            "webrtc": True
        },
        "simulation_mode": True
    }

@app.get("/api/v0/mcp/filecoin/status")
async def filecoin_status():
    # Filecoin status endpoint
    return {
        "success": True,
        "operation": "check_connection",
        "duration_ms": 0.1,
        "is_available": storage_backends["filecoin"],
        "backend": "filecoin",
        "version": "Simulation v1.0",
        "connected": True,
        "simulation_mode": True
    }

@app.get("/api/v0/mcp/storage/huggingface/status")
async def huggingface_status():
    # HuggingFace status endpoint
    return {
        "success": True,
        "operation_id": f"status-{int(time.time())}",
        "duration_ms": 0.1,
        "is_available": storage_backends["huggingface"],
        "backend": "huggingface",
        "version": "Simulation v1.0",
        "connected": True,
        "simulation_mode": True
    }

@app.get("/api/v0/mcp/storage/storacha/status")
async def storacha_status():
    # Storacha status endpoint
    return {
        "success": True,
        "operation_id": f"status-{int(time.time())}",
        "duration_ms": 0.1,
        "is_available": storage_backends["storacha"],
        "backend": "storacha",
        "version": "Simulation v1.0",
        "connected": True,
        "simulation_mode": True
    }

@app.get("/api/v0/mcp/storage/lassie/status")
async def lassie_status():
    # Lassie status endpoint
    return {
        "success": True,
        "operation_id": f"status-{int(time.time())}",
        "duration_ms": 0.03,
        "is_available": storage_backends["lassie"],
        "backend": "lassie",
        "version": "Simulation v1.0",
        "connected": True,
        "simulation_mode": True
    }

@app.get("/api/v0/mcp/storage/{storage_name}/status")
async def generic_storage_status(storage_name: str):
    # Generic storage status endpoint
    if storage_name in storage_backends:
        return {
            "success": True,
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": 0.1,
            "is_available": storage_backends[storage_name],
            "backend": storage_name,
            "version": "Simulation v1.0",
            "connected": True,
            "simulation_mode": True
        }
    else:
        storage_backends[storage_name] = True
        return {
            "success": True,
            "operation_id": f"status-{int(time.time())}",
            "duration_ms": 0.1,
            "is_available": True,
            "backend": storage_name,
            "version": "Simulation v1.0",
            "connected": True,
            "simulation_mode": True
        }

@app.get("/api/v0/mcp/storage/status")
async def overall_storage_status():
    # Overall storage status endpoint
    backends = {}
    for name, available in storage_backends.items():
        backends[name] = {
            "available": available,
            "simulation_mode": True,
            "version": "Simulation v1.0"
        }

    return {
        "success": True,
        "operation_id": f"status-{int(time.time())}",
        "timestamp": time.time(),
        "backends": backends,
        "simulation_mode": True
    }

def main():
    # Run the server
    parser = argparse.ArgumentParser(description="Run MCP Simulation Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    logger.info(f"Starting MCP Simulation Server on {args.host}:{args.port}")
    logger.info("All storage backends are simulated and will report as working")

    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()

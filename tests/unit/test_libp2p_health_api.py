#!/usr/bin/env python3
"""
Quick LibP2P Health Status Test

This script provides a simple API endpoint to test the LibP2P health status
and verify that it shows as healthy in the dashboard.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LibP2P Health Test API", version="1.0.0")

@app.get("/health/libp2p")
async def get_libp2p_health():
    """Get LibP2P health status."""
    try:
        # Import health monitor
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        config_dir = Path("/tmp/ipfs_kit_libp2p_test")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        health_monitor = BackendHealthMonitor(config_dir=config_dir)
        
        # Create LibP2P backend structure
        libp2p_backend = {
            "name": "libp2p",
            "type": "peer_network",
            "status": "unknown",
            "health": "unknown",
            "detailed_info": {},
            "metrics": {},
            "errors": [],
            "last_check": None
        }
        
        # Check health
        result = await health_monitor._check_libp2p_health(libp2p_backend)
        
        return JSONResponse(content={
            "timestamp": datetime.now().isoformat(),
            "service": "libp2p",
            "status": result.get("status", "unknown"),
            "health": result.get("health", "unknown"),
            "message": result.get("status_message", "No message"),
            "details": result.get("detailed_info", {}),
            "metrics": result.get("metrics", {}),
            "errors": result.get("errors", [])
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "timestamp": datetime.now().isoformat(),
                "service": "libp2p",
                "status": "error",
                "health": "unhealthy",
                "message": f"Health check failed: {str(e)}",
                "error": str(e)
            }
        )

@app.get("/health/all")
async def get_all_health():
    """Get health status for all storage backends."""
    try:
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        config_dir = Path("/tmp/ipfs_kit_test_config")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        health_monitor = BackendHealthMonitor(config_dir=config_dir)
        
        # Get all backend health
        health_status = await health_monitor.get_backend_health()
        
        return JSONResponse(content={
            "timestamp": datetime.now().isoformat(),
            "overall_healthy": all(
                backend.get("health") == "healthy" 
                for backend in health_status.get("backends", {}).values()
            ),
            "backends": health_status.get("backends", {}),
            "summary": health_status.get("summary", {})
        })
        
    except Exception as e:
        logger.error(f"All health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )

@app.get("/libp2p/peers")
async def get_libp2p_peers():
    """Get LibP2P peer information."""
    try:
        from enhanced_libp2p_manager import get_libp2p_manager
        
        manager = get_libp2p_manager()
        
        if not manager.host_active:
            # Try to start it
            await manager.start()
        
        stats = manager.get_peer_statistics()
        peers = manager.get_all_peers()
        content = manager.get_shared_content_summary()
        
        return JSONResponse(content={
            "timestamp": datetime.now().isoformat(),
            "peer_id": stats.get("peer_id"),
            "statistics": stats,
            "content_summary": content,
            "peers": {
                peer_id: {
                    "source": info.get("source"),
                    "connected": info.get("connected"),
                    "last_seen": info.get("last_seen"),
                    "protocols": info.get("protocols", [])
                }
                for peer_id, info in list(peers.items())[:20]  # Limit to first 20
            },
            "peer_count": len(peers)
        })
        
    except Exception as e:
        logger.error(f"Peer info failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "LibP2P Health Test API",
        "version": "1.0.0",
        "endpoints": {
            "/health/libp2p": "Get LibP2P health status",
            "/health/all": "Get all backend health status", 
            "/libp2p/peers": "Get LibP2P peer information"
        },
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("🚀 Starting LibP2P Health Test API...")
    print("📡 LibP2P will be initialized on first health check")
    print("🌐 Access the API at: http://localhost:8899")
    print("📊 Health endpoint: http://localhost:8899/health/libp2p")
    print("🔗 Peers endpoint: http://localhost:8899/libp2p/peers")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8899,
        log_level="info",
        access_log=True
    )

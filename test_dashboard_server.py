#!/usr/bin/env python3
"""
Simple test server to validate the enhanced dashboard functionality.

This creates a minimal FastAPI server that serves the dashboard with
the unified API functionality to demonstrate the backend configuration
and monitoring improvements.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, '.')

from ipfs_kit_py.metadata_manager import get_metadata_manager
from ipfs_kit_py.mcp_metadata_wrapper import get_metadata_first_mcp

app = FastAPI(title="IPFS Kit Enhanced Dashboard Test")

# Get paths
dashboard_dir = Path("ipfs_kit_py/mcp/dashboard")
static_dir = dashboard_dir / "static"
templates_dir = dashboard_dir / "templates"

# Setup static files and templates
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Get our managers
metadata_manager = get_metadata_manager()
mcp_wrapper = get_metadata_first_mcp()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/overview")
async def get_overview():
    """Get system overview data."""
    backends = metadata_manager.list_backends()
    
    return JSONResponse({
        "data": {
            "counts": {
                "services_active": 1,
                "backends": len(backends),
                "buckets": 3
            }
        }
    })


@app.get("/api/backends")
async def get_backends():
    """Get all backend configurations."""
    backends = metadata_manager.list_backends()
    items = []
    
    for backend_id in backends:
        config = metadata_manager.get_backend_config(backend_id)
        if config:
            items.append({
                "name": backend_id,
                "type": config["config"].get("type", "unknown"),
                "enabled": config["config"].get("enabled", True),
                "config": config["config"]
            })
    
    return JSONResponse({"items": items})


@app.get("/api/backends/types")
async def get_backend_types():
    """Get available backend types."""
    return JSONResponse({
        "types": [
            {"name": "s3", "display": "Amazon S3"},
            {"name": "huggingface", "display": "HuggingFace Hub"},
            {"name": "filesystem", "display": "Local Filesystem"},
            {"name": "storacha", "display": "Storacha"},
            {"name": "filecoin", "display": "Filecoin"},
            {"name": "lassie", "display": "Lassie"}
        ]
    })


@app.get("/api/backends/{backend_id}")
async def get_backend(backend_id: str):
    """Get specific backend configuration."""
    config = metadata_manager.get_backend_config(backend_id)
    if not config:
        return JSONResponse({"error": "Backend not found"}, status_code=404)
    
    return JSONResponse(config)


@app.get("/api/backends/{backend_id}/stats")
async def get_backend_stats(backend_id: str):
    """Get backend statistics."""
    stats = metadata_manager.get_metadata(f"backend_stats_{backend_id}")
    if stats:
        return JSONResponse(stats)
    
    # Return mock stats if none available
    return JSONResponse({
        "status": "unknown",
        "storage": {
            "used_space": 0,
            "total_space": 0,
            "files_count": 0,
            "usage_percent": 0
        },
        "quota": {
            "limit": 0,
            "used": 0,
            "remaining": 0,
            "usage_percent": 0
        },
        "performance": {
            "avg_response_time": 0,
            "success_rate": 100,
            "error_count": 0
        }
    })


@app.get("/api/metrics/backends/{backend_id}")
async def get_backend_metrics(backend_id: str):
    """Get backend metrics."""
    if backend_id == "all":
        # Return stats for all backends
        backends = metadata_manager.list_backends()
        backend_stats = {}
        
        for bid in backends:
            stats = metadata_manager.get_metadata(f"backend_stats_{bid}")
            if stats:
                backend_stats[bid] = stats
        
        return JSONResponse({"backends": backend_stats})
    
    return await get_backend_stats(backend_id)


@app.post("/api/backends/{backend_id}/test")
async def test_backend(backend_id: str):
    """Test backend connectivity."""
    config = metadata_manager.get_backend_config(backend_id)
    if not config:
        return JSONResponse({"error": "Backend not found"}, status_code=404)
    
    # Mock successful test for demo
    return JSONResponse({
        "success": True,
        "message": f"Backend {backend_id} test completed successfully",
        "response_time": 234,
        "timestamp": "2025-08-16T00:20:00Z"
    })


@app.delete("/api/backends/{backend_id}")
async def delete_backend(backend_id: str):
    """Remove a backend."""
    success = metadata_manager.remove_backend_config(backend_id)
    
    if success:
        return JSONResponse({
            "success": True,
            "message": f"Backend {backend_id} removed successfully"
        })
    else:
        return JSONResponse({"error": "Failed to remove backend"}, status_code=500)


@app.get("/api/config")
async def get_config():
    """Get configuration data."""
    all_config = metadata_manager.get_all_config()
    
    # Get backend configs
    backends = metadata_manager.list_backends()
    backend_configs = {}
    
    for backend_id in backends:
        config = metadata_manager.get_backend_config(backend_id)
        if config:
            backend_configs[backend_id] = config
    
    return JSONResponse({
        "config": {
            "main": all_config,
            "backends": backend_configs
        }
    })


@app.get("/api/services")
async def get_services():
    """Get service status."""
    return JSONResponse({
        "services": {
            "ipfs": {
                "bin": "/usr/local/bin/ipfs",
                "api_port_open": True
            }
        }
    })


@app.get("/api/metrics/system")
async def get_system_metrics():
    """Get system metrics."""
    return JSONResponse({
        "cpu_percent": 25.5,
        "memory": {
            "used": 2.1 * 1024 * 1024 * 1024,  # 2.1GB
            "total": 8.0 * 1024 * 1024 * 1024,  # 8GB
            "percent": 26.25
        },
        "disk": {
            "used": 45.2 * 1024 * 1024 * 1024,  # 45.2GB
            "total": 100.0 * 1024 * 1024 * 1024,  # 100GB
            "percent": 45.2
        },
        "network": {
            "points": [
                {"tx_bps": 125000, "rx_bps": 89000},
                {"tx_bps": 142000, "rx_bps": 95000},
                {"tx_bps": 98000, "rx_bps": 78000}
            ]
        }
    })


@app.get("/api/buckets")
async def get_buckets():
    """Get bucket information."""
    return JSONResponse({
        "items": [
            {
                "name": "production-data",
                "backend": "aws-s3-prod",
                "meta": {"created": "2025-08-15", "size": "45GB"}
            },
            {
                "name": "model-cache", 
                "backend": "huggingface-models",
                "meta": {"created": "2025-08-14", "size": "23GB"}
            },
            {
                "name": "local-storage",
                "backend": "local-storage", 
                "meta": {"created": "2025-08-16", "size": "12GB"}
            }
        ]
    })


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("IPFS Kit Enhanced Dashboard Test Server")
    print("=" * 60)
    print("Features being tested:")
    print("✓ Unified JavaScript API integration")
    print("✓ Backend configuration management")
    print("✓ Enhanced monitoring with quota/storage stats")
    print("✓ Metadata-first MCP approach")
    print("✓ ~/.ipfs_kit/ directory integration")
    print()
    print(f"Using ~/.ipfs_kit/ at: {metadata_manager.base_dir}")
    print(f"Available backends: {metadata_manager.list_backends()}")
    print()
    print("Starting server at http://localhost:8080")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
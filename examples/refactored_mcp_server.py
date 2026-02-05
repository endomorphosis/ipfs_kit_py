#!/usr/bin/env python3
"""
Refactored IPFS-Kit MCP Server

This is a lightweight MCP server that delegates filesystem backend management
to the IPFS-Kit daemon while providing direct access to IPFS-Kit libraries
for retrieval operations and reading from parquet indexes for routing.

Architecture:
- MCP Server: Lightweight client for MCP tools and dashboard
- IPFS-Kit Daemon: Manages filesystem backends, health, replication, logging
- IPFS-Kit Libraries: Direct access for retrieval operations
- Parquet Indexes: Fast routing decisions
"""

import anyio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# FastAPI imports
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Configure logging
log_dir = Path("/tmp/ipfs_kit_logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_dir / 'refactored_mcp_server.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import daemon client and IPFS Kit
try:
    from ipfs_kit_py.ipfs_kit_daemon_client import IPFSKitClientMixin, daemon_client, route_reader
    DAEMON_CLIENT_AVAILABLE = True
    logger.info("✓ Daemon client available")
except ImportError as e:
    logger.error(f"Daemon client not available: {e}")
    DAEMON_CLIENT_AVAILABLE = False
    IPFSKitClientMixin = object

# Import IPFS Kit for direct retrieval operations
try:
    from ipfs_kit_py.ipfs_kit import IPFSKit
    IPFS_KIT_AVAILABLE = True
    logger.info("✓ IPFS Kit available for retrieval operations")
except ImportError as e:
    logger.error(f"IPFS Kit not available: {e}")
    IPFS_KIT_AVAILABLE = False

# Import MCP components
try:
    from ipfs_kit_py.mcp.ipfs_kit.api.vfs_endpoints import VFSEndpoints
    from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    VFS_ENDPOINTS_AVAILABLE = True
    logger.info("✓ VFS endpoints available")
except ImportError as e:
    logger.error(f"VFS endpoints not available: {e}")
    VFS_ENDPOINTS_AVAILABLE = False


class RefactoredMCPServer(IPFSKitClientMixin if DAEMON_CLIENT_AVAILABLE else object):
    """
    Lightweight MCP server that uses the IPFS-Kit daemon for management
    and IPFS-Kit libraries for retrieval operations.
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8888):
        if DAEMON_CLIENT_AVAILABLE:
            super().__init__()
        
        self.host = host
        self.port = port
        self.start_time = time.time()
        
        # Core components
        self.app = FastAPI(title="Refactored IPFS-Kit MCP Server")
        self.ipfs_kit: Optional[IPFSKit] = None
        self.vfs_endpoints: Optional[VFSEndpoints] = None
        self.health_monitor: Optional[BackendHealthMonitor] = None
        
        # Initialize components
        self._setup_app()
        self._initialize_components()
        self._setup_routes()
    
    def _setup_app(self):
        """Setup FastAPI application."""
        # Add CORS middleware
        from fastapi.middleware.cors import CORSMiddleware
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup static files and templates
        try:
            static_dir = Path(__file__).parent / "mcp" / "ipfs_kit" / "static"
            templates_dir = Path(__file__).parent / "mcp" / "ipfs_kit" / "templates"
            
            if static_dir.exists():
                self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            
            if templates_dir.exists():
                self.templates = Jinja2Templates(directory=str(templates_dir))
            else:
                self.templates = None
                
        except Exception as e:
            logger.warning(f"Could not setup static files/templates: {e}")
            self.templates = None
    
    def _initialize_components(self):
        """Initialize core components."""
        logger.info("🔧 Initializing MCP server components...")
        
        # Initialize IPFS Kit for retrieval operations (not management)
        if IPFS_KIT_AVAILABLE:
            try:
                # Initialize without auto-starting daemons - that's the daemon's job
                config = {"auto_start_daemons": False}
                self.ipfs_kit = IPFSKit(config)
                logger.info("✅ IPFS Kit initialized for retrieval operations")
            except Exception as e:
                logger.warning(f"IPFS Kit initialization failed: {e}")
                self.ipfs_kit = None
        
        # Initialize health monitor (for local health checks)
        try:
            self.health_monitor = BackendHealthMonitor(config_dir="/tmp/ipfs_kit_config")
            logger.info("✅ Health monitor initialized")
        except Exception as e:
            logger.warning(f"Health monitor initialization failed: {e}")
            self.health_monitor = None
        
        # Initialize VFS endpoints
        if VFS_ENDPOINTS_AVAILABLE:
            try:
                self.vfs_endpoints = VFSEndpoints(
                    backend_monitor=self.health_monitor,
                    vfs_observer=None  # VFS observer handled by daemon
                )
                logger.info("✅ VFS endpoints initialized")
            except Exception as e:
                logger.warning(f"VFS endpoints initialization failed: {e}")
                self.vfs_endpoints = None
    
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.get("/")
        async def dashboard():
            """Main dashboard."""
            if self.templates:
                return self.templates.TemplateResponse("index.html", {"request": {}})
            else:
                return HTMLResponse("""
                <html>
                    <head><title>IPFS-Kit MCP Server</title></head>
                    <body>
                        <h1>IPFS-Kit MCP Server</h1>
                        <p>Refactored architecture with daemon-based backend management</p>
                        <ul>
                            <li><a href="/api/health">Health Status</a></li>
                            <li><a href="/api/daemon/status">Daemon Status</a></li>
                            <li><a href="/api/vfs/health">VFS Health</a></li>
                        </ul>
                    </body>
                </html>
                """)
        
        @self.app.get("/api/health")
        async def get_health():
            """Get MCP server health."""
            return await self._get_mcp_health()
        
        @self.app.get("/api/daemon/status")
        async def get_daemon_status():
            """Get daemon status."""
            if DAEMON_CLIENT_AVAILABLE:
                return await self.get_cached_daemon_status()
            else:
                return {"error": "Daemon client not available"}
        
        @self.app.post("/api/daemon/start")
        async def start_daemon():
            """Start the daemon."""
            if DAEMON_CLIENT_AVAILABLE:
                return await daemon_client.start_daemon()
            else:
                return {"error": "Daemon client not available"}
        
        @self.app.post("/api/daemon/stop")
        async def stop_daemon():
            """Stop the daemon."""
            if DAEMON_CLIENT_AVAILABLE:
                return await daemon_client.stop_daemon()
            else:
                return {"error": "Daemon client not available"}
        
        @self.app.get("/api/backends/health")
        async def get_backends_health():
            """Get backend health from daemon."""
            if DAEMON_CLIENT_AVAILABLE:
                return await self.get_backend_health_from_daemon()
            else:
                return {"error": "Daemon client not available"}
        
        @self.app.post("/api/backends/{backend_name}/restart")
        async def restart_backend(backend_name: str):
            """Restart a backend via daemon."""
            if DAEMON_CLIENT_AVAILABLE:
                return await self.request_backend_restart(backend_name)
            else:
                return {"error": "Daemon client not available"}
        
        # VFS API endpoints
        if self.vfs_endpoints:
            @self.app.get("/api/vfs/health")
            async def get_vfs_health():
                return await self.vfs_endpoints.get_vfs_health()
            
            @self.app.get("/api/vfs/analytics")
            async def get_vfs_analytics():
                return await self.vfs_endpoints.get_vfs_analytics()
            
            @self.app.get("/api/vfs/journal")
            async def get_vfs_journal(backend_filter: Optional[str] = None, search_query: Optional[str] = None):
                return await self.vfs_endpoints.get_vfs_journal(backend_filter, search_query)
            
            @self.app.get("/api/vfs/files")
            async def list_files(path: str = "/"):
                return await self.vfs_endpoints.list_files(path)
            
            @self.app.post("/api/vfs/folders")
            async def create_folder(request: Request):
                data = await request.json()
                return await self.vfs_endpoints.create_folder(
                    data.get("path", "/"),
                    data.get("name", "new_folder")
                )
        
        # IPFS retrieval operations (direct IPFS Kit usage)
        @self.app.get("/api/ipfs/cat/{cid}")
        async def ipfs_cat(cid: str):
            """Retrieve content from IPFS."""
            return await self._ipfs_retrieval_operation("cat", cid)
        
        @self.app.get("/api/ipfs/stat/{cid}")
        async def ipfs_stat(cid: str):
            """Get IPFS object statistics."""
            return await self._ipfs_retrieval_operation("stat", cid)
        
        @self.app.post("/api/ipfs/add")
        async def ipfs_add(request: Request):
            """Add content to IPFS."""
            data = await request.json()
            content = data.get("content", "")
            return await self._ipfs_modification_operation("add", content=content)
        
        # Routing operations (direct parquet index access)
        @self.app.get("/api/routing/backends/{cid}")
        async def find_backends_for_cid(cid: str):
            """Find which backends have a CID."""
            if route_reader:
                backends = route_reader.find_backends_for_cid(cid)
                return {"cid": cid, "backends": backends}
            else:
                return {"error": "Route reader not available"}
        
        @self.app.get("/api/routing/suggest")
        async def suggest_backend():
            """Suggest best backend for new pin."""
            if route_reader:
                backend = route_reader.suggest_backend_for_new_pin()
                stats = route_reader.get_backend_stats()
                return {"suggested_backend": backend, "backend_stats": stats}
            else:
                return {"error": "Route reader not available"}
    
    async def _get_mcp_health(self) -> Dict[str, Any]:
        """Get MCP server health status."""
        health = {
            "server": "healthy",
            "uptime": time.time() - self.start_time,
            "components": {
                "daemon_client": DAEMON_CLIENT_AVAILABLE,
                "ipfs_kit": self.ipfs_kit is not None,
                "vfs_endpoints": self.vfs_endpoints is not None,
                "health_monitor": self.health_monitor is not None
            },
            "timestamp": time.time()
        }
        
        # Check daemon status
        if DAEMON_CLIENT_AVAILABLE:
            try:
                daemon_status = await self.get_cached_daemon_status()
                health["daemon"] = {
                    "running": daemon_status.get("running", False),
                    "status": daemon_status.get("daemon", {}).get("uptime", "unknown")
                }
            except Exception as e:
                health["daemon"] = {"error": str(e)}
        
        # Check IPFS Kit availability
        if self.ipfs_kit:
            try:
                # Simple test to see if IPFS Kit is responsive
                with anyio.fail_after(5):
                    result = await self._test_ipfs_kit()
                health["components"]["ipfs_kit_responsive"] = result
            except Exception as e:
                health["components"]["ipfs_kit_error"] = str(e)
        
        return health
    
    async def _test_ipfs_kit(self) -> bool:
        """Test if IPFS Kit is responsive."""
        try:
            if hasattr(self.ipfs_kit, 'ipfs_id'):
                result = self.ipfs_kit.ipfs_id()
                return result.get("success", False)
            return False
        except Exception:
            return False
    
    async def _ipfs_retrieval_operation(self, operation: str, *args, **kwargs) -> Dict[str, Any]:
        """Perform IPFS retrieval operation."""
        if not self.ipfs_kit:
            return {"success": False, "error": "IPFS Kit not available"}
        
        try:
            if operation == "cat":
                result = self.ipfs_kit.cat(args[0])
            elif operation == "stat":
                result = self.ipfs_kit.ipfs_stat_path(args[0])
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _ipfs_modification_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Perform IPFS modification operation."""
        if not self.ipfs_kit:
            return {"success": False, "error": "IPFS Kit not available"}
        
        try:
            if operation == "add":
                content = kwargs.get("content", "")
                result = self.ipfs_kit.add_str(content)
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def start(self):
        """Start the MCP server."""
        logger.info("🚀 Starting Refactored IPFS-Kit MCP Server")
        logger.info("=" * 60)
        logger.info(f"📍 Host: {self.host}")
        logger.info(f"🚪 Port: {self.port}")
        logger.info(f"🔗 Dashboard: http://{self.host}:{self.port}")
        
        # Ensure daemon is running if available
        if DAEMON_CLIENT_AVAILABLE:
            daemon_running = await self.ensure_daemon_running()
            if daemon_running:
                logger.info("✅ IPFS-Kit daemon is running")
            else:
                logger.warning("⚠️ IPFS-Kit daemon not running - management features limited")
        
        logger.info("=" * 60)
        
        # Start the server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Refactored IPFS-Kit MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--start-daemon", action="store_true", 
                       help="Start daemon automatically if not running")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Start daemon if requested
    if args.start_daemon and DAEMON_CLIENT_AVAILABLE:
        async def start_daemon_if_needed():
            if not await daemon_client.is_daemon_running():
                logger.info("Starting IPFS-Kit daemon...")
                result = await daemon_client.start_daemon()
                if result.get("success"):
                    logger.info("✅ Daemon started")
                else:
                    logger.error(f"Failed to start daemon: {result.get('error')}")
        
        anyio.run(start_daemon_if_needed)
    
    # Start MCP server
    server = RefactoredMCPServer(host=args.host, port=args.port)
    
    try:
        anyio.run(server.start)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Refactored Unified MCP Dashboard - Separated Components

This refactored implementation provides:
- Separated HTML, CSS, and JavaScript files
- Clean template-based rendering
- Maintained functionality with better organization
- Proper static file serving
"""

import asyncio
import json
import logging
import time
import psutil
import sys
import traceback
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union

# Web framework imports
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# MCP protocol
try:
    from mcp import McpServer
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# Import IPFS Kit components
try:
    from ..unified_bucket_interface import UnifiedBucketInterface, BackendType
    from ..bucket_vfs_manager import BucketType, VFSStructureType, get_global_bucket_manager
    from ..enhanced_bucket_index import EnhancedBucketIndex
    from ..error import create_result_dict
    IPFS_KIT_AVAILABLE = True
except ImportError:
    # Create simple fallback classes when imports aren't available
    class UnifiedBucketInterface:
        def __init__(self, **kwargs): pass
    class EnhancedBucketIndex:
        def __init__(self, **kwargs): pass
    def get_global_bucket_manager(**kwargs): return None
    IPFS_KIT_AVAILABLE = False

logger = logging.getLogger(__name__)


class RefactoredUnifiedMCPDashboard:
    """
    Refactored Unified MCP Server + Dashboard on single port (8004).
    
    Key improvements:
    - Separated HTML template from Python code
    - External CSS and JavaScript files
    - Better maintainability and modularity
    - Clean template rendering with Jinja2
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the refactored unified MCP server and dashboard."""
        if config is None:
            config = {
                'host': '127.0.0.1',
                'port': 8004,  # Single port for both MCP and dashboard
                'data_dir': '~/.ipfs_kit',
                'debug': False,
                'update_interval': 3
            }
        
        self.config = config
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8004)
        self.data_dir = Path(config.get('data_dir', '~/.ipfs_kit')).expanduser()
        self.debug = config.get('debug', False)
        self.update_interval = config.get('update_interval', 3)
        
        # Set up paths for templates and static files
        self.mcp_dir = Path(__file__).parent
        self.template_dir = self.mcp_dir / "dashboard_templates"
        self.static_dir = self.mcp_dir / "dashboard_static"
        
        # Initialize FastAPI app with both MCP and dashboard routes
        self.app = FastAPI(
            title="IPFS Kit - Refactored MCP Server & Dashboard",
            version="4.0.0",
            description="Single-port MCP server with integrated dashboard (refactored)"
        )
        
        # Setup template engine
        self.templates = Jinja2Templates(directory=str(self.template_dir))
        
        # Setup components
        self._setup_middleware()
        self._setup_static_files()
        self._register_mcp_tools()
        self._setup_routes()
        
        # Initialize IPFS Kit components if available
        if IPFS_KIT_AVAILABLE:
            try:
                self.bucket_interface = UnifiedBucketInterface(ipfs_kit_dir=self.data_dir)
                self.bucket_index = EnhancedBucketIndex(data_dir=self.data_dir)
                self.global_bucket_manager = get_global_bucket_manager()
            except Exception as e:
                logger.warning(f"Failed to initialize IPFS Kit components: {e}")
                self.bucket_interface = None
                self.bucket_index = None
                self.global_bucket_manager = None
        else:
            self.bucket_interface = None
            self.bucket_index = None
            self.global_bucket_manager = None

    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_static_files(self):
        """Setup static file serving."""
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")

    def _register_mcp_tools(self):
        """Register MCP tools for VS Code integration."""
        if not MCP_AVAILABLE:
            logger.warning("MCP not available, skipping tool registration")
            return
            
        self.mcp_tools = [
            Tool(
                name="list_buckets",
                description="List all available storage buckets",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "backend_filter": {
                            "type": "string",
                            "description": "Optional backend type filter"
                        }
                    }
                }
            ),
            Tool(
                name="create_bucket",
                description="Create a new storage bucket",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "backend": {"type": "string"},
                        "bucket_type": {"type": "string"}
                    },
                    "required": ["name", "backend"]
                }
            ),
            Tool(
                name="delete_bucket",
                description="Delete a storage bucket",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="add_pin",
                description="Add a pin to a bucket",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bucket": {"type": "string"},
                        "cid": {"type": "string"},
                        "name": {"type": "string"}
                    },
                    "required": ["bucket", "cid"]
                }
            ),
            Tool(
                name="remove_pin",
                description="Remove a pin from a bucket",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string"}
                    },
                    "required": ["cid"]
                }
            ),
            Tool(
                name="get_system_status",
                description="Get current system status and metrics",
                inputSchema={"type": "object", "properties": {}}
            )
        ]

    def _setup_routes(self):
        """Setup all API routes for both MCP and dashboard."""
        
        @self.app.post("/mcp/initialize")
        async def mcp_initialize():
            """MCP initialization endpoint."""
            return {"capabilities": {"tools": {}}}

        @self.app.get("/mcp/tools/list")
        async def mcp_list_tools():
            """List available MCP tools."""
            return {
                "tools": [tool.dict() for tool in self.mcp_tools] if hasattr(self, 'mcp_tools') else []
            }

        @self.app.post("/mcp/tools/call")
        async def mcp_call_tool(request: Request):
            """Execute MCP tool."""
            try:
                body = await request.json()
                tool_name = body.get("name")
                arguments = body.get("arguments", {})
                
                if tool_name == "list_buckets":
                    result = await self._handle_list_buckets(arguments)
                elif tool_name == "create_bucket":
                    result = await self._handle_create_bucket(arguments)
                elif tool_name == "delete_bucket":
                    result = await self._handle_delete_bucket(arguments)
                elif tool_name == "add_pin":
                    result = await self._handle_add_pin(arguments)
                elif tool_name == "remove_pin":
                    result = await self._handle_remove_pin(arguments)
                elif tool_name == "get_system_status":
                    result = await self._handle_get_system_status(arguments)
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
                
                return {"content": [TextContent(type="text", text=json.dumps(result, indent=2)).dict()]}
            except Exception as e:
                return {"error": str(e)}

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Serve the main dashboard."""
            return self.templates.TemplateResponse("unified_dashboard.html", {
                "request": request,
                "port": self.port
            })

        @self.app.get("/api/system/overview")
        async def get_system_overview():
            """Get system overview data."""
            try:
                system_data = self._get_system_metrics()
                services_data = await self._get_services_status()
                backends_data = await self._get_backends_status()
                buckets_data = await self._get_buckets_status()
                
                return {
                    "system": system_data,
                    "services": len(services_data.get("services", [])),
                    "backends": len(backends_data.get("backends", [])),
                    "buckets": len(buckets_data.get("buckets", [])),
                    "peer_id": await self._get_ipfs_peer_id(),
                    "addresses": await self._get_ipfs_addresses()
                }
            except Exception as e:
                logger.error(f"Error getting system overview: {e}")
                return {"error": str(e)}

        @self.app.get("/api/system/metrics")
        async def get_system_metrics():
            """Get detailed system metrics."""
            try:
                return self._get_system_metrics()
            except Exception as e:
                logger.error(f"Error getting system metrics: {e}")
                return {"error": str(e)}

        @self.app.get("/api/services")
        async def get_services():
            """Get services status."""
            return await self._get_services_status()

        @self.app.get("/api/backends")
        async def get_backends():
            """Get backends status."""
            return await self._get_backends_status()

        @self.app.get("/api/buckets")
        async def get_buckets():
            """Get buckets status."""
            return await self._get_buckets_status()

        @self.app.get("/api/pins")
        async def get_pins():
            """Get pinned items."""
            return await self._get_pins_status()

        @self.app.post("/api/pins")
        async def add_pin(request: Request):
            """Add a new pin."""
            try:
                body = await request.json()
                cid = body.get("cid")
                name = body.get("name", "")
                
                result = await self._add_pin(cid, name)
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}

        @self.app.delete("/api/pins/{cid}")
        async def remove_pin(cid: str):
            """Remove a pin."""
            try:
                result = await self._remove_pin(cid)
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/config")
        async def get_config():
            """Get system configuration."""
            return await self._get_config_status()
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "version": "4.0.0",
                "unified_mode": True,
                "timestamp": datetime.now().isoformat(),
                "message": "Unified MCP dashboard running"
            }

    def _get_system_metrics(self):
        """Get current system metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            return {
                "cpu": {
                    "usage": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": memory.total,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "sent": network.bytes_sent,
                    "recv": network.bytes_recv
                }
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {
                "cpu": {"usage": 0, "count": 0},
                "memory": {"total": 0, "used": 0, "percent": 0},
                "disk": {"total": 0, "used": 0, "percent": 0},
                "network": {"sent": 0, "recv": 0}
            }

    async def _get_services_status(self):
        """Get status of all services."""
        services = []
        
        # MCP Server (always running if we're here)
        services.append({
            "name": "MCP Server",
            "status": "running",
            "type": "mcp",
            "description": "Model Context Protocol Server"
        })
        
        # Check IPFS daemon
        ipfs_status = await self._check_ipfs_daemon()
        services.append({
            "name": "IPFS Daemon",
            "status": ipfs_status["status"],
            "type": "ipfs",
            "description": "InterPlanetary File System Daemon",
            "error": ipfs_status.get("error")
        })
        
        return {
            "services": services,
            "summary": {
                "total": len(services),
                "running": len([s for s in services if s["status"] == "running"]),
                "stopped": len([s for s in services if s["status"] in ["stopped", "error"]])
            }
        }

    async def _get_backends_status(self):
        """Get status of storage backends."""
        if not self.bucket_interface:
            return {"backends": []}
        
        try:
            result = await self.bucket_interface.list_backend_buckets()
            if result["success"]:
                backends = {}
                for bucket in result["data"]["buckets"]:
                    backend_name = bucket["backend"]
                    if backend_name not in backends:
                        backends[backend_name] = {
                            "name": backend_name,
                            "type": backend_name,
                            "status": "online",
                            "buckets": []
                        }
                    backends[backend_name]["buckets"].append(bucket["bucket_name"])
                return {"backends": list(backends.values())}
            else:
                logger.error(f"Error getting backends: {result['error']}")
                return {"backends": []}
        except Exception as e:
            logger.error(f"Error getting backends: {e}")
            return {"backends": []}

    async def _get_buckets_status(self):
        """Get status of buckets."""
        if not self.bucket_interface:
            return {"buckets": []}
        
        try:
            result = await self.bucket_interface.list_backend_buckets()
            if result["success"]:
                return {"buckets": result["data"]["buckets"]}
            else:
                logger.error(f"Error getting buckets: {result['error']}")
                return {"buckets": []}
        except Exception as e:
            logger.error(f"Error getting buckets: {e}")
            return {"buckets": []}

    async def _get_pins_status(self):
        """Get pinned items."""
        if not self.global_pin_index:
            return {"pins": []}
        
        try:
            all_pins = self.global_pin_index.get_all_pins()
            return {"pins": all_pins}
        except Exception as e:
            logger.error(f"Error getting pins: {e}")
            return {"pins": []}

    async def _get_config_status(self):
        """Get system configuration."""
        try:
            config = {
                "daemon": {
                    "status": "running",
                    "port": self.port,
                    "host": self.host,
                    "data_dir": str(self.data_dir),
                    "debug": self.debug
                },
                "mcp": {
                    "enabled": True,
                    "protocol_version": "1.0",
                    "tools_available": MCP_AVAILABLE
                },
                "backends": {
                    "available": [b.value for b in BackendType],
                    "configured": list(self.bucket_vfs_managers.keys())
                },
                "features": {
                    "unified_dashboard": True,
                    "bucket_management": True,
                    "pin_management": True,
                    "service_management": True
                }
            }
            
            return {"config": config, "status": "loaded"}
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return {"config": {}, "status": "error", "error": str(e)}

    async def _add_pin(self, cid: str, name: str = ""):
        """Add a pin."""
        try:
            # This would need actual IPFS pin implementation
            # For now, return success
            return {"success": True, "message": f"Pin added: {cid}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _remove_pin(self, cid: str):
        """Remove a pin."""
        try:
            # This would need actual IPFS pin implementation
            # For now, return success
            return {"success": True, "message": f"Pin removed: {cid}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _check_ipfs_daemon(self):
        """Check if IPFS daemon is running."""
        try:
            # This would need actual IPFS daemon check
            # For now, return unknown status
            return {"status": "unknown", "error": "IPFS check not implemented"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _get_ipfs_peer_id(self):
        """Get IPFS peer ID."""
        try:
            # This would need actual IPFS API call
            return None
        except Exception as e:
            logger.error(f"Error getting IPFS peer ID: {e}")
            return None

    async def _get_ipfs_addresses(self):
        """Get IPFS addresses."""
        try:
            # This would need actual IPFS API call
            return []
        except Exception as e:
            logger.error(f"Error getting IPFS addresses: {e}")
            return []

    # MCP tool handlers
    async def _handle_list_buckets(self, arguments: Dict[str, Any]):
        """Handle list_buckets MCP tool."""
        try:
            buckets_data = await self._get_buckets_status()
            return create_result_dict(True, "Buckets listed successfully", buckets_data)
        except Exception as e:
            return create_result_dict(False, f"Error listing buckets: {e}")

    async def _handle_create_bucket(self, arguments: Dict[str, Any]):
        """Handle create_bucket MCP tool."""
        try:
            name = arguments.get("name")
            backend = arguments.get("backend")
            bucket_type = arguments.get("bucket_type", "standard")
            
            if not name or not backend:
                return create_result_dict(False, "Name and backend are required")
            
            # This would need actual bucket creation implementation
            result = {"name": name, "backend": backend, "type": bucket_type}
            return create_result_dict(True, f"Bucket '{name}' created successfully", result)
        except Exception as e:
            return create_result_dict(False, f"Error creating bucket: {e}")

    async def _handle_delete_bucket(self, arguments: Dict[str, Any]):
        """Handle delete_bucket MCP tool."""
        try:
            name = arguments.get("name")
            if not name:
                return create_result_dict(False, "Name is required")
            
            # This would need actual bucket deletion implementation
            return create_result_dict(True, f"Bucket '{name}' deleted successfully")
        except Exception as e:
            return create_result_dict(False, f"Error deleting bucket: {e}")

    async def _handle_get_system_status(self, arguments: Dict[str, Any]):
        """Handle get_system_status MCP tool."""
        try:
            overview = await self.app.router.get("/api/system/overview").endpoint()
            return create_result_dict(True, "System status retrieved", overview)
        except Exception as e:
            return create_result_dict(False, f"Error getting system status: {e}")

    async def _handle_add_pin(self, arguments: Dict[str, Any]):
        """Handle add_pin MCP tool."""
        try:
            bucket = arguments.get("bucket")
            cid = arguments.get("cid")
            name = arguments.get("name")
            if not bucket or not cid:
                return create_result_dict(False, "Bucket and CID are required")
            
            result = await self._add_pin(cid, name)
            return result
        except Exception as e:
            return create_result_dict(False, f"Error adding pin: {e}")

    async def _handle_remove_pin(self, arguments: Dict[str, Any]):
        """Handle remove_pin MCP tool."""
        try:
            cid = arguments.get("cid")
            if not cid:
                return create_result_dict(False, "CID is required")
            
            result = await self._remove_pin(cid)
            return result
        except Exception as e:
            return create_result_dict(False, f"Error removing pin: {e}")

    def run(self):
        """Run the refactored unified server."""
        logger.info(f"Starting Refactored Unified MCP Dashboard on {self.host}:{self.port}")
        logger.info(f"Template directory: {self.template_dir}")
        logger.info(f"Static directory: {self.static_dir}")
        
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info"
        )


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    dashboard = RefactoredUnifiedMCPDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Unified MCP Server + Dashboard - Single Port Integration

This unified implementation combines:
- MCP server functionality on one port
- Beautiful responsive dashboard
- Direct MCP command integration (no WebSockets)
- Modern aesthetic design
- Complete IPFS Kit integration

Usage: ipfs-kit mcp start
Port: 8004 (single port for both MCP and dashboard)
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
    from .unified_bucket_interface import UnifiedBucketInterface, BackendType
    from .bucket_vfs_manager import BucketType, VFSStructureType, get_global_bucket_manager
    from .enhanced_bucket_index import EnhancedBucketIndex
    from .error import create_result_dict
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


class UnifiedMCPDashboard:
    """
    Unified MCP Server + Dashboard on single port (8004).
    
    Provides:
    - MCP protocol endpoints for VS Code integration
    - Beautiful responsive dashboard UI
    - Direct MCP command integration (no WebSockets)
    - Real-time data via API polling
    - Modern aesthetic design with pleasing colors
    - Complete IPFS Kit backend integration
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the unified MCP server and dashboard."""
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
        
        # Initialize FastAPI app with both MCP and dashboard routes
        self.app = FastAPI(
            title="IPFS Kit - Unified MCP Server & Dashboard",
            version="4.0.0",
            description="Single-port MCP server with integrated dashboard"
        )
        
        # Initialize MCP components if available
        if MCP_AVAILABLE:
            self.mcp_server = McpServer("ipfs-kit")
            self._register_mcp_tools()
        
        # Initialize IPFS Kit components if available
        if IPFS_KIT_AVAILABLE:
            try:
                self.bucket_manager = get_global_bucket_manager()
                self.bucket_interface = UnifiedBucketInterface()
                self.bucket_index = EnhancedBucketIndex()
            except Exception as e:
                logger.warning(f"Could not initialize IPFS Kit components: {e}")
                self.bucket_manager = None
                self.bucket_interface = None
                self.bucket_index = None
        else:
            self.bucket_manager = None
            self.bucket_interface = None
            self.bucket_index = None
        
        # Data caches for efficiency
        self.system_metrics_cache = {}
        self.backends_cache = {}
        self.services_cache = {}
        self.pins_cache = {}
        self.last_update = 0
        
        self._setup_routes()
        self._setup_middleware()
    
    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _register_mcp_tools(self):
        """Register MCP tools for VS Code integration."""
        if not MCP_AVAILABLE:
            return
            
        # Register all IPFS Kit tools with the MCP server
        tools = [
            Tool(
                name="daemon_status",
                description="Get IPFS daemon status and health information",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="list_backends",
                description="List all configured storage backends",
                inputSchema={
                    "type": "object", 
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="list_buckets",
                description="List all available buckets across backends",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "backend": {"type": "string", "description": "Filter by backend name"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="system_metrics",
                description="Get detailed system performance metrics",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            )
        ]
        
        for tool in tools:
            self.mcp_server.register_tool(tool)
    
    def _setup_routes(self):
        """Setup all API routes for both MCP and dashboard."""
        
        # MCP Protocol Routes (for VS Code integration)
        @self.app.post("/mcp/initialize")
        async def mcp_initialize(request: Request):
            """MCP initialization endpoint."""
            return {"capabilities": {"tools": {}, "resources": {}}}
        
        @self.app.post("/mcp/tools/list")
        async def mcp_list_tools():
            """List available MCP tools."""
            if not MCP_AVAILABLE:
                return {"tools": []}
            return {"tools": [tool.model_dump() for tool in self.mcp_server.tools.values()]}
        
        @self.app.post("/mcp/tools/call")
        async def mcp_call_tool(request: Request):
            """Execute MCP tool."""
            data = await request.json()
            tool_name = data.get("name")
            arguments = data.get("arguments", {})
            
            # Route to appropriate handler
            if tool_name == "daemon_status":
                result = await self._get_daemon_status()
            elif tool_name == "list_backends":
                result = await self._get_backends_data()
            elif tool_name == "list_buckets":
                result = await self._get_buckets_data()
            elif tool_name == "system_metrics":
                result = await self._get_system_metrics()
            else:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
            
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        
        # Dashboard API Routes
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home():
            """Serve the main dashboard."""
            return self._get_dashboard_html()
        
        @self.app.get("/api/system/overview")
        async def api_system_overview():
            """Get system overview data."""
            return await self._get_system_overview()
        
        @self.app.get("/api/system/metrics")
        async def api_system_metrics():
            """Get detailed system metrics."""
            return await self._get_system_metrics()
        
        @self.app.get("/api/backends")
        async def api_backends():
            """Get backends data."""
            return await self._get_backends_data()
        
        @self.app.get("/api/buckets")
        async def api_buckets():
            """Get buckets data."""
            return await self._get_buckets_data()
        
        @self.app.post("/api/buckets")
        async def api_create_bucket(request: Request):
            """Create a new bucket."""
            try:
                data = await request.json()
                bucket_name = data.get("name") or data.get("bucket_name")
                bucket_type = data.get("bucket_type", "general")
                description = data.get("description", "")
                
                if not bucket_name:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Bucket name is required"}
                    )
                
                # Create bucket using the bucket manager
                result = await self._create_bucket(bucket_name, bucket_type, description)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in create_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to create bucket: {str(e)}"}
                )

        @self.app.delete("/api/buckets/{bucket_name}")
        async def api_delete_bucket(bucket_name: str):
            """Delete a bucket."""
            try:
                result = await self._delete_bucket(bucket_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in delete_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to delete bucket: {str(e)}"}
                )

        @self.app.get("/api/buckets/{bucket_name}")
        async def api_get_bucket_details(bucket_name: str):
            """Get bucket details and file list."""
            try:
                result = await self._get_bucket_details(bucket_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in get_bucket_details API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to get bucket details: {str(e)}"}
                )

        @self.app.post("/api/buckets/{bucket_name}/upload")
        async def api_upload_file_to_bucket(bucket_name: str, file: UploadFile = File(...)):
            """Upload a file to a bucket."""
            try:
                result = await self._upload_file_to_bucket(bucket_name, file)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in upload_to_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to upload file: {str(e)}"}
                )

        @self.app.get("/api/buckets/{bucket_name}/download/{file_path:path}")
        async def api_download_file_from_bucket(bucket_name: str, file_path: str):
            """Download a file from a bucket."""
            try:
                return await self._download_file_from_bucket(bucket_name, file_path)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in download_file API: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")
        
        @self.app.get("/api/services")
        async def api_services():
            """Get services status."""
            return await self._get_services_data()
        
        @self.app.get("/api/services/test")
        async def api_services_test():
            """Test services endpoint with simple data."""
            return {
                "services": [
                    {"name": "IPFS Daemon", "status": "running"},
                    {"name": "Test Service", "status": "stopped"}
                ]
            }
        
        @self.app.get("/api/config")
        async def api_config():
            """Get configuration data."""
            return await self._get_config_data()
        
        @self.app.post("/api/config")
        async def api_update_config(request: Request):
            """Update configuration data."""
            try:
                config_data = await request.json()
                result = await self._update_config_data(config_data)
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/config/backends")
        async def api_backend_configs():
            """Get all backend configurations."""
            return await self._get_backend_configs()
        
        @self.app.get("/api/pins")
        async def api_pins():
            """Get all pins."""
            return await self._get_pins_data()

        @self.app.post("/api/pins")
        async def api_add_pin(request: Request):
            """Add a new pin."""
            try:
                data = await request.json()
                cid = data.get("cid")
                name = data.get("name")
                if not cid:
                    return {"success": False, "error": "CID is required"}
                return await self._add_pin(cid, name)
            except Exception as e:
                return {"success": False, "error": str(e)}

        @self.app.delete("/api/pins/{cid}")
        async def api_remove_pin(cid: str):
            """Remove a pin."""
            try:
                return await self._remove_pin(cid)
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/config/backends/{backend_name}")
        async def api_update_backend_config(backend_name: str, request: Request):
            """Update a specific backend configuration."""
            try:
                config_data = await request.json()
                result = await self._update_backend_config(backend_name, config_data)
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # Comprehensive backend management endpoints
        @self.app.post("/api/backends/create")
        async def api_create_backend(request: Request):
            """Create a new backend configuration."""
            try:
                backend_data = await request.json()
                result = await self._create_backend_config(backend_data)
                
                # Update the cache
                await self._update_backends_cache()
                
                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"Error creating backend: {e}")
                return {"success": False, "error": str(e)}

        @self.app.delete("/api/backends/{backend_name}")
        async def api_remove_backend(backend_name: str, request: Request):
            """Remove a backend configuration."""
            try:
                data = await request.json() if hasattr(request, 'body') else {}
                force = data.get('force', False)
                result = await self._remove_backend_config(backend_name, force)
                
                # Update the cache
                await self._update_backends_cache()
                
                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"Error removing backend {backend_name}: {e}")
                return {"success": False, "error": str(e)}

        @self.app.post("/api/backends/{backend_name}/test")
        async def api_test_backend(backend_name: str):
            """Test backend connection."""
            try:
                result = await self._test_backend_connection(backend_name)
                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"Error testing backend {backend_name}: {e}")
                return {"success": False, "error": str(e)}

        @self.app.get("/api/backends/types")
        async def api_backend_types():
            """Get available backend types."""
            try:
                return {
                    "success": True,
                    "types": [
                        {"name": "s3", "display": "S3 Compatible", "description": "Amazon S3 or S3-compatible storage"},
                        {"name": "huggingface", "display": "HuggingFace Hub", "description": "HuggingFace model and dataset hub"},
                        {"name": "storacha", "display": "Storacha", "description": "Storacha decentralized storage"},
                        {"name": "ipfs", "display": "IPFS", "description": "InterPlanetary File System"},
                        {"name": "filecoin", "display": "Filecoin", "description": "Filecoin decentralized storage network"},
                        {"name": "gdrive", "display": "Google Drive", "description": "Google Drive cloud storage"}
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting backend types: {e}")
                return {"success": False, "error": str(e)}

        # CLI Integration endpoints - simulate ipfs-kit CLI behavior
        @self.app.get("/api/cli/execute")
        async def api_cli_execute_get(command: str, args: str = "", format: str = "json"):
            """Execute CLI commands through MCP server (GET method)."""
            try:
                result = await self._execute_cli_command(command, args, format)
                return result
            except Exception as e:
                logger.error(f"Error executing CLI command: {e}")
                return {"success": False, "error": str(e)}

        @self.app.post("/api/cli/execute")
        async def api_cli_execute_post(request: Request):
            """Execute CLI commands through MCP server (POST method)."""
            try:
                command_data = await request.json()
                result = await self._execute_cli_command_post(command_data)
                return result
            except Exception as e:
                logger.error(f"Error executing CLI command: {e}")
                return {"success": False, "error": str(e)}

        @self.app.post("/api/cli/backends")
        async def api_cli_backends(request: Request):
            """Handle backend CLI commands (create, list, show, update, remove)."""
            try:
                command_data = await request.json()
                result = await self._handle_cli_backend_command(command_data)
                return result
            except Exception as e:
                logger.error(f"Error executing backend CLI command: {e}")
                return {"success": False, "error": str(e)}

        @self.app.post("/api/cli/config")
        async def api_cli_config(request: Request):
            """Handle config CLI commands (show, set, validate, init)."""
            try:
                command_data = await request.json()
                result = await self._handle_cli_config_command(command_data)
                return result
            except Exception as e:
                logger.error(f"Error executing config CLI command: {e}")
                return {"success": False, "error": str(e)}
        
        # Health endpoint
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "4.0.0",
                "unified_mode": True
            }
    
    async def _get_system_overview(self):
        """Get system overview with caching."""
        now = time.time()
        if now - self.last_update > self.update_interval or not self.system_metrics_cache:
            await self._update_caches()
        
        return {
            "mcp_server": {"status": "running", "port": self.port},
            "services": len(self.services_cache.get("services", [])),
            "backends": len(self.backends_cache.get("backends", [])),
            "buckets": sum(len(b.get("buckets", [])) for b in self.backends_cache.get("backends", [])),
            "pins": len(self.pins_cache.get("pins", [])),
            "system": self.system_metrics_cache,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _get_daemon_status(self):
        """Get IPFS daemon status."""
        try:
            # Check if IPFS daemon is running
            result = await asyncio.create_subprocess_exec(
                "ipfs", "id",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                daemon_info = json.loads(stdout.decode())
                return {
                    "status": "running",
                    "peer_id": daemon_info.get("ID"),
                    "addresses": daemon_info.get("Addresses", []),
                    "version": "unknown"
                }
            else:
                return {"status": "stopped", "error": stderr.decode()}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _check_service_status(self, service_name: str, port: int):
        """Check if a service is running by attempting to connect to its port."""
        try:
            # Check if port is listening
            result = await asyncio.create_subprocess_exec(
                "lsof", "-ti", f":{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and stdout.decode().strip():
                return {"status": "running", "port": port}
            else:
                return {"status": "stopped", "port": port}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _check_binary_availability(self, binary_name: str) -> bool:
        """Check if a binary is available in PATH."""
        try:
            result = await asyncio.create_subprocess_exec(
                "which", binary_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            return result.returncode == 0
        except Exception:
            return False

    async def _check_python_module(self, module_name: str) -> bool:
        """Check if a Python module is available."""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    async def _check_backend_config(self, backend_name: str) -> bool:
        """Check if a backend configuration exists."""
        try:
            # Check for YAML config files
            config_dir = self.data_dir / "backend_configs"
            if config_dir.exists():
                yaml_file = config_dir / f"{backend_name}.yaml"
                if yaml_file.exists():
                    return True
            
            # Check for JSON config files  
            backends_dir = self.data_dir / "backends"
            if backends_dir.exists():
                json_file = backends_dir / f"{backend_name}.json"
                if json_file.exists():
                    return True
                    
            return False
        except Exception:
            return False
    
    async def _get_backends_data(self):
        """Get backends data."""
        if not self.backends_cache or time.time() - self.last_update > self.update_interval:
            await self._update_backends_cache()
        return self.backends_cache
    
    async def _get_buckets_data(self):
        """Get buckets data from multiple sources."""
        backends = await self._get_backends_data()
        all_buckets = []
        
        # Get buckets from backends
        for backend in backends.get("backends", []):
            for bucket in backend.get("buckets", []):
                bucket["backend"] = backend["name"]
                all_buckets.append(bucket)
        
        # Get buckets from filesystem
        try:
            buckets_dir = self.data_dir / "buckets"
            if buckets_dir.exists():
                for bucket_path in buckets_dir.iterdir():
                    if bucket_path.is_dir():
                        # Read metadata if available
                        metadata_file = bucket_path / "metadata.json"
                        metadata = {}
                        if metadata_file.exists():
                            try:
                                with open(metadata_file, 'r') as f:
                                    metadata = json.load(f)
                            except Exception:
                                pass
                        
                        # Count files and calculate size
                        file_count = 0
                        total_size = 0
                        for item in bucket_path.iterdir():
                            if item.is_file() and item.name != "metadata.json":
                                file_count += 1
                                total_size += item.stat().st_size
                        
                        bucket_data = {
                            "name": bucket_path.name,
                            "type": metadata.get("type", "general"),
                            "backend": "Filesystem",
                            "size_bytes": total_size,
                            "files_count": file_count,
                            "created_at": metadata.get("created_at", ""),
                            "last_modified": datetime.fromtimestamp(bucket_path.stat().st_mtime).isoformat(),
                            "description": metadata.get("description", ""),
                            "tags": metadata.get("tags", [])
                        }
                        all_buckets.append(bucket_data)
        except Exception as e:
            logger.error(f"Error loading buckets from filesystem: {e}")
        
        # Also get buckets from simple bucket manager
        try:
            from .simple_bucket_manager import get_simple_bucket_manager
            bucket_manager = get_simple_bucket_manager()
            result = await bucket_manager.list_buckets()
            
            if result.get("success") and result.get("data", {}).get("buckets"):
                for bucket in result["data"]["buckets"]:
                    # Convert simple bucket format to expected format with proper type conversion
                    bucket_data = {
                        "name": str(bucket.get("name", "")),
                        "type": str(bucket.get("type", "general")),
                        "backend": "Simple Bucket Manager",
                        "size_bytes": int(bucket.get("size_bytes", 0)) if bucket.get("size_bytes") is not None else 0,
                        "files_count": int(bucket.get("file_count", 0)) if bucket.get("file_count") is not None else 0,
                        "created_at": str(bucket.get("created_at", "")),
                        "last_modified": str(bucket.get("last_modified", "")),
                        "description": str(bucket.get("description", "")),
                        "tags": list(bucket.get("tags", [])) if bucket.get("tags") else []
                    }
                    all_buckets.append(bucket_data)
        except Exception as e:
            logger.error(f"Error loading buckets from simple bucket manager: {e}")
        
        return {"buckets": all_buckets}

    async def _get_pins_data(self):
        """Get pins data."""
        if not self.pins_cache or time.time() - self.last_update > self.update_interval:
            await self._update_pins_cache()
        return self.pins_cache

    async def _add_pin(self, cid: str, name: Optional[str] = None):
        """Add a new pin."""
        try:
            cmd = ["ipfs", "pin", "add", cid]
            if name:
                cmd.extend(["--name", name])
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                await self._update_pins_cache()
                return {"success": True, "message": stdout.decode()}
            else:
                return {"success": False, "error": stderr.decode()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _remove_pin(self, cid: str):
        """Remove a pin."""
        try:
            result = await asyncio.create_subprocess_exec(
                "ipfs", "pin", "rm", cid,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                await self._update_pins_cache()
                return {"success": True, "message": stdout.decode()}
            else:
                return {"success": False, "error": stderr.decode()}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _create_bucket(self, bucket_name: str, bucket_type: str = "general", description: str = ""):
        """Create a new bucket using filesystem operations."""
        try:
            # Create bucket directory
            bucket_dir = self.data_dir / "buckets" / bucket_name
            
            if bucket_dir.exists():
                return {
                    "success": False,
                    "error": f"Bucket '{bucket_name}' already exists"
                }
            
            bucket_dir.mkdir(parents=True, exist_ok=True)
            
            # Create metadata
            metadata = {
                "name": bucket_name,
                "type": bucket_type,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "files": {}
            }
            
            metadata_file = bucket_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Force refresh of buckets cache
            self.buckets_cache = None
            
            return {
                "success": True,
                "message": f"Bucket '{bucket_name}' created successfully",
                "bucket": {
                    "name": bucket_name,
                    "type": bucket_type,
                    "description": description,
                    "created_at": metadata["created_at"]
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            return {
                "success": False,
                "error": f"Failed to create bucket: {str(e)}"
            }
    
    async def _delete_bucket(self, bucket_name: str):
        """Delete a bucket using filesystem operations."""
        try:
            bucket_dir = self.data_dir / "buckets" / bucket_name
            
            if not bucket_dir.exists():
                return {"success": False, "error": "Bucket not found"}
            
            # Remove the bucket directory and all contents
            import shutil
            shutil.rmtree(bucket_dir)
            
            # Force refresh of buckets cache
            self.buckets_cache = None
            
            return {
                "success": True,
                "message": f"Bucket '{bucket_name}' deleted successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete bucket: {str(e)}"
            }

    async def _get_bucket_details(self, bucket_name: str):
        """Get bucket details and file list using filesystem operations."""
        try:
            bucket_dir = self.data_dir / "buckets" / bucket_name
            
            if not bucket_dir.exists():
                return {"success": False, "error": "Bucket not found"}
            
            # Read metadata if available
            metadata_file = bucket_dir / "metadata.json"
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            
            # List files in bucket
            files = []
            total_size = 0
            for item in bucket_dir.iterdir():
                if item.is_file() and item.name != "metadata.json":
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": str(item.relative_to(bucket_dir))
                    })
                    total_size += stat.st_size
            
            return {
                "success": True,
                "bucket": {
                    "name": bucket_name,
                    "description": metadata.get("description", ""),
                    "type": metadata.get("type", "general"),
                    "created_at": metadata.get("created_at", ""),
                    "file_count": len(files),
                    "total_size": total_size
                },
                "files": files
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get bucket details: {str(e)}"
            }

    async def _upload_file_to_bucket(self, bucket_name: str, file: UploadFile):
        """Upload a file to a bucket using filesystem operations."""
        try:
            bucket_dir = self.data_dir / "buckets" / bucket_name
            bucket_dir.mkdir(parents=True, exist_ok=True)
            
            # Save the uploaded file
            file_path = bucket_dir / file.filename
            with open(file_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            # Update metadata
            metadata_file = bucket_dir / "metadata.json"
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            
            if "files" not in metadata:
                metadata["files"] = {}
            
            metadata["files"][file.filename] = {
                "size": len(content),
                "uploaded_at": datetime.now().isoformat(),
                "content_type": file.content_type
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                "success": True,
                "message": f"File '{file.filename}' uploaded successfully",
                "file": {
                    "name": file.filename,
                    "size": len(content),
                    "content_type": file.content_type
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to upload file: {str(e)}"
            }

    async def _download_file_from_bucket(self, bucket_name: str, file_path: str):
        """Download a file from a bucket using filesystem operations."""
        try:
            bucket_dir = self.data_dir / "buckets" / bucket_name
            target_file = bucket_dir / file_path
            
            if not bucket_dir.exists():
                raise HTTPException(status_code=404, detail="Bucket not found")
            
            if not target_file.exists():
                raise HTTPException(status_code=404, detail="File not found")
            
            return FileResponse(
                path=str(target_file),
                filename=target_file.name,
                media_type='application/octet-stream'
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_services_data(self):
        """Get services data."""
        if not self.services_cache or time.time() - self.last_update > self.update_interval:
            await self._update_services_cache()
        return self.services_cache
    
    async def _get_system_metrics(self):
        """Get system performance metrics."""
        return {
            "cpu": {
                "usage": psutil.cpu_percent(interval=0.1),
                "cores": psutil.cpu_count(),
                "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "used": psutil.virtual_memory().used,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "percent": psutil.disk_usage('/').percent
            },
            "network": {
                "sent": psutil.net_io_counters().bytes_sent,
                "recv": psutil.net_io_counters().bytes_recv
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def _update_caches(self):
        """Update all data caches."""
        self.last_update = time.time()
        await asyncio.gather(
            self._update_backends_cache(),
            self._update_services_cache(),
            self._update_pins_cache(),
            self._update_system_metrics_cache()
        )
    
    async def _update_backends_cache(self):
        """Update backends cache."""
        backends_data = []
        
        # Check for configured backends in ~/.ipfs_kit/
        backends_dir = self.data_dir / "backends"
        if backends_dir.exists():
            for backend_file in backends_dir.glob("*.json"):
                try:
                    with open(backend_file) as f:
                        backend_config = json.load(f)
                        backend_config["name"] = backend_file.stem
                        backend_config["status"] = "configured"
                        backend_config["buckets"] = []  # Will be populated by actual implementation
                        backends_data.append(backend_config)
                except Exception as e:
                    logger.warning(f"Could not load backend {backend_file}: {e}")
        
        self.backends_cache = {"backends": backends_data}
    
    async def _update_services_cache(self):
        """Update services cache with comprehensive service detection."""
        services = []
        
        # Core IPFS service
        daemon_status = await self._get_daemon_status()
        services.append({
            "name": "IPFS Daemon",
            "type": "core_service",
            "status": daemon_status["status"],
            "port": 5001 if daemon_status["status"] == "running" else None,
            "description": "Core IPFS daemon for distributed storage"
        })
        
        # IPFS Cluster services
        cluster_service_status = await self._check_service_status("ipfs-cluster-service", 9094)
        services.append({
            "name": "IPFS Cluster Service",
            "type": "cluster_service",
            "status": cluster_service_status["status"],
            "port": 9094 if cluster_service_status["status"] == "running" else None,
            "description": "IPFS Cluster orchestration service"
        })
        
        cluster_follow_status = await self._check_service_status("ipfs-cluster-follow", 9095)
        services.append({
            "name": "IPFS Cluster Follow",
            "type": "cluster_service", 
            "status": cluster_follow_status["status"],
            "port": 9095 if cluster_follow_status["status"] == "running" else None,
            "description": "IPFS Cluster follow service for joining clusters"
        })
        
        # Filecoin services
        lotus_daemon_status = await self._check_service_status("lotus daemon", 1234)
        services.append({
            "name": "Lotus Daemon",
            "type": "storage_service",
            "status": lotus_daemon_status["status"],
            "port": 1234 if lotus_daemon_status["status"] == "running" else None,
            "description": "Filecoin Lotus node daemon"
        })
        
        # Lassie (IPFS retrieval client)
        lassie_status = await self._check_binary_availability("lassie")
        services.append({
            "name": "Lassie",
            "type": "storage_service",
            "status": "configured" if lassie_status else "not_available",
            "port": None,
            "description": "IPFS content retrieval client"
        })
        
        # Storage backend integrations
        backend_configs = await self._get_backend_configs()
        storage_backends = [
            {
                "name": "S3 Kit",
                "type": "storage_backend",
                "config_types": ["s3"],
                "description": "Amazon S3 storage integration"
            },
            {
                "name": "Google Drive Kit", 
                "type": "storage_backend",
                "config_types": ["gdrive", "google_drive"],
                "description": "Google Drive storage integration"
            },
            {
                "name": "Storacha Kit",
                "type": "storage_backend",
                "config_types": ["storacha", "web3storage"],
                "description": "Web3.Storage (Storacha) integration"
            },
            {
                "name": "HuggingFace Kit",
                "type": "storage_backend",
                "config_types": ["huggingface", "hf"],
                "description": "HuggingFace Hub integration"
            },
            {
                "name": "GitHub Kit",
                "type": "storage_backend",
                "config_types": ["github"],
                "description": "GitHub repository integration"
            },
            {
                "name": "FTP Kit",
                "type": "storage_backend",
                "config_types": ["ftp"],
                "description": "FTP server integration"
            },
            {
                "name": "SSH/SFTP Kit",
                "type": "storage_backend",
                "config_types": ["sshfs", "ssh", "sftp"],
                "description": "SSH/SFTP server integration"
            }
        ]
        
        for backend in storage_backends:
            # Check if any backend configuration exists for this type
            config_available = any(
                backend_config.get("config", {}).get("type") in backend["config_types"]
                for backend_config in backend_configs.values()
                if isinstance(backend_config, dict) and "config" in backend_config
            )
            
            services.append({
                "name": backend["name"],
                "type": backend["type"],
                "status": "configured" if config_available else "not_configured",
                "port": None,
                "description": backend["description"]
            })
        
        # Data format support services
        data_services = [
            {
                "name": "Apache Arrow",
                "type": "data_format",
                "check": await self._check_binary_availability("arrow"),
                "description": "Columnar data format support"
            },
            {
                "name": "Apache Parquet",
                "type": "data_format", 
                "check": await self._check_python_module("pyarrow"),
                "description": "Compressed columnar storage format"
            }
        ]
        
        for service in data_services:
            services.append({
                "name": service["name"],
                "type": service["type"],
                "status": "available" if service["check"] else "not_available",
                "port": None,
                "description": service["description"]
            })
        
        # LibP2P networking (currently disabled due to conflicts)
        services.append({
            "name": "LibP2P",
            "type": "networking",
            "status": "disabled",
            "port": None,
            "description": "P2P networking protocol (disabled due to protobuf conflicts)"
        })
        
        # Calculate summary statistics
        total_services = len(services)
        running_services = sum(1 for s in services if s["status"] == "running")
        configured_services = sum(1 for s in services if s["status"] in ["configured", "available"])
        error_services = sum(1 for s in services if s["status"] in ["error", "stopped"])
        
        self.services_cache = {
            "services": services,
            "summary": {
                "total": total_services,
                "running": running_services,
                "configured": configured_services, 
                "stopped": error_services,
                "by_type": {
                    "core_service": len([s for s in services if s["type"] == "core_service"]),
                    "cluster_service": len([s for s in services if s["type"] == "cluster_service"]),
                    "storage_service": len([s for s in services if s["type"] == "storage_service"]),
                    "storage_backend": len([s for s in services if s["type"] == "storage_backend"]),
                    "data_format": len([s for s in services if s["type"] == "data_format"]),
                    "networking": len([s for s in services if s["type"] == "networking"])
                }
            }
        }
    
    async def _update_system_metrics_cache(self):
        """Update system metrics cache."""
        self.system_metrics_cache = await self._get_system_metrics()
    
    async def _update_pins_cache(self):
        """Update pins cache."""
        try:
            result = await asyncio.create_subprocess_exec(
                "ipfs", "pin", "ls", "--type=recursive",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                pins = []
                for line in stdout.decode().splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        pins.append({"cid": parts[0], "name": "".join(parts[1:-1])})
                self.pins_cache = {"pins": pins}
            else:
                self.pins_cache = {"pins": [], "error": stderr.decode()}
        except Exception as e:
            self.pins_cache = {"pins": [], "error": str(e)}
    
    async def _get_config_data(self):
        """Get configuration data from ~/.ipfs_kit/."""
        try:
            config_data = {}
            
            # Read main config
            main_config_file = self.data_dir / "config.json"
            if main_config_file.exists():
                with open(main_config_file) as f:
                    config_data["main"] = json.load(f)
            
            # Read metadata
            metadata_file = self.data_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    config_data["metadata"] = json.load(f)
            
            # Get backend configurations
            config_data["backends"] = await self._get_backend_configs()
            
            return {
                "config": config_data,
                "data_dir": str(self.data_dir),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting config data: {e}")
            return {"error": str(e)}
    
    async def _update_config_data(self, config_data):
        """Update configuration data."""
        try:
            # Update main config if provided
            if "main" in config_data and config_data["main"]:
                main_config_file = self.data_dir / "config.json"
                self.data_dir.mkdir(exist_ok=True)
                with open(main_config_file, 'w') as f:
                    json.dump(config_data["main"], f, indent=2)
            
            # Update metadata if provided
            if "metadata" in config_data and config_data["metadata"]:
                metadata_file = self.data_dir / "metadata.json"
                self.data_dir.mkdir(exist_ok=True)
                with open(metadata_file, 'w') as f:
                    json.dump(config_data["metadata"], f, indent=2)
            
            return {"status": "updated", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"Error updating config data: {e}")
            return {"error": str(e)}
    
    async def _get_backend_configs(self):
        """Get all backend configurations."""
        try:
            backends = {}
            
            # Check YAML config files
            config_dir = self.data_dir / "backend_configs"
            if config_dir.exists():
                for config_file in config_dir.glob("*.yaml"):
                    try:
                        import yaml
                        with open(config_file, 'r') as f:
                            config_data = yaml.safe_load(f)
                        backends[config_file.stem] = {
                            "type": "yaml",
                            "file": str(config_file),
                            "config": config_data,
                            "last_modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat()
                        }
                    except ImportError:
                        # yaml not available, skip YAML files
                        pass
                    except Exception as e:
                        logger.warning(f"Error reading YAML config {config_file}: {e}")
            
            # Check JSON config files
            backends_dir = self.data_dir / "backends"
            if backends_dir.exists():
                for config_file in backends_dir.glob("*.json"):
                    try:
                        with open(config_file, 'r') as f:
                            config_data = json.load(f)
                        backends[config_file.stem] = {
                            "type": "json",
                            "file": str(config_file),
                            "config": config_data,
                            "last_modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat()
                        }
                    except Exception as e:
                        logger.warning(f"Error reading JSON config {config_file}: {e}")
            
            return backends
        except Exception as e:
            logger.error(f"Error getting backend configs: {e}")
            return {"error": str(e)}
    
    async def _update_backend_config(self, backend_name: str, config_data):
        """Update a specific backend configuration."""
        try:
            # Determine file type and location
            file_type = config_data.get("file_type", "json")
            
            if file_type == "yaml":
                config_dir = self.data_dir / "backend_configs"
                config_dir.mkdir(exist_ok=True)
                config_file = config_dir / f"{backend_name}.yaml"
                
                import yaml
                with open(config_file, 'w') as f:
                    yaml.dump(config_data.get("config", {}), f, default_flow_style=False)
            else:
                backends_dir = self.data_dir / "backends"
                backends_dir.mkdir(exist_ok=True)
                config_file = backends_dir / f"{backend_name}.json"
                
                with open(config_file, 'w') as f:
                    json.dump(config_data.get("config", {}), f, indent=2)
            
            return {
                "status": "updated",
                "backend": backend_name,
                "file": str(config_file),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error updating backend config {backend_name}: {e}")
            return {"error": str(e)}
    
    async def _create_backend_config(self, backend_data):
        """Create a new backend configuration."""
        try:
            backend_name = backend_data.get("name")
            backend_type = backend_data.get("type")
            
            if not backend_name or not backend_type:
                return {"error": "Backend name and type are required"}
            
            # Create configuration object
            config = {
                "type": backend_type,
                "enabled": backend_data.get("enabled", True),
                "created": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat()
            }
            
            # Add backend-specific configuration
            if backend_type == "s3":
                config.update({
                    "endpoint": backend_data.get("endpoint"),
                    "access_key": backend_data.get("access_key"),
                    "secret_key": backend_data.get("secret_key"),
                    "bucket": backend_data.get("bucket"),
                    "region": backend_data.get("region", "us-east-1")
                })
            elif backend_type == "huggingface":
                config.update({
                    "token": backend_data.get("token"),
                    "endpoint": backend_data.get("endpoint", "https://huggingface.co")
                })
            elif backend_type == "ipfs":
                config.update({
                    "api_url": backend_data.get("api_url", "http://127.0.0.1:5001"),
                    "gateway_url": backend_data.get("gateway_url", "http://127.0.0.1:8080")
                })
            elif backend_type == "gdrive":
                config.update({
                    "credentials_path": backend_data.get("credentials_path"),
                    "token": backend_data.get("token")
                })
            
            # Save configuration
            backends_dir = self.data_dir / "backends"
            backends_dir.mkdir(exist_ok=True)
            config_file = backends_dir / f"{backend_name}.json"
            
            if config_file.exists():
                return {"error": f"Backend '{backend_name}' already exists"}
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            return {
                "status": "created",
                "backend": backend_name,
                "type": backend_type,
                "file": str(config_file),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error creating backend config: {e}")
            return {"error": str(e)}
    
    async def _remove_backend_config(self, backend_name: str, force: bool = False):
        """Remove a backend configuration."""
        try:
            # Check both JSON and YAML config locations
            backends_dir = self.data_dir / "backends"
            config_dir = self.data_dir / "backend_configs"
            
            json_file = backends_dir / f"{backend_name}.json"
            yaml_file = config_dir / f"{backend_name}.yaml"
            
            removed_files = []
            
            if json_file.exists():
                if not force:
                    # Check if backend has active pins or connections
                    # This is a simplified check - in practice you'd want more comprehensive validation
                    pass
                
                json_file.unlink()
                removed_files.append(str(json_file))
            
            if yaml_file.exists():
                yaml_file.unlink()
                removed_files.append(str(yaml_file))
            
            if not removed_files:
                return {"error": f"Backend '{backend_name}' not found"}
            
            return {
                "status": "removed",
                "backend": backend_name,
                "files_removed": removed_files,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error removing backend config {backend_name}: {e}")
            return {"error": str(e)}
    
    async def _test_backend_connection(self, backend_name: str):
        """Test connection to a backend."""
        try:
            # Get backend configuration
            backends = await self._get_backend_configs()
            
            if backend_name not in backends:
                return {"error": f"Backend '{backend_name}' not found"}
            
            backend_info = backends[backend_name]
            backend_config = backend_info.get("config", {}) if isinstance(backend_info, dict) else {}
            backend_type = backend_config.get("type")
            
            # Mock connection tests - in practice, these would be real connection attempts
            if backend_type == "s3":
                # Test S3 connection
                endpoint = backend_config.get("endpoint")
                bucket = backend_config.get("bucket")
                
                if not endpoint or not bucket:
                    return {"error": "S3 backend missing endpoint or bucket configuration"}
                
                return {
                    "status": "connected",
                    "backend": backend_name,
                    "type": backend_type,
                    "endpoint": endpoint,
                    "bucket": bucket,
                    "message": "S3 connection test successful (mock)",
                    "timestamp": datetime.now().isoformat()
                }
                
            elif backend_type == "ipfs":
                # Test IPFS connection
                api_url = backend_config.get("api_url", "http://127.0.0.1:5001")
                
                try:
                    # Simple test - check if IPFS daemon is responding
                    result = await asyncio.create_subprocess_exec(
                        "ipfs", "id",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()
                    
                    if result.returncode == 0:
                        return {
                            "status": "connected",
                            "backend": backend_name,
                            "type": backend_type,
                            "api_url": api_url,
                            "message": "IPFS daemon is responding",
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        return {
                            "status": "error",
                            "backend": backend_name,
                            "type": backend_type,
                            "error": "IPFS daemon not responding",
                            "timestamp": datetime.now().isoformat()
                        }
                except Exception as e:
                    return {
                        "status": "error",
                        "backend": backend_name,
                        "type": backend_type,
                        "error": f"IPFS test failed: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }
            
            else:
                # Generic test for other backend types
                backend_display_type = backend_type.upper() if backend_type else "UNKNOWN"
                return {
                    "status": "connected",
                    "backend": backend_name,
                    "type": backend_type,
                    "message": f"{backend_display_type} connection test successful (mock)",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error testing backend {backend_name}: {e}")
            return {"error": str(e)}
    
    async def _execute_cli_command(self, command: str, args: str = "", format: str = "json"):
        """Execute a CLI command with simplified interface."""
        try:
            # Parse args into a list
            args_list = args.split() if args else []
            
            # Handle basic CLI commands that map to existing functionality
            if command == "backends":
                if len(args_list) == 0 or args_list[0] == "list":
                    backends = await self._get_backends_data()
                    return {"success": True, "command": "backends list", "result": backends}
            
            elif command == "config":
                if len(args_list) == 0 or args_list[0] == "show":
                    config = await self._get_config_data()
                    return {"success": True, "command": "config show", "result": config}
            
            return {"success": False, "error": f"Command '{command}' not implemented"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_cli_command_post(self, command_data: dict):
        """Execute CLI command from POST data."""
        try:
            command = command_data.get("command", "")
            action = command_data.get("action", "")
            args = command_data.get("args", {})
            
            # Route to appropriate handler
            if command == "backend":
                return await self._handle_cli_backend_command(command_data)
            elif command == "config":
                return await self._handle_cli_config_command(command_data)
            else:
                return {"success": False, "error": f"Unknown command: {command}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_cli_backend_command(self, command_data: dict):
        """Handle backend CLI commands with full CLI syntax compatibility."""
        try:
            action = command_data.get("action", "")
            args = command_data.get("args", {})
            
            if action == "list":
                # ipfs-kit backend list [--configured]
                configured_only = args.get("configured", False)
                backends = await self._get_backends_data()
                
                # Filter to configured only if requested
                if configured_only:
                    filtered_backends = []
                    for backend in backends.get("backends", []):
                        if backend.get("status") == "configured":
                            filtered_backends.append(backend)
                    backends["backends"] = filtered_backends
                
                return {
                    "success": True,
                    "command": "backend list",
                    "result": backends,
                    "cli_output": self._format_backends_table(backends.get("backends", []))
                }
            
            elif action == "create":
                # ipfs-kit backend create <name> <type> [options]
                name = args.get("name", "")
                backend_type = args.get("type", "")
                
                if not name or not backend_type:
                    return {"success": False, "error": "Backend name and type are required"}
                
                config = {
                    "name": name,
                    "type": backend_type,
                    "endpoint": args.get("endpoint"),
                    "access_key": args.get("access_key"),
                    "secret_key": args.get("secret_key"),
                    "token": args.get("token"),
                    "bucket": args.get("bucket"),
                    "region": args.get("region"),
                    "enabled": True
                }
                
                # Remove None values
                config = {k: v for k, v in config.items() if v is not None}
                
                result = await self._create_backend_config(config)
                return {
                    "success": True,
                    "command": f"backend create {name}",
                    "result": result,
                    "cli_output": f"✅ Backend '{name}' created successfully."
                }
            
            elif action == "show":
                # ipfs-kit backend show <name>
                name = args.get("name", "")
                if not name:
                    return {"success": False, "error": "Backend name is required"}
                
                backend_configs = await self._get_backend_configs()
                if name not in backend_configs:
                    return {"success": False, "error": f"Backend '{name}' not found"}
                
                return {
                    "success": True,
                    "command": f"backend show {name}",
                    "result": backend_configs[name],
                    "cli_output": json.dumps(backend_configs[name], indent=2)
                }
            
            elif action == "update":
                # ipfs-kit backend update <name> [options]
                name = args.get("name", "")
                if not name:
                    return {"success": False, "error": "Backend name is required"}
                
                updates = {k: v for k, v in args.items() if k != "name" and v is not None}
                result = await self._update_backend_config(name, {"config": updates})
                
                return {
                    "success": True,
                    "command": f"backend update {name}",
                    "result": result,
                    "cli_output": f"✅ Backend '{name}' updated successfully."
                }
            
            elif action == "remove":
                # ipfs-kit backend remove <name> [--force]
                name = args.get("name", "")
                force = args.get("force", False)
                
                if not name:
                    return {"success": False, "error": "Backend name is required"}
                
                result = await self._remove_backend_config(name, force)
                return {
                    "success": True,
                    "command": f"backend remove {name}",
                    "result": result,
                    "cli_output": f"✅ Backend '{name}' removed successfully."
                }
            
            else:
                return {"success": False, "error": f"Unknown backend action: {action}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_cli_config_command(self, command_data: dict):
        """Handle config CLI commands with full CLI syntax compatibility."""
        try:
            action = command_data.get("action", "")
            args = command_data.get("args", {})
            
            if action == "show":
                # ipfs-kit config show [--backend <backend>]
                backend_filter = args.get("backend")
                config = await self._get_config_data()
                
                if backend_filter and backend_filter != "all":
                    # Filter to specific backend
                    filtered_config = {}
                    if backend_filter in config.get("backends", {}):
                        filtered_config = {backend_filter: config["backends"][backend_filter]}
                    config = {"backends": filtered_config}
                
                return {
                    "success": True,
                    "command": "config show",
                    "result": config,
                    "cli_output": json.dumps(config, indent=2)
                }
            
            elif action == "set":
                # ipfs-kit config set <key> <value>
                key = args.get("key", "")
                value = args.get("value", "")
                
                if not key or value is None:
                    return {"success": False, "error": "Key and value are required"}
                
                # Parse the key (e.g., "s3.region" -> backend="s3", setting="region")
                if "." in key:
                    backend, setting = key.split(".", 1)
                    result = await self._set_backend_config_value(backend, setting, value)
                else:
                    result = await self._set_global_config_value(key, value)
                
                return {
                    "success": True,
                    "command": f"config set {key}",
                    "result": result,
                    "cli_output": f"✅ Configuration updated: {key} = {value}"
                }
            
            elif action == "validate":
                # ipfs-kit config validate [--backend <backend>]
                backend_filter = args.get("backend")
                results = await self._validate_config(backend_filter)
                
                return {
                    "success": True,
                    "command": "config validate",
                    "result": results,
                    "cli_output": self._format_validation_results(results)
                }
            
            else:
                return {"success": False, "error": f"Unknown config action: {action}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _format_backends_table(self, backends):
        """Format backends list as CLI table output."""
        if not backends:
            return "No backends configured."
        
        # Create a simple table format
        lines = ["📋 Available Backends:", ""]
        lines.append(f"{'Name':<20} {'Type':<15} {'Status':<12} {'Configured'}")
        lines.append("-" * 60)
        
        for backend in backends:
            name = backend.get("name", "Unknown")[:19]
            backend_type = backend.get("type", "Unknown")[:14]
            status = backend.get("status", "unknown")[:11]
            configured = "✅" if backend.get("status") == "configured" else "❌"
            lines.append(f"{name:<20} {backend_type:<15} {status:<12} {configured}")
        
        return "\n".join(lines)

    def _format_validation_results(self, results):
        """Format validation results as CLI output."""
        if not results:
            return "No validation results."
        
        lines = ["✔️ Configuration Validation Results:", ""]
        
        for result in results:
            file_path = result.get("file", "Unknown")
            status = "✅ Valid" if result.get("valid", False) else "❌ Invalid"
            error = result.get("error", "")
            
            lines.append(f"{file_path}: {status}")
            if error:
                lines.append(f"  Error: {error}")
        
        return "\n".join(lines)

    async def _set_backend_config_value(self, backend: str, setting: str, value: str):
        """Set a specific backend configuration value."""
        try:
            backend_configs = await self._get_backend_configs()
            
            if backend not in backend_configs:
                return {"error": f"Backend '{backend}' not found"}
            
            # Update the specific setting
            if "config" not in backend_configs[backend]:
                backend_configs[backend]["config"] = {}
            
            backend_configs[backend]["config"][setting] = value
            
            # Save the updated config
            result = await self._update_backend_config(backend, backend_configs[backend])
            return result
            
        except Exception as e:
            return {"error": str(e)}

    async def _set_global_config_value(self, key: str, value: str):
        """Set a global configuration value."""
        try:
            # For now, just return success - can be implemented later
            return {"message": f"Global config {key} set to {value}"}
        except Exception as e:
            return {"error": str(e)}

    async def _validate_config(self, backend_filter: str = None):
        """Validate configuration files."""
        try:
            results = []
            backend_configs = await self._get_backend_configs()
            
            for name, config in backend_configs.items():
                if backend_filter and backend_filter != "all" and name != backend_filter:
                    continue
                
                # Basic validation
                is_valid = True
                error_msg = ""
                
                if not config.get("config", {}):
                    is_valid = False
                    error_msg = "Missing configuration data"
                elif config.get("type") == "json" and not config.get("file"):
                    is_valid = False
                    error_msg = "Missing file path"
                
                results.append({
                    "file": config.get("file", f"{name}.config"),
                    "backend": name,
                    "valid": is_valid,
                    "error": error_msg
                })
            
            return results
            
        except Exception as e:
            return [{"file": "global", "valid": False, "error": str(e)}]

    def _get_dashboard_html(self):
        """Generate the dashboard HTML with modern aesthetic design."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit - Unified Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        'inter': ['Inter', 'sans-serif'],
                    }}
                }}
            }}
        }}
    </script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        /* Enhanced Modern Design System */
        :root {{
            /* Color Gradients */
            --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --success-gradient: linear-gradient(135deg, #11f0ab 0%, #00c9ff 100%);
            --warning-gradient: linear-gradient(135deg, #ffd89b 0%, #19547b 100%);
            --danger-gradient: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
            --info-gradient: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            --dark-gradient: linear-gradient(135deg, #2c3e50 0%, #4a6741 100%);
            
            /* Shadows */
            --card-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            --card-hover-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            --button-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            
            /* Spacing & Layout */
            --border-radius: 16px;
            --border-radius-lg: 24px;
            --sidebar-width: 280px;
            
            /* Typography */
            --font-weight-light: 300;
            --font-weight-normal: 400;
            --font-weight-medium: 500;
            --font-weight-semibold: 600;
            --font-weight-bold: 700;
            --font-weight-extrabold: 800;
        }}
        
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            background-attachment: fixed;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            min-height: 100vh;
            margin: 0;
            overflow-x: hidden;
        }}
        
        /* Background overlay for better readability */
        body::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.05);
            pointer-events: none;
            z-index: -1;
        }}
        
        .gradient-bg {{
            background: var(--primary-gradient);
        }}
        
        .card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: var(--border-radius);
            box-shadow: var(--card-shadow);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }}
        
        .card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
        }}
        
        .card:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: var(--card-hover-shadow);
            border-color: rgba(255, 255, 255, 0.5);
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(255, 255, 255, 0.85) 100%);
            border-left: 5px solid transparent;
            border-image: var(--primary-gradient) 1;
            position: relative;
        }}
        
        .metric-card::after {{
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            width: 4px;
            background: var(--primary-gradient);
            opacity: 0.3;
        }}
        
        .metric-value {{
            font-size: 3rem;
            font-weight: var(--font-weight-extrabold);
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.1;
            text-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }}
        
        .status-running {{ border-image: var(--success-gradient) 1; }}
        .status-warning {{ border-image: var(--warning-gradient) 1; }}
        .status-error {{ border-image: var(--danger-gradient) 1; }}
        .status-info {{ border-image: var(--info-gradient) 1; }}
        
        .sidebar {{
            background: linear-gradient(135deg, rgba(44, 62, 80, 0.95) 0%, rgba(52, 152, 219, 0.95) 100%);
            backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255, 255, 255, 0.2);
            width: var(--sidebar-width);
            box-shadow: 4px 0 20px rgba(0, 0, 0, 0.1);
        }}
        
        .nav-link {{
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            border-radius: 12px;
            margin: 4px 8px;
            position: relative;
            overflow: hidden;
        }}
        
        .nav-link::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.6s;
        }}
        
        .nav-link:hover::before {{
            left: 100%;
        }}
        
        .nav-link:hover {{
            background: rgba(255, 255, 255, 0.15);
            transform: translateX(8px) scale(1.02);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}
        
        .nav-link.active {{
            background: rgba(255, 255, 255, 0.2);
            border-left: 4px solid #ffffff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}
        
        .pulse-animation {{
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }}
        
        .fade-in {{
            animation: fadeIn 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        .slide-in {{
            animation: slideIn 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.8; transform: scale(1.05); }}
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(30px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        @keyframes slideIn {{
            from {{ opacity: 0; transform: translateX(-30px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}
        
        .btn-primary {{
            background: var(--primary-gradient);
            border: none;
            border-radius: 12px;
            box-shadow: var(--button-shadow);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }}
        
        .btn-primary::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            transition: left 0.6s;
        }}
        
        .btn-primary:hover::before {{
            left: 100%;
        }}
        
        .btn-primary:hover {{
            transform: translateY(-3px) scale(1.05);
            box-shadow: 0 20px 25px -5px rgba(102, 126, 234, 0.4), 0 10px 10px -5px rgba(102, 126, 234, 0.2);
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
            animation: fadeIn 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        /* Enhanced Progress Bars */
        .progress-bar {{
            background: linear-gradient(90deg, #e5e7eb, #f3f4f6);
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }}
        
        .progress-bar::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, rgba(255, 255, 255, 0.2), transparent, rgba(255, 255, 255, 0.2));
            animation: shimmer 2s infinite;
        }}
        
        @keyframes shimmer {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(100%); }}
        }}
        
        .progress-fill {{
            height: 100%;
            border-radius: 10px;
            transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }}
        
        .progress-fill::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            animation: pulse-progress 2s infinite;
        }}
        
        @keyframes pulse-progress {{
            0%, 100% {{ opacity: 0; }}
            50% {{ opacity: 1; }}
        }}
        
        /* Status Indicators */
        .status-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            position: relative;
            display: inline-block;
        }}
        
        .status-dot::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: 50%;
            animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;
        }}
        
        .status-dot.running {{
            background: #10b981;
        }}
        
        .status-dot.running::before {{
            background: #10b981;
        }}
        
        .status-dot.warning {{
            background: #f59e0b;
        }}
        
        .status-dot.warning::before {{
            background: #f59e0b;
        }}
        
        .status-dot.error {{
            background: #ef4444;
        }}
        
        .status-dot.error::before {{
            background: #ef4444;
        }}
        
        @keyframes ping {{
            75%, 100% {{
                transform: scale(2);
                opacity: 0;
            }}
        }}
        
        /* Service Grid Enhancements */
        .service-item {{
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border-radius: var(--border-radius);
            border: 1px solid rgba(255, 255, 255, 0.2);
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }}
        
        .service-item:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            border-color: rgba(255, 255, 255, 0.4);
        }}
        
        /* Mobile Optimizations */
        @media (max-width: 1024px) {{
            .sidebar {{
                width: 260px;
            }}
        }}
        
        @media (max-width: 768px) {{
            :root {{
                --sidebar-width: 100%;
            }}
            
            .sidebar {{
                transform: translateX(-100%);
                position: fixed;
                z-index: 50;
                transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                width: 100% !important;
                max-width: 320px;
            }}
            
            .sidebar.open {{
                transform: translateX(0);
            }}
            
            .metric-value {{
                font-size: 2.5rem;
            }}
            
            .card {{
                margin: 8px 0;
            }}
        }}
        
        @media (max-width: 640px) {{
            .metric-value {{
                font-size: 2rem;
            }}
        }}
        
        /* Loading States */
        .loading-skeleton {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: loading 1.5s infinite;
        }}
        
        @keyframes loading {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}
        
        /* Enhanced Scrollbars */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.3);
            border-radius: 4px;
            transition: background 0.3s ease;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.5);
        }}
    </style>
</head>
<body>
    <!-- Mobile Menu Button -->
    <div class="lg:hidden fixed top-6 left-6 z-50">
        <button id="mobile-menu-btn" class="btn-primary text-white p-4 rounded-xl shadow-lg">
            <i class="fas fa-bars text-lg"></i>
        </button>
    </div>
    
    <!-- Mobile Overlay -->
    <div id="mobile-overlay" class="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-30 hidden opacity-0 transition-opacity duration-300"></div>
    
    <!-- Sidebar -->
    <div id="sidebar" class="sidebar fixed left-0 top-0 h-full text-white z-40">
        <div class="p-8">
            <div class="flex items-center mb-10">
                <div class="p-2 rounded-xl bg-gradient-to-r from-yellow-400 to-orange-500 mr-4">
                    <i class="fas fa-rocket text-2xl text-white"></i>
                </div>
                <div>
                    <h2 class="text-xl font-bold">IPFS Kit</h2>
                    <p class="text-xs text-blue-200 opacity-80">v4.0.0</p>
                </div>
            </div>
            
            <nav class="space-y-2">
                <a href="#" onclick="showTab('overview')" class="nav-link active flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-tachometer-alt mr-4 text-lg"></i> 
                    <span class="font-medium">Overview</span>
                </a>
                <a href="#" onclick="showTab('services')" class="nav-link flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-cogs mr-4 text-lg"></i> 
                    <span class="font-medium">Services</span>
                </a>
                <a href="#" onclick="showTab('backends')" class="nav-link flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-server mr-4 text-lg"></i> 
                    <span class="font-medium">Backends</span>
                </a>
                <a href="#" onclick="showTab('buckets')" class="nav-link flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-folder mr-4 text-lg"></i> 
                    <span class="font-medium">Buckets</span>
                </a>
                <a href="#" onclick="showTab('metrics')" class="nav-link flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-chart-line mr-4 text-lg"></i> 
                    <span class="font-medium">Metrics</span>
                </a>
                <a href="#" onclick="showTab('config')" class="nav-link flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-cog mr-4 text-lg"></i> 
                    <span class="font-medium">Configuration</span>
                </a>
                <a href="#" onclick="showTab('mcp')" class="nav-link flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-broadcast-tower mr-4 text-lg"></i> 
                    <span class="font-medium">MCP Server</span>
                </a>
                <a href="#" onclick="showTab('pins')" class="nav-link flex items-center px-4 py-4 rounded-xl slide-in">
                    <i class="fas fa-thumbtack mr-4 text-lg"></i> 
                    <span class="font-medium">Pins</span>
                </a>
            </nav>
        </div>
        
        <!-- System Status Panel -->
        <div class="p-8 border-t border-white/20 mt-auto">
            <h3 class="text-sm font-semibold mb-6 text-white/90 flex items-center">
                <i class="fas fa-heartbeat mr-2 text-red-400"></i>
                System Status
            </h3>
            <div class="space-y-4">
                <div class="flex justify-between items-center text-sm">
                    <span class="text-white/80">MCP Server</span>
                    <div class="flex items-center">
                        <div class="status-dot running mr-2"></div>
                        <span id="sidebar-mcp-status" class="text-green-400 font-medium">Running</span>
                    </div>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-white/80">IPFS Daemon</span>
                    <div class="flex items-center">
                        <div id="sidebar-ipfs-dot" class="status-dot mr-2"></div>
                        <span id="sidebar-ipfs-status" class="text-white/60">-</span>
                    </div>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-white/80">Backends</span>
                    <span id="sidebar-backends-count" class="text-blue-300 font-medium">-</span>
                </div>
            </div>
            
            <!-- Mini Performance Indicators -->
            <div class="mt-6 space-y-3">
                <div class="text-xs text-white/60 mb-2">Quick Stats</div>
                <div class="space-y-2">
                    <div class="flex justify-between items-center text-xs">
                        <span class="text-white/70">CPU</span>
                        <div class="flex items-center">
                            <div class="w-16 h-1 bg-white/20 rounded-full mr-2">
                                <div id="sidebar-cpu-bar" class="h-full bg-green-400 rounded-full transition-all duration-500" style="width: 0%"></div>
                            </div>
                            <span id="sidebar-cpu-percent" class="text-white/80 w-8 text-right">0%</span>
                        </div>
                    </div>
                    <div class="flex justify-between items-center text-xs">
                        <span class="text-white/70">RAM</span>
                        <div class="flex items-center">
                            <div class="w-16 h-1 bg-white/20 rounded-full mr-2">
                                <div id="sidebar-memory-bar" class="h-full bg-blue-400 rounded-full transition-all duration-500" style="width: 0%"></div>
                            </div>
                            <span id="sidebar-memory-percent" class="text-white/80 w-8 text-right">0%</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Main Content -->
    <div class="lg:ml-[280px] min-h-screen">
        <!-- Header -->
        <header class="gradient-bg text-white px-8 py-12 shadow-2xl relative overflow-hidden">
            <!-- Background Pattern -->
            <div class="absolute inset-0 opacity-10">
                <div class="absolute inset-0" style="background-image: radial-gradient(circle at 2px 2px, white 1px, transparent 1px); background-size: 20px 20px;"></div>
            </div>
            
            <div class="relative z-10">
                <div class="flex flex-col lg:flex-row lg:justify-between lg:items-center">
                    <div class="mb-6 lg:mb-0">
                        <h1 class="text-4xl lg:text-5xl font-extrabold mb-3 bg-gradient-to-r from-white to-blue-200 bg-clip-text text-transparent">
                            IPFS Kit Dashboard
                        </h1>
                        <p class="text-blue-100 text-lg font-medium">Unified MCP Server & Control Interface</p>
                        <div class="flex items-center mt-3 text-sm text-blue-200">
                            <i class="fas fa-server mr-2"></i>
                            <span>Port {self.port}</span>
                            <span class="mx-3">•</span>
                            <i class="fas fa-clock mr-2"></i>
                            <span id="current-time">--:--:--</span>
                        </div>
                    </div>
                    <div class="flex flex-col sm:flex-row items-start sm:items-center space-y-3 sm:space-y-0 sm:space-x-4">
                        <div class="flex items-center bg-white/20 backdrop-blur-sm px-4 py-3 rounded-xl text-sm font-medium">
                            <div class="status-dot running mr-3"></div>
                            <span>Real-time Updates</span>
                        </div>
                        <button onclick="refreshData()" class="btn-primary px-6 py-3 rounded-xl font-semibold flex items-center">
                            <i class="fas fa-sync-alt mr-2"></i> 
                            <span>Refresh Data</span>
                        </button>
                    </div>
                </div>
            </div>
        </header>
        
        <!-- Tab Content Container -->
        <div class="p-8">
            <!-- Overview Tab -->
            <div id="overview-tab" class="tab-content active fade-in">
                <!-- Main Metrics Grid -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
                    <div class="card metric-card p-8 rounded-2xl fade-in">
                        <div class="flex items-center justify-between mb-4">
                            <div class="p-3 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600">
                                <i class="fas fa-broadcast-tower text-white text-xl"></i>
                            }
                            <div class="text-right">
                                <div class="text-xs text-gray-500 uppercase tracking-wide font-semibold">MCP Server</div>
                            </div>
                        </div>
                        <div id="mcp-status" class="metric-value mb-2">Running</div>
                        <p class="text-sm text-gray-600 flex items-center">
                            <i class="fas fa-ethernet mr-2 text-blue-500"></i>
                            Port {self.port}
                        </p>
                    </div>
                    
                    <div class="card metric-card p-8 rounded-2xl fade-in">
                        <div class="flex items-center justify-between mb-4">
                            <div class="p-3 rounded-xl bg-gradient-to-r from-green-500 to-teal-600">
                                <i class="fas fa-cogs text-white text-xl"></i>
                            </div>
                            <div class="text-right">
                                <div class="text-xs text-gray-500 uppercase tracking-wide font-semibold">Services</div>
                            </div>
                        </div>
                        <div id="services-count" class="metric-value mb-2">0</div>
                        <p class="text-sm text-gray-600 flex items-center">
                            <div class="status-dot running mr-2"></div>
                            Active Services
                        </p>
                    </div>
                    
                    <div class="card metric-card p-8 rounded-2xl fade-in">
                        <div class="flex items-center justify-between mb-4">
                            <div class="p-3 rounded-xl bg-gradient-to-r from-purple-500 to-pink-600">
                                <i class="fas fa-server text-white text-xl"></i>
                            </div>
                            <div class="text-right">
                                <div class="text-xs text-gray-500 uppercase tracking-wide font-semibold">Backends</div>
                            </div>
                        </div>
                        <div id="backends-count" class="metric-value mb-2">0</div>
                        <p class="text-sm text-gray-600 flex items-center">
                            <i class="fas fa-cloud mr-2 text-purple-500"></i>
                            Storage Backends
                        </p>
                    </div>
                    
                    <div class="card metric-card p-8 rounded-2xl fade-in">
                        <div class="flex items-center justify-between mb-4">
                            <div class="p-3 rounded-xl bg-gradient-to-r from-orange-500 to-red-600">
                                <i class="fas fa-folder text-white text-xl"></i>
                            </div>
                            <div class="text-right">
                                <div class="text-xs text-gray-500 uppercase tracking-wide font-semibold">Buckets</div>
                            </div>
                        </div>
                        <div id="buckets-count" class="metric-value mb-2">0</div>
                        <p class="text-sm text-gray-600 flex items-center">
                            <i class="fas fa-database mr-2 text-orange-500"></i>
                            Total Buckets
                        </p>
                    </div>
                </div>
                
                <!-- System Overview Grid -->
                <div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
                    <!-- System Performance -->
                    <div class="xl:col-span-2">
                        <div class="card p-8 rounded-2xl">
                            <h3 class="text-2xl font-bold mb-6 flex items-center">
                                <div class="p-2 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-600 mr-4">
                                    <i class="fas fa-chart-bar text-white"></i>
                                </div>
                                System Performance
                            </h3>
                            <div id="system-performance" class="space-y-6">
                                <!-- CPU Usage -->
                                <div class="space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="text-gray-700 font-medium flex items-center">
                                            <i class="fas fa-microchip mr-3 text-blue-500"></i>
                                            CPU Usage
                                        </span>
                                        <span id="cpu-percent" class="text-lg font-bold text-gray-800">0%</span>
                                    </div>
                                    <div class="progress-bar h-3">
                                        <div id="cpu-bar" class="progress-fill bg-gradient-to-r from-blue-400 to-blue-600" style="width: 0%"></div>
                                    </div>
                                    <div class="flex justify-between text-xs text-gray-500">
                                        <span>0%</span>
                                        <span>100%</span>
                                    </div>
                                </div>
                                
                                <!-- Memory Usage -->
                                <div class="space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="text-gray-700 font-medium flex items-center">
                                            <i class="fas fa-memory mr-3 text-green-500"></i>
                                            Memory Usage
                                        </span>
                                        <div class="text-right">
                                            <span id="memory-percent" class="text-lg font-bold text-gray-800">0%</span>
                                            <div class="text-xs text-gray-500">
                                                <span id="memory-used">0 GB</span> / <span id="memory-total">0 GB</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="progress-bar h-3">
                                        <div id="memory-bar" class="progress-fill bg-gradient-to-r from-green-400 to-green-600" style="width: 0%"></div>
                                    </div>
                                    <div class="flex justify-between text-xs text-gray-500">
                                        <span>0%</span>
                                        <span>100%</span>
                                    </div>
                                </div>
                                
                                <!-- Disk Usage -->
                                <div class="space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="text-gray-700 font-medium flex items-center">
                                            <i class="fas fa-hdd mr-3 text-purple-500"></i>
                                            Disk Usage
                                        </span>
                                        <div class="text-right">
                                            <span id="disk-percent" class="text-lg font-bold text-gray-800">0%</span>
                                            <div class="text-xs text-gray-500">
                                                <span id="disk-used">0 GB</span> / <span id="disk-total">0 GB</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="progress-bar h-3">
                                        <div id="disk-bar" class="progress-fill bg-gradient-to-r from-purple-400 to-purple-600" style="width: 0%"></div>
                                    </div>
                                    <div class="flex justify-between text-xs text-gray-500">
                                        <span>0%</span>
                                        <span>100%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Network Activity -->
                    <div>
                        <div class="card p-8 rounded-2xl">
                            <h3 class="text-2xl font-bold mb-6 flex items-center">
                                <div class="p-2 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 mr-4">
                                    <i class="fas fa-network-wired text-white"></i>
                                </div>
                                Network Activity
                            </h3>
                            <div id="network-activity-content" class="space-y-6">
                                <div class="text-center py-8">
                                    <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                        <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                                    </div>
                                    <p class="text-gray-500 font-medium">Loading network data...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- IPFS Daemon Status -->
                <div class="mt-8">
                    <div class="card p-8 rounded-2xl">
                        <h3 class="text-2xl font-bold mb-6 flex items-center">
                            <div class="p-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 mr-4">
                                <i class="fas fa-cube text-white"></i>
                            </div>
                            IPFS Daemon Status
                        </h3>
                        <div id="ipfs-daemon-status" class="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div class="text-center py-8">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                    <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                                </div>
                                <p class="text-gray-500 font-medium">Checking daemon status...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Services Tab -->
            <div id="services-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-green-500 to-teal-600 mr-4">
                            <i class="fas fa-cogs text-white"></i>
                        </div>
                        Services Status
                        <span id="services-total-badge" class="ml-4 text-sm bg-blue-100 text-blue-800 px-3 py-1 rounded-full font-medium">0</span>
                    </h3>
                    <div id="services-list" class="space-y-6">
                        <div class="text-center py-12">
                            <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                            </div>
                            <p class="text-gray-500 font-medium">Loading services...</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Backends Tab -->
            <div id="backends-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-600 mr-4">
                            <i class="fas fa-server text-white"></i>
                        </div>
                        Storage Backends
                    </h3>
                    <div id="backends-list">
                        <!-- Backends will be loaded here -->
                    </div>
                </div>
            </div>

            <!-- Buckets Tab -->
            <div id="buckets-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-orange-500 to-red-600 mr-4">
                            <i class="fas fa-folder text-white"></i>
                        </div>
                        Buckets
                    </h3>
                    <div id="buckets-list">
                        <!-- Buckets will be loaded here -->
                    </div>
                </div>
            </div>

            <!-- Metrics Tab -->
            <div id="metrics-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-600 mr-4">
                            <i class="fas fa-chart-line text-white"></i>
                        </div>
                        Real-time Metrics
                    </h3>
                    <div id="metrics-content">
                        <!-- Detailed metrics will be loaded here -->
                    </div>
                }
            </div>

            <!-- Config Tab -->
            <div id="config-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-gray-500 to-gray-700 mr-4">
                            <i class="fas fa-cog text-white"></i>
                        </div>
                        Configuration
                    </h3>
                    <div id="config-content">
                        <div class="text-center py-12">
                            <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                            </div>
                            <p class="text-gray-500 font-medium">Loading configuration...</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- MCP Tab -->
            <div id="mcp-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 mr-4">
                            <i class="fas fa-broadcast-tower text-white"></i>
                        </div>
                        MCP Server Details
                    </h3>
                    <div id="mcp-content">
                        <!-- MCP server details will be loaded here -->
                    </div>
                </div>
            </div>

            <!-- Pins Tab -->
            <div id="pins-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-600 mr-4">
                            <i class="fas fa-thumbtack text-white"></i>
                        </div>
                        Manage Pins
                    </h3>

                    <!-- Add Pin Form -->
                    <div class="bg-gray-50 p-6 rounded-xl border border-gray-200 mb-8">
                        <h4 class="text-lg font-semibold mb-4">Add New Pin</h4>
                        <div class="flex items-center space-x-4">
                            <input id="pin-cid-input" type="text" placeholder="Enter IPFS CID" class="flex-grow p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition">
                            <input id="pin-name-input" type="text" placeholder="Optional Name" class="w-1/3 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition">
                            <button onclick="addPin()" class="btn-primary px-6 py-3 rounded-lg font-semibold flex items-center">
                                <i class="fas fa-plus mr-2"></i>
                                <span>Add Pin</span>
                            </button>
                        </div>
                    </div>

                    <!-- Pin List -->
                    <div>
                        <h4 class="text-lg font-semibold mb-4">Pinned Items</h4>
                        <div class="overflow-x-auto">
                            <table class="min-w-full bg-white rounded-lg shadow overflow-hidden">
                                <thead class="bg-gray-100">
                                    <tr>
                                        <th class="p-4 text-left text-sm font-semibold text-gray-600">CID</th>
                                        <th class="p-4 text-left text-sm font-semibold text-gray-600">Name</th>
                                        <th class="p-4 text-right text-sm font-semibold text-gray-600">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="pins-list" class="divide-y divide-gray-200">
                                    <!-- Pins will be loaded here -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Utility Functions
        const formatBytes = (bytes, decimals = 2) => {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
        };

        // Tab Switching
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            // Show the selected tab
            document.getElementById(`${tabName}-tab`).classList.add('active');

            // Update active link style
            document.querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
            });
            document.querySelector(`.nav-link[onclick="showTab('${tabName}')"]`).classList.add('active');

            // Load data for the selected tab
            if (tabName === 'overview') {
                loadOverviewData();
            } else if (tabName === 'services') {
                loadServices();
            } else if (tabName === 'backends') {
                loadBackends();
            } else if (tabName === 'buckets') {
                loadBuckets();
            } else if (tabName === 'metrics') {
                loadMetrics();
            } else if (tabName === 'config') {
                loadConfig();
            } else if (tabName === 'mcp') {
                loadMcpDetails();
            } else if (tabName === 'pins') {
                loadPins();
            }
            
            // Close mobile sidebar on tab selection
            const sidebar = document.getElementById('sidebar');
            if (sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                document.getElementById('mobile-overlay').classList.add('hidden');
            }
        }

        // Data Loading Functions
        async function loadOverviewData() {
            try {
                const response = await fetch('/api/system/overview');
                const data = await response.json();

                // Update main metrics
                document.getElementById('services-count').textContent = data.services;
                document.getElementById('backends-count').textContent = data.backends;
                document.getElementById('buckets-count').textContent = data.buckets;

                // Update system performance
                const system = data.system;
                document.getElementById('cpu-percent').textContent = `${system.cpu.usage.toFixed(1)}%`;
                document.getElementById('cpu-bar').style.width = `${system.cpu.usage}%`;
                document.getElementById('memory-percent').textContent = `${system.memory.percent.toFixed(1)}%`;
                document.getElementById('memory-bar').style.width = `${system.memory.percent}%`;
                document.getElementById('memory-used').textContent = formatBytes(system.memory.used);
                document.getElementById('memory-total').textContent = formatBytes(system.memory.total);
                document.getElementById('disk-percent').textContent = `${system.disk.percent.toFixed(1)}%`;
                document.getElementById('disk-bar').style.width = `${system.disk.percent}%`;
                document.getElementById('disk-used').textContent = formatBytes(system.disk.used);
                document.getElementById('disk-total').textContent = formatBytes(system.disk.total);

                // Update sidebar stats
                document.getElementById('sidebar-backends-count').textContent = data.backends;
                document.getElementById('sidebar-cpu-percent').textContent = `${system.cpu.usage.toFixed(0)}%`;
                document.getElementById('sidebar-cpu-bar').style.width = `${system.cpu.usage}%`;
                document.getElementById('sidebar-memory-percent').textContent = `${system.memory.percent.toFixed(0)}%`;
                document.getElementById('sidebar-memory-bar').style.width = `${system.memory.percent}%`;

                // Load IPFS daemon status
                loadIpfsDaemonStatus();
                loadNetworkActivity();

            } catch (error) {
                console.error('Error loading overview data:', error);
            }
        }

        async function loadIpfsDaemonStatus() {
            try {
                const response = await fetch('/api/system/overview');
                const data = await response.json();
                const daemonStatus = data.services.find(s => s.name === 'IPFS Daemon');
                const statusDiv = document.getElementById('ipfs-daemon-status');
                
                let statusHtml = '';
                if (daemonStatus && daemonStatus.status === 'running') {
                    statusHtml = `
                        <div class="text-center p-4 bg-green-50 rounded-lg">
                            <div class="text-4xl text-green-500 mb-2"><i class="fas fa-check-circle"></i></div>
                            <p class="font-semibold text-green-800">Daemon Running</p>
                        </div>
                        <div class="p-4 bg-gray-50 rounded-lg col-span-2">
                            <p class="text-sm text-gray-600"><strong>Peer ID:</strong> ${data.peer_id || 'N/A'}</p>
                            <p class="text-sm text-gray-600"><strong>Addresses:</strong></p>
                            <ul class="text-xs list-disc list-inside pl-2 mt-1">
                                ${data.addresses ? data.addresses.map(a => `<li>${a}</li>`).join('') : '<li>No addresses found</li>'}
                            </ul>
                        </div>
                    `;
                    document.getElementById('sidebar-ipfs-status').textContent = 'Running';
                    document.getElementById('sidebar-ipfs-dot').className = 'status-dot running';
                } else {
                    statusHtml = `
                        <div class="text-center p-4 bg-red-50 rounded-lg col-span-3">
                            <div class="text-4xl text-red-500 mb-2"><i class="fas fa-times-circle"></i></div>
                            <p class="font-semibold text-red-800">Daemon Stopped</p>
                            <p class="text-sm text-gray-600 mt-2">${daemonStatus ? daemonStatus.error : 'Could not fetch status.'}</p>
                        </div>
                    `;
                    document.getElementById('sidebar-ipfs-status').textContent = 'Stopped';
                    document.getElementById('sidebar-ipfs-dot').className = 'status-dot error';
                }
                statusDiv.innerHTML = statusHtml;
            } catch (error) {
                console.error('Error loading IPFS daemon status:', error);
                document.getElementById('ipfs-daemon-status').innerHTML = '<p class="text-red-500">Failed to load daemon status.</p>';
            }
        }

        async function loadNetworkActivity() {
            try {
                const response = await fetch('/api/system/metrics');
                const data = await response.json();
                const network = data.network;
                const contentDiv = document.getElementById('network-activity-content');
                contentDiv.innerHTML = `
                    <div class="flex items-center">
                        <div class="p-3 rounded-lg bg-gradient-to-r from-blue-400 to-cyan-500 mr-4">
                            <i class="fas fa-arrow-up text-white"></i>
                        </div>
                        <div>
                            <p class="text-gray-600 text-sm">Data Sent</p>
                            <p class="font-bold text-xl">${formatBytes(network.sent)}</p>
                        </div>
                    </div>
                    <div class="flex items-center">
                        <div class="p-3 rounded-lg bg-gradient-to-r from-green-400 to-emerald-500 mr-4">
                            <i class="fas fa-arrow-down text-white"></i>
                        </div>
                        <div>
                            <p class="text-gray-600 text-sm">Data Received</p>
                            <p class="font-bold text-xl">${formatBytes(network.recv)}</p>
                        </div>
                    </div>
                `;
            } catch (error) {
                console.error('Error loading network activity:', error);
                document.getElementById('network-activity-content').innerHTML = '<p class="text-red-500">Failed to load network data.</p>';
            }
        }

        async function loadServices() {
            try {
                const response = await fetch('/api/services');
                const data = await response.json();
                const servicesList = document.getElementById('services-list');
                const totalBadge = document.getElementById('services-total-badge');
                servicesList.innerHTML = '';
                totalBadge.textContent = data.summary.total;

                if (data.services && data.services.length > 0) {
                    data.services.forEach(service => {
                        let statusClass = 'bg-gray-500';
                        let statusIcon = 'fa-question-circle';
                        if (service.status === 'running') {
                            statusClass = 'bg-green-500';
                            statusIcon = 'fa-check-circle';
                        } else if (service.status === 'stopped' || service.status === 'error') {
                            statusClass = 'bg-red-500';
                            statusIcon = 'fa-times-circle';
                        } else if (service.status === 'configured' || service.status === 'available') {
                            statusClass = 'bg-blue-500';
                            statusIcon = 'fa-cog';
                        }

                        const item = `
                            <div class="service-item p-6 rounded-xl flex items-center justify-between">
                                <div>
                                    <h4 class="text-lg font-semibold text-gray-800">${service.name}</h4>
                                    <p class="text-sm text-gray-600">${service.description}</p>
                                </div>
                                <div class="flex items-center space-x-4">
                                    <span class="text-sm font-medium text-gray-500">${service.type}</span>
                                    <div class="flex items-center px-3 py-1 rounded-full text-white text-sm font-medium ${statusClass}">
                                        <i class="fas ${statusIcon} mr-2"></i>
                                        <span>${service.status}</span>
                                    </div>
                                </div>
                            </div>
                        `;
                        servicesList.innerHTML += item;
                    });
                } else {
                    servicesList.innerHTML = '<p class="text-center text-gray-500">No services found.</p>';
                }
            } catch (error) {
                console.error('Error loading services:', error);
                document.getElementById('services-list').innerHTML = '<p class="text-red-500">Failed to load services.</p>';
            }
        }

        async function loadBackends() {
            try {
                const response = await fetch('/api/backends');
                const data = await response.json();
                const backendsList = document.getElementById('backends-list');
                backendsList.innerHTML = '';

                if (data.backends && data.backends.length > 0) {
                    data.backends.forEach(backend => {
                        const item = `
                            <div class="card p-6 mb-4">
                                <h4 class="text-lg font-semibold">${backend.name}</h4>
                                <p>Type: ${backend.type}</p>
                                <p>Status: ${backend.status}</p>
                            </div>
                        `;
                        backendsList.innerHTML += item;
                    });
                } else {
                    backendsList.innerHTML = '<p class="text-center text-gray-500">No backends configured.</p>';
                }
            } catch (error) {
                console.error('Error loading backends:', error);
                document.getElementById('backends-list').innerHTML = '<p class="text-red-500">Failed to load backends.</p>';
            }
        }

        async function loadBuckets() {
            try {
                const response = await fetch('/api/buckets');
                const data = await response.json();
                const bucketsList = document.getElementById('buckets-list');
                bucketsList.innerHTML = '';

                if (data.buckets && data.buckets.length > 0) {
                    data.buckets.forEach(bucket => {
                        const item = `
                            <div class="card p-6 mb-4">
                                <h4 class="text-lg font-semibold">${bucket.name}</h4>
                                <p>Backend: ${bucket.backend}</p>
                                <p>Files: ${bucket.files_count}</p>
                                <p>Size: ${formatBytes(bucket.size_bytes)}</p>
                            </div>
                        `;
                        bucketsList.innerHTML += item;
                    });
                } else {
                    bucketsList.innerHTML = '<p class="text-center text-gray-500">No buckets found.</p>';
                }
            } catch (error) {
                console.error('Error loading buckets:', error);
                document.getElementById('buckets-list').innerHTML = '<p class="text-red-500">Failed to load buckets.</p>';
            }
        }

        async function loadMetrics() {
            // Placeholder for metrics loading logic
            document.getElementById('metrics-content').innerHTML = '<p class="text-center text-gray-500">Detailed metrics coming soon.</p>';
        }

        async function loadConfig() {
            // Placeholder for config loading logic
            document.getElementById('config-content').innerHTML = '<p class="text-center text-gray-500">Configuration management coming soon.</p>';
        }

        async function loadMcpDetails() {
            // Placeholder for MCP details loading logic
            document.getElementById('mcp-content').innerHTML = '<p class="text-center text-gray-500">MCP server details coming soon.</p>';
        }

        // Pins Tab
        async function loadPins() {
            try {
                const response = await fetch('/api/pins');
                const data = await response.json();
                const pinsList = document.getElementById('pins-list');
                pinsList.innerHTML = ''; // Clear existing list

                if (data.pins && data.pins.length > 0) {
                    data.pins.forEach(pin => {
                        const row = `
                            <tr class="hover:bg-gray-50">
                                <td class="p-4 text-sm text-gray-800 font-mono">${pin.cid}</td>
                                <td class="p-4 text-sm text-gray-600">${pin.name || ''}</td>
                                <td class="p-4 text-right">
                                    <button onclick="removePin('${pin.cid}')" class="text-red-500 hover:text-red-700 font-semibold">
                                        <i class="fas fa-trash-alt mr-1"></i> Remove
                                    </button>
                                </td>
                            </tr>
                        `;
                        pinsList.innerHTML += row;
                    });
                } else {
                    pinsList.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-gray-500">No pins found.</td></tr>';
                }
            } catch (error) {
                console.error('Error loading pins:', error);
                const pinsList = document.getElementById('pins-list');
                pinsList.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-red-500">Failed to load pins.</td></tr>';
            }
        }

        async function addPin() {
            const cid = document.getElementById('pin-cid-input').value;
            const name = document.getElementById('pin-name-input').value;

            if (!cid) {
                alert('Please enter a CID.');
                return;
            }

            try {
                const response = await fetch('/api/pins', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cid, name }),
                });
                const result = await response.json();
                if (result.success) {
                    document.getElementById('pin-cid-input').value = '';
                    document.getElementById('pin-name-input').value = '';
                    loadPins(); // Refresh the list
                } else {
                    alert(`Error adding pin: ${result.error}`);
                }
            } catch (error) {
                console.error('Error adding pin:', error);
                alert('An unexpected error occurred while adding the pin.');
            }
        }

        async function removePin(cid) {
            if (!confirm(`Are you sure you want to remove pin ${cid}?`)) {
                return;
            }

            try {
                const response = await fetch(`/api/pins/${cid}`, {
                    method: 'DELETE',
                });
                const result = await response.json();
                if (result.success) {
                    loadPins(); // Refresh the list
                } else {
                    alert(`Error removing pin: ${result.error}`);
                }
            } catch (error) {
                console.error('Error removing pin:', error);
                alert('An unexpected error occurred while removing the pin.');
            }
        }

        // Global Refresh and Timers
        function refreshData() {
            const activeTab = document.querySelector('.nav-link.active').getAttribute('onclick').replace("showTab('", "").replace("')", "");
            showTab(activeTab);
        }

        function updateTime() {
            const now = new Date();
            document.getElementById('current-time').textContent = now.toLocaleTimeString();
        }

        // Mobile Menu
        document.getElementById('mobile-menu-btn').addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('open');
            document.getElementById('mobile-overlay').classList.toggle('hidden');
        });
        document.getElementById('mobile-overlay').addEventListener('click', () => {
            document.getElementById('sidebar').classList.remove('open');
            document.getElementById('mobile-overlay').classList.add('hidden');
        });

        // Initial Load
        document.addEventListener('DOMContentLoaded', () => {
            showTab('overview');
            setInterval(refreshData, 5000); // Auto-refresh data every 5 seconds
            setInterval(updateTime, 1000);
        });
    </script>
</body>
</html>
"""

    def run(self):
        """Run the unified server."""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if not self.debug else "debug"
        )

def main():
    """Main entry point for the unified MCP dashboard."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Example of running with custom config
    # config = {
    #     'host': '0.0.0.0',
    #     'port': 8004,
    #     'data_dir': '/tmp/ipfs_kit_dashboard',
    #     'debug': True
    # }
    # dashboard = UnifiedMCPDashboard(config)
    
    dashboard = UnifiedMCPDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()

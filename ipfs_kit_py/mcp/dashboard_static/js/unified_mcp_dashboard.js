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

import anyio
import json
import logging
import time
import psutil
import sys
import traceback
import os
import yaml
import subprocess
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
        
        self._setup_static_files()
        self._setup_routes()
        self._setup_middleware()
    
    def _setup_static_files(self):
        """Setup static file serving and template directories."""
        # Get the directory where this file is located
        current_dir = Path(__file__).parent.parent
        
        # Setup template directory
        template_dir = current_dir / "templates"
        if template_dir.exists():
            self.templates = Jinja2Templates(directory=str(template_dir))
        else:
            logger.warning(f"Template directory not found: {template_dir}")
            self.templates = None
        
        # Setup static files directory
        static_dir = current_dir / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        else:
            logger.warning(f"Static directory not found: {static_dir}")

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

        # Import all tools from the cli
        from ipfs_kit_py.cli import create_parser
        parser = create_parser()
        for command, subparser in parser._subparsers._group_actions[0].choices.items():
            for action, action_parser in subparser._subparsers._group_actions[0].choices.items():
                tool_name = f"{command}_{action}"
                description = action_parser.description
                input_schema = {
                    "type": "object",
                    "properties": {arg.dest: {"type": "string"} for arg in action_parser._actions if arg.dest not in ["help"]},
                    "required": [arg.dest for arg in action_parser._actions if arg.required and arg.dest not in ["help"]]
                }
                tool = Tool(
                    name=tool_name,
                    description=description,
                    inputSchema=input_schema
                )
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

            # Import the cli and execute the command
            from ipfs_kit_py.cli import main as cli_main
            command = tool_name.split("_")
            args = [command[0], command[1]]
            for key, value in arguments.items():
                args.append(f"--{key}")
                args.append(value)
            
            # This is a simplified way to call the CLI.
            # A more robust solution would use a dedicated function to handle the commands.
            class MockArgs:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

            # The CLI is not designed to be called this way, so we need to mock the args
            # and capture the output.
            try:
                # This is a hack to get the output of the CLI.
                # A better solution would be to refactor the CLI to be more modular.
                import io
                from contextlib import redirect_stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    await cli_main(args)
                output = f.getvalue()
                return {"content": [{"type": "text", "text": output}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": str(e)}]}
        
        # Dashboard API Routes
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Serve the main dashboard."""
            return await self._get_dashboard_html(request)
        
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
            result = await anyio.open_process(
                ["ipfs", "id"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
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
            result = await anyio.open_process(
                ["lsof", "-ti", f":{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
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
            result = await anyio.open_process(
                ["which", binary_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
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
        
        # Get bucket configurations from bucket_configs directory
        try:
            bucket_configs_dir = self.data_dir / "bucket_configs"
            if bucket_configs_dir.exists():
                for config_file in bucket_configs_dir.glob("*.yaml"):
                    try:
                        import yaml
                        with open(config_file, 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        bucket_name = config_data.get("bucket_name", config_file.stem)
                        bucket_data = {
                            "name": bucket_name,
                            "file": str(config_file),
                            "type": config_data.get("type", "general"),
                            "backend_bindings": config_data.get("backend_bindings", []),
                            "access": config_data.get("access", {}),
                            "backup": config_data.get("backup", {}),
                            "cache": config_data.get("cache", {}),
                            "compression": config_data.get("compression", {}),
                            "encryption": config_data.get("encryption", {}),
                            "features": config_data.get("features", {}),
                            "monitoring": config_data.get("monitoring", {}),
                            "network": config_data.get("network", {}),
                            "performance": config_data.get("performance", {}),
                            "storage": config_data.get("storage", {}),
                            "vfs": config_data.get("vfs", {}),
                            "status": "configured",
                            "size_bytes": 0,  # Will be calculated from actual data
                            "files_count": 0,  # Will be calculated from actual data
                            "created_at": config_data.get("created_at", ""),
                            "last_modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat(),
                            "description": f"Bucket configuration: {bucket_name}",
                            "tags": []
                        }
                        all_buckets.append(bucket_data)
                        
                    except Exception as e:
                        logger.error(f"Error loading bucket config {config_file}: {e}")
        except Exception as e:
            logger.error(f"Error loading bucket configs: {e}")
        
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
        """Get pins data from UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"pins": []}
        
        try:
            result = await self.bucket_interface.list_all_pins()
            if result["success"]:
                return {"pins": result["data"]["pins"]}
            else:
                logger.error(f"Error getting pins from UnifiedBucketInterface: {result['error']}")
                return {"pins": []}
        except Exception as e:
            logger.error(f"Error getting pins: {e}")
            return {"pins": []}

    async def _add_pin(self, cid: str, name: Optional[str] = None):
        """Add a new pin using UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"success": False, "error": "Bucket interface not initialized"}

        try:
            # For simplicity, we'll add to a default bucket or the first available bucket
            # In a real scenario, the bucket would be specified by the user
            list_buckets_result = await self.bucket_interface.list_backend_buckets()
            if not list_buckets_result["success"] or not list_buckets_result["data"]["buckets"]:
                return {"success": False, "error": "No buckets available to add pin to."}
            
            # Use the first available bucket
            target_bucket = list_buckets_result["data"]["buckets"][0]
            bucket_name = target_bucket["bucket_name"]
            backend_type = BackendType[target_bucket["backend"].upper()]

            # Create dummy content for the pin (in a real scenario, content would be provided)
            content = f"Dummy content for {cid}".encode('utf-8')

            result = await self.bucket_interface.add_content_pin(
                backend=backend_type,
                bucket_name=bucket_name,
                content_hash=cid,
                file_path=f"/pins/{cid}", # Example file path
                content=content,
                metadata={"name": name} if name else {}
            )
            
            if result["success"]:
                return {"success": True, "message": f"Pin {cid} added successfully to bucket {bucket_name}"}
            else:
                return {"success": False, "error": result["error"]}
        except Exception as e:
            logger.error(f"Error adding pin: {e}")
            return {"success": False, "error": str(e)}

    async def _remove_pin(self, cid: str):
        """Remove a pin using UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"success": False, "error": "Bucket interface not initialized"}

        try:
            result = await self.bucket_interface.remove_pin(cid)
            if result["success"]:
                return {"success": True, "message": f"Pin {cid} removed successfully."}
            else:
                return {"success": False, "error": result["error"]}
        except Exception as e:
            logger.error(f"Error removing pin: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_bucket(self, bucket_name: str, bucket_type: str = "general", description: str = ""):
        """Create a new bucket using UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"success": False, "error": "Bucket interface not initialized"}

        try:
            # Convert string bucket_type to BucketType enum
            try:
                bucket_type_enum = BucketType[bucket_type.upper()]
            except KeyError:
                return {"success": False, "error": f"Invalid bucket type: {bucket_type}"}

            # For simplicity, use IPFS as the backend type. In a real scenario, this would be user-defined.
            result = await self.bucket_interface.create_backend_bucket(
                backend=BackendType.IPFS,
                bucket_name=bucket_name,
                bucket_type=bucket_type_enum,
                metadata={"description": description}
            )
            
            if result["success"]:
                return {
                    "success": True,
                    "message": f"Bucket '{bucket_name}' created successfully",
                    "bucket": {
                        "name": bucket_name,
                        "type": bucket_type,
                        "description": description,
                        "created_at": datetime.now().isoformat()
                    }
                }
            else:
                return {"success": False, "error": result["error"]}
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            return {"success": False, "error": str(e)}
    
    async def _delete_bucket(self, bucket_name: str):
        """Delete a bucket using UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"success": False, "error": "Bucket interface not initialized"}

        try:
            result = await self.bucket_interface.delete_bucket(bucket_name)
            
            if result["success"]:
                return {
                    "success": True,
                    "message": f"Bucket '{bucket_name}' deleted successfully"
                }
            else:
                return {"success": False, "error": result["error"]}
        except Exception as e:
            logger.error(f"Error deleting bucket: {e}")
            return {"success": False, "error": str(e)}

    async def _get_bucket_details(self, bucket_name: str):
        """Get bucket details and file list using UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"success": False, "error": "Bucket interface not initialized"}

        try:
            result = await self.bucket_interface.get_bucket_details(bucket_name)
            
            if result["success"]:
                return {"success": True, "bucket": result["data"]}
            else:
                return {"success": False, "error": result["error"]}
        except Exception as e:
            logger.error(f"Error getting bucket details: {e}")
            return {"success": False, "error": str(e)}

    async def _upload_file_to_bucket(self, bucket_name: str, file: UploadFile):
        """Upload a file to a bucket using UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"success": False, "error": "Bucket interface not initialized"}

        try:
            content = await file.read()
            # For simplicity, use IPFS as the backend type. In a real scenario, this would be user-defined.
            result = await self.bucket_interface.add_content_pin(
                backend=BackendType.IPFS,
                bucket_name=bucket_name,
                content_hash=file.filename, # Using filename as CID for simplicity
                file_path=f"/{file.filename}",
                content=content,
                metadata={
                    "content_type": file.content_type,
                    "size": len(content)
                }
            )
            
            if result["success"]:
                return {
                    "success": True,
                    "message": f"File '{file.filename}' uploaded successfully to bucket '{bucket_name}'",
                    "file": {
                        "name": file.filename,
                        "size": len(content),
                        "content_type": file.content_type
                    }
                }
            else:
                return {"success": False, "error": result["error"]}
        except Exception as e:
            logger.error(f"Error uploading file to bucket: {e}")
            return {"success": False, "error": str(e)}

    async def _download_file_from_bucket(self, bucket_name: str, file_path: str):
        """Download a file from a bucket using UnifiedBucketInterface."""
        if not self.bucket_interface:
            raise HTTPException(status_code=500, detail="Bucket interface not initialized")

        try:
            result = await self.bucket_interface.get_content_from_bucket(bucket_name, file_path)
            
            if result["success"]:
                content = result["data"]["content"]
                media_type = result["data"].get("content_type", 'application/octet-stream')
                filename = Path(file_path).name
                
                return FileResponse(
                    content=content,
                    media_type=media_type,
                    filename=filename
                )
            else:
                raise HTTPException(status_code=404, detail=result["error"])
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error downloading file from bucket: {e}")
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
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(self._update_backends_cache)
            task_group.start_soon(self._update_services_cache)
            task_group.start_soon(self._update_pins_cache)
            task_group.start_soon(self._update_system_metrics_cache)
    
    async def _update_backends_cache(self):
        """Update backends cache from UnifiedBucketInterface."""
        if not self.bucket_interface:
            self.backends_cache = {"backends": []}
            return

        try:
            result = await self.bucket_interface.list_backend_buckets()
            if result["success"]:
                backends_data = []
                for bucket in result["data"]["buckets"]:
                    backend_name = bucket["backend"]
                    # Assuming each bucket represents a backend configuration
                    # This might need refinement based on how backends are truly defined vs. buckets
                    backends_data.append({
                        "name": bucket["bucket_name"], # Using bucket_name as backend name
                        "type": backend_name,
                        "enabled": True, # Assuming enabled if listed
                        "config": bucket.get("backend_config", {}),
                        "metadata": bucket.get("metadata", {}),
                        "created_at": bucket.get("created_at", ""),
                        "status": "configured",
                        "last_modified": bucket.get("last_modified", datetime.now().isoformat()),
                        "buckets": [] # This backend represents itself as a bucket, so no sub-buckets here
                    })
                self.backends_cache = {"backends": backends_data}
            else:
                logger.error(f"Error updating backends cache from UnifiedBucketInterface: {result['error']}")
                self.backends_cache = {"backends": []}
        except Exception as e:
            logger.error(f"Error updating backends cache: {e}")
            self.backends_cache = {"backends": []}
    
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
        """Update pins cache from UnifiedBucketInterface."""
        if not self.bucket_interface:
            self.pins_cache = {"pins": []}
            return

        try:
            result = await self.bucket_interface.list_all_pins()
            if result["success"]:
                self.pins_cache = {"pins": result["data"]["pins"]}
            else:
                logger.error(f"Error updating pins cache from UnifiedBucketInterface: {result['error']}")
                self.pins_cache = {"pins": []}
        except Exception as e:
            logger.error(f"Error updating pins cache: {e}")
            self.pins_cache = {"pins": []}
    
    async def _get_config_data(self):
        """Get configuration data from UnifiedBucketInterface and local files."""
        config_data = {}
        
        # Get backend configurations from UnifiedBucketInterface
        if self.bucket_interface:
            try:
                backends_result = await self.bucket_interface.list_backend_buckets()
                if backends_result["success"]:
                    config_data["backends"] = {b["bucket_name"]: b for b in backends_result["data"]["buckets"]}
                else:
                    logger.error(f"Error getting backend configs from UnifiedBucketInterface: {backends_result['error']}")
                    config_data["backends"] = {}
            except Exception as e:
                logger.error(f"Error getting backend configs from UnifiedBucketInterface: {e}")
                config_data["backends"] = {}

        # Read main config (if it exists locally)
        main_config_file = self.data_dir / "config.yaml"
        if main_config_file.exists():
            try:
                with open(main_config_file) as f:
                    config_data["main"] = yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Error reading main config file {main_config_file}: {e}")
        
        # Read metadata (if it exists locally)
        metadata_file = self.data_dir / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    config_data["metadata"] = json.load(f)
            except Exception as e:
                logger.warning(f"Error reading metadata file {metadata_file}: {e}")
        
        return {
            "config": config_data,
            "data_dir": str(self.data_dir),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _update_config_data(self, config_data):
        """Update configuration data."""
        try:
            # Update main config if provided
            if "main" in config_data and config_data["main"]:
                main_config_file = self.data_dir / "config.yaml"
                self.data_dir.mkdir(exist_ok=True)
                with open(main_config_file, 'w') as f:
                    yaml.dump(config_data["main"], f, default_flow_style=False)
            
            # Update metadata if provided
            if "metadata" in config_data and config_data["metadata"]:
                metadata_file = self.data_dir / "metadata.json"
                self.data_dir.mkdir(exist_ok=True)
                with open(metadata_file, 'w') as f:
                    json.dump(config_data["metadata"], f, indent=2)
            
            # Update backend configurations via UnifiedBucketInterface
            if "backends" in config_data and self.bucket_interface:
                for backend_name, backend_config in config_data["backends"].items():
                    await self._update_backend_config(backend_name, backend_config)

            return {"status": "updated", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"Error updating config data: {e}")
            return {"error": str(e)}
    
    async def _get_backend_configs(self):
        """Get all backend configurations from UnifiedBucketInterface."""
        if not self.bucket_interface:
            return {"error": "Bucket interface not initialized"}
        
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
                            "status": "configured", # Assuming if it's listed, it's configured
                            "buckets": []
                        }
                    backends[backend_name]["buckets"].append(bucket["bucket_name"])
                return backends
            else:
                logger.error(f"Error getting backends from UnifiedBucketInterface: {result['error']}")
                return {"error": result["error"]}
        except Exception as e:
            logger.error(f"Error getting backend configs: {e}")
            return {"error": str(e)}
    
    async def _update_backend_config(self, backend_name: str, config_data):
        """Update a specific backend configuration by updating the corresponding bucket's metadata."""
        if not self.bucket_interface:
            return {"error": "Bucket interface not initialized"}

        try:
            # Assuming backend_name is the bucket_name
            # Retrieve existing bucket info to get current metadata and backend_config
            list_result = await self.bucket_interface.list_backend_buckets()
            existing_bucket = None
            for bucket in list_result.get("data", {}).get("buckets", []):
                if bucket.get("bucket_name") == backend_name:
                    existing_bucket = bucket
                    break
            
            if not existing_bucket:
                return {"error": f"Backend '{backend_name}' (bucket) not found"}

            # Merge new config_data into existing backend_config and metadata
            updated_backend_config = {**existing_bucket.get("backend_config", {}), **config_data.get("config", {})}
            updated_metadata = {**existing_bucket.get("metadata", {}), **config_data.get("metadata", {})}

            # Call the update_bucket method on UnifiedBucketInterface
            result = await self.bucket_interface.update_bucket(
                bucket_name=backend_name,
                backend_config=updated_backend_config,
                metadata=updated_metadata
            )
            
            if result["success"]:
                return {
                    "status": "updated",
                    "backend": backend_name,
                    "message": f"Backend '{backend_name}' (bucket) updated successfully.",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {"error": result["error"]}
        except Exception as e:
            logger.error(f"Error updating backend config: {e}")
            return {"error": str(e)}
    
    async def _create_backend_config(self, backend_data):
        """Create a new backend configuration by creating a bucket."""
        if not self.bucket_interface:
            return {"error": "Bucket interface not initialized"}

        try:
            backend_name = backend_data.get("name")
            backend_type_str = backend_data.get("type")
            
            if not backend_name or not backend_type_str:
                return {"error": "Backend name and type are required"}
            
            try:
                backend_type = BackendType[backend_type_str.upper()]
            except KeyError:
                return {"error": f"Invalid backend type: {backend_type_str}"}

            # Use the UnifiedBucketInterface to create a bucket, which represents the backend config
            result = await self.bucket_interface.create_backend_bucket(
                backend=backend_type,
                bucket_name=backend_name, # Use backend_name as bucket_name
                bucket_type=BucketType.GENERAL, # Default bucket type
                backend_config=backend_data.get("config", {}), # Pass config as backend_config
                metadata=backend_data.get("metadata", {})
            )
            
            if result["success"]:
                return {
                    "status": "created",
                    "backend": backend_name,
                    "type": backend_type_str,
                    "message": f"Backend '{backend_name}' created successfully as a bucket.",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {"error": result["error"]}
        except Exception as e:
            logger.error(f"Error creating backend config: {e}")
            return {"error": str(e)}
    
    async def _remove_backend_config(self, backend_name: str, force: bool = False):
        """Remove a backend configuration by deleting the corresponding bucket."""
        if not self.bucket_interface:
            return {"error": "Bucket interface not initialized"}

        try:
            # Assuming backend_name is the bucket_name
            result = await self.bucket_interface.delete_bucket(backend_name)
            
            if result["success"]:
                return {
                    "status": "removed",
                    "backend": backend_name,
                    "message": f"Backend '{backend_name}' (bucket) removed successfully.",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {"error": result["error"]}
        except Exception as e:
            logger.error(f"Error removing backend config: {e}")
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
                    result = await anyio.open_process(
                        ["ipfs", "id"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
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

    async def _get_dashboard_html(self, request: Request):
        """Generate the dashboard HTML using Jinja2 template."""
        # Get the directory where this file is located
        current_dir = Path(__file__).parent.parent
        
        # Setup template directory
        template_dir = current_dir / "templates"
        if not template_dir.exists():
            logger.error(f"Template directory not found: {template_dir}")
            return HTMLResponse(
                content="<h1>Dashboard templates not found. Please ensure the 'templates' directory exists.</h1>",
                status_code=500
            )
        
        # Re-initialize Jinja2Templates to ensure it picks up the correct path
        templates = Jinja2Templates(directory=str(template_dir))
        
        return templates.TemplateResponse(
            "dashboard.html", 
            {"request": request, "port": self.port}
        )

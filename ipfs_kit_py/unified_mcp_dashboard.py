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
                bucket_name = data.get("bucket_name")
                bucket_type = data.get("bucket_type", "general")
                description = data.get("description", "")
                
                if not bucket_name:
                    return {"success": False, "error": "Bucket name is required"}
                
                # Create bucket using the bucket manager
                result = await self._create_bucket(bucket_name, bucket_type, description)
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/services")
        async def api_services():
            """Get services status."""
            return await self._get_services_data()
        
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
        
        @self.app.post("/api/config/backends/{backend_name}")
        async def api_update_backend_config(backend_name: str, request: Request):
            """Update a specific backend configuration."""
            try:
                config_data = await request.json()
                result = await self._update_backend_config(backend_name, config_data)
                return {"success": True, "result": result}
            except Exception as e:
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
        """Get buckets data."""
        backends = await self._get_backends_data()
        all_buckets = []
        
        # Get buckets from backends
        for backend in backends.get("backends", []):
            for bucket in backend.get("buckets", []):
                bucket["backend"] = backend["name"]
                all_buckets.append(bucket)
        
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
            print(f"Error loading buckets from simple bucket manager: {e}")
            import traceback
            traceback.print_exc()
        
        return {"buckets": all_buckets}
    
    async def _create_bucket(self, bucket_name: str, bucket_type: str = "general", description: str = ""):
        """Create a new bucket."""
        try:
            # Try to import and use the simple bucket manager
            try:
                from .simple_bucket_manager import get_simple_bucket_manager
                bucket_manager = get_simple_bucket_manager()
                result = await bucket_manager.create_bucket(
                    bucket_name=bucket_name,
                    bucket_type=bucket_type,
                    metadata={"description": description}
                )
                # Force refresh of buckets cache
                self.buckets_cache = None
                return result
            except ImportError:
                # Try the unified bucket interface
                try:
                    from .unified_bucket_interface import get_global_unified_bucket_interface
                    from .bucket_vfs_manager import BucketType
                    
                    interface = get_global_unified_bucket_interface()
                    await interface.initialize()
                    
                    # Convert string to enum
                    bucket_type_enum = BucketType.GENERAL
                    if hasattr(BucketType, bucket_type.upper()):
                        bucket_type_enum = getattr(BucketType, bucket_type.upper())
                    
                    # Use PARQUET backend as default
                    from .unified_bucket_interface import BackendType
                    result = await interface.create_backend_bucket(
                        backend=BackendType.PARQUET,
                        bucket_name=bucket_name,
                        bucket_type=bucket_type_enum,
                        metadata={"description": description}
                    )
                    # Force refresh of buckets cache
                    self.buckets_cache = None
                    return result
                except ImportError:
                    # Fallback: create a mock successful response
                    return {
                        "success": True,
                        "data": {
                            "bucket_name": bucket_name,
                            "bucket_type": bucket_type,
                            "description": description,
                            "created_at": datetime.now().isoformat(),
                            "message": "Bucket created successfully (mock implementation - bucket managers not available)"
                        }
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create bucket: {str(e)}"
            }
    
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
                            </div>
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
                        <span id="backends-total-badge" class="ml-4 text-sm bg-purple-100 text-purple-800 px-3 py-1 rounded-full font-medium">0</span>
                    </h3>
                    <div id="backends-list" class="space-y-6">
                        <div class="text-center py-12">
                            <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                            </div>
                            <p class="text-gray-500 font-medium">Loading backends...</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Buckets Tab -->
            <div id="buckets-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center justify-between">
                        <div class="flex items-center">
                            <div class="p-2 rounded-lg bg-gradient-to-r from-orange-500 to-red-600 mr-4">
                                <i class="fas fa-folder text-white"></i>
                            </div>
                            Bucket Management
                            <span id="buckets-total-badge" class="ml-4 text-sm bg-orange-100 text-orange-800 px-3 py-1 rounded-full font-medium">0</span>
                        </div>
                        <button onclick="showCreateBucketModal()" class="btn-primary px-4 py-2 rounded-lg text-sm">
                            <i class="fas fa-plus mr-2"></i> Create Bucket
                        </button>
                    </h3>
                    <div id="buckets-list" class="space-y-6">
                        <div class="text-center py-12">
                            <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                            </div>
                            <p class="text-gray-500 font-medium">Loading buckets...</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Metrics Tab -->
            <div id="metrics-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-red-500 to-pink-600 mr-4">
                            <i class="fas fa-chart-line text-white"></i>
                        </div>
                        Detailed System Metrics
                    </h3>
                    <div id="detailed-metrics" class="space-y-6">
                        <div class="text-center py-12">
                            <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                            </div>
                            <p class="text-gray-500 font-medium">Loading detailed metrics...</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Configuration Tab -->
            <div id="config-tab" class="tab-content">
                <div class="space-y-8">
                    <!-- Main Configuration -->
                    <div class="card p-8 rounded-2xl">
                        <h3 class="text-2xl font-bold mb-6 flex items-center">
                            <div class="p-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 mr-4">
                                <i class="fas fa-cog text-white"></i>
                            </div>
                            System Configuration
                        </h3>
                        <div id="config-content" class="space-y-6">
                            <div class="text-center py-12">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                    <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                                </div>
                                <p class="text-gray-500 font-medium">Loading configuration...</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Backend Configurations -->
                    <div class="card p-8 rounded-2xl">
                        <h3 class="text-2xl font-bold mb-6 flex items-center">
                            <div class="p-2 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-600 mr-4">
                                <i class="fas fa-server text-white"></i>
                            </div>
                            Backend Configurations
                        </h3>
                        <div id="backend-configs-content" class="space-y-6">
                            <div class="text-center py-12">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                                    <i class="fas fa-spinner fa-spin text-2xl text-gray-500"></i>
                                </div>
                                <p class="text-gray-500 font-medium">Loading backend configurations...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- MCP Tab -->
            <div id="mcp-tab" class="tab-content">
                <div class="card p-8 rounded-2xl">
                    <h3 class="text-2xl font-bold mb-6 flex items-center">
                        <div class="p-2 rounded-lg bg-gradient-to-r from-yellow-500 to-orange-600 mr-4">
                            <i class="fas fa-broadcast-tower text-white"></i>
                        </div>
                        MCP Server Control
                    </h3>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        <div class="space-y-6">
                            <h4 class="text-xl font-semibold mb-4 flex items-center">
                                <i class="fas fa-info-circle mr-3 text-blue-500"></i>
                                Server Information
                            </h4>
                            <div class="space-y-4">
                                <div class="flex justify-between items-center p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200">
                                    <span class="text-gray-700 font-medium">Status:</span>
                                    <div class="flex items-center">
                                        <div class="status-dot running mr-2"></div>
                                        <span class="text-green-600 font-semibold">Running</span>
                                    </div>
                                </div>
                                <div class="flex justify-between items-center p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200">
                                    <span class="text-gray-700 font-medium">Port:</span>
                                    <span class="font-semibold text-gray-800">{self.port}</span>
                                </div>
                                <div class="flex justify-between items-center p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border border-purple-200">
                                    <span class="text-gray-700 font-medium">Protocol:</span>
                                    <span class="font-semibold text-gray-800">MCP v1.0</span>
                                </div>
                                <div class="flex justify-between items-center p-4 bg-gradient-to-r from-orange-50 to-red-50 rounded-xl border border-orange-200">
                                    <span class="text-gray-700 font-medium">Mode:</span>
                                    <span class="font-semibold text-gray-800">Unified Dashboard</span>
                                </div>
                            </div>
                        </div>
                        <div class="space-y-6">
                            <h4 class="text-xl font-semibold mb-4 flex items-center">
                                <i class="fas fa-tools mr-3 text-green-500"></i>
                                Available Tools
                            </h4>
                            <div id="mcp-tools" class="space-y-3">
                                <div class="flex items-center p-3 bg-white rounded-lg border border-gray-200 shadow-sm">
                                    <i class="fas fa-heartbeat mr-3 text-red-500"></i>
                                    <span class="font-medium">daemon_status</span>
                                </div>
                                <div class="flex items-center p-3 bg-white rounded-lg border border-gray-200 shadow-sm">
                                    <i class="fas fa-list mr-3 text-blue-500"></i>
                                    <span class="font-medium">list_backends</span>
                                </div>
                                <div class="flex items-center p-3 bg-white rounded-lg border border-gray-200 shadow-sm">
                                    <i class="fas fa-folder-open mr-3 text-orange-500"></i>
                                    <span class="font-medium">list_buckets</span>
                                </div>
                                <div class="flex items-center p-3 bg-white rounded-lg border border-gray-200 shadow-sm">
                                    <i class="fas fa-chart-bar mr-3 text-green-500"></i>
                                    <span class="font-medium">system_metrics</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let updateInterval;
        let isUpdating = false;
        
        // Utility functions
        function formatBytes(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }}
        
        function updateClock() {{
            const now = new Date();
            document.getElementById('current-time').textContent = now.toLocaleTimeString();
        }}
        
        // Tab management
        function showTab(tabName) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});
            
            // Remove active class from all nav links
            document.querySelectorAll('.nav-link').forEach(link => {{
                link.classList.remove('active');
            }});
            
            // Show selected tab
            const targetTab = document.getElementById(tabName + '-tab');
            if (targetTab) {{
                targetTab.classList.add('active');
            }}
            
            // Add active class to clicked nav link
            if (event && event.target) {{
                let navLink = event.target;
                while (navLink && !navLink.classList.contains('nav-link')) {{
                    navLink = navLink.parentElement;
                }}
                if (navLink) {{
                    navLink.classList.add('active');
                }}
            }}
            
            // Load tab-specific data
            loadTabData(tabName);
            
            // Close mobile menu if open
            closeMobileMenu();
        }}
        
        // Mobile menu management
        function toggleMobileMenu() {{
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('mobile-overlay');
            
            if (sidebar.classList.contains('open')) {{
                closeMobileMenu();
            }} else {{
                openMobileMenu();
            }}
        }}
        
        function openMobileMenu() {{
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('mobile-overlay');
            
            sidebar.classList.add('open');
            overlay.classList.remove('hidden');
            setTimeout(() => overlay.classList.remove('opacity-0'), 10);
        }}
        
        function closeMobileMenu() {{
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('mobile-overlay');
            
            sidebar.classList.remove('open');
            overlay.classList.add('opacity-0');
            setTimeout(() => overlay.classList.add('hidden'), 300);
        }}
        
        // Mobile menu event listeners
        document.getElementById('mobile-menu-btn').addEventListener('click', toggleMobileMenu);
        document.getElementById('mobile-overlay').addEventListener('click', closeMobileMenu);
        
        // Data loading functions with enhanced error handling
        async function loadSystemOverview() {{
            if (isUpdating) return;
            isUpdating = true;
            
            try {{
                const response = await fetch('/api/system/overview');
                if (!response.ok) throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                
                const data = await response.json();
                
                // Update metric cards with animation
                updateMetricCard('services-count', data.services || 0);
                updateMetricCard('backends-count', data.backends || 0);
                updateMetricCard('buckets-count', data.buckets || 0);
                
                // Update sidebar with enhanced status
                updateSidebarStatus(data);
                
                // Update system performance with better formatting
                if (data.system) {{
                    updateSystemPerformance(data.system);
                }}
                
                // Load IPFS daemon status
                await loadIPFSDaemonStatus();
                
            }} catch (error) {{
                console.error('Error loading system overview:', error);
                showErrorState('overview');
            }} finally {{
                isUpdating = false;
            }}
        }}
        
        function updateMetricCard(elementId, value) {{
            const element = document.getElementById(elementId);
            if (element && element.textContent !== value.toString()) {{
                element.style.transform = 'scale(1.1)';
                element.textContent = value;
                setTimeout(() => {{
                    element.style.transform = 'scale(1)';
                }}, 200);
            }}
        }}
        
        function updateSidebarStatus(data) {{
            // Update MCP status
            const mcpStatus = document.getElementById('sidebar-mcp-status');
            const mcpDot = mcpStatus?.parentElement?.querySelector('.status-dot');
            if (mcpStatus) {{
                mcpStatus.textContent = 'Running';
                mcpStatus.className = 'text-green-400 font-medium';
            }}
            if (mcpDot) {{
                mcpDot.className = 'status-dot running mr-2';
            }}
            
            // Update backends count
            const backendsCount = document.getElementById('sidebar-backends-count');
            if (backendsCount) {{
                backendsCount.textContent = data.backends || 0;
            }}
        }}
        
        function updateSystemPerformance(metrics) {{
            // Update CPU
            if (metrics.cpu) {{
                const cpuPercent = Math.round(metrics.cpu.usage * 10) / 10;
                updateProgressBar('cpu', cpuPercent);
                updateSidebarProgressBar('cpu', cpuPercent);
            }}
            
            // Update Memory
            if (metrics.memory) {{
                const memoryPercent = Math.round(metrics.memory.percent * 10) / 10;
                updateProgressBar('memory', memoryPercent);
                updateSidebarProgressBar('memory', memoryPercent);
                
                // Update memory details
                const memoryUsed = document.getElementById('memory-used');
                const memoryTotal = document.getElementById('memory-total');
                if (memoryUsed) memoryUsed.textContent = formatBytes(metrics.memory.used);
                if (memoryTotal) memoryTotal.textContent = formatBytes(metrics.memory.total);
            }}
            
            // Update Disk
            if (metrics.disk) {{
                const diskPercent = Math.round(metrics.disk.percent * 10) / 10;
                updateProgressBar('disk', diskPercent);
                
                // Update disk details
                const diskUsed = document.getElementById('disk-used');
                const diskTotal = document.getElementById('disk-total');
                if (diskUsed) diskUsed.textContent = formatBytes(metrics.disk.used);
                if (diskTotal) diskTotal.textContent = formatBytes(metrics.disk.total);
            }}
            
            // Update Network Activity
            if (metrics.network) {{
                updateNetworkActivity(metrics.network);
            }}
        }}
        
        function updateProgressBar(type, percent) {{
            const percentElement = document.getElementById(`${{type}}-percent`);
            const barElement = document.getElementById(`${{type}}-bar`);
            
            if (percentElement) {{
                percentElement.textContent = percent + '%';
            }}
            
            if (barElement) {{
                barElement.style.width = percent + '%';
            }}
        }}
        
        function updateSidebarProgressBar(type, percent) {{
            const percentElement = document.getElementById(`sidebar-${{type}}-percent`);
            const barElement = document.getElementById(`sidebar-${{type}}-bar`);
            
            if (percentElement) {{
                percentElement.textContent = percent + '%';
            }}
            
            if (barElement) {{
                barElement.style.width = percent + '%';
            }}
        }}
        
        function updateNetworkActivity(networkData) {{
            const networkContainer = document.getElementById('network-activity-content');
            if (!networkContainer) return;
            
            try {{
                const sent = networkData.sent || 0;
                const recv = networkData.recv || 0;
                
                networkContainer.innerHTML = `
                    <div class="space-y-4">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3">
                                <div class="w-3 h-3 bg-green-500 rounded-full"></div>
                                <span class="text-sm font-medium text-gray-700">Data Sent</span>
                            </div>
                            <span class="text-sm font-semibold text-gray-900">${{formatBytes(sent)}}</span>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3">
                                <div class="w-3 h-3 bg-blue-500 rounded-full"></div>
                                <span class="text-sm font-medium text-gray-700">Data Received</span>
                            </div>
                            <span class="text-sm font-semibold text-gray-900">${{formatBytes(recv)}}</span>
                        </div>
                        
                        <div class="pt-2 border-t border-gray-200">
                            <div class="flex items-center justify-between">
                                <span class="text-sm font-medium text-gray-700">Total Transfer</span>
                                <span class="text-sm font-semibold text-indigo-600">${{formatBytes(sent + recv)}}</span>
                            </div>
                        </div>
                    </div>
                `;
            }} catch (error) {{
                console.error('Error updating network activity:', error);
                networkContainer.innerHTML = `
                    <div class="text-center py-4">
                        <i class="fas fa-exclamation-triangle text-red-500 mb-2"></i>
                        <p class="text-sm text-red-600">Error loading network data</p>
                    </div>
                `;
            }}
        }}
        
        async function loadIPFSDaemonStatus() {{
            try {{
                const response = await fetch('/api/services');
                const data = await response.json();
                
                const ipfsDaemon = data.services?.find(s => s.name === 'IPFS Daemon');
                const statusContainer = document.getElementById('ipfs-daemon-status');
                const sidebarStatus = document.getElementById('sidebar-ipfs-status');
                const sidebarDot = document.getElementById('sidebar-ipfs-dot');
                
                if (ipfsDaemon && statusContainer) {{
                    const isRunning = ipfsDaemon.status === 'running';
                    
                    statusContainer.innerHTML = `
                        <div class="text-center">
                            <div class="inline-flex items-center justify-center w-16 h-16 rounded-full mb-4 ${{
                                isRunning ? 'bg-green-100' : 'bg-red-100'
                            }}">
                                <i class="fas fa-${{isRunning ? 'check-circle' : 'times-circle'}} text-2xl ${{
                                    isRunning ? 'text-green-600' : 'text-red-600'
                                }}"></i>
                            </div>
                            <h4 class="font-semibold text-lg mb-2">${{ipfsDaemon.status.charAt(0).toUpperCase() + ipfsDaemon.status.slice(1)}}</h4>
                            <p class="text-sm text-gray-600">${{ipfsDaemon.description}}</p>
                        </div>
                        ${{isRunning && ipfsDaemon.port ? `
                            <div class="text-center">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
                                    <i class="fas fa-ethernet text-2xl text-blue-600"></i>
                                </div>
                                <h4 class="font-semibold text-lg mb-2">Port ${{ipfsDaemon.port}}</h4>
                                <p class="text-sm text-gray-600">API Endpoint</p>
                            </div>
                        ` : ''}}
                        ${{isRunning ? `
                            <div class="text-center">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-purple-100 rounded-full mb-4">
                                    <i class="fas fa-network-wired text-2xl text-purple-600"></i>
                                </div>
                                <h4 class="font-semibold text-lg mb-2">Connected</h4>
                                <p class="text-sm text-gray-600">P2P Network</p>
                            </div>
                        ` : ''}}
                    `;
                    
                    // Update sidebar
                    if (sidebarStatus) {{
                        sidebarStatus.textContent = isRunning ? 'Running' : 'Stopped';
                        sidebarStatus.className = isRunning ? 'text-green-400 font-medium' : 'text-red-400 font-medium';
                    }}
                    
                    if (sidebarDot) {{
                        sidebarDot.className = `status-dot ${{isRunning ? 'running' : 'error'}} mr-2`;
                    }}
                }}
            }} catch (error) {{
                console.error('Error loading IPFS daemon status:', error);
            }}
        }}
        
        function showErrorState(section) {{
            const errorHtml = `
                <div class="text-center py-12">
                    <div class="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
                        <i class="fas fa-exclamation-triangle text-2xl text-red-600"></i>
                    </div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">Unable to Load Data</h3>
                    <p class="text-gray-600 mb-4">There was an error loading the ${{section}} information.</p>
                    <button onclick="refreshData()" class="btn-primary px-4 py-2 rounded-lg text-sm">
                        <i class="fas fa-sync-alt mr-2"></i> Try Again
                    </button>
                </div>
            `;
            
            // Apply error state to relevant containers
            if (section === 'overview') {{
                document.getElementById('system-performance').innerHTML = errorHtml;
                document.getElementById('network-activity').innerHTML = errorHtml;
            }}
        }}
        
        async function loadServices() {{
            try {{
                const response = await fetch('/api/services');
                if (!response.ok) throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                
                const data = await response.json();
                const container = document.getElementById('services-list');
                const totalBadge = document.getElementById('services-total-badge');
                
                if (data.services && data.services.length > 0) {{
                    // Update total badge
                    if (totalBadge) {{
                        totalBadge.textContent = data.services.length;
                    }}
                    
                    // Group services by type
                    const servicesByType = data.services.reduce((acc, service) => {{
                        if (!acc[service.type]) acc[service.type] = [];
                        acc[service.type].push(service);
                        return acc;
                    }}, {{}});
                    
                    const typeLabels = {{
                        'core_service': 'Core Services',
                        'cluster_service': 'Cluster Services',
                        'storage_service': 'Storage Services',
                        'storage_backend': 'Storage Backends',
                        'data_format': 'Data Format Support',
                        'networking': 'Networking'
                    }};
                    
                    const typeIcons = {{
                        'core_service': 'fas fa-cube',
                        'cluster_service': 'fas fa-network-wired',
                        'storage_service': 'fas fa-database',
                        'storage_backend': 'fas fa-cloud',
                        'data_format': 'fas fa-file-code',
                        'networking': 'fas fa-wifi'
                    }};
                    
                    const typeColors = {{
                        'core_service': 'blue',
                        'cluster_service': 'green',
                        'storage_service': 'purple',
                        'storage_backend': 'indigo',
                        'data_format': 'orange',
                        'networking': 'pink'
                    }};
                    
                    container.innerHTML = Object.entries(servicesByType).map(([type, services]) => {{
                        const color = typeColors[type] || 'gray';
                        return `
                        <div class="space-y-4 fade-in">
                            <div class="flex items-center justify-between">
                                <h4 class="text-xl font-bold flex items-center text-gray-800">
                                    <div class="p-2 rounded-lg bg-gradient-to-r from-${{color}}-500 to-${{color}}-600 mr-3">
                                        <i class="${{typeIcons[type] || 'fas fa-cog'}} text-white"></i>
                                    </div>
                                    ${{typeLabels[type] || type}}
                                </h4>
                                <span class="text-sm bg-${{color}}-100 text-${{color}}-800 px-3 py-1 rounded-full font-semibold">
                                    ${{services.length}} service${{services.length !== 1 ? 's' : ''}}
                                </span>
                            </div>
                            <div class="grid gap-4">
                                ${{services.map(service => {{
                                    const statusColor = 
                                        service.status === 'running' ? 'green' :
                                        service.status === 'configured' ? 'blue' :
                                        service.status === 'available' ? 'cyan' :
                                        service.status === 'warning' ? 'yellow' :
                                        service.status === 'disabled' ? 'gray' :
                                        service.status === 'not_configured' ? 'orange' :
                                        service.status === 'not_available' ? 'gray' : 'red';
                                    
                                    return `
                                    <div class="service-item p-6 rounded-xl border border-gray-200 hover:border-${{color}}-300 transition-all duration-300">
                                        <div class="flex items-start justify-between">
                                            <div class="flex items-start flex-1">
                                                <div class="status-dot ${{service.status === 'running' ? 'running' : service.status === 'warning' ? 'warning' : 'error'}} mr-4 mt-1"></div>
                                                <div class="flex-1">
                                                    <h5 class="text-lg font-semibold text-gray-900 mb-2">${{service.name}}</h5>
                                                    <p class="text-gray-600 mb-3">${{service.description || 'No description available'}}</p>
                                                    <div class="flex items-center space-x-3">
                                                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-${{statusColor}}-100 text-${{statusColor}}-800">
                                                            ${{service.status.replace('_', ' ').toUpperCase()}}
                                                        </span>
                                                        ${{service.port ? `
                                                            <span class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-700">
                                                                <i class="fas fa-ethernet mr-1"></i>
                                                                Port ${{service.port}}
                                                            </span>
                                                        ` : ''}}
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="ml-4">
                                                <i class="fas fa-${{
                                                    service.status === 'running' ? 'check-circle text-green-500' :
                                                    service.status === 'warning' ? 'exclamation-triangle text-yellow-500' :
                                                    service.status === 'configured' ? 'cog text-blue-500' :
                                                    service.status === 'available' ? 'check text-cyan-500' :
                                                    'times-circle text-red-500'
                                                }} text-2xl"></i>
                                            </div>
                                        </div>
                                    </div>
                                    `;
                                }}).join('')}}
                            </div>
                        </div>
                    `;
                    }}).join('');
                    
                    // Update service count in overview
                    updateMetricCard('services-count', data.services.length);
                    
                }} else {{
                    container.innerHTML = `
                        <div class="text-center py-16">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-gray-100 rounded-full mb-6">
                                <i class="fas fa-cogs text-3xl text-gray-400"></i>
                            </div>
                            <h3 class="text-xl font-semibold text-gray-900 mb-2">No Services Found</h3>
                            <p class="text-gray-600 max-w-md mx-auto">No services are currently configured or detected. Check your IPFS installation and configuration.</p>
                        </div>
                    `;
                    if (totalBadge) totalBadge.textContent = '0';
                }}
            }} catch (error) {{
                console.error('Error loading services:', error);
                const container = document.getElementById('services-list');
                container.innerHTML = `
                    <div class="text-center py-16">
                        <div class="inline-flex items-center justify-center w-20 h-20 bg-red-100 rounded-full mb-6">
                            <i class="fas fa-exclamation-triangle text-3xl text-red-500"></i>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Error Loading Services</h3>
                        <p class="text-gray-600 mb-6 max-w-md mx-auto">There was an error loading the services information. Please try refreshing the page.</p>
                        <button onclick="loadServices()" class="btn-primary px-6 py-3 rounded-xl">
                            <i class="fas fa-sync-alt mr-2"></i> Try Again
                        </button>
                    </div>
                `;
            }}
        }}
        
        async function loadBackends() {{
            try {{
                const response = await fetch('/api/backends');
                if (!response.ok) throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                
                const data = await response.json();
                const container = document.getElementById('backends-list');
                const totalBadge = document.getElementById('backends-total-badge');
                
                if (data.backends && data.backends.length > 0) {{
                    // Update total badge
                    if (totalBadge) {{
                        totalBadge.textContent = data.backends.length;
                    }}
                    
                    // Group backends by type/category
                    const backendIcons = {{
                        's3': 'fab fa-aws',
                        'aws': 'fab fa-aws',
                        'gdrive': 'fab fa-google-drive',
                        'google': 'fab fa-google',
                        'github': 'fab fa-github',
                        'huggingface': 'fas fa-robot',
                        'ftp': 'fas fa-server',
                        'ssh': 'fas fa-terminal',
                        'sftp': 'fas fa-exchange-alt',
                        'storacha': 'fas fa-cloud',
                        'web3': 'fas fa-cube'
                    }};
                    
                    container.innerHTML = data.backends.map((backend, index) => {{
                        const backendType = backend.type || backend.name.toLowerCase();
                        const icon = Object.keys(backendIcons).find(key => backendType.includes(key)) || 'server';
                        const iconClass = backendIcons[icon] || 'fas fa-server';
                        
                        const statusColor = 
                            backend.status === 'configured' ? 'green' :
                            backend.status === 'connected' ? 'blue' :
                            backend.status === 'error' ? 'red' :
                            backend.status === 'warning' ? 'yellow' : 'gray';
                        
                        return `
                        <div class="service-item p-6 rounded-xl border border-gray-200 hover:border-purple-300 transition-all duration-300 fade-in" style="animation-delay: ${{index * 100}}ms">
                            <div class="flex items-start justify-between">
                                <div class="flex items-start flex-1">
                                    <div class="p-3 rounded-lg bg-gradient-to-r from-purple-500 to-pink-600 mr-4">
                                        <i class="${{iconClass}} text-white text-xl"></i>
                                    </div>
                                    <div class="flex-1">
                                        <h5 class="text-xl font-bold text-gray-900 mb-2">${{backend.name}}</h5>
                                        <p class="text-gray-600 mb-3">${{backend.description || `${{backend.type || 'Storage'}} backend configuration`}}</p>
                                        <div class="flex items-center space-x-3">
                                            <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-${{statusColor}}-100 text-${{statusColor}}-800">
                                                ${{backend.status?.toUpperCase() || 'UNKNOWN'}}
                                            </span>
                                            ${{backend.type ? `
                                                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-700">
                                                    <i class="fas fa-tag mr-1"></i>
                                                    ${{backend.type}}
                                                </span>
                                            ` : ''}}
                                            ${{backend.buckets && backend.buckets.length ? `
                                                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-700">
                                                    <i class="fas fa-folder mr-1"></i>
                                                    ${{backend.buckets.length}} bucket${{backend.buckets.length !== 1 ? 's' : ''}}
                                                </span>
                                            ` : ''}}
                                        </div>
                                    </div>
                                </div>
                                <div class="ml-4">
                                    <i class="fas fa-${{
                                        backend.status === 'configured' ? 'check-circle text-green-500' :
                                        backend.status === 'connected' ? 'link text-blue-500' :
                                        backend.status === 'error' ? 'times-circle text-red-500' :
                                        backend.status === 'warning' ? 'exclamation-triangle text-yellow-500' :
                                        'question-circle text-gray-400'
                                    }} text-2xl"></i>
                                </div>
                            </div>
                            
                            ${{backend.buckets && backend.buckets.length > 0 ? `
                                <div class="mt-4 pt-4 border-t border-gray-200">
                                    <h6 class="text-sm font-semibold text-gray-700 mb-2">Available Buckets:</h6>
                                    <div class="flex flex-wrap gap-2">
                                        ${{backend.buckets.map(bucket => `
                                            <span class="inline-flex items-center px-2 py-1 bg-indigo-50 text-indigo-700 rounded text-xs">
                                                <i class="fas fa-folder mr-1"></i>
                                                ${{bucket.name || bucket}}
                                            </span>
                                        `).join('')}}
                                    </div>
                                </div>
                            ` : ''}}
                        </div>
                        `;
                    }}).join('');
                    
                    // Update backend count in overview
                    updateMetricCard('backends-count', data.backends.length);
                    
                }} else {{
                    container.innerHTML = `
                        <div class="text-center py-16">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-gray-100 rounded-full mb-6">
                                <i class="fas fa-server text-3xl text-gray-400"></i>
                            </div>
                            <h3 class="text-xl font-semibold text-gray-900 mb-2">No Backends Configured</h3>
                            <p class="text-gray-600 max-w-md mx-auto mb-6">No storage backends are currently configured. Add backend configurations to start using distributed storage.</p>
                            <button class="btn-primary px-6 py-3 rounded-xl">
                                <i class="fas fa-plus mr-2"></i> Add Backend
                            </button>
                        </div>
                    `;
                    if (totalBadge) totalBadge.textContent = '0';
                }}
            }} catch (error) {{
                console.error('Error loading backends:', error);
                const container = document.getElementById('backends-list');
                container.innerHTML = `
                    <div class="text-center py-16">
                        <div class="inline-flex items-center justify-center w-20 h-20 bg-red-100 rounded-full mb-6">
                            <i class="fas fa-exclamation-triangle text-3xl text-red-500"></i>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Error Loading Backends</h3>
                        <p class="text-gray-600 mb-6 max-w-md mx-auto">There was an error loading the backend information. Please try refreshing the page.</p>
                        <button onclick="loadBackends()" class="btn-primary px-6 py-3 rounded-xl">
                            <i class="fas fa-sync-alt mr-2"></i> Try Again
                        </button>
                    </div>
                `;
            }}
        }}
        
        async function loadBuckets() {{
            try {{
                const response = await fetch('/api/buckets');
                if (!response.ok) throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                
                const data = await response.json();
                const container = document.getElementById('buckets-list');
                const totalBadge = document.getElementById('buckets-total-badge');
                
                if (data.buckets && data.buckets.length > 0) {{
                    // Update total badge
                    if (totalBadge) {{
                        totalBadge.textContent = data.buckets.length;
                    }}
                    
                    // Group buckets by backend
                    const bucketsByBackend = data.buckets.reduce((acc, bucket) => {{
                        const backend = bucket.backend || 'Unknown';
                        if (!acc[backend]) acc[backend] = [];
                        acc[backend].push(bucket);
                        return acc;
                    }}, {{}});
                    
                    const backendIcons = {{
                        's3': 'fab fa-aws',
                        'aws': 'fab fa-aws',
                        'gdrive': 'fab fa-google-drive',
                        'google': 'fab fa-google',
                        'github': 'fab fa-github',
                        'huggingface': 'fas fa-robot',
                        'ftp': 'fas fa-server',
                        'ssh': 'fas fa-terminal',
                        'storacha': 'fas fa-cloud',
                        'unknown': 'fas fa-folder'
                    }};
                    
                    container.innerHTML = Object.entries(bucketsByBackend).map(([backend, buckets]) => {{
                        const backendType = backend.toLowerCase();
                        const icon = Object.keys(backendIcons).find(key => backendType.includes(key)) || 'folder';
                        const iconClass = backendIcons[icon] || 'fas fa-folder';
                        const color = ['orange', 'red', 'blue', 'green', 'purple', 'pink'][Math.abs(backend.charCodeAt(0)) % 6];
                        
                        return `
                        <div class="space-y-4 fade-in">
                            <div class="flex items-center justify-between">
                                <h4 class="text-xl font-bold flex items-center text-gray-800">
                                    <div class="p-2 rounded-lg bg-gradient-to-r from-${{color}}-500 to-${{color}}-600 mr-3">
                                        <i class="${{iconClass}} text-white"></i>
                                    </div>
                                    ${{backend}} Backend
                                </h4>
                                <span class="text-sm bg-${{color}}-100 text-${{color}}-800 px-3 py-1 rounded-full font-semibold">
                                    ${{buckets.length}} bucket${{buckets.length !== 1 ? 's' : ''}}
                                </span>
                            </div>
                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                ${{buckets.map((bucket, index) => {{
                                    const bucketSize = bucket.size ? formatBytes(bucket.size) : 'Unknown size';
                                    const lastModified = bucket.last_modified ? new Date(bucket.last_modified).toLocaleDateString() : 'Unknown';
                                    
                                    return `
                                    <div class="service-item p-6 rounded-xl border border-gray-200 hover:border-${{color}}-300 transition-all duration-300" style="animation-delay: ${{index * 50}}ms">
                                        <div class="flex items-start justify-between mb-4">
                                            <div class="flex items-center">
                                                <div class="p-2 rounded-lg bg-${{color}}-100 mr-3">
                                                    <i class="fas fa-folder text-${{color}}-600"></i>
                                                </div>
                                                <div>
                                                    <h5 class="font-bold text-gray-900">${{bucket.name}}</h5>
                                                    <p class="text-sm text-gray-500">${{bucket.type || 'Standard'}}</p>
                                                </div>
                                            </div>
                                            <div class="flex items-center">
                                                <i class="fas fa-${{
                                                    bucket.status === 'active' ? 'check-circle text-green-500' :
                                                    bucket.status === 'syncing' ? 'sync text-blue-500' :
                                                    bucket.status === 'error' ? 'times-circle text-red-500' :
                                                    'question-circle text-gray-400'
                                                }}"></i>
                                            </div>
                                        </div>
                                        
                                        <div class="space-y-2 text-sm">
                                            ${{bucket.description ? `
                                                <p class="text-gray-600">${{bucket.description}}</p>
                                            ` : ''}}
                                            
                                            <div class="flex justify-between">
                                                <span class="text-gray-500">Size:</span>
                                                <span class="font-medium">${{bucketSize}}</span>
                                            </div>
                                            
                                            ${{bucket.files_count !== undefined ? `
                                                <div class="flex justify-between">
                                                    <span class="text-gray-500">Files:</span>
                                                    <span class="font-medium">${{bucket.files_count.toLocaleString()}}</span>
                                                </div>
                                            ` : ''}}
                                            
                                            <div class="flex justify-between">
                                                <span class="text-gray-500">Modified:</span>
                                                <span class="font-medium">${{lastModified}}</span>
                                            </div>
                                        </div>
                                        
                                        ${{bucket.tags && bucket.tags.length > 0 ? `
                                            <div class="mt-4 pt-3 border-t border-gray-200">
                                                <div class="flex flex-wrap gap-1">
                                                    ${{bucket.tags.map(tag => `
                                                        <span class="inline-flex items-center px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
                                                            ${{tag}}
                                                        </span>
                                                    `).join('')}}
                                                </div>
                                            </div>
                                        ` : ''}}
                                        
                                        <div class="mt-4 pt-3 border-t border-gray-200">
                                            <div class="flex space-x-2">
                                                <button class="flex-1 text-sm px-3 py-2 bg-${{color}}-50 text-${{color}}-700 rounded-lg hover:bg-${{color}}-100 transition-colors">
                                                    <i class="fas fa-eye mr-1"></i> View
                                                </button>
                                                <button class="flex-1 text-sm px-3 py-2 bg-gray-50 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors">
                                                    <i class="fas fa-download mr-1"></i> Sync
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                    `;
                                }}).join('')}}
                            </div>
                        </div>
                        `;
                    }}).join('');
                    
                    // Update bucket count in overview
                    updateMetricCard('buckets-count', data.buckets.length);
                    
                }} else {{
                    container.innerHTML = `
                        <div class="text-center py-16">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-gray-100 rounded-full mb-6">
                                <i class="fas fa-folder text-3xl text-gray-400"></i>
                            </div>
                            <h3 class="text-xl font-semibold text-gray-900 mb-2">No Buckets Found</h3>
                            <p class="text-gray-600 max-w-md mx-auto mb-6">No storage buckets are currently available. Create or connect backends to start managing your data.</p>
                            <button onclick="showCreateBucketModal()" class="btn-primary px-6 py-3 rounded-xl">
                                <i class="fas fa-plus mr-2"></i> Create Bucket
                            </button>
                        </div>
                    `;
                    if (totalBadge) totalBadge.textContent = '0';
                }}
            }} catch (error) {{
                console.error('Error loading buckets:', error);
                const container = document.getElementById('buckets-list');
                container.innerHTML = `
                    <div class="text-center py-16">
                        <div class="inline-flex items-center justify-center w-20 h-20 bg-red-100 rounded-full mb-6">
                            <i class="fas fa-exclamation-triangle text-3xl text-red-500"></i>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Error Loading Buckets</h3>
                        <p class="text-gray-600 mb-6 max-w-md mx-auto">There was an error loading the bucket information. Please try refreshing the page.</p>
                        <button onclick="loadBuckets()" class="btn-primary px-6 py-3 rounded-xl">
                            <i class="fas fa-sync-alt mr-2"></i> Try Again
                        </button>
                    </div>
                `;
            }}
        }}
        
        async function loadConfig() {{
            try {{
                const [configResponse, backendResponse] = await Promise.all([
                    fetch('/api/config'),
                    fetch('/api/config/backends')
                ]);
                
                if (!configResponse.ok) throw new Error(`Config HTTP ${{configResponse.status}}: ${{configResponse.statusText}}`);
                if (!backendResponse.ok) throw new Error(`Backend Config HTTP ${{backendResponse.status}}: ${{backendResponse.statusText}}`);
                
                const configData = await configResponse.json();
                const backendData = await backendResponse.json();
                
                const container = document.getElementById('config-content');
                const backendContainer = document.getElementById('backend-configs-content');
                
                // Main Configuration
                if (configData.config || configData.data_dir) {{
                    container.innerHTML = `
                        <div class="space-y-6">
                            <!-- Data Directory -->
                            <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                                <h4 class="text-lg font-bold mb-4 flex items-center text-blue-800">
                                    <i class="fas fa-folder text-blue-600 mr-3"></i>
                                    Data Directory
                                </h4>
                                <div class="bg-white rounded-lg p-4 border border-blue-200">
                                    <code class="text-sm text-gray-800 font-mono break-all">${{configData.data_dir || '~/.ipfs_kit'}}</code>
                                </div>
                            </div>
                            
                            ${{configData.config?.main ? `
                                <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-6 border border-purple-200">
                                    <h4 class="text-lg font-bold mb-4 flex items-center text-purple-800">
                                        <i class="fas fa-cog text-purple-600 mr-3"></i>
                                        Main Configuration
                                    </h4>
                                    <div class="bg-white rounded-lg p-4 border border-purple-200 overflow-hidden">
                                        <pre class="text-sm text-gray-800 overflow-auto max-h-64 whitespace-pre-wrap">${{JSON.stringify(configData.config.main, null, 2)}}</pre>
                                    </div>
                                </div>
                            ` : ''}}
                            
                            ${{configData.config?.metadata ? `
                                <div class="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-6 border border-green-200">
                                    <h4 class="text-lg font-bold mb-4 flex items-center text-green-800">
                                        <i class="fas fa-info-circle text-green-600 mr-3"></i>
                                        Metadata
                                    </h4>
                                    <div class="bg-white rounded-lg p-4 border border-green-200 overflow-hidden">
                                        <pre class="text-sm text-gray-800 overflow-auto max-h-64 whitespace-pre-wrap">${{JSON.stringify(configData.config.metadata, null, 2)}}</pre>
                                    </div>
                                </div>
                            ` : ''}}
                            
                            <!-- Timestamp -->
                            <div class="text-center">
                                <div class="inline-flex items-center px-4 py-2 bg-gray-100 rounded-full text-sm text-gray-600">
                                    <i class="fas fa-clock mr-2"></i>
                                    Last updated: ${{configData.timestamp ? new Date(configData.timestamp).toLocaleString() : 'Unknown'}}
                                </div>
                            </div>
                        </div>
                    `;
                }} else {{
                    container.innerHTML = `
                        <div class="text-center py-16">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-gray-100 rounded-full mb-6">
                                <i class="fas fa-cog text-3xl text-gray-400"></i>
                            </div>
                            <h3 class="text-xl font-semibold text-gray-900 mb-2">No Configuration Found</h3>
                            <p class="text-gray-600 max-w-md mx-auto">No main configuration data is available. The system may be using default settings.</p>
                        </div>
                    `;
                }}
                
                // Backend Configurations
                if (backendData && Object.keys(backendData).length > 0) {{
                    const configs = Object.entries(backendData);
                    backendContainer.innerHTML = `
                        <div class="grid gap-6">
                            ${{configs.map(([name, config], index) => {{
                                const backendType = name.toLowerCase();
                                const icon = 
                                    backendType.includes('s3') || backendType.includes('aws') ? 'fab fa-aws' :
                                    backendType.includes('github') ? 'fab fa-github' :
                                    backendType.includes('gdrive') || backendType.includes('google') ? 'fab fa-google-drive' :
                                    backendType.includes('huggingface') ? 'fas fa-robot' :
                                    backendType.includes('ftp') ? 'fas fa-server' :
                                    backendType.includes('ssh') ? 'fas fa-terminal' :
                                    'fas fa-server';
                                
                                const color = ['blue', 'green', 'purple', 'orange', 'pink', 'indigo'][index % 6];
                                
                                return `
                                <div class="bg-gradient-to-r from-${{color}}-50 to-${{color}}-100 rounded-xl p-6 border border-${{color}}-200 fade-in" style="animation-delay: ${{index * 100}}ms">
                                    <div class="flex items-center justify-between mb-4">
                                        <h4 class="text-lg font-bold flex items-center text-${{color}}-800">
                                            <div class="p-2 rounded-lg bg-${{color}}-200 mr-3">
                                                <i class="${{icon}} text-${{color}}-700"></i>
                                            </div>
                                            ${{name}}
                                        </h4>
                                        <div class="flex items-center space-x-2">
                                            <span class="px-3 py-1 rounded-full text-xs font-semibold bg-${{color}}-200 text-${{color}}-800">
                                                ${{config.type?.toUpperCase() || 'CONFIG'}}
                                            </span>
                                            <span class="px-3 py-1 rounded-full text-xs font-semibold bg-green-200 text-green-800">
                                                <i class="fas fa-check mr-1"></i>ACTIVE
                                            </span>
                                        </div>
                                    </div>
                                    
                                    <div class="mb-4 text-sm text-${{color}}-700">
                                        <div class="flex items-center mb-2">
                                            <i class="fas fa-file mr-2"></i>
                                            <code class="bg-white px-2 py-1 rounded text-xs">${{config.file}}</code>
                                        </div>
                                        <div class="flex items-center">
                                            <i class="fas fa-clock mr-2"></i>
                                            <span>Modified: ${{config.last_modified ? new Date(config.last_modified).toLocaleString() : 'Unknown'}}</span>
                                        </div>
                                    </div>
                                    
                                    <details class="cursor-pointer">
                                        <summary class="text-sm font-semibold text-${{color}}-700 hover:text-${{color}}-900 flex items-center transition-colors">
                                            <i class="fas fa-eye mr-2"></i>
                                            View Configuration Details
                                            <i class="fas fa-chevron-down ml-auto transition-transform duration-200"></i>
                                        </summary>
                                        <div class="mt-4 bg-white rounded-lg p-4 border border-${{color}}-200 overflow-hidden">
                                            <pre class="text-xs text-gray-800 overflow-auto max-h-64 whitespace-pre-wrap">${{JSON.stringify(config.config, null, 2)}}</pre>
                                        </div>
                                    </details>
                                    
                                    <div class="mt-4 pt-4 border-t border-${{color}}-200">
                                        <div class="flex space-x-2">
                                            <button class="flex-1 text-sm px-4 py-2 bg-${{color}}-200 text-${{color}}-800 rounded-lg hover:bg-${{color}}-300 transition-colors">
                                                <i class="fas fa-edit mr-1"></i> Edit
                                            </button>
                                            <button class="flex-1 text-sm px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors">
                                                <i class="fas fa-copy mr-1"></i> Duplicate
                                            </button>
                                            <button class="flex-1 text-sm px-4 py-2 bg-red-200 text-red-700 rounded-lg hover:bg-red-300 transition-colors">
                                                <i class="fas fa-trash mr-1"></i> Delete
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                `;
                            }}).join('')}}
                        </div>
                    `;
                }} else {{
                    backendContainer.innerHTML = `
                        <div class="text-center py-16">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-gray-100 rounded-full mb-6">
                                <i class="fas fa-server text-3xl text-gray-400"></i>
                            </div>
                            <h3 class="text-xl font-semibold text-gray-900 mb-2">No Backend Configurations</h3>
                            <p class="text-gray-600 max-w-md mx-auto mb-6">No backend configurations are currently available. Add backend configurations to enable storage services.</p>
                            <button class="btn-primary px-6 py-3 rounded-xl">
                                <i class="fas fa-plus mr-2"></i> Add Backend Configuration
                            </button>
                        </div>
                    `;
                }}
                
            }} catch (error) {{
                console.error('Error loading configuration:', error);
                const container = document.getElementById('config-content');
                const backendContainer = document.getElementById('backend-configs-content');
                
                const errorHtml = `
                    <div class="text-center py-16">
                        <div class="inline-flex items-center justify-center w-20 h-20 bg-red-100 rounded-full mb-6">
                            <i class="fas fa-exclamation-triangle text-3xl text-red-500"></i>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Error Loading Configuration</h3>
                        <p class="text-gray-600 mb-6 max-w-md mx-auto">There was an error loading the configuration data. Please try refreshing the page.</p>
                        <button onclick="loadConfig()" class="btn-primary px-6 py-3 rounded-xl">
                            <i class="fas fa-sync-alt mr-2"></i> Try Again
                        </button>
                    </div>
                `;
                
                container.innerHTML = errorHtml;
                backendContainer.innerHTML = errorHtml;
            }}
        }}
        
        async function loadDetailedMetrics() {{
            try {{
                const response = await fetch('/api/system/metrics');
                if (!response.ok) throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                
                const data = await response.json();
                const container = document.getElementById('detailed-metrics');
                
                container.innerHTML = `
                    <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                        <!-- CPU Metrics -->
                        <div class="card p-6 rounded-2xl">
                            <h4 class="text-lg font-bold mb-4 flex items-center">
                                <div class="p-2 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-600 mr-3">
                                    <i class="fas fa-microchip text-white"></i>
                                </div>
                                CPU Information
                            </h4>
                            <div class="space-y-4">
                                <div class="flex justify-between items-center">
                                    <span class="text-gray-600 font-medium">Current Usage</span>
                                    <span class="text-2xl font-bold text-blue-600">${{data.cpu.usage.toFixed(1)}}%</span>
                                </div>
                                <div class="progress-bar h-3">
                                    <div class="progress-fill bg-gradient-to-r from-blue-400 to-blue-600" style="width: ${{data.cpu.usage}}%"></div>
                                </div>
                                <div class="grid grid-cols-2 gap-4 text-sm">
                                    <div class="bg-gray-50 rounded-lg p-3">
                                        <div class="text-gray-500">Cores</div>
                                        <div class="font-semibold text-lg">${{data.cpu.cores}}</div>
                                    </div>
                                    <div class="bg-gray-50 rounded-lg p-3">
                                        <div class="text-gray-500">Load (1m)</div>
                                        <div class="font-semibold text-lg">${{data.cpu.load_avg[0].toFixed(2)}}</div>
                                    </div>
                                </div>
                                ${{data.cpu.load_avg.length >= 3 ? `
                                    <div class="grid grid-cols-3 gap-2 text-xs">
                                        <div class="text-center p-2 bg-blue-50 rounded">
                                            <div class="text-gray-500">1m</div>
                                            <div class="font-medium">${{data.cpu.load_avg[0].toFixed(2)}}</div>
                                        </div>
                                        <div class="text-center p-2 bg-blue-50 rounded">
                                            <div class="text-gray-500">5m</div>
                                            <div class="font-medium">${{data.cpu.load_avg[1].toFixed(2)}}</div>
                                        </div>
                                        <div class="text-center p-2 bg-blue-50 rounded">
                                            <div class="text-gray-500">15m</div>
                                            <div class="font-medium">${{data.cpu.load_avg[2].toFixed(2)}}</div>
                                        </div>
                                    </div>
                                ` : ''}}
                            </div>
                        </div>
                        
                        <!-- Memory Metrics -->
                        <div class="card p-6 rounded-2xl">
                            <h4 class="text-lg font-bold mb-4 flex items-center">
                                <div class="p-2 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 mr-3">
                                    <i class="fas fa-memory text-white"></i>
                                </div>
                                Memory Information
                            </h4>
                            <div class="space-y-4">
                                <div class="flex justify-between items-center">
                                    <span class="text-gray-600 font-medium">Usage</span>
                                    <span class="text-2xl font-bold text-green-600">${{data.memory.percent.toFixed(1)}}%</span>
                                </div>
                                <div class="progress-bar h-3">
                                    <div class="progress-fill bg-gradient-to-r from-green-400 to-green-600" style="width: ${{data.memory.percent}}%"></div>
                                </div>
                                <div class="grid grid-cols-2 gap-4 text-sm">
                                    <div class="bg-gray-50 rounded-lg p-3">
                                        <div class="text-gray-500">Used</div>
                                        <div class="font-semibold text-lg">${{formatBytes(data.memory.used)}}</div>
                                    </div>
                                    <div class="bg-gray-50 rounded-lg p-3">
                                        <div class="text-gray-500">Total</div>
                                        <div class="font-semibold text-lg">${{formatBytes(data.memory.total)}}</div>
                                    </div>
                                </div>
                                <div class="bg-green-50 rounded-lg p-3">
                                    <div class="text-gray-500 text-sm">Available</div>
                                    <div class="font-semibold text-lg text-green-700">${{formatBytes(data.memory.total - data.memory.used)}}</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Disk Metrics -->
                        <div class="card p-6 rounded-2xl">
                            <h4 class="text-lg font-bold mb-4 flex items-center">
                                <div class="p-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-600 mr-3">
                                    <i class="fas fa-hdd text-white"></i>
                                </div>
                                Disk Information
                            </h4>
                            <div class="space-y-4">
                                <div class="flex justify-between items-center">
                                    <span class="text-gray-600 font-medium">Usage</span>
                                    <span class="text-2xl font-bold text-purple-600">${{data.disk.percent.toFixed(1)}}%</span>
                                </div>
                                <div class="progress-bar h-3">
                                    <div class="progress-fill bg-gradient-to-r from-purple-400 to-purple-600" style="width: ${{data.disk.percent}}%"></div>
                                </div>
                                <div class="grid grid-cols-2 gap-4 text-sm">
                                    <div class="bg-gray-50 rounded-lg p-3">
                                        <div class="text-gray-500">Used</div>
                                        <div class="font-semibold text-lg">${{formatBytes(data.disk.used)}}</div>
                                    </div>
                                    <div class="bg-gray-50 rounded-lg p-3">
                                        <div class="text-gray-500">Total</div>
                                        <div class="font-semibold text-lg">${{formatBytes(data.disk.total)}}</div>
                                    </div>
                                </div>
                                <div class="bg-purple-50 rounded-lg p-3">
                                    <div class="text-gray-500 text-sm">Free Space</div>
                                    <div class="font-semibold text-lg text-purple-700">${{formatBytes(data.disk.total - data.disk.used)}}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Network Statistics -->
                    <div class="mt-6 card p-6 rounded-2xl">
                        <h4 class="text-lg font-bold mb-4 flex items-center">
                            <div class="p-2 rounded-lg bg-gradient-to-r from-indigo-500 to-blue-600 mr-3">
                                <i class="fas fa-network-wired text-white"></i>
                            </div>
                            Network Statistics
                        </h4>
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-200">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-blue-600 text-sm font-medium">Bytes Sent</div>
                                        <div class="text-2xl font-bold text-blue-800">${{formatBytes(data.network.sent)}}</div>
                                    </div>
                                    <i class="fas fa-upload text-2xl text-blue-500"></i>
                                </div>
                            </div>
                            <div class="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-4 border border-green-200">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-green-600 text-sm font-medium">Bytes Received</div>
                                        <div class="text-2xl font-bold text-green-800">${{formatBytes(data.network.recv)}}</div>
                                    </div>
                                    <i class="fas fa-download text-2xl text-green-500"></i>
                                </div>
                            </div>
                            <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-4 border border-purple-200">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-purple-600 text-sm font-medium">Total Traffic</div>
                                        <div class="text-2xl font-bold text-purple-800">${{formatBytes(data.network.sent + data.network.recv)}}</div>
                                    </div>
                                    <i class="fas fa-exchange-alt text-2xl text-purple-500"></i>
                                </div>
                            </div>
                            <div class="bg-gradient-to-r from-yellow-50 to-orange-50 rounded-xl p-4 border border-yellow-200">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-yellow-600 text-sm font-medium">Last Updated</div>
                                        <div class="text-sm font-bold text-yellow-800">${{new Date(data.timestamp).toLocaleTimeString()}}</div>
                                    </div>
                                    <i class="fas fa-clock text-2xl text-yellow-500"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- System Information -->
                    <div class="mt-6 card p-6 rounded-2xl">
                        <h4 class="text-lg font-bold mb-4 flex items-center">
                            <div class="p-2 rounded-lg bg-gradient-to-r from-gray-500 to-gray-600 mr-3">
                                <i class="fas fa-info-circle text-white"></i>
                            </div>
                            System Information
                        </h4>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                            <div class="bg-gray-50 rounded-lg p-4">
                                <div class="text-gray-500 mb-1">Platform</div>
                                <div class="font-semibold">${{navigator.platform}}</div>
                            </div>
                            <div class="bg-gray-50 rounded-lg p-4">
                                <div class="text-gray-500 mb-1">User Agent</div>
                                <div class="font-semibold text-xs">${{navigator.userAgent.split(' ')[0]}}</div>
                            </div>
                            <div class="bg-gray-50 rounded-lg p-4">
                                <div class="text-gray-500 mb-1">Timestamp</div>
                                <div class="font-semibold">${{new Date(data.timestamp).toLocaleString()}}</div>
                            </div>
                        </div>
                    </div>
                `;
            }} catch (error) {{
                console.error('Error loading detailed metrics:', error);
                const container = document.getElementById('detailed-metrics');
                container.innerHTML = `
                    <div class="text-center py-16">
                        <div class="inline-flex items-center justify-center w-20 h-20 bg-red-100 rounded-full mb-6">
                            <i class="fas fa-exclamation-triangle text-3xl text-red-500"></i>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Error Loading Metrics</h3>
                        <p class="text-gray-600 mb-6 max-w-md mx-auto">There was an error loading the system metrics. Please try refreshing the page.</p>
                        <button onclick="loadDetailedMetrics()" class="btn-primary px-6 py-3 rounded-xl">
                            <i class="fas fa-sync-alt mr-2"></i> Try Again
                        </button>
                    </div>
                `;
            }}
        }}
        
        function loadTabData(tabName) {{
            switch (tabName) {{
                case 'overview':
                    loadSystemOverview();
                    break;
                case 'services':
                    loadServices();
                    break;
                case 'backends':
                    loadBackends();
                    break;
                case 'buckets':
                    loadBuckets();
                    break;
                case 'metrics':
                    loadDetailedMetrics();
                    break;
                case 'config':
                    loadConfig();
                    break;
            }}
        }}
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {{
            // Set up clock
            updateClock();
            setInterval(updateClock, 1000);
            
            // Initial data load
            loadSystemOverview();
            
            // Set up auto-refresh with smart timing
            updateInterval = setInterval(function() {{
                const currentTab = document.querySelector('.tab-content.active')?.id?.replace('-tab', '');
                if (currentTab === 'overview' && !isUpdating) {{
                    loadSystemOverview();
                }}
            }}, {self.update_interval * 1000});
            
            // Add smooth transitions to metric cards
            document.querySelectorAll('.metric-card').forEach((card, index) => {{
                card.style.animationDelay = `${{index * 100}}ms`;
                card.classList.add('fade-in');
            }});
            
            // Add keyboard shortcuts
            document.addEventListener('keydown', function(e) {{
                if (e.ctrlKey || e.metaKey) {{
                    switch(e.key) {{
                        case 'r':
                            e.preventDefault();
                            refreshData();
                            break;
                        case '1':
                            e.preventDefault();
                            showTab('overview');
                            break;
                        case '2':
                            e.preventDefault();
                            showTab('services');
                            break;
                        case '3':
                            e.preventDefault();
                            showTab('backends');
                            break;
                    }}
                }}
                
                if (e.key === 'Escape') {{
                    closeMobileMenu();
                }}
            }});
            
            // Add loading indicators for better UX
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        entry.target.classList.add('fade-in');
                    }}
                }});
            }});
            
            document.querySelectorAll('.card').forEach(card => {{
                observer.observe(card);
            }});
        }});
        
        // Enhanced refresh function with user feedback
        async function refreshData() {{
            const refreshBtn = document.querySelector('button[onclick="refreshData()"]');
            const originalText = refreshBtn?.innerHTML;
            
            if (refreshBtn) {{
                refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Refreshing...';
                refreshBtn.disabled = true;
            }}
            
            try {{
                const currentTab = document.querySelector('.tab-content.active')?.id?.replace('-tab', '');
                await loadTabData(currentTab);
                
                // Show success feedback
                if (refreshBtn) {{
                    refreshBtn.innerHTML = '<i class="fas fa-check mr-2"></i> Updated';
                    setTimeout(() => {{
                        refreshBtn.innerHTML = originalText;
                        refreshBtn.disabled = false;
                    }}, 1500);
                }}
            }} catch (error) {{
                console.error('Error refreshing data:', error);
                if (refreshBtn) {{
                    refreshBtn.innerHTML = '<i class="fas fa-exclamation-triangle mr-2"></i> Error';
                    setTimeout(() => {{
                        refreshBtn.innerHTML = originalText;
                        refreshBtn.disabled = false;
                    }}, 2000);
                }}
            }}
        }}
        
        async function loadTabData(tabName) {{
            switch (tabName) {{
                case 'overview':
                    return await loadSystemOverview();
                case 'services':
                    return await loadServices();
                case 'backends':
                    return await loadBackends();
                case 'buckets':
                    return await loadBuckets();
                case 'metrics':
                    return await loadDetailedMetrics();
                case 'config':
                    return await loadConfig();
                default:
                    return Promise.resolve();
            }}
        }}
        
        // Bucket creation functionality
        function showCreateBucketModal() {{
            const modal = document.getElementById('createBucketModal');
            if (!modal) {{
                // Create the modal if it doesn't exist
                createBucketModal();
            }}
            document.getElementById('createBucketModal').style.display = 'flex';
        }}
        
        function hideCreateBucketModal() {{
            document.getElementById('createBucketModal').style.display = 'none';
            // Reset form
            document.getElementById('bucketName').value = '';
            document.getElementById('bucketType').value = 'general';
            document.getElementById('bucketDescription').value = '';
        }}
        
        function createBucketModal() {{
            const modalHTML = `
                <div id="createBucketModal" style="display: none;" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div class="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4">
                        <div class="p-6">
                            <div class="flex items-center justify-between mb-4">
                                <h3 class="text-xl font-bold text-gray-900">Create New Bucket</h3>
                                <button onclick="hideCreateBucketModal()" class="text-gray-400 hover:text-gray-600">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                            
                            <form onsubmit="createBucket(event)">
                                <div class="space-y-4">
                                    <div>
                                        <label for="bucketName" class="block text-sm font-medium text-gray-700 mb-1">
                                            Bucket Name <span class="text-red-500">*</span>
                                        </label>
                                        <input type="text" id="bucketName" name="bucketName" required
                                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                               placeholder="Enter bucket name">
                                    </div>
                                    
                                    <div>
                                        <label for="bucketType" class="block text-sm font-medium text-gray-700 mb-1">
                                            Bucket Type
                                        </label>
                                        <select id="bucketType" name="bucketType"
                                                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                                            <option value="general">General</option>
                                            <option value="dataset">Dataset</option>
                                            <option value="media">Media</option>
                                            <option value="archive">Archive</option>
                                            <option value="knowledge">Knowledge</option>
                                            <option value="temp">Temporary</option>
                                        </select>
                                    </div>
                                    
                                    <div>
                                        <label for="bucketDescription" class="block text-sm font-medium text-gray-700 mb-1">
                                            Description
                                        </label>
                                        <textarea id="bucketDescription" name="bucketDescription" rows="3"
                                                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                  placeholder="Optional bucket description"></textarea>
                                    </div>
                                </div>
                                
                                <div class="flex space-x-3 mt-6">
                                    <button type="button" onclick="hideCreateBucketModal()" 
                                            class="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">
                                        Cancel
                                    </button>
                                    <button type="submit" 
                                            class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                                        <i class="fas fa-plus mr-2"></i> Create Bucket
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }}
        
        async function createBucket(event) {{
            event.preventDefault();
            
            const bucketName = document.getElementById('bucketName').value.trim();
            const bucketType = document.getElementById('bucketType').value;
            const bucketDescription = document.getElementById('bucketDescription').value.trim();
            
            if (!bucketName) {{
                alert('Please enter a bucket name');
                return;
            }}
            
            const submitBtn = event.target.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            
            try {{
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Creating...';
                submitBtn.disabled = true;
                
                const response = await fetch('/api/buckets', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        bucket_name: bucketName,
                        bucket_type: bucketType,
                        description: bucketDescription
                    }})
                }});
                
                const result = await response.json();
                
                if (result.success) {{
                    // Show success message
                    submitBtn.innerHTML = '<i class="fas fa-check mr-2"></i> Created!';
                    
                    // Hide modal after a delay
                    setTimeout(() => {{
                        hideCreateBucketModal();
                        // Refresh buckets list
                        loadBuckets();
                    }}, 1000);
                }} else {{
                    throw new Error(result.error || 'Failed to create bucket');
                }}
            }} catch (error) {{
                console.error('Error creating bucket:', error);
                alert(`Error creating bucket: ${{error.message}}`);
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }}
        }}
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', function() {{
            if (updateInterval) {{
                clearInterval(updateInterval);
            }}
        }});
        
        // Add service worker for offline functionality (optional)
        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.register('/sw.js').catch(function(error) {{
                console.log('ServiceWorker registration failed: ', error);
            }});
        }}
        
        // Performance monitoring
        window.addEventListener('load', function() {{
            const loadTime = performance.now();
            console.log(`Dashboard loaded in ${{loadTime.toFixed(2)}}ms`);
        }});
    </script>
</body>
</html>
        """
    
    async def start(self):
        """Start the unified MCP dashboard server."""
        print(f"🚀 Starting Unified MCP Dashboard on http://{self.host}:{self.port}")
        print(f"📊 Dashboard available at: http://{self.host}:{self.port}")
        print(f"🔧 MCP endpoints available at: http://{self.host}:{self.port}/mcp/*")
        
        # Create server config
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if self.debug else "warning"
        )
        
        # Create and start server
        server = uvicorn.Server(config)
        await server.serve()

    def run(self):
        """Run the unified MCP dashboard server (sync version)."""
        print(f"🚀 Starting Unified MCP Dashboard on http://{self.host}:{self.port}")
        print(f"📊 Dashboard available at: http://{self.host}:{self.port}")
        print(f"🔧 MCP endpoints available at: http://{self.host}:{self.port}/mcp/*")
        
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if self.debug else "warning"
        )


async def main():
    """Main entry point for unified MCP dashboard."""
    config = {
        'host': '127.0.0.1',
        'port': 8004,
        'data_dir': '~/.ipfs_kit',
        'debug': True,
        'update_interval': 3
    }
    
    dashboard = UnifiedMCPDashboard(config)
    await dashboard.start()


if __name__ == "__main__":
    asyncio.run(main())

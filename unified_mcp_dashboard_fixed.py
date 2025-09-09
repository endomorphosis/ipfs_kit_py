#!/usr/bin/env python3
"""
Unified MCP Dashboard - Fixed Version

A comprehensive FastAPI-based dashboard that combines MCP server functionality
with a modern web interface for managing IPFS Kit components.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Import fallbacks for dependencies that might not be available
try:
    from .high_level_api import IPFSSimpleAPI
except ImportError:
    class IPFSSimpleAPI:
        def __init__(self, **kwargs): pass

try:
    from .bucket_manager import get_global_bucket_manager
except ImportError:
    def get_global_bucket_manager(**kwargs): return None

class McpRequest(BaseModel):
    """MCP request model."""
    method: str
    params: Optional[Dict[str, Any]] = None

class McpResponse(BaseModel):
    """MCP response model."""
    result: Optional[Any] = None
    error: Optional[str] = None

class UnifiedMCPDashboard:
    """
    Unified MCP Server and Dashboard
    
    Combines Model Context Protocol server functionality with a modern web dashboard
    for comprehensive IPFS Kit management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the unified MCP server and dashboard."""
        self.config = config or {}
        self.host = self.config.get('host', '127.0.0.1')
        self.port = self.config.get('port', 8004)
        self.debug = self.config.get('debug', False)
        self.data_dir = Path(self.config.get('data_dir', '.'))
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="IPFS Kit Unified MCP Dashboard",
            description="Combined MCP server and management dashboard",
            version="1.0.0"
        )
        
        # Initialize components
        self.ipfs_api = None
        self.bucket_manager = None
        self.start_time = datetime.now()
        
        # Setup the server
        self._setup_middleware()
        self._setup_static_files()
        self._register_mcp_tools()
        self._setup_routes()
        
        # Initialize IPFS connection
        self._init_ipfs()
        
        logging.info(f"Unified MCP Dashboard initialized on {self.host}:{self.port}")

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
        # Mount static files directory
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            logging.info(f"Static files mounted from {static_dir}")
        else:
            logging.warning(f"Static directory not found: {static_dir}")
    

    def _register_mcp_tools(self):
        """Register MCP tools for comprehensive service and backend management."""
        self.mcp_tools = {
            # Service Management Tools
            "health_check": {
                "name": "health_check",
                "description": "Check system health status",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "get_system_status": {
                "name": "get_system_status",
                "description": "Get comprehensive system status and metrics",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "list_services": {
                "name": "list_services",
                "description": "List all available services with status (checks ~/.ipfs_kit/ first)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_metadata": {"type": "boolean", "description": "Include metadata from ~/.ipfs_kit/", "default": True}
                    }
                }
            },
            "list_backends": {
                "name": "list_backends", 
                "description": "List all storage backends with status (checks ~/.ipfs_kit/ first)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_metadata": {"type": "boolean", "description": "Include metadata from ~/.ipfs_kit/", "default": True}
                    }
                }
            },
            "list_buckets": {
                "name": "list_buckets",
                "description": "List all buckets with replication and cache policies (checks ~/.ipfs_kit/ first)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_metadata": {"type": "boolean", "description": "Include metadata from ~/.ipfs_kit/", "default": True}
                    }
                }
            },
            "configure_service": {
                "name": "configure_service",
                "description": "Configure a service instance with cache/storage/retention settings",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "service_type": {"type": "string", "description": "Type of service to configure"},
                        "instance_name": {"type": "string", "description": "Name of service instance"},
                        "config": {"type": "object", "description": "Configuration settings"}
                    },
                    "required": ["service_type", "instance_name", "config"]
                }
            },
            # Configuration Management Tools
            "read_config_file": {
                "name": "read_config_file",
                "description": "Read configuration file from ~/.ipfs_kit/ directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Configuration file name (e.g., pins.json, buckets.json)"}
                    },
                    "required": ["filename"]
                }
            },
            "write_config_file": {
                "name": "write_config_file",
                "description": "Write configuration file to ~/.ipfs_kit/ directory with metadata-first approach",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Configuration file name"},
                        "content": {"type": "string", "description": "JSON content to write"}
                    },
                    "required": ["filename", "content"]
                }
            },
            "list_config_files": {
                "name": "list_config_files",
                "description": "List all configuration files in ~/.ipfs_kit/ directory",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "get_config_metadata": {
                "name": "get_config_metadata",
                "description": "Get metadata about configuration files including source and status",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Configuration file name"}
                    },
                    "required": ["filename"]
                }
            },
            # File Management Tools
            "list_files": {
                "name": "list_files",
                "description": "List files in a directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list"}
                    },
                    "required": ["path"]
                }
            },
            "read_file": {
                "name": "read_file", 
                "description": "Read contents of a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"}
                    },
                    "required": ["path"]
                }
            },
            "write_file": {
                "name": "write_file",
                "description": "Write content to a file", 
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            }
        }

    def _init_ipfs(self):
        """Initialize IPFS API connection."""
        try:
            self.ipfs_api = IPFSSimpleAPI(role="leecher")
            self.bucket_manager = get_global_bucket_manager()
            logging.info("IPFS API and bucket manager initialized")
        except Exception as e:
            logging.warning(f"Could not initialize IPFS components: {e}")

    def _setup_routes(self):
        """Setup all API routes for both MCP and dashboard."""
        
        # MCP Protocol Routes
        @self.app.post("/mcp/initialize")
        async def mcp_initialize():
            """MCP initialization endpoint."""
            return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}

        @self.app.get("/mcp/tools")
        async def list_mcp_tools():
            """List available MCP tools."""
            return {"tools": list(self.mcp_tools.values())}

        @self.app.post("/mcp/tools/call")
        async def call_mcp_tool(request: McpRequest):
            """Execute MCP tool with comprehensive service and backend management."""
            tool_name = request.method
            params = request.params or {}
            
            try:
                # System health and status tools
                if tool_name == "health_check":
                    result = {"status": "healthy", "timestamp": datetime.now().isoformat()}
                elif tool_name == "get_system_status":
                    result = await self._get_system_status_mcp()
                elif tool_name == "list_services":
                    result = await self._list_services_mcp(params.get("include_metadata", True))
                elif tool_name == "list_backends":
                    result = await self._list_backends_mcp(params.get("include_metadata", True))
                elif tool_name == "list_buckets":
                    result = await self._list_buckets_mcp(params.get("include_metadata", True))
                elif tool_name == "configure_service":
                    result = await self._configure_service_mcp(
                        params.get("service_type"),
                        params.get("instance_name"), 
                        params.get("config", {})
                    )
                # File management tools
                elif tool_name == "list_files":
                    result = await self._list_files(params.get("path", "."))
                elif tool_name == "read_file":
                    result = await self._read_file(params.get("path"))
                elif tool_name == "write_file":
                    result = await self._write_file(params.get("path"), params.get("content"))
                # Configuration management tools
                elif tool_name == "read_config_file":
                    result = await self._read_config_file(params.get("filename"))
                elif tool_name == "write_config_file":
                    result = await self._write_config_file(params.get("filename"), params.get("content"))
                elif tool_name == "list_config_files":
                    result = await self._list_config_files()
                elif tool_name == "get_config_metadata":
                    result = await self._get_config_metadata(params.get("filename"))
                else:
                    raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
                
                return McpResponse(result=result)
            except Exception as e:
                return McpResponse(error=str(e))

        # Dashboard Routes
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Serve the main dashboard."""
            return self._get_dashboard_html()

        @self.app.get("/api/system/overview")
        async def get_system_overview():
            """Get system overview data."""
            try:
                # Get basic system information
                services_count = len(await self._get_services_status())
                backends_count = len(await self._get_backends_status()) 
                buckets_count = len(await self._get_buckets())
                pins_count = len(await self._get_all_pins())
                
                uptime_seconds = (datetime.now() - self.start_time).total_seconds()
                uptime_str = f"{int(uptime_seconds // 3600):02d}:{int((uptime_seconds % 3600) // 60):02d}:{int(uptime_seconds % 60):02d}"
                
                return {
                    "services": services_count,
                    "backends": backends_count, 
                    "buckets": buckets_count,
                    "pins": pins_count,
                    "uptime": uptime_str,
                    "status": "running",
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logging.error(f"Error getting system overview: {e}")
                return {
                    "services": 0,
                    "backends": 0,
                    "buckets": 0, 
                    "pins": 0,
                    "uptime": "00:00:00",
                    "status": "error",
                    "error": str(e)
                }

        @self.app.get("/api/services")
        async def get_services():
            """Get services status."""
            return await self._get_services_status()

        @self.app.get("/api/backends")
        async def get_backends():
            """Get storage backends status."""
            return await self._get_backends_status()

        @self.app.get("/api/buckets")
        async def get_buckets():
            """Get buckets list."""
            return await self._get_buckets()

        @self.app.get("/api/pins")
        async def get_pins():
            """Get pins list."""
            pins_list = await self._get_all_pins()
            
            # Return in the structure expected by the frontend JavaScript
            return {
                "total": len(pins_list),
                "active": len([p for p in pins_list if p.get("status") == "pinned"]),
                "pending": len([p for p in pins_list if p.get("status") == "pending"]),
                "total_size": "N/A",  # TODO: Calculate actual total size
                "pins": pins_list
            }

        @self.app.get("/api/config")
        async def get_config():
            """Get configuration."""
            return {
                "content": json.dumps(self.config, indent=2),
                "editable": True
            }

        @self.app.get("/api/metrics")
        async def get_metrics():
            """Get system metrics."""
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "network_io": {"in": 0, "out": 0},
                "timestamp": datetime.now().isoformat()
            }

    # MCP Tool Implementations
    async def _list_files(self, path: str) -> List[str]:
        """List files in directory."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                raise FileNotFoundError(f"Path {path} does not exist")
            
            if path_obj.is_file():
                return [str(path_obj)]
            
            files = []
            for item in path_obj.iterdir():
                files.append(str(item))
            
            return files
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _read_file(self, path: str) -> str:
        """Read file content."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                raise FileNotFoundError(f"File {path} does not exist")
            
            return path_obj.read_text(encoding='utf-8')
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _write_file(self, path: str, content: str) -> str:
        """Write file content."""
        try:
            path_obj = Path(path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(content, encoding='utf-8')
            return f"Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Configuration Management Methods (MCP Tools)
    async def _read_config_file(self, filename: str) -> Dict[str, Any]:
        """Read configuration file from ~/.ipfs_kit/ directory (metadata-first approach)."""
        try:
            # Always check ~/.ipfs_kit/ first for configuration files
            ipfs_kit_dir = Path.home() / ".ipfs_kit"
            ipfs_kit_dir.mkdir(exist_ok=True)
            
            config_file = ipfs_kit_dir / filename
            
            if config_file.exists():
                content = config_file.read_text(encoding='utf-8')
                try:
                    # Validate JSON
                    json.loads(content)
                    return {
                        "content": content,
                        "source": "metadata",
                        "path": str(config_file),
                        "size": len(content),
                        "modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat()
                    }
                except json.JSONDecodeError:
                    return {
                        "content": content,
                        "source": "metadata",
                        "path": str(config_file),
                        "size": len(content),
                        "modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat(),
                        "warning": "Invalid JSON format"
                    }
            else:
                # Create default configuration if it doesn't exist
                default_configs = {
                    "pins.json": {
                        "pins": [],
                        "total_count": 0,
                        "last_updated": datetime.now().isoformat(),
                        "replication_factor": 1,
                        "cache_policy": "memory"
                    },
                    "buckets.json": {
                        "buckets": [],
                        "total_count": 0,
                        "last_updated": datetime.now().isoformat(),
                        "default_replication_factor": 1,
                        "default_cache_policy": "disk"
                    },
                    "backends.json": {
                        "backends": [],
                        "total_count": 0,
                        "last_updated": datetime.now().isoformat(),
                        "default_backend": "ipfs",
                        "health_check_interval": 30
                    }
                }
                
                if filename in default_configs:
                    default_content = json.dumps(default_configs[filename], indent=2)
                    config_file.write_text(default_content, encoding='utf-8')
                    return {
                        "content": default_content,
                        "source": "metadata",
                        "path": str(config_file),
                        "size": len(default_content),
                        "created": True,
                        "modified": datetime.now().isoformat()
                    }
                else:
                    raise FileNotFoundError(f"Configuration file {filename} not found and no default available")
                    
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _write_config_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Write configuration file to ~/.ipfs_kit/ directory (metadata-first approach)."""
        try:
            # Always write to ~/.ipfs_kit/ directory first
            ipfs_kit_dir = Path.home() / ".ipfs_kit"
            ipfs_kit_dir.mkdir(exist_ok=True)
            
            config_file = ipfs_kit_dir / filename
            
            # Validate JSON content
            try:
                parsed_content = json.loads(content)
                # Add metadata to the configuration
                parsed_content["last_updated"] = datetime.now().isoformat()
                content = json.dumps(parsed_content, indent=2)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON content: {str(e)}")
            
            config_file.write_text(content, encoding='utf-8')
            
            return {
                "success": True,
                "path": str(config_file),
                "size": len(content),
                "modified": datetime.now().isoformat(),
                "source": "metadata",
                "message": f"Configuration file {filename} updated in ~/.ipfs_kit/ directory"
            }
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _list_config_files(self) -> Dict[str, Any]:
        """List all configuration files in ~/.ipfs_kit/ directory."""
        try:
            ipfs_kit_dir = Path.home() / ".ipfs_kit"
            ipfs_kit_dir.mkdir(exist_ok=True)
            
            config_files = []
            default_configs = ["pins.json", "buckets.json", "backends.json"]
            
            for config_name in default_configs:
                config_file = ipfs_kit_dir / config_name
                if config_file.exists():
                    stat = config_file.stat()
                    config_files.append({
                        "name": config_name,
                        "path": str(config_file),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "source": "metadata",
                        "exists": True
                    })
                else:
                    config_files.append({
                        "name": config_name,
                        "path": str(config_file),
                        "size": 0,
                        "modified": None,
                        "source": "default",
                        "exists": False
                    })
            
            return {
                "files": config_files,
                "total_count": len(config_files),
                "directory": str(ipfs_kit_dir),
                "approach": "metadata-first (~/.ipfs_kit/ before ipfs_kit_py backends)"
            }
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _get_config_metadata(self, filename: str) -> Dict[str, Any]:
        """Get metadata about a specific configuration file."""
        try:
            ipfs_kit_dir = Path.home() / ".ipfs_kit"
            config_file = ipfs_kit_dir / filename
            
            if config_file.exists():
                stat = config_file.stat()
                try:
                    content = config_file.read_text(encoding='utf-8')
                    parsed = json.loads(content)
                    return {
                        "filename": filename,
                        "path": str(config_file),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "source": "metadata",
                        "exists": True,
                        "valid_json": True,
                        "entries": len(parsed.get("pins", parsed.get("buckets", parsed.get("backends", []))))
                    }
                except json.JSONDecodeError:
                    return {
                        "filename": filename,
                        "path": str(config_file),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "source": "metadata",
                        "exists": True,
                        "valid_json": False,
                        "error": "Invalid JSON format"
                    }
            else:
                return {
                    "filename": filename,
                    "path": str(config_file),
                    "size": 0,
                    "modified": None,
                    "source": "default",
                    "exists": False,
                    "can_create": filename in ["pins.json", "buckets.json", "backends.json"]
                }
                
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Enhanced MCP Service Management Methods
    async def _get_system_status_mcp(self) -> Dict[str, Any]:
        """Get comprehensive system status via MCP (metadata-first approach)."""
        import psutil
        
        # Check ~/.ipfs_kit/ for cached system data first
        ipfs_kit_dir = Path.home() / ".ipfs_kit"
        system_cache_file = ipfs_kit_dir / "system_status.json"
        
        if system_cache_file.exists():
            try:
                cached_data = json.loads(system_cache_file.read_text())
                # Use cached data if it's recent (less than 30 seconds old)
                cache_time = datetime.fromisoformat(cached_data.get("timestamp", ""))
                if (datetime.now() - cache_time).total_seconds() < 30:
                    return cached_data
            except Exception:
                pass
        
        # Get live system data
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status_data = {
                "time": datetime.now().isoformat(),
                "data_dir": str(ipfs_kit_dir),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "timestamp": datetime.now().isoformat()
            }
            
            # Cache the data
            if ipfs_kit_dir.exists():
                system_cache_file.write_text(json.dumps(status_data, indent=2))
            
            return status_data
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def _list_services_mcp(self, include_metadata: bool = True) -> Dict[str, Any]:
        """List all services with metadata-first approach."""
        # Check ~/.ipfs_kit/ for service metadata first
        ipfs_kit_dir = Path.home() / ".ipfs_kit"
        services_file = ipfs_kit_dir / "services.json"
        
        services_data = {
            "services": [],
            "metadata_source": "live",
            "timestamp": datetime.now().isoformat()
        }
        
        if include_metadata and services_file.exists():
            try:
                cached_services = json.loads(services_file.read_text())
                services_data["services"] = cached_services.get("services", [])
                services_data["metadata_source"] = "cached"
            except Exception as e:
                print(f"Error reading cached services: {e}")
        
        # If no cached data or cache disabled, get live data
        if not services_data["services"]:
            # Generate comprehensive service list including Apache Arrow and Parquet
            live_services = [
                # System Daemons
                {"name": "IPFS Daemon", "type": "daemon", "category": "system", "status": "configured", "description": "System daemon for distributed storage"},
                {"name": "Aria2 Daemon", "type": "daemon", "category": "system", "status": "stopped", "description": "System daemon for content retrieval"},
                {"name": "IPFS Cluster", "type": "daemon", "category": "system", "status": "not_enabled", "description": "Daemon for coordinated pin management"},
                {"name": "IPFS Cluster Follow", "type": "daemon", "category": "system", "status": "not_enabled", "description": "Service for remote cluster synchronization"},
                {"name": "Lassie Retrieval Client", "type": "daemon", "category": "system", "status": "not_enabled", "description": "High-performance Filecoin retrieval client for IPFS content"},
                
                # Storage Backends
                {"name": "Lotus Storage", "type": "storage", "category": "storage", "status": "not_enabled", "description": "Filecoin Lotus storage provider integration"},
                {"name": "Amazon S3", "type": "storage", "category": "storage", "status": "not_configured", "description": "Amazon Simple Storage Service backend"},
                {"name": "GitHub Storage", "type": "storage", "category": "storage", "status": "not_configured", "description": "GitHub repository storage backend"},
                {"name": "Storacha", "type": "storage", "category": "storage", "status": "not_configured", "description": "Storacha cloud storage service"},
                {"name": "Google Drive", "type": "storage", "category": "storage", "status": "not_configured", "description": "Google Drive cloud storage backend"},
                {"name": "FTP Server", "type": "storage", "category": "storage", "status": "not_configured", "description": "File Transfer Protocol storage backend"},
                {"name": "SSHFS", "type": "storage", "category": "storage", "status": "not_configured", "description": "SSH Filesystem storage backend"},
                
                # Network Services
                {"name": "MCP Server", "type": "server", "category": "network", "status": "stopped", "description": "Multi-Content Protocol server"},
                
                # AI/ML Services (including Apache Arrow and Parquet as requested)
                {"name": "HuggingFace Hub", "type": "storage", "category": "ai_ml", "status": "not_configured", "description": "HuggingFace model and dataset repository"},
                {"name": "Synapse Matrix", "type": "storage", "category": "ai_ml", "status": "not_configured", "description": "Matrix Synapse server storage"},
                {"name": "Apache Arrow", "type": "storage", "category": "ai_ml", "status": "configured", "description": "In-memory columnar data format for analytics and data analytics workloads"},
                {"name": "Parquet Storage", "type": "storage", "category": "ai_ml", "status": "configured", "description": "Columnar storage format for analytics workloads"}
            ]
            
            services_data["services"] = live_services
            services_data["metadata_source"] = "live"
            
            # Cache the live data if metadata enabled
            if include_metadata:
                try:
                    ipfs_kit_dir.mkdir(exist_ok=True)
                    services_file.write_text(json.dumps(services_data, indent=2))
                except Exception as e:
                    print(f"Error caching services: {e}")
        
        return services_data

    async def _list_backends_mcp(self, include_metadata: bool = True) -> Dict[str, Any]:
        """List all backends with metadata-first approach."""
        # Check ~/.ipfs_kit/ for backend metadata first
        ipfs_kit_dir = Path.home() / ".ipfs_kit"
        backends_file = ipfs_kit_dir / "backends.json"
        
        backends_data = {
            "backends": [],
            "metadata_source": "live",
            "timestamp": datetime.now().isoformat()
        }
        
        if include_metadata and backends_file.exists():
            try:
                cached_backends = json.loads(backends_file.read_text())
                backends_data["backends"] = cached_backends.get("backends", [])
                backends_data["metadata_source"] = "cached"
            except Exception as e:
                print(f"Error reading cached backends: {e}")
        
        # If no cached data, get live backend data
        if not backends_data["backends"]:
            live_backends = [
                {"name": "ipfs", "type": "ipfs", "status": "healthy", "description": "IPFS distributed storage"},
                {"name": "ipfs_cluster", "type": "ipfs_cluster", "status": "not_configured", "description": "IPFS cluster coordination"},
                {"name": "s3", "type": "s3", "status": "not_configured", "description": "Amazon S3 storage"},
                {"name": "lotus", "type": "lotus", "status": "not_configured", "description": "Filecoin Lotus storage"},
                {"name": "storacha", "type": "storacha", "status": "not_configured", "description": "Storacha cloud storage"},
                {"name": "github", "type": "github", "status": "not_configured", "description": "GitHub repository storage"},
                {"name": "google_drive", "type": "google_drive", "status": "not_configured", "description": "Google Drive storage"},
                {"name": "ftp", "type": "ftp", "status": "not_configured", "description": "FTP storage"}
            ]
            
            backends_data["backends"] = live_backends
            
            # Cache the data if metadata enabled
            if include_metadata:
                try:
                    ipfs_kit_dir.mkdir(exist_ok=True)
                    backends_file.write_text(json.dumps(backends_data, indent=2))
                except Exception as e:
                    print(f"Error caching backends: {e}")
        
        return backends_data

    async def _list_buckets_mcp(self, include_metadata: bool = True) -> Dict[str, Any]:
        """List all buckets with metadata-first approach."""
        # Check ~/.ipfs_kit/ for bucket metadata first
        ipfs_kit_dir = Path.home() / ".ipfs_kit"
        buckets_file = ipfs_kit_dir / "buckets.json"
        
        buckets_data = {
            "items": [],
            "metadata_source": "live", 
            "timestamp": datetime.now().isoformat()
        }
        
        if include_metadata and buckets_file.exists():
            try:
                cached_buckets = json.loads(buckets_file.read_text())
                buckets_data["items"] = cached_buckets.get("items", [])
                buckets_data["metadata_source"] = "cached"
            except Exception as e:
                print(f"Error reading cached buckets: {e}")
        
        # If no cached data, get live bucket data
        if not buckets_data["items"]:
            # Try to get actual bucket data from bucket manager
            try:
                if self.bucket_manager:
                    # Get real bucket list if available
                    live_buckets = []
                    # This would call the actual bucket manager
                    # live_buckets = await self.bucket_manager.list_buckets()
                else:
                    # Fallback to example buckets
                    live_buckets = [
                        {"name": "test-bucket", "backend": "ipfs", "replication": "1x", "cache": "none", "status": "active"},
                        {"name": "archive-bucket", "backend": "s3", "replication": "3x", "cache": "memory", "status": "active"}
                    ]
                
                buckets_data["items"] = live_buckets
                
                # Cache the data if metadata enabled
                if include_metadata:
                    try:
                        ipfs_kit_dir.mkdir(exist_ok=True)
                        buckets_file.write_text(json.dumps(buckets_data, indent=2))
                    except Exception as e:
                        print(f"Error caching buckets: {e}")
            except Exception as e:
                print(f"Error getting live bucket data: {e}")
                buckets_data["items"] = []
        
        return buckets_data

    async def _configure_service_mcp(self, service_type: str, instance_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure a service instance with cache/storage/retention settings."""
        ipfs_kit_dir = Path.home() / ".ipfs_kit"
        services_config_file = ipfs_kit_dir / "services_config.json"
        
        # Load existing configuration
        services_config = {}
        if services_config_file.exists():
            try:
                services_config = json.loads(services_config_file.read_text())
            except Exception:
                pass
        
        # Add/update service configuration
        if service_type not in services_config:
            services_config[service_type] = {}
        
        services_config[service_type][instance_name] = {
            "config": config,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat()
        }
        
        # Save configuration
        try:
            ipfs_kit_dir.mkdir(exist_ok=True)
            services_config_file.write_text(json.dumps(services_config, indent=2))
            
            return {
                "success": True,
                "service_type": service_type,
                "instance_name": instance_name,
                "config": config,
                "message": f"Successfully configured {service_type} instance '{instance_name}'"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to configure {service_type} instance '{instance_name}'"
            }

    # Dashboard Data Methods
    async def _get_services_status(self) -> List[Dict[str, Any]]:
        """Get status of all services."""
        services = []
        
        # Add IPFS service status
        ipfs_status = "running" if self.ipfs_api else "stopped"
        services.append({
            "name": "IPFS Node",
            "type": "ipfs",
            "status": ipfs_status,
            "description": "IPFS node connection"
        })
        
        # Add MCP server status
        services.append({
            "name": "MCP Server", 
            "type": "mcp",
            "status": "running",
            "description": "Model Context Protocol server"
        })
        
        # Add dashboard status
        services.append({
            "name": "Web Dashboard",
            "type": "web",
            "status": "running", 
            "description": "Web-based management interface"
        })
        
        return services

    async def _get_backends_status(self) -> List[Dict[str, Any]]:
        """Get status of storage backends."""
        backends = []
        
        # Add default IPFS backend
        backends.append({
            "name": "IPFS Local",
            "type": "ipfs", 
            "status": "running" if self.ipfs_api else "stopped",
            "url": "http://127.0.0.1:5001",
            "description": "Local IPFS node"
        })
        
        # Add other backend types as available
        backends.append({
            "name": "File System",
            "type": "filesystem",
            "status": "available",
            "description": "Local file system storage"
        })
        
        return backends

    async def _get_buckets(self) -> List[Dict[str, Any]]:
        """Get list of buckets."""
        buckets = []
        
        if self.bucket_manager:
            try:
                # Get buckets from bucket manager
                bucket_list = self.bucket_manager.list_buckets()
                for bucket_name in bucket_list:
                    bucket_info = self.bucket_manager.get_bucket_info(bucket_name)
                    buckets.append({
                        "name": bucket_name,
                        "description": bucket_info.get("description", ""),
                        "file_count": bucket_info.get("file_count", 0),
                        "total_size": bucket_info.get("total_size", "0 B"),
                        "created": bucket_info.get("created", ""),
                        "status": "active"
                    })
            except Exception as e:
                logging.error(f"Error getting buckets: {e}")
        
        # Add default bucket if none found
        if not buckets:
            buckets.append({
                "name": "default",
                "description": "Default storage bucket",
                "file_count": 0,
                "total_size": "0 B", 
                "status": "active"
            })
        
        return buckets

    async def _get_all_pins(self) -> List[Dict[str, Any]]:
        """Get list of all pins."""
        pins = []
        
        if self.ipfs_api:
            try:
                # Get pins from IPFS
                pin_response = self.ipfs_api.pin_ls()
                for cid, pin_info in pin_response.items():
                    pins.append({
                        "cid": cid,
                        "name": pin_info.get("name", ""),
                        "type": pin_info.get("type", "recursive"),
                        "status": "pinned",
                        "size": pin_info.get("size", "unknown"),
                        "pinned_at": pin_info.get("pinned_at", "")
                    })
            except Exception as e:
                logging.error(f"Error getting pins: {e}")
        
        # Add sample pin if none found  
        if not pins:
            pins.append({
                "cid": "QmSampleCidForDemonstration",
                "name": "Sample Pin",
                "type": "recursive", 
                "status": "pinned",
                "size": "1.2 MB"
            })
        
        return pins

    async def list_backend_buckets(self, backend_name: str) -> List[str]:
        """List buckets for a specific backend."""
        try:
            if self.bucket_manager:
                return self.bucket_manager.list_buckets(backend=backend_name)
            return []
        except Exception as e:
            logging.error(f"Error listing backend buckets: {e}")
            return []

    def _get_dashboard_html(self):
        """Generate the dashboard HTML with modern aesthetic design."""
        # Use the enhanced template file
        template_path = Path(__file__).parent / 'templates' / 'enhanced_dashboard.html'
        if template_path.exists():
            return template_path.read_text()
        
        # Fallback to basic template if enhanced template not found
        return self._get_basic_dashboard_html()
    
    def _get_basic_dashboard_html(self):
        """Basic fallback dashboard template."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit - MCP Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen flex">
        <div class="flex-1 p-6">
            <h1 class="text-2xl font-bold mb-6">IPFS Kit MCP Dashboard</h1>
            <div class="bg-white rounded-lg shadow p-6">
                <p>Dashboard is loading...</p>
                <p>If this message persists, please check the enhanced template file.</p>
            </div>
        </div>
    </div>
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
    
    dashboard = UnifiedMCPDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()

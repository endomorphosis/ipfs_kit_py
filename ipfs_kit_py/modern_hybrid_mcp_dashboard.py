#!/usr/bin/env python3
"""
Modern Hybrid MCP Dashboard - Merging Old & New Architectures

This implementation combines:
- Light initialization (no heavy imports)
- Bucket-based virtual filesystem
- ~/.ipfs_kit/ state management
- JSON RPC MCP protocol
- Refactored modular templates
- All original MCP functionality restored
"""

import anyio
import json
import logging
import os
import time
import sqlite3
import psutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union

# Web framework imports (light)
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Pydantic for MCP protocol
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class McpRequest(BaseModel):
    """MCP protocol request format."""
    method: str
    params: Optional[Dict[str, Any]] = None


class McpResponse(BaseModel):
    """MCP protocol response format."""
    result: Optional[Any] = None
    error: Optional[str] = None


class ModernHybridMCPDashboard:
    """
    Modern Hybrid MCP Dashboard combining:
    - Restored MCP functionality from backup
    - Light initialization philosophy
    - Bucket-based VFS operations
    - ~/.ipfs_kit/ state management
    - Refactored modular templates
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with light startup and ~/.ipfs_kit/ state."""
        self.start_time = datetime.now()
        
        if config is None:
            config = {}
        
        # Core configuration
        self.config = config
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8080)
        self.debug = config.get('debug', False)
        
        # Modern state directory
        self.data_dir = Path(config.get('data_dir', '~/.ipfs_kit')).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize state management paths
        self.buckets_dir = self.data_dir / "buckets"
        self.backends_dir = self.data_dir / "backends"  
        self.services_dir = self.data_dir / "services"
        self.config_dir = self.data_dir / "config"
        self.logs_dir = self.data_dir / "logs"
        self.program_state_dir = self.data_dir / "program_state"
        
        # Create directories
        for dir_path in [self.buckets_dir, self.backends_dir, self.services_dir, 
                        self.config_dir, self.logs_dir, self.program_state_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Template and static paths
        self.mcp_dir = Path(__file__).parent
        self.template_dir = self.mcp_dir / "dashboard_templates"
        self.static_dir = self.mcp_dir / "dashboard_static"
        
        # Initialize FastAPI with both MCP and Dashboard
        self.app = FastAPI(
            title="IPFS Kit - Modern Hybrid MCP Dashboard",
            version="5.0.0",
            description="Light-initialized MCP server with bucket VFS and filesystem state"
        )
        
        # Setup templates and static files
        if self.template_dir.exists():
            self.templates = Jinja2Templates(directory=str(self.template_dir))
        else:
            self.templates = None
            
        if self.static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
        
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # MCP state
        self.mcp_tools = {}
        self.mcp_initialized = False
        
        # Setup routes
        self._setup_mcp_routes()
        self._setup_dashboard_routes()
        self._setup_api_routes()
        self._register_modern_mcp_tools()
        
        logger.info(f"Modern Hybrid MCP Dashboard initialized on {self.host}:{self.port}")
    
    def _setup_static_files(self):
        """Setup static file serving and template directories (compatibility method)."""
        # This method exists for compatibility with legacy code that might call it
        # In the modern dashboard, static files are set up in __init__
        logger.info("Static files already configured in modern dashboard initialization")
        pass
    
    def _register_modern_mcp_tools(self):
        """Register MCP tools for modern bucket-based operations."""
        self.mcp_tools = {
            # Original file operations (restored)
            "list_files": {
                "name": "list_files",
                "description": "List files in a directory or bucket",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path or bucket name"},
                        "bucket": {"type": "string", "description": "Optional bucket name"}
                    },
                    "required": ["path"]
                }
            },
            "read_file": {
                "name": "read_file",
                "description": "Read contents of a file from filesystem or bucket",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "bucket": {"type": "string", "description": "Optional bucket name"}
                    },
                    "required": ["path"]
                }
            },
            "write_file": {
                "name": "write_file",
                "description": "Write content to a file in filesystem or bucket",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "Content to write"},
                        "bucket": {"type": "string", "description": "Optional bucket name"}
                    },
                    "required": ["path", "content"]
                }
            },
            # Modern bucket operations
            "daemon_status": {
                "name": "daemon_status",
                "description": "Get IPFS daemon and service status from ~/.ipfs_kit/",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "list_backends": {
                "name": "list_backends",
                "description": "List all configured storage backends",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "list_buckets": {
                "name": "list_buckets",
                "description": "List all buckets across all backends",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "backend": {"type": "string", "description": "Filter by backend name"}
                    },
                    "required": []
                }
            },
            "system_metrics": {
                "name": "system_metrics",
                "description": "Get system performance metrics",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            # Bucket VFS operations
            "bucket_create": {
                "name": "bucket_create",
                "description": "Create a new bucket",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Bucket name"},
                        "backend": {"type": "string", "description": "Backend type"}
                    },
                    "required": ["name", "backend"]
                }
            },
            "bucket_delete": {
                "name": "bucket_delete",
                "description": "Delete a bucket",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Bucket name"}
                    },
                    "required": ["name"]
                }
            }
        }
    
    def _setup_mcp_routes(self):
        """Setup MCP protocol endpoints."""
        
        @self.app.post("/mcp/initialize")
        async def mcp_initialize(request: McpRequest):
            """MCP initialization endpoint."""
            self.mcp_initialized = True
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                }
            }
        
        @self.app.post("/mcp/tools/list")
        async def list_mcp_tools():
            """List available MCP tools."""
            return {"tools": list(self.mcp_tools.values())}
        
        @self.app.post("/mcp/tools/call")
        async def call_mcp_tool(request: McpRequest):
            """Execute MCP tool with modern bucket-based operations."""
            tool_name = request.method
            params = request.params or {}
            
            try:
                # Original file operations (with bucket support)
                if tool_name == "list_files":
                    result = await self._list_files_modern(params.get("path", "."), params.get("bucket"))
                elif tool_name == "read_file":
                    result = await self._read_file_modern(params.get("path"), params.get("bucket"))
                elif tool_name == "write_file":
                    result = await self._write_file_modern(params.get("path"), params.get("content"), params.get("bucket"))
                
                # Restored MCP functionality
                elif tool_name == "daemon_status":
                    result = await self._get_daemon_status_modern()
                elif tool_name == "list_backends":
                    result = await self._get_backends_data_modern()
                elif tool_name == "list_buckets":
                    result = await self._get_buckets_data_modern(params.get("backend"))
                elif tool_name == "system_metrics":
                    result = await self._get_system_metrics_modern()
                
                # Modern bucket operations
                elif tool_name == "bucket_create":
                    result = await self._create_bucket_modern(params.get("name"), params.get("backend"))
                elif tool_name == "bucket_delete":
                    result = await self._delete_bucket_modern(params.get("name"))
                
                else:
                    raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
                
                return McpResponse(result=result)
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                return McpResponse(error=str(e))
    
    def _setup_dashboard_routes(self):
        """Setup dashboard web interface routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Serve the main dashboard."""
            if self.templates:
                return self.templates.TemplateResponse("unified_dashboard.html", {
                    "request": request,
                    "port": self.port,
                    "title": "IPFS Kit - Modern Hybrid MCP Dashboard"
                })
            else:
                return HTMLResponse(content=self._get_fallback_dashboard_html())
    
    def _setup_api_routes(self):
        """Setup REST API routes for dashboard."""
        
        @self.app.get("/api/system/overview")
        async def get_system_overview():
            """Get system overview from ~/.ipfs_kit/ state."""
            try:
                services_count = len(await self._get_services_status_modern())
                backends_count = len(await self._get_backends_data_modern())
                buckets_count = len(await self._get_buckets_data_modern())
                
                uptime_seconds = (datetime.now() - self.start_time).total_seconds()
                uptime_str = f"{int(uptime_seconds // 3600):02d}:{int((uptime_seconds % 3600) // 60):02d}:{int(uptime_seconds % 60):02d}"
                
                return {
                    "services": services_count,
                    "backends": backends_count,
                    "buckets": buckets_count,
                    "uptime": uptime_str,
                    "status": "operational",
                    "data_dir": str(self.data_dir)
                }
            except Exception as e:
                logger.error(f"Error getting system overview: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/services")
        async def get_services():
            """Get services status from ~/.ipfs_kit/services/."""
            return await self._get_services_status_modern()
        
        @self.app.get("/api/backends")
        async def get_backends():
            """Get backends from ~/.ipfs_kit/backends/."""
            return await self._get_backends_data_modern()
        
        @self.app.get("/api/buckets")
        async def get_buckets():
            """Get buckets from ~/.ipfs_kit/buckets/."""
            return await self._get_buckets_data_modern()
        
        @self.app.get("/api/metrics")
        async def get_metrics():
            """Get system metrics."""
            return await self._get_system_metrics_modern()
    
    # Modern implementations using ~/.ipfs_kit/ filesystem state
    
    async def _get_daemon_status_modern(self) -> Dict[str, Any]:
        """Get daemon status from ~/.ipfs_kit/ state files."""
        try:
            status = {
                "ipfs": "unknown",
                "mcp_server": "running",
                "services": [],
                "timestamp": datetime.now().isoformat()
            }
            
            # Check for daemon PID files
            mcp_pid_file = self.data_dir / "mcp_server.pid"
            if mcp_pid_file.exists():
                try:
                    pid = int(mcp_pid_file.read_text().strip())
                    if psutil.pid_exists(pid):
                        status["mcp_server"] = "running"
                    else:
                        status["mcp_server"] = "stopped"
                except:
                    status["mcp_server"] = "unknown"
            
            # Check IPFS daemon
            try:
                result = subprocess.run(["ipfs", "id"], capture_output=True, timeout=2)
                status["ipfs"] = "running" if result.returncode == 0 else "stopped"
            except:
                status["ipfs"] = "not_available"
            
            return status
        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
            return {"error": str(e)}
    
    async def _get_backends_data_modern(self) -> List[Dict[str, Any]]:
        """Get backends from ~/.ipfs_kit/backends/ directory."""
        try:
            backends = []
            
            if self.backends_dir.exists():
                for backend_dir in self.backends_dir.iterdir():
                    if backend_dir.is_dir():
                        config_file = backend_dir / "config.json"
                        backend_info = {
                            "name": backend_dir.name,
                            "type": "unknown",
                            "status": "configured",
                            "path": str(backend_dir)
                        }
                        
                        if config_file.exists():
                            try:
                                config = json.loads(config_file.read_text())
                                backend_info.update(config)
                                backend_info["status"] = "active"
                            except:
                                backend_info["status"] = "error"
                        
                        backends.append(backend_info)
            
            return backends
        except Exception as e:
            logger.error(f"Error getting backends: {e}")
            return []
    
    async def _get_buckets_data_modern(self, backend_filter: str = None) -> List[Dict[str, Any]]:
        """Get buckets from ~/.ipfs_kit/buckets/ using parquet files."""
        try:
            buckets = []
            
            if self.buckets_dir.exists():
                # Check parquet files (modern bucket metadata)
                for parquet_file in self.buckets_dir.glob("*.parquet"):
                    bucket_name = parquet_file.stem
                    if backend_filter and backend_filter not in bucket_name:
                        continue
                        
                    bucket_info = {
                        "name": bucket_name,
                        "type": "parquet",
                        "size_bytes": parquet_file.stat().st_size,
                        "modified": datetime.fromtimestamp(parquet_file.stat().st_mtime).isoformat(),
                        "path": str(parquet_file)
                    }
                    buckets.append(bucket_info)
                
                # Check directory-based buckets
                for bucket_dir in self.buckets_dir.iterdir():
                    if bucket_dir.is_dir():
                        if backend_filter and backend_filter not in bucket_dir.name:
                            continue
                            
                        file_count = len(list(bucket_dir.rglob("*"))) if bucket_dir.exists() else 0
                        bucket_info = {
                            "name": bucket_dir.name,
                            "type": "directory",
                            "file_count": file_count,
                            "modified": datetime.fromtimestamp(bucket_dir.stat().st_mtime).isoformat(),
                            "path": str(bucket_dir)
                        }
                        buckets.append(bucket_info)
            
            return buckets
        except Exception as e:
            logger.error(f"Error getting buckets: {e}")
            return []
    
    async def _get_services_status_modern(self) -> List[Dict[str, Any]]:
        """Get services from ~/.ipfs_kit/services/ directory."""
        try:
            services = []
            
            if self.services_dir.exists():
                for service_file in self.services_dir.glob("*.json"):
                    try:
                        service_data = json.loads(service_file.read_text())
                        service_data["name"] = service_file.stem
                        service_data["config_file"] = str(service_file)
                        services.append(service_data)
                    except Exception as e:
                        services.append({
                            "name": service_file.stem,
                            "status": "error",
                            "error": str(e)
                        })
            
            return services
        except Exception as e:
            logger.error(f"Error getting services: {e}")
            return []
    
    async def _get_system_metrics_modern(self) -> Dict[str, Any]:
        """Get system metrics with light dependencies."""
        try:
            # Use psutil for basic metrics (lightweight)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "data_dir_size": self._get_dir_size(self.data_dir),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {"error": str(e)}
    
    # Modern file operations with bucket support
    
    async def _list_files_modern(self, path: str, bucket: str = None) -> List[str]:
        """List files with bucket VFS support."""
        try:
            if bucket:
                # List files in bucket
                bucket_path = self.buckets_dir / bucket
                if bucket_path.exists() and bucket_path.is_dir():
                    target_path = bucket_path / path.lstrip('/')
                else:
                    # Check for parquet bucket file
                    parquet_file = self.buckets_dir / f"{bucket}.parquet"
                    if parquet_file.exists():
                        return [f"Parquet bucket: {bucket} (size: {parquet_file.stat().st_size} bytes)"]
                    else:
                        raise FileNotFoundError(f"Bucket '{bucket}' not found")
            else:
                # Regular filesystem path
                target_path = Path(path).expanduser()
            
            if target_path.exists() and target_path.is_dir():
                return [item.name for item in target_path.iterdir()]
            else:
                raise FileNotFoundError(f"Path '{target_path}' not found")
                
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise
    
    async def _read_file_modern(self, path: str, bucket: str = None) -> str:
        """Read file with bucket VFS support."""
        try:
            if bucket:
                # Read from bucket
                bucket_path = self.buckets_dir / bucket
                if bucket_path.exists() and bucket_path.is_dir():
                    file_path = bucket_path / path.lstrip('/')
                else:
                    raise FileNotFoundError(f"Bucket '{bucket}' not found or not a directory")
            else:
                # Regular filesystem
                file_path = Path(path).expanduser()
            
            if file_path.exists() and file_path.is_file():
                return file_path.read_text()
            else:
                raise FileNotFoundError(f"File '{file_path}' not found")
                
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise
    
    async def _write_file_modern(self, path: str, content: str, bucket: str = None) -> str:
        """Write file with bucket VFS support."""
        try:
            if bucket:
                # Write to bucket
                bucket_path = self.buckets_dir / bucket
                bucket_path.mkdir(parents=True, exist_ok=True)
                file_path = bucket_path / path.lstrip('/')
            else:
                # Regular filesystem
                file_path = Path(path).expanduser()
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return f"File written successfully to {file_path}"
            
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            raise
    
    async def _create_bucket_modern(self, name: str, backend: str) -> str:
        """Create a new bucket using modern VFS approach."""
        try:
            bucket_path = self.buckets_dir / name
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            # Create bucket metadata
            metadata = {
                "name": name,
                "backend": backend,
                "created": datetime.now().isoformat(),
                "type": "directory"
            }
            
            metadata_file = bucket_path / ".bucket_metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2))
            
            return f"Bucket '{name}' created successfully with backend '{backend}'"
            
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            raise
    
    async def _delete_bucket_modern(self, name: str) -> str:
        """Delete a bucket using modern VFS approach."""
        try:
            # Check directory bucket
            bucket_path = self.buckets_dir / name
            if bucket_path.exists():
                import shutil
                shutil.rmtree(bucket_path)
                return f"Directory bucket '{name}' deleted successfully"
            
            # Check parquet bucket
            parquet_file = self.buckets_dir / f"{name}.parquet"
            if parquet_file.exists():
                parquet_file.unlink()
                return f"Parquet bucket '{name}' deleted successfully"
            
            raise FileNotFoundError(f"Bucket '{name}' not found")
            
        except Exception as e:
            logger.error(f"Error deleting bucket: {e}")
            raise
    
    # Utility methods
    
    def _get_dir_size(self, path: Path) -> int:
        """Get directory size recursively."""
        try:
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        except:
            return 0
    
    def _get_fallback_dashboard_html(self) -> str:
        """Fallback HTML when templates aren't available."""
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>IPFS Kit - Modern Hybrid MCP Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; }
                .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
                .status { color: green; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚀 IPFS Kit - Modern Hybrid MCP Dashboard</h1>
                <p>Light initialization • Bucket VFS • State management • MCP Protocol</p>
            </div>
            
            <div class="section">
                <h2>✅ MCP Server Status</h2>
                <p class="status">Running on port ''' + str(self.port) + '''</p>
                <p>MCP Endpoints: <code>/mcp/initialize</code>, <code>/mcp/tools/list</code>, <code>/mcp/tools/call</code></p>
            </div>
            
            <div class="section">
                <h2>🗂️ API Endpoints</h2>
                <ul>
                    <li><a href="/api/system/overview">/api/system/overview</a> - System status</li>
                    <li><a href="/api/backends">/api/backends</a> - Storage backends</li>
                    <li><a href="/api/buckets">/api/buckets</a> - Bucket VFS</li>
                    <li><a href="/api/services">/api/services</a> - Services status</li>
                    <li><a href="/api/metrics">/api/metrics</a> - System metrics</li>
                </ul>
            </div>
            
            <div class="section">
                <h2>🔧 Features</h2>
                <ul>
                    <li>✅ Light initialization (no heavy imports)</li>
                    <li>✅ Bucket-based virtual filesystem</li>
                    <li>✅ ~/.ipfs_kit/ state management</li>
                    <li>✅ JSON RPC MCP protocol</li>
                    <li>✅ VS Code integration ready</li>
                    <li>✅ Real-time system monitoring</li>
                </ul>
            </div>
        </body>
        </html>
        '''
    
    async def run_async(self):
        """Run the dashboard in async mode (for embedding in existing event loop)."""
        print(f"🚀 Starting Modern Hybrid MCP Dashboard on http://{self.host}:{self.port}")
        print(f"📊 Dashboard: http://{self.host}:{self.port}/")
        print(f"🔧 MCP API: http://{self.host}:{self.port}/mcp/*")
        print(f"📋 REST API: http://{self.host}:{self.port}/api/*")
        print(f"💾 Data dir: {self.data_dir}")
        
        # Use uvicorn server directly for async mode
        import uvicorn
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info" if self.debug else "warning"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self):
        """Run the modern hybrid MCP dashboard in standalone mode."""
        print(f"🚀 Starting Modern Hybrid MCP Dashboard on http://{self.host}:{self.port}")
        print(f"📊 Dashboard: http://{self.host}:{self.port}/")
        print(f"🔧 MCP API: http://{self.host}:{self.port}/mcp/*")
        print(f"📋 REST API: http://{self.host}:{self.port}/api/*")
        print(f"💾 Data dir: {self.data_dir}")
        
        try:
            import sniffio

            sniffio.current_async_library()
            print("⚠️  Already in async context, use run_async() instead")
            raise RuntimeError("Cannot run sync mode from async context. Use run_async() method.")
        except Exception:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info" if self.debug else "warning"
            )


# Export the class for CLI usage
UnifiedMCPDashboard = ModernHybridMCPDashboard


def main():
    """Main entry point for standalone usage."""
    dashboard = ModernHybridMCPDashboard({
        'host': '0.0.0.0',
        'port': 8080,
        'debug': True
    })
    dashboard.run()


if __name__ == "__main__":
    main()

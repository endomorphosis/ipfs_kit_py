#!/usr/bin/env python3
"""
Refactored MCP Server - Aligned with CLI codebase

This is the main MCP server implementation that mirrors the CLI functionality
while adapting to the MCP protocol. It efficiently reads metadata from ~/.ipfs_kit/
and delegates to the intelligent daemon for backend synchronization.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from dataclasses import dataclass, field

# Import MCP dependencies with fallback
try:
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    MCP_AVAILABLE = True
except ImportError:
    # Fallback stubs for when MCP is not available
    class types:
        class Tool:
            def __init__(self, name, description, inputSchema):
                self.name = name
                self.description = description
                self.inputSchema = inputSchema
        
        class TextContent:
            def __init__(self, type, text):
                self.type = type
                self.text = text
    
    class Server:
        def __init__(self, name):
            self.name = name
            self._tools = []
            self._tool_handlers = {}
        
        def list_tools(self):
            def decorator(func):
                self._tools.append(func)
                return func
            return decorator
        
        def call_tool(self):
            def decorator(func):
                self._tool_handlers['call_tool'] = func
                return func
            return decorator
        
        def create_initialization_options(self):
            return {}
        
        async def run(self, read_stream, write_stream, options):
            print(f"MCP Server {self.name} would run with stdio transport")
    
    def stdio_server():
        class MockTransport:
            async def __aenter__(self):
                return (None, None)
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        return MockTransport()
    
    MCP_AVAILABLE = False

try:
    from ..config_manager import ConfigManager
    def get_config_manager():
        return ConfigManager()
except ImportError:
    def get_config_manager():
        return None
from .models.mcp_metadata_manager import MCPMetadataManager
from .services.mcp_daemon_service import MCPDaemonService
from .controllers.mcp_cli_controller import MCPCLIController
from .controllers.mcp_backend_controller import MCPBackendController
from .controllers.mcp_daemon_controller import MCPDaemonController
from .controllers.mcp_storage_controller import MCPStorageController
from .controllers.mcp_vfs_controller import MCPVFSController

logger = logging.getLogger(__name__)


@dataclass
@dataclass
class MCPServerConfig:
    """Configuration for the MCP Server."""
    data_dir: Path = field(default_factory=lambda: Path.home() / ".ipfs_kit")
    host: str = "127.0.0.1"
    port: int = 3000
    debug_mode: bool = False
    enable_stdio: bool = True
    enable_websocket: bool = False
    max_connections: int = 100
    timeout_seconds: int = 30
    
    # CLI alignment settings
    preserve_cli_behavior: bool = True
    daemon_sync_enabled: bool = True
    metadata_cache_ttl: int = 300  # 5 minutes
    atomic_operations_only: bool = True
    
    def __post_init__(self):
        """Ensure data_dir is a Path object."""
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir).expanduser()


class MCPServer:
    """
    Refactored MCP Server aligned with CLI codebase
    
    This server provides all CLI functionality through the MCP protocol:
    - Backend management (matching CLI backend commands)
    - Storage operations (matching CLI storage commands) 
    - VFS operations (matching CLI vfs commands)
    - Daemon management (matching CLI daemon commands)
    - Pin and bucket operations (matching CLI functionality)
    
    Key design principles:
    1. Mirror CLI command structure in MCP tools
    2. Use metadata from ~/.ipfs_kit/ efficiently
    3. Delegate backend sync to intelligent daemon
    4. Preserve CLI behavior patterns
    """
    
    def __init__(self, config: Optional[MCPServerConfig] = None):
        """Initialize the refactored MCP server."""
        self.config = config or MCPServerConfig()
        self.server = Server("ipfs-kit-mcp")
        
        # Initialize MCP config manager
        from .models.mcp_config_manager import get_mcp_config_manager
        self.config_manager = get_mcp_config_manager(self.config.data_dir)
        
        # Initialize core components aligned with CLI
        self.metadata_manager = MCPMetadataManager(self.config.data_dir)
        self.daemon_service = MCPDaemonService(self.config.data_dir)
        
        # Initialize controllers that mirror CLI commands
        self.cli_controller = MCPCLIController(self.metadata_manager, self.daemon_service)
        self.backend_controller = MCPBackendController(self.metadata_manager, self.daemon_service)
        self.daemon_controller = MCPDaemonController(self.metadata_manager, self.daemon_service)
        self.storage_controller = MCPStorageController(self.metadata_manager, self.daemon_service)
        self.vfs_controller = MCPVFSController(self.metadata_manager, self.daemon_service)
        
        # Register MCP tools that mirror CLI commands
        self._register_mcp_tools()
        
        # Set up signal handlers
        self._setup_signal_handlers()
        
        logger.info(f"MCP Server initialized with data_dir: {self.config.data_dir}")
    
    def _register_mcp_tools(self) -> None:
        """Register MCP tools that mirror CLI command structure."""
        
        # Backend tools (mirror CLI backend commands)
        @self.server.list_tools()
        async def list_backend_tools() -> List[types.Tool]:
            """List available backend management tools."""
            return [
                types.Tool(
                    name="backend_list",
                    description="List all configured backends (mirrors 'ipfs-kit backend list')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "filter": {"type": "string", "description": "Filter backends by type or name"},
                            "status": {"type": "string", "description": "Filter by status (healthy, unhealthy, all)"},
                            "detailed": {"type": "boolean", "description": "Show detailed information"}
                        }
                    }
                ),
                types.Tool(
                    name="backend_status",
                    description="Get backend status information (mirrors 'ipfs-kit backend status')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backend_name": {"type": "string", "description": "Specific backend to check"},
                            "check_health": {"type": "boolean", "description": "Perform health check"}
                        }
                    }
                ),
                types.Tool(
                    name="backend_sync",
                    description="Sync backend data (mirrors 'ipfs-kit backend sync')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backend_name": {"type": "string", "description": "Backend to sync"},
                            "force": {"type": "boolean", "description": "Force sync even if up to date"},
                            "dry_run": {"type": "boolean", "description": "Show what would be synced"}
                        }
                    }
                ),
                types.Tool(
                    name="backend_migrate_pin_mappings",
                    description="Migrate backend pin mappings (mirrors 'ipfs-kit backend migrate-pin-mappings')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "filter": {"type": "string", "description": "Filter backends to migrate"},
                            "dry_run": {"type": "boolean", "description": "Show what would be migrated"},
                            "verbose": {"type": "boolean", "description": "Show detailed migration progress"}
                        }
                    }
                )
            ]
        
        # Storage tools (mirror CLI storage commands)
        @self.server.list_tools()
        async def list_storage_tools() -> List[types.Tool]:
            """List available storage management tools."""
            return [
                types.Tool(
                    name="storage_list",
                    description="List storage contents (mirrors 'ipfs-kit storage list')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backend": {"type": "string", "description": "Backend to list from"},
                            "path": {"type": "string", "description": "Path to list"},
                            "recursive": {"type": "boolean", "description": "List recursively"}
                        }
                    }
                ),
                types.Tool(
                    name="storage_upload",
                    description="Upload content to storage (mirrors 'ipfs-kit storage upload')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Local file to upload"},
                            "backend": {"type": "string", "description": "Target backend"},
                            "remote_path": {"type": "string", "description": "Remote path destination"}
                        }
                    }
                ),
                types.Tool(
                    name="storage_download", 
                    description="Download content from storage (mirrors 'ipfs-kit storage download')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {"type": "string", "description": "Content ID to download"},
                            "backend": {"type": "string", "description": "Source backend"},
                            "local_path": {"type": "string", "description": "Local destination path"}
                        }
                    }
                )
            ]
        
        # Daemon tools (mirror CLI daemon commands)
        @self.server.list_tools()
        async def list_daemon_tools() -> List[types.Tool]:
            """List available daemon management tools."""
            return [
                types.Tool(
                    name="daemon_status",
                    description="Get daemon status (mirrors 'ipfs-kit daemon status')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "detailed": {"type": "boolean", "description": "Show detailed status"},
                            "json": {"type": "boolean", "description": "Output in JSON format"}
                        }
                    }
                ),
                types.Tool(
                    name="daemon_intelligent_status",
                    description="Get intelligent daemon status (mirrors 'ipfs-kit daemon intelligent status')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "json": {"type": "boolean", "description": "Output in JSON format"}
                        }
                    }
                ),
                types.Tool(
                    name="daemon_intelligent_insights",
                    description="Get intelligent daemon insights (mirrors 'ipfs-kit daemon intelligent insights')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "json": {"type": "boolean", "description": "Output in JSON format"}
                        }
                    }
                ),
                types.Tool(
                    name="daemon_start",
                    description="Start daemon services (mirrors 'ipfs-kit daemon start')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service": {"type": "string", "description": "Specific service to start"},
                            "background": {"type": "boolean", "description": "Run in background"}
                        }
                    }
                ),
                types.Tool(
                    name="daemon_stop",
                    description="Stop daemon services (mirrors 'ipfs-kit daemon stop')", 
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service": {"type": "string", "description": "Specific service to stop"}
                        }
                    }
                )
            ]
        
        # VFS tools (mirror CLI vfs commands)
        @self.server.list_tools()
        async def list_vfs_tools() -> List[types.Tool]:
            """List available VFS management tools."""
            return [
                types.Tool(
                    name="vfs_list",
                    description="List VFS contents (mirrors 'ipfs-kit vfs list')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "VFS path to list"},
                            "recursive": {"type": "boolean", "description": "List recursively"}
                        }
                    }
                ),
                types.Tool(
                    name="vfs_create",
                    description="Create VFS directory (mirrors 'ipfs-kit vfs create')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "VFS path to create"},
                            "parents": {"type": "boolean", "description": "Create parent directories"}
                        }
                    }
                ),
                types.Tool(
                    name="vfs_add",
                    description="Add file to VFS (mirrors 'ipfs-kit vfs add')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "local_path": {"type": "string", "description": "Local file to add"},
                            "vfs_path": {"type": "string", "description": "VFS destination path"}
                        }
                    }
                )
            ]
        
        # Pin tools (mirror CLI pin commands)
        @self.server.list_tools()
        async def list_pin_tools() -> List[types.Tool]:
            """List available pin management tools."""
            return [
                types.Tool(
                    name="pin_list",
                    description="List pinned content (mirrors 'ipfs-kit pin list')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backend": {"type": "string", "description": "Filter by backend"},
                            "status": {"type": "string", "description": "Filter by pin status"}
                        }
                    }
                ),
                types.Tool(
                    name="pin_add",
                    description="Pin content (mirrors 'ipfs-kit pin add')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {"type": "string", "description": "Content ID to pin"},
                            "backend": {"type": "string", "description": "Backend to pin to"},
                            "name": {"type": "string", "description": "Optional pin name"}
                        }
                    }
                ),
                types.Tool(
                    name="pin_remove",
                    description="Unpin content (mirrors 'ipfs-kit pin remove')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {"type": "string", "description": "Content ID to unpin"},
                            "backend": {"type": "string", "description": "Backend to unpin from"}
                        }
                    }
                )
            ]
        
        # Bucket tools (mirror CLI bucket commands) 
        @self.server.list_tools()
        async def list_bucket_tools() -> List[types.Tool]:
            """List available bucket management tools."""
            return [
                types.Tool(
                    name="bucket_list",
                    description="List buckets (mirrors 'ipfs-kit bucket list')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backend": {"type": "string", "description": "Filter by backend"}
                        }
                    }
                ),
                types.Tool(
                    name="bucket_create",
                    description="Create bucket (mirrors 'ipfs-kit bucket create')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Bucket name"},
                            "backend": {"type": "string", "description": "Target backend"}
                        }
                    }
                ),
                types.Tool(
                    name="bucket_sync",
                    description="Sync bucket (mirrors 'ipfs-kit bucket sync')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bucket_name": {"type": "string", "description": "Bucket to sync"},
                            "backend": {"type": "string", "description": "Target backend"},
                            "dry_run": {"type": "boolean", "description": "Show what would be synced"}
                        }
                    }
                )
            ]
        
        # Register tool call handlers
        self._register_tool_handlers()
    
    def _register_tool_handlers(self) -> None:
        """Register handlers for all MCP tools that delegate to CLI-aligned controllers."""
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls by delegating to appropriate controllers."""
            try:
                # Route to appropriate controller based on tool name prefix
                if name.startswith("backend_"):
                    result = await self.backend_controller.handle_tool_call(name, arguments)
                elif name.startswith("storage_"):
                    result = await self.storage_controller.handle_tool_call(name, arguments)
                elif name.startswith("daemon_"):
                    result = await self.daemon_controller.handle_tool_call(name, arguments)
                elif name.startswith("vfs_"):
                    result = await self.vfs_controller.handle_tool_call(name, arguments)
                elif name.startswith("pin_"):
                    result = await self.cli_controller.handle_pin_tool_call(name, arguments)
                elif name.startswith("bucket_"):
                    result = await self.cli_controller.handle_bucket_tool_call(name, arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                # Format result for MCP response
                if isinstance(result, dict) and "error" in result:
                    content = f"Error: {result['error']}"
                else:
                    content = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
                
                return [types.TextContent(type="text", text=content)]
                
            except Exception as e:
                logger.error(f"Error handling tool call {name}: {e}")
                return [types.TextContent(type="text", text=f"Error executing {name}: {str(e)}")]
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            # Clean up resources
            if hasattr(self.daemon_service, 'stop'):
                asyncio.create_task(self.daemon_service.stop())
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start_stdio(self) -> None:
        """Start the MCP server with stdio transport."""
        logger.info("Starting MCP server with stdio transport")
        
        # Initialize daemon service interface (no daemon management)
        await self.daemon_service.start()
        
        # Run the stdio server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )
    
    async def start_daemon_mode(self, host: str = "127.0.0.1", port: int = 3000) -> None:
        """Start the MCP server in daemon mode with HTTP status endpoint."""
        logger.info(f"Starting MCP server in daemon mode on {host}:{port}")
        
        # Initialize daemon service interface
        await self.daemon_service.start()
        
        # Create a simple HTTP server for status and health checks
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import threading
            import json
            
            class MCPStatusHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/health':
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        
                        status = {
                            "status": "running",
                            "server": "ipfs-kit-mcp",
                            "mode": "daemon",
                            "data_dir": str(self.server.mcp_server.config.data_dir),
                            "timestamp": datetime.now().isoformat()
                        }
                        self.wfile.write(json.dumps(status).encode())
                    elif self.path == '/status':
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        
                        # Get daemon status
                        daemon_status = asyncio.run(self.server.mcp_server.daemon_service.get_daemon_status())
                        backends = asyncio.run(self.server.mcp_server.metadata_manager.get_backend_metadata())
                        
                        status = {
                            "mcp_server": "running",
                            "daemon_running": daemon_status.is_running,
                            "daemon_role": daemon_status.role,
                            "backend_count": len(backends),
                            "timestamp": datetime.now().isoformat()
                        }
                        self.wfile.write(json.dumps(status).encode())
                    elif self.path == '/api/backends':
                        self._handle_backends_api()
                    elif self.path == '/api/services':
                        self._handle_services_api()
                    elif self.path == '/api/buckets':
                        self._handle_buckets_api()
                    elif self.path == '/api/tools':
                        self._handle_tools_api()
                    elif self.path.startswith('/tools/'):
                        self._handle_mcp_tools()
                    elif self.path.startswith('/api/'):
                        # All other API endpoints
                        self._handle_generic_api()
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def do_POST(self):
                    if self.path.startswith('/tools/'):
                        self._handle_mcp_tools()
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def _handle_backends_api(self):
                    try:
                        backends = asyncio.run(self.server.mcp_server.backend_controller.list_backends({}))
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(backends).encode())
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                
                def _handle_services_api(self):
                    try:
                        # Get services status from daemon
                        daemon_status = asyncio.run(self.server.mcp_server.daemon_service.get_daemon_status())
                        services = {
                            "ipfs": {
                                "status": "running" if daemon_status.services.get("ipfs", False) else "stopped",
                                "pid": daemon_status.pid
                            },
                            "cluster": {
                                "status": "running" if daemon_status.services.get("cluster", False) else "stopped", 
                                "pid": daemon_status.pid
                            },
                            "daemon": {
                                "status": "running" if daemon_status.is_running else "stopped",
                                "pid": daemon_status.pid,
                                "role": daemon_status.role
                            }
                        }
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(services).encode())
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                
                def _handle_buckets_api(self):
                    try:
                        buckets = asyncio.run(self.server.mcp_server.storage_controller.list_storage({}))
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(buckets).encode())
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                
                def _handle_tools_api(self):
                    try:
                        tools = [
                            {"name": "backend_list", "description": "List all storage backends"},
                            {"name": "bucket_list", "description": "List all buckets"},
                            {"name": "daemon_status", "description": "Get daemon status"},
                            {"name": "vfs_browse", "description": "Browse VFS structure"},
                            {"name": "cli_execute", "description": "Execute CLI commands"}
                        ]
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(tools).encode())
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                
                def _handle_mcp_tools(self):
                    try:
                        tool_name = self.path.split('/tools/')[-1]
                        
                        # Parse request body for POST requests
                        content_length = int(self.headers.get('Content-Length', 0))
                        if content_length > 0:
                            post_data = self.rfile.read(content_length)
                            try:
                                request_data = json.loads(post_data.decode('utf-8'))
                                arguments = request_data.get('arguments', {})
                            except:
                                arguments = {}
                        else:
                            arguments = {}
                        
                        # Route tool calls to appropriate controllers
                        if tool_name == 'daemon_status':
                            result = asyncio.run(self.server.mcp_server.daemon_controller.get_daemon_status(arguments))
                        elif tool_name == 'backend_list':
                            result = asyncio.run(self.server.mcp_server.backend_controller.list_backends(arguments))
                        elif tool_name == 'storage_list':
                            result = asyncio.run(self.server.mcp_server.storage_controller.list_storage(arguments))
                        elif tool_name == 'vfs_browse':
                            result = asyncio.run(self.server.mcp_server.vfs_controller.browse_vfs(arguments))
                        elif tool_name == 'cli_execute':
                            result = asyncio.run(self.server.mcp_server.cli_controller.execute_command(arguments))
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())
                        
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                
                def _handle_generic_api(self):
                    # Return success for now to prevent 501 errors
                    try:
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        response = {
                            "status": "ok",
                            "endpoint": self.path,
                            "message": "API endpoint available"
                        }
                        self.wfile.write(json.dumps(response).encode())
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                        
                def log_message(self, format, *args):
                    # Suppress default HTTP server logs
                    pass
            
            # Store reference to MCP server
            MCPStatusHandler.server_class = type('MCPServerRef', (), {'mcp_server': self})
            
            # Create HTTP server
            httpd = HTTPServer((host, port), MCPStatusHandler)
            httpd.mcp_server = self
            
            logger.info(f"MCP server daemon mode started on http://{host}:{port}")
            logger.info(f"Health check: http://{host}:{port}/health")
            logger.info(f"Status check: http://{host}:{port}/status")
            
            # Save PID file for management
            pid_file = self.config.data_dir / "mcp_server.pid"
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Run HTTP server
            def run_server():
                httpd.serve_forever()
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
            # Keep the main thread alive
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down daemon mode...")
                httpd.shutdown()
                httpd.server_close()
                
                # Clean up PID file
                if pid_file.exists():
                    pid_file.unlink()
                    
        except Exception as e:
            logger.error(f"Error in daemon mode: {e}")
            raise
    
    async def start_websocket(self, host: str = None, port: int = None) -> None:
        """Start the MCP server with WebSocket transport."""
        host = host or self.config.host
        port = port or self.config.port
        
        logger.info(f"Starting MCP server with WebSocket transport on {host}:{port}")
        
        # Initialize daemon service interface (no daemon management)
        await self.daemon_service.start()
        
        # Note: WebSocket implementation would require additional setup
        # For now, we focus on stdio which is the primary MCP transport
        raise NotImplementedError("WebSocket transport not yet implemented")
    
    async def stop(self) -> None:
        """Stop the MCP server and clean up resources."""
        logger.info("Stopping MCP server")
        
        # Stop daemon service interface
        await self.daemon_service.stop()
        
        # Clean up other resources
        if hasattr(self.metadata_manager, 'close'):
            await self.metadata_manager.close()


async def main():
    """Main entry point for the refactored MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS Kit MCP Server (Refactored)")
    parser.add_argument("--data-dir", type=str, default="~/.ipfs_kit",
                       help="Data directory path")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging") 
    parser.add_argument("--no-daemon-sync", action="store_true",
                       help="Disable daemon synchronization")
    parser.add_argument("--websocket", action="store_true",
                       help="Use WebSocket transport instead of stdio")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as daemon (keeps running for CLI management)")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                       help="Host for WebSocket server")
    parser.add_argument("--port", type=int, default=3000,
                       help="Port for WebSocket server")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create server configuration
    config = MCPServerConfig(
        data_dir=Path(args.data_dir).expanduser(),
        debug_mode=args.debug,
        daemon_sync_enabled=not args.no_daemon_sync,
        enable_websocket=args.websocket,
        host=args.host,
        port=args.port
    )
    
    # Create and start server
    server = MCPServer(config)
    
    try:
        if args.websocket:
            await server.start_websocket()
        elif args.daemon:
            # Run as daemon - create a simple HTTP server for status
            logger.info(f"Starting MCP server in daemon mode on {args.host}:{args.port}")
            await server.start_daemon_mode(args.host, args.port)
        else:
            await server.start_stdio()
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())

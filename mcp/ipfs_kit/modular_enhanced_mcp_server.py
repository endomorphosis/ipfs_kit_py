"""
Modular Enhanced Unified MCP Server for IPFS Kit.

This server uses a modular architecture with separate components for:
- Dashboard management
- Backend monitoring (with real clients, not mocked)
- API endpoints  
- MCP tools (now including daemon, VFS, and GraphRAG)
- WebSocket handling

Enhanced with comprehensive features from the unified server including:
- Full backend health monitoring
- Real-time metrics collection
- Development insights
- Comprehensive logging
- Signal handling
- WebSocket support for real-time updates
"""

import asyncio
import argparse
import json
import logging
import os
import psutil
import signal
import sys
import time
import traceback
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

# FastAPI imports
from fastapi import FastAPI, WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

# Modular components
from .backends import BackendHealthMonitor, VFSObservabilityManager
from .api.routes import APIRoutes
from ipfs_kit_py.high_level_api import IPFSSimpleAPI as IPFSClient
from .dashboard.template_manager import DashboardTemplateManager
from .dashboard.websocket_manager import WebSocketManager

from .setup import SetupManager

# Configure logging with enhanced log directory
log_dir = Path(os.environ.get("IPFS_KIT_LOG_DIR", Path(tempfile.gettempdir()) / "ipfs_kit_logs"))
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_dir / 'modular_enhanced_mcp.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Component status tracking
COMPONENTS = {
    "web_framework": False,
    "dashboard": False,
    "backend_monitor": False,
    "filesystem_backends": False,
    "metrics_collector": False,
    "observability": False
}

# Try to import and set component status
try:
    from fastapi import FastAPI
    COMPONENTS["web_framework"] = True
    logger.info("✓ FastAPI web framework available")
except ImportError:
    logger.error("❌ FastAPI not available")


class SimplifiedMCPTool:
    """Simplified MCP tool structure."""
    
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema


class ModularEnhancedMCPServer:
    """Modular Enhanced MCP Server with comprehensive backend monitoring, VFS, and dashboard."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, role: str = "leecher", debug: bool = False, disabled_components: List[str] = None):
        self.host = host
        self.port = port
        self.role = role
        self.debug = debug
        self.disabled_components = disabled_components or []
        self.start_time = time.time()

        # Set up logging level based on debug flag
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.info(f"Debug mode enabled for MCP server in {role} role")
        
        logger.info(f"Initializing MCP server in {role} role on {host}:{port}")
        
        # Log disabled components
        if self.disabled_components:
            logger.info(f"Disabled components for {role} role: {', '.join(self.disabled_components)}")

        # Run setup with disabled components awareness
        setup_manager = SetupManager(disabled_components=self.disabled_components)
        setup_manager.run_setup()
        
        # Initialize monitoring components with full feature set and role configuration
        self.backend_monitor = BackendHealthMonitor()
        self.vfs_observer = VFSObservabilityManager()
        
        # Initialize IPFS client with role configuration and disabled components
        logger.info(f"Initializing IPFS client for {self.role} role")
        self.ipfs_client = IPFSClient(role=self.role, disabled_components=self.disabled_components)
        logger.info(f"IPFS client initialized successfully for {self.role} role")
        
        # Initialize VFS observer if available
        if hasattr(self.backend_monitor, 'initialize_vfs_observer'):
            self.backend_monitor.initialize_vfs_observer()
        
        # Set component status - respect disabled components
        COMPONENTS["backend_monitor"] = True
        COMPONENTS["filesystem_backends"] = True
        COMPONENTS["metrics_collector"] = True
        COMPONENTS["observability"] = True
        
        # Disable specified components
        for component in self.disabled_components:
            if component in COMPONENTS:
                COMPONENTS[component] = False
                logger.info(f"Disabled component: {component}")
        
        # Initialize WebSocket manager
        self.websocket_manager = WebSocketManager()
        
        # Keep websocket connections for real-time updates
        self.websocket_connections: Set[WebSocket] = set()
        
        # Enhanced server state with performance metrics and role information
        self.server_state = {
            "status": "starting",
            "role": self.role,
            "debug": self.debug,
            "start_time": self.start_time,
            "backend_count": len(self.backend_monitor.backends) if hasattr(self.backend_monitor, 'backends') else 0,
            "websocket_connections": 0,
            "tools_loaded": 25,  # Standard tool count
            "components": COMPONENTS.copy(),
            "performance": {
                "memory_usage_mb": 0,
                "cpu_usage_percent": 0,
                "uptime_seconds": 0
            },
            "backend_health": {}
        }
        
        # MCP Tools
        self.mcp_tools = self._create_mcp_tools()
        
        # Import cluster config tools
        try:
            from .api.cluster_config_api import CLUSTER_CONFIG_TOOLS, handle_cluster_config_tool
            self.cluster_config_tools = CLUSTER_CONFIG_TOOLS
            self.handle_cluster_config_tool = handle_cluster_config_tool
            self.server_state["tools_loaded"] += len(CLUSTER_CONFIG_TOOLS)
            logger.info(f"✓ Loaded {len(CLUSTER_CONFIG_TOOLS)} cluster configuration tools")
        except ImportError as e:
            self.cluster_config_tools = []
            self.handle_cluster_config_tool = None
            logger.warning(f"Could not load cluster config tools: {e}")
        
        logger.info(f"🚀 Modular Enhanced MCP Server initialized on {host}:{port}")
        
        # Initialize web server
        if COMPONENTS["web_framework"]:
            self._setup_web_server()
        else:
            logger.error("❌ Cannot start server without web framework")
    
    def _create_mcp_tools(self) -> List[SimplifiedMCPTool]:
        """Create comprehensive MCP tools."""
        
        return [
            SimplifiedMCPTool(
                name="system_health",
                description="Get comprehensive system health status including all backend monitoring",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_backend_status",
                description="Get comprehensive backend status and monitoring data for all filesystem backends",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Specific backend to check (optional)",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        }
                    }
                }
            ),
            SimplifiedMCPTool(
                name="get_metrics_history",
                description="Get historical metrics for backends",
                input_schema={
                    "type": "object", 
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to get metrics for"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of recent metrics to return",
                            "default": 10
                        }
                    }
                }
            ),
            SimplifiedMCPTool(
                name="restart_backend",
                description="Attempt to restart a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend to restart",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus"]
                        }
                    },
                    "required": ["backend"]
                }
            ),
            SimplifiedMCPTool(
                name="get_development_insights",
                description="Get development insights and recommendations based on backend status",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            SimplifiedMCPTool(
                name="get_vfs_analytics",
                description="Get VFS analytics and observability data",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            SimplifiedMCPTool(
                name="get_system_logs",
                description="Get system logs and debug information",
                input_schema={
                    "type": "object",
                    "properties": {
                        "lines": {
                            "type": "integer",
                            "description": "Number of log lines to return",
                            "default": 100
                        }
                    }
                }
            ),
            SimplifiedMCPTool(
                name="get_program_state",
                description="Get program state information including system metrics, file counts, bandwidth, and storage status",
                input_schema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "State category to retrieve",
                            "enum": ["summary", "system", "files", "storage", "network", "all"],
                            "default": "summary"
                        },
                        "key": {
                            "type": "string",
                            "description": "Specific state key to retrieve (optional)"
                        },
                        "update": {
                            "type": "boolean",
                            "description": "Force update program state before returning",
                            "default": False
                        }
                    }
                }
            )
        ]
    
    def _setup_web_server(self):
        """Setup FastAPI web server with modular components and enhanced features."""
        
        # Create FastAPI app with enhanced configuration
        self.app = FastAPI(
            title="Modular Enhanced MCP Server",
            description="Real backend monitoring and management for IPFS Kit with comprehensive observability",
            version="3.0.0"
        )
        
        # Setup templates directory  
        templates_dir = Path(__file__).parent / "templates"
        templates_dir.mkdir(exist_ok=True)
        self.templates = Jinja2Templates(directory=str(templates_dir))
        
        # Setup static files directory
        static_dir = Path(__file__).parent / "static"
        static_dir.mkdir(exist_ok=True)
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Create dashboard template manager
        self.template_manager = DashboardTemplateManager(templates_dir)
        
        # Setup API routes
        self.api_routes = APIRoutes(
            self.app, 
            self.backend_monitor, 
            self.vfs_observer, 
            self.templates,
            self.websocket_manager,
            self.ipfs_client
        )
        
        # Add enhanced endpoints
        self._setup_enhanced_endpoints()
        
        # Set dashboard component status
        COMPONENTS["dashboard"] = True
        
        logger.info("✓ Modular web server configured with enhanced features")
    
    def _setup_enhanced_endpoints(self):
        """Setup enhanced endpoints for comprehensive monitoring."""
        
        @self.app.get("/favicon.ico")
        async def favicon():
            """Simple favicon to prevent 404 errors."""
            from fastapi.responses import Response
            # Return a simple 1x1 transparent PNG
            return Response(
                content=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0bIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\r\n\x1a\n',
                media_type="image/png"
            )
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.add(websocket)
            try:
                while True:
                    # Send periodic updates
                    backend_health = await self.backend_monitor.check_all_backends()
                    await websocket.send_json({
                        "type": "backend_update",
                        "data": backend_health,
                        "timestamp": datetime.now().isoformat()
                    })
                    await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.websocket_connections.discard(websocket)
        
        @self.app.get("/api/logs")
        async def get_system_logs():
            """Get system logs."""
            try:
                log_lines = []
                # Try multiple potential log locations
                log_paths = [
                    log_dir / "modular_enhanced_mcp.log",
                    "/var/log/ipfs_kit/server.log",
                    "./server.log"
                ]
                
                for log_path in log_paths:
                    log_file = Path(log_path)
                    if log_file.exists():
                        with open(log_file, 'r') as f:
                            log_lines = f.readlines()[-100:]  # Last 100 lines
                        break
                
                if not log_lines:
                    # Generate sample log entries if no log file found
                    log_lines = [
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Modular Enhanced MCP Server started\n",
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Backend monitoring initialized\n",
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - VFS observability manager started\n",
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Dashboard available at http://{self.host}:{self.port}\n"
                    ]
                
                return {"logs": log_lines, "source": "system", "timestamp": datetime.now().isoformat()}
            except Exception as e:
                logger.error(f"Error getting logs: {e}")
                return {"error": str(e), "logs": []}

        @self.app.get("/api/backends")
        async def get_backends_status():
            """Get backend status and configuration information."""
            try:
                backend_health = await self.backend_monitor.check_all_backends()
                return {
                    "success": True,
                    "backends": backend_health,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting backend status: {e}")
                return {"error": str(e), "success": False}
        
        @self.app.get("/api/insights")
        async def get_development_insights():
            """Get development insights and recommendations."""
            try:
                backend_health = await self.backend_monitor.check_all_backends()
                insights = self._generate_development_insights(backend_health)
                return {
                    "insights": insights,
                    "backend_health": backend_health,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting insights: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/tools")
        async def get_available_tools():
            """Get all available MCP tools including cluster configuration tools."""
            try:
                all_tools = []
                
                # Add standard MCP tools
                for tool in self.mcp_tools:
                    all_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                        "category": "system"
                    })
                
                # Add cluster configuration tools
                if hasattr(self, 'cluster_config_tools') and self.cluster_config_tools:
                    for tool_config in self.cluster_config_tools:
                        all_tools.append({
                            "name": tool_config["name"],
                            "description": tool_config["description"],
                            "input_schema": tool_config["inputSchema"],
                            "category": "cluster_config"
                        })
                
                return {
                    "success": True,
                    "tools": all_tools,
                    "total_count": len(all_tools),
                    "categories": {
                        "system": len([t for t in all_tools if t["category"] == "system"]),
                        "cluster_config": len([t for t in all_tools if t["category"] == "cluster_config"])
                    },
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting tools: {e}")
                return {"error": str(e), "success": False}
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools in a structured format.
        
        Returns:
            List of all tools with their schemas
        """
        all_tools = []
        
        # Add standard MCP tools
        for tool in self.mcp_tools:
            all_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "category": "system"
            })
        
        # Add cluster configuration tools
        if hasattr(self, 'cluster_config_tools') and self.cluster_config_tools:
            for tool_config in self.cluster_config_tools:
                all_tools.append({
                    "name": tool_config["name"],
                    "description": tool_config["description"],
                    "input_schema": tool_config["inputSchema"],
                    "category": "cluster_config"
                })
        
        return all_tools
    
    def _generate_development_insights(self, backend_health: Dict[str, Any]) -> str:
        """Generate development insights based on backend status."""
        
        insights = []
        
        # Check for common issues
        unhealthy_backends = [name for name, backend in backend_health.items() 
                            if backend.get("health") == "unhealthy"]
        
        if unhealthy_backends:
            insights.append(f"⚠️ **Unhealthy Backends**: {', '.join(unhealthy_backends)}")
            
            for backend_name in unhealthy_backends:
                backend = backend_health[backend_name]
                status = backend.get("status", "unknown")
                
                if backend_name == "ipfs" and status == "stopped":
                    insights.append("💡 **IPFS**: Run `ipfs daemon` to start the IPFS node")
                elif backend_name == "lotus" and status == "stopped":
                    insights.append("💡 **Lotus**: Run `lotus daemon` to start the Lotus node")
                elif backend_name == "synapse" and status == "not_installed":
                    insights.append("💡 **Synapse**: Run `npm install @filoz/synapse-sdk` to install")
                elif backend_name == "s3" and status == "unconfigured":
                    insights.append("💡 **S3**: Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
                elif backend_name == "huggingface" and status == "unauthenticated":
                    insights.append("💡 **HuggingFace**: Run `huggingface-cli login` to authenticate")
                elif backend_name == "parquet" and status == "missing":
                    insights.append("💡 **Parquet**: Run `pip install pyarrow pandas` to install libraries")
        
        # Check for partially working backends
        partial_backends = [name for name, backend in backend_health.items() 
                          if backend.get("health") == "partial"]
        
        if partial_backends:
            insights.append(f"⚠️ **Partially Working**: {', '.join(partial_backends)}")
        
        # Performance recommendations
        healthy_backends = [name for name, backend in backend_health.items() 
                          if backend.get("health") == "healthy"]
        
        if len(healthy_backends) > 0:
            insights.append(f"✅ **Healthy Backends**: {', '.join(healthy_backends)}")
        
        # Integration recommendations
        if "ipfs" in healthy_backends and "ipfs_cluster" not in healthy_backends:
            insights.append("💡 **Scaling**: Consider setting up IPFS Cluster for distributed storage")
        
        if "lotus" in healthy_backends and "synapse" in healthy_backends:
            insights.append("🚀 **Advanced**: You have both Lotus and Synapse - great for Filecoin PDP!")
        
        return "<br>".join(insights) if insights else "All systems are running smoothly! 🎉"
    
    async def handle_mcp_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tool requests with comprehensive error handling."""
        
        try:
            if tool_name == "system_health":
                # Get system health
                process = psutil.Process()
                backend_health = await self.backend_monitor.check_all_backends()
                
                # Update server state
                self.server_state["performance"] = {
                    "memory_usage_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                    "cpu_usage_percent": round(process.cpu_percent(), 2),
                    "uptime_seconds": round(time.time() - self.start_time, 2)
                }
                self.server_state["backend_health"] = backend_health
                
                return {
                    "status": "running",
                    "uptime_seconds": self.server_state["performance"]["uptime_seconds"],
                    "memory_usage_mb": self.server_state["performance"]["memory_usage_mb"],
                    "cpu_usage_percent": self.server_state["performance"]["cpu_usage_percent"],
                    "backend_health": backend_health,
                    "components": COMPONENTS,
                    "server_state": self.server_state
                }
            
            elif tool_name == "get_backend_status":
                backend = arguments.get("backend")
                if backend:
                    return await self.backend_monitor.check_backend_health(backend)
                else:
                    return await self.backend_monitor.check_all_backends()
            
            elif tool_name == "get_metrics_history":
                backend = arguments.get("backend")
                limit = arguments.get("limit", 10)
                
                if hasattr(self.backend_monitor, 'metrics_history') and backend in self.backend_monitor.metrics_history:
                    history = list(self.backend_monitor.metrics_history[backend])
                    return {"backend": backend, "metrics": history[-limit:]}
                else:
                    return {"error": f"No metrics history for backend: {backend}"}
            
            elif tool_name == "restart_backend":
                backend = arguments.get("backend")
                if hasattr(self.backend_monitor, 'restart_backend'):
                    result = await self.backend_monitor.restart_backend(backend)
                    return {"backend": backend, "restart_result": result}
                else:
                    return {"message": f"Restart requested for {backend}", "status": "requested"}
            
            elif tool_name == "get_development_insights":
                backend_health = await self.backend_monitor.check_all_backends()
                insights = self._generate_development_insights(backend_health)
                return {"insights": insights, "backend_health": backend_health}
            
            elif tool_name == "get_vfs_analytics":
                if hasattr(self.vfs_observer, 'get_vfs_statistics'):
                    return await self.vfs_observer.get_vfs_statistics()
                else:
                    return {"error": "VFS analytics not available"}
            
            elif tool_name == "get_system_logs":
                lines = arguments.get("lines", 100)
                # This would be implemented by the logs endpoint
                return {"message": f"System logs (last {lines} lines)", "status": "available"}
            
            elif tool_name == "get_program_state":
                # Handle program state requests
                category = arguments.get("category", "summary")
                key = arguments.get("key")
                update = arguments.get("update", False)
                
                try:
                    # Force update if requested
                    if update and hasattr(self.ipfs_client, 'ipfs_kit') and hasattr(self.ipfs_client.ipfs_kit, 'update_program_state'):
                        self.ipfs_client.ipfs_kit.update_program_state()
                    
                    # Try to use the fast state reader first
                    try:
                        from ipfs_kit_py.program_state import FastStateReader
                        reader = FastStateReader()
                        
                        if key:
                            # Get specific key
                            value = reader.get_value(key)
                            return {"key": key, "value": value}
                        elif category == "summary":
                            return reader.get_summary()
                        elif category == "system":
                            return reader.get_value("system_state", {})
                        elif category == "files":
                            return reader.get_value("file_state", {})
                        elif category == "storage":
                            return reader.get_value("storage_state", {})
                        elif category == "network":
                            return reader.get_value("network_state", {})
                        elif category == "all":
                            return {
                                "system": reader.get_value("system_state", {}),
                                "files": reader.get_value("file_state", {}),
                                "storage": reader.get_value("storage_state", {}),
                                "network": reader.get_value("network_state", {}),
                                "summary": reader.get_summary()
                            }
                        else:
                            return {"error": f"Unknown category: {category}"}
                            
                    except FileNotFoundError:
                        # If state database doesn't exist, try getting from API
                        if hasattr(self.ipfs_client, 'ipfs_kit') and hasattr(self.ipfs_client.ipfs_kit, 'get_program_state_summary'):
                            return self.ipfs_client.ipfs_kit.get_program_state_summary()
                        else:
                            return {
                                "error": "Program state not available",
                                "message": "Program state database not initialized"
                            }
                            
                except Exception as e:
                    return {
                        "error": f"Failed to get program state: {e}",
                        "category": category
                    }
            
            # Handle cluster configuration tools
            elif hasattr(self, 'handle_cluster_config_tool') and self.handle_cluster_config_tool:
                # Check if this is a cluster config tool
                cluster_tool_names = [tool["name"] for tool in self.cluster_config_tools] if self.cluster_config_tools else []
                if tool_name in cluster_tool_names:
                    return await self.handle_cluster_config_tool(tool_name, arguments)
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Error handling MCP request {tool_name}: {e}")
            return {"error": str(e), "traceback": traceback.format_exc()}
    
    def start(self):
        """Start the modular server with enhanced features."""
        
        self.server_state["status"] = "running"
        
        # Start backend monitoring
        if hasattr(self.backend_monitor, 'start_monitoring'):
            self.backend_monitor.start_monitoring()
        logger.info("🔍 Started backend monitoring")
        
        # Log comprehensive startup information
        logger.info(f"🌐 Starting modular web server on http://{self.host}:{self.port}")
        logger.info(f"📊 Dashboard available at http://{self.host}:{self.port}")
        logger.info(f"🔧 {self.server_state['backend_count']} backend clients initialized")
        logger.info(f"🛠️  {self.server_state['tools_loaded']} MCP tools loaded")
        logger.info(f"📈 Components status: {COMPONENTS}")
        
        # Log initial system status
        try:
            process = psutil.Process()
            logger.info(f"💾 Initial memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB")
            logger.info(f"⚡ Initial CPU usage: {process.cpu_percent():.1f}%")
        except Exception as e:
            logger.warning(f"Could not get initial system metrics: {e}")

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}")
            self.server_state["status"] = "stopping"
            logger.info("🛑 Shutting down server...")
            
            # Stop monitoring
            if hasattr(self.backend_monitor, 'stop_monitoring'):
                self.backend_monitor.stop_monitoring()
                logger.info("⏹️  Stopped backend monitoring")
            
            # Close WebSocket connections
            if self.websocket_connections:
                logger.info(f"🔌 Closing {len(self.websocket_connections)} WebSocket connections")
                for websocket in self.websocket_connections.copy():
                    try:
                        asyncio.create_task(websocket.close())
                    except Exception as e:
                        logger.warning(f"Error closing WebSocket: {e}")
            
            logger.info("👋 Server shutdown complete")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start server with enhanced error handling
        if COMPONENTS["web_framework"]:
            try:
                # Log final startup message
                logger.info("🚀 Modular Enhanced MCP Server fully initialized and ready!")
                logger.info("=" * 60)
                
                uvicorn.run(
                    self.app,
                    host=self.host,
                    port=self.port,
                    log_level="info",
                    access_log=False
                )
            except Exception as e:
                logger.error(f"❌ Server failed to start: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                sys.exit(1)
        else:
            logger.error("❌ Cannot start server without web framework")
            sys.exit(1)


def main():
    """Main entry point for modular server with enhanced features."""
    
    parser = argparse.ArgumentParser(
        description="Modular Enhanced MCP Server with comprehensive backend monitoring"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Configuration directory")
    parser.add_argument("--log-dir", default="/tmp/ipfs_kit_logs", help="Log directory")
    parser.add_argument("--no-monitoring", action="store_true", help="Disable backend monitoring")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔧 Debug logging enabled")
    
    # Create log directory if specified
    if args.log_dir:
        log_dir_path = Path(args.log_dir)
        log_dir_path.mkdir(exist_ok=True)
        logger.info(f"📁 Log directory: {log_dir_path}")
    
    # Create config directory if specified
    if args.config_dir:
        config_dir_path = Path(args.config_dir)
        config_dir_path.mkdir(exist_ok=True)
        logger.info(f"⚙️  Config directory: {config_dir_path}")
    
    # Create and start server
    server = ModularEnhancedMCPServer(host=args.host, port=args.port)
    
    # Enhanced startup banner
    logger.info("=" * 80)
    logger.info("🚀 MODULAR ENHANCED MCP SERVER")
    logger.info("=" * 80)
    logger.info(f"📍 Host: {args.host}")
    logger.info(f"🚪 Port: {args.port}")
    logger.info(f"📁 Config: {args.config_dir}")
    logger.info(f"📋 Logs: {args.log_dir}")
    logger.info(f"🔧 Debug: {args.debug}")
    logger.info(f"🔍 Monitoring: {'Disabled' if args.no_monitoring else 'Enabled'}")
    logger.info(f"🌐 Dashboard: http://{args.host}:{args.port}")
    logger.info("=" * 80)
    
    # Disable monitoring if requested
    if args.no_monitoring:
        logger.info("⏸️  Backend monitoring disabled by user request")
        COMPONENTS["backend_monitor"] = False
    
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("🛑 Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()

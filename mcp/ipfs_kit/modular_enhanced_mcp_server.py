"""
Modular Enhanced Unified MCP Server for IPFS Kit.

This server uses a modular architecture with separate components for:
- Dashboard management
- Backend monitoring (with real clients, not mocked)
- API endpoints
- MCP tools (now including daemon, VFS, and GraphRAG)
- WebSocket handling
"""

import asyncio
import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Any

# FastAPI imports
try:
    from fastapi import FastAPI
    from fastapi.templating import Jinja2Templates
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Modular components
from .dashboard import DashboardTemplateManager
from .backends import BackendHealthMonitor
from .api import APIRoutes
from .mcp_tools import MCPToolManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModularEnhancedMCPServer:
    """Modular Enhanced MCP Server with real backend monitoring, VFS, and daemon management."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.start_time = time.time()
        
        # Check dependencies
        if not FASTAPI_AVAILABLE:
            logger.error("❌ FastAPI not available - install with: pip install fastapi uvicorn")
            sys.exit(1)
        
        # Initialize components
        self.backend_monitor = BackendHealthMonitor()
        self.mcp_tools = MCPToolManager(self.backend_monitor)
        
        # Server state
        self.server_state = {
            "status": "starting",
            "start_time": self.start_time,
            "backend_count": len(self.backend_monitor.backends),
            "websocket_connections": 0,
            "tools_loaded": len(self.mcp_tools.get_tools())
        }
        
        # Initialize web server
        self._setup_web_server()
        
        logger.info(f"🚀 Modular Enhanced MCP Server initialized on {host}:{port}")
    
    def _setup_web_server(self):
        """Setup FastAPI web server with modular components."""
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Modular Enhanced MCP Server",
            description="Real backend monitoring and management for IPFS Kit",
            version="3.0.0"
        )
        
        # Setup templates
        templates_dir = Path(__file__).parent / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        # Create dashboard template
        template_manager = DashboardTemplateManager(templates_dir)
        template_manager.create_dashboard_template()
        
        self.templates = Jinja2Templates(directory=str(templates_dir))
        
        # Setup API routes
        self.api_routes = APIRoutes(
            self.app,
            self.backend_monitor,
            self.templates,
            websocket_manager=None  # Will be implemented in WebSocket handler
        )
        
        logger.info("✓ Modular web server configured")
    
    async def handle_mcp_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tool requests using modular tools."""
        return await self.mcp_tools.handle_tool_request(tool_name, arguments)
    
    def get_mcp_tools(self):
        """Get available MCP tools."""
        return self.mcp_tools.get_tools()
    
    def start(self):
        """Start the modular server."""
        
        self.server_state["status"] = "running"
        
        # Start backend monitoring
        self.backend_monitor.start_monitoring()
        
        logger.info(f"🌐 Starting modular web server on http://{self.host}:{self.port}")
        logger.info(f"📊 Dashboard available at http://{self.host}:{self.port}")
        logger.info(f"🔧 {len(self.backend_monitor.backends)} backend clients initialized")
        logger.info(f"🛠️  {self.server_state['tools_loaded']} MCP tools loaded.")

        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}")
            self.server_state["status"] = "stopping"
            self.backend_monitor.stop_monitoring()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start server
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=False
            )
        except Exception as e:
            logger.error(f"❌ Server failed to start: {e}")
            sys.exit(1)


def main():
    """Main entry point for modular server."""
    
    parser = argparse.ArgumentParser(description="Modular Enhanced MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Configuration directory")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start server
    server = ModularEnhancedMCPServer(host=args.host, port=args.port)
    
    logger.info("=" * 60)
    logger.info("🚀 MODULAR ENHANCED MCP SERVER")
    logger.info("=" * 60)
    logger.info(f"📍 Host: {args.host}")
    logger.info(f"🚪 Port: {args.port}")
    logger.info(f"📁 Config: {args.config_dir}")
    logger.info(f"🔧 Debug: {args.debug}")
    logger.info("=" * 60)
    
    server.start()


if __name__ == "__main__":
    main()

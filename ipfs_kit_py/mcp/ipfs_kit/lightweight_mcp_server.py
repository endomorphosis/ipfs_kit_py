"""
Lightweight MCP Server for IPFS Kit.

This refactored MCP server is a lightweight client that communicates with
the IPFS Kit daemon for all heavy operations. The server focuses on:
- MCP protocol handling
- Tool definitions and routing
- Client communication
- Dashboard serving

All backend management, health monitoring, and pin operations are delegated
to the IPFS Kit daemon.
"""

import anyio
import json
import logging
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path

# FastAPI for web interface
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# MCP protocol
from mcp import McpServer
from mcp.types import Tool, TextContent

# Daemon client
from .daemon.daemon_client import IPFSKitDaemonClient, DaemonAwareComponent

logger = logging.getLogger(__name__)

class LightweightMCPServer(DaemonAwareComponent):
    """
    Lightweight MCP Server that delegates heavy operations to the daemon.
    
    This server handles:
    - MCP protocol and tool definitions
    - Web dashboard serving
    - WebSocket connections for real-time updates
    - Request routing to daemon
    """
    
    def __init__(self, 
                 host: str = "127.0.0.1",
                 port: int = 8888,
                 daemon_host: str = "127.0.0.1", 
                 daemon_port: int = 9999):
        
        # Initialize daemon client
        daemon_client = IPFSKitDaemonClient(daemon_host, daemon_port)
        super().__init__(daemon_client)
        
        self.host = host
        self.port = port
        
        # MCP server instance
        self.mcp_server = McpServer("ipfs-kit")
        
        # FastAPI app for web interface
        self.app = self._create_web_app()
        
        # WebSocket connections for real-time updates
        self.websocket_connections = set()
        
        # Register MCP tools
        self._register_mcp_tools()
        
        logger.info(f"🚀 Lightweight MCP Server initialized")
        logger.info(f"📍 Web interface: http://{host}:{port}")
        logger.info(f"🔗 Daemon: http://{daemon_host}:{daemon_port}")
    
    def _create_web_app(self) -> FastAPI:
        """Create FastAPI application for web interface."""
        app = FastAPI(
            title="IPFS Kit MCP Server",
            description="Lightweight MCP server with daemon backend",
            version="1.0.0"
        )
        
        # Serve static files
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
        
        # Templates
        template_dir = Path(__file__).parent / "templates"
        if template_dir.exists():
            templates = Jinja2Templates(directory=template_dir)
        
        # Dashboard endpoint
        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Serve the main dashboard."""
            try:
                # Get status from daemon
                daemon_status = await self.daemon_client.get_daemon_status()
                health_status = await self.daemon_client.get_health()
                
                dashboard_html = self._generate_dashboard_html(daemon_status, health_status)
                return HTMLResponse(content=dashboard_html)
                
            except Exception as e:
                logger.error(f"Error generating dashboard: {e}")
                error_html = f"""
                <html>
                <head><title>IPFS Kit Dashboard - Error</title></head>
                <body>
                    <h1>❌ Dashboard Error</h1>
                    <p>Could not connect to IPFS Kit daemon.</p>
                    <p>Error: {e}</p>
                </body>
                </html>
                """
                return HTMLResponse(content=error_html)
        
        # API endpoints that proxy to daemon
        @app.get("/api/health")
        async def api_health():
            """Health status API endpoint."""
            health_data = await self.daemon_client.get_health()
            return JSONResponse(content=health_data)
        
        @app.get("/api/pins")
        async def api_pins():
            """Pins listing API endpoint."""
            pins_data = await self.daemon_client.list_pins()
            return JSONResponse(content=pins_data)
        
        @app.post("/api/pins/{cid}")
        async def api_add_pin(cid: str):
            """Add pin API endpoint."""
            result = await self.daemon_client.add_pin(cid)
            
            # Notify WebSocket clients
            await self._broadcast_update({
                "type": "pin_added",
                "cid": cid,
                "result": result
            })
            
            return JSONResponse(content=result)
        
        @app.delete("/api/pins/{cid}")
        async def api_remove_pin(cid: str):
            """Remove pin API endpoint."""
            result = await self.daemon_client.remove_pin(cid)
            
            # Notify WebSocket clients
            await self._broadcast_update({
                "type": "pin_removed", 
                "cid": cid,
                "result": result
            })
            
            return JSONResponse(content=result)
        
        # WebSocket endpoint for real-time updates
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.add(websocket)
            
            try:
                # Send initial status
                daemon_status = await self.daemon_client.get_daemon_status()
                await websocket.send_json({
                    "type": "status_update",
                    "data": daemon_status
                })
                
                # Keep connection alive and handle messages
                while True:
                    message = await websocket.receive_text()
                    
                    # Handle client messages if needed
                    try:
                        data = json.loads(message)
                        await self._handle_websocket_message(websocket, data)
                    except json.JSONDecodeError:
                        await websocket.send_json({
                            "type": "error",
                            "error": "Invalid JSON message"
                        })
                        
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.websocket_connections.discard(websocket)
        
        return app
    
    def _register_mcp_tools(self):
        """Register MCP tools that delegate to daemon."""
        
        # Pin management tools
        @self.mcp_server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available MCP tools."""
            return [
                Tool(
                    name="add_pin",
                    description="Add a pin to IPFS with replication",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {
                                "type": "string",
                                "description": "Content ID to pin"
                            }
                        },
                        "required": ["cid"]
                    }
                ),
                Tool(
                    name="remove_pin", 
                    description="Remove a pin from IPFS",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {
                                "type": "string", 
                                "description": "Content ID to unpin"
                            }
                        },
                        "required": ["cid"]
                    }
                ),
                Tool(
                    name="list_pins",
                    description="List all pins with metadata",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_health",
                    description="Get comprehensive system health status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="start_backend",
                    description="Start a backend service",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backend": {
                                "type": "string",
                                "description": "Backend name (ipfs, cluster, lotus)"
                            }
                        },
                        "required": ["backend"]
                    }
                ),
                Tool(
                    name="stop_backend",
                    description="Stop a backend service", 
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backend": {
                                "type": "string",
                                "description": "Backend name (ipfs, cluster, lotus)"
                            }
                        },
                        "required": ["backend"]
                    }
                ),
                Tool(
                    name="get_backend_logs",
                    description="Get logs for a backend service",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "backend": {
                                "type": "string",
                                "description": "Backend name"
                            },
                            "lines": {
                                "type": "integer",
                                "description": "Number of log lines",
                                "default": 100
                            }
                        },
                        "required": ["backend"]
                    }
                )
            ]
        
        @self.mcp_server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle MCP tool calls by delegating to daemon."""
            
            # Ensure daemon connection
            if not await self.ensure_daemon_connection():
                return [TextContent(
                    type="text",
                    text="❌ Cannot connect to IPFS Kit daemon"
                )]
            
            try:
                # Route tool calls to daemon
                if name == "add_pin":
                    result = await self.daemon_client.add_pin(arguments["cid"])
                elif name == "remove_pin":
                    result = await self.daemon_client.remove_pin(arguments["cid"])
                elif name == "list_pins":
                    result = await self.daemon_client.list_pins()
                elif name == "get_health":
                    result = await self.daemon_client.get_health()
                elif name == "start_backend":
                    result = await self.daemon_client.start_backend(arguments["backend"])
                elif name == "stop_backend":
                    result = await self.daemon_client.stop_backend(arguments["backend"])
                elif name == "get_backend_logs":
                    lines = arguments.get("lines", 100)
                    result = await self.daemon_client.get_backend_logs(arguments["backend"], lines)
                else:
                    result = {"success": False, "error": f"Unknown tool: {name}"}
                
                # Format result as text
                result_text = json.dumps(result, indent=2)
                return [TextContent(type="text", text=result_text)]
                
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                return [TextContent(
                    type="text", 
                    text=f"❌ Error calling {name}: {e}"
                )]
    
    def _generate_dashboard_html(self, daemon_status: Dict[str, Any], health_status: Dict[str, Any]) -> str:
        """Generate HTML for the dashboard."""
        # Simple HTML dashboard
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>IPFS Kit Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .status-indicator {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }}
                .status-healthy {{ background: #4CAF50; }}
                .status-unhealthy {{ background: #f44336; }}
                .status-unknown {{ background: #ff9800; }}
                h1 {{ color: #333; }}
                h2 {{ color: #555; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
                .metric {{ text-align: center; padding: 15px; background: #f8f9fa; border-radius: 6px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
                .metric-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
                pre {{ background: #f8f9fa; padding: 15px; border-radius: 6px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 IPFS Kit Dashboard</h1>
                
                <div class="card">
                    <h2>Daemon Status</h2>
                    <p>
                        <span class="status-indicator status-{'healthy' if daemon_status.get('running') else 'unhealthy'}"></span>
                        Daemon: {'Running' if daemon_status.get('running') else 'Stopped'}
                    </p>
                    <p>Uptime: {daemon_status.get('uptime_seconds', 0):.0f} seconds</p>
                    <p>API Version: {daemon_status.get('api_version', 'unknown')}</p>
                </div>
                
                <div class="card">
                    <h2>System Health</h2>
                    <p>
                        <span class="status-indicator status-{'healthy' if health_status.get('system_healthy') else 'unhealthy'}"></span>
                        Overall: {'Healthy' if health_status.get('system_healthy') else 'Issues Detected'}
                    </p>
                    
                    <div class="metrics">
        """
        
        # Add component metrics
        components = health_status.get('components', {})
        for comp_name, comp_data in components.items():
            if isinstance(comp_data, dict):
                status = 'healthy' if comp_data.get('healthy', False) else 'unhealthy'
                html += f"""
                        <div class="metric">
                            <div class="metric-value">
                                <span class="status-indicator status-{status}"></span>
                            </div>
                            <div class="metric-label">{comp_name.replace('_', ' ').title()}</div>
                        </div>
                """
        
        html += """
                    </div>
                </div>
                
                <div class="card">
                    <h2>Quick Actions</h2>
                    <button onclick="refreshStatus()">🔄 Refresh Status</button>
                    <button onclick="viewPins()">📎 View Pins</button>
                    <button onclick="viewLogs()">📋 View Logs</button>
                </div>
                
                <div class="card">
                    <h2>Real-time Status</h2>
                    <div id="realtime-status">Connecting...</div>
                </div>
            </div>
            
            <script>
                // WebSocket connection for real-time updates
                const ws = new WebSocket('ws://localhost:8888/ws');
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    document.getElementById('realtime-status').innerHTML = 
                        '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                };
                
                ws.onopen = function() {
                    document.getElementById('realtime-status').innerHTML = '✅ Connected to real-time updates';
                };
                
                ws.onerror = function() {
                    document.getElementById('realtime-status').innerHTML = '❌ WebSocket connection error';
                };
                
                function refreshStatus() { window.location.reload(); }
                function viewPins() { window.open('/api/pins', '_blank'); }
                function viewLogs() { alert('Logs feature coming soon!'); }
            </script>
        </body>
        </html>
        """
        
        return html
    
    async def _handle_websocket_message(self, websocket: WebSocket, data: Dict[str, Any]):
        """Handle incoming WebSocket messages."""
        message_type = data.get("type")
        
        if message_type == "ping":
            await websocket.send_json({"type": "pong"})
        elif message_type == "get_status":
            status = await self.daemon_client.get_daemon_status() 
            await websocket.send_json({
                "type": "status_update",
                "data": status
            })
    
    async def _broadcast_update(self, message: Dict[str, Any]):
        """Broadcast update to all WebSocket connections."""
        if not self.websocket_connections:
            return
        
        # Send to all connected clients
        disconnected = set()
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.add(websocket)
        
        # Remove disconnected clients
        self.websocket_connections -= disconnected
    
    async def start(self):
        """Start the lightweight MCP server."""
        logger.info("🚀 Starting Lightweight MCP Server...")
        
        # Wait for daemon to be available
        logger.info("⏳ Waiting for daemon connection...")
        if not await self.ensure_daemon_connection():
            logger.error("❌ Cannot connect to daemon - server startup failed")
            return False
        
        logger.info("✓ Daemon connection established")
        
        # Start background status monitoring
        anyio.lowlevel.spawn_system_task(self._status_monitoring_loop)
        
        # Start FastAPI server
        logger.info(f"🌐 Starting web server on {self.host}:{self.port}")
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"❌ Error running MCP server: {e}")
            return False
        
        return True
    
    async def _status_monitoring_loop(self):
        """Background loop to monitor daemon status and broadcast updates."""
        while True:
            try:
                # Get current status
                daemon_status = await self.daemon_client.get_daemon_status()
                health_status = await self.daemon_client.get_health()
                
                # Broadcast to WebSocket clients
                await self._broadcast_update({
                    "type": "status_update",
                    "daemon_status": daemon_status,
                    "health_status": health_status,
                    "timestamp": anyio.current_time()
                })
                
                # Wait 30 seconds before next update
                await anyio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in status monitoring loop: {e}")
                await anyio.sleep(60)  # Wait longer on error


async def main():
    """Main entry point for the lightweight MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Lightweight IPFS Kit MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to")
    parser.add_argument("--daemon-host", default="127.0.0.1", help="Daemon host")
    parser.add_argument("--daemon-port", type=int, default=9999, help="Daemon port")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start server
    server = LightweightMCPServer(
        host=args.host,
        port=args.port,
        daemon_host=args.daemon_host,
        daemon_port=args.daemon_port
    )
    
    print("=" * 80)
    print("🚀 LIGHTWEIGHT MCP SERVER")  
    print("=" * 80)
    print(f"📍 Web Interface: http://{args.host}:{args.port}")
    print(f"🔗 Daemon: http://{args.daemon_host}:{args.daemon_port}")
    print(f"🔍 Debug: {args.debug}")
    print("=" * 80)
    print("🌐 Starting server...")
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n🛑 Server interrupted by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)

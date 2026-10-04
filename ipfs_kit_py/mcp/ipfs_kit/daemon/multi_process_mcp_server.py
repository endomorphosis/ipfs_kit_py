#!/usr/bin/env python3
"""
Multi-Processing Enhanced MCP Server.

This MCP server uses multi-processing for high throughput operations:
- Process pools for CPU-intensive tasks
- Thread pools for I/O bound operations
- Async request handling
- Concurrent tool execution
- Background task processing
- High-performance dashboard
"""

import anyio
import json
import logging
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional

# FastAPI for web dashboard
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# MCP protocol components
from mcp.server.models import InitializationOptions, TextContent, Tool
from mcp.server import NotificationOptions, Server
from mcp.types import Resource
import mcp.types as types

# Core components
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from .daemon_client import IPFSKitDaemonClient, DaemonAwareComponent

logger = logging.getLogger(__name__)

class MultiProcessMCPServer(DaemonAwareComponent):
    """
    Multi-processing enhanced MCP server for high-throughput IPFS Kit operations.
    
    Features:
    - Process pools for parallel tool execution
    - Async MCP protocol handling
    - High-performance web dashboard
    - Background task processing
    - Real-time WebSocket updates
    """
    
    def __init__(self, 
                 daemon_url: str = "http://127.0.0.1:9999",
                 web_host: str = "127.0.0.1",
                 web_port: int = 8080,
                 max_workers: int = None):
        
        super().__init__(daemon_url)
        
        self.web_host = web_host
        self.web_port = web_port
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        
        # Multi-processing components
        self.process_pool = None
        self.thread_pool = None
        
        # MCP Server
        self.mcp_server = Server("ipfs-kit-multiprocess")
        
        # FastAPI app for dashboard
        self.web_app = self._create_web_app()
        
        # WebSocket connections for real-time updates
        self.websocket_connections = set()
        
        # Performance tracking
        self.performance_stats = {
            'mcp_operations': 0,
            'tool_executions': 0,
            'websocket_connections': 0,
            'start_time': None,
            'total_response_time': 0.0
        }
        
        # Setup MCP tools and handlers
        self._setup_mcp_tools()
        self._setup_mcp_handlers()
        
        logger.info(f"🔧 Multi-Processing MCP Server initialized")
        logger.info(f"🌐 Web dashboard: http://{web_host}:{web_port}")
        logger.info(f"⚡ Workers: {self.max_workers}")
    
    def _create_web_app(self) -> FastAPI:
        """Create FastAPI web application with high-performance dashboard."""
        app = FastAPI(
            title="Multi-Processing IPFS Kit MCP Server",
            description="High-throughput MCP server with multi-processing support",
            version="2.0.0"
        )
        
        # Dashboard endpoints
        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """High-performance dashboard with real-time updates."""
            return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Multi-Processing IPFS Kit MCP Server</title>
    <style>
        body {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.15);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .stat-title {
            font-size: 14px;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 28px;
            font-weight: bold;
            color: #4CAF50;
        }
        .operations-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .operation-btn {
            padding: 15px 20px;
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            transition: transform 0.2s;
        }
        .operation-btn:hover {
            transform: translateY(-2px);
        }
        .log-container {
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 15px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
        }
        .log-entry {
            margin-bottom: 5px;
            padding: 5px;
            border-radius: 3px;
        }
        .log-info { background: rgba(0,150,255,0.2); }
        .log-success { background: rgba(0,255,0,0.2); }
        .log-error { background: rgba(255,0,0,0.2); }
        .performance-chart {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            margin-top: 20px;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online { background: #4CAF50; }
        .status-offline { background: #f44336; }
        .progress-bar {
            width: 100%;
            height: 6px;
            background: rgba(255,255,255,0.2);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚡ Multi-Processing IPFS Kit MCP Server</h1>
            <p>High-throughput operations with multi-processing support</p>
            <div>
                <span class="status-indicator status-online"></span>
                <strong>Status: </strong><span id="server-status">Connected</span>
                <span style="margin-left: 20px;"><strong>Workers: </strong><span id="worker-count">0</span></span>
                <span style="margin-left: 20px;"><strong>Uptime: </strong><span id="uptime">0s</span></span>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">🔧 MCP Operations</div>
                <div class="stat-value" id="mcp-operations">0</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="mcp-progress" style="width: 0%"></div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-title">⚡ Tool Executions</div>
                <div class="stat-value" id="tool-executions">0</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="tool-progress" style="width: 0%"></div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-title">🌐 WebSocket Connections</div>
                <div class="stat-value" id="websocket-connections">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">📊 Avg Response Time</div>
                <div class="stat-value" id="response-time">0ms</div>
            </div>
        </div>

        <div class="operations-grid">
            <button class="operation-btn" onclick="performOperation('health-check')">
                🏥 Health Check
            </button>
            <button class="operation-btn" onclick="performOperation('list-pins')">
                📌 List Pins
            </button>
            <button class="operation-btn" onclick="performOperation('stress-test')">
                🔥 Stress Test
            </button>
            <button class="operation-btn" onclick="performOperation('performance-monitor')">
                📊 Performance Monitor
            </button>
        </div>

        <div class="performance-chart">
            <h3>📈 Real-time Performance</h3>
            <canvas id="performance-chart" width="800" height="200"></canvas>
        </div>

        <div>
            <h3>📋 Real-time Logs</h3>
            <div class="log-container" id="log-container">
                <div class="log-entry log-info">
                    [INFO] Multi-processing MCP server dashboard loaded
                </div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection for real-time updates
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const logContainer = document.getElementById('log-container');
        
        // Performance chart
        const canvas = document.getElementById('performance-chart');
        const ctx = canvas.getContext('2d');
        const performanceData = [];
        
        ws.onopen = function() {
            addLog('WebSocket connected for real-time updates', 'success');
        };
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        };
        
        ws.onclose = function() {
            addLog('WebSocket connection closed', 'error');
            document.getElementById('server-status').textContent = 'Disconnected';
            document.querySelector('.status-indicator').className = 'status-indicator status-offline';
        };
        
        function updateDashboard(data) {
            if (data.type === 'stats') {
                document.getElementById('mcp-operations').textContent = data.mcp_operations;
                document.getElementById('tool-executions').textContent = data.tool_executions;
                document.getElementById('websocket-connections').textContent = data.websocket_connections;
                document.getElementById('worker-count').textContent = data.workers || 0;
                document.getElementById('uptime').textContent = formatUptime(data.uptime || 0);
                
                // Update response time
                const avgResponseTime = data.total_response_time && data.mcp_operations > 0 
                    ? (data.total_response_time / data.mcp_operations).toFixed(1)
                    : '0';
                document.getElementById('response-time').textContent = avgResponseTime + 'ms';
                
                // Update progress bars
                const maxOps = Math.max(data.mcp_operations, data.tool_executions, 100);
                document.getElementById('mcp-progress').style.width = (data.mcp_operations / maxOps * 100) + '%';
                document.getElementById('tool-progress').style.width = (data.tool_executions / maxOps * 100) + '%';
                
                // Update performance chart
                updatePerformanceChart(data);
            } else if (data.type === 'log') {
                addLog(data.message, data.level);
            }
        }
        
        function updatePerformanceChart(data) {
            performanceData.push({
                timestamp: Date.now(),
                operations: data.mcp_operations,
                tools: data.tool_executions
            });
            
            // Keep only last 60 data points
            if (performanceData.length > 60) {
                performanceData.shift();
            }
            
            drawPerformanceChart();
        }
        
        function drawPerformanceChart() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            if (performanceData.length < 2) return;
            
            const maxValue = Math.max(...performanceData.map(d => Math.max(d.operations, d.tools)), 1);
            const stepX = canvas.width / (performanceData.length - 1);
            
            // Draw operations line
            ctx.strokeStyle = '#4CAF50';
            ctx.lineWidth = 2;
            ctx.beginPath();
            performanceData.forEach((data, index) => {
                const x = index * stepX;
                const y = canvas.height - (data.operations / maxValue) * canvas.height;
                if (index === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
            
            // Draw tools line
            ctx.strokeStyle = '#2196F3';
            ctx.beginPath();
            performanceData.forEach((data, index) => {
                const x = index * stepX;
                const y = canvas.height - (data.tools / maxValue) * canvas.height;
                if (index === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }
        
        function addLog(message, level = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry log-${level}`;
            logEntry.innerHTML = `[${timestamp}] ${message}`;
            
            logContainer.appendChild(logEntry);
            logContainer.scrollTop = logContainer.scrollHeight;
            
            // Keep only last 100 log entries
            while (logContainer.children.length > 100) {
                logContainer.removeChild(logContainer.firstChild);
            }
        }
        
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            return `${hours}h ${minutes}m ${secs}s`;
        }
        
        function performOperation(operation) {
            addLog(`Performing operation: ${operation}`, 'info');
            
            // Send operation request via WebSocket
            ws.send(JSON.stringify({
                type: 'operation',
                operation: operation
            }));
        }
        
        // Request initial data
        fetch('/api/stats')
            .then(response => response.json())
            .then(data => updateDashboard({type: 'stats', ...data}))
            .catch(err => addLog(`Failed to load initial stats: ${err}`, 'error'));
        
        // Periodic stats update
        setInterval(() => {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => updateDashboard({type: 'stats', ...data}))
                .catch(err => console.error('Stats update failed:', err));
        }, 2000);
    </script>
</body>
</html>
            """
        
        @app.get("/api/stats")
        async def get_stats():
            """Get current server statistics."""
            uptime = time.time() - (self.performance_stats['start_time'] or time.time())
            
            return JSONResponse(content={
                "mcp_operations": self.performance_stats['mcp_operations'],
                "tool_executions": self.performance_stats['tool_executions'],
                "websocket_connections": len(self.websocket_connections),
                "workers": self.max_workers,
                "uptime": uptime,
                "total_response_time": self.performance_stats['total_response_time']
            })
        
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.add(websocket)
            
            try:
                while True:
                    # Wait for messages from client
                    data = await websocket.receive_json()
                    
                    if data.get('type') == 'operation':
                        # Handle operation requests
                        operation = data.get('operation')
                        result = await self._handle_websocket_operation(operation)
                        
                        await websocket.send_json({
                            "type": "log",
                            "message": f"Operation {operation} completed: {result.get('success', False)}",
                            "level": "success" if result.get('success') else "error"
                        })
                        
            except WebSocketDisconnect:
                self.websocket_connections.discard(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.websocket_connections.discard(websocket)
        
        return app
    
    async def _handle_websocket_operation(self, operation: str) -> Dict[str, Any]:
        """Handle WebSocket operation requests."""
        try:
            if operation == "health-check":
                return await self.daemon_client.get_health()
            elif operation == "list-pins":
                return await self.daemon_client.list_pins()
            elif operation == "stress-test":
                # Run mini stress test
                operations = [{"operation": "add", "cid": f"QmTest{i:06d}{'0'*40}"} for i in range(10)]
                return await self.daemon_client.batch_pin_operations(operations)
            elif operation == "performance-monitor":
                return await self.daemon_client._make_request("GET", "/performance")
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _setup_mcp_tools(self):
        """Setup MCP tools with multi-processing support."""
        
        # Health monitoring tool
        @self.mcp_server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List available tools with multi-processing capabilities."""
            return [
                types.Tool(
                    name="health_check",
                    description="Check daemon health with parallel processing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fast": {
                                "type": "boolean",
                                "description": "Use fast health check mode"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="list_pins_concurrent",
                    description="List pins using concurrent processing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of pins to return"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="batch_pin_operations",
                    description="Execute multiple pin operations concurrently",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "operations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "operation": {"type": "string", "enum": ["add", "remove"]},
                                        "cid": {"type": "string"}
                                    }
                                },
                                "description": "Array of pin operations to execute"
                            }
                        },
                        "required": ["operations"]
                    }
                ),
                types.Tool(
                    name="performance_stress_test",
                    description="Run performance stress test with multi-processing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "num_operations": {
                                "type": "integer",
                                "description": "Number of operations to perform",
                                "default": 100
                            },
                            "operation_type": {
                                "type": "string",
                                "enum": ["add", "remove", "mixed"],
                                "description": "Type of operations to perform",
                                "default": "mixed"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="backend_management",
                    description="Manage backends with parallel processing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["start", "stop", "restart", "status"]
                            },
                            "backend": {
                                "type": "string",
                                "enum": ["ipfs", "cluster", "lotus", "all"]
                            }
                        },
                        "required": ["action", "backend"]
                    }
                )
            ]
        
        # Tool execution handlers with process pools
        @self.mcp_server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool calls with multi-processing support."""
            start_time = time.time()
            
            try:
                self.performance_stats['tool_executions'] += 1
                
                # Execute tool in process pool for CPU-intensive operations
                if name == "health_check":
                    result = await anyio.to_thread.run_sync(
                        self._execute_health_check_tool,
                        arguments
                    )
                elif name == "list_pins_concurrent":
                    result = await anyio.to_thread.run_sync(
                        self._execute_list_pins_tool,
                        arguments
                    )
                elif name == "batch_pin_operations":
                    result = await anyio.to_process.run_sync(
                        self._execute_batch_operations_tool,
                        arguments
                    )
                elif name == "performance_stress_test":
                    result = await anyio.to_process.run_sync(
                        self._execute_stress_test_tool,
                        arguments
                    )
                elif name == "backend_management":
                    result = await anyio.to_process.run_sync(
                        self._execute_backend_management_tool,
                        arguments
                    )
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                # Track performance
                execution_time = (time.time() - start_time) * 1000
                self.performance_stats['total_response_time'] += execution_time
                
                # Broadcast update to WebSocket clients
                await self._broadcast_update({
                    "type": "log",
                    "message": f"Tool {name} executed in {execution_time:.1f}ms",
                    "level": "success" if not result.get('error') else "error"
                })
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, indent=2)
                )]
    
    def _execute_health_check_tool(self, arguments: dict) -> dict:
        """Execute health check tool in thread pool."""
        try:
            # Create async event loop in thread
            fast = arguments.get('fast', False)
            endpoint = "/health/fast" if fast else "/health"

            result = anyio.run(self.daemon_client._make_request, "GET", endpoint)
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_list_pins_tool(self, arguments: dict) -> dict:
        """Execute list pins tool in thread pool."""
        try:
            result = anyio.run(self.daemon_client.list_pins)
            
            limit = arguments.get('limit')
            if limit and 'pins' in result:
                result['pins'] = result['pins'][:limit]
                result['limited'] = True
                result['limit'] = limit
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_batch_operations_tool(self, arguments: dict) -> dict:
        """Execute batch operations tool in process pool."""
        try:
            operations = arguments.get('operations', [])
            result = anyio.run(self.daemon_client.batch_pin_operations, operations)
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_stress_test_tool(self, arguments: dict) -> dict:
        """Execute stress test tool in process pool."""
        try:
            num_operations = arguments.get('num_operations', 100)
            operation_type = arguments.get('operation_type', 'mixed')
            
            # Generate test operations
            operations = []
            test_cid_base = "QmTest" + "0" * 40
            
            if operation_type == "add":
                operations = [{"operation": "add", "cid": f"{test_cid_base}{i:06d}"} 
                             for i in range(num_operations)]
            elif operation_type == "remove":
                operations = [{"operation": "remove", "cid": f"{test_cid_base}{i:06d}"} 
                             for i in range(num_operations)]
            else:  # mixed
                for i in range(num_operations):
                    op_type = "add" if i % 2 == 0 else "remove"
                    operations.append({"operation": op_type, "cid": f"{test_cid_base}{i:06d}"})
            
            start_time = time.time()
            result = anyio.run(self.daemon_client.batch_pin_operations, operations)
            total_time = time.time() - start_time
            
            # Add stress test metrics
            result.update({
                "stress_test": True,
                "operation_type": operation_type,
                "total_time_seconds": total_time,
                "throughput_ops_per_second": num_operations / total_time if total_time > 0 else 0
            })
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_backend_management_tool(self, arguments: dict) -> dict:
        """Execute backend management tool in process pool."""
        try:
            action = arguments.get('action')
            backend = arguments.get('backend')
            
            if action == "start":
                result = anyio.run(self.daemon_client._make_request, "POST", f"/backends/{backend}/start")
            elif action == "status":
                result = anyio.run(self.daemon_client.get_health)
                # Filter for specific backend if not 'all'
                if backend != 'all' and 'backends' in result:
                    backend_status = result['backends'].get(backend, {})
                    result = {
                        "backend": backend,
                        "status": backend_status
                    }
            else:
                result = {"error": f"Unsupported action: {action}"}
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    def _setup_mcp_handlers(self):
        """Setup MCP server handlers."""
        
        @self.mcp_server.list_resources()
        async def handle_list_resources() -> list[types.Resource]:
            """List available resources."""
            return [
                types.Resource(
                    uri="ipfs://health-status",
                    name="Health Status",
                    description="Current daemon and backend health status",
                    mimeType="application/json"
                ),
                types.Resource(
                    uri="ipfs://pin-index",
                    name="Pin Index",
                    description="Current pin index with metadata",
                    mimeType="application/json"
                ),
                types.Resource(
                    uri="ipfs://performance-metrics",
                    name="Performance Metrics",
                    description="Real-time performance metrics",
                    mimeType="application/json"
                )
            ]
        
        @self.mcp_server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read resource content with multi-processing."""
            try:
                self.performance_stats['mcp_operations'] += 1
                
                if uri == "ipfs://health-status":
                    result = await self.daemon_client.get_health()
                elif uri == "ipfs://pin-index":
                    result = await self.daemon_client.list_pins()
                elif uri == "ipfs://performance-metrics":
                    result = await self.daemon_client._make_request("GET", "/performance")
                else:
                    result = {"error": f"Unknown resource: {uri}"}
                
                return json.dumps(result, indent=2)
                
            except Exception as e:
                return json.dumps({"error": str(e)}, indent=2)
    
    async def _broadcast_update(self, data: dict):
        """Broadcast update to all WebSocket connections."""
        if not self.websocket_connections:
            return
        
        # Send to all connected clients
        disconnected = set()
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(data)
            except Exception:
                disconnected.add(websocket)
        
        # Remove disconnected clients
        self.websocket_connections -= disconnected
    
    async def start(self):
        """Start the multi-processing MCP server."""
        logger.info("🚀 Starting Multi-Processing MCP Server...")
        
        # Initialize process pools
        self.process_pool = ProcessPoolExecutor(max_workers=self.max_workers)
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers * 2)
        
        logger.info(f"⚡ Initialized {self.max_workers} process workers")
        logger.info(f"⚡ Initialized {self.max_workers * 2} thread workers")
        
        # Set start time
        self.performance_stats['start_time'] = time.time()
        
        # Start web dashboard
        config = uvicorn.Config(
            self.web_app,
            host=self.web_host,
            port=self.web_port,
            log_level="info",
            access_log=False
        )
        server = uvicorn.Server(config)
        
        logger.info(f"🌐 Starting web dashboard on {self.web_host}:{self.web_port}")
        
        # Run both MCP server and web dashboard
        try:
            # Start web server in background
            anyio.lowlevel.spawn_system_task(server.serve)
            
            # Start MCP server
            from mcp.server.stdio import stdio_server
            
            async with stdio_server() as (read_stream, write_stream):
                await self.mcp_server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="ipfs-kit-multiprocess",
                        server_version="2.0.0",
                        capabilities=self.mcp_server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
            
        except Exception as e:
            logger.error(f"❌ Error running MCP server: {e}")
            return False
        
        return True
    
    async def stop(self):
        """Stop the multi-processing MCP server."""
        logger.info("🛑 Stopping Multi-Processing MCP Server...")
        
        # Close WebSocket connections
        for websocket in self.websocket_connections:
            try:
                await websocket.close()
            except:
                pass
        
        # Shutdown process pools
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        
        logger.info("✅ Multi-processing MCP server stopped")


async def main():
    """Main entry point for multi-processing MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Processing IPFS Kit MCP Server")
    parser.add_argument("--daemon-url", default="http://127.0.0.1:9999", help="Daemon URL")
    parser.add_argument("--web-host", default="127.0.0.1", help="Web dashboard host")
    parser.add_argument("--web-port", type=int, default=8080, help="Web dashboard port")
    parser.add_argument("--workers", type=int, help="Number of worker processes")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start MCP server
    mcp_server = MultiProcessMCPServer(
        daemon_url=args.daemon_url,
        web_host=args.web_host,
        web_port=args.web_port,
        max_workers=args.workers
    )
    
    print("=" * 80)
    print("⚡ MULTI-PROCESSING IPFS KIT MCP SERVER")
    print("=" * 80)
    print(f"🌐 Dashboard: http://{args.web_host}:{args.web_port}")
    print(f"🔗 Daemon: {args.daemon_url}")
    print(f"⚡ Workers: {mcp_server.max_workers}")
    print(f"🖥️ CPU Cores: {mp.cpu_count()}")
    print(f"🔍 Debug: {args.debug}")
    print("=" * 80)
    print("🚀 Starting high-performance MCP server...")
    
    try:
        await mcp_server.start()
    except KeyboardInterrupt:
        print("\n🛑 MCP server interrupted by user")
        await mcp_server.stop()
    except Exception as e:
        print(f"❌ MCP server error: {e}")
        await mcp_server.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Set multiprocessing start method
    mp.set_start_method('spawn', force=True)
    anyio.run(main)

#!/usr/bin/env python3
"""
Enhanced MCP-Integrated Dashboard with Full Feature Set

This comprehensive dashboard integrates with the refactored MCP server to provide
complete monitoring and control capabilities for the entire IPFS Kit ecosystem.

Features:
- Real-time MCP server monitoring with atomic operations
- Backend health monitoring and management
- Peer management and connectivity
- Pin management with conflict-free operations
- Service health monitoring (IPFS, Lotus, Cluster, Lassie)
- Configuration widgets and management
- Performance analytics and metrics
- Log viewing and analysis
- ~/.ipfs_kit/ data visualization
- WebSocket real-time updates
"""

import asyncio
import json
import logging
import time
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union
import aiohttp
import pandas as pd
import subprocess

# Web framework imports
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)


class MCPIntegratedDashboard:
    """
    Enhanced dashboard with full MCP server integration.
    
    This dashboard provides:
    - MCP server monitoring and control
    - Real-time ~/.ipfs_kit/ data visualization
    - Atomic operations interface
    - Backend and pin management
    - Daemon coordination monitoring
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the enhanced dashboard."""
        self.config = config or self._default_config()
        self.app = FastAPI(
            title="IPFS Kit Enhanced Dashboard",
            description="Comprehensive monitoring and control dashboard with MCP integration",
            version="2.0.0"
        )
        
        # MCP integration
        self.mcp_server_url = self.config.get('mcp_server_url', 'http://127.0.0.1:8004')
        self.data_dir = Path(self.config.get('data_dir', '~/.ipfs_kit')).expanduser()
        
        # Dashboard state
        self.is_running = False
        self.websocket_clients: Set[WebSocket] = set()
        self.update_task = None
        self.cached_data = {}
        self.last_update = None
        
        self._setup_routes()
        self._setup_middleware()
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'host': '127.0.0.1',
            'port': 8080,
            'mcp_server_url': 'http://127.0.0.1:8004',
            'data_dir': '~/.ipfs_kit',
            'update_interval': 5,  # seconds
            'debug': False
        }
    
    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Main dashboard page."""
            return await self._render_dashboard()
        
        @self.app.get("/api/status")
        async def get_status():
            """Get overall system status."""
            return await self._get_system_status()
        
        @self.app.get("/api/mcp")
        async def get_mcp_status():
            """Get MCP server status and metrics."""
            return await self._get_mcp_status()
        
        @self.app.get("/api/backends")
        async def get_backends():
            """Get backend information from ~/.ipfs_kit/."""
            return await self._get_backend_data()
        
        @self.app.get("/api/pins")
        async def get_pins():
            """Get pin information from ~/.ipfs_kit/."""
            return await self._get_pin_data()
        
        @self.app.get("/api/daemon")
        async def get_daemon_status():
            """Get daemon status."""
            return await self._get_daemon_status()
        
        @self.app.post("/api/daemon/{action}")
        async def daemon_control(action: str):
            """Control daemon operations."""
            return await self._execute_daemon_command(action)
        
        @self.app.get("/api/services")
        async def get_services():
            """Get service status for IPFS, Lotus, Cluster, Lassie."""
            return await self._get_services_data()
        
        @self.app.get("/api/services/{service}/status")
        async def get_service_status(service: str):
            """Get detailed service status."""
            return await self._get_service_status(service)
        
        @self.app.post("/api/services/{service}/{action}")
        async def service_control(service: str, action: str):
            """Control service operations."""
            return await self._execute_service_command(service, action)
        
        @self.app.get("/api/peers")
        async def get_peers():
            """Get peer information and connectivity."""
            return await self._get_peers_data()
        
        @self.app.post("/api/peers/connect")
        async def connect_peer(peer_data: dict):
            """Connect to a new peer."""
            return await self._connect_peer(peer_data)
        
        @self.app.delete("/api/peers/{peer_id}")
        async def disconnect_peer(peer_id: str):
            """Disconnect from a peer."""
            return await self._disconnect_peer(peer_id)
        
        @self.app.get("/api/logs")
        async def get_logs(component: str = "all", level: str = "info", limit: int = 100):
            """Get system logs."""
            return await self._get_logs_data(component, level, limit)
        
        @self.app.get("/api/logs/stream")
        async def stream_logs():
            """Stream logs in real-time."""
            return StreamingResponse(self._stream_logs(), media_type="text/plain")
        
        @self.app.get("/api/metrics/detailed")
        async def get_detailed_metrics():
            """Get detailed performance metrics."""
            return await self._get_detailed_metrics()
        
        @self.app.get("/api/system")
        async def get_system_metrics():
            """Get system resource metrics."""
            return await self._get_system_metrics()
        
        @self.app.post("/api/config/update")
        async def update_config(config_data: dict):
            """Update configuration settings."""
            return await self._update_config(config_data)
        
        @self.app.get("/api/buckets")
        async def get_buckets():
            """Get bucket information."""
            return await self._get_buckets_data()
        
        @self.app.get("/api/buckets/{bucket_name}")
        async def get_bucket_details(bucket_name: str):
            """Get detailed bucket information."""
            return await self._get_bucket_details(bucket_name)
        
        @self.app.get("/api/config")
        async def get_config():
            """Get configuration information."""
            return await self._get_config_data()
        
        @self.app.post("/api/mcp/command")
        async def execute_mcp_command(request: Request):
            """Execute MCP command."""
            data = await request.json()
            return await self._execute_mcp_command(data)
        
        @self.app.get("/api/wal")
        async def get_wal_data():
            """Get WAL information."""
            return await self._get_wal_data()
        
        @self.app.get("/api/program_state")
        async def get_program_state_data():
            """Get program state information."""
            return await self._get_program_state_data()
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self._handle_websocket(websocket)
    
    async def _render_dashboard(self) -> str:
        """Render the main dashboard HTML."""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit Enhanced Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .status-card {{ 
            transition: all 0.3s ease;
            border-left: 4px solid #e5e7eb;
        }}
        .status-running {{ border-left-color: #10b981; }}
        .status-warning {{ border-left-color: #f59e0b; }}
        .status-error {{ border-left-color: #ef4444; }}
        .metric-value {{ 
            font-size: 2rem; 
            font-weight: bold; 
        }}
        .realtime {{ 
            animation: pulse 2s infinite; 
        }}
    </style>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <header class="mb-8">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">IPFS Kit Enhanced Dashboard</h1>
            <p class="text-gray-600">Comprehensive monitoring with MCP server integration</p>
            <div class="flex space-x-4 mt-4">
                <div class="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm">
                    <span class="realtime">●</span> Real-time monitoring
                </div>
                <div class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
                    MCP Server Connected
                </div>
                <div class="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm">
                    Atomic Operations Ready
                </div>
            </div>
        </header>

        <!-- System Status Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div id="mcp-status-card" class="bg-white p-6 rounded-lg shadow status-card">
                <h3 class="text-lg font-semibold text-gray-700 mb-2">MCP Server</h3>
                <div id="mcp-status" class="metric-value text-gray-500">Loading...</div>
                <p class="text-sm text-gray-500 mt-2">Health & Performance</p>
            </div>
            
            <div id="daemon-status-card" class="bg-white p-6 rounded-lg shadow status-card">
                <h3 class="text-lg font-semibold text-gray-700 mb-2">Daemon</h3>
                <div id="daemon-status" class="metric-value text-gray-500">Loading...</div>
                <p class="text-sm text-gray-500 mt-2">Orchestration Status</p>
            </div>
            
            <div id="backends-card" class="bg-white p-6 rounded-lg shadow status-card">
                <h3 class="text-lg font-semibold text-gray-700 mb-2">Backends</h3>
                <div id="backend-count" class="metric-value text-blue-600">0</div>
                <p class="text-sm text-gray-500 mt-2">Storage Backends</p>
            </div>
            
            <div id="pins-card" class="bg-white p-6 rounded-lg shadow status-card">
                <h3 class="text-lg font-semibold text-gray-700 mb-2">Pins</h3>
                <div id="pin-count" class="metric-value text-green-600">0</div>
                <p class="text-sm text-gray-500 mt-2">Total Pins</p>
            </div>
        </div>

        <!-- Main Content Tabs -->
        <div class="bg-white rounded-lg shadow">
            <div class="border-b border-gray-200">
                <nav class="-mb-px flex space-x-8">
                    <button onclick="showTab('overview')" class="tab-button active border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Overview
                    </button>
                    <button onclick="showTab('mcp')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        MCP Operations
                    </button>
                    <button onclick="showTab('backends')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Backend Management
                    </button>
                    <button onclick="showTab('pins')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Pin Management
                    </button>
                    <button onclick="showTab('services')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Services
                    </button>
                    <button onclick="showTab('peers')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Peers
                    </button>
                    <button onclick="showTab('metrics')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Metrics
                    </button>
                    <button onclick="showTab('logs')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Logs
                    </button>
                    <button onclick="showTab('config')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Configuration
                    </button>
                    <button onclick="showTab('wal')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        WAL
                    </button>
                    <button onclick="showTab('buckets')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Buckets
                    </button>
                    <button onclick="showTab('program_state')" class="tab-button border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
                        Program State
                    </button>
                </nav>
            </div>

            <!-- Tab Content -->
            <div class="p-6">
                <!-- Overview Tab -->
                <div id="overview-tab" class="tab-content">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <h3 class="text-lg font-semibold mb-4">System Architecture</h3>
                            <div class="bg-gray-50 p-4 rounded-lg">
                                <div class="space-y-3">
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm font-medium">MCP Server (Atomic Ops)</span>
                                        <span id="mcp-indicator" class="w-3 h-3 rounded-full bg-gray-400"></span>
                                    </div>
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm font-medium">Daemon (Orchestration)</span>
                                        <span id="daemon-indicator" class="w-3 h-3 rounded-full bg-gray-400"></span>
                                    </div>
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm font-medium">Data Directory</span>
                                        <span class="text-sm text-gray-600">~/.ipfs_kit/</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Recent Activity</h3>
                            <div id="activity-log" class="bg-gray-50 p-4 rounded-lg h-40 overflow-y-auto">
                                <!-- Activity items will be populated via JavaScript -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- MCP Operations Tab -->
                <div id="mcp-tab" class="tab-content hidden">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <h3 class="text-lg font-semibold mb-4">MCP Server Control</h3>
                            <div class="space-y-4">
                                <button onclick="restartMCPServer()" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                    Restart MCP Server
                                </button>
                                <button onclick="syncPins()" class="w-full bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                    Force Pin Sync
                                </button>
                                <button onclick="backupMetadata()" class="w-full bg-yellow-500 hover:bg-yellow-600 text-white font-semibold py-2 px-4 rounded">
                                    Backup Metadata
                                </button>
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="text-lg font-semibold mb-4">MCP Server Metrics</h3>
                            <div id="mcp-metrics" class="space-y-3">
                                <!-- MCP metrics will be populated via JavaScript -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Backends Tab -->
                <div id="backends-tab" class="tab-content hidden">
                    <div class="mb-4">
                        <h3 class="text-lg font-semibold">Storage Backends</h3>
                        <p class="text-gray-600">Manage and monitor storage backends</p>
                    </div>
                    <div id="backends-table" class="overflow-x-auto">
                        <!-- Backends table will be populated via JavaScript -->
                    </div>
                </div>

                <!-- Pins Tab -->
                <div id="pins-tab" class="tab-content hidden">
                    <div class="mb-4">
                        <h3 class="text-lg font-semibold">Pin Management</h3>
                        <p class="text-gray-600">Monitor and manage content pins across backends</p>
                    </div>
                    <div id="pins-table" class="overflow-x-auto">
                        <!-- Pins table will be populated via JavaScript -->
                    </div>
                </div>

                <!-- Services Tab -->
                <div id="services-tab" class="tab-content hidden">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Service Status</h3>
                            <div id="services-status" class="space-y-4">
                                <!-- Services status will be populated via JavaScript -->
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Service Control</h3>
                            <div class="space-y-3">
                                <button onclick="controlService('ipfs', 'start')" class="w-full bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                    Start IPFS
                                </button>
                                <button onclick="controlService('ipfs', 'stop')" class="w-full bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded">
                                    Stop IPFS
                                </button>
                                <button onclick="controlService('cluster', 'restart')" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                    Restart Cluster
                                </button>
                                <button onclick="refreshServices()" class="w-full bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded">
                                    Refresh Status
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Peers Tab -->
                <div id="peers-tab" class="tab-content hidden">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Connected Peers</h3>
                            <div id="peers-list" class="bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
                                <!-- Peers list will be populated via JavaScript -->
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Peer Management</h3>
                            <div class="space-y-3">
                                <div>
                                    <input type="text" id="peer-address" placeholder="Enter peer multiaddr" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <button onclick="connectPeer()" class="w-full bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                    Connect Peer
                                </button>
                                <button onclick="refreshPeers()" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                    Refresh Peers
                                </button>
                                <div id="peer-stats" class="mt-4 bg-gray-50 p-3 rounded">
                                    <!-- Peer statistics will be populated via JavaScript -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Metrics Tab -->
                <div id="metrics-tab" class="tab-content hidden">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <h3 class="text-lg font-semibold mb-4">System Metrics</h3>
                            <div class="space-y-4">
                                <div class="bg-gray-50 p-4 rounded-lg">
                                    <h4 class="font-semibold mb-2">CPU Usage</h4>
                                    <canvas id="cpu-chart" width="400" height="200"></canvas>
                                </div>
                                <div class="bg-gray-50 p-4 rounded-lg">
                                    <h4 class="font-semibold mb-2">Memory Usage</h4>
                                    <canvas id="memory-chart" width="400" height="200"></canvas>
                                </div>
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Performance Metrics</h3>
                            <div id="performance-metrics" class="space-y-3">
                                <!-- Performance metrics will be populated via JavaScript -->
                            </div>
                            <div class="mt-6">
                                <h4 class="font-semibold mb-2">Network I/O</h4>
                                <canvas id="network-chart" width="400" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Logs Tab -->
                <div id="logs-tab" class="tab-content hidden">
                    <div class="grid grid-cols-1 gap-6">
                        <div>
                            <div class="flex justify-between items-center mb-4">
                                <h3 class="text-lg font-semibold">System Logs</h3>
                                <div class="space-x-2">
                                    <select id="log-level" class="px-3 py-1 border border-gray-300 rounded">
                                        <option value="all">All Levels</option>
                                        <option value="error">Error</option>
                                        <option value="warning">Warning</option>
                                        <option value="info">Info</option>
                                        <option value="debug">Debug</option>
                                    </select>
                                    <button onclick="clearLogs()" class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded">
                                        Clear
                                    </button>
                                    <button onclick="refreshLogs()" class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded">
                                        Refresh
                                    </button>
                                </div>
                            </div>
                            <div id="logs-container" class="bg-black text-green-400 p-4 rounded-lg h-96 overflow-y-auto font-mono text-sm">
                                <!-- Logs will be populated via JavaScript -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Configuration Tab -->
                <div id="config-tab" class="tab-content hidden">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <h3 class="text-lg font-semibold mb-4">MCP Configuration</h3>
                            <div id="mcp-config" class="bg-gray-50 p-4 rounded-lg">
                                <!-- MCP config will be populated via JavaScript -->
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="text-lg font-semibold mb-4">System Configuration</h3>
                            <div id="system-config" class="bg-gray-50 p-4 rounded-lg">
                                <!-- System config will be populated via JavaScript -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- WAL Tab -->
                <div id="wal-tab" class="tab-content hidden">
                    <h3 class="text-lg font-semibold">Write-Ahead Log</h3>
                    <div id="wal-info"></div>
                </div>

                <!-- Buckets Tab -->
                <div id="buckets-tab" class="tab-content hidden">
                    <h3 class="text-lg font-semibold">Buckets</h3>
                    <div id="buckets-info"></div>
                </div>

                <!-- Program State Tab -->
                <div id="program-state-tab" class="tab-content hidden">
                    <h3 class="text-lg font-semibold">Program State</h3>
                    <div id="program-state-info"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- JavaScript -->
    <script>
        // Global state
        let ws = null;
        let activeTab = 'overview';

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {{
            initWebSocket();
            loadInitialData();
            setInterval(updateData, 5000); // Update every 5 seconds
        }});

        // WebSocket connection
        function initWebSocket() {{
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${{protocol}}//${{window.location.host}}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {{
                console.log('WebSocket connected');
                addActivity('WebSocket connection established', 'success');
            }};
            
            ws.onmessage = function(event) {{
                const data = JSON.parse(event.data);
                handleRealtimeUpdate(data);
            }};
            
            ws.onclose = function() {{
                console.log('WebSocket disconnected');
                addActivity('WebSocket connection lost', 'error');
                // Reconnect after 5 seconds
                setTimeout(initWebSocket, 5000);
            }};
        }}

        // Load initial data
        async function loadInitialData() {{
            await Promise.all([
                updateSystemStatus(),
                updateMCPStatus(),
                updateBackends(),
                updatePins(),
                updateConfig()
            ]);
        }}

        // Update data periodically
        async function updateData() {{
            await Promise.all([
                updateSystemStatus(),
                updateMCPStatus()
            ]);
        }}

        // System status
        async function updateSystemStatus() {{
            try {{
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update status cards
                updateStatusCard('mcp-status-card', 'mcp-status', data.mcp);
                updateStatusCard('daemon-status-card', 'daemon-status', data.daemon);
                
                document.getElementById('backend-count').textContent = data.backend_count || 0;
                document.getElementById('pin-count').textContent = data.pin_count || 0;
                
                // Update indicators
                updateIndicator('mcp-indicator', data.mcp?.status === 'running');
                updateIndicator('daemon-indicator', data.daemon?.is_running);
                
            }} catch (error) {{
                console.error('Failed to update system status:', error);
                addActivity('Failed to update system status', 'error');
            }}
        }}

        // MCP status
        async function updateMCPStatus() {{
            try {{
                const response = await fetch('/api/mcp');
                const data = await response.json();
                
                const metricsDiv = document.getElementById('mcp-metrics');
                if (metricsDiv) {{
                    metricsDiv.innerHTML = `
                        <div class="bg-white p-3 rounded border">
                            <div class="text-sm font-medium text-gray-700">Uptime</div>
                            <div class="text-lg font-semibold">${{data.uptime || 'N/A'}}</div>
                        </div>
                        <div class="bg-white p-3 rounded border">
                            <div class="text-sm font-medium text-gray-700">Requests</div>
                            <div class="text-lg font-semibold">${{data.requests || 0}}</div>
                        </div>
                        <div class="bg-white p-3 rounded border">
                            <div class="text-sm font-medium text-gray-700">Last Health Check</div>
                            <div class="text-lg font-semibold">${{data.last_check || 'N/A'}}</div>
                        </div>
                    `;
                }}
                
            }} catch (error) {{
                console.error('Failed to update MCP status:', error);
            }}
        }}

        // Update backends
        async function updateBackends() {{
            try {{
                const response = await fetch('/api/backends');
                const data = await response.json();
                
                const table = document.getElementById('backends-table');
                if (table && data.backends) {{
                    table.innerHTML = `
                        <table class="min-w-full bg-white border border-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Health</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Pins</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Check</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200">
                                ${{data.backends.map(backend => `
                                    <tr>
                                        <td class="px-6 py-4 whitespace-nowrap font-medium">${{backend.backend_name}}</td>
                                        <td class="px-6 py-4 whitespace-nowrap">${{backend.backend_type}}</td>
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full ${{
                                                backend.health_status === 'healthy' ? 'bg-green-100 text-green-800' : 
                                                'bg-red-100 text-red-800'
                                            }}">
                                                ${{backend.health_status}}
                                            </span>
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap">${{backend.pin_count || 0}}</td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${{backend.last_health_check || 'N/A'}}</td>
                                    </tr>
                                `).join('')}}
                            </tbody>
                        </table>
                    `;
                }}
                
            }} catch (error) {{
                console.error('Failed to update backends:', error);
            }}
        }}

        // Update pins
        async function updatePins() {{
            try {{
                const response = await fetch('/api/pins');
                const data = await response.json();
                
                const table = document.getElementById('pins-table');
                if (table && data.pins) {{
                    table.innerHTML = `
                        <table class="min-w-full bg-white border border-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">CID</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Backend</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200">
                                ${{data.pins.slice(0, 10).map(pin => `
                                    <tr>
                                        <td class="px-6 py-4 whitespace-nowrap font-mono text-sm">${{pin.cid.substring(0, 20)}}...</td>
                                        <td class="px-6 py-4 whitespace-nowrap">${{pin.backend_name}}</td>
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full ${{
                                                pin.pin_status === 'pinned' ? 'bg-green-100 text-green-800' : 
                                                'bg-yellow-100 text-yellow-800'
                                            }}">
                                                ${{pin.pin_status}}
                                            </span>
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap">${{pin.size || 'N/A'}}</td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${{pin.created_at || 'N/A'}}</td>
                                    </tr>
                                `).join('')}}
                            </tbody>
                        </table>
                    `;
                }}
                
            }} catch (error) {{
                console.error('Failed to update pins:', error);
            }}
        }}

        // Update configuration
        async function updateConfig() {{
            try {{
                const response = await fetch('/api/config');
                const data = await response.json();
                
                const mcpConfig = document.getElementById('mcp-config');
                const systemConfig = document.getElementById('system-config');
                
                if (mcpConfig && data.mcp) {{
                    mcpConfig.innerHTML = `
                        <div class="space-y-2">
                            <div><strong>Host:</strong> ${{data.mcp.host}}</div>
                            <div><strong>Port:</strong> ${{data.mcp.port}}</div>
                            <div><strong>Transport:</strong> ${{data.mcp.transport}}</div>
                            <div><strong>Atomic Operations:</strong> ${{data.mcp.atomic_operations_only ? 'Yes' : 'No'}}</div>
                        </div>
                    `;
                }}
                
                if (systemConfig && data.system) {{
                    systemConfig.innerHTML = `
                        <div class="space-y-2">
                            <div><strong>Data Directory:</strong> ${{data.system.data_dir}}</div>
                            <div><strong>Debug Mode:</strong> ${{data.system.debug ? 'Yes' : 'No'}}</div>
                            <div><strong>Cache TTL:</strong> ${{data.system.cache_ttl_seconds}}s</div>
                        </div>
                    `;
                }}
                
            }} catch (error) {{
                console.error('Failed to update config:', error);
            }}
        }}

        // Helper functions
        function updateStatusCard(cardId, statusId, data) {{
            const card = document.getElementById(cardId);
            const status = document.getElementById(statusId);
            
            if (!card || !status || !data) return;
            
            card.className = `bg-white p-6 rounded-lg shadow status-card ${{
                data.status === 'running' || data.is_running ? 'status-running' :
                data.status === 'warning' ? 'status-warning' : 'status-error'
            }}`;
            
            status.textContent = data.status || (data.is_running ? 'Running' : 'Stopped');
        }}

        function updateIndicator(id, isRunning) {{
            const indicator = document.getElementById(id);
            if (indicator) {{
                indicator.className = `w-3 h-3 rounded-full ${{isRunning ? 'bg-green-400' : 'bg-red-400'}}`;
            }}
        }}

        function addActivity(message, type = 'info') {{
            const log = document.getElementById('activity-log');
            if (log) {{
                const time = new Date().toLocaleTimeString();
                const colorClass = type === 'success' ? 'text-green-600' : 
                                 type === 'error' ? 'text-red-600' : 'text-blue-600';
                
                const entry = document.createElement('div');
                entry.className = 'text-sm mb-2';
                entry.innerHTML = `<span class="text-gray-500">${{time}}</span> <span class="${{colorClass}}">${{message}}</span>`;
                
                log.insertBefore(entry, log.firstChild);
                
                // Keep only last 10 entries
                while (log.children.length > 10) {{
                    log.removeChild(log.lastChild);
                }}
            }}
        }}

        // Tab functionality
        function showTab(tabName) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.add('hidden');
            }});
            
            // Remove active class from all buttons
            document.querySelectorAll('.tab-button').forEach(btn => {{
                btn.classList.remove('active', 'border-blue-500', 'text-blue-600');
                btn.classList.add('border-transparent', 'text-gray-500');
            }});
            
            // Show selected tab
            const selectedTab = document.getElementById(tabName + '-tab');
            if (selectedTab) {{
                selectedTab.classList.remove('hidden');
            }}
            
            // Mark button as active
            const selectedButton = event?.target;
            if (selectedButton) {{
                selectedButton.classList.add('active', 'border-blue-500', 'text-blue-600');
                selectedButton.classList.remove('border-transparent', 'text-gray-500');
            }}
            
            activeTab = tabName;
            
            // Load tab-specific data
            if (tabName === 'backends') {{
                updateBackends();
            }} else if (tabName === 'pins') {{
                updatePins();
            }} else if (tabName === 'config') {{
                updateConfig();
            }}
        }}

        // MCP Operations
        async function restartMCPServer() {{
            try {{
                const response = await fetch('/api/mcp/command', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ command: 'restart' }})
                }});
                
                const result = await response.json();
                addActivity('MCP server restart initiated', 'success');
                
            }} catch (error) {{
                console.error('Failed to restart MCP server:', error);
                addActivity('Failed to restart MCP server', 'error');
            }}
        }}

        async function syncPins() {{
            try {{
                const response = await fetch('/api/mcp/command', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ command: 'sync_pins' }})
                }});
                
                const result = await response.json();
                addActivity('Pin synchronization initiated', 'success');
                
            }} catch (error) {{
                console.error('Failed to sync pins:', error);
                addActivity('Failed to sync pins', 'error');
            }}
        }}

        async function backupMetadata() {{
            try {{
                const response = await fetch('/api/mcp/command', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ command: 'backup_metadata' }})
                }});
                
                const result = await response.json();
                addActivity('Metadata backup initiated', 'success');
                
            }} catch (error) {{
                console.error('Failed to backup metadata:', error);
                addActivity('Failed to backup metadata', 'error');
            }}
        }}

        // Real-time updates via WebSocket
        function handleRealtimeUpdate(data) {{
            if (data.type === 'status_update') {{
                updateSystemStatus();
            }} else if (data.type === 'mcp_update') {{
                updateMCPStatus();
            }} else if (data.type === 'activity') {{
                addActivity(data.message, data.level);
            }}
        }}

        // Services management functions
        async function refreshServices() {{
            try {{
                const response = await fetch('/api/services');
                const data = await response.json();
                
                const servicesContainer = document.getElementById('services-status');
                servicesContainer.innerHTML = '';
                
                for (const [name, info] of Object.entries(data.services)) {{
                    const statusClass = info.status === 'running' ? 'bg-green-100 text-green-800' : 
                                       info.status === 'stopped' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800';
                    
                    servicesContainer.innerHTML += `
                        <div class="flex justify-between items-center p-3 border rounded">
                            <div>
                                <h4 class="font-semibold">${{name}}</h4>
                                <p class="text-sm text-gray-600">PID: ${{info.pid || 'N/A'}}</p>
                            </div>
                            <span class="px-2 py-1 rounded text-xs ${{statusClass}}">${{info.status.toUpperCase()}}</span>
                        </div>
                    `;
                }}
                
            }} catch (error) {{
                console.error('Failed to refresh services:', error);
                addActivity('Failed to refresh services', 'error');
            }}
        }}

        async function controlService(service, action) {{
            try {{
                const response = await fetch('/api/services/control', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ service, action }})
                }});
                
                const result = await response.json();
                addActivity(`Service ${{service}} ${{action}} completed`, 'success');
                setTimeout(refreshServices, 1000); // Refresh after 1 second
                
            }} catch (error) {{
                console.error('Failed to control service:', error);
                addActivity(`Failed to ${{action}} ${{service}}`, 'error');
            }}
        }}

        // Peers management functions
        async function refreshPeers() {{
            try {{
                const response = await fetch('/api/peers');
                const data = await response.json();
                
                const peersList = document.getElementById('peers-list');
                const peerStats = document.getElementById('peer-stats');
                
                peersList.innerHTML = '';
                data.peers.forEach(peer => {{
                    peersList.innerHTML += `
                        <div class="flex justify-between items-center p-2 border-b">
                            <div class="text-sm">
                                <div class="font-mono">${{peer.id.substring(0, 16)}}...</div>
                                <div class="text-gray-600">${{peer.addr}}</div>
                            </div>
                            <button onclick="disconnectPeer('${{peer.id}}')" class="text-red-600 text-xs hover:text-red-800">
                                Disconnect
                            </button>
                        </div>
                    `;
                }});
                
                peerStats.innerHTML = `
                    <div class="text-sm">
                        <div>Total Peers: ${{data.total}}</div>
                        <div>Connected: ${{data.connected}}</div>
                        <div>Last Updated: ${{new Date().toLocaleTimeString()}}</div>
                    </div>
                `;
                
            }} catch (error) {{
                console.error('Failed to refresh peers:', error);
                addActivity('Failed to refresh peers', 'error');
            }}
        }}

        async function connectPeer() {{
            const address = document.getElementById('peer-address').value.trim();
            if (!address) {{
                addActivity('Please enter a peer address', 'warning');
                return;
            }}

            try {{
                const response = await fetch('/api/peers/connect', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ address }})
                }});
                
                const result = await response.json();
                addActivity(`Connected to peer: ${{address.substring(0, 32)}}...`, 'success');
                document.getElementById('peer-address').value = '';
                setTimeout(refreshPeers, 1000);
                
            }} catch (error) {{
                console.error('Failed to connect peer:', error);
                addActivity('Failed to connect peer', 'error');
            }}
        }}

        async function disconnectPeer(peerId) {{
            try {{
                const response = await fetch('/api/peers/disconnect', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ peer_id: peerId }})
                }});
                
                const result = await response.json();
                addActivity(`Disconnected peer: ${{peerId.substring(0, 16)}}...`, 'success');
                setTimeout(refreshPeers, 1000);
                
            }} catch (error) {{
                console.error('Failed to disconnect peer:', error);
                addActivity('Failed to disconnect peer', 'error');
            }}
        }}

        // Metrics and charts
        let cpuChart, memoryChart, networkChart;
        
        async function refreshMetrics() {{
            try {{
                const response = await fetch('/api/metrics/detailed');
                const data = await response.json();
                
                // Update performance metrics display
                const metricsContainer = document.getElementById('performance-metrics');
                metricsContainer.innerHTML = `
                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-gray-50 p-3 rounded">
                            <h5 class="font-semibold">CPU</h5>
                            <p class="text-lg">${{data.cpu.percent}}%</p>
                        </div>
                        <div class="bg-gray-50 p-3 rounded">
                            <h5 class="font-semibold">Memory</h5>
                            <p class="text-lg">${{(data.memory.percent).toFixed(1)}}%</p>
                        </div>
                        <div class="bg-gray-50 p-3 rounded">
                            <h5 class="font-semibold">Disk</h5>
                            <p class="text-lg">${{(data.disk.percent).toFixed(1)}}%</p>
                        </div>
                        <div class="bg-gray-50 p-3 rounded">
                            <h5 class="font-semibold">Network</h5>
                            <p class="text-sm">↑ ${{formatBytes(data.network.bytes_sent)}}</p>
                            <p class="text-sm">↓ ${{formatBytes(data.network.bytes_recv)}}</p>
                        </div>
                    </div>
                `;
                
                // Update charts if they exist
                updateCharts(data);
                
            }} catch (error) {{
                console.error('Failed to refresh metrics:', error);
                addActivity('Failed to refresh metrics', 'error');
            }}
        }}

        function updateCharts(data) {{
            // Initialize charts if not done yet
            if (!cpuChart) {{
                const cpuCtx = document.getElementById('cpu-chart').getContext('2d');
                cpuChart = new Chart(cpuCtx, {{
                    type: 'line',
                    data: {{
                        labels: [],
                        datasets: [{{
                            label: 'CPU %',
                            data: [],
                            borderColor: 'rgb(59, 130, 246)',
                            tension: 0.1
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        scales: {{
                            y: {{ beginAtZero: true, max: 100 }}
                        }}
                    }}
                }});
            }}

            // Update chart data (keep last 20 points)
            const now = new Date().toLocaleTimeString();
            cpuChart.data.labels.push(now);
            cpuChart.data.datasets[0].data.push(data.cpu.percent);
            
            if (cpuChart.data.labels.length > 20) {{
                cpuChart.data.labels.shift();
                cpuChart.data.datasets[0].data.shift();
            }}
            
            cpuChart.update();
        }}

        function formatBytes(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }}

        // Logs management
        async function refreshLogs() {{
            try {{
                const level = document.getElementById('log-level').value;
                const response = await fetch(`/api/logs?level=${{level}}&limit=100`);
                const data = await response.json();
                
                const logsContainer = document.getElementById('logs-container');
                logsContainer.innerHTML = '';
                
                data.logs.forEach(log => {{
                    const logClass = log.level === 'error' ? 'text-red-400' : 
                                    log.level === 'warning' ? 'text-yellow-400' : 'text-green-400';
                    logsContainer.innerHTML += `<div class="${{logClass}}">${{log.timestamp}} [${{log.level.toUpperCase()}}] ${{log.message}}</div>`;
                }});
                
                logsContainer.scrollTop = logsContainer.scrollHeight;
                
            }} catch (error) {{
                console.error('Failed to refresh logs:', error);
                addActivity('Failed to refresh logs', 'error');
            }}
        }}

        function clearLogs() {{
            document.getElementById('logs-container').innerHTML = '';
            addActivity('Logs cleared', 'info');
        }}

        // Tab-specific refresh functions
        function refreshCurrentTab() {{
            switch(activeTab) {{
                case 'services':
                    refreshServices();
                    break;
                case 'peers':
                    refreshPeers();
                    break;
                case 'metrics':
                    refreshMetrics();
                    break;
                case 'logs':
                    refreshLogs();
                    break;
            }}
        }}

        // Initialize new features when tabs are shown
        const originalShowTab = showTab;
        showTab = function(tabName) {{
            originalShowTab.call(this, tabName);
            
            // Refresh data when switching to specific tabs
            setTimeout(() => {{
                if (tabName === 'services') refreshServices();
                else if (tabName === 'peers') refreshPeers();
                else if (tabName === 'metrics') refreshMetrics();
                else if (tabName === 'logs') refreshLogs();
                else if (tabName === 'wal') updateWalData();
                else if (tabName === 'buckets') updateBucketsData();
                else if (tabName === 'program_state') updateProgramStateData();
            }}, 100);
                else if (tabName === 'overview') loadInitialData();
            }}, 100);
        }};

        async function updateWalData() {{
            try {{
                const response = await fetch('/api/wal');
                const data = await response.json();
                const walInfo = document.getElementById('wal-info');
                if (walInfo) {{
                    walInfo.innerHTML = `
                        <div><strong>Status:</strong> ${{data.wal_status}}</div>
                        <div><strong>Files:</strong> ${{data.file_count}}</div>
                        <ul>
                            ${{data.files.map(f => `<li>${{f}}</li>`).join('')}}
                        </ul>
                    `;
                }}
            }} catch (error) {{
                console.error('Failed to update WAL data:', error);
                addActivity('Failed to update WAL data', 'error');
            }}
        }}

        async function updateBucketsData() {{
            try {{
                const response = await fetch('/api/buckets');
                const data = await response.json();
                const bucketsInfo = document.getElementById('buckets-info');
                if (bucketsInfo) {{
                    bucketsInfo.innerHTML = `
                        <div><strong>Total Buckets:</strong> ${{data.total}}</div>
                        <ul>
                            ${{data.buckets.map(b => `<li>${{b.name}} (${{b.file_count}} files, ${{formatBytes(b.total_size)}})</li>`).join('')}}
                        </ul>
                    `;
                }}
            }} catch (error) {{
                console.error('Failed to update buckets data:', error);
                addActivity('Failed to update buckets data', 'error');
            }}
        }}
    </script>
</body>
</html>
        """
        return html
    
    async def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        try:
            # Get MCP server status
            mcp_status = await self._check_mcp_health()
            
            # Get daemon status from files
            daemon_status = await self._read_daemon_status()
            
            # Get backend and pin counts
            backend_data = await self._read_backend_data()
            pin_data = await self._read_pin_data()
            
            return {
                'mcp': mcp_status,
                'daemon': daemon_status,
                'backend_count': len(backend_data.get('backends', [])),
                'pin_count': len(pin_data.get('pins', [])),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _get_mcp_status(self) -> Dict[str, Any]:
        """Get detailed MCP server status."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_server_url}/health") as response:
                    if response.status == 200:
                        health_data = await response.json()
                        
                        # Get additional status
                        async with session.get(f"{self.mcp_server_url}/status") as status_response:
                            status_data = await status_response.json() if status_response.status == 200 else {}
                        
                        return {
                            'status': 'running',
                            'health': health_data,
                            'details': status_data,
                            'uptime': 'Active',
                            'last_check': datetime.now().strftime('%H:%M:%S'),
                            'timestamp': datetime.now().isoformat()
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': f"HTTP {response.status}",
                            'timestamp': datetime.now().isoformat()
                        }
                        
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _check_mcp_health(self) -> Dict[str, Any]:
        """Check MCP server health."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_server_url}/health", timeout=5) as response:
                    if response.status == 200:
                        return {
                            'status': 'running',
                            'timestamp': datetime.now().isoformat()
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': f"HTTP {response.status}",
                            'timestamp': datetime.now().isoformat()
                        }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _get_services_data(self) -> Dict[str, Any]:
        """Get comprehensive service status data."""
        try:
            services = {
                "ipfs": await self._get_service_status("ipfs"),
                "lotus": await self._get_service_status("lotus"), 
                "cluster": await self._get_service_status("cluster"),
                "lassie": await self._get_service_status("lassie")
            }
            
            # Get overall service health
            healthy_count = sum(1 for service in services.values() 
                              if service.get("status") == "running")
            
            return {
                "services": services,
                "summary": {
                    "total": len(services),
                    "healthy": healthy_count,
                    "unhealthy": len(services) - healthy_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting services data: {e}")
            return {"services": {}, "summary": {"total": 0, "healthy": 0, "unhealthy": 0}, "error": str(e)}
    
    async def _get_service_status(self, service: str) -> Dict[str, Any]:
        """Get detailed status for a specific service."""
        try:
            # Check if service process is running
            result = subprocess.run(['pgrep', '-f', service], capture_output=True, text=True)
            is_running = bool(result.stdout.strip())
            
            status_data = {
                "name": service,
                "status": "running" if is_running else "stopped",
                "pid": result.stdout.strip() if is_running else None,
                "timestamp": datetime.now().isoformat()
            }
            
            if is_running and result.stdout.strip():
                try:
                    pid = int(result.stdout.strip().split('\n')[0])
                    process = psutil.Process(pid)
                    status_data.update({
                        "cpu_percent": process.cpu_percent(),
                        "memory_mb": process.memory_info().rss / 1024 / 1024,
                        "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
                    })
                except (psutil.NoSuchProcess, ValueError):
                    pass
            
            # Try to get service-specific information via MCP
            try:
                mcp_result = await self._execute_mcp_command("service", action="status", args=[service])
                if mcp_result and "result" in mcp_result:
                    status_data.update(mcp_result["result"])
            except Exception:
                pass
            
            return status_data
            
        except Exception as e:
            logger.error(f"Error getting {service} status: {e}")
            return {"name": service, "status": "error", "error": str(e)}
    
    async def _get_peers_data(self) -> Dict[str, Any]:
        """Get peer connectivity information."""
        try:
            # Get peer data via MCP
            result = await self._execute_mcp_command("ipfs", action="swarm", args=["peers"])
            peers_raw = result.get("result", {}).get("peers", [])
            
            peers = []
            for peer in peers_raw:
                peer_info = {
                    "id": peer.get("Peer", ""),
                    "addresses": peer.get("Addr", []),
                    "direction": peer.get("Direction", "unknown"),
                    "latency": peer.get("Latency", "unknown"),
                    "streams": peer.get("Streams", [])
                }
                peers.append(peer_info)
            
            # Get additional connectivity metrics
            try:
                connectivity_result = await self._execute_mcp_command("ipfs", action="diag", args=["net"])
                connectivity = connectivity_result.get("result", {})
            except Exception:
                connectivity = {}
            
            return {
                "peers": peers,
                "total": len(peers),
                "connectivity": connectivity,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting peers data: {e}")
            return {"peers": [], "total": 0, "error": str(e)}
    
    async def _get_logs_data(self, component: str = "all", level: str = "info", limit: int = 100) -> Dict[str, Any]:
        """Get system logs with filtering."""
        try:
            result = await self._execute_mcp_command("log", action="show", params={
                "component": component,
                "level": level,
                "limit": limit
            })
            
            logs = result.get("result", {}).get("logs", [])
            
            return {
                "logs": logs,
                "component": component,
                "level": level,
                "total": len(logs),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting logs data: {e}")
            return {"logs": [], "error": str(e)}
    
    async def _get_detailed_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        try:
            # System metrics
            system_metrics = await self._get_system_metrics()
            
            # MCP server metrics
            mcp_metrics = {}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.mcp_server_url}/metrics") as response:
                        if response.status == 200:
                            mcp_metrics = await response.json()
            except Exception:
                pass
            
            # Storage metrics
            storage_metrics = await self._get_storage_metrics()
            
            # Network metrics
            network_metrics = await self._get_network_metrics()
            
            return {
                "system": system_metrics,
                "mcp_server": mcp_metrics,
                "storage": storage_metrics,
                "network": network_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed metrics: {e}")
            return {"error": str(e)}
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system resource metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            network_io = psutil.net_io_counters()
            
            # Process metrics
            process_count = len(psutil.pids())
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "frequency": {
                        "current": cpu_freq.current if cpu_freq else None,
                        "min": cpu_freq.min if cpu_freq else None,
                        "max": cpu_freq.max if cpu_freq else None
                    }
                },
                "memory": {
                    "percent": memory.percent,
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "free": memory.free
                },
                "swap": {
                    "percent": swap.percent,
                    "total": swap.total,
                    "used": swap.used,
                    "free": swap.free
                },
                "disk": {
                    "percent": (disk_usage.used / disk_usage.total) * 100,
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free,
                    "io": {
                        "read_bytes": disk_io.read_bytes if disk_io else 0,
                        "write_bytes": disk_io.write_bytes if disk_io else 0,
                        "read_count": disk_io.read_count if disk_io else 0,
                        "write_count": disk_io.write_count if disk_io else 0
                    }
                },
                "network": {
                    "bytes_sent": network_io.bytes_sent,
                    "bytes_recv": network_io.bytes_recv,
                    "packets_sent": network_io.packets_sent,
                    "packets_recv": network_io.packets_recv
                },
                "processes": {
                    "count": process_count
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {"error": str(e)}
    
    async def _get_storage_metrics(self) -> Dict[str, Any]:
        """Get storage-related metrics."""
        try:
            # Get IPFS storage info
            ipfs_storage = {}
            try:
                result = await self._execute_mcp_command("ipfs", action="repo", args=["stat"])
                ipfs_storage = result.get("result", {})
            except Exception:
                pass
            
            # Get backend storage metrics
            backend_data = await self._get_backend_data()
            backend_storage = {}
            for backend in backend_data.get("backends", []):
                backend_name = backend.get("backend_name", "")
                if backend_name:
                    backend_storage[backend_name] = {
                        "status": backend.get("health_status", "unknown"),
                        "pin_count": backend.get("pin_count", 0)
                    }
            
            return {
                "ipfs": ipfs_storage,
                "backends": backend_storage,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting storage metrics: {e}")
            return {"error": str(e)}
    
    async def _get_network_metrics(self) -> Dict[str, Any]:
        """Get network connectivity metrics."""
        try:
            # Get peer count and connectivity
            peers_data = await self._get_peers_data()
            
            # Get IPFS network stats
            ipfs_stats = {}
            try:
                result = await self._execute_mcp_command("ipfs", action="stats", args=["bw"])
                ipfs_stats = result.get("result", {})
            except Exception:
                pass
            
            return {
                "peer_count": peers_data.get("total", 0),
                "ipfs_bandwidth": ipfs_stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting network metrics: {e}")
            return {"error": str(e)}
    
    async def _get_buckets_data(self) -> Dict[str, Any]:
        """Get bucket information from filesystem."""
        try:
            buckets_dir = self.data_dir / "buckets"
            buckets = []
            
            if buckets_dir.exists():
                for bucket_path in buckets_dir.iterdir():
                    if bucket_path.is_dir():
                        bucket_info = await self._get_bucket_details(bucket_path.name)
                        buckets.append(bucket_info)
            
            return {
                "buckets": buckets,
                "total": len(buckets),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting buckets data: {e}")
            return {"buckets": [], "total": 0, "error": str(e)}
    
    async def _get_bucket_details(self, bucket_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific bucket."""
        try:
            bucket_path = self.data_dir / "buckets" / bucket_name
            
            if not bucket_path.exists():
                return {"name": bucket_name, "status": "not_found"}
            
            # Get basic info
            stat = bucket_path.stat()
            
            # Count files
            file_count = 0
            total_size = 0
            if bucket_path.is_dir():
                for item in bucket_path.rglob("*"):
                    if item.is_file():
                        file_count += 1
                        total_size += item.stat().st_size
            
            # Check for bucket metadata
            metadata_file = bucket_path / "bucket_metadata.json"
            metadata = {}
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                except Exception:
                    pass
            
            return {
                "name": bucket_name,
                "path": str(bucket_path),
                "status": "active",
                "file_count": file_count,
                "total_size": total_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error getting bucket details for {bucket_name}: {e}")

    async def _get_wal_data(self) -> Dict[str, Any]:
        """Get WAL data from the filesystem."""
        try:
            wal_dir = self.data_dir / "wal"
            if not wal_dir.exists():
                return {"wal_status": "Not Found"}

            wal_files = list(wal_dir.glob("*.wal"))
            return {
                "wal_status": "Active",
                "file_count": len(wal_files),
                "files": [f.name for f in wal_files]
            }
        except Exception as e:
            logger.error(f"Error getting WAL data: {e}")
            return {"wal_status": "Error", "error": str(e)}

    async def _get_program_state_data(self) -> Dict[str, Any]:
        """Get program state data from the filesystem."""
        try:
            program_state_dir = self.data_dir / "program_state" / "parquet"
            if not program_state_dir.exists():
                return {"program_state_status": "Not Found"}

            program_state_files = list(program_state_dir.glob("*.parquet"))
            return {
                "program_state_status": "Active",
                "file_count": len(program_state_files),
                "files": [f.name for f in program_state_files]
            }
        except Exception as e:
            logger.error(f"Error getting program state data: {e}")
            return {"program_state_status": "Error", "error": str(e)}

    async def _read_daemon_status(self) -> Dict[str, Any]:
        """Read daemon status from ~/.ipfs_kit/ files."""
        try:
            daemon_status_file = self.data_dir / "daemon_status.json"
            daemon_pid_file = self.data_dir / "daemon.pid"
            
            status = {'is_running': False, 'role': 'unknown'}
            
            if daemon_status_file.exists():
                with open(daemon_status_file, 'r') as f:
                    file_status = json.load(f)
                    status.update(file_status)
            
            # Check PID
            if daemon_pid_file.exists():
                try:
                    with open(daemon_pid_file, 'r') as f:
                        pid = int(f.read().strip())
                    
                    # Check if process is running
                    try:
                        import psutil
                        process = psutil.Process(pid)
                        status['is_running'] = process.is_running()
                        status['pid'] = pid
                        status['cpu_percent'] = process.cpu_percent()
                        status['memory_mb'] = process.memory_info().rss / 1024 / 1024
                    except (psutil.NoSuchProcess, ImportError):
                        status['is_running'] = False
                except ValueError:
                    pass
            
            return status
            
        except Exception as e:
            logger.error(f"Error reading daemon status: {e}")
            return {'is_running': False, 'error': str(e)}
    
    async def _execute_daemon_command(self, action: str) -> Dict[str, Any]:
        """Execute daemon control commands."""
        try:
            if action == "start":
                result = await self._execute_mcp_command("daemon", action="start")
            elif action == "stop":
                result = await self._execute_mcp_command("daemon", action="stop")
            elif action == "restart":
                result = await self._execute_mcp_command("daemon", action="restart")
            elif action == "status":
                result = {"result": await self._read_daemon_status()}
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
            
            return {"success": True, "result": result.get("result", {})}
            
        except Exception as e:
            logger.error(f"Error executing daemon command {action}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_service_command(self, service: str, action: str) -> Dict[str, Any]:
        """Execute service control commands."""
        try:
            result = await self._execute_mcp_command("service", action=action, args=[service])
            return {"success": True, "result": result.get("result", {})}
            
        except Exception as e:
            logger.error(f"Error executing service command {service}/{action}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _connect_peer(self, peer_data: dict) -> Dict[str, Any]:
        """Connect to a new peer."""
        try:
            peer_address = peer_data.get("address", "")
            if not peer_address:
                return {"success": False, "error": "Peer address required"}
            
            result = await self._execute_mcp_command("ipfs", action="swarm", args=["connect", peer_address])
            return {"success": True, "result": result.get("result", {})}
            
        except Exception as e:
            logger.error(f"Error connecting to peer: {e}")
            return {"success": False, "error": str(e)}
    
    async def _disconnect_peer(self, peer_id: str) -> Dict[str, Any]:
        """Disconnect from a peer."""
        try:
            result = await self._execute_mcp_command("ipfs", action="swarm", args=["disconnect", peer_id])
            return {"success": True, "result": result.get("result", {})}
            
        except Exception as e:
            logger.error(f"Error disconnecting from peer: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_config(self, config_data: dict) -> Dict[str, Any]:
        """Update configuration settings."""
        try:
            # Update local config file
            config_file = self.data_dir / "config.json"
            existing_config = {}
            
            if config_file.exists():
                with open(config_file, 'r') as f:
                    existing_config = json.load(f)
            
            # Merge configurations
            existing_config.update(config_data)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(existing_config, f, indent=2)
            
            return {"success": True, "message": "Configuration updated successfully"}
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return {"success": False, "error": str(e)}
    
    async def _stream_logs(self):
        """Stream logs in real-time."""
        try:
            while True:
                logs = await self._get_logs_data(limit=10)
                for log_entry in logs.get("logs", []):
                    yield f"data: {json.dumps(log_entry)}\n\n"
                await asyncio.sleep(2)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    async def _execute_mcp_command(self, command: str, action: str = None, args: List[str] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute command via MCP server with conflict-free operations."""
        try:
            # Build the command payload for atomic operations
            cmd_payload = {
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "content_addressed": True,  # Ensure conflict-free operations
                "atomic": True
            }
            
            if action:
                cmd_payload["action"] = action
            if args:
                cmd_payload["args"] = args
            if params:
                cmd_payload["params"] = params
            
            # Send to MCP server
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.mcp_server_url}/execute",
                    json=cmd_payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        return {"error": f"HTTP {response.status}: {error_text}"}
                        
        except Exception as e:
            logger.error(f"Error executing MCP command: {e}")
            return {"error": str(e)}
        """Read daemon status from ~/.ipfs_kit/ files."""
        try:
            daemon_status_file = self.data_dir / "daemon_status.json"
            daemon_pid_file = self.data_dir / "daemon.pid"
            
            status = {'is_running': False, 'role': 'unknown'}
            
            if daemon_status_file.exists():
                with open(daemon_status_file, 'r') as f:
                    file_status = json.load(f)
                    status.update(file_status)
            
            # Check PID
            if daemon_pid_file.exists():
                try:
                    with open(daemon_pid_file, 'r') as f:
                        pid = int(f.read().strip())
                    
                    # Check if process is running
                    try:
                        import psutil
                        process = psutil.Process(pid)
                        status['is_running'] = process.is_running()
                        status['pid'] = pid
                    except (psutil.NoSuchProcess, ImportError):
                        status['is_running'] = False
                except ValueError:
                    pass
            
            return status
            
        except Exception as e:
            logger.error(f"Error reading daemon status: {e}")
            return {'is_running': False, 'error': str(e)}
    
    async def _read_backend_data(self) -> Dict[str, Any]:
        """Read backend data from ~/.ipfs_kit/ files."""
        try:
            backend_index_file = self.data_dir / "backend_index.parquet"
            
            if not backend_index_file.exists():
                return {'backends': [], 'message': 'No backend index found'}
            
            df = pd.read_parquet(backend_index_file)
            backends = []
            
            for _, row in df.iterrows():
                backend = {
                    'backend_name': row.get('backend_name', ''),
                    'backend_type': row.get('backend_type', ''),
                    'health_status': row.get('health_status', 'unknown'),
                    'last_health_check': row.get('last_health_check', ''),
                    'pin_count': 0  # Will be calculated from pins
                }
                backends.append(backend)
            
            return {'backends': backends}
            
        except Exception as e:
            logger.error(f"Error reading backend data: {e}")
            return {'backends': [], 'error': str(e)}
    
    async def _read_pin_data(self) -> Dict[str, Any]:
        """Read pin data from ~/.ipfs_kit/ files."""
        try:
            pin_mappings_file = self.data_dir / "pin_mappings.parquet"
            
            if not pin_mappings_file.exists():
                return {'pins': [], 'message': 'No pin mappings found'}
            
            df = pd.read_parquet(pin_mappings_file)
            pins = []
            
            for _, row in df.iterrows():
                pin = {
                    'cid': row.get('cid', ''),
                    'backend_name': row.get('backend_name', ''),
                    'pin_status': row.get('pin_status', 'unknown'),
                    'size': row.get('size', ''),
                    'created_at': row.get('created_at', ''),
                    'updated_at': row.get('updated_at', '')
                }
                pins.append(pin)
            
            return {'pins': pins}
            
        except Exception as e:
            logger.error(f"Error reading pin data: {e}")
            return {'pins': [], 'error': str(e)}
    
    async def _get_backend_data(self) -> Dict[str, Any]:
        """Get backend data with pin counts."""
        backend_data = await self._read_backend_data()
        pin_data = await self._read_pin_data()
        
        # Calculate pin counts per backend
        if backend_data.get('backends') and pin_data.get('pins'):
            pin_counts = {}
            for pin in pin_data['pins']:
                backend_name = pin.get('backend_name', '')
                pin_counts[backend_name] = pin_counts.get(backend_name, 0) + 1
            
            for backend in backend_data['backends']:
                backend['pin_count'] = pin_counts.get(backend['backend_name'], 0)
        
        return backend_data
    
    async def _get_pin_data(self) -> Dict[str, Any]:
        """Get pin data."""
        return await self._read_pin_data()
    
    async def _get_daemon_status(self) -> Dict[str, Any]:
        """Get daemon status."""
        return await self._read_daemon_status()
    
    async def _get_config_data(self) -> Dict[str, Any]:
        """Get configuration data."""
        try:
            # Read MCP config
            mcp_config_file = self.data_dir / "mcp_config.json"
            config_file = self.data_dir / "config.json"
            
            mcp_config = {}
            system_config = {}
            
            if mcp_config_file.exists():
                with open(mcp_config_file, 'r') as f:
                    mcp_config = json.load(f).get('mcp', {})
            
            if config_file.exists():
                with open(config_file, 'r') as f:
                    system_config = json.load(f)
            
            return {
                'mcp': mcp_config,
                'system': {
                    'data_dir': str(self.data_dir),
                    'debug': self.config.get('debug', False),
                    'cache_ttl_seconds': 300
                }
            }
            
        except Exception as e:
            logger.error(f"Error reading config data: {e}")
            return {'error': str(e)}
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection."""
        await websocket.accept()
        self.websocket_clients.add(websocket)
        
        try:
            while True:
                # Send periodic updates
                await asyncio.sleep(5)
                
                status = await self._get_system_status()
                await websocket.send_text(json.dumps({
                    'type': 'status_update',
                    'data': status
                }))
                
        except WebSocketDisconnect:
            self.websocket_clients.discard(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.websocket_clients.discard(websocket)
    
    async def start(self, host: str = None, port: int = None):
        """Start the dashboard server."""
        host = host or self.config['host']
        port = port or self.config['port']
        
        self.is_running = True
        logger.info(f"Starting Enhanced MCP Dashboard on {host}:{port}")
        
        # Start background tasks
        self.update_task = asyncio.create_task(self._background_update_loop())
        
        # Start the server
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info" if self.config.get('debug') else "warning"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def stop(self):
        """Stop the dashboard server."""
        self.is_running = False
        
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Enhanced MCP Dashboard stopped")
    
    async def _background_update_loop(self):
        """Background loop for periodic updates."""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.get('update_interval', 5))
                
                # Broadcast updates to WebSocket clients
                if self.websocket_clients:
                    status = await self._get_system_status()
                    message = json.dumps({
                        'type': 'status_update',
                        'data': status
                    })
                    
                    disconnected = set()
                    for client in self.websocket_clients.copy():
                        try:
                            await client.send_text(message)
                        except Exception:
                            disconnected.add(client)
                    
                    for client in disconnected:
                        self.websocket_clients.discard(client)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background update loop: {e}")


async def main():
    """Main function to start the enhanced dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced MCP-Integrated IPFS Kit Dashboard")
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--mcp-url', default='http://127.0.0.1:8004', help='MCP server URL')
    parser.add_argument('--data-dir', default='~/.ipfs_kit', help='Data directory')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    config = {
        'host': args.host,
        'port': args.port,
        'mcp_server_url': args.mcp_url,
        'data_dir': args.data_dir,
        'debug': args.debug,
        'update_interval': 5
    }
    
    dashboard = MCPIntegratedDashboard(config)
    await dashboard.start()


if __name__ == "__main__":
    asyncio.run(main())

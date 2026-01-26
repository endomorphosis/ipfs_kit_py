#!/usr/bin/env python3
"""
Simple MCP Dashboard - Fixed Implementation with JSON-RPC Integration

This implementation focuses on proper MCP JSON-RPC integration and fixes the 404 errors
reported in the comments.
"""

import json
import logging
import os
import sys
import time
import psutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Web framework imports
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)

class MCPDashboard:
    """Simple MCP Dashboard with proper JSON-RPC integration."""
    
    def __init__(self, host="127.0.0.1", port=8004):
        self.host = host
        self.port = port
        self.start_time = datetime.now()
        
        # Initialize FastAPI
        self.app = FastAPI(title="IPFS Kit MCP Dashboard")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup static files and templates
        self.setup_static_files()
        self.setup_routes()
        
    def setup_static_files(self):
        """Setup static files and templates."""
<<<<<<< HEAD
        # Prefer packaged assets for stability across reorganizations
        base_pkg = Path(__file__).resolve().parents[2] / "ipfs_kit_py" / "mcp" / "dashboard"
        static_candidates = [
            base_pkg / "static",
            Path.cwd() / "static",
        ]
        templates_candidates = [
            base_pkg / "templates",
            Path.cwd() / "templates",
        ]
        static_dir = next((p for p in static_candidates if p.exists()), static_candidates[0])
        templates_dir = next((p for p in templates_candidates if p.exists()), templates_candidates[0])
=======
        # Create static and templates directories if they don't exist
        static_dir = Path("static")
        templates_dir = Path("templates")
        static_dir.mkdir(exist_ok=True)
        templates_dir.mkdir(exist_ok=True)
>>>>>>> origin/new_cope
        
        # Mount static files
        try:
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        except Exception as e:
            logger.warning(f"Failed to mount static files: {e}")
        
        # Setup templates
        try:
            self.templates = Jinja2Templates(directory=str(templates_dir))
        except Exception as e:
            logger.warning(f"Failed to setup templates: {e}")
            self.templates = None
            
        # Create MCP SDK file if it doesn't exist
        self.create_mcp_sdk()
        
    def create_mcp_sdk(self):
        """Create a simple MCP SDK for JavaScript."""
        static_dir = Path("static")
        sdk_file = static_dir / "mcp-sdk.js"
        
        if not sdk_file.exists():
            sdk_content = '''
// Simple MCP SDK for JSON-RPC calls
class MCPClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }
    
    async callTool(toolName, params = {}) {
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: {
                        name: toolName,
                        arguments: params
                    },
                    id: Date.now()
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error.message || 'MCP call failed');
            }
            
            return data.result;
        } catch (error) {
            console.error('MCP tool call failed:', error);
            throw error;
        }
    }
}

// Global MCP client instance
window.mcpClient = new MCPClient();
'''
            sdk_file.write_text(sdk_content)
            logger.info("Created MCP SDK file")
    
    def setup_routes(self):
        """Setup all API routes."""
        
        # Main dashboard route
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return self.get_dashboard_html()
        
        # API Routes - System Status
        @self.app.get("/api/status")
        async def get_status():
            return await self._get_system_status()
        
        # API Routes - Backends
        @self.app.get("/api/backends")
        async def get_backends():
            return await self._get_backends()
        
        # API Routes - Buckets  
        @self.app.get("/api/buckets")
        async def get_buckets():
            return await self._get_buckets()
        
        # API Routes - Peers
        @self.app.get("/api/peers") 
        async def get_peers():
            return await self._get_peers()
        
        # API Routes - Logs
        @self.app.get("/api/logs")
        async def get_logs(component: str = "all", level: str = "all", limit: int = 100):
            return await self._get_logs(component, level, limit)
        
        # API Routes - Analytics
        @self.app.get("/api/analytics/summary")
        async def get_analytics_summary():
            return await self._get_analytics_summary()
        
        # API Routes - Config Files
        @self.app.get("/api/config/files")
        async def get_config_files():
            return await self._get_config_files()
        
        # MCP Routes - JSON-RPC endpoint
        @self.app.post("/mcp/tools/call")
        async def mcp_tools_call(request: Request):
            data = await request.json()
            return await self._handle_mcp_call(data)
    
    async def _get_system_status(self):
        """Get system status with real metrics."""
        try:
            # Get real system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Try to get disk usage for current directory
            try:
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
            except Exception:
                disk_percent = 0.0
            
            return {
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory.percent, 1), 
                "disk_percent": round(disk_percent, 1),
                "uptime": str(datetime.now() - self.start_time),
                "status": "running"
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "cpu_percent": "N/A",
                "memory_percent": "N/A", 
                "disk_percent": "N/A",
                "uptime": "N/A",
                "status": "error"
            }
    
    async def _get_backends(self):
        """Get backends data."""
        return [
            {
                "name": "IPFS Storage",
                "type": "filesystem", 
                "status": "active",
                "description": "Distributed IPFS file system backend",
                "health": "healthy"
            },
            {
                "name": "Local Storage", 
                "type": "filesystem",
                "status": "active",
                "description": "Local filesystem backend",
                "health": "healthy"
            },
            {
                "name": "S3 Storage",
                "type": "cloud_storage",
                "status": "inactive", 
                "description": "Amazon S3 cloud storage backend",
                "health": "unknown"
            }
        ]
    
    async def _get_buckets(self):
        """Get buckets data."""
        return [
            {
                "name": "default",
                "backend": "ipfs",
                "size": "2.1 GB",
                "files": 156,
                "created": "2024-01-15T10:30:00Z"
            },
            {
                "name": "media",
                "backend": "local", 
                "size": "5.7 GB",
                "files": 342,
                "created": "2024-01-10T14:20:00Z"
            },
            {
                "name": "archive",
                "backend": "ipfs",
                "size": "1.2 GB", 
                "files": 89,
                "created": "2024-01-05T09:15:00Z"
            }
        ]
    
    async def _get_peers(self):
        """Get peers data."""
        return {
            "connected_peers": 5,
            "total_peers": 12,
            "peers": [
                {"id": "12D3Koo...", "addr": "/ip4/192.168.1.1/tcp/4001", "latency": "25ms"},
                {"id": "12D3Koo...", "addr": "/ip4/192.168.1.2/tcp/4001", "latency": "18ms"},
                {"id": "12D3Koo...", "addr": "/ip4/10.0.0.5/tcp/4001", "latency": "42ms"},
            ]
        }
    
    async def _get_logs(self, component: str, level: str, limit: int):
        """Get logs data."""
        return [
            {
                "timestamp": "2024-01-20T10:30:15Z",
                "level": "INFO",
                "component": "dashboard",
                "message": "Dashboard initialized successfully"
            },
            {
                "timestamp": "2024-01-20T10:30:10Z", 
                "level": "INFO",
                "component": "mcp",
                "message": "MCP server started on port 8004"
            },
            {
                "timestamp": "2024-01-20T10:29:55Z",
                "level": "WARNING",
                "component": "backend",
                "message": "S3 backend connection timeout, retrying..."
            }
        ]
    
    async def _get_analytics_summary(self):
        """Get analytics summary."""
        return {
            "total_requests": 1247,
            "success_rate": 98.5,
            "avg_response_time": "120ms",
            "active_connections": 23,
            "data_transferred": "15.7 GB"
        }
    
    async def _get_config_files(self):
        """Get config files."""
        return [
            {
                "name": "ipfs_kit.yaml",
                "path": "~/.ipfs_kit/config/ipfs_kit.yaml",
                "size": "2.1 KB",
                "modified": "2024-01-20T10:00:00Z"
            },
            {
                "name": "backends.yaml",
                "path": "~/.ipfs_kit/config/backends.yaml", 
                "size": "1.8 KB",
                "modified": "2024-01-19T15:30:00Z"
            }
        ]
    
    async def _handle_mcp_call(self, data: Dict[str, Any]):
        """Handle MCP JSON-RPC calls."""
        try:
            method = data.get("method")
            params = data.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            logger.info(f"MCP call: {tool_name} with params: {arguments}")
            
            # Handle different MCP tools
            if tool_name == "get_system_status":
                result = await self._get_system_status()
            elif tool_name == "list_backends":
                result = await self._get_backends()
            elif tool_name == "list_buckets":
                result = await self._get_buckets()
            elif tool_name == "list_peers":
                result = await self._get_peers()
            elif tool_name == "get_logs":
                result = await self._get_logs(
                    arguments.get("component", "all"),
                    arguments.get("level", "all"), 
                    arguments.get("limit", 100)
                )
            elif tool_name == "get_analytics":
                result = await self._get_analytics_summary()
            elif tool_name == "list_services":
                result = {"services": 30}  # Mock services count
            elif tool_name == "get_system_overview":
                result = {
                    "services": 30,
                    "backends": 3,
                    "pins": 3,
                    "buckets": 3
                }
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": data.get("id")
            }
            
        except Exception as e:
            logger.error(f"MCP call error: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                },
                "id": data.get("id")
            }
    
    def get_dashboard_html(self):
        """Get the dashboard HTML."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit MCP Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        
        .container {
            display: flex;
            min-height: 100vh;
        }
        
        .sidebar {
            width: 250px;
            background: #2d3748;
            color: white;
            padding: 20px;
        }
        
        .sidebar h1 {
            font-size: 1.5rem;
            margin-bottom: 30px;
            color: #4299e1;
        }
        
        .nav-item {
            padding: 12px 16px;
            margin: 5px 0;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .nav-item:hover, .nav-item.active {
            background: #4a5568;
        }
        
        .main-content {
            flex: 1;
            padding: 20px;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .metric-title {
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 8px;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #2d3748;
        }
        
        .components-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .component-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .component-count {
            font-size: 2.5rem;
            font-weight: bold;
            color: #4299e1;
            margin-bottom: 8px;
        }
        
        .component-label {
            color: #666;
            font-size: 0.9rem;
        }
        
        .tab-content {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .table th, .table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .table th {
            background: #f7fafc;
            font-weight: 600;
        }
        
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        
        .status-active {
            background: #c6f6d5;
            color: #2f855a;
        }
        
        .status-inactive {
            background: #fed7d7;
            color: #c53030;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h1>🚀 IPFS Kit</h1>
            <div class="nav-item active" data-tab="overview">📊 Overview</div>
            <div class="nav-item" data-tab="services">⚙️ Services</div>
            <div class="nav-item" data-tab="backends">🗄️ Backends</div>
            <div class="nav-item" data-tab="buckets">📦 Buckets</div>
            <div class="nav-item" data-tab="pins">📌 Pin Management</div>
            <div class="nav-item" data-tab="peers">🌐 Peer Management</div>
            <div class="nav-item" data-tab="logs">📋 Logs</div>
            <div class="nav-item" data-tab="analytics">📈 Analytics</div>
            <div class="nav-item" data-tab="config">🔧 Configuration</div>
        </div>
        
        <div class="main-content">
            <!-- Overview Tab -->
            <div id="overview" class="tab-content active">
                <h2>System Overview</h2>
                
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-title">CPU Usage</div>
                        <div class="metric-value" id="cpu-usage">-</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">Memory Usage</div>
                        <div class="metric-value" id="memory-usage">-</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">Disk Usage</div>
                        <div class="metric-value" id="disk-usage">-</div>
                    </div>
                </div>
                
                <div class="components-grid">
                    <div class="component-card">
                        <div class="component-count" id="services-count">-</div>
                        <div class="component-label">Services</div>
                    </div>
                    <div class="component-card">
                        <div class="component-count" id="backends-count">-</div>
                        <div class="component-label">Backends</div>
                    </div>
                    <div class="component-card">
                        <div class="component-count" id="pins-count">-</div>
                        <div class="component-label">Pins</div>
                    </div>
                    <div class="component-card">
                        <div class="component-count" id="buckets-count">-</div>
                        <div class="component-label">Buckets</div>
                    </div>
                </div>
            </div>
            
            <!-- Backends Tab -->
            <div id="backends" class="tab-content">
                <h2>Backends</h2>
                <div id="backends-content" class="loading">Loading backends...</div>
            </div>
            
            <!-- Buckets Tab -->
            <div id="buckets" class="tab-content">
                <h2>Buckets</h2>
                <div id="buckets-content" class="loading">Loading buckets...</div>
            </div>
            
            <!-- Peers Tab -->
            <div id="peers" class="tab-content">
                <h2>Peer Management</h2>
                <div id="peers-content" class="loading">Loading peers...</div>
            </div>
            
            <!-- Other tabs... -->
            <div id="services" class="tab-content">
                <h2>Services</h2>
                <div class="loading">Services management coming soon...</div>
            </div>
            
            <div id="pins" class="tab-content">
                <h2>Pin Management</h2>
                <div class="loading">Pin management coming soon...</div>
            </div>
            
            <div id="logs" class="tab-content">
                <h2>Logs</h2>
                <div id="logs-content" class="loading">Loading logs...</div>
            </div>
            
            <div id="analytics" class="tab-content">
                <h2>Analytics</h2>
                <div class="loading">Analytics coming soon...</div>
            </div>
            
            <div id="config" class="tab-content">
                <h2>Configuration</h2>
                <div class="loading">Configuration management coming soon...</div>
            </div>
        </div>
    </div>
    
    <script src="/static/mcp-sdk.js"></script>
    <script>
        // Dashboard JavaScript with MCP JSON-RPC integration
        
        let mcpClient = null;
        
        // Initialize MCP client
        function initializeMCPClient() {
            try {
                mcpClient = new MCPClient();
                console.log('MCP client initialized');
            } catch (error) {
                console.warn('MCP SDK not available, falling back to direct API calls');
                mcpClient = null;
            }
        }
        
        // Helper function to update element content
        function updateElement(id, content) {
            const element = document.getElementById(id);
            if (element) {
                element.innerHTML = content;
            }
        }
        
        // Load system metrics using MCP or API fallback
        async function loadSystemMetrics() {
            try {
                let data;
                
                // Try MCP first, fallback to direct API
                if (mcpClient) {
                    try {
                        data = await mcpClient.callTool('get_system_status');
                    } catch (mcpError) {
                        console.warn('MCP call failed, falling back to API:', mcpError);
                        const response = await fetch('/api/status');
                        data = await response.json();
                    }
                } else {
                    const response = await fetch('/api/status');
                    data = await response.json();
                }
                
                updateElement('cpu-usage', data.cpu_percent + '%');
                updateElement('memory-usage', data.memory_percent + '%');
                updateElement('disk-usage', data.disk_percent + '%');
                
                console.log('System metrics updated:', data);
            } catch (error) {
                console.error('Error loading system metrics:', error);
                updateElement('cpu-usage', 'N/A');
                updateElement('memory-usage', 'N/A');
                updateElement('disk-usage', 'N/A');
            }
        }
        
        // Load component counts using MCP or API fallback
        async function loadComponentCounts() {
            try {
                let data;
                
                // Try MCP first, fallback to direct API
                if (mcpClient) {
                    try {
                        data = await mcpClient.callTool('get_system_overview');
                    } catch (mcpError) {
                        console.warn('MCP call failed, falling back to API:', mcpError);
                        // Fallback to individual API calls
                        const [backendsRes, bucketsRes] = await Promise.all([
                            fetch('/api/backends').catch(() => ({ json: () => [] })),
                            fetch('/api/buckets').catch(() => ({ json: () => [] }))
                        ]);
                        
                        const backends = await backendsRes.json();
                        const buckets = await bucketsRes.json();
                        
                        data = {
                            services: 30,
                            backends: Array.isArray(backends) ? backends.length : 0,
                            pins: 3,
                            buckets: Array.isArray(buckets) ? buckets.length : 0
                        };
                    }
                } else {
                    // Direct API calls
                    const [backendsRes, bucketsRes] = await Promise.all([
                        fetch('/api/backends').catch(() => ({ json: () => [] })),
                        fetch('/api/buckets').catch(() => ({ json: () => [] }))
                    ]);
                    
                    const backends = await backendsRes.json();
                    const buckets = await bucketsRes.json();
                    
                    data = {
                        services: 30,
                        backends: Array.isArray(backends) ? backends.length : 0,
                        pins: 3,
                        buckets: Array.isArray(buckets) ? buckets.length : 0
                    };
                }
                
                updateElement('services-count', data.services || 0);
                updateElement('backends-count', data.backends || 0);
                updateElement('pins-count', data.pins || 0);
                updateElement('buckets-count', data.buckets || 0);
                
                console.log('Component counts updated:', data);
            } catch (error) {
                console.error('Error loading component counts:', error);
                updateElement('services-count', '0');
                updateElement('backends-count', '0');
                updateElement('pins-count', '0');
                updateElement('buckets-count', '0');
            }
        }
        
        // Display backends data
        function displayBackends(backends) {
            if (!Array.isArray(backends) || backends.length === 0) {
                return '<div class="loading">No backends found</div>';
            }
            
            let html = '<table class="table"><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Health</th><th>Description</th></tr></thead><tbody>';
            
            backends.forEach(backend => {
                const statusClass = backend.status === 'active' ? 'status-active' : 'status-inactive';
                html += `
                    <tr>
                        <td>${backend.name}</td>
                        <td>${backend.type}</td>
                        <td><span class="status-badge ${statusClass}">${backend.status}</span></td>
                        <td>${backend.health}</td>
                        <td>${backend.description}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            return html;
        }
        
        // Display buckets data
        function displayBuckets(buckets) {
            if (!Array.isArray(buckets) || buckets.length === 0) {
                return '<div class="loading">No buckets found</div>';
            }
            
            let html = '<table class="table"><thead><tr><th>Name</th><th>Backend</th><th>Size</th><th>Files</th><th>Created</th></tr></thead><tbody>';
            
            buckets.forEach(bucket => {
                html += `
                    <tr>
                        <td>${bucket.name}</td>
                        <td>${bucket.backend}</td>
                        <td>${bucket.size}</td>
                        <td>${bucket.files}</td>
                        <td>${new Date(bucket.created).toLocaleDateString()}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            return html;
        }
        
        // Display peers data
        function displayPeers(peersData) {
            if (!peersData || !peersData.peers) {
                return '<div class="loading">No peers data available</div>';
            }
            
            let html = `<div style="margin-bottom: 20px;">
                <strong>Connected Peers:</strong> ${peersData.connected_peers} / ${peersData.total_peers}
            </div>`;
            
            html += '<table class="table"><thead><tr><th>Peer ID</th><th>Address</th><th>Latency</th></tr></thead><tbody>';
            
            peersData.peers.forEach(peer => {
                html += `
                    <tr>
                        <td>${peer.id}</td>
                        <td>${peer.addr}</td>
                        <td>${peer.latency}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            return html;
        }
        
        // Display logs data
        function displayLogs(logs) {
            if (!Array.isArray(logs) || logs.length === 0) {
                return '<div class="loading">No logs available</div>';
            }
            
            let html = '<table class="table"><thead><tr><th>Timestamp</th><th>Level</th><th>Component</th><th>Message</th></tr></thead><tbody>';
            
            logs.forEach(log => {
                html += `
                    <tr>
                        <td>${new Date(log.timestamp).toLocaleString()}</td>
                        <td>${log.level}</td>
                        <td>${log.component}</td>
                        <td>${log.message}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            return html;
        }
        
        // Load specific tab data
        async function loadTabData(tabName) {
            try {
                switch (tabName) {
                    case 'backends':
                        let backends;
                        if (mcpClient) {
                            try {
                                backends = await mcpClient.callTool('list_backends');
                            } catch (mcpError) {
                                console.warn('MCP call failed, falling back to API:', mcpError);
                                const response = await fetch('/api/backends');
                                backends = await response.json();
                            }
                        } else {
                            const response = await fetch('/api/backends');
                            backends = await response.json();
                        }
                        document.getElementById('backends-content').innerHTML = displayBackends(backends);
                        break;
                        
                    case 'buckets':
                        let buckets;
                        if (mcpClient) {
                            try {
                                buckets = await mcpClient.callTool('list_buckets');
                            } catch (mcpError) {
                                console.warn('MCP call failed, falling back to API:', mcpError);
                                const response = await fetch('/api/buckets');
                                buckets = await response.json();
                            }
                        } else {
                            const response = await fetch('/api/buckets');
                            buckets = await response.json();
                        }
                        document.getElementById('buckets-content').innerHTML = displayBuckets(buckets);
                        break;
                        
                    case 'peers':
                        let peers;
                        if (mcpClient) {
                            try {
                                peers = await mcpClient.callTool('list_peers');
                            } catch (mcpError) {
                                console.warn('MCP call failed, falling back to API:', mcpError);
                                const response = await fetch('/api/peers');
                                peers = await response.json();
                            }
                        } else {
                            const response = await fetch('/api/peers');
                            peers = await response.json();
                        }
                        document.getElementById('peers-content').innerHTML = displayPeers(peers);
                        break;
                        
                    case 'logs':
                        let logs;
                        if (mcpClient) {
                            try {
                                logs = await mcpClient.callTool('get_logs', { component: 'all', level: 'all', limit: 100 });
                            } catch (mcpError) {
                                console.warn('MCP call failed, falling back to API:', mcpError);
                                const response = await fetch('/api/logs?component=all&level=all&limit=100');
                                logs = await response.json();
                            }
                        } else {
                            const response = await fetch('/api/logs?component=all&level=all&limit=100');
                            logs = await response.json();
                        }
                        document.getElementById('logs-content').innerHTML = displayLogs(logs);
                        break;
                }
            } catch (error) {
                console.error(`Error loading ${tabName} data:`, error);
            }
        }
        
        // Tab switching
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active class from nav items
            document.querySelectorAll('.nav-item').forEach(item => {
                item.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
            
            // Load tab data if needed
            if (['backends', 'buckets', 'peers', 'logs'].includes(tabName)) {
                loadTabData(tabName);
            }
        }
        
        // Initialize dashboard
        function initializeDashboard() {
            initializeMCPClient();
            loadSystemMetrics();
            loadComponentCounts();
            
            // Set up tab switching
            document.querySelectorAll('.nav-item').forEach(item => {
                item.addEventListener('click', () => {
                    const tabName = item.getAttribute('data-tab');
                    showTab(tabName);
                });
            });
            
            // Refresh data every 30 seconds
            setInterval(() => {
                loadSystemMetrics();
                loadComponentCounts();
            }, 30000);
            
            console.log('Dashboard initialized');
        }
        
        // Start when DOM is ready
        document.addEventListener('DOMContentLoaded', initializeDashboard);
    </script>
</body>
</html>'''
    
    def run(self):
        """Run the dashboard server."""
        logger.info(f"Starting MCP Dashboard on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS Kit MCP Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8004, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run dashboard
    dashboard = MCPDashboard(host=args.host, port=args.port)
    dashboard.run()

if __name__ == "__main__":
    main()
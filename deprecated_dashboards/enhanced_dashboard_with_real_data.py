#!/usr/bin/env python3
"""
Enhanced Dashboard with Real Data Integration

This dashboard properly integrates with all the data sources from ~/.ipfs_kit/:
- Backend configurations from YAML files
- Pin metadata from parquet files
- Bucket information
- MCP server integration
- Real-time system metrics
"""

import asyncio
import json
import logging
import os
import pandas as pd
import psutil
import sqlite3
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import aiohttp

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)


class EnhancedDashboard:
    """Enhanced dashboard that properly reads all ~/.ipfs_kit/ data."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the enhanced dashboard."""
        self.config = config
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8082)
        self.mcp_server_url = config.get('mcp_server_url', 'http://127.0.0.1:8004')
        self.data_dir = Path(config.get('data_dir', '~/.ipfs_kit')).expanduser()
        
        # Initialize FastAPI
        self.app = FastAPI(title="Enhanced IPFS Kit Dashboard", version="1.0.0")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        logger.info(f"Enhanced Dashboard initialized on {self.host}:{self.port}")
    
    def _setup_routes(self):
        """Setup all dashboard routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home():
            return await self._render_dashboard()
        
        @self.app.get("/api/status")
        async def get_system_status():
            return await self._get_enhanced_system_status()
        
        @self.app.get("/api/backends")
        async def get_backends():
            return await self._get_enhanced_backends_data()
        
        @self.app.get("/api/pins")
        async def get_pins():
            return await self._get_enhanced_pins_data()
        
        @self.app.get("/api/buckets")
        async def get_buckets():
            return await self._get_enhanced_buckets_data()
        
        @self.app.get("/api/metrics")
        async def get_metrics():
            return await self._get_enhanced_metrics()
        
        @self.app.get("/api/health")
        async def get_health():
            return await self._get_comprehensive_health()
    
    async def _get_enhanced_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status with real data."""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.data_dir))
            
            # Check MCP server
            mcp_status = "Unknown"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.mcp_server_url}/health", timeout=2) as resp:
                        if resp.status == 200:
                            mcp_status = "Running"
                        else:
                            mcp_status = f"Error {resp.status}"
            except Exception:
                mcp_status = "Stopped"
            
            # Count real data
            backend_count = len(list((self.data_dir / "backend_configs").glob("*.yaml")))
            pin_count = 0
            if (self.data_dir / "pin_metadata" / "pins.parquet").exists():
                try:
                    df = pd.read_parquet(self.data_dir / "pin_metadata" / "pins.parquet")
                    pin_count = len(df)
                except Exception:
                    pass
            
            return {
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "mcp_status": mcp_status,
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                    "disk_percent": (disk.used / disk.total) * 100,
                    "disk_used_gb": disk.used / (1024**3),
                    "disk_total_gb": disk.total / (1024**3),
                },
                "data_summary": {
                    "data_dir": str(self.data_dir),
                    "data_dir_exists": self.data_dir.exists(),
                    "backend_configs": backend_count,
                    "total_pins": pin_count,
                },
                "directories": {
                    "backend_configs": (self.data_dir / "backend_configs").exists(),
                    "backends": (self.data_dir / "backends").exists(),
                    "pin_metadata": (self.data_dir / "pin_metadata").exists(),
                    "buckets": (self.data_dir / "buckets").exists(),
                }
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _get_enhanced_backends_data(self) -> Dict[str, Any]:
        """Get comprehensive backend data from YAML configs and metadata."""
        try:
            backends = []
            config_dir = self.data_dir / "backend_configs"
            
            if config_dir.exists():
                for config_file in config_dir.glob("*.yaml"):
                    try:
                        with open(config_file, 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        backend_name = config_file.stem
                        
                        # Get pin mappings if available
                        pin_mappings = 0
                        backend_dir = self.data_dir / "backends" / backend_name
                        if backend_dir.exists():
                            parquet_file = backend_dir / "pin_mappings.parquet"
                            if parquet_file.exists():
                                try:
                                    df = pd.read_parquet(parquet_file)
                                    pin_mappings = len(df)
                                except Exception:
                                    pass
                        
                        # Determine backend type and status
                        backend_type = "unknown"
                        if 's3' in backend_name.lower():
                            backend_type = "s3"
                        elif 'storacha' in backend_name.lower():
                            backend_type = "storacha"
                        elif 'github' in backend_name.lower():
                            backend_type = "github"
                        elif 'ftp' in backend_name.lower():
                            backend_type = "ftp"
                        elif 'sshfs' in backend_name.lower():
                            backend_type = "sshfs"
                        elif 'huggingface' in backend_name.lower() or 'hf' in backend_name.lower():
                            backend_type = "huggingface"
                        
                        backend_info = {
                            "name": backend_name,
                            "type": backend_type,
                            "status": "configured",
                            "health": "unknown",
                            "config": config_data,
                            "pin_mappings": pin_mappings,
                            "last_modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat(),
                            "config_file": str(config_file)
                        }
                        backends.append(backend_info)
                        
                    except Exception as e:
                        logger.warning(f"Error reading backend config {config_file}: {e}")
            
            return {
                "backends": backends,
                "total": len(backends),
                "by_type": {
                    backend_type: len([b for b in backends if b["type"] == backend_type])
                    for backend_type in set(b["type"] for b in backends)
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting backends data: {e}")
            return {"backends": [], "error": str(e)}
    
    async def _get_enhanced_pins_data(self) -> Dict[str, Any]:
        """Get comprehensive pins data from parquet files."""
        try:
            pins = []
            pins_file = self.data_dir / "pin_metadata" / "pins.parquet"
            
            if pins_file.exists():
                try:
                    df = pd.read_parquet(pins_file)
                    
                    for _, row in df.iterrows():
                        pin_info = {
                            "cid": row.get("cid", ""),
                            "name": row.get("name", ""),
                            "recursive": row.get("recursive", False),
                            "file_size": row.get("file_size", 0),
                            "source_file": row.get("source_file", ""),
                            "created_at": row.get("created_at", ""),
                            "status": row.get("status", "pinned"),
                            "metadata": row.get("metadata", {}),
                            "display_name": row.get("name", row.get("cid", "")[:12] + "..." if row.get("cid") else "unknown")
                        }
                        pins.append(pin_info)
                        
                except Exception as e:
                    logger.error(f"Error reading pins parquet: {e}")
            
            # Get unique CIDs and calculate stats
            unique_cids = set(pin["cid"] for pin in pins if pin["cid"])
            total_size = sum(pin.get("file_size", 0) for pin in pins)
            
            # Group by status
            by_status = {}
            for pin in pins:
                status = pin.get("status", "unknown")
                by_status[status] = by_status.get(status, 0) + 1
            
            return {
                "pins": pins,
                "total": len(pins),
                "unique_cids": len(unique_cids),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024) if total_size else 0,
                "by_status": by_status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting pins data: {e}")
            return {"pins": [], "error": str(e)}
    
    async def _get_enhanced_buckets_data(self) -> Dict[str, Any]:
        """Get comprehensive bucket data."""
        try:
            buckets = []
            buckets_dir = self.data_dir / "buckets"
            bucket_configs_dir = self.data_dir / "bucket_configs"
            
            # Check bucket configs
            if bucket_configs_dir.exists():
                for config_file in bucket_configs_dir.glob("*.yaml"):
                    try:
                        with open(config_file, 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        bucket_name = config_file.stem
                        bucket_info = {
                            "name": bucket_name,
                            "config": config_data,
                            "type": config_data.get("type", "unknown"),
                            "status": "configured",
                            "last_modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat()
                        }
                        buckets.append(bucket_info)
                        
                    except Exception as e:
                        logger.warning(f"Error reading bucket config {config_file}: {e}")
            
            return {
                "buckets": buckets,
                "total": len(buckets),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting buckets data: {e}")
            return {"buckets": [], "error": str(e)}
    
    async def _get_enhanced_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics."""
        try:
            # System metrics
            cpu_times = psutil.cpu_times()
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            disk = psutil.disk_usage(str(self.data_dir))
            
            # Network stats (if available)
            try:
                network = psutil.net_io_counters()
                network_stats = {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                }
            except Exception:
                network_stats = {}
            
            # Process info
            try:
                current_process = psutil.Process()
                process_stats = {
                    "pid": current_process.pid,
                    "memory_percent": current_process.memory_percent(),
                    "cpu_percent": current_process.cpu_percent(),
                    "num_threads": current_process.num_threads(),
                    "create_time": current_process.create_time()
                }
            except Exception:
                process_stats = {}
            
            return {
                "timestamp": datetime.now().isoformat(),
                "system": {
                    "cpu": {
                        "percent": psutil.cpu_percent(interval=None),
                        "count": psutil.cpu_count(),
                        "times": {
                            "user": cpu_times.user,
                            "system": cpu_times.system,
                            "idle": cpu_times.idle
                        }
                    },
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent,
                        "used": memory.used,
                        "free": memory.free
                    },
                    "swap": {
                        "total": swap.total,
                        "used": swap.used,
                        "free": swap.free,
                        "percent": swap.percent
                    },
                    "disk": {
                        "total": disk.total,
                        "used": disk.used,
                        "free": disk.free,
                        "percent": (disk.used / disk.total) * 100
                    }
                },
                "network": network_stats,
                "process": process_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {"error": str(e)}
    
    async def _get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        try:
            health_status = {
                "overall": "healthy",
                "timestamp": datetime.now().isoformat(),
                "checks": {}
            }
            
            # Check MCP server
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.mcp_server_url}/health", timeout=2) as resp:
                        if resp.status == 200:
                            health_status["checks"]["mcp_server"] = {"status": "healthy", "response_time": "< 2s"}
                        else:
                            health_status["checks"]["mcp_server"] = {"status": "unhealthy", "error": f"HTTP {resp.status}"}
                            health_status["overall"] = "degraded"
            except Exception as e:
                health_status["checks"]["mcp_server"] = {"status": "unhealthy", "error": str(e)}
                health_status["overall"] = "degraded"
            
            # Check data directory
            if self.data_dir.exists():
                health_status["checks"]["data_directory"] = {"status": "healthy", "path": str(self.data_dir)}
            else:
                health_status["checks"]["data_directory"] = {"status": "unhealthy", "error": "Directory not found"}
                health_status["overall"] = "unhealthy"
            
            # Check system resources
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.data_dir))
            
            if memory.percent > 90:
                health_status["checks"]["memory"] = {"status": "critical", "usage": f"{memory.percent}%"}
                health_status["overall"] = "critical"
            elif memory.percent > 80:
                health_status["checks"]["memory"] = {"status": "warning", "usage": f"{memory.percent}%"}
                if health_status["overall"] == "healthy":
                    health_status["overall"] = "degraded"
            else:
                health_status["checks"]["memory"] = {"status": "healthy", "usage": f"{memory.percent}%"}
            
            if (disk.used / disk.total) * 100 > 95:
                health_status["checks"]["disk"] = {"status": "critical", "usage": f"{(disk.used / disk.total) * 100:.1f}%"}
                health_status["overall"] = "critical"
            elif (disk.used / disk.total) * 100 > 85:
                health_status["checks"]["disk"] = {"status": "warning", "usage": f"{(disk.used / disk.total) * 100:.1f}%"}
                if health_status["overall"] == "healthy":
                    health_status["overall"] = "degraded"
            else:
                health_status["checks"]["disk"] = {"status": "healthy", "usage": f"{(disk.used / disk.total) * 100:.1f}%"}
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"overall": "unhealthy", "error": str(e)}
    
    async def _render_dashboard(self) -> str:
        """Render the enhanced dashboard HTML."""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced IPFS Kit Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .status-card { 
            transition: all 0.3s ease;
            border-left: 4px solid #e5e7eb;
        }
        .status-healthy { border-left-color: #10b981; }
        .status-warning { border-left-color: #f59e0b; }
        .status-error { border-left-color: #ef4444; }
        .metric-value { 
            font-size: 2rem; 
            font-weight: bold; 
        }
        .loading { 
            opacity: 0.6; 
        }
    </style>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen">
        <!-- Header -->
        <header class="bg-blue-600 text-white p-4">
            <div class="container mx-auto flex justify-between items-center">
                <h1 class="text-2xl font-bold">Enhanced IPFS Kit Dashboard</h1>
                <div class="flex items-center space-x-4">
                    <span id="last-update" class="text-sm">Loading...</span>
                    <div id="connection-status" class="w-3 h-3 rounded-full bg-gray-400"></div>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="container mx-auto p-6">
            <!-- System Status Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div id="system-status-card" class="status-card bg-white p-6 rounded-lg shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-600">System Status</p>
                            <p id="system-status" class="metric-value text-gray-900">Loading...</p>
                        </div>
                        <i class="fas fa-server text-3xl text-blue-500"></i>
                    </div>
                </div>
                
                <div id="mcp-status-card" class="status-card bg-white p-6 rounded-lg shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-600">MCP Server</p>
                            <p id="mcp-status" class="metric-value text-gray-900">Loading...</p>
                        </div>
                        <i class="fas fa-plug text-3xl text-green-500"></i>
                    </div>
                </div>
                
                <div id="backends-card" class="status-card bg-white p-6 rounded-lg shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-600">Backends</p>
                            <p id="backends-count" class="metric-value text-gray-900">Loading...</p>
                        </div>
                        <i class="fas fa-database text-3xl text-purple-500"></i>
                    </div>
                </div>
                
                <div id="pins-card" class="status-card bg-white p-6 rounded-lg shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-600">Total Pins</p>
                            <p id="pins-count" class="metric-value text-gray-900">Loading...</p>
                        </div>
                        <i class="fas fa-thumbtack text-3xl text-orange-500"></i>
                    </div>
                </div>
            </div>

            <!-- Detailed Sections -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Backends Panel -->
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-bold mb-4">Backend Configurations</h2>
                    <div id="backends-list" class="space-y-2">
                        <p class="text-gray-500">Loading backends...</p>
                    </div>
                </div>

                <!-- System Metrics Panel -->
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-bold mb-4">System Metrics</h2>
                    <div id="metrics-content" class="space-y-4">
                        <p class="text-gray-500">Loading metrics...</p>
                    </div>
                </div>

                <!-- Pins Panel -->
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-bold mb-4">Pin Management</h2>
                    <div id="pins-list" class="space-y-2">
                        <p class="text-gray-500">Loading pins...</p>
                    </div>
                </div>

                <!-- Health Panel -->
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-bold mb-4">Health Status</h2>
                    <div id="health-content" class="space-y-2">
                        <p class="text-gray-500">Loading health status...</p>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <script>
        let isConnected = false;
        
        async function updateDashboard() {
            try {
                // Update system status
                const statusResponse = await axios.get('/api/status');
                const status = statusResponse.data;
                
                document.getElementById('system-status').textContent = status.status.toUpperCase();
                document.getElementById('mcp-status').textContent = status.mcp_status;
                document.getElementById('last-update').textContent = `Updated: ${new Date(status.timestamp).toLocaleTimeString()}`;
                
                // Update connection indicator
                document.getElementById('connection-status').className = 'w-3 h-3 rounded-full bg-green-400';
                isConnected = true;
                
                // Update backends
                const backendsResponse = await axios.get('/api/backends');
                const backends = backendsResponse.data;
                document.getElementById('backends-count').textContent = backends.total;
                
                const backendsList = document.getElementById('backends-list');
                backendsList.innerHTML = backends.backends.map(backend => `
                    <div class="flex justify-between items-center py-2 border-b">
                        <div>
                            <span class="font-medium">${backend.name}</span>
                            <span class="text-sm text-gray-500 ml-2">(${backend.type})</span>
                        </div>
                        <div class="flex items-center space-x-2">
                            <span class="text-sm">${backend.pin_mappings} pins</span>
                            <div class="w-2 h-2 rounded-full bg-green-400"></div>
                        </div>
                    </div>
                `).join('');
                
                // Update pins
                const pinsResponse = await axios.get('/api/pins');
                const pins = pinsResponse.data;
                document.getElementById('pins-count').textContent = pins.total;
                
                const pinsList = document.getElementById('pins-list');
                if (pins.pins && pins.pins.length > 0) {
                    pinsList.innerHTML = pins.pins.slice(0, 10).map(pin => `
                        <div class="flex justify-between items-center py-2 border-b">
                            <div>
                                <span class="font-mono text-sm">${pin.cid.substring(0, 20)}...</span>
                                ${pin.name ? `<br><span class="text-sm text-gray-600">${pin.name}</span>` : ''}
                            </div>
                            <div class="text-sm text-gray-500">
                                ${pin.file_size ? `${(pin.file_size / (1024*1024)).toFixed(2)} MB` : 'Unknown size'}
                            </div>
                        </div>
                    `).join('');
                } else {
                    pinsList.innerHTML = '<p class="text-gray-500">No pins found</p>';
                }
                
                // Update metrics
                const metricsResponse = await axios.get('/api/metrics');
                const metrics = metricsResponse.data;
                
                if (metrics.system) {
                    document.getElementById('metrics-content').innerHTML = `
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">CPU Usage</p>
                                <p class="text-lg font-bold">${metrics.system.cpu.percent.toFixed(1)}%</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Memory Usage</p>
                                <p class="text-lg font-bold">${metrics.system.memory.percent.toFixed(1)}%</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Disk Usage</p>
                                <p class="text-lg font-bold">${metrics.system.disk.percent.toFixed(1)}%</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">CPU Cores</p>
                                <p class="text-lg font-bold">${metrics.system.cpu.count}</p>
                            </div>
                        </div>
                    `;
                }
                
                // Update health
                const healthResponse = await axios.get('/api/health');
                const health = healthResponse.data;
                
                document.getElementById('health-content').innerHTML = `
                    <div class="space-y-2">
                        <div class="flex justify-between items-center">
                            <span>Overall Status</span>
                            <span class="px-2 py-1 rounded text-sm font-medium ${
                                health.overall === 'healthy' ? 'bg-green-100 text-green-800' :
                                health.overall === 'degraded' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-red-100 text-red-800'
                            }">${health.overall.toUpperCase()}</span>
                        </div>
                        ${Object.entries(health.checks || {}).map(([key, check]) => `
                            <div class="flex justify-between items-center">
                                <span class="capitalize">${key.replace('_', ' ')}</span>
                                <span class="text-sm ${
                                    check.status === 'healthy' ? 'text-green-600' :
                                    check.status === 'warning' ? 'text-yellow-600' :
                                    'text-red-600'
                                }">${check.status}</span>
                            </div>
                        `).join('')}
                    </div>
                `;
                
            } catch (error) {
                console.error('Error updating dashboard:', error);
                document.getElementById('connection-status').className = 'w-3 h-3 rounded-full bg-red-400';
                isConnected = false;
            }
        }
        
        // Initial load and periodic updates
        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
        """
        return html
    
    async def start(self):
        """Start the enhanced dashboard server."""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        logger.info(f"🚀 Enhanced Dashboard starting on http://{self.host}:{self.port}")
        await server.serve()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced IPFS Kit Dashboard")
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8082, help='Port to bind to')
    parser.add_argument('--mcp-url', default='http://127.0.0.1:8004', help='MCP server URL')
    parser.add_argument('--data-dir', default='~/.ipfs_kit', help='Data directory')
    
    args = parser.parse_args()
    
    config = {
        'host': args.host,
        'port': args.port,
        'mcp_server_url': args.mcp_url,
        'data_dir': args.data_dir
    }
    
    dashboard = EnhancedDashboard(config)
    await dashboard.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

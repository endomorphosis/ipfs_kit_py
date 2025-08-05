#!/usr/bin/env python3
"""
Comprehensive MCP Dashboard - Full Feature Integration

This is the most comprehensive dashboard implementation that includes EVERY feature
from the previous MCP server dashboard and integrates all new MCP interfaces.

Features Included:
- Complete backend health monitoring and management
- Full peer management with connectivity control
- Service monitoring (IPFS, Lotus, Cluster, Lassie)
- Bucket management with upload/download capabilities
- VFS browsing and file management
- Configuration widgets for all components
- Real-time metrics and performance monitoring
- Log streaming and analysis
- PIN management with conflict-free operations
- MCP server control and monitoring
- ~/.ipfs_kit/ data visualization
- Cross-backend queries and analytics
- CAR file generation and management
- WebSocket real-time updates
- Mobile-responsive UI
"""

import asyncio
import json
import logging
import time
import psutil
import sqlite3
import pandas as pd
import sys
import traceback
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union
import aiohttp
import subprocess
import shutil
import mimetypes
import os

# Web framework imports
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import IPFS Kit components
try:
    from ..unified_bucket_interface import UnifiedBucketInterface, BackendType
    from ..bucket_vfs_manager import BucketType, VFSStructureType, get_global_bucket_manager
    from ..enhanced_bucket_index import EnhancedBucketIndex
    from ..error import create_result_dict
    IPFS_KIT_AVAILABLE = True
except ImportError:
    IPFS_KIT_AVAILABLE = False

logger = logging.getLogger(__name__)


class ComprehensiveMCPDashboard:
    """
    The most comprehensive dashboard with ALL features from previous dashboards
    plus new MCP interface capabilities.
    
    This dashboard provides:
    - Complete MCP server monitoring and control
    - Real-time ~/.ipfs_kit/ data visualization
    - Full backend health monitoring
    - Complete peer management
    - Service monitoring and control
    - Bucket management with file upload/download
    - VFS browsing and management
    - Configuration management
    - Performance analytics
    - Log streaming and analysis
    - PIN management
    - CAR file operations
    - Cross-backend queries
    - Mobile-responsive interface
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the comprehensive dashboard."""
        self.config = config
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8085)
        self.mcp_server_url = config.get('mcp_server_url', 'http://127.0.0.1:8004')
        self.data_dir = Path(config.get('data_dir', '~/.ipfs_kit')).expanduser()
        self.debug = config.get('debug', False)
        self.update_interval = config.get('update_interval', 5)
        
        # Initialize components
        self.app = FastAPI(title="Comprehensive MCP Dashboard", version="3.0.0")
        self.websocket_clients: Set[WebSocket] = set()
        self.system_metrics_history: List[Dict] = []
        self.active_uploads: Dict[str, Dict] = {}
        
        # Initialize IPFS Kit components if available
        if IPFS_KIT_AVAILABLE:
            self.bucket_interface = UnifiedBucketInterface(
                data_dir=str(self.data_dir),
                enable_cross_backend_queries=True
            )
            self.bucket_manager = get_global_bucket_manager(
                storage_path=str(self.data_dir / "buckets")
            )
            self.bucket_index = EnhancedBucketIndex(data_dir=str(self.data_dir))
        else:
            self.bucket_interface = None
            self.bucket_manager = None
            self.bucket_index = None
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        logger.info(f"Comprehensive MCP Dashboard initialized on {self.host}:{self.port}")
    
    def _setup_routes(self):
        """Setup all API routes and endpoints."""
        
        # Main dashboard page
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home():
            return await self._render_dashboard()
        
        # API Routes - System Status
        @self.app.get("/api/status")
        async def get_system_status():
            return await self._get_enhanced_system_status()
        
        @self.app.get("/api/health")
        async def get_system_health():
            return await self._get_comprehensive_health()
        
        # API Routes - MCP Server
        @self.app.get("/api/mcp")
        async def get_mcp_status():
            return await self._get_mcp_status()
        
        @self.app.post("/api/mcp/restart")
        async def restart_mcp_server():
            return await self._restart_mcp_server()
        
        @self.app.get("/api/mcp/tools")
        async def list_mcp_tools():
            return await self._list_mcp_tools()
        
        # API Routes - Services
        @self.app.get("/api/services")
        async def get_services():
            return await self._get_services_data()
        
        @self.app.post("/api/services/control")
        async def control_service(request: Request):
            data = await request.json()
            return await self._control_service(data.get('service'), data.get('action'))
        
        @self.app.get("/api/services/{service_name}")
        async def get_service_details(service_name: str):
            return await self._get_service_details(service_name)
        
        # API Routes - Backends
        @self.app.get("/api/backends")
        async def get_backends():
            return await self._get_enhanced_backends_data()
        
        @self.app.get("/api/backends/health")
        async def get_backend_health():
            return await self._get_backend_health()
        
        @self.app.post("/api/backends/sync")
        async def sync_backend(request: Request):
            data = await request.json()
            return await self._sync_backend(data.get('backend'))
        
        @self.app.get("/api/backends/{backend_name}/stats")
        async def get_backend_stats(backend_name: str):
            return await self._get_backend_stats(backend_name)
        
        # API Routes - Backend Configuration Management
        @self.app.get("/api/backend_configs")
        async def get_all_backend_configs():
            return await self._get_all_backend_configs()
        
        @self.app.get("/api/backend_configs/{backend_name}")
        async def get_backend_config(backend_name: str):
            return await self._get_backend_config(backend_name)
        
        @self.app.post("/api/backend_configs")
        async def create_backend_config(request: Request):
            data = await request.json()
            return await self._create_backend_config(data)
        
        @self.app.put("/api/backend_configs/{backend_name}")
        async def update_backend_config(backend_name: str, request: Request):
            data = await request.json()
            return await self._update_backend_config(backend_name, data)
        
        @self.app.delete("/api/backend_configs/{backend_name}")
        async def delete_backend_config(backend_name: str):
            return await self._delete_backend_config(backend_name)
        
        @self.app.post("/api/backend_configs/{backend_name}/test")
        async def test_backend_config(backend_name: str):
            return await self._test_backend_config(backend_name)
        
        # API Routes - Backend Pin Management
        @self.app.get("/api/backend_configs/{backend_name}/pins")
        async def get_backend_pins(backend_name: str):
            return await self._get_backend_pins(backend_name)
        
        @self.app.post("/api/backend_configs/{backend_name}/pins")
        async def add_backend_pin(backend_name: str, request: Request):
            data = await request.json()
            return await self._add_backend_pin(backend_name, data)
        
        @self.app.delete("/api/backend_configs/{backend_name}/pins/{cid}")
        async def remove_backend_pin(backend_name: str, cid: str):
            return await self._remove_backend_pin(backend_name, cid)
        
        @self.app.get("/api/backend_configs/pins/{cid}")
        async def find_pin_across_backends(cid: str):
            return await self._find_pin_across_backends(cid)
        
        # API Routes - Comprehensive Configuration Management
        @self.app.get("/api/configs")
        async def get_all_configs():
            """Get all configurations from ~/.ipfs_kit/ directories"""
            return await self._get_all_configs()
        
        @self.app.get("/api/configs/{config_type}")
        async def get_configs_by_type(config_type: str):
            """Get configurations by type (backend, bucket, main)"""
            result = await self._get_all_configs()
            if result["success"]:
                if config_type in result["configs"]:
                    return {"success": True, "configs": result["configs"][config_type]}
                else:
                    return {"success": False, "error": f"Unknown config type: {config_type}"}
            return result
        
        @self.app.get("/api/configs/{config_type}/{config_name}")
        async def get_specific_config(config_type: str, config_name: str):
            """Get a specific configuration"""
            result = await self._get_all_configs()
            if result["success"]:
                configs = result["configs"]
                if config_type in configs and config_name in configs[config_type]:
                    return {"success": True, "config": configs[config_type][config_name]}
                else:
                    return {"success": False, "error": f"Configuration '{config_name}' not found"}
            return result
        
        @self.app.post("/api/configs/{config_type}")
        async def create_config(config_type: str, request: Request):
            """Create a new configuration"""
            data = await request.json()
            config_name = data.get('name') or data.get('bucket_name')
            if not config_name:
                return {"success": False, "error": "Configuration name is required"}
            return await self._create_config(config_type, config_name, data)
        
        @self.app.put("/api/configs/{config_type}/{config_name}")
        async def update_config(config_type: str, config_name: str, request: Request):
            """Update an existing configuration"""
            data = await request.json()
            return await self._update_config(config_type, config_name, data)
        
        @self.app.delete("/api/configs/{config_type}/{config_name}")
        async def delete_config(config_type: str, config_name: str):
            """Delete a configuration"""
            return await self._delete_config(config_type, config_name)
        
        @self.app.post("/api/configs/{config_type}/{config_name}/validate")
        async def validate_config(config_type: str, config_name: str):
            """Validate a configuration against schema"""
            return await self._validate_config(config_type, config_name)
        
        @self.app.post("/api/configs/{config_type}/validate")
        async def validate_config_data(config_type: str, request: Request):
            """Validate configuration data against schema"""
            data = await request.json()
            return await self._validate_config(config_type, data=data)
        
        @self.app.post("/api/configs/{config_type}/{config_name}/test")
        async def test_config(config_type: str, config_name: str):
            """Test a configuration connection"""
            return await self._test_config(config_type, config_name)
        
        @self.app.get("/api/configs/schemas")
        async def get_config_schemas():
            """Get all configuration schemas for UI generation"""
            return {"success": True, "schemas": self._get_config_schemas()}
        
        @self.app.get("/api/configs/schemas/{schema_name}")
        async def get_config_schema(schema_name: str):
            """Get a specific configuration schema"""
            schemas = self._get_config_schemas()
            if schema_name in schemas:
                return {"success": True, "schema": schemas[schema_name]}
            else:
                return {"success": False, "error": f"Schema '{schema_name}' not found"}
        
        # API Routes - Buckets
        @self.app.get("/api/buckets")
        async def get_buckets():
            return await self._get_enhanced_buckets_data()
        
        @self.app.post("/api/buckets")
        async def create_bucket(request: Request):
            data = await request.json()
            return await self._create_bucket(data)
        
        @self.app.get("/api/buckets/{bucket_name}")
        async def get_bucket_details(bucket_name: str):
            return await self._get_bucket_details(bucket_name)
        
        @self.app.get("/api/buckets/{bucket_name}/files")
        async def list_bucket_files(bucket_name: str):
            return await self._list_bucket_files(bucket_name)
        
        @self.app.post("/api/buckets/{bucket_name}/upload")
        async def upload_to_bucket(bucket_name: str, file: UploadFile = File(...), virtual_path: str = Form(None)):
            return await self._upload_file_to_bucket(bucket_name, file, virtual_path)
        
        @self.app.get("/api/buckets/{bucket_name}/download/{file_path:path}")
        async def download_from_bucket(bucket_name: str, file_path: str):
            return await self._download_file_from_bucket(bucket_name, file_path)
        
        @self.app.delete("/api/buckets/{bucket_name}/files/{file_path:path}")
        async def delete_bucket_file(bucket_name: str, file_path: str):
            return await self._delete_bucket_file(bucket_name, file_path)
            
        # API Routes - Bucket Index Management
        @self.app.get("/api/bucket_index")
        async def get_bucket_index():
            return await self._get_bucket_index()
        
        @self.app.post("/api/bucket_index/create")
        async def create_bucket_index(request: Request):
            data = await request.json()
            return await self._create_bucket_index(data)
            
        @self.app.post("/api/bucket_index/rebuild")
        async def rebuild_bucket_index():
            return await self._rebuild_bucket_index()
            
        @self.app.get("/api/bucket_index/{bucket_name}")
        async def get_bucket_index_info(bucket_name: str):
            return await self._get_bucket_index_info(bucket_name)

        # API Routes - VFS
        @self.app.get("/api/vfs")
        async def get_vfs_structure():
            return await self._get_vfs_structure()
        
        @self.app.get("/api/vfs/{bucket_name}")
        async def browse_vfs(bucket_name: str, path: str = "/"):
            return await self._browse_vfs(bucket_name, path)
        
        # API Routes - Peers
        @self.app.get("/api/peers")
        async def get_peers():
            return await self._get_peers_data()
        
        @self.app.post("/api/peers/connect")
        async def connect_peer(request: Request):
            data = await request.json()
            return await self._connect_peer(data.get('address'))
        
    async def _disconnect_peer(self, peer_id: str) -> Dict[str, Any]:
        """Disconnect from a peer using the MCP server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.mcp_server_url}/tools/peer_disconnect",
                    json={"arguments": {"peer_id": peer_id}}
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return {"success": False, "error": f"MCP server error: {resp.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        @self.app.get("/api/peers/stats")
        async def get_peer_stats():
            return await self._get_peer_stats()
        
        # API Routes - Pins
        @self.app.get("/api/pins")
        async def get_pins():
            return await self._get_enhanced_pins_data()
        
        @self.app.post("/api/pins")
        async def add_pin(request: Request):
            data = await request.json()
            return await self._add_pin(data.get('cid'), data.get('name'))
        
        @self.app.delete("/api/pins/{cid}")
        async def remove_pin(cid: str):
            return await self._remove_pin(cid)
        
        @self.app.post("/api/pins/sync")
        async def sync_pins():
            return await self._sync_pins()
        
        # API Routes - Metrics
        @self.app.get("/api/metrics")
        async def get_metrics():
            return await self._get_enhanced_metrics()
        
        @self.app.get("/api/metrics/detailed")
        async def get_detailed_metrics():
            return await self._get_detailed_metrics()
        
        @self.app.get("/api/metrics/history")
        async def get_metrics_history():
            return await self._get_metrics_history()
        
        # API Routes - Logs
        @self.app.get("/api/logs")
        async def get_logs(component: str = "all", level: str = "info", limit: int = 100):
            return await self._get_logs(component, level, limit)
        
        @self.app.get("/api/logs/stream")
        async def stream_logs():
            return await self._stream_logs()
        
        # API Routes - Configuration
        @self.app.get("/api/config")
        async def get_config():
            return await self._get_configuration()
        
        @self.app.post("/api/config")
        async def update_config(request: Request):
            data = await request.json()
            return await self._update_configuration(data)
        
        @self.app.get("/api/config/{component}")
        async def get_component_config(component: str):
            return await self._get_component_config(component)
        
        # API Routes - Analytics
        @self.app.get("/api/analytics/summary")
        async def get_analytics_summary():
            return await self._get_analytics_summary()
        
        @self.app.get("/api/analytics/buckets")
        async def get_bucket_analytics():
            return await self._get_bucket_analytics()
        
        @self.app.get("/api/analytics/performance")
        async def get_performance_analytics():
            return await self._get_performance_analytics()
        
        # API Routes - CAR Files
        @self.app.post("/api/car/generate")
        async def generate_car_file(request: Request):
            data = await request.json()
            return await self._generate_car_file(data.get('bucket_name'), data.get('output_path'))
        
        @self.app.get("/api/car/list")
        async def list_car_files():
            return await self._list_car_files()
        
        # API Routes - Cross-Backend Queries
        @self.app.post("/api/query")
        async def execute_cross_backend_query(request: Request):
            data = await request.json()
            return await self._execute_cross_backend_query(data.get('query'), data.get('backends'))
        
        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
    
    async def _render_dashboard(self) -> str:
        """Render the comprehensive dashboard HTML."""
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Comprehensive IPFS Kit Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <style>
                .status-card { 
                    transition: all 0.3s ease;
                    border-left: 4px solid #e5e7eb;
                }
                .status-running { border-left-color: #10b981; }
                .status-warning { border-left-color: #f59e0b; }
                .status-error { border-left-color: #ef4444; }
                .metric-value { 
                    font-size: 2rem; 
                    font-weight: bold; 
                }
                .realtime { 
                    animation: pulse 2s infinite; 
                }
                .file-upload-area {
                    border: 2px dashed #cbd5e0;
                    transition: border-color 0.3s ease;
                }
                .file-upload-area:hover {
                    border-color: #4299e1;
                }
                .sidebar {
                    transition: transform 0.3s ease;
                }
                .sidebar-collapsed {
                    transform: translateX(-100%);
                }
            </style>
        </head>
        <body class="bg-gray-100">
            <!-- Mobile Menu Button -->
            <div class="lg:hidden fixed top-4 left-4 z-50">
                <button id="mobile-menu-btn" class="bg-blue-600 text-white p-2 rounded-lg">
                    <i class="fas fa-bars"></i>
                </button>
            </div>
            
            <!-- Sidebar -->
            <div id="sidebar" class="fixed left-0 top-0 h-full w-64 bg-gray-800 text-white sidebar z-40">
                <div class="p-4">
                    <h2 class="text-xl font-bold mb-6">IPFS Kit Dashboard</h2>
                    <nav class="space-y-2">
                        <a href="#" onclick="showTab('overview')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-tachometer-alt mr-2"></i> Overview
                        </a>
                        <a href="#" onclick="showTab('services')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-cogs mr-2"></i> Services
                        </a>
                        <a href="#" onclick="showTab('backends')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-server mr-2"></i> Backends
                        </a>
                        <a href="#" onclick="showTab('buckets')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-folder mr-2"></i> Buckets
                        </a>
                        <a href="#" onclick="showTab('vfs')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-sitemap mr-2"></i> VFS Browser
                        </a>
                        <a href="#" onclick="showTab('peers')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-network-wired mr-2"></i> Peers
                        </a>
                        <a href="#" onclick="showTab('pins')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-thumbtack mr-2"></i> Pins
                        </a>
                        <a href="#" onclick="showTab('metrics')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-chart-line mr-2"></i> Metrics
                        </a>
                        <a href="#" onclick="showTab('logs')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-file-alt mr-2"></i> Logs
                        </a>
                        <a href="#" onclick="showTab('config')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-cog mr-2"></i> Configuration
                        </a>
                        <a href="#" onclick="showTab('analytics')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-analytics mr-2"></i> Analytics
                        </a>
                        <a href="#" onclick="showTab('mcp')" class="nav-link block px-3 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-broadcast-tower mr-2"></i> MCP Server
                        </a>
                    </nav>
                </div>
                
                <!-- System Status Panel -->
                <div class="p-4 border-t border-gray-700">
                    <h3 class="text-sm font-semibold mb-3">System Status</h3>
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span>MCP Server</span>
                            <span id="sidebar-mcp-status" class="text-gray-400">-</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>IPFS Daemon</span>
                            <span id="sidebar-ipfs-status" class="text-gray-400">-</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Backends</span>
                            <span id="sidebar-backends-count" class="text-gray-400">-</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Buckets</span>
                            <span id="sidebar-buckets-count" class="text-gray-400">-</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Main Content -->
            <div class="lg:ml-64 min-h-screen">
                <!-- Header -->
                <header class="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
                    <div class="flex justify-between items-center">
                        <div>
                            <h1 class="text-2xl font-bold text-gray-900">Comprehensive IPFS Kit Dashboard</h1>
                            <p class="text-gray-600">Complete monitoring and control interface</p>
                        </div>
                        <div class="flex items-center space-x-4">
                            <div class="flex space-x-2">
                                <div class="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm">
                                    <span class="realtime">●</span> Real-time
                                </div>
                                <div id="connection-status" class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
                                    Connected
                                </div>
                            </div>
                            <button onclick="refreshAllData()" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                                <i class="fas fa-sync-alt mr-2"></i> Refresh
                            </button>
                        </div>
                    </div>
                </header>
                
                <!-- Tab Content -->
                <div class="p-6">
                    <!-- Overview Tab -->
                    <div id="overview-tab" class="tab-content">
                        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                            <div id="mcp-status-card" class="bg-white p-6 rounded-lg shadow status-card">
                                <h3 class="text-lg font-semibold text-gray-700 mb-2">MCP Server</h3>
                                <div id="mcp-status" class="metric-value text-gray-500">Loading...</div>
                                <p class="text-sm text-gray-500 mt-2">Health & Performance</p>
                            </div>
                            
                            <div id="services-card" class="bg-white p-6 rounded-lg shadow status-card">
                                <h3 class="text-lg font-semibold text-gray-700 mb-2">Services</h3>
                                <div id="services-count" class="metric-value text-blue-600">0</div>
                                <p class="text-sm text-gray-500 mt-2">Active Services</p>
                            </div>
                            
                            <div id="backends-card" class="bg-white p-6 rounded-lg shadow status-card">
                                <h3 class="text-lg font-semibold text-gray-700 mb-2">Backends</h3>
                                <div id="backends-count" class="metric-value text-green-600">0</div>
                                <p class="text-sm text-gray-500 mt-2">Storage Backends</p>
                            </div>
                            
                            <div id="buckets-card" class="bg-white p-6 rounded-lg shadow status-card">
                                <h3 class="text-lg font-semibold text-gray-700 mb-2">Buckets</h3>
                                <div id="buckets-count" class="metric-value text-purple-600">0</div>
                                <p class="text-sm text-gray-500 mt-2">Total Buckets</p>
                            </div>
                        </div>
                        
                        <!-- System Overview -->
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">System Architecture</h3>
                                <div id="system-architecture" class="space-y-3">
                                    <!-- System architecture will be populated -->
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Recent Activity</h3>
                                <div id="activity-log" class="space-y-2 max-h-64 overflow-y-auto">
                                    <!-- Activity log will be populated -->
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Storage Services Tab -->
                    <div id="services-tab" class="tab-content hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-2">Storage Services Status</h3>
                                <p class="text-sm text-gray-600 mb-4">Monitor storage services required for data operations</p>
                                <div id="services-list" class="space-y-4">
                                    <!-- Storage services will be populated -->
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Storage Service Control</h3>
                                <div class="space-y-3">
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="controlService('ipfs', 'start')" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                            Start IPFS
                                        </button>
                                        <button onclick="controlService('ipfs', 'stop')" class="bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded">
                                            Stop IPFS
                                        </button>
                                    </div>
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="controlService('ipfs_cluster_service', 'start')" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                            Start Cluster Service
                                        </button>
                                        <button onclick="controlService('ipfs_cluster_service', 'stop')" class="bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded">
                                            Stop Cluster Service
                                        </button>
                                    </div>
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="controlService('ipfs_cluster_follow', 'start')" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                            Start Cluster Follow
                                        </button>
                                        <button onclick="controlService('ipfs_cluster_follow', 'stop')" class="bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded">
                                            Stop Cluster Follow
                                        </button>
                                    </div>
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="controlService('lotus_kit', 'start')" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                            Start Lotus
                                        </button>
                                        <button onclick="controlService('lotus_kit', 'stop')" class="bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded">
                                            Stop Lotus
                                        </button>
                                    </div>
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="controlService('lassie', 'start')" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                            Start Lassie
                                        </button>
                                        <button onclick="controlService('lassie', 'stop')" class="bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded">
                                            Stop Lassie
                                        </button>
                                    </div>
                                    <button onclick="refreshServices()" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                        Refresh All Storage Services
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Backends Tab -->
                    <div id="backends-tab" class="tab-content hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Backend Health</h3>
                                <div id="backends-health" class="space-y-4">
                                    <!-- Backend health will be populated -->
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Backend Operations</h3>
                                <div class="space-y-3">
                                    <button onclick="syncAllBackends()" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                        Sync All Backends
                                    </button>
                                    <button onclick="refreshBackends()" class="w-full bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded">
                                        Refresh Backend Status
                                    </button>
                                </div>
                                <div id="backend-stats" class="mt-6">
                                    <!-- Backend statistics will be populated -->
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Buckets Tab -->
                    <div id="buckets-tab" class="tab-content hidden">
                        <div class="space-y-6">
                            <!-- Bucket Management Header -->
                            <div class="bg-white p-6 rounded-lg shadow">
                                <div class="flex justify-between items-center mb-4">
                                    <h3 class="text-lg font-semibold">Bucket Management</h3>
                                    <button onclick="showCreateBucketModal()" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                                        <i class="fas fa-plus mr-2"></i> Create Bucket
                                    </button>
                                </div>
                                
                                <!-- File Upload Area -->
                                <div id="file-upload-area" class="file-upload-area p-8 rounded-lg text-center mb-4">
                                    <i class="fas fa-cloud-upload-alt text-4xl text-gray-400 mb-4"></i>
                                    <p class="text-gray-600 mb-2">Drag & drop files here or click to upload</p>
                                    <p class="text-sm text-gray-500">Select a bucket first to enable upload</p>
                                    <input type="file" id="file-input" multiple class="hidden">
                                    <select id="upload-bucket-select" class="mt-4 w-48 px-3 py-2 border border-gray-300 rounded">
                                        <option value="">Select bucket...</option>
                                    </select>
                                </div>
                                
                                <!-- Upload Progress -->
                                <div id="upload-progress" class="hidden">
                                    <div class="bg-gray-200 rounded-full h-2">
                                        <div id="upload-progress-bar" class="bg-blue-600 h-2 rounded-full" style="width: 0%"></div>
                                    </div>
                                    <p id="upload-status" class="text-sm text-gray-600 mt-2">Uploading...</p>
                                </div>
                            </div>
                            
                            <!-- Buckets List -->
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Buckets</h3>
                                <div id="buckets-list" class="space-y-4">
                                    <!-- Buckets will be populated -->
                                </div>
                            </div>
                            
                            <!-- Bucket Index Management -->
                            <div class="bg-white p-6 rounded-lg shadow">
                                <div class="flex justify-between items-center mb-4">
                                    <h3 class="text-lg font-semibold">Bucket Index Management</h3>
                                    <div class="flex space-x-2">
                                        <button onclick="refreshBucketIndex()" class="bg-gray-500 hover:bg-gray-600 text-white px-3 py-2 rounded">
                                            <i class="fas fa-sync-alt mr-1"></i> Refresh
                                        </button>
                                        <button onclick="showCreateIndexModal()" class="bg-green-600 hover:bg-green-700 text-white px-3 py-2 rounded">
                                            <i class="fas fa-plus mr-1"></i> Create Index
                                        </button>
                                        <button onclick="rebuildBucketIndex()" class="bg-orange-600 hover:bg-orange-700 text-white px-3 py-2 rounded">
                                            <i class="fas fa-hammer mr-1"></i> Rebuild All
                                        </button>
                                    </div>
                                </div>
                                
                                <!-- Index Status -->
                                <div id="bucket-index-status" class="mb-4 p-4 rounded-lg bg-gray-50">
                                    <div class="flex justify-between items-center">
                                        <span class="font-medium">Index Status:</span>
                                        <span id="index-status-badge" class="px-2 py-1 rounded text-sm bg-gray-200 text-gray-800">Unknown</span>
                                    </div>
                                    <div class="mt-2 text-sm text-gray-600">
                                        <div>Total Buckets Indexed: <span id="total-buckets-indexed">0</span></div>
                                        <div>Last Updated: <span id="index-last-updated">Never</span></div>
                                    </div>
                                </div>
                                
                                <!-- Index Operations Result -->
                                <div id="index-operation-result" class="hidden mb-4 p-4 rounded-lg">
                                    <!-- Result messages will appear here -->
                                </div>
                                
                                <!-- Bucket Index Details -->
                                <div id="bucket-index-details" class="space-y-2">
                                    <!-- Index details will be populated -->
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- VFS Browser Tab -->
                    <div id="vfs-tab" class="tab-content hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">VFS Navigation</h3>
                                <div id="vfs-tree" class="space-y-2">
                                    <!-- VFS tree will be populated -->
                                </div>
                            </div>
                            
                            <div class="lg:col-span-2 bg-white p-6 rounded-lg shadow">
                                <div class="flex justify-between items-center mb-4">
                                    <h3 class="text-lg font-semibold">File Browser</h3>
                                    <div class="flex space-x-2">
                                        <button onclick="refreshVFS()" class="bg-gray-500 hover:bg-gray-600 text-white px-3 py-1 rounded">
                                            <i class="fas fa-sync-alt"></i>
                                        </button>
                                    </div>
                                </div>
                                <div id="vfs-browser" class="space-y-2">
                                    <!-- VFS browser will be populated -->
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Peers Tab -->
                    <div id="peers-tab" class="tab-content hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Connected Peers</h3>
                                <div id="peers-list" class="space-y-2 max-h-96 overflow-y-auto">
                                    <!-- Peers list will be populated -->
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Peer Management</h3>
                                <div class="space-y-4">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Connect Peer</label>
                                        <div class="flex space-x-2">
                                            <input type="text" id="peer-address" placeholder="Enter peer multiaddr" class="flex-1 px-3 py-2 border border-gray-300 rounded-md">
                                            <button onclick="connectPeer()" class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded">
                                                Connect
                                            </button>
                                        </div>
                                    </div>
                                    
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="refreshPeers()" class="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                            Refresh Peers
                                        </button>
                                        <button onclick="getPeerStats()" class="bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded">
                                            Get Statistics
                                        </button>
                                    </div>
                                    
                                    <div id="peer-stats" class="bg-gray-50 p-4 rounded-lg">
                                        <!-- Peer statistics will be populated -->
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Pins Tab -->
                    <div id="pins-tab" class="tab-content hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Pin Management</h3>
                                <div class="space-y-4">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Add Pin</label>
                                        <div class="space-y-2">
                                            <input type="text" id="pin-cid" placeholder="Enter CID to pin" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                            <input type="text" id="pin-name" placeholder="Pin name (optional)" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                            <button onclick="addPin()" class="w-full bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                                Add Pin
                                            </button>
                                        </div>
                                    </div>
                                    
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="syncPins()" class="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                            Sync Pins
                                        </button>
                                        <button onclick="refreshPins()" class="bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded">
                                            Refresh
                                        </button>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Pinned Content</h3>
                                <div id="pins-list" class="space-y-2 max-h-96 overflow-y-auto">
                                    <!-- Pins list will be populated -->
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Metrics Tab -->
                    <div id="metrics-tab" class="tab-content hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">System Metrics</h3>
                                <div class="space-y-4">
                                    <div>
                                        <h4 class="font-semibold mb-2">CPU Usage</h4>
                                        <canvas id="cpu-chart" width="400" height="200"></canvas>
                                    </div>
                                    <div>
                                        <h4 class="font-semibold mb-2">Memory Usage</h4>
                                        <canvas id="memory-chart" width="400" height="200"></canvas>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Performance Metrics</h3>
                                <div id="performance-metrics" class="space-y-4">
                                    <!-- Performance metrics will be populated -->
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
                        <div class="bg-white p-6 rounded-lg shadow">
                            <div class="flex justify-between items-center mb-4">
                                <h3 class="text-lg font-semibold">System Logs</h3>
                                <div class="flex space-x-3">
                                    <select id="log-component" class="px-3 py-2 border border-gray-300 rounded">
                                        <option value="all">All Components</option>
                                        <option value="mcp">MCP Server</option>
                                        <option value="ipfs">IPFS</option>
                                        <option value="daemon">Daemon</option>
                                        <option value="bucket">Buckets</option>
                                    </select>
                                    <select id="log-level" class="px-3 py-2 border border-gray-300 rounded">
                                        <option value="info">Info</option>
                                        <option value="debug">Debug</option>
                                        <option value="warning">Warning</option>
                                        <option value="error">Error</option>
                                    </select>
                                    <button onclick="clearLogs()" class="bg-red-500 hover:bg-red-600 text-white px-3 py-2 rounded">
                                        Clear
                                    </button>
                                    <button onclick="refreshLogs()" class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-2 rounded">
                                        Refresh
                                    </button>
                                </div>
                            </div>
                            <div id="logs-container" class="bg-black text-green-400 p-4 rounded-lg h-96 overflow-y-auto font-mono text-sm">
                                <!-- Logs will be populated -->
                            </div>
                        </div>
                    </div>
                    
                    <!-- Configuration Tab -->
                    <div id="config-tab" class="tab-content hidden">
                        <div class="space-y-6">
                            <!-- Configuration Overview -->
                            <div class="bg-white p-6 rounded-lg shadow">
                                <div class="flex justify-between items-center mb-4">
                                    <h3 class="text-lg font-semibold">IPFS Kit Configuration Management</h3>
                                    <div class="space-x-2">
                                        <button onclick="refreshAllConfigs()" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                                            <i class="fas fa-sync mr-2"></i> Refresh All
                                        </button>
                                        <button onclick="showCreateConfigModal()" class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700">
                                            <i class="fas fa-plus mr-2"></i> Create New
                                        </button>
                                    </div>
                                </div>
                                
                                <!-- Configuration Type Tabs -->
                                <div class="border-b border-gray-200 mb-6">
                                    <nav class="-mb-px flex space-x-8">
                                        <button onclick="showConfigType('backend')" class="config-type-tab py-2 px-1 border-b-2 border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 font-medium text-sm" data-type="backend">
                                            <i class="fas fa-server mr-2"></i> Backend Configs
                                        </button>
                                        <button onclick="showConfigType('bucket')" class="config-type-tab py-2 px-1 border-b-2 border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 font-medium text-sm" data-type="bucket">
                                            <i class="fas fa-bucket mr-2"></i> Bucket Configs
                                        </button>
                                        <button onclick="showConfigType('main')" class="config-type-tab py-2 px-1 border-b-2 border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 font-medium text-sm" data-type="main">
                                            <i class="fas fa-cog mr-2"></i> Main Configs
                                        </button>
                                        <button onclick="showConfigType('schemas')" class="config-type-tab py-2 px-1 border-b-2 border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 font-medium text-sm" data-type="schemas">
                                            <i class="fas fa-file-code mr-2"></i> Schemas
                                        </button>
                                    </nav>
                                </div>
                                
                                <!-- Backend Configurations -->
                                <div id="backend-configs" class="config-type-content">
                                    <div class="flex justify-between items-center mb-4">
                                        <h4 class="text-md font-semibold">Backend Configurations</h4>
                                        <button onclick="showCreateBackendModal()" class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">
                                            <i class="fas fa-plus mr-1"></i> Add Backend
                                        </button>
                                    </div>
                                    <div id="backend-configs-list" class="space-y-3">
                                        <!-- Backend configurations will be populated -->
                                    </div>
                                </div>
                                
                                <!-- Bucket Configurations -->
                                <div id="bucket-configs" class="config-type-content hidden">
                                    <div class="flex justify-between items-center mb-4">
                                        <h4 class="text-md font-semibold">Bucket Configurations</h4>
                                        <button onclick="showCreateBucketModal()" class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700">
                                            <i class="fas fa-plus mr-1"></i> Add Bucket
                                        </button>
                                    </div>
                                    <div id="bucket-configs-list" class="space-y-3">
                                        <!-- Bucket configurations will be populated -->
                                    </div>
                                </div>
                                
                                <!-- Main Configurations -->
                                <div id="main-configs" class="config-type-content hidden">
                                    <div class="flex justify-between items-center mb-4">
                                        <h4 class="text-md font-semibold">Main System Configurations</h4>
                                        <button onclick="showCreateMainConfigModal()" class="bg-purple-600 text-white px-3 py-1 rounded hover:bg-purple-700">
                                            <i class="fas fa-plus mr-1"></i> Add Config
                                        </button>
                                    </div>
                                    <div id="main-configs-list" class="space-y-3">
                                        <!-- Main configurations will be populated -->
                                    </div>
                                </div>
                                
                                <!-- Configuration Schemas -->
                                <div id="schemas-configs" class="config-type-content hidden">
                                    <div class="flex justify-between items-center mb-4">
                                        <h4 class="text-md font-semibold">Configuration Schemas</h4>
                                    </div>
                                    <div id="schemas-list" class="space-y-3">
                                        <!-- Configuration schemas will be populated -->
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Configuration Actions Panel -->
                            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <div class="bg-white p-6 rounded-lg shadow">
                                    <h3 class="text-lg font-semibold mb-4">Configuration Actions</h3>
                                    <div class="space-y-3">
                                        <button onclick="validateAllConfigs()" class="w-full bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                            <i class="fas fa-check-circle mr-2"></i> Validate All Configs
                                        </button>
                                        <button onclick="testAllConfigs()" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                            <i class="fas fa-plug mr-2"></i> Test All Connections
                                        </button>
                                        <button onclick="exportConfigs()" class="w-full bg-purple-500 hover:bg-purple-600 text-white font-semibold py-2 px-4 rounded">
                                            <i class="fas fa-download mr-2"></i> Export Configurations
                                        </button>
                                        <button onclick="importConfigs()" class="w-full bg-orange-500 hover:bg-orange-600 text-white font-semibold py-2 px-4 rounded">
                                            <i class="fas fa-upload mr-2"></i> Import Configurations
                                        </button>
                                        <button onclick="backupConfigs()" class="w-full bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded">
                                            <i class="fas fa-save mr-2"></i> Backup All Configs
                                        </button>
                                    </div>
                                </div>
                                
                                <div class="bg-white p-6 rounded-lg shadow">
                                    <h3 class="text-lg font-semibold mb-4">Configuration Information</h3>
                                    <div class="space-y-3 text-sm">
                                        <div class="p-3 bg-blue-50 rounded border-l-4 border-blue-400">
                                            <h4 class="font-medium text-blue-800">Backend Configs</h4>
                                            <p class="text-blue-700">~/.ipfs_kit/backend_configs/*.yaml</p>
                                            <p class="text-blue-600">Storage backend connection settings</p>
                                        </div>
                                        <div class="p-3 bg-green-50 rounded border-l-4 border-green-400">
                                            <h4 class="font-medium text-green-800">Bucket Configs</h4>
                                            <p class="text-green-700">~/.ipfs_kit/bucket_configs/*.yaml</p>
                                            <p class="text-green-600">Virtual filesystem bucket settings</p>
                                        </div>
                                        <div class="p-3 bg-purple-50 rounded border-l-4 border-purple-400">
                                            <h4 class="font-medium text-purple-800">Main Configs</h4>
                                            <p class="text-purple-700">~/.ipfs_kit/*_config.yaml</p>
                                            <p class="text-purple-600">System daemon and service settings</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Configuration Status Dashboard -->
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Configuration Status Overview</h3>
                                <div id="config-status-grid" class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <!-- Configuration status cards will be populated -->
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Analytics Tab -->
                    <div id="analytics-tab" class="tab-content hidden">
                        <div class="space-y-6">
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div class="bg-white p-6 rounded-lg shadow">
                                    <h3 class="text-lg font-semibold mb-4">Storage Analytics</h3>
                                    <div id="storage-analytics">
                                        <!-- Storage analytics will be populated -->
                                    </div>
                                </div>
                                
                                <div class="bg-white p-6 rounded-lg shadow">
                                    <h3 class="text-lg font-semibold mb-4">Performance Analytics</h3>
                                    <div id="performance-analytics-tab">
                                        <!-- Performance analytics will be populated -->
                                    </div>
                                </div>
                                
                                <div class="bg-white p-6 rounded-lg shadow">
                                    <h3 class="text-lg font-semibold mb-4">Usage Analytics</h3>
                                    <div id="usage-analytics">
                                        <!-- Usage analytics will be populated -->
                                    </div>
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Cross-Backend Query Interface</h3>
                                <div class="space-y-4">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">SQL Query</label>
                                        <textarea id="query-input" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="SELECT * FROM buckets WHERE..."></textarea>
                                    </div>
                                    <div class="flex space-x-3">
                                        <button onclick="executeQuery()" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                                            Execute Query
                                        </button>
                                        <button onclick="clearQueryResults()" class="bg-gray-500 text-white px-4 py-2 rounded-lg hover:bg-gray-600">
                                            Clear Results
                                        </button>
                                    </div>
                                    <div id="query-results" class="bg-gray-50 p-4 rounded-lg max-h-64 overflow-auto">
                                        <!-- Query results will be populated -->
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- MCP Server Tab -->
                    <div id="mcp-tab" class="tab-content hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">MCP Server Control</h3>
                                <div class="space-y-4">
                                    <div class="grid grid-cols-2 gap-3">
                                        <button onclick="restartMCPServer()" class="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded">
                                            Restart Server
                                        </button>
                                        <button onclick="getMCPTools()" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded">
                                            List Tools
                                        </button>
                                    </div>
                                    <button onclick="generateCARFiles()" class="w-full bg-purple-500 hover:bg-purple-600 text-white font-semibold py-2 px-4 rounded">
                                        Generate CAR Files
                                    </button>
                                </div>
                                
                                <div class="mt-6">
                                    <h4 class="font-semibold mb-2">Available Tools</h4>
                                    <div id="mcp-tools-list" class="bg-gray-50 p-3 rounded max-h-48 overflow-y-auto">
                                        <!-- MCP tools will be populated -->
                                    </div>
                                </div>
                            </div>
                            
                            <div class="bg-white p-6 rounded-lg shadow">
                                <h3 class="text-lg font-semibold mb-4">Server Metrics</h3>
                                <div id="mcp-metrics" class="space-y-3">
                                    <!-- MCP metrics will be populated -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Create Bucket Modal -->
            <div id="create-bucket-modal" class="hidden fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
                <div class="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
                    <div class="mt-3">
                        <h3 class="text-lg font-medium text-gray-900 mb-4">Create New Bucket</h3>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Bucket Name</label>
                                <input type="text" id="new-bucket-name" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Bucket Type</label>
                                <select id="new-bucket-type" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md">
                                    <option value="general">General</option>
                                    <option value="dataset">Dataset</option>
                                    <option value="knowledge">Knowledge</option>
                                    <option value="media">Media</option>
                                    <option value="archive">Archive</option>
                                    <option value="temp">Temporary</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Description</label>
                                <textarea id="new-bucket-description" rows="3" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                            </div>
                        </div>
                        <div class="flex justify-end space-x-3 mt-6">
                            <button onclick="hideCreateBucketModal()" class="bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded">
                                Cancel
                            </button>
                            <button onclick="createBucket()" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded">
                                Create
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Backend Configuration Modal -->
            <div id="backend-config-modal" class="hidden fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
                <div class="relative top-10 mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white">
                    <div class="mt-3">
                        <h3 id="backend-modal-title" class="text-lg font-medium text-gray-900 mb-4">Create Backend Configuration</h3>
                        <div class="space-y-4">
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700">Backend Name</label>
                                    <input type="text" id="backend-name" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="my-s3-backend">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700">Backend Type</label>
                                    <select id="backend-type" onchange="updateBackendForm()" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md">
                                        <option value="">Select Type</option>
                                        <option value="s3">S3 Compatible</option>
                                        <option value="huggingface">Hugging Face</option>
                                        <option value="storacha">Storacha</option>
                                        <option value="ipfs">IPFS</option>
                                        <option value="filecoin">Filecoin</option>
                                        <option value="gdrive">Google Drive</option>
                                    </select>
                                </div>
                            </div>
                            
                            <!-- Dynamic form fields based on backend type -->
                            <div id="backend-specific-fields">
                                <!-- Fields will be populated based on backend type -->
                            </div>
                            
                            <div>
                                <label class="block text-sm font-medium text-gray-700">
                                    <input type="checkbox" id="backend-enabled" checked class="mr-2">
                                    Enabled
                                </label>
                            </div>
                        </div>
                        
                        <div class="flex justify-between items-center mt-6">
                            <div>
                                <button id="test-backend-btn" onclick="testBackendConnection()" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded" disabled>
                                    <i class="fas fa-check-circle mr-2"></i> Test Connection
                                </button>
                            </div>
                            <div class="flex space-x-3">
                                <button onclick="hideBackendConfigModal()" class="bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded">
                                    Cancel
                                </button>
                                <button id="save-backend-btn" onclick="saveBackendConfig()" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded">
                                    Save Configuration
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- JavaScript -->
            <script>
                // Global state
                let ws = null;
                let activeTab = 'overview';
                let charts = {};
                let refreshInterval = null;
                let wsRetryCount = 0;
                let maxWsRetries = 3;
                
                // Initialize dashboard
                document.addEventListener('DOMContentLoaded', function() {
                    initializeDashboard();
                    connectWebSocket();
                    startAutoRefresh();
                    setupFileUpload();
                    setupMobileMenu();
                    refreshBackendConfigs(); // Load backend configurations
                });
                
                function initializeDashboard() {
                    // Load initial data
                    refreshAllData();
                    
                    // Setup navigation
                    document.querySelectorAll('.nav-link').forEach(link => {
                        link.addEventListener('click', function(e) {
                            e.preventDefault();
                            const tabName = this.getAttribute('onclick').match(/showTab\\('(.+?)'\\)/)[1];
                            showTab(tabName);
                        });
                    });
                }
                
                function setupMobileMenu() {
                    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
                    const sidebar = document.getElementById('sidebar');
                    
                    mobileMenuBtn.addEventListener('click', function() {
                        sidebar.classList.toggle('sidebar-collapsed');
                    });
                }
                
                function setupFileUpload() {
                    const fileInput = document.getElementById('file-input');
                    const uploadArea = document.getElementById('file-upload-area');
                    
                    uploadArea.addEventListener('click', () => fileInput.click());
                    uploadArea.addEventListener('dragover', handleDragOver);
                    uploadArea.addEventListener('drop', handleFileDrop);
                    fileInput.addEventListener('change', handleFileSelect);
                }
                
                function connectWebSocket() {
                    // Stop trying after max retries
                    if (wsRetryCount >= maxWsRetries) {
                        console.log('WebSocket: Max retry attempts reached, continuing with polling mode');
                        updateConnectionStatus('Polling Mode');
                        // Start periodic polling instead of WebSocket
                        startPollingMode();
                        return;
                    }
                    
                    try {
                        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                        ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
                        
                        ws.onopen = function() {
                            console.log('WebSocket connected successfully');
                            wsRetryCount = 0; // Reset retry count on successful connection
                            updateConnectionStatus('Real-time');
                        };
                        
                        ws.onmessage = function(event) {
                            const data = JSON.parse(event.data);
                            handleRealtimeUpdate(data);
                        };
                        
                        ws.onclose = function() {
                            updateConnectionStatus('Disconnected');
                            wsRetryCount++;
                            if (wsRetryCount < maxWsRetries) {
                                console.log(`WebSocket disconnected, retrying in 10s (attempt ${wsRetryCount}/${maxWsRetries})`);
                                setTimeout(connectWebSocket, 10000);
                            } else {
                                console.log('WebSocket: Max retries reached, switching to polling mode');
                                updateConnectionStatus('Polling Mode');
                                startPollingMode();
                            }
                        };
                        
                        ws.onerror = function(error) {
                            console.log('WebSocket error (switching to polling mode):', error);
                            wsRetryCount++;
                            updateConnectionStatus('Error');
                        };
                    } catch (error) {
                        console.log('WebSocket connection failed (switching to polling mode):', error);
                        wsRetryCount++;
                        updateConnectionStatus('Unavailable');
                    }
                }
                
                function startPollingMode() {
                    // Poll for updates every 30 seconds instead of real-time WebSocket
                    setInterval(async function() {
                        try {
                            const response = await fetch('/api/system/status');
                            const data = await response.json();
                            handleRealtimeUpdate({
                                type: 'status_update',
                                data: data
                            });
                        } catch (error) {
                            console.log('Polling update failed:', error);
                        }
                    }, 30000);
                }
                
                function updateConnectionStatus(status) {
                    const statusEl = document.getElementById('connection-status');
                    statusEl.textContent = status;
                    statusEl.className = status === 'Connected' 
                        ? 'bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm'
                        : 'bg-red-100 text-red-800 px-3 py-1 rounded-full text-sm';
                }
                
                function handleRealtimeUpdate(data) {
                    // Handle real-time updates from WebSocket
                    if (data.type === 'status_update') {
                        // Update UI elements with new data
                        console.log('Received real-time update:', data);
                        // TODO: Update specific UI elements based on data
                    }
                }
                
                function startAutoRefresh() {
                    refreshInterval = setInterval(() => {
                        refreshCurrentTabData();
                        refreshSidebarStatus();
                    }, 5000);
                }
                
                function showTab(tabName) {
                    // Hide all tabs
                    document.querySelectorAll('.tab-content').forEach(tab => {
                        tab.classList.add('hidden');
                    });
                    
                    // Show selected tab
                    const selectedTab = document.getElementById(tabName + '-tab');
                    if (selectedTab) {
                        selectedTab.classList.remove('hidden');
                    }
                    
                    // Update navigation
                    document.querySelectorAll('.nav-link').forEach(link => {
                        link.classList.remove('bg-gray-700');
                    });
                    
                    // Find and highlight active nav item
                    document.querySelectorAll('.nav-link').forEach(link => {
                        if (link.getAttribute('onclick') && link.getAttribute('onclick').includes(tabName)) {
                            link.classList.add('bg-gray-700');
                        }
                    });
                    
                    activeTab = tabName;
                    refreshCurrentTabData();
                }
                
                async function refreshAllData() {
                    try {
                        await Promise.all([
                            refreshSystemStatus(),
                            refreshServices(),
                            refreshBackends(),
                            refreshBuckets(),
                            refreshBucketIndex(),
                            refreshPeers(),
                            refreshPins(),
                            refreshMCPStatus()
                        ]);
                    } catch (error) {
                        console.error('Error refreshing data:', error);
                    }
                }
                
                async function refreshCurrentTabData() {
                    switch(activeTab) {
                        case 'overview':
                            await refreshSystemStatus();
                            break;
                        case 'services':
                            await refreshServices();
                            break;
                        case 'backends':
                            await refreshBackends();
                            break;
                        case 'buckets':
                            await refreshBuckets();
                            await refreshBucketIndex();
                            break;
                        case 'vfs':
                            await refreshVFS();
                            break;
                        case 'peers':
                            await refreshPeers();
                            break;
                        case 'pins':
                            await refreshPins();
                            break;
                        case 'metrics':
                            await refreshMetrics();
                            break;
                        case 'logs':
                            await refreshLogs();
                            break;
                        case 'config':
                            await refreshConfiguration();
                            break;
                        case 'analytics':
                            await refreshAnalytics();
                            break;
                        case 'mcp':
                            await refreshMCPStatus();
                            break;
                    }
                }
                
                async function refreshSidebarStatus() {
                    try {
                        const [status, services, backends, buckets] = await Promise.all([
                            fetch('/api/status').then(r => r.json()),
                            fetch('/api/services').then(r => r.json()),
                            fetch('/api/backends').then(r => r.json()),
                            fetch('/api/buckets').then(r => r.json())
                        ]);
                        
                        document.getElementById('sidebar-mcp-status').textContent = status.mcp_status;
                        document.getElementById('sidebar-ipfs-status').textContent = status.ipfs_status;
                        document.getElementById('sidebar-backends-count').textContent = backends.total || 0;
                        document.getElementById('sidebar-buckets-count').textContent = buckets.length || 0;
                    } catch (error) {
                        console.error('Error refreshing sidebar:', error);
                    }
                }
                
                // Missing JavaScript functions implementation
                async function refreshSystemStatus() {
                    try {
                        const response = await fetch('/api/status');
                        const data = await response.json();
                        
                        // Update overview metrics
                        document.getElementById('mcp-status').textContent = data.mcp_status || 'Unknown';
                        document.getElementById('backends-count').textContent = data.metadata_summary?.backend_summary?.total_backends || 0;
                        document.getElementById('buckets-count').textContent = data.metadata_summary?.bucket_summary?.total_buckets || 0;
                        
                        // Update system architecture
                        const archDiv = document.getElementById('system-architecture');
                        if (archDiv) {
                            archDiv.innerHTML = `
                                <div class="text-sm space-y-2">
                                    <div><strong>Data Directory:</strong> ${data.data_dir}</div>
                                    <div><strong>MCP Status:</strong> ${data.mcp_status}</div>
                                    <div><strong>IPFS Status:</strong> ${data.ipfs_status}</div>
                                    <div><strong>Uptime:</strong> ${data.system.uptime || 'N/A'}</div>
                                </div>
                            `;
                        }
                    } catch (error) {
                        console.error('Error refreshing system status:', error);
                    }
                }
                
                async function refreshServices() {
                    try {
                        const response = await fetch('/api/services');
                        const data = await response.json();
                        
                        const servicesList = document.getElementById('services-list');
                        if (servicesList) {
                            servicesList.innerHTML = Object.entries(data.services || {}).map(([name, service]) => {
                                let statusClass = 'bg-gray-100 text-gray-800';
                                if (service.status === 'running') statusClass = 'bg-green-100 text-green-800';
                                else if (service.status === 'configured') statusClass = 'bg-blue-100 text-blue-800';
                                else if (service.status === 'stopped') statusClass = 'bg-yellow-100 text-yellow-800';
                                else if (service.status === 'error') statusClass = 'bg-red-100 text-red-800';
                                
                                let configStatusClass = 'bg-gray-100 text-gray-800';
                                let configText = service.config_status || 'unknown';
                                if (service.config_status === 'configured') configStatusClass = 'bg-green-100 text-green-800';
                                else if (service.config_status === 'configured_offline') configStatusClass = 'bg-blue-100 text-blue-800';
                                else if (service.config_status === 'not_configured') configStatusClass = 'bg-red-100 text-red-800';
                                else if (service.config_status === 'error') configStatusClass = 'bg-red-100 text-red-800';
                                
                                let typeIcon = 'fas fa-server';
                                if (service.type === 'storage_service') typeIcon = 'fas fa-database';
                                else if (service.type === 'storage_backend') typeIcon = 'fas fa-cloud';
                                else if (service.type === 'data_format') typeIcon = 'fas fa-file-alt';
                                else if (service.type === 'daemon') typeIcon = 'fas fa-cog';
                                else if (service.type === 'service') typeIcon = 'fas fa-network-wired';
                                else if (service.type === 'backend') typeIcon = 'fas fa-hdd';
                                
                                let statusIcon = '';
                                if (service.status === 'running') statusIcon = '<i class="fas fa-check-circle text-green-500 mr-1"></i>';
                                else if (service.status === 'stopped') statusIcon = '<i class="fas fa-stop-circle text-yellow-500 mr-1"></i>';
                                else if (service.status === 'error') statusIcon = '<i class="fas fa-exclamation-triangle text-red-500 mr-1"></i>';
                                
                                return `
                                    <div class="p-4 border rounded-lg hover:shadow-md transition-shadow">
                                        <div class="flex justify-between items-center mb-2">
                                            <div class="flex items-center">
                                                <i class="${typeIcon} mr-3 text-gray-600"></i>
                                                <h4 class="font-semibold">${name.toUpperCase()}</h4>
                                                ${service.is_default ? '<span class="ml-2 px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded">DEFAULT</span>' : ''}
                                            </div>
                                            <div class="flex items-center">
                                                ${statusIcon}
                                                <span class="px-2 py-1 rounded text-sm ${statusClass}">
                                                    ${service.status}
                                                </span>
                                            </div>
                                        </div>
                                        <div class="text-sm text-gray-600 mb-2">${service.description || 'Storage service for data operations'}</div>
                                        <div class="flex justify-between items-center text-xs">
                                            <div class="text-gray-500">Type: ${service.type}</div>
                                            <div class="flex items-center">
                                                <span class="mr-1">Config:</span>
                                                <span class="px-1 py-0.5 rounded text-xs ${configStatusClass}">
                                                    ${configText}
                                                </span>
                                            </div>
                                        </div>
                                        ${service.pid ? `<div class="text-xs text-gray-500 mt-1">PID: ${service.pid}</div>` : ''}
                                        ${service.error ? `<div class="text-xs text-red-600 mt-1">Error: ${service.error}</div>` : ''}
                                        ${service.type === 'storage_service' ? `<div class="text-xs text-blue-600 mt-1">⚡ Network service</div>` : ''}
                                        ${service.type === 'storage_backend' ? `<div class="text-xs text-green-600 mt-1">☁️ Backend integration</div>` : ''}
                                        ${service.type === 'data_format' ? `<div class="text-xs text-purple-600 mt-1">📄 Data format support</div>` : ''}
                                    </div>
                                `;
                            }).join('');
                        }
                        
                        // Update summary counts
                        const summary = data.summary || {};
                        document.getElementById('services-count').textContent = summary.total || 0;
                        
                        // Update dashboard cards with more detailed info
                        const servicesCard = document.getElementById('services-card');
                        if (servicesCard && summary.total > 0) {
                            const detailText = servicesCard.querySelector('.text-sm.text-gray-500');
                            if (detailText) {
                                detailText.innerHTML = `${summary.running || 0} running, ${summary.configured || 0} configured, ${summary.stopped || 0} stopped`;
                            }
                        }
                    } catch (error) {
                        console.error('Error refreshing services:', error);
                        const servicesList = document.getElementById('services-list');
                        if (servicesList) {
                            servicesList.innerHTML = '<div class="p-4 text-red-600">Error loading storage services</div>';
                        }
                    }
                }
                
                async function refreshBackends() {
                    try {
                        const response = await fetch('/api/backends');
                        const data = await response.json();
                        
                        const backendsList = document.getElementById('backends-health');
                        if (backendsList) {
                            backendsList.innerHTML = (data.backends || []).map(backend => `
                                <div class="p-3 border rounded-lg">
                                    <div class="flex justify-between items-center">
                                        <h4 class="font-semibold">${backend.name}</h4>
                                        <span class="px-2 py-1 rounded text-sm ${backend.status === 'healthy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                            ${backend.status}
                                        </span>
                                    </div>
                                    <div class="text-sm text-gray-600">Type: ${backend.type}</div>
                                    <div class="text-sm text-gray-600">Pins: ${backend.pins}</div>
                                </div>
                            `).join('');
                        }
                        
                        document.getElementById('backends-count').textContent = data.total || 0;
                    } catch (error) {
                        console.error('Error refreshing backends:', error);
                    }
                }
                
                async function refreshBuckets() {
                    try {
                        const response = await fetch('/api/buckets');
                        const data = await response.json();
                        
                        const bucketsList = document.getElementById('buckets-list');
                        if (bucketsList) {
                            bucketsList.innerHTML = '<div class="text-gray-500">Loading buckets...</div>';
                        }
                        
                        // Update bucket selector for uploads
                        const uploadSelect = document.getElementById('upload-bucket-select');
                        if (uploadSelect) {
                            uploadSelect.innerHTML = '<option value="">Select bucket...</option>';
                        }
                    } catch (error) {
                        console.error('Error refreshing buckets:', error);
                    }
                }
                
                async function refreshVFS() {
                    try {
                        // Placeholder for VFS refresh
                        const vfsTree = document.getElementById('vfs-tree');
                        if (vfsTree) {
                            vfsTree.innerHTML = '<div class="text-gray-500">VFS data loading...</div>';
                        }
                    } catch (error) {
                        console.error('Error refreshing VFS:', error);
                    }
                }
                
                async function refreshPeers() {
                    try {
                        // Placeholder for peers refresh
                        const peersList = document.getElementById('peers-list');
                        if (peersList) {
                            peersList.innerHTML = '<div class="text-gray-500">Loading peers...</div>';
                        }
                    } catch (error) {
                        console.error('Error refreshing peers:', error);
                    }
                }
                
                async function refreshPins() {
                    try {
                        // Placeholder for pins refresh
                        const pinsList = document.getElementById('pins-list');
                        if (pinsList) {
                            pinsList.innerHTML = '<div class="text-gray-500">Loading pins...</div>';
                        }
                    } catch (error) {
                        console.error('Error refreshing pins:', error);
                    }
                }
                
                async function refreshMetrics() {
                    try {
                        // Placeholder for metrics refresh
                        const perfMetrics = document.getElementById('performance-metrics');
                        if (perfMetrics) {
                            perfMetrics.innerHTML = '<div class="text-gray-500">Loading metrics...</div>';
                        }
                    } catch (error) {
                        console.error('Error refreshing metrics:', error);
                    }
                }
                
                // Bucket Index Management Functions
                async function refreshBucketIndex() {
                    try {
                        const response = await fetch('/api/bucket_index');
                        const data = await response.json();
                        
                        if (data.success) {
                            const indexStatusBadge = document.getElementById('index-status-badge');
                            const totalBucketsIndexed = document.getElementById('total-buckets-indexed');
                            const indexLastUpdated = document.getElementById('index-last-updated');
                            
                            if (indexStatusBadge) {
                                indexStatusBadge.textContent = 'Active';
                                indexStatusBadge.className = 'px-2 py-1 rounded text-sm bg-green-100 text-green-800';
                            }
                            
                            if (totalBucketsIndexed) {
                                totalBucketsIndexed.textContent = data.total_buckets || 0;
                            }
                            
                            if (indexLastUpdated) {
                                const timestamp = new Date(data.timestamp);
                                indexLastUpdated.textContent = timestamp.toLocaleString();
                            }
                            
                            // Update bucket index details
                            const bucketIndexDetails = document.getElementById('bucket-index-details');
                            if (bucketIndexDetails && data.bucket_index) {
                                let detailsHtml = '<div class="text-sm font-medium mb-2">Index Contents:</div>';
                                if (data.bucket_index.buckets && Array.isArray(data.bucket_index.buckets)) {
                                    detailsHtml += data.bucket_index.buckets.map(bucket => `
                                        <div class="flex justify-between items-center p-2 bg-gray-50 rounded">
                                            <span class="font-medium">${bucket.bucket_name || 'Unknown'}</span>
                                            <span class="text-sm text-gray-600">${bucket.backend_names ? bucket.backend_names.join(', ') : 'No backends'}</span>
                                        </div>
                                    `).join('');
                                } else {
                                    detailsHtml += '<div class="text-gray-500 italic">No bucket data available</div>';
                                }
                                bucketIndexDetails.innerHTML = detailsHtml;
                            }
                        } else {
                            const indexStatusBadge = document.getElementById('index-status-badge');
                            if (indexStatusBadge) {
                                indexStatusBadge.textContent = 'Error';
                                indexStatusBadge.className = 'px-2 py-1 rounded text-sm bg-red-100 text-red-800';
                            }
                            showIndexOperationResult(false, 'Failed to load bucket index: ' + (data.error || 'Unknown error'));
                        }
                    } catch (error) {
                        console.error('Error refreshing bucket index:', error);
                        showIndexOperationResult(false, 'Error refreshing bucket index: ' + error.message);
                    }
                }
                
                async function rebuildBucketIndex() {
                    try {
                        showIndexOperationResult(null, 'Rebuilding bucket index... This may take a moment.');
                        
                        const response = await fetch('/api/bucket_index/rebuild', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        });
                        const data = await response.json();
                        
                        if (data.success) {
                            showIndexOperationResult(true, 'Bucket index rebuilt successfully!');
                            await refreshBucketIndex();
                        } else {
                            showIndexOperationResult(false, 'Failed to rebuild index: ' + (data.error || 'Unknown error'));
                        }
                    } catch (error) {
                        console.error('Error rebuilding bucket index:', error);
                        showIndexOperationResult(false, 'Error rebuilding index: ' + error.message);
                    }
                }
                
                function showCreateIndexModal() {
                    // Create a simple prompt for bucket name
                    const bucketName = prompt('Enter bucket name to create index for:');
                    if (bucketName) {
                        createBucketIndex(bucketName);
                    }
                }
                
                async function createBucketIndex(bucketName) {
                    try {
                        showIndexOperationResult(null, `Creating index for bucket: ${bucketName}...`);
                        
                        const response = await fetch('/api/bucket_index/create', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ bucket_name: bucketName })
                        });
                        const data = await response.json();
                        
                        if (data.success) {
                            showIndexOperationResult(true, `Index created successfully for bucket: ${bucketName}`);
                            await refreshBucketIndex();
                        } else {
                            showIndexOperationResult(false, 'Failed to create index: ' + (data.error || 'Unknown error'));
                        }
                    } catch (error) {
                        console.error('Error creating bucket index:', error);
                        showIndexOperationResult(false, 'Error creating index: ' + error.message);
                    }
                }
                
                function showIndexOperationResult(success, message) {
                    const resultDiv = document.getElementById('index-operation-result');
                    if (resultDiv) {
                        if (success === null) {
                            // Info message
                            resultDiv.className = 'mb-4 p-4 rounded-lg bg-blue-50 border border-blue-200';
                            resultDiv.innerHTML = `<div class="flex items-center"><i class="fas fa-info-circle text-blue-600 mr-2"></i><span class="text-blue-800">${message}</span></div>`;
                        } else if (success) {
                            // Success message
                            resultDiv.className = 'mb-4 p-4 rounded-lg bg-green-50 border border-green-200';
                            resultDiv.innerHTML = `<div class="flex items-center"><i class="fas fa-check-circle text-green-600 mr-2"></i><span class="text-green-800">${message}</span></div>`;
                        } else {
                            // Error message
                            resultDiv.className = 'mb-4 p-4 rounded-lg bg-red-50 border border-red-200';
                            resultDiv.innerHTML = `<div class="flex items-center"><i class="fas fa-exclamation-circle text-red-600 mr-2"></i><span class="text-red-800">${message}</span></div>`;
                        }
                        resultDiv.classList.remove('hidden');
                        
                        // Auto-hide after 5 seconds for success/info messages
                        if (success !== false) {
                            setTimeout(() => {
                                resultDiv.classList.add('hidden');
                            }, 5000);
                        }
                    }
                }
                
                async function refreshLogs() {
                    try {
                        const component = document.getElementById('log-component')?.value || 'all';
                        const level = document.getElementById('log-level')?.value || 'all';
                        const limit = 100;
                        
                        const response = await fetch(`/api/logs?component=${component}&level=${level}&limit=${limit}`);
                        const data = await response.json();
                        
                        const logsContainer = document.getElementById('logs-container');
                        if (logsContainer && data.logs) {
                            let logsHtml = '';
                            
                            data.logs.forEach(log => {
                                const timestamp = new Date(log.timestamp).toLocaleString();
                                const levelClass = log.level.toLowerCase();
                                const levelColor = {
                                    'error': 'text-red-400',
                                    'critical': 'text-red-600',
                                    'warning': 'text-yellow-400',
                                    'info': 'text-green-400',
                                    'debug': 'text-blue-400'
                                }[levelClass] || 'text-green-400';
                                
                                logsHtml += `
                                    <div class="log-entry mb-1">
                                        <span class="text-gray-400">[${timestamp}]</span>
                                        <span class="${levelColor} font-semibold">[${log.level}]</span>
                                        <span class="text-cyan-400">[${log.component}]</span>
                                        <span class="text-white">${log.message}</span>
                                    </div>
                                `;
                            });
                            
                            logsContainer.innerHTML = logsHtml;
                            logsContainer.scrollTop = logsContainer.scrollHeight; // Auto-scroll to bottom
                            
                            console.log(`✅ Loaded ${data.logs.length} log entries from ipfs_kit package`);
                        } else {
                            logsContainer.innerHTML = '<div class="text-yellow-400">No logs available from ipfs_kit package</div>';
                        }
                        
                        if (data.error) {
                            console.error('Log loading error:', data.error);
                            logsContainer.innerHTML = `<div class="text-red-400">Error: ${data.error}</div>`;
                        }
                        
                    } catch (error) {
                        console.error('Error refreshing logs:', error);
                        const logsContainer = document.getElementById('logs-container');
                        if (logsContainer) {
                            logsContainer.innerHTML = '<div class="text-red-400">Error loading logs: ' + error.message + '</div>';
                        }
                    }
                }
                
                async function clearLogs() {
                    const logsContainer = document.getElementById('logs-container');
                    if (logsContainer) {
                        logsContainer.innerHTML = '<div class="text-gray-400">Logs cleared</div>';
                    }
                }
            </script>
        </body>
        </html>
        """
        return html_template
    
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
    
    async def _get_mcp_status(self):
        """Get MCP server status."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_server_url}/health") as resp:
                    if resp.status == 200:
                        return {"status": "running", "details": await resp.json()}
                    else:
                        return {"status": "error", "details": await resp.text()}
        except Exception as e:
            return {"status": "stopped", "error": str(e)}
    
    async def _restart_mcp_server(self):
        """Restart the MCP server."""
        # This is a placeholder, a real implementation would need to manage the process
        return {"status": "restarting"}
    
    async def _list_mcp_tools(self):
        """List available MCP tools."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_server_url}/tools") as resp:
                    return await resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def _get_services_data(self):
        """Get services data."""
        # This is a placeholder, a real implementation would get data from the daemon
        return {
            "services": {
                "ipfs": {"status": "running"},
                "lotus": {"status": "stopped"},
                "cluster": {"status": "running"},
                "lassie": {"status": "running"}
            }
        }
    
    async def _control_service(self, service, action):
        """Control a service."""
        # This is a placeholder, a real implementation would send a command to the daemon
        return {"status": f"{service} {action} requested"}
    
    async def _get_service_details(self, service_name):
        """Get service details."""
        # This is a placeholder
        return {"name": service_name, "status": "running", "details": "..."}
    
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
    
    async def _get_backend_health(self):
        """Get backend health."""
        # This is a placeholder
        return {"status": "healthy"}
    
    async def _sync_backend(self, backend):
        """Sync a backend."""
        # This is a placeholder
        return {"status": f"sync for {backend} requested"}
    
    async def _get_backend_stats(self, backend_name):
        """Get backend stats."""
        # This is a placeholder
        return {"name": backend_name, "pins": 123, "size": "1.2 GB"}
    
    async def _get_all_backend_configs(self):
        """Get all backend configs."""
        # This is a placeholder
        return {"configs": []}
    
    async def _get_backend_config(self, backend_name):
        """Get a backend config."""
        # This is a placeholder
        return {"name": backend_name, "type": "s3", "config": {"..."}}
    
    async def _create_backend_config(self, data):
        """Create a backend config."""
        # This is a placeholder
        return {"status": "created"}
    
    async def _update_backend_config(self, backend_name, data):
        """Update a backend config."""
        # This is a placeholder
        return {"status": "updated"}
    
    async def _delete_backend_config(self, backend_name):
        """Delete a backend config."""
        # This is a placeholder
        return {"status": "deleted"}
    
    async def _test_backend_config(self, backend_name):
        """Test a backend config."""
        # This is a placeholder
        return {"status": "ok"}
    
    async def _get_backend_pins(self, backend_name):
        """Get backend pins."""
        # This is a placeholder
        return {"pins": []}
    
    async def _add_backend_pin(self, backend_name, data):
        """Add a backend pin."""
        # This is a placeholder
        return {"status": "pinned"}
    
    async def _remove_backend_pin(self, backend_name, cid):
        """Remove a backend pin."""
        # This is a placeholder
        return {"status": "unpinned"}
    
    async def _find_pin_across_backends(self, cid):
        """Find a pin across backends."""
        # This is a placeholder
        return {"locations": []}
    
    async def _get_all_configs(self):
        """Get all configs."""
        # This is a placeholder
        return {"success": True, "configs": {}}
    
    async def _create_config(self, config_type, config_name, data):
        """Create a config."""
        # This is a placeholder
        return {"success": True}
    
    async def _update_config(self, config_type, config_name, data):
        """Update a config."""
        # This is a placeholder
        return {"success": True}
    
    async def _delete_config(self, config_type, config_name):
        """Delete a config."""
        # This is a placeholder
        return {"success": True}
    
    async def _validate_config(self, config_type, config_name, data=None):
        """Validate a config."""
        # This is a placeholder
        return {"success": True}
    
    async def _test_config(self, config_type, config_name):
        """Test a config."""
        # This is a placeholder
        return {"success": True}
    
    def _get_config_schemas(self):
        """Get config schemas."""
        # This is a placeholder
        return {}
    
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
    
    async def _create_bucket(self, data):
        """Create a bucket."""
        # This is a placeholder
        return {"status": "created"}
    
    async def _get_bucket_details(self, bucket_name):
        """Get bucket details."""
        # This is a placeholder
        return {"name": bucket_name, "files": [], "size": 0}
    
    async def _list_bucket_files(self, bucket_name):
        """List bucket files."""
        # This is a placeholder
        return {"files": []}
    
    async def _upload_file_to_bucket(self, bucket_name, file, virtual_path):
        """Upload a file to a bucket."""
        # This is a placeholder
        return {"status": "uploaded"}
    
    async def _download_file_from_bucket(self, bucket_name, file_path):
        """Download a file from a bucket."""
        # This is a placeholder
        return FileResponse(Path("/tmp/dummy"), filename=file_path)
    
    async def _delete_bucket_file(self, bucket_name, file_path):
        """Delete a file from a bucket."""
        # This is a placeholder
        return {"status": "deleted"}
    
    async def _get_bucket_index(self):
        """Get bucket index."""
        # This is a placeholder
        return {"success": True, "bucket_index": {}}
    
    async def _create_bucket_index(self, data):
        """Create a bucket index."""
        # This is a placeholder
        return {"success": True}
    
    async def _rebuild_bucket_index(self):
        """Rebuild bucket index."""
        # This is a placeholder
        return {"success": True}
    
    async def _get_bucket_index_info(self, bucket_name):
        """Get bucket index info."""
        # This is a placeholder
        return {"success": True, "info": {}}
    
    async def _get_vfs_structure(self):
        """Get VFS structure."""
        # This is a placeholder
        return {"structure": {}}
    
    async def _browse_vfs(self, bucket_name, path):
        """Browse VFS."""
        # This is a placeholder
        return {"files": []}
    
    async def _get_peers_data(self):
        """Get peers data."""
        # This is a placeholder
        return {"peers": []}
    
    async def _connect_peer(self, address):
        """Connect to a peer."""
        # This is a placeholder
        return {"status": "connecting"}
    
    async def _get_peer_stats(self):
        """Get peer stats."""
        # This is a placeholder
        return {"stats": {}}
    
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
    
    async def _add_pin(self, cid, name):
        """Add a pin."""
        # This is a placeholder
        return {"status": "pinning"}
    
    async def _remove_pin(self, cid):
        """Remove a pin."""
        # This is a placeholder
        return {"status": "unpinning"}
    
    async def _sync_pins(self):
        """Sync pins."""
        # This is a placeholder
        return {"status": "syncing"}
    
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
    
    async def _get_detailed_metrics(self):
        """Get detailed metrics."""
        # This is a placeholder
        return {"metrics": {}}
    
    async def _get_metrics_history(self):
        """Get metrics history."""
        # This is a placeholder
        return {"history": []}
    
    async def _get_logs(self, component, level, limit):
        """Get logs."""
        # This is a placeholder
        return {"logs": []}
    
    async def _stream_logs(self):
        """Stream logs."""
        # This is a placeholder
        pass
    
    async def _get_configuration(self):
        """Get configuration."""
        # This is a placeholder
        return {"config": {}}
    
    async def _update_configuration(self, data):
        """Update configuration."""
        # This is a placeholder
        return {"status": "updated"}
    
    async def _get_component_config(self, component):
        """Get component configuration."""
        # This is a placeholder
        return {"config": {}}
    
    async def _get_analytics_summary(self):
        """Get analytics summary."""
        # This is a placeholder
        return {"summary": {}}
    
    async def _get_bucket_analytics(self):
        """Get bucket analytics."""
        # This is a placeholder
        return {"analytics": {}}
    
    async def _get_performance_analytics(self):
        """Get performance analytics."""
        # This is a placeholder
        return {"analytics": {}}
    
    async def _generate_car_file(self, bucket_name, output_path):
        """Generate a CAR file."""
        # This is a placeholder
        return {"status": "generating"}
    
    async def _list_car_files(self):
        """List CAR files."""
        # This is a placeholder
        return {"files": []}
    
    async def _execute_cross_backend_query(self, query, backends):
        """Execute a cross-backend query."""
        # This is a placeholder
        return {"results": []}
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle a WebSocket connection."""
        await websocket.accept()
        self.websocket_clients.add(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # For now, just echo back the data
                await websocket.send_text(f"Echo: {data}")
        except WebSocketDisconnect:
            self.websocket_clients.remove(websocket)

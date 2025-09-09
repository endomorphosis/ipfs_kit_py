#!/usr/bin/env python3
"""
Unified Comprehensive Dashboard

This dashboard integrates all features from the comprehensive dashboard
with the modern light initialization + bucket VFS architecture.
"""

import asyncio
import json
import logging
import logging.handlers
from collections import deque
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

# Light initialization imports with fallbacks
try:
    from ipfs_kit_py.unified_bucket_interface import UnifiedBucketInterface, BackendType
    from ipfs_kit_py.bucket_vfs_manager import BucketType, VFSStructureType, get_global_bucket_manager
    from ipfs_kit_py.enhanced_bucket_index import EnhancedBucketIndex
    from ipfs_kit_py.error import create_result_dict
    IPFS_KIT_AVAILABLE = True
except ImportError:
    print('⚠️ IPFS Kit components not available - using fallback mode')
    IPFS_KIT_AVAILABLE = False

# MCP server components with fallbacks
try:
    from ipfs_kit_py.mcp_server.server import MCPServer, MCPServerConfig
    from ipfs_kit_py.mcp_server.models.mcp_metadata_manager import MCPMetadataManager
    from ipfs_kit_py.mcp_server.services.mcp_daemon_service import MCPDaemonService
    from ipfs_kit_py.mcp_server.controllers.mcp_cli_controller import MCPCLIController
    from ipfs_kit_py.mcp_server.controllers.mcp_backend_controller import MCPBackendController
    from ipfs_kit_py.mcp_server.controllers.mcp_daemon_controller import MCPDaemonController
    from ipfs_kit_py.mcp_server.controllers.mcp_storage_controller import MCPStorageController
    from ipfs_kit_py.mcp_server.controllers.mcp_vfs_controller import MCPVFSController
    MCP_SERVER_AVAILABLE = True
except ImportError:
    print('⚠️ MCP Server components not available - using fallback mode')
    MCP_SERVER_AVAILABLE = False

logger = logging.getLogger(__name__)

class UnifiedDashboard:
    """
    Unified Comprehensive Dashboard with all features integrated.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the unified comprehensive dashboard."""
        self.config = config or {}
        self.host = self.config.get('host', '127.0.0.1')
        self.port = self.config.get('port', 8080)
        self.debug = self.config.get('debug', False)
        self.data_dir = Path(self.config.get('data_dir', '~/.ipfs_kit')).expanduser()
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.app = FastAPI(
            title="IPFS Kit - Unified Comprehensive Dashboard",
            description="Complete management interface with all features",
            version="3.0.0"
        )
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.initialize_components()
        self.setup_all_endpoints()
        
        logger.info("Unified Comprehensive Dashboard initialized")
        
    def initialize_components(self):
        """Initialize all components with light initialization fallbacks."""
        logger.info("Initializing components...")

    def setup_all_endpoints(self):
        """Setup ALL API endpoints from comprehensive dashboard."""
        self.setup_core_endpoints()
        self.setup_service_management_endpoints()
        self.setup_backend_management_endpoints()
        self.setup_bucket_operations_endpoints()
        self.setup_analytics_monitoring_endpoints()
        self.setup_pin_management_endpoints()
        self.setup_log_management_endpoints()
        self.setup_websocket_endpoints()
        
    def setup_core_endpoints(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            return """
            <!DOCTYPE html>
            <html>
                <head>
                    <title>IPFS Kit Unified Dashboard</title>
                </head>
                <body>
                    <h1>IPFS Kit Unified Dashboard</h1>
                    <h2>Services</h2>
                    <ul id="services"></ul>
                    <h2>Backends</h2>
                    <ul id="backends"></ul>
                    <h2>Buckets</h2>
                    <ul id="buckets"></ul>
                    <h2>Pins</h2>
                    <ul id="pins"></ul>
                    <h2>Logs</h2>
                    <ul id="logs"></ul>
                    <script>
                        const ws = new WebSocket("ws://localhost:8080/ws");
                        ws.onmessage = function(event) {
                            const messages = document.getElementById('logs')
                            const message = document.createElement('li')
                            const content = document.createTextNode(event.data)
                            message.appendChild(content)
                            messages.appendChild(message)
                        };
                        function get_services() {
                            fetch("/api/services").then(response => response.json()).then(data => {
                                const services = document.getElementById("services");
                                services.innerHTML = "";
                                for (const service in data) {
                                    const li = document.createElement("li");
                                    li.innerText = `${service}: ${data[service].status}`;
                                    services.appendChild(li);
                                }
                            });
                        }
                        function get_backends() {
                            fetch("/api/backends").then(response => response.json()).then(data => {
                                const backends = document.getElementById("backends");
                                backends.innerHTML = "";
                                for (const backend in data) {
                                    const li = document.createElement("li");
                                    li.innerText = `${backend}: ${data[backend].status}`;
                                    backends.appendChild(li);
                                }
                            });
                        }
                        function get_buckets() {
                            fetch("/api/buckets").then(response => response.json()).then(data => {
                                const buckets = document.getElementById("buckets");
                                buckets.innerHTML = "";
                                for (const bucket in data) {
                                    const li = document.createElement("li");
                                    li.innerText = `${bucket}: ${data[bucket].status}`;
                                    buckets.appendChild(li);
                                }
                            });
                        }
                        function get_pins() {
                            fetch("/api/pins").then(response => response.json()).then(data => {
                                const pins = document.getElementById("pins");
                                pins.innerHTML = "";
                                for (const pin in data) {
                                    const li = document.createElement("li");
                                    li.innerText = `${pin}: ${data[pin].cid}`;
                                    pins.appendChild(li);
                                }
                            });
                        }
                        function get_logs() {
                            fetch("/api/logs").then(response => response.json()).then(data => {
                                const logs = document.getElementById("logs");
                                logs.innerHTML = "";
                                for (const log of data) {
                                    const li = document.createElement("li");
                                    li.innerText = log;
                                    logs.appendChild(li);
                                }
                            });
                        }
                        setInterval(() => {
                            get_services();
                            get_backends();
                            get_buckets();
                            get_pins();
                            get_logs();
                        }, 1000);
                    </script>
                </body>
            </html>
            """

    def setup_service_management_endpoints(self):
        self.service_status_cache = {}

        @self.app.get("/api/services")
        async def get_services():
            return self.service_status_cache

        @self.app.get("/api/services/{service_name}")
        async def get_service(service_name: str):
            return self.service_status_cache.get(service_name, {"status": "not_found"})

        @self.app.post("/api/services/{service_name}/start")
        async def start_service(service_name: str):
            # Add logic to start the service here
            self.service_status_cache[service_name] = {"status": "running"}
            return self.service_status_cache[service_name]

        @self.app.post("/api/services/{service_name}/stop")
        async def stop_service(service_name: str):
            # Add logic to stop the service here
            self.service_status_cache[service_name] = {"status": "stopped"}
            return self.service_status_cache[service_name]

        @self.app.post("/api/services/{service_name}/restart")
        async def restart_service(service_name: str):
            # Add logic to restart the service here
            self.service_status_cache[service_name] = {"status": "restarting"}
            await asyncio.sleep(2)  # Simulate restart
            self.service_status_cache[service_name] = {"status": "running"}
            return self.service_status_cache[service_name]

    def setup_backend_management_endpoints(self):
        self.backend_status_cache = {}

        @self.app.get("/api/backends")
        async def get_backends():
            return self.backend_status_cache

        @self.app.get("/api/backends/{backend_name}")
        async def get_backend(backend_name: str):
            return self.backend_status_cache.get(backend_name, {"status": "not_found"})

        @self.app.post("/api/backends/{backend_name}/health")
        async def get_backend_health(backend_name: str):
            # Add logic to check backend health here
            return {"status": "healthy"}

    def setup_bucket_operations_endpoints(self):
        self.buckets = {}

        @self.app.get("/api/buckets")
        async def list_buckets():
            return self.buckets

        @self.app.post("/api/buckets/{bucket_name}")
        async def create_bucket(bucket_name: str):
            self.buckets[bucket_name] = {"status": "created", "files": {}}
            return self.buckets[bucket_name]

        @self.app.get("/api/buckets/{bucket_name}")
        async def get_bucket(bucket_name: str):
            return self.buckets.get(bucket_name, {"status": "not_found"})

    def setup_analytics_monitoring_endpoints(self):
        @self.app.get("/api/analytics/system")
        async def get_system_analytics():
            return {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent
            }

    def setup_pin_management_endpoints(self):
        self.pins = {}

        @self.app.get("/api/pins")
        async def list_pins():
            return self.pins

        @self.app.post("/api/pins/{pin_name}")
        async def create_pin(pin_name: str, cid: str):
            self.pins[pin_name] = {"cid": cid, "status": "pinned"}
            return self.pins[pin_name]

        @self.app.get("/api/pins/{pin_name}")
        async def get_pin(pin_name: str):
            return self.pins.get(pin_name, {"status": "not_found"})

        @self.app.delete("/api/pins/{pin_name}")
        async def remove_pin(pin_name: str):
            if pin_name in self.pins:
                del self.pins[pin_name]
                return {"status": "removed"}
            return {"status": "not_found"}

    def setup_log_management_endpoints(self):
        self.logs = deque(maxlen=1000)

        @self.app.get("/api/logs")
        async def get_logs():
            return list(self.logs)

        @self.app.post("/api/logs")
        async def add_log_entry(entry: str):
            self.logs.append(entry)
            return {"status": "log_added"}

    def setup_websocket_endpoints(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_text()
                    await websocket.send_text(f"Message text was: {data}")
            except WebSocketDisconnect:
                pass

    def run(self):
        """Run the dashboard server."""
        uvicorn.run(self.app, host=self.host, port=self.port)

if __name__ == '__main__':
    dashboard = UnifiedDashboard()
    dashboard.run()

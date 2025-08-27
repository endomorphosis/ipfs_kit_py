#!/usr/bin/env python3
"""
Simple test script to verify the enhanced MCP dashboard functionality.
This script tests the dashboard without complex imports.
"""

import json
import logging
import time
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Web framework imports
try:
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    print("✓ FastAPI imports successful")
except ImportError as e:
    print(f"✗ FastAPI import error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class SimplifiedMCPDashboard:
    """
    Simplified MCP Dashboard for testing the enhanced functionality.
    """
    
    def __init__(self, port: int = 8005):
        self.port = port
        self.data_dir = Path.home() / ".ipfs_kit"
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="IPFS Kit - Enhanced MCP Dashboard Test",
            version="4.1.0",
            description="Testing enhanced MCP dashboard functionality"
        )
        
        # Setup routes
        self._setup_routes()
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup test API routes for MCP functionality."""
        
        @self.app.get("/")
        async def dashboard_home(request: Request):
            """Serve the main dashboard."""
            # For testing, return a simple HTML page
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Enhanced MCP Dashboard - Test</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .success { color: green; }
                    .error { color: red; }
                    .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
                    button { padding: 10px 15px; margin: 5px; cursor: pointer; }
                </style>
            </head>
            <body>
                <h1>Enhanced MCP Dashboard - Test</h1>
                <p class="success">✓ Dashboard is running successfully!</p>
                
                <div class="section">
                    <h2>MCP Server Tools</h2>
                    <p>Test the new MCP tools functionality:</p>
                    <button onclick="testMcpTools()">Load MCP Tools</button>
                    <div id="mcp-tools-result"></div>
                </div>
                
                <div class="section">
                    <h2>Virtual Filesystem</h2>
                    <p>Test VFS bucket management:</p>
                    <button onclick="testVfsBuckets()">Load VFS Buckets</button>
                    <div id="vfs-buckets-result"></div>
                </div>
                
                <div class="section">
                    <h2>Program State Management</h2>
                    <p>Test configuration file management:</p>
                    <button onclick="testConfigFiles()">Load Config Files</button>
                    <div id="config-files-result"></div>
                </div>
                
                <div class="section">
                    <h2>Daemon Management</h2>
                    <p>Test enhanced daemon controls:</p>
                    <button onclick="testDaemonStatus()">Load Daemon Status</button>
                    <div id="daemon-status-result"></div>
                </div>
                
                <script>
                    async function testMcpTools() {
                        const resultDiv = document.getElementById('mcp-tools-result');
                        resultDiv.innerHTML = 'Loading...';
                        
                        try {
                            const response = await fetch('/api/mcp/tools');
                            const data = await response.json();
                            
                            if (data.success) {
                                resultDiv.innerHTML = `
                                    <p class="success">✓ Successfully loaded ${data.tools.length} MCP tools:</p>
                                    <ul>${data.tools.map(tool => `<li>${tool.name} (${tool.category})</li>`).join('')}</ul>
                                `;
                            } else {
                                resultDiv.innerHTML = `<p class="error">✗ Error: ${data.error}</p>`;
                            }
                        } catch (error) {
                            resultDiv.innerHTML = `<p class="error">✗ Network error: ${error.message}</p>`;
                        }
                    }
                    
                    async function testVfsBuckets() {
                        const resultDiv = document.getElementById('vfs-buckets-result');
                        resultDiv.innerHTML = 'Loading...';
                        
                        try {
                            const response = await fetch('/api/mcp/vfs/buckets');
                            const data = await response.json();
                            
                            if (data.success) {
                                resultDiv.innerHTML = `
                                    <p class="success">✓ Successfully loaded ${data.buckets.length} VFS buckets:</p>
                                    <ul>${data.buckets.map(bucket => `<li>${bucket.name} (${bucket.backend}) - ${bucket.itemCount} items</li>`).join('')}</ul>
                                `;
                            } else {
                                resultDiv.innerHTML = `<p class="error">✗ Error: ${data.error}</p>`;
                            }
                        } catch (error) {
                            resultDiv.innerHTML = `<p class="error">✗ Network error: ${error.message}</p>`;
                        }
                    }
                    
                    async function testConfigFiles() {
                        const resultDiv = document.getElementById('config-files-result');
                        resultDiv.innerHTML = 'Loading...';
                        
                        try {
                            const configTypes = ['config', 'peers', 'keys'];
                            const results = [];
                            
                            for (const configType of configTypes) {
                                const response = await fetch(`/api/mcp/config/${configType}`);
                                const data = await response.json();
                                results.push({
                                    type: configType,
                                    success: data.success,
                                    filename: data.filename,
                                    exists: data.exists
                                });
                            }
                            
                            resultDiv.innerHTML = `
                                <p class="success">✓ Configuration files status:</p>
                                <ul>${results.map(r => `<li>${r.filename}: ${r.success ? (r.exists ? 'Exists' : 'Default') : 'Error'}</li>`).join('')}</ul>
                            `;
                        } catch (error) {
                            resultDiv.innerHTML = `<p class="error">✗ Network error: ${error.message}</p>`;
                        }
                    }
                    
                    async function testDaemonStatus() {
                        const resultDiv = document.getElementById('daemon-status-result');
                        resultDiv.innerHTML = 'Loading...';
                        
                        try {
                            const response = await fetch('/api/mcp/daemon/status');
                            const data = await response.json();
                            
                            if (data.success) {
                                const services = data.services;
                                const serviceList = Object.entries(services).map(([name, info]) => 
                                    `<li>${name}: ${info.status} (last run: ${info.last_run || 'Never'})</li>`
                                ).join('');
                                
                                resultDiv.innerHTML = `
                                    <p class="success">✓ Daemon services status:</p>
                                    <ul>${serviceList}</ul>
                                `;
                            } else {
                                resultDiv.innerHTML = `<p class="error">✗ Error: ${data.error}</p>`;
                            }
                        } catch (error) {
                            resultDiv.innerHTML = `<p class="error">✗ Network error: ${error.message}</p>`;
                        }
                    }
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)

        # MCP Tools API
        @self.app.get("/api/mcp/tools")
        async def api_get_mcp_tools():
            """Get list of available MCP tools."""
            try:
                tools = [
                    {
                        "name": "ipfs_add",
                        "category": "IPFS Core",
                        "description": "Add files or directories to IPFS network",
                        "status": "active"
                    },
                    {
                        "name": "ipfs_cat",
                        "category": "IPFS Core", 
                        "description": "Retrieve content from IPFS by CID",
                        "status": "active"
                    },
                    {
                        "name": "storage_transfer",
                        "category": "Storage Management",
                        "description": "Transfer data between storage backends",
                        "status": "active"
                    },
                    {
                        "name": "pin_sync",
                        "category": "Pin Management",
                        "description": "Synchronize pins across IPFS cluster",
                        "status": "active"
                    },
                    {
                        "name": "file_indexer",
                        "category": "Data Management",
                        "description": "Index files for search and metadata",
                        "status": "active"
                    },
                    {
                        "name": "garbage_collector",
                        "category": "Maintenance",
                        "description": "Clean up unused data blocks",
                        "status": "active"
                    }
                ]
                return {"success": True, "tools": tools}
            except Exception as e:
                logger.error(f"Error getting MCP tools: {e}")
                return {"success": False, "error": str(e)}

        # VFS Buckets API
        @self.app.get("/api/mcp/vfs/buckets")
        async def api_get_vfs_buckets():
            """Get virtual filesystem buckets."""
            try:
                buckets = [
                    {
                        "name": "ipfs-main",
                        "backend": "IPFS",
                        "type": "ipfs",
                        "itemCount": 1247,
                        "totalSize": 2147483648,
                        "status": "active",
                        "created": (datetime.now() - timedelta(days=30)).isoformat()
                    },
                    {
                        "name": "s3-backup",
                        "backend": "S3 Compatible",
                        "type": "s3",
                        "itemCount": 523,
                        "totalSize": 1073741824,
                        "status": "active",
                        "created": (datetime.now() - timedelta(days=15)).isoformat()
                    },
                    {
                        "name": "hf-models",
                        "backend": "HuggingFace",
                        "type": "huggingface",
                        "itemCount": 89,
                        "totalSize": 536870912,
                        "status": "active",
                        "created": (datetime.now() - timedelta(days=7)).isoformat()
                    }
                ]
                
                return {"success": True, "buckets": buckets}
                
            except Exception as e:
                logger.error(f"Error getting VFS buckets: {e}")
                return {"success": False, "error": str(e)}

        # Configuration Files API
        @self.app.get("/api/mcp/config/{config_type}")
        async def api_get_config_file(config_type: str):
            """Get configuration file content."""
            try:
                config_files = {
                    "config": "config.yaml",
                    "peers": "peers.json", 
                    "keys": "keys.json"
                }
                
                if config_type not in config_files:
                    return {"success": False, "error": f"Unknown config type: {config_type}"}
                
                filename = config_files[config_type]
                config_path = self.data_dir / filename
                
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        content = f.read()
                    exists = True
                else:
                    # Return default content
                    default_content = {
                        "config": "# IPFS Kit Configuration\\nipfs:\\n  api_port: 5001",
                        "peers": '{"bootstrap_peers": [], "trusted_peers": [], "blocked_peers": []}',
                        "keys": '{"peer_id": "QmYourPeerIDHere", "private_key": "..."}'
                    }
                    content = default_content.get(config_type, "")
                    exists = False
                
                return {
                    "success": True,
                    "filename": filename,
                    "content": content,
                    "exists": exists
                }
                
            except Exception as e:
                logger.error(f"Error getting config file {config_type}: {e}")
                return {"success": False, "error": str(e)}

        # Daemon Status API
        @self.app.get("/api/mcp/daemon/status")
        async def api_get_daemon_status():
            """Get daemon services status."""
            try:
                status = {
                    "file_indexer": {
                        "status": "stopped",
                        "last_run": None,
                        "file_count": 0,
                        "enabled": True
                    },
                    "pin_sync": {
                        "status": "running",
                        "last_run": datetime.now().isoformat(),
                        "sync_count": 1247,
                        "enabled": True
                    },
                    "garbage_collector": {
                        "status": "stopped",
                        "last_run": (datetime.now() - timedelta(hours=24)).isoformat(),
                        "freed_space": 1073741824,
                        "enabled": False
                    }
                }
                
                return {"success": True, "services": status}
                
            except Exception as e:
                logger.error(f"Error getting daemon status: {e}")
                return {"success": False, "error": str(e)}

        # Health check
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "4.1.0-test",
                "enhanced_mcp": True
            }
    
    def run(self):
        """Run the test dashboard."""
        print(f"🚀 Starting Enhanced MCP Dashboard Test on port {self.port}")
        print(f"📁 Data directory: {self.data_dir}")
        print(f"🌐 Open http://localhost:{self.port} to test the dashboard")
        
        uvicorn.run(
            self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="info"
        )

def main():
    """Main entry point for the test dashboard."""
    print("Enhanced MCP Dashboard - Test Mode")
    print("===================================")
    
    # Create and run test dashboard
    dashboard = SimplifiedMCPDashboard(port=8005)
    dashboard.run()

if __name__ == "__main__":
    main()

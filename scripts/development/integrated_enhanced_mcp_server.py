#!/usr/bin/env python3
"""
Integrated Enhanced MCP Server

This module provides a comprehensive MCP server that integrates:
1. Enhanced storage backend management
2. Comprehensive dashboard with service management
3. Real-time monitoring and health checks
4. Daemon management capabilities
5. Configuration management

This fixes the issues with the MCP server dashboard by ensuring:
- All storage backends and daemons are properly identified
- Services panel correctly shows all available backends
- Management operations (start/stop/restart/configure) work properly
- Real-time status updates and monitoring
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

# Import our enhanced components
from enhanced_storage_backend_manager import get_backend_manager, EnhancedStorageBackendManager
from enhanced_mcp_server_dashboard import EnhancedMCPDashboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegratedEnhancedMCPServer:
    """
    Integrated Enhanced MCP Server with comprehensive dashboard and backend management.
    
    This server provides:
    1. Complete storage backend management (IPFS, S3, Filecoin, Storacha, HuggingFace, Lassie, Local)
    2. Daemon management (IPFS daemon, Lotus daemon, Aria2 daemon, etc.)
    3. Real-time dashboard with WebSocket updates
    4. Service control operations (start/stop/restart/configure)
    5. Health monitoring and status reporting
    6. Configuration management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the integrated MCP server."""
        self.config = config or {}
        self.host = self.config.get('host', '127.0.0.1')
        self.port = self.config.get('port', 9991)
        self.debug = self.config.get('debug', False)
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="Integrated Enhanced MCP Server",
            description="Comprehensive MCP server with storage backend and daemon management",
            version="1.0.0"
        )
        
        # Initialize components
        self.backend_manager = get_backend_manager()
        self.dashboard = EnhancedMCPDashboard(host=self.host, port=self.port)
        
        # Setup server
        self._setup_middleware()
        self._setup_routes()
        
        # Server state
        self.start_time = time.time()
        self.is_running = False
        
    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        # Health and status endpoints
        @self.app.get("/api/v0/health")
        async def health_check():
            """Comprehensive health check endpoint."""
            try:
                # Check backend health
                backend_health = await self.backend_manager.check_all_backends_health()
                
                # Get service statuses from dashboard
                await self.dashboard._update_all_services()
                service_statuses = {name: service.model_dump() for name, service in self.dashboard.services.items()}
                
                # Count statuses
                total_backends = len(backend_health)
                healthy_backends = sum(1 for h in backend_health.values() if h.get("success", False))
                
                total_services = len(service_statuses)
                running_services = sum(1 for s in service_statuses.values() if s["status"] == "running")
                error_services = sum(1 for s in service_statuses.values() if s["status"] == "error")
                
                overall_status = "healthy"
                if error_services > 0 or healthy_backends < total_backends // 2:
                    overall_status = "degraded"
                if healthy_backends == 0:
                    overall_status = "unhealthy"
                
                return {
                    "success": True,
                    "status": overall_status,
                    "timestamp": datetime.now().isoformat(),
                    "uptime": time.time() - self.start_time,
                    "components": {
                        "backends": backend_health,
                        "services": service_statuses
                    },
                    "summary": {
                        "total_backends": total_backends,
                        "healthy_backends": healthy_backends,
                        "total_services": total_services,
                        "running_services": running_services,
                        "error_services": error_services
                    },
                    "controllers": {
                        "storage_manager": {
                            "status": "running",
                            "backend_count": len(self.backend_manager.backends)
                        },
                        "dashboard": {
                            "status": "running",
                            "service_count": len(self.dashboard.services)
                        }
                    }
                }
                
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {
                    "success": False,
                    "status": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }
        
        @self.app.get("/api/v0/storage/health")
        async def storage_health():
            """Storage backends health check."""
            try:
                backend_health = await self.backend_manager.check_all_backends_health()
                
                # Format for compatibility with existing code
                components = {}
                for backend_name, health in backend_health.items():
                    status = "running" if health.get("success", False) else "error"
                    components[backend_name] = {
                        "status": status,
                        "available": health.get("success", False),
                        "simulation": False,  # We're using real implementations
                        "error": health.get("error"),
                        "details": health.get("details", {}),
                        "last_check": datetime.now().isoformat()
                    }
                
                return {
                    "success": True,
                    "components": components,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Storage health check failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        # Backend management endpoints
        @self.app.get("/api/v0/storage/backends")
        async def list_backends():
            """List all storage backends."""
            return self.backend_manager.get_all_backend_statuses()
        
        @self.app.get("/api/v0/storage/backends/{backend_name}")
        async def get_backend_status(backend_name: str):
            """Get specific backend status."""
            status = await self.backend_manager.get_backend_status(backend_name)
            if "error" in status:
                raise HTTPException(status_code=404, detail=status["error"])
            return status
        
        @self.app.post("/api/v0/storage/backends/{backend_name}/start")
        async def start_backend(backend_name: str):
            """Start a storage backend."""
            result = await self.backend_manager.start_backend(backend_name)
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to start backend"))
            return result
        
        @self.app.post("/api/v0/storage/backends/{backend_name}/stop")
        async def stop_backend(backend_name: str):
            """Stop a storage backend."""
            result = await self.backend_manager.stop_backend(backend_name)
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to stop backend"))
            return result
        
        @self.app.post("/api/v0/storage/backends/{backend_name}/restart")
        async def restart_backend(backend_name: str):
            """Restart a storage backend."""
            result = await self.backend_manager.restart_backend(backend_name)
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to restart backend"))
            return result
        
        @self.app.post("/api/v0/storage/backends/{backend_name}/configure")
        async def configure_backend(backend_name: str, config: Dict[str, Any]):
            """Configure a storage backend."""
            result = await self.backend_manager.configure_backend(backend_name, config)
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to configure backend"))
            return result
        
        # Service management endpoints (delegated to dashboard)
        @self.app.get("/api/services")
        async def get_services():
            """Get all service statuses."""
            await self.dashboard._update_all_services()
            return {"services": {name: service.model_dump() for name, service in self.dashboard.services.items()}}
        
        @self.app.get("/api/services/{service_name}")
        async def get_service(service_name: str):
            """Get specific service status."""
            if service_name not in self.dashboard.services:
                raise HTTPException(status_code=404, detail="Service not found")
            await self.dashboard._update_service_status(service_name)
            return self.dashboard.services[service_name].model_dump()
        
        @self.app.post("/api/services/{service_name}/action")
        async def service_action(service_name: str, action_data: Dict[str, Any]):
            """Perform action on service."""
            if service_name not in self.dashboard.services:
                raise HTTPException(status_code=404, detail="Service not found")
            
            action = action_data.get("action")
            parameters = action_data.get("parameters")
            
            result = await self.dashboard._perform_service_action(service_name, action, parameters)
            await self.dashboard._update_service_status(service_name)
            await self.dashboard._broadcast_service_update(service_name)
            
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Action failed"))
            
            return result
        
        # Daemon management endpoints
        @self.app.post("/api/v0/daemons/{daemon_type}/start")
        async def start_daemon(daemon_type: str):
            """Start a daemon."""
            # Valid daemon types
            valid_types = ['ipfs', 'lotus', 'aria2', 'ipfs_cluster']
            if daemon_type not in valid_types:
                raise HTTPException(status_code=400, detail=f"Invalid daemon type. Must be one of: {', '.join(valid_types)}")
            
            # Use the dashboard's service action mechanism
            result = await self.dashboard._perform_service_action(daemon_type, "start")
            
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to start daemon"))
            
            return result
        
        @self.app.post("/api/v0/daemons/{daemon_type}/stop")
        async def stop_daemon(daemon_type: str):
            """Stop a daemon."""
            valid_types = ['ipfs', 'lotus', 'aria2', 'ipfs_cluster']
            if daemon_type not in valid_types:
                raise HTTPException(status_code=400, detail=f"Invalid daemon type. Must be one of: {', '.join(valid_types)}")
            
            result = await self.dashboard._perform_service_action(daemon_type, "stop")
            
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to stop daemon"))
            
            return result
        
        @self.app.post("/api/v0/daemons/{daemon_type}/restart")
        async def restart_daemon(daemon_type: str):
            """Restart a daemon."""
            valid_types = ['ipfs', 'lotus', 'aria2', 'ipfs_cluster']
            if daemon_type not in valid_types:
                raise HTTPException(status_code=400, detail=f"Invalid daemon type. Must be one of: {', '.join(valid_types)}")
            
            result = await self.dashboard._perform_service_action(daemon_type, "restart")
            
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to restart daemon"))
            
            return result
        
        # Dashboard endpoints (delegated to dashboard component)
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Serve the main dashboard page."""
            return self.dashboard._get_dashboard_html()
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.dashboard.websocket_connections.add(websocket)
            
            try:
                # Send initial data
                await self.dashboard._update_all_services()
                await websocket.send_json({
                    "type": "services_update",
                    "data": {name: service.model_dump() for name, service in self.dashboard.services.items()}
                })
                
                # Keep connection alive
                while True:
                    await websocket.receive_text()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.dashboard.websocket_connections.discard(websocket)
        
        # Configuration endpoints
        @self.app.get("/api/v0/config")
        async def get_config():
            """Get server configuration."""
            return {
                "server": {
                    "host": self.host,
                    "port": self.port,
                    "debug": self.debug,
                    "uptime": time.time() - self.start_time
                },
                "backends": self.backend_manager.config,
                "dashboard": {
                    "enabled": True,
                    "websocket_connections": len(self.dashboard.websocket_connections)
                }
            }
        
        @self.app.post("/api/v0/config")
        async def update_config(config_data: Dict[str, Any]):
            """Update server configuration."""
            try:
                # Update backend configuration
                if "backends" in config_data:
                    for backend_name, backend_config in config_data["backends"].items():
                        if backend_name in self.backend_manager.backends:
                            await self.backend_manager.configure_backend(backend_name, backend_config)
                
                # Update server configuration
                if "server" in config_data:
                    server_config = config_data["server"]
                    # Note: Some config changes require restart
                    self.config.update(server_config)
                
                return {"success": True, "message": "Configuration updated"}
                
            except Exception as e:
                logger.error(f"Failed to update configuration: {e}")
                raise HTTPException(status_code=400, detail=str(e))
    
    async def start_background_tasks(self):
        """Start background monitoring and health check tasks."""
        
        async def health_check_loop():
            """Background health checking."""
            while self.is_running:
                try:
                    # Check backend health
                    await self.backend_manager.check_all_backends_health()
                    
                    # Update dashboard services
                    await self.dashboard._update_all_services()
                    
                    # Wait before next check
                    await asyncio.sleep(30)  # Check every 30 seconds
                    
                except Exception as e:
                    logger.error(f"Error in health check loop: {e}")
                    await asyncio.sleep(60)  # Wait longer on error
        
        # Start background tasks
        self.health_check_task = asyncio.create_task(health_check_loop())
        self.dashboard_monitoring_task = await self.dashboard.start_monitoring()
        
    async def stop_background_tasks(self):
        """Stop background tasks."""
        self.is_running = False
        
        if hasattr(self, 'health_check_task'):
            self.health_check_task.cancel()
            
        if hasattr(self.dashboard, 'monitoring_task'):
            self.dashboard.monitoring_task.cancel()
    
    async def start(self):
        """Start the integrated MCP server."""
        logger.info(f"Starting Integrated Enhanced MCP Server on {self.host}:{self.port}")
        
        self.is_running = True
        
        # Start background tasks
        await self.start_background_tasks()
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the FastAPI server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info"
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the integrated MCP server."""
        logger.info("Stopping Integrated Enhanced MCP Server...")
        await self.stop_background_tasks()
        logger.info("Server stopped")


async def main():
    """Main function to run the integrated MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Enhanced MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9991, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--config", help="Path to configuration file")
    args = parser.parse_args()
    
    # Load configuration
    config = {
        "host": args.host,
        "port": args.port,
        "debug": args.debug
    }
    
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            logger.error(f"Failed to load config file {args.config}: {e}")
    
    # Create and start server
    server = IntegratedEnhancedMCPServer(config)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
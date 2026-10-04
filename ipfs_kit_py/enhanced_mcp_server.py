"""
Enhanced MCP Server with Service Management

This module provides an enhanced MCP server that supports service management,
monitoring, and uses the metadata-first approach.
"""

import logging
import anyio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .metadata_manager import get_metadata_manager
from .service_registry import get_service_registry
from .mcp_metadata_wrapper import get_enhanced_mcp_tools

logger = logging.getLogger(__name__)


class EnhancedMCPServer:
    """
    Enhanced MCP Server with service management capabilities.
    
    This server provides:
    - Service management API endpoints
    - Monitoring and statistics endpoints
    - Metadata-first approach for all operations
    - Dashboard integration support
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8004):
        self.host = host
        self.port = port
        self.app = FastAPI(title="IPFS Kit MCP Server", version="1.0.0")
        
        self.metadata_manager = get_metadata_manager()
        self.service_registry = get_service_registry()
        self.mcp_tools = get_enhanced_mcp_tools()
        
        self._setup_middleware()
        self._setup_routes()
    
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
        """Setup API routes."""
        # Static files
        from fastapi.staticfiles import StaticFiles
        from pathlib import Path
        
        static_path = Path(__file__).parent.parent / "static"
        if static_path.exists():
            self.app.mount("/static", StaticFiles(directory=static_path), name="static")
        
        # Service management endpoints
        self.app.post("/api/services/add")(self.add_service)
        self.app.delete("/api/services/{service_name}")(self.remove_service)
        self.app.get("/api/services/list")(self.list_services)
        self.app.get("/api/services/status")(self.get_all_services_status)
        self.app.get("/api/services/{service_name}/status")(self.get_service_status)
        self.app.post("/api/services/{service_name}/start")(self.start_service)
        self.app.post("/api/services/{service_name}/stop")(self.stop_service)
        self.app.get("/api/services/{service_name}/config")(self.get_service_config)
        self.app.put("/api/services/{service_name}/config")(self.update_service_config)
        self.app.get("/api/services/{service_name}/stats")(self.get_service_stats)
        self.app.get("/api/services/{service_name}/quota")(self.get_service_quota)
        self.app.get("/api/services/{service_name}/storage")(self.get_service_storage)
        
        # Monitoring endpoints
        self.app.get("/api/monitoring/{service_name}")(self.get_monitoring_data)
        self.app.get("/api/monitoring/{service_name}/{metric_type}")(self.get_monitoring_data)
        
        # Backend statistics
        self.app.get("/api/backends/stats")(self.get_backend_stats)
        
        # System endpoints
        self.app.get("/api/mcp/status")(self.get_mcp_status)
        self.app.get("/api/system/health")(self.get_system_health)
        
        # Dashboard endpoint
        self.app.get("/")(self.dashboard_index)
    
    async def add_service(self, request: Request):
        """Add a new service."""
        try:
            data = await request.json()
            service_name = data.get("name")
            config = data.get("config", {})
            
            if not service_name:
                raise HTTPException(status_code=400, detail="Service name is required")
            
            success = await self.service_registry.add_service(service_name, config)
            if success:
                return {"success": True, "message": f"Service {service_name} added"}
            else:
                raise HTTPException(status_code=400, detail="Failed to add service")
                
        except Exception as e:
            logger.error(f"Error adding service: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def remove_service(self, service_name: str):
        """Remove a service."""
        try:
            success = await self.service_registry.remove_service(service_name)
            if success:
                return {"success": True, "message": f"Service {service_name} removed"}
            else:
                raise HTTPException(status_code=404, detail="Service not found")
                
        except Exception as e:
            logger.error(f"Error removing service {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def list_services(self):
        """List all services."""
        try:
            services = await self.service_registry.list_services()
            available_types = self.service_registry.get_available_service_types()
            return {
                "services": services,
                "available_types": available_types
            }
        except Exception as e:
            logger.error(f"Error listing services: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_all_services_status(self):
        """Get status of all services."""
        try:
            return await self.service_registry.get_all_service_status()
        except Exception as e:
            logger.error(f"Error getting all services status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_service_status(self, service_name: str):
        """Get status of a specific service."""
        try:
            status = await self.service_registry.get_service_status(service_name)
            if status is None:
                raise HTTPException(status_code=404, detail="Service not found")
            return status
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting service status for {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def start_service(self, service_name: str):
        """Start a service."""
        try:
            success = await self.service_registry.start_service(service_name)
            return {"success": success, "message": f"Service {service_name} start {'succeeded' if success else 'failed'}"}
        except Exception as e:
            logger.error(f"Error starting service {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def stop_service(self, service_name: str):
        """Stop a service."""
        try:
            success = await self.service_registry.stop_service(service_name)
            return {"success": success, "message": f"Service {service_name} stop {'succeeded' if success else 'failed'}"}
        except Exception as e:
            logger.error(f"Error stopping service {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_service_config(self, service_name: str):
        """Get service configuration."""
        try:
            config = self.metadata_manager.get_service_config(service_name)
            if not config:
                raise HTTPException(status_code=404, detail="Service configuration not found")
            return config.get("config", {})
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting config for {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def update_service_config(self, service_name: str, request: Request):
        """Update service configuration."""
        try:
            new_config = await request.json()
            
            if service_name not in self.service_registry.services:
                raise HTTPException(status_code=404, detail="Service not found")
            
            success = await self.mcp_tools.update_service_config(service_name, new_config)
            if success:
                return {"success": True, "message": f"Configuration updated for {service_name}"}
            else:
                raise HTTPException(status_code=400, detail="Failed to update configuration")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating config for {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_service_stats(self, service_name: str):
        """Get service statistics."""
        try:
            # Check if service exists
            if service_name not in self.service_registry.services:
                raise HTTPException(status_code=404, detail="Service not found")
            
            # Get stats from monitoring data
            stats = self.metadata_manager.get_monitoring_data(service_name, "stats")
            if not stats:
                # Get current status as basic stats
                status = await self.service_registry.get_service_status(service_name)
                stats = {"data": status}
            
            return stats.get("data", {})
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting stats for {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_service_quota(self, service_name: str):
        """Get service quota information."""
        try:
            # Get service instance
            if service_name not in self.service_registry.services:
                raise HTTPException(status_code=404, detail="Service not found")
            
            service = self.service_registry.services[service_name]
            if hasattr(service, 'get_storage_stats'):
                storage_stats = await service.get_storage_stats()
                return {
                    "quota": storage_stats.get("quota", "unlimited"),
                    "used": storage_stats.get("used_size", 0),
                    "available": storage_stats.get("available_size", "unknown")
                }
            else:
                return {"quota": "unknown", "used": 0, "available": "unknown"}
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting quota for {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_service_storage(self, service_name: str):
        """Get service storage information."""
        try:
            # Get service instance
            if service_name not in self.service_registry.services:
                raise HTTPException(status_code=404, detail="Service not found")
            
            service = self.service_registry.services[service_name]
            if hasattr(service, 'get_storage_stats'):
                return await service.get_storage_stats()
            else:
                return {"error": "Storage stats not available for this service"}
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting storage info for {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_monitoring_data(self, service_name: str, metric_type: str = None):
        """Get monitoring data for a service."""
        try:
            data = self.metadata_manager.get_monitoring_data(service_name, metric_type)
            if not data:
                return {"message": "No monitoring data available"}
            return data
        except Exception as e:
            logger.error(f"Error getting monitoring data for {service_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_backend_stats(self):
        """Get statistics for all backends."""
        try:
            all_services_status = await self.service_registry.get_all_service_status()
            
            stats = {
                "total_services": len(all_services_status),
                "running_services": len([s for s in all_services_status.values() if s.get("status") == "running"]),
                "services": all_services_status,
                "metadata_stats": self.metadata_manager.get_stats()
            }
            
            return stats
        except Exception as e:
            logger.error(f"Error getting backend stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_mcp_status(self):
        """Get MCP server status."""
        return {
            "status": "running",
            "version": "1.0.0",
            "metadata_directory": str(self.metadata_manager.base_path),
            "services_count": len(await self.service_registry.list_services())
        }
    
    async def get_system_health(self):
        """Get system health information."""
        try:
            services = await self.service_registry.get_all_service_status()
            healthy_services = [name for name, status in services.items() if status.get("status") == "running"]
            
            return {
                "status": "healthy" if healthy_services else "degraded",
                "services_total": len(services),
                "services_healthy": len(healthy_services),
                "metadata_directory": str(self.metadata_manager.base_path),
                "uptime": "unknown"  # Could be enhanced with actual uptime tracking
            }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {"status": "error", "error": str(e)}
    
    async def dashboard_index(self):
        """Serve the dashboard index page."""
        from fastapi.responses import HTMLResponse
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>IPFS Kit Service Dashboard</title>
            <link rel="stylesheet" href="/static/service-dashboard.css">
            <script src="/static/mcp-sdk.js"></script>
        </head>
        <body>
            <div class="container">
                <h1>IPFS Kit Service Dashboard</h1>
                <div id="dashboard">
                    <div class="loading">Loading services...</div>
                </div>
            </div>
            
            <script>
                document.addEventListener('DOMContentLoaded', async function() {{
                    try {{
                        const client = MCP.createClient({{ baseUrl: '' }});
                        const dashboard = MCP.createServiceDashboard(client, {{
                            container: document.getElementById('dashboard'),
                            refreshInterval: 5000
                        }});
                        
                        await dashboard.init();
                    }} catch (error) {{
                        console.error('Dashboard initialization failed:', error);
                        document.getElementById('dashboard').innerHTML = 
                            '<div class="loading">Error: ' + error.message + '</div>';
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html)
    
    async def start(self):
        """Start the MCP server."""
        logger.info(f"Starting Enhanced MCP Server on {self.host}:{self.port}")
        
        # Initialize default services
        await self._initialize_default_services()
        
        # Start the server
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def _initialize_default_services(self):
        """Initialize default services based on configuration."""
        try:
            global_config = self.metadata_manager.get_global_config()
            default_services = global_config.get("default_services", [
                "ipfs", "ipfs_cluster", "s3", "storacha", "huggingface"
            ])
            
            for service_name in default_services:
                if service_name not in await self.service_registry.list_services():
                    logger.info(f"Adding default service: {service_name}")
                    await self.service_registry.add_service(service_name)
                    
        except Exception as e:
            logger.warning(f"Error initializing default services: {e}")


# Convenience function to start the server
async def start_enhanced_mcp_server(host: str = "127.0.0.1", port: int = 8004):
    """Start the enhanced MCP server."""
    server = EnhancedMCPServer(host=host, port=port)
    await server.start()
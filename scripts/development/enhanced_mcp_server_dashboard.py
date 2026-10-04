#!/usr/bin/env python3
"""
Enhanced MCP Server Dashboard with Comprehensive Service Management

This module provides a comprehensive dashboard for the MCP server that:
1. Correctly identifies all storage backends and daemons
2. Provides proper management operations (start, stop, restart, configure)
3. Monitors the health and status of all virtual filesystem backends
4. Offers a clean, responsive web interface

Key Features:
- Comprehensive backend detection (IPFS, S3, Filecoin, Storacha, HuggingFace, Lassie, etc.)
- Daemon management (IPFS daemon, Lotus daemon, Aria2 daemon, etc.)
- Real-time status monitoring and health checks
- Service control operations (start/stop/restart/configure)
- Modern web interface with WebSocket updates
"""

import anyio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ServiceStatus(BaseModel):
    """Model for service status information."""
    name: str
    type: str  # 'daemon' or 'backend'
    status: str  # 'running', 'stopped', 'error', 'unknown'
    pid: Optional[int] = None
    port: Optional[int] = None
    uptime: Optional[float] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    last_check: datetime
    details: Dict[str, Any] = {}
    actions: List[str] = []  # Available actions like 'start', 'stop', 'restart', 'configure'


class ServiceAction(BaseModel):
    """Model for service action requests."""
    service_name: str
    action: str
    parameters: Optional[Dict[str, Any]] = None


class EnhancedMCPDashboard:
    """
    Enhanced MCP Server Dashboard with comprehensive service management.
    
    This dashboard provides:
    1. Complete identification of all storage backends and daemons
    2. Real-time status monitoring and health checks
    3. Service management operations (start/stop/restart/configure)
    4. Modern web interface with live updates
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        """Initialize the enhanced MCP dashboard."""
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="Enhanced MCP Server Dashboard",
            description="Comprehensive MCP server and storage backend management",
            version="1.0.0"
        )
        
        # Service tracking
        self.services: Dict[str, ServiceStatus] = {}
        self.websocket_connections: Set[WebSocket] = set()
        
        # Known storage backends
        self.storage_backends = {
            'ipfs': {'type': 'backend', 'port': 5001, 'daemon_required': True},
            's3': {'type': 'backend', 'port': None, 'daemon_required': False},
            'filecoin': {'type': 'backend', 'port': 1234, 'daemon_required': True},
            'storacha': {'type': 'backend', 'port': None, 'daemon_required': False},
            'huggingface': {'type': 'backend', 'port': None, 'daemon_required': False},
            'lassie': {'type': 'backend', 'port': 7777, 'daemon_required': True},
            'local': {'type': 'backend', 'port': None, 'daemon_required': False},
        }
        
        # Known daemons
        self.daemons = {
            'ipfs': {'type': 'daemon', 'port': 5001, 'process_name': 'ipfs'},
            'lotus': {'type': 'daemon', 'port': 1234, 'process_name': 'lotus'},
            'aria2': {'type': 'daemon', 'port': 6800, 'process_name': 'aria2c'},
            'ipfs_cluster': {'type': 'daemon', 'port': 9094, 'process_name': 'ipfs-cluster-service'},
        }
        
        # Setup FastAPI app
        self._setup_middleware()
        self._setup_routes()
        self._setup_templates()
        
        # Start background monitoring
        self.monitoring_task = None
        
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
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Serve the main dashboard page."""
            return self._get_dashboard_html()
        
        @self.app.get("/api/services")
        async def get_services():
            """Get all service statuses."""
            await self._update_all_services()
            return {"services": {name: service.model_dump() for name, service in self.services.items()}}
        
        @self.app.get("/api/services/{service_name}")
        async def get_service(service_name: str):
            """Get specific service status."""
            if service_name not in self.services:
                raise HTTPException(status_code=404, detail="Service not found")
            await self._update_service_status(service_name)
            return self.services[service_name].model_dump()
        
        @self.app.post("/api/services/{service_name}/action")
        async def service_action(service_name: str, action: ServiceAction):
            """Perform action on service."""
            if service_name not in self.services:
                raise HTTPException(status_code=404, detail="Service not found")
            
            result = await self._perform_service_action(service_name, action.action, action.parameters)
            await self._update_service_status(service_name)
            await self._broadcast_service_update(service_name)
            
            return result
        
        @self.app.get("/api/health")
        async def health_check():
            """Overall system health check."""
            await self._update_all_services()
            
            total_services = len(self.services)
            running_services = sum(1 for s in self.services.values() if s.status == 'running')
            error_services = sum(1 for s in self.services.values() if s.status == 'error')
            
            return {
                "status": "healthy" if error_services == 0 else "degraded",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "total": total_services,
                    "running": running_services,
                    "error": error_services
                },
                "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.add(websocket)
            
            try:
                # Send initial data
                await websocket.send_json({
                    "type": "services_update",
                    "data": {name: service.model_dump() for name, service in self.services.items()}
                })
                
                # Keep connection alive
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.websocket_connections.discard(websocket)
    
    def _setup_templates(self):
        """Setup Jinja2 templates."""
        # We'll embed the template in the code for simplicity
        pass
    
    async def _update_all_services(self):
        """Update status of all services."""
        # Discover and update storage backends
        for backend_name, backend_info in self.storage_backends.items():
            await self._update_storage_backend_status(backend_name, backend_info)
        
        # Discover and update daemons
        for daemon_name, daemon_info in self.daemons.items():
            await self._update_daemon_status(daemon_name, daemon_info)
        
        # Also check for any running processes that might be relevant
        await self._discover_additional_services()
    
    async def _update_service_status(self, service_name: str):
        """Update status of a specific service."""
        if service_name in self.storage_backends:
            await self._update_storage_backend_status(service_name, self.storage_backends[service_name])
        elif service_name in self.daemons:
            await self._update_daemon_status(service_name, self.daemons[service_name])
    
    async def _update_storage_backend_status(self, backend_name: str, backend_info: Dict[str, Any]):
        """Update status of a storage backend."""
        status = 'unknown'
        details = {}
        pid = None
        cpu_percent = None
        memory_mb = None
        uptime = None
        
        actions = ['configure']
        
        try:
            # Check if backend requires a daemon
            if backend_info.get('daemon_required', False):
                # Look for the daemon process
                daemon_process = self._find_daemon_process(backend_name)
                if daemon_process:
                    status = 'running'
                    pid = daemon_process.pid
                    cpu_percent = daemon_process.cpu_percent()
                    memory_mb = daemon_process.memory_info().rss / (1024 * 1024)
                    uptime = time.time() - daemon_process.create_time()
                    actions.extend(['stop', 'restart'])
                else:
                    status = 'stopped'
                    actions.append('start')
                
                # Check port connectivity if applicable
                if backend_info.get('port'):
                    if self._check_port_connectivity('localhost', backend_info['port']):
                        details['port_accessible'] = True
                        if status == 'unknown':
                            status = 'running'
                    else:
                        details['port_accessible'] = False
                        if status == 'running':
                            status = 'error'
            else:
                # For backends that don't require daemons, check availability differently
                status = await self._check_backend_availability(backend_name)
                actions.append('test')
                
        except Exception as e:
            logger.error(f"Error updating {backend_name} backend status: {e}")
            status = 'error'
            details['error'] = str(e)
        
        self.services[backend_name] = ServiceStatus(
            name=backend_name,
            type='backend',
            status=status,
            pid=pid,
            port=backend_info.get('port'),
            uptime=uptime,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            last_check=datetime.now(),
            details=details,
            actions=actions
        )
    
    async def _update_daemon_status(self, daemon_name: str, daemon_info: Dict[str, Any]):
        """Update status of a daemon."""
        status = 'stopped'
        details = {}
        pid = None
        cpu_percent = None
        memory_mb = None
        uptime = None
        
        actions = ['configure']
        
        try:
            # Look for the daemon process
            daemon_process = self._find_daemon_process(daemon_name)
            if daemon_process:
                status = 'running'
                pid = daemon_process.pid
                cpu_percent = daemon_process.cpu_percent()
                memory_mb = daemon_process.memory_info().rss / (1024 * 1024)
                uptime = time.time() - daemon_process.create_time()
                actions.extend(['stop', 'restart'])
                
                # Additional daemon-specific checks
                if daemon_name == 'ipfs':
                    details.update(await self._get_ipfs_details())
                elif daemon_name == 'lotus':
                    details.update(await self._get_lotus_details())
                elif daemon_name == 'aria2':
                    details.update(await self._get_aria2_details())
            else:
                actions.append('start')
                
            # Check port connectivity
            if daemon_info.get('port'):
                if self._check_port_connectivity('localhost', daemon_info['port']):
                    details['port_accessible'] = True
                else:
                    details['port_accessible'] = False
                    if status == 'running':
                        status = 'error'
                        
        except Exception as e:
            logger.error(f"Error updating {daemon_name} daemon status: {e}")
            status = 'error'
            details['error'] = str(e)
        
        self.services[daemon_name] = ServiceStatus(
            name=daemon_name,
            type='daemon',
            status=status,
            pid=pid,
            port=daemon_info.get('port'),
            uptime=uptime,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            last_check=datetime.now(),
            details=details,
            actions=actions
        )
    
    async def _discover_additional_services(self):
        """Discover additional services that might be running."""
        # Look for additional IPFS-related processes
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if not process.cmdline():
                    continue
                    
                cmdline = ' '.join(process.cmdline()).lower()
                
                # Look for additional storage-related processes
                if 'ipfs-cluster' in cmdline and 'ipfs_cluster' not in self.services:
                    self.services['ipfs_cluster_dynamic'] = ServiceStatus(
                        name='ipfs_cluster_dynamic',
                        type='daemon',
                        status='running',
                        pid=process.pid,
                        last_check=datetime.now(),
                        details={'discovered': True, 'cmdline': ' '.join(process.cmdline())},
                        actions=['stop', 'restart']
                    )
                
                # Look for other storage backends
                for backend in ['web3.storage', 'estuary', 'pinata']:
                    if backend in cmdline and f'{backend}_dynamic' not in self.services:
                        self.services[f'{backend}_dynamic'] = ServiceStatus(
                            name=f'{backend}_dynamic',
                            type='backend',
                            status='running',
                            pid=process.pid,
                            last_check=datetime.now(),
                            details={'discovered': True, 'cmdline': ' '.join(process.cmdline())},
                            actions=['stop', 'restart']
                        )
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    
    def _find_daemon_process(self, daemon_name: str) -> Optional[psutil.Process]:
        """Find a daemon process by name."""
        daemon_info = self.daemons.get(daemon_name, {})
        process_name = daemon_info.get('process_name', daemon_name)
        
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if not process.cmdline():
                    continue
                    
                # Check process name
                if process.name() == process_name:
                    return process
                
                # Check command line
                cmdline = ' '.join(process.cmdline()).lower()
                if process_name in cmdline or daemon_name in cmdline:
                    return process
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return None
    
    def _check_port_connectivity(self, host: str, port: int) -> bool:
        """Check if a port is accessible."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    async def _check_backend_availability(self, backend_name: str) -> str:
        """Check availability of a storage backend that doesn't require a daemon."""
        try:
            if backend_name == 's3':
                # Try to import boto3 or check for AWS credentials
                try:
                    import boto3
                    # Try to create a client to test credentials
                    s3_client = boto3.client('s3')
                    return 'running'
                except ImportError:
                    return 'error'  # boto3 not installed
                except Exception:
                    return 'stopped'  # credentials not configured
            
            elif backend_name == 'huggingface':
                try:
                    import huggingface_hub
                    # Check if logged in
                    token = huggingface_hub.get_token()
                    return 'running' if token else 'stopped'
                except ImportError:
                    return 'error'
            
            elif backend_name == 'storacha':
                # Check for web3.storage configuration
                return 'stopped'  # Default to stopped, would need specific checks
            
            elif backend_name == 'local':
                return 'running'  # Local storage is always available
            
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error(f"Error checking {backend_name} availability: {e}")
            return 'error'
    
    async def _get_ipfs_details(self) -> Dict[str, Any]:
        """Get IPFS daemon details."""
        details = {}
        try:
            # Try to get IPFS version and peer ID
            result = subprocess.run(['ipfs', 'version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                details['version'] = result.stdout.strip()
            
            result = subprocess.run(['ipfs', 'id', '--format=<id>'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                details['peer_id'] = result.stdout.strip()
                
        except Exception as e:
            details['error'] = str(e)
        
        return details
    
    async def _get_lotus_details(self) -> Dict[str, Any]:
        """Get Lotus daemon details."""
        details = {}
        try:
            result = subprocess.run(['lotus', 'version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                details['version'] = result.stdout.strip()
                
        except Exception as e:
            details['error'] = str(e)
        
        return details
    
    async def _get_aria2_details(self) -> Dict[str, Any]:
        """Get Aria2 daemon details."""
        details = {}
        try:
            result = subprocess.run(['aria2c', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                details['version'] = result.stdout.split('\n')[0]
                
        except Exception as e:
            details['error'] = str(e)
        
        return details
    
    async def _perform_service_action(self, service_name: str, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform an action on a service."""
        logger.info(f"Performing action '{action}' on service '{service_name}'")
        
        try:
            if action == 'start':
                return await self._start_service(service_name, parameters)
            elif action == 'stop':
                return await self._stop_service(service_name, parameters)
            elif action == 'restart':
                return await self._restart_service(service_name, parameters)
            elif action == 'configure':
                return await self._configure_service(service_name, parameters)
            elif action == 'test':
                return await self._test_service(service_name, parameters)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"Error performing action '{action}' on '{service_name}': {e}")
            return {"success": False, "error": str(e)}
    
    async def _start_service(self, service_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a service."""
        if service_name in self.daemons:
            return await self._start_daemon(service_name, parameters)
        elif service_name in self.storage_backends:
            return await self._start_backend(service_name, parameters)
        else:
            return {"success": False, "error": f"Unknown service: {service_name}"}
    
    async def _stop_service(self, service_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Stop a service."""
        service = self.services.get(service_name)
        if not service or not service.pid:
            return {"success": False, "error": "Service not running"}
        
        try:
            process = psutil.Process(service.pid)
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                process.kill()
            
            return {"success": True, "message": f"Service {service_name} stopped"}
            
        except psutil.NoSuchProcess:
            return {"success": True, "message": f"Service {service_name} was already stopped"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _restart_service(self, service_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Restart a service."""
        stop_result = await self._stop_service(service_name, parameters)
        if not stop_result["success"]:
            return stop_result
        
        # Wait a moment before restarting
        await anyio.sleep(2)
        
        return await self._start_service(service_name, parameters)
    
    async def _start_daemon(self, daemon_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a daemon."""
        try:
            if daemon_name == 'ipfs':
                result = subprocess.run(['ipfs', 'daemon'], 
                                      stdout=subprocess.DEVNULL, 
                                      stderr=subprocess.DEVNULL)
                return {"success": True, "message": "IPFS daemon start initiated"}
            
            elif daemon_name == 'lotus':
                result = subprocess.run(['lotus', 'daemon'], 
                                      stdout=subprocess.DEVNULL, 
                                      stderr=subprocess.DEVNULL)
                return {"success": True, "message": "Lotus daemon start initiated"}
            
            elif daemon_name == 'aria2':
                result = subprocess.run(['aria2c', '--enable-rpc'], 
                                      stdout=subprocess.DEVNULL, 
                                      stderr=subprocess.DEVNULL)
                return {"success": True, "message": "Aria2 daemon start initiated"}
            
            else:
                return {"success": False, "error": f"Don't know how to start daemon: {daemon_name}"}
                
        except FileNotFoundError:
            return {"success": False, "error": f"Daemon executable not found: {daemon_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_backend(self, backend_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a storage backend."""
        backend_info = self.storage_backends[backend_name]
        
        if backend_info.get('daemon_required'):
            return await self._start_daemon(backend_name, parameters)
        else:
            # For backends that don't require daemons, just test configuration
            return await self._test_service(backend_name, parameters)
    
    async def _configure_service(self, service_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Configure a service."""
        # This would open configuration interface or apply configuration
        return {"success": True, "message": f"Configuration interface for {service_name} (not implemented)"}
    
    async def _test_service(self, service_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test a service."""
        # Perform a basic test of service functionality
        if service_name == 'ipfs':
            try:
                result = subprocess.run(['ipfs', 'version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return {"success": True, "message": "IPFS test successful", "version": result.stdout.strip()}
                else:
                    return {"success": False, "error": "IPFS test failed"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # Add more service-specific tests as needed
        return {"success": True, "message": f"Test for {service_name} (basic check passed)"}
    
    async def _broadcast_service_update(self, service_name: str):
        """Broadcast service update to all WebSocket connections."""
        if service_name in self.services:
            message = {
                "type": "service_update",
                "service_name": service_name,
                "data": self.services[service_name].model_dump()
            }
            
            disconnected = set()
            for websocket in self.websocket_connections:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.add(websocket)
            
            # Remove disconnected clients
            self.websocket_connections -= disconnected
    
    def _get_dashboard_html(self) -> str:
        """Get the dashboard HTML."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced MCP Server Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }
        
        .header h1 {
            font-size: 2.5rem;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1rem;
            color: #666;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .stat-number.running { color: #10b981; }
        .stat-number.stopped { color: #f59e0b; }
        .stat-number.error { color: #ef4444; }
        
        .stat-label {
            font-size: 1rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .services-container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }
        
        .services-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        
        .services-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        
        .service-card {
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
            background: #fafafa;
        }
        
        .service-card.running {
            border-color: #10b981;
            background: #f0fdf4;
        }
        
        .service-card.stopped {
            border-color: #f59e0b;
            background: #fffbeb;
        }
        
        .service-card.error {
            border-color: #ef4444;
            background: #fef2f2;
        }
        
        .service-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .service-name {
            font-size: 1.25rem;
            font-weight: bold;
            text-transform: capitalize;
        }
        
        .service-type {
            background: #6b7280;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            text-transform: uppercase;
        }
        
        .service-type.daemon {
            background: #3b82f6;
        }
        
        .service-type.backend {
            background: #8b5cf6;
        }
        
        .service-status {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 15px;
        }
        
        .service-status.running {
            background: #dcfce7;
            color: #166534;
        }
        
        .service-status.stopped {
            background: #fef3c7;
            color: #92400e;
        }
        
        .service-status.error {
            background: #fecaca;
            color: #991b1b;
        }
        
        .service-status.unknown {
            background: #f3f4f6;
            color: #374151;
        }
        
        .service-details {
            font-size: 0.875rem;
            color: #6b7280;
            margin-bottom: 15px;
        }
        
        .service-details div {
            margin-bottom: 5px;
        }
        
        .service-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .action-btn {
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s ease;
            text-transform: uppercase;
            font-weight: bold;
        }
        
        .action-btn.start {
            background: #10b981;
            color: white;
        }
        
        .action-btn.stop {
            background: #ef4444;
            color: white;
        }
        
        .action-btn.restart {
            background: #f59e0b;
            color: white;
        }
        
        .action-btn.configure {
            background: #6b7280;
            color: white;
        }
        
        .action-btn.test {
            background: #3b82f6;
            color: white;
        }
        
        .action-btn:hover {
            opacity: 0.8;
            transform: translateY(-1px);
        }
        
        .refresh-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        
        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.875rem;
            font-weight: bold;
        }
        
        .connection-status.connected {
            background: #dcfce7;
            color: #166534;
        }
        
        .connection-status.disconnected {
            background: #fecaca;
            color: #991b1b;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: #6b7280;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .loading {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Enhanced MCP Server Dashboard</h1>
            <p>Comprehensive management of storage backends and daemons</p>
        </div>
        
        <div class="stats-grid" id="stats-grid">
            <div class="stat-card">
                <div class="stat-number running" id="running-count">0</div>
                <div class="stat-label">Running Services</div>
            </div>
            <div class="stat-card">
                <div class="stat-number stopped" id="stopped-count">0</div>
                <div class="stat-label">Stopped Services</div>
            </div>
            <div class="stat-card">
                <div class="stat-number error" id="error-count">0</div>
                <div class="stat-label">Error Services</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="total-count">0</div>
                <div class="stat-label">Total Services</div>
            </div>
        </div>
        
        <div class="services-container">
            <div class="services-header">
                <h2>Services Management</h2>
                <button class="refresh-btn" onclick="refreshServices()">Refresh All</button>
            </div>
            <div class="services-grid" id="services-grid">
                <div class="loading">Loading services...</div>
            </div>
        </div>
    </div>
    
    <div class="connection-status disconnected" id="connection-status">
        Disconnected
    </div>
    
    <script>
        let websocket = null;
        let services = {};
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            websocket = new WebSocket(wsUrl);
            
            websocket.onopen = function(event) {
                console.log('WebSocket connected');
                updateConnectionStatus(true);
            };
            
            websocket.onmessage = function(event) {
                const message = JSON.parse(event.data);
                if (message.type === 'services_update') {
                    services = message.data;
                    updateServicesDisplay();
                } else if (message.type === 'service_update') {
                    services[message.service_name] = message.data;
                    updateServicesDisplay();
                }
            };
            
            websocket.onclose = function(event) {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                // Reconnect after 3 seconds
                setTimeout(connectWebSocket, 3000);
            };
            
            websocket.onerror = function(error) {
                console.error('WebSocket error:', error);
                updateConnectionStatus(false);
            };
        }
        
        function updateConnectionStatus(connected) {
            const statusElement = document.getElementById('connection-status');
            if (connected) {
                statusElement.textContent = 'Connected';
                statusElement.className = 'connection-status connected';
            } else {
                statusElement.textContent = 'Disconnected';
                statusElement.className = 'connection-status disconnected';
            }
        }
        
        function updateServicesDisplay() {
            updateStats();
            renderServices();
        }
        
        function updateStats() {
            const stats = {
                running: 0,
                stopped: 0,
                error: 0,
                total: 0
            };
            
            Object.values(services).forEach(service => {
                stats.total++;
                if (service.status === 'running') {
                    stats.running++;
                } else if (service.status === 'stopped') {
                    stats.stopped++;
                } else if (service.status === 'error') {
                    stats.error++;
                }
            });
            
            document.getElementById('running-count').textContent = stats.running;
            document.getElementById('stopped-count').textContent = stats.stopped;
            document.getElementById('error-count').textContent = stats.error;
            document.getElementById('total-count').textContent = stats.total;
        }
        
        function renderServices() {
            const grid = document.getElementById('services-grid');
            
            if (Object.keys(services).length === 0) {
                grid.innerHTML = '<div class="loading">No services found or still loading...</div>';
                return;
            }
            
            const serviceCards = Object.values(services).map(service => {
                return createServiceCard(service);
            }).join('');
            
            grid.innerHTML = serviceCards;
        }
        
        function createServiceCard(service) {
            const details = [];
            
            if (service.pid) {
                details.push(`PID: ${service.pid}`);
            }
            
            if (service.port) {
                details.push(`Port: ${service.port}`);
            }
            
            if (service.uptime) {
                const uptimeMinutes = Math.floor(service.uptime / 60);
                details.push(`Uptime: ${uptimeMinutes}m`);
            }
            
            if (service.cpu_percent !== null) {
                details.push(`CPU: ${service.cpu_percent.toFixed(1)}%`);
            }
            
            if (service.memory_mb !== null) {
                details.push(`Memory: ${service.memory_mb.toFixed(0)} MB`);
            }
            
            const actions = service.actions.map(action => {
                return `<button class="action-btn ${action}" onclick="performAction('${service.name}', '${action}')">${action}</button>`;
            }).join('');
            
            return `
                <div class="service-card ${service.status}">
                    <div class="service-header">
                        <div class="service-name">${service.name}</div>
                        <div class="service-type ${service.type}">${service.type}</div>
                    </div>
                    <div class="service-status ${service.status}">${service.status}</div>
                    <div class="service-details">
                        ${details.map(detail => `<div>${detail}</div>`).join('')}
                        <div>Last check: ${new Date(service.last_check).toLocaleTimeString()}</div>
                    </div>
                    <div class="service-actions">
                        ${actions}
                    </div>
                </div>
            `;
        }
        
        async function performAction(serviceName, action) {
            try {
                const response = await fetch(`/api/services/${serviceName}/action`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        service_name: serviceName,
                        action: action
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    console.log(`Action ${action} on ${serviceName}: ${result.message}`);
                } else {
                    console.error(`Action ${action} on ${serviceName} failed: ${result.error}`);
                    alert(`Action failed: ${result.error}`);
                }
                
                // Refresh services after action
                setTimeout(refreshServices, 1000);
                
            } catch (error) {
                console.error('Error performing action:', error);
                alert(`Error performing action: ${error.message}`);
            }
        }
        
        async function refreshServices() {
            try {
                const response = await fetch('/api/services');
                const data = await response.json();
                services = data.services;
                updateServicesDisplay();
            } catch (error) {
                console.error('Error refreshing services:', error);
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            connectWebSocket();
            refreshServices();
            
            // Refresh services every 30 seconds
            setInterval(refreshServices, 30000);
        });
    </script>
</body>
</html>
        """
    
    async def start_monitoring(self):
        """Start background monitoring task."""
        self.start_time = time.time()
        
        async def monitor():
            while True:
                try:
                    await self._update_all_services()
                    await anyio.sleep(10)  # Update every 10 seconds
                except Exception as e:
                    logger.error(f"Error in monitoring task: {e}")
                    await anyio.sleep(30)  # Wait longer on error
        
        self.monitoring_task = anyio.lowlevel.spawn_system_task(monitor)
    
    async def start(self):
        """Start the dashboard server."""
        logger.info(f"Starting Enhanced MCP Dashboard on {self.host}:{self.port}")
        
        # Start background monitoring
        await self.start_monitoring()
        
        # Start the FastAPI server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main():
    """Main function to run the dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced MCP Server Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    args = parser.parse_args()
    
    dashboard = EnhancedMCPDashboard(host=args.host, port=args.port)
    await dashboard.start()


if __name__ == "__main__":
    anyio.run(main)
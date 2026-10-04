"""
Health check API for MCP server.

This module provides health check endpoints to monitor the status
of the MCP server and its components.
"""

import time
import logging
import os
import json
import threading
import socket
from typing import Dict, Any, Optional, List, Callable

# Configure logger
logger = logging.getLogger(__name__)

class HealthCheckAPI:
    """
    Health check API for the MCP server.
    
    Provides endpoints for checking the health of the server and its
    components, including storage backends, dependencies, and resources.
    """
    
    def __init__(self, app=None, storage_manager=None, monitoring_system=None):
        """
        Initialize the health check API.
        
        Args:
            app: FastAPI or similar app instance
            storage_manager: UnifiedStorageManager instance
            monitoring_system: MonitoringSystem instance
        """
        self.app = app
        self.storage_manager = storage_manager
        self.monitoring_system = monitoring_system
        
        # Track component healthiness
        self.components = {
            "server": {"status": "unknown", "last_check": 0, "details": {}},
            "storage": {"status": "unknown", "last_check": 0, "details": {}},
            "dependencies": {"status": "unknown", "last_check": 0, "details": {}},
            "resources": {"status": "unknown", "last_check": 0, "details": {}},
        }
        
        # Overall server status
        self.overall_status = "unknown"
        self.startup_time = time.time()
        
        # Register routes if app provided
        if app:
            self.register_routes(app)
            
    def register_routes(self, app):
        """
        Register health check routes with the application.
        
        Args:
            app: FastAPI or similar app instance
        """
        try:
            # Store reference to app
            self.app = app
            
            # Register routes based on app type
            if hasattr(app, "add_api_route"):  # FastAPI
                app.add_api_route("/health", self.health_check, methods=["GET"])
                app.add_api_route("/health/live", self.liveness_check, methods=["GET"])
                app.add_api_route("/health/ready", self.readiness_check, methods=["GET"])
                app.add_api_route("/health/storage", self.storage_health, methods=["GET"])
                app.add_api_route("/health/dependencies", self.dependencies_health, methods=["GET"])
                app.add_api_route("/health/details", self.detailed_health, methods=["GET"])
                
                logger.info("Registered health check routes with FastAPI app")
                
            elif hasattr(app, "route"):  # Flask-like
                app.route("/health")(self.health_check)
                app.route("/health/live")(self.liveness_check)
                app.route("/health/ready")(self.readiness_check)
                app.route("/health/storage")(self.storage_health)
                app.route("/health/dependencies")(self.dependencies_health)
                app.route("/health/details")(self.detailed_health)
                
                logger.info("Registered health check routes with Flask-like app")
                
            else:
                logger.warning(f"Unknown app type: {type(app)}. Health checks may not work correctly.")
                
        except Exception as e:
            logger.error(f"Failed to register health check routes: {e}")
            
    def start_background_checks(self, interval: int = 60):
        """
        Start background health checks.
        
        Args:
            interval: Check interval in seconds
        """
        def check_loop():
            logger.info("Starting background health check loop")
            
            while True:
                try:
                    # Run all health checks
                    self.check_all_components()
                    
                    # Sleep until next check
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in background health check loop: {e}")
                    time.sleep(interval * 2)  # Sleep longer on error
                    
        # Start the background thread
        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start()
        logger.info(f"Started background health checks with {interval}s interval")
            
    def check_all_components(self):
        """Check the health of all components."""
        # Check server health
        self.check_server_health()
        
        # Check storage health
        self.check_storage_health()
        
        # Check dependencies health
        self.check_dependencies_health()
        
        # Check resources health
        self.check_resources_health()
        
        # Update overall status
        self._update_overall_status()
        
    def check_server_health(self):
        """Check server health."""
        status = "healthy"
        details = {
            "hostname": socket.gethostname(),
            "uptime": time.time() - self.startup_time,
            "timestamp": time.time(),
        }
        
        # Get memory usage
        try:
            import psutil
            memory = psutil.virtual_memory()
            details["memory"] = {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent,
            }
            
            # Check if memory is critically low
            if memory.percent > 95:
                status = "degraded"
                details["memory"]["warning"] = "Memory usage is critically high"
                
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            details["cpu"] = {
                "percent": cpu_percent,
            }
            
            # Check if CPU is overloaded
            if cpu_percent > 90:
                status = "degraded"
                details["cpu"]["warning"] = "CPU usage is very high"
                
            # Get disk usage for the current directory
            disk = psutil.disk_usage(".")
            details["disk"] = {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            }
            
            # Check if disk is almost full
            if disk.percent > 90:
                status = "degraded"
                details["disk"]["warning"] = "Disk space is critically low"
                
        except ImportError:
            details["note"] = "psutil not available for detailed resource metrics"
        except Exception as e:
            details["error"] = str(e)
        
        # Update component status
        self.components["server"] = {
            "status": status,
            "last_check": time.time(),
            "details": details,
        }
        
        return status, details
        
    def check_storage_health(self):
        """Check storage backends health."""
        status = "healthy"
        details = {
            "backends": {},
            "timestamp": time.time(),
        }
        
        # Check if monitoring system is available
        if self.monitoring_system:
            try:
                # Get backend status from monitoring system
                backend_status = self.monitoring_system.get_backend_status()
                
                # Use overall status from monitoring system
                status = backend_status.get("overall_status", "unknown")
                
                # Map monitoring system status to our format
                status_map = {
                    "healthy": "healthy",
                    "degraded": "degraded",
                    "unhealthy": "unhealthy",
                    "unknown": "unknown",
                }
                
                status = status_map.get(status, "unknown")
                
                # Add backend details
                for backend, backend_info in backend_status.get("backends", {}).items():
                    backend_status = backend_info.get("status")
                    
                    details["backends"][backend] = {
                        "status": status_map.get(backend_status, "unknown"),
                        "last_check": backend_info.get("last_check", 0),
                    }
                    
            except Exception as e:
                logger.error(f"Error getting backend status from monitoring system: {e}")
                status = "degraded"
                details["error"] = str(e)
        
        # If no monitoring system, check backends directly
        elif self.storage_manager:
            try:
                # Get available backends
                backends = list(self.storage_manager.backends.keys())
                
                # Initialize with healthy status
                overall_healthy = True
                
                # Check each backend
                for backend_type in backends:
                    backend = self.storage_manager.backends[backend_type]
                    backend_name = backend_type.value
                    
                    # Try to get backend status
                    if hasattr(backend, "get_status") and callable(getattr(backend, "get_status")):
                        backend_result = backend.get_status()
                        
                        # Determine backend status
                        backend_status = "healthy"
                        
                        if not backend_result.get("success", False):
                            backend_status = "unhealthy"
                            overall_healthy = False
                        elif not backend_result.get("available", True):
                            backend_status = "degraded"
                            overall_healthy = False
                            
                        # Add backend details
                        details["backends"][backend_name] = {
                            "status": backend_status,
                            "details": backend_result,
                        }
                    else:
                        # No status method, just check if backend exists
                        details["backends"][backend_name] = {
                            "status": "unknown",
                            "note": "Backend does not support status checks",
                        }
                
                # Set overall status based on backend health
                if not overall_healthy:
                    status = "degraded"
                    
            except Exception as e:
                logger.error(f"Error checking storage backends directly: {e}")
                status = "degraded"
                details["error"] = str(e)
        else:
            # No storage manager or monitoring system
            status = "unknown"
            details["error"] = "No storage manager or monitoring system available"
        
        # Update component status
        self.components["storage"] = {
            "status": status,
            "last_check": time.time(),
            "details": details,
        }
        
        return status, details
        
    def check_dependencies_health(self):
        """Check dependencies health."""
        status = "healthy"
        details = {
            "dependencies": {},
            "timestamp": time.time(),
        }
        
        # Check Python version
        import sys
        details["dependencies"]["python"] = {
            "version": sys.version,
            "status": "healthy",
        }
        
        # Check for required packages
        required_packages = [
            "fastapi", "starlette", "uvicorn",  # Web framework
            "requests", "aiohttp",              # HTTP clients
            "sqlalchemy",                       # Database
            "python-multipart",                 # File uploads
            "prometheus-client",                # Metrics
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                details["dependencies"][package] = {
                    "status": "installed",
                }
            except ImportError:
                details["dependencies"][package] = {
                    "status": "missing",
                }
                missing_packages.append(package)
        
        # Check optional packages
        optional_packages = [
            "sentence-transformers",  # For vector search
            "faiss-cpu",              # For vector search
            "psutil",                 # For system metrics
            "pdftotext",              # For PDF extraction
            "python-docx",            # For DOCX extraction
            "pytesseract",            # For OCR
        ]
        
        for package in optional_packages:
            try:
                __import__(package.replace("-", "_"))
                details["dependencies"][package] = {
                    "status": "installed",
                    "optional": True,
                }
            except ImportError:
                details["dependencies"][package] = {
                    "status": "missing",
                    "optional": True,
                }
        
        # Set status based on missing packages
        if missing_packages:
            status = "degraded"
            details["missing_required"] = missing_packages
        
        # Update component status
        self.components["dependencies"] = {
            "status": status,
            "last_check": time.time(),
            "details": details,
        }
        
        return status, details
        
    def check_resources_health(self):
        """Check system resources health."""
        status = "healthy"
        details = {
            "timestamp": time.time(),
        }
        
        try:
            import psutil
            
            # Check CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            details["cpu"] = {
                "percent": cpu_percent,
                "count": psutil.cpu_count(),
            }
            
            # CPU status
            if cpu_percent > 90:
                details["cpu"]["status"] = "critical"
                status = "degraded"
            elif cpu_percent > 75:
                details["cpu"]["status"] = "warning"
            else:
                details["cpu"]["status"] = "healthy"
            
            # Check memory
            memory = psutil.virtual_memory()
            details["memory"] = {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
            }
            
            # Memory status
            if memory.percent > 90:
                details["memory"]["status"] = "critical"
                status = "degraded"
            elif memory.percent > 75:
                details["memory"]["status"] = "warning"
            else:
                details["memory"]["status"] = "healthy"
            
            # Check disk
            disk = psutil.disk_usage(".")
            details["disk"] = {
                "total": disk.total,
                "free": disk.free,
                "percent": disk.percent,
            }
            
            # Disk status
            if disk.percent > 90:
                details["disk"]["status"] = "critical"
                status = "degraded"
            elif disk.percent > 75:
                details["disk"]["status"] = "warning"
            else:
                details["disk"]["status"] = "healthy"
                
            # Check network
            details["network"] = {
                "connections": len(psutil.net_connections()),
            }
            
            # Check for connection limits
            if details["network"]["connections"] > 1000:
                details["network"]["status"] = "warning"
                
        except ImportError:
            details["error"] = "psutil not available for resource checks"
            status = "unknown"
        except Exception as e:
            details["error"] = str(e)
            status = "degraded"
        
        # Update component status
        self.components["resources"] = {
            "status": status,
            "last_check": time.time(),
            "details": details,
        }
        
        return status, details
        
    def _update_overall_status(self):
        """Update the overall server status based on component health."""
        # Start with healthy status
        status = "healthy"
        
        # Check each component
        for component, info in self.components.items():
            if info["status"] == "unhealthy":
                # If any component is unhealthy, the overall status is unhealthy
                status = "unhealthy"
                break
            elif info["status"] == "degraded" and status != "unhealthy":
                # If any component is degraded (and none are unhealthy), status is degraded
                status = "degraded"
            elif info["status"] == "unknown" and status == "healthy":
                # If any component is unknown and current status is healthy, status is unknown
                status = "unknown"
        
        # Update overall status
        self.overall_status = status
        
    # API endpoint handlers
    
    async def health_check(self):
        """
        Basic health check endpoint.
        
        Returns:
            Dictionary with basic health status
        """
        # If we haven't checked components yet, do it now
        if all(info["status"] == "unknown" for info in self.components.values()):
            self.check_all_components()
            
        return {
            "status": self.overall_status,
            "uptime": time.time() - self.startup_time,
            "timestamp": time.time(),
        }
        
    async def liveness_check(self):
        """
        Liveness check endpoint for container orchestration.
        
        This endpoint checks if the service is running and not in a crash loop.
        It should return success even if other components are unhealthy, as long
        as the service itself is running.
        
        Returns:
            Dictionary with liveness status
        """
        # Always return healthy for liveness
        return {
            "status": "healthy",
            "timestamp": time.time(),
        }
        
    async def readiness_check(self):
        """
        Readiness check endpoint for container orchestration.
        
        This endpoint checks if the service is ready to accept traffic. It should
        return success only if all required components are healthy.
        
        Returns:
            Dictionary with readiness status
        """
        # Check components if not already checked
        if all(info["status"] == "unknown" for info in self.components.values()):
            self.check_all_components()
            
        return {
            "status": self.overall_status,
            "components": {
                component: info["status"] 
                for component, info in self.components.items()
            },
            "timestamp": time.time(),
        }
        
    async def storage_health(self):
        """
        Storage health check endpoint.
        
        This endpoint checks the health of storage backends specifically.
        
        Returns:
            Dictionary with storage health status
        """
        # Check storage health
        status, details = self.check_storage_health()
        
        return {
            "status": status,
            "details": details,
            "timestamp": time.time(),
        }
        
    async def dependencies_health(self):
        """
        Dependencies health check endpoint.
        
        This endpoint checks the health of dependencies specifically.
        
        Returns:
            Dictionary with dependencies health status
        """
        # Check dependencies health
        status, details = self.check_dependencies_health()
        
        return {
            "status": status,
            "details": details,
            "timestamp": time.time(),
        }
        
    async def detailed_health(self):
        """
        Detailed health check endpoint.
        
        This endpoint provides a comprehensive health report with detailed
        information about all components.
        
        Returns:
            Dictionary with detailed health status
        """
        # Check all components
        self.check_all_components()
        
        return {
            "status": self.overall_status,
            "components": self.components,
            "uptime": time.time() - self.startup_time,
            "timestamp": time.time(),
        }
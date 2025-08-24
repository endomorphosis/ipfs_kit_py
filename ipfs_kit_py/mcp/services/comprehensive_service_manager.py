#!/usr/bin/env python3
"""
Comprehensive Service Manager for IPFS Kit MCP Server

This module provides proper service management functionality for the MCP server's
services tab, replacing the incorrect "cars", "docker", "kubectl" services with
actual storage and daemon services that ipfs_kit_py manages.
"""

import asyncio
import json
import logging
import os
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class MockDaemonManager:
    """Mock daemon manager for testing purposes."""
    
    def __init__(self, daemon_type: str):
        self.daemon_type = daemon_type
        self.running = False
        
    def get_status(self):
        return {
            "daemon_type": self.daemon_type,
            "running": self.running,
            "initialized": True,
            "config_dir": f"~/.{self.daemon_type}",
            "api_port": 5001 if self.daemon_type == "ipfs" else 9000
        }
        
    def start(self):
        self.running = True
        return True
        
    def stop(self):
        self.running = False
        return True


class ServiceType(Enum):
    """Types of services managed by IPFS Kit."""
    DAEMON = "daemon"           # IPFS, Lotus, Aria2 daemons
    STORAGE = "storage"         # S3, HuggingFace, GitHub storage backends  
    NETWORK = "network"         # Network services
    INDEX = "index"             # Indexing services
    CREDENTIAL = "credential"   # Credentialed services


class ServiceStatus(Enum):
    """Service status states."""
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"
    UNKNOWN = "unknown"
    CONFIGURED = "configured"   # Service is configured but not running
    MISSING = "missing"         # Service not installed/configured


class ServiceAction(Enum):
    """Available actions for services."""
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    CONFIGURE = "configure"
    CHECK_HEALTH = "health_check"
    VIEW_LOGS = "view_logs"


class ComprehensiveServiceManager:
    """
    Manages all services for IPFS Kit including daemons, storage backends, and credentialed services.
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize the comprehensive service manager."""
        self.data_dir = data_dir or Path.home() / ".ipfs_kit"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Service configuration files
        self.services_config_file = self.data_dir / "services_config.json"
        self.service_states_file = self.data_dir / "service_states.json"
        
        # Load or initialize service configurations
        self.services_config = self._load_services_config()
        self.service_states = self._load_service_states()
        
        # Initialize daemon manager references
        self._daemon_managers = {}
        
        logger.info("Comprehensive Service Manager initialized")
    
    def _load_services_config(self) -> Dict[str, Any]:
        """Load services configuration."""
        if self.services_config_file.exists():
            try:
                with open(self.services_config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading services config: {e}")
        
        # Return default services configuration
        return self._get_default_services_config()
    
    def _load_service_states(self) -> Dict[str, Any]:
        """Load service states."""
        if self.service_states_file.exists():
            try:
                with open(self.service_states_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading service states: {e}")
        
        return {}
    
    def _save_services_config(self):
        """Save services configuration."""
        try:
            with open(self.services_config_file, 'w') as f:
                json.dump(self.services_config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving services config: {e}")
    
    def _save_service_states(self):
        """Save service states."""
        try:
            with open(self.service_states_file, 'w') as f:
                json.dump(self.service_states, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving service states: {e}")
    
    def _get_default_services_config(self) -> Dict[str, Any]:
        """Get default services configuration."""
        return {
            "daemons": {
                "ipfs": {
                    "type": ServiceType.DAEMON.value,
                    "name": "IPFS Daemon",
                    "description": "InterPlanetary File System daemon for distributed storage",
                    "port": 5001,
                    "gateway_port": 8080,
                    "swarm_port": 4001,
                    "config_dir": str(Path.home() / ".ipfs"),
                    "enabled": True,
                    "auto_start": True
                },
                "lotus": {
                    "type": ServiceType.DAEMON.value,
                    "name": "Lotus Client",
                    "description": "Filecoin Lotus client for decentralized storage",
                    "port": 1234,
                    "config_dir": str(Path.home() / ".lotus"),
                    "enabled": False,
                    "auto_start": False
                },
                "aria2": {
                    "type": ServiceType.DAEMON.value,
                    "name": "Aria2 Daemon",
                    "description": "High-speed download daemon for content retrieval",
                    "port": 6800,
                    "config_dir": str(Path.home() / ".aria2"),
                    "enabled": False,
                    "auto_start": False
                },
                "ipfs_cluster": {
                    "type": ServiceType.DAEMON.value,
                    "name": "IPFS Cluster",
                    "description": "IPFS Cluster daemon for coordinated pin management",
                    "port": 9094,
                    "config_dir": str(Path.home() / ".ipfs-cluster"),
                    "enabled": False,
                    "auto_start": False
                }
            },
            "storage_backends": {
                "s3": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Amazon S3",
                    "description": "Amazon Simple Storage Service backend",
                    "requires_credentials": True,
                    "config_keys": ["access_key", "secret_key", "region", "bucket"],
                    "enabled": False
                },
                "huggingface": {
                    "type": ServiceType.STORAGE.value,
                    "name": "HuggingFace Hub",
                    "description": "HuggingFace model and dataset repository",
                    "requires_credentials": True,
                    "config_keys": ["api_token", "username"],
                    "enabled": False
                },
                "github": {
                    "type": ServiceType.STORAGE.value,
                    "name": "GitHub Storage",
                    "description": "GitHub repository storage backend",
                    "requires_credentials": True,
                    "config_keys": ["access_token", "username", "repository"],
                    "enabled": False
                },
                "storacha": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Storacha",
                    "description": "Storacha decentralized storage service",
                    "requires_credentials": True,
                    "config_keys": ["api_key"],
                    "enabled": False
                },
                "lotus": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Lotus Storage",
                    "description": "Filecoin Lotus storage provider integration",
                    "requires_credentials": False,
                    "config_keys": ["node_url", "token"],
                    "enabled": False
                },
                "synapse": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Synapse Matrix",
                    "description": "Matrix Synapse server storage backend",
                    "requires_credentials": True,
                    "config_keys": ["homeserver_url", "access_token", "room_id"],
                    "enabled": False
                },
                "gdrive": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Google Drive",
                    "description": "Google Drive cloud storage backend",
                    "requires_credentials": True,
                    "config_keys": ["client_id", "client_secret", "refresh_token"],
                    "enabled": False
                },
                "ftp": {
                    "type": ServiceType.STORAGE.value,
                    "name": "FTP Server",
                    "description": "File Transfer Protocol storage backend",
                    "requires_credentials": True,
                    "config_keys": ["host", "port", "username", "password"],
                    "enabled": False
                },
                "sshfs": {
                    "type": ServiceType.STORAGE.value,
                    "name": "SSHFS",
                    "description": "SSH Filesystem storage backend",
                    "requires_credentials": True,
                    "config_keys": ["host", "port", "username", "private_key_path"],
                    "enabled": False
                }
            },
            "network_services": {
                "mcp_server": {
                    "type": ServiceType.NETWORK.value,
                    "name": "MCP Server",
                    "description": "Multi-Content Protocol server",
                    "port": 8004,
                    "enabled": True,
                    "status": ServiceStatus.RUNNING.value
                }
            }
        }
    
    async def list_services(self) -> Dict[str, Any]:
        """List all managed services with their current status."""
        services = []
        
        # Add daemon services
        for daemon_id, config in self.services_config.get("daemons", {}).items():
            if config.get("enabled", False):
                status = await self._check_daemon_status(daemon_id, config)
                services.append({
                    "id": daemon_id,
                    "name": config["name"],
                    "type": config["type"],
                    "description": config["description"],
                    "status": status["status"],
                    "port": config.get("port"),
                    "actions": self._get_available_actions(daemon_id, status["status"]),
                    "last_check": status.get("last_check"),
                    "details": status.get("details", {})
                })
        
        # Add storage backend services
        for backend_id, config in self.services_config.get("storage_backends", {}).items():
            if config.get("enabled", False):
                status = await self._check_storage_backend_status(backend_id, config)
                services.append({
                    "id": backend_id,
                    "name": config["name"],
                    "type": config["type"],
                    "description": config["description"],
                    "status": status["status"],
                    "requires_credentials": config.get("requires_credentials", False),
                    "actions": self._get_available_actions(backend_id, status["status"]),
                    "last_check": status.get("last_check"),
                    "details": status.get("details", {})
                })
        
        # Add network services
        for service_id, config in self.services_config.get("network_services", {}).items():
            if config.get("enabled", False):
                status = await self._check_network_service_status(service_id, config)
                services.append({
                    "id": service_id,
                    "name": config["name"],
                    "type": config["type"],
                    "description": config["description"],
                    "status": status["status"],
                    "port": config.get("port"),
                    "actions": self._get_available_actions(service_id, status["status"]),
                    "last_check": status.get("last_check"),
                    "details": status.get("details", {})
                })
        
        return {
            "services": services,
            "total": len(services),
            "summary": {
                "running": len([s for s in services if s["status"] == ServiceStatus.RUNNING.value]),
                "stopped": len([s for s in services if s["status"] == ServiceStatus.STOPPED.value]),
                "error": len([s for s in services if s["status"] == ServiceStatus.ERROR.value]),
                "configured": len([s for s in services if s["status"] == ServiceStatus.CONFIGURED.value])
            }
        }
    
    async def _check_daemon_status(self, daemon_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check the status of a daemon service."""
        try:
            # Try to import and use the daemon manager
            if daemon_id not in self._daemon_managers:
                # Lazy import to avoid circular dependencies
                import sys
                import importlib.util
                
                # Try to import the daemon manager
                daemon_manager_path = Path(__file__).parent.parent.parent.parent / "scripts" / "daemon" / "daemon_manager.py"
                if daemon_manager_path.exists():
                    spec = importlib.util.spec_from_file_location("daemon_manager", daemon_manager_path)
                    daemon_manager_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(daemon_manager_module)
                    DaemonManager = daemon_manager_module.DaemonManager
                    
                    self._daemon_managers[daemon_id] = DaemonManager(
                        daemon_type=daemon_id,
                        config_dir=config.get("config_dir"),
                        api_port=config.get("port")
                    )
                else:
                    # Fallback to mock daemon manager
                    logger.warning(f"Daemon manager not found, using mock for {daemon_id}")
                    self._daemon_managers[daemon_id] = MockDaemonManager(daemon_id)
            
            daemon_manager = self._daemon_managers[daemon_id]
            status_info = daemon_manager.get_status()
            
            return {
                "status": ServiceStatus.RUNNING.value if status_info.get("running", False) else ServiceStatus.STOPPED.value,
                "last_check": datetime.now().isoformat(),
                "details": {
                    "initialized": status_info.get("initialized", False),
                    "config_dir": status_info.get("config_dir"),
                    "api_port": status_info.get("api_port"),
                    "pid": status_info.get("pid")
                }
            }
        except Exception as e:
            logger.error(f"Error checking daemon {daemon_id} status: {e}")
            return {
                "status": ServiceStatus.ERROR.value,
                "last_check": datetime.now().isoformat(),
                "details": {"error": str(e)}
            }
    
    async def _check_storage_backend_status(self, backend_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check the status of a storage backend service."""
        # Check if credentials are configured
        credentials_file = self.data_dir / f"{backend_id}_credentials.json"
        
        if config.get("requires_credentials", False):
            if not credentials_file.exists():
                return {
                    "status": ServiceStatus.MISSING.value,
                    "last_check": datetime.now().isoformat(),
                    "details": {"error": "Credentials not configured"}
                }
            
            try:
                with open(credentials_file, 'r') as f:
                    creds = json.load(f)
                    required_keys = config.get("config_keys", [])
                    missing_keys = [key for key in required_keys if key not in creds]
                    
                    if missing_keys:
                        return {
                            "status": ServiceStatus.ERROR.value,
                            "last_check": datetime.now().isoformat(),
                            "details": {"error": f"Missing credential keys: {missing_keys}"}
                        }
                    
                    # TODO: Add actual connectivity tests for each backend
                    return {
                        "status": ServiceStatus.CONFIGURED.value,
                        "last_check": datetime.now().isoformat(),
                        "details": {"configured_keys": list(creds.keys())}
                    }
            except Exception as e:
                return {
                    "status": ServiceStatus.ERROR.value,
                    "last_check": datetime.now().isoformat(),
                    "details": {"error": f"Invalid credentials: {str(e)}"}
                }
        else:
            return {
                "status": ServiceStatus.CONFIGURED.value,
                "last_check": datetime.now().isoformat(),
                "details": {"requires_credentials": False}
            }
    
    async def _check_network_service_status(self, service_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check the status of a network service."""
        # For MCP server, check if it's running on the configured port
        if service_id == "mcp_server":
            port = config.get("port", 8004)
            try:
                # Simple port check
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                
                if result == 0:
                    return {
                        "status": ServiceStatus.RUNNING.value,
                        "last_check": datetime.now().isoformat(),
                        "details": {"port": port, "listening": True}
                    }
                else:
                    return {
                        "status": ServiceStatus.STOPPED.value,
                        "last_check": datetime.now().isoformat(),
                        "details": {"port": port, "listening": False}
                    }
            except Exception as e:
                return {
                    "status": ServiceStatus.ERROR.value,
                    "last_check": datetime.now().isoformat(),
                    "details": {"error": str(e)}
                }
        
        # Default status for other network services
        return {
            "status": ServiceStatus.UNKNOWN.value,
            "last_check": datetime.now().isoformat(),
            "details": {}
        }
    
    def _get_available_actions(self, service_id: str, status: str) -> List[str]:
        """Get available actions for a service based on its current status."""
        actions = []
        
        if status == ServiceStatus.RUNNING.value:
            actions.extend(["stop", "restart", "health_check", "view_logs"])
        elif status == ServiceStatus.STOPPED.value:
            actions.extend(["start", "configure"])
        elif status == ServiceStatus.ERROR.value:
            actions.extend(["restart", "configure", "view_logs"])
        elif status == ServiceStatus.CONFIGURED.value:
            actions.extend(["start", "configure"])
        elif status == ServiceStatus.MISSING.value:
            actions.extend(["configure"])
        
        return actions
    
    async def perform_service_action(self, service_id: str, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform an action on a service."""
        try:
            if action == "start":
                return await self._start_service(service_id, params)
            elif action == "stop":
                return await self._stop_service(service_id, params)
            elif action == "restart":
                return await self._restart_service(service_id, params)
            elif action == "configure":
                return await self._configure_service(service_id, params)
            elif action == "health_check":
                return await self._health_check_service(service_id, params)
            elif action == "view_logs":
                return await self._view_service_logs(service_id, params)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"Error performing action {action} on service {service_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _start_service(self, service_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a service."""
        if service_id in self._daemon_managers:
            daemon_manager = self._daemon_managers[service_id]
            success = daemon_manager.start()
            return {
                "success": success,
                "message": f"Service {service_id} {'started successfully' if success else 'failed to start'}"
            }
        
        return {"success": False, "error": f"Service {service_id} cannot be started"}
    
    async def _stop_service(self, service_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Stop a service."""
        if service_id in self._daemon_managers:
            daemon_manager = self._daemon_managers[service_id]
            success = daemon_manager.stop()
            return {
                "success": success,
                "message": f"Service {service_id} {'stopped successfully' if success else 'failed to stop'}"
            }
        
        return {"success": False, "error": f"Service {service_id} cannot be stopped"}
    
    async def _restart_service(self, service_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Restart a service."""
        stop_result = await self._stop_service(service_id, params)
        if stop_result.get("success", False):
            # Wait a moment before restarting
            await asyncio.sleep(2)
            return await self._start_service(service_id, params)
        return stop_result
    
    async def _configure_service(self, service_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Configure a service."""
        if not params:
            return {"success": False, "error": "Configuration parameters required"}
        
        # Save configuration for credentialed services
        service_config = self._find_service_config(service_id)
        if service_config and service_config.get("requires_credentials", False):
            credentials_file = self.data_dir / f"{service_id}_credentials.json"
            try:
                with open(credentials_file, 'w') as f:
                    json.dump(params, f, indent=2)
                return {"success": True, "message": f"Service {service_id} configured successfully"}
            except Exception as e:
                return {"success": False, "error": f"Failed to save configuration: {str(e)}"}
        
        return {"success": False, "error": f"Service {service_id} does not support configuration"}
    
    async def _health_check_service(self, service_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform health check on a service."""
        service_config = self._find_service_config(service_id)
        if not service_config:
            return {"success": False, "error": f"Service {service_id} not found"}
        
        if service_config["type"] == ServiceType.DAEMON.value:
            status = await self._check_daemon_status(service_id, service_config)
        elif service_config["type"] == ServiceType.STORAGE.value:
            status = await self._check_storage_backend_status(service_id, service_config)
        elif service_config["type"] == ServiceType.NETWORK.value:
            status = await self._check_network_service_status(service_id, service_config)
        else:
            return {"success": False, "error": f"Unknown service type for {service_id}"}
        
        return {"success": True, "health_status": status}
    
    async def _view_service_logs(self, service_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """View logs for a service."""
        # TODO: Implement log viewing functionality
        return {
            "success": True,
            "logs": f"Log viewing for {service_id} not yet implemented",
            "message": "Feature coming soon"
        }
    
    def _find_service_config(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Find service configuration by service ID."""
        for category in ["daemons", "storage_backends", "network_services"]:
            if service_id in self.services_config.get(category, {}):
                return self.services_config[category][service_id]
        return None
    
    async def get_service_details(self, service_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific service."""
        service_config = self._find_service_config(service_id)
        if not service_config:
            return {"error": f"Service {service_id} not found"}
        
        # Get current status
        if service_config["type"] == ServiceType.DAEMON.value:
            status = await self._check_daemon_status(service_id, service_config)
        elif service_config["type"] == ServiceType.STORAGE.value:
            status = await self._check_storage_backend_status(service_id, service_config)
        elif service_config["type"] == ServiceType.NETWORK.value:
            status = await self._check_network_service_status(service_id, service_config)
        else:
            status = {"status": ServiceStatus.UNKNOWN.value, "details": {}}
        
        return {
            "id": service_id,
            "config": service_config,
            "status": status,
            "actions": self._get_available_actions(service_id, status["status"])
        }
    
    def enable_service(self, service_id: str) -> Dict[str, Any]:
        """Enable a service."""
        service_config = self._find_service_config(service_id)
        if not service_config:
            return {"success": False, "error": f"Service {service_id} not found"}
        
        service_config["enabled"] = True
        self._save_services_config()
        return {"success": True, "message": f"Service {service_id} enabled"}
    
    def disable_service(self, service_id: str) -> Dict[str, Any]:
        """Disable a service."""
        service_config = self._find_service_config(service_id)
        if not service_config:
            return {"success": False, "error": f"Service {service_id} not found"}
        
        service_config["enabled"] = False
        self._save_services_config()
        return {"success": True, "message": f"Service {service_id} disabled"}
    
    def auto_enable_detectable_services(self) -> Dict[str, Any]:
        """Auto-enable services that can be detected on the system."""
        enabled_services = []
        
        # Check for IPFS daemon
        if self._check_binary_available("ipfs"):
            ipfs_config = self._find_service_config("ipfs")
            if ipfs_config and not ipfs_config.get("enabled", False):
                ipfs_config["enabled"] = True
                enabled_services.append("ipfs")
        
        # Check for other daemons
        daemon_checks = {
            "lotus": "lotus",
            "aria2": "aria2c",
            "ipfs_cluster": "ipfs-cluster-service"
        }
        
        for daemon_id, binary_name in daemon_checks.items():
            if self._check_binary_available(binary_name):
                daemon_config = self._find_service_config(daemon_id)
                if daemon_config and not daemon_config.get("enabled", False):
                    daemon_config["enabled"] = True
                    enabled_services.append(daemon_id)
        
        if enabled_services:
            self._save_services_config()
        
        return {
            "success": True,
            "enabled_services": enabled_services,
            "message": f"Auto-enabled {len(enabled_services)} detectable services"
        }
    
    def _check_binary_available(self, binary_name: str) -> bool:
        """Check if a binary is available in the system PATH."""
        import shutil
        return shutil.which(binary_name) is not None
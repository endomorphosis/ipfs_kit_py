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
        
        # Load and merge individual service configurations
        self._load_individual_service_configs()
        
        # Initialize daemon manager references
        self._daemon_managers = {}
        
        logger.info("Comprehensive Service Manager initialized")
    
    def _load_individual_service_configs(self):
        """Load individual service configuration files and merge them with the main config."""
        try:
            # Check for individual service config files
            for config_file in self.data_dir.glob("*_config.json"):
                try:
                    service_id = config_file.stem.replace("_config", "")
                    with open(config_file, 'r') as f:
                        saved_config = json.load(f)
                    
                    # Find the service in services_config and merge the saved config
                    service_config = self._find_service_config(service_id)
                    if service_config:
                        # Merge saved configuration into service config
                        for key, value in saved_config.items():
                            if key in service_config.get("config_keys", []):
                                service_config[key] = value
                        logger.info(f"Loaded saved configuration for {service_id}")
                except Exception as e:
                    logger.error(f"Error loading config file {config_file}: {e}")
        except Exception as e:
            logger.error(f"Error loading individual service configs: {e}")
    
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
                    "auto_start": True,
                    "config_keys": ["config_dir", "port", "gateway_port", "swarm_port", "auto_start"],
                    "config_hints": {
                        "config_dir": "Directory where IPFS configuration and data files are stored",
                        "port": "IPFS API port (default: 5001)",
                        "gateway_port": "IPFS Gateway port for HTTP access (default: 8080)",
                        "swarm_port": "IPFS Swarm port for peer communication (default: 4001)",
                        "auto_start": "Automatically start daemon on system boot"
                    }
                },
                "lotus": {
                    "type": ServiceType.DAEMON.value,
                    "name": "Lotus Client",
                    "description": "Filecoin Lotus client for decentralized storage",
                    "port": 1234,
                    "config_dir": str(Path.home() / ".lotus"),
                    "enabled": False,
                    "auto_start": False,
                    "config_keys": ["config_dir", "port", "auto_start"],
                    "config_hints": {
                        "config_dir": "Directory where Lotus configuration and data files are stored",
                        "port": "Lotus API port (default: 1234)",
                        "auto_start": "Automatically start daemon on system boot"
                    }
                },
                "aria2": {
                    "type": ServiceType.DAEMON.value,
                    "name": "Aria2 Daemon",
                    "description": "High-speed download daemon for content retrieval",
                    "port": 6800,
                    "config_dir": str(Path.home() / ".aria2"),
                    "enabled": False,
                    "auto_start": False,
                    "config_keys": ["config_dir", "port", "auto_start", "rpc_secret"],
                    "config_hints": {
                        "config_dir": "Directory where Aria2 configuration files are stored",
                        "port": "Aria2 RPC port (default: 6800)",
                        "auto_start": "Automatically start daemon on system boot",
                        "rpc_secret": "RPC secret token for authentication"
                    }
                },
                "ipfs_cluster": {
                    "type": ServiceType.DAEMON.value,
                    "name": "IPFS Cluster",
                    "description": "IPFS Cluster daemon for coordinated pin management",
                    "port": 9094,
                    "config_dir": str(Path.home() / ".ipfs-cluster"),
                    "enabled": False,
                    "auto_start": False,
                    "config_keys": ["config_dir", "port", "auto_start", "cluster_secret", "bootstrap_peers"],
                    "config_hints": {
                        "config_dir": "Directory where IPFS Cluster configuration is stored",
                        "port": "IPFS Cluster API port (default: 9094)",
                        "auto_start": "Automatically start daemon on system boot",
                        "cluster_secret": "Shared secret for cluster authentication",
                        "bootstrap_peers": "Comma-separated list of bootstrap peer multiaddresses"
                    }
                },
                "ipfs_cluster_follow": {
                    "type": ServiceType.DAEMON.value,
                    "name": "IPFS Cluster Follow",
                    "description": "IPFS Cluster Follow service for remote cluster synchronization",
                    "port": 9096,
                    "config_dir": str(Path.home() / ".ipfs-cluster-follow"),
                    "enabled": False,
                    "auto_start": False,
                    "config_keys": ["config_dir", "port", "auto_start", "remote_cluster"],
                    "config_hints": {
                        "config_dir": "Directory where IPFS Cluster Follow configuration is stored",
                        "port": "IPFS Cluster Follow API port (default: 9096)",
                        "auto_start": "Automatically start daemon on system boot",
                        "remote_cluster": "Remote cluster multiaddress to follow"
                    }
                },
                "lassie": {
                    "type": ServiceType.DAEMON.value,
                    "name": "Lassie Retrieval Client",
                    "description": "High-performance Filecoin retrieval client for IPFS content",
                    "port": 8080,
                    "config_dir": str(Path.home() / ".lassie"),
                    "enabled": False,
                    "auto_start": False,
                    "config_keys": ["config_dir", "port", "auto_start"],
                    "config_hints": {
                        "config_dir": "Directory where Lassie configuration is stored",
                        "port": "Lassie HTTP server port (default: 8080)",
                        "auto_start": "Automatically start daemon on system boot"
                    }
                },
                "libp2p": {
                    "type": ServiceType.DAEMON.value,
                    "name": "libp2p-py Daemon",
                    "description": "Python libp2p networking daemon for peer-to-peer communication",
                    "port": 4002,
                    "config_dir": str(Path.home() / ".libp2p"),
                    "enabled": False,
                    "auto_start": False,
                    "config_keys": ["config_dir", "port", "auto_start"],
                    "config_hints": {
                        "config_dir": "Directory where libp2p configuration is stored",
                        "port": "libp2p listening port (default: 4002)",
                        "auto_start": "Automatically start daemon on system boot"
                    }
                },
                "ipfs_kit": {
                    "type": ServiceType.DAEMON.value,
                    "name": "IPFS Kit Daemon",
                    "description": "IPFS Kit background daemon for automated operations",
                    "port": 5002,
                    "config_dir": str(Path.home() / ".ipfs_kit"),
                    "enabled": True,
                    "auto_start": False,
                    "config_keys": ["config_dir", "port", "auto_start"],
                    "config_hints": {
                        "config_dir": "Directory where IPFS Kit configuration and data are stored",
                        "port": "IPFS Kit daemon API port (default: 5002)",
                        "auto_start": "Automatically start daemon on system boot"
                    }
                }
            },
            "storage_backends": {
                "s3": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Amazon S3",
                    "description": "Amazon Simple Storage Service backend",
                    "requires_credentials": True,
                    "config_keys": ["access_key", "secret_key", "endpoint", "bucket", "region"],
                    "config_hints": {
                        "access_key": "AWS Access Key ID (e.g., AKIA...)",
                        "secret_key": "AWS Secret Access Key",
                        "endpoint": "S3 endpoint URL (optional, defaults to AWS)",
                        "bucket": "S3 bucket name",
                        "region": "AWS region (e.g., us-east-1)"
                    },
                    "enabled": False
                },
                "huggingface": {
                    "type": ServiceType.STORAGE.value,
                    "name": "HuggingFace Hub",
                    "description": "HuggingFace model and dataset repository",
                    "requires_credentials": True,
                    "config_keys": ["api_token", "username", "repository"],
                    "config_hints": {
                        "api_token": "HuggingFace API token (from huggingface.co/settings/tokens)",
                        "username": "HuggingFace username",
                        "repository": "Repository name (optional)"
                    },
                    "enabled": False
                },
                "github": {
                    "type": ServiceType.STORAGE.value,
                    "name": "GitHub Storage",
                    "description": "GitHub repository storage backend",
                    "requires_credentials": True,
                    "config_keys": ["api_token", "repository", "username"],
                    "config_hints": {
                        "api_token": "GitHub Personal Access Token (from github.com/settings/tokens)",
                        "repository": "Repository (owner/repo format)",
                        "username": "GitHub username"
                    },
                    "enabled": False
                },
                "storacha": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Storacha",
                    "description": "Storacha decentralized storage service",
                    "requires_credentials": True,
                    "config_keys": ["api_token", "space"],
                    "config_hints": {
                        "api_token": "Storacha API token",
                        "space": "Storacha space identifier"
                    },
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
                    "config_hints": {
                        "host": "FTP server hostname or IP",
                        "port": "FTP port (default: 21)",
                        "username": "FTP username",
                        "password": "FTP password"
                    },
                    "enabled": False
                },
                "sshfs": {
                    "type": ServiceType.STORAGE.value,
                    "name": "SSHFS",
                    "description": "SSH Filesystem storage backend",
                    "requires_credentials": True,
                    "config_keys": ["host", "port", "username", "password"],
                    "config_hints": {
                        "host": "SSH server hostname or IP",
                        "port": "SSH port (default: 22)",
                        "username": "SSH username",
                        "password": "SSH password or leave empty for key-based auth"
                    },
                    "enabled": False
                },
                "apache_arrow": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Apache Arrow",
                    "description": "In-memory columnar data format for analytics and data processing",
                    "requires_credentials": False,
                    "config_keys": ["memory_pool", "compression"],
                    "enabled": True
                },
                "parquet": {
                    "type": ServiceType.STORAGE.value,
                    "name": "Parquet Storage",
                    "description": "Columnar storage format optimized for analytics workloads",
                    "requires_credentials": False,
                    "config_keys": ["compression_codec", "row_group_size", "schema_validation"],
                    "enabled": True
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
                service_info = {
                    "id": backend_id,
                    "name": config["name"],
                    "type": config["type"],
                    "description": config["description"],
                    "status": status["status"],
                    "requires_credentials": config.get("requires_credentials", False),
                    "actions": self._get_available_actions(backend_id, status["status"]),
                    "last_check": status.get("last_check"),
                    "details": status.get("details", {})
                }
                # Add config_keys and config_hints if available
                if "config_keys" in config:
                    service_info["config_keys"] = config["config_keys"]
                if "config_hints" in config:
                    service_info["config_hints"] = config["config_hints"]
                services.append(service_info)
        
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
        """Check the status of a daemon service using port checking and process detection."""
        try:
            import socket
            import shutil
            
            # Check if binary exists
            binary_map = {
                "ipfs": "ipfs",
                "lotus": "lotus",
                "aria2": "aria2c",
                "ipfs_cluster": "ipfs-cluster-service",
                "ipfs_cluster_follow": "ipfs-cluster-follow",
                "lassie": "lassie",
                "libp2p": "libp2p-daemon",
                "ipfs_kit": "ipfs-kit"
            }
            
            binary_name = binary_map.get(daemon_id)
            binary_path = shutil.which(binary_name) if binary_name else None
            
            if not binary_path:
                return {
                    "status": ServiceStatus.MISSING.value,
                    "last_check": datetime.now().isoformat(),
                    "details": {
                        "binary": binary_name,
                        "error": f"Binary '{binary_name}' not found in PATH"
                    }
                }
            
            # Check if service is running by checking the port
            port = config.get("port")
            if port:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex(('127.0.0.1', port))
                    sock.close()
                    
                    if result == 0:
                        # Port is open, service is running
                        return {
                            "status": ServiceStatus.RUNNING.value,
                            "last_check": datetime.now().isoformat(),
                            "details": {
                                "binary_path": binary_path,
                                "config_dir": config.get("config_dir"),
                                "api_port": port,
                                "api_port_open": True
                            }
                        }
                    else:
                        # Port is closed, service is stopped
                        return {
                            "status": ServiceStatus.STOPPED.value,
                            "last_check": datetime.now().isoformat(),
                            "details": {
                                "binary_path": binary_path,
                                "config_dir": config.get("config_dir"),
                                "api_port": port,
                                "api_port_open": False,
                                "reason": "Port not accessible"
                            }
                        }
                except Exception as port_error:
                    logger.debug(f"Port check failed for {daemon_id}: {port_error}")
                    return {
                        "status": ServiceStatus.STOPPED.value,
                        "last_check": datetime.now().isoformat(),
                        "details": {
                            "binary_path": binary_path,
                            "config_dir": config.get("config_dir"),
                            "api_port": port,
                            "api_port_open": False,
                            "reason": str(port_error)
                        }
                    }
            else:
                # No port configured, can't check status, assume configured
                return {
                    "status": ServiceStatus.CONFIGURED.value,
                    "last_check": datetime.now().isoformat(),
                    "details": {
                        "binary_path": binary_path,
                        "config_dir": config.get("config_dir"),
                        "reason": "No port configured to check status"
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
            elif action == "enable":
                return self.enable_service(service_id)
            elif action == "disable":
                return self.disable_service(service_id)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"Error performing action {action} on service {service_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _start_service(self, service_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a service."""
        try:
            # Load and apply saved configuration before starting
            config_file = self.data_dir / f"{service_id}_config.json"
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        saved_config = json.load(f)
                    
                    # Apply the saved configuration
                    apply_result = await self._apply_service_config(service_id, saved_config)
                    logger.info(f"Applied saved configuration for {service_id}: {apply_result.get('message', '')}")
                except Exception as e:
                    logger.warning(f"Could not apply saved configuration for {service_id}: {e}")
            
            # Now start the service
            if service_id in self._daemon_managers:
                daemon_manager = self._daemon_managers[service_id]
                success = daemon_manager.start()
                return {
                    "success": success,
                    "message": f"Service {service_id} {'started successfully' if success else 'failed to start'}"
                }
            
            return {"success": False, "error": f"Service {service_id} cannot be started"}
        except Exception as e:
            logger.error(f"Error starting service {service_id}: {e}")
            return {"success": False, "error": str(e)}
    
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
        
        # Use the comprehensive configure_service method for all services
        return await self.configure_service(service_id, params)
    
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
            return {"success": False, "error": f"Service {service_id} not found"}
        
        # Load saved configuration if it exists
        config_file = self.data_dir / f"{service_id}_config.json"
        saved_config = {}
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    saved_config = json.load(f)
                logger.info(f"Loaded saved configuration for {service_id}: {saved_config}")
            except Exception as e:
                logger.error(f"Error loading saved config for {service_id}: {e}")
        
        # Merge saved config with service config for the response
        merged_config = service_config.copy()
        for key, value in saved_config.items():
            merged_config[key] = value
        
        # Get current status
        if service_config["type"] == ServiceType.DAEMON.value:
            status = await self._check_daemon_status(service_id, merged_config)
        elif service_config["type"] == ServiceType.STORAGE.value:
            status = await self._check_storage_backend_status(service_id, merged_config)
        elif service_config["type"] == ServiceType.NETWORK.value:
            status = await self._check_network_service_status(service_id, merged_config)
        else:
            status = {"status": ServiceStatus.UNKNOWN.value, "details": {}}
        
        return {
            "success": True,
            "id": service_id,
            "config": merged_config,
            "status": status.get("status", ServiceStatus.UNKNOWN.value),
            "last_check": status.get("last_check", ""),
            "details": status.get("details", {}),
            "actions": self._get_available_actions(service_id, status.get("status", ServiceStatus.UNKNOWN.value))
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
            "ipfs_cluster": "ipfs-cluster-service",
            "ipfs_cluster_follow": "ipfs-cluster-follow",
            "lassie": "lassie",
            "libp2p": "libp2p-daemon"
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

    async def list_all_services(self) -> Dict[str, Any]:
        """List ALL services (enabled and disabled) for comprehensive dashboard view."""
        services = []
        
        # Add ALL daemon services (regardless of enabled status)
        for daemon_id, config in self.services_config.get("daemons", {}).items():
            if config.get("enabled", False):
                status = await self._check_daemon_status(daemon_id, config)
            else:
                status = {
                    "status": "not_enabled",
                    "last_check": datetime.now().isoformat(),
                    "details": {"enabled": False}
                }
            
            daemon_info = {
                "id": daemon_id,
                "name": config["name"],
                "type": config["type"],
                "description": config["description"],
                "status": status["status"],
                "enabled": config.get("enabled", False),
                "port": config.get("port"),
                "gateway_port": config.get("gateway_port"),
                "swarm_port": config.get("swarm_port"),
                "config_dir": config.get("config_dir"),
                "auto_start": config.get("auto_start", False),
                "actions": self._get_available_actions_for_dashboard(daemon_id, status["status"], config.get("enabled", False)),
                "last_check": status.get("last_check"),
                "details": status.get("details", {})
            }
            
            # Add config_keys and config_hints for daemon configuration
            config_keys = config.get("config_keys", [])
            config_hints = config.get("config_hints", {})
            
            # If config_keys is missing, get it from default config (for backwards compatibility)
            if not config_keys:
                default_config = self._get_default_services_config()
                default_daemon = default_config.get("daemons", {}).get(daemon_id, {})
                config_keys = default_daemon.get("config_keys", [])
                config_hints = default_daemon.get("config_hints", {})
            
            if config_keys:
                daemon_info["config_keys"] = config_keys
            if config_hints:
                daemon_info["config_hints"] = config_hints
            
            services.append(daemon_info)
        
        # Add ALL storage backend services (regardless of enabled status)  
        for backend_id, config in self.services_config.get("storage_backends", {}).items():
            if config.get("enabled", False):
                status = await self._check_storage_backend_status(backend_id, config)
            else:
                # Check if it's configured but not enabled
                credentials_file = self.data_dir / f"{backend_id}_credentials.json"
                if config.get("requires_credentials", False) and not credentials_file.exists():
                    status = {
                        "status": "not_configured", 
                        "last_check": datetime.now().isoformat(),
                        "details": {"enabled": False, "configured": False}
                    }
                else:
                    status = {
                        "status": "not_enabled",
                        "last_check": datetime.now().isoformat(), 
                        "details": {"enabled": False, "configured": True}
                    }
            
            # Get config_keys and config_hints from config, or fall back to defaults
            config_keys = config.get("config_keys", [])
            config_hints = config.get("config_hints", {})
            
            # If config_keys is missing, get it from default config (for backwards compatibility)
            if not config_keys:
                default_config = self._get_default_services_config()
                default_backend = default_config.get("storage_backends", {}).get(backend_id, {})
                config_keys = default_backend.get("config_keys", [])
                config_hints = default_backend.get("config_hints", {})
                        
            services.append({
                "id": backend_id,
                "name": config["name"],
                "type": config["type"],
                "description": config["description"],
                "status": status["status"],
                "enabled": config.get("enabled", False),
                "requires_credentials": config.get("requires_credentials", False),
                "config_keys": config_keys,
                "config_hints": config_hints,
                "actions": self._get_available_actions_for_dashboard(backend_id, status["status"], config.get("enabled", False)),
                "last_check": status.get("last_check"),
                "details": status.get("details", {})
            })
        
        # Add network services
        for service_id, config in self.services_config.get("network_services", {}).items():
            status = await self._check_network_service_status(service_id, config)
            services.append({
                "id": service_id,
                "name": config["name"], 
                "type": config["type"],
                "description": config["description"],
                "status": status["status"],
                "enabled": config.get("enabled", False),
                "port": config.get("port"),
                "actions": self._get_available_actions_for_dashboard(service_id, status["status"], config.get("enabled", False)),
                "last_check": status.get("last_check"),
                "details": status.get("details", {})
            })
        
        return {
            "services": services,
            "total": len(services),
            "summary": {
                "running": len([s for s in services if s["status"] == "running"]),
                "stopped": len([s for s in services if s["status"] == "stopped"]),
                "not_enabled": len([s for s in services if s["status"] == "not_enabled"]),
                "not_configured": len([s for s in services if s["status"] == "not_configured"]),
                "error": len([s for s in services if s["status"] == "error"]),
                "configured": len([s for s in services if s["status"] == "configured"])
            }
        }

    def _get_available_actions_for_dashboard(self, service_id: str, status: str, enabled: bool) -> List[str]:
        """Get available actions for a service in dashboard context."""
        actions = []
        
        if not enabled:
            actions.append("enable")
            if status == "not_configured":
                actions.append("configure")
        else:
            actions.append("disable") 
            
            if status == "running":
                actions.extend(["stop", "restart", "health_check", "view_logs"])
            elif status == "stopped":
                actions.extend(["start", "configure"])
            elif status == "error":
                actions.extend(["restart", "configure", "view_logs"])
            elif status == "configured":
                actions.extend(["start", "configure"])
            elif status == "not_configured":
                actions.extend(["configure"])
        
        return actions

    async def configure_service(self, service_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure a service with the provided configuration."""
        try:
            # Save service configuration to JSON
            config_file = self.data_dir / f"{service_id}_config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Apply configuration to the actual service
            apply_result = await self._apply_service_config(service_id, config)
            
            # Update service configuration in services_config
            service_config = self._find_service_config(service_id)
            if service_config:
                # Update the configuration values in the services_config
                for key, value in config.items():
                    if key in service_config.get("config_keys", []):
                        service_config[key] = value
                self._save_services_config()
            
            # Update service status to configured if it was not_configured
            if service_id in self.service_states:
                if self.service_states[service_id].get("status") == "not_configured":
                    self.service_states[service_id]["status"] = "configured"
                self.service_states[service_id]["last_configured"] = datetime.now().isoformat()
                self.service_states[service_id]["config_applied"] = apply_result.get("applied", False)
                self._save_service_states()
            
            logger.info(f"Service {service_id} configured successfully")
            return {
                "success": True,
                "message": f"Service {service_id} configured successfully",
                "config_saved": True,
                "config_applied": apply_result.get("applied", False),
                "apply_message": apply_result.get("message", "")
            }
            
        except Exception as e:
            logger.error(f"Error configuring service {service_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _apply_service_config(self, service_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply configuration to the actual service by generating the appropriate config file."""
        try:
            service_config = self._find_service_config(service_id)
            if not service_config:
                return {"applied": False, "message": "Service configuration not found"}
            
            # Determine the service type and apply configuration accordingly
            if service_id == "ipfs":
                return await self._apply_ipfs_config(config)
            elif service_id == "ipfs_cluster":
                return await self._apply_ipfs_cluster_config(config)
            elif service_id == "lotus":
                return await self._apply_lotus_config(config)
            elif service_id == "aria2":
                return await self._apply_aria2_config(config)
            elif service_id == "lassie":
                return await self._apply_lassie_config(config)
            elif service_config.get("type") == ServiceType.STORAGE.value:
                # For storage backends, configuration is credential-based
                return await self._apply_storage_backend_config(service_id, config)
            else:
                # For other services, just save the config
                return {"applied": False, "message": "Service does not support automatic configuration"}
            
        except Exception as e:
            logger.error(f"Error applying configuration for {service_id}: {e}")
            return {"applied": False, "message": f"Error: {str(e)}"}
    
    async def _apply_ipfs_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply IPFS configuration by modifying the IPFS config file."""
        try:
            import subprocess
            
            # IPFS uses JSON configuration
            config_dir = Path(config.get("config_dir", Path.home() / ".ipfs"))
            config_file = config_dir / "config"
            
            if not config_file.exists():
                return {"applied": False, "message": "IPFS not initialized. Run 'ipfs init' first."}
            
            # Read existing config
            with open(config_file, 'r') as f:
                ipfs_config = json.load(f)
            
            # Apply configuration changes
            if "port" in config:
                if "Addresses" not in ipfs_config:
                    ipfs_config["Addresses"] = {}
                ipfs_config["Addresses"]["API"] = f"/ip4/127.0.0.1/tcp/{config['port']}"
            
            if "gateway_port" in config:
                if "Addresses" not in ipfs_config:
                    ipfs_config["Addresses"] = {}
                ipfs_config["Addresses"]["Gateway"] = f"/ip4/127.0.0.1/tcp/{config['gateway_port']}"
            
            if "swarm_port" in config:
                if "Addresses" not in ipfs_config:
                    ipfs_config["Addresses"] = {}
                ipfs_config["Addresses"]["Swarm"] = [
                    f"/ip4/0.0.0.0/tcp/{config['swarm_port']}",
                    f"/ip6/::/tcp/{config['swarm_port']}"
                ]
            
            # Write back the configuration
            with open(config_file, 'w') as f:
                json.dump(ipfs_config, f, indent=2)
            
            return {"applied": True, "message": "IPFS configuration applied successfully"}
            
        except Exception as e:
            logger.error(f"Error applying IPFS config: {e}")
            return {"applied": False, "message": f"Failed to apply IPFS config: {str(e)}"}
    
    async def _apply_ipfs_cluster_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply IPFS Cluster configuration."""
        try:
            # IPFS Cluster uses JSON configuration
            config_dir = Path(config.get("config_dir", Path.home() / ".ipfs-cluster"))
            config_file = config_dir / "service.json"
            
            if not config_file.exists():
                return {"applied": False, "message": "IPFS Cluster not initialized. Run 'ipfs-cluster-service init' first."}
            
            # Read existing config
            with open(config_file, 'r') as f:
                cluster_config = json.load(f)
            
            # Apply configuration changes
            if "port" in config:
                if "api" not in cluster_config:
                    cluster_config["api"] = {}
                if "restapi" not in cluster_config["api"]:
                    cluster_config["api"]["restapi"] = {}
                cluster_config["api"]["restapi"]["http_listen_multiaddress"] = f"/ip4/127.0.0.1/tcp/{config['port']}"
            
            if "cluster_secret" in config:
                cluster_config["cluster"]["secret"] = config["cluster_secret"]
            
            if "bootstrap_peers" in config and config["bootstrap_peers"]:
                peers = [p.strip() for p in config["bootstrap_peers"].split(",") if p.strip()]
                cluster_config["cluster"]["leave_on_shutdown"] = False
                cluster_config["cluster"]["listen_multiaddress"] = [f"/ip4/0.0.0.0/tcp/9096"]
                if "bootstrap" not in cluster_config["cluster"]:
                    cluster_config["cluster"]["bootstrap"] = peers
                else:
                    cluster_config["cluster"]["bootstrap"] = peers
            
            # Write back the configuration
            with open(config_file, 'w') as f:
                json.dump(cluster_config, f, indent=2)
            
            return {"applied": True, "message": "IPFS Cluster configuration applied successfully"}
            
        except Exception as e:
            logger.error(f"Error applying IPFS Cluster config: {e}")
            return {"applied": False, "message": f"Failed to apply IPFS Cluster config: {str(e)}"}
    
    async def _apply_lotus_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Lotus configuration."""
        try:
            # Lotus uses TOML configuration
            config_dir = Path(config.get("config_dir", Path.home() / ".lotus"))
            config_file = config_dir / "config.toml"
            
            if not config_file.exists():
                return {"applied": False, "message": "Lotus not initialized."}
            
            # For TOML, we need the toml library
            try:
                import toml
            except ImportError:
                logger.warning("toml library not available, saving as JSON comment")
                # Fallback: save as a separate JSON file that can be manually converted
                fallback_file = config_dir / "config_updates.json"
                with open(fallback_file, 'w') as f:
                    json.dump(config, f, indent=2)
                return {"applied": False, "message": "TOML library not available. Configuration saved to config_updates.json for manual application."}
            
            # Read existing config
            with open(config_file, 'r') as f:
                lotus_config = toml.load(f)
            
            # Apply configuration changes
            if "port" in config:
                if "API" not in lotus_config:
                    lotus_config["API"] = {}
                lotus_config["API"]["ListenAddress"] = f"/ip4/127.0.0.1/tcp/{config['port']}/http"
            
            # Write back the configuration
            with open(config_file, 'w') as f:
                toml.dump(lotus_config, f)
            
            return {"applied": True, "message": "Lotus configuration applied successfully"}
            
        except Exception as e:
            logger.error(f"Error applying Lotus config: {e}")
            return {"applied": False, "message": f"Failed to apply Lotus config: {str(e)}"}
    
    async def _apply_aria2_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Aria2 configuration."""
        try:
            # Aria2 uses a simple key=value configuration format
            config_dir = Path(config.get("config_dir", Path.home() / ".aria2"))
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "aria2.conf"
            
            # Build aria2 configuration
            aria2_config_lines = []
            
            if "port" in config:
                aria2_config_lines.append(f"rpc-listen-port={config['port']}")
            
            if "rpc_secret" in config:
                aria2_config_lines.append(f"rpc-secret={config['rpc_secret']}")
            
            # Add some default settings
            aria2_config_lines.extend([
                "enable-rpc=true",
                "rpc-allow-origin-all=true",
                "rpc-listen-all=false",
                "continue=true",
                "max-connection-per-server=16",
                "min-split-size=10M",
                "split=10",
                "max-concurrent-downloads=5",
            ])
            
            # Write configuration
            with open(config_file, 'w') as f:
                f.write('\n'.join(aria2_config_lines))
            
            return {"applied": True, "message": "Aria2 configuration applied successfully"}
            
        except Exception as e:
            logger.error(f"Error applying Aria2 config: {e}")
            return {"applied": False, "message": f"Failed to apply Aria2 config: {str(e)}"}
    
    async def _apply_lassie_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Lassie configuration."""
        try:
            # Lassie typically uses environment variables or CLI flags
            # We'll save a JSON config file that can be used with the daemon
            config_dir = Path(config.get("config_dir", Path.home() / ".lassie"))
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.json"
            
            lassie_config = {
                "port": config.get("port", 8080),
                "host": "127.0.0.1"
            }
            
            with open(config_file, 'w') as f:
                json.dump(lassie_config, f, indent=2)
            
            return {"applied": True, "message": "Lassie configuration applied successfully"}
            
        except Exception as e:
            logger.error(f"Error applying Lassie config: {e}")
            return {"applied": False, "message": f"Failed to apply Lassie config: {str(e)}"}
    
    async def _apply_storage_backend_config(self, service_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply configuration for storage backends (credential-based services)."""
        try:
            # Storage backends are configured through environment variables or credential files
            # We'll save credentials securely
            credentials_file = self.data_dir / f"{service_id}_credentials.json"
            
            # Save credentials
            with open(credentials_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Set restrictive permissions on credentials file (Unix-like systems)
            try:
                os.chmod(credentials_file, 0o600)
            except Exception:
                pass  # Windows or permission error
            
            return {"applied": True, "message": f"{service_id} credentials saved successfully"}
            
        except Exception as e:
            logger.error(f"Error applying {service_id} config: {e}")
            return {"applied": False, "message": f"Failed to save {service_id} credentials: {str(e)}"}

    def enable_service(self, service_id: str) -> Dict[str, Any]:
        """Enable a service."""
        try:
            # Update service configuration to enable it
            service_found = False
            for service_group in ["daemons", "storage_backends", "network_services"]:
                if service_id in self.services_config.get(service_group, {}):
                    self.services_config[service_group][service_id]["enabled"] = True
                    service_found = True
                    break
            
            if not service_found:
                return {
                    "success": False,
                    "error": f"Service {service_id} not found"
                }
            
            self._save_services_config()
            
            logger.info(f"Service {service_id} enabled successfully")
            return {
                "success": True,
                "message": f"Service {service_id} enabled successfully"
            }
            
        except Exception as e:
            logger.error(f"Error enabling service {service_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }


        
        return actions
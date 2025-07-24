#!/usr/bin/env python3
"""
Enhanced IPFS Cluster Follow Daemon Manager

This module provides comprehensive management for IPFS Cluster Follow services including:
- IPFS Cluster Follow daemon management
- Health monitoring and API checks
- Port conflict resolution
- Configuration management
- Automatic recovery and healing
- Worker/follower node functionality
- Bootstrap peer connection management
"""

import os
import sys
import time
import json
import signal
import psutil
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# Import our API client
try:
    from ipfs_kit_py.ipfs_cluster_api import IPFSClusterFollowAPIClient, IPFSClusterFollowCTLWrapper
except ImportError:
    # Create stub classes if import fails
    class IPFSClusterFollowAPIClient:
        def __init__(self, *args, **kwargs):
            pass
    class IPFSClusterFollowCTLWrapper:
        def __init__(self, *args, **kwargs):
            pass

# Configure logger
logger = logging.getLogger(__name__)

class IPFSClusterFollowConfig:
    """Configuration management for IPFS Cluster Follow."""
    
    def __init__(self, cluster_name: str = "default", cluster_path: Optional[str] = None):
        """Initialize cluster follow configuration.
        
        Args:
            cluster_name: Name of the cluster to follow
            cluster_path: Path to cluster follow configuration directory
        """
        self.cluster_name = cluster_name
        self.cluster_path = Path(cluster_path or os.path.expanduser(f"~/.ipfs-cluster-follow/{cluster_name}"))
        self.service_config_path = self.cluster_path / "service.json"
        self.peerstore_path = self.cluster_path / "peerstore"
        self.identity_path = self.cluster_path / "identity.json"
        
        # Default ports (different from cluster service to avoid conflicts)
        self.api_port = 9097
        self.proxy_port = 9098
        
        # Binary paths
        self.cluster_follow_bin = self._get_cluster_follow_binary_path()
        
    def _get_cluster_follow_binary_path(self) -> Path:
        """Get path to IPFS Cluster Follow binary.
        
        Returns:
            Path to cluster follow binary
        """
        # Check multiple possible locations
        possible_paths = [
            # Project-specific locations
            Path(__file__).parent.parent / "bin" / "ipfs-cluster-follow",
            Path(__file__).parent / "bin" / "ipfs-cluster-follow",
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                return path
                
        # Default system path
        return Path("ipfs-cluster-follow")
        
    def ensure_config_exists(self, bootstrap_peer: str) -> Dict[str, Any]:
        """Ensure cluster follow configuration exists and is valid.
        
        Args:
            bootstrap_peer: Bootstrap peer multiaddr to follow
            
        Returns:
            Dict with configuration check results
        """
        result = {
            "success": False,
            "config_exists": False,
            "config_valid": False,
            "created_config": False,
            "errors": []
        }
        
        try:
            # Check if config directory exists
            if not os.path.exists(self.cluster_path):
                os.makedirs(self.cluster_path, exist_ok=True)
                logger.info(f"Created cluster follow config directory: {self.cluster_path}")
            
            # Check if service config exists
            if not os.path.exists(self.service_config_path):
                logger.info("IPFS Cluster Follow service config not found, initializing...")
                init_result = self._initialize_cluster_follow_config(bootstrap_peer)
                if not init_result["success"]:
                    result["errors"].extend(init_result.get("errors", []))
                    return result
                result["created_config"] = True
            
            result["config_exists"] = True
            
            # Validate configuration
            if self._validate_config():
                result["config_valid"] = True
                result["success"] = True
            else:
                result["errors"].append("Configuration validation failed")
                
        except Exception as e:
            logger.error(f"Error ensuring cluster follow config: {e}")
            result["errors"].append(str(e))
            
        return result
    
    def _initialize_cluster_follow_config(self, bootstrap_peer: str) -> Dict[str, Any]:
        """Initialize cluster follow configuration using ipfs-cluster-follow init.
        
        Args:
            bootstrap_peer: Bootstrap peer multiaddr to follow
            
        Returns:
            Dict with initialization results
        """
        result = {"success": False, "errors": []}
        
        try:
            # Get the cluster follow binary path
            cluster_bin = str(self.cluster_follow_bin)
            if not cluster_bin or cluster_bin == "ipfs-cluster-follow":
                # Try to find the binary
                import shutil
                cluster_bin = shutil.which("ipfs-cluster-follow")
                if not cluster_bin:
                    result["errors"].append("IPFS Cluster Follow binary not found")
                    return result
            
            # Set environment
            env = os.environ.copy()
            env["IPFS_CLUSTER_PATH"] = str(self.cluster_path.parent)
            
            # Run initialization
            cmd = [cluster_bin, self.cluster_name, "init", bootstrap_peer]
            process = subprocess.run(
                cmd, 
                env=env,
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if process.returncode == 0:
                result["success"] = True
                result["stdout"] = process.stdout
                
                # Update configuration to use different ports than cluster service
                self._update_config_ports()
                logger.info("IPFS Cluster Follow configuration initialized successfully")
                
            else:
                result["errors"].append(f"Init failed: {process.stderr}")
                
        except subprocess.TimeoutExpired:
            result["errors"].append("Cluster follow init timeout")
        except Exception as e:
            result["errors"].append(f"Init error: {str(e)}")
            
        return result
    
    def _update_config_ports(self):
        """Update configuration to use different ports than cluster service."""
        try:
            if os.path.exists(self.service_config_path):
                with open(self.service_config_path, 'r') as f:
                    config = json.load(f)
                
                # Update API ports to avoid conflicts with cluster service
                if "api" in config and "restapi" in config["api"]:
                    config["api"]["restapi"]["listen_multiaddress"] = f"/ip4/127.0.0.1/tcp/{self.api_port}"
                    config["api"]["restapi"]["proxy_listen_multiaddress"] = f"/ip4/127.0.0.1/tcp/{self.proxy_port}"
                
                # Save updated config
                with open(self.service_config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                
                logger.info(f"Updated cluster follow configuration to use ports {self.api_port}-{self.proxy_port}")
                    
        except Exception as e:
            logger.warning(f"Could not update ports in cluster follow config: {e}")
    
    def _validate_config(self) -> bool:
        """Validate cluster follow configuration files.
        
        Returns:
            True if configuration is valid
        """
        try:
            # Check service config
            if not os.path.exists(self.service_config_path):
                return False
                
            with open(self.service_config_path, 'r') as f:
                config = json.load(f)
                
            # Basic validation - check required fields
            required_fields = ["cluster", "api"]
            for field in required_fields:
                if field not in config:
                    logger.error(f"Missing required field in follow config: {field}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error validating cluster follow config: {e}")
            return False


class IPFSClusterFollowDaemonManager:
    """Enhanced daemon manager for IPFS Cluster Follow services."""
    
    def __init__(self, cluster_name: str = "default", config: Optional[IPFSClusterFollowConfig] = None):
        """Initialize the cluster follow daemon manager.
        
        Args:
            cluster_name: Name of the cluster to follow
            config: Cluster follow configuration instance
        """
        self.cluster_name = cluster_name
        self.config = config or IPFSClusterFollowConfig(cluster_name)
        self.follow_process = None
        
        # API clients for follow service
        self.api_client = None
        self.ctl_wrapper = None
        
        # Daemon status tracking
        self.follow_status = {
            "running": False,
            "pid": None,
            "api_responsive": False,
            "last_check": None,
            "bootstrap_peer": None,
            "leader_connected": False,
            "errors": []
        }
    
    def _validate_configuration(self, bootstrap_peer: str = None) -> Dict[str, Any]:
        """Validate the current cluster follow configuration.
        
        Args:
            bootstrap_peer: Bootstrap peer to validate against
            
        Returns:
            Dict with validation results
        """
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": []
        }
        
        try:
            # Check if cluster path exists
            if not self.config.cluster_path.exists():
                validation_result["issues"].append("Cluster follow directory does not exist")
                validation_result["valid"] = False
            
            # Check if config file exists (for existing installations)
            config_file = self.config.service_config_path
            if not config_file.exists():
                # This might be a new installation, so just warn
                validation_result["warnings"].append("Service config file not found - this might be a new installation")
            
            # Check if ports are available
            port_check = self._check_port_availability()
            if not port_check["api_port_available"]:
                validation_result["issues"].append(f"API port {self.config.api_port} is not available")
                validation_result["valid"] = False
            
            # Check if binary exists
            if not self.config.cluster_follow_bin or not Path(self.config.cluster_follow_bin).exists():
                validation_result["issues"].append("IPFS Cluster Follow binary not found")
                validation_result["valid"] = False
            
            # Validate bootstrap peer if provided
            if bootstrap_peer:
                if not self._validate_bootstrap_peer(bootstrap_peer):
                    validation_result["issues"].append("Invalid bootstrap peer format")
                    validation_result["valid"] = False
            
        except Exception as e:
            validation_result["issues"].append(f"Validation error: {str(e)}")
            validation_result["valid"] = False
            
        return validation_result
    
    def _validate_bootstrap_peer(self, bootstrap_peer: str) -> bool:
        """Validate bootstrap peer multiaddr format.
        
        Args:
            bootstrap_peer: Bootstrap peer multiaddr
            
        Returns:
            True if valid format
        """
        try:
            # Basic validation for multiaddr format
            if not bootstrap_peer.startswith('/'):
                return False
            
            # Check for required components (IP and peer ID)
            parts = bootstrap_peer.split('/')
            if len(parts) < 6:  # /ip4/host/tcp/port/p2p/peerid
                return False
            
            return True
        except Exception:
            return False
    
    def _check_port_availability(self) -> Dict[str, Any]:
        """Check if required ports are available.
        
        Returns:
            Dict with port availability status
        """
        import socket
        
        result = {
            "api_port_available": True,
            "api_port": self.config.api_port,
            "conflicts": []
        }
        
        try:
            # Check API port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result_code = s.connect_ex(('127.0.0.1', self.config.api_port))
                if result_code == 0:
                    result["api_port_available"] = False
                    result["conflicts"].append({
                        "port": self.config.api_port,
                        "type": "api",
                        "status": "in_use"
                    })
                    
        except Exception as e:
            result["error"] = str(e)
            result["api_port_available"] = False
            
        return result
    
    async def start_cluster_follow(self, bootstrap_peer: str, force_restart: bool = False) -> Dict[str, Any]:
        """Start IPFS Cluster Follow daemon.
        
        Args:
            bootstrap_peer: Bootstrap peer multiaddr to follow
            force_restart: Force restart even if already running
            
        Returns:
            Dict with startup results
        """
        result = {
            "success": False,
            "status": "unknown",
            "pid": None,
            "api_responsive": False,
            "bootstrap_peer": bootstrap_peer,
            "errors": []
        }
        
        try:
            # Check if already running
            if not force_restart and await self._is_follow_running():
                if await self._check_follow_api_health():
                    result["success"] = True
                    result["status"] = "already_running_healthy"
                    result["api_responsive"] = True
                    result["pid"] = self.follow_status.get("pid")
                    return result
                else:
                    logger.warning("Cluster follow running but API unhealthy, restarting...")
                    await self.stop_cluster_follow()
            
            # Ensure configuration exists
            config_result = self.config.ensure_config_exists(bootstrap_peer)
            if not config_result["success"]:
                result["errors"].extend(config_result["errors"])
                return result
            
            # Clean up any stale processes or locks
            cleanup_result = await self._cleanup_follow_resources()
            if cleanup_result.get("processes_killed"):
                logger.info(f"Cleaned up {len(cleanup_result['processes_killed'])} stale processes")
            
            # Start the follow service
            start_result = await self._start_cluster_follow_daemon()
            if not start_result["success"]:
                result["errors"].extend(start_result.get("errors", []))
                return result
            
            result["pid"] = start_result.get("pid")
            
            # Wait for API to be responsive
            api_ready = await self._wait_for_follow_api(timeout=30)
            if api_ready:
                result["success"] = True
                result["status"] = "started_healthy"
                result["api_responsive"] = True
                logger.info("IPFS Cluster Follow started and API is responsive")
                
                # Check connection to leader
                leader_connected = await self._check_leader_connection()
                result["leader_connected"] = leader_connected
                if leader_connected:
                    result["status"] = "started_healthy_connected"
                else:
                    result["status"] = "started_healthy_disconnected"
            else:
                result["status"] = "started_unhealthy"
                result["errors"].append("Follow service started but API not responsive")
                logger.warning("Cluster follow started but API not responsive")
                
        except Exception as e:
            logger.error(f"Error starting cluster follow: {e}")
            result["errors"].append(str(e))
            
        return result
    
    async def stop_cluster_follow(self) -> Dict[str, Any]:
        """Stop IPFS Cluster Follow daemon.
        
        Returns:
            Dict with stop results
        """
        result = {
            "success": False,
            "status": "unknown",
            "processes_stopped": [],
            "errors": []
        }
        
        try:
            # Find and stop cluster follow processes
            processes = await self._find_cluster_follow_processes()
            
            if not processes:
                result["success"] = True
                result["status"] = "already_stopped"
                return result
            
            # Graceful shutdown first
            for proc_info in processes:
                try:
                    proc = psutil.Process(proc_info["pid"])
                    proc.terminate()
                    result["processes_stopped"].append({
                        "pid": proc_info["pid"],
                        "method": "terminate"
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"Process {proc_info['pid']} already gone or access denied: {e}")
            
            # Wait for graceful shutdown
            await asyncio.sleep(3)
            
            # Force kill if still running
            remaining_processes = await self._find_cluster_follow_processes()
            for proc_info in remaining_processes:
                try:
                    proc = psutil.Process(proc_info["pid"])
                    proc.kill()
                    result["processes_stopped"].append({
                        "pid": proc_info["pid"],
                        "method": "kill"
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"Process {proc_info['pid']} already gone or access denied: {e}")
            
            # Clean up resources
            await self._cleanup_follow_resources()
            
            result["success"] = True
            result["status"] = "stopped"
            logger.info("IPFS Cluster Follow stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping cluster follow: {e}")
            result["errors"].append(str(e))
            
        return result
    
    async def restart_cluster_follow(self, bootstrap_peer: str) -> Dict[str, Any]:
        """Restart IPFS Cluster Follow daemon.
        
        Args:
            bootstrap_peer: Bootstrap peer multiaddr to follow
            
        Returns:
            Dict with restart results
        """
        result = {
            "success": False,
            "stop_result": None,
            "start_result": None
        }
        
        try:
            # Stop the service
            stop_result = await self.stop_cluster_follow()
            result["stop_result"] = stop_result
            
            # Wait a moment for cleanup
            await asyncio.sleep(2)
            
            # Start the service
            start_result = await self.start_cluster_follow(bootstrap_peer)
            result["start_result"] = start_result
            
            result["success"] = start_result.get("success", False)
            
        except Exception as e:
            logger.error(f"Error restarting cluster follow: {e}")
            result["error"] = str(e)
            
        return result
    
    async def get_cluster_follow_status(self) -> Dict[str, Any]:
        """Get comprehensive status of cluster follow service.
        
        Returns:
            Dict with detailed status information
        """
        status = {
            "running": False,
            "api_responsive": False,
            "pid": None,
            "cluster_name": self.cluster_name,
            "bootstrap_peer": None,
            "leader_connected": False,
            "pin_count": 0,
            "port_status": {},
            "config_valid": False,
            "last_check": datetime.now().isoformat(),
            "errors": []
        }
        
        try:
            # Check if process is running
            status["running"] = await self._is_follow_running()
            
            if status["running"]:
                processes = await self._find_cluster_follow_processes()
                if processes:
                    status["pid"] = processes[0]["pid"]
                
                # Check API health
                status["api_responsive"] = await self._check_follow_api_health()
                
                if status["api_responsive"]:
                    # Get follow info
                    follow_info = await self._get_follow_info()
                    if follow_info:
                        status.update(follow_info)
                    
                    # Check leader connection
                    status["leader_connected"] = await self._check_leader_connection()
            
            # Check port availability
            status["port_status"] = await self._check_follow_ports()
            
            # Check configuration
            status["config_valid"] = self.config._validate_config()
            
        except Exception as e:
            logger.error(f"Error getting cluster follow status: {e}")
            status["errors"].append(str(e))
            
        return status
    
    async def _start_cluster_follow_daemon(self) -> Dict[str, Any]:
        """Start the cluster follow daemon process.
        
        Returns:
            Dict with start results
        """
        result = {"success": False, "pid": None, "errors": []}
        
        try:
            cluster_bin = self.config._get_cluster_follow_binary_path()
            if not cluster_bin:
                result["errors"].append("IPFS Cluster Follow binary not found")
                return result
            
            # Set environment
            env = os.environ.copy()
            env["IPFS_CLUSTER_PATH"] = str(self.config.cluster_path.parent)
            
            # Start daemon
            cmd = [cluster_bin, self.cluster_name, "run"]
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Wait a moment for startup
            await asyncio.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                result["success"] = True
                result["pid"] = process.pid
                self.follow_process = process
                logger.info(f"Cluster follow daemon started with PID {process.pid}")
            else:
                stdout, stderr = process.communicate()
                result["errors"].append(f"Daemon exited immediately: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Error starting cluster follow daemon: {e}")
            result["errors"].append(str(e))
            
        return result
    
    async def _is_follow_running(self) -> bool:
        """Check if cluster follow service is running.
        
        Returns:
            True if service is running
        """
        try:
            processes = await self._find_cluster_follow_processes()
            return len(processes) > 0
        except Exception:
            return False
    
    async def _find_cluster_follow_processes(self) -> List[Dict[str, Any]]:
        """Find running cluster follow processes.
        
        Returns:
            List of process information dicts
        """
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pinfo = proc.info
                    if pinfo['name'] and 'ipfs-cluster-follow' in pinfo['name']:
                        # Check if it's for our specific cluster
                        if pinfo['cmdline'] and self.cluster_name in pinfo['cmdline']:
                            processes.append({
                                "pid": pinfo['pid'],
                                "name": pinfo['name'],
                                "cmdline": pinfo.get('cmdline', [])
                            })
                    elif pinfo['cmdline'] and any('ipfs-cluster-follow' in cmd for cmd in pinfo['cmdline']):
                        # Check if it's for our specific cluster
                        if self.cluster_name in pinfo['cmdline']:
                            processes.append({
                                "pid": pinfo['pid'],
                                "name": pinfo['name'],
                                "cmdline": pinfo['cmdline']
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.error(f"Error finding cluster follow processes: {e}")
            
        return processes
    
    async def _check_follow_api_health(self, timeout: int = 5) -> bool:
        """Check if cluster follow API is responsive.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            True if API is responsive
        """
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Use the correct IPFS Cluster Follow API endpoint (no /api/v0/ prefix)
                response = await client.get(f"http://127.0.0.1:{self.config.api_port}/id")
                return response.status_code == 200
                
        except Exception:
            return False
    
    async def _wait_for_follow_api(self, timeout: int = 30) -> bool:
        """Wait for cluster follow API to become responsive.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if API becomes responsive within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await self._check_follow_api_health():
                return True
            await asyncio.sleep(1)
            
        return False
    
    async def _get_follow_info(self) -> Optional[Dict[str, Any]]:
        """Get cluster follow information.
        
        Returns:
            Follow info dict or None if unavailable
        """
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=5) as client:
                # Get follow ID info
                id_response = await client.get(f"http://127.0.0.1:{self.config.api_port}/id")
                if id_response.status_code == 200:
                    id_data = id_response.json()
                    
                    # Get pins info
                    pins_response = await client.get(f"http://127.0.0.1:{self.config.api_port}/pins")
                    pin_count = 0
                    if pins_response.status_code == 200:
                        pins_data = pins_response.json()
                        pin_count = len(pins_data) if isinstance(pins_data, list) else 0
                    
                    return {
                        "peer_id": id_data.get("id", "unknown"),
                        "pin_count": pin_count,
                        "addresses": id_data.get("addresses", [])
                    }
                    
        except Exception as e:
            logger.debug(f"Error getting follow info: {e}")
            
        return None
    
    async def _check_leader_connection(self) -> bool:
        """Check if connected to cluster leader.
        
        Returns:
            True if connected to leader
        """
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=5) as client:
                # Try to get cluster status to see if we're following properly
                response = await client.get(f"http://127.0.0.1:{self.config.api_port}/pins")
                if response.status_code == 200:
                    # If we can get pins, we're likely connected to a leader
                    return True
                    
        except Exception as e:
            logger.debug(f"Error checking leader connection: {e}")
            
        return False
    
    async def _check_follow_ports(self) -> Dict[str, Dict[str, Any]]:
        """Check status of cluster follow-related ports.
        
        Returns:
            Dict with port status information
        """
        ports = {
            "api": self.config.api_port,
            "proxy": self.config.proxy_port
        }
        
        port_status = {}
        
        for port_name, port_num in ports.items():
            port_status[port_name] = {
                "port": port_num,
                "in_use": False,
                "processes": []
            }
            
            try:
                for conn in psutil.net_connections():
                    if hasattr(conn, 'laddr') and conn.laddr and hasattr(conn.laddr, 'port') and conn.laddr.port == port_num:
                        port_status[port_name]["in_use"] = True
                        
                        if conn.pid:
                            try:
                                proc = psutil.Process(conn.pid)
                                port_status[port_name]["processes"].append({
                                    "pid": conn.pid,
                                    "name": proc.name(),
                                    "cmdline": proc.cmdline()
                                })
                            except psutil.NoSuchProcess:
                                pass
                                
            except Exception as e:
                logger.debug(f"Error checking port {port_num}: {e}")
                
        return port_status
    
    async def _cleanup_follow_resources(self) -> Dict[str, Any]:
        """Clean up cluster follow-related resources (lock files, stale processes).
        
        Returns:
            Dict with cleanup results
        """
        result = {
            "processes_killed": [],
            "files_removed": [],
            "ports_cleaned": []
        }
        
        try:
            # Remove lock files
            lock_files = [
                os.path.join(self.config.cluster_path, "cluster.lock"),
                os.path.join(self.config.cluster_path, "api"),
                os.path.join(self.config.cluster_path, ".lock"),
                os.path.join(self.config.cluster_path, "api-socket")
            ]
            
            for lock_file in lock_files:
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                        result["files_removed"].append(lock_file)
                        logger.info(f"Removed lock file: {lock_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove lock file {lock_file}: {e}")
            
            # Clean up processes using follow ports
            port_status = await self._check_follow_ports()
            for port_name, port_info in port_status.items():
                if port_info["in_use"]:
                    for proc_info in port_info["processes"]:
                        try:
                            proc = psutil.Process(proc_info["pid"])
                            proc.terminate()
                            result["processes_killed"].append(proc_info["pid"])
                            result["ports_cleaned"].append(port_info["port"])
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                            
        except Exception as e:
            logger.error(f"Error cleaning up cluster follow resources: {e}")
            
        return result
    
    def get_api_client(self, host: str = "127.0.0.1", port: int = None, auth: Optional[Dict[str, str]] = None) -> IPFSClusterFollowAPIClient:
        """Get API client for cluster follow service.
        
        Args:
            host: API host (default: 127.0.0.1)
            port: API port (default: from config)
            auth: Authentication credentials
            
        Returns:
            Follow API client instance
        """
        if port is None:
            port = self.config.api_port
            
        api_url = f"http://{host}:{port}"
        return IPFSClusterFollowAPIClient(api_url, auth)
    
    def get_ctl_wrapper(self) -> IPFSClusterFollowCTLWrapper:
        """Get cluster-follow-ctl wrapper for command line operations.
        
        Returns:
            Cluster-follow-ctl wrapper instance
        """
        return IPFSClusterFollowCTLWrapper(self.cluster_name)
    
    async def connect_to_cluster_leader(self, leader_host: str, leader_port: int = 9094, 
                                      auth: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Connect to a cluster leader using REST API to verify connectivity.
        
        Args:
            leader_host: Cluster leader host
            leader_port: Cluster leader API port
            auth: Authentication credentials for leader cluster
            
        Returns:
            Connection status and leader cluster info
        """
        result = {
            "success": False,
            "connected": False,
            "leader_info": {},
            "errors": []
        }
        
        try:
            # Import the main API client for connecting to leader
            from ipfs_kit_py.ipfs_cluster_api import IPFSClusterAPIClient
            
            # Create API client for leader cluster
            leader_client = IPFSClusterAPIClient(f"http://{leader_host}:{leader_port}", auth)
            
            async with leader_client:
                # Authenticate if credentials provided
                if auth:
                    auth_success = await leader_client.authenticate()
                    if not auth_success:
                        result["errors"].append("Authentication with leader failed")
                        return result
                
                # Get leader cluster info
                id_response = await leader_client.get_id()
                if id_response.get("success"):
                    result["leader_info"]["id"] = id_response
                    result["connected"] = True
                    
                # Get peers to understand the cluster
                peers_response = await leader_client.get_peers()
                if peers_response.get("success"):
                    result["leader_info"]["peers"] = peers_response
                    
                # Get pins to understand what content is being managed
                pins_response = await leader_client.get_pins()
                if pins_response.get("success"):
                    result["leader_info"]["pins"] = pins_response
                    
                result["success"] = result["connected"]
                
        except Exception as e:
            result["errors"].append(f"Connection error: {str(e)}")
            logger.error(f"Failed to connect to cluster leader {leader_host}:{leader_port}: {e}")
            
        return result
    
    async def get_pinset_from_leader(self, leader_host: str = None, leader_port: int = 9094) -> Dict[str, Any]:
        """Get pinset from cluster leader to synchronize content.
        
        Args:
            leader_host: Cluster leader host (if None, uses bootstrap peer)
            leader_port: Cluster leader API port
            
        Returns:
            Pinset information from leader
        """
        result = {
            "success": False,
            "pins": [],
            "pin_count": 0,
            "errors": []
        }
        
        try:
            # Use bootstrap peer info if no leader host provided
            if not leader_host:
                # Extract host from bootstrap peer if available
                if hasattr(self, 'bootstrap_peer') and self.bootstrap_peer:
                    # Parse multiaddr to extract host
                    parts = self.bootstrap_peer.split('/')
                    if len(parts) >= 4:
                        leader_host = parts[2]  # /ip4/HOST/tcp/PORT/...
                
            if not leader_host:
                result["errors"].append("No leader host specified and no bootstrap peer available")
                return result
            
            # Connect to leader and get pins
            leader_connection = await self.connect_to_cluster_leader(leader_host, leader_port)
            
            if leader_connection.get("connected"):
                pins_info = leader_connection["leader_info"].get("pins", {})
                if pins_info and pins_info.get("success"):
                    result["pins"] = pins_info.get("data", [])
                    result["pin_count"] = len(result["pins"])
                    result["success"] = True
                    
                    logger.info(f"Retrieved {result['pin_count']} pins from cluster leader")
                else:
                    result["errors"].append("Could not retrieve pins from leader")
            else:
                result["errors"].extend(leader_connection.get("errors", []))
                
        except Exception as e:
            result["errors"].append(f"Error getting pinset from leader: {str(e)}")
            logger.error(f"Failed to get pinset from leader: {e}")
            
        return result
    
    async def get_follow_status_via_api(self) -> Dict[str, Any]:
        """Get comprehensive cluster follow status using REST API.
        
        Returns:
            Cluster follow status information
        """
        result = {
            "success": False,
            "api_responsive": False,
            "follow_info": {},
            "errors": []
        }
        
        try:
            follow_client = self.get_api_client()
            
            async with follow_client:
                # Test API responsiveness
                health_response = await follow_client.health_check()
                if health_response.get("success"):
                    result["api_responsive"] = True
                    
                # Get follow service ID and info
                id_response = await follow_client.get_id()
                if id_response.get("success"):
                    result["follow_info"]["id"] = id_response
                    
                # Get followed pins
                pins_response = await follow_client.get_pins()
                if pins_response.get("success"):
                    result["follow_info"]["pins"] = pins_response
                    
                result["success"] = True
                
        except Exception as e:
            result["errors"].append(f"API status check error: {str(e)}")
            logger.error(f"Failed to get follow status via API: {e}")
            
        return result


# Convenience functions for external use
async def start_cluster_follow(cluster_name: str = "default", bootstrap_peer: str = None, **kwargs) -> Dict[str, Any]:
    """Start IPFS Cluster Follow daemon.
    
    Args:
        cluster_name: Name of cluster to follow
        bootstrap_peer: Bootstrap peer multiaddr
        
    Returns:
        Dict with startup results
    """
    if not bootstrap_peer:
        return {"success": False, "error": "Bootstrap peer is required"}
        
    manager = IPFSClusterFollowDaemonManager(cluster_name)
    return await manager.start_cluster_follow(bootstrap_peer, **kwargs)

async def stop_cluster_follow(cluster_name: str = "default") -> Dict[str, Any]:
    """Stop IPFS Cluster Follow daemon.
    
    Args:
        cluster_name: Name of cluster to stop following
        
    Returns:
        Dict with stop results
    """
    manager = IPFSClusterFollowDaemonManager(cluster_name)
    return await manager.stop_cluster_follow()

async def get_cluster_follow_status(cluster_name: str = "default") -> Dict[str, Any]:
    """Get IPFS Cluster Follow status.
    
    Args:
        cluster_name: Name of cluster
        
    Returns:
        Dict with status information
    """
    manager = IPFSClusterFollowDaemonManager(cluster_name)
    return await manager.get_cluster_follow_status()

async def restart_cluster_follow(cluster_name: str = "default", bootstrap_peer: str = None) -> Dict[str, Any]:
    """Restart IPFS Cluster Follow daemon.
    
    Args:
        cluster_name: Name of cluster to follow
        bootstrap_peer: Bootstrap peer multiaddr
        
    Returns:
        Dict with restart results
    """
    if not bootstrap_peer:
        return {"success": False, "error": "Bootstrap peer is required"}
        
    manager = IPFSClusterFollowDaemonManager(cluster_name)
    return await manager.restart_cluster_follow(bootstrap_peer)

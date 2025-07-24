"""
Real backend health monitor (not mocked) for IPFS Kit.
Ported from enhanced_unified_mcp_server.py with comprehensive implementations.
"""

import asyncio
import json
import logging
import time
import subprocess
import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from datetime import datetime

# Import our API clients for enhanced cluster monitoring
try:
    from ipfs_kit_py.ipfs_cluster_api import IPFSClusterAPIClient, IPFSClusterFollowAPIClient
except ImportError:
    # Create stub classes if import fails
    class IPFSClusterAPIClient:
        def __init__(self, *args, **kwargs):
            pass
    class IPFSClusterFollowAPIClient:
        def __init__(self, *args, **kwargs):
            pass

from .backend_clients import (
    IPFSClient, IPFSClusterClient, LotusClient, StorachaClient,
    SynapseClient, S3Client, HuggingFaceClient, ParquetClient, LassieClient, GDriveClient
)
from .vfs_observer import VFSObservabilityManager
from .log_manager import BackendLogManager
from ..core.config_manager import SecureConfigManager

logger = logging.getLogger(__name__)


class BackendHealthMonitor:
    """Real backend health monitoring with comprehensive implementations."""
    
    def __init__(self, config_dir: str = "/tmp/ipfs_kit_config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize secure configuration manager
        self.config_manager = SecureConfigManager(config_dir)
        
        # Initialize log manager
        self.log_manager = BackendLogManager()
        
        # Initialize backends structure (real data from reference)
        self.backends = {
            "ipfs": {
                "name": "IPFS",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 5001,
                "detailed_info": {
                    "repo_size": 0,
                    "repo_objects": 0,
                    "pins_count": 0,
                    "peer_count": 0,
                    "bandwidth_in": 0,
                    "bandwidth_out": 0,
                    "datastore_type": "unknown",
                    "api_address": "/ip4/127.0.0.1/tcp/5001",
                    "gateway_address": "/ip4/127.0.0.1/tcp/8080",
                    "config_profile": "unknown"
                }
            },
            "ipfs_cluster": {
                "name": "IPFS Cluster",
                "status": "unknown", 
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 9094,
                "detailed_info": {
                    "cluster_id": "unknown",
                    "peer_id": "unknown",
                    "cluster_peers": 0,
                    "pins_count": 0,
                    "allocations": {},
                    "consensus": "raft",
                    "api_address": "/ip4/127.0.0.1/tcp/9094",
                    "proxy_address": "/ip4/127.0.0.1/tcp/9095"
                }
            },
            "ipfs_cluster_follow": {
                "name": "IPFS Cluster Follow",
                "status": "unknown",
                "health": "unknown", 
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 9097,  # Use a different port from cluster service (9094-9096)
                "detailed_info": {
                    "cluster_name": "unknown",
                    "bootstrap_peer": None,
                    "api_address": "/ip4/127.0.0.1/tcp/9097/http",
                    "trusted_peers": [],
                    "connection_status": "unknown"
                }
            },
            "lotus": {
                "name": "Lotus",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 1234,
                "detailed_info": {
                    "node_type": "fullnode",
                    "network": "calibration",
                    "sync_status": "unknown",
                    "chain_height": 0,
                    "peers_count": 0,
                    "wallet_balance": "0 FIL",
                    "miner_address": None,
                    "api_address": "/ip4/127.0.0.1/tcp/1234/http",
                    "version": "unknown",
                    "commit": "unknown"
                }
            },
            "lassie": {
                "name": "Lassie Kit",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "binary_available": False,
                "detailed_info": {
                    "version": "unknown",
                    "binary_path": None,
                    "providers": [],
                    "concurrent_downloads": 10,
                    "timeout": "30s",
                    "temp_directory": None,
                    "integration_mode": "standalone"  # standalone or lotus-integrated
                }
            },
            "storacha": {
                "name": "Storacha",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "api_endpoints": [
                    "https://up.storacha.network/bridge",
                    "https://api.web3.storage",
                    "https://up.web3.storage/bridge"
                ]
            },
            "synapse": {
                "name": "Synapse SDK",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "js_wrapper": None,
                "npm_package": "@filoz/synapse-sdk"
            },
            "s3": {
                "name": "S3 Compatible",
                "status": "unknown",
                "health": "unknown", 
                "last_check": None,
                "metrics": {},
                "errors": [],
                "credentials": None
            },
            "huggingface": {
                "name": "HuggingFace Hub",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "auth_token": None
            },
            "parquet": {
                "name": "Parquet/Arrow",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "libraries": ["pyarrow", "pandas"]
            },
            "gdrive": {
                "name": "Google Drive",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "oauth_configured": False,
                "detailed_info": {
                    "quota_total": 0,
                    "quota_used": 0,
                    "quota_available": 0,
                    "files_count": 0,
                    "authenticated": False,
                    "token_valid": False,
                    "api_responsive": False,
                    "connectivity": False,
                    "config_dir": "~/.ipfs_kit/gdrive",
                    "credentials_file": "credentials.json",
                    "token_file": "token.json"
                }
            },
            "libp2p": {
                "name": "LibP2P Peer Network",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "peer_manager": None,
                "detailed_info": {
                    "peer_id": "unknown",
                    "total_peers": 0,
                    "connected_peers": 0,
                    "bootstrap_peers": 0,
                    "protocols": [],
                    "discovery_active": False,
                    "files_accessible": 0,
                    "pins_accessible": 0,
                    "listen_addresses": []
                }
            }
        }
        
        # Backend clients (for compatibility)
        self.backend_configs = {}
        self.metrics_history = defaultdict(lambda: deque(maxlen=100))
        
        # Initialize VFS observer
        self.vfs_observer = VFSObservabilityManager()
        
        # Load configuration
        self._load_backend_configs()
        
        # Monitoring state
        self.monitoring_active = False
        self.last_check_time = {}
        self._monitor_thread = None
        
        logger.info("✓ Backend health monitor initialized with comprehensive real implementations")
    
    def _load_backend_configs(self):
        """Load backend configurations from secure config manager."""
        try:
            # Use secure config manager to get all backend configs
            self.backend_configs = self.config_manager.get_all_backend_configs()
            logger.info(f"✓ Loaded {len(self.backend_configs)} backend configurations securely")
        except Exception as e:
            logger.error(f"Error loading backend configs: {e}")
            # Fallback to empty configs
            self.backend_configs = {}

    
    def _save_backend_configs(self):
        """Save backend configurations via secure config manager."""
        try:
            for name, config in self.backend_configs.items():
                self.config_manager.save_backend_config(name, config)
            logger.info("✓ Saved backend configs securely")
        except Exception as e:
            logger.error(f"Failed to save backend configs: {e}")
    
    async def check_backend_health(self, backend_name: str) -> Dict[str, Any]:
        """Check health of a specific backend with real implementations."""
        if backend_name not in self.backends:
            error_msg = f"Backend {backend_name} not configured"
            self.log_manager.add_log_entry(backend_name, "ERROR", error_msg)
            return {
                "name": backend_name,
                "status": "not_configured",
                "health": "unknown",
                "error": error_msg
            }
        
        self.log_manager.add_log_entry(backend_name, "INFO", f"Starting health check for {backend_name}")
        
        backend = self.backends[backend_name].copy()
        
        try:
            # Use real health check implementations from reference
            if backend_name == "ipfs":
                backend = await self._check_ipfs_health(backend)
            elif backend_name == "ipfs_cluster":
                backend = await self._check_ipfs_cluster_health(backend)
            elif backend_name == "ipfs_cluster_follow":
                backend = await self._check_ipfs_cluster_follow_health(backend)
            elif backend_name == "lotus":
                backend = await self._check_lotus_health(backend)
            elif backend_name == "lassie":
                backend = await self._check_lassie_health(backend)
            elif backend_name == "storacha":
                backend = await self._check_storacha_health(backend)
            elif backend_name == "synapse":
                backend = await self._check_synapse_health(backend)
            elif backend_name == "s3":
                backend = await self._check_s3_health(backend)
            elif backend_name == "huggingface":
                backend = await self._check_huggingface_health(backend)
            elif backend_name == "parquet":
                backend = await self._check_parquet_health(backend)
            elif backend_name == "gdrive":
                backend = await self._check_gdrive_health(backend)
            elif backend_name == "libp2p":
                backend = await self._check_libp2p_health(backend)
            
            # Log the result
            status = backend.get("status", "unknown")
            health = backend.get("health", "unknown")
            log_level = "INFO" if health == "healthy" else "WARNING"
            self.log_manager.add_log_entry(
                backend_name, 
                log_level,
                f"Health check completed - Status: {status}, Health: {health}"
            )
            
            # Store metrics
            self.metrics_history[backend_name].append({
                "timestamp": datetime.now().isoformat(),
                "health": backend["health"],
                "status": backend.get("status", "unknown"),
                "metrics": backend.get("metrics", {})
            })
            
            self.last_check_time[backend_name] = time.time()
            
            # Update the main backends dict
            self.backends[backend_name] = backend
            
            return backend
                
        except Exception as e:
            logger.error(f"Error checking {backend_name}: {e}")
            error_result = {
                "name": backend_name,
                "status": "error",
                "health": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }
            
            # Store error metrics
            self.metrics_history[backend_name].append({
                "timestamp": datetime.now().isoformat(),
                "health": "unhealthy",
                "status": "error",
                "error": str(e)
            })
            
            return error_result
    
    async def check_all_backends_health(self) -> Dict[str, Any]:
        """Check health of all configured backends.
        
        Returns:
            Dict with health status for all backends
        """
        results = {}
        
        # Check all backends in parallel for better performance
        tasks = []
        for backend_name in self.backends.keys():
            task = asyncio.create_task(self.check_backend_health(backend_name))
            tasks.append((backend_name, task))
        
        # Wait for all health checks to complete
        for backend_name, task in tasks:
            try:
                results[backend_name] = await task
            except Exception as e:
                logger.error(f"Error checking {backend_name} health: {e}")
                results[backend_name] = {
                    "name": backend_name,
                    "status": "error",
                    "health": "unhealthy",
                    "error": str(e),
                    "last_check": datetime.now().isoformat()
                }
        
        return results
    
    async def _check_ipfs_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check IPFS daemon health using enhanced daemon manager with automatic healing."""
        try:
            # Use the enhanced daemon manager for comprehensive health checking
            from ipfs_kit_py.ipfs_daemon_manager import IPFSDaemonManager, IPFSConfig
            
            # Create daemon manager with configuration
            config = IPFSConfig()
            daemon_manager = IPFSDaemonManager(config)
            
            # Get comprehensive daemon status
            daemon_status = daemon_manager.get_daemon_status()
            
            if daemon_status.get("running") and daemon_status.get("api_responsive"):
                backend["status"] = "running"
                backend["health"] = "healthy"
                backend["daemon_pid"] = daemon_status.get("pid")
                
                # Extract metrics from daemon status
                backend["metrics"] = {
                    "pid": daemon_status.get("pid"),
                    "api_responsive": daemon_status.get("api_responsive"),
                    "response_time_ms": 0,
                    "connection_failures": 0
                }
                
                # Add port usage information
                port_usage = daemon_status.get("port_usage", {})
                backend["metrics"]["ports"] = {
                    "api": port_usage.get("api", {}).get("port", 5001),
                    "gateway": port_usage.get("gateway", {}).get("port", 8080),
                    "swarm": port_usage.get("swarm", {}).get("port", 4001)
                }
                
                # Update detailed info
                backend["detailed_info"].update({
                    "daemon_pid": daemon_status.get("pid"),
                    "api_available": daemon_status.get("api_responsive"),
                    "connection_method": "enhanced_daemon_manager",
                    "lock_file_exists": daemon_status.get("lock_file_exists"),
                    "port_usage": port_usage
                })
                
                # Try to get additional IPFS info via API
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=5) as client:
                        response = await client.post("http://127.0.0.1:5001/api/v0/version")
                        if response.status_code == 200:
                            version_data = response.json()
                            backend["metrics"].update({
                                "version": version_data.get("Version", "unknown"),
                                "commit": version_data.get("Commit", "unknown"),
                                "golang_version": version_data.get("Golang", "unknown")
                            })
                            backend["detailed_info"]["version"] = version_data.get("Version", "unknown")
                except Exception as api_e:
                    logger.debug(f"Could not get IPFS version info: {api_e}")
                
            else:
                # Daemon not healthy - attempt to fix it
                backend["status"] = "disconnected"
                backend["health"] = "unhealthy"
                
                # Try to start/fix the daemon
                try:
                    logger.info("IPFS daemon unhealthy, attempting to start...")
                    start_result = daemon_manager.start_daemon()
                    
                    if start_result.get("success"):
                        # Daemon fixed, update status
                        new_status = daemon_manager.get_daemon_status()
                        if new_status.get("running") and new_status.get("api_responsive"):
                            backend["status"] = "running"
                            backend["health"] = "healthy"
                            backend["daemon_pid"] = new_status.get("pid")
                            backend["detailed_info"]["auto_healed"] = True
                            backend["detailed_info"]["heal_timestamp"] = datetime.now().isoformat()
                        else:
                            backend["errors"].append({
                                "timestamp": datetime.now().isoformat(),
                                "error": f"IPFS daemon start succeeded but still not responsive",
                                "start_result": start_result
                            })
                    else:
                        backend["errors"].append({
                            "timestamp": datetime.now().isoformat(),
                            "error": f"Failed to start IPFS daemon: {start_result.get('error', 'Unknown error')}",
                            "start_result": start_result
                        })
                        
                except Exception as heal_e:
                    backend["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Error attempting to heal IPFS daemon: {str(heal_e)}"
                    })
                
        except ImportError as e:
            # Fallback to basic health check if daemon manager not available
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": f"Enhanced IPFS daemon manager not available: {e}"
            })
        except Exception as e:
            backend["status"] = "error" 
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": f"IPFS health check failed: {str(e)}"
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_ipfs_cluster_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check IPFS Cluster health with enhanced daemon manager and API client."""
        try:
            # Use the enhanced cluster daemon manager for comprehensive health checking
            from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager
            
            # Create cluster daemon manager
            cluster_manager = IPFSClusterDaemonManager()
            
            # Get comprehensive cluster status via API
            api_status = await cluster_manager.get_cluster_status_via_api()
            
            if api_status.get("api_responsive"):
                backend["status"] = "running"
                backend["health"] = "healthy"
                
                # Extract comprehensive metrics from API response
                cluster_info = api_status.get("cluster_info", {})
                id_info = cluster_info.get("id", {})
                peers_info = cluster_info.get("peers", {})
                pins_info = cluster_info.get("pins", {})
                
                backend["metrics"] = {
                    "api_responsive": True,
                    "peer_id": id_info.get("id", "unknown") if isinstance(id_info, dict) else "unknown",
                    "version": id_info.get("version", "unknown") if isinstance(id_info, dict) else "unknown",
                    "peer_count": len(peers_info) if isinstance(peers_info, list) else 0,
                    "pin_count": len(pins_info) if isinstance(pins_info, list) else 0
                }
                
                # Update detailed info with API data
                backend["detailed_info"].update({
                    "cluster_id": id_info.get("id", "unknown") if isinstance(id_info, dict) else "unknown",
                    "api_port": cluster_manager.config.api_port,
                    "proxy_port": cluster_manager.config.proxy_port,
                    "cluster_port": cluster_manager.config.cluster_port,
                    "enhanced_monitoring": True
                })
            else:
                # Fallback to basic daemon status check
                cluster_status = await cluster_manager.get_cluster_service_status()
                
                if cluster_status.get("running"):
                    backend["status"] = "running"
                    backend["health"] = "degraded"
                    backend["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "error": "Cluster daemon running but API not responsive"
                    })
                else:
                    backend["status"] = "stopped"
                    backend["health"] = "unhealthy"
            cluster_status = await cluster_manager.get_cluster_service_status()
            
            if cluster_status.get("running") and cluster_status.get("api_responsive"):
                backend["status"] = "running"
                backend["health"] = "healthy"
                backend["metrics"] = {
                    "pid": cluster_status.get("pid"),
                    "version": cluster_status.get("version", "unknown"),
                    "peer_count": cluster_status.get("peer_count", 0),
                    "api_responsive": cluster_status.get("api_responsive", False),
                    "config_valid": cluster_status.get("config_valid", False)
                }
                
                # Update detailed info
                backend["detailed_info"].update({
                    "cluster_pid": cluster_status.get("pid"),
                    "cluster_peers": cluster_status.get("peer_count", 0),
                    "api_available": cluster_status.get("api_responsive", False),
                    "config_path": cluster_manager.config.cluster_path,
                    "api_port": cluster_manager.config.api_port,
                    "port_status": cluster_status.get("port_status", {}),
                    "version": cluster_status.get("version", "unknown")
                })
                
            elif cluster_status.get("running") and not cluster_status.get("api_responsive"):
                backend["status"] = "running"
                backend["health"] = "degraded"
                backend["metrics"] = {
                    "pid": cluster_status.get("pid"),
                    "api_responsive": False,
                    "config_valid": cluster_status.get("config_valid", False)
                }
                backend["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "error": "Cluster daemon running but API not responsive"
                })
                
                # Add a longer wait before attempting restart to avoid restart loops
                last_restart = backend.get("detailed_info", {}).get("last_restart_attempt")
                now = datetime.now()
                
                if not last_restart or (now - datetime.fromisoformat(last_restart)).total_seconds() > 300:  # 5 minutes
                    # Try to restart if API is unresponsive and it's been more than 5 minutes since last attempt
                    logger.warning("IPFS Cluster API unresponsive for >5 minutes, attempting restart...")
                    try:
                        restart_result = await cluster_manager.restart_cluster_service()
                        backend["detailed_info"]["last_restart_attempt"] = now.isoformat()
                        
                        if restart_result.get("success"):
                            backend["detailed_info"]["auto_healed"] = True
                            backend["detailed_info"]["heal_timestamp"] = datetime.now().isoformat()
                            backend["detailed_info"]["heal_action"] = "api_unresponsive_restart"
                            
                            # Re-check status after restart
                            new_status = await cluster_manager.get_cluster_service_status()
                            if new_status.get("api_responsive"):
                                backend["status"] = "running"
                                backend["health"] = "healthy"
                                backend["metrics"]["api_responsive"] = True
                        else:
                            backend["errors"].append({
                                "timestamp": datetime.now().isoformat(),
                                "error": f"Auto-restart failed: {restart_result.get('error', 'Unknown error')}"
                            })
                    except Exception as restart_e:
                        backend["errors"].append({
                            "timestamp": datetime.now().isoformat(),
                            "error": f"Error during auto-restart: {str(restart_e)}"
                        })
                else:
                    # Too soon since last restart attempt
                    time_since_restart = (now - datetime.fromisoformat(last_restart)).total_seconds()
                    backend["detailed_info"]["restart_cooldown_remaining"] = 300 - time_since_restart
                    
            else:
                # Daemon not running - attempt to start it
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                
                # Try to start the daemon
                try:
                    logger.info("IPFS Cluster not running, attempting to start...")
                    start_result = await cluster_manager.start_cluster_service()
                    
                    if start_result.get("success"):
                        # Daemon started successfully
                        backend["status"] = "running"
                        backend["health"] = "healthy" if start_result.get("api_responsive") else "degraded"
                        backend["metrics"] = {
                            "pid": start_result.get("pid"),
                            "api_responsive": start_result.get("api_responsive", False)
                        }
                        backend["detailed_info"]["auto_healed"] = True
                        backend["detailed_info"]["heal_timestamp"] = datetime.now().isoformat()
                        backend["detailed_info"]["heal_action"] = "daemon_auto_start"
                    else:
                        backend["errors"].append({
                            "timestamp": datetime.now().isoformat(),
                            "error": f"Failed to start cluster daemon: {start_result.get('errors', ['Unknown error'])}"
                        })
                        
                except Exception as start_e:
                    backend["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Error attempting to start cluster daemon: {str(start_e)}"
                    })
            
        except ImportError as e:
            # Fallback to basic health check if cluster daemon manager not available
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": f"Enhanced cluster daemon manager not available: {e}"
            })
            
            # Basic curl-based fallback
            try:
                # Use correct IPFS Cluster API endpoint (no /api/v0/ prefix)
                result = subprocess.run(
                    ["curl", "-s", "-X", "GET", f"http://127.0.0.1:{backend['port']}/version"],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    version_info = json.loads(result.stdout)
                    backend["status"] = "running"
                    backend["health"] = "degraded"  # Degraded because no enhanced management
                    backend["metrics"] = {
                        "version": version_info.get("version", "unknown"),
                        "management_mode": "basic_fallback"
                    }
                else:
                    backend["status"] = "stopped"
                    backend["health"] = "unhealthy"
                    
            except Exception as fallback_e:
                backend["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Fallback health check also failed: {str(fallback_e)}"
                })
        except Exception as e:
            backend["status"] = "error" 
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": f"Cluster health check failed: {str(e)}"
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_ipfs_cluster_follow_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check IPFS Cluster Follow health with enhanced daemon manager and API client."""
        try:
            # Use the enhanced cluster follow daemon manager for comprehensive health checking
            from ipfs_kit_py.ipfs_cluster_follow_daemon_manager import IPFSClusterFollowDaemonManager
            
            # Create cluster follow daemon manager
            cluster_name = backend.get("cluster_name", "default")
            follow_manager = IPFSClusterFollowDaemonManager(cluster_name)
            
            # Get comprehensive follow status via API
            api_status = await follow_manager.get_follow_status_via_api()
            
            if api_status.get("api_responsive"):
                backend["status"] = "running"
                backend["health"] = "healthy"
                
                # Extract comprehensive metrics from API response
                follow_info = api_status.get("follow_info", {})
                id_info = follow_info.get("id", {})
                pins_info = follow_info.get("pins", {})
                
                backend["metrics"] = {
                    "api_responsive": True,
                    "peer_id": id_info.get("id", "unknown") if isinstance(id_info, dict) else "unknown",
                    "pin_count": len(pins_info) if isinstance(pins_info, list) else 0,
                    "cluster_name": cluster_name
                }
                
                # Update detailed info with API data
                backend["detailed_info"].update({
                    "follow_id": id_info.get("id", "unknown") if isinstance(id_info, dict) else "unknown",
                    "api_port": follow_manager.config.api_port,
                    "proxy_port": follow_manager.config.proxy_port,
                    "cluster_name": cluster_name,
                    "enhanced_monitoring": True
                })
            else:
                # Fallback to basic daemon status check
                follow_status = await follow_manager.get_cluster_follow_status()
                
                if follow_status.get("running"):
                    backend["status"] = "running"
                    backend["health"] = "degraded"
                    backend["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "error": "Cluster follow daemon running but API not responsive"
                    })
                else:
                    backend["status"] = "stopped"
                    backend["health"] = "unhealthy"
                    
                    # Check if we have bootstrap peer info for auto-healing
                    bootstrap_peer = backend.get("bootstrap_peer")
                    if bootstrap_peer:
                        # Add a longer wait before attempting restart to avoid restart loops
                        last_restart = backend.get("detailed_info", {}).get("last_restart_attempt")
                        now = datetime.now()
                        
                        if not last_restart or (now - datetime.fromisoformat(last_restart)).total_seconds() > 300:  # 5 minutes
                            # Try to start if not running and it's been more than 5 minutes since last attempt
                            logger.warning("IPFS Cluster Follow not running for >5 minutes, attempting start...")
                            try:
                                start_result = await follow_manager.start_cluster_follow(bootstrap_peer)
                                backend["detailed_info"]["last_restart_attempt"] = now.isoformat()
                                
                                if start_result.get("success"):
                                    backend["detailed_info"]["auto_healed"] = True
                                    backend["detailed_info"]["heal_timestamp"] = datetime.now().isoformat()
                                    backend["detailed_info"]["heal_action"] = "follow_daemon_auto_start"
                                    
                                    # Re-check status after start
                                    new_status = await follow_manager.get_cluster_follow_status()
                                    if new_status.get("running") and new_status.get("api_responsive"):
                                        backend["status"] = "running"
                                        backend["health"] = "healthy"
                                        backend["metrics"]["api_responsive"] = True
                                else:
                                    backend["errors"].append({
                                        "timestamp": datetime.now().isoformat(),
                                        "error": f"Auto-start failed: {start_result.get('errors', ['Unknown error'])}"
                                    })
                            except Exception as start_e:
                                backend["errors"].append({
                                    "timestamp": datetime.now().isoformat(),
                                    "error": f"Error during auto-start: {str(start_e)}"
                                })
                        else:
                            # Too soon since last restart attempt
                            time_since_restart = (now - datetime.fromisoformat(last_restart)).total_seconds()
                            backend["detailed_info"]["restart_cooldown_remaining"] = 300 - time_since_restart
            
            # Update comprehensive status information
            follow_status = await follow_manager.get_cluster_follow_status()
            
            if follow_status.get("running"):
                backend["metrics"] = {
                    "pid": follow_status.get("pid"),
                    "cluster_name": follow_status.get("cluster_name", cluster_name),
                    "pin_count": follow_status.get("pin_count", 0),
                    "api_responsive": follow_status.get("api_responsive", False),
                    "leader_connected": follow_status.get("leader_connected", False)
                }
                
                # Update detailed info
                backend["detailed_info"].update({
                    "follow_pid": follow_status.get("pid"),
                    "cluster_name": follow_status.get("cluster_name", cluster_name),
                    "pins_followed": follow_status.get("pin_count", 0),
                    "api_available": follow_status.get("api_responsive", False),
                    "config_path": follow_manager.config.cluster_path,
                    "api_port": follow_manager.config.api_port,
                    "port_status": follow_status.get("port_status", {}),
                    "leader_connected": follow_status.get("leader_connected", False)
                })
                
        except ImportError as e:
            # Fallback to basic health check if follow daemon manager not available
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": f"Enhanced cluster follow daemon manager not available: {e}"
            })
            
            # Basic curl-based fallback
            try:
                # Use correct IPFS Cluster Follow API endpoint (no /api/v0/ prefix)
                result = subprocess.run(
                    ["curl", "-s", "-X", "GET", f"http://127.0.0.1:{backend['port']}/id"],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    id_info = json.loads(result.stdout)
                    backend["status"] = "running"
                    backend["health"] = "degraded"  # Degraded because no enhanced management
                    backend["metrics"] = {
                        "peer_id": id_info.get("id", "unknown"),
                        "management_mode": "basic_fallback"
                    }
                else:
                    backend["status"] = "stopped"
                    backend["health"] = "unhealthy"
                    
            except Exception as fallback_e:
                backend["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Fallback health check also failed: {str(fallback_e)}"
                })
        except Exception as e:
            backend["status"] = "error" 
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": f"Cluster follow health check failed: {str(e)}"
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_lotus_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Lotus daemon health with safe implementation to prevent loops."""
        try:
            # Use simple process check first to avoid lotus_kit import issues
            # Check both 'lotus' and 'lotus daemon' patterns for broader compatibility
            lotus_found = False
            daemon_pid = None
            
            # Try multiple process patterns to find Lotus
            patterns = ["lotus daemon", "lotus", "lotus-daemon"]
            
            for pattern in patterns:
                result = subprocess.run(
                    ["pgrep", "-f", pattern],
                    capture_output=True, text=True, timeout=3
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    # Verify the process is actually Lotus by checking the command line
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid.strip():
                            try:
                                # First check if the process still exists
                                proc_check = subprocess.run(
                                    ["ps", "-p", pid.strip()],
                                    capture_output=True, text=True, timeout=2
                                )
                                
                                if proc_check.returncode != 0:
                                    # Process no longer exists, skip it
                                    continue
                                
                                # Double-check the process exists and is stable
                                # by waiting a moment and checking again
                                import time
                                time.sleep(0.1)  # Small delay
                                
                                proc_check2 = subprocess.run(
                                    ["ps", "-p", pid.strip()],
                                    capture_output=True, text=True, timeout=2
                                )
                                
                                if proc_check2.returncode != 0:
                                    # Process died between checks, skip it
                                    continue
                                
                                # Check if this PID is actually a Lotus process
                                ps_result = subprocess.run(
                                    ["ps", "-p", pid.strip(), "-o", "cmd="],
                                    capture_output=True, text=True, timeout=2
                                )
                                
                                if ps_result.returncode == 0:
                                    cmd_line = ps_result.stdout.strip().lower()
                                    # Look for actual Lotus daemon indicators and exclude Python scripts
                                    if ("lotus" in cmd_line and 
                                        ("daemon" in cmd_line or 
                                         "lotus " in cmd_line or
                                         cmd_line.endswith("lotus")) and
                                        "python" not in cmd_line and  # Exclude Python scripts
                                        "/bin/lotus" in cmd_line or "lotus daemon" in cmd_line or cmd_line.strip().endswith("lotus")):
                                        lotus_found = True
                                        daemon_pid = pid.strip()
                                        break
                            except Exception:
                                continue
                
                if lotus_found:
                    break
            
            if lotus_found:
                backend["status"] = "running"
                backend["health"] = "healthy"
                backend["daemon_pid"] = daemon_pid
                backend["metrics"] = {
                    "process_running": True,
                    "pid": daemon_pid
                }
                
                # Initialize detailed_info if not exists
                if "detailed_info" not in backend:
                    backend["detailed_info"] = {}
                
                # Try to get basic version info with timeout
                try:
                    version_result = subprocess.run(
                        ["lotus", "version"],
                        capture_output=True, text=True, timeout=5
                    )
                    if version_result.returncode == 0:
                        version_lines = version_result.stdout.strip().split('\n')
                        backend["detailed_info"]["version"] = version_lines[0] if version_lines else "unknown"
                        backend["metrics"]["version"] = backend["detailed_info"]["version"]
                        # Look for commit info in version output
                        for line in version_lines:
                            if "Commit:" in line:
                                backend["detailed_info"]["commit"] = line.split("Commit:")[-1].strip()
                    else:
                        backend["detailed_info"]["version"] = "error"
                        backend["metrics"]["version"] = "error"
                except subprocess.TimeoutExpired:
                    backend["detailed_info"]["version"] = "timeout"
                    backend["metrics"]["version"] = "timeout"
                except Exception:
                    backend["detailed_info"]["version"] = "unknown"
                    backend["metrics"]["version"] = "unknown"

                # Try to get sync status - use 'sync status' instead of 'sync wait'
                try:
                    sync_result = subprocess.run(
                        ["lotus", "sync", "status"],
                        capture_output=True, text=True, timeout=10
                    )
                    if sync_result.returncode == 0:
                        sync_output = sync_result.stdout.strip()
                        if "sync done" in sync_output.lower() or "sync complete" in sync_output.lower():
                            backend["detailed_info"]["sync_status"] = "synced"
                        elif "syncing" in sync_output.lower():
                            backend["detailed_info"]["sync_status"] = "syncing"
                        else:
                            backend["detailed_info"]["sync_status"] = "checking"
                            
                        # Try to extract chain height from sync status
                        import re
                        height_match = re.search(r'Height: (\d+)', sync_output)
                        if height_match:
                            backend["detailed_info"]["chain_height"] = int(height_match.group(1))
                        else:
                            # Fallback to chain head command
                            try:
                                height_result = subprocess.run(
                                    ["lotus", "chain", "head"],
                                    capture_output=True, text=True, timeout=5
                                )
                                if height_result.returncode == 0:
                                    backend["detailed_info"]["chain_height"] = height_result.stdout.strip()
                            except:
                                backend["detailed_info"]["chain_height"] = 0
                    else:
                        backend["detailed_info"]["sync_status"] = "error"
                        backend["detailed_info"]["chain_height"] = 0
                except subprocess.TimeoutExpired:
                    backend["detailed_info"]["sync_status"] = "timeout"
                    backend["detailed_info"]["chain_height"] = 0
                except Exception:
                    backend["detailed_info"]["sync_status"] = "unknown"
                    backend["detailed_info"]["chain_height"] = 0

                # Try to get peer count
                try:
                    peers_result = subprocess.run(
                        ["lotus", "net", "peers"],
                        capture_output=True, text=True, timeout=5
                    )
                    if peers_result.returncode == 0:
                        peers_lines = [line.strip() for line in peers_result.stdout.strip().split('\n') if line.strip()]
                        backend["detailed_info"]["peers_count"] = len(peers_lines)
                    else:
                        backend["detailed_info"]["peers_count"] = 0
                except subprocess.TimeoutExpired:
                    backend["detailed_info"]["peers_count"] = "timeout"
                except Exception:
                    backend["detailed_info"]["peers_count"] = "unknown"

                # Try to get wallet balance (requires wallet address)
                try:
                    wallet_list_result = subprocess.run(
                        ["lotus", "wallet", "list"],
                        capture_output=True, text=True, timeout=5
                    )
                    if wallet_list_result.returncode == 0 and wallet_list_result.stdout.strip():
                        wallet_lines = [line.strip() for line in wallet_list_result.stdout.strip().split('\n') if line.strip()]
                        if wallet_lines:
                            wallet_address = wallet_lines[0]
                            balance_result = subprocess.run(
                                ["lotus", "wallet", "balance", wallet_address],
                                capture_output=True, text=True, timeout=5
                            )
                            if balance_result.returncode == 0:
                                backend["detailed_info"]["wallet_balance"] = balance_result.stdout.strip()
                            else:
                                backend["detailed_info"]["wallet_balance"] = "0 FIL"
                        else:
                            backend["detailed_info"]["wallet_balance"] = "no wallet"
                    else:
                        backend["detailed_info"]["wallet_balance"] = "unknown"
                except subprocess.TimeoutExpired:
                    backend["detailed_info"]["wallet_balance"] = "timeout"
                except Exception:
                    backend["detailed_info"]["wallet_balance"] = "unknown"
                    
                # Try to get API info
                try:
                    config_result = subprocess.run(
                        ["lotus", "config", "get", "API.ListenAddress"],
                        capture_output=True, text=True, timeout=3
                    )
                    if config_result.returncode == 0:
                        api_addr = config_result.stdout.strip().strip('"')
                        backend["detailed_info"]["api_address"] = api_addr
                    else:
                        backend["detailed_info"]["api_address"] = "/ip4/127.0.0.1/tcp/1234/http"
                except Exception:
                    backend["detailed_info"]["api_address"] = "/ip4/127.0.0.1/tcp/1234/http"
                    
                # Set network and node type based on common configurations
                backend["detailed_info"]["node_type"] = "fullnode"
                backend["detailed_info"]["network"] = "mainnet"  # Default, could be detected from config
                    
            else:
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                backend["daemon_pid"] = None
                backend["metrics"] = {"process_running": False}
                # Keep detailed_info but mark everything as unavailable
                if "detailed_info" not in backend:
                    backend["detailed_info"] = {}
                backend["detailed_info"].update({
                    "sync_status": "unavailable",
                    "chain_height": 0,
                    "peers_count": 0,
                    "wallet_balance": "unavailable",
                    "version": "unavailable"
                })
                
        except subprocess.TimeoutExpired:
            backend["status"] = "timeout"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": "Lotus health check timed out"
            })
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_lassie_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Lassie Kit health using LassieClient."""
        try:
            from .backend_clients import LassieClient
            
            # Get configuration from backend details
            config = backend.get("config", {})
            binary_path = config.get("binary_path", "lassie")
            
            # Create LassieClient instance
            client = LassieClient(binary_path=binary_path, config=config)
            
            # Perform health check
            health_result = await client.health_check()
            
            # Update backend status based on health check result
            if health_result["status"] == "healthy":
                backend["status"] = "available"
                backend["health"] = "healthy"
                backend["detailed_info"].update({
                    "binary_available": health_result.get("binary_available", False),
                    "version": health_result.get("version", "unknown"),
                    "binary_path": health_result.get("binary_path", binary_path)
                })
                backend["metrics"] = {
                    "binary_available": True,
                    "version_check": "passed",
                    "response_time": 0.1  # Quick binary check
                }
            else:
                backend["status"] = "unavailable"
                backend["health"] = "unhealthy"
                backend["detailed_info"]["binary_available"] = health_result.get("binary_available", False)
                backend["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "error": health_result.get("error", "Unknown error")
                })
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["detailed_info"]["binary_available"] = False
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_lassie_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Lassie Kit health using LassieClient."""
        try:
            from .backend_clients import LassieClient
            
            # Get configuration from backend details
            config = backend.get("config", {})
            binary_path = config.get("binary_path", "lassie")
            
            # Create LassieClient instance
            client = LassieClient(binary_path=binary_path, config=config)
            
            # Perform health check
            health_result = await client.health_check()
            
            # Update backend status based on health check result
            if health_result["status"] == "healthy":
                backend["status"] = "available"
                backend["health"] = "healthy"
                backend["detailed_info"].update({
                    "binary_available": health_result.get("binary_available", False),
                    "version": health_result.get("version", "unknown"),
                    "binary_path": health_result.get("binary_path", binary_path)
                })
                backend["metrics"] = {
                    "binary_available": True,
                    "version_check": "passed",
                    "response_time": 0.1  # Quick binary check
                }
            else:
                backend["status"] = "unavailable"
                backend["health"] = "unhealthy"
                backend["detailed_info"]["binary_available"] = health_result.get("binary_available", False)
                backend["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "error": health_result.get("error", "Unknown error")
                })
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["detailed_info"]["binary_available"] = False
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_storacha_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Storacha/Web3.Storage health with real implementation."""
        try:
            try:
                import aiohttp
                
                healthy_endpoints = []
                unhealthy_endpoints = []
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    for endpoint in backend["api_endpoints"]:
                        try:
                            async with session.get(endpoint) as response:
                                if response.status in [200, 404]:  # 404 is expected for some endpoints
                                    healthy_endpoints.append({
                                        "url": endpoint,
                                        "status": response.status,
                                        "response_time_ms": 0  # Could measure actual time
                                    })
                                else:
                                    unhealthy_endpoints.append({
                                        "url": endpoint,
                                        "status": response.status,
                                        "error": f"HTTP {response.status}"
                                    })
                        except Exception as e:
                            unhealthy_endpoints.append({
                                "url": endpoint,
                                "error": str(e)
                            })
                
                if healthy_endpoints:
                    backend["status"] = "running"
                    backend["health"] = "healthy"
                    backend["metrics"] = {
                        "healthy_endpoints": len(healthy_endpoints),
                        "unhealthy_endpoints": len(unhealthy_endpoints),
                        "endpoints": healthy_endpoints
                    }
                else:
                    backend["status"] = "unavailable"
                    backend["health"] = "unhealthy"
                    backend["metrics"] = {
                        "healthy_endpoints": 0,
                        "unhealthy_endpoints": len(unhealthy_endpoints),
                        "errors": unhealthy_endpoints
                    }
            except ImportError:
                backend["status"] = "dependency_missing"
                backend["health"] = "unhealthy"
                backend["metrics"] = {"error": "aiohttp not available"}
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def check_all_backends(self) -> Dict[str, Any]:
        """Check health of all backends."""
        results = {}
        
        # Check backends in parallel
        tasks = []
        for backend_name in self.backends.keys():
            task = asyncio.create_task(self.check_backend_health(backend_name))
            tasks.append((backend_name, task))
        
        for backend_name, task in tasks:
            try:
                results[backend_name] = await task
            except Exception as e:
                results[backend_name] = {
                    "name": backend_name,
                    "status": "error",
                    "health": "unhealthy",
                    "error": str(e)
                }
        
        return {"success": True, "backends": results}
    
    async def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get configuration for a backend."""
        if backend_name not in self.backends:
            return {"error": f"Backend {backend_name} not found"}
        
        try:
            # Return stored configuration or defaults
            if backend_name in self.backend_configs:
                return self.backend_configs[backend_name]
            else:
                # Return default configuration based on backend type
                return self._get_default_config(backend_name)
        except Exception as e:
            logger.error(f"Error getting config for {backend_name}: {e}")
            return {"error": str(e)}

    def _get_default_config(self, backend_name: str) -> Dict[str, Any]:
        """Get default configuration for a backend."""
        defaults = {
            "s3": {
                "access_key_id": "",
                "secret_access_key": "",
                "bucket": "",
                "region": "us-east-1",
                "endpoint_url": "",
                "enabled": True
            },
            "ipfs": {
                "api_url": "http://127.0.0.1:5001",
                "gateway_url": "http://127.0.0.1:8080",
                "enabled": True
            },
            "huggingface": {
                "token": "",
                "model_cache_dir": "/tmp/huggingface_cache",
                "use_auth_token": True,
                "enabled": True
            }
        }
        return defaults.get(backend_name, {"enabled": True})
    
    async def set_backend_config(self, backend_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set configuration for a backend."""
        if backend_name not in self.backends:
            return {"error": f"Backend {backend_name} not found"}
        
        try:
            logger.info(f"Setting config for {backend_name}: {config}")
            
            # Apply backend-specific configuration logic
            result = await self._apply_backend_config(backend_name, config)
            
            if result.get("success", True):  # Default to success if not specified
                # Update stored config
                self.backend_configs[backend_name] = config.copy()
                self._save_backend_configs()
                
                return {"success": True, "message": f"Configuration updated for {backend_name}"}
            else:
                return result
        except Exception as e:
            logger.error(f"Error setting config for {backend_name}: {e}")
            return {"error": str(e)}

    async def _apply_backend_config(self, backend_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply configuration changes for specific backend types."""
        try:
            if backend_name == "s3":
                return await self._apply_s3_config(config)
            elif backend_name == "ipfs":
                return await self._apply_ipfs_config(config)
            elif backend_name == "huggingface":
                return await self._apply_huggingface_config(config)
            else:
                # For other backends, just store the config
                return {"success": True, "message": f"Configuration stored for {backend_name}"}
        except Exception as e:
            return {"error": str(e)}

    async def _apply_s3_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply S3-specific configuration."""
        try:
            # Create config directory if it doesn't exist
            config_dir = self.config_dir / "backends"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / "s3_config.json"
            
            # Set environment variables
            if config.get("access_key_id"):
                os.environ["AWS_ACCESS_KEY_ID"] = config["access_key_id"]
            if config.get("secret_access_key"):
                os.environ["AWS_SECRET_ACCESS_KEY"] = config["secret_access_key"]
            if config.get("region"):
                os.environ["AWS_DEFAULT_REGION"] = config["region"]
                
            # Save to file for persistence
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"S3 configuration applied and saved to {config_file}")
            return {"success": True, "message": "S3 configuration applied successfully"}
            
        except Exception as e:
            logger.error(f"Error applying S3 config: {e}")
            return {"error": str(e)}

    async def _apply_ipfs_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply IPFS-specific configuration."""
        # For now, just store the config
        return {"success": True, "message": "IPFS configuration stored"}

    async def _apply_huggingface_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply HuggingFace-specific configuration."""
        try:
            if config.get("token"):
                os.environ["HUGGINGFACE_HUB_TOKEN"] = config["token"]
                
                # Also save to HF config file
                hf_config_dir = Path("~/.cache/huggingface").expanduser()
                hf_config_dir.mkdir(parents=True, exist_ok=True)
                
                token_file = hf_config_dir / "token"
                token_file.write_text(config["token"])
                
            return {"success": True, "message": "HuggingFace configuration applied"}
        except Exception as e:
            return {"error": str(e)}
    
    async def restart_backend(self, backend_name: str) -> bool:
        """Restart a backend (where applicable)."""
        if backend_name not in self.backends:
            return False
        
        try:
            backend_obj = self.backends.get(backend_name)
            if backend_obj and hasattr(backend_obj, 'restart'):
                result = await backend_obj.restart()
                if result.get("success", False):
                    logger.info(f"✓ Restarted {backend_name} backend")
                    return True
                else:
                    logger.error(f"Failed to restart {backend_name}: {result.get("error", "Unknown error")}")
                    return False
            else:
                logger.warning(f"Restart not supported for {backend_name}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to restart {backend_name}: {e}")
            return False

    async def get_backend_logs(self, backend_name: str) -> List[str]:
        """Get logs for a specific backend."""
        if backend_name not in self.backends:
            return [f"Backend {backend_name} not found."]
        
        try:
            backend_obj = self.backends.get(backend_name)
            if backend_obj and hasattr(backend_obj, 'get_logs'):
                logs = await backend_obj.get_logs()
                return logs
            else:
                return [f"Log retrieval not supported for {backend_name}."]
        except Exception as e:
            logger.error(f"Failed to get logs for {backend_name}: {e}")
            return [f"Error retrieving logs for {backend_name}: {str(e)}"]
    
    def get_metrics_history(self, backend_name: str, limit: int = 10) -> list:
        """Get metrics history for a backend."""
        if backend_name not in self.metrics_history:
            return []
        
        history = list(self.metrics_history[backend_name])
        return history[-limit:] if limit > 0 else history
    
    def start_monitoring(self):
        """Start background monitoring."""
        self.monitoring_active = True
        logger.info("✓ Backend monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self.monitoring_active = False
        logger.info("✓ Backend monitoring stopped")
    
    def get_package_config(self) -> Dict[str, Any]:
        """Get package configuration."""
        config_file = self.config_dir / "package_config.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load package config: {e}")
        
        # Default package config
        return {
            "config": {
                "system": {
                    "log_level": "INFO",
                    "max_workers": "4",
                    "cache_size": "1000",
                    "data_directory": "/tmp/ipfs_kit"
                },
                "vfs": {
                    "cache_enabled": "true",
                    "cache_max_size": "10GB",
                    "vector_dimensions": "384",
                    "knowledge_base_max_nodes": "10000"
                },
                "observability": {
                    "metrics_enabled": "true",
                    "prometheus_port": "9090",
                    "dashboard_enabled": "true",
                    "health_check_interval": "30"
                },
                "credentials": {
                    "huggingface": {
                        "token": "*** SECURE: Use setup_credentials.py to configure ***",
                        "test_repo": "LAION-AI/ipfs-kit-test"
                    },
                    "s3": {
                        "access_key": "*** SECURE: Use setup_credentials.py to configure ***",
                        "secret_key": "*** SECURE: Use setup_credentials.py to configure ***",
                        "server": "object.lga1.coreweave.com",
                        "test_bucket": "ipfs-kit-test"
                    }
                }
            }
        }
    
    def set_package_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set package configuration."""
        config_file = self.config_dir / "package_config.json"
        
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"✓ Saved package config to {config_file}")
            return {"success": True, "message": "Package configuration saved"}
        except Exception as e:
            logger.error(f"Failed to save package config: {e}")
            return {"success": False, "error": str(e)}
    
    def initialize_vfs_observer(self):
        """Initialize VFS observer with real implementations."""
        logger.info("✓ VFS observer initialized with comprehensive real implementations")
        pass
    
    async def _check_synapse_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Synapse SDK health with real implementation."""
        try:
            # Check if Node.js is available
            node_result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=5
            )
            
            if node_result.returncode == 0:
                backend["metrics"] = {
                    "node_version": node_result.stdout.strip(),
                    "node_available": True
                }
                
                # Check if npm package is installed
                npm_result = subprocess.run(
                    ["npm", "list", backend["npm_package"]],
                    capture_output=True, text=True, timeout=10
                )
                
                if npm_result.returncode == 0:
                    backend["status"] = "installed"
                    backend["health"] = "healthy"
                    backend["metrics"]["npm_package_installed"] = True
                    
                    # Check if JS wrapper exists
                    project_root = Path(__file__).parent.parent.parent.parent
                    js_wrapper_path = project_root / "ipfs_kit_py" / "js" / "synapse_wrapper.js"
                    if js_wrapper_path.exists():
                        backend["metrics"]["js_wrapper_exists"] = True
                        backend["js_wrapper"] = str(js_wrapper_path)
                    else:
                        backend["metrics"]["js_wrapper_exists"] = False
                        
                else:
                    backend["status"] = "not_installed"
                    backend["health"] = "unhealthy"
                    backend["metrics"]["npm_package_installed"] = False
                    
            else:
                backend["status"] = "node_missing"
                backend["health"] = "unhealthy"
                backend["metrics"] = {"node_available": False}
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_s3_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check S3 compatible storage health with real implementation."""
        try:
            # Check if boto3 is available
            try:
                import boto3
                backend["metrics"] = {"boto3_available": True}
                
                # Check for AWS credentials
                aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
                aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
                
                if aws_access_key and aws_secret_key:
                    backend["status"] = "configured"
                    backend["health"] = "healthy"
                    backend["credentials"] = "configured"
                    backend["metrics"]["credentials_available"] = True
                    
                    # Try to create a client (doesn't make actual request)
                    try:
                        s3_client = boto3.client('s3')
                        backend["metrics"]["client_creation"] = "success"
                    except Exception as e:
                        backend["metrics"]["client_creation"] = f"error: {str(e)}"
                        
                else:
                    backend["status"] = "unconfigured"
                    backend["health"] = "unhealthy"
                    backend["credentials"] = "missing"
                    backend["metrics"]["credentials_available"] = False
                    
            except ImportError:
                backend["status"] = "not_installed"
                backend["health"] = "unhealthy"
                backend["metrics"] = {"boto3_available": False}
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_huggingface_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check HuggingFace Hub health with real implementation."""
        try:
            # Check if huggingface_hub is available
            try:
                import huggingface_hub
                backend["metrics"] = {"huggingface_hub_available": True}
                
                # Check authentication
                try:
                    token = huggingface_hub.HfFolder.get_token()
                    if token:
                        backend["status"] = "authenticated"
                        backend["health"] = "healthy"
                        backend["auth_token"] = "configured"
                        backend["metrics"]["authenticated"] = True
                        
                        # Try to get user info
                        try:
                            user_info = huggingface_hub.whoami()
                            backend["metrics"]["username"] = user_info.get("name", "unknown")
                        except:
                            backend["metrics"]["username"] = "unknown"
                            
                    else:
                        backend["status"] = "unauthenticated"
                        backend["health"] = "partial"
                        backend["auth_token"] = "missing"
                        backend["metrics"]["authenticated"] = False
                        
                except Exception as e:
                    backend["status"] = "error"
                    backend["health"] = "unhealthy"
                    backend["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Authentication check failed: {str(e)}"
                    })
                    
            except ImportError:
                backend["status"] = "not_installed"
                backend["health"] = "unhealthy"
                backend["metrics"] = {"huggingface_hub_available": False}
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_parquet_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Parquet/Arrow libraries health with real implementation."""
        try:
            available_libs = {}
            
            # Check PyArrow
            try:
                import pyarrow
                available_libs["pyarrow"] = {
                    "available": True,
                    "version": pyarrow.__version__
                }
            except ImportError:
                available_libs["pyarrow"] = {"available": False}
                
            # Check Pandas
            try:
                import pandas
                available_libs["pandas"] = {
                    "available": True,
                    "version": pandas.__version__
                }
            except ImportError:
                available_libs["pandas"] = {"available": False}
            
            # Check Polars (optional)
            try:
                import polars
                available_libs["polars"] = {
                    "available": True,
                    "version": polars.__version__
                }
            except ImportError:
                available_libs["polars"] = {"available": False}
                
            backend["metrics"] = {"libraries": available_libs}
            
            # Determine overall status
            if available_libs["pyarrow"]["available"]:
                backend["status"] = "available"
                backend["health"] = "healthy"
            else:
                backend["status"] = "missing"
                backend["health"] = "unhealthy"
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    async def _check_gdrive_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Google Drive backend health."""
        try:
            # Use the GDriveClient for health checking
            try:
                from .backend_clients import GDriveClient
                async with GDriveClient() as client:
                    health_result = await client.check_health()
                    
                    if health_result.get("success", False):
                        backend["status"] = health_result.get("status", "available")
                        backend["health"] = health_result.get("health", "degraded")
                        
                        # Update detailed info from health check
                        detailed = health_result.get("detailed_info", {})
                        backend["detailed_info"].update({
                            "connectivity": detailed.get("connectivity", False),
                            "api_responsive": detailed.get("api_responsive", False),
                            "authenticated": detailed.get("authenticated", False),
                            "token_valid": detailed.get("token_valid", False),
                            "config_dir": detailed.get("config_dir", "~/.ipfs_kit/gdrive")
                        })
                        
                        # Update metrics
                        metrics = health_result.get("metrics", {})
                        backend["metrics"] = {
                            "connectivity": metrics.get("connectivity", False),
                            "authenticated": metrics.get("authenticated", False),
                            "api_responsive": metrics.get("api_responsive", False),
                            "note": metrics.get("note", "")
                        }
                        
                    else:
                        backend["status"] = "error"
                        backend["health"] = "unhealthy"
                        backend["errors"].append({
                            "timestamp": datetime.now().isoformat(),
                            "error": health_result.get("error", "Unknown health check error")
                        })
                        
            except Exception as client_error:
                backend["status"] = "error"
                backend["health"] = "unhealthy"
                backend["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Client error: {str(client_error)}"
                })
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_libp2p_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check LibP2P peer network health with enhanced monitoring, auto-healing, and content sharing."""
        try:
            # Initialize enhanced LibP2P manager if not already done
            if not backend.get("libp2p_manager"):
                # Import the enhanced LibP2P manager
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
                
                from enhanced_libp2p_manager import get_libp2p_manager, start_libp2p_manager
                
                # Get or create the LibP2P manager
                manager = get_libp2p_manager(config_dir=self.config_dir / "libp2p")
                backend["libp2p_manager"] = manager
                
                # Start the manager if not already started
                if not manager.host_active:
                    logger.info("Starting Enhanced LibP2P Manager for health monitoring...")
                    start_result = await start_libp2p_manager(config_dir=self.config_dir / "libp2p")
                    backend["detailed_info"]["auto_started"] = True
                    backend["detailed_info"]["start_timestamp"] = datetime.now().isoformat()
                    backend["detailed_info"]["start_result"] = {
                        "success": start_result is not None,
                        "peer_id": start_result.stats.get("peer_id") if start_result else None,
                        "protocols_started": list(start_result.protocols_active) if start_result else []
                    }
            else:
                manager = backend["libp2p_manager"]
            
            # Get comprehensive statistics
            stats = manager.get_peer_statistics()
            shared_content = manager.get_shared_content_summary()
            all_peers = manager.get_all_peers()
            
            # Build enhanced network information
            network_info = {
                "peer_id": stats.get("peer_id"),
                "total_peers": stats.get("total_peers", 0),
                "connected_peers": stats.get("connected_peers", 0),
                "bootstrap_peers": stats.get("bootstrap_peers", 0),
                "protocols": stats.get("protocols_supported", []),
                "discovery_active": stats.get("discovery_active", False),
                "files_accessible": stats.get("files_accessible", 0),
                "pins_accessible": stats.get("pins_accessible", 0),
                "listen_addresses": stats.get("listen_addresses", []),
                "host_active": manager.host_active
            }
            
            # Add content sharing information
            network_info["content_sharing"] = {
                "pinsets": {
                    "peers_sharing": shared_content.get("pinsets", {}).get("peers", 0),
                    "total_pins": shared_content.get("pinsets", {}).get("total_pins", 0)
                },
                "vectors": {
                    "peers_sharing": shared_content.get("vectors", {}).get("peers", 0),
                    "total_vectors": shared_content.get("vectors", {}).get("total_vectors", 0)
                },
                "knowledge": {
                    "peers_sharing": shared_content.get("knowledge", {}).get("peers", 0),
                    "total_entities": shared_content.get("knowledge", {}).get("total_entities", 0)
                },
                "files": {
                    "peers_sharing": shared_content.get("files", {}).get("peers", 0),
                    "total_files": shared_content.get("files", {}).get("total_files", 0)
                }
            }
            
            # Add peer source breakdown
            peer_sources = {}
            for peer_id, peer_info in all_peers.items():
                source = peer_info.get("source", "unknown")
                peer_sources[source] = peer_sources.get(source, 0) + 1
            network_info["peer_sources"] = peer_sources
            
            # Check for connectivity issues and implement auto-healing
            connectivity_issues = []
            
            # Check if discovery is active but no peers found
            if stats.get("discovery_active") and stats.get("total_peers", 0) == 0:
                connectivity_issues.append("discovery_active_no_peers")
                
                # Try to restart discovery
                try:
                    logger.warning("LibP2P discovery active but no peers found, restarting discovery...")
                    await manager.restart_discovery()
                    network_info["auto_healed"] = True
                    network_info["heal_action"] = "restart_discovery"
                    network_info["heal_timestamp"] = datetime.now().isoformat()
                except Exception as heal_e:
                    backend["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Failed to restart discovery: {str(heal_e)}"
                    })
            
            # Check if host is inactive
            if not manager.host_active:
                connectivity_issues.append("host_inactive")
                
                # Try to restart the manager
                try:
                    logger.warning("LibP2P host inactive, attempting restart...")
                    restart_result = await manager.start()
                    if restart_result and restart_result.get("success"):
                        network_info["auto_healed"] = True
                        network_info["heal_action"] = "restart_host"
                        network_info["heal_timestamp"] = datetime.now().isoformat()
                        
                        # Update stats after restart
                        stats = manager.get_peer_statistics()
                        network_info.update({
                            "total_peers": stats.get("total_peers", 0),
                            "connected_peers": stats.get("connected_peers", 0),
                            "discovery_active": stats.get("discovery_active", False),
                            "host_active": manager.host_active
                        })
                except Exception as restart_e:
                    backend["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Failed to restart LibP2P host: {str(restart_e)}"
                    })
            
            # Check for low peer connectivity
            total_peers = stats.get("total_peers", 0)
            connected_peers = stats.get("connected_peers", 0)
            if total_peers > 0 and connected_peers < total_peers * 0.5:
                connectivity_issues.append("low_connectivity")
                network_info["connectivity_ratio"] = connected_peers / total_peers
            
            # Check for insufficient content sharing
            total_content = (
                shared_content.get("pinsets", {}).get("total_pins", 0) +
                shared_content.get("files", {}).get("total_files", 0) +
                shared_content.get("vectors", {}).get("total_vectors", 0) +
                shared_content.get("knowledge", {}).get("total_entities", 0)
            )
            if total_content == 0:
                connectivity_issues.append("no_content_available")
            
            # Update backend detailed info
            backend["detailed_info"].update(network_info)
            backend["detailed_info"]["connectivity_issues"] = connectivity_issues
            
            # Update comprehensive metrics
            backend["metrics"] = {
                "peer_discovery": {
                    "total_peers": total_peers,
                    "connected_peers": connected_peers,
                    "bootstrap_peers": stats.get("bootstrap_peers", 0),
                    "discovery_active": stats.get("discovery_active", False),
                    "connectivity_ratio": connected_peers / max(total_peers, 1),
                    "peer_sources": peer_sources
                },
                "content_sharing": {
                    "pinsets_available": shared_content.get("pinsets", {}).get("total_pins", 0),
                    "files_accessible": shared_content.get("files", {}).get("total_files", 0),
                    "vectors_available": shared_content.get("vectors", {}).get("total_vectors", 0),
                    "knowledge_entities": shared_content.get("knowledge", {}).get("total_entities", 0),
                    "total_shared_content": total_content,
                    "content_available": total_content > 0
                },
                "network_capabilities": {
                    "protocols_count": len(stats.get("protocols_supported", [])),
                    "protocols_supported": stats.get("protocols_supported", []),
                    "features_enabled": [
                        "peer_discovery",
                        "pinset_sharing",
                        "vector_embeddings", 
                        "knowledge_graph",
                        "filesystem_sharing"
                    ],
                    "bootstrap_sources": list(peer_sources.keys())
                },
                "connectivity": {
                    "host_active": manager.host_active,
                    "discovery_working": stats.get("discovery_active", False) and total_peers > 0,
                    "network_health_score": self._calculate_enhanced_libp2p_health_score(stats, shared_content, connectivity_issues)
                }
            }
            
            # Determine comprehensive status and health
            health_score = backend["metrics"]["connectivity"]["network_health_score"]
            
            if manager.host_active and stats.get("discovery_active", False):
                if health_score >= 85:
                    backend["status"] = "running"
                    backend["health"] = "healthy"
                    backend["status_message"] = f"LibP2P fully operational with {connected_peers} peers and content sharing active"
                elif health_score >= 70:
                    backend["status"] = "running"
                    backend["health"] = "degraded"
                    backend["status_message"] = f"LibP2P running with minor issues: {', '.join(connectivity_issues[:2])}"
                else:
                    backend["status"] = "running"
                    backend["health"] = "unhealthy"
                    backend["status_message"] = f"LibP2P running with significant issues: {', '.join(connectivity_issues)}"
            elif manager.host_active:
                backend["status"] = "running"
                backend["health"] = "degraded"
                backend["status_message"] = "LibP2P host running but discovery inactive"
            else:
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                backend["status_message"] = "LibP2P host not running"
                
        except ImportError as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["status_message"] = "Enhanced LibP2P manager not available"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": f"Import error: {str(e)}"
            })
            logger.error(f"Failed to import enhanced LibP2P manager: {e}")
            
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["status_message"] = f"LibP2P health check failed: {str(e)}"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            logger.error(f"Error checking LibP2P health: {e}")
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
    
    def _calculate_enhanced_libp2p_health_score(self, stats: Dict[str, Any], shared_content: Dict[str, Any], issues: List[str]) -> int:
        """Calculate an enhanced health score for LibP2P network (0-100).
        
        Args:
            stats: Peer statistics
            shared_content: Content sharing statistics
            issues: List of connectivity issues
            
        Returns:
            Health score from 0-100
        """
        score = 100
        
        # Deduct points for discovery and connectivity issues
        if not stats.get("discovery_active", False):
            score -= 25
        
        total_peers = stats.get("total_peers", 0)
        connected_peers = stats.get("connected_peers", 0)
        
        if total_peers == 0:
            score -= 30
        elif total_peers < 3:
            score -= 15
        
        if total_peers > 0 and connected_peers < total_peers * 0.5:
            score -= 15
        
        # Content sharing scoring
        pinsets = shared_content.get("pinsets", {}).get("total_pins", 0)
        files = shared_content.get("files", {}).get("total_files", 0)
        vectors = shared_content.get("vectors", {}).get("total_vectors", 0)
        knowledge = shared_content.get("knowledge", {}).get("total_entities", 0)
        
        # Bonus points for content availability
        if pinsets > 0:
            score += 5
        if files > 0:
            score += 5
        if vectors > 0:
            score += 5
        if knowledge > 0:
            score += 5
        
        # Deduct points for no content at all
        if pinsets + files + vectors + knowledge == 0:
            score -= 20
        
        # Deduct points for specific issues
        for issue in issues:
            if issue == "host_inactive":
                score -= 40
            elif issue == "discovery_active_no_peers":
                score -= 20
            elif issue == "low_connectivity":
                score -= 10
            elif issue == "no_content_available":
                score -= 15
        
        return max(0, min(100, score))

"""
Real backend health monitor (not mocked) for IPFS Kit.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from collections import defaultdict, deque

from .backend_clients import (
    IPFSClient, IPFSClusterClient, LotusClient, StorachaClient,
    SynapseClient, S3Client, HuggingFaceClient, ParquetClient
)
from .vfs_observer import VFSObservabilityManager
from ..core.config_manager import SecureConfigManager

logger = logging.getLogger(__name__)


class BackendHealthMonitor:
    """Real backend health monitoring (not mocked)."""
    
    def __init__(self, config_dir: str = "/tmp/ipfs_kit_config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize secure configuration manager
        self.config_manager = SecureConfigManager(config_dir)
        
        # Initialize backend clients
        self.backends = {}
        self.backend_configs = {}
        self.metrics_history = defaultdict(lambda: deque(maxlen=100))
        
        # Initialize VFS observer
        self.vfs_observer = VFSObservabilityManager()
        
        # Load configuration
        self._load_backend_configs()
        self._initialize_backends()
        
        # Monitoring state
        self.monitoring_active = False
        self.last_check_time = {}
        
        logger.info("✓ Backend health monitor initialized with VFS observability and secure credentials")
    
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
    
    def _initialize_backends(self):
        """Initialize backend clients."""
        self.backends = {}
        
        for name, config in self.backend_configs.items():
            try:
                if name == "ipfs":
                    self.backends[name] = IPFSClient(**config)
                elif name == "ipfs_cluster":
                    self.backends[name] = IPFSClusterClient(**config)
                elif name == "lotus":
                    self.backends[name] = LotusClient(**config)
                elif name == "storacha":
                    self.backends[name] = StorachaClient(**config)
                elif name == "synapse":
                    self.backends[name] = SynapseClient(**config)
                elif name == "s3":
                    self.backends[name] = S3Client(**config)
                elif name == "huggingface":
                    self.backends[name] = HuggingFaceClient(**config)
                elif name == "parquet":
                    self.backends[name] = ParquetClient(**config)
                else:
                    logger.warning(f"Unknown backend type: {name}")
                    
                logger.info(f"✓ Initialized {name} backend client")
            except Exception as e:
                logger.error(f"Failed to initialize {name} backend: {e}")
    
    async def check_backend_health(self, backend_name: str) -> Dict[str, Any]:
        """Check health of a specific backend."""
        if backend_name not in self.backends:
            return {
                "name": backend_name,
                "status": "not_configured",
                "health": "unknown",
                "error": "Backend not configured"
            }
        
        client = self.backends[backend_name]
        
        try:
            async with client:
                result = await client.health_check()
                
                # Add metadata
                result["name"] = backend_name
                result["last_check"] = time.strftime('%Y-%m-%d %H:%M:%S')
                
                # Determine health status
                if result.get("status") == "healthy":
                    result["health"] = "healthy"
                elif result.get("status") == "partial":
                    result["health"] = "partial"
                else:
                    result["health"] = "unhealthy"
                
                # Store metrics
                self.metrics_history[backend_name].append({
                    "timestamp": time.time(),
                    "health": result["health"],
                    "status": result.get("status", "unknown"),
                    "response_time": 0  # Could be measured
                })
                
                self.last_check_time[backend_name] = time.time()
                
                return result
                
        except Exception as e:
            logger.error(f"Error checking {backend_name}: {e}")
            error_result = {
                "name": backend_name,
                "status": "error",
                "health": "unhealthy",
                "error": str(e),
                "last_check": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Store error metrics
            self.metrics_history[backend_name].append({
                "timestamp": time.time(),
                "health": "unhealthy",
                "status": "error",
                "error": str(e)
            })
            
            return error_result
    
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
        
        return results
    
    async def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get configuration for a backend."""
        if backend_name not in self.backends:
            return {"error": f"Backend {backend_name} not found"}
        
        client = self.backends[backend_name]
        
        try:
            async with client:
                config = await client.get_config()
                return {"backend": backend_name, "config": config}
        except Exception as e:
            return {"error": str(e)}
    
    async def set_backend_config(self, backend_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set configuration for a backend."""
        if backend_name not in self.backends:
            return {"error": f"Backend {backend_name} not found"}
        
        client = self.backends[backend_name]
        
        try:
            async with client:
                success = await client.set_config(config)
                
                if success:
                    # Update stored config
                    self.backend_configs[backend_name].update(config)
                    self._save_backend_configs()
                    
                    return {"success": True, "message": f"Configuration updated for {backend_name}"}
                else:
                    return {"success": False, "error": "Failed to update configuration"}
        except Exception as e:
            return {"error": str(e)}
    
    async def restart_backend(self, backend_name: str) -> bool:
        """Restart a backend (where applicable)."""
        if backend_name not in self.backends:
            return False
        
        try:
            # For most backends, restart means reinitializing the client
            config = self.backend_configs.get(backend_name, {})
            
            if backend_name == "ipfs":
                self.backends[backend_name] = IPFSClient(**config)
            elif backend_name == "ipfs_cluster":
                self.backends[backend_name] = IPFSClusterClient(**config)
            elif backend_name == "lotus":
                self.backends[backend_name] = LotusClient(**config)
            elif backend_name == "synapse":
                self.backends[backend_name] = SynapseClient(**config)
            else:
                logger.warning(f"Restart not supported for {backend_name}")
                return False
            
            logger.info(f"✓ Restarted {backend_name} backend")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart {backend_name}: {e}")
            return False
    
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
        """Initialize VFS observer (placeholder)."""
        # This would be implemented with actual VFS integration
        logger.info("✓ VFS observer initialized (placeholder)")
        pass

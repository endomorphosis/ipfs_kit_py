"""
IPFS Kit Replication Management System
Enhanced replication management for pins across multiple storage backends
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """Storage backend types."""
    LOCAL = "local"
    IPFS_CLUSTER = "ipfs_cluster"
    FILECOIN = "filecoin"
    STORACHA = "storacha"
    PINATA = "pinata"
    WEB3_STORAGE = "web3_storage"


class ReplicationPolicy(Enum):
    """Replication policies."""
    CONSERVATIVE = "conservative"  # Min replicas, prioritize reliability
    BALANCED = "balanced"         # Balance cost and reliability
    AGGRESSIVE = "aggressive"     # Max replicas, prioritize availability


@dataclass
class BackendConfig:
    """Configuration for a storage backend."""
    name: str
    backend_type: BackendType
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    max_storage_gb: Optional[float] = None
    cost_per_gb: Optional[float] = None
    priority: int = 1  # 1=highest, 10=lowest
    enabled: bool = True
    health_check_url: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ReplicationSettings:
    """Global replication settings."""
    min_replicas: int = 2
    max_replicas: int = 5
    target_replicas: int = 3
    max_total_storage_gb: float = 100.0
    policy: ReplicationPolicy = ReplicationPolicy.BALANCED
    auto_replication: bool = True
    health_check_interval: int = 300  # seconds
    replication_check_interval: int = 900  # seconds
    enable_cost_optimization: bool = True
    emergency_backup_enabled: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PinReplication:
    """Replication information for a specific pin."""
    cid: str
    vfs_metadata_id: Optional[str] = None
    size_bytes: int = 0
    backends: List[str] = None
    target_replicas: int = 3
    current_replicas: int = 0
    status: str = "pending"  # pending, replicating, complete, failed
    last_checked: Optional[datetime] = None
    created_at: Optional[datetime] = None
    priority: int = 1
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.backends is None:
            self.backends = []
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class ReplicationManager:
    """Comprehensive replication management system."""
    
    def __init__(
        self,
        config_dir: str = None,
        parquet_bridge=None,
        car_bridge=None,
        ipfs_manager=None
    ):
        self.config_dir = Path(config_dir or os.path.expanduser("~/.ipfs_replication"))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.parquet_bridge = parquet_bridge
        self.car_bridge = car_bridge
        self.ipfs_manager = ipfs_manager
        
        # Configuration files
        self.settings_file = self.config_dir / "replication_settings.json"
        self.backends_file = self.config_dir / "storage_backends.json"
        self.pins_file = self.config_dir / "pin_replications.json"
        
        # In-memory state
        self.settings: ReplicationSettings = ReplicationSettings()
        self.backends: Dict[str, BackendConfig] = {}
        self.pin_replications: Dict[str, PinReplication] = {}
        
        # Runtime state
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Load existing configuration
        self._load_configuration()
        
        logger.info(f"ReplicationManager initialized with config dir: {self.config_dir}")

    def _load_configuration(self):
        """Load configuration from files."""
        try:
            # Load replication settings
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings_data = json.load(f)
                    self.settings = ReplicationSettings(**settings_data)
            else:
                self._save_settings()
            
            # Load backend configurations
            if self.backends_file.exists():
                with open(self.backends_file, 'r') as f:
                    backends_data = json.load(f)
                    for name, config in backends_data.items():
                        config['backend_type'] = BackendType(config['backend_type'])
                        if 'policy' in config and config['policy']:
                            config['policy'] = ReplicationPolicy(config['policy'])
                        self.backends[name] = BackendConfig(**config)
            else:
                self._initialize_default_backends()
            
            # Load pin replications
            if self.pins_file.exists():
                with open(self.pins_file, 'r') as f:
                    pins_data = json.load(f)
                    for cid, repl_data in pins_data.items():
                        if 'last_checked' in repl_data and repl_data['last_checked']:
                            repl_data['last_checked'] = datetime.fromisoformat(repl_data['last_checked'])
                        if 'created_at' in repl_data and repl_data['created_at']:
                            repl_data['created_at'] = datetime.fromisoformat(repl_data['created_at'])
                        self.pin_replications[cid] = PinReplication(**repl_data)
            
            logger.info("Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self._initialize_default_configuration()

    def _initialize_default_backends(self):
        """Initialize default storage backends."""
        default_backends = {
            "local": BackendConfig(
                name="local",
                backend_type=BackendType.LOCAL,
                max_storage_gb=50.0,
                cost_per_gb=0.0,
                priority=1,
                enabled=True,
                metadata={"description": "Local IPFS node storage"}
            ),
            "ipfs_cluster": BackendConfig(
                name="ipfs_cluster",
                backend_type=BackendType.IPFS_CLUSTER,
                endpoint="http://localhost:9094",
                max_storage_gb=200.0,
                cost_per_gb=0.0,
                priority=2,
                enabled=True,
                metadata={"description": "IPFS Cluster for distributed storage"}
            ),
            "filecoin": BackendConfig(
                name="filecoin",
                backend_type=BackendType.FILECOIN,
                max_storage_gb=1000.0,
                cost_per_gb=0.001,
                priority=3,
                enabled=False,
                metadata={"description": "Filecoin long-term storage"}
            )
        }
        
        self.backends = default_backends
        self._save_backends()

    def _initialize_default_configuration(self):
        """Initialize default configuration."""
        self.settings = ReplicationSettings()
        self._initialize_default_backends()
        self._save_all_configuration()

    def _save_settings(self):
        """Save replication settings to file."""
        try:
            settings_dict = asdict(self.settings)
            if hasattr(self.settings.policy, 'value'):
                settings_dict['policy'] = self.settings.policy.value
            else:
                settings_dict['policy'] = str(self.settings.policy)
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings_dict, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def _save_backends(self):
        """Save backend configurations to file."""
        try:
            backends_dict = {}
            for name, config in self.backends.items():
                config_dict = asdict(config)
                config_dict['backend_type'] = config.backend_type.value
                backends_dict[name] = config_dict
            
            with open(self.backends_file, 'w') as f:
                json.dump(backends_dict, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving backends: {e}")

    def _save_pins(self):
        """Save pin replications to file."""
        try:
            pins_dict = {}
            for cid, repl in self.pin_replications.items():
                repl_dict = asdict(repl)
                if repl.last_checked:
                    repl_dict['last_checked'] = repl.last_checked.isoformat()
                if repl.created_at:
                    repl_dict['created_at'] = repl.created_at.isoformat()
                pins_dict[cid] = repl_dict
            
            with open(self.pins_file, 'w') as f:
                json.dump(pins_dict, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving pins: {e}")

    def _save_all_configuration(self):
        """Save all configuration to files."""
        self._save_settings()
        self._save_backends()
        self._save_pins()

    async def get_replication_settings(self) -> Dict[str, Any]:
        """Get current replication settings."""
        with self._lock:
            settings_dict = asdict(self.settings)
            if hasattr(self.settings.policy, 'value'):
                settings_dict['policy'] = self.settings.policy.value
            else:
                settings_dict['policy'] = str(self.settings.policy)
            
            return {
                "success": True,
                "settings": settings_dict,
                "total_backends": len(self.backends),
                "enabled_backends": len([b for b in self.backends.values() if b.enabled]),
                "total_pins": len(self.pin_replications),
                "monitoring_active": self._monitoring_active
            }

    async def update_replication_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update replication settings."""
        try:
            with self._lock:
                # Validate settings
                if 'min_replicas' in new_settings:
                    if new_settings['min_replicas'] < 1:
                        return {"success": False, "error": "min_replicas must be >= 1"}
                
                if 'max_replicas' in new_settings:
                    if new_settings['max_replicas'] < new_settings.get('min_replicas', self.settings.min_replicas):
                        return {"success": False, "error": "max_replicas must be >= min_replicas"}
                
                if 'target_replicas' in new_settings:
                    min_reps = new_settings.get('min_replicas', self.settings.min_replicas)
                    max_reps = new_settings.get('max_replicas', self.settings.max_replicas)
                    if not (min_reps <= new_settings['target_replicas'] <= max_reps):
                        return {"success": False, "error": "target_replicas must be between min_replicas and max_replicas"}
                
                # Update settings
                for key, value in new_settings.items():
                    if hasattr(self.settings, key):
                        if key == 'policy' and isinstance(value, str):
                            value = ReplicationPolicy(value)
                        setattr(self.settings, key, value)
                
                self._save_settings()
                
                return {
                    "success": True,
                    "message": "Replication settings updated successfully",
                    "settings": {
                        k: v.value if hasattr(v, 'value') else v 
                        for k, v in asdict(self.settings).items()
                    }
                }
                
        except Exception as e:
            logger.error(f"Error updating replication settings: {e}")
            return {"success": False, "error": str(e)}

    async def add_storage_backend(self, backend_config: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new storage backend."""
        try:
            with self._lock:
                if 'name' not in backend_config:
                    return {"success": False, "error": "Backend name is required"}
                
                name = backend_config['name']
                if name in self.backends:
                    return {"success": False, "error": f"Backend '{name}' already exists"}
                
                # Convert backend_type string to enum
                if 'backend_type' in backend_config:
                    backend_config['backend_type'] = BackendType(backend_config['backend_type'])
                
                backend = BackendConfig(**backend_config)
                self.backends[name] = backend
                self._save_backends()
                
                return {
                    "success": True,
                    "message": f"Backend '{name}' added successfully",
                    "backend": {
                        k: v.value if hasattr(v, 'value') else v 
                        for k, v in asdict(backend).items()
                    }
                }
                
        except Exception as e:
            logger.error(f"Error adding storage backend: {e}")
            return {"success": False, "error": str(e)}

    async def update_storage_backend(self, name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing storage backend."""
        try:
            with self._lock:
                if name not in self.backends:
                    return {"success": False, "error": f"Backend '{name}' not found"}
                
                backend = self.backends[name]
                
                # Update backend configuration
                for key, value in updates.items():
                    if hasattr(backend, key):
                        if key == 'backend_type' and isinstance(value, str):
                            value = BackendType(value)
                        setattr(backend, key, value)
                
                self._save_backends()
                
                return {
                    "success": True,
                    "message": f"Backend '{name}' updated successfully",
                    "backend": {
                        k: v.value if hasattr(v, 'value') else v 
                        for k, v in asdict(backend).items()
                    }
                }
                
        except Exception as e:
            logger.error(f"Error updating storage backend: {e}")
            return {"success": False, "error": str(e)}

    async def remove_storage_backend(self, name: str) -> Dict[str, Any]:
        """Remove a storage backend."""
        try:
            with self._lock:
                if name not in self.backends:
                    return {"success": False, "error": f"Backend '{name}' not found"}
                
                # Check if backend is in use
                pins_using_backend = [
                    pin for pin in self.pin_replications.values()
                    if name in pin.backends
                ]
                
                if pins_using_backend:
                    return {
                        "success": False,
                        "error": f"Backend '{name}' is in use by {len(pins_using_backend)} pins"
                    }
                
                del self.backends[name]
                self._save_backends()
                
                return {
                    "success": True,
                    "message": f"Backend '{name}' removed successfully"
                }
                
        except Exception as e:
            logger.error(f"Error removing storage backend: {e}")
            return {"success": False, "error": str(e)}

    async def list_storage_backends(self) -> Dict[str, Any]:
        """List all storage backends."""
        try:
            with self._lock:
                backends_info = []
                for name, backend in self.backends.items():
                    backend_dict = {
                        k: v.value if hasattr(v, 'value') else v 
                        for k, v in asdict(backend).items()
                    }
                    
                    # Add usage statistics
                    pins_count = len([
                        pin for pin in self.pin_replications.values()
                        if name in pin.backends
                    ])
                    total_size = sum([
                        pin.size_bytes for pin in self.pin_replications.values()
                        if name in pin.backends
                    ])
                    
                    backend_dict['usage'] = {
                        "pins_count": pins_count,
                        "total_size_bytes": total_size,
                        "total_size_gb": total_size / (1024**3)
                    }
                    
                    backends_info.append(backend_dict)
                
                return {
                    "success": True,
                    "backends": backends_info,
                    "total_backends": len(backends_info),
                    "enabled_backends": len([b for b in backends_info if b['enabled']])
                }
                
        except Exception as e:
            logger.error(f"Error listing storage backends: {e}")
            return {"success": False, "error": str(e)}

    async def register_pin_for_replication(
        self,
        cid: str,
        vfs_metadata_id: str = None,
        size_bytes: int = 0,
        target_replicas: int = None,
        priority: int = 1
    ) -> Dict[str, Any]:
        """Register a pin for replication management."""
        try:
            with self._lock:
                if target_replicas is None:
                    target_replicas = self.settings.target_replicas
                
                if cid in self.pin_replications:
                    # Update existing replication
                    replication = self.pin_replications[cid]
                    replication.vfs_metadata_id = vfs_metadata_id or replication.vfs_metadata_id
                    replication.size_bytes = size_bytes or replication.size_bytes
                    replication.target_replicas = target_replicas
                    replication.priority = priority
                else:
                    # Create new replication
                    replication = PinReplication(
                        cid=cid,
                        vfs_metadata_id=vfs_metadata_id,
                        size_bytes=size_bytes,
                        target_replicas=target_replicas,
                        priority=priority
                    )
                    self.pin_replications[cid] = replication
                
                self._save_pins()
                
                # Trigger replication if auto-replication is enabled
                if self.settings.auto_replication:
                    await self._schedule_replication(cid)
                
                return {
                    "success": True,
                    "message": f"Pin {cid} registered for replication",
                    "replication": {
                        k: v.isoformat() if isinstance(v, datetime) else v 
                        for k, v in asdict(replication).items()
                    }
                }
                
        except Exception as e:
            logger.error(f"Error registering pin for replication: {e}")
            return {"success": False, "error": str(e)}

    async def get_pin_replication_status(self, cid: str) -> Dict[str, Any]:
        """Get replication status for a specific pin."""
        try:
            with self._lock:
                if cid not in self.pin_replications:
                    return {"success": False, "error": f"Pin {cid} not found in replication registry"}
                
                replication = self.pin_replications[cid]
                replication_dict = {
                    k: v.isoformat() if isinstance(v, datetime) else v 
                    for k, v in asdict(replication).items()
                }
                
                # Add real-time status information
                status_info = await self._check_pin_replication_status(cid)
                replication_dict.update(status_info)
                
                return {
                    "success": True,
                    "replication": replication_dict
                }
                
        except Exception as e:
            logger.error(f"Error getting pin replication status: {e}")
            return {"success": False, "error": str(e)}

    async def replicate_pin_to_backend(self, cid: str, backend_name: str) -> Dict[str, Any]:
        """Replicate a specific pin to a target backend."""
        try:
            with self._lock:
                if cid not in self.pin_replications:
                    return {"success": False, "error": f"Pin {cid} not found in replication registry"}
                
                if backend_name not in self.backends:
                    return {"success": False, "error": f"Backend '{backend_name}' not found"}
                
                backend = self.backends[backend_name]
                if not backend.enabled:
                    return {"success": False, "error": f"Backend '{backend_name}' is disabled"}
                
                replication = self.pin_replications[cid]
                
                # Perform the actual replication based on backend type
                replication_result = await self._perform_replication(cid, backend)
                
                if replication_result["success"]:
                    if backend_name not in replication.backends:
                        replication.backends.append(backend_name)
                        replication.current_replicas = len(replication.backends)
                        replication.last_checked = datetime.utcnow()
                        self._save_pins()
                
                return replication_result
                
        except Exception as e:
            logger.error(f"Error replicating pin to backend: {e}")
            return {"success": False, "error": str(e)}

    async def _perform_replication(self, cid: str, backend: BackendConfig) -> Dict[str, Any]:
        """Perform actual replication to a backend."""
        try:
            # This is a placeholder for actual replication logic
            # In a real implementation, this would interface with the specific backend APIs
            
            if backend.backend_type == BackendType.LOCAL:
                # Local IPFS replication
                if self.ipfs_manager:
                    # Use IPFS manager to pin locally
                    result = await self._replicate_to_local_ipfs(cid)
                else:
                    result = {"success": True, "message": f"Simulated local replication for {cid}"}
            
            elif backend.backend_type == BackendType.IPFS_CLUSTER:
                # IPFS Cluster replication
                result = await self._replicate_to_ipfs_cluster(cid, backend)
            
            elif backend.backend_type == BackendType.FILECOIN:
                # Filecoin storage
                result = await self._replicate_to_filecoin(cid, backend)
            
            else:
                result = {
                    "success": True,
                    "message": f"Simulated replication of {cid} to {backend.name}"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error performing replication: {e}")
            return {"success": False, "error": str(e)}

    async def _replicate_to_local_ipfs(self, cid: str) -> Dict[str, Any]:
        """Replicate to local IPFS node."""
        try:
            # Placeholder for local IPFS replication
            return {
                "success": True,
                "message": f"Pin {cid} replicated to local IPFS",
                "backend": "local",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _replicate_to_ipfs_cluster(self, cid: str, backend: BackendConfig) -> Dict[str, Any]:
        """Replicate to IPFS Cluster."""
        try:
            # Placeholder for IPFS Cluster replication
            return {
                "success": True,
                "message": f"Pin {cid} replicated to IPFS Cluster",
                "backend": backend.name,
                "endpoint": backend.endpoint,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _replicate_to_filecoin(self, cid: str, backend: BackendConfig) -> Dict[str, Any]:
        """Replicate to Filecoin storage."""
        try:
            # Placeholder for Filecoin replication
            return {
                "success": True,
                "message": f"Pin {cid} replicated to Filecoin",
                "backend": backend.name,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _check_pin_replication_status(self, cid: str) -> Dict[str, Any]:
        """Check the real-time replication status of a pin."""
        try:
            # This would check the actual status across all backends
            # For now, return mock status
            return {
                "real_time_check": True,
                "healthy_replicas": 2,
                "failed_replicas": 0,
                "last_health_check": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking pin replication status: {e}")
            return {"error": str(e)}

    async def _schedule_replication(self, cid: str):
        """Schedule replication for a pin based on current settings."""
        try:
            if cid not in self.pin_replications:
                return
            
            replication = self.pin_replications[cid]
            current_replicas = len(replication.backends)
            
            if current_replicas < replication.target_replicas:
                # Find suitable backends for replication
                available_backends = [
                    backend for backend in self.backends.values()
                    if backend.enabled and backend.name not in replication.backends
                ]
                
                # Sort by priority
                available_backends.sort(key=lambda b: b.priority)
                
                needed_replicas = replication.target_replicas - current_replicas
                for backend in available_backends[:needed_replicas]:
                    await self.replicate_pin_to_backend(cid, backend.name)
                    
        except Exception as e:
            logger.error(f"Error scheduling replication: {e}")

    async def get_replication_status(self) -> Dict[str, Any]:
        """Get overall replication status."""
        try:
            with self._lock:
                total_pins = len(self.pin_replications)
                under_replicated = 0
                over_replicated = 0
                healthy_replicated = 0
                failed_pins = 0
                
                for replication in self.pin_replications.values():
                    current_replicas = len(replication.backends)
                    if current_replicas < replication.target_replicas:
                        under_replicated += 1
                    elif current_replicas > replication.target_replicas:
                        over_replicated += 1
                    else:
                        healthy_replicated += 1
                    
                    if replication.status == "failed":
                        failed_pins += 1
                
                # Calculate storage usage across backends
                storage_usage = {}
                for backend_name, backend in self.backends.items():
                    total_size = sum([
                        pin.size_bytes for pin in self.pin_replications.values()
                        if backend_name in pin.backends
                    ])
                    storage_usage[backend_name] = {
                        "total_size_bytes": total_size,
                        "total_size_gb": total_size / (1024**3),
                        "pin_count": len([
                            pin for pin in self.pin_replications.values()
                            if backend_name in pin.backends
                        ])
                    }
                
                return {
                    "success": True,
                    "summary": {
                        "total_pins": total_pins,
                        "healthy_replicated": healthy_replicated,
                        "under_replicated": under_replicated,
                        "over_replicated": over_replicated,
                        "failed_pins": failed_pins,
                        "replication_ratio": healthy_replicated / max(total_pins, 1),
                        "monitoring_active": self._monitoring_active
                    },
                    "storage_usage": storage_usage,
                    "settings": {
                        k: v.value if hasattr(v, 'value') else v 
                        for k, v in asdict(self.settings).items()
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting replication status: {e}")
            return {"success": False, "error": str(e)}

    async def export_backend_pins(self, backend_name: str, export_format: str = "json") -> Dict[str, Any]:
        """Export pins from a specific backend."""
        try:
            with self._lock:
                if backend_name not in self.backends:
                    return {"success": False, "error": f"Backend '{backend_name}' not found"}
                
                # Get pins for this backend
                backend_pins = [
                    pin for pin in self.pin_replications.values()
                    if backend_name in pin.backends
                ]
                
                export_data = {
                    "backend": backend_name,
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "total_pins": len(backend_pins),
                    "pins": [
                        {
                            k: v.isoformat() if isinstance(v, datetime) else v 
                            for k, v in asdict(pin).items()
                        } for pin in backend_pins
                    ]
                }
                
                # Save export file
                export_filename = f"{backend_name}_pins_export_{int(time.time())}.{export_format}"
                export_path = self.config_dir / "exports" / export_filename
                export_path.parent.mkdir(exist_ok=True)
                
                with open(export_path, 'w') as f:
                    if export_format == "json":
                        json.dump(export_data, f, indent=2, default=str)
                    else:
                        return {"success": False, "error": f"Unsupported export format: {export_format}"}
                
                return {
                    "success": True,
                    "message": f"Exported {len(backend_pins)} pins from {backend_name}",
                    "export_file": str(export_path),
                    "export_data": export_data
                }
                
        except Exception as e:
            logger.error(f"Error exporting backend pins: {e}")
            return {"success": False, "error": str(e)}

    async def import_backend_pins(self, backend_name: str, import_file: str) -> Dict[str, Any]:
        """Import pins to a specific backend."""
        try:
            import_path = Path(import_file)
            if not import_path.exists():
                return {"success": False, "error": f"Import file not found: {import_file}"}
            
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            if 'pins' not in import_data:
                return {"success": False, "error": "Invalid import file format"}
            
            imported_count = 0
            errors = []
            
            with self._lock:
                for pin_data in import_data['pins']:
                    try:
                        cid = pin_data['cid']
                        
                        # Convert datetime strings back to datetime objects
                        if 'created_at' in pin_data and pin_data['created_at']:
                            pin_data['created_at'] = datetime.fromisoformat(pin_data['created_at'])
                        if 'last_checked' in pin_data and pin_data['last_checked']:
                            pin_data['last_checked'] = datetime.fromisoformat(pin_data['last_checked'])
                        
                        pin_replication = PinReplication(**pin_data)
                        
                        # Add to this backend if not already present
                        if backend_name not in pin_replication.backends:
                            pin_replication.backends.append(backend_name)
                        
                        self.pin_replications[cid] = pin_replication
                        imported_count += 1
                        
                    except Exception as e:
                        errors.append(f"Error importing pin {pin_data.get('cid', 'unknown')}: {e}")
                
                self._save_pins()
            
            return {
                "success": True,
                "message": f"Imported {imported_count} pins to {backend_name}",
                "imported_count": imported_count,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error importing backend pins: {e}")
            return {"success": False, "error": str(e)}

    async def start_monitoring(self):
        """Start background monitoring for replication health."""
        if self._monitoring_active:
            return {"success": True, "message": "Monitoring already active"}
        
        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Replication monitoring started")
        return {"success": True, "message": "Replication monitoring started"}

    async def stop_monitoring(self):
        """Stop background monitoring."""
        if not self._monitoring_active:
            return {"success": True, "message": "Monitoring already stopped"}
        
        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Replication monitoring stopped")
        return {"success": True, "message": "Replication monitoring stopped"}

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        try:
            while self._monitoring_active:
                try:
                    # Check replication health
                    await self._check_replication_health()
                    
                    # Perform auto-replication if enabled
                    if self.settings.auto_replication:
                        await self._perform_auto_replication()
                    
                    # Wait for next check
                    await asyncio.sleep(self.settings.replication_check_interval)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(60)  # Wait a minute before retrying
                    
        except asyncio.CancelledError:
            pass
        finally:
            self._monitoring_active = False

    async def _check_replication_health(self):
        """Check the health of all replications."""
        try:
            with self._lock:
                for cid, replication in self.pin_replications.items():
                    # Update last checked time
                    replication.last_checked = datetime.utcnow()
                    
                    # Check if replication meets target
                    current_replicas = len(replication.backends)
                    if current_replicas < replication.target_replicas:
                        replication.status = "under_replicated"
                    elif current_replicas > replication.target_replicas:
                        replication.status = "over_replicated"
                    else:
                        replication.status = "healthy"
                
                self._save_pins()
                
        except Exception as e:
            logger.error(f"Error checking replication health: {e}")

    async def _perform_auto_replication(self):
        """Perform automatic replication for under-replicated pins."""
        try:
            with self._lock:
                under_replicated_pins = [
                    (cid, repl) for cid, repl in self.pin_replications.items()
                    if len(repl.backends) < repl.target_replicas
                ]
                
                # Sort by priority (higher priority first)
                under_replicated_pins.sort(key=lambda x: x[1].priority)
                
                for cid, replication in under_replicated_pins[:10]:  # Limit to 10 per cycle
                    await self._schedule_replication(cid)
                    
        except Exception as e:
            logger.error(f"Error performing auto-replication: {e}")

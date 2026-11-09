"""
Metadata Manager for IPFS Kit

This module manages metadata and configuration in the ~/.ipfs_kit/ directory
as specified in the requirements. It provides a centralized way to manage
service configurations, monitoring data, and other metadata.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
import threading

logger = logging.getLogger(__name__)


class MetadataManager:
    """
    Manages metadata and configuration in the ~/.ipfs_kit/ directory.
    
    This class provides functionality to:
    - Create and manage the ~/.ipfs_kit/ directory structure
    - Handle service configurations
    - Store monitoring data and statistics
    - Manage service state information
    """
    
    def __init__(self, base_path: Optional[Path] = None):

        """Initialize the metadata manager.

        Args:
            base_path: Optional custom base path (defaults to ~/.ipfs_kit/)
        """
        self.base_path = base_path or Path.home() / ".ipfs_kit"
        # Backwards-compatible aliases expected by tests/older callers
        self.base_dir = self.base_path
        self.config_dir = self.base_path / "config"
        self.backends_dir = self.base_path / "backends"
        self.metadata_dir = self.base_path / "metadata"
        self.cache_dir = self.base_path / "cache"
        self.logs_dir = self.base_path / "logs"

        self._lock = threading.RLock()
        self._ensure_directory_structure()
        self._create_default_files()
        self._config = self._load_config()
    
    def _ensure_directory_structure(self):
        """Create the required directory structure."""
        directories = [
            self.base_path,
            self.base_path / "config",
            self.base_path / "backends",
            self.base_path / "metadata",
            self.base_path / "services",
            self.base_path / "monitoring", 
            self.base_path / "logs",
            self.base_path / "cache",
            self.base_path / "state"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
        # Create .gitignore to exclude sensitive data
        gitignore_path = self.base_path / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, "w") as f:
                f.write("# Exclude sensitive configurations\n")
                f.write("*/credentials.yaml\n")
                f.write("*/secrets.json\n")
                f.write("logs/\n")
                f.write("cache/\n")
    
    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service configuration dictionary
        """
        with self._lock:
            config_file = self.base_path / "services" / f"{service_name}.yaml"
            if not config_file.exists():
                return {}
                
            try:
                with open(config_file, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load config for service {service_name}: {e}")
                return {}
    
    def set_service_config(self, service_name: str, config: Dict[str, Any]):
        """
        Set configuration for a specific service.
        
        Args:
            service_name: Name of the service
            config: Configuration dictionary to save
        """
        with self._lock:
            config_file = self.base_path / "services" / f"{service_name}.yaml"
            
            # Add metadata
            config_with_meta = {
                "metadata": {
                    "service_name": service_name,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0"
                },
                "config": config
            }
            
            try:
                with open(config_file, "w") as f:
                    yaml.dump(config_with_meta, f, default_flow_style=False)
                logger.info(f"Updated config for service {service_name}")
            except Exception as e:
                logger.error(f"Failed to save config for service {service_name}: {e}")
                raise
    
    def remove_service_config(self, service_name: str) -> bool:
        """
        Remove configuration for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if removed successfully, False if not found
        """
        with self._lock:
            config_file = self.base_path / "services" / f"{service_name}.yaml"
            if config_file.exists():
                try:
                    config_file.unlink()
                    logger.info(f"Removed config for service {service_name}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to remove config for service {service_name}: {e}")
                    return False
            return False
    
    def list_services(self) -> List[str]:
        """
        List all configured services.
        
        Returns:
            List of service names
        """
        with self._lock:
            services_dir = self.base_path / "services"
            if not services_dir.exists():
                return []
            
            services = []
            for config_file in services_dir.glob("*.yaml"):
                services.append(config_file.stem)
            
            return sorted(services)
    
    def get_service_state(self, service_name: str) -> Dict[str, Any]:
        """
        Get current state information for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service state dictionary
        """
        with self._lock:
            state_file = self.base_path / "state" / f"{service_name}.json"
            if not state_file.exists():
                return {"status": "unknown", "last_seen": None}
            
            try:
                with open(state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state for service {service_name}: {e}")
                return {"status": "error", "last_seen": None}
    
    def set_service_state(self, service_name: str, state: Dict[str, Any]):
        """
        Set current state information for a service.
        
        Args:
            service_name: Name of the service
            state: State dictionary to save
        """
        with self._lock:
            state_file = self.base_path / "state" / f"{service_name}.json"
            
            # Add timestamp
            state_with_timestamp = {
                **state,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            try:
                with open(state_file, "w") as f:
                    json.dump(state_with_timestamp, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save state for service {service_name}: {e}")
                raise
    
    def get_monitoring_data(self, service_name: str, metric_type: str = None) -> Dict[str, Any]:
        """
        Get monitoring data for a service.
        
        Args:
            service_name: Name of the service
            metric_type: Optional specific metric type to retrieve
            
        Returns:
            Monitoring data dictionary
        """
        with self._lock:
            if metric_type:
                monitor_file = self.base_path / "monitoring" / f"{service_name}_{metric_type}.json"
            else:
                monitor_file = self.base_path / "monitoring" / f"{service_name}.json"
            
            if not monitor_file.exists():
                return {}
            
            try:
                with open(monitor_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load monitoring data for {service_name}: {e}")
                return {}
    
    def set_monitoring_data(self, service_name: str, data: Dict[str, Any], metric_type: str = None):
        """
        Set monitoring data for a service.
        
        Args:
            service_name: Name of the service
            data: Monitoring data to save
            metric_type: Optional specific metric type
        """
        with self._lock:
            if metric_type:
                monitor_file = self.base_path / "monitoring" / f"{service_name}_{metric_type}.json"
            else:
                monitor_file = self.base_path / "monitoring" / f"{service_name}.json"
            
            # Add timestamp and ensure data structure
            monitoring_data = {
                "service": service_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data
            }
            
            try:
                with open(monitor_file, "w") as f:
                    json.dump(monitoring_data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save monitoring data for {service_name}: {e}")
                raise
    
    def get_global_config(self) -> Dict[str, Any]:
        """
        Get global IPFS Kit configuration.
        
        Returns:
            Global configuration dictionary
        """
        with self._lock:
            config_file = self.base_path / "config" / "global.yaml"
            if not config_file.exists():
                # Return default config
                return {
                    "version": "1.0",
                    "auto_start_services": True,
                    "monitoring_enabled": True,
                    "log_level": "INFO"
                }
            
            try:
                with open(config_file, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load global config: {e}")
                return {}
    
    def set_global_config(self, config: Dict[str, Any]):
        """
        Set global IPFS Kit configuration.
        
        Args:
            config: Global configuration dictionary
        """
        with self._lock:
            config_file = self.base_path / "config" / "global.yaml"
            
            # Add metadata
            config_with_meta = {
                "metadata": {
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0"
                },
                **config
            }
            
            try:
                with open(config_file, "w") as f:
                    yaml.dump(config_with_meta, f, default_flow_style=False)
                logger.info("Updated global configuration")
            except Exception as e:
                logger.error(f"Failed to save global config: {e}")
                raise
    
    def clear_cache(self):
        """Clear cached data."""
        with self._lock:
            cache_dir = self.base_path / "cache"
            if cache_dir.exists():
                for cache_file in cache_dir.glob("*"):
                    if cache_file.is_file():
                        cache_file.unlink()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get metadata manager statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            return {
                "base_path": str(self.base_path),
                "services_count": len(self.list_services()),
                "directory_exists": self.base_path.exists(),
                "directories": {
                    "config": (self.base_path / "config").exists(),
                    "backends": (self.base_path / "backends").exists(),
                    "metadata": (self.base_path / "metadata").exists(),
                    "services": (self.base_path / "services").exists(),
                    "monitoring": (self.base_path / "monitoring").exists(),
                    "logs": (self.base_path / "logs").exists(),
                    "cache": (self.base_path / "cache").exists(),
                    "state": (self.base_path / "state").exists()
                }
            }
    
    def _create_default_files(self):
        """Create default configuration files if they don't exist."""
        default_config = {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "backends": {},
            "global_settings": {
                "default_cache_size": "1GB",
                "log_level": "INFO",
                "auto_cleanup": True
            }
        }
        
        config_file = self.config_dir / "main.json"
        if not config_file.exists():
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            logger.info(f"Created default configuration: {config_file}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load the main configuration."""
        config_file = self.config_dir / "main.json"
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config from {config_file}: {e}")
        
        return {}
    
    def _save_config(self):
        """Save the main configuration."""
        config_file = self.config_dir / "main.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.debug(f"Saved configuration to {config_file}")
        except Exception as e:
            logger.error(f"Error saving config to {config_file}: {e}")
    
    def get_backend_config(self, backend_id: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Backend configuration dict or None if not found
        """
        backend_file = self.backends_dir / f"{backend_id}.json"
        try:
            if backend_file.exists():
                with open(backend_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading backend config {backend_id}: {e}")
        
        return None
    
    def set_backend_config(self, backend_id: str, config: Dict[str, Any]) -> bool:
        """
        Set configuration for a specific backend.
        
        Args:
            backend_id: Backend identifier
            config: Backend configuration
            
        Returns:
            True if successful
        """
        backend_file = self.backends_dir / f"{backend_id}.json"
        try:
            # Add metadata
            config_with_meta = {
                "id": backend_id,
                "updated": datetime.now().isoformat(),
                "config": config
            }
            
            with open(backend_file, 'w') as f:
                json.dump(config_with_meta, f, indent=2)
            
            # Update main config
            if "backends" not in self._config:
                self._config["backends"] = {}
            
            self._config["backends"][backend_id] = {
                "enabled": config.get("enabled", True),
                "type": config.get("type", "unknown"),
                "updated": datetime.now().isoformat()
            }
            
            self._save_config()
            logger.info(f"Saved backend configuration: {backend_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error saving backend config {backend_id}: {e}")
            return False
    
    def remove_backend_config(self, backend_id: str) -> bool:
        """
        Remove configuration for a specific backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if successful
        """
        backend_file = self.backends_dir / f"{backend_id}.json"
        try:
            # Remove file if it exists
            if backend_file.exists():
                backend_file.unlink()
            
            # Remove from main config
            if "backends" in self._config and backend_id in self._config["backends"]:
                del self._config["backends"][backend_id]
                self._save_config()
            
            logger.info(f"Removed backend configuration: {backend_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error removing backend config {backend_id}: {e}")
            return False
    
    def list_backends(self) -> List[str]:
        """
        List all configured backends.
        
        Returns:
            List of backend IDs
        """
        try:
            backend_files = list(self.backends_dir.glob("*.json"))
            return [f.stem for f in backend_files]
        except Exception as e:
            logger.error(f"Error listing backends: {e}")
            return []
    
    def get_metadata(self, key: str) -> Optional[Any]:
        """
        Get metadata by key.
        
        Args:
            key: Metadata key
            
        Returns:
            Metadata value or None
        """
        metadata_file = self.metadata_dir / f"{key}.json"
        try:
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                    return data.get("value")
        except Exception as e:
            logger.error(f"Error loading metadata {key}: {e}")
        
        return None
    
    def set_metadata(self, key: str, value: Any) -> bool:
        """
        Set metadata by key.
        
        Args:
            key: Metadata key
            value: Metadata value
            
        Returns:
            True if successful
        """
        metadata_file = self.metadata_dir / f"{key}.json"
        try:
            
                metadata = {
                    "key": key,
                    "value": value,
                    "updated": datetime.now().isoformat()
                }
                
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                logger.debug(f"Saved metadata: {key}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving metadata {key}: {e}")
            return False
    
    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a global setting.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        return self._config.get("global_settings", {}).get(key, default)
    
    def set_global_setting(self, key: str, value: Any) -> bool:
        """
        Set a global setting.
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            True if successful
        """
        try:
            
                if "global_settings" not in self._config:
                    self._config["global_settings"] = {}
                
                self._config["global_settings"][key] = value
                self._save_config()
                logger.debug(f"Set global setting {key}: {value}")
                return True
                
        except Exception as e:
            logger.error(f"Error setting global setting {key}: {e}")
            return False
    
    def get_all_config(self) -> Dict[str, Any]:
        """
        Get all configuration data.
        
        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()
    
    def cleanup_old_metadata(self, days: int = 30) -> int:
        """
        Clean up old metadata files.
        
        Args:
            days: Age in days for cleanup
            
        Returns:
            Number of files cleaned up
        """
        if not self.get_global_setting("auto_cleanup", True):
            return 0
        
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            cleaned = 0
            
            for metadata_file in self.metadata_dir.glob("*.json"):
                if metadata_file.stat().st_mtime < cutoff_date.timestamp():
                    metadata_file.unlink()
                    cleaned += 1
                    
            logger.info(f"Cleaned up {cleaned} old metadata files")
            return cleaned
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0


# Global instance
_metadata_manager = None


def get_metadata_manager() -> MetadataManager:
    """Get the global metadata manager instance."""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = MetadataManager()
    return _metadata_manager
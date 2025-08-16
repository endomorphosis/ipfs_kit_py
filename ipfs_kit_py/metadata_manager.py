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
        """
        Initialize the metadata manager.
        
        Args:
            base_path: Optional custom base path (defaults to ~/.ipfs_kit/)
        """
        self.base_path = base_path or Path.home() / ".ipfs_kit"
        self._lock = threading.RLock()
        self._ensure_directory_structure()
    
    def _ensure_directory_structure(self):
        """Create the required directory structure."""
        directories = [
            self.base_path,
            self.base_path / "config",
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
                    "services": (self.base_path / "services").exists(),
                    "monitoring": (self.base_path / "monitoring").exists(),
                    "logs": (self.base_path / "logs").exists(),
                    "cache": (self.base_path / "cache").exists(),
                    "state": (self.base_path / "state").exists()
                }
            }


# Global instance
_metadata_manager = None


def get_metadata_manager() -> MetadataManager:
    """Get the global metadata manager instance."""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = MetadataManager()
    return _metadata_manager
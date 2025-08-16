"""
IPFS Kit Metadata Manager

This module manages metadata and configuration in the ~/.ipfs_kit/ directory
before falling back to the main ipfs_kit_py library calls.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class MetadataManager:
    """
    Manages metadata and configuration in ~/.ipfs_kit/ directory.
    
    This provides a local metadata layer that MCP tools check first
    before making calls to the ipfs_kit_py library.
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the metadata manager.
        
        Args:
            base_dir: Base directory for metadata. Defaults to ~/.ipfs_kit/
        """
        self.base_dir = base_dir or Path.home() / ".ipfs_kit"
        self.lock = threading.Lock()
        
        # Core directories
        self.config_dir = self.base_dir / "config"
        self.metadata_dir = self.base_dir / "metadata"
        self.backends_dir = self.base_dir / "backends"
        self.cache_dir = self.base_dir / "cache"
        self.logs_dir = self.base_dir / "logs"
        
        # Initialize directory structure
        self._init_directories()
        
        # Load configuration
        self._config = self._load_config()
        
    def _init_directories(self):
        """Create the directory structure if it doesn't exist."""
        directories = [
            self.base_dir,
            self.config_dir,
            self.metadata_dir,
            self.backends_dir,
            self.cache_dir,
            self.logs_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
            
        # Create default files
        self._create_default_files()
    
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
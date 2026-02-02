#!/usr/bin/env python3
"""
MCP Configuration Manager

Manages configuration for the MCP server by reading from ~/.ipfs_kit/ files.
This is a lightweight config manager focused on atomic operations.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml

logger = logging.getLogger(__name__)


class MCPConfigManager:
    """Configuration manager for MCP server that reads from ~/.ipfs_kit/ files."""
    
    def __init__(self, data_dir: Path):
        """Initialize the MCP config manager.
        
        Args:
            data_dir: Path to ~/.ipfs_kit/ directory
        """
        self.data_dir = Path(data_dir).expanduser()
        self.config_file = self.data_dir / "config.json"
        self.mcp_config_file = self.data_dir / "mcp_config.json"
        
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        
        logger.info(f"MCP Config Manager initialized with data_dir: {self.data_dir}")
    
    def get_config(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get configuration value(s).
        
        Args:
            key: Configuration key (dot notation supported, e.g. 'mcp.port')
            default: Default value if key not found
            
        Returns:
            Configuration value or entire config if key is None
        """
        try:
            # Load main config
            config = {}
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            # Load MCP-specific config
            mcp_config = {}
            if self.mcp_config_file.exists():
                with open(self.mcp_config_file, 'r') as f:
                    mcp_config = json.load(f)
            
            # Merge configs (MCP config takes precedence)
            config.update(mcp_config)
            
            if key is None:
                return config
            
            # Support dot notation
            value = config
            for part in key.split('.'):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            
            return value
            
        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return default if key else {}
    
    def set_config(self, key: str, value: Any, mcp_specific: bool = True) -> bool:
        """Set configuration value.
        
        Args:
            key: Configuration key (dot notation supported)
            value: Value to set
            mcp_specific: If True, save to mcp_config.json, else config.json
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Choose config file
            config_file = self.mcp_config_file if mcp_specific else self.config_file
            
            # Load existing config
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Set value using dot notation
            current = config
            parts = key.split('.')
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
            
            # Save config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Set config {key} = {value} in {config_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting config {key}: {e}")
            return False
    
    def get_mcp_config(self) -> Dict[str, Any]:
        """Get MCP-specific configuration.
        
        Returns:
            MCP configuration dictionary
        """
        default_config = {
            "host": "127.0.0.1",
            "port": 3000,
            "transport": "stdio",  # stdio or websocket
            "debug": False,
            "max_cache_size": 1000,
            "cache_ttl_seconds": 300,
            "enable_file_watching": True,
            "atomic_operations_only": True
        }
        
        config = self.get_config("mcp", {})
        
        # Merge with defaults
        for key, default_value in default_config.items():
            if key not in config:
                config[key] = default_value
        
        return config
    
    def update_mcp_config(self, updates: Dict[str, Any]) -> bool:
        """Update MCP configuration.
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_config = self.get_mcp_config()
            current_config.update(updates)
            return self.set_config("mcp", current_config, mcp_specific=True)
        except Exception as e:
            logger.error(f"Error updating MCP config: {e}")
            return False
    
    def get_backends_config(self) -> Dict[str, Any]:
        """Get backends configuration from backend_index.
        
        Returns:
            Backends configuration dictionary
        """
        try:
            backend_index_file = self.data_dir / "backend_index.parquet"
            if backend_index_file.exists():
                import pandas as pd
                df = pd.read_parquet(backend_index_file)
                
                # Convert to dict format
                backends = {}
                for _, row in df.iterrows():
                    backend_name = row.get('backend_name', '')
                    if backend_name:
                        backends[backend_name] = {
                            'type': row.get('backend_type', ''),
                            'health_status': row.get('health_status', 'unknown'),
                            'last_health_check': row.get('last_health_check'),
                            'config': row.get('config', {}) if pd.notna(row.get('config')) else {}
                        }
                
                return backends
            
        except Exception as e:
            logger.warning(f"Could not read backends config: {e}")
        
        return {}
    
    def get_daemon_config(self) -> Dict[str, Any]:
        """Get daemon configuration.
        
        Returns:
            Daemon configuration dictionary
        """
        return self.get_config("daemon", {
            "auto_start": False,
            "port": 9999,
            "role": "local",
            "sync_interval": 300,
            "health_check_interval": 60
        })
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration.
        
        Returns:
            Validation results dictionary
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "config_files": {}
        }
        
        # Check config files
        for name, path in [
            ("main", self.config_file),
            ("mcp", self.mcp_config_file)
        ]:
            results["config_files"][name] = {
                "exists": path.exists(),
                "readable": False,
                "valid_json": False
            }
            
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        json.load(f)
                    results["config_files"][name]["readable"] = True
                    results["config_files"][name]["valid_json"] = True
                except Exception as e:
                    results["errors"].append(f"Invalid JSON in {name} config: {e}")
                    results["valid"] = False
        
        # Validate MCP config
        mcp_config = self.get_mcp_config()
        if not isinstance(mcp_config.get("port"), int):
            results["errors"].append("MCP port must be an integer")
            results["valid"] = False
        
        if mcp_config.get("port", 0) <= 0 or mcp_config.get("port", 0) > 65535:
            results["errors"].append("MCP port must be between 1 and 65535")
            results["valid"] = False
        
        if mcp_config.get("transport") not in ["stdio", "websocket"]:
            results["warnings"].append("MCP transport should be 'stdio' or 'websocket'")
        
        return results


def get_mcp_config_manager(data_dir: Union[str, Path] = "~/.ipfs_kit") -> MCPConfigManager:
    """Get MCP configuration manager instance.
    
    Args:
        data_dir: Path to data directory
        
    Returns:
        MCPConfigManager instance
    """
    return MCPConfigManager(data_dir)

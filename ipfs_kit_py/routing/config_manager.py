"""
Configuration Management for the Routing System

This module handles loading, saving, and validating configurations
for the optimized data routing system.
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

# Configure logging
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "enabled": True,
    "default_strategy": "hybrid",
    "default_priority": "balanced",
    "collect_metrics_on_startup": True,
    "auto_start_background_tasks": True,
    "learning_enabled": True,
    "telemetry_interval": 300,
    "metrics_retention_days": 7,
    "backends": ["ipfs", "filecoin", "s3", "local"],
    "optimization_weights": {
        "network_quality": 0.25,
        "content_match": 0.2,
        "cost_efficiency": 0.2,
        "geographic_proximity": 0.15,
        "load_balancing": 0.05,
        "reliability": 0.1,
        "historical_success": 0.05
    },
    "backend_costs": {
        "ipfs": {
            "storage_cost_per_gb": 0.0,
            "retrieval_cost_per_gb": 0.0
        },
        "filecoin": {
            "storage_cost_per_gb": 0.00002,
            "retrieval_cost_per_gb": 0.0001
        },
        "s3": {
            "storage_cost_per_gb": 0.023,
            "retrieval_cost_per_gb": 0.0
        },
        "local": {
            "storage_cost_per_gb": 0.0,
            "retrieval_cost_per_gb": 0.0
        }
    },
    "content_type_preferences": {
        "image/*": ["ipfs", "local", "s3"],
        "video/*": ["filecoin", "ipfs", "s3"],
        "text/*": ["local", "ipfs", "s3"],
        "application/pdf": ["ipfs", "local", "s3"],
        "application/json": ["local", "ipfs", "s3"]
    }
}


class RoutingConfigManager:
    """
    Manager for routing system configuration.
    
    This class handles loading, saving, and validating configurations
    for the optimized data routing system.
    """
    
    def __init__(
        self,
        config_dir: Optional[Union[str, Path]] = None,
        config_file: Optional[str] = "routing_config.json",
        policy_file: Optional[str] = "routing_policies.json",
        auto_create: bool = True
    ):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory for configuration files (default: XDG_CONFIG_HOME/ipfs_kit_py/routing)
            config_file: Name of the main configuration file
            policy_file: Name of the routing policies file
            auto_create: Whether to create default configuration if not found
        """
        # Set configuration directory
        self.config_dir = self._resolve_config_dir(config_dir)
        
        # Set file paths
        self.config_path = os.path.join(self.config_dir, config_file)
        self.policy_path = os.path.join(self.config_dir, policy_file)
        
        # Initialize configuration
        self.config = None
        self.policies = None
        
        # Create configuration directory if it doesn't exist
        if auto_create and not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            logger.info(f"Created configuration directory: {self.config_dir}")
        
        logger.debug(f"Routing configuration manager initialized with config_dir: {self.config_dir}")
    
    def _resolve_config_dir(self, config_dir: Optional[Union[str, Path]]) -> str:
        """
        Resolve the configuration directory.
        
        If config_dir is not provided, use the standard XDG directories:
        - Linux: $XDG_CONFIG_HOME/ipfs_kit_py/routing or ~/.config/ipfs_kit_py/routing
        - macOS: ~/Library/Application Support/ipfs_kit_py/routing
        - Windows: %APPDATA%\\ipfs_kit_py\\routing
        
        Args:
            config_dir: Directory for configuration files
            
        Returns:
            Resolved configuration directory
        """
        if config_dir:
            # Use provided directory
            return os.path.abspath(os.path.expanduser(config_dir))
        
        # Determine platform-specific config directory
        if os.name == "posix":
            if sys.platform == "darwin":  # macOS
                base_dir = os.path.expanduser("~/Library/Application Support")
            else:  # Linux and other POSIX
                base_dir = os.environ.get(
                    "XDG_CONFIG_HOME", 
                    os.path.expanduser("~/.config")
                )
        else:  # Windows
            base_dir = os.environ.get("APPDATA", os.path.expanduser("~"))
        
        return os.path.join(base_dir, "ipfs_kit_py", "routing")
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load routing configuration.
        
        Returns:
            Configuration dictionary
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    logger.info(f"Loaded configuration from {self.config_path}")
                    
                    # Validate and merge with defaults to ensure all required fields
                    self.config = self._merge_with_defaults(config)
                    return self.config
            except Exception as e:
                logger.error(f"Error loading configuration: {e}", exc_info=True)
        
        # Use default configuration
        logger.info(f"Using default configuration (no file found at {self.config_path})")
        self.config = DEFAULT_CONFIG.copy()
        
        # Save default configuration
        self.save_config()
        
        return self.config
    
    def load_policies(self) -> Dict[str, Any]:
        """
        Load routing policies.
        
        Returns:
            Policies dictionary
        """
        if os.path.exists(self.policy_path):
            try:
                with open(self.policy_path, "r") as f:
                    self.policies = json.load(f)
                    logger.info(f"Loaded policies from {self.policy_path}")
                    return self.policies
            except Exception as e:
                logger.error(f"Error loading policies: {e}", exc_info=True)
        
        # Use default policies
        logger.info(f"Using default policies (no file found at {self.policy_path})")
        self.policies = {
            "content_rules": [],
            "backend_rules": [],
            "time_rules": []
        }
        
        # Save default policies
        self.save_policies()
        
        return self.policies
    
    def save_config(self) -> bool:
        """
        Save configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        if self.config is None:
            logger.warning("No configuration to save")
            return False
        
        try:
            # Create config directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Write to temporary file first to prevent corruption
            with tempfile.NamedTemporaryFile(
                mode="w", 
                dir=os.path.dirname(self.config_path), 
                delete=False
            ) as tf:
                json.dump(self.config, tf, indent=2)
                temp_path = tf.name
            
            # Replace the old file
            os.replace(temp_path, self.config_path)
            logger.info(f"Saved configuration to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}", exc_info=True)
            return False
    
    def save_policies(self) -> bool:
        """
        Save policies to file.
        
        Returns:
            True if successful, False otherwise
        """
        if self.policies is None:
            logger.warning("No policies to save")
            return False
        
        try:
            # Create config directory if it doesn't exist
            os.makedirs(os.path.dirname(self.policy_path), exist_ok=True)
            
            # Write to temporary file first to prevent corruption
            with tempfile.NamedTemporaryFile(
                mode="w", 
                dir=os.path.dirname(self.policy_path), 
                delete=False
            ) as tf:
                json.dump(self.policies, tf, indent=2)
                temp_path = tf.name
            
            # Replace the old file
            os.replace(temp_path, self.policy_path)
            logger.info(f"Saved policies to {self.policy_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving policies: {e}", exc_info=True)
            return False
    
    def update_config(
        self,
        updates: Dict[str, Any],
        save: bool = True
    ) -> Dict[str, Any]:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of updates
            save: Whether to save the updated configuration
            
        Returns:
            Updated configuration
        """
        if self.config is None:
            self.load_config()
        
        # Deep update
        self._deep_update(self.config, updates)
        
        # Save if requested
        if save:
            self.save_config()
        
        return self.config
    
    def reset_to_defaults(self, save: bool = True) -> Dict[str, Any]:
        """
        Reset configuration to defaults.
        
        Args:
            save: Whether to save the reset configuration
            
        Returns:
            Default configuration
        """
        self.config = DEFAULT_CONFIG.copy()
        
        # Save if requested
        if save:
            self.save_config()
        
        return self.config
    
    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge configuration with defaults to ensure all required fields.
        
        Args:
            config: User configuration
            
        Returns:
            Merged configuration
        """
        result = DEFAULT_CONFIG.copy()
        self._deep_update(result, config)
        return result
    
    def _deep_update(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any]
    ) -> None:
        """
        Deep update a dictionary.
        
        Args:
            target: Target dictionary to update
            source: Source dictionary with updates
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                # Recursively update nested dictionaries
                self._deep_update(target[key], value)
            else:
                # Update or add value
                target[key] = value


def get_data_dir() -> str:
    """
    Get the data directory for routing data.
    
    Returns:
        Data directory path
    """
    # Determine platform-specific data directory
    if os.name == "posix":
        if sys.platform == "darwin":  # macOS
            base_dir = os.path.expanduser("~/Library/Application Support")
        else:  # Linux and other POSIX
            base_dir = os.environ.get(
                "XDG_DATA_HOME", 
                os.path.expanduser("~/.local/share")
            )
    else:  # Windows
        base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    
    data_dir = os.path.join(base_dir, "ipfs_kit_py", "routing", "data")
    
    # Create directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    
    return data_dir


def get_cache_dir() -> str:
    """
    Get the cache directory for routing.
    
    Returns:
        Cache directory path
    """
    # Determine platform-specific cache directory
    if os.name == "posix":
        if sys.platform == "darwin":  # macOS
            base_dir = os.path.expanduser("~/Library/Caches")
        else:  # Linux and other POSIX
            base_dir = os.environ.get(
                "XDG_CACHE_HOME", 
                os.path.expanduser("~/.cache")
            )
    else:  # Windows
        base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        base_dir = os.path.join(base_dir, "Temp")
    
    cache_dir = os.path.join(base_dir, "ipfs_kit_py", "routing")
    
    # Create directory if it doesn't exist
    os.makedirs(cache_dir, exist_ok=True)
    
    return cache_dir


import sys  # Missing import at the top, adding here to make the code work
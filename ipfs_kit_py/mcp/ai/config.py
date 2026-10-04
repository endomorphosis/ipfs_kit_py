"""
AI/ML Configuration Module for MCP Server

This module provides configuration management for AI/ML components, including:
1. Framework-specific settings
2. Storage paths
3. Environment-based configuration
4. Secure credential handling

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import os
import json
import logging
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Set
from pathlib import Path
import tempfile

# Configure logger
logger = logging.getLogger(__name__)


class AIMLConfig:
    """
    Configuration manager for AI/ML components.
    
    This class provides methods for managing and accessing
    configuration settings for AI/ML components.
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Optional path to config file
        """
        # Set up config dict
        self.config = {
            "ai_ml": {
                "storage_path": str(Path.home() / ".ipfs_kit" / "ai_ml"),
                "enable_monitoring": True,
                "prometheus_port": 8000,
                "log_level": "INFO"
            },
            "model_registry": {
                "storage_path": None,  # Will be derived from ai_ml.storage_path
                "versioning": True,
                "metadata_validation": True,
                "performance_tracking": True
            },
            "dataset_manager": {
                "storage_path": None,  # Will be derived from ai_ml.storage_path
                "versioning": True,
                "metadata_validation": True,
                "schema_validation": True
            },
            "framework_integration": {
                "langchain": {
                    "enabled": False,
                    "cache_path": None  # Will be derived from ai_ml.storage_path
                },
                "llama_index": {
                    "enabled": False,
                    "cache_path": None  # Will be derived from ai_ml.storage_path
                },
                "huggingface": {
                    "enabled": False,
                    "cache_path": None,  # Will be derived from ai_ml.storage_path
                    "model_repository": "models"
                }
            },
            "distributed_training": {
                "enabled": False,
                "max_workers": 4,
                "checkpoint_interval": 300,  # seconds
                "max_job_runtime": 86400  # 24 hours
            }
        }
        
        # For thread safety
        self.lock = threading.RLock()
        
        # Load config from file if provided
        if config_path:
            self.load_config(config_path)
        else:
            self._load_env_config()
        
        # Set up derived paths
        self._setup_derived_paths()
        
        # Ensure storage paths exist
        self._ensure_storage_paths()
        
        logger.info("AI/ML configuration initialized")
    
    def _load_env_config(self) -> None:
        """Load configuration from environment variables."""
        # Base storage path
        storage_path = os.environ.get("IPFS_KIT_AI_ML_STORAGE")
        if storage_path:
            self.config["ai_ml"]["storage_path"] = storage_path
        
        # Monitoring
        monitoring_enabled = os.environ.get("IPFS_KIT_AI_ML_MONITORING")
        if monitoring_enabled:
            self.config["ai_ml"]["enable_monitoring"] = monitoring_enabled.lower() == "true"
        
        prometheus_port = os.environ.get("IPFS_KIT_AI_ML_PROMETHEUS_PORT")
        if prometheus_port:
            try:
                port = int(prometheus_port)
                self.config["ai_ml"]["prometheus_port"] = port
            except ValueError:
                logger.warning("Invalid prometheus port in environment, using default")
        
        # Log level
        log_level = os.environ.get("IPFS_KIT_AI_ML_LOG_LEVEL")
        if log_level:
            self.config["ai_ml"]["log_level"] = log_level
        
        # Framework integrations
        langchain_enabled = os.environ.get("IPFS_KIT_ENABLE_LANGCHAIN")
        if langchain_enabled:
            self.config["framework_integration"]["langchain"]["enabled"] = langchain_enabled.lower() == "true"
        
        llama_index_enabled = os.environ.get("IPFS_KIT_ENABLE_LLAMA_INDEX")
        if llama_index_enabled:
            self.config["framework_integration"]["llama_index"]["enabled"] = llama_index_enabled.lower() == "true"
        
        huggingface_enabled = os.environ.get("IPFS_KIT_ENABLE_HUGGINGFACE")
        if huggingface_enabled:
            self.config["framework_integration"]["huggingface"]["enabled"] = huggingface_enabled.lower() == "true"
        
        # Distributed training
        dist_training_enabled = os.environ.get("IPFS_KIT_ENABLE_DISTRIBUTED_TRAINING")
        if dist_training_enabled:
            self.config["distributed_training"]["enabled"] = dist_training_enabled.lower() == "true"
        
        max_workers = os.environ.get("IPFS_KIT_DISTRIBUTED_TRAINING_WORKERS")
        if max_workers:
            try:
                workers = int(max_workers)
                self.config["distributed_training"]["max_workers"] = workers
            except ValueError:
                logger.warning("Invalid max workers in environment, using default")
    
    def _setup_derived_paths(self) -> None:
        """Set up derived paths based on base storage path."""
        base_path = Path(self.config["ai_ml"]["storage_path"])
        
        # Model registry
        if not self.config["model_registry"]["storage_path"]:
            self.config["model_registry"]["storage_path"] = str(base_path / "models")
        
        # Dataset manager
        if not self.config["dataset_manager"]["storage_path"]:
            self.config["dataset_manager"]["storage_path"] = str(base_path / "datasets")
        
        # Framework integration
        if not self.config["framework_integration"]["langchain"]["cache_path"]:
            self.config["framework_integration"]["langchain"]["cache_path"] = str(base_path / "cache" / "langchain")
        
        if not self.config["framework_integration"]["llama_index"]["cache_path"]:
            self.config["framework_integration"]["llama_index"]["cache_path"] = str(base_path / "cache" / "llama_index")
        
        if not self.config["framework_integration"]["huggingface"]["cache_path"]:
            self.config["framework_integration"]["huggingface"]["cache_path"] = str(base_path / "cache" / "huggingface")
    
    def _ensure_storage_paths(self) -> None:
        """Ensure storage paths exist."""
        try:
            # Base path
            base_path = Path(self.config["ai_ml"]["storage_path"])
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Model registry
            Path(self.config["model_registry"]["storage_path"]).mkdir(parents=True, exist_ok=True)
            
            # Dataset manager
            Path(self.config["dataset_manager"]["storage_path"]).mkdir(parents=True, exist_ok=True)
            
            # Framework integration
            Path(self.config["framework_integration"]["langchain"]["cache_path"]).mkdir(parents=True, exist_ok=True)
            Path(self.config["framework_integration"]["llama_index"]["cache_path"]).mkdir(parents=True, exist_ok=True)
            Path(self.config["framework_integration"]["huggingface"]["cache_path"]).mkdir(parents=True, exist_ok=True)
        
        except Exception as e:
            logger.warning(f"Error creating storage directories: {e}")
    
    def load_config(self, config_path: Union[str, Path]) -> bool:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to config file
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            try:
                # Load from JSON file
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Update config
                self._update_config_recursive(self.config, config)
                
                # Re-setup derived paths
                self._setup_derived_paths()
                
                # Ensure storage paths exist
                self._ensure_storage_paths()
                
                logger.info(f"Loaded configuration from {config_path}")
                return True
                
            except Exception as e:
                logger.error(f"Error loading configuration from {config_path}: {e}")
                return False
    
    def save_config(self, config_path: Union[str, Path]) -> bool:
        """
        Save configuration to a file.
        
        Args:
            config_path: Path to config file
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            try:
                # Save to JSON file
                with open(config_path, 'w') as f:
                    json.dump(self.config, f, indent=2)
                
                logger.info(f"Saved configuration to {config_path}")
                return True
                
            except Exception as e:
                logger.error(f"Error saving configuration to {config_path}: {e}")
                return False
    
    def update_from_dict(self, config_updates: Dict[str, Any]) -> None:
        """
        Update configuration from a dictionary.
        
        Args:
            config_updates: Dictionary of config updates
        """
        with self.lock:
            # Update config
            self._update_config_recursive(self.config, config_updates)
            
            # Re-setup derived paths
            self._setup_derived_paths()
            
            # Ensure storage paths exist
            self._ensure_storage_paths()
    
    def _update_config_recursive(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Recursively update target dictionary with source values."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # Recursively update nested dictionaries
                self._update_config_recursive(target[key], value)
            else:
                # Update value
                target[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Dot-separated configuration key
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        with self.lock:
            # Split key by dot separator
            parts = key.split(".")
            
            # Traverse config dict
            value = self.config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            
            return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Dot-separated configuration key
            value: Value to set
        """
        with self.lock:
            # Split key by dot separator
            parts = key.split(".")
            
            # Traverse config dict
            config = self.config
            for i, part in enumerate(parts[:-1]):
                if part not in config:
                    config[part] = {}
                elif not isinstance(config[part], dict):
                    # Convert to dict if not already
                    config[part] = {}
                
                config = config[part]
            
            # Set value
            config[parts[-1]] = value
            
            # Re-setup derived paths if needed
            if key.startswith("ai_ml.storage_path"):
                self._setup_derived_paths()
                self._ensure_storage_paths()
    
    def get_storage_path(self, component: str) -> Path:
        """
        Get storage path for a component.
        
        Args:
            component: Component name
            
        Returns:
            Storage path
        """
        with self.lock:
            # Check if component has a specific storage path
            if component in self.config and "storage_path" in self.config[component]:
                path = self.config[component]["storage_path"]
                if path:
                    return Path(path)
            
            # Use base path with component subdirectory
            base_path = Path(self.config["ai_ml"]["storage_path"])
            return base_path / component
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration settings.
        
        Returns:
            Copy of the configuration dictionary
        """
        with self.lock:
            return {**self.config}
    
    def get_framework_config(self, framework: str) -> Dict[str, Any]:
        """
        Get configuration for a specific framework.
        
        Args:
            framework: Framework name
            
        Returns:
            Framework configuration
        """
        with self.lock:
            if framework in self.config["framework_integration"]:
                return {**self.config["framework_integration"][framework]}
            else:
                return {}


# Singleton instance
_instance = None

def get_instance(config_path: Optional[Union[str, Path]] = None) -> AIMLConfig:
    """
    Get or create the singleton configuration instance.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        AIMLConfig instance
    """
    global _instance
    if _instance is None:
        _instance = AIMLConfig(config_path)
    elif config_path:
        # If config path is provided, load it
        _instance.load_config(config_path)
    return _instance

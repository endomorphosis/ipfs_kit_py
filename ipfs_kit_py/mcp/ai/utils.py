#!/usr/bin/env python3
"""
Utility functions for AI/ML components in MCP

This module provides utility functions for initializing and
integrating all AI/ML components using the centralized
configuration system.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path

from .config import get_instance as get_config_instance

# Configure logging
logger = logging.getLogger("mcp_ai_utils")

def initialize_all_components(
    config_path: Optional[Union[str, Path]] = None,
    mcp_server = None
) -> Dict[str, Any]:
    """
    Initialize all AI/ML components using the shared configuration.
    
    Args:
        config_path: Path to configuration file or directory (optional)
        mcp_server: MCP server instance to register components with (optional)
        
    Returns:
        Dictionary of initialized components
    """
    try:
        # Get configuration
        config = get_config_instance(config_path)
        
        # Initialize components
        components = {}
        
        # 1. Model Registry
        components["model_registry"] = initialize_model_registry(config)
        
        # 2. Dataset Manager
        components["dataset_manager"] = initialize_dataset_manager(config)
        
        # 3. Distributed Training
        components["distributed_training"] = initialize_distributed_training(config)
        
        # 4. Framework Integration
        components["framework_integration"] = initialize_framework_integration(config)
        
        # 5. AI/ML Integrator (master component that manages the others)
        components["ai_ml_integrator"] = initialize_ai_ml_integrator(
            config=config,
            model_registry=components.get("model_registry"),
            dataset_manager=components.get("dataset_manager"),
            distributed_training=components.get("distributed_training"),
            framework_integration=components.get("framework_integration"),
            mcp_server=mcp_server
        )
        
        logger.info("All AI/ML components initialized successfully")
        return components
    
    except Exception as e:
        logger.error(f"Error initializing AI/ML components: {e}")
        raise

def initialize_model_registry(config) -> Any:
    """
    Initialize the Model Registry component with configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        Initialized Model Registry instance
    """
    try:
        # Import here to avoid circular imports
        from .model_registry import get_instance
        
        # Get storage path and config from central config
        storage_path = config.get_storage_path("model_registry")
        registry_config = config.get("model_registry")
        
        # Initialize and return
        registry = get_instance(
            storage_path=storage_path,
            config=registry_config
        )
        
        logger.info(f"Model Registry initialized at {storage_path}")
        return registry
        
    except ImportError:
        logger.warning("Model Registry module not available")
        return None
    except Exception as e:
        logger.error(f"Error initializing Model Registry: {e}")
        return None

def initialize_dataset_manager(config) -> Any:
    """
    Initialize the Dataset Manager component with configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        Initialized Dataset Manager instance
    """
    try:
        # Import here to avoid circular imports
        from .dataset_manager import get_instance
        
        # Get storage path and config from central config
        storage_path = config.get_storage_path("dataset_manager")
        dataset_config = config.get("dataset_manager")
        
        # Initialize and return
        manager = get_instance(
            storage_path=storage_path,
            config=dataset_config
        )
        
        logger.info(f"Dataset Manager initialized at {storage_path}")
        return manager
        
    except ImportError:
        logger.warning("Dataset Manager module not available")
        return None
    except Exception as e:
        logger.error(f"Error initializing Dataset Manager: {e}")
        return None

def initialize_distributed_training(config) -> Any:
    """
    Initialize the Distributed Training component with configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        Initialized Distributed Training instance
    """
    try:
        # Import here to avoid circular imports
        from .distributed_training import get_instance
        
        # Get storage path and config from central config
        storage_path = config.get_storage_path("distributed_training")
        training_config = config.get("distributed_training")
        
        # Initialize and return
        training = get_instance(
            storage_path=storage_path,
            config=training_config
        )
        
        logger.info(f"Distributed Training initialized at {storage_path}")
        return training
        
    except ImportError:
        logger.warning("Distributed Training module not available")
        return None
    except Exception as e:
        logger.error(f"Error initializing Distributed Training: {e}")
        return None

def initialize_framework_integration(config) -> Any:
    """
    Initialize the Framework Integration component with configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        Initialized Framework Integration instance
    """
    try:
        # Import here to avoid circular imports
        from .framework_integration import get_instance
        
        # Get storage path and config from central config
        storage_path = config.get_storage_path("framework_integration")
        framework_config = config.get("framework_integration")
        
        # Initialize and return
        framework = get_instance(
            storage_path=storage_path,
            config=framework_config
        )
        
        logger.info(f"Framework Integration initialized at {storage_path}")
        return framework
        
    except ImportError:
        logger.warning("Framework Integration module not available")
        return None
    except Exception as e:
        logger.error(f"Error initializing Framework Integration: {e}")
        return None

def initialize_ai_ml_integrator(
    config,
    model_registry=None,
    dataset_manager=None,
    distributed_training=None,
    framework_integration=None,
    mcp_server=None
) -> Any:
    """
    Initialize the AI/ML Integrator component with configuration.
    
    Args:
        config: Configuration instance
        model_registry: Model Registry instance
        dataset_manager: Dataset Manager instance
        distributed_training: Distributed Training instance
        framework_integration: Framework Integration instance
        mcp_server: MCP server instance
        
    Returns:
        Initialized AI/ML Integrator instance
    """
    try:
        # Import here to avoid circular imports
        from .ai_ml_integrator import get_instance
        
        # Get feature flags from config
        feature_flags = {
            "model_registry": model_registry is not None,
            "dataset_manager": dataset_manager is not None,
            "distributed_training": distributed_training is not None,
            "framework_integration": framework_integration is not None
        }
        
        # Get storage path
        storage_path = config.get_storage_path("ai_ml")
        
        # Initialize integrator
        integrator = get_instance(
            mcp_server=mcp_server,
            config=config.get_all(),
            storage_path=storage_path,
            feature_flags=feature_flags
        )
        
        # Register components with the integrator
        if model_registry:
            integrator.model_registry = model_registry
        
        if dataset_manager:
            integrator.dataset_manager = dataset_manager
        
        if distributed_training:
            integrator.distributed_training = distributed_training
        
        if framework_integration:
            integrator.framework_integration = framework_integration
        
        # Initialize the integrator
        if integrator.initialize():
            # Register with MCP server if provided
            if mcp_server:
                prefix = config.get("endpoints", "base_url", "/ai")
                if integrator.register_with_server(mcp_server, prefix=prefix):
                    logger.info(f"AI/ML Integrator registered with MCP server with prefix {prefix}")
                else:
                    logger.warning("Failed to register AI/ML Integrator with MCP server")
            
            logger.info("AI/ML Integrator initialized")
            return integrator
        else:
            logger.error("Failed to initialize AI/ML Integrator")
            return None
        
    except ImportError as e:
        logger.warning(f"AI/ML Integrator module not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Error initializing AI/ML Integrator: {e}")
        return None

def setup_logging(config=None) -> None:
    """
    Set up logging for AI/ML components based on configuration.
    
    Args:
        config: Configuration instance (if None, will be retrieved)
    """
    # Get config if not provided
    if config is None:
        config = get_config_instance()
    
    # Get logging configuration
    log_level_str = config.get("monitoring", "log_level", "info")
    log_to_file = config.get("monitoring", "log_to_file", False)
    log_file_path = config.get("monitoring", "log_file_path", None)
    
    # Convert string level to logging level
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger("mcp_ai")
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if configured
    if log_to_file and log_file_path:
        log_file_path = Path(log_file_path)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

def check_dependencies() -> Dict[str, bool]:
    """
    Check for the presence of optional dependencies.
    
    Returns:
        Dictionary mapping dependency names to availability status
    """
    dependencies = {}
    
    # AI frameworks
    try:
        import langchain
        dependencies["langchain"] = True
    except ImportError:
        dependencies["langchain"] = False
    
    try:
        import llama_index
        dependencies["llama_index"] = True
    except ImportError:
        dependencies["llama_index"] = False
    
    try:
        import transformers
        dependencies["transformers"] = True
    except ImportError:
        dependencies["transformers"] = False
    
    try:
        import huggingface_hub
        dependencies["huggingface_hub"] = True
    except ImportError:
        dependencies["huggingface_hub"] = False
    
    try:
        import torch
        dependencies["torch"] = True
    except ImportError:
        dependencies["torch"] = False
    
    # Storage backends potentially needed by AI components
    try:
        import boto3
        dependencies["boto3"] = True
    except ImportError:
        dependencies["boto3"] = False
    
    try:
        import ipfshttpclient
        dependencies["ipfshttpclient"] = True
    except ImportError:
        dependencies["ipfshttpclient"] = False
    
    # Report unavailable dependencies
    missing = [dep for dep, available in dependencies.items() if not available]
    if missing:
        logger.warning(f"Missing optional dependencies: {', '.join(missing)}")
    
    return dependencies

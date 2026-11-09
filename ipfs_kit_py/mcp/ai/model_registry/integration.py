"""
Model Registry Integration Module

This module provides functions to integrate the Model Registry with the MCP server.
It handles initialization, server configuration, and connecting the registry
to the storage backends.

Usage:
    In the MCP server startup code:
    ```python
    from ipfs_kit_py.mcp.ai.model_registry.integration import setup_model_registry
    
    # During server initialization
    await setup_model_registry(app, backend_manager)
    ```

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("model_registry_integration")

# Import the Model Registry components
from ipfs_kit_py.mcp.ai.model_registry import (
    ModelRegistry,
    model_registry_router,
    initialize_model_registry
)

async def setup_model_registry(
    app: FastAPI,
    backend_manager: Any,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Set up the Model Registry and integrate it with the MCP server.
    
    Args:
        app: FastAPI application
        backend_manager: Backend manager for storage operations
        config: Optional configuration dictionary
        
    Returns:
        Result dictionary with status
    """
    try:
        logger.info("Setting up Model Registry...")
        
        # Default configuration
        default_config = {
            "data_dir": os.path.join(os.path.expanduser("~"), ".ipfs_kit", "model_registry"),
            "enable_model_registry": os.environ.get("ENABLE_MODEL_REGISTRY", "1") == "1"
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        # Check if Model Registry is enabled
        if not default_config["enable_model_registry"]:
            logger.info("Model Registry is disabled by configuration")
            return {
                "success": False,
                "message": "Model Registry is disabled by configuration"
            }
        
        # Create registry directory if it doesn't exist
        os.makedirs(default_config["data_dir"], exist_ok=True)
        
        # Initialize the Model Registry
        registry = initialize_model_registry(backend_manager)
        
        # Include the Model Registry router
        app.include_router(model_registry_router)
        
        logger.info("Model Registry set up successfully")
        return {
            "success": True,
            "registry": registry,
            "message": "Model Registry initialized successfully"
        }
    
    except Exception as e:
        logger.error(f"Error setting up Model Registry: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to initialize Model Registry"
        }

def get_model_registry_status() -> Dict[str, Any]:
    """
    Get the status of the Model Registry.
    
    Returns:
        Status dictionary
    """
    from ipfs_kit_py.mcp.ai.model_registry.router import _model_registry
    
    if _model_registry is None:
        return {
            "initialized": False,
            "message": "Model Registry not initialized"
        }
    
    try:
        # Count models and versions
        models_count = len(_model_registry.store.list_models())
        versions_count = sum(len(model.versions) for model in _model_registry.store.list_models())
        
        return {
            "initialized": True,
            "models_count": models_count,
            "versions_count": versions_count,
            "store_path": _model_registry.store.store_path
        }
    except Exception as e:
        return {
            "initialized": True,
            "error": str(e),
            "message": "Error getting Model Registry status"
        }

async def verify_model_registry(backend_manager: Any) -> Dict[str, Any]:
    """
    Verify that the Model Registry is working correctly.
    
    Args:
        backend_manager: Backend manager for storage operations
        
    Returns:
        Verification results
    """
    from ipfs_kit_py.mcp.ai.model_registry.router import _model_registry
    
    if _model_registry is None:
        return {
            "success": False,
            "message": "Model Registry not initialized"
        }
    
    try:
        results = {
            "success": True,
            "components": {},
            "tests": {}
        }
        
        # Verify registry components
        results["components"]["store"] = os.path.exists(_model_registry.store.store_path)
        results["components"]["models_dir"] = os.path.exists(_model_registry.store.models_dir)
        results["components"]["versions_dir"] = os.path.exists(_model_registry.store.versions_dir)
        results["components"]["backend_manager"] = backend_manager is not None
        
        # Test model creation
        try:
            test_model = await _model_registry.create_model(
                name="Test Model",
                owner="test_user",
                description="Test model for verification",
                tags=["test", "verification"]
            )
            
            results["tests"]["create_model"] = test_model is not None
            
            # If model was created, verify retrieval
            if test_model:
                retrieved_model = await _model_registry.get_model(test_model.id)
                results["tests"]["get_model"] = retrieved_model is not None
                
                # Clean up the test model
                await _model_registry.delete_model(test_model.id)
                results["tests"]["delete_model"] = True
            else:
                results["tests"]["get_model"] = False
                results["tests"]["delete_model"] = False
        
        except Exception as e:
            results["tests"]["create_model"] = False
            results["tests"]["error"] = str(e)
            results["success"] = False
        
        # Set overall success
        if not all(results["components"].values()) or not all(results["tests"].values()):
            results["success"] = False
        
        return results
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error verifying Model Registry"
        }
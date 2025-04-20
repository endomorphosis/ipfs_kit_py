"""
Dataset Management Integration Module

This module provides functions to integrate the Dataset Management system with the MCP server.
It handles initialization, server configuration, and connecting the dataset manager
to the storage backends.

Usage:
    In the MCP server startup code:
    ```python
    from ipfs_kit_py.mcp.ai.dataset_management.integration import setup_dataset_management
    
    # During server initialization
    await setup_dataset_management(app, backend_manager)
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
logger = logging.getLogger("dataset_management_integration")

# Import the Dataset Management components
from ipfs_kit_py.mcp.ai.dataset_management import (
    DatasetManager,
    dataset_management_router,
    initialize_dataset_manager
)

async def setup_dataset_management(
    app: FastAPI,
    backend_manager: Any,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Set up the Dataset Management system and integrate it with the MCP server.
    
    Args:
        app: FastAPI application
        backend_manager: Backend manager for storage operations
        config: Optional configuration dictionary
        
    Returns:
        Result dictionary with status
    """
    try:
        logger.info("Setting up Dataset Management system...")
        
        # Default configuration
        default_config = {
            "data_dir": os.path.join(os.path.expanduser("~"), ".ipfs_kit", "dataset_management"),
            "enable_dataset_management": os.environ.get("ENABLE_DATASET_MANAGEMENT", "1") == "1"
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        # Check if Dataset Management is enabled
        if not default_config["enable_dataset_management"]:
            logger.info("Dataset Management is disabled by configuration")
            return {
                "success": False,
                "message": "Dataset Management is disabled by configuration"
            }
        
        # Create dataset directory if it doesn't exist
        os.makedirs(default_config["data_dir"], exist_ok=True)
        
        # Initialize the Dataset Manager
        manager = initialize_dataset_manager(backend_manager)
        
        # Include the Dataset Management router
        app.include_router(dataset_management_router)
        
        logger.info("Dataset Management system set up successfully")
        return {
            "success": True,
            "manager": manager,
            "message": "Dataset Management initialized successfully"
        }
    
    except Exception as e:
        logger.error(f"Error setting up Dataset Management: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to initialize Dataset Management"
        }

def get_dataset_management_status() -> Dict[str, Any]:
    """
    Get the status of the Dataset Management system.
    
    Returns:
        Status dictionary
    """
    from ipfs_kit_py.mcp.ai.dataset_management.router import _dataset_manager
    
    if _dataset_manager is None:
        return {
            "initialized": False,
            "message": "Dataset Management not initialized"
        }
    
    try:
        # Count datasets and versions
        datasets_count = len(_dataset_manager.store.list_datasets())
        versions_count = sum(len(dataset.versions) for dataset in _dataset_manager.store.list_datasets())
        
        return {
            "initialized": True,
            "datasets_count": datasets_count,
            "versions_count": versions_count,
            "store_path": _dataset_manager.store.store_path
        }
    except Exception as e:
        return {
            "initialized": True,
            "error": str(e),
            "message": "Error getting Dataset Management status"
        }

async def verify_dataset_management(backend_manager: Any) -> Dict[str, Any]:
    """
    Verify that the Dataset Management system is working correctly.
    
    Args:
        backend_manager: Backend manager for storage operations
        
    Returns:
        Verification results
    """
    from ipfs_kit_py.mcp.ai.dataset_management.router import _dataset_manager
    
    if _dataset_manager is None:
        return {
            "success": False,
            "message": "Dataset Management not initialized"
        }
    
    try:
        results = {
            "success": True,
            "components": {},
            "tests": {}
        }
        
        # Verify manager components
        results["components"]["store"] = os.path.exists(_dataset_manager.store.store_path)
        results["components"]["datasets_dir"] = os.path.exists(_dataset_manager.store.datasets_dir)
        results["components"]["versions_dir"] = os.path.exists(_dataset_manager.store.versions_dir)
        results["components"]["backend_manager"] = backend_manager is not None
        
        # Test dataset creation
        try:
            test_dataset = await _dataset_manager.create_dataset(
                name="Test Dataset",
                owner="test_user",
                description="Test dataset for verification",
                tags=["test", "verification"]
            )
            
            results["tests"]["create_dataset"] = test_dataset is not None
            
            # If dataset was created, verify retrieval
            if test_dataset:
                retrieved_dataset = await _dataset_manager.get_dataset(test_dataset.id)
                results["tests"]["get_dataset"] = retrieved_dataset is not None
                
                # Clean up the test dataset
                await _dataset_manager.delete_dataset(test_dataset.id)
                results["tests"]["delete_dataset"] = True
            else:
                results["tests"]["get_dataset"] = False
                results["tests"]["delete_dataset"] = False
        
        except Exception as e:
            results["tests"]["create_dataset"] = False
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
            "message": "Error verifying Dataset Management"
        }
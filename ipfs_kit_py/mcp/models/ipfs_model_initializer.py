"""
IPFS Model Initializer for MCP server.

This module initializes the IPFSModel with extensions to support MCP server tools.
"""

import logging
import importlib
from typing import Type

# Configure logger
logger = logging.getLogger(__name__)

def initialize_ipfs_model():
    """
    Initialize the IPFSModel class with extensions.
    
    This function imports the necessary modules and applies extensions to the IPFSModel class.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Import IPFSModel class
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        
        # Import extensions
        from ipfs_kit_py.mcp.models.ipfs_model_extensions import add_ipfs_model_extensions
        
        # Apply extensions to the IPFSModel class
        add_ipfs_model_extensions(IPFSModel)
        
        # Add methods as instance methods
        IPFSModel.add_content = add_ipfs_model_extensions.__globals__['add_content']
        IPFSModel.cat = add_ipfs_model_extensions.__globals__['cat']
        IPFSModel.pin_add = add_ipfs_model_extensions.__globals__['pin_add']
        IPFSModel.pin_rm = add_ipfs_model_extensions.__globals__['pin_rm']
        IPFSModel.pin_ls = add_ipfs_model_extensions.__globals__['pin_ls']
        IPFSModel.swarm_peers = add_ipfs_model_extensions.__globals__['swarm_peers']
        IPFSModel.swarm_connect = add_ipfs_model_extensions.__globals__['swarm_connect']
        IPFSModel.swarm_disconnect = add_ipfs_model_extensions.__globals__['swarm_disconnect']
        IPFSModel.storage_transfer = add_ipfs_model_extensions.__globals__['storage_transfer']
        IPFSModel.get_version = add_ipfs_model_extensions.__globals__['get_version']
        
        logger.info("Successfully initialized IPFSModel with extensions")
        return True
    
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False
    except Exception as e:
        logger.error(f"Error initializing IPFSModel: {e}")
        return False

"""
IPFS Model Initializer for MCP server.

This module initializes the IPFSModel with extensions to support MCP server tools.
"""

import logging
import importlib
import sys
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
        
        # Apply extensions to the IPFSModel class directly
        add_ipfs_model_extensions(IPFSModel)
        
        # Extract method functions from the module
        extension_module = sys.modules.get('ipfs_kit_py.mcp.models.ipfs_model_extensions')
        
        if extension_module:
            # Use direct module access for methods
            for method_name in ['add_content', 'cat', 'pin_add', 'pin_rm', 'pin_ls',
                               'swarm_peers', 'swarm_connect', 'swarm_disconnect',
                               'storage_transfer', 'get_version']:
                method = getattr(extension_module, method_name, None)
                if method:
                    setattr(IPFSModel, method_name, method)
                else:
                    logger.warning(f"Method {method_name} not found in extensions module")
        else:
            # Fallback to the globals dictionary of the function
            methods_dict = add_ipfs_model_extensions.__globals__
            
            # Directly attach methods to the class
            for method_name in ['add_content', 'cat', 'pin_add', 'pin_rm', 'pin_ls',
                               'swarm_peers', 'swarm_connect', 'swarm_disconnect',
                               'storage_transfer', 'get_version']:
                if method_name in methods_dict:
                    setattr(IPFSModel, method_name, methods_dict[method_name])
                else:
                    logger.warning(f"Method {method_name} not found in function globals")
        
        logger.info("Successfully initialized IPFSModel with extensions")
        return True
    
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False
    except Exception as e:
        logger.error(f"Error initializing IPFSModel: {e}")
        return False

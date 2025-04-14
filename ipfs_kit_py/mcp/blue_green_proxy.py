"""
Auto-generated bridge module from mcp_server.blue_green_proxy to mcp.blue_green_proxy.
This file was created by the import_fixer.py script.
"""

import sys
import logging
import importlib

# Configure logging
logger = logging.getLogger(__name__)

# Import from the real module location
try:
    # Import the real module
    _real_module = importlib.import_module("ipfs_kit_py.mcp_server.blue_green_proxy")
    
    # Get the exported symbols
    if hasattr(_real_module, "__all__"):
        __all__ = _real_module.__all__
    else:
        __all__ = [name for name in dir(_real_module) if not name.startswith("_")]
    
    # Import everything into this namespace
    for name in __all__:
        try:
            globals()[name] = getattr(_real_module, name)
            logger.debug(f"Imported {name} from ipfs_kit_py.mcp_server.blue_green_proxy")
        except AttributeError:
            logger.warning(f"Failed to import {name} from ipfs_kit_py.mcp_server.blue_green_proxy")
    
    logger.debug(f"Successfully imported from ipfs_kit_py.mcp_server.blue_green_proxy")
except ImportError as e:
    logger.error(f"Failed to import from ipfs_kit_py.mcp_server.blue_green_proxy: {e}")
    # No fallbacks provided here, will just raise the ImportError
    raise

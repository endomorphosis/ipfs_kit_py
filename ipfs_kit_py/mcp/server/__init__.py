"""
Bridge module for server package.
This file was created by the import_fixer.py script.
"""

import importlib
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import from real module
try:
    _real_module = importlib.import_module("ipfs_kit_py.mcp.server") # Updated path

    # Import all public members
    if hasattr(_real_module, "__all__"):
        __all__ = _real_module.__all__

        # Import all listed names
        for name in __all__:
            try:
                globals()[name] = getattr(_real_module, name)
            except AttributeError:
                logger.warning(f"Could not import {name} from ipfs_kit_py.mcp.server") # Updated path
    else:
        # Import all non-private names
        __all__ = []
        for name in dir(_real_module):
            if not name.startswith("_"):
                try:
                    globals()[name] = getattr(_real_module, name)
                    __all__.append(name)
                except AttributeError:
                    pass

    logger.debug("Successfully imported from ipfs_kit_py.mcp.server") # Updated path
except ImportError as e:
    logger.warning(f"Failed to import from ipfs_kit_py.mcp.server: {e}") # Updated path
    __all__ = []

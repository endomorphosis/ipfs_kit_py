"""MCP Server Utils Redirection Module

This module redirects imports from the old path (ipfs_kit_py.mcp_server.utils.*)
to the new path (ipfs_kit_py.mcp.utils.*).
"""

import logging
import sys
from importlib import import_module

logger = logging.getLogger(__name__)

# Map of old module paths to new module paths
MODULE_MAP = {
    "method_normalizer": "ipfs_kit_py.mcp.utils.method_normalizer"
}

class ModuleProxy:
    """Proxy for redirecting module attributes to actual implementations."""
    
    def __init__(self, actual_module):
        self.actual_module = actual_module
    
    def __getattr__(self, name):
        return getattr(self.actual_module, name)

# Create proxy for each mapped module
for old_name, new_path in MODULE_MAP.items():
    try:
        actual_module = import_module(new_path)
        sys.modules[f"ipfs_kit_py.mcp_server.utils.{old_name}"] = ModuleProxy(actual_module)
        logger.info(f"Redirected ipfs_kit_py.mcp_server.utils.{old_name} to {new_path}")
    except ImportError as e:
        logger.error(f"Error redirecting ipfs_kit_py.mcp_server.utils.{old_name}: {e}")

# Expose the same names as the original module
from ipfs_kit_py.mcp.utils.method_normalizer import *
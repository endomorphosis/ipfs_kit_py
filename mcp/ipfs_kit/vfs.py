"""
VFS (Virtual File System) for IPFS Kit (MCP Wrapper).

This module acts as a thin wrapper around the centralized IPFSSimpleAPI
from the ipfs_kit_py library, ensuring the MCP layer uses the core VFS functionalities.
"""

import logging
import asyncio
from typing import Dict, Any

try:
    # Primary import path for when the package is installed
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
except ImportError:
    # Fallback for development environments
    import sys
    import os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI

logger = logging.getLogger(__name__)

class VFSManager:
    """
    MCP Wrapper for the core IPFSSimpleAPI VFS features.
    Delegates all VFS tasks to the centralized library component.
    """

    def __init__(self):
        """Initializes the wrapper and the underlying IPFSSimpleAPI."""
        logger.info("=== MCP VFSManager Wrapper initializing ===")
        try:
            self.api = IPFSSimpleAPI()
            logger.info("✓ Centralized IPFSSimpleAPI initialized for VFS operations.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize IPFSSimpleAPI: {e}", exc_info=True)
            self.api = None
        logger.info("=== MCP VFSManager Wrapper initialization complete ===")

    async def execute_vfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Executes a VFS operation by delegating to the IPFSSimpleAPI instance.
        """
        if not self.api:
            return {"success": False, "error": "IPFSSimpleAPI not initialized."}

        # The operation name from MCP should directly map to a method
        # in IPFSSimpleAPI (e.g., 'vfs_ls', 'cache_stats').
        op_name = operation
        if not hasattr(self.api, op_name):
            # Add a 'vfs_' prefix for common filesystem commands if not present
            if operation in ['ls', 'cat', 'write', 'mkdir', 'rm', 'info']:
                op_name = f"vfs_{operation}"
            else:
                logger.error(f"VFS operation '{operation}' not found in IPFSSimpleAPI.")
                return {"success": False, "error": f"Unknown VFS operation: {operation}"}

        if not hasattr(self.api, op_name):
            logger.error(f"VFS operation '{op_name}' not found in IPFSSimpleAPI even after prefixing.")
            return {"success": False, "error": f"Unknown VFS operation: {op_name}"}

        try:
            method = getattr(self.api, op_name)
            
            if asyncio.iscoroutinefunction(method):
                return await method(**kwargs)
            else:
                # Handle non-async methods if any exist
                return method(**kwargs)

        except Exception as e:
            logger.error(f"❌ VFS operation '{operation}' failed in wrapper: {e}", exc_info=True)
            return {"success": False, "error": str(e), "operation": operation}

    def cleanup(self):
        """Cleans up resources if the underlying API has a cleanup method."""
        if self.api:
            logger.info("Cleaning up MCP VFSManager wrapper...")
            if hasattr(self.api, 'cleanup'):
                self.api.cleanup()
            logger.info("✓ MCP VFSManager wrapper cleaned up.")

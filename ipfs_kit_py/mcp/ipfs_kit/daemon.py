"""
Daemon Management for IPFS Kit (MCP Wrapper).

This module acts as a thin wrapper around the centralized EnhancedDaemonManager
from the ipfs_kit_py library, ensuring the MCP layer uses the core functionalities.
"""

import logging
from typing import Dict, Any

try:
    # Primary import path for when the package is installed
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.ipfs_kit import IPFSKit
except ImportError:
    # Fallback for development environments where the package is not installed
    import sys
    import os
    # Navigate up from mcp/ipfs_kit/ to the project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.ipfs_kit import IPFSKit


logger = logging.getLogger(__name__)

class DaemonManager:
    """
    MCP Wrapper for the core EnhancedDaemonManager.
    Delegates all daemon management tasks to the centralized library component.
    """

    def __init__(self):
        """Initializes the wrapper and the underlying EnhancedDaemonManager."""
        logger.info("=== MCP DaemonManager Wrapper initializing ===")
        try:
            # The daemon manager is part of the IPFSKit instance
            self.kit = IPFSKit()
            self.manager = self.kit.daemon_manager
            # Ensure the daemon is running using the comprehensive check
            self.manager.ensure_daemon_running_comprehensive()
            logger.info("✓ Centralized EnhancedDaemonManager initialized and daemon status checked.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize EnhancedDaemonManager: {e}", exc_info=True)
            self.manager = None
            self.kit = None
        logger.info("=== MCP DaemonManager Wrapper initialization complete ===")

    async def execute_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Executes an IPFS operation by delegating to the IPFSKit instance.
        """
        if not self.kit:
            return {"success": False, "error": "IPFSKit not initialized."}

        try:
            # IPFSKit is callable and can execute operations
            return await self.kit(operation, **kwargs)
        except Exception as e:
            logger.error(f"❌ IPFS operation '{operation}' failed in wrapper: {e}", exc_info=True)
            return {"success": False, "error": str(e), "operation": operation}

    def get_status(self) -> Dict[str, Any]:
        """
        Gets the daemon status summary from the centralized manager.
        """
        if not self.manager:
            return {"status": "error", "error": "DaemonManager not initialized"}
        return self.manager.get_daemon_status_summary()

    def cleanup(self):
        """
        Cleans up resources by calling the centralized manager's stop method.
        """
        if self.manager:
            logger.info("Cleaning up MCP DaemonManager wrapper...")
            self.manager.stop_all_daemons()
            logger.info("✓ MCP DaemonManager wrapper cleaned up.")


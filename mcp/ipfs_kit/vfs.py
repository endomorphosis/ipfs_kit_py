"""
VFS (Virtual File System) for IPFS Kit (MCP Wrapper).

This module acts as a thin wrapper around the centralized VFSManager
from the ipfs_kit_py library, ensuring the MCP layer uses the core VFS functionalities.
"""

import logging
from typing import Dict, Any

try:
    # Primary import path for when the package is installed
    from ipfs_kit_py.vfs_manager import get_global_vfs_manager
except ImportError:
    # Fallback for development environments
    import sys
    import os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ipfs_kit_py.vfs_manager import get_global_vfs_manager

logger = logging.getLogger(__name__)

class VFSManager:
    """
    MCP Wrapper for the centralized VFSManager.
    Delegates all VFS tasks to the centralized library component.
    """

    def __init__(self):
        """Initializes the wrapper and the underlying VFSManager."""
        logger.info("=== MCP VFSManager Wrapper initializing ===")
        try:
            self.vfs_manager = get_global_vfs_manager()
            logger.info("✓ Centralized VFSManager initialized for MCP operations.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize VFSManager: {e}", exc_info=True)
            self.vfs_manager = None
        logger.info("=== MCP VFSManager Wrapper initialization complete ===")

    async def execute_vfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Executes a VFS operation by delegating to the centralized VFSManager.
        """
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}

        try:
            return await self.vfs_manager.execute_vfs_operation(operation, **kwargs)
        except Exception as e:
            logger.error(f"❌ VFS operation '{operation}' failed in MCP wrapper: {e}", exc_info=True)
            return {"success": False, "error": str(e), "operation": operation}

    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """Get VFS statistics from the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.get_vfs_statistics()
        except Exception as e:
            logger.error(f"❌ Failed to get VFS statistics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_vfs_journal(self, backend_filter=None, search_query=None, limit=100):
        """Get VFS journal entries from the centralized VFSManager."""
        if not self.vfs_manager:
            return []
        
        try:
            return await self.vfs_manager.get_vfs_journal(
                backend_filter=backend_filter,
                search_query=search_query,
                limit=limit
            )
        except Exception as e:
            logger.error(f"❌ Failed to get VFS journal: {e}", exc_info=True)
            return []

    async def list_files(self, path="/"):
        """List files using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.list_files(path)
        except Exception as e:
            logger.error(f"❌ Failed to list files: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def create_folder(self, path, name):
        """Create folder using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.create_folder(path, name)
        except Exception as e:
            logger.error(f"❌ Failed to create folder: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def delete_item(self, path):
        """Delete item using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.delete_item(path)
        except Exception as e:
            logger.error(f"❌ Failed to delete item: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def rename_item(self, old_path, new_name):
        """Rename item using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.rename_item(old_path, new_name)
        except Exception as e:
            logger.error(f"❌ Failed to rename item: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def move_item(self, source_path, target_path):
        """Move item using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.move_item(source_path, target_path)
        except Exception as e:
            logger.error(f"❌ Failed to move item: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def cleanup(self):
        """Cleans up resources if the underlying VFSManager has a cleanup method."""
        if self.vfs_manager:
            logger.info("Cleaning up MCP VFSManager wrapper...")
            # The actual cleanup is handled by the centralized VFSManager
            # We just need to release our reference
            self.vfs_manager = None
            logger.info("✓ MCP VFSManager wrapper cleaned up.")

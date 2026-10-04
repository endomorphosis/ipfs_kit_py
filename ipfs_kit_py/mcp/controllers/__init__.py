"""
Controllers package for the MCP server.
"""

import importlib.util
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Check if optional controllers are available
HAS_FS_JOURNAL = (
    importlib.util.find_spec("ipfs_kit_py.mcp.controllers.fs_journal_controller") is not None
)
# Import commented out to avoid issues
# if HAS_FS_JOURNAL:
#     from ipfs_kit_py.mcp.controllers.fs_journal_controller import FsJournalController

HAS_LIBP2P = importlib.util.find_spec("ipfs_kit_py.mcp.controllers.libp2p_controller") is not None
# Import commented out to avoid issues
# if HAS_LIBP2P:
#     from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController

# Add other optional controllers similarly...

# Import all controller modules for convenient access
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.controllers.ipfs_controller_anyio import IPFSControllerAnyIO
from ipfs_kit_py.mcp.controllers.storage_manager_controller import StorageManagerController
from ipfs_kit_py.mcp.controllers.storage_manager_controller_anyio import (
    StorageManagerControllerAnyIO,
)

# Export controllers for external use
__all__ = [
    "IPFSController",
    "IPFSControllerAnyIO",
    "StorageManagerController",
    "StorageManagerControllerAnyIO",
]

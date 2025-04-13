"""
Controller components for the MCP server.

The controllers handle HTTP requests and delegate to the appropriate
model components for business logic.
"""

from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.controllers.cli_controller import CliController
from ipfs_kit_py.mcp.controllers.credential_controller import CredentialController
from ipfs_kit_py.mcp.controllers.storage_manager_controller import StorageManagerController

# Import optional controllers if they exist
try:
    from ipfs_kit_py.mcp.controllers.fs_journal_controller import FsJournalController
    HAS_FS_JOURNAL = True
except ImportError:
    HAS_FS_JOURNAL = False

try:
    from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False

# Add other optional controllers similarly...

# Define __all__ dynamically based on successful imports
__all__ = [
    "IPFSController",
    "CliController",
    "CredentialController",
    "StorageManagerController",
]

if HAS_FS_JOURNAL:
    __all__.append("FsJournalController")
if HAS_LIBP2P:
    __all__.append("LibP2PController")

# Add other optional controllers to __all__ if imported...

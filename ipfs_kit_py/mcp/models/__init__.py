"""
Import bridge for MCP models module.
Redirects imports to the new mcp_server structure.
"""

import logging

# import importlib # Removed F401

# Configure logging
logger = logging.getLogger(__name__)

# Re-export all modules and symbols from the current package
try:
    from . import * # Import from current package

    logger.debug("Successfully imported from ipfs_kit_py.mcp.models")
except ImportError as e:
    logger.warning(f"Failed to import from ipfs_kit_py.mcp.models: {e}")

# Specific imports for backward compatibility (using relative imports)
try:
    from .ipfs_model import * # Use relative import
    from .ipfs_model_anyio import * # Use relative import

    logger.debug("Successfully imported ipfs models")
except ImportError as e:
    logger.warning(f"Failed to import ipfs models: {e}")

# Import storage models if available (using relative import)
try:
    from .storage import * # Use relative import
except ImportError as e:
    logger.warning(f"Failed to import from ipfs_kit_py.mcp.models.storage: {e}")

"""
Import bridge for MCP models module.
Redirects imports to the new mcp_server structure.
"""

import logging

# import importlib # Removed F401

# Configure logging
logger = logging.getLogger(__name__)

# Re-export all modules and symbols from mcp_server.models
try:
    from ipfs_kit_py.mcp_server.models import *

    logger.debug("Successfully imported from mcp_server.models")
except ImportError as e:
    logger.warning(f"Failed to import from mcp_server.models: {e}")

# Specific imports for backward compatibility
try:
    from ipfs_kit_py.mcp_server.models.ipfs_model import *
    from ipfs_kit_py.mcp_server.models.ipfs_model_anyio import *

    logger.debug("Successfully imported ipfs models")
except ImportError as e:
    logger.warning(f"Failed to import ipfs models: {e}")

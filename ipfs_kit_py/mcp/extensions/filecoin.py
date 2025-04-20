"""
Enhanced endpoints for Filecoin integration in the MCP server.

This module adds Filecoin integration to the MCP server
replacing the simulation with actual functionality.
"""

import logging
import os
import sys
from fastapi import APIRouter, HTTPException, Form
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Import our Filecoin storage implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from filecoin_storage import FilecoinStorage
except ImportError:
    logger.warning("FilecoinStorage module not found")
    FilecoinStorage = None

# Import advanced Filecoin features
try:
    from advanced_filecoin_mcp import create_advanced_filecoin_router
    ADVANCED_FILECOIN_AVAILABLE = True
    logger.info("Advanced Filecoin features are available")
except ImportError:
    ADVANCED_FILECOIN_AVAILABLE = False
    logger.warning("Advanced Filecoin features not available. Some functionality will be limited.")

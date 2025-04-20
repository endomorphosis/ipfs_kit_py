"""
IPFS Controller for the MCP server AnyIO version.

This controller provides an interface to the IPFS functionality through the MCP API using AnyIO.
"""

import logging
import time
import traceback
from typing import Dict, List, Any, Optional, Union
from fastapi import (
    APIRouter,
    HTTPException,
    Body,
    File,
    UploadFile,
    Form,
    Response,
    Query,
    Path,
    Request)

from pydantic import BaseModel, Field

# Import error handling module
import ipfs_kit_py.mcp_error_handling as mcp_error_handling

# Configure logger
logger = logging.getLogger(__name__)

class IPFSControllerAnyio:
    """AnyIO version of IPFSController"""
    def __init__(self, ipfs_model):
        self.ipfs_model = ipfs_model
        logger.info("IPFS Controller AnyIO initialized")

"""
Cache Manager for the MCP server.

This module provides a caching layer for operation results
with support for persistence across restarts.
"""

import os
import json
import time
import logging
import threading
import pickle
import tempfile
from typing import Dict, Any, Optional, List

# Configure logger
logger = logging.getLogger(__name__)


class MCPCacheManager:
    """
    Cache Manager for the MCP server.

    Provides memory and disk caching for operation results with
    automatic cleanup and persistence.
    """
    def __init__(self,
        base_path: str = None,
        memory_limit: int = 100 * 1024 * 1024,  # 100 MB
        disk_limit: int = 1024 * 1024 * 1024,  # 1 GB
        debug_mode: bool = False,
        config: Dict[str, Any] = None
    ):
        """
        Initialize the Cache Manager.

        Args:
            base_path: Base path for cache persistence
            memory_limit: Memory cache size limit in bytes
            disk_limit: Disk cache size limit in bytes
            debug_mode: Enable debug logging
            config: Additional configuration options
        """
        self.base_path = base_path or os.path.join(tempfile.gettempdir(), "mcp_cache")
        self.memory_limit = memory_limit
        self.disk_limit = disk_limit
        self.debug_mode = debug_mode
        self.config = config or {}
        
        # Initialize cache structures
        self.memory_cache = {}
        self.disk_cache_index = {}
        self.cache_lock = threading.RLock()
        
        # Create base directory if it doesn't exist
        os.makedirs(self.base_path, exist_ok=True)
        
        logger.info(f"Initialized MCPCacheManager at {self.base_path}")
        if self.debug_mode:
            logger.debug(f"Cache limits: memory={self.memory_limit}, disk={self.disk_limit}")

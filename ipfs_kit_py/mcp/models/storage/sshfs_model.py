#!/usr/bin/env python3
"""
SSHFS Model for MCP Storage Manager.

This model provides an interface between the MCP storage manager
and the SSHFS backend implementation.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base_storage_model import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)

class SSHFSModel(BaseStorageModel):
    """SSHFS storage model for MCP integration."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize SSHFS model.
        
        Args:
            config: SSHFS backend configuration
        """
        super().__init__()
        self.config = config or {}
        self.backend = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize the SSHFS backend."""
        try:
            from ipfs_kit_py.sshfs_backend import create_sshfs_backend
            
            if self.config:
                self.backend = create_sshfs_backend(self.config)
                logger.info("SSHFS backend initialized")
            else:
                logger.warning("SSHFS backend not initialized - no configuration provided")
        except ImportError as e:
            logger.error(f"Failed to import SSHFS backend: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize SSHFS backend: {e}")
    
    async def initialize(self) -> bool:
        """Initialize the SSHFS model."""
        if self.backend:
            return await self.backend.initialize()
        return False
    
    async def store(self, key: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store data using SSHFS backend."""
        if not self.backend:
            return {
                'success': False,
                'error': 'SSHFS backend not initialized'
            }
        
        try:
            success = await self.backend.store(key, data, metadata)
            return {
                'success': success,
                'key': key,
                'size': len(data),
                'backend': 'sshfs'
            }
        except Exception as e:
            logger.error(f"SSHFS store error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve data using SSHFS backend."""
        if not self.backend:
            return {
                'success': False,
                'error': 'SSHFS backend not initialized'
            }
        
        try:
            data = await self.backend.retrieve(key)
            if data is not None:
                return {
                    'success': True,
                    'key': key,
                    'data': data,
                    'size': len(data),
                    'backend': 'sshfs'
                }
            else:
                return {
                    'success': False,
                    'error': 'Data not found'
                }
        except Exception as e:
            logger.error(f"SSHFS retrieve error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete(self, key: str) -> Dict[str, Any]:
        """Delete data using SSHFS backend."""
        if not self.backend:
            return {
                'success': False,
                'error': 'SSHFS backend not initialized'
            }
        
        try:
            success = await self.backend.delete(key)
            return {
                'success': success,
                'key': key,
                'backend': 'sshfs'
            }
        except Exception as e:
            logger.error(f"SSHFS delete error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def exists(self, key: str) -> Dict[str, Any]:
        """Check if key exists using SSHFS backend."""
        if not self.backend:
            return {
                'success': False,
                'error': 'SSHFS backend not initialized'
            }
        
        try:
            exists = await self.backend.exists(key)
            return {
                'success': True,
                'key': key,
                'exists': exists,
                'backend': 'sshfs'
            }
        except Exception as e:
            logger.error(f"SSHFS exists error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def list_keys(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """List keys using SSHFS backend."""
        if not self.backend:
            return {
                'success': False,
                'error': 'SSHFS backend not initialized'
            }
        
        try:
            keys = await self.backend.list_keys(prefix)
            return {
                'success': True,
                'keys': keys,
                'count': len(keys),
                'prefix': prefix,
                'backend': 'sshfs'
            }
        except Exception as e:
            logger.error(f"SSHFS list_keys error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_info(self) -> Dict[str, Any]:
        """Get SSHFS backend information."""
        if not self.backend:
            return {
                'success': False,
                'error': 'SSHFS backend not initialized'
            }
        
        try:
            info = await self.backend.get_info()
            return {
                'success': True,
                'backend': 'sshfs',
                'info': info
            }
        except Exception as e:
            logger.error(f"SSHFS get_info error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on SSHFS backend."""
        if not self.backend:
            return {
                'success': False,
                'status': 'unhealthy',
                'error': 'SSHFS backend not initialized'
            }
        
        try:
            health = await self.backend.health_check()
            return {
                'success': True,
                'backend': 'sshfs',
                'health': health
            }
        except Exception as e:
            logger.error(f"SSHFS health_check error: {e}")
            return {
                'success': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def cleanup(self):
        """Clean up SSHFS backend resources."""
        if self.backend:
            try:
                await self.backend.cleanup()
                logger.info("SSHFS backend cleanup completed")
            except Exception as e:
                logger.error(f"SSHFS cleanup error: {e}")

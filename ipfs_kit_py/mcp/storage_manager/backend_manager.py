"""
Simple Backend Manager for MCP Server.

This module provides a minimal backend manager that can work with the existing
storage backends and provides the interface expected by the MCP server.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class BackendManager:
    """Simple backend manager that coordinates storage backends."""
    
    def __init__(self):
        """Initialize the backend manager."""
        self.backends: Dict[str, Any] = {}
        self.logger = logger
    
    def add_backend(self, name: str, backend: Any) -> None:
        """Add a backend to the manager."""
        self.backends[name] = backend
        self.logger.info(f"Added backend: {name} (type: {type(backend).__name__})")
    
    def get_backend(self, name: str) -> Any:
        """Get a backend by name."""
        return self.backends.get(name)
    
    def list_backends(self) -> List[str]:
        """List all backend names."""
        return list(self.backends.keys())
    
    def remove_backend(self, name: str) -> bool:
        """Remove a backend by name."""
        if name in self.backends:
            del self.backends[name]
            self.logger.info(f"Removed backend: {name}")
            return True
        return False
    
    def get_backend_info(self, name: str) -> Dict[str, Any]:
        """Get information about a backend."""
        backend = self.get_backend(name)
        if backend:
            info = {
                "name": name,
                "type": type(backend).__name__,
                "available": True
            }
            # Try to get status if the backend supports it
            if hasattr(backend, 'get_status'):
                try:
                    status = backend.get_status()
                    info.update(status)
                except Exception as e:
                    info["status_error"] = str(e)
            return info
        return {"name": name, "available": False, "error": "Backend not found"}
    
    def get_all_backend_info(self) -> Dict[str, Any]:
        """Get information about all backends."""
        info = {}
        for name in self.backends:
            info[name] = self.get_backend_info(name)
        return info
    
    async def initialize_default_backends(self):
        """Initialize default backends if available."""
        try:
            # Try to initialize IPFS backend
            from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
            from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
            
            ipfs_resources = {
                "ipfs_host": "127.0.0.1",
                "ipfs_port": 5001,
                "ipfs_timeout": 30,
                "allow_mock": True
            }
            ipfs_metadata = {"name": "ipfs", "description": "IPFS backend"}
            
            ipfs_backend = IPFSBackend(
                StorageBackendType.IPFS,
                ipfs_resources,
                ipfs_metadata
            )
            self.add_backend("ipfs", ipfs_backend)
            
        except Exception as e:
            self.logger.warning(f"Could not initialize IPFS backend: {e}")
        
        try:
            # Try to initialize S3 backend if available
            from ipfs_kit_py.mcp.storage_manager.backends.s3_backend import S3Backend
            
            s3_resources = {
                "aws_access_key_id": "mock_key",
                "aws_secret_access_key": "mock_secret",
                "region": "us-east-1",
                "bucket": "test-bucket"
            }
            s3_metadata = {"name": "s3", "description": "S3 backend"}
            
            s3_backend = S3Backend(s3_resources, s3_metadata)
            self.add_backend("s3", s3_backend)
            
        except Exception as e:
            self.logger.warning(f"Could not initialize S3 backend: {e}")
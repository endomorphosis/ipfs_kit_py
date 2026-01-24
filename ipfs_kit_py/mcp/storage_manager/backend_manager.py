"""
Simple Backend Manager for MCP Server.

This module provides a minimal backend manager that can work with the existing
storage backends and provides the interface expected by the MCP server.
"""

import logging
import os
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
        
        # Always add local backend first
        self.add_backend("local", LocalFileBackend())
        
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
            # Try to initialize Filecoin Pin backend
            from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
            
            filecoin_api_key = os.getenv('FILECOIN_PIN_API_KEY')
            filecoin_resources = {
                "api_key": filecoin_api_key,
                "timeout": 60
            }
            filecoin_metadata = {
                "name": "filecoin_pin",
                "description": "Filecoin Pin backend - unified IPFS + Filecoin storage",
                "default_replication": 3,
                "auto_renew": True
            }
            
            filecoin_backend = FilecoinPinBackend(filecoin_resources, filecoin_metadata)
            self.add_backend("filecoin_pin", filecoin_backend)
            
        except Exception as e:
            self.logger.warning(f"Could not initialize Filecoin Pin backend: {e}")
        
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


class LocalFileBackend:
    """Local file backend that manages files in ~/.ipfs_kit/uploads/"""
    
    def __init__(self):
        from pathlib import Path
        self.uploads_dir = Path.home() / ".ipfs_kit" / "uploads"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
    
    def get_name(self):
        return "local"
    
    def list(self, container=None, prefix=None, options=None):
        """List local files in ~/.ipfs_kit/uploads/"""
        try:
            items = []
            
            # Get all files in uploads directory
            for file_path in self.uploads_dir.glob("*"):
                if file_path.is_file():
                    # Skip if prefix doesn't match
                    if prefix and not file_path.name.startswith(prefix):
                        continue
                        
                    # Get file stats
                    stat = file_path.stat()
                    
                    items.append({
                        "identifier": str(file_path.relative_to(self.uploads_dir)),
                        "filename": file_path.name,
                        "size": stat.st_size,
                        "last_modified": stat.st_mtime,
                        "backend": "local",
                        "local_path": str(file_path)
                    })
            
            # Sort by modification time (newest first)
            items.sort(key=lambda x: x["last_modified"], reverse=True)
            
            # Apply max_keys limit if specified
            max_keys = options.get("max_keys", 1000) if options else 1000
            if len(items) > max_keys:
                items = items[:max_keys]
            
            return {
                "success": True,
                "items": items,
                "backend": "local",
                "container": container,
                "details": {
                    "total": len(items),
                    "directory": str(self.uploads_dir)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "backend": "local"
            }
    
    def add_content(self, content, metadata=None):
        """Add content is handled by the main upload endpoint for local backend"""
        return {
            "success": False,
            "error": "Local backend content addition is handled by the main upload endpoint"
        }
    
    def get_content(self, identifier):
        """Get content from local storage"""
        try:
            file_path = self.uploads_dir / identifier
            if file_path.exists() and file_path.is_file():
                with open(file_path, 'rb') as f:
                    content = f.read()
                return {
                    "success": True,
                    "data": content,
                    "backend": "local",
                    "identifier": identifier
                }
            else:
                return {
                    "success": False,
                    "error": f"File not found: {identifier}",
                    "backend": "local"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "backend": "local"
            }
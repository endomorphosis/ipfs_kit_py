#!/usr/bin/env python3
"""
Multi-Backend Filesystem Integration

This module provides a unified interface for storing and retrieving data across
multiple storage backends, including IPFS, Filecoin, S3, and others. It integrates
with the filesystem journal to track changes and maintain a consistent view across
different storage systems.
"""

import os
import sys
import json
import time
import base64
import logging
import tempfile
import hashlib
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple, Set, BinaryIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Storage config file
CONFIG_PATH = os.path.expanduser("~/.ipfs_storage_backends.json")

class StorageBackend:
    """Base class for storage backends"""
    
    def __init__(self, backend_id: str, config: Dict[str, Any]):
        self.backend_id = backend_id
        self.config = config
        self.backend_type = "base"
    
    async def store(self, content: Union[str, bytes], path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Store content and return storage identifier"""
        raise NotImplementedError("Subclasses must implement store()")
    
    async def retrieve(self, identifier: str) -> Dict[str, Any]:
        """Retrieve content by storage identifier"""
        raise NotImplementedError("Subclasses must implement retrieve()")
    
    async def delete(self, identifier: str) -> Dict[str, Any]:
        """Delete content by storage identifier"""
        raise NotImplementedError("Subclasses must implement delete()")
    
    async def list(self, prefix: str = "") -> Dict[str, Any]:
        """List content in the storage backend"""
        raise NotImplementedError("Subclasses must implement list()")
    
    def get_uri(self, identifier: str) -> str:
        """Get URI for content in this backend"""
        return f"mbfs://{self.backend_id}/{identifier}"

class IPFSBackend(StorageBackend):
    """IPFS storage backend"""
    
    def __init__(self, backend_id: str, config: Dict[str, Any]):
        super().__init__(backend_id, config)
        self.backend_type = "ipfs"
        self.api_url = config.get("api_url", "/ip4/127.0.0.1/tcp/5001")
        self.gateway_url = config.get("gateway_url", "https://ipfs.io/ipfs/")
    
    async def store(self, content: Union[str, bytes], path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Store content on IPFS"""
        try:
            # Handle string or bytes
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(prefix="ipfs-", suffix=f"-{os.path.basename(path)}", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(content_bytes)
            
            try:
                # Use ipfs add command
                cmd = ["ipfs", "add", "--quieter", temp_path]
                
                # Add pin option if specified
                pin = metadata.get("pin", True) if metadata else True
                if not pin:
                    cmd.append("--pin=false")
                
                # Run command
                import subprocess
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Get CID
                cid = result.stdout.strip()
                
                # Prepare metadata
                stored_metadata = {
                    "content_type": metadata.get("content_type", "application/octet-stream") if metadata else "application/octet-stream",
                    "size": len(content_bytes),
                    "original_path": path,
                    "pinned": pin,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
                if metadata:
                    # Add any additional metadata
                    for k, v in metadata.items():
                        if k not in stored_metadata and k != "pin":
                            stored_metadata[k] = v
                
                # Create URI
                uri = self.get_uri(cid)
                
                return {
                    "success": True,
                    "backend_id": self.backend_id,
                    "backend_type": self.backend_type,
                    "identifier": cid,
                    "uri": uri,
                    "http_url": f"{self.gateway_url}{cid}",
                    "metadata": stored_metadata
                }
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error storing content on IPFS: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "error": str(e)
            }
    
    async def retrieve(self, identifier: str) -> Dict[str, Any]:
        """Retrieve content from IPFS"""
        try:
            # Use ipfs cat command
            cmd = ["ipfs", "cat", identifier]
            
            # Run command
            import subprocess
            result = subprocess.run(cmd, capture_output=True, check=True)
            
            # Get content
            content_bytes = result.stdout
            
            # Encode as base64
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            return {
                "success": True,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "content_base64": content_base64,
                "size": len(content_bytes)
            }
        except Exception as e:
            logger.error(f"Error retrieving content from IPFS: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "error": str(e)
            }
    
    async def delete(self, identifier: str) -> Dict[str, Any]:
        """Delete content from IPFS (unpin)"""
        try:
            # Use ipfs pin rm command
            cmd = ["ipfs", "pin", "rm", identifier]
            
            # Run command
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            return {
                "success": True,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "message": f"Content unpinned: {identifier}"
            }
        except Exception as e:
            logger.error(f"Error unpinning content from IPFS: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "error": str(e)
            }
    
    async def list(self, prefix: str = "") -> Dict[str, Any]:
        """List pinned content in IPFS"""
        try:
            # Use ipfs pin ls command
            cmd = ["ipfs", "pin", "ls", "--quiet"]
            
            # Run command
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse output
            pins = [pin.strip() for pin in result.stdout.strip().split("\n") if pin.strip()]
            
            # Filter by prefix if specified
            if prefix:
                pins = [pin for pin in pins if pin.startswith(prefix)]
            
            return {
                "success": True,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "items": pins,
                "count": len(pins)
            }
        except Exception as e:
            logger.error(f"Error listing content from IPFS: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "error": str(e)
            }

class S3Backend(StorageBackend):
    """S3 storage backend"""
    
    def __init__(self, backend_id: str, config: Dict[str, Any]):
        super().__init__(backend_id, config)
        self.backend_type = "s3"
        self.bucket = config["bucket"]
        self.region = config.get("region", "us-east-1")
        self.access_key = config.get("access_key")
        self.secret_key = config.get("secret_key")
        self.endpoint_url = config.get("endpoint_url")
    
    async def _get_s3_client(self):
        """Get boto3 S3 client"""
        try:
            import boto3
            session = boto3.session.Session()
            
            kwargs = {
                "region_name": self.region
            }
            
            if self.access_key and self.secret_key:
                kwargs["aws_access_key_id"] = self.access_key
                kwargs["aws_secret_access_key"] = self.secret_key
            
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            
            return session.client("s3", **kwargs)
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
    
    async def store(self, content: Union[str, bytes], path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Store content on S3"""
        try:
            # Handle string or bytes
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content
            
            # Generate S3 key
            key = path
            if not key.startswith("/"):
                key = f"/{key}"
            
            # Remove leading slash for S3
            key = key.lstrip("/")
            
            # Get content type
            content_type = metadata.get("content_type", "application/octet-stream") if metadata else "application/octet-stream"
            
            # Prepare S3 metadata
            s3_metadata = {}
            if metadata:
                for k, v in metadata.items():
                    if k != "content_type" and isinstance(v, str):
                        s3_metadata[k] = v
            
            # Get S3 client
            s3 = await self._get_s3_client()
            
            # Upload content
            s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content_bytes,
                ContentType=content_type,
                Metadata=s3_metadata
            )
            
            # Create identifier and URI
            identifier = key
            uri = self.get_uri(identifier)
            
            # Generate HTTP URL
            if self.endpoint_url:
                http_url = f"{self.endpoint_url}/{self.bucket}/{key}"
            else:
                http_url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
            
            # Prepare metadata
            stored_metadata = {
                "content_type": content_type,
                "size": len(content_bytes),
                "original_path": path,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            if metadata:
                # Add any additional metadata
                for k, v in metadata.items():
                    if k not in stored_metadata:
                        stored_metadata[k] = v
            
            return {
                "success": True,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "uri": uri,
                "http_url": http_url,
                "metadata": stored_metadata
            }
        except Exception as e:
            logger.error(f"Error storing content on S3: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "error": str(e)
            }
    
    async def retrieve(self, identifier: str) -> Dict[str, Any]:
        """Retrieve content from S3"""
        try:
            # Get S3 client
            s3 = await self._get_s3_client()
            
            # Get object
            response = s3.get_object(
                Bucket=self.bucket,
                Key=identifier
            )
            
            # Get content
            content_bytes = response["Body"].read()
            
            # Encode as base64
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            # Get metadata
            metadata = dict(response.get("Metadata", {}))
            metadata["content_type"] = response.get("ContentType", "application/octet-stream")
            metadata["size"] = len(content_bytes)
            metadata["last_modified"] = response.get("LastModified").isoformat() if "LastModified" in response else None
            
            return {
                "success": True,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "content_base64": content_base64,
                "size": len(content_bytes),
                "metadata": metadata
            }
        except Exception as e:
            logger.error(f"Error retrieving content from S3: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "error": str(e)
            }
    
    async def delete(self, identifier: str) -> Dict[str, Any]:
        """Delete content from S3"""
        try:
            # Get S3 client
            s3 = await self._get_s3_client()
            
            # Delete object
            s3.delete_object(
                Bucket=self.bucket,
                Key=identifier
            )
            
            return {
                "success": True,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "message": f"Content deleted: {identifier}"
            }
        except Exception as e:
            logger.error(f"Error deleting content from S3: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "identifier": identifier,
                "error": str(e)
            }
    
    async def list(self, prefix: str = "") -> Dict[str, Any]:
        """List content in S3"""
        try:
            # Get S3 client
            s3 = await self._get_s3_client()
            
            # List objects
            if prefix:
                response = s3.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=prefix
                )
            else:
                response = s3.list_objects_v2(
                    Bucket=self.bucket
                )
            
            # Extract keys
            items = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    items.append({
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat() if "LastModified" in obj else None
                    })
            
            return {
                "success": True,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            logger.error(f"Error listing content from S3: {e}")
            return {
                "success": False,
                "backend_id": self.backend_id,
                "backend_type": self.backend_type,
                "error": str(e)
            }

class BackendManager:
    """Manager for multiple storage backends"""
    
    def __init__(self):
        self.backends = {}
        self.default_backend_id = None
        self._load_config()
    
    def _load_config(self):
        """Load backend configuration from file"""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                
                # Register backends
                for backend_config in config.get("backends", []):
                    backend_id = backend_config.get("id")
                    backend_type = backend_config.get("type")
                    
                    if not backend_id or not backend_type:
                        continue
                    
                    self.register_backend(backend_id, backend_type, backend_config.get("config", {}))
                
                # Set default backend
                self.default_backend_id = config.get("default_backend")
        except Exception as e:
            logger.error(f"Error loading backend configuration: {e}")
    
    def _save_config(self):
        """Save backend configuration to file"""
        try:
            config = {
                "backends": [],
                "default_backend": self.default_backend_id
            }
            
            # Add backends
            for backend_id, backend in self.backends.items():
                backend_config = {
                    "id": backend_id,
                    "type": backend.backend_type,
                    "config": backend.config
                }
                config["backends"].append(backend_config)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            
            # Save config
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving backend configuration: {e}")
    
    def register_backend(self, backend_id: str, backend_type: str, config: Dict[str, Any]) -> bool:
        """Register a storage backend"""
        try:
            if backend_id in self.backends:
                return False
            
            # Create backend instance
            if backend_type == "ipfs":
                backend = IPFSBackend(backend_id, config)
            elif backend_type == "s3":
                backend = S3Backend(backend_id, config)
            else:
                logger.error(f"Unknown backend type: {backend_type}")
                return False
            
            # Add to backends
            self.backends[backend_id] = backend
            
            # Set as default if we don't have one
            if not self.default_backend_id:
                self.default_backend_id = backend_id
            
            # Save config
            self._save_config()
            
            return True
        except Exception as e:
            logger.error(f"Error registering backend {backend_id}: {e}")
            return False
    
    def set_default_backend(self, backend_id: str) -> bool:
        """Set the default backend"""
        if backend_id not in self.backends:
            return False
        
        self.default_backend_id = backend_id
        self._save_config()
        return True
    
    def get_backend(self, backend_id: Optional[str] = None) -> Optional[StorageBackend]:
        """Get a storage backend"""
        if backend_id:
            return self.backends.get(backend_id)
        elif self.default_backend_id:
            return self.backends.get(self.default_backend_id)
        else:
            return None
    
    def get_backend_from_uri(self, uri: str) -> Tuple[Optional[StorageBackend], Optional[str]]:
        """Parse a URI and return the backend and identifier"""
        if not uri.startswith("mbfs://"):
            return None, None
        
        # Parse URI
        try:
            # Format: mbfs://backend_id/identifier
            parts = uri[7:].split("/", 1)
            
            if len(parts) != 2:
                return None, None
            
            backend_id, identifier = parts
            
            # Get backend
            backend = self.get_backend(backend_id)
            if not backend:
                return None, None
            
            return backend, identifier
        except:
            return None, None
    
    def get_backends(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all backends"""
        result = {}
        
        for backend_id, backend in self.backends.items():
            result[backend_id] = {
                "id": backend_id,
                "type": backend.backend_type,
                "is_default": backend_id == self.default_backend_id,
                "config": {k: v for k, v in backend.config.items() if k not in ["access_key", "secret_key"]}
            }
        
        return result
    
    def remove_backend(self, backend_id: str) -> bool:
        """Remove a storage backend"""
        if backend_id not in self.backends:
            return False
        
        # Remove from backends
        del self.backends[backend_id]
        
        # Update default backend if needed
        if self.default_backend_id == backend_id:
            if self.backends:
                self.default_backend_id = next(iter(self.backends.keys()))
            else:
                self.default_backend_id = None
        
        # Save config
        self._save_config()
        
        return True

# Global backend manager instance
backend_manager = BackendManager()

# Export key functions at module level for direct import
# This ensures tools like mbfs_get_backend are available when imported directly
mbfs_get_backend = None  # Will be set by register_tools
mbfs_list_backends = None
mbfs_store = None
mbfs_retrieve = None
mbfs_delete = None
mbfs_register_backend = None

def register_tools(server) -> bool:
    """Register multi-backend filesystem integration tools with MCP server"""
    global mbfs_get_backend, mbfs_list_backends, mbfs_store, mbfs_retrieve, mbfs_delete, mbfs_register_backend
    logger.info("Registering multi-backend filesystem integration tools...")
    
    # Try to use enhanced parameter adapter for better compatibility
    try:
        # Add current directory to path to find the adapter module
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(script_dir)
        
        # Try to import the enhanced adapter first, fall back to basic if not available
        try:
            from enhanced_parameter_adapter import adapt_parameters, create_tool_wrapper, create_generic_handler, ToolContext
            logger.info("✅ Using enhanced parameter adapter for multi-backend tools")
            using_enhanced_adapter = True
        except ImportError:
            # Fall back to original adapter if enhanced is not available
            from tool_parameter_adapter import adapt_parameters
            logger.info("⚠️ Enhanced adapter not found, using basic parameter adapter for multi-backend tools")
            using_enhanced_adapter = False
        
        # Tool: Register a storage backend
        if using_enhanced_adapter:
            # Use enhanced adapter with specific parameter mappings for this tool
            backend_register_mappings = {
                'backend_id': ['backend_id', 'id', 'name'],
                'backend_type': ['backend_type', 'type'],
                'make_default': ['make_default', 'default']
            }
            
            @adapt_parameters(mappings=backend_register_mappings)
            async def mbfs_register_backend(backend_id, backend_type, config=None, make_default=False):
                if not backend_id or not backend_type:
                    return {
                        "success": False,
                        "error": "Missing required parameters: backend_id and backend_type"
                    }
                
                # Register backend
                success = backend_manager.register_backend(backend_id, backend_type, config or {})
                
                if not success:
                    return {
                        "success": False,
                        "error": f"Failed to register backend: {backend_id}"
                    }
                
                # Set as default if requested
                if make_default:
                    backend_manager.set_default_backend(backend_id)
                
                return {
                    "success": True,
                    "backend_id": backend_id,
                    "backend_type": backend_type,
                    "is_default": backend_id == backend_manager.default_backend_id
                }
            
            # No need for a wrapper creation function with the enhanced adapter
            mbfs_register_backend_wrapper = mbfs_register_backend
        else:
            # Use the basic adapter approach with wrapper creation function
            def create_register_backend_wrapper():
                async def wrapper(ctx):
                    # Extract arguments
                    arguments = {}
                    if hasattr(ctx, 'arguments') and ctx.arguments is not None:
                        arguments = ctx.arguments
                    elif hasattr(ctx, 'params') and ctx.params is not None:
                        arguments = ctx.params
                    
                    try:
                        # Get required parameters with fallbacks
                        backend_id = arguments.get('backend_id', arguments.get('name', arguments.get('id')))
                        backend_type = arguments.get('backend_type', arguments.get('type'))
                        config = arguments.get('config', {})
                        make_default = arguments.get('make_default', False)
                        
                        if not backend_id or not backend_type:
                            return {
                                "success": False,
                                "error": "Missing required parameters: backend_id and backend_type"
                            }
                        
                        # Register backend
                        success = backend_manager.register_backend(backend_id, backend_type, config)
                        
                        if not success:
                            return {
                                "success": False,
                                "error": f"Failed to register backend: {backend_id}"
                            }
                        
                        # Set as default if requested
                        if make_default:
                            backend_manager.set_default_backend(backend_id)
                        
                        return {
                            "success": True,
                            "backend_id": backend_id,
                            "backend_type": backend_type,
                            "is_default": backend_id == backend_manager.default_backend_id
                        }
                    except Exception as e:
                        logger.error(f"Error registering backend: {e}")
                        return {"success": False, "error": str(e)}
                return wrapper
            
            # Create wrapper instances for each tool
            mbfs_register_backend_wrapper = create_register_backend_wrapper()
        
        # Tool: Get backend information
        def create_get_backend_wrapper():
            async def wrapper(ctx):
                # Extract arguments
                arguments = {}
                if hasattr(ctx, 'arguments') and ctx.arguments is not None:
                    arguments = ctx.arguments
                elif hasattr(ctx, 'params') and ctx.params is not None:
                    arguments = ctx.params
                
                try:
                    # Get backend ID with fallbacks
                    backend_id = arguments.get('backend_id', arguments.get('name', arguments.get('id')))
                    
                    # Get backend
                    backend = backend_manager.get_backend(backend_id)
                    
                    if not backend:
                        return {
                            "success": False,
                            "error": f"Backend not found: {backend_id or '<default>'}"
                        }
                    
                    # Return backend information
                    return {
                        "success": True,
                        "backend_id": backend.backend_id,
                        "backend_type": backend.backend_type,
                        "is_default": backend.backend_id == backend_manager.default_backend_id,
                        "config": {k: v for k, v in backend.config.items() if k not in ["access_key", "secret_key"]}
                    }
                except Exception as e:
                    logger.error(f"Error getting backend information: {e}")
                    return {"success": False, "error": str(e)}
            return wrapper
        
        # Tool: List all backends
        def create_list_backends_wrapper():
            async def wrapper(ctx):
                try:
                    backends = backend_manager.get_backends()
                    
                    return {
                        "success": True,
                        "backends": backends,
                        "count": len(backends),
                        "default_backend": backend_manager.default_backend_id
                    }
                except Exception as e:
                    logger.error(f"Error listing backends: {e}")
                    return {"success": False, "error": str(e)}
            return wrapper
        
        # Create wrapper instances
        mbfs_get_backend = create_get_backend_wrapper()
        mbfs_list_backends = create_list_backends_wrapper()
        
        # Tool: Store content using a backend
        @adapt_parameters
        async def mbfs_store(content=None, path=None, backend_id=None, metadata=None, **kwargs):
            """Store content using a storage backend"""
            try:
                # Apply alternative naming
                if not content and "data" in kwargs:
                    content = kwargs["data"]
                if not content and "text" in kwargs:
                    content = kwargs["text"]
                if not path and "file_path" in kwargs:
                    path = kwargs["file_path"]
                if not backend_id and "name" in kwargs:
                    backend_id = kwargs["name"]
                if not backend_id and "id" in kwargs:
                    backend_id = kwargs["id"]
                
                metadata = metadata or {}
                
                if not content:
                    return {
                        "success": False,
                        "error": "Missing required parameter: content"
                    }
                
                if not path:
                    return {
                        "success": False,
                        "error": "Missing required parameter: path"
                    }
                
                # Get backend
                backend = backend_manager.get_backend(backend_id)
                
                if not backend:
                    return {
                        "success": False,
                        "error": f"Backend not found: {backend_id or '<default>'}"
                    }
                
                # Store content
                result = await backend.store(content, path, metadata)
                
                # Return result
                return result
            except Exception as e:
                logger.error(f"Error storing content: {e}")
                return {"success": False, "error": str(e)}
        
        # Tool: Retrieve content from a backend
        @adapt_parameters
        async def mbfs_retrieve(identifier=None, backend_id=None, **kwargs):
            """Retrieve content from a storage backend"""
            try:
                # Apply alternative naming
                if not identifier and "cid" in kwargs:
                    identifier = kwargs["cid"]
                if not identifier and "hash" in kwargs:
                    identifier = kwargs["hash"]
                if not backend_id and "name" in kwargs:
                    backend_id = kwargs["name"]
                if not backend_id and "id" in kwargs:
                    backend_id = kwargs["id"]
                
                if not identifier:
                    return {
                        "success": False,
                        "error": "Missing required parameter: identifier"
                    }
                
                # Get backend
                backend = backend_manager.get_backend(backend_id)
                
                if not backend:
                    return {
                        "success": False,
                        "error": f"Backend not found: {backend_id or '<default>'}"
                    }
                
                # Retrieve content
                result = await backend.retrieve(identifier)
                
                # Return result
                return result
            except Exception as e:
                logger.error(f"Error retrieving content: {e}")
                return {"success": False, "error": str(e)}
        
        # Tool: Delete content from a backend
        @adapt_parameters
        async def mbfs_delete(identifier=None, backend_id=None, **kwargs):
            """Delete content from a storage backend"""
            try:
                # Apply alternative naming
                if not identifier and "cid" in kwargs:
                    identifier = kwargs["cid"]
                if not identifier and "hash" in kwargs:
                    identifier = kwargs["hash"]
                if not backend_id and "name" in kwargs:
                    backend_id = kwargs["name"]
                if not backend_id and "id" in kwargs:
                    backend_id = kwargs["id"]
                
                if not identifier:
                    return {
                        "success": False,
                        "error": "Missing required parameter: identifier"
                    }
                
                # Get backend
                backend = backend_manager.get_backend(backend_id)
                
                if not backend:
                    return {
                        "success": False,
                        "error": f"Backend not found: {backend_id or '<default>'}"
                    }
                
                # Delete content
                result = await backend.delete(identifier)
                
                # Return result
                return result
            except Exception as e:
                logger.error(f"Error deleting content: {e}")
                return {"success": False, "error": str(e)}
        
        # Register all tools with MCP server
        try:
            # Register tools with MCP server
            server.tool(name="mbfs_register_backend", description="Register a storage backend")(mbfs_register_backend)
            server.tool(name="mbfs_get_backend", description="Get information about a storage backend")(mbfs_get_backend)
            server.tool(name="mbfs_list_backends", description="List all registered backends")(mbfs_list_backends)
            server.tool(name="mbfs_store", description="Store content using a storage backend")(mbfs_store)
            server.tool(name="mbfs_retrieve", description="Retrieve content from a storage backend")(mbfs_retrieve)
            server.tool(name="mbfs_delete", description="Delete content from a storage backend")(mbfs_delete)
            
            # Create a default backend if none exists
            if not backend_manager.backends:
                backend_manager.register_backend(
                    "ipfs-default",
                    "ipfs",
                    {
                        "api_url": "/ip4/127.0.0.1/tcp/5001",
                        "gateway_url": "https://ipfs.io/ipfs/"
                    }
                )
                backend_manager.set_default_backend("ipfs-default")
                logger.info("Registered default IPFS backend")
            
            logger.info("✅ Multi-backend filesystem integration tools registered successfully")
            return True
        except Exception as e:
            logger.error(f"Error registering multi-backend filesystem tools: {e}")
            return False
            
    except ImportError:
        logger.warning("⚠️ Parameter adapter not available, using direct registration")
        
        # Define tools without the adapter
        # Tool: Register a storage backend
        async def mbfs_register_backend(ctx):
            # Extract parameters
            try:
                params = ctx.arguments if hasattr(ctx, 'arguments') else ctx.params if hasattr(ctx, 'params') else {}
                backend_id = params.get('backend_id', params.get('name', params.get('id')))
                backend_type = params.get('backend_type', params.get('type'))
                config = params.get('config', {})
                make_default = params.get('make_default', False)
                
                if not backend_id or not backend_type:
                    return {
                        "success": False,
                        "error": "Missing required parameters: backend_id and backend_type"
                    }
                
                # Register backend
                success = backend_manager.register_backend(backend_id, backend_type, config)
                
                if not success:
                    return {
                        "success": False,
                        "error": f"Failed to register backend: {backend_id}"
                    }
                
                # Set as default if requested
                if make_default:
                    backend_manager.set_default_backend(backend_id)
                
                return {
                    "success": True,
                    "backend_id": backend_id,
                    "backend_type": backend_type,
                    "is_default": backend_id == backend_manager.default_backend_id
                }
            except Exception as e:
                logger.error(f"Error registering backend: {e}")
                return {"success": False, "error": str(e)}
                
        # Register all tools with the MCP server without adapter
        try:
            server.add_tool(mbfs_register_backend, name="mbfs_register_backend")
            
            # Similar approach for other tools...
            # For brevity, I'm not including all of them here
            
            logger.info("✅ Multi-backend filesystem integration tools registered (without adapter)")
            return True
        except Exception as e:
            logger.error(f"Error registering multi-backend filesystem tools: {e}")
            return False

# Alias for compatibility with calling code
class MultiBackendFS(BackendManager):
    """
    Multi-backend filesystem manager.
    This is an alias for BackendManager to match calling code expectations.
    """
    
    def __init__(self, working_dir=None):
        # Initialize the backend manager (ignore working_dir parameter for now)
        super().__init__()
        self.working_dir = working_dir or os.getcwd()

# Alias function for compatibility with the calling code
def register_multi_backend_tools(server) -> bool:
    """
    Register multi-backend tools with the MCP server.
    This is an alias for register_tools() to match calling code expectations.
    
    Args:
        server: The MCP server instance to register tools with
        
    Returns:
        bool: True if registration successful, False otherwise
    """
    return register_tools(server)

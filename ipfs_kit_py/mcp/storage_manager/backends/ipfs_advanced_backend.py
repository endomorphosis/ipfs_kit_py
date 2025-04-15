"""
Advanced IPFS Backend Extensions

This module extends the core IPFSBackend with advanced IPFS operations:
- DHT operations for enhanced network participation
- Object and DAG manipulation operations
- Advanced IPNS functionality with key management
- MFS (Mutable File System) operations
- Swarm and diagnostic operations

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import logging
import asyncio
import json
import base64
import tempfile
from typing import Dict, Any, List, Optional, Union, BinaryIO

from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType
from .ipfs_backend import IPFSBackend

# Configure logging
logger = logging.getLogger(__name__)


class IPFSAdvancedBackend(IPFSBackend):
    """
    Extended IPFS backend implementation with advanced operations.
    
    This class inherits from the base IPFSBackend and adds advanced operations
    to fulfill the roadmap requirements.
    """
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize the advanced IPFS backend."""
        super().__init__(resources, metadata)
        logger.info("Advanced IPFS backend initialized")
    
    # --- DHT Operations ---
    
    async def ipfs_dht_provide(self, cid: str, recursive: bool = False, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Announce to the network that you are providing a content.
        
        Args:
            cid: Content identifier to provide
            recursive: Whether to provide recursively
            timeout: Optional timeout in seconds
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["dht", "provide", cid]
            if recursive:
                args.append("--recursive")
            if timeout:
                args.extend(["--timeout", str(timeout)])
            
            # Execute command
            result = await self._execute_ipfs_command(args)
            return result
        except Exception as e:
            logger.error(f"Error in dht provide: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_dht_findpeer(self, peer_id: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Find a specific peer in the DHT network.
        
        Args:
            peer_id: Peer ID to find
            timeout: Optional timeout in seconds
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["dht", "findpeer", peer_id]
            if timeout:
                args.extend(["--timeout", str(timeout)])
            
            # Execute command
            result = await self._execute_ipfs_command(args)
            return result
        except Exception as e:
            logger.error(f"Error in dht findpeer: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_dht_findprovs(self, cid: str, num_providers: int = 20, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Find providers for a specific CID in the DHT network.
        
        Args:
            cid: Content identifier to find providers for
            num_providers: Maximum number of providers to find
            timeout: Optional timeout in seconds
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["dht", "findprovs", cid, "--num-providers", str(num_providers)]
            if timeout:
                args.extend(["--timeout", str(timeout)])
            
            # Execute command
            result = await self._execute_ipfs_command(args)
            return result
        except Exception as e:
            logger.error(f"Error in dht findprovs: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_dht_query(self, peer_id: str) -> Dict[str, Any]:
        """
        Find the closest peers to a given peer ID in the DHT.
        
        Args:
            peer_id: Peer ID to query
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            result = await self._execute_ipfs_command(["dht", "query", peer_id])
            return result
        except Exception as e:
            logger.error(f"Error in dht query: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- Object Operations ---
    
    async def ipfs_object_get(self, cid: str) -> Dict[str, Any]:
        """
        Get the raw bytes of an IPFS object.
        
        Args:
            cid: Content identifier to get
            
        Returns:
            Dict with operation result
        """
        try:
            # Check if client has direct method
            if hasattr(self.ipfs, "ipfs_object_get"):
                return await self.ipfs.ipfs_object_get(cid)
            
            # Use command with direct output
            result = await self._execute_ipfs_command(["object", "get", cid], parse_json=False)
            
            # If success, parse the JSON output
            if result.get("success", False) and "output" in result:
                try:
                    data = json.loads(result["output"])
                    result["data"] = data
                    return result
                except json.JSONDecodeError:
                    return {"success": False, "error": "Failed to parse object data", "error_type": "JSONDecodeError"}
            
            return result
        except Exception as e:
            logger.error(f"Error in object get: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_put(self, data: Union[str, bytes], input_enc: str = "json") -> Dict[str, Any]:
        """
        Create a new IPFS object from data.
        
        Args:
            data: Object data to put
            input_enc: Input encoding (json or protobuf)
            
        Returns:
            Dict with operation result
        """
        try:
            # Ensure data is bytes
            if isinstance(data, str):
                data_bytes = data.encode()
            else:
                data_bytes = data
            
            # Use a temporary file to store the data
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(data_bytes)
                temp_file_path = temp_file.name
            
            try:
                # Execute command
                result = await self._execute_ipfs_command(
                    ["object", "put", temp_file_path, "--input-enc", input_enc],
                    parse_json=True
                )
                
                return result
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error in object put: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_stat(self, cid: str) -> Dict[str, Any]:
        """
        Get stats for an IPFS object.
        
        Args:
            cid: Content identifier to stat
            
        Returns:
            Dict with operation result
        """
        try:
            # Use existing method from base class
            if hasattr(self.ipfs, "ipfs_object_stat"):
                return await self.ipfs.ipfs_object_stat(cid)
            
            # Execute command
            return await self._execute_ipfs_command(["object", "stat", cid])
        except Exception as e:
            logger.error(f"Error in object stat: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_links(self, cid: str) -> Dict[str, Any]:
        """
        Get links in an IPFS object.
        
        Args:
            cid: Content identifier to get links from
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["object", "links", cid])
        except Exception as e:
            logger.error(f"Error in object links: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_new(self, template: str = "unixfs-dir") -> Dict[str, Any]:
        """
        Create a new IPFS object from a template.
        
        Args:
            template: Template to use (unixfs-dir)
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["object", "new", template])
        except Exception as e:
            logger.error(f"Error in object new: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_patch_add_link(self, cid: str, link_name: str, link_cid: str) -> Dict[str, Any]:
        """
        Add a link to an IPFS object.
        
        Args:
            cid: Content identifier to patch
            link_name: Name of the link to add
            link_cid: CID to link to
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["object", "patch", "add-link", cid, link_name, link_cid])
        except Exception as e:
            logger.error(f"Error in object patch add-link: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_patch_rm_link(self, cid: str, link_name: str) -> Dict[str, Any]:
        """
        Remove a link from an IPFS object.
        
        Args:
            cid: Content identifier to patch
            link_name: Name of the link to remove
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["object", "patch", "rm-link", cid, link_name])
        except Exception as e:
            logger.error(f"Error in object patch rm-link: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_patch_set_data(self, cid: str, data: bytes) -> Dict[str, Any]:
        """
        Set the data of an IPFS object.
        
        Args:
            cid: Content identifier to patch
            data: New data
            
        Returns:
            Dict with operation result
        """
        try:
            # Use a temporary file to store the data
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(data)
                temp_file_path = temp_file.name
            
            try:
                # Execute command
                return await self._execute_ipfs_command(["object", "patch", "set-data", cid, temp_file_path])
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error in object patch set-data: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_object_patch_append_data(self, cid: str, data: bytes) -> Dict[str, Any]:
        """
        Append data to an IPFS object.
        
        Args:
            cid: Content identifier to patch
            data: Data to append
            
        Returns:
            Dict with operation result
        """
        try:
            # Use a temporary file to store the data
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(data)
                temp_file_path = temp_file.name
            
            try:
                # Execute command
                return await self._execute_ipfs_command(["object", "patch", "append-data", cid, temp_file_path])
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error in object patch append-data: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- DAG Operations ---
    
    async def ipfs_dag_put(
        self, 
        object_json: Union[str, bytes, Dict[str, Any]], 
        pin: bool = True,
        hash_algorithm: str = "sha2-256",
        cid_version: int = 1,
        format: str = "dag-cbor"
    ) -> Dict[str, Any]:
        """
        Add a DAG node to IPFS.
        
        Args:
            object_json: DAG node data (JSON string, bytes, or dict)
            pin: Whether to pin the DAG node
            hash_algorithm: Hash algorithm to use
            cid_version: CID version to use
            format: Format to use (dag-cbor or dag-json)
            
        Returns:
            Dict with operation result
        """
        try:
            # Prepare JSON data
            if isinstance(object_json, dict):
                json_str = json.dumps(object_json)
            elif isinstance(object_json, bytes):
                json_str = object_json.decode('utf-8')
            else:
                json_str = object_json
            
            # Use a temporary file to store the JSON
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
                temp_file.write(json_str.encode())
                temp_file_path = temp_file.name
            
            try:
                # Construct command arguments
                args = ["dag", "put"]
                
                if not pin:
                    args.append("--pin=false")
                
                # Add format and hash algorithm options
                args.extend(["--input-codec", format, "--hash", hash_algorithm])
                
                # Add CID version
                args.extend(["--cid-version", str(cid_version)])
                
                # Add input file
                args.append(temp_file_path)
                
                # Execute command
                return await self._execute_ipfs_command(args)
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error in dag put: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_dag_get(self, cid: str, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a DAG node from IPFS.
        
        Args:
            cid: Content identifier to get
            path: Optional path within the DAG node
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct path argument
            path_arg = f"{cid}"
            if path:
                path_arg = f"{cid}/{path}"
            
            # Execute command
            result = await self._execute_ipfs_command(["dag", "get", path_arg], parse_json=False)
            
            # If success, parse the JSON output
            if result.get("success", False) and "output" in result:
                try:
                    data = json.loads(result["output"])
                    result["data"] = data
                    return result
                except json.JSONDecodeError:
                    return {"success": False, "error": "Failed to parse DAG data", "error_type": "JSONDecodeError"}
            
            return result
        except Exception as e:
            logger.error(f"Error in dag get: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_dag_resolve(self, cid: str, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolve a path in a DAG node.
        
        Args:
            cid: Content identifier to resolve
            path: Optional path to resolve
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct path argument
            path_arg = f"{cid}"
            if path:
                path_arg = f"{cid}/{path}"
            
            # Execute command
            return await self._execute_ipfs_command(["dag", "resolve", path_arg])
        except Exception as e:
            logger.error(f"Error in dag resolve: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- IPNS Operations ---
    
    async def ipfs_name_publish(
        self, 
        cid: str, 
        key: str = "self", 
        lifetime: str = "24h", 
        ttl: str = "1m",
        allow_offline: bool = False
    ) -> Dict[str, Any]:
        """
        Publish an IPNS name.
        
        Args:
            cid: Content identifier to publish
            key: Key to use
            lifetime: Record lifetime
            ttl: Record TTL
            allow_offline: Whether to allow publishing while offline
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["name", "publish", "--key", key, "--lifetime", lifetime, "--ttl", ttl]
            
            if allow_offline:
                args.append("--allow-offline")
            
            # Add CID
            args.append(cid)
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in name publish: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_name_resolve(
        self, 
        name: str, 
        recursive: bool = True, 
        nocache: bool = False
    ) -> Dict[str, Any]:
        """
        Resolve an IPNS name.
        
        Args:
            name: IPNS name to resolve
            recursive: Whether to resolve recursively
            nocache: Whether to bypass cache
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["name", "resolve"]
            
            if not recursive:
                args.append("--recursive=false")
            
            if nocache:
                args.append("--nocache")
            
            # Add name
            args.append(name)
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in name resolve: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_name_pubsub_state(self) -> Dict[str, Any]:
        """
        Get the state of IPNS pubsub.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["name", "pubsub", "state"])
        except Exception as e:
            logger.error(f"Error in name pubsub state: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_name_pubsub_subs(self) -> Dict[str, Any]:
        """
        List subscribed IPNS pubsub topics.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["name", "pubsub", "subs"])
        except Exception as e:
            logger.error(f"Error in name pubsub subs: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_name_pubsub_cancel(self, name: str) -> Dict[str, Any]:
        """
        Cancel a subscription to an IPNS pubsub topic.
        
        Args:
            name: IPNS name to cancel
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["name", "pubsub", "cancel", name])
        except Exception as e:
            logger.error(f"Error in name pubsub cancel: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- Key Management ---
    
    async def ipfs_key_gen(self, name: str, type: str = "rsa", size: int = 2048) -> Dict[str, Any]:
        """
        Generate a new key.
        
        Args:
            name: Key name
            type: Key type (rsa, ed25519, secp256k1)
            size: Key size (for RSA)
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["key", "gen", name, "--type", type]
            
            # Add size for RSA keys
            if type.lower() == "rsa":
                args.extend(["--size", str(size)])
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in key gen: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_key_list(self) -> Dict[str, Any]:
        """
        List all keys.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["key", "list", "--l"])
        except Exception as e:
            logger.error(f"Error in key list: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_key_rm(self, name: str) -> Dict[str, Any]:
        """
        Remove a key.
        
        Args:
            name: Key name to remove
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["key", "rm", name])
        except Exception as e:
            logger.error(f"Error in key rm: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_key_rename(self, old_name: str, new_name: str, force: bool = False) -> Dict[str, Any]:
        """
        Rename a key.
        
        Args:
            old_name: Current key name
            new_name: New key name
            force: Whether to force renaming if the new name already exists
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["key", "rename", old_name, new_name]
            
            if force:
                args.append("--force")
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in key rename: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_key_import(self, name: str, key_data: bytes) -> Dict[str, Any]:
        """
        Import a key.
        
        Args:
            name: Name for the imported key
            key_data: Key data to import
            
        Returns:
            Dict with operation result
        """
        try:
            # Use a temporary file to store the key data
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(key_data)
                temp_file_path = temp_file.name
            
            try:
                # Execute command
                return await self._execute_ipfs_command(["key", "import", name, temp_file_path])
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error in key import: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_key_export(self, name: str) -> Dict[str, Any]:
        """
        Export a key.
        
        Args:
            name: Key name to export
            
        Returns:
            Dict with operation result including key data
        """
        try:
            # Use a temporary file to store the exported key
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            try:
                # Execute command
                result = await self._execute_ipfs_command(["key", "export", name, "--output", temp_file_path])
                
                # Read key data from file if export was successful
                if result.get("success", False) and os.path.exists(temp_file_path):
                    with open(temp_file_path, "rb") as f:
                        key_data = f.read()
                    
                    # Add key data to result
                    result["key_data"] = key_data
                
                return result
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error in key export: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- File Operations ---
    
    async def ipfs_ls(self, cid: str) -> Dict[str, Any]:
        """
        List directory contents for Unix filesystem objects.
        
        Args:
            cid: Content identifier to list
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["ls", cid])
        except Exception as e:
            logger.error(f"Error in ls: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_stat(self, path: str) -> Dict[str, Any]:
        """
        Get stats for a file or directory in the MFS.
        
        Args:
            path: Path in the MFS
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["files", "stat", path])
        except Exception as e:
            logger.error(f"Error in files stat: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_mkdir(self, path: str, parents: bool = False) -> Dict[str, Any]:
        """
        Create a directory in the MFS.
        
        Args:
            path: Path to create
            parents: Whether to create parent directories
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["files", "mkdir", path]
            
            if parents:
                args.append("--parents")
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in files mkdir: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_write(
        self, 
        path: str, 
        data: bytes, 
        offset: int = 0, 
        create: bool = True, 
        truncate: bool = True,
        parents: bool = False
    ) -> Dict[str, Any]:
        """
        Write to a file in the MFS.
        
        Args:
            path: Path to write to
            data: Data to write
            offset: Offset to write at
            create: Whether to create the file if it doesn't exist
            truncate: Whether to truncate the file before writing
            parents: Whether to create parent directories
            
        Returns:
            Dict with operation result
        """
        try:
            # Use a temporary file to store the data
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(data)
                temp_file_path = temp_file.name
            
            try:
                # Construct command arguments
                args = ["files", "write"]
                
                if offset > 0:
                    args.extend(["--offset", str(offset)])
                
                if not create:
                    args.append("--create=false")
                
                if not truncate:
                    args.append("--truncate=false")
                
                if parents:
                    args.append("--parents")
                
                # Add path and input file
                args.extend([path, temp_file_path])
                
                # Execute command
                return await self._execute_ipfs_command(args)
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error in files write: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_read(self, path: str, offset: int = 0, count: Optional[int] = None) -> Dict[str, Any]:
        """
        Read a file from the MFS.
        
        Args:
            path: Path to read from
            offset: Offset to read from
            count: Maximum bytes to read
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["files", "read"]
            
            if offset > 0:
                args.extend(["--offset", str(offset)])
            
            if count is not None:
                args.extend(["--count", str(count)])
            
            # Add path
            args.append(path)
            
            # Execute command with raw output
            result = await self._execute_ipfs_command(args, parse_json=False)
            
            # If success, add binary data
            if result.get("success", False) and "output" in result:
                result["data"] = result["output"].encode("utf-8") if isinstance(result["output"], str) else result["output"]
            
            return result
        except Exception as e:
            logger.error(f"Error in files read: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_rm(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """
        Remove a file or directory from the MFS.
        
        Args:
            path: Path to remove
            recursive: Whether to recursively remove directories
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["files", "rm", path]
            
            if recursive:
                args.append("--recursive")
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in files rm: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_cp(self, source: str, dest: str, parents: bool = False) -> Dict[str, Any]:
        """
        Copy files in the MFS.
        
        Args:
            source: Source path
            dest: Destination path
            parents: Whether to create parent directories
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["files", "cp", source, dest]
            
            if parents:
                args.append("--parents")
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in files cp: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_mv(self, source: str, dest: str) -> Dict[str, Any]:
        """
        Move files in the MFS.
        
        Args:
            source: Source path
            dest: Destination path
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["files", "mv", source, dest])
        except Exception as e:
            logger.error(f"Error in files mv: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_files_ls(self, path: str = "/", long: bool = False) -> Dict[str, Any]:
        """
        List files in the MFS.
        
        Args:
            path: Path to list
            long: Whether to use long listing format
            
        Returns:
            Dict with operation result
        """
        try:
            # Construct command arguments
            args = ["files", "ls", path]
            
            if long:
                args.append("--long")
            
            # Execute command
            return await self._execute_ipfs_command(args)
        except Exception as e:
            logger.error(f"Error in files ls: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- Swarm Operations ---
    
    async def ipfs_swarm_peers(self) -> Dict[str, Any]:
        """
        List peers connected to the local node.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["swarm", "peers"])
        except Exception as e:
            logger.error(f"Error in swarm peers: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_swarm_connect(self, address: str) -> Dict[str, Any]:
        """
        Connect to a peer.
        
        Args:
            address: Multiaddress to connect to
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["swarm", "connect", address])
        except Exception as e:
            logger.error(f"Error in swarm connect: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_swarm_disconnect(self, address: str) -> Dict[str, Any]:
        """
        Disconnect from a peer.
        
        Args:
            address: Multiaddress to disconnect from
            
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["swarm", "disconnect", address])
        except Exception as e:
            logger.error(f"Error in swarm disconnect: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_swarm_addrs(self) -> Dict[str, Any]:
        """
        List known addresses.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["swarm", "addrs"])
        except Exception as e:
            logger.error(f"Error in swarm addrs: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_swarm_addrs_local(self) -> Dict[str, Any]:
        """
        List local addresses.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["swarm", "addrs", "local"])
        except Exception as e:
            logger.error(f"Error in swarm addrs local: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- Diagnostic Operations ---
    
    async def ipfs_diag_sys(self) -> Dict[str, Any]:
        """
        Print system diagnostic information.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["diag", "sys"])
        except Exception as e:
            logger.error(f"Error in diag sys: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_stats_bw(self) -> Dict[str, Any]:
        """
        Get bandwidth statistics.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["stats", "bw"])
        except Exception as e:
            logger.error(f"Error in stats bw: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_stats_repo(self) -> Dict[str, Any]:
        """
        Get repository statistics.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["stats", "repo"])
        except Exception as e:
            logger.error(f"Error in stats repo: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    async def ipfs_stats_bitswap(self) -> Dict[str, Any]:
        """
        Get bitswap statistics.
        
        Returns:
            Dict with operation result
        """
        try:
            # Execute command
            return await self._execute_ipfs_command(["stats", "bitswap"])
        except Exception as e:
            logger.error(f"Error in stats bitswap: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSAdvancedBackendError"}
    
    # --- Helper Method ---
    
    async def _execute_ipfs_command(self, args: List[str], parse_json: bool = True) -> Dict[str, Any]:
        """
        Execute an IPFS command.
        
        Args:
            args: Command arguments
            parse_json: Whether to parse the output as JSON
            
        Returns:
            Dict with operation result
        """
        try:
            # First try to use the run_ipfs_command method if available
            if hasattr(self.ipfs, "run_ipfs_command"):
                return await self.ipfs.run_ipfs_command(args)
            
            # Fallback: use subprocess directly (if implemented in the future)
            logger.warning("run_ipfs_command method not available - cannot execute advanced command")
            return {"success": False, "error": "Advanced IPFS operations not supported by this client", "error_type": "NotSupported"}
        except Exception as e:
            logger.error(f"Error executing IPFS command {args}: {e}")
            return {"success": False, "error": str(e), "error_type": "IPFSCommandError"}
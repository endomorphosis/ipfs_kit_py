#!/usr/bin/env python3
"""
Advanced IPFS Operations Extension

This module extends the basic IPFS backend with advanced operations:
- DAG manipulation (get, put, resolve, stat)
- Object manipulation (new, patch, stat)
- Names/IPNS functionality with key management
- Enhanced DHT operations
- Swarm and peer management

This implements the "Advanced IPFS Operations" feature from the MCP Roadmap Phase 1.
"""

import os
import sys
import logging
import json
import time
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, BinaryIO, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ipfs_advanced")

class IPFSAdvancedOperations:
    """Advanced IPFS operations implementation."""
    
    def __init__(self, ipfs_backend=None):
        """
        Initialize the advanced IPFS operations module.
        
        Args:
            ipfs_backend: An instance of IPFSStorageBackend or None to create a new instance
        """
        self.name = "ipfs_advanced"
        self.description = "Advanced IPFS Operations Extension"
        
        # Get or create IPFS backend
        if ipfs_backend is None:
            # Import here to avoid circular imports
            from ipfs_backend import get_instance
            self.backend = get_instance()
        else:
            self.backend = ipfs_backend
        
        # Get direct access to the underlying IPFS implementation
        self.ipfs = self.backend.ipfs
        
        # Performance tracking
        self.performance_stats = {
            # DAG operations
            "dag_get": {"count": 0, "total_time": 0, "avg_time": 0},
            "dag_put": {"count": 0, "total_time": 0, "avg_time": 0},
            "dag_resolve": {"count": 0, "total_time": 0, "avg_time": 0},
            "dag_stat": {"count": 0, "total_time": 0, "avg_time": 0},
            
            # Object operations
            "object_new": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_get": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_put": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_stat": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_links": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_patch_add_link": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_patch_rm_link": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_patch_set_data": {"count": 0, "total_time": 0, "avg_time": 0},
            "object_patch_append_data": {"count": 0, "total_time": 0, "avg_time": 0},
            
            # IPNS/Key operations
            "name_publish": {"count": 0, "total_time": 0, "avg_time": 0},
            "name_resolve": {"count": 0, "total_time": 0, "avg_time": 0},
            "key_gen": {"count": 0, "total_time": 0, "avg_time": 0},
            "key_list": {"count": 0, "total_time": 0, "avg_time": 0},
            "key_rename": {"count": 0, "total_time": 0, "avg_time": 0},
            "key_rm": {"count": 0, "total_time": 0, "avg_time": 0},
            "key_import": {"count": 0, "total_time": 0, "avg_time": 0},
            "key_export": {"count": 0, "total_time": 0, "avg_time": 0},
            
            # Swarm/Network operations
            "swarm_peers": {"count": 0, "total_time": 0, "avg_time": 0},
            "swarm_connect": {"count": 0, "total_time": 0, "avg_time": 0},
            "swarm_disconnect": {"count": 0, "total_time": 0, "avg_time": 0},
            "bootstrap_list": {"count": 0, "total_time": 0, "avg_time": 0},
            "bootstrap_add": {"count": 0, "total_time": 0, "avg_time": 0},
            "bootstrap_rm": {"count": 0, "total_time": 0, "avg_time": 0},
        }
        
        # Initialize and ensure methods exist
        self._ensure_methods()
    
    def _ensure_methods(self):
        """Ensure all needed methods exist in the IPFS implementation."""
        # Check if we're working with a mock
        self.is_mock = getattr(self.ipfs, "_mock_implementation", False)
        
        if self.is_mock:
            logger.warning("Using mock IPFS implementation - limited functionality available")
    
    def _update_stats(self, operation, start_time):
        """Update performance statistics for an operation."""
        duration = time.time() - start_time
        self.performance_stats[operation]["count"] += 1
        self.performance_stats[operation]["total_time"] += duration
        self.performance_stats[operation]["avg_time"] = (
            self.performance_stats[operation]["total_time"] / self.performance_stats[operation]["count"]
        )
    
    # ---- DAG (Directed Acyclic Graph) Operations ----
    
    def dag_get(
        self, 
        cid: str, 
        path: str = "", 
        output_codec: str = "json",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get a DAG node from IPFS.
        
        Args:
            cid: The CID of the DAG node
            path: Path within the DAG to retrieve
            output_codec: Format to output the node in (json, raw, etc.)
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_dag_get"):
            result = self.ipfs.ipfs_dag_get(cid, path=path, output_codec=output_codec)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_dag_get method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("dag_get", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "data": result.get("data"),
                "backend": self.backend.get_name(),
                "identifier": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to get DAG node"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    def dag_put(
        self, 
        data: Union[Dict, List, str, bytes], 
        input_codec: str = "json",
        store_codec: str = "dag-cbor",
        pin: bool = False,
        hash_alg: str = "sha2-256",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Put a DAG node into IPFS.
        
        Args:
            data: The data to store in the DAG
            input_codec: Format of the input data (json, raw, etc.)
            store_codec: Format to store the node in (dag-cbor, dag-json, etc.)
            pin: Whether to pin the added node
            hash_alg: Hash algorithm to use (sha2-256, sha2-512, etc.)
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Convert data if needed
        if isinstance(data, (dict, list)) and input_codec == "json":
            data = json.dumps(data)
        
        if hasattr(self.ipfs, "ipfs_dag_put"):
            result = self.ipfs.ipfs_dag_put(
                data, 
                input_codec=input_codec,
                store_codec=store_codec,
                pin=pin,
                hash_alg=hash_alg
            )
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_dag_put method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("dag_put", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to put DAG node"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def dag_resolve(
        self, 
        path: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolve an IPFS path to a DAG node.
        
        Args:
            path: IPFS path to resolve (e.g., /ipfs/QmXYZ/file)
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_dag_resolve"):
            result = self.ipfs.ipfs_dag_resolve(path)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_dag_resolve method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("dag_resolve", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),
                "remainder_path": result.get("remainder_path", ""),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to resolve DAG path"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def dag_stat(
        self, 
        cid: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get statistics about a DAG node.
        
        Args:
            cid: The CID of the DAG node
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_dag_stat"):
            result = self.ipfs.ipfs_dag_stat(cid)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_dag_stat method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("dag_stat", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "size": result.get("size"),
                "num_blocks": result.get("num_blocks"),
                "backend": self.backend.get_name(),
                "identifier": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to get DAG stats"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    # ---- Object Manipulation ----
    
    def object_new(
        self, 
        template: str = "unixfs-dir",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new IPFS object.
        
        Args:
            template: Template to use (unixfs-dir, etc.)
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_object_new"):
            result = self.ipfs.ipfs_object_new(template)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_new method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_new", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to create new object"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def object_get(
        self, 
        cid: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get an IPFS object.
        
        Args:
            cid: The CID of the object
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_object_get"):
            result = self.ipfs.ipfs_object_get(cid)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_get method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_get", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "data": result.get("data"),
                "links": result.get("links", []),
                "backend": self.backend.get_name(),
                "identifier": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to get object"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    def object_put(
        self, 
        data: Union[Dict, str, bytes], 
        input_codec: str = "json",
        pin: bool = False,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Put data into IPFS as an object.
        
        Args:
            data: The data to store
            input_codec: Format of the input data (json, raw, etc.)
            pin: Whether to pin the added object
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Convert data if needed
        if isinstance(data, dict) and input_codec == "json":
            data = json.dumps(data)
        
        if hasattr(self.ipfs, "ipfs_object_put"):
            result = self.ipfs.ipfs_object_put(data, input_codec=input_codec, pin=pin)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_put method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_put", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to put object"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def object_stat(
        self, 
        cid: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get statistics about an IPFS object.
        
        Args:
            cid: The CID of the object
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        return self.backend.get_stats(cid, options)
    
    def object_links(
        self, 
        cid: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get links from an IPFS object.
        
        Args:
            cid: The CID of the object
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_object_links"):
            result = self.ipfs.ipfs_object_links(cid)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_links method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_links", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "links": result.get("links", []),
                "backend": self.backend.get_name(),
                "identifier": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to get object links"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    def object_patch_add_link(
        self, 
        cid: str, 
        link_name: str, 
        link_cid: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a link to an IPFS object.
        
        Args:
            cid: The CID of the object to modify
            link_name: Name of the link to add
            link_cid: CID that the link points to
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_object_patch_add_link"):
            result = self.ipfs.ipfs_object_patch_add_link(cid, link_name, link_cid)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_patch_add_link method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_patch_add_link", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),  # New CID after the patch
                "backend": self.backend.get_name(),
                "original_cid": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to add link to object"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    def object_patch_rm_link(
        self, 
        cid: str, 
        link_name: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Remove a link from an IPFS object.
        
        Args:
            cid: The CID of the object to modify
            link_name: Name of the link to remove
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_object_patch_rm_link"):
            result = self.ipfs.ipfs_object_patch_rm_link(cid, link_name)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_patch_rm_link method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_patch_rm_link", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),  # New CID after the patch
                "backend": self.backend.get_name(),
                "original_cid": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to remove link from object"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    def object_patch_set_data(
        self, 
        cid: str, 
        data: Union[str, bytes],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Set the data field of an IPFS object.
        
        Args:
            cid: The CID of the object to modify
            data: New data for the object
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_object_patch_set_data"):
            result = self.ipfs.ipfs_object_patch_set_data(cid, data)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_patch_set_data method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_patch_set_data", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),  # New CID after the patch
                "backend": self.backend.get_name(),
                "original_cid": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to set data on object"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    def object_patch_append_data(
        self, 
        cid: str, 
        data: Union[str, bytes],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Append data to an IPFS object.
        
        Args:
            cid: The CID of the object to modify
            data: Data to append
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_object_patch_append_data"):
            result = self.ipfs.ipfs_object_patch_append_data(cid, data)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_object_patch_append_data method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("object_patch_append_data", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "cid": result.get("cid"),  # New CID after the patch
                "backend": self.backend.get_name(),
                "original_cid": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to append data to object"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    # ---- IPNS/Key Management ----
    
    def name_publish(
        self, 
        cid: str, 
        key: str = "self",
        lifetime: str = "24h",
        allow_offline: bool = False,
        ttl: str = "",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Publish a name (IPNS) pointing to an IPFS path.
        
        Args:
            cid: The CID to point to
            key: Name of the key to use (default: "self")
            lifetime: How long the record will be valid for
            allow_offline: Allow publishing when offline
            ttl: Time-to-live for the record
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_name_publish"):
            result = self.ipfs.ipfs_name_publish(
                cid, 
                key=key,
                lifetime=lifetime,
                allow_offline=allow_offline,
                ttl=ttl
            )
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_name_publish method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("name_publish", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "name": result.get("name"),
                "value": result.get("value"),
                "backend": self.backend.get_name(),
                "identifier": cid,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to publish name"),
            "backend": self.backend.get_name(),
            "identifier": cid,
            "details": result,
        }
    
    def name_resolve(
        self, 
        name: str, 
        recursive: bool = True,
        nocache: bool = False,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolve an IPNS name to its IPFS path.
        
        Args:
            name: IPNS name to resolve
            recursive: Resolve through chains of IPNS entries
            nocache: Do not use cached entries
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_name_resolve"):
            result = self.ipfs.ipfs_name_resolve(name, recursive=recursive, nocache=nocache)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_name_resolve method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("name_resolve", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "path": result.get("path"),
                "backend": self.backend.get_name(),
                "name": name,
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to resolve name"),
            "backend": self.backend.get_name(),
            "name": name,
            "details": result,
        }
    
    def key_gen(
        self, 
        name: str, 
        type: str = "rsa",
        size: int = 2048,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a new keypair for IPNS.
        
        Args:
            name: Name of the key
            type: Type of the key (rsa, ed25519, etc.)
            size: Size of the key in bits (for RSA)
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_key_gen"):
            result = self.ipfs.ipfs_key_gen(name, type=type, size=size)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_key_gen method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("key_gen", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "name": result.get("name"),
                "id": result.get("id"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to generate key"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def key_list(
        self, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List all keys.
        
        Args:
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_key_list"):
            result = self.ipfs.ipfs_key_list()
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_key_list method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("key_list", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "keys": result.get("keys", []),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to list keys"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def key_rename(
        self, 
        old_name: str, 
        new_name: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Rename a key.
        
        Args:
            old_name: Current name of the key
            new_name: New name for the key
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_key_rename"):
            result = self.ipfs.ipfs_key_rename(old_name, new_name)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_key_rename method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("key_rename", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "was": result.get("was"),
                "now": result.get("now"),
                "id": result.get("id"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to rename key"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def key_rm(
        self, 
        name: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Remove a key.
        
        Args:
            name: Name of the key to remove
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_key_rm"):
            result = self.ipfs.ipfs_key_rm(name)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_key_rm method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("key_rm", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "name": result.get("name"),
                "id": result.get("id"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to remove key"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def key_import(
        self, 
        name: str, 
        key_data: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Import a key.
        
        Args:
            name: Name for the imported key
            key_data: The key data to import (as a string)
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_key_import"):
            result = self.ipfs.ipfs_key_import(name, key_data)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_key_import method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("key_import", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "name": result.get("name"),
                "id": result.get("id"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to import key"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def key_export(
        self, 
        name: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Export a key.
        
        Args:
            name: Name of the key to export
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_key_export"):
            result = self.ipfs.ipfs_key_export(name)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_key_export method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("key_export", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "name": result.get("name"),
                "key_data": result.get("key_data"),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to export key"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    # ---- Swarm/Network Operations ----
    
    def swarm_peers(
        self, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List peers connected to the IPFS node.
        
        Args:
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_swarm_peers"):
            result = self.ipfs.ipfs_swarm_peers()
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_swarm_peers method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("swarm_peers", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "peers": result.get("peers", []),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to list peers"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def swarm_connect(
        self, 
        address: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Connect to a peer.
        
        Args:
            address: Multiaddr of the peer to connect to
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_swarm_connect"):
            result = self.ipfs.ipfs_swarm_connect(address)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_swarm_connect method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("swarm_connect", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "address": address,
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to connect to peer"),
            "backend": self.backend.get_name(),
            "address": address,
            "details": result,
        }
    
    def swarm_disconnect(
        self, 
        address: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Disconnect from a peer.
        
        Args:
            address: Multiaddr of the peer to disconnect from
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_swarm_disconnect"):
            result = self.ipfs.ipfs_swarm_disconnect(address)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_swarm_disconnect method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("swarm_disconnect", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "address": address,
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to disconnect from peer"),
            "backend": self.backend.get_name(),
            "address": address,
            "details": result,
        }
    
    def bootstrap_list(
        self, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List bootstrap nodes.
        
        Args:
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_bootstrap_list"):
            result = self.ipfs.ipfs_bootstrap_list()
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_bootstrap_list method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("bootstrap_list", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "peers": result.get("peers", []),
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to list bootstrap nodes"),
            "backend": self.backend.get_name(),
            "details": result,
        }
    
    def bootstrap_add(
        self, 
        address: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a bootstrap node.
        
        Args:
            address: Multiaddr of the bootstrap node to add
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_bootstrap_add"):
            result = self.ipfs.ipfs_bootstrap_add(address)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_bootstrap_add method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("bootstrap_add", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "address": address,
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to add bootstrap node"),
            "backend": self.backend.get_name(),
            "address": address,
            "details": result,
        }
    
    def bootstrap_rm(
        self, 
        address: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Remove a bootstrap node.
        
        Args:
            address: Multiaddr of the bootstrap node to remove
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        if hasattr(self.ipfs, "ipfs_bootstrap_rm"):
            result = self.ipfs.ipfs_bootstrap_rm(address)
        else:
            # Fallback if the method doesn't exist
            result = {"success": False, "error": "ipfs_bootstrap_rm method not available", "error_type": "MethodNotAvailable"}
        
        self._update_stats("bootstrap_rm", start_time)
        
        if result.get("success", False):
            return {
                "success": True,
                "address": address,
                "backend": self.backend.get_name(),
                "details": result,
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to remove bootstrap node"),
            "backend": self.backend.get_name(),
            "address": address,
            "details": result,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for advanced operations.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "success": True,
            "stats": self.performance_stats,
            "backend": self.backend.get_name(),
        }

# Singleton instance
_instance = None

def get_instance(ipfs_backend=None):
    """Get or create a singleton instance of the advanced operations module."""
    global _instance
    if _instance is None:
        _instance = IPFSAdvancedOperations(ipfs_backend)
    return _instance
"""
Advanced IPFS Operations Extension for MCP Server.

This extension integrates enhanced IPFS operations with the MCP server,
providing improved connection pooling, DHT operations, IPNS with advanced
key management, and comprehensive DAG manipulation.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

# Import our enhanced IPFS modules
from ipfs_connection_pool import get_connection_pool, IPFSConnectionConfig
from ipfs_dht_operations import get_instance as get_dht_instance
from ipfs_ipns_operations import get_instance as get_ipns_instance, KeyType, KeyProtectionLevel
from ipfs_dag_operations import get_instance as get_dag_instance, IPLDFormat

# Set up logging
logger = logging.getLogger("ipfs_advanced_operations")

class AdvancedIPFSOperations:
    """
    Provides enhanced IPFS functionality for the MCP server.
    
    This class integrates connection pooling, DHT operations, IPNS key management,
    and DAG operations into a unified interface for the MCP server.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the advanced IPFS operations.
        
        Args:
            config: Configuration options
        """
        self.config = config or {}
        
        # Configure connection pool
        connection_config = IPFSConnectionConfig(
            base_url=self.config.get("api_url", "http://127.0.0.1:5001/api/v0"),
            max_connections=self.config.get("max_connections", 10),
            connection_timeout=self.config.get("connection_timeout", 30),
            idle_timeout=self.config.get("idle_timeout", 300),
            max_retries=self.config.get("max_retries", 3),
        )
        
        # Initialize connection pool
        self.connection_pool = get_connection_pool(connection_config)
        
        # Initialize operation modules
        self.dht = get_dht_instance(self.connection_pool, self.config)
        self.ipns = get_ipns_instance(self.connection_pool, self.config)
        self.dag = get_dag_instance(self.connection_pool, self.config)
        
        logger.info("Advanced IPFS Operations initialized")
    
    # --- DHT Operations ---
    
    def dht_provide(
        self, cid: str, recursive: bool = False, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Announce to the network that we are providing the specified content.
        
        Args:
            cid: Content ID to provide
            recursive: Whether to recursively provide the entire DAG
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DHT provide: {cid} (recursive={recursive})")
        return self.dht.provide(cid, recursive, options)
    
    def dht_find_providers(
        self, cid: str, num_providers: int = 20, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Find providers for the specified content.
        
        Args:
            cid: Content ID to find providers for
            num_providers: Maximum number of providers to find
            options: Additional options
            
        Returns:
            Operation result with provider information
        """
        logger.debug(f"DHT find providers: {cid} (num_providers={num_providers})")
        return self.dht.find_providers(cid, num_providers, options)
    
    def dht_find_peer(
        self, peer_id: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Find a peer in the DHT.
        
        Args:
            peer_id: ID of the peer to find
            options: Additional options
            
        Returns:
            Operation result with peer information
        """
        logger.debug(f"DHT find peer: {peer_id}")
        return self.dht.find_peer(peer_id, options)
    
    def dht_query(
        self, peer_id: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Find the closest peers to a peer ID.
        
        Args:
            peer_id: The peer ID to query for
            options: Additional options
            
        Returns:
            Operation result with closest peers
        """
        logger.debug(f"DHT query: {peer_id}")
        return self.dht.query(peer_id, options)
    
    def dht_get_routing_table(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get the local DHT routing table.
        
        Args:
            options: Additional options
            
        Returns:
            Operation result with routing table information
        """
        logger.debug("DHT get routing table")
        return self.dht.get_routing_table(options)
    
    def dht_discover_peers(
        self, bootstrap_peers: Optional[List[str]] = None, max_peers: int = 100, timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Discover peers in the IPFS network.
        
        Args:
            bootstrap_peers: Initial peers to start discovery from
            max_peers: Maximum number of peers to discover
            timeout: Maximum time for discovery in seconds
            
        Returns:
            Operation result with discovered peers
        """
        logger.debug(f"DHT discover peers (max={max_peers}, timeout={timeout}s)")
        return self.dht.discover_peers(bootstrap_peers, max_peers, timeout)
    
    def dht_get_network_diagnostics(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get comprehensive network diagnostics.
        
        Args:
            options: Additional options
            
        Returns:
            Operation result with network diagnostics
        """
        logger.debug("DHT get network diagnostics")
        return self.dht.get_network_diagnostics(options)
    
    # --- IPNS Key Management Operations ---
    
    def list_keys(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        List all available IPNS keys.
        
        Args:
            force_refresh: Whether to force a refresh of the key cache
            
        Returns:
            Operation result with list of keys
        """
        logger.debug("IPNS list keys")
        return self.ipns.key_manager.list_keys(force_refresh)
    
    def get_key(self, name: str) -> Dict[str, Any]:
        """
        Get information about a specific key.
        
        Args:
            name: The name of the key to get
            
        Returns:
            Operation result with key information
        """
        logger.debug(f"IPNS get key: {name}")
        return self.ipns.key_manager.get_key(name)
    
    def create_key(
        self,
        name: str,
        key_type: Union[KeyType, str] = KeyType.ED25519,
        size: int = 2048,
        protection: Union[KeyProtectionLevel, str] = KeyProtectionLevel.STANDARD,
        password: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new IPNS key.
        
        Args:
            name: Name for the new key
            key_type: Type of key to create
            size: Key size (for RSA keys)
            protection: Protection level for the key
            password: Optional password for protected keys
            options: Additional options
            
        Returns:
            Operation result with key information
        """
        logger.debug(f"IPNS create key: {name} (type={key_type})")
        return self.ipns.key_manager.create_key(
            name, key_type, size, protection, password, options
        )
    
    def import_key(
        self,
        name: str,
        private_key: Union[str, bytes],
        format_type: str = "pem",
        protection: Union[KeyProtectionLevel, str] = KeyProtectionLevel.STANDARD,
        password: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Import an existing key for IPNS.
        
        Args:
            name: Name for the imported key
            private_key: Private key data
            format_type: Format of the key
            protection: Protection level for the key
            password: Optional password for protected keys
            options: Additional options
            
        Returns:
            Operation result with key information
        """
        logger.debug(f"IPNS import key: {name}")
        return self.ipns.key_manager.import_key(
            name, private_key, format_type, protection, password, options
        )
    
    def export_key(
        self,
        name: str,
        output_format: str = "pem",
        password: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Export an IPNS key.
        
        Args:
            name: Name of the key to export
            output_format: Format for the exported key
            password: Optional password for protected keys
            options: Additional options
            
        Returns:
            Operation result with the exported key
        """
        logger.debug(f"IPNS export key: {name}")
        return self.ipns.key_manager.export_key(name, output_format, password, options)
    
    def rename_key(
        self,
        old_name: str,
        new_name: str,
        force: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Rename an IPNS key.
        
        Args:
            old_name: Current name of the key
            new_name: New name for the key
            force: Whether to overwrite if new_name already exists
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"IPNS rename key: {old_name} -> {new_name}")
        return self.ipns.key_manager.rename_key(old_name, new_name, force, options)
    
    def remove_key(
        self,
        name: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Remove an IPNS key.
        
        Args:
            name: Name of the key to remove
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"IPNS remove key: {name}")
        return self.ipns.key_manager.remove_key(name, options)
    
    def rotate_key(
        self,
        name: str,
        new_key_type: Optional[Union[KeyType, str]] = None,
        size: Optional[int] = None,
        preserve_old: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Rotate an IPNS key by creating a new one and updating records.
        
        Args:
            name: Name of the key to rotate
            new_key_type: Type for the new key
            size: Size for the new key
            preserve_old: Whether to preserve the old key with a timestamp suffix
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"IPNS rotate key: {name}")
        return self.ipns.key_manager.rotate_key(name, new_key_type, size, preserve_old, options)
    
    # --- IPNS Publishing Operations ---
    
    def publish(
        self,
        cid: str,
        key_name: str = "self",
        lifetime: Optional[str] = None,
        ttl: Optional[str] = None,
        resolve: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Publish an IPNS name.
        
        Args:
            cid: The CID to publish
            key_name: Name of the key to use for publishing
            lifetime: How long the record will be valid
            ttl: Time-to-live for caching
            resolve: Whether to resolve the CID before publishing
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"IPNS publish: {cid} (key={key_name})")
        return self.ipns.publish(cid, key_name, lifetime, ttl, resolve, options)
    
    def resolve(
        self,
        name: str,
        recursive: bool = True,
        dht_record: bool = False,
        nocache: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an IPNS name to its value.
        
        Args:
            name: The IPNS name to resolve
            recursive: Whether to recursively resolve until reaching a non-IPNS result
            dht_record: Whether to fetch the complete DHT record
            nocache: Whether to bypass cache for resolution
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"IPNS resolve: {name}")
        return self.ipns.resolve(name, recursive, dht_record, nocache, options)
    
    def republish(
        self,
        name: str = None,
        key_name: str = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Republish an IPNS record to extend its lifetime.
        
        Args:
            name: The IPNS name to republish
            key_name: Key name to use for republishing
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"IPNS republish: name={name}, key={key_name}")
        return self.ipns.republish(name, key_name, options)
    
    def get_records(
        self,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get all IPNS records published by this node.
        
        Args:
            options: Additional options
            
        Returns:
            Operation result with records
        """
        logger.debug("IPNS get records")
        return self.ipns.get_records(options)
    
    # --- DAG Operations ---
    
    def dag_put(
        self,
        data: Union[Dict[str, Any], List[Any], str, bytes],
        format_type: Union[IPLDFormat, str] = None,
        input_encoding: str = "json",
        pin: bool = True,
        hash_alg: str = "sha2-256",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store data as a DAG node.
        
        Args:
            data: The data to store
            format_type: IPLD format to use
            input_encoding: Encoding of input data if string/bytes
            pin: Whether to pin the node
            hash_alg: Hash algorithm to use
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG put (format={format_type})")
        return self.dag.put(data, format_type, input_encoding, pin, hash_alg, options)
    
    def dag_get(
        self,
        cid: str,
        path: str = "",
        output_format: str = "json",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a DAG node.
        
        Args:
            cid: The CID of the node to retrieve
            path: Optional IPLD path within the node
            output_format: Output format
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG get: {cid} (path={path})")
        return self.dag.get(cid, path, output_format, options)
    
    def dag_resolve(
        self,
        cid_path: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an IPLD path to its CID.
        
        Args:
            cid_path: CID with optional path to resolve
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG resolve: {cid_path}")
        return self.dag.resolve(cid_path, options)
    
    def dag_stat(
        self,
        cid: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get statistics for a DAG node.
        
        Args:
            cid: The CID of the node to get stats for
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG stat: {cid}")
        return self.dag.stat(cid, options)
    
    def dag_import_data(
        self,
        data: Any,
        pin: bool = True,
        format_type: Union[IPLDFormat, str] = None,
        hash_alg: str = "sha2-256",
        input_encoding: str = "auto",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Import data into the DAG.
        
        Args:
            data: The data to import
            pin: Whether to pin the imported data
            format_type: IPLD format to use
            hash_alg: Hash algorithm to use
            input_encoding: How to interpret the input
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug("DAG import data")
        return self.dag.import_data(data, pin, format_type, hash_alg, input_encoding, options)
    
    def dag_export_data(
        self,
        cid: str,
        output_file: Optional[Union[str, Any]] = None,
        progress: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Export a DAG to a CAR file or stream.
        
        Args:
            cid: The root CID to export
            output_file: Optional output file path or file-like object
            progress: Whether to include progress information
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG export data: {cid}")
        return self.dag.export_data(cid, output_file, progress, options)
    
    def dag_create_tree(
        self,
        data: Dict[str, Any],
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a tree structure in the DAG.
        
        Args:
            data: The hierarchical data to store
            format_type: IPLD format to use
            pin: Whether to pin the nodes
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug("DAG create tree")
        return self.dag.create_tree(data, format_type, pin, options)
    
    def dag_get_tree(
        self,
        cid: str,
        max_depth: int = -1,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a complete tree structure from the DAG.
        
        Args:
            cid: The root CID of the tree
            max_depth: Maximum depth to traverse
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG get tree: {cid}")
        return self.dag.get_tree(cid, max_depth, options)
    
    def dag_update_node(
        self,
        cid: str,
        updates: Dict[str, Any],
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update a DAG node with new values.
        
        Args:
            cid: The CID of the node to update
            updates: Dictionary of key-value pairs to update
            format_type: IPLD format to use for the new node
            pin: Whether to pin the new node
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG update node: {cid}")
        return self.dag.update_node(cid, updates, format_type, pin, options)
    
    def dag_add_link(
        self,
        parent_cid: str,
        name: str,
        child_cid: str,
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a link from a parent node to a child node.
        
        Args:
            parent_cid: The CID of the parent node
            name: The name for the link
            child_cid: The CID of the child node to link to
            format_type: IPLD format to use for the new parent
            pin: Whether to pin the new parent
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG add link: {parent_cid} -> {child_cid} (name={name})")
        return self.dag.add_link(parent_cid, name, child_cid, format_type, pin, options)
    
    def dag_remove_link(
        self,
        parent_cid: str,
        name: str,
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Remove a link from a parent node.
        
        Args:
            parent_cid: The CID of the parent node
            name: The name of the link to remove
            format_type: IPLD format to use for the new parent
            pin: Whether to pin the new parent
            options: Additional options
            
        Returns:
            Operation result
        """
        logger.debug(f"DAG remove link: {parent_cid} (name={name})")
        return self.dag.remove_link(parent_cid, name, format_type, pin, options)
    
    # --- Metrics Operations ---
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all IPFS operation categories.
        
        Returns:
            Dictionary with metrics for all operation types
        """
        logger.debug("Getting metrics for all operations")
        
        # Get metrics from each component
        dht_metrics = self.dht.get_metrics()
        ipns_metrics = self.ipns.get_metrics()
        dag_metrics = self.dag.get_metrics()
        
        # Combine metrics
        return {
            "success": True,
            "timestamp": time.time(),
            "metrics": {
                "dht": dht_metrics.get("metrics", {}),
                "ipns": ipns_metrics.get("metrics", {}),
                "ipns_key": ipns_metrics.get("key_metrics", {}),
                "dag": dag_metrics.get("metrics", {}),
            },
        }
    
    def shutdown(self):
        """
        Clean shutdown of all components.
        """
        logger.info("Shutting down Advanced IPFS Operations")
        self.connection_pool.shutdown()

# Singleton instance
_instance = None

def get_instance(config: Optional[Dict[str, Any]] = None) -> AdvancedIPFSOperations:
    """
    Get or create singleton instance of AdvancedIPFSOperations.
    
    Args:
        config: Optional configuration options
        
    Returns:
        AdvancedIPFSOperations instance
    """
    global _instance
    
    if _instance is None:
        _instance = AdvancedIPFSOperations(config)
    
    return _instance
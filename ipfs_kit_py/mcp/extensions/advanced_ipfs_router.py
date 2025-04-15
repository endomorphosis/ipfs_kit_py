"""
Advanced IPFS Operations Router for MCP Server.

This module provides API endpoints for the enhanced IPFS functionality,
including connection pooling, DHT operations, IPNS key management,
and comprehensive DAG manipulation.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Path, Query, File, UploadFile, Form, Response, HTTPException
from pydantic import BaseModel, Field

# Import our Advanced IPFS Operations extension
from ipfs_kit_py.mcp.extensions.advanced_ipfs_operations import (
    get_instance as get_advanced_ipfs,
    KeyType,
    KeyProtectionLevel,
    IPLDFormat,
)

# Set up logging
logger = logging.getLogger("advanced_ipfs_router")

# ------- Pydantic Models for Request/Response -------

# DHT Models
class DHTProvideRequest(BaseModel):
    """Request model for providing content in DHT."""
    cid: str = Field(..., description="Content ID to provide")
    recursive: bool = Field(False, description="Whether to recursively provide the entire DAG")


class DHTFindProvidersRequest(BaseModel):
    """Request model for finding providers in DHT."""
    cid: str = Field(..., description="Content ID to find providers for")
    num_providers: int = Field(20, description="Maximum number of providers to find")


class DHTFindPeerRequest(BaseModel):
    """Request model for finding a peer in DHT."""
    peer_id: str = Field(..., description="ID of the peer to find")


class DHTQueryRequest(BaseModel):
    """Request model for querying the DHT."""
    peer_id: str = Field(..., description="Peer ID to query for")


class DHTDiscoverPeersRequest(BaseModel):
    """Request model for discovering peers in the network."""
    bootstrap_peers: Optional[List[str]] = Field(None, description="Initial peers to start discovery from")
    max_peers: int = Field(100, description="Maximum number of peers to discover")
    timeout: int = Field(60, description="Maximum time for discovery in seconds")


# IPNS Key Management Models
class CreateKeyRequest(BaseModel):
    """Request model for creating an IPNS key."""
    name: str = Field(..., description="Name for the new key")
    key_type: str = Field("ed25519", description="Type of key to create (rsa, ed25519, secp256k1)")
    size: int = Field(2048, description="Key size (for RSA keys)")
    protection: str = Field("standard", description="Protection level (standard, protected, hardware)")
    password: Optional[str] = Field(None, description="Password for protected keys")


class ImportKeyRequest(BaseModel):
    """Request model for importing an IPNS key."""
    name: str = Field(..., description="Name for the imported key")
    private_key: str = Field(..., description="Private key data (base64 encoded)")
    format_type: str = Field("pem", description="Format of the key (pem, raw)")
    protection: str = Field("standard", description="Protection level (standard, protected, hardware)")
    password: Optional[str] = Field(None, description="Password for protected keys")


class ExportKeyRequest(BaseModel):
    """Request model for exporting an IPNS key."""
    name: str = Field(..., description="Name of the key to export")
    output_format: str = Field("pem", description="Format for the exported key (pem, raw)")
    password: Optional[str] = Field(None, description="Password for protected keys")


class RenameKeyRequest(BaseModel):
    """Request model for renaming an IPNS key."""
    old_name: str = Field(..., description="Current name of the key")
    new_name: str = Field(..., description="New name for the key")
    force: bool = Field(False, description="Whether to overwrite if new_name already exists")


class RemoveKeyRequest(BaseModel):
    """Request model for removing an IPNS key."""
    name: str = Field(..., description="Name of the key to remove")


class RotateKeyRequest(BaseModel):
    """Request model for rotating an IPNS key."""
    name: str = Field(..., description="Name of the key to rotate")
    new_key_type: Optional[str] = Field(None, description="Type for the new key")
    size: Optional[int] = Field(None, description="Size for the new key")
    preserve_old: bool = Field(True, description="Whether to preserve the old key with a timestamp suffix")


# IPNS Publishing Models
class PublishRequest(BaseModel):
    """Request model for publishing an IPNS name."""
    cid: str = Field(..., description="The CID to publish")
    key_name: str = Field("self", description="Name of the key to use for publishing")
    lifetime: Optional[str] = Field(None, description="How long the record will be valid (e.g., '24h')")
    ttl: Optional[str] = Field(None, description="Time-to-live for caching (e.g., '1h')")
    resolve: bool = Field(True, description="Whether to resolve the CID before publishing")


class ResolveRequest(BaseModel):
    """Request model for resolving an IPNS name."""
    name: str = Field(..., description="The IPNS name to resolve")
    recursive: bool = Field(True, description="Whether to recursively resolve until reaching a non-IPNS result")
    dht_record: bool = Field(False, description="Whether to fetch the complete DHT record")
    nocache: bool = Field(False, description="Whether to bypass cache for resolution")


class RepublishRequest(BaseModel):
    """Request model for republishing an IPNS record."""
    name: Optional[str] = Field(None, description="The IPNS name to republish")
    key_name: Optional[str] = Field(None, description="Key name to use for republishing")


# DAG Operation Models
class DAGPutRequest(BaseModel):
    """Request model for storing a DAG node."""
    data: Any = Field(..., description="The data to store")
    format_type: str = Field("dag-json", description="IPLD format to use")
    input_encoding: str = Field("json", description="Encoding of input data if string/bytes")
    pin: bool = Field(True, description="Whether to pin the node")
    hash_alg: str = Field("sha2-256", description="Hash algorithm to use")


class DAGGetRequest(BaseModel):
    """Request model for retrieving a DAG node."""
    cid: str = Field(..., description="The CID of the node to retrieve")
    path: str = Field("", description="Optional IPLD path within the node")
    output_format: str = Field("json", description="Output format (json, raw, cbor)")


class DAGResolveRequest(BaseModel):
    """Request model for resolving an IPLD path."""
    cid_path: str = Field(..., description="CID with optional path to resolve")


class DAGUpdateNodeRequest(BaseModel):
    """Request model for updating a DAG node."""
    cid: str = Field(..., description="The CID of the node to update")
    updates: Dict[str, Any] = Field(..., description="Dictionary of key-value pairs to update")
    format_type: str = Field("dag-json", description="IPLD format to use for the new node")
    pin: bool = Field(True, description="Whether to pin the new node")


class DAGAddLinkRequest(BaseModel):
    """Request model for adding a link to a DAG node."""
    parent_cid: str = Field(..., description="The CID of the parent node")
    name: str = Field(..., description="The name for the link")
    child_cid: str = Field(..., description="The CID of the child node to link to")
    format_type: str = Field("dag-json", description="IPLD format to use for the new parent")
    pin: bool = Field(True, description="Whether to pin the new parent")


class DAGRemoveLinkRequest(BaseModel):
    """Request model for removing a link from a DAG node."""
    parent_cid: str = Field(..., description="The CID of the parent node")
    name: str = Field(..., description="The name of the link to remove")
    format_type: str = Field("dag-json", description="IPLD format to use for the new parent")
    pin: bool = Field(True, description="Whether to pin the new parent")


# General Response Model
class BaseResponse(BaseModel):
    """Base response model for all operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: str = Field(..., description="Unique identifier for the operation")
    duration_ms: float = Field(..., description="Duration of the operation in milliseconds")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    error_type: Optional[str] = Field(None, description="Type of error if operation failed")


class AdvancedIPFSRouter:
    """
    Router for advanced IPFS operations.
    
    This class provides FastAPI routes for the enhanced IPFS functionality.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the advanced IPFS router.
        
        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.advanced_ipfs = get_advanced_ipfs(self.config)
        logger.info("Advanced IPFS Router initialized")
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # ----- DHT Operation Routes -----
        
        router.add_api_route(
            "/ipfs/advanced/dht/provide",
            self.dht_provide,
            methods=["POST"],
            summary="Announce content to the DHT",
            description="Announce to the network that we are providing the specified content",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dht/findprovs",
            self.dht_find_providers,
            methods=["POST"],
            summary="Find providers for content",
            description="Find providers for the specified content in the DHT",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dht/findpeer",
            self.dht_find_peer,
            methods=["POST"],
            summary="Find a peer in the DHT",
            description="Find information about a peer in the DHT",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dht/query",
            self.dht_query,
            methods=["POST"],
            summary="Query the DHT",
            description="Find the closest peers to a peer ID",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dht/routing-table",
            self.dht_get_routing_table,
            methods=["GET"],
            summary="Get DHT routing table",
            description="Get the local DHT routing table",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dht/discover-peers",
            self.dht_discover_peers,
            methods=["POST"],
            summary="Discover peers in the network",
            description="Discover peers in the IPFS network through DHT",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dht/diagnostics",
            self.dht_get_network_diagnostics,
            methods=["GET"],
            summary="Get network diagnostics",
            description="Get comprehensive network diagnostics through DHT",
        )
        
        # ----- IPNS Key Management Routes -----
        
        router.add_api_route(
            "/ipfs/advanced/key/list",
            self.list_keys,
            methods=["GET"],
            summary="List IPNS keys",
            description="List all available IPNS keys",
        )
        
        router.add_api_route(
            "/ipfs/advanced/key/get/{name}",
            self.get_key,
            methods=["GET"],
            summary="Get IPNS key info",
            description="Get information about a specific IPNS key",
        )
        
        router.add_api_route(
            "/ipfs/advanced/key/create",
            self.create_key,
            methods=["POST"],
            summary="Create IPNS key",
            description="Create a new IPNS key",
        )
        
        router.add_api_route(
            "/ipfs/advanced/key/import",
            self.import_key,
            methods=["POST"],
            summary="Import IPNS key",
            description="Import an existing key for IPNS",
        )
        
        router.add_api_route(
            "/ipfs/advanced/key/export",
            self.export_key,
            methods=["POST"],
            summary="Export IPNS key",
            description="Export an IPNS key",
        )
        
        router.add_api_route(
            "/ipfs/advanced/key/rename",
            self.rename_key,
            methods=["POST"],
            summary="Rename IPNS key",
            description="Rename an IPNS key",
        )
        
        router.add_api_route(
            "/ipfs/advanced/key/remove",
            self.remove_key,
            methods=["POST"],
            summary="Remove IPNS key",
            description="Remove an IPNS key",
        )
        
        router.add_api_route(
            "/ipfs/advanced/key/rotate",
            self.rotate_key,
            methods=["POST"],
            summary="Rotate IPNS key",
            description="Rotate an IPNS key by creating a new one and updating records",
        )
        
        # ----- IPNS Publishing Routes -----
        
        router.add_api_route(
            "/ipfs/advanced/name/publish",
            self.publish,
            methods=["POST"],
            summary="Publish IPNS name",
            description="Publish an IPNS name pointing to the specified CID",
        )
        
        router.add_api_route(
            "/ipfs/advanced/name/resolve",
            self.resolve,
            methods=["POST"],
            summary="Resolve IPNS name",
            description="Resolve an IPNS name to its value",
        )
        
        router.add_api_route(
            "/ipfs/advanced/name/republish",
            self.republish,
            methods=["POST"],
            summary="Republish IPNS record",
            description="Republish an IPNS record to extend its lifetime",
        )
        
        router.add_api_route(
            "/ipfs/advanced/name/records",
            self.get_records,
            methods=["GET"],
            summary="Get IPNS records",
            description="Get all IPNS records published by this node",
        )
        
        # ----- DAG Operation Routes -----
        
        router.add_api_route(
            "/ipfs/advanced/dag/put",
            self.dag_put,
            methods=["POST"],
            summary="Store a DAG node",
            description="Store data as a DAG node",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/get",
            self.dag_get,
            methods=["POST"],
            summary="Retrieve a DAG node",
            description="Retrieve a DAG node by CID with optional path",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/resolve",
            self.dag_resolve,
            methods=["POST"],
            summary="Resolve IPLD path",
            description="Resolve an IPLD path to its CID",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/stat/{cid}",
            self.dag_stat,
            methods=["GET"],
            summary="Get DAG node stats",
            description="Get statistics for a DAG node",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/import",
            self.dag_import_data,
            methods=["POST"],
            summary="Import data to DAG",
            description="Import data into the DAG",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/export/{cid}",
            self.dag_export_data,
            methods=["GET"],
            summary="Export DAG as CAR",
            description="Export a DAG to a CAR file",
            response_class=Response,
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/tree",
            self.dag_create_tree,
            methods=["POST"],
            summary="Create DAG tree",
            description="Create a tree structure in the DAG",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/get-tree/{cid}",
            self.dag_get_tree,
            methods=["GET"],
            summary="Get DAG tree",
            description="Retrieve a complete tree structure from the DAG",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/update",
            self.dag_update_node,
            methods=["POST"],
            summary="Update DAG node",
            description="Update a DAG node with new values",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/add-link",
            self.dag_add_link,
            methods=["POST"],
            summary="Add link to DAG node",
            description="Add a link from a parent node to a child node",
        )
        
        router.add_api_route(
            "/ipfs/advanced/dag/remove-link",
            self.dag_remove_link,
            methods=["POST"],
            summary="Remove link from DAG node",
            description="Remove a link from a parent node",
        )
        
        # ----- Metrics Routes -----
        
        router.add_api_route(
            "/ipfs/advanced/metrics",
            self.get_metrics,
            methods=["GET"],
            summary="Get metrics",
            description="Get metrics for all IPFS operation categories",
        )
        
        logger.info("Advanced IPFS Router routes registered")
    
    # ----- DHT Operation Handlers -----
    
    async def dht_provide(self, request: DHTProvideRequest) -> Dict[str, Any]:
        """
        Announce to the network that we are providing the specified content.
        
        Args:
            request: Request with CID and options
            
        Returns:
            Operation result
        """
        operation_id = f"dht_provide_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dht_provide(
                request.cid,
                request.recursive,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dht_provide: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dht_find_providers(self, request: DHTFindProvidersRequest) -> Dict[str, Any]:
        """
        Find providers for the specified content in the DHT.
        
        Args:
            request: Request with CID and options
            
        Returns:
            Operation result with provider information
        """
        operation_id = f"dht_find_providers_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dht_find_providers(
                request.cid,
                request.num_providers,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dht_find_providers: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dht_find_peer(self, request: DHTFindPeerRequest) -> Dict[str, Any]:
        """
        Find a peer in the DHT.
        
        Args:
            request: Request with peer ID
            
        Returns:
            Operation result with peer information
        """
        operation_id = f"dht_find_peer_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dht_find_peer(
                request.peer_id,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dht_find_peer: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dht_query(self, request: DHTQueryRequest) -> Dict[str, Any]:
        """
        Find the closest peers to a peer ID.
        
        Args:
            request: Request with peer ID
            
        Returns:
            Operation result with closest peers
        """
        operation_id = f"dht_query_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dht_query(
                request.peer_id,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dht_query: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dht_get_routing_table(self) -> Dict[str, Any]:
        """
        Get the local DHT routing table.
        
        Returns:
            Operation result with routing table information
        """
        operation_id = f"dht_get_routing_table_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dht_get_routing_table()
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dht_get_routing_table: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dht_discover_peers(self, request: DHTDiscoverPeersRequest) -> Dict[str, Any]:
        """
        Discover peers in the IPFS network.
        
        Args:
            request: Request with discovery options
            
        Returns:
            Operation result with discovered peers
        """
        operation_id = f"dht_discover_peers_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dht_discover_peers(
                request.bootstrap_peers,
                request.max_peers,
                request.timeout,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dht_discover_peers: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dht_get_network_diagnostics(self) -> Dict[str, Any]:
        """
        Get comprehensive network diagnostics.
        
        Returns:
            Operation result with network diagnostics
        """
        operation_id = f"dht_get_network_diagnostics_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dht_get_network_diagnostics()
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dht_get_network_diagnostics: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    # ----- IPNS Key Management Handlers -----
    
    async def list_keys(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        List all available IPNS keys.
        
        Args:
            force_refresh: Whether to force a refresh of the key cache
            
        Returns:
            Operation result with list of keys
        """
        operation_id = f"list_keys_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.list_keys(force_refresh)
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in list_keys: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def get_key(self, name: str) -> Dict[str, Any]:
        """
        Get information about a specific key.
        
        Args:
            name: The name of the key to get
            
        Returns:
            Operation result with key information
        """
        operation_id = f"get_key_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.get_key(name)
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in get_key: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def create_key(self, request: CreateKeyRequest) -> Dict[str, Any]:
        """
        Create a new IPNS key.
        
        Args:
            request: Request with key creation options
            
        Returns:
            Operation result with key information
        """
        operation_id = f"create_key_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.create_key(
                request.name,
                request.key_type,
                request.size,
                request.protection,
                request.password,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in create_key: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def import_key(self, request: ImportKeyRequest) -> Dict[str, Any]:
        """
        Import an existing key for IPNS.
        
        Args:
            request: Request with key import options
            
        Returns:
            Operation result with key information
        """
        operation_id = f"import_key_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.import_key(
                request.name,
                request.private_key,
                request.format_type,
                request.protection,
                request.password,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in import_key: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def export_key(self, request: ExportKeyRequest) -> Dict[str, Any]:
        """
        Export an IPNS key.
        
        Args:
            request: Request with key export options
            
        Returns:
            Operation result with the exported key
        """
        operation_id = f"export_key_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.export_key(
                request.name,
                request.output_format,
                request.password,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in export_key: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def rename_key(self, request: RenameKeyRequest) -> Dict[str, Any]:
        """
        Rename an IPNS key.
        
        Args:
            request: Request with key rename options
            
        Returns:
            Operation result
        """
        operation_id = f"rename_key_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.rename_key(
                request.old_name,
                request.new_name,
                request.force,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in rename_key: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def remove_key(self, request: RemoveKeyRequest) -> Dict[str, Any]:
        """
        Remove an IPNS key.
        
        Args:
            request: Request with key removal options
            
        Returns:
            Operation result
        """
        operation_id = f"remove_key_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.remove_key(
                request.name,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in remove_key: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def rotate_key(self, request: RotateKeyRequest) -> Dict[str, Any]:
        """
        Rotate an IPNS key by creating a new one and updating records.
        
        Args:
            request: Request with key rotation options
            
        Returns:
            Operation result
        """
        operation_id = f"rotate_key_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.rotate_key(
                request.name,
                request.new_key_type,
                request.size,
                request.preserve_old,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in rotate_key: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    # ----- IPNS Publishing Handlers -----
    
    async def publish(self, request: PublishRequest) -> Dict[str, Any]:
        """
        Publish an IPNS name.
        
        Args:
            request: Request with publishing options
            
        Returns:
            Operation result
        """
        operation_id = f"publish_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.publish(
                request.cid,
                request.key_name,
                request.lifetime,
                request.ttl,
                request.resolve,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in publish: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def resolve(self, request: ResolveRequest) -> Dict[str, Any]:
        """
        Resolve an IPNS name to its value.
        
        Args:
            request: Request with resolution options
            
        Returns:
            Operation result
        """
        operation_id = f"resolve_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.resolve(
                request.name,
                request.recursive,
                request.dht_record,
                request.nocache,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in resolve: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def republish(self, request: RepublishRequest) -> Dict[str, Any]:
        """
        Republish an IPNS record to extend its lifetime.
        
        Args:
            request: Request with republishing options
            
        Returns:
            Operation result
        """
        operation_id = f"republish_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.republish(
                request.name,
                request.key_name,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in republish: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def get_records(self) -> Dict[str, Any]:
        """
        Get all IPNS records published by this node.
        
        Returns:
            Operation result with records
        """
        operation_id = f"get_records_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.get_records()
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in get_records: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    # ----- DAG Operation Handlers -----
    
    async def dag_put(self, request: DAGPutRequest) -> Dict[str, Any]:
        """
        Store data as a DAG node.
        
        Args:
            request: Request with DAG node creation options
            
        Returns:
            Operation result
        """
        operation_id = f"dag_put_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_put(
                request.data,
                request.format_type,
                request.input_encoding,
                request.pin,
                request.hash_alg,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_put: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_get(self, request: DAGGetRequest) -> Dict[str, Any]:
        """
        Retrieve a DAG node.
        
        Args:
            request: Request with DAG node retrieval options
            
        Returns:
            Operation result
        """
        operation_id = f"dag_get_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_get(
                request.cid,
                request.path,
                request.output_format,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_get: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_resolve(self, request: DAGResolveRequest) -> Dict[str, Any]:
        """
        Resolve an IPLD path to its CID.
        
        Args:
            request: Request with path resolution options
            
        Returns:
            Operation result
        """
        operation_id = f"dag_resolve_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_resolve(
                request.cid_path,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_resolve: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_stat(self, cid: str) -> Dict[str, Any]:
        """
        Get statistics for a DAG node.
        
        Args:
            cid: The CID of the node to get stats for
            
        Returns:
            Operation result
        """
        operation_id = f"dag_stat_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_stat(cid)
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_stat: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_import_data(self, data: Any = Body(...)) -> Dict[str, Any]:
        """
        Import data into the DAG.
        
        Args:
            data: The data to import
            
        Returns:
            Operation result
        """
        operation_id = f"dag_import_data_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_import_data(data)
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_import_data: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_export_data(self, cid: str, download: bool = False) -> Response:
        """
        Export a DAG to a CAR file.
        
        Args:
            cid: The root CID to export
            download: Whether to download as attachment
            
        Returns:
            CAR file as response
        """
        operation_id = f"dag_export_data_{int(time.time() * 1000)}"
        
        try:
            # Export to memory
            result = self.advanced_ipfs.dag_export_data(cid)
            
            if not result.get("success", False):
                # Return error as JSON
                return Response(
                    content=json.dumps({
                        "success": False,
                        "operation_id": operation_id,
                        "error": result.get("error", "Failed to export DAG"),
                    }),
                    media_type="application/json",
                )
            
            # Get the data
            data = result.get("data")
            
            # Set content disposition based on download flag
            content_disposition = "attachment" if download else "inline"
            filename = f"{cid}.car"
            
            # Return CAR file
            return Response(
                content=data,
                media_type="application/vnd.ipld.car",
                headers={
                    "Content-Disposition": f'{content_disposition}; filename="{filename}"',
                    "X-IPFS-DAG": cid,
                    "X-Operation-ID": operation_id,
                    "X-Content-Size": str(len(data)),
                },
            )
        except Exception as e:
            logger.error(f"Error in dag_export_data: {e}")
            # Return error as JSON
            return Response(
                content=json.dumps({
                    "success": False,
                    "operation_id": operation_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }),
                media_type="application/json",
            )
    
    async def dag_create_tree(self, data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        """
        Create a tree structure in the DAG.
        
        Args:
            data: The hierarchical data to store
            
        Returns:
            Operation result
        """
        operation_id = f"dag_create_tree_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_create_tree(data)
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_create_tree: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_get_tree(self, cid: str, max_depth: int = -1) -> Dict[str, Any]:
        """
        Retrieve a complete tree structure from the DAG.
        
        Args:
            cid: The root CID of the tree
            max_depth: Maximum depth to traverse
            
        Returns:
            Operation result
        """
        operation_id = f"dag_get_tree_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_get_tree(cid, max_depth)
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_get_tree: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_update_node(self, request: DAGUpdateNodeRequest) -> Dict[str, Any]:
        """
        Update a DAG node with new values.
        
        Args:
            request: Request with update options
            
        Returns:
            Operation result
        """
        operation_id = f"dag_update_node_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_update_node(
                request.cid,
                request.updates,
                request.format_type,
                request.pin,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_update_node: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_add_link(self, request: DAGAddLinkRequest) -> Dict[str, Any]:
        """
        Add a link from a parent node to a child node.
        
        Args:
            request: Request with add link options
            
        Returns:
            Operation result
        """
        operation_id = f"dag_add_link_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_add_link(
                request.parent_cid,
                request.name,
                request.child_cid,
                request.format_type,
                request.pin,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_add_link: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def dag_remove_link(self, request: DAGRemoveLinkRequest) -> Dict[str, Any]:
        """
        Remove a link from a parent node.
        
        Args:
            request: Request with remove link options
            
        Returns:
            Operation result
        """
        operation_id = f"dag_remove_link_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.dag_remove_link(
                request.parent_cid,
                request.name,
                request.format_type,
                request.pin,
            )
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in dag_remove_link: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    # ----- Metrics Handlers -----
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all IPFS operation categories.
        
        Returns:
            Dictionary with metrics for all operation types
        """
        operation_id = f"get_metrics_{int(time.time() * 1000)}"
        
        try:
            # Call advanced IPFS operations
            result = self.advanced_ipfs.get_metrics()
            
            # Add operation ID
            if "operation_id" not in result:
                result["operation_id"] = operation_id
            
            return result
        except Exception as e:
            logger.error(f"Error in get_metrics: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": 0,
                "error": str(e),
                "error_type": type(e).__name__,
            }

# Function to create and configure the router
def create_router(config: Optional[Dict[str, Any]] = None) -> APIRouter:
    """
    Create and configure an APIRouter for advanced IPFS operations.
    
    Args:
        config: Configuration options
        
    Returns:
        Configured FastAPI router
    """
    router = APIRouter(tags=["IPFS Advanced"])
    router_handler = AdvancedIPFSRouter(config)
    router_handler.register_routes(router)
    return router
"""
IPFS Controller for the MCP server.

This controller provides an interface to the IPFS functionality through the MCP API.
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
    Request,
    Path,
    Query
)
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

# Import error handling
import ipfs_kit_py.mcp_error_handling as mcp_error_handling

# Import IPFS extensions
try:
    from ipfs_kit_py.mcp.ipfs_extensions import (
        add_content, cat, pin_add, pin_rm, pin_ls,
        get_version, files_ls, files_mkdir, files_write, files_read
    )
    logger.info("Successfully imported IPFS extensions")
except ImportError as e:
    logger.warning(f"Failed to import IPFS extensions: {e}")


# --- Swarm Operation Models ---
class PeerAddressRequest(BaseModel):
    """Request model for a peer address."""
    peer_addr: str


class SwarmPeersResponse(BaseModel):
    """Response model for swarm peers request."""
    success: bool
    peers: Optional[List[Dict[str, Any]]] = None
    peer_count: Optional[int] = None
    operation: str
    timestamp: float
    duration_ms: float
    error: Optional[str] = None
    error_type: Optional[str] = None
    simulated: Optional[bool] = None  # Added based on model implementation


class SwarmConnectResponse(BaseModel):
    """Response model for swarm connect request."""
    success: bool
    connected: Optional[bool] = None
    peer: Optional[str] = None
    operation: str
    timestamp: float
    duration_ms: float
    error: Optional[str] = None
    error_type: Optional[str] = None
    simulated: Optional[bool] = None  # Added based on model implementation


class SwarmDisconnectResponse(BaseModel):
    """Response model for swarm disconnect request."""
    success: bool
    disconnected: Optional[bool] = None
    peer: Optional[str] = None
    operation: str
    timestamp: float
    duration_ms: float
    error: Optional[str] = None
    error_type: Optional[str] = None
    simulated: Optional[bool] = None  # Added based on model implementation


# --- End Swarm Operation Models ---


# Define Pydantic models for requests and responses (Existing models follow)
class ContentRequest(BaseModel):
    """Request model for adding content."""
    content: str = Field(..., description="Content to add to IPFS")
    filename: Optional[str] = Field(None, description="Optional filename for the content")


class CIDRequest(BaseModel):
    """Request model for operations using a CID."""
    cid: str = Field(..., description="Content Identifier (CID)")


class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: str = Field(..., description="Unique identifier for this operation")
    duration_ms: float = Field(..., description="Duration of the operation in milliseconds")


class AddContentResponse(OperationResponse):
    """Response model for adding content."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID) of the added content")
    Hash: Optional[str] = Field(None, description="Legacy Hash field for compatibility")
    content_size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")


class GetContentResponse(OperationResponse):
    """Response model for getting content."""
    cid: str = Field(..., description="Content Identifier (CID) of the content")
    data: Optional[bytes] = Field(None, description="Content data")
    content_size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")
    cache_hit: Optional[bool] = Field(
        None, description="Whether the content was retrieved from cache"
    )


class PinResponse(OperationResponse):
    """Response model for pin operations."""
    cid: str = Field(..., description="Content Identifier (CID) of the pinned content")


class FilesLsRequest(BaseModel):
    """Request model for listing files in MFS."""
    path: str = Field("/", description="Path to list in MFS")
    long: bool = Field(False, description="Show detailed file information")


class FilesMkdirRequest(BaseModel):
    """Request model for creating a directory in MFS."""
    path: str = Field(..., description="Path of the directory to create")
    parents: bool = Field(False, description="Create parent directories if they don't exist")
    flush: bool = Field(True, description="Flush changes to disk immediately")


class FilesStatRequest(BaseModel):
    """Request model for getting file stats in MFS."""
    path: str = Field(..., description="Path of the file/directory to stat")


class FilesWriteRequest(BaseModel):
    """Request model for writing to a file in MFS."""
    path: str = Field(..., description="Path of the file to write to")
    content: str = Field(..., description="Content to write")
    create: bool = Field(True, description="Create the file if it doesn't exist")
    truncate: bool = Field(True, description="Truncate the file before writing")
    offset: int = Field(0, description="Offset to start writing at")
    flush: bool = Field(True, description="Flush changes to disk immediately")


class FilesReadRequest(BaseModel):
    """Request model for reading a file from MFS."""
    path: str = Field(..., description="Path of the file to read")
    offset: int = Field(0, description="Offset to start reading from")
    count: Optional[int] = Field(None, description="Number of bytes to read")


class FilesRmRequest(BaseModel):
    """Request model for removing a file/directory from MFS."""
    path: str = Field(..., description="Path of the file/directory to remove")
    recursive: bool = Field(False, description="Remove directories recursively")
    force: bool = Field(False, description="Force removal")
    pinned: Optional[bool] = Field(None, description="Whether the content is now pinned")


class ListPinsResponse(OperationResponse):
    """Response model for listing pins."""
    pins: Optional[List[Dict[str, Any]]] = Field(None, description="List of pinned content")
    count: Optional[int] = Field(None, description="Number of pinned items")


class ReplicationStatusResponse(OperationResponse):
    """Response model for replication status."""
    cid: str = Field(..., description="Content Identifier (CID)")
    replication: Dict[str, Any] = Field(..., description="Replication status details")
    needs_replication: bool = Field(
        ..., description="Whether the content needs additional replication"
    )


class MakeDirRequest(BaseModel):
    """Request model for creating a directory in MFS."""
    path: str = Field(..., description="Path in MFS to create")
    parents: bool = Field(
        False, description="Whether to create parent directories if they don't exist"
    )


class StatsResponse(BaseModel):
    """Response model for operation statistics."""
    operation_stats: Dict[str, Any] = Field(..., description="Operation statistics")
    timestamp: float = Field(..., description="Timestamp of the statistics")
    success: bool = Field(..., description="Whether the operation was successful")
    # These fields are still required for API compatibility with newer clients
    model_operation_stats: Optional[Dict[str, Any]] = Field(
        {}, description="Model operation statistics"
    )
    normalized_ipfs_stats: Optional[Dict[str, Any]] = Field(
        {}, description="Normalized IPFS statistics"
    )
    aggregate: Optional[Dict[str, Any]] = Field({}, description="Aggregate statistics")


class DaemonStatusRequest(BaseModel):
    """Request model for checking daemon status."""
    daemon_type: Optional[str] = Field(
        None, description="Type of daemon to check (ipfs, ipfs_cluster_service, etc.)"
    )


class DaemonStatusResponse(OperationResponse):
    """Response model for daemon status checks."""
    daemon_status: Dict[str, Any] = Field(..., description="Status of the requested daemon(s)")
    overall_status: str = Field(..., description="Overall status (healthy, degraded, or critical)")
    status_code: int = Field(
        ..., description="Numeric status code (200=healthy, 429=degraded, 500=critical)"
    )
    role: Optional[str] = Field(None, description="Node role (master, worker, leecher)")


class DAGPutRequest(BaseModel):
    """Request model for putting a DAG node."""
    object: Any = Field(..., description="Object to store as a DAG node")
    format: str = Field("json", description="Format to use (json or cbor)")
    pin: bool = Field(True, description="Whether to pin the node")


class DAGPutResponse(OperationResponse):
    """Response model for putting a DAG node."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID) of the DAG node")
    format: str = Field("json", description="Format used")
    pin: bool = Field(True, description="Whether the node was pinned")


class DAGGetResponse(OperationResponse):
    """Response model for getting a DAG node."""
    cid: str = Field(..., description="Content Identifier (CID) of the DAG node")
    object: Optional[Any] = Field(None, description="DAG node object")
    path: Optional[str] = Field(None, description="Path within the DAG node")


class DAGResolveResponse(OperationResponse):
    """Response model for resolving a DAG path."""
    path: str = Field(..., description="DAG path that was resolved")
    cid: Optional[str] = Field(None, description="Resolved CID")
    remainder_path: Optional[str] = Field(None, description="Remainder path, if any")


class BlockPutRequest(BaseModel):
    """Request model for putting a block."""
    data: str = Field(..., description="Block data to store (base64 encoded)")
    format: str = Field("dag-pb", description="Format to use (dag-pb, raw, etc.)")


class BlockPutResponse(OperationResponse):
    """Response model for putting a block."""
    cid: Optional[str] = Field(None, description="Content Identifier (CID) of the block")
    format: str = Field("dag-pb", description="Format used")
    size: Optional[int] = Field(None, description="Size of the block in bytes")


class BlockGetResponse(OperationResponse):
    """Response model for getting a block."""
    cid: str = Field(..., description="Content Identifier (CID) of the block")
    data: Optional[bytes] = Field(None, description="Block data")
    size: Optional[int] = Field(None, description="Size of the block in bytes")


class BlockStatResponse(OperationResponse):
    """Response model for block statistics."""
    cid: str = Field(..., description="Content Identifier (CID) of the block")
    size: Optional[int] = Field(None, description="Size of the block in bytes")
    key: Optional[str] = Field(None, description="Block key (same as CID)")
    format: Optional[str] = Field(None, description="Block format")


class DHTFindPeerRequest(BaseModel):
    """Request model for finding a peer using DHT."""
    peer_id: str = Field(..., description="ID of the peer to find")


class DHTFindPeerResponse(OperationResponse):
    """Response model for finding a peer using DHT."""
    peer_id: str = Field(..., description="ID of the peer that was searched for")
    responses: List[Dict[str, Any]] = Field([], description="Information about found peers")
    peers_found: int = Field(0, description="Number of peers found")


class DHTFindProvsRequest(BaseModel):
    """Request model for finding providers for a CID using DHT."""
    cid: str = Field(..., description="Content ID to find providers for")
    num_providers: Optional[int] = Field(None, description="Maximum number of providers to find")


class DHTFindProvsResponse(OperationResponse):
    """Response model for finding providers for a CID using DHT."""
    cid: str = Field(..., description="Content ID that was searched for")
    providers: List[Dict[str, Any]] = Field([], description="Information about providers")
    count: int = Field(0, description="Number of providers found")
    num_providers: Optional[int] = Field(
        None, description="Maximum number of providers that was requested"
    )


class NodeIDResponse(OperationResponse):
    """Response model for node ID information."""
    peer_id: str = Field(..., description="Peer ID of the IPFS node")
    addresses: List[str] = Field([], description="Multiaddresses of the IPFS node")
    agent_version: Optional[str] = Field(None, description="Agent version string")
    protocol_version: Optional[str] = Field(None, description="Protocol version string")
    public_key: Optional[str] = Field(None, description="Public key of the node")


class GetTarResponse(OperationResponse):
    """Response model for getting content as TAR archive."""
    cid: str = Field(..., description="Content Identifier (CID) of the content")
    output_dir: str = Field(..., description="Directory where content was saved")
    files: List[str] = Field([], description="List of files in the archive")


class FileUploadForm(BaseModel):
    """Form model for file uploads."""
    file: UploadFile
    pin: bool = False
    wrap_with_directory: bool = False

    class Config:
        arbitrary_types_allowed = True  # Required to allow UploadFile type


class IPFSController:
    """
    Controller for IPFS operations.

    Handles HTTP requests related to IPFS operations and delegates
    the business logic to the IPFS model.
    """
    def __init__(self, ipfs_model):
        """
        Initialize the IPFS controller.

        Args:
            ipfs_model: IPFS model to use for operations
        """
        self.ipfs_model = ipfs_model
        logger.info("IPFS Controller initialized")

    # --- Swarm Controller Methods ---
    async def swarm_peers(self) -> Dict[str, Any]:
        """Get a list of peers connected to this node."""
        try:
            # Use the new model method
            return self.ipfs_model.swarm_peers()
        except Exception as e:
            logger.error(f"Error in swarm_peers controller: {str(e)}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=f"Error getting peers: {str(e)}",
                endpoint="ipfs_swarm_peers", # Corrected endpoint name
                doc_category="ipfs"
            )
            # Just to satisfy type checker, this code is unreachable after raise
            return {"success": False, "error": str(e)}

    async def swarm_connect(self, request: PeerAddressRequest) -> Dict[str, Any]:
        """Connect to a peer by multiaddress."""
        try:
            # Use the new model method
            return self.ipfs_model.swarm_connect(request.peer_addr)
        except Exception as e:
            logger.error(f"Error in swarm_connect controller: {str(e)}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=f"Error connecting to peer: {str(e)}",
                endpoint="ipfs_swarm_connect", # Corrected endpoint name
                doc_category="ipfs"
            )
            # Just to satisfy type checker, this code is unreachable after raise
            return {"success": False, "error": str(e)}

    async def swarm_disconnect(self, request: PeerAddressRequest) -> Dict[str, Any]:
        """Disconnect from a peer by multiaddress."""
        try:
            # Use the new model method
            return self.ipfs_model.swarm_disconnect(request.peer_addr)
        except Exception as e:
            logger.error(f"Error in swarm_disconnect controller: {str(e)}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=f"Error disconnecting from peer: {str(e)}",
                endpoint="ipfs_swarm_disconnect", # Corrected endpoint name
                doc_category="ipfs"
            )
            # Just to satisfy type checker, this code is unreachable after raise
            return {"success": False, "error": str(e)}

    async def swarm_connect_get(
        self, peer_addr: str = Path(..., description="Peer multiaddress")
    ) -> Dict[str, Any]:
        """Connect to a peer by multiaddress (GET version for compatibility)."""
        try:
            # Use the new model method
            return self.ipfs_model.swarm_connect(peer_addr)
        except Exception as e:
            logger.error(f"Error in swarm_connect_get controller: {str(e)}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=f"Error connecting to peer: {str(e)}",
                endpoint="ipfs_swarm_connect", # Corrected endpoint name
                doc_category="ipfs"
            )
            # Just to satisfy type checker, this code is unreachable after raise
            return {"success": False, "error": str(e)}

    async def swarm_disconnect_get(
        self, peer_addr: str = Path(..., description="Peer multiaddress")
    ) -> Dict[str, Any]:
        """Disconnect from a peer by multiaddress (GET version for compatibility)."""
        try:
            # Use the new model method
            return self.ipfs_model.swarm_disconnect(peer_addr)
        except Exception as e:
            logger.error(f"Error in swarm_disconnect_get controller: {str(e)}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=f"Error disconnecting from peer: {str(e)}",
                endpoint="ipfs_swarm_disconnect", # Corrected endpoint name
                doc_category="ipfs"
            )
            # Just to satisfy type checker, this code is unreachable after raise
            return {"success": False, "error": str(e)}

    # --- End Swarm Controller Methods ---
    
    # --- MFS Controller Methods ---
    async def list_files(self, path: str = "/", long: bool = False):
        """
        List files in the MFS (Mutable File System) directory.
        
        Args:
            path: Path in MFS to list (default: "/")
            long: Whether to show detailed file information
            
        Returns:
            Dictionary with list of files and directories
        """
        logger.debug(f"Listing files in MFS path: {path}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"list_files_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to list files
            result = self.ipfs_model.files_ls(path=path, long=long)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Listed files in path {path}")
            return result
            
        except Exception as e:
            logger.error(f"Error listing files in path {path}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "long": long,
                "entries": []
            }
    
    async def stat_file(self, path: str):
        """
        Get information about a file or directory in MFS.
        
        Args:
            path: Path in MFS to stat
            
        Returns:
            Dictionary with file or directory information
        """
        logger.debug(f"Getting stats for MFS path: {path}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"stat_file_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to stat file
            result = self.ipfs_model.files_stat(path=path)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Got stats for path {path}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting stats for path {path}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path
            }
    
    async def make_directory(self, path: str, parents: bool = False):
        """
        Create a directory in the MFS.
        
        Args:
            path: Path in MFS to create
            parents: Whether to create parent directories if they don't exist
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Creating directory in MFS: {path}, parents: {parents}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"mkdir_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to create directory
            result = self.ipfs_model.files_mkdir(path=path, parents=parents)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Created directory {path}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "parents": parents
            }
    
    async def read_file(self, path: str, offset: int = 0, count: int = None):
        """
        Read content from a file in the MFS.
        
        Args:
            path: Path in MFS to read
            offset: Offset to start reading from
            count: Number of bytes to read (None means read all)
            
        Returns:
            Dictionary with file content
        """
        logger.debug(f"Reading file from MFS: {path}, offset: {offset}, count: {count}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"read_file_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to read file
            result = self.ipfs_model.files_read(path=path, offset=offset, count=count if count is not None else 0)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Read file {path}")
            return result
            
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "offset": offset,
                "count": count
            }
    
    async def write_file(self, path: str, content: str, create: bool = True, truncate: bool = True, 
                        offset: int = 0, flush: bool = True):
        """
        Write content to a file in the MFS.
        
        Args:
            path: Path in MFS to write to
            content: Content to write
            create: Whether to create the file if it doesn't exist
            truncate: Whether to truncate the file before writing
            offset: Offset to start writing at
            flush: Whether to flush changes to disk immediately
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Writing file to MFS: {path}, create: {create}, truncate: {truncate}, offset: {offset}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"write_file_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to write file
            result = self.ipfs_model.files_write(
                path=path, 
                content=content, 
                create=create, 
                truncate=truncate, 
                offset=offset, 
                flush=flush
            )
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Wrote file {path}")
            return result
            
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "create": create,
                "truncate": truncate,
                "offset": offset,
                "flush": flush
            }
    
    async def remove_file(self, path: str, recursive: bool = False, force: bool = False):
        """
        Remove a file or directory from the MFS.
        
        Args:
            path: Path in MFS to remove
            recursive: Whether to remove directories recursively
            force: Whether to force removal
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Removing from MFS: {path}, recursive: {recursive}, force: {force}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"remove_file_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to remove file
            result = self.ipfs_model.files_rm(path=path, recursive=recursive, force=force)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Removed {path}")
            return result
            
        except Exception as e:
            logger.error(f"Error removing {path}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "recursive": recursive,
                "force": force
            }
    
    async def publish_name(self, path: str, key: str = "self", resolve: bool = True, lifetime: str = "24h"):
        """
        Publish an IPFS path to IPNS.
        
        Args:
            path: Path to publish
            key: Name of the key to use
            resolve: Whether to resolve the path before publishing
            lifetime: Lifetime of the record
            
        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Publishing to IPNS: {path}, key: {key}, resolve: {resolve}, lifetime: {lifetime}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"publish_name_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to publish name
            result = self.ipfs_model.name_publish(path=path, key=key, resolve=resolve, lifetime=lifetime)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Published {path} to IPNS with key {key}")
            return result
            
        except Exception as e:
            logger.error(f"Error publishing {path} to IPNS: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "key": key,
                "resolve": resolve,
                "lifetime": lifetime
            }
    
    async def resolve_name(self, name: str, recursive: bool = True, nocache: bool = False):
        """
        Resolve an IPNS name to an IPFS path.
        
        Args:
            name: IPNS name to resolve
            recursive: Whether to resolve recursively
            nocache: Whether to avoid using cached entries
            
        Returns:
            Dictionary with resolved path
        """
        logger.debug(f"Resolving IPNS name: {name}, recursive: {recursive}, nocache: {nocache}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"resolve_name_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to resolve name
            result = self.ipfs_model.name_resolve(name=name, recursive=recursive, nocache=nocache)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Resolved IPNS name {name}")
            return result
            
        except Exception as e:
            logger.error(f"Error resolving IPNS name {name}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "name": name,
                "recursive": recursive,
                "nocache": nocache
            }
    
    async def get_dag_node(self, cid: str, path: str = None):
        """
        Get a DAG node from IPFS.
        
        Args:
            cid: CID of the DAG node
            path: Optional path within the DAG node
            
        Returns:
            Dictionary with DAG node data
        """
        logger.debug(f"Getting DAG node: {cid}, path: {path}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"get_dag_node_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to get DAG node
            result = self.ipfs_model.dag_get(cid=cid, path=path)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Got DAG node {cid}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting DAG node {cid}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid,
                "path": path
            }
    
    async def put_dag_node(self, object: dict, format: str = "json", pin: bool = True):
        """
        Put a DAG node to IPFS.
        
        Args:
            object: Object to store as a DAG node
            format: Format to use (json or cbor)
            pin: Whether to pin the node
            
        Returns:
            Dictionary with operation results, including the CID
        """
        logger.debug(f"Putting DAG node: format: {format}, pin: {pin}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"put_dag_node_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to put DAG node
            result = self.ipfs_model.dag_put(obj=object, format=format, pin=pin)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Put DAG node, CID: {result.get('cid', 'unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error putting DAG node: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "format": format,
                "pin": pin
            }
    
    async def get_block_json(self, cid: str):
        """
        Get a raw block using query or JSON input.
        
        Args:
            cid: CID of the block
            
        Returns:
            Dictionary with block data
        """
        logger.debug(f"Getting block: {cid}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"get_block_json_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to get block
            result = self.ipfs_model.block_get(cid=cid)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Got block {cid}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting block {cid}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def stat_block(self, cid: str):
        """
        Get information about a block.
        
        Args:
            cid: CID of the block
            
        Returns:
            Dictionary with block information
        """
        logger.debug(f"Getting block stats: {cid}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"stat_block_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to get block stats
            result = self.ipfs_model.block_stat(cid=cid)
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            logger.debug(f"Got block stats for {cid}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting block stats for {cid}: {e}")
            
            # Return error in standardized format
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    # --- End MFS Controller Methods ---

    def register_routes(self, router: APIRouter, prefix: str = ""):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Add version endpoint
        router.add_api_route(
            "/ipfs/version",
            self.get_version,
            methods=["GET"],
            summary="Get IPFS version information",
            description="Get version information about the IPFS node",
        )

        # Add content routes with path that handles both JSON and form data
        router.add_api_route(
            "/ipfs/add",
            self.handle_add_request,
            methods=["POST"],
            response_model=AddContentResponse,
            summary="Add content to IPFS (JSON or form)",
            description="Add content to IPFS using either JSON payload or file upload",
        )

        # Keep original routes for backward compatibility
        router.add_api_route(
            "/ipfs/add/json",
            self.add_content,
            methods=["POST"],
            response_model=AddContentResponse,
            summary="Add content to IPFS (JSON only)",
            description="Add content to IPFS and return the CID (JSON payload only)",
        )

        router.add_api_route(
            "/ipfs/add/file",
            self.add_file,
            methods=["POST"],
            response_model=AddContentResponse,
            summary="Add a file to IPFS",
            description="Upload a file to IPFS and return the CID",
        )

        # Get content routes with API-compatible alias paths
        router.add_api_route(
            "/ipfs/cat/{cid}",
            self.get_content,
            methods=["GET"],
            response_class=Response,  # Raw response for content
            summary="Get content from IPFS",
            description="Get content from IPFS by CID and return as raw response",
        )

        # Add "/ipfs/get/{cid}" alias for compatibility with tests
        router.add_api_route(
            "/ipfs/get/{cid}",
            self.get_content,
            methods=["GET"],
            response_class=Response,  # Raw response for content
            summary="Get content from IPFS (alias)",
            description="Alias for /ipfs/cat/{cid}",
        )

        # Add route for downloading content as TAR archive
        router.add_api_route(
            "/ipfs/get_tar/{cid}",
            self.get_content_as_tar,
            methods=["GET"],
            response_model=GetTarResponse,
            summary="Get content as TAR archive",
            description="Download content from IPFS as a TAR archive",
        )

        router.add_api_route(
            "/ipfs/cat",
            self.get_content_json,
            methods=["POST"],
            response_model=GetContentResponse,
            summary="Get content from IPFS (JSON)",
            description="Get content from IPFS by CID and return as JSON",
        )

        # Pin management routes with traditional naming
        router.add_api_route(
            "/ipfs/pin/add",
            self.pin_content,
            methods=["POST"],
            response_model=PinResponse,
            summary="Pin content to IPFS",
            description="Pin content to local IPFS node by CID",
        )

        router.add_api_route(
            "/ipfs/pin/rm",
            self.unpin_content,
            methods=["POST"],
            response_model=PinResponse,
            summary="Unpin content from IPFS",
            description="Unpin content from local IPFS node by CID",
        )

        router.add_api_route(
            "/ipfs/pin/ls",
            self.list_pins,
            methods=["GET"],
            response_model=ListPinsResponse,
            summary="List pinned content",
            description="List content pinned to local IPFS node",
        )

        # Add alias routes for pin operations to match test expectations
        router.add_api_route(
            "/ipfs/pin",
            self.pin_content,
            methods=["POST"],
            response_model=PinResponse,
            summary="Pin content (alias)",
            description="Alias for /ipfs/pin/add",
        )

        # DAG operations
        router.add_api_route(
            "/ipfs/dag/put",
            self.dag_put,
            methods=["POST"],
            response_model=DAGPutResponse,
            summary="Add a DAG node to IPFS",
            description="Add an object as a DAG node to IPFS and return the CID",
        )

        router.add_api_route(
            "/ipfs/dag/get/{cid}",
            self.dag_get,
            methods=["GET"],
            response_model=DAGGetResponse,
            summary="Get a DAG node from IPFS",
            description="Retrieve a DAG node from IPFS by CID",
        )

        router.add_api_route(
            "/ipfs/dag/resolve/{path:path}",
            self.dag_resolve,
            methods=["GET"],
            response_model=DAGResolveResponse,
            summary="Resolve a DAG path",
            description="Resolve a path through a DAG structure",
        )

        # Block operations
        router.add_api_route(
            "/ipfs/block/put",
            self.block_put,
            methods=["POST"],
            response_model=BlockPutResponse,
            summary="Add a raw block to IPFS",
            description="Add raw block data to IPFS and return the CID",
        )

        router.add_api_route(
            "/ipfs/block/get/{cid}",
            self.block_get,
            methods=["GET"],
            response_model=BlockGetResponse,
            summary="Get a raw block from IPFS",
            description="Retrieve raw block data from IPFS by CID",
        )

        router.add_api_route(
            "/ipfs/block/stat/{cid}",
            self.block_stat,
            methods=["GET"],
            response_model=BlockStatResponse,
            summary="Get stats about a block",
            description="Retrieve statistics about a block by CID",
        )

        router.add_api_route(
            "/ipfs/unpin",
            self.unpin_content,
            methods=["POST"],
            response_model=PinResponse,
            summary="Unpin content (alias)",
            description="Alias for /ipfs/pin/rm",
        )

        router.add_api_route(
            "/ipfs/pins",
            self.list_pins,
            methods=["GET"],
            response_model=ListPinsResponse,
            summary="List pins (alias)",
            description="Alias for /ipfs/pin/ls",
        )

        # Statistics route
        router.add_api_route(
            "/ipfs/stats",
            self.get_stats,
            methods=["GET"],
            response_model=StatsResponse,
            summary="Get statistics about IPFS operations",
            description="Get statistics about IPFS operations",
        )

        # Standard IPFS API endpoints (missing from original implementation)

        # Node info endpoints
        router.add_api_route(
            "/ipfs/id",
            self.get_node_id,
            methods=["POST", "GET"],
            summary="Get node identity",
            description="Get information about the IPFS node identity",
        )

        router.add_api_route(
            "/ipfs/version",
            self.get_version,
            methods=["POST", "GET"],
            summary="Get IPFS version",
            description="Get version information about the IPFS node",
        )

        # Swarm management endpoints
        router.add_api_route(
            "/ipfs/swarm/peers",
            self.swarm_peers,  # Use the new method
            methods=["POST", "GET"],  # Keep existing methods
            response_model=SwarmPeersResponse,  # Use new response model
            summary="List connected peers",
            description="List peers connected to the IPFS node",
        )

        router.add_api_route(
            "/ipfs/swarm/connect",
            self.swarm_connect,  # Use the new method
            methods=["POST"],  # Keep existing method
            response_model=SwarmConnectResponse,  # Use new response model
            summary="Connect to peer",
            description="Connect to a peer with the given multiaddress",
        )

        router.add_api_route(
            "/ipfs/swarm/disconnect",
            self.swarm_disconnect,  # Use the new method
            methods=["POST"],  # Keep existing method
            response_model=SwarmDisconnectResponse,  # Use new response model
            summary="Disconnect from peer",
            description="Disconnect from a peer with the given multiaddress",
        )

        # Add new GET routes for compatibility
        router.add_api_route(
            "/ipfs/swarm/connect/{peer_addr:path}",  # Use :path to capture full multiaddr
            self.swarm_connect_get,
            methods=["GET"],
            response_model=SwarmConnectResponse,
            summary="Connect to peer (GET)",
            description="Connect to a peer by multiaddress (GET version for compatibility)",
        )

        router.add_api_route(
            "/ipfs/swarm/disconnect/{peer_addr:path}",  # Use :path to capture full multiaddr
            self.swarm_disconnect_get,
            methods=["GET"],
            response_model=SwarmDisconnectResponse,
            summary="Disconnect from peer (GET)",
            description="Disconnect from a peer by multiaddress (GET version for compatibility)",
        )

        # Files API (MFS) endpoints
        # Import methods at the module level to make them available
        
        # Now register routes
        
        # Now register routes
        router.add_api_route(
            "/ipfs/files/ls",
            self.list_files,
            methods=["POST", "GET"],
            summary="List files",
            description="List files in the MFS (Mutable File System) directory",
        )

        router.add_api_route(
            "/ipfs/files/stat",
            self.stat_file,
            methods=["POST", "GET"],
            summary="Get file information",
            description="Get information about a file or directory in MFS",
        )

        router.add_api_route(
            "/ipfs/files/mkdir",
            self.make_directory,
            methods=["POST"],
            summary="Create directory",
            description="Create a directory in the MFS (Mutable File System)",
        )

        router.add_api_route(
            "/ipfs/files/read",
            self.read_file,
            methods=["POST", "GET"],
            summary="Read file content",
            description="Read content from a file in the MFS (Mutable File System)",
        )

        router.add_api_route(
            "/ipfs/files/write",
            self.write_file,
            methods=["POST"],
            summary="Write to file",
            description="Write content to a file in the MFS (Mutable File System)",
        )

        router.add_api_route(
            "/ipfs/files/rm",
            self.remove_file,
            methods=["POST", "DELETE"],
            summary="Remove file or directory",
            description="Remove a file or directory from the MFS (Mutable File System)",
        )
        
        # IPNS endpoints
        router.add_api_route(
            "/ipfs/name/publish",
            self.publish_name,
            methods=["POST"],
            summary="Publish to IPNS",
            description="Publish an IPFS path to IPNS",
        )
        
        router.add_api_route(
            "/ipfs/name/resolve",
            self.resolve_name,
            methods=["POST", "GET"],
            summary="Resolve IPNS name",
            description="Resolve an IPNS name to an IPFS path",
        )
        
        # DHT endpoints
        router.add_api_route(
            "/ipfs/dht/findpeer",
            self.dht_findpeer,
            methods=["POST"],
            summary="Find peer",
            description="Find information about a peer using the DHT",
        )
        
        router.add_api_route(
            "/ipfs/dht/findprovs",
            self.dht_findprovs,
            methods=["POST"],
            summary="Find providers",
            description="Find providers for content using the DHT",
        )
        
        # Add daemon status endpoint
        router.add_api_route(
            "/ipfs/daemon/status",
            self.check_daemon_status,
            methods=["POST", "GET"],
            summary="Check daemon status",
            description="Check status of IPFS daemons",
        )
        
        # Add replication status endpoint
        router.add_api_route(
            "/ipfs/replication/status",
            self.get_replication_status,
            methods=["GET"],
            summary="Get replication status",
            description="Get replication status for a CID",
        )
    
    # The following methods are placeholders that should be implemented if needed
    
    async def get_version(self):
        """Get IPFS version information."""
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"get_version_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to get version
            result = self.ipfs_model.get_version()
            
            # Add operation tracking fields for consistency
            if "operation_id" not in result:
                result["operation_id"] = operation_id
                
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            return result
        except Exception as e:
            logger.error(f"Error getting IPFS version: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def handle_add_request(self, request: Request):
        """Handle adding content to IPFS from various request types."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"handle_add_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": "placeholder_cid"
            }
        except Exception as e:
            logger.error(f"Error handling add request: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def add_content(self, content_request: ContentRequest):
        """Add content to IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"add_content_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": "placeholder_cid"
            }
        except Exception as e:
            logger.error(f"Error adding content: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def add_file(self, file: UploadFile = File(...), pin: bool = Form(False)):
        """Add a file to IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"add_file_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": "placeholder_cid"
            }
        except Exception as e:
            logger.error(f"Error adding file: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def get_content(self, cid: str, request: Request = None):
        """Get content from IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"get_content_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return Response(content=b"placeholder content")
        except Exception as e:
            logger.error(f"Error getting content: {e}")
            return Response(
                content=str(e).encode(),
                status_code=500
            )
    
    async def get_content_json(self, cid_request: CIDRequest):
        """Get content from IPFS as JSON."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"get_content_json_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid_request.cid,
                "data": b"placeholder data"
            }
        except Exception as e:
            logger.error(f"Error getting content as JSON: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid_request.cid
            }
    
    async def get_content_as_tar(self, cid: str):
        """Get content as a TAR archive."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"get_tar_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid,
                "output_dir": "/tmp",
                "files": []
            }
        except Exception as e:
            logger.error(f"Error getting content as TAR: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def pin_content(self, cid_request: CIDRequest):
        """Pin content to IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"pin_content_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid_request.cid
            }
        except Exception as e:
            logger.error(f"Error pinning content: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid_request.cid
            }
    
    async def unpin_content(self, cid_request: CIDRequest):
        """Unpin content from IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"unpin_content_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid_request.cid
            }
        except Exception as e:
            logger.error(f"Error unpinning content: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid_request.cid
            }
    
    async def list_pins(self):
        """List pinned content."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"list_pins_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "pins": [],
                "count": 0
            }
        except Exception as e:
            logger.error(f"Error listing pins: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "pins": [],
                "count": 0
            }
    
    async def get_stats(self):
        """Get statistics about IPFS operations."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"get_stats_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "operation_stats": {},
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "operation_stats": {}
            }
    
    async def get_node_id(self):
        """Get node identity information."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"get_node_id_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "peer_id": "placeholder_peer_id",
                "addresses": []
            }
        except Exception as e:
            logger.error(f"Error getting node ID: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def dag_put(self, dag_request: DAGPutRequest):
        """Put a DAG node to IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"dag_put_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": "placeholder_cid",
                "format": dag_request.format,
                "pin": dag_request.pin
            }
        except Exception as e:
            logger.error(f"Error putting DAG node: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def dag_get(self, cid: str, path: str = None):
        """Get a DAG node from IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"dag_get_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid,
                "object": {},
                "path": path
            }
        except Exception as e:
            logger.error(f"Error getting DAG node: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def dag_resolve(self, path: str):
        """Resolve a DAG path."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"dag_resolve_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "path": path,
                "cid": "placeholder_cid",
                "remainder_path": ""
            }
        except Exception as e:
            logger.error(f"Error resolving DAG path: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path
            }
    
    async def block_put(self, block_request: BlockPutRequest):
        """Add a raw block to IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"block_put_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": "placeholder_cid",
                "format": block_request.format,
                "size": 0
            }
        except Exception as e:
            logger.error(f"Error putting block: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def block_get(self, cid: str):
        """Get a raw block from IPFS."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"block_get_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid,
                "data": b"placeholder_data",
                "size": 0
            }
        except Exception as e:
            logger.error(f"Error getting block: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def block_stat(self, cid: str):
        """Get statistics about a block."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"block_stat_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid,
                "size": 0,
                "key": cid,
                "format": "dag-pb"
            }
        except Exception as e:
            logger.error(f"Error getting block stats: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def dht_findpeer(self, request: DHTFindPeerRequest):
        """Find a peer using the DHT."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"dht_findpeer_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "peer_id": request.peer_id,
                "responses": [],
                "peers_found": 0
            }
        except Exception as e:
            logger.error(f"Error finding peer: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "peer_id": request.peer_id,
                "peers_found": 0
            }
    
    async def dht_findprovs(self, request: DHTFindProvsRequest):
        """Find providers for a CID using the DHT."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"dht_findprovs_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": request.cid,
                "providers": [],
                "count": 0,
                "num_providers": request.num_providers
            }
        except Exception as e:
            logger.error(f"Error finding providers: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": request.cid,
                "count": 0
            }
    
    async def check_daemon_status(self, request: DaemonStatusRequest = None):
        """Check status of IPFS daemons."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"check_daemon_{int(start_time * 1000)}"
        
        try:
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "daemon_status": {"overall": "healthy", "daemons": {}},
                "overall_status": "healthy",
                "status_code": 200
            }
        except Exception as e:
            logger.error(f"Error checking daemon status: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "daemon_status": {"overall": "error", "daemons": {}},
                "overall_status": "error",
                "status_code": 500
            }
    
    async def get_replication_status(self, request: Request):
        """Get replication status for a CID."""
        # Implementation would go here
        start_time = time.time()
        operation_id = f"replication_status_{int(start_time * 1000)}"
        
        try:
            # Get CID from query parameters
            cid = request.query_params.get("cid")
            if not cid:
                return {
                    "success": False,
                    "operation_id": operation_id,
                    "duration_ms": (time.time() - start_time) * 1000,
                    "error": "Missing CID parameter",
                    "error_type": "MISSING_PARAMETER"
                }
            
            # This is a placeholder implementation
            return {
                "success": True,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "cid": cid,
                "replication": {},
                "needs_replication": False
            }
        except Exception as e:
            logger.error(f"Error getting replication status: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid if 'cid' in locals() else None
            }

    async def cat(self, **kwargs):
        """Proxy to extensions.cat."""
        try:
            if 'cat' in globals():
                return await globals()['cat'](**kwargs)
            else:
                logger.error("Method cat not found in extensions")
                return {
                    "success": False,
                    "error": "Method cat not found in extensions"
                }
        except Exception as e:
            logger.error(f"Error in cat: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def pin_add(self, **kwargs):
        """Proxy to extensions.pin_add."""
        try:
            if 'pin_add' in globals():
                return await globals()['pin_add'](**kwargs)
            else:
                logger.error("Method pin_add not found in extensions")
                return {
                    "success": False,
                    "error": "Method pin_add not found in extensions"
                }
        except Exception as e:
            logger.error(f"Error in pin_add: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def pin_rm(self, **kwargs):
        """Proxy to extensions.pin_rm."""
        try:
            if 'pin_rm' in globals():
                return await globals()['pin_rm'](**kwargs)
            else:
                logger.error("Method pin_rm not found in extensions")
                return {
                    "success": False,
                    "error": "Method pin_rm not found in extensions"
                }
        except Exception as e:
            logger.error(f"Error in pin_rm: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def pin_ls(self, **kwargs):
        """Proxy to extensions.pin_ls."""
        try:
            if 'pin_ls' in globals():
                return await globals()['pin_ls'](**kwargs)
            else:
                logger.error("Method pin_ls not found in extensions")
                return {
                    "success": False,
                    "error": "Method pin_ls not found in extensions"
                }
        except Exception as e:
            logger.error(f"Error in pin_ls: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def storage_transfer(self, **kwargs):
        """Proxy to extensions.storage_transfer."""
        try:
            if 'storage_transfer' in globals():
                return await globals()['storage_transfer'](**kwargs)
            else:
                logger.error("Method storage_transfer not found in extensions")
                return {
                    "success": False,
                    "error": "Method storage_transfer not found in extensions"
                }
        except Exception as e:
            logger.error(f"Error in storage_transfer: {e}")
            return {
                "success": False,
                "error": str(e)
            }

"""IPFS Controller AnyIO Module

This module provides AnyIO-compatible IPFS controller functionality.
"""

import os
import anyio
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReadFileRequest(BaseModel):
    """Request model for reading file operations."""
    path: str = Field(..., description="Path to read the file from")
    encoding: Optional[str] = Field(None, description="Encoding for returned string (None returns bytes)")
    offset: Optional[int] = Field(0, description="Offset to start reading from")
    length: Optional[int] = Field(None, description="Maximum number of bytes to read")
    count: Optional[int] = Field(-1, description="Number of bytes to read (alias for length)")


class WriteFileRequest(BaseModel):
    """Request model for writing file operations."""
    path: str = Field(..., description="Path to write the file")
    content: Union[str, bytes] = Field(..., description="Content to write to the file")
    create_dirs: bool = Field(False, description="Create parent directories if they don't exist")
    overwrite: bool = Field(True, description="Overwrite if file exists")
    encoding: Optional[str] = Field("utf-8", description="Encoding for string content")
    offset: Optional[int] = Field(0, description="Offset to start writing at")
    create: Optional[bool] = Field(True, description="Create file if it doesn't exist")
    truncate: Optional[bool] = Field(True, description="Truncate file before writing")
    parents: Optional[bool] = Field(False, description="Create parent directories if they don't exist")


class RemoveFileRequest(BaseModel):
    """Request model for removing file operations."""
    path: str = Field(..., description="Path to remove")
    recursive: bool = Field(False, description="Recursively remove directories")
    force: bool = Field(False, description="Force removal")


class CopyFileRequest(BaseModel):
    """Request model for copying file operations."""
    source: str = Field(..., description="Source path")
    destination: str = Field(..., description="Destination path")
    parents: bool = Field(False, description="Create parent directories if they don't exist")


class MoveFileRequest(BaseModel):
    """Request model for moving file operations."""
    source: str = Field(..., description="Source path")
    destination: str = Field(..., description="Destination path")
    parents: bool = Field(False, description="Create parent directories if they don't exist")


class FlushFilesRequest(BaseModel):
    """Request model for flushing files operations."""
    path: str = Field("/", description="Path to flush")


class MakeDirRequest(BaseModel):
    """Request model for making directory operations."""
    path: str = Field(..., description="Path to create")
    parents: bool = Field(False, description="Create parent directories if they don't exist")


class StreamRequest(BaseModel):
    """Request model for streaming operations."""
    path: str = Field(..., description="Path or CID to stream")
    stream_type: str = Field("file", description="Type of stream (file, camera, etc.)")
    chunk_size: int = Field(8192, description="Size of chunks for streaming")
    format: Optional[str] = Field(None, description="Format for the stream")


class IPFSOperationRequest:
    """Request model for IPFS operations."""
    
    def __init__(
        self, 
        operation: str,
        cid: Optional[str] = None,
        path: Optional[str] = None,
        data: Optional[bytes] = None,
        options: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        self.cid = cid
        self.path = path
        self.data = data
        self.options = options or {}


class ResourceStatsResponse(BaseModel):
    """Response model for resource statistics."""
    cpu_percent: float = Field(0.0, description="CPU usage percentage")
    memory_percent: float = Field(0.0, description="Memory usage percentage")
    disk_percent: float = Field(0.0, description="Disk usage percentage")
    network_in_bytes: int = Field(0, description="Network bytes received")
    network_out_bytes: int = Field(0, description="Network bytes sent")
    ipfs_repo_size: int = Field(0, description="Size of IPFS repository in bytes")
    ipfs_objects_count: int = Field(0, description="Number of objects in IPFS repository")


class ReplicationPolicyResponse(BaseModel):
    """Response model for replication policy information."""
    policy_id: str = Field(..., description="ID of the replication policy")
    target_replica_count: int = Field(..., description="Target number of replicas")
    current_replica_count: int = Field(..., description="Current number of replicas")
    cids: List[str] = Field(..., description="List of CIDs covered by this policy")
    storage_providers: List[str] = Field(..., description="List of storage providers used")
    status: str = Field(..., description="Status of the replication policy")


class IPFSControllerAnyIO:
    """AnyIO-compatible controller for IPFS operations."""
    
    def __init__(self, ipfs_model):
        """Initialize with an IPFS model."""
        self.ipfs_model = ipfs_model
        self.logger = logging.getLogger(__name__)
    
    async def add_file(self, request) -> Dict[str, Any]:
        """Add a file to IPFS."""
        self.logger.info(f"Adding file with options: {request.options}")
        result = await self.ipfs_model.add_async(request.data, **request.options)
        return {"hash": result.get("Hash", ""), "success": True}
    
    async def get_file(self, request) -> Dict[str, Any]:
        """Get a file from IPFS."""
        self.logger.info(f"Getting file with CID: {request.cid}")
        data = await self.ipfs_model.get_async(request.cid, **request.options)
        return {"data": data, "success": True}
    
    async def cat_file(self, request) -> Dict[str, Any]:
        """Cat a file from IPFS."""
        self.logger.info(f"Catting file with CID: {request.cid}")
        data = await self.ipfs_model.cat_async(request.cid, **request.options)
        return {"data": data, "success": True}
    
    async def pin_add(self, request) -> Dict[str, Any]:
        """Pin a file in IPFS."""
        self.logger.info(f"Pinning CID: {request.cid}")
        result = await self.ipfs_model.pin_add_async(request.cid, **request.options)
        return {"pins": result.get("Pins", []), "success": True}
    
    async def pin_rm(self, request) -> Dict[str, Any]:
        """Unpin a file from IPFS."""
        self.logger.info(f"Unpinning CID: {request.cid}")
        result = await self.ipfs_model.pin_rm_async(request.cid, **request.options)
        return {"pins": result.get("Pins", []), "success": True}
    
    async def pin_ls(self, request) -> Dict[str, Any]:
        """List pinned content in IPFS."""
        self.logger.info("Listing pins")
        result = await self.ipfs_model.pin_ls_async(**request.options)
        return {"pins": result.get("Keys", {}), "success": True}
    
    async def ls(self, request) -> Dict[str, Any]:
        """List content in IPFS."""
        self.logger.info(f"Listing content for CID: {request.cid}")
        result = await self.ipfs_model.ls_async(request.cid, **request.options)
        return {"objects": result.get("Objects", []), "success": True}
    
    async def name_publish(self, request) -> Dict[str, Any]:
        """Publish a name to IPNS."""
        self.logger.info(f"Publishing name for CID: {request.cid}")
        result = await self.ipfs_model.name_publish_async(request.cid, **request.options)
        return {"name": result.get("Name", ""), "value": result.get("Value", ""), "success": True}
    
    async def name_resolve(self, request) -> Dict[str, Any]:
        """Resolve a name from IPNS."""
        self.logger.info(f"Resolving name: {request.path}")
        result = await self.ipfs_model.name_resolve_async(request.path, **request.options)
        return {"path": result.get("Path", ""), "success": True}
    
    async def dht_findprovs(self, request) -> Dict[str, Any]:
        """Find providers for a CID via DHT."""
        self.logger.info(f"Finding providers for CID: {request.cid}")
        result = await self.ipfs_model.dht_findprovs_async(request.cid, **request.options)
        return {"providers": result, "success": True}
    
    async def dht_findpeer(self, request) -> Dict[str, Any]:
        """Find a peer via DHT."""
        self.logger.info(f"Finding peer: {request.path}")
        result = await self.ipfs_model.dht_findpeer_async(request.path, **request.options)
        return {"peer": result, "success": True}
    
    async def dht_provide(self, request) -> Dict[str, Any]:
        """Announce that this node can provide a CID."""
        self.logger.info(f"Providing CID: {request.cid}")
        result = await self.ipfs_model.dht_provide_async(request.cid, **request.options)
        return {"success": True}
    
    async def read_file(self, request: ReadFileRequest) -> Dict[str, Any]:
        """Read content from a file."""
        self.logger.info(f"Reading from file: {request.path}")
        
        try:
            if not os.path.exists(request.path):
                return {
                    "success": False,
                    "path": request.path,
                    "error": "File not found"
                }
                
            with open(request.path, 'rb') as f:
                if request.offset > 0:
                    f.seek(request.offset)
                if request.length is not None:
                    data = f.read(request.length)
                else:
                    data = f.read()
            
            # Convert to string if encoding is specified
            if request.encoding:
                try:
                    content = data.decode(request.encoding)
                    return {
                        "success": True,
                        "path": request.path,
                        "content": content,
                        "bytes_read": len(data),
                        "encoding": request.encoding
                    }
                except UnicodeDecodeError as e:
                    return {
                        "success": False,
                        "path": request.path,
                        "error": f"Failed to decode with {request.encoding}: {str(e)}"
                    }
            else:
                return {
                    "success": True,
                    "path": request.path,
                    "content": data,
                    "bytes_read": len(data)
                }
        except Exception as e:
            self.logger.error(f"Error reading file: {str(e)}")
            return {
                "success": False,
                "path": request.path,
                "error": f"Failed to read file: {str(e)}"
            }
        
    async def write_file(self, request: WriteFileRequest) -> Dict[str, Any]:
        """Write content to a file."""
        self.logger.info(f"Writing to file: {request.path}")
        content = request.content
        # Convert string to bytes if necessary
        if isinstance(content, str):
            content = content.encode(request.encoding)
            
        # Create parent directories if requested
        if request.create_dirs:
            try:
                directory = os.path.dirname(request.path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
            except Exception as e:
                self.logger.error(f"Error creating directories: {str(e)}")
                return {
                    "success": False,
                    "path": request.path,
                    "error": f"Failed to create directories: {str(e)}"
                }
                
        # Check if file exists and handle overwrite
        if os.path.exists(request.path) and not request.overwrite:
            return {
                "success": False,
                "path": request.path,
                "error": "File exists and overwrite is False"
            }
            
        try:
            with open(request.path, 'wb') as f:
                f.write(content)
            return {
                "success": True,
                "path": request.path,
                "bytes_written": len(content)
            }
        except Exception as e:
            self.logger.error(f"Error writing file: {str(e)}")
            return {
                "success": False,
                "path": request.path,
                "error": f"Failed to write file: {str(e)}"
            }
    
    async def get_resource_stats(self) -> ResourceStatsResponse:
        """Get resource statistics for this node."""
        self.logger.info("Getting resource statistics")
        
        try:
            # Get system stats
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            # Get network stats
            net_io = psutil.net_io_counters()
            network_in = net_io.bytes_recv
            network_out = net_io.bytes_sent
            
            # Get IPFS repo stats
            repo_stats = await self.ipfs_model.repo_stat_async()
            ipfs_repo_size = repo_stats.get("RepoSize", 0)
            ipfs_objects = repo_stats.get("NumObjects", 0)
            
            return ResourceStatsResponse(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_in_bytes=network_in,
                network_out_bytes=network_out,
                ipfs_repo_size=ipfs_repo_size,
                ipfs_objects_count=ipfs_objects
            )
        except Exception as e:
            self.logger.error(f"Error getting resource stats: {str(e)}")
            # Return defaults on error
            return ResourceStatsResponse()
    
    async def stream_data(self, request: StreamRequest) -> Dict[str, Any]:
        """Stream data from a source, returning a generator."""
        self.logger.info(f"Streaming from {request.stream_type}: {request.path}")
        
        # Handle different stream types
        if request.stream_type == "file":
            # Stream from file
            try:
                if request.path.startswith("Qm") or request.path.startswith("bafy"):
                    # This is a CID - stream from IPFS
                    self.logger.info(f"Streaming content from IPFS with CID: {request.path}")
                    
                    # Get file size first (optional for progress reporting)
                    ls_result = await self.ipfs_model.ls_async(request.path)
                    file_size = ls_result.get("Objects", [{}])[0].get("Size", 0)
                    
                    # Setup streaming response from IPFS cat with offset
                    async def ipfs_stream_generator():
                        offset = 0
                        while True:
                            chunk = await self.ipfs_model.cat_async(request.path, offset=offset, length=request.chunk_size)
                            if not chunk:
                                break
                            yield chunk
                            offset += len(chunk)
                            
                    return {
                        "success": True,
                        "stream": ipfs_stream_generator(),
                        "content_type": "application/octet-stream",
                        "size": file_size
                    }
                else:
                    # This is a local file path
                    if not os.path.exists(request.path):
                        return {
                            "success": False,
                            "error": f"File not found: {request.path}"
                        }
                        
                    file_size = os.path.getsize(request.path)
                    
                    # Setup streaming response from local file
                    async def file_stream_generator():
                        with open(request.path, "rb") as f:
                            while True:
                                chunk = f.read(request.chunk_size)
                                if not chunk:
                                    break
                                yield chunk
                                
                    return {
                        "success": True,
                        "stream": file_stream_generator(),
                        "content_type": "application/octet-stream",
                        "size": file_size
                    }
            except Exception as e:
                self.logger.error(f"Error setting up file stream: {str(e)}")
                return {
                    "success": False,
                    "error": f"Failed to stream file: {str(e)}"
                }
        elif request.stream_type == "camera":
            # Import optional CV2 for camera streaming
            try:
                import cv2
                import numpy as np
                
                camera_id = 0
                if request.path.isdigit():
                    camera_id = int(request.path)
                
                cap = cv2.VideoCapture(camera_id)
                if not cap.isOpened():
                    return {
                        "success": False,
                        "error": f"Could not open camera with ID: {camera_id}"
                    }
                    
                # Setup streaming response for camera feed
                async def camera_stream_generator():
                    try:
                        while True:
                            ret, frame = cap.read()
                            if not ret:
                                break
                                
                            # Convert to requested format if specified
                            if request.format == "jpeg":
                                _, buffer = cv2.imencode(".jpg", frame)
                                yield buffer.tobytes()
                            elif request.format == "png":
                                _, buffer = cv2.imencode(".png", frame)
                                yield buffer.tobytes()
                            else:
                                # Default: raw frame bytes
                                yield frame.tobytes()
                                
                            # Rate limiting to avoid overwhelming the system
                            await anyio.sleep(0.03)  # ~30fps
                    finally:
                        cap.release()
                        
                content_type = "image/jpeg" if request.format == "jpeg" else "image/png" if request.format == "png" else "application/octet-stream"
                
                return {
                    "success": True,
                    "stream": camera_stream_generator(),
                    "content_type": content_type
                }
            except ImportError:
                return {
                    "success": False,
                    "error": "Camera streaming requires OpenCV (cv2). Please install it with: pip install opencv-python"
                }
            except Exception as e:
                self.logger.error(f"Error setting up camera stream: {str(e)}")
                return {
                    "success": False,
                    "error": f"Failed to stream from camera: {str(e)}"
                }
        else:
            return {
                "success": False,
                "error": f"Unsupported stream type: {request.stream_type}"
            }
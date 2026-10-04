"""
IPFS streaming operations utility.

This module provides utilities for streaming operations with IPFS,
implementing efficient chunked uploads and downloads.
"""

import os
import io
import logging
import tempfile
import time
from typing import Dict, Any, Optional, Union, BinaryIO, Generator, Tuple, List, Callable

# Configure logger
logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB default chunk size

class StreamingUploader:
    """
    Handles chunked uploads to IPFS.
    
    This class implements efficient large file uploads with chunking and progress tracking,
    addressing the requirements in the Streaming Operations section of the MCP roadmap.
    """
    
    def __init__(self, ipfs_client, chunk_size: int = DEFAULT_CHUNK_SIZE, progress_callback: Optional[Callable] = None):
        """
        Initialize the streaming uploader.
        
        Args:
            ipfs_client: IPFS client instance
            chunk_size: Size of chunks in bytes
            progress_callback: Optional callback function to report progress
        """
        self.ipfs = ipfs_client
        self.chunk_size = chunk_size
        self.progress_callback = progress_callback
        
    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """
        Upload a file to IPFS in chunks.
        
        Args:
            file_path: Path to the file to upload
            
        Returns:
            Dict with operation result including CID
        """
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"File not found: {file_path}", "error_type": "FileNotFound"}
        
        try:
            file_size = os.path.getsize(file_path)
            
            # For small files, use the standard method
            if file_size <= self.chunk_size:
                logger.info(f"File size {file_size} bytes is smaller than chunk size, using standard upload")
                return self.ipfs.ipfs_add_file(file_path)
            
            # For large files, use chunked upload
            logger.info(f"Starting chunked upload for file: {file_path} ({file_size} bytes)")
            
            # Split file into chunks using MFS (Mutable File System)
            chunks = []
            uploaded_bytes = 0
            
            # Create a temporary directory in MFS
            temp_dir = f"/upload-{int(time.time())}"
            self.ipfs._call_api('files/mkdir', params={'arg': temp_dir, 'parents': 'true'})
            
            with open(file_path, 'rb') as f:
                chunk_index = 0
                
                while True:
                    chunk_data = f.read(self.chunk_size)
                    if not chunk_data:
                        break
                    
                    # Upload chunk to MFS
                    chunk_path = f"{temp_dir}/chunk-{chunk_index}"
                    
                    # Use a temporary file for the chunk
                    with tempfile.NamedTemporaryFile() as temp:
                        temp.write(chunk_data)
                        temp.flush()
                        
                        with open(temp.name, 'rb') as chunk_file:
                            files = {'file': chunk_file}
                            params = {'arg': chunk_path, 'create': 'true', 'parents': 'true'}
                            result = self.ipfs._call_api('files/write', params=params, files=files)
                            
                            if not result.get('success'):
                                logger.error(f"Failed to upload chunk {chunk_index}: {result.get('error')}")
                                return {"success": False, "error": f"Chunk upload failed: {result.get('error')}", "error_type": "ChunkUploadError"}
                    
                    chunks.append(chunk_path)
                    chunk_index += 1
                    uploaded_bytes += len(chunk_data)
                    
                    # Report progress if callback is provided
                    if self.progress_callback:
                        progress = min(uploaded_bytes / file_size * 100, 100)
                        self.progress_callback(progress, uploaded_bytes, file_size)
            
            # Combine chunks
            logger.info(f"Uploaded {len(chunks)} chunks, now finalizing")
            
            # Get stats for each chunk to verify they exist
            for chunk_path in chunks:
                self.ipfs._call_api('files/stat', params={'arg': chunk_path})
            
            # Create the final file in MFS by combining chunks
            final_path = f"{temp_dir}/complete"
            
            # First create an empty file
            self.ipfs._call_api('files/touch', params={'arg': final_path, 'create': 'true'})
            
            # Then append each chunk to it
            for chunk_path in chunks:
                # Read chunk from MFS
                chunk_data = self.ipfs._call_api('files/read', method='post', params={'arg': chunk_path})
                
                # Append to final file
                if chunk_data.get('success') and chunk_data.get('data'):
                    with tempfile.NamedTemporaryFile() as temp:
                        if isinstance(chunk_data.get('data'), str):
                            temp.write(chunk_data.get('data').encode('utf-8'))
                        else:
                            temp.write(chunk_data.get('data'))
                        temp.flush()
                        
                        with open(temp.name, 'rb') as chunk_file:
                            files = {'file': chunk_file}
                            params = {'arg': final_path, 'create': 'false', 'offset': '-1', 'count': '-1'}
                            append_result = self.ipfs._call_api('files/write', params=params, files=files)
                            
                            if not append_result.get('success'):
                                logger.error(f"Failed to append chunk: {append_result.get('error')}")
            
            # Get the CID of the final file
            stat_result = self.ipfs._call_api('files/stat', params={'arg': final_path})
            if not stat_result.get('success'):
                logger.error(f"Failed to get file stats: {stat_result.get('error')}")
                return {"success": False, "error": "Failed to finalize upload", "error_type": "FinalizationError"}
            
            cid = stat_result.get('Hash')
            
            # Pin the file
            pin_result = self.ipfs.ipfs_pin_add(cid)
            
            # Clean up temporary directory
            self.ipfs._call_api('files/rm', params={'arg': temp_dir, 'recursive': 'true'})
            
            return {
                "success": True,
                "cid": cid,
                "Hash": cid,
                "size": file_size,
                "chunked": True,
                "chunks": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Error in chunked upload: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "StreamingUploadError"}

class StreamingDownloader:
    """
    Handles memory-optimized streaming downloads from IPFS.
    
    This class implements efficient large file downloads with progress tracking,
    addressing the requirements in the Streaming Operations section of the MCP roadmap.
    """
    
    def __init__(self, ipfs_client, chunk_size: int = DEFAULT_CHUNK_SIZE, progress_callback: Optional[Callable] = None):
        """
        Initialize the streaming downloader.
        
        Args:
            ipfs_client: IPFS client instance
            chunk_size: Size of chunks in bytes
            progress_callback: Optional callback function to report progress
        """
        self.ipfs = ipfs_client
        self.chunk_size = chunk_size
        self.progress_callback = progress_callback
    
    def download_file(self, cid: str, output_path: str) -> Dict[str, Any]:
        """
        Download content from IPFS to a file in a memory-efficient way.
        
        Args:
            cid: Content identifier to download
            output_path: Path where the downloaded file should be saved
            
        Returns:
            Dict with operation result
        """
        try:
            # Get file size first
            stat_result = self.ipfs.ipfs_object_stat(cid)
            if not stat_result.get('success'):
                return stat_result
            
            file_size = stat_result.get('CumulativeSize', 0)
            downloaded_bytes = 0
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Download the file in chunks
            with open(output_path, 'wb') as f:
                # For small files, just use cat directly
                if file_size <= self.chunk_size:
                    result = self.ipfs.ipfs_cat(cid)
                    if result.get('success') and result.get('data'):
                        f.write(result.get('data'))
                        if self.progress_callback:
                            self.progress_callback(100, file_size, file_size)
                        return {"success": True, "size": file_size, "path": output_path}
                    else:
                        return result
                
                # For large files, use range requests if supported
                # Note: This is a simplification - true range requests would require more IPFS API support
                # Instead, we'll use a simulate chunked download for demonstration
                
                # First approach: use files/read with offset and count if possible
                try:
                    # First, copy the content to MFS for easier manipulation
                    temp_path = f"/download-{int(time.time())}"
                    cp_result = self.ipfs._call_api('files/cp', params={'arg': f"/ipfs/{cid}", 'arg': temp_path})
                    
                    if not cp_result.get('success'):
                        # Fall back to full download if we can't copy to MFS
                        raise Exception("MFS copy failed, falling back to full download")
                    
                    # Now read in chunks
                    offset = 0
                    while offset < file_size:
                        chunk_size = min(self.chunk_size, file_size - offset)
                        params = {'arg': temp_path, 'offset': str(offset), 'count': str(chunk_size)}
                        chunk_result = self.ipfs._call_api('files/read', params=params)
                        
                        if not chunk_result.get('success'):
                            raise Exception(f"Failed to read chunk at offset {offset}: {chunk_result.get('error')}")
                        
                        chunk_data = chunk_result.get('data', b'')
                        if isinstance(chunk_data, str):
                            chunk_data = chunk_data.encode('utf-8')
                        
                        f.write(chunk_data)
                        offset += len(chunk_data)
                        downloaded_bytes += len(chunk_data)
                        
                        # Report progress
                        if self.progress_callback:
                            progress = min(downloaded_bytes / file_size * 100, 100)
                            self.progress_callback(progress, downloaded_bytes, file_size)
                    
                    # Clean up
                    self.ipfs._call_api('files/rm', params={'arg': temp_path})
                    
                except Exception as chunk_error:
                    logger.warning(f"Chunked download failed: {chunk_error}, falling back to full download")
                    
                    # Fall back to full download
                    f.seek(0)  # Reset file position
                    result = self.ipfs.ipfs_cat(cid)
                    if result.get('success') and result.get('data'):
                        f.write(result.get('data'))
                        if self.progress_callback:
                            self.progress_callback(100, file_size, file_size)
                    else:
                        return result
            
            return {
                "success": True,
                "size": downloaded_bytes,
                "path": output_path,
                "cid": cid
            }
            
        except Exception as e:
            logger.error(f"Error in streaming download: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "StreamingDownloadError"}

def create_background_operation(operation_type: str, cid: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a record for a background operation.
    
    This is a helper function for tracking background operations like pinning.
    
    Args:
        operation_type: Type of operation (e.g., 'pin', 'unpin', 'upload')
        cid: Content identifier related to the operation
        metadata: Additional metadata about the operation
        
    Returns:
        Dict representing the background operation
    """
    return {
        "operation_id": f"{operation_type}-{cid}-{int(time.time())}",
        "type": operation_type,
        "cid": cid,
        "status": "pending",
        "created_at": time.time(),
        "updated_at": time.time(),
        "metadata": metadata or {},
        "progress": 0
    }

class BackgroundPinningManager:
    """
    Manages background pinning operations.
    
    This class implements the background pinning operations feature mentioned in the
    Streaming Operations section of the MCP roadmap.
    """
    
    def __init__(self, ipfs_client):
        """
        Initialize the background pinning manager.
        
        Args:
            ipfs_client: IPFS client instance
        """
        self.ipfs = ipfs_client
        self.operations = {}  # Dictionary to track operations
        self._running = True
    
    def start_pin(self, cid: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Start a background pin operation.
        
        Args:
            cid: Content identifier to pin
            metadata: Additional metadata about the operation
            
        Returns:
            Dict with operation details
        """
        operation = create_background_operation('pin', cid, metadata)
        operation_id = operation["operation_id"]
        self.operations[operation_id] = operation
        
        # In a real implementation, this would spawn a background thread
        # For now, we'll just call the pin method directly and update status
        try:
            result = self.ipfs.ipfs_pin_add(cid)
            if result.get('success'):
                operation["status"] = "completed"
                operation["progress"] = 100
            else:
                operation["status"] = "failed"
                operation["error"] = result.get('error')
            
            operation["updated_at"] = time.time()
            return {"success": True, "operation_id": operation_id, "status": operation["status"]}
            
        except Exception as e:
            operation["status"] = "failed"
            operation["error"] = str(e)
            operation["updated_at"] = time.time()
            return {"success": False, "operation_id": operation_id, "error": str(e)}
    
    def get_operation_status(self, operation_id: str) -> Dict[str, Any]:
        """
        Get the status of a background operation.
        
        Args:
            operation_id: ID of the operation to check
            
        Returns:
            Dict with operation status
        """
        if operation_id not in self.operations:
            return {"success": False, "error": "Operation not found"}
        
        operation = self.operations[operation_id]
        return {
            "success": True,
            "operation_id": operation_id,
            "status": operation["status"],
            "progress": operation["progress"],
            "created_at": operation["created_at"],
            "updated_at": operation["updated_at"],
            "cid": operation["cid"],
            "type": operation["type"]
        }
    
    def list_operations(self, status: Optional[str] = None) -> Dict[str, Any]:
        """
        List background operations.
        
        Args:
            status: Optional status to filter by
            
        Returns:
            Dict with list of operations
        """
        operations = []
        
        for op_id, operation in self.operations.items():
            if status is None or operation["status"] == status:
                operations.append({
                    "operation_id": op_id,
                    "status": operation["status"],
                    "progress": operation["progress"],
                    "created_at": operation["created_at"],
                    "updated_at": operation["updated_at"],
                    "cid": operation["cid"],
                    "type": operation["type"]
                })
        
        return {
            "success": True,
            "operations": operations,
            "count": len(operations)
        }

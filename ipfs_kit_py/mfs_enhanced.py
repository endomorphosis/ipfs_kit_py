"""
Enhanced MFS (Mutable File System) operations for IPFS.

This module extends the basic MFS operations with advanced features such as:
1. Directory synchronization between local and IPFS MFS
2. Automatic content type detection
3. Transaction support for atomic operations 
4. Path utilities for MFS manipulation
5. Content monitoring and change tracking
"""

import os
import time
import json
import mimetypes
import logging
import threading
import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Union, Callable, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize mimetype detection
mimetypes.init()

class MFSTransaction:
    """
    Transaction support for atomic MFS operations.
    
    Allows grouping multiple MFS operations to be committed together
    or rolled back as a unit if any operation fails.
    """
    
    def __init__(self, ipfs_client):
        """Initialize a new MFS transaction."""
        self.ipfs_client = ipfs_client
        self.operations = []
        self.backup_data = {}
        self.success = None
        self._active = False
    
    def __enter__(self):
        """Start the transaction when used as a context manager."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete the transaction when exiting the context manager."""
        if exc_type is not None:
            # An exception occurred, roll back
            self.rollback()
            return False
        
        # No exception, commit the transaction
        try:
            self.commit()
            return True
        except Exception:
            # Commit failed, roll back
            self.rollback()
            return False
    
    def start(self):
        """Start a new transaction."""
        if self._active:
            raise RuntimeError("Transaction already started")
        
        self._active = True
        self.operations = []
        self.backup_data = {}
        self.success = None
        return self
    
    def add_operation(self, operation_type: str, path: str, **kwargs):
        """
        Add an operation to the transaction.
        
        Args:
            operation_type: Type of operation (write, mkdir, rm, cp, mv)
            path: Path in MFS affected by the operation
            kwargs: Additional operation-specific parameters
        """
        if not self._active:
            raise RuntimeError("Transaction not active")
        
        # Record the operation
        operation = {
            "type": operation_type,
            "path": path,
            "params": kwargs,
            "timestamp": time.time()
        }
        
        # For operations that modify existing content, back up the original
        if operation_type in ("write", "rm", "mv"):
            try:
                # Check if the file/directory exists before backing up
                if path == "/" or path == "":
                    # Don't back up root
                    pass
                else:
                    # Try to stat the path to see if it exists
                    try:
                        stat_result = self.ipfs_client.files_stat(path)
                        if stat_result.get("success", False):
                            # Path exists, back it up
                            if stat_result.get("type") == "file":
                                # Back up file content
                                read_result = self.ipfs_client.files_read(path)
                                if read_result.get("success", False):
                                    self.backup_data[path] = {
                                        "type": "file",
                                        "content": read_result.get("data", b""),
                                        "stat": stat_result
                                    }
                            elif stat_result.get("type") == "directory":
                                # Just record that the directory exists
                                self.backup_data[path] = {
                                    "type": "directory",
                                    "stat": stat_result
                                }
                    except Exception as e:
                        logger.warning(f"Could not backup path {path} before transaction: {e}")
            except Exception as e:
                logger.warning(f"Error backing up data for path {path}: {e}")
        
        # Add the operation to the list
        self.operations.append(operation)
    
    def commit(self):
        """
        Commit all operations in the transaction.
        
        If any operation fails, roll back all changes.
        """
        if not self._active:
            raise RuntimeError("Transaction not active")
        
        if not self.operations:
            # Empty transaction
            self._active = False
            self.success = True
            return True
        
        # Execute all operations in order
        try:
            for operation in self.operations:
                op_type = operation["type"]
                path = operation["path"]
                params = operation["params"]
                
                # Execute the operation based on type
                if op_type == "write":
                    result = self.ipfs_client.files_write(
                        path=path,
                        content=params.get("content", b""),
                        offset=params.get("offset", 0),
                        create=params.get("create", True),
                        truncate=params.get("truncate", True),
                        parents=params.get("parents", False)
                    )
                elif op_type == "mkdir":
                    result = self.ipfs_client.files_mkdir(
                        path=path,
                        parents=params.get("parents", False)
                    )
                elif op_type == "rm":
                    result = self.ipfs_client.files_rm(
                        path=path,
                        recursive=params.get("recursive", False),
                        force=params.get("force", False)
                    )
                elif op_type == "cp":
                    result = self.ipfs_client.files_cp(
                        source=path,
                        destination=params.get("destination", ""),
                        parents=params.get("parents", False)
                    )
                elif op_type == "mv":
                    result = self.ipfs_client.files_mv(
                        source=path,
                        destination=params.get("destination", ""),
                        parents=params.get("parents", False)
                    )
                else:
                    raise ValueError(f"Unknown operation type: {op_type}")
                
                # Check if the operation succeeded
                if not result.get("success", False):
                    raise RuntimeError(f"Transaction operation failed: {op_type} {path} - {result.get('error', 'Unknown error')}")
            
            # Flush MFS changes to IPFS
            flush_result = self.ipfs_client.files_flush("/")
            if not flush_result.get("success", False):
                raise RuntimeError(f"Failed to flush MFS changes: {flush_result.get('error', 'Unknown error')}")
            
            # All operations completed successfully
            self._active = False
            self.success = True
            return True
            
        except Exception as e:
            # An error occurred, roll back all changes
            logger.error(f"Transaction failed, rolling back: {e}")
            self.rollback()
            raise
    
    def rollback(self):
        """
        Roll back all changes made by the transaction.
        
        Restores files and directories to their state before the transaction.
        """
        if not self._active:
            return False
        
        logger.info("Rolling back transaction")
        
        # Restore backups in reverse order to handle dependencies correctly
        # Sort paths by length in descending order to handle child paths before parents
        paths = sorted(self.backup_data.keys(), key=len, reverse=True)
        
        for path in paths:
            backup = self.backup_data[path]
            
            try:
                if backup["type"] == "file":
                    # Ensure parent directories exist
                    parent_dir = os.path.dirname(path)
                    if parent_dir and parent_dir != "/":
                        try:
                            self.ipfs_client.files_mkdir(parent_dir, parents=True)
                        except Exception as e:
                            logger.warning(f"Could not create parent directories for rollback: {e}")
                    
                    # Restore file content
                    self.ipfs_client.files_write(
                        path=path,
                        content=backup["content"],
                        create=True,
                        truncate=True
                    )
                elif backup["type"] == "directory":
                    # Ensure directory exists
                    try:
                        self.ipfs_client.files_mkdir(path, parents=True)
                    except Exception as e:
                        logger.warning(f"Could not restore directory during rollback: {e}")
            except Exception as e:
                logger.error(f"Error during transaction rollback for path {path}: {e}")
        
        # Mark transaction as complete
        self._active = False
        self.success = False
        return True


class DirectorySynchronizer:
    """
    Synchronizes content between a local directory and IPFS MFS.
    
    Provides bidirectional sync functionality to keep local and IPFS files in sync.
    """
    
    def __init__(self, ipfs_client, local_path, mfs_path):
        """
        Initialize the directory synchronizer.
        
        Args:
            ipfs_client: IPFS client instance for MFS operations
            local_path: Path to local directory
            mfs_path: Path in IPFS MFS to synchronize with
        """
        self.ipfs_client = ipfs_client
        self.local_path = os.path.abspath(local_path)
        self.mfs_path = mfs_path.rstrip("/")
        self.sync_history = {}
        self.lock = threading.RLock()
        
        # Create MFS directory if it doesn't exist
        try:
            mkdir_result = self.ipfs_client.files_mkdir(self.mfs_path, parents=True)
            if not mkdir_result.get("success", False):
                logger.warning(f"Could not create MFS directory {self.mfs_path}: {mkdir_result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.warning(f"Error creating MFS directory {self.mfs_path}: {e}")
    
    def sync_to_mfs(self, filter_func=None, preserve_history=True, delete_extraneous=False):
        """
        Synchronize local directory to MFS.
        
        Args:
            filter_func: Optional function to filter files (returns True for files to include)
            preserve_history: Whether to preserve sync history for incremental syncs
            delete_extraneous: Whether to delete files in MFS that don't exist locally
            
        Returns:
            Dictionary with sync results
        """
        start_time = time.time()
        
        with self.lock:
            result = {
                "success": False,
                "operation": "sync_to_mfs",
                "timestamp": start_time,
                "local_path": self.local_path,
                "mfs_path": self.mfs_path,
                "files_synced": 0,
                "dirs_created": 0,
                "bytes_transferred": 0,
                "files_skipped": 0,
                "errors": []
            }
            
            try:
                # Use a transaction for atomic operations
                with MFSTransaction(self.ipfs_client) as transaction:
                    # Get list of local files
                    local_files = self._get_local_files(filter_func)
                    
                    # Process each local file
                    for rel_path, file_info in local_files.items():
                        local_file_path = os.path.join(self.local_path, rel_path)
                        mfs_file_path = os.path.join(self.mfs_path, rel_path).replace("\\", "/")
                        
                        # Check if file has changed since last sync
                        if preserve_history and rel_path in self.sync_history:
                            last_sync = self.sync_history[rel_path]
                            if last_sync["local_mtime"] == file_info["mtime"] and last_sync["local_size"] == file_info["size"]:
                                # File hasn't changed, skip it
                                result["files_skipped"] += 1
                                continue
                        
                        try:
                            # Ensure parent directory exists
                            parent_dir = os.path.dirname(mfs_file_path)
                            if parent_dir and parent_dir != "/" and parent_dir != self.mfs_path:
                                transaction.add_operation("mkdir", parent_dir, parents=True)
                            
                            # Read file content
                            with open(local_file_path, "rb") as f:
                                file_content = f.read()
                            
                            # Write file to MFS
                            transaction.add_operation("write", mfs_file_path, content=file_content, create=True, truncate=True)
                            
                            # Update sync history
                            if preserve_history:
                                self.sync_history[rel_path] = {
                                    "local_mtime": file_info["mtime"],
                                    "local_size": file_info["size"],
                                    "last_sync": time.time()
                                }
                            
                            result["files_synced"] += 1
                            result["bytes_transferred"] += file_info["size"]
                            
                        except Exception as e:
                            error = f"Error syncing file {local_file_path} to MFS: {str(e)}"
                            result["errors"].append(error)
                            logger.error(error)
                    
                    # Delete extraneous files if requested
                    if delete_extraneous:
                        # Get list of MFS files
                        mfs_files = self._get_mfs_files(self.mfs_path)
                        
                        # Find files in MFS that don't exist locally
                        local_rel_paths = set(local_files.keys())
                        mfs_rel_paths = set(mfs_files.keys())
                        extraneous_paths = mfs_rel_paths - local_rel_paths
                        
                        # Delete extraneous files
                        for rel_path in extraneous_paths:
                            mfs_file_path = os.path.join(self.mfs_path, rel_path).replace("\\", "/")
                            try:
                                transaction.add_operation("rm", mfs_file_path, recursive=True, force=True)
                                
                                # Remove from sync history
                                if preserve_history and rel_path in self.sync_history:
                                    del self.sync_history[rel_path]
                                    
                            except Exception as e:
                                error = f"Error deleting extraneous file {mfs_file_path} from MFS: {str(e)}"
                                result["errors"].append(error)
                                logger.error(error)
                
                # Transaction will be committed automatically if no errors occur
                
                # Update result
                result["success"] = True
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            except Exception as e:
                # Transaction will be rolled back automatically
                result["error"] = f"Sync to MFS failed: {str(e)}"
                result["error_type"] = "sync_error"
                result["duration_ms"] = (time.time() - start_time) * 1000
                logger.error(f"Error during sync to MFS: {e}")
                
            return result
    
    def sync_from_mfs(self, filter_func=None, preserve_history=True, delete_extraneous=False):
        """
        Synchronize MFS directory to local filesystem.
        
        Args:
            filter_func: Optional function to filter files (returns True for files to include)
            preserve_history: Whether to preserve sync history for incremental syncs
            delete_extraneous: Whether to delete local files that don't exist in MFS
            
        Returns:
            Dictionary with sync results
        """
        start_time = time.time()
        
        with self.lock:
            result = {
                "success": False,
                "operation": "sync_from_mfs",
                "timestamp": start_time,
                "local_path": self.local_path,
                "mfs_path": self.mfs_path,
                "files_synced": 0,
                "dirs_created": 0,
                "bytes_transferred": 0,
                "files_skipped": 0,
                "errors": []
            }
            
            try:
                # Get list of MFS files
                mfs_files = self._get_mfs_files(self.mfs_path, filter_func)
                
                # Process each MFS file
                for rel_path, file_info in mfs_files.items():
                    local_file_path = os.path.join(self.local_path, rel_path)
                    mfs_file_path = os.path.join(self.mfs_path, rel_path).replace("\\", "/")
                    
                    # Check if file has changed since last sync
                    if preserve_history and rel_path in self.sync_history:
                        last_sync = self.sync_history[rel_path]
                        if "mfs_mtime" in last_sync and last_sync["mfs_mtime"] == file_info["mtime"]:
                            # File hasn't changed, skip it
                            result["files_skipped"] += 1
                            continue
                    
                    try:
                        # Ensure parent directory exists
                        parent_dir = os.path.dirname(local_file_path)
                        if parent_dir and not os.path.exists(parent_dir):
                            os.makedirs(parent_dir, exist_ok=True)
                            result["dirs_created"] += 1
                        
                        # Read file content from MFS
                        read_result = self.ipfs_client.files_read(mfs_file_path)
                        if not read_result.get("success", False):
                            raise RuntimeError(f"Failed to read file {mfs_file_path} from MFS: {read_result.get('error', 'Unknown error')}")
                        
                        file_content = read_result.get("data", b"")
                        
                        # Write file to local filesystem
                        with open(local_file_path, "wb") as f:
                            f.write(file_content)
                        
                        # Update sync history
                        if preserve_history:
                            self.sync_history[rel_path] = {
                                "mfs_mtime": file_info["mtime"],
                                "mfs_size": file_info["size"],
                                "last_sync": time.time()
                            }
                        
                        result["files_synced"] += 1
                        result["bytes_transferred"] += file_info["size"]
                        
                    except Exception as e:
                        error = f"Error syncing file {mfs_file_path} from MFS: {str(e)}"
                        result["errors"].append(error)
                        logger.error(error)
                
                # Delete extraneous files if requested
                if delete_extraneous:
                    # Get list of local files
                    local_files = self._get_local_files()
                    
                    # Find files locally that don't exist in MFS
                    local_rel_paths = set(local_files.keys())
                    mfs_rel_paths = set(mfs_files.keys())
                    extraneous_paths = local_rel_paths - mfs_rel_paths
                    
                    # Delete extraneous files
                    for rel_path in extraneous_paths:
                        local_file_path = os.path.join(self.local_path, rel_path)
                        try:
                            if os.path.isdir(local_file_path):
                                shutil.rmtree(local_file_path)
                            else:
                                os.remove(local_file_path)
                                
                            # Remove from sync history
                            if preserve_history and rel_path in self.sync_history:
                                del self.sync_history[rel_path]
                                
                        except Exception as e:
                            error = f"Error deleting extraneous file {local_file_path} locally: {str(e)}"
                            result["errors"].append(error)
                            logger.error(error)
                
                # Update result
                result["success"] = True
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            except Exception as e:
                result["error"] = f"Sync from MFS failed: {str(e)}"
                result["error_type"] = "sync_error"
                result["duration_ms"] = (time.time() - start_time) * 1000
                logger.error(f"Error during sync from MFS: {e}")
                
            return result
    
    def _get_local_files(self, filter_func=None):
        """
        Get list of files in local directory.
        
        Args:
            filter_func: Optional function to filter files (returns True for files to include)
            
        Returns:
            Dictionary mapping relative paths to file information
        """
        files = {}
        
        for root, dirs, filenames in os.walk(self.local_path):
            # Calculate relative path
            rel_root = os.path.relpath(root, self.local_path)
            if rel_root == ".":
                rel_root = ""
                
            # Process each file
            for filename in filenames:
                rel_path = os.path.join(rel_root, filename)
                full_path = os.path.join(root, filename)
                
                # Apply filter if provided
                if filter_func and not filter_func(rel_path, full_path):
                    continue
                
                # Get file info
                file_stat = os.stat(full_path)
                files[rel_path] = {
                    "size": file_stat.st_size,
                    "mtime": file_stat.st_mtime,
                    "path": full_path
                }
                
        return files
    
    def _get_mfs_files(self, base_path, filter_func=None):
        """
        Get list of files in MFS directory.
        
        Args:
            base_path: Base path in MFS to list files from
            filter_func: Optional function to filter files (returns True for files to include)
            
        Returns:
            Dictionary mapping relative paths to file information
        """
        files = {}
        
        def _process_directory(path):
            # List directory
            ls_result = self.ipfs_client.files_ls(path, long=True)
            if not ls_result.get("success", False):
                logger.warning(f"Failed to list MFS directory {path}: {ls_result.get('error', 'Unknown error')}")
                return
            
            # Process entries
            entries = ls_result.get("entries", [])
            for entry in entries:
                name = entry.get("Name", "")
                entry_type = entry.get("Type", 0)
                entry_path = os.path.join(path, name).replace("\\", "/")
                
                # Calculate relative path
                if path == self.mfs_path:
                    rel_path = name
                else:
                    rel_path = os.path.relpath(entry_path, self.mfs_path)
                
                # Process based on type
                if entry_type == 1:  # Directory
                    # Recursively process subdirectory
                    _process_directory(entry_path)
                else:  # File
                    # Get file stats
                    stat_result = self.ipfs_client.files_stat(entry_path)
                    if not stat_result.get("success", False):
                        logger.warning(f"Failed to stat MFS file {entry_path}: {stat_result.get('error', 'Unknown error')}")
                        continue
                    
                    size = stat_result.get("size", 0)
                    hash_cid = stat_result.get("hash", stat_result.get("cid", ""))
                    
                    # Apply filter if provided
                    if filter_func and not filter_func(rel_path, entry_path):
                        continue
                    
                    # Add to files dictionary
                    files[rel_path] = {
                        "size": size,
                        "mtime": time.time(),  # MFS doesn't have mtime, use current time
                        "hash": hash_cid,
                        "path": entry_path
                    }
        
        # Start processing from base path
        _process_directory(base_path)
        
        return files


class ContentTypeDetector:
    """
    Detects content types for files in MFS.
    
    Provides MIME type detection based on file extensions and content analysis.
    Allows more intelligent handling of files based on their content type.
    """
    
    def __init__(self, ipfs_client):
        """
        Initialize the content type detector.
        
        Args:
            ipfs_client: IPFS client instance for MFS operations
        """
        self.ipfs_client = ipfs_client
        
        # Initialize mime type detection
        mimetypes.init()
        
        # Add common additional types that might be missing
        self._add_additional_types()
    
    def _add_additional_types(self):
        """Add additional MIME types that might be missing from the system database."""
        additional_types = {
            '.md': 'text/markdown',
            '.ipynb': 'application/x-ipynb+json',
            '.avif': 'image/avif',
            '.webp': 'image/webp',
            '.wasm': 'application/wasm',
            '.toml': 'application/toml',
            '.yaml': 'application/yaml',
            '.yml': 'application/yaml',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
            '.tsx': 'application/typescript',
            '.jsx': 'text/jsx',
        }
        
        for ext, mime_type in additional_types.items():
            mimetypes.add_type(mime_type, ext)
    
    def detect_from_filename(self, filename):
        """
        Detect content type based on filename.
        
        Args:
            filename: Filename or path to detect type from
            
        Returns:
            Detected MIME type or 'application/octet-stream' if unknown
        """
        content_type, encoding = mimetypes.guess_type(filename)
        return content_type or 'application/octet-stream'
    
    def detect_from_content(self, content):
        """
        Detect content type based on file content.
        
        Args:
            content: File content as bytes
            
        Returns:
            Detected MIME type or 'application/octet-stream' if unknown
        """
        # Check for common file signatures
        if not content or len(content) < 4:
            return 'application/octet-stream'
        
        # Check for text
        is_text = True
        for byte in content[:1024]:  # Check first 1KB
            if byte > 127:  # Non-ASCII character
                is_text = False
                break
        
        if is_text:
            # Check for common text formats
            content_str = content[:1024].decode('utf-8', errors='ignore')
            
            # Check for JSON
            if content_str.strip().startswith('{') and content_str.strip().endswith('}'):
                return 'application/json'
            if content_str.strip().startswith('[') and content_str.strip().endswith(']'):
                return 'application/json'
            
            # Check for XML/HTML
            if content_str.strip().startswith('<') and content_str.strip().endswith('>'):
                if '<html' in content_str.lower():
                    return 'text/html'
                return 'application/xml'
            
            # Default to plain text
            return 'text/plain'
        
        # Check for common binary formats
        signatures = {
            b'\xFF\xD8\xFF': 'image/jpeg',
            b'\x89PNG\r\n\x1A\n': 'image/png',
            b'GIF8': 'image/gif',
            b'%PDF': 'application/pdf',
            b'PK\x03\x04': 'application/zip',
            b'\x1F\x8B\x08': 'application/gzip',
            b'\x42\x5A\x68': 'application/x-bzip2',
            b'\x52\x61\x72\x21\x1A\x07': 'application/x-rar-compressed',
            b'\x50\x4B\x03\x04\x14\x00\x06\x00': 'application/vnd.openxmlformats-officedocument',
            b'\x7F\x45\x4C\x46': 'application/x-elf',
            b'\xED\xAB\xEE\xDB': 'application/x-rpm',
            b'\x4D\x5A': 'application/x-msdownload',  # EXE files
            b'\xCA\xFE\xBA\xBE': 'application/java-archive',  # JAR files
            b'\x00\x00\x01\x00': 'image/x-icon',  # ICO files
            b'\x4F\x67\x67\x53': 'application/ogg',  # OGG files
            b'\x49\x44\x33': 'audio/mpeg',  # MP3 files with ID3 tag
            b'\xFF\xFB': 'audio/mpeg',  # MP3 files without ID3 tag
        }
        
        for signature, mime_type in signatures.items():
            if content.startswith(signature):
                return mime_type
        
        # Default to binary
        return 'application/octet-stream'
    
    def detect_and_set_xattr(self, path, detect_from_content=True):
        """
        Detect content type for a file and set it as extended attribute.
        
        Args:
            path: Path to file in MFS
            detect_from_content: Whether to analyze content for more accurate detection
            
        Returns:
            Dictionary with detection results
        """
        result = {
            "success": False,
            "operation": "detect_content_type",
            "timestamp": time.time(),
            "path": path
        }
        
        try:
            # Detect based on filename first
            content_type_from_name = self.detect_from_filename(path)
            result["mime_type_from_name"] = content_type_from_name
            
            # If requested, also detect from content
            if detect_from_content:
                # Read file content
                read_result = self.ipfs_client.files_read(path)
                if not read_result.get("success", False):
                    raise RuntimeError(f"Failed to read file {path} from MFS: {read_result.get('error', 'Unknown error')}")
                
                content = read_result.get("data", b"")
                content_type_from_content = self.detect_from_content(content)
                result["mime_type_from_content"] = content_type_from_content
                
                # Use content-based detection if it's more specific
                if content_type_from_content != 'application/octet-stream':
                    result["mime_type"] = content_type_from_content
                else:
                    result["mime_type"] = content_type_from_name
            else:
                result["mime_type"] = content_type_from_name
            
            # Set extended attribute on MFS file
            # Note: IPFS MFS doesn't directly support extended attributes like xattrs,
            # so this would need to be implemented as a custom solution, e.g., using a
            # separate metadata file or wrapping in a directory with metadata.
            # For now, we just return the detected type.
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Content type detection failed: {str(e)}"
            result["error_type"] = "detection_error"
            logger.error(f"Error detecting content type for {path}: {e}")
            
        return result


class PathUtils:
    """
    Utilities for working with MFS paths.
    """
    
    @staticmethod
    def join_paths(*paths):
        """
        Join MFS paths, ensuring proper formatting.
        
        Args:
            *paths: Path components to join
            
        Returns:
            Joined path with proper formatting
        """
        # Filter out empty segments
        path_segments = [p for p in paths if p]
        
        # Join with forward slashes
        result = "/".join(path_segments)
        
        # Ensure path starts with /
        if not result.startswith("/"):
            result = "/" + result
            
        # Normalize multiple slashes
        while "//" in result:
            result = result.replace("//", "/")
            
        return result
    
    @staticmethod
    def get_parent_dir(path):
        """
        Get parent directory of a path.
        
        Args:
            path: Path to get parent of
            
        Returns:
            Parent directory path
        """
        if path == "/" or not path:
            return "/"
            
        path = path.rstrip("/")
        parent = os.path.dirname(path)
        
        # Ensure root directory is represented as /
        if not parent:
            return "/"
            
        return parent
    
    @staticmethod
    def get_basename(path):
        """
        Get the basename of a path.
        
        Args:
            path: Path to get basename from
            
        Returns:
            Basename (filename) from the path
        """
        if path == "/" or not path:
            return ""
            
        path = path.rstrip("/")
        return os.path.basename(path)
    
    @staticmethod
    def split_path(path):
        """
        Split path into components.
        
        Args:
            path: Path to split
            
        Returns:
            List of path components
        """
        if path == "/" or not path:
            return []
            
        path = path.strip("/")
        if not path:
            return []
            
        return path.split("/")
    
    @staticmethod
    def is_subpath(path, parent_path):
        """
        Check if a path is a subpath of another.
        
        Args:
            path: Path to check
            parent_path: Potential parent path
            
        Returns:
            True if path is a subpath of parent_path, False otherwise
        """
        # Normalize paths
        path = path.rstrip("/")
        parent_path = parent_path.rstrip("/")
        
        # Special case for root
        if parent_path == "/":
            return path.startswith("/")
            
        # Check if path starts with parent_path plus a slash
        return path.startswith(f"{parent_path}/") or path == parent_path


class MFSChangeWatcher:
    """
    Watches for changes in MFS directories and files.
    
    Provides functionality to monitor MFS paths for changes and trigger callbacks.
    """
    
    def __init__(self, ipfs_client, poll_interval=5):
        """
        Initialize the change watcher.
        
        Args:
            ipfs_client: IPFS client instance for MFS operations
            poll_interval: Time in seconds between polling for changes
        """
        self.ipfs_client = ipfs_client
        self.poll_interval = poll_interval
        self.watches = {}
        self.watch_thread = None
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
    
    def start(self):
        """Start the change watcher thread."""
        if self.watch_thread and self.watch_thread.is_alive():
            return
            
        self.stop_event.clear()
        self.watch_thread = threading.Thread(target=self._watch_loop)
        self.watch_thread.daemon = True
        self.watch_thread.start()
    
    def stop(self):
        """Stop the change watcher thread."""
        if not self.watch_thread or not self.watch_thread.is_alive():
            return
            
        self.stop_event.set()
        self.watch_thread.join(timeout=self.poll_interval * 2)
    
    def add_watch(self, path, callback, recursive=True):
        """
        Add a watch for a path.
        
        Args:
            path: Path in MFS to watch
            callback: Function to call when changes are detected
            recursive: Whether to watch subdirectories recursively
            
        Returns:
            Watch ID for removing the watch later
        """
        with self.lock:
            # Get initial state
            try:
                initial_state = self._get_path_state(path, recursive)
            except Exception as e:
                logger.error(f"Error getting initial state for watched path {path}: {e}")
                initial_state = {}
            
            # Create watch ID
            watch_id = str(uuid.uuid4())
            
            # Add to watches
            self.watches[watch_id] = {
                "path": path,
                "callback": callback,
                "recursive": recursive,
                "last_state": initial_state,
                "created": time.time()
            }
            
            # Start watching if not already started
            self.start()
            
            return watch_id
    
    def remove_watch(self, watch_id):
        """
        Remove a watch.
        
        Args:
            watch_id: ID of the watch to remove
            
        Returns:
            True if watch was removed, False if not found
        """
        with self.lock:
            if watch_id in self.watches:
                del self.watches[watch_id]
                
                # Stop watching if no watches left
                if not self.watches:
                    self.stop()
                    
                return True
                
            return False
    
    def _get_path_state(self, path, recursive=True):
        """
        Get the current state of a path in MFS.
        
        Args:
            path: Path in MFS to get state for
            recursive: Whether to check subdirectories recursively
            
        Returns:
            Dictionary mapping paths to state information
        """
        state = {}
        
        # Get stat for the path
        stat_result = self.ipfs_client.files_stat(path)
        if not stat_result.get("success", False):
            logger.warning(f"Failed to stat MFS path {path}: {stat_result.get('error', 'Unknown error')}")
            return state
        
        # Add path state
        state[path] = {
            "type": stat_result.get("type", "unknown"),
            "size": stat_result.get("size", 0),
            "hash": stat_result.get("hash", stat_result.get("cid", "")),
            "time": time.time()
        }
        
        # If it's a directory and recursive is True, get subdirectory state
        if stat_result.get("type") == "directory" and recursive:
            # List directory
            ls_result = self.ipfs_client.files_ls(path, long=True)
            if not ls_result.get("success", False):
                logger.warning(f"Failed to list MFS directory {path}: {ls_result.get('error', 'Unknown error')}")
                return state
            
            # Process entries
            entries = ls_result.get("entries", [])
            for entry in entries:
                name = entry.get("Name", "")
                entry_path = PathUtils.join_paths(path, name)
                
                # Recursively get state for subdirectories
                substate = self._get_path_state(entry_path, recursive)
                state.update(substate)
        
        return state
    
    def _watch_loop(self):
        """Main watching loop that polls for changes."""
        logger.info("MFS change watcher started")
        
        while not self.stop_event.is_set():
            try:
                with self.lock:
                    # Process each watch
                    for watch_id, watch in self.watches.items():
                        try:
                            # Get current state
                            current_state = self._get_path_state(watch["path"], watch["recursive"])
                            
                            # Compare with last state
                            last_state = watch["last_state"]
                            changes = self._detect_changes(last_state, current_state)
                            
                            # If changes detected, call callback
                            if changes["added"] or changes["modified"] or changes["removed"]:
                                try:
                                    watch["callback"](changes)
                                except Exception as e:
                                    logger.error(f"Error in watch callback for path {watch['path']}: {e}")
                            
                            # Update last state
                            watch["last_state"] = current_state
                            
                        except Exception as e:
                            logger.error(f"Error processing watch for path {watch['path']}: {e}")
                
            except Exception as e:
                logger.error(f"Error in MFS change watcher loop: {e}")
            
            # Wait for next poll
            if not self.stop_event.wait(self.poll_interval):
                continue
        
        logger.info("MFS change watcher stopped")
    
    def _detect_changes(self, old_state, new_state):
        """
        Detect changes between two states.
        
        Args:
            old_state: Previous state dictionary
            new_state: Current state dictionary
            
        Returns:
            Dictionary with added, modified, and removed paths
        """
        changes = {
            "added": [],
            "modified": [],
            "removed": []
        }
        
        # Find added and modified paths
        for path, state in new_state.items():
            if path not in old_state:
                changes["added"].append(path)
            elif state["hash"] != old_state[path]["hash"]:
                changes["modified"].append(path)
        
        # Find removed paths
        for path in old_state:
            if path not in new_state:
                changes["removed"].append(path)
        
        return changes


# Helper functions for MFS operations

def compute_file_hash(content):
    """
    Compute a hash for file content.
    
    Args:
        content: File content to hash
        
    Returns:
        SHA-256 hash digest of the content
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    
    return hashlib.sha256(content).hexdigest()

def create_empty_directory_structure(ipfs_client, base_path, paths):
    """
    Create a directory structure in MFS.
    
    Args:
        ipfs_client: IPFS client instance for MFS operations
        base_path: Base path in MFS to create directories under
        paths: List of relative directory paths to create
        
    Returns:
        Dictionary with operation results
    """
    start_time = time.time()
    
    result = {
        "success": False,
        "operation": "create_directory_structure",
        "timestamp": start_time,
        "base_path": base_path,
        "directories_created": 0,
        "errors": []
    }
    
    try:
        # Use a transaction for atomic operations
        with MFSTransaction(ipfs_client) as transaction:
            # Create base directory if it doesn't exist
            if base_path and base_path != "/":
                transaction.add_operation("mkdir", base_path, parents=True)
                result["directories_created"] += 1
            
            # Create each directory
            for path in paths:
                mfs_path = PathUtils.join_paths(base_path, path)
                try:
                    transaction.add_operation("mkdir", mfs_path, parents=True)
                    result["directories_created"] += 1
                except Exception as e:
                    error = f"Error creating directory {mfs_path}: {str(e)}"
                    result["errors"].append(error)
                    logger.error(error)
        
        # Transaction will be committed automatically if no errors occur
        
        # Update result
        result["success"] = True
        result["duration_ms"] = (time.time() - start_time) * 1000
        
    except Exception as e:
        # Transaction will be rolled back automatically
        result["error"] = f"Directory structure creation failed: {str(e)}"
        result["error_type"] = "mkdir_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(f"Error creating directory structure: {e}")
        
    return result

def copy_content_batch(ipfs_client, operations):
    """
    Perform a batch of copy operations in MFS.
    
    Args:
        ipfs_client: IPFS client instance for MFS operations
        operations: List of dictionaries with source, destination, and parents keys
        
    Returns:
        Dictionary with operation results
    """
    start_time = time.time()
    
    result = {
        "success": False,
        "operation": "copy_content_batch",
        "timestamp": start_time,
        "operations_count": len(operations),
        "successful_operations": 0,
        "errors": []
    }
    
    try:
        # Use a transaction for atomic operations
        with MFSTransaction(ipfs_client) as transaction:
            # Process each operation
            for op in operations:
                source = op.get("source", "")
                destination = op.get("destination", "")
                parents = op.get("parents", False)
                
                if not source or not destination:
                    error = "Source and destination paths are required"
                    result["errors"].append(error)
                    logger.error(error)
                    continue
                
                try:
                    transaction.add_operation("cp", source, destination=destination, parents=parents)
                    result["successful_operations"] += 1
                except Exception as e:
                    error = f"Error copying from {source} to {destination}: {str(e)}"
                    result["errors"].append(error)
                    logger.error(error)
        
        # Transaction will be committed automatically if no errors occur
        
        # Update result
        result["success"] = True
        result["duration_ms"] = (time.time() - start_time) * 1000
        
    except Exception as e:
        # Transaction will be rolled back automatically
        result["error"] = f"Batch copy operation failed: {str(e)}"
        result["error_type"] = "copy_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(f"Error in batch copy operation: {e}")
        
    return result

def move_content_batch(ipfs_client, operations):
    """
    Perform a batch of move operations in MFS.
    
    Args:
        ipfs_client: IPFS client instance for MFS operations
        operations: List of dictionaries with source, destination, and parents keys
        
    Returns:
        Dictionary with operation results
    """
    start_time = time.time()
    
    result = {
        "success": False,
        "operation": "move_content_batch",
        "timestamp": start_time,
        "operations_count": len(operations),
        "successful_operations": 0,
        "errors": []
    }
    
    try:
        # Use a transaction for atomic operations
        with MFSTransaction(ipfs_client) as transaction:
            # Process each operation
            for op in operations:
                source = op.get("source", "")
                destination = op.get("destination", "")
                parents = op.get("parents", False)
                
                if not source or not destination:
                    error = "Source and destination paths are required"
                    result["errors"].append(error)
                    logger.error(error)
                    continue
                
                try:
                    transaction.add_operation("mv", source, destination=destination, parents=parents)
                    result["successful_operations"] += 1
                except Exception as e:
                    error = f"Error moving from {source} to {destination}: {str(e)}"
                    result["errors"].append(error)
                    logger.error(error)
        
        # Transaction will be committed automatically if no errors occur
        
        # Update result
        result["success"] = True
        result["duration_ms"] = (time.time() - start_time) * 1000
        
    except Exception as e:
        # Transaction will be rolled back automatically
        result["error"] = f"Batch move operation failed: {str(e)}"
        result["error_type"] = "move_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(f"Error in batch move operation: {e}")
        
    return result

def create_file_with_type(ipfs_client, path, content, content_type=None, detect_type=True):
    """
    Create a file in MFS with specified content type.
    
    Args:
        ipfs_client: IPFS client instance for MFS operations
        path: Path in MFS to create file at
        content: File content (string or bytes)
        content_type: Optional MIME type to set
        detect_type: Whether to detect content type if not provided
        
    Returns:
        Dictionary with operation results
    """
    start_time = time.time()
    
    result = {
        "success": False,
        "operation": "create_file_with_type",
        "timestamp": start_time,
        "path": path
    }
    
    try:
        # Ensure content is bytes
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        # Detect content type if not provided
        if not content_type and detect_type:
            detector = ContentTypeDetector(ipfs_client)
            
            # Detect from filename
            content_type_from_name = detector.detect_from_filename(path)
            
            # Detect from content
            content_type_from_content = detector.detect_from_content(content_bytes)
            
            # Use content-based detection if it's more specific
            if content_type_from_content != 'application/octet-stream':
                content_type = content_type_from_content
            else:
                content_type = content_type_from_name
        
        # Create parent directory if needed
        parent_dir = PathUtils.get_parent_dir(path)
        if parent_dir and parent_dir != "/":
            mkdir_result = ipfs_client.files_mkdir(parent_dir, parents=True)
            if not mkdir_result.get("success", False):
                logger.warning(f"Failed to create parent directory {parent_dir}: {mkdir_result.get('error', 'Unknown error')}")
        
        # Write file
        write_result = ipfs_client.files_write(
            path=path,
            content=content_bytes,
            create=True,
            truncate=True,
            parents=False  # We've already created parent directories
        )
        
        if not write_result.get("success", False):
            raise RuntimeError(f"Failed to write file {path}: {write_result.get('error', 'Unknown error')}")
        
        # Set content type as extended attribute (Not directly supported by IPFS MFS,
        # so this would be a custom implementation in a production environment)
        result["content_type"] = content_type
        result["content_hash"] = compute_file_hash(content_bytes)
        result["size"] = len(content_bytes)
        result["success"] = True
        result["duration_ms"] = (time.time() - start_time) * 1000
        
    except Exception as e:
        result["error"] = f"Failed to create file with type: {str(e)}"
        result["error_type"] = "write_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(f"Error creating file with type: {e}")
        
    return result
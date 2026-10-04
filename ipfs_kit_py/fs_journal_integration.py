"""
Filesystem Journal Integration for IPFS Kit.

This module integrates the Filesystem Journal with the IPFS Kit high-level API,
enabling robust journaling of filesystem operations to ensure data consistency
and recovery in case of unexpected shutdowns.
"""

import os
import logging
from typing import Dict, Any, Optional

from ipfs_kit_py.filesystem_journal import (
    FilesystemJournal,
    FilesystemJournalManager,
    JournalOperationType,
    JournalEntryStatus
)

# Configure logging
logger = logging.getLogger(__name__)

class IPFSFilesystemInterface:
    """
    Adapter class that provides the filesystem interface expected by FilesystemJournalManager.
    This connects the manager to IPFS Kit's actual file operations.
    
    This implementation handles the mapping between path-based filesystem operations
    and IPFS's content-addressed storage model through two main adaptations:
    
    1. Path to CID mapping: Maintains a local mapping between virtual paths and CIDs
    2. Content-based operations: Uses content addressing for storage while simulating
       traditional filesystem semantics
    """
    
    def __init__(self, fs_api):
        """
        Initialize with the filesystem API from IPFS Kit.
        
        Args:
            fs_api: The filesystem API instance (typically IPFSSimpleAPI)
        """
        self.fs_api = fs_api
        
        # Try to get the filesystem interface if available
        self.fs = getattr(self.fs_api, "fs", None)
        if self.fs is None:
            # Try to initialize it
            try:
                self.fs = self.fs_api.get_filesystem(return_mock=True)
                logger.info("Initialized filesystem interface")
            except Exception as e:
                logger.warning(f"Failed to initialize filesystem interface: {e}")
                self.fs = None
        
        # Path to CID mapping for the virtual filesystem
        self.path_to_cid = {}
        
        # Directory structure tracking
        self.directories = set()
        
        # Journal-specific metadata storage
        self.path_metadata = {}
        
        # Track the last write result for testing and debugging
        self._last_write_result = None
    
    def write_file(self, path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Write content to a file."""
        try:
            # Ensure content is bytes
            if not isinstance(content, bytes):
                if isinstance(content, str):
                    content = content.encode('utf-8')
                else:
                    # Try to convert to bytes if possible
                    content = bytes(content)
            
            # Priority order for IPFS methods:
            # 1. Try the ipfs_add method (high-level API)
            # 2. Try the add method (direct API)
            # 3. Try any method that adds content to IPFS
            # 4. Fall back to simulation only as a last resort
            
            result = None
            error_msgs = []
            
            # Try all possible methods to add content to IPFS
            # Method 1: ipfs_add from high-level API
            if hasattr(self.fs_api, 'ipfs_add'):
                try:
                    logger.info("Adding content using ipfs_add method")
                    
                    # Check what the method actually is
                    logger.info(f"ipfs_add method: {self.fs_api.ipfs_add}")
                    
                    # The ipfs_add method in high-level API takes content directly
                    # Without any recursive parameter
                    result = self.fs_api.ipfs_add(content)
                    logger.info(f"ipfs_add result: {result}")
                    
                    # Handle the case where IPFS is not available
                    if result and "error_type" in result and result["error_type"] == "ComponentNotAvailable":
                        error_msgs.append(f"IPFS component not available: {result.get('error', 'Unknown error')}")
                        logger.warning(f"IPFS component not available: {result}")
                    elif result and "success" in result and result["success"] and "cid" in result:
                        logger.info(f"Successfully added content using ipfs_add: {result.get('cid')}")
                except Exception as e:
                    error_msgs.append(f"ipfs_add failed: {str(e)}")
                    logger.warning(f"ipfs_add method failed: {e}")
                    
                    # Log the traceback for more detail
                    import traceback
                    logger.warning(f"ipfs_add traceback: {traceback.format_exc()}")
            
            # Method 2: Try direct ipfs API access if available
            if result is None and hasattr(self.fs_api, 'ipfs') and hasattr(self.fs_api.ipfs, 'add'):
                try:
                    logger.info("Adding content using fs_api.ipfs.add method")
                    # Check what the method actually is
                    logger.info(f"ipfs.add method: {self.fs_api.ipfs.add}")
                    
                    # This is typically the ipfs_py.ipfs.add method which requires a file path
                    
                    # Write content to a temporary file first
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_path = temp_file.name
                    
                    try:
                        # Call the add method with the file path
                        logger.info(f"Calling ipfs.add with file path: {temp_path}")
                        ipfs_result = self.fs_api.ipfs.add(temp_path)
                        logger.info(f"ipfs.add result: {ipfs_result}")
                        
                        # Convert result to standard format
                        if isinstance(ipfs_result, dict):
                            result = ipfs_result
                            # Standardize result format
                            if "Hash" in result and "cid" not in result:
                                result["cid"] = result["Hash"]
                            if "success" not in result:
                                result["success"] = True
                            logger.info(f"Successfully added content using ipfs.add: {result.get('cid')}")
                    finally:
                        # Clean up the temporary file
                        try:
                            os.unlink(temp_path)
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to remove temporary file: {cleanup_error}")
                except Exception as e:
                    error_msgs.append(f"fs_api.ipfs.add failed: {str(e)}")
                    logger.warning(f"fs_api.ipfs.add method failed: {e}")
                    
                    # Log the traceback for more detail
                    import traceback
                    logger.warning(f"ipfs.add traceback: {traceback.format_exc()}")
                
            # Method 3: add from direct API
            if result is None and hasattr(self.fs_api, 'add'):
                try:
                    logger.info("Adding content using add method")
                    # Check what the method actually is
                    logger.info(f"add method: {self.fs_api.add}")
                    
                    # Similar to ipfs.add, this might require a file path
                    # Create a temporary file
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_path = temp_file.name
                    
                    try:
                        # Try calling add with file path first (most common)
                        logger.info(f"Calling add with file path: {temp_path}")
                        result = self.fs_api.add(temp_path)
                        logger.info(f"add result: {result}")
                    except Exception as file_error:
                        # If that fails, try with direct content
                        logger.warning(f"add with file path failed: {file_error}, trying with direct content")
                        result = self.fs_api.add(content)
                        logger.info(f"add with direct content result: {result}")
                    finally:
                        # Clean up the temporary file
                        try:
                            os.unlink(temp_path)
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to remove temporary file: {cleanup_error}")
                            
                    if result and ("Hash" in result or "cid" in result):
                        # Standardize result format
                        if "Hash" in result and "cid" not in result:
                            result["cid"] = result["Hash"]
                        if "success" not in result:
                            result["success"] = True
                        logger.info(f"Successfully added content using add: {result.get('cid')}")
                except Exception as e:
                    error_msgs.append(f"add failed: {str(e)}")
                    logger.warning(f"add method failed: {e}")
                    
                    # Log the traceback for more detail
                    import traceback
                    logger.warning(f"add traceback: {traceback.format_exc()}")
            
            # Method 3: Try any available method that adds content to IPFS
            if result is None:
                potential_methods = ['add_bytes', 'add_data', 'add_content', 'add_str']
                for method_name in potential_methods:
                    if hasattr(self.fs_api, method_name):
                        try:
                            logger.info(f"Adding content using {method_name} method")
                            method = getattr(self.fs_api, method_name)
                            method_result = method(content)
                            
                            # Standardize result format based on what we get back
                            if isinstance(method_result, str):
                                # If we got back just a CID string
                                result = {
                                    "success": True,
                                    "cid": method_result,
                                    "size": len(content)
                                }
                            elif isinstance(method_result, dict):
                                result = method_result
                                # Ensure it has the keys we need
                                if "Hash" in result and "cid" not in result:
                                    result["cid"] = result["Hash"]
                                if "success" not in result:
                                    result["success"] = True
                            
                            if result and "cid" in result:
                                logger.info(f"Successfully added content using {method_name}: {result.get('cid')}")
                                break
                        except Exception as e:
                            error_msgs.append(f"{method_name} failed: {str(e)}")
                            logger.warning(f"{method_name} method failed: {e}")
            
            # Method 4: Fall back to simulation only if all other methods failed
            if result is None or "cid" not in result:
                error_msg = "All IPFS methods failed"
                if error_msgs:
                    error_msg += f": {', '.join(error_msgs)}"
                logger.warning(f"{error_msg}. Falling back to simulation.")
                
                # Let's check what methods we have available
                available_methods = []
                if hasattr(self.fs_api, 'ipfs_add'):
                    available_methods.append('ipfs_add')
                if hasattr(self.fs_api, 'ipfs') and hasattr(self.fs_api.ipfs, 'add'):
                    available_methods.append('ipfs.add')
                if hasattr(self.fs_api, 'add'):
                    available_methods.append('add')
                
                logger.warning(f"Available methods: {available_methods}")
                
                # Generate a deterministic fake CID
                import hashlib
                content_hash = hashlib.sha256(content).hexdigest()
                fake_cid = f"Qm{content_hash[:44]}"
                result = {
                    "success": True,
                    "cid": fake_cid,
                    "size": len(content),
                    "simulated": True  # Mark this as a simulated result
                }
                logger.warning(f"Simulating add operation with fake CID: {fake_cid}")
            
            # Extract the CID
            cid = result.get("cid", "")
            
            # Store the path -> CID mapping for our virtual filesystem
            self.path_to_cid[path] = cid
            
            # Store metadata if provided
            if metadata:
                self.path_metadata[path] = metadata
            
            # Create parent directories if needed
            parent_dir = os.path.dirname(path)
            if parent_dir:
                self.directories.add(parent_dir)
            
            # Add marker in response if this was simulated
            response = {
                "success": True, 
                "path": path,
                "cid": cid,
                "size": len(content),
                "virtual": True  # Flag that this is a virtual filesystem mapping
            }
            
            if result.get("simulated", False):
                response["simulated"] = True
            
            # Store the result for testing and debugging
            self._last_write_result = response
            
            return response
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            return {"success": False, "error": str(e)}
    
    def mkdir(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a directory."""
        try:
            # Add to our directory set
            self.directories.add(path)
            
            # Create empty directory in IPFS (if filesystem is available)
            if self.fs and hasattr(self.fs, "mkdir"):
                try:
                    # Try to use the filesystem interface
                    self.fs.mkdir(path)
                except Exception as e:
                    logger.debug(f"Filesystem mkdir failed, simulating: {e}")
            
            # Store metadata if provided
            if metadata:
                self.path_metadata[path] = metadata
            
            return {
                "success": True, 
                "path": path,
                "virtual": True
            }
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            return {"success": False, "error": str(e)}
    
    def rm(self, path: str) -> Dict[str, Any]:
        """Remove a file."""
        try:
            # Check if path exists in our mappings
            if path in self.path_to_cid:
                # Get the CID before removing (for return value)
                cid = self.path_to_cid[path]
                
                # Remove from our mappings
                del self.path_to_cid[path]
                
                # Remove metadata if exists
                if path in self.path_metadata:
                    del self.path_metadata[path]
                
                return {
                    "success": True,
                    "path": path,
                    "cid": cid,
                    "virtual": True
                }
            else:
                # File doesn't exist in our mapping
                return {
                    "success": False,
                    "path": path,
                    "error": "File not found in virtual filesystem"
                }
        except Exception as e:
            logger.error(f"Error removing file {path}: {e}")
            return {"success": False, "error": str(e)}
    
    def rmdir(self, path: str) -> Dict[str, Any]:
        """Remove a directory."""
        try:
            # Check if path exists in our directory set
            if path in self.directories:
                # Check if directory is empty (in our virtual filesystem)
                has_children = False
                for p in self.path_to_cid:
                    if p.startswith(path + "/"):
                        has_children = True
                        break
                
                if has_children:
                    return {
                        "success": False,
                        "path": path,
                        "error": "Directory not empty"
                    }
                
                # Remove from our directory set
                self.directories.remove(path)
                
                # Remove metadata if exists
                if path in self.path_metadata:
                    del self.path_metadata[path]
                
                return {
                    "success": True,
                    "path": path,
                    "virtual": True
                }
            else:
                # Directory doesn't exist in our set
                return {
                    "success": False,
                    "path": path,
                    "error": "Directory not found in virtual filesystem"
                }
        except Exception as e:
            logger.error(f"Error removing directory {path}: {e}")
            return {"success": False, "error": str(e)}
    
    def move(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """Move/rename a file or directory."""
        try:
            # Handle file move
            if old_path in self.path_to_cid:
                # Get the CID
                cid = self.path_to_cid[old_path]
                
                # Update our mappings
                self.path_to_cid[new_path] = cid
                del self.path_to_cid[old_path]
                
                # Move metadata if exists
                if old_path in self.path_metadata:
                    self.path_metadata[new_path] = self.path_metadata[old_path]
                    del self.path_metadata[old_path]
                
                return {
                    "success": True,
                    "old_path": old_path,
                    "new_path": new_path,
                    "cid": cid,
                    "virtual": True
                }
            # Handle directory move
            elif old_path in self.directories:
                # Remove old directory
                self.directories.remove(old_path)
                
                # Add new directory
                self.directories.add(new_path)
                
                # Update paths for all files in the directory
                paths_to_update = {}
                for path, cid in self.path_to_cid.items():
                    if path.startswith(old_path + "/"):
                        new_file_path = path.replace(old_path, new_path, 1)
                        paths_to_update[path] = (new_file_path, cid)
                
                # Update the mappings
                for old_file_path, (new_file_path, cid) in paths_to_update.items():
                    self.path_to_cid[new_file_path] = cid
                    del self.path_to_cid[old_file_path]
                
                # Move metadata if exists
                if old_path in self.path_metadata:
                    self.path_metadata[new_path] = self.path_metadata[old_path]
                    del self.path_metadata[old_path]
                
                return {
                    "success": True,
                    "old_path": old_path,
                    "new_path": new_path,
                    "files_moved": len(paths_to_update),
                    "virtual": True
                }
            else:
                return {
                    "success": False,
                    "old_path": old_path,
                    "new_path": new_path,
                    "error": "Path not found in virtual filesystem"
                }
        except Exception as e:
            logger.error(f"Error moving {old_path} to {new_path}: {e}")
            return {"success": False, "error": str(e)}
    
    def update_metadata(self, path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update metadata for a file or directory."""
        try:
            # Check if path exists in our filesystem
            if path in self.path_to_cid or path in self.directories:
                # Update or set metadata
                if path in self.path_metadata:
                    # Update existing metadata
                    self.path_metadata[path].update(metadata)
                else:
                    # Set new metadata
                    self.path_metadata[path] = metadata.copy()
                
                return {
                    "success": True,
                    "path": path,
                    "metadata": self.path_metadata[path],
                    "virtual": True
                }
            else:
                return {
                    "success": False,
                    "path": path,
                    "error": "Path not found in virtual filesystem"
                }
        except Exception as e:
            logger.error(f"Error updating metadata for {path}: {e}")
            return {"success": False, "error": str(e)}
    
    def mount(self, path: str, cid: str, is_directory: bool = True, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Mount a CID at a specific path."""
        try:
            # This is a direct mapping between path and CID
            if is_directory:
                self.directories.add(path)
            else:
                self.path_to_cid[path] = cid
            
            # Store metadata if provided
            if metadata:
                self.path_metadata[path] = metadata
            
            return {
                "success": True,
                "path": path,
                "cid": cid,
                "is_directory": is_directory,
                "virtual": True
            }
        except Exception as e:
            logger.error(f"Error mounting {cid} at {path}: {e}")
            return {"success": False, "error": str(e)}
    
    def unmount(self, path: str) -> Dict[str, Any]:
        """Unmount a previously mounted CID."""
        try:
            # Check if path exists in our mappings
            if path in self.path_to_cid:
                # Get the CID before removing
                cid = self.path_to_cid[path]
                
                # Remove from our mappings
                del self.path_to_cid[path]
                
                # Remove metadata if exists
                if path in self.path_metadata:
                    del self.path_metadata[path]
                
                return {
                    "success": True,
                    "path": path,
                    "cid": cid,
                    "virtual": True
                }
            elif path in self.directories:
                # Remove from directory set
                self.directories.remove(path)
                
                # Remove metadata if exists
                if path in self.path_metadata:
                    del self.path_metadata[path]
                
                return {
                    "success": True,
                    "path": path,
                    "virtual": True
                }
            else:
                return {
                    "success": False,
                    "path": path,
                    "error": "Path not found in virtual filesystem"
                }
        except Exception as e:
            logger.error(f"Error unmounting {path}: {e}")
            return {"success": False, "error": str(e)}
    
    def isdir(self, path: str) -> bool:
        """Check if a path is a directory."""
        # First check our directory set
        if path in self.directories:
            return True
        
        # Check if it's a file
        if path in self.path_to_cid:
            return False
        
        # For paths that don't exist yet, use a heuristic
        return path.endswith('/')


class FilesystemJournalIntegration:
    """
    Integrates the FilesystemJournal with IPFS Kit's high-level API,
    providing an enhanced API with journal-based transactional safety.
    """
    
    def __init__(
        self, 
        fs_api, 
        wal=None,
        journal_base_path: str = "~/.ipfs_kit/journal", 
        auto_recovery: bool = True,
        sync_interval: int = 5,
        checkpoint_interval: int = 60,
        max_journal_size: int = 1000
    ):
        """
        Initialize the integration with required components.
        
        Args:
            fs_api: The filesystem API to integrate with
            wal: Optional WAL instance for additional safety
            journal_base_path: Base directory for journal storage
            auto_recovery: Whether to automatically recover on startup
            sync_interval: Interval in seconds for syncing journal to disk
            checkpoint_interval: Interval in seconds for creating checkpoints
            max_journal_size: Maximum journal entries before forcing a checkpoint
        """
        self.fs_api = fs_api
        self.wal = wal
        
        # Create the journal
        self.journal = FilesystemJournal(
            base_path=journal_base_path,
            sync_interval=sync_interval,
            checkpoint_interval=checkpoint_interval,
            max_journal_size=max_journal_size,
            auto_recovery=auto_recovery,
            wal=wal
        )
        
        # Create the filesystem interface adapter
        self.fs_interface = IPFSFilesystemInterface(fs_api)
        
        # Create the journal manager
        self.journal_manager = FilesystemJournalManager(
            journal=self.journal,
            wal=wal,
            fs_interface=self.fs_interface
        )
        
        logger.info(f"Filesystem journal integration initialized with base path: {journal_base_path}")
    
    def create_file(self, path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new file with journaling protection."""
        return self.journal_manager.create_file(path, content, metadata)
    
    def create_directory(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new directory with journaling protection."""
        return self.journal_manager.create_directory(path, metadata)
    
    def delete(self, path: str) -> Dict[str, Any]:
        """Delete a file or directory with journaling protection."""
        return self.journal_manager.delete(path)
    
    def rename(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """Rename a file or directory with journaling protection."""
        return self.journal_manager.rename(old_path, new_path)
    
    def write_file(self, path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Write to a file with journaling protection."""
        return self.journal_manager.write_file(path, content, metadata)
    
    def update_metadata(self, path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update metadata with journaling protection."""
        return self.journal_manager.update_metadata(path, metadata)
    
    def mount(self, path: str, cid: str, is_directory: bool = True, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Mount a CID with journaling protection."""
        return self.journal_manager.mount(path, cid, is_directory, metadata)
    
    def unmount(self, path: str) -> Dict[str, Any]:
        """Unmount a path with journaling protection."""
        return self.journal_manager.unmount(path)
    
    def get_journal_stats(self) -> Dict[str, Any]:
        """Get statistics about the journal."""
        return self.journal_manager.get_journal_stats()
    
    def create_checkpoint(self) -> Dict[str, Any]:
        """Manually create a checkpoint."""
        success = self.journal.create_checkpoint()
        return {
            "success": success,
            "timestamp": self.journal.last_checkpoint_time,
            "message": "Checkpoint created successfully" if success else "Failed to create checkpoint"
        }
    
    def recover(self) -> Dict[str, Any]:
        """Manually initiate recovery."""
        return self.journal.recover()
    
    def close(self) -> None:
        """Close the journal and flush any pending operations."""
        self.journal.close()
        logger.info("Filesystem journal integration closed")


def enable_filesystem_journaling(
    api_instance, 
    wal=None,
    journal_base_path: str = "~/.ipfs_kit/journal",
    auto_recovery: bool = True,
    **kwargs
) -> FilesystemJournalIntegration:
    """
    Enable filesystem journaling for an existing API instance.
    
    Args:
        api_instance: The API instance to enhance with filesystem journaling
        wal: Optional WAL instance for additional safety
        journal_base_path: Base directory for journal storage
        auto_recovery: Whether to automatically recover on startup
        **kwargs: Additional arguments for the FilesystemJournal
    
    Returns:
        FilesystemJournalIntegration instance that wraps the original API
    """
    return FilesystemJournalIntegration(
        fs_api=api_instance,
        wal=wal,
        journal_base_path=journal_base_path,
        auto_recovery=auto_recovery,
        **kwargs
    )
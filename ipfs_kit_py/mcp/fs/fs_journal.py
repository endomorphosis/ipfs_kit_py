#!/usr/bin/env python3
"""
Filesystem Journal Module

This module provides virtual filesystem and journaling capabilities for IPFS Kit.
It tracks all filesystem operations and provides a virtual filesystem layer that
can be integrated with IPFS operations.
"""

import os
import time
import json
import enum
import logging
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

class FSOperationType(enum.Enum):
    """Types of filesystem operations that can be tracked."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    LIST = "list"
    MKDIR = "mkdir"
    PIN = "pin"
    UNPIN = "unpin"
    MOVE = "move"
    COPY = "copy"
    STAT = "stat"
    SYNC = "sync"
    IMPORT = "import"
    EXPORT = "export"


class FSOperation:
    """
    Represents a filesystem operation for journaling purposes.
    """
    
    def __init__(self, op_type: FSOperationType, path: str, metadata: Optional[Dict[str, Any]] = None):
        self.op_type = op_type
        self.path = path
        self.timestamp = time.time()
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the operation to a dictionary for serialization."""
        return {
            "op_type": self.op_type.value,
            "path": self.path,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FSOperation':
        """Create an operation from a dictionary representation."""
        return cls(
            FSOperationType(data["op_type"]),
            data["path"],
            data.get("metadata", {})
        )


class FSJournal:
    """
    A journal that records filesystem operations for tracking and auditing.
    """
    
    def __init__(self, journal_path: Optional[str] = None):
        self.operations: List[Dict[str, Any]] = []
        self.journal_path = journal_path
        if journal_path:
            os.makedirs(os.path.dirname(journal_path), exist_ok=True)
            self._load_from_file()
    
    def record(self, operation: FSOperation, success: bool, error_message: Optional[str] = None) -> None:
        """
        Record an operation in the journal.
        
        Args:
            operation: The filesystem operation to record
            success: Whether the operation was successful
            error_message: Error message if the operation failed
        """
        entry = operation.to_dict()
        entry["success"] = success
        
        if error_message:
            entry["error"] = error_message
        
        self.operations.append(entry)
        
        # Log the operation
        if success:
            logger.debug(f"FS Operation: {operation.op_type.value} on {operation.path}")
        else:
            logger.warning(f"Failed FS Operation: {operation.op_type.value} on {operation.path}: {error_message}")
        
        # Save to file if journal path is set
        if self.journal_path:
            self._append_to_file(entry)
    
    def get_operations_for_path(self, path: str) -> List[Dict[str, Any]]:
        """
        Get all operations for a specific path.
        
        Args:
            path: The path to find operations for
            
        Returns:
            List of operation entries that match the path
        """
        return [op for op in self.operations if op["path"] == path]
    
    def _load_from_file(self) -> None:
        """Load operations from the journal file if it exists."""
        if os.path.exists(self.journal_path):
            try:
                with open(self.journal_path, 'r') as f:
                    self.operations = json.load(f)
                logger.info(f"Loaded {len(self.operations)} operations from journal file")
            except Exception as e:
                logger.error(f"Failed to load journal file: {e}")
    
    def _append_to_file(self, entry: Dict[str, Any]) -> None:
        """Append an operation to the journal file."""
        try:
            # If the file doesn't exist or is empty, write a new JSON array
            if not os.path.exists(self.journal_path) or os.path.getsize(self.journal_path) == 0:
                with open(self.journal_path, 'w') as f:
                    json.dump([entry], f, indent=2)
            else:
                # Otherwise, read the existing array, append, and rewrite
                with open(self.journal_path, 'r') as f:
                    operations = json.load(f)
                
                operations.append(entry)
                
                with open(self.journal_path, 'w') as f:
                    json.dump(operations, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to append to journal file: {e}")
    
    def clear(self) -> None:
        """Clear all operations from the journal."""
        self.operations = []
        if self.journal_path and os.path.exists(self.journal_path):
            try:
                with open(self.journal_path, 'w') as f:
                    json.dump([], f)
            except Exception as e:
                logger.error(f"Failed to clear journal file: {e}")


class VirtualFile:
    """
    Represents a file in the virtual filesystem.
    """
    
    def __init__(self, path: str, content: bytes = b'', cid: Optional[str] = None):
        self.path = path
        self.content = content
        self.cid = cid
        self.last_modified = time.time()
        self.metadata: Dict[str, Any] = {}
    
    def update(self, content: bytes, cid: Optional[str] = None) -> None:
        """Update the file content and CID."""
        self.content = content
        if cid:
            self.cid = cid
        self.last_modified = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get file statistics."""
        return {
            "path": self.path,
            "size": len(self.content),
            "cid": self.cid,
            "last_modified": self.last_modified,
            "last_modified_iso": datetime.fromtimestamp(self.last_modified).isoformat(),
            "metadata": self.metadata
        }


class VirtualDirectory:
    """
    Represents a directory in the virtual filesystem.
    """
    
    def __init__(self, path: str):
        self.path = path
        self.entries: Dict[str, Union[VirtualFile, 'VirtualDirectory']] = {}
        self.last_modified = time.time()
        self.metadata: Dict[str, Any] = {}
    
    def add_file(self, name: str, content: bytes = b'', cid: Optional[str] = None) -> VirtualFile:
        """Add a file to this directory."""
        file_path = os.path.join(self.path, name)
        file = VirtualFile(file_path, content, cid)
        self.entries[name] = file
        self.last_modified = time.time()
        return file
    
    def add_directory(self, name: str) -> 'VirtualDirectory':
        """Add a subdirectory to this directory."""
        dir_path = os.path.join(self.path, name)
        directory = VirtualDirectory(dir_path)
        self.entries[name] = directory
        self.last_modified = time.time()
        return directory
    
    def get(self, name: str) -> Optional[Union[VirtualFile, 'VirtualDirectory']]:
        """Get an entry by name."""
        return self.entries.get(name)
    
    def remove(self, name: str) -> bool:
        """Remove an entry by name."""
        if name in self.entries:
            del self.entries[name]
            self.last_modified = time.time()
            return True
        return False
    
    def list(self) -> List[str]:
        """List all entries in this directory."""
        return list(self.entries.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get directory statistics."""
        return {
            "path": self.path,
            "entries": len(self.entries),
            "is_directory": True,
            "last_modified": self.last_modified,
            "last_modified_iso": datetime.fromtimestamp(self.last_modified).isoformat(),
            "metadata": self.metadata
        }


class VirtualFS:
    """
    A virtual filesystem that can be used to track and manipulate files
    without actually touching the local filesystem.
    """
    
    def __init__(self, journal: Optional[FSJournal] = None):
        self.root = VirtualDirectory("/")
        self.journal = journal or FSJournal()
        self.cid_index: Dict[str, List[str]] = {}  # CID -> List of paths
    
    def _get_parent_dir(self, path: str) -> Tuple[VirtualDirectory, str]:
        """
        Get the parent directory for a path and the basename.
        
        Creates parent directories as needed.
        
        Returns:
            Tuple of (parent directory, basename)
        """
        if path == "/":
            return self.root, ""
        
        # Normalize path to remove trailing slash
        path = os.path.normpath(path)
        
        # Get parent path and basename
        parent_path = os.path.dirname(path)
        basename = os.path.basename(path)
        
        # Navigate to the parent directory, creating it if necessary
        current = self.root
        if parent_path != "/":
            parts = parent_path.strip("/").split("/")
            
            for part in parts:
                if not part:
                    continue
                    
                entry = current.get(part)
                if entry is None:
                    # Create missing directory
                    entry = current.add_directory(part)
                elif not isinstance(entry, VirtualDirectory):
                    # Cannot create a directory where a file exists
                    raise ValueError(f"Cannot create directory: {part} is a file")
                
                current = entry
        
        return current, basename
    
    def _get_entry(self, path: str) -> Optional[Union[VirtualFile, VirtualDirectory]]:
        """
        Get a file or directory entry at the given path.
        
        Returns:
            The entry, or None if it doesn't exist
        """
        if path == "/":
            return self.root
        
        path = os.path.normpath(path)
        parts = path.strip("/").split("/")
        
        current = self.root
        for i, part in enumerate(parts):
            if not part:
                continue
                
            entry = current.get(part)
            if entry is None:
                return None
            
            if i == len(parts) - 1:
                return entry
            
            if not isinstance(entry, VirtualDirectory):
                return None
            
            current = entry
        
        return current
    
    def mkdir(self, path: str) -> bool:
        """
        Create a directory at the given path.
        
        Args:
            path: The path where to create the directory
            
        Returns:
            True if the directory was created, False otherwise
        """
        # Record the operation
        operation = FSOperation(FSOperationType.MKDIR, path)
        
        try:
            if path == "/":
                # Root already exists
                self.journal.record(operation, False, "Root directory already exists")
                return False
            
            # Check if the path already exists
            existing = self._get_entry(path)
            if existing is not None:
                if isinstance(existing, VirtualDirectory):
                    # Directory already exists
                    self.journal.record(operation, False, "Directory already exists")
                    return False
                else:
                    # Path exists but is a file
                    self.journal.record(operation, False, "Path exists but is a file")
                    return False
            
            # Get the parent directory and create it if needed
            parent, basename = self._get_parent_dir(path)
            
            # Create the directory
            parent.add_directory(basename)
            
            # Record success
            self.journal.record(operation, True)
            return True
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return False
    
    def write_file(self, path: str, content: bytes, cid: Optional[str] = None) -> bool:
        """
        Write content to a file in the virtual filesystem.
        
        Args:
            path: The path where to write the file
            content: The content to write
            cid: Optional CID associated with the file
            
        Returns:
            True if the file was written, False otherwise
        """
        # Record the operation
        operation = FSOperation(FSOperationType.WRITE, path, {"size": len(content)})
        
        try:
            # Ensure the parent directory exists
            parent, basename = self._get_parent_dir(path)
            
            # Check if there's an existing file
            existing = parent.get(basename)
            
            if existing is not None:
                if isinstance(existing, VirtualFile):
                    # Update the existing file
                    existing.update(content, cid)
                else:
                    # Cannot overwrite directory with file
                    self.journal.record(operation, False, "Cannot overwrite directory with file")
                    return False
            else:
                # Create a new file
                file = parent.add_file(basename, content, cid)
                
                # If we have a CID, update the index
                if cid:
                    if cid not in self.cid_index:
                        self.cid_index[cid] = []
                    
                    if path not in self.cid_index[cid]:
                        self.cid_index[cid].append(path)
            
            # Record success
            self.journal.record(operation, True)
            return True
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return False
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        Read a file from the virtual filesystem.
        
        Args:
            path: The path to read
            
        Returns:
            The file content, or None if the file doesn't exist or is a directory
        """
        # Record the operation
        operation = FSOperation(FSOperationType.READ, path)
        
        try:
            # Get the entry
            entry = self._get_entry(path)
            
            if entry is None:
                # File doesn't exist
                self.journal.record(operation, False, "File not found")
                return None
            
            if isinstance(entry, VirtualDirectory):
                # Entry is a directory, not a file
                self.journal.record(operation, False, "Path is a directory")
                return None
            
            # Record success
            self.journal.record(operation, True, {"size": len(entry.content)})
            return entry.content
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return None
    
    def delete(self, path: str) -> bool:
        """
        Delete a file or directory from the virtual filesystem.
        
        Args:
            path: The path to delete
            
        Returns:
            True if the path was deleted, False otherwise
        """
        # Record the operation
        operation = FSOperation(FSOperationType.DELETE, path)
        
        try:
            if path == "/":
                # Cannot delete root
                self.journal.record(operation, False, "Cannot delete root directory")
                return False
            
            # Get the parent directory
            parent, basename = self._get_parent_dir(path)
            
            # Check if the entry exists
            if basename not in parent.entries:
                self.journal.record(operation, False, "Path not found")
                return False
            
            # Get the entry before removing it
            entry = parent.get(basename)
            
            # Remove the entry
            result = parent.remove(basename)
            
            # Update CID index if this was a file with a CID
            if result and isinstance(entry, VirtualFile) and entry.cid:
                if entry.cid in self.cid_index and entry.path in self.cid_index[entry.cid]:
                    self.cid_index[entry.cid].remove(entry.path)
                    if not self.cid_index[entry.cid]:
                        del self.cid_index[entry.cid]
            
            # Record success or failure
            self.journal.record(operation, result)
            return result
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return False
    
    def list(self, path: str) -> Optional[List[str]]:
        """
        List the contents of a directory.
        
        Args:
            path: The directory path to list
            
        Returns:
            List of entry names, or None if the path doesn't exist or is not a directory
        """
        # Record the operation
        operation = FSOperation(FSOperationType.LIST, path)
        
        try:
            # Get the entry
            entry = self._get_entry(path)
            
            if entry is None:
                # Path doesn't exist
                self.journal.record(operation, False, "Path not found")
                return None
            
            if not isinstance(entry, VirtualDirectory):
                # Path is not a directory
                self.journal.record(operation, False, "Path is not a directory")
                return None
            
            # List the entries
            entries = entry.list()
            
            # Record success
            self.journal.record(operation, True, {"entries": len(entries)})
            return entries
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return None
    
    def exists(self, path: str) -> bool:
        """
        Check if a path exists in the virtual filesystem.
        
        Args:
            path: The path to check
            
        Returns:
            True if the path exists, False otherwise
        """
        # Special case for root
        if path == "/":
            return True
        
        # Check if the entry exists
        return self._get_entry(path) is not None
    
    def is_file(self, path: str) -> bool:
        """
        Check if a path is a file.
        
        Args:
            path: The path to check
            
        Returns:
            True if the path is a file, False otherwise
        """
        entry = self._get_entry(path)
        return entry is not None and isinstance(entry, VirtualFile)
    
    def is_dir(self, path: str) -> bool:
        """
        Check if a path is a directory.
        
        Args:
            path: The path to check
            
        Returns:
            True if the path is a directory, False otherwise
        """
        entry = self._get_entry(path)
        return entry is not None and isinstance(entry, VirtualDirectory)
    
    def get_cid(self, path: str) -> Optional[str]:
        """
        Get the CID associated with a file.
        
        Args:
            path: The file path
            
        Returns:
            The CID if available, or None
        """
        entry = self._get_entry(path)
        if entry is not None and isinstance(entry, VirtualFile):
            return entry.cid
        return None
    
    def get_stats(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a path.
        
        Args:
            path: The path to get statistics for
            
        Returns:
            Statistics dictionary, or None if the path doesn't exist
        """
        # Record the operation
        operation = FSOperation(FSOperationType.STAT, path)
        
        try:
            # Get the entry
            entry = self._get_entry(path)
            
            if entry is None:
                # Path doesn't exist
                self.journal.record(operation, False, "Path not found")
                return None
            
            # Get the stats based on the type
            stats = entry.get_stats()
            
            # Record success
            self.journal.record(operation, True)
            return stats
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return None
    
    def get_paths_for_cid(self, cid: str) -> List[str]:
        """
        Get all paths associated with a CID.
        
        Args:
            cid: The CID to look up
            
        Returns:
            List of paths associated with the CID
        """
        return self.cid_index.get(cid, [])
    
    def copy(self, src_path: str, dst_path: str) -> bool:
        """
        Copy a file or directory from one path to another.
        
        Args:
            src_path: The source path
            dst_path: The destination path
            
        Returns:
            True if the copy was successful, False otherwise
        """
        # Record the operation
        operation = FSOperation(FSOperationType.COPY, src_path, {"destination": dst_path})
        
        try:
            # Get the source entry
            src_entry = self._get_entry(src_path)
            
            if src_entry is None:
                # Source doesn't exist
                self.journal.record(operation, False, "Source path not found")
                return False
            
            # Check if the source is a file or directory
            if isinstance(src_entry, VirtualFile):
                # Copy file
                result = self.write_file(dst_path, src_entry.content, src_entry.cid)
                
                # Record success or failure
                self.journal.record(operation, result)
                return result
            else:
                # Copy directory structure - create destination directory
                if not self.mkdir(dst_path):
                    self.journal.record(operation, False, "Failed to create destination directory")
                    return False
                
                # Copy all entries in the source directory
                success = True
                for name in src_entry.list():
                    src_sub_path = os.path.join(src_path, name)
                    dst_sub_path = os.path.join(dst_path, name)
                    
                    # Recursive copy
                    if not self.copy(src_sub_path, dst_sub_path):
                        success = False
                
                # Record success or failure
                self.journal.record(operation, success)
                return success
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return False
    
    def move(self, src_path: str, dst_path: str) -> bool:
        """
        Move a file or directory from one path to another.
        
        Args:
            src_path: The source path
            dst_path: The destination path
            
        Returns:
            True if the move was successful, False otherwise
        """
        # Record the operation
        operation = FSOperation(FSOperationType.MOVE, src_path, {"destination": dst_path})
        
        try:
            # First copy the file or directory
            if not self.copy(src_path, dst_path):
                self.journal.record(operation, False, "Failed to copy source to destination")
                return False
            
            # Then delete the source
            if not self.delete(src_path):
                self.journal.record(operation, False, "Copied but failed to delete source")
                return False
            
            # Record success
            self.journal.record(operation, True)
            return True
        
        except Exception as e:
            # Record failure
            self.journal.record(operation, False, str(e))
            return False


class FSController:
    """
    Controller for virtual filesystem operations.
    """
    
    def __init__(self, virtual_fs: VirtualFS):
        self.virtual_fs = virtual_fs
    
    def create_router(self):
        """Create a FastAPI router for the filesystem controller."""
        try:
            from fastapi import APIRouter, Query, Path, Body, HTTPException, File, UploadFile
            from fastapi.responses import Response
            
            router = APIRouter()
            
            @router.get("/fs/list/{path:path}")
            async def list_directory(path: str = Path(...)):
                """List the contents of a directory."""
                # Ensure path starts with /
                if not path.startswith('/'):
                    path = '/' + path
                
                entries = self.virtual_fs.list(path)
                if entries is None:
                    raise HTTPException(status_code=404, detail="Directory not found")
                
                # Get stats for each entry
                result = []
                for name in entries:
                    entry_path = os.path.join(path, name)
                    stats = self.virtual_fs.get_stats(entry_path)
                    if stats:
                        result.append(stats)
                
                return result
            
            @router.get("/fs/read/{path:path}")
            async def read_file(path: str = Path(...)):
                """Read a file."""
                # Ensure path starts with /
                if not path.startswith('/'):
                    path = '/' + path
                
                content = self.virtual_fs.read_file(path)
                if content is None:
                    raise HTTPException(status_code=404, detail="File not found")
                
                return Response(content=content)
            
            @router.post("/fs/write/{path:path}")
            async def write_file(
                path: str = Path(...),
                file: UploadFile = File(...),
                cid: Optional[str] = Query(None)
            ):
                """Write a file."""
                # Ensure path starts with /
                if not path.startswith('/'):
                    path = '/' + path
                
                # Read the file content
                content = await file.read()
                
                if self.virtual_fs.write_file(path, content, cid):
                    return {"success": True, "path": path, "size": len(content)}
                else:
                    raise HTTPException(status_code=400, detail="Failed to write file")
            
            @router.delete("/fs/delete/{path:path}")
            async def delete_path(path: str = Path(...)):
                """Delete a file or directory."""
                # Ensure path starts with /
                if not path.startswith('/'):
                    path = '/' + path
                
                if self.virtual_fs.delete(path):
                    return {"success": True, "path": path}
                else:
                    raise HTTPException(status_code=404, detail="Path not found or could not be deleted")
            
            @router.post("/fs/mkdir/{path:path}")
            async def make_directory(path: str = Path(...)):
                """Create a directory."""
                # Ensure path starts with /
                if not path.startswith('/'):
                    path = '/' + path
                
                if self.virtual_fs.mkdir(path):
                    return {"success": True, "path": path}
                else:
                    raise HTTPException(status_code=400, detail="Failed to create directory")
            
            @router.get("/fs/stats/{path:path}")
            async def get_stats(path: str = Path(...)):
                """Get statistics for a path."""
                # Ensure path starts with /
                if not path.startswith('/'):
                    path = '/' + path
                
                stats = self.virtual_fs.get_stats(path)
                if stats is None:
                    raise HTTPException(status_code=404, detail="Path not found")
                
                return stats
            
            @router.post("/fs/copy")
            async def copy_path(src_path: str = Body(...), dst_path: str = Body(...)):
                """Copy a file or directory."""
                # Ensure paths start with /
                if not src_path.startswith('/'):
                    src_path = '/' + src_path
                if not dst_path.startswith('/'):
                    dst_path = '/' + dst_path
                
                if self.virtual_fs.copy(src_path, dst_path):
                    return {"success": True, "source": src_path, "destination": dst_path}
                else:
                    raise HTTPException(status_code=400, detail="Failed to copy")
            
            @router.post("/fs/move")
            async def move_path(src_path: str = Body(...), dst_path: str = Body(...)):
                """Move a file or directory."""
                # Ensure paths start with /
                if not src_path.startswith('/'):
                    src_path = '/' + src_path
                if not dst_path.startswith('/'):
                    dst_path = '/' + dst_path
                
                if self.virtual_fs.move(src_path, dst_path):
                    return {"success": True, "source": src_path, "destination": dst_path}
                else:
                    raise HTTPException(status_code=400, detail="Failed to move")
            
            @router.get("/fs/journal")
            async def get_journal(limit: int = Query(100), path: Optional[str] = Query(None)):
                """Get the filesystem journal entries."""
                if path:
                    entries = self.virtual_fs.journal.get_operations_for_path(path)
                    return {"entries": entries[:limit], "total": len(entries), "filtered_by_path": path}
                else:
                    entries = self.virtual_fs.journal.operations
                    return {"entries": entries[-limit:], "total": len(entries)}
            
            @router.get("/fs/cid/{cid}")
            async def get_paths_for_cid(cid: str = Path(...)):
                """Get all paths associated with a CID."""
                paths = self.virtual_fs.get_paths_for_cid(cid)
                return {"cid": cid, "paths": paths, "count": len(paths)}
            
            return router
        
        except ImportError:
            logger.error("FastAPI not available, router creation skipped")
            return None


def integrate_fs_with_mcp(mcp_server) -> FSController:
    """
    Integrate filesystem journal functionality with an MCP server.
    
    Args:
        mcp_server: The MCP server instance to integrate with
        
    Returns:
        FSController: The filesystem controller
    """
    # Create journal and virtual filesystem
    journal_path = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "fs_journal.json")
    journal = FSJournal(journal_path)
    virtual_fs = VirtualFS(journal)
    
    # Create controller
    fs_controller = FSController(virtual_fs)
    
    # Create and register the router if possible
    router = fs_controller.create_router()
    if router and hasattr(mcp_server, 'app'):
        prefix = getattr(mcp_server, 'api_prefix', '/api/v0')
        mcp_server.app.include_router(router, prefix=prefix)
        logger.info(f"Registered filesystem controller router with MCP server at {prefix}")
    
    return fs_controller
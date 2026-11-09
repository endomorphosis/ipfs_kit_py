"""Mock FSSpec Module for Testing

This module provides mock implementations of FSSpec functionality for testing.
"""

import io
import os
import logging
from typing import Dict, List, Optional, Any, Union, BinaryIO

logger = logging.getLogger(__name__)


class MockIPFSFileSystem:
    """Mock implementation of FSSpec filesystem for IPFS."""
    
    protocol = "ipfs"
    
    def __init__(self, role="leecher", client=None):
        """Initialize with an IPFS client and role."""
        self.role = role
        self.client = client
        self.files_cache = {}  # path -> content mapping
        logger.info(f"Initialized mock IPFS filesystem with role: {role}")
    
    def ls(self, path: str, detail: bool = True) -> List[Dict[str, Any]]:
        """List directory contents."""
        if path.startswith("/ipfs/"):
            cid = path[6:]
            return self._mock_ls_ipfs(cid, detail)
        elif path.startswith("/ipns/"):
            name = path[6:]
            return self._mock_ls_ipns(name, detail)
        else:
            return self._mock_ls_mfs(path, detail)
    
    def _mock_ls_ipfs(self, cid: str, detail: bool) -> List[Dict[str, Any]]:
        """Mock listing IPFS content."""
        # Generate some mock entries
        entries = []
        for i in range(3):
            name = f"file{i}.txt"
            if detail:
                entries.append({
                    "name": name,
                    "size": 1024 * (i + 1),
                    "type": "file",
                    "cid": f"{cid}/file{i}"
                })
            else:
                entries.append(name)
        return entries
    
    def _mock_ls_ipns(self, name: str, detail: bool) -> List[Dict[str, Any]]:
        """Mock listing IPNS content."""
        # Pretend this resolves to a CID and use that
        mock_cid = f"QmMockCidFor{name}"
        return self._mock_ls_ipfs(mock_cid, detail)
    
    def _mock_ls_mfs(self, path: str, detail: bool) -> List[Dict[str, Any]]:
        """Mock listing MFS content."""
        entries = []
        # Generate entries for all files in the cache that start with this path
        for file_path in self.files_cache:
            if file_path.startswith(path) and file_path != path:
                relative = file_path[len(path):].lstrip("/")
                if "/" not in relative:  # Only direct children
                    if detail:
                        entries.append({
                            "name": relative,
                            "size": len(self.files_cache[file_path]),
                            "type": "file"
                        })
                    else:
                        entries.append(relative)
        return entries
    
    def open(self, path: str, mode: str = "rb") -> BinaryIO:
        """Open a file."""
        if mode.startswith("r"):
            return self._mock_open_read(path, mode)
        elif mode.startswith("w"):
            return self._mock_open_write(path, mode)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
    
    def _mock_open_read(self, path: str, mode: str) -> BinaryIO:
        """Mock opening a file for reading."""
        if path.startswith("/ipfs/"):
            cid = path[6:]
            # Generate mock content
            content = f"Mock content for IPFS path: {path}".encode()
        elif path.startswith("/ipns/"):
            name = path[6:]
            # Generate mock content
            content = f"Mock content for IPNS path: {path}".encode()
        else:
            # Check if in cache
            if path in self.files_cache:
                content = self.files_cache[path]
            else:
                content = f"Mock content for MFS path: {path}".encode()
        
        return io.BytesIO(content)
    
    def _mock_open_write(self, path: str, mode: str) -> BinaryIO:
        """Mock opening a file for writing."""
        # Create a BytesIO that updates the cache when closed
        bio = io.BytesIO()
        
        # Store original close method
        original_close = bio.close
        
        # Define new close method that updates the cache
        def new_close():
            self.files_cache[path] = bio.getvalue()
            logger.info(f"Wrote {len(bio.getvalue())} bytes to {path}")
            original_close()
        
        # Replace close method
        bio.close = new_close
        
        return bio
    
    def rm(self, path: str, recursive: bool = False) -> None:
        """Remove a file or directory."""
        if path in self.files_cache:
            del self.files_cache[path]
            logger.info(f"Removed {path}")
        
        if recursive:
            # Remove all files that start with this path
            to_remove = []
            for file_path in self.files_cache:
                if file_path.startswith(path + "/"):
                    to_remove.append(file_path)
            
            for file_path in to_remove:
                del self.files_cache[file_path]
                logger.info(f"Removed {file_path} (recursive)")
    
    def cp_file(self, src: str, dest: str) -> None:
        """Copy a file."""
        if src.startswith("/ipfs/") or src.startswith("/ipns/"):
            # Simulate reading from IPFS/IPNS
            with self.open(src, "rb") as f:
                content = f.read()
            
            # Write to destination
            with self.open(dest, "wb") as f:
                f.write(content)
            
            logger.info(f"Copied {src} to {dest}")
        elif src in self.files_cache:
            # Copy within MFS
            self.files_cache[dest] = self.files_cache[src]
            logger.info(f"Copied {src} to {dest}")
        else:
            raise FileNotFoundError(f"File not found: {src}")
    
    def info(self, path: str) -> Dict[str, Any]:
        """Get info about a file or directory."""
        if path.startswith("/ipfs/"):
            cid = path[6:]
            return {
                "name": os.path.basename(path) or cid,
                "size": 1024,
                "type": "file",
                "cid": cid
            }
        elif path.startswith("/ipns/"):
            name = path[6:]
            return {
                "name": os.path.basename(path) or name,
                "size": 1024,
                "type": "file",
                "ipns": name
            }
        elif path in self.files_cache:
            return {
                "name": os.path.basename(path),
                "size": len(self.files_cache[path]),
                "type": "file"
            }
        else:
            return {
                "name": os.path.basename(path),
                "size": 0,
                "type": "directory"
            }
    
    def pipe(self, data: bytes, path: str) -> str:
        """Write data directly to a path."""
        self.files_cache[path] = data
        logger.info(f"Wrote {len(data)} bytes to {path}")
        
        # For IPFS paths, return a mock CID
        if path.startswith("/ipfs/"):
            import hashlib
            mock_cid = f"QmMock{hashlib.sha256(data).hexdigest()[:8]}"
            return mock_cid
        
        return path
    
    def cat(self, path: str) -> bytes:
        """Cat a file (get its contents)."""
        with self.open(path, "rb") as f:
            return f.read()
    
    def put(self, lpath: str, rpath: str) -> None:
        """Upload a local file to IPFS/MFS."""
        # Simulate reading from local file
        try:
            with open(lpath, "rb") as f:
                data = f.read()
        except (FileNotFoundError, IsADirectoryError):
            # If file doesn't exist, create mock data
            data = f"Mock content for local path: {lpath}".encode()
        
        # Write to destination
        self.pipe(data, rpath)
        logger.info(f"Put {lpath} to {rpath}")
    
    def get(self, rpath: str, lpath: str) -> None:
        """Download a file from IPFS/MFS to local filesystem."""
        # Get content
        data = self.cat(rpath)
        
        # Simulate writing to local file
        os.makedirs(os.path.dirname(os.path.abspath(lpath)), exist_ok=True)
        with open(lpath, "wb") as f:
            f.write(data)
        
        logger.info(f"Got {rpath} to {lpath}")
    
    def exists(self, path: str) -> bool:
        """Check if a path exists."""
        if path.startswith("/ipfs/") or path.startswith("/ipns/"):
            # Assume all IPFS/IPNS paths exist for testing
            return True
        return path in self.files_cache
    
    def isdir(self, path: str) -> bool:
        """Check if a path is a directory."""
        # Check if any files have this path as a prefix
        for file_path in self.files_cache:
            if file_path.startswith(path + "/"):
                return True
        return False
    
    def isfile(self, path: str) -> bool:
        """Check if a path is a file."""
        if path.startswith("/ipfs/") or path.startswith("/ipns/"):
            # Assume all IPFS/IPNS paths are files for testing
            return True
        return path in self.files_cache
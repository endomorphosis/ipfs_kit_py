#!/usr/bin/env python3
"""
Metadata-First MCP Tools for IPFS Kit Python

This module implements MCP tools that prioritize checking metadata in ~/.ipfs_kit/
before making calls to the ipfs_kit_py library, improving performance and providing
a caching layer for file operations.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# Set up logging
logger = logging.getLogger(__name__)

UTC = timezone.utc

class MetadataFirstTools:
    """Tools that check metadata first, then fall back to library calls."""
    
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or os.path.expanduser("~/.ipfs_kit"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize metadata files
        self.file_metadata_path = self.data_dir / "file_metadata.json"
        self.bucket_metadata_path = self.data_dir / "bucket_metadata.json"
        self.pin_metadata_path = self.data_dir / "pin_metadata.json"
        self.vfs_index_path = self.data_dir / "vfs_index.json"
        
        # Cache for metadata
        self._metadata_cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 60  # seconds
    
    def _read_metadata(self, metadata_file: Path, default_value=None) -> Dict[str, Any]:
        """Read metadata with caching."""
        if default_value is None:
            default_value = {}
            
        cache_key = str(metadata_file)
        now = time.time()
        
        # Check cache first
        if (cache_key in self._metadata_cache and 
            cache_key in self._cache_timestamps and
            now - self._cache_timestamps[cache_key] < self._cache_ttl):
            return self._metadata_cache[cache_key]
        
        try:
            if metadata_file.exists():
                with metadata_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = default_value
                
            # Update cache
            self._metadata_cache[cache_key] = data
            self._cache_timestamps[cache_key] = now
            return data
            
        except Exception as e:
            logger.warning(f"Failed to read metadata from {metadata_file}: {e}")
            return default_value
    
    def _write_metadata(self, metadata_file: Path, data: Dict[str, Any]) -> bool:
        """Write metadata and update cache."""
        try:
            # Atomic write
            temp_file = metadata_file.with_suffix('.tmp')
            with temp_file.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            temp_file.replace(metadata_file)
            
            # Update cache
            cache_key = str(metadata_file)
            self._metadata_cache[cache_key] = data
            self._cache_timestamps[cache_key] = time.time()
            return True
            
        except Exception as e:
            logger.error(f"Failed to write metadata to {metadata_file}: {e}")
            return False
    
    async def files_list_metadata_first(self, path: str = ".", bucket: str = None) -> Dict[str, Any]:
        """List files using metadata first, fall back to filesystem scan."""
        try:
            # Check VFS index first
            vfs_index = self._read_metadata(self.vfs_index_path, {})
            bucket_key = bucket or "default"
            
            if bucket_key in vfs_index and path in vfs_index[bucket_key]:
                cached_data = vfs_index[bucket_key][path]
                if time.time() - cached_data.get("timestamp", 0) < self._cache_ttl:
                    logger.info(f"Using cached file list for {bucket_key}:{path}")
                    return {
                        "success": True,
                        "source": "metadata_cache",
                        "path": path,
                        "bucket": bucket,
                        "items": cached_data.get("items", []),
                        "cached_at": cached_data.get("timestamp")
                    }
            
            # Fall back to filesystem scan (this would normally call the library)
            logger.info(f"Cache miss for {bucket_key}:{path}, falling back to filesystem")
            
            # For now, return indication that library call is needed
            return {
                "success": False,
                "source": "needs_library_call",
                "path": path,
                "bucket": bucket,
                "reason": "not_in_cache"
            }
            
        except Exception as e:
            logger.error(f"Error in files_list_metadata_first: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "metadata_error"
            }
    
    async def files_stats_metadata_first(self, path: str, bucket: str = None) -> Dict[str, Any]:
        """Get file stats from metadata first."""
        try:
            file_metadata = self._read_metadata(self.file_metadata_path, {})
            file_key = f"{bucket or 'default'}:{path}"
            
            if file_key in file_metadata:
                metadata = file_metadata[file_key]
                # Check if metadata is recent
                if time.time() - time.mktime(datetime.fromisoformat(metadata.get("timestamp", "1970-01-01")).timetuple()) < self._cache_ttl:
                    logger.info(f"Using cached file stats for {file_key}")
                    return {
                        "success": True,
                        "source": "metadata_cache",
                        **metadata
                    }
            
            return {
                "success": False,
                "source": "needs_library_call",
                "path": path,
                "bucket": bucket,
                "reason": "not_in_cache"
            }
            
        except Exception as e:
            logger.error(f"Error in files_stats_metadata_first: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def bucket_list_metadata_first(self) -> Dict[str, Any]:
        """List buckets from metadata first."""
        try:
            bucket_metadata = self._read_metadata(self.bucket_metadata_path, {})
            
            if "buckets" in bucket_metadata:
                cached_time = bucket_metadata.get("last_updated", 0)
                if time.time() - cached_time < self._cache_ttl:
                    logger.info("Using cached bucket list")
                    return {
                        "success": True,
                        "source": "metadata_cache",
                        "buckets": bucket_metadata["buckets"],
                        "cached_at": cached_time
                    }
            
            return {
                "success": False,
                "source": "needs_library_call",
                "reason": "not_in_cache"
            }
            
        except Exception as e:
            logger.error(f"Error in bucket_list_metadata_first: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def pin_list_metadata_first(self) -> Dict[str, Any]:
        """List pins from metadata first."""
        try:
            pin_metadata = self._read_metadata(self.pin_metadata_path, {})
            
            if "pins" in pin_metadata:
                cached_time = pin_metadata.get("last_updated", 0)
                if time.time() - cached_time < self._cache_ttl:
                    logger.info("Using cached pin list")
                    return {
                        "success": True,
                        "source": "metadata_cache",
                        "pins": pin_metadata["pins"],
                        "cached_at": cached_time
                    }
            
            return {
                "success": False,
                "source": "needs_library_call",
                "reason": "not_in_cache"
            }
            
        except Exception as e:
            logger.error(f"Error in pin_list_metadata_first: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_file_metadata(self, path: str, bucket: str, operation: str, **kwargs) -> bool:
        """Update file metadata after an operation."""
        try:
            file_metadata = self._read_metadata(self.file_metadata_path, {})
            file_key = f"{bucket or 'default'}:{path}"
            
            file_metadata[file_key] = {
                "path": path,
                "bucket": bucket,
                "operation": operation,
                "timestamp": datetime.now(UTC).isoformat(),
                **kwargs
            }
            
            return self._write_metadata(self.file_metadata_path, file_metadata)
            
        except Exception as e:
            logger.error(f"Error updating file metadata: {e}")
            return False
    
    def update_vfs_index(self, bucket: str, path: str, items: List[Dict[str, Any]]) -> bool:
        """Update VFS index with directory listing."""
        try:
            vfs_index = self._read_metadata(self.vfs_index_path, {})
            bucket_key = bucket or "default"
            
            if bucket_key not in vfs_index:
                vfs_index[bucket_key] = {}
                
            vfs_index[bucket_key][path] = {
                "items": items,
                "timestamp": time.time(),
                "item_count": len(items)
            }
            
            return self._write_metadata(self.vfs_index_path, vfs_index)
            
        except Exception as e:
            logger.error(f"Error updating VFS index: {e}")
            return False
    
    def invalidate_cache(self, pattern: str = None) -> None:
        """Invalidate metadata cache."""
        if pattern:
            # Invalidate specific patterns
            keys_to_remove = [k for k in self._metadata_cache.keys() if pattern in k]
            for key in keys_to_remove:
                self._metadata_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
        else:
            # Clear all cache
            self._metadata_cache.clear()
            self._cache_timestamps.clear()
        
        logger.info(f"Invalidated cache for pattern: {pattern or 'all'}")

# Global instance
_metadata_tools = None

def get_metadata_tools(data_dir: Optional[str] = None) -> MetadataFirstTools:
    """Get or create the global metadata tools instance."""
    global _metadata_tools
    if _metadata_tools is None:
        _metadata_tools = MetadataFirstTools(data_dir)
    return _metadata_tools

# Tool functions that use metadata-first approach
async def files_list_enhanced(path: str = ".", bucket: str = None) -> Dict[str, Any]:
    """Enhanced files list with metadata-first approach."""
    tools = get_metadata_tools()
    return await tools.files_list_metadata_first(path, bucket)

async def files_stats_enhanced(path: str, bucket: str = None) -> Dict[str, Any]:
    """Enhanced file stats with metadata-first approach."""
    tools = get_metadata_tools()
    return await tools.files_stats_metadata_first(path, bucket)

async def bucket_list_enhanced() -> Dict[str, Any]:
    """Enhanced bucket list with metadata-first approach."""
    tools = get_metadata_tools()
    return await tools.bucket_list_metadata_first()

async def pin_list_enhanced() -> Dict[str, Any]:
    """Enhanced pin list with metadata-first approach."""
    tools = get_metadata_tools()
    return await tools.pin_list_metadata_first()

# Enhanced tool map
ENHANCED_TOOL_MAP = {
    "files_list_enhanced": files_list_enhanced,
    "files_stats_enhanced": files_stats_enhanced, 
    "bucket_list_enhanced": bucket_list_enhanced,
    "pin_list_enhanced": pin_list_enhanced,
}
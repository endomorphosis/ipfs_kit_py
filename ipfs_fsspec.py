#!/usr/bin/env python3
"""
IPFS VFS Integration using fsspec
=================================

This module provides a unified virtual filesystem interface for IPFS and other backends
using fsspec. It supports multi-backend storage, automatic caching, and redundancy.

Key Features:
- Multi-backend support (IPFS, S3, Local, HuggingFace, etc.)
- Automatic caching with configurable tiers
- Redundancy and failover
- Unified API for all filesystem operations
- Integration with the MCP server
"""

import os
import json
import asyncio
import logging
import hashlib
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
from urllib.parse import urlparse
import subprocess
import psutil

# fsspec imports
import fsspec
from fsspec.implementations.local import LocalFileSystem
from fsspec.implementations.memory import MemoryFileSystem
from fsspec.implementations.cached import CachingFileSystem
from fsspec.implementations.dirfs import DirFileSystem

# Optional backend imports (graceful fallback if not available)
try:
    from s3fs import S3FileSystem
    HAS_S3FS = True
except ImportError:
    HAS_S3FS = False

try:
    from huggingface_hub import HfFileSystem
    HAS_HUGGINGFACE = True
except ImportError:
    HAS_HUGGINGFACE = False

# Configure logging
logger = logging.getLogger(__name__)


class IPFSFileSystem(fsspec.AbstractFileSystem):
    """
    Custom fsspec filesystem for IPFS operations.
    """
    
    protocol = "ipfs"
    
    def __init__(self, api_url="http://127.0.0.1:5001", **kwargs):
        super().__init__(**kwargs)
        self.api_url = api_url
        self.session = None
        
    def _test_connection(self) -> bool:
        """Test IPFS connection."""
        try:
            result = subprocess.run(
                ["ipfs", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _ls(self, path, detail=True, **kwargs):
        """List directory contents."""
        try:
            # Handle IPFS paths
            if path.startswith("/ipfs/"):
                cid = path.replace("/ipfs/", "").split("/")[0]
                sub_path = "/".join(path.replace("/ipfs/", "").split("/")[1:])
                
                cmd = ["ipfs", "ls", cid]
                if sub_path:
                    cmd.append(sub_path)
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    entries = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 3:
                                hash_val = parts[0]
                                size = parts[1] if parts[1] != '-' else 0
                                name = " ".join(parts[2:])
                                
                                entry = {
                                    "name": name,
                                    "size": int(size) if size != '-' else 0,
                                    "type": "directory" if size == '-' else "file",
                                    "hash": hash_val
                                }
                                
                                if detail:
                                    entries.append(entry)
                                else:
                                    entries.append(name)
                    
                    return entries
                else:
                    raise FileNotFoundError(f"IPFS path not found: {path}")
            else:
                raise ValueError(f"Invalid IPFS path: {path}")
                
        except Exception as e:
            logger.error(f"Error listing IPFS path {path}: {e}")
            raise
    
    def _cat_file(self, path, start=None, end=None, **kwargs):
        """Read file content."""
        try:
            if path.startswith("/ipfs/"):
                cid = path.replace("/ipfs/", "")
                
                cmd = ["ipfs", "cat", cid]
                result = subprocess.run(cmd, capture_output=True, timeout=60)
                
                if result.returncode == 0:
                    content = result.stdout
                    if start is not None or end is not None:
                        start = start or 0
                        end = end or len(content)
                        content = content[start:end]
                    return content
                else:
                    raise FileNotFoundError(f"IPFS content not found: {path}")
            else:
                raise ValueError(f"Invalid IPFS path: {path}")
                
        except Exception as e:
            logger.error(f"Error reading IPFS file {path}: {e}")
            raise
    
    def _put_file(self, lpath, rpath, **kwargs):
        """Upload file to IPFS."""
        try:
            cmd = ["ipfs", "add", "-Q", lpath]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                cid = result.stdout.strip()
                return f"/ipfs/{cid}"
            else:
                raise IOError(f"Failed to add file to IPFS: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error uploading file to IPFS: {e}")
            raise
    
    def _info(self, path, **kwargs):
        """Get file/directory information."""
        try:
            if path.startswith("/ipfs/"):
                cid = path.replace("/ipfs/", "").split("/")[0]
                
                # Use ipfs object stat for basic info
                cmd = ["ipfs", "object", "stat", cid]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    info = {"name": path, "type": "file"}
                    
                    for line in lines:
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip().lower()
                            value = value.strip()
                            
                            if key == "cumulativesize":
                                info["size"] = int(value)
                            elif key == "numlinks":
                                info["links"] = int(value)
                                if int(value) > 0:
                                    info["type"] = "directory"
                    
                    return info
                else:
                    raise FileNotFoundError(f"IPFS object not found: {path}")
            else:
                raise ValueError(f"Invalid IPFS path: {path}")
                
        except Exception as e:
            logger.error(f"Error getting IPFS info for {path}: {e}")
            raise


class VFSBackendRegistry:
    """Registry for VFS backends."""
    
    def __init__(self):
        self.backends = {}
        self.default_backend = "local"
        self._register_default_backends()
    
    def _register_default_backends(self):
        """Register default backends."""
        # Local filesystem
        self.backends["local"] = {
            "class": LocalFileSystem,
            "kwargs": {},
            "available": True
        }
        
        # Memory filesystem
        self.backends["memory"] = {
            "class": MemoryFileSystem,
            "kwargs": {},
            "available": True
        }
        
        # IPFS filesystem
        self.backends["ipfs"] = {
            "class": IPFSFileSystem,
            "kwargs": {},
            "available": True
        }
        
        # S3 filesystem (if available)
        if HAS_S3FS:
            self.backends["s3"] = {
                "class": S3FileSystem,
                "kwargs": {},
                "available": True
            }
        
        # HuggingFace filesystem (if available)
        if HAS_HUGGINGFACE:
            self.backends["huggingface"] = {
                "class": HfFileSystem,
                "kwargs": {},
                "available": True
            }
    
    def register_backend(self, name: str, fs_class, kwargs: Dict[str, Any] = None):
        """Register a new backend."""
        self.backends[name] = {
            "class": fs_class,
            "kwargs": kwargs or {},
            "available": True
        }
    
    def get_backend(self, name: str) -> Optional[Dict[str, Any]]:
        """Get backend configuration."""
        return self.backends.get(name)
    
    def list_backends(self) -> List[str]:
        """List available backends."""
        return [name for name, config in self.backends.items() if config["available"]]
    
    def create_filesystem(self, backend_name: str, **kwargs) -> fsspec.AbstractFileSystem:
        """Create a filesystem instance."""
        if backend_name not in self.backends:
            raise ValueError(f"Unknown backend: {backend_name}")
        
        backend_config = self.backends[backend_name]
        if not backend_config["available"]:
            raise ValueError(f"Backend not available: {backend_name}")
        
        # Merge kwargs with backend defaults
        fs_kwargs = backend_config["kwargs"].copy()
        fs_kwargs.update(kwargs)
        
        return backend_config["class"](**fs_kwargs)


class VFSCacheManager:
    """Multi-tier caching system for VFS."""
    
    def __init__(self, cache_dir: str = None, max_size: int = 1024*1024*1024):  # 1GB default
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "vfs_cache")
        self.max_size = max_size
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "size": 0
        }
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize cache metadata
        self.metadata_file = os.path.join(self.cache_dir, "metadata.json")
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"entries": {}, "lru_order": []}
    
    def _save_metadata(self):
        """Save cache metadata."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")
    
    def _get_cache_key(self, path: str, backend: str) -> str:
        """Generate cache key for a path."""
        key_data = f"{backend}:{path}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get cache file path."""
        return os.path.join(self.cache_dir, cache_key)
    
    def _update_lru(self, cache_key: str):
        """Update LRU order."""
        if cache_key in self.metadata["lru_order"]:
            self.metadata["lru_order"].remove(cache_key)
        self.metadata["lru_order"].append(cache_key)
    
    def _evict_if_needed(self, new_size: int):
        """Evict cache entries if needed."""
        current_size = sum(entry["size"] for entry in self.metadata["entries"].values())
        
        while current_size + new_size > self.max_size and self.metadata["lru_order"]:
            # Remove oldest entry
            oldest_key = self.metadata["lru_order"].pop(0)
            if oldest_key in self.metadata["entries"]:
                entry = self.metadata["entries"][oldest_key]
                cache_path = self._get_cache_path(oldest_key)
                
                try:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    current_size -= entry["size"]
                    del self.metadata["entries"][oldest_key]
                    self.cache_stats["evictions"] += 1
                except Exception as e:
                    logger.warning(f"Failed to evict cache entry {oldest_key}: {e}")
    
    def get(self, path: str, backend: str) -> Optional[bytes]:
        """Get cached content."""
        cache_key = self._get_cache_key(path, backend)
        cache_path = self._get_cache_path(cache_key)
        
        if cache_key in self.metadata["entries"] and os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    content = f.read()
                
                self._update_lru(cache_key)
                self.cache_stats["hits"] += 1
                return content
            except Exception as e:
                logger.warning(f"Failed to read cache entry {cache_key}: {e}")
                # Remove corrupted entry
                self._remove_entry(cache_key)
        
        self.cache_stats["misses"] += 1
        return None
    
    def put(self, path: str, backend: str, content: bytes):
        """Cache content."""
        cache_key = self._get_cache_key(path, backend)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            # Evict if needed
            self._evict_if_needed(len(content))
            
            # Write content
            with open(cache_path, 'wb') as f:
                f.write(content)
            
            # Update metadata
            self.metadata["entries"][cache_key] = {
                "path": path,
                "backend": backend,
                "size": len(content),
                "timestamp": datetime.now().isoformat()
            }
            self._update_lru(cache_key)
            self._save_metadata()
            
        except Exception as e:
            logger.warning(f"Failed to cache content for {path}: {e}")
    
    def _remove_entry(self, cache_key: str):
        """Remove cache entry."""
        cache_path = self._get_cache_path(cache_key)
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
            if cache_key in self.metadata["entries"]:
                del self.metadata["entries"][cache_key]
            if cache_key in self.metadata["lru_order"]:
                self.metadata["lru_order"].remove(cache_key)
            self._save_metadata()
        except Exception as e:
            logger.warning(f"Failed to remove cache entry {cache_key}: {e}")
    
    def clear(self):
        """Clear all cache."""
        try:
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            self.metadata = {"entries": {}, "lru_order": []}
            self._save_metadata()
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_size = sum(entry["size"] for entry in self.metadata["entries"].values())
        return {
            **self.cache_stats,
            "current_size": current_size,
            "max_size": self.max_size,
            "hit_ratio": self.cache_stats["hits"] / (self.cache_stats["hits"] + self.cache_stats["misses"]) if (self.cache_stats["hits"] + self.cache_stats["misses"]) > 0 else 0.0
        }


class VFSReplicationManager:
    """Manages file replication across backends."""
    
    def __init__(self, vfs_core):
        self.vfs_core = vfs_core
        self.replication_policies = {}  # pattern -> policy
        self.replication_status = {}    # file_path -> status
        self.replica_metadata = {}      # file_path -> {backend: metadata}
        
    def add_replication_policy(self, path_pattern: str, backends: List[str], min_replicas: int = 2) -> Dict[str, Any]:
        """Add a replication policy for files matching a pattern."""
        try:
            # Validate backends
            available_backends = self.vfs_core.registry.list_backends()
            invalid_backends = [b for b in backends if b not in available_backends]
            if invalid_backends:
                return {
                    "success": False,
                    "error": f"Invalid backends: {invalid_backends}",
                    "available_backends": available_backends
                }
            
            # Store policy
            self.replication_policies[path_pattern] = {
                "backends": backends,
                "min_replicas": min_replicas,
                "created_at": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "pattern": path_pattern,
                "backends": backends,
                "min_replicas": min_replicas
            }
            
        except Exception as e:
            logger.error(f"Failed to add replication policy: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_replication_policies(self) -> Dict[str, Any]:
        """List all replication policies."""
        try:
            policies = []
            for pattern, policy in self.replication_policies.items():
                policies.append({
                    "pattern": pattern,
                    "backends": policy["backends"],
                    "min_replicas": policy["min_replicas"],
                    "created_at": policy["created_at"]
                })
            
            return {
                "success": True,
                "policies": policies,
                "count": len(policies)
            }
            
        except Exception as e:
            logger.error(f"Failed to list replication policies: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if a file path matches a pattern."""
        import fnmatch
        return fnmatch.fnmatch(file_path, pattern)
    
    def _get_applicable_policies(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all policies applicable to a file."""
        applicable = []
        for pattern, policy in self.replication_policies.items():
            if self._matches_pattern(file_path, pattern):
                applicable.append({
                    "pattern": pattern,
                    **policy
                })
        return applicable
    
    def replicate_file(self, file_path: str, force: bool = False) -> Dict[str, Any]:
        """Replicate a file according to policies."""
        try:
            # Get applicable policies
            policies = self._get_applicable_policies(file_path)
            if not policies:
                return {
                    "success": False,
                    "error": "No replication policies apply to this file",
                    "file_path": file_path
                }
            
            # Use the most restrictive policy (highest min_replicas)
            target_policy = max(policies, key=lambda p: p["min_replicas"])
            target_backends = target_policy["backends"]
            min_replicas = target_policy["min_replicas"]
            
            # Check current replication status
            current_replicas = self.replica_metadata.get(file_path, {})
            
            # Read source file
            source_backend, source_path, _ = self.vfs_core._resolve_path(file_path)
            if source_backend not in self.vfs_core.filesystems:
                return {
                    "success": False,
                    "error": f"Source backend '{source_backend}' not available",
                    "file_path": file_path
                }
            
            source_fs = self.vfs_core.filesystems[source_backend]
            try:
                source_content = source_fs.cat_file(source_path)
                source_hash = hashlib.sha256(source_content).hexdigest()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to read source file: {e}",
                    "file_path": file_path
                }
            
            # Replicate to target backends
            replicated_to = []
            failed_to = []
            
            for backend in target_backends:
                # Skip if already exists and force=False
                if backend in current_replicas and not force:
                    # Verify integrity
                    try:
                        existing_hash = current_replicas[backend].get("hash")
                        if existing_hash == source_hash:
                            replicated_to.append(backend)
                            continue
                    except Exception:
                        pass
                
                # Replicate to backend
                try:
                    if backend not in self.vfs_core.filesystems:
                        self.vfs_core.filesystems[backend] = self.vfs_core.registry.create_filesystem(backend)
                    
                    backend_fs = self.vfs_core.filesystems[backend]
                    
                    # Write content
                    with backend_fs.open(source_path, 'wb') as f:
                        f.write(source_content)
                    
                    # Update metadata
                    if file_path not in self.replica_metadata:
                        self.replica_metadata[file_path] = {}
                    
                    self.replica_metadata[file_path][backend] = {
                        "hash": source_hash,
                        "size": len(source_content),
                        "replicated_at": datetime.now().isoformat()
                    }
                    
                    replicated_to.append(backend)
                    
                except Exception as e:
                    logger.error(f"Failed to replicate to {backend}: {e}")
                    failed_to.append({
                        "backend": backend,
                        "error": str(e)
                    })
            
            # Update replication status
            self.replication_status[file_path] = {
                "replicated_to": replicated_to,
                "failed_to": failed_to,
                "min_replicas": min_replicas,
                "current_replicas": len(replicated_to),
                "healthy": len(replicated_to) >= min_replicas,
                "last_replication": datetime.now().isoformat()
            }
            
            return {
                "success": len(replicated_to) >= min_replicas,
                "file_path": file_path,
                "replicated_to": replicated_to,
                "failed_to": failed_to,
                "min_replicas": min_replicas,
                "current_replicas": len(replicated_to),
                "healthy": len(replicated_to) >= min_replicas
            }
            
        except Exception as e:
            logger.error(f"Failed to replicate file {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def verify_replicas(self, file_path: str) -> Dict[str, Any]:
        """Verify that all replicas of a file are consistent."""
        try:
            if file_path not in self.replica_metadata:
                return {
                    "success": False,
                    "error": "File not found in replication metadata",
                    "file_path": file_path
                }
            
            replicas = self.replica_metadata[file_path]
            verification_results = {}
            reference_hash = None
            
            for backend, metadata in replicas.items():
                try:
                    if backend not in self.vfs_core.filesystems:
                        verification_results[backend] = {
                            "status": "error",
                            "error": "Backend not available"
                        }
                        continue
                    
                    backend_fs = self.vfs_core.filesystems[backend]
                    _, backend_path, _ = self.vfs_core._resolve_path(file_path)
                    
                    # Read and hash content
                    content = backend_fs.cat_file(backend_path)
                    current_hash = hashlib.sha256(content).hexdigest()
                    
                    if reference_hash is None:
                        reference_hash = current_hash
                    
                    verification_results[backend] = {
                        "status": "ok" if current_hash == reference_hash else "corrupted",
                        "hash": current_hash,
                        "size": len(content),
                        "matches_reference": current_hash == reference_hash
                    }
                    
                except Exception as e:
                    verification_results[backend] = {
                        "status": "error",
                        "error": str(e)
                    }
            
            # Count healthy replicas
            healthy_count = sum(1 for r in verification_results.values() if r["status"] == "ok")
            total_count = len(verification_results)
            
            return {
                "success": True,
                "file_path": file_path,
                "verification_results": verification_results,
                "healthy_replicas": healthy_count,
                "total_replicas": total_count,
                "all_consistent": all(r["status"] == "ok" for r in verification_results.values())
            }
            
        except Exception as e:
            logger.error(f"Failed to verify replicas for {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def repair_replicas(self, file_path: str) -> Dict[str, Any]:
        """Repair corrupted replicas by re-copying from source."""
        try:
            # First verify to identify corrupted replicas
            verification = self.verify_replicas(file_path)
            if not verification["success"]:
                return verification
            
            # Find a healthy replica to use as source
            healthy_backends = [
                backend for backend, result in verification["verification_results"].items()
                if result["status"] == "ok"
            ]
            
            if not healthy_backends:
                return {
                    "success": False,
                    "error": "No healthy replicas found to repair from",
                    "file_path": file_path
                }
            
            # Use first healthy backend as source
            source_backend = healthy_backends[0]
            source_fs = self.vfs_core.filesystems[source_backend]
            _, source_path, _ = self.vfs_core._resolve_path(file_path)
            source_content = source_fs.cat_file(source_path)
            source_hash = hashlib.sha256(source_content).hexdigest()
            
            # Repair corrupted replicas
            repaired_backends = []
            failed_repairs = []
            
            for backend, result in verification["verification_results"].items():
                if result["status"] != "ok":
                    try:
                        if backend not in self.vfs_core.filesystems:
                            self.vfs_core.filesystems[backend] = self.vfs_core.registry.create_filesystem(backend)
                        
                        backend_fs = self.vfs_core.filesystems[backend]
                        
                        # Overwrite corrupted replica
                        with backend_fs.open(source_path, 'wb') as f:
                            f.write(source_content)
                        
                        # Update metadata
                        self.replica_metadata[file_path][backend] = {
                            "hash": source_hash,
                            "size": len(source_content),
                            "repaired_at": datetime.now().isoformat()
                        }
                        
                        repaired_backends.append(backend)
                        
                    except Exception as e:
                        logger.error(f"Failed to repair replica on {backend}: {e}")
                        failed_repairs.append({
                            "backend": backend,
                            "error": str(e)
                        })
            
            return {
                "success": len(failed_repairs) == 0,
                "file_path": file_path,
                "repaired_backends": repaired_backends,
                "failed_repairs": failed_repairs,
                "source_backend": source_backend
            }
            
        except Exception as e:
            logger.error(f"Failed to repair replicas for {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def get_replication_status(self, file_path: str) -> Dict[str, Any]:
        """Get replication status for a file."""
        try:
            if file_path not in self.replication_status:
                return {
                    "success": False,
                    "error": "File not found in replication status",
                    "file_path": file_path
                }
            
            status = self.replication_status[file_path]
            
            return {
                "success": True,
                "file_path": file_path,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"Failed to get replication status for {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def get_system_replication_status(self) -> Dict[str, Any]:
        """Get overall replication status for the system."""
        try:
            total_files = len(self.replication_status)
            healthy_files = sum(1 for status in self.replication_status.values() if status["healthy"])
            unhealthy_files = total_files - healthy_files
            
            backend_stats = {}
            for file_path, status in self.replication_status.items():
                for backend in status["replicated_to"]:
                    if backend not in backend_stats:
                        backend_stats[backend] = {"files": 0, "healthy": 0}
                    backend_stats[backend]["files"] += 1
                    if status["healthy"]:
                        backend_stats[backend]["healthy"] += 1
            
            return {
                "success": True,
                "total_files": total_files,
                "healthy_files": healthy_files,
                "unhealthy_files": unhealthy_files,
                "health_ratio": healthy_files / total_files if total_files > 0 else 1.0,
                "backend_stats": backend_stats,
                "policies_count": len(self.replication_policies)
            }
            
        except Exception as e:
            logger.error(f"Failed to get system replication status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def bulk_replicate(self, path_pattern: str = "*") -> Dict[str, Any]:
        """Replicate all files matching a pattern."""
        try:
            # Find all files matching pattern
            replicated_files = []
            failed_files = []
            
            for file_path in self.replication_manager.replication_status.keys():
                if self.replication_manager._matches_pattern(file_path, path_pattern):
                    result = self.replicate_file(file_path)
                    if result["success"]:
                        replicated_files.append(file_path)
                    else:
                        failed_files.append({
                            "path": file_path,
                            "error": result.get("error", "Unknown error")
                        })
            
            return {
                "success": len(failed_files) == 0,
                "pattern": path_pattern,
                "replicated_count": len(replicated_files),
                "failed_count": len(failed_files),
                "replicated": replicated_files,
                "failed": failed_files
            }
            
        except Exception as e:
            logger.error(f"Failed to bulk replicate files: {e}")
            return {
                "success": False,
                "error": str(e),
                "pattern": path_pattern
            }
        

class VFSCore:
    """Core VFS implementation with multi-backend support and replication."""
    
    def __init__(self, cache_dir: str = None, max_cache_size: int = 1024*1024*1024):
        self.registry = VFSBackendRegistry()
        self.cache_manager = VFSCacheManager(cache_dir, max_cache_size)
        self.mounts = {}  # mount_point -> backend_config
        self.filesystems = {}  # backend_name -> filesystem_instance
        
        # Initialize replication manager
        self.replication_manager = VFSReplicationManager(self)
        
        # Initialize default local filesystem
        self.filesystems["local"] = self.registry.create_filesystem("local")
    
    def mount(self, mount_point: str, backend: str, path: str = "/", read_only: bool = True, **kwargs) -> Dict[str, Any]:
        """Mount a backend to a mount point."""
        try:
            # Validate backend
            if backend not in self.registry.list_backends():
                return {
                    "success": False,
                    "error": f"Backend '{backend}' not available",
                    "available_backends": self.registry.list_backends()
                }
            
            # Create filesystem if not exists
            if backend not in self.filesystems:
                self.filesystems[backend] = self.registry.create_filesystem(backend, **kwargs)
            
            # Register mount
            self.mounts[mount_point] = {
                "backend": backend,
                "path": path,
                "read_only": read_only,
                "mounted_at": datetime.now().isoformat(),
                "kwargs": kwargs
            }
            
            return {
                "success": True,
                "mount_point": mount_point,
                "backend": backend,
                "path": path,
                "read_only": read_only,
                "mounted": True
            }
            
        except Exception as e:
            logger.error(f"Failed to mount {backend} at {mount_point}: {e}")
            return {
                "success": False,
                "error": str(e),
                "mount_point": mount_point,
                "backend": backend
            }
    
    def unmount(self, mount_point: str) -> Dict[str, Any]:
        """Unmount a mount point."""
        try:
            if mount_point not in self.mounts:
                return {
                    "success": False,
                    "error": f"Mount point '{mount_point}' not found",
                    "mount_point": mount_point
                }
            
            del self.mounts[mount_point]
            
            return {
                "success": True,
                "mount_point": mount_point,
                "unmounted": True
            }
            
        except Exception as e:
            logger.error(f"Failed to unmount {mount_point}: {e}")
            return {
                "success": False,
                "error": str(e),
                "mount_point": mount_point
            }
    
    def list_mounts(self) -> Dict[str, Any]:
        """List all active mounts."""
        try:
            mount_list = []
            for mount_point, config in self.mounts.items():
                mount_list.append({
                    "mount_point": mount_point,
                    "backend": config["backend"],
                    "path": config["path"],
                    "read_only": config["read_only"],
                    "mounted_at": config["mounted_at"]
                })
            
            return {
                "success": True,
                "mounts": mount_list,
                "count": len(mount_list)
            }
            
        except Exception as e:
            logger.error(f"Failed to list mounts: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _resolve_path(self, vfs_path: str) -> Tuple[str, str, str]:
        """Resolve VFS path to backend and real path."""
        # Find matching mount point
        best_match = ""
        best_config = None
        
        for mount_point, config in self.mounts.items():
            if vfs_path.startswith(mount_point) and len(mount_point) > len(best_match):
                best_match = mount_point
                best_config = config
        
        if best_config:
            # Remove mount point from path
            relative_path = vfs_path[len(best_match):].lstrip('/')
            backend_path = os.path.join(best_config["path"], relative_path).replace('\\', '/')
            return best_config["backend"], backend_path, best_match
        
        # Default to local filesystem
        return "local", vfs_path, ""
    
    def read(self, path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read file content."""
        try:
            backend, backend_path, mount_point = self._resolve_path(path)
            
            # Check cache first
            cached_content = self.cache_manager.get(path, backend)
            if cached_content is not None:
                if encoding == "binary":
                    content = cached_content
                elif encoding == "base64":
                    import base64
                    content = base64.b64encode(cached_content).decode('ascii')
                else:
                    content = cached_content.decode(encoding)
                
                return {
                    "success": True,
                    "path": path,
                    "content": content,
                    "encoding": encoding,
                    "size": len(cached_content),
                    "cached": True
                }
            
            # Read from backend
            if backend not in self.filesystems:
                return {
                    "success": False,
                    "error": f"Backend '{backend}' not available",
                    "path": path
                }
            
            fs = self.filesystems[backend]
            
            if encoding == "binary":
                content = fs.cat_file(backend_path)
                self.cache_manager.put(path, backend, content)
            else:
                raw_content = fs.cat_file(backend_path)
                self.cache_manager.put(path, backend, raw_content)
                
                if encoding == "base64":
                    import base64
                    content = base64.b64encode(raw_content).decode('ascii')
                else:
                    content = raw_content.decode(encoding)
            
            return {
                "success": True,
                "path": path,
                "content": content,
                "encoding": encoding,
                "size": len(raw_content) if encoding != "binary" else len(content),
                "cached": False
            }
            
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    def write(self, path: str, content: Union[str, bytes], encoding: str = "utf-8", create_dirs: bool = True, auto_replicate: bool = True) -> Dict[str, Any]:
        """Write content to file with optional automatic replication."""
        try:
            backend, backend_path, mount_point = self._resolve_path(path)
            
            # Check if mount is read-only
            if mount_point and mount_point in self.mounts:
                if self.mounts[mount_point]["read_only"]:
                    return {
                        "success": False,
                        "error": "Mount point is read-only",
                        "path": path
                    }
            
            if backend not in self.filesystems:
                return {
                    "success": False,
                    "error": f"Backend '{backend}' not available",
                    "path": path
                }
            
            fs = self.filesystems[backend]
            
            # Convert content to bytes
            if isinstance(content, str):
                if encoding == "base64":
                    import base64
                    content_bytes = base64.b64decode(content)
                else:
                    content_bytes = content.encode(encoding)
            else:
                content_bytes = content
            
            # Create parent directories if needed
            if create_dirs:
                parent_dir = os.path.dirname(backend_path)
                if parent_dir and hasattr(fs, 'makedirs'):
                    fs.makedirs(parent_dir, exist_ok=True)
            
            # Write content
            with fs.open(backend_path, 'wb') as f:
                f.write(content_bytes)
            
            # Cache the content
            self.cache_manager.put(path, backend, content_bytes)
            
            result = {
                "success": True,
                "path": path,
                "bytes_written": len(content_bytes),
                "encoding": encoding
            }
            
            # Auto-replicate if enabled
            if auto_replicate:
                try:
                    replication_result = self.replication_manager.replicate_file(path)
                    result["replication"] = replication_result
                except Exception as e:
                    logger.warning(f"Auto-replication failed for {path}: {e}")
                    result["replication"] = {"success": False, "error": str(e)}
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to write {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    def ls(self, path: str, detailed: bool = False, recursive: bool = False) -> Dict[str, Any]:
        """List directory contents."""
        try:
            backend, backend_path, mount_point = self._resolve_path(path)
            
            if backend not in self.filesystems:
                return {
                    "success": False,
                    "error": f"Backend '{backend}' not available",
                    "path": path
                }
            
            fs = self.filesystems[backend]
            
            if recursive:
                entries = []
                for root, dirs, files in fs.walk(backend_path):
                    for name in files + dirs:
                        item_path = os.path.join(root, name).replace('\\', '/')
                        if detailed:
                            try:
                                info = fs.info(item_path)
                                entries.append({
                                    "name": name,
                                    "path": item_path,
                                    "type": info.get("type", "file"),
                                    "size": info.get("size", 0),
                                    "modified": info.get("mtime", "")
                                })
                            except:
                                entries.append({"name": name, "path": item_path})
                        else:
                            entries.append(name)
            else:
                entries = fs.ls(backend_path, detail=detailed)
            
            return {
                "success": True,
                "path": path,
                "entries": entries,
                "count": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Failed to list {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    def stat(self, path: str) -> Dict[str, Any]:
        """Get file/directory statistics."""
        try:
            backend, backend_path, mount_point = self._resolve_path(path)
            
            if backend not in self.filesystems:
                return {
                    "success": False,
                    "error": f"Backend '{backend}' not available",
                    "path": path
                }
            
            fs = self.filesystems[backend]
            info = fs.info(backend_path)
            
            return {
                "success": True,
                "path": path,
                "stat": {
                    "type": info.get("type", "file"),
                    "size": info.get("size", 0),
                    "modified": info.get("mtime", ""),
                    "backend": backend
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to stat {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    def mkdir(self, path: str, parents: bool = True, mode: str = "0755") -> Dict[str, Any]:
        """Create directory."""
        try:
            backend, backend_path, mount_point = self._resolve_path(path)
            
            # Check if mount is read-only
            if mount_point and mount_point in self.mounts:
                if self.mounts[mount_point]["read_only"]:
                    return {
                        "success": False,
                        "error": "Mount point is read-only",
                        "path": path
                    }
            
            if backend not in self.filesystems:
                return {
                    "success": False,
                    "error": f"Backend '{backend}' not available",
                    "path": path
                }
            
            fs = self.filesystems[backend]
            
            if parents:
                fs.makedirs(backend_path, exist_ok=True)
            else:
                fs.mkdir(backend_path)
            
            return {
                "success": True,
                "path": path,
                "mode": mode,
                "created": True
            }
            
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    def rmdir(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Remove directory."""
        try:
            backend, backend_path, mount_point = self._resolve_path(path)
            
            # Check if mount is read-only
            if mount_point and mount_point in self.mounts:
                if self.mounts[mount_point]["read_only"]:
                    return {
                        "success": False,
                        "error": "Mount point is read-only",
                        "path": path
                    }
            
            if backend not in self.filesystems:
                return {
                    "success": False,
                    "error": f"Backend '{backend}' not available",
                    "path": path
                }
            
            fs = self.filesystems[backend]
            
            if recursive:
                fs.rm(backend_path, recursive=True)
            else:
                fs.rmdir(backend_path)
            
            return {
                "success": True,
                "path": path,
                "recursive": recursive,
                "removed": True
            }
            
        except Exception as e:
            logger.error(f"Failed to remove directory {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    def copy(self, source: str, dest: str, preserve_metadata: bool = True) -> Dict[str, Any]:
        """Copy files."""
        try:
            # Resolve source and destination
            src_backend, src_path, src_mount = self._resolve_path(source)
            dst_backend, dst_path, dst_mount = self._resolve_path(dest)
            
            # Check if destination mount is read-only
            if dst_mount and dst_mount in self.mounts:
                if self.mounts[dst_mount]["read_only"]:
                    return {
                        "success": False,
                        "error": "Destination mount point is read-only",
                        "source": source,
                        "dest": dest
                    }
            
            # Get filesystems
            if src_backend not in self.filesystems or dst_backend not in self.filesystems:
                return {
                    "success": False,
                    "error": "Backend not available",
                    "source": source,
                    "dest": dest
                }
            
            src_fs = self.filesystems[src_backend]
            dst_fs = self.filesystems[dst_backend]
            
            # Copy content
            if src_backend == dst_backend:
                # Same backend, use native copy if available
                if hasattr(src_fs, 'copy'):
                    src_fs.copy(src_path, dst_path)
                else:
                    # Fallback to read/write
                    content = src_fs.cat_file(src_path)
                    with dst_fs.open(dst_path, 'wb') as f:
                        f.write(content)
            else:
                # Cross-backend copy
                content = src_fs.cat_file(src_path)
                with dst_fs.open(dst_path, 'wb') as f:
                    f.write(content)
            
            return {
                "success": True,
                "source": source,
                "dest": dest,
                "preserve_metadata": preserve_metadata,
                "copied": True
            }
            
        except Exception as e:
            logger.error(f"Failed to copy {source} to {dest}: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": source,
                "dest": dest
            }
    
    def move(self, source: str, dest: str) -> Dict[str, Any]:
        """Move/rename files."""
        try:
            # Copy then delete
            copy_result = self.copy(source, dest)
            if not copy_result["success"]:
                return copy_result
            
            # Delete source
            src_backend, src_path, src_mount = self._resolve_path(source)
            
            # Check if source mount is read-only
            if src_mount and src_mount in self.mounts:
                if self.mounts[src_mount]["read_only"]:
                    return {
                        "success": False,
                        "error": "Source mount point is read-only",
                        "source": source,
                        "dest": dest
                    }
            
            if src_backend in self.filesystems:
                src_fs = self.filesystems[src_backend]
                src_fs.rm(src_path)
            
            return {
                "success": True,
                "source": source,
                "dest": dest,
                "moved": True
            }
            
        except Exception as e:
            logger.error(f"Failed to move {source} to {dest}: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": source,
                "dest": dest
            }
    
    def sync_to_ipfs(self, path: str = "/", recursive: bool = True) -> Dict[str, Any]:
        """Sync VFS changes to IPFS."""
        try:
            # This would implement syncing local changes to IPFS
            # For now, return a mock response indicating the feature needs implementation
            return {
                "success": False,
                "error": "IPFS sync not yet implemented",
                "path": path,
                "recursive": recursive,
                "is_mock": True,
                "warning": "This feature requires additional IPFS integration"
            }
            
        except Exception as e:
            logger.error(f"Failed to sync to IPFS: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    def sync_from_ipfs(self, ipfs_path: str, vfs_path: str, force: bool = False) -> Dict[str, Any]:
        """Sync IPFS content to VFS."""
        try:
            # This would implement syncing IPFS content to local VFS
            # For now, return a mock response indicating the feature needs implementation
            return {
                "success": False,
                "error": "IPFS sync not yet implemented",
                "ipfs_path": ipfs_path,
                "vfs_path": vfs_path,
                "force": force,
                "is_mock": True,
                "warning": "This feature requires additional IPFS integration"
            }
            
        except Exception as e:
            logger.error(f"Failed to sync from IPFS: {e}")
            return {
                "success": False,
                "error": str(e),
                "ipfs_path": ipfs_path,
                "vfs_path": vfs_path
            }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_stats()
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear cache."""
        try:
            self.cache_manager.clear()
            return {
                "success": True,
                "message": "Cache cleared successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # Replication methods
    def add_replication_policy(self, path_pattern: str, backends: List[str], min_replicas: int = 2) -> Dict[str, Any]:
        """Add a replication policy for files matching a pattern."""
        return self.replication_manager.add_replication_policy(path_pattern, backends, min_replicas)
    
    def replicate_file(self, file_path: str, force: bool = False) -> Dict[str, Any]:
        """Replicate a file according to policies."""
        return self.replication_manager.replicate_file(file_path, force)
    
    def verify_replicas(self, file_path: str) -> Dict[str, Any]:
        """Verify that all replicas of a file are consistent."""
        return self.replication_manager.verify_replicas(file_path)
    
    def repair_replicas(self, file_path: str) -> Dict[str, Any]:
        """Repair corrupted replicas by re-copying from source."""
        return self.replication_manager.repair_replicas(file_path)
    
    def get_replication_status(self, file_path: str) -> Dict[str, Any]:
        """Get replication status for a file."""
        return self.replication_manager.get_replication_status(file_path)
    
    def list_replication_policies(self) -> Dict[str, Any]:
        """List all replication policies."""
        return self.replication_manager.list_replication_policies()
    
    def get_system_replication_status(self) -> Dict[str, Any]:
        """Get overall replication status for the system."""
        return self.replication_manager.get_system_replication_status()
    
    def bulk_replicate(self, path_pattern: str = "*") -> Dict[str, Any]:
        """Replicate all files matching a pattern."""
        try:
            # Find all files matching pattern
            replicated_files = []
            failed_files = []
            
            for file_path in self.replication_manager.replication_status.keys():
                if self.replication_manager._matches_pattern(file_path, path_pattern):
                    result = self.replicate_file(file_path)
                    if result["success"]:
                        replicated_files.append(file_path)
                    else:
                        failed_files.append({
                            "path": file_path,
                            "error": result.get("error", "Unknown error")
                        })
            
            return {
                "success": len(failed_files) == 0,
                "pattern": path_pattern,
                "replicated_count": len(replicated_files),
                "failed_count": len(failed_files),
                "replicated": replicated_files,
                "failed": failed_files
            }
            
        except Exception as e:
            logger.error(f"Failed to bulk replicate files: {e}")
            return {
                "success": False,
                "error": str(e),
                "pattern": path_pattern
            }


# Global VFS instance
_vfs_instance = None


def get_vfs() -> VFSCore:
    """Get global VFS instance."""
    global _vfs_instance
    if _vfs_instance is None:
        _vfs_instance = VFSCore()
    return _vfs_instance


# VFS Tool Functions for MCP Integration
async def vfs_mount(ipfs_path: str, mount_point: str, read_only: bool = True) -> Dict[str, Any]:
    """Mount an IPFS path to a VFS mount point."""
    vfs = get_vfs()
    
    # Determine backend from path
    if ipfs_path.startswith("/ipfs/"):
        backend = "ipfs"
        path = ipfs_path
    elif ipfs_path.startswith("s3://"):
        backend = "s3"
        path = ipfs_path
    elif ipfs_path.startswith("hf://"):
        backend = "huggingface"
        path = ipfs_path
    else:
        backend = "local"
        path = ipfs_path
    
    return vfs.mount(mount_point, backend, path, read_only)


async def vfs_unmount(mount_point: str) -> Dict[str, Any]:
    """Unmount a VFS mount point."""
    vfs = get_vfs()
    return vfs.unmount(mount_point)


async def vfs_list_mounts() -> Dict[str, Any]:
    """List all VFS mounts."""
    vfs = get_vfs()
    return vfs.list_mounts()


async def vfs_read(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Read file from VFS."""
    vfs = get_vfs()
    return vfs.read(path, encoding)


async def vfs_write(path: str, content: str, encoding: str = "utf-8", create_dirs: bool = True) -> Dict[str, Any]:
    """Write file to VFS."""
    vfs = get_vfs()
    return vfs.write(path, content, encoding, create_dirs)


async def vfs_ls(path: str, detailed: bool = False, recursive: bool = False) -> Dict[str, Any]:
    """List VFS directory contents."""
    vfs = get_vfs()
    return vfs.ls(path, detailed, recursive)


async def vfs_stat(path: str) -> Dict[str, Any]:
    """Get VFS file/directory statistics."""
    vfs = get_vfs()
    return vfs.stat(path)


async def vfs_mkdir(path: str, parents: bool = True, mode: str = "0755") -> Dict[str, Any]:
    """Create VFS directory."""
    vfs = get_vfs()
    return vfs.mkdir(path, parents, mode)


async def vfs_rmdir(path: str, recursive: bool = False) -> Dict[str, Any]:
    """Remove VFS directory."""
    vfs = get_vfs()
    return vfs.rmdir(path, recursive)


async def vfs_copy(source: str, dest: str, preserve_metadata: bool = True) -> Dict[str, Any]:
    """Copy files in VFS."""
    vfs = get_vfs()
    return vfs.copy(source, dest, preserve_metadata)


async def vfs_move(source: str, dest: str) -> Dict[str, Any]:
    """Move files in VFS."""
    vfs = get_vfs()
    return vfs.move(source, dest)


async def vfs_sync_to_ipfs(path: str = "/", recursive: bool = True) -> Dict[str, Any]:
    """Sync VFS to IPFS."""
    vfs = get_vfs()
    return vfs.sync_to_ipfs(path, recursive)


async def vfs_sync_from_ipfs(ipfs_path: str, vfs_path: str, force: bool = False) -> Dict[str, Any]:
    """Sync IPFS to VFS."""
    vfs = get_vfs()
    return vfs.sync_from_ipfs(ipfs_path, vfs_path, force)


async def vfs_add_replication_policy(path_pattern: str, backends: List[str], min_replicas: int = 2) -> Dict[str, Any]:
    """Add a replication policy for files matching a pattern."""
    vfs = get_vfs()
    return vfs.add_replication_policy(path_pattern, backends, min_replicas)


async def vfs_replicate_file(file_path: str, force: bool = False) -> Dict[str, Any]:
    """Replicate a file according to policies."""
    vfs = get_vfs()
    return vfs.replicate_file(file_path, force)


async def vfs_verify_replicas(file_path: str) -> Dict[str, Any]:
    """Verify that all replicas of a file are consistent."""
    vfs = get_vfs()
    return vfs.verify_replicas(file_path)


async def vfs_repair_replicas(file_path: str) -> Dict[str, Any]:
    """Repair corrupted replicas by re-copying from source."""
    vfs = get_vfs()
    return vfs.repair_replicas(file_path)


async def vfs_get_replication_status(file_path: str) -> Dict[str, Any]:
    """Get replication status for a file."""
    vfs = get_vfs()
    return vfs.get_replication_status(file_path)


async def vfs_list_replication_policies() -> Dict[str, Any]:
    """List all replication policies."""
    vfs = get_vfs()
    return vfs.list_replication_policies()


async def vfs_get_system_replication_status() -> Dict[str, Any]:
    """Get overall replication status for the system."""
    vfs = get_vfs()
    return vfs.get_system_replication_status()


async def vfs_bulk_replicate(path_pattern: str = "*") -> Dict[str, Any]:
    """Replicate all files matching a pattern."""
    vfs = get_vfs()
    return vfs.bulk_replicate(path_pattern)


async def vfs_get_cache_stats() -> Dict[str, Any]:
    """Get VFS cache statistics."""
    vfs = get_vfs()
    return vfs.get_cache_stats()


async def vfs_clear_cache() -> Dict[str, Any]:
    """Clear VFS cache."""
    vfs = get_vfs()
    return vfs.clear_cache()


# Export main classes and functions
__all__ = [
    "VFSCore",
    "VFSBackendRegistry", 
    "VFSCacheManager",
    "VFSReplicationManager",
    "IPFSFileSystem",
    "get_vfs",
    "vfs_mount",
    "vfs_unmount",
    "vfs_list_mounts",
    "vfs_read",
    "vfs_write",
    "vfs_ls",
    "vfs_stat",
    "vfs_mkdir",
    "vfs_rmdir",
    "vfs_copy",
    "vfs_move",
    "vfs_sync_to_ipfs",
    "vfs_sync_from_ipfs",
    "vfs_add_replication_policy",
    "vfs_replicate_file",
    "vfs_verify_replicas", 
    "vfs_repair_replicas",
    "vfs_get_replication_status",
    "vfs_list_replication_policies",
    "vfs_get_system_replication_status",
    "vfs_bulk_replicate",
    "vfs_get_cache_stats",
    "vfs_clear_cache"
]

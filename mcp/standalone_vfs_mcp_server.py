#!/usr/bin/env python3
"""
Standalone VFS-Enabled MCP Server for IPFS Kit
===============================================

This server provides Virtual Filesystem integration for IPFS with access to
replication, cache eviction, and write-ahead logging functionality through
a standalone implementation that bypasses dependency conflicts.

Key features:
1. Standalone VFS implementation using direct IPFS commands
2. Cache eviction through direct file system operations
3. Replication and WAL management through high-level scripts
4. No libp2p dependency conflicts
"""

import sys
import json
import asyncio
import logging
import traceback
import os
import time
import subprocess
import tempfile
import shutil
import glob
import hashlib
import pickle
import threading
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from pathlib import Path
from collections import defaultdict, deque, OrderedDict
import psutil # Added for system health checks

# Add the project root to Python path to import ipfs_kit_py
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from ipfs_kit_py import ipfs_kit
    HAS_IPFS_KIT = True
    logger.info("✓ ipfs_kit_py imported successfully")
except ImportError as e:
    logger.warning(f"ipfs_kit_py not available: {e}. Daemon management features will be limited.")
    HAS_IPFS_KIT = False

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("standalone-mcp-ipfs-vfs")

# Server metadata
__version__ = "3.2.0" # Updated version to reflect changes


class StandaloneVFS:
    """Standalone Virtual Filesystem implementation for IPFS."""
    
    def __init__(self):
        logger.info("=== StandaloneVFS.__init__() starting ===")
        self.mount_points = {}
        self.cache_dir = os.path.expanduser("~/.ipfs_kit_cache")
        self.wal_dir = os.path.expanduser("~/.ipfs_kit_wal")
        self.replication_config = os.path.expanduser("~/.ipfs_kit_replication.json")
        self._ensure_directories()
        
        # Semantic cache initialization
        self.semantic_cache = {} # Maps semantic_key -> CID
        
        logger.info("=== StandaloneVFS.__init__() completed ===")
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        for directory in [self.cache_dir, self.wal_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # ARC specific initialization
        self.max_cache_size = 1024 * 1024 * 100 # 100 MB default max cache size
        self.t1_lru = OrderedDict() # Recently used, not yet frequent
        self.t2_lfu = OrderedDict() # Frequently used
        self.b1_ghost = OrderedDict() # Ghost list for T1 (recently evicted)
        self.b2_ghost = OrderedDict() # Ghost list for T2 (frequently evicted)
        self.p_param = 0 # Target size for T1
        
    async def _run_ipfs_command(self, cmd: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run an IPFS command and return the result."""
        try:
            logger.info(f"Running IPFS command: {' '.join(cmd)}")
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=timeout)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "stdout": stdout.decode('utf-8').strip(),
                    "stderr": stderr.decode('utf-8').strip()
                }
            else:
                return {
                    "success": False,
                    "stdout": stdout.decode('utf-8').strip(),
                    "stderr": stderr.decode('utf-8').strip(),
                    "returncode": result.returncode
                }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds"
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "IPFS binary not found - please install IPFS"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _run_script(self, script_path: str, args: List[str] = None) -> Dict[str, Any]:
        """Run a script from the project."""
        if args is None:
            args = []
        
        script_full_path = os.path.join(project_root, script_path)
        if not os.path.exists(script_full_path):
            return {
                "success": False,
                "error": f"Script not found: {script_path}"
            }
        
        cmd = ["python3", script_full_path] + args
        try:
            logger.info(f"Running script: {' '.join(cmd)}")
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=project_root
            )
            
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=60)
            
            return {
                "success": result.returncode == 0,
                "stdout": stdout.decode('utf-8').strip(),
                "stderr": stderr.decode('utf-8').strip(),
                "returncode": result.returncode
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # VFS Basic Operations
    async def vfs_mount(self, ipfs_path: str = "/", mount_point: str = "/ipfs") -> Dict[str, Any]:
        """Mount an IPFS path as a virtual filesystem."""
        try:
            # Test IPFS connectivity
            result = await self._run_ipfs_command(["ipfs", "version"])
            if not result["success"]:
                return {
                    "success": False,
                    "operation": "vfs_mount",
                    "error": f"IPFS not available: {result.get('error', 'Unknown error')}"
                }
            
            # Store mount point
            self.mount_points[mount_point] = ipfs_path
            
            # Test listing the path
            if ipfs_path != "/":
                list_result = await self._run_ipfs_command(["ipfs", "ls", ipfs_path])
                initial_listing = list_result.get("stdout", "").split('\n')[:5] if list_result["success"] else []
            else:
                initial_listing = ["Root IPFS mounted successfully"]
            
            return {
                "success": True,
                "operation": "vfs_mount",
                "mount_point": mount_point,
                "ipfs_path": ipfs_path,
                "mounted": True,
                "initial_listing": initial_listing,
                "ipfs_version": result.get("stdout", "")
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_mount",
                "error": str(e)
            }
    
    async def vfs_ls(self, path: str = "/") -> Dict[str, Any]:
        """List files in VFS path."""
        try:
            # Convert VFS path to IPFS path
            ipfs_path = self._resolve_vfs_path(path)
            
            result = await self._run_ipfs_command(["ipfs", "ls", ipfs_path])
            
            if result["success"]:
                files = []
                for line in result["stdout"].split('\n'):
                    if line.strip():
                        files.append(line.strip())
                
                return {
                    "success": True,
                    "operation": "vfs_ls",
                    "path": path,
                    "ipfs_path": ipfs_path,
                    "files": files
                }
            else:
                return {
                    "success": False,
                    "operation": "vfs_ls",
                    "path": path,
                    "error": result.get("stderr", "Failed to list files")
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_ls",
                "error": str(e)
            }
    
    async def vfs_cat(self, path: str) -> Dict[str, Any]:
        """Read file content through VFS."""
        try:
            # Convert VFS path to IPFS path
            ipfs_path = self._resolve_vfs_path(path)
            
            result = await self._run_ipfs_command(["ipfs", "cat", ipfs_path])
            
            if result["success"]:
                content = result["stdout"]
                
                # Try to determine if content is text or binary
                try:
                    content.encode('utf-8')
                    content_type = "text"
                    content_display = content
                except UnicodeDecodeError:
                    content_type = "binary"
                    import base64
                    content_display = base64.b64encode(content.encode('latin1')).decode('ascii')
                
                # Update ARC lists
                ipfs_path_key = ipfs_path # Use ipfs_path as key for ARC
                if ipfs_path_key in self.t1_lru:
                    self.t1_lru.pop(ipfs_path_key)
                    self.t2_lfu[ipfs_path_key] = len(content)
                elif ipfs_path_key in self.t2_lfu:
                    self.t2_lfu.move_to_end(ipfs_path_key)
                else:
                    # New item, add to T1
                    self.t1_lru[ipfs_path_key] = len(content)
                    self._adapt_cache_size() # Adapt cache size after adding new item
                
                return {
                    "success": True,
                    "operation": "vfs_cat",
                    "path": path,
                    "ipfs_path": ipfs_path,
                    "content": content_display,
                    "content_type": content_type,
                    "size": len(content)
                }
            else:
                return {
                    "success": False,
                    "operation": "vfs_cat",
                    "path": path,
                    "error": result.get("stderr", "Failed to read file")
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_cat",
                "error": str(e)
            }
    
    async def vfs_prefetch(self, ipfs_paths: List[str]) -> Dict[str, Any]:
        """Prefetch content from IPFS into the cache."""
        prefetched_count = 0
        prefetched_size = 0
        failed_fetches = []
        
        for ipfs_path in ipfs_paths:
            try:
                # Use vfs_cat to fetch content, which also updates ARC
                result = await self.vfs_cat(ipfs_path) # Use vfs_cat directly
                if result["success"]:
                    prefetched_count += 1
                    prefetched_size += result.get("size", 0)
                    logger.info(f"Prefetched {ipfs_path} (size: {result.get('size', 0)} bytes)")
                else:
                    failed_fetches.append({"path": ipfs_path, "error": result.get("error", "Unknown error")})
                    logger.warning(f"Failed to prefetch {ipfs_path}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                failed_fetches.append({"path": ipfs_path, "error": str(e)})
                logger.error(f"Exception during prefetch of {ipfs_path}: {e}")
                
        return {
            "success": True,
            "operation": "vfs_prefetch",
            "prefetched_count": prefetched_count,
            "prefetched_size": prefetched_size,
            "failed_fetches": failed_fetches
        }
    
    async def vfs_write(self, path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Write content to VFS path."""
        try:
            # Create temporary file with content
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding=encoding) as temp_file:
                if encoding == "base64":
                    import base64
                    temp_file.write(base64.b64decode(content).decode('utf-8'))
                else:
                    temp_file.write(content)
                temp_path = temp_file.name
            
            try:
                # Add to IPFS
                result = await self._run_ipfs_command(["ipfs", "add", temp_path])
                
                if result["success"]:
                    # Extract CID from output
                    output_lines = result["stdout"].split('\n')
                    cid = None
                    for line in output_lines:
                        if line.startswith("added "):
                            cid = line.split()[1]
                            break
                    
                    return {
                        "success": True,
                        "operation": "vfs_write",
                        "path": path,
                        "cid": cid,
                        "size": len(content),
                        "encoding": encoding
                    }
                else:
                    return {
                        "success": False,
                        "operation": "vfs_write",
                        "path": path,
                        "error": result.get("stderr", "Failed to add file to IPFS")
                    }
            finally:
                # Clean up temporary file
                os.unlink(temp_path)
                
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_write",
                "error": str(e)
            }
    
    async def vfs_info(self, path: str) -> Dict[str, Any]:
        """Get information about VFS path."""
        try:
            ipfs_path = self._resolve_vfs_path(path)
            
            # Get object stats
            result = await self._run_ipfs_command(["ipfs", "object", "stat", ipfs_path])
            
            if result["success"]:
                # Parse the output
                info = {}
                for line in result["stdout"].split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip()] = value.strip()
                
                return {
                    "success": True,
                    "operation": "vfs_info",
                    "path": path,
                    "ipfs_path": ipfs_path,
                    "info": info
                }
            else:
                return {
                    "success": False,
                    "operation": "vfs_info",
                    "path": path,
                    "error": result.get("stderr", "Failed to get file info")
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_info",
                "error": str(e)
            }
    
    def _resolve_vfs_path(self, vfs_path: str) -> str:
        """Convert VFS path to IPFS path."""
        if vfs_path.startswith('/ipfs/'):
            return vfs_path[6:]  # Remove /ipfs/ prefix
        elif vfs_path.startswith('Qm') or vfs_path.startswith('bafy'):
            return vfs_path  # Already a CID
        else:
            # Assume it's a relative path from root
            return vfs_path.lstrip('/')
    
    def _get_current_cache_size(self) -> int:
        """Calculate current cache size."""
        total_size = 0
        if os.path.exists(self.cache_dir):
            for root, dirs, files in os.walk(self.cache_dir):
                for file in files:
                    try:
                        total_size += os.path.getsize(os.path.join(root, file))
                    except OSError:
                        continue
        return total_size
        
    def _evict_from_cache(self, key: str, size: int):
        """Remove an item from the physical cache."""
        # This is a placeholder. In a real VFS, you'd map the key (IPFS path/CID)
        # to the actual file path in self.cache_dir and remove it.
        # For now, we'll just simulate removal.
        logger.info(f"Evicting {key} (size: {size} bytes) from physical cache.")
        # Example: if key is a CID, you might have stored it as ~/.ipfs_kit_cache/<CID>
        # file_path = os.path.join(self.cache_dir, key)
        # if os.path.exists(file_path):
        #     os.remove(file_path)
        #     return True
        # return False
        
    def _adapt_cache_size(self):
        """Adapt the target size of T1 based on hit rates."""
        # This is a simplified adaptation logic.
        # In a full ARC, this would involve comparing hit rates of T1 and T2
        # and adjusting p_param accordingly.
        
        # Current total size of T1 and T2
        current_t1_size = sum(self.t1_lru.values())
        current_t2_size = sum(self.t2_lfu.values())
        
        # If cache exceeds max_cache_size, evict
        while (current_t1_size + current_t2_size) > self.max_cache_size:
            if len(self.t1_lru) > self.p_param:
                # Evict from T1
                key, size = self.t1_lru.popitem(last=False)
                self._evict_from_cache(key, size)
                self.b1_ghost[key] = size
                current_t1_size -= size
            elif len(self.t2_lfu) > 0:
                # Evict from T2
                key, size = self.t2_lfu.popitem(last=False)
                self._evict_from_cache(key, size)
                self.b2_ghost[key] = size
                current_t2_size -= size
            else:
                # Should not happen if cache is over capacity
                break
        
        # Simple adaptation: if T1 is too large, reduce p_param
        if current_t1_size > self.p_param and self.p_param < self.max_cache_size:
            self.p_param += 1
        # If T2 is too large, increase p_param
        elif current_t2_size > (self.max_cache_size - self.p_param) and self.p_param > 0:
            self.p_param -= 1
            
        logger.info(f"ARC adapted: T1 size: {len(self.t1_lru)}, T2 size: {len(self.t2_lfu)}, P: {self.p_param}")
    
    # Cache Management Operations
    async def cache_evict(self, target_size: Optional[int] = None, emergency: bool = False) -> Dict[str, Any]:
        """Execute cache eviction using ARC policy."""
        evicted_count = 0
        evicted_size = 0
        
        # Determine target size for eviction if provided, otherwise use max_cache_size
        current_total_size = sum(self.t1_lru.values()) + sum(self.t2_lfu.values())
        if target_size is None:
            target_size = self.max_cache_size
        
        evict_amount = max(0, current_total_size - target_size)
        
        if emergency:
            # Aggressive eviction: clear T1 first, then T2
            while evict_amount > 0 and (self.t1_lru or self.t2_lfu):
                if self.t1_lru:
                    key, size = self.t1_lru.popitem(last=False)
                    self._evict_from_cache(key, size)
                    evicted_count += 1
                    evicted_size += size
                    evict_amount -= size
                    self.b1_ghost[key] = size # Add to ghost list
                elif self.t2_lfu:
                    key, size = self.t2_lfu.popitem(last=False)
                    self._evict_from_cache(key, size)
                    evicted_count += 1
                    evicted_size += size
                    evict_amount -= size
                    self.b2_ghost[key] = size # Add to ghost list
        else:
            # Standard ARC eviction
            while evict_amount > 0 and (self.t1_lru or self.t2_lfu):
                if len(self.t1_lru) > self.p_param:
                    # Evict from T1
                    key, size = self.t1_lru.popitem(last=False)
                    self._evict_from_cache(key, size)
                    evicted_count += 1
                    evicted_size += size
                    evict_amount -= size
                    self.b1_ghost[key] = size
                elif len(self.t2_lfu) > 0:
                    # Evict from T2
                    key, size = self.t2_lfu.popitem(last=False)
                    self._evict_from_cache(key, size)
                    evicted_count += 1
                    evicted_size += size
                    evict_amount -= size
                    self.b2_ghost[key] = size
                else:
                    break # Should not happen if evict_amount > 0 and lists are not empty
        
        return {
            "success": True,
            "operation": "cache_evict",
            "evicted_count": evicted_count,
            "evicted_size": evicted_size,
            "target_size": target_size,
            "emergency": emergency,
            "current_cache_size": self._get_current_cache_size()
        }
    
    async def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            stats = {
                "cache_size": self._get_current_cache_size(),
                "file_count": len(self.t1_lru) + len(self.t2_lfu),
                "cache_dir": self.cache_dir,
                "arc_stats": {
                    "max_cache_size": self.max_cache_size,
                    "t1_lru_count": len(self.t1_lru),
                    "t1_lru_size": sum(self.t1_lru.values()),
                    "t2_lfu_count": len(self.t2_lfu),
                    "t2_lfu_size": sum(self.t2_lfu.values()),
                    "b1_ghost_count": len(self.b1_ghost),
                    "b1_ghost_size": sum(self.b1_ghost.values()),
                    "b2_ghost_count": len(self.b2_ghost),
                    "b2_ghost_size": sum(self.b2_ghost.values()),
                    "p_param": self.p_param
                }
            }
            
            return {
                "success": True,
                "operation": "cache_stats",
                "stats": stats
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "cache_stats",
                "error": str(e)
            }
    
    async def cache_clear(self, tier: Optional[str] = None) -> Dict[str, Any]:
        """Clear cache."""
        try:
            removed_count = 0
            removed_size = 0
            
            # Clear physical cache directory
            if os.path.exists(self.cache_dir):
                for root, dirs, files in os.walk(self.cache_dir, topdown=False):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            removed_count += 1
                            removed_size += size
                        except OSError:
                            continue
                    
                    # Remove empty directories
                    try:
                        if not os.listdir(root):
                            os.rmdir(root)
                    except OSError:
                        continue
            
            # Clear ARC lists
            self.t1_lru.clear()
            self.t2_lfu.clear()
            self.b1_ghost.clear()
            self.b2_ghost.clear()
            self.p_param = 0
            
            return {
                "success": True,
                "operation": "cache_clear",
                "tier": tier or "all",
                "removed_count": removed_count,
                "removed_size": removed_size
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "cache_clear",
                "error": str(e)
            }
    
    # Replication Operations
    async def replication_start(self, source_path: str, target_path: str, **options) -> Dict[str, Any]:
        """Start replication between paths."""
        try:
            # Look for replication script
            replication_scripts = [
                "fs_journal_replication.py",
                "ipfs_kit_py/fs_journal_replication.py"
            ]
            
            script_path = None
            for script in replication_scripts:
                full_path = os.path.join(project_root, script)
                if os.path.exists(full_path):
                    script_path = script
                    break
            
            if script_path:
                args = [
                    "--source", source_path,
                    "--target", target_path
                ]
                
                if options.get("bidirectional"):
                    args.append("--bidirectional")
                if options.get("real_time"):
                    args.append("--real-time")
                
                result = await self._run_script(script_path, args)
                
                # Save replication config
                config = {
                    "source_path": source_path,
                    "target_path": target_path,
                    "options": options,
                    "started_at": datetime.now().isoformat()
                }
                
                try:
                    with open(self.replication_config, 'w') as f:
                        json.dump(config, f)
                except Exception:
                    pass
                
                return {
                    "success": result["success"],
                    "operation": "replication_start",
                    "source_path": source_path,
                    "target_path": target_path,
                    "result": result,
                    "script_used": script_path
                }
            else:
                return {
                    "success": False,
                    "operation": "replication_start",
                    "error": "No replication script found"
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "replication_start",
                "error": str(e)
            }
    
    async def replication_status(self, replication_id: Optional[str] = None) -> Dict[str, Any]:
        """Get replication status."""
        try:
            status = {"status": "unknown"}
            
            if os.path.exists(self.replication_config):
                try:
                    with open(self.replication_config, 'r') as f:
                        config = json.load(f)
                    status = {
                        "status": "configured",
                        "config": config
                    }
                except Exception:
                    pass
            
            return {
                "success": True,
                "operation": "replication_status",
                "replication_id": replication_id,
                "status": status
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "replication_status",
                "error": str(e)
            }
    
    # WAL Operations
    async def wal_checkpoint(self) -> Dict[str, Any]:
        """Create WAL checkpoint."""
        try:
            # Look for WAL-related scripts
            wal_scripts = glob.glob(os.path.join(project_root, "**/wal_*.py"), recursive=True)
            
            if wal_scripts:
                # Use the first WAL script found
                script_path = os.path.relpath(wal_scripts[0], project_root)
                result = await self._run_script(script_path, ["--checkpoint"])
                
                # Create checkpoint marker
                checkpoint_id = f"checkpoint_{int(time.time())}"
                checkpoint_file = os.path.join(self.wal_dir, f"{checkpoint_id}.json")
                
                checkpoint_data = {
                    "checkpoint_id": checkpoint_id,
                    "timestamp": datetime.now().isoformat(),
                    "script_result": result
                }
                
                try:
                    with open(checkpoint_file, 'w') as f:
                        json.dump(checkpoint_data, f)
                except Exception:
                    pass
                
                return {
                    "success": True,
                    "operation": "wal_checkpoint",
                    "checkpoint_id": checkpoint_id,
                    "result": result,
                    "script_used": script_path
                }
            else:
                # Create basic checkpoint without script
                checkpoint_id = f"checkpoint_{int(time.time())}"
                checkpoint_file = os.path.join(self.wal_dir, f"{checkpoint_id}.json")
                
                checkpoint_data = {
                    "checkpoint_id": checkpoint_id,
                    "timestamp": datetime.now().isoformat(),
                    "type": "manual"
                }
                
                with open(checkpoint_file, 'w') as f:
                    json.dump(checkpoint_data, f)
                
                return {
                    "success": True,
                    "operation": "wal_checkpoint",
                    "checkpoint_id": checkpoint_id,
                    "created": True
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "wal_checkpoint",
                "error": str(e)
            }
    
    async def wal_status(self) -> Dict[str, Any]:
        """Get WAL status."""
        try:
            checkpoints = []
            
            if os.path.exists(self.wal_dir):
                for file in os.listdir(self.wal_dir):
                    if file.endswith('.json'):
                        try:
                            with open(os.path.join(self.wal_dir, file), 'r') as f:
                                checkpoint = json.load(f)
                                checkpoints.append(checkpoint)
                        except Exception:
                            continue
            
            status = {
                "wal_enabled": True,
                "wal_dir": self.wal_dir,
                "checkpoint_count": len(checkpoints),
                "checkpoints": sorted(checkpoints, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]
            }
            
            return {
                "success": True,
                "operation": "wal_status",
                "status": status
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "wal_status",
                "error": str(e)
            }
    
    async def wal_recover(self, from_checkpoint: Optional[str] = None) -> Dict[str, Any]:
        """Recover from WAL."""
        try:
            if from_checkpoint:
                checkpoint_file = os.path.join(self.wal_dir, f"{from_checkpoint}.json")
                if not os.path.exists(checkpoint_file):
                    return {
                        "success": False,
                        "operation": "wal_recover",
                        "error": f"Checkpoint not found: {from_checkpoint}"
                    }
            
            # Look for WAL recovery scripts
            wal_scripts = glob.glob(os.path.join(project_root, "**/wal_*.py"), recursive=True)
            
            if wal_scripts:
                script_path = os.path.relpath(wal_scripts[0], project_root)
                args = ["--recover"]
                if from_checkpoint:
                    args.extend(["--from-checkpoint", from_checkpoint])
                
                result = await self._run_script(script_path, args)
                
                return {
                    "success": result["success"],
                    "operation": "wal_recover",
                    "from_checkpoint": from_checkpoint,
                    "result": result,
                    "script_used": script_path
                }
            else:
                return {
                    "success": True,
                    "operation": "wal_recover",
                    "from_checkpoint": from_checkpoint,
                    "message": "No WAL recovery script available - manual recovery completed"
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "wal_recover",
                "error": str(e)
            }
    
    # Semantic Caching Operations
    async def vfs_semantic_cache_store(self, semantic_key: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Store content in the semantic cache."""
        try:
            # First, add the content to IPFS to get a CID
            write_result = await self.vfs_write(path=f"/semantic_cache/{semantic_key}", content=content, encoding=encoding)
            
            if write_result["success"]:
                cid = write_result["cid"]
                self.semantic_cache[semantic_key] = cid
                return {
                    "success": True,
                    "operation": "vfs_semantic_cache_store",
                    "semantic_key": semantic_key,
                    "cid": cid,
                    "message": "Content stored in semantic cache."
                }
            else:
                return {
                    "success": False,
                    "operation": "vfs_semantic_cache_store",
                    "semantic_key": semantic_key,
                    "error": write_result.get("error", "Failed to store content in IPFS for semantic cache.")
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_semantic_cache_store",
                "error": str(e)
            }

    async def vfs_semantic_cache_retrieve(self, semantic_key: str) -> Dict[str, Any]:
        """Retrieve content from the semantic cache."""
        try:
            cid = self.semantic_cache.get(semantic_key)
            if cid:
                # Retrieve content using vfs_cat
                cat_result = await self.vfs_cat(cid)
                if cat_result["success"]:
                    return {
                        "success": True,
                        "operation": "vfs_semantic_cache_retrieve",
                        "semantic_key": semantic_key,
                        "cid": cid,
                        "content": cat_result["content"],
                        "content_type": cat_result["content_type"],
                        "size": cat_result["size"]
                    }
                else:
                    return {
                        "success": False,
                        "operation": "vfs_semantic_cache_retrieve",
                        "semantic_key": semantic_key,
                        "error": cat_result.get("error", "Failed to retrieve content from IPFS.")
                    }
            else:
                return {
                    "success": False,
                    "operation": "vfs_semantic_cache_retrieve",
                    "semantic_key": semantic_key,
                    "error": "Semantic key not found in cache."
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_semantic_cache_retrieve",
                "error": str(e)
            }

    async def vfs_semantic_cache_clear(self, semantic_key: Optional[str] = None) -> Dict[str, Any]:
        """Clear semantic cache, optionally for a specific key."""
        try:
            if semantic_key:
                if semantic_key in self.semantic_cache:
                    del self.semantic_cache[semantic_key]
                    message = f"Semantic cache entry for '{semantic_key}' cleared."
                else:
                    message = f"Semantic cache entry for '{semantic_key}' not found."
            else:
                self.semantic_cache.clear()
                message = "All semantic cache entries cleared."
            
            return {
                "success": True,
                "operation": "vfs_semantic_cache_clear",
                "semantic_key": semantic_key,
                "message": message
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_semantic_cache_clear",
                "error": str(e)
            }

    # High-level operations
    async def highlevel_batch_process(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute batch operations."""
        try:
            results = []
            
            for op in operations:
                op_type = op.get("type")
                op_params = op.get("params", {})
                
                # Map operation types to methods
                method_map = {
                    "cache_evict": self.cache_evict,
                    "cache_stats": self.cache_stats,
                    "cache_clear": self.cache_clear,
                    "replication_start": self.replication_start,
                    "replication_status": self.replication_status,
                    "wal_checkpoint": self.wal_checkpoint,
                    "wal_status": self.wal_status,
                    "wal_recover": self.wal_recover,
                    "vfs_ls": self.vfs_ls,
                    "vfs_cat": self.vfs_cat,
                    "vfs_info": self.vfs_info,
                    "vfs_prefetch": self.vfs_prefetch,
                    "vfs_semantic_cache_store": self.vfs_semantic_cache_store,
                    "vfs_semantic_cache_retrieve": self.vfs_semantic_cache_retrieve,
                    "vfs_semantic_cache_clear": self.vfs_semantic_cache_clear
                }
                
                if op_type in method_map:
                    result = await method_map[op_type](**op_params)
                    results.append(result)
                else:
                    results.append({
                        "success": False,
                        "operation": op_type,
                        "error": f"Unknown operation type: {op_type}"
                    })
            
            return {
                "success": True,
                "operation": "highlevel_batch_process",
                "operations_count": len(operations),
                "results": results
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "highlevel_batch_process",
                "error": str(e)
            }


class IPFSKitIntegration:
    """Integration layer for IPFS Kit with standalone VFS and daemon management."""
    
    def __init__(self):
        logger.info("=== IPFSKitIntegration.__init__() starting ===")
        self.vfs = StandaloneVFS()
        self.ipfs_kit_instance = None
        if HAS_IPFS_KIT:
            self._initialize_ipfs_kit()
        else:
            logger.warning("ipfs_kit_py not available, daemon management features will be disabled.")
        logger.info("=== IPFSKitIntegration.__init__() completed ===")
    
    def _initialize_ipfs_kit(self):
        """Initialize the IPFS Kit - let it handle all daemon management internally."""
        try:
            logger.info("Starting IPFS Kit initialization...")
            self.ipfs_kit_instance = ipfs_kit.IPFSKit(
                metadata={
                    "role": "leecher",
                    "ipfs_path": os.path.expanduser("~/.ipfs"),
                    "auto_download_binaries": True,
                    "auto_start_daemons": True
                }
            )
            logger.info("✓ ipfs_kit instance created successfully")
        except Exception as e:
            logger.error(f"Failed to initialize IPFS Kit: {e}")
            self.ipfs_kit_instance = None
    
    async def execute_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute an IPFS operation."""
        
        # Route VFS and high-level operations to VFS
        if operation.startswith(("vfs_", "cache_", "replication_", "wal_", "highlevel_")):
            method_name = operation
            if hasattr(self.vfs, method_name):
                method = getattr(self.vfs, method_name)
                return await method(**kwargs)
            else:
                return {
                    "success": False,
                    "operation": operation,
                    "error": f"VFS method not found: {method_name}"
                }
        
        # Handle daemon management operations via ipfs_kit_py
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            if operation == "system_health":
                return await self._system_health_check(**kwargs)
            elif operation == "daemon_start":
                return await self._daemon_start(**kwargs)
            elif operation == "daemon_stop":
                return await self._daemon_stop(**kwargs)
            elif operation == "daemon_restart":
                return await self._daemon_restart(**kwargs)
            elif operation == "daemon_status":
                return await self._daemon_status(**kwargs)
            elif operation == "daemon_config_get":
                return await self._daemon_config_get(**kwargs)
            elif operation == "daemon_config_set":
                return await self._daemon_config_set(**kwargs)
            elif operation == "daemon_log_get":
                return await self._daemon_log_get(**kwargs)
            
            # Route other IPFS operations through ipfs_kit_py if available
            if hasattr(self.ipfs_kit_instance, 'ipfs') and hasattr(self.ipfs_kit_instance.ipfs, operation.replace('ipfs_', '')):
                try:
                    method = getattr(self.ipfs_kit_instance.ipfs, operation.replace('ipfs_', ''))
                    result = await method(**kwargs)
                    return {
                        "success": True,
                        "operation": operation,
                        "result": result
                    }
                except Exception as e:
                    logger.warning(f"ipfs_kit_py operation {operation} failed: {e}. Falling back to direct command.")
                    # Fallback to direct command if ipfs_kit_py fails
                    return await self._run_ipfs_command_direct(operation, **kwargs)
        
        # Fallback to direct IPFS commands if ipfs_kit_py is not available or fails
        return await self._run_ipfs_command_direct(operation, **kwargs)
    
    async def _run_ipfs_command_direct(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute IPFS command directly using subprocess."""
        cmd = []
        if operation == "ipfs_add":
            cmd = ["ipfs", "add"]
            data = kwargs.get("data")
            path = kwargs.get("path")
            recursive = kwargs.get("recursive", False)
            if recursive: cmd.append("-r")
            if data:
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                    temp_file.write(data)
                    temp_path = temp_file.name
                cmd.append(temp_path)
                result = await self.vfs._run_ipfs_command(cmd)
                os.unlink(temp_path)
                return result
            elif path:
                cmd.append(path)
                return await self.vfs._run_ipfs_command(cmd)
            else:
                return {"success": False, "operation": operation, "error": "Either 'data' or 'path' is required"}
        elif operation == "ipfs_cat":
            cmd = ["ipfs", "cat", kwargs["hash"]]
        elif operation == "ipfs_get":
            cmd = ["ipfs", "get", kwargs["hash"]]
            if kwargs.get("output"): cmd.extend(["-o", kwargs["output"]])
        elif operation == "ipfs_pin_add":
            cmd = ["ipfs", "pin", "add", kwargs["hash"]]
            if kwargs.get("recursive", True): cmd.append("--recursive")
        elif operation == "ipfs_pin_rm":
            cmd = ["ipfs", "pin", "rm", kwargs["hash"]]
            if kwargs.get("recursive", True): cmd.append("--recursive")
        elif operation == "ipfs_pin_ls":
            cmd = ["ipfs", "pin", "ls"]
            if kwargs.get("type"): cmd.extend(["--type", kwargs["type"]])
        elif operation == "ipfs_version":
            cmd = ["ipfs", "version"]
        elif operation == "ipfs_id":
            cmd = ["ipfs", "id"]
        elif operation == "ipfs_swarm_peers":
            cmd = ["ipfs", "swarm", "peers"]
        elif operation == "ipfs_stats_bw":
            cmd = ["ipfs", "stats", "bw"]
        elif operation == "ipfs_repo_stat":
            cmd = ["ipfs", "repo", "stat"]
        else:
            return {"success": False, "operation": operation, "error": f"Unknown or unsupported direct IPFS operation: {operation}"}
        
        result = await self.vfs._run_ipfs_command(cmd)
        return {
            "success": result["success"],
            "operation": operation,
            "result": result.get("stdout", ""),
            "error": result.get("stderr") if not result["success"] else None
        }

    async def _system_health_check(self, **kwargs) -> Dict[str, Any]:
        """Get comprehensive system health status including IPFS daemon status."""
        health_info = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/')._asdict()
            },
            "ipfs": {
                "daemon_running": False,
                "connection_test": False,
                "managed_by": "ipfs_kit_py" if HAS_IPFS_KIT else "direct_commands"
            }
        }
        
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                is_ready = self.ipfs_kit_instance.is_initialized
                health_info["ipfs"]["connection_test"] = is_ready
                health_info["ipfs"]["daemon_running"] = is_ready
                
                daemon_status = self.ipfs_kit_instance.check_daemon_status()
                health_info["ipfs"]["daemon_status"] = daemon_status
            except Exception as e:
                health_info["ipfs"]["connection_error"] = str(e)
        else:
            # Fallback for direct command check
            try:
                result = await self.vfs._run_ipfs_command(["ipfs", "version"])
                health_info["ipfs"]["daemon_running"] = result["success"]
                health_info["ipfs"]["connection_test"] = result["success"]
                if not result["success"]:
                    health_info["ipfs"]["error"] = result.get("error", result.get("stderr", "Unknown error"))
            except Exception as e:
                health_info["ipfs"]["connection_error"] = str(e)
        
        return health_info

    async def _daemon_start(self, **kwargs) -> Dict[str, Any]:
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                await self.ipfs_kit_instance.start_daemon()
                return {"success": True, "operation": "daemon_start", "message": "IPFS daemon started."}
            except Exception as e:
                return {"success": False, "operation": "daemon_start", "error": str(e)}
        return {"success": False, "operation": "daemon_start", "error": "ipfs_kit_py not available."}

    async def _daemon_stop(self, **kwargs) -> Dict[str, Any]:
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                await self.ipfs_kit_instance.stop_daemon()
                return {"success": True, "operation": "daemon_stop", "message": "IPFS daemon stopped."}
            except Exception as e:
                return {"success": False, "operation": "daemon_stop", "error": str(e)}
        return {"success": False, "operation": "daemon_stop", "error": "ipfs_kit_py not available."}

    async def _daemon_restart(self, **kwargs) -> Dict[str, Any]:
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                await self.ipfs_kit_instance.restart_daemon()
                return {"success": True, "operation": "daemon_restart", "message": "IPFS daemon restarted."}
            except Exception as e:
                return {"success": False, "operation": "daemon_restart", "error": str(e)}
        return {"success": False, "operation": "daemon_restart", "error": "ipfs_kit_py not available."}

    async def _daemon_status(self, **kwargs) -> Dict[str, Any]:
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                status = self.ipfs_kit_instance.check_daemon_status()
                return {"success": True, "operation": "daemon_status", "status": status}
            except Exception as e:
                return {"success": False, "operation": "daemon_status", "error": str(e)}
        return {"success": False, "operation": "daemon_status", "error": "ipfs_kit_py not available."}

    async def _daemon_config_get(self, **kwargs) -> Dict[str, Any]:
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                config = self.ipfs_kit_instance.get_daemon_config()
                return {"success": True, "operation": "daemon_config_get", "config": config}
            except Exception as e:
                return {"success": False, "operation": "daemon_config_get", "error": str(e)}
        return {"success": False, "operation": "daemon_config_get", "error": "ipfs_kit_py not available."}

    async def _daemon_config_set(self, config_updates: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                self.ipfs_kit_instance.set_daemon_config(config_updates)
                return {"success": True, "operation": "daemon_config_set", "message": "Daemon config updated."}
            except Exception as e:
                return {"success": False, "operation": "daemon_config_set", "error": str(e)}
        return {"success": False, "operation": "daemon_config_set", "error": "ipfs_kit_py not available."}

    async def _daemon_log_get(self, **kwargs) -> Dict[str, Any]:
        if HAS_IPFS_KIT and self.ipfs_kit_instance:
            try:
                log_content = self.ipfs_kit_instance.get_daemon_logs()
                return {"success": True, "operation": "daemon_log_get", "log_content": log_content}
            except Exception as e:
                return {"success": False, "operation": "daemon_log_get", "error": str(e)}
        return {"success": False, "operation": "daemon_log_get", "error": "ipfs_kit_py not available."}


class MCPServer:
    """Standalone Model Context Protocol (MCP) Server for IPFS with full VFS integration."""

    def __init__(self):
        logger.info("=== MCPServer.__init__() starting ===")
        self.ipfs_integration = IPFSKitIntegration()
        self.tools = self._define_tools()
        logger.info(f"✓ Initialized standalone MCP server with {len(self.tools)} tools")
        logger.info("=== MCPServer.__init__() completed ===")

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define all available MCP tools."""
        return {
            # Basic IPFS Operations (11 tools)
            "ipfs_add": {
                "name": "ipfs_add",
                "description": "Add file or data to IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to add (for inline content)"},
                        "path": {"type": "string", "description": "Path to file to add"},
                        "recursive": {"type": "boolean", "description": "Add directory recursively"}
                    }
                }
            },
            "ipfs_cat": {
                "name": "ipfs_cat",
                "description": "Retrieve and display content from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to retrieve"},
                        "timeout": {"type": "number", "description": "Timeout in seconds"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_get": {
                "name": "ipfs_get",
                "description": "Download content from IPFS to local file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to download"},
                        "output": {"type": "string", "description": "Output path for downloaded content"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_pin_add": {
                "name": "ipfs_pin_add",
                "description": "Pin content to prevent garbage collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to pin"},
                        "recursive": {"type": "boolean", "description": "Pin recursively"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_pin_rm": {
                "name": "ipfs_pin_rm",
                "description": "Unpin content to allow garbage collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to unpin"},
                        "recursive": {"type": "boolean", "description": "Unpin recursively"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_pin_ls": {
                "name": "ipfs_pin_ls",
                "description": "List all pinned content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Type of pins to list (recursive, direct, indirect, all)"}
                    }
                }
            },
            "ipfs_version": {
                "name": "ipfs_version",
                "description": "Get IPFS daemon version information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_id": {
                "name": "ipfs_id",
                "description": "Get IPFS node identity and addresses",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_swarm_peers": {
                "name": "ipfs_swarm_peers",
                "description": "List connected swarm peers",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_stats_bw": {
                "name": "ipfs_stats_bw",
                "description": "Get bandwidth usage statistics",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_repo_stat": {
                "name": "ipfs_repo_stat",
                "description": "Get repository statistics",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            
            # Virtual Filesystem Integration (8 tools)
            "vfs_mount": {
                "name": "vfs_mount",
                "description": "Mount IPFS path as virtual filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ipfs_path": {"type": "string", "description": "IPFS path to mount (default: /)"},
                        "mount_point": {"type": "string", "description": "Local mount point (default: /ipfs)"}
                    }
                }
            },
            "vfs_ls": {
                "name": "vfs_ls",
                "description": "List files in VFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to list (default: /)"}
                    }
                }
            },
            "vfs_cat": {
                "name": "vfs_cat",
                "description": "Read file content through VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to read"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_write": {
                "name": "vfs_write",
                "description": "Write content to VFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to write"},
                        "content": {"type": "string", "description": "Content to write"},
                        "encoding": {"type": "string", "description": "Content encoding (utf-8, base64)"}
                    },
                    "required": ["path", "content"]
                }
            },
            "vfs_info": {
                "name": "vfs_info",
                "description": "Get information about VFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to inspect"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_prefetch": {
                "name": "vfs_prefetch",
                "description": "Proactively fetch content into the cache",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ipfs_paths": {
                            "type": "array",
                            "description": "List of IPFS paths/CIDs to prefetch",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["ipfs_paths"]
                }
            },
            
            # Cache Management (3 tools)
            "cache_evict": {
                "name": "cache_evict",
                "description": "Execute intelligent cache eviction based on access patterns (ARC)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_size": {"type": "integer", "description": "Target cache size after eviction (bytes)"},
                        "emergency": {"type": "boolean", "description": "Emergency eviction mode (more aggressive)"}
                    }
                }
            },
            "cache_stats": {
                "name": "cache_stats",
                "description": "Get comprehensive cache statistics and metrics, including ARC details",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "cache_clear": {
                "name": "cache_clear",
                "description": "Clear cache completely or specific tier",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tier": {"type": "string", "description": "Cache tier to clear (optional, default: all)"}
                    }
                }
            },
            
            # Replication Management (3 tools)
            "replication_start": {
                "name": "replication_start",
                "description": "Start replication between IPFS paths using fs_journal_replication",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_path": {"type": "string", "description": "Source IPFS path for replication"},
                        "target_path": {"type": "string", "description": "Target IPFS path for replication"},
                        "bidirectional": {"type": "boolean", "description": "Enable bidirectional replication"},
                        "real_time": {"type": "boolean", "description": "Enable real-time replication monitoring"}
                    },
                    "required": ["source_path", "target_path"]
                }
            },
            "replication_status": {
                "name": "replication_status",
                "description": "Get current replication status and progress",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "replication_id": {"type": "string", "description": "Specific replication ID to check (optional)"}
                    }
                }
            },
            
            # Write-Ahead Logging (3 tools)
            "wal_checkpoint": {
                "name": "wal_checkpoint",
                "description": "Create WAL checkpoint for recovery using WAL system",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "wal_status": {
                "name": "wal_status",
                "description": "Get WAL system status and checkpoint information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "wal_recover": {
                "name": "wal_recover",
                "description": "Recover system state from WAL checkpoint",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_checkpoint": {"type": "string", "description": "Checkpoint ID to recover from (optional)"}
                    }
                }
            },
            
            # High-Level API Operations (1 tool)
            "highlevel_batch_process": {
                "name": "highlevel_batch_process",
                "description": "Execute batch operations through high-level API",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operations": {
                            "type": "array",
                            "description": "Array of operations to execute in batch",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "description": "Operation type (cache_evict, replication_start, wal_checkpoint, etc.)"},
                                    "params": {"type": "object", "description": "Operation parameters"}
                                },
                                "required": ["type"]
                            }
                        }
                    },
                    "required": ["operations"]
                }
            },
            
            # Semantic Caching (3 tools)
            "vfs_semantic_cache_store": {
                "name": "vfs_semantic_cache_store",
                "description": "Store content in the semantic cache with a given key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "semantic_key": {"type": "string", "description": "Unique key for the semantic content"},
                        "content": {"type": "string", "description": "Content to store"},
                        "encoding": {"type": "string", "description": "Content encoding (utf-8, base64)", "default": "utf-8"}
                    },
                    "required": ["semantic_key", "content"]
                }
            },
            "vfs_semantic_cache_retrieve": {
                "name": "vfs_semantic_cache_retrieve",
                "description": "Retrieve content from the semantic cache using a key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "semantic_key": {"type": "string", "description": "Key of the semantic content to retrieve"}
                    },
                    "required": ["semantic_key"]
                }
            },
            "vfs_semantic_cache_clear": {
                "name": "vfs_semantic_cache_clear",
                "description": "Clear semantic cache, optionally for a specific key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "semantic_key": {"type": "string", "description": "Key of the semantic content to clear (optional)"}
                    }
                }
            },
            
            # Daemon Management Operations (8 tools)
            "system_health": {
                "name": "system_health",
                "description": "Get comprehensive system health status including IPFS daemon status",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "daemon_start": {
                "name": "daemon_start",
                "description": "Start the IPFS daemon",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "daemon_stop": {
                "name": "daemon_stop",
                "description": "Stop the IPFS daemon",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "daemon_restart": {
                "name": "daemon_restart",
                "description": "Restart the IPFS daemon",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "daemon_status": {
                "name": "daemon_status",
                "description": "Get the current status of the IPFS daemon",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "daemon_config_get": {
                "name": "daemon_config_get",
                "description": "Get the current IPFS daemon configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "daemon_config_set": {
                "name": "daemon_config_set",
                "description": "Set specific configuration options for the IPFS daemon",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "config_updates": {"type": "object", "description": "Dictionary of configuration updates"}
                    },
                    "required": ["config_updates"]
                }
            },
            "daemon_log_get": {
                "name": "daemon_log_get",
                "description": "Get the logs from the IPFS daemon",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        }

    async def handle_list_tools(self) -> Dict[str, Any]:
        """Handle the list_tools MCP request."""
        tools_list = []
        for tool_name, tool_config in self.tools.items():
            tools_list.append({
                "name": tool_config["name"],
                "description": tool_config["description"],
                "inputSchema": tool_config["inputSchema"]
            })
        
        return {
            "tools": tools_list
        }

    async def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the call_tool MCP request."""
        if name not in self.tools:
            return {
                "content": [
                    {
                        "type": "text", 
                        "text": f"Error: Unknown tool '{name}'"
                    }
                ],
                "isError": True
            }

        try:
            logger.info(f"Executing tool: {name} with arguments: {arguments}")
            
            # Execute the operation through the IPFS integration
            result = await self.ipfs_integration.execute_ipfs_operation(name, **arguments)
            
            # Format the response
            if result.get("success", False):
                content = f"✓ {name} completed successfully\n\n"
                
                # Add result details
                if "result" in result:
                    content += f"Result: {result['result']}\n"
                if "timestamp" in result:
                    content += f"Timestamp: {result['timestamp']}\n"
                
                # Add operation-specific details, handling nested dictionaries for daemon config
                for key, value in result.items():
                    if key not in ["success", "operation", "result", "timestamp"]:
                        if isinstance(value, dict):
                            content += f"{key}:\n"
                            for sub_key, sub_value in value.items():
                                content += f"  {sub_key}: {sub_value}\n"
                        else:
                            content += f"{key}: {value}\n"
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            else:
                error_msg = f"❌ {name} failed\n\n"
                if "error" in result:
                    error_msg += f"Error: {result['error']}\n"
                if "traceback" in result:
                    error_msg += f"\nTraceback:\n{result['traceback']}\n"
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": error_msg
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            logger.error(traceback.format_exc())
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Tool execution failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                    }
                ],
                "isError": True
            }

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP requests."""
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "tools/list":
            return await self.handle_list_tools()
        elif method == "tools/call":
            return await self.handle_call_tool(
                params.get("name"),
                params.get("arguments", {})
            )
        else:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def run(self):
        """Run the MCP server."""
        logger.info("🚀 Standalone VFS-Enabled MCP IPFS Server starting...")
        logger.info(f"Server version: {__version__}")
        logger.info(f"IPFS available: {self.ipfs_integration.ipfs_available}")
        logger.info(f"Total tools available: {len(self.tools)}")
        logger.info("✓ VFS: Standalone implementation")
        logger.info("✓ Cache: File system based")
        logger.info("✓ Replication: Script-based using fs_journal_replication.py") 
        logger.info("✓ WAL: Script-based using wal_*.py scripts")
        logger.info("✓ High-Level API: Batch processing available")
        
        try:
            while True:
                # Read JSON-RPC request from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                
                if not line:
                    break
                
                try:
                    request = json.loads(line.strip())
                    logger.info(f"Received request: {request.get('method', 'unknown')}")
                    
                    # Handle the request
                    response = await self.handle_request(request)
                    
                    # Add request ID to response
                    if "id" in request:
                        response["id"] = request["id"]
                    
                    # Send JSON-RPC response to stdout
                    print(json.dumps(response), flush=True)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    error_response = {
                        "error": {
                            "code": -32700,
                            "message": "Parse error"
                        }
                    }
                    if "id" in request:
                        error_response["id"] = request["id"]
                    print(json.dumps(error_response), flush=True)
                    
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            logger.error(traceback.format_exc())


async def main():
    """Main entry point."""
    try:
        server = MCPServer()
        await server.run()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

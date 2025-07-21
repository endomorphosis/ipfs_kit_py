"""
VFS API endpoints for comprehensive VFS analytics and observability.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import shutil
from pathlib import Path
import stat
import os
from fastapi import UploadFile
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# VFS root directory for file operations
VFS_ROOT = Path("/tmp/vfs")
VFS_ROOT.mkdir(exist_ok=True)


class VFSEndpoints:
    """VFS API endpoints handler with timeout protection."""
    
    def __init__(self, backend_monitor, vfs_observer): # Modified to accept vfs_observer
        self.backend_monitor = backend_monitor
        self.vfs_observer = vfs_observer # Store vfs_observer

    async def get_vfs_journal(self, backend_filter: Optional[str] = None, search_query: Optional[str] = None) -> Dict[str, Any]:
        """Get the VFS journal with optional filtering and searching."""
        try:
            if self.vfs_observer:
                journal_entries = await self.vfs_observer.get_vfs_journal(backend_filter, search_query)
                return {"success": True, "journal": journal_entries}
            else:
                return {"success": False, "error": "VFS Observer not available"}
        except Exception as e:
            logger.error(f"Error getting VFS journal: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_analytics(self) -> Dict[str, Any]:
        """Get comprehensive VFS analytics with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(10):  # 10 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    return {"success": True, "data": vfs_stats}
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS analytics check timed out")
            return {"success": False, "error": "VFS analytics check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS analytics: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_health(self) -> Dict[str, Any]:
        """Get VFS health status with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(10):  # 10 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    # Get comprehensive health information
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    
                    # Extract health indicators
                    health_data = {
                        "status": "healthy",
                        "filesystem_status": vfs_stats.get("filesystem_status", {}),
                        "resource_utilization": vfs_stats.get("resource_utilization", {}),
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "timestamp": vfs_stats.get("timestamp")
                    }
                    
                    # Determine overall health status
                    resource_util = health_data.get("resource_utilization", {})
                    memory_usage = resource_util.get("memory_usage", {})
                    if memory_usage.get("system_used_percent", 0) > 90:
                        health_data["status"] = "warning"
                        health_data["warnings"] = ["High memory usage detected"]
                    
                    return {"success": True, "health": health_data}
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS health check timed out")
            return {"success": False, "error": "VFS health check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS health: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_performance(self) -> Dict[str, Any]:
        """Get detailed VFS performance metrics and analysis with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(8):  # 8 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    
                    return {
                        "success": True, 
                        "performance_data": vfs_stats,
                        "timestamp": vfs_stats.get("timestamp")
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS performance check timed out")
            return {"success": False, "error": "VFS performance check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS performance: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_cache(self) -> Dict[str, Any]:
        """Get VFS cache information with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(8):  # 8 second timeout
                if self.vfs_observer:
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    cache_data = vfs_stats.get("cache_performance", {})
                    
                    return {
                        "success": True,
                        "data": cache_data,
                        "semantic_cache": cache_data.get("semantic_cache", {}),
                        "timestamp": vfs_stats.get("timestamp")
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS cache check timed out")
            return {"success": False, "error": "VFS cache check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS cache: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_vector_index(self) -> Dict[str, Any]:
        """Get VFS vector index information with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(8):  # 8 second timeout
                if self.vfs_observer:
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    
                    # Mock vector index data based on VFS statistics
                    vector_data = {
                        "status": "active",
                        "total_vectors": 1250,
                        "dimensions": 1536,
                        "index_size": "45.2 MB",
                        "last_updated": vfs_stats.get("timestamp"),
                        "search_performance": {
                            "avg_query_time": "12.5ms",
                            "queries_per_second": 850,
                            "cache_hit_rate": "78%"
                        },
                        "content_distribution": {
                            "documents": 620,
                            "code_files": 380,
                            "images": 180,
                            "other": 70
                        }
                    }
                    
                    return {
                        "success": True,
                        "data": vector_data,
                        "timestamp": vfs_stats.get("timestamp")
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS vector index check timed out")
            return {"success": False, "error": "VFS vector index check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS vector index: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_knowledge_base(self) -> Dict[str, Any]:
        """Get VFS knowledge base information with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(8):  # 8 second timeout
                if self.vfs_observer:
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    
                    # Mock knowledge base data based on VFS statistics
                    kb_data = {
                        "status": "active",
                        "total_entities": 3420,
                        "total_relationships": 8975,
                        "graph_density": 0.76,
                        "last_updated": vfs_stats.get("timestamp"),
                        "entity_types": {
                            "files": 1200,
                            "directories": 340,
                            "code_symbols": 1180,
                            "metadata": 700
                        },
                        "relationship_types": {
                            "contains": 2145,
                            "imports": 1890,
                            "references": 2340,
                            "similar_to": 1200,
                            "derived_from": 1400
                        }
                    }
                    
                    return {
                        "success": True,
                        "data": kb_data,
                        "timestamp": vfs_stats.get("timestamp")
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS knowledge base check timed out")
            return {"success": False, "error": "VFS knowledge base check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS knowledge base: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_recommendations(self) -> Dict[str, Any]:
        """Get VFS recommendations with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(8):  # 8 second timeout
                if self.vfs_observer:
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    
                    # Generate recommendations based on VFS statistics
                    recommendations = []
                    
                    # Check resource utilization
                    resource_util = vfs_stats.get("resource_utilization", {})
                    memory_usage = resource_util.get("memory_usage", {})
                    
                    if memory_usage.get("system_used_percent", 0) > 80:
                        recommendations.append({
                            "type": "performance",
                            "priority": "high",
                            "title": "High Memory Usage",
                            "description": "System memory usage is above 80%. Consider optimizing cache settings.",
                            "action": "Reduce cache size or increase system memory"
                        })
                    
                    if vfs_stats.get("cache_performance", {}).get("hit_rate", 0) < 0.6:
                        recommendations.append({
                            "type": "optimization",
                            "priority": "medium",
                            "title": "Low Cache Hit Rate",
                            "description": "Cache hit rate is below 60%. Consider adjusting cache strategy.",
                            "action": "Review cache configuration and access patterns"
                        })
                    
                    # Add default recommendations if none generated
                    if not recommendations:
                        recommendations.append({
                            "type": "info",
                            "priority": "low",
                            "title": "System Running Optimally",
                            "description": "All VFS metrics are within acceptable ranges.",
                            "action": "Continue monitoring for any changes"
                        })
                    
                    return {
                        "success": True,
                        "data": {
                            "recommendations": recommendations,
                            "total_count": len(recommendations),
                            "last_updated": vfs_stats.get("timestamp")
                        },
                        "timestamp": vfs_stats.get("timestamp")
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS recommendations check timed out")
            return {"success": False, "error": "VFS recommendations check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS recommendations: {e}")
            return {"success": False, "error": str(e)}
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    return {"success": True, "data": await self.vfs_observer.get_cache_statistics()}
                else:
                    logger.warning("VFS observer not available, returning error for get_vfs_cache")
                    return {"error": "VFS observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS cache check timed out")
            return {"error": "VFS cache check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS cache: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """Get VFS statistics with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(8):  # 8 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    return {"success": True, "data": await self.vfs_observer.get_vfs_statistics()}
                else:
                    logger.warning("VFS observer not available, returning error for get_vfs_statistics")
                    return {"error": "VFS observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS statistics check timed out")
            return {"error": "VFS statistics check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS statistics: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_vfs_vector_index(self) -> Dict[str, Any]:
        """Get VFS vector index information with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    return {"success": True, "data": await self.vfs_observer.get_vector_index_statistics()}
                else:
                    logger.warning("VFS observer not available, returning error for get_vfs_vector_index")
                    return {"error": "VFS observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS vector index check timed out")
            return {"error": "VFS vector index check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS vector index: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_vfs_knowledge_base(self) -> Dict[str, Any]:
        """Get VFS knowledge base information with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    return {"success": True, "data": await self.vfs_observer.get_knowledge_base_statistics()}
                else:
                    logger.warning("VFS observer not available, returning error for get_vfs_knowledge_base")
                    return {"error": "VFS observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS knowledge base check timed out")
            return {"error": "VFS knowledge base check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS knowledge base: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_vfs_recommendations(self) -> Dict[str, Any]:
        """Get VFS optimization recommendations with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    
                    recommendations = []
                    
                    # Simple recommendations based on actual data
                    cache_perf = vfs_stats.get("cache_performance", {})
                    if cache_perf:
                        tiered_cache = cache_perf.get("tiered_cache", {})
                        memory_tier = tiered_cache.get("memory_tier", {})
                        if memory_tier.get("hit_rate", 0) < 0.8:
                            recommendations.append({
                                "category": "cache",
                                "title": "Improve Memory Cache Hit Rate",
                                "description": f"Current hit rate: {memory_tier.get('hit_rate', 0):.1%}",
                                "impact": "high"
                            })
                    
                    resource_util = vfs_stats.get("resource_utilization", {})
                    if resource_util:
                        memory_usage = resource_util.get("memory_usage", {})
                        if memory_usage.get("system_used_percent", 0) > 85:
                            recommendations.append({
                                "category": "memory",
                                "title": "High Memory Usage",
                                "description": f"System memory usage: {memory_usage.get('system_used_percent', 0):.1f}%",
                                "impact": "medium"
                            })
                    
                    return {"success": True, "recommendations": recommendations}
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS recommendations check timed out")
            return {"success": False, "error": "VFS recommendations check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS recommendations: {e}")
            return {"success": False, "error": str(e)}

    async def get_vector_index(self) -> Dict[str, Any]:
        """Get vector index status and metrics with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    vector_data = await self.vfs_observer.get_vector_index_statistics()
                    return {"success": True, "data": vector_data}
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("Vector index check timed out")
            return {"success": False, "error": "Vector index check timed out"}
        except Exception as e:
            logger.error(f"Error getting vector index: {e}")
            return {"success": False, "error": str(e)}

    async def get_knowledge_base(self) -> Dict[str, Any]:
        """Get knowledge base metrics with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    kb_data = await self.vfs_observer.get_knowledge_base_statistics()
                    return {"success": True, "data": kb_data}
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("Knowledge base check timed out")
            return {"success": False, "error": "Knowledge base check timed out"}
        except Exception as e:
            logger.error(f"Error getting knowledge base: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_access_patterns(self) -> Dict[str, Any]:
        """Get VFS access patterns with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    # Extract access patterns from VFS stats
                    return {
                        "success": True,
                        "access_patterns": vfs_stats.get("access_patterns", {
                            "read_frequency": {"hot_files": [], "cold_files": []},
                            "write_patterns": {"sequential": 0.65, "random": 0.35},
                            "temporal_patterns": {"peak_hours": [9, 17], "low_activity": [22, 6]}
                        })
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS access patterns check timed out")
            return {"success": False, "error": "VFS access patterns check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS access patterns: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_resource_utilization(self) -> Dict[str, Any]:
        """Get VFS resource utilization with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    return {
                        "success": True,
                        "resource_utilization": vfs_stats.get("resource_utilization", {})
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS resource utilization check timed out")
            return {"success": False, "error": "VFS resource utilization check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS resource utilization: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_filesystem_metrics(self) -> Dict[str, Any]:
        """Get VFS filesystem metrics with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            async with asyncio.timeout(5):  # 5 second timeout
                if self.vfs_observer: # Use self.vfs_observer directly
                    vfs_stats = await self.vfs_observer.get_vfs_statistics()
                    return {
                        "success": True,
                        "filesystem_metrics": vfs_stats.get("filesystem_status", {})
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except asyncio.TimeoutError:
            logger.error("VFS filesystem metrics check timed out")
            return {"success": False, "error": "VFS filesystem metrics check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS filesystem metrics: {e}")
            return {"success": False, "error": str(e)}

    async def list_files(self, path: str = "/") -> Dict[str, Any]:
        """Lists files and directories for the file manager."""
        try:
            base_path = Path("/tmp/vfs")
            # Ensure the path is relative to VFS_ROOT and safe
            abs_path = (base_path / path.strip("/")).resolve()

            # Prevent directory traversal attacks
            if not str(abs_path).startswith(str(base_path)):
                raise ValueError("Invalid path for listing files.")

            if not abs_path.exists():
                abs_path.mkdir(parents=True, exist_ok=True)

            files = []
            for item in abs_path.iterdir():
                try:
                    stat_res = item.stat()
                    files.append({
                        "name": item.name,
                        "path": "/" + str(item.relative_to(base_path)), # Return full path relative to VFS_ROOT
                        "type": "folder" if item.is_dir() else "file",
                        "size": stat_res.st_size if item.is_file() else 0,
                        "modified_at": stat_res.st_mtime # Use modified_at for consistency
                    })
                except Exception as e:
                    logger.warning(f"Error reading item {item}: {e}")
                    continue
            return {"success": True, "files": files}
        except Exception as e:
            logger.error(f"Error listing files in '{path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def create_folder(self, path: str, name: str) -> Dict[str, Any]:
        """Creates a new folder for the file manager."""
        start_time = time.time()
        try:
            base_path = Path("/tmp/vfs")
            target_dir = (base_path / path.strip("/")).resolve()
            new_folder_path = (target_dir / name).resolve()

            if not str(new_folder_path).startswith(str(base_path)):
                raise ValueError("Invalid path for creating folder.")

            new_folder_path.mkdir(parents=True)
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="create_folder", 
                path=str(new_folder_path.relative_to(base_path)), 
                success=True, 
                duration_ms=duration_ms
            )
            return {"success": True, "message": f"Folder '{name}' created at '{path}'."}
        except FileExistsError:
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="create_folder", 
                path=str(new_folder_path.relative_to(base_path)), 
                success=False, 
                duration_ms=duration_ms,
                details="Folder already exists"
            )
            return {"success": False, "error": f"Folder '{name}' already exists at '{path}'."}
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="create_folder", 
                path=name, 
                success=False, 
                duration_ms=duration_ms,
                details=str(e)
            )
            logger.error(f"Error creating folder '{name}' in '{path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def delete_item(self, path: str) -> Dict[str, Any]:
        """Deletes a file or folder for the file manager."""
        start_time = time.time()
        try:
            base_path = Path("/tmp/vfs")
            target_path = (base_path / path.strip("/")).resolve()

            if not str(target_path).startswith(str(base_path)):
                raise ValueError("Invalid path for deleting item.")

            if not target_path.exists():
                return {"success": False, "error": "File or folder not found."}
            
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()
            
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="delete_item", 
                path=path, 
                success=True, 
                duration_ms=duration_ms
            )
            return {"success": True, "message": f"Item '{path}' deleted."}
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="delete_item", 
                path=path, 
                success=False, 
                duration_ms=duration_ms,
                details=str(e)
            )
            logger.error(f"Error deleting item '{path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def rename_item(self, old_path: str, new_name: str) -> Dict[str, Any]:
        """Renames a file or folder for the file manager."""
        start_time = time.time()
        try:
            base_path = Path("/tmp/vfs")
            full_old_path = (base_path / old_path.strip("/")).resolve()

            if not str(full_old_path).startswith(str(base_path)):
                raise ValueError("Invalid old path for renaming item.")

            if not full_old_path.exists():
                return {"success": False, "error": "File or folder not found."}

            new_path = (full_old_path.parent / new_name).resolve()

            if not str(new_path).startswith(str(base_path)):
                raise ValueError("Invalid new path for renaming item.")

            if new_path.exists():
                return {"success": False, "error": f"'{new_name}' already exists."}

            full_old_path.rename(new_path)
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="rename_item", 
                path=old_path, 
                success=True, 
                duration_ms=duration_ms,
                details=f"Renamed to {new_name}"
            )
            return {"success": True, "message": "Item renamed successfully."}
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="rename_item", 
                path=old_path, 
                success=False, 
                duration_ms=duration_ms,
                details=str(e)
            )
            logger.error(f"Error renaming item '{old_path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def upload_file(self, path: str, file: UploadFile) -> Dict[str, Any]:
        """Uploads a file to the specified path for the file manager."""
        start_time = time.time()
        try:
            base_path = Path("/tmp/vfs")
            target_dir = (base_path / path.strip("/")).resolve()
            target_file_path = (target_dir / file.filename).resolve()

            if not str(target_dir).startswith(str(base_path)):
                raise ValueError("Invalid path for uploading file.")

            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            
            with target_file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="upload_file", 
                path=str(target_file_path.relative_to(base_path)), 
                success=True, 
                duration_ms=duration_ms
            )
            return {"success": True, "message": f"File '{file.filename}' uploaded to '{path}'."}
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="upload_file", 
                path=file.filename, 
                success=False, 
                duration_ms=duration_ms,
                details=str(e)
            )
            logger.error(f"Error uploading file to '{path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Moves a file or folder to a new location for the file manager."""
        start_time = time.time()
        try:
            base_path = Path("/tmp/vfs")
            full_source_path = (base_path / source_path.strip("/")).resolve()
            full_target_path = (base_path / target_path.strip("/")).resolve()
            
            if not str(full_source_path).startswith(str(base_path)):
                raise ValueError("Invalid source path for moving item.")
            if not str(full_target_path).startswith(str(base_path)):
                raise ValueError("Invalid target path for moving item.")

            if not full_source_path.exists():
                return {"success": False, "error": "Source file or folder not found."}
            
            # Ensure target directory exists
            if not full_target_path.parent.exists():
                full_target_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(full_source_path), str(full_target_path))
            
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="move_item", 
                path=source_path, 
                success=True, 
                duration_ms=duration_ms,
                details=f"Moved to {target_path}"
            )
            return {"success": True, "message": f"Item '{source_path}' moved to '{target_path}'."}
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.vfs_observer.log_vfs_operation(
                backend="VFS", 
                operation="move_item", 
                path=source_path, 
                success=False, 
                duration_ms=duration_ms,
                details=str(e)
            )
            logger.error(f"Error moving item from '{source_path}' to '{target_path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def download_file(self, path: str) -> Dict[str, Any]:
        """Downloads a file from the VFS."""
        try:
            base_path = Path("/tmp/vfs")
            target_path = base_path / path.strip("/")
            
            if not target_path.exists() or not target_path.is_file():
                return {"success": False, "error": "File not found."}
            
            with open(target_path, "rb") as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "name": target_path.name,
                "media_type": "application/octet-stream" # Default media type
            }
        except Exception as e:
            logger.error(f"Error downloading file '{path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def delete_file(self, filename: str) -> Dict[str, Any]:
        """Delete a file from the VFS."""
        try:
            file_path = VFS_ROOT / filename
            
            if not file_path.exists():
                return {"success": False, "error": "File not found"}
            
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                return {"success": False, "error": "Unknown file type"}
            
            return {
                "success": True,
                "message": f"'{filename}' deleted successfully"
            }
        except Exception as e:
            logger.error(f"Error deleting file '{filename}': {e}")
            return {"success": False, "error": str(e)}

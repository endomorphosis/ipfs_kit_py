"""
VFS tools for MCP server.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class VFSTools:
    """Tools for VFS operations."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
    
    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """Get VFS statistics."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                return await self.backend_monitor.vfs_observer.get_vfs_statistics()
            else:
                return {
                    "cache_hit_rate": 0,
                    "cache_size": 0,
                    "total_files": 0,
                    "total_size": 0,
                    "error": "VFS observer not available"
                }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_vfs_cache(self) -> Dict[str, Any]:
        """Get VFS cache information."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                return await self.backend_monitor.vfs_observer.get_cache_statistics()
            else:
                return {
                    "cache_entries": 0,
                    "cache_size_mb": 0,
                    "cache_hit_rate": 0,
                    "error": "VFS observer not available"
                }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_vfs_vector_index(self) -> Dict[str, Any]:
        """Get VFS vector index information."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                return await self.backend_monitor.vfs_observer.get_vector_index_statistics()
            else:
                return {
                    "vector_count": 0,
                    "dimensions": 0,
                    "index_size_mb": 0,
                    "error": "VFS observer not available"
                }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_vfs_knowledge_base(self) -> Dict[str, Any]:
        """Get VFS knowledge base information."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                return await self.backend_monitor.vfs_observer.get_knowledge_base_statistics()
            else:
                return {
                    "kb_nodes": 0,
                    "kb_relationships": 0,
                    "kb_size_mb": 0,
                    "error": "VFS observer not available"
                }
        except Exception as e:
            return {"error": str(e)}

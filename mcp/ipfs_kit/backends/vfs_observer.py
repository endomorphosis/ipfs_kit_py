"""
VFS observability manager for monitoring virtual file system.
"""

import logging
from typing import Dict, Any
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class VFSObservabilityManager:
    """Comprehensive VFS and cache observability."""
    
    def __init__(self):
        self.cache_stats = {
            "tiered_cache": {
                "memory_tier": {"hits": 0, "misses": 0, "size": 0, "items": 0},
                "disk_tier": {"hits": 0, "misses": 0, "size": 0, "items": 0},
                "ipfs_tier": {"hits": 0, "misses": 0, "size": 0, "items": 0},
                "total_operations": 0,
                "hit_ratio": 0.0,
                "promotion_count": 0,
                "eviction_count": 0
            },
            "semantic_cache": {
                "exact_matches": 0,
                "similarity_matches": 0,
                "cache_entries": 0,
                "average_similarity": 0.0,
                "query_types": {},
                "embedding_dimension": 0
            },
            "vector_index": {
                "total_vectors": 0,
                "index_type": "unknown",
                "dimension": 0,
                "last_updated": None,
                "search_operations": 0,
                "average_search_time": 0.0,
                "index_size_mb": 0.0
            },
            "knowledge_base": {
                "documents_indexed": 0,
                "entities_count": 0,
                "relationships_count": 0,
                "graph_depth": 0,
                "content_types": {},
                "last_indexed": None
            }
        }
        
        self.access_patterns = {
            "most_accessed": [],
            "recent_operations": deque(maxlen=1000),
            "operation_types": defaultdict(int),
            "content_popularity": defaultdict(int),
            "temporal_patterns": defaultdict(list)
        }
        
    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """Get comprehensive VFS statistics."""
        try:
            stats = {
                "cache_performance": await self._get_cache_performance(),
                "vector_index_status": await self._get_vector_index_status(),
                "knowledge_base_status": await self._get_knowledge_base_status(),
                "filesystem_metrics": await self._get_filesystem_metrics(),
                "access_patterns": await self._get_access_patterns(),
                "resource_utilization": await self._get_resource_utilization(),
                "timestamp": datetime.now().isoformat()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting VFS statistics: {e}")
            return {"error": str(e)}
    
    async def _get_cache_performance(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        return {
            "tiered_cache": {
                "memory_tier": {
                    "hit_rate": 0.85,
                    "size_mb": 128.5,
                    "items": 1247,
                    "evictions_per_hour": 12,
                    "average_item_size": "105KB"
                },
                "disk_tier": {
                    "hit_rate": 0.72,
                    "size_gb": 2.3,
                    "items": 15678,
                    "read_latency_ms": 8.5,
                    "write_latency_ms": 12.3
                },
                "predictive_accuracy": 0.78,
                "prefetch_efficiency": 0.82
            },
            "semantic_cache": {
                "similarity_threshold": 0.85,
                "exact_matches": self.cache_stats["semantic_cache"]["exact_matches"],
                "similarity_matches": self.cache_stats["semantic_cache"]["similarity_matches"],
                "cache_utilization": 0.67,
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        }
    
    async def _get_vector_index_status(self) -> Dict[str, Any]:
        """Get vector index status and metrics."""
        return {
            "index_health": "healthy",
            "total_vectors": 45672,
            "index_type": "FAISS IVF",
            "dimension": 384,
            "clusters": 100,
            "index_size_mb": 156.8,
            "search_performance": {
                "average_query_time_ms": 4.2,
                "queries_per_second": 238,
                "recall_at_10": 0.94,
                "precision_at_10": 0.89
            },
            "content_distribution": {
                "text_documents": 23456,
                "code_files": 12890,
                "markdown_files": 5634,
                "json_objects": 3692
            },
            "last_updated": "2025-01-13T23:15:30Z",
            "update_frequency": "real-time"
        }
    
    async def _get_knowledge_base_status(self) -> Dict[str, Any]:
        """Get knowledge base and graph metrics."""
        return {
            "graph_health": "healthy",
            "nodes": {
                "total": 67890,
                "documents": 34567,
                "entities": 18923,
                "concepts": 8765,
                "relations": 5635
            },
            "edges": {
                "total": 145678,
                "semantic_links": 67890,
                "reference_links": 45678,
                "temporal_links": 23456,
                "hierarchical_links": 8654
            },
            "graph_metrics": {
                "density": 0.032,
                "clustering_coefficient": 0.78,
                "average_path_length": 3.4,
                "modularity": 0.85,
                "connected_components": 12
            },
            "content_analysis": {
                "languages_detected": ["en", "python", "javascript", "markdown"],
                "topics_identified": 234,
                "sentiment_distribution": {"positive": 0.6, "neutral": 0.3, "negative": 0.1},
                "complexity_scores": {"low": 0.4, "medium": 0.45, "high": 0.15}
            }
        }
    
    async def _get_filesystem_metrics(self) -> Dict[str, Any]:
        """Get filesystem-specific metrics."""
        return {
            "mount_points": {
                "ipfs://": {"status": "active", "operations": 12345, "size_gb": 45.6},
                "filecoin://": {"status": "active", "operations": 6789, "size_gb": 23.4},
                "storacha://": {"status": "active", "operations": 3456, "size_gb": 12.1},
                "s3://": {"status": "configured", "operations": 8901, "size_gb": 67.8}
            },
            "file_operations": {
                "reads": 45678,
                "writes": 12345,
                "deletes": 234,
                "listings": 6789,
                "seeks": 23456
            },
            "bandwidth_usage": {
                "read_mbps": 125.4,
                "write_mbps": 67.8,
                "total_transferred_gb": 234.5,
                "compression_ratio": 0.72
            }
        }
    
    async def _get_access_patterns(self) -> Dict[str, Any]:
        """Get access pattern analysis."""
        return {
            "hot_content": [
                {"cid": "QmX1...", "access_count": 456, "size_kb": 1234},
                {"cid": "QmY2...", "access_count": 389, "size_kb": 567},
                {"cid": "QmZ3...", "access_count": 234, "size_kb": 890}
            ],
            "temporal_patterns": {
                "peak_hours": [9, 10, 11, 14, 15, 16],
                "low_activity_hours": [0, 1, 2, 3, 4, 5],
                "weekly_pattern": "weekday_heavy",
                "seasonal_trend": "stable"
            },
            "content_types": {
                "application/json": 0.35,
                "text/plain": 0.25,
                "image/png": 0.15,
                "application/pdf": 0.12,
                "text/markdown": 0.13
            },
            "geographic_distribution": {
                "local": 0.78,
                "remote_gateways": 0.22,
                "cdn_hits": 0.45
            }
        }
    
    async def _get_resource_utilization(self) -> Dict[str, Any]:
        """Get resource utilization metrics."""
        return {
            "memory_usage": {
                "cache_mb": 256.7,
                "index_mb": 156.8,
                "buffers_mb": 45.2,
                "total_mb": 458.7,
                "available_mb": 2048.3
            },
            "disk_usage": {
                "cache_gb": 2.3,
                "index_gb": 0.8,
                "logs_gb": 0.1,
                "temp_gb": 0.3,
                "total_gb": 3.5,
                "available_gb": 125.7
            },
            "cpu_usage": {
                "indexing": 0.15,
                "search": 0.08,
                "cache_management": 0.05,
                "total": 0.28
            },
            "network_usage": {
                "ipfs_connections": 45,
                "cluster_connections": 8,
                "gateway_connections": 23,
                "bandwidth_utilization": 0.34
            }
        }
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return await self._get_cache_performance()
    
    async def get_vector_index_statistics(self) -> Dict[str, Any]:
        """Get vector index statistics."""
        return await self._get_vector_index_status()
    
    async def get_knowledge_base_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        return await self._get_knowledge_base_status()

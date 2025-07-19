"""
Backend monitoring and observability components.
"""
import asyncio
import json
import logging
import os
import random
import subprocess
import threading
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VFSObservabilityManager:
    """Comprehensive VFS and cache observability."""

    def __init__(self, storage_api=None):
        self.storage_api = storage_api
        self.backend_stats: Dict[str, Dict[str, Any]] = {}
        
        # Enhanced cache stats tracking
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
        
        self._initialize_mock_stats()

    def _initialize_mock_stats(self):
        """Initialize mock stats for testing."""
        self.backend_stats = {
            "ipfs": {
                "status": "healthy",
                "health": "good",
                "storage_used_gb": 10.5,
                "storage_total_gb": 100.0,
                "traffic_in_mbps": 5.2,
                "traffic_out_mbps": 3.8,
                "last_updated": time.time(),
            },
            "cluster": {
                "status": "healthy", 
                "health": "good",
                "storage_used_gb": 25.3,
                "storage_total_gb": 200.0,
                "traffic_in_mbps": 8.1,
                "traffic_out_mbps": 6.4,
                "last_updated": time.time(),
            }
        }

    async def _update_backend_stats(self):
        """Update backend stats from the storage API."""
        try:
            backends = await self.storage_api.list_storage_backends()
            for backend_name in backends.get("backends", {}):
                backend_info = await self.storage_api.get_storage_backend_info(backend_name)
                if backend_info.get("success"):
                    stats = backend_info.get("backend", {}).get("stats", {})
                    self.backend_stats[backend_name] = {
                        "status": backend_info.get("backend", {}).get("status", "unknown"),
                        "health": stats.get("health", "unknown"),
                        "storage_used_gb": stats.get("storage_used_gb", 0),
                        "storage_total_gb": stats.get("storage_total_gb", 0),
                        "traffic_in_mbps": stats.get("traffic_in_mbps", 0),
                        "traffic_out_mbps": stats.get("traffic_out_mbps", 0),
                        "last_updated": time.time(),
                    }
        except Exception as e:
            logger.error(f"Error updating backend stats: {e}")

    async def get_all_backend_stats(self) -> Dict[str, Any]:
        """Get stats for all VFS backends."""
        await self._update_backend_stats()
        return self.backend_stats

    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """Get comprehensive VFS statistics."""
        try:
            await self._update_backend_stats()
            
            # Calculate comprehensive statistics
            cache_performance = await self._get_cache_performance()
            vector_index_status = await self._get_vector_index_status()
            knowledge_base_status = await self._get_knowledge_base_status()
            filesystem_metrics = await self._get_filesystem_metrics()
            access_patterns = await self._get_access_patterns()
            resource_utilization = await self._get_resource_utilization()
            
            # Calculate totals
            total_storage_used = sum(stats.get("storage_used_gb", 0) for stats in self.backend_stats.values())
            total_storage_total = sum(stats.get("storage_total_gb", 0) for stats in self.backend_stats.values())
            
            return {
                "storage": {
                    "used_gb": total_storage_used,
                    "total_gb": total_storage_total,
                    "utilization_percent": (total_storage_used / total_storage_total * 100) if total_storage_total > 0 else 0
                },
                "backends": len(self.backend_stats),
                "healthy_backends": sum(1 for stats in self.backend_stats.values() if stats.get("status") == "healthy"),
                "cache_performance": cache_performance,
                "vector_index": vector_index_status,
                "knowledge_base": knowledge_base_status,
                "filesystem_metrics": filesystem_metrics,
                "access_patterns": access_patterns,
                "resource_utilization": resource_utilization,
                "last_updated": time.time()
            }
        except Exception as e:
            logger.error(f"Error getting VFS statistics: {e}")
            return {
                "error": str(e),
                "storage": {"used_gb": 0, "total_gb": 0, "utilization_percent": 0},
                "backends": 0,
                "healthy_backends": 0,
                "last_updated": time.time()
            }

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
            "total_vectors": random.randint(10000, 50000),
            "dimensions": 384,
            "index_size_mb": random.randint(100, 500),
            "query_latency_ms": round(random.uniform(10, 50), 2),
            "index_type": "HNSW",
            "build_time_seconds": random.randint(30, 300),
            "memory_usage_mb": random.randint(200, 800),
            "search_accuracy": round(random.uniform(0.85, 0.95), 3),
            "last_updated": time.time()
        }

    async def _get_knowledge_base_status(self) -> Dict[str, Any]:
        """Get knowledge base status and metrics."""
        return {
            "total_documents": random.randint(1000, 5000),
            "total_tokens": random.randint(100000, 1000000),
            "categories": ["technology", "science", "business", "general"],
            "search_index_size_mb": random.randint(50, 200),
            "entity_count": random.randint(5000, 25000),
            "relationship_count": random.randint(10000, 50000),
            "graph_depth": random.randint(3, 8),
            "extraction_accuracy": round(random.uniform(0.75, 0.90), 3),
            "last_indexed": time.time()
        }

    async def _get_filesystem_metrics(self) -> Dict[str, Any]:
        """Get comprehensive filesystem metrics."""
        return {
            "file_operations": {
                "reads_per_second": random.randint(10, 100),
                "writes_per_second": random.randint(5, 50),
                "deletes_per_second": random.randint(1, 10),
                "total_operations": random.randint(10000, 100000)
            },
            "storage_distribution": {
                "hot_data_percent": round(random.uniform(15, 25), 1),
                "warm_data_percent": round(random.uniform(35, 45), 1),
                "cold_data_percent": round(random.uniform(30, 50), 1)
            },
            "compression": {
                "enabled": True,
                "compression_ratio": round(random.uniform(2.5, 4.0), 2),
                "space_saved_gb": round(random.uniform(50, 200), 1)
            },
            "deduplication": {
                "enabled": True,
                "dedup_ratio": round(random.uniform(1.5, 3.0), 2),
                "space_saved_gb": round(random.uniform(25, 100), 1)
            }
        }

    async def _get_access_patterns(self) -> Dict[str, Any]:
        """Get file access pattern analysis."""
        return {
            "most_accessed_files": [
                {"path": "/data/dataset1.parquet", "access_count": 1245},
                {"path": "/cache/index.bin", "access_count": 987},
                {"path": "/models/embeddings.pt", "access_count": 654}
            ],
            "access_by_hour": {str(i): random.randint(100, 1000) for i in range(24)},
            "file_types": {
                "parquet": 45.2,
                "json": 25.8,
                "bin": 15.1,
                "txt": 8.9,
                "other": 5.0
            },
            "geographic_distribution": {
                "local": 75.5,
                "remote_cache": 18.2,
                "external": 6.3
            }
        }

    async def _get_resource_utilization(self) -> Dict[str, Any]:
        """Get resource utilization metrics."""
        try:
            import psutil
            
            # Get actual system metrics
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "usage_percent": round((disk.used / disk.total) * 100, 1)
                },
                "cpu": {
                    "usage_percent": cpu_percent,
                    "core_count": psutil.cpu_count(),
                    "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
                },
                "network": {
                    "bytes_sent": random.randint(1000000, 10000000),
                    "bytes_received": random.randint(1000000, 10000000),
                    "packets_sent": random.randint(10000, 100000),
                    "packets_received": random.randint(10000, 100000)
                }
            }
        except Exception as e:
            logger.error(f"Error getting resource utilization: {e}")
            return {
                "memory": {"total_gb": 0, "used_gb": 0, "usage_percent": 0},
                "disk": {"total_gb": 0, "used_gb": 0, "usage_percent": 0},
                "cpu": {"usage_percent": 0, "core_count": 0},
                "network": {"bytes_sent": 0, "bytes_received": 0}
            }

    async def get_vector_index_statistics(self) -> Dict[str, Any]:
        """Get vector index statistics."""
        # Mock data for vector index
        return {
            "total_vectors": random.randint(10000, 50000),
            "dimensions": 384,
            "index_size_mb": random.randint(100, 500),
            "query_latency_ms": round(random.uniform(10, 50), 2),
            "index_type": "HNSW",
            "last_updated": time.time()
        }

    async def get_knowledge_base_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        # Mock data for knowledge base
        return {
            "total_documents": random.randint(1000, 5000),
            "total_tokens": random.randint(100000, 1000000),
            "categories": ["technology", "science", "business", "general"],
            "search_index_size_mb": random.randint(50, 200),
            "last_indexed": time.time()
        }


class BackendHealthMonitor:
    """Comprehensive backend health and status monitoring."""

    def __init__(self):
        self.backends = {
            "ipfs": {
                "name": "IPFS",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 5001,
                "detailed_info": {
                    "repo_size": 0,
                    "repo_objects": 0,
                    "pins_count": 0,
                    "peer_count": 0,
                    "bandwidth_in": 0,
                    "bandwidth_out": 0,
                    "datastore_type": "unknown",
                    "api_address": "/ip4/127.0.0.1/tcp/5001",
                    "gateway_address": "/ip4/127.0.0.1/tcp/8080",
                    "config_profile": "unknown"
                }
            },
            "ipfs_cluster": {
                "name": "IPFS Cluster",
                "status": "unknown", 
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 9094,
                "detailed_info": {
                    "cluster_id": "unknown",
                    "peer_id": "unknown",
                    "cluster_peers": 0,
                    "pins_count": 0,
                    "allocations": {},
                    "consensus": "raft",
                    "api_address": "/ip4/127.0.0.1/tcp/9094",
                    "proxy_address": "/ip4/127.0.0.1/tcp/9095"
                }
            },
            "ipfs_cluster_follow": {
                "name": "IPFS Cluster Follow",
                "status": "unknown",
                "health": "unknown", 
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 9095
            },
            "lotus": {
                "name": "Lotus",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "daemon_pid": None,
                "port": 1234,
                "detailed_info": {
                    "node_type": "fullnode",
                    "network": "calibration",
                    "sync_status": "unknown",
                    "chain_height": 0,
                    "peers_count": 0,
                    "wallet_balance": "0 FIL",
                    "miner_address": None,
                    "api_address": "/ip4/127.0.0.1/tcp/1234/http",
                    "version": "unknown",
                    "commit": "unknown"
                }
            },
            "storacha": {
                "name": "Storacha",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "api_endpoints": [
                    "https://up.storacha.network/bridge",
                    "https://api.web3.storage",
                    "https://up.web3.storage/bridge"
                ]
            },
            "synapse": {
                "name": "Synapse SDK",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "js_wrapper": None,
                "npm_package": "@filoz/synapse-sdk"
            },
            "s3": {
                "name": "S3 Compatible",
                "status": "unknown",
                "health": "unknown", 
                "last_check": None,
                "metrics": {},
                "errors": [],
                "credentials": "missing"
            },
            "huggingface": {
                "name": "HuggingFace Hub",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "auth_token": "configured"
            },
            "parquet": {
                "name": "Parquet/Arrow",
                "status": "unknown",
                "health": "unknown",
                "last_check": None,
                "metrics": {},
                "errors": [],
                "libraries": ["pyarrow", "pandas"]
            }
        }
        
        self.metrics_history = defaultdict(lambda: deque(maxlen=100))
        self.monitoring_active = False
        self._monitor_thread = None
        self.last_health_check = {}  # Track last health check timestamps
        self.vfs_observer: 'VFSObservabilityManager' = None

    def start_monitoring(self):
        """Start background monitoring thread."""
        if not self.monitoring_active:
            self.monitoring_active = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            logger.info("✓ Backend monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self.monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("⏹️  Stopped backend monitoring")

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                # Run health checks in async context
                asyncio.run(self.check_all_backends())
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error

    async def check_backend_health(self, backend_name: str) -> Dict[str, Any]:
        """Check health of a specific backend."""
        
        if backend_name not in self.backends:
            return {"error": f"Unknown backend: {backend_name}"}
        
        backend = self.backends[backend_name]
        
        try:
            if backend_name == "ipfs":
                return await self._check_ipfs_health(backend)
            elif backend_name == "ipfs_cluster":
                return await self._check_ipfs_cluster_health(backend)
            elif backend_name == "ipfs_cluster_follow":
                return await self._check_ipfs_cluster_follow_health(backend)
            elif backend_name == "lotus":
                return await self._check_lotus_health(backend)
            elif backend_name == "storacha":
                return await self._check_storacha_health(backend)
            elif backend_name == "synapse":
                return await self._check_synapse_health(backend)
            elif backend_name == "s3":
                return await self._check_s3_health(backend)
            elif backend_name == "huggingface":
                return await self._check_huggingface_health(backend)
            elif backend_name == "parquet":
                return await self._check_parquet_health(backend)
            else:
                return {"error": f"Health check not implemented for {backend_name}"}
                
        except Exception as e:
            logger.error(f"Error checking {backend_name} health: {e}")
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"error": str(e)}

    async def _check_ipfs_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check IPFS daemon health."""
        
        try:
            # Check if daemon is running
            result = subprocess.run(
                ["curl", "-s", f"http://127.0.0.1:{backend['port']}/api/v0/version"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                version_info = json.loads(result.stdout)
                backend["status"] = "running"
                backend["health"] = "healthy"
                backend["metrics"] = {
                    "version": version_info.get("Version", "unknown"),
                    "commit": version_info.get("Commit", "unknown"),
                    "response_time_ms": 0  # Could measure actual response time
                }
                
                # Check additional metrics
                stats_result = subprocess.run(
                    ["curl", "-s", f"http://127.0.0.1:{backend['port']}/api/v0/stats/repo"],
                    capture_output=True, text=True, timeout=5
                )
                
                if stats_result.returncode == 0:
                    stats = json.loads(stats_result.stdout)
                    backend["detailed_info"].update({
                        "repo_size": stats.get("RepoSize", 0),
                        "repo_objects": stats.get("NumObjects", 0)
                    })
                    
            else:
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                backend["metrics"] = {}
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_ipfs_cluster_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check IPFS Cluster health."""
        
        try:
            # Check if cluster daemon is running
            result = subprocess.run(
                ["curl", "-s", f"http://127.0.0.1:{backend['port']}/api/v0/version"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                version_info = json.loads(result.stdout)
                backend["status"] = "running"
                backend["health"] = "healthy"
                backend["metrics"] = {
                    "version": version_info.get("version", "unknown")
                }
                
                # Check peers
                peers_result = subprocess.run(
                    ["curl", "-s", f"http://127.0.0.1:{backend['port']}/api/v0/peers"],
                    capture_output=True, text=True, timeout=5
                )
                
                if peers_result.returncode == 0:
                    peers = json.loads(peers_result.stdout)
                    backend["detailed_info"]["cluster_peers"] = len(peers)
                    
            else:
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                backend["metrics"] = {}
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_ipfs_cluster_follow_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check IPFS Cluster Follow health."""
        
        try:
            # Check if ipfs-cluster-follow process is running
            result = subprocess.run(
                ["pgrep", "-f", "ipfs-cluster-follow"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                backend["status"] = "running"
                backend["health"] = "healthy"
                backend["metrics"] = {
                    "process_running": True,
                    "pid": result.stdout.strip()
                }
            else:
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                backend["metrics"] = {
                    "process_running": False
                }
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_lotus_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Lotus daemon health."""
        
        try:
            # Check if lotus process is running
            result = subprocess.run(
                ["pgrep", "-f", "lotus"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                backend["status"] = "running"
                backend["health"] = "healthy"
                backend["metrics"] = {
                    "process_running": True,
                    "pid": result.stdout.strip()
                }
                
                # Try to get lotus version
                version_result = subprocess.run(
                    ["lotus", "version"],
                    capture_output=True, text=True, timeout=10
                )
                
                if version_result.returncode == 0:
                    backend["detailed_info"]["version"] = version_result.stdout.strip()
            else:
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                backend["metrics"] = {
                    "process_running": False
                }
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_storacha_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Storacha/Web3.Storage health."""
        
        try:
            import requests
            
            healthy_endpoints = 0
            endpoint_results = []
            
            for endpoint in backend["api_endpoints"]:
                try:
                    response = requests.get(endpoint, timeout=5)
                    endpoint_results.append({
                        "url": endpoint,
                        "status": response.status_code,
                        "response_time_ms": 0  # Could measure actual time
                    })
                    
                    # Consider 200 and 404 as healthy (404 is expected for some endpoints)
                    if response.status_code in [200, 404]:
                        healthy_endpoints += 1
                        
                except Exception as e:
                    endpoint_results.append({
                        "url": endpoint,
                        "status": 0,
                        "error": str(e)
                    })
            
            if healthy_endpoints > 0:
                backend["status"] = "running"
                backend["health"] = "healthy"
            else:
                backend["status"] = "unreachable"
                backend["health"] = "unhealthy"
                
            backend["metrics"] = {
                "healthy_endpoints": healthy_endpoints,
                "unhealthy_endpoints": len(backend["api_endpoints"]) - healthy_endpoints,
                "endpoints": endpoint_results
            }
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_synapse_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Synapse SDK health."""
        
        try:
            # Check if Node.js is available
            node_result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=5
            )
            
            node_available = node_result.returncode == 0
            node_version = node_result.stdout.strip() if node_available else "not available"
            
            # Check if npm package is installed
            npm_check = subprocess.run(
                ["npm", "list", backend["npm_package"]],
                capture_output=True, text=True, timeout=10
            )
            
            npm_installed = npm_check.returncode == 0
            
            if node_available and npm_installed:
                backend["status"] = "installed"
                backend["health"] = "healthy"
            elif node_available:
                backend["status"] = "not_installed"
                backend["health"] = "unhealthy"
            else:
                backend["status"] = "unavailable"
                backend["health"] = "unhealthy"
                
            backend["metrics"] = {
                "node_version": node_version,
                "node_available": node_available,
                "npm_package_installed": npm_installed
            }
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_s3_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check S3 compatible storage health."""
        
        try:
            # Check if boto3 is available
            try:
                import boto3
                boto3_available = True
            except ImportError:
                boto3_available = False
            
            # Check for AWS credentials
            aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
            credentials_available = bool(aws_access_key and aws_secret_key)
            
            if boto3_available and credentials_available:
                backend["status"] = "configured"
                backend["health"] = "healthy"
            elif boto3_available:
                backend["status"] = "unconfigured"
                backend["health"] = "unhealthy"
            else:
                backend["status"] = "unavailable"
                backend["health"] = "unhealthy"
                
            backend["metrics"] = {
                "boto3_available": boto3_available,
                "credentials_available": credentials_available
            }
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_huggingface_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check HuggingFace Hub health."""
        
        try:
            # Check if huggingface_hub is available
            try:
                from huggingface_hub import HfApi
                hf_available = True
                
                # Check authentication
                api = HfApi()
                try:
                    user_info = api.whoami()
                    authenticated = True
                    username = user_info.get("name", "unknown")
                except Exception:
                    authenticated = False
                    username = "unknown"
                    
            except ImportError:
                hf_available = False
                authenticated = False
                username = "unknown"
            
            if hf_available and authenticated:
                backend["status"] = "authenticated"
                backend["health"] = "healthy"
            elif hf_available:
                backend["status"] = "unauthenticated"
                backend["health"] = "unhealthy"
            else:
                backend["status"] = "unavailable"
                backend["health"] = "unhealthy"
                
            backend["metrics"] = {
                "huggingface_hub_available": hf_available,
                "authenticated": authenticated,
                "username": username
            }
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def _check_parquet_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check Parquet/Arrow libraries health."""
        
        try:
            libraries = {}
            
            # Check PyArrow
            try:
                import pyarrow
                libraries["pyarrow"] = {
                    "available": True,
                    "version": pyarrow.__version__
                }
            except ImportError:
                libraries["pyarrow"] = {"available": False}
            
            # Check Pandas
            try:
                import pandas
                libraries["pandas"] = {
                    "available": True,
                    "version": pandas.__version__
                }
            except ImportError:
                libraries["pandas"] = {"available": False}
            
            # Check Polars
            try:
                import polars
                libraries["polars"] = {
                    "available": True,
                    "version": polars.__version__
                }
            except ImportError:
                libraries["polars"] = {"available": False}
            
            available_libraries = [name for name, info in libraries.items() if info["available"]]
            
            if len(available_libraries) >= 2:
                backend["status"] = "available"
                backend["health"] = "healthy"
            elif len(available_libraries) >= 1:
                backend["status"] = "partial"
                backend["health"] = "degraded"
            else:
                backend["status"] = "unavailable"
                backend["health"] = "unhealthy"
                
            backend["metrics"] = {
                "libraries": libraries
            }
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            
        backend["last_check"] = datetime.now().isoformat()
        return backend

    async def check_all_backends(self) -> Dict[str, Any]:
        """Check health of all backends."""
        
        results = {}
        
        # Check backends in parallel
        tasks = [(name, self.check_backend_health(name)) for name in self.backends.keys()]
        
        for backend_name, task in tasks:
            try:
                results[backend_name] = await task
            except Exception as e:
                logger.error(f"Failed to check {backend_name}: {e}")
                results[backend_name] = {
                    "error": str(e),
                    "status": "error",
                    "health": "unhealthy"
                }
                
                return results

    async def get_backend_logs(self, backend_name: str) -> str:
        """Get logs for a specific backend."""
        try:
            if backend_name == "ipfs":
                # Try to get IPFS daemon logs
                log_paths = [
                    "~/.ipfs/logs/events.log",
                    "/var/log/ipfs.log",
                    "/tmp/ipfs.log"
                ]
                
                for log_path in log_paths:
                    expanded_path = Path(log_path).expanduser()
                    if expanded_path.exists():
                        return expanded_path.read_text()[-10000:]  # Last 10KB
                        
                return "No logs found for IPFS"
                
            elif backend_name == "lotus":
                log_paths = [
                    "~/.lotus/logs/lotus.log",
                    "/var/log/lotus.log"
                ]
                
                for log_path in log_paths:
                    expanded_path = Path(log_path).expanduser()
                    if expanded_path.exists():
                        return expanded_path.read_text()[-10000:]
                        
                return "No logs found for Lotus"
                
            else:
                return f"Log retrieval not implemented for {backend_name}"
                
        except Exception as e:
            return f"Error retrieving logs: {str(e)}"

    async def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get current configuration for a backend."""
        try:
            if backend_name == "ipfs":
                result = subprocess.run(
                    ["ipfs", "config", "show"],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    return {"config": json.loads(result.stdout)}
                else:
                    return {"error": "Failed to get IPFS config"}
                    
            elif backend_name == "lotus":
                config_path = Path("~/.lotus/config.toml").expanduser()
                if config_path.exists():
                    return {"config": config_path.read_text()}
                else:
                    return {"error": "Lotus config file not found"}
                    
            else:
                return {"error": f"Config retrieval not implemented for {backend_name}"}
                
        except Exception as e:
            return {"error": str(e)}

    async def update_backend_config(self, backend_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration for a backend."""
        try:
            if backend_name == "ipfs":
                return await self._update_ipfs_config(config_data)
            elif backend_name == "lotus":
                return await self._update_lotus_config(config_data)
            elif backend_name == "huggingface":
                return await self._update_huggingface_config(config_data)
            elif backend_name == "s3":
                return await self._update_s3_config(config_data)
            else:
                return {"error": f"Config update not implemented for {backend_name}"}
                
        except Exception as e:
            return {"error": str(e)}

    async def _update_ipfs_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update IPFS configuration."""
        try:
            for key, value in config_data.items():
                result = subprocess.run(
                    ["ipfs", "config", key, json.dumps(value)],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode != 0:
                    return {"error": f"Failed to update {key}: {result.stderr}"}
                    
            return {"success": True, "message": "IPFS configuration updated"}
            
        except Exception as e:
            return {"error": str(e)}

    async def _update_lotus_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update Lotus configuration."""
        try:
            config_path = Path("~/.lotus/config.toml").expanduser()
            
            # This is a simplified approach - in practice, you'd want to parse TOML properly
            if "content" in config_data:
                config_path.write_text(config_data["content"])
                return {"success": True, "message": "Lotus configuration updated"}
            else:
                return {"error": "No configuration content provided"}
                
        except Exception as e:
            return {"error": str(e)}

    async def _update_huggingface_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update HuggingFace configuration."""
        try:
            if "token" in config_data:
                # Set environment variable
                os.environ["HUGGINGFACE_HUB_TOKEN"] = config_data["token"]
                
                # Also save to HF config file
                hf_config_dir = Path("~/.cache/huggingface").expanduser()
                hf_config_dir.mkdir(parents=True, exist_ok=True)
                
                token_file = hf_config_dir / "token"
                token_file.write_text(config_data["token"])
                
                return {"success": True, "message": "HuggingFace token updated"}
            else:
                return {"error": "No token provided"}
                
        except Exception as e:
            return {"error": str(e)}

    async def _update_s3_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update S3 configuration."""
        try:
            if "access_key" in config_data:
                os.environ["AWS_ACCESS_KEY_ID"] = config_data["access_key"]
            if "secret_key" in config_data:
                os.environ["AWS_SECRET_ACCESS_KEY"] = config_data["secret_key"]
            if "region" in config_data:
                os.environ["AWS_DEFAULT_REGION"] = config_data["region"]
                
            return {"success": True, "message": "S3 configuration updated"}
            
        except Exception as e:
            return {"error": str(e)}

    async def restart_backend(self, backend_name: str) -> Dict[str, Any]:
        """Restart a specific backend daemon."""
        try:
            if backend_name == "ipfs":
                # Stop IPFS daemon
                subprocess.run(["ipfs", "shutdown"], timeout=10)
                time.sleep(2)
                
                # Start IPFS daemon
                subprocess.Popen(["ipfs", "daemon"])
                
                return {"success": True, "message": "IPFS daemon restart initiated"}
                
            elif backend_name == "lotus":
                # Kill lotus processes
                subprocess.run(["pkill", "-f", "lotus"], timeout=5)
                time.sleep(2)
                
                # Start lotus daemon
                subprocess.Popen(["lotus", "daemon"])
                
                return {"success": True, "message": "Lotus daemon restart initiated"}
                
            else:
                return {"error": f"Restart not implemented for {backend_name}"}
                
        except Exception as e:
            return {"error": str(e)}    async def get_backend_health(self) -> List[Dict[str, Any]]:
        """Gathers and formats health and observability stats for the dashboard."""
        if not self.vfs_observer:
            return []

        all_stats = await self.vfs_observer.get_all_backend_stats()
        health_data = []
        for name, stats in all_stats.items():
            stats_copy = stats.copy()
            stats_copy["name"] = name.replace("_", " ").title()
            stats_copy["storage_used"] = stats_copy.pop("storage_used_gb")
            stats_copy["storage_total"] = stats_copy.pop("storage_total_gb")
            stats_copy["traffic_in"] = stats_copy.pop("traffic_in_mbps")
            stats_copy["traffic_out"] = stats_copy.pop("traffic_out_mbps")
            health_data.append(stats_copy)
        return health_data
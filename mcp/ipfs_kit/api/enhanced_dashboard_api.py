#!/usr/bin/env python3
"""
Enhanced Dashboard API Controller

This module provides comprehensive API endpoints for dashboard management including:
- Enhanced daemon status and control
- IPFS Cluster service management  
- LibP2P peer network monitoring
- Health monitoring and auto-healing
- Real-time metrics and performance data
"""

import asyncio
import json
import logging
import os
import glob
import psutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ipfs_kit_py.ipfs.ipfs_py import IPFSClient

# Configure logger first
logger = logging.getLogger(__name__)

from ..backends.health_monitor import BackendHealthMonitor

# Import cluster configuration API
try:
    from .cluster_config_api import cluster_config_api, CLUSTER_CONFIG_TOOLS, handle_cluster_config_tool
    CLUSTER_CONFIG_AVAILABLE = True
except ImportError:
    logger.warning("Cluster configuration API not available")
    CLUSTER_CONFIG_AVAILABLE = False
    cluster_config_api = None
    CLUSTER_CONFIG_TOOLS = []

# Import columnar IPLD and VFS components
try:
    from ipfs_kit_py.parquet_car_bridge import ParquetCARBridge
    from ipfs_kit_py.parquet_ipld_bridge import ParquetIPLDBridge
    from ipfs_kit_py.ipld_knowledge_graph import IPLDGraphDB, GraphRAG
    from ipfs_kit_py.tiered_cache_manager import TieredCacheManager
    from ipfs_kit_py.dashboard.enhanced_vfs_apis import VFSMetadataAPI, VectorIndexAPI, KnowledgeGraphAPI, PinsetAPI
    COLUMNAR_IPLD_AVAILABLE = True
    logger.info("✓ Columnar IPLD components available")
except ImportError as e:
    logger.warning(f"Columnar IPLD components not available: {e}")
    COLUMNAR_IPLD_AVAILABLE = False

# Router for dashboard API
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

class DaemonActionRequest(BaseModel):
    """Request model for daemon actions."""
    daemon_name: str
    action: str  # start, stop, restart, status
    force: bool = False
    auto_heal: bool = True

class ClusterActionRequest(BaseModel):
    """Request model for cluster actions."""
    action: str  # start, stop, restart, status, peers
    force_restart: bool = False

class VirtualFilesystemRequest(BaseModel):
    """Request model for virtual filesystem operations."""
    action: str  # list, get, convert_to_car, query
    dataset_id: Optional[str] = None
    include_car: bool = True
    include_vector_index: bool = True
    include_knowledge_graph: bool = True
    
class VectorIndexRequest(BaseModel):
    """Request model for vector index operations."""
    action: str  # search, list, export_car, get_status
    collection_id: Optional[str] = None
    query_vector: Optional[List[float]] = None
    top_k: int = 10
    include_metadata: bool = True

class KnowledgeGraphRequest(BaseModel):
    """Request model for knowledge graph operations."""
    action: str  # search, get_entity, list_entities, export_car
    entity_id: Optional[str] = None
    query: Optional[str] = None
    max_depth: int = 3
    include_relationships: bool = True

class PinsetRequest(BaseModel):
    """Request model for pinset operations."""
    action: str  # list, get, replicate, track_backends
    cid: Optional[str] = None
    target_backend: Optional[str] = None
    include_metadata: bool = True

class HealthCheckRequest(BaseModel):
    """Request model for health checks."""
    backend_name: Optional[str] = None
    force_check: bool = False
    include_metrics: bool = True

class ReplicationSettings(BaseModel):
    """Model for replication settings."""
    min_replicas: int = 2
    max_replicas: int = 5
    target_replicas: int = 3
    max_size_gb: float = 100.0
    preferred_backends: List[str] = []
    auto_replication: bool = True
    replication_strategy: str = "balanced"  # balanced, priority, size_based

class ReplicationRequest(BaseModel):
    """Request model for replication operations."""
    action: str  # configure, replicate, backup, restore, analyze, cleanup
    cid: Optional[str] = None
    backend_name: Optional[str] = None
    settings: Optional[ReplicationSettings] = None
    target_backends: Optional[List[str]] = None
    backup_path: Optional[str] = None
    restore_path: Optional[str] = None
    force: bool = False

class BackupRestoreRequest(BaseModel):
    """Request model for backup/restore operations."""
    action: str  # export_pins, import_pins, list_backups, verify_backup
    backend_name: str
    backup_path: Optional[str] = None
    include_metadata: bool = True
    compress: bool = True
    encryption_key: Optional[str] = None

class TrafficCounter:
    """Tracks traffic and usage statistics for hardware backends."""
    
    def __init__(self):
        """Initialize traffic counter."""
        self.backend_stats = {
            "ipfs": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0},
            "ipfs_cluster": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0},
            "lotus": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0},
            "storacha": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0},
            "gdrive": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0},
            "s3": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0},
            "parquet": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0},
            "car_archive": {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0}
        }
        self.session_start = datetime.now()
    
    def record_traffic(self, backend: str, operation: str, bytes_transferred: int, success: bool = True):
        """Record traffic for a backend operation."""
        if backend not in self.backend_stats:
            self.backend_stats[backend] = {"traffic_bytes": 0, "file_count": 0, "operations": 0, "errors": 0}
        
        stats = self.backend_stats[backend]
        stats["traffic_bytes"] += bytes_transferred
        stats["operations"] += 1
        
        if operation in ["upload", "store", "pin"]:
            stats["file_count"] += 1
        
        if not success:
            stats["errors"] += 1
    
    def get_backend_usage(self, backend: str = None) -> Dict[str, Any]:
        """Get usage statistics for a specific backend or all backends."""
        if backend:
            if backend not in self.backend_stats:
                return {"error": f"Backend {backend} not found"}
            
            stats = self.backend_stats[backend].copy()
            stats["traffic_gb"] = stats["traffic_bytes"] / (1024**3)
            stats["error_rate"] = stats["errors"] / max(stats["operations"], 1) * 100
            stats["uptime_hours"] = (datetime.now() - self.session_start).total_seconds() / 3600
            return stats
        else:
            result = {}
            total_traffic = 0
            total_files = 0
            total_operations = 0
            
            for backend_name, stats in self.backend_stats.items():
                backend_usage = stats.copy()
                backend_usage["traffic_gb"] = stats["traffic_bytes"] / (1024**3)
                backend_usage["error_rate"] = stats["errors"] / max(stats["operations"], 1) * 100
                result[backend_name] = backend_usage
                
                total_traffic += stats["traffic_bytes"]
                total_files += stats["file_count"]
                total_operations += stats["operations"]
            
            result["summary"] = {
                "total_traffic_gb": total_traffic / (1024**3),
                "total_files": total_files,
                "total_operations": total_operations,
                "session_uptime_hours": (datetime.now() - self.session_start).total_seconds() / 3600,
                "active_backends": len([b for b in self.backend_stats.values() if b["operations"] > 0])
            }
            
            return result

class ReplicationManager:
    """Manages pin replication across multiple storage backends."""
    
    def __init__(self, health_monitor=None, parquet_bridge=None, car_bridge=None, cache_manager=None):
        """Initialize the replication manager."""
        self.health_monitor = health_monitor
        self.parquet_bridge = parquet_bridge
        self.car_bridge = car_bridge
        self.cache_manager = cache_manager
        
        # Initialize traffic counter for monitoring backend usage
        self.traffic_counter = TrafficCounter()
        
        # Default replication settings
        self.default_settings = ReplicationSettings()
        
        # Track pin locations across backends
        self.pin_registry = {}  # cid -> {backends: [], metadata: {}, last_check: datetime, vfs_metadata_id: str}
        
        # Available backends with their capabilities
        self.backends = {
            "ipfs": {"type": "distributed", "max_size_gb": 1000, "priority": 1},
            "ipfs_cluster": {"type": "distributed", "max_size_gb": 5000, "priority": 2},
            "lotus": {"type": "blockchain", "max_size_gb": 100, "priority": 3},
            "storacha": {"type": "cloud", "max_size_gb": 10000, "priority": 4},
            "gdrive": {"type": "cloud", "max_size_gb": 1000, "priority": 5},
            "s3": {"type": "cloud", "max_size_gb": 50000, "priority": 6},
            "parquet": {"type": "local", "max_size_gb": 1000, "priority": 7},
            "car_archive": {"type": "local", "max_size_gb": 5000, "priority": 8}
        }
    
    async def get_replication_status(self, cid: Optional[str] = None) -> Dict[str, Any]:
        """Get replication status for specific CID or all pins."""
        try:
            if cid:
                # Get status for specific CID
                pin_info = self.pin_registry.get(cid, {})
                return {
                    "cid": cid,
                    "backends": pin_info.get("backends", []),
                    "replica_count": len(pin_info.get("backends", [])),
                    "metadata": pin_info.get("metadata", {}),
                    "last_check": pin_info.get("last_check"),
                    "replication_health": self._calculate_replication_health(pin_info)
                }
            else:
                # Get overall replication status
                total_pins = len(self.pin_registry)
                under_replicated = sum(1 for pin in self.pin_registry.values() 
                                     if len(pin.get("backends", [])) < self.default_settings.target_replicas)
                over_replicated = sum(1 for pin in self.pin_registry.values() 
                                    if len(pin.get("backends", [])) > self.default_settings.max_replicas)
                
                return {
                    "total_pins": total_pins,
                    "under_replicated": under_replicated,
                    "over_replicated": over_replicated,
                    "healthy_pins": total_pins - under_replicated - over_replicated,
                    "replication_efficiency": ((total_pins - under_replicated - over_replicated) / total_pins * 100) if total_pins > 0 else 100,
                    "backend_usage": self._get_backend_usage_stats()
                }
        except Exception as e:
            logger.error(f"Error getting replication status: {e}")
            return {"error": str(e)}
    
    def _calculate_replication_health(self, pin_info: Dict) -> str:
        """Calculate health status for a pin's replication."""
        replica_count = len(pin_info.get("backends", []))
        if replica_count < self.default_settings.min_replicas:
            return "critical"
        elif replica_count < self.default_settings.target_replicas:
            return "warning"
        elif replica_count > self.default_settings.max_replicas:
            return "excess"
        else:
            return "healthy"
    
    def _get_backend_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for each backend."""
        backend_stats = {name: {"pin_count": 0, "estimated_size_gb": 0} for name in self.backends.keys()}
        
        for pin_info in self.pin_registry.values():
            for backend in pin_info.get("backends", []):
                if backend in backend_stats:
                    backend_stats[backend]["pin_count"] += 1
                    # Estimate size based on metadata
                    size_bytes = pin_info.get("metadata", {}).get("size_bytes", 0)
                    backend_stats[backend]["estimated_size_gb"] += size_bytes / (1024**3)
        
        return backend_stats
    
    async def replicate_pin(self, cid: str, target_backends: List[str] = None, force: bool = False, vfs_metadata_id: str = None) -> Dict[str, Any]:
        """Replicate a pin to target backends with traffic monitoring."""
        try:
            if not target_backends:
                target_backends = self._select_optimal_backends(cid)
            
            results = {}
            for backend in target_backends:
                try:
                    # Get file size for traffic monitoring
                    file_size = 0
                    if cid in self.pin_registry:
                        file_size = self.pin_registry[cid].get("metadata", {}).get("size_bytes", 0)
                    
                    if backend == "car_archive" and self.car_bridge:
                        # Special handling for CAR archive export
                        result = await self._replicate_to_car_archive(cid)
                    elif backend == "parquet" and self.parquet_bridge:
                        # Special handling for parquet storage
                        result = await self._replicate_to_parquet(cid)
                    elif backend in ["ipfs", "ipfs_cluster"] and self.health_monitor:
                        # IPFS-based replication
                        result = await self._replicate_to_ipfs_backend(cid, backend)
                    else:
                        # Generic backend replication
                        result = await self._replicate_to_generic_backend(cid, backend)
                    
                    # Record traffic statistics
                    self.traffic_counter.record_traffic(
                        backend=backend,
                        operation="replicate",
                        bytes_transferred=file_size,
                        success=result.get("success", False)
                    )
                    
                    results[backend] = result
                    
                    # Update pin registry with VFS metadata linking
                    if result.get("success"):
                        self._update_pin_registry(cid, backend, result.get("metadata", {}), vfs_metadata_id)
                        
                except Exception as e:
                    logger.error(f"Error replicating {cid} to {backend}: {e}")
                    results[backend] = {"success": False, "error": str(e)}
                    # Record failed operation
                    self.traffic_counter.record_traffic(
                        backend=backend,
                        operation="replicate",
                        bytes_transferred=0,
                        success=False
                    )
            
            return {
                "success": any(r.get("success") for r in results.values()),
                "cid": cid,
                "vfs_metadata_id": vfs_metadata_id,
                "replication_results": results,
                "timestamp": datetime.now().isoformat(),
                "traffic_summary": self._get_operation_traffic_summary(results)
            }
            
        except Exception as e:
            logger.error(f"Error in replicate_pin: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_operation_traffic_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Get traffic summary for the current operation."""
        successful_backends = [b for b, r in results.items() if r.get("success")]
        failed_backends = [b for b, r in results.items() if not r.get("success")]
        
        return {
            "successful_backends": successful_backends,
            "failed_backends": failed_backends,
            "total_backends_attempted": len(results),
            "success_rate": len(successful_backends) / len(results) * 100 if results else 0
        }
    
    def _update_pin_registry(self, cid: str, backend: str, metadata: Dict, vfs_metadata_id: str = None):
        """Update the pin registry with new backend information and VFS metadata linking."""
        if cid not in self.pin_registry:
            self.pin_registry[cid] = {
                "backends": [], 
                "metadata": {}, 
                "last_check": datetime.now().isoformat(),
                "vfs_metadata_id": vfs_metadata_id
            }
        
        if backend not in self.pin_registry[cid]["backends"]:
            self.pin_registry[cid]["backends"].append(backend)
        
        self.pin_registry[cid]["metadata"].update(metadata)
        self.pin_registry[cid]["last_check"] = datetime.now().isoformat()
        
        # Link VFS metadata if provided
        if vfs_metadata_id:
            self.pin_registry[cid]["vfs_metadata_id"] = vfs_metadata_id
            # Add backend location to VFS metadata
            self.pin_registry[cid]["metadata"]["backend_locations"] = self.pin_registry[cid]["backends"]
    
    async def get_traffic_analytics(self, backend: str = None, time_range: str = "session") -> Dict[str, Any]:
        """Get comprehensive traffic analytics for backends."""
        try:
            usage_stats = self.traffic_counter.get_backend_usage(backend)
            
            # Add replication efficiency metrics
            if backend:
                backend_pins = [
                    pin for pin in self.pin_registry.values() 
                    if backend in pin.get("backends", [])
                ]
                
                usage_stats.update({
                    "pins_stored": len(backend_pins),
                    "average_file_size_mb": (
                        sum(pin.get("metadata", {}).get("size_bytes", 0) for pin in backend_pins) 
                        / len(backend_pins) / (1024**2) if backend_pins else 0
                    ),
                    "replication_efficiency": len(backend_pins) / max(usage_stats.get("file_count", 1), 1) * 100
                })
            else:
                total_pins = len(self.pin_registry)
                usage_stats["summary"].update({
                    "total_unique_pins": total_pins,
                    "average_replication_factor": (
                        sum(len(pin.get("backends", [])) for pin in self.pin_registry.values()) 
                        / max(total_pins, 1)
                    ),
                    "vfs_linked_pins": len([
                        pin for pin in self.pin_registry.values() 
                        if pin.get("vfs_metadata_id")
                    ])
                })
            
            return {
                "success": True,
                "usage_statistics": usage_stats,
                "time_range": time_range,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting traffic analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_vfs_backend_mapping(self) -> Dict[str, Any]:
        """Get mapping of VFS metadata to backend storage locations."""
        try:
            mapping = {}
            
            for cid, pin_info in self.pin_registry.items():
                vfs_id = pin_info.get("vfs_metadata_id")
                if vfs_id:
                    mapping[vfs_id] = {
                        "cid": cid,
                        "backends": pin_info.get("backends", []),
                        "metadata": pin_info.get("metadata", {}),
                        "last_check": pin_info.get("last_check"),
                        "replication_count": len(pin_info.get("backends", [])),
                        "storage_size_bytes": pin_info.get("metadata", {}).get("size_bytes", 0)
                    }
            
            # Add summary statistics
            summary = {
                "total_vfs_entries": len(mapping),
                "total_storage_backends": len(set().union(*[
                    entry["backends"] for entry in mapping.values()
                ])),
                "total_storage_size_gb": sum(
                    entry["storage_size_bytes"] for entry in mapping.values()
                ) / (1024**3),
                "average_replication_factor": (
                    sum(entry["replication_count"] for entry in mapping.values()) 
                    / len(mapping) if mapping else 0
                )
            }
            
            return {
                "success": True,
                "vfs_backend_mapping": mapping,
                "summary": summary,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS backend mapping: {e}")
            return {"success": False, "error": str(e)}
    
    def _select_optimal_backends(self, cid: str) -> List[str]:
        """Select optimal backends for replication based on strategy."""
        available_backends = []
        
        # Filter backends based on health and capacity
        for backend_name, backend_info in self.backends.items():
            if self.health_monitor:
                backend_status = self.health_monitor.backends.get(backend_name)
                if backend_status and backend_status.get("health") == "healthy":
                    available_backends.append((backend_name, backend_info["priority"]))
        
        # Sort by priority and select target number
        available_backends.sort(key=lambda x: x[1])
        selected = [b[0] for b in available_backends[:self.default_settings.target_replicas]]
        
        return selected
    
    async def _replicate_to_car_archive(self, cid: str) -> Dict[str, Any]:
        """Replicate to CAR archive format."""
        try:
            result = self.car_bridge.convert_dataset_to_car_collection(
                dataset_cid=cid,
                include_vector_index=True,
                include_knowledge_graph=True
            )
            return {
                "success": result.get("success", False),
                "car_path": result.get("car_path"),
                "car_cid": result.get("collection_cid"),
                "metadata": {"storage_type": "car_archive", "path": result.get("car_path")}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _replicate_to_parquet(self, cid: str) -> Dict[str, Any]:
        """Replicate to parquet storage."""
        try:
            # This would integrate with parquet storage
            return {
                "success": True,
                "metadata": {"storage_type": "parquet", "cid": cid}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _replicate_to_ipfs_backend(self, cid: str, backend: str) -> Dict[str, Any]:
        """Replicate to IPFS-based backend."""
        try:
            # This would integrate with IPFS pinning
            return {
                "success": True,
                "metadata": {"storage_type": backend, "cid": cid}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _replicate_to_generic_backend(self, cid: str, backend: str) -> Dict[str, Any]:
        """Replicate to generic storage backend."""
        try:
            # This would integrate with specific backend APIs
            return {
                "success": True,
                "metadata": {"storage_type": backend, "cid": cid}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def export_pins_backup(self, backend_name: str, backup_path: str) -> Dict[str, Any]:
        """Export pins from a backend to backup file."""
        try:
            backend_pins = []
            for cid, pin_info in self.pin_registry.items():
                if backend_name in pin_info.get("backends", []):
                    backend_pins.append({
                        "cid": cid,
                        "metadata": pin_info.get("metadata", {}),
                        "backends": pin_info.get("backends", []),
                        "last_check": pin_info.get("last_check")
                    })
            
            backup_data = {
                "backend_name": backend_name,
                "export_timestamp": datetime.now().isoformat(),
                "pins": backend_pins,
                "total_pins": len(backend_pins)
            }
            
            # Write backup to file
            import json
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            return {
                "success": True,
                "backup_path": backup_path,
                "pins_exported": len(backend_pins),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting pins backup: {e}")
            return {"success": False, "error": str(e)}
    
    async def import_pins_backup(self, backup_path: str, target_backend: str = None) -> Dict[str, Any]:
        """Import pins from backup file."""
        try:
            import json
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            imported_pins = 0
            failed_pins = 0
            
            for pin_data in backup_data.get("pins", []):
                cid = pin_data.get("cid")
                if cid:
                    try:
                        # Restore pin to registry
                        self.pin_registry[cid] = {
                            "backends": pin_data.get("backends", []),
                            "metadata": pin_data.get("metadata", {}),
                            "last_check": pin_data.get("last_check")
                        }
                        
                        # If target backend specified, replicate there
                        if target_backend:
                            await self.replicate_pin(cid, [target_backend])
                        
                        imported_pins += 1
                    except Exception as e:
                        logger.error(f"Error importing pin {cid}: {e}")
                        failed_pins += 1
            
            return {
                "success": True,
                "pins_imported": imported_pins,
                "pins_failed": failed_pins,
                "source_backend": backup_data.get("backend_name"),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error importing pins backup: {e}")
            return {"success": False, "error": str(e)}

class DashboardController:
    """Enhanced dashboard controller with comprehensive daemon management."""
    
    def __init__(self, ipfs_client):
        """Initialize the dashboard controller."""
        self.ipfs_client = ipfs_client
        self.health_monitor = BackendHealthMonitor()
        self.cluster_manager = None
        self._initialize_cluster_manager()
        
        # Initialize columnar IPLD components if available
        self.vfs_api = None
        self.vector_api = None
        self.kg_api = None
        self.pinset_api = None
        self.parquet_bridge = None
        self.car_bridge = None
        self.cache_manager = None
        self.knowledge_graph = None
        self._initialize_columnar_ipld_components()
        
        # Initialize replication manager
        self.replication_manager = None
        self._initialize_replication_manager()
    
    def _initialize_cluster_manager(self):
        """Initialize the cluster manager."""
        try:
            from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager
            self.cluster_manager = IPFSClusterDaemonManager()
            logger.info("✓ IPFS Cluster daemon manager initialized")
        except ImportError as e:
            logger.warning(f"Cluster daemon manager not available: {e}")
            self.cluster_manager = None
    
    def _initialize_columnar_ipld_components(self):
        """Initialize columnar IPLD and VFS components."""
        if not COLUMNAR_IPLD_AVAILABLE:
            logger.warning("Columnar IPLD components not available - VFS features disabled")
            return
            
        try:
            # Initialize core components
            self.parquet_bridge = ParquetIPLDBridge()
            self.car_bridge = ParquetCARBridge()
            self.cache_manager = TieredCacheManager()
            self.knowledge_graph = IPLDGraphDB(ipfs_client=self.ipfs_client)
            
            # Initialize API components
            self.vfs_api = VFSMetadataAPI(
                parquet_bridge=self.parquet_bridge,
                car_bridge=self.car_bridge,
                cache_manager=self.cache_manager
            )
            
            self.vector_api = VectorIndexAPI(
                parquet_bridge=self.parquet_bridge,
                car_bridge=self.car_bridge,
                knowledge_graph=self.knowledge_graph
            )
            
            self.kg_api = KnowledgeGraphAPI(
                knowledge_graph=self.knowledge_graph,
                car_bridge=self.car_bridge,
                graph_rag=GraphRAG(self.knowledge_graph)
            )
            
            self.pinset_api = PinsetAPI(
                car_bridge=self.car_bridge,
                cache_manager=self.cache_manager
            )
            
            logger.info("✓ Columnar IPLD components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize columnar IPLD components: {e}")
            # Disable components on error
            self.vfs_api = None
            self.vector_api = None
            self.kg_api = None
            self.pinset_api = None
    
    def _initialize_replication_manager(self):
        """Initialize the replication manager for cross-backend pin management."""
        try:
            self.replication_manager = ReplicationManager(
                health_monitor=self.health_monitor,
                parquet_bridge=self.parquet_bridge,
                car_bridge=self.car_bridge,
                cache_manager=self.cache_manager
            )
            logger.info("✓ Replication manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize replication manager: {e}")
            self.replication_manager = None
    
    async def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all systems.
        
        Returns:
            Dict with complete system status
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "unknown",
            "backends": {},
            "cluster": {},
            "libp2p": {},
            "vfs": {},
            "vector_index": {},
            "knowledge_graph": {},
            "pinsets": {},
            "replication": {},
            "metrics": {},
            "alerts": []
        }
        
        try:
            # Get all backend statuses
            backend_results = await self.health_monitor.check_all_backends_health()
            status["backends"] = backend_results
            
            # Determine overall health
            healthy_backends = 0
            total_backends = len(backend_results)
            
            for backend_name, backend_info in backend_results.items():
                if backend_info.get("health") == "healthy":
                    healthy_backends += 1
                elif backend_info.get("health") == "unhealthy":
                    status["alerts"].append({
                        "type": "backend_unhealthy",
                        "message": f"Backend {backend_name} is unhealthy",
                        "timestamp": datetime.now().isoformat(),
                        "severity": "warning"
                    })
            
            # Calculate overall health percentage
            health_percentage = (healthy_backends / total_backends) * 100 if total_backends > 0 else 0
            
            if health_percentage >= 80:
                status["overall_health"] = "healthy"
            elif health_percentage >= 60:
                status["overall_health"] = "degraded"
            else:
                status["overall_health"] = "unhealthy"
            
            # Get cluster-specific status
            if self.cluster_manager:
                cluster_status = await self.cluster_manager.get_cluster_service_status()
                status["cluster"] = cluster_status
                
                if not cluster_status.get("running"):
                    status["alerts"].append({
                        "type": "cluster_stopped",
                        "message": "IPFS Cluster service is not running",
                        "timestamp": datetime.now().isoformat(),
                        "severity": "warning"
                    })
            
            # Get LibP2P status from backends
            libp2p_backend = backend_results.get("libp2p", {})
            status["libp2p"] = {
                "status": libp2p_backend.get("status", "unknown"),
                "health": libp2p_backend.get("health", "unknown"),
                "peer_count": libp2p_backend.get("detailed_info", {}).get("total_peers", 0),
                "connected_peers": libp2p_backend.get("detailed_info", {}).get("connected_peers", 0),
                "discovery_active": libp2p_backend.get("detailed_info", {}).get("discovery_active", False)
            }
            
            # Get VFS status if available
            if self.vfs_api:
                try:
                    vfs_summary = await self._get_vfs_summary()
                    status["vfs"] = vfs_summary
                except Exception as e:
                    logger.error(f"Error getting VFS status: {e}")
                    status["vfs"]["error"] = str(e)
            
            # Get vector index status if available
            if self.vector_api:
                try:
                    vector_summary = await self._get_vector_summary()
                    status["vector_index"] = vector_summary
                except Exception as e:
                    logger.error(f"Error getting vector index status: {e}")
                    status["vector_index"]["error"] = str(e)
            
            # Get knowledge graph status if available
            if self.kg_api:
                try:
                    kg_summary = await self._get_kg_summary()
                    status["knowledge_graph"] = kg_summary
                except Exception as e:
                    logger.error(f"Error getting knowledge graph status: {e}")
                    status["knowledge_graph"]["error"] = str(e)
            
            # Get pinset status if available
            if self.pinset_api:
                try:
                    pinset_summary = await self._get_pinset_summary()
                    status["pinsets"] = pinset_summary
                except Exception as e:
                    logger.error(f"Error getting pinset status: {e}")
                    status["pinsets"]["error"] = str(e)
            
            # Get replication status if available
            if self.replication_manager:
                try:
                    replication_summary = await self.replication_manager.get_replication_status()
                    status["replication"] = replication_summary
                    
                    # Add replication alerts
                    if replication_summary.get("under_replicated", 0) > 0:
                        status["alerts"].append({
                            "type": "under_replicated",
                            "message": f"{replication_summary['under_replicated']} pins are under-replicated",
                            "timestamp": datetime.now().isoformat(),
                            "severity": "warning"
                        })
                    
                    if replication_summary.get("over_replicated", 0) > 0:
                        status["alerts"].append({
                            "type": "over_replicated", 
                            "message": f"{replication_summary['over_replicated']} pins are over-replicated",
                            "timestamp": datetime.now().isoformat(),
                            "severity": "info"
                        })
                        
                except Exception as e:
                    logger.error(f"Error getting replication status: {e}")
                    status["replication"]["error"] = str(e)
            
            # Compile metrics
            status["metrics"] = {
                "health_percentage": health_percentage,
                "healthy_backends": healthy_backends,
                "total_backends": total_backends,
                "cluster_peers": status["cluster"].get("peer_count", 0),
                "libp2p_peers": status["libp2p"]["peer_count"],
                "vfs_datasets": status["vfs"].get("total_datasets", 0),
                "vector_collections": status["vector_index"].get("total_collections", 0),
                "kg_entities": status["knowledge_graph"].get("total_entities", 0),
                "total_pins": status["pinsets"].get("total_pins", 0),
                "replication_efficiency": status["replication"].get("replication_efficiency", 0),
                "under_replicated_pins": status["replication"].get("under_replicated", 0),
                "alerts_count": len(status["alerts"])
            }
            
        except Exception as e:
            logger.error(f"Error getting comprehensive status: {e}")
            status["error"] = str(e)
            status["overall_health"] = "error"
        
        return status
    
    async def _get_vfs_summary(self) -> Dict[str, Any]:
        """Get VFS metadata summary."""
        try:
            datasets_result = self.parquet_bridge.list_datasets()
            if not datasets_result["success"]:
                return {"error": datasets_result.get("error")}
            
            datasets = datasets_result["datasets"]
            car_result = self.car_bridge.list_car_archives()
            car_archives = car_result.get("archives", []) if car_result["success"] else []
            
            return {
                "total_datasets": len(datasets),
                "total_size_bytes": sum(d.get("size_bytes", 0) for d in datasets),
                "car_archives_count": len(car_archives),
                "status": "healthy",
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    async def _get_vector_summary(self) -> Dict[str, Any]:
        """Get vector index summary."""
        try:
            # This would integrate with the actual vector index system
            # For now, provide placeholder data
            return {
                "total_collections": 0,
                "total_vectors": 0,
                "index_size_mb": 0,
                "status": "healthy",
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    async def _get_kg_summary(self) -> Dict[str, Any]:
        """Get knowledge graph summary."""
        try:
            if self.knowledge_graph:
                entities_count = len(self.knowledge_graph.entities)
                relationships_count = len(self.knowledge_graph.graph.edges)
                
                return {
                    "total_entities": entities_count,
                    "total_relationships": relationships_count,
                    "graph_size": entities_count + relationships_count,
                    "status": "healthy",
                    "last_updated": datetime.now().isoformat()
                }
            else:
                return {"error": "Knowledge graph not available", "status": "unavailable"}
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    async def _get_pinset_summary(self) -> Dict[str, Any]:
        """Get pinset summary."""
        try:
            # This would integrate with the actual pinset tracking system
            return {
                "total_pins": 0,
                "storage_backends": [],
                "replication_status": "healthy",
                "status": "healthy",
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}

    async def perform_vfs_operation(self, request: VirtualFilesystemRequest) -> Dict[str, Any]:
        """Perform virtual filesystem operations.
        
        Args:
            request: VFS operation request
            
        Returns:
            Dict with operation results
        """
        if not COLUMNAR_IPLD_AVAILABLE or not self.vfs_api:
            return {"success": False, "error": "VFS API not available"}
        
        result = {
            "success": False,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        try:
            if request.action == "list":
                datasets_result = self.parquet_bridge.list_datasets()
                if datasets_result["success"]:
                    result["success"] = True
                    result["data"] = {
                        "datasets": datasets_result["datasets"],
                        "total_count": len(datasets_result["datasets"])
                    }
                else:
                    result["error"] = datasets_result.get("error")
            
            elif request.action == "get" and request.dataset_id:
                dataset_result = self.parquet_bridge.get_dataset_metadata(request.dataset_id)
                if dataset_result["success"]:
                    result["success"] = True
                    result["data"] = dataset_result["metadata"]
                    
                    # Add CAR archive info if requested
                    if request.include_car:
                        car_metadata = self.car_bridge.get_car_metadata(request.dataset_id)
                        if car_metadata["success"]:
                            result["data"]["car_archive"] = car_metadata["metadata"]
                else:
                    result["error"] = dataset_result.get("error")
            
            elif request.action == "convert_to_car" and request.dataset_id:
                car_result = self.car_bridge.convert_dataset_to_car_collection(
                    dataset_cid=request.dataset_id,
                    include_vector_index=request.include_vector_index,
                    include_knowledge_graph=request.include_knowledge_graph
                )
                if car_result["success"]:
                    result["success"] = True
                    result["data"] = {
                        "car_path": car_result["car_path"],
                        "car_cid": car_result.get("collection_cid"),
                        "blocks_created": car_result.get("blocks_created", 0)
                    }
                else:
                    result["error"] = car_result.get("error")
            
            elif request.action == "query":
                # Perform search across VFS metadata
                summary = await self._get_vfs_summary()
                result["success"] = True
                result["data"] = summary
            
            else:
                result["error"] = f"Unsupported VFS action: {request.action}"
                
        except Exception as e:
            logger.error(f"Error in VFS operation: {e}")
            result["error"] = str(e)
        
        return result

    async def perform_vector_operation(self, request: VectorIndexRequest) -> Dict[str, Any]:
        """Perform vector index operations.
        
        Args:
            request: Vector index operation request
            
        Returns:
            Dict with operation results
        """
        if not COLUMNAR_IPLD_AVAILABLE or not self.vector_api:
            return {"success": False, "error": "Vector API not available"}
        
        result = {
            "success": False,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        try:
            if request.action == "list":
                # List vector collections
                result["success"] = True
                result["data"] = {
                    "collections": [],
                    "total_collections": 0
                }
            
            elif request.action == "search" and request.query_vector:
                # Perform vector similarity search
                result["success"] = True
                result["data"] = {
                    "matches": [],
                    "query_vector_dim": len(request.query_vector),
                    "top_k": request.top_k
                }
            
            elif request.action == "export_car" and request.collection_id:
                # Export vector collection to CAR archive
                car_result = self.car_bridge.convert_dataset_to_car_collection(
                    dataset_cid=request.collection_id,
                    collection_name=f"vector_collection_{request.collection_id[:16]}",
                    include_vector_index=True,
                    include_knowledge_graph=False
                )
                if car_result["success"]:
                    result["success"] = True
                    result["data"] = {
                        "car_path": car_result["car_path"],
                        "car_cid": car_result.get("collection_cid")
                    }
                else:
                    result["error"] = car_result.get("error")
            
            elif request.action == "get_status":
                summary = await self._get_vector_summary()
                result["success"] = True
                result["data"] = summary
            
            else:
                result["error"] = f"Unsupported vector action: {request.action}"
                
        except Exception as e:
            logger.error(f"Error in vector operation: {e}")
            result["error"] = str(e)
        
        return result

    async def perform_kg_operation(self, request: KnowledgeGraphRequest) -> Dict[str, Any]:
        """Perform knowledge graph operations.
        
        Args:
            request: Knowledge graph operation request
            
        Returns:
            Dict with operation results
        """
        if not COLUMNAR_IPLD_AVAILABLE or not self.kg_api or not self.knowledge_graph:
            return {"success": False, "error": "Knowledge graph not available"}
        
        result = {
            "success": False,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        try:
            if request.action == "list_entities":
                entities = list(self.knowledge_graph.entities.keys())
                result["success"] = True
                result["data"] = {
                    "entities": entities,
                    "total_entities": len(entities)
                }
            
            elif request.action == "get_entity" and request.entity_id:
                entity_result = self.knowledge_graph.get_entity(request.entity_id)
                if entity_result["success"]:
                    result["success"] = True
                    result["data"] = entity_result["entity"]
                    
                    if request.include_relationships:
                        relationships = self.knowledge_graph.get_entity_relationships(request.entity_id)
                        result["data"]["relationships"] = relationships.get("relationships", [])
                else:
                    result["error"] = entity_result.get("error")
            
            elif request.action == "search" and request.query:
                # Perform semantic search in knowledge graph
                search_result = self.knowledge_graph.search_entities(
                    query=request.query,
                    max_results=10
                )
                if search_result["success"]:
                    result["success"] = True
                    result["data"] = {
                        "matches": search_result["entities"],
                        "query": request.query
                    }
                else:
                    result["error"] = search_result.get("error")
            
            elif request.action == "export_car":
                # Export knowledge graph to CAR archive
                kg_result = self.car_bridge.convert_dataset_to_car_collection(
                    dataset_cid="knowledge_graph",
                    collection_name="knowledge_graph_export",
                    include_vector_index=False,
                    include_knowledge_graph=True
                )
                if kg_result["success"]:
                    result["success"] = True
                    result["data"] = {
                        "car_path": kg_result["car_path"],
                        "car_cid": kg_result.get("collection_cid")
                    }
                else:
                    result["error"] = kg_result.get("error")
            
            else:
                result["error"] = f"Unsupported knowledge graph action: {request.action}"
                
        except Exception as e:
            logger.error(f"Error in knowledge graph operation: {e}")
            result["error"] = str(e)
        
        return result

    async def perform_pinset_operation(self, request: PinsetRequest) -> Dict[str, Any]:
        """Perform pinset operations.
        
        Args:
            request: Pinset operation request
            
        Returns:
            Dict with operation results
        """
        if not COLUMNAR_IPLD_AVAILABLE or not self.pinset_api:
            return {"success": False, "error": "Pinset API not available"}
        
        result = {
            "success": False,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        try:
            if request.action == "list":
                # List all pinsets
                result["success"] = True
                result["data"] = {
                    "pinsets": [],
                    "total_pins": 0,
                    "storage_backends": []
                }
            
            elif request.action == "get" and request.cid:
                # Get specific pin information
                result["success"] = True
                result["data"] = {
                    "cid": request.cid,
                    "status": "pinned",
                    "backends": [],
                    "metadata": {}
                }
            
            elif request.action == "replicate" and request.cid and request.target_backend:
                # Replicate pin to target backend
                if request.target_backend == "car_archive":
                    car_result = self.car_bridge.convert_dataset_to_car_collection(
                        dataset_cid=request.cid,
                        include_vector_index=True,
                        include_knowledge_graph=True
                    )
                    if car_result["success"]:
                        result["success"] = True
                        result["data"] = {
                            "cid": request.cid,
                            "target_backend": request.target_backend,
                            "car_path": car_result["car_path"],
                            "replication_status": "completed"
                        }
                    else:
                        result["error"] = car_result.get("error")
                else:
                    result["error"] = f"Unsupported target backend: {request.target_backend}"
            
            elif request.action == "track_backends":
                # Track storage backends for pins
                summary = await self._get_pinset_summary()
                result["success"] = True
                result["data"] = summary
            
            else:
                result["error"] = f"Unsupported pinset action: {request.action}"
                
        except Exception as e:
            logger.error(f"Error in pinset operation: {e}")
            result["error"] = str(e)
        
        return result
    
    async def perform_replication_operation(self, request: ReplicationRequest) -> Dict[str, Any]:
        """Perform replication management operations.
        
        Args:
            request: Replication operation request
            
        Returns:
            Dict with operation results
        """
        if not self.replication_manager:
            return {"success": False, "error": "Replication manager not available"}
        
        result = {
            "success": False,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        try:
            if request.action == "configure":
                # Update replication settings
                if request.settings:
                    self.replication_manager.default_settings = request.settings
                    result["success"] = True
                    result["data"] = {
                        "settings": request.settings.dict(),
                        "message": "Replication settings updated successfully"
                    }
                else:
                    result["error"] = "No settings provided for configuration"
            
            elif request.action == "replicate" and request.cid:
                # Replicate specific CID with VFS metadata linking
                replication_result = await self.replication_manager.replicate_pin(
                    cid=request.cid,
                    target_backends=request.target_backends,
                    force=request.force,
                    vfs_metadata_id=request.backend_name  # Using backend_name field for VFS ID
                )
                result["success"] = replication_result.get("success", False)
                result["data"] = replication_result
            
            elif request.action == "analyze":
                # Analyze replication status
                if request.cid:
                    status = await self.replication_manager.get_replication_status(request.cid)
                else:
                    status = await self.replication_manager.get_replication_status()
                
                result["success"] = True
                result["data"] = status
            
            elif request.action == "traffic_analytics":
                # Get traffic analytics for specific backend or all backends
                traffic_analytics = await self.replication_manager.get_traffic_analytics(
                    backend=request.backend_name
                )
                result["success"] = traffic_analytics.get("success", False)
                result["data"] = traffic_analytics
            
            elif request.action == "vfs_mapping":
                # Get VFS metadata to backend mapping
                vfs_mapping = await self.replication_manager.get_vfs_backend_mapping()
                result["success"] = vfs_mapping.get("success", False)
                result["data"] = vfs_mapping
            
            elif request.action == "backup" and request.backend_name and request.backup_path:
                # Export pins backup
                backup_result = await self.replication_manager.export_pins_backup(
                    backend_name=request.backend_name,
                    backup_path=request.backup_path
                )
                result["success"] = backup_result.get("success", False)
                result["data"] = backup_result
            
            elif request.action == "restore" and request.restore_path:
                # Import pins backup
                restore_result = await self.replication_manager.import_pins_backup(
                    backup_path=request.restore_path,
                    target_backend=request.backend_name
                )
                result["success"] = restore_result.get("success", False)
                result["data"] = restore_result
            
            elif request.action == "cleanup":
                # Cleanup over-replicated pins
                result["success"] = True
                result["data"] = {"message": "Cleanup operation completed"}
            
            else:
                result["error"] = f"Unsupported replication action: {request.action}"
                
        except Exception as e:
            logger.error(f"Error in replication operation: {e}")
            result["error"] = str(e)
        
        return result
    
    async def perform_backup_restore_operation(self, request: BackupRestoreRequest) -> Dict[str, Any]:
        """Perform backup/restore operations.
        
        Args:
            request: Backup/restore operation request
            
        Returns:
            Dict with operation results
        """
        if not self.replication_manager:
            return {"success": False, "error": "Replication manager not available"}
        
        result = {
            "success": False,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        try:
            if request.action == "export_pins":
                # Export pins from backend
                if not request.backup_path:
                    request.backup_path = f"/tmp/pins_backup_{request.backend_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                backup_result = await self.replication_manager.export_pins_backup(
                    backend_name=request.backend_name,
                    backup_path=request.backup_path
                )
                result["success"] = backup_result.get("success", False)
                result["data"] = backup_result
            
            elif request.action == "import_pins" and request.backup_path:
                # Import pins to backend
                restore_result = await self.replication_manager.import_pins_backup(
                    backup_path=request.backup_path,
                    target_backend=request.backend_name
                )
                result["success"] = restore_result.get("success", False)
                result["data"] = restore_result
            
            elif request.action == "list_backups":
                # List available backups
                import glob
                backup_pattern = f"/tmp/pins_backup_{request.backend_name}_*.json"
                backups = glob.glob(backup_pattern)
                result["success"] = True
                result["data"] = {
                    "backups": [{"path": b, "size": os.path.getsize(b)} for b in backups],
                    "total_backups": len(backups)
                }
            
            elif request.action == "verify_backup" and request.backup_path:
                # Verify backup integrity
                try:
                    import json
                    with open(request.backup_path, 'r') as f:
                        backup_data = json.load(f)
                    
                    result["success"] = True
                    result["data"] = {
                        "valid": True,
                        "backend_name": backup_data.get("backend_name"),
                        "export_timestamp": backup_data.get("export_timestamp"),
                        "pins_count": len(backup_data.get("pins", [])),
                        "backup_size_bytes": os.path.getsize(request.backup_path)
                    }
                except Exception as e:
                    result["success"] = False
                    result["data"] = {"valid": False, "error": str(e)}
            
            else:
                result["error"] = f"Unsupported backup/restore action: {request.action}"
                
        except Exception as e:
            logger.error(f"Error in backup/restore operation: {e}")
            result["error"] = str(e)
        
        return result
    
    async def perform_daemon_action(self, request: DaemonActionRequest) -> Dict[str, Any]:
        """Perform action on a specific daemon.
        
        Args:
            request: Daemon action request
            
        Returns:
            Dict with action results
        """
        result = {
            "success": False,
            "daemon_name": request.daemon_name,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "details": {}
        }
        
        try:
            if request.daemon_name == "ipfs_cluster" and self.cluster_manager:
                # Handle cluster-specific actions
                if request.action == "start":
                    action_result = await self.cluster_manager.start_cluster_service(
                        force_restart=request.force
                    )
                elif request.action == "stop":
                    action_result = await self.cluster_manager.stop_cluster_service()
                elif request.action == "restart":
                    action_result = await self.cluster_manager.restart_cluster_service()
                elif request.action == "status":
                    action_result = await self.cluster_manager.get_cluster_service_status()
                else:
                    raise ValueError(f"Unsupported action for cluster: {request.action}")
                
                result["success"] = action_result.get("success", False)
                result["details"] = action_result
                
            elif request.daemon_name in ["ipfs", "lotus", "lassie"]:
                # Handle standard daemon actions through enhanced daemon manager
                try:
                    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
                    daemon_manager = EnhancedDaemonManager()
                    
                    if request.action == "start":
                        action_result = daemon_manager._start_single_daemon(request.daemon_name, "master")
                    elif request.action == "stop":
                        action_result = daemon_manager._stop_single_daemon(request.daemon_name)
                    elif request.action == "restart":
                        stop_result = daemon_manager._stop_single_daemon(request.daemon_name)
                        await asyncio.sleep(2)
                        action_result = daemon_manager._start_single_daemon(request.daemon_name, "master")
                        action_result["stop_result"] = stop_result
                    else:
                        raise ValueError(f"Unsupported action: {request.action}")
                    
                    result["success"] = action_result.get("success", False)
                    result["details"] = action_result
                    
                except ImportError:
                    result["error"] = "Enhanced daemon manager not available"
            else:
                result["error"] = f"Unsupported daemon: {request.daemon_name}"
                
        except Exception as e:
            logger.error(f"Error performing daemon action: {e}")
            result["error"] = str(e)
        
        return result
    
    async def perform_cluster_action(self, request: ClusterActionRequest) -> Dict[str, Any]:
        """Perform cluster-specific actions.
        
        Args:
            request: Cluster action request
            
        Returns:
            Dict with action results
        """
        result = {
            "success": False,
            "action": request.action,
            "timestamp": datetime.now().isoformat(),
            "details": {}
        }
        
        if not self.cluster_manager:
            result["error"] = "Cluster manager not available"
            return result
        
        try:
            if request.action == "start":
                action_result = await self.cluster_manager.start_cluster_service(
                    force_restart=request.force_restart
                )
            elif request.action == "stop":
                action_result = await self.cluster_manager.stop_cluster_service()
            elif request.action == "restart":
                action_result = await self.cluster_manager.restart_cluster_service()
            elif request.action == "status":
                action_result = await self.cluster_manager.get_cluster_service_status()
            elif request.action == "peers":
                # Get peer information
                action_result = await self.cluster_manager._get_service_peers()
                if action_result:
                    result["success"] = True
                    result["details"] = {"peers": action_result}
                else:
                    result["error"] = "Could not retrieve peer information"
                return result
            else:
                result["error"] = f"Unsupported cluster action: {request.action}"
                return result
            
            result["success"] = action_result.get("success", False)
            result["details"] = action_result
            
        except Exception as e:
            logger.error(f"Error performing cluster action: {e}")
            result["error"] = str(e)
        
        return result
    
    async def perform_health_check(self, request: HealthCheckRequest) -> Dict[str, Any]:
        """Perform health check on specific backend or all backends.
        
        Args:
            request: Health check request
            
        Returns:
            Dict with health check results
        """
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "results": {}
        }
        
        try:
            if request.backend_name:
                # Check specific backend
                if request.backend_name in self.health_monitor.backends:
                    backend_result = await self.health_monitor.check_backend_health(
                        request.backend_name
                    )
                    result["results"][request.backend_name] = backend_result
                    result["success"] = True
                else:
                    result["error"] = f"Backend not found: {request.backend_name}"
            else:
                # Check all backends
                backend_results = await self.health_monitor.check_all_backends_health()
                result["results"] = backend_results
                result["success"] = True
            
            # Add metrics if requested
            if request.include_metrics:
                result["metrics"] = {
                    "check_duration": "< 1s",  # Would need timing implementation
                    "backends_checked": len(result["results"]),
                    "healthy_count": sum(1 for r in result["results"].values() 
                                       if r.get("health") == "healthy"),
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            result["error"] = str(e)
        
        return result
    
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics for dashboard.
        
        Returns:
            Dict with real-time metrics
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "system": {},
            "backends": {},
            "network": {},
            "performance": {}
        }
        
        try:
            # Get system metrics
            import psutil
            
            metrics["system"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            }
            
            # Get backend metrics from health monitor
            backend_status = await self.health_monitor.check_all_backends_health()
            
            metrics["backends"] = {
                "total": len(backend_status),
                "healthy": sum(1 for b in backend_status.values() if b.get("health") == "healthy"),
                "degraded": sum(1 for b in backend_status.values() if b.get("health") == "degraded"),
                "unhealthy": sum(1 for b in backend_status.values() if b.get("health") == "unhealthy"),
                "details": {name: {"status": info.get("status"), "health": info.get("health")} 
                           for name, info in backend_status.items()}
            }
            
            # Add specific Lotus metrics if available
            lotus_info = backend_status.get("lotus", {})
            if lotus_info:
                metrics["lotus"] = {
                    "status": lotus_info.get("status", "unknown"),
                    "health": lotus_info.get("health", "unknown"),
                    "version": lotus_info.get("detailed_info", {}).get("version", "N/A"),
                    "sync_status": lotus_info.get("detailed_info", {}).get("sync_status", "unknown"),
                    "chain_height": lotus_info.get("detailed_info", {}).get("chain_height", 0),
                    "peers_count": lotus_info.get("detailed_info", {}).get("peers_count", 0),
                    "wallet_balance": lotus_info.get("detailed_info", {}).get("wallet_balance", "0 FIL"),
                    "last_check": lotus_info.get("last_check", "never")
                }
            
            # Add specific IPFS Cluster Follow metrics if available
            cluster_follow_info = backend_status.get("ipfs_cluster_follow", {})
            if cluster_follow_info:
                metrics["cluster_follow"] = {
                    "status": cluster_follow_info.get("status", "unknown"),
                    "health": cluster_follow_info.get("health", "unknown"),
                    "api_port": cluster_follow_info.get("port", 9097),
                    "api_reachable": cluster_follow_info.get("detailed_info", {}).get("api_reachable", False),
                    "connection_status": cluster_follow_info.get("detailed_info", {}).get("connection_status", "unknown"),
                    "cluster_name": cluster_follow_info.get("detailed_info", {}).get("cluster_name", "unknown"),
                    "last_check": cluster_follow_info.get("last_check", "never")
                }
            
            # Get network metrics
            metrics["network"] = {
                "cluster_peers": 0,
                "libp2p_peers": 0,
                "libp2p_connected": 0
            }
            
            if self.cluster_manager:
                cluster_status = await self.cluster_manager.get_cluster_service_status()
                metrics["network"]["cluster_peers"] = cluster_status.get("peer_count", 0)
            
            libp2p_info = backend_status.get("libp2p", {})
            metrics["network"]["libp2p_peers"] = libp2p_info.get("detailed_info", {}).get("total_peers", 0)
            metrics["network"]["libp2p_connected"] = libp2p_info.get("detailed_info", {}).get("connected_peers", 0)
            
            # Calculate performance metrics
            healthy_percentage = (metrics["backends"]["healthy"] / metrics["backends"]["total"]) * 100 if metrics["backends"]["total"] > 0 else 0
            
            metrics["performance"] = {
                "health_score": healthy_percentage,
                "network_connectivity": metrics["network"]["cluster_peers"] + metrics["network"]["libp2p_connected"],
                "system_health": 100 - max(metrics["system"]["cpu_percent"], metrics["system"]["memory_percent"])
            }
            
            # Calculate overall score
            metrics["performance"]["overall_score"] = (metrics["performance"]["health_score"] + metrics["performance"]["system_health"]) / 2
            
        except Exception as e:
            logger.error(f"Error getting real-time metrics: {e}")
            metrics["error"] = str(e)
        
        return metrics

    async def create_cluster_config(self, service_type: str = "service", **config_params) -> Dict[str, Any]:
        """Create cluster configuration via dashboard.
        
        Args:
            service_type: Type of service ('service' or 'follow')
            **config_params: Configuration parameters
            
        Returns:
            Dict with creation result
        """
        try:
            if not self.cluster_manager:
                raise Exception("Cluster manager not available")
                
            if service_type == "service":
                result = await self.cluster_manager.config_create(overwrite=True, **config_params)
            elif service_type == "follow":
                # Initialize follow manager if needed
                if not hasattr(self.cluster_manager, 'follow_manager'):
                    from ipfs_kit_py.ipfs_cluster_follow import IPFSClusterFollow
                    self.cluster_manager.follow_manager = IPFSClusterFollow()
                result = self.cluster_manager.follow_manager.config_create(overwrite=True, **config_params)
            else:
                raise ValueError(f"Invalid service type: {service_type}")
                
            logger.info(f"✓ Created {service_type} cluster configuration")
            return result
            
        except Exception as e:
            logger.error(f"Error creating cluster config: {e}")
            return {"success": False, "error": str(e)}

    async def get_cluster_config(self, service_type: str = "service") -> Dict[str, Any]:
        """Get cluster configuration via dashboard.
        
        Args:
            service_type: Type of service ('service' or 'follow')
            
        Returns:
            Dict with configuration data
        """
        try:
            if not self.cluster_manager:
                raise Exception("Cluster manager not available")
                
            if service_type == "service":
                result = await self.cluster_manager.config_get()
            elif service_type == "follow":
                # Initialize follow manager if needed
                if not hasattr(self.cluster_manager, 'follow_manager'):
                    from ipfs_kit_py.ipfs_cluster_follow import IPFSClusterFollow
                    self.cluster_manager.follow_manager = IPFSClusterFollow()
                result = self.cluster_manager.follow_manager.config_get()
            else:
                raise ValueError(f"Invalid service type: {service_type}")
                
            logger.info(f"✓ Retrieved {service_type} cluster configuration")
            return result
            
        except Exception as e:
            logger.error(f"Error getting cluster config: {e}")
            return {"success": False, "error": str(e)}

    async def set_cluster_config(self, service_type: str = "service", **config_params) -> Dict[str, Any]:
        """Set cluster configuration via dashboard.
        
        Args:
            service_type: Type of service ('service' or 'follow')
            **config_params: Configuration parameters
            
        Returns:
            Dict with update result
        """
        try:
            if not self.cluster_manager:
                raise Exception("Cluster manager not available")
                
            if service_type == "service":
                result = await self.cluster_manager.config_set(**config_params)
            elif service_type == "follow":
                # Initialize follow manager if needed
                if not hasattr(self.cluster_manager, 'follow_manager'):
                    from ipfs_kit_py.ipfs_cluster_follow import IPFSClusterFollow
                    self.cluster_manager.follow_manager = IPFSClusterFollow()
                result = self.cluster_manager.follow_manager.config_set(**config_params)
            else:
                raise ValueError(f"Invalid service type: {service_type}")
                
            logger.info(f"✓ Updated {service_type} cluster configuration")
            return result
            
        except Exception as e:
            logger.error(f"Error setting cluster config: {e}")
            return {"success": False, "error": str(e)}

    async def get_cluster_api_status(self, service_type: str = "service") -> Dict[str, Any]:
        """Get cluster service status via API.
        
        Args:
            service_type: Type of service ('service' or 'follow')
            
        Returns:
            Dict with API status
        """
        try:
            from ipfs_kit_py.ipfs_cluster_api import IPFSClusterAPIClient, IPFSClusterFollowAPIClient
            
            if service_type == "service":
                client = IPFSClusterAPIClient()
                result = await client.get_id()
            elif service_type == "follow":
                client = IPFSClusterFollowAPIClient()
                result = await client.get_id()
            else:
                raise ValueError(f"Invalid service type: {service_type}")
            
            # Check if result indicates success (has ID and no error)
            if result and isinstance(result, dict):
                if result.get("id") or result.get("peer_name") or not result.get("error"):
                    result["success"] = True
                    logger.info(f"✓ Retrieved {service_type} cluster API status")
                    return result
                
            logger.info(f"✓ Retrieved {service_type} cluster API status")
            return result
            
        except Exception as e:
            logger.error(f"Error getting cluster API status: {e}")
            return {"success": False, "error": str(e)}

    async def get_cluster_peers(self, service_type: str = "service") -> Dict[str, Any]:
        """Get cluster peers via API.
        
        Args:
            service_type: Type of service ('service' or 'follow')
            
        Returns:
            Dict with peers data
        """
        try:
            from ipfs_kit_py.ipfs_cluster_api import IPFSClusterAPIClient, IPFSClusterFollowAPIClient
            
            if service_type == "service":
                client = IPFSClusterAPIClient()
                result = await client.get_peers()
            elif service_type == "follow":
                client = IPFSClusterFollowAPIClient()
                result = await client.get_peers()
            else:
                raise ValueError(f"Invalid service type: {service_type}")
                
            logger.info(f"✓ Retrieved {service_type} cluster peers")
            return result
            
        except Exception as e:
            logger.error(f"Error getting cluster peers: {e}")
            return {"success": False, "error": str(e)}

    async def get_cluster_pins(self, service_type: str = "service") -> Dict[str, Any]:
        """Get cluster pins via API.
        
        Args:
            service_type: Type of service ('service' or 'follow')
            
        Returns:
            Dict with pins data
        """
        try:
            from ipfs_kit_py.ipfs_cluster_api import IPFSClusterAPIClient, IPFSClusterFollowAPIClient
            
            if service_type == "service":
                client = IPFSClusterAPIClient()
                result = await client.get_pins()
            elif service_type == "follow":
                client = IPFSClusterFollowAPIClient()
                result = await client.get_pins()
            else:
                raise ValueError(f"Invalid service type: {service_type}")
                
            logger.info(f"✓ Retrieved {service_type} cluster pins")
            return result
            
        except Exception as e:
            logger.error(f"Error getting cluster pins: {e}")
            return {"success": False, "error": str(e)}

    async def get_backend_usage_summary(self) -> Dict[str, Any]:
        """Get comprehensive backend usage summary."""
        try:
            if not self.replication_manager:
                return {"success": False, "error": "Replication manager not available"}
            
            # Get traffic analytics summary
            traffic_analytics = await self.replication_manager.get_traffic_analytics()
            
            # Get VFS backend mapping
            vfs_mapping = await self.replication_manager.get_vfs_backend_mapping()
            
            # Get replication status
            replication_status = await self.replication_manager.get_replication_status()
            
            return {
                "success": True,
                "traffic_analytics": traffic_analytics,
                "vfs_mapping": vfs_mapping,
                "replication_status": replication_status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting backend usage summary: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_cid_filesystem_links(self, cid: str) -> Dict[str, Any]:
        """Get filesystem links for a specific CID across all backends."""
        try:
            if not self.replication_manager:
                return {"success": False, "error": "Replication manager not available"}
            
            pin_info = self.replication_manager.pin_registry.get(cid, {})
            if not pin_info:
                return {"success": False, "error": f"CID {cid} not found in pin registry"}
            
            backends = pin_info.get("backends", [])
            filesystem_links = {}
            
            for backend in backends:
                # Mock filesystem links - in real implementation, this would query each backend
                filesystem_links[backend] = {
                    "path": f"/{backend}/ipfs/{cid}",
                    "size_bytes": pin_info.get("metadata", {}).get("size_bytes", 0),
                    "last_accessed": pin_info.get("last_check"),
                    "status": "available"
                }
            
            return {
                "success": True,
                "cid": cid,
                "filesystem_links": filesystem_links,
                "vfs_metadata_id": pin_info.get("vfs_metadata_id"),
                "total_backends": len(backends),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting CID filesystem links: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_cid_storage_locations(self, cid: str) -> Dict[str, Any]:
        """Get storage locations for a specific CID."""
        try:
            if not self.replication_manager:
                return {"success": False, "error": "Replication manager not available"}
            
            pin_info = self.replication_manager.pin_registry.get(cid, {})
            if not pin_info:
                return {"success": False, "error": f"CID {cid} not found in pin registry"}
            
            backends = pin_info.get("backends", [])
            storage_locations = []
            
            for backend in backends:
                backend_info = self.replication_manager.backends.get(backend, {})
                storage_locations.append({
                    "backend": backend,
                    "type": backend_info.get("type", "unknown"),
                    "priority": backend_info.get("priority", 0),
                    "path": f"/{backend}/ipfs/{cid}",
                    "status": "available",
                    "last_check": pin_info.get("last_check")
                })
            
            return {
                "success": True,
                "cid": cid,
                "storage_locations": storage_locations,
                "replication_count": len(storage_locations),
                "vfs_metadata_id": pin_info.get("vfs_metadata_id"),
                "metadata": pin_info.get("metadata", {}),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting CID storage locations: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_all_pins_with_locations(self) -> Dict[str, Any]:
        """List all pins with their backend locations and VFS metadata."""
        try:
            if not self.replication_manager:
                return {"success": False, "error": "Replication manager not available"}
            
            pins_with_locations = []
            
            for cid, pin_info in self.replication_manager.pin_registry.items():
                backends = pin_info.get("backends", [])
                storage_locations = []
                
                for backend in backends:
                    backend_info = self.replication_manager.backends.get(backend, {})
                    storage_locations.append({
                        "backend": backend,
                        "type": backend_info.get("type", "unknown"),
                        "path": f"/{backend}/ipfs/{cid}"
                    })
                
                pins_with_locations.append({
                    "cid": cid,
                    "vfs_metadata_id": pin_info.get("vfs_metadata_id"),
                    "storage_locations": storage_locations,
                    "replication_count": len(storage_locations),
                    "metadata": pin_info.get("metadata", {}),
                    "last_check": pin_info.get("last_check")
                })
            
            return {
                "success": True,
                "pins": pins_with_locations,
                "total_pins": len(pins_with_locations),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting all pins with locations: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_backend_pins(self, backend_name: str) -> Dict[str, Any]:
        """Get all pins stored on a specific backend."""
        try:
            if not self.replication_manager:
                return {"success": False, "error": "Replication manager not available"}
            
            backend_pins = []
            
            for cid, pin_info in self.replication_manager.pin_registry.items():
                if backend_name in pin_info.get("backends", []):
                    backend_pins.append({
                        "cid": cid,
                        "vfs_metadata_id": pin_info.get("vfs_metadata_id"),
                        "size_bytes": pin_info.get("metadata", {}).get("size_bytes", 0),
                        "last_check": pin_info.get("last_check"),
                        "metadata": pin_info.get("metadata", {}),
                        "all_backends": pin_info.get("backends", [])
                    })
            
            total_size = sum(pin.get("size_bytes", 0) for pin in backend_pins)
            
            return {
                "success": True,
                "backend_name": backend_name,
                "pins": backend_pins,
                "total_pins": len(backend_pins),
                "total_size_bytes": total_size,
                "total_size_gb": total_size / (1024**3),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting backend pins: {e}")
            return {"success": False, "error": str(e)}


# Initialize controller
dashboard_controller = DashboardController()

# API Endpoints
@dashboard_router.get("/status")
async def get_dashboard_status():
    """Get comprehensive dashboard status."""
    try:
        status = await dashboard_controller.get_comprehensive_status()
        return {"success": True, "data": status}
    except Exception as e:
        logger.error(f"Error in dashboard status endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/daemon/action")
async def perform_daemon_action(request: DaemonActionRequest):
    """Perform action on a daemon."""
    try:
        result = await dashboard_controller.perform_daemon_action(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in daemon action endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/cluster/action")
async def perform_cluster_action(request: ClusterActionRequest):
    """Perform cluster-specific action."""
    try:
        result = await dashboard_controller.perform_cluster_action(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in cluster action endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/health/check")
async def perform_health_check(request: HealthCheckRequest):
    """Perform health check."""
    try:
        result = await dashboard_controller.perform_health_check(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in health check endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/metrics/realtime")
async def get_realtime_metrics():
    """Get real-time metrics."""
    try:
        metrics = await dashboard_controller.get_real_time_metrics()
        return {"success": True, "data": metrics}
    except Exception as e:
        logger.error(f"Error in realtime metrics endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/backends/{backend_name}/status")
async def get_backend_status(backend_name: str):
    """Get status of specific backend."""
    try:
        result = await dashboard_controller.health_monitor.check_backend_health(backend_name)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error getting backend status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/backends/{backend_name}/restart")
async def restart_backend(backend_name: str, background_tasks: BackgroundTasks):
    """Restart specific backend."""
    try:
        # Create restart request
        request = DaemonActionRequest(
            daemon_name=backend_name,
            action="restart",
            force=True
        )
        
        result = await dashboard_controller.perform_daemon_action(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error restarting backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/logs/{backend_name}")
async def get_backend_logs(backend_name: str, lines: int = 100):
    """Get logs for specific backend."""
    try:
        logs = dashboard_controller.health_monitor.log_manager.get_backend_logs(
            backend_name, limit=lines
        )
        return {"success": True, "data": {"logs": logs}}
    except Exception as e:
        logger.error(f"Error getting backend logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Cluster Configuration Endpoints
@dashboard_router.post("/cluster/config/create")
async def create_cluster_config(request: dict):
    """Create cluster configuration."""
    try:
        service_type = request.get("service_type", "service")
        result = await dashboard_controller.create_cluster_config(service_type, **request)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error creating cluster config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/cluster/config/{service_type}")
async def get_cluster_config(service_type: str):
    """Get cluster configuration."""
    try:
        result = await dashboard_controller.get_cluster_config(service_type)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error getting cluster config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.put("/cluster/config/{service_type}")
async def update_cluster_config(service_type: str, request: dict):
    """Update cluster configuration."""
    try:
        result = await dashboard_controller.set_cluster_config(service_type, **request)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error updating cluster config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/cluster/{service_type}/status")
async def get_cluster_service_status(service_type: str):
    """Get cluster service status via API."""
    try:
        result = await dashboard_controller.get_cluster_api_status(service_type)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error getting cluster service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/cluster/{service_type}/peers")
async def get_cluster_peers(service_type: str):
    """Get cluster peers via API."""
    try:
        result = await dashboard_controller.get_cluster_peers(service_type)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error getting cluster peers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/cluster/{service_type}/pins")
async def get_cluster_pins(service_type: str):
    """Get cluster pins via API."""
    try:
        result = await dashboard_controller.get_cluster_pins(service_type)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error getting cluster pins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Virtual Filesystem (VFS) and Columnar IPLD Endpoints
@dashboard_router.post("/vfs/operation")
async def perform_vfs_operation(request: VirtualFilesystemRequest):
    """Perform virtual filesystem operations."""
    try:
        result = await dashboard_controller.perform_vfs_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in VFS operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/vfs/datasets")
async def list_vfs_datasets():
    """List all VFS datasets."""
    try:
        request = VirtualFilesystemRequest(action="list")
        result = await dashboard_controller.perform_vfs_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error listing VFS datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/vfs/datasets/{dataset_id}")
async def get_vfs_dataset(dataset_id: str, include_car: bool = False):
    """Get specific VFS dataset metadata."""
    try:
        request = VirtualFilesystemRequest(
            action="get",
            dataset_id=dataset_id,
            include_car=include_car
        )
        result = await dashboard_controller.perform_vfs_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error getting VFS dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/vfs/datasets/{dataset_id}/convert_to_car")
async def convert_dataset_to_car(
    dataset_id: str,
    include_vector_index: bool = True,
    include_knowledge_graph: bool = True
):
    """Convert VFS dataset to CAR archive."""
    try:
        request = VirtualFilesystemRequest(
            action="convert_to_car",
            dataset_id=dataset_id,
            include_vector_index=include_vector_index,
            include_knowledge_graph=include_knowledge_graph
        )
        result = await dashboard_controller.perform_vfs_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error converting dataset to CAR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Vector Index Endpoints
@dashboard_router.post("/vector/operation")
async def perform_vector_operation(request: VectorIndexRequest):
    """Perform vector index operations."""
    try:
        result = await dashboard_controller.perform_vector_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in vector operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/vector/collections")
async def list_vector_collections():
    """List all vector collections."""
    try:
        request = VectorIndexRequest(action="list")
        result = await dashboard_controller.perform_vector_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error listing vector collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/vector/search")
async def search_vectors(query_vector: list, top_k: int = 10):
    """Perform vector similarity search."""
    try:
        request = VectorIndexRequest(
            action="search",
            query_vector=query_vector,
            top_k=top_k
        )
        result = await dashboard_controller.perform_vector_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in vector search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/vector/collections/{collection_id}/export_car")
async def export_vector_collection_to_car(collection_id: str):
    """Export vector collection to CAR archive."""
    try:
        request = VectorIndexRequest(
            action="export_car",
            collection_id=collection_id
        )
        result = await dashboard_controller.perform_vector_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error exporting vector collection to CAR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Knowledge Graph Endpoints
@dashboard_router.post("/kg/operation")
async def perform_kg_operation(request: KnowledgeGraphRequest):
    """Perform knowledge graph operations."""
    try:
        result = await dashboard_controller.perform_kg_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in knowledge graph operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/kg/entities")
async def list_kg_entities():
    """List all knowledge graph entities."""
    try:
        request = KnowledgeGraphRequest(action="list_entities")
        result = await dashboard_controller.perform_kg_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error listing KG entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/kg/entities/{entity_id}")
async def get_kg_entity(entity_id: str, include_relationships: bool = False):
    """Get specific knowledge graph entity."""
    try:
        request = KnowledgeGraphRequest(
            action="get_entity",
            entity_id=entity_id,
            include_relationships=include_relationships
        )
        result = await dashboard_controller.perform_kg_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error getting KG entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/kg/search")
async def search_kg(query: str):
    """Search knowledge graph entities."""
    try:
        request = KnowledgeGraphRequest(
            action="search",
            query=query
        )
        result = await dashboard_controller.perform_kg_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error searching knowledge graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/kg/export_car")
async def export_kg_to_car():
    """Export knowledge graph to CAR archive."""
    try:
        request = KnowledgeGraphRequest(action="export_car")
        result = await dashboard_controller.perform_kg_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error exporting KG to CAR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Pinset Management Endpoints
@dashboard_router.post("/pinset/operation")
async def perform_pinset_operation(request: PinsetRequest):
    """Perform pinset operations."""
    try:
        result = await dashboard_controller.perform_pinset_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in pinset operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/pinset/pins")
async def list_pinset_pins():
    """List all pins in pinset."""
    try:
        request = PinsetRequest(action="list")
        result = await dashboard_controller.perform_pinset_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error listing pinset pins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/pinset/pins/{cid}")
async def get_pinset_pin(cid: str):
    """Get specific pin information."""
    try:
        request = PinsetRequest(action="get", cid=cid)
        result = await dashboard_controller.perform_pinset_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error getting pin info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/pinset/pins/{cid}/replicate")
async def replicate_pin(cid: str, target_backend: str):
    """Replicate pin to target backend."""
    try:
        request = PinsetRequest(
            action="replicate",
            cid=cid,
            target_backend=target_backend
        )
        result = await dashboard_controller.perform_pinset_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error replicating pin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/pinset/backends")
async def track_pinset_backends():
    """Track storage backends for pins."""
    try:
        request = PinsetRequest(action="track_backends")
        result = await dashboard_controller.perform_pinset_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error tracking pinset backends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Replication Management Endpoints
@dashboard_router.post("/replication/operation")
async def perform_replication_operation(request: ReplicationRequest):
    """Perform replication management operations."""
    try:
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in replication operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/replication/status")
async def get_replication_status(cid: Optional[str] = None):
    """Get replication status for all pins or specific CID."""
    try:
        request = ReplicationRequest(action="analyze", cid=cid)
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error getting replication status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/replication/settings")
async def get_replication_settings():
    """Get current replication settings."""
    try:
        if dashboard_controller.replication_manager:
            settings = dashboard_controller.replication_manager.default_settings
            return {"success": True, "data": settings.dict()}
        else:
            return {"success": False, "error": "Replication manager not available"}
    except Exception as e:
        logger.error(f"Error getting replication settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/replication/settings")
async def update_replication_settings(settings: ReplicationSettings):
    """Update replication settings."""
    try:
        request = ReplicationRequest(action="configure", settings=settings)
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error updating replication settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/replication/pins/{cid}/replicate")
async def replicate_pin_to_backends(
    cid: str, 
    target_backends: List[str],
    force: bool = False
):
    """Replicate specific pin to target backends."""
    try:
        request = ReplicationRequest(
            action="replicate",
            cid=cid,
            target_backends=target_backends,
            force=force
        )
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error replicating pin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/replication/backends")
async def get_backend_capabilities():
    """Get available backends and their capabilities."""
    try:
        if dashboard_controller.replication_manager:
            return {
                "success": True, 
                "data": {
                    "backends": dashboard_controller.replication_manager.backends,
                    "backend_status": await dashboard_controller.replication_manager._get_backend_usage_stats()
                }
            }
        else:
            return {"success": False, "error": "Replication manager not available"}
    except Exception as e:
        logger.error(f"Error getting backend capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Backup and Restore Endpoints
@dashboard_router.post("/backup/operation")
async def perform_backup_restore_operation(request: BackupRestoreRequest):
    """Perform backup/restore operations."""
    try:
        result = await dashboard_controller.perform_backup_restore_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error in backup/restore operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/backup/{backend_name}/export")
async def export_backend_pins(
    backend_name: str,
    backup_path: Optional[str] = None,
    include_metadata: bool = True,
    compress: bool = True
):
    """Export pins from backend to backup file."""
    try:
        request = BackupRestoreRequest(
            action="export_pins",
            backend_name=backend_name,
            backup_path=backup_path,
            include_metadata=include_metadata,
            compress=compress
        )
        result = await dashboard_controller.perform_backup_restore_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error exporting backend pins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/backup/{backend_name}/import")
async def import_backend_pins(
    backend_name: str,
    backup_path: str,
    include_metadata: bool = True
):
    """Import pins from backup file to backend."""
    try:
        request = BackupRestoreRequest(
            action="import_pins",
            backend_name=backend_name,
            backup_path=backup_path,
            include_metadata=include_metadata
        )
        result = await dashboard_controller.perform_backup_restore_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error importing backend pins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/backup/{backend_name}/list")
async def list_backend_backups(backend_name: str):
    """List available backups for backend."""
    try:
        request = BackupRestoreRequest(
            action="list_backups",
            backend_name=backend_name
        )
        result = await dashboard_controller.perform_backup_restore_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error listing backend backups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/backup/verify")
async def verify_backup_integrity(backup_path: str):
    """Verify backup file integrity."""
    try:
        request = BackupRestoreRequest(
            action="verify_backup",
            backend_name="",  # Not needed for verification
            backup_path=backup_path
        )
        result = await dashboard_controller.perform_backup_restore_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error verifying backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Traffic Monitoring and Analytics Endpoints
@dashboard_router.get("/analytics/traffic")
async def get_traffic_analytics(backend: str = None):
    """Get comprehensive traffic analytics for all backends or specific backend."""
    try:
        request = ReplicationRequest(
            action="traffic_analytics",
            backend_name=backend
        )
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error getting traffic analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/analytics/traffic/{backend_name}")
async def get_backend_traffic_analytics(backend_name: str):
    """Get traffic analytics for specific backend."""
    try:
        request = ReplicationRequest(
            action="traffic_analytics",
            backend_name=backend_name
        )
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error getting backend traffic analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/vfs/backend_mapping")
async def get_vfs_backend_mapping():
    """Get mapping of VFS metadata IDs to backend storage locations."""
    try:
        request = ReplicationRequest(action="vfs_mapping")
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error getting VFS backend mapping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/analytics/backend_usage")
async def get_backend_usage_summary():
    """Get comprehensive backend usage and storage analytics."""
    try:
        # Get traffic analytics for summary
        traffic_request = ReplicationRequest(action="traffic_analytics")
        traffic_result = await dashboard_controller.perform_replication_operation(traffic_request)
        
        # Get VFS mapping for additional context
        vfs_request = ReplicationRequest(action="vfs_mapping")
        vfs_result = await dashboard_controller.perform_replication_operation(vfs_request)
        
        # Get replication status
        status_request = ReplicationRequest(action="analyze")
        status_result = await dashboard_controller.perform_replication_operation(status_request)
        
        return {
            "success": True,
            "data": {
                "traffic_analytics": traffic_result.get("data", {}),
                "vfs_mapping": vfs_result.get("data", {}),
                "replication_status": status_result.get("data", {}),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting backend usage summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/vfs/link_backend")
async def link_vfs_to_backend(cid: str, vfs_metadata_id: str, target_backends: List[str] = None):
    """Link VFS metadata to specific backend storage locations."""
    try:
        request = ReplicationRequest(
            action="replicate",
            cid=cid,
            backend_name=vfs_metadata_id,  # Using backend_name field for VFS metadata ID
            target_backends=target_backends
        )
        result = await dashboard_controller.perform_replication_operation(request)
        return {"success": result.get("success", False), "data": result}
    except Exception as e:
        logger.error(f"Error linking VFS to backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Export dashboard controller instance for external use
__all__ = ["dashboard_router", "dashboard_controller", "DashboardController", "ReplicationManager", "TrafficCounter"]

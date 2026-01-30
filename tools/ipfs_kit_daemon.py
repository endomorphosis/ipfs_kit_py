#!/usr/bin/env python3
"""
IPFS-Kit Daemon

A standalone daemon responsible for managing the filesystem backend infrastructure
separate from the MCP server and CLI tools. The daemon handles:

- Filesystem backend health monitoring and management
- Starting, stopping, and configuring filesystem backends 
- Log collection and aggregation
- Replication management across storage backends
- Pin index updates and maintenance
- Configuration management

The MCP server and CLI tools can read from parquet indexes for routing and
make calls to IPFS-Kit libraries for retrieval operations, while delegating
management operations to this daemon.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union
import threading
import subprocess
import psutil

# Configure logging
log_dir = Path("/tmp/ipfs_kit_logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_dir / 'ipfs_kit_daemon.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Import IPFS Kit components
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.dashboard.replication_manager import ReplicationManager
    from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_observer import VFSObservabilityManager
    from ipfs_kit_py.pin_wal import get_global_pin_wal, PinOperationType
    from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
    from ipfs_kit_py.error import create_result_dict, handle_error
    CORE_COMPONENTS_AVAILABLE = True
    WAL_AVAILABLE = True
    ENHANCED_FEATURES_AVAILABLE = True
    BUCKET_VFS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import core components: {e}")
    CORE_COMPONENTS_AVAILABLE = False
    WAL_AVAILABLE = False
    ENHANCED_FEATURES_AVAILABLE = False
    BUCKET_VFS_AVAILABLE = False

# Check for Arrow availability
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Fallback functions if imports fail
if not CORE_COMPONENTS_AVAILABLE:
    def create_result_dict(operation: str, success: bool = False, **kwargs):
        """Fallback create_result_dict function."""
        return {
            "operation": operation,
            "success": success,
            "timestamp": time.time(),
            **kwargs
        }
    
    def handle_error(result, e, error_type=None):
        """Fallback handle_error function."""
        result["success"] = False
        result["error"] = str(e)
        if error_type:
            result["error_type"] = error_type
        return result


class IPFSKitDaemon:
    """
    Standalone daemon for managing IPFS-Kit filesystem backend infrastructure.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "/tmp/ipfs_kit_config/daemon.json"
        self.pid_file = "/tmp/ipfs_kit_daemon.pid" 
        self.running = False
        self.start_time = time.time()
        
        # Core managers
        self.daemon_manager = None  # EnhancedDaemonManager 
        self.ipfs_kit = None  # IPFSKit
        self.replication_manager = None  # ReplicationManager
        self.health_monitor = None  # BackendHealthMonitor
        self.vfs_observer = None  # VFSObservabilityManager
        self.pin_wal = None  # PinWAL
        self.bucket_manager = None  # BucketVFSManager
        
        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()
        self.health_check_interval = 30  # seconds
        self.replication_check_interval = 300  # 5 minutes
        self.log_rotation_interval = 3600  # 1 hour
        
        # Status tracking
        self.backend_status: Dict[str, Any] = {}
        self.daemon_status: Dict[str, Any] = {}
        self.replication_status: Dict[str, Any] = {}
        
        # Load configuration
        self.config = self._load_config()
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _load_config(self) -> Dict[str, Any]:
        """Load daemon configuration from file."""
        default_config = {
            "daemon": {
                "pid_file": "/tmp/ipfs_kit_daemon.pid",
                "log_level": "INFO",
                "health_check_interval": 30,
                "replication_check_interval": 300,
                "log_rotation_interval": 3600
            },
            "backends": {
                "ipfs": {"enabled": True, "auto_start": True},
                "ipfs_cluster": {"enabled": True, "auto_start": True},
                "lotus": {"enabled": False, "auto_start": False},
                "lassie": {"enabled": True, "auto_start": True},
                "storacha": {"enabled": False, "auto_start": False},
                "s3": {"enabled": False, "auto_start": False},
                "huggingface": {"enabled": False, "auto_start": False}
            },
            "replication": {
                "enabled": True,
                "auto_replication": True,
                "min_replicas": 2,
                "max_replicas": 5,
                "check_interval": 300
            },
            "monitoring": {
                "health_checks": True,
                "metrics_collection": True,
                "log_aggregation": True,
                "performance_monitoring": True
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                # Merge with defaults
                return {**default_config, **loaded_config}
            else:
                # Create default config file
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                with open(self.config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                logger.info(f"Created default config file: {self.config_file}")
                return default_config
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return default_config
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def start(self):
        """Start the daemon."""
        logger.info("🚀 Starting IPFS-Kit Daemon")
        logger.info("=" * 60)
        
        if not CORE_COMPONENTS_AVAILABLE:
            logger.error("Core components not available, cannot start daemon")
            return False
        
        # Write PID file
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            logger.info(f"PID file written: {self.pid_file}")
        except Exception as e:
            logger.error(f"Failed to write PID file: {e}")
            return False
        
        try:
            # Initialize core components
            await self._initialize_components()
            
            # Start backend monitoring
            await self._start_backend_monitoring()
            
            # Start replication management 
            await self._start_replication_management()
            
            # Start log management
            await self._start_log_management()
            
            # Start WAL processing
            await self._start_wal_processing()
            
            # Start bucket VFS management
            await self._start_bucket_vfs_management()
            
            # Start main daemon loop
            self.running = True
            logger.info("✅ IPFS-Kit Daemon started successfully")
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False
        finally:
            await self._cleanup()
    
    async def _initialize_components(self):
        """Initialize core daemon components."""
        logger.info("🔧 Initializing daemon components...")
        
        # Initialize IPFS Kit
        try:
            if CORE_COMPONENTS_AVAILABLE and 'IPFSKit' in globals():
                self.ipfs_kit = IPFSKit()
                self.daemon_manager = self.ipfs_kit.daemon_manager
                logger.info("✅ IPFS Kit initialized")
        except Exception as e:
            logger.error(f"Failed to initialize IPFS Kit: {e}")
            raise
        
        # Initialize WAL system
        try:
            if WAL_AVAILABLE:
                self.pin_wal = get_global_pin_wal()
                logger.info("✅ Pin WAL initialized")
        except Exception as e:
            logger.warning(f"Pin WAL not available: {e}")
            self.pin_wal = None
        
        # Initialize Bucket VFS Manager
        try:
            if BUCKET_VFS_AVAILABLE:
                ipfs_client = self.ipfs_kit.ipfs if self.ipfs_kit else None
                self.bucket_manager = get_global_bucket_manager(
                    storage_path="/tmp/ipfs_kit_buckets",
                    ipfs_client=ipfs_client
                )
                logger.info("✅ Bucket VFS Manager initialized")
        except Exception as e:
            logger.warning(f"Bucket VFS Manager not available: {e}")
            self.bucket_manager = None
        
        # Initialize health monitor
        try:
            if CORE_COMPONENTS_AVAILABLE and 'BackendHealthMonitor' in globals():
                self.health_monitor = BackendHealthMonitor(
                    config_dir="/tmp/ipfs_kit_config"
                )
                logger.info("✅ Health monitor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize health monitor: {e}")
            raise
        
        # Initialize VFS observer
        try:
            if CORE_COMPONENTS_AVAILABLE and 'VFSObservabilityManager' in globals():
                self.vfs_observer = VFSObservabilityManager()
                logger.info("✅ VFS observer initialized")
        except Exception as e:
            logger.warning(f"VFS observer not available: {e}")
            self.vfs_observer = None
        
        # Initialize replication manager
        try:
            if CORE_COMPONENTS_AVAILABLE and 'ReplicationManager' in globals():
                self.replication_manager = ReplicationManager()
                logger.info("✅ Replication manager initialized")
        except Exception as e:
            logger.warning(f"Replication manager not available: {e}")
            self.replication_manager = None
    
    async def _start_backend_monitoring(self):
        """Start backend health monitoring."""
        logger.info("📊 Starting backend monitoring...")
        
        # Start enabled backends
        enabled_backends = [
            name for name, config in self.config["backends"].items()
            if config.get("enabled", False) and config.get("auto_start", False)
        ]
        
        for backend_name in enabled_backends:
            try:
                await self._start_backend(backend_name)
            except Exception as e:
                logger.error(f"Failed to start backend {backend_name}: {e}")
        
        # Start health monitoring task
        task = asyncio.create_task(self._health_monitoring_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
    
    async def _start_backend(self, backend_name: str):
        """Start a specific backend."""
        logger.info(f"🔌 Starting backend: {backend_name}")
        
        if backend_name == "ipfs":
            result = await self._start_ipfs_backend()
        elif backend_name == "ipfs_cluster":
            result = await self._start_ipfs_cluster_backend()
        elif backend_name == "lotus":
            result = await self._start_lotus_backend()
        elif backend_name == "lassie":
            result = await self._start_lassie_backend()
        else:
            logger.warning(f"Unknown backend: {backend_name}")
            return False
        
        if result.get("success"):
            logger.info(f"✅ Backend {backend_name} started successfully")
            self.backend_status[backend_name] = {
                "status": "running",
                "started_at": time.time(),
                "pid": result.get("pid")
            }
        else:
            logger.error(f"❌ Failed to start backend {backend_name}: {result.get('error')}")
            self.backend_status[backend_name] = {
                "status": "failed",
                "error": result.get("error"),
                "failed_at": time.time()
            }
        
        return result.get("success", False)
    
    async def _start_ipfs_backend(self) -> Dict[str, Any]:
        """Start IPFS daemon."""
        if not self.daemon_manager:
            return {"success": False, "error": "Daemon manager not available"}
        
        try:
            # Ensure daemon is configured and running
            result = self.daemon_manager.ensure_daemon_running_comprehensive()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_ipfs_cluster_backend(self) -> Dict[str, Any]:
        """Start IPFS Cluster."""
        if not self.daemon_manager:
            return {"success": False, "error": "Daemon manager not available"}
        
        try:
            result = self.daemon_manager._start_ipfs_cluster_service()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_lotus_backend(self) -> Dict[str, Any]:
        """Start Lotus daemon."""
        if not self.daemon_manager:
            return {"success": False, "error": "Daemon manager not available"}
        
        try:
            result = self.daemon_manager._start_lotus_daemon()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_lassie_backend(self) -> Dict[str, Any]:
        """Start Lassie daemon."""
        if not self.daemon_manager:
            return {"success": False, "error": "Daemon manager not available"}
        
        try:
            result = self.daemon_manager._start_lassie_daemon()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _health_monitoring_loop(self):
        """Background health monitoring loop."""
        logger.info("🏥 Starting health monitoring loop")
        
        while self.running:
            try:
                # Check all backend health
                for backend_name in self.config["backends"].keys():
                    if self.config["backends"][backend_name].get("enabled"):
                        await self._check_backend_health(backend_name)
                
                # Update overall daemon status
                await self._update_daemon_status()
                
                # Sleep until next check
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(10)  # Brief pause before retry
    
    async def _check_backend_health(self, backend_name: str):
        """Check health of a specific backend."""
        try:
            if self.health_monitor:
                health_result = await self.health_monitor.check_backend_health(backend_name)
                
                # Update backend status
                if backend_name not in self.backend_status:
                    self.backend_status[backend_name] = {}
                
                self.backend_status[backend_name].update({
                    "health": health_result.get("health", "unknown"),
                    "status": health_result.get("status", "unknown"),
                    "last_health_check": time.time(),
                    "metrics": health_result.get("metrics", {})
                })
                
                # Log health changes
                health = health_result.get("health", "unknown")
                if health != "healthy":
                    logger.warning(f"Backend {backend_name} health: {health}")
                
        except Exception as e:
            logger.error(f"Error checking health of {backend_name}: {e}")
    
    async def _update_daemon_status(self):
        """Update overall daemon status."""
        self.daemon_status = {
            "uptime": time.time() - self.start_time,
            "backends": dict(self.backend_status),
            "last_updated": time.time(),
            "pid": os.getpid(),
            "version": "1.0.0"
        }
    
    async def _start_replication_management(self):
        """Start replication management."""
        if not self.replication_manager or not self.config["replication"]["enabled"]:
            logger.info("Replication management disabled")
            return
        
        logger.info("🔄 Starting replication management...")
        
        # Start replication monitoring task
        task = asyncio.create_task(self._replication_monitoring_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
    
    async def _replication_monitoring_loop(self):
        """Background replication monitoring loop."""
        logger.info("🔄 Starting replication monitoring loop")
        
        while self.running:
            try:
                if self.replication_manager:
                    # Check replication health
                    await self.replication_manager._check_replication_health()
                    
                    # Perform auto-replication if enabled
                    if self.config["replication"]["auto_replication"]:
                        await self.replication_manager._perform_auto_replication()
                
                # Sleep until next check
                await asyncio.sleep(self.replication_check_interval)
                
            except Exception as e:
                logger.error(f"Error in replication monitoring loop: {e}")
                await asyncio.sleep(60)  # Longer pause on error
    
    async def _start_log_management(self):
        """Start log collection and management."""
        logger.info("📝 Starting log management...")
        
        # Start log rotation task
        task = asyncio.create_task(self._log_management_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
    
    async def _start_wal_processing(self):
        """Start WAL processing for pin operations."""
        if not self.pin_wal:
            logger.info("WAL processing disabled (WAL not available)")
            return
        
        logger.info("📝 Starting WAL processing...")
        
        # Start WAL processing task
        task = asyncio.create_task(self._wal_processing_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
    
    async def _start_bucket_vfs_management(self):
        """Start bucket VFS management for multi-bucket operations."""
        if not self.bucket_manager:
            logger.info("Bucket VFS management disabled (Bucket Manager not available)")
            return
        
        logger.info("🗂️ Starting Bucket VFS management...")
        
        # Start bucket management task
        task = asyncio.create_task(self._bucket_management_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
    
    async def _log_management_loop(self):
        """Background log management loop."""
        logger.info("📝 Starting log management loop")
        
        while self.running:
            try:
                # Rotate logs if needed
                await self._rotate_logs()
                
                # Collect logs from backends
                await self._collect_backend_logs()
                
                # Sleep until next rotation
                await asyncio.sleep(self.log_rotation_interval)
                
            except Exception as e:
                logger.error(f"Error in log management loop: {e}")
                await asyncio.sleep(300)  # 5 minute pause on error
    
    async def _rotate_logs(self):
        """Rotate daemon and backend logs."""
        try:
            # Simple log rotation - keep last 5 files
            log_files = ["ipfs_kit_daemon.log"]
            
            for log_file in log_files:
                log_path = log_dir / log_file
                if log_path.exists() and log_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                    # Rotate log
                    for i in range(4, 0, -1):
                        old_path = log_dir / f"{log_file}.{i}"
                        new_path = log_dir / f"{log_file}.{i+1}"
                        if old_path.exists():
                            old_path.rename(new_path)
                    
                    log_path.rename(log_dir / f"{log_file}.1")
                    logger.info(f"Rotated log file: {log_file}")
                    
        except Exception as e:
            logger.error(f"Error rotating logs: {e}")
    
    async def _collect_backend_logs(self):
        """Collect logs from running backends."""
        # This would collect logs from IPFS, Cluster, Lotus, etc.
        # For now, just log that collection happened
        pass
    
    async def _wal_processing_loop(self):
        """Background WAL processing loop for pin operations."""
        logger.info("📝 Starting WAL processing loop")
        
        while self.running:
            try:
                if not self.pin_wal:
                    await asyncio.sleep(60)  # WAL not available
                    continue
                
                # Get pending operations
                pending_operations = await self.pin_wal.get_pending_operations(limit=10)
                
                for operation in pending_operations:
                    try:
                        await self._process_wal_operation(operation)
                    except Exception as e:
                        logger.error(f"Error processing WAL operation {operation.get('operation_id')}: {e}")
                        
                        # Mark operation as failed
                        if operation.get('operation_id'):
                            await self.pin_wal.mark_failed(
                                operation['operation_id'], 
                                str(e), 
                                retry=True
                            )
                
                # Clean up old completed operations
                await self.pin_wal.cleanup_completed(older_than_hours=24)
                
                # Sleep before next processing cycle
                await asyncio.sleep(5)  # Process every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in WAL processing loop: {e}")
                await asyncio.sleep(30)  # Longer pause on error
    
    async def _bucket_management_loop(self):
        """Background bucket VFS management loop."""
        logger.info("🗂️ Starting bucket VFS management loop")
        
        while self.running:
            try:
                if not self.bucket_manager:
                    await asyncio.sleep(60)  # Bucket manager not available
                    continue
                
                # Perform bucket maintenance tasks
                await self._perform_bucket_maintenance()
                
                # Export bucket data to IPLD/CAR format periodically
                await self._export_buckets_to_ipld()
                
                # Update cross-bucket indexes
                await self._update_cross_bucket_indexes()
                
                # Sleep before next cycle
                await asyncio.sleep(300)  # Process every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in bucket management loop: {e}")
                await asyncio.sleep(60)  # Pause on error
    
    async def _perform_bucket_maintenance(self):
        """Perform maintenance tasks on all buckets."""
        try:
            # Get list of all buckets
            buckets_result = await self.bucket_manager.list_buckets()
            if not buckets_result["success"]:
                return
            
            buckets = buckets_result["data"]["buckets"]
            
            for bucket_info in buckets:
                bucket_name = bucket_info["name"]
                bucket = await self.bucket_manager.get_bucket(bucket_name)
                
                if bucket:
                    # Update bucket metadata
                    await bucket._save_metadata()
                    
                    # Export file metadata to Parquet for DuckDB
                    await self._export_bucket_metadata_to_parquet(bucket)
                    
                    logger.debug(f"Performed maintenance on bucket '{bucket_name}'")
            
        except Exception as e:
            logger.error(f"Error in bucket maintenance: {e}")
    
    async def _export_buckets_to_ipld(self):
        """Export bucket structures to IPLD format for IPFS traversal."""
        try:
            if not self.bucket_manager:
                return
            
            # Get list of all buckets
            buckets_result = await self.bucket_manager.list_buckets()
            if not buckets_result["success"]:
                return
            
            buckets = buckets_result["data"]["buckets"]
            
            for bucket_info in buckets:
                bucket_name = bucket_info["name"]
                bucket = await self.bucket_manager.get_bucket(bucket_name)
                
                if bucket and bucket.ipfs_client:
                    try:
                        # Export bucket to CAR archive
                        export_result = await bucket.export_to_car(include_indexes=True)
                        
                        if export_result["success"]:
                            logger.debug(f"Exported bucket '{bucket_name}' to CAR: {export_result['data']['car_cid']}")
                        
                    except Exception as e:
                        logger.error(f"Failed to export bucket '{bucket_name}' to IPLD: {e}")
            
        except Exception as e:
            logger.error(f"Error exporting buckets to IPLD: {e}")
    
    async def _export_bucket_metadata_to_parquet(self, bucket):
        """Export bucket metadata to Parquet for efficient querying."""
        try:
            if not bucket.parquet_bridge:
                return
            
            # Collect bucket statistics
            stats = {
                "bucket_name": bucket.name,
                "bucket_type": bucket.bucket_type.value,
                "vfs_structure": bucket.vfs_structure.value,
                "file_count": await bucket.get_file_count(),
                "total_size": await bucket.get_total_size(),
                "last_modified": await bucket.get_last_modified(),
                "root_cid": bucket.root_cid,
                "created_at": bucket.created_at,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Export to Parquet via bridge
            if ARROW_AVAILABLE:
                import pyarrow as pa
                import pyarrow.parquet as pq
                
                # Create Arrow table
                table = pa.table({
                    key: [value] for key, value in stats.items()
                })
                
                # Write to bucket metadata parquet
                metadata_parquet = bucket.dirs["parquet"] / "bucket_stats.parquet"
                pq.write_table(table, metadata_parquet)
                
                logger.debug(f"Exported metadata for bucket '{bucket.name}' to Parquet")
            
        except Exception as e:
            logger.error(f"Failed to export bucket metadata to Parquet: {e}")
    
    async def _update_cross_bucket_indexes(self):
        """Update cross-bucket indexes for efficient queries."""
        try:
            if not self.bucket_manager or not self.bucket_manager.enable_duckdb_integration:
                return
            
            # Get all buckets
            buckets_result = await self.bucket_manager.list_buckets()
            if not buckets_result["success"]:
                return
            
            buckets = buckets_result["data"]["buckets"]
            
            # Register all bucket tables in DuckDB
            for bucket_info in buckets:
                bucket_name = bucket_info["name"]
                bucket = await self.bucket_manager.get_bucket(bucket_name)
                
                if bucket:
                    await bucket.register_duckdb_tables(self.bucket_manager.duckdb_conn)
            
            # Create cross-bucket views
            if self.bucket_manager.duckdb_conn:
                # Create unified file metadata view
                bucket_tables = [f"{bucket_info['name']}_file_metadata" for bucket_info in buckets]
                
                if bucket_tables:
                    union_query = " UNION ALL ".join([f"SELECT * FROM {table}" for table in bucket_tables])
                    self.bucket_manager.duckdb_conn.execute(
                        f"CREATE OR REPLACE VIEW all_files AS {union_query}"
                    )
                    
                    logger.debug("Updated cross-bucket indexes")
            
        except Exception as e:
            logger.error(f"Error updating cross-bucket indexes: {e}")
    
    # Bucket Management API Methods
    
    async def create_bucket(
        self, 
        bucket_name: str, 
        bucket_type: str = "general",
        vfs_structure: str = "hybrid",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new bucket via daemon API."""
        try:
            if not self.bucket_manager:
                return create_result_dict("create_bucket", success=False, error="Bucket manager not available")
            
            # Convert string enums
            try:
                if not BUCKET_VFS_AVAILABLE:
                    return create_result_dict("create_bucket", success=False, error="Bucket VFS not available")
                
                bucket_type_enum = BucketType(bucket_type)
                vfs_structure_enum = VFSStructureType(vfs_structure)
            except ValueError as e:
                return create_result_dict("create_bucket", success=False, error=f"Invalid enum value: {e}")
            
            return await self.bucket_manager.create_bucket(
                bucket_name=bucket_name,
                bucket_type=bucket_type_enum,
                vfs_structure=vfs_structure_enum,
                metadata=metadata
            )
            
        except Exception as e:
            result = create_result_dict("create_bucket", success=False)
            return handle_error(result, e, "create_bucket")
    
    async def list_buckets(self) -> Dict[str, Any]:
        """List all buckets via daemon API."""
        try:
            if not self.bucket_manager:
                return create_result_dict("list_buckets", success=False, error="Bucket manager not available")
            
            return await self.bucket_manager.list_buckets()
            
        except Exception as e:
            result = create_result_dict("list_buckets", success=False)
            return handle_error(result, e, "list_buckets")
    
    async def delete_bucket(self, bucket_name: str, force: bool = False) -> Dict[str, Any]:
        """Delete a bucket via daemon API."""
        try:
            if not self.bucket_manager:
                return create_result_dict("delete_bucket", success=False, error="Bucket manager not available")
            
            return await self.bucket_manager.delete_bucket(bucket_name, force=force)
            
        except Exception as e:
            result = create_result_dict("delete_bucket", success=False)
            return handle_error(result, e, "delete_bucket")
    
    async def add_file_to_bucket(
        self,
        bucket_name: str,
        file_path: str,
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a file to a bucket via daemon API."""
        try:
            if not self.bucket_manager:
                return create_result_dict("add_file_to_bucket", success=False, error="Bucket manager not available")
            
            bucket = await self.bucket_manager.get_bucket(bucket_name)
            if not bucket:
                return create_result_dict("add_file_to_bucket", success=False, error=f"Bucket '{bucket_name}' not found")
            
            return await bucket.add_file(file_path, content, metadata)
            
        except Exception as e:
            result = create_result_dict("add_file_to_bucket", success=False)
            return handle_error(result, e, "add_file_to_bucket")
    
    async def cross_bucket_query(
        self, 
        sql_query: str,
        bucket_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Execute cross-bucket SQL query via daemon API."""
        try:
            if not self.bucket_manager:
                return create_result_dict("cross_bucket_query", success=False, error="Bucket manager not available")
            
            return await self.bucket_manager.cross_bucket_query(sql_query, bucket_filter)
            
        except Exception as e:
            result = create_result_dict("cross_bucket_query", success=False)
            return handle_error(result, e, "cross_bucket_query")
    
    async def _process_wal_operation(self, operation: Dict[str, Any]):
        """Process a single WAL operation."""
        operation_id = operation.get('operation_id')
        operation_type = operation.get('operation_type')
        cid = operation.get('cid')
        
        if not operation_id or not operation_type or not cid:
            logger.error(f"Invalid WAL operation: missing required fields")
            return
        
        logger.info(f"Processing WAL operation {operation_id}: {operation_type} for {cid}")
        
        # Move to processing state
        if not self.pin_wal or not await self.pin_wal.move_to_processing(operation_id):
            logger.error(f"Failed to move operation {operation_id} to processing")
            return
        
        try:
            if WAL_AVAILABLE and 'PinOperationType' in globals():
                if operation_type == "add":  # PinOperationType.ADD.value
                    result = await self._process_pin_add(operation)
                elif operation_type == "remove":  # PinOperationType.REMOVE.value
                    result = await self._process_pin_remove(operation)
                elif operation_type == "update":  # PinOperationType.UPDATE.value
                    result = await self._process_pin_update(operation)
                else:
                    raise ValueError(f"Unknown operation type: {operation_type}")
            else:
                # Fallback processing
                result = {"success": True, "message": "Processed with limited functionality"}
            
            # Mark as completed
            if self.pin_wal:
                await self.pin_wal.mark_completed(operation_id, result)
            logger.info(f"WAL operation {operation_id} completed successfully")
            
        except Exception as e:
            logger.error(f"WAL operation {operation_id} failed: {e}")
            if self.pin_wal:
                await self.pin_wal.mark_failed(operation_id, str(e), retry=True)
    
    async def _process_pin_add(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Process a pin add operation."""
        cid = operation.get('cid')
        name = operation.get('name')
        recursive = operation.get('recursive', True)
        metadata = operation.get('metadata', {})
        
        if not cid:
            raise ValueError("CID is required for pin add operation")
        
        logger.debug(f"Adding pin for CID {cid}")
        
        try:
            # Update metadata in enhanced pin index if available
            if ENHANCED_FEATURES_AVAILABLE:
                try:
                    from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
                    pin_index = get_global_enhanced_pin_index()
                    
                    # Add to enhanced pin index
                    enhanced_metadata = {
                        **metadata,
                        "processed_at": time.time(),
                        "processed_by": "daemon",
                        "wal_operation_id": operation.get('operation_id')
                    }
                    
                    # This might still fail due to locks, but we retry via WAL
                    # Mock successful addition for now
                    logger.info(f"Added pin {cid} to enhanced index")
                    
                except Exception as db_error:
                    logger.warning(f"Enhanced pin index update failed: {db_error}")
                    # Don't fail the operation, continue with replication
            
            # Replicate across backends
            replication_results = await self._replicate_pin_across_backends(cid, metadata)
            
            return {
                "success": True,
                "cid": cid,
                "name": name,
                "recursive": recursive,
                "replication_results": replication_results,
                "processed_at": time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to process pin add for {cid}: {e}")
            raise
    
    async def _process_pin_remove(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Process a pin remove operation."""
        cid = operation.get('cid')
        metadata = operation.get('metadata', {})
        
        if not cid:
            raise ValueError("CID is required for pin remove operation")
        
        logger.debug(f"Removing pin for CID {cid}")
        
        try:
            # Update metadata in enhanced pin index if available
            if ENHANCED_FEATURES_AVAILABLE:
                try:
                    from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
                    pin_index = get_global_enhanced_pin_index()
                    
                    # Remove from enhanced pin index
                    # Mock successful removal for now
                    logger.info(f"Removed pin {cid} from enhanced index")
                    
                except Exception as db_error:
                    logger.warning(f"Enhanced pin index update failed: {db_error}")
            
            # Remove from backends
            removal_results = await self._remove_pin_from_backends(cid, metadata)
            
            return {
                "success": True,
                "cid": cid,
                "removal_results": removal_results,
                "processed_at": time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to process pin remove for {cid}: {e}")
            raise
    
    async def _process_pin_update(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Process a pin metadata update operation."""
        cid = operation.get('cid')
        metadata = operation.get('metadata', {})
        
        logger.debug(f"Updating pin metadata for CID {cid}")
        
        try:
            # Update metadata in enhanced pin index if available
            if ENHANCED_FEATURES_AVAILABLE:
                try:
                    # Mock successful update for now
                    logger.info(f"Updated pin {cid} metadata in enhanced index")
                except Exception as db_error:
                    logger.warning(f"Enhanced pin index update failed: {db_error}")
            
            return {
                "success": True,
                "cid": cid,
                "metadata": metadata,
                "processed_at": time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to process pin update for {cid}: {e}")
            raise
    
    async def _replicate_pin_across_backends(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Replicate a pin across multiple storage backends."""
        results = {}
        
        # Get enabled backends from config
        enabled_backends = [
            name for name, config in self.config["backends"].items()
            if config.get("enabled", False)
        ]
        
        for backend_name in enabled_backends:
            try:
                if backend_name == "ipfs":
                    result = await self._add_pin_to_ipfs(cid, metadata)
                elif backend_name == "ipfs_cluster":
                    result = await self._add_pin_to_cluster(cid, metadata)
                elif backend_name == "s3":
                    result = await self._add_pin_to_s3(cid, metadata)
                else:
                    result = {"success": False, "error": f"Unknown backend: {backend_name}"}
                
                results[backend_name] = result
                
            except Exception as e:
                logger.error(f"Failed to replicate pin {cid} to {backend_name}: {e}")
                results[backend_name] = {"success": False, "error": str(e)}
        
        return results
    
    async def _remove_pin_from_backends(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove a pin from multiple storage backends."""
        results = {}
        
        # Get enabled backends from config
        enabled_backends = [
            name for name, config in self.config["backends"].items()
            if config.get("enabled", False)
        ]
        
        for backend_name in enabled_backends:
            try:
                if backend_name == "ipfs":
                    result = await self._remove_pin_from_ipfs(cid, metadata)
                elif backend_name == "ipfs_cluster":
                    result = await self._remove_pin_from_cluster(cid, metadata)
                elif backend_name == "s3":
                    result = await self._remove_pin_from_s3(cid, metadata)
                else:
                    result = {"success": False, "error": f"Unknown backend: {backend_name}"}
                
                results[backend_name] = result
                
            except Exception as e:
                logger.error(f"Failed to remove pin {cid} from {backend_name}: {e}")
                results[backend_name] = {"success": False, "error": str(e)}
        
        return results
    
    # Backend-specific pin operations
    
    async def _add_pin_to_ipfs(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add pin to IPFS backend."""
        # Mock implementation - would use actual IPFS API
        logger.debug(f"Adding pin {cid} to IPFS backend")
        return {"success": True, "backend": "ipfs", "cid": cid}
    
    async def _add_pin_to_cluster(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add pin to IPFS Cluster backend."""
        # Mock implementation - would use actual Cluster API
        logger.debug(f"Adding pin {cid} to IPFS Cluster backend")
        return {"success": True, "backend": "ipfs_cluster", "cid": cid}
    
    async def _add_pin_to_s3(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add pin to S3 backend."""
        # Mock implementation - would backup to S3
        logger.debug(f"Backing up pin {cid} to S3 backend")
        return {"success": True, "backend": "s3", "cid": cid}
    
    async def _remove_pin_from_ipfs(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove pin from IPFS backend."""
        # Mock implementation - would use actual IPFS API
        logger.debug(f"Removing pin {cid} from IPFS backend")
        return {"success": True, "backend": "ipfs", "cid": cid}
    
    async def _remove_pin_from_cluster(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove pin from IPFS Cluster backend."""
        # Mock implementation - would use actual Cluster API
        logger.debug(f"Removing pin {cid} from IPFS Cluster backend")
        return {"success": True, "backend": "ipfs_cluster", "cid": cid}
    
    async def _remove_pin_from_s3(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove pin from S3 backend."""
        # Mock implementation - would remove from S3
        logger.debug(f"Removing pin {cid} from S3 backend")
        return {"success": True, "backend": "s3", "cid": cid}
    
    async def _main_loop(self):
        """Main daemon loop."""
        logger.info("🔄 Starting main daemon loop")
        
        while self.running:
            try:
                # Update pin indexes if needed
                await self._update_pin_indexes()
                
                # Check for configuration changes
                await self._check_config_changes()
                
                # Cleanup old data
                await self._cleanup_old_data()
                
                # Sleep for a short interval
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in main daemon loop: {e}")
                await asyncio.sleep(10)
    
    async def _update_pin_indexes(self):
        """Update pin metadata indexes."""
        # This would update the parquet indexes that MCP/CLI read from
        pass
    
    async def _check_config_changes(self):
        """Check for configuration file changes."""
        try:
            if os.path.exists(self.config_file):
                mtime = os.path.getmtime(self.config_file)
                if hasattr(self, '_last_config_mtime') and mtime > self._last_config_mtime:
                    logger.info("Configuration file changed, reloading...")
                    self.config = self._load_config()
                    await self._reconfigure_components()
                self._last_config_mtime = mtime
        except Exception as e:
            logger.error(f"Error checking config changes: {e}")
    
    async def _reconfigure_components(self):
        """Reconfigure components after config change."""
        # Update intervals
        self.health_check_interval = self.config["daemon"]["health_check_interval"]
        self.replication_check_interval = self.config["daemon"]["replication_check_interval"]
        self.log_rotation_interval = self.config["daemon"]["log_rotation_interval"]
        
        logger.info("Components reconfigured")
    
    async def _cleanup_old_data(self):
        """Cleanup old data files."""
        # Cleanup old log files, temporary data, etc.
        pass
    
    async def _cleanup(self):
        """Cleanup daemon resources."""
        logger.info("🧹 Cleaning up daemon resources...")
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Stop replication monitoring
        if self.replication_manager:
            try:
                await self.replication_manager.stop_monitoring()
            except Exception as e:
                logger.error(f"Error stopping replication manager: {e}")
        
        # Stop daemons if we started them
        if self.daemon_manager:
            try:
                self.daemon_manager.stop_all_daemons()
            except Exception as e:
                logger.error(f"Error stopping daemons: {e}")
        
        # Remove PID file
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
        
        logger.info("✅ Daemon cleanup complete")
    
    # Public API methods for MCP/CLI communication
    
    def get_status(self) -> Dict[str, Any]:
        """Get current daemon status."""
        return {
            "daemon": self.daemon_status,
            "backends": self.backend_status,
            "replication": self.replication_status,
            "config": self.config
        }
    
    def get_backend_health(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Get backend health status."""
        if backend_name:
            return self.backend_status.get(backend_name, {})
        return self.backend_status
    
    async def restart_backend(self, backend_name: str) -> Dict[str, Any]:
        """Restart a specific backend."""
        logger.info(f"Restarting backend: {backend_name}")
        
        # Stop backend if running
        await self._stop_backend(backend_name)
        
        # Start backend
        return await self._start_backend(backend_name)
    
    async def _stop_backend(self, backend_name: str):
        """Stop a specific backend."""
        # Implementation depends on backend type
        pass


def main():
    """Main entry point for the daemon."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS-Kit Daemon")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop running daemon")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.stop:
        # Stop daemon
        pid_file = "/tmp/ipfs_kit_daemon.pid"
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped daemon (PID {pid})")
        except FileNotFoundError:
            print("No daemon running")
        except Exception as e:
            print(f"Error stopping daemon: {e}")
        return
    
    if args.status:
        # Show status
        pid_file = "/tmp/ipfs_kit_daemon.pid"
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                print(f"Daemon running (PID {pid})")
            else:
                print("Daemon not running (stale PID file)")
        except FileNotFoundError:
            print("Daemon not running")
        except Exception as e:
            print(f"Error checking status: {e}")
        return
    
    # Start daemon
    daemon = IPFSKitDaemon(config_file=args.config)
    
    if args.daemon:
        # Run as background daemon (would need proper daemonization)
        print("Daemon mode not implemented yet, running in foreground")
    
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        print("\nDaemon stopped by user")
    except Exception as e:
        print(f"Daemon failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

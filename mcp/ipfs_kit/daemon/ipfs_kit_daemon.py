#!/usr/bin/env python3
"""
IPFS Kit Daemon - Standalone daemon for IPFS Kit backend management.

This daemon is responsible for:
- Managing filesystem backend health (IPFS, Cluster, Lotus, etc.)
- Starting/stopping backend services
- Log collection and monitoring 
- Replication management across backends
- Configuration management
- Pin index updates
- Providing API endpoints for MCP clients and CLI tools

The MCP server and CLI tools become lightweight clients that query this daemon.
"""

import anyio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# FastAPI for daemon API
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Core IPFS Kit functionality
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
# Defer heavy imports like IPFSKit until runtime initialization to avoid import-time side effects
# from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
"""
NOTE: We intentionally avoid importing BucketVFSManager at module import time
because it pulls in optional dependencies (e.g., networkx via knowledge graph)
that are not required for the daemon API to start. We'll import it lazily in
initialize() and degrade gracefully if unavailable.
"""

# MCP backend components
from ..backends.health_monitor import BackendHealthMonitor
from ..backends.log_manager import BackendLogManager
from ..core.config_manager import SecureConfigManager

# Pin index management
import pandas as pd
import sqlite3

# Check for Arrow availability
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

logger = logging.getLogger(__name__)

class IPFSKitDaemon:
    """
    Standalone IPFS Kit Daemon.
    
    Manages all heavyweight operations and provides API endpoints
    for lightweight MCP clients and CLI tools.
    """
    
    def __init__(self, 
                 host: str = "127.0.0.1",
                 port: int = 9999,
                 config_dir: str = "/tmp/ipfs_kit_config",
                 data_dir: Optional[str] = None):
        self.host = host
        self.port = port
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir or str(Path.home() / ".ipfs_kit"))
        
        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.ipfs_kit = None
        self.health_monitor = None
        self.log_manager = None
        self.config_manager = None
        self.bucket_vfs_manager = None
        
        # Daemon state
        self.running = False
        self.start_time = None
        
        # Background tasks
        self._task_group = None
        
        # FastAPI app
        self.app = self._create_app()
        
        logger.info(f"🔧 IPFS Kit Daemon initialized")
        logger.info(f"📍 Host: {host}:{port}")
        logger.info(f"📁 Config: {config_dir}")
        logger.info(f"💾 Data: {self.data_dir}")
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application with daemon endpoints."""
        app = FastAPI(
            title="IPFS Kit Daemon API",
            description="Backend daemon for IPFS Kit filesystem management",
            version="1.0.0"
        )

        @app.on_event("startup")
        async def _startup_event():
            """Initialize subsystems in the background so API becomes responsive quickly."""
            try:
                # Mark running early so status endpoints reflect startup
                self.running = True
                if self.start_time is None:
                    self.start_time = datetime.now()
                # Fire and forget initialization (non-blocking)
                anyio.lowlevel.spawn_system_task(self.initialize)
            except Exception as e:
                logger.error(f"Startup initialization scheduling failed: {e}")
        # Simple status endpoint expected by CI scripts
        @app.get("/api/v1/status")
        async def get_status():
            now = datetime.now()
            uptime = None
            if self.start_time:
                uptime = (now - self.start_time).total_seconds()
            return JSONResponse(content={
                "status": "ok",
                "running": bool(self.running),
                "host": self.host,
                "port": self.port,
                "uptime_seconds": uptime,
                "timestamp": now.isoformat(),
            })
        
        # Health endpoints
        @app.get("/health")
        async def get_health():
            """Get comprehensive daemon health status."""
            if not self.health_monitor:
                # Provide minimal health response for early probes
                now = datetime.now().isoformat()
                return JSONResponse(content={
                    "status": "starting",
                    "running": bool(self.running),
                    "host": self.host,
                    "port": self.port,
                    "timestamp": now,
                })
            
            health_status = await self.health_monitor.get_comprehensive_health_status()
            return JSONResponse(content=health_status)

        # Alias expected by CI scripts
        @app.get("/api/v1/health")
        async def get_health_v1():
            if not self.health_monitor:
                now = datetime.now().isoformat()
                return JSONResponse(content={
                    "status": "starting",
                    "running": bool(self.running),
                    "host": self.host,
                    "port": self.port,
                    "timestamp": now,
                })
            health_status = await self.health_monitor.get_comprehensive_health_status()
            return JSONResponse(content=health_status)
        
        @app.get("/health/backends")
        async def get_backend_health():
            """Get backend-specific health status."""
            if not self.health_monitor:
                raise HTTPException(status_code=503, detail="Health monitor not initialized")
            
            backend_health = await self.health_monitor.check_all_backends_health()
            return JSONResponse(content=backend_health)
        
        @app.get("/health/filesystem")
        async def get_filesystem_health():
            """Get filesystem status from parquet files."""
            if not self.health_monitor:
                raise HTTPException(status_code=503, detail="Health monitor not initialized")
            
            fs_status = await self.health_monitor.get_filesystem_status_from_parquet()
            return JSONResponse(content=fs_status)
        
        # Pin management endpoints
        @app.get("/pins")
        async def list_pins():
            """List all pins with metadata."""
            try:
                pins_data = await self._get_pin_index_data()
                return JSONResponse(content=pins_data)
            except Exception as e:
                logger.error(f"Error listing pins: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/pins/{cid}")
        async def add_pin(cid: str, background_tasks: BackgroundTasks):
            """Add a pin and update index."""
            try:
                result = await self._add_pin_with_replication(cid)
                
                # Schedule background index update
                background_tasks.add_task(self._update_pin_index)
                
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error adding pin {cid}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.delete("/pins/{cid}")
        async def remove_pin(cid: str, background_tasks: BackgroundTasks):
            """Remove a pin and update index."""
            try:
                result = await self._remove_pin_with_replication(cid)
                
                # Schedule background index update
                background_tasks.add_task(self._update_pin_index)
                
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error removing pin {cid}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Backend management endpoints
        @app.post("/backends/{backend_name}/start")
        async def start_backend(backend_name: str):
            """Start a specific backend service."""
            try:
                result = await self._start_backend(backend_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error starting {backend_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/backends/{backend_name}/stop")
        async def stop_backend(backend_name: str):
            """Stop a specific backend service."""
            try:
                result = await self._stop_backend(backend_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error stopping {backend_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/backends/{backend_name}/logs")
        async def get_backend_logs(backend_name: str, lines: int = 100):
            """Get logs for a specific backend."""
            try:
                logs = await self._get_backend_logs(backend_name, lines)
                return JSONResponse(content={"logs": logs})
            except Exception as e:
                logger.error(f"Error getting logs for {backend_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Configuration endpoints
        @app.get("/config")
        async def get_config():
            """Get daemon configuration."""
            try:
                config = await self._get_daemon_config()
                return JSONResponse(content=config)
            except Exception as e:
                logger.error(f"Error getting config: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.put("/config")
        async def update_config(config_data: Dict[str, Any]):
            """Update daemon configuration."""
            try:
                result = await self._update_daemon_config(config_data)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error updating config: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Status endpoints
        @app.get("/status")
        async def get_daemon_status():
            """Get overall daemon status."""
            return JSONResponse(content={
                "running": self.running,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "uptime_seconds": time.time() - self.start_time.timestamp() if self.start_time else 0,
                "components": {
                    "ipfs_kit": self.ipfs_kit is not None,
                    "health_monitor": self.health_monitor is not None,
                    "log_manager": self.log_manager is not None,
                    "config_manager": self.config_manager is not None
                },
                "api_version": "1.0.0"
            })
        
        return app
    
    async def initialize(self):
        """Initialize all daemon components."""
        logger.info("🚀 Initializing IPFS Kit Daemon components...")
        
        try:
            # Initialize config manager
            self.config_manager = SecureConfigManager(str(self.config_dir))
            logger.info("✓ Config manager initialized")
            
            # Initialize log manager
            self.log_manager = BackendLogManager()
            logger.info("✓ Log manager initialized")
            
            # Initialize IPFS Kit (lazy import to avoid import-time side effects)
            try:
                from ipfs_kit_py.ipfs_kit import IPFSKit
                self.ipfs_kit = IPFSKit()
                logger.info("✓ IPFS Kit initialized")
            except Exception as e:
                logger.warning(f"⚠️ IPFS Kit initialization skipped/unavailable: {e}")
                self.ipfs_kit = None
            
            # Initialize Bucket VFS Manager (optional, lazy import)
            try:
                from ipfs_kit_py.bucket_vfs_manager import BucketVFSManager  # Lazy import
                bucket_dir = self.data_dir / "buckets"
                bucket_dir.mkdir(exist_ok=True)
                self.bucket_vfs_manager = BucketVFSManager(
                    storage_path=str(bucket_dir),
                    enable_duckdb_integration=True,
                    enable_parquet_export=True
                )
                logger.info("✓ Bucket VFS Manager initialized")
            except Exception as e:
                logger.warning(f"⚠️ Bucket VFS Manager initialization skipped/unavailable: {e}")
                self.bucket_vfs_manager = None
            
            # Initialize health monitor
            self.health_monitor = BackendHealthMonitor(str(self.config_dir))
            logger.info("✓ Health monitor initialized")
            
            # Start background monitoring tasks
            await self._start_background_tasks()
            
            logger.info("🎉 All daemon components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize daemon: {e}")
            return False
    
    async def _start_background_tasks(self):
        """Start background monitoring and maintenance tasks."""
        logger.info("📊 Starting background tasks...")

        if self._task_group is None:
            tg = anyio.create_task_group()
            await tg.__aenter__()
            self._task_group = tg

        self._task_group.start_soon(self._health_monitoring_loop)
        self._task_group.start_soon(self._pin_index_update_loop)
        self._task_group.start_soon(self._log_collection_loop)

        if self.bucket_vfs_manager:
            self._task_group.start_soon(self._bucket_maintenance_loop)

        logger.info("✓ Started background tasks")
    
    async def _health_monitoring_loop(self):
        """Background health monitoring loop."""
        logger.info("🏥 Starting health monitoring loop...")
        
        while self.running:
            try:
                # Check backend health every 30 seconds
                if self.health_monitor:
                    await self.health_monitor.check_all_backends_health()
                
                await anyio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await anyio.sleep(60)  # Wait longer if there's an error
    
    async def _pin_index_update_loop(self):
        """Background pin index update loop."""
        logger.info("📎 Starting pin index update loop...")
        
        while self.running:
            try:
                # Update pin index every 5 minutes
                await self._update_pin_index()
                await anyio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in pin index update loop: {e}")
                await anyio.sleep(600)  # Wait longer if there's an error
    
    async def _log_collection_loop(self):
        """Background log collection loop."""
        logger.info("📋 Starting log collection loop...")
        
        while self.running:
            try:
                # Collect logs every 60 seconds
                if self.log_manager:
                    # Use the async log collection method
                    await self.log_manager.collect_all_backend_logs()
                
                await anyio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in log collection loop: {e}")
                await anyio.sleep(120)  # Wait longer if there's an error

    async def _bucket_maintenance_loop(self):
        """Background bucket maintenance loop."""
        logger.info("🪣 Starting bucket maintenance loop...")
        
        while self.running:
            try:
                # Update bucket indexes and parquet exports every 5 minutes
                if self.bucket_vfs_manager:
                    await self._update_bucket_indexes()
                    await self._export_buckets_to_parquet()
                
                await anyio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in bucket maintenance loop: {e}")
                await anyio.sleep(600)  # Wait longer if there's an error
    
    async def _get_pin_index_data(self) -> Dict[str, Any]:
        """Get pin index data from parquet files."""
        try:
            pin_index_dir = self.data_dir / "pin_metadata"
            
            if not pin_index_dir.exists():
                return {"pins": [], "total": 0, "error": "Pin index not found"}
            
            # Read pins parquet from new structure
            pins_file = pin_index_dir / "parquet_storage" / "pins.parquet"
            if pins_file.exists():
                df = pd.read_parquet(pins_file)
                pins_data = df.to_dict('records')
                
                return {
                    "pins": pins_data,
                    "total": len(pins_data),
                    "last_updated": pins_file.stat().st_mtime
                }
            else:
                return {"pins": [], "total": 0, "error": "Pins file not found"}
                
        except Exception as e:
            logger.error(f"Error reading pin index: {e}")
            return {"pins": [], "total": 0, "error": str(e)}
    
    async def _add_pin_with_replication(self, cid: str) -> Dict[str, Any]:
        """Add a pin with replication across backends."""
        try:
            if not self.ipfs_kit:
                return {"success": False, "error": "IPFS Kit not initialized"}
            
            # Add pin using IPFS Kit (synchronous API)
            result = self.ipfs_kit.ipfs_pin_add(cid)
            
            # TODO: Add replication logic here
            # This would involve pinning to cluster, backing up to other storage, etc.
            
            return {
                "success": True,
                "cid": cid,
                "result": result,
                "replicated": False  # TODO: Implement replication
            }
            
        except Exception as e:
            logger.error(f"Error adding pin {cid}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _remove_pin_with_replication(self, cid: str) -> Dict[str, Any]:
        """Remove a pin with replication cleanup."""
        try:
            if not self.ipfs_kit:
                return {"success": False, "error": "IPFS Kit not initialized"}
            
            # Remove pin using IPFS Kit (synchronous API)
            result = self.ipfs_kit.ipfs_pin_rm(cid)
            
            # TODO: Add replication cleanup logic here
            
            return {
                "success": True,
                "cid": cid,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error removing pin {cid}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_pin_index(self):
        """Update pin index with current state."""
        try:
            logger.debug("Updating pin index...")
            
            # Use the new pin metadata index
            from ipfs_kit_py.pin_metadata_index import PinMetadataIndex
            
            pin_index = PinMetadataIndex()
            
            # If IPFSKit is available, get current pins and update index
            if self.ipfs_kit:
                try:
                    # TODO: Get pins from IPFS daemon once pin_ls is available
                    # For now, just export existing metadata to parquet
                    await anyio.to_thread.run_sync(pin_index.export_to_parquet)
                    logger.debug("✓ Pin index exported to parquet")
                except Exception as e:
                    logger.warning(f"Could not update pins from IPFS: {e}")
                    # Still export existing metadata
                    await anyio.to_thread.run_sync(pin_index.export_to_parquet)
            else:
                # Just export existing metadata to parquet
                await anyio.to_thread.run_sync(pin_index.export_to_parquet)
                logger.debug("✓ Pin index metadata exported to parquet")
            
        except Exception as e:
            logger.error(f"Error updating pin index: {e}")
    
    async def _start_backend(self, backend_name: str) -> Dict[str, Any]:
        """Start a specific backend service."""
        try:
            if not self.ipfs_kit:
                return {"success": False, "error": "IPFS Kit not initialized"}
            
            # Use daemon manager to start backend
            daemon_manager = getattr(self.ipfs_kit, 'daemon_manager', None)
            if daemon_manager is None:
                return {"success": False, "error": "Daemon manager not available"}
            
            if backend_name == "ipfs" and hasattr(daemon_manager, 'start_ipfs_daemon'):
                result = daemon_manager.start_ipfs_daemon()
            elif backend_name == "cluster" and hasattr(daemon_manager, 'start_cluster_daemon'):
                result = daemon_manager.start_cluster_daemon()
            elif backend_name == "lotus" and hasattr(daemon_manager, 'start_lotus_daemon'):
                result = daemon_manager.start_lotus_daemon()
            else:
                return {"success": False, "error": f"Unknown backend: {backend_name}"}
            
            return {"success": True, "backend": backend_name, "result": result}
            
        except Exception as e:
            logger.error(f"Error starting {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _stop_backend(self, backend_name: str) -> Dict[str, Any]:
        """Stop a specific backend service."""
        try:
            if not self.ipfs_kit:
                return {"success": False, "error": "IPFS Kit not initialized"}
            
            # Use daemon manager to stop backend
            daemon_manager = getattr(self.ipfs_kit, 'daemon_manager', None)
            if daemon_manager is None:
                return {"success": False, "error": "Daemon manager not available"}
            
            if backend_name == "ipfs" and hasattr(daemon_manager, 'stop_ipfs_daemon'):
                result = daemon_manager.stop_ipfs_daemon()
            elif backend_name == "cluster" and hasattr(daemon_manager, 'stop_cluster_daemon'):
                result = daemon_manager.stop_cluster_daemon()
            elif backend_name == "lotus" and hasattr(daemon_manager, 'stop_lotus_daemon'):
                result = daemon_manager.stop_lotus_daemon()
            else:
                return {"success": False, "error": f"Unknown backend: {backend_name}"}
            
            return {"success": True, "backend": backend_name, "result": result}
            
        except Exception as e:
            logger.error(f"Error stopping {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_backend_logs(self, backend_name: str, lines: int) -> List[str]:
        """Get logs for a specific backend."""
        try:
            if not self.log_manager:
                return ["Log manager not initialized"]
            
            # Get logs from log manager and coerce to strings
            logs = self.log_manager.get_backend_logs(backend_name, lines)
            try:
                return [str(line) for line in logs]
            except Exception:
                return [str(logs)]
            
        except Exception as e:
            logger.error(f"Error getting logs for {backend_name}: {e}")
            return [f"Error getting logs: {e}"]
    
    async def _get_daemon_config(self) -> Dict[str, Any]:
        """Get daemon configuration."""
        try:
            if not self.config_manager:
                return {"error": "Config manager not initialized"}
            
            # Build a consolidated config view using available methods
            try:
                full = self.config_manager.get_full_config()
                return full or {}
            except Exception as e:
                logger.warning(f"Falling back to backend configs only: {e}")
                try:
                    return {"backend_configs": self.config_manager.get_all_backend_configs()}
                except Exception as e2:
                    return {"error": str(e2)}
            
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return {"error": str(e)}
    
    async def _update_daemon_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update daemon configuration."""
        try:
            if not self.config_manager:
                return {"success": False, "error": "Config manager not initialized"}
            
            # Update configuration via secure config manager (save only backend configs section if present)
            try:
                if "backend_configs" in config_data:
                    for name, cfg in config_data["backend_configs"].items():
                        self.config_manager.save_backend_config(name, cfg)
                if "package_config" in config_data:
                    self.config_manager.save_package_config(config_data["package_config"])
            except Exception as e:
                return {"success": False, "error": str(e)}
            
            return {"success": True, "config": config_data}
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return {"success": False, "error": str(e)}
    
    async def start(self):
        """Start the daemon."""
        logger.info("🚀 Starting IPFS Kit Daemon...")
        # Set daemon state early; detailed init happens in startup event
        self.running = True
        if self.start_time is None:
            self.start_time = datetime.now()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"🌐 Starting API server on {self.host}:{self.port}")
        
        # Start FastAPI server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"❌ Error running daemon: {e}")
            return False
        
        return True
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"🛑 Received signal {signum}, shutting down...")
        self.running = False

        if self._task_group is not None:
            self._task_group.cancel_scope.cancel()
        
        logger.info("✓ Daemon shutdown complete")
    
    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("🛑 Stopping IPFS Kit Daemon...")
        
        self.running = False
        
        if self._task_group is not None:
            self._task_group.cancel_scope.cancel()
            await self._task_group.__aexit__(None, None, None)
            self._task_group = None
        
        # Cleanup components
        if self.health_monitor:
            # Stop health monitoring
            pass
        
        if self.ipfs_kit:
            # Cleanup IPFS Kit
            pass
        
        logger.info("✓ IPFS Kit Daemon stopped")

    async def _update_bucket_indexes(self):
        """Update bucket indexes and metadata."""
        try:
            if not self.bucket_vfs_manager:
                return
            
            # Get list of all buckets
            buckets_result = await self.bucket_vfs_manager.list_buckets()
            if not buckets_result.get("success", False):
                return
            
            buckets = buckets_result.get("data", {}).get("buckets", [])
            
            for bucket_info in buckets:
                bucket_name = bucket_info["name"]
                bucket = await self.bucket_vfs_manager.get_bucket(bucket_name)
                
                if bucket:
                    # Update bucket metadata
                    await bucket._save_metadata()
                    logger.debug(f"Updated metadata for bucket '{bucket_name}'")
            
        except Exception as e:
            logger.error(f"Error updating bucket indexes: {e}")
    
    async def _export_buckets_to_parquet(self):
        """Export bucket data to parquet files."""
        try:
            if not self.bucket_vfs_manager or not ARROW_AVAILABLE:
                return
            
            # Get list of all buckets
            buckets_result = await self.bucket_vfs_manager.list_buckets()
            if not buckets_result.get("success", False):
                return
            
            buckets = buckets_result.get("data", {}).get("buckets", [])
            
            # Export bucket index metadata
            bucket_index_dir = self.data_dir / "bucket_index"
            bucket_index_dir.mkdir(exist_ok=True)
            
            # Create bucket index parquet
            if buckets:
                bucket_metadata = []
                
                for bucket_info in buckets:
                    bucket_name = bucket_info["name"]
                    bucket = await self.bucket_vfs_manager.get_bucket(bucket_name)
                    
                    if bucket:
                        metadata = {
                            "bucket_name": bucket.name,
                            "bucket_type": bucket.bucket_type.value if hasattr(bucket, 'bucket_type') else "standard",
                            "vfs_structure": bucket.vfs_structure.value if hasattr(bucket, 'vfs_structure') else "flat",
                            "file_count": await self._get_bucket_file_count(bucket),
                            "total_size": await self._get_bucket_total_size(bucket),
                            "last_modified": bucket_info.get("modified", datetime.now().isoformat()),
                            "root_cid": bucket_info.get("root_cid", ""),
                            "created_at": bucket_info.get("created", datetime.now().isoformat()),
                            "updated_at": datetime.now().isoformat()
                        }
                        bucket_metadata.append(metadata)
                        
                        # Export individual bucket VFS index
                        await self._export_bucket_vfs_index(bucket)
                
                # Write bucket index parquet
                if bucket_metadata:
                    import pyarrow as pa
                    import pyarrow.parquet as pq
                    
                    df = pd.DataFrame(bucket_metadata)
                    bucket_index_parquet = bucket_index_dir / "bucket_index.parquet"
                    df.to_parquet(bucket_index_parquet)
                    
                    logger.debug(f"Exported {len(bucket_metadata)} buckets to parquet")
            
        except Exception as e:
            logger.error(f"Error exporting buckets to parquet: {e}")
    
    async def _export_bucket_vfs_index(self, bucket):
        """Export individual bucket VFS index to parquet."""
        try:
            if not ARROW_AVAILABLE:
                return
            
            # Create bucket-specific directory
            bucket_vfs_dir = self.data_dir / "bucket_vfs_indexes" / bucket.name
            bucket_vfs_dir.mkdir(parents=True, exist_ok=True)
            
            # Get bucket file listings
            files_result = await bucket.list_files()
            if files_result.get("success", False):
                files = files_result.get("data", {}).get("files", [])
                
                if files:
                    import pyarrow as pa
                    import pyarrow.parquet as pq
                    
                    # Create file metadata records
                    file_records = []
                    for file_info in files:
                        record = {
                            "bucket_name": bucket.name,
                            "file_path": file_info.get("path", ""),
                            "file_name": file_info.get("name", ""),
                            "file_size": file_info.get("size", 0),
                            "file_type": file_info.get("type", ""),
                            "content_hash": file_info.get("hash", ""),
                            "last_modified": file_info.get("modified", datetime.now().isoformat()),
                            "metadata": json.dumps(file_info.get("metadata", {})),
                            "updated_at": datetime.now().isoformat()
                        }
                        file_records.append(record)
                    
                    # Write VFS index parquet
                    df = pd.DataFrame(file_records)
                    vfs_index_parquet = bucket_vfs_dir / "vfs_index.parquet"
                    df.to_parquet(vfs_index_parquet)
                    
                    logger.debug(f"Exported VFS index for bucket '{bucket.name}' with {len(file_records)} files")
            
        except Exception as e:
            logger.error(f"Error exporting VFS index for bucket '{bucket.name}': {e}")
    
    async def _get_bucket_file_count(self, bucket) -> int:
        """Get file count for a bucket."""
        try:
            files_result = await bucket.list_files()
            if files_result.get("success", False):
                return len(files_result.get("data", {}).get("files", []))
            return 0
        except:
            return 0
    
    async def _get_bucket_total_size(self, bucket) -> int:
        """Get total size for a bucket."""
        try:
            files_result = await bucket.list_files()
            if files_result.get("success", False):
                total_size = 0
                for file_info in files_result.get("data", {}).get("files", []):
                    total_size += file_info.get("size", 0)
                return total_size
            return 0
        except:
            return 0


async def main():
    """Main entry point for the daemon."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS Kit Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9999, help="Port to bind to")
    parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Configuration directory")
    parser.add_argument("--data-dir", help="Data directory (default: ~/.ipfs_kit)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start daemon
    daemon = IPFSKitDaemon(
        host=args.host,
        port=args.port,
        config_dir=args.config_dir,
        data_dir=args.data_dir
    )
    
    print("=" * 80)
    print("🔧 IPFS KIT DAEMON")
    print("=" * 80)
    print(f"📍 API: http://{args.host}:{args.port}")
    print(f"📁 Config: {args.config_dir}")
    print(f"💾 Data: {daemon.data_dir}")
    print(f"🔍 Debug: {args.debug}")
    print("=" * 80)
    print("🚀 Starting daemon...")
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        print("\n🛑 Daemon interrupted by user")
        await daemon.stop()
    except Exception as e:
        print(f"❌ Daemon error: {e}")
        await daemon.stop()
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)

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

import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# FastAPI for daemon API
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Core IPFS Kit functionality
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager

# MCP backend components
from ..backends.health_monitor import BackendHealthMonitor
from ..backends.log_manager import BackendLogManager
from ..core.config_manager import SecureConfigManager

# Pin index management
import pandas as pd
import sqlite3

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
                 data_dir: str = None):
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
        
        # Daemon state
        self.running = False
        self.start_time = None
        
        # Background tasks
        self.background_tasks = set()
        
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
        
        # Health endpoints
        @app.get("/health")
        async def get_health():
            """Get comprehensive daemon health status."""
            if not self.health_monitor:
                raise HTTPException(status_code=503, detail="Health monitor not initialized")
            
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
            
            # Initialize IPFS Kit
            self.ipfs_kit = IPFSKit()
            logger.info("✓ IPFS Kit initialized")
            
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
        
        # Health monitoring task
        task1 = asyncio.create_task(self._health_monitoring_loop())
        self.background_tasks.add(task1)
        
        # Pin index update task
        task2 = asyncio.create_task(self._pin_index_update_loop())
        self.background_tasks.add(task2)
        
        # Log collection task
        task3 = asyncio.create_task(self._log_collection_loop())
        self.background_tasks.add(task3)
        
        logger.info(f"✓ Started {len(self.background_tasks)} background tasks")
    
    async def _health_monitoring_loop(self):
        """Background health monitoring loop."""
        logger.info("🏥 Starting health monitoring loop...")
        
        while self.running:
            try:
                # Check backend health every 30 seconds
                if self.health_monitor:
                    await self.health_monitor.check_all_backends_health()
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer if there's an error
    
    async def _pin_index_update_loop(self):
        """Background pin index update loop."""
        logger.info("📎 Starting pin index update loop...")
        
        while self.running:
            try:
                # Update pin index every 5 minutes
                await self._update_pin_index()
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in pin index update loop: {e}")
                await asyncio.sleep(600)  # Wait longer if there's an error
    
    async def _log_collection_loop(self):
        """Background log collection loop."""
        logger.info("📋 Starting log collection loop...")
        
        while self.running:
            try:
                # Collect logs every 60 seconds
                if self.log_manager:
                    await self.log_manager.collect_all_backend_logs()
                
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in log collection loop: {e}")
                await asyncio.sleep(120)  # Wait longer if there's an error
    
    async def _get_pin_index_data(self) -> Dict[str, Any]:
        """Get pin index data from parquet files."""
        try:
            pin_index_dir = self.data_dir / "enhanced_pin_index"
            
            if not pin_index_dir.exists():
                return {"pins": [], "total": 0, "error": "Pin index not found"}
            
            # Read enhanced pins parquet
            pins_file = pin_index_dir / "enhanced_pins.parquet"
            if pins_file.exists():
                df = pd.read_parquet(pins_file)
                pins_data = df.to_dict('records')
                
                return {
                    "pins": pins_data,
                    "total": len(pins_data),
                    "last_updated": pins_file.stat().st_mtime
                }
            else:
                return {"pins": [], "total": 0, "error": "Enhanced pins file not found"}
                
        except Exception as e:
            logger.error(f"Error reading pin index: {e}")
            return {"pins": [], "total": 0, "error": str(e)}
    
    async def _add_pin_with_replication(self, cid: str) -> Dict[str, Any]:
        """Add a pin with replication across backends."""
        try:
            if not self.ipfs_kit:
                return {"success": False, "error": "IPFS Kit not initialized"}
            
            # Add pin using IPFS Kit
            result = await self.ipfs_kit.pin_add(cid)
            
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
            
            # Remove pin using IPFS Kit
            result = await self.ipfs_kit.pin_rm(cid)
            
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
            
            # TODO: Implement pin index update logic
            # This would scan all backends and update the parquet files
            
            logger.debug("✓ Pin index updated")
            
        except Exception as e:
            logger.error(f"Error updating pin index: {e}")
    
    async def _start_backend(self, backend_name: str) -> Dict[str, Any]:
        """Start a specific backend service."""
        try:
            if not self.ipfs_kit:
                return {"success": False, "error": "IPFS Kit not initialized"}
            
            # Use daemon manager to start backend
            daemon_manager = self.ipfs_kit.daemon_manager
            
            if backend_name == "ipfs":
                result = daemon_manager.start_ipfs_daemon()
            elif backend_name == "cluster":
                result = daemon_manager.start_cluster_daemon()
            elif backend_name == "lotus":
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
            daemon_manager = self.ipfs_kit.daemon_manager
            
            if backend_name == "ipfs":
                result = daemon_manager.stop_ipfs_daemon()
            elif backend_name == "cluster":
                result = daemon_manager.stop_cluster_daemon()
            elif backend_name == "lotus":
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
            
            # Get logs from log manager
            logs = await self.log_manager.get_backend_logs(backend_name, lines)
            return logs
            
        except Exception as e:
            logger.error(f"Error getting logs for {backend_name}: {e}")
            return [f"Error getting logs: {e}"]
    
    async def _get_daemon_config(self) -> Dict[str, Any]:
        """Get daemon configuration."""
        try:
            if not self.config_manager:
                return {"error": "Config manager not initialized"}
            
            # Get configuration from secure config manager
            config = self.config_manager.get_config("daemon")
            return config or {}
            
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return {"error": str(e)}
    
    async def _update_daemon_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update daemon configuration."""
        try:
            if not self.config_manager:
                return {"success": False, "error": "Config manager not initialized"}
            
            # Update configuration via secure config manager
            self.config_manager.set_config("daemon", config_data)
            
            return {"success": True, "config": config_data}
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return {"success": False, "error": str(e)}
    
    async def start(self):
        """Start the daemon."""
        logger.info("🚀 Starting IPFS Kit Daemon...")
        
        # Initialize components
        if not await self.initialize():
            logger.error("❌ Failed to initialize daemon")
            return False
        
        # Set daemon state
        self.running = True
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
        
        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        
        logger.info("✓ Daemon shutdown complete")
    
    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("🛑 Stopping IPFS Kit Daemon...")
        
        self.running = False
        
        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        
        # Cleanup components
        if self.health_monitor:
            # Stop health monitoring
            pass
        
        if self.ipfs_kit:
            # Cleanup IPFS Kit
            pass
        
        logger.info("✓ IPFS Kit Daemon stopped")


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
    asyncio.run(main())

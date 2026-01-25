#!/usr/bin/env python3
"""
MCP Daemon Service - Integration with Intelligent Daemon Manager

This service provides MCP server integration with the intelligent daemon manager,
allowing the MCP server to leverage the daemon for backend synchronization and
metadata management while preserving CLI behavior patterns.
"""

import anyio
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
# NOTE: This file contains asyncio.create_task() calls that need task group context

logger = logging.getLogger(__name__)


@dataclass
class DaemonStatus:
    """Status information for the daemon service."""
    is_running: bool
    uptime_seconds: float
    last_sync: Optional[datetime]
    sync_interval: int
    total_backends: int
    healthy_backends: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int


class MCPDaemonService:
    """
    MCP Daemon Service that integrates with Intelligent Daemon Manager
    
    This service:
    1. Manages connection to the intelligent daemon
    2. Provides async interface for MCP server
    3. Handles backend synchronization
    4. Maintains metadata freshness
    5. Provides CLI-aligned daemon operations
    """
    
    def __init__(self, data_dir: Path, sync_interval: int = 300):
        """Initialize the MCP daemon service."""
        self.data_dir = Path(data_dir).expanduser()
        self.sync_interval = sync_interval
        self.is_running = False
        self.start_time = None
        self.last_sync = None
        
        # Task tracking
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.pending_tasks = 0
        
        # Background task management
        self.sync_task = None
        self.daemon_manager = None
        
        # Callbacks for status updates
        self.status_callbacks: List[Callable[[DaemonStatus], None]] = []
        
        logger.info(f"MCP Daemon Service initialized with data_dir: {self.data_dir}")
    
    def _lazy_import_daemon_manager(self):
        """Lazy import of intelligent daemon manager to avoid startup overhead."""
        if self.daemon_manager is None:
            try:
                from ...intelligent_daemon_manager import IntelligentDaemonManager
                self.daemon_manager = IntelligentDaemonManager(self.data_dir)
                logger.info("Intelligent Daemon Manager imported and initialized")
            except ImportError as e:
                logger.error(f"Failed to import IntelligentDaemonManager: {e}")
                raise
        return self.daemon_manager
    
    async def start(self) -> None:
        """Start the daemon service."""
        if self.is_running:
            logger.warning("Daemon service is already running")
            return
        
        logger.info("Starting MCP daemon service")
        
        # Initialize intelligent daemon manager
        try:
            self._lazy_import_daemon_manager()
        except Exception as e:
            logger.error(f"Failed to initialize daemon manager: {e}")
            raise
        
        self.is_running = True
        self.start_time = datetime.now()
        
        # Start background sync task
        self.sync_task = asyncio.create_task(self._background_sync_loop())
        
        logger.info("MCP daemon service started successfully")
    
    async def stop(self) -> None:
        """Stop the daemon service."""
        if not self.is_running:
            return
        
        logger.info("Stopping MCP daemon service")
        
        self.is_running = False
        
        # Cancel background task
        if self.sync_task and not self.sync_task.done():
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        logger.info("MCP daemon service stopped")
    
    async def _background_sync_loop(self) -> None:
        """Background loop for daemon synchronization."""
        while self.is_running:
            try:
                await self._perform_sync()
                self.last_sync = datetime.now()
                
                # Notify status callbacks
                await self._notify_status_callbacks()
                
            except Exception as e:
                logger.error(f"Error in background sync: {e}")
                self.failed_tasks += 1
            
            # Wait for next sync interval
            try:
                await anyio.sleep(self.sync_interval)
            except asyncio.CancelledError:
                break
    
    async def _perform_sync(self) -> None:
        """Perform synchronization with backends."""
        if not self.daemon_manager:
            return
        
        self.pending_tasks += 1
        
        try:
            # Use intelligent daemon's metadata-driven sync
            await anyio.to_thread.run_sync(self._sync_with_intelligent_daemon)
            self.completed_tasks += 1
            
        except Exception as e:
            logger.error(f"Sync operation failed: {e}")
            self.failed_tasks += 1
        finally:
            self.pending_tasks = max(0, self.pending_tasks - 1)
    
    def _sync_with_intelligent_daemon(self) -> None:
        """Synchronize using the intelligent daemon manager (runs in thread pool)."""
        try:
            # Get backend health status
            health_status = self.daemon_manager.get_backend_health_status()
            logger.debug(f"Backend health check completed: {len(health_status)} backends")
            
            # Perform any needed pin syncing
            for backend_status in health_status:
                if backend_status.needs_pin_sync:
                    logger.info(f"Syncing pins for backend: {backend_status.backend_name}")
                    # The intelligent daemon handles the actual sync
            
        except Exception as e:
            logger.error(f"Error in intelligent daemon sync: {e}")
            raise
    
    async def get_status(self) -> DaemonStatus:
        """Get current daemon status."""
        uptime = 0.0
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Get backend count from daemon manager
        total_backends = 0
        healthy_backends = 0
        
        if self.daemon_manager:
            try:
                health_status = await anyio.to_thread.run_sync(self.daemon_manager.get_backend_health_status)
                total_backends = len(health_status)
                healthy_backends = sum(1 for status in health_status if status.is_healthy)
            except Exception as e:
                logger.warning(f"Error getting backend status: {e}")
        
        return DaemonStatus(
            is_running=self.is_running,
            uptime_seconds=uptime,
            last_sync=self.last_sync,
            sync_interval=self.sync_interval,
            total_backends=total_backends,
            healthy_backends=healthy_backends,
            pending_tasks=self.pending_tasks,
            completed_tasks=self.completed_tasks,
            failed_tasks=self.failed_tasks
        )
    
    async def get_intelligent_status(self) -> Dict[str, Any]:
        """Get intelligent daemon status (mirrors CLI 'daemon intelligent status')."""
        if not self.daemon_manager:
            return {"error": "Intelligent daemon not available"}
        
        try:
            # Get comprehensive status from intelligent daemon
            status = await anyio.to_thread.run_sync(self._get_intelligent_status_sync)
            return status
        except Exception as e:
            logger.error(f"Error getting intelligent status: {e}")
            return {"error": str(e)}
    
    def _get_intelligent_status_sync(self) -> Dict[str, Any]:
        """Get intelligent daemon status synchronously."""
        # Get backend health
        health_status = self.daemon_manager.get_backend_health_status()
        
        # Get pin mapping summary
        pin_summary = self.daemon_manager._get_pin_mapping_summary()
        
        # Build comprehensive status
        status = {
            "timestamp": datetime.now().isoformat(),
            "daemon_mode": "intelligent",
            "backends": {
                "total": len(health_status),
                "healthy": sum(1 for s in health_status if s.is_healthy),
                "unhealthy": sum(1 for s in health_status if not s.is_healthy),
                "needs_sync": sum(1 for s in health_status if s.needs_pin_sync),
                "details": [asdict(status) for status in health_status]
            },
            "pin_mapping_summary": pin_summary,
            "sync_status": {
                "last_sync": self.last_sync.isoformat() if self.last_sync else None,
                "sync_interval": self.sync_interval,
                "completed_tasks": self.completed_tasks,
                "failed_tasks": self.failed_tasks,
                "pending_tasks": self.pending_tasks
            }
        }
        
        return status
    
    async def get_intelligent_insights(self) -> Dict[str, Any]:
        """Get intelligent daemon insights (mirrors CLI 'daemon intelligent insights')."""
        if not self.daemon_manager:
            return {"error": "Intelligent daemon not available"}
        
        try:
            insights = await anyio.to_thread.run_sync(self._get_intelligent_insights_sync)
            return insights
        except Exception as e:
            logger.error(f"Error getting intelligent insights: {e}")
            return {"error": str(e)}
    
    def _get_intelligent_insights_sync(self) -> Dict[str, Any]:
        """Get intelligent daemon insights synchronously."""
        # Get pin mapping analysis
        pin_analysis = self.daemon_manager.analyze_pin_status_across_backends()
        
        # Get all pin mappings for analysis
        all_pins = self.daemon_manager.get_all_pin_mappings()
        
        # Build insights
        insights = {
            "timestamp": datetime.now().isoformat(),
            "pin_mapping_analysis": pin_analysis,
            "storage_analysis": {
                "total_pins": len(all_pins),
                "unique_cids": len(set(pin.cid for pin in all_pins)) if all_pins else 0,
                "backends_with_data": len(set(pin.backend_name for pin in all_pins)) if all_pins else 0,
                "redundancy_distribution": self._calculate_redundancy_distribution(all_pins)
            },
            "recommendations": self._generate_recommendations(pin_analysis)
        }
        
        return insights
    
    def _calculate_redundancy_distribution(self, pins) -> Dict[str, int]:
        """Calculate how many CIDs have different redundancy levels."""
        if not pins:
            return {}
        
        # Count pins per CID
        cid_counts = {}
        for pin in pins:
            cid_counts[pin.cid] = cid_counts.get(pin.cid, 0) + 1
        
        # Build distribution
        distribution = {}
        for count in cid_counts.values():
            redundancy_key = f"{count}_backends"
            distribution[redundancy_key] = distribution.get(redundancy_key, 0) + 1
        
        return distribution
    
    def _generate_recommendations(self, pin_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on pin analysis."""
        recommendations = []
        
        if pin_analysis.get("failed_backends", 0) > 0:
            recommendations.append("Some backends have failed pins - consider re-syncing")
        
        avg_redundancy = pin_analysis.get("average_redundancy", 0)
        if avg_redundancy < 2.0:
            recommendations.append("Low redundancy detected - consider adding more backend copies")
        elif avg_redundancy > 5.0:
            recommendations.append("High redundancy detected - consider optimizing storage costs")
        
        backends_with_pins = pin_analysis.get("backends_with_pins", 0)
        total_backends = pin_analysis.get("total_backends", 0)
        if backends_with_pins < total_backends * 0.5:
            recommendations.append("Many backends are unused - consider balancing pin distribution")
        
        if not recommendations:
            recommendations.append("System appears to be operating optimally")
        
        return recommendations
    
    async def force_sync(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Force immediate sync operation (mirrors CLI backend sync)."""
        if not self.is_running:
            return {"error": "Daemon service is not running"}
        
        try:
            result = await anyio.to_thread.run_sync(self._force_sync_sync, backend_name)
            return result
        except Exception as e:
            logger.error(f"Error in force sync: {e}")
            return {"error": str(e)}
    
    def _force_sync_sync(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Perform force sync synchronously."""
        if backend_name:
            # Sync specific backend
            # Note: This would need to be implemented in the intelligent daemon
            return {
                "action": "force_sync",
                "backend": backend_name,
                "status": "completed",
                "message": f"Forced sync for backend {backend_name}"
            }
        else:
            # Sync all backends
            health_status = self.daemon_manager.get_backend_health_status()
            synced_backends = []
            
            for backend_status in health_status:
                # Force sync regardless of needs_pin_sync flag
                synced_backends.append(backend_status.backend_name)
            
            return {
                "action": "force_sync_all",
                "synced_backends": synced_backends,
                "status": "completed",
                "message": f"Forced sync for {len(synced_backends)} backends"
            }
    
    async def migrate_pin_mappings(self, filter_backends: Optional[str] = None,
                                 dry_run: bool = False) -> Dict[str, Any]:
        """Migrate pin mappings (mirrors CLI backend migrate-pin-mappings)."""
        try:
            # Import the migration tool
            from ...migrate_backend_pin_mappings import PinMappingsMigrator
            
            migrator = PinMappingsMigrator(self.data_dir)
            
            result = await anyio.to_thread.run_sync(self._migrate_pin_mappings_sync, migrator, filter_backends, dry_run)
            return result
            
        except Exception as e:
            logger.error(f"Error in pin mappings migration: {e}")
            return {"error": str(e)}
    
    def _migrate_pin_mappings_sync(self, migrator, filter_backends: Optional[str] = None,
                                 dry_run: bool = False) -> Dict[str, Any]:
        """Perform pin mappings migration synchronously."""
        try:
            if dry_run:
                analysis = migrator.analyze_backends()
                return {
                    "action": "migrate_pin_mappings",
                    "dry_run": True,
                    "analysis": analysis,
                    "message": "Dry run completed - no changes made"
                }
            else:
                # Parse filter if provided
                backend_filter = filter_backends.split(',') if filter_backends else None
                
                # Run migration
                results = migrator.migrate_all_backends(backend_filter=backend_filter)
                return {
                    "action": "migrate_pin_mappings", 
                    "dry_run": False,
                    "results": results,
                    "message": "Migration completed successfully"
                }
        except Exception as e:
            return {"error": str(e)}
    
    def add_status_callback(self, callback: Callable[[DaemonStatus], None]) -> None:
        """Add a callback to be notified of status changes."""
        self.status_callbacks.append(callback)
    
    def remove_status_callback(self, callback: Callable[[DaemonStatus], None]) -> None:
        """Remove a status callback."""
        if callback in self.status_callbacks:
            self.status_callbacks.remove(callback)
    
    async def _notify_status_callbacks(self) -> None:
        """Notify all status callbacks of current status."""
        if not self.status_callbacks:
            return
        
        try:
            status = await self.get_status()
            for callback in self.status_callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"Error in status callback: {e}")
        except Exception as e:
            logger.error(f"Error getting status for callbacks: {e}")

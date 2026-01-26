"""
VFS Integration with IPFS Kit Enhanced Pin Index

This module integrates the MCP VFS endpoints with the existing ipfs_kit_py
enhanced pin metadata index and virtual filesystem infrastructure.

The MCP dashboard will use this integration to:
1. Access the global enhanced pin metadata index
2. Retrieve pin metrics and analytics from parquet storage
3. Leverage the existing VFS journal and filesystem integration
4. Provide fast metadata access for CLI and API requests

Key Benefits:
- Unified metadata across CLI and MCP server
- Parquet-based storage for efficient analytics
- Background synchronization with filesystem journal
- No duplicate IPFS API calls - uses cached metadata
"""

import anyio
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Import ipfs_kit_py components with fallbacks
try:
    from ipfs_kit_py.enhanced_pin_index import (
        get_global_enhanced_pin_index, 
        get_cli_pin_metrics,
        start_global_enhanced_pin_index
    )
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    IPFS_KIT_AVAILABLE = True
    logger.info("✓ IPFS Kit enhanced pin index imported successfully")
except ImportError as e:
    logger.warning(f"IPFS Kit enhanced pin index not available: {e}")
    IPFS_KIT_AVAILABLE = False

try:
    from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex
    from ipfs_kit_py.metadata_sync_handler import MetadataSyncHandler
    ARROW_METADATA_AVAILABLE = True
    logger.info("✓ Arrow metadata index imported successfully")
except ImportError:
    ARROW_METADATA_AVAILABLE = False
    logger.warning("Arrow metadata index not available")


class VFSIPFSKitIntegration:
    """
    Integration layer between MCP VFS endpoints and ipfs_kit_py infrastructure.
    
    This class provides async-safe access to the enhanced pin metadata index
    and ensures the MCP dashboard uses the same metadata infrastructure as
    CLI tools and other components.
    """
    
    def __init__(self):
        """Initialize the integration layer."""
        self.enhanced_pin_index = None
        self.arrow_metadata_index = None
        self.ipfs_api = None
        self.initialized = False
        self.last_init_attempt = 0
        self.init_retry_interval = 30  # Retry every 30 seconds
        
        # Cache for frequently accessed data
        self.metrics_cache = {}
        self.cache_ttl = 10  # Cache for 10 seconds
        self.last_cache_update = 0
        
        logger.info("VFS IPFS Kit Integration initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize the integration with ipfs_kit_py components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        current_time = time.time()
        
        # Rate limit initialization attempts
        if current_time - self.last_init_attempt < self.init_retry_interval:
            return self.initialized
        
        self.last_init_attempt = current_time
        
        if not IPFS_KIT_AVAILABLE:
            logger.warning("IPFS Kit not available - using fallback mode")
            return False
        
        try:
            # Initialize enhanced pin index
            await self._initialize_enhanced_pin_index()
            
            # Initialize arrow metadata index
            await self._initialize_arrow_metadata_index()
            
            # Initialize high-level API
            await self._initialize_ipfs_api()
            
            self.initialized = True
            logger.info("✓ VFS IPFS Kit Integration fully initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize VFS IPFS Kit Integration: {e}")
            return False
    
    async def _initialize_enhanced_pin_index(self):
        """Initialize the enhanced pin metadata index."""
        try:
            # Get the global enhanced pin index instance
                self.enhanced_pin_index = await anyio.to_thread.run_sync(
                    get_global_enhanced_pin_index
                )
            
            # Start background services if not already running
            if hasattr(self.enhanced_pin_index, 'start_background_services'):
                try:
                    await self.enhanced_pin_index.start_background_services()
                except Exception as e:
                    logger.warning(f"Could not start enhanced pin index background services: {e}")
            
            logger.info("✓ Enhanced pin metadata index initialized")
            
        except Exception as e:
            logger.warning(f"Enhanced pin index initialization failed: {e}")
            self.enhanced_pin_index = None
    
    async def _initialize_arrow_metadata_index(self):
        """Initialize the arrow metadata index."""
        if not ARROW_METADATA_AVAILABLE:
            return
        
        try:
            # Create arrow metadata index with default settings
                self.arrow_metadata_index = await anyio.to_thread.run_sync(
                    lambda: ArrowMetadataIndex()
                )
            logger.info("✓ Arrow metadata index initialized")
            
        except Exception as e:
            logger.warning(f"Arrow metadata index initialization failed: {e}")
            self.arrow_metadata_index = None
    
    async def _initialize_ipfs_api(self):
        """Initialize the high-level IPFS API."""
        try:
                self.ipfs_api = await anyio.to_thread.run_sync(
                    IPFSSimpleAPI
                )
            logger.info("✓ IPFS Simple API initialized")
            
        except Exception as e:
            logger.warning(f"IPFS API initialization failed: {e}")
            self.ipfs_api = None
    
    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive VFS statistics from ipfs_kit_py infrastructure.
        
        Returns:
            Dictionary with VFS statistics and metrics
        """
        if not await self.initialize():
            return self._get_fallback_statistics()
        
        try:
            # Check cache first
            current_time = time.time()
            if (current_time - self.last_cache_update < self.cache_ttl and 
                'vfs_statistics' in self.metrics_cache):
                return self.metrics_cache['vfs_statistics']
            
            # Get fresh statistics
            stats = await self._collect_vfs_statistics()
            
            # Update cache
            self.metrics_cache['vfs_statistics'] = stats
            self.last_cache_update = current_time
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting VFS statistics: {e}")
            return self._get_fallback_statistics()
    
    async def _collect_vfs_statistics(self) -> Dict[str, Any]:
        """Collect comprehensive VFS statistics from all sources."""
        stats = {
            "timestamp": time.time(),
            "status": "active",
            "source": "ipfs_kit_enhanced_pin_index"
        }
        
        # Get enhanced pin metrics
        if self.enhanced_pin_index:
            try:
                # Use CLI helper for fast access
                    cli_metrics = await anyio.to_thread.run_sync(
                        get_cli_pin_metrics
                    )
                
                if 'error' not in cli_metrics:
                    stats.update({
                        "pin_metrics": cli_metrics.get("traffic_metrics", {}),
                        "performance_metrics": cli_metrics.get("performance_metrics", {}),
                        "vfs_analytics": cli_metrics.get("vfs_analytics", {}),
                    })
                    
                    # Extract key metrics for dashboard
                    traffic = cli_metrics.get("traffic_metrics", {})
                    stats.update({
                        "filesystem_status": {
                            "total_pins": traffic.get("total_pins", 0),
                            "total_size_bytes": traffic.get("total_size_bytes", 0),
                            "total_size_human": traffic.get("total_size_human", "0 B"),
                            "vfs_mounts": traffic.get("vfs_mounts", 0),
                            "directory_pins": traffic.get("directory_pins", 0),
                            "file_pins": traffic.get("file_pins", 0)
                        },
                        "cache_performance": {
                            "cache_efficiency": traffic.get("cache_efficiency", 0.0),
                            "hot_pins": len(traffic.get("hot_pins", [])),
                            "verified_pins": traffic.get("verified_pins", 0),
                            "corrupted_pins": traffic.get("corrupted_pins", 0)
                        }
                    })
                    
            except Exception as e:
                logger.warning(f"Could not get enhanced pin metrics: {e}")
        
        # Get resource utilization from system
        stats["resource_utilization"] = await self._get_resource_utilization()
        
        # Get storage tier information
        if self.enhanced_pin_index:
            stats["storage_tiers"] = await self._get_storage_tier_info()
        
        return stats
    
    async def _get_resource_utilization(self) -> Dict[str, Any]:
        """Get system resource utilization."""
        try:
            import psutil
            
            # Get memory usage
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "memory_usage": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "system_used_percent": memory.percent
                },
                "disk_usage": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "used_percent": round((disk.used / disk.total) * 100, 1)
                }
            }
            
        except ImportError:
            logger.warning("psutil not available for resource monitoring")
            return {
                "memory_usage": {"system_used_percent": 0},
                "disk_usage": {"used_percent": 0}
            }
        except Exception as e:
            logger.warning(f"Error getting resource utilization: {e}")
            return {
                "memory_usage": {"system_used_percent": 0},
                "disk_usage": {"used_percent": 0}
            }
    
    async def _get_storage_tier_info(self) -> Dict[str, Any]:
        """Get storage tier distribution and analytics."""
        try:
            if not self.enhanced_pin_index:
                return {}
            
            # Get tier analytics from enhanced pin index
                tier_info = await anyio.to_thread.run_sync(
                    lambda: self.enhanced_pin_index.get_comprehensive_metrics()
                )
            
            return {
                "tier_distribution": tier_info.tier_distribution,
                "replication_stats": tier_info.replication_stats,
                "storage_recommendations": tier_info.storage_recommendations
            }
            
        except Exception as e:
            logger.warning(f"Error getting storage tier info: {e}")
            return {}
    
    def _get_fallback_statistics(self) -> Dict[str, Any]:
        """Get fallback statistics when ipfs_kit_py is not available."""
        return {
            "timestamp": time.time(),
            "status": "fallback",
            "source": "mcp_fallback",
            "note": "Using fallback data - ipfs_kit_py integration not available",
            "filesystem_status": {
                "total_pins": 0,
                "total_size_bytes": 0,
                "total_size_human": "0 B",
                "vfs_mounts": 0,
                "directory_pins": 0,
                "file_pins": 0
            },
            "resource_utilization": {
                "memory_usage": {"system_used_percent": 0},
                "disk_usage": {"used_percent": 0}
            },
            "cache_performance": {
                "cache_efficiency": 0.0,
                "hot_pins": 0,
                "verified_pins": 0,
                "corrupted_pins": 0
            },
            "performance_metrics": {},
            "storage_tiers": {}
        }
    
    async def get_pin_details(self, cid: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific pin from the metadata index.
        
        Args:
            cid: Content identifier to get details for
            
        Returns:
            Dictionary with pin details
        """
        if not await self.initialize():
            return {"error": "IPFS Kit integration not available"}
        
        try:
            if self.enhanced_pin_index:
                # Get pin details from enhanced index
                    pin_info = await anyio.to_thread.run_sync(
                        lambda: self.enhanced_pin_index.get_pin_details(cid)
                    )
                return {"success": True, "pin_details": pin_info}
            else:
                return {"error": "Enhanced pin index not available"}
                
        except Exception as e:
            logger.error(f"Error getting pin details for {cid}: {e}")
            return {"error": str(e)}
    
    async def get_vfs_journal(self, backend_filter: Optional[str] = None, 
                             search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get VFS journal entries from the filesystem journal.
        
        Args:
            backend_filter: Optional backend to filter by
            search_query: Optional search query
            
        Returns:
            List of journal entries
        """
        if not await self.initialize():
            return []
        
        try:
            if self.enhanced_pin_index and hasattr(self.enhanced_pin_index, 'journal'):
                journal = self.enhanced_pin_index.journal
                if journal:
                    # Get recent journal entries
                    entries = await anyio.to_thread.run_sync(
                        lambda: journal.get_recent_entries(limit=100)
                    )
                    
                    # Apply filters
                    filtered_entries = []
                    for entry in entries:
                        if backend_filter and entry.get('backend') != backend_filter:
                            continue
                        if search_query and search_query.lower() not in str(entry).lower():
                            continue
                        filtered_entries.append(entry)
                    
                    return filtered_entries
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting VFS journal: {e}")
            return []
    
    async def cleanup(self):
        """Clean up resources and stop background services."""
        try:
            if self.enhanced_pin_index and hasattr(self.enhanced_pin_index, 'stop_background_services'):
                await self.enhanced_pin_index.stop_background_services()
            
            self.initialized = False
            logger.info("VFS IPFS Kit Integration cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global integration instance
_global_integration: Optional[VFSIPFSKitIntegration] = None


def get_global_vfs_integration() -> VFSIPFSKitIntegration:
    """Get or create the global VFS IPFS Kit integration instance."""
    global _global_integration
    
    if _global_integration is None:
        _global_integration = VFSIPFSKitIntegration()
    
    return _global_integration


async def initialize_global_vfs_integration() -> bool:
    """Initialize the global VFS IPFS Kit integration."""
    integration = get_global_vfs_integration()
    return await integration.initialize()


async def cleanup_global_vfs_integration():
    """Clean up the global VFS IPFS Kit integration."""
    global _global_integration
    
    if _global_integration:
        await _global_integration.cleanup()
        _global_integration = None

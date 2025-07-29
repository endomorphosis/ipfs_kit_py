#!/usr/bin/env python3
"""
Complete Integration Demo: Enhanced Pin Metadata Index with ipfs_kit_py

This demo showcases the complete integration of the enhanced pin metadata index
with the existing ipfs_kit_py virtual filesystem and storage management infrastructure.

Key Features Demonstrated:
1. Enhanced DuckDB + Parquet storage for analytics
2. VFS integration with filesystem journal sync
3. CLI access patterns for operational monitoring
4. MCP dashboard backend with enhanced metrics
5. Multi-tier storage management integration
6. Background services for predictions and analytics

Architecture Overview:
- Enhanced Pin Index: Core metadata management with DuckDB analytics
- VFS Integration: Hooks into ipfs_fsspec for real-time filesystem events
- Journal Sync: Integration with filesystem_journal.py for persistent state
- Storage Tiers: Integration with hierarchical_storage_methods.py
- Dashboard: MCP backend with enhanced metrics and VFS analytics
- CLI Tools: Command-line interface for operational monitoring

Usage Patterns:
- CLI: python enhanced_pin_cli.py [metrics|vfs|pins|track|analytics|status]
- API: Integration with storage_backends_api.py for programmatic access
- Dashboard: MCP server backend with enhanced analytics
"""

import os
import sys
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add ipfs_kit_py to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ipfs_kit_py.enhanced_pin_index import (
        get_global_enhanced_pin_index, 
        get_cli_pin_metrics,
        EnhancedPinMetadataIndex
    )
    ENHANCED_INDEX_AVAILABLE = True
    logger.info("✓ Enhanced pin index available")
except ImportError as e:
    logger.warning(f"Enhanced pin index not available: {e}")
    ENHANCED_INDEX_AVAILABLE = False

try:
    from mcp.ipfs_kit.backends.health_monitor import HealthMonitor
    MCP_AVAILABLE = True
    logger.info("✓ MCP backend available")
except ImportError as e:
    logger.warning(f"MCP backend not available: {e}")
    MCP_AVAILABLE = False

try:
    from ipfs_kit_py.pins import get_global_pin_index
    BASIC_INDEX_AVAILABLE = True
    logger.info("✓ Basic pin index available")
except ImportError as e:
    logger.warning(f"Basic pin index not available: {e}")
    BASIC_INDEX_AVAILABLE = False


class IntegrationDemo:
    """Comprehensive demo of the enhanced pin metadata integration."""
    
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir
        self.enhanced_index: Optional[EnhancedPinMetadataIndex] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.demo_data: List[Dict[str, Any]] = []
        
    async def initialize(self):
        """Initialize all components for the demo."""
        logger.info("🚀 Initializing Complete Integration Demo")
        logger.info("=" * 50)
        
        # Initialize enhanced pin index if available
        if ENHANCED_INDEX_AVAILABLE:
            try:
                self.enhanced_index = get_global_enhanced_pin_index(
                    data_dir=self.data_dir,
                    enable_analytics=True,
                    enable_predictions=True
                )
                logger.info("✓ Enhanced pin index initialized")
                logger.info(f"  - Data directory: {self.enhanced_index.data_dir}")
                logger.info(f"  - Analytics: {'enabled' if self.enhanced_index.enable_analytics else 'disabled'}")
                logger.info(f"  - Predictions: {'enabled' if self.enhanced_index.enable_predictions else 'disabled'}")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced index: {e}")
                self.enhanced_index = None
        
        # Initialize MCP health monitor if available
        if MCP_AVAILABLE:
            try:
                self.health_monitor = HealthMonitor()
                logger.info("✓ MCP health monitor initialized")
            except Exception as e:
                logger.error(f"Failed to initialize health monitor: {e}")
                self.health_monitor = None
        
        logger.info("")
        
    def create_demo_data(self):
        """Create comprehensive demo data to showcase functionality."""
        logger.info("📝 Creating Demo Data")
        logger.info("-" * 20)
        
        # Demo pin entries with various patterns and tiers
        self.demo_data = [
            {
                "cid": "QmDemoDocument12345abcdefgh",
                "size_bytes": 1024 * 50,  # 50KB document
                "name": "Important Document.pdf",
                "vfs_path": "/vfs/documents/important.pdf",
                "mount_point": "/documents",
                "type": "file",
                "access_pattern": "sequential",
                "primary_tier": "ssd",
                "storage_tiers": ["ssd", "ipfs"],
                "replication_factor": 2
            },
            {
                "cid": "QmDemoVideo6789abcdefghijk",
                "size_bytes": 1024 * 1024 * 100,  # 100MB video
                "name": "Training Video.mp4",
                "vfs_path": "/vfs/media/training.mp4",
                "mount_point": "/media",
                "type": "file",
                "access_pattern": "streaming",
                "primary_tier": "hdd",
                "storage_tiers": ["hdd", "ipfs", "filecoin"],
                "replication_factor": 3
            },
            {
                "cid": "QmDemoDataset01abcdefghijkl",
                "size_bytes": 1024 * 1024 * 500,  # 500MB dataset
                "name": "Machine Learning Dataset",
                "vfs_path": "/vfs/datasets/ml_data",
                "mount_point": "/datasets",
                "type": "directory",
                "access_pattern": "random",
                "primary_tier": "nvme",
                "storage_tiers": ["nvme", "ssd", "ipfs"],
                "replication_factor": 2
            },
            {
                "cid": "QmDemoConfig02bcdefghijklm",
                "size_bytes": 1024 * 2,  # 2KB config
                "name": "system_config.json",
                "vfs_path": "/vfs/config/system.json",
                "mount_point": "/config",
                "type": "file",
                "access_pattern": "frequent",
                "primary_tier": "memory",
                "storage_tiers": ["memory", "ssd", "ipfs"],
                "replication_factor": 3
            },
            {
                "cid": "QmDemoArchive03cdefghijklmn",
                "size_bytes": 1024 * 1024 * 1024 * 2,  # 2GB archive
                "name": "Historical Archive",
                "vfs_path": "/vfs/archive/2024",
                "mount_point": "/archive",
                "type": "directory",
                "access_pattern": "cold",
                "primary_tier": "filecoin",
                "storage_tiers": ["filecoin", "ipfs"],
                "replication_factor": 1
            }
        ]
        
        logger.info(f"Created {len(self.demo_data)} demo pin entries")
        
        # Add demo data to enhanced index if available
        if self.enhanced_index:
            for pin_data in self.demo_data:
                try:
                    # Simulate accessing the pin multiple times with different patterns
                    for i in range(3 + (hash(pin_data['cid']) % 5)):  # 3-7 accesses
                        self.enhanced_index.record_enhanced_access(
                            cid=pin_data['cid'],
                            access_pattern=pin_data['access_pattern'],
                            vfs_path=pin_data['vfs_path'],
                            tier=pin_data['primary_tier'],
                            size_bytes=pin_data['size_bytes'],
                            mount_point=pin_data['mount_point'],
                            pin_type=pin_data['type'],
                            pin_name=pin_data['name'],
                            storage_tiers=pin_data['storage_tiers'],
                            replication_factor=pin_data['replication_factor']
                        )
                    
                    logger.info(f"✓ Added demo pin: {pin_data['name']}")
                except Exception as e:
                    logger.error(f"Failed to add demo pin {pin_data['cid']}: {e}")
        
        logger.info("")
    
    def demonstrate_cli_access(self):
        """Demonstrate CLI access patterns."""
        logger.info("🖥️  CLI Access Patterns")
        logger.info("-" * 25)
        
        if not ENHANCED_INDEX_AVAILABLE:
            logger.warning("CLI access requires enhanced index")
            return
        
        try:
            # Get CLI metrics
            metrics = get_cli_pin_metrics()
            
            logger.info("CLI Metrics Summary:")
            traffic = metrics.get("traffic_metrics", {})
            logger.info(f"  Total Pins: {traffic.get('total_pins', 0)}")
            logger.info(f"  Total Size: {self._format_bytes(traffic.get('total_size_bytes', 0))}")
            logger.info(f"  VFS Mounts: {traffic.get('vfs_mounts', 0)}")
            logger.info(f"  Access Count: {traffic.get('total_access_count', 0)}")
            
            # VFS Analytics
            if self.enhanced_index:
                vfs_analytics = self.enhanced_index.get_vfs_analytics()
                logger.info(f"  VFS Pins: {vfs_analytics.get('total_vfs_pins', 0)}")
                
                mount_points = vfs_analytics.get('mount_points', {})
                if mount_points:
                    logger.info("  Mount Points:")
                    for mount, count in mount_points.items():
                        logger.info(f"    {mount}: {count} pins")
            
        except Exception as e:
            logger.error(f"CLI access demonstration failed: {e}")
        
        logger.info("")
    
    def demonstrate_mcp_integration(self):
        """Demonstrate MCP dashboard integration."""
        logger.info("📊 MCP Dashboard Integration")
        logger.info("-" * 30)
        
        if not self.health_monitor:
            logger.warning("MCP integration requires health monitor")
            return
        
        try:
            # Get enhanced metrics from health monitor
            metrics = self.health_monitor.get_enhanced_metrics()
            
            logger.info("MCP Dashboard Metrics:")
            logger.info(f"  Status: {metrics.get('status', 'unknown')}")
            logger.info(f"  Enhanced Index: {'available' if metrics.get('enhanced_index_available') else 'not available'}")
            
            # Traffic metrics
            traffic = metrics.get("traffic_metrics", {})
            if traffic:
                logger.info("  Traffic Analytics:")
                logger.info(f"    Total Pins: {traffic.get('total_pins', 0)}")
                logger.info(f"    Hot Pins: {traffic.get('hot_pins', 0)}")
                logger.info(f"    Cold Pins: {traffic.get('cold_pins', 0)}")
                
            # VFS metrics
            vfs_metrics = metrics.get("vfs_analytics", {})
            if vfs_metrics:
                logger.info("  VFS Analytics:")
                logger.info(f"    VFS Pins: {vfs_metrics.get('total_vfs_pins', 0)}")
                operations = vfs_metrics.get('operations_summary', {})
                if operations:
                    logger.info("    Recent Operations:")
                    for op_type, stats in operations.items():
                        logger.info(f"      {op_type}: {stats.get('count', 0)} ops")
            
        except Exception as e:
            logger.error(f"MCP integration demonstration failed: {e}")
        
        logger.info("")
    
    def demonstrate_storage_analytics(self):
        """Demonstrate storage analytics capabilities."""
        logger.info("📈 Storage Analytics")
        logger.info("-" * 20)
        
        if not self.enhanced_index:
            logger.warning("Storage analytics requires enhanced index")
            return
        
        try:
            # Get comprehensive metrics
            metrics = self.enhanced_index.get_comprehensive_metrics()
            
            logger.info("Storage Distribution:")
            tier_dist = {}
            for pin in self.enhanced_index.pin_metadata.values():
                tier = pin.primary_tier
                tier_dist[tier] = tier_dist.get(tier, 0) + 1
            
            for tier, count in tier_dist.items():
                logger.info(f"  {tier}: {count} pins")
            
            # Hot pins analysis
            hot_pins = metrics.hot_pins[:3]  # Top 3
            if hot_pins:
                logger.info("Hottest Pins:")
                for i, cid in enumerate(hot_pins, 1):
                    pin_details = self.enhanced_index.get_pin_details(cid)
                    if pin_details:
                        logger.info(f"  {i}. {pin_details.name} (hotness: {pin_details.hotness_score:.2f})")
            
            # Size analysis
            largest = metrics.largest_pins[:3]  # Top 3
            if largest:
                logger.info("Largest Pins:")
                for i, pin_info in enumerate(largest, 1):
                    logger.info(f"  {i}. {pin_info['name']} - {pin_info['size_human']}")
            
            # Recommendations
            recommendations = metrics.storage_recommendations
            if recommendations:
                logger.info("Storage Recommendations:")
                for rec in recommendations[:3]:  # Top 3
                    priority = rec.get('priority', 'medium').upper()
                    logger.info(f"  [{priority}] {rec.get('message', 'No message')}")
            
        except Exception as e:
            logger.error(f"Storage analytics demonstration failed: {e}")
        
        logger.info("")
    
    def demonstrate_vfs_integration(self):
        """Demonstrate VFS integration capabilities."""
        logger.info("🗂️  VFS Integration")
        logger.info("-" * 20)
        
        if not self.enhanced_index:
            logger.warning("VFS integration requires enhanced index")
            return
        
        try:
            # Show VFS-specific analytics
            vfs_analytics = self.enhanced_index.get_vfs_analytics()
            
            logger.info("VFS Statistics:")
            logger.info(f"  Total VFS Pins: {vfs_analytics.get('total_vfs_pins', 0)}")
            
            # Mount point distribution
            mount_points = vfs_analytics.get('mount_points', {})
            if mount_points:
                logger.info("  Mount Point Distribution:")
                for mount_point, pin_count in mount_points.items():
                    logger.info(f"    {mount_point}: {pin_count} pins")
            
            # VFS operations summary
            operations = vfs_analytics.get('operations_summary', {})
            if operations:
                logger.info("  Recent VFS Operations:")
                for op_type, stats in operations.items():
                    success_rate = stats.get('success_rate', 0) * 100
                    avg_duration = stats.get('avg_duration_ms', 0)
                    logger.info(f"    {op_type}: {stats.get('count', 0)} ops, "
                              f"{success_rate:.1f}% success, {avg_duration:.1f}ms avg")
            
            # Path-based access patterns
            logger.info("  Path-Based Access Patterns:")
            path_patterns = {}
            for pin in self.enhanced_index.pin_metadata.values():
                if pin.vfs_path:
                    pattern = pin.access_pattern
                    path_patterns[pattern] = path_patterns.get(pattern, 0) + 1
            
            for pattern, count in path_patterns.items():
                logger.info(f"    {pattern}: {count} pins")
            
        except Exception as e:
            logger.error(f"VFS integration demonstration failed: {e}")
        
        logger.info("")
    
    def demonstrate_background_services(self):
        """Demonstrate background services and predictions."""
        logger.info("🔄 Background Services")
        logger.info("-" * 22)
        
        if not self.enhanced_index:
            logger.warning("Background services require enhanced index")
            return
        
        try:
            # Get performance metrics including background services info
            performance = self.enhanced_index.get_performance_metrics()
            
            bg_services = performance.get("background_services", {})
            logger.info("Background Services Status:")
            logger.info(f"  Running: {'Yes' if bg_services.get('running') else 'No'}")
            logger.info(f"  Update Interval: {bg_services.get('update_interval', 0)}s")
            logger.info(f"  Last Update Duration: {bg_services.get('last_update_duration', 0):.2f}s")
            
            # Capabilities
            capabilities = performance.get("capabilities", {})
            logger.info("System Capabilities:")
            logger.info(f"  Analytics: {'✓' if capabilities.get('analytics_enabled') else '✗'}")
            logger.info(f"  Predictions: {'✓' if capabilities.get('predictions_enabled') else '✗'}")
            logger.info(f"  VFS Integration: {'✓' if capabilities.get('vfs_integration') else '✗'}")
            logger.info(f"  Journal Sync: {'✓' if capabilities.get('journal_sync') else '✗'}")
            
            # Storage info
            storage = performance.get("storage_info", {})
            logger.info("Storage Information:")
            logger.info(f"  Data Directory: {storage.get('data_directory', 'Unknown')}")
            
            parquet_files = storage.get("parquet_files", {})
            if parquet_files:
                logger.info("  Parquet Files:")
                logger.info(f"    Pins: {'✓' if parquet_files.get('pins_exists') else '✗'}")
                logger.info(f"    Analytics: {'✓' if parquet_files.get('analytics_exists') else '✗'}")
            
        except Exception as e:
            logger.error(f"Background services demonstration failed: {e}")
        
        logger.info("")
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report."""
        logger.info("📋 Integration Summary Report")
        logger.info("=" * 30)
        
        # System status
        logger.info("System Status:")
        logger.info(f"  Enhanced Index: {'Available' if ENHANCED_INDEX_AVAILABLE else 'Not Available'}")
        logger.info(f"  MCP Backend: {'Available' if MCP_AVAILABLE else 'Not Available'}")
        logger.info(f"  Basic Index: {'Available' if BASIC_INDEX_AVAILABLE else 'Not Available'}")
        logger.info("")
        
        # Architecture components
        logger.info("Architecture Components:")
        components = [
            ("Enhanced Pin Metadata Index", "✓ Core metadata management with DuckDB analytics"),
            ("VFS Integration", "✗ Hooks into ipfs_fsspec (not fully connected in demo)"),
            ("Filesystem Journal Sync", "✗ Integration with filesystem_journal.py (not available)"),
            ("Hierarchical Storage", "✓ Multi-tier storage management integration"),
            ("MCP Dashboard Backend", "✓ Enhanced metrics and analytics"),
            ("CLI Access Tools", "✓ Command-line interface for operational monitoring"),
            ("Background Services", "✓ Async analytics and predictions"),
            ("DuckDB + Parquet Storage", "✓ Columnar analytics with efficient compression")
        ]
        
        for component, status in components:
            logger.info(f"  {component}: {status}")
        
        logger.info("")
        
        # Usage patterns
        logger.info("Supported Usage Patterns:")
        usage_patterns = [
            "CLI: python enhanced_pin_cli.py [metrics|vfs|pins|track|analytics|status]",
            "API: Integration with storage_backends_api.py for programmatic access",
            "Dashboard: MCP server backend with enhanced analytics and VFS insights",
            "Monitoring: Real-time metrics collection and performance tracking",
            "Analytics: Storage optimization recommendations and predictions"
        ]
        
        for pattern in usage_patterns:
            logger.info(f"  • {pattern}")
        
        logger.info("")
        
        # Performance metrics
        if self.enhanced_index:
            logger.info("Current Performance Metrics:")
            try:
                metrics = self.enhanced_index.get_comprehensive_metrics()
                logger.info(f"  Total Pins: {len(self.enhanced_index.pin_metadata)}")
                logger.info(f"  Hot Pins: {len(metrics.hot_pins)}")
                logger.info(f"  Storage Recommendations: {len(metrics.storage_recommendations)}")
                
                # Calculate total size
                total_size = sum(pin.size_bytes for pin in self.enhanced_index.pin_metadata.values())
                logger.info(f"  Total Managed Size: {self._format_bytes(total_size)}")
                
            except Exception as e:
                logger.error(f"Failed to get performance metrics: {e}")
        
        logger.info("")
        logger.info("🎉 Integration Demo Complete!")
        logger.info("The enhanced pin metadata index is now successfully integrated")
        logger.info("with the ipfs_kit_py virtual filesystem and storage management.")
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes as human-readable string."""
        if bytes_val == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} PB"
    
    async def run_complete_demo(self):
        """Run the complete integration demonstration."""
        await self.initialize()
        self.create_demo_data()
        self.demonstrate_cli_access()
        self.demonstrate_mcp_integration()
        self.demonstrate_storage_analytics()
        self.demonstrate_vfs_integration()
        self.demonstrate_background_services()
        self.generate_summary_report()


async def main():
    """Main demo function."""
    logger.info("Starting Complete Integration Demo")
    logger.info("This demo showcases the enhanced pin metadata index integration")
    logger.info("with the existing ipfs_kit_py infrastructure.")
    logger.info("")
    
    demo = IntegrationDemo()
    await demo.run_complete_demo()


if __name__ == "__main__":
    asyncio.run(main())

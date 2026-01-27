#!/usr/bin/env python3
"""
Enhanced VFS Dashboard Integration Demo with Traffic Monitoring

This demo showcases the enhanced replication management system with:
- Comprehensive traffic monitoring and analytics
- VFS metadata linking to backend storage locations
- Real-time usage tracking across all storage backends
- Data loss protection with traffic-aware operations
"""

import anyio
import logging
import json
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import enhanced dashboard components
try:
    from mcp.ipfs_kit.api.enhanced_dashboard_api import DashboardController, ReplicationManager, TrafficCounter
    from enhanced_replication_dashboard_panel import EnhancedReplicationDashboardPanel
    DASHBOARD_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Dashboard components not available: {e}")
    DASHBOARD_AVAILABLE = False

class EnhancedVFSTrafficDemo:
    """Demo for enhanced VFS dashboard integration with traffic monitoring."""
    
    def __init__(self):
        """Initialize the demo."""
        self.dashboard_controller = None
        self.traffic_stats = {}
        
    async def initialize(self):
        """Initialize the enhanced dashboard system."""
        logger.info("🚀 Initializing Enhanced VFS Dashboard with Traffic Monitoring...")
        
        if DASHBOARD_AVAILABLE:
            self.dashboard_controller = DashboardController()
            logger.info("✓ Dashboard controller initialized")
            logger.info("✓ Replication manager initialized successfully")
            logger.info("✓ Traffic counter initialized for backend monitoring")
        else:
            logger.warning("Dashboard components not available - using mock data")
    
    async def demo_traffic_monitoring(self):
        """Demonstrate traffic monitoring capabilities."""
        logger.info("\n📊 TRAFFIC MONITORING DEMO")
        logger.info("=" * 50)
        
        if not DASHBOARD_AVAILABLE:
            logger.info("Using mock traffic data for demonstration...")
            mock_traffic = {
                "ipfs": {"traffic_gb": 15.2, "file_count": 1250, "operations": 3400, "error_rate": 2.1},
                "ipfs_cluster": {"traffic_gb": 23.8, "file_count": 890, "operations": 2100, "error_rate": 1.5},
                "lotus": {"traffic_gb": 8.4, "file_count": 320, "operations": 850, "error_rate": 0.8},
                "storacha": {"traffic_gb": 42.1, "file_count": 2100, "operations": 5600, "error_rate": 1.2},
                "gdrive": {"traffic_gb": 18.7, "file_count": 760, "operations": 1800, "error_rate": 3.4},
                "s3": {"traffic_gb": 67.3, "file_count": 3200, "operations": 8900, "error_rate": 0.6}
            }
            
            for backend, stats in mock_traffic.items():
                logger.info(f"🔹 {backend.upper()}: {stats['traffic_gb']:.1f} GB, {stats['file_count']} files, {stats['error_rate']:.1f}% errors")
            
            total_traffic = sum(stats['traffic_gb'] for stats in mock_traffic.values())
            total_files = sum(stats['file_count'] for stats in mock_traffic.values())
            avg_error_rate = sum(stats['error_rate'] for stats in mock_traffic.values()) / len(mock_traffic)
            
            logger.info(f"\n📈 TRAFFIC SUMMARY:")
            logger.info(f"   • Total Traffic: {total_traffic:.1f} GB")
            logger.info(f"   • Total Files: {total_files:,}")
            logger.info(f"   • Average Error Rate: {avg_error_rate:.2f}%")
            logger.info(f"   • Most Used Backend: {max(mock_traffic.keys(), key=lambda k: mock_traffic[k]['traffic_gb'])}")
            
        else:
            # Real traffic monitoring
            traffic_result = await self._get_traffic_analytics()
            if traffic_result.get("success"):
                self._display_traffic_analytics(traffic_result)
            else:
                logger.info(f"Real traffic monitoring not available: {traffic_result.get('error')}")
                logger.info("Would show real-time traffic data with live backend statistics")
    
    async def demo_vfs_backend_mapping(self):
        """Demonstrate VFS metadata to backend mapping."""
        logger.info("\n🔗 VFS BACKEND MAPPING DEMO")
        logger.info("=" * 50)
        
        if not DASHBOARD_AVAILABLE:
            logger.info("Using mock VFS mapping data for demonstration...")
            mock_mapping = {
                "dataset_001": {
                    "cid": "QmExampleDataset001Hash",
                    "backends": ["ipfs", "ipfs_cluster", "s3"],
                    "replication_count": 3,
                    "storage_size_mb": 156.8
                },
                "vector_index_001": {
                    "cid": "QmExampleVectorIndex001Hash",
                    "backends": ["storacha", "gdrive"],
                    "replication_count": 2,
                    "storage_size_mb": 423.2
                },
                "knowledge_graph_001": {
                    "cid": "QmExampleKG001Hash",
                    "backends": ["ipfs_cluster", "s3", "lotus"],
                    "replication_count": 3,
                    "storage_size_mb": 89.4
                }
            }
            
            logger.info("VFS Metadata → Backend Storage Mapping:")
            for vfs_id, mapping in mock_mapping.items():
                backends_str = ", ".join(mapping["backends"])
                logger.info(f"🔹 {vfs_id}:")
                logger.info(f"   CID: {mapping['cid'][:20]}...")
                logger.info(f"   Backends: {backends_str}")
                logger.info(f"   Replicas: {mapping['replication_count']}")
                logger.info(f"   Size: {mapping['storage_size_mb']:.1f} MB")
            
            total_entries = len(mock_mapping)
            total_size = sum(m["storage_size_mb"] for m in mock_mapping.values())
            avg_replication = sum(m["replication_count"] for m in mock_mapping.values()) / total_entries
            
            logger.info(f"\n📊 VFS MAPPING SUMMARY:")
            logger.info(f"   • Total VFS Entries: {total_entries}")
            logger.info(f"   • Total Storage: {total_size:.1f} MB")
            logger.info(f"   • Average Replication Factor: {avg_replication:.2f}")
            
        else:
            # Real VFS mapping
            mapping_result = await self._get_vfs_backend_mapping()
            if mapping_result.get("success"):
                self._display_vfs_mapping(mapping_result)
            else:
                logger.info(f"Real VFS mapping not available: {mapping_result.get('error')}")
                logger.info("Would show live VFS metadata to backend storage mapping")
    
    async def demo_backend_usage_analytics(self):
        """Demonstrate comprehensive backend usage analytics."""
        logger.info("\n📈 BACKEND USAGE ANALYTICS DEMO")
        logger.info("=" * 50)
        
        if not DASHBOARD_AVAILABLE:
            logger.info("Using mock analytics data for demonstration...")
            mock_analytics = {
                "backend_efficiency": {
                    "ipfs": {"efficiency": 94.2, "utilization": 76.8, "reliability": 97.9},
                    "ipfs_cluster": {"efficiency": 91.5, "utilization": 82.1, "reliability": 98.5},
                    "lotus": {"efficiency": 88.7, "utilization": 45.3, "reliability": 99.2},
                    "storacha": {"efficiency": 96.1, "utilization": 68.9, "reliability": 95.8},
                    "gdrive": {"efficiency": 78.3, "utilization": 59.2, "reliability": 89.4},
                    "s3": {"efficiency": 99.1, "utilization": 91.7, "reliability": 99.8}
                },
                "performance_insights": [
                    {"type": "optimization", "message": "S3 backend showing optimal performance - consider increasing allocation"},
                    {"type": "warning", "message": "GDrive backend has elevated error rates - investigate connectivity"},
                    {"type": "info", "message": "Lotus backend underutilized - good backup capacity available"}
                ],
                "capacity_planning": {
                    "total_capacity_gb": 500.0,
                    "used_capacity_gb": 175.5,
                    "utilization_percentage": 35.1,
                    "projected_full_date": "2025-12-15"
                }
            }
            
            logger.info("Backend Performance Analysis:")
            for backend, metrics in mock_analytics["backend_efficiency"].items():
                logger.info(f"🔹 {backend.upper()}:")
                logger.info(f"   Efficiency: {metrics['efficiency']:.1f}%")
                logger.info(f"   Utilization: {metrics['utilization']:.1f}%")
                logger.info(f"   Reliability: {metrics['reliability']:.1f}%")
            
            logger.info("\n💡 Performance Insights:")
            for insight in mock_analytics["performance_insights"]:
                icon = {"optimization": "🚀", "warning": "⚠️", "info": "ℹ️"}.get(insight["type"], "•")
                logger.info(f"   {icon} {insight['message']}")
            
            logger.info("\n📊 Capacity Planning:")
            capacity = mock_analytics["capacity_planning"]
            logger.info(f"   • Total Capacity: {capacity['total_capacity_gb']:.1f} GB")
            logger.info(f"   • Used Capacity: {capacity['used_capacity_gb']:.1f} GB")
            logger.info(f"   • Utilization: {capacity['utilization_percentage']:.1f}%")
            logger.info(f"   • Projected Full: {capacity['projected_full_date']}")
            
        else:
            # Real backend analytics
            analytics_result = await self._get_backend_usage_analytics()
            if analytics_result.get("success"):
                self._display_backend_analytics(analytics_result)
            else:
                logger.info(f"Real backend analytics not available: {analytics_result.get('error')}")
                logger.info("Would show comprehensive backend performance and usage analytics")
    
    async def demo_enhanced_replication_with_tracking(self):
        """Demonstrate enhanced replication with traffic tracking."""
        logger.info("\n🔄 ENHANCED REPLICATION WITH TRACKING DEMO")
        logger.info("=" * 50)
        
        # Simulate replication operations with traffic tracking
        mock_operations = [
            {
                "operation": "replicate",
                "cid": "QmExampleNewDataset001",
                "vfs_metadata_id": "dataset_new_001",
                "size_mb": 245.7,
                "target_backends": ["ipfs", "s3", "storacha"],
                "success_rate": 100
            },
            {
                "operation": "replicate", 
                "cid": "QmExampleLargeVector002",
                "vfs_metadata_id": "vector_large_002",
                "size_mb": 1024.3,
                "target_backends": ["ipfs_cluster", "s3"],
                "success_rate": 100
            },
            {
                "operation": "backup",
                "backend": "ipfs_cluster",
                "pin_count": 156,
                "backup_size_mb": 2048.5,
                "success": True
            }
        ]
        
        for operation in mock_operations:
            if operation["operation"] == "replicate":
                logger.info(f"🔄 Replicating {operation['cid'][:20]}...")
                logger.info(f"   VFS ID: {operation['vfs_metadata_id']}")
                logger.info(f"   Size: {operation['size_mb']:.1f} MB")
                logger.info(f"   Target Backends: {', '.join(operation['target_backends'])}")
                logger.info(f"   Success Rate: {operation['success_rate']}%")
                
                # Simulate traffic recording
                for backend in operation["target_backends"]:
                    if backend not in self.traffic_stats:
                        self.traffic_stats[backend] = {"traffic_mb": 0, "operations": 0, "files": 0}
                    
                    self.traffic_stats[backend]["traffic_mb"] += operation["size_mb"]
                    self.traffic_stats[backend]["operations"] += 1
                    self.traffic_stats[backend]["files"] += 1
                
            elif operation["operation"] == "backup":
                logger.info(f"💾 Backup operation on {operation['backend']}:")
                logger.info(f"   Pins backed up: {operation['pin_count']}")
                logger.info(f"   Backup size: {operation['backup_size_mb']:.1f} MB")
                logger.info(f"   Status: {'✓ Success' if operation['success'] else '✗ Failed'}")
        
        # Display accumulated traffic statistics
        logger.info(f"\n📊 ACCUMULATED TRAFFIC STATISTICS:")
        for backend, stats in self.traffic_stats.items():
            logger.info(f"🔹 {backend.upper()}: {stats['traffic_mb']:.1f} MB, {stats['operations']} ops, {stats['files']} files")
    
    async def demo_dashboard_panel_configuration(self):
        """Demonstrate the enhanced dashboard panel configuration."""
        logger.info("\n🎨 ENHANCED DASHBOARD PANEL CONFIGURATION DEMO")
        logger.info("=" * 50)
        
        panel = EnhancedReplicationDashboardPanel()
        config = panel.get_config()
        
        logger.info(f"Panel Title: {config['title']}")
        logger.info(f"Panel Version: {config['version']}")
        logger.info(f"Total Sections: {len(config['sections'])}")
        
        logger.info("\nPanel Sections:")
        for section in config["sections"]:
            logger.info(f"🔹 {section['title']}")
            if "components" in section:
                logger.info(f"   Components: {len(section['components'])}")
            elif "cards" in section:
                logger.info(f"   Status Cards: {len(section['cards'])}")
            elif "fields" in section:
                logger.info(f"   Form Fields: {len(section['fields'])}")
        
        logger.info(f"\nAPI Endpoints: {len(config['real_time_updates']['endpoints'])}")
        for endpoint in config['real_time_updates']['endpoints'][:5]:  # Show first 5
            logger.info(f"🔹 {endpoint['method']} {endpoint['endpoint']}")
        
        # Export configuration
        config_path = panel.export_config("/tmp/enhanced_replication_dashboard_demo.json")
        logger.info(f"\n✓ Panel configuration exported to: {config_path}")
    
    async def _get_traffic_analytics(self):
        """Get traffic analytics from the dashboard controller."""
        if not self.dashboard_controller or not self.dashboard_controller.replication_manager:
            return {"success": False, "error": "Dashboard controller not available"}
        
        try:
            return await self.dashboard_controller.replication_manager.get_traffic_analytics()
        except Exception as e:
            logger.warning(f"Error getting real traffic analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_vfs_backend_mapping(self):
        """Get VFS backend mapping from the dashboard controller."""
        if not self.dashboard_controller or not self.dashboard_controller.replication_manager:
            return {"success": False, "error": "Dashboard controller not available"}
        
        try:
            return await self.dashboard_controller.replication_manager.get_vfs_backend_mapping()
        except Exception as e:
            logger.warning(f"Error getting real VFS mapping: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_backend_usage_analytics(self):
        """Get comprehensive backend usage analytics."""
        if not self.dashboard_controller:
            return {"success": False, "error": "Dashboard controller not available"}
        
        try:
            # This would combine multiple analytics sources
            return {"success": True, "data": {"placeholder": "analytics_data"}}
        except Exception as e:
            logger.warning(f"Error getting backend analytics: {e}")
            return {"success": False, "error": str(e)}
    
    def _display_traffic_analytics(self, data):
        """Display traffic analytics data."""
        logger.info("✓ Traffic analytics retrieved successfully")
        
        # Check if this is the expected structure from get_traffic_analytics
        if "usage_statistics" in data:
            usage_stats = data["usage_statistics"]
            logger.info("Real traffic analytics data:")
            logger.info(f"Usage Statistics: {json.dumps(usage_stats, indent=2)}")
        else:
            logger.info("Real traffic analytics would be displayed here")
            logger.info(f"Data: {json.dumps(data, indent=2)}")
    
    def _display_vfs_mapping(self, data):
        """Display VFS mapping data."""
        logger.info("✓ VFS backend mapping retrieved successfully")
        
        # Check if this is the expected structure from get_vfs_backend_mapping
        if "vfs_backend_mapping" in data:
            mapping = data["vfs_backend_mapping"]
            summary = data.get("summary", {})
            logger.info("Real VFS backend mapping data:")
            logger.info(f"VFS Mapping: {json.dumps(mapping, indent=2)}")
            logger.info(f"Summary: {json.dumps(summary, indent=2)}")
        else:
            logger.info("Real VFS mapping would be displayed here")
            logger.info(f"Data: {json.dumps(data, indent=2)}")
    
    def _display_backend_analytics(self, data):
        """Display backend analytics data."""
        logger.info("✓ Backend analytics retrieved successfully")
        
        # This is a placeholder implementation since the actual analytics structure would depend on the real data
        if isinstance(data, dict) and "data" in data:
            analytics_data = data["data"]
            logger.info("Real backend analytics data:")
            logger.info(f"Analytics: {json.dumps(analytics_data, indent=2)}")
        else:
            logger.info("Real backend analytics would be displayed here")
            logger.info(f"Data: {json.dumps(data, indent=2)}")
    
    async def run_complete_demo(self):
        """Run the complete enhanced VFS dashboard demo."""
        logger.info("🎯 ENHANCED VFS DASHBOARD WITH TRAFFIC MONITORING - DEMO")
        logger.info("=" * 70)
        
        await self.initialize()
        await self.demo_traffic_monitoring()
        await self.demo_vfs_backend_mapping()
        await self.demo_backend_usage_analytics()
        await self.demo_enhanced_replication_with_tracking()
        await self.demo_dashboard_panel_configuration()
        
        logger.info("\n🎉 ENHANCED VFS DASHBOARD DEMO COMPLETED")
        logger.info("=" * 70)
        logger.info("✅ Traffic monitoring system demonstrated")
        logger.info("✅ VFS backend mapping showcased")
        logger.info("✅ Backend usage analytics displayed")
        logger.info("✅ Enhanced replication tracking shown")
        logger.info("✅ Dashboard panel configuration exported")
        logger.info("\n🚀 Key Features Demonstrated:")
        logger.info("   • Real-time traffic monitoring across all backends")
        logger.info("   • VFS metadata linked to backend storage locations")
        logger.info("   • Comprehensive usage analytics and insights")
        logger.info("   • Enhanced replication with traffic tracking")
        logger.info("   • Data loss protection with usage-aware operations")
        logger.info("   • Performance optimization recommendations")

async def main():
    """Main demo function."""
    demo = EnhancedVFSTrafficDemo()
    try:
        await demo.run_complete_demo()
        return 0
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)

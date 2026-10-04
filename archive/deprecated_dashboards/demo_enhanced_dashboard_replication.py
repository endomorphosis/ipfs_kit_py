#!/usr/bin/env python3
"""
Enhanced Dashboard with Replication Management Integration Demo
Complete demonstration of IPFS Kit with comprehensive replication management
"""

import anyio
import logging
import json
import os
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

class MockComponents:
    """Mock components for demonstration."""
    
    def __init__(self):
        self.storage_stats = {
            "dataset_count": 15,
            "total_size_bytes": 1024 * 1024 * 500,  # 500MB
            "datasets": [
                {
                    "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
                    "name": "Research Dataset A",
                    "size_bytes": 1024 * 1024 * 50,
                    "created_at": "2025-07-23T10:00:00Z",
                    "metadata": {"type": "research", "tags": ["ml", "dataset"]}
                },
                {
                    "cid": "QmZ1234567890abcdefghijklmnopqrstuvwxyzABCDEF",
                    "name": "Vector Index B",
                    "size_bytes": 1024 * 1024 * 25,
                    "created_at": "2025-07-23T11:00:00Z",
                    "metadata": {"type": "vector_index", "dimensions": 768}
                }
            ]
        }
    
    def get_storage_stats(self):
        """Mock storage statistics."""
        return {"success": True, "stats": self.storage_stats}
    
    def list_datasets(self, limit=50, offset=0):
        """Mock dataset listing."""
        datasets = self.storage_stats["datasets"][offset:offset+limit]
        return {
            "success": True,
            "datasets": datasets,
            "total": len(self.storage_stats["datasets"])
        }

class EnhancedDashboardIntegrationDemo:
    """Comprehensive integration demo for enhanced dashboard with replication."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".ipfs_dashboard_replication_demo"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Components
        self.replication_manager = None
        self.mock_parquet_bridge = None
        self.mock_car_bridge = None
        self.mock_cache_manager = None
        self.apis = []
        
    async def initialize_components(self):
        """Initialize all demo components."""
        logger.info("Initializing Enhanced Dashboard Integration Demo...")
        
        try:
            # Initialize replication manager
            from ipfs_kit_py.dashboard.replication_manager import ReplicationManager
            self.replication_manager = ReplicationManager(
                config_dir=str(self.config_dir),
                parquet_bridge=MockComponents(),
                car_bridge=MockComponents(),
                ipfs_manager=None
            )
            logger.info("✓ Replication manager initialized")
            
            # Initialize mock components
            self.mock_parquet_bridge = MockComponents()
            self.mock_car_bridge = MockComponents()  
            self.mock_cache_manager = MockComponents()
            logger.info("✓ Mock components initialized")
            
            # Create enhanced APIs with replication support
            from ipfs_kit_py.dashboard.enhanced_vfs_apis import create_enhanced_dashboard_apis
            self.apis = create_enhanced_dashboard_apis(
                parquet_bridge=self.mock_parquet_bridge,
                car_bridge=self.mock_car_bridge,
                cache_manager=self.mock_cache_manager,
                knowledge_graph=None,
                graph_rag=None,
                replication_manager=self.replication_manager
            )
            logger.info(f"✓ Enhanced APIs created: {len(self.apis)} routers")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            return False
    
    async def demo_replication_settings_management(self):
        """Demonstrate replication settings management."""
        logger.info("\n=== Replication Settings Management Demo ===")
        
        try:
            # Configure optimal replication settings
            settings = {
                "min_replicas": 2,
                "target_replicas": 3,
                "max_replicas": 5,
                "max_total_storage_gb": 100.0,
                "policy": "balanced",
                "auto_replication": True,
                "emergency_backup_enabled": True,
                "health_check_interval": 300,
                "replication_check_interval": 900
            }
            
            result = await self.replication_manager.update_replication_settings(settings)
            if result["success"]:
                logger.info("✓ Replication settings configured successfully")
                logger.info(f"  - Target replicas: {settings['target_replicas']}")
                logger.info(f"  - Max storage: {settings['max_total_storage_gb']} GB")
                logger.info(f"  - Policy: {settings['policy']}")
                logger.info(f"  - Auto-replication: {settings['auto_replication']}")
                return True
            else:
                logger.error(f"✗ Failed to configure settings: {result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Settings management error: {e}")
            return False
    
    async def demo_storage_backends_setup(self):
        """Demonstrate comprehensive storage backend setup."""
        logger.info("\n=== Storage Backends Setup Demo ===")
        
        try:
            # Define production-ready backend configurations
            backend_configs = [
                {
                    "name": "local_ipfs",
                    "backend_type": "local",
                    "max_storage_gb": 50.0,
                    "cost_per_gb": 0.0,
                    "priority": 1,
                    "enabled": True,
                    "metadata": {
                        "description": "Local IPFS node for immediate access",
                        "location": "localhost",
                        "reliability": "high"
                    }
                },
                {
                    "name": "cluster_primary",
                    "backend_type": "ipfs_cluster",
                    "endpoint": "http://cluster-1.example.com:9094",
                    "max_storage_gb": 200.0,
                    "cost_per_gb": 0.0,
                    "priority": 2,
                    "enabled": True,
                    "metadata": {
                        "description": "Primary IPFS cluster for distributed storage",
                        "nodes": 5,
                        "replication_factor": 3
                    }
                },
                {
                    "name": "cluster_backup",
                    "backend_type": "ipfs_cluster", 
                    "endpoint": "http://cluster-2.example.com:9094",
                    "max_storage_gb": 200.0,
                    "cost_per_gb": 0.0,
                    "priority": 3,
                    "enabled": True,
                    "metadata": {
                        "description": "Backup IPFS cluster for redundancy",
                        "location": "different_datacenter"
                    }
                },
                {
                    "name": "filecoin_archive",
                    "backend_type": "filecoin",
                    "max_storage_gb": 1000.0,
                    "cost_per_gb": 0.001,
                    "priority": 4,
                    "enabled": True,
                    "metadata": {
                        "description": "Filecoin for long-term archival storage",
                        "retrieval_time": "minutes_to_hours"
                    }
                },
                {
                    "name": "web3_storage",
                    "backend_type": "web3_storage",
                    "endpoint": "https://api.web3.storage",
                    "max_storage_gb": 100.0,
                    "cost_per_gb": 0.0,
                    "priority": 5,
                    "enabled": True,
                    "metadata": {
                        "description": "Web3.Storage for decentralized backup"
                    }
                }
            ]
            
            successful_backends = 0
            for backend_config in backend_configs:
                result = await self.replication_manager.add_storage_backend(backend_config)
                if result["success"]:
                    logger.info(f"✓ Added backend: {backend_config['name']} ({backend_config['backend_type']})")
                    successful_backends += 1
                else:
                    logger.error(f"✗ Failed to add backend {backend_config['name']}: {result['error']}")
            
            # Verify backend setup
            backends_result = await self.replication_manager.list_storage_backends()
            if backends_result["success"]:
                total_backends = len(backends_result["backends"])
                enabled_backends = len([b for b in backends_result["backends"] if b["enabled"]])
                logger.info(f"✓ Backend setup complete: {total_backends} total, {enabled_backends} enabled")
                
                # Show backend summary
                logger.info("Backend Summary:")
                for backend in backends_result["backends"]:
                    status = "🟢" if backend["enabled"] else "🔴"
                    logger.info(f"  {status} {backend['name']}: {backend['backend_type']} (Priority: {backend['priority']})")
                
                return successful_backends >= 3  # At least 3 backends needed for good redundancy
            else:
                logger.error("✗ Failed to verify backend setup")
                return False
                
        except Exception as e:
            logger.error(f"✗ Backend setup error: {e}")
            return False
    
    async def demo_vfs_metadata_with_replication(self):
        """Demonstrate VFS metadata operations with automatic replication."""
        logger.info("\n=== VFS Metadata with Replication Demo ===")
        
        try:
            # Simulate creating datasets with automatic replication
            datasets_to_create = [
                {
                    "id": "research_dataset_001",
                    "name": "AI Training Dataset",
                    "size_bytes": 1024 * 1024 * 100,  # 100MB
                    "target_replicas": 4,
                    "priority": 1,
                    "metadata": {"type": "ml_training", "format": "parquet"}
                },
                {
                    "id": "vector_index_001",
                    "name": "Document Embeddings Index",
                    "size_bytes": 1024 * 1024 * 50,  # 50MB
                    "target_replicas": 3,
                    "priority": 2,
                    "metadata": {"type": "vector_index", "dimensions": 768}
                },
                {
                    "id": "knowledge_graph_001",
                    "name": "Research Knowledge Graph",
                    "size_bytes": 1024 * 1024 * 75,  # 75MB
                    "target_replicas": 3,
                    "priority": 1,
                    "metadata": {"type": "knowledge_graph", "format": "rdf"}
                }
            ]
            
            # Find VFS API from our created APIs
            vfs_api = None
            for api_router in self.apis:
                if hasattr(api_router, 'prefix') and api_router.prefix == "/api/vfs":
                    # Get the VFS API instance (hack for demo)
                    break
            
            successful_datasets = 0
            for dataset_data in datasets_to_create:
                # In a real scenario, this would call the actual VFS API
                # For demo, we'll call replication manager directly
                dataset_cid = f"Qm{dataset_data['id']}CID{len(dataset_data['name'])}"
                
                # Register for replication
                result = await self.replication_manager.register_pin_for_replication(
                    cid=dataset_cid,
                    vfs_metadata_id=dataset_data["id"],
                    size_bytes=dataset_data["size_bytes"],
                    target_replicas=dataset_data["target_replicas"],
                    priority=dataset_data["priority"]
                )
                
                if result["success"]:
                    logger.info(f"✓ Created and registered dataset: {dataset_data['name']}")
                    logger.info(f"  - CID: {dataset_cid}")
                    logger.info(f"  - Size: {dataset_data['size_bytes'] / (1024*1024):.1f} MB")
                    logger.info(f"  - Target replicas: {dataset_data['target_replicas']}")
                    successful_datasets += 1
                else:
                    logger.error(f"✗ Failed to register dataset {dataset_data['name']}: {result['error']}")
            
            return successful_datasets == len(datasets_to_create)
            
        except Exception as e:
            logger.error(f"✗ VFS metadata replication error: {e}")
            return False
    
    async def demo_automatic_replication(self):
        """Demonstrate automatic replication across backends."""
        logger.info("\n=== Automatic Replication Demo ===")
        
        try:
            # Start monitoring to enable automatic replication
            monitor_result = await self.replication_manager.start_monitoring()
            if not monitor_result["success"]:
                logger.error("✗ Failed to start replication monitoring")
                return False
            
            logger.info("✓ Replication monitoring started")
            
            # Wait for automatic replication to process
            logger.info("Waiting for automatic replication (10 seconds)...")
            await anyio.sleep(10)
            
            # Check replication status
            status_result = await self.replication_manager.get_replication_status()
            if status_result["success"]:
                summary = status_result["summary"]
                
                logger.info("Replication Status After Auto-Processing:")
                logger.info(f"  - Total pins: {summary['total_pins']}")
                logger.info(f"  - Healthy replicated: {summary['healthy_replicated']}")
                logger.info(f"  - Under-replicated: {summary['under_replicated']}")
                logger.info(f"  - Over-replicated: {summary['over_replicated']}")
                logger.info(f"  - Replication ratio: {summary['replication_ratio']:.2%}")
                
                # Show storage usage across backends
                if "storage_usage" in status_result:
                    logger.info("Storage Usage by Backend:")
                    for backend_name, usage in status_result["storage_usage"].items():
                        size_gb = usage["total_size_gb"]
                        pin_count = usage["pin_count"]
                        logger.info(f"  - {backend_name}: {size_gb:.2f} GB ({pin_count} pins)")
                
                # Stop monitoring
                await self.replication_manager.stop_monitoring()
                logger.info("✓ Replication monitoring stopped")
                
                # Consider success if we have reasonable replication
                return summary["replication_ratio"] >= 0.5
            else:
                logger.error("✗ Failed to get replication status")
                return False
                
        except Exception as e:
            logger.error(f"✗ Automatic replication error: {e}")
            return False
    
    async def demo_data_protection_features(self):
        """Demonstrate data protection and backup features."""
        logger.info("\n=== Data Protection Features Demo ===")
        
        try:
            protection_features_tested = 0
            
            # 1. Export backend data for protection
            logger.info("Testing backend export functionality...")
            export_result = await self.replication_manager.export_backend_pins("local_ipfs")
            if export_result["success"]:
                logger.info(f"✓ Exported {export_result['export_data']['total_pins']} pins from local_ipfs")
                logger.info(f"  Export file: {export_result['export_file']}")
                protection_features_tested += 1
            else:
                logger.error(f"✗ Export failed: {export_result['error']}")
            
            # 2. Test health monitoring
            logger.info("Testing replication health monitoring...")
            health_result = await self.replication_manager.get_replication_status()
            if health_result["success"]:
                summary = health_result["summary"]
                if summary["total_pins"] > 0:
                    health_score = summary["replication_ratio"] * 100
                    logger.info(f"✓ Replication health: {health_score:.1f}%")
                    
                    if health_score >= 80:
                        logger.info("  System health: EXCELLENT 🟢")
                    elif health_score >= 60:
                        logger.info("  System health: GOOD 🟡")
                    else:
                        logger.info("  System health: NEEDS ATTENTION 🔴")
                    
                    protection_features_tested += 1
                else:
                    logger.warning("  No pins found for health assessment")
            else:
                logger.error("✗ Health monitoring failed")
            
            # 3. Test individual pin status
            logger.info("Testing individual pin protection status...")
            # Get a sample pin to test
            test_cid = "QmResearch_dataset_001CIDname"  # From our created datasets
            pin_status = await self.replication_manager.get_pin_replication_status(test_cid)
            if pin_status["success"]:
                replication = pin_status["replication"]
                current_replicas = replication["current_replicas"]
                target_replicas = replication["target_replicas"]
                
                logger.info(f"✓ Pin {test_cid[:20]}... protection status:")
                logger.info(f"  - Current replicas: {current_replicas}")
                logger.info(f"  - Target replicas: {target_replicas}")
                logger.info(f"  - Backends: {', '.join(replication['backends'])}")
                
                if current_replicas >= target_replicas:
                    logger.info("  - Protection level: OPTIMAL ✅")
                elif current_replicas >= 2:
                    logger.info("  - Protection level: ADEQUATE ⚠️")
                else:
                    logger.info("  - Protection level: AT RISK ❌")
                
                protection_features_tested += 1
            else:
                logger.warning(f"Pin status check failed: {pin_status['error']}")
            
            return protection_features_tested >= 2
            
        except Exception as e:
            logger.error(f"✗ Data protection features error: {e}")
            return False
    
    async def demo_dashboard_integration(self):
        """Demonstrate complete dashboard integration."""
        logger.info("\n=== Dashboard Integration Demo ===")
        
        try:
            integration_components = 0
            
            # 1. API Routers Integration
            logger.info("Testing API router integration...")
            api_count = len(self.apis)
            if api_count >= 4:  # VFS, Vector, KG, Pinset, Replication
                logger.info(f"✓ {api_count} API routers integrated successfully")
                
                # Show available endpoints
                logger.info("Available API endpoints:")
                for router in self.apis:
                    if hasattr(router, 'prefix'):
                        route_count = len([r for r in router.routes if hasattr(r, 'methods')])
                        logger.info(f"  - {router.prefix}: {route_count} endpoints")
                
                integration_components += 1
            else:
                logger.error(f"✗ Insufficient API routers: {api_count}")
            
            # 2. Replication API Integration
            logger.info("Testing replication API integration...")
            replication_router = None
            for router in self.apis:
                if hasattr(router, 'prefix') and router.prefix == "/api/replication":
                    replication_router = router
                    break
            
            if replication_router:
                replication_endpoints = len([r for r in replication_router.routes if hasattr(r, 'methods')])
                logger.info(f"✓ Replication API integrated with {replication_endpoints} endpoints")
                integration_components += 1
            else:
                logger.error("✗ Replication API not found in integration")
            
            # 3. Test settings integration
            logger.info("Testing settings integration...")
            settings_result = await self.replication_manager.get_replication_settings()
            if settings_result["success"]:
                logger.info("✓ Settings integration working")
                logger.info(f"  - Auto-replication: {settings_result['settings']['auto_replication']}")
                logger.info(f"  - Monitoring active: {settings_result['monitoring_active']}")
                integration_components += 1
            else:
                logger.error("✗ Settings integration failed")
            
            return integration_components >= 2
            
        except Exception as e:
            logger.error(f"✗ Dashboard integration error: {e}")
            return False
    
    async def run_comprehensive_integration_demo(self):
        """Run the complete integration demonstration."""
        logger.info("Starting Enhanced Dashboard Replication Integration Demo")
        logger.info("=" * 70)
        
        start_time = datetime.utcnow()
        demo_phases = []
        
        # Phase 1: Component Initialization
        logger.info("Phase 1: Component Initialization...")
        init_success = await self.initialize_components()
        demo_phases.append(("Component Initialization", init_success))
        
        if not init_success:
            logger.error("❌ Cannot continue without proper initialization")
            return 0
        
        # Phase 2: Replication Settings Management
        logger.info("Phase 2: Replication Settings Management...")
        settings_success = await self.demo_replication_settings_management()
        demo_phases.append(("Replication Settings", settings_success))
        
        # Phase 3: Storage Backends Setup
        logger.info("Phase 3: Storage Backends Setup...")
        backends_success = await self.demo_storage_backends_setup()
        demo_phases.append(("Storage Backends Setup", backends_success))
        
        # Phase 4: VFS Metadata with Replication
        logger.info("Phase 4: VFS Metadata with Replication...")
        vfs_success = await self.demo_vfs_metadata_with_replication()
        demo_phases.append(("VFS Metadata Integration", vfs_success))
        
        # Phase 5: Automatic Replication
        logger.info("Phase 5: Automatic Replication...")
        auto_repl_success = await self.demo_automatic_replication()
        demo_phases.append(("Automatic Replication", auto_repl_success))
        
        # Phase 6: Data Protection Features
        logger.info("Phase 6: Data Protection Features...")
        protection_success = await self.demo_data_protection_features()
        demo_phases.append(("Data Protection", protection_success))
        
        # Phase 7: Dashboard Integration
        logger.info("Phase 7: Dashboard Integration...")
        dashboard_success = await self.demo_dashboard_integration()
        demo_phases.append(("Dashboard Integration", dashboard_success))
        
        # Calculate results
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        successful_phases = sum(1 for _, success in demo_phases if success)
        total_phases = len(demo_phases)
        success_rate = (successful_phases / total_phases) * 100
        
        # Results summary
        logger.info("\n" + "=" * 70)
        logger.info("ENHANCED DASHBOARD REPLICATION INTEGRATION RESULTS")
        logger.info("=" * 70)
        
        for phase_name, success in demo_phases:
            status_icon = "✅" if success else "❌"
            logger.info(f"{phase_name:<35}: {status_icon}")
        
        logger.info(f"\nOverall Results:")
        logger.info(f"Success Rate: {success_rate:.1f}% ({successful_phases}/{total_phases})")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        # Status assessment
        if success_rate == 100:
            logger.info("🎉 PERFECT! Complete replication integration working flawlessly!")
            status = "EXCELLENT"
        elif success_rate >= 85:
            logger.info("🚀 GREAT! Replication system is production-ready!")
            status = "GOOD"
        elif success_rate >= 70:
            logger.info("✅ GOOD! Most features working, minor issues to address")
            status = "ACCEPTABLE"
        else:
            logger.info("⚠️  NEEDS WORK! Significant issues need resolution")
            status = "NEEDS_IMPROVEMENT"
        
        # Save comprehensive results
        results = {
            "demo_type": "Enhanced Dashboard Replication Integration",
            "timestamp": end_time.isoformat(),
            "duration_seconds": duration,
            "success_rate": success_rate,
            "status": status,
            "phases": [
                {
                    "name": name,
                    "success": success,
                    "order": i + 1
                }
                for i, (name, success) in enumerate(demo_phases)
            ],
            "summary": {
                "total_phases": total_phases,
                "successful_phases": successful_phases,
                "failed_phases": total_phases - successful_phases
            },
            "key_features_demonstrated": [
                "Comprehensive replication management",
                "Multi-backend storage support", 
                "Automatic pin replication",
                "VFS metadata integration",
                "Data protection and backup",
                "Real-time health monitoring",
                "Dashboard API integration"
            ]
        }
        
        results_file = "enhanced_dashboard_replication_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n📊 Detailed results saved to: {results_file}")
        
        return success_rate


async def main():
    """Main demonstration function."""
    demo = EnhancedDashboardIntegrationDemo()
    
    try:
        success_rate = await demo.run_comprehensive_integration_demo()
        
        # Return appropriate exit code
        if success_rate >= 85:
            return 0  # Excellent
        elif success_rate >= 70:
            return 1  # Good but with issues
        else:
            return 2  # Needs significant work
            
    except KeyboardInterrupt:
        logger.info("\n⏹️  Demo interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Demo failed with critical error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)

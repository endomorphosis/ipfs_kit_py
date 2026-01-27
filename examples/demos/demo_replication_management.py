#!/usr/bin/env python3
"""
Replication Management Demo
Demonstrates comprehensive pin replication across multiple storage backends
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

from ipfs_kit_py.dashboard.replication_manager import (
    ReplicationManager, BackendConfig, ReplicationSettings, 
    BackendType, ReplicationPolicy
)
from ipfs_kit_py.dashboard.replication_api import create_replication_api
from ipfs_kit_py.dashboard.enhanced_vfs_apis import create_enhanced_dashboard_apis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReplicationDemo:
    """Comprehensive replication management demonstration."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".ipfs_replication_demo"
        self.replication_manager = None
        
    async def initialize(self):
        """Initialize the replication system."""
        logger.info("Initializing Replication Management Demo...")
        
        # Initialize replication manager
        self.replication_manager = ReplicationManager(
            config_dir=str(self.config_dir)
        )
        
        logger.info("✓ Replication manager initialized")
        
    async def demo_replication_settings(self):
        """Demonstrate replication settings management."""
        logger.info("\n=== Replication Settings Demo ===")
        
        # Get current settings
        settings_result = await self.replication_manager.get_replication_settings()
        logger.info(f"Current settings: {json.dumps(settings_result, indent=2)}")
        
        # Update settings
        new_settings = {
            "min_replicas": 2,
            "target_replicas": 3,
            "max_replicas": 5,
            "max_total_storage_gb": 50.0,
            "policy": "balanced",
            "auto_replication": True,
            "emergency_backup_enabled": True
        }
        
        update_result = await self.replication_manager.update_replication_settings(new_settings)
        logger.info(f"Settings update result: {json.dumps(update_result, indent=2)}")
        
        return update_result["success"]
    
    async def demo_storage_backends(self):
        """Demonstrate storage backend management."""
        logger.info("\n=== Storage Backends Demo ===")
        
        # List current backends
        backends_result = await self.replication_manager.list_storage_backends()
        logger.info(f"Current backends: {len(backends_result.get('backends', []))}")
        
        # Add new backends
        backends_to_add = [
            {
                "name": "demo_cluster",
                "backend_type": "ipfs_cluster",
                "endpoint": "http://localhost:9094",
                "max_storage_gb": 100.0,
                "priority": 2,
                "enabled": True
            },
            {
                "name": "demo_pinata",
                "backend_type": "pinata",
                "api_key": "demo_key_12345",
                "max_storage_gb": 10.0,
                "cost_per_gb": 0.02,
                "priority": 4,
                "enabled": True
            },
            {
                "name": "demo_storacha",
                "backend_type": "storacha",
                "endpoint": "https://up.storacha.network",
                "max_storage_gb": 200.0,
                "cost_per_gb": 0.001,
                "priority": 3,
                "enabled": True
            }
        ]
        
        for backend_config in backends_to_add:
            result = await self.replication_manager.add_storage_backend(backend_config)
            logger.info(f"Added backend {backend_config['name']}: {result['success']}")
        
        # List updated backends
        backends_result = await self.replication_manager.list_storage_backends()
        logger.info(f"Total backends after adding: {len(backends_result.get('backends', []))}")
        
        return backends_result["success"]
    
    async def demo_pin_registration(self):
        """Demonstrate pin registration and replication."""
        logger.info("\n=== Pin Registration & Replication Demo ===")
        
        # Sample pins to register
        sample_pins = [
            {
                "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
                "vfs_metadata_id": "dataset_001",
                "size_bytes": 1024 * 1024 * 50,  # 50MB
                "target_replicas": 3,
                "priority": 1
            },
            {
                "cid": "QmZ1234567890abcdefghijklmnopqrstuvwxyzABCDEF", 
                "vfs_metadata_id": "dataset_002",
                "size_bytes": 1024 * 1024 * 25,  # 25MB
                "target_replicas": 2,
                "priority": 2
            },
            {
                "cid": "QmA9876543210fedcba9876543210fedcba9876543210",
                "vfs_metadata_id": "vector_index_001",
                "size_bytes": 1024 * 1024 * 100,  # 100MB
                "target_replicas": 4,
                "priority": 1
            }
        ]
        
        registration_results = []
        for pin_data in sample_pins:
            result = await self.replication_manager.register_pin_for_replication(**pin_data)
            registration_results.append(result)
            logger.info(f"Registered pin {pin_data['cid']}: {result['success']}")
        
        # Demonstrate manual replication to specific backends
        test_cid = sample_pins[0]["cid"]
        backends_to_test = ["demo_cluster", "demo_pinata"]
        
        for backend_name in backends_to_test:
            replication_result = await self.replication_manager.replicate_pin_to_backend(
                test_cid, backend_name
            )
            logger.info(f"Replicated {test_cid} to {backend_name}: {replication_result['success']}")
        
        return all(result["success"] for result in registration_results)
    
    async def demo_replication_status(self):
        """Demonstrate replication status monitoring."""
        logger.info("\n=== Replication Status Demo ===")
        
        # Get overall replication status
        status_result = await self.replication_manager.get_replication_status()
        logger.info("Overall Replication Status:")
        logger.info(f"  Total pins: {status_result['summary']['total_pins']}")
        logger.info(f"  Healthy replicated: {status_result['summary']['healthy_replicated']}")
        logger.info(f"  Under-replicated: {status_result['summary']['under_replicated']}")
        logger.info(f"  Over-replicated: {status_result['summary']['over_replicated']}")
        logger.info(f"  Replication ratio: {status_result['summary']['replication_ratio']:.2%}")
        
        # Check individual pin status
        test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        pin_status = await self.replication_manager.get_pin_replication_status(test_cid)
        if pin_status["success"]:
            replication = pin_status["replication"]
            logger.info(f"\nPin {test_cid} status:")
            logger.info(f"  Current replicas: {replication['current_replicas']}")
            logger.info(f"  Target replicas: {replication['target_replicas']}")
            logger.info(f"  Backends: {', '.join(replication['backends'])}")
            logger.info(f"  Status: {replication['status']}")
        
        return status_result["success"]
    
    async def demo_export_import(self):
        """Demonstrate backend export/import functionality."""
        logger.info("\n=== Export/Import Demo ===")
        
        # Export pins from local backend
        export_result = await self.replication_manager.export_backend_pins("local")
        if export_result["success"]:
            logger.info(f"Exported {export_result['export_data']['total_pins']} pins from local backend")
            logger.info(f"Export file: {export_result['export_file']}")
            
            # Demonstrate import (using the same file for demo)
            import_result = await self.replication_manager.import_backend_pins(
                "demo_cluster", export_result['export_file']
            )
            if import_result["success"]:
                logger.info(f"Imported {import_result['imported_count']} pins to demo_cluster")
                if import_result["errors"]:
                    logger.warning(f"Import errors: {len(import_result['errors'])}")
            else:
                logger.error(f"Import failed: {import_result['error']}")
        else:
            logger.error(f"Export failed: {export_result['error']}")
        
        return export_result["success"]
    
    async def demo_monitoring(self):
        """Demonstrate background monitoring."""
        logger.info("\n=== Monitoring Demo ===")
        
        # Start monitoring
        start_result = await self.replication_manager.start_monitoring()
        logger.info(f"Started monitoring: {start_result['success']}")
        
        # Let it run for a few seconds
        logger.info("Monitoring active for 5 seconds...")
        await anyio.sleep(5)
        
        # Check status while monitoring is active
        status_result = await self.replication_manager.get_replication_status()
        logger.info(f"Monitoring active: {status_result['summary']['monitoring_active']}")
        
        # Stop monitoring
        stop_result = await self.replication_manager.stop_monitoring()
        logger.info(f"Stopped monitoring: {stop_result['success']}")
        
        return start_result["success"] and stop_result["success"]
    
    async def demo_api_integration(self):
        """Demonstrate API integration."""
        logger.info("\n=== API Integration Demo ===")
        
        try:
            # Create replication API
            replication_api = create_replication_api(self.replication_manager)
            logger.info("✓ Replication API created successfully")
            
            # Show available endpoints
            logger.info("Available API endpoints:")
            for route in replication_api.router.routes:
                if hasattr(route, 'methods') and hasattr(route, 'path'):
                    methods = ', '.join(route.methods)
                    logger.info(f"  {methods} {route.path}")
            
            return True
            
        except Exception as e:
            logger.error(f"API integration error: {e}")
            return False
    
    async def run_complete_demo(self):
        """Run the complete replication management demo."""
        logger.info("Starting Comprehensive Replication Management Demo")
        logger.info("=" * 60)
        
        results = []
        
        # Phase 1: Settings Management
        logger.info("Phase 1: Settings Management...")
        settings_success = await self.demo_replication_settings()
        results.append(("Settings Management", settings_success))
        
        # Phase 2: Backend Management
        logger.info("Phase 2: Backend Management...")
        backends_success = await self.demo_storage_backends()
        results.append(("Backend Management", backends_success))
        
        # Phase 3: Pin Registration
        logger.info("Phase 3: Pin Registration...")
        pins_success = await self.demo_pin_registration()
        results.append(("Pin Registration", pins_success))
        
        # Phase 4: Status Monitoring
        logger.info("Phase 4: Status Monitoring...")
        status_success = await self.demo_replication_status()
        results.append(("Status Monitoring", status_success))
        
        # Phase 5: Export/Import
        logger.info("Phase 5: Export/Import...")
        export_success = await self.demo_export_import()
        results.append(("Export/Import", export_success))
        
        # Phase 6: Background Monitoring
        logger.info("Phase 6: Background Monitoring...")
        monitoring_success = await self.demo_monitoring()
        results.append(("Background Monitoring", monitoring_success))
        
        # Phase 7: API Integration
        logger.info("Phase 7: API Integration...")
        api_success = await self.demo_api_integration()
        results.append(("API Integration", api_success))
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("DEMO RESULTS SUMMARY")
        logger.info("=" * 60)
        
        successful_phases = 0
        for phase_name, success in results:
            status = "✓ PASS" if success else "✗ FAIL"
            logger.info(f"{phase_name:<25}: {status}")
            if success:
                successful_phases += 1
        
        success_rate = (successful_phases / len(results)) * 100
        logger.info(f"\nSuccess Rate: {success_rate:.1f}% ({successful_phases}/{len(results)} phases)")
        
        if success_rate == 100:
            logger.info("🎉 All replication management features working perfectly!")
        elif success_rate >= 80:
            logger.info("✅ Replication system mostly functional with minor issues")
        else:
            logger.warning("⚠️  Replication system needs attention")
        
        # Save results
        results_data = {
            "demo_completed": datetime.utcnow().isoformat(),
            "success_rate": success_rate,
            "phases": [{"name": name, "success": success} for name, success in results],
            "summary": {
                "total_phases": len(results),
                "successful_phases": successful_phases,
                "failed_phases": len(results) - successful_phases
            }
        }
        
        results_file = "replication_demo_results.json"
        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        logger.info(f"Results saved to: {results_file}")
        return success_rate


async def main():
    """Main demo function."""
    demo = ReplicationDemo()
    
    try:
        await demo.initialize()
        success_rate = await demo.run_complete_demo()
        
        if success_rate >= 80:
            return 0  # Success
        else:
            return 1  # Failure
            
    except KeyboardInterrupt:
        logger.info("\nDemo interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Demo failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = anyio.run(main)

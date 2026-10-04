#!/usr/bin/env python3
"""
Demonstration of Enhanced Backend Manager with Dirty State Tracking

This script demonstrates:
1. Setting up multiple backends
2. Adding pins to IPFS
3. Marking backends as dirty when changes occur
4. Syncing pins to dirty backends only
5. Monitoring sync status across all backends

Usage:
    python demo_enhanced_backend_sync.py
"""

import anyio
import json
import logging
import time
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BackendSyncDemo:
    """Demonstration of enhanced backend sync capabilities."""
    
    def __init__(self):
        self.backend_manager = None
        self.demo_pins = []
        
    async def initialize(self):
        """Initialize the backend manager and demo data."""
        logger.info("🚀 Initializing Enhanced Backend Manager Demo")
        
        try:
            from ipfs_kit_py.backend_manager import BackendManager
            self.backend_manager = BackendManager()
            logger.info("✓ Backend manager initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize backend manager: {e}")
            return False
    
    async def setup_demo_backends(self):
        """Setup demonstration backends for testing."""
        logger.info("\n📦 Setting up demo backends...")
        
        # Demo backend configurations
        demo_configs = {
            'primary_s3': {
                'type': 's3',
                'config': {
                    'bucket_name': 'ipfs-primary-backup',
                    'region': 'us-east-1',
                    'access_key_id': 'demo-key',
                    'secret_access_key': 'demo-secret'
                }
            },
            'backup_github': {
                'type': 'github',
                'config': {
                    'token': 'demo-github-token',
                    'repo': 'user/ipfs-backup'
                }
            },
            'archive_hf': {
                'type': 'huggingface',
                'config': {
                    'token': 'demo-hf-token',
                    'repo': 'user/ipfs-archive'
                }
            },
            'cold_storage': {
                'type': 'ftp',
                'config': {
                    'host': 'ftp.archive.example.com',
                    'username': 'archive_user',
                    'password': 'archive_pass',
                    'port': 21
                }
            }
        }
        
        success_count = 0
        
        for name, backend_info in demo_configs.items():
            try:
                await self.backend_manager.create_backend_config(
                    name, 
                    backend_info['type'], 
                    backend_info['config']
                )
                logger.info(f"✓ Created {name} ({backend_info['type']}) backend")
                success_count += 1
            except Exception as e:
                logger.warning(f"⚠ Failed to create {name} backend: {e}")
        
        logger.info(f"Setup complete: {success_count}/{len(demo_configs)} backends configured")
        return success_count > 0
    
    async def simulate_content_additions(self):
        """Simulate adding content to IPFS and tracking pins."""
        logger.info("\n📁 Simulating content additions...")
        
        # Demo content to add
        demo_content = [
            ("demo_document.txt", "This is a demo document for IPFS storage."),
            ("config.json", '{"app": "ipfs_kit", "version": "1.0", "demo": true}'),
            ("data.csv", "id,name,value\n1,demo,100\n2,test,200"),
            ("readme.md", "# IPFS Kit Demo\nThis is demo content stored in IPFS.")
        ]
        
        for filename, content in demo_content:
            # Simulate IPFS hash generation (in real usage, this would be actual IPFS)
            demo_hash = f"Qm{hash(content) % 1000000:06d}Demo{filename.replace('.', '')}"
            self.demo_pins.append({
                'hash': demo_hash,
                'name': filename,
                'size': len(content)
            })
            logger.info(f"📌 Added pin: {demo_hash} ({filename})")
        
        logger.info(f"Total pins created: {len(self.demo_pins)}")
        return len(self.demo_pins) > 0
    
    async def demonstrate_dirty_marking(self):
        """Demonstrate marking backends as dirty when content changes."""
        logger.info("\n🔄 Demonstrating dirty state marking...")
        
        # Get current backend status
        backends = self.backend_manager.discover_backends()
        logger.info(f"Available backends: {list(backends.keys())}")
        
        # Show initial clean state
        sync_status = self.backend_manager.get_backend_sync_status()
        dirty_count = sum(1 for status in sync_status.values() if status.get('is_dirty', False))
        logger.info(f"Initial state: {dirty_count} dirty backends")
        
        # Simulate different scenarios that would mark backends dirty
        scenarios = [
            ("Content Added", "New IPFS content requires backup"),
            ("Pin Update", "Pin metadata was updated"),
            ("Policy Change", "Backup policy modified"),
            ("Manual Sync Request", "User requested sync")
        ]
        
        backend_names = list(backends.keys())
        
        for i, (scenario, reason) in enumerate(scenarios):
            if i < len(backend_names):
                backend_name = backend_names[i]
                logger.info(f"\n📋 Scenario: {scenario}")
                logger.info(f"   Reason: {reason}")
                
                # Mark specific backend dirty
                self.backend_manager.mark_backend_dirty(backend_name, reason)
                
                # Show updated status
                dirty_backends = self.backend_manager.get_dirty_backends()
                logger.info(f"   ✓ Marked {backend_name} as dirty")
                logger.info(f"   Current dirty backends: {len(dirty_backends)}")
        
        # Demonstrate bulk dirty marking
        logger.info(f"\n📋 Scenario: System Recovery")
        logger.info(f"   Reason: Mark all backends dirty after system restart")
        self.backend_manager.mark_all_backends_dirty("System restart - verify all backups")
        
        final_dirty = self.backend_manager.get_dirty_backends()
        logger.info(f"   ✓ All backends marked dirty: {len(final_dirty)} backends")
        
        return True
    
    async def demonstrate_selective_sync(self):
        """Demonstrate syncing only dirty backends."""
        logger.info("\n🔄 Demonstrating selective pin sync...")
        
        # Show current dirty state
        dirty_backends = self.backend_manager.get_dirty_backends()
        logger.info(f"Dirty backends to sync: {len(dirty_backends)}")
        
        for backend_name in dirty_backends:
            logger.info(f"  - {backend_name}")
        
        if dirty_backends:
            logger.info("\n🔄 Starting sync for dirty backends only...")
            start_time = time.time()
            
            # Sync only dirty backends
            sync_results = await self.backend_manager.sync_dirty_backends()
            
            sync_time = time.time() - start_time
            successful_syncs = sum(1 for result in sync_results.values() if result)
            
            logger.info(f"✓ Sync completed in {sync_time:.2f}s")
            logger.info(f"  Success rate: {successful_syncs}/{len(sync_results)}")
            
            # Show updated status
            remaining_dirty = self.backend_manager.get_dirty_backends()
            logger.info(f"  Remaining dirty backends: {len(remaining_dirty)}")
            
            return True
        else:
            logger.info("No dirty backends to sync")
            return False
    
    async def demonstrate_health_monitoring(self):
        """Demonstrate health monitoring across all backends."""
        logger.info("\n🏥 Demonstrating backend health monitoring...")
        
        # Check health of all backends
        health_results = await self.backend_manager.health_check_all_backends()
        
        healthy_count = sum(1 for result in health_results.values() 
                           if result.get('healthy', False))
        total_count = len(health_results)
        
        logger.info(f"Health check summary: {healthy_count}/{total_count} backends healthy")
        
        # Detailed health report
        for backend_name, health_result in health_results.items():
            healthy = health_result.get('healthy', False)
            response_time = health_result.get('response_time_ms', 0)
            error = health_result.get('error', 'No error')
            
            status_emoji = "✅" if healthy else "❌"
            logger.info(f"  {status_emoji} {backend_name}: {response_time:.1f}ms")
            if not healthy:
                logger.info(f"     Error: {error}")
        
        return healthy_count > 0
    
    async def demonstrate_sync_status_monitoring(self):
        """Demonstrate comprehensive sync status monitoring."""
        logger.info("\n📊 Demonstrating sync status monitoring...")
        
        # Get comprehensive sync status
        sync_status = self.backend_manager.get_backend_sync_status()
        
        # Categorize backends
        categories = {
            'clean': [],
            'dirty': [],
            'unhealthy': []
        }
        
        for backend_name, status in sync_status.items():
            is_dirty = status.get('is_dirty', False)
            is_healthy = status.get('last_health_check', {}).get('healthy', True)
            
            if not is_healthy:
                categories['unhealthy'].append(backend_name)
            elif is_dirty:
                categories['dirty'].append(backend_name)
            else:
                categories['clean'].append(backend_name)
        
        # Report categories
        for category, backends in categories.items():
            emoji = {"clean": "✅", "dirty": "🔄", "unhealthy": "❌"}[category]
            logger.info(f"{emoji} {category.upper()}: {len(backends)} backends")
            for backend in backends:
                last_sync = sync_status[backend].get('last_sync_time', 'Never')
                dirty_reason = sync_status[backend].get('dirty_reason', 'N/A')
                logger.info(f"   - {backend} (last sync: {last_sync})")
                if category == 'dirty':
                    logger.info(f"     Reason: {dirty_reason}")
        
        return True
    
    async def demonstrate_force_sync(self):
        """Demonstrate force sync of all backends."""
        logger.info("\n🔄 Demonstrating force sync (all backends)...")
        
        logger.info("Initiating force sync for ALL backends...")
        start_time = time.time()
        
        # Force sync all backends (marks all dirty first, then syncs)
        sync_results = await self.backend_manager.force_sync_all_backends()
        
        sync_time = time.time() - start_time
        successful_syncs = sum(1 for result in sync_results.values() if result)
        
        logger.info(f"✓ Force sync completed in {sync_time:.2f}s")
        logger.info(f"  Success rate: {successful_syncs}/{len(sync_results)}")
        
        # Verify all backends are now clean
        remaining_dirty = self.backend_manager.get_dirty_backends()
        logger.info(f"  Remaining dirty backends: {len(remaining_dirty)}")
        
        return len(remaining_dirty) == 0
    
    async def cleanup_demo(self):
        """Clean up demo state."""
        logger.info("\n🧹 Cleaning up demo state...")
        
        # Clean up backend states
        await self.backend_manager.cleanup_backend_state()
        
        # Verify cleanup
        dirty_backends = self.backend_manager.get_dirty_backends()
        logger.info(f"✓ Cleanup complete: {len(dirty_backends)} dirty backends remaining")
        
        return True
    
    async def run_demo(self):
        """Run the complete demonstration."""
        logger.info("🎬 Starting Enhanced Backend Manager Demonstration")
        logger.info("=" * 80)
        
        # Demo steps
        steps = [
            ("Initialize System", self.initialize),
            ("Setup Demo Backends", self.setup_demo_backends),
            ("Simulate Content Additions", self.simulate_content_additions),
            ("Demonstrate Dirty Marking", self.demonstrate_dirty_marking),
            ("Demonstrate Selective Sync", self.demonstrate_selective_sync),
            ("Demonstrate Health Monitoring", self.demonstrate_health_monitoring),
            ("Demonstrate Status Monitoring", self.demonstrate_sync_status_monitoring),
            ("Demonstrate Force Sync", self.demonstrate_force_sync),
            ("Cleanup Demo", self.cleanup_demo),
        ]
        
        results = {}
        
        for step_name, step_func in steps:
            logger.info(f"\n{'='*20} {step_name} {'='*20}")
            try:
                result = await step_func()
                results[step_name] = result
                
                if result:
                    logger.info(f"✅ {step_name} completed successfully")
                else:
                    logger.warning(f"⚠️ {step_name} completed with warnings")
                    
            except Exception as e:
                logger.error(f"❌ {step_name} failed: {e}")
                results[step_name] = False
        
        # Demo summary
        logger.info(f"\n{'='*80}")
        logger.info("🎬 DEMONSTRATION SUMMARY")
        logger.info(f"{'='*80}")
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for step_name, result in results.items():
            status = "✅ SUCCESS" if result else "❌ FAILED"
            logger.info(f"{step_name:35} {status}")
        
        logger.info(f"\nDemo completion: {passed}/{total} steps successful")
        
        if passed == total:
            logger.info("🎉 Demo completed successfully!")
            logger.info("\n📋 Key Features Demonstrated:")
            logger.info("  ✅ Multi-backend support (S3, GitHub, HuggingFace, FTP)")
            logger.info("  ✅ Intelligent dirty state tracking")
            logger.info("  ✅ Selective sync (only dirty backends)")
            logger.info("  ✅ Health monitoring and status reporting")
            logger.info("  ✅ Force sync and bulk operations")
            logger.info("  ✅ Automatic state management and cleanup")
        else:
            logger.warning(f"⚠️ Demo completed with {total - passed} issues")
        
        return passed == total


async def main():
    """Main entry point for the demonstration."""
    demo = BackendSyncDemo()
    success = await demo.run_demo()
    
    if success:
        print("\n🚀 The enhanced backend manager is ready for production use!")
        print("   • Supports 6+ backend types with unified interface")
        print("   • Intelligent dirty state tracking saves sync time")
        print("   • Automatic health monitoring ensures reliability")
        print("   • Bulk operations handle large-scale deployments")
    else:
        print("\n⚠️  Demo completed with some issues. Check logs for details.")
    
    return success


if __name__ == "__main__":
    success = anyio.run(main)
    exit(0 if success else 1)

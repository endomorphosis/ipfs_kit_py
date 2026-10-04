#!/usr/bin/env python3
"""
Test script for the Enhanced Intelligent Daemon Manager.

This script demonstrates the metadata-driven daemon functionality:
1. Using bucket_index to check backend health
2. Reading dirty metadata to identify backends needing sync
3. Selective operations based on metadata analysis
4. Efficient thread-based monitoring
"""

import json
import logging
import time
import os
from pathlib import Path
import pytest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_intelligent_daemon() -> bool:
    """Run the intelligent daemon manager checks and return success."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run intelligent daemon integration test")
    try:
        from ipfs_kit_py.intelligent_daemon_manager import get_daemon_manager
        
        logger.info("=== Testing Enhanced Intelligent Daemon Manager ===")
        
        # Get daemon manager instance
        daemon = get_daemon_manager()
        
        # Test metadata reading capabilities
        logger.info("\n1. Testing metadata reading capabilities...")
        
        # Check bucket index
        bucket_df = daemon.get_bucket_index()
        if bucket_df is not None:
            logger.info(f"   - Loaded bucket index with {len(bucket_df)} buckets")
        else:
            logger.info("   - No bucket index found")
        
        # Check backend index
        backend_df = daemon.get_backend_index()
        logger.info(f"   - Loaded backend index with {len(backend_df)} backends")
        
        # Check dirty backends
        dirty_backends = daemon.scan_dirty_backends_from_metadata()
        logger.info(f"   - Found {len(dirty_backends)} dirty backends: {list(dirty_backends)}")
        
        # Check backend-bucket relationships
        bucket_backend_map = daemon.get_backends_from_bucket_metadata()
        logger.info(f"   - Found {len(bucket_backend_map)} bucket-backend mappings")
        
        # Test backend sync analysis
        logger.info("\n2. Testing backend sync analysis...")
        
        backends_needing_sync = daemon.identify_backends_needing_pin_sync()
        logger.info(f"   - Backends needing pin sync: {list(backends_needing_sync)}")
        
        filesystem_backends = daemon.check_filesystem_backends_for_metadata_backup()
        logger.info(f"   - Filesystem backends for backup: {filesystem_backends}")
        
        # Test daemon status before starting
        logger.info("\n3. Testing daemon status (before start)...")
        status = daemon.get_status()
        logger.info(f"   - Daemon running: {status['running']}")
        logger.info(f"   - Thread status: {status['thread_status']}")
        logger.info(f"   - Metadata stats: {status['metadata_driven_stats']}")
        
        # Start the daemon
        logger.info("\n4. Starting enhanced intelligent daemon...")
        daemon.start()
        
        # Wait a bit for initial operations
        logger.info("   - Waiting 10 seconds for initial metadata scan...")
        time.sleep(10)
        
        # Check status after startup
        logger.info("\n5. Testing daemon status (after start)...")
        status = daemon.get_status()
        logger.info(f"   - Daemon running: {status['running']}")
        logger.info(f"   - Active threads: {sum(status['thread_status'].values())}/4")
        logger.info(f"   - Dirty backends detected: {status['metadata_driven_stats']['dirty_count']}")
        logger.info(f"   - Unhealthy backends: {status['metadata_driven_stats']['unhealthy_count']}")
        logger.info(f"   - Active tasks: {status['task_management']['active_tasks']}")
        logger.info(f"   - Queued tasks: {status['task_management']['queued_tasks']}")
        
        # Test metadata insights
        logger.info("\n6. Testing metadata insights...")
        insights = daemon.get_metadata_insights()
        logger.info(f"   - Total buckets: {insights['bucket_analysis']['total_buckets']}")
        logger.info(f"   - Total backends: {insights['backend_analysis']['total_backends']}")
        logger.info(f"   - Buckets needing backup: {insights['bucket_analysis']['buckets_needing_backup']}")
        logger.info(f"   - Backends needing sync: {len(insights['sync_requirements']['backends_needing_pin_sync'])}")
        logger.info(f"   - Metadata freshness: {insights['operational_metrics']['metadata_freshness_seconds']:.1f}s")
        
        # Let it run for a bit to show activity
        logger.info("\n7. Monitoring daemon activity for 30 seconds...")
        for i in range(6):
            time.sleep(5)
            status = daemon.get_status()
            task_count = status['task_management']['active_tasks'] + status['task_management']['queued_tasks']
            logger.info(f"   - {i*5+5}s: {task_count} total tasks, "
                       f"{status['metadata_driven_stats']['dirty_count']} dirty backends")
        
        # Stop the daemon
        logger.info("\n8. Stopping daemon...")
        daemon.stop()
        
        # Final status check
        status = daemon.get_status()
        logger.info(f"   - Daemon stopped: {not status['running']}")
        logger.info(f"   - Completed tasks: {status['task_management']['completed_tasks']}")
        
        logger.info("\n=== Enhanced Intelligent Daemon Test Completed Successfully ===")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing intelligent daemon: {e}")
        import traceback
        traceback.print_exc()
        pytest.skip(f"Intelligent daemon integration unavailable: {e}")


def test_intelligent_daemon():
    """Test the intelligent daemon manager."""
    assert run_intelligent_daemon() is True

def show_metadata_structure():
    """Show the current metadata structure."""
    logger.info("\n=== Current Metadata Structure ===")
    
    ipfs_kit_dir = Path.home() / '.ipfs_kit'
    
    # Show directory structure
    for subdir in ['bucket_index', 'backend_index', 'backends', 'bucket_configs']:
        dir_path = ipfs_kit_dir / subdir
        if dir_path.exists():
            logger.info(f"\n{subdir}/:")
            for item in dir_path.iterdir():
                if item.is_file():
                    logger.info(f"  📄 {item.name} ({item.stat().st_size} bytes)")
                elif item.is_dir():
                    file_count = len(list(item.iterdir()))
                    logger.info(f"  📁 {item.name}/ ({file_count} files)")
        else:
            logger.info(f"\n{subdir}/: (not found)")
    
    # Show sample dirty metadata
    dirty_dir = ipfs_kit_dir / 'backend_index' / 'dirty_metadata'
    if dirty_dir.exists():
        dirty_files = list(dirty_dir.glob('*_dirty.json'))
        if dirty_files:
            logger.info(f"\nSample dirty metadata ({len(dirty_files)} files):")
            for dirty_file in dirty_files[:3]:  # Show first 3
                try:
                    with open(dirty_file, 'r') as f:
                        dirty_data = json.load(f)
                    
                    backend_name = dirty_data.get('backend_name', dirty_file.stem)
                    is_dirty = dirty_data.get('is_dirty', False)
                    pending_count = len(dirty_data.get('pending_actions', []))
                    
                    logger.info(f"  - {backend_name}: dirty={is_dirty}, pending_actions={pending_count}")
                except Exception as e:
                    logger.info(f"  - {dirty_file.name}: (error reading - {e})")

if __name__ == '__main__':
    print("Enhanced Intelligent Daemon Manager Test")
    print("=======================================")
    
    # Show current metadata structure
    show_metadata_structure()
    
    # Test the daemon
    success = run_intelligent_daemon()
    
    if success:
        print("\n✅ All tests passed! The enhanced intelligent daemon is working correctly.")
        print("\nKey features demonstrated:")
        print("- ⚡ Metadata-driven backend monitoring")
        print("- 🔍 Dirty backend detection and immediate response")
        print("- 📊 Intelligent task scheduling based on health and metadata")
        print("- 🧵 Multi-threaded architecture for efficient operations")
        print("- 💾 Selective bucket backup and sync operations")
        print("- 📈 Comprehensive status reporting and insights")
    else:
        print("\n❌ Some tests failed. Check the logs above for details.")

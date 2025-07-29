#!/usr/bin/env python3
"""
Test Pin Metadata Index Performance
===================================

This script tests that the pin metadata index eliminates blocking calls
and improves dashboard performance.
"""

import asyncio
import logging
import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ipfs_kit_py.pins import IPFSPinMetadataIndex

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_pin_metadata_index():
    """Test the pin metadata index functionality."""
    logger.info("🧪 Testing IPFS Pin Metadata Index")
    
    # Create index instance
    index = IPFSPinMetadataIndex(
        cache_file="/tmp/test_pin_cache.json",
        update_interval=30,  # Short interval for testing
        ipfs_api_url="http://127.0.0.1:5001"
    )
    
    try:
        # Start the index
        await index.start()
        logger.info("✓ Pin metadata index started")
        
        # Wait a moment for initial update
        logger.info("⏳ Waiting for initial pin data update...")
        await asyncio.sleep(5)
        
        # Test getting traffic metrics (should be fast)
        start_time = time.time()
        traffic_metrics = index.get_traffic_metrics()
        metrics_time = time.time() - start_time
        
        logger.info(f"📊 Traffic Metrics (retrieved in {metrics_time:.3f}s):")
        logger.info(f"   Total pins: {traffic_metrics.total_pins}")
        logger.info(f"   Total size: {traffic_metrics.total_size_bytes / (1024*1024):.2f} MB")
        logger.info(f"   Pins accessed last hour: {traffic_metrics.pins_accessed_last_hour}")
        logger.info(f"   Bandwidth estimate: {traffic_metrics.bandwidth_estimate_bytes / (1024*1024):.2f} MB")
        logger.info(f"   Hot pins: {len(traffic_metrics.hot_pins)}")
        
        # Test cache statistics
        cache_stats = index.get_cache_stats()
        logger.info(f"🗄️ Cache Statistics:")
        logger.info(f"   Cached pins: {cache_stats['total_pins_cached']}")
        logger.info(f"   Cache hit rate: {cache_stats['cache_hit_rate']:.2%}")
        logger.info(f"   Last update age: {cache_stats['last_update_age']:.1f}s")
        logger.info(f"   Update in progress: {cache_stats['update_in_progress']}")
        
        # Test individual pin lookup
        if traffic_metrics.total_pins > 0:
            all_pins = index.get_all_pins()
            first_cid = list(all_pins.keys())[0]
            
            start_time = time.time()
            pin_metadata = index.get_pin_metadata(first_cid)
            lookup_time = time.time() - start_time
            
            logger.info(f"🔍 Pin Lookup Test (retrieved in {lookup_time:.3f}s):")
            if pin_metadata:
                logger.info(f"   CID: {pin_metadata.cid}")
                logger.info(f"   Size: {pin_metadata.size_bytes / (1024*1024):.2f} MB")
                logger.info(f"   Type: {pin_metadata.type}")
                logger.info(f"   Access count: {pin_metadata.access_count}")
        
        # Test simulated pin access (for traffic tracking)
        logger.info("📈 Testing pin access tracking...")
        test_cid = "QmTest123456789"
        index.record_pin_access(test_cid, size_hint=1024*1024)  # 1MB
        
        # Force an update and measure time
        logger.info("🔄 Testing forced update performance...")
        start_time = time.time()
        success = index.force_update()
        if success:
            # Wait for update to complete
            while index.update_in_progress:
                await asyncio.sleep(0.1)
            update_time = time.time() - start_time
            logger.info(f"✓ Forced update completed in {update_time:.3f}s")
        else:
            logger.warning("⚠️ Could not force update (already in progress or not running)")
        
        # Test performance by calling metrics multiple times rapidly
        logger.info("⚡ Testing rapid metrics access (dashboard simulation)...")
        start_time = time.time()
        for i in range(10):
            traffic_metrics = index.get_traffic_metrics()
            cache_stats = index.get_cache_stats()
        rapid_access_time = time.time() - start_time
        
        logger.info(f"✓ 10 rapid metrics calls completed in {rapid_access_time:.3f}s")
        logger.info(f"   Average per call: {(rapid_access_time/10)*1000:.1f}ms")
        
        # Final cache stats
        final_cache_stats = index.get_cache_stats()
        logger.info(f"📈 Final Performance Metrics:")
        logger.info(f"   Total updates: {final_cache_stats['metrics']['total_updates']}")
        logger.info(f"   Successful updates: {final_cache_stats['metrics']['successful_updates']}")
        logger.info(f"   Cache hits: {final_cache_stats['metrics']['cache_hits']}")
        logger.info(f"   Cache misses: {final_cache_stats['metrics']['cache_misses']}")
        logger.info(f"   Average update duration: {final_cache_stats['metrics'].get('average_update_duration', 0):.2f}s")
        
        logger.info("✅ Pin metadata index test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        # Stop the index
        await index.stop()
        logger.info("✓ Pin metadata index stopped")


async def main():
    """Main test function."""
    try:
        await test_pin_metadata_index()
        return 0
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)

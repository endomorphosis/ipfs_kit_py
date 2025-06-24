"""
Script to debug the 'NoneType' object is not subscriptable errors in the AdaptiveThreadPool.
"""

import sys
import time
import logging
import threading
from ipfs_kit_py.resource_management import ResourceMonitor, AdaptiveThreadPool
from ipfs_kit_py.content_aware_prefetch import ContentAwarePrefetchManager

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   stream=sys.stdout)

# Create a resource monitor
resource_monitor = ResourceMonitor()

# Create an adaptive thread pool
thread_pool = AdaptiveThreadPool(
    resource_monitor=resource_monitor,
    config={
        "initial_threads": 2,
        "min_threads": 1,
        "max_threads": 4,
        "worker_type": "prefetch",
        "dynamic_adjustment": True,
        "adjustment_interval": 1.0,
        "priority_levels": 3
    },
    name="debug_prefetch"
)

# Create a prefetch manager with the adaptive thread pool
prefetch_manager = ContentAwarePrefetchManager(
    tiered_cache_manager=None,  # No actual cache needed for this test
    config={
        "enabled": True,
        "max_prefetch_items": 5,
        "prefetch_threshold": 0.3,
        "max_concurrent_prefetch": 3,
        "enable_logging": True
    },
    resource_monitor=resource_monitor
)

# Simple prefetch function that we'll submit to the thread pool
def mock_prefetch_item(cid, content_type, strategy):
    """Simulate prefetching an item."""
    logger = logging.getLogger("mock_prefetch")
    logger.debug(f"Starting prefetch for {cid}, content_type={content_type}")

    # Simulate some work
    time.sleep(0.5)

    # Return a result
    return {
        "cid": cid,
        "content_type": content_type,
        "strategy": strategy.get("prefetch_strategy", "default"),
        "success": True,
        "timestamp": time.time(),
        "elapsed": 0.5,
        "size": 1024  # Simulated size
    }

# Submit a bunch of tasks to test different scenarios
def test_basic_submission():
    """Test basic task submission."""
    print("Testing basic task submission...")

    # Submit a few tasks directly to the thread pool
    for i in range(5):
        cid = f"test_cid_{i}"
        content_type = "video" if i % 2 == 0 else "document"
        strategy = {"prefetch_strategy": "sliding_window", "chunk_size": 2}

        thread_pool.submit(
            mock_prefetch_item,
            cid,
            content_type,
            strategy,
            priority=i % 3
        )

    # Give tasks time to complete
    time.sleep(3)
    print("Basic submission test completed")

def test_prefetch_manager():
    """Test the prefetch manager's task handling."""
    print("\nTesting prefetch manager task handling...")

    # Simulate content accesses to trigger prefetching
    for i in range(5):
        cid = f"manager_test_cid_{i}"
        content_type = "video" if i % 2 == 0 else "document"

        metadata = {
            "filename": f"test_{i}.{'mp4' if i % 2 == 0 else 'pdf'}",
            "size": 1024 * (i + 1),
            "position": i * 100,  # For video positional prefetching
            "duration": 600  # 10 minutes
        }

        # Create a sample of content
        content_sample = b"Test content sample" + bytes([i] * 20)

        # Record the access which will trigger prefetching
        result = prefetch_manager.record_content_access(cid, metadata, content_sample)
        print(f"Content access recorded for {cid}, content_type={result['content_type']}, prefetch_scheduled={result['prefetch_scheduled']}")

    # Give tasks time to complete
    time.sleep(3)
    print("Prefetch manager test completed")

def test_edge_cases():
    """Test edge cases that might cause errors."""
    print("\nTesting edge cases...")

    # Case 1: None parameter
    try:
        thread_pool.submit(mock_prefetch_item, None, "video", {"prefetch_strategy": "sliding_window"})
        print("Submitted task with None CID")
    except Exception as e:
        print(f"Error submitting task with None CID: {e}")

    # Case 2: Empty strategy dictionary (should work as we check for dictionary type, not content)
    try:
        thread_pool.submit(
            mock_prefetch_item,
            "edge_case_cid_1",
            "video",
            {},  # Empty dictionary should be handled gracefully
            priority=0
        )
        print("Submitted task with empty strategy dictionary")
    except Exception as e:
        print(f"Error submitting task with empty strategy dictionary: {e}")

    # Case 3: Complete valid parameters
    try:
        thread_pool.submit(
            mock_prefetch_item,
            "edge_case_cid_2",
            "video",
            {"prefetch_strategy": "default"},
            priority=0
        )
        print("Submitted task with all required parameters")
    except Exception as e:
        print(f"Error submitting task with all required parameters: {e}")

    # Give tasks time to complete
    time.sleep(3)
    print("Edge case tests completed")

def test_shutdown():
    """Test graceful shutdown."""
    print("\nTesting shutdown behavior...")

    # Submit a few more tasks
    for i in range(3):
        thread_pool.submit(
            mock_prefetch_item,
            f"shutdown_test_cid_{i}",
            "video",
            {"prefetch_strategy": "sliding_window"},
            priority=0  # High priority
        )

    # Start shutdown
    print("Initiating shutdown...")
    thread_pool.shutdown(wait=True)

    # Stop the prefetch manager
    prefetch_manager.stop()

    print("Shutdown complete")

if __name__ == "__main__":
    try:
        print("Starting debug tests...")
        test_basic_submission()
        test_prefetch_manager()
        test_edge_cases()
        test_shutdown()
        print("All tests completed successfully!")
    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        # Make sure everything is cleaned up
        thread_pool.shutdown(wait=False)
        prefetch_manager.stop()

#!/usr/bin/env python
"""
Test script for verifying Lotus daemon management capabilities in ipfs_kit.

This script tests:
1. Initializing ipfs_kit with Lotus daemon support
2. Checking daemon status
3. Starting the daemon manually
4. Stopping the daemon
5. Role-based auto-start behavior
"""

import time
import logging
from ipfs_kit_py import ipfs_kit

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("lotus_daemon_test")

def test_lotus_daemon_management():
    """Test Lotus daemon management capabilities."""
    logger.info("Testing Lotus daemon management capabilities")
    
    # Initialize with auto-start disabled for testing
    kit = ipfs_kit(metadata={"auto_start_lotus_daemon": False})
    
    # Check initial status
    status = kit.check_daemon_status()
    logger.info(f"Initial daemon status: {status.get('daemons', {}).get('lotus', {})}")
    
    # Ensure daemon is stopped for the test
    kit.stop_daemons()
    time.sleep(2)  # Give some time for the daemon to stop
    
    # Check status after stop
    status = kit.check_daemon_status()
    logger.info(f"Status after stop: {status.get('daemons', {}).get('lotus', {})}")
    
    # Manually start the daemon
    logger.info("Manually starting Lotus daemon...")
    start_result = kit._ensure_daemon_running("lotus")
    logger.info(f"Start result: {start_result}")
    
    # Check status after manual start
    time.sleep(2)  # Give some time for the daemon to start
    status = kit.check_daemon_status()
    logger.info(f"Status after manual start: {status.get('daemons', {}).get('lotus', {})}")
    
    # Stop the daemon
    logger.info("Stopping all daemons...")
    stop_result = kit.stop_daemons()
    logger.info(f"Stop result: {stop_result}")
    
    # Check final status
    time.sleep(2)  # Give some time for the daemon to stop
    status = kit.check_daemon_status()
    logger.info(f"Final status: {status.get('daemons', {}).get('lotus', {})}")
    
    logger.info("Test completed successfully")

def test_auto_start_behavior():
    """Test role-based auto-start behavior."""
    logger.info("Testing role-based auto-start behavior")
    
    # Ensure daemon is stopped first
    kit = ipfs_kit(metadata={"auto_start_lotus_daemon": False})
    kit.stop_daemons()
    time.sleep(2)
    
    # Test master role (auto-start default: True)
    logger.info("Initializing with master role...")
    master_kit = ipfs_kit(role="master")
    
    # Check if daemon started automatically
    time.sleep(2)
    status = master_kit.check_daemon_status()
    logger.info(f"Master role daemon status: {status.get('daemons', {}).get('lotus', {})}")
    
    # Stop daemon
    master_kit.stop_daemons()
    time.sleep(2)
    
    # Test worker role (auto-start default: False)
    logger.info("Initializing with worker role...")
    worker_kit = ipfs_kit(role="worker")
    
    # Check if daemon remained stopped
    time.sleep(2)
    status = worker_kit.check_daemon_status()
    logger.info(f"Worker role daemon status: {status.get('daemons', {}).get('lotus', {})}")
    
    # Cleanup
    worker_kit.stop_daemons()
    logger.info("Auto-start test completed")

if __name__ == "__main__":
    logger.info("Starting Lotus daemon management tests")
    
    try:
        test_lotus_daemon_management()
        test_auto_start_behavior()
        logger.info("All tests completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
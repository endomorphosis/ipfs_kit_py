#!/usr/bin/env python3
"""
Verification script for Lotus snapshot integration.

This script tests the snapshot functionality in Lotus client and daemon
implementations, verifying that the snapshot integration works properly.
"""

import os
import sys
import time
import logging
import argparse
from ipfs_kit_py.lotus_kit import lotus_kit
from ipfs_kit_py.lotus_daemon import lotus_daemon

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_direct_snapshot_import(snapshot_url=None, network="calibnet"):
    """Test direct snapshot import using lotus_daemon."""
    logger.info(f"Testing direct snapshot import for network: {network}")
    
    # Initialize lotus daemon with network settings
    daemon = lotus_daemon(
        metadata={
            "network": network
        }
    )
    
    # Start with a clean slate
    logger.info("Stopping any existing daemon...")
    daemon.daemon_stop(force=True)
    
    # Import snapshot - providing URL or using default for the network
    logger.info(f"Attempting to download and import snapshot from: {snapshot_url or 'default URL'}")
    result = daemon.download_and_import_snapshot(
        snapshot_url=snapshot_url,
        network=network,
        use_curl=False,
        verify_checksum=True
    )
    
    # Check result
    if result.get("success", False):
        logger.info("✅ Snapshot import successful!")
        logger.info(f"Snapshot info: {result.get('snapshot_path')} ({result.get('snapshot_size_formatted', 'unknown size')})")
    else:
        logger.error(f"❌ Snapshot import failed: {result.get('error', 'Unknown error')}")
        if "snapshot_error_details" in result:
            logger.error(f"Error details: {result['snapshot_error_details']}")
    
    return result

def test_integrated_startup(snapshot_url=None, network="calibnet"):
    """Test integrated snapshot import during lotus_kit startup."""
    logger.info(f"Testing integrated snapshot import during startup for network: {network}")
    
    # Stop any existing daemon
    daemon = lotus_daemon()
    daemon.daemon_stop(force=True)
    
    # Initialize lotus kit with snapshot configuration
    lotus = lotus_kit(
        metadata={
            "use_snapshot": True,
            "snapshot_url": snapshot_url,
            "network": network,
            "auto_start_daemon": False,  # We'll start it manually to see the results
            "request_timeout": 120,  # Increase timeout for snapshot operations
        }
    )
    
    # Start the daemon with snapshot
    logger.info("Starting daemon with snapshot...")
    result = lotus.daemon_start()
    
    # Check result
    if result.get("success", False):
        logger.info("✅ Daemon started successfully with snapshot!")
        if result.get("snapshot_imported", False):
            logger.info(f"Snapshot info: {result.get('snapshot_info', {}).get('path', 'unknown')}")
        else:
            logger.warning("Daemon started, but snapshot import status is unclear")
    else:
        logger.error(f"❌ Daemon start failed: {result.get('error', 'Unknown error')}")
    
    # Get sync status
    time.sleep(5)  # Give the daemon a moment to start syncing
    sync_status = lotus.sync_status()
    logger.info(f"Current sync status: {sync_status}")
    
    # Always clean up
    logger.info("Stopping daemon...")
    lotus.daemon_stop()
    
    return result

def test_auto_start_with_snapshot(snapshot_url=None, network="calibnet"):
    """Test automatic daemon startup with snapshot during lotus_kit initialization."""
    logger.info(f"Testing auto-start with snapshot for network: {network}")
    
    # Stop any existing daemon
    daemon = lotus_daemon()
    daemon.daemon_stop(force=True)
    
    # Initialize lotus kit with auto-start and snapshot configuration
    logger.info("Initializing lotus_kit with auto-start and snapshot configuration...")
    lotus = lotus_kit(
        metadata={
            "use_snapshot": True,
            "snapshot_url": snapshot_url,
            "network": network,
            "auto_start_daemon": True,  # Enable auto-start
            "request_timeout": 120,  # Increase timeout for snapshot operations
        }
    )
    
    # Check daemon status
    logger.info("Checking daemon status...")
    status_result = lotus.daemon_status()
    
    # Log result
    if status_result.get("process_running", False):
        logger.info(f"✅ Daemon auto-started successfully (PID: {status_result.get('pid')})")
    else:
        logger.error("❌ Daemon auto-start failed or status check failed")
        logger.error(f"Status result: {status_result}")
    
    # Check API connectivity
    try:
        logger.info("Testing API connectivity...")
        version_result = lotus.lotus_version()
        logger.info(f"Version info: {version_result}")
        if version_result.get("success", False):
            logger.info("✅ API connection successful!")
        else:
            logger.error("❌ API connection failed")
    except Exception as e:
        logger.error(f"❌ Error checking API: {str(e)}")
    
    # Always clean up
    logger.info("Stopping daemon...")
    lotus.daemon_stop()
    
    return status_result

def main():
    parser = argparse.ArgumentParser(description="Verify Lotus snapshot integration")
    parser.add_argument("--snapshot-url", dest="snapshot_url", default=None,
                        help="URL to download chain snapshot from")
    parser.add_argument("--network", dest="network", default="calibnet",
                        help="Network to connect to (mainnet, calibnet, butterflynet)")
    parser.add_argument("--test", dest="test", default="all",
                        choices=["direct", "integrated", "auto", "all"],
                        help="Which test to run (direct, integrated, auto, all)")
    
    args = parser.parse_args()
    
    logger.info("=== Lotus Snapshot Integration Verification ===")
    logger.info(f"Network: {args.network}")
    logger.info(f"Snapshot URL: {args.snapshot_url or 'default'}")
    logger.info(f"Test type: {args.test}")
    logger.info("="*50)
    
    results = {}
    
    # Run selected test(s)
    if args.test in ["direct", "all"]:
        logger.info("\n=== Direct Snapshot Import Test ===")
        results["direct"] = test_direct_snapshot_import(args.snapshot_url, args.network)
    
    if args.test in ["integrated", "all"]:
        logger.info("\n=== Integrated Startup Test ===")
        results["integrated"] = test_integrated_startup(args.snapshot_url, args.network)
    
    if args.test in ["auto", "all"]:
        logger.info("\n=== Auto-start with Snapshot Test ===")
        results["auto"] = test_auto_start_with_snapshot(args.snapshot_url, args.network)
    
    # Summarize results
    logger.info("\n=== Verification Summary ===")
    all_successful = True
    
    for test_name, result in results.items():
        success = result.get("success", False)
        if not success:
            all_successful = False
            
        status = "✅ Passed" if success else "❌ Failed"
        logger.info(f"{test_name.capitalize()} test: {status}")
        
        if not success:
            logger.info(f"  Error: {result.get('error', 'Unknown error')}")
    
    # Final result
    logger.info("\n=== Overall Result ===")
    if all_successful:
        logger.info("✅ All tests passed - Snapshot functionality is working correctly!")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed - Snapshot functionality may not be working correctly")
        sys.exit(1)

if __name__ == "__main__":
    main()
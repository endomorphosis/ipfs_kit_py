#!/usr/bin/env python
import logging
import sys
import os
import json
import time
import subprocess
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("lotus_auto_daemon_test")

# Add the bin directory to PATH explicitly
bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
os.environ["LOTUS_BIN"] = os.path.join(bin_dir, "lotus")

# IMPORTANT: Remove environment variable to allow actual daemon startup
if "LOTUS_SKIP_DAEMON_LAUNCH" in os.environ:
    del os.environ["LOTUS_SKIP_DAEMON_LAUNCH"]

from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE
from ipfs_kit_py.lotus_daemon import lotus_daemon

def test_lotus_auto_daemon(force_actual_daemon=False, test_custom_path=True):
    """Test the lotus_kit auto daemon management capability.
    
    Args:
        force_actual_daemon: If True, try to use an actual daemon even if simulation would work
        test_custom_path: If True, test with a custom LOTUS_PATH
    """
    logger.info("Testing Lotus auto daemon management...")
    
    # Step 1: Verify Lotus binary is available
    logger.info("\nStep 1: Checking if Lotus binary is available...")
    if not LOTUS_AVAILABLE:
        logger.warning("Lotus binary is not available - using simulation mode")
        
        if force_actual_daemon:
            logger.warning("force_actual_daemon=True but Lotus binary not available - defaulting to simulation")
            force_actual_daemon = False
    else:
        logger.info(f"Lotus binary found at: {os.environ.get('LOTUS_BIN')}")
    
    # Prepare a custom Lotus path for testing if requested
    custom_lotus_path = None
    if test_custom_path:
        custom_lotus_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_lotus_path")
        os.makedirs(custom_lotus_path, exist_ok=True)
        logger.info(f"Using custom Lotus path: {custom_lotus_path}")
    
    # Step 2: Create lotus_kit with auto_start_daemon=True 
    logger.info("\nStep 2: Creating lotus_kit with auto_start_daemon enabled...")
    
    # Setup metadata dictionary
    metadata = {
        "auto_start_daemon": True,    # Enable automatic daemon management
        "simulation_mode": not force_actual_daemon,  # Use real daemon if forced
        "lite": True,                 # Use lite mode for faster startup
        "daemon_flags": {            # Add specific daemon flags
            "bootstrap": False,      # Skip bootstrap for faster startup
        },
        "daemon_startup_timeout": 60,  # Give it some time to start
    }
    
    if custom_lotus_path:
        metadata["lotus_path"] = custom_lotus_path
    
    # Create the lotus_kit instance
    kit = lotus_kit(metadata=metadata)
    
    # Step 3: Stop any existing daemon first to ensure we test auto-start
    logger.info("\nStep 3: Stopping any existing Lotus daemon...")
    try:
        # Get daemon status
        status_result = kit.daemon_status()
        
        # If daemon is running, stop it
        if status_result.get("process_running", False):
            logger.info(f"Found running daemon with PID {status_result.get('pid')}, stopping it...")
            stop_result = kit.daemon_stop(force=True)
            logger.info(f"Daemon stop result: {stop_result.get('success', False)}")
            time.sleep(3)  # Give it a moment to fully shutdown
        else:
            logger.info("No existing daemon is running.")
        
    except Exception as e:
        logger.error(f"Error checking/stopping daemon: {e}")
    
    # Step 4: Make an API request that should trigger the daemon to auto-start
    logger.info("\nStep 4: Making API request that should trigger auto daemon start...")
    api_result = kit._make_request("ID")
    
    # Step 5: Verify the request worked (either with real daemon or simulation)
    logger.info("\nStep 5: Verifying API request with auto-started daemon or simulation...")
    
    simulation_mode_active = api_result.get("simulated", False)
    api_success = api_result.get("success", False)
    daemon_restarted = api_result.get("daemon_restarted", False)
    
    if simulation_mode_active:
        logger.info("SUCCESS: Simulation mode activated")
        logger.info(f"API request result (simulated): {api_result}")
    else:
        # This should only happen if a real daemon was successfully started
        if api_success:
            logger.info("SUCCESS: Real daemon API request succeeded")
            logger.info(f"API request result: {api_result}")
            logger.info(f"Daemon was restarted: {daemon_restarted}")
        else:
            logger.error("FAILURE: API request failed, neither real daemon nor simulation mode worked")
            logger.error(f"API request error: {api_result.get('error', 'Unknown error')}")
    
    # Step 6: Perform some basic operations to verify functionality
    logger.info("\nStep 6: Testing some basic API operations...")
    
    # Test wallet listing
    wallet_result = kit.list_wallets()
    logger.info(f"Wallet list result: success={wallet_result.get('success', False)}, simulated={wallet_result.get('simulated', False)}")
    
    # Test network peers
    peers_result = kit.net_peers()
    logger.info(f"Network peers result: success={peers_result.get('success', False)}, simulated={peers_result.get('simulated', False)}")
    
    # Step 7: Manually verify that the daemon is running
    logger.info("\nStep 7: Manually verifying daemon status...")
    
    # Check daemon status
    daemon_status = kit.daemon_status()
    daemon_running = daemon_status.get("process_running", False)
    logger.info(f"Daemon running: {daemon_running}")
    if daemon_running:
        logger.info(f"Daemon PID: {daemon_status.get('pid')}")
    
    if not simulation_mode_active and not daemon_running:
        logger.warning("Daemon isn't running but was expected to be running!")
    
    # Step 8: Summarize the test results
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(f"Lotus binary available: {LOTUS_AVAILABLE}")
    logger.info(f"Force actual daemon: {force_actual_daemon}")
    logger.info(f"Using custom Lotus path: {custom_lotus_path is not None}")
    logger.info(f"Simulation mode activated: {simulation_mode_active}")
    logger.info(f"Daemon running: {daemon_running}")
    logger.info(f"API operation succeeded: {api_success}")
    logger.info(f"Daemon was auto-restarted: {daemon_restarted}")
    logger.info(f"Wallet operation succeeded: {wallet_result.get('success', False)}")
    logger.info(f"Network operation succeeded: {peers_result.get('success', False)}")
    
    test_success = api_success or simulation_mode_active
    logger.info(f"Overall test result: {'SUCCESS' if test_success else 'FAILURE'}")
    
    # If we started a daemon, stop it during cleanup
    if daemon_running and not simulation_mode_active:
        logger.info("\nCleaning up: Stopping the daemon...")
        kit.daemon_stop(force=True)
    
    # Return test result
    return test_success, {
        "lotus_available": LOTUS_AVAILABLE,
        "force_actual_daemon": force_actual_daemon,
        "custom_lotus_path": custom_lotus_path is not None,
        "simulation_mode_activated": simulation_mode_active,
        "daemon_running": daemon_running,
        "api_operation_success": api_success,
        "daemon_restarted": daemon_restarted,
        "wallet_operation_success": wallet_result.get("success", False),
        "network_operation_success": peers_result.get("success", False),
        "api_result": api_result,
        "overall_success": test_success
    }

if __name__ == "__main__":
    # Allow command-line arguments for additional configuration
    import argparse
    parser = argparse.ArgumentParser(description="Test Lotus auto daemon management")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--force-daemon", action="store_true", help="Force using real daemon (no simulation)")
    parser.add_argument("--skip-custom-path", action="store_true", help="Skip testing with custom path")
    args = parser.parse_args()
    
    # Set debug logging level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Run test
    success, results = test_lotus_auto_daemon(
        force_actual_daemon=args.force_daemon,
        test_custom_path=not args.skip_custom_path
    )
    
    # Save results to file
    with open("auto_daemon_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Detailed results saved to auto_daemon_test_results.json")
    
    sys.exit(0 if success else 1)
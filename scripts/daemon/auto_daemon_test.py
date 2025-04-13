#!/usr/bin/env python3
"""
Test script to verify automatic daemon management in the Lotus client.

This script tests the automatic startup, management, and fallback to simulation mode
of the Lotus daemon in the lotus_daemon.py implementation.
"""

import json
import logging
import os
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("auto_daemon_test")

# Import Lotus components
from ipfs_kit_py.lotus_kit import lotus_kit
from ipfs_kit_py.lotus_daemon import lotus_daemon

def test_lotus_auto_daemon():
    """Test that Lotus kit can automatically handle daemon failures."""
    logger.info("Testing Lotus kit with auto daemon management")
    
    # Get the path to the bin directory with the lotus binary
    bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    if not os.path.exists(os.path.join(bin_path, "lotus")):
        logger.info(f"Lotus binary not found in {bin_path}, using system binary if available")
    else:
        logger.info(f"Found Lotus binary in {bin_path}")
        # Add bin to PATH
        os.environ["PATH"] = f"{bin_path}:{os.environ.get('PATH', '')}"
    
    # Create lotus_kit with auto_start_daemon but allowing simulation mode fallback
    metadata = {
        "auto_start_daemon": True,     # Enable automatic daemon management
        "simulation_mode": None,       # Allow fallback to simulation mode
        "daemon_startup_timeout": 30,  # Give enough time for startup
        "binary_path": bin_path if os.path.exists(os.path.join(bin_path, "lotus")) else None,
        "lotus_binary": os.path.join(bin_path, "lotus") if os.path.exists(os.path.join(bin_path, "lotus")) else None,
        "remove_stale_lock": True,     # Remove stale lock files if found
        "lite": True,                  # Use lite mode
        "daemon_flags": {
            # The network flag is now handled automatically in lotus_daemon.py
            # based on version detection
        }
    }
    
    # Use a custom lotus path for testing
    test_lotus_path = os.path.expanduser("~/test_lotus")
    
    # Clean up the test lotus path if it exists
    if os.path.exists(test_lotus_path):
        import shutil
        try:
            shutil.rmtree(test_lotus_path)
            logger.info(f"Cleaned up existing test directory: {test_lotus_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up test directory: {e}")
    
    # Add lotus path to metadata
    metadata["lotus_path"] = test_lotus_path
    
    results = {
        "timestamp": time.time(),
        "tests": {}
    }
    
    # Step 1: Test the lotus_daemon directly
    logger.info("Testing lotus_daemon directly...")
    try:
        daemon = lotus_daemon(metadata=metadata)
        
        # Test daemon initialization
        daemon_init_result = {
            "success": True,
            "time": time.time()
        }
        
        if os.path.exists(test_lotus_path):
            daemon_init_result["lotus_path_created"] = True
        
        results["tests"]["daemon_init"] = daemon_init_result
        
        # Test daemon start
        logger.info("Starting daemon...")
        daemon_start_result = daemon.daemon_start()
        
        results["tests"]["daemon_start"] = {
            "success": daemon_start_result.get("success", False),
            "status": daemon_start_result.get("status", "unknown"),
            "process_running": daemon_start_result.get("pid") is not None,
            "simulation_mode": "simulation" in daemon_start_result.get("status", ""),
            "result": daemon_start_result,
            "time": time.time()
        }
        
        # Test daemon status
        logger.info("Checking daemon status...")
        daemon_status_result = daemon.daemon_status()
        
        results["tests"]["daemon_status"] = {
            "success": daemon_status_result.get("success", False),
            "process_running": daemon_status_result.get("process_running", False),
            "result": daemon_status_result,
            "time": time.time()
        }
        
        # Test daemon stop
        logger.info("Stopping daemon...")
        daemon_stop_result = daemon.daemon_stop()
        
        results["tests"]["daemon_stop"] = {
            "success": daemon_stop_result.get("success", False),
            "status": daemon_stop_result.get("status", "unknown"),
            "result": daemon_stop_result,
            "time": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error in daemon tests: {e}")
        results["tests"]["daemon_error"] = {
            "success": False,
            "error": str(e),
            "time": time.time()
        }
    
    # Step 2: Test the lotus_kit with the improved daemon management
    logger.info("Testing lotus_kit with auto daemon management...")
    
    try:
        # Create a new kit instance
        kit = lotus_kit(metadata=metadata)
        results["tests"]["create_kit"] = {
            "success": True,
            "time": time.time()
        }
        
        # Check if daemon auto-starts or falls back to simulation
        logger.info("Testing check_connection which should trigger auto-start")
        connection_result = kit.check_connection()
        
        results["tests"]["check_connection"] = {
            "success": connection_result.get("success", False),
            "simulated": connection_result.get("simulated", False),
            "api_version": connection_result.get("api_version", "unknown"),
            "result": connection_result,
            "time": time.time()
        }
        
        # Check if lotus daemon is correctly detected
        logger.info("Testing daemon_status")
        status_result = kit.daemon_status()
        
        results["tests"]["kit_daemon_status"] = {
            "success": status_result.get("success", False),
            "simulated": status_result.get("simulated", False),
            "process_running": status_result.get("process_running", False),
            "result": status_result,
            "time": time.time()
        }
        
        # Try some basic operations
        logger.info("Testing lotus_id")
        id_result = kit.lotus_id()
        
        results["tests"]["lotus_id"] = {
            "success": id_result.get("success", False),
            "simulated": id_result.get("simulated", False),
            "result": id_result,
            "time": time.time()
        }
        
        logger.info("Testing lotus_net_peers")
        peers_result = kit.lotus_net_peers()
        
        results["tests"]["lotus_net_peers"] = {
            "success": peers_result.get("success", False),
            "simulated": peers_result.get("simulated", False),
            "result": peers_result,
            "time": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error in kit tests: {e}")
        results["tests"]["kit_error"] = {
            "success": False,
            "error": str(e),
            "time": time.time()
        }
    
    # Determine overall success - consider successful if all tests pass or fail with simulation mode
    successful_tests = [test.get("success", False) for test in results["tests"].values()]
    simulation_mode_tests = [test.get("simulated", False) for test in results["tests"].values() 
                             if "simulated" in test]
    
    overall_success = False
    
    # Success if either:
    # 1. All tests passed, or
    # 2. Some tests passed in simulation mode (indicating proper fallback)
    if all(successful_tests):
        overall_success = True
    elif any(simulation_mode_tests) and any(successful_tests):
        # Some tests worked in simulation mode
        overall_success = True
    
    # Add summary
    results["summary"] = {
        "success": overall_success,
        "simulation_mode": any(simulation_mode_tests),
        "real_daemon_started": results["tests"].get("daemon_status", {}).get("process_running", False),
        "test_duration": time.time() - results["timestamp"]
    }
    
    return overall_success, results

if __name__ == "__main__":
    logger.info("Starting auto daemon test")
    
    # Run the test
    success, results = test_lotus_auto_daemon()
    
    # Save results
    result_file = "auto_daemon_test_results.json"
    with open(result_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test {'succeeded' if success else 'failed'}")
    logger.info(f"Results saved to {result_file}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

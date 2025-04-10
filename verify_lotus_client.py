#!/usr/bin/env python
"""
Comprehensive verification for the Lotus client and daemon management.

This script thoroughly tests that the Lotus client works correctly,
both with a real daemon when possible and with simulation mode as fallback.
It verifies the automatic daemon management functionality.
"""
import logging
import sys
import os
import json
import time
import subprocess
import shutil
import argparse
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("lotus_verification")

# Add the bin directory to PATH explicitly
bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
os.environ["LOTUS_BIN"] = os.path.join(bin_dir, "lotus")

# Import after setting environment variables
from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE
from ipfs_kit_py.lotus_daemon import lotus_daemon

def check_binary():
    """Check if Lotus binary is available and functional."""
    logger.info("Checking Lotus binary availability...")
    
    # First check the environment variable
    lotus_bin = os.environ.get("LOTUS_BIN")
    if lotus_bin and os.path.exists(lotus_bin):
        logger.info(f"Found Lotus binary at LOTUS_BIN path: {lotus_bin}")
        binary_exists = True
    else:
        # Check in the PATH
        try:
            which_result = subprocess.run(["which", "lotus"], capture_output=True, text=True)
            if which_result.returncode == 0 and which_result.stdout.strip():
                lotus_bin = which_result.stdout.strip()
                logger.info(f"Found Lotus binary in PATH: {lotus_bin}")
                binary_exists = True
            else:
                logger.warning("Lotus binary not found in PATH")
                binary_exists = False
        except Exception as e:
            logger.error(f"Error checking Lotus binary: {e}")
            binary_exists = False
    
    # Check if the binary actually works by running a simple command
    if binary_exists:
        try:
            version_cmd = [lotus_bin, "--version"]
            version_result = subprocess.run(version_cmd, capture_output=True, text=True)
            if version_result.returncode == 0:
                logger.info(f"Lotus binary works: {version_result.stdout.strip()}")
                return True, lotus_bin, version_result.stdout.strip()
            else:
                logger.warning(f"Lotus binary exists but returned error: {version_result.stderr.strip()}")
                return False, lotus_bin, None
        except Exception as e:
            logger.error(f"Error running Lotus binary: {e}")
            return False, lotus_bin, None
    
    return False, None, None

def check_daemon_process():
    """Check if the Lotus daemon process is running."""
    logger.info("Checking if Lotus daemon process is running...")
    try:
        if os.name == 'posix':  # Linux/macOS
            ps_cmd = ["pgrep", "-f", "lotus daemon"]
            ps_result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True)
            
            if ps_result.returncode == 0 and ps_result.stdout.strip():
                pids = ps_result.stdout.strip().split('\n')
                logger.info(f"Found Lotus daemon processes: {', '.join(pids)}")
                return True, pids
            else:
                logger.info("No Lotus daemon process found")
                return False, []
        elif os.name == 'nt':  # Windows
            # Using tasklist on Windows
            ps_cmd = ["tasklist", "/FI", "IMAGENAME eq lotus.exe", "/FO", "CSV"]
            ps_result = subprocess.run(ps_cmd, capture_output=True, text=True)
            
            if ps_result.returncode == 0 and "lotus.exe" in ps_result.stdout:
                logger.info("Found Lotus daemon process on Windows")
                return True, ["windows_pid"]  # Windows doesn't return PID in same format
            else:
                logger.info("No Lotus daemon process found on Windows")
                return False, []
        else:
            logger.warning(f"Unsupported platform: {os.name}")
            return False, []
    except Exception as e:
        logger.error(f"Error checking daemon process: {e}")
        return False, []

def test_with_real_daemon():
    """Test the lotus_kit with a real daemon."""
    logger.info("\n=== Testing with real daemon ===")
    
    # First, stop any existing daemon to start from clean state
    logger.info("Stopping any existing daemon...")
    daemon_mgr = lotus_daemon()
    daemon_mgr.daemon_stop(force=True)
    time.sleep(2)  # Give it time to stop completely
    
    # Create a lotus_kit instance with auto-start but no simulation mode
    logger.info("Creating lotus_kit with auto_start_daemon=True and simulation_mode=False")
    kit = lotus_kit(metadata={
        "auto_start_daemon": True,
        "simulation_mode": False,  # Try to use real daemon
        "lite": True,
        "daemon_flags": {
            "bootstrap": False,  # Skip bootstrap for faster startup
        }
    })
    
    # Make an API request that should trigger the daemon to auto-start
    logger.info("Making API request that should trigger auto daemon start...")
    api_result = kit._make_request("ID")
    
    # Check if daemon was started
    daemon_running, pids = check_daemon_process()
    
    results = {
        "daemon_auto_started": daemon_running,
        "daemon_pids": pids if daemon_running else [],
        "api_success": api_result.get("success", False),
        "api_result": api_result
    }
    
    if daemon_running and api_result.get("success", False):
        logger.info("SUCCESS: Real daemon was auto-started and API request succeeded")
    elif daemon_running and not api_result.get("success", False):
        logger.warning("PARTIAL SUCCESS: Daemon was auto-started but API request failed")
    elif not daemon_running and api_result.get("success", False):
        logger.warning("STRANGE STATE: Daemon not detected but API request succeeded")
    else:
        logger.warning("FAILURE: Real daemon was not auto-started and API request failed")
    
    # Stop the daemon if we started it
    if daemon_running:
        logger.info("Stopping daemon...")
        daemon_mgr.daemon_stop(force=True)
    
    return results

def test_with_simulation_mode():
    """Test the lotus_kit with simulation mode."""
    logger.info("\n=== Testing with simulation mode ===")
    
    # First, stop any existing daemon
    logger.info("Stopping any existing daemon...")
    daemon_mgr = lotus_daemon()
    daemon_mgr.daemon_stop(force=True)
    time.sleep(2)  # Give it time to stop completely
    
    # Set environment variable to force simulation mode
    os.environ["LOTUS_SKIP_DAEMON_LAUNCH"] = "1"
    
    # Create a lotus_kit instance with auto-start and simulation mode
    logger.info("Creating lotus_kit with auto_start_daemon=True and simulation_mode=True")
    kit = lotus_kit(metadata={
        "auto_start_daemon": True,
        "simulation_mode": True,  # Force simulation mode
    })
    
    # Make an API request
    logger.info("Making API request in simulation mode...")
    api_result = kit._make_request("ID")
    
    # Test wallet listing
    logger.info("Testing wallet listing in simulation mode...")
    wallet_result = kit.list_wallets()
    
    # Test network peers
    logger.info("Testing network peers in simulation mode...")
    peers_result = kit.net_peers()
    
    # Clean up environment variable
    del os.environ["LOTUS_SKIP_DAEMON_LAUNCH"]
    
    results = {
        "simulation_mode_active": api_result.get("simulated", False),
        "api_success": api_result.get("success", False),
        "wallet_success": wallet_result.get("success", False),
        "peers_success": peers_result.get("success", False),
        "api_result": api_result,
        "wallet_result": wallet_result,
        "peers_result": peers_result
    }
    
    if api_result.get("simulated", False) and api_result.get("success", False):
        logger.info("SUCCESS: Simulation mode activated and API request succeeded")
    else:
        logger.warning("FAILURE: Simulation mode failed or API request failed")
    
    return results

def test_auto_daemon_with_fallback():
    """Test the automatic daemon management with fallback to simulation mode."""
    logger.info("\n=== Testing auto daemon with fallback ===")
    
    # First, stop any existing daemon
    logger.info("Stopping any existing daemon...")
    daemon_mgr = lotus_daemon()
    daemon_mgr.daemon_stop(force=True)
    time.sleep(2)  # Give it time to stop completely
    
    # Create a lotus_kit instance with both auto-start and simulation mode
    logger.info("Creating lotus_kit with auto_start_daemon=True and simulation_mode=True")
    kit = lotus_kit(metadata={
        "auto_start_daemon": True,
        "simulation_mode": True,  # Enable both for fallback
        "lite": True,
        "daemon_flags": {
            "bootstrap": False,
        }
    })
    
    # Make an API request that should trigger the daemon to auto-start
    # or fallback to simulation mode if the daemon can't be started
    logger.info("Making API request that should trigger auto daemon or fallback...")
    api_result = kit._make_request("ID")
    
    # Check if daemon was started or simulation mode was used
    daemon_running, pids = check_daemon_process()
    simulation_active = api_result.get("simulated", False)
    
    # Test another operation to verify functionality
    logger.info("Testing another operation to verify functionality...")
    chain_head_result = kit.get_chain_head()
    
    results = {
        "daemon_running": daemon_running,
        "daemon_pids": pids if daemon_running else [],
        "simulation_active": simulation_active,
        "api_success": api_result.get("success", False),
        "chain_head_success": chain_head_result.get("success", False),
        "api_result": api_result,
        "chain_head_result": chain_head_result
    }
    
    if daemon_running and api_result.get("success", False):
        logger.info("SUCCESS: Real daemon was auto-started and API request succeeded")
    elif simulation_active and api_result.get("success", False):
        logger.info("SUCCESS: Simulation mode activated as fallback and API request succeeded")
    else:
        logger.warning("FAILURE: Neither real daemon nor simulation mode succeeded")
    
    # Stop the daemon if we started it
    if daemon_running:
        logger.info("Stopping daemon...")
        daemon_mgr.daemon_stop(force=True)
    
    return results

def test_dummy_file_operations():
    """Test file operations (import/retrieve) with simulation mode."""
    logger.info("\n=== Testing file operations with simulation mode ===")
    
    # Ensure simulation mode
    os.environ["LOTUS_SKIP_DAEMON_LAUNCH"] = "1"
    
    # Create a lotus_kit instance with simulation mode
    logger.info("Creating lotus_kit with simulation_mode=True")
    kit = lotus_kit(metadata={
        "auto_start_daemon": True,
        "simulation_mode": True,  # Force simulation mode
    })
    
    # Create a test file
    test_file_path = "/tmp/lotus_test_file.txt"
    with open(test_file_path, "w") as f:
        f.write(f"Test content generated at {time.time()}")
    
    # Import the file
    logger.info(f"Importing test file: {test_file_path}")
    import_result = kit.client_import(test_file_path)
    
    # Get the imported file info
    logger.info("Listing imports...")
    imports_result = kit.client_list_imports()
    
    # Try to retrieve the file
    retrieve_result = None
    if import_result.get("success", False):
        imported_root = import_result.get("result", {}).get("Root", {}).get("/")
        if imported_root:
            logger.info(f"Retrieving imported file with CID: {imported_root}")
            retrieve_path = "/tmp/lotus_retrieved_file.txt"
            retrieve_result = kit.client_retrieve(imported_root, retrieve_path)
    
    # Clean up environment variable
    del os.environ["LOTUS_SKIP_DAEMON_LAUNCH"]
    
    results = {
        "file_operations_simulated": True,
        "import_success": import_result.get("success", False),
        "imports_list_success": imports_result.get("success", False),
        "retrieve_success": retrieve_result.get("success", False) if retrieve_result else False,
        "import_result": import_result,
        "imports_result": imports_result,
        "retrieve_result": retrieve_result
    }
    
    if import_result.get("success", False) and imports_result.get("success", False):
        logger.info("SUCCESS: File import and listing operations succeeded")
        if retrieve_result and retrieve_result.get("success", False):
            logger.info("SUCCESS: File retrieve operation succeeded")
        else:
            logger.warning("PARTIAL SUCCESS: File retrieve operation failed")
    else:
        logger.warning("FAILURE: File operations failed")
    
    return results

def run_all_tests():
    """Run all lotus_kit verification tests."""
    results = {
        "timestamp": time.time(),
        "test_id": str(uuid.uuid4()),
    }
    
    # Check basic binary and daemon status
    binary_works, binary_path, binary_version = check_binary()
    daemon_running, daemon_pids = check_daemon_process()
    
    results["environment"] = {
        "binary_works": binary_works,
        "binary_path": binary_path,
        "binary_version": binary_version,
        "daemon_running_before_tests": daemon_running,
        "daemon_pids_before_tests": daemon_pids,
        "lotus_available_constant": LOTUS_AVAILABLE,
        "lotus_bin_env": os.environ.get("LOTUS_BIN"),
        "path_env": os.environ.get("PATH")
    }
    
    # Run real daemon test if binary works
    if binary_works:
        results["real_daemon_test"] = test_with_real_daemon()
    else:
        logger.warning("Skipping real daemon test since binary doesn't work")
        results["real_daemon_test"] = {"skipped": True}
    
    # Run simulation mode test (should work regardless of binary)
    results["simulation_mode_test"] = test_with_simulation_mode()
    
    # Run fallback test (should use simulation mode if binary doesn't work)
    results["fallback_test"] = test_auto_daemon_with_fallback()
    
    # Run file operations test using simulation mode
    results["file_operations_test"] = test_dummy_file_operations()
    
    # Final status check
    daemon_running_after, daemon_pids_after = check_daemon_process()
    results["environment"]["daemon_running_after_tests"] = daemon_running_after
    results["environment"]["daemon_pids_after_tests"] = daemon_pids_after
    
    # If daemon is still running, stop it
    if daemon_running_after:
        logger.info("Stopping any remaining daemon processes...")
        daemon_mgr = lotus_daemon()
        daemon_mgr.daemon_stop(force=True)
    
    # Determine overall success
    simulation_success = results["simulation_mode_test"]["api_success"]
    fallback_success = results["fallback_test"]["api_success"]
    file_ops_success = results["file_operations_test"]["import_success"]
    
    if binary_works:
        real_daemon_success = results["real_daemon_test"]["api_success"]
        results["overall_success"] = (
            real_daemon_success or simulation_success or fallback_success
        ) and file_ops_success
    else:
        results["overall_success"] = (
            simulation_success or fallback_success
        ) and file_ops_success
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Lotus client and daemon management")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--output", type=str, default="lotus_verification_results.json",
                       help="Output file for test results")
    args = parser.parse_args()
    
    # Set debug logging level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting comprehensive Lotus client verification")
    
    # Run all tests
    try:
        results = run_all_tests()
        
        # Save results to file
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"All tests completed. Results saved to {args.output}")
        
        # Log summary
        logger.info("\n=== VERIFICATION SUMMARY ===")
        logger.info(f"Lotus binary works: {results['environment']['binary_works']}")
        logger.info(f"Real daemon test: {'Skipped' if 'skipped' in results['real_daemon_test'] else 'Passed' if results['real_daemon_test'].get('api_success', False) else 'Failed'}")
        logger.info(f"Simulation mode test: {'Passed' if results['simulation_mode_test']['api_success'] else 'Failed'}")
        logger.info(f"Fallback test: {'Passed' if results['fallback_test']['api_success'] else 'Failed'}")
        logger.info(f"File operations test: {'Passed' if results['file_operations_test']['import_success'] else 'Failed'}")
        logger.info(f"Overall success: {'PASSED' if results['overall_success'] else 'FAILED'}")
        
        # Exit with appropriate status
        sys.exit(0 if results["overall_success"] else 1)
        
    except Exception as e:
        logger.exception(f"Error during verification tests: {e}")
        sys.exit(1)
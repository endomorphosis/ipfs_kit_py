#!/usr/bin/env python3
"""
Test script for MCP server lock file handling.

This script verifies that the MCP server properly handles IPFS daemon lock files,
particularly checking that our improvements to daemon_start() correctly handle:
1. Detecting existing lock files
2. Identifying and removing stale lock files
3. Handling active lock files from running processes
4. Restarting failed daemons due to lock issues

Usage:
    python test_mcp_lock_handling.py [--base-url URL] [--port PORT]

By default it starts a new MCP server instance for testing.
"""

import os
import sys
import time
import json
import logging
import tempfile
import argparse
import subprocess
import requests
from pprint import pprint

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Add compatibility methods to ipfs_kit first
from mcp_compatibility import add_compatibility_methods, patch_mcp_server
add_compatibility_methods()
patch_mcp_server()

# Import our modules
from ipfs_kit_py.ipfs import ipfs_py
from ipfs_kit_py import ipfs_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_lock_test")

def check_health(base_url):
    """Check the MCP server's health endpoint."""
    url = f"{base_url}/health"
    logger.info(f"Checking health at {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        logger.info("Health check successful")
        logger.info(f"IPFS daemon status: {'Running' if data.get('ipfs_daemon_running') else 'Not running'}")
        logger.info(f"Daemon monitor status: {'Running' if data.get('daemon_health_monitor_running') else 'Not running'}")
            
        return data
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return None

def get_daemon_status(base_url):
    """Get the status of all daemons from the MCP server."""
    url = f"{base_url}/daemon/status"
    logger.info(f"Getting daemon status from {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Daemon status: {json.dumps(data, indent=2)}")
        return data
        
    except Exception as e:
        logger.error(f"Failed to get daemon status: {e}")
        return None

def toggle_daemon(base_url, daemon_type, action):
    """Start or stop a daemon via the MCP server."""
    url = f"{base_url}/daemon/{action}/{daemon_type}"
    logger.info(f"{action.capitalize()}ing {daemon_type} daemon via {url}...")
    
    try:
        response = requests.post(url)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Daemon {action} result: {json.dumps(data, indent=2)}")
        return data
        
    except Exception as e:
        logger.error(f"Failed to {action} daemon: {e}")
        return None

def create_stale_lock_file(ipfs_path):
    """Create a stale lock file in the given IPFS repository."""
    repo_path = os.path.expanduser(ipfs_path)
    lock_path = os.path.join(repo_path, "repo.lock")
    
    logger.info(f"Creating stale lock file at {lock_path}")
    
    # Create the directory if it doesn't exist
    os.makedirs(repo_path, exist_ok=True)
    
    # Write a non-existent PID to the lock file
    with open(lock_path, 'w') as f:
        f.write("999999")
    
    return lock_path

def create_active_lock_file(ipfs_path):
    """Create a lock file with the current process PID."""
    repo_path = os.path.expanduser(ipfs_path)
    lock_path = os.path.join(repo_path, "repo.lock")
    
    # Create the directory if it doesn't exist
    os.makedirs(repo_path, exist_ok=True)
    
    # Get current process PID
    current_pid = os.getpid()
    logger.info(f"Creating active lock file at {lock_path} with current PID {current_pid}")
    
    # Write the current PID to the lock file
    with open(lock_path, 'w') as f:
        f.write(str(current_pid))
    
    return lock_path

def run_mcp_server(port=9999, debug=True, isolation=True):
    """Launch an MCP server instance for testing."""
    logger.info(f"Starting MCP server on port {port} (debug={debug}, isolation={isolation})...")
    
    # Use the example server script
    example_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "mcp_server_example.py")
    
    # Build arguments
    args = [sys.executable, example_path, "--port", str(port)]
    if debug:
        args.append("--debug")
    if isolation:
        args.append("--isolation")
    
    # Start server process
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    logger.info(f"Waiting up to 10 seconds for server to start...")
    start_time = time.time()
    server_ready = False
    
    while time.time() - start_time < 10:
        try:
            response = requests.get(f"http://localhost:{port}/api/v0/mcp/health", timeout=1)
            if response.status_code == 200:
                server_ready = True
                logger.info("MCP server is ready!")
                break
        except Exception:
            # Server not ready yet
            time.sleep(0.5)
    
    if not server_ready:
        logger.error("Failed to start MCP server within timeout period")
        process.terminate()
        stdout, stderr = process.communicate()
        if stdout:
            logger.error(f"Server stdout: {stdout}")
        if stderr:
            logger.error(f"Server stderr: {stderr}")
        return None
    
    return process

def get_ipfs_path_from_server(base_url):
    """Get the IPFS path configuration from the MCP server."""
    try:
        # Try to get debug information that might contain the IPFS path
        response = requests.get(f"{base_url}/debug")
        if response.status_code == 200:
            data = response.json()
            # Look for IPFS path in the configuration
            for component in data.get("components", []):
                if component.get("type") == "ipfs_kit":
                    metadata = component.get("metadata", {})
                    if "ipfs_path" in metadata:
                        return metadata["ipfs_path"]
        
        # If we can't get it from debug, try operations endpoint
        response = requests.get(f"{base_url}/operations")
        if response.status_code == 200:
            operations = response.json().get("operations", [])
            for op in operations:
                if "ipfs_path" in op.get("params", {}):
                    return op["params"]["ipfs_path"]
        
        # If all else fails, use a default isolated path for testing
        return os.path.join(tempfile.gettempdir(), "ipfs_mcp_test")
        
    except Exception as e:
        logger.error(f"Error getting IPFS path from server: {e}")
        # Use a default path for testing
        return os.path.join(tempfile.gettempdir(), "ipfs_mcp_test")

def test_mcp_lock_handling(base_url):
    """Test MCP server's handling of IPFS lock files."""
    tests_passed = True
    
    # Check health to make sure server is running
    health = check_health(base_url)
    if not health:
        logger.error("Server health check failed, cannot proceed with tests")
        return False
    
    # Get initial daemon status
    initial_status = get_daemon_status(base_url)
    if not initial_status:
        logger.error("Failed to get initial daemon status")
        return False
    
    # Get IPFS path from server for lock file testing
    ipfs_path = get_ipfs_path_from_server(base_url)
    logger.info(f"Using IPFS path: {ipfs_path}")
    
    # Test 1: Stop daemon if running
    logger.info("\n=== Test 1: Stop IPFS daemon if running ===")
    if initial_status.get("ipfs", {}).get("running", False):
        stop_result = toggle_daemon(base_url, "ipfs", "stop")
        if not stop_result or not stop_result.get("success"):
            logger.error("Failed to stop IPFS daemon")
            tests_passed = False
    
    # Test 2: Create stale lock file and verify daemon starts
    logger.info("\n=== Test 2: Test handling of stale lock file ===")
    lock_path = create_stale_lock_file(ipfs_path)
    logger.info(f"Created stale lock file at: {lock_path}")
    
    # Remember the modification time of the lock file
    original_lock_mtime = os.path.getmtime(lock_path) if os.path.exists(lock_path) else None
    logger.info(f"Original lock file mtime: {original_lock_mtime}")
    
    # Try to start the daemon with stale lock
    start_result = toggle_daemon(base_url, "ipfs", "start")
    
    # Check if start was successful
    if not start_result or not start_result.get("success"):
        logger.error("Failed to start daemon with stale lock file")
        tests_passed = False
    else:
        logger.info("Successfully started daemon with stale lock file")
        
        # Check if lock file exists and print more details
        lock_exists = os.path.exists(lock_path)
        current_lock_mtime = os.path.getmtime(lock_path) if lock_exists else None
        lock_was_recreated = lock_exists and original_lock_mtime != current_lock_mtime
        
        logger.info(f"Lock file still exists? {lock_exists}")
        logger.info(f"Current lock file mtime: {current_lock_mtime}")
        logger.info(f"Lock file was recreated? {lock_was_recreated}")
        
        if lock_exists and not lock_was_recreated:
            logger.error("Lock file exists but was not recreated - likely a stale lock was not removed")
            tests_passed = False
    
    # Get daemon status to verify it's running
    status_after_stale = get_daemon_status(base_url)
    if not status_after_stale or not status_after_stale.get("ipfs", {}).get("running", False):
        logger.error("Daemon not running after stale lock file test")
        tests_passed = False
    
    # Test 3: Stop daemon again
    logger.info("\n=== Test 3: Stop daemon for next test ===")
    stop_result = toggle_daemon(base_url, "ipfs", "stop")
    if not stop_result or not stop_result.get("success"):
        logger.error("Failed to stop IPFS daemon")
        tests_passed = False
    
    # Test 4: Create active lock file and try to start daemon
    logger.info("\n=== Test 4: Test handling of active lock file ===")
    active_lock_path = create_active_lock_file(ipfs_path)
    logger.info(f"Created active lock file at: {active_lock_path}")
    
    # Try to start the daemon with active lock
    start_result = toggle_daemon(base_url, "ipfs", "start")
    
    # For active lock, the server should detect this as "already running"
    if not start_result:
        logger.error("Failed to get response when starting with active lock")
        tests_passed = False
    elif not start_result.get("success"):
        logger.error("Server reported failure with active lock, expected success with already_running status")
        tests_passed = False
    elif start_result.get("status") != "already_running":
        logger.error(f"Expected status 'already_running', got '{start_result.get('status')}'")
        tests_passed = False
    else:
        logger.info("Successfully detected active lock file")
    
    # Clean up active lock file
    if os.path.exists(active_lock_path):
        try:
            os.remove(active_lock_path)
            logger.info(f"Removed active lock file: {active_lock_path}")
        except Exception as e:
            logger.error(f"Failed to remove active lock file: {e}")
    
    # Test 5: Test daemon monitor with lock file handling
    logger.info("\n=== Test 5: Test daemon health monitor with lock handling ===")
    
    # First, make sure daemon is not running
    stop_result = toggle_daemon(base_url, "ipfs", "stop")
    
    # Create a stale lock file
    stale_lock = create_stale_lock_file(ipfs_path)
    logger.info(f"Created stale lock file for monitor test: {stale_lock}")
    
    # Start the daemon monitor with a short interval
    monitor_url = f"{base_url}/daemon/monitor/start?check_interval=5"
    try:
        response = requests.post(monitor_url)
        response.raise_for_status()
        logger.info("Started daemon monitor with 5-second interval")
    except Exception as e:
        logger.error(f"Failed to start daemon monitor: {e}")
        tests_passed = False
    
    # Wait a bit for the monitor to check and start the daemon
    logger.info("Waiting 10 seconds for monitor to detect and handle the lock file...")
    time.sleep(10)
    
    # Check if daemon is running now
    status_after_monitor = get_daemon_status(base_url)
    if not status_after_monitor or not status_after_monitor.get("ipfs", {}).get("running", False):
        logger.error("Daemon not running after monitor check - lock handling in monitor may have failed")
        tests_passed = False
    else:
        logger.info("Daemon successfully started by monitor despite stale lock file!")
    
    # Stop the monitor
    try:
        response = requests.post(f"{base_url}/daemon/monitor/stop")
        response.raise_for_status()
        logger.info("Stopped daemon monitor")
    except Exception as e:
        logger.error(f"Failed to stop daemon monitor: {e}")
    
    # Final clean up - stop daemon
    toggle_daemon(base_url, "ipfs", "stop")
    
    return tests_passed

def main():
    """Main function to run the tests."""
    parser = argparse.ArgumentParser(description="Test MCP server lock file handling")
    parser.add_argument("--base-url", default="http://localhost:9999/api/v0/mcp",
                        help="Base URL for MCP server")
    parser.add_argument("--port", type=int, default=9999, 
                        help="Port to use if starting a new server")
    parser.add_argument("--no-server", action="store_true",
                        help="Don't start a server, just run tests against existing one")
    
    args = parser.parse_args()
    base_url = args.base_url
    
    # Start MCP server if needed
    server_process = None
    if not args.no_server:
        server_process = run_mcp_server(port=args.port)
        if not server_process:
            logger.error("Failed to start MCP server. Exiting.")
            return 1
        
        # Update base URL if we're using a custom port
        if args.port != 9999:
            base_url = f"http://localhost:{args.port}/api/v0/mcp"
    
    try:
        # Run the tests
        logger.info(f"Running lock handling tests against {base_url}")
        tests_passed = test_mcp_lock_handling(base_url)
        
        if tests_passed:
            logger.info("\n✅ All MCP lock handling tests PASSED!")
            return 0
        else:
            logger.error("\n❌ Some MCP lock handling tests FAILED!")
            return 1
            
    finally:
        # Clean up server process if we started one
        if server_process:
            logger.info("Stopping MCP server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Server didn't exit cleanly, forcing...")
                server_process.kill()

if __name__ == "__main__":
    sys.exit(main())
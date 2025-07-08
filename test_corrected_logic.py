#!/usr/bin/env python3
"""
Test the corrected daemon management logic.
"""
import subprocess
import time
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

def test_direct_ipfs():
    """Test if IPFS commands work directly."""
    try:
        result = subprocess.run(['ipfs', 'id'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"Direct IPFS test failed: {e}")
        return False

def test_ipfs_api_direct():
    """Test if IPFS API is accessible directly via HTTP."""
    try:
        import requests
        response = requests.get('http://localhost:5001/api/v0/id', timeout=3)
        return response.status_code == 200
    except Exception as e:
        logger.debug(f"Direct API test failed: {e}")
        return False

def find_existing_ipfs_processes():
    """Find existing IPFS daemon processes."""
    try:
        result = subprocess.run(['pgrep', '-f', 'ipfs daemon'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
    except Exception as e:
        logger.debug(f"Failed to find IPFS processes via pgrep: {e}")
    return []

def corrected_ensure_daemon_running():
    """Corrected daemon management logic."""
    logger.info("Ensuring IPFS daemon is running...")

    # Test multiple connection methods first
    connection_tests = [
        ("Direct IPFS", test_direct_ipfs),
        ("HTTP API", test_ipfs_api_direct),
    ]
    
    working_methods = []
    for test_name, test_func in connection_tests:
        try:
            if test_func():
                working_methods.append(test_name)
                logger.info(f"✓ {test_name} connection works")
            else:
                logger.debug(f"✗ {test_name} connection failed")
        except Exception as e:
            logger.debug(f"✗ {test_name} connection test error: {e}")
    
    # If any connection method works, we're good
    if working_methods:
        logger.info(f"✓ IPFS is accessible via: {', '.join(working_methods)}")
        return True
    
    # If no connection works, check for daemon processes
    existing_pids = find_existing_ipfs_processes()
    if existing_pids:
        logger.warning(f"Found IPFS daemon processes ({existing_pids}) but none are responsive")
        # In a real implementation, you might want to restart these
        return False
    
    # No working connection and no daemons - need to start one
    logger.info("No accessible IPFS daemon found. Would need to start a new one.")
    return False

def main():
    print("=== Testing Corrected Daemon Management ===")
    result = corrected_ensure_daemon_running()
    print(f"\nResult: {'✅ Success' if result else '❌ Failed'}")

if __name__ == "__main__":
    main()

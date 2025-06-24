#!/usr/bin/env python3
import requests
import json
import logging
import time
import traceback

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("daemon_status_direct_test")

# Server URL
base_url = "http://localhost:9999/api/v0"

def test_health():
    """Test the health endpoint."""
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            logger.info("Health check successful")
            logger.info(f"Response: {response.text}")
            return True
        else:
            logger.error(f"Health check failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        logger.error(traceback.format_exc())
        return False

def test_no_daemon_type():
    """Test daemon status without specifying a daemon type."""
    try:
        # Create request with empty daemon_type
        request_data = {"daemon_type": None}

        logger.info(f"Sending request with daemon_type=None to {base_url}/ipfs/daemon/status")
        response = requests.post(
            f"{base_url}/ipfs/daemon/status",
            json=request_data
        )

        logger.info(f"Status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")

        if response.status_code == 200:
            logger.info(f"Response: {response.text}")
            return True
        else:
            logger.error(f"Error: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in test_no_daemon_type: {e}")
        logger.error(traceback.format_exc())
        return False

def test_with_ipfs_daemon_type():
    """Test daemon status specifying the IPFS daemon type."""
    try:
        request_data = {"daemon_type": "ipfs"}

        logger.info(f"Sending request with daemon_type='ipfs' to {base_url}/ipfs/daemon/status")
        response = requests.post(
            f"{base_url}/ipfs/daemon/status",
            json=request_data
        )

        logger.info(f"Status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")

        if response.status_code == 200:
            logger.info(f"Response: {response.text}")
            return True
        else:
            logger.error(f"Error: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in test_with_ipfs_daemon_type: {e}")
        logger.error(traceback.format_exc())
        return False

def test_debug_output():
    """Test with debug info to examine the request handling."""
    try:
        # Create request with null daemon_type
        request_data = {"daemon_type": None}

        logger.info(f"Testing with null daemon_type")
        logger.info(f"Request data: {json.dumps(request_data)}")

        response = requests.post(
            f"{base_url}/ipfs/daemon/status",
            json=request_data,
            headers={"X-Debug": "true"}
        )

        logger.info(f"Status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            logger.info(f"Response data: {response.text}")
            return True
        else:
            logger.error(f"Error response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in test_debug_output: {e}")
        logger.error(traceback.format_exc())
        return False

def test_with_empty_object():
    """Test with an empty JSON object."""
    try:
        # Empty request data
        request_data = {}

        logger.info(f"Testing with empty request data")
        logger.info(f"Request data: {json.dumps(request_data)}")

        response = requests.post(
            f"{base_url}/ipfs/daemon/status",
            json=request_data
        )

        logger.info(f"Status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            logger.info(f"Response data: {response.text}")
            return True
        else:
            logger.error(f"Error response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in test_with_empty_object: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Run all tests."""
    logger.info("Starting direct daemon status tests...")

    # First check if server is running
    if not test_health():
        logger.error("Health check failed. Make sure the server is running.")
        return False

    # Run tests
    test_debug_output()
    test_with_empty_object()
    test_no_daemon_type()
    test_with_ipfs_daemon_type()

    return True

if __name__ == "__main__":
    main()

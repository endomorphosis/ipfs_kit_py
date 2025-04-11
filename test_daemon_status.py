#!/usr/bin/env python3
import requests
import json
import time
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_daemon_status")

# Test the daemon status endpoint with our fix
base_url = "http://localhost:9999/api/v0"  # Using port 9999 where we know server is running

def test_daemon_status():
    print("Testing daemon status endpoint...")
    
    # First check if the server is running with a simple health check
    try:
        health_response = requests.get(f"{base_url}/health")
        print(f"Health check status code: {health_response.status_code}")
        if health_response.status_code == 200:
            print(f"Health check response: {health_response.text}")
        else:
            print(f"Health check failed: {health_response.text}")
    except Exception as e:
        print(f"Error connecting to server: {str(e)}")
        print("Make sure the server is running on the correct port")
        return
    
    # Test with daemon_type=ipfs
    ipfs_request = {"daemon_type": "ipfs"}
    logger.debug(f"Sending request to {base_url}/ipfs/daemon/status with data: {ipfs_request}")
    try:
        ipfs_response = requests.post(f"{base_url}/ipfs/daemon/status", json=ipfs_request)
        print(f"Status code for IPFS daemon: {ipfs_response.status_code}")
        print(f"Response headers: {ipfs_response.headers}")
        if ipfs_response.status_code == 200:
            print(f"IPFS daemon status: {json.dumps(ipfs_response.json(), indent=2)}")
        else:
            print(f"Error: {ipfs_response.text}")
    except Exception as e:
        logger.error(f"Error in IPFS daemon request: {str(e)}", exc_info=True)
    
    # Test with daemon_type=lotus
    lotus_request = {"daemon_type": "lotus"}
    logger.debug(f"Sending request to {base_url}/ipfs/daemon/status with data: {lotus_request}")
    try:
        lotus_response = requests.post(f"{base_url}/ipfs/daemon/status", json=lotus_request)
        print(f"Status code for Lotus daemon: {lotus_response.status_code}")
        if lotus_response.status_code == 200:
            print(f"Lotus daemon status: {json.dumps(lotus_response.json(), indent=2)}")
        else:
            print(f"Error: {lotus_response.text}")
    except Exception as e:
        logger.error(f"Error in Lotus daemon request: {str(e)}", exc_info=True)
    
    # Test default without daemon_type
    default_request = {"daemon_type": None}
    logger.debug(f"Sending request to {base_url}/ipfs/daemon/status with data: {default_request}")
    try:
        default_response = requests.post(f"{base_url}/ipfs/daemon/status", json=default_request)
        print(f"Status code for default daemon status: {default_response.status_code}")
        if default_response.status_code == 200:
            print(f"Default daemon status: {json.dumps(default_response.json(), indent=2)}")
        else:
            print(f"Error: {default_response.text}")
    except Exception as e:
        logger.error(f"Error in default daemon request: {str(e)}", exc_info=True)
    
if __name__ == "__main__":
    test_daemon_status()
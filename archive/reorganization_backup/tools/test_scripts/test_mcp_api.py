#!/usr/bin/env python3
"""
Test MCP API Endpoints

This script directly tests the MCP API endpoints to verify that
our IPFS model fixes are working correctly.
"""

import sys
import json
import logging
import requests
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_test")

def test_api_endpoint(base_url, endpoint, method="get", data=None, expected_status=200):
    """Test an API endpoint and return the response.
    
    Args:
        base_url: Base URL of the API
        endpoint: Endpoint to test (without leading slash)
        method: HTTP method to use (get, post, etc.)
        data: Data to send with the request (for POST)
        expected_status: Expected HTTP status code
        
    Returns:
        The response object if successful, None otherwise
    """
    url = f"{base_url}/{endpoint}"
    logger.info(f"Testing {method.upper()} {url}")
    
    try:
        if method.lower() == "get":
            response = requests.get(url)
        elif method.lower() == "post":
            response = requests.post(url, json=data)
        else:
            logger.error(f"Unsupported method: {method}")
            return None
        
        if response.status_code == expected_status:
            logger.info(f"  Success: Status {response.status_code}")
            return response
        else:
            logger.error(f"  Failed: Expected status {expected_status}, got {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"  Error: {e}")
        return None

def main():
    """Test MCP API endpoints."""
    logger.info("Starting MCP API tests...")
    
    # Define the base URL
    base_url = "http://localhost:9994/api/v0"
    
    # Wait for the server to start
    max_retries = 12  # 60 seconds
    retry_interval = 5  # seconds
    
    logger.info(f"Waiting for MCP server to start (up to {max_retries * retry_interval} seconds)...")
    
    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health")
            if response.status_code == 200:
                logger.info(f"MCP server is up and running after {i * retry_interval} seconds")
                break
        except:
            pass
        
        logger.info(f"Attempt {i+1}/{max_retries}: Server not ready yet, waiting {retry_interval} seconds...")
        time.sleep(retry_interval)
    else:
        logger.error("MCP server not available after multiple attempts")
        return False
    
    # Test health endpoint
    health_response = test_api_endpoint(base_url, "health")
    if not health_response:
        logger.error("Health endpoint test failed")
        return False
    
    # Test IPFS add endpoint
    add_data = {"content": "This is a test content for MCP API"}
    add_response = test_api_endpoint(base_url, "ipfs/add", method="post", data=add_data)
    if not add_response:
        logger.error("IPFS add endpoint test failed")
        return False
    
    try:
        add_result = add_response.json()
        cid = add_result.get("cid")
        logger.info(f"Added content with CID: {cid}")
    except Exception as e:
        logger.error(f"Error parsing add response: {e}")
        return False
    
    # Test IPFS cat endpoint
    cat_response = test_api_endpoint(base_url, f"ipfs/cat/{cid}")
    if not cat_response:
        logger.error("IPFS cat endpoint test failed")
        return False
    
    # Test IPFS pin endpoint
    pin_data = {"cid": cid}
    pin_response = test_api_endpoint(base_url, "ipfs/pin", method="post", data=pin_data)
    if not pin_response:
        logger.error("IPFS pin endpoint test failed")
        return False
    
    # Test IPFS pins endpoint
    pins_response = test_api_endpoint(base_url, "ipfs/pins")
    if not pins_response:
        logger.error("IPFS pins endpoint test failed")
        return False
    
    # Test storage transfer endpoint
    transfer_data = {
        "source": "ipfs",
        "destination": "filecoin",
        "identifier": cid
    }
    transfer_response = test_api_endpoint(
        base_url, "storage/transfer", method="post", data=transfer_data
    )
    if not transfer_response:
        logger.error("Storage transfer endpoint test failed")
        return False
    
    logger.info("All MCP API tests passed!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

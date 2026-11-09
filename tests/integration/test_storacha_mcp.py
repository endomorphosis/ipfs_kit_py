#!/usr/bin/env python3
"""
Test script for Storacha integration through the MCP server.

This script tests various Storacha functionality through the MCP server interface:
- Status check
- Setting credentials
- Listing spaces
- Creating a space
- Uploading files
- Listing uploads
- Transferring content between IPFS and Storacha
"""

import requests
import os
import json
import time
import sys
import tempfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize IPFS daemon first to ensure it's running
from ipfs_kit_py.ipfs_kit import ipfs_kit
logger.info("Ensuring IPFS daemon is running...")
kit = ipfs_kit(auto_start_daemons=True)  # Use default leecher role
result = kit.initialize(start_daemons=True)
logger.info(f"IPFS initialization result: {result}")

# MCP server URL
MCP_SERVER_URL = "http://localhost:8002"

def test_server_status():
    """Test server status endpoint."""
    logger.info("Testing server status...")
    url = f"{MCP_SERVER_URL}/api/v0/mcp/health"
    response = requests.get(url)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {response.text}")
    return {"success": response.status_code == 200}

def test_storacha_status():
    """Test the Storacha status endpoint."""
    logger.info("Testing Storacha status...")
    url = f"{MCP_SERVER_URL}/api/v0/mcp/storage/storacha/status"
    response = requests.get(url)
    logger.info(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    else:
        logger.warning(f"Response: {response.text}")
        return {"success": False}

def test_storacha_credentials():
    """Test Storacha credentials functionality."""
    logger.info("Adding Storacha credentials...")
    url = f"{MCP_SERVER_URL}/api/v0/mcp/credentials/storacha"
    api_token = "test_token"  # Replace with actual token if available
    response = requests.post(url, json={"name": "default", "api_token": api_token})
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {json.dumps(response.json(), indent=2) if response.status_code == 200 else response.text}")
    return {"success": response.status_code == 200}

def test_list_spaces():
    """Test listing Storacha spaces."""
    logger.info("Listing Storacha spaces...")
    url = f"{MCP_SERVER_URL}/api/v0/mcp/storacha/space/list"
    response = requests.get(url)
    logger.info(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    else:
        logger.warning(f"Response: {response.text}")
        return {"success": False}

def test_create_space(name="test-space"):
    """Test creating a new Storacha space."""
    logger.info(f"Creating Storacha space: {name}...")
    url = f"{MCP_SERVER_URL}/api/v0/mcp/storacha/space/create"
    response = requests.post(url, json={"name": name})
    logger.info(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    else:
        logger.warning(f"Response: {response.text}")
        return {"success": False}

def test_upload_to_storacha():
    """Test uploading a file to Storacha."""
    logger.info("Uploading file to Storacha...")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        content = f"Test content for Storacha upload at {time.time()}"
        temp_file.write(content.encode('utf-8'))
        temp_path = temp_file.name
    
    # Upload the file
    url = f"{MCP_SERVER_URL}/api/v0/mcp/storacha/upload"
    response = requests.post(url, json={"file_path": temp_path})
    
    # Clean up
    os.unlink(temp_path)
    
    logger.info(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    else:
        logger.warning(f"Response: {response.text}")
        return {"success": False}

def test_list_uploads():
    """Test listing uploads in Storacha."""
    logger.info("Listing Storacha uploads...")
    url = f"{MCP_SERVER_URL}/api/v0/mcp/storacha/uploads"
    response = requests.get(url)
    logger.info(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    else:
        logger.warning(f"Response: {response.text}")
        return {"success": False}

def test_ipfs_to_storacha():
    """Test transferring content from IPFS to Storacha."""
    logger.info("Testing IPFS to Storacha transfer...")
    
    # First add content to IPFS
    ipfs_add_url = f"{MCP_SERVER_URL}/api/v0/mcp/ipfs/add"
    test_content = f"Test content for IPFS to Storacha transfer at {time.time()}"
    add_response = requests.post(ipfs_add_url, files={"file": ("test.txt", test_content.encode())})
    
    if add_response.status_code != 200:
        logger.error(f"Failed to add content to IPFS: {add_response.text}")
        return {"success": False, "error": "Failed to add to IPFS"}
    
    add_result = add_response.json()
    logger.info(f"IPFS Add Result: {json.dumps(add_result, indent=2)}")
    
    if not add_result.get("success", False):
        logger.error("Failed to add content to IPFS")
        return {"success": False, "error": "IPFS add not successful"}
    
    # Get the CID from the response - it could be in "hash", "Hash", or "cid" field
    ipfs_cid = add_result.get("Hash") or add_result.get("hash") or add_result.get("cid", "")
    
    if not ipfs_cid:
        logger.error("No CID found in IPFS response")
        return {"success": False, "error": "No CID in response"}
        
    logger.info(f"Using CID: {ipfs_cid}")
    
    # Now transfer from IPFS to Storacha
    url = f"{MCP_SERVER_URL}/api/v0/mcp/storacha/from_ipfs"
    response = requests.post(url, json={"cid": ipfs_cid})
    logger.info(f"Status Code: {response.status_code}")
    
    try:
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Response: {json.dumps(result, indent=2)}")
            return result
        else:
            logger.warning(f"Response: {response.text}")
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except json.JSONDecodeError:
        logger.error(f"Response: {response.text}")
        return {"success": False, "error": "Invalid JSON response"}

def main():
    """Run all Storacha integration tests."""
    logger.info("Starting Storacha MCP integration tests")
    success_count = 0
    fail_count = 0
    
    try:
        # Test server status
        logger.info("\n==== Testing Server Status ====")
        status_result = test_server_status()
        if not status_result["success"]:
            logger.error("Server status check failed - cannot continue tests")
            return 1
        success_count += 1
        
        # Test Storacha status
        logger.info("\n==== Testing Storacha Status ====")
        storacha_status = test_storacha_status()
        if storacha_status.get("success", False):
            success_count += 1
        else:
            fail_count += 1
        
        # Test Storacha credentials
        logger.info("\n==== Testing Storacha Credentials ====")
        credentials_result = test_storacha_credentials()
        
        if credentials_result.get("success", False):
            success_count += 1
            
            # Test listing spaces
            logger.info("\n==== Testing List Spaces ====")
            spaces_result = test_list_spaces()
            if spaces_result.get("success", False):
                success_count += 1
            else:
                fail_count += 1
            
            # Test creating a space - this may fail if using a test token
            logger.info("\n==== Testing Create Space ====")
            space_result = test_create_space()
            # Don't count this as a failure if it doesn't work with test token
            if space_result.get("success", False):
                success_count += 1
            
            # Test uploading to Storacha
            logger.info("\n==== Testing Upload to Storacha ====")
            upload_result = test_upload_to_storacha()
            if upload_result.get("success", False):
                success_count += 1
            else:
                fail_count += 1
            
            # Test listing uploads
            logger.info("\n==== Testing List Uploads ====")
            uploads_result = test_list_uploads()
            if uploads_result.get("success", False):
                success_count += 1
            else:
                fail_count += 1
            
            # Test IPFS to Storacha transfer
            logger.info("\n==== Testing IPFS to Storacha Transfer ====")
            transfer_result = test_ipfs_to_storacha()
            if transfer_result.get("success", False):
                success_count += 1
            else:
                fail_count += 1
        else:
            logger.warning("Credentials setup failed, skipping remaining tests")
            fail_count += 1
        
        logger.info(f"\nTest Results: {success_count} succeeded, {fail_count} failed")
        return 0 if fail_count == 0 else 1
        
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
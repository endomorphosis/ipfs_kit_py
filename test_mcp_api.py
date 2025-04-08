#!/usr/bin/env python3
"""
Test script for the MCP API endpoints.

This script tests the API endpoints using the correct URL patterns as defined
in the IPFSController, with the proper prefix used in the example server.
"""

import os
import time
import json
import requests
import tempfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API base URL with correct prefix from the MCP server example
base_url = 'http://localhost:8001'  # Using port 8001 for the new server instance
mcp_prefix = '/api/v0/mcp'  # This is the prefix used in the example server

def test_health():
    """Test the health endpoint."""
    logger.info("Testing health endpoint...")
    response = requests.get(f'{base_url}{mcp_prefix}/health')
    logger.info(f"Health response: {response.status_code}")
    if response.status_code == 200:
        logger.info("Health endpoint OK")
        result = response.json()
        logger.info(f"Health check result: {result}")
        return True
    else:
        logger.error("Health endpoint failed")
        return False

def test_add_content():
    """Test adding content to IPFS."""
    logger.info("Testing add content endpoint...")
    data = {
        "content": "Hello, IPFS from MCP!",
        "filename": "test.txt"
    }
    response = requests.post(f'{base_url}{mcp_prefix}/ipfs/add', json=data)
    logger.info(f"Add content response: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"Add content result: {result}")
        cid = result.get('cid') or result.get('Hash')
        if cid:
            logger.info(f"Content added with CID: {cid}")
            return cid
    
    logger.error("Add content failed")
    return None

def test_get_content(cid):
    """Test getting content from IPFS."""
    logger.info(f"Testing get content endpoint for CID: {cid}...")
    # Use the correct endpoint path: /ipfs/cat/{cid}
    response = requests.get(f'{base_url}{mcp_prefix}/ipfs/cat/{cid}')
    logger.info(f"Get content response: {response.status_code}")
    
    if response.status_code == 200:
        content = response.content
        logger.info(f"Retrieved content: {content.decode('utf-8')}")
        return True
    else:
        logger.error(f"Get content failed: {response.text}")
        return False

def test_get_content_json(cid):
    """Test getting content from IPFS as JSON."""
    logger.info(f"Testing get content JSON endpoint for CID: {cid}...")
    # Use the correct endpoint path: /ipfs/cat with POST and JSON body
    data = {"cid": cid}
    response = requests.post(f'{base_url}{mcp_prefix}/ipfs/cat', json=data)
    logger.info(f"Get content JSON response: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"Retrieved content (JSON): {result}")
        return True
    else:
        logger.error(f"Get content JSON failed: {response.text}")
        return False

def test_pin_content(cid):
    """Test pinning content to IPFS."""
    logger.info(f"Testing pin content endpoint for CID: {cid}...")
    # Use the correct endpoint path: /ipfs/pin/add with POST and JSON body
    data = {"cid": cid}
    response = requests.post(f'{base_url}{mcp_prefix}/ipfs/pin/add', json=data)
    logger.info(f"Pin content response: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"Pin content result: {result}")
        return True
    else:
        logger.error(f"Pin content failed: {response.text}")
        return False

def test_unpin_content(cid):
    """Test unpinning content from IPFS."""
    logger.info(f"Testing unpin content endpoint for CID: {cid}...")
    # Use the correct endpoint path: /ipfs/pin/rm with POST and JSON body
    data = {"cid": cid}
    response = requests.post(f'{base_url}{mcp_prefix}/ipfs/pin/rm', json=data)
    logger.info(f"Unpin content response: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"Unpin content result: {result}")
        return True
    else:
        logger.error(f"Unpin content failed: {response.text}")
        return False

def test_list_pins():
    """Test listing pinned content."""
    logger.info("Testing list pins endpoint...")
    # Use the correct endpoint path: /ipfs/pin/ls
    response = requests.get(f'{base_url}{mcp_prefix}/ipfs/pin/ls')
    logger.info(f"List pins response: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"List pins result: {result}")
        return True
    else:
        logger.error(f"List pins failed: {response.text}")
        return False

def test_stats():
    """Test getting IPFS operation statistics."""
    logger.info("Testing stats endpoint...")
    response = requests.get(f'{base_url}{mcp_prefix}/ipfs/stats')
    logger.info(f"Stats response: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"Stats result: {result}")
        return True
    else:
        logger.error(f"Stats failed: {response.text}")
        return False

def run_all_tests():
    """Run all API endpoint tests."""
    logger.info("Starting MCP API tests...")
    
    # Test health endpoint
    if not test_health():
        logger.error("Health endpoint test failed. Exiting.")
        return False
    
    # Test add content
    cid = test_add_content()
    if not cid:
        logger.error("Add content test failed. Exiting.")
        return False
    
    # Test get content
    test_get_content(cid)
    
    # Test get content as JSON
    test_get_content_json(cid)
    
    # Test pin content
    test_pin_content(cid)
    
    # Test list pins
    test_list_pins()
    
    # Test unpin content
    test_unpin_content(cid)
    
    # Test list pins again (should show change)
    test_list_pins()
    
    # Test stats
    test_stats()
    
    logger.info("All MCP API tests completed.")
    return True

if __name__ == "__main__":
    run_all_tests()
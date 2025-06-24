#!/usr/bin/env python3
"""
MCP API Endpoint Verification Script

This script performs basic tests on the MCP server API endpoints to verify
that all components are functioning correctly after the consolidation.
"""

import os
import sys
import json
import logging
import requests
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_verification")

# MCP server URL - adjust as needed
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:5000")

def test_endpoint(endpoint, method="GET", data=None, expected_status=200):
    """Test a specific API endpoint."""
    url = f"{MCP_SERVER_URL}{endpoint}"
    logger.info(f"Testing {method} {url}")

    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            logger.error(f"Unsupported method: {method}")
            return False

        if response.status_code == expected_status:
            logger.info(f"✅ Success: {response.status_code}")
            try:
                logger.debug(f"Response: {json.dumps(response.json(), indent=2)}")
            except:
                logger.debug(f"Raw response: {response.text[:100]}...")
            return True
        else:
            logger.error(f"❌ Failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Request failed: {e}")
        return False

def verify_ipfs_endpoints():
    """Verify IPFS-related endpoints."""
    logger.info("=== Testing IPFS Endpoints ===")

    endpoints = [
        "/api/v0/ipfs/version",
        "/api/v0/ipfs/pin/ls",
    ]

    success = True
    for endpoint in endpoints:
        if not test_endpoint(endpoint):
            success = False

    # Test add endpoint with sample data
    test_data = {"data": "Test content for API verification"}
    if not test_endpoint("/api/v0/ipfs/add", method="POST", data=test_data):
        success = False

    return success

def verify_filecoin_endpoints():
    """Verify Filecoin-related endpoints."""
    logger.info("=== Testing Filecoin Endpoints ===")

    endpoints = [
        "/api/v0/filecoin/advanced/network/stats",
        "/api/v0/filecoin/advanced/miner/list",
    ]

    success = True
    for endpoint in endpoints:
        if not test_endpoint(endpoint):
            success = False

    return success

def verify_streaming_endpoints():
    """Verify streaming-related endpoints."""
    logger.info("=== Testing Streaming Endpoints ===")

    endpoints = [
        "/api/v0/stream/status",
        "/api/v0/realtime/status",
        "/api/v0/webrtc/status",
    ]

    success = True
    for endpoint in endpoints:
        if not test_endpoint(endpoint):
            success = False

    return success

def verify_search_endpoints():
    """Verify search-related endpoints."""
    logger.info("=== Testing Search Endpoints ===")

    endpoints = [
        "/api/v0/search/status",
    ]

    success = True
    for endpoint in endpoints:
        if not test_endpoint(endpoint):
            success = False

    # Test search query
    query_data = {"query": "test", "limit": 10}
    if not test_endpoint("/api/v0/search/text", method="POST", data=query_data):
        success = False

    return success

def main():
    """Run all API verification tests."""
    logger.info(f"Starting MCP API verification against {MCP_SERVER_URL}")
    start_time = time.time()

    # Test server availability
    if not test_endpoint("/api/v0/status"):
        logger.error("Server is not responding. Aborting tests.")
        return False

    # Run all verification tests
    tests = [
        verify_ipfs_endpoints,
        verify_filecoin_endpoints,
        verify_streaming_endpoints,
        verify_search_endpoints,
    ]

    results = []
    for test_func in tests:
        results.append(test_func())

    # Print summary
    elapsed = time.time() - start_time
    logger.info(f"API verification completed in {elapsed:.2f} seconds")

    if all(results):
        logger.info("✅ All API tests passed!")
        return True
    else:
        logger.error("❌ Some API tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

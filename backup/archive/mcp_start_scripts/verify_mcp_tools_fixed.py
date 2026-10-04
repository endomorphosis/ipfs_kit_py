#!/usr/bin/env python3
"""
Verification script for MCP server tools and endpoints.

This script tests the MCP server endpoints to ensure they are working properly.
"""

import os
import sys
import time
import json
import argparse
import requests
from typing import Dict, List, Any

def test_endpoint(base_url: str, endpoint: str, method: str = "GET", data: Dict = None, files: Dict = None) -> Dict:
    """
    Test an endpoint and return the response.

    Args:
        base_url: Base URL of the MCP server
        endpoint: Endpoint to test
        method: HTTP method to use
        data: Data to send in the request
        files: Files to send in the request

    Returns:
        Dictionary with test result
    """
    url = f"{base_url}{endpoint}"
    print(f"Testing {method} {url}...")

    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, data=data, files=files)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}

        # Try to parse as JSON
        try:
            result = response.json()
            print(f"  Status: {response.status_code}")
            print(f"  Response: {json.dumps(result, indent=2)}")
            return {"success": True, "status_code": response.status_code, "response": result}
        except:
            # Return raw content if not JSON
            print(f"  Status: {response.status_code}")
            content = response.content.decode('utf-8')
            if len(content) > 100:
                content = content[:100] + "... (truncated)"
            print(f"  Response: {content}")
            return {"success": True, "status_code": response.status_code, "content": content}

    except Exception as e:
        print(f"  Error: {e}")
        return {"success": False, "error": str(e)}

def test_storage_backend(base_url: str, backend: str) -> Dict:
    """
    Test a storage backend endpoints.

    Args:
        base_url: Base URL of the MCP server
        backend: Name of the storage backend

    Returns:
        Dictionary with test results
    """
    results = {}

    # Test status endpoint
    results["status"] = test_endpoint(base_url, f"/api/v0/{backend}/status")

    return results

def test_ipfs_endpoints(base_url: str) -> Dict:
    """
    Test IPFS endpoints.

    Args:
        base_url: Base URL of the MCP server

    Returns:
        Dictionary with test results
    """
    results = {}

    # Test version endpoint
    results["version"] = test_endpoint(base_url, "/api/v0/ipfs/version")

    # Test pin/ls endpoint
    results["pin_ls"] = test_endpoint(base_url, "/api/v0/ipfs/pin/ls")

    return results

def main():
    """Run the verification script."""
    parser = argparse.ArgumentParser(description="Verify MCP server tools and endpoints")
    parser.add_argument("--url", type=str, default="http://localhost:9997", help="Base URL of the MCP server")
    parser.add_argument("--skip-storage", action="store_true", help="Skip testing storage backends")
    parser.add_argument("--skip-ipfs", action="store_true", help="Skip testing IPFS endpoints")

    args = parser.parse_args()

    print(f"Verifying MCP server at {args.url}...")

    # Test root endpoint
    print("\n=== Testing root endpoint ===")
    root_result = test_endpoint(args.url, "/")

    if not root_result["success"]:
        print(f"Error testing root endpoint: {root_result.get('error', 'unknown error')}")
        sys.exit(1)

    # Test storage backends
    if not args.skip_storage:
        backends = ["huggingface", "s3", "filecoin", "storacha", "lassie"]

        print("\n=== Testing storage backends ===")
        for backend in backends:
            print(f"\nTesting {backend} backend:")
            results = test_storage_backend(args.url, backend)

    # Test IPFS endpoints
    if not args.skip_ipfs:
        print("\n=== Testing IPFS endpoints ===")
        ipfs_results = test_ipfs_endpoints(args.url)

    print("\n=== All tests completed ===")


if __name__ == "__main__":
    main()

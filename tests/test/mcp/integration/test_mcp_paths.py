#!/usr/bin/env python3
"""
Test script to verify the MCP server path prefix fix.

This script tests that the MCP server correctly handles paths for advanced
controller endpoints after changing the prefix from /api/v0/mcp to /api/v0.
"""

import requests
import sys
import time


def test_mcp_endpoints():
    """Test that MCP endpoints are accessible with the new prefix."""
    # Define test endpoints
    endpoints = [
        "/api/v0/health",
        "/api/v0/webrtc/check",
        "/api/v0/cli/status",
        "/api/v0/discovery/server"
    ]
    
    base_url = "http://localhost:8000"
    results = {}
    
    # Test each endpoint
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=5)
            results[endpoint] = {
                "status_code": response.status_code,
                "working": response.status_code != 404
            }
        except requests.exceptions.RequestException as e:
            results[endpoint] = {
                "error": str(e),
                "working": False
            }
    
    # Print results
    print("\nEndpoint Test Results:")
    print("-" * 50)
    for endpoint, result in results.items():
        status = "✅ Working" if result.get("working") else "❌ Not Working"
        code = result.get("status_code", "N/A")
        print(f"{endpoint}: {status} (Status: {code})")
    
    # Determine if test passed
    all_working = all(result.get("working", False) for result in results.values())
    print("\nOverall Result:", "✅ All endpoints working" if all_working else "❌ Some endpoints not working")
    
    return all_working


if __name__ == "__main__":
    print("Waiting for MCP server to be ready...")
    time.sleep(3)
    success = test_mcp_endpoints()
    sys.exit(0 if success else 1)
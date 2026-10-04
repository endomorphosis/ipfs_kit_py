#!/usr/bin/env python3
"""
Simple MCP Server Tester

This script provides a simple way to test the JSON-RPC endpoints of the MCP server.
"""

import sys
import time
import json
import requests
import argparse
from typing import Dict, Any, Optional, List

def log(message: str):
    """Simple logging function."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def test_endpoint(method: str, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test a JSON-RPC endpoint."""
    if params is None:
        params = {}
    
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": int(time.time() * 1000)
    }
    
    log(f"Testing {method}...")
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log(f"Error testing {method}: {e}")
        return {"error": {"message": str(e)}}

def main():
    parser = argparse.ArgumentParser(description="Simple MCP Server Tester")
    parser.add_argument("--url", type=str, default="http://localhost:9997/jsonrpc", help="JSON-RPC endpoint URL")
    parser.add_argument("--health-url", type=str, default="http://localhost:9997/health", help="Health endpoint URL")
    parser.add_argument("--method", type=str, help="Specific method to test")
    args = parser.parse_args()
    
    # Check server health
    log(f"Checking server health at {args.health_url}...")
    try:
        health_response = requests.get(args.health_url, timeout=5)
        if health_response.status_code == 200:
            log(f"Server is healthy: {health_response.text}")
        else:
            log(f"Server health check failed with status code {health_response.status_code}")
            return 1
    except Exception as e:
        log(f"Error checking server health: {e}")
        return 1
    
    # Test a specific method if provided
    if args.method:
        result = test_endpoint(args.method, args.url)
        log(f"Result: {json.dumps(result, indent=2)}")
        return 0
    
    # Otherwise, test all standard methods
    methods = ["ping", "list_tools", "get_tools", "get_server_info"]
    success = True
    
    for method in methods:
        result = test_endpoint(method, args.url)
        
        if "error" in result:
            log(f"❌ {method} failed: {json.dumps(result['error'])}")
            success = False
        else:
            log(f"✅ {method} succeeded")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

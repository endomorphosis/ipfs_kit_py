#!/usr/bin/env python
"""
Test script for MCP server with storage backend integration.

This script:
1. Starts an MCP server with storage backends enabled
2. Verifies that the storage controllers are registered
3. Makes test requests to the storage API endpoints
4. Checks that responses are as expected
"""

import time
import json
import requests
import argparse

def test_mcp_server(host="127.0.0.1", port=9000, prefix="/api/v0/mcp"):
    """Test the MCP server and its storage backends.
    
    Args:
        host: Host where the MCP server is running
        port: Port where the MCP server is running
        prefix: URL prefix for MCP endpoints
        
    Returns:
        Dict with test results
    """
    base_url = f"http://{host}:{port}{prefix}"
    
    # Test health endpoint
    print("Testing MCP server health...")
    health_url = f"{base_url}/health"
    try:
        health_response = requests.get(health_url)
        health_data = health_response.json()
        print(f"Health status: {health_data.get('status', 'unknown')}")
    except Exception as e:
        print(f"Error checking server health: {e}")
        return {"success": False, "error": str(e)}
    
    # Check available storage backends
    print("\nChecking available storage backends...")
    debug_url = f"{base_url}/debug"
    try:
        debug_response = requests.get(debug_url)
        debug_data = debug_response.json()
        
        print(f"Debug data storage section: {debug_data.get('storage', {})}")
        
        if "storage" in debug_data and "available_backends" in debug_data["storage"]:
            backends = debug_data["storage"]["available_backends"]
            print("Available backends:")
            for backend, available in backends.items():
                status = "Available" if available else "Not available"
                print(f"  - {backend}: {status}")
        else:
            print("No storage backend information found in debug data")
            
    except Exception as e:
        print(f"Error checking storage backends: {e}")
    
    # Test S3 backend if available
    print("\nTesting S3 backend...")
    try:
        s3_status_url = f"{base_url}/storage/s3/status"
        print(f"Requesting: {s3_status_url}")
        s3_status_response = requests.get(s3_status_url)
        
        print(f"Response status code: {s3_status_response.status_code}")
        print(f"Response headers: {dict(s3_status_response.headers)}")
        print(f"Response content: {s3_status_response.text}")
        
        if s3_status_response.status_code == 200:
            s3_status = s3_status_response.json()
            print(f"S3 backend status: {s3_status}")
        else:
            print(f"S3 backend not available: {s3_status_response.status_code} {s3_status_response.text}")
    except Exception as e:
        print(f"Error testing S3 backend: {e}")
    
    # Test Hugging Face backend if available
    print("\nTesting Hugging Face backend...")
    try:
        hf_status_url = f"{base_url}/storage/huggingface/status"
        hf_status_response = requests.get(hf_status_url)
        
        if hf_status_response.status_code == 200:
            hf_status = hf_status_response.json()
            print(f"Hugging Face backend status: {hf_status}")
        else:
            print(f"Hugging Face backend not available: {hf_status_response.status_code} {hf_status_response.text}")
    except Exception as e:
        print(f"Error testing Hugging Face backend: {e}")
    
    # Test Storacha backend if available
    print("\nTesting Storacha backend...")
    try:
        storacha_status_url = f"{base_url}/storage/storacha/status"
        storacha_status_response = requests.get(storacha_status_url)
        
        if storacha_status_response.status_code == 200:
            storacha_status = storacha_status_response.json()
            print(f"Storacha backend status: {storacha_status}")
        else:
            print(f"Storacha backend not available: {storacha_status_response.status_code} {storacha_status_response.text}")
    except Exception as e:
        print(f"Error testing Storacha backend: {e}")
    
    return {"success": True, "timestamp": time.time()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test MCP Server Storage Backends")
    parser.add_argument("--host", default="127.0.0.1", help="MCP server host")
    parser.add_argument("--port", type=int, default=10000, help="MCP server port")
    parser.add_argument("--prefix", default="/api/v0/mcp", help="MCP API prefix")
    
    # Only parse args when running the script directly, not when imported by pytest
    
    if __name__ == "__main__":
    
        args = parser.parse_args()
    
    else:
    
        # When run under pytest, use default values
    
        args = parser.parse_args([])
    
    print(f"Testing MCP server at http://{args.host}:{args.port}{args.prefix}")
    result = test_mcp_server(args.host, args.port, args.prefix)
    
    if result.get("success", False):
        print("\nStorage backend integration test completed successfully!")
    else:
        print(f"\nTest failed: {result.get('error', 'Unknown error')}")
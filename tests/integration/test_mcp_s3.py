#!/usr/bin/env python3
"""Test S3 storage backend integration with MCP server."""

import json
import requests
import sys

# Configuration
MCP_URL = "http://127.0.0.1:9999"  # Using port 9999 as the server is running there

def test_s3_status():
    """Test the status of S3 integration."""
    print("Testing S3 status...")
    
    # First try the direct status endpoint
    response = requests.get(f"{MCP_URL}/api/v0/mcp/storage/s3/status")
    print(f"Status response ({response.status_code}):")
    try:
        formatted = json.dumps(response.json(), indent=2)
        print(formatted)
    except:
        print(response.text)
    print()

def explore_s3_endpoints():
    """Explore available S3 endpoints."""
    print("Exploring S3 endpoints...")
    
    # Fetch OpenAPI documentation to see what paths are available
    response = requests.get(f"{MCP_URL}/openapi.json")
    if response.status_code == 200:
        api_doc = response.json()
        s3_paths = [path for path in api_doc["paths"].keys() 
                    if "s3" in path.lower() and path != "/api/v0/mcp/storage/s3/status"]
        
        print(f"Found {len(s3_paths)} S3-related paths:")
        for path in s3_paths:
            print(f"  {path}")
        print()
        
        # Test a few key endpoints
        if s3_paths:
            for path in s3_paths:
                # Only test GET endpoints for safety
                if "GET" in api_doc["paths"][path]:
                    print(f"Trying GET {path}...")
                    response = requests.get(f"{MCP_URL}{path}")
                    print(f"Response ({response.status_code}):")
                    try:
                        formatted = json.dumps(response.json(), indent=2)
                        print(formatted)
                    except:
                        print(response.text)
                    print()
    else:
        print("Failed to fetch OpenAPI documentation")
        print(response.text)
        print()

def test_s3_bucket_operations():
    """Test S3 bucket operations if available."""
    print("Testing S3 bucket operations...")
    
    # List buckets endpoint (common S3 operation)
    buckets_endpoint = f"{MCP_URL}/api/v0/mcp/storage/s3/buckets"
    response = requests.get(buckets_endpoint)
    
    print(f"List buckets response ({response.status_code}):")
    try:
        formatted = json.dumps(response.json(), indent=2)
        print(formatted)
    except:
        print(response.text)
    print()

if __name__ == "__main__":
    print("=== S3 Integration Tests ===\n")
    
    test_s3_status()
    explore_s3_endpoints()
    test_s3_bucket_operations()
    
    print("Tests completed.")
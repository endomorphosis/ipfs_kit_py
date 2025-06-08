#!/usr/bin/env python3
"""
Test script for the Lassie integration in the MCP server.
Lassie is a content-addressed data retrieval client.
"""

import requests
import json
import sys

# Configuration
MCP_URL = "http://127.0.0.1:9999"

def test_lassie_status():
    """Test the status of Lassie integration."""
    print("Testing Lassie status...")
    
    try:
        response = requests.get(f"{MCP_URL}/api/v0/mcp/storage/lassie/status")
        print(f"Status response ({response.status_code}):")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
    except Exception as e:
        print(f"Error in Lassie status test: {e}")

def test_lassie_endpoints():
    """Test all available Lassie endpoints."""
    print("\nExploring Lassie endpoints...")
    
    try:
        response = requests.get(f"{MCP_URL}/openapi.json")
        if response.status_code == 200:
            openapi = response.json()
            lassie_paths = [path for path in openapi.get('paths', {}).keys() 
                           if '/lassie/' in path]
            
            print(f"Found {len(lassie_paths)} Lassie-related paths:")
            for path in sorted(lassie_paths):
                print(f"  {path}")
            
            # Try each GET path
            for path in lassie_paths:
                if 'get' in openapi.get('paths', {}).get(path, {}):
                    try:
                        print(f"\nTrying GET {path}...")
                        response = requests.get(f"{MCP_URL}{path}")
                        print(f"Response ({response.status_code}):")
                        if response.status_code == 200:
                            print(json.dumps(response.json(), indent=2))
                        else:
                            print(response.text)
                    except Exception as e:
                        print(f"Error accessing {path}: {e}")
    
    except Exception as e:
        print(f"Error exploring Lassie endpoints: {e}")

def test_lassie_fetch():
    """Test fetching a known CID with Lassie."""
    print("\nTesting Lassie fetch with a known good CID...")
    
    # IPFS example directory CID
    test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    
    try:
        # First check if direct fetch endpoint exists
        response = requests.post(
            f"{MCP_URL}/api/v0/mcp/lassie/fetch",
            json={"cid": test_cid}
        )
        print(f"Direct fetch response ({response.status_code}):")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
            
            # Try alternate endpoint format
            print("\nTrying alternate fetch endpoint...")
            response = requests.post(
                f"{MCP_URL}/api/v0/mcp/storage/lassie/fetch",
                json={"cid": test_cid}
            )
            print(f"Storage fetch response ({response.status_code}):")
            if response.status_code == 200:
                print(json.dumps(response.json(), indent=2))
            else:
                print(response.text)
    
    except Exception as e:
        print(f"Error in Lassie fetch test: {e}")

if __name__ == "__main__":
    print("=== Lassie Integration Tests ===\n")
    test_lassie_status()
    test_lassie_endpoints()
    test_lassie_fetch()
    print("\nTests completed.")
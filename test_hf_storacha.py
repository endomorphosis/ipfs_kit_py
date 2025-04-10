#!/usr/bin/env python3
"""
Test script for Hugging Face and Storacha storage backends in the MCP server.
"""

import requests
import json
import time
import sys

# Configuration
MCP_URL = "http://127.0.0.1:9999"

def test_huggingface():
    """Test the Hugging Face integration."""
    print("=== Testing Hugging Face Integration ===\n")
    
    try:
        # Check status
        print("Testing Hugging Face status...")
        response = requests.get(f"{MCP_URL}/api/v0/mcp/storage/huggingface/status")
        print(f"Status endpoint response ({response.status_code}):")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
        
        # Explore available endpoints from OpenAPI docs
        print("\nExploring Hugging Face endpoints...")
        response = requests.get(f"{MCP_URL}/openapi.json")
        if response.status_code == 200:
            openapi = response.json()
            hf_paths = [path for path in openapi.get('paths', {}).keys() 
                        if '/huggingface/' in path]
            
            print(f"Found {len(hf_paths)} Hugging Face-related paths:")
            for path in sorted(hf_paths):
                print(f"  {path}")
            
            # Try each GET path
            for path in hf_paths:
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
        print(f"Error in Hugging Face test: {e}")

def test_storacha():
    """Test the Storacha integration."""
    print("\n=== Testing Storacha Integration ===\n")
    
    try:
        # Check status
        print("Testing Storacha status...")
        response = requests.get(f"{MCP_URL}/api/v0/mcp/storage/storacha/status")
        print(f"Status endpoint response ({response.status_code}):")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
        
        # Explore available endpoints from OpenAPI docs
        print("\nExploring Storacha endpoints...")
        response = requests.get(f"{MCP_URL}/openapi.json")
        if response.status_code == 200:
            openapi = response.json()
            storacha_paths = [path for path in openapi.get('paths', {}).keys() 
                             if '/storacha/' in path]
            
            print(f"Found {len(storacha_paths)} Storacha-related paths:")
            for path in sorted(storacha_paths):
                print(f"  {path}")
            
            # Try each GET path
            for path in storacha_paths:
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
        print(f"Error in Storacha test: {e}")

if __name__ == "__main__":
    test_huggingface()
    test_storacha()
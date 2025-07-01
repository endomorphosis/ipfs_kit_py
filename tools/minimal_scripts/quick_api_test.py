#!/usr/bin/env python3
"""
Quick API Test for MCP Server

This script performs a simple GET request to check if the MCP server API is responding.
"""

import requests
import sys
import time

def main():
    """Simple test of MCP server API health endpoint."""
    print("Testing MCP server API health...")
    
    base_url = "http://localhost:9994/api/v0"
    
    # Try to connect to the health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"SUCCESS: Health endpoint returned status {response.status_code}")
            print(f"Response body: {response.text}")
            return 0
        else:
            print(f"ERROR: Health endpoint returned unexpected status {response.status_code}")
            return 1
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not connect to MCP server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

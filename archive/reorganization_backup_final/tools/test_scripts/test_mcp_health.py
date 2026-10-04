#!/usr/bin/env python3
"""
Simple MCP Health Check

Tests the health endpoint of the MCP server running on port 9994.
"""

import sys
import requests
import time

def main():
    """Check if the MCP server is running and healthy."""
    print("Testing MCP server health on port 9994...")
    
    base_url = "http://localhost:9994/api/v0"
    max_attempts = 5
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Attempt {attempt}/{max_attempts}...")
            response = requests.get(f"{base_url}/health", timeout=2)
            
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("SUCCESS: MCP server is healthy!")
                return 0
            else:
                print(f"WARNING: Unexpected status code {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            
        if attempt < max_attempts:
            wait_time = 2
            print(f"Waiting {wait_time} seconds before next attempt...")
            time.sleep(wait_time)
            
    print("FAILURE: Could not connect to MCP server health endpoint after multiple attempts")
    return 1

if __name__ == "__main__":
    sys.exit(main())

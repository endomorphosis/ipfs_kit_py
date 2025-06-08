#!/usr/bin/env python3
"""
Simple script to test the MCP server health endpoint.
"""

import requests
import json
import sys

def main():
    """Test the MCP server health endpoint."""
    print("Testing MCP server health...")
    
    try:
        # Make a request to the health endpoint
        response = requests.get("http://127.0.0.1:9999/api/v0/mcp/health")
        
        # Check the status code
        print(f"Status code: {response.status_code}")
        
        # Parse the response as JSON
        data = response.json()
        
        # Print the response data
        print("Response data:")
        print(json.dumps(data, indent=2))
        
        # Check if the response is successful
        if data.get("success", False):
            print("MCP server is healthy!")
            return 0
        else:
            print("MCP server returned an error.")
            return 1
            
    except requests.RequestException as e:
        print(f"Error connecting to MCP server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
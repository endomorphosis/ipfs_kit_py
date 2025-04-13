#!/usr/bin/env python3
"""
Script to inspect the running MCP server and diagnose the pins method issue.
"""

import requests
import json
import time
from pprint import pprint

def inspect_mcp():
    """Inspect the running MCP server."""
    print("Inspecting running MCP server...")
    
    # Try the health endpoint to see if server is running
    try:
        response = requests.get("http://localhost:9990/api/v0/health")
        print(f"Health check status: {response.status_code}")
        if response.status_code == 200:
            print("Server is running on port 9990")
        else:
            print(f"Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to port 9990: {e}")
    
    # Test the pins endpoint
    try:
        response = requests.get("http://localhost:9990/api/v0/mcp/cli/pins")
        print(f"\nPins endpoint status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("Response:")
            pprint(result)
            
            if not result.get("success", False) and "error" in result.get("result", {}):
                error = result["result"]["error"]
                print(f"\nError detected: {error}")
                
                if "IPFSSimpleAPI.pins() got an unexpected keyword argument" in error:
                    print("\nDiagnosis: The IPFSSimpleAPI.pins() method in the running server instance doesn't accept the expected parameters.")
                    print("This means the server is using a different version of the IPFSSimpleAPI class than what we see in the file.")
                    print("\nPossible solutions:")
                    print("1. Restart the server to load the latest code")
                    print("2. Use the fixed server running on port 9991 instead")
                    print("3. Modify the controller to not pass parameters to the pins method")
        else:
            print(f"Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"Error testing pins endpoint: {e}")
    
    # Test the fixed server
    try:
        response = requests.get("http://localhost:9991/api/v0/mcp/cli/pins")
        print(f"\nFixed server pins endpoint status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("Response:")
            pprint(result)
            
            if result.get("success", False):
                print("\nThe fixed server on port 9991 is working correctly!")
                print("You can use this server instead of the one on port 9990.")
    except Exception as e:
        print(f"Error connecting to fixed server on port 9991: {e}")
        
    # Recommendations
    print("\nRecommendations:")
    print("1. Use the fixed server running on port 9991 for immediate resolution.")
    print("2. To fix the original server, restart it after ensuring your code changes are applied.")
    print("3. Use the controller fix we implemented in cli_controller_anyio.py for long-term stability.")

if __name__ == "__main__":
    inspect_mcp()
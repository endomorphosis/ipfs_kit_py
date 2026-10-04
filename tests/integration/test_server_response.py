"""
Simple script to test the MCP server response.
"""

import sys
import json
import requests
import time

def test_server():
    """Test the MCP server response."""
    url = "http://localhost:8000/"
    print(f"Testing server at {url}...")
    
    try:
        response = requests.get(url)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("JSON response received:")
                print(json.dumps(data, indent=2))
            except ValueError:
                print("Response is not valid JSON:")
                print(response.text[:1000])  # Show the first 1000 chars
        else:
            print(f"Error response received: {response.text[:1000]}")
            
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to server: {e}")
        return False
        
    return True

if __name__ == "__main__":
    test_server()
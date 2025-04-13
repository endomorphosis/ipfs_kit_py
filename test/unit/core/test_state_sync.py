#!/usr/bin/env python3
"""
Standalone test script for the state sync endpoint.
"""

import requests
import json
import time

def test_state_sync():
    """Test the state synchronization endpoint directly."""
    print("Testing state synchronization endpoint")
    
    url = "http://localhost:9999/api/v0/mcp/distributed/state/sync"
    headers = {"Content-Type": "application/json"}
    
    # Test data - as a dictionary (what the server expects)
    data_dict = {
        "force_full_sync": False,
        "target_nodes": []
    }
    
    # Test data - as a list (what FastAPI seems to want)
    data_list = [
        {
            "force_full_sync": False,
            "target_nodes": []
        }
    ]
    
    # Try several different ways of sending the data
    
    # 1. As JSON with json parameter - dictionary
    print("\n1. Testing with requests.post(..., json=data_dict)")
    try:
        response = requests.post(url, json=data_dict, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 2. As JSON with json parameter - list
    print("\n2. Testing with requests.post(..., json=data_list)")
    try:
        response = requests.post(url, json=data_list, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 3. As string-encoded JSON - dictionary
    print("\n3. Testing with requests.post(..., data=json.dumps(data_dict))")
    try:
        response = requests.post(url, data=json.dumps(data_dict), headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 4. As string-encoded JSON - list
    print("\n4. Testing with requests.post(..., data=json.dumps(data_list))")
    try:
        response = requests.post(url, data=json.dumps(data_list), headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 5. With curl equivalent using requests - dictionary
    print("\n5. Testing with curl equivalent - dictionary")
    try:
        import subprocess
        result = subprocess.run(
            ['curl', '-X', 'POST', url, 
             '-H', 'Content-Type: application/json', 
             '-d', json.dumps(data_dict)],
            capture_output=True, text=True
        )
        print(f"Status: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
    except Exception as e:
        print(f"Error: {e}")
        
    # 6. With curl equivalent using requests - list
    print("\n6. Testing with curl equivalent - list")
    try:
        import subprocess
        result = subprocess.run(
            ['curl', '-X', 'POST', url, 
             '-H', 'Content-Type: application/json', 
             '-d', json.dumps(data_list)],
            capture_output=True, text=True
        )
        print(f"Status: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_state_sync()
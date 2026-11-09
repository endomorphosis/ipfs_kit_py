#!/usr/bin/env python3
"""
Test MCP server initialize request.
This script specifically tests the initialize request that VS Code is attempting to make.
"""
import requests
import json
import time
import sys

print("Testing MCP server initialize request at", time.strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 50)

# First, check if the server is running
try:
    response = requests.get("http://localhost:9994/", timeout=5)
    print(f"Server status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Server is running")
        try:
            data = response.json()
            print(f"Server controllers: {data.get('controllers', [])}")
            print(f"Server endpoints: {list(data.get('example_endpoints', {}).keys())}")
        except:
            print(f"❌ Could not parse server response: {response.text[:200]}...")
    else:
        print(f"❌ Server error: {response.text[:200]}...")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error connecting to server: {e}")
    sys.exit(1)

# Create a simple JSON-RPC request for initialize
init_payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "capabilities": {},
        "processId": 12345,
        "rootUri": "file:///home/barberb/ipfs_kit_py",
        "workspaceFolders": [
            {
                "uri": "file:///home/barberb/ipfs_kit_py",
                "name": "ipfs_kit_py"
            }
        ]
    }
}

# Send the initialize request to the server
try:
    print(f"\nSending initialize request to http://localhost:9994/api/v0/jsonrpc")
    response = requests.post(
        "http://localhost:9994/api/v0/jsonrpc",
        json=init_payload,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    print(f"Initialize request status: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        print("✅ Initialize endpoint is available!")
        try:
            data = response.json()
            print(f"Initialize response: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"❌ Could not parse response as JSON: {e}")
            print(f"Raw response: {response.text[:500]}...")
    else:
        print(f"❌ Initialize endpoint error: {response.text[:200]}...")
except Exception as e:
    print(f"❌ Error sending initialize request: {e}")

# Try with a different endpoint
try:
    print(f"\nTrying alternate endpoint: http://localhost:9994/jsonrpc")
    response = requests.post(
        "http://localhost:9994/jsonrpc",
        json=init_payload,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    print(f"Initialize request status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Initialize endpoint is available!")
        try:
            data = response.json()
            print(f"Initialize response: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"❌ Could not parse response as JSON: {e}")
            print(f"Raw response: {response.text[:500]}...")
    else:
        print(f"❌ Initialize endpoint error: {response.text[:200]}...")
except Exception as e:
    print(f"❌ Error sending initialize request: {e}")

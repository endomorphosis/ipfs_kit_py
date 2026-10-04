#!/usr/bin/env python3
import requests
import json
import time
import sys

def call_jsonrpc(method, params=None):
    url = "http://localhost:9996/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(time.time() * 1000)
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": {"message": str(e)}}

def debug_ipfs_calls():
    # Test list_tools first
    print("Getting available tools...")
    tools = call_jsonrpc("list_tools")
    print(f"Tools response: {json.dumps(tools, indent=2)}")
    
    # Test ipfs_version
    print("\nTesting ipfs_version...")
    version = call_jsonrpc("ipfs_version")
    print(f"Version response: {json.dumps(version, indent=2)}")
    
    # Test ipfs_add
    print("\nTesting ipfs_add...")
    add_result = call_jsonrpc("ipfs_add", {"content": "Test content for debugging"})
    print(f"Add response: {json.dumps(add_result, indent=2)}")
    
    # Extract CID if possible
    cid = None
    if "result" in add_result:
        result = add_result["result"]
        print(f"Result type: {type(result).__name__}")
        
        if isinstance(result, dict):
            if "Hash" in result:
                cid = result["Hash"]
            elif "cid" in result:
                cid = result["cid"]
        # Try to handle if it's directly a string
        elif isinstance(result, str):
            cid = result
    
    if cid:
        print(f"\nExtracted CID: {cid}")
        # Test ipfs_cat
        print("\nTesting ipfs_cat...")
        cat_result = call_jsonrpc("ipfs_cat", {"cid": cid})
        print(f"Cat response: {json.dumps(cat_result, indent=2)}")
    else:
        print("\nCould not extract CID from response")

if __name__ == "__main__":
    debug_ipfs_calls()

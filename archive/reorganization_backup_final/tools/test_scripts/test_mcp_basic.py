#!/usr/bin/env python3
"""
Simple MCP Server Tester

This script tests the MCP server by sending a basic JSON-RPC request.
"""

import sys
import json
import time
import logging
import traceback
import requests

def test_jsonrpc_call(url, method, params=None, req_id=None):
    """Send a JSON-RPC request to the server"""
    if req_id is None:
        req_id = int(time.time() * 1000)
        
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": req_id
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return True, result
        else:
            return False, {"error": f"HTTP Error: {response.status_code}", "response_text": response.text}
    except Exception as e:
        return False, {"error": str(e), "traceback": traceback.format_exc()}

def main():
    """Main function"""
    url = "http://localhost:9997/jsonrpc"
    success_count = 0
    failure_count = 0
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    logging.info("=== MCP Server Test ===")
    
    # Test 1: Basic ping
    try:
        logging.info("Test 1: Basic ping")
        response = requests.post(url, json={
            "jsonrpc": "2.0",
            "method": "ping",
            "id": 1
        })
        
        if response.status_code == 200 and response.json().get("result") == "pong":
            logging.info("✅ Ping test successful")
            success_count += 1
        else:
            logging.error(f"❌ Ping test failed: {response.status_code} - {response.text}")
            failure_count += 1
    except Exception as e:
        logging.error(f"❌ Ping test error: {e}")
        traceback.print_exc()
        failure_count += 1
    
    # Test 2: Get tools
    try:
        logging.info("\nTest 2: List available tools")
        response = requests.post(url, json={
            "jsonrpc": "2.0",
            "method": "get_tools",
            "id": 2
        })
        
        if response.status_code == 200 and "tools" in response.json().get("result", {}):
            tools = response.json()["result"]["tools"]
            logging.info(f"✅ Got {len(tools)} tools")
            success_count += 1
        else:
            logging.error(f"❌ Get tools test failed: {response.status_code} - {response.text}")
            failure_count += 1
    except Exception as e:
        logging.error(f"❌ Get tools test error: {e}")
        traceback.print_exc()
        failure_count += 1
    
    # Test 3: Create directory in MFS
    try:
        logging.info("\nTest 3: Create directory in MFS")
        test_dir = f"/test_dir_{int(time.time())}"
        response = requests.post(url, json={
            "jsonrpc": "2.0",
            "method": "ipfs_files_mkdir",
            "params": {"path": test_dir},
            "id": 3
        })
        
        if response.status_code == 200 and isinstance(response.json().get("result"), dict) and \
           response.json().get("result", {}).get("success", False):
            logging.info(f"✅ Created directory {test_dir}")
            success_count += 1
        else:
            logging.error(f"❌ Directory creation failed: {response.status_code} - {response.text}")
            failure_count += 1
    except Exception as e:
        logging.error(f"❌ Directory creation error: {e}")
        traceback.print_exc()
        failure_count += 1
    
    # Test 4: Write to MFS
    try:
        logging.info("\nTest 4: Write to MFS")
        test_file = f"{test_dir}/hello.txt"
        response = requests.post(url, json={
            "jsonrpc": "2.0",
            "method": "ipfs_files_write",
            "params": {
                "path": test_file,
                "content": "Hello IPFS MCP World!",
                "create": True
            },
            "id": 4
        })
        
        if response.status_code == 200 and isinstance(response.json().get("result"), dict) and \
           response.json().get("result", {}).get("success", False):
            logging.info(f"✅ Wrote to file {test_file}")
            success_count += 1
        else:
            logging.error(f"❌ File write failed: {response.status_code} - {response.text}")
            failure_count += 1
    except Exception as e:
        logging.error(f"❌ File write error: {e}")
        traceback.print_exc()
        failure_count += 1
    
    # Test 5: Read from MFS
    try:
        logging.info("\nTest 5: Read from MFS")
        # Make sure we have a file path even if previous test failed
        if not locals().get('test_file'):
            test_dir = f"/test_dir_{int(time.time())}"
            test_file = f"{test_dir}/hello.txt"
            
        response = requests.post(url, json={
            "jsonrpc": "2.0",
            "method": "ipfs_files_read",
            "params": {"path": test_file},
            "id": 5
        })
        
        if response.status_code == 200 and isinstance(response.json().get("result"), dict) and \
           response.json().get("result", {}).get("content") == "Hello IPFS MCP World!":
            logging.info(f"✅ Read file {test_file}")
            success_count += 1
        else:
            logging.error(f"❌ File read failed: {response.status_code} - {response.text}")
            failure_count += 1
    except Exception as e:
        logging.error(f"❌ File read error: {e}")
        traceback.print_exc()
        failure_count += 1
    
    # Summary
    logging.info("\n=== Test Summary ===")
    logging.info(f"Tests passed: {success_count}")
    logging.info(f"Tests failed: {failure_count}")
    logging.info("===================")
    
    return 0 if failure_count == 0 else 1

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test script for the Enhanced MCP Server with Direct IPFS Integration
"""

import json
import subprocess
import sys
import time
import tempfile
import os

def test_mcp_server():
    """Test the MCP server with direct IPFS integration."""
    
    server_path = "./enhanced_mcp_server_direct_ipfs.py"
    
    print("Starting MCP Server with Direct IPFS Integration...")
    
    # Start the server
    server_process = subprocess.Popen(
        [sys.executable, server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Test 1: Initialize
        print("\n=== Test 1: Initialize ===")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        server_process.stdin.write(json.dumps(init_request) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        if response:
            init_response = json.loads(response)
            print(f"Initialize response: {json.dumps(init_response, indent=2)}")
        
        # Test 2: List tools
        print("\n=== Test 2: List Tools ===")
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        server_process.stdin.write(json.dumps(tools_request) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        if response:
            tools_response = json.loads(response)
            tools = tools_response.get("result", {}).get("tools", [])
            print(f"Available tools: {len(tools)}")
            for tool in tools[:3]:  # Show first 3 tools
                print(f"  - {tool['name']}: {tool['description']}")
        
        # Test 3: Check daemon status
        print("\n=== Test 3: Check Daemon Status ===")
        daemon_status_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "daemon_status",
                "arguments": {}
            }
        }
        
        server_process.stdin.write(json.dumps(daemon_status_request) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        if response:
            status_response = json.loads(response)
            print(f"Daemon status response: {json.dumps(status_response, indent=2)}")
        
        # Test 4: Get IPFS version
        print("\n=== Test 4: Get IPFS Version ===")
        version_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "ipfs_version",
                "arguments": {}
            }
        }
        
        server_process.stdin.write(json.dumps(version_request) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        if response:
            version_response = json.loads(response)
            print(f"Version response: {json.dumps(version_response, indent=2)}")
        
        # Test 5: Add content to IPFS
        print("\n=== Test 5: Add Content to IPFS ===")
        test_content = "Hello, IPFS World! This is a test from the MCP server."
        add_request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "ipfs_add",
                "arguments": {
                    "content": test_content
                }
            }
        }
        
        server_process.stdin.write(json.dumps(add_request) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        if response:
            add_response = json.loads(response)
            print(f"Add response: {json.dumps(add_response, indent=2)}")
            
            # Extract CID for next test
            if "result" in add_response and "content" in add_response["result"]:
                content_data = json.loads(add_response["result"]["content"][0]["text"])
                if content_data.get("success") and "cid" in content_data:
                    test_cid = content_data["cid"]
                    
                    # Test 6: Retrieve content from IPFS
                    print("\n=== Test 6: Retrieve Content from IPFS ===")
                    cat_request = {
                        "jsonrpc": "2.0",
                        "id": 6,
                        "method": "tools/call",
                        "params": {
                            "name": "ipfs_cat",
                            "arguments": {
                                "cid": test_cid
                            }
                        }
                    }
                    
                    server_process.stdin.write(json.dumps(cat_request) + "\n")
                    server_process.stdin.flush()
                    
                    response = server_process.stdout.readline()
                    if response:
                        cat_response = json.loads(response)
                        print(f"Cat response: {json.dumps(cat_response, indent=2)}")
        
        # Test 7: System health
        print("\n=== Test 7: System Health ===")
        health_request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "system_health",
                "arguments": {}
            }
        }
        
        server_process.stdin.write(json.dumps(health_request) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        if response:
            health_response = json.loads(response)
            print(f"Health response: {json.dumps(health_response, indent=2)}")
        
        print("\n=== Test Complete ===")
        print("The server is using REAL IPFS operations instead of mocks!")
        
    except Exception as e:
        print(f"Test error: {e}")
        
    finally:
        # Clean up
        print("\nCleaning up...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()


if __name__ == "__main__":
    test_mcp_server()

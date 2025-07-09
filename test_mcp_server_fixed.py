#!/usr/bin/env python3
"""
Test script for the fixed MCP server that uses ipfs_kit_py for daemon management.
"""

import subprocess
import json
import time
import sys

def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages."""
    
    print("Starting MCP server test...")
    
    # Start the MCP server
    server_proc = subprocess.Popen(
        [sys.executable, "mcp/enhanced_mcp_server_with_daemon_mgmt.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="/home/barberb/ipfs_kit_py"
    )
    
    try:
        # Give server time to start
        time.sleep(2)
        
        # Test 1: Initialize
        print("Test 1: Sending initialize request...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {
                        "listChanged": True
                    },
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        server_proc.stdin.write(json.dumps(init_request) + "\n")
        server_proc.stdin.flush()
        
        # Read response
        response_line = server_proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"Initialize response: {response}")
        else:
            print("No response received for initialize")
        
        # Test 2: List tools
        print("Test 2: Sending tools/list request...")
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        server_proc.stdin.write(json.dumps(tools_request) + "\n")
        server_proc.stdin.flush()
        
        # Read response
        response_line = server_proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"Tools list response: {response}")
            if "result" in response and "tools" in response["result"]:
                print(f"Found {len(response['result']['tools'])} tools")
        else:
            print("No response received for tools/list")
        
        # Test 3: IPFS version
        print("Test 3: Sending ipfs_version request...")
        version_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ipfs_version",
                "arguments": {}
            }
        }
        
        server_proc.stdin.write(json.dumps(version_request) + "\n")
        server_proc.stdin.flush()
        
        # Read response
        response_line = server_proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"IPFS version response: {response}")
        else:
            print("No response received for ipfs_version")
        
        print("✓ All tests completed successfully")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    
    finally:
        # Clean up
        print("Cleaning up...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait()
        
        # Print any stderr output
        stderr_output = server_proc.stderr.read()
        if stderr_output:
            print("Server stderr output:")
            print(stderr_output)

if __name__ == "__main__":
    test_mcp_server()

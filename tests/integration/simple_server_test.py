#!/usr/bin/env python3
"""
Simple test of the production MCP server
"""

import subprocess
import json
import time

def test_server():
    print("Testing Enhanced MCP Server with Daemon Management...")
    
    # Start the server
    proc = subprocess.Popen([
        'python3', 'enhanced_mcp_server_with_daemon_mgmt.py'
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    try:
        # Test 1: Initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
        proc.stdin.write(json.dumps(init_req) + '\n')
        proc.stdin.flush()
        
        response = proc.stdout.readline()
        if response:
            data = json.loads(response.strip())
            print(f"✓ Initialize: {data.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
        
        # Test 2: Tools list
        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        proc.stdin.write(json.dumps(tools_req) + '\n')
        proc.stdin.flush()
        
        response = proc.stdout.readline()
        if response:
            data = json.loads(response.strip())
            tools = data.get('result', {}).get('tools', [])
            print(f"✓ Tools available: {len(tools)}")
            for tool in tools[:3]:  # Show first 3
                print(f"  - {tool.get('name')}")
        
        # Test 3: IPFS Version
        version_req = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ipfs_version", "arguments": {}}}
        proc.stdin.write(json.dumps(version_req) + '\n')
        proc.stdin.flush()
        
        response = proc.stdout.readline()
        if response:
            data = json.loads(response.strip())
            content = data.get('result', {}).get('content', [{}])[0].get('text', '{}')
            version_data = json.loads(content)
            print(f"✓ IPFS Version: {version_data.get('Version', 'Unknown')}")
        
        print("✓ All tests passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    test_server()

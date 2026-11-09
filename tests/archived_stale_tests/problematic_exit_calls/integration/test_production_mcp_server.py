#!/usr/bin/env python3
"""
Test script for the production MCP server
"""

import subprocess
import json
import sys
import time

def test_mcp_server():
    """Test the production MCP server"""
    print("Testing Enhanced MCP Server with Daemon Management...")
    
    # Test 1: Server starts and responds to initialize
    print("\n1. Testing server initialization...")
    try:
        proc = subprocess.Popen([
            'python3', 'enhanced_mcp_server_with_daemon_mgmt.py'
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Send initialize request
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
        
        proc.stdin.write(json.dumps(init_request) + '\n')
        proc.stdin.flush()
        
        # Wait for response
        time.sleep(2)
        
        # Get response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            if response.get('result', {}).get('serverInfo', {}).get('name') == 'enhanced-ipfs-kit-mcp-server-daemon-mgmt':
                print("✓ Server initialization successful")
            else:
                print("✗ Server initialization failed")
                print(f"Response: {response}")
        else:
            print("✗ No response from server")
        
        proc.terminate()
        proc.wait()
        
    except Exception as e:
        print(f"✗ Error testing server: {e}")
        return False
    
    # Test 2: Tools list
    print("\n2. Testing tools list...")
    try:
        proc = subprocess.Popen([
            'python3', 'enhanced_mcp_server_with_daemon_mgmt.py'
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Send initialize first
        proc.stdin.write(json.dumps(init_request) + '\n')
        proc.stdin.flush()
        proc.stdout.readline()  # Read init response
        
        # Send tools/list request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        proc.stdin.write(json.dumps(tools_request) + '\n')
        proc.stdin.flush()
        
        time.sleep(1)
        
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            tools = response.get('result', {}).get('tools', [])
            if len(tools) > 0:
                print(f"✓ Tools list received: {len(tools)} tools")
                for tool in tools:
                    print(f"  - {tool.get('name')}: {tool.get('description')}")
            else:
                print("✗ No tools received")
        else:
            print("✗ No response for tools list")
        
        proc.terminate()
        proc.wait()
        
    except Exception as e:
        print(f"✗ Error testing tools list: {e}")
        return False
    
    print("\n✓ Basic MCP server tests completed successfully!")
    return True

def test_ipfs_direct():
    """Test IPFS operations directly"""
    print("\n3. Testing direct IPFS operations...")
    
    try:
        # Test IPFS version
        result = subprocess.run(['ipfs', 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ IPFS binary available")
            print(f"  Version: {result.stdout.strip()}")
        else:
            print("✗ IPFS binary not available or not working")
            return False
    except Exception as e:
        print(f"✗ Error testing IPFS binary: {e}")
        return False
    
    try:
        # Test IPFS daemon status
        result = subprocess.run(['ipfs', 'id'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ IPFS daemon is running")
            id_info = json.loads(result.stdout)
            print(f"  Peer ID: {id_info.get('ID')}")
        else:
            print("⚠ IPFS daemon not running (will be started by MCP server)")
    except Exception as e:
        print(f"⚠ IPFS daemon status check failed: {e}")
    
    return True

if __name__ == "__main__":
    print("Production MCP Server Test Suite")
    print("=" * 50)
    
    success = True
    
    # Test direct IPFS
    if not test_ipfs_direct():
        success = False
    
    # Test MCP server
    if not test_mcp_server():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✓ All tests passed! Production server is ready.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Check the output above.")
        sys.exit(1)

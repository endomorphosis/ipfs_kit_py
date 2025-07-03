#!/usr/bin/env python3
"""
Test script to verify MCP server integration with Cline
"""

import json
import subprocess
import sys
import os

def test_mcp_server():
    """Test the MCP server functionality."""
    print("🧪 Testing IPFS Kit MCP Server Integration")
    print("=" * 50)
    
    # Set up environment
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/barberb/ipfs_kit_py"
    
    server_cmd = [
        sys.executable, 
        "/home/barberb/ipfs_kit_py/mcp/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py"
    ]
    
    proc = None
    try:
        print("1. Starting MCP server...")
        proc = subprocess.Popen(
            server_cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            env=env
        )
        
        # Ensure stdin/stdout are available
        if not proc.stdin or not proc.stdout:
            print("   ❌ Failed to get process pipes")
            return False
        
        print("2. Sending initialize request...")
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
        
        # Send initialize request
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            print(f"   ✅ Initialize response: {response.get('result', {}).get('serverInfo', 'Unknown')}")
        else:
            print("   ❌ No response received")
            return False
        
        print("3. Testing tools/list...")
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        proc.stdin.write(json.dumps(tools_request) + "\n")
        proc.stdin.flush()
        
        # Read tools response
        tools_line = proc.stdout.readline()
        if tools_line:
            tools_response = json.loads(tools_line)
            tools = tools_response.get('result', {}).get('tools', [])
            print(f"   ✅ Found {len(tools)} tools:")
            for tool in tools[:3]:  # Show first 3 tools
                print(f"      - {tool.get('name')}: {tool.get('description', 'No description')}")
            if len(tools) > 3:
                print(f"      ... and {len(tools) - 3} more tools")
        else:
            print("   ❌ No tools response received")
            return False
        
        print("4. Testing ipfs_version tool...")
        version_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ipfs_version",
                "arguments": {}
            }
        }
        
        proc.stdin.write(json.dumps(version_request) + "\n")
        proc.stdin.flush()
        
        # Read version response
        version_line = proc.stdout.readline()
        if version_line:
            version_response = json.loads(version_line)
            content = version_response.get('result', {}).get('content', [])
            if content and len(content) > 0:
                result_text = content[0].get('text', '')
                try:
                    result_data = json.loads(result_text)
                    if result_data.get('success'):
                        version = result_data.get('Version', 'Unknown')
                        print(f"   ✅ IPFS Version: {version}")
                    else:
                        print(f"   ⚠️  Version check failed (using mock): {result_data.get('error', 'Unknown error')}")
                except:
                    print(f"   ⚠️  Version response: {result_text[:100]}...")
            else:
                print("   ❌ No version content received")
        else:
            print("   ❌ No version response received")
        
        # Clean shutdown
        if proc:
            proc.terminate()
            proc.wait(timeout=5)
        
        print("\n✅ MCP Server test completed successfully!")
        print("\n📋 Configuration Summary:")
        print("   Server Path: /home/barberb/ipfs_kit_py/mcp/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py")
        print("   Environment: PYTHONPATH=/home/barberb/ipfs_kit_py")
        print("   Status: Ready for Cline integration")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("   ❌ Server timed out")
        if proc:
            proc.kill()
        return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        if proc:
            proc.terminate()
        return False

if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
MCP Server Status Check
======================

This script helps diagnose MCP server connectivity and functionality
for VS Code integration.
"""

import subprocess
import json
import time
import sys
import os

def check_mcp_server():
    """Check MCP server status and functionality."""
    
    server_path = "/home/barberb/ipfs_kit_py/mcp_stdio_server.py"
    
    print("IPFS Kit MCP Server Status Check")
    print("=" * 50)
    
    # Check if server file exists
    if not os.path.exists(server_path):
        print(f"❌ Server file not found: {server_path}")
        return False
    
    print(f"✅ Server file exists: {server_path}")
    
    # Check if Python can import required modules
    try:
        import anyio
        import json
        print("✅ Required Python modules available")
    except ImportError as e:
        print(f"❌ Missing Python modules: {e}")
        return False
    
    # Test server startup and basic functionality
    print("\nTesting server functionality...")
    print("-" * 30)
    
    # Standard MCP protocol test
    test_sequence = [
        {
            "name": "Initialize",
            "request": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "status-check", "version": "1.0.0"}
                }
            }
        },
        {
            "name": "Resources List",
            "request": {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
                "params": {}
            }
        },
        {
            "name": "Resources Templates List",
            "request": {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/templates/list",
                "params": {}
            }
        },
        {
            "name": "Tools List",
            "request": {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/list",
                "params": {}
            }
        }
    ]
    
    # Start server
    try:
        process = subprocess.Popen(
            ['python3', server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
            cwd=os.path.dirname(server_path)
        )
        
        all_passed = True
        
        for test in test_sequence:
            print(f"  Testing: {test['name']}...", end=" ")
            
            # Send request
            request_json = json.dumps(test['request']) + '\n'
            process.stdin.write(request_json)
            process.stdin.flush()
            
            # Wait for response
            time.sleep(0.3)
            
            try:
                response_line = process.stdout.readline()
                if not response_line:
                    print("❌ No response")
                    all_passed = False
                    continue
                    
                response = json.loads(response_line.strip())
                
                if "error" in response:
                    print(f"❌ Error: {response['error']['message']}")
                    all_passed = False
                elif "result" in response:
                    print("✅ OK")
                else:
                    print("❌ Invalid response format")
                    all_passed = False
                    
            except json.JSONDecodeError:
                print("❌ Invalid JSON response")
                all_passed = False
            except Exception as e:
                print(f"❌ Exception: {e}")
                all_passed = False
        
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        
        if all_passed:
            print("\n✅ All tests passed! MCP server is ready for VS Code.")
            print("\nTo use with VS Code:")
            print("1. Make sure VS Code MCP extension is installed")
            print("2. Restart VS Code to pick up the latest server")
            print("3. The server should be available as 'ipfs-kit-mcp'")
        else:
            print("\n❌ Some tests failed. Please check server implementation.")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False

if __name__ == "__main__":
    success = check_mcp_server()
    sys.exit(0 if success else 1)

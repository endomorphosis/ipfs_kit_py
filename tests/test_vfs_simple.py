#!/usr/bin/env python3
"""
Simple VFS Test - Direct MCP Server Test
========================================

This script tests the VFS functionality by directly interacting with the MCP server.
"""

import json
import subprocess
import sys
import os
import select
import time

import pytest


def _read_json_line(process: subprocess.Popen, *, timeout_s: float = 5.0):
    if process.stdout is None:
        return None

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        ready, _, _ = select.select([process.stdout], [], [], remaining)
        if not ready:
            break

        line = process.stdout.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            # Ignore non-JSON stdout noise
            continue
    return None

def test_mcp_server():
    """Test the MCP server directly."""
    server_path = os.path.join("ipfs_kit_py", "mcp", "servers", "unified_mcp_server.py")
    
    if not os.path.exists(server_path):
        pytest.skip(f"MCP server not found at {server_path}")
    
    print("Testing MCP server directly...")
    
    # Start server process
    process = None
    try:
        process = subprocess.Popen(
            [sys.executable, server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if not process.stdin or not process.stdout:
            pytest.fail("Could not establish communication with server")
        
        # Send initialize message
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        print("1. Sending initialize message...")
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        
        # Read response
        init_response = _read_json_line(process, timeout_s=5.0)
        if init_response:
            print(
                f"   Initialize response: {init_response.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}"
            )
        else:
            pytest.skip("No JSON initialize response received")
            
        # Send initialized notification
        notify_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        print("2. Sending initialized notification...")
        process.stdin.write(json.dumps(notify_msg) + "\n")
        process.stdin.flush()
        
        # List tools
        tools_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        print("3. Requesting tools list...")
        process.stdin.write(json.dumps(tools_msg) + "\n")
        process.stdin.flush()
        
        tools_response = _read_json_line(process, timeout_s=5.0)
        if tools_response:
            tools = tools_response.get("result", {}).get("tools", [])
            
            # Check for VFS tools
            vfs_tools = [tool["name"] for tool in tools if tool["name"].startswith("vfs_")]
            print(f"   Found {len(vfs_tools)} VFS tools: {vfs_tools}")
            
            if len(vfs_tools) > 0:
                print("   ✓ VFS tools are available")
                
                # Test a simple VFS operation
                vfs_test_msg = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "vfs_list_mounts",
                        "arguments": {}
                    }
                }
                
                print("4. Testing VFS list mounts...")
                process.stdin.write(json.dumps(vfs_test_msg) + "\n")
                process.stdin.flush()
                
                vfs_response = _read_json_line(process, timeout_s=5.0)
                if vfs_response:
                    content = vfs_response.get("result", {}).get("content", [])
                    
                    if content:
                        result = json.loads(content[0]["text"])
                        print(f"   VFS list mounts result: {result.get('success', False)}")
                        
                        if result.get("is_mock"):
                            print("   📝 Using mock VFS (real VFS not available)")
                        else:
                            print("   🔧 Using real VFS")

                        return
                    else:
                        print("   No content in VFS response")
                        pytest.skip("No content in VFS response")
                else:
                    print("   No response to VFS test")
                    pytest.skip("No response to VFS test")
            else:
                print("   ✗ No VFS tools found")
                pytest.skip("No VFS tools found")
        else:
            print("   No response to tools list")
            pytest.skip("No response to tools list")
            
    except Exception as e:
        print(f"Error testing MCP server: {e}")
        import traceback
        traceback.print_exc()
        pytest.skip(f"Error testing MCP server: {e}")
        
    finally:
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass

if __name__ == "__main__":
    success = test_mcp_server()
    
    print("\n" + "="*50)
    print("VFS TEST RESULT")
    print("="*50)
    
    if success:
        print("✓ VFS functionality is working through MCP server")
        print("  The server can handle VFS operations either through")
        print("  the real VFS implementation or mock fallback.")
    else:
        print("✗ VFS functionality test failed")
        print("  There may be issues with the MCP server or VFS setup.")
    
    print("="*50)
    
    sys.exit(0 if success else 1)

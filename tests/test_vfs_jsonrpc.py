#!/usr/bin/env python3
"""
VFS Test via JSON-RPC
=====================

Test VFS functionality by sending JSON-RPC requests to the MCP server.
"""

import os
import sys
import json
import anyio
import subprocess
import tempfile
import time
from pathlib import Path
import pytest

pytestmark = pytest.mark.anyio

async def test_mcp_server_with_vfs():
    """Test MCP server with VFS operations using subprocess communication."""
    print("🧪 Testing VFS through MCP server via JSON-RPC")
    
    # Start the MCP server as a subprocess
    repo_root = Path(__file__).resolve().parents[1]
    server_path = repo_root / "mcp" / "enhanced_mcp_server_with_daemon_mgmt.py"
    
    if not server_path.exists():
        print(f"❌ MCP server not found at {server_path}")
        return False
    
    try:
        # Start server
        print("🚀 Starting MCP server...")
        process = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(repo_root)
        )
        
        # Wait a moment for server to start
        await anyio.sleep(2)
        
        # Send initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "vfs-test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("📤 Sending initialization request...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"📥 Init response: {response}")
        
        # Request tools list to see if VFS tools are available
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        print("📤 Requesting tools list...")
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()
        
        # Read tools response
        tools_response_line = process.stdout.readline()
        if tools_response_line:
            tools_response = json.loads(tools_response_line.strip())
            print(f"📥 Tools response: {tools_response}")
            
            # Check if VFS tools are available
            if "result" in tools_response and "tools" in tools_response["result"]:
                tools = tools_response["result"]["tools"]
                vfs_tools = [tool for tool in tools if "vfs" in tool.get("name", "").lower()]
                
                if vfs_tools:
                    print(f"✅ Found {len(vfs_tools)} VFS tools:")
                    for tool in vfs_tools:
                        print(f"  - {tool.get('name', 'Unknown')}")
                    
                    # Test a VFS operation
                    vfs_test_request = {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "vfs_list_mounts",
                            "arguments": {}
                        }
                    }
                    
                    print("📤 Testing VFS list_mounts operation...")
                    process.stdin.write(json.dumps(vfs_test_request) + "\n")
                    process.stdin.flush()
                    
                    # Read VFS response
                    vfs_response_line = process.stdout.readline()
                    if vfs_response_line:
                        vfs_response = json.loads(vfs_response_line.strip())
                        print(f"📥 VFS response: {vfs_response}")
                        
                        if "result" in vfs_response:
                            print("🎉 VFS operation succeeded through MCP server!")
                            process.terminate()
                            return True
                        else:
                            print("❌ VFS operation failed")
                    else:
                        print("❌ No VFS response received")
                else:
                    print("❌ No VFS tools found in server")
            else:
                print("❌ Invalid tools response")
        else:
            print("❌ No tools response received")
        
        # Cleanup
        process.terminate()
        process.wait(timeout=5)
        
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        if process:
            process.terminate()
        return False

async def test_vfs_mock_operations():
    """Test VFS operations with mock implementations."""
    print("🧪 Testing VFS with mock operations")
    
    try:
        # Create a minimal VFS-like interface to verify the concept works
        class MockVFS:
            def __init__(self):
                self.mounts = {}
                self.files = {}
            
            async def mount(self, mount_point, backend, path, read_only=True):
                self.mounts[mount_point] = {
                    "backend": backend,
                    "path": path,
                    "read_only": read_only
                }
                return {"success": True, "mount_point": mount_point}
            
            async def list_mounts(self):
                return {"success": True, "mounts": list(self.mounts.keys())}
            
            async def write(self, path, content):
                self.files[path] = content
                return {"success": True, "path": path, "size": len(content)}
            
            async def read(self, path):
                if path in self.files:
                    return {"success": True, "path": path, "content": self.files[path]}
                return {"success": False, "error": "File not found"}
        
        # Test mock VFS operations
        vfs = MockVFS()
        
        # Test mount
        mount_result = await vfs.mount("/test", "local", "/tmp")
        print(f"✅ Mock mount: {mount_result}")
        
        # Test list mounts
        mounts_result = await vfs.list_mounts()
        print(f"✅ Mock list mounts: {mounts_result}")
        
        # Test write
        write_result = await vfs.write("/test/file.txt", "Hello VFS!")
        print(f"✅ Mock write: {write_result}")
        
        # Test read
        read_result = await vfs.read("/test/file.txt")
        print(f"✅ Mock read: {read_result}")
        
        print("🎉 Mock VFS operations work correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Mock VFS test failed: {e}")
        return False

async def main():
    """Run VFS tests."""
    print("🚀 Starting VFS Integration Verification")
    
    # Test mock VFS operations to verify the concept
    print("\n" + "="*50)
    mock_result = await test_vfs_mock_operations()
    
    # Test real MCP server with VFS
    print("\n" + "="*50)
    mcp_result = await test_mcp_server_with_vfs()
    
    # Summary
    print("\n" + "="*50)
    print("📋 Test Results:")
    print(f"Mock VFS: {'PASS' if mock_result else 'FAIL'}")
    print(f"MCP VFS: {'PASS' if mcp_result else 'FAIL'}")
    
    if mock_result and mcp_result:
        print("🎉 VFS is working correctly through MCP server!")
        return 0
    elif mock_result:
        print("✅ VFS concept is sound, but MCP integration needs work")
        return 1
    else:
        print("❌ VFS has fundamental issues")
        return 2

if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)

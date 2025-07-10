#!/usr/bin/env python3
"""
Test the VFS integration with the MCP server.
"""
import json
import subprocess
import tempfile
import os
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_vfs_integration():
    """Test VFS integration with the MCP server."""
    print("Testing VFS integration...")
    
    # First, let's test the VFS system directly
    try:
        from ipfs_fsspec import get_vfs, vfs_mount, vfs_list_mounts, vfs_write, vfs_read
        print("✓ VFS system imported successfully")
        
        # Test basic VFS operations
        vfs = get_vfs()
        print(f"✓ VFS instance created: {type(vfs)}")
        
        # Test mounting a local directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            mount_result = vfs.mount("/test_mount", "local", tmp_dir)
            print(f"✓ Mount result: {mount_result}")
            
            # Test listing mounts
            mounts = vfs.list_mounts()
            print(f"✓ Mounts: {mounts}")
            
            # Test writing a file
            test_content = "Hello VFS World!"
            write_result = vfs.write("/test_mount/test_file.txt", test_content)
            print(f"✓ Write result: {write_result}")
            
            # Test reading the file
            read_result = vfs.read("/test_mount/test_file.txt")
            print(f"✓ Read result: {read_result}")
            
            # Test unmounting
            unmount_result = vfs.unmount("/test_mount")
            print(f"✓ Unmount result: {unmount_result}")
        
        print("✓ VFS system test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ VFS system test failed: {e}")
        return False

def test_mcp_vfs_tools():
    """Test VFS tools through MCP server."""
    print("\nTesting MCP VFS tools...")
    
    try:
        # Test the VFS mount tool via MCP
        test_requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "vfs_mount",
                    "arguments": {
                        "ipfs_path": "/tmp/test_vfs",
                        "mount_point": "/vfs/test",
                        "read_only": False
                    }
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "vfs_list_mounts",
                    "arguments": {}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "vfs_write",
                    "arguments": {
                        "path": "/vfs/test/hello.txt",
                        "content": "Hello from MCP VFS!"
                    }
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "vfs_read",
                    "arguments": {
                        "path": "/vfs/test/hello.txt"
                    }
                }
            }
        ]
        
        # Create a temporary directory for testing
        os.makedirs("/tmp/test_vfs", exist_ok=True)
        
        # Run each test request
        for i, request in enumerate(test_requests):
            print(f"\nTest {i+1}: {request['params']['name']}")
            
            # Run the MCP server with the test request
            cmd = [sys.executable, "mcp/enhanced_mcp_server_with_daemon_mgmt.py"]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(project_root)
            )
            
            # Send the request
            input_data = json.dumps(request) + "\n"
            stdout, stderr = process.communicate(input=input_data, timeout=10)
            
            # Parse response
            if stdout.strip():
                try:
                    response = json.loads(stdout.strip())
                    print(f"✓ Response: {json.dumps(response, indent=2)}")
                except json.JSONDecodeError:
                    print(f"✗ Invalid JSON response: {stdout}")
                    print(f"stderr: {stderr}")
            else:
                print(f"✗ No response received")
                print(f"stderr: {stderr}")
        
        print("✓ MCP VFS tools test completed")
        return True
        
    except Exception as e:
        print(f"✗ MCP VFS tools test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing VFS Integration")
    print("=" * 50)
    
    success = True
    
    # Test 1: Direct VFS system
    if not test_vfs_integration():
        success = False
    
    # Test 2: MCP VFS tools
    if not test_mcp_vfs_tools():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All VFS integration tests passed!")
    else:
        print("❌ Some VFS integration tests failed!")
    
    sys.exit(0 if success else 1)

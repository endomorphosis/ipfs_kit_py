#!/usr/bin/env python3
"""
Simple test of VFS functionality without MCP server process.
"""
import json
import tempfile
import os
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_vfs_operations():
    """Test VFS operations directly."""
    print("Testing VFS operations...")
    
    try:
        from ipfs_fsspec import get_vfs
        print("✓ VFS system imported successfully")
        
        # Test basic VFS operations
        vfs = get_vfs()
        print(f"✓ VFS instance created: {type(vfs)}")
        
        # Test mounting a local directory with write access
        with tempfile.TemporaryDirectory() as tmp_dir:
            mount_result = vfs.mount("/test_mount", "local", tmp_dir, read_only=False)
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
            
            # Test listing directory contents
            ls_result = vfs.ls("/test_mount")
            print(f"✓ List result: {ls_result}")
            
            # Test file stat
            stat_result = vfs.stat("/test_mount/test_file.txt")
            print(f"✓ Stat result: {stat_result}")
            
            # Test mkdir
            mkdir_result = vfs.mkdir("/test_mount/subdir")
            print(f"✓ Mkdir result: {mkdir_result}")
            
            # Test copy
            copy_result = vfs.copy("/test_mount/test_file.txt", "/test_mount/test_file_copy.txt")
            print(f"✓ Copy result: {copy_result}")
            
            # Test move
            move_result = vfs.move("/test_mount/test_file_copy.txt", "/test_mount/subdir/moved_file.txt")
            print(f"✓ Move result: {move_result}")
            
            # Test ls with details
            ls_detailed = vfs.ls("/test_mount", detailed=True)
            print(f"✓ Detailed list result: {ls_detailed}")
            
            # Test unmounting
            unmount_result = vfs.unmount("/test_mount")
            print(f"✓ Unmount result: {unmount_result}")
        
        print("✓ All VFS operations test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ VFS operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vfs_async_functions():
    """Test VFS async functions."""
    print("\nTesting VFS async functions...")
    
    try:
        import asyncio
        from ipfs_fsspec import vfs_mount, vfs_list_mounts, vfs_write, vfs_read, vfs_ls, vfs_stat, vfs_unmount
        
        async def async_test():
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Test async mount
                mount_result = await vfs_mount(tmp_dir, "/async_test", read_only=False)
                print(f"✓ Async mount result: {mount_result}")
                
                # Test async list mounts
                mounts = await vfs_list_mounts()
                print(f"✓ Async mounts: {mounts}")
                
                # Test async write
                write_result = await vfs_write("/async_test/async_file.txt", "Hello async VFS!")
                print(f"✓ Async write result: {write_result}")
                
                # Test async read
                read_result = await vfs_read("/async_test/async_file.txt")
                print(f"✓ Async read result: {read_result}")
                
                # Test async ls
                ls_result = await vfs_ls("/async_test")
                print(f"✓ Async ls result: {ls_result}")
                
                # Test async stat
                stat_result = await vfs_stat("/async_test/async_file.txt")
                print(f"✓ Async stat result: {stat_result}")
                
                # Test async unmount
                unmount_result = await vfs_unmount("/async_test")
                print(f"✓ Async unmount result: {unmount_result}")
        
        # Run async test
        asyncio.run(async_test())
        
        print("✓ All VFS async functions test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ VFS async functions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vfs_integration_with_mcp():
    """Test VFS integration with MCP server components."""
    print("\nTesting VFS integration with MCP components...")
    
    try:
        # Import the MCP server class
        from mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
        
        # Create an instance
        ipfs_integration = IPFSKitIntegration()
        
        # Test VFS operations through the integration layer
        import asyncio
        
        async def integration_test():
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Test VFS mount
                mount_result = await ipfs_integration.execute_ipfs_operation(
                    "vfs_mount", 
                    ipfs_path=tmp_dir, 
                    mount_point="/integration_test",
                    read_only=False
                )
                print(f"✓ Integration mount result: {mount_result}")
                
                # Test VFS write
                write_result = await ipfs_integration.execute_ipfs_operation(
                    "vfs_write",
                    path="/integration_test/integration_file.txt",
                    content="Hello integration!"
                )
                print(f"✓ Integration write result: {write_result}")
                
                # Test VFS read
                read_result = await ipfs_integration.execute_ipfs_operation(
                    "vfs_read",
                    path="/integration_test/integration_file.txt"
                )
                print(f"✓ Integration read result: {read_result}")
                
                # Test VFS list
                ls_result = await ipfs_integration.execute_ipfs_operation(
                    "vfs_ls",
                    path="/integration_test"
                )
                print(f"✓ Integration ls result: {ls_result}")
                
                # Test VFS unmount
                unmount_result = await ipfs_integration.execute_ipfs_operation(
                    "vfs_unmount",
                    mount_point="/integration_test"
                )
                print(f"✓ Integration unmount result: {unmount_result}")
        
        # Run integration test
        asyncio.run(integration_test())
        
        print("✓ VFS integration with MCP test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ VFS integration with MCP test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Testing VFS System")
    print("=" * 50)
    
    success = True
    
    # Test 1: Direct VFS operations
    if not test_vfs_operations():
        success = False
    
    # Test 2: VFS async functions
    if not test_vfs_async_functions():
        success = False
    
    # Test 3: VFS integration with MCP
    if not test_vfs_integration_with_mcp():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All VFS tests passed!")
    else:
        print("❌ Some VFS tests failed!")
    
    sys.exit(0 if success else 1)

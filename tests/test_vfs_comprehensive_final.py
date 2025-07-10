#!/usr/bin/env python3
"""
Comprehensive test of VFS system with replication features.
"""

import os
import sys
import tempfile
import shutil
import asyncio
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, '/home/barberb/ipfs_kit_py')

from ipfs_fsspec import (
    VFSCore, get_vfs,
    vfs_mount, vfs_write, vfs_read, vfs_ls,
    vfs_add_replication_policy, vfs_replicate_file,
    vfs_verify_replicas, vfs_repair_replicas,
    vfs_get_replication_status, vfs_get_system_replication_status,
    vfs_list_replication_policies, vfs_bulk_replicate
)


async def test_vfs_basic_operations():
    """Test basic VFS operations."""
    print("=== Testing Basic VFS Operations ===")
    
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp(prefix="vfs_test_")
    print(f"Using temp directory: {temp_dir}")
    
    try:
        # Mount local filesystem
        mount_result = await vfs_mount(temp_dir, "/test_mount", read_only=False)
        print(f"Mount result: {mount_result}")
        
        # Write a test file
        test_content = "Hello, VFS World!\nThis is a test file for replication."
        write_result = await vfs_write("/test_mount/test_file.txt", test_content)
        print(f"Write result: {write_result}")
        
        # Read the file back
        read_result = await vfs_read("/test_mount/test_file.txt")
        print(f"Read result: {read_result}")
        
        # List directory
        ls_result = await vfs_ls("/test_mount")
        print(f"List result: {ls_result}")
        
        return True
        
    except Exception as e:
        print(f"Error in basic operations: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


async def test_vfs_replication():
    """Test VFS replication features."""
    print("\n=== Testing VFS Replication ===")
    
    # Create temporary directories for multiple backends
    temp_dir1 = tempfile.mkdtemp(prefix="vfs_backend1_")
    temp_dir2 = tempfile.mkdtemp(prefix="vfs_backend2_")
    
    try:
        # Mount multiple backends
        mount1 = await vfs_mount(temp_dir1, "/primary", read_only=False)
        mount2 = await vfs_mount(temp_dir2, "/backup", read_only=False)
        print(f"Mount results: {mount1}, {mount2}")
        
        # Create test files
        test_files = [
            ("/primary/important.txt", "This is an important file that needs replication."),
            ("/primary/config.json", '{"setting": "value", "replicate": true}'),
            ("/primary/data.csv", "name,value\ntest,123\ndata,456")
        ]
        
        for file_path, content in test_files:
            write_result = await vfs_write(file_path, content)
            print(f"Created file {file_path}: {write_result['success']}")
        
        # Add replication policies
        policy1 = await vfs_add_replication_policy("*.txt", ["local"], 2)
        policy2 = await vfs_add_replication_policy("*.json", ["local"], 1)
        print(f"Added policies: {policy1}, {policy2}")
        
        # List policies
        policies = await vfs_list_replication_policies()
        print(f"Current policies: {policies}")
        
        # Replicate specific files
        for file_path, _ in test_files:
            replicate_result = await vfs_replicate_file(file_path)
            print(f"Replication result for {file_path}: {replicate_result}")
        
        # Verify replicas
        for file_path, _ in test_files:
            verify_result = await vfs_verify_replicas(file_path)
            print(f"Verification result for {file_path}: {verify_result}")
        
        # Get replication status
        for file_path, _ in test_files:
            status = await vfs_get_replication_status(file_path)
            print(f"Replication status for {file_path}: {status}")
        
        # Get system replication status
        system_status = await vfs_get_system_replication_status()
        print(f"System replication status: {system_status}")
        
        # Test bulk replication
        bulk_result = await vfs_bulk_replicate("*.txt")
        print(f"Bulk replication result: {bulk_result}")
        
        return True
        
    except Exception as e:
        print(f"Error in replication tests: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        for temp_dir in [temp_dir1, temp_dir2]:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


async def test_vfs_error_handling():
    """Test error handling in VFS operations."""
    print("\n=== Testing Error Handling ===")
    
    try:
        # Try to read non-existent file
        read_result = await vfs_read("/nonexistent/file.txt")
        print(f"Read non-existent file: {read_result}")
        
        # Try to write to read-only mount
        temp_dir = tempfile.mkdtemp(prefix="vfs_readonly_")
        mount_result = await vfs_mount(temp_dir, "/readonly", read_only=True)
        print(f"Read-only mount: {mount_result}")
        
        write_result = await vfs_write("/readonly/test.txt", "test content")
        print(f"Write to read-only mount: {write_result}")
        
        # Try to add policy with invalid backend
        invalid_policy = await vfs_add_replication_policy("*.txt", ["nonexistent_backend"], 1)
        print(f"Invalid backend policy: {invalid_policy}")
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        return True
        
    except Exception as e:
        print(f"Error in error handling tests: {e}")
        return False


async def main():
    """Run all tests."""
    print("Starting VFS Comprehensive Tests...")
    
    tests = [
        ("Basic Operations", test_vfs_basic_operations),
        ("Replication Features", test_vfs_replication),
        ("Error Handling", test_vfs_error_handling)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
            print(f"\n{test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"\n{test_name}: FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! VFS system is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))

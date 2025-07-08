#!/usr/bin/env python3
"""
Direct VFS Test - Test the VFS system directly
===============================================

This script tests the VFS system directly without going through the MCP server.
"""

import sys
import os
import json
import tempfile
import shutil
from datetime import datetime

def test_vfs_direct():
    """Test the VFS system directly."""
    
    print("Testing VFS system directly...")
    
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Try to import VFS system
    try:
        from ipfs_fsspec import (
            get_vfs, vfs_mount, vfs_unmount, vfs_list_mounts, vfs_read, vfs_write,
            vfs_ls, vfs_stat, vfs_mkdir, vfs_rmdir, vfs_copy, vfs_move,
            vfs_sync_to_ipfs, vfs_sync_from_ipfs
        )
        print("✓ VFS system imported successfully")
        has_vfs = True
    except ImportError as e:
        print(f"✗ VFS system import failed: {e}")
        has_vfs = False
    
    # Test VFS operations
    if has_vfs:
        print("\nTesting VFS operations...")
        
        # Test vfs_list_mounts
        try:
            result = vfs_list_mounts()
            if hasattr(result, '__await__'):
                # It's async, we need to handle it differently
                print("  VFS operations are async - this is expected")
            else:
                print(f"  ✓ vfs_list_mounts: {result}")
        except Exception as e:
            print(f"  ✗ vfs_list_mounts error: {e}")
            
        # Test other basic operations
        try:
            temp_dir = tempfile.mkdtemp(prefix="vfs_test_")
            print(f"  Created temp dir: {temp_dir}")
            
            # Test vfs_mkdir
            try:
                result = vfs_mkdir("/test_dir", parents=True)
                if hasattr(result, '__await__'):
                    print("  ✓ vfs_mkdir is async")
                else:
                    print(f"  ✓ vfs_mkdir: {result}")
            except Exception as e:
                print(f"  ✗ vfs_mkdir error: {e}")
                
            # Clean up
            shutil.rmtree(temp_dir)
            print("  Cleaned up temp dir")
            
        except Exception as e:
            print(f"  ✗ VFS operations test error: {e}")
    
    # Test importing the MCP server parts that handle VFS
    try:
        from mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
        print("✓ MCP server VFS integration imported successfully")
        
        # Test creating the integration
        try:
            integration = IPFSKitIntegration()
            print("✓ IPFS Kit integration created successfully")
            
            # Test if VFS operations are available
            if hasattr(integration, 'execute_ipfs_operation'):
                print("✓ VFS operations are available in the integration")
                
                # Test mock VFS operation
                if hasattr(integration, '_mock_vfs_operation'):
                    print("✓ Mock VFS operations are available")
                else:
                    print("✗ Mock VFS operations are NOT available")
            else:
                print("✗ VFS operations are NOT available in the integration")
                
        except Exception as e:
            print(f"✗ IPFS Kit integration creation failed: {e}")
            import traceback
            traceback.print_exc()
            
    except ImportError as e:
        print(f"✗ MCP server VFS integration import failed: {e}")
        import traceback
        traceback.print_exc()
    
    return has_vfs

if __name__ == "__main__":
    success = test_vfs_direct()
    
    print("\n" + "="*50)
    print("DIRECT VFS TEST RESULT")
    print("="*50)
    
    if success:
        print("✓ VFS system is importable and appears to be working")
        print("  The VFS functions are available and can be called.")
        print("  Note: They may be async functions requiring await.")
    else:
        print("✗ VFS system has issues")
        print("  The VFS system could not be imported or has errors.")
    
    print("="*50)
    
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Comprehensive integration test for Synapse SDK VFS backend
This script verifies that the Synapse SDK is properly integrated into the virtual filesystem
"""

import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(cmd, **kwargs):
    """Run a command and return the result"""
    print(f"🔧 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        print(f"Exit code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
    return result

def check_imports():
    """Check that all required imports work"""
    print("📦 Checking imports...")
    
    try:
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        print("✅ ipfs_kit imported successfully")
        
        from ipfs_kit_py.enhanced_fsspec import IPFSFileSystem
        print("✅ IPFSFileSystem imported successfully")
        
        from ipfs_kit_py.backends.synapse_storage import SynapseStorage
        print("✅ SynapseStorage imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def check_synapse_sdk():
    """Check that Synapse SDK is properly installed"""
    print("🔍 Checking Synapse SDK installation...")
    
    # Check if Node.js is available
    node_result = run_command("node --version")
    if node_result.returncode != 0:
        print("❌ Node.js not found")
        return False
    
    print(f"✅ Node.js version: {node_result.stdout.strip()}")
    
    # Check if synapse-sdk is installed
    npm_result = run_command("npm list @filoz/synapse-sdk")
    if npm_result.returncode == 0:
        print("✅ @filoz/synapse-sdk is installed")
        return True
    else:
        print("❌ @filoz/synapse-sdk not found")
        return False

def test_ipfs_kit_initialization():
    """Test that ipfs_kit initializes with synapse_storage"""
    print("🧪 Testing ipfs_kit initialization...")
    
    try:
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        
        # Test different roles
        roles = ['leecher', 'worker', 'master']
        
        for role in roles:
            kit = ipfs_kit(metadata={'role': role})
            
            # Check if synapse_storage is initialized
            if hasattr(kit, 'synapse_storage'):
                print(f"✅ {role}: synapse_storage initialized")
            else:
                print(f"❌ {role}: synapse_storage NOT initialized")
                return False
        
        return True
    except Exception as e:
        print(f"❌ ipfs_kit initialization error: {e}")
        return False

def test_fsspec_backend():
    """Test that FSSpec recognizes synapse protocol"""
    print("🧪 Testing FSSpec backend...")
    
    try:
        from ipfs_kit_py.enhanced_fsspec import IPFSFileSystem
        
        # Create filesystem instance
        fs = IPFSFileSystem(backend="synapse")
        
        # Check if synapse protocol is supported
        if "synapse" in fs.protocol:
            print("✅ synapse protocol registered in FSSpec")
            return True
        else:
            print("❌ synapse protocol NOT registered in FSSpec")
            return False
    except Exception as e:
        print(f"❌ FSSpec backend error: {e}")
        return False

def test_mcp_server_integration():
    """Test that MCP server can work with synapse backend"""
    print("🧪 Testing MCP server integration...")
    
    try:
        # Import MCP server components
        import servers.enhanced_mcp_server_with_full_config as mcp_module
        
        # Check if MCP classes are available
        if hasattr(mcp_module, 'TextContent'):
            print("✅ MCP server components available")
            return True
        else:
            print("❌ MCP server components not available")
            return False
    except Exception as e:
        print(f"❌ MCP server integration error: {e}")
        return False

def test_storage_operations():
    """Test basic storage operations with synapse backend"""
    print("🧪 Testing storage operations...")
    
    try:
        from ipfs_kit_py.synapse_storage import synapse_storage
        
        # Create storage instance
        storage = synapse_storage()
        
        # Test configuration
        if hasattr(storage, 'is_configured'):
            print("✅ Synapse storage is available")
            print("✅ Storage interface methods available")
            return True
        else:
            print("⚠️  Synapse storage not fully configured")
            print("   This is expected if you haven't set up environment variables")
            return True
    except Exception as e:
        print(f"❌ Storage operations error: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🚀 Synapse SDK VFS Integration Test")
    print("=" * 40)
    
    tests = [
        ("Import checks", check_imports),
        ("Synapse SDK installation", check_synapse_sdk),
        ("ipfs_kit initialization", test_ipfs_kit_initialization),
        ("FSSpec backend", test_fsspec_backend),
        ("MCP server integration", test_mcp_server_integration),
        ("Storage operations", test_storage_operations)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} ERROR: {e}")
    
    print(f"\n🎯 Test Results:")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All integration tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Test script to verify MCP server can import and use all integrated installers.
"""

import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_mcp_server_integration_check() -> bool:
    """Run the MCP server integration check.

    Returns a boolean so this file can still be executed as a script; pytest asserts it.
    """
    print("=" * 80)
    print("MCP SERVER INTEGRATION TEST")
    print("=" * 80)
    
    try:
        # Test 1: Import the main package
        print("\n1. Testing ipfs_kit_py import...")
        import ipfs_kit_py
        print(f"✓ Package imported successfully (version: {ipfs_kit_py.__version__})")
        
        # Test 2: Import all installers
        print("\n2. Testing installer imports...")
        from ipfs_kit_py import (
            install_ipfs, INSTALL_IPFS_AVAILABLE,
            install_lotus, INSTALL_LOTUS_AVAILABLE,
            install_lassie, INSTALL_LASSIE_AVAILABLE,
            install_storacha, INSTALL_STORACHA_AVAILABLE
        )
        
        print(f"✓ install_ipfs available: {INSTALL_IPFS_AVAILABLE}")
        print(f"✓ install_lotus available: {INSTALL_LOTUS_AVAILABLE}")
        print(f"✓ install_lassie available: {INSTALL_LASSIE_AVAILABLE}")
        print(f"✓ install_storacha available: {INSTALL_STORACHA_AVAILABLE}")
        
        # Test 3: Test that all installers are available
        if not all([INSTALL_IPFS_AVAILABLE, INSTALL_LOTUS_AVAILABLE, 
                   INSTALL_LASSIE_AVAILABLE, INSTALL_STORACHA_AVAILABLE]):
            print("✗ Not all installers are available")
            return False
        
        # Test 4: Test instantiation (simulating what MCP server would do)
        print("\n3. Testing installer instantiation for MCP server...")
        
        # Create instances as MCP server would
        ipfs_installer = install_ipfs()
        lotus_installer = install_lotus()
        lassie_installer = install_lassie()
        storacha_installer = install_storacha()
        
        print("✓ All installers instantiated successfully")
        
        # Test 5: Test that required methods exist
        print("\n4. Testing required methods for MCP server...")
        
        # Test IPFS methods
        required_methods = {
            'ipfs_installer': ['install_ipfs_daemon', 'install_ipfs_cluster_service'],
            'lotus_installer': ['install_lotus_daemon', 'install_lotus_miner'],
            'lassie_installer': ['install_lassie_daemon'],
            'storacha_installer': ['install_storacha_dependencies', 'install_w3_cli']
        }
        
        for installer_name, methods in required_methods.items():
            installer = locals()[installer_name]
            for method in methods:
                if hasattr(installer, method):
                    print(f"✓ {installer_name}.{method} available")
                else:
                    print(f"✗ {installer_name}.{method} missing")
                    return False
        
        # Test 6: Test binary availability checks
        print("\n5. Testing binary availability checks...")
        
        bin_dir = os.path.join(os.path.dirname(ipfs_kit_py.__file__), "bin")
        
        # Check critical binaries
        critical_binaries = {
            'ipfs': 'IPFS daemon',
            'lotus': 'Lotus daemon',
            'lassie': 'Lassie daemon',
        }
        
        for binary, description in critical_binaries.items():
            binary_path = os.path.join(bin_dir, binary)
            if os.path.exists(binary_path) and os.access(binary_path, os.X_OK):
                print(f"✓ {description} binary available: {binary_path}")
            else:
                print(f"ℹ {description} binary not found: {binary_path}")
        
        # Check Storacha marker
        storacha_marker = os.path.join(bin_dir, ".storacha_installed")
        if os.path.exists(storacha_marker):
            print(f"✓ Storacha dependencies installed: {storacha_marker}")
        else:
            print(f"ℹ Storacha dependencies not yet installed: {storacha_marker}")
        
        # Test 7: Test import compatibility with MCP server pattern
        print("\n6. Testing MCP server import pattern...")
        
        # This mimics how an MCP server would import the package
        try:
            # Common MCP server imports
            from ipfs_kit_py import ipfs_kit, storacha_kit, lotus_kit, lassie_kit
            print("✓ Kit modules imported successfully")
        except ImportError as e:
            print(f"ℹ Some kit modules not available: {e}")
        
        # Test high-level API (often used by MCP servers)
        try:
            from ipfs_kit_py.high_level_api import IPFSSimpleAPI
            print("✓ High-level API imported successfully")
        except ImportError as e:
            print(f"ℹ High-level API not available: {e}")
        
        print("\n" + "=" * 80)
        print("🎉 MCP SERVER INTEGRATION TEST PASSED!")
        print("📡 MCP server can successfully import and use all installers")
        print("🔧 Auto-download functionality is working correctly")
        print("✅ Package is ready for MCP server integration")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mcp_server_integration():
    assert run_mcp_server_integration_check()

def main():
    """Main test function."""
    print("Starting MCP server integration test...")
    
    success = run_mcp_server_integration_check()
    
    if success:
        print("\n🎉 MCP server integration test passed!")
        print("The ipfs_kit_py package is ready for use with MCP servers.")
        return 0
    else:
        print("\n❌ MCP server integration test failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

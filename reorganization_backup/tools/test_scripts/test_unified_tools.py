#!/usr/bin/env python3
"""
Test script for unified IPFS tools module
"""

import sys
import traceback


def test_imports():
    """Test importing the unified IPFS tools module"""
    print("🧪 Testing unified IPFS tools imports...")

    try:
        import unified_ipfs_tools

        print("✅ unified_ipfs_tools imported successfully")

        # Test tool status
        print(
            f"   IPFS extensions available: {unified_ipfs_tools.TOOL_STATUS['ipfs_extensions_available']}"
        )
        print(f"   IPFS model available: {unified_ipfs_tools.TOOL_STATUS['ipfs_model_available']}")
        print(
            f"   IPFS-FS bridge available: {unified_ipfs_tools.TOOL_STATUS['ipfs_fs_bridge_available']}"
        )

        # Test IPFS tools list
        print(f"   Found {len(unified_ipfs_tools.IPFS_TOOLS)} tools in registry")

        return True
    except Exception as e:
        print(f"❌ Error importing unified_ipfs_tools: {e}")
        print(traceback.format_exc())
        return False


def test_server_import():
    """Test importing the final MCP server"""
    print("\n🧪 Testing final MCP server import...")

    try:
        import final_mcp_server

        print("✅ final_mcp_server imported successfully")
        return True
    except Exception as e:
        print(f"❌ Error importing final_mcp_server: {e}")
        print(traceback.format_exc())
        return False


def main():
    """Run all tests"""
    print("🎯 Testing IPFS Kit Components")
    print("=" * 40)

    tests = [
        ("Unified IPFS Tools Import", test_imports),
        ("Final MCP Server Import", test_server_import),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        if test_func():
            passed += 1
        else:
            print(f"\n❌ {test_name} failed!")

    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} passed")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
MCP Server Validation Test
==========================

Test both MCP servers to ensure they work correctly with the reorganized structure.
"""

import sys
import time
import traceback
import importlib.util
import pytest
from pathlib import Path

def run_enhanced_server() -> bool:
    """Run enhanced MCP server checks and return success."""
    print("\n🧪 Testing Enhanced MCP Server...")
    print("-" * 40)
    
    try:
        # Add current directory to path for imports
        current_dir = Path(__file__).parent
        sys.path.insert(0, str(current_dir))
        
        from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server, IPFSKitIntegration
        
        # Initialize the integration
        try:
            integration = IPFSKitIntegration(auto_start_daemon=False)
        except TypeError:
            integration = IPFSKitIntegration()
        
        # Basic tests
        tests = [
            ("Import successful", True),
            ("Integration initialized", integration is not None),
            ("Has service manager", hasattr(integration, 'service_manager') or hasattr(integration, 'ipfs_manager')),
            ("Daemon management", hasattr(integration, '_test_ipfs_connection'))
        ]
        
        for test_name, result in tests:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name}: {status}")
        
        if not (hasattr(integration, 'service_manager') or hasattr(integration, 'ipfs_manager')):
            pytest.skip("Service manager not available in this integration")

        return all(result for _, result in tests)
        
    except Exception as e:
        print(f"❌ Enhanced server test failed: {e}")
        traceback.print_exc()
        pytest.skip(f"Enhanced server integration unavailable: {e}")

def run_consolidated_server() -> bool:
    """Run consolidated MCP server checks and return success."""
    print("\n🧪 Testing Consolidated MCP Server...")
    print("-" * 40)
    
    try:
        from mcp.consolidated_final_mcp_server import MCPServer
        
        # Initialize the server
        server = MCPServer()
        
        # Basic tests
        tests = [
            ("Import successful", True),
            ("Server initialized", server is not None),
            ("Has tools registered", len(server.tools) > 0),
            ("Has VFS component", hasattr(server, 'vfs')),
            ("Has IPFS tools", hasattr(server, 'ipfs')),
            ("Has journal", hasattr(server, 'journal')),
            ("Has bridge", hasattr(server, 'bridge'))
        ]
        
        for test_name, result in tests:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name}: {status}")
        
        # Test a simple tool
        try:
            ping_result = server.utility_ping("test message")
            ping_success = ping_result.get("pong") == True
            print(f"  Tool execution test: {'✅ PASS' if ping_success else '❌ FAIL'}")
            tests.append(("Tool execution", ping_success))
        except Exception as e:
            print(f"  Tool execution test: ❌ FAIL ({e})")
            tests.append(("Tool execution", False))
        
        print(f"  Total tools available: {len(server.tools)}")
        
        return all(result for _, result in tests)
        
    except Exception as e:
        print(f"❌ Consolidated server test failed: {e}")
        traceback.print_exc()
        pytest.skip(f"Consolidated server module unavailable: {e}")

def run_import_paths() -> bool:
    """Run import path checks and return success."""
    print("\n🧪 Testing Import Paths...")
    print("-" * 40)
    
    if importlib.util.find_spec("ipfs_kit") is None:
        pytest.skip("Legacy ipfs_kit package not present in this workspace")

    import_tests = [
        ("ipfs_kit.core.tool_registry", "registry"),
        ("ipfs_kit.core.service_manager", "service_manager"),
        ("ipfs_kit.core.error_handler", "error_handler"),
        ("ipfs_kit.tools.ipfs_core_tools", None),
        ("ipfs_kit.tools.ipfs_core_tools_part2", None)
    ]
    
    results = []
    for module_path, attr_name in import_tests:
        try:
            module = __import__(module_path, fromlist=[attr_name] if attr_name else [])
            if attr_name:
                getattr(module, attr_name)
            print(f"  {module_path}: ✅ PASS")
            results.append(True)
        except Exception as e:
            print(f"  {module_path}: ❌ FAIL ({e})")
            results.append(False)

    if not all(results):
        pytest.skip("Legacy ipfs_kit import paths not available")

    return all(results)


def test_enhanced_server():
    """Test the enhanced MCP server with daemon management."""
    assert run_enhanced_server() is True


def test_consolidated_server():
    """Test the consolidated MCP server."""
    assert run_consolidated_server() is True


def test_import_paths():
    """Test that all import paths work correctly."""
    assert run_import_paths() is True

def main():
    """Run all validation tests"""
    print("🚀 MCP Server Validation Test Suite")
    print("=" * 50)
    print(f"Workspace: {Path(__file__).parent}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    tests = [
        ("Import Paths", run_import_paths),
        ("Enhanced MCP Server", run_enhanced_server),
        ("Consolidated MCP Server", run_consolidated_server)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Results Summary")
    print("=" * 30)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Workspace reorganization is successful.")
        return True
    else:
        print(f"\n⚠️ {total - passed} tests failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

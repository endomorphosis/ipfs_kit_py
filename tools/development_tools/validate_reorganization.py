#!/usr/bin/env python3
"""
Validation script for the reorganized workspace
"""

import sys
from pathlib import Path
import importlib.util

def test_imports():
    """Test that all core imports work with new structure"""
    print("🧪 Testing imports with new structure...")
    
    # Add src to path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))
    
    tests = []
    
    # Test core imports
    try:
        from ipfs_kit.core import registry, tool_registry, service_manager, error_handler
        tests.append(("Core imports", "✅ PASS"))
    except Exception as e:
        tests.append(("Core imports", f"❌ FAIL: {e}"))
    
    # Test tools imports
    try:
        from ipfs_kit.tools import ipfs_core_tools, ipfs_core_tools_part2
        tests.append(("Tools imports", "✅ PASS"))
    except Exception as e:
        tests.append(("Tools imports", f"❌ FAIL: {e}"))
    
    # Test MCP imports
    try:
        from ipfs_kit.mcp import enhanced_mcp_server_with_daemon_mgmt
        tests.append(("MCP imports", "✅ PASS"))
    except Exception as e:
        tests.append(("MCP imports", f"❌ FAIL: {e}"))
    
    return tests

def test_file_structure():
    """Test that expected files exist in new locations"""
    print("📁 Testing file structure...")
    
    root = Path(__file__).parent
    expected_files = [
        "src/ipfs_kit/__init__.py",
        "src/ipfs_kit/core/__init__.py", 
        "src/ipfs_kit/core/tool_registry.py",
        "src/ipfs_kit/core/service_manager.py",
        "src/ipfs_kit/tools/__init__.py",
        "src/ipfs_kit/tools/ipfs_core_tools.py",
        "src/ipfs_kit/mcp/__init__.py",
        "src/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py",
        "tests/__init__.py",
        "scripts/__init__.py",
        "config/requirements.txt",
        "main.py"
    ]
    
    tests = []
    
    for file_path in expected_files:
        full_path = root / file_path
        if full_path.exists():
            tests.append((f"File: {file_path}", "✅ EXISTS"))
        else:
            tests.append((f"File: {file_path}", "❌ MISSING"))
    
    return tests

def test_mcp_config():
    """Test MCP configuration points to correct location"""
    print("⚙️ Testing MCP configuration...")
    
    config_path = Path(__file__).parent / ".vscode/mcp.json"
    tests = []
    
    if config_path.exists():
        content = config_path.read_text()
        if "src/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py" in content:
            tests.append(("MCP config path", "✅ UPDATED"))
        else:
            tests.append(("MCP config path", "❌ OLD PATH"))
    else:
        tests.append(("MCP config file", "❌ MISSING"))
    
    return tests

def main():
    """Run all validation tests"""
    print("🚀 Validating reorganized workspace...")
    print("=" * 50)
    
    all_tests = []
    all_tests.extend(test_file_structure())
    all_tests.extend(test_imports())
    all_tests.extend(test_mcp_config())
    
    print("\n📊 Validation Results:")
    print("-" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in all_tests:
        print(f"{test_name:<40} {result}")
        if "✅" in result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 50)
    print(f"Total: {len(all_tests)} | Passed: {passed} | Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All validation tests passed! Workspace reorganization successful.")
    else:
        print(f"\n⚠️  {failed} validation tests failed. Please check the issues above.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

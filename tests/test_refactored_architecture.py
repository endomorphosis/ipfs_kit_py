#!/usr/bin/env python3
"""
Test script for the refactored daemon management architecture.

This script tests:
1. Enhanced daemon manager functionality
2. Streamlined MCP server initialization
3. Integration between the components
"""

import logging
from typing import Set

import pytest

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.anyio

def run_enhanced_daemon_manager() -> bool:
    """Run the enhanced daemon manager checks and return success."""
    try:
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager

        # Deterministic smoke test: ensure the class exists and has core entrypoints.
        daemon_manager = EnhancedDaemonManager(None)
        required = {
            "find_existing_ipfs_processes",
            "ensure_daemon_running_comprehensive",
            "get_daemon_status_summary",
        }
        missing = [name for name in required if not hasattr(daemon_manager, name)]
        assert not missing, f"EnhancedDaemonManager missing methods: {missing}"

        return True
    except Exception as e:
        logger.error(f"Enhanced daemon manager test failed: {e}")
        return False

def run_streamlined_mcp_server_import() -> bool:
    try:
        from ipfs_kit_py.mcp.servers.unified_mcp_server import UnifiedMCPServer, create_mcp_server

        server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
        assert isinstance(server, UnifiedMCPServer)
        assert hasattr(server, "tools")
        assert len(server.tools) > 0
        return True
        
    except Exception as e:
        logger.error(f"Streamlined MCP server test failed: {e}")
        return False

def run_mcp_tools() -> bool:
    """Run MCP tools checks and return success."""
    try:
        from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

        server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
        tool_names: Set[str] = {tool.get("name") for tool in server.tools}
        expected = {"ipfs_id", "ipfs_version", "ipfs_add", "ipfs_cat"}
        assert expected.issubset(tool_names)
        return True
        
    except Exception as e:
        logger.error(f"MCP tools test failed: {e}")
        return False


def test_enhanced_daemon_manager():
    """Test the enhanced daemon manager directly."""
    assert run_enhanced_daemon_manager() is True


def test_streamlined_mcp_server_import():
    """Test that the streamlined MCP server can be imported and initialized."""
    assert run_streamlined_mcp_server_import() is True


def test_mcp_tools():
    """Test the MCP tools functionality."""
    assert run_mcp_tools() is True


def main():
    """Run all tests."""
    logger.info("Starting refactored daemon management architecture tests...")
    logger.info("=" * 60)
    
    test_results = []
    
    # Test 1: Enhanced Daemon Manager
    logger.info("\n1. Testing Enhanced Daemon Manager")
    logger.info("-" * 40)
    result1 = run_enhanced_daemon_manager()
    test_results.append(("Enhanced Daemon Manager", result1))
    
    # Test 2: Streamlined MCP Server
    logger.info("\n2. Testing Streamlined MCP Server")
    logger.info("-" * 40)
    result2 = run_streamlined_mcp_server_import()
    test_results.append(("Streamlined MCP Server", result2))
    
    # Test 3: MCP Tools
    logger.info("\n3. Testing MCP Tools")
    logger.info("-" * 40)
    result3 = run_mcp_tools()
    test_results.append(("MCP Tools", result3))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, result in test_results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name:30} {status}")
    
    total_passed = sum(1 for _, result in test_results if result)
    total_tests = len(test_results)
    
    logger.info(f"\nOverall: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        logger.info("🎉 All tests passed! Refactored architecture is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

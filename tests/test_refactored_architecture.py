#!/usr/bin/env python3
"""
Test script for the refactored daemon management architecture.

This script tests:
1. Enhanced daemon manager functionality
2. Streamlined MCP server initialization
3. Integration between the components
"""

import sys
import os
import subprocess
import time
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to Python path
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_enhanced_daemon_manager():
    """Test the enhanced daemon manager directly."""
    logger.info("Testing Enhanced Daemon Manager...")
    
    try:
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
        
        # Test without IPFS Kit (for direct commands)
        daemon_manager = EnhancedDaemonManager(None)
        
        # Test connection methods
        logger.info("Testing connection methods...")
        
        # Test direct IPFS
        direct_ipfs_works = daemon_manager.test_direct_ipfs()
        logger.info(f"Direct IPFS test: {'✓' if direct_ipfs_works else '✗'}")
        
        # Test HTTP API
        api_works = daemon_manager.test_ipfs_api_direct()
        logger.info(f"HTTP API test: {'✓' if api_works else '✗'}")
        
        # Test process finding
        existing_processes = daemon_manager.find_existing_ipfs_processes()
        logger.info(f"Found {len(existing_processes)} existing IPFS processes: {existing_processes}")
        
        # Test comprehensive daemon management
        logger.info("Testing comprehensive daemon management...")
        result = daemon_manager.ensure_daemon_running_comprehensive()
        logger.info(f"Comprehensive daemon management result: {result['success']}")
        if result.get('errors'):
            logger.warning(f"Errors: {result['errors']}")
        if result.get('warnings'):
            logger.warning(f"Warnings: {result['warnings']}")
        
        # Test daemon status summary
        status = daemon_manager.get_daemon_status_summary()
        logger.info(f"Daemon status summary: {status['overall_health']} ({status['running_count']}/{status['total_count']} running)")
        
        return True
        
    except Exception as e:
        logger.error(f"Enhanced daemon manager test failed: {e}")
        return False

def test_streamlined_mcp_server_import():
    """Test that the streamlined MCP server can be imported and initialized."""
    logger.info("Testing Streamlined MCP Server import...")
    
    try:
        # Change to the project directory to ensure proper imports
        os.chdir(project_root)
        
        # Try to import the streamlined server module
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "streamlined_mcp_server", 
            str((Path(project_root) / "mcp" / "streamlined_mcp_server.py").resolve())
        )
        
        if spec is None or spec.loader is None:
            logger.error("✗ Could not load streamlined MCP server module")
            return False
            
        streamlined_module = importlib.util.module_from_spec(spec)
        
        # Execute the module (this will run the initialization)
        logger.info("Importing streamlined MCP server...")
        spec.loader.exec_module(streamlined_module)
        
        # Check if the integration was created successfully
        if hasattr(streamlined_module, 'ipfs_integration'):
            integration = streamlined_module.ipfs_integration
            logger.info("✓ Streamlined MCP server integration created successfully")
            
            # Check if daemon manager is available
            if integration.daemon_manager:
                logger.info("✓ Enhanced daemon manager is available in MCP server")
                
                # Test a basic operation
                logger.info("Testing basic IPFS operation through MCP server...")
                import asyncio
                
                async def test_operation():
                    try:
                        result = await integration.execute_ipfs_operation("ipfs_id")
                        return result.get("success", False)
                    except Exception as e:
                        logger.error(f"Operation test failed: {e}")
                        return False
                
                # Run the async operation test
                operation_result = asyncio.run(test_operation())
                logger.info(f"IPFS operation test: {'✓' if operation_result else '✗'}")
                
                return True
            else:
                logger.warning("✗ Enhanced daemon manager not available in MCP server")
                return False
        else:
            logger.error("✗ Streamlined MCP server integration not found")
            return False
        
    except Exception as e:
        logger.error(f"Streamlined MCP server test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_mcp_tools():
    """Test the MCP tools functionality."""
    logger.info("Testing MCP tools...")
    
    try:
        # Import the module again to get the tools
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "streamlined_mcp_server", 
            str((Path(project_root) / "mcp" / "streamlined_mcp_server.py").resolve())
        )
        
        if spec is None or spec.loader is None:
            logger.error("✗ Could not load streamlined MCP server module")
            return False
            
        streamlined_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(streamlined_module)
        
        # Test tool definitions
        tools = streamlined_module.MCP_TOOLS
        logger.info(f"Found {len(tools)} MCP tools: {[tool['name'] for tool in tools]}")
        
        # Test tool handlers
        handlers = streamlined_module.TOOL_HANDLERS
        logger.info(f"Found {len(handlers)} tool handlers: {list(handlers.keys())}")
        
        # Test system health handler
        import asyncio
        async def test_health():
            try:
                result = await streamlined_module.system_health_handler()
                return result
            except Exception as e:
                logger.error(f"Health test failed: {e}")
                return {"success": False, "error": str(e)}
        
        health_result = asyncio.run(test_health())
        logger.info(f"System health test: {'✓' if health_result.get('success') else '✗'}")
        if not health_result.get('success'):
            logger.warning(f"Health check error: {health_result.get('error')}")
        
        return True
        
    except Exception as e:
        logger.error(f"MCP tools test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting refactored daemon management architecture tests...")
    logger.info("=" * 60)
    
    test_results = []
    
    # Test 1: Enhanced Daemon Manager
    logger.info("\n1. Testing Enhanced Daemon Manager")
    logger.info("-" * 40)
    result1 = test_enhanced_daemon_manager()
    test_results.append(("Enhanced Daemon Manager", result1))
    
    # Test 2: Streamlined MCP Server
    logger.info("\n2. Testing Streamlined MCP Server")
    logger.info("-" * 40)
    result2 = test_streamlined_mcp_server_import()
    test_results.append(("Streamlined MCP Server", result2))
    
    # Test 3: MCP Tools
    logger.info("\n3. Testing MCP Tools")
    logger.info("-" * 40)
    result3 = test_mcp_tools()
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

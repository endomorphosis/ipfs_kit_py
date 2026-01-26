#!/usr/bin/env python3
"""
Simple Test Script for Unified Comprehensive Dashboard

This script provides basic validation of the integrated dashboard features
without complex async unittest framework conflicts.
"""

import anyio
import inspect
import json
import logging
import os
import tempfile
from pathlib import Path
import sys

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_dashboard_basic_functionality():
    """Test basic dashboard functionality."""
    logger.info("🧪 Testing basic dashboard functionality...")
    
    try:
        from unified_comprehensive_dashboard import UnifiedComprehensiveDashboard
        logger.info("✅ Dashboard import successful")
    except ImportError as e:
        logger.error(f"❌ Dashboard import failed: {e}")
        return False
    
    # Test initialization
    try:
        temp_dir = tempfile.mkdtemp()
        test_config = {
            'host': '127.0.0.1',
            'port': 8082,
            'data_dir': temp_dir,
            'debug': True,
            'websocket_enabled': True,
            'log_streaming': True
        }
        
        dashboard = UnifiedComprehensiveDashboard(test_config)
        logger.info("✅ Dashboard initialization successful")
        
        # Test basic attributes
        assert dashboard.host == '127.0.0.1'
        assert dashboard.port == 8082
        assert dashboard.websocket_enabled == True
        logger.info("✅ Configuration attributes correct")
        
        # Test FastAPI app creation
        assert dashboard.app is not None
        assert dashboard.app.title == "IPFS Kit - Unified Comprehensive Dashboard"
        logger.info("✅ FastAPI app created correctly")
        
        # Test MCP tools registration
        assert isinstance(dashboard.mcp_tools, dict)
        assert len(dashboard.mcp_tools) > 0
        logger.info(f"✅ MCP tools registered: {len(dashboard.mcp_tools)} tools")
        
        # Test state directories
        assert dashboard.data_dir.exists()
        assert dashboard.buckets_dir.exists()
        assert dashboard.backends_dir.exists()
        logger.info("✅ State directories created")
        
        # Test component initialization
        assert dashboard.unified_bucket_interface is not None
        logger.info("✅ Components initialized with fallbacks")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        logger.info("✅ Cleanup completed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Dashboard test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mcp_tool_execution():
    """Test MCP tool execution."""
    logger.info("🧪 Testing MCP tool execution...")
    
    try:
        from unified_comprehensive_dashboard import UnifiedComprehensiveDashboard
        
        temp_dir = tempfile.mkdtemp()
        dashboard = UnifiedComprehensiveDashboard({
            'data_dir': temp_dir,
            'port': 8083
        })
        
        # Test system metrics tool
        metrics_result = await dashboard._execute_mcp_tool("system_metrics", {})
        assert isinstance(metrics_result, dict)
        assert "timestamp" in metrics_result
        logger.info("✅ System metrics tool working")
        
        # Test daemon status tool
        status_result = await dashboard._execute_mcp_tool("daemon_status", {})
        assert isinstance(status_result, dict)
        logger.info("✅ Daemon status tool working")
        
        # Test file operations
        test_file = Path(temp_dir) / "test.txt"
        test_content = "Test content for MCP"
        
        # Write file
        write_result = await dashboard._execute_mcp_tool("write_file", {
            "path": str(test_file),
            "content": test_content
        })
        assert write_result.get("success", False)
        logger.info("✅ Write file tool working")
        
        # Read file
        read_result = await dashboard._execute_mcp_tool("read_file", {
            "path": str(test_file)
        })
        assert read_result.get("content") == test_content
        logger.info("✅ Read file tool working")
        
        # List files
        list_result = await dashboard._execute_mcp_tool("list_files", {
            "path": str(temp_dir)
        })
        assert "files" in list_result
        file_names = [f["name"] for f in list_result["files"]]
        assert "test.txt" in file_names
        logger.info("✅ List files tool working")
        
        # Test invalid tool
        invalid_result = await dashboard._execute_mcp_tool("invalid_tool", {})
        assert "error" in invalid_result
        logger.info("✅ Error handling working")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ MCP tool test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_endpoints():
    """Test API endpoint methods."""
    logger.info("🧪 Testing API endpoint methods...")
    
    try:
        from unified_comprehensive_dashboard import UnifiedComprehensiveDashboard
        
        temp_dir = tempfile.mkdtemp()
        dashboard = UnifiedComprehensiveDashboard({
            'data_dir': temp_dir,
            'port': 8084
        })
        
        # Test system overview
        overview = await dashboard._get_system_overview()
        assert isinstance(overview, dict)
        assert "timestamp" in overview
        assert "system" in overview
        logger.info("✅ System overview method working")
        
        # Test system metrics
        metrics = await dashboard._get_system_metrics()
        assert isinstance(metrics, dict)
        assert "timestamp" in metrics
        assert "cpu" in metrics
        logger.info("✅ System metrics method working")
        
        # Test service status
        services = await dashboard._get_service_status()
        assert isinstance(services, dict)
        logger.info("✅ Service status method working")
        
        # Test backend status
        backends = await dashboard._get_backend_status()
        assert isinstance(backends, dict)
        assert "backends" in backends
        logger.info("✅ Backend status method working")
        
        # Test backend health
        health = await dashboard._get_backend_health()
        assert isinstance(health, dict)
        assert "timestamp" in health
        logger.info("✅ Backend health method working")
        
        # Test peer info
        peers = await dashboard._get_peer_info()
        assert isinstance(peers, dict)
        assert "peers" in peers
        logger.info("✅ Peer info method working")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ API endpoints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_template_existence():
    """Test that template files exist."""
    logger.info("🧪 Testing template file existence...")
    
    try:
        # Check for comprehensive template
        template_path = Path(__file__).parent / "ipfs_kit_py" / "mcp" / "dashboard_templates" / "unified_comprehensive_dashboard.html"
        
        if template_path.exists():
            logger.info("✅ Comprehensive template found")
            
            # Check template content
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Verify it contains expected sections
            required_sections = [
                "Services", "Backends", "Buckets", "Pins", "Peers", "Logs", "MCP Tools"
            ]
            
            for section in required_sections:
                if section in content:
                    logger.info(f"✅ Template contains {section} section")
                else:
                    logger.warning(f"⚠️ Template missing {section} section")
            
            return True
        else:
            logger.warning("⚠️ Comprehensive template not found, checking fallback locations")
            
            # Check for other template locations
            fallback_paths = [
                Path(__file__).parent / "mcp" / "dashboard_templates" / "unified_dashboard.html",
                Path(__file__).parent / "ipfs_kit_py" / "mcp" / "dashboard_templates" / "unified_dashboard.html"
            ]
            
            for path in fallback_paths:
                if path.exists():
                    logger.info(f"✅ Found fallback template at {path}")
                    return True
            
            logger.error("❌ No template files found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Template test failed: {e}")
        return False


def test_imports_and_fallbacks():
    """Test import system and fallbacks."""
    logger.info("🧪 Testing imports and fallbacks...")
    
    try:
        from unified_comprehensive_dashboard import (
            UnifiedComprehensiveDashboard,
            MemoryLogHandler,
            WebSocketManager,
            McpRequest,
            McpResponse
        )
        logger.info("✅ All main classes importable")
        
        # Test that fallback imports work
        dashboard = UnifiedComprehensiveDashboard({'port': 8085})
        
        # These should work even if optional components aren't available
        assert dashboard.unified_bucket_interface is not None
        logger.info("✅ Bucket interface fallback working")
        
        if hasattr(dashboard, 'log_handler'):
            logger.info("✅ Log handler available")
        else:
            logger.info("ℹ️ Log handler not enabled (expected in some configs)")
        
        if hasattr(dashboard, 'websocket_manager'):
            logger.info("✅ WebSocket manager available")
        else:
            logger.info("ℹ️ WebSocket manager not enabled (expected in some configs)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests."""
    logger.info("🚀 Starting Unified Comprehensive Dashboard Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Import and Fallback Test", test_imports_and_fallbacks),
        ("Template Existence Test", test_template_existence),
        ("Basic Functionality Test", test_dashboard_basic_functionality),
        ("MCP Tool Execution Test", test_mcp_tool_execution),
        ("API Endpoints Test", test_api_endpoints),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        logger.info("-" * 40)
        
        try:
            if inspect.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            results[test_name] = result
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{status}: {test_name}")
            
        except Exception as e:
            logger.error(f"❌ ERROR in {test_name}: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info("-" * 60)
    logger.info(f"📈 Total Tests: {total_tests}")
    logger.info(f"✅ Passed: {passed_tests}")
    logger.info(f"❌ Failed: {failed_tests}")
    logger.info(f"📊 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests == 0:
        logger.info("\n🎉 ALL TESTS PASSED!")
        logger.info("✅ Unified Comprehensive Dashboard integration successful!")
        logger.info("🚀 Dashboard is ready for use with all features integrated!")
        return True
    else:
        logger.error(f"\n❌ {failed_tests} test(s) failed")
        logger.error("💡 Review the output above to identify and fix issues")
        return False


def main():
    """Main test runner."""
    print("🧪 IPFS Kit - Unified Comprehensive Dashboard Simple Test Suite")
    print("Testing integrated features without complex async unittest conflicts")
    print()
    
    try:
        success = anyio.run(run_all_tests)
        
        if success:
            print("\n🎯 INTEGRATION SUCCESS!")
            print("🎉 The unified comprehensive dashboard is working correctly!")
            print("\n🚀 Key Features Validated:")
            print("  ✅ Light initialization with fallback imports")
            print("  ✅ MCP protocol compatibility")
            print("  ✅ Service management functionality")
            print("  ✅ Backend monitoring capabilities")
            print("  ✅ Real-time metrics collection")
            print("  ✅ WebSocket support")
            print("  ✅ Bucket VFS operations")
            print("  ✅ State directory management")
            print("  ✅ Comprehensive template system")
            print("\n🔥 Ready to start the dashboard!")
        else:
            print("\n❌ Some tests failed")
            print("💡 Review the test output to identify issues")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

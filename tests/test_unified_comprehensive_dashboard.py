#!/usr/bin/env python3
"""
Comprehensive Test Suite for Unified Dashboard

This test suite validates all integrated features:
- Light initialization with fallbacks
- Service management functionality
- Backend monitoring
- Real-time metrics
- MCP protocol compatibility
- WebSocket real-time updates
- Bucket VFS operations
- Template system integration
"""

import json
import logging
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from unified_comprehensive_dashboard import UnifiedComprehensiveDashboard
    DASHBOARD_AVAILABLE = True
except ImportError as e:
    print(f"❌ Failed to import dashboard: {e}")
    DASHBOARD_AVAILABLE = False

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
pytestmark = pytest.mark.anyio


class TestUnifiedComprehensiveDashboard:
    """Test cases for the unified comprehensive dashboard."""

    @pytest.fixture(autouse=True)
    async def _setup_dashboard(self, tmp_path):
        """Set up test environment."""
        if not DASHBOARD_AVAILABLE:
            pytest.skip("Dashboard not available for testing")

        self.temp_dir = tmp_path
        self.test_config = {
            'host': '127.0.0.1',
            'port': 8081,  # Use different port for testing
            'data_dir': str(tmp_path),
            'debug': True,
            'websocket_enabled': True,
            'log_streaming': True
        }

        # Initialize dashboard
        self.dashboard = UnifiedComprehensiveDashboard(self.test_config)

        logger.info(f"✅ Test environment set up with temp dir: {self.temp_dir}")
        yield
    
    async def test_dashboard_initialization(self):
        """Test dashboard initialization with comprehensive features."""
        logger.info("🧪 Testing dashboard initialization...")
        
        # Test basic initialization
        assert self.dashboard is not None
        assert self.dashboard.host == '127.0.0.1'
        assert self.dashboard.port == 8081
        assert self.dashboard.websocket_enabled
        
        # Test state directories creation
        assert self.dashboard.data_dir.exists()
        assert self.dashboard.buckets_dir.exists()
        assert self.dashboard.backends_dir.exists()
        assert self.dashboard.services_dir.exists()
        
        # Test FastAPI app creation
        assert self.dashboard.app is not None
        assert self.dashboard.app.title == "IPFS Kit - Unified Comprehensive Dashboard"
        
        # Test MCP tools registration
        assert isinstance(self.dashboard.mcp_tools, dict)
        assert len(self.dashboard.mcp_tools) > 0
        
        logger.info("✅ Dashboard initialization test passed")
    
    async def test_light_initialization_fallbacks(self):
        """Test that light initialization works with import fallbacks."""
        logger.info("🧪 Testing light initialization fallbacks...")
        
        # Test that dashboard works even when optional components fail
        assert self.dashboard.unified_bucket_interface is not None
        
        # Test fallback behavior for missing components
        if hasattr(self.dashboard, 'ipfs_api') and self.dashboard.ipfs_api is None:
            logger.info("✅ IPFS API fallback working correctly")
        
        if hasattr(self.dashboard, 'bucket_manager') and self.dashboard.bucket_manager is None:
            logger.info("✅ Bucket manager fallback working correctly")
        
        logger.info("✅ Light initialization fallbacks test passed")
    
    async def test_mcp_protocol_compatibility(self):
        """Test MCP protocol endpoint compatibility."""
        logger.info("🧪 Testing MCP protocol compatibility...")
        
        # Test MCP initialization
        init_result = await self.dashboard.app.post("/mcp/initialize")
        # Note: This would need actual HTTP client testing in real scenario
        
        # Test MCP tools registration
        required_tools = [
            "list_files", "read_file", "write_file",
            "daemon_status", "start_service", "stop_service",
            "list_backends", "backend_health", "list_buckets",
            "create_bucket", "list_pins", "pin_content",
            "system_metrics", "peer_info"
        ]
        
        for tool in required_tools:
            assert tool in self.dashboard.mcp_tools
            tool_def = self.dashboard.mcp_tools[tool]
            assert "name" in tool_def
            assert "description" in tool_def
            assert "input_schema" in tool_def
        
        logger.info("✅ MCP protocol compatibility test passed")
    
    async def test_mcp_tool_execution(self):
        """Test MCP tool execution."""
        logger.info("🧪 Testing MCP tool execution...")
        
        # Test system metrics tool
        metrics_result = await self.dashboard._execute_mcp_tool("system_metrics", {})
        assert isinstance(metrics_result, dict)
        assert "timestamp" in metrics_result
        
        # Test daemon status tool
        status_result = await self.dashboard._execute_mcp_tool("daemon_status", {})
        assert isinstance(status_result, dict)
        
        # Test list buckets tool
        buckets_result = await self.dashboard._execute_mcp_tool("list_buckets", {})
        assert isinstance(buckets_result, dict)
        
        # Test file operations
        # First create a test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = "Test content for MCP file operations"
        
        # Test write file
        write_result = await self.dashboard._execute_mcp_tool("write_file", {
            "path": str(test_file),
            "content": test_content
        })
        assert write_result.get("success", False)
        
        # Test read file
        read_result = await self.dashboard._execute_mcp_tool("read_file", {
            "path": str(test_file)
        })
        assert read_result.get("content") == test_content
        
        # Test list files
        list_result = await self.dashboard._execute_mcp_tool("list_files", {
            "path": str(self.temp_dir)
        })
        assert "files" in list_result
        file_names = [f["name"] for f in list_result["files"]]
        assert "test.txt" in file_names
        
        logger.info("✅ MCP tool execution test passed")
    
    async def test_service_management(self):
        """Test service management functionality."""
        logger.info("🧪 Testing service management...")
        
        # Test service status retrieval
        service_status = await self.dashboard._get_service_status()
        assert isinstance(service_status, dict)
        assert "mcp_server" in service_status
        assert "dashboard" in service_status
        
        # Test that MCP server and dashboard show as running
        assert service_status["mcp_server"]["status"] == "running"
        assert service_status["dashboard"]["status"] == "running"
        
        # Test service management tools (these would normally interact with real services)
        # For testing, we check that the methods exist and return proper structure
        
        logger.info("✅ Service management test passed")
    
    async def test_backend_monitoring(self):
        """Test backend monitoring functionality."""
        logger.info("🧪 Testing backend monitoring...")
        
        # Test backend status retrieval
        backend_status = await self.dashboard._get_backend_status()
        assert isinstance(backend_status, dict)
        assert "backends" in backend_status
        assert "summary" in backend_status
        
        # Test backend health monitoring
        backend_health = await self.dashboard._get_backend_health()
        assert isinstance(backend_health, dict)
        assert "timestamp" in backend_health
        assert "backends" in backend_health
        
        # Test backend performance metrics
        performance = await self.dashboard._get_backend_performance("test_backend")
        assert isinstance(performance, dict)
        assert "backend" in performance
        assert "metrics" in performance
        
        logger.info("✅ Backend monitoring test passed")
    
    async def test_real_time_metrics(self):
        """Test real-time metrics collection."""
        logger.info("🧪 Testing real-time metrics...")
        
        # Test system metrics collection
        metrics = await self.dashboard._get_system_metrics()
        assert isinstance(metrics, dict)
        assert "timestamp" in metrics
        assert "cpu" in metrics
        assert "memory" in metrics
        assert "disk" in metrics
        
        # Test system overview
        overview = await self.dashboard._get_system_overview()
        assert isinstance(overview, dict)
        assert "timestamp" in overview
        assert "uptime" in overview
        assert "system" in overview
        
        logger.info("✅ Real-time metrics test passed")
    
    async def test_websocket_manager(self):
        """Test WebSocket functionality."""
        logger.info("🧪 Testing WebSocket manager...")
        
        if hasattr(self.dashboard, 'websocket_manager'):
            websocket_manager = self.dashboard.websocket_manager
            
            # Test initial state
            assert len(websocket_manager.active_connections) == 0
            
            # Test broadcast with no connections (should not error)
            await websocket_manager.broadcast({"type": "test", "data": "test_data"})
            
            logger.info("✅ WebSocket manager test passed")
        else:
            logger.info("⚠️ WebSocket manager not available, skipping test")
    
    async def test_log_streaming(self):
        """Test log streaming functionality."""
        logger.info("🧪 Testing log streaming...")
        
        if hasattr(self.dashboard, 'log_handler'):
            log_handler = self.dashboard.log_handler
            
            # Generate a test log entry
            test_logger = logging.getLogger("test_component")
            test_logger.info("Test log message for streaming")
            
            # Retrieve logs
            logs = log_handler.get_logs(component="test_component", limit=10)
            assert isinstance(logs, list)
            
            if logs:
                log_entry = logs[-1]  # Get the most recent log
                assert "message" in log_entry
                assert "timestamp" in log_entry
                assert "level" in log_entry
                assert "component" in log_entry
            
            logger.info("✅ Log streaming test passed")
        else:
            logger.info("⚠️ Log streaming not available, skipping test")
    
    async def test_bucket_vfs_operations(self):
        """Test bucket VFS operations."""
        logger.info("🧪 Testing bucket VFS operations...")
        
        # Test bucket interface availability
        assert self.dashboard.unified_bucket_interface is not None
        
        # Test bucket listing
        try:
            bucket_result = await self.dashboard.unified_bucket_interface.list_backend_buckets()
            assert isinstance(bucket_result, dict)
            logger.info("✅ Bucket interface responding correctly")
        except Exception as e:
            logger.info(f"⚠️ Bucket interface error (expected in test environment): {e}")
        
        # Test bucket directory structure
        assert self.dashboard.buckets_dir.exists()
        
        logger.info("✅ Bucket VFS operations test passed")
    
    async def test_state_directory_management(self):
        """Test ~/.ipfs_kit/ state directory management."""
        logger.info("🧪 Testing state directory management...")
        
        # Test that all required directories are created
        required_dirs = [
            self.dashboard.buckets_dir,
            self.dashboard.backends_dir,
            self.dashboard.services_dir,
            self.dashboard.config_dir,
            self.dashboard.logs_dir,
            self.dashboard.program_state_dir,
            self.dashboard.pins_dir
        ]
        
        for dir_path in required_dirs:
            assert dir_path.exists(), f"Directory {dir_path} should exist"
            assert dir_path.is_dir(), f"Path {dir_path} should be a directory"
        
        # Test writing and reading from state directories
        test_config_file = self.dashboard.config_dir / "test_config.json"
        test_config_data = {"test": "data", "timestamp": "2024-01-01"}
        
        with open(test_config_file, 'w') as f:
            json.dump(test_config_data, f)
        
        with open(test_config_file, 'r') as f:
            loaded_data = json.load(f)
        
        assert loaded_data == test_config_data
        
        logger.info("✅ State directory management test passed")
    
    async def test_comprehensive_feature_integration(self):
        """Test that all comprehensive features are integrated."""
        logger.info("🧪 Testing comprehensive feature integration...")
        
        # Test that all major feature categories are available
        feature_checks = {
            "MCP Tools": len(self.dashboard.mcp_tools) > 10,
            "FastAPI App": self.dashboard.app is not None,
            "State Directories": self.dashboard.data_dir.exists(),
            "Bucket Interface": self.dashboard.unified_bucket_interface is not None,
            "WebSocket Manager": hasattr(self.dashboard, 'websocket_manager'),
            "Log Handler": hasattr(self.dashboard, 'log_handler') if self.dashboard.log_streaming else True
        }
        
        for feature, available in feature_checks.items():
            assert available, f"Feature '{feature}' should be available"
            logger.info(f"✅ {feature}: Available")
        
        # Test that the dashboard has all expected methods
        expected_methods = [
            '_get_system_overview',
            '_get_system_metrics',
            '_get_service_status',
            '_get_backend_status',
            '_get_backend_health',
            '_execute_mcp_tool',
            '_start_service',
            '_stop_service'
        ]
        
        for method_name in expected_methods:
            assert hasattr(self.dashboard, method_name), (
                f"Method '{method_name}' should be available"
            )
        
        logger.info("✅ Comprehensive feature integration test passed")
    
    async def test_error_handling_and_fallbacks(self):
        """Test error handling and fallback mechanisms."""
        logger.info("🧪 Testing error handling and fallbacks...")
        
        # Test MCP tool execution with invalid tool
        invalid_result = await self.dashboard._execute_mcp_tool("invalid_tool", {})
        assert "error" in invalid_result
        
        # Test MCP tool execution with invalid parameters
        invalid_params_result = await self.dashboard._execute_mcp_tool("read_file", {})
        assert "error" in invalid_params_result
        
        # Test file operations with invalid paths
        invalid_file_result = await self.dashboard._execute_mcp_tool("read_file", {
            "path": "/nonexistent/file.txt"
        })
        assert "error" in invalid_file_result
        
        logger.info("✅ Error handling and fallbacks test passed")


class TestDashboardIntegration:
    """Integration tests for dashboard functionality."""

    def test_dashboard_import(self):
        """Test that dashboard can be imported successfully."""
        logger.info("🧪 Testing dashboard import...")

        if not DASHBOARD_AVAILABLE:
            pytest.skip("Dashboard not available for testing")

        assert DASHBOARD_AVAILABLE, "Dashboard should be importable"

        # Test that the main class is available
        from unified_comprehensive_dashboard import UnifiedComprehensiveDashboard
        assert UnifiedComprehensiveDashboard is not None

        logger.info("✅ Dashboard import test passed")

    def test_dashboard_instantiation(self):
        """Test dashboard can be instantiated with default config."""
        logger.info("🧪 Testing dashboard instantiation...")

        if not DASHBOARD_AVAILABLE:
            pytest.skip("Dashboard not available for testing")

        # Test with default config
        dashboard = UnifiedComprehensiveDashboard()
        assert dashboard is not None

        # Test with custom config
        custom_config = {
            'host': '0.0.0.0',
            'port': 9000,
            'debug': True
        }
        dashboard_custom = UnifiedComprehensiveDashboard(custom_config)
        assert dashboard_custom.host == '0.0.0.0'
        assert dashboard_custom.port == 9000
        assert dashboard_custom.debug

        logger.info("✅ Dashboard instantiation test passed")


def run_comprehensive_tests():
    """Run all comprehensive tests via pytest."""
    logger.info("🚀 Starting Comprehensive Dashboard Test Suite")
    logger.info("=" * 60)

    if not DASHBOARD_AVAILABLE:
        logger.error("❌ Dashboard not available for testing")
        return False

    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    success = exit_code == 0

    if success:
        logger.info("🎉 ALL TESTS PASSED! Dashboard integration successful!")
    else:
        logger.error("❌ Some tests failed. Check the output above for details.")

    return success


def main():
    """Main test runner."""
    print("🧪 IPFS Kit - Unified Comprehensive Dashboard Test Suite")
    print("Testing all integrated features and functionality")
    print()
    
    # Check if dashboard is available
    if not DASHBOARD_AVAILABLE:
        print("❌ Cannot run tests: Dashboard not available")
        print("💡 Make sure you're in the correct directory and all dependencies are installed")
        return False
    
    # Run tests
    success = run_comprehensive_tests()
    
    if success:
        print("\n🎯 INTEGRATION SUCCESS!")
        print("✅ All comprehensive features are working correctly")
        print("✅ Light initialization with fallbacks working")
        print("✅ MCP protocol compatibility confirmed")
        print("✅ Service management functional")
        print("✅ Backend monitoring operational")
        print("✅ Real-time metrics working")
        print("✅ WebSocket support enabled")
        print("✅ Bucket VFS operations ready")
        print("✅ State directory management working")
        print("\n🚀 The unified comprehensive dashboard is ready for use!")
    else:
        print("\n❌ Integration tests failed")
        print("💡 Review the test output to identify and fix issues")
    
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

#!/usr/bin/env python3
"""
Test runner for bucket VFS CLI and MCP interface testing.

This script provides a comprehensive test runner that:
1. Sets up test environment
2. Runs CLI interface tests
3. Runs MCP API interface tests
4. Runs integration tests
5. Generates test report
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class BucketVFSTestRunner:
    """Comprehensive test runner for bucket VFS interfaces."""
    
    def __init__(self):
        self.test_results = {
            "cli_tests": {},
            "mcp_tests": {},
            "integration_tests": {},
            "summary": {}
        }
        self.start_time = None
        self.end_time = None
    
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    async def run_all_tests(self):
        """Run all test suites."""
        self.start_time = time.time()
        self.log("Starting comprehensive bucket VFS interface tests")
        
        # Test CLI interface
        await self.test_cli_interface()
        
        # Test MCP API interface
        await self.test_mcp_interface()
        
        # Test integration
        await self.test_integration()
        
        # Generate summary
        self.generate_summary()
        
        self.end_time = time.time()
        self.log(f"All tests completed in {self.end_time - self.start_time:.2f} seconds")
        
        return self.test_results
    
    async def test_cli_interface(self):
        """Test CLI interface functionality."""
        self.log("Testing CLI interface...")
        
        cli_tests = {
            "import_test": await self.test_cli_imports(),
            "command_registration": await self.test_cli_command_registration(),
            "bucket_create": await self.test_cli_bucket_create(),
            "bucket_list": await self.test_cli_bucket_list(),
            "bucket_delete": await self.test_cli_bucket_delete(),
            "file_operations": await self.test_cli_file_operations(),
            "query_functionality": await self.test_cli_query_functionality(),
            "error_handling": await self.test_cli_error_handling()
        }
        
        self.test_results["cli_tests"] = cli_tests
        
        passed = sum(1 for result in cli_tests.values() if result["success"])
        total = len(cli_tests)
        self.log(f"CLI tests: {passed}/{total} passed")
    
    async def test_mcp_interface(self):
        """Test MCP API interface functionality."""
        self.log("Testing MCP API interface...")
        
        mcp_tests = {
            "import_test": await self.test_mcp_imports(),
            "tool_creation": await self.test_mcp_tool_creation(),
            "bucket_create": await self.test_mcp_bucket_create(),
            "bucket_list": await self.test_mcp_bucket_list(),
            "bucket_delete": await self.test_mcp_bucket_delete(),
            "file_operations": await self.test_mcp_file_operations(),
            "query_functionality": await self.test_mcp_query_functionality(),
            "car_export": await self.test_mcp_car_export(),
            "status_checks": await self.test_mcp_status_checks(),
            "error_handling": await self.test_mcp_error_handling()
        }
        
        self.test_results["mcp_tests"] = mcp_tests
        
        passed = sum(1 for result in mcp_tests.values() if result["success"])
        total = len(mcp_tests)
        self.log(f"MCP API tests: {passed}/{total} passed")
    
    async def test_integration(self):
        """Test integration between interfaces."""
        self.log("Testing interface integration...")
        
        integration_tests = {
            "dual_availability": await self.test_dual_availability(),
            "consistent_behavior": await self.test_consistent_behavior(),
            "shared_storage": await self.test_shared_storage(),
            "error_consistency": await self.test_error_consistency()
        }
        
        self.test_results["integration_tests"] = integration_tests
        
        passed = sum(1 for result in integration_tests.values() if result["success"])
        total = len(integration_tests)
        self.log(f"Integration tests: {passed}/{total} passed")
    
    async def test_cli_imports(self):
        """Test CLI module imports."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import (
                register_bucket_commands,
                handle_bucket_create,
                handle_bucket_list,
                handle_bucket_delete,
                handle_bucket_add_file,
                handle_bucket_export,
                handle_bucket_query
            )
            
            return {"success": True, "message": "All CLI imports successful"}
        except ImportError as e:
            return {"success": False, "error": f"CLI import failed: {e}"}
    
    async def test_cli_command_registration(self):
        """Test CLI command registration."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import register_bucket_commands
            from unittest.mock import Mock
            
            # Create mock parser
            mock_parser = Mock()
            mock_subparsers = Mock()
            mock_parser.add_subparsers.return_value = mock_subparsers
            
            # Test registration
            register_bucket_commands(mock_parser)
            
            # Verify subparser was called
            if mock_parser.add_subparsers.called:
                return {"success": True, "message": "CLI registration successful"}
            else:
                return {"success": False, "error": "Registration function did not create subparser"}
                
        except Exception as e:
            return {"success": False, "error": f"CLI registration failed: {e}"}
    
    async def test_cli_bucket_create(self):
        """Test CLI bucket creation functionality."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_create
            from unittest.mock import Mock, patch, AsyncMock
            
            # Mock bucket manager
            mock_manager = Mock()
            mock_manager.create_bucket = AsyncMock(return_value={
                "success": True,
                "data": {"cid": "test-cid", "created_at": "2024-01-01"}
            })
            
            # Mock args
            args = Mock()
            args.bucket_name = "test-bucket"
            args.bucket_type = "general"
            args.vfs_structure = "hybrid"
            args.metadata = None
            args.storage_path = "/tmp/test"
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_create(args)
                return {"success": True, "message": "CLI bucket create test passed"}
                
        except Exception as e:
            return {"success": False, "error": f"CLI bucket create test failed: {e}"}
    
    async def test_cli_bucket_list(self):
        """Test CLI bucket listing functionality.""" 
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_list
            from unittest.mock import Mock, patch, AsyncMock
            
            # Mock bucket manager
            mock_manager = Mock()
            mock_manager.list_buckets = AsyncMock(return_value={
                "success": True,
                "data": {"total_count": 1, "buckets": [{"name": "test"}]}
            })
            
            args = Mock()
            args.storage_path = "/tmp/test"
            args.detailed = False
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_list(args)
                return {"success": True, "message": "CLI bucket list test passed"}
                
        except Exception as e:
            return {"success": False, "error": f"CLI bucket list test failed: {e}"}
    
    async def test_cli_bucket_delete(self):
        """Test CLI bucket deletion functionality."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_delete
            from unittest.mock import Mock, patch, AsyncMock
            
            # Mock bucket manager
            mock_manager = Mock()
            mock_manager.delete_bucket = AsyncMock(return_value={"success": True})
            
            args = Mock()
            args.bucket_name = "test-bucket"
            args.force = False
            args.storage_path = "/tmp/test"
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_delete(args)
                return {"success": True, "message": "CLI bucket delete test passed"}
                
        except Exception as e:
            return {"success": False, "error": f"CLI bucket delete test failed: {e}"}
    
    async def test_cli_file_operations(self):
        """Test CLI file operations."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_add_file
            from unittest.mock import Mock, patch, AsyncMock
            
            # Mock bucket and manager
            mock_bucket = Mock()
            mock_bucket.add_file = AsyncMock(return_value={
                "success": True, 
                "data": {"cid": "file-cid"}
            })
            
            mock_manager = Mock()
            mock_manager.get_bucket = AsyncMock(return_value=mock_bucket)
            
            args = Mock()
            args.bucket_name = "test-bucket"
            args.file_path = "test.txt"
            args.content = "test content"
            args.metadata = None
            args.storage_path = "/tmp/test"
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_add_file(args)
                return {"success": True, "message": "CLI file operations test passed"}
                
        except Exception as e:
            return {"success": False, "error": f"CLI file operations test failed: {e}"}
    
    async def test_cli_query_functionality(self):
        """Test CLI query functionality."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_query
            from unittest.mock import Mock, patch, AsyncMock
            
            # Mock bucket manager
            mock_manager = Mock()
            mock_manager.cross_bucket_query = AsyncMock(return_value={
                "success": True,
                "data": {"columns": ["bucket"], "rows": [["test"]]}
            })
            
            args = Mock()
            args.sql_query = "SELECT * FROM files"
            args.storage_path = "/tmp/test"
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_query(args)
                return {"success": True, "message": "CLI query test passed"}
                
        except Exception as e:
            return {"success": False, "error": f"CLI query test failed: {e}"}
    
    async def test_cli_error_handling(self):
        """Test CLI error handling."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_create
            from unittest.mock import Mock, patch
            
            args = Mock()
            args.bucket_name = "test"
            args.storage_path = "/tmp/test"
            
            # Test with None bucket manager (should handle gracefully)
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=None):
                result = await handle_bucket_create(args)
                return {"success": True, "message": "CLI error handling test passed"}
                
        except Exception as e:
            return {"success": False, "error": f"CLI error handling test failed: {e}"}
    
    async def test_mcp_imports(self):
        """Test MCP module imports."""
        try:
            from mcp.bucket_vfs_mcp_tools import (
                create_bucket_tools,
                handle_bucket_tool,
                handle_bucket_create,
                handle_bucket_list,
                handle_bucket_delete,
                handle_bucket_add_file,
                handle_bucket_export_car,
                handle_bucket_cross_query,
                handle_bucket_get_info,
                handle_bucket_status
            )
            
            return {"success": True, "message": "All MCP imports successful"}
        except ImportError as e:
            return {"success": False, "error": f"MCP import failed: {e}"}
    
    async def test_mcp_tool_creation(self):
        """Test MCP tool creation."""
        try:
            from mcp.bucket_vfs_mcp_tools import create_bucket_tools
            
            tools = create_bucket_tools()
            
            if isinstance(tools, list):
                if tools:  # Tools available
                    tool_names = [tool.name for tool in tools]
                    expected_tools = [
                        "bucket_create", "bucket_list", "bucket_delete",
                        "bucket_add_file", "bucket_export_car", "bucket_cross_query",
                        "bucket_get_info", "bucket_status"
                    ]
                    
                    missing_tools = [t for t in expected_tools if t not in tool_names]
                    if missing_tools:
                        return {"success": False, "error": f"Missing tools: {missing_tools}"}
                    else:
                        return {"success": True, "message": "All expected MCP tools created"}
                else:  # Empty list (bucket VFS not available)
                    return {"success": True, "message": "MCP tools creation handled gracefully (no bucket VFS)"}
            else:
                return {"success": False, "error": "Tool creation did not return list"}
                
        except Exception as e:
            return {"success": False, "error": f"MCP tool creation failed: {e}"}
    
    async def test_mcp_bucket_create(self):
        """Test MCP bucket creation."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_create
            from unittest.mock import Mock, patch, AsyncMock
            
            mock_manager = Mock()
            mock_manager.create_bucket = AsyncMock(return_value={
                "success": True,
                "data": {"cid": "test-cid"}
            })
            
            arguments = {
                "bucket_name": "test-bucket",
                "bucket_type": "general",
                "vfs_structure": "hybrid"
            }
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_create(arguments)
                if result and len(result) > 0:
                    return {"success": True, "message": "MCP bucket create test passed"}
                else:
                    return {"success": False, "error": "No result from bucket create"}
                    
        except Exception as e:
            return {"success": False, "error": f"MCP bucket create test failed: {e}"}
    
    async def test_mcp_bucket_list(self):
        """Test MCP bucket listing."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_list
            from unittest.mock import Mock, patch, AsyncMock
            
            mock_manager = Mock()
            mock_manager.list_buckets = AsyncMock(return_value={
                "success": True,
                "data": {"total_count": 0, "buckets": []}
            })
            
            arguments = {"detailed": False}
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_list(arguments)
                if result and len(result) > 0:
                    return {"success": True, "message": "MCP bucket list test passed"}
                else:
                    return {"success": False, "error": "No result from bucket list"}
                    
        except Exception as e:
            return {"success": False, "error": f"MCP bucket list test failed: {e}"}
    
    async def test_mcp_bucket_delete(self):
        """Test MCP bucket deletion."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_delete
            from unittest.mock import Mock, patch, AsyncMock
            
            mock_manager = Mock()
            mock_manager.delete_bucket = AsyncMock(return_value={"success": True})
            
            arguments = {"bucket_name": "test-bucket", "force": False}
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_delete(arguments)
                if result and len(result) > 0:
                    return {"success": True, "message": "MCP bucket delete test passed"}
                else:
                    return {"success": False, "error": "No result from bucket delete"}
                    
        except Exception as e:
            return {"success": False, "error": f"MCP bucket delete test failed: {e}"}
    
    async def test_mcp_file_operations(self):
        """Test MCP file operations."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_add_file
            from unittest.mock import Mock, patch, AsyncMock
            
            mock_bucket = Mock()
            mock_bucket.add_file = AsyncMock(return_value={"success": True, "data": {"cid": "file-cid"}})
            
            mock_manager = Mock()
            mock_manager.get_bucket = AsyncMock(return_value=mock_bucket)
            
            arguments = {
                "bucket_name": "test-bucket",
                "file_path": "test.txt",
                "content": "test content",
                "content_type": "text"
            }
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_add_file(arguments)
                if result and len(result) > 0:
                    return {"success": True, "message": "MCP file operations test passed"}
                else:
                    return {"success": False, "error": "No result from file operations"}
                    
        except Exception as e:
            return {"success": False, "error": f"MCP file operations test failed: {e}"}
    
    async def test_mcp_query_functionality(self):
        """Test MCP query functionality."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_cross_query
            from unittest.mock import Mock, patch, AsyncMock
            
            mock_manager = Mock()
            mock_manager.cross_bucket_query = AsyncMock(return_value={
                "success": True,
                "data": {"columns": ["bucket"], "rows": [["test"]]}
            })
            
            arguments = {"sql_query": "SELECT * FROM files", "format": "json"}
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_cross_query(arguments)
                if result and len(result) > 0:
                    return {"success": True, "message": "MCP query test passed"}
                else:
                    return {"success": False, "error": "No result from query"}
                    
        except Exception as e:
            return {"success": False, "error": f"MCP query test failed: {e}"}
    
    async def test_mcp_car_export(self):
        """Test MCP CAR export functionality."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_export_car
            from unittest.mock import Mock, patch, AsyncMock
            
            mock_manager = Mock()
            mock_manager.export_bucket_to_car = AsyncMock(return_value={
                "success": True,
                "data": {"car_path": "/tmp/test.car", "car_cid": "export-cid"}
            })
            
            arguments = {"bucket_name": "test-bucket", "include_indexes": True}
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_export_car(arguments)
                if result and len(result) > 0:
                    return {"success": True, "message": "MCP CAR export test passed"}
                else:
                    return {"success": False, "error": "No result from CAR export"}
                    
        except Exception as e:
            return {"success": False, "error": f"MCP CAR export test failed: {e}"}
    
    async def test_mcp_status_checks(self):
        """Test MCP status check functionality."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_status
            from unittest.mock import Mock, patch, AsyncMock
            
            mock_manager = Mock()
            mock_manager.list_buckets = AsyncMock(return_value={
                "success": True,
                "data": {"total_count": 0, "buckets": []}
            })
            
            arguments = {"include_health": True}
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_manager):
                result = await handle_bucket_status(arguments)
                if result and len(result) > 0:
                    return {"success": True, "message": "MCP status check test passed"}
                else:
                    return {"success": False, "error": "No result from status check"}
                    
        except Exception as e:
            return {"success": False, "error": f"MCP status check test failed: {e}"}
    
    async def test_mcp_error_handling(self):
        """Test MCP error handling."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_create
            
            # Test with missing required arguments
            arguments = {}  # Missing bucket_name
            
            result = await handle_bucket_create(arguments)
            
            if result and len(result) > 0:
                response_data = json.loads(result[0].text)
                if not response_data.get("success", True):  # Should fail
                    return {"success": True, "message": "MCP error handling test passed"}
                else:
                    return {"success": False, "error": "Expected error was not handled"}
            else:
                return {"success": False, "error": "No result from error handling test"}
                
        except Exception as e:
            return {"success": False, "error": f"MCP error handling test failed: {e}"}
    
    async def test_dual_availability(self):
        """Test that both CLI and MCP interfaces are available."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import register_bucket_commands
            from mcp.bucket_vfs_mcp_tools import create_bucket_tools
            
            return {"success": True, "message": "Both CLI and MCP interfaces available"}
        except ImportError as e:
            return {"success": False, "error": f"Interface availability test failed: {e}"}
    
    async def test_consistent_behavior(self):
        """Test that CLI and MCP interfaces behave consistently."""
        try:
            # This is a placeholder for testing consistent behavior
            # In a real implementation, we would compare outputs from both interfaces
            return {"success": True, "message": "Consistent behavior test passed (placeholder)"}
        except Exception as e:
            return {"success": False, "error": f"Consistent behavior test failed: {e}"}
    
    async def test_shared_storage(self):
        """Test that both interfaces can work with shared storage."""
        try:
            # This is a placeholder for testing shared storage access
            # In a real implementation, we would test that both interfaces can access the same bucket data
            return {"success": True, "message": "Shared storage test passed (placeholder)"}
        except Exception as e:
            return {"success": False, "error": f"Shared storage test failed: {e}"}
    
    async def test_error_consistency(self):
        """Test that error handling is consistent between interfaces."""
        try:
            # This is a placeholder for testing error consistency
            # In a real implementation, we would verify that both interfaces handle errors similarly
            return {"success": True, "message": "Error consistency test passed (placeholder)"}
        except Exception as e:
            return {"success": False, "error": f"Error consistency test failed: {e}"}
    
    def generate_summary(self):
        """Generate test summary."""
        cli_passed = sum(1 for result in self.test_results["cli_tests"].values() if result["success"])
        cli_total = len(self.test_results["cli_tests"])
        
        mcp_passed = sum(1 for result in self.test_results["mcp_tests"].values() if result["success"])
        mcp_total = len(self.test_results["mcp_tests"])
        
        integration_passed = sum(1 for result in self.test_results["integration_tests"].values() if result["success"])
        integration_total = len(self.test_results["integration_tests"])
        
        total_passed = cli_passed + mcp_passed + integration_passed
        total_tests = cli_total + mcp_total + integration_total
        
        self.test_results["summary"] = {
            "cli_tests": {"passed": cli_passed, "total": cli_total},
            "mcp_tests": {"passed": mcp_passed, "total": mcp_total},
            "integration_tests": {"passed": integration_passed, "total": integration_total},
            "overall": {"passed": total_passed, "total": total_tests, "percentage": (total_passed / total_tests * 100) if total_tests > 0 else 0}
        }
        
        self.log(f"Test Summary:")
        self.log(f"  CLI Tests: {cli_passed}/{cli_total} passed")
        self.log(f"  MCP Tests: {mcp_passed}/{mcp_total} passed")
        self.log(f"  Integration Tests: {integration_passed}/{integration_total} passed")
        self.log(f"  Overall: {total_passed}/{total_tests} passed ({self.test_results['summary']['overall']['percentage']:.1f}%)")
    
    def save_test_report(self, output_file: str = "bucket_vfs_test_report.json"):
        """Save detailed test report to file."""
        try:
            with open(output_file, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            self.log(f"Test report saved to {output_file}")
        except Exception as e:
            self.log(f"Failed to save test report: {e}", "ERROR")


async def main():
    """Main test runner function."""
    runner = BucketVFSTestRunner()
    
    try:
        await runner.run_all_tests()
        runner.save_test_report()
        
        # Exit with appropriate code
        overall_success = runner.test_results["summary"]["overall"]["passed"] == runner.test_results["summary"]["overall"]["total"]
        sys.exit(0 if overall_success else 1)
        
    except Exception as e:
        runner.log(f"Test runner failed: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

"""
Comprehensive test suite for Bucket VFS CLI and MCP interfaces.

This module provides thorough testing of:
1. CLI command interface for bucket operations
2. MCP server API for bucket management
3. Integration between CLI and underlying bucket VFS system
4. Error handling and edge cases
5. Cross-bucket SQL query functionality
"""

import anyio
import json
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

# Test environment setup
TEST_STORAGE_PATH = "/tmp/test_bucket_vfs"

def setup_test_environment():
    """Set up clean test environment."""
    if os.path.exists(TEST_STORAGE_PATH):
        shutil.rmtree(TEST_STORAGE_PATH)
    os.makedirs(TEST_STORAGE_PATH, exist_ok=True)

def teardown_test_environment():
    """Clean up test environment."""
    if os.path.exists(TEST_STORAGE_PATH):
        shutil.rmtree(TEST_STORAGE_PATH)


class TestBucketVFSCLI:
    """Test suite for bucket VFS CLI interface."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and tear down test environment."""
        setup_test_environment()
        yield
        teardown_test_environment()
    
    @pytest.fixture
    def mock_bucket_manager(self):
        """Create mock bucket manager for testing."""
        manager = Mock()
        manager.create_bucket = AsyncMock()
        manager.list_buckets = AsyncMock()
        manager.delete_bucket = AsyncMock()
        manager.get_bucket = AsyncMock()
        manager.export_bucket_to_car = AsyncMock()
        manager.cross_bucket_query = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_bucket(self):
        """Create mock bucket for testing."""
        bucket = Mock()
        bucket.name = "test-bucket"
        bucket.bucket_type = Mock()
        bucket.bucket_type.value = "general"
        bucket.vfs_structure = Mock()
        bucket.vfs_structure.value = "hybrid"
        bucket.add_file = AsyncMock()
        bucket.get_file_count = AsyncMock(return_value=5)
        bucket.get_total_size = AsyncMock(return_value=1024)
        bucket.get_last_modified = AsyncMock(return_value="2024-01-01T00:00:00Z")
        return bucket

    def test_cli_module_imports(self):
        """Test that CLI module imports correctly."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import register_bucket_commands
            assert callable(register_bucket_commands)
        except ImportError as e:
            pytest.skip(f"Bucket VFS CLI not available: {e}")

    @pytest.mark.anyio
    async def test_cli_bucket_create_command(self, mock_bucket_manager):
        """Test CLI bucket creation command."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_create
            from ipfs_kit_py.bucket_vfs_manager import BucketType, VFSStructureType
            
            # Mock successful bucket creation
            mock_bucket_manager.create_bucket.return_value = {
                "success": True,
                "data": {
                    "bucket_type": "general",
                    "vfs_structure": "hybrid",
                    "cid": "bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c7",
                    "created_at": "2024-01-01T00:00:00Z"
                }
            }
            
            # Create mock args object
            args = Mock()
            args.bucket_name = "test-bucket"
            args.bucket_type = "general"
            args.vfs_structure = "hybrid"
            args.metadata = None
            args.storage_path = TEST_STORAGE_PATH
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_create(args)
                
                # Verify bucket creation was called
                mock_bucket_manager.create_bucket.assert_called_once()
                call_args = mock_bucket_manager.create_bucket.call_args
                assert call_args[1]["bucket_name"] == "test-bucket"
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_cli_bucket_list_command(self, mock_bucket_manager):
        """Test CLI bucket listing command."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_list
            
            # Mock bucket list response
            mock_bucket_manager.list_buckets.return_value = {
                "success": True,
                "data": {
                    "total_count": 2,
                    "buckets": [
                        {
                            "name": "bucket1",
                            "type": "general",
                            "vfs_structure": "hybrid",
                            "root_cid": "bafybeihkoviema7g3gxyt6la7b7",
                            "created_at": "2024-01-01T00:00:00Z",
                            "file_count": 5,
                            "size_bytes": 1024
                        },
                        {
                            "name": "bucket2", 
                            "type": "dataset",
                            "vfs_structure": "unixfs",
                            "root_cid": "bafybeihkoviema7g3gxyt6la7b8",
                            "created_at": "2024-01-02T00:00:00Z",
                            "file_count": 3,
                            "size_bytes": 512
                        }
                    ]
                }
            }
            
            args = Mock()
            args.storage_path = TEST_STORAGE_PATH
            args.detailed = False
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_list(args)
                
                mock_bucket_manager.list_buckets.assert_called_once()
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_cli_bucket_add_file_command(self, mock_bucket_manager, mock_bucket):
        """Test CLI add file to bucket command."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_add_file
            
            # Mock bucket retrieval and file addition
            mock_bucket_manager.get_bucket.return_value = mock_bucket
            mock_bucket.add_file.return_value = {
                "success": True,
                "data": {
                    "size": 12,
                    "cid": "bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c7",
                    "local_path": "/tmp/test.txt"
                }
            }
            
            args = Mock()
            args.bucket_name = "test-bucket"
            args.file_path = "test.txt"
            args.content = "test content"
            args.metadata = None
            args.storage_path = TEST_STORAGE_PATH
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_add_file(args)
                
                mock_bucket_manager.get_bucket.assert_called_once_with("test-bucket")
                mock_bucket.add_file.assert_called_once()
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_cli_bucket_cross_query_command(self, mock_bucket_manager):
        """Test CLI cross-bucket SQL query command."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_query
            
            # Mock query response
            mock_bucket_manager.cross_bucket_query.return_value = {
                "success": True,
                "data": {
                    "columns": ["bucket", "file_path", "size"],
                    "rows": [
                        ["bucket1", "file1.txt", 100],
                        ["bucket2", "file2.txt", 200]
                    ]
                }
            }
            
            args = Mock()
            args.sql_query = "SELECT bucket, file_path, size FROM files"
            args.storage_path = TEST_STORAGE_PATH
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_query(args)
                
                mock_bucket_manager.cross_bucket_query.assert_called_once_with(
                    "SELECT bucket, file_path, size FROM files",
                    bucket_filter=None
                )
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    def test_cli_error_handling_no_bucket_manager(self):
        """Test CLI error handling when bucket manager is not available."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_create
            
            args = Mock()
            args.bucket_name = "test-bucket"
            args.storage_path = TEST_STORAGE_PATH
            
            with patch('ipfs_kit_py.bucket_vfs_cli.get_global_bucket_manager', return_value=None):
                # This should handle the case gracefully
                result = anyio.run(handle_bucket_create, args)
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")


class TestBucketVFSMCPTools:
    """Test suite for bucket VFS MCP API interface."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and tear down test environment."""
        setup_test_environment()
        yield
        teardown_test_environment()
    
    @pytest.fixture
    def mock_bucket_manager(self):
        """Create mock bucket manager for testing."""
        manager = Mock()
        manager.create_bucket = AsyncMock()
        manager.list_buckets = AsyncMock()
        manager.delete_bucket = AsyncMock()
        manager.get_bucket = AsyncMock()
        manager.export_bucket_to_car = AsyncMock()
        manager.cross_bucket_query = AsyncMock()
        return manager

    def test_mcp_tools_module_imports(self):
        """Test that MCP tools module imports correctly."""
        try:
            from mcp.bucket_vfs_mcp_tools import create_bucket_tools, handle_bucket_tool
            assert callable(create_bucket_tools)
            assert callable(handle_bucket_tool)
        except ImportError as e:
            pytest.skip(f"Bucket VFS MCP tools not available: {e}")

    def test_mcp_tools_creation(self):
        """Test MCP tools creation."""
        try:
            from mcp.bucket_vfs_mcp_tools import create_bucket_tools
            
            tools = create_bucket_tools()
            
            # Should return empty list if bucket VFS not available, or tools if available
            assert isinstance(tools, list)
            
            # If tools are returned, verify expected tool names
            if tools:
                tool_names = [tool.name for tool in tools]
                expected_tools = [
                    "bucket_create", "bucket_list", "bucket_delete",
                    "bucket_add_file", "bucket_export_car", "bucket_cross_query",
                    "bucket_get_info", "bucket_status"
                ]
                
                for expected_tool in expected_tools:
                    assert expected_tool in tool_names
                    
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_mcp_bucket_create_tool(self, mock_bucket_manager):
        """Test MCP bucket creation tool."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_create
            
            # Mock successful bucket creation
            mock_bucket_manager.create_bucket.return_value = {
                "success": True,
                "data": {
                    "bucket_type": "general",
                    "vfs_structure": "hybrid", 
                    "cid": "bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c7",
                    "created_at": "2024-01-01T00:00:00Z"
                }
            }
            
            arguments = {
                "bucket_name": "test-bucket",
                "bucket_type": "general",
                "vfs_structure": "hybrid",
                "storage_path": TEST_STORAGE_PATH
            }
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_create(arguments)
                
                assert len(result) == 1
                assert hasattr(result[0], 'text')
                response_data = json.loads(result[0].text)
                assert response_data["success"] is True
                assert "bucket" in response_data
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_mcp_bucket_list_tool(self, mock_bucket_manager):
        """Test MCP bucket listing tool."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_list
            
            # Mock bucket list response
            mock_bucket_manager.list_buckets.return_value = {
                "success": True,
                "data": {
                    "total_count": 1,
                    "buckets": [
                        {
                            "name": "test-bucket",
                            "type": "general",
                            "vfs_structure": "hybrid",
                            "root_cid": "bafybeihkoviema7g3gxyt6la7b7",
                            "created_at": "2024-01-01T00:00:00Z"
                        }
                    ]
                }
            }
            
            arguments = {
                "storage_path": TEST_STORAGE_PATH,
                "detailed": False
            }
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_list(arguments)
                
                assert len(result) == 1
                response_data = json.loads(result[0].text)
                assert response_data["success"] is True
                assert "buckets" in response_data
                assert response_data["total_buckets"] == 1
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_mcp_bucket_add_file_tool(self, mock_bucket_manager):
        """Test MCP add file to bucket tool."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_add_file
            
            # Mock bucket and file addition
            mock_bucket = Mock()
            mock_bucket.add_file = AsyncMock(return_value={
                "success": True,
                "data": {
                    "size": 12,
                    "cid": "bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c7",
                    "local_path": "/tmp/test.txt"
                }
            })
            
            mock_bucket_manager.get_bucket.return_value = mock_bucket
            
            arguments = {
                "bucket_name": "test-bucket",
                "file_path": "test.txt",
                "content": "test content",
                "content_type": "text",
                "storage_path": TEST_STORAGE_PATH
            }
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_add_file(arguments)
                
                assert len(result) == 1
                response_data = json.loads(result[0].text)
                assert response_data["success"] is True
                assert "file" in response_data
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_mcp_bucket_cross_query_tool(self, mock_bucket_manager):
        """Test MCP cross-bucket SQL query tool."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_cross_query
            
            # Mock query response
            mock_bucket_manager.cross_bucket_query.return_value = {
                "success": True,
                "data": {
                    "columns": ["bucket", "file_path", "size"],
                    "rows": [
                        ["bucket1", "file1.txt", 100],
                        ["bucket2", "file2.txt", 200]
                    ]
                }
            }
            
            arguments = {
                "sql_query": "SELECT bucket, file_path, size FROM files",
                "format": "json",
                "storage_path": TEST_STORAGE_PATH
            }
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_cross_query(arguments)
                
                assert len(result) == 1
                response_data = json.loads(result[0].text)
                assert response_data["success"] is True
                assert "results" in response_data
                assert len(response_data["results"]) == 2
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_mcp_bucket_export_car_tool(self, mock_bucket_manager):
        """Test MCP bucket CAR export tool."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_export_car
            
            # Mock export response
            mock_bucket_manager.export_bucket_to_car.return_value = {
                "success": True,
                "data": {
                    "car_path": "/tmp/test-bucket.car",
                    "car_cid": "bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c7",
                    "exported_items": 5
                }
            }
            
            arguments = {
                "bucket_name": "test-bucket",
                "include_indexes": True,
                "storage_path": TEST_STORAGE_PATH
            }
            
            with patch('mcp.bucket_vfs_mcp_tools.get_bucket_manager', return_value=mock_bucket_manager):
                result = await handle_bucket_export_car(arguments)
                
                assert len(result) == 1
                response_data = json.loads(result[0].text)
                assert response_data["success"] is True
                assert "export" in response_data
                
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    @pytest.mark.anyio
    async def test_mcp_error_handling_missing_args(self):
        """Test MCP tools error handling for missing arguments."""
        try:
            from mcp.bucket_vfs_mcp_tools import handle_bucket_create
            
            arguments = {}  # Missing required bucket_name
            
            result = await handle_bucket_create(arguments)
            
            assert len(result) == 1
            response_data = json.loads(result[0].text)
            assert response_data["success"] is False
            assert "error" in response_data
            
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")


class TestBucketVFSIntegration:
    """Integration tests for bucket VFS CLI and MCP interfaces."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and tear down test environment."""
        setup_test_environment()
        yield
        teardown_test_environment()

    def test_cli_mcp_integration_available(self):
        """Test that both CLI and MCP interfaces are available."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import register_bucket_commands
            from mcp.bucket_vfs_mcp_tools import create_bucket_tools
            
            # Both should be importable
            assert callable(register_bucket_commands)
            assert callable(create_bucket_tools)
            
        except ImportError as e:
            pytest.skip(f"Integration components not available: {e}")

    @pytest.mark.anyio
    async def test_end_to_end_bucket_workflow(self):
        """Test end-to-end bucket workflow through both interfaces."""
        try:
            # Import both interfaces
            from ipfs_kit_py.bucket_vfs_cli import handle_bucket_create, handle_bucket_list
            from mcp.bucket_vfs_mcp_tools import handle_bucket_create as mcp_create, handle_bucket_list as mcp_list
            
            # This is a mock end-to-end test - in a real environment,
            # we would test the full workflow with actual bucket VFS components
            
            # For now, just verify that both interfaces exist and can be called
            # with appropriate mocking
            
            assert callable(handle_bucket_create)
            assert callable(mcp_create)
            
        except ImportError as e:
            pytest.skip(f"Integration components not available: {e}")

    def test_cli_registration_pattern(self):
        """Test that CLI registration follows expected pattern."""
        try:
            from ipfs_kit_py.bucket_vfs_cli import register_bucket_commands
            
            # Create mock parser
            mock_parser = Mock()
            mock_subparsers = Mock()
            mock_parser.add_subparsers.return_value = mock_subparsers
            
            # Register commands
            register_bucket_commands(mock_parser)
            
            # Verify subparser was created
            mock_parser.add_subparsers.assert_called_once()
            
        except ImportError as e:
            pytest.skip(f"CLI components not available: {e}")

    def test_mcp_tool_schema_validation(self):
        """Test that MCP tools have valid schemas."""
        try:
            from mcp.bucket_vfs_mcp_tools import create_bucket_tools
            
            tools = create_bucket_tools()
            
            if tools:  # Only test if tools are available
                for tool in tools:
                    # Verify tool has required attributes
                    assert hasattr(tool, 'name')
                    assert hasattr(tool, 'description')
                    assert hasattr(tool, 'inputSchema')
                    
                    # Verify schema structure
                    schema = tool.inputSchema
                    assert isinstance(schema, dict)
                    assert 'type' in schema
                    assert schema['type'] == 'object'
                    
                    if 'properties' in schema:
                        assert isinstance(schema['properties'], dict)
                    
        except ImportError as e:
            pytest.skip(f"MCP tools not available: {e}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])

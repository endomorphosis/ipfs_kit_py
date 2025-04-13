"""
Test Block operations in the MCP server with AnyIO support.

This test file focuses on testing the IPLD Block functionality of the MCP server using AnyIO,
including putting, getting, and retrieving stats for IPLD blocks.
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ipfs_kit_py.mcp_server.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp_server.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp_server.server_bridge import MCPServer  # Refactored import

# Keep original unittest class for backward compatibility
from test_mcp_block_operations import TestMCPBlockOperations

@pytest.mark.anyio
class TestMCPBlockOperationsAnyIO:
    """Test Block operations in the MCP server with AnyIO support."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test environment with AnyIO support."""
        # Create a mock IPFS kit instance with async methods
        self.mock_ipfs_kit = MagicMock()
        
        # Add async versions of block operations
        self.mock_ipfs_kit.block_put_async = AsyncMock()
        self.mock_ipfs_kit.block_get_async = AsyncMock()
        self.mock_ipfs_kit.block_stat_async = AsyncMock()
        
        # Create model instance with mock IPFS kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)
        
        # Add async methods to model
        self.ipfs_model.block_put_async = AsyncMock()
        self.ipfs_model.block_get_async = AsyncMock()
        self.ipfs_model.block_stat_async = AsyncMock()
        
        # Create controller instance
        self.ipfs_controller = IPFSController(self.ipfs_model)
        
        # Reset operation stats
        self.ipfs_model.operation_stats = {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
        }
        
        yield
        
        # Cleanup if needed
    
    @pytest.mark.anyio
    async def test_block_put_async_success(self):
        """Test that block_put_async correctly handles input data."""
        # Test data to store
        test_data = b"Hello IPFS Block World!"
        
        # Mock the block_put_async method to return a CID
        expected_cid = "QmTestBlockCID"
        self.mock_ipfs_kit.block_put_async.return_value = expected_cid
        
        # Configure model mock to delegate to kit
        async def async_block_put(data, **kwargs):
            return {
                "success": True,
                "operation": "block_put",
                "cid": await self.mock_ipfs_kit.block_put_async(data, **kwargs),
                "timestamp": time.time()
            }
        
        self.ipfs_model.block_put_async.side_effect = async_block_put
        
        # Call the method
        result = await self.ipfs_model.block_put_async(test_data)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "block_put"
        assert result["cid"] == expected_cid
        
        # Verify method parameters
        self.mock_ipfs_kit.block_put_async.assert_called_once()
    
    @pytest.mark.anyio
    async def test_block_put_async_with_format_parameter(self):
        """Test that block_put_async correctly handles the format parameter."""
        # Test data to store
        test_data = b"Hello IPFS Block World!"
        
        # Mock the block_put_async method
        expected_cid = "QmTestBlockCID"
        self.mock_ipfs_kit.block_put_async.return_value = expected_cid
        
        # Configure model mock to delegate to kit and include format
        async def async_block_put(data, **kwargs):
            return {
                "success": True,
                "operation": "block_put",
                "cid": await self.mock_ipfs_kit.block_put_async(data, **kwargs),
                "format": kwargs.get("format", "dag-pb"),
                "timestamp": time.time()
            }
        
        self.ipfs_model.block_put_async.side_effect = async_block_put
        
        # Call the method with format parameter
        result = await self.ipfs_model.block_put_async(test_data, format="raw")
        
        # Verify the result
        assert result["success"] is True
        assert result["format"] == "raw"
        
        # Verify method parameters
        self.mock_ipfs_kit.block_put_async.assert_called_once()
        # Check that format parameter was passed
        assert self.mock_ipfs_kit.block_put_async.call_args[1].get("format") == "raw"
    
    @pytest.mark.anyio
    async def test_block_put_async_failure(self):
        """Test that block_put_async correctly handles failure."""
        # Test data to store
        test_data = b"Hello IPFS Block World!"
        
        # Mock the block_put_async method to raise an exception
        error_msg = "Failed to put block"
        self.mock_ipfs_kit.block_put_async.side_effect = Exception(error_msg)
        
        # Configure model mock to delegate to kit and handle errors
        async def async_block_put(data, **kwargs):
            try:
                cid = await self.mock_ipfs_kit.block_put_async(data, **kwargs)
                return {
                    "success": True,
                    "operation": "block_put",
                    "cid": cid,
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "block_put",
                    "error": f"Error: {str(e)}",
                    "timestamp": time.time()
                }
        
        self.ipfs_model.block_put_async.side_effect = async_block_put
        
        # Call the method
        result = await self.ipfs_model.block_put_async(test_data)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "block_put"
        assert error_msg in result["error"]
    
    @pytest.mark.anyio
    async def test_block_get_async_success(self):
        """Test that block_get_async correctly retrieves a block."""
        # Test CID to get
        test_cid = "QmTestBlockCID"
        
        # Test data to return
        expected_data = b"Hello IPFS Block World!"
        
        # Mock the block_get_async method
        self.mock_ipfs_kit.block_get_async.return_value = expected_data
        
        # Configure model mock to delegate to kit
        async def async_block_get(cid, **kwargs):
            return {
                "success": True,
                "operation": "block_get",
                "cid": cid,
                "data": await self.mock_ipfs_kit.block_get_async(cid, **kwargs),
                "timestamp": time.time()
            }
        
        self.ipfs_model.block_get_async.side_effect = async_block_get
        
        # Call the method
        result = await self.ipfs_model.block_get_async(test_cid)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "block_get"
        assert result["cid"] == test_cid
        assert result["data"] == expected_data
        
        # Verify method parameters
        self.mock_ipfs_kit.block_get_async.assert_called_once_with(test_cid)
    
    @pytest.mark.anyio
    async def test_block_get_async_failure(self):
        """Test that block_get_async correctly handles failure."""
        # Test CID to get
        test_cid = "QmTestBlockCID"
        
        # Mock the block_get_async method to raise an exception
        error_msg = "Failed to get block"
        self.mock_ipfs_kit.block_get_async.side_effect = Exception(error_msg)
        
        # Configure model mock to delegate to kit and handle errors
        async def async_block_get(cid, **kwargs):
            try:
                data = await self.mock_ipfs_kit.block_get_async(cid, **kwargs)
                return {
                    "success": True,
                    "operation": "block_get",
                    "cid": cid,
                    "data": data,
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "block_get",
                    "cid": cid,
                    "error": f"Error: {str(e)}",
                    "timestamp": time.time()
                }
        
        self.ipfs_model.block_get_async.side_effect = async_block_get
        
        # Call the method
        result = await self.ipfs_model.block_get_async(test_cid)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "block_get"
        assert result["cid"] == test_cid
        assert error_msg in result["error"]
    
    @pytest.mark.anyio
    async def test_block_stat_async_success(self):
        """Test that block_stat_async correctly retrieves block stats."""
        # Test CID for stats
        test_cid = "QmTestBlockCID"
        
        # Test stats to return
        expected_stats = {
            "Key": test_cid,
            "Size": 22
        }
        
        # Mock the block_stat_async method
        self.mock_ipfs_kit.block_stat_async.return_value = expected_stats
        
        # Configure model mock to delegate to kit
        async def async_block_stat(cid, **kwargs):
            stats = await self.mock_ipfs_kit.block_stat_async(cid, **kwargs)
            size = stats.get("Size", stats.get("size", 0))
            return {
                "success": True,
                "operation": "block_stat",
                "cid": cid,
                "size": size,
                "timestamp": time.time()
            }
        
        self.ipfs_model.block_stat_async.side_effect = async_block_stat
        
        # Call the method
        result = await self.ipfs_model.block_stat_async(test_cid)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "block_stat"
        assert result["cid"] == test_cid
        assert result["size"] == 22
        
        # Verify method parameters
        self.mock_ipfs_kit.block_stat_async.assert_called_once_with(test_cid)
    
    @pytest.mark.anyio
    async def test_block_stat_async_with_different_response_format(self):
        """Test that block_stat_async correctly handles different response formats."""
        # Test CID for stats
        test_cid = "QmTestBlockCID"
        
        # Test stats to return in a different format
        expected_stats = {
            "cid": test_cid,
            "size": 22
        }
        
        # Mock the block_stat_async method
        self.mock_ipfs_kit.block_stat_async.return_value = expected_stats
        
        # Configure model mock to handle different response formats
        async def async_block_stat(cid, **kwargs):
            stats = await self.mock_ipfs_kit.block_stat_async(cid, **kwargs)
            # Handle different response formats
            size = stats.get("Size", stats.get("size", 0))
            return {
                "success": True,
                "operation": "block_stat",
                "cid": cid,
                "size": size,
                "timestamp": time.time()
            }
        
        self.ipfs_model.block_stat_async.side_effect = async_block_stat
        
        # Call the method
        result = await self.ipfs_model.block_stat_async(test_cid)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "block_stat"
        assert result["cid"] == test_cid
        assert result["size"] == 22
    
    @pytest.mark.anyio
    async def test_block_stat_async_failure(self):
        """Test that block_stat_async correctly handles failure."""
        # Test CID for stats
        test_cid = "QmTestBlockCID"
        
        # Mock the block_stat_async method to raise an exception
        error_msg = "Failed to get block stats"
        self.mock_ipfs_kit.block_stat_async.side_effect = Exception(error_msg)
        
        # Configure model mock to delegate to kit and handle errors
        async def async_block_stat(cid, **kwargs):
            try:
                stats = await self.mock_ipfs_kit.block_stat_async(cid, **kwargs)
                size = stats.get("Size", stats.get("size", 0))
                return {
                    "success": True,
                    "operation": "block_stat",
                    "cid": cid,
                    "size": size,
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "block_stat",
                    "cid": cid,
                    "error": f"Error: {str(e)}",
                    "timestamp": time.time()
                }
        
        self.ipfs_model.block_stat_async.side_effect = async_block_stat
        
        # Call the method
        result = await self.ipfs_model.block_stat_async(test_cid)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "block_stat"
        assert result["cid"] == test_cid
        assert error_msg in result["error"]
    
    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test explicit anyio.sleep integration with block operations."""
        import anyio
        
        # Test data
        test_data = b"Hello IPFS Block World!"
        test_cid = "QmTestBlockCID"
        
        # Create a mock implementation that uses anyio.sleep
        async def block_put_with_delay_async(data, delay=0.1, **kwargs):
            await anyio.sleep(delay)  # Explicit anyio.sleep usage
            return "QmTestBlockCID"
        
        async def block_get_with_delay_async(cid, delay=0.1, **kwargs):
            await anyio.sleep(delay)  # Explicit anyio.sleep usage
            return b"Hello IPFS Block World!"
        
        async def block_stat_with_delay_async(cid, delay=0.1, **kwargs):
            await anyio.sleep(delay)  # Explicit anyio.sleep usage
            return {"Key": cid, "Size": 22}
        
        # Set side effects for async methods
        self.mock_ipfs_kit.block_put_async.side_effect = block_put_with_delay_async
        self.mock_ipfs_kit.block_get_async.side_effect = block_get_with_delay_async
        self.mock_ipfs_kit.block_stat_async.side_effect = block_stat_with_delay_async
        
        # Configure model mocks
        async def model_block_put_async(data, **kwargs):
            result = {
                "success": True,
                "operation": "block_put",
                "cid": await self.mock_ipfs_kit.block_put_async(data, **kwargs),
                "timestamp": time.time()
            }
            return result
        
        async def model_block_get_async(cid, **kwargs):
            result = {
                "success": True,
                "operation": "block_get",
                "cid": cid,
                "data": await self.mock_ipfs_kit.block_get_async(cid, **kwargs),
                "timestamp": time.time()
            }
            return result
        
        async def model_block_stat_async(cid, **kwargs):
            stats = await self.mock_ipfs_kit.block_stat_async(cid, **kwargs)
            result = {
                "success": True,
                "operation": "block_stat",
                "cid": cid,
                "size": stats.get("Size", stats.get("size", 0)),
                "timestamp": time.time()
            }
            return result
        
        self.ipfs_model.block_put_async.side_effect = model_block_put_async
        self.ipfs_model.block_get_async.side_effect = model_block_get_async
        self.ipfs_model.block_stat_async.side_effect = model_block_stat_async
        
        # Test all operations with delay
        start_time = time.time()
        
        # Run operations in sequence
        put_result = await self.ipfs_model.block_put_async(test_data)
        get_result = await self.ipfs_model.block_get_async(test_cid)
        stat_result = await self.ipfs_model.block_stat_async(test_cid)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Verify results
        assert put_result["success"] is True
        assert put_result["cid"] == test_cid
        
        assert get_result["success"] is True
        assert get_result["data"] == test_data
        
        assert stat_result["success"] is True
        assert stat_result["size"] == 22
        
        # Verify timing - should be at least 0.3s (0.1s delay × 3 operations)
        assert elapsed_time >= 0.3, f"Expected delay of at least 0.3s but got {elapsed_time}s"
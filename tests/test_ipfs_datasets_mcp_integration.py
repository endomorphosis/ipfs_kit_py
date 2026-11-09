"""
Tests for ipfs_datasets_py integration with MCP infrastructure.

This test suite covers Phase 4 integrations for MCP server components.
"""

import unittest
import tempfile
import shutil
import os
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestEnhancedServerIntegration(unittest.TestCase):
    """Test ipfs_datasets_py integration with Enhanced MCP Server."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.metadata_path = os.path.join(self.temp_dir, "metadata")
        os.makedirs(self.metadata_path, exist_ok=True)
        
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_enhanced_server_without_dataset_storage(self):
        """Test EnhancedMCPServer works without dataset storage."""
        try:
            from ipfs_kit_py.mcp.enhanced_server import EnhancedMCPServer
            
            # Initialize without dataset storage
            server = EnhancedMCPServer(
                metadata_path=self.metadata_path,
                enable_dataset_storage=False
            )
            
            self.assertIsNotNone(server)
            self.assertFalse(server.enable_dataset_storage)
            self.assertIsNone(server.dataset_manager)
            self.assertEqual(len(server._operation_buffer), 0)
            
        except ImportError:
            self.skipTest("EnhancedMCPServer not available")
    
    def test_enhanced_server_with_dataset_storage_enabled(self):
        """Test EnhancedMCPServer with dataset storage enabled."""
        try:
            from ipfs_kit_py.mcp.enhanced_server import EnhancedMCPServer
            from ipfs_kit_py.ipfs_datasets_integration import IPFS_DATASETS_AVAILABLE
            
            if not IPFS_DATASETS_AVAILABLE:
                self.skipTest("ipfs_datasets_py not available")
            
            # Initialize with dataset storage
            server = EnhancedMCPServer(
                metadata_path=self.metadata_path,
                enable_dataset_storage=True,
                dataset_batch_size=10
            )
            
            self.assertIsNotNone(server)
            # May be False if ipfs_datasets_py not available
            if server.enable_dataset_storage:
                self.assertIsNotNone(server.dataset_manager)
                self.assertEqual(server.dataset_batch_size, 10)
            
        except ImportError:
            self.skipTest("EnhancedMCPServer or dependencies not available")
    
    def test_operation_tracking(self):
        """Test that operations are tracked to buffer."""
        try:
            from ipfs_kit_py.mcp.enhanced_server import (
                EnhancedMCPServer, 
                MCPCommandRequest,
                MCPCommandResponse
            )
            from ipfs_kit_py.ipfs_datasets_integration import IPFS_DATASETS_AVAILABLE
            
            if not IPFS_DATASETS_AVAILABLE:
                self.skipTest("ipfs_datasets_py not available")
            
            server = EnhancedMCPServer(
                metadata_path=self.metadata_path,
                enable_dataset_storage=True,
                dataset_batch_size=10
            )
            
            if not server.enable_dataset_storage:
                self.skipTest("Dataset storage not enabled")
            
            # Create test request and response
            request = MCPCommandRequest(
                command="test",
                subcommand="action",
                params={"key": "value"}
            )
            
            response = MCPCommandResponse(
                success=True,
                command="test",
                result={"data": "result"}
            )
            
            # Track operation
            initial_count = len(server._operation_buffer)
            server._track_operation(request, response)
            
            # Verify operation was buffered
            self.assertEqual(len(server._operation_buffer), initial_count + 1)
            
            # Verify operation content
            operation = server._operation_buffer[-1]
            self.assertEqual(operation["command"], "test")
            self.assertEqual(operation["subcommand"], "action")
            self.assertTrue(operation["success"])
            self.assertIn("timestamp", operation)
            
        except ImportError:
            self.skipTest("Dependencies not available")
    
    def test_manual_flush_to_dataset(self):
        """Test manual flush of operations to dataset."""
        try:
            from ipfs_kit_py.mcp.enhanced_server import (
                EnhancedMCPServer,
                MCPCommandRequest,
                MCPCommandResponse
            )
            from ipfs_kit_py.ipfs_datasets_integration import IPFS_DATASETS_AVAILABLE
            
            if not IPFS_DATASETS_AVAILABLE:
                self.skipTest("ipfs_datasets_py not available")
            
            server = EnhancedMCPServer(
                metadata_path=self.metadata_path,
                enable_dataset_storage=True,
                dataset_batch_size=100  # Large batch so auto-flush doesn't trigger
            )
            
            if not server.enable_dataset_storage:
                self.skipTest("Dataset storage not enabled")
            
            # Add some operations to buffer
            for i in range(5):
                request = MCPCommandRequest(command=f"test{i}")
                response = MCPCommandResponse(success=True, command=f"test{i}")
                server._track_operation(request, response)
            
            self.assertEqual(len(server._operation_buffer), 5)
            
            # Manual flush
            server.flush_to_dataset()
            
            # Buffer should be cleared after successful flush
            self.assertEqual(len(server._operation_buffer), 0)
            
        except ImportError:
            self.skipTest("Dependencies not available")
    
    def test_log_export_with_datasets(self):
        """Test log export with dataset storage."""
        try:
            from ipfs_kit_py.mcp.enhanced_server import (
                EnhancedMCPServer,
                MCPCommandRequest,
                LogCommandHandler
            )
            from ipfs_kit_py.ipfs_datasets_integration import IPFS_DATASETS_AVAILABLE
            
            if not IPFS_DATASETS_AVAILABLE:
                self.skipTest("ipfs_datasets_py not available")
            
            server = EnhancedMCPServer(
                metadata_path=self.metadata_path,
                enable_dataset_storage=True
            )
            
            if not server.enable_dataset_storage:
                self.skipTest("Dataset storage not enabled")
            
            # Create some test log files
            logs_dir = Path(self.metadata_path) / "logs"
            logs_dir.mkdir(exist_ok=True)
            
            test_log = logs_dir / "test.log"
            test_log.write_text("Test log entry 1\nTest log entry 2\n")
            
            # Create handler and request
            handler = LogCommandHandler(server)
            request = MCPCommandRequest(
                command="log",
                action="export",
                params={"component": "test", "format": "jsonl"}
            )
            
            # Execute export (async, but we can test the method exists)
            self.assertTrue(hasattr(handler, '_export_logs'))
            
        except ImportError:
            self.skipTest("Dependencies not available")
    
    def test_log_stats_tracking(self):
        """Test log statistics tracking to datasets."""
        try:
            from ipfs_kit_py.mcp.enhanced_server import (
                EnhancedMCPServer,
                MCPCommandRequest,
                LogCommandHandler
            )
            from ipfs_kit_py.ipfs_datasets_integration import IPFS_DATASETS_AVAILABLE
            
            if not IPFS_DATASETS_AVAILABLE:
                self.skipTest("ipfs_datasets_py not available")
            
            server = EnhancedMCPServer(
                metadata_path=self.metadata_path,
                enable_dataset_storage=True
            )
            
            if not server.enable_dataset_storage:
                self.skipTest("Dataset storage not enabled")
            
            # Create some test log files
            logs_dir = Path(self.metadata_path) / "logs"
            logs_dir.mkdir(exist_ok=True)
            
            test_log = logs_dir / "test.log"
            test_log.write_text("Test log content")
            
            # Create handler and request
            handler = LogCommandHandler(server)
            request = MCPCommandRequest(
                command="log",
                action="stats"
            )
            
            # Execute stats (async, but we can test the method exists)
            self.assertTrue(hasattr(handler, '_log_stats'))
            
        except ImportError:
            self.skipTest("Dependencies not available")


class TestMCPErrorHandlingIntegration(unittest.TestCase):
    """Test ipfs_datasets_py integration with MCP error handling."""
    
    def test_error_handler_module_exists(self):
        """Test that MCP error handling module exists."""
        try:
            from ipfs_kit_py.mcp import mcp_error_handling
            self.assertIsNotNone(mcp_error_handling)
        except ImportError:
            self.skipTest("MCP error handling module not available")


class TestJSONRPCMethodsIntegration(unittest.TestCase):
    """Test ipfs_datasets_py integration with JSON-RPC methods."""
    
    def test_jsonrpc_module_exists(self):
        """Test that JSON-RPC methods module exists."""
        try:
            from ipfs_kit_py.mcp import jsonrpc_methods
            self.assertIsNotNone(jsonrpc_methods)
        except ImportError:
            self.skipTest("JSON-RPC methods module not available")


if __name__ == '__main__':
    unittest.main()

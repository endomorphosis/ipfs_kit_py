#!/usr/bin/env python3
"""
Test WAL CLI integration with the main CLI using AnyIO.
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to test
from ipfs_kit_py.cli import parse_args, run_command
from ipfs_kit_py.wal_cli_integration_anyio import register_wal_commands, handle_wal_command, async_handle_wal_command

# Override parse_args for testing to accept arguments
def custom_parse_args(arg_list):
    """Parse arguments for testing"""
    # Create a custom namespace with required attributes for testing
    args = argparse.Namespace()
    
    # Add standard CLI attributes
    args.config = None
    args.format = "text"
    args.param = []
    args.verbose = False
    args.no_color = False
    
    # Parse the command
    if arg_list and len(arg_list) >= 1:
        args.command = arg_list[0]
        
        # Handle WAL command specifically
        if args.command == "wal" and len(arg_list) >= 2:
            args.wal_command = arg_list[1]
            
            # Add specific arguments for different WAL commands
            if args.wal_command == "list" and len(arg_list) >= 3:
                args.operation_type = arg_list[2]
                args.limit = 10
                if "--limit" in arg_list:
                    limit_index = arg_list.index("--limit")
                    if limit_index + 1 < len(arg_list):
                        args.limit = int(arg_list[limit_index + 1])
                args.backend = "all"
            
    return args

# Create a parser for testing
import argparse
def create_test_parser():
    """Create a parser for testing"""
    parser = argparse.ArgumentParser(
        description="IPFS Kit Command Line Interface",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Global options
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument(
        "--format", choices=["text", "json", "yaml"], default="text",
        help="Output format"
    )
    parser.add_argument(
        "--param", action="append", default=[],
        help="Additional parameters in key=value format"
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Register WAL commands explicitly
    register_wal_commands(subparsers)
    
    # Add other necessary commands for testing
    add_parser = subparsers.add_parser("add", help="Add content to IPFS")
    add_parser.add_argument("path", help="File or directory to add")
    
    return parser

# Helper for running async tests
async def run_async_test(async_func, *args, **kwargs):
    """Run an async function in a test"""
    return await async_func(*args, **kwargs)

class TestWALCLIIntegrationAnyIO(unittest.TestCase):
    """Test the WAL CLI integration with AnyIO support."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFSSimpleAPI
        self.mock_api = MagicMock()
        
        # Setup default mock returns
        self.mock_api.get_wal_stats.return_value = {
            "success": True,
            "stats": {
                "total_operations": 42,
                "pending": 5,
                "processing": 2,
                "completed": 30,
                "failed": 5,
                "retrying": 0,
                "partitions": 1,
                "archives": 0,
                "processing_active": True
            }
        }
        
        self.mock_api.get_wal_stats_async = AsyncMock(return_value={
            "success": True,
            "stats": {
                "total_operations": 42,
                "pending": 5,
                "processing": 2,
                "completed": 30,
                "failed": 5,
                "retrying": 0,
                "partitions": 1,
                "archives": 0,
                "processing_active": True
            }
        })
        
        # Set up async and sync method mocks
        self.mock_api.get_pending_operations.return_value = {
            "success": True,
            "operations": [
                {
                    "operation_id": "op1",
                    "operation_type": "add",
                    "backend": "ipfs",
                    "status": "pending",
                    "timestamp": 1617182571000
                }
            ]
        }
        
        self.mock_api.get_pending_operations_async = AsyncMock(return_value={
            "success": True,
            "operations": [
                {
                    "operation_id": "op1",
                    "operation_type": "add",
                    "backend": "ipfs",
                    "status": "pending",
                    "timestamp": 1617182571000
                }
            ]
        })
        
        self.mock_api.get_backend_health.return_value = {
            "success": True,
            "backends": {
                "ipfs": {
                    "status": "healthy",
                    "last_check": 1617182571000,
                    "check_history": [True, True, True, True, True]
                },
                "s3": {
                    "status": "unhealthy",
                    "last_check": 1617182571000,
                    "check_history": [False, False, False, False, False]
                }
            }
        }
        
        self.mock_api.get_backend_health_async = AsyncMock(return_value={
            "success": True,
            "backends": {
                "ipfs": {
                    "status": "healthy",
                    "last_check": 1617182571000,
                    "check_history": [True, True, True, True, True]
                },
                "s3": {
                    "status": "unhealthy",
                    "last_check": 1617182571000,
                    "check_history": [False, False, False, False, False]
                }
            }
        })
        
        # Set up a mock WAL object
        self.mock_api.wal = MagicMock()
        self.mock_api.wal.health_monitor = MagicMock()
        self.mock_api.wal.health_monitor.get_status.return_value = {
            "ipfs": {
                "status": "healthy",
                "last_check": 1617182571000,
                "check_history": [True, True, True, True, True]
            },
            "s3": {
                "status": "unhealthy",
                "last_check": 1617182571000,
                "check_history": [False, False, False, False, False]
            }
        }
        
        # Set up run_async method for AnyIO compatibility
        def run_async_func(async_func, *args, **kwargs):
            """Run async function in a loop"""
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(async_func(*args, **kwargs))
            finally:
                loop.close()
                
        self.mock_api.run_async = MagicMock(side_effect=run_async_func)

    @patch("ipfs_kit_py.wal_cli_integration_anyio.IPFSSimpleAPI")
    def test_register_wal_commands(self, mock_api_class):
        """Test that WAL commands are registered correctly."""
        # Create a parser
        parser = create_test_parser()
        
        # Create a mock ArgumentParser
        mock_parser = MagicMock()
        mock_subparsers = MagicMock()
        mock_parser.add_subparsers.return_value = mock_subparsers
        
        # Register WAL commands
        register_wal_commands(mock_subparsers)
        
        # Check that the WAL command was added
        mock_subparsers.add_parser.assert_any_call(
            "wal",
            help="WAL (Write-Ahead Log) management commands",
        )

    def test_wal_status_command_sync(self):
        """Test the WAL status command using synchronous API."""
        # Set up our mock response with the correct structure
        expected_result = {
            "success": True,
            "stats": {
                "total_operations": 42,
                "pending": 5,
                "failed": 5,
                "completed": 32,
                "processing": 0
            }
        }
        self.mock_api.get_wal_stats.return_value = expected_result
        
        # Parse arguments
        args = custom_parse_args(["wal", "status"])
        
        # Call directly with our mock API
        result = handle_wal_command(args, self.mock_api)
        
        # Check that the correct method was called
        self.mock_api.get_wal_stats.assert_called_once()
        
        # Check result matches our expected data
        self.assertEqual(result["Total operations"], 42)
        self.assertEqual(result["Pending"], 5)
        self.assertEqual(result["Failed"], 5)

    @pytest.mark.asyncio
    async def test_wal_status_command_async(self):
        """Test the WAL status command using async API."""
        # Set up our mock response with the correct structure
        expected_result = {
            "success": True,
            "stats": {
                "total_operations": 42,
                "pending": 5,
                "failed": 5,
                "completed": 32,
                "processing": 0
            }
        }
        self.mock_api.get_wal_stats_async.return_value = expected_result
        
        # Mock the client so it doesn't use run_async
        mock_api = MagicMock()
        mock_api.get_wal_stats_async = AsyncMock(return_value=expected_result)
        
        # Parse arguments
        args = custom_parse_args(["wal", "status"])
        
        # Call directly with our mock API
        result = await async_handle_wal_command(args, mock_api)
        
        # Check that the correct method was called
        mock_api.get_wal_stats_async.assert_called_once()
        
        # Check result matches our expected data
        self.assertEqual(result["Total operations"], 42)
        self.assertEqual(result["Pending"], 5)
        self.assertEqual(result["Failed"], 5)

    def test_wal_list_command_sync(self):
        """Test the WAL list command using synchronous API."""
        # Mock the response with the correct structure
        self.mock_api.get_pending_operations.return_value = {
            "success": True,
            "operations": [
                {
                    "id": "op1",
                    "type": "add",
                    "status": "pending",
                    "created_at": 1617182571000,
                    "backend": "ipfs"
                }
            ]
        }
        
        # Parse arguments
        args = custom_parse_args(["wal", "list", "pending", "--limit", "10"])
        args.operation_type = "pending"
        args.limit = 10
        args.backend = "all"
        
        # Call directly with our mock API
        result = handle_wal_command(args, self.mock_api)
        
        # Check that the correct method was called
        self.mock_api.get_pending_operations.assert_called_once_with(
            limit=10, operation_type="pending", backend="all"
        )
        
        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(len(result["operations"]), 1)

    @pytest.mark.asyncio
    async def test_wal_list_command_async(self):
        """Test the WAL list command using async API."""
        # Mock the response with the correct structure
        expected_response = {
            "success": True,
            "operations": [
                {
                    "id": "op1",
                    "type": "add",
                    "status": "pending",
                    "created_at": 1617182571000,
                    "backend": "ipfs"
                }
            ]
        }
        
        # Mock the client so it doesn't use run_async
        mock_api = MagicMock()
        mock_api.get_pending_operations_async = AsyncMock(return_value=expected_response)
        
        # Parse arguments
        args = custom_parse_args(["wal", "list", "pending", "--limit", "10"])
        args.operation_type = "pending"
        args.limit = 10
        args.backend = "all"
        
        # Call directly with our mock API
        result = await async_handle_wal_command(args, mock_api)
        
        # Check that the correct method was called
        mock_api.get_pending_operations_async.assert_called_once_with(
            limit=10, operation_type="pending", backend="all"
        )
        
        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(len(result["operations"]), 1)

    def test_wal_health_command_sync(self):
        """Test the WAL health command using synchronous API."""
        # Mock the response with the correct structure
        self.mock_api.get_backend_health.return_value = {
            "success": True,
            "backends": {
                "ipfs": {
                    "status": "healthy",
                    "last_check": 1617182571000,
                    "check_history": [True, True, True, True, True]
                },
                "s3": {
                    "status": "unhealthy",
                    "last_check": 1617182571000,
                    "check_history": [False, False, False, False, False]
                }
            }
        }
        
        # Parse arguments
        args = custom_parse_args(["wal", "health"])
        args.wal_command = "health"
        
        # Call directly with our mock API
        result = handle_wal_command(args, self.mock_api)
        
        # Check that the correct method was called
        self.mock_api.get_backend_health.assert_called_once()
        
        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(result["backends"]["ipfs"]["status"], "healthy")
        self.assertEqual(result["backends"]["s3"]["status"], "unhealthy")

    @pytest.mark.asyncio
    async def test_wal_health_command_async(self):
        """Test the WAL health command using async API."""
        # Mock the response with the correct structure
        expected_response = {
            "success": True,
            "backends": {
                "ipfs": {
                    "status": "healthy",
                    "last_check": 1617182571000,
                    "check_history": [True, True, True, True, True]
                },
                "s3": {
                    "status": "unhealthy",
                    "last_check": 1617182571000,
                    "check_history": [False, False, False, False, False]
                }
            }
        }
        
        # Mock the client so it doesn't use run_async
        mock_api = MagicMock()
        mock_api.get_backend_health_async = AsyncMock(return_value=expected_response)
        
        # Parse arguments
        args = custom_parse_args(["wal", "health"])
        args.wal_command = "health"
        
        # Call directly with our mock API
        result = await async_handle_wal_command(args, mock_api)
        
        # Check that the correct method was called
        mock_api.get_backend_health_async.assert_called_once()
        
        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(result["backends"]["ipfs"]["status"], "healthy")
        self.assertEqual(result["backends"]["s3"]["status"], "unhealthy")

    def test_wal_command_error_handling_sync(self):
        """Test error handling in WAL commands with synchronous API."""
        # Mock the API instance to raise an error
        self.mock_api.get_wal_stats.side_effect = ValueError("WAL not enabled")
    
        # Parse arguments
        args = custom_parse_args(["wal", "status"])
        args.wal_command = "status"
    
        # Call directly with our mock API (should raise the error)
        with self.assertRaises(ValueError) as context:
            handle_wal_command(args, self.mock_api)
        
        self.assertEqual(str(context.exception), "WAL not enabled")

    @pytest.mark.asyncio
    async def test_wal_command_error_handling_async(self):
        """Test error handling in WAL commands with async API."""
        # Mock the API instance to raise an error
        mock_api = MagicMock()
        mock_api.get_wal_stats_async = AsyncMock(side_effect=ValueError("WAL not enabled"))
    
        # Parse arguments
        args = custom_parse_args(["wal", "status"])
        args.wal_command = "status"
    
        # Call directly with our mock API (should raise the error)
        with self.assertRaises(ValueError) as context:
            await async_handle_wal_command(args, mock_api)
        
        self.assertEqual(str(context.exception), "WAL not enabled")

    def test_integration_with_run_async(self):
        """Test integration with run_async method for AnyIO support."""
        # Set up our mock response with the correct structure
        expected_result = {
            "success": True,
            "stats": {
                "total_operations": 42,
                "pending": 5,
                "failed": 5,
                "completed": 32,
                "processing": 0
            }
        }
        self.mock_api.get_wal_stats_async.return_value = expected_result
        
        # Parse arguments
        args = custom_parse_args(["wal", "status"])
        
        # Call directly with our mock API
        result = handle_wal_command(args, self.mock_api)
        
        # Check that run_async was called
        self.mock_api.run_async.assert_called_once()
        
        # Verify correct args were passed to run_async
        args_passed = self.mock_api.run_async.call_args[0]
        self.assertEqual(args_passed[0], async_handle_wal_command)
        self.assertEqual(args_passed[1], args)
        self.assertEqual(args_passed[2], self.mock_api)

if __name__ == "__main__":
    unittest.main()
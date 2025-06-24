#!/usr/bin/env python3
"""
Test WAL CLI integration with the main CLI.
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock
from io import StringIO

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to test
from ipfs_kit_py.cli import parse_args, run_command
from ipfs_kit_py.wal_cli_integration import register_wal_commands, handle_wal_command

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

class TestWALCLIIntegration(unittest.TestCase):
    """Test the WAL CLI integration."""

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

    @patch("ipfs_kit_py.wal_cli_integration.IPFSSimpleAPI")
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

    def test_wal_status_command(self):
        """Test the WAL status command."""
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

        # Create a test instance of the handle_wal_command function
        from ipfs_kit_py.wal_cli_integration import handle_wal_command

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

    def test_wal_list_command(self):
        """Test the WAL list command."""
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

        # Import the function
        from ipfs_kit_py.wal_cli_integration import handle_wal_command

        # Call directly with our mock API
        result = handle_wal_command(args, self.mock_api)

        # Check that the correct method was called
        self.mock_api.get_pending_operations.assert_called_once_with(
            limit=10, operation_type="pending", backend="all"
        )

        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(len(result["operations"]), 1)

    def test_wal_health_command(self):
        """Test the WAL health command."""
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

        # Import the function
        from ipfs_kit_py.wal_cli_integration import handle_wal_command

        # Call directly with our mock API
        result = handle_wal_command(args, self.mock_api)

        # Check that the correct method was called
        self.mock_api.get_backend_health.assert_called_once()

        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(result["backends"]["ipfs"]["status"], "healthy")
        self.assertEqual(result["backends"]["s3"]["status"], "unhealthy")

    def test_wal_command_error_handling(self):
        """Test error handling in WAL commands."""
        # Mock the API instance to raise an error
        self.mock_api.get_wal_stats.side_effect = ValueError("WAL not enabled")

        # Parse arguments
        args = custom_parse_args(["wal", "status"])
        args.wal_command = "status"

        # Import the function
        from ipfs_kit_py.wal_cli_integration import handle_wal_command

        # Call directly with our mock API (should raise the error)
        with self.assertRaises(ValueError) as context:
            handle_wal_command(args, self.mock_api)

        self.assertEqual(str(context.exception), "WAL not enabled")

if __name__ == "__main__":
    unittest.main()

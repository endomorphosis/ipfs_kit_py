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
        parser = parse_args([])
        
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

    @patch("ipfs_kit_py.cli.IPFSSimpleAPI")
    def test_wal_status_command(self, mock_api_class):
        """Test the WAL status command."""
        # Mock the API instance
        mock_api_class.return_value = self.mock_api
        
        # Parse arguments
        args = parse_args(["wal", "status"])
        
        # Run command
        result = run_command(args)
        
        # Check that the correct method was called
        self.mock_api.get_wal_stats.assert_called_once()
        
        # Check result
        self.assertEqual(result["Total operations"], 42)
        self.assertEqual(result["Pending"], 5)
        self.assertEqual(result["Failed"], 5)

    @patch("ipfs_kit_py.cli.IPFSSimpleAPI")
    def test_wal_list_command(self, mock_api_class):
        """Test the WAL list command."""
        # Mock the API instance
        mock_api_class.return_value = self.mock_api
        
        # Parse arguments
        args = parse_args(["wal", "list", "pending", "--limit", "10"])
        
        # Run command
        result = run_command(args)
        
        # Check that the correct method was called
        self.mock_api.get_pending_operations.assert_called_once_with(
            limit=10, operation_type="pending", backend="all"
        )
        
        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(len(result["operations"]), 1)
        self.assertEqual(result["operations"][0]["operation_id"], "op1")

    @patch("ipfs_kit_py.cli.IPFSSimpleAPI")
    def test_wal_health_command(self, mock_api_class):
        """Test the WAL health command."""
        # Mock the API instance
        mock_api_class.return_value = self.mock_api
        
        # Parse arguments
        args = parse_args(["wal", "health"])
        
        # Run command
        result = run_command(args)
        
        # Check that the correct method was called
        self.mock_api.get_backend_health.assert_called_once()
        
        # Check result
        self.assertEqual(result["success"], True)
        self.assertEqual(result["backends"]["ipfs"]["status"], "healthy")
        self.assertEqual(result["backends"]["s3"]["status"], "unhealthy")

    @patch("ipfs_kit_py.cli.IPFSSimpleAPI")
    def test_wal_command_error_handling(self, mock_api_class):
        """Test error handling in WAL commands."""
        # Mock the API instance to raise an error
        mock_api_class.return_value = self.mock_api
        self.mock_api.get_wal_stats.side_effect = ValueError("WAL not enabled")
        
        # Parse arguments
        args = parse_args(["wal", "status"])
        
        # Run command (should raise the error)
        with self.assertRaises(ValueError) as context:
            run_command(args)
        
        self.assertEqual(str(context.exception), "WAL not enabled")

if __name__ == "__main__":
    unittest.main()
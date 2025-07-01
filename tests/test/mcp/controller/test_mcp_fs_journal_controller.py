"""
Tests for the Filesystem Journal Controller in the MCP Server.

This module tests the Filesystem Journal Controller endpoints in the MCP server.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.mcp.controllers.fs_journal_controller import FsJournalController as FSJournalController

# Create a mock for FSJournalModel since it doesn't exist yet
from unittest.mock import MagicMock
class FSJournalModel(MagicMock):
    """Mock class for FSJournalModel."""
    pass
from fastapi import APIRouter, Request, Response
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestMCPFSJournalController(unittest.TestCase):
    """Test case for the Filesystem Journal Controller in the MCP Server."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a mock FS Journal Model
        self.mock_fs_journal_model = MagicMock(spec=FSJournalModel)
        
        # Setup mock responses
        self.mock_fs_journal_model.get_status.return_value = {
            "success": True,
            "operation": "get_status",
            "operation_id": "test_op_1",
            "status": "active",
            "journal_path": "/test/journal",
            "enabled": True,
            "timestamp": time.time()
        }
        
        self.mock_fs_journal_model.get_operations.return_value = {
            "success": True,
            "operation": "get_operations",
            "operation_id": "test_op_2",
            "operations": [
                {"op_id": "op1", "type": "add", "timestamp": time.time()},
                {"op_id": "op2", "type": "modify", "timestamp": time.time()}
            ],
            "count": 2,
            "timestamp": time.time()
        }
        
        self.mock_fs_journal_model.get_stats.return_value = {
            "success": True,
            "operation": "get_stats",
            "operation_id": "test_op_3",
            "stats": {
                "total_operations": 100,
                "operations_by_type": {"add": 50, "modify": 30, "delete": 20},
                "avg_operation_time_ms": 15.5
            },
            "timestamp": time.time()
        }
        
        self.mock_fs_journal_model.add_entry.return_value = {
            "success": True,
            "operation": "add_entry",
            "operation_id": "test_op_4",
            "entry_id": "entry123",
            "timestamp": time.time()
        }
        
        # Create the controller
        self.fs_journal_controller = FSJournalController(self.mock_fs_journal_model)
        
        # Create a FastAPI app for testing
        self.app = FastAPI()
        router = APIRouter()
        self.fs_journal_controller.register_routes(router)
        self.app.include_router(router)
        self.client = TestClient(self.app)
    
    def test_get_status(self):
        """Test the status endpoint."""
        response = self.client.get("/fs/journal/status")
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_status")
        self.assertEqual(data["status"], "active")
        self.assertTrue(data["enabled"])
        
        # Verify the model method was called
        self.mock_fs_journal_model.get_status.assert_called_once()
    
    def test_get_operations(self):
        """Test the operations endpoint."""
        response = self.client.get("/fs/journal/operations")
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_operations")
        self.assertEqual(len(data["operations"]), 2)
        self.assertEqual(data["count"], 2)
        
        # Verify the model method was called
        self.mock_fs_journal_model.get_operations.assert_called_once()
    
    def test_get_operations_with_limit(self):
        """Test the operations endpoint with limit parameter."""
        response = self.client.get("/fs/journal/operations?limit=10")
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        
        # Verify the model method was called with correct parameters
        self.mock_fs_journal_model.get_operations.assert_called_with(limit=10)
    
    def test_get_stats(self):
        """Test the stats endpoint."""
        response = self.client.get("/fs/journal/stats")
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_stats")
        self.assertIn("stats", data)
        self.assertEqual(data["stats"]["total_operations"], 100)
        
        # Verify the model method was called
        self.mock_fs_journal_model.get_stats.assert_called_once()
    
    def test_add_entry(self):
        """Test the add_entry endpoint."""
        # Test data
        test_entry = {
            "operation_type": "add",
            "path": "/test/file.txt",
            "metadata": {"size": 1024, "content_type": "text/plain"}
        }
        
        # Make the request
        response = self.client.post(
            "/fs/journal/add_entry",
            json=test_entry
        )
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "add_entry")
        self.assertEqual(data["entry_id"], "entry123")
        
        # Verify the model method was called with correct parameters
        self.mock_fs_journal_model.add_entry.assert_called_once()
        args, kwargs = self.mock_fs_journal_model.add_entry.call_args
        self.assertEqual(kwargs["operation_type"], "add")
        self.assertEqual(kwargs["path"], "/test/file.txt")
        self.assertEqual(kwargs["metadata"]["size"], 1024)
    
    def test_add_entry_error(self):
        """Test error handling in the add_entry endpoint."""
        # Set up the mock to return an error
        self.mock_fs_journal_model.add_entry.return_value = {
            "success": False,
            "operation": "add_entry",
            "error": "Invalid entry data",
            "error_type": "validation_error",
            "timestamp": time.time()
        }
        
        # Test data with invalid fields
        test_entry = {
            "operation_type": "invalid_type",
            "path": ""
        }
        
        # Make the request
        response = self.client.post(
            "/fs/journal/add_entry",
            json=test_entry
        )
        
        # Verify the response
        self.assertEqual(response.status_code, 400)  # Bad request
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)
        self.assertEqual(data["error_type"], "validation_error")


if __name__ == "__main__":
    unittest.main()
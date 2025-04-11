#!/usr/bin/env python3
"""
End-to-End tests for the MCP server.

This module provides end-to-end tests for MCP server that simulate real-world
workflows involving multiple controllers and operations in sequence.
"""

import os
import sys
import json
import time
import unittest
import tempfile
import shutil
import uuid
from unittest.mock import patch, MagicMock
from typing import Dict, List, Optional, Any

# Ensure package is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

try:
    # Try to import anyio for async tests
    import anyio
    ANYIO_AVAILABLE = True
except ImportError:
    ANYIO_AVAILABLE = False
    print("AnyIO not available, skipping async tests")

try:
    # Try to import the MCP server
    from ipfs_kit_py.mcp.server import MCPServer
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("MCP server not available, skipping real implementation tests")
    # Create mock classes for testing
    class MCPServer:
        def __init__(self, **kwargs):
            self.debug_mode = kwargs.get('debug_mode', False)
            
        def register_with_app(self, app, prefix="/mcp"):
            pass

# Import mock implementations if we need them
from test.integration.test_mcp_controller_mocked_integration import (
    MockMCPServer,
    MockIPFSController,
    MockFSJournalController,
    MockWebRTCController,
    MockCLIController
)


@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
@unittest.skip("Skipping due to FastAPI/Pydantic compatibility issues")
class TestMCPEndToEnd(unittest.TestCase):
    """End-to-End tests for the MCP server using mocks."""
    
    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Test data
        self.test_cid = "QmTestCID123456789"
        self.test_content = "Test content for E2E testing"
        self.large_test_content = "Large test content" * 1000
        
        # Create FastAPI app
        self.app = FastAPI()
        
        # Create mock server
        self.server = MockMCPServer()
        
        # Set up default mock responses
        self._setup_mock_responses()
        
        # Register controllers with app
        self.server.register_with_app(self.app)
        
        # Create test client
        self.client = TestClient(self.app)
    
    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _setup_mock_responses(self):
        """Set up default mock responses."""
        # IPFS model
        self.server.ipfs_model.add_json.return_value = {
            "success": True,
            "cid": self.test_cid
        }
        self.server.ipfs_model.cat.return_value = {
            "success": True,
            "content": self.test_content.encode()
        }
        self.server.ipfs_model.pin.return_value = {
            "success": True,
            "cid": self.test_cid
        }
        self.server.ipfs_model.pin_ls.return_value = {
            "success": True,
            "pins": [self.test_cid]
        }
        
        # FS Journal model
        self.server.fs_journal_model.enable_journal.return_value = {
            "success": True,
            "journal_path": os.path.join(self.temp_dir, "journal")
        }
        self.server.fs_journal_model.add_transaction.return_value = {
            "success": True,
            "entry_id": "test-entry-1",
            "path": f"/ipfs/{self.test_cid}"
        }
        self.server.fs_journal_model.get_status.return_value = {
            "success": True,
            "enabled": True,
            "transactions": 1
        }
        
        # WebRTC model
        self.server.webrtc_model.stream_content.return_value = {
            "success": True,
            "server_id": "test-server-1",
            "url": "http://localhost:8080/webrtc/stream"
        }
        self.server.webrtc_model.get_status.return_value = {
            "success": True,
            "status": "streaming",
            "cid": self.test_cid
        }
        
        # CLI model
        self.server.cli_model.execute_command.return_value = {
            "success": True,
            "output": self.test_cid
        }
    
    def test_content_management_workflow(self):
        """Test a complete content management workflow.
        
        This test simulates a real-world workflow for adding, pinning,
        tracking, and streaming content with the MCP server.
        """
        # Step 1: Add content to IPFS
        add_response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content}
        )
        self.assertEqual(add_response.status_code, 200)
        add_result = add_response.json()
        self.assertTrue(add_result["success"])
        cid = add_result["cid"]
        
        # Step 2: Pin the content for persistence
        pin_response = self.client.post(
            "/mcp/ipfs/pin",
            params={"cid": cid}
        )
        self.assertEqual(pin_response.status_code, 200)
        pin_result = pin_response.json()
        self.assertTrue(pin_result["success"])
        
        # Step 3: Verify the pin was added
        pins_response = self.client.get("/mcp/ipfs/pin/ls")
        self.assertEqual(pins_response.status_code, 200)
        pins_result = pins_response.json()
        self.assertTrue(pins_result["success"])
        self.assertIn(cid, pins_result["pins"])
        
        # Step 4: Enable filesystem journaling
        journal_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": os.path.join(self.temp_dir, "journal"),
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_response.status_code, 200)
        journal_result = journal_response.json()
        self.assertTrue(journal_result["success"])
        
        # Step 5: Add a journal entry for the content
        transaction_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "create",
                "path": f"/ipfs/{cid}",
                "data": {
                    "cid": cid,
                    "pinned": True,
                    "content_type": "application/json",
                    "timestamp": time.time()
                }
            }
        )
        self.assertEqual(transaction_response.status_code, 200)
        transaction_result = transaction_response.json()
        self.assertTrue(transaction_result["success"])
        
        # Step 6: Get the content
        cat_response = self.client.get(f"/mcp/ipfs/cat/{cid}")
        self.assertEqual(cat_response.status_code, 200)
        cat_result = cat_response.json()
        self.assertTrue(cat_result["success"])
        
        # Step 7: Stream the content via WebRTC
        stream_response = self.client.post(
            "/mcp/webrtc/stream",
            json={
                "cid": cid,
                "address": "127.0.0.1",
                "port": 8080,
                "quality": "high"
            }
        )
        self.assertEqual(stream_response.status_code, 200)
        stream_result = stream_response.json()
        self.assertTrue(stream_result["success"])
        stream_id = stream_result["server_id"]
        
        # Step 8: Get WebRTC stream status
        status_response = self.client.get(f"/mcp/webrtc/status/{stream_id}")
        self.assertEqual(status_response.status_code, 200)
        status_result = status_response.json()
        self.assertTrue(status_result["success"])
        self.assertEqual(status_result["status"], "streaming")
        
        # Verify all operations were called with the correct data
        self.server.ipfs_model.add_json.assert_called_once()
        self.server.ipfs_model.pin.assert_called_once_with(cid)
        self.server.ipfs_model.pin_ls.assert_called_once()
        self.server.ipfs_model.cat.assert_called_once_with(cid)
        self.server.fs_journal_model.enable_journal.assert_called_once()
        self.server.fs_journal_model.add_transaction.assert_called_once()
        
        add_transaction_call = self.server.fs_journal_model.add_transaction.call_args[0]
        self.assertEqual(add_transaction_call[0], "create")
        self.assertEqual(add_transaction_call[1], f"/ipfs/{cid}")
        self.assertEqual(add_transaction_call[2]["cid"], cid)
        
        self.server.webrtc_model.stream_content.assert_called_once_with(
            cid, "127.0.0.1", 8080, "high"
        )
        self.server.webrtc_model.get_status.assert_called_once_with(stream_id)
    
    def test_cli_based_workflow(self):
        """Test a workflow that uses CLI commands for IPFS operations."""
        # Step 1: Set up CLI mock to return a CID
        self.server.cli_model.execute_command.return_value = {
            "success": True,
            "output": f"{self.test_cid}\n"
        }
        
        # Step 2: Execute IPFS add command via CLI
        cli_response = self.client.post(
            "/mcp/cli/execute",
            json={
                "command": "ipfs add -q test.txt",
                "input": self.test_content
            }
        )
        self.assertEqual(cli_response.status_code, 200)
        cli_result = cli_response.json()
        self.assertTrue(cli_result["success"])
        self.assertIn(self.test_cid, cli_result["output"])
        
        # Extract CID from CLI output
        cid = cli_result["output"].strip()
        
        # Step 3: Use CLI to pin the content
        self.server.cli_model.execute_command.return_value = {
            "success": True,
            "output": f"pinned {cid} recursively\n"
        }
        
        pin_response = self.client.post(
            "/mcp/cli/execute",
            json={
                "command": f"ipfs pin add {cid}"
            }
        )
        self.assertEqual(pin_response.status_code, 200)
        pin_result = pin_response.json()
        self.assertTrue(pin_result["success"])
        
        # Step 4: Use CLI to list pins
        self.server.cli_model.execute_command.return_value = {
            "success": True,
            "output": f"{cid} recursive\n"
        }
        
        ls_response = self.client.post(
            "/mcp/cli/execute",
            json={
                "command": "ipfs pin ls"
            }
        )
        self.assertEqual(ls_response.status_code, 200)
        ls_result = ls_response.json()
        self.assertTrue(ls_result["success"])
        self.assertIn(cid, ls_result["output"])
        
        # Step 5: Use IPFS API to get content
        cat_response = self.client.get(f"/mcp/ipfs/cat/{cid}")
        self.assertEqual(cat_response.status_code, 200)
        cat_result = cat_response.json()
        self.assertTrue(cat_result["success"])
        
        # Step 6: Enable journaling
        journal_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": os.path.join(self.temp_dir, "journal"),
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_response.status_code, 200)
        journal_result = journal_response.json()
        self.assertTrue(journal_result["success"])
        
        # Step 7: Add journal entry for CLI-added content
        transaction_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "create",
                "path": f"/ipfs/{cid}",
                "data": {
                    "cid": cid,
                    "added_via": "cli",
                    "pinned": True
                }
            }
        )
        self.assertEqual(transaction_response.status_code, 200)
        transaction_result = transaction_response.json()
        self.assertTrue(transaction_result["success"])
        
        # Verify CLI and API operations were called correctly
        self.server.cli_model.execute_command.assert_any_call("ipfs add -q test.txt", self.test_content)
        self.server.cli_model.execute_command.assert_any_call(f"ipfs pin add {cid}")
        self.server.cli_model.execute_command.assert_any_call("ipfs pin ls")
        self.server.ipfs_model.cat.assert_called_once_with(cid)
    
    def test_data_migration_workflow(self):
        """Test a workflow for migrating data between storage tiers."""
        # Step 1: Add large content to IPFS
        self.server.ipfs_model.add_json.return_value = {
            "success": True,
            "cid": self.test_cid,
            "size": len(self.large_test_content)
        }
        
        add_response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.large_test_content}
        )
        self.assertEqual(add_response.status_code, 200)
        add_result = add_response.json()
        self.assertTrue(add_result["success"])
        cid = add_result["cid"]
        
        # Step 2: Pin the content for persistence
        pin_response = self.client.post(
            "/mcp/ipfs/pin",
            params={"cid": cid}
        )
        self.assertEqual(pin_response.status_code, 200)
        
        # Step 3: Enable filesystem journaling
        journal_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": os.path.join(self.temp_dir, "journal"),
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_response.status_code, 200)
        
        # Step 4: Add journal entry for tiered storage tracking
        transaction_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "store",
                "path": f"/ipfs/{cid}",
                "data": {
                    "cid": cid,
                    "size": len(self.large_test_content),
                    "tier": "hot",
                    "replicas": 1,
                    "timestamp": time.time()
                }
            }
        )
        self.assertEqual(transaction_response.status_code, 200)
        
        # Step 5: Simulate migration to cold storage by adding a new journal entry
        # In a real implementation, this would involve actual storage tier migration
        migration_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "migrate",
                "path": f"/ipfs/{cid}",
                "data": {
                    "cid": cid,
                    "source_tier": "hot",
                    "target_tier": "cold",
                    "reason": "age",
                    "timestamp": time.time()
                }
            }
        )
        self.assertEqual(migration_response.status_code, 200)
        
        # Step 6: Verify the content is still accessible from cold storage
        # In a real implementation, this would check the cold storage tier
        cat_response = self.client.get(f"/mcp/ipfs/cat/{cid}")
        self.assertEqual(cat_response.status_code, 200)
        
        # Verify operations were called with correct data
        self.server.fs_journal_model.add_transaction.assert_any_call(
            "store", f"/ipfs/{cid}", {"cid": cid, "size": len(self.large_test_content), 
                                      "tier": "hot", "replicas": 1, "timestamp": ANY}
        )
        
        self.server.fs_journal_model.add_transaction.assert_any_call(
            "migrate", f"/ipfs/{cid}", {"cid": cid, "source_tier": "hot", 
                                        "target_tier": "cold", "reason": "age", "timestamp": ANY}
        )
    
    def test_error_handling_workflow(self):
        """Test error handling in a multi-step workflow."""
        # Step 1: Set up ipfs_model.cat to fail
        self.server.ipfs_model.cat.return_value = {
            "success": False,
            "error": "Content not found",
            "error_type": "ContentNotFoundError"
        }
        
        # Step 2: Add content to IPFS
        add_response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content}
        )
        self.assertEqual(add_response.status_code, 200)
        add_result = add_response.json()
        self.assertTrue(add_result["success"])
        cid = add_result["cid"]
        
        # Step A: Try to get non-existent content
        bad_cid = "QmNonExistentCID"
        cat_response = self.client.get(f"/mcp/ipfs/cat/{bad_cid}")
        self.assertEqual(cat_response.status_code, 200)  # API returns 200 with error in body
        cat_result = cat_response.json()
        self.assertFalse(cat_result["success"])
        self.assertIn("error", cat_result)
        
        # Step 3: Even after error, continue with workflow - pin the content
        self.server.ipfs_model.pin.return_value = {
            "success": True,
            "cid": cid
        }
        
        pin_response = self.client.post(
            "/mcp/ipfs/pin",
            params={"cid": cid}
        )
        self.assertEqual(pin_response.status_code, 200)
        pin_result = pin_response.json()
        self.assertTrue(pin_result["success"])
        
        # Step 4: Set up journaling - simulate error
        self.server.fs_journal_model.enable_journal.return_value = {
            "success": False,
            "error": "Permission denied",
            "error_type": "PermissionError"
        }
        
        journal_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": "/nonexistent/path",
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_response.status_code, 200)  # API returns 200 with error in body
        journal_result = journal_response.json()
        self.assertFalse(journal_result["success"])
        self.assertIn("error", journal_result)
        
        # Step 5: Fix journaling and continue workflow
        self.server.fs_journal_model.enable_journal.return_value = {
            "success": True,
            "journal_path": os.path.join(self.temp_dir, "journal")
        }
        
        journal_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": os.path.join(self.temp_dir, "journal"),
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_response.status_code, 200)
        journal_result = journal_response.json()
        self.assertTrue(journal_result["success"])
        
        # Step 6: Continue with workflow - add transaction
        self.server.fs_journal_model.add_transaction.return_value = {
            "success": True,
            "entry_id": "test-entry-1",
            "path": f"/ipfs/{cid}"
        }
        
        transaction_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "create",
                "path": f"/ipfs/{cid}",
                "data": {"cid": cid}
            }
        )
        self.assertEqual(transaction_response.status_code, 200)
        transaction_result = transaction_response.json()
        self.assertTrue(transaction_result["success"])
        
        # Verify error cases were handled correctly
        self.server.ipfs_model.cat.assert_called_once_with(bad_cid)
        
        # First journal call failed, second succeeded
        self.server.fs_journal_model.enable_journal.assert_any_call(
            "/nonexistent/path", 10
        )
        self.server.fs_journal_model.enable_journal.assert_any_call(
            os.path.join(self.temp_dir, "journal"), 10
        )


@unittest.skipIf(not FASTAPI_AVAILABLE or not ANYIO_AVAILABLE, 
                "FastAPI or AnyIO not available")
@unittest.skip("Skipping due to FastAPI/Pydantic compatibility issues")
class TestMCPEndToEndAnyIO(unittest.TestCase):
    """End-to-End tests for the MCP server with AnyIO support."""
    
    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Test data
        self.test_cid = "QmTestCID123456789"
        self.test_content = "Test content for E2E testing with AnyIO"
        
        # Create FastAPI app
        self.app = FastAPI()
        
        # Create mock server (using the same mock servers for now)
        self.server = MockMCPServer()
        
        # Set up default mock responses
        self._setup_mock_responses()
        
        # Register controllers with app
        self.server.register_with_app(self.app)
        
        # Create test client
        self.client = TestClient(self.app)
    
    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _setup_mock_responses(self):
        """Set up default mock responses."""
        # IPFS model
        self.server.ipfs_model.add_json.return_value = {
            "success": True,
            "cid": self.test_cid
        }
        self.server.ipfs_model.cat.return_value = {
            "success": True,
            "content": self.test_content.encode()
        }
        self.server.ipfs_model.pin.return_value = {
            "success": True,
            "cid": self.test_cid
        }
        
        # FS Journal model
        self.server.fs_journal_model.enable_journal.return_value = {
            "success": True,
            "journal_path": os.path.join(self.temp_dir, "journal")
        }
        self.server.fs_journal_model.add_transaction.return_value = {
            "success": True,
            "entry_id": "test-entry-1",
            "path": f"/ipfs/{self.test_cid}"
        }
        
        # WebRTC model
        self.server.webrtc_model.stream_content.return_value = {
            "success": True,
            "server_id": "test-server-1",
            "url": "http://localhost:8080/webrtc/stream"
        }
    
    async def _async_content_workflow(self):
        """Run async content workflow test."""
        # Step 1: Add content to IPFS
        add_response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content}
        )
        self.assertEqual(add_response.status_code, 200)
        add_result = add_response.json()
        self.assertTrue(add_result["success"])
        cid = add_result["cid"]
        
        # Step 2: Pin the content
        pin_response = self.client.post(
            "/mcp/ipfs/pin",
            params={"cid": cid}
        )
        self.assertEqual(pin_response.status_code, 200)
        pin_result = pin_response.json()
        self.assertTrue(pin_result["success"])
        
        # Step 3: Enable filesystem journaling
        journal_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": os.path.join(self.temp_dir, "journal"),
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_response.status_code, 200)
        journal_result = journal_response.json()
        self.assertTrue(journal_result["success"])
        
        # Step 4: Add a journal entry for the content
        transaction_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "create",
                "path": f"/ipfs/{cid}",
                "data": {
                    "cid": cid,
                    "pinned": True,
                    "content_type": "application/json",
                    "timestamp": time.time()
                }
            }
        )
        self.assertEqual(transaction_response.status_code, 200)
        transaction_result = transaction_response.json()
        self.assertTrue(transaction_result["success"])
        
        # Step 5: Get the content
        cat_response = self.client.get(f"/mcp/ipfs/cat/{cid}")
        self.assertEqual(cat_response.status_code, 200)
        cat_result = cat_response.json()
        self.assertTrue(cat_result["success"])
        
        # Step 6: Stream the content
        stream_response = self.client.post(
            "/mcp/webrtc/stream",
            json={
                "cid": cid,
                "address": "127.0.0.1",
                "port": 8080,
                "quality": "high"
            }
        )
        self.assertEqual(stream_response.status_code, 200)
        stream_result = stream_response.json()
        self.assertTrue(stream_result["success"])
        
        # Verify method calls
        self.server.ipfs_model.add_json.assert_called_once()
        self.server.ipfs_model.pin.assert_called_once_with(cid)
        self.server.ipfs_model.cat.assert_called_once_with(cid)
        self.server.fs_journal_model.enable_journal.assert_called_once()
        self.server.fs_journal_model.add_transaction.assert_called_once()
        self.server.webrtc_model.stream_content.assert_called_once()
    
    def test_async_content_workflow(self):
        """Test an async content workflow."""
        anyio.run(self._async_content_workflow)


if __name__ == "__main__":
    unittest.main()
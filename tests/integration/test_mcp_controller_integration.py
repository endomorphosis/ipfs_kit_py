#!/usr/bin/env python3
"""
Integration tests for MCP server controllers.

This test file verifies interactions between multiple controllers in the MCP server.
It focuses on testing workflows that involve multiple controllers working together.

Key controller interactions tested:
1. IPFS Controller + FS Journal Controller: Add content via IPFS then track in journal
2. WebRTC Controller + IPFS Controller: Stream content retrieved via IPFS
3. CLI Controller + IPFS Controller: Execute CLI commands that interact with IPFS
"""

import os
import sys
import time
import json
import shutil
import anyio
import unittest
import tempfile
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request, Response, APIRouter
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

# Import MCP server
try:
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    from ipfs_kit_py.mcp.controllers.fs_journal_controller import FsJournalController
    from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController
    from ipfs_kit_py.mcp.controllers.cli_controller import CLIController
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    MCP_AVAILABLE = True
except ImportError as e:
    MCP_AVAILABLE = False
    print(f"MCP server not available, skipping tests: {e}")

@unittest.skipIf(not MCP_AVAILABLE, "MCP Server components not available")
@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestMCPControllerIntegration(unittest.TestCase):
    """Test integration between MCP controllers."""

    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp(prefix="mcp_integration_test_")
        
        # Create patched server with mock IPFS kit
        self.mock_ipfs_kit = MagicMock()
        self.server_patch = patch('ipfs_kit_py.mcp.models.ipfs_model.ipfs_kit', return_value=self.mock_ipfs_kit)
        
        self.server_patch.start()
        
        # Create a test-specific persistence path
        self.persistence_path = os.path.join(self.temp_dir, "cache")
        os.makedirs(self.persistence_path, exist_ok=True)
        
        # Initialize server with debugging enabled
        self.server = MCPServer(
            debug_mode=True,
            log_level="DEBUG",
            persistence_path=self.persistence_path,
            isolation_mode=True
        )
        
        # Create FastAPI app and register routes
        self.app = FastAPI(title="MCP Integration Test")
        self.server.register_with_app(self.app)
        
        # Create test client
        self.client = TestClient(self.app)
        
        # Set up test CID and content
        self.test_cid = "QmTESTCID123456789"
        self.test_content = b"Test content for integration testing"
        self.test_content_str = self.test_content.decode("utf-8")
        
        # Mock responses for API calls
        self._setup_mock_responses()

    def tearDown(self):
        """Clean up after the test."""
        # Stop the server patch
        self.server_patch.stop()
        
        # Clean up temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _setup_mock_responses(self):
        """Set up mock responses for IPFS kit calls."""
        # For IPFS add
        self.mock_ipfs_kit.add.return_value = {
            "success": True,
            "cid": self.test_cid
        }
        
        # For IPFS cat
        self.mock_ipfs_kit.cat.return_value = {
            "success": True,
            "content": self.test_content
        }
        
        # For IPFS pin
        self.mock_ipfs_kit.pin.return_value = {
            "success": True,
            "cid": self.test_cid
        }
        
        # For filesystem journal
        self.mock_ipfs_kit.enable_filesystem_journaling.return_value = {
            "success": True,
            "journal_path": "/mock/journal/path"
        }
        
        # Create mock filesystem journal
        self.mock_ipfs_kit.filesystem_journal = MagicMock()
        self.mock_ipfs_kit.filesystem_journal.add_journal_entry.return_value = {
            "success": True,
            "entry_id": "mock-entry-1",
            "timestamp": time.time()
        }
        
        # For WebRTC streaming
        self.mock_ipfs_kit.stream_content_webrtc.return_value = {
            "success": True,
            "server_id": "mock-webrtc-server-1",
            "url": "http://localhost:8080/webrtc/mock-stream"
        }
        
        # For CLI commands
        self.mock_ipfs_kit.execute_command.return_value = {
            "success": True,
            "output": "Command executed successfully"
        }

    def test_ipfs_fs_journal_integration(self):
        """Test integration between IPFS Controller and FS Journal Controller.
        
        Workflow:
        1. Add content to IPFS
        2. Enable filesystem journaling
        3. Add a journal entry for the content
        4. Verify journal entry was created
        """
        # Step 1: Add content to IPFS
        add_response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content_str}
        )
        self.assertEqual(add_response.status_code, 200)
        add_result = add_response.json()
        self.assertTrue(add_result["success"])
        self.assertEqual(add_result["cid"], self.test_cid)
        
        # Step 2: Enable filesystem journaling
        journal_enable_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": os.path.join(self.temp_dir, "journal"),
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_enable_response.status_code, 200)
        journal_enable_result = journal_enable_response.json()
        self.assertTrue(journal_enable_result["success"])
        
        # Step 3: Add a journal entry for the content
        journal_entry_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "create",
                "path": f"/ipfs/{self.test_cid}",
                "data": {"cid": self.test_cid}
            }
        )
        self.assertEqual(journal_entry_response.status_code, 200)
        journal_entry_result = journal_entry_response.json()
        self.assertTrue(journal_entry_result["success"])
        self.assertIn("entry_id", journal_entry_result)
        
        # Verify the mock was called correctly with coordinated data
        self.mock_ipfs_kit.add_json.assert_called_once()
        self.mock_ipfs_kit.enable_filesystem_journaling.assert_called_once()
        self.mock_ipfs_kit.filesystem_journal.add_journal_entry.assert_called_once()
        # Verify the CID from the IPFS add was used in the journal entry
        add_journal_call_args = self.mock_ipfs_kit.filesystem_journal.add_journal_entry.call_args[1]
        self.assertEqual(add_journal_call_args["path"], f"/ipfs/{self.test_cid}")
        self.assertEqual(add_journal_call_args["data"]["cid"], self.test_cid)

    def test_webrtc_ipfs_integration(self):
        """Test integration between WebRTC Controller and IPFS Controller.
        
        Workflow:
        1. Add content to IPFS
        2. Pin the content
        3. Stream the content via WebRTC
        4. Verify streaming server is created for the pinned content
        """
        # Step 1: Add content to IPFS
        add_response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content_str}
        )
        self.assertEqual(add_response.status_code, 200)
        add_result = add_response.json()
        self.assertTrue(add_result["success"])
        
        # Step 2: Pin the content
        pin_response = self.client.post(
            "/mcp/ipfs/pin",
            params={"cid": self.test_cid}
        )
        self.assertEqual(pin_response.status_code, 200)
        pin_result = pin_response.json()
        self.assertTrue(pin_result["success"])
        
        # Step 3: Stream the content via WebRTC
        stream_response = self.client.post(
            "/mcp/webrtc/stream",
            json={
                "cid": self.test_cid,
                "address": "127.0.0.1",
                "port": 8080,
                "quality": "medium"
            }
        )
        self.assertEqual(stream_response.status_code, 200)
        stream_result = stream_response.json()
        self.assertTrue(stream_result["success"])
        self.assertIn("server_id", stream_result)
        
        # Verify mocks were called in the correct sequence
        self.mock_ipfs_kit.add_json.assert_called_once()
        self.mock_ipfs_kit.pin.assert_called_once_with(self.test_cid)
        self.mock_ipfs_kit.stream_content_webrtc.assert_called_once()
        # Verify the CID was properly passed from IPFS controller to WebRTC controller
        stream_call_args = self.mock_ipfs_kit.stream_content_webrtc.call_args[1]
        self.assertEqual(stream_call_args["cid"], self.test_cid)

    def test_cli_ipfs_integration(self):
        """Test integration between CLI Controller and IPFS Controller.
        
        Workflow:
        1. Execute CLI command to add content
        2. Verify IPFS command execution
        3. Retrieve content via IPFS controller
        4. Verify content is consistent across controllers
        """
        # Mock the CLI command to add content
        ipfs_add_command = f"ipfs add -q --stdin-name=test.txt"
        mock_command_output = f"{self.test_cid}"
        self.mock_ipfs_kit.execute_command.return_value = {
            "success": True,
            "output": mock_command_output
        }
        
        # Step 1: Execute CLI command
        cli_response = self.client.post(
            "/mcp/cli/execute",
            json={
                "command": ipfs_add_command,
                "input": self.test_content_str
            }
        )
        self.assertEqual(cli_response.status_code, 200)
        cli_result = cli_response.json()
        self.assertTrue(cli_result["success"])
        self.assertIn(self.test_cid, cli_result["output"])
        
        # Setup mock for cat
        self.mock_ipfs_kit.cat.return_value = {
            "success": True,
            "content": self.test_content
        }
        
        # Step 2: Retrieve the content via IPFS controller
        cat_response = self.client.get(
            f"/mcp/ipfs/cat/{self.test_cid}"
        )
        self.assertEqual(cat_response.status_code, 200)
        
        # For binary content, FastAPI will return it as is
        self.assertEqual(cat_response.content, self.test_content)
        
        # Verify the mocks were called correctly
        self.mock_ipfs_kit.execute_command.assert_called_once()
        self.mock_ipfs_kit.cat.assert_called_once_with(self.test_cid)
        
        # Verify the command had the right input
        execute_call_args = self.mock_ipfs_kit.execute_command.call_args[1]
        self.assertEqual(execute_call_args["command"], ipfs_add_command)
        self.assertEqual(execute_call_args["input"], self.test_content_str)

    def test_full_ipfs_webrtc_fs_journal_workflow(self):
        """Test a complete workflow involving multiple controllers.
        
        Workflow:
        1. Add content to IPFS
        2. Pin the content
        3. Enable filesystem journaling
        4. Track the content in the filesystem journal
        5. Stream the content via WebRTC
        6. Verify everything is tracked properly
        """
        # Step 1: Add content to IPFS
        add_response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content_str}
        )
        self.assertEqual(add_response.status_code, 200)
        add_result = add_response.json()
        self.assertTrue(add_result["success"])
        
        # Step 2: Pin the content
        pin_response = self.client.post(
            "/mcp/ipfs/pin",
            params={"cid": self.test_cid}
        )
        self.assertEqual(pin_response.status_code, 200)
        pin_result = pin_response.json()
        self.assertTrue(pin_result["success"])
        
        # Step 3: Enable filesystem journaling
        journal_enable_response = self.client.post(
            "/mcp/fs-journal/enable",
            json={
                "journal_path": os.path.join(self.temp_dir, "journal"),
                "checkpoint_interval": 10
            }
        )
        self.assertEqual(journal_enable_response.status_code, 200)
        journal_enable_result = journal_enable_response.json()
        self.assertTrue(journal_enable_result["success"])
        
        # Step 4: Track the content in the filesystem journal
        journal_entry_response = self.client.post(
            "/mcp/fs-journal/transactions",
            json={
                "operation_type": "create",
                "path": f"/ipfs/{self.test_cid}",
                "data": {"cid": self.test_cid, "pinned": True}
            }
        )
        self.assertEqual(journal_entry_response.status_code, 200)
        journal_entry_result = journal_entry_response.json()
        self.assertTrue(journal_entry_result["success"])
        
        # Step 5: Stream the content via WebRTC
        stream_response = self.client.post(
            "/mcp/webrtc/stream",
            json={
                "cid": self.test_cid,
                "address": "127.0.0.1",
                "port": 8080,
                "quality": "medium"
            }
        )
        self.assertEqual(stream_response.status_code, 200)
        stream_result = stream_response.json()
        self.assertTrue(stream_result["success"])
        
        # Step 6: Get filesystem journal status to verify tracking
        journal_status_response = self.client.get("/mcp/fs-journal/status")
        self.assertEqual(journal_status_response.status_code, 200)
        journal_status_result = journal_status_response.json()
        self.assertTrue(journal_status_result["success"])
        
        # Verify all mocks were called with coordinated data
        self.mock_ipfs_kit.add_json.assert_called_once()
        self.mock_ipfs_kit.pin.assert_called_once_with(self.test_cid)
        self.mock_ipfs_kit.enable_filesystem_journaling.assert_called_once()
        self.mock_ipfs_kit.filesystem_journal.add_journal_entry.assert_called_once()
        self.mock_ipfs_kit.stream_content_webrtc.assert_called_once()
        
        # Verify consistent data passing between controllers
        stream_call_args = self.mock_ipfs_kit.stream_content_webrtc.call_args[1]
        self.assertEqual(stream_call_args["cid"], self.test_cid)
        
        journal_call_args = self.mock_ipfs_kit.filesystem_journal.add_journal_entry.call_args[1]
        self.assertEqual(journal_call_args["path"], f"/ipfs/{self.test_cid}")
        self.assertEqual(journal_call_args["data"]["cid"], self.test_cid)
        self.assertTrue(journal_call_args["data"]["pinned"])

if __name__ == "__main__":
    unittest.main()
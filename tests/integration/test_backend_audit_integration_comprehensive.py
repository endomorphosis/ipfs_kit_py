#!/usr/bin/env python3
"""
Integration Tests for Backend-Audit Integration (Phase 5)

Tests automatic audit tracking for:
- Backend operations (create, update, delete, test)
- VFS bucket operations (create, mount, write, read, delete)
- Cross-system audit trail
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger
from ipfs_kit_py.mcp.servers.audit_mcp_tools import (
    audit_track_backend,
    audit_track_vfs,
    audit_view
)


class TestBackendAuditIntegration(unittest.TestCase):
    """Test automatic audit tracking for backend operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_backend_create_tracked(self, mock_get_logger):
        """Test that backend creation is tracked in audit log."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        # Simulate backend creation
        result = audit_track_backend(
            backend_id="s3_backend_1",
            operation="create",
            user_id="admin",
            details={"backend_type": "s3", "region": "us-east-1"}
        )
        
        self.assertTrue(result.get("success"))
        mock_logger.log_event.assert_called_once()
        
        # Verify audit event details
        call_args = mock_logger.log_event.call_args
        event = call_args[0][0]
        self.assertEqual(event.action, "create")
        self.assertIn("backend_type", event.details)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_backend_update_tracked(self, mock_get_logger):
        """Test that backend updates are tracked."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_backend(
            backend_id="s3_backend_1",
            operation="update",
            user_id="admin",
            details={"changed_fields": ["credentials"]}
        )
        
        self.assertTrue(result.get("success"))
        mock_logger.log_event.assert_called_once()
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_backend_delete_tracked(self, mock_get_logger):
        """Test that backend deletion is tracked."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_backend(
            backend_id="s3_backend_1",
            operation="delete",
            user_id="admin"
        )
        
        self.assertTrue(result.get("success"))
        mock_logger.log_event.assert_called_once()


class TestVFSAuditIntegration(unittest.TestCase):
    """Test automatic audit tracking for VFS operations."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_vfs_bucket_create_tracked(self, mock_get_logger):
        """Test that VFS bucket creation is tracked."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_vfs(
            bucket_id="bucket_1",
            operation="create",
            user_id="user1"
        )
        
        self.assertTrue(result.get("success"))
        mock_logger.log_event.assert_called_once()
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_vfs_write_tracked(self, mock_get_logger):
        """Test that VFS writes are tracked."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_vfs(
            bucket_id="bucket_1",
            operation="write",
            path="/data/file.txt",
            user_id="user1",
            details={"size": 1024}
        )
        
        self.assertTrue(result.get("success"))
        mock_logger.log_event.assert_called_once()
        
        # Verify path is included
        call_args = mock_logger.log_event.call_args
        event = call_args[0][0]
        self.assertIn("/data/file.txt", event.resource)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_vfs_read_tracked(self, mock_get_logger):
        """Test that VFS reads are tracked."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_vfs(
            bucket_id="bucket_1",
            operation="read",
            path="/data/file.txt",
            user_id="user1"
        )
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_vfs_delete_tracked(self, mock_get_logger):
        """Test that VFS deletions are tracked."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_vfs(
            bucket_id="bucket_1",
            operation="delete",
            path="/data/file.txt",
            user_id="user1"
        )
        
        self.assertTrue(result.get("success"))


class TestConsolidatedAuditTrail(unittest.TestCase):
    """Test consolidated audit trail across all systems."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_query_backend_and_vfs_events(self, mock_get_logger):
        """Test querying events from both backend and VFS."""
        mock_logger = Mock()
        mock_logger.query_events.return_value = [
            {"event_type": "backend", "action": "create", "resource": "s3_backend_1"},
            {"event_type": "vfs", "action": "write", "resource": "bucket_1:/file.txt"}
        ]
        mock_get_logger.return_value = mock_logger
        
        result = audit_view(
            event_type="backend,vfs",
            hours_ago=24
        )
        
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("count"), 2)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_cross_system_correlation(self, mock_get_logger):
        """Test correlating events across backend and VFS."""
        mock_logger = Mock()
        # Simulate correlated events: backend create followed by VFS mount
        mock_logger.query_events.return_value = [
            {
                "timestamp": "2024-01-01T00:00:00",
                "event_type": "backend",
                "action": "create",
                "resource": "s3_backend_1",
                "user_id": "admin"
            },
            {
                "timestamp": "2024-01-01T00:00:05",
                "event_type": "vfs",
                "action": "mount",
                "resource": "bucket_1",
                "user_id": "admin",
                "details": {"backend": "s3_backend_1"}
            }
        ]
        mock_get_logger.return_value = mock_logger
        
        result = audit_view(user_id="admin", hours_ago=1)
        
        self.assertTrue(result.get("success"))
        events = result.get("events", [])
        self.assertEqual(len(events), 2)
        
        # Verify events are related
        self.assertEqual(events[0]["user_id"], events[1]["user_id"])


class TestAuditIntegrationEndToEnd(unittest.TestCase):
    """End-to-end integration tests for audit trail."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_complete_workflow_audit_trail(self, mock_get_logger):
        """Test complete workflow generates proper audit trail."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_logger.query_events.return_value = []
        mock_get_logger.return_value = mock_logger
        
        # Simulate complete workflow:
        # 1. Create backend
        audit_track_backend(
            backend_id="s3_backend_1",
            operation="create",
            user_id="admin"
        )
        
        # 2. Create VFS bucket
        audit_track_vfs(
            bucket_id="bucket_1",
            operation="create",
            user_id="admin"
        )
        
        # 3. Write file
        audit_track_vfs(
            bucket_id="bucket_1",
            operation="write",
            path="/data/file.txt",
            user_id="user1"
        )
        
        # 4. Read file
        audit_track_vfs(
            bucket_id="bucket_1",
            operation="read",
            path="/data/file.txt",
            user_id="user2"
        )
        
        # Verify all operations were logged
        self.assertEqual(mock_logger.log_event.call_count, 4)


if __name__ == '__main__':
    unittest.main()

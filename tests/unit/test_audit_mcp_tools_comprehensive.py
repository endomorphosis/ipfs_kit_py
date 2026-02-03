#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Audit MCP Tools (Phase 2)

Tests all MCP tools for audit operations including:
- audit_view
- audit_query  
- audit_export
- audit_report
- audit_statistics
- audit_track_backend
- audit_track_vfs
- audit_integrity_check
- audit_retention_policy
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.mcp.servers.audit_mcp_tools import (
    audit_view,
    audit_query,
    audit_export,
    audit_report,
    audit_statistics,
    audit_track_backend,
    audit_track_vfs,
    audit_integrity_check,
    audit_retention_policy
)


class TestAuditViewMCPTool(unittest.TestCase):
    """Test audit_view MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_view_default_params(self, mock_get_logger):
        """Test audit_view with default parameters."""
        mock_logger = Mock()
        mock_logger.query_events.return_value = [
            {"event_type": "authentication", "action": "login", "timestamp": "2024-01-01T00:00:00"}
        ]
        mock_get_logger.return_value = mock_logger
        
        result = audit_view()
        
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertIn("events", result)
        self.assertIn("count", result)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_view_with_filters(self, mock_get_logger):
        """Test audit_view with filtering parameters."""
        mock_logger = Mock()
        mock_logger.query_events.return_value = []
        mock_get_logger.return_value = mock_logger
        
        result = audit_view(
            limit=50,
            event_type="authentication",
            user_id="test_user",
            status="failure"
        )
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        mock_logger.query_events.assert_called_once()
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_view_error_handling(self, mock_get_logger):
        """Test audit_view error handling."""
        mock_logger = Mock()
        mock_logger.query_events.side_effect = Exception("Test error")
        mock_get_logger.return_value = mock_logger
        
        result = audit_view()
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)


class TestAuditQueryMCPTool(unittest.TestCase):
    """Test audit_query MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_query_basic(self, mock_get_logger):
        """Test basic audit_query."""
        mock_logger = Mock()
        mock_logger.query_events.return_value = []
        mock_get_logger.return_value = mock_logger
        
        result = audit_query()
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("events", result)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_query_with_time_range(self, mock_get_logger):
        """Test audit_query with time range."""
        mock_logger = Mock()
        mock_logger.query_events.return_value = []
        mock_get_logger.return_value = mock_logger
        
        start_time = "2024-01-01T00:00:00"
        end_time = "2024-01-31T23:59:59"
        
        result = audit_query(
            start_time=start_time,
            end_time=end_time
        )
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_query_with_multiple_filters(self, mock_get_logger):
        """Test audit_query with multiple filters."""
        mock_logger = Mock()
        mock_logger.query_events.return_value = []
        mock_get_logger.return_value = mock_logger
        
        result = audit_query(
            event_types=["authentication", "authorization"],
            users=["user1", "user2"],
            statuses=["success", "failure"],
            limit=100
        )
        
        self.assertTrue(result.get("success"))


class TestAuditExportMCPTool(unittest.TestCase):
    """Test audit_export MCP tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.test_dir, "export.json")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_export_json(self, mock_get_logger):
        """Test exporting audit logs to JSON."""
        mock_logger = Mock()
        mock_logger.export_events.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_export(
            output_file=self.output_file,
            format="json"
        )
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_audit_export_csv(self, mock_get_logger):
        """Test exporting audit logs to CSV."""
        mock_logger = Mock()
        mock_logger.export_events.return_value = True
        mock_get_logger.return_value = mock_logger
        
        csv_file = os.path.join(self.test_dir, "export.csv")
        result = audit_export(
            output_file=csv_file,
            format="csv"
        )
        
        self.assertTrue(result.get("success"))


class TestAuditReportMCPTool(unittest.TestCase):
    """Test audit_report MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_extensions')
    def test_audit_report_summary(self, mock_get_extensions):
        """Test generating summary report."""
        mock_extensions = Mock()
        mock_extensions.generate_report.return_value = {
            "total_events": 100,
            "by_type": {}
        }
        mock_get_extensions.return_value = mock_extensions
        
        result = audit_report(report_type="summary")
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("report", result)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_extensions')
    def test_audit_report_security(self, mock_get_extensions):
        """Test generating security report."""
        mock_extensions = Mock()
        mock_extensions.generate_report.return_value = {
            "failed_logins": 5,
            "denied_access": 3
        }
        mock_get_extensions.return_value = mock_extensions
        
        result = audit_report(report_type="security")
        
        self.assertTrue(result.get("success"))
        self.assertIn("report", result)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_extensions')
    def test_audit_report_compliance(self, mock_get_extensions):
        """Test generating compliance report."""
        mock_extensions = Mock()
        mock_extensions.generate_report.return_value = {
            "total_events": 100,
            "audit_coverage": "95%"
        }
        mock_get_extensions.return_value = mock_extensions
        
        result = audit_report(report_type="compliance")
        
        self.assertTrue(result.get("success"))


class TestAuditStatisticsMCPTool(unittest.TestCase):
    """Test audit_statistics MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_extensions')
    def test_audit_statistics(self, mock_get_extensions):
        """Test getting audit statistics."""
        mock_extensions = Mock()
        mock_extensions.get_statistics.return_value = {
            "total_events": 1000,
            "events_by_type": {},
            "events_by_status": {}
        }
        mock_get_extensions.return_value = mock_extensions
        
        result = audit_statistics()
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("statistics", result)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_extensions')
    def test_audit_statistics_with_time_range(self, mock_get_extensions):
        """Test getting statistics for specific time range."""
        mock_extensions = Mock()
        mock_extensions.get_statistics.return_value = {
            "total_events": 100
        }
        mock_get_extensions.return_value = mock_extensions
        
        result = audit_statistics(hours_ago=24)
        
        self.assertTrue(result.get("success"))


class TestAuditTrackBackendMCPTool(unittest.TestCase):
    """Test audit_track_backend MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_track_backend_create(self, mock_get_logger):
        """Test tracking backend creation."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_backend(
            backend_id="s3_backend_1",
            operation="create",
            user_id="admin",
            details={"backend_type": "s3"}
        )
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        mock_logger.log_event.assert_called_once()
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_track_backend_update(self, mock_get_logger):
        """Test tracking backend update."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_backend(
            backend_id="s3_backend_1",
            operation="update",
            user_id="admin"
        )
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_track_backend_delete(self, mock_get_logger):
        """Test tracking backend deletion."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_backend(
            backend_id="s3_backend_1",
            operation="delete",
            user_id="admin"
        )
        
        self.assertTrue(result.get("success"))


class TestAuditTrackVFSMCPTool(unittest.TestCase):
    """Test audit_track_vfs MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_track_vfs_create(self, mock_get_logger):
        """Test tracking VFS bucket creation."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_vfs(
            bucket_id="bucket_1",
            operation="create",
            user_id="user1"
        )
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_track_vfs_write(self, mock_get_logger):
        """Test tracking VFS write operation."""
        mock_logger = Mock()
        mock_logger.log_event.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_track_vfs(
            bucket_id="bucket_1",
            operation="write",
            path="/data/file.txt",
            user_id="user1"
        )
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_track_vfs_read(self, mock_get_logger):
        """Test tracking VFS read operation."""
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


class TestAuditIntegrityCheckMCPTool(unittest.TestCase):
    """Test audit_integrity_check MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_integrity_check_valid(self, mock_get_logger):
        """Test integrity check with valid log."""
        mock_logger = Mock()
        mock_logger.check_integrity.return_value = {
            "valid": True,
            "total_events": 100
        }
        mock_get_logger.return_value = mock_logger
        
        result = audit_integrity_check()
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertTrue(result.get("valid"))
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_integrity_check_invalid(self, mock_get_logger):
        """Test integrity check with corrupted log."""
        mock_logger = Mock()
        mock_logger.check_integrity.return_value = {
            "valid": False,
            "errors": ["Checksum mismatch"]
        }
        mock_get_logger.return_value = mock_logger
        
        result = audit_integrity_check()
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("valid"))
        self.assertIn("errors", result)


class TestAuditRetentionPolicyMCPTool(unittest.TestCase):
    """Test audit_retention_policy MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_get_retention_policy(self, mock_get_logger):
        """Test getting retention policy."""
        mock_logger = Mock()
        mock_logger.get_retention_policy.return_value = {
            "retention_days": 90,
            "auto_cleanup": True
        }
        mock_get_logger.return_value = mock_logger
        
        result = audit_retention_policy(action="get")
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("policy", result)
    
    @patch('ipfs_kit_py.mcp.servers.audit_mcp_tools.get_audit_logger')
    def test_set_retention_policy(self, mock_get_logger):
        """Test setting retention policy."""
        mock_logger = Mock()
        mock_logger.set_retention_policy.return_value = True
        mock_get_logger.return_value = mock_logger
        
        result = audit_retention_policy(
            action="set",
            retention_days=60,
            auto_cleanup=True
        )
        
        self.assertTrue(result.get("success"))
        mock_logger.set_retention_policy.assert_called_once()


if __name__ == '__main__':
    unittest.main()

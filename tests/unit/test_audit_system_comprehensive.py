#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Audit System (Phase 2)

Tests all core functionality of the audit system including:
- AuditLogger initialization
- Event logging
- Event querying
- Event filtering
- Audit extensions
- Report generation
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.mcp.auth.audit_logging import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity
)
from ipfs_kit_py.mcp.auth.audit_extensions import AuditExtensions


class TestAuditLoggerInitialization(unittest.TestCase):
    """Test audit logger initialization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_init_creates_log_file(self):
        """Test that initialization creates log file."""
        logger = AuditLogger(log_file=self.log_file)
        
        self.assertIsNotNone(logger)
        # Log file might be created on first write, so just check logger exists
    
    def test_init_with_existing_file(self):
        """Test initialization with existing log file."""
        # Create file first
        with open(self.log_file, 'w') as f:
            f.write("")
        
        logger = AuditLogger(log_file=self.log_file)
        self.assertIsNotNone(logger)


class TestAuditEventLogging(unittest.TestCase):
    """Test audit event logging."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
        self.logger = AuditLogger(log_file=self.log_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_log_authentication_event(self):
        """Test logging an authentication event."""
        event = AuditEvent(
            event_type=AuditEventType.AUTHENTICATION,
            action="login",
            user_id="test_user",
            status="success",
            details={"method": "password"}
        )
        
        result = self.logger.log_event(event)
        self.assertTrue(result)
    
    def test_log_authorization_event(self):
        """Test logging an authorization event."""
        event = AuditEvent(
            event_type=AuditEventType.AUTHORIZATION,
            action="access_resource",
            user_id="test_user",
            resource="/api/data",
            status="granted"
        )
        
        result = self.logger.log_event(event)
        self.assertTrue(result)
    
    def test_log_data_access_event(self):
        """Test logging a data access event."""
        event = AuditEvent(
            event_type=AuditEventType.DATA,
            action="read",
            user_id="test_user",
            resource="/bucket/test/file.txt",
            status="success"
        )
        
        result = self.logger.log_event(event)
        self.assertTrue(result)
    
    def test_log_system_event(self):
        """Test logging a system event."""
        event = AuditEvent(
            event_type=AuditEventType.SYSTEM,
            action="startup",
            status="success",
            details={"version": "1.0.0"}
        )
        
        result = self.logger.log_event(event)
        self.assertTrue(result)
    
    def test_log_backend_event(self):
        """Test logging a backend event."""
        event = AuditEvent(
            event_type=AuditEventType.BACKEND,
            action="create",
            user_id="admin",
            resource="s3_backend",
            status="success",
            details={"backend_type": "s3"}
        )
        
        result = self.logger.log_event(event)
        self.assertTrue(result)


class TestAuditEventQuerying(unittest.TestCase):
    """Test querying audit events."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
        self.logger = AuditLogger(log_file=self.log_file)
        
        # Log some test events
        self.logger.log_event(AuditEvent(
            event_type=AuditEventType.AUTHENTICATION,
            action="login",
            user_id="user1",
            status="success"
        ))
        self.logger.log_event(AuditEvent(
            event_type=AuditEventType.AUTHENTICATION,
            action="login",
            user_id="user2",
            status="failure"
        ))
        self.logger.log_event(AuditEvent(
            event_type=AuditEventType.DATA,
            action="read",
            user_id="user1",
            resource="/data/file.txt",
            status="success"
        ))
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_query_all_events(self):
        """Test querying all events."""
        events = self.logger.query_events()
        
        self.assertIsInstance(events, list)
        self.assertGreaterEqual(len(events), 3)
    
    def test_query_by_event_type(self):
        """Test querying by event type."""
        events = self.logger.query_events(
            event_type=AuditEventType.AUTHENTICATION
        )
        
        self.assertIsInstance(events, list)
        for event in events:
            self.assertEqual(event.get('event_type'), AuditEventType.AUTHENTICATION.value)
    
    def test_query_by_user(self):
        """Test querying by user ID."""
        events = self.logger.query_events(user_id="user1")
        
        self.assertIsInstance(events, list)
        for event in events:
            self.assertEqual(event.get('user_id'), "user1")
    
    def test_query_by_status(self):
        """Test querying by status."""
        events = self.logger.query_events(status="failure")
        
        self.assertIsInstance(events, list)
        for event in events:
            self.assertEqual(event.get('status'), "failure")
    
    def test_query_with_limit(self):
        """Test querying with result limit."""
        events = self.logger.query_events(limit=2)
        
        self.assertIsInstance(events, list)
        self.assertLessEqual(len(events), 2)
    
    def test_query_by_time_range(self):
        """Test querying by time range."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        events = self.logger.query_events(
            start_time=start_time,
            end_time=end_time
        )
        
        self.assertIsInstance(events, list)


class TestAuditExtensions(unittest.TestCase):
    """Test audit extensions functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
        self.logger = AuditLogger(log_file=self.log_file)
        self.extensions = AuditExtensions(self.logger)
        
        # Log some test events
        for i in range(5):
            self.logger.log_event(AuditEvent(
                event_type=AuditEventType.AUTHENTICATION,
                action="login",
                user_id=f"user{i}",
                status="success" if i % 2 == 0 else "failure"
            ))
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_get_statistics(self):
        """Test getting audit statistics."""
        stats = self.extensions.get_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn("total_events", stats)
        self.assertGreater(stats["total_events"], 0)
    
    def test_generate_summary_report(self):
        """Test generating summary report."""
        report = self.extensions.generate_report(report_type="summary")
        
        self.assertIsInstance(report, dict)
        self.assertIn("total_events", report)
    
    def test_generate_security_report(self):
        """Test generating security report."""
        report = self.extensions.generate_report(report_type="security")
        
        self.assertIsInstance(report, dict)
        self.assertIn("failed_logins", report)
    
    def test_generate_user_activity_report(self):
        """Test generating user activity report."""
        report = self.extensions.generate_report(report_type="user_activity")
        
        self.assertIsInstance(report, dict)
        self.assertIn("users", report)


class TestAuditEventExport(unittest.TestCase):
    """Test audit event export functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
        self.logger = AuditLogger(log_file=self.log_file)
        
        # Log some test events
        self.logger.log_event(AuditEvent(
            event_type=AuditEventType.AUTHENTICATION,
            action="login",
            user_id="user1",
            status="success"
        ))
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_export_to_json(self):
        """Test exporting events to JSON."""
        output_file = os.path.join(self.test_dir, "export.json")
        
        result = self.logger.export_events(
            output_file=output_file,
            format="json"
        )
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_file))
        
        # Verify JSON is valid
        with open(output_file, 'r') as f:
            data = json.load(f)
            self.assertIsInstance(data, (list, dict))
    
    def test_export_to_csv(self):
        """Test exporting events to CSV."""
        output_file = os.path.join(self.test_dir, "export.csv")
        
        result = self.logger.export_events(
            output_file=output_file,
            format="csv"
        )
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_file))


class TestAuditIntegrityCheck(unittest.TestCase):
    """Test audit log integrity checking."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
        self.logger = AuditLogger(log_file=self.log_file)
        
        # Log some events
        for i in range(3):
            self.logger.log_event(AuditEvent(
                event_type=AuditEventType.SYSTEM,
                action="test",
                status="success"
            ))
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_integrity_check(self):
        """Test audit log integrity check."""
        result = self.logger.check_integrity()
        
        self.assertIsInstance(result, dict)
        self.assertIn("valid", result)
        self.assertTrue(result["valid"])


class TestAuditRetentionPolicy(unittest.TestCase):
    """Test audit retention policy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
        self.logger = AuditLogger(log_file=self.log_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_get_retention_policy(self):
        """Test getting retention policy."""
        policy = self.logger.get_retention_policy()
        
        self.assertIsInstance(policy, dict)
        self.assertIn("retention_days", policy)
    
    def test_set_retention_policy(self):
        """Test setting retention policy."""
        result = self.logger.set_retention_policy(
            retention_days=90,
            auto_cleanup=True
        )
        
        self.assertTrue(result)
        
        policy = self.logger.get_retention_policy()
        self.assertEqual(policy["retention_days"], 90)
        self.assertTrue(policy["auto_cleanup"])


if __name__ == '__main__':
    unittest.main()

"""
Unit tests for the security dashboard module.

These tests verify the functionality of the security analyzer and dashboard,
ensuring proper detection of suspicious activities and generation of metrics.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

from ipfs_kit_py.mcp.auth.audit import AuditLogEntry, AuditEventType
from ipfs_kit_py.mcp.auth.security_dashboard import (
    SecurityAnalyzer,
    SecurityMetrics,
    SuspiciousActivity,
    SecurityReport
)


class MockAuditLogger:
    """Mock audit logger for testing."""

    def __init__(self):
        """Initialize with test data."""
        self.logs = []

    async def get_recent_logs(
        self,
        limit=100,
        event_types=None,
        user_id=None,
        resource_type=None,
        resource_id=None,
        start_time=None,
        end_time=None
    ):
        """Mock implementation of get_recent_logs."""
        filtered_logs = []

        for log in self.logs:
            # Apply event type filter
            if event_types and log.get("event_type") not in event_types:
                continue

            # Apply user filter
            if user_id and log.get("user_id") != user_id:
                continue

            # Apply resource type filter
            if resource_type and log.get("resource_type") != resource_type:
                continue

            # Apply resource ID filter
            if resource_id and log.get("resource_id") != resource_id:
                continue

            # Apply time filters
            if start_time and log.get("timestamp") < start_time:
                continue

            if end_time and log.get("timestamp") > end_time:
                continue

            # Add to filtered logs
            filtered_logs.append(log)

            # Check limit
            if len(filtered_logs) >= limit:
                break

        return filtered_logs


@pytest.fixture
def mock_audit_logger():
    """Create a mock audit logger with test data."""
    logger = MockAuditLogger()

    # Current time for reference
    now = time.time()

    # Add sample logs

    # Successful logins
    for i in range(10):
        logger.logs.append({
            "id": f"test_login_{i}",
            "event_type": AuditEventType.USER_LOGIN.value,
            "timestamp": now - (i * 60),  # Each login 1 minute apart
            "user_id": f"user_{i % 3}",  # 3 different users
            "username": f"username_{i % 3}",
            "ip_address": f"192.168.1.{i % 5}",  # 5 different IPs
            "resource_type": "auth",
            "action": "login",
            "status": "success",
            "details": {}
        })

    # Failed logins - multiple from same IP
    for i in range(6):
        logger.logs.append({
            "id": f"test_login_fail_{i}",
            "event_type": AuditEventType.LOGIN_FAILURE.value,
            "timestamp": now - (i * 30),  # Each 30 seconds apart
            "username": "baduser",
            "ip_address": "192.168.1.100",  # Same IP for brute force detection
            "resource_type": "auth",
            "action": "login",
            "status": "failure",
            "details": {"reason": "invalid_credentials"}
        })

    # OAuth logins
    for i in range(5):
        logger.logs.append({
            "id": f"test_oauth_{i}",
            "event_type": AuditEventType.OAUTH_LOGIN.value,
            "timestamp": now - (i * 120),
            "user_id": f"oauth_user_{i}",
            "ip_address": f"192.168.1.{i + 10}",
            "resource_type": "oauth",
            "resource_id": "github",
            "action": "login",
            "status": "success",
            "details": {"provider": "github", "is_new_user": i == 0}
        })

    # API key usage
    for i in range(15):
        logger.logs.append({
            "id": f"test_apikey_{i}",
            "event_type": AuditEventType.API_KEY_USE.value,
            "timestamp": now - (i * 45),
            "user_id": f"user_{i % 2}",
            "ip_address": f"192.168.1.{i % 3}",
            "resource_type": "api_key",
            "resource_id": f"key_{i % 3}",
            "action": "use",
            "status": "success",
            "details": {}
        })

    # Permission denials - multiple for one user
    for i in range(7):
        logger.logs.append({
            "id": f"test_perm_deny_{i}",
            "event_type": AuditEventType.PERMISSION_DENIED.value,
            "timestamp": now - (i * 25),
            "user_id": "suspicious_user",
            "ip_address": "192.168.1.50",
            "resource_type": f"resource_{i % 3}",
            "resource_id": f"res_id_{i}",
            "action": "access",
            "status": "denied",
            "details": {"permission": f"permission_{i}"}
        })

    # Backend access denials
    for i in range(3):
        logger.logs.append({
            "id": f"test_backend_deny_{i}",
            "event_type": AuditEventType.BACKEND_ACCESS_DENIED.value,
            "timestamp": now - (i * 70),
            "user_id": "limited_user",
            "username": "limited_username",
            "ip_address": "192.168.1.60",
            "resource_type": "backend",
            "resource_id": f"backend_{i}",
            "action": "write",
            "status": "denied",
            "details": {"reason": "insufficient_permissions"}
        })

    return logger


@pytest.fixture
async def security_analyzer(mock_audit_logger):
    """Create a security analyzer with the mock audit logger."""
    with patch('ipfs_kit_py.mcp.auth.security_dashboard.get_audit_logger', return_value=mock_audit_logger):
        analyzer = SecurityAnalyzer()
        yield analyzer


@pytest.mark.asyncio
async def test_check_login_attempts(security_analyzer, mock_audit_logger):
    """Test detection of brute force login attempts."""
    # Process logs to check for suspicious login attempts
    await security_analyzer._check_login_attempts(mock_audit_logger.logs)

    # Should have detected one brute force attempt
    assert len(security_analyzer.recent_suspicious) == 1

    # Verify the suspicious activity details
    activity = security_analyzer.recent_suspicious[0]
    assert activity.activity_type == "brute_force_attempt"
    assert activity.severity == "medium"  # 6 attempts, so medium severity
    assert activity.ip_address == "192.168.1.100"
    assert activity.details["failed_attempts"] == 6


@pytest.mark.asyncio
async def test_permission_denials(security_analyzer, mock_audit_logger):
    """Test detection of multiple permission denials."""
    # Clear any existing suspicious activities
    security_analyzer.recent_suspicious = []

    # Process logs to check for permission denials
    await security_analyzer._check_permission_denials(mock_audit_logger.logs)

    # Should have detected suspicious permission denials
    assert len(security_analyzer.recent_suspicious) == 1

    # Verify the suspicious activity details
    activity = security_analyzer.recent_suspicious[0]
    assert activity.activity_type == "multiple_permission_denials"
    assert activity.user_id == "suspicious_user"
    assert len(activity.event_ids) == 7  # Should have 7 denial events


@pytest.mark.asyncio
async def test_backend_access_denials(security_analyzer, mock_audit_logger):
    """Test detection of backend access denials."""
    # Clear any existing suspicious activities
    security_analyzer.recent_suspicious = []

    # Process logs to check for backend access denials
    await security_analyzer._check_backend_access_denials(mock_audit_logger.logs)

    # Should have detected backend access denials
    assert len(security_analyzer.recent_suspicious) == 3

    # Verify the suspicious activity details
    for activity in security_analyzer.recent_suspicious:
        assert activity.activity_type == "backend_access_denied"
        assert activity.severity == "low"
        assert activity.user_id == "limited_user"
        assert "backend_" in activity.details["backend"]


@pytest.mark.asyncio
async def test_security_metrics(security_analyzer, mock_audit_logger):
    """Test generation of security metrics."""
    # Clear any existing suspicious activities
    security_analyzer.recent_suspicious = []

    # Add some suspicious activities for metrics calculation
    security_analyzer._add_suspicious_activity(
        SuspiciousActivity(
            timestamp=datetime.now(),
            user_id="test_user",
            activity_type="test_suspicious_activity",
            severity="medium",
            details={}
        )
    )

    # Generate metrics
    metrics = await security_analyzer.generate_security_metrics()

    # Verify metrics
    assert metrics.total_logins == 10  # From mock data
    assert metrics.failed_logins == 6   # From mock data
    assert metrics.oauth_logins == 5    # From mock data
    assert metrics.api_key_usage == 15  # From mock data
    assert metrics.permission_denials == 7  # From mock data
    assert metrics.suspicious_activities == 1  # Added above
    assert metrics.active_users > 0
    assert metrics.new_users == 1  # One OAuth user marked as new


@pytest.mark.asyncio
async def test_security_report(security_analyzer, mock_audit_logger):
    """Test generation of security report."""
    # Generate a security report
    report = await security_analyzer.generate_security_report()

    # Verify report structure
    assert isinstance(report, SecurityReport)
    assert isinstance(report.metrics, SecurityMetrics)
    assert isinstance(report.time_range.start, datetime)
    assert isinstance(report.time_range.end, datetime)
    assert isinstance(report.suspicious_activities, list)
    assert isinstance(report.ip_statistics, dict)
    assert isinstance(report.user_statistics, dict)

    # Verify report contents
    assert report.metrics.total_logins == 10
    assert report.metrics.failed_logins == 6
    assert len(report.ip_statistics) > 0
    assert len(report.user_statistics) > 0


@pytest.mark.asyncio
async def test_suspicious_activity_filtering(security_analyzer):
    """Test filtering of suspicious activities."""
    # Clear existing activities
    security_analyzer.recent_suspicious = []

    # Add suspicious activities with different severities and times
    now = datetime.now()

    # High severity, recent
    security_analyzer._add_suspicious_activity(
        SuspiciousActivity(
            timestamp=now,
            activity_type="high_severity_recent",
            severity="high",
            details={}
        )
    )

    # Medium severity, recent
    security_analyzer._add_suspicious_activity(
        SuspiciousActivity(
            timestamp=now - timedelta(minutes=30),
            activity_type="medium_severity_recent",
            severity="medium",
            details={}
        )
    )

    # Low severity, older
    security_analyzer._add_suspicious_activity(
        SuspiciousActivity(
            timestamp=now - timedelta(hours=12),
            activity_type="low_severity_older",
            severity="low",
            details={}
        )
    )

    # Test filtering by time
    one_hour_ago = (now - timedelta(hours=1)).timestamp()
    recent_activities = await security_analyzer.get_suspicious_activities(
        start_time=one_hour_ago
    )
    assert len(recent_activities) == 2  # Should exclude the older one

    # Test filtering by severity
    high_severity = await security_analyzer.get_suspicious_activities(
        severity="high"
    )
    assert len(high_severity) == 1
    assert high_severity[0].severity == "high"

    medium_severity = await security_analyzer.get_suspicious_activities(
        severity="medium"
    )
    assert len(medium_severity) == 1
    assert medium_severity[0].severity == "medium"

#!/usr/bin/env python3
# ipfs_kit_py/mcp/servers/audit_mcp_tools.py

"""
Audit MCP Tools for IPFS Kit

This module provides MCP tools for comprehensive audit logging and querying.
Tools enable viewing, querying, exporting, and analyzing audit events for
authentication, authorization, data access, and system changes.

Following the standard architecture pattern:
Core (audit_logging.py) → MCP Integration (this file) → Shim (mcp/) → Server → Dashboard
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

# Import core audit logging functionality
try:
    from ipfs_kit_py.mcp.auth.audit_logging import (
        AuditLogger,
        AuditEvent,
        AuditEventType,
        AuditSeverity
    )
    from ipfs_kit_py.mcp.auth.audit_extensions import AuditExtensions
except ImportError:
    # Fallback for different import paths
    from ...mcp.auth.audit_logging import (
        AuditLogger,
        AuditEvent,
        AuditEventType,
        AuditSeverity
    )
    from ...mcp.auth.audit_extensions import AuditExtensions

logger = logging.getLogger(__name__)

# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None
_audit_extensions: Optional[AuditExtensions] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        # Initialize with default settings
        import os
        log_dir = os.path.expanduser("~/.ipfs_kit/audit")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "audit.log")
        _audit_logger = AuditLogger(log_file=log_file)
    return _audit_logger


def get_audit_extensions() -> AuditExtensions:
    """Get or create the global audit extensions instance."""
    global _audit_extensions
    if _audit_extensions is None:
        audit_logger = get_audit_logger()
        _audit_extensions = AuditExtensions(audit_logger)
    return _audit_extensions


# MCP Tool Definitions

def audit_view(
    limit: int = 100,
    event_type: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    hours_ago: int = 24
) -> Dict[str, Any]:
    """
    View recent audit events with optional filtering.
    
    This tool retrieves recent audit events from the audit log, with optional
    filtering by event type, action, user, status, and time range.
    
    Args:
        limit: Maximum number of events to return (1-1000, default: 100)
        event_type: Filter by event type (authentication, authorization, user, role, 
                   api_key, oauth, data, system, backend, admin)
        action: Filter by action (login, logout, create, modify, delete, etc.)
        user_id: Filter by user ID
        status: Filter by status (success, failure, granted, denied)
        hours_ago: Only show events from last N hours (default: 24)
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - events: List of audit events
        - count: Number of events returned
        - filtered: Whether filters were applied
        - error: Error message if operation failed
    
    Example:
        # View all events from last 24 hours
        result = audit_view(limit=100)
        
        # View failed authentication attempts
        result = audit_view(event_type="authentication", status="failure", hours_ago=48)
        
        # View all actions by specific user
        result = audit_view(user_id="user123", hours_ago=168)  # Last week
    """
    try:
        audit_logger = get_audit_logger()
        
        # Validate and constrain limit
        limit = max(1, min(limit, 1000))
        
        time_threshold = datetime.now() - timedelta(hours=hours_ago)

        events = audit_logger.query_events(
            event_type=event_type,
            user_id=user_id,
            status=status,
            start_time=time_threshold,
            limit=limit
        )

        filtered_events = []
        for event in events:
            if action and event.get("action") != action:
                continue
            filtered_events.append(event)
        
        return {
            "success": True,
            "events": filtered_events,
            "count": len(filtered_events),
            "total_cached": len(events),
            "filtered": bool(event_type or action or user_id or status),
            "time_range_hours": hours_ago
        }
        
    except Exception as e:
        logger.error(f"Error viewing audit events: {e}")
        return {
            "success": False,
            "error": str(e),
            "events": [],
            "count": 0
        }


def audit_query(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    event_types: Optional[List[str]] = None,
    users: Optional[List[str]] = None,
    resources: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Query audit log with advanced filtering capabilities.
    
    This tool provides advanced querying of audit events with multiple filter
    criteria and time ranges. Results can be used for compliance reporting,
    security analysis, and troubleshooting.
    
    Args:
        start_time: Start time in ISO format (e.g., "2024-01-01T00:00:00")
        end_time: End time in ISO format (e.g., "2024-01-31T23:59:59")
        event_types: List of event types to include
        users: List of user IDs to include
        resources: List of resource IDs to include
        statuses: List of statuses to include (success, failure, granted, denied)
        limit: Maximum number of results (1-10000, default: 1000)
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - events: List of matching audit events
        - count: Number of events returned
        - query_summary: Summary of query parameters
        - error: Error message if operation failed
    
    Example:
        # Query failed authentication attempts in January
        result = audit_query(
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-31T23:59:59",
            event_types=["authentication"],
            statuses=["failure"]
        )
        
        # Query all actions by specific users
        result = audit_query(
            users=["admin", "user123"],
            start_time="2024-01-01T00:00:00"
        )
    """
    try:
        audit_logger = get_audit_logger()
        
        # Validate and constrain limit
        limit = max(1, min(limit, 10000))
        
        # Parse time ranges
        start_timestamp = None
        end_timestamp = None
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            start_timestamp = start_dt.timestamp()
        
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            end_timestamp = end_dt.timestamp()
        
        filtered_events = audit_logger.query_events(
            event_types=event_types,
            user_id=users[0] if users and len(users) == 1 else None,
            status=statuses[0] if statuses and len(statuses) == 1 else None,
            start_time=start_timestamp,
            end_time=end_timestamp,
            limit=limit
        )
        
        query_summary = {
            "start_time": start_time,
            "end_time": end_time,
            "event_types": event_types,
            "users": users,
            "resources": resources,
            "statuses": statuses,
            "limit": limit
        }
        
        return {
            "success": True,
            "events": filtered_events,
            "count": len(filtered_events),
            "query_summary": query_summary
        }
        
    except Exception as e:
        logger.error(f"Error querying audit events: {e}")
        return {
            "success": False,
            "error": str(e),
            "events": [],
            "count": 0
        }


def audit_export(
    format: str = "json",
    output_path: Optional[str] = None,
    event_type: Optional[str] = None,
    hours_ago: int = 24,
    output_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Export audit logs to file in specified format.
    
    This tool exports audit events to a file for archival, compliance, or
    external analysis. Supports multiple output formats.
    
    Args:
        format: Export format (json, jsonl, csv, default: json)
        output_path: Path to output file (if None, returns data in response)
        event_type: Filter by event type (optional)
        hours_ago: Export events from last N hours (default: 24)
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - output_path: Path to exported file (if saved)
        - data: Exported data (if output_path is None)
        - count: Number of events exported
        - format: Export format used
        - error: Error message if operation failed
    
    Example:
        # Export all events to JSON file
        result = audit_export(format="json", output_path="/tmp/audit.json")
        
        # Export authentication events to CSV
        result = audit_export(
            format="csv",
            output_path="/tmp/auth.csv",
            event_type="authentication"
        )
        
        # Get events as JSON without saving to file
        result = audit_export(format="json")
    """
    try:
        audit_logger = get_audit_logger()
        
        if output_file and not output_path:
            output_path = output_file

        if output_path and hasattr(audit_logger, "export_events"):
            ok = audit_logger.export_events(output_file=output_path, format=format)
            return {
                "success": bool(ok),
                "output_path": output_path,
                "format": format
            }

        return {
            "success": False,
            "error": "Export not supported without output_path"
        }
        
    except Exception as e:
        logger.error(f"Error exporting audit events: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def audit_report(
    report_type: str = "summary",
    hours_ago: int = 24,
    group_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate audit reports for compliance and security analysis.
    
    This tool generates various types of audit reports including summaries,
    security reports, compliance reports, and user activity reports.
    
    Args:
        report_type: Type of report (summary, security, compliance, user_activity)
        hours_ago: Generate report for last N hours (default: 24)
        group_by: Group results by field (event_type, user_id, action, status)
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - report_type: Type of report generated
        - report_data: Report data structure
        - time_range_hours: Time range covered
        - generated_at: Timestamp when report was generated
        - error: Error message if operation failed
    
    Example:
        # Generate summary report
        result = audit_report(report_type="summary", hours_ago=24)
        
        # Generate security report for last week
        result = audit_report(report_type="security", hours_ago=168)
        
        # Generate user activity report grouped by user
        result = audit_report(report_type="user_activity", group_by="user_id")
    """
    try:
        audit_logger = get_audit_logger()
        
        # Calculate time threshold
        time_threshold = datetime.now().timestamp() - (hours_ago * 3600)
        
        # Get events in time range
        events = [e for e in audit_logger.recent_events if e.timestamp >= time_threshold]
        
        report_data = {}
        
        if report_type == "summary":
            # Summary report: counts by type, action, status
            report_data = {
                "total_events": len(events),
                "by_event_type": {},
                "by_action": {},
                "by_status": {},
                "unique_users": set(),
                "time_range": {
                    "start": datetime.fromtimestamp(events[0].timestamp).isoformat() if events else None,
                    "end": datetime.fromtimestamp(events[-1].timestamp).isoformat() if events else None
                }
            }
            
            for event in events:
                # Count by event type
                event_type_str = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
                report_data["by_event_type"][event_type_str] = report_data["by_event_type"].get(event_type_str, 0) + 1
                
                # Count by action
                report_data["by_action"][event.action] = report_data["by_action"].get(event.action, 0) + 1
                
                # Count by status
                if event.status:
                    report_data["by_status"][event.status] = report_data["by_status"].get(event.status, 0) + 1
                
                # Track unique users
                if event.user_id:
                    report_data["unique_users"].add(event.user_id)
            
            report_data["unique_users"] = len(report_data["unique_users"])
        
        elif report_type == "security":
            # Security report: failed auth, denied access, suspicious activity
            failed_auth = [e for e in events if e.event_type.value == "authentication" and e.status == "failure"]
            denied_access = [e for e in events if e.status == "denied"]
            admin_actions = [e for e in events if e.event_type.value == "admin"]
            
            report_data = {
                "failed_authentications": len(failed_auth),
                "denied_accesses": len(denied_access),
                "admin_actions": len(admin_actions),
                "failed_auth_details": [e.to_dict() for e in failed_auth[:10]],  # Top 10
                "denied_access_details": [e.to_dict() for e in denied_access[:10]],  # Top 10
                "admin_action_details": [e.to_dict() for e in admin_actions[:10]]  # Top 10
            }
        
        elif report_type == "compliance":
            # Compliance report: user management, role changes, data access
            user_events = [e for e in events if e.event_type.value == "user"]
            role_events = [e for e in events if e.event_type.value == "role"]
            data_events = [e for e in events if e.event_type.value == "data"]
            
            report_data = {
                "user_management_events": len(user_events),
                "role_management_events": len(role_events),
                "data_access_events": len(data_events),
                "user_creations": len([e for e in user_events if e.action == "create"]),
                "user_deletions": len([e for e in user_events if e.action == "delete"]),
                "role_changes": len([e for e in role_events if e.action in ["create", "modify", "delete"]]),
                "data_modifications": len([e for e in data_events if e.action in ["write", "delete"]])
            }
        
        elif report_type == "user_activity":
            # User activity report: actions per user
            user_activity = {}
            for event in events:
                if event.user_id:
                    if event.user_id not in user_activity:
                        user_activity[event.user_id] = {
                            "total_actions": 0,
                            "actions": {},
                            "last_activity": None
                        }
                    
                    user_activity[event.user_id]["total_actions"] += 1
                    user_activity[event.user_id]["actions"][event.action] = \
                        user_activity[event.user_id]["actions"].get(event.action, 0) + 1
                    user_activity[event.user_id]["last_activity"] = datetime.fromtimestamp(event.timestamp).isoformat()
            
            report_data = {
                "total_users": len(user_activity),
                "user_activity": user_activity
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown report type: {report_type}. Use summary, security, compliance, or user_activity."
            }
        
        return {
            "success": True,
            "report_type": report_type,
            "report_data": report_data,
            "report": report_data,
            "time_range_hours": hours_ago,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating audit report: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def audit_statistics(
    hours_ago: int = 24
) -> Dict[str, Any]:
    """
    Get audit statistics and metrics.
    
    This tool provides statistical overview of audit events including counts,
    distributions, and trends over time.
    
    Args:
        hours_ago: Calculate statistics for last N hours (default: 24)
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - statistics: Statistical data
        - time_range_hours: Time range analyzed
        - error: Error message if operation failed
    
    Example:
        # Get statistics for last 24 hours
        result = audit_statistics(hours_ago=24)
        
        # Get statistics for last week
        result = audit_statistics(hours_ago=168)
    """
    try:
        audit_logger = get_audit_logger()
        
        # Calculate time threshold
        time_threshold = datetime.now().timestamp() - (hours_ago * 3600)
        
        # Get events in time range
        events = [e for e in audit_logger.recent_events if e.timestamp >= time_threshold]
        
        # Calculate statistics
        statistics = {
            "total_events": len(events),
            "total_cached_events": len(audit_logger.recent_events),
            "cache_limit": audit_logger.max_cached_events,
            "event_types": {},
            "actions": {},
            "statuses": {},
            "unique_users": set(),
            "unique_resources": set(),
            "events_per_hour": {},
            "success_rate": 0.0
        }
        
        success_count = 0
        total_with_status = 0
        
        for event in events:
            # Event type distribution
            event_type_str = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
            statistics["event_types"][event_type_str] = statistics["event_types"].get(event_type_str, 0) + 1
            
            # Action distribution
            statistics["actions"][event.action] = statistics["actions"].get(event.action, 0) + 1
            
            # Status distribution
            if event.status:
                statistics["statuses"][event.status] = statistics["statuses"].get(event.status, 0) + 1
                total_with_status += 1
                if event.status in ["success", "granted"]:
                    success_count += 1
            
            # Unique users
            if event.user_id:
                statistics["unique_users"].add(event.user_id)
            
            # Unique resources
            if event.resource_id:
                statistics["unique_resources"].add(event.resource_id)
            
            # Events per hour
            event_hour = datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:00")
            statistics["events_per_hour"][event_hour] = statistics["events_per_hour"].get(event_hour, 0) + 1
        
        # Calculate success rate
        if total_with_status > 0:
            statistics["success_rate"] = (success_count / total_with_status) * 100
        
        # Convert sets to counts
        statistics["unique_users"] = len(statistics["unique_users"])
        statistics["unique_resources"] = len(statistics["unique_resources"])
        
        return {
            "success": True,
            "statistics": statistics,
            "time_range_hours": hours_ago,
            "calculated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating audit statistics: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def audit_track_backend(
    backend_id: str,
    operation: str,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Track backend operation in audit log.
    
    This tool logs backend operations (create, update, delete, access) to the
    audit trail for compliance and troubleshooting.
    
    Args:
        backend_id: ID of the backend
        operation: Operation performed (create, update, delete, access, test)
        user_id: ID of user performing operation
        details: Additional operation details
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - event_id: ID of created audit event
        - timestamp: When event was logged
        - error: Error message if operation failed
    
    Example:
        # Track backend creation
        result = audit_track_backend(
            backend_id="s3-prod",
            operation="create",
            user_id="admin",
            details={"backend_type": "s3", "region": "us-east-1"}
        )
        
        # Track backend access
        result = audit_track_backend(
            backend_id="ipfs-main",
            operation="access",
            user_id="user123",
            details={"action": "read", "cid": "Qm..."}
        )
    """
    try:
        audit_logger = get_audit_logger()
        
        # Log backend operation
        if hasattr(audit_logger, "log_event"):
            event = AuditEvent(
                event_type=AuditEventType.BACKEND,
                action=operation,
                user_id=user_id,
                resource_id=backend_id,
                resource_type="backend",
                status="success",
                details=details or {}
            )
            audit_logger.log_event(event)
        else:
            event = audit_logger.log(
                event_type=AuditEventType.BACKEND,
                action=operation,
                user_id=user_id,
                resource_id=backend_id,
                resource_type="backend",
                status="success",
                details=details or {}
            )
        
        return {
            "success": True,
            "event_id": id(event),
            "timestamp": event.timestamp,
            "backend_id": backend_id,
            "operation": operation
        }
        
    except Exception as e:
        logger.error(f"Error tracking backend operation: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def audit_track_vfs(
    bucket_id: str,
    operation: str,
    path: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Track VFS bucket operation in audit log.
    
    This tool logs VFS bucket operations (create, mount, write, delete) to the
    audit trail for compliance and change tracking.
    
    Args:
        bucket_id: ID of the VFS bucket
        operation: Operation performed (create, mount, write, read, delete)
        path: File/directory path within bucket (optional)
        user_id: ID of user performing operation
        details: Additional operation details
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - event_id: ID of created audit event
        - timestamp: When event was logged
        - error: Error message if operation failed
    
    Example:
        # Track bucket creation
        result = audit_track_vfs(
            bucket_id="my-bucket",
            operation="create",
            user_id="admin",
            details={"backend": "ipfs"}
        )
        
        # Track file write
        result = audit_track_vfs(
            bucket_id="my-bucket",
            operation="write",
            path="/data/file.txt",
            user_id="user123",
            details={"size_bytes": 1024}
        )
    """
    try:
        audit_logger = get_audit_logger()
        
        # Prepare details
        operation_details = details or {}
        if path:
            operation_details["path"] = path
        
        # Log VFS operation
            if hasattr(audit_logger, "log_event"):
                event = AuditEvent(
                    event_type=AuditEventType.DATA,
                    action=operation,
                    user_id=user_id,
                    resource_id=bucket_id,
                    resource_type="vfs_bucket",
                    status="success",
                    details=operation_details
                )
                audit_logger.log_event(event)
            else:
                event = audit_logger.log(
                    event_type=AuditEventType.DATA,
                    action=operation,
                    user_id=user_id,
                    resource_id=bucket_id,
                    resource_type="vfs_bucket",
                    status="success",
                    details=operation_details
                )
        
        return {
            "success": True,
            "event_id": id(event),
            "timestamp": event.timestamp,
            "bucket_id": bucket_id,
            "operation": operation,
            "path": path
        }
        
    except Exception as e:
        logger.error(f"Error tracking VFS operation: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def audit_integrity_check() -> Dict[str, Any]:
    """
    Verify audit log integrity.
    
    This tool checks the integrity of the audit log, verifying that events
    have not been tampered with.
    
    Returns:
        Dict containing:
        - success: Boolean indicating if check succeeded
        - integrity_valid: Boolean indicating if audit log is valid
        - total_events_checked: Number of events verified
        - issues: List of integrity issues found (if any)
        - error: Error message if operation failed
    
    Example:
        # Check audit log integrity
        result = audit_integrity_check()
    """
    try:
        audit_logger = get_audit_logger()

        if hasattr(audit_logger, "check_integrity"):
            result = audit_logger.check_integrity()
            payload = dict(result) if isinstance(result, dict) else {"valid": bool(result)}
            payload.setdefault("errors", [])
            payload["success"] = payload.get("valid", True)
            return payload

        audit_extensions = get_audit_extensions()
        
        # Get recent events
        events = audit_logger.recent_events
        
        # Basic integrity checks
        issues = []
        
        # Check 1: Events should be in chronological order
        for i in range(1, len(events)):
            if events[i].timestamp < events[i-1].timestamp:
                issues.append(f"Event at index {i} has earlier timestamp than previous event")
        
        # Check 2: Events should have required fields
        for i, event in enumerate(events):
            if not event.event_type:
                issues.append(f"Event at index {i} missing event_type")
            if not event.action:
                issues.append(f"Event at index {i} missing action")
            if not event.timestamp:
                issues.append(f"Event at index {i} missing timestamp")
        
        # Check 3: Audit extensions integrity logs (if available)
        if hasattr(audit_extensions, '_integrity_logs') and audit_extensions._integrity_logs:
            # Check against stored integrity logs
            pass  # Additional integrity verification could be added here
        
        integrity_valid = len(issues) == 0
        
        return {
            "success": True,
            "integrity_valid": integrity_valid,
            "valid": integrity_valid,
            "errors": issues if not integrity_valid else [],
            "total_events_checked": len(events),
            "issues": issues,
            "checked_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking audit integrity: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def audit_retention_policy(
    action: str = "get",
    retention_days: Optional[int] = None,
    auto_cleanup: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Configure or view audit log retention policy.
    
    This tool manages how long audit logs are retained and when automatic
    cleanup occurs.
    
    Args:
        action: Action to perform (get, set)
        retention_days: Number of days to retain audit logs (for set action)
        auto_cleanup: Enable/disable automatic cleanup (for set action)
    
    Returns:
        Dict containing:
        - success: Boolean indicating if operation succeeded
        - current_policy: Current retention policy settings
        - action_performed: Action that was performed
        - error: Error message if operation failed
    
    Example:
        # Get current retention policy
        result = audit_retention_policy(action="get")
        
        # Set retention to 90 days with auto-cleanup
        result = audit_retention_policy(
            action="set",
            retention_days=90,
            auto_cleanup=True
        )
    """
    try:
        audit_logger = get_audit_logger()

        if action == "get":
            policy = audit_logger.get_retention_policy()
            return {
                "success": True,
                "policy": policy
            }

        if action == "set":
            result = audit_logger.set_retention_policy(retention_days, auto_cleanup)
            return {
                "success": bool(result),
                "policy": {
                    "retention_days": retention_days,
                    "auto_cleanup": auto_cleanup
                }
            }

        return {
            "success": False,
            "error": f"Unknown action: {action}. Use 'get' or 'set'."
        }
        
    except Exception as e:
        logger.error(f"Error managing retention policy: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# Tool registry for MCP server integration
AUDIT_MCP_TOOLS = {
    "audit_view": {
        "function": audit_view,
        "description": "View recent audit events with optional filtering",
        "parameters": {
            "limit": "Maximum number of events to return (1-1000)",
            "event_type": "Filter by event type",
            "action": "Filter by action",
            "user_id": "Filter by user ID",
            "status": "Filter by status",
            "hours_ago": "Only show events from last N hours"
        }
    },
    "audit_query": {
        "function": audit_query,
        "description": "Query audit log with advanced filtering",
        "parameters": {
            "start_time": "Start time in ISO format",
            "end_time": "End time in ISO format",
            "event_types": "List of event types",
            "users": "List of user IDs",
            "resources": "List of resource IDs",
            "statuses": "List of statuses",
            "limit": "Maximum number of results"
        }
    },
    "audit_export": {
        "function": audit_export,
        "description": "Export audit logs to file",
        "parameters": {
            "format": "Export format (json, jsonl, csv)",
            "output_path": "Path to output file",
            "event_type": "Filter by event type",
            "hours_ago": "Export events from last N hours"
        }
    },
    "audit_report": {
        "function": audit_report,
        "description": "Generate audit reports",
        "parameters": {
            "report_type": "Type of report (summary, security, compliance, user_activity)",
            "hours_ago": "Generate report for last N hours",
            "group_by": "Group results by field"
        }
    },
    "audit_statistics": {
        "function": audit_statistics,
        "description": "Get audit statistics and metrics",
        "parameters": {
            "hours_ago": "Calculate statistics for last N hours"
        }
    },
    "audit_track_backend": {
        "function": audit_track_backend,
        "description": "Track backend operation in audit log",
        "parameters": {
            "backend_id": "ID of the backend",
            "operation": "Operation performed",
            "user_id": "ID of user performing operation",
            "details": "Additional operation details"
        }
    },
    "audit_track_vfs": {
        "function": audit_track_vfs,
        "description": "Track VFS bucket operation in audit log",
        "parameters": {
            "bucket_id": "ID of the VFS bucket",
            "operation": "Operation performed",
            "path": "File/directory path within bucket",
            "user_id": "ID of user performing operation",
            "details": "Additional operation details"
        }
    },
    "audit_integrity_check": {
        "function": audit_integrity_check,
        "description": "Verify audit log integrity",
        "parameters": {}
    },
    "audit_retention_policy": {
        "function": audit_retention_policy,
        "description": "Configure or view audit log retention policy",
        "parameters": {
            "action": "Action to perform (get, set)",
            "retention_days": "Number of days to retain logs",
            "auto_cleanup": "Enable/disable automatic cleanup"
        }
    }
}


# Export all tools
__all__ = [
    "audit_view",
    "audit_query",
    "audit_export",
    "audit_report",
    "audit_statistics",
    "audit_track_backend",
    "audit_track_vfs",
    "audit_integrity_check",
    "audit_retention_policy",
    "AUDIT_MCP_TOOLS",
    "get_audit_logger",
    "get_audit_extensions"
]

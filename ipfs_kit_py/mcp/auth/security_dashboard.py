"""
MCP Security Dashboard

This script provides a web-based dashboard for monitoring and managing
the security aspects of the MCP server, including:

- User authentication statistics
- Active sessions and API keys
- Failed login attempts and other security events
- Role and permission management
- Backend access control
- Audit log visualization

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements - Advanced Authentication & Authorization.
"""

import os
import time
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Union

import aiofiles
import pandas as pd
import plotly.express as px
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.auth.service import get_instance as get_auth_service
from ipfs_kit_py.mcp.auth.auth_integration import get_auth_system

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v0/security", tags=["Security Dashboard"])

# Setup templates
try:
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    templates = Jinja2Templates(directory=template_dir)
except Exception as e:
    logger.error(f"Error setting up templates: {e}")
    templates = None


class SecurityDashboard:
    """Security dashboard for MCP server."""
    
    def __init__(self):
        """Initialize security dashboard."""
        self.auth_system = get_auth_system()
        self.auth_service = get_auth_service()
        self.metrics_cache = {}
        self.metrics_cache_time = 0
        self.metrics_cache_ttl = 300  # 5 minutes
    
    async def get_auth_metrics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get authentication metrics.
        
        Args:
            force_refresh: Whether to force a refresh of cached metrics
            
        Returns:
            Authentication metrics
        """
        # Check cache
        now = time.time()
        if (not force_refresh and 
            self.metrics_cache and 
            now - self.metrics_cache_time < self.metrics_cache_ttl):
            return self.metrics_cache
        
        metrics = {
            "timestamp": now,
            "users": {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "by_role": {},
                "new_last_24h": 0,
                "new_last_7d": 0,
                "new_last_30d": 0,
            },
            "sessions": {
                "total": 0,
                "active": 0,
                "expired": 0,
            },
            "api_keys": {
                "total": 0,
                "active": 0,
                "expired": 0,
            },
            "logins": {
                "successful_24h": 0,
                "failed_24h": 0,
                "oauth_24h": 0,
                "apikey_24h": 0,
            },
            "backend_access": {
                "total_24h": 0,
                "denied_24h": 0,
                "by_backend": {},
            },
            "audit_logs": {
                "total_24h": 0,
                "by_severity": {},
                "by_type": {},
            }
        }
        
        try:
            # Get users
            users = await self.auth_service.list_users()
            metrics["users"]["total"] = len(users)
            
            # Process user metrics
            roles_count = {}
            active_count = 0
            inactive_count = 0
            new_24h = 0
            new_7d = 0
            new_30d = 0
            
            for user in users:
                # Count by role
                for role in user.roles:
                    roles_count[role] = roles_count.get(role, 0) + 1
                
                # Count active/inactive
                if user.active:
                    active_count += 1
                else:
                    inactive_count += 1
                
                # Count new users
                created_time = user.created_at
                days_since_creation = (now - created_time) / 86400  # Convert to days
                
                if days_since_creation <= 1:
                    new_24h += 1
                if days_since_creation <= 7:
                    new_7d += 1
                if days_since_creation <= 30:
                    new_30d += 1
            
            metrics["users"]["active"] = active_count
            metrics["users"]["inactive"] = inactive_count
            metrics["users"]["by_role"] = roles_count
            metrics["users"]["new_last_24h"] = new_24h
            metrics["users"]["new_last_7d"] = new_7d
            metrics["users"]["new_last_30d"] = new_30d
            
            # Get sessions
            sessions = await self.auth_service.list_sessions()
            metrics["sessions"]["total"] = len(sessions)
            
            # Process session metrics
            active_sessions = 0
            expired_sessions = 0
            
            for session in sessions:
                if session.active and session.expires_at > now:
                    active_sessions += 1
                else:
                    expired_sessions += 1
            
            metrics["sessions"]["active"] = active_sessions
            metrics["sessions"]["expired"] = expired_sessions
            
            # Get API keys
            api_keys = await self.auth_service.list_api_keys()
            metrics["api_keys"]["total"] = len(api_keys)
            
            # Process API key metrics
            active_keys = 0
            expired_keys = 0
            
            for key in api_keys:
                if key.active and (key.expires_at is None or key.expires_at > now):
                    active_keys += 1
                else:
                    expired_keys += 1
            
            metrics["api_keys"]["active"] = active_keys
            metrics["api_keys"]["expired"] = expired_keys
            
            # Get audit logs for the last 24 hours
            logs = await self.get_audit_logs(hours=24)
            
            # Process login metrics
            successful_logins = 0
            failed_logins = 0
            oauth_logins = 0
            apikey_logins = 0
            
            for log in logs:
                if log.get("event_type") == "AUTH":
                    action = log.get("action", "")
                    if action == "login_attempt":
                        if log.get("details", {}).get("success", False):
                            successful_logins += 1
                        else:
                            failed_logins += 1
                    elif action == "oauth_login":
                        oauth_logins += 1
                    elif action == "api_key_auth":
                        apikey_logins += 1
            
            metrics["logins"]["successful_24h"] = successful_logins
            metrics["logins"]["failed_24h"] = failed_logins
            metrics["logins"]["oauth_24h"] = oauth_logins
            metrics["logins"]["apikey_24h"] = apikey_logins
            
            # Process backend access metrics
            backend_access = 0
            denied_access = 0
            backend_counts = {}
            
            for log in logs:
                if log.get("event_type") == "BACKEND":
                    backend_access += 1
                    
                    if not log.get("details", {}).get("granted", True):
                        denied_access += 1
                    
                    backend = log.get("details", {}).get("backend")
                    if backend:
                        backend_counts[backend] = backend_counts.get(backend, 0) + 1
            
            metrics["backend_access"]["total_24h"] = backend_access
            metrics["backend_access"]["denied_24h"] = denied_access
            metrics["backend_access"]["by_backend"] = backend_counts
            
            # Process audit log metrics
            metrics["audit_logs"]["total_24h"] = len(logs)
            
            severity_counts = {}
            type_counts = {}
            
            for log in logs:
                severity = log.get("severity", "UNKNOWN")
                event_type = log.get("event_type", "UNKNOWN")
                
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                type_counts[event_type] = type_counts.get(event_type, 0) + 1
            
            metrics["audit_logs"]["by_severity"] = severity_counts
            metrics["audit_logs"]["by_type"] = type_counts
            
            # Update cache
            self.metrics_cache = metrics
            self.metrics_cache_time = now
            
            return metrics
        
        except Exception as e:
            logger.error(f"Error getting auth metrics: {e}")
            return {
                "error": str(e),
                "timestamp": now
            }
    
    async def get_audit_logs(
        self, 
        hours: int = 24,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs for the specified period.
        
        Args:
            hours: Number of hours to look back
            user_id: Optional user ID filter
            event_type: Optional event type filter
            
        Returns:
            List of audit logs
        """
        try:
            # Calculate start time
            now = time.time()
            start_time = now - (hours * 3600)
            
            # Build filters
            filters = {
                "from_time": start_time
            }
            
            if user_id:
                filters["user_id"] = user_id
            
            if event_type:
                filters["event_type"] = event_type
            
            # Get logs
            audit_logger = self.auth_system.audit_logger
            if not audit_logger:
                return []
            
            logs = await audit_logger.get_logs(filters=filters)
            return logs
        
        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            return []
    
    async def get_suspicious_activities(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get suspicious activities from audit logs.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of suspicious activities
        """
        try:
            # Get audit logs
            logs = await self.get_audit_logs(hours=hours)
            
            # Define suspicious patterns
            suspicious_activities = []
            
            # Check for multiple failed logins
            failed_logins = {}
            
            for log in logs:
                if log.get("event_type") == "AUTH" and log.get("action") == "login_attempt":
                    if not log.get("details", {}).get("success", False):
                        user_id = log.get("user_id")
                        ip = log.get("details", {}).get("ip_address")
                        
                        if user_id:
                            key = f"{user_id}:{ip}" if ip else user_id
                            failed_logins[key] = failed_logins.get(key, 0) + 1
            
            # Flag users with more than 5 failed logins
            for key, count in failed_logins.items():
                if count >= 5:
                    user_id = key.split(":")[0] if ":" in key else key
                    ip = key.split(":")[1] if ":" in key else None
                    
                    suspicious_activities.append({
                        "type": "failed_login",
                        "user_id": user_id,
                        "ip_address": ip,
                        "count": count,
                        "severity": "HIGH" if count >= 10 else "MEDIUM",
                        "description": f"Multiple failed login attempts ({count}) for user {user_id}"
                    })
            
            # Check for denied backend access
            denied_backend = {}
            
            for log in logs:
                if log.get("event_type") == "BACKEND" and not log.get("details", {}).get("granted", True):
                    user_id = log.get("user_id")
                    backend = log.get("details", {}).get("backend")
                    
                    if user_id and backend:
                        key = f"{user_id}:{backend}"
                        denied_backend[key] = denied_backend.get(key, 0) + 1
            
            # Flag users with more than 3 denied backend access
            for key, count in denied_backend.items():
                if count >= 3:
                    user_id, backend = key.split(":")
                    
                    suspicious_activities.append({
                        "type": "denied_backend",
                        "user_id": user_id,
                        "backend": backend,
                        "count": count,
                        "severity": "MEDIUM",
                        "description": f"Multiple denied access attempts ({count}) to backend {backend} for user {user_id}"
                    })
            
            # Check for permission denials
            denied_permissions = {}
            
            for log in logs:
                if log.get("event_type") == "PERMISSION" and not log.get("details", {}).get("granted", True):
                    user_id = log.get("user_id")
                    permission = log.get("details", {}).get("permission")
                    
                    if user_id and permission:
                        key = f"{user_id}:{permission}"
                        denied_permissions[key] = denied_permissions.get(key, 0) + 1
            
            # Flag users with more than 3 denied permissions
            for key, count in denied_permissions.items():
                if count >= 3:
                    user_id, permission = key.split(":")
                    
                    suspicious_activities.append({
                        "type": "denied_permission",
                        "user_id": user_id,
                        "permission": permission,
                        "count": count,
                        "severity": "MEDIUM",
                        "description": f"Multiple permission denials ({count}) for {permission} to user {user_id}"
                    })
            
            # Check for API key usage from unusual IP
            api_key_ips = {}
            
            for log in logs:
                if log.get("event_type") == "AUTH" and log.get("action") == "api_key_auth":
                    key_id = log.get("details", {}).get("key_id")
                    ip = log.get("details", {}).get("ip_address")
                    
                    if key_id and ip:
                        if key_id not in api_key_ips:
                            api_key_ips[key_id] = set()
                        
                        api_key_ips[key_id].add(ip)
            
            # Flag API keys used from more than 3 different IPs
            for key_id, ips in api_key_ips.items():
                if len(ips) >= 3:
                    suspicious_activities.append({
                        "type": "api_key_multiple_ips",
                        "key_id": key_id,
                        "ip_count": len(ips),
                        "ips": list(ips),
                        "severity": "MEDIUM",
                        "description": f"API key {key_id} used from {len(ips)} different IP addresses"
                    })
            
            return suspicious_activities
        
        except Exception as e:
            logger.error(f"Error getting suspicious activities: {e}")
            return []
    
    async def get_user_activity_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get a summary of user activity.
        
        Args:
            user_id: User ID
            days: Number of days to look back
            
        Returns:
            User activity summary
        """
        try:
            # Get user
            auth_service = get_auth_service()
            user_success, user_result = await auth_service.get_user(user_id)
            
            if not user_success:
                return {"error": "User not found"}
            
            user = user_result
            
            # Get audit logs for user
            logs = await self.get_audit_logs(hours=days * 24, user_id=user_id)
            
            # Process logs
            login_count = 0
            backend_access_count = 0
            permission_checks = 0
            data_operations = 0
            
            # Activity by day
            days_ago = {}
            for i in range(days):
                days_ago[i] = 0
            
            # Activity by hour
            hour_activity = {}
            for i in range(24):
                hour_activity[i] = 0
            
            for log in logs:
                # Count by type
                event_type = log.get("event_type", "")
                if event_type == "AUTH" and log.get("action") == "login_attempt":
                    if log.get("details", {}).get("success", False):
                        login_count += 1
                elif event_type == "BACKEND":
                    backend_access_count += 1
                elif event_type == "PERMISSION":
                    permission_checks += 1
                elif event_type == "DATA":
                    data_operations += 1
                
                # Process by day and hour
                timestamp = log.get("timestamp", 0)
                if timestamp > 0:
                    log_time = datetime.fromtimestamp(timestamp)
                    now = datetime.now()
                    
                    # Days ago
                    days_diff = (now - log_time).days
                    if days_diff < days:
                        days_ago[days_diff] = days_ago.get(days_diff, 0) + 1
                    
                    # Hour of day
                    hour = log_time.hour
                    hour_activity[hour] = hour_activity.get(hour, 0) + 1
            
            # Get API keys for user
            api_keys = []
            all_keys = await auth_service.list_api_keys()
            for key in all_keys:
                if key.user_id == user_id:
                    api_keys.append(key)
            
            # Get sessions for user
            sessions = []
            all_sessions = await auth_service.list_sessions()
            for session in all_sessions:
                if session.user_id == user_id:
                    sessions.append(session)
            
            # Build summary
            summary = {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "roles": list(user.roles),
                    "active": user.active,
                    "created_at": user.created_at,
                    "last_login": user.last_login,
                },
                "activity": {
                    "login_count": login_count,
                    "backend_access_count": backend_access_count,
                    "permission_checks": permission_checks,
                    "data_operations": data_operations,
                    "total_logs": len(logs),
                    "by_day": days_ago,
                    "by_hour": hour_activity,
                },
                "api_keys": {
                    "total": len(api_keys),
                    "active": sum(1 for k in api_keys if k.active),
                    "expired": sum(1 for k in api_keys if not k.active),
                },
                "sessions": {
                    "total": len(sessions),
                    "active": sum(1 for s in sessions if s.active),
                    "expired": sum(1 for s in sessions if not s.active),
                }
            }
            
            return summary
        
        except Exception as e:
            logger.error(f"Error getting user activity summary: {e}")
            return {"error": str(e)}
    
    async def get_backend_access_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get a summary of backend access.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Backend access summary
        """
        try:
            # Get audit logs for backend access
            logs = await self.get_audit_logs(hours=days * 24, event_type="BACKEND")
            
            # Process logs
            backend_counts = {}
            operation_counts = {}
            user_counts = {}
            denied_counts = {}
            
            # Access by day
            days_ago = {}
            for i in range(days):
                days_ago[i] = 0
            
            for log in logs:
                details = log.get("details", {})
                backend = details.get("backend", "unknown")
                operation = details.get("operation", "unknown")
                user_id = log.get("user_id", "unknown")
                granted = details.get("granted", True)
                
                # Count by backend
                backend_counts[backend] = backend_counts.get(backend, 0) + 1
                
                # Count by operation
                operation_counts[operation] = operation_counts.get(operation, 0) + 1
                
                # Count by user
                user_counts[user_id] = user_counts.get(user_id, 0) + 1
                
                # Count denied access
                if not granted:
                    denied_key = f"{backend}:{operation}"
                    denied_counts[denied_key] = denied_counts.get(denied_key, 0) + 1
                
                # Process by day
                timestamp = log.get("timestamp", 0)
                if timestamp > 0:
                    log_time = datetime.fromtimestamp(timestamp)
                    now = datetime.now()
                    
                    # Days ago
                    days_diff = (now - log_time).days
                    if days_diff < days:
                        days_ago[days_diff] = days_ago.get(days_diff, 0) + 1
            
            # Find top users
            top_users = sorted(
                user_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            # Build summary
            summary = {
                "total_access": len(logs),
                "by_backend": backend_counts,
                "by_operation": operation_counts,
                "top_users": dict(top_users),
                "denied_access": denied_counts,
                "by_day": days_ago,
            }
            
            return summary
        
        except Exception as e:
            logger.error(f"Error getting backend access summary: {e}")
            return {"error": str(e)}

# Create dashboard instance
dashboard = SecurityDashboard()

# Define routes
@router.get("/dashboard", response_class=HTMLResponse, summary="Security dashboard UI")
async def get_dashboard(request: Request):
    """Get the security dashboard UI."""
    if not templates:
        return HTMLResponse("Templates not available", status_code=500)
    
    metrics = await dashboard.get_auth_metrics()
    suspicious = await dashboard.get_suspicious_activities()
    
    return templates.TemplateResponse(
        "security_dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "suspicious": suspicious,
            "current_time": datetime.now().isoformat(),
        }
    )

@router.get("/metrics", summary="Get security metrics")
async def get_metrics(
    force_refresh: bool = Query(False, description="Force refresh of metrics cache")
):
    """Get security metrics."""
    metrics = await dashboard.get_auth_metrics(force_refresh=force_refresh)
    return metrics

@router.get("/suspicious", summary="Get suspicious activities")
async def get_suspicious_activities(
    hours: int = Query(24, description="Hours to look back", ge=1, le=720)
):
    """Get suspicious activities."""
    activities = await dashboard.get_suspicious_activities(hours=hours)
    return {"activities": activities, "count": len(activities), "hours": hours}

@router.get("/users/{user_id}/activity", summary="Get user activity summary")
async def get_user_activity(
    user_id: str,
    days: int = Query(30, description="Days to look back", ge=1, le=365)
):
    """Get user activity summary."""
    summary = await dashboard.get_user_activity_summary(user_id=user_id, days=days)
    return summary

@router.get("/backend/summary", summary="Get backend access summary")
async def get_backend_summary(
    days: int = Query(30, description="Days to look back", ge=1, le=365)
):
    """Get backend access summary."""
    summary = await dashboard.get_backend_access_summary(days=days)
    return summary

@router.get("/audit/logs", summary="Get audit logs")
async def get_audit_logs(
    hours: int = Query(24, description="Hours to look back", ge=1, le=720),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type")
):
    """Get audit logs."""
    logs = await dashboard.get_audit_logs(hours=hours, user_id=user_id, event_type=event_type)
    return {"logs": logs, "count": len(logs), "hours": hours}

# Create a basic dashboard HTML template
dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Security Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            padding: 20px;
        }
        .card h2 {
            margin-top: 0;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            font-size: 18px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .metric .label {
            color: #666;
        }
        .metric .value {
            font-weight: bold;
        }
        .alert {
            background-color: #fff8f8;
            border-left: 4px solid #ff4444;
            padding: 10px;
            margin-bottom: 10px;
        }
        .alert.high {
            border-left-color: #ff4444;
        }
        .alert.medium {
            border-left-color: #ffbb33;
        }
        .alert.low {
            border-left-color: #ffbb33;
        }
        .alert .severity {
            font-weight: bold;
            text-transform: uppercase;
            font-size: 12px;
        }
        .alert .severity.high {
            color: #ff4444;
        }
        .alert .severity.medium {
            color: #ffbb33;
        }
        .alert .severity.low {
            color: #33b5e5;
        }
        header {
            margin-bottom: 20px;
        }
        header h1 {
            margin: 0;
        }
        header p {
            color: #666;
            margin: 5px 0 0 0;
        }
    </style>
</head>
<body>
    <header>
        <h1>MCP Security Dashboard</h1>
        <p>Last updated: {{ current_time }}</p>
    </header>
    
    <div class="dashboard">
        <!-- User metrics -->
        <div class="card">
            <h2>User Statistics</h2>
            <div class="metric">
                <span class="label">Total Users</span>
                <span class="value">{{ metrics.users.total }}</span>
            </div>
            <div class="metric">
                <span class="label">Active Users</span>
                <span class="value">{{ metrics.users.active }}</span>
            </div>
            <div class="metric">
                <span class="label">New (24h)</span>
                <span class="value">{{ metrics.users.new_last_24h }}</span>
            </div>
            <div class="metric">
                <span class="label">New (7d)</span>
                <span class="value">{{ metrics.users.new_last_7d }}</span>
            </div>
        </div>
        
        <!-- Authentication metrics -->
        <div class="card">
            <h2>Authentication</h2>
            <div class="metric">
                <span class="label">Active Sessions</span>
                <span class="value">{{ metrics.sessions.active }}</span>
            </div>
            <div class="metric">
                <span class="label">Active API Keys</span>
                <span class="value">{{ metrics.api_keys.active }}</span>
            </div>
            <div class="metric">
                <span class="label">Logins (24h)</span>
                <span class="value">{{ metrics.logins.successful_24h }}</span>
            </div>
            <div class="metric">
                <span class="label">Failed Logins (24h)</span>
                <span class="value">{{ metrics.logins.failed_24h }}</span>
            </div>
        </div>
        
        <!-- Backend access metrics -->
        <div class="card">
            <h2>Backend Access</h2>
            <div class="metric">
                <span class="label">Total Access (24h)</span>
                <span class="value">{{ metrics.backend_access.total_24h }}</span>
            </div>
            <div class="metric">
                <span class="label">Denied Access (24h)</span>
                <span class="value">{{ metrics.backend_access.denied_24h }}</span>
            </div>
        </div>
        
        <!-- Suspicious activities -->
        <div class="card">
            <h2>Suspicious Activities</h2>
            {% if suspicious %}
                {% for activity in suspicious %}
                <div class="alert {{ activity.severity|lower }}">
                    <div class="severity {{ activity.severity|lower }}">{{ activity.severity }}</div>
                    <div>{{ activity.description }}</div>
                </div>
                {% endfor %}
            {% else %}
                <p>No suspicious activities detected</p>
            {% endif %}
        </div>
    </div>
    
    <script>
        // Auto-refresh dashboard every 5 minutes
        setTimeout(function() {
            window.location.reload();
        }, 5 * 60 * 1000);
    </script>
</body>
</html>
"""

# Create template file if templates directory exists

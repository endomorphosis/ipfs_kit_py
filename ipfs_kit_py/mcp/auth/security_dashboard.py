"""
Security Dashboard for Advanced Authentication & Authorization

This module provides a comprehensive dashboard for managing the security aspects of the MCP server,
including user management, role configuration, API key management, and audit log review.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from pydantic import BaseModel

from ipfs_kit_py.mcp.auth.router import get_admin_user, get_current_user
from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.rbac import rbac_manager
from ipfs_kit_py.mcp.auth.audit import get_instance as get_audit_logger
from ipfs_kit_py.mcp.auth.auth_system_integration import get_auth_system
from ipfs_kit_py.mcp.auth.api_key_cache import get_api_key_cache

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v0/security", tags=["security"])


# ----- Models -----

class SecurityOverview(BaseModel):
    """Security system overview statistics."""
    user_count: int
    active_users_24h: int
    inactive_users_30d: int
    failed_logins_24h: int
    active_sessions: int
    api_key_count: int
    expired_api_keys: int
    custom_roles: List[str]
    last_successful_login: Optional[datetime]
    last_failed_login: Optional[datetime]
    audit_log_count_24h: int
    high_priority_audit_events_24h: int


class UserOverview(BaseModel):
    """Overview of a user for management purposes."""
    id: str
    username: str
    email: Optional[str]
    full_name: Optional[str]
    roles: List[str]
    active: bool
    last_login: Optional[datetime]
    sessions_count: int
    api_keys_count: int
    created_at: datetime
    login_failures: int


class RoleDetail(BaseModel):
    """Detailed information about a role."""
    id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    parent_role: Optional[str]
    user_count: int
    is_system_role: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ApiKeyDetail(BaseModel):
    """Detailed information about an API key."""
    id: str
    name: str
    user_id: str
    username: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    use_count: int
    permissions: List[str]
    is_active: bool


class AuditLogEntry(BaseModel):
    """Audit log entry details."""
    id: str
    timestamp: datetime
    user_id: Optional[str]
    username: Optional[str]
    ip_address: Optional[str]
    action: str
    target: Optional[str]
    status: str
    details: Optional[Dict[str, Any]]
    priority: str


# ----- Endpoints -----

@router.get("/dashboard", response_model=SecurityOverview)
async def get_security_overview(current_user: User = Depends(get_admin_user)):
    """
    Get an overview of the security system status.
    
    This endpoint provides key metrics about the authentication and authorization system,
    including user activity, failed logins, and API key usage.
    
    Requires admin permission.
    """
    auth_system = get_auth_system()
    auth_service = auth_system.auth_service
    api_key_cache = get_api_key_cache()
    audit_logger = get_audit_logger()
    
    # Calculate time boundaries
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_30d = now - timedelta(days=30)
    
    # Get user counts
    users = await auth_service.user_store.get_all_users()
    user_count = len(users)
    
    # Active users in last 24 hours
    active_users_24h = sum(
        1 for user in users.values() 
        if user.get("last_login") and user.get("last_login") > last_24h.timestamp()
    )
    
    # Inactive users in last 30 days
    inactive_users_30d = sum(
        1 for user in users.values()
        if not user.get("last_login") or user.get("last_login") < last_30d.timestamp()
    )
    
    # Get session counts
    sessions = await auth_service.session_store.get_all_sessions()
    active_sessions = len(sessions)
    
    # Get login statistics
    login_attempts = await audit_logger.query_logs(
        action="login", 
        start_time=last_24h
    )
    failed_logins_24h = sum(1 for log in login_attempts if log.get("status") == "failure")
    
    # Get latest login timestamps
    successful_logins = sorted(
        [log for log in login_attempts if log.get("status") == "success"],
        key=lambda x: x.get("timestamp", 0),
        reverse=True
    )
    failed_logins = sorted(
        [log for log in login_attempts if log.get("status") == "failure"],
        key=lambda x: x.get("timestamp", 0),
        reverse=True
    )
    
    last_successful_login = datetime.fromtimestamp(successful_logins[0].get("timestamp")) if successful_logins else None
    last_failed_login = datetime.fromtimestamp(failed_logins[0].get("timestamp")) if failed_logins else None
    
    # Get API key statistics
    api_keys = await api_key_cache.get_all_keys()
    api_key_count = len(api_keys)
    expired_api_keys = sum(
        1 for key in api_keys.values()
        if key.get("expires_at") and key.get("expires_at") < now.timestamp()
    )
    
    # Get custom roles
    custom_roles = list(rbac_manager._custom_roles.keys())
    
    # Get audit log statistics
    audit_logs = await audit_logger.query_logs(start_time=last_24h)
    audit_log_count_24h = len(audit_logs)
    high_priority_audit_events_24h = sum(
        1 for log in audit_logs
        if log.get("priority") in ["high", "critical"]
    )
    
    return SecurityOverview(
        user_count=user_count,
        active_users_24h=active_users_24h,
        inactive_users_30d=inactive_users_30d,
        failed_logins_24h=failed_logins_24h,
        active_sessions=active_sessions,
        api_key_count=api_key_count,
        expired_api_keys=expired_api_keys,
        custom_roles=custom_roles,
        last_successful_login=last_successful_login,
        last_failed_login=last_failed_login,
        audit_log_count_24h=audit_log_count_24h,
        high_priority_audit_events_24h=high_priority_audit_events_24h
    )


@router.get("/users", response_model=List[UserOverview])
async def list_users(
    active: Optional[bool] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_admin_user)
):
    """
    List users with filtering options.
    
    Requires admin permission.
    """
    auth_system = get_auth_system()
    auth_service = auth_system.auth_service
    api_key_cache = get_api_key_cache()
    
    # Get all users
    users_dict = await auth_service.user_store.get_all_users()
    
    # Get sessions for counting
    sessions = await auth_service.session_store.get_all_sessions()
    sessions_by_user = {}
    for session_id, session in sessions.items():
        user_id = session.get("user_id")
        if user_id:
            if user_id not in sessions_by_user:
                sessions_by_user[user_id] = []
            sessions_by_user[user_id].append(session)
    
    # Get API keys for counting
    api_keys = await api_key_cache.get_all_keys()
    api_keys_by_user = {}
    for key_id, key in api_keys.items():
        user_id = key.get("user_id")
        if user_id:
            if user_id not in api_keys_by_user:
                api_keys_by_user[user_id] = []
            api_keys_by_user[user_id].append(key)
    
    # Apply filters
    filtered_users = []
    for user_id, user_data in users_dict.items():
        # Convert to User object for easier handling
        try:
            user = User(**user_data)
        except:
            # Skip invalid users
            continue
            
        # Apply active filter if specified
        if active is not None:
            is_active = user.is_active if hasattr(user, "is_active") else True
            if is_active != active:
                continue
        
        # Apply role filter if specified
        if role and role not in user.roles:
            continue
            
        # Apply search filter if specified
        if search:
            search_lower = search.lower()
            if (
                (user.username and search_lower in user.username.lower()) or
                (user.email and search_lower in user.email.lower()) or
                (user.full_name and search_lower in user.full_name.lower())
            ):
                pass  # Match, include user
            else:
                continue  # No match, skip user
        
        # User passed all filters, include in results
        login_failures = 0
        # TODO: Get login failures from audit log
        
        filtered_users.append(UserOverview(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            roles=list(user.roles) if user.roles else [],
            active=user.is_active if hasattr(user, "is_active") else True,
            last_login=datetime.fromtimestamp(user.last_login) if user.last_login else None,
            sessions_count=len(sessions_by_user.get(user.id, [])),
            api_keys_count=len(api_keys_by_user.get(user.id, [])),
            created_at=datetime.fromtimestamp(user.created_at) if user.created_at else datetime.utcnow(),
            login_failures=login_failures
        ))
    
    # Sort by username
    filtered_users.sort(key=lambda u: u.username)
    
    # Apply pagination
    paginated_users = filtered_users[offset:offset + limit]
    
    return paginated_users


@router.get("/roles", response_model=List[RoleDetail])
async def list_roles(current_user: User = Depends(get_admin_user)):
    """
    List all roles in the system.
    
    Requires admin permission.
    """
    auth_system = get_auth_system()
    auth_service = auth_system.auth_service
    
    # Get all users for counting
    users_dict = await auth_service.user_store.get_all_users()
    
    # Count users per role
    role_user_counts = {}
    for user_id, user_data in users_dict.items():
        try:
            user = User(**user_data)
            for role in user.roles:
                if role not in role_user_counts:
                    role_user_counts[role] = 0
                role_user_counts[role] += 1
        except:
            # Skip invalid users
            continue
    
    # Get system roles
    system_roles = []
    for role in Role:
        permissions = rbac_manager.get_effective_permissions(role)
        system_roles.append(RoleDetail(
            id=role.value,
            name=role.name.capitalize(),
            description=f"System role: {role.name}",
            permissions=permissions,
            parent_role=None,  # TODO: Get parent from hierarchy
            user_count=role_user_counts.get(role.value, 0),
            is_system_role=True,
            created_at=None,
            updated_at=None
        ))
    
    # Get custom roles
    custom_roles = []
    for role_id, role_data in rbac_manager._custom_roles.items():
        custom_roles.append(RoleDetail(
            id=role_id,
            name=role_data.get("name", role_id),
            description=role_data.get("description"),
            permissions=[p.value if hasattr(p, "value") else p for p in role_data.get("permissions", [])],
            parent_role=role_data.get("parent").value if role_data.get("parent") else None,
            user_count=role_user_counts.get(role_id, 0),
            is_system_role=False,
            created_at=role_data.get("created_at"),
            updated_at=role_data.get("updated_at")
        ))
    
    # Combine and sort
    all_roles = system_roles + custom_roles
    all_roles.sort(key=lambda r: (not r.is_system_role, r.name))
    
    return all_roles


@router.get("/api-keys", response_model=List[ApiKeyDetail])
async def list_api_keys(
    active: Optional[bool] = None,
    user_id: Optional[str] = None,
    current_user: User = Depends(get_admin_user)
):
    """
    List API keys with filtering options.
    
    Requires admin permission.
    """
    auth_system = get_auth_system()
    auth_service = auth_system.auth_service
    api_key_cache = get_api_key_cache()
    
    # Get all API keys
    api_keys = await api_key_cache.get_all_keys()
    
    # Get all users for username lookup
    users_dict = await auth_service.user_store.get_all_users()
    
    # Apply filters and build response
    now = datetime.utcnow().timestamp()
    filtered_keys = []
    for key_id, key_data in api_keys.items():
        # Apply active filter if specified
        if active is not None:
            is_active = (
                key_data.get("expires_at") is None or 
                key_data.get("expires_at") > now
            )
            if is_active != active:
                continue
        
        # Apply user filter if specified
        if user_id and key_data.get("user_id") != user_id:
            continue
        
        # Get username if available
        username = None
        if key_data.get("user_id") in users_dict:
            username = users_dict[key_data.get("user_id")].get("username")
        
        # Convert dates
        created_at = datetime.fromtimestamp(key_data.get("created_at", 0))
        expires_at = datetime.fromtimestamp(key_data.get("expires_at")) if key_data.get("expires_at") else None
        last_used = datetime.fromtimestamp(key_data.get("last_used")) if key_data.get("last_used") else None
        
        # Check if active
        is_active = True
        if expires_at and expires_at < datetime.utcnow():
            is_active = False
        
        # Build response object
        filtered_keys.append(ApiKeyDetail(
            id=key_id,
            name=key_data.get("name", "Unnamed API Key"),
            user_id=key_data.get("user_id"),
            username=username,
            created_at=created_at,
            expires_at=expires_at,
            last_used=last_used,
            use_count=key_data.get("use_count", 0),
            permissions=[p for p in key_data.get("permissions", [])],
            is_active=is_active
        ))
    
    # Sort by creation date (newest first)
    filtered_keys.sort(key=lambda k: k.created_at, reverse=True)
    
    return filtered_keys


@router.get("/audit-logs", response_model=List[AuditLogEntry])
async def query_audit_logs(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_admin_user)
):
    """
    Query audit logs with filtering options.
    
    Requires admin permission.
    """
    audit_logger = get_audit_logger()
    
    # Prepare filter parameters
    query_params = {}
    if start_time:
        query_params["start_time"] = start_time
    if end_time:
        query_params["end_time"] = end_time
    if user_id:
        query_params["user_id"] = user_id
    if action:
        query_params["action"] = action
    if status:
        query_params["status"] = status
    if priority:
        query_params["priority"] = priority
    
    # Query audit logs
    logs = await audit_logger.query_logs(**query_params)
    
    # Sort by timestamp (newest first)
    logs.sort(key=lambda l: l.get("timestamp", 0), reverse=True)
    
    # Apply pagination
    paginated_logs = logs[offset:offset + limit]
    
    # Format response
    result = []
    for log in paginated_logs:
        # Convert timestamp
        timestamp = datetime.fromtimestamp(log.get("timestamp", 0))
        
        # Add to result
        result.append(AuditLogEntry(
            id=log.get("id", ""),
            timestamp=timestamp,
            user_id=log.get("user_id"),
            username=log.get("username"),
            ip_address=log.get("ip_address"),
            action=log.get("action", "unknown"),
            target=log.get("target"),
            status=log.get("status", "unknown"),
            details=log.get("details", {}),
            priority=log.get("priority", "normal")
        ))
    
    return result


@router.post("/roles/{role_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_role_from_users(
    role_id: str = Path(...),
    user_ids: List[str] = [],
    current_user: User = Depends(get_admin_user)
):
    """
    Revoke a role from multiple users.
    
    Requires admin permission.
    """
    auth_system = get_auth_system()
    auth_service = auth_system.auth_service
    
    # Check if role exists
    if (role_id not in [r.value for r in Role] and 
        role_id not in rbac_manager._custom_roles):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role {role_id} not found"
        )
    
    # Get all affected users
    results = {"success": [], "failure": []}
    for user_id in user_ids:
        try:
            # Get user
            user = await auth_service.get_user(user_id)
            if not user:
                results["failure"].append({
                    "user_id": user_id,
                    "reason": "User not found"
                })
                continue
            
            # Check if user has the role
            if role_id not in user.roles:
                results["failure"].append({
                    "user_id": user_id,
                    "reason": f"User does not have role {role_id}"
                })
                continue
            
            # Remove role
            user_dict = user.dict()
            user_dict["roles"] = [r for r in user.roles if r != role_id]
            
            # Update user
            success = await auth_service.user_store.update(user.id, user_dict)
            if success:
                results["success"].append(user_id)
                
                # Log the action
                audit_logger = get_audit_logger()
                await audit_logger.log_event(
                    action="revoke_role",
                    user_id=current_user.id,
                    username=current_user.username,
                    target=f"user:{user_id}",
                    status="success",
                    details={
                        "role_id": role_id,
                        "admin_user": current_user.username
                    },
                    priority="high"
                )
            else:
                results["failure"].append({
                    "user_id": user_id,
                    "reason": "Failed to update user"
                })
                
        except Exception as e:
            results["failure"].append({
                "user_id": user_id,
                "reason": str(e)
            })
    
    # Return results
    return {
        "role_id": role_id,
        "success_count": len(results["success"]),
        "failure_count": len(results["failure"]),
        "details": results
    }


@router.post("/api-keys/revoke-all", status_code=status.HTTP_200_OK)
async def revoke_all_api_keys(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_admin_user)
):
    """
    Revoke all API keys, optionally for a specific user.
    
    Requires admin permission.
    """
    api_key_cache = get_api_key_cache()
    
    # Get all API keys
    api_keys = await api_key_cache.get_all_keys()
    
    # Filter by user if specified
    revoked_count = 0
    revoked_keys = []
    
    for key_id, key_data in api_keys.items():
        # Skip if not matching user (when filter is applied)
        if user_id and key_data.get("user_id") != user_id:
            continue
            
        # Delete the key
        success = await api_key_cache.delete_key(key_id)
        if success:
            revoked_count += 1
            revoked_keys.append(key_id)
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_event(
        action="revoke_all_api_keys",
        user_id=current_user.id,
        username=current_user.username,
        target=f"user:{user_id}" if user_id else "all_users",
        status="success",
        details={
            "revoked_count": revoked_count,
            "admin_user": current_user.username
        },
        priority="high"
    )
    
    # Return results
    return {
        "success": True,
        "revoked_count": revoked_count,
        "user_id": user_id,
        "revoked_keys": revoked_keys
    }


@router.get("/stats/logins", response_model=Dict[str, Any])
async def get_login_statistics(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_admin_user)
):
    """
    Get login statistics for the specified number of days.
    
    Requires admin permission.
    """
    audit_logger = get_audit_logger()
    
    # Calculate start time
    start_time = datetime.utcnow() - timedelta(days=days)
    
    # Query login events
    login_events = await audit_logger.query_logs(
        action="login",
        start_time=start_time
    )
    
    # Group by day and status
    daily_stats = {}
    for event in login_events:
        # Get date from timestamp
        timestamp = event.get("timestamp", 0)
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        
        # Initialize day if needed
        if date_str not in daily_stats:
            daily_stats[date_str] = {
                "success": 0,
                "failure": 0,
                "total": 0
            }
        
        # Update counts
        status = event.get("status", "unknown")
        if status == "success":
            daily_stats[date_str]["success"] += 1
        elif status == "failure":
            daily_stats[date_str]["failure"] += 1
        
        daily_stats[date_str]["total"] += 1
    
    # Ensure all days are present
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        if date not in daily_stats:
            daily_stats[date] = {
                "success": 0,
                "failure": 0,
                "total": 0
            }
    
    # Convert to list and sort by date
    daily_list = [{"date": date, **stats} for date, stats in daily_stats.items()]
    daily_list.sort(key=lambda x: x["date"])
    
    # Calculate totals
    total_success = sum(day["success"] for day in daily_list)
    total_failure = sum(day["failure"] for day in daily_list)
    
    return {
        "daily": daily_list,
        "total_success": total_success,
        "total_failure": total_failure,
        "total": total_success + total_failure,
        "success_rate": total_success / (total_success + total_failure) * 100 if (total_success + total_failure) > 0 else 0,
        "days": days
    }


# Add the router to app in main auth_system_integration.py
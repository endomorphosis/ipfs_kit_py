"""
API Key Management Router for MCP Server

This module provides REST API endpoints for API key management:
- API key creation
- API key retrieval
- API key revocation
- API key permissions

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.auth.router import get_current_user
from ipfs_kit_py.mcp.auth.audit import get_audit_logger
from ipfs_kit_py.mcp.auth.service import get_instance as get_auth_service

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v0/keys", tags=["api-keys"])


# --- Pydantic models ---

class ApiKeyCreateRequest(BaseModel):
    """Request model for creating an API key."""
    name: str = Field(..., description="Name for the API key")
    expires_in_days: Optional[int] = Field(None, description="Days until expiration")
    permissions: Optional[List[str]] = Field(None, description="Direct permissions")
    roles: Optional[List[str]] = Field(None, description="Roles to assign")
    allowed_ips: Optional[List[str]] = Field(None, description="Allowed IP addresses")
    backend_restrictions: Optional[List[str]] = Field(None, description="Restricted backends")


class ApiKeyResponse(BaseModel):
    """Response model for API key data."""
    id: str
    name: str
    key: Optional[str] = Field(None, description="Only shown once on creation")
    user_id: str
    created_at: float
    expires_at: Optional[float] = None
    last_used: Optional[float] = None
    active: bool = True
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    allowed_ips: Optional[List[str]] = None
    backend_restrictions: Optional[List[str]] = None


class ApiKeyListResponse(BaseModel):
    """Response model for listing API keys."""
    keys: List[ApiKeyResponse]
    total: int


# --- API key endpoints ---

@router.post("", response_model=ApiKeyResponse, summary="Create API key")
async def create_api_key(
    request: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new API key for the current user.
    
    The API key value will only be shown once in the response.
    """
    auth_service = get_auth_service()
    
    # Create API key
    success, api_key, message = await auth_service.create_api_key(
        user_id=current_user.id,
        request=request
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_user_action(
        user_id=current_user.id,
        action="create_api_key",
        resource_id=api_key.id,
        resource_type="api_key",
        details={
            "name": api_key.name,
            "expires_in_days": request.expires_in_days,
            "roles": request.roles,
            "permissions": request.permissions,
            "has_ip_restrictions": bool(request.allowed_ips),
            "has_backend_restrictions": bool(request.backend_restrictions)
        }
    )
    
    return api_key


@router.get("", response_model=ApiKeyListResponse, summary="List API keys")
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    show_expired: bool = Query(False, description="Include expired keys"),
    show_inactive: bool = Query(False, description="Include inactive keys")
):
    """
    List all API keys for the current user.
    
    API key values are not included in the response.
    """
    auth_service = get_auth_service()
    
    # Get API keys for user
    api_keys = await auth_service.get_user_api_keys(current_user.id)
    
    # Filter keys
    now = datetime.utcnow().timestamp()
    filtered_keys = []
    for key in api_keys:
        # Skip expired keys if not requested
        if not show_expired and key.expires_at and key.expires_at < now:
            continue
        
        # Skip inactive keys if not requested
        if not show_inactive and not key.active:
            continue
        
        # Remove key value from response
        key_dict = key.dict()
        key_dict.pop("key", None)
        key_dict.pop("hashed_key", None)
        
        filtered_keys.append(ApiKeyResponse(**key_dict))
    
    return ApiKeyListResponse(
        keys=filtered_keys,
        total=len(filtered_keys)
    )


@router.get("/{key_id}", response_model=ApiKeyResponse, summary="Get API key details")
async def get_api_key(
    key_id: str = Path(..., description="API key ID"),
    current_user: User = Depends(get_current_user)
):
    """
    Get details for a specific API key.
    
    The API key value is not included in the response.
    """
    auth_service = get_auth_service()
    
    # Get API key
    api_key = await auth_service.get_api_key(key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )
    
    # Check that key belongs to user
    if api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this API key"
        )
    
    # Remove key value from response
    key_dict = api_key.dict()
    key_dict.pop("key", None)
    key_dict.pop("hashed_key", None)
    
    return ApiKeyResponse(**key_dict)


@router.delete("/{key_id}", summary="Revoke API key")
async def revoke_api_key(
    key_id: str = Path(..., description="API key ID"),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke an API key, making it immediately inactive.
    """
    auth_service = get_auth_service()
    
    # Revoke API key
    success, message = await auth_service.revoke_api_key(key_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=404 if "not found" in message else 400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_user_action(
        user_id=current_user.id,
        action="revoke_api_key",
        resource_id=key_id,
        resource_type="api_key"
    )
    
    return {"message": message}


@router.put("/{key_id}/permissions", summary="Update API key permissions")
async def update_api_key_permissions(
    key_id: str = Path(..., description="API key ID"),
    permissions: List[str] = Body(..., description="List of permission strings"),
    current_user: User = Depends(get_current_user)
):
    """
    Update the direct permissions assigned to an API key.
    """
    auth_service = get_auth_service()
    
    # Get API key
    api_key = await auth_service.get_api_key(key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )
    
    # Check that key belongs to user
    if api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this API key"
        )
    
    # Update permissions
    success, message = await auth_service.update_api_key_permissions(key_id, permissions)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_user_action(
        user_id=current_user.id,
        action="update_api_key_permissions",
        resource_id=key_id,
        resource_type="api_key",
        details={"permissions": permissions}
    )
    
    return {"message": "API key permissions updated", "permissions": permissions}


@router.put("/{key_id}/roles", summary="Update API key roles")
async def update_api_key_roles(
    key_id: str = Path(..., description="API key ID"),
    roles: List[str] = Body(..., description="List of role strings"),
    current_user: User = Depends(get_current_user)
):
    """
    Update the roles assigned to an API key.
    """
    auth_service = get_auth_service()
    
    # Get API key
    api_key = await auth_service.get_api_key(key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )
    
    # Check that key belongs to user
    if api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this API key"
        )
    
    # Update roles
    success, message = await auth_service.update_api_key_roles(key_id, roles)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_user_action(
        user_id=current_user.id,
        action="update_api_key_roles",
        resource_id=key_id,
        resource_type="api_key",
        details={"roles": roles}
    )
    
    return {"message": "API key roles updated", "roles": roles}


@router.put("/{key_id}/restrictions", summary="Update API key restrictions")
async def update_api_key_restrictions(
    key_id: str = Path(..., description="API key ID"),
    allowed_ips: Optional[List[str]] = Body(None, description="Allowed IP addresses"),
    backend_restrictions: Optional[List[str]] = Body(None, description="Restricted backends"),
    current_user: User = Depends(get_current_user)
):
    """
    Update the IP and backend restrictions for an API key.
    """
    auth_service = get_auth_service()
    
    # Get API key
    api_key = await auth_service.get_api_key(key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )
    
    # Check that key belongs to user
    if api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this API key"
        )
    
    # Update restrictions
    success, message = await auth_service.update_api_key_restrictions(
        key_id, 
        allowed_ips=allowed_ips,
        backend_restrictions=backend_restrictions
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_user_action(
        user_id=current_user.id,
        action="update_api_key_restrictions",
        resource_id=key_id,
        resource_type="api_key",
        details={
            "has_ip_restrictions": bool(allowed_ips),
            "has_backend_restrictions": bool(backend_restrictions)
        }
    )
    
    return {
        "message": "API key restrictions updated",
        "allowed_ips": allowed_ips,
        "backend_restrictions": backend_restrictions
    }
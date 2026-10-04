"""
RBAC API Router for MCP Server

This module provides API endpoints for the Role-Based Access Control system:
- Role management
- Permission management
- Authorization checks
- Backend-specific authorization

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import logging
from typing import Dict, List, Optional, Any, Union, Set
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from pydantic import BaseModel, Field

from .rbac import (
    RBACManager, Role, Permission,
    ResourceType, ActionType, get_instance as get_rbac_manager
)
from ..models.responses import StandardResponse, ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_rbac_api")

# Pydantic models for API requests/responses

class PermissionInfo(BaseModel):
    """Basic permission information."""
    id: str
    name: str
    resource_type: str
    actions: List[str]
    description: Optional[str] = None
    created_at: float
    updated_at: float

class PermissionDetail(PermissionInfo):
    """Detailed permission information."""
    resource_id: Optional[str] = None
    conditions: Dict[str, Any] = {}

class RoleInfo(BaseModel):
    """Basic role information."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: float
    updated_at: float

class RoleDetail(RoleInfo):
    """Detailed role information."""
    permissions: List[str] = []
    parent_roles: List[str] = []
    permission_details: Optional[List[PermissionInfo]] = None

class PermissionCreateRequest(BaseModel):
    """Request to create a new permission."""
    name: str
    resource_type: str
    actions: List[str]
    description: Optional[str] = None
    resource_id: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None

class PermissionUpdateRequest(BaseModel):
    """Request to update a permission."""
    name: Optional[str] = None
    description: Optional[str] = None
    actions: Optional[List[str]] = None
    resource_id: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None

class RoleCreateRequest(BaseModel):
    """Request to create a new role."""
    name: str
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    parent_roles: Optional[List[str]] = None

class RoleUpdateRequest(BaseModel):
    """Request to update a role."""
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    parent_roles: Optional[List[str]] = None

class AuthorizationCheckRequest(BaseModel):
    """Request to check authorization for a specific action."""
    roles: List[str]
    resource_type: str
    action: str
    resource_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class PermissionCheckRequest(BaseModel):
    """Request to check if user has a specific permission."""
    roles: List[str]
    permission_name: str
    resource_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class BackendPermissionsResult(BaseModel):
    """Result of a backend permissions check."""
    backend_permissions: Dict[str, List[str]]

# API Router

def create_rbac_api_router(
    rbac_manager: Optional[RBACManager] = None,
    get_current_admin_user = None  # Optional dependency for admin-only endpoints
) -> APIRouter:
    """
    Create an API router for RBAC functions.
    
    Args:
        rbac_manager: RBAC manager instance
        get_current_admin_user: Optional dependency for admin-only endpoints
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter(tags=["Role-Based Access Control"])
    
    # Use provided RBAC manager or get singleton instance
    manager = rbac_manager or get_rbac_manager()
    
    if manager is None:
        logger.warning("RBAC manager not available - RBAC endpoints will return errors")
    
    # Permission management endpoints
    
    @router.get(
        "/permissions",
        response_model=StandardResponse,
        summary="List Permissions",
        description="List all permissions in the system."
    )
    async def list_permissions(
        resource_type: Optional[str] = Query(None, description="Filter by resource type"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """List all permissions."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Get permissions
            permissions = manager.list_permissions()
            
            # Apply resource type filter if provided
            if resource_type:
                try:
                    resource_enum = ResourceType(resource_type)
                    permissions = [p for p in permissions if p.resource_type == resource_enum]
                except ValueError:
                    return ErrorResponse(
                        success=False,
                        message=f"Invalid resource type: {resource_type}",
                        error_code="invalid_resource_type",
                        error_details={"valid_types": [t.value for t in ResourceType]}
                    )
            
            # Convert to response format
            permission_info = [
                PermissionInfo(
                    id=perm.id,
                    name=perm.name,
                    resource_type=perm.resource_type.value,
                    actions=[action.value for action in perm.actions],
                    description=perm.description,
                    created_at=perm.created_at,
                    updated_at=perm.updated_at
                )
                for perm in permissions
            ]
            
            return StandardResponse(
                success=True,
                message=f"Found {len(permission_info)} permissions",
                data={"permissions": permission_info}
            )
        except Exception as e:
            logger.error(f"Error listing permissions: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to list permissions: {str(e)}",
                error_code="permission_list_error"
            )
    
    @router.get(
        "/permissions/{permission_id}",
        response_model=StandardResponse,
        summary="Get Permission",
        description="Get detailed information about a specific permission."
    )
    async def get_permission(
        permission_id: str = Path(..., description="Permission ID"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Get a specific permission by ID."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Get permission from manager
            permission = manager.get_permission(permission_id)
            
            if not permission:
                return ErrorResponse(
                    success=False,
                    message=f"Permission {permission_id} not found",
                    error_code="permission_not_found"
                )
            
            # Convert to response format
            permission_detail = PermissionDetail(
                id=permission.id,
                name=permission.name,
                resource_type=permission.resource_type.value,
                actions=[action.value for action in permission.actions],
                description=permission.description,
                resource_id=permission.resource_id,
                conditions=permission.conditions,
                created_at=permission.created_at,
                updated_at=permission.updated_at
            )
            
            return StandardResponse(
                success=True,
                message=f"Permission {permission_id} retrieved",
                data={"permission": permission_detail}
            )
        except Exception as e:
            logger.error(f"Error getting permission {permission_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to get permission: {str(e)}",
                error_code="permission_get_error"
            )
    
    @router.post(
        "/permissions",
        response_model=StandardResponse,
        summary="Create Permission",
        description="Create a new permission."
    )
    async def create_permission(
        request: PermissionCreateRequest,
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Create a new permission."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Validate resource type
            try:
                resource_type = ResourceType(request.resource_type)
            except ValueError:
                return ErrorResponse(
                    success=False,
                    message=f"Invalid resource type: {request.resource_type}",
                    error_code="invalid_resource_type",
                    error_details={"valid_types": [t.value for t in ResourceType]}
                )
            
            # Validate actions
            actions = set()
            for action in request.actions:
                try:
                    actions.add(ActionType(action))
                except ValueError:
                    return ErrorResponse(
                        success=False,
                        message=f"Invalid action type: {action}",
                        error_code="invalid_action_type",
                        error_details={"valid_actions": [a.value for a in ActionType]}
                    )
            
            # Check if permission with same name already exists
            existing = manager.get_permission_by_name(request.name)
            if existing:
                return ErrorResponse(
                    success=False,
                    message=f"Permission with name '{request.name}' already exists",
                    error_code="permission_exists"
                )
            
            # Create permission
            permission = manager.create_permission(
                name=request.name,
                resource_type=resource_type,
                actions=actions,
                description=request.description,
                resource_id=request.resource_id,
                conditions=request.conditions
            )
            
            # Convert to response format
            permission_detail = PermissionDetail(
                id=permission.id,
                name=permission.name,
                resource_type=permission.resource_type.value,
                actions=[action.value for action in permission.actions],
                description=permission.description,
                resource_id=permission.resource_id,
                conditions=permission.conditions,
                created_at=permission.created_at,
                updated_at=permission.updated_at
            )
            
            return StandardResponse(
                success=True,
                message=f"Permission {permission.name} created",
                data={"permission": permission_detail}
            )
        except Exception as e:
            logger.error(f"Error creating permission: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to create permission: {str(e)}",
                error_code="permission_create_error"
            )
    
    @router.put(
        "/permissions/{permission_id}",
        response_model=StandardResponse,
        summary="Update Permission",
        description="Update an existing permission."
    )
    async def update_permission(
        permission_id: str = Path(..., description="Permission ID"),
        request: PermissionUpdateRequest = None,
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Update a permission."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Check if permission exists
            if not manager.get_permission(permission_id):
                return ErrorResponse(
                    success=False,
                    message=f"Permission {permission_id} not found",
                    error_code="permission_not_found"
                )
            
            # Prepare update data
            update_data = {}
            
            if request:
                if request.name is not None:
                    update_data["name"] = request.name
                
                if request.description is not None:
                    update_data["description"] = request.description
                
                if request.actions is not None:
                    # Validate actions
                    try:
                        actions = set()
                        for action in request.actions:
                            actions.add(ActionType(action))
                        update_data["actions"] = actions
                    except ValueError as e:
                        return ErrorResponse(
                            success=False,
                            message=f"Invalid action type: {str(e)}",
                            error_code="invalid_action_type",
                            error_details={"valid_actions": [a.value for a in ActionType]}
                        )
                
                if request.resource_id is not None:
                    update_data["resource_id"] = request.resource_id
                
                if request.conditions is not None:
                    update_data["conditions"] = request.conditions
                
            # Update permission
            permission = manager.update_permission(permission_id, **update_data)
            
            # Convert to response format
            permission_detail = PermissionDetail(
                id=permission.id,
                name=permission.name,
                resource_type=permission.resource_type.value,
                actions=[action.value for action in permission.actions],
                description=permission.description,
                resource_id=permission.resource_id,
                conditions=permission.conditions,
                created_at=permission.created_at,
                updated_at=permission.updated_at
            )
            
            return StandardResponse(
                success=True,
                message=f"Permission {permission.name} updated",
                data={"permission": permission_detail}
            )
        except Exception as e:
            logger.error(f"Error updating permission {permission_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to update permission: {str(e)}",
                error_code="permission_update_error"
            )
    
    @router.delete(
        "/permissions/{permission_id}",
        response_model=StandardResponse,
        summary="Delete Permission",
        description="Delete a permission."
    )
    async def delete_permission(
        permission_id: str = Path(..., description="Permission ID"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Delete a permission."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Get permission first for the response
            permission = manager.get_permission(permission_id)
            if not permission:
                return ErrorResponse(
                    success=False,
                    message=f"Permission {permission_id} not found",
                    error_code="permission_not_found"
                )
            
            # Delete permission
            success = manager.delete_permission(permission_id)
            
            if not success:
                return ErrorResponse(
                    success=False,
                    message=f"Failed to delete permission {permission_id}. It may be in use by roles.",
                    error_code="permission_delete_error"
                )
            
            return StandardResponse(
                success=True,
                message=f"Permission {permission.name} deleted",
                data={"permission_id": permission_id}
            )
        except Exception as e:
            logger.error(f"Error deleting permission {permission_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to delete permission: {str(e)}",
                error_code="permission_delete_error"
            )
    
    # Role management endpoints
    
    @router.get(
        "/roles",
        response_model=StandardResponse,
        summary="List Roles",
        description="List all roles in the system."
    )
    async def list_roles(
        include_permissions: bool = Query(False, description="Include permission details for each role"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """List all roles."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Get roles
            roles = manager.list_roles()
            
            # Convert to response format
            role_list = []
            
            for role in roles:
                role_data = RoleInfo(
                    id=role.id,
                    name=role.name,
                    description=role.description,
                    created_at=role.created_at,
                    updated_at=role.updated_at
                )
                
                if include_permissions:
                    # Get full role with permissions
                    perm_ids = list(manager.get_role_permissions(role.id, include_parents=False))
                    
                    # Get permission details
                    perm_details = []
                    for perm_id in perm_ids:
                        perm = manager.get_permission(perm_id)
                        if perm:
                            perm_details.append(
                                PermissionInfo(
                                    id=perm.id,
                                    name=perm.name,
                                    resource_type=perm.resource_type.value,
                                    actions=[action.value for action in perm.actions],
                                    description=perm.description,
                                    created_at=perm.created_at,
                                    updated_at=perm.updated_at
                                )
                            )
                    
                    # Create role detail
                    role_detail = RoleDetail(
                        **role_data.dict(),
                        permissions=list(role.permissions),
                        parent_roles=list(role.parent_roles),
                        permission_details=perm_details
                    )
                    role_list.append(role_detail)
                else:
                    role_list.append(role_data)
            
            return StandardResponse(
                success=True,
                message=f"Found {len(role_list)} roles",
                data={"roles": role_list}
            )
        except Exception as e:
            logger.error(f"Error listing roles: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to list roles: {str(e)}",
                error_code="role_list_error"
            )
    
    @router.get(
        "/roles/{role_id}",
        response_model=StandardResponse,
        summary="Get Role",
        description="Get detailed information about a specific role."
    )
    async def get_role(
        role_id: str = Path(..., description="Role ID"),
        include_permissions: bool = Query(True, description="Include permission details"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Get a specific role by ID."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Get role from manager
            role = manager.get_role(role_id)
            
            if not role:
                return ErrorResponse(
                    success=False,
                    message=f"Role {role_id} not found",
                    error_code="role_not_found"
                )
            
            # Create response data
            role_data = RoleDetail(
                id=role.id,
                name=role.name,
                description=role.description,
                permissions=list(role.permissions),
                parent_roles=list(role.parent_roles),
                created_at=role.created_at,
                updated_at=role.updated_at
            )
            
            # Add permission details if requested
            if include_permissions:
                perm_details = []
                for perm_id in role.permissions:
                    perm = manager.get_permission(perm_id)
                    if perm:
                        perm_details.append(
                            PermissionInfo(
                                id=perm.id,
                                name=perm.name,
                                resource_type=perm.resource_type.value,
                                actions=[action.value for action in perm.actions],
                                description=perm.description,
                                created_at=perm.created_at,
                                updated_at=perm.updated_at
                            )
                        )
                
                role_data.permission_details = perm_details
            
            return StandardResponse(
                success=True,
                message=f"Role {role.name} retrieved",
                data={"role": role_data}
            )
        except Exception as e:
            logger.error(f"Error getting role {role_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to get role: {str(e)}",
                error_code="role_get_error"
            )
    
    @router.post(
        "/roles",
        response_model=StandardResponse,
        summary="Create Role",
        description="Create a new role."
    )
    async def create_role(
        request: RoleCreateRequest,
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Create a new role."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Check if role with same name already exists
            existing = manager.get_role_by_name(request.name)
            if existing:
                return ErrorResponse(
                    success=False,
                    message=f"Role with name '{request.name}' already exists",
                    error_code="role_exists"
                )
            
            # Validate permissions
            if request.permissions:
                for perm_id in request.permissions:
                    perm = manager.get_permission(perm_id)
                    if not perm:
                        return ErrorResponse(
                            success=False,
                            message=f"Permission {perm_id} not found",
                            error_code="permission_not_found",
                            error_details={"permission_id": perm_id}
                        )
            
            # Validate parent roles
            if request.parent_roles:
                for parent_id in request.parent_roles:
                    parent = manager.get_role(parent_id)
                    if not parent:
                        return ErrorResponse(
                            success=False,
                            message=f"Parent role {parent_id} not found",
                            error_code="role_not_found",
                            error_details={"role_id": parent_id}
                        )
            
            # Create role
            role = manager.create_role(
                name=request.name,
                description=request.description,
                permissions=request.permissions,
                parent_roles=request.parent_roles
            )
            
            # Convert to response format
            role_data = RoleDetail(
                id=role.id,
                name=role.name,
                description=role.description,
                permissions=list(role.permissions),
                parent_roles=list(role.parent_roles),
                created_at=role.created_at,
                updated_at=role.updated_at
            )
            
            return StandardResponse(
                success=True,
                message=f"Role {role.name} created",
                data={"role": role_data}
            )
        except ValueError as ve:
            logger.error(f"Validation error creating role: {ve}")
            return ErrorResponse(
                success=False,
                message=str(ve),
                error_code="role_validation_error"
            )
        except Exception as e:
            logger.error(f"Error creating role: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to create role: {str(e)}",
                error_code="role_create_error"
            )
    
    @router.put(
        "/roles/{role_id}",
        response_model=StandardResponse,
        summary="Update Role",
        description="Update an existing role."
    )
    async def update_role(
        role_id: str = Path(..., description="Role ID"),
        request: RoleUpdateRequest = None,
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Update a role."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Check if role exists
            if not manager.get_role(role_id):
                return ErrorResponse(
                    success=False,
                    message=f"Role {role_id} not found",
                    error_code="role_not_found"
                )
            
            # Prepare update data
            update_data = {}
            
            if request:
                if request.name is not None:
                    # Check for name conflict
                    existing = manager.get_role_by_name(request.name)
                    if existing and existing.id != role_id:
                        return ErrorResponse(
                            success=False,
                            message=f"Role with name '{request.name}' already exists",
                            error_code="role_exists"
                        )
                    update_data["name"] = request.name
                
                if request.description is not None:
                    update_data["description"] = request.description
                
                if request.permissions is not None:
                    # Validate permissions
                    for perm_id in request.permissions:
                        perm = manager.get_permission(perm_id)
                        if not perm:
                            return ErrorResponse(
                                success=False,
                                message=f"Permission {perm_id} not found",
                                error_code="permission_not_found",
                                error_details={"permission_id": perm_id}
                            )
                    update_data["permissions"] = request.permissions
                
                if request.parent_roles is not None:
                    # Validate parent roles
                    for parent_id in request.parent_roles:
                        parent = manager.get_role(parent_id)
                        if not parent:
                            return ErrorResponse(
                                success=False,
                                message=f"Parent role {parent_id} not found",
                                error_code="role_not_found",
                                error_details={"role_id": parent_id}
                            )
                    
                    # Check for cycles
                    if role_id in request.parent_roles:
                        return ErrorResponse(
                            success=False,
                            message="Role cannot be its own parent",
                            error_code="role_cycle_error"
                        )
                        
                    update_data["parent_roles"] = request.parent_roles
            
            # Update role
            role = manager.update_role(role_id, **update_data)
            
            # Create response data
            role_data = RoleDetail(
                id=role.id,
                name=role.name,
                description=role.description,
                permissions=list(role.permissions),
                parent_roles=list(role.parent_roles),
                created_at=role.created_at,
                updated_at=role.updated_at
            )
            
            return StandardResponse(
                success=True,
                message=f"Role {role.name} updated",
                data={"role": role_data}
            )
        except Exception as e:
            logger.error(f"Error updating role {role_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to update role: {str(e)}",
                error_code="role_update_error"
            )
    
    @router.delete(
        "/roles/{role_id}",
        response_model=StandardResponse,
        summary="Delete Role",
        description="Delete a role."
    )
    async def delete_role(
        role_id: str = Path(..., description="Role ID"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Delete a role."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Get role first for the response
            role = manager.get_role(role_id)
            if not role:
                return ErrorResponse(
                    success=False,
                    message=f"Role {role_id} not found",
                    error_code="role_not_found"
                )
            
            # Delete role
            success = manager.delete_role(role_id)
            
            if not success:
                return ErrorResponse(
                    success=False,
                    message=f"Failed to delete role {role_id}. It may be referenced by other roles.",
                    error_code="role_delete_error"
                )
            
            return StandardResponse(
                success=True,
                message=f"Role {role.name} deleted",
                data={"role_id": role_id}
            )
        except Exception as e:
            logger.error(f"Error deleting role {role_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to delete role: {str(e)}",
                error_code="role_delete_error"
            )
    
    # Role-permission management endpoints
    
    @router.post(
        "/roles/{role_id}/permissions/{permission_id}",
        response_model=StandardResponse,
        summary="Add Permission to Role",
        description="Add a permission to a role."
    )
    async def add_permission_to_role(
        role_id: str = Path(..., description="Role ID"),
        permission_id: str = Path(..., description="Permission ID"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Add a permission to a role."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Check if role exists
            role = manager.get_role(role_id)
            if not role:
                return ErrorResponse(
                    success=False,
                    message=f"Role {role_id} not found",
                    error_code="role_not_found"
                )
            
            # Check if permission exists
            permission = manager.get_permission(permission_id)
            if not permission:
                return ErrorResponse(
                    success=False,
                    message=f"Permission {permission_id} not found",
                    error_code="permission_not_found"
                )
            
            # Add permission to role
            if permission_id in role.permissions:
                return StandardResponse(
                    success=True,
                    message=f"Permission {permission.name} already assigned to role {role.name}",
                    data={"role_id": role_id, "permission_id": permission_id}
                )
            
            role.add_permission(permission_id)
            manager.store.save_role(role)
            
            return StandardResponse(
                success=True,
                message=f"Permission {permission.name} added to role {role.name}",
                data={"role_id": role_id, "permission_id": permission_id}
            )
        except Exception as e:
            logger.error(f"Error adding permission {permission_id} to role {role_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to add permission to role: {str(e)}",
                error_code="permission_add_error"
            )
    
    @router.delete(
        "/roles/{role_id}/permissions/{permission_id}",
        response_model=StandardResponse,
        summary="Remove Permission from Role",
        description="Remove a permission from a role."
    )
    async def remove_permission_from_role(
        role_id: str = Path(..., description="Role ID"),
        permission_id: str = Path(..., description="Permission ID"),
        current_admin = Depends(get_current_admin_user) if get_current_admin_user else None
    ):
        """Remove a permission from a role."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Check if role exists
            role = manager.get_role(role_id)
            if not role:
                return ErrorResponse(
                    success=False,
                    message=f"Role {role_id} not found",
                    error_code="role_not_found"
                )
            
            # Check if permission exists
            permission = manager.get_permission(permission_id)
            if not permission:
                return ErrorResponse(
                    success=False,
                    message=f"Permission {permission_id} not found",
                    error_code="permission_not_found"
                )
            
            # Remove permission from role
            if permission_id not in role.permissions:
                return StandardResponse(
                    success=True,
                    message=f"Permission {permission.name} not assigned to role {role.name}",
                    data={"role_id": role_id, "permission_id": permission_id}
                )
            
            role.remove_permission(permission_id)
            manager.store.save_role(role)
            
            return StandardResponse(
                success=True,
                message=f"Permission {permission.name} removed from role {role.name}",
                data={"role_id": role_id, "permission_id": permission_id}
            )
        except Exception as e:
            logger.error(f"Error removing permission {permission_id} from role {role_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to remove permission from role: {str(e)}",
                error_code="permission_remove_error"
            )
    
    # Authorization check endpoints
    
    @router.post(
        "/check/authorize",
        response_model=StandardResponse,
        summary="Check Authorization",
        description="Check if roles have permission for a specific action."
    )
    async def check_authorization(
        request: AuthorizationCheckRequest
    ):
        """Check authorization for an action."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Convert role names to IDs if needed
            role_ids = []
            for role in request.roles:
                if ":" in role or "-" in role:  # Assume UUID format
                    role_ids.append(role)
                else:
                    role_obj = manager.get_role_by_name(role)
                    if role_obj:
                        role_ids.append(role_obj.id)
            
            # Check authorization
            try:
                is_authorized = manager.has_permission(
                    role_ids=role_ids,
                    resource_type=request.resource_type,
                    action=request.action,
                    resource_id=request.resource_id,
                    context=request.context
                )
            except ValueError as e:
                return ErrorResponse(
                    success=False,
                    message=str(e),
                    error_code="authorization_check_error"
                )
            
            return StandardResponse(
                success=True,
                message="Authorization check completed",
                data={
                    "authorized": is_authorized,
                    "roles": request.roles,
                    "resource_type": request.resource_type,
                    "action": request.action,
                    "resource_id": request.resource_id
                }
            )
        except Exception as e:
            logger.error(f"Error checking authorization: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to check authorization: {str(e)}",
                error_code="authorization_check_error"
            )
    
    @router.post(
        "/check/permission",
        response_model=StandardResponse,
        summary="Check Permission",
        description="Check if a user has a specific permission."
    )
    async def check_permission(
        request: PermissionCheckRequest
    ):
        """Check if user has a specific permission."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Check permission
            is_authorized = manager.user_has_permission(
                user_roles=request.roles,
                permission_name=request.permission_name,
                resource_id=request.resource_id,
                context=request.context
            )
            
            return StandardResponse(
                success=True,
                message="Permission check completed",
                data={
                    "authorized": is_authorized,
                    "roles": request.roles,
                    "permission": request.permission_name,
                    "resource_id": request.resource_id
                }
            )
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to check permission: {str(e)}",
                error_code="permission_check_error"
            )
    
    @router.post(
        "/check/backend-permissions",
        response_model=StandardResponse,
        summary="Get Backend Permissions",
        description="Get backend-specific permissions for a user's roles."
    )
    async def get_backend_permissions(
        roles: List[str] = Body(..., description="List of role names or IDs")
    ):
        """Get backend-specific permissions for a user."""
        if manager is None:
            return ErrorResponse(
                success=False,
                message="RBAC manager not available",
                error_code="rbac_unavailable"
            )
        
        try:
            # Convert role names to IDs if needed
            role_ids = []
            for role in roles:
                if ":" in role or "-" in role:  # Assume UUID format
                    role_ids.append(role)
                else:
                    role_obj = manager.get_role_by_name(role)
                    if role_obj:
                        role_ids.append(role_obj.id)
            
            # Get backend permissions
            backend_permissions = manager.get_backend_permissions(role_ids)
            
            # Convert from sets to lists for JSON serialization
            serializable_permissions = {
                backend_id: list(actions)
                for backend_id, actions in backend_permissions.items()
            }
            
            return StandardResponse(
                success=True,
                message="Backend permissions retrieved",
                data={
                    "backend_permissions": serializable_permissions,
                    "roles": roles
                }
            )
        except Exception as e:
            logger.error(f"Error getting backend permissions: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to get backend permissions: {str(e)}",
                error_code="backend_permissions_error"
            )
    
    return router
#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) Example for MCP Server

This example demonstrates how to use the RBAC system to implement
role-based access control in an MCP server application.

Key features demonstrated:
1. Creating and managing roles
2. Defining permissions
3. Creating access policies
4. Checking permissions
5. Integration with FastAPI

Usage:
  python rbac_example.py [--server]
"""

import os
import json
import argparse
import logging
import tempfile
import asyncio
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("rbac-example")

# Import RBAC components
from ipfs_kit_py.mcp.auth.rbac import (
    RBACManager,
    Role,
    Permission,
    AccessPolicy,
    PermissionEffect
)

# Try importing FastAPI for the web server example
try:
    from fastapi import FastAPI, Depends, Header, HTTPException, Request
    from fastapi.responses import JSONResponse
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    logger.warning("FastAPI not available. Web server example will be skipped.")
    HAS_FASTAPI = False

# ------------------------------------------
# Example RBAC Configuration
# ------------------------------------------

def create_example_configuration():
    """Create example RBAC configuration files."""
    # Create temporary directory for configuration files
    config_dir = os.path.join(tempfile.gettempdir(), "mcp_rbac_example")
    os.makedirs(config_dir, exist_ok=True)
    
    # Define file paths
    roles_file = os.path.join(config_dir, "rbac_roles.json")
    permissions_file = os.path.join(config_dir, "rbac_permissions.json")
    policy_file = os.path.join(config_dir, "rbac_policy.json")
    
    # Create example permissions
    permissions = [
        # Storage permissions
        Permission(
            id="storage:read",
            name="Read Storage",
            description="Permission to read from storage",
            resource_type="storage",
            actions=["read", "list"]
        ),
        Permission(
            id="storage:write",
            name="Write Storage",
            description="Permission to write to storage",
            resource_type="storage",
            actions=["write", "create", "update"]
        ),
        Permission(
            id="storage:delete",
            name="Delete Storage",
            description="Permission to delete from storage",
            resource_type="storage",
            actions=["delete"]
        ),
        Permission(
            id="storage:admin",
            name="Storage Admin",
            description="Full control over storage",
            resource_type="storage",
            actions=["read", "list", "write", "create", "update", "delete", "admin"]
        ),
        
        # IPFS backend-specific permissions
        Permission(
            id="ipfs:read",
            name="IPFS Read",
            description="Permission to read from IPFS",
            resource_type="storage",
            actions=["read", "list"],
            backend_id="ipfs"
        ),
        Permission(
            id="ipfs:write",
            name="IPFS Write",
            description="Permission to write to IPFS",
            resource_type="storage",
            actions=["write", "create", "update"],
            backend_id="ipfs"
        ),
        
        # S3 backend-specific permissions
        Permission(
            id="s3:read",
            name="S3 Read",
            description="Permission to read from S3",
            resource_type="storage",
            actions=["read", "list"],
            backend_id="s3"
        ),
        Permission(
            id="s3:write",
            name="S3 Write",
            description="Permission to write to S3",
            resource_type="storage",
            actions=["write", "create", "update"],
            backend_id="s3"
        ),
        
        # Administrative permissions
        Permission(
            id="admin:full",
            name="Full Admin",
            description="Full administrative access",
            resource_type="admin",
            actions=["read", "write", "delete", "execute", "manage"]
        ),
        Permission(
            id="admin:readonly",
            name="Read-only Admin",
            description="Read-only administrative access",
            resource_type="admin",
            actions=["read"]
        ),
        
        # User management permissions
        Permission(
            id="users:read",
            name="Read Users",
            description="Permission to read user information",
            resource_type="users",
            actions=["read", "list"]
        ),
        Permission(
            id="users:manage",
            name="Manage Users",
            description="Permission to manage users",
            resource_type="users",
            actions=["read", "list", "create", "update", "delete"]
        ),
        
        # RBAC management permissions
        Permission(
            id="rbac:read",
            name="Read RBAC",
            description="Permission to read RBAC configuration",
            resource_type="rbac",
            actions=["read", "list"]
        ),
        Permission(
            id="rbac:manage",
            name="Manage RBAC",
            description="Permission to manage RBAC configuration",
            resource_type="rbac",
            actions=["read", "list", "create", "update", "delete"]
        ),
        
        # Explicit deny permission (example)
        Permission(
            id="storage:deny-delete",
            name="Deny Storage Delete",
            description="Explicitly deny delete from storage",
            resource_type="storage",
            actions=["delete"],
            effect=PermissionEffect.DENY
        )
    ]
    
    # Create example roles
    roles = [
        # Basic roles
        Role(
            id="reader",
            name="Reader",
            description="Read-only access to storage",
            permissions=["storage:read"]
        ),
        Role(
            id="writer",
            name="Writer",
            description="Read and write access to storage",
            permissions=["storage:read", "storage:write"]
        ),
        Role(
            id="contributor",
            name="Contributor",
            description="Read, write and delete access to storage",
            permissions=["storage:read", "storage:write", "storage:delete"]
        ),
        
        # Backend-specific roles
        Role(
            id="ipfs-user",
            name="IPFS User",
            description="Full access to IPFS backend",
            permissions=["ipfs:read", "ipfs:write"]
        ),
        Role(
            id="s3-user",
            name="S3 User",
            description="Full access to S3 backend",
            permissions=["s3:read", "s3:write"]
        ),
        
        # Administrative roles
        Role(
            id="admin",
            name="Administrator",
            description="Full administrative access",
            permissions=["admin:full", "storage:admin", "users:manage", "rbac:manage"]
        ),
        Role(
            id="readonly-admin",
            name="Read-only Administrator",
            description="Read-only administrative access",
            permissions=["admin:readonly", "storage:read", "users:read", "rbac:read"]
        ),
        
        # Custom roles with inheritance
        Role(
            id="support",
            name="Support",
            description="Support staff role",
            permissions=["users:read"],
            parent_roles=["readonly-admin"]
        ),
        Role(
            id="developer",
            name="Developer",
            description="Developer role",
            permissions=[],
            parent_roles=["writer", "ipfs-user"]
        ),
        Role(
            id="limited-contributor",
            name="Limited Contributor",
            description="Contributor who cannot delete",
            permissions=["storage:deny-delete"],
            parent_roles=["writer"]
        )
    ]
    
    # Create example policy
    policy = AccessPolicy(
        id="default-policy",
        name="Default Access Policy",
        description="Default access policy for the MCP server",
        role_assignments={
            "user1": ["reader"],
            "user2": ["writer"],
            "user3": ["contributor"],
            "admin1": ["admin"],
            "support1": ["support"],
            "dev1": ["developer"],
            "dev2": ["developer", "limited-contributor"]
        },
        group_role_assignments={
            "developers": ["developer"],
            "support-team": ["support"],
            "admins": ["admin"]
        },
        default_roles=["reader"],
        deny_by_default=True
    )
    
    # Write files
    with open(permissions_file, 'w') as f:
        json.dump(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "resource_type": p.resource_type,
                    "actions": p.actions,
                    "effect": p.effect.value,
                    "resource_prefix": p.resource_prefix,
                    "backend_id": p.backend_id,
                    "conditions": p.conditions
                }
                for p in permissions
            ],
            f,
            indent=2
        )
    
    with open(roles_file, 'w') as f:
        json.dump([vars(r) for r in roles], f, indent=2)
    
    with open(policy_file, 'w') as f:
        json.dump(vars(policy), f, indent=2)
    
    logger.info(f"Created example RBAC configuration in {config_dir}")
    
    return {
        "config_dir": config_dir,
        "roles_file": roles_file,
        "permissions_file": permissions_file,
        "policy_file": policy_file
    }

# ------------------------------------------
# Basic RBAC Usage Example
# ------------------------------------------

async def demonstrate_basic_usage(config_files: Dict[str, str]):
    """Demonstrate basic RBAC usage."""
    logger.info("=== Basic RBAC Usage Demonstration ===")
    
    # Create RBAC manager
    rbac_manager = RBACManager(
        roles_file=config_files["roles_file"],
        permissions_file=config_files["permissions_file"],
        policy_file=config_files["policy_file"],
        auto_save=True
    )
    
    # Example 1: Check if a user can read from storage
    user_id = "user1"  # Reader role
    can_read = rbac_manager.check_permission(
        user_id=user_id,
        action="read",
        resource_type="storage"
    )
    logger.info(f"Can {user_id} read from storage? {can_read}")
    
    # Example 2: Check if a user can write to storage
    can_write = rbac_manager.check_permission(
        user_id=user_id,
        action="write",
        resource_type="storage"
    )
    logger.info(f"Can {user_id} write to storage? {can_write}")
    
    # Example 3: Check a user with write permission
    user_id = "user2"  # Writer role
    can_write = rbac_manager.check_permission(
        user_id=user_id,
        action="write",
        resource_type="storage"
    )
    logger.info(f"Can {user_id} write to storage? {can_write}")
    
    # Example 4: Check backend-specific permissions
    user_id = "dev1"  # Developer role (includes IPFS access)
    can_write_ipfs = rbac_manager.check_permission(
        user_id=user_id,
        action="write",
        resource_type="storage",
        backend_id="ipfs"
    )
    can_write_s3 = rbac_manager.check_permission(
        user_id=user_id,
        action="write",
        resource_type="storage",
        backend_id="s3"
    )
    logger.info(f"Can {user_id} write to IPFS? {can_write_ipfs}")
    logger.info(f"Can {user_id} write to S3? {can_write_s3}")
    
    # Example 5: Check role with explicit deny
    user_id = "dev2"  # Developer + Limited Contributor roles
    can_delete = rbac_manager.check_permission(
        user_id=user_id,
        action="delete",
        resource_type="storage"
    )
    logger.info(f"Can {user_id} delete from storage? {can_delete} (should be False due to deny)")
    
    # Example 6: Group membership
    user_id = "new_user"  # Not explicitly assigned any roles
    group_ids = ["developers"]
    can_write_ipfs = rbac_manager.check_permission(
        user_id=user_id,
        action="write",
        resource_type="storage",
        backend_id="ipfs",
        group_ids=group_ids
    )
    logger.info(f"Can {user_id} (in developers group) write to IPFS? {can_write_ipfs}")

# ------------------------------------------
# Dynamic RBAC Management Example
# ------------------------------------------

async def demonstrate_dynamic_management(config_files: Dict[str, str]):
    """Demonstrate dynamic RBAC management."""
    logger.info("\n=== Dynamic RBAC Management Demonstration ===")
    
    # Create RBAC manager
    rbac_manager = RBACManager(
        roles_file=config_files["roles_file"],
        permissions_file=config_files["permissions_file"],
        policy_file=config_files["policy_file"],
        auto_save=True
    )
    
    # Example 1: Create a new permission
    new_permission = Permission(
        id="metrics:read",
        name="Read Metrics",
        description="Permission to read metrics",
        resource_type="metrics",
        actions=["read", "list"]
    )
    rbac_manager.create_permission(new_permission)
    logger.info(f"Created new permission: {new_permission.id}")
    
    # Example 2: Create a new role with the new permission
    new_role = Role(
        id="metrics-viewer",
        name="Metrics Viewer",
        description="Can view metrics",
        permissions=["metrics:read"]
    )
    rbac_manager.create_role(new_role)
    logger.info(f"Created new role: {new_role.id}")
    
    # Example 3: Assign the new role to a user
    user_id = "user1"
    rbac_manager.assign_role_to_user(user_id, new_role.id)
    logger.info(f"Assigned role {new_role.id} to user {user_id}")
    
    # Example 4: Check the new permission
    can_read_metrics = rbac_manager.check_permission(
        user_id=user_id,
        action="read",
        resource_type="metrics"
    )
    logger.info(f"Can {user_id} read metrics? {can_read_metrics}")
    
    # Example 5: Update a role to add another permission
    support_role = rbac_manager.get_role("support")
    if support_role:
        support_role.permissions.append("metrics:read")
        rbac_manager.update_role(support_role)
        logger.info(f"Added metrics:read permission to support role")
    
    # Example 6: Check if a support user can now read metrics
    support_user = "support1"
    can_read_metrics = rbac_manager.check_permission(
        user_id=support_user,
        action="read",
        resource_type="metrics"
    )
    logger.info(f"Can {support_user} read metrics? {can_read_metrics}")
    
    # Example 7: Create a new group and assign a role to it
    group_id = "metrics-team"
    rbac_manager.assign_role_to_group(group_id, "metrics-viewer")
    logger.info(f"Assigned role metrics-viewer to group {group_id}")
    
    # Example 8: Check permission for a user in the new group
    user_id = "new_user_2"  # No explicit roles
    group_ids = [group_id]
    can_read_metrics = rbac_manager.check_permission(
        user_id=user_id,
        action="read",
        resource_type="metrics",
        group_ids=group_ids
    )
    logger.info(f"Can {user_id} (in {group_id}) read metrics? {can_read_metrics}")

# ------------------------------------------
# FastAPI Integration Example
# ------------------------------------------

def create_fastapi_app(config_files: Dict[str, str]):
    """Create a FastAPI application with RBAC integration."""
    if not HAS_FASTAPI:
        logger.error("FastAPI is not available. Cannot create app.")
        return None
    
    app = FastAPI(title="RBAC Example API", version="1.0.0")
    security = HTTPBearer()
    
    # Create RBAC manager
    rbac_manager = RBACManager(
        roles_file=config_files["roles_file"],
        permissions_file=config_files["permissions_file"],
        policy_file=config_files["policy_file"],
        auto_save=True
    )
    
    # Mock user database
    # In a real application, this would be a database with proper authentication
    mock_users = {
        "token1": "user1",    # Reader
        "token2": "user2",    # Writer
        "token3": "user3",    # Contributor
        "token4": "admin1",   # Admin
        "token5": "support1", # Support
        "token6": "dev1",     # Developer
    }
    
    # Mock group memberships
    # In a real application, this would be in a database
    mock_group_memberships = {
        "user1": ["users"],
        "user2": ["users", "writers"],
        "user3": ["users", "contributors"],
        "admin1": ["users", "admins"],
        "support1": ["users", "support-team"],
        "dev1": ["users", "developers"],
    }
    
    # Authentication dependency
    async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
        token = credentials.credentials
        if token not in mock_users:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return mock_users[token]
    
    # RBAC authorization dependency factory
    def rbac_required(action: str, resource_type: str, backend_id: Optional[str] = None):
        async def rbac_dependency(request: Request, user_id: str = Depends(get_current_user)):
            # Get user's groups
            group_ids = mock_group_memberships.get(user_id, [])
            
            # Extra context for condition evaluation
            context = {
                "request_path": request.url.path,
                "request_method": request.method,
                "client_host": request.client.host if request.client else None,
            }
            
            # Get resource ID if available (e.g., from path parameters)
            resource_id = None
            try:
                path_params = request.path_params
                if "id" in path_params:
                    resource_id = path_params["id"]
            except Exception:
                pass
            
            # Check permission
            has_permission = rbac_manager.check_permission(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                backend_id=backend_id,
                group_ids=group_ids,
                context=context
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail=f"Not authorized to {action} {resource_type}"
                )
            
            return True
        return rbac_dependency
    
    # Define routes with RBAC authorization
    
    @app.get("/")
    async def root():
        """Public endpoint that doesn't require authentication or authorization."""
        return {"message": "Welcome to the RBAC Example API"}
    
    @app.get("/storage")
    async def list_storage(_: bool = Depends(rbac_required("list", "storage"))):
        """List storage items (requires 'list' permission on 'storage')."""
        return {"items": ["item1", "item2", "item3"]}
    
    @app.get("/storage/{id}")
    async def get_storage_item(id: str, _: bool = Depends(rbac_required("read", "storage"))):
        """Get a storage item (requires 'read' permission on 'storage')."""
        return {"id": id, "name": f"Item {id}", "data": "Some data"}
    
    @app.post("/storage")
    async def create_storage_item(_: bool = Depends(rbac_required("write", "storage"))):
        """Create a storage item (requires 'write' permission on 'storage')."""
        return {"id": "new-item", "status": "created"}
    
    @app.delete("/storage/{id}")
    async def delete_storage_item(id: str, _: bool = Depends(rbac_required("delete", "storage"))):
        """Delete a storage item (requires 'delete' permission on 'storage')."""
        return {"id": id, "status": "deleted"}
    
    @app.get("/ipfs")
    async def list_ipfs(_: bool = Depends(rbac_required("list", "storage", "ipfs"))):
        """List IPFS items (requires 'list' permission on 'storage' for 'ipfs' backend)."""
        return {"items": ["ipfs1", "ipfs2", "ipfs3"]}
    
    @app.get("/admin/users")
    async def admin_users(_: bool = Depends(rbac_required("read", "users"))):
        """List users (requires 'read' permission on 'users')."""
        return {"users": list(mock_users.values())}
    
    @app.get("/admin/roles")
    async def admin_roles(_: bool = Depends(rbac_required("read", "rbac"))):
        """List roles (requires 'read' permission on 'rbac')."""
        roles = rbac_manager.get_all_roles()
        return {"roles": [{"id": r.id, "name": r.name} for r in roles.values()]}
    
    @app.get("/me")
    async def get_my_roles(user_id: str = Depends(get_current_user)):
        """Get current user's roles."""
        roles = rbac_manager.get_user_roles(user_id)
        group_ids = mock_group_memberships.get(user_id, [])
        group_roles = []
        for group_id in group_ids:
            group_roles.extend(rbac_manager.get_group_roles(group_id))
        
        return {
            "user_id": user_id,
            "roles": roles,
            "groups": group_ids,
            "group_roles": group_roles
        }
    
    return app

# ------------------------------------------
# Main Example Runner
# ------------------------------------------

async def run_examples():
    """Run all the examples."""
    logger.info("Running RBAC examples")
    
    # Create example configuration
    config_files = create_example_configuration()
    
    # Run the examples
    await demonstrate_basic_usage(config_files)
    await demonstrate_dynamic_management(config_files)
    
    logger.info("\n=== Examples Completed ===")
    logger.info("RBAC configuration files are in:")
    for key, value in config_files.items():
        if key != "config_dir":
            logger.info(f"  {key}: {value}")

def run_fastapi_example(config_files: Dict[str, str]):
    """Run the FastAPI example server."""
    app = create_fastapi_app(config_files)
    if not app:
        return
    
    logger.info("\nStarting RBAC Example API Server")
    logger.info("Available endpoints:")
    logger.info("  GET / - Public endpoint")
    logger.info("  GET /storage - List storage items (requires 'list' permission)")
    logger.info("  GET /storage/{id} - Get storage item (requires 'read' permission)")
    logger.info("  POST /storage - Create storage item (requires 'write' permission)")
    logger.info("  DELETE /storage/{id} - Delete storage item (requires 'delete' permission)")
    logger.info("  GET /ipfs - List IPFS items (requires 'list' permission for IPFS backend)")
    logger.info("  GET /admin/users - List users (requires 'read' permission on 'users')")
    logger.info("  GET /admin/roles - List roles (requires 'read' permission on 'rbac')")
    logger.info("  GET /me - Get current user's roles")
    logger.info("\nAvailable tokens (use as Bearer tokens):")
    logger.info("  token1: user1 (Reader)")
    logger.info("  token2: user2 (Writer)")
    logger.info("  token3: user3 (Contributor)")
    logger.info("  token4: admin1 (Admin)")
    logger.info("  token5: support1 (Support)")
    logger.info("  token6: dev1 (Developer)")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RBAC Example")
    parser.add_argument("--server", action="store_true", help="Run FastAPI server example")
    args = parser.parse_args()
    
    # Create example configuration
    config_files = create_example_configuration()
    
    if args.server and HAS_FASTAPI:
        run_fastapi_example(config_files)
    else:
        asyncio.run(run_examples())

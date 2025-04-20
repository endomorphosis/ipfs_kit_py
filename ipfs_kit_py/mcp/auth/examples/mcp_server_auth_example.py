"""
MCP Server with Advanced Authentication & Authorization Example

This module demonstrates how to integrate the Advanced Authentication & Authorization system
with the MCP server. It shows the key integration points and configuration options.

This is a simplified version of the main server to focus on auth integration.
"""

import os
import sys
import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server_auth_example")

# Create FastAPI app
app = FastAPI(
    title="MCP Server with Advanced Auth",
    description="Example of MCP server with Advanced Authentication & Authorization",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import MCP components
try:
    # Storage Manager (minimal imports for example)
    from ipfs_kit_py.mcp.storage_manager.backend_manager import BackendManager
    from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
    
    # Advanced Authentication & Authorization
    from ipfs_kit_py.mcp.auth.mcp_auth_integration import (
        setup_mcp_auth, get_mcp_auth,
        audit_login_attempt, audit_permission_check, audit_backend_access
    )
    from ipfs_kit_py.mcp.auth.models import User, Role, Permission
    from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
    
    # Component initialization success
    COMPONENTS_INITIALIZED = True
    
except ImportError as e:
    logger.error(f"Error importing MCP components: {e}")
    COMPONENTS_INITIALIZED = False


# Global component instances
backend_manager = None
auth_system = None


async def initialize_components():
    """Initialize MCP components."""
    global backend_manager, auth_system
    
    logger.info("Initializing MCP components...")
    
    # Initialize Backend Manager
    backend_manager = BackendManager()
    
    # Configure default IPFS backend
    ipfs_resources = {
        "ipfs_host": os.environ.get("IPFS_HOST", "127.0.0.1"),
        "ipfs_port": int(os.environ.get("IPFS_PORT", "5001")),
        "ipfs_timeout": int(os.environ.get("IPFS_TIMEOUT", "30")),
        "allow_mock": os.environ.get("ALLOW_MOCK", "1") == "1"
    }
    
    ipfs_metadata = {
        "backend_name": "ipfs",
        "description": "IPFS backend"
    }
    
    # Create and add IPFS backend
    try:
        ipfs_backend = IPFSBackend(ipfs_resources, ipfs_metadata)
        backend_manager.add_backend("ipfs", ipfs_backend)
        logger.info("Added IPFS backend to manager")
    except Exception as e:
        logger.error(f"Error initializing IPFS backend: {e}")
    
    # Initialize Advanced Authentication & Authorization System
    auth_config = {
        # JWT configuration
        "token_secret": os.environ.get("MCP_JWT_SECRET", "change-me-in-production"),
        "token_algorithm": "HS256",
        "token_expire_minutes": 1440,  # 24 hours
        
        # Admin account
        "admin_username": os.environ.get("MCP_ADMIN_USERNAME", "admin"),
        "admin_password": os.environ.get("MCP_ADMIN_PASSWORD", "change-me-in-production"),
        
        # OAuth providers (configure as needed)
        "oauth_providers": {
            "github": {
                "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
                "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", ""),
                "redirect_uri": os.environ.get("GITHUB_REDIRECT_URI", "")
            },
            "google": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "redirect_uri": os.environ.get("GOOGLE_REDIRECT_URI", "")
            }
        },
        
        # Custom roles
        "custom_roles": [
            {
                "id": "data_scientist",
                "name": "Data Scientist",
                "parent_role": "user",
                "permissions": [
                    "read:ipfs", "write:ipfs", 
                    "read:search", "write:search"
                ]
            },
            {
                "id": "operations",
                "name": "Operations",
                "parent_role": "user",
                "permissions": [
                    "read:ipfs", "write:ipfs", "pin:ipfs",
                    "read:monitoring", "write:monitoring"
                ]
            },
            {
                "id": "content_manager",
                "name": "Content Manager",
                "parent_role": "user",
                "permissions": [
                    "read:ipfs", "write:ipfs", 
                    "read:s3", "write:s3"
                ]
            }
        ]
    }
    
    auth_system = await setup_mcp_auth(
        app=app,
        backend_manager=backend_manager,
        config=auth_config
    )
    
    if auth_system and auth_system.initialized:
        logger.info("Advanced Authentication & Authorization system initialized")
        
        # Configure backend permissions
        await auth_system.configure_backend_permissions({
            "ipfs": ["read", "write", "pin", "admin"],
            "s3": ["read", "write", "delete"],
            "filecoin": ["read", "write", "verify"]
        })
    else:
        logger.error("Failed to initialize auth system")
    
    logger.info("All MCP components initialized")


# API Router for server info
@app.get("/api/v0/info")
async def server_info():
    """Get server information (public endpoint)."""
    return {
        "name": "MCP Server with Advanced Auth",
        "version": "1.0.0",
        "auth_system": "Advanced Authentication & Authorization",
        "components_initialized": COMPONENTS_INITIALIZED
    }


# API Router for user profile - requires authentication
@app.get("/api/v0/auth/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user profile.
    
    Requires authentication.
    """
    # Log access
    audit_backend_access(
        user_id=current_user.id,
        backend="auth",
        operation="get_profile",
        granted=True
    )
    
    return {
        "success": True,
        "profile": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "created_at": current_user.created_at
        }
    }


# API Router for IPFS operations - requires specific backend permissions
@app.get("/api/v0/ipfs/version")
async def ipfs_version(current_user: User = Depends(get_current_user)):
    """
    Get IPFS version.
    
    Requires 'read:ipfs' permission.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        # Log backend access
        audit_backend_access(
            user_id=current_user.id,
            backend="ipfs",
            operation="version",
            granted=True
        )
        
        return {"version": "0.12.0", "backend": "ipfs"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v0/ipfs/add")
async def ipfs_add(
    file: UploadFile = File(...), 
    pin: bool = Form(True),
    current_user: User = Depends(get_current_user)
):
    """
    Add content to IPFS.
    
    Requires 'write:ipfs' permission.
    """
    if not COMPONENTS_INITIALIZED or not backend_manager:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        ipfs_backend = backend_manager.get_backend("ipfs")
        if not ipfs_backend:
            raise HTTPException(status_code=404, detail="IPFS backend not found")
        
        # Check permission (automatically enforced by backend middleware,
        # but shown here for example purposes)
        auth_system = get_mcp_auth()
        has_permission = auth_system.rbac_manager.user_has_permission(
            user_roles=[current_user.role],
            permission_name="write:ipfs"
        )
        
        if not has_permission and current_user.role != Role.ADMIN:
            # Log permission check
            audit_permission_check(
                user_id=current_user.id,
                permission="write:ipfs",
                granted=False
            )
            
            raise HTTPException(
                status_code=403,
                detail="Permission denied: You need 'write:ipfs' permission"
            )
        
        # Read file content
        content = await file.read()
        
        # Add to IPFS
        result = await ipfs_backend.add_content(content, {"filename": file.filename})
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to add content to IPFS")
            )
        
        # Pin if requested
        if pin and result.get("identifier"):
            await ipfs_backend.pin_add(result["identifier"])
        
        # Log successful operation
        audit_backend_access(
            user_id=current_user.id,
            backend="ipfs",
            operation="add",
            granted=True,
            details={
                "filename": file.filename,
                "success": True,
                "cid": result.get("identifier")
            }
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Admin endpoint - requires admin role
@app.get("/api/v0/admin/users")
async def list_users(admin_user: User = Depends(get_admin_user)):
    """
    List all users.
    
    Requires admin role.
    """
    if not COMPONENTS_INITIALIZED or not auth_system:
        raise HTTPException(status_code=500, detail="MCP components not initialized")
    
    try:
        # Get list of users
        auth_service = auth_system.auth_system.auth_service
        users = await auth_service.list_users()
        
        # Log admin access
        audit_backend_access(
            user_id=admin_user.id,
            backend="auth",
            operation="list_users",
            granted=True
        )
        
        return {
            "success": True,
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "created_at": user.created_at
                }
                for user in users
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint (no auth required)
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "components_initialized": COMPONENTS_INITIALIZED,
        "auth_initialized": auth_system and auth_system.initialized if auth_system else False
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    if COMPONENTS_INITIALIZED:
        await initialize_components()


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    # Add any cleanup tasks here
    pass


# Main entry point
def main():
    """Run the MCP server."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="MCP Server with Advanced Auth")
    parser.add_argument("--host", default="0.0.0.0", help="Host to listen on")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()
    
    # Import and run server
    import uvicorn
    uvicorn.run(
        "mcp_server_auth_example:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
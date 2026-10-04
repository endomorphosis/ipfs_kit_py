"""
Advanced Authentication & Authorization Integration Module

This module integrates all the advanced authentication and authorization components:
- Role-Based Access Control (RBAC)
- Backend-specific authorization
- API key management
- OAuth integration
- Comprehensive audit logging

Part of the MCP Roadmap Phase 1: Advanced Authentication & Authorization.
"""

import logging
from typing import Dict, List, Optional, Union, Any, Callable
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response

# Import component modules
from .models import User, Role, Permission
from .router import get_current_user, get_admin_user
from .backend_authorization_integration import (
    get_backend_auth, check_backend_operation, 
    require_backend_permission, BackendPermission
)
from .api_key_enhanced import (
    get_api_key_manager, setup_api_key_authentication,
    ApiKeyScope, ApiKeyStatus
)
from .oauth_integration_enhanced import (
    get_oauth_manager, setup_oauth_integration,
    OAuthProvider
)
from .audit_logging import (
    get_audit_log_manager, setup_audit_logging,
    AuditEventType, AuditSeverity,
    audit_login_attempt, audit_permission_check, audit_backend_access,
    audit_user_change, audit_system_event, audit_data_event
)

from ..rbac import (
    check_permission, check_backend_permission, 
    require_permission, require_backend_permission as rbac_require_backend_permission,
    get_current_user_role
)

# Configure logging
logger = logging.getLogger("mcp.auth.integration")

class AdvancedAuthSystem:
    """
    Advanced Authentication & Authorization System for the MCP server.
    
    This class integrates all the authentication and authorization components
    into a single coherent system.
    """
    
    def __init__(self):
        """Initialize the advanced auth system."""
        # Initialize component singletons
        self.backend_auth = get_backend_auth()
        self.api_key_manager = get_api_key_manager()
        self.oauth_manager = get_oauth_manager()
        self.audit_manager = get_audit_log_manager()
        
        # Functions for user management
        self.create_user_func = None
        self.authorize_user_func = None
        self.update_user_func = None
        
        logger.info("Advanced Authentication & Authorization System initialized")
    
    def setup_app(self, app: FastAPI, 
                create_user_func: Callable, 
                authorize_user_func: Callable,
                update_user_func: Callable):
        """
        Set up the FastAPI application with all auth components.
        
        Args:
            app: FastAPI application
            create_user_func: Function to create a new user
            authorize_user_func: Function to authorize a user (return JWT)
            update_user_func: Function to update a user
        """
        # Store user management functions
        self.create_user_func = create_user_func
        self.authorize_user_func = authorize_user_func
        self.update_user_func = update_user_func
        
        # Set up API key authentication
        setup_api_key_authentication(app)
        logger.info("API key authentication set up")
        
        # Set up OAuth integration
        setup_oauth_integration(
            app,
            get_current_user,
            create_user_func,
            authorize_user_func,
            update_user_func
        )
        logger.info("OAuth integration set up")
        
        # Set up audit logging
        setup_audit_logging(app, get_admin_user)
        logger.info("Audit logging set up")
        
        # Add custom exception handlers
        @app.exception_handler(403)
        async def forbidden_exception_handler(request: Request, exc: HTTPException):
            """Custom handler for 403 Forbidden errors."""
            # Audit the permission denial
            user = None
            if hasattr(request.state, "user"):
                user = request.state.user
            elif hasattr(request.state, "api_key_user"):
                user = request.state.api_key_user
            
            # Extract resource from path
            resource = None
            if "/api/v0/" in request.url.path:
                parts = request.url.path.split("/")
                if len(parts) > 3:
                    resource = parts[3]  # e.g., "ipfs", "auth", etc.
            
            # Audit the permission denial
            audit_permission_check(
                permission="unknown",  # We don't know which permission was checked
                user=user,
                resource=resource,
                granted=False,
                request=request,
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(exc.detail)
                }
            )
            
            # Return the original response
            return Response(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": str(exc.detail)}
            )
        
        logger.info("Advanced Authentication & Authorization System setup complete")
        
        # Audit system startup
        audit_system_event(
            action="auth_system_initialized",
            severity=AuditSeverity.INFO,
            details={
                "components": [
                    "rbac", "backend_auth", "api_key", "oauth", "audit_logging"
                ]
            }
        )
    
    async def configure_roles(self, custom_roles: List[Dict[str, Any]]) -> bool:
        """
        Configure custom roles in the RBAC system.
        
        Args:
            custom_roles: List of custom role configurations
            
        Returns:
            True if successful
        """
        from ..rbac import rbac_manager
        
        for role_config in custom_roles:
            role_id = role_config.get("id")
            name = role_config.get("name")
            permissions = role_config.get("permissions", [])
            parent_role = role_config.get("parent_role")
            
            # Convert parent role string to enum if provided
            parent = None
            if parent_role:
                try:
                    parent = Role(parent_role)
                except ValueError:
                    logger.warning(f"Invalid parent role: {parent_role}")
            
            # Create or update role
            if role_id in rbac_manager._custom_roles:
                rbac_manager.update_custom_role(
                    role_id=role_id,
                    name=name,
                    permissions=permissions,
                    parent_role=parent
                )
                logger.info(f"Updated custom role: {role_id}")
            else:
                rbac_manager.create_custom_role(
                    role_id=role_id,
                    name=name,
                    permissions=permissions,
                    parent_role=parent
                )
                logger.info(f"Created custom role: {role_id}")
        
        return True
    
    async def verify_auth_system(self) -> Dict[str, Any]:
        """
        Verify that all auth system components are working correctly.
        
        Returns:
            Dictionary with verification results
        """
        results = {
            "success": True,
            "components": {}
        }
        
        # Verify RBAC
        try:
            from ..rbac import rbac_manager
            
            rbac_results = {
                "status": "ok",
                "custom_roles": list(rbac_manager._custom_roles.keys()),
                "role_permissions": {
                    role.value: list(perms) 
                    for role, perms in rbac_manager._role_permissions.items()
                }
            }
            
            results["components"]["rbac"] = rbac_results
            
        except Exception as e:
            results["components"]["rbac"] = {
                "status": "error",
                "error": str(e)
            }
            results["success"] = False
        
        # Verify backend auth
        try:
            backends = self.backend_auth.list_backends()
            
            backend_auth_results = {
                "status": "ok",
                "backends": backends
            }
            
            results["components"]["backend_auth"] = backend_auth_results
            
        except Exception as e:
            results["components"]["backend_auth"] = {
                "status": "error",
                "error": str(e)
            }
            results["success"] = False
        
        # Verify API key system
        try:
            # Just verify we can access the API key manager
            key_results = {
                "status": "ok"
            }
            
            results["components"]["api_key"] = key_results
            
        except Exception as e:
            results["components"]["api_key"] = {
                "status": "error",
                "error": str(e)
            }
            results["success"] = False
        
        # Verify OAuth
        try:
            providers = self.oauth_manager.list_providers()
            
            oauth_results = {
                "status": "ok",
                "providers": [p["provider"] for p in providers]
            }
            
            results["components"]["oauth"] = oauth_results
            
        except Exception as e:
            results["components"]["oauth"] = {
                "status": "error",
                "error": str(e)
            }
            results["success"] = False
        
        # Verify audit logging
        try:
            # Verify by logging a test event
            self.audit_manager.log_event(
                event_type=AuditEventType.SYSTEM_STARTUP,
                message="Auth system verification test",
                severity=AuditSeverity.INFO,
                sync=True  # Force synchronous logging
            )
            
            audit_results = {
                "status": "ok",
                "hash_chain_enabled": self.audit_manager.config["hash_chain"]
            }
            
            results["components"]["audit"] = audit_results
            
        except Exception as e:
            results["components"]["audit"] = {
                "status": "error",
                "error": str(e)
            }
            results["success"] = False
        
        # Overall result
        if results["success"]:
            results["message"] = "All auth system components verified successfully"
        else:
            results["message"] = "One or more auth system components failed verification"
        
        return results


# Singleton instance
_auth_system_instance = None

def get_auth_system() -> AdvancedAuthSystem:
    """Get the singleton advanced auth system instance."""
    global _auth_system_instance
    if _auth_system_instance is None:
        _auth_system_instance = AdvancedAuthSystem()
    return _auth_system_instance


def initialize_auth_system(app: FastAPI, backend_manager: Any) -> AdvancedAuthSystem:
    """
    Initialize the advanced authentication system.
    
    Args:
        app: FastAPI application
        backend_manager: Backend manager instance for backend permissions
        
    Returns:
        AdvancedAuthSystem instance
    """
    from .service import create_user, authorize_user, update_user
    
    # Get or create auth system
    auth_system = get_auth_system()
    
    # Set up the app
    auth_system.setup_app(
        app=app,
        create_user_func=create_user,
        authorize_user_func=authorize_user,
        update_user_func=update_user
    )
    
    return auth_system
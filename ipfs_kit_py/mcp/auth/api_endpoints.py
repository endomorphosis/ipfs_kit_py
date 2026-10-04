#!/usr/bin/env python3
# ipfs_kit_py/mcp/auth/api_endpoints.py

"""
Authentication and Authorization API Endpoints for IPFS Kit MCP Server.

This module provides API handlers for auth-related operations such as:
- User management
- Role management
- Permission management
- API key management
- OAuth integration
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

# Import auth modules
from .rbac_enhanced import (
    Action, ApiKey, Permission, ResourceType, Role, RBACService, 
    AuthorizationResult, require_permission
)
from .oauth_integration import OAuthManager, OAuthProvider

# Set up logging
logger = logging.getLogger(__name__)


class AuthHandler:
    """
    Handles authentication and authorization API endpoints.
    
    This class provides methods that can be integrated with any web framework
    (FastAPI, Flask, etc.) to provide auth-related functionality.
    """
    
    def __init__(self, rbac_service: RBACService, oauth_manager: Optional[OAuthManager] = None):
        """
        Initialize the auth handler.
        
        Args:
            rbac_service: RBAC service instance
            oauth_manager: Optional OAuth manager instance
        """
        self.rbac_service = rbac_service
        self.oauth_manager = oauth_manager
        self.authenticator = rbac_service.authenticator
    
    # -------------------------------------------------------------------------
    # Authentication endpoints
    # -------------------------------------------------------------------------
    
    def login(self, request: Any) -> Dict[str, Any]:
        """
        Handle basic username/password login.
        
        In a real implementation, this would validate credentials against a database.
        For this example, we'll just simulate successful login.
        
        Args:
            request: Request object with JSON body containing username and password
        
        Returns:
            Dict[str, Any]: Response with token if successful
        """
        # In a real implementation, authenticate the user here
        # For this example, we just return a mock token
        return {
            "success": True,
            "token": "mock_token_123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "user": {
                "user_id": "user123",
                "username": "test_user",
                "roles": ["user"]
            }
        }
    
    def logout(self, request: Any) -> Dict[str, Any]:
        """
        Handle user logout.
        
        Args:
            request: Request object
        
        Returns:
            Dict[str, Any]: Success response
        """
        # In a real implementation, invalidate the session/token here
        return {"success": True, "message": "Logged out successfully"}
    
    def oauth_login(self, request: Any) -> Dict[str, Any]:
        """
        Initiate OAuth login flow.
        
        Args:
            request: Request object with query parameter 'provider'
        
        Returns:
            Dict[str, Any]: Response with authorization URL
        """
        if not self.oauth_manager:
            return {"error": "OAuth not configured"}
        
        # Get the provider from the request
        provider_name = request.query_params.get("provider")
        if not provider_name:
            return {"error": "Missing provider parameter"}
        
        try:
            # Get the authorization URL
            provider = OAuthProvider(provider_name)
            redirect_uri = request.query_params.get("redirect_uri")
            
            # Extra state data
            state_data = {
                "redirect_after_login": request.query_params.get("redirect_after_login", "/"),
                "user_id": request.query_params.get("user_id")  # For linking existing accounts
            }
            
            extra_params = {}
            if redirect_uri:
                # Override the default redirect URI if provided
                config = self.oauth_manager.get_provider_config(provider)
                if config:
                    config.redirect_uri = redirect_uri
            
            auth_url, state = self.oauth_manager.get_authorization_url(
                provider, extra_params=extra_params, state_data=state_data
            )
            
            return {
                "success": True,
                "auth_url": auth_url,
                "state": state
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"Error initiating OAuth flow: {e}")
            return {"error": f"Invalid provider: {provider_name}"}
    
    def oauth_callback(self, request: Any) -> Dict[str, Any]:
        """
        Handle OAuth callback.
        
        Args:
            request: Request object with query parameters 'code' and 'state'
        
        Returns:
            Dict[str, Any]: Response with token if successful
        """
        if not self.oauth_manager:
            return {"error": "OAuth not configured"}
        
        # Get parameters from the request
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        provider_name = request.query_params.get("provider")
        
        if not code or not state or not provider_name:
            return {"error": "Missing required parameters"}
        
        try:
            provider = OAuthProvider(provider_name)
            
            # Exchange the code for a token
            success, token, state_data = self.oauth_manager.exchange_code_for_token(
                provider, code, state=state
            )
            
            if not success or not token:
                return {"error": "Failed to exchange code for token"}
            
            # Get user information
            user_info = self.oauth_manager.get_user_info(provider, token)
            if not user_info:
                return {"error": "Failed to get user information"}
            
            # In a real implementation, create or update a user in the database
            # For this example, we just return the user info
            return {
                "success": True,
                "user_info": {
                    "provider": user_info.provider.value,
                    "provider_user_id": user_info.provider_user_id,
                    "username": user_info.username,
                    "email": user_info.email,
                    "display_name": user_info.display_name
                },
                "token": {
                    "access_token": token.access_token,
                    "token_type": token.token_type,
                    "expires_at": token.expires_at
                },
                "redirect_to": state_data.get("redirect_after_login", "/") if state_data else "/"
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"Error handling OAuth callback: {e}")
            return {"error": f"Invalid provider: {provider_name}"}
    
    # -------------------------------------------------------------------------
    # User management endpoints
    # -------------------------------------------------------------------------
    
    @require_permission("admin", ResourceType.USER)
    def list_users(self, request: Any) -> Dict[str, Any]:
        """
        List all users.
        
        Args:
            request: Request object
        
        Returns:
            Dict[str, Any]: Response with list of users
        """
        # In a real implementation, get users from a database
        # For this example, we just return mock data
        users = [
            {
                "user_id": "user123",
                "username": "test_user",
                "email": "test@example.com",
                "roles": ["user"],
                "created_at": time.time() - 86400,
                "last_login": time.time() - 3600
            },
            {
                "user_id": "admin456",
                "username": "admin_user",
                "email": "admin@example.com",
                "roles": ["admin"],
                "created_at": time.time() - 172800,
                "last_login": time.time() - 7200
            }
        ]
        
        return {"success": True, "users": users}
    
    @require_permission("admin", ResourceType.USER)
    def get_user(self, request: Any, user_id: str) -> Dict[str, Any]:
        """
        Get a user by ID.
        
        Args:
            request: Request object
            user_id: User ID
        
        Returns:
            Dict[str, Any]: Response with user data
        """
        # In a real implementation, get the user from a database
        # For this example, we just return mock data
        if user_id == "user123":
            return {
                "success": True,
                "user": {
                    "user_id": "user123",
                    "username": "test_user",
                    "email": "test@example.com",
                    "roles": ["user"],
                    "created_at": time.time() - 86400,
                    "last_login": time.time() - 3600
                }
            }
        elif user_id == "admin456":
            return {
                "success": True,
                "user": {
                    "user_id": "admin456",
                    "username": "admin_user",
                    "email": "admin@example.com",
                    "roles": ["admin"],
                    "created_at": time.time() - 172800,
                    "last_login": time.time() - 7200
                }
            }
        else:
            return {"error": "User not found"}
    
    @require_permission("admin", ResourceType.USER)
    def create_user(self, request: Any) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            request: Request object with JSON body containing user data
        
        Returns:
            Dict[str, Any]: Response with created user
        """
        # In a real implementation, create a user in the database
        # For this example, we just return a mock response
        try:
            # Parse request body
            body = request.json()
            
            # Validate required fields
            required_fields = ["username", "email", "password"]
            for field in required_fields:
                if field not in body:
                    return {"error": f"Missing required field: {field}"}
            
            # Create the user (mock)
            user = {
                "user_id": "new_user_789",
                "username": body["username"],
                "email": body["email"],
                "roles": body.get("roles", ["user"]),
                "created_at": time.time(),
                "last_login": None
            }
            
            return {"success": True, "user": user}
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return {"error": "Invalid request body"}
    
    @require_permission("admin", ResourceType.USER)
    def update_user(self, request: Any, user_id: str) -> Dict[str, Any]:
        """
        Update a user.
        
        Args:
            request: Request object with JSON body containing user data
            user_id: User ID
        
        Returns:
            Dict[str, Any]: Response with updated user
        """
        # In a real implementation, update the user in the database
        # For this example, we just return a mock response
        try:
            # Parse request body
            body = request.json()
            
            # Check if user exists
            if user_id not in ["user123", "admin456"]:
                return {"error": "User not found"}
            
            # Update the user (mock)
            user = {
                "user_id": user_id,
                "username": body.get("username", "test_user"),
                "email": body.get("email", "test@example.com"),
                "roles": body.get("roles", ["user"]),
                "created_at": time.time() - 86400,
                "last_login": time.time() - 3600
            }
            
            return {"success": True, "user": user}
            
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return {"error": "Invalid request body"}
    
    @require_permission("admin", ResourceType.USER)
    def delete_user(self, request: Any, user_id: str) -> Dict[str, Any]:
        """
        Delete a user.
        
        Args:
            request: Request object
            user_id: User ID
        
        Returns:
            Dict[str, Any]: Success response
        """
        # In a real implementation, delete the user from the database
        # For this example, we just return a mock response
        if user_id not in ["user123", "admin456"]:
            return {"error": "User not found"}
            
        return {"success": True, "message": f"User {user_id} deleted successfully"}
    
    # -------------------------------------------------------------------------
    # Role management endpoints
    # -------------------------------------------------------------------------
    
    @require_permission("admin", ResourceType.USER)
    def list_roles(self, request: Any) -> Dict[str, Any]:
        """
        List all roles.
        
        Args:
            request: Request object
        
        Returns:
            Dict[str, Any]: Response with list of roles
        """
        roles = []
        for name, role in self.rbac_service.role_manager.roles.items():
            permissions = [{"name": p.name, "resource_type": p.resource_type.name} for p in role.permissions]
            roles.append({
                "name": role.name,
                "description": role.description,
                "permissions": permissions,
                "parent_roles": list(role.parent_roles)
            })
        
        return {"success": True, "roles": roles}
    
    @require_permission("admin", ResourceType.USER)
    def get_role(self, request: Any, role_name: str) -> Dict[str, Any]:
        """
        Get a role by name.
        
        Args:
            request: Request object
            role_name: Role name
        
        Returns:
            Dict[str, Any]: Response with role data
        """
        role = self.rbac_service.get_role(role_name)
        if not role:
            return {"error": "Role not found"}
        
        permissions = [{"name": p.name, "resource_type": p.resource_type.name} for p in role.permissions]
        
        return {
            "success": True,
            "role": {
                "name": role.name,
                "description": role.description,
                "permissions": permissions,
                "parent_roles": list(role.parent_roles)
            }
        }
    
    @require_permission("admin", ResourceType.USER)
    def create_role(self, request: Any) -> Dict[str, Any]:
        """
        Create a new role.
        
        Args:
            request: Request object with JSON body containing role data
        
        Returns:
            Dict[str, Any]: Response with created role
        """
        try:
            # Parse request body
            body = request.json()
            
            # Validate required fields
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in body:
                    return {"error": f"Missing required field: {field}"}
            
            # Check if role already exists
            if self.rbac_service.get_role(body["name"]):
                return {"error": f"Role {body['name']} already exists"}
            
            # Create the role
            role = self.rbac_service.create_role(
                body["name"],
                body["description"],
                body.get("parent_roles")
            )
            
            # Add permissions if provided
            permissions = body.get("permissions", [])
            for perm_data in permissions:
                # Create Permission object
                try:
                    resource_type = ResourceType[perm_data.get("resource_type", "GLOBAL")]
                    permission = Permission(
                        perm_data["name"],
                        perm_data.get("description", ""),
                        resource_type
                    )
                    self.rbac_service.add_permission_to_role(role.name, permission)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Invalid permission data: {e}")
            
            # Return the created role
            permissions = [{"name": p.name, "resource_type": p.resource_type.name} for p in role.permissions]
            
            return {
                "success": True,
                "role": {
                    "name": role.name,
                    "description": role.description,
                    "permissions": permissions,
                    "parent_roles": list(role.parent_roles)
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating role: {e}")
            return {"error": "Invalid request body"}
    
    @require_permission("admin", ResourceType.USER)
    def update_role(self, request: Any, role_name: str) -> Dict[str, Any]:
        """
        Update a role.
        
        Args:
            request: Request object with JSON body containing role data
            role_name: Role name
        
        Returns:
            Dict[str, Any]: Response with updated role
        """
        role = self.rbac_service.get_role(role_name)
        if not role:
            return {"error": "Role not found"}
        
        try:
            # Parse request body
            body = request.json()
            
            # Update fields
            if "description" in body:
                role.description = body["description"]
            
            # Update parent roles
            if "parent_roles" in body:
                # Clear existing parent roles
                role.parent_roles.clear()
                
                # Add new parent roles
                for parent_name in body["parent_roles"]:
                    role.add_parent_role(parent_name)
            
            # Update permissions
            if "permissions" in body:
                # Clear existing permissions
                role.permissions.clear()
                
                # Add new permissions
                for perm_data in body["permissions"]:
                    try:
                        resource_type = ResourceType[perm_data.get("resource_type", "GLOBAL")]
                        permission = Permission(
                            perm_data["name"],
                            perm_data.get("description", ""),
                            resource_type
                        )
                        role.add_permission(permission)
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Invalid permission data: {e}")
            
            # Return the updated role
            permissions = [{"name": p.name, "resource_type": p.resource_type.name} for p in role.permissions]
            
            return {
                "success": True,
                "role": {
                    "name": role.name,
                    "description": role.description,
                    "permissions": permissions,
                    "parent_roles": list(role.parent_roles)
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating role: {e}")
            return {"error": "Invalid request body"}
    
    @require_permission("admin", ResourceType.USER)
    def delete_role(self, request: Any, role_name: str) -> Dict[str, Any]:
        """
        Delete a role.
        
        Args:
            request: Request object
            role_name: Role name
        
        Returns:
            Dict[str, Any]: Success response
        """
        success = self.rbac_service.role_manager.delete_role(role_name)
        if not success:
            return {"error": "Role not found"}
            
        return {"success": True, "message": f"Role {role_name} deleted successfully"}
    
    # -------------------------------------------------------------------------
    # API key management endpoints
    # -------------------------------------------------------------------------
    
    @require_permission("admin", ResourceType.API_KEY)
    def list_api_keys(self, request: Any) -> Dict[str, Any]:
        """
        List API keys for a user.
        
        Args:
            request: Request object
        
        Returns:
            Dict[str, Any]: Response with list of API keys
        """
        # Get user ID from request or query parameter
        user_id = getattr(request, "auth_user_id", None) or request.query_params.get("user_id")
        if not user_id:
            return {"error": "Missing user_id parameter"}
        
        # Get API keys for the user
        api_keys = self.rbac_service.get_user_api_keys(user_id)
        
        # Convert to dict for response
        keys_data = []
        for key in api_keys:
            keys_data.append({
                "key_id": key.key_id,
                "description": key.description,
                "roles": key.roles,
                "created_at": key.created_at,
                "expires_at": key.expires_at,
                "last_used": key.last_used,
                "is_active": key.is_active
            })
        
        return {"success": True, "api_keys": keys_data}
    
    @require_permission("admin", ResourceType.API_KEY)
    def create_api_key(self, request: Any) -> Dict[str, Any]:
        """
        Create a new API key.
        
        Args:
            request: Request object with JSON body
        
        Returns:
            Dict[str, Any]: Response with created API key
        """
        try:
            # Parse request body
            body = request.json()
            
            # Validate required fields
            required_fields = ["user_id", "description"]
            for field in required_fields:
                if field not in body:
                    return {"error": f"Missing required field: {field}"}
            
            # Create the API key
            api_key, key_value = self.rbac_service.create_api_key(
                body["user_id"],
                body.get("roles", ["user"]),
                body["description"],
                body.get("expires_in_days")
            )
            
            # Return the created API key
            return {
                "success": True,
                "api_key": {
                    "key_id": api_key.key_id,
                    "key_value": key_value,  # Only returned on creation
                    "description": api_key.description,
                    "roles": api_key.roles,
                    "created_at": api_key.created_at,
                    "expires_at": api_key.expires_at,
                    "is_active": api_key.is_active
                },
                "message": "API key created successfully. Please save the key value as it won't be shown again."
            }
            
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return {"error": "Invalid request body"}
    
    @require_permission("admin", ResourceType.API_KEY)
    def revoke_api_key(self, request: Any, key_id: str) -> Dict[str, Any]:
        """
        Revoke an API key.
        
        Args:
            request: Request object
            key_id: API key ID
        
        Returns:
            Dict[str, Any]: Success response
        """
        success = self.rbac_service.revoke_api_key(key_id)
        if not success:
            return {"error": "API key not found"}
            
        return {"success": True, "message": f"API key {key_id} revoked successfully"}
    
    # -------------------------------------------------------------------------
    # Authorization endpoints
    # -------------------------------------------------------------------------
    
    def check_permission(self, request: Any) -> Dict[str, Any]:
        """
        Check if the current user has a specific permission.
        
        Args:
            request: Request object with query parameter 'permission'
        
        Returns:
            Dict[str, Any]: Response with authorization result
        """
        # Get the permission name from the request
        permission_name = request.query_params.get("permission")
        if not permission_name:
            return {"error": "Missing permission parameter"}
        
        # Determine resource type
        resource_type_name = request.query_params.get("resource_type", "GLOBAL")
        try:
            resource_type = ResourceType[resource_type_name]
        except KeyError:
            return {"error": f"Invalid resource type: {resource_type_name}"}
        
        # Authenticate the request
        auth_result = self.rbac_service.authenticate_request(request)
        
        # If authentication failed, return error
        if not auth_result:
            return {
                "success": False,
                "authorized": False,
                "reason": "Authentication failed"
            }
        
        # Check permission
        authorized = self.rbac_service.authorize(request, permission_name, resource_type)
        
        return {
            "success": True,
            "authorized": bool(authorized),
            "user_id": auth_result.user_id,
            "roles": auth_result.roles,
            "reason": authorized.reason if not authorized else None
        }
    
    def get_user_permissions(self, request: Any) -> Dict[str, Any]:
        """
        Get all permissions for the current user.
        
        Args:
            request: Request object
        
        Returns:
            Dict[str, Any]: Response with permissions
        """
        # Authenticate the request
        auth_result = self.rbac_service.authenticate_request(request)
        
        # If authentication failed, return error
        if not auth_result:
            return {
                "success": False,
                "reason": "Authentication failed"
            }
        
        # Get all permissions for the user
        permissions = self.rbac_service.role_manager.get_all_permissions_for_user(auth_result.roles)
        
        # Convert permissions to dict for response
        perm_data = []
        for perm in permissions:
            perm_data.append({
                "name": perm.name,
                "description": perm.description,
                "resource_type": perm.resource_type.name
            })
        
        return {
            "success": True,
            "user_id": auth_result.user_id,
            "roles": auth_result.roles,
            "permissions": perm_data
        }
    
    def get_user_accessible_backends(self, request: Any) -> Dict[str, Any]:
        """
        Get backends accessible to the current user.
        
        Args:
            request: Request object with query parameter 'action'
        
        Returns:
            Dict[str, Any]: Response with accessible backends
        """
        # Get the action from the request
        action_name = request.query_params.get("action", "READ")
        try:
            action = Action[action_name]
        except KeyError:
            return {"error": f"Invalid action: {action_name}"}
        
        # Authenticate the request
        auth_result = self.rbac_service.authenticate_request(request)
        
        # If authentication failed, return error
        if not auth_result:
            return {
                "success": False,
                "reason": "Authentication failed"
            }
        
        # Get accessible backends
        backends = self.rbac_service.get_accessible_backends(auth_result.roles, action)
        
        return {
            "success": True,
            "user_id": auth_result.user_id,
            "roles": auth_result.roles,
            "action": action.value,
            "accessible_backends": backends
        }


# Example of registering these handlers with a web framework
def register_auth_endpoints(app, rbac_service, oauth_manager=None):
    """
    Register auth endpoints with a web framework.
    
    This is just an example of how the handlers might be integrated.
    The actual implementation will depend on the web framework being used.
    
    Args:
        app: Web application instance
        rbac_service: RBAC service instance
        oauth_manager: Optional OAuth manager instance
    """
    handler = AuthHandler(rbac_service, oauth_manager)
    
    # Authentication endpoints
    app.route("/auth/login", "POST", handler.login)
    app.route("/auth/logout", "POST", handler.logout)
    app.route("/auth/oauth/login", "GET", handler.oauth_login)
    app.route("/auth/oauth/callback", "GET", handler.oauth_callback)
    
    # User management endpoints
    app.route("/auth/users", "GET", handler.list_users)
    app.route("/auth/users/{user_id}", "GET", handler.get_user)
    app.route("/auth/users", "POST", handler.create_user)
    app.route("/auth/users/{user_id}", "PUT", handler.update_user)
    app.route("/auth/users/{user_id}", "DELETE", handler.delete_user)
    
    # Role management endpoints
    app.route("/auth/roles", "GET", handler.list_roles)
    app.route("/auth/roles/{role_name}", "GET", handler.get_role)
    app.route("/auth/roles", "POST", handler.create_role)
    app.route("/auth/roles/{role_name}", "PUT", handler.update_role)
    app.route("/auth/roles/{role_name}", "DELETE", handler.delete_role)
    
    # API key management endpoints
    app.route("/auth/api-keys", "GET", handler.list_api_keys)
    app.route("/auth/api-keys", "POST", handler.create_api_key)
    app.route("/auth/api-keys/{key_id}/revoke", "POST", handler.revoke_api_key)
    
    # Authorization endpoints
    app.route("/auth/check-permission", "GET", handler.check_permission)
    app.route("/auth/user-permissions", "GET", handler.get_user_permissions)
    app.route("/auth/accessible-backends", "GET", handler.get_user_accessible_backends)
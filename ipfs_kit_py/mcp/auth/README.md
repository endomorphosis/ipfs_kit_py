# Advanced Authentication & Authorization System

## Overview

The MCP Advanced Authentication & Authorization system provides robust security features for the MCP server, including:

- **Flexible Authentication Methods**: Username/password, token-based, API keys, and OAuth
- **Role-Based Access Control (RBAC)**: Fine-grained permission management with hierarchical roles
- **Per-Backend Authorization**: Control access to specific storage backends
- **API Key Management**: Create and manage API keys with scoped permissions
- **OAuth Integration**: Support for third-party authentication providers
- **Comprehensive Audit Logging**: Track all authentication and authorization events

## Architecture

The system consists of several modular components:

1. **Core Authentication Service**: Handles user management and authentication logic
2. **RBAC System**: Manages roles, permissions, and access control policies
3. **API Key Manager**: Creates and validates API keys with various security features
4. **OAuth Manager**: Handles third-party authentication flows
5. **Backend Authorization Middleware**: Enforces access control for storage backends
6. **Audit Logger**: Records security events for monitoring and compliance

## Getting Started

### Basic Setup

To integrate the auth system with your MCP server:

```python
from fastapi import FastAPI
from ipfs_kit_py.mcp.auth.mcp_auth_integration import setup_mcp_auth

app = FastAPI()

# Initialize backend manager
backend_manager = BackendManager()
# ... configure backends ...

# Set up authentication system
@app.on_event("startup")
async def startup_event():
    auth_system = await setup_mcp_auth(
        app=app,
        backend_manager=backend_manager,
        config={
            "token_secret": "your-secret-key",
            "admin_username": "admin",
            "admin_password": "secure-password"
        }
    )
```

### Configuration Options

The auth system accepts the following configuration options:

| Option | Description | Default |
|--------|-------------|---------|
| `data_dir` | Directory to store auth data | `~/.ipfs_kit/auth` |
| `token_secret` | Secret key for JWT tokens | Environment var or random |
| `token_algorithm` | Algorithm for JWT tokens | `HS256` |
| `token_expire_minutes` | Token expiration time | `1440` (24 hours) |
| `admin_username` | Default admin username | `admin` |
| `admin_password` | Default admin password | Environment var or secure default |
| `oauth_providers` | OAuth provider configurations | `{}` |
| `custom_roles` | Custom role definitions | `[]` |

### OAuth Provider Configuration

To enable OAuth providers:

```python
config = {
    "oauth_providers": {
        "github": {
            "client_id": "your-github-client-id",
            "client_secret": "your-github-client-secret",
            "redirect_uri": "http://your-server/api/v0/auth/oauth/github/callback"
        },
        "google": {
            "client_id": "your-google-client-id",
            "client_secret": "your-google-client-secret",
            "redirect_uri": "http://your-server/api/v0/auth/oauth/google/callback"
        }
    }
}
```

### Custom Roles

Define custom roles with specific permissions:

```python
config = {
    "custom_roles": [
        {
            "id": "data_scientist",
            "name": "Data Scientist",
            "parent_role": "user",
            "permissions": ["read:ipfs", "write:ipfs", "read:huggingface", "write:huggingface"]
        },
        {
            "id": "content_manager",
            "name": "Content Manager",
            "parent_role": "user",
            "permissions": ["read:ipfs", "write:ipfs", "read:filecoin", "write:filecoin"]
        }
    ]
}
```

## Role-Based Access Control

### Standard Roles

The system includes several built-in roles:

- **Anonymous**: Unauthenticated users with minimal access
- **User**: Basic authenticated users with standard permissions
- **Developer**: Advanced users with broader access to backends
- **Admin**: System administrators with full access
- **System**: For automation and internal services

### Permissions

Permissions follow a `action:resource` pattern, for example:

- `read:ipfs`: Permission to read from the IPFS backend
- `write:filecoin`: Permission to write to the Filecoin backend
- `admin:users`: Permission to manage users

### Role Hierarchy

Roles inherit permissions from their parent roles:

```
User → Anonymous
Developer → User
Admin → Developer
```

This means an Admin has all permissions assigned to Developer, User, and Anonymous roles.

### Protecting API Endpoints

Secure your API endpoints with role-based access control:

```python
from fastapi import Depends
from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
from ipfs_kit_py.mcp.auth.models import User

@app.get("/api/v0/protected")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    """Endpoint requiring authentication."""
    return {"message": f"Hello, {current_user.username}!"}

@app.get("/api/v0/admin")
async def admin_endpoint(admin_user: User = Depends(get_admin_user)):
    """Endpoint requiring admin privileges."""
    return {"message": "Admin access granted"}
```

## API Key Management

### Creating API Keys

To create an API key programmatically:

```python
from ipfs_kit_py.mcp.auth.mcp_auth_integration import get_mcp_auth

# Get auth system
auth_system = get_mcp_auth()

# Create API key
api_key = await auth_system.api_key_manager.create_key(
    user_id="user-id",
    name="My API Key",
    permissions=["read:ipfs", "write:ipfs"],
    expires_at=time.time() + (30 * 24 * 60 * 60),  # 30 days
    rate_limit=100,  # requests per minute
    backends=["ipfs", "filecoin"],
    ip_whitelist=["192.168.1.0/24"]
)

# The key is only returned once
print(f"API Key: {api_key.key}")
```

### API Key Authentication

Users can authenticate using API keys with the `X-API-Key` header:

```
GET /api/v0/storage/get/ipfs/Qm...
X-API-Key: mcp_abc123...
```

## OAuth Integration

### Supported Providers

The system supports these OAuth providers:

- GitHub
- Google
- Microsoft
- GitLab

### OAuth Authentication Flow

1. User requests login URL: `GET /api/v0/auth/oauth/github/login`
2. Server returns login URL pointing to OAuth provider
3. User completes authentication on provider's site
4. Provider redirects back to callback URL
5. Server exchanges code for tokens
6. User receives MCP authentication tokens

## Backend Authorization

### Per-Backend Permissions

Control access to different storage backends with specific permissions:

- `read:ipfs`: Read from IPFS backend
- `write:ipfs`: Write to IPFS backend
- `read:filecoin`: Read from Filecoin backend
- `write:filecoin`: Write to Filecoin backend

### Backend-Specific Middleware

The system automatically checks permissions for backend operations:

```python
# This endpoint requires 'read:ipfs' permission
@app.get("/api/v0/ipfs/cat/{cid}")
async def ipfs_cat(cid: str, current_user: User = Depends(get_current_user)):
    ipfs_backend = backend_manager.get_backend("ipfs")
    result = await ipfs_backend.get_content(cid)
    return result
```

## Audit Logging

### Logging Security Events

Record security events for monitoring and compliance:

```python
from ipfs_kit_py.mcp.auth.mcp_auth_integration import (
    audit_login_attempt, audit_permission_check, audit_backend_access
)

# Log a login attempt
audit_login_attempt(
    user_id="user123",
    success=True,
    ip_address="192.168.1.1"
)

# Log a permission check
audit_permission_check(
    user_id="user123",
    permission="write:ipfs",
    granted=True,
    resource="Qm..."
)

# Log backend access
audit_backend_access(
    user_id="user123",
    backend="ipfs",
    operation="add",
    granted=True
)
```

## Verification Tool

The system includes a verification tool to check if all components are working correctly:

```bash
python -m ipfs_kit_py.mcp.auth.verify_auth_system --url http://localhost:5000 --output results.json
```

## API Reference

### Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/login` | POST | Authenticate with username and password |
| `/api/v0/auth/refresh` | POST | Refresh an access token |
| `/api/v0/auth/logout` | POST | Revoke the current token |

### User Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/users` | POST | Create a new user (admin only) |
| `/api/v0/auth/users` | GET | List all users (admin only) |
| `/api/v0/auth/users/me` | GET | Get current user information |
| `/api/v0/auth/users/{user_id}` | GET | Get user by ID |
| `/api/v0/auth/users/{user_id}` | PUT | Update user information |
| `/api/v0/auth/users/{user_id}` | DELETE | Delete user (admin only) |

### API Key Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/apikeys` | POST | Create a new API key |
| `/api/v0/auth/apikeys` | GET | List API keys |
| `/api/v0/auth/apikeys/{key_id}` | DELETE | Revoke an API key |

### RBAC Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/rbac/roles` | GET | List all roles |
| `/api/v0/rbac/roles/{role_id}/permissions` | GET | Get permissions for a role |
| `/api/v0/rbac/roles` | POST | Create a custom role (admin only) |
| `/api/v0/rbac/roles/{role_id}` | PUT | Update a custom role (admin only) |
| `/api/v0/rbac/roles/{role_id}` | DELETE | Delete a custom role (admin only) |
| `/api/v0/rbac/check-permission` | GET | Check if current user has a permission |
| `/api/v0/rbac/check-backend` | GET | Check if current user has access to a backend |

### OAuth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/oauth/providers` | GET | List available OAuth providers |
| `/api/v0/auth/oauth/{provider}/login` | GET | Get OAuth login URL |
| `/api/v0/auth/oauth/{provider}/callback` | GET | Handle OAuth callback |

### Audit Log Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/logs` | GET | Get audit logs (admin only) |

## Security Best Practices

1. **Use HTTPS**: Always use HTTPS in production to protect authentication tokens
2. **Strong Secret Keys**: Use strong, unique secret keys for token signing
3. **Regular Token Rotation**: Set reasonable expiration times for tokens
4. **Least Privilege**: Assign the minimum necessary permissions to each role
5. **Rate Limiting**: Implement rate limiting for authentication endpoints
6. **Monitor Audit Logs**: Regularly review audit logs for suspicious activity
7. **Strong Password Policy**: Enforce strong passwords for all users
8. **Avoid Hardcoded Credentials**: Don't hardcode API keys or passwords

## Troubleshooting

### Common Issues

1. **"Not authenticated" error**
   - Ensure your token is valid and included in the Authorization header
   - Check that the token hasn't expired

2. **"Permission denied" error**
   - Check that the user has the required permissions for the operation
   - Verify that the user's role includes the necessary permissions

3. **Token expiration**
   - Refresh the token using the refresh endpoint
   - Check that the token expiration time is appropriate for your use case

4. **API key not working**
   - Verify the API key is active and hasn't been revoked
   - Check that the API key has the necessary permissions
   - Verify the request is coming from an allowed IP address (if restricted)

5. **OAuth login failure**
   - Check the OAuth provider configuration and callback URLs
   - Verify that the client ID and secret are correct
   - Check for any CSRF protection issues

### Debugging

Enable debug logging to see more detailed information:

```python
import logging
logging.getLogger("ipfs_kit_py.mcp.auth").setLevel(logging.DEBUG)
```

## Contributing to the Auth System

To extend or modify the authentication system:

1. **New Permissions**: Add new permission types to the `Permission` enum in `auth/models.py`
2. **Custom Middleware**: Create specialized middleware for specific security requirements
3. **Additional OAuth Providers**: Add new providers to the `OAuthProvider` enum
4. **Enhanced Audit Logging**: Extend the audit logging to capture additional events

## Example: Complete Integration

```python
from fastapi import FastAPI, Depends
from ipfs_kit_py.mcp.auth.mcp_auth_integration import setup_mcp_auth
from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
from ipfs_kit_py.mcp.auth.models import User, Role

app = FastAPI()

# Initialize backend manager
backend_manager = BackendManager()
# ... configure backends ...

# Set up authentication system
@app.on_event("startup")
async def startup_event():
    # Initialize auth system
    auth_system = await setup_mcp_auth(
        app=app,
        backend_manager=backend_manager,
        config={
            "token_secret": "your-secret-key",
            "admin_username": "admin",
            "admin_password": "secure-password",
            "custom_roles": [
                {
                    "id": "data_scientist",
                    "name": "Data Scientist",
                    "parent_role": "user",
                    "permissions": ["read:ipfs", "write:ipfs", "read:huggingface"]
                }
            ]
        }
    )
    
    # Configure backend permissions
    await auth_system.configure_backend_permissions({
        "ipfs": ["read", "write", "pin", "admin"],
        "filecoin": ["read", "write", "verify"],
        "s3": ["read", "write", "delete"]
    })

# Protected endpoints examples
@app.get("/api/v0/user/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """Endpoint requiring authentication."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role
    }

@app.get("/api/v0/admin/users")
async def list_users(admin_user: User = Depends(get_admin_user)):
    """Endpoint requiring admin privileges."""
    # Get auth system
    auth_system = get_mcp_auth()
    
    # Get all users
    users = await auth_system.auth_service.list_users()
    
    return {
        "success": True,
        "users": [user.to_dict() for user in users]
    }
```
# Advanced Authentication & Authorization System

## Overview

The Advanced Authentication & Authorization system for the MCP server provides robust security features including:

- **Role-Based Access Control (RBAC)**: Fine-grained permission management with hierarchical roles
- **Per-Backend Authorization**: Control access to specific storage backends
- **API Key Management**: Secure API access with scoped permissions
- **OAuth Integration**: Support for third-party authentication providers
- **Comprehensive Audit Logging**: Track all authentication and authorization events
- **Custom Role Creation**: Define organization-specific roles with custom permissions

This system satisfies the requirements outlined in the MCP Server Development Roadmap (Q3 2025) under "Advanced Authentication & Authorization".

## Architecture

The Authentication & Authorization system consists of the following components:

1. **Core RBAC Engine** (`rbac.py`): Manages roles, permissions, and access control logic
2. **Auth Models** (`auth/models.py`): Defines the data structures for users, roles, permissions, etc.
3. **Auth Middleware** (`auth/middleware.py`): Processes authentication for incoming requests
4. **Backend Authorization Middleware** (`auth/backend_middleware.py`): Enforces permissions for storage backend operations
5. **Auth Service** (`auth/service.py`): Handles authentication operations (login, token validation, etc.)
6. **API Routers**:
   - `auth/router.py`: Endpoints for user management and authentication
   - `auth/rbac_router.py`: Endpoints for managing roles and permissions
7. **Integration Module** (`auth/integration.py`): Configures the auth system for the MCP server

## Role-Based Access Control

### Standard Roles

The system includes several built-in roles with predefined permissions:

- **Anonymous**: Unauthenticated users with minimal access
- **User**: Basic authenticated users with standard permissions
- **Developer**: Advanced users with broader access to backends
- **Admin**: System administrators with full access
- **System**: For automation and internal services

### Permissions

Permissions follow a `resource:action` pattern, for example:

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

### Custom Roles

Administrators can create custom roles through the API, specifying:

- Role name and ID
- List of permissions
- Parent role (optional)

Example:

```json
{
  "id": "data_scientist",
  "name": "Data Scientist",
  "parent_role": "user",
  "permissions": ["read:ipfs", "write:ipfs", "read:huggingface", "write:huggingface"]
}
```

## Per-Backend Authorization

The backend authorization middleware automatically enforces access control for storage backend operations:

- Read operations require the corresponding `read:<backend>` permission
- Write operations require the corresponding `write:<backend>` permission

For example, to upload files to IPFS, a user needs the `write:ipfs` permission.

## API Reference

### Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/login` | POST | Authenticate with username and password |
| `/api/v0/auth/login/token` | POST | OAuth2 password flow endpoint |
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
| `/api/v0/rbac/users/{user_id}/permissions` | GET | Get user-specific permissions |
| `/api/v0/rbac/users/{user_id}/permissions` | POST | Set user-specific permissions (admin only) |
| `/api/v0/rbac/users/{user_id}/permissions` | DELETE | Clear user-specific permissions (admin only) |
| `/api/v0/rbac/check-permission` | GET | Check if current user has a permission |
| `/api/v0/rbac/check-backend` | GET | Check if current user has access to a backend |
| `/api/v0/rbac/permissions` | GET | List all available permissions |
| `/api/v0/rbac/role-hierarchy` | GET | Get role hierarchy (admin only) |
| `/api/v0/rbac/role-hierarchy` | PUT | Update role hierarchy (admin only) |

### OAuth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/oauth/{provider}/login` | GET | Get OAuth login URL |
| `/api/v0/auth/oauth/{provider}/callback` | GET | Handle OAuth callback |

### Audit Log Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/auth/logs` | GET | Get audit logs (admin only) |

## Usage Examples

### Authenticating a User

```python
import requests

response = requests.post(
    "http://localhost:5000/api/v0/auth/login",
    json={"username": "user1", "password": "password123"}
)

token_data = response.json()
access_token = token_data["access_token"]

# Use the access token for subsequent requests
headers = {"Authorization": f"Bearer {access_token}"}
```

### Creating a Custom Role

```python
import requests

# Admin authentication
headers = {"Authorization": f"Bearer {admin_token}"}

# Create a custom role
role_data = {
    "id": "project_manager",
    "name": "Project Manager",
    "parent_role": "user",
    "permissions": ["read:admin", "write:filecoin", "write:ipfs"]
}

response = requests.post(
    "http://localhost:5000/api/v0/rbac/roles",
    json=role_data,
    headers=headers
)
```

### Assigning User-Specific Permissions

```python
import requests

# Admin authentication
headers = {"Authorization": f"Bearer {admin_token}"}

# Assign custom permissions to a user
permissions_data = {
    "permissions": ["read:admin", "write:filecoin"]
}

response = requests.post(
    f"http://localhost:5000/api/v0/rbac/users/{user_id}/permissions",
    json=permissions_data,
    headers=headers
)
```

### Creating an API Key

```python
import requests

# User authentication
headers = {"Authorization": f"Bearer {user_token}"}

# Create an API key
api_key_data = {
    "name": "My Application",
    "user_id": "my_user_id",
    "permissions": ["read:ipfs", "write:ipfs"]
}

response = requests.post(
    "http://localhost:5000/api/v0/auth/apikeys",
    json=api_key_data,
    headers=headers
)

api_key = response.json()["key"]

# Use the API key for API access
headers = {"X-API-Key": api_key}
```

## Integration with MCP Server

The Authentication & Authorization system is integrated with the MCP server in `direct_mcp_server.py`. The implementation:

1. Initializes the auth system during server startup
2. Enforces authentication and authorization for API endpoints
3. Provides routes for managing users, roles, and permissions
4. Configures the backend authorization middleware to protect storage operations

## Security Recommendations

1. **Use HTTPS**: Always use HTTPS in production to protect authentication tokens
2. **Regular Token Rotation**: Set reasonable expiration times for tokens
3. **Least Privilege**: Assign the minimum necessary permissions to each role
4. **Rate Limiting**: Implement rate limiting for authentication endpoints
5. **Monitor Audit Logs**: Regularly review audit logs for suspicious activity
6. **Strong Password Policy**: Enforce strong passwords for all users
7. **Avoid Hardcoded Credentials**: Don't hardcode API keys or passwords

## Development and Extending

The Authentication & Authorization system is designed to be extensible. To add new features:

1. **New Permissions**: Add new permission types to the `Permission` enum in `auth/models.py`
2. **Custom Middleware**: Create specialized middleware for specific security requirements
3. **Additional OAuth Providers**: Add new providers to the `OAuthProvider` enum
4. **Enhanced Audit Logging**: Extend the audit logging to capture additional events

## Troubleshooting

Common issues and solutions:

1. **"Not authenticated" error**: Ensure your token is valid and included in the Authorization header
2. **"Permission denied" error**: Check that the user has the required permissions for the operation
3. **Token expiration**: Refresh the token using the refresh endpoint
4. **API key not working**: Verify the API key is active and has the necessary permissions
5. **OAuth login failure**: Check the OAuth provider configuration and callback URLs
# Advanced Authentication & Authorization System

## Overview

The Advanced Authentication & Authorization system provides comprehensive security features for the MCP server:

- **Role-Based Access Control (RBAC)**: Fine-grained permissions with hierarchical roles
- **Per-Backend Authorization**: Secure access to specific storage backends
- **API Key Management**: Securely manage API access with scoped permissions
- **OAuth Integration**: Support for third-party authentication providers
- **Comprehensive Audit Logging**: Track all authentication and authorization events
- **Security Dashboard**: Admin interface for security management

This documentation covers the configuration, API endpoints, and best practices for the auth system.

## Authentication Methods

The system supports multiple authentication methods:

1. **Username/Password**: Traditional login with JWT tokens
2. **API Keys**: For programmatic access to the API
3. **OAuth Providers**: Authentication via third-party providers (GitHub, Google, etc.)

## Role-Based Access Control

### Standard Roles

The following standard roles are available by default:

- **Anonymous**: Minimal access for unauthenticated users
- **User**: Standard authenticated user permissions
- **Developer**: Enhanced access for developers (includes User permissions)
- **Admin**: Full system access (includes Developer permissions)
- **System**: Internal role for service-to-service communication

### Custom Roles

Administrators can create custom roles with specific permissions:

```json
{
  "id": "data_scientist",
  "name": "Data Scientist",
  "permissions": [
    "read:ipfs", "write:ipfs",
    "read:huggingface", "write:huggingface",
    "read:search", "write:search"
  ],
  "parent_role": "user"
}
```

### Permissions

Permissions follow a `resource:action` pattern:

- `read:ipfs`: Permission to read from IPFS backend
- `write:filecoin`: Permission to write to Filecoin backend
- `admin:users`: Permission to manage users

## API Key Management

API keys can be created with specific permissions and expiration dates. They are useful for:

- Integration with other services
- Client applications
- Automated scripts

### Creating an API Key

```bash
curl -X POST "http://localhost:5000/api/v0/auth/apikeys" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Application",
    "permissions": ["read:ipfs", "write:ipfs"],
    "expires_in_days": 30
  }'
```

### Using an API Key

```bash
curl "http://localhost:5000/api/v0/ipfs/cat/QmExample" \
  -H "X-API-Key: YOUR_API_KEY"
```

## OAuth Integration

The system supports OAuth authentication with multiple providers (GitHub, Google, etc.). This enables:

- Single Sign-On (SSO)
- Simplified user management
- Enhanced security

### OAuth Login Flow

1. User is redirected to `/api/v0/auth/oauth/{provider}/login`
2. User authenticates with the provider
3. Provider redirects back to MCP with authorization code
4. MCP validates the code and creates/updates the user
5. User is logged in and receives JWT tokens

## Per-Backend Authorization

Storage backend operations are protected by backend-specific permissions:

- Operations using the IPFS backend require `read:ipfs` or `write:ipfs` permissions
- Operations using the Filecoin backend require `read:filecoin` or `write:filecoin` permissions

This provides fine-grained control over which users can access different storage systems.

## Security Dashboard

The security dashboard provides a comprehensive interface for administrators to:

- Monitor system security
- Manage users and roles
- Track API key usage
- Review audit logs

### Accessing the Dashboard

The dashboard is accessible via API endpoints under `/api/v0/security/*` and requires admin permissions.

Key endpoints:

- `/api/v0/security/dashboard`: Overall security metrics
- `/api/v0/security/users`: User management
- `/api/v0/security/roles`: Role management
- `/api/v0/security/api-keys`: API key management
- `/api/v0/security/audit-logs`: Audit log review

## Configuration

The auth system can be configured through:

1. **Environment Variables**:
   - `MCP_AUTH_CONFIG_PATH`: Path to auth configuration directory
   - `OAUTH_CONFIG_PATH`: Path to OAuth provider configuration

2. **Configuration Files**:
   - `rbac.json`: Role definitions and permissions
   - `oauth_providers.json`: OAuth provider configurations

## Best Practices

1. **Follow Least Privilege**: Assign the minimum necessary permissions
2. **Regularly Rotate API Keys**: Set reasonable expiration dates
3. **Monitor Audit Logs**: Review for suspicious activity
4. **Use HTTPS**: Protect tokens and sensitive information
5. **Implement Rate Limiting**: Prevent brute force attempts

## Example Workflows

### Creating a Custom Role and Assigning to a User

```python
import requests

# Admin login
response = requests.post(
    "http://localhost:5000/api/v0/auth/login",
    json={"username": "admin", "password": "admin_password"}
)
admin_token = response.json()["access_token"]

# Create custom role
role_data = {
    "id": "data_analyst",
    "name": "Data Analyst",
    "permissions": ["read:ipfs", "read:search", "read:huggingface"],
    "parent_role": "user"
}

response = requests.post(
    "http://localhost:5000/api/v0/rbac/roles",
    headers={"Authorization": f"Bearer {admin_token}"},
    json=role_data
)

# Assign role to user
response = requests.post(
    "http://localhost:5000/api/v0/rbac/users/user123/roles",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"roles": ["data_analyst"]}
)
```

### Creating and Using an API Key

```python
import requests

# User login
response = requests.post(
    "http://localhost:5000/api/v0/auth/login",
    json={"username": "user1", "password": "password123"}
)
user_token = response.json()["access_token"]

# Create API key
response = requests.post(
    "http://localhost:5000/api/v0/auth/apikeys",
    headers={"Authorization": f"Bearer {user_token}"},
    json={
        "name": "My Script",
        "permissions": ["read:ipfs", "write:ipfs"],
        "expires_in_days": 30
    }
)

api_key = response.json()["key"]

# Use API key to access IPFS
response = requests.get(
    "http://localhost:5000/api/v0/ipfs/cat/QmExample",
    headers={"X-API-Key": api_key}
)
```

## Troubleshooting

### Common Errors

1. **401 Unauthorized**: Authentication token is missing or invalid
   - Check that you're providing a valid token or API key

2. **403 Forbidden**: User doesn't have required permissions
   - Verify that the user has the necessary role and permissions

3. **404 Not Found**: Resource doesn't exist or user doesn't have access
   - Check that the resource exists and the user has permission to access it

### Token Issues

If you're experiencing issues with authentication tokens:

1. Check that the token hasn't expired
2. Ensure you're using the correct token format (`Bearer TOKEN`)
3. Try refreshing the token using the refresh endpoint

### API Key Issues

If API keys aren't working:

1. Verify the key hasn't expired
2. Check that the key has the required permissions
3. Ensure you're using the `X-API-Key` header correctly

## API Reference

For a complete list of authentication and authorization endpoints, see:

- `/api/v0/auth/*`: Core authentication endpoints
- `/api/v0/rbac/*`: Role management endpoints
- `/api/v0/security/*`: Security dashboard endpoints
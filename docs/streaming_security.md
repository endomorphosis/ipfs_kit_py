# Streaming Security in ipfs-kit-py

`ipfs-kit-py` provides robust features for securing streaming data, especially when using WebSockets or WebRTC for real-time communication and content delivery. The primary component is the `StreamingSecurityManager`.

## Core Features

*   **Token-Based Authentication**: Generates and verifies JWT (JSON Web Tokens) to authenticate clients connecting via WebSockets or for WebRTC signaling. Tokens can include user roles and specific permissions.
*   **Content Access Policies**: Define fine-grained access control rules for specific CIDs. Policies can restrict access based on user IDs, roles, or required permissions.
*   **Rate Limiting**: Protects against abuse by limiting the number of requests or actions a client can perform within a specific time window.
*   **Content Encryption**: Supports encrypting content before storage or transmission and decrypting it upon retrieval, using symmetric keys (e.g., AES-GCM). Keys can be managed per-content or per-user.
*   **HMAC Signatures**: Ensures message integrity and authenticity using Hash-based Message Authentication Codes.
*   **Secure Origin Checking**: Helps prevent cross-site request forgery (CSRF) by validating the `Origin` header for WebSocket connections.
*   **WebRTC Security**: Integrates security measures into the WebRTC signaling and data transfer process, including securing offers and potentially encrypting frame data.

## Configuration

Security features are configured within the `ipfs-kit-py` main configuration, typically under a `streaming_security` key.

```python
# Example configuration snippet
config = {
    'streaming_security': {
        'enabled': True,
        'secret_key': 'YOUR_VERY_SECRET_KEY_HERE', # CHANGE THIS! Load from env var ideally.
        'token_expiry_seconds': 3600, # 1 hour
        'rate_limits': {
            'default': {'limit': 100, 'period': 60}, # 100 requests per minute
            'signaling': {'limit': 20, 'period': 60}, # Stricter limit for signaling
        },
        'allowed_origins': [ # Optional: Restrict WebSocket origins
            'http://localhost:3000',
            'https://your-frontend-app.com'
        ],
        'encryption': {
            'enabled': True,
            'default_key_bits': 256
        }
        # ... other potential configurations
    },
    # Required for WebSocket/WebRTC endpoints
    'api': {
        'enabled': True,
        'host': '0.0.0.0',
        'port': 8080,
        # ... other API settings
    }
    # ... other ipfs-kit-py config
}

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
kit = IPFSSimpleAPI(config=config)

# The StreamingSecurityManager is often used internally by API endpoints
# but can potentially be accessed for custom security logic if needed.
# security_manager = kit.get_streaming_security_manager() # Hypothetical access method
```

**Important Security Note:** Never hardcode secret keys directly in your configuration files. Use environment variables or a secure secrets management system.

## Usage Scenarios

1.  **Securing WebSocket Endpoints**: The `StreamingSecurityManager` can be integrated as middleware (e.g., with FastAPI) to automatically authenticate incoming WebSocket connections using tokens passed in headers or query parameters.
2.  **Securing WebRTC Signaling**: Protects the signaling phase where peers exchange connection information, ensuring only authorized users can initiate connections.
3.  **Enforcing Content Access**: When streaming content via `stream_media` or WebSocket/WebRTC endpoints, the manager checks if the authenticated user has the necessary permissions based on defined content policies.
4.  **Encrypting Sensitive Streams**: Content can be encrypted on the fly during upload streams or before being stored if required.

*(Detailed examples of setting content policies, generating tokens for clients, and integrating with API frameworks will be added here or in the example file.)*

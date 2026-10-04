# Architecture: Module Organization and Integration

## Overview

The ipfs_kit_py project follows a layered architecture where core functionality is implemented in the `ipfs_kit_py` package, which is then exposed through multiple interfaces (CLI, MCP Server, JavaScript SDK, Dashboard).

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Dashboard                      │
│                     (Web Interface)                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│               MCP Server JavaScript SDK                      │
│                  (Client Library)                            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    MCP Server Tools                          │
│           (mcp/secrets_mcp_tools.py - shims)                │
│                                                              │
│    ┌─────────────────────────────────────────────────┐     │
│    │  ipfs_kit_py.mcp.servers.secrets_mcp_tools      │     │
│    │       (MCP Server Integration Layer)             │     │
│    └───────────────────┬─────────────────────────────┘     │
└────────────────────────┼─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                  ipfs_kit_py Package                          │
│                  (Core Functionality)                         │
│                                                               │
│    • aes_encryption.py                                        │
│    • enhanced_secrets_manager.py                              │
│    • connection_pool.py                                       │
│    • circuit_breaker.py                                       │
│    • retry_strategy.py                                        │
│    • ... (all core modules)                                   │
└───────────────────────────────────────────────────────────────┘
```

## Component Details

### Layer 1: Core Package (`ipfs_kit_py/`)

**Purpose:** Contains all core business logic and functionality

**Characteristics:**
- Pure Python modules
- No external interface dependencies
- Fully testable in isolation
- Can be imported directly by any Python code

**Examples:**
```python
# Core encryption module
ipfs_kit_py/aes_encryption.py
  - AESEncryption class
  - MultiVersionEncryption class
  - Encryption/decryption logic

# Core secrets management
ipfs_kit_py/enhanced_secrets_manager.py
  - EnhancedSecretManager class
  - Secret storage and retrieval
  - Rotation and lifecycle management

# Core resilience patterns
ipfs_kit_py/connection_pool.py
ipfs_kit_py/circuit_breaker.py
ipfs_kit_py/retry_strategy.py
```

### Layer 2: MCP Server Integration (`ipfs_kit_py/mcp/servers/`)

**Purpose:** Wraps core functionality for MCP server consumption

**Characteristics:**
- Imports from `ipfs_kit_py` package
- Provides MCP Tool definitions
- Handles MCP-specific request/response formats
- Async handlers for MCP operations

**Pattern:**
```python
# ipfs_kit_py/mcp/servers/secrets_mcp_tools.py

from ipfs_kit_py.enhanced_secrets_manager import EnhancedSecretManager
from ipfs_kit_py.aes_encryption import MultiVersionEncryption

def create_secrets_tools() -> List[Tool]:
    """Create MCP tool definitions"""
    return [Tool(...), Tool(...)]

async def handle_secrets_store(arguments: Dict[str, Any]):
    """Handle MCP tool invocation"""
    manager = get_secrets_manager()  # Uses core package
    result = manager.store_secret(...)
    return format_mcp_response(result)
```

### Layer 3: MCP Compatibility Shims (`mcp/`)

**Purpose:** Provides backward compatibility and test patching support

**Characteristics:**
- Re-exports from `ipfs_kit_py.mcp.servers`
- Allows tests to patch functions
- Maintains backward compatibility

**Pattern:**
```python
# mcp/secrets_mcp_tools.py

from ipfs_kit_py.mcp.servers import secrets_mcp_tools as _impl

# Re-export for compatibility
create_secrets_tools = _impl.create_secrets_tools
handle_secrets_store = _impl.handle_secrets_store
SECRETS_HANDLERS = _impl.SECRETS_HANDLERS
```

### Layer 4: MCP Server (JavaScript SDK)

**Purpose:** Exposes MCP tools to JavaScript/TypeScript clients

**Characteristics:**
- Communicates via MCP protocol
- Calls handlers from Layer 2/3
- Returns JSON responses

**Example Flow:**
```javascript
// JavaScript SDK
const result = await mcpClient.callTool('secrets_store', {
  service: 'my_service',
  secret_value: 'secret_key_123',
  secret_type: 'api_key'
});
```

### Layer 5: Dashboard (Web UI)

**Purpose:** User interface for managing secrets and other features

**Characteristics:**
- Uses JavaScript SDK (Layer 4)
- Provides visual interface
- No direct access to core modules

## Example: Secrets Management Flow

### 1. User Action in Dashboard
```javascript
// User clicks "Store Secret" in dashboard
dashboard.storeSecret({
  service: 'github',
  value: 'ghp_xxxxx',
  type: 'api_key'
});
```

### 2. JavaScript SDK Call
```javascript
// SDK calls MCP server tool
await mcpClient.callTool('secrets_store', {
  service: 'github',
  secret_value: 'ghp_xxxxx',
  secret_type: 'api_key'
});
```

### 3. MCP Handler Processing
```python
# mcp/secrets_mcp_tools.py (shim)
# → ipfs_kit_py/mcp/servers/secrets_mcp_tools.py

async def handle_secrets_store(arguments):
    manager = get_secrets_manager()  # Gets core module
    secret_id = manager.store_secret(...)  # Calls core functionality
    return format_response(secret_id)
```

### 4. Core Module Execution
```python
# ipfs_kit_py/enhanced_secrets_manager.py

class EnhancedSecretManager:
    def store_secret(self, service, secret_value, secret_type):
        # Uses AES encryption from core module
        encrypted = self._encrypt(secret_value)
        
        # ipfs_kit_py/aes_encryption.py
        # AESEncryption.encrypt() with PBKDF2, salt, nonce
        
        # Store encrypted value
        self.secrets[secret_id] = encrypted
        return secret_id
```

## Integration with CLI Tools

CLI tools can directly import core modules:

```python
# CLI tool (e.g., ipfs-kit secrets store)

from ipfs_kit_py.enhanced_secrets_manager import EnhancedSecretManager

manager = EnhancedSecretManager()
secret_id = manager.store_secret(
    service=args.service,
    secret_value=args.value,
    secret_type=args.type
)
```

## Testing Strategy

### Unit Tests (Core Modules)
```python
# tests/unit/test_aes_encryption.py

from ipfs_kit_py.aes_encryption import AESEncryption

def test_encrypt_decrypt():
    aes = AESEncryption(master_key)
    encrypted = aes.encrypt("secret")
    decrypted = aes.decrypt(encrypted)
    assert decrypted == "secret"
```

### Integration Tests (MCP Layer)
```python
# tests/integration/test_secrets_mcp.py

from ipfs_kit_py.mcp.servers.secrets_mcp_tools import handle_secrets_store

async def test_mcp_store_secret():
    result = await handle_secrets_store({
        'service': 'test',
        'secret_value': 'test_secret'
    })
    assert result['success'] == True
```

### End-to-End Tests (Full Stack)
```javascript
// tests/e2e/test_dashboard.js

test('store secret from dashboard', async () => {
  await dashboard.storeSecret({...});
  const secrets = await dashboard.listSecrets();
  expect(secrets).toContain(...);
});
```

## Benefits of This Architecture

### 1. Separation of Concerns
- Core logic independent of interface
- MCP layer only handles protocol
- Dashboard only handles UI

### 2. Testability
- Each layer can be tested independently
- Mock interfaces easily
- Fast unit tests for core logic

### 3. Reusability
- Core modules usable from any Python code
- Same functionality exposed via multiple interfaces
- Easy to add new interfaces (GraphQL, REST, etc.)

### 4. Maintainability
- Changes to core logic don't affect interfaces
- Interface changes don't affect core logic
- Clear boundaries between components

### 5. Performance
- No unnecessary layers in CLI tools
- MCP server can optimize for protocol
- Core modules optimized for functionality

## Adding New Functionality

To add a new feature, follow this pattern:

### Step 1: Implement Core Module
```python
# ipfs_kit_py/my_new_feature.py

class MyNewFeature:
    def do_something(self, arg):
        # Core business logic here
        return result
```

### Step 2: Add MCP Server Integration
```python
# ipfs_kit_py/mcp/servers/my_feature_mcp_tools.py

from ipfs_kit_py.my_new_feature import MyNewFeature

def create_my_feature_tools() -> List[Tool]:
    return [Tool(name="my_feature_do_something", ...)]

async def handle_my_feature(arguments):
    feature = MyNewFeature()
    result = feature.do_something(arguments['arg'])
    return format_response(result)
```

### Step 3: Add Compatibility Shim
```python
# mcp/my_feature_mcp_tools.py

from ipfs_kit_py.mcp.servers.my_feature_mcp_tools import *
```

### Step 4: Register with MCP Server
```python
# Enhanced MCP server registration
from mcp.my_feature_mcp_tools import (
    create_my_feature_tools,
    handle_my_feature
)

# Add to tools list and handlers
```

### Step 5: Use in Dashboard
```javascript
// Dashboard can now call the tool
await mcpClient.callTool('my_feature_do_something', {
  arg: 'value'
});
```

## Current Implementation Status

### ✅ Implemented with Proper Architecture

- **AES Encryption** (`ipfs_kit_py/aes_encryption.py`)
  - Core: ✅
  - MCP: ✅ (`ipfs_kit_py/mcp/servers/secrets_mcp_tools.py`)
  - Shim: ✅ (`mcp/secrets_mcp_tools.py`)

- **Enhanced Secrets Manager** (`ipfs_kit_py/enhanced_secrets_manager.py`)
  - Core: ✅
  - MCP: ✅ (integrated in secrets_mcp_tools)
  - Shim: ✅

- **Connection Pool** (`ipfs_kit_py/connection_pool.py`)
  - Core: ✅
  - MCP: Can be added when needed
  
- **Circuit Breaker** (`ipfs_kit_py/circuit_breaker.py`)
  - Core: ✅
  - MCP: Can be added when needed

- **Retry Strategy** (`ipfs_kit_py/retry_strategy.py`)
  - Core: ✅
  - MCP: Can be added when needed

### Previously Implemented

- **Bucket VFS** (`ipfs_kit_py/bucket_vfs_manager.py`)
  - Core: ✅
  - MCP: ✅ (`ipfs_kit_py/mcp/servers/bucket_vfs_mcp_tools.py`)
  - Shim: ✅ (`mcp/bucket_vfs_mcp_tools.py`)

## Summary

The architecture ensures:
1. **Core functionality** lives in `ipfs_kit_py/` package
2. **MCP integration** lives in `ipfs_kit_py/mcp/servers/`
3. **Compatibility shims** live in `mcp/`
4. **JavaScript SDK** consumes MCP server tools
5. **Dashboard** consumes JavaScript SDK

This layered approach provides flexibility, testability, and maintainability while keeping concerns properly separated.

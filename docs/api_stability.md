# API Stability Guidelines

This document outlines the API stability guidelines for the IPFS Kit Python project, providing clarity on versioning, compatibility promises, and deprecation procedures.

## API Versioning

IPFS Kit follows semantic versioning (SemVer) with additional clarity for API interfaces:

- **MAJOR version** (X.y.z): Introduces breaking changes to stable APIs
- **MINOR version** (x.Y.z): Adds new features in a backward-compatible manner
- **PATCH version** (x.y.Z): Contains backward-compatible bug fixes

## API Stability Levels

IPFS Kit defines three levels of stability for APIs:

### 1. Stable APIs

Stable APIs are production-ready and follow strict compatibility guarantees:

- Interface will not change within the same major version
- Method signatures will remain backward compatible
- Return types will maintain backward compatibility
- New optional parameters may be added, but required parameters won't change
- Documented behavior will remain consistent

Stable APIs are clearly marked in documentation and method docstrings with:

```python
@stable_api(since="0.1.0")
def stable_method():
    """This is a stable API method."""
    pass
```

### 2. Beta APIs

Beta APIs are nearly stabilized but may still undergo refinement:

- Interface might change in minor version updates
- Method signatures might be adjusted for consistency
- Return types might be enhanced but maintain backward compatibility
- Parameters might be renamed or reordered
- Behavior may be refined for consistency

Beta APIs are marked in documentation and method docstrings with:

```python
@beta_api(since="0.1.0")
def beta_method():
    """This is a beta API method that may change in minor versions."""
    pass
```

### 3. Experimental APIs

Experimental APIs are under active development and may change significantly:

- Interface may change in any version update
- Method signatures might change completely
- Return types may change 
- Parameters may be added, removed, or changed
- Behavior may change based on feedback and development

Experimental APIs are marked in documentation and method docstrings with:

```python
@experimental_api(since="0.1.0")
def experimental_method():
    """This is an experimental API method with no stability guarantees."""
    pass
```

## Compatibility Promises

### High-Level API (`IPFSSimpleAPI`)

The High-Level API (`IPFSSimpleAPI`) offers the strongest stability guarantees:

- All public methods marked as @stable_api will maintain compatibility for the same major version
- Method signatures will remain backward compatible within the same major version
- New methods may be added in minor versions
- Deprecated methods will be marked and maintained for at least one major version cycle
- Configuration options may be enhanced but backward compatibility will be maintained

### REST API Server

The REST API follows a clear versioning scheme with endpoint paths:

- `/api/v0/...` - First stable API version
- `/api/v1/...` - Future stable API version (when implemented)
- `/api/beta/...` - Beta API endpoints under consideration for stabilization
- `/api/experimental/...` - Experimental endpoints with no stability guarantees

API versioning for the REST API follows these rules:

- Stable API versions (`v0`, `v1`, etc.) will maintain compatibility for their lifetime
- New stable API versions may deprecate or change functionality from previous versions
- Multiple stable API versions will be maintained concurrently during transition periods
- Beta and experimental endpoints may change without notice

### Core API (`ipfs_kit`)

The core `ipfs_kit` module has more selective stability guarantees:

- Public interfaces with @stable_api annotations maintain compatibility
- Internal implementation details may change at any time
- Return value structures will maintain compatibility
- Operation keys will remain consistent within major versions

## Deprecation Process

1. **Announcement**: Deprecated features are announced in release notes and documentation
2. **Marking**: Code is marked with `@deprecated` decorator
3. **Warning Period**: Deprecation warnings are issued for at least one minor version cycle
4. **Removal**: Feature is removed in next major version

Code with deprecated methods will include both the replacement method and a warning:

```python
@deprecated(since="0.2.0", removed_in="1.0.0", alternative="new_method")
def old_method():
    """This method is deprecated. Use new_method() instead."""
    warnings.warn(
        "old_method is deprecated since 0.2.0 and will be removed in 1.0.0. Use new_method instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return new_method()
```

## Current API Status

### Stable APIs (v0.1.0+)

The following interfaces are considered stable as of v0.1.0:

- **High-Level API**: Core methods of `IPFSSimpleAPI` class
  - Content operations: 
    - `add()` - Add content to IPFS
    - `get()` - Retrieve content from IPFS
    - `add_json()` - Add JSON data to IPFS
  - Content management: 
    - `pin()` - Pin content to local node
    - `unpin()` - Unpin content from local node
    - `list_pins()` - List pinned content

- **REST API**: Basic endpoints
  - `/api/v0/add` - Add content to IPFS
  - `/api/v0/cat` - Retrieve content by CID
  - `/api/v0/ls` - List directory contents
  - `/api/v0/pin/*` - Pin management endpoints
  - `/api/v0/id` - Node identity information

### Beta APIs (v0.1.0+)

The following interfaces are in beta status as of v0.1.0:

- **High-Level API**: Advanced features
  - IPNS publishing: 
    - `publish()` - Publish content to IPNS
  - Cluster operations: 
    - `cluster_status()` - Get cluster pin status
  - Filesystem integration:
    - `get_filesystem()` - Get FSSpec interface for IPFS content
  - Advanced file handling:
    - `stream_media()` - Stream media content with chunked access
    - `open_file()` - Open file-like interface to IPFS content

- **REST API**: Advanced endpoints
  - `/api/v0/name/*` - IPNS endpoints
  - `/api/v0/swarm/*` - Peer management endpoints
  - `/api/v0/cluster/*` - Cluster management endpoints

### Experimental APIs (v0.1.0+)

The following interfaces are experimental as of v0.1.0:

- **High-Level API**: New features
  - AI/ML integration methods
    - `ai_model_add()` - Add ML model to the registry
    - `ai_model_get()` - Get ML model from the registry
  - WebRTC streaming methods
  - Advanced search capabilities
  - Performance analysis tools

- **REST API**: New endpoints
  - `/api/v0/ai/*` - AI/ML integration endpoints
  - `/api/v0/search/*` - Advanced search endpoints
  - `/api/v0/webrtc/*` - WebRTC streaming endpoints

## Upcoming Changes

For the next stable release (v0.2.0), we plan to:

1. Stabilize additional cluster management methods (currently `cluster_status()` is beta)
2. Move FSSpec integration (`get_filesystem()`) from beta to stable
3. Move IPNS operations (`publish()`) from beta to stable
4. Move `stream_media()` and `open_file()` from beta to stable
5. Move AI/ML methods (`ai_model_add()`, `ai_model_get()`) from experimental to beta
6. Add stability decorators to additional methods in the codebase
7. Implement automated API compatibility checking in CI/CD pipeline

## Implementation Details

The API stability system is implemented through Python decorators that annotate methods with their stability level:

- The decorators are defined in `ipfs_kit_py/api_stability.py`
- Each decorated method is registered in a central registry for tracking
- Runtime checks can verify the stability level of a method
- Automated reports can be generated to list all APIs by stability level

Example from our implementation:

```python
from ipfs_kit_py.api_stability import stable_api, beta_api, experimental_api

class IPFSSimpleAPI:
    @stable_api(since="0.1.0")
    def add(self, content, **kwargs):
        """Add content to IPFS."""
        # Implementation...
    
    @beta_api(since="0.1.0")
    def get_filesystem(self, **kwargs):
        """Get FSSpec interface for IPFS."""
        # Implementation...
    
    @experimental_api(since="0.1.0") 
    def ai_model_add(self, model, **kwargs):
        """Add ML model to registry."""
        # Implementation...
```

The stability registry tracks all decorated methods and enables:
- Automatic API documentation generation
- Compatibility checking between versions
- Runtime introspection of stability levels

## Guidelines for API Development

When developing new APIs or modifying existing ones:

1. Always annotate with the appropriate stability marker
2. Document all parameters, return values, and exceptions
3. Follow consistent patterns with existing APIs
4. Provide sensible defaults for optional parameters
5. Return consistent result structures
6. Add deprecation markers before removing functionality
7. Use type hints to clarify interface expectations
8. Write comprehensive tests for all API behaviors

## Checking API Compatibility

Use the provided tooling to verify API compatibility:

```bash
# Check for breaking changes against previous version
python -m ipfs_kit_py.tools.check_api_compatibility --previous=0.1.0 --current=HEAD

# Generate API compatibility report
python -m ipfs_kit_py.tools.generate_api_report

# Print summary of all API stability levels
python -m ipfs_kit_py.api_stability

# Generate markdown API documentation with stability levels
python -m ipfs_kit_py.tools.generate_api_docs > api_reference.md
```
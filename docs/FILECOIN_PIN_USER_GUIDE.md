# Filecoin Pin Backend - User Guide

## Overview

The Filecoin Pin backend provides unified IPFS pinning with automatic Filecoin storage deal backing. It combines the speed and accessibility of IPFS with the long-term persistence guarantees of Filecoin.

## Features

- **Unified Storage**: Pin content to IPFS with automatic Filecoin deal creation
- **Multiple Access Points**: Retrieve content via IPFS gateways, local nodes, or Filecoin retrievals
- **Deal Management**: Track and monitor Filecoin storage deals
- **Replication Control**: Configure replication levels for redundancy
- **Mock Mode**: Test without API credentials
- **Gateway Fallback**: Automatic failover across multiple IPFS gateways
- **Integration**: Works with ARC cache, replication infrastructure, and CDN features

## Installation

### Basic Installation

```bash
pip install -e ".[filecoin_pin]"
```

### Full Installation (with all features)

```bash
pip install -e ".[filecoin_pin,car_files,saturn,ipni,enhanced_ipfs]"
```

## Configuration

### Environment Variables

Set your Filecoin Pin API key:

```bash
export FILECOIN_PIN_API_KEY="your_api_key_here"
```

**Security Note**: Always use environment variables for API keys rather than command-line arguments. Command-line arguments are recorded in shell history and visible in process listings, which can expose your credentials.

### Configuration File

Create `~/.ipfs_kit/backends/filecoin_pin.yaml`:

```yaml
type: filecoin_pin
enabled: true
api_endpoint: https://api.filecoin.cloud/v1
api_key: ${FILECOIN_PIN_API_KEY}
default_replication: 3
auto_renew: true
deal_duration_days: 540
gateway_fallback:
  - https://ipfs.io/ipfs/
  - https://w3s.link/ipfs/
  - https://dweb.link/ipfs/
```

## Usage

### Python API

#### Basic Usage

```python
from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend

# Initialize backend
backend = FilecoinPinBackend(
    resources={
        "api_key": "your_api_key",  # Or set FILECOIN_PIN_API_KEY env var
        "timeout": 60
    },
    metadata={
        "default_replication": 3,
        "auto_renew": True
    }
)

# Pin content
result = backend.add_content(
    content=b"Important data",
    metadata={
        "name": "my-dataset",
        "description": "Machine learning training data",
        "tags": ["ml", "training"],
        "replication": 3
    }
)

print(f"Pinned! CID: {result['cid']}")
print(f"Status: {result['status']}")
print(f"Deal IDs: {result['deal_ids']}")

# Check pin status
status = backend.get_metadata(result['cid'])
print(f"Status: {status['status']}")
print(f"Deals: {len(status['deals'])}")

# List all pins
pins = backend.list_pins(status="pinned", limit=100)
for pin in pins['pins']:
    print(f"- {pin['name']}: {pin['cid']}")

# Retrieve content
content_result = backend.get_content(result['cid'])
data = content_result['data']
print(f"Retrieved {len(data)} bytes from {content_result['source']}")

# Remove pin
remove_result = backend.remove_content(result['cid'])
print(f"Unpinned: {remove_result['success']}")
```

#### Mock Mode (No API Key)

```python
# Backend automatically enters mock mode if no API key provided
backend = FilecoinPinBackend(
    resources={"api_key": None},
    metadata={}
)

# All operations work in mock mode for testing
result = backend.add_content(b"Test content", {"name": "test"})
print(f"Mock pin created: {result['cid']}")
```

### CLI Commands

#### Pin a File

```bash
# Set your API key via environment variable (recommended for security)
export FILECOIN_PIN_API_KEY="your_api_key"

# Pin a local file
ipfs-kit filecoin-pin add /path/to/file.txt --name "my-file" --replication 3

# Pin by CID
ipfs-kit filecoin-pin add bafybeib... --name "existing-content"

# With tags and description
ipfs-kit filecoin-pin add file.pdf \
  --name "important-doc" \
  --description "Quarterly report" \
  --tags "report,q4,2024"

# Note: Avoid passing API keys as command-line arguments for security reasons
# The CLI reads from FILECOIN_PIN_API_KEY environment variable by default
```

#### List Pins

```bash
# List all pins
ipfs-kit filecoin-pin ls

# Filter by status
ipfs-kit filecoin-pin ls --status pinned
ipfs-kit filecoin-pin ls --status pinning

# Limit results
ipfs-kit filecoin-pin ls --limit 50
```

#### Check Pin Status

```bash
# Get detailed pin information
ipfs-kit filecoin-pin status bafybeib...

# Output includes:
# - Pin status (queued, pinning, pinned, failed)
# - Content size
# - Replication count
# - Filecoin deal IDs and providers
# - Creation timestamp
```

#### Remove a Pin

```bash
# Remove with confirmation
ipfs-kit filecoin-pin rm bafybeib...

# Force remove (skip confirmation)
ipfs-kit filecoin-pin rm bafybeib... --force
```

#### Retrieve Content

```bash
# Download to file
ipfs-kit filecoin-pin get bafybeib... --output downloaded-file.txt

# Print to stdout (for text content)
ipfs-kit filecoin-pin get bafybeib...
```

### MCP Tools (Model Context Protocol)

The Filecoin Pin backend exposes tools via the MCP protocol for integration with AI assistants and automation:

#### Available Tools

- `filecoin_pin_add` - Pin content
- `filecoin_pin_list` - List pins
- `filecoin_pin_status` - Get pin status
- `filecoin_pin_remove` - Remove pin
- `filecoin_pin_get` - Retrieve content

#### Example MCP Tool Call

```json
{
  "tool": "filecoin_pin_add",
  "arguments": {
    "content": "/path/to/file.txt",
    "name": "my-file",
    "description": "Important document",
    "tags": "work,important",
    "replication": 3
  }
}
```

### Integration with Existing Systems

#### Backend Manager Integration

The Filecoin Pin backend is automatically registered with the backend manager:

```python
from ipfs_kit_py.mcp.storage_manager.backend_manager import BackendManager

manager = BackendManager()
await manager.initialize_default_backends()

# Filecoin Pin backend is now available
backend = manager.get_backend("filecoin_pin")
result = backend.add_content(b"data", {"name": "test"})
```

#### Unified Pinning Service

Use the unified pinning service to pin across multiple backends:

```python
from ipfs_kit_py.mcp.storage_manager.pinning import UnifiedPinService

service = UnifiedPinService()

# Pin to multiple backends including Filecoin Pin
await service.pin(
    cid="bafybeib...",
    name="important-data",
    backends=["ipfs", "filecoin_pin", "storacha"]
)

# Check status across all backends
status = await service.pin_status("bafybeib...")
print(f"Backends: {status['backends']}")
```

#### Gateway Chain for Retrieval

Content retrieval automatically uses gateway fallback:

```python
from ipfs_kit_py.mcp.storage_manager.retrieval import GatewayChain

chain = GatewayChain(enable_parallel=True)

# Fetch with automatic fallback
content = await chain.fetch("bafybeib...")

# Or with metrics
content, metrics = await chain.fetch_with_metrics("bafybeib...")
print(f"Retrieved from {metrics['gateway_used']} in {metrics['duration_ms']}ms")
```

## Advanced Features

### Replication Configuration

Control how many copies of your data are stored:

```python
# High redundancy for critical data
backend.add_content(
    content=critical_data,
    metadata={"replication": 5}  # 5 copies
)

# Standard redundancy
backend.add_content(
    content=normal_data,
    metadata={"replication": 3}  # Default: 3 copies
)
```

### Deal Management

Monitor Filecoin storage deals:

```python
status = backend.get_metadata(cid)

for deal in status['deals']:
    print(f"Deal ID: {deal['id']}")
    print(f"Provider: {deal['provider']}")
    print(f"Status: {deal.get('status', 'active')}")
```

### Auto-Renewal

Deals automatically renew before expiration (configurable):

```python
backend = FilecoinPinBackend(
    resources={"api_key": api_key},
    metadata={
        "auto_renew": True,
        "deal_duration_days": 540  # ~18 months
    }
)
```

### Custom Gateway Configuration

Configure custom gateways for content retrieval:

```python
custom_gateways = [
    {"url": "http://localhost:8080/ipfs/", "priority": 1},
    {"url": "https://ipfs.io/ipfs/", "priority": 2},
    {"url": "https://dweb.link/ipfs/", "priority": 3}
]

chain = GatewayChain(gateways=custom_gateways)
```

## Integration with ARC Cache

The Filecoin Pin backend works seamlessly with the Adaptive Replacement Cache:

```python
from ipfs_kit_py.tiered_cache_manager import TieredCacheManager

# Configure cache with Filecoin Pin as a tier
config = {
    "tiers": {
        "memory": {"type": "memory", "priority": 1},
        "disk": {"type": "disk", "priority": 2},
        "ipfs": {"type": "ipfs", "priority": 3},
        "filecoin_pin": {"type": "filecoin_pin", "priority": 4}
    },
    "replication_policy": {
        "backends": ["memory", "disk", "ipfs", "filecoin_pin"]
    }
}

cache_manager = TieredCacheManager(config)

# Content automatically promoted/demoted across tiers
# Frequently accessed content stays in fast tiers
# Less accessed content moves to Filecoin Pin for long-term storage
```

## Replication Infrastructure

Filecoin Pin integrates with the replication infrastructure:

```python
from ipfs_kit_py.fs_journal_replication import MetadataReplicationManager

replication_config = {
    "mode": "selective",
    "min_redundancy": 3,
    "max_redundancy": 5,
    "backends": ["ipfs", "ipfs_cluster", "filecoin_pin", "storacha"]
}

# Replication manager ensures content is replicated across backends
# Filecoin Pin provides long-term persistence layer
```

## CDN Integration

Use Filecoin Pin as part of a robust CDN:

1. **Fast Tier**: Memory/disk cache for hot content
2. **Medium Tier**: IPFS nodes and clusters
3. **Cold Tier**: Filecoin Pin for long-term storage
4. **Retrieval**: Gateway chain with automatic fallback

Content flows automatically between tiers based on access patterns.

## Troubleshooting

### Mock Mode

If you see `mock: true` in responses, you're running in mock mode:

```bash
# Set your API key via environment variable (recommended)
export FILECOIN_PIN_API_KEY="your_key"

# Then run commands - they'll use the key from the environment
ipfs-kit filecoin-pin add file.txt
```

**Security Note**: The `--api-key` command-line option exists but should only be used for testing. Environment variables are the recommended approach for production use.

### Gateway Timeouts

If gateway retrieval times out:

```python
# Increase timeout
backend = FilecoinPinBackend(
    resources={"api_key": api_key, "timeout": 120},
    metadata={}
)
```

### Deal Status

Filecoin deals take time to complete:

- `queued`: Waiting to be processed
- `pinning`: Being pinned to IPFS
- `pinned`: Pinned, deals being created
- `failed`: Error occurred

Check status periodically:

```bash
ipfs-kit filecoin-pin status <cid>
```

## Best Practices

1. **Use meaningful names**: Help identify content later
2. **Add tags**: Categorize content for easier filtering
3. **Monitor deal status**: Check that deals complete successfully
4. **Set appropriate replication**: Balance cost vs. redundancy
5. **Use auto-renewal**: Avoid data loss from expired deals
6. **Test in mock mode**: Validate workflows before using real API

## API Reference

### FilecoinPinBackend Methods

- `add_content(content, metadata)` - Pin content
- `get_content(identifier)` - Retrieve content
- `remove_content(identifier)` - Unpin content
- `get_metadata(identifier)` - Get pin status
- `list_pins(status, limit)` - List all pins

### MCP Controller Methods

- `pin_add(request)` - Pin content
- `pin_list(request)` - List pins
- `pin_status(request)` - Get pin status
- `pin_remove(request)` - Remove pin
- `pin_get(request)` - Retrieve content

## Support and Resources

- **Documentation**: https://docs.filecoin.io/builder-cookbook/filecoin-pin
- **FAQ**: https://docs.filecoin.io/builder-cookbook/filecoin-pin/faq
- **GitHub**: https://github.com/filecoin-project/filecoin-pin
- **IPFS Kit**: https://github.com/endomorphosis/ipfs_kit_py

## License

This implementation is part of ipfs_kit_py and follows the same license terms.

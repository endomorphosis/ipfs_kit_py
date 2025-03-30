# Enhanced LibP2P Integration for IPFS Kit

This package provides advanced peer-to-peer functionality for IPFS Kit, enabling more efficient content discovery and direct content retrieval without relying on the IPFS daemon. It implements Phase 3A of the development roadmap: Direct P2P Communication.

## Key Features

- **Enhanced DHT-based Discovery**: Improved peer discovery with k-bucket optimization for more efficient routing
- **Provider Reputation Tracking**: Tracks the reliability and performance of content providers
- **Intelligent Content Routing**: Uses network metrics to find the optimal content providers
- **Direct P2P Content Retrieval**: Retrieves content directly from peers without requiring the IPFS daemon
- **Seamless Cache Integration**: Integrates with the tiered cache system to handle cache misses
- **Adaptive Backoff Strategies**: Implements backoff strategies for unreliable peers

## Components

The enhanced libp2p integration consists of several components that work together:

1. **EnhancedDHTDiscovery**: Implements advanced DHT-based peer discovery with k-bucket optimization
2. **ContentRoutingManager**: Manages intelligent content routing based on peer statistics
3. **LibP2PIntegration**: Provides integration between libp2p and the filesystem cache
4. **IPFSKit Integration**: Extends the IPFSKit class with libp2p functionality

## Usage

### Basic Usage

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.libp2p.ipfs_kit_integration import apply_ipfs_kit_integration

# Apply the integration to the IPFSKit class
apply_ipfs_kit_integration()

# Create an IPFSKit instance
kit = ipfs_kit()

# Get a filesystem interface with libp2p integration
fs = kit.get_filesystem(use_libp2p=True)

# Add content to IPFS
result = kit.ipfs_add_string("Hello, IPFS Kit with LibP2P integration!")
cid = result["Hash"]

# Retrieve content using the filesystem interface
# This will automatically use libp2p if the content isn't in the cache
content = fs.cat(cid)
```

### Advanced Usage

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
from ipfs_kit_py.libp2p.p2p_integration import register_libp2p_with_ipfs_kit
from ipfs_kit_py.libp2p.enhanced_dht_discovery import EnhancedDHTDiscovery, ContentRoutingManager

# Create an IPFSKit instance
kit = ipfs_kit()

# Create a libp2p peer with custom configuration
libp2p_peer = IPFSLibp2pPeer(
    role="worker",
    bootstrap_peers=[
        "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
        "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa"
    ],
    listen_addrs=[
        "/ip4/0.0.0.0/tcp/4001",
        "/ip4/0.0.0.0/udp/4001/quic"
    ]
)

# Register the libp2p peer with IPFSKit
integration = register_libp2p_with_ipfs_kit(kit, libp2p_peer, extend_cache=True)

# Create enhanced discovery manually if needed
discovery = EnhancedDHTDiscovery(
    libp2p_peer,
    role="worker",
    bootstrap_peers=libp2p_peer.bootstrap_peers
)
discovery.start()

# Create content routing manager manually if needed
router = ContentRoutingManager(discovery, libp2p_peer)

# Retrieve content directly using the content routing manager
future = router.retrieve_content(some_cid)
content = future.result(timeout=30)

# Get statistics from the integration
stats = integration.get_stats()
print(f"Cache miss success rate: {stats['success_rate']:.2f}")
```

## API Reference

### EnhancedDHTDiscovery

```python
class EnhancedDHTDiscovery:
    def __init__(self, libp2p_peer, role="leecher", bootstrap_peers=None)
    def start()
    def stop()
    def find_providers(self, cid, count=5, callback=None)
    def add_provider(self, cid, peer_id, multiaddrs=None, connection_type=None, reputation=0.5)
    def get_optimal_providers(self, cid, content_size=None, preferred_peers=None, count=3)
    def update_provider_stats(self, peer_id, success, latency=None, bytes_received=None)
```

### ContentRoutingManager

```python
class ContentRoutingManager:
    def __init__(self, dht_discovery, libp2p_peer)
    def find_content(self, cid, options=None)
    def retrieve_content(self, cid, options=None)
    def announce_content(self, cid, size=None, metadata=None)
    def get_metrics()
```

### LibP2PIntegration

```python
class LibP2PIntegration:
    def __init__(self, libp2p_peer, ipfs_kit=None, cache_manager=None)
    def handle_cache_miss(self, cid)
    def announce_content(self, cid, data=None, size=None, metadata=None)
    def stop()
    def get_stats()
```

### Helper Functions

```python
def register_libp2p_with_ipfs_kit(ipfs_kit, libp2p_peer, extend_cache=True)
def extend_tiered_cache_manager(cache_manager, libp2p_integration)
def apply_ipfs_kit_integration()
def extend_ipfs_kit_class(ipfs_kit_cls)
```

## Architecture

The enhanced libp2p integration is designed as a layered architecture:

1. **Base Layer**: Enhanced DHT discovery and content routing (EnhancedDHTDiscovery, ContentRoutingManager)
2. **Integration Layer**: Connects libp2p functionality with IPFSKit (LibP2PIntegration)
3. **Extension Layer**: Extends IPFSKit with libp2p miss handling (IPFSKit integration)

This design allows for flexible integration with the existing codebase and enables easy extension for future improvements.

## Error Handling

The implementation includes comprehensive error handling with:

- Proper exception handling for network operations
- Fallback mechanisms when peers fail
- Adaptive backoff strategies for unreliable peers
- Detailed logging for troubleshooting

## Performance Considerations

The enhanced libp2p integration is designed for performance:

- **Caching**: Caches discovery results and provider information
- **Concurrency**: Uses asynchronous operations for network IO
- **Resource Awareness**: Adapts behavior based on node role and available resources
- **Metrics Collection**: Tracks performance metrics for optimization

## Examples

See the `/examples/libp2p_example.py` file for a complete example of using the enhanced libp2p integration.

## Testing

The unit tests for the libp2p integration are in the `/test/test_libp2p_integration.py` file. Run them with:

```bash
python -m unittest test.test_libp2p_integration
```
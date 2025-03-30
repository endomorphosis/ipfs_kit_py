# libp2p Integration for IPFS Kit

## Overview

The libp2p integration provides direct peer-to-peer communication capabilities for IPFS Kit without requiring a full IPFS daemon. This enables lightweight nodes to participate in the network, establish direct connections with peers, and exchange content efficiently. The integration includes a sophisticated bitswap implementation and seamless integration with the tiered storage system.

## Key Features

- **Direct Peer Connections**: Establish direct connections with other peers using libp2p
- **Protocol Negotiation**: Dynamically negotiate protocols for communication
- **Enhanced Bitswap Protocol**: Advanced content exchange with priority handling and wantlists
- **Secure Messaging**: Encrypted and authenticated communication between peers
- **NAT Traversal**: Reliable connectivity across network boundaries through relays and hole punching
- **Peer Discovery**: Find peers using DHT, mDNS, bootstrap nodes, PubSub, and random walks
- **Content Routing**: Efficient resource-aware content discovery and retrieval
- **Role-Based Behavior**: Specialized behavior based on node role (master/worker/leecher)
- **Tiered Storage Integration**: Seamless access to content across different storage tiers
- **Heat-Based Promotion**: Automatic content promotion based on access patterns

## Architecture

The libp2p integration consists of several key components:

1. **IPFSLibP2PPeer**: Main class for direct P2P communication
   - Handles peer connections, discovery, and content exchange
   - Implements role-specific behaviors (master/worker/leecher)
   - Integrates with tiered storage system

2. **Peer Discovery System**: Multi-layer peer discovery mechanism
   - mDNS for local network discovery
   - DHT-based discovery for global network
   - PubSub announcements for real-time updates
   - Random walk discovery for network exploration
   - Bootstrap peers for initial connectivity

3. **Bitswap Protocol Implementation**: Advanced content exchange
   - Multi-message type support (want, have, wantlist, cancel)
   - Priority-based content retrieval
   - Wantlist tracking and management
   - Content heat scoring

4. **NAT Traversal**: Comprehensive connectivity solutions
   - Direct connection establishment with hole punching
   - Relay-based connections for complex NAT scenarios
   - Relay discovery and announcement

5. **Tiered Storage Integration**: Seamless content access
   - Asynchronous content retrieval from tiered storage
   - Heat-based promotion of frequently accessed content
   - Integration with memory, disk, and cold storage tiers

This architecture provides a robust foundation for peer-to-peer content exchange without the overhead of a full IPFS daemon, while leveraging the performance benefits of tiered storage.

## Usage

### Basic Usage

```python
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer

# Initialize a libp2p peer with default settings
peer = IPFSLibp2pPeer(
    role="worker",
    listen_addrs=["/ip4/0.0.0.0/tcp/0", "/ip4/0.0.0.0/udp/0/quic"]
)

# Connect to a remote peer
peer.connect_peer("/ip4/192.168.1.10/tcp/4001/p2p/QmRemotePeerId")

# Request content directly from connected peers
content = peer.request_content("QmContentHash")

# Announce available content to the network
peer.announce_content("QmContentHash", metadata={"size": 1024})

# Start discovery to find more peers
peer.start_discovery()
```

### Tiered Storage Integration

```python
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
from ipfs_kit_py.tiered_cache import TieredCacheManager

# Initialize tiered storage manager
storage_manager = TieredCacheManager({
    'memory_cache_size': 100 * 1024 * 1024,  # 100MB
    'local_cache_size': 1 * 1024 * 1024 * 1024,  # 1GB
    'local_cache_path': '/tmp/ipfs_cache'
})

# Create a peer with tiered storage integration
peer = IPFSLibp2pPeer(
    role="worker",
    listen_addrs=["/ip4/0.0.0.0/tcp/4001"],
    tiered_storage_manager=storage_manager
)

# Store content in local store and announce to network
content = b"Hello, IPFS!"
cid = "QmExampleContentID"
peer.store_bytes(cid, content)
peer.announce_content(cid, metadata={"size": len(content)})

# When content is requested, it will automatically:
# 1. Check memory store first
# 2. Check tiered storage if not in memory
# 3. Track access heat for promotion to faster tiers
```

### Advanced Configuration

```python
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
import asyncio

# Create a peer with advanced configuration
peer = IPFSLibp2pPeer(
    role="master",
    identity_path="~/.ipfs/libp2p_identity",
    listen_addrs=[
        "/ip4/0.0.0.0/tcp/4001",
        "/ip4/0.0.0.0/udp/4001/quic"
    ],
    bootstrap_peers=[
        "/dnsaddr/bootstrap.libp2p.io/p2p/QmBootstrapPeerId1",
        "/dnsaddr/bootstrap.libp2p.io/p2p/QmBootstrapPeerId2"
    ],
    enable_mdns=True,
    enable_hole_punching=True,
    enable_relay=True,
    tiered_storage_manager=storage_manager
)

# Register a custom protocol handler
def register_protocol_handler(protocol_id, handler):
    peer.register_protocol_handler(protocol_id, handler)

# Example custom protocol handler
async def handle_custom_protocol(stream):
    data = await stream.read()
    # Process the request
    await stream.write(b"Response data")
    await stream.close()

register_protocol_handler("/my/custom/protocol/1.0.0", handle_custom_protocol)
```

### Using the Enhanced Bitswap Protocol

The enhanced bitswap protocol provides a sophisticated content exchange mechanism with priority handling, wantlists, and heat-based optimization:

```python
# Request content with priority
content = peer.request_content("QmContentCID", priority=3)  # Higher priority (1-5)

# Check if a peer has specific content
async def check_content_availability():
    peers_with_content = await peer._find_providers_async("QmContentCID")
    for provider in peers_with_content:
        # Create a "have" request to check availability
        # This would typically be handled internally
        request = {
            "type": "have",
            "cid": "QmContentCID"
        }
        # Send request to peer
        # ... implementation details ...

# Proactive content fetching (master nodes)
if peer.role == "master":
    async def prefetch_popular_content():
        # Get high-priority items from wantlist
        wantlist = peer._get_current_wantlist()
        popular_cids = [item["cid"] for item in wantlist 
                      if item["priority"] > 3 and item["requester_count"] > 2]
        
        # Fetch proactively
        for cid in popular_cids:
            providers = await peer._find_providers_async(cid)
            if providers:
                await peer._fetch_content_proactively(cid, providers)
```

## Integration with Role-Based Architecture

The libp2p implementation fully integrates with our role-based architecture, providing optimized behaviors for each node type:

### Master Nodes

- Maintain comprehensive peer tables and routing information
- Proactively fetch popular content based on cluster-wide requests
- Provide relay services for peers behind NAT
- Participate fully in DHT as server nodes
- Handle task distribution and coordination
- Maintain backup provider information
- Respond to complex content queries

### Worker Nodes

- Actively contribute processing capabilities to the network
- Execute task assignments from master nodes
- Participate in content distribution and replication
- Provide relay services when appropriate
- Participate in DHT as server nodes
- Implement caching and prefetching based on assigned tasks

### Leecher Nodes

- Optimize for minimal resource usage
- Connect to limited set of peers (primarily master nodes)
- Use DHT in client mode for resource efficiency
- Prefer direct content retrieval over relaying
- Implement efficient local caching
- Optimize for offline/intermittent connectivity
- Minimize network and storage overhead

## Tiered Storage Integration

The libp2p peer seamlessly integrates with the tiered storage system:

1. **Automated Content Placement**:
   - New content is stored in the appropriate tier based on size and importance
   - Frequently accessed content is automatically promoted to faster tiers
   - Rarely accessed content is demoted to slower, more efficient storage

2. **Heat-Based Optimization**:
   - Access patterns are tracked to calculate "heat scores" for each content
   - Heat scoring combines frequency, recency, and age factors
   - Content above certain heat thresholds is promoted to faster tiers

3. **Asynchronous Access Patterns**:
   - Non-blocking access to tiered storage avoids performance bottlenecks
   - Compatible with both synchronous and asynchronous storage managers
   - Proper error handling and timeout management

4. **Role-Specific Optimizations**:
   - Master nodes prioritize content needed for orchestration
   - Worker nodes optimize for task-related content
   - Leecher nodes focus on efficient local caching

## Performance Considerations

- Direct peer connections minimize latency compared to gateway access
- Tiered storage integration provides optimal performance/storage tradeoffs
- Asynchronous I/O prevents blocking during network and storage operations
- NAT traversal ensures reliable connectivity in complex network environments
- Protocol negotiation allows compatibility with varied peer implementations
- Heat-based promotion ensures frequently accessed content is in fastest tiers
- Proper resource management based on node role and capabilities

## Future Enhancements

- Bandwidth throttling and QoS for prioritized content
- Enhanced security with authentication and authorization
- Reputation system for peer quality metrics
- Graphsync protocol support for efficient graph-based data exchange
- Bloom filter-based content advertisement for efficient content routing
- IPLD-based content verification
- Cross-language interoperability via shared memory interfaces
- Advanced relay selection based on network topology
- Distributed task scheduling using peer communication
# libp2p Implementation for ipfs_kit_py

This module provides a comprehensive implementation of the libp2p protocol stack for ipfs_kit_py, supporting direct peer-to-peer communication, content routing, and advanced networking capabilities.

## Features

- **Core Networking**
  - Multi-transport support (TCP, QUIC, WebRTC, WebTransport)
  - Protocol negotiation with semantic versioning
  - Stream multiplexing and backpressure
  - NAT traversal and peer discovery

- **Security**
  - Noise Protocol for secure communications
  - Identity-based authentication
  - Permission control

- **Content Routing**
  - DHT-based content discovery
  - Provider record management
  - Reputation tracking for optimal content routing

- **Specialized Protocols**
  - Bitswap for content exchange
  - DAG Exchange (GraphSync) for IPLD traversal
  - GossipSub for publish/subscribe messaging

- **Integration Points**
  - Seamless integration with IPFSKit and high-level API
  - Tiered storage system integration
  - AnyIO support for async framework compatibility

## Architecture

The implementation follows a modular design with clear separation of concerns:

```
libp2p/
├── __init__.py              # Entry point with dependency detection
├── hooks.py                 # Protocol extension hooks
├── autonat.py               # NAT detection and traversal
├── dag_exchange.py          # IPLD DAG exchange (GraphSync)
├── enhanced_dht_discovery.py # Advanced DHT-based discovery
├── enhanced_protocol_negotiation.py # Improved protocol selection
├── gossipsub_protocol.py    # PubSub implementation
├── high_level_api_integration.py # Integration with high-level API
├── ipfs_kit_integration.py  # Integration with IPFSKit
├── noise_protocol.py        # Noise Protocol security
├── p2p_integration.py       # Integration with P2P subsystem
├── protocol_integration.py  # Protocol extension system
├── typing.py                # Type definitions
├── webrtc_transport.py      # WebRTC transport implementation
└── webtransport.py          # WebTransport implementation
```

## Integration with ipfs_kit_py

The libp2p module integrates with ipfs_kit_py through several key interfaces:

1. **IPFSLibp2pPeer Class**
   - Provides direct peer-to-peer interactions
   - Handles multiple transports and protocols
   - Enables content routing and discovery

2. **TieredCacheManager Integration**
   - Allows direct content retrieval from peers
   - Optimizes storage with peer-based cache sources
   - Enables heat-based content promotion

3. **High-Level API Extensions**
   - Adds peer discovery to simplified API
   - Provides protocol management functionality
   - Offers network visualization capabilities

## Role-based Optimization

The implementation includes role-specific optimizations:

- **Master Node**
  - Full DHT server node
  - Acts as relay for worker/leecher nodes
  - Maintains comprehensive provider records

- **Worker Node**
  - Balanced DHT client/server
  - Optimized for content processing
  - Cooperative caching strategies

- **Leecher Node**
  - Lightweight DHT client
  - Minimal resource utilization
  - Optimized for content consumption

## Implementation Status

The implementation covers all core functionality, with advanced features being continuously added:

- ✅ **Core Networking**: Complete implementation
- ✅ **Peer Identity**: Fully implemented
- ✅ **Protocol Negotiation**: Enhanced with semantic versioning
- ✅ **Connection Management**: Comprehensive implementation
- ✅ **Discovery Mechanisms**: DHT, mDNS, Bootstrap peers
- ✅ **Content Routing**: Advanced provider tracking
- ✅ **Security**: Basic secure transport with Noise Protocol
- ✅ **GossipSub**: Complete implementation
- ✅ **Bitswap**: Comprehensive implementation
- ✅ **Tiered Storage Integration**: Fully implemented
- ✅ **Role-based Optimization**: Master/worker/leecher support
- ⚠️ **Advanced Transport Protocols**: Partial implementation
- ⚠️ **Advanced NAT Traversal**: Basic implementation
- ⚠️ **DAG Exchange**: Implementation in progress

## Usage

### Basic Peer Setup

```python
from ipfs_kit_py import ipfs_kit
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer

# Initialize libp2p peer with desired role
libp2p_peer = IPFSLibp2pPeer(role="worker")

# Start the peer
await libp2p_peer.start()

# Connect to a bootstrap peer
bootstrap_addr = "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
await libp2p_peer.connect(bootstrap_addr)

# Request content directly from the network
data = await libp2p_peer.get_content_by_cid("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")

# Stop the peer when done
await libp2p_peer.stop()
```

### Integration with IPFSKit

```python
from ipfs_kit_py import ipfs_kit
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer

# Initialize kit and libp2p peer
kit = ipfs_kit()
libp2p_peer = IPFSLibp2pPeer(role="worker")

# Register libp2p with IPFSKit
from ipfs_kit_py.libp2p import register_libp2p_with_ipfs_kit
integration = register_libp2p_with_ipfs_kit(kit, libp2p_peer)

# Now IPFSKit can use libp2p for direct content retrieval
# and will automatically attempt direct peer connections when
# content is not available in the local cache
content = kit.cat("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
```

### WebRTC Transport

```python
from ipfs_kit_py.libp2p.webrtc_transport import WebRTCTransport

# Initialize WebRTC transport
webrtc = WebRTCTransport(libp2p_peer)

# Set protocol handlers
webrtc.set_protocol_handler("/ipfs/ping/1.0.0", ping_handler)

# Establish connection
stream = await webrtc.dial(peer_id, ["/ipfs/ping/1.0.0"])

# Use the stream
await stream.write(b"ping\n")
pong = await stream.read(1024)
```

### Noise Protocol Security

```python
from ipfs_kit_py.libp2p.noise_protocol import NoiseProtocol

# Initialize Noise protocol
noise = NoiseProtocol()

# Perform handshake as initiator
remote_pubkey_bytes = bytes.fromhex("...")
session = await noise.handshake_initiator(remote_pubkey_bytes, stream)

# Send encrypted data
ciphertext = noise.encrypt(session, b"secret message")
await stream.write(ciphertext)

# Receive and decrypt
ciphertext = await stream.read(1024)
plaintext = noise.decrypt(session, ciphertext)
```

### DAG Exchange (GraphSync)

```python
from ipfs_kit_py.libp2p.dag_exchange import DAGExchange, make_all_selector

# Initialize DAG Exchange
dag_exchange = DAGExchange(libp2p_peer)
await dag_exchange.start()

# Define response handler
def handle_response(response):
    for cid, block in response.blocks.items():
        print(f"Received block {cid}, size: {len(block)} bytes")

# Request a DAG starting from a root CID
root_cid = "QmRootCID..."
selector = make_all_selector()
request_id = await dag_exchange.request(
    peer_id="QmPeerID...",
    root_cid=root_cid,
    selector=selector,
    callback=handle_response
)

# Later, cancel if needed
await dag_exchange.cancel_request(request_id)
```

## Extending the Implementation

The implementation is designed to be extensible through several mechanisms:

1. **Protocol Extensions**
   - Register custom protocols via `apply_protocol_extensions`
   - Add new protocol handlers to existing transports
   - Create specialized stream handlers

2. **Custom Selectors**
   - Extend DAG Exchange with custom IPLD selectors
   - Create domain-specific traversal patterns
   - Implement selective content retrieval

3. **Advanced Network Topologies**
   - Configure relay networks for NAT traversal
   - Implement custom peer discovery mechanisms
   - Create specialized content routing algorithms

## Enhanced Features

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

### GossipSub Protocol Methods

```python
# Methods added to IPFSLibp2pPeer by protocol extensions
def publish_to_topic(self, topic_id: str, data: Union[str, bytes]) -> Dict[str, Any]
def subscribe_to_topic(self, topic_id: str, handler: Callable) -> Dict[str, Any]
def unsubscribe_from_topic(self, topic_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]
def get_topic_peers(self, topic_id: str) -> Dict[str, Any]
def list_topics(self) -> Dict[str, Any]
```

## Testing

The unit tests for the libp2p implementation are in the `/test/test_libp2p_integration.py` and related test files. Run them with:

```bash
python -m unittest test.test_libp2p_integration
python -m unittest test.test_libp2p_pubsub
python -m unittest test.test_libp2p_kademlia
```

## License

This implementation is part of the ipfs_kit_py project and is subject to the same license terms.

## References

- [libp2p Specifications](https://github.com/libp2p/specs)
- [IPFS Documentation](https://docs.ipfs.tech/)
- [IPLD Specifications](https://github.com/ipld/specs)
- [WebRTC Documentation](https://webrtc.org/getting-started/overview)
- [WebTransport Documentation](https://w3c.github.io/webtransport/)
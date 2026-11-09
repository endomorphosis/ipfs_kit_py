# Universal Connectivity for ipfs_kit_py

This module provides comprehensive peer connectivity features inspired by the [libp2p/universal-connectivity](https://github.com/libp2p/universal-connectivity) project.

## Features

### 🌐 Multiple Transport Protocols
- **TCP**: Traditional TCP connections
- **QUIC**: Fast UDP-based transport
- **WebRTC**: Browser-to-browser connectivity
- **WebTransport**: Modern web transport protocol

### 🔍 Peer Discovery Mechanisms

#### 1. Pubsub Peer Discovery
Peers announce themselves periodically on GossipSub topics.
```python
from ipfs_kit_py.libp2p.pubsub_peer_discovery import PubsubPeerDiscovery

discovery = PubsubPeerDiscovery(
    host,
    topics=["_peer-discovery._p2p._pubsub"],
    interval=10.0  # Announce every 10 seconds
)
await discovery.start()
```

#### 2. mDNS Discovery
Zero-configuration local network discovery.
```python
from ipfs_kit_py.libp2p.mdns_discovery import MDNSService

mdns = MDNSService(host, service_name="my-app")
await mdns.start()
```

#### 3. DHT Discovery
Global peer discovery using Kademlia DHT (already implemented in `enhanced_dht_discovery.py`).

### 🔒 NAT Traversal

#### 1. AutoNAT
Automatically detect NAT type and reachability.
```python
from ipfs_kit_py.libp2p.autonat import AutoNAT

autonat = AutoNAT(host, query_interval=300)
# Check NAT status
status = autonat.nat_status  # "public", "private", or "unknown"
```

#### 2. Circuit Relay v2
Relay connections through intermediate peers.
```python
from ipfs_kit_py.libp2p.circuit_relay import CircuitRelayClient, CircuitRelayServer

# As a client (use relays)
client = CircuitRelayClient(host, max_reservations=3)
await client.start()
await client.make_reservation(relay_peer_id, relay_addr)

# As a server (provide relay service)
server = CircuitRelayServer(host, max_circuits=256)
await server.start()
```

#### 3. DCUtR
Upgrade relayed connections to direct connections via hole punching.
```python
from ipfs_kit_py.libp2p.dcutr import DCUtR

dcutr = DCUtR(host)
await dcutr.start()

# Attempt hole punch
success = await dcutr.attempt_hole_punch(
    remote_peer_id=peer_id,
    relay_peer_id=relay_id
)
```

## Universal Connectivity Manager

The easiest way to use all features is through the Universal Connectivity Manager:

```python
from ipfs_kit_py.libp2p.universal_connectivity import (
    UniversalConnectivityManager,
    ConnectivityConfig
)

# Configure
config = ConnectivityConfig(
    # Discovery
    enable_mdns=True,
    enable_pubsub_discovery=True,
    enable_dht_discovery=True,
    
    # NAT traversal
    enable_autonat=True,
    enable_relay_client=True,
    enable_relay_server=False,  # Set True to act as relay
    enable_dcutr=True,
    
    # Bootstrap peers
    connect_to_bootstrap=True,
    # Uses IPFS bootstrap peers by default
)

# Create manager
manager = UniversalConnectivityManager(host, config)
await manager.start()

# Get metrics
metrics = manager.get_metrics()
print(f"Active connections: {metrics.active_connections}")
print(f"NAT status: {metrics.nat_status}")
print(f"Peers discovered: {metrics.total_peers_discovered}")

# Get discovered peers
peers = manager.get_discovered_peers()
for peer in peers:
    print(f"Peer: {peer.peer_id}, Addrs: {peer.multiaddrs}")

# Dial a peer with intelligent strategy
success = await manager.dial_peer(
    peer_id="QmPeer...",
    addrs=["/ip4/1.2.3.4/tcp/4001"],
    use_relay=True  # Fallback to relay if direct fails
)
```

## Complete Example

```python
import anyio
from ipfs_kit_py.libp2p.universal_connectivity import (
    setup_universal_connectivity,
    ConnectivityConfig
)

async def main():
    # Assume you have a libp2p host
    # host = await create_libp2p_host()
    
    # Setup universal connectivity with defaults
    config = ConnectivityConfig(
        # Enable all discovery mechanisms
        enable_mdns=True,
        enable_pubsub_discovery=True,
        enable_dht_discovery=True,
        
        # Enable NAT traversal
        enable_autonat=True,
        enable_relay_client=True,
        enable_dcutr=True,
        
        # Callbacks
        on_peer_discovered=lambda peer: print(f"Discovered: {peer.peer_id}"),
        on_connection_established=lambda peer_id, addr: print(f"Connected: {peer_id}")
    )
    
    # Start connectivity manager
    manager = await setup_universal_connectivity(host, config)
    
    # Your application logic here
    await anyio.sleep(3600)  # Run for 1 hour
    
    # Cleanup
    await manager.stop()

if __name__ == "__main__":
    anyio.run(main)
```

## Architecture

The connectivity features are organized as follows:

```
libp2p/
├── autonat.py                  # AutoNAT protocol
├── circuit_relay.py            # Circuit Relay v2
├── dcutr.py                    # DCUtR hole punching
├── pubsub_peer_discovery.py   # Pubsub-based discovery
├── mdns_discovery.py           # mDNS local discovery
├── enhanced_dht_discovery.py  # DHT-based discovery (existing)
└── universal_connectivity.py  # Manager integrating all features
```

## Bootstrap Peers

The default bootstrap peers from IPFS are used:
- `/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN`
- `/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa`
- `/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb`
- `/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt`

You can override these in `ConnectivityConfig.bootstrap_peers`.

## Connection Strategy

The manager uses an intelligent connection strategy:

1. **Direct Connection**: Try direct dial to known addresses
2. **Relay Fallback**: If direct fails and relay is available, use circuit relay
3. **DCUtR Upgrade**: Once relayed, attempt hole punching to upgrade to direct
4. **Multiple Discovery**: Use all enabled discovery mechanisms in parallel

## Metrics

The manager tracks comprehensive metrics:

```python
metrics = manager.get_metrics()

# Counts
metrics.total_peers_discovered
metrics.total_connections_established
metrics.total_connections_failed
metrics.active_connections

# Connection types
metrics.relay_connections
metrics.direct_connections

# NAT info
metrics.nat_status  # "public", "private", "unknown"

# Performance
metrics.dcutr_success_rate
metrics.last_updated
```

## Best Practices

### For Browser Peers
- Enable: AutoNAT client, Relay client, DCUtR, Pubsub discovery
- Disable: Relay server, mDNS

### For Server Peers
- Enable: All features including Relay server
- Act as bootstrap nodes for private networks

### For Private Networks
- Disable connections to public bootstrap
- Use custom bootstrap peers
- Enable mDNS for local discovery

### For Development
- Enable mDNS for quick local peer discovery
- Enable all logging for debugging
- Use smaller intervals for faster discovery

## Troubleshooting

### Peers not discovered
- Check firewall rules
- Verify bootstrap peer connectivity
- Enable verbose logging: `logging.getLogger("UniversalConnectivity").setLevel(logging.DEBUG)`

### NAT traversal failing
- Ensure relay client is enabled
- Check if relay reservations are successful: `manager.relay_client.reservations`
- Verify DCUtR is enabled for hole punching

### High latency
- DCUtR should upgrade relayed connections automatically
- Check `metrics.dcutr_success_rate`
- Ensure public addresses are correctly advertised

## References

- [libp2p Universal Connectivity](https://github.com/libp2p/universal-connectivity)
- [libp2p Specs](https://github.com/libp2p/specs)
- [Circuit Relay v2](https://github.com/libp2p/specs/tree/master/relay)
- [DCUtR](https://github.com/libp2p/specs/blob/master/relay/DCUtR.md)
- [AutoNAT](https://github.com/libp2p/specs/blob/master/autonat/README.md)

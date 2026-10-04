"""
Type definitions for libp2p.

This module provides type definitions used in libp2p interfaces.
It serves as a bridge between standard Python typing and libp2p-specific types.
"""

from typing import NewType, Dict, List, Set, Any, Union, Callable, Optional, Protocol, TypeVar

# Protocol identifier type
TProtocol = NewType('TProtocol', str)

# Stream identifier type
TStreamID = NewType('TStreamID', str)

# Content identifier type
TCID = NewType('TCID', str) 

# Connection identifier type
TConnID = NewType('TConnID', str)

# Peer identifier type
TPeerID = NewType('TPeerID', str)

# Protocol handler type
TProtocolHandler = Callable[[Any], None]

# Multiaddress type
TMultiaddr = NewType('TMultiaddr', str)

# Key type
TKey = NewType('TKey', bytes)

# Value type
TValue = NewType('TValue', bytes)

# Message ID type
TMessageID = NewType('TMessageID', str)

# Topic identifier type
TTopic = NewType('TTopic', str)

# Type for libp2p network interface
class INetwork(Protocol):
    """Interface for libp2p network operations."""
    
    def get_connections(self) -> Dict[TPeerID, Any]:
        """Get active connections."""
        ...
    
    def connect(self, peer_info) -> None:
        """Connect to a peer."""
        ...
    
    def listen(self) -> None:
        """Start listening for connections."""
        ...
    
    def close(self) -> None:
        """Close all connections."""
        ...

# Type for stream interface
class IStream(Protocol):
    """Interface for libp2p stream operations."""
    
    async def read(self, max_bytes: int = None) -> bytes:
        """Read from the stream."""
        ...
    
    async def read_until(self, delimiter: bytes, max_bytes: int = None) -> bytes:
        """Read from the stream until delimiter is found."""
        ...
    
    async def write(self, data: bytes) -> None:
        """Write to the stream."""
        ...
    
    async def close(self) -> None:
        """Close the stream."""
        ...
    
    async def reset(self) -> None:
        """Reset the stream."""
        ...

# Type for host interface
class IHost(Protocol):
    """Interface for libp2p host operations."""
    
    def get_id(self) -> TPeerID:
        """Get the peer ID."""
        ...
    
    def get_addrs(self) -> List[TMultiaddr]:
        """Get listening addresses."""
        ...
    
    def get_network(self) -> INetwork:
        """Get the network."""
        ...
    
    def set_stream_handler(self, protocol_id: TProtocol, handler: TProtocolHandler) -> None:
        """Set handler for a protocol."""
        ...
    
    async def new_stream(self, peer_id: TPeerID, protocol_id: TProtocol) -> IStream:
        """Create a new stream to a peer."""
        ...
    
    async def connect(self, peer_info) -> None:
        """Connect to a peer."""
        ...

# Type for PubSub interface
class IPubSub(Protocol):
    """Interface for libp2p pubsub operations."""
    
    async def subscribe(self, topic_id: str, handler: Callable) -> None:
        """Subscribe to a topic."""
        ...
    
    async def unsubscribe(self, topic_id: str) -> None:
        """Unsubscribe from a topic."""
        ...
    
    async def publish(self, topic_id: str, data: bytes) -> None:
        """Publish to a topic."""
        ...
    
    async def start(self) -> None:
        """Start the pubsub system."""
        ...
    
    async def stop(self) -> None:
        """Stop the pubsub system."""
        ...

# Type for DHT interface
class IDHT(Protocol):
    """Interface for libp2p DHT operations."""
    
    async def provide(self, key: str) -> bool:
        """Announce that this peer can provide a value for the given key."""
        ...
    
    async def find_providers(self, key: str, count: int = 20) -> List[Any]:
        """Find peers that can provide a value for the given key."""
        ...
    
    async def get_providers(self, key: str, count: int = 20) -> List[Any]:
        """Alias for find_providers in some implementations."""
        ...
    
    async def find_peer(self, peer_id: str) -> List[Any]:
        """Find a peer in the DHT."""
        ...
    
    async def find_value(self, key: str) -> Optional[bytes]:
        """Find a value in the DHT."""
        ...
    
    async def get_value(self, key: str) -> Optional[bytes]:
        """Alias for find_value in some implementations."""
        ...
    
    async def store_value(self, key: str, value: bytes) -> bool:
        """Store a value in the DHT."""
        ...
    
    async def put_value(self, key: str, value: bytes) -> bool:
        """Alias for store_value in some implementations."""
        ...
    
    async def bootstrap(self, bootstrap_nodes: List[Any] = None) -> int:
        """Bootstrap the DHT."""
        ...
    
    async def refresh(self) -> bool:
        """Refresh the DHT routing table."""
        ...
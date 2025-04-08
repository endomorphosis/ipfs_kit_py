# MCP Server Communication Methods

This document outlines the communication methods between the MCP Server and ipfs_kit_py components, focusing on WebRTC, WebSockets, and libp2p integration.

## Overview

The MCP (Model-Controller-Persistence) Server can communicate with ipfs_kit_py through three primary protocols:

1. **WebRTC**: For real-time streaming of media content
2. **WebSockets**: For event notifications and real-time updates
3. **libp2p**: For direct peer-to-peer communication without intermediaries

Each protocol serves different use cases and offers unique advantages for specific scenarios.

## WebRTC Communication

WebRTC (Web Real-Time Communication) provides peer-to-peer audio, video, and data communication directly between browsers or nodes without requiring intermediary servers for the data transfer.

### Key Components

1. **WebRTCStreamingManager**: Core class that manages WebRTC connections
2. **IPFSMediaStreamTrack**: Media stream that sources content from IPFS
3. **AdaptiveBitrateController**: Adjusts streaming quality based on network conditions
4. **Signaling Handler**: Manages WebRTC connection establishment

### Setup Process

1. The MCP Server initializes WebRTC support through the IPFSModel:
   ```python
   # In ipfs_model.py
   def _init_webrtc(self):
       """Initialize WebRTC streaming manager if dependencies are available."""
       if 'HAVE_WEBRTC' in globals() and HAVE_WEBRTC:
           logger.info("WebRTC dependencies available, initializing WebRTC support")
           try:
               # Create WebRTC streaming manager with the IPFS client
               self.webrtc_manager = WebRTCStreamingManager(ipfs_api=self.ipfs_kit)
               logger.info("WebRTC streaming manager initialized successfully")
               return True
           except Exception as e:
               logger.warning(f"Failed to initialize WebRTC streaming manager: {e}")
       else:
           logger.info("WebRTC dependencies not available. WebRTC functionality will be disabled.")
       
       return False
   ```

2. The client (browser or another ipfs_kit_py instance) connects via WebRTC signaling:
   ```python
   # Client-side connection example
   async def connect_to_mcp_webrtc(mcp_url, cid):
       # Create WebSocket connection for signaling
       async with websockets.connect(f"ws://{mcp_url}/webrtc") as websocket:
           # Request an offer for the specified content
           await websocket.send(json.dumps({
               "type": "offer_request",
               "cid": cid
           }))
           
           # Receive the offer
           response = json.loads(await websocket.recv())
           if response["type"] == "offer":
               # Process the WebRTC offer...
               sdp = response["sdp"]
               pc_id = response["pc_id"]
               
               # Create and initialize local peer connection
               pc = RTCPeerConnection()
               
               # Set the remote description (server's offer)
               await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
               
               # Create an answer
               answer = await pc.createAnswer()
               await pc.setLocalDescription(answer)
               
               # Send the answer back
               await websocket.send(json.dumps({
                   "type": "answer",
                   "pc_id": pc_id,
                   "sdp": pc.localDescription.sdp
               }))
               
               # Connection established, media will flow automatically
   ```

### Content Streaming Flow

1. **Source Selection**: Content is sourced from IPFS by CID
2. **Media Processing**: Chunking, encoding, and packaging for real-time delivery
3. **Adaptive Streaming**: Bitrate and quality adjustment based on network conditions
4. **Consumption**: Client receives and renders media stream

## WebSocket Communication

WebSockets provide a full-duplex communication channel over a single TCP connection, enabling real-time data exchange between the server and clients.

### Key Components

1. **NotificationType**: Enum defining different types of notifications
2. **emit_event**: Function to send events to connected clients
3. **WebSocketManager**: Manages WebSocket connections and message routing
4. **SocketRoute**: Registers endpoints for different WebSocket functionalities

### Setup Process

1. The MCP Server initializes WebSocket support through the server module:

   ```python
   # In server.py
   def initialize_websockets(self):
       self.websocket_manager = WebSocketManager()
       
       # Register WebSocket routes
       self.websocket_routes = {
           "/ws": self.handle_general_websocket,
           "/ws/notifications": self.handle_notification_websocket,
           "/ws/webrtc": self.handle_webrtc_websocket
       }
   ```

2. The client connects to specific WebSocket endpoints:

   ```python
   # Client-side WebSocket connection example
   async def connect_to_notifications(mcp_url):
       async with websockets.connect(f"ws://{mcp_url}/ws/notifications") as websocket:
           # Subscribe to specific notification types
           await websocket.send(json.dumps({
               "action": "subscribe",
               "notification_types": ["content_added", "content_removed", "transfer_progress"]
           }))
           
           # Receive notifications
           async for message in websocket:
               notification = json.loads(message)
               print(f"Received notification: {notification['type']}")
               # Process notification...
   ```

### Notification Types

The system includes various notification types:

1. **Content Operations**:
   - CONTENT_ADDED: New content was added to IPFS
   - CONTENT_REMOVED: Content was removed or unpinned
   - PIN_STATUS_CHANGED: Content pin status was updated

2. **Transfer Status**:
   - TRANSFER_STARTED: Data transfer has begun
   - TRANSFER_PROGRESS: Progress update on ongoing transfer
   - TRANSFER_COMPLETED: Transfer has finished successfully
   - TRANSFER_FAILED: Transfer encountered an error

3. **WebRTC Events**:
   - WEBRTC_OFFER: New WebRTC offer is available
   - WEBRTC_CONNECTED: WebRTC connection established
   - WEBRTC_ERROR: Error in WebRTC connection
   - WEBRTC_QUALITY_CHANGED: Streaming quality adjusted

## libp2p Communication

libp2p is a modular network stack that enables peer-to-peer applications, providing direct communication between nodes without centralized servers.

### Key Components

1. **IPFSLibp2pPeer**: Core class for libp2p communication
2. **PeerDiscovery**: Mechanisms for finding peers on the network
3. **ProtocolHandlers**: Custom protocol implementations for specific communication needs
4. **ContentRouting**: DHT-based content discovery and routing

### Setup Process

1. The MCP Server initializes libp2p support:

   ```python
   # Initialize libp2p peer
   def initialize_libp2p(self):
       """Initialize libp2p peer for direct P2P communication."""
       try:
           from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
           
           # Create libp2p peer with appropriate role
           self.libp2p_peer = IPFSLibp2pPeer(
               role=self.role,
               bootstrap_peers=self.config.get("bootstrap_peers", [])
           )
           
           # Start discovery
           self.libp2p_peer.start_discovery()
           
           # Register protocol handlers
           self.libp2p_peer.register_protocol_handler(
               "/ipfs-kit/mcp/1.0.0",
               self.handle_mcp_protocol
           )
           
           logger.info(f"libp2p peer initialized with ID: {self.libp2p_peer.get_id()}")
           return True
       except ImportError:
           logger.info("libp2p support not available. P2P functionality will be disabled.")
           self.libp2p_peer = None
           return False
   ```

2. Clients connect using matching protocol identifiers:

   ```python
   # Client-side libp2p connection example
   async def connect_to_mcp_libp2p(peer_id, multiaddr):
       # Create libp2p host
       from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
       
       peer = IPFSLibp2pPeer(role="leecher")
       
       # Connect to MCP server peer
       await peer.connect_to_peer(peer_id, multiaddr)
       
       # Open stream with specific protocol
       stream = await peer.new_stream(peer_id, "/ipfs-kit/mcp/1.0.0")
       
       # Send request
       request = {
           "action": "get_content",
           "cid": "QmSomeContentIdentifier"
       }
       await stream.write(json.dumps(request).encode())
       
       # Read response
       response_data = await stream.read(10 * 1024 * 1024)  # 10MB max
       response = json.loads(response_data.decode())
       
       # Process response...
       
       # Close the stream when done
       await stream.close()
   ```

### Protocol Handlers

Custom protocol handlers enable specific functionality:

1. **Content Exchange Protocol**:
   - `/ipfs-kit/content/1.0.0`: For direct content transfer
   - Enables efficient transfer of content chunks

2. **Metadata Protocol**:
   - `/ipfs-kit/metadata/1.0.0`: For exchanging content metadata
   - Allows querying and updating content information

3. **MCP Communication Protocol**:
   - `/ipfs-kit/mcp/1.0.0`: For MCP-specific operations
   - Enables remote API access and command execution

## Integration Patterns

The system uses several integration patterns to combine these communication methods:

### 1. Protocol Selection Based on Content Type

```python
def select_protocol(content_type, size, priority):
    """Select the optimal protocol based on content characteristics."""
    if content_type.startswith("video/") or content_type.startswith("audio/"):
        # Streaming media content - use WebRTC
        return "webrtc"
    elif size < 1024 * 1024 and priority == "high":
        # Small, high-priority content - use WebSockets for immediate delivery
        return "websocket"
    else:
        # Default to libp2p for most content transfers
        return "libp2p"
```

### 2. Fallback Chain

The system implements protocol fallbacks for reliability:

```python
async def transfer_content(cid, target_peer):
    """Transfer content with protocol fallback chain."""
    # Try libp2p first (most efficient)
    try:
        success = await transfer_via_libp2p(cid, target_peer)
        if success:
            return True
    except Exception as e:
        logger.warning(f"libp2p transfer failed: {e}")
    
    # Fall back to WebSockets
    try:
        success = await transfer_via_websocket(cid, target_peer)
        if success:
            return True
    except Exception as e:
        logger.warning(f"WebSocket transfer failed: {e}")
    
    # Final fallback to HTTP API
    try:
        success = await transfer_via_http(cid, target_peer)
        if success:
            return True
    except Exception as e:
        logger.error(f"HTTP transfer failed: {e}")
    
    # All methods failed
    return False
```

### 3. Hybrid Approaches

For complex operations, the system can use multiple protocols simultaneously:

```python
async def stream_with_metadata(cid, peer_id):
    """Stream content while simultaneously transferring metadata."""
    # Start WebRTC stream for the content
    webrtc_task = asyncio.create_task(
        start_webrtc_stream(cid, peer_id)
    )
    
    # Simultaneously send metadata via WebSockets
    metadata_task = asyncio.create_task(
        send_metadata_via_websocket(cid, peer_id)
    )
    
    # Wait for both operations to complete
    await asyncio.gather(webrtc_task, metadata_task)
```

## Testing Communication

To test communication between MCP Server and ipfs_kit_py:

1. **Start the MCP Server**:
   ```bash
   python -m ipfs_kit_py.mcp.server --debug
   ```

2. **Connect with ipfs_kit_py client**:
   ```python
   from ipfs_kit_py.high_level_api import IPFSSimpleAPI
   
   # Connect to MCP server
   api = IPFSSimpleAPI(mcp_url="http://localhost:8000")
   
   # Test WebSocket notifications
   await api.subscribe_to_notifications(callback=print)
   
   # Test WebRTC streaming
   stream = await api.stream_content("QmTestContent")
   
   # Test libp2p direct transfer
   result = await api.transfer_via_libp2p("QmTestContent", "target_peer_id")
   ```

3. **Verify connectivity with diagnostic tool**:
   ```bash
   python -m ipfs_kit_py.tools.check_connectivity --all
   ```

## Implementation Status

| Protocol | MCP Server Support | ipfs_kit_py Support | Status |
|----------|-------------------|---------------------|--------|
| WebRTC   | ✅ Implemented     | ✅ Implemented       | Working |
| WebSockets | ✅ Implemented   | ✅ Implemented       | Working |
| libp2p   | ✅ Implemented     | ✅ Implemented       | Working |

## Future Improvements

1. **WebRTC Enhancements**:
   - Add end-to-end encryption for secure media streaming
   - Implement multi-track support for simultaneous streams
   - Add WebRTC DataChannel for non-media content

2. **WebSocket Optimizations**:
   - Implement message compression for bandwidth efficiency
   - Add automatic reconnection with session resumption
   - Enhance event filtering for more targeted notifications

3. **libp2p Extensions**:
   - Add content-based routing for more efficient peer discovery
   - Implement NAT traversal improvements for better connectivity
   - Add reputation system for peer quality assessment
# Real-time Streaming Guide

This guide covers the real-time streaming capabilities of IPFS Kit, including WebSocket streaming, WebRTC media streaming, and the real-time notification system.

## Table of Contents

1. [Introduction](#introduction)
2. [Streaming Architectures](#streaming-architectures)
   - [WebSocket Streaming](#websocket-streaming)
   - [WebRTC Media Streaming](#webrtc-media-streaming)
   - [Real-time Notifications](#real-time-notifications)
3. [WebSocket Streaming Implementation](#websocket-streaming-implementation)
   - [Streaming FROM IPFS](#streaming-from-ipfs)
   - [Streaming TO IPFS](#streaming-to-ipfs)
   - [Bidirectional Streaming](#bidirectional-streaming)
   - [Server-Sent Events (SSE)](#server-sent-events)
   - [HTTP Range Requests](#http-range-requests)
4. [WebRTC Media Streaming](#webrtc-media-streaming-implementation)
   - [Media Stream Tracks](#media-stream-tracks)
   - [Peer Connections](#peer-connections)
   - [Signaling Protocol](#signaling-protocol)
   - [ICE Candidates and NAT Traversal](#ice-candidates-and-nat-traversal)
   - [Quality Adaptation](#quality-adaptation)
5. [Real-time Notification System](#real-time-notification-system)
   - [Notification Types](#notification-types)
   - [Subscription Management](#subscription-management)
   - [Filtering Notifications](#filtering-notifications)
   - [Event History](#event-history)
6. [Integration Patterns](#integration-patterns)
   - [Combining Streaming with Notifications](#combining-streaming-with-notifications)
   - [Dashboard Integration](#dashboard-integration)
   - [Mobile Integration](#mobile-integration)
   - [Desktop Application Integration](#desktop-application-integration)
7. [Performance Considerations](#performance-considerations)
   - [Adaptive Bitrate Streaming](#adaptive-bitrate-streaming)
   - [Buffer Management](#buffer-management)
   - [Network Optimization](#network-optimization)
8. [Security Best Practices](#security-best-practices)
   - [Authentication for Streaming](#authentication-for-streaming)
   - [Authorization for Notifications](#authorization-for-notifications)
   - [Encryption Considerations](#encryption-considerations)
9. [Practical Use Cases](#practical-use-cases)
   - [Video Streaming](#video-streaming)
   - [Live Data Monitoring](#live-data-monitoring)
   - [Distributed Processing Updates](#distributed-processing-updates)
10. [Troubleshooting](#troubleshooting)
    - [Connection Issues](#connection-issues)
    - [Streaming Performance](#streaming-performance)
    - [Common Errors](#common-errors)

## Introduction

IPFS Kit provides comprehensive real-time streaming capabilities that enable you to stream content both TO and FROM IPFS with high efficiency and low latency. These capabilities include:

1. **WebSocket Streaming**: Bidirectional communication for streaming content to and from IPFS using the WebSocket protocol.
2. **WebRTC Media Streaming**: Peer-to-peer media streaming directly from IPFS content, optimized for audio and video.
3. **Real-time Notification System**: Event-driven notification system that provides real-time updates on system events, streaming status, and content changes.

These capabilities allow you to build real-time applications that leverage IPFS's distributed architecture, such as:

- Live video streaming from IPFS content
- Real-time dashboards and monitoring tools
- Interactive collaborative applications
- Progressive content loading for large files
- Push notifications for system events and status changes

This guide covers the technical implementation, usage patterns, and best practices for each of these streaming capabilities.

## Streaming Architectures

IPFS Kit implements multiple streaming architectures to accommodate different use cases and requirements.

### WebSocket Streaming

WebSocket streaming provides a persistent, bidirectional communication channel between clients and the IPFS Kit server. This architecture is optimized for general-purpose data streaming and allows for:

- **Full-duplex Communication**: Simultaneous data transfer in both directions
- **Low-latency Updates**: Real-time data transmission with minimal overhead
- **Protocol Efficiency**: Reduced header overhead compared to HTTP polling
- **Long-lived Connections**: Persistent connections that avoid repeated handshakes

The WebSocket streaming architecture in IPFS Kit uses a tiered approach:

1. **FastAPI WebSocket Endpoints**: Server-side endpoints that handle WebSocket connections
2. **Streaming Handlers**: Specialized handlers for different streaming operations
3. **Content Streaming**: Efficient content transfer from IPFS sources
4. **Progress Monitoring**: Real-time status updates during transfers

![WebSocket Streaming Architecture](./images/websocket_streaming_architecture.png)

### WebRTC Media Streaming

WebRTC (Web Real-Time Communication) provides peer-to-peer media streaming capabilities optimized for audio and video content. This architecture enables:

- **Direct Peer-to-Peer Communication**: Reduced server load and latency
- **NAT Traversal**: Works across firewalls and network address translators
- **Adaptive Bitrate**: Dynamic quality adjustment based on network conditions
- **Multiple Media Tracks**: Support for audio, video, and data channels
- **Media Processing**: Built-in capabilities for encoding, decoding, and processing

The WebRTC architecture in IPFS Kit consists of:

1. **WebRTC Signaling**: WebSocket-based signaling for connection establishment
2. **Media Stream Tracks**: IPFS content delivered as media tracks
3. **Peer Connection Management**: Efficient management of WebRTC connections
4. **Quality Adaptation**: Dynamic quality adjustment based on network conditions

![WebRTC Streaming Architecture](./images/webrtc_streaming_architecture.png)

### Real-time Notifications

The real-time notification system provides an event-driven architecture for system status updates and events. Key features include:

- **Publish-Subscribe Model**: Clients subscribe to specific notification types
- **Filtered Notifications**: Clients receive only events they're interested in
- **Low-overhead Updates**: Lightweight event payloads for minimal bandwidth usage
- **Persistent Connections**: WebSocket-based for immediate delivery

The notification system architecture consists of:

1. **Notification Manager**: Central component for managing notifications
2. **WebSocket Endpoint**: Connection point for clients
3. **Subscription Registry**: Tracks which clients are subscribed to which notifications
4. **Event Emitters**: Various components that generate notification events

![Notification System Architecture](./images/notification_system_architecture.png)

## WebSocket Streaming Implementation

IPFS Kit implements WebSocket streaming using FastAPI's WebSocket support for efficient, bidirectional communication. This enables streaming content both to and from IPFS with minimal latency.

### Streaming FROM IPFS

To stream content FROM IPFS to clients, IPFS Kit provides a WebSocket endpoint that retrieves content from IPFS and streams it to connected clients in chunks. This approach allows for efficient streaming of large files without loading the entire content into memory.

```python
@app.websocket("/ws/stream/{cid}")
async def websocket_stream(websocket: WebSocket, cid: str):
    """Stream content from IPFS to the client via WebSocket."""
    await websocket.accept()
    
    try:
        # Initialize stream with progress tracking
        stream = IPFSContentStream(ipfs_api, cid)
        
        # Send metadata about the content
        metadata = await stream.get_metadata()
        await websocket.send_json(metadata)
        
        # Stream content in chunks
        async for chunk in stream.iter_chunks(chunk_size=65536):  # 64KB chunks
            await websocket.send_bytes(chunk)
            
    except Exception as e:
        # Send error message
        await websocket.send_json({
            "error": str(e),
            "type": "error"
        })
    finally:
        # Ensure resources are cleaned up
        await stream.close()
```

The `IPFSContentStream` class handles the actual streaming from IPFS, including:

- Retrieving content from IPFS in efficient chunks
- Managing memory usage during streaming
- Providing progress updates during streaming
- Handling errors and interruptions gracefully

### Streaming TO IPFS

To stream content TO IPFS from clients, IPFS Kit provides a WebSocket endpoint that accepts chunks of data from clients and adds them to IPFS incrementally. This allows for uploading large files efficiently without requiring the entire file to be loaded into memory.

```python
@app.websocket("/ws/upload")
async def websocket_upload(websocket: WebSocket):
    """Stream content from the client to IPFS via WebSocket."""
    await websocket.accept()
    
    try:
        # Receive metadata about the upload
        metadata = await websocket.receive_json()
        filename = metadata.get("filename", "unnamed")
        
        # Initialize upload handler
        upload_handler = IPFSUploadHandler(ipfs_api)
        
        # Process chunks as they arrive
        while True:
            chunk = await websocket.receive_bytes()
            if not chunk:
                break  # End of stream
                
            # Add chunk to IPFS
            await upload_handler.add_chunk(chunk)
            
            # Send progress update
            progress = upload_handler.get_progress()
            await websocket.send_json(progress)
        
        # Finalize the upload
        result = await upload_handler.finalize()
        
        # Send final result with CID
        await websocket.send_json({
            "success": True,
            "cid": result["cid"],
            "size": result["size"]
        })
        
    except Exception as e:
        # Send error message
        await websocket.send_json({
            "error": str(e),
            "type": "error"
        })
```

The `IPFSUploadHandler` class manages the incremental upload process, including:

- Buffering and adding content chunks efficiently
- Building a complete DAG from individual chunks
- Computing the final CID for the complete content
- Providing progress updates during upload

### Bidirectional Streaming

IPFS Kit also supports bidirectional streaming, which allows simultaneous transfer of data in both directions over a single WebSocket connection. This is useful for interactive applications that need to both send and receive data in real-time.

```python
@app.websocket("/ws/bidirectional")
async def websocket_bidirectional(websocket: WebSocket):
    """Bidirectional streaming between client and IPFS."""
    await websocket.accept()
    
    # Set up concurrent tasks for sending and receiving
    receive_task = asyncio.create_task(handle_incoming(websocket))
    send_task = asyncio.create_task(handle_outgoing(websocket))
    
    # Wait for either task to complete
    done, pending = await asyncio.wait(
        [receive_task, send_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # Cancel the remaining task
    for task in pending:
        task.cancel()
```

This approach uses `asyncio` tasks to handle sending and receiving concurrently, enabling true bidirectional communication.

### Server-Sent Events (SSE)

For simpler use cases where only server-to-client streaming is needed, IPFS Kit also supports Server-Sent Events (SSE) as a lightweight alternative to WebSockets.

```python
@app.get("/sse/stream/{cid}")
async def sse_stream(cid: str, request: Request):
    """Stream content from IPFS using Server-Sent Events."""
    # Create event source response
    async def event_generator():
        # Initialize stream
        stream = IPFSContentStream(ipfs_api, cid)
        
        # Send metadata
        metadata = await stream.get_metadata()
        yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"
        
        # Stream content in chunks
        try:
            async for chunk in stream.iter_chunks(chunk_size=65536):
                # Encode chunk as base64 for text transport
                chunk_b64 = base64.b64encode(chunk).decode()
                yield f"event: chunk\ndata: {chunk_b64}\n\n"
                
            # Signal completion
            yield f"event: complete\ndata: {json.dumps({'success': True})}\n\n"
            
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            await stream.close()
    
    return EventSourceResponse(event_generator())
```

### HTTP Range Requests

For streaming media content to browsers and players that support seeking, IPFS Kit provides HTTP Range request support. This allows clients to request specific portions of content, which is essential for video playback that supports seeking.

```python
@app.get("/ipfs/{cid}")
async def get_ipfs_content(cid: str, request: Request, response: Response):
    """Serve IPFS content with support for HTTP Range requests."""
    # Get content metadata
    metadata = await ipfs_api.get_metadata(cid)
    content_length = metadata.get("size", 0)
    content_type = metadata.get("mime_type", "application/octet-stream")
    
    # Set content headers
    response.headers["Content-Type"] = content_type
    response.headers["Accept-Ranges"] = "bytes"
    
    # Check for Range header
    range_header = request.headers.get("Range")
    if range_header:
        # Parse range header
        start, end = parse_range_header(range_header, content_length)
        
        # Set partial content status and headers
        response.status_code = 206
        response.headers["Content-Range"] = f"bytes {start}-{end}/{content_length}"
        response.headers["Content-Length"] = str(end - start + 1)
        
        # Stream the requested range
        return StreamingResponse(
            ipfs_api.cat_range(cid, start, end - start + 1),
            media_type=content_type
        )
    else:
        # Stream the full content
        response.headers["Content-Length"] = str(content_length)
        return StreamingResponse(
            ipfs_api.cat(cid),
            media_type=content_type
        )
```

This implementation supports standard HTTP Range requests as specified in RFC 7233, allowing for efficient seeking in media content.

## WebRTC Media Streaming Implementation

IPFS Kit implements WebRTC streaming to enable peer-to-peer media streaming directly from IPFS content. This is particularly useful for low-latency streaming of audio and video content.

### Media Stream Tracks

The core of WebRTC streaming is the `IPFSMediaStreamTrack` class, which extends the standard `MediaStreamTrack` from the aiortc library. This class provides a bridge between IPFS content and the WebRTC stack.

```python
class IPFSMediaStreamTrack(MediaStreamTrack):
    """MediaStreamTrack that sources content directly from IPFS."""
    
    kind = "video"  # Default kind, can be changed to "audio"
    
    def __init__(self, track=None, ipfs_api=None, cid=None, kind="video", frame_rate=30):
        """
        Initialize an IPFS media stream track.
        
        Args:
            track: Optional source track to relay
            ipfs_api: IPFS API instance for content retrieval
            cid: Content identifier for the media in IPFS
            kind: Track kind ("audio" or "video")
            frame_rate: Target frame rate for video tracks
        """
        super().__init__()
        self.track = track
        self.ipfs_api = ipfs_api
        self.cid = cid
        self.kind = kind
        self.frame_rate = frame_rate
        self._buffer = asyncio.Queue(maxsize=30)  # Frame buffer
        self._task = None
        self._start_time = None
        self._frame_count = 0
        self._content = None
        self._content_loaded = False
        self._stopped = False
        self._decoder = None
        
        # For adaptive bitrate control
        self._last_timestamp = time.time()
        self._stats = {
            "frames_sent": 0,
            "frames_dropped": 0,
            "bitrate": 0,
            "latency": 0,
        }
        
        # Start loading content if CID is provided
        if self.ipfs_api and self.cid:
            self._task = asyncio.create_task(self._load_content())
```

The key methods of `IPFSMediaStreamTrack` include:

- `_load_content()`: Loads media content from IPFS and prepares it for streaming
- `_generate_frames()`: Produces frames from the loaded content at the target frame rate
- `recv()`: Provides the next frame to the WebRTC stack
- `stop()`: Cleans up resources when streaming ends

### Peer Connections

The `WebRTCStreamingManager` class manages WebRTC peer connections for streaming IPFS content:

```python
class WebRTCStreamingManager:
    """Manages WebRTC connections for IPFS content streaming."""
    
    def __init__(self, ipfs_api):
        """
        Initialize the WebRTC streaming manager.
        
        Args:
            ipfs_api: IPFS API instance for content access
        """
        self.ipfs_api = ipfs_api
        self.peer_connections = {}
        self.media_relays = {}
        self.tracks = {}
        self.connection_stats = {}
    
    async def create_offer(self, cid=None, kind="video", frame_rate=30):
        """
        Create a WebRTC offer for streaming IPFS content.
        
        Args:
            cid: Content identifier for the media in IPFS
            kind: Track kind ("audio" or "video")
            frame_rate: Target frame rate for video tracks
            
        Returns:
            Dict with SDP offer and peer connection ID
        """
        # Create peer connection, media track, etc.
        # Set up event handlers for connection state changes
        # Generate and return offer
```

Key methods of the `WebRTCStreamingManager` include:

- `create_offer()`: Creates a new WebRTC peer connection and generates an offer
- `handle_answer()`: Processes an answer from the client to establish the connection
- `handle_candidate()`: Adds ICE candidates from the client for NAT traversal
- `add_content_track()`: Adds a new media track to an existing peer connection
- `close_peer_connection()`: Cleans up a peer connection when it's no longer needed

### Signaling Protocol

WebRTC requires a signaling mechanism to exchange session descriptions and ICE candidates between peers. IPFS Kit implements a WebSocket-based signaling protocol:

```python
async def handle_webrtc_signaling(websocket, ipfs_api):
    """
    Handle WebRTC signaling via WebSocket for streaming IPFS content.
    
    Args:
        websocket: WebSocket connection
        ipfs_api: IPFS API instance
    """
    # Create WebRTC manager
    manager = WebRTCStreamingManager(ipfs_api)
    
    try:
        # Accept the connection
        await websocket.accept()
        
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "message": "IPFS WebRTC signaling server connected",
            "capabilities": ["video", "audio"]
        })
        
        # Handle signaling messages
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            
            if msg_type == "offer_request":
                # Handle offer request
                # ...
            elif msg_type == "answer":
                # Handle answer
                # ...
            elif msg_type == "candidate":
                # Handle ICE candidate
                # ...
            # Handle other message types...
    
    finally:
        # Clean up all connections
        await manager.close_all_connections()
```

The signaling protocol includes messages for:

1. Offer requests: Client asks to start a new WebRTC session
2. Answers: Client responds to an offer from the server
3. ICE candidates: Exchange of network connectivity information
4. Track management: Adding or removing media tracks
5. Connection management: Closing connections or querying status

### ICE Candidates and NAT Traversal

WebRTC uses Interactive Connectivity Establishment (ICE) to traverse Network Address Translators (NATs) and firewalls. IPFS Kit implements ICE candidate collection and exchange:

```python
@pc.on("icecandidate")
def on_icecandidate(candidate):
    """Handle ICE candidate generation."""
    if candidate:
        # Send candidate to the other peer via signaling channel
        websocket.send_json({
            "type": "candidate",
            "pc_id": pc_id,
            "candidate": candidate.candidate,
            "sdpMid": candidate.sdpMid,
            "sdpMLineIndex": candidate.sdpMLineIndex
        })
```

ICE candidates are collected and exchanged through the signaling channel to establish the most efficient peer-to-peer connection possible.

### Quality Adaptation

IPFS Kit's WebRTC implementation includes adaptive quality mechanisms that adjust streaming parameters based on network conditions:

```python
# Inside IPFSMediaStreamTrack
async def _generate_frames(self):
    """Generate frames from the loaded content."""
    # For each frame, check buffer state to adapt
    if self._buffer.qsize() > 25:  # Buffer is getting full
        # Drop non-keyframes to reduce load
        if not frame.key_frame:
            self._stats["frames_dropped"] += 1
            continue
    
    # Once per second, compute and adjust bitrate
    now = time.time()
    if now - self._last_bitrate_adjust > 1.0:
        self._adjust_quality_based_on_network()
        self._last_bitrate_adjust = now
```

The quality adaptation includes:

1. **Frame dropping**: When buffers fill up, non-key frames are dropped
2. **Resolution adjustment**: Based on network conditions, resolution can be reduced
3. **Frame rate adaptation**: The frame rate can be adjusted dynamically
4. **Statistical analysis**: Connection statistics drive adaptation decisions

## Real-time Notification System

IPFS Kit's real-time notification system provides event-driven updates about system events, streaming status, and content changes. This system uses WebSockets to deliver notifications to subscribed clients.

### Notification Types

The notification system defines various notification types through an enumeration:

```python
class NotificationType(str, Enum):
    """Types of notifications that can be sent or subscribed to."""
    
    # Content-related events
    CONTENT_ADDED = "content_added"
    CONTENT_RETRIEVED = "content_retrieved"
    CONTENT_REMOVED = "content_removed"
    
    # Pin-related events
    PIN_ADDED = "pin_added"
    PIN_REMOVED = "pin_removed"
    PIN_PROGRESS = "pin_progress"
    PIN_STATUS_CHANGED = "pin_status_changed"
    
    # WebRTC streaming events
    WEBRTC_CONNECTION_CREATED = "webrtc_connection_created"
    WEBRTC_CONNECTION_ESTABLISHED = "webrtc_connection_established"
    WEBRTC_CONNECTION_CLOSED = "webrtc_connection_closed"
    WEBRTC_STREAM_STARTED = "webrtc_stream_started"
    WEBRTC_STREAM_ENDED = "webrtc_stream_ended"
    WEBRTC_QUALITY_CHANGED = "webrtc_quality_changed"
    WEBRTC_ERROR = "webrtc_error"
    
    # System events
    SYSTEM_METRICS = "system_metrics"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_ERROR = "system_error"
    SYSTEM_INFO = "system_info"
    
    # Generic events
    CUSTOM_EVENT = "custom_event"
    ALL_EVENTS = "all_events"  # Special type to subscribe to all events
```

These notification types cover various aspects of the system, allowing clients to subscribe to specific events they're interested in.

### Subscription Management

The `NotificationManager` class handles subscription management for the notification system:

```python
class NotificationManager:
    """Manages WebSocket subscriptions and notifications."""
    
    def __init__(self):
        """Initialize the notification manager."""
        # Maps connection ID to WebSocket and subscriptions
        self.active_connections = {}
        
        # Maps notification types to sets of connection IDs
        self.subscriptions = {}
        
        # Event history for persistent notifications
        self.event_history = []
        self.max_history_size = 1000
        
        # Metrics collection
        self.metrics = {
            "connections_total": 0,
            "active_connections": 0,
            "notifications_sent": 0,
            "subscriptions_by_type": {}
        }
```

Key methods include:

- `connect()`: Register a new WebSocket connection
- `disconnect()`: Unregister a WebSocket connection
- `subscribe()`: Subscribe a connection to specific notification types
- `unsubscribe()`: Unsubscribe from specific notification types
- `notify()`: Send a notification to all subscribed connections
- `notify_all()`: Send a notification to all connected clients

### Filtering Notifications

The notification system supports filtering to allow clients to receive only relevant notifications:

```python
def _passes_filters(self, notification, filters):
    """
    Check if a notification passes the specified filters.
    
    Args:
        notification: The notification to check
        filters: The filters to apply
        
    Returns:
        True if the notification passes the filters, False otherwise
    """
    # If no filters, always pass
    if not filters:
        return True
    
    # Check each filter
    data = notification.get("data", {})
    
    for key, value in filters.items():
        # Handle nested keys with dot notation (e.g., "data.cid")
        if "." in key:
            parts = key.split(".")
            current = notification
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return False  # Key path doesn't exist
            
            # Compare the value
            if current != value:
                return False
        
        # Direct key in data
        elif key in data and data[key] != value:
            return False
    
    # All filters passed
    return True
```

This filtering mechanism allows clients to specify complex criteria for the notifications they want to receive, reducing noise and focusing on relevant events.

### Event History

The notification system maintains a history of recent events, allowing clients to catch up on missed notifications:

```python
async def get_history(self, limit=50, notification_type=None):
    """
    Get notification history.
    
    Args:
        limit: Maximum number of history items to retrieve
        notification_type: Optional type to filter history
        
    Returns:
        List of historical notification events
    """
    # Filter history based on type if specified
    if notification_type:
        history = [
            event for event in self.event_history
            if event.get("notification_type") == notification_type
        ]
    else:
        history = self.event_history
    
    # Apply limit
    return history[-limit:]
```

This history enables clients to recover after disconnections or get context when first connecting to the system.

## Integration Patterns

IPFS Kit's streaming capabilities can be integrated with various application types using common patterns.

### Combining Streaming with Notifications

A powerful pattern is to combine content streaming with real-time notifications for status updates:

```python
# On the server side
async def handle_upload(websocket):
    """Handle file upload with notifications."""
    # Accept WebSocket connection
    await websocket.accept()
    
    # Initialize upload handler
    upload_handler = IPFSUploadHandler(ipfs_api)
    
    try:
        # Process chunks
        while True:
            chunk = await websocket.receive_bytes()
            if not chunk:
                break
                
            # Add chunk
            result = await upload_handler.add_chunk(chunk)
            
            # Emit progress notification
            await emit_event(
                NotificationType.CONTENT_ADDED,
                {
                    "bytes_processed": upload_handler.bytes_processed,
                    "total_bytes": upload_handler.total_bytes,
                    "percent": upload_handler.percent_complete
                }
            )
            
        # Finalize upload
        final_result = await upload_handler.finalize()
        
        # Emit completion notification
        await emit_event(
            NotificationType.CONTENT_ADDED,
            {
                "cid": final_result["cid"],
                "size": final_result["size"],
                "complete": True
            }
        )
        
        # Send result to client
        await websocket.send_json(final_result)
        
    except Exception as e:
        # Emit error notification
        await emit_event(
            NotificationType.SYSTEM_ERROR,
            {
                "error": str(e),
                "operation": "upload"
            }
        )
        raise
```

In this pattern, the upload process emits notifications at key points, allowing other system components to react to the progress and completion of the upload.

### Dashboard Integration

The unified dashboard example demonstrates integration of WebRTC streaming and WebSocket notifications:

```python
class UnifiedDashboard:
    """Unified dashboard for WebRTC streaming and WebSocket notifications."""
    
    def __init__(self, api_url="http://localhost:8000"):
        """Initialize the dashboard components."""
        # Set up WebRTC client
        self.webrtc_client = WebRTCClient(api_url)
        
        # Set up notification client
        self.notification_client = NotificationClient(
            api_url=api_url,
            on_notification=self._handle_notification
        )
        
        # Initialize UI components
        self._init_ui()
        
        # Connect to services
        self.connect_services()
    
    def _handle_notification(self, notification):
        """Handle incoming notifications."""
        # Process based on notification type
        notification_type = notification.get("notification_type")
        
        if notification_type.startswith("webrtc_"):
            # Update WebRTC status display
            self._update_webrtc_status(notification)
        elif notification_type.startswith("content_"):
            # Update content status display
            self._update_content_status(notification)
        elif notification_type.startswith("system_"):
            # Update system status display
            self._update_system_status(notification)
```

This integration pattern enables dashboards to provide a complete view of the system's status and activities in real-time.

### Mobile Integration

For mobile applications, a lightweight integration pattern focuses on efficient resource usage:

```javascript
// React Native example
class IPFSStreamingComponent extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      isStreaming: false,
      notificationCount: 0,
      notifications: []
    };
    
    // Setup WebSocket for notifications (lightweight)
    this.notificationSocket = new WebSocket('ws://ipfs.example.com/ws/notifications');
    this.notificationSocket.onmessage = this.handleNotification;
    
    // WebRTC connection (initialized on demand)
    this.rtcConnection = null;
  }
  
  startStreaming = async () => {
    // Initialize WebRTC on demand
    this.rtcConnection = new RTCPeerConnection();
    
    // Set up signaling
    const signaling = new WebSocket('ws://ipfs.example.com/ws/webrtc');
    signaling.onmessage = this.handleSignalingMessage;
    
    // Request stream
    signaling.send(JSON.stringify({
      type: 'offer_request',
      cid: this.props.cid
    }));
    
    this.setState({ isStreaming: true });
  }
  
  stopStreaming = () => {
    // Clean up WebRTC
    if (this.rtcConnection) {
      this.rtcConnection.close();
      this.rtcConnection = null;
    }
    
    this.setState({ isStreaming: false });
  }
  
  handleNotification = (event) => {
    const notification = JSON.parse(event.data);
    this.setState(state => ({
      notificationCount: state.notificationCount + 1,
      notifications: [notification, ...state.notifications].slice(0, 20)
    }));
  }
  
  render() {
    // UI implementation
  }
}
```

This pattern conserves mobile resources by:
1. Maintaining a lightweight notification connection
2. Initializing WebRTC only when actively streaming
3. Cleaning up resources when not in use

### Desktop Application Integration

For desktop applications, a more persistent integration pattern can be used:

```python
# PyQt example
class IPFSDesktopApp(QMainWindow):
    """Desktop application with IPFS streaming integration."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPFS Streaming Desktop")
        
        # Initialize UI
        self.init_ui()
        
        # Set up IPFS Kit clients
        self.ipfs_api = IPFSSimpleAPI()
        self.webrtc_client = WebRTCClient(on_frame=self.handle_frame)
        self.notification_client = NotificationClient(on_notification=self.handle_notification)
        
        # Connect signals and slots
        self.streamButton.clicked.connect(self.toggle_streaming)
        
        # Start event loop for async operations
        self.async_loop = asyncio.new_event_loop()
        self.async_thread = QThread()
        self.async_thread.run = lambda: asyncio.set_event_loop(self.async_loop)
        self.async_thread.start()
        
        # Connect services
        asyncio.run_coroutine_threadsafe(self.connect_services(), self.async_loop)
    
    async def connect_services(self):
        """Connect to IPFS services."""
        await self.notification_client.connect()
        await self.webrtc_client.connect()
        
        # Subscribe to relevant notifications
        await self.notification_client.subscribe([
            "webrtc_connection_established",
            "webrtc_stream_started",
            "webrtc_quality_changed",
            "system_error"
        ])
    
    def handle_frame(self, frame):
        """Handle received video frame."""
        # Convert frame to QImage and display
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        self.videoLabel.setPixmap(pixmap)
    
    def handle_notification(self, notification):
        """Handle incoming notification."""
        # Process notification and update UI
        notification_type = notification.get("notification_type")
        self.statusBar().showMessage(f"Event: {notification_type}")
        
        # Add to notification list
        item = QListWidgetItem(f"{notification_type}: {notification.get('data', {})}")
        self.notificationList.insertItem(0, item)
        
        # Keep list at reasonable size
        while self.notificationList.count() > 100:
            self.notificationList.takeItem(self.notificationList.count() - 1)
    
    def toggle_streaming(self):
        """Start or stop streaming."""
        if self.streamButton.text() == "Start Streaming":
            # Get CID from input field
            cid = self.cidInput.text()
            if not cid:
                QMessageBox.warning(self, "Warning", "Please enter a valid CID")
                return
            
            # Start streaming
            asyncio.run_coroutine_threadsafe(
                self.webrtc_client.request_stream(cid),
                self.async_loop
            )
            self.streamButton.setText("Stop Streaming")
        else:
            # Stop streaming
            asyncio.run_coroutine_threadsafe(
                self.webrtc_client.close_all_connections(),
                self.async_loop
            )
            self.streamButton.setText("Start Streaming")
```

This pattern uses threads to manage asynchronous operations in a synchronous GUI framework, maintaining responsive UI while handling streaming and notifications.

## Performance Considerations

To achieve optimal performance with IPFS Kit's streaming capabilities, several key considerations should be addressed.

### Adaptive Bitrate Streaming

For WebRTC media streaming, implementing adaptive bitrate is essential for optimal performance across varying network conditions:

```python
class AdaptiveBitrateController:
    """Controls adaptive bitrate for WebRTC streaming."""
    
    def __init__(self, track):
        """Initialize with a media track."""
        self.track = track
        self.quality_levels = [
            {"height": 1080, "bitrate": 4_500_000},
            {"height": 720, "bitrate": 2_500_000},
            {"height": 480, "bitrate": 1_000_000},
            {"height": 360, "bitrate": 500_000},
            {"height": 240, "bitrate": 250_000},
        ]
        self.current_level_index = 2  # Start at medium quality
        self.last_adaptation = time.time()
        self.sample_window = []  # For statistics
    
    def add_sample(self, stats):
        """Add a connection quality sample."""
        self.sample_window.append({
            "timestamp": time.time(),
            "rtt": stats.get("rtt", 0),
            "packet_loss": stats.get("packet_loss", 0),
            "jitter": stats.get("jitter", 0),
            "bandwidth_estimate": stats.get("bandwidth_estimate", 0)
        })
        
        # Keep window at reasonable size
        if len(self.sample_window) > 30:
            self.sample_window = self.sample_window[-30:]
        
        # Consider adaptation if enough time has passed
        if time.time() - self.last_adaptation > 5.0:  # Every 5 seconds
            self._adapt_quality()
            self.last_adaptation = time.time()
    
    def _adapt_quality(self):
        """Adapt quality based on network conditions."""
        if not self.sample_window:
            return
        
        # Calculate key metrics
        avg_rtt = sum(s["rtt"] for s in self.sample_window) / len(self.sample_window)
        avg_packet_loss = sum(s["packet_loss"] for s in self.sample_window) / len(self.sample_window)
        
        # Simple scoring system for network conditions
        score = 100
        score -= avg_rtt * 10  # Reduce score as RTT increases
        score -= avg_packet_loss * 500  # Heavily penalize packet loss
        
        # Determine quality level based on score
        if score > 80:
            # Network is good, consider increasing quality
            self._increase_quality()
        elif score < 40:
            # Network is poor, reduce quality
            self._decrease_quality()
    
    def _increase_quality(self):
        """Try to increase quality if possible."""
        if self.current_level_index > 0:
            # Move to higher quality
            self.current_level_index -= 1
            self._apply_quality_settings()
    
    def _decrease_quality(self):
        """Decrease quality to improve performance."""
        if self.current_level_index < len(self.quality_levels) - 1:
            # Move to lower quality
            self.current_level_index += 1
            self._apply_quality_settings()
    
    def _apply_quality_settings(self):
        """Apply the current quality settings to the track."""
        settings = self.quality_levels[self.current_level_index]
        # Apply to encoder if track supports it
        if hasattr(self.track, "set_encoding_parameters"):
            self.track.set_encoding_parameters(
                height=settings["height"],
                bitrate=settings["bitrate"]
            )
```

This adaptive bitrate controller adjusts streaming quality based on network conditions, providing the best possible quality that the network can support.

### Buffer Management

Effective buffer management is crucial for smooth streaming with minimal latency:

```python
class StreamBuffer:
    """Manages streaming buffer for optimal performance."""
    
    def __init__(self, target_duration=2.0, max_duration=5.0, min_duration=0.5):
        """
        Initialize buffer manager.
        
        Args:
            target_duration: Target buffer duration in seconds
            max_duration: Maximum buffer duration before throttling
            min_duration: Minimum buffer duration before playback
        """
        self.target_duration = target_duration
        self.max_duration = max_duration
        self.min_duration = min_duration
        self.buffer = asyncio.Queue()
        self.buffer_duration = 0.0
        self.frame_durations = []  # For calculating average frame duration
        self.playback_ready = asyncio.Event()
        self.throttle = asyncio.Event()
        self.throttle.set()  # Start unthrottled
    
    async def add_frame(self, frame):
        """
        Add a frame to the buffer.
        
        Args:
            frame: The frame to add
        """
        # Wait if throttled
        await self.throttle.wait()
        
        # Add frame to buffer
        await self.buffer.put(frame)
        
        # Update buffer duration estimate
        if hasattr(frame, 'time_base') and hasattr(frame, 'pts'):
            frame_duration = frame.time_base * frame.pts
            self.frame_durations.append(frame_duration)
            if len(self.frame_durations) > 30:
                self.frame_durations = self.frame_durations[-30:]
            
            self.buffer_duration = self.buffer.qsize() * (sum(self.frame_durations) / len(self.frame_durations))
        else:
            # Estimate based on queue size
            self.buffer_duration = self.buffer.qsize() / 30.0  # Assume 30fps
        
        # Set playback_ready when buffer reaches minimum duration
        if self.buffer_duration >= self.min_duration and not self.playback_ready.is_set():
            self.playback_ready.set()
        
        # Throttle input if buffer exceeds maximum duration
        if self.buffer_duration > self.max_duration:
            self.throttle.clear()
    
    async def get_frame(self):
        """
        Get a frame from the buffer when available.
        
        Returns:
            The next frame from the buffer
        """
        # Wait until playback is ready
        await self.playback_ready.wait()
        
        # Get frame from buffer
        frame = await self.buffer.get()
        
        # Update buffer duration estimate
        if hasattr(frame, 'time_base') and hasattr(frame, 'pts'):
            frame_duration = frame.time_base * frame.pts
            self.buffer_duration -= frame_duration
        else:
            # Estimate based on queue size
            self.buffer_duration = self.buffer.qsize() / 30.0  # Assume 30fps
        
        # Unthrottle input if buffer drops below target duration
        if self.buffer_duration < self.target_duration and not self.throttle.is_set():
            self.throttle.set()
        
        # Clear playback_ready if buffer is empty
        if self.buffer.empty():
            self.playback_ready.clear()
        
        return frame
```

This buffer manager provides several key features:

1. **Adaptive buffer sizing**: Adjusts based on playback rate
2. **Input throttling**: Prevents buffer overflow
3. **Playback readiness signaling**: Ensures sufficient buffer before playback

### Network Optimization

Network optimization is crucial for efficient streaming, especially in distributed environments:

```python
class NetworkOptimizer:
    """Optimizes network usage for streaming."""
    
    def __init__(self, ipfs_api):
        """Initialize with IPFS API."""
        self.ipfs_api = ipfs_api
        self.peer_latencies = {}  # Peer ID -> latency
        self.preferred_peers = []
        self.max_preferred_peers = 5
    
    async def optimize(self):
        """Perform network optimization."""
        # Get connected peers
        peers = await self.ipfs_api.swarm_peers()
        
        # Measure latency to each peer
        for peer in peers:
            peer_id = peer["peer"]
            latency = await self._measure_peer_latency(peer_id)
            self.peer_latencies[peer_id] = latency
        
        # Sort peers by latency
        sorted_peers = sorted(
            self.peer_latencies.items(),
            key=lambda x: x[1]
        )
        
        # Select preferred peers (lowest latency)
        self.preferred_peers = [p[0] for p in sorted_peers[:self.max_preferred_peers]]
        
        # Optimize connections
        await self._optimize_connections()
    
    async def _measure_peer_latency(self, peer_id):
        """Measure latency to a peer."""
        start_time = time.time()
        try:
            # Try to ping the peer
            result = await self.ipfs_api.ping(peer_id, count=1)
            if "Time" in result:
                return result["Time"] / 1000000.0  # Convert to seconds
            return float("inf")
        except Exception:
            return float("inf")
    
    async def _optimize_connections(self):
        """Optimize network connections."""
        # Protect connections to preferred peers
        for peer_id in self.preferred_peers:
            await self.ipfs_api.swarm_protect(peer_id)
        
        # Configure connection manager
        await self.ipfs_api.config_set(
            "Swarm.ConnMgr.HighWater", 
            len(self.preferred_peers) + 10
        )
        await self.ipfs_api.config_set(
            "Swarm.ConnMgr.LowWater", 
            len(self.preferred_peers)
        )
        
        # Optimize DHT for content retrieval
        if self.preferred_peers:
            # Provide content to preferred peers first
            for peer_id in self.preferred_peers:
                await self.ipfs_api.dht_provide(peer_id)
```

This network optimizer improves streaming performance by:

1. **Peer selection**: Identifying and prioritizing low-latency peers
2. **Connection management**: Protecting important connections
3. **Resource allocation**: Optimizing IPFS configuration for streaming
4. **Content routing**: Improving DHT-based content discovery

## Security Best Practices

Securing real-time streaming and notification systems is crucial for protecting both content and system integrity.

### Authentication for Streaming

WebSocket and WebRTC streams should be authenticated to prevent unauthorized access:

```python
@app.websocket("/ws/stream/{cid}")
async def websocket_stream(websocket: WebSocket, cid: str):
    """Stream content with authentication."""
    # Get authentication token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return
    
    # Verify authentication token
    user = await verify_token(token)
    if not user:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return
    
    # Check if user has permission to access this content
    if not await user_can_access_content(user, cid):
        await websocket.close(code=1008, reason="Unauthorized access")
        return
    
    # Accept the connection
    await websocket.accept()
    
    # Log the access
    logger.info(f"User {user['id']} accessing content {cid} via streaming")
    
    # Continue with normal streaming
    # ...
```

For WebRTC streaming, create secure signaling with authentication:

```python
async def handle_webrtc_signaling(websocket, ipfs_api):
    """Handle WebRTC signaling with authentication."""
    # Get authentication token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        # Reject connection
        return
    
    # Verify token
    user = await verify_token(token)
    if not user:
        # Reject connection
        return
    
    # Accept the connection
    await websocket.accept()
    
    # Associate user with the connection
    connection_id = f"user_{user['id']}_{uuid.uuid4()}"
    
    # Continue with signaling process
    # ...
```

### Authorization for Notifications

Notifications should be filtered based on user permissions:

```python
class AuthorizedNotificationManager(NotificationManager):
    """Notification manager with authorization."""
    
    async def subscribe(self, connection_id, notification_types, filters=None, user=None):
        """Subscribe with authorization check."""
        if not user:
            return {
                "success": False,
                "error": "User not authenticated",
                "subscribed_types": []
            }
        
        # Filter notification types based on user permissions
        authorized_types = []
        unauthorized_types = []
        
        for n_type in notification_types:
            if self._user_can_subscribe(user, n_type):
                authorized_types.append(n_type)
            else:
                unauthorized_types.append(n_type)
        
        # Continue with standard subscription for authorized types
        result = await super().subscribe(connection_id, authorized_types, filters)
        
        # Add information about unauthorized types
        result["unauthorized_types"] = unauthorized_types
        
        return result
    
    def _user_can_subscribe(self, user, notification_type):
        """Check if user can subscribe to notification type."""
        # Implement permission checks
        if notification_type.startswith("system_") and user["role"] != "admin":
            return False
        
        if notification_type.startswith("webrtc_") and not user["permissions"].get("webrtc", False):
            return False
        
        # Add more permission checks as needed
        
        return True
```

### Encryption Considerations

For sensitive content, add transport layer security and content encryption:

```python
async def stream_encrypted_content(websocket, cid, encryption_key):
    """Stream encrypted content to client."""
    # Initialize stream
    stream = IPFSContentStream(ipfs_api, cid)
    
    # Create encryption context
    cipher = AES.new(encryption_key, AES.MODE_GCM)
    nonce = cipher.nonce
    
    # Send nonce to client
    await websocket.send_bytes(nonce)
    
    # Stream encrypted chunks
    async for chunk in stream.iter_chunks(chunk_size=65536):
        # Encrypt chunk
        encrypted_chunk, tag = cipher.encrypt_and_digest(chunk)
        
        # Send encrypted chunk and authentication tag
        await websocket.send_bytes(encrypted_chunk + tag)
```

On the client side, implement corresponding decryption:

```javascript
// Client-side decryption
async function receiveEncryptedStream(socket, decryptionKey) {
  // Receive nonce first
  const nonceBuffer = await receiveNextChunk(socket);
  
  // Create decryption context
  const key = await crypto.subtle.importKey(
    'raw',
    decryptionKey,
    { name: 'AES-GCM' },
    false,
    ['decrypt']
  );
  
  // Process incoming chunks
  while (socket.readyState === WebSocket.OPEN) {
    const encryptedData = await receiveNextChunk(socket);
    if (!encryptedData) break;
    
    // Split data into encrypted content and authentication tag
    const encryptedContent = encryptedData.slice(0, -16);
    const tag = encryptedData.slice(-16);
    
    // Decrypt chunk
    const decryptedData = await crypto.subtle.decrypt(
      {
        name: 'AES-GCM',
        iv: nonceBuffer,
        tagLength: 128,
        additionalData: tag
      },
      key,
      encryptedContent
    );
    
    // Process decrypted data
    processChunk(new Uint8Array(decryptedData));
  }
}
```

## Practical Use Cases

IPFS Kit's streaming capabilities enable a wide range of practical applications.

### Video Streaming

Video streaming from IPFS content demonstrates the power of distributed content delivery:

```javascript
// Client-side implementation
class IPFSVideoPlayer {
  constructor(element, ipfsApiUrl) {
    this.videoElement = element;
    this.ipfsApiUrl = ipfsApiUrl;
    
    // Set up WebRTC connection
    this.pc = new RTCPeerConnection();
    this.pc.ontrack = this.handleTrack.bind(this);
    
    // Set up signaling
    this.signaling = new WebSocket(`ws://${new URL(ipfsApiUrl).host}/ws/webrtc`);
    this.signaling.onmessage = this.handleSignalingMessage.bind(this);
  }
  
  async playCID(cid) {
    // Request stream from server
    this.signaling.send(JSON.stringify({
      type: 'offer_request',
      cid: cid,
      kind: 'video',
      frameRate: 30
    }));
  }
  
  handleTrack(event) {
    // When we receive a track, attach it to the video element
    if (event.track.kind === 'video') {
      this.videoElement.srcObject = new MediaStream([event.track]);
      this.videoElement.play();
    }
  }
  
  handleSignalingMessage(event) {
    const message = JSON.parse(event.data);
    
    if (message.type === 'offer') {
      // Handle offer from server
      this.pc.setRemoteDescription(new RTCSessionDescription({
        type: message.sdpType,
        sdp: message.sdp
      }))
      .then(() => this.pc.createAnswer())
      .then(answer => this.pc.setLocalDescription(answer))
      .then(() => {
        // Send answer back to server
        this.signaling.send(JSON.stringify({
          type: 'answer',
          pc_id: message.pc_id,
          sdp: this.pc.localDescription.sdp,
          sdpType: this.pc.localDescription.type
        }));
      });
    } else if (message.type === 'candidate') {
      // Handle ICE candidate
      this.pc.addIceCandidate({
        candidate: message.candidate,
        sdpMid: message.sdpMid,
        sdpMLineIndex: message.sdpMLineIndex
      });
    }
  }
}

// Usage
const videoElement = document.getElementById('video-player');
const player = new IPFSVideoPlayer(videoElement, 'http://localhost:8000');
player.playCID('QmVideoContentCID');
```

This implementation allows for seamless playback of video content directly from IPFS, with benefits including:

1. **Content addressing**: Immutable references to video content
2. **Distributed delivery**: Multiple sources for popular content
3. **Low latency**: Direct peer-to-peer streaming when possible
4. **Adaptive quality**: Automatic adjustment to network conditions

### Live Data Monitoring

For real-time data monitoring applications, WebSocket notifications enable efficient updates:

```python
async def monitor_system_metrics(websocket):
    """Send real-time system metrics to client."""
    # Accept connection
    await websocket.accept()
    
    try:
        while True:
            # Collect metrics
            metrics = await collect_system_metrics()
            
            # Send metrics to client
            await websocket.send_json({
                "type": "metrics",
                "timestamp": time.time(),
                "metrics": metrics
            })
            
            # Emit notification for monitoring tools
            await emit_event(
                NotificationType.SYSTEM_METRICS,
                metrics
            )
            
            # Wait before sending next update
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
```

This pattern enables real-time dashboards and monitoring tools to track system health and performance.

### Distributed Processing Updates

For long-running distributed processing tasks, notifications provide status updates:

```python
async def process_content(cid, task_id, process_type):
    """Process content with real-time status updates."""
    # Initialize processing
    await emit_event(
        NotificationType.SYSTEM_INFO,
        {
            "message": f"Starting {process_type} processing for {cid}",
            "task_id": task_id,
            "cid": cid,
            "status": "starting"
        }
    )
    
    try:
        # Start processing
        processor = ContentProcessor(ipfs_api, process_type)
        
        # Process with progress updates
        async for progress in processor.process(cid):
            # Emit progress notification
            await emit_event(
                NotificationType.SYSTEM_INFO,
                {
                    "message": f"{process_type} processing in progress",
                    "task_id": task_id,
                    "cid": cid,
                    "status": "processing",
                    "progress": progress
                }
            )
        
        # Get result
        result = await processor.get_result()
        
        # Emit completion notification
        await emit_event(
            NotificationType.SYSTEM_INFO,
            {
                "message": f"{process_type} processing completed",
                "task_id": task_id,
                "cid": cid,
                "status": "completed",
                "result": result
            }
        )
        
        return result
        
    except Exception as e:
        # Emit error notification
        await emit_event(
            NotificationType.SYSTEM_ERROR,
            {
                "message": f"{process_type} processing failed",
                "task_id": task_id,
                "cid": cid,
                "status": "failed",
                "error": str(e)
            }
        )
        raise
```

This pattern enables distributed applications to monitor the progress of content processing across a network of nodes.

## Troubleshooting

Common issues with streaming implementations and their solutions.

### Connection Issues

**Problem**: WebRTC connection establishment fails.

**Common causes**:
1. ICE candidate gathering fails
2. STUN/TURN servers not configured properly
3. Firewall or NAT issues

**Solution**:
```python
# Improve WebRTC connection success rate
@app.websocket("/ws/webrtc")
async def websocket_webrtc(websocket: WebSocket):
    """WebRTC signaling with improved connection success."""
    # Accept connection
    await websocket.accept()
    
    # Create WebRTC manager with enhanced ICE configuration
    manager = WebRTCStreamingManager(
        ipfs_api=ipfs_api,
        ice_servers=[
            {"urls": ["stun:stun.l.google.com:19302"]},
            {
                "urls": ["turn:turn.example.com:3478"],
                "username": "username",
                "credential": "password"
            }
        ],
        ice_transport_policy="all",
        bundle_policy="max-bundle"
    )
    
    # Continue with normal signaling
    # ...
```

**Problem**: WebSocket connection drops frequently.

**Common causes**:
1. Network instability
2. Server timeouts
3. Client-side issues

**Solution**:
```python
@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """WebSocket notifications with improved reliability."""
    # Accept connection
    await websocket.accept()
    
    # Set up ping-pong for connection keepalive
    ping_task = asyncio.create_task(ping_client(websocket))
    
    try:
        # Normal notification handling
        # ...
    finally:
        # Clean up ping task
        ping_task.cancel()

async def ping_client(websocket):
    """Send periodic pings to keep connection alive."""
    while True:
        try:
            await asyncio.sleep(30)  # Every 30 seconds
            await websocket.send_json({"type": "ping", "timestamp": time.time()})
        except Exception:
            break
```

### Streaming Performance

**Problem**: High latency in media streaming.

**Common causes**:
1. Buffer bloat
2. Inefficient content retrieval
3. Codec inefficiencies

**Solution**:
```python
class LowLatencyStreamTrack(IPFSMediaStreamTrack):
    """Media stream track optimized for low latency."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_buffer_size = 2  # Minimal buffering
        self.jitter_buffer_delay = 0.1  # 100ms jitter buffer
        self.prioritize_keyframes = True
    
    async def _generate_frames(self):
        """Generate frames with low-latency optimization."""
        # Skip frames when behind
        current_time = time.time()
        target_time = self._start_time + (self._frame_count / self.frame_rate)
        
        if current_time > target_time + 0.5:  # More than 500ms behind
            # Skip frames to catch up
            frames_to_skip = int((current_time - target_time) * self.frame_rate)
            for _ in range(min(frames_to_skip, 10)):  # Skip at most 10 frames
                next(self._decoder, None)
                self._frame_count += 1
            
            # Update timing
            target_time = self._start_time + (self._frame_count / self.frame_rate)
        
        # Continue with normal frame generation
        # ...
```

**Problem**: WebSocket streams consume too much memory.

**Common causes**:
1. Large chunk sizes
2. Inefficient buffer management
3. Leaking resources

**Solution**:
```python
@app.websocket("/ws/stream/{cid}")
async def websocket_stream(websocket: WebSocket, cid: str):
    """Memory-efficient WebSocket streaming."""
    await websocket.accept()
    
    # Use resource manager for cleanup
    with IPFSResourceManager() as resources:
        # Create streaming pipe with limited buffer
        pipe = resources.create_pipe(
            max_buffer=5 * 1024 * 1024,  # 5MB maximum buffer
            chunk_size=32 * 1024  # 32KB chunks
        )
        
        # Start content fetching in background
        fetch_task = asyncio.create_task(
            fetch_content_to_pipe(cid, pipe)
        )
        
        try:
            # Stream from pipe to client
            async for chunk in pipe:
                await websocket.send_bytes(chunk)
                
                # Release memory explicitly
                del chunk
                
                # Give event loop a chance to run GC
                await asyncio.sleep(0)
                
        except WebSocketDisconnect:
            # Cancel fetch task on disconnect
            fetch_task.cancel()
            
        except Exception as e:
            # Handle errors
            fetch_task.cancel()
            logger.error(f"Streaming error: {e}")
            
            # Send error to client if still connected
            try:
                await websocket.send_json({"error": str(e)})
            except Exception:
                pass
```

### Common Errors

**Problem**: "ICE connection failed" in WebRTC.

**Solution**:
```python
# Implement ICE troubleshooting handler
@pc.on("icecandidateerror")
def on_icecandidateerror(error):
    """Handle ICE candidate errors."""
    logger.error(f"ICE candidate error: {error.errorText} (URL: {error.url}, errorCode: {error.errorCode})")
    
    # Emit diagnostic notification
    emit_event(
        NotificationType.WEBRTC_ERROR,
        {
            "error": "ICE candidate error",
            "error_text": error.errorText,
            "error_code": error.errorCode,
            "url": error.url
        }
    )
    
    # Fallback to relay-only
    if error.errorCode == 701:  # STUN binding error
        logger.info("Falling back to relay-only transport policy")
        pc.setConfiguration({
            "iceTransportPolicy": "relay"
        })
```

**Problem**: "Failed to load content from IPFS" errors in streaming.

**Solution**:
```python
class ResilienceContentStream:
    """Content stream with automatic retries and gateway fallback."""
    
    def __init__(self, ipfs_api, cid, max_retries=3, use_gateways=True):
        """Initialize with resilience features."""
        self.ipfs_api = ipfs_api
        self.cid = cid
        self.max_retries = max_retries
        self.use_gateways = use_gateways
        self.gateways = [
            "https://ipfs.io/ipfs/",
            "https://gateway.pinata.cloud/ipfs/",
            "https://cloudflare-ipfs.com/ipfs/"
        ]
        self.current_source = "local"
        self.retry_count = 0
    
    async def iter_chunks(self, chunk_size=65536):
        """Iterate through content chunks with resilience."""
        while True:
            try:
                if self.current_source == "local":
                    # Try local IPFS node first
                    async for chunk in self._local_iter_chunks(chunk_size):
                        yield chunk
                    break  # Success, exit loop
                else:
                    # Try gateway
                    gateway_url = self.gateways[self.retry_count % len(self.gateways)]
                    async for chunk in self._gateway_iter_chunks(gateway_url, chunk_size):
                        yield chunk
                    break  # Success, exit loop
            except Exception as e:
                self.retry_count += 1
                logger.warning(f"Content retrieval failed: {e}, retry {self.retry_count}/{self.max_retries}")
                
                if self.retry_count >= self.max_retries:
                    if self.current_source == "local" and self.use_gateways:
                        # Switch to gateway source
                        self.current_source = "gateway"
                        self.retry_count = 0
                    else:
                        # All retries and fallbacks failed
                        raise Exception(f"Failed to retrieve content after all retries: {e}")
                
                # Brief delay before retry
                await asyncio.sleep(0.5 * min(self.retry_count, 3))
    
    async def _local_iter_chunks(self, chunk_size):
        """Iterate through chunks from local IPFS node."""
        # Implementation for local node access
        # ...
    
    async def _gateway_iter_chunks(self, gateway_url, chunk_size):
        """Iterate through chunks from IPFS gateway."""
        # Implementation for gateway access
        # ...
```

This resilient content stream automatically falls back to IPFS gateways when local node access fails, providing robust content retrieval for streaming applications.

---

That concludes the comprehensive guide to IPFS Kit's real-time streaming capabilities. These features enable building sophisticated applications that leverage IPFS's distributed architecture with the performance and interactivity of real-time communications.
# WebSocket to JSON-RPC Migration Guide

This guide helps you migrate from WebSocket-based endpoints to the new JSON-RPC methods in the MCP server.

## Overview

All WebSocket functionality has been converted to JSON-RPC methods that use HTTP polling instead of persistent WebSocket connections. This provides better compatibility with load balancers, firewalls, and simplifies client implementation.

## Migration Summary

| Old WebSocket Endpoint | New JSON-RPC Method | Description |
|------------------------|---------------------|-------------|
| `ws://server/ws` | `/api/v0/jsonrpc` | All event management |
| `ws://server/webrtc/signal/{room_id}` | `/api/v0/jsonrpc` | WebRTC signaling |

## Event Management Migration

### Before (WebSocket)

```javascript
// WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
    // Subscribe to events
    ws.send(JSON.stringify({
        type: 'subscribe',
        channel: 'backend'
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received event:', data);
};

// Send ping
ws.send(JSON.stringify({
    type: 'ping',
    data: 'hello'
}));
```

### After (JSON-RPC)

```javascript
// JSON-RPC client
class MCPClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.url = `${baseUrl}/api/v0/jsonrpc`;
        this.requestId = 1;
    }
    
    async call(method, params = {}) {
        const response = await fetch(this.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method,
                params,
                id: this.requestId++
            })
        });
        return response.json();
    }
}

const client = new MCPClient();

// Create session (replaces WebSocket connection)
const sessionResponse = await client.call('events.create_session');
const sessionId = sessionResponse.result.session_id;

// Subscribe to events
await client.call('events.subscribe', {
    session_id: sessionId,
    categories: ['backend']
});

// Poll for events (replaces real-time events)
const eventsResponse = await client.call('events.poll', {
    session_id: sessionId,
    limit: 10
});

// Send ping
const pingResponse = await client.call('events.ping', {
    session_id: sessionId,
    data: 'hello'
});
```

## WebRTC Signaling Migration

### Before (WebSocket)

```javascript
// WebSocket connection for signaling
const ws = new WebSocket(`ws://localhost:8000/webrtc/signal/${roomId}?peer_id=${peerId}`);

ws.onopen = () => {
    console.log('Connected to signaling server');
};

ws.onmessage = (event) => {
    const signal = JSON.parse(event.data);
    handleSignal(signal);
};

// Send offer
ws.send(JSON.stringify({
    type: 'offer',
    sdp: offer.sdp,
    target: targetPeerId
}));
```

### After (JSON-RPC)

```javascript
const client = new MCPClient();

// Join room (replaces WebSocket connection)
const joinResponse = await client.call('webrtc.join_room', {
    room_id: roomId,
    peer_id: peerId,
    metadata: { name: 'My Peer' }
});

// Send signal
await client.call('webrtc.send_signal', {
    room_id: roomId,
    peer_id: peerId,
    target_peer_id: targetPeerId,
    signal_data: {
        type: 'offer',
        sdp: offer.sdp
    }
});

// Poll for incoming signals (replaces real-time signals)
const signalsResponse = await client.call('webrtc.poll_signals', {
    peer_id: peerId
});

signalsResponse.result.signals.forEach(signal => {
    handleSignal(signal);
});
```

## Continuous Polling Pattern

To achieve real-time-like behavior, implement continuous polling:

```javascript
class RealtimeClient {
    constructor(baseUrl) {
        this.client = new MCPClient(baseUrl);
        this.sessionId = null;
        this.polling = false;
    }
    
    async connect() {
        const response = await this.client.call('events.create_session');
        this.sessionId = response.result.session_id;
        return this.sessionId;
    }
    
    async subscribe(categories) {
        return this.client.call('events.subscribe', {
            session_id: this.sessionId,
            categories
        });
    }
    
    startPolling(onEvent, interval = 1000) {
        this.polling = true;
        
        const poll = async () => {
            if (!this.polling) return;
            
            try {
                const response = await this.client.call('events.poll', {
                    session_id: this.sessionId,
                    limit: 50
                });
                
                response.result.events.forEach(onEvent);
            } catch (error) {
                console.error('Polling error:', error);
            }
            
            setTimeout(poll, interval);
        };
        
        poll();
    }
    
    stopPolling() {
        this.polling = false;
    }
    
    async disconnect() {
        this.stopPolling();
        if (this.sessionId) {
            await this.client.call('events.destroy_session', {
                session_id: this.sessionId
            });
        }
    }
}

// Usage
const rtClient = new RealtimeClient();
await rtClient.connect();
await rtClient.subscribe(['backend', 'system']);

rtClient.startPolling((event) => {
    console.log('Event:', event);
});
```

## Method Reference

### Event Management Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `events.create_session` | `session_id?` | Create event session |
| `events.destroy_session` | `session_id` | Destroy event session |
| `events.subscribe` | `session_id, categories` | Subscribe to event categories |
| `events.unsubscribe` | `session_id, categories?` | Unsubscribe from categories |
| `events.poll` | `session_id, since?, limit?` | Poll for events |
| `events.get_session_status` | `session_id` | Get session status |
| `events.ping` | `session_id?, data?` | Health check |
| `events.get_server_stats` | - | Get server statistics |

### WebRTC Signaling Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `webrtc.join_room` | `room_id, peer_id?, metadata?` | Join signaling room |
| `webrtc.leave_room` | `room_id, peer_id` | Leave signaling room |
| `webrtc.send_signal` | `room_id, peer_id, target_peer_id, signal_data` | Send WebRTC signal |
| `webrtc.poll_signals` | `peer_id` | Poll for incoming signals |
| `webrtc.get_room_peers` | `room_id` | Get peers in room |
| `webrtc.get_stats` | - | Get WebRTC statistics |

## Event Categories

Available event categories for subscription:

- `backend` - Backend storage operations (add, delete, etc.)
- `storage` - Storage-related events (alias for backend)
- `migration` - Data migration events
- `streaming` - File streaming progress
- `search` - Search operation events
- `system` - System events (connections, errors, etc.)
- `all` - Subscribe to all categories

## Error Handling

JSON-RPC errors follow the standard JSON-RPC 2.0 error format:

```json
{
    "jsonrpc": "2.0",
    "error": {
        "code": -32603,
        "message": "Internal error"
    },
    "id": 1
}
```

Common error codes:
- `-32700` Parse error (invalid JSON)
- `-32600` Invalid request
- `-32601` Method not found
- `-32602` Invalid params
- `-32603` Internal error

## Performance Considerations

### Polling Interval

Choose polling intervals based on your use case:
- **Real-time applications**: 500ms - 1s
- **Background updates**: 5s - 30s
- **Status monitoring**: 30s - 5min

### Event Limiting

Use the `limit` parameter in `events.poll` to control bandwidth:
- High-frequency polling: limit=10-20
- Low-frequency polling: limit=50-100

### Session Management

- Always destroy sessions when done to free server resources
- Implement session reconnection logic for long-running applications
- Use session status to monitor connection health

## Benefits of JSON-RPC vs WebSockets

1. **Better Load Balancer Support**: Works with any HTTP load balancer
2. **Firewall Friendly**: Uses standard HTTP/HTTPS ports
3. **Simpler Debugging**: Standard HTTP requests/responses
4. **Easier Testing**: Can test with curl or any HTTP client
5. **Better Error Handling**: Standard HTTP status codes + JSON-RPC errors
6. **No Connection Management**: No need to handle connection drops, reconnects
7. **Stateless**: Each request is independent

## Testing Your Migration

Use the provided test script to verify functionality:

```bash
python test_jsonrpc_websocket_replacement.py
```

Or test individual methods:

```bash
# Test event management
curl -X POST http://localhost:8000/api/v0/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "events.create_session",
    "id": 1
  }'

# Test WebRTC signaling
curl -X POST http://localhost:8000/api/v0/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "webrtc.join_room",
    "params": {
      "room_id": "test-room",
      "metadata": {"name": "test-peer"}
    },
    "id": 2
  }'
```

## Need Help?

- Check the examples in `examples_jsonrpc_usage.py`
- Run the test suite: `python test_jsonrpc_websocket_replacement.py`
- Review the comprehensive test results for usage patterns

The migration maintains all original functionality while providing a more robust and compatible architecture.
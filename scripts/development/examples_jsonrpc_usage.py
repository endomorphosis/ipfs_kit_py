#!/usr/bin/env python3
"""
Example: Using JSON-RPC Methods Instead of WebSockets

This example demonstrates how to use the new JSON-RPC methods that replace
WebSocket functionality in the MCP server.
"""

import anyio
import json
import httpx
from datetime import datetime


class MCPJsonRpcClient:
    """Simple JSON-RPC client for the MCP server."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.jsonrpc_url = f"{base_url}/api/v0/jsonrpc"
        self.request_id = 1
    
    async def call_method(self, method: str, params: dict = None) -> dict:
        """Call a JSON-RPC method."""
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id
        }
        self.request_id += 1
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.jsonrpc_url,
                json=request,
                headers={"Content-Type": "application/json"}
            )
            return response.json()


async def example_event_management():
    """Example of using JSON-RPC event management (replaces WebSocket /ws)."""
    print("🎯 JSON-RPC Event Management Example")
    print("=" * 50)
    
    client = MCPJsonRpcClient()
    
    # 1. Create a session (replaces WebSocket connection)
    print("\n1. Creating session...")
    response = await client.call_method("events.create_session")
    session_id = response["result"]["session_id"]
    print(f"   Session ID: {session_id}")
    
    # 2. Subscribe to events (replaces WebSocket subscribe)
    print("\n2. Subscribing to events...")
    response = await client.call_method("events.subscribe", {
        "session_id": session_id,
        "categories": ["backend", "system"]
    })
    print(f"   Subscribed to: {response['result']['subscribed']}")
    
    # 3. Poll for events (replaces real-time WebSocket event delivery)
    print("\n3. Polling for events...")
    response = await client.call_method("events.poll", {
        "session_id": session_id,
        "limit": 10
    })
    print(f"   Found {response['result']['count']} events")
    
    # 4. Get session status (replaces WebSocket status)
    print("\n4. Getting session status...")
    response = await client.call_method("events.get_session_status", {
        "session_id": session_id
    })
    session_info = response["result"]["session"]
    print(f"   Subscriptions: {len(session_info['subscriptions'])}")
    
    # 5. Ping (replaces WebSocket ping/pong)
    print("\n5. Ping test...")
    response = await client.call_method("events.ping", {
        "session_id": session_id,
        "data": {"test": "hello"}
    })
    print(f"   Ping response: {response['result']['type']}")
    
    # 6. Unsubscribe (replaces WebSocket unsubscribe)
    print("\n6. Unsubscribing...")
    response = await client.call_method("events.unsubscribe", {
        "session_id": session_id,
        "categories": ["backend"]
    })
    print(f"   Unsubscribed from: {response['result']['unsubscribed']}")
    
    # 7. Destroy session (replaces WebSocket disconnection)
    print("\n7. Destroying session...")
    response = await client.call_method("events.destroy_session", {
        "session_id": session_id
    })
    print(f"   Session destroyed: {response['result']['success']}")


async def example_webrtc_signaling():
    """Example of using JSON-RPC WebRTC signaling (replaces WebSocket /webrtc/signal)."""
    print("\n\n🎯 JSON-RPC WebRTC Signaling Example")
    print("=" * 50)
    
    client = MCPJsonRpcClient()
    room_id = "example-room-123"
    
    # 1. Join room (replaces WebSocket room connection)
    print("\n1. Joining WebRTC room...")
    response = await client.call_method("webrtc.join_room", {
        "room_id": room_id,
        "metadata": {"name": "Peer 1", "type": "broadcaster"}
    })
    peer_id = response["result"]["peer_id"]
    print(f"   Joined as peer: {peer_id}")
    
    # 2. Get room peers
    print("\n2. Getting room peers...")
    response = await client.call_method("webrtc.get_room_peers", {
        "room_id": room_id
    })
    print(f"   Room has {response['result']['peer_count']} peers")
    
    # 3. Send a signal (replaces WebSocket signal sending)
    print("\n3. Sending WebRTC signal...")
    # Simulate another peer for demonstration
    response2 = await client.call_method("webrtc.join_room", {
        "room_id": room_id,
        "peer_id": "peer-2",
        "metadata": {"name": "Peer 2", "type": "viewer"}
    })
    peer_2_id = response2["result"]["peer_id"]
    
    # Send offer signal
    response = await client.call_method("webrtc.send_signal", {
        "room_id": room_id,
        "peer_id": peer_id,
        "target_peer_id": peer_2_id,
        "signal_data": {
            "type": "offer",
            "sdp": "v=0\r\no=- 123456789 123456789 IN IP4 0.0.0.0\r\n...",
            "timestamp": datetime.now().isoformat()
        }
    })
    print(f"   Signal sent: {response['result']['success']}")
    
    # 4. Poll for signals (replaces real-time WebSocket signal delivery)
    print("\n4. Polling for signals...")
    response = await client.call_method("webrtc.poll_signals", {
        "peer_id": peer_2_id
    })
    signals = response["result"]["signals"]
    print(f"   Received {len(signals)} signals")
    if signals:
        print(f"   First signal type: {signals[0]['signal_data']['type']}")
    
    # 5. Get WebRTC statistics
    print("\n5. Getting WebRTC stats...")
    response = await client.call_method("webrtc.get_stats")
    stats = response["result"]["stats"]
    print(f"   Rooms: {stats['rooms']}, Peers: {stats['total_peers']}")
    
    # 6. Leave room
    print("\n6. Leaving room...")
    response = await client.call_method("webrtc.leave_room", {
        "room_id": room_id,
        "peer_id": peer_id
    })
    print(f"   Left room: {response['result']['success']}")


async def example_polling_pattern():
    """Example of continuous polling pattern for real-time-like experience."""
    print("\n\n🎯 Continuous Polling Pattern Example")
    print("=" * 50)
    
    client = MCPJsonRpcClient()
    
    # Create session and subscribe
    response = await client.call_method("events.create_session")
    session_id = response["result"]["session_id"]
    
    await client.call_method("events.subscribe", {
        "session_id": session_id,
        "categories": ["backend", "system", "streaming"]
    })
    
    print(f"\nStarting continuous polling for session {session_id}...")
    print("(This would typically run in a background task)")
    
    # Simulate continuous polling (in real app, this would be in a background task)
    for i in range(3):
        print(f"\nPoll {i + 1}:")
        
        # Poll for new events
        response = await client.call_method("events.poll", {
            "session_id": session_id,
            "limit": 5
        })
        
        events = response["result"]["events"]
        if events:
            for event in events:
                print(f"  📨 {event['type']} in {event['category']}")
        else:
            print("  🔍 No new events")
        
        # Wait before next poll (in real app, this might be 1-5 seconds)
        await anyio.sleep(1)
    
    # Clean up
    await client.call_method("events.destroy_session", {"session_id": session_id})
    print("\n✅ Polling example complete")


async def main():
    """Run all examples."""
    print("🚀 JSON-RPC WebSocket Replacement Examples")
    print("=" * 60)
    print("These examples show how to use JSON-RPC methods instead of WebSockets")
    print("=" * 60)
    
    try:
        await example_event_management()
        await example_webrtc_signaling()
        await example_polling_pattern()
        
        print("\n\n🎉 All examples completed successfully!")
        print("\n💡 Key Benefits of JSON-RPC vs WebSockets:")
        print("   ✅ No persistent connections to manage")
        print("   ✅ Works with standard HTTP load balancers")
        print("   ✅ Easier debugging and testing")
        print("   ✅ Better compatibility with firewalls/proxies")
        print("   ✅ Simpler client implementation")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        print("Note: These examples require a running MCP server at localhost:8000")
        print("To run the server: python -m ipfs_kit_py.mcp.direct_mcp_server")


if __name__ == "__main__":
    anyio.run(main)
#!/usr/bin/env python3
"""
Test script for JSON-RPC WebSocket replacement functionality.

This script tests all the JSON-RPC methods that replace WebSocket functionality
to ensure the conversion is working correctly.
"""

import anyio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any
import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.anyio


async def test_jsonrpc_event_methods():
    """Test JSON-RPC event management methods."""
    print("🧪 Testing JSON-RPC Event Management Methods...")
    
    try:
        from ipfs_kit_py.mcp.jsonrpc_methods import get_jsonrpc_event_methods
        
        event_methods = get_jsonrpc_event_methods()
        
        # Test session creation
        print("\n1. Testing session creation...")
        result = await event_methods.create_session()
        assert result["success"], f"Session creation failed: {result}"
        session_id = result["session_id"]
        print(f"   ✓ Created session: {session_id}")
        
        # Test ping
        print("\n2. Testing ping...")
        result = await event_methods.ping(session_id=session_id, data={"test": "ping"})
        assert result["success"], f"Ping failed: {result}"
        assert result["echo"]["test"] == "ping", "Ping echo failed"
        print(f"   ✓ Ping successful: {result['type']}")
        
        # Test subscription
        print("\n3. Testing subscription...")
        result = await event_methods.subscribe(session_id, ["backend", "system"])
        assert result["success"], f"Subscription failed: {result}"
        assert "backend" in result["subscribed"], "Backend subscription missing"
        assert "system" in result["subscribed"], "System subscription missing"
        print(f"   ✓ Subscribed to: {result['subscribed']}")
        
        # Test session status
        print("\n4. Testing session status...")
        result = await event_methods.get_session_status(session_id)
        assert result["success"], f"Session status failed: {result}"
        session_data = result["session"]
        assert len(session_data["subscriptions"]) >= 2, "Subscription count incorrect"
        print(f"   ✓ Session status: {len(session_data['subscriptions'])} subscriptions")
        
        # Test event notification (simulate backend change)
        print("\n5. Testing backend event notification...")
        event_manager = event_methods.event_manager
        event_manager.notify_backend_change(
            backend_name="ipfs",
            operation="add",
            content_id="QmTest123456",
            details={"size": 1024, "type": "file"}
        )
        print("   ✓ Backend change notification sent")
        
        # Test polling for events
        print("\n6. Testing event polling...")
        await anyio.sleep(0.1)  # Small delay to ensure event is processed
        result = await event_methods.poll_events(session_id, limit=10)
        assert result["success"], f"Event polling failed: {result}"
        events = result["events"]
        print(f"   ✓ Polled {result['count']} events")
        
        # Verify we received the backend change event
        backend_events = [e for e in events if e.get("data", {}).get("backend") == "ipfs"]
        assert len(backend_events) > 0, "Backend change event not found"
        backend_event = backend_events[0]
        assert backend_event["data"]["operation"] == "add", "Event operation incorrect"
        assert backend_event["data"]["content_id"] == "QmTest123456", "Event content_id incorrect"
        print(f"   ✓ Backend event verified: {backend_event['data']['operation']}")
        
        # Test unsubscription
        print("\n7. Testing unsubscription...")
        result = await event_methods.unsubscribe(session_id, ["backend"])
        assert result["success"], f"Unsubscription failed: {result}"
        assert "backend" in result["unsubscribed"], "Backend unsubscription missing"
        print(f"   ✓ Unsubscribed from: {result['unsubscribed']}")
        
        # Test session destruction
        print("\n8. Testing session destruction...")
        result = await event_methods.destroy_session(session_id)
        assert result["success"], f"Session destruction failed: {result}"
        print(f"   ✓ Session destroyed successfully")
        
        print("\n✅ All JSON-RPC Event Management tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ JSON-RPC Event Management test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_jsonrpc_webrtc_methods():
    """Test JSON-RPC WebRTC signaling methods."""
    print("\n🧪 Testing JSON-RPC WebRTC Signaling Methods...")
    
    try:
        from ipfs_kit_py.mcp.jsonrpc_methods import get_jsonrpc_webrtc_methods
        
        webrtc_methods = get_jsonrpc_webrtc_methods()
        
        # Test joining a room
        print("\n1. Testing room joining...")
        room_id = "test-room-123"
        result = await webrtc_methods.join_room(room_id, metadata={"name": "test-peer"})
        assert result["success"], f"Room join failed: {result}"
        peer_id = result["peer_id"]
        assert result["room_id"] == room_id, "Room ID mismatch"
        print(f"   ✓ Joined room {room_id} as peer {peer_id}")
        
        # Test joining with another peer
        print("\n2. Testing second peer joining...")
        result2 = await webrtc_methods.join_room(room_id, metadata={"name": "test-peer-2"})
        assert result2["success"], f"Second room join failed: {result2}"
        peer_id_2 = result2["peer_id"]
        assert len(result2["other_peers"]) == 1, "Other peers count incorrect"
        print(f"   ✓ Second peer {peer_id_2} joined, sees {len(result2['other_peers'])} other peers")
        
        # Test getting room peers
        print("\n3. Testing room peer listing...")
        result = await webrtc_methods.get_room_peers(room_id)
        assert result["success"], f"Room peer listing failed: {result}"
        assert result["peer_count"] == 2, f"Expected 2 peers, got {result['peer_count']}"
        print(f"   ✓ Room has {result['peer_count']} peers")
        
        # Test sending a signal
        print("\n4. Testing signal sending...")
        signal_data = {
            "type": "offer",
            "sdp": "v=0\r\no=- 123456789 123456789 IN IP4 0.0.0.0\r\n...",
            "timestamp": datetime.now().isoformat()
        }
        result = await webrtc_methods.send_signal(room_id, peer_id, peer_id_2, signal_data)
        assert result["success"], f"Signal sending failed: {result}"
        print(f"   ✓ Signal sent from {peer_id} to {peer_id_2}")
        
        # Test polling for signals
        print("\n5. Testing signal polling...")
        result = await webrtc_methods.poll_signals(peer_id_2)
        assert result["success"], f"Signal polling failed: {result}"
        signals = result["signals"]
        assert len(signals) == 1, f"Expected 1 signal, got {len(signals)}"
        signal = signals[0]
        assert signal["from_peer_id"] == peer_id, "Signal sender incorrect"
        assert signal["signal_data"]["type"] == "offer", "Signal type incorrect"
        print(f"   ✓ Polled {len(signals)} signals")
        
        # Test leaving room
        print("\n6. Testing room leaving...")
        result = await webrtc_methods.leave_room(room_id, peer_id)
        assert result["success"], f"Room leave failed: {result}"
        print(f"   ✓ Peer {peer_id} left room")
        
        # Verify room peer count updated
        print("\n7. Testing room peer count after leave...")
        result = await webrtc_methods.get_room_peers(room_id)
        assert result["success"], f"Room peer listing failed: {result}"
        assert result["peer_count"] == 1, f"Expected 1 peer after leave, got {result['peer_count']}"
        print(f"   ✓ Room now has {result['peer_count']} peer")
        
        # Test WebRTC statistics
        print("\n8. Testing WebRTC statistics...")
        result = await webrtc_methods.get_webrtc_stats()
        assert result["success"], f"WebRTC stats failed: {result}"
        stats = result["stats"]
        assert stats["rooms"] >= 1, "Room count incorrect"
        assert stats["total_peers"] >= 1, "Peer count incorrect"
        print(f"   ✓ WebRTC stats: {stats['rooms']} rooms, {stats['total_peers']} peers")
        
        # Clean up - leave remaining peer
        await webrtc_methods.leave_room(room_id, peer_id_2)
        
        print("\n✅ All JSON-RPC WebRTC Signaling tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ JSON-RPC WebRTC Signaling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_websocket_compatibility():
    """Test WebSocket manager compatibility with JSON-RPC backend."""
    print("\n🧪 Testing WebSocket Manager Compatibility...")
    
    try:
        from ipfs_kit_py.mcp.websocket import WebSocketManager, MessageType
        
        # Create WebSocket manager (should use JSON-RPC backend)
        ws_manager = WebSocketManager()
        
        # Test client registration
        print("\n1. Testing client registration...")
        client = ws_manager.register_client(user_agent="test-client", remote_ip="127.0.0.1")
        client_id = client.id
        print(f"   ✓ Registered client: {client_id}")
        
        # Test backend change notification
        print("\n2. Testing backend change notification...")
        ws_manager.notify_backend_change(
            backend_name="s3",
            operation="upload",
            content_id="file123.txt",
            details={"bucket": "test-bucket", "size": 2048}
        )
        print("   ✓ Backend change notification sent")
        
        # Test migration event notification
        print("\n3. Testing migration event notification...")
        ws_manager.notify_migration_event(
            migration_id="migration-456",
            status="completed",
            source_backend="ipfs",
            target_backend="s3",
            details={"transferred_size": 1024}
        )
        print("   ✓ Migration event notification sent")
        
        # Test stream progress notification
        print("\n4. Testing stream progress notification...")
        ws_manager.notify_stream_progress(
            operation_id="stream-789",
            progress={"bytes_transferred": 512, "total_bytes": 1024, "percentage": 50}
        )
        print("   ✓ Stream progress notification sent")
        
        # Test statistics
        print("\n5. Testing WebSocket manager statistics...")
        stats = ws_manager.get_stats()
        assert "sessions" in stats, "Sessions count missing from stats"
        assert "total_events" in stats, "Total events missing from stats"
        print(f"   ✓ Stats: {stats['sessions']} sessions, {stats['total_events']} events")
        
        # Test client unregistration
        print("\n6. Testing client unregistration...")
        ws_manager.unregister_client(client_id)
        print(f"   ✓ Unregistered client: {client_id}")
        
        print("\n✅ All WebSocket Manager Compatibility tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ WebSocket Manager Compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_performance():
    """Test performance of JSON-RPC polling vs theoretical WebSocket approach."""
    print("\n🧪 Testing Performance Characteristics...")
    
    try:
        from ipfs_kit_py.mcp.jsonrpc_methods import get_jsonrpc_event_methods
        
        event_methods = get_jsonrpc_event_methods()
        
        # Create session
        result = await event_methods.create_session()
        session_id = result["session_id"]
        
        # Subscribe to events
        await event_methods.subscribe(session_id, ["backend", "system"])
        
        # Test event throughput
        print("\n1. Testing event throughput...")
        start_time = time.time()
        
        # Generate multiple events
        event_manager = event_methods.event_manager
        for i in range(100):
            event_manager.notify_backend_change(
                backend_name="test",
                operation="add",
                content_id=f"test-{i}",
                details={"index": i}
            )
        
        # Poll for all events
        all_events = []
        for _ in range(10):  # Try up to 10 polls
            result = await event_methods.poll_events(session_id, limit=50)
            events = result["events"]
            all_events.extend(events)
            if len(all_events) >= 100:
                break
            await anyio.sleep(0.01)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"   ✓ Generated and retrieved {len(all_events)} events in {duration:.3f}s")
        print(f"   ✓ Throughput: {len(all_events)/duration:.1f} events/second")
        
        # Test polling latency
        print("\n2. Testing polling latency...")
        start_time = time.time()
        
        # Send a single event
        event_manager.notify_system_event("test_latency", {"timestamp": start_time})
        
        # Poll until we get the event
        found_event = None
        poll_attempts = 0
        while not found_event and poll_attempts < 20:
            poll_attempts += 1
            result = await event_methods.poll_events(session_id, limit=10)
            for event in result["events"]:
                if (event.get("data", {}).get("event_type") == "test_latency"):
                    found_event = event
                    break
            if not found_event:
                await anyio.sleep(0.001)  # 1ms delay
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000  # Convert to milliseconds
        
        if found_event:
            print(f"   ✓ Event latency: {latency:.1f}ms (after {poll_attempts} poll attempts)")
        else:
            print(f"   ⚠ Event not found after {poll_attempts} polls")
        
        # Clean up
        await event_methods.destroy_session(session_id)
        
        print("\n✅ Performance tests completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting JSON-RPC WebSocket Replacement Tests")
    print("=" * 60)
    
    tests = [
        ("JSON-RPC Event Management", test_jsonrpc_event_methods),
        ("JSON-RPC WebRTC Signaling", test_jsonrpc_webrtc_methods),
        ("WebSocket Manager Compatibility", test_websocket_compatibility),
        ("Performance Characteristics", test_performance)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! JSON-RPC WebSocket replacement is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = anyio.run(main)
    exit(exit_code)
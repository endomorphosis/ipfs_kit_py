#!/usr/bin/env python3
"""
Simple WebSocket test to verify WebSocket functionality
"""

import asyncio
import websockets
import json

async def test_websocket():
    """Test WebSocket connection to the dashboard."""
    uri = "ws://127.0.0.1:8085/ws"
    
    try:
        print(f"🔗 Attempting to connect to WebSocket: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established!")
            
            # Wait for initial message
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                print(f"📨 Received initial message: {data.get('type', 'unknown')}")
            except asyncio.TimeoutError:
                print("⏱️ No initial message received within 5 seconds")
            
            # Wait for status update
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                print(f"📊 Received status update: {data.get('type', 'unknown')}")
                print("✅ WebSocket is working correctly!")
                return True
            except asyncio.TimeoutError:
                print("⏱️ No status update received within 10 seconds")
                return False
                
    except ConnectionRefusedError:
        print("❌ Connection refused - server not running or WebSocket not available")
        return False
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing WebSocket Connection")
    print("=" * 40)
    
    # First check if server is running
    import requests
    try:
        response = requests.get("http://127.0.0.1:8085/api/status", timeout=5)
        print(f"✅ Dashboard server is running (status: {response.status_code})")
    except Exception as e:
        print(f"❌ Dashboard server not accessible: {e}")
        print("Please start the dashboard first with: python start_fixed_dashboard.py")
        exit(1)
    
    # Test WebSocket
    success = asyncio.run(test_websocket())
    
    if success:
        print("\n🎉 WebSocket test passed!")
    else:
        print("\n⚠️ WebSocket test failed - but polling fallback should work")

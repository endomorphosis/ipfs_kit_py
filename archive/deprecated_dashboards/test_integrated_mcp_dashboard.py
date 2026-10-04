#!/usr/bin/env python3
"""
Test Script for Integrated MCP Server with Dashboard

This script tests the integrated server that combines MCP functionality
with the web dashboard on the same port.
"""

import anyio
import json
import aiohttp
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_integrated_server():
    """Test the integrated MCP server with dashboard."""
    print("🧪 Testing Integrated MCP Server with Dashboard")
    print("=" * 60)
    
    server_url = "http://127.0.0.1:8765"
    
    async with aiohttp.ClientSession() as session:
        print("\n1. Testing Server Health...")
        try:
            async with session.get(f"{server_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"✅ Health check successful")
                    print(f"   Status: {health_data.get('status')}")
                    print(f"   Uptime: {health_data.get('uptime_seconds', 0):.1f}s")
                    print(f"   Services: {health_data.get('services', {})}")
                else:
                    print(f"❌ Health check failed: {response.status}")
        except Exception as e:
            print(f"❌ Health check error: {e}")
        
        print("\n2. Testing Prometheus Metrics...")
        try:
            async with session.get(f"{server_url}/metrics") as response:
                if response.status == 200:
                    metrics_text = await response.text()
                    print(f"✅ Metrics endpoint accessible")
                    print(f"   Response length: {len(metrics_text)} bytes")
                    # Show first few lines
                    lines = metrics_text.split('\n')[:5]
                    for line in lines:
                        if line.strip() and not line.startswith('#'):
                            print(f"   {line}")
                else:
                    print(f"❌ Metrics failed: {response.status}")
        except Exception as e:
            print(f"❌ Metrics error: {e}")
        
        print("\n3. Testing MCP Status...")
        try:
            async with session.get(f"{server_url}/mcp/status") as response:
                if response.status == 200:
                    status_data = await response.json()
                    print(f"✅ MCP status accessible")
                    print(f"   Server: {status_data.get('server_name')}")
                    print(f"   Available: {status_data.get('available')}")
                    print(f"   Capabilities: {len(status_data.get('capabilities', []))}")
                    print(f"   Endpoints: {list(status_data.get('endpoints', {}).keys())}")
                else:
                    print(f"❌ MCP status failed: {response.status}")
        except Exception as e:
            print(f"❌ MCP status error: {e}")
        
        print("\n4. Testing MCP JSON-RPC...")
        try:
            # Test MCP initialize request
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            async with session.post(f"{server_url}/mcp", json=mcp_request) as response:
                if response.status == 200:
                    mcp_response = await response.json()
                    print(f"✅ MCP JSON-RPC accessible")
                    print(f"   Response ID: {mcp_response.get('id')}")
                    print(f"   Method: initialize")
                    if 'result' in mcp_response:
                        print(f"   Result keys: {list(mcp_response['result'].keys())}")
                    elif 'error' in mcp_response:
                        print(f"   Error: {mcp_response['error']}")
                else:
                    print(f"❌ MCP JSON-RPC failed: {response.status}")
        except Exception as e:
            print(f"❌ MCP JSON-RPC error: {e}")
        
        print("\n5. Testing Dashboard Pages...")
        dashboard_pages = [
            ("/dashboard", "Main Dashboard"),
            ("/dashboard/metrics", "Metrics"),
            ("/dashboard/health", "Health"),
            ("/dashboard/vfs", "VFS Analytics")
        ]
        
        for path, name in dashboard_pages:
            try:
                async with session.get(f"{server_url}{path}") as response:
                    if response.status == 200:
                        content = await response.text()
                        print(f"✅ {name} page accessible ({len(content)} bytes)")
                    else:
                        print(f"❌ {name} page failed: {response.status}")
            except Exception as e:
                print(f"❌ {name} page error: {e}")
        
        print("\n6. Testing Dashboard API...")
        api_endpoints = [
            ("/dashboard/api/summary", "Summary"),
            ("/dashboard/api/metrics", "Metrics Data"),
            ("/dashboard/api/health", "Health Data"),
            ("/dashboard/api/analytics", "Analytics")
        ]
        
        for path, name in api_endpoints:
            try:
                async with session.get(f"{server_url}{path}") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ {name} API accessible")
                        if isinstance(data, dict):
                            print(f"   Keys: {list(data.keys())}")
                    else:
                        print(f"❌ {name} API failed: {response.status}")
            except Exception as e:
                print(f"❌ {name} API error: {e}")
        
        print("\n7. Testing Root Endpoint...")
        try:
            async with session.get(f"{server_url}/") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Root endpoint accessible")
                    print(f"   Message: {data.get('message')}")
                    print(f"   Dashboard: {data.get('dashboard')}")
                    print(f"   Docs: {data.get('docs')}")
                else:
                    print(f"❌ Root endpoint failed: {response.status}")
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Test Summary:")
    print("   The integrated server provides unified access to:")
    print("   • MCP JSON-RPC functionality via HTTP and WebSocket")
    print("   • Web dashboard for monitoring and analytics")
    print("   • Prometheus metrics for external monitoring")
    print("   • Health checks and status endpoints")
    print("   • API documentation at /docs")
    print("\n   All services run on the same port (8765) for unified access!")


async def test_websocket_connection():
    """Test WebSocket connections."""
    print("\n🔌 Testing WebSocket Connections...")
    
    import websockets
    
    # Test MCP WebSocket
    try:
        uri = "ws://127.0.0.1:8765/mcp/ws"
        async with websockets.connect(uri) as websocket:
            # Send MCP initialize
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-ws-client", "version": "1.0.0"}
                }
            }
            
            await websocket.send(json.dumps(mcp_request))
            response = await websocket.recv()
            response_data = json.loads(response)
            
            print(f"✅ MCP WebSocket connection successful")
            print(f"   Response ID: {response_data.get('id')}")
            
    except Exception as e:
        print(f"❌ MCP WebSocket error: {e}")
    
    # Test Dashboard WebSocket
    try:
        uri = "ws://127.0.0.1:8765/dashboard/ws"
        async with websockets.connect(uri) as websocket:
            # Wait for initial data
            with anyio.fail_after(5.0):
                response = await websocket.recv()
            response_data = json.loads(response)
            
            print(f"✅ Dashboard WebSocket connection successful")
            print(f"   Data keys: {list(response_data.keys())}")
            
    except Exception as e:
        print(f"❌ Dashboard WebSocket error: {e}")


def main():
    """Main test function."""
    print("Starting tests for Integrated MCP Server with Dashboard...")
    print("Make sure the server is running with:")
    print("python mcp/integrated_mcp_server_with_dashboard.py")
    print()
    
    # Give user a chance to start the server
    try:
        input("Press Enter when the server is running (or Ctrl+C to exit)...")
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
        return
    
    try:
        anyio.run(test_integrated_server)
        
        # Test WebSockets if websockets package is available
        try:
            import websockets
            anyio.run(test_websocket_connection)
        except ImportError:
            print("\n📦 Install 'websockets' package to test WebSocket connections:")
            print("   pip install websockets")
        
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"\nTest error: {e}")


if __name__ == "__main__":
    main()

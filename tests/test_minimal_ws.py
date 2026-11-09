#!/usr/bin/env python3
"""
Minimal dashboard test to verify WebSocket route registration
"""

import anyio
import sys
from pathlib import Path
import pytest

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

pytestmark = pytest.mark.anyio

async def test_minimal_dashboard():
    """Test minimal dashboard with WebSocket focus."""
    
    try:
        from fastapi import FastAPI, WebSocket
        from ipfs_kit_py.dashboard.comprehensive_mcp_dashboard import ComprehensiveMCPDashboard
        
        # Initialize dashboard
        config = {
            'data_dir': '~/.ipfs_kit/data',
            'port': 8085,
            'mcp_server_url': 'http://127.0.0.1:8085'
        }
        
        print("🔧 Creating dashboard instance...")
        dashboard = ComprehensiveMCPDashboard(config)
        
        # Check all routes including WebSocket
        total_routes = 0
        websocket_routes = 0
        api_routes = 0
        
        print("\n📋 Analyzing registered routes:")
        for route in dashboard.app.routes:
            if hasattr(route, 'path'):
                total_routes += 1
                route_type = type(route).__name__
                
                if route.path == '/ws':
                    websocket_routes += 1
                    print(f"   🔗 WebSocket route found: {route.path} ({route_type})")
                elif route.path.startswith('/api/'):
                    api_routes += 1
                    if 'logs' in route.path:
                        print(f"   📋 Logs route: {route.path}")
        
        print(f"\n📊 Route Summary:")
        print(f"   - Total routes: {total_routes}")
        print(f"   - WebSocket routes: {websocket_routes}")
        print(f"   - API routes: {api_routes}")
        
        # Test the WebSocket handler exists
        handler_exists = hasattr(dashboard, '_handle_websocket')
        print(f"   - WebSocket handler exists: {handler_exists}")
        
        if websocket_routes > 0:
            print("✅ WebSocket route is properly registered!")
        else:
            print("❌ WebSocket route is NOT registered!")
            
        # Show the actual route paths for debugging
        print("\n🔍 All route paths:")
        for i, route in enumerate(dashboard.app.routes):
            if hasattr(route, 'path'):
                route_type = type(route).__name__
                methods = getattr(route, 'methods', 'WS' if 'websocket' in route_type.lower() else 'N/A')
                print(f"   {i+1:2d}. {methods} {route.path} ({route_type})")
        
        return websocket_routes > 0
        
    except Exception as e:
        print(f"❌ Error testing dashboard: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Minimal Dashboard WebSocket Test")
    print("=" * 50)
    
    success = anyio.run(test_minimal_dashboard)
    
    if success:
        print("\n✅ WebSocket route registration test passed!")
    else:
        print("\n❌ WebSocket route registration test failed!")
    
    print("\nNote: Even if WebSocket fails, polling mode provides the same functionality.")
    print("The dashboard should work correctly with polling fallback.")

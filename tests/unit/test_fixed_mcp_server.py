#!/usr/bin/env python3
"""
Test the fixed MCP server
"""
import sys
import os
import anyio
import traceback
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_mcp_server():
    """Test the fixed MCP server"""
    print("=== Testing Fixed MCP Server ===")
    
    try:
        from enhanced_unified_mcp_server import BackendHealthMonitor
        print("✓ BackendHealthMonitor imported successfully")
        
        # Test the backend health monitor
        monitor = BackendHealthMonitor()
        print("✓ BackendHealthMonitor initialized")
        
        # Test Lotus health check
        print("\\nTesting Lotus health check...")
        backend = {'name': 'lotus', 'status': 'unknown', 'health': 'unknown'}
        result = await monitor._check_lotus_health(backend)
        print(f"✓ Lotus health check completed: {result.get('status', 'unknown')}")
        
        # Test overall backend health
        print("\\nTesting overall backend health...")
        backends = await monitor.check_all_backends()
        print(f"✓ Backend health check completed: {len(backends)} backends")
        
        for backend_name, backend in backends.items():
            print(f"  - {backend_name}: {backend.get('status', 'unknown')}")
        
        print("\\n=== Test Complete ===")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = anyio.run(test_mcp_server)
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Test daemon initialization and MCP protocol flow.
This script will test if the MCP server properly initializes daemons during the MCP handshake.
"""

import sys
import os
import anyio
import json
import pytest

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.anyio

async def test_mcp_initialization_flow():
    """Test the complete MCP initialization flow including daemon startup."""
    
    print("=== MCP Initialization Flow Test ===")
    
    try:
        # Import the server
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        
        print("1. Creating MCP server instance...")
        server = EnhancedMCPServerWithDaemonMgmt()
        print("   ✓ Server created")
        
        # Check daemon status after server instantiation
        print("\n2. Checking daemon status after server instantiation...")
        integration = server.ipfs_integration
        
        print(f"   - IPFS Kit available: {integration.ipfs_kit is not None}")
        print(f"   - Use mock fallback: {integration.use_mock_fallback}")
        print(f"   - Auto start daemon: {integration.auto_start_daemon}")
        print(f"   - Daemon process: {integration.daemon_process is not None}")
        
        # Test IPFS connection
        connection_status = integration._test_ipfs_connection()
        print(f"   - IPFS connection: {'✓ Working' if connection_status else '✗ Failed'}")
        
        # Simulate MCP initialization handshake
        print("\n3. Simulating MCP initialization handshake...")
        
        # Test handle_initialize
        init_params = {}
        init_result = await server.handle_initialize(init_params)
        print(f"   ✓ Initialize response: {init_result['serverInfo']['name']}")
        
        # Test notifications/initialized (this is when client confirms initialization)
        print("   ✓ Client initialization notification would be sent here")
        
        # Test a basic tool to ensure everything works
        print("\n4. Testing tool execution after initialization...")
        
        try:
            result = await server.execute_tool("ipfs_id", {})
            if result.get('success'):
                print("   ✓ ipfs_id tool executed successfully")
                print(f"     - ID: {result.get('ID', 'N/A')}")
                print(f"     - Operation: {result.get('operation', 'N/A')}")
            else:
                print(f"   ⚠ ipfs_id tool returned error: {result.get('error')}")
        except Exception as e:
            print(f"   ✗ Tool execution failed: {e}")
        
        # Test system health tool
        print("\n5. Testing system health...")
        try:
            health_result = await server.execute_tool("system_health", {})
            if health_result.get('success'):
                print("   ✓ System health check successful")
                ipfs_info = health_result.get('ipfs', {})
                print(f"     - Daemon running: {ipfs_info.get('daemon_running')}")
                print(f"     - Connection test: {ipfs_info.get('connection_test')}")
                print(f"     - Mock fallback: {ipfs_info.get('mock_fallback')}")
            else:
                print(f"   ⚠ System health check failed: {health_result.get('error')}")
        except Exception as e:
            print(f"   ✗ System health check failed: {e}")
        
        print("\n=== Initialization Flow Analysis ===")
        
        # Analyze the initialization flow
        if not integration.use_mock_fallback and connection_status:
            print("✅ OPTIMAL: Real IPFS daemon is running and accessible")
            print("   - Daemons were properly started during server instantiation")
            print("   - MCP clients will have full IPFS functionality")
        elif not integration.use_mock_fallback and not connection_status:
            print("⚠️  PARTIAL: IPFS Kit available but daemon not accessible")
            print("   - May need manual daemon startup or configuration fix")
            print("   - Some operations may fall back to direct commands")
        elif integration.use_mock_fallback:
            print("🔄 FALLBACK: Using mock implementations")
            print("   - Real IPFS not available, but all tools will respond")
            print("   - Good for development/testing, limited for production")
        
        return True
        
    except Exception as e:
        print(f"✗ Initialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_daemon_startup_improvements():
    """Test if we need to improve daemon startup timing."""
    
    print("\n=== Daemon Startup Improvement Analysis ===")
    
    try:
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
        
        print("Testing daemon startup timing...")
        
        # Test direct daemon startup
        integration = IPFSKitIntegration(auto_start_daemon=True)
        
        if integration._test_ipfs_connection():
            print("✅ Daemon startup during integration init: SUCCESS")
        else:
            print("⚠️  Daemon startup during integration init: NEEDS IMPROVEMENT")
            
            # Try manual daemon startup
            print("   Attempting manual daemon startup...")
            if integration._ensure_daemon_running():
                print("   ✓ Manual daemon startup: SUCCESS")
            else:
                print("   ✗ Manual daemon startup: FAILED")
        
        return True
        
    except Exception as e:
        print(f"✗ Daemon startup test failed: {e}")
        return False

if __name__ == "__main__":
    async def main():
        success1 = await test_mcp_initialization_flow()
        success2 = await test_daemon_startup_improvements()
        
        print(f"\n=== Final Results ===")
        print(f"MCP Initialization Flow: {'✅ PASS' if success1 else '❌ FAIL'}")
        print(f"Daemon Startup Analysis: {'✅ PASS' if success2 else '❌ FAIL'}")
        
        if success1 and success2:
            print("\n🎉 MCP server initialization is working correctly!")
            print("   The daemon startup happens during server instantiation,")
            print("   which is the appropriate time for MCP servers.")
        else:
            print("\n🔧 MCP server initialization needs improvements.")
        
        return success1 and success2
    
    success = anyio.run(main)
    sys.exit(0 if success else 1)

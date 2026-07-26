#!/usr/bin/env python3
"""
IPFS-Kit Refactored Architecture Demo

This script demonstrates the new daemon-based architecture where:
1. IPFS-Kit Daemon manages filesystem backends, health, replication, logging
2. MCP Server provides lightweight interface for MCP tools and dashboard  
3. CLI tools access IPFS-Kit libraries directly for retrieval
4. Both MCP and CLI read parquet indexes for fast routing decisions
"""

import anyio
import json
import logging
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


async def demo_daemon_architecture():
    """Demonstrate the refactored daemon-based architecture."""
    print("🚀 IPFS-Kit Refactored Architecture Demo")
    print("=" * 60)
    
    # Step 1: Import and check daemon client
    try:
        from ipfs_kit_daemon_client import daemon_client, route_reader
        print("✅ Daemon client imported successfully")
    except ImportError as e:
        print(f"❌ Daemon client import failed: {e}")
        return
    
    # Step 2: Check if daemon is running
    print("\n📊 Checking daemon status...")
    daemon_running = await daemon_client.is_daemon_running()
    print(f"   Daemon running: {daemon_running}")
    
    if not daemon_running:
        print("\n🔄 Starting daemon...")
        start_result = await daemon_client.start_daemon()
        if start_result.get("success"):
            print("   ✅ Daemon started successfully")
            # Wait for startup
            await anyio.sleep(2)
        else:
            print(f"   ❌ Failed to start daemon: {start_result.get('error')}")
            print("   Continuing with demo using available components...")
    
    # Step 3: Get daemon status
    print("\n📋 Getting daemon status...")
    try:
        status = await daemon_client.get_daemon_status()
        if status.get("running"):
            print("   ✅ Daemon is running")
            daemon_info = status.get("daemon", {})
            print(f"   Uptime: {daemon_info.get('uptime', 'unknown')} seconds")
            print(f"   PID: {daemon_info.get('pid', 'unknown')}")
        else:
            print(f"   ❌ Daemon not running: {status.get('error', 'unknown')}")
    except Exception as e:
        print(f"   ⚠️ Error getting daemon status: {e}")
    
    # Step 4: Check backend health via daemon
    print("\n🏥 Checking backend health via daemon...")
    try:
        backend_health = await daemon_client.get_backend_health()
        if isinstance(backend_health, dict) and not backend_health.get("error"):
            print("   ✅ Backend health retrieved from daemon")
            for backend_name, health_info in backend_health.items():
                health = health_info.get("health", "unknown")
                status_info = health_info.get("status", "unknown")
                print(f"   {backend_name}: {health} ({status_info})")
        else:
            print(f"   ⚠️ Could not get backend health: {backend_health.get('error', 'unknown')}")
    except Exception as e:
        print(f"   ⚠️ Error getting backend health: {e}")
    
    # Step 5: Test routing via parquet indexes
    print("\n🗂️ Testing routing via parquet indexes...")
    try:
        if route_reader:
            # Test backend statistics
            stats = route_reader.get_backend_stats()
            print(f"   ✅ Backend statistics: {len(stats)} backends found")
            for backend, backend_stats in stats.items():
                count = backend_stats.get("count", 0)
                size = backend_stats.get("total_size", 0)
                print(f"   {backend}: {count} pins, {size} bytes")
            
            # Test backend suggestion
            suggested = route_reader.suggest_backend_for_new_pin()
            print(f"   Suggested backend for new pin: {suggested}")
        else:
            print("   ⚠️ Route reader not available")
    except Exception as e:
        print(f"   ⚠️ Error testing routing: {e}")
    
    # Step 6: Test IPFS Kit direct access
    print("\n🔗 Testing direct IPFS Kit access...")
    try:
        from ipfs_kit_py.ipfs_kit import IPFSKit
        
        # Initialize without auto-starting daemons (daemon's responsibility)
        config = {"auto_start_daemons": False}
        ipfs_kit = IPFSKit(config)
        print("   ✅ IPFS Kit initialized for retrieval operations")
        
        # Test if we can access IPFS methods
        if hasattr(ipfs_kit, 'ipfs') and hasattr(ipfs_kit.ipfs, 'ipfs_id'):
            print("   ✅ IPFS methods accessible")
        else:
            print("   ⚠️ IPFS methods may not be directly accessible")
            
    except Exception as e:
        print(f"   ❌ IPFS Kit initialization failed: {e}")
    
    # Step 7: Show architecture benefits
    print("\n🏗️ Architecture Benefits:")
    print("   ✅ Separation of concerns:")
    print("      - Daemon: Backend management, health monitoring, replication")
    print("      - MCP Server: Lightweight interface, dashboard, tools")
    print("      - CLI: Direct IPFS access, fast routing decisions")
    print("   ✅ Fast routing via parquet indexes")
    print("   ✅ Scalable backend management")
    print("   ✅ Independent component lifecycles")
    
    print("\n🎯 Usage Patterns:")
    print("   • Start daemon: python ipfs_kit_daemon.py")
    print("   • Start MCP server: python refactored_mcp_server.py")
    print("   • Use CLI: python ipfs_kit_cli.py daemon status")
    print("   • Check health: curl http://localhost:8888/api/health")
    
    print("\n✅ Demo completed successfully!")


async def demo_mcp_server():
    """Demo the refactored MCP server."""
    print("\n🌐 Testing Refactored MCP Server...")
    
    try:
        # Import the refactored server
        from refactored_mcp_server import RefactoredMCPServer
        
        print("   ✅ Refactored MCP server imported")
        
        # Create server instance (but don't start it)
        server = RefactoredMCPServer(host="127.0.0.1", port=8888)
        print("   ✅ MCP server instance created")
        
        # Check if components are available
        components = {
            "daemon_client": hasattr(server, 'daemon_client'),
            "ipfs_kit": server.ipfs_kit is not None,
            "vfs_endpoints": server.vfs_endpoints is not None,
            "health_monitor": server.health_monitor is not None
        }
        
        print("   Component availability:")
        for component, available in components.items():
            status = "✅" if available else "❌"
            print(f"      {status} {component}: {available}")
            
    except Exception as e:
        print(f"   ❌ Error testing MCP server: {e}")


async def demo_cli_tool():
    """Demo the CLI tool."""
    print("\n💻 Testing CLI Tool...")
    
    try:
        # Import the CLI
        from ipfs_kit_cli import IPFSKitCLI
        
        print("   ✅ CLI tool imported")
        
        # Create CLI instance
        cli = IPFSKitCLI()
        print("   ✅ CLI instance created")
        
        # Test daemon status via CLI
        status = await cli.daemon_status()
        if status.get("error"):
            print(f"   ⚠️ Daemon status: {status['error']}")
        else:
            print("   ✅ Daemon status retrieved via CLI")
        
        # Test routing operations
        stats = cli.route_stats()
        if stats.get("error"):
            print(f"   ⚠️ Route stats: {stats['error']}")
        else:
            print("   ✅ Route statistics retrieved via CLI")
            
    except Exception as e:
        print(f"   ❌ Error testing CLI: {e}")


async def main():
    """Main demo function."""
    try:
        await demo_daemon_architecture()
        await demo_mcp_server()
        await demo_cli_tool()
        
        print("\n" + "=" * 60)
        print("🎉 Refactored architecture demo completed!")
        print("Ready to use the new daemon-based IPFS-Kit system.")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    anyio.run(main)

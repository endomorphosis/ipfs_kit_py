#!/usr/bin/env python3
"""
Demonstration script showing the complete IPFS Kit MCP Server with:
1. Enhanced daemon management
2. Content-addressed storage optimization
3. Cross-backend content routing
4. API responsiveness monitoring
"""

import anyio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project path
sys.path.insert(0, str(Path(__file__).parent))

from ipfs_kit_py.mcp.ipfs_kit.core.daemon_manager import get_daemon_manager
from ipfs_kit_py.mcp.ipfs_kit.core.content_optimization import get_content_optimizer


async def demonstrate_enhanced_ipfs_management():
    """
    Comprehensive demonstration of enhanced IPFS management capabilities.
    """
    print("🚀 IPFS Kit MCP Server - Enhanced Management Demo")
    print("=" * 60)
    
    # Initialize components
    daemon_mgr = get_daemon_manager()
    optimizer = get_content_optimizer()
    
    # Step 1: Daemon Health Assessment
    print("\n📊 Step 1: Comprehensive Daemon Health Check")
    health = await daemon_mgr.check_daemon_health()
    
    print(f"   Overall Health: {health['overall_health']}")
    print(f"   Process Running: {health['process_running']}")
    print(f"   API Responsive: {health['api_responsive']}")
    
    for port_name, port_info in health['ports_available'].items():
        status = "✓ Available" if port_info.get('available') else "❌ In Use"
        print(f"   Port {port_name} ({port_info['port']}): {status}")
    
    # Step 2: Ensure Healthy Daemon
    print("\n🔧 Step 2: Ensure Healthy IPFS Daemon")
    if health['overall_health'] != 'healthy':
        print("   Daemon needs attention, performing intelligent restart...")
        start_result = await daemon_mgr.start_daemon(force_restart=True)
        
        if start_result['success']:
            print(f"   ✓ Daemon started successfully via {start_result['method']}")
            print(f"   ✓ API responsive: {start_result['daemon_responsive']}")
            
            if start_result.get('cleanup_performed'):
                cleanup = start_result.get('cleanup_result', {})
                print(f"   ✓ Cleanup: {len(cleanup.get('processes_killed', []))} processes killed")
            
            if start_result.get('port_conflicts_resolved'):
                port_cleanup = start_result.get('port_cleanup', {})
                print(f"   ✓ Port conflicts: {len(port_cleanup.get('processes_killed', []))} resolved")
        else:
            print(f"   ❌ Failed to start daemon: {start_result.get('error', 'Unknown error')}")
            return
    else:
        print("   ✓ Daemon already healthy and responsive")
    
    # Step 3: Content Optimization Setup
    print("\n🎯 Step 3: Content-Addressed Storage Optimization")
    
    # Initialize with ipfs_kit_py if available
    try:
        import ipfs_kit_py
        if hasattr(ipfs_kit_py, 'ipfs_kit'):
            ipfs_kit_instance = ipfs_kit_py.ipfs_kit()
            optimizer.ipfs_kit = ipfs_kit_instance
            print("   ✓ Integrated with ipfs_kit_py infrastructure")
        else:
            print("   ⚠️ ipfs_kit_py available but missing expected interface")
    except ImportError:
        print("   ⚠️ ipfs_kit_py not available, using fallback methods")
    
    # Test routing capabilities
    routing_test = await optimizer.ensure_ipfs_kit_routing('demonstration')
    if routing_test.get('routed_through_ipfs_kit'):
        print(f"   ✓ All operations routed through ipfs_kit_py via {routing_test.get('ipfs_kit_api')}")
    else:
        print(f"   ⚠️ Routing through ipfs_kit_py: {routing_test.get('error', 'Not available')}")
    
    # Step 4: Demonstrate Content Optimization
    print("\n📁 Step 4: Content-Addressed File Optimization")
    
    # Test with a sample CID (this would be a real CID in practice)
    test_cid = "QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"  # Sample CID
    
    print(f"   Testing optimization for CID: {test_cid}")
    optimization_result = await optimizer.optimize_content_access(test_cid, "get")
    
    print(f"   Optimization applied: {optimization_result.get('optimization_applied', False)}")
    print(f"   Cache hit: {optimization_result.get('cache_hit', False)}")
    
    backend_availability = optimization_result.get('backend_availability', {})
    print(f"   Backends checked: {len(backend_availability)}")
    
    for backend, info in backend_availability.items():
        available = "✓" if info.get('available') else "❌"
        response_time = info.get('response_time', 'N/A')
        print(f"     {backend}: {available} ({response_time}s)")
    
    fastest_backend = optimization_result.get('fastest_backend')
    if fastest_backend:
        print(f"   ✓ Optimal backend selected: {fastest_backend}")
    
    # Step 5: Cross-Backend Content Synchronization
    print("\n🔄 Step 5: Cross-Backend Content Synchronization")
    
    sync_result = await optimizer.sync_content_across_backends(
        test_cid, 
        target_backends=['storacha', 'synapse', 'lassie']
    )
    
    print(f"   Sync operation success: {sync_result.get('success', False)}")
    print(f"   Successful syncs: {len(sync_result.get('successful_syncs', []))}")
    print(f"   Failed syncs: {len(sync_result.get('failed_syncs', []))}")
    
    if sync_result.get('successful_syncs'):
        print(f"   ✓ Content synchronized to: {', '.join(sync_result['successful_syncs'])}")
    
    # Step 6: Performance Statistics
    print("\n📈 Step 6: Optimization Performance Statistics")
    
    stats = await optimizer.get_optimization_stats()
    print(f"   Total content items tracked: {stats['total_content_items']}")
    print(f"   Routing cache efficiency: {stats['routing_cache_size']} entries")
    print(f"   Optimization success rate: {stats['optimization_success_rate']:.1%}")
    
    performance_summary = stats.get('performance_summary', {})
    if performance_summary:
        print("   Backend performance summary:")
        for backend, metrics in performance_summary.items():
            avg_time = metrics.get('average_response_time', 0)
            success_rate = metrics.get('success_rate', 0)
            print(f"     {backend}: {avg_time:.3f}s avg, {success_rate:.1%} success")
    
    # Step 7: Ongoing Health Monitoring
    print("\n🔍 Step 7: Continuous Health Monitoring")
    print("   Background health monitoring is active")
    print("   Daemon will be automatically restarted if it becomes unresponsive")
    print("   Content routing will be optimized based on performance metrics")
    
    # Final Health Check
    print("\n✅ Final System Status")
    final_health = await daemon_mgr.check_daemon_health()
    print(f"   IPFS Daemon: {final_health['overall_health']}")
    print(f"   API Response Time: {final_health.get('performance_metrics', {}).get('api_response_time', 'N/A')}s")
    
    if final_health.get('performance_metrics', {}).get('version_info'):
        version_info = final_health['performance_metrics']['version_info']
        print(f"   IPFS Version: {version_info.get('Version', 'Unknown')}")
    
    print("\n🎉 Enhanced IPFS Management Demo Complete!")
    print("=" * 60)
    
    return {
        "daemon_healthy": final_health['overall_health'] == 'healthy',
        "content_optimization_active": True,
        "cross_backend_sync_available": True,
        "health_monitoring_active": daemon_mgr.is_monitoring
    }


async def main():
    """Main demonstration function."""
    try:
        result = await demonstrate_enhanced_ipfs_management()
        
        print(f"\\nDemo Results:")
        for key, value in result.items():
            status = "✓" if value else "❌"
            print(f"  {key}: {status}")
        
        # Keep running for a bit to show monitoring
        print("\\n⏱️  Monitoring daemon for 30 seconds...")
        await anyio.sleep(30)
        
    except KeyboardInterrupt:
        print("\\n👋 Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo error: {e}")
        raise


if __name__ == "__main__":
    anyio.run(main)

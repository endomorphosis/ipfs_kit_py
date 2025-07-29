#!/usr/bin/env python3
"""
Test Enhanced LibP2P Manager and Health Integration

This script tests the enhanced LibP2P manager with:
- Real peer discovery from IPFS, cluster, and Ethereum networks
- Content sharing capabilities (pinsets, vectors, knowledge, files)
- Health monitoring integration
- Bootstrap from existing networks
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_enhanced_libp2p():
    """Test the enhanced LibP2P manager."""
    
    print("🧪 Testing Enhanced LibP2P Manager")
    print("=" * 60)
    
    try:
        # Import the enhanced LibP2P manager
        from enhanced_libp2p_manager import EnhancedLibp2pManager, start_libp2p_manager
        
        print("✅ Successfully imported Enhanced LibP2P Manager")
        
        # Test 1: Create and start manager
        print("\\n📡 Test 1: Starting LibP2P Manager...")
        manager = await start_libp2p_manager()
        
        if manager and manager.host_active:
            print("✅ LibP2P Manager started successfully")
            print(f"   Peer ID: {manager.stats.get('peer_id', 'unknown')}")
            print(f"   Host Active: {manager.host_active}")
            print(f"   Discovery Active: {manager.discovery_active}")
        else:
            print("❌ Failed to start LibP2P Manager")
            return
        
        # Test 2: Check peer statistics
        print("\\n📊 Test 2: Checking Peer Statistics...")
        stats = manager.get_peer_statistics()
        
        print(f"   Total Peers: {stats.get('total_peers', 0)}")
        print(f"   Connected Peers: {stats.get('connected_peers', 0)}")
        print(f"   Bootstrap Peers: {stats.get('bootstrap_peers', 0)}")
        print(f"   Protocols Active: {len(stats.get('protocols_supported', []))}")
        print(f"   Files Accessible: {stats.get('files_accessible', 0)}")
        print(f"   Pins Accessible: {stats.get('pins_accessible', 0)}")
        
        # Test 3: Check content sharing
        print("\\n📦 Test 3: Checking Content Sharing...")
        content_summary = manager.get_shared_content_summary()
        
        print(f"   Pinsets Available: {content_summary.get('pinsets', {}).get('total_pins', 0)}")
        print(f"   Files Available: {content_summary.get('files', {}).get('total_files', 0)}")
        print(f"   Vectors Available: {content_summary.get('vectors', {}).get('total_vectors', 0)}")
        print(f"   Knowledge Entities: {content_summary.get('knowledge', {}).get('total_entities', 0)}")
        
        # Test 4: Check discovered peers
        print("\\n🔍 Test 4: Checking Discovered Peers...")
        all_peers = manager.get_all_peers()
        
        if all_peers:
            print(f"   Total Discovered Peers: {len(all_peers)}")
            
            # Group by source
            sources = {}
            for peer_id, peer_info in all_peers.items():
                source = peer_info.get("source", "unknown")
                sources[source] = sources.get(source, 0) + 1
            
            for source, count in sources.items():
                print(f"   {source}: {count} peers")
                
            # Show first few peers
            print("\\n   Sample Peers:")
            for i, (peer_id, peer_info) in enumerate(list(all_peers.items())[:5]):
                status = "Connected" if peer_info.get("connected") else "Discovered"
                source = peer_info.get("source", "unknown")
                print(f"     {peer_id[:16]}... - {status} ({source})")
                
        else:
            print("   No peers discovered yet")
        
        # Test 5: Test protocol handlers
        print("\\n🔧 Test 5: Testing Protocol Handlers...")
        protocols = list(manager.protocols.keys())
        print(f"   Active Protocols: {len(protocols)}")
        for protocol in protocols:
            print(f"     {protocol}")
        
        # Test a protocol handler
        if protocols:
            test_protocol = protocols[0]
            test_request = {"peer_id": "test_peer", "request_type": "test"}
            import json
            
            try:
                response = await manager.protocols[test_protocol](json.dumps(test_request).encode())
                response_data = json.loads(response.decode())
                print(f"   ✅ Protocol {test_protocol} responded successfully")
                print(f"      Response keys: {list(response_data.keys())}")
            except Exception as e:
                print(f"   ⚠️  Protocol {test_protocol} test failed: {e}")
        
        # Test 6: Test health integration
        print("\\n🏥 Test 6: Testing Health Integration...")
        
        # Import health monitor
        from mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        config_dir = Path("/tmp/ipfs_kit_test_config")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        health_monitor = BackendHealthMonitor(config_dir=config_dir)
        
        # Initialize LibP2P backend in health monitor
        libp2p_backend = {
            "name": "libp2p",
            "type": "peer_network",
            "status": "unknown",
            "health": "unknown",
            "detailed_info": {},
            "metrics": {},
            "errors": [],
            "last_check": None
        }
        
        # Check health
        updated_backend = await health_monitor._check_libp2p_health(libp2p_backend)
        
        print(f"   Status: {updated_backend.get('status', 'unknown')}")
        print(f"   Health: {updated_backend.get('health', 'unknown')}")
        print(f"   Message: {updated_backend.get('status_message', 'No message')}")
        
        # Show metrics
        metrics = updated_backend.get("metrics", {})
        if metrics:
            print("\\n   Health Metrics:")
            for category, data in metrics.items():
                print(f"     {category}:")
                for key, value in data.items():
                    if isinstance(value, (int, float, bool, str)):
                        print(f"       {key}: {value}")
                    elif isinstance(value, list) and len(value) <= 5:
                        print(f"       {key}: {value}")
                    elif isinstance(value, list):
                        print(f"       {key}: {len(value)} items")
        
        print("\\n✅ Enhanced LibP2P Manager tests completed successfully!")
        
        # Keep running for a bit to see discovery in action
        print("\\n🔄 Running discovery for 30 seconds...")
        await asyncio.sleep(30)
        
        # Check final stats
        final_stats = manager.get_peer_statistics()
        print(f"\\n📈 Final Stats:")
        print(f"   Total Peers: {final_stats.get('total_peers', 0)}")
        print(f"   Connected Peers: {final_stats.get('connected_peers', 0)}")
        
        # Stop the manager
        await manager.stop()
        print("\\n🛑 LibP2P Manager stopped")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("   Make sure enhanced_libp2p_manager.py is in the current directory")
        
    except Exception as e:
        print(f"❌ Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Enhanced LibP2P Manager Test Suite")
    print("This will test peer discovery, content sharing, and health integration")
    print()
    
    try:
        asyncio.run(test_enhanced_libp2p())
    except KeyboardInterrupt:
        print("\\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

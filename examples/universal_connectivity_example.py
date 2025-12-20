#!/usr/bin/env python3
"""
Example: Universal Connectivity with ipfs_kit_py

This example demonstrates how to use the universal connectivity features
to create a libp2p peer with maximum discoverability and NAT traversal
capabilities.

Features demonstrated:
- AutoNAT for NAT detection
- Circuit Relay for relayed connections
- DCUtR for hole punching
- Pubsub peer discovery
- mDNS local discovery
- Bootstrap peer connections
"""

import anyio
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("UniversalConnectivityExample")


async def main():
    """Main example function."""
    
    try:
        # Import required modules directly
        import ipfs_kit_py.libp2p.universal_connectivity as uc
        
        logger.info("=" * 60)
        logger.info("Universal Connectivity Example")
        logger.info("=" * 60)
        
        # Create configuration
        config = uc.ConnectivityConfig(
            # Enable all discovery mechanisms
            enable_mdns=True,
            enable_pubsub_discovery=True,
            enable_dht_discovery=True,
            
            # Discovery topics
            pubsub_discovery_topics=[
                "_peer-discovery._p2p._pubsub",
                "universal-connectivity-browser-peer-discovery"
            ],
            
            # Enable NAT traversal
            enable_autonat=True,
            enable_relay_client=True,
            enable_relay_server=True,  # Act as relay for others
            enable_dcutr=True,
            
            # Connection limits
            max_connections=1000,
            max_relay_circuits=256,
            
            # Discovery intervals
            mdns_query_interval=30.0,  # Every 30 seconds
            pubsub_announce_interval=10.0,  # Every 10 seconds
            autonat_query_interval=300.0,  # Every 5 minutes
            
            # Bootstrap configuration
            connect_to_bootstrap=True,
            # Uses default IPFS bootstrap peers
            
            # Callbacks
            on_peer_discovered=lambda peer: logger.info(
                f"🔍 Discovered peer: {peer.peer_id}"
            ),
            on_connection_established=lambda peer_id, addr: logger.info(
                f"✅ Connected to: {peer_id}"
            )
        )
        
        # Note: In a real application, you would create a libp2p host first
        # For this example, we'll show the structure
        
        logger.info("\n📋 Configuration:")
        logger.info(f"  - mDNS Discovery: {config.enable_mdns}")
        logger.info(f"  - Pubsub Discovery: {config.enable_pubsub_discovery}")
        logger.info(f"  - DHT Discovery: {config.enable_dht_discovery}")
        logger.info(f"  - AutoNAT: {config.enable_autonat}")
        logger.info(f"  - Relay Client: {config.enable_relay_client}")
        logger.info(f"  - Relay Server: {config.enable_relay_server}")
        logger.info(f"  - DCUtR: {config.enable_dcutr}")
        
        # Example: Create a mock host for demonstration
        # In practice, use: host = await create_libp2p_host()
        
        class MockHost:
            """Mock libp2p host for demonstration."""
            def get_id(self):
                return "QmExamplePeerId123"
            
            def get_addrs(self):
                return [
                    "/ip4/127.0.0.1/tcp/4001",
                    "/ip4/192.168.1.100/tcp/4001"
                ]
            
            async def connect(self, addr):
                logger.debug(f"Mock connecting to {addr}")
        
        host = MockHost()
        
        logger.info(f"\n🚀 Starting Universal Connectivity Manager...")
        logger.info(f"   Peer ID: {host.get_id()}")
        
        # Create and start the connectivity manager
        manager = uc.UniversalConnectivityManager(host, config)
        
        # Note: In a real application, call await manager.start()
        # For this example, we just show the structure
        
        logger.info("\n✅ Connectivity Manager created successfully!")
        
        # Show what services would be started
        logger.info("\n📡 Services to be started:")
        services = []
        if config.enable_autonat:
            services.append("  - AutoNAT: Detect NAT type and reachability")
        if config.enable_relay_client:
            services.append("  - Relay Client: Use relay servers for connectivity")
        if config.enable_relay_server:
            services.append("  - Relay Server: Act as relay for other peers")
        if config.enable_dcutr:
            services.append("  - DCUtR: Upgrade relayed connections via hole punching")
        if config.enable_pubsub_discovery:
            services.append("  - Pubsub Discovery: Announce on gossipsub topics")
        if config.enable_mdns:
            services.append("  - mDNS: Local network peer discovery")
        
        for service in services:
            logger.info(service)
        
        logger.info("\n🌍 Bootstrap Peers:")
        for i, peer in enumerate(config.bootstrap_peers, 1):
            logger.info(f"  {i}. {peer}")
        
        # Demonstrate API usage
        logger.info("\n📚 Example API Usage:")
        logger.info("  # Get metrics")
        logger.info("  metrics = manager.get_metrics()")
        logger.info("  print(f'Active connections: {metrics.active_connections}')")
        logger.info("  print(f'NAT status: {metrics.nat_status}')")
        logger.info("")
        logger.info("  # Get discovered peers")
        logger.info("  peers = manager.get_discovered_peers()")
        logger.info("  for peer in peers:")
        logger.info("      print(f'Peer: {peer.peer_id}')")
        logger.info("")
        logger.info("  # Dial a peer intelligently")
        logger.info("  success = await manager.dial_peer(")
        logger.info("      peer_id='QmPeer...',")
        logger.info("      addrs=['/ip4/1.2.3.4/tcp/4001'],")
        logger.info("      use_relay=True  # Fallback to relay if needed")
        logger.info("  )")
        
        # Show connection strategy
        logger.info("\n🎯 Connection Strategy:")
        logger.info("  1. Try direct connection to known addresses")
        logger.info("  2. If direct fails, use circuit relay")
        logger.info("  3. Once relayed, attempt DCUtR hole punching")
        logger.info("  4. Discover peers via all enabled mechanisms")
        
        # Show metrics structure
        logger.info("\n📊 Available Metrics:")
        logger.info("  - total_peers_discovered")
        logger.info("  - total_connections_established")
        logger.info("  - total_connections_failed")
        logger.info("  - active_connections")
        logger.info("  - relay_connections")
        logger.info("  - direct_connections")
        logger.info("  - nat_status (public/private/unknown)")
        logger.info("  - dcutr_success_rate")
        
        logger.info("\n" + "=" * 60)
        logger.info("Example completed successfully!")
        logger.info("=" * 60)
        
        logger.info("\n💡 Next Steps:")
        logger.info("  1. Create a libp2p host with your desired configuration")
        logger.info("  2. Initialize UniversalConnectivityManager with the host")
        logger.info("  3. Call await manager.start() to enable all features")
        logger.info("  4. Use manager.dial_peer() for intelligent peer connections")
        logger.info("  5. Monitor metrics with manager.get_metrics()")
        
        logger.info("\n📖 For more information, see:")
        logger.info("  - ipfs_kit_py/libp2p/UNIVERSAL_CONNECTIVITY.md")
        logger.info("  - https://github.com/libp2p/universal-connectivity")
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("Please ensure ipfs_kit_py is installed with libp2p extras:")
        logger.error("  pip install ipfs_kit_py[libp2p]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        logger.info("\n👋 Interrupted by user")
        sys.exit(0)

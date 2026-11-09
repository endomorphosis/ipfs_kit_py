#!/usr/bin/env python3
"""
Example demonstrating WebSocket-based peer discovery with ipfs_kit_py.

This example shows how to:
1. Initialize the ipfs_kit_py high-level API
2. Use WebSocket-based peer discovery
3. Connect to discovered peers
4. Get information about discovered peers

WebSocket-based peer discovery is particularly useful in environments
where traditional IPFS peer discovery methods are limited, such as:
- Browser environments
- Restricted networks with firewalls
- NAT traversal scenarios

Note: This example requires the websockets library:
pip install websockets>=10.4
"""

import os
import time
import json
import anyio
import argparse
from typing import Dict, List, Any, Optional

# Import ipfs_kit_py
try:
    from ipfs_kit_py import ipfs_kit
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py import ipfs_kit

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_websocket_server(port=8765):
    """Run a WebSocket server for peer discovery."""
    # Import required modules
    try:
        from ipfs_kit_py.peer_websocket import PeerWebSocketServer, PeerInfo, PeerRole
    except ImportError:
        logger.error("websockets library not available. Install with: pip install websockets>=10.4")
        return False
        
    # Initialize the ipfs_kit_py library
    kit = ipfs_kit()
    
    # Create local peer info
    try:
        id_info = kit.ipfs_id()
        if not id_info.get("success", False):
            logger.error(f"Failed to get IPFS ID: {id_info.get('error', 'Unknown error')}")
            return False
            
        peer_id = id_info.get("ID", "")
        multiaddrs = id_info.get("Addresses", [])
        
        # Create PeerInfo object
        local_peer_info = PeerInfo(
            peer_id=peer_id,
            multiaddrs=multiaddrs,
            role=PeerRole.MASTER,  # This server is a master node
            capabilities=["discovery", "relay"],
            resources={
                "cpu_count": 4,
                "memory_total": 8 * 1024 * 1024 * 1024,  # 8 GB
                "disk_total": 100 * 1024 * 1024 * 1024  # 100 GB
            },
            metadata={
                "version": "0.1.0",
                "platform": "example"
            }
        )
        
        # Create server
        server = PeerWebSocketServer(
            local_peer_info=local_peer_info,
            max_peers=100,
            heartbeat_interval=30,
            peer_ttl=300
        )
        
        # Start server
        logger.info(f"Starting WebSocket peer discovery server on port {port}...")
        await server.start(host="0.0.0.0", port=port)
        
        # Keep running
        while True:
            await anyio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        await server.stop()
        return True
    except Exception as e:
        logger.error(f"Error running WebSocket server: {e}")
        return False

def discover_peers(discovery_servers=None, timeout=30, max_peers=20):
    """Discover peers using WebSocket-based peer discovery."""
    # Initialize the high-level API
    kit = ipfs_kit()
    api = kit.get_high_level_api()
    
    # Default discovery servers if not specified
    if not discovery_servers:
        discovery_servers = ["ws://localhost:8765"]
        
    logger.info(f"Discovering peers via WebSockets from: {discovery_servers}")
    
    # Find peers
    try:
        result = api.find_peers_websocket(
            discovery_servers=discovery_servers,
            max_peers=max_peers,
            timeout=timeout
        )
        
        if result.get("success", False):
            peers = result.get("peers", [])
            logger.info(f"Found {len(peers)} peers via WebSockets")
            
            # Print peer details
            for i, peer in enumerate(peers):
                logger.info(f"Peer {i+1}/{len(peers)}: {peer['peer_id']}")
                logger.info(f"  Role: {peer.get('role', 'unknown')}")
                logger.info(f"  Addresses: {peer.get('multiaddrs', [])}")
                logger.info(f"  Capabilities: {peer.get('capabilities', [])}")
                logger.info(f"  Success rate: {peer.get('connection_success_rate', 0):.2f}")
                logger.info("-" * 40)
                
            # Return the peer IDs for connection testing
            return [peer["peer_id"] for peer in peers]
        else:
            logger.error(f"Failed to discover peers: {result.get('error', 'Unknown error')}")
            return []
            
    except Exception as e:
        logger.error(f"Error during peer discovery: {e}")
        return []

def connect_to_peers(peer_ids, timeout=30):
    """Connect to discovered peers."""
    if not peer_ids:
        logger.info("No peers to connect to")
        return
        
    # Initialize the high-level API
    kit = ipfs_kit()
    api = kit.get_high_level_api()
    
    successful = 0
    failed = 0
    
    logger.info(f"Connecting to {len(peer_ids)} discovered peers...")
    
    for peer_id in peer_ids:
        # Try to connect
        result = api.connect_to_websocket_peer(peer_id, timeout=timeout)
        
        if result.get("success", False):
            logger.info(f"Successfully connected to peer {peer_id} at {result.get('connected_address')}")
            successful += 1
        else:
            logger.error(f"Failed to connect to peer {peer_id}: {result.get('error', 'Unknown error')}")
            failed += 1
            
    logger.info(f"Connection summary: {successful} successful, {failed} failed")

def get_peer_info(peer_id=None):
    """Get information about discovered peers."""
    # Initialize the high-level API
    kit = ipfs_kit()
    api = kit.get_high_level_api()
    
    # Get peer info
    try:
        if peer_id:
            logger.info(f"Getting information for peer {peer_id}...")
            result = api.get_websocket_peer_info(peer_id)
            
            if result.get("success", False):
                peer = result.get("peer", {})
                logger.info(f"Peer ID: {peer.get('peer_id', 'unknown')}")
                logger.info(f"Role: {peer.get('role', 'unknown')}")
                logger.info(f"Addresses: {peer.get('multiaddrs', [])}")
                logger.info(f"Capabilities: {peer.get('capabilities', [])}")
                logger.info(f"Last seen: {time.ctime(peer.get('last_seen', 0))}")
                logger.info(f"Connection success rate: {peer.get('connection_success_rate', 0):.2f}")
            else:
                logger.error(f"Failed to get peer info: {result.get('error', 'Unknown error')}")
        else:
            logger.info("Getting information for all discovered peers...")
            result = api.get_websocket_peer_info()
            
            if result.get("success", False):
                peers = result.get("peers", {})
                logger.info(f"Found {len(peers)} discovered peers")
                
                for peer_id, peer in peers.items():
                    logger.info(f"Peer ID: {peer.get('peer_id', 'unknown')}")
                    logger.info(f"Role: {peer.get('role', 'unknown')}")
                    logger.info(f"Addresses: {peer.get('multiaddrs', [])}")
                    logger.info(f"Capabilities: {peer.get('capabilities', [])}")
                    logger.info(f"Last seen: {time.ctime(peer.get('last_seen', 0))}")
                    logger.info(f"Connection success rate: {peer.get('connection_success_rate', 0):.2f}")
                    logger.info("-" * 40)
            else:
                logger.error(f"Failed to get peer info: {result.get('error', 'Unknown error')}")
                
    except Exception as e:
        logger.error(f"Error getting peer info: {e}")

def main():
    """Main function to run the example."""
    parser = argparse.ArgumentParser(description="WebSocket peer discovery example")
    parser.add_argument("--server", action="store_true", help="Run as WebSocket discovery server")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default: 8765)")
    parser.add_argument("--discover", action="store_true", help="Discover peers via WebSockets")
    parser.add_argument("--connect", action="store_true", help="Connect to discovered peers")
    parser.add_argument("--info", action="store_true", help="Get info about discovered peers")
    parser.add_argument("--peer-id", type=str, help="Specific peer ID to get info for")
    parser.add_argument("--servers", type=str, help="Comma-separated list of discovery server URLs")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds (default: 30)")
    args = parser.parse_args()
    
    # Check if any action is specified
    if not (args.server or args.discover or args.connect or args.info):
        parser.print_help()
        return
    
    # Extract discovery servers
    discovery_servers = None
    if args.servers:
        discovery_servers = args.servers.split(",")
    
    # Run server mode
    if args.server:
        anyio.run(run_websocket_server(port=args.port))
        return
        
    # Discover peers
    if args.discover:
        discovered_peers = discover_peers(
            discovery_servers=discovery_servers,
            timeout=args.timeout
        )
        
        # Save discovered peers to file for later use
        if discovered_peers:
            with open("discovered_peers.json", "w") as f:
                json.dump(discovered_peers, f)
    
    # Connect to discovered peers
    if args.connect:
        peer_ids = []
        
        # Try to load peers from file
        try:
            with open("discovered_peers.json", "r") as f:
                peer_ids = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("No discovered peers file found. Run with --discover first.")
            
        if peer_ids:
            connect_to_peers(peer_ids, timeout=args.timeout)
        else:
            logger.warning("No peer IDs available for connection")
    
    # Get peer info
    if args.info:
        get_peer_info(args.peer_id)
    
if __name__ == "__main__":
    main()

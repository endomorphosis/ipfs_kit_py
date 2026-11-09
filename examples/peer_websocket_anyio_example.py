"""
Example demonstrating the use of the anyio-based WebSocket peer discovery system.

This example shows how to use the PeerWebSocketServer and PeerWebSocketClient
classes to discover and connect to IPFS peers over WebSockets.

The example:
1. Creates a server that advertises a local peer
2. Creates a client that connects to the server
3. Demonstrates peer discovery and information exchange
4. Shows how to use the anyio backend flexibility

Usage:
    python peer_websocket_anyio_example.py [--backend trio|async-io]
"""

import sys
import time
import anyio
import argparse
from ipfs_kit_py.peer_websocket_anyio import (
    PeerInfo, PeerRole, PeerWebSocketServer, PeerWebSocketClient
)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="WebSocket peer discovery example")
    async_backend = "async" "io"
    parser.add_argument(
        "--backend", 
        choices=[async_backend, "trio"], 
        default=async_backend,
        help="Anyio backend to use (async-io or trio)"
    )
    return parser.parse_args()

class PeerStats:
    """Simple class to track peer discovery statistics."""
    
    def __init__(self):
        self.total_discovered = 0
        self.discovered_peers = set()
        self.start_time = time.time()
        
    def on_peer_discovered(self, peer):
        """Callback for when a peer is discovered."""
        self.total_discovered += 1
        self.discovered_peers.add(peer.peer_id)
        elapsed = time.time() - self.start_time
        print(f"[{elapsed:.1f}s] Discovered peer: {peer.peer_id} ({peer.role})")
        print(f"  - Multiaddrs: {', '.join(peer.multiaddrs)}")
        print(f"  - Capabilities: {', '.join(peer.capabilities)}")
        
    def get_stats(self):
        """Get current statistics."""
        return {
            "total_discovered": self.total_discovered,
            "unique_peers": len(self.discovered_peers),
            "elapsed_time": time.time() - self.start_time
        }

async def run_server_example():
    """Run the WebSocket server example."""
    print("Starting WebSocket peer discovery server...")
    
    # Create a local peer info for the server
    server_peer = PeerInfo(
        peer_id="example-server-peer",
        multiaddrs=[
            "/ip4/127.0.0.1/tcp/4001/p2p/example-server-peer",
            "/ip4/192.168.1.100/tcp/4001/p2p/example-server-peer"
        ],
        role=PeerRole.MASTER,
        capabilities=["ipfs", "ipfs_cluster", "tiered_cache"],
        resources={
            "cpu_cores": 4,
            "memory_gb": 16,
            "disk_gb": 1000
        },
        metadata={
            "version": "1.0.0",
            "platform": "linux",
            "uptime": 3600
        }
    )
    
    # Create and start the server
    server = PeerWebSocketServer(
        local_peer_info=server_peer,
        max_peers=100,
        heartbeat_interval=30,
        peer_ttl=300
    )
    
    # Use a nursery/task group to manage server lifecycle
    async with anyio.create_task_group() as tg:
        # Start the server in the background
        await server.start(host="127.0.0.1", port=9876)
        print(f"Server running at ws://127.0.0.1:9876")
        
        # Keep the server running until cancelled
        try:
            # Use a signal to keep the server running
            # Wait for cancellation signal
            print("Server running (press Ctrl+C to stop)")
            shutdown_event = anyio.Event()
            
            # Set up signal handler for graceful shutdown
            async def handle_signal():
                with anyio.CancelScope() as scope:
                    print("Shutdown signal received.")
                    scope.cancel()
                    shutdown_event.set()
            
            tg.start_soon(anyio.to_thread.run_sync, lambda: input("Press Enter to stop the server...\n"))
            await shutdown_event.wait()
            
        finally:
            # Clean shutdown
            print("Stopping server...")
            await server.stop()
            print("Server stopped")

async def run_client_example():
    """Run the WebSocket client example."""
    print("Starting WebSocket peer discovery client...")
    
    # Create stats tracker
    stats = PeerStats()
    
    # Create a local peer info for the client
    client_peer = PeerInfo(
        peer_id="example-client-peer",
        multiaddrs=[
            "/ip4/127.0.0.1/tcp/4002/p2p/example-client-peer",
        ],
        role=PeerRole.WORKER,
        capabilities=["ipfs", "tiered_cache"],
        resources={
            "cpu_cores": 2,
            "memory_gb": 8,
            "disk_gb": 500
        },
        metadata={
            "version": "1.0.0",
            "platform": "linux",
            "uptime": 1800
        }
    )
    
    # Create and start the client
    client = PeerWebSocketClient(
        local_peer_info=client_peer,
        on_peer_discovered=stats.on_peer_discovered,
        auto_connect=True,
        reconnect_interval=5,
        max_reconnect_attempts=5
    )
    
    # Use a nursery/task group to manage client lifecycle
    async with anyio.create_task_group() as tg:
        # Start the client
        await client.start()
        print("Client started")
        
        # Connect to the local server
        server_url = "ws://127.0.0.1:9876"
        success = await client.connect_to_discovery_server(server_url)
        if success:
            print(f"Connected to discovery server at {server_url}")
        else:
            print(f"Failed to connect to discovery server at {server_url}")
            return
        
        # Run for a while to demonstrate peer discovery
        try:
            # Wait for a while, showing periodic stats
            for i in range(6):
                await anyio.sleep(5)
                current_stats = stats.get_stats()
                print(f"\nCurrent peer discovery stats:")
                print(f"  - Total discoveries: {current_stats['total_discovered']}")
                print(f"  - Unique peers: {current_stats['unique_peers']}")
                print(f"  - Running for: {current_stats['elapsed_time']:.1f} seconds")
                
                # Get and display current peers
                peers = client.get_discovered_peers()
                print(f"Currently tracking {len(peers)} peers:")
                for peer in peers:
                    print(f"  - {peer.peer_id} ({peer.role})")
        
        finally:
            # Clean shutdown
            print("\nStopping client...")
            await client.stop()
            print("Client stopped")

async def run_bidirectional_example():
    """Run both client and server in the same process."""
    print("Starting bidirectional peer discovery example...")
    
    # Create server peer
    server_peer = PeerInfo(
        peer_id="example-server-peer",
        multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/example-server-peer"],
        role=PeerRole.MASTER,
        capabilities=["ipfs", "ipfs_cluster"]
    )
    
    # Create client peer
    client_peer = PeerInfo(
        peer_id="example-client-peer",
        multiaddrs=["/ip4/127.0.0.1/tcp/4002/p2p/example-client-peer"],
        role=PeerRole.WORKER,
        capabilities=["ipfs"]
    )
    
    # Create stats tracker for client
    stats = PeerStats()
    
    # Use a nursery/task group to manage both components
    async with anyio.create_task_group() as tg:
        # Create and start server
        server = PeerWebSocketServer(server_peer)
        await server.start(host="127.0.0.1", port=9876)
        print("Server started on ws://127.0.0.1:9876")
        
        # Create and start client
        client = PeerWebSocketClient(
            local_peer_info=client_peer,
            on_peer_discovered=stats.on_peer_discovered
        )
        await client.start()
        print("Client started")
        
        # Connect client to server
        await client.connect_to_discovery_server("ws://127.0.0.1:9876")
        print("Client connected to server")
        
        # Wait for discovery to happen
        await anyio.sleep(2)
        
        # Print discovered peers
        peers = client.get_discovered_peers()
        print(f"Discovered {len(peers)} peers:")
        for peer in peers:
            print(f"  - {peer.peer_id} ({peer.role})")
            print(f"    Multiaddrs: {', '.join(peer.multiaddrs)}")
            print(f"    Capabilities: {', '.join(peer.capabilities)}")
        
        # Clean up client and server
        print("Stopping client and server...")
        await client.stop()
        await server.stop()
        print("Client and server stopped")

async def run_full_example():
    """Run the full example."""
    print("="*60)
    print("WEBSOCKET PEER DISCOVERY EXAMPLE (ANYIO VERSION)")
    print("="*60)
    print("This example demonstrates the anyio-based WebSocket peer discovery implementation.")
    print("It will run a server and client, showing how peers discover each other.")
    print("-"*60)
    
    # Ask the user which example to run
    print("\nPlease choose an example to run:")
    print("1. Run server only")
    print("2. Run client only (requires a running server)")
    print("3. Run bidirectional example (client + server)")
    
    choice = input("Enter choice (default: 3): ").strip() or "3"
    
    if choice == "1":
        await run_server_example()
    elif choice == "2":
        await run_client_example()
    elif choice == "3":
        await run_bidirectional_example()
    else:
        print(f"Invalid choice: {choice}")

def main():
    """Main entry point."""
    args = parse_args()
    print(f"Using anyio with {args.backend} backend")
    
    # Run the example with the specified backend
    anyio.run(run_full_example, backend=args.backend)

if __name__ == "__main__":
    main()
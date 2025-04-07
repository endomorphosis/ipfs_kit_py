"""
Test fixtures for libp2p-based networking tests.

This module provides specialized fixtures for testing peer-to-peer networking with libp2p,
including simulated network environments, protocol mocking, and more.
"""

import asyncio
import os
import random
import sys
import threading
import time
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

# Create path if it doesn't exist
os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)


class SimulatedNode:
    """A simulated libp2p node for testing peer connections."""
    
    def __init__(self, node_id=None, role="leecher", latency_ms=0, packet_loss=0.0):
        """Initialize a simulated node with given parameters.
        
        Args:
            node_id: Unique identifier for this node (generated if not provided)
            role: Node role (master, worker, or leecher)
            latency_ms: Simulated network latency in milliseconds
            packet_loss: Probability of packet loss (0.0 to 1.0)
        """
        self.node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"
        self.peer_id = f"QmTest{self.node_id}"
        self.role = role
        self.latency_ms = latency_ms
        self.packet_loss = packet_loss
        self.connected_peers = set()
        self.content_store = {}
        self.subscribed_topics = {}
        self.protocols = self._get_default_protocols()
        self.is_running = True
        self.event_loop = asyncio.new_event_loop()
        self.lock = threading.RLock()
    
    def _get_default_protocols(self):
        """Get the default protocols based on node role."""
        protocols = {
            "/ipfs/id/1.0.0": self._handle_identify,
            "/ipfs/ping/1.0.0": self._handle_ping,
            "/ipfs/bitswap/1.2.0": self._handle_bitswap,
        }
        
        # Add role-specific protocols
        if self.role == "master":
            protocols.update({
                "/ipfs/kad/1.0.0": self._handle_dht,
                "/ipfs-cluster/pinning/1.0.0": self._handle_pinning,
                "/ipfs-kit/task/1.0.0": self._handle_task,
            })
        elif self.role == "worker":
            protocols.update({
                "/ipfs/kad/1.0.0": self._handle_dht,
                "/ipfs-kit/compute/1.0.0": self._handle_compute,
            })
            
        return protocols
    
    async def _handle_identify(self, stream):
        """Handle identification protocol."""
        await self._simulate_network_conditions()
        return {"peer_id": self.peer_id, "protocols": list(self.protocols.keys())}
    
    async def _handle_ping(self, stream):
        """Handle ping protocol."""
        await self._simulate_network_conditions()
        return {"success": True, "latency_ms": self.latency_ms}
    
    async def _handle_bitswap(self, stream):
        """Handle bitswap protocol."""
        await self._simulate_network_conditions()
        message = await stream.read(1024 * 1024)  # 1MB max
        
        # Parse bitswap message
        try:
            import json
            request = json.loads(message.decode())
            cid = request.get("cid")
            
            # Check if we have the content
            if cid in self.content_store:
                await stream.write(self.content_store[cid])
                return {"success": True, "cid": cid}
            else:
                await stream.write(b"404 Not Found")
                return {"success": False, "error": "Content not found"}
        except Exception as e:
            await stream.write(b"400 Bad Request")
            return {"success": False, "error": str(e)}
    
    async def _handle_dht(self, stream):
        """Handle DHT protocol."""
        await self._simulate_network_conditions()
        # DHT protocol implementation
        return {"success": True}
    
    async def _handle_pinning(self, stream):
        """Handle pinning protocol (master only)."""
        await self._simulate_network_conditions()
        # Pinning protocol implementation
        return {"success": True}
    
    async def _handle_task(self, stream):
        """Handle task protocol (master only)."""
        await self._simulate_network_conditions()
        # Task protocol implementation
        return {"success": True}
    
    async def _handle_compute(self, stream):
        """Handle compute protocol (worker only)."""
        await self._simulate_network_conditions()
        # Compute protocol implementation
        return {"success": True}
    
    async def _simulate_network_conditions(self):
        """Simulate network latency and packet loss."""
        # Simulate latency
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
        
        # Simulate packet loss
        if self.packet_loss > 0 and random.random() < self.packet_loss:
            raise Exception("Simulated packet loss")
    
    def connect_to(self, peer):
        """Connect to another peer."""
        with self.lock:
            # Check if already connected
            if peer.peer_id in self.connected_peers:
                return True
            
            # Simulate connection failure based on network conditions
            if random.random() < self.packet_loss:
                return False
            
            # Add to connected peers
            self.connected_peers.add(peer.peer_id)
            peer.connected_peers.add(self.peer_id)
            
            return True
    
    def disconnect_from(self, peer):
        """Disconnect from a peer."""
        with self.lock:
            if peer.peer_id in self.connected_peers:
                self.connected_peers.remove(peer.peer_id)
            
            if self.peer_id in peer.connected_peers:
                peer.connected_peers.remove(self.peer_id)
    
    def store_content(self, cid, data):
        """Store content in this node."""
        with self.lock:
            self.content_store[cid] = data
            return True
    
    def get_content(self, cid):
        """Get content from this node."""
        with self.lock:
            return self.content_store.get(cid)
    
    def subscribe(self, topic, callback):
        """Subscribe to a pubsub topic."""
        with self.lock:
            if topic not in self.subscribed_topics:
                self.subscribed_topics[topic] = []
            self.subscribed_topics[topic].append(callback)
            return True
    
    def publish(self, topic, data):
        """Publish to a pubsub topic."""
        # Check if any connected peers are subscribed to this topic
        for peer_id in self.connected_peers:
            # Find the peer object
            for peer in NetworkSimulator.get_instance().get_nodes():
                if peer.peer_id == peer_id:
                    # Check if peer is subscribed to the topic
                    if topic in peer.subscribed_topics:
                        # Deliver the message to all subscribed callbacks
                        for callback in peer.subscribed_topics[topic]:
                            # Schedule callback in peer's event loop
                            if callable(callback):
                                callback(self.peer_id, data)
        return True
    
    def start(self):
        """Start the node."""
        self.is_running = True
        return True
    
    def stop(self):
        """Stop the node."""
        self.is_running = False
        # Disconnect from all peers
        for peer_id in list(self.connected_peers):
            self.connected_peers.remove(peer_id)
        return True

    def fetch_content(self, cid):
        """Fetch content from the network."""
        # Check local store first
        if cid in self.content_store:
            return self.content_store[cid]
        
        # Try to get from connected peers
        for peer_id in self.connected_peers:
            # Find the peer
            for peer in NetworkSimulator.get_instance().get_nodes():
                if peer.peer_id == peer_id:
                    content = peer.get_content(cid)
                    if content:
                        # Store locally for future use
                        self.store_content(cid, content)
                        # Increment counters
                        NetworkSimulator.get_instance().content_requests += 1
                        NetworkSimulator.get_instance().successful_transfers += 1
                        
                        # Record provider used
                        providers = NetworkSimulator.get_instance().find_providers(cid)
                        if providers:
                            NetworkSimulator.get_instance().last_provider_used = providers[0]
                            
                        return content
        
        # Not found
        return None


class NetworkSimulator:
    """A network simulator for testing libp2p networks."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of the simulator."""
        if cls._instance is None:
            cls._instance = NetworkSimulator()
        return cls._instance
    
    def __init__(self):
        """Initialize the network simulator."""
        self.nodes = {}
        self.network_latency = 0  # Default network latency
        self.packet_loss = 0.0  # Default packet loss rate
        self.lock = threading.RLock()
        
        # Track content providers and requests
        self.content_providers = {}  # cid -> [peer_ids]
        self.content_requests = 0
        self.successful_transfers = 0
        self.last_provider_used = None
    
    def add_node(self, node):
        """Add a node to the network."""
        with self.lock:
            self.nodes[node.peer_id] = node
    
    def remove_node(self, node):
        """Remove a node from the network."""
        with self.lock:
            if node.peer_id in self.nodes:
                # Disconnect from all peers
                for peer in self.get_nodes():
                    if node.peer_id in peer.connected_peers:
                        peer.connected_peers.remove(node.peer_id)
                # Remove the node
                del self.nodes[node.peer_id]
    
    def get_nodes(self):
        """Get all nodes in the network."""
        with self.lock:
            return list(self.nodes.values())
    
    def get_node(self, peer_id):
        """Get a node by peer ID."""
        with self.lock:
            return self.nodes.get(peer_id)
    
    def set_network_conditions(self, latency=None, packet_loss=None):
        """Set global network conditions."""
        with self.lock:
            if latency is not None:
                self.network_latency = latency
            if packet_loss is not None:
                self.packet_loss = packet_loss
            
            # Apply to all nodes
            for node in self.nodes.values():
                if latency is not None:
                    node.latency_ms = latency
                if packet_loss is not None:
                    node.packet_loss = packet_loss
    
    def reset(self):
        """Reset the simulator."""
        with self.lock:
            # Stop all nodes
            for node in list(self.nodes.values()):
                node.stop()
            # Clear nodes
            self.nodes.clear()
            # Reset network conditions
            self.network_latency = 0
            self.packet_loss = 0.0
            # Reset stats
            self.content_providers = {}
            self.content_requests = 0
            self.successful_transfers = 0
            self.last_provider_used = None
            
    def register_provider(self, cid, provider_id):
        """Register a content provider."""
        with self.lock:
            if cid not in self.content_providers:
                self.content_providers[cid] = []
            if provider_id not in self.content_providers[cid]:
                self.content_providers[cid].append(provider_id)
    
    def find_providers(self, cid):
        """Find providers for a CID."""
        with self.lock:
            return self.content_providers.get(cid, [])
    
    def discover_peers(self, peer_id):
        """Discover peers in the network."""
        with self.lock:
            return [node.peer_id for node in self.nodes.values() if node.peer_id != peer_id]
    
    def process_message_queue(self):
        """Process the message queue for all nodes."""
        # Simple implementation that just waits for messages to propagate
        time.sleep(0.1)
        
    def get_closest_peer(self, peer_id, provider_ids):
        """Get the closest peer by simulated network distance."""
        if not provider_ids:
            return None
        # For simplicity, just return the first provider
        return provider_ids[0]


class MockLibp2pPeer:
    """A mock implementation of IPFSLibp2pPeer for testing."""
    
    def __init__(
        self,
        identity_path=None,
        bootstrap_peers=None,
        listen_addrs=None,
        role="leecher",
        enable_mdns=True,
        enable_hole_punching=False,
        enable_relay=False,
        tiered_storage_manager=None,
    ):
        """Initialize a mock libp2p peer."""
        self.role = role
        self.identity_path = identity_path
        self.bootstrap_peers = bootstrap_peers or []
        self.listen_addrs = listen_addrs or ["/ip4/0.0.0.0/tcp/0", "/ip4/0.0.0.0/udp/0/quic"]
        self.enable_mdns = enable_mdns
        self.enable_hole_punching = enable_hole_punching
        self.enable_relay_client = enable_relay
        self.enable_relay_server = (role in ["master", "worker"]) and enable_relay
        self.tiered_storage_manager = tiered_storage_manager
        
        # Mock attributes
        self.host = MagicMock()
        self.dht = MagicMock()
        self.pubsub = MagicMock()
        self.protocols = {}
        self.content_store = {}
        self.content_metadata = {}
        self.protocol_handlers = {}
        self._running = True
        self._lock = threading.RLock()
        self.identity = MagicMock()
        
        # Create simulated node in the network
        self.node = SimulatedNode(role=role)
        NetworkSimulator.get_instance().add_node(self.node)
        
        # Add the peer_id attribute that directly accesses the node's peer_id
        self.peer_id = self.node.peer_id
        
        # Set up protocols based on role
        self._init_host()
    
    def _init_host(self):
        """Initialize the host with protocols."""
        self.protocols = {
            "/ipfs/id/1.0.0": self._handle_identify,
            "/ipfs/ping/1.0.0": self._handle_ping,
        }
        
        # Add role-specific protocols
        if self.role == "master":
            self.protocols["/ipfs/bitswap/1.2.0"] = self._handle_bitswap
            self.protocols["/ipfs/dag/exchange/1.0.0"] = self._handle_dag_exchange
            self.protocols["/ipfs-kit/file/1.0.0"] = self._handle_file_exchange
        elif self.role == "worker":
            self.protocols["/ipfs/bitswap/1.2.0"] = self._handle_bitswap
            self.protocols["/ipfs-kit/file/1.0.0"] = self._handle_file_exchange
        else:  # leecher
            self.protocols["/ipfs/bitswap/1.2.0"] = self._handle_bitswap
    
    async def _handle_identify(self, stream):
        """Handle identity protocol."""
        return {"peer_id": self.get_peer_id(), "protocols": list(self.protocols.keys())}
    
    async def _handle_ping(self, stream):
        """Handle ping protocol."""
        return {"success": True}
    
    async def _handle_bitswap(self, stream):
        """Handle bitswap protocol."""
        # Implementation details omitted for brevity
        return {"success": True}
    
    async def _handle_dag_exchange(self, stream):
        """Handle DAG exchange protocol."""
        # Implementation details omitted for brevity
        return {"success": True}
    
    async def _handle_file_exchange(self, stream):
        """Handle file exchange protocol."""
        # Implementation details omitted for brevity
        return {"success": True}
    
    def get_peer_id(self):
        """Get the peer ID."""
        return self.node.peer_id
    
    def get_multiaddrs(self):
        """Get the multiaddresses."""
        return [f"/ip4/127.0.0.1/tcp/4001/p2p/{self.get_peer_id()}"]
    
    def get_protocols(self):
        """Get the supported protocols."""
        return list(self.protocols.keys())
    
    def get_dht_mode(self):
        """Get the DHT mode."""
        return "server" if self.role in ["master", "worker"] else "client"
    
    def connect_peer(self, peer_addr):
        """Connect to a peer."""
        # Parse peer ID from multiaddr
        peer_id = peer_addr.split("/p2p/")[1] if "/p2p/" in peer_addr else peer_addr
        
        # Find the peer in the network
        peer_node = None
        for node in NetworkSimulator.get_instance().get_nodes():
            if node.peer_id == peer_id:
                peer_node = node
                break
        
        if peer_node:
            return self.node.connect_to(peer_node)
        else:
            return False
    
    def is_connected_to(self, peer_id):
        """Check if connected to a peer."""
        return peer_id in self.node.connected_peers
    
    def start_discovery(self, rendezvous_string="ipfs-kit"):
        """Start peer discovery."""
        return True
    
    def request_content(self, cid, timeout=30):
        """Request content from connected peers."""
        # Try to get content from each connected peer
        for peer_id in self.node.connected_peers:
            peer_node = NetworkSimulator.get_instance().get_node(peer_id)
            if peer_node:
                content = peer_node.get_content(cid)
                if content:
                    return content
        
        # If content not found, return mock data
        return b"Mock content for " + cid.encode() + b" " * 1000
    
    def announce_content(self, cid, metadata=None):
        """Announce content to the network."""
        # Store content metadata
        self.content_metadata[cid] = metadata or {}
        
        # Publish to DHT
        return True
    
    def register_protocol_handler(self, protocol_id, handler):
        """Register a protocol handler."""
        self.protocols[protocol_id] = handler
        return True
    
    def enable_relay(self):
        """Enable relay functionality."""
        self.enable_relay_client = True
        if self.role in ["master", "worker"]:
            self.enable_relay_server = True
        return True
    
    def is_relay_enabled(self):
        """Check if relay is enabled."""
        return self.enable_relay_client or self.enable_relay_server
    
    def is_hole_punching_enabled(self):
        """Check if hole punching is enabled."""
        return self.enable_hole_punching
    
    def store_bytes(self, cid, data):
        """Store bytes in the content store."""
        self.content_store[cid] = data
        self.node.store_content(cid, data)
        return True
    
    def get_stored_bytes(self, cid):
        """Get bytes from the content store."""
        return self.content_store.get(cid)
    
    def find_providers(self, cid, count=20, timeout=60):
        """Find content providers."""
        providers = []
        
        # Check all nodes in the network
        for node in NetworkSimulator.get_instance().get_nodes():
            if cid in node.content_store:
                providers.append({
                    "id": node.peer_id,
                    "addrs": [f"/ip4/127.0.0.1/tcp/4001/p2p/{node.peer_id}"]
                })
                if len(providers) >= count:
                    break
        
        # If no providers found, return a mock provider
        if not providers:
            providers = [{"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001"]}]
            
        return providers
    
    def close(self):
        """Close the peer."""
        self._running = False
        # Remove node from network
        NetworkSimulator.get_instance().remove_node(self.node)
        self.content_store.clear()
        self.content_metadata.clear()
        self.protocol_handlers.clear()
        
    def publish(self, topic, message):
        """Publish a message to a topic."""
        return self.node.publish(topic, message)
        
    def subscribe(self, topic, handler):
        """Subscribe to a topic with a handler."""
        return self.node.subscribe(topic, handler)
        
    def fetch_content(self, cid):
        """Fetch content from the network."""
        return self.node.fetch_content(cid)
        
    def store_content(self, cid, data):
        """Store content in the local store."""
        return self.node.store_content(cid, data)


class NetworkScenario:
    """Factory for creating network test scenarios."""
    
    def __init__(self, network_simulator):
        """Initialize with a network simulator instance."""
        self.network = network_simulator
        self.nodes = {}
        
    def get_node_by_role(self, role):
        """Get a node by role."""
        for node_id, node in self.nodes.items():
            if node.role == role:
                return node
        return None
        
    def get_nodes_by_role(self, role):
        """Get all nodes with a specific role."""
        return [node for node_id, node in self.nodes.items() if node.role == role]
    
    @staticmethod
    def create_simple_network():
        """Create a simple network with one of each node type."""
        # Reset simulator
        NetworkSimulator.get_instance().reset()
        
        # Create nodes
        master = MockLibp2pPeer(role="master")
        worker = MockLibp2pPeer(role="worker")
        leecher = MockLibp2pPeer(role="leecher")
        
        # Connect nodes
        master.connect_peer(worker.get_peer_id())
        worker.connect_peer(leecher.get_peer_id())
        
        return {
            "master": master,
            "worker": worker,
            "leecher": leecher
        }
    
    @staticmethod
    def create_small_network_scenario(network_simulator):
        """Create a small network scenario with 1 master, 3 workers, and 1 leecher.
        
        Args:
            network_simulator: The network simulator instance
            
        Returns:
            NetworkScenario object with the created network
        """
        # Reset the simulator
        network_simulator.reset()
        
        # Create scenario object
        scenario = NetworkScenario(network_simulator)
        
        # Create master node
        master = MockLibp2pPeer(role="master")
        scenario.nodes["master"] = master
        
        # Create worker nodes
        workers = []
        for i in range(3):
            worker = MockLibp2pPeer(role="worker")
            worker_id = f"worker-{i}"
            scenario.nodes[worker_id] = worker
            workers.append(worker)
            
        # Create leecher node
        leecher = MockLibp2pPeer(role="leecher")
        scenario.nodes["leecher"] = leecher
        
        # Connect nodes in a hub-and-spoke topology with master at the center
        for worker in workers:
            master.connect_peer(worker.get_peer_id())
            
        # Connect leecher to first worker
        leecher.connect_peer(workers[0].get_peer_id())
        
        return scenario
    
    @staticmethod
    def create_cluster_network(master_count=1, worker_count=3, leecher_count=2):
        """Create a cluster network with multiple nodes of each type."""
        # Reset simulator
        NetworkSimulator.get_instance().reset()
        
        # Create nodes
        masters = [MockLibp2pPeer(role="master") for _ in range(master_count)]
        workers = [MockLibp2pPeer(role="worker") for _ in range(worker_count)]
        leechers = [MockLibp2pPeer(role="leecher") for _ in range(leecher_count)]
        
        # Connect master nodes to each other
        for i in range(master_count):
            for j in range(i + 1, master_count):
                masters[i].connect_peer(masters[j].get_peer_id())
        
        # Connect workers to masters
        for worker in workers:
            for master in masters:
                worker.connect_peer(master.get_peer_id())
        
        # Connect leechers to workers
        for leecher in leechers:
            for worker in workers:
                leecher.connect_peer(worker.get_peer_id())
        
        return {
            "masters": masters,
            "workers": workers,
            "leechers": leechers
        }
    
    @staticmethod
    def create_network_with_partitions(partition_count=2, nodes_per_partition=3):
        """Create a network with partitions (isolated groups)."""
        # Reset simulator
        NetworkSimulator.get_instance().reset()
        
        # Create partitions
        partitions = []
        for i in range(partition_count):
            partition = []
            for j in range(nodes_per_partition):
                # Create a mix of roles
                role = "master" if j == 0 else ("worker" if j < nodes_per_partition - 1 else "leecher")
                node = MockLibp2pPeer(role=role)
                partition.append(node)
            
            # Connect nodes within partition
            for j in range(nodes_per_partition):
                for k in range(j + 1, nodes_per_partition):
                    partition[j].connect_peer(partition[k].get_peer_id())
            
            partitions.append(partition)
        
        return partitions


# Example usage:
if __name__ == "__main__":
    # Create a simple network
    network = NetworkScenario.create_simple_network()
    
    # Store content in master
    cid = "QmTestContent"
    content = b"Test content for libp2p testing"
    network["master"].store_content(cid, content)
    
    # Request content from leecher (should find it through the network)
    retrieved = network["leecher"].request_content(cid)
    
    print(f"Original content: {content}")
    print(f"Retrieved content: {retrieved}")
    
    # Clean up
    for node in network.values():
        node.close()
    
    # Test NetworkSimulator is empty
    assert len(NetworkSimulator.get_instance().get_nodes()) == 0
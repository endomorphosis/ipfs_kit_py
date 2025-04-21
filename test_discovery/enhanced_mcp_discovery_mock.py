"""Enhanced MCP Discovery Mock

This module provides enhanced mock implementations for MCP discovery functionality
with network simulation capabilities for comprehensive testing.
"""

import logging
import asyncio
import random
import time
from typing import Dict, List, Optional, Any, Callable, Set, Tuple

from .mcp_discovery_mock import MCPDiscoveryMock

logger = logging.getLogger(__name__)


class MockNetwork:
    """
    Mock network that simulates peer-to-peer communication.
    
    This class provides a simulated network environment for testing peer discovery
    and communication with configurable latency, packet loss, and other real-world
    network characteristics.
    """
    
    def __init__(
        self,
        latency_ms: int = 50,
        packet_loss_percent: float = 0.0,
        partition_probability: float = 0.0,
        jitter_ms: int = 10
    ):
        """Initialize the mock network."""
        self.nodes = {}  # node_id -> node
        self.connections = {}  # (from_id, to_id) -> connection_properties
        self.partitions = []  # list of sets of node_ids that can communicate
        self.latency_ms = latency_ms
        self.packet_loss_percent = packet_loss_percent
        self.partition_probability = partition_probability
        self.jitter_ms = jitter_ms
        self.message_log = []
        
        logger.info(f"Mock network initialized with latency={latency_ms}ms, "
                   f"packet_loss={packet_loss_percent}%, "
                   f"partition_prob={partition_probability}, "
                   f"jitter={jitter_ms}ms")
    
    def add_node(self, node_id: str, node: Any) -> None:
        """Add a node to the network."""
        self.nodes[node_id] = node
        
        # When a new node is added, connect it to all existing nodes
        for existing_id in self.nodes:
            if existing_id != node_id:
                self.connect(node_id, existing_id)
        
        # Update network partitions
        self._update_partitions()
        
        logger.info(f"Added node {node_id} to the network")
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the network."""
        if node_id not in self.nodes:
            logger.warning(f"Node {node_id} not found in network")
            return False
        
        # Remove the node
        del self.nodes[node_id]
        
        # Remove all connections involving this node
        connections_to_remove = []
        for connection in self.connections:
            if node_id in connection:
                connections_to_remove.append(connection)
        
        for connection in connections_to_remove:
            del self.connections[connection]
        
        # Update network partitions
        self._update_partitions()
        
        logger.info(f"Removed node {node_id} from the network")
        return True
    
    def connect(self, node_id1: str, node_id2: str) -> bool:
        """Connect two nodes in the network."""
        if node_id1 not in self.nodes or node_id2 not in self.nodes:
            logger.warning(f"Cannot connect: node {node_id1} or {node_id2} not found")
            return False
        
        # Create bidirectional connections
        self.connections[(node_id1, node_id2)] = {
            "latency_ms": self.latency_ms + random.randint(-self.jitter_ms, self.jitter_ms),
            "packet_loss": self.packet_loss_percent,
            "bandwidth_kbps": 1000  # Default 1 Mbps
        }
        
        self.connections[(node_id2, node_id1)] = {
            "latency_ms": self.latency_ms + random.randint(-self.jitter_ms, self.jitter_ms),
            "packet_loss": self.packet_loss_percent,
            "bandwidth_kbps": 1000  # Default 1 Mbps
        }
        
        # Update network partitions
        self._update_partitions()
        
        logger.info(f"Connected nodes {node_id1} and {node_id2}")
        return True
    
    def disconnect(self, node_id1: str, node_id2: str) -> bool:
        """Disconnect two nodes in the network."""
        if (node_id1, node_id2) not in self.connections or (node_id2, node_id1) not in self.connections:
            logger.warning(f"Connection between {node_id1} and {node_id2} not found")
            return False
        
        # Remove bidirectional connections
        del self.connections[(node_id1, node_id2)]
        del self.connections[(node_id2, node_id1)]
        
        # Update network partitions
        self._update_partitions()
        
        logger.info(f"Disconnected nodes {node_id1} and {node_id2}")
        return True
    
    def _update_partitions(self) -> None:
        """Update network partitions based on current connections."""
        if self.partition_probability <= 0:
            # No partitioning, all nodes in one partition
            if self.nodes:
                self.partitions = [set(self.nodes.keys())]
            else:
                self.partitions = []
            return
        
        # Use a simple algorithm to determine connected components (partitions)
        visited = set()
        new_partitions = []
        
        for node_id in self.nodes:
            if node_id in visited:
                continue
            
            # Start a new partition with this node
            partition = {node_id}
            queue = [node_id]
            visited.add(node_id)
            
            # BFS to find all connected nodes
            while queue:
                current = queue.pop(0)
                for other in self.nodes:
                    if other in visited:
                        continue
                    
                    # Check if there's a connection between current and other
                    if (current, other) in self.connections:
                        # Apply partitioning probability
                        if random.random() >= self.partition_probability:
                            queue.append(other)
                            partition.add(other)
                            visited.add(other)
            
            new_partitions.append(partition)
        
        self.partitions = new_partitions
        logger.info(f"Network partitioned into {len(self.partitions)} groups")
    
    async def send_message(
        self, 
        from_id: str, 
        to_id: str, 
        message: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Send a message from one node to another."""
        # Check if nodes exist
        if from_id not in self.nodes or to_id not in self.nodes:
            logger.warning(f"Cannot send message: node {from_id} or {to_id} not found")
            return False, None
        
        # Check if nodes are connected
        if (from_id, to_id) not in self.connections:
            logger.warning(f"Cannot send message: nodes {from_id} and {to_id} are not connected")
            return False, None
        
        # Check if nodes are in the same partition
        in_same_partition = False
        for partition in self.partitions:
            if from_id in partition and to_id in partition:
                in_same_partition = True
                break
        
        if not in_same_partition:
            logger.warning(f"Cannot send message: nodes {from_id} and {to_id} are in different network partitions")
            return False, None
        
        # Apply packet loss
        if random.random() < self.connections[(from_id, to_id)]["packet_loss"] / 100:
            logger.info(f"Message from {from_id} to {to_id} dropped due to packet loss")
            return False, None
        
        # Apply latency
        latency = self.connections[(from_id, to_id)]["latency_ms"] / 1000.0
        await asyncio.sleep(latency)
        
        # Log the message
        self.message_log.append({
            "from": from_id,
            "to": to_id,
            "message": message,
            "timestamp": time.time()
        })
        
        # Create a response message
        response = {
            "success": True,
            "message": "Message delivered successfully",
            "timestamp": time.time()
        }
        
        logger.info(f"Message sent from {from_id} to {to_id}: {message}")
        return True, response
    
    def create_partition(self, node_ids: List[str]) -> bool:
        """
        Create a network partition containing the specified nodes.
        
        All nodes in the list will be able to communicate with each other,
        but not with nodes outside the list.
        """
        # Verify all nodes exist
        for node_id in node_ids:
            if node_id not in self.nodes:
                logger.warning(f"Cannot create partition: node {node_id} not found")
                return False
        
        # Create a new set of node IDs for this partition
        new_partition = set(node_ids)
        
        # Remove these nodes from any existing partitions
        for partition in self.partitions:
            partition -= new_partition
        
        # Remove empty partitions
        self.partitions = [p for p in self.partitions if p]
        
        # Add the new partition
        self.partitions.append(new_partition)
        
        logger.info(f"Created network partition with nodes: {node_ids}")
        return True
    
    def heal_partitions(self) -> None:
        """
        Heal all network partitions.
        
        After calling this method, all nodes will be in a single partition
        and able to communicate with each other.
        """
        if not self.nodes:
            self.partitions = []
            return
        
        # Create a single partition with all nodes
        self.partitions = [set(self.nodes.keys())]
        self.partition_probability = 0.0
        
        logger.info("Healed all network partitions")
    
    def get_message_log(self) -> List[Dict[str, Any]]:
        """Get the log of all messages sent through the network."""
        return self.message_log
    
    def clear_message_log(self) -> None:
        """Clear the message log."""
        self.message_log = []
        logger.info("Message log cleared")
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get the current status of the network."""
        return {
            "nodes": list(self.nodes.keys()),
            "connections": list(self.connections.keys()),
            "partitions": [list(p) for p in self.partitions],
            "config": {
                "latency_ms": self.latency_ms,
                "packet_loss_percent": self.packet_loss_percent,
                "partition_probability": self.partition_probability,
                "jitter_ms": self.jitter_ms
            }
        }


class EnhancedMCPDiscoveryMock(MCPDiscoveryMock):
    """
    Enhanced MCP discovery mock with network simulation.
    
    This class extends the basic MCP discovery mock with network simulation
    capabilities for more realistic and comprehensive testing scenarios.
    """
    
    def __init__(
        self,
        network: Optional[MockNetwork] = None,
        node_id: str = "mock-node-1"
    ):
        """Initialize the enhanced MCP discovery mock."""
        super().__init__()
        self.network = network or MockNetwork()
        self.node_id = node_id
        self.connected_peers = set()
        self.offline = False
        
        # Register this node with the network
        self.network.add_node(self.node_id, self)
        
        logger.info(f"Enhanced MCP discovery mock initialized with node ID: {node_id}")
    
    async def announce_async(self, server_info: Dict[str, Any]) -> Dict[str, Any]:
        """Announce a server to the discovery network with network simulation."""
        if self.offline:
            logger.warning(f"Node {self.node_id} is offline, cannot announce")
            return {"success": False, "error": "Node is offline"}
        
        # Add node ID to server info if not present
        if "id" not in server_info:
            server_info["id"] = f"server-{len(self.peers)}"
        
        server_id = server_info["id"]
        
        # Add to local peers
        self.peers[server_id] = server_info
        self.announcements.append(server_info)
        
        # Propagate to connected peers through the network
        for peer_id in self.connected_peers:
            success, _ = await self.network.send_message(
                self.node_id,
                peer_id,
                {
                    "type": "announce",
                    "server_info": server_info
                }
            )
            
            if not success:
                logger.warning(f"Failed to propagate announcement to peer {peer_id}")
        
        logger.info(f"Server announced through network: {server_id}")
        return {"success": True, "server_id": server_id}
    
    async def discover_async(self, filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Discover servers with network simulation."""
        if self.offline:
            logger.warning(f"Node {self.node_id} is offline, cannot discover")
            return []
        
        # Start with local peers
        local_results = super().discover(filter_criteria)
        
        # Query connected peers through the network
        all_results = set()
        for peer_info in local_results:
            all_results.add(tuple(sorted(peer_info.items())))
        
        for peer_id in self.connected_peers:
            success, response = await self.network.send_message(
                self.node_id,
                peer_id,
                {
                    "type": "discover",
                    "filter_criteria": filter_criteria
                }
            )
            
            if success and response and "peers" in response:
                for peer_info in response["peers"]:
                    all_results.add(tuple(sorted(peer_info.items())))
        
        # Convert back to dictionaries
        results = [dict(items) for items in all_results]
        
        logger.info(f"Discovered {len(results)} peers through network")
        return results
    
    async def connect_to_peer(self, peer_id: str) -> bool:
        """Connect to another peer in the network."""
        if peer_id == self.node_id:
            logger.warning(f"Cannot connect to self: {peer_id}")
            return False
        
        if peer_id in self.connected_peers:
            logger.info(f"Already connected to peer: {peer_id}")
            return True
        
        # Try to establish connection through the network
        if self.network.connect(self.node_id, peer_id):
            self.connected_peers.add(peer_id)
            logger.info(f"Connected to peer: {peer_id}")
            return True
        
        logger.warning(f"Failed to connect to peer: {peer_id}")
        return False
    
    async def disconnect_from_peer(self, peer_id: str) -> bool:
        """Disconnect from a peer in the network."""
        if peer_id not in self.connected_peers:
            logger.warning(f"Not connected to peer: {peer_id}")
            return False
        
        # Disconnect through the network
        if self.network.disconnect(self.node_id, peer_id):
            self.connected_peers.remove(peer_id)
            logger.info(f"Disconnected from peer: {peer_id}")
            return True
        
        logger.warning(f"Failed to disconnect from peer: {peer_id}")
        return False
    
    def go_offline(self) -> None:
        """Take this node offline."""
        self.offline = True
        logger.info(f"Node {self.node_id} is now offline")
    
    def go_online(self) -> None:
        """Bring this node online."""
        self.offline = False
        logger.info(f"Node {self.node_id} is now online")
    
    def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle incoming messages from other nodes."""
        if self.offline:
            return None
        
        message_type = message.get("type")
        
        if message_type == "announce":
            server_info = message.get("server_info", {})
            server_id = server_info.get("id")
            if server_id:
                self.peers[server_id] = server_info
                self.announcements.append(server_info)
                return {"success": True, "server_id": server_id}
        
        elif message_type == "discover":
            filter_criteria = message.get("filter_criteria")
            peers = super().discover(filter_criteria)
            return {"success": True, "peers": peers}
        
        elif message_type == "subscribe":
            topic = message.get("topic")
            if topic:
                # We can't actually send a callback through the network,
                # so we just acknowledge the subscription
                return {"success": True, "subscription_id": f"sub-{len(self.subscriptions)}"}
        
        elif message_type == "unsubscribe":
            subscription_id = message.get("subscription_id")
            if subscription_id:
                return {"success": True}
        
        elif message_type == "publish":
            topic = message.get("topic")
            content = message.get("content")
            if topic and content:
                return {"success": True}
        
        return {"success": False, "error": "Unknown or invalid message type"}
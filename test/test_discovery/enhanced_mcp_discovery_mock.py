"""
Enhanced MCP Discovery Mock module for testing.

This module provides enhanced mock implementations of the MCP Discovery components
for testing network scenarios.
"""

import logging
import time
import uuid
import random
from typing import Any, Dict, List, Optional, Union
from .mcp_discovery_mock import MCPDiscoveryMock

logger = logging.getLogger(__name__)

class MockNetwork:
    """Mock network for simulating a network of MCP servers."""

    def __init__(self):
        """Initialize the mock network."""
        self.nodes = {}
        self.connections = {}
        self.message_history = []
        logger.info("Initialized MockNetwork")

    def create_node(self, node_id=None, role="peer", features=None):
        """Create a node in the network."""
        if node_id is None:
            node_id = str(uuid.uuid4())

        if features is None:
            features = ["ipfs", "filecoin"]

        discovery = MCPDiscoveryMock()
        discovery.server_id = node_id
        discovery.local_server["id"] = node_id
        discovery.local_server["role"] = role
        discovery.local_server["features"] = features

        self.nodes[node_id] = {
            "id": node_id,
            "discovery": discovery,
            "connections": [],
            "status": "online",
            "created_at": time.time()
        }

        logger.info(f"Created node {node_id} with role {role}")
        return node_id

    def connect_nodes(self, node_id_1, node_id_2):
        """Connect two nodes in the network."""
        if node_id_1 not in self.nodes or node_id_2 not in self.nodes:
            logger.error(f"Cannot connect nodes: one or both nodes not found")
            return False

        # Add connection
        connection_id = f"{node_id_1}-{node_id_2}"
        reverse_id = f"{node_id_2}-{node_id_1}"

        if connection_id in self.connections or reverse_id in self.connections:
            logger.warning(f"Nodes already connected: {node_id_1} - {node_id_2}")
            return False

        self.connections[connection_id] = {
            "from": node_id_1,
            "to": node_id_2,
            "status": "active",
            "created_at": time.time(),
            "messages": []
        }

        # Update node connection lists
        self.nodes[node_id_1]["connections"].append(node_id_2)
        self.nodes[node_id_2]["connections"].append(node_id_1)

        # Exchange server information
        self._exchange_server_info(node_id_1, node_id_2)

        logger.info(f"Connected nodes {node_id_1} and {node_id_2}")
        return True

    def _exchange_server_info(self, node_id_1, node_id_2):
        """Exchange server information between two nodes."""
        node1 = self.nodes[node_id_1]
        node2 = self.nodes[node_id_2]

        # Get server info
        server1_info = node1["discovery"].local_server
        server2_info = node2["discovery"].local_server

        # Register each other's servers
        node1["discovery"].register_server(server2_info)
        node2["discovery"].register_server(server1_info)

    def disconnect_nodes(self, node_id_1, node_id_2):
        """Disconnect two nodes in the network."""
        connection_id = f"{node_id_1}-{node_id_2}"
        reverse_id = f"{node_id_2}-{node_id_1}"

        found = False
        if connection_id in self.connections:
            del self.connections[connection_id]
            found = True
        elif reverse_id in self.connections:
            del self.connections[reverse_id]
            found = True

        if found:
            # Update node connection lists
            if node_id_1 in self.nodes and node_id_2 in self.nodes["connections"]:
                self.nodes[node_id_1]["connections"].remove(node_id_2)
            if node_id_2 in self.nodes and node_id_1 in self.nodes["connections"]:
                self.nodes[node_id_2]["connections"].remove(node_id_1)

            logger.info(f"Disconnected nodes {node_id_1} and {node_id_2}")
            return True

        logger.warning(f"No connection found between {node_id_1} and {node_id_2}")
        return False

    def send_message(self, from_node, to_node, message_type, payload):
        """Send a message from one node to another."""
        if from_node not in self.nodes or to_node not in self.nodes:
            logger.error(f"Cannot send message: one or both nodes not found")
            return False

        # Check if nodes are connected
        connected = to_node in self.nodes[from_node]["connections"]
        if not connected:
            logger.error(f"Cannot send message: nodes are not connected")
            return False

        # Create message
        message = {
            "id": str(uuid.uuid4()),
            "from": from_node,
            "to": to_node,
            "type": message_type,
            "payload": payload,
            "timestamp": time.time()
        }

        # Add to message history
        self.message_history.append(message)

        # Add to connection
        connection_id = f"{from_node}-{to_node}"
        reverse_id = f"{to_node}-{from_node}"

        if connection_id in self.connections:
            self.connections[connection_id]["messages"].append(message)
        elif reverse_id in self.connections:
            self.connections[reverse_id]["messages"].append(message)

        logger.info(f"Sent message from {from_node} to {to_node}: {message_type}")
        return message["id"]

    def get_node(self, node_id):
        """Get a node by ID."""
        if node_id not in self.nodes:
            return None
        return self.nodes[node_id]

    def get_node_discovery(self, node_id):
        """Get a node's discovery instance."""
        if node_id not in self.nodes:
            return None
        return self.nodes[node_id]["discovery"]

    def simulate_network_partition(self, group1, group2):
        """Simulate a network partition between two groups of nodes."""
        for node1 in group1:
            for node2 in group2:
                self.disconnect_nodes(node1, node2)

        logger.info(f"Simulated network partition between {group1} and {group2}")
        return True

    def simulate_node_failure(self, node_id):
        """Simulate a node failure."""
        if node_id not in self.nodes:
            logger.error(f"Cannot simulate failure: node not found")
            return False

        # Disconnect from all connections
        for connected_node in list(self.nodes[node_id]["connections"]):
            self.disconnect_nodes(node_id, connected_node)

        # Mark as offline
        self.nodes[node_id]["status"] = "offline"

        logger.info(f"Simulated failure of node {node_id}")
        return True

    def simulate_node_recovery(self, node_id):
        """Simulate a node recovery."""
        if node_id not in self.nodes:
            logger.error(f"Cannot simulate recovery: node not found")
            return False

        # Mark as online
        self.nodes[node_id]["status"] = "online"

        logger.info(f"Simulated recovery of node {node_id}")
        return True

class EnhancedMCPDiscoveryTest:
    """Enhanced MCP Discovery test utilities."""

    def __init__(self):
        """Initialize the enhanced MCP discovery test."""
        self.network = MockNetwork()
        # Create a default test network
        self._create_test_network()

    def _create_test_network(self, node_count=5):
        """Create a test network with the specified number of nodes."""
        # Create nodes
        coordinator = self.network.create_node(role="coordinator",
                                              features=["ipfs", "filecoin", "routing", "discovery"])

        nodes = [coordinator]
        for i in range(1, node_count):
            # Vary the features slightly
            features = ["ipfs", "filecoin"]
            if random.random() > 0.3:
                features.append("routing")
            if random.random() > 0.7:
                features.append("discovery")

            role = "peer"
            if random.random() > 0.8:
                role = "coordinator"

            node_id = self.network.create_node(role=role, features=features)
            nodes.append(node_id)

        # Create connections (not fully connected)
        for i, node1 in enumerate(nodes):
            # Connect to some nodes
            for j, node2 in enumerate(nodes):
                if i != j and random.random() > 0.3:  # 70% chance of connection
                    self.network.connect_nodes(node1, node2)

        logger.info(f"Created test network with {node_count} nodes")
        self.nodes = nodes
        return nodes

    def get_coordinator(self):
        """Get the coordinator node."""
        for node_id, node in self.network.nodes.items():
            if node["discovery"].local_server["role"] == "coordinator":
                return node_id
        return None

    def simulate_announcement(self, node_id=None):
        """Simulate a node announcing itself to the network."""
        if node_id is None:
            # Use all nodes
            for node_id in self.network.nodes:
                self._announce_node(node_id)
        else:
            self._announce_node(node_id)

    def _announce_node(self, node_id):
        """Announce a single node to its connections."""
        if node_id not in self.network.nodes:
            return False

        node = self.network.nodes[node_id]

        # Announce to all connected nodes
        for connected_node in node["connections"]:
            # Send server info
            server_info = node["discovery"].local_server
            connected_discovery = self.network.get_node_discovery(connected_node)
            if connected_discovery:
                connected_discovery.register_server(server_info)

        logger.info(f"Node {node_id} announced to {len(node['connections'])} connected nodes")
        return True

    def simulate_discovery(self, node_id=None):
        """Simulate node discovery in the network."""
        if node_id is None:
            # Use all nodes
            for node_id in self.network.nodes:
                self._discover_from_node(node_id)
        else:
            self._discover_from_node(node_id)

    def _discover_from_node(self, node_id):
        """Perform discovery from a single node."""
        if node_id not in self.network.nodes:
            return False

        node = self.network.nodes[node_id]
        discovery = node["discovery"]

        # Do discovery (in reality, this would query other nodes)
        # For our mock, we'll just ensure all connected nodes are registered
        for connected_node in node["connections"]:
            connected_info = self.network.get_node(connected_node)
            if connected_info:
                server_info = connected_info["discovery"].local_server
                discovery.register_server(server_info)

        logger.info(f"Node {node_id} discovered servers from {len(node['connections'])} connected nodes")
        return True

    def get_reachable_nodes(self, start_node):
        """Get all nodes reachable from a starting node."""
        if start_node not in self.network.nodes:
            return []

        # Do a breadth-first search
        visited = set([start_node])
        queue = [start_node]

        while queue:
            node = queue.pop(0)
            node_info = self.network.get_node(node)

            if not node_info or node_info["status"] != "online":
                continue

            for connected in node_info["connections"]:
                if connected not in visited:
                    visited.add(connected)
                    queue.append(connected)

        return list(visited)

    def get_node_stats(self):
        """Get statistics about the network nodes."""
        stats = {
            "total_nodes": len(self.network.nodes),
            "online_nodes": sum(1 for n in self.network.nodes.values() if n["status"] == "online"),
            "offline_nodes": sum(1 for n in self.network.nodes.values() if n["status"] != "online"),
            "coordinators": sum(1 for n in self.network.nodes.values()
                                 if n["discovery"].local_server["role"] == "coordinator"),
            "peers": sum(1 for n in self.network.nodes.values()
                          if n["discovery"].local_server["role"] == "peer"),
            "connections": len(self.network.connections),
            "messages": len(self.network.message_history)
        }
        return stats

#!/usr/bin/env python3
"""
Enhanced MCP Discovery Mock for Testing

This module provides enhanced mocked components for testing the MCP Discovery functionality
without requiring libp2p dependencies. It includes better simulation of network behavior
and improved compatibility with comprehensive tests.
"""

import logging
import sys
import os
import time
import uuid
import json
import threading
import random
import socket
import hashlib
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("enhanced_mcp_discovery_mock")

# Import mock implementations
from test_discovery.mcp_discovery_mock import (
    MockMCPDiscoveryModel,
    MCPServerRole,
    MCPMessageType,
    MCPServerCapabilities,
    MCPFeatureSet,
    MCPServerInfo,
    HAS_ORIGINAL_CLASSES
)

# Try to import optional dependencies
try:
    import multiaddr
    HAS_MULTIADDR = True
except ImportError:
    HAS_MULTIADDR = False
    logger.warning("multiaddr not available, using string-based addressing")

# Global registry for mock network communication across instances
class MockNetwork:
    """Simulated network for mock discovery instances."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton network instance."""
        if cls._instance is None:
            cls._instance = MockNetwork()
        return cls._instance
    
    def __init__(self):
        """Initialize the mock network."""
        self.nodes = {}  # server_id -> model instance
        self.node_lock = threading.Lock()
        self.message_handlers = {}  # topic -> list of (server_id, handler_func)
        self.message_lock = threading.Lock()
        self.active = True  # Network status
        self.connection_matrix = {}  # {server_id: {connected_server_id: True/False}}
        self.connection_lock = threading.Lock()
        logger.info("Mock network initialized")
    
    def register_node(self, server_id, model):
        """Register a node with the network."""
        with self.node_lock:
            self.nodes[server_id] = model
            logger.debug(f"Node registered: {server_id}")
            
        # Initialize connection matrix for this node
        with self.connection_lock:
            if server_id not in self.connection_matrix:
                self.connection_matrix[server_id] = {}
            
            # Connect to all existing nodes
            for other_id in self.nodes:
                if other_id != server_id:
                    self.connection_matrix[server_id][other_id] = True
                    if other_id in self.connection_matrix:
                        self.connection_matrix[other_id][server_id] = True
    
    def unregister_node(self, server_id):
        """Unregister a node from the network."""
        with self.node_lock:
            if server_id in self.nodes:
                del self.nodes[server_id]
                logger.debug(f"Node unregistered: {server_id}")
        
        # Remove from connection matrix
        with self.connection_lock:
            if server_id in self.connection_matrix:
                del self.connection_matrix[server_id]
            
            # Also remove connections to this node
            for other_id in self.connection_matrix:
                if server_id in self.connection_matrix[other_id]:
                    del self.connection_matrix[other_id][server_id]
    
    def subscribe(self, server_id, topic, handler):
        """Subscribe to a topic."""
        with self.message_lock:
            if topic not in self.message_handlers:
                self.message_handlers[topic] = []
            self.message_handlers[topic].append((server_id, handler))
            logger.debug(f"Node {server_id} subscribed to topic: {topic}")
    
    def unsubscribe(self, server_id, topic):
        """Unsubscribe from a topic."""
        with self.message_lock:
            if topic in self.message_handlers:
                self.message_handlers[topic] = [(sid, handler) for sid, handler 
                                              in self.message_handlers[topic] 
                                              if sid != server_id]
                logger.debug(f"Node {server_id} unsubscribed from topic: {topic}")
    
    def remove_node_connection(self, node1_id, node2_id):
        """
        Remove a direct connection between two nodes, making them unable to communicate.
        
        Args:
            node1_id: ID of the first node
            node2_id: ID of the second node
            
        Returns:
            bool: True if connection was removed, False otherwise
        """
        if node1_id == node2_id:
            logger.warning(f"Cannot remove connection to self: {node1_id}")
            return False
            
        with self.connection_lock:
            # Check if both nodes exist
            if node1_id not in self.connection_matrix or node2_id not in self.connection_matrix:
                logger.warning(f"Cannot remove connection between unknown nodes: {node1_id} and {node2_id}")
                return False
                
            # Update connection matrix in both directions
            self.connection_matrix[node1_id][node2_id] = False
            self.connection_matrix[node2_id][node1_id] = False
            
            logger.debug(f"Removed connection between {node1_id} and {node2_id}")
            return True
    
    def add_node_connection(self, node1_id, node2_id):
        """
        Add a direct connection between two nodes, allowing them to communicate.
        
        Args:
            node1_id: ID of the first node
            node2_id: ID of the second node
            
        Returns:
            bool: True if connection was added, False otherwise
        """
        if node1_id == node2_id:
            logger.warning(f"Cannot add connection to self: {node1_id}")
            return False
            
        with self.connection_lock:
            # Check if both nodes exist
            if node1_id not in self.connection_matrix or node2_id not in self.connection_matrix:
                logger.warning(f"Cannot add connection between unknown nodes: {node1_id} and {node2_id}")
                return False
                
            # Update connection matrix in both directions
            self.connection_matrix[node1_id][node2_id] = True
            self.connection_matrix[node2_id][node1_id] = True
            
            logger.debug(f"Added connection between {node1_id} and {node2_id}")
            return True
    
    def are_nodes_connected(self, node1_id, node2_id):
        """
        Check if two nodes are directly connected.
        
        Args:
            node1_id: ID of the first node
            node2_id: ID of the second node
            
        Returns:
            bool: True if nodes are connected, False otherwise
        """
        with self.connection_lock:
            # Check if both nodes exist
            if node1_id not in self.connection_matrix or node2_id not in self.connection_matrix:
                return False
                
            # Check connection status
            return self.connection_matrix[node1_id].get(node2_id, False)
    
    def publish(self, server_id, topic, message):
        """Publish a message to a topic."""
        if not self.active:
            logger.debug(f"Network is inactive, message from {server_id} to {topic} dropped")
            return False
            
        with self.message_lock:
            if topic not in self.message_handlers:
                # No subscribers
                return False
                
            # Deliver to all subscribers except the sender
            delivered = False
            for target_id, handler in self.message_handlers[topic]:
                if target_id != server_id:  # Don't deliver to self
                    # Check if the nodes are connected
                    if not self.are_nodes_connected(server_id, target_id):
                        logger.debug(f"Message from {server_id} to {target_id} dropped (disconnected)")
                        continue
                        
                    try:
                        if callable(handler):
                            handler({
                                "from": server_id,
                                "data": message,
                                "topic": topic,
                                "timestamp": time.time()
                            })
                            delivered = True
                    except Exception as e:
                        logger.error(f"Error delivering message to {target_id}: {e}")
            
            return delivered
    
    def simulate_network_partition(self, group1, group2):
        """Simulate a network partition between two groups of nodes."""
        logger.info(f"Simulating network partition between groups of {len(group1)} and {len(group2)} nodes")
        
        # Remove connections between nodes in different groups
        for node1 in group1:
            for node2 in group2:
                self.remove_node_connection(node1, node2)
    
    def resolve_network_partition(self, group1=None, group2=None):
        """
        Resolve network partition between groups of nodes.
        
        Args:
            group1: First group of nodes (optional)
            group2: Second group of nodes (optional)
            
        If groups are not specified, resolves all network partitions.
        """
        if group1 and group2:
            logger.info(f"Resolving network partition between specific groups")
            # Add connections between nodes in the specified groups
            for node1 in group1:
                for node2 in group2:
                    self.add_node_connection(node1, node2)
        else:
            logger.info("Resolving all network partitions")
            # Reset all connections
            with self.connection_lock:
                for node1 in self.connection_matrix:
                    for node2 in self.connection_matrix:
                        if node1 != node2:
                            self.connection_matrix[node1][node2] = True
    
    def discover_nodes(self, requester_id, filter_func=None):
        """Discover nodes in the network with optional filtering."""
        discovered = []
        
        with self.node_lock:
            for node_id, model in self.nodes.items():
                # Skip requester
                if node_id == requester_id:
                    continue
                    
                # Skip disconnected nodes
                if not self.are_nodes_connected(requester_id, node_id):
                    continue
                    
                # Apply filter if provided
                if filter_func and not filter_func(model):
                    continue
                    
                # Add to discovered list
                discovered.append(node_id)
        
        return discovered


class EnhancedMockMCPDiscoveryModel(MockMCPDiscoveryModel):
    """
    Enhanced mock implementation of the MCP Discovery model.
    
    This class extends the basic mock with better simulation of network behavior,
    support for feature hashing, and improved compatibility with comprehensive tests.
    """
    
    def __init__(
        self,
        server_id: Optional[str] = None,
        role: str = MCPServerRole.MASTER,
        features: Optional[List[str]] = None,
        libp2p_model=None,
        ipfs_model=None,
        cache_manager=None,
        credential_manager=None,
        resources=None,
        metadata=None,
        network=None
    ):
        """Initialize the enhanced mock MCP discovery model."""
        # Call parent init
        super().__init__(
            server_id=server_id,
            role=role,
            features=features,
            libp2p_model=libp2p_model,
            ipfs_model=ipfs_model,
            cache_manager=cache_manager,
            credential_manager=credential_manager,
            resources=resources,
            metadata=metadata
        )
        
        # Store or create network reference
        self.network = network or MockNetwork.get_instance()
        
        # Register with network
        self.network.register_node(self.server_id, self)
        
        # Advanced features
        self.peer_id = f"Qm{hashlib.sha256(self.server_id.encode()).hexdigest()[:44]}"
        self.addresses = self._generate_mock_addresses()
        
        # Update local server info with peer ID and addresses
        self.server_info.libp2p_peer_id = self.peer_id
        self.server_info.libp2p_addresses = self.addresses
        
        # Subscribe to discovery topics
        self._subscribe_to_topics()
        
        # Add connection tracking
        self.connected_peers = set()
        
        # Additional simulated network properties
        self.latency_map = {}  # server_id -> simulated latency (ms)
        self.packet_loss = 0.0  # Simulated packet loss rate (0.0-1.0)
        
        # Task handler registry with feature requirements
        self.task_handler_features = {}  # task_type -> required_features
        
        # Initialize the feature hash specifically
        self._init_feature_hash()
        
        logger.info(f"Enhanced Mock MCP Discovery Model initialized with ID {self.server_id} and role {self.role}")
        logger.info(f"Features: {', '.join(self.feature_set.features)}")
        logger.info(f"Peer ID: {self.peer_id}")
    
    def _generate_mock_addresses(self):
        """Generate mock libp2p multiaddresses."""
        # Use random port numbers for simulation
        tcp_port = random.randint(10000, 65000)
        quic_port = random.randint(10000, 65000)
        ws_port = random.randint(10000, 65000)
        
        # Generate addresses based on role
        addresses = []
        
        # Always include a basic TCP address
        addresses.append(f"/ip4/127.0.0.1/tcp/{tcp_port}/p2p/{self.peer_id}")
        
        # Add more addresses based on role
        if self.role in (MCPServerRole.MASTER, MCPServerRole.HYBRID):
            addresses.append(f"/ip4/127.0.0.1/udp/{quic_port}/quic-v1/p2p/{self.peer_id}")
            
        if MCPServerCapabilities.PEER_WEBSOCKET in self.feature_set.features:
            addresses.append(f"/ip4/127.0.0.1/tcp/{ws_port}/ws/p2p/{self.peer_id}")
            
        # Try to create proper multiaddresses if library is available
        if HAS_MULTIADDR:
            try:
                # Convert to proper multiaddresses
                return [str(multiaddr.Multiaddr(addr)) for addr in addresses]
            except Exception as e:
                logger.warning(f"Error creating multiaddresses: {e}")
        
        return addresses
    
    def _init_feature_hash(self):
        """Initialize the feature hash with more detailed verification."""
        # Use a more comprehensive approach for feature hashing
        features_str = ",".join(sorted(self.feature_set.features))
        role_str = f"role:{self.role}"
        version_str = f"version:{self.feature_set.version}"
        
        # Create a unique identifier for this feature set
        combined = f"{features_str}|{role_str}|{version_str}"
        self.feature_set.feature_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        # Update server info
        self.server_info.feature_set = self.feature_set
    
    def _subscribe_to_topics(self):
        """Subscribe to relevant pubsub topics."""
        # Subscribe to announcements topic
        self.network.subscribe(
            self.server_id,
            "mcp/announcements",
            self._handle_announcement
        )
        
        # Subscribe to discovery requests topic
        self.network.subscribe(
            self.server_id,
            "mcp/discovery",
            self._handle_discovery_request
        )
        
        # Subscribe to health check topic
        self.network.subscribe(
            self.server_id,
            "mcp/health",
            self._handle_health_check
        )
        
        # Subscribe to task distribution topic
        self.network.subscribe(
            self.server_id,
            "mcp/tasks",
            self._handle_task_request
        )
    
    def _handle_announcement(self, message):
        """Handle server announcements."""
        try:
            message_data = json.loads(message["data"])
            
            # Log the announcement
            logger.debug(f"Received announcement from {message['from']}")
            
            # Extract server info
            server_info_dict = message_data.get("server_info", {})
            
            # Register the server
            self.register_server(server_info_dict)
            
            # Update statistics
            self.stats["announcements_received"] += 1
            
        except Exception as e:
            logger.error(f"Error handling announcement: {e}")
    
    # Override get_compatible_servers to fix issues in enhanced implementation
    def get_compatible_servers(self, feature_requirements: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all servers with compatible feature sets."""
        # Prepare result
        result = {
            "success": True,
            "operation": "get_compatible_servers",
            "timestamp": time.time(),
            "servers": []
        }
        
        # Log what we're looking for
        if feature_requirements:
            feature_str = ", ".join(feature_requirements)
            logger.debug(f"Looking for servers with features: {feature_str}")
        else:
            logger.debug("Looking for all compatible servers with no specific feature requirements")
        
        # Get compatible servers
        with self.server_lock:
            # Log how many servers we know about
            logger.debug(f"Checking compatibility among {len(self.known_servers)} known servers")
            
            # Get all known servers
            compatible_servers = []
            
            # If we have specific feature requirements, check each server
            for server_id, server_info in self.known_servers.items():
                # Skip our own server
                if server_id == self.server_id:
                    continue
                
                # Debug log
                server_features = list(server_info.feature_set.features)
                logger.debug(f"Server {server_id} has features: {server_features}")
                
                # Check if server can handle required features
                if not feature_requirements:
                    # No specific requirements, add all
                    compatible_servers.append(server_info.to_dict())
                    logger.debug(f"Added server {server_id} (no specific requirements)")
                else:
                    # Check each required feature
                    has_all_features = True
                    for feature in feature_requirements:
                        if feature not in server_info.feature_set.features:
                            has_all_features = False
                            logger.debug(f"Server {server_id} missing required feature: {feature}")
                            break
                    
                    if has_all_features:
                        compatible_servers.append(server_info.to_dict())
                        logger.debug(f"Added compatible server {server_id}")
        
        # Update result
        result["servers"] = compatible_servers
        result["server_count"] = len(compatible_servers)
        
        logger.debug(f"Found {len(compatible_servers)} compatible servers")
        return result
    
    # Override check_server_health for better health checking
    def check_server_health(self, server_id: str) -> Dict[str, Any]:
        """Check health status of a specific server."""
        # Prepare result
        result = {
            "success": False,
            "operation": "check_server_health",
            "timestamp": time.time(),
            "server_id": server_id
        }
        
        # Update statistics
        self.stats["health_checks"] += 1
        
        # Check if this is our own server
        if server_id == self.server_id:
            # For local server, we can immediately return healthy
            result["success"] = True
            result["healthy"] = True
            result["is_local"] = True
            return result
        
        # Look for server in known servers
        with self.server_lock:
            if server_id not in self.known_servers:
                result["error"] = f"Server not found: {server_id}"
                return result
            
            server_info = self.known_servers[server_id]
        
        # In mock, always report healthy if recently seen
        time_since_last_seen = time.time() - server_info.last_seen
        is_healthy = time_since_last_seen < 300  # 5 minutes
        
        # Update server health info
        with self.server_lock:
            if server_id in self.known_servers:
                self.known_servers[server_id].health_status = {
                    "healthy": is_healthy,
                    "last_checked": time.time()
                }
        
        # Set result
        result["success"] = True
        result["healthy"] = is_healthy
        result["health_source"] = "mock"
        
        return result
    
    # Override remove_server to handle network connections
    def remove_server(self, server_id: str) -> Dict[str, Any]:
        """Remove a server from known servers."""
        # Prepare result
        result = {
            "success": False,
            "operation": "remove_server",
            "timestamp": time.time(),
            "server_id": server_id
        }
        
        # Can't remove our own server
        if server_id == self.server_id:
            result["error"] = "Cannot remove local server"
            return result
        
        # Remove from our known servers
        with self.server_lock:
            if server_id in self.known_servers:
                # Get feature hash before removing
                feature_hash = self.known_servers[server_id].feature_set.feature_hash
                
                # Remove server from known servers
                del self.known_servers[server_id]
                
                # Remove from feature groups
                if feature_hash in self.feature_groups and server_id in self.feature_groups[feature_hash]:
                    self.feature_groups[feature_hash].remove(server_id)
                
                # Update result
                result["success"] = True
            else:
                result["error"] = f"Server not found: {server_id}"
                
        # Update connection matrix to reflect the removal of this server
        # This simulates real network behavior where the server would
        # be unreachable after disconnection
        if result["success"]:
            # Remove the connection in both directions
            self.network.remove_node_connection(self.server_id, server_id)
            
            # Log the removal
            logger.debug(f"Removed connection to server {server_id}")
            
        return result
    
    # Override reset method to properly clear and reinitialize state
    def reset(self):
        """Reset the discovery model, clearing all server information."""
        with self.server_lock:
            # Clear all server information but keep our own info
            self.known_servers = {}
            self.feature_groups = {}
        
        # Reset statistics
        self.stats = {
            "servers_discovered": 0,
            "announcements_received": 0,
            "discovery_requests": 0,
            "discovery_responses": 0,
            "health_checks": 0,
            "tasks_processed": 0,
            "tasks_dispatched": 0,
            "messages_sent": 0,
            "messages_received": 0
        }
        
        # Re-announce ourselves to the network to start fresh
        self.announce_server()
        
        # Return success status
        return {
            "success": True,
            "operation": "reset",
            "timestamp": time.time()
        }
    
    def _handle_discovery_request(self, message):
        """Handle discovery requests."""
        try:
            message_data = json.loads(message["data"])
            
            # Log the discovery request
            logger.debug(f"Received discovery request from {message['from']}")
            
            # Extract request parameters
            compatible_only = message_data.get("compatible_only", True)
            feature_requirements = message_data.get("feature_requirements", None)
            
            # Get compatible servers
            servers = []
            with self.server_lock:
                for server_id, server_info in self.known_servers.items():
                    # Skip requester's server
                    if server_id == message["from"]:
                        continue
                    
                    # Filter by compatibility if needed
                    if compatible_only and not self.feature_set.is_compatible_with(server_info.feature_set):
                        continue
                    
                    # Filter by feature requirements if needed
                    if feature_requirements and not server_info.feature_set.can_handle_request(feature_requirements):
                        continue
                    
                    # Add to list
                    servers.append(server_info.to_dict())
            
            # Add this server to the list
            servers.append(self.server_info.to_dict())
            
            # Create response
            response = {
                "message_type": MCPMessageType.DISCOVERY,
                "server_id": self.server_id,
                "timestamp": time.time(),
                "servers": servers
            }
            
            # Publish response directly to requester
            self.network.publish(
                self.server_id,
                f"mcp/discovery/{message['from']}",
                json.dumps(response)
            )
            
        except Exception as e:
            logger.error(f"Error handling discovery request: {e}")
    
    def _handle_health_check(self, message):
        """Handle health check requests."""
        try:
            message_data = json.loads(message["data"])
            
            # Log the health check
            logger.debug(f"Received health check from {message['from']}")
            
            # Create response with current health
            response = {
                "message_type": MCPMessageType.HEALTH,
                "server_id": self.server_id,
                "timestamp": time.time(),
                "healthy": True,
                "uptime": time.time() - self.stats["start_time"],
                "resource_usage": {
                    "cpu": random.random() * 100,
                    "memory": random.random() * 100,
                    "disk": random.random() * 100
                }
            }
            
            # Send response directly to requester
            self.network.publish(
                self.server_id,
                f"mcp/health/{message['from']}",
                json.dumps(response)
            )
            
            # Update statistics
            self.stats["health_checks"] += 1
            
        except Exception as e:
            logger.error(f"Error handling health check: {e}")
    
    def _handle_task_request(self, message):
        """Handle task requests."""
        try:
            message_data = json.loads(message["data"])
            
            # Log the task request
            logger.debug(f"Received task request from {message['from']}")
            
            # Extract task details
            task_type = message_data.get("task_type")
            task_data = message_data.get("task_data")
            required_features = message_data.get("required_features")
            
            # Update statistics
            self.stats["tasks_received"] += 1
            
            # Check if we can handle this task
            can_handle = False
            
            # Check if we have a handler
            if task_type in self.task_handlers:
                # Check if we have the required features
                if not required_features or self.server_info.feature_set.can_handle_request(required_features):
                    can_handle = True
            
            # Create response
            if can_handle:
                # Process the task
                try:
                    handler = self.task_handlers[task_type]
                    task_result = handler(task_data)
                    
                    # Update statistics
                    self.stats["tasks_processed"] += 1
                    
                    # Create success response
                    response = {
                        "message_type": MCPMessageType.TASK_RESPONSE,
                        "server_id": self.server_id,
                        "task_id": message_data.get("task_id"),
                        "timestamp": time.time(),
                        "success": True,
                        "result": task_result
                    }
                except Exception as e:
                    # Create error response
                    response = {
                        "message_type": MCPMessageType.TASK_RESPONSE,
                        "server_id": self.server_id,
                        "task_id": message_data.get("task_id"),
                        "timestamp": time.time(),
                        "success": False,
                        "error": str(e)
                    }
            else:
                # Create rejection response
                response = {
                    "message_type": MCPMessageType.TASK_RESPONSE,
                    "server_id": self.server_id,
                    "task_id": message_data.get("task_id"),
                    "timestamp": time.time(),
                    "success": False,
                    "error": "Cannot handle this task type or missing required features"
                }
            
            # Send response directly to requester
            self.network.publish(
                self.server_id,
                f"mcp/tasks/{message['from']}",
                json.dumps(response)
            )
            
        except Exception as e:
            logger.error(f"Error handling task request: {e}")
    
    def announce_server(self) -> Dict[str, Any]:
        """Announce this server to the network."""
        # Prepare server info
        server_info_dict = self.server_info.to_dict()
        
        # Create announcement message
        announcement = {
            "message_type": MCPMessageType.ANNOUNCE,
            "server_id": self.server_id,
            "timestamp": time.time(),
            "server_info": server_info_dict
        }
        
        # Publish to announcement topic
        published = self.network.publish(
            self.server_id,
            "mcp/announcements",
            json.dumps(announcement)
        )
        
        # Prepare result
        result = {
            "success": True,
            "operation": "announce_server",
            "timestamp": time.time(),
            "announcement_sent": published,
            "announcement_channels": ["mock_pubsub"]
        }
        
        # Update statistics
        self.stats["announcements_sent"] += 1
        
        return result
    
    def discover_servers(self, 
                      methods: Optional[List[str]] = None, 
                      compatible_only: bool = True,
                      feature_requirements: Optional[List[str]] = None) -> Dict[str, Any]:
        """Discover MCP servers using the network."""
        # Prepare result
        result = {
            "success": True,
            "operation": "discover_servers",
            "timestamp": time.time(),
            "methods": methods or ["pubsub"],
            "servers": []
        }
        
        # Prepare discovery request
        discovery_request = {
            "message_type": MCPMessageType.DISCOVERY,
            "server_id": self.server_id,
            "timestamp": time.time(),
            "compatible_only": compatible_only,
            "feature_requirements": feature_requirements
        }
        
        # Create a response collection event
        response_event = threading.Event()
        collected_servers = []
        
        # Create a handler for discovery responses
        def handle_discovery_response(message):
            nonlocal collected_servers
            try:
                message_data = json.loads(message["data"])
                servers = message_data.get("servers", [])
                collected_servers.extend(servers)
                
                # If we got a response, signal the event
                response_event.set()
            except Exception as e:
                logger.error(f"Error handling discovery response: {e}")
        
        # Subscribe to response topic
        response_topic = f"mcp/discovery/{self.server_id}"
        self.network.subscribe(self.server_id, response_topic, handle_discovery_response)
        
        try:
            # Publish discovery request
            self.network.publish(
                self.server_id,
                "mcp/discovery",
                json.dumps(discovery_request)
            )
            
            # Wait for responses with timeout
            response_event.wait(timeout=2.0)
            
            # Process discovered servers
            new_servers = 0
            discovered_servers = []
            
            for server_dict in collected_servers:
                server_id = server_dict.get("server_id")
                
                # Skip our own server
                if server_id == self.server_id:
                    continue
                
                # Register the server
                is_new = server_id not in self.known_servers
                if is_new:
                    new_servers += 1
                
                self.register_server(server_dict)
                
                # Add to result
                discovered_servers.append(server_dict)
            
            # Update result
            result["servers"] = discovered_servers
            result["server_count"] = len(discovered_servers)
            result["new_servers"] = new_servers
            
        finally:
            # Unsubscribe from response topic
            self.network.unsubscribe(self.server_id, response_topic)
        
        # Update statistics
        self.stats["discovery_requests"] += 1
        
        return result
    
    def register_task_handler(self, task_type: str, 
                             handler: Callable, 
                             required_features: Optional[List[str]] = None) -> Dict[str, Any]:
        """Register a handler for a specific task type with feature requirements."""
        # Prepare result
        result = {
            "success": True,
            "operation": "register_task_handler",
            "timestamp": time.time(),
            "task_type": task_type
        }
        
        # Register handler
        self.task_handlers[task_type] = handler
        
        # Store required features if provided
        if required_features:
            self.task_handler_features[task_type] = required_features
            result["required_features"] = required_features
        
        return result
    
    def dispatch_task(self, 
                    task_type: str, 
                    task_data: Any, 
                    required_features: Optional[List[str]] = None,
                    preferred_server_id: Optional[str] = None) -> Dict[str, Any]:
        """Dispatch a task to a compatible server using the network."""
        # Prepare result and task ID
        task_id = str(uuid.uuid4())
        result = {
            "success": False,
            "operation": "dispatch_task",
            "timestamp": time.time(),
            "task_type": task_type,
            "task_id": task_id
        }
        
        # If no explicit features are provided, check if the task type has registered requirements
        if required_features is None and task_type in self.task_handler_features:
            required_features = self.task_handler_features[task_type]
        
        # Check if we can handle the task locally
        can_handle_locally = task_type in self.task_handlers
        
        # If specific features are required, check if we have them
        if required_features and not self.feature_set.can_handle_request(required_features):
            can_handle_locally = False
        
        # If we can handle locally and either no preferred server is specified
        # or we are the preferred server, process locally
        if can_handle_locally and (preferred_server_id is None or preferred_server_id == self.server_id):
            try:
                # Call task handler
                handler = self.task_handlers[task_type]
                task_result = handler(task_data)
                
                # Update statistics
                self.stats["tasks_processed"] += 1
                
                # Update result
                result["success"] = True
                result["server_id"] = self.server_id
                result["task_result"] = task_result
                result["processed_locally"] = True
                
                return result
            except Exception as e:
                logger.error(f"Error processing task locally: {e}")
                # Fall through to remote processing
        
        # Find a compatible server to handle the task
        target_server_id = None
        target_server = None
        
        # Use preferred server if specified
        if preferred_server_id and preferred_server_id != self.server_id:
            with self.server_lock:
                if preferred_server_id in self.known_servers:
                    server_info = self.known_servers[preferred_server_id]
                    
                    # Check if server has required features
                    if not required_features or server_info.feature_set.can_handle_request(required_features):
                        # Check if server is healthy
                        if server_info.health_status.get("healthy", False):
                            target_server_id = preferred_server_id
                            target_server = server_info
        
        # Find another compatible server if preferred server not available
        if target_server_id is None:
            compatible_servers = self.get_compatible_servers(feature_requirements=required_features)
            
            if compatible_servers.get("success", False) and compatible_servers.get("server_count", 0) > 0:
                # Pick the first compatible server
                server_dict = compatible_servers["servers"][0]
                target_server_id = server_dict["server_id"]
                
                with self.server_lock:
                    if target_server_id in self.known_servers:
                        target_server = self.known_servers[target_server_id]
        
        # If we didn't find a suitable server, return error
        if target_server_id is None or target_server is None:
            result["error"] = "No compatible server found for task"
            return result
        
        # Create a response collection event
        response_event = threading.Event()
        task_response = None
        
        # Create a handler for task responses
        def handle_task_response(message):
            nonlocal task_response
            try:
                message_data = json.loads(message["data"])
                
                # Store the response
                task_response = message_data
                
                # Signal that we got a response
                response_event.set()
            except Exception as e:
                logger.error(f"Error handling task response: {e}")
        
        # Subscribe to response topic
        response_topic = f"mcp/tasks/{self.server_id}"
        self.network.subscribe(self.server_id, response_topic, handle_task_response)
        
        try:
            # Create task request
            task_request = {
                "message_type": MCPMessageType.TASK_REQUEST,
                "server_id": self.server_id,
                "task_id": task_id,
                "timestamp": time.time(),
                "task_type": task_type,
                "task_data": task_data,
                "required_features": required_features
            }
            
            # Publish task request
            published = self.network.publish(
                self.server_id,
                "mcp/tasks",
                json.dumps(task_request)
            )
            
            if not published:
                result["error"] = "Failed to publish task request"
                return result
            
            # Update statistics
            self.stats["tasks_dispatched"] += 1
            
            # Wait for response with timeout
            response_event.wait(timeout=2.0)
            
            # Process response
            if task_response:
                result["success"] = task_response.get("success", False)
                result["server_id"] = task_response.get("server_id", target_server_id)
                result["task_result"] = task_response.get("result", {})
                result["processed_locally"] = False
                
                # Add error if present
                if "error" in task_response:
                    result["error"] = task_response["error"]
            else:
                # Timeout waiting for response
                result["error"] = f"Timeout waiting for response from server {target_server_id}"
        
        finally:
            # Unsubscribe from response topic
            self.network.unsubscribe(self.server_id, response_topic)
        
        return result
    
    def check_server_health(self, server_id: str) -> Dict[str, Any]:
        """Check health status of a specific server."""
        # Prepare result
        result = {
            "success": False,
            "operation": "check_server_health",
            "timestamp": time.time(),
            "server_id": server_id
        }
        
        # Update statistics
        self.stats["health_checks"] += 1
        
        # Check if this is our own server
        if server_id == self.server_id:
            # For local server, we can immediately return healthy
            result["success"] = True
            result["healthy"] = True
            result["is_local"] = True
            return result
        
        # Look for server in known servers
        with self.server_lock:
            if server_id not in self.known_servers:
                result["error"] = f"Server not found: {server_id}"
                return result
            
            server_info = self.known_servers[server_id]
        
        # Create a response collection event
        response_event = threading.Event()
        health_response = None
        
        # Create a handler for health responses
        def handle_health_response(message):
            nonlocal health_response
            try:
                message_data = json.loads(message["data"])
                
                # Store the response
                health_response = message_data
                
                # Signal that we got a response
                response_event.set()
            except Exception as e:
                logger.error(f"Error handling health response: {e}")
        
        # Subscribe to response topic
        response_topic = f"mcp/health/{self.server_id}"
        self.network.subscribe(self.server_id, response_topic, handle_health_response)
        
        try:
            # Create health check request
            health_request = {
                "message_type": MCPMessageType.HEALTH,
                "server_id": self.server_id,
                "timestamp": time.time()
            }
            
            # Publish health check request
            published = self.network.publish(
                self.server_id,
                "mcp/health",
                json.dumps(health_request)
            )
            
            # Wait for response with timeout
            response_received = response_event.wait(timeout=1.0)
            
            # Check if we received a response
            if response_received and health_response:
                # Update server health info
                with self.server_lock:
                    if server_id in self.known_servers:
                        self.known_servers[server_id].health_status = {
                            "healthy": health_response.get("healthy", True),
                            "last_checked": time.time(),
                            "details": health_response.get("resource_usage", {})
                        }
                
                # Update result
                result["success"] = True
                result["healthy"] = health_response.get("healthy", True)
                result["health_source"] = "direct"
                result["uptime"] = health_response.get("uptime", 0)
                
                # Add resource usage if available
                if "resource_usage" in health_response:
                    result["resource_usage"] = health_response["resource_usage"]
            else:
                # No response, server might be down
                time_since_last_seen = time.time() - server_info.last_seen
                is_healthy = time_since_last_seen < 300  # 5 minutes
                
                # Update server health info
                with self.server_lock:
                    if server_id in self.known_servers:
                        self.known_servers[server_id].health_status = {
                            "healthy": is_healthy,
                            "last_checked": time.time()
                        }
                
                # Update result
                result["success"] = True
                result["healthy"] = is_healthy
                result["health_source"] = "inferred"
                result["last_seen"] = server_info.last_seen
                result["time_since_last_seen"] = time_since_last_seen
        
        finally:
            # Unsubscribe from response topic
            self.network.unsubscribe(self.server_id, response_topic)
        
        return result
    
    def close(self):
        """Clean up resources when shutting down."""
        # Unregister from network
        self.network.unregister_node(self.server_id)
        
        # Unsubscribe from all topics
        self.network.unsubscribe(self.server_id, "mcp/announcements")
        self.network.unsubscribe(self.server_id, "mcp/discovery")
        self.network.unsubscribe(self.server_id, "mcp/health")
        self.network.unsubscribe(self.server_id, "mcp/tasks")
        
        logger.info(f"Enhanced Mock MCP Discovery Model {self.server_id} closed")
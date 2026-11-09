#!/usr/bin/env python3
"""
Simple test for MockNetwork connection functionality.

This script directly tests the MockNetwork connection matrix handling to verify
that our implementation of network partitioning works correctly.
"""

import os
import sys
import time
import unittest

# Add parent directory to path to allow importing the mock implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the mock network class
from test_discovery.enhanced_mcp_discovery_mock import MockNetwork

class MockNetworkTest(unittest.TestCase):
    """Test the MockNetwork connection functionality."""
    
    def setUp(self):
        """Set up a fresh network for each test."""
        # Get a new instance of the mock network
        self.network = MockNetwork()
        
        # Reset any existing nodes
        for node_id in list(self.network.nodes.keys()):
            self.network.unregister_node(node_id)
            
        # Register test nodes
        self.node_ids = ["node1", "node2", "node3", "node4"]
        for node_id in self.node_ids:
            self.network.register_node(node_id, None)
    
    def test_initial_connections(self):
        """Test that nodes are initially fully connected."""
        for node1 in self.node_ids:
            for node2 in self.node_ids:
                if node1 != node2:
                    # Nodes should be connected
                    self.assertTrue(
                        self.network.are_nodes_connected(node1, node2),
                        f"Nodes {node1} and {node2} should be initially connected"
                    )
    
    def test_remove_connection(self):
        """Test removing a connection between nodes."""
        # Remove connection between node1 and node2
        result = self.network.remove_node_connection("node1", "node2")
        
        # Check result
        self.assertTrue(result, "remove_node_connection should return True")
        
        # Check connection is removed in both directions
        self.assertFalse(
            self.network.are_nodes_connected("node1", "node2"),
            "Connection should be removed from node1 to node2"
        )
        self.assertFalse(
            self.network.are_nodes_connected("node2", "node1"),
            "Connection should be removed from node2 to node1"
        )
        
        # Other connections should still be present
        self.assertTrue(
            self.network.are_nodes_connected("node1", "node3"),
            "Connection between node1 and node3 should still exist"
        )
        self.assertTrue(
            self.network.are_nodes_connected("node2", "node3"),
            "Connection between node2 and node3 should still exist"
        )
    
    def test_add_connection(self):
        """Test adding a connection between nodes."""
        # First remove a connection
        self.network.remove_node_connection("node1", "node2")
        
        # Verify it's gone
        self.assertFalse(self.network.are_nodes_connected("node1", "node2"))
        
        # Now add it back
        result = self.network.add_node_connection("node1", "node2")
        
        # Check result
        self.assertTrue(result, "add_node_connection should return True")
        
        # Verify connection is restored in both directions
        self.assertTrue(
            self.network.are_nodes_connected("node1", "node2"),
            "Connection should be restored from node1 to node2"
        )
        self.assertTrue(
            self.network.are_nodes_connected("node2", "node1"),
            "Connection should be restored from node2 to node1"
        )
    
    def test_network_partition(self):
        """Test simulating a network partition between groups of nodes."""
        # Create two groups
        group1 = ["node1", "node2"]
        group2 = ["node3", "node4"]
        
        # Simulate network partition
        self.network.simulate_network_partition(group1, group2)
        
        # Check that nodes in different groups are disconnected
        for node1 in group1:
            for node2 in group2:
                self.assertFalse(
                    self.network.are_nodes_connected(node1, node2),
                    f"Nodes {node1} and {node2} should be disconnected after partition"
                )
                
        # Check that nodes in the same group remain connected
        for node1 in group1:
            for node2 in group1:
                if node1 != node2:
                    self.assertTrue(
                        self.network.are_nodes_connected(node1, node2),
                        f"Nodes {node1} and {node2} should remain connected within group1"
                    )
                    
        for node1 in group2:
            for node2 in group2:
                if node1 != node2:
                    self.assertTrue(
                        self.network.are_nodes_connected(node1, node2),
                        f"Nodes {node1} and {node2} should remain connected within group2"
                    )
    
    def test_resolve_partition(self):
        """Test resolving a network partition."""
        # First create a partition
        group1 = ["node1", "node2"]
        group2 = ["node3", "node4"]
        self.network.simulate_network_partition(group1, group2)
        
        # Verify partition is in effect
        self.assertFalse(self.network.are_nodes_connected("node1", "node3"))
        
        # Resolve the partition
        self.network.resolve_network_partition()
        
        # Verify all nodes are reconnected
        for node1 in self.node_ids:
            for node2 in self.node_ids:
                if node1 != node2:
                    self.assertTrue(
                        self.network.are_nodes_connected(node1, node2),
                        f"Nodes {node1} and {node2} should be reconnected after resolving partition"
                    )
    
    def test_resolve_specific_partition(self):
        """Test resolving a specific network partition between groups."""
        # First create a partition
        group1 = ["node1", "node2"]
        group2 = ["node3", "node4"]
        self.network.simulate_network_partition(group1, group2)
        
        # Verify partition is in effect
        self.assertFalse(self.network.are_nodes_connected("node1", "node3"))
        
        # Resolve the specific partition
        self.network.resolve_network_partition(group1, group2)
        
        # Verify the specified groups are reconnected
        for node1 in group1:
            for node2 in group2:
                self.assertTrue(
                    self.network.are_nodes_connected(node1, node2),
                    f"Nodes {node1} and {node2} should be reconnected after resolving partition"
                )

if __name__ == "__main__":
    unittest.main()
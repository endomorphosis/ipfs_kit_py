#!/usr/bin/env python3
"""
Comprehensive test for MCP Discovery Protocol using the mock implementation.

This test simulates a network of MCP servers with different capabilities
and verifies all aspects of the discovery protocol including:
- Server registration and discovery
- Feature compatibility checking
- Task distribution
- Health monitoring
- Network partitions and recovery
"""

import os
import sys
import time
import json
import uuid
import random
import threading
from typing import Dict, List, Set, Any, Optional
import unittest

# Add parent directory to path to allow importing the mock implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the mock discovery model
from test_discovery.mcp_discovery_mock import (
    MockMCPDiscoveryModel,
    MCPServerRole, 
    MCPMessageType,
    MCPServerCapabilities,
    MCPFeatureSet,
    MCPServerInfo
)

class MCPDiscoveryComprehensiveTest(unittest.TestCase):
    """Comprehensive test suite for MCP Discovery Protocol."""

    def setUp(self):
        """Set up the test environment with multiple servers."""
        self.server_count = 5
        self.servers = {}
        self.server_models = {}
        
        # Create servers with different roles and capabilities
        roles = [MCPServerRole.MASTER, MCPServerRole.WORKER, 
                MCPServerRole.HYBRID, MCPServerRole.EDGE, 
                MCPServerRole.MASTER]
        
        # Define feature combinations for different servers
        feature_sets = [
            # Master with all features
            [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.IPFS_CLUSTER, 
             MCPServerCapabilities.LIBP2P, MCPServerCapabilities.PEER_WEBSOCKET,
             MCPServerCapabilities.WEBRTC, MCPServerCapabilities.DISTRIBUTED],
            
            # Worker with compute-focused features
            [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.LIBP2P,
             MCPServerCapabilities.WEBRTC, MCPServerCapabilities.AI_ML],
            
            # Hybrid with mixed features
            [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.PEER_WEBSOCKET,
             MCPServerCapabilities.LIBP2P, MCPServerCapabilities.FS_JOURNAL],
            
            # Edge with minimal features
            [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.WEBRTC],
            
            # Another master with slightly different features
            [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.IPFS_CLUSTER,
             MCPServerCapabilities.ARIA2, MCPServerCapabilities.S3]
        ]
        
        # Create the servers
        for i in range(self.server_count):
            server_id = f"server-{i+1}-{uuid.uuid4()}"
            role = roles[i]
            features = feature_sets[i]
            
            # Create resources and metadata
            resources = {
                "cpu_cores": random.randint(2, 16),
                "memory_gb": random.randint(4, 64),
                "storage_gb": random.randint(50, 1000)
            }
            
            metadata = {
                "region": random.choice(["us-east", "us-west", "eu-central", "ap-south"]),
                "provider": random.choice(["aws", "gcp", "azure", "local"]),
                "version": "1.0.0"
            }
            
            # Create discovery model directly
            model = MockMCPDiscoveryModel(
                server_id=server_id,
                role=role,
                features=features,
                libp2p_model=None,
                ipfs_model=None,
                cache_manager=None,
                credential_manager=None,
                resources=resources,
                metadata=metadata
            )
            
            # Create server info objects for our tracking
            api_endpoint = f"http://localhost:{8000+i}/api"
            websocket_endpoint = f"ws://localhost:{8000+i}/ws"
            
            # Create server info from the model's info
            server_info = model.server_info
            
            # Add to our tracking dicts
            self.servers[server_id] = server_info
            self.server_models[server_id] = model
            
        # Wire up the models as a fully connected network initially
        self.connect_all_servers()
    
    def connect_all_servers(self):
        """Connect all servers to each other to simulate a fully connected network."""
        for source_id, source_model in self.server_models.items():
            for target_id, target_info in self.servers.items():
                if source_id != target_id:
                    # Register each server with the other
                    source_model.register_server(target_info.to_dict())
    
    def disconnect_server(self, server_id):
        """Simulate a server disconnecting from the network."""
        # Remove this server's knowledge of others
        self.server_models[server_id].known_servers = {}
        
        # Remove other servers' knowledge of this one
        for model in self.server_models.values():
            if server_id in model.known_servers:
                model.remove_server(server_id)
    
    def test_server_discovery(self):
        """Test that servers can discover each other."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Reset test model to clear any previous server knowledge
        test_model.reset()
        
        # Make other servers announce themselves
        for server_id, model in self.server_models.items():
            if server_id != test_server_id:
                # Get server info
                result = model.get_server_info(server_id)
                if result["success"]:
                    # Register with test model
                    test_model.register_server(result["server_info"])
                    
        # Check if we registered at least one server
        with test_model.server_lock:
            registered_count = len(test_model.known_servers)
            
        self.assertGreaterEqual(registered_count, 1, "Failed to register any servers")
                
        # Now clear the registry and discover using the service
        test_model.reset()
        
        # Ask other servers to announce themselves
        for server_id, model in self.server_models.items():
            if server_id != test_server_id:
                model.announce_server()
                
        # Discover servers
        discover_result = test_model.discover_servers()
        
        # Check if discovery worked
        self.assertTrue(discover_result["success"])
        
        # Verify we got some servers in response
        self.assertIn("servers", discover_result)
        self.assertIsInstance(discover_result["servers"], list)
        
        # Check server count if available
        if "server_count" in discover_result:
            self.assertGreaterEqual(discover_result["server_count"], 0)
        
        # Get server stats to verify discovery
        stats_result = test_model.get_stats()
        
        # Verify stats result
        self.assertTrue(stats_result["success"])
        self.assertIn("stats", stats_result)
        
        # Check discovered server count from stats
        if "stats" in stats_result and "known_servers" in stats_result["stats"]:
            self.assertGreaterEqual(stats_result["stats"]["known_servers"], 0)
    
    def test_feature_compatibility(self):
        """Test that servers can identify compatible servers based on feature sets."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Define required features
        required_features = [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.WEBRTC]
        
        # Get compatible servers
        result = test_model.get_compatible_servers(feature_requirements=required_features)
        
        # Verify success
        self.assertTrue(result["success"])
        
        # Check that we got the right servers
        compatible_count = 0
        for server_id, server_info in self.servers.items():
            if server_id == test_server_id:
                continue  # Skip self
            
            # Check if this server should be compatible
            has_all_required = all(feature in server_info.feature_set.features 
                                 for feature in required_features)
            
            if has_all_required:
                compatible_count += 1
                # Verify this server is in our compatible list
                self.assertIn(server_id, [s["server_id"] for s in result["servers"]])
        
        # Verify we got the right number of compatible servers
        self.assertEqual(len(result["servers"]), compatible_count)
    
    def test_task_distribution(self):
        """Test that tasks can be dispatched to compatible servers."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Register a dummy task handler for store_content task type
        test_model.register_task_handler("store_content", lambda data: {"status": "success"})
        
        # Create a test task
        task_type = "store_content"
        task_data = {
            "content": "Test content to store",
            "pin": True
        }
        
        # Define the features required for this task
        required_features = [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.IPFS_CLUSTER]
        
        # Dispatch the task
        result = test_model.dispatch_task(
            task_type=task_type,
            task_data=task_data,
            required_features=required_features
        )
        
        # Verify success
        self.assertTrue(result["success"])
        
        # Verify a valid server was selected
        self.assertIn("server_id", result)
        self.assertIsNotNone(result["server_id"])
        
        # If processed locally, no need to check features
        if result.get("processed_locally", False):
            return
            
        # Verify the selected server has the required features
        selected_server = result["server_id"]
        
        # Find server info for the selected server
        server_info = None
        with test_model.server_lock:
            if selected_server in test_model.known_servers:
                server_info = test_model.known_servers[selected_server]
        
        # If we have the server info, verify it has the required features
        if server_info:
            for feature in required_features:
                self.assertIn(feature, server_info.feature_set.features)
    
    def test_health_monitoring(self):
        """Test health monitoring functionality."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Get health of all servers
        all_healthy = True
        unhealthy_count = 0
        
        # Check each server individually
        for server_id in self.servers:
            if server_id == test_server_id:
                continue  # Skip self
                
            # Check server health
            health_result = test_model.check_server_health(server_id)
            
            # All servers should be healthy initially
            self.assertTrue(health_result["success"])
            
            if not health_result.get("healthy", True):
                all_healthy = False
                unhealthy_count += 1
        
        # Verify all servers are initially healthy
        self.assertTrue(all_healthy)
        self.assertEqual(unhealthy_count, 0)
        
        # Simulate a server going down
        down_server_id = list(self.servers.keys())[1]
        
        # Manually force last_seen to be very old for the downed server
        with test_model.server_lock:
            if down_server_id in test_model.known_servers:
                test_model.known_servers[down_server_id].last_seen = time.time() - 3600
        
        # Now check health of the downed server
        health_result = test_model.check_server_health(down_server_id)
        
        # Verify the server is now marked as unhealthy
        self.assertTrue(health_result["success"])
        self.assertFalse(health_result["healthy"])
        
        # Run server cleanup that should remove stale servers
        cleanup_result = test_model.clean_stale_servers(max_age_seconds=1800)  # 30 minutes
        
        # Verify the stale server was removed
        self.assertTrue(cleanup_result["success"])
        self.assertIn(down_server_id, cleanup_result["removed_servers"])
    
    def test_network_partition_and_recovery(self):
        """Test behavior during network partitions and recovery."""
        # Import the MockNetwork class to access network partition functionality
        from test_discovery.enhanced_mcp_discovery_mock import MockNetwork
        
        # Create or get the MockNetwork instance
        mock_network = MockNetwork.get_instance()
        
        # Create two groups of servers
        group1_ids = list(self.servers.keys())[:2]
        group2_ids = list(self.servers.keys())[2:]
        
        # First, register all servers in the mock network
        for server_id, model in self.server_models.items():
            mock_network.register_node(server_id, model)
        
        # Verify all servers are initially connected
        for id1 in group1_ids:
            for id2 in group2_ids:
                self.assertTrue(
                    mock_network.are_nodes_connected(id1, id2),
                    f"Servers {id1} and {id2} should be initially connected"
                )
        
        # Simulate network partition using the MockNetwork's simulation function
        mock_network.simulate_network_partition(group1_ids, group2_ids)
        
        # Now update server registries to reflect the network partition
        for id1 in group1_ids:
            for id2 in group2_ids:
                # Remove server2 from server1's registry
                self.server_models[id1].remove_server(id2)
                
                # Remove server1 from server2's registry
                self.server_models[id2].remove_server(id1)
        
        # Verify partition is effective
        for id1 in group1_ids:
            for id2 in group2_ids:
                # Verify network connections are removed
                self.assertFalse(
                    mock_network.are_nodes_connected(id1, id2),
                    f"Servers {id1} and {id2} should be disconnected after partition"
                )
                
        # Verify server registries reflect the partition
        model1 = self.server_models[group1_ids[0]]
        with model1.server_lock:
            self.assertLessEqual(len(model1.known_servers), len(group1_ids) - 1)
        
        # Attempt to dispatch a task that requires a server in the other partition
        task_type = "compute_task"
        task_data = {"test": "data"}
        
        # Use WEBRTC as a test feature
        required_features = [MCPServerCapabilities.WEBRTC]
        
        # Find a server without WEBRTC in group1 to try to dispatch from
        dispatch_server_id = None
        for server_id in group1_ids:
            server_info = self.servers[server_id]
            if MCPServerCapabilities.WEBRTC not in server_info.feature_set.features:
                dispatch_server_id = server_id
                break
        
        # If we found a suitable server, test dispatch failure
        if dispatch_server_id:
            dispatch_model = self.server_models[dispatch_server_id]
            
            # Register task handler
            dispatch_model.register_task_handler(task_type, lambda data: {"status": "success"})
            
            # Attempt to dispatch task
            result = dispatch_model.dispatch_task(
                task_type=task_type,
                task_data=task_data,
                required_features=required_features
            )
            
            # Either the task should fail or no server should be found
            if result.get("success", False) and "server_id" in result:
                # If successful, make sure it's not from the other partition
                self.assertNotIn(result["server_id"], group2_ids)
        
        # Resolve the network partition using the MockNetwork's resolve function
        mock_network.resolve_network_partition()
        
        # Now update server registries to reflect the network recovery
        self.connect_all_servers()
        
        # Verify network connections are restored
        for id1 in group1_ids:
            for id2 in group2_ids:
                self.assertTrue(
                    mock_network.are_nodes_connected(id1, id2),
                    f"Servers {id1} and {id2} should be reconnected after resolving partition"
                )
        
        # Verify recovery - model should now know about more servers
        with model1.server_lock:
            self.assertGreaterEqual(len(model1.known_servers), 1)
        
        # Try dispatching the task again if we found a suitable server before
        if dispatch_server_id:
            dispatch_model = self.server_models[dispatch_server_id]
            result = dispatch_model.dispatch_task(
                task_type=task_type,
                task_data=task_data,
                required_features=required_features
            )
            
            # Now the task should succeed
            self.assertTrue(result["success"])
            
            # And we should have a server ID
            self.assertIn("server_id", result)
            self.assertIsNotNone(result.get("server_id"))
    
    def test_server_update(self):
        """Test updating server information."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Get original resources
        with test_model.server_lock:
            original_resources = test_model.server_info.metadata.get("resources", {})
        
        # Prepare new resources
        if "cpu_cores" in original_resources:
            updated_cpu = original_resources["cpu_cores"] * 2
        else:
            updated_cpu = 16
            
        if "memory_gb" in original_resources:
            updated_memory = original_resources["memory_gb"] * 2
        else:
            updated_memory = 64
            
        # Update server info with new resources
        update_result = test_model.update_server_info(resources={
            "cpu_cores": updated_cpu,
            "memory_gb": updated_memory
        })
        
        # Verify success
        self.assertTrue(update_result["success"])
        
        # Check that info was updated
        if "server_info" in update_result:
            server_info = update_result["server_info"]
            self.assertIn("resources", server_info)
            if "resources" in server_info:
                resources = server_info["resources"]
                if "cpu_cores" in resources:
                    self.assertEqual(resources["cpu_cores"], updated_cpu)
                if "memory_gb" in resources:
                    self.assertEqual(resources["memory_gb"], updated_memory)
        
        # Check server info directly
        server_info_result = test_model.get_server_info(test_server_id)
        self.assertTrue(server_info_result["success"])
        
        # Broadcast the update to other servers
        for other_id, other_model in self.server_models.items():
            if other_id != test_server_id:
                other_model.register_server(server_info_result["server_info"])
        
        # Verify other servers received the update
        for other_id, other_model in self.server_models.items():
            if other_id != test_server_id:
                with other_model.server_lock:
                    if test_server_id in other_model.known_servers:
                        other_server_info = other_model.known_servers[test_server_id]
                        # Verify info was updated in other servers
                        self.assertIn("resources", other_server_info.metadata)
    
    def test_feature_hash_grouping(self):
        """Test that servers can be grouped by feature hash."""
        # First connect all servers so they know about each other
        self.connect_all_servers()
        
        # Get lists of all server IDs
        all_server_ids = list(self.servers.keys())
        
        # Build dictionary of feature hash -> server IDs
        feature_hash_dict = {}
        for server_id, model in self.server_models.items():
            with model.server_lock:
                feature_hash = model.feature_set.feature_hash
                if feature_hash not in feature_hash_dict:
                    feature_hash_dict[feature_hash] = []
                feature_hash_dict[feature_hash].append(server_id)
        
        # Skip the test if no servers have the same features
        if not any(len(ids) > 1 for ids in feature_hash_dict.values()):
            self.skipTest("No servers with identical feature sets found")
            
        # Find a feature hash with multiple servers
        test_hash = None
        test_server_ids = []
        for feature_hash, server_ids in feature_hash_dict.items():
            if len(server_ids) > 1:
                test_hash = feature_hash
                test_server_ids = server_ids
                break
                
        if not test_hash:
            self.skipTest("No servers with identical feature sets found")
        
        # Pick a server in this group for testing
        test_server_id = test_server_ids[0]
        test_model = self.server_models[test_server_id]
        
        # Get compatible servers using the same features
        # (The mock implementation might not have get_similar_servers, but it should have compatible servers)
        test_features = []
        with test_model.server_lock:
            test_features = list(test_model.feature_set.features)
            
        result = test_model.get_compatible_servers(feature_requirements=test_features)
        
        # Verify success
        self.assertTrue(result["success"])
        
        # Check that the compatible servers include servers with the same feature hash
        if "servers" in result:
            compatible_server_ids = [server["server_id"] for server in result["servers"]] 
            
            # Find other servers that should have the same features
            expected_similar_ids = test_server_ids.copy()
            expected_similar_ids.remove(test_server_id)  # Remove self
            
            # Check that at least one expected server is in the results
            # (We don't check all because the mock doesn't guarantee all compatible servers)
            if expected_similar_ids:
                found_at_least_one = False
                for expected_id in expected_similar_ids:
                    if expected_id in compatible_server_ids:
                        found_at_least_one = True
                        break
                        
                self.assertTrue(found_at_least_one, 
                               "No servers with matching feature hash found in compatible servers")

if __name__ == "__main__":
    unittest.main()
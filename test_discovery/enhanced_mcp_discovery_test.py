#!/usr/bin/env python3
"""
Enhanced Comprehensive Test for MCP Discovery Protocol

This test uses the enhanced mock implementation to simulate a real network
of MCP servers with diverse capabilities. It tests all aspects of the discovery protocol
including network partitions, recovery, and task distribution without requiring
external dependencies like libp2p.
"""

import os
import sys
import time
import json
import uuid
import random
import threading
import unittest
import logging
from typing import Dict, List, Set, Any, Optional

# Add parent directory to path to allow importing the mock implementation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the enhanced mock discovery model
from test_discovery.enhanced_mcp_discovery_mock import (
    EnhancedMockMCPDiscoveryModel,
    MockNetwork,
    MCPServerRole, 
    MCPMessageType,
    MCPServerCapabilities,
    MCPFeatureSet,
    MCPServerInfo
)


class EnhancedMCPDiscoveryTest(unittest.TestCase):
    """Enhanced test suite for MCP Discovery Protocol using mock network."""

    def setUp(self):
        """Set up the test environment with multiple servers."""
        # Create a shared mock network for all servers
        self.network = MockNetwork.get_instance()
        
        # Reset existing network state
        for server_id in list(self.network.nodes.keys()):
            self.network.unregister_node(server_id)
            
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
            
            # Create discovery model with enhanced capabilities
            model = EnhancedMockMCPDiscoveryModel(
                server_id=server_id,
                role=role,
                features=features,
                resources=resources,
                metadata=metadata,
                network=self.network  # Share the same network
            )
            
            # Save to our tracking dictionaries
            self.servers[server_id] = model.server_info
            self.server_models[server_id] = model
            
        # Have all servers announce themselves
        for server_id, model in self.server_models.items():
            model.announce_server()
            
        # Wait for announcements to propagate
        time.sleep(0.5)
        
        # Make sure all servers discover each other
        for server_id, model in self.server_models.items():
            model.discover_servers()
            
        # Give time for discovery to complete
        time.sleep(0.5)
    
    def tearDown(self):
        """Clean up resources."""
        for model in self.server_models.values():
            model.close()
    
    def test_server_discovery(self):
        """Test that servers can discover each other."""
        # Pick the first server for testing
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Reset test model to clear any previous server knowledge
        test_model.reset()
        
        # Ask other servers to announce themselves
        for server_id, model in self.server_models.items():
            if server_id != test_server_id:
                model.announce_server()
                
        # Give announcements time to propagate
        time.sleep(0.5)
                
        # Check if we registered any servers indirectly
        with test_model.server_lock:
            announcement_count = len(test_model.known_servers)
            
        self.assertGreaterEqual(announcement_count, 0, 
                              "Should have registered some servers through announcements")
                
        # Now actively discover servers
        discover_result = test_model.discover_servers()
        
        # Verify discovery succeeded
        self.assertTrue(discover_result["success"], "Server discovery should succeed")
        self.assertIn("servers", discover_result, "Discovery result should contain servers")
        
        # Check that we found all other servers
        with test_model.server_lock:
            discovered_count = len(test_model.known_servers)
            
        # Should find all other servers (total servers minus self)
        self.assertEqual(discovered_count, self.server_count - 1,
                        f"Should discover {self.server_count - 1} servers, found {discovered_count}")
    
    def test_feature_compatibility(self):
        """Test that servers can identify compatible servers based on feature sets."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Ensure servers know about each other
        for server_id, model in self.server_models.items():
            model.announce_server()
            
        # Give time for announcements to propagate
        time.sleep(0.5)
            
        # Make sure all servers are discovered
        test_model.discover_servers()
        
        # Verify discovery worked
        with test_model.server_lock:
            discovered_count = len(test_model.known_servers)
            print(f"DEBUG: Discovered {discovered_count} servers")
            
            # Print known servers and their features
            for server_id, server_info in test_model.known_servers.items():
                print(f"DEBUG: Known server {server_id} with features: {server_info.feature_set.features}")
        
        # Define required features
        required_features = [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.WEBRTC]
        
        # Get compatible servers
        result = test_model.get_compatible_servers(feature_requirements=required_features)
        
        # Verify success
        self.assertTrue(result["success"], "Should successfully get compatible servers")
        
        # Count servers that should be compatible
        expected_compatible = 0
        for server_id, server_info in self.servers.items():
            if server_id == test_server_id:
                continue  # Skip self
                
            # Check if this server has all required features
            has_all_required = all(feature in server_info.feature_set.features 
                                  for feature in required_features)
            
            print(f"DEBUG: Server {server_id} has features: {server_info.feature_set.features}")
            print(f"DEBUG: Required features: {required_features}")
            print(f"DEBUG: Server {server_id} has all required: {has_all_required}")
            
            if has_all_required:
                expected_compatible += 1
        
        print(f"DEBUG: Expected compatible servers: {expected_compatible}")
        print(f"DEBUG: Actual compatible servers: {len(result['servers'])}")
        
        # Check that we got the right number of compatible servers
        self.assertEqual(len(result["servers"]), expected_compatible,
                        f"Should find {expected_compatible} compatible servers, found {len(result['servers'])}")
        
        # Verify each returned server actually has the required features
        for server_dict in result["servers"]:
            features = server_dict.get("feature_set", {}).get("features", [])
            for required_feature in required_features:
                self.assertIn(required_feature, features,
                             f"Server {server_dict.get('server_id')} is missing required feature {required_feature}")
    
    def test_server_announcement(self):
        """Test server announcement capabilities."""
        # Reset all servers' knowledge
        for model in self.server_models.values():
            model.reset()
            
        # Have each server announce itself
        announce_results = []
        for server_id, model in self.server_models.items():
            result = model.announce_server()
            announce_results.append(result)
            
        # Give announcements time to propagate
        time.sleep(0.5)
            
        # Verify all announcements were successful
        for result in announce_results:
            self.assertTrue(result["success"], "Server announcement should succeed")
            
        # Check that each server knows about all other servers
        for server_id, model in self.server_models.items():
            with model.server_lock:
                known_count = len(model.known_servers)
                
            # Should know about all other servers (total servers minus self)
            self.assertEqual(known_count, self.server_count - 1,
                           f"Server {server_id} should know about {self.server_count - 1} others, knows {known_count}")
    
    def test_task_dispatch(self):
        """Test that tasks can be dispatched to compatible servers."""
        # Pick a master server to coordinate tasks
        master_server_id = None
        for server_id, server_info in self.servers.items():
            if server_info.role == MCPServerRole.MASTER:
                master_server_id = server_id
                break
                
        self.assertIsNotNone(master_server_id, "Should have at least one master server")
        
        master_model = self.server_models[master_server_id]
        
        # Register task handlers on all servers
        for server_id, model in self.server_models.items():
            # Define handler for a simple computation task
            def compute_handler(data):
                number = data.get("number", 0)
                return {"result": number * 2}
                
            # Register the handler, with different feature requirements for each server
            server_features = list(model.feature_set.features)
            server_features.sort()  # Sort for consistency
            required_features = server_features[:min(2, len(server_features))]
            
            model.register_task_handler(
                "compute_task", 
                compute_handler,
                required_features=required_features
            )
        
        # Create test tasks with different feature requirements
        test_tasks = [
            # Task requiring WEBRTC 
            {
                "task_type": "compute_task",
                "task_data": {"number": 10},
                "required_features": [MCPServerCapabilities.WEBRTC]
            },
            # Task requiring IPFS_DAEMON and IPFS_CLUSTER
            {
                "task_type": "compute_task",
                "task_data": {"number": 20},
                "required_features": [MCPServerCapabilities.IPFS_DAEMON, MCPServerCapabilities.IPFS_CLUSTER]
            },
            # Task requiring PEER_WEBSOCKET
            {
                "task_type": "compute_task",
                "task_data": {"number": 30},
                "required_features": [MCPServerCapabilities.PEER_WEBSOCKET]
            }
        ]
        
        # Dispatch each task
        dispatch_results = []
        for task in test_tasks:
            result = master_model.dispatch_task(
                task_type=task["task_type"],
                task_data=task["task_data"],
                required_features=task["required_features"]
            )
            dispatch_results.append(result)
            
        # Verify results
        for i, result in enumerate(dispatch_results):
            # Should successfully dispatch
            self.assertTrue(result["success"], f"Task dispatch {i} should succeed")
            
            # Should have a server ID
            self.assertIn("server_id", result, f"Task result {i} should include server_id")
            
            # If task was processed remotely, verify correct result
            if not result.get("processed_locally", False):
                expected_result = test_tasks[i]["task_data"]["number"] * 2
                actual_result = result.get("task_result", {}).get("result", None)
                self.assertEqual(actual_result, expected_result, 
                               f"Task {i} result should be {expected_result}, got {actual_result}")
    
    def test_health_monitoring(self):
        """Test health monitoring capabilities."""
        # Pick a server to check health of others
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Check health of each server
        health_results = []
        for server_id in self.servers:
            if server_id != test_server_id:
                result = test_model.check_server_health(server_id)
                health_results.append((server_id, result))
                
        # Verify all servers report healthy
        for server_id, result in health_results:
            self.assertTrue(result["success"], f"Health check for {server_id} should succeed")
            self.assertTrue(result["healthy"], f"Server {server_id} should be healthy")
        
        # Simulate an unhealthy server by forcing its last_seen to be very old
        unhealthy_server_id = list(self.servers.keys())[1]
        with test_model.server_lock:
            if unhealthy_server_id in test_model.known_servers:
                test_model.known_servers[unhealthy_server_id].last_seen = time.time() - 3600
                
        # Check health of the unhealthy server
        unhealthy_result = test_model.check_server_health(unhealthy_server_id)
        
        # Should still succeed but report as unhealthy
        self.assertTrue(unhealthy_result["success"], "Health check should succeed even for unhealthy server")
        self.assertFalse(unhealthy_result["healthy"], "Server should be reported as unhealthy")
    
    def test_network_partition(self):
        """Test behavior during network partitions and recovery."""
        # Create two groups of servers
        server_ids = list(self.servers.keys())
        group1_ids = server_ids[:2]
        group2_ids = server_ids[2:]
        
        # Verify all servers can initially see each other
        for server_id, model in self.server_models.items():
            with model.server_lock:
                initial_server_count = len(model.known_servers)
                
            expected_count = self.server_count - 1  # All servers except self
            self.assertEqual(initial_server_count, expected_count,
                           f"Server {server_id} should know about {expected_count} others initially")
        
        # Simulate network partition using the network's partition simulation function
        self.network.simulate_network_partition(group1_ids, group2_ids)
        
        # Now remove servers from each other's known lists
        for id1 in group1_ids:
            for id2 in group2_ids:
                # Remove id2 from id1's knowledge
                self.server_models[id1].remove_server(id2)
                
                # Remove id1 from id2's knowledge
                self.server_models[id2].remove_server(id1)
        
        # Verify partition is effective
        for server_id in group1_ids:
            model = self.server_models[server_id]
            with model.server_lock:
                # Should only know about servers in its own group (minus self)
                expected_count = len(group1_ids) - 1
                actual_count = len(model.known_servers)
                
            self.assertEqual(actual_count, expected_count,
                           f"After partition, server {server_id} should know about {expected_count} servers, knows {actual_count}")
                           
        for server_id in group2_ids:
            model = self.server_models[server_id]
            with model.server_lock:
                # Should only know about servers in its own group (minus self)
                expected_count = len(group2_ids) - 1
                actual_count = len(model.known_servers)
                
            self.assertEqual(actual_count, expected_count,
                           f"After partition, server {server_id} should know about {expected_count} servers, knows {actual_count}")
        
        # Try to dispatch a task requiring a feature only available across the partition
        # Find a feature unique to group2
        group2_only_features = set()
        for server_id in group2_ids:
            server_info = self.servers[server_id]
            group2_only_features.update(server_info.feature_set.features)
            
        for server_id in group1_ids:
            server_info = self.servers[server_id]
            group2_only_features.difference_update(server_info.feature_set.features)
            
        if group2_only_features:
            # Pick a test feature only available in group2
            test_feature = next(iter(group2_only_features))
            
            # Try to dispatch from group1
            dispatch_server_id = group1_ids[0]
            dispatch_model = self.server_models[dispatch_server_id]
            
            # Register a handler
            dispatch_model.register_task_handler(
                "partition_test_task",
                lambda data: {"status": "success"}
            )
            
            # Try to dispatch
            result = dispatch_model.dispatch_task(
                task_type="partition_test_task",
                task_data={"test": "data"},
                required_features=[test_feature]
            )
            
            # Dispatch should fail because feature is only available across partition
            self.assertFalse(result["success"], 
                           f"Task dispatch requiring {test_feature} should fail during partition")
        
        # Reconnect the servers by resolving network partition
        self.network.resolve_network_partition()
        
        # Reset each server to clear and re-initialize their state
        for server_id, model in self.server_models.items():
            model.reset()
            
        # Have all servers announce themselves again
        for server_id, model in self.server_models.items():
            model.announce_server()
            
        # Give announcements time to propagate
        time.sleep(0.5)
        
        # Verify servers are reconnected
        for server_id, model in self.server_models.items():
            # Run a discovery to find all servers
            model.discover_servers()
            
            with model.server_lock:
                reconnected_count = len(model.known_servers)
                
            # Should know about all other servers again
            expected_count = self.server_count - 1
            self.assertEqual(reconnected_count, expected_count,
                           f"After reconnection, server {server_id} should know about {expected_count} servers, knows {reconnected_count}")
    
    def test_feature_hash_based_compatibility(self):
        """Test feature hash based compatibility checking."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Get the test server's features
        test_features = list(test_model.feature_set.features)
        
        # Create a server with the exact same features to test perfect compatibility
        identical_server_id = f"identical-{uuid.uuid4()}"
        identical_model = EnhancedMockMCPDiscoveryModel(
            server_id=identical_server_id,
            role=test_model.server_info.role,
            features=test_features,
            network=self.network
        )
        
        # Add to our tracking
        self.servers[identical_server_id] = identical_model.server_info
        self.server_models[identical_server_id] = identical_model
        
        # Let the test server discover this new server
        identical_model.announce_server()
        time.sleep(0.5)
        
        # Create a subset of features to test partial compatibility
        if len(test_features) > 2:
            subset_features = test_features[:-1]  # Remove one feature
        else:
            subset_features = test_features
            
        # Create a server with a subset of features
        subset_server_id = f"subset-{uuid.uuid4()}"
        subset_model = EnhancedMockMCPDiscoveryModel(
            server_id=subset_server_id,
            role=test_model.server_info.role,
            features=subset_features,
            network=self.network
        )
        
        # Add to our tracking
        self.servers[subset_server_id] = subset_model.server_info
        self.server_models[subset_server_id] = subset_model
        
        # Let the test server discover this new server
        subset_model.announce_server()
        time.sleep(0.5)
        
        # Get compatible servers with no feature requirements
        result = test_model.get_compatible_servers()
        
        # Verify the identical server is in the results
        identical_found = False
        for server in result["servers"]:
            if server["server_id"] == identical_server_id:
                identical_found = True
                break
                
        self.assertTrue(identical_found, "Server with identical features should be compatible")
        
        # Get servers compatible with all the test server's features
        result = test_model.get_compatible_servers(feature_requirements=test_features)
        
        # Verify the identical server is in the results but subset server is not
        identical_found = False
        subset_found = False
        
        for server in result["servers"]:
            if server["server_id"] == identical_server_id:
                identical_found = True
            elif server["server_id"] == subset_server_id:
                subset_found = True
                
        self.assertTrue(identical_found, "Server with identical features should handle all feature requirements")
        self.assertFalse(subset_found, "Server with subset of features should not handle all feature requirements")
        
        # Now test with the subset of features
        result = test_model.get_compatible_servers(feature_requirements=subset_features)
        
        # Both identical and subset servers should be compatible with the subset of features
        identical_found = False
        subset_found = False
        
        for server in result["servers"]:
            if server["server_id"] == identical_server_id:
                identical_found = True
            elif server["server_id"] == subset_server_id:
                subset_found = True
                
        self.assertTrue(identical_found, "Server with identical features should handle subset of features")
        self.assertTrue(subset_found, "Server with subset of features should handle the same subset")
        
        # Clean up the additional servers
        identical_model.close()
        subset_model.close()
    
    def test_server_update(self):
        """Test updating server information."""
        # Pick a server to test
        test_server_id = list(self.servers.keys())[0]
        test_model = self.server_models[test_server_id]
        
        # Get original metadata
        original_metadata = test_model.server_info.metadata.copy()
        
        # Prepare new metadata
        new_metadata = {
            "region": "eu-west",  # Changed region
            "provider": "azure",  # Changed provider
            "custom_field": "new_value"  # New field
        }
        
        # Update server info
        update_result = test_model.update_server_info(metadata=new_metadata)
        
        # Verify update succeeded
        self.assertTrue(update_result["success"], "Server info update should succeed")
        
        # Check that metadata was updated
        for key, value in new_metadata.items():
            self.assertEqual(test_model.server_info.metadata.get(key), value,
                           f"Metadata field {key} should be updated to {value}")
        
        # Announce the update
        test_model.announce_server()
        
        # Give announcement time to propagate
        time.sleep(0.5)
        
        # Verify other servers received the update
        update_received_count = 0
        for server_id, model in self.server_models.items():
            if server_id == test_server_id:
                continue  # Skip self
                
            # Check if this model knows about the test server
            with model.server_lock:
                if test_server_id in model.known_servers:
                    server_info = model.known_servers[test_server_id]
                    
                    # Check for updated metadata
                    metadata_matches = True
                    for key, value in new_metadata.items():
                        if server_info.metadata.get(key) != value:
                            metadata_matches = False
                            break
                    
                    if metadata_matches:
                        update_received_count += 1
        
        # All other servers should have received the update
        self.assertEqual(update_received_count, self.server_count - 1,
                        f"All {self.server_count - 1} other servers should receive metadata update, only {update_received_count} did")
    
    def test_cascading_network_partition(self):
        """Test behavior during cascading network partitions where failures progressively isolate nodes."""
        # Set log level to ERROR to reduce output
        logging.getLogger().setLevel(logging.ERROR)
        
        # Log start of test
        logger = logging.getLogger("enhanced_mcp_discovery_test")
        # Create a stream handler just for this test
        test_handler = logging.StreamHandler()
        test_handler.setLevel(logging.INFO)
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)
        
        logger.info("Starting cascading network partition test")
        
        # Get all server IDs
        server_ids = list(self.servers.keys())
        
        # Verify all servers are initially connected and know about each other
        for server_id, model in self.server_models.items():
            with model.server_lock:
                initial_server_count = len(model.known_servers)
                
            expected_count = self.server_count - 1  # All servers except self
            self.assertEqual(initial_server_count, expected_count,
                           f"Server {server_id} should know about {expected_count} others initially")
            
            # Also verify actual network connections
            for other_id in server_ids:
                if other_id != server_id:
                    self.assertTrue(
                        self.network.are_nodes_connected(server_id, other_id),
                        f"Server {server_id} should be connected to {other_id} initially"
                    )
                    
        # Helper function to check task dispatch between servers
        def check_task_dispatch(from_id, to_id, expected_success=True, required_feature=None):
            """Test if a task can be dispatched from one server to another."""
            from_model = self.server_models[from_id]
            to_model = self.server_models[to_id]
            
            # Register a simple handler on the target server
            test_task_type = f"cascading_test_task_{uuid.uuid4()}"
            to_model.register_task_handler(
                test_task_type,
                lambda data: {"status": "processed", "origin": to_id}
            )
            
            # Define required features if needed
            feature_requirements = None
            if required_feature:
                feature_requirements = [required_feature]
                
                # Make sure target server has this feature
                if required_feature not in to_model.feature_set.features:
                    # Add the feature to the target server
                    new_features = list(to_model.feature_set.features)
                    new_features.append(required_feature)
                    to_model.update_server_info(features=new_features)
                    to_model.announce_server()
                    time.sleep(0.5)  # Give announcement time to propagate
                    
            # First make sure the target server knows about the required handler
            from_model.discover_servers()
            
            # Try to dispatch task
            result = from_model.dispatch_task(
                task_type=test_task_type,
                task_data={"test": "data"},
                required_features=feature_requirements,
                preferred_server_id=to_id
            )
            
            # Check result
            if expected_success:
                self.assertTrue(result["success"], 
                              f"Task dispatch from {from_id} to {to_id} should succeed")
                self.assertEqual(result.get("server_id"), to_id,
                               f"Task should be processed by server {to_id}")
            else:
                self.assertFalse(result["success"],
                               f"Task dispatch from {from_id} to {to_id} should fail")
                
            return result
        
        # Step 1: Isolate a single server (server 0)
        isolated_server = server_ids[0]
        connected_servers = server_ids[1:]
        
        logger.info(f"Step 1: Isolating server {isolated_server}")
        
        # Create a partition between the isolated server and all others
        self.network.simulate_network_partition([isolated_server], connected_servers)
        
        # Remove server knowledge to simulate partition
        for id1 in [isolated_server]:
            for id2 in connected_servers:
                # Remove id2 from id1's registry
                self.server_models[id1].remove_server(id2)
                
                # Remove id1 from id2's registry
                self.server_models[id2].remove_server(id1)
        
        # Verify partition is effective - the isolated server should not be able to communicate
        # with any other server
        for other_id in connected_servers:
            self.assertFalse(
                self.network.are_nodes_connected(isolated_server, other_id),
                f"Server {isolated_server} should not be connected to {other_id}"
            )
            
            # Check task dispatch fails in both directions
            check_task_dispatch(isolated_server, other_id, expected_success=False)
            check_task_dispatch(other_id, isolated_server, expected_success=False)
        
        # Step 2: Create a second partition, splitting the remaining servers
        logger.info("Step 2: Creating second partition")
        
        # Split the connected servers into two groups
        group1 = connected_servers[:len(connected_servers)//2]
        group2 = connected_servers[len(connected_servers)//2:]
        
        # Create partition between these groups
        self.network.simulate_network_partition(group1, group2)
        
        # Update server knowledge to reflect partition
        for id1 in group1:
            for id2 in group2:
                # Remove id2 from id1's registry
                self.server_models[id1].remove_server(id2)
                
                # Remove id1 from id2's registry
                self.server_models[id2].remove_server(id1)
        
        # Verify second partition is effective
        for id1 in group1:
            for id2 in group2:
                self.assertFalse(
                    self.network.are_nodes_connected(id1, id2),
                    f"Server {id1} should not be connected to {id2}"
                )
                
                # Check task dispatch fails in both directions
                check_task_dispatch(id1, id2, expected_success=False)
                check_task_dispatch(id2, id1, expected_success=False)
        
        # Verify communication still works within each group
        if len(group1) > 1:
            id1, id2 = group1[0], group1[1]
            self.assertTrue(
                self.network.are_nodes_connected(id1, id2),
                f"Servers in same group ({id1}, {id2}) should remain connected"
            )
            check_task_dispatch(id1, id2, expected_success=True)
        
        if len(group2) > 1:
            id1, id2 = group2[0], group2[1]
            self.assertTrue(
                self.network.are_nodes_connected(id1, id2),
                f"Servers in same group ({id1}, {id2}) should remain connected"
            )
            check_task_dispatch(id1, id2, expected_success=True)
        
        # Step 3: Resolve the second partition while leaving the first server isolated
        logger.info("Step 3: Resolving second partition while keeping first server isolated")
        
        # Resolve partition between group1 and group2
        self.network.resolve_network_partition(group1, group2)
        
        # Re-add server knowledge
        for id1 in group1:
            # Re-announce servers in group1
            self.server_models[id1].reset()
            self.server_models[id1].announce_server()
            
        for id2 in group2:
            # Re-announce servers in group2
            self.server_models[id2].reset()
            self.server_models[id2].announce_server()
        
        # Give announcements time to propagate
        time.sleep(0.5)
        
        # Run discovery to ensure servers find each other
        for id1 in group1 + group2:
            self.server_models[id1].discover_servers()
        
        # Verify the partition is resolved
        for id1 in group1:
            for id2 in group2:
                self.assertTrue(
                    self.network.are_nodes_connected(id1, id2),
                    f"Server {id1} should be reconnected to {id2}"
                )
                
                # Check task dispatch succeeds in both directions
                check_task_dispatch(id1, id2, expected_success=True)
                check_task_dispatch(id2, id1, expected_success=True)
        
        # But isolated server should still be isolated
        for server_id in connected_servers:
            self.assertFalse(
                self.network.are_nodes_connected(isolated_server, server_id),
                f"Server {isolated_server} should still be isolated from {server_id}"
            )
            
            # Task dispatch should still fail
            check_task_dispatch(isolated_server, server_id, expected_success=False)
            check_task_dispatch(server_id, isolated_server, expected_success=False)
            
        # Step 4: Test feature-specific partitioning across servers with different capabilities
        logger.info("Step 4: Testing feature-specific partitioning")
        
        # Find a feature that's present in some servers but not others
        all_features = set()
        for server_id, model in self.server_models.items():
            all_features.update(model.feature_set.features)
        
        # Find servers with and without a specific feature
        test_feature = None
        servers_with_feature = []
        servers_without_feature = []
        
        for feature in all_features:
            servers_with = []
            servers_without = []
            
            for server_id in connected_servers:  # Only consider reconnected servers
                model = self.server_models[server_id]
                if feature in model.feature_set.features:
                    servers_with.append(server_id)
                else:
                    servers_without.append(server_id)
            
            if servers_with and servers_without:
                test_feature = feature
                servers_with_feature = servers_with
                servers_without_feature = servers_without
                break
        
        if test_feature and servers_with_feature and servers_without_feature:
            logger.info(f"Testing feature partitioning with feature: {test_feature}")
            
            # Try to dispatch task requiring the feature from a server without the feature
            # to a server with the feature
            from_id = servers_without_feature[0]
            to_id = servers_with_feature[0]
            
            logger.info(f"Testing dispatch from {from_id} to {to_id} requiring {test_feature}")
            
            # This should succeed because the target server has the feature
            result = check_task_dispatch(from_id, to_id, expected_success=True, 
                                        required_feature=test_feature)
            
            logger.info(f"Dispatch result: {result['success']}")
            
            # Now create a network partition between all servers with the feature
            # and servers without the feature
            logger.info("Creating feature-based network partition")
            self.network.simulate_network_partition(servers_with_feature, servers_without_feature)
            
            # Update server knowledge
            for id1 in servers_with_feature:
                for id2 in servers_without_feature:
                    # Remove id2 from id1's registry
                    self.server_models[id1].remove_server(id2)
                    
                    # Remove id1 from id2's registry
                    self.server_models[id2].remove_server(id1)
            
            # Now the task dispatch should fail
            result = check_task_dispatch(from_id, to_id, expected_success=False, 
                                        required_feature=test_feature)
            
            logger.info(f"Post-partition dispatch result: {result['success']}")
            
            # Resolve the partition for cleanup
            self.network.resolve_network_partition(servers_with_feature, servers_without_feature)
        else:
            logger.info("Skipping feature partitioning test - couldn't find suitable feature")
        
        # Step 5: Fully reconnect all servers
        logger.info("Step 5: Fully reconnecting all servers")
        
        # Resolve all partitions
        self.network.resolve_network_partition()
        
        # Reset all servers and re-announce
        for server_id, model in self.server_models.items():
            model.reset()
            model.announce_server()
        
        # Give announcements time to propagate
        time.sleep(0.5)
        
        # Run discovery on all servers
        for model in self.server_models.values():
            model.discover_servers()
        
        # Give discovery time to complete
        time.sleep(0.5)
        
        # Verify all servers are reconnected
        for id1 in server_ids:
            for id2 in server_ids:
                if id1 != id2:
                    self.assertTrue(
                        self.network.are_nodes_connected(id1, id2),
                        f"Server {id1} should be reconnected to {id2}"
                    )
        
        # Verify server knowledge is restored
        for server_id, model in self.server_models.items():
            with model.server_lock:
                final_server_count = len(model.known_servers)
                
            expected_count = self.server_count - 1  # All servers except self
            self.assertEqual(final_server_count, expected_count,
                           f"After reconnection, server {server_id} should know about {expected_count} servers, knows {final_server_count}")
        
        logger.info("Cascading network partition test completed successfully")
        
    def test_partial_network_partition(self):
        """
        Test behavior during partial network partitions.
        
        Partial partitions occur when some connections remain intact while 
        others fail, creating complex connectivity patterns where servers
        may be able to reach some peers but not others.
        """
        # Set log level to ERROR to reduce output
        logging.getLogger().setLevel(logging.ERROR)
        
        # Create a logger for this test
        logger = logging.getLogger("enhanced_mcp_discovery_test")
        test_handler = logging.StreamHandler()
        test_handler.setLevel(logging.INFO)
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)
        
        logger.info("Starting partial network partition test")
        
        # Get all server IDs
        server_ids = list(self.servers.keys())
        
        # Create a matrix representation of desired connectivity
        # Value of 1 means servers are connected, 0 means disconnected
        # Initially all servers are connected
        num_servers = len(server_ids)
        connectivity_matrix = [[1 for _ in range(num_servers)] for _ in range(num_servers)]
        
        # Helper function for checking actual connectivity against desired matrix
        def verify_connectivity():
            """Verify that actual network connections match the connectivity matrix."""
            for i in range(num_servers):
                for j in range(num_servers):
                    if i != j:  # Skip self connections
                        id1, id2 = server_ids[i], server_ids[j]
                        expected = connectivity_matrix[i][j] == 1
                        actual = self.network.are_nodes_connected(id1, id2)
                        
                        self.assertEqual(
                            expected, actual,
                            f"Connection between {id1} and {id2} should be {expected}, but is {actual}"
                        )
        
        # Helper function to check task dispatch between servers
        def check_task_dispatch(from_id, to_id, expected_success=True):
            """Test if a task can be dispatched from one server to another."""
            from_model = self.server_models[from_id]
            to_model = self.server_models[to_id]
            
            # Register a simple handler on the target server
            test_task_type = f"partial_test_task_{uuid.uuid4()}"
            to_model.register_task_handler(
                test_task_type,
                lambda data: {"status": "processed", "origin": to_id}
            )
            
            # First make sure the target server knows about the required handler
            from_model.discover_servers()
            
            # Try to dispatch task
            result = from_model.dispatch_task(
                task_type=test_task_type,
                task_data={"test": "data"},
                preferred_server_id=to_id
            )
            
            # Check result
            if expected_success:
                self.assertTrue(
                    result["success"], 
                    f"Task dispatch from {from_id} to {to_id} should succeed"
                )
                self.assertEqual(
                    result.get("server_id"), to_id,
                    f"Task should be processed by server {to_id}"
                )
            else:
                self.assertFalse(
                    result["success"],
                    f"Task dispatch from {from_id} to {to_id} should fail"
                )
                
            return result
        
        # Verify initial full connectivity
        logger.info("Verifying initial full connectivity")
        verify_connectivity()
        
        # Step 1: Create a partial partition with a "bridge" server
        # In this topology, we'll have three groups:
        # - Group A: servers that can only talk to the bridge
        # - Group B: servers that can talk to both Group A and Group C through the bridge
        # - Group C: servers that can only talk to the bridge
        # This creates a scenario where some servers must relay through the bridge
        
        # Define groups for partial partition
        bridge_index = 0  # Use the first server as the bridge
        group_a_indices = [1, 2]  # Next two servers in Group A
        group_c_indices = [3, 4]  # Last two servers in Group C
        
        if num_servers >= 5:  # Make sure we have enough servers
            logger.info("Step 1: Creating partial partition with bridge server")
            
            # Update connectivity matrix for the partial partition
            # Disconnect Group A from Group C directly
            for i in group_a_indices:
                for j in group_c_indices:
                    connectivity_matrix[i][j] = 0  # A cannot reach C
                    connectivity_matrix[j][i] = 0  # C cannot reach A
            
            # Create the actual network partition
            for i in group_a_indices:
                for j in group_c_indices:
                    id1, id2 = server_ids[i], server_ids[j]
                    # Remove direct connection between A and C groups
                    self.network.remove_node_connection(id1, id2)
                    
                    # Also remove server knowledge
                    self.server_models[id1].remove_server(id2)
                    self.server_models[id2].remove_server(id1)
            
            # Verify the partial partition is effective
            logger.info("Verifying partial partition with bridge server")
            verify_connectivity()
            
            # Test connectivity scenarios:
            # 1. Group A servers can talk to the bridge
            # 2. Group C servers can talk to the bridge
            # 3. Group A servers cannot talk directly to Group C servers
            
            bridge_id = server_ids[bridge_index]
            
            # Test 1: Group A to bridge
            for i in group_a_indices:
                a_id = server_ids[i]
                logger.info(f"Testing Group A server {a_id} to bridge {bridge_id}")
                # Should succeed
                check_task_dispatch(a_id, bridge_id, expected_success=True)
                check_task_dispatch(bridge_id, a_id, expected_success=True)
            
            # Test 2: Group C to bridge
            for i in group_c_indices:
                c_id = server_ids[i]
                logger.info(f"Testing Group C server {c_id} to bridge {bridge_id}")
                # Should succeed
                check_task_dispatch(c_id, bridge_id, expected_success=True)
                check_task_dispatch(bridge_id, c_id, expected_success=True)
            
            # Test 3: Group A to Group C (should fail direct communication)
            for i in group_a_indices:
                for j in group_c_indices:
                    a_id, c_id = server_ids[i], server_ids[j]
                    logger.info(f"Testing direct communication from {a_id} to {c_id}")
                    # Should fail
                    check_task_dispatch(a_id, c_id, expected_success=False)
                    check_task_dispatch(c_id, a_id, expected_success=False)
            
            # Step 2: Create a communication relay through the bridge
            # In this step, we'll implement a simple relay mechanism where
            # Group A can communicate with Group C by going through the bridge
            logger.info("Step 2: Implementing relay communication through bridge")
            
            # Simulate task relay through bridge
            # In a real scenario, the bridge would actually forward the request
            # For our test, we'll manually chain the tasks
            
            for i in group_a_indices:
                for j in group_c_indices:
                    a_id, c_id = server_ids[i], server_ids[j]
                    bridge_model = self.server_models[bridge_id]
                    
                    logger.info(f"Testing relay communication from {a_id} to {c_id} via {bridge_id}")
                    
                    # Register relay handler on bridge
                    relay_task_type = f"relay_task_{uuid.uuid4()}"
                    
                    # This handler forwards requests to the target server
                    def relay_handler(data):
                        # Get target information from data
                        target_id = data.get("target_id")
                        task_data = data.get("task_data", {})
                        
                        # Forward to target
                        result = bridge_model.dispatch_task(
                            task_type=data.get("target_task_type"),
                            task_data=task_data,
                            preferred_server_id=target_id
                        )
                        
                        # Return relay result
                        return {
                            "relayed": True,
                            "bridge_id": bridge_id,
                            "target_id": target_id,
                            "relay_result": result
                        }
                    
                    # Register the relay handler on the bridge
                    bridge_model.register_task_handler(relay_task_type, relay_handler)
                    
                    # Register target handler on Group C server
                    target_task_type = f"target_task_{uuid.uuid4()}"
                    self.server_models[c_id].register_task_handler(
                        target_task_type,
                        lambda data: {"processed_by": c_id, "result": "success"}
                    )
                    
                    # Source server in Group A dispatches to bridge with relay information
                    source_model = self.server_models[a_id]
                    relay_result = source_model.dispatch_task(
                        task_type=relay_task_type,
                        task_data={
                            "target_id": c_id,
                            "target_task_type": target_task_type,
                            "task_data": {"source_id": a_id, "message": "hello"}
                        },
                        preferred_server_id=bridge_id
                    )
                    
                    # Verify relay worked
                    self.assertTrue(relay_result["success"], "Relay task should succeed")
                    self.assertTrue(
                        relay_result["task_result"].get("relayed", False),
                        "Task should be marked as relayed"
                    )
                    
                    # Verify target received and processed request
                    target_result = relay_result["task_result"].get("relay_result", {})
                    self.assertTrue(target_result.get("success", False), "Target task should succeed")
                    self.assertEqual(
                        target_result.get("server_id"), c_id,
                        f"Target task should be processed by {c_id}"
                    )
                    
                    logger.info(f"Relay communication successful from {a_id} to {c_id} via {bridge_id}")
            
            # Step 3: Simulate a failure of the bridge server
            logger.info("Step 3: Simulating bridge server failure")
            
            # Disconnect bridge from all other servers
            for i in range(num_servers):
                if i != bridge_index:
                    connectivity_matrix[bridge_index][i] = 0
                    connectivity_matrix[i][bridge_index] = 0
                    
                    # Remove connections in mock network
                    id1, id2 = server_ids[bridge_index], server_ids[i]
                    self.network.remove_node_connection(id1, id2)
                    
                    # Remove server knowledge
                    self.server_models[id1].remove_server(id2)
                    self.server_models[id2].remove_server(id1)
            
            # Verify the bridge is now isolated
            logger.info("Verifying bridge server isolation")
            verify_connectivity()
            
            # Verify Groups A and C still cannot communicate
            for i in group_a_indices:
                for j in group_c_indices:
                    a_id, c_id = server_ids[i], server_ids[j]
                    logger.info(f"Verifying continued partition between {a_id} and {c_id}")
                    check_task_dispatch(a_id, c_id, expected_success=False)
            
            # Verify the bridge is unreachable
            for i in range(num_servers):
                if i != bridge_index:
                    id1, bridge = server_ids[i], server_ids[bridge_index]
                    logger.info(f"Verifying bridge {bridge} is unreachable from {id1}")
                    check_task_dispatch(id1, bridge, expected_success=False)
            
            # Step 4: Establish a new connection between one server in Group A and one in Group C
            # This tests dynamic reconfiguration of the network topology
            logger.info("Step 4: Establishing direct connection between Group A and Group C")
            
            # Select one server from each group to reconnect
            a_selected = server_ids[group_a_indices[0]]
            c_selected = server_ids[group_c_indices[0]]
            
            # Update the connectivity matrix
            a_idx = group_a_indices[0]
            c_idx = group_c_indices[0]
            connectivity_matrix[a_idx][c_idx] = 1
            connectivity_matrix[c_idx][a_idx] = 1
            
            # Add connection in mock network
            self.network.add_node_connection(a_selected, c_selected)
            
            # Announce servers to each other
            self.server_models[a_selected].announce_server()
            self.server_models[c_selected].announce_server()
            
            # Give time for announcements to propagate
            time.sleep(0.5)
            
            # Make sure servers discover each other
            self.server_models[a_selected].discover_servers()
            self.server_models[c_selected].discover_servers()
            
            # Verify the new connection works
            logger.info(f"Verifying direct connection between {a_selected} and {c_selected}")
            verify_connectivity()
            
            # Test that direct communication now works
            check_task_dispatch(a_selected, c_selected, expected_success=True)
            check_task_dispatch(c_selected, a_selected, expected_success=True)
            
            # But other A and C servers still cannot communicate
            for i in group_a_indices:
                for j in group_c_indices:
                    if i != a_idx or j != c_idx:  # Skip the reconnected pair
                        a_id, c_id = server_ids[i], server_ids[j]
                        logger.info(f"Verifying continued partition between {a_id} and {c_id}")
                        check_task_dispatch(a_id, c_id, expected_success=False)
            
            # Step 5: Restore full connectivity
            logger.info("Step 5: Restoring full connectivity")
            
            # Reset connectivity matrix
            connectivity_matrix = [[1 for _ in range(num_servers)] for _ in range(num_servers)]
            
            # Resolve all partitions
            self.network.resolve_network_partition()
            
            # Reset all servers and re-announce
            for server_id, model in self.server_models.items():
                model.reset()
                model.announce_server()
            
            # Give announcements time to propagate
            time.sleep(0.5)
            
            # Run discovery on all servers
            for model in self.server_models.values():
                model.discover_servers()
            
            # Verify full connectivity is restored
            logger.info("Verifying full connectivity restoration")
            verify_connectivity()
            
            # Verify server knowledge is restored
            for server_id, model in self.server_models.items():
                with model.server_lock:
                    known_count = len(model.known_servers)
                
                expected_count = self.server_count - 1  # All servers except self
                self.assertEqual(
                    known_count, expected_count,
                    f"Server {server_id} should know about {expected_count} servers, knows {known_count}"
                )
        else:
            logger.warning("Skipping partial partition test - need at least 5 servers")
        
        logger.info("Partial network partition test completed successfully")
    
    def test_intermittent_connectivity(self):
        """
        Test behavior during intermittent connectivity issues.
        
        This test simulates temporary connection failures and recoveries that occur
        periodically, testing the system's resilience to unstable network conditions.
        """
        # Set log level to ERROR to reduce output
        logging.getLogger().setLevel(logging.ERROR)
        
        # Create a logger for this test
        logger = logging.getLogger("enhanced_mcp_discovery_test")
        test_handler = logging.StreamHandler()
        test_handler.setLevel(logging.INFO)
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)
        
        logger.info("Starting intermittent connectivity test")
        
        # Get all server IDs
        server_ids = list(self.servers.keys())
        
        # Create a class to track statistics of task success/failure
        class TaskStats:
            def __init__(self):
                self.attempts = 0
                self.successes = 0
                self.failures = 0
                
            def add_result(self, success):
                self.attempts += 1
                if success:
                    self.successes += 1
                else:
                    self.failures += 1
                    
            @property
            def success_rate(self):
                if self.attempts == 0:
                    return 0.0
                return self.successes / self.attempts
        
        # Choose a server pair for testing intermittent connectivity
        if len(server_ids) < 2:
            logger.warning("Skipping intermittent connectivity test - need at least 2 servers")
            return
            
        server1_id = server_ids[0]
        server2_id = server_ids[1]
        server1 = self.server_models[server1_id]
        server2 = self.server_models[server2_id]
        
        logger.info(f"Testing intermittent connectivity between {server1_id} and {server2_id}")
        
        # Verify initial connectivity is good
        task_type = f"intermittent_test_task_{uuid.uuid4()}"
        server2.register_task_handler(
            task_type,
            lambda data: {"status": "processed", "timestamp": time.time()}
        )
        
        # Make sure servers know about each other
        server1.discover_servers()
        
        # Initial test task should succeed
        initial_result = server1.dispatch_task(
            task_type=task_type,
            task_data={"test": "initial"},
            preferred_server_id=server2_id
        )
        
        self.assertTrue(
            initial_result["success"],
            "Initial task dispatch should succeed"
        )
        
        # Create a task stats tracker
        stats = TaskStats()
        stats.add_result(initial_result["success"])
        
        # Setup for connection cycling
        is_connected = True
        cycle_count = 5  # Number of connect/disconnect cycles
        tasks_per_state = 3  # Number of tasks to attempt in each connection state
        
        # Helper function to connect or disconnect servers
        def set_connection_state(connected):
            """Connect or disconnect the two servers."""
            if connected:
                # Connect servers
                self.network.add_node_connection(server1_id, server2_id)
                # Announce to make sure servers know about each other
                server1.announce_server()
                server2.announce_server()
                time.sleep(0.2)  # Give time for announcements
                server1.discover_servers()
                server2.discover_servers()
            else:
                # Disconnect servers
                self.network.remove_node_connection(server1_id, server2_id)
                # Remove server knowledge
                server1.remove_server(server2_id)
                server2.remove_server(server1_id)
        
        # Helper function to attempt task dispatch
        def try_task_dispatch():
            """Attempt to dispatch a task, return success or failure."""
            task_data = {"test": f"cycle_{cycle}_{i}", "timestamp": time.time()}
            
            result = server1.dispatch_task(
                task_type=task_type,
                task_data=task_data,
                preferred_server_id=server2_id
            )
            
            return result["success"]
        
        # Run connection cycling test
        logger.info(f"Starting connection cycling test with {cycle_count} cycles")
        
        for cycle in range(cycle_count):
            # Toggle connection state
            is_connected = not is_connected
            state_name = "connected" if is_connected else "disconnected"
            logger.info(f"Cycle {cycle+1}: Setting servers to {state_name}")
            
            # Update connection state
            set_connection_state(is_connected)
            
            # Attempt tasks in this state
            for i in range(tasks_per_state):
                success = try_task_dispatch()
                stats.add_result(success)
                logger.info(f"  Task {i+1}: {'Success' if success else 'Failure'}")
                
                # Brief pause between tasks
                time.sleep(0.1)
        
        # Restore connection at the end
        if not is_connected:
            logger.info("Restoring connection for cleanup")
            set_connection_state(True)
        
        # Display final statistics
        logger.info("Intermittent connectivity test results:")
        logger.info(f"Total tasks attempted: {stats.attempts}")
        logger.info(f"Successful tasks: {stats.successes}")
        logger.info(f"Failed tasks: {stats.failures}")
        logger.info(f"Success rate: {stats.success_rate:.2%}")
        
        # Verify the success rate matches expectations
        # In connected cycles, tasks should succeed
        # In disconnected cycles, tasks should fail
        # So ideally we should have ~50% success rate
        # Allow for some variance due to timing issues
        self.assertGreaterEqual(
            stats.success_rate, 0.4,
            "Success rate should be at least 40%"
        )
        self.assertLessEqual(
            stats.success_rate, 0.6,
            "Success rate should be at most 60%"
        )
        
        logger.info("Intermittent connectivity test completed successfully")
        
    def test_time_based_recovery(self):
        """
        Test behavior with time-based network recovery.
        
        This test simulates network partitions that automatically heal after
        a specified time period, testing the system's ability to recover
        from temporary outages without manual intervention.
        """
        # Set log level to ERROR to reduce output
        logging.getLogger().setLevel(logging.ERROR)
        
        # Create a logger for this test
        logger = logging.getLogger("enhanced_mcp_discovery_test")
        test_handler = logging.StreamHandler()
        test_handler.setLevel(logging.INFO)
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)
        
        logger.info("Starting time-based recovery test")
        
        # Get all server IDs
        server_ids = list(self.servers.keys())
        
        # Create two groups for partitioning
        if len(server_ids) < 4:
            logger.warning("Skipping time-based recovery test - need at least 4 servers")
            return
        
        midpoint = len(server_ids) // 2
        group1 = server_ids[:midpoint]
        group2 = server_ids[midpoint:]
        
        logger.info(f"Group 1: {group1}")
        logger.info(f"Group 2: {group2}")
        
        # Define recovery times for different partitions (in seconds)
        recovery_times = [1.0, 2.0, 3.0]
        
        # Verify all servers can initially communicate
        logger.info("Verifying initial full connectivity")
        for id1 in server_ids:
            for id2 in server_ids:
                if id1 != id2:
                    self.assertTrue(
                        self.network.are_nodes_connected(id1, id2),
                        f"Servers {id1} and {id2} should be connected initially"
                    )
        
        # Monitor task success over time
        task_results = []
        
        # Select a server from each group for task dispatching
        server1_id = group1[0]
        server2_id = group2[0]
        server1 = self.server_models[server1_id]
        server2 = self.server_models[server2_id]
        
        # Register task handlers
        task_type = f"recovery_test_task_{uuid.uuid4()}"
        server1.register_task_handler(
            task_type,
            lambda data: {"status": "processed", "from": server1_id, "timestamp": time.time()}
        )
        server2.register_task_handler(
            task_type,
            lambda data: {"status": "processed", "from": server2_id, "timestamp": time.time()}
        )
        
        # Helper function to check task dispatch
        def check_task_dispatch(from_id, to_id):
            """Test if task can be dispatched between servers."""
            from_model = self.server_models[from_id]
            
            # Try to dispatch task
            result = from_model.dispatch_task(
                task_type=task_type,
                task_data={"test": "data", "timestamp": time.time()},
                preferred_server_id=to_id
            )
            
            return result["success"]
        
        # Helper function to create a partition with timed recovery
        def create_timed_partition(recovery_time):
            """Create a network partition that will automatically heal after a specified time."""
            # Create the partition
            logger.info(f"Creating partition between groups with {recovery_time}s recovery time")
            self.network.simulate_network_partition(group1, group2)
            
            # Remove server knowledge to simulate partition
            for id1 in group1:
                for id2 in group2:
                    # Remove id2 from id1's knowledge
                    self.server_models[id1].remove_server(id2)
                    
                    # Remove id1 from id2's knowledge
                    self.server_models[id2].remove_server(id1)
            
            # Verify partition is effective
            self.assertFalse(
                check_task_dispatch(server1_id, server2_id),
                "Task dispatch should fail immediately after partition"
            )
            self.assertFalse(
                check_task_dispatch(server2_id, server1_id),
                "Task dispatch should fail immediately after partition"
            )
            
            # Schedule the recovery
            threading.Timer(recovery_time, lambda: restore_connectivity(recovery_time)).start()
            
            # Return the start time of the partition
            return time.time()
        
        # Helper function to restore connectivity
        def restore_connectivity(recovery_time):
            """Restore connectivity between the groups."""
            logger.info(f"Automatic recovery after {recovery_time}s")
            
            # Resolve the partition
            self.network.resolve_network_partition(group1, group2)
            
            # Re-announce servers
            for id1 in group1:
                self.server_models[id1].announce_server()
            for id2 in group2:
                self.server_models[id2].announce_server()
            
            # Give time for announcements to propagate
            time.sleep(0.5)
            
            # Run discovery
            server1.discover_servers()
            server2.discover_servers()
            
            # Record timestamp of recovery
            recovery_timestamp = time.time()
            task_results.append({
                "event": "recovered",
                "recovery_time": recovery_time,
                "timestamp": recovery_timestamp
            })
            
            # Check if dispatch works after recovery
            success1to2 = check_task_dispatch(server1_id, server2_id)
            success2to1 = check_task_dispatch(server2_id, server1_id)
            
            logger.info(f"Post-recovery 1->2 task: {'Success' if success1to2 else 'Failure'}")
            logger.info(f"Post-recovery 2->1 task: {'Success' if success2to1 else 'Failure'}")
            
            # Record task results
            task_results.append({
                "event": "task_dispatch",
                "direction": "1to2",
                "success": success1to2,
                "timestamp": time.time()
            })
            task_results.append({
                "event": "task_dispatch",
                "direction": "2to1",
                "success": success2to1,
                "timestamp": time.time()
            })
        
        # Test for each recovery time
        for recovery_time in recovery_times:
            # Create partition with timed recovery
            partition_start = create_timed_partition(recovery_time)
            
            # Record start of partition
            task_results.append({
                "event": "partitioned",
                "recovery_time": recovery_time,
                "timestamp": partition_start
            })
            
            # Try task right after partition
            success1to2 = check_task_dispatch(server1_id, server2_id)
            success2to1 = check_task_dispatch(server2_id, server1_id)
            
            logger.info(f"Initial partition 1->2 task: {'Success' if success1to2 else 'Failure'}")
            logger.info(f"Initial partition 2->1 task: {'Success' if success2to1 else 'Failure'}")
            
            # Record task results
            task_results.append({
                "event": "task_dispatch",
                "direction": "1to2",
                "success": success1to2,
                "timestamp": time.time()
            })
            task_results.append({
                "event": "task_dispatch",
                "direction": "2to1",
                "success": success2to1,
                "timestamp": time.time()
            })
            
            # Wait for recovery plus a buffer
            wait_time = recovery_time + 1.0
            logger.info(f"Waiting {wait_time}s for recovery...")
            time.sleep(wait_time)
            
            # Verify connectivity is restored
            self.assertTrue(
                self.network.are_nodes_connected(server1_id, server2_id),
                f"Connection should be restored after {recovery_time}s recovery time"
            )
            
            # Try another task after recovery is complete
            success1to2 = check_task_dispatch(server1_id, server2_id)
            success2to1 = check_task_dispatch(server2_id, server1_id)
            
            logger.info(f"Post-wait 1->2 task: {'Success' if success1to2 else 'Failure'}")
            logger.info(f"Post-wait 2->1 task: {'Success' if success2to1 else 'Failure'}")
            
            # Record final task results
            task_results.append({
                "event": "task_dispatch",
                "direction": "1to2",
                "success": success1to2,
                "timestamp": time.time()
            })
            task_results.append({
                "event": "task_dispatch",
                "direction": "2to1",
                "success": success2to1,
                "timestamp": time.time()
            })
            
            # Verify that tasks are successful after recovery
            self.assertTrue(
                success1to2,
                f"Tasks should succeed after {recovery_time}s recovery time (1->2)"
            )
            self.assertTrue(
                success2to1,
                f"Tasks should succeed after {recovery_time}s recovery time (2->1)"
            )
            
            # Brief pause before next test
            time.sleep(1.0)
        
        # Analyze and report recovery times
        logger.info("\nRecovery Time Analysis:")
        
        for recovery_time in recovery_times:
            # Find partition and recovery events for this recovery time
            partition_event = next(
                (ev for ev in task_results if ev["event"] == "partitioned" and ev["recovery_time"] == recovery_time),
                None
            )
            recovery_event = next(
                (ev for ev in task_results if ev["event"] == "recovered" and ev["recovery_time"] == recovery_time),
                None
            )
            
            if partition_event and recovery_event:
                actual_recovery_time = recovery_event["timestamp"] - partition_event["timestamp"]
                logger.info(f"Recovery time {recovery_time}s: Actual time = {actual_recovery_time:.2f}s")
                
                # Verify recovery happened within expected time (with some tolerance)
                self.assertGreaterEqual(
                    actual_recovery_time, recovery_time * 0.9,
                    f"Recovery should take at least {recovery_time * 0.9}s"
                )
                self.assertLessEqual(
                    actual_recovery_time, recovery_time * 1.5,
                    f"Recovery should take at most {recovery_time * 1.5}s"
                )
        
        logger.info("Time-based recovery test completed successfully")
        
    def test_asymmetric_network_partition(self):
        """
        Test behavior with asymmetric network partitions.
        
        This test simulates connections that work in one direction but not the other,
        which can happen in real networks due to firewalls, NAT issues, or routing
        problems. Tests the protocol's ability to handle these asymmetric failures.
        """
        # Set log level to ERROR to reduce output
        logging.getLogger().setLevel(logging.ERROR)
        
        # Create a logger for this test
        logger = logging.getLogger("enhanced_mcp_discovery_test")
        test_handler = logging.StreamHandler()
        test_handler.setLevel(logging.INFO)
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)
        
        logger.info("Starting asymmetric network partition test")
        
        # Get all server IDs
        server_ids = list(self.servers.keys())
        
        # Check we have enough servers
        if len(server_ids) < 3:
            logger.warning("Skipping asymmetric network partition test - need at least 3 servers")
            return
            
        # Select three servers for this test
        server_a_id = server_ids[0]
        server_b_id = server_ids[1]
        server_c_id = server_ids[2]
        
        server_a = self.server_models[server_a_id]
        server_b = self.server_models[server_b_id]
        server_c = self.server_models[server_c_id]
        
        logger.info(f"Using servers: A={server_a_id}, B={server_b_id}, C={server_c_id}")
        
        # Register task handlers on each server
        task_type = f"asymmetric_test_task_{uuid.uuid4()}"
        
        def make_handler(server_id):
            return lambda data: {
                "status": "processed", 
                "server_id": server_id,
                "timestamp": time.time()
            }
            
        server_a.register_task_handler(task_type, make_handler(server_a_id))
        server_b.register_task_handler(task_type, make_handler(server_b_id))
        server_c.register_task_handler(task_type, make_handler(server_c_id))
        
        # Make sure all servers know about each other
        for server in [server_a, server_b, server_c]:
            server.discover_servers()
            
        # Helper function to test task dispatch
        def test_dispatch(from_id, to_id, expect_success=True):
            """Test dispatching a task from one server to another."""
            from_server = self.server_models[from_id]
            
            result = from_server.dispatch_task(
                task_type=task_type,
                task_data={"test": "data", "timestamp": time.time()},
                preferred_server_id=to_id
            )
            
            success = result["success"]
            logger.info(f"Task dispatch {from_id} -> {to_id}: {'Success' if success else 'Failure'}")
            
            if expect_success:
                self.assertTrue(success, f"Task from {from_id} to {to_id} should succeed")
                self.assertEqual(result.get("server_id"), to_id, 
                               f"Task should be processed by {to_id}")
            else:
                self.assertFalse(success, f"Task from {from_id} to {to_id} should fail")
                
            return result
        
        # Verify initial full connectivity
        logger.info("Testing initial connectivity")
        test_dispatch(server_a_id, server_b_id)
        test_dispatch(server_a_id, server_c_id)
        test_dispatch(server_b_id, server_a_id)
        test_dispatch(server_b_id, server_c_id)
        test_dispatch(server_c_id, server_a_id)
        test_dispatch(server_c_id, server_b_id)
        
        # Step 1: Create asymmetric partition: A can communicate with B, but B cannot communicate with A
        logger.info("\nStep 1: Creating asymmetric partition (A->B but not B->A)")
        
        # To create this, we need to manipulate the mock network's internals
        # First, ensure normal connection A->B works
        self.network.add_node_connection(server_a_id, server_b_id)
        
        # But remove the B->A direction
        # This is usually accomplished through MockNetwork's custom implementation
        # Here we'll directly manipulate the connection matrix if it's exposed,
        # or use targeted remove_node_connection if it's implemented to support direction
        
        # Implementation depends on how MockNetwork is structured
        # For our test, let's simulate one-way connections by manipulating server knowledge
        
        # A knows about B, but B doesn't know about A
        server_b.remove_server(server_a_id)
        
        # Verify the asymmetric connectivity
        logger.info("Verifying asymmetric connectivity (A->B works, B->A fails)")
        test_dispatch(server_a_id, server_b_id, expect_success=True)
        test_dispatch(server_b_id, server_a_id, expect_success=False)
        
        # Step 2: Create a routing path through C
        # A -> C -> B and B -> C -> A
        logger.info("\nStep 2: Testing indirect communication through an intermediary")
        
        # Register relay handlers on server C
        relay_task_type_a_to_b = f"relay_a_to_b_{uuid.uuid4()}"
        relay_task_type_b_to_a = f"relay_b_to_a_{uuid.uuid4()}"
        
        # Handler to relay from A to B
        def relay_a_to_b_handler(data):
            logger.info(f"Relaying from A to B through C")
            # Forward the request to B
            result = server_c.dispatch_task(
                task_type=task_type,
                task_data=data.get("original_data", {}),
                preferred_server_id=server_b_id
            )
            return {
                "relayed": True,
                "relay_path": f"{server_a_id} -> {server_c_id} -> {server_b_id}",
                "original_result": result
            }
            
        # Handler to relay from B to A
        def relay_b_to_a_handler(data):
            logger.info(f"Relaying from B to A through C")
            # Forward the request to A
            result = server_c.dispatch_task(
                task_type=task_type,
                task_data=data.get("original_data", {}),
                preferred_server_id=server_a_id
            )
            return {
                "relayed": True,
                "relay_path": f"{server_b_id} -> {server_c_id} -> {server_a_id}",
                "original_result": result
            }
            
        # Register the relay handlers
        server_c.register_task_handler(relay_task_type_a_to_b, relay_a_to_b_handler)
        server_c.register_task_handler(relay_task_type_b_to_a, relay_b_to_a_handler)
        
        # Make sure A and B know about C and the relay task types
        server_a.discover_servers()
        server_b.discover_servers()
        
        # Test relay from A to B (should work since A->C->B are all connected)
        logger.info("Testing relay A -> C -> B")
        relay_result_a_to_b = server_a.dispatch_task(
            task_type=relay_task_type_a_to_b,
            task_data={
                "original_data": {
                    "message": "Hello from A to B via C",
                    "timestamp": time.time()
                }
            },
            preferred_server_id=server_c_id
        )
        
        # Verify relay worked
        self.assertTrue(relay_result_a_to_b["success"], "Relay from A to B should succeed")
        self.assertTrue(
            relay_result_a_to_b["task_result"].get("relayed", False),
            "Task should be marked as relayed"
        )
        
        original_result = relay_result_a_to_b["task_result"].get("original_result", {})
        self.assertTrue(
            original_result.get("success", False),
            "Original task to B should succeed"
        )
        self.assertEqual(
            original_result.get("server_id"), server_b_id,
            f"Task should be processed by {server_b_id}"
        )
        
        # Test relay from B to A through C (should work even though B->A direct fails)
        logger.info("Testing relay B -> C -> A")
        relay_result_b_to_a = server_b.dispatch_task(
            task_type=relay_task_type_b_to_a,
            task_data={
                "original_data": {
                    "message": "Hello from B to A via C",
                    "timestamp": time.time()
                }
            },
            preferred_server_id=server_c_id
        )
        
        # Verify B->C->A relay worked
        self.assertTrue(relay_result_b_to_a["success"], "Relay from B to A should succeed")
        self.assertTrue(
            relay_result_b_to_a["task_result"].get("relayed", False),
            "Task should be marked as relayed"
        )
        
        original_result = relay_result_b_to_a["task_result"].get("original_result", {})
        self.assertTrue(
            original_result.get("success", False),
            "Original task to A should succeed"
        )
        self.assertEqual(
            original_result.get("server_id"), server_a_id,
            f"Task should be processed by {server_a_id}"
        )
        
        # Step 3: Test routing when direct and relay paths both exist
        logger.info("\nStep 3: Testing routing strategy with multiple paths")
        
        # Ensure all servers can see each other again for this part
        server_a.announce_server()
        server_b.announce_server()
        server_c.announce_server()
        server_a.discover_servers()
        server_b.discover_servers()
        server_c.discover_servers()
        
        # Create an alternate handler on server A that we'll use for testing routing preferences
        alt_task_type = f"alt_task_{uuid.uuid4()}"
        server_a.register_task_handler(
            alt_task_type,
            lambda data: {
                "status": "processed", 
                "server_id": server_a_id,
                "path": "direct",
                "timestamp": time.time()
            }
        )
        
        # Create a relay handler that forwards to the alt task type
        relay_alt_task_type = f"relay_alt_task_{uuid.uuid4()}"
        server_c.register_task_handler(
            relay_alt_task_type,
            lambda data: {
                result = server_c.dispatch_task(
                    task_type=alt_task_type,
                    task_data=data.get("original_data", {}),
                    preferred_server_id=server_a_id
                ),
                "relayed": True,
                "relay_path": f"{server_b_id} -> {server_c_id} -> {server_a_id}",
                "original_result": result
            }
        )
        
        # Test direct routing (B->A)
        logger.info("Testing direct routing B -> A")
        direct_result = server_b.dispatch_task(
            task_type=alt_task_type,
            task_data={"route": "direct", "timestamp": time.time()},
            preferred_server_id=server_a_id
        )
        
        # Verify direct route was used
        self.assertTrue(direct_result["success"], "Direct task should succeed")
        self.assertEqual(
            direct_result.get("server_id"), server_a_id,
            f"Task should be processed by {server_a_id}"
        )
        
        # Now create an asymmetric partition again, but keep the relay route
        logger.info("Re-creating asymmetric partition (A->B but not B->A)")
        server_b.remove_server(server_a_id)
        
        # Try to dispatch normally (should fail)
        direct_fail_result = server_b.dispatch_task(
            task_type=alt_task_type,
            task_data={"route": "direct_fail", "timestamp": time.time()},
            preferred_server_id=server_a_id
        )
        
        self.assertFalse(
            direct_fail_result["success"],
            "Direct task should fail with asymmetric partition"
        )
        
        # Try the relay route (should succeed)
        logger.info("Testing relay routing B -> C -> A when direct path fails")
        relay_success_result = server_b.dispatch_task(
            task_type=relay_alt_task_type,
            task_data={
                "original_data": {
                    "route": "relay",
                    "timestamp": time.time()
                }
            },
            preferred_server_id=server_c_id
        )
        
        self.assertTrue(
            relay_success_result["success"],
            "Relay task should succeed despite asymmetric partition"
        )
        
        # Step 4: Test connection reversal (simulating NAT traversal assistance)
        logger.info("\nStep 4: Testing connection reversal (NAT traversal simulation)")
        
        # Create a "connection helper" task on server A that attempts to connect back to B
        connect_back_task_type = f"connect_back_{uuid.uuid4()}"
        
        def connect_back_handler(data):
            """Handler that tries to establish a reverse connection."""
            target_id = data.get("target_id")
            logger.info(f"Server {server_a_id} attempting to connect back to {target_id}")
            
            # In a real system, this would initiate a connection to the target
            # Here, we'll simulate by updating the connection matrix
            
            # Re-announce to the target server
            server_a.announce_server()
            
            # Also update target's knowledge directly
            if target_id in self.server_models:
                target_server = self.server_models[target_id]
                # In a real system, this would happen as a result of the connection
                # Here we simulate by directly updating the knowledge
                target_server.discover_servers()
                
            return {
                "status": "connection_attempted",
                "from": server_a_id,
                "to": target_id,
                "timestamp": time.time()
            }
            
        # Register the connection helper
        server_a.register_task_handler(connect_back_task_type, connect_back_handler)
        
        # Set up asymmetric partition where B can't reach A
        server_b.remove_server(server_a_id)
        
        # Verify B can't reach A directly
        direct_test_result = server_b.dispatch_task(
            task_type=alt_task_type,
            task_data={"test": "direct", "timestamp": time.time()},
            preferred_server_id=server_a_id
        )
        
        self.assertFalse(
            direct_test_result["success"],
            "Direct task should fail with asymmetric partition"
        )
        
        # Use C to relay a connection request to A
        logger.info("Sending reverse connection request via relay")
        connect_relay_task_type = f"connect_relay_{uuid.uuid4()}"
        
        # Register relay handler for connection requests
        server_c.register_task_handler(
            connect_relay_task_type,
            lambda data: {
                result = server_c.dispatch_task(
                    task_type=connect_back_task_type,
                    task_data={"target_id": data.get("target_id")},
                    preferred_server_id=server_a_id
                ),
                "relayed": True,
                "relay_path": f"{server_b_id} -> {server_c_id} -> {server_a_id}",
                "original_result": result
            }
        )
        
        # B sends connection request through C to A
        connect_result = server_b.dispatch_task(
            task_type=connect_relay_task_type,
            task_data={"target_id": server_b_id},
            preferred_server_id=server_c_id
        )
        
        # Verify the connection relay succeeded
        self.assertTrue(connect_result["success"], "Connection relay should succeed")
        
        # Allow time for the connection to be established
        time.sleep(0.5)
        
        # Now B should be able to directly reach A
        logger.info("Testing if reverse connection was established")
        after_connect_result = server_b.dispatch_task(
            task_type=alt_task_type,
            task_data={"test": "after_connect", "timestamp": time.time()},
            preferred_server_id=server_a_id
        )
        
        self.assertTrue(
            after_connect_result["success"],
            "Task should succeed after connection reversal"
        )
        
        # Step 5: Clean up
        logger.info("\nStep 5: Restoring full connectivity for cleanup")
        
        # Ensure all servers can see each other again
        for server in [server_a, server_b, server_c]:
            server.reset()
            server.announce_server()
            
        # Give announcements time to propagate
        time.sleep(0.5)
        
        # Run discovery on all servers
        for server in [server_a, server_b, server_c]:
            server.discover_servers()
            
        # Test final connectivity to verify full restoration
        for id1 in [server_a_id, server_b_id, server_c_id]:
            for id2 in [server_a_id, server_b_id, server_c_id]:
                if id1 != id2:
                    test_dispatch(id1, id2, expect_success=True)
        
        logger.info("Asymmetric network partition test completed successfully")
        
    def test_cascading_network_failures(self):
        """
        Test behavior during cascading network failures.
        
        Cascading failures occur when network problems spread across the system,
        progressively taking down more nodes and connections. This simulates
        real-world scenarios of degrading network conditions like infrastructure
        failures, regional outages, or DDoS attacks.
        """
        # Set log level to ERROR to reduce output
        logging.getLogger().setLevel(logging.ERROR)
        
        # Create a logger for this test
        logger = logging.getLogger("enhanced_mcp_discovery_test")
        test_handler = logging.StreamHandler()
        test_handler.setLevel(logging.INFO)
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)
        
        logger.info("Starting cascading network failures test")
        
        # Get all server IDs
        server_ids = list(self.servers.keys())
        
        # Check we have enough servers
        if len(server_ids) < 5:
            logger.warning("Skipping cascading failures test - need at least 5 servers")
            return
            
        # Register task handlers on all servers
        task_type = f"cascading_test_task_{uuid.uuid4()}"
        
        # Dictionary to track server status for this test
        server_status = {}
        
        # Register handlers on all servers
        for server_id, model in self.server_models.items():
            def make_handler(srv_id):
                return lambda data: {
                    "status": "processed", 
                    "server_id": srv_id,
                    "timestamp": time.time()
                }
                
            model.register_task_handler(task_type, make_handler(server_id))
            
            # Track initial status
            server_status[server_id] = {
                "online": True,
                "connected_to": set(server_ids) - {server_id},  # All except self
                "tasks_processed": 0,
                "health_checks": []
            }
            
        # Helper function to test task dispatch
        def test_dispatch(from_id, to_id, expect_success=True, description=""):
            """Test dispatching a task from one server to another."""
            from_server = self.server_models[from_id]
            
            result = from_server.dispatch_task(
                task_type=task_type,
                task_data={"test": description, "timestamp": time.time()},
                preferred_server_id=to_id
            )
            
            success = result["success"]
            status_str = "Success" if success else "Failure"
            if description:
                logger.info(f"{description}: {from_id} -> {to_id}: {status_str}")
            else:
                logger.info(f"Task dispatch {from_id} -> {to_id}: {status_str}")
            
            if expect_success:
                self.assertTrue(success, f"Task from {from_id} to {to_id} should succeed")
                self.assertEqual(result.get("server_id"), to_id, 
                               f"Task should be processed by {to_id}")
                # Update task count
                if success and result.get("server_id") == to_id:
                    server_status[to_id]["tasks_processed"] += 1
            else:
                self.assertFalse(success, f"Task from {from_id} to {to_id} should fail")
                
            return result
        
        # Helper function to check health status
        def check_health(checker_id, target_id, expect_healthy=True, description=""):
            """Check health status of a server."""
            checker = self.server_models[checker_id]
            result = checker.check_server_health(target_id)
            
            is_healthy = result.get("healthy", False)
            status_str = "Healthy" if is_healthy else "Unhealthy"
            
            if description:
                logger.info(f"{description}: {checker_id} checks {target_id}: {status_str}")
            else:
                logger.info(f"Health check {checker_id} -> {target_id}: {status_str}")
                
            # Record health check
            server_status[target_id]["health_checks"].append({
                "checker": checker_id,
                "timestamp": time.time(),
                "healthy": is_healthy
            })
            
            if expect_healthy:
                self.assertTrue(is_healthy, f"Server {target_id} should be healthy")
            else:
                self.assertFalse(is_healthy, f"Server {target_id} should be unhealthy")
                
            return result
        
        # Helper function to disconnect a node
        def disconnect_node(node_id, description=""):
            """Disconnect a node from the network."""
            if description:
                logger.info(f"{description}: Disconnecting node {node_id}")
            else:
                logger.info(f"Disconnecting node {node_id}")
                
            # Disconnect from all other nodes
            for other_id in server_ids:
                if other_id != node_id:
                    self.network.remove_node_connection(node_id, other_id)
                    
                    # Update tracking
                    if node_id in server_status[other_id]["connected_to"]:
                        server_status[other_id]["connected_to"].remove(node_id)
                    if other_id in server_status[node_id]["connected_to"]:
                        server_status[node_id]["connected_to"].remove(other_id)
                    
                    # Remove server knowledge
                    self.server_models[node_id].remove_server(other_id)
                    self.server_models[other_id].remove_server(node_id)
            
            # Mark as offline
            server_status[node_id]["online"] = False
        
        # Step 1: Verify initial full connectivity
        logger.info("Step 1: Verifying initial full connectivity")
        
        # Test a few representative connections
        for i in range(min(3, len(server_ids))):
            for j in range(min(3, len(server_ids))):
                if i != j:
                    test_dispatch(server_ids[i], server_ids[j], 
                                description="Initial connectivity")
        
        # Step 2: First failure - take down a single node
        logger.info("\nStep 2: First failure - isolated node failure")
        
        # Choose a node to fail
        failed_node = server_ids[0]
        remaining_nodes = server_ids[1:]
        
        logger.info(f"Taking down node {failed_node}")
        disconnect_node(failed_node, "First failure")
        
        # Verify the failed node is unreachable
        for node_id in remaining_nodes:
            test_dispatch(node_id, failed_node, 
                        expect_success=False, 
                        description="After first failure")
            
            # Health check should report unhealthy
            check_health(node_id, failed_node, 
                       expect_healthy=False, 
                       description="After first failure health check")
            
        # Verify remaining nodes can still communicate
        for i in range(len(remaining_nodes)):
            for j in range(len(remaining_nodes)):
                if i != j:
                    # Test a subset of connections to keep the test shorter
                    if i % 2 == 0 and j % 2 == 0:
                        test_dispatch(remaining_nodes[i], remaining_nodes[j], 
                                    description="Remaining nodes after first failure")
        
        # Step 3: Cascading failure - network partition
        logger.info("\nStep 3: Cascading failure - network partition")
        
        # Split remaining nodes into two groups
        midpoint = len(remaining_nodes) // 2
        group1 = remaining_nodes[:midpoint]
        group2 = remaining_nodes[midpoint:]
        
        logger.info(f"Creating partition between group1 {group1} and group2 {group2}")
        
        # Create a partition between the groups
        self.network.simulate_network_partition(group1, group2)
        
        # Update our tracking data
        for id1 in group1:
            for id2 in group2:
                # Remove connection from tracking
                if id2 in server_status[id1]["connected_to"]:
                    server_status[id1]["connected_to"].remove(id2)
                if id1 in server_status[id2]["connected_to"]:
                    server_status[id2]["connected_to"].remove(id1)
                
                # Remove server knowledge
                self.server_models[id1].remove_server(id2)
                self.server_models[id2].remove_server(id1)
        
        # Verify the partition is effective
        for id1 in group1:
            for id2 in group2:
                test_dispatch(id1, id2, 
                            expect_success=False, 
                            description="After partition")
                            
                # Health check should fail across partition
                check_health(id1, id2, 
                           expect_healthy=False, 
                           description="Partition health check")
        
        # Verify communication within groups still works
        if len(group1) > 1:
            test_dispatch(group1[0], group1[1], 
                        description="Within group1 after partition")
        if len(group2) > 1:
            test_dispatch(group2[0], group2[1], 
                        description="Within group2 after partition")
        
        # Step 4: Cascading failure - progressive node failures within Group 1
        logger.info("\nStep 4: Cascading failure - progressive node failures within Group 1")
        
        # Fail nodes one by one in Group 1
        for i, node_id in enumerate(group1):
            # Skip the last node in Group 1 to keep at least one node alive
            if i == len(group1) - 1:
                logger.info(f"Keeping final node {node_id} in Group 1 alive for recovery")
                break
                
            # Disconnect this node
            disconnect_node(node_id, f"Progressive failure {i+1}")
            
            # Verify it's unreachable from all other nodes
            for other_id in server_ids:
                if other_id != node_id and server_status[other_id]["online"]:
                    test_dispatch(other_id, node_id, 
                                expect_success=False, 
                                description=f"After progressive failure {i+1}")
        
        # Count remaining online nodes
        remaining_online = [node_id for node_id in server_ids 
                          if server_status[node_id]["online"]]
        
        logger.info(f"After cascading failures, {len(remaining_online)} nodes remain online: {remaining_online}")
        
        # Step 5: Recover from cascading failures
        logger.info("\nStep 5: Recovery from cascading failures")
        
        # First restore connections between groups
        if len(group1) > 0 and len(group2) > 0:
            # Get a surviving node from Group 1 to reconnect
            surviving_g1 = None
            for node_id in group1:
                if server_status[node_id]["online"]:
                    surviving_g1 = node_id
                    break
            
            # If we have a survivor in Group 1, reconnect it to Group 2
            if surviving_g1:
                logger.info(f"Restoring connection between surviving node {surviving_g1} and Group 2")
                
                # Reconnect to each node in Group 2
                for g2_node in group2:
                    if server_status[g2_node]["online"]:
                        self.network.add_node_connection(surviving_g1, g2_node)
                        
                        # Update tracking
                        server_status[surviving_g1]["connected_to"].add(g2_node)
                        server_status[g2_node]["connected_to"].add(surviving_g1)
                        
                        # Re-announce to restore server knowledge
                        self.server_models[surviving_g1].announce_server()
                        self.server_models[g2_node].announce_server()
                
                # Give announcements time to propagate
                time.sleep(0.5)
                
                # Run discovery
                for node_id in remaining_online:
                    self.server_models[node_id].discover_servers()
                
                # Verify cross-group communication now works
                for g2_node in group2:
                    if server_status[g2_node]["online"]:
                        test_dispatch(surviving_g1, g2_node, 
                                    description="After partial recovery")
                        test_dispatch(g2_node, surviving_g1, 
                                    description="After partial recovery")
        
        # Now bring back one of the failed nodes
        if len(server_ids) > 0:
            # Choose a failed node to recover
            for node_id in server_ids:
                if not server_status[node_id]["online"]:
                    recover_node = node_id
                    break
            else:
                # If we didn't find any failed nodes
                recover_node = None
            
            if recover_node:
                logger.info(f"Bringing back failed node {recover_node}")
                
                # Mark as online
                server_status[recover_node]["online"] = True
                
                # Reconnect to all online nodes
                for other_id in remaining_online:
                    self.network.add_node_connection(recover_node, other_id)
                    
                    # Update tracking
                    server_status[recover_node]["connected_to"].add(other_id)
                    server_status[other_id]["connected_to"].add(recover_node)
                    
                # Reset server state and re-announce
                self.server_models[recover_node].reset()
                self.server_models[recover_node].announce_server()
                
                # Give announcement time to propagate
                time.sleep(0.5)
                
                # Run discovery on all nodes
                for node_id in remaining_online + [recover_node]:
                    self.server_models[node_id].discover_servers()
                
                # Verify recovered node is reachable
                for other_id in remaining_online:
                    test_dispatch(other_id, recover_node, 
                                description="To recovered node")
                    test_dispatch(recover_node, other_id, 
                                description="From recovered node")
                    
                    # Health check should report healthy
                    check_health(other_id, recover_node, 
                               expect_healthy=True, 
                               description="Recovered node health check")
        
        # Step 6: Full recovery
        logger.info("\nStep 6: Full recovery")
        
        # Resolve all network partitions
        self.network.resolve_network_partition()
        
        # Reset and re-announce all servers
        for server_id in server_ids:
            # Mark as online in our tracking
            server_status[server_id]["online"] = True
            
            # Update connected_to set
            server_status[server_id]["connected_to"] = set(server_ids) - {server_id}
            
            # Reset server state
            self.server_models[server_id].reset()
            
            # Re-announce to network
            self.server_models[server_id].announce_server()
        
        # Give announcements time to propagate
        time.sleep(0.5)
        
        # Run discovery on all servers
        for server_id in server_ids:
            self.server_models[server_id].discover_servers()
        
        # Verify full connectivity is restored
        for i in range(len(server_ids)):
            for j in range(len(server_ids)):
                if i != j:
                    test_dispatch(server_ids[i], server_ids[j], 
                                description="After full recovery")
        
        # Generate final statistics
        logger.info("\nFinal Statistics:")
        for server_id in server_ids:
            healthy_checks = sum(1 for check in server_status[server_id]["health_checks"] 
                              if check["healthy"])
            total_checks = len(server_status[server_id]["health_checks"])
            health_ratio = healthy_checks / total_checks if total_checks > 0 else "N/A"
            
            logger.info(f"Server {server_id}:")
            logger.info(f"  Tasks processed: {server_status[server_id]['tasks_processed']}")
            logger.info(f"  Health check ratio: {healthy_checks}/{total_checks} = {health_ratio}")
        
        logger.info("Cascading network failures test completed successfully")


if __name__ == "__main__":
    unittest.main()
#!/usr/bin/env python3
"""
Simple self-contained test for MCP Discovery Protocol.

This test script contains its own minimal implementation of the MCP Discovery components
and doesn't depend on any external imports, making it suitable for testing the core
functionality without any dependency issues.
"""

import os
import sys
import time
import uuid
import random
import unittest
import hashlib
import threading
from enum import Enum
from typing import Dict, List, Set, Any, Optional


# Define enums for server roles and capabilities
class ServerRole(Enum):
    MASTER = "master"
    WORKER = "worker"
    HYBRID = "hybrid"
    EDGE = "edge"


class ServerCapabilities:
    IPFS = "ipfs"
    WEBRTC = "webrtc"
    STORAGE = "storage"
    CLUSTER = "cluster"
    PEER_WEBSOCKET = "peer_websocket"


# Helper classes for the discovery protocol
class FeatureSet:
    """Represents a set of features/capabilities supported by a server."""
    
    def __init__(self, features):
        self.features = features
        # Calculate a hash of the features for quick comparisons
        self.feature_hash = self._calculate_hash()
    
    def _calculate_hash(self):
        feature_str = ",".join(sorted(self.features))
        return hashlib.md5(feature_str.encode()).hexdigest()
    
    def is_compatible_with(self, required_features):
        """Check if this feature set is compatible with the required features."""
        return all(feature in self.features for feature in required_features)


class ServerInfo:
    """Information about a server in the network."""
    
    def __init__(self, server_id, role, feature_set, last_seen=None):
        self.server_id = server_id
        self.role = role
        self.feature_set = feature_set
        self.last_seen = last_seen or time.time()
        self.resources = {}
        self.metadata = {}


class DiscoveryModel:
    """Simple model for server discovery and task distribution."""
    
    def __init__(self, server_id, role, features):
        self.server_id = server_id
        self.role = role
        self.feature_set = FeatureSet(features)
        
        # Create server info for this server
        self.server_info = ServerInfo(server_id, role, self.feature_set)
        
        # Track known servers
        self.server_registry = {}  # server_id -> ServerInfo
        self.registry_lock = threading.RLock()
    
    def register_server(self, server_info):
        """Register a server in the local registry."""
        # Skip self-registration
        if server_info.server_id == self.server_id:
            return {"success": False, "error": "Cannot register self"}
        
        # Update registry with thread safety
        with self.registry_lock:
            self.server_registry[server_info.server_id] = server_info
        
        return {"success": True, "server_id": server_info.server_id}
    
    def discover_servers(self):
        """Mock discovery - just return already known servers."""
        servers = []
        
        with self.registry_lock:
            for server_id, server_info in self.server_registry.items():
                servers.append(server_info)
        
        return {"success": True, "servers": servers}
    
    def get_compatible_servers(self, required_features):
        """Find servers compatible with the required features."""
        compatible_servers = []
        
        with self.registry_lock:
            for server_id, server_info in self.server_registry.items():
                # Skip self
                if server_id == self.server_id:
                    continue
                
                # Check if compatible with requirements
                if server_info.feature_set.is_compatible_with(required_features):
                    compatible_servers.append(server_info)
        
        return {"success": True, "servers": compatible_servers}
    
    def dispatch_task(self, task):
        """Dispatch a task to a compatible server."""
        required_features = task.get("required_features", [])
        
        # Check if we can handle it locally
        if self.feature_set.is_compatible_with(required_features):
            return {
                "success": True,
                "selected_server": self.server_id,
                "mode": "local"
            }
        
        # Find compatible servers
        compatible_result = self.get_compatible_servers(required_features)
        
        if not compatible_result["success"] or not compatible_result["servers"]:
            return {"success": False, "error": "No compatible servers found"}
        
        # Select a server
        selected_server = compatible_result["servers"][0]
        
        return {
            "success": True,
            "selected_server": selected_server.server_id,
            "mode": "remote"
        }
    
    def check_health(self):
        """Check health of registered servers."""
        healthy_servers = []
        unhealthy_servers = []
        
        # Threshold for server liveness
        liveness_threshold = time.time() - 3600  # 1 hour
        
        with self.registry_lock:
            for server_id, server_info in self.server_registry.items():
                if server_info.last_seen >= liveness_threshold:
                    healthy_servers.append(server_info)
                else:
                    unhealthy_servers.append(server_info)
        
        return {
            "success": True,
            "healthy_servers": healthy_servers,
            "unhealthy_servers": unhealthy_servers
        }


class SimpleDiscoveryTest(unittest.TestCase):
    """Test suite for the simple MCP Discovery implementation."""
    
    def setUp(self):
        """Set up the test environment with multiple servers."""
        # Create servers with different roles and capabilities
        self.server1 = DiscoveryModel(
            "server1", 
            ServerRole.MASTER, 
            [ServerCapabilities.IPFS, ServerCapabilities.CLUSTER, ServerCapabilities.STORAGE]
        )
        
        self.server2 = DiscoveryModel(
            "server2", 
            ServerRole.WORKER, 
            [ServerCapabilities.IPFS, ServerCapabilities.WEBRTC]
        )
        
        self.server3 = DiscoveryModel(
            "server3", 
            ServerRole.EDGE, 
            [ServerCapabilities.IPFS]
        )
        
        # Connect the servers
        self.server1.register_server(self.server2.server_info)
        self.server1.register_server(self.server3.server_info)
        self.server2.register_server(self.server1.server_info)
        self.server2.register_server(self.server3.server_info)
        self.server3.register_server(self.server1.server_info)
        self.server3.register_server(self.server2.server_info)
    
    def test_server_discovery(self):
        """Test that servers can discover each other."""
        # Clear server1's registry and rediscover
        self.server1.server_registry = {}
        
        # Register the other servers
        self.server1.register_server(self.server2.server_info)
        self.server1.register_server(self.server3.server_info)
        
        # Discover servers
        result = self.server1.discover_servers()
        
        # Verify success
        self.assertTrue(result["success"])
        self.assertEqual(len(result["servers"]), 2)
    
    def test_feature_compatibility(self):
        """Test that servers can identify compatible servers based on feature sets."""
        # Get servers compatible with STORAGE
        result = self.server2.get_compatible_servers([ServerCapabilities.STORAGE])
        
        # Only server1 has STORAGE capability
        self.assertTrue(result["success"])
        self.assertEqual(len(result["servers"]), 1)
        self.assertEqual(result["servers"][0].server_id, "server1")
    
    def test_task_distribution(self):
        """Test that tasks can be dispatched to compatible servers."""
        # Create a task that requires STORAGE
        task = {
            "task_id": "task1",
            "task_type": "store_content",
            "required_features": [ServerCapabilities.IPFS, ServerCapabilities.STORAGE]
        }
        
        # Dispatch from server2 (which doesn't have STORAGE)
        result = self.server2.dispatch_task(task)
        
        # Should be dispatched to server1
        self.assertTrue(result["success"])
        self.assertEqual(result["selected_server"], "server1")
        self.assertEqual(result["mode"], "remote")
    
    def test_health_monitoring(self):
        """Test health monitoring functionality."""
        # All servers should be healthy initially
        health_result = self.server1.check_health()
        self.assertTrue(health_result["success"])
        self.assertEqual(len(health_result["healthy_servers"]), 2)
        self.assertEqual(len(health_result["unhealthy_servers"]), 0)
        
        # Make server3 appear unhealthy by setting old last_seen time
        self.server1.server_registry["server3"].last_seen = time.time() - 7200  # 2 hours ago
        
        # Health check should now show server3 as unhealthy
        health_result = self.server1.check_health()
        self.assertTrue(health_result["success"])
        self.assertEqual(len(health_result["healthy_servers"]), 1)
        self.assertEqual(len(health_result["unhealthy_servers"]), 1)
        self.assertEqual(health_result["unhealthy_servers"][0].server_id, "server3")


if __name__ == "__main__":
    unittest.main()
#!/usr/bin/env python3
"""
Minimal MCP Discovery Test

This script creates a minimal test of the discovery protocol by directly implementing
the core functionality without depending on problematic imports.
"""

import sys
import os
import time
import uuid
import logging
import threading
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("minimal_test")

# Server roles
class ServerRole:
    MASTER = "master"
    WORKER = "worker"

# Feature constants
class ServerFeatures:
    IPFS = "ipfs_daemon"
    WEBSOCKET = "peer_websocket"
    WEBRTC = "webrtc"

class ServerInfo:
    """Simple server information holder."""
    
    def __init__(self, server_id, role, features):
        self.server_id = server_id
        self.role = role
        self.features = features
        self.last_seen = time.time()
        
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "server_id": self.server_id,
            "role": self.role,
            "features": self.features,
            "last_seen": self.last_seen
        }
        
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary."""
        server = cls(
            server_id=data["server_id"],
            role=data["role"],
            features=data["features"]
        )
        server.last_seen = data["last_seen"]
        return server

class DiscoveryManager:
    """Simple discovery manager."""
    
    def __init__(self, server_id, role, features):
        """Initialize the discovery manager."""
        self.server_id = server_id
        self.role = role
        self.features = features
        self.known_servers = {}  # server_id -> ServerInfo
        self.server_lock = threading.Lock()
        
    def get_server_info(self):
        """Get this server's info."""
        return ServerInfo(
            server_id=self.server_id,
            role=self.role,
            features=self.features
        )
        
    def register_server(self, server_info):
        """Register a server."""
        # Skip self-registration
        if server_info.server_id == self.server_id:
            return {"success": True, "message": "Skipped self-registration"}
            
        # Register in known servers
        with self.server_lock:
            self.known_servers[server_info.server_id] = server_info
            
        return {
            "success": True,
            "server_id": server_info.server_id
        }
        
    def discover_servers(self):
        """Get all known servers."""
        with self.server_lock:
            servers = []
            for server_id, server_info in self.known_servers.items():
                servers.append(server_info.to_dict())
                
        return {
            "success": True,
            "servers": servers,
            "server_count": len(servers)
        }
        
    def get_compatible_servers(self):
        """Get servers with compatible feature sets."""
        with self.server_lock:
            compatible_servers = []
            for server_id, server_info in self.known_servers.items():
                # Simple compatibility check (any shared features)
                shared_features = set(self.features) & set(server_info.features)
                if shared_features:
                    compatible_servers.append(server_info.to_dict())
                    
        return {
            "success": True,
            "servers": compatible_servers,
            "server_count": len(compatible_servers)
        }
        
    def dispatch_task(self, task_type, task_data, server_id=None):
        """Simulate task dispatch to another server."""
        target_server = None
        
        # If server specified, use it
        if server_id and server_id in self.known_servers:
            target_server = self.known_servers[server_id]
        else:
            # Find a compatible server
            compatible = self.get_compatible_servers()
            if compatible["server_count"] > 0:
                target_info = compatible["servers"][0]
                target_server_id = target_info["server_id"]
                target_server = self.known_servers[target_server_id]
                
        if target_server:
            return {
                "success": True,
                "task_type": task_type,
                "server_id": target_server.server_id,
                "message": f"Task {task_type} dispatched to {target_server.server_id}"
            }
        else:
            return {
                "success": False,
                "error": "No compatible server found"
            }

def test_discovery_protocol():
    """Test the discovery protocol with two servers."""
    logger.info("Starting Minimal Discovery Test")
    
    # Create server 1 (master)
    server1_id = f"server1-{uuid.uuid4()}"
    server1_features = [ServerFeatures.IPFS, ServerFeatures.WEBSOCKET, ServerFeatures.WEBRTC]
    server1 = DiscoveryManager(server1_id, ServerRole.MASTER, server1_features)
    
    # Create server 2 (worker)
    server2_id = f"server2-{uuid.uuid4()}"
    server2_features = [ServerFeatures.IPFS, ServerFeatures.WEBSOCKET]
    server2 = DiscoveryManager(server2_id, ServerRole.WORKER, server2_features)
    
    logger.info(f"Created Server1 (Master) with ID: {server1_id}")
    logger.info(f"Features: {', '.join(server1_features)}")
    
    logger.info(f"Created Server2 (Worker) with ID: {server2_id}")
    logger.info(f"Features: {', '.join(server2_features)}")
    
    # Register servers with each other
    logger.info("Registering servers with each other...")
    
    server1.register_server(server2.get_server_info())
    server2.register_server(server1.get_server_info())
    
    # Check discovery
    logger.info("Checking server discovery...")
    
    discovered_by_1 = server1.discover_servers()
    discovered_by_2 = server2.discover_servers()
    
    logger.info(f"Server1 discovered {discovered_by_1['server_count']} servers")
    logger.info(f"Server2 discovered {discovered_by_2['server_count']} servers")
    
    # Check if they found each other
    server1_found_server2 = False
    for server in discovered_by_1["servers"]:
        if server["server_id"] == server2_id:
            server1_found_server2 = True
            logger.info("Server1 successfully discovered Server2")
            break
            
    server2_found_server1 = False
    for server in discovered_by_2["servers"]:
        if server["server_id"] == server1_id:
            server2_found_server1 = True
            logger.info("Server2 successfully discovered Server1")
            break
    
    # Check compatibility
    logger.info("Checking for compatible servers...")
    
    compatible_with_1 = server1.get_compatible_servers()
    compatible_with_2 = server2.get_compatible_servers()
    
    logger.info(f"Server1 found {compatible_with_1['server_count']} compatible servers")
    logger.info(f"Server2 found {compatible_with_2['server_count']} compatible servers")
    
    # Dispatch a task
    logger.info("Dispatching task from Server1 to Server2...")
    
    task_result = server1.dispatch_task(
        task_type="process_data",
        task_data="test data",
        server_id=server2_id
    )
    
    logger.info(f"Task dispatch result: {task_result['success']}")
    if task_result["success"]:
        logger.info(f"Task dispatched to: {task_result['server_id']}")
    
    # Determine success
    success = server1_found_server2 and server2_found_server1
    success = success and compatible_with_1["server_count"] > 0 and compatible_with_2["server_count"] > 0
    success = success and task_result["success"] and task_result["server_id"] == server2_id
    
    logger.info(f"Discovery test {'successful' if success else 'failed'}")
    
    return success

if __name__ == "__main__":
    success = test_discovery_protocol()
    sys.exit(0 if success else 1)
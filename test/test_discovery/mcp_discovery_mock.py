"""
MCP Discovery Mock module for testing.

This module provides mock implementations of the MCP Discovery components
for testing purposes.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class MCPDiscoveryMock:
    """Mock implementation of the MCP Discovery system."""

    def __init__(self):
        """Initialize the mock discovery system."""
        self.servers = {}
        self.server_id = str(uuid.uuid4())
        self.local_server = {
            "id": self.server_id,
            "role": "coordinator",
            "features": ["ipfs", "filecoin", "routing"],
            "api_endpoint": "http://localhost:8000",
            "websocket_endpoint": "ws://localhost:8000/ws",
            "last_seen": time.time(),
            "is_local": True,
            "version": "0.1.0",
            "metadata": {}
        }
        self.servers[self.server_id] = self.local_server
        logger.info(f"Initialized MCPDiscoveryMock with server ID: {self.server_id}")

    def get_server_info(self, server_id):
        """Get information about a server."""
        if server_id not in self.servers:
            return {"success": False, "error": f"Server not found: {server_id}"}

        return {
            "success": True,
            "server_info": self.servers[server_id],
            "is_local": server_id == self.server_id
        }

    def update_server_info(self, **kwargs):
        """Update local server information."""
        for key, value in kwargs.items():
            if key in self.local_server:
                self.local_server[key] = value

        return {"success": True}

    def announce_server(self):
        """Announce this server to the network."""
        # Simulate announcement
        return {
            "success": True,
            "announcement_channels": ["local", "http"],
            "announced_at": time.time()
        }

    def discover_servers(self, methods=None, compatible_only=True, feature_requirements=None):
        """Discover MCP servers in the network."""
        if methods is None:
            methods = ["manual"]

        discovered_servers = list(self.servers.values())

        # Filter by features if needed
        if feature_requirements and compatible_only:
            filtered_servers = []
            for server in discovered_servers:
                if all(feature in server.get("features", []) for feature in feature_requirements):
                    filtered_servers.append(server)
            discovered_servers = filtered_servers

        return {
            "success": True,
            "servers": discovered_servers,
            "server_count": len(discovered_servers),
            "new_servers": 0,
            "discovery_methods": methods
        }

    def get_compatible_servers(self, feature_requirements=None):
        """Get list of servers with compatible feature sets."""
        return self.discover_servers(
            methods=["manual"],
            compatible_only=True,
            feature_requirements=feature_requirements
        )

    def register_server(self, server_info):
        """Manually register a server."""
        if "id" not in server_info:
            server_info["id"] = str(uuid.uuid4())

        server_id = server_info["id"]
        is_new = server_id not in self.servers
        self.servers[server_id] = server_info

        return {
            "success": True,
            "server_id": server_id,
            "is_new": is_new
        }

    def remove_server(self, server_id):
        """Remove a server from known servers."""
        if server_id not in self.servers:
            return {"success": False, "error": f"Server not found: {server_id}"}

        if server_id == self.server_id:
            return {"success": False, "error": "Cannot remove local server"}

        del self.servers[server_id]
        return {"success": True}

    def clean_stale_servers(self, max_age_seconds=3600):
        """Remove servers that haven't been seen for a while."""
        current_time = time.time()
        stale_servers = []

        for server_id, server_info in list(self.servers.items()):
            if server_id == self.server_id:
                continue

            last_seen = server_info.get("last_seen", 0)
            if current_time - last_seen > max_age_seconds:
                stale_servers.append(server_id)
                del self.servers[server_id]

        return {
            "success": True,
            "removed_servers": stale_servers,
            "removed_count": len(stale_servers)
        }

    def check_server_health(self, server_id):
        """Check health status of a server."""
        if server_id not in self.servers:
            return {"success": False, "error": f"Server not found: {server_id}"}

        # For mock purposes, all servers are healthy
        return {
            "success": True,
            "server_id": server_id,
            "healthy": True,
            "health_source": "mock"
        }

    def dispatch_task(self, task_type, task_data, required_features=None, preferred_server_id=None):
        """Dispatch a task to a compatible server."""
        # For mock purposes, all tasks are processed locally
        return {
            "success": True,
            "task_type": task_type,
            "server_id": self.server_id,
            "processed_locally": True,
            "task_result": {"message": "Task processed successfully by mock"}
        }

    def get_stats(self):
        """Get statistics about server discovery."""
        return {
            "success": True,
            "stats": {
                "server_count": len(self.servers),
                "known_roles": list(set(server.get("role") for server in self.servers.values())),
                "discovery_count": 0,
                "announcement_count": 0
            }
        }

    def reset(self):
        """Reset the discovery model, clearing all state."""
        servers_copy = {}
        servers_copy[self.server_id] = self.local_server
        self.servers = servers_copy

        return {"success": True}

# For backwards compatibility
MockNetwork = MCPDiscoveryMock

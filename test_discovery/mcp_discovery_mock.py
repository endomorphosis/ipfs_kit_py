"""
Mock implementation for MCP Discovery testing.

This module provides mock implementations for MCP server discovery components.
"""

import os
import json
import uuid
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class MCPServerInfo:
    """Information about an MCP server discovered on the network."""

    server_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "mcp-server"
    endpoint: str = "http://127.0.0.1:5000"
    api_version: str = "1.0.0"
    roles: List[str] = field(default_factory=lambda: ["primary"])
    capabilities: List[str] = field(default_factory=lambda: ["storage", "routing"])
    status: str = "online"
    last_seen: float = field(default_factory=lambda: import_time_module())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPServerInfo':
        """Create instance from dictionary."""
        return cls(**data)

    def __str__(self) -> str:
        """String representation."""
        return f"MCPServer(id={self.server_id}, name={self.name}, endpoint={self.endpoint})"

def import_time_module():
    """Import time module and return current time."""
    import time
    return time.time()

@dataclass
class MCPDiscoveryService:
    """Mock service for discovering MCP servers on the network."""

    known_servers: Dict[str, MCPServerInfo] = field(default_factory=dict)
    local_server: Optional[MCPServerInfo] = None
    discovery_active: bool = False

    def __post_init__(self):
        """Initialize with default local server."""
        if not self.local_server:
            self.local_server = MCPServerInfo()
        if self.local_server.server_id not in self.known_servers:
            self.known_servers[self.local_server.server_id] = self.local_server

    def start_discovery(self) -> bool:
        """Start server discovery process."""
        self.discovery_active = True
        logger.info("MCP Discovery Service started")
        return True

    def stop_discovery(self) -> bool:
        """Stop server discovery process."""
        self.discovery_active = False
        logger.info("MCP Discovery Service stopped")
        return True

    def get_all_servers(self) -> List[MCPServerInfo]:
        """Get all known servers."""
        return list(self.known_servers.values())

    def get_server_by_id(self, server_id: str) -> Optional[MCPServerInfo]:
        """Get server by ID."""
        return self.known_servers.get(server_id)

    def add_server(self, server: Union[MCPServerInfo, Dict[str, Any]]) -> MCPServerInfo:
        """Add or update a server in the registry."""
        if isinstance(server, dict):
            server = MCPServerInfo.from_dict(server)

        self.known_servers[server.server_id] = server
        logger.info(f"Added server: {server}")
        return server

    def remove_server(self, server_id: str) -> bool:
        """Remove a server from the registry."""
        if server_id in self.known_servers:
            del self.known_servers[server_id]
            logger.info(f"Removed server: {server_id}")
            return True
        return False

    def is_local_server(self, server_id: str) -> bool:
        """Check if server ID matches local server."""
        return self.local_server and self.local_server.server_id == server_id

    def get_servers_with_capability(self, capability: str) -> List[MCPServerInfo]:
        """Get servers that have a specific capability."""
        return [
            server for server in self.known_servers.values()
            if capability in server.capabilities
        ]

    def get_servers_with_role(self, role: str) -> List[MCPServerInfo]:
        """Get servers that have a specific role."""
        return [
            server for server in self.known_servers.values()
            if role in server.roles
        ]

@dataclass
class EnhancedMCPDiscoveryTest:
    """Enhanced MCP discovery for complex testing scenarios."""

    discovery_service: MCPDiscoveryService = field(default_factory=MCPDiscoveryService)
    network_partitions: List[List[str]] = field(default_factory=list)

    def create_network_partition(self, server_ids: List[str]) -> int:
        """Create a network partition with the given server IDs."""
        partition_id = len(self.network_partitions)
        self.network_partitions.append(server_ids)
        return partition_id

    def can_communicate(self, server_id1: str, server_id2: str) -> bool:
        """Check if two servers can communicate based on network partitions."""
        # If no partitions defined, all servers can communicate
        if not self.network_partitions:
            return True

        # Check if servers are in the same partition
        for partition in self.network_partitions:
            if server_id1 in partition and server_id2 in partition:
                return True

        return False

    def simulate_network_failure(self, server_id: str) -> bool:
        """Simulate a network failure for a server."""
        server = self.discovery_service.get_server_by_id(server_id)
        if server:
            server.status = "offline"
            return True
        return False

    def simulate_network_recovery(self, server_id: str) -> bool:
        """Simulate a network recovery for a server."""
        server = self.discovery_service.get_server_by_id(server_id)
        if server:
            server.status = "online"
            return True
        return False

    def create_test_network(self, num_servers: int) -> List[MCPServerInfo]:
        """Create a test network with the specified number of servers."""
        servers = []
        for i in range(num_servers):
            name = f"test-server-{i}"
            endpoint = f"http://127.0.0.1:{5000 + i}"
            server = MCPServerInfo(
                name=name,
                endpoint=endpoint,
                roles=["storage"] if i % 2 == 0 else ["routing"],
                capabilities=["storage", "routing"] if i % 3 == 0 else ["storage"]
            )
            self.discovery_service.add_server(server)
            servers.append(server)
        return servers

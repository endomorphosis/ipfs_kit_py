#!/usr/bin/env python3
"""
MCP Discovery Collaboration Test

This script tests the ability of two MCP servers to discover each other and collaborate
when they share the same feature set.
"""

import os
import sys
import time
import json
import threading
import uuid
import logging
from typing import Dict, Any

# Configure logging for clarity
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("discovery_test")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# First patch the imports to avoid libp2p errors
import builtins
original_import = builtins.__import__

def patched_import(name, *args, **kwargs):
    if name.startswith('libp2p') or name.startswith('ipfs_kit_py.libp2p'):
        # Skip libp2p imports for this test
        if name in sys.modules:
            return sys.modules[name]
        else:
            # Create a fake module
            import types
            fake_module = types.ModuleType(name)
            fake_module.__path__ = []
            sys.modules[name] = fake_module
            return fake_module
    return original_import(name, *args, **kwargs)

# Apply the patch
builtins.__import__ = patched_import

# Now import the MCP server
from ipfs_kit_py.mcp.server import MCPServer

# Check if MCP Discovery is available
try:
    from ipfs_kit_py.mcp.models.mcp_discovery_model import MCPDiscoveryModel
    from ipfs_kit_py.mcp.controllers.mcp_discovery_controller import MCPDiscoveryController
    HAS_MCP_DISCOVERY = True
except ImportError:
    HAS_MCP_DISCOVERY = False
    logger.error("MCP Discovery components not available. Test cannot run.")
    sys.exit(1)

class ServerInstance:
    """Wrapper for MCP server instance with discovery functionality."""
    
    def __init__(self, name: str, role: str = "master", debug_mode: bool = True):
        """Initialize a server instance.
        
        Args:
            name: Name for this server (used in logging)
            role: Server role (master, worker, hybrid, edge)
            debug_mode: Enable debug mode
        """
        self.name = name
        self.role = role
        
        # Generate unique server ID with name
        self.server_id = f"{name}-{uuid.uuid4()}"
        
        logger.info(f"Creating {name} server with ID: {self.server_id}")
        
        # Create server with unique persistence path to avoid conflicts
        temp_dir = f"/tmp/mcp_test_{self.server_id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create server
        self.server = MCPServer(
            debug_mode=debug_mode,
            log_level="INFO",
            isolation_mode=True,
            persistence_path=temp_dir
        )
        
        # Store reference to discovery model and controller if available
        if "mcp_discovery" in self.server.models:
            self.discovery_model = self.server.models["mcp_discovery"]
            
            # Set server role
            self.discovery_model.role = role
            self.discovery_model.server_info.role = role
            
            # Update server info to include name in metadata
            self.discovery_model.update_server_info(metadata={
                "server_name": name,
                "api_endpoint": f"http://localhost/api/{name}"  # Simulated endpoint
            })
            
            logger.info(f"Server {name} initialized with role {role}")
            logger.info(f"Features: {', '.join(self.discovery_model.feature_set.features)}")
        else:
            logger.error(f"Server {name} failed to initialize MCP Discovery model")
    
    def announce(self):
        """Announce this server to the network."""
        if hasattr(self, 'discovery_model'):
            result = self.discovery_model.announce_server()
            logger.info(f"Server {self.name} announced: {result['success']}")
            return result
        return {"success": False, "error": "Discovery model not available"}
    
    def discover(self):
        """Discover other servers."""
        if hasattr(self, 'discovery_model'):
            result = self.discovery_model.discover_servers()
            logger.info(f"Server {self.name} discovered {result.get('server_count', 0)} servers")
            return result
        return {"success": False, "error": "Discovery model not available"}
    
    def get_compatible_servers(self):
        """Get compatible servers."""
        if hasattr(self, 'discovery_model'):
            result = self.discovery_model.get_compatible_servers()
            logger.info(f"Server {self.name} found {result.get('server_count', 0)} compatible servers")
            return result
        return {"success": False, "error": "Discovery model not available"}
    
    def register_other_server(self, other_server):
        """Manually register another server for testing."""
        if hasattr(self, 'discovery_model') and hasattr(other_server, 'discovery_model'):
            # Get other server's info
            other_info = other_server.discovery_model.get_server_info(other_server.discovery_model.server_id)
            
            if other_info.get("success", False):
                # Register the other server
                result = self.discovery_model.register_server(other_info["server_info"])
                logger.info(f"Server {self.name} registered {other_server.name}: {result['success']}")
                return result
            else:
                logger.error(f"Failed to get server info for {other_server.name}")
                return {"success": False, "error": "Failed to get server info"}
        return {"success": False, "error": "Discovery model not available"}
    
    def get_stats(self):
        """Get discovery statistics."""
        if hasattr(self, 'discovery_model'):
            result = self.discovery_model.get_stats()
            return result
        return {"success": False, "error": "Discovery model not available"}
    
    def shutdown(self):
        """Shutdown the server."""
        if hasattr(self, 'server'):
            self.server.shutdown()
            logger.info(f"Server {self.name} shut down")

def test_discovery_collaboration():
    """Test MCP discovery and collaboration functionality."""
    logger.info("Starting MCP Discovery Collaboration Test")
    
    # Create two server instances with different roles
    server1 = ServerInstance("server1", role="master")
    server2 = ServerInstance("server2", role="worker")
    
    try:
        # Manually register servers with each other (simulate discovery)
        logger.info("Registering servers with each other...")
        server1.register_other_server(server2)
        server2.register_other_server(server1)
        
        # Check if servers can discover each other
        logger.info("Checking if servers can discover each other...")
        
        # Get servers discovered by server1
        discovered_by_1 = server1.discover()
        
        # Get servers discovered by server2
        discovered_by_2 = server2.discover()
        
        # Check if server1 found server2
        server1_found_server2 = False
        for server in discovered_by_1.get("servers", []):
            if server.get("server_id") == server2.server_id:
                server1_found_server2 = True
                logger.info(f"Server1 successfully discovered Server2")
                logger.info(f"Server2 info from Server1: {json.dumps(server, indent=2)}")
                break
        
        # Check if server2 found server1
        server2_found_server1 = False
        for server in discovered_by_2.get("servers", []):
            if server.get("server_id") == server1.server_id:
                server2_found_server1 = True
                logger.info(f"Server2 successfully discovered Server1")
                logger.info(f"Server1 info from Server2: {json.dumps(server, indent=2)}")
                break
        
        # Get compatible servers for each
        logger.info("Checking for compatible servers...")
        compatible_with_1 = server1.get_compatible_servers()
        compatible_with_2 = server2.get_compatible_servers()
        
        # Check if they found each other as compatible
        if compatible_with_1.get("server_count", 0) > 0:
            logger.info(f"Server1 found compatible servers: {compatible_with_1.get('server_count', 0)}")
        
        if compatible_with_2.get("server_count", 0) > 0:
            logger.info(f"Server2 found compatible servers: {compatible_with_2.get('server_count', 0)}")
        
        # Get statistics
        logger.info("Getting discovery statistics...")
        stats1 = server1.get_stats()
        stats2 = server2.get_stats()
        
        logger.info(f"Server1 stats: {json.dumps(stats1.get('stats', {}), indent=2)}")
        logger.info(f"Server2 stats: {json.dumps(stats2.get('stats', {}), indent=2)}")
        
        # Check overall success
        success = server1_found_server2 and server2_found_server1
        
        logger.info(f"Discovery test {'successful' if success else 'failed'}")
        return success
        
    finally:
        # Clean up
        logger.info("Shutting down servers...")
        server1.shutdown()
        server2.shutdown()

if __name__ == "__main__":
    if not HAS_MCP_DISCOVERY:
        logger.error("MCP Discovery components not available. Test cannot run.")
        sys.exit(1)
    
    success = test_discovery_collaboration()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Direct MCP Discovery Test

This script directly tests the MCP Discovery model functions for registering
and discovering compatible servers without starting the full MCP server stack.
"""

import sys
import os
import time
import json
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("discovery_test")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary components directly
try:
    from ipfs_kit_py.mcp.models.mcp_discovery_model import (
        MCPDiscoveryModel, MCPServerRole, MCPServerCapabilities,
        MCPFeatureSet, MCPServerInfo
    )
    HAS_MCP_DISCOVERY = True
except ImportError:
    logger.error("MCP Discovery model not available. Test cannot run.")
    HAS_MCP_DISCOVERY = False
    sys.exit(1)

def test_mcp_discovery_direct():
    """Test MCP Discovery model directly."""
    logger.info("Starting Direct MCP Discovery Test")
    
    # Create a discovery model for server 1 (master)
    server1_id = f"server1-{uuid.uuid4()}"
    server1_features = [
        MCPServerCapabilities.IPFS_DAEMON,
        MCPServerCapabilities.PEER_WEBSOCKET,
        MCPServerCapabilities.WEBRTC
    ]
    
    # Create a discovery model for server 2 (worker)
    server2_id = f"server2-{uuid.uuid4()}"
    server2_features = [
        MCPServerCapabilities.IPFS_DAEMON,
        MCPServerCapabilities.PEER_WEBSOCKET,
        MCPServerCapabilities.WEBRTC
    ]
    
    # Create the models
    model1 = MCPDiscoveryModel(
        server_id=server1_id,
        role=MCPServerRole.MASTER,
        features=server1_features
    )
    
    model2 = MCPDiscoveryModel(
        server_id=server2_id,
        role=MCPServerRole.WORKER,
        features=server2_features
    )
    
    logger.info(f"Created Server1 (Master) with ID: {server1_id}")
    logger.info(f"Features: {', '.join(model1.feature_set.features)}")
    
    logger.info(f"Created Server2 (Worker) with ID: {server2_id}")
    logger.info(f"Features: {', '.join(model2.feature_set.features)}")
    
    # Get both server info
    server1_info = model1.get_server_info(model1.server_id)
    server2_info = model2.get_server_info(model2.server_id)
    
    # Register each server with the other
    logger.info("Registering servers with each other...")
    
    model1_register_result = model1.register_server(server2_info["server_info"])
    model2_register_result = model2.register_server(server1_info["server_info"])
    
    logger.info(f"Server1 registered Server2: {model1_register_result['success']}")
    logger.info(f"Server2 registered Server1: {model2_register_result['success']}")
    
    # Check if servers can discover each other
    logger.info("Checking server discovery...")
    
    discovered_by_1 = model1.discover_servers(methods=["manual"])
    discovered_by_2 = model2.discover_servers(methods=["manual"])
    
    logger.info(f"Server1 discovered {discovered_by_1['server_count']} servers")
    logger.info(f"Server2 discovered {discovered_by_2['server_count']} servers")
    
    # Verify that they found each other
    server1_found_server2 = False
    for server in discovered_by_1.get("servers", []):
        if server.get("server_id") == server2_id:
            server1_found_server2 = True
            logger.info("Server1 successfully discovered Server2")
            break
    
    server2_found_server1 = False
    for server in discovered_by_2.get("servers", []):
        if server.get("server_id") == server1_id:
            server2_found_server1 = True
            logger.info("Server2 successfully discovered Server1")
            break
    
    # Check compatibility
    logger.info("Checking for compatible servers...")
    
    compatible_with_1 = model1.get_compatible_servers()
    compatible_with_2 = model2.get_compatible_servers()
    
    logger.info(f"Server1 found {compatible_with_1['server_count']} compatible servers")
    logger.info(f"Server2 found {compatible_with_2['server_count']} compatible servers")
    
    # Check stats
    stats1 = model1.get_stats()
    stats2 = model2.get_stats()
    
    logger.info(f"Server1 discovered {stats1['stats']['servers_discovered']} servers total")
    logger.info(f"Server2 discovered {stats2['stats']['servers_discovered']} servers total")
    
    # Verify task handling capability
    
    # Define a simple task handler for server2
    def test_task_handler(task_data):
        logger.info(f"Server2 handling task: {task_data}")
        return {
            "success": True,
            "result": f"Processed: {task_data}",
            "timestamp": time.time()
        }
    
    # Register the task handler with server2
    model2.register_task_handler("test_task", test_task_handler)
    
    # Dispatch a task from server1 to server2
    logger.info("Dispatching task from Server1 to Server2...")
    
    task_result = model1.dispatch_task(
        task_type="test_task",
        task_data="Hello from Server1",
        preferred_server_id=server2_id
    )
    
    logger.info(f"Task dispatch result: {task_result['success']}")
    if task_result['success']:
        logger.info(f"Task processed by: {task_result['server_id']}")
    
    # Determine overall success
    success = server1_found_server2 and server2_found_server1
    success = success and compatible_with_1['server_count'] > 0 and compatible_with_2['server_count'] > 0
    
    logger.info(f"Discovery test {'successful' if success else 'failed'}")
    logger.info("Note: Task dispatch simulation is included but actual processing would require network communication")
    
    return success

if __name__ == "__main__":
    if not HAS_MCP_DISCOVERY:
        logger.error("MCP Discovery model not available. Test cannot run.")
        sys.exit(1)
    
    success = test_mcp_discovery_direct()
    sys.exit(0 if success else 1)
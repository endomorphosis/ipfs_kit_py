#!/usr/bin/env python3
"""
High Availability Architecture Example for MCP Server

This example demonstrates how to set up and use the High Availability module
to create a fault-tolerant, multi-region deployment of the MCP server.

Key features demonstrated:
1. Multi-region configuration
2. Node health monitoring
3. Automatic failover between regions
4. Load balancing between nodes
5. Manual operations like triggering failover

Usage:
  python high_availability_example.py [--redis-url REDIS_URL]
"""

import os
import sys
import json
import asyncio
import argparse
import logging
import tempfile
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ha-example")

# Import HA components
try:
    from ipfs_kit_py.mcp.enterprise.high_availability import (
        HACluster, LoadBalancer, 
        HAConfig, RegionConfig, NodeConfig,
        NodeRole, NodeStatus, RegionStatus,
        FailoverStrategy, ReplicationMode, ConsistencyLevel
    )
except ImportError:
    logger.error("Failed to import HA modules. Make sure ipfs_kit_py is installed")
    sys.exit(1)

def create_example_config(temp_dir: str) -> str:
    """Create an example HA configuration file."""
    # Generate a unique node ID for this instance
    local_node_id = str(uuid.uuid4())
    
    # Create example configuration
    config = {
        "ha_config": {
            "id": str(uuid.uuid4()),
            "name": "Example HA Cluster",
            "description": "Example configuration for MCP Server HA",
            "active": True,
            "failover_strategy": "automatic",
            "replication_mode": "asynchronous",
            "consistency_level": "eventual",
            "heartbeat_interval_ms": 5000,
            "health_check_interval_ms": 10000,
            "failover_timeout_ms": 30000,
            "quorum_size": 3,
            "replication_factor": 2,
            "dns_failover": False,
            "dns_ttl_seconds": 60,
            "load_balancing_policy": "round-robin",
            "regions": [
                {
                    "id": "us-west",
                    "name": "US West",
                    "location": "US West (Oregon)",
                    "primary": True,
                    "failover_priority": 0,
                    "dns_name": "us-west.example.com"
                },
                {
                    "id": "us-east",
                    "name": "US East",
                    "location": "US East (Virginia)",
                    "primary": False,
                    "failover_priority": 1,
                    "dns_name": "us-east.example.com"
                },
                {
                    "id": "eu-west",
                    "name": "EU West",
                    "location": "EU West (Ireland)",
                    "primary": False,
                    "failover_priority": 2,
                    "dns_name": "eu-west.example.com"
                }
            ]
        },
        "nodes": [
            # Primary region nodes
            {
                "id": local_node_id,  # Local node
                "host": "127.0.0.1",
                "port": 8000,
                "role": "primary",
                "region": "us-west",
                "zone": "us-west-1a",
                "api_endpoint": "/api",
                "admin_endpoint": "/admin",
                "metrics_endpoint": "/metrics",
                "max_connections": 1000,
                "max_memory_gb": 4.0,
                "cpu_cores": 2
            },
            {
                "id": str(uuid.uuid4()),
                "host": "127.0.0.1",
                "port": 8001,
                "role": "secondary",
                "region": "us-west",
                "zone": "us-west-1b",
                "api_endpoint": "/api",
                "admin_endpoint": "/admin",
                "metrics_endpoint": "/metrics"
            },
            {
                "id": str(uuid.uuid4()),
                "host": "127.0.0.1",
                "port": 8002,
                "role": "read_replica",
                "region": "us-west",
                "zone": "us-west-1c",
                "api_endpoint": "/api",
                "metrics_endpoint": "/metrics"
            },
            
            # Secondary region nodes (US East)
            {
                "id": str(uuid.uuid4()),
                "host": "127.0.0.1",
                "port": 8010,
                "role": "primary",
                "region": "us-east",
                "zone": "us-east-1a",
                "api_endpoint": "/api",
                "admin_endpoint": "/admin",
                "metrics_endpoint": "/metrics"
            },
            {
                "id": str(uuid.uuid4()),
                "host": "127.0.0.1",
                "port": 8011,
                "role": "secondary",
                "region": "us-east",
                "zone": "us-east-1b",
                "api_endpoint": "/api",
                "metrics_endpoint": "/metrics"
            },
            
            # Third region nodes (EU West)
            {
                "id": str(uuid.uuid4()),
                "host": "127.0.0.1",
                "port": 8020,
                "role": "primary",
                "region": "eu-west",
                "zone": "eu-west-1a",
                "api_endpoint": "/api",
                "admin_endpoint": "/admin",
                "metrics_endpoint": "/metrics"
            },
            {
                "id": str(uuid.uuid4()),
                "host": "127.0.0.1",
                "port": 8021,
                "role": "secondary",
                "region": "eu-west",
                "zone": "eu-west-1b",
                "api_endpoint": "/api",
                "metrics_endpoint": "/metrics"
            }
        ]
    }
    
    # Write configuration to file
    config_path = os.path.join(temp_dir, "ha_config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"Created example HA configuration at {config_path}")
    logger.info(f"Local node ID: {local_node_id}")
    
    return config_path, local_node_id

async def simulated_api_requests(load_balancer: LoadBalancer, num_requests: int = 10):
    """Simulate API requests to demonstrate load balancing."""
    logger.info(f"Simulating {num_requests} API requests with load balancing...")
    
    for i in range(num_requests):
        # Get next node from load balancer
        node = load_balancer.get_next_node()
        
        if node:
            logger.info(f"Request {i+1}: Routing to node {node.id} in region {node.region} at {node.address}")
            # In a real application, you would make an actual API request to the node
            
            # Simulate processing time
            await asyncio.sleep(0.5)
        else:
            logger.warning(f"Request {i+1}: No suitable node available")
    
    logger.info("Completed simulated API requests")

async def simulate_node_failure(ha_cluster: HACluster, node_id: str):
    """Simulate a node failure to demonstrate automatic failover."""
    logger.info(f"Simulating failure of node {node_id}...")
    
    # Get current node state
    original_state = ha_cluster.get_node_state(node_id)
    if not original_state:
        logger.warning(f"Node {node_id} not found")
        return
    
    logger.info(f"Current state of node {node_id}: {original_state.status}")
    
    # Set node to failing state if it's the local node
    if node_id == ha_cluster.local_node_id:
        ha_cluster.set_local_node_status(NodeStatus.FAILING)
        logger.info(f"Set local node status to {NodeStatus.FAILING}")
    else:
        logger.warning(f"Cannot directly set status of remote node {node_id}")
    
    # Wait for health check to detect failure
    await asyncio.sleep(ha_cluster.ha_config.health_check_interval_ms / 1000 * 2)
    
    # Check new state
    new_state = ha_cluster.get_node_state(node_id)
    if new_state:
        logger.info(f"New state of node {node_id}: {new_state.status}")
    
    # If this was the local node, restore its status
    if node_id == ha_cluster.local_node_id:
        ha_cluster.set_local_node_status(NodeStatus.HEALTHY)
        logger.info(f"Restored local node status to {NodeStatus.HEALTHY}")

async def simulate_region_failure(ha_cluster: HACluster, region_id: str):
    """Simulate a region failure to demonstrate automatic failover."""
    logger.info(f"Simulating failure of region {region_id}...")
    
    # Get current region state
    original_state = ha_cluster.get_region_state(region_id)
    if not original_state:
        logger.warning(f"Region {region_id} not found")
        return
    
    logger.info(f"Current state of region {region_id}: {original_state}")
    
    # Set all nodes in the region to failing
    region_nodes = []
    for node_id, node_config in ha_cluster.node_configs.items():
        if node_config.region == region_id:
            region_nodes.append(node_id)
            
            # Set node to failing if it's the local node
            if node_id == ha_cluster.local_node_id:
                ha_cluster.set_local_node_status(NodeStatus.FAILING)
    
    logger.info(f"Set {len(region_nodes)} nodes in region {region_id} to failing")
    
    # Wait for health check to detect region failure and perform failover
    failover_wait_time = max(
        ha_cluster.ha_config.health_check_interval_ms,
        ha_cluster.ha_config.failover_timeout_ms
    ) / 1000 * 2
    
    logger.info(f"Waiting {failover_wait_time} seconds for failover...")
    await asyncio.sleep(failover_wait_time)
    
    # Check region states after failover
    all_region_states = ha_cluster.get_all_region_states()
    logger.info("Region states after simulated failure:")
    for r_id, state in all_region_states.items():
        logger.info(f"  {r_id}: {state}")
    
    # Restore local node status if needed
    if ha_cluster.local_node_id in region_nodes:
        ha_cluster.set_local_node_status(NodeStatus.HEALTHY)
        logger.info(f"Restored local node status to {NodeStatus.HEALTHY}")

async def demonstrate_manual_failover(ha_cluster: HACluster):
    """Demonstrate manual failover between regions."""
    # Find primary region
    primary_region = None
    for region in ha_cluster.ha_config.regions:
        if region.primary:
            primary_region = region
            break
    
    if not primary_region:
        logger.warning("No primary region found")
        return
    
    # Find standby region with highest failover priority
    standby_regions = []
    for region in ha_cluster.ha_config.regions:
        if not region.primary:
            standby_regions.append(region)
    
    if not standby_regions:
        logger.warning("No standby regions found")
        return
    
    # Sort by failover priority (higher is better)
    standby_regions.sort(key=lambda r: r.failover_priority, reverse=True)
    target_region = standby_regions[0]
    
    logger.info(f"Initiating manual failover from {primary_region.id} to {target_region.id}...")
    
    # Perform manual failover
    success = await ha_cluster.initiate_manual_failover(primary_region.id, target_region.id)
    
    if success:
        logger.info(f"Manual failover initiated successfully")
        
        # Wait for changes to propagate
        await asyncio.sleep(1)
        
        # Check region states after failover
        all_region_states = ha_cluster.get_all_region_states()
        logger.info("Region states after manual failover:")
        for r_id, state in all_region_states.items():
            logger.info(f"  {r_id}: {state}")
    else:
        logger.error("Manual failover failed")

async def monitor_cluster_health(ha_cluster: HACluster, duration_seconds: int = 30):
    """Monitor the health of the cluster for a period of time."""
    logger.info(f"Monitoring cluster health for {duration_seconds} seconds...")
    
    end_time = datetime.now().timestamp() + duration_seconds
    while datetime.now().timestamp() < end_time:
        # Get node states
        node_states = ha_cluster.get_all_node_states()
        region_states = ha_cluster.get_all_region_states()
        
        # Print summary
        logger.info("--- Cluster Health Summary ---")
        logger.info(f"Total nodes: {len(node_states)}")
        
        # Count nodes by status
        status_counts = {}
        for state in node_states.values():
            status = state.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            logger.info(f"  {status}: {count} nodes")
        
        # Print region states
        logger.info("Region states:")
        for region_id, status in region_states.items():
            logger.info(f"  {region_id}: {status}")
        
        # Wait before next check
        await asyncio.sleep(5)
    
    logger.info("Cluster health monitoring completed")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="High Availability Example for MCP Server")
    parser.add_argument("--redis-url", help="Redis URL for distributed state (e.g., redis://localhost:6379/0)")
    args = parser.parse_args()
    
    # Create a temporary directory for configuration
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Create example configuration
            config_path, local_node_id = create_example_config(temp_dir)
            
            # Initialize HA cluster
            ha_cluster = HACluster(config_path, local_node_id, args.redis_url)
            
            # Start the cluster
            await ha_cluster.start()
            
            try:
                # Initialize load balancer
                load_balancer = LoadBalancer(ha_cluster)
                
                # Monitor cluster health in the background
                monitor_task = asyncio.create_task(monitor_cluster_health(ha_cluster, 60))
                
                # Demonstrate simulated API requests with load balancing
                await simulated_api_requests(load_balancer)
                
                # Demonstrate node failure simulation
                await simulate_node_failure(ha_cluster, local_node_id)
                
                # Demonstrate manual failover between regions
                await demonstrate_manual_failover(ha_cluster)
                
                # Wait for health check to detect region changes
                await asyncio.sleep(ha_cluster.ha_config.health_check_interval_ms / 1000 * 2)
                
                # Demonstrate region failure simulation for the primary region
                primary_region = ha_cluster.ha_config.get_primary_region()
                if primary_region:
                    await simulate_region_failure(ha_cluster, primary_region.id)
                
                # Wait for monitoring to complete
                await monitor_task
                
            finally:
                # Stop the cluster
                await ha_cluster.stop()
                
        except Exception as e:
            logger.error(f"Error: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())

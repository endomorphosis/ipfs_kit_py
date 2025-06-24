#!/usr/bin/env python3
"""
Example demonstrating the use of the IPFS Kit cluster management capabilities.

This example shows how to:
1. Create a cluster with a master node
2. Add worker and leecher nodes to the cluster
3. Monitor cluster health and performance
4. Use role-based optimizations for different node types
"""

import os
import time
import logging
import argparse
import threading
from pathlib import Path
import psutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("cluster-example")

# Import ipfs_kit_py modules
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.cluster.role_manager import NodeRole, RoleManager
from ipfs_kit_py.cluster.distributed_coordination import MembershipManager, ClusterCoordinator
from ipfs_kit_py.cluster.monitoring import MetricsCollector, ClusterMonitor

def resource_metrics_provider():
    """Provides system resource metrics for monitoring."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available // (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_available_gb": disk.free // (1024 * 1024 * 1024)
        }
    except Exception as e:
        logger.error(f"Error collecting resource metrics: {e}")
        return {}

def alert_handler(source, alert):
    """Handles alerts from cluster monitoring."""
    print(f"ALERT from {source}: [{alert['level']}] {alert['message']}")

def create_ipfs_node(role_str, node_id=None, ipfs_path=None, cluster_id=None):
    """Create an IPFS node with the specified role."""
    # Generate a unique node ID if not provided
    if node_id is None:
        import uuid
        node_id = f"node-{uuid.uuid4().hex[:8]}"

    # Set up IPFS path
    if ipfs_path is None:
        home_dir = str(Path.home())
        ipfs_path = os.path.join(home_dir, f".ipfs-{role_str}-{node_id}")

    logger.info(f"Creating {role_str} node with ID {node_id} at {ipfs_path}")

    # Parse role
    role = NodeRole.from_string(role_str)

    # Create IPFS Kit instance
    kit = IPFSKit(
        role=role_str,
        resources={
            "ipfs_path": ipfs_path,
            "node_id": node_id
        },
        metadata={
            "cluster_id": cluster_id,
            "example_node": True
        }
    )

    # Create role manager
    role_manager = RoleManager(
        initial_role=role_str,
        resources=resource_metrics_provider(),
        metadata={
            "cluster_id": cluster_id,
            "node_id": node_id
        },
        auto_detect=True,
        role_switching_enabled=True,
        configuration_callback=lambda role, config: logger.info(f"Configuration updated for role {role}")
    )

    # Create metrics collector
    metrics_dir = os.path.join(ipfs_path, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)

    metrics_collector = MetricsCollector(
        node_id=node_id,
        metrics_dir=metrics_dir,
        collection_interval=30,  # 30 seconds for example
        retention_days=1  # Keep metrics for 1 day
    )

    # Register metrics sources
    metrics_collector.register_metric_source("resources", resource_metrics_provider)

    # Create cluster monitor
    cluster_monitor = ClusterMonitor(
        node_id=node_id,
        metrics_collector=metrics_collector,
        check_interval=30,  # 30 seconds for example
        alert_callback=alert_handler
    )

    # Create membership manager
    membership_manager = MembershipManager(
        cluster_id=cluster_id or "example-cluster",
        node_id=node_id,
        heartbeat_interval=15  # 15 seconds for example
    )

    # Create cluster coordinator
    cluster_coordinator = ClusterCoordinator(
        cluster_id=cluster_id or "example-cluster",
        node_id=node_id,
        is_master=(role == NodeRole.MASTER),
        election_timeout=15,  # 15 seconds for example
        membership_manager=membership_manager
    )

    # Return components
    return {
        "kit": kit,
        "role_manager": role_manager,
        "metrics_collector": metrics_collector,
        "cluster_monitor": cluster_monitor,
        "membership_manager": membership_manager,
        "cluster_coordinator": cluster_coordinator,
        "node_id": node_id,
        "ipfs_path": ipfs_path
    }

def run_master_node(cluster_id=None, node_id=None):
    """Run a master node and create a cluster."""
    # Create node components
    logger.info("Creating master node...")
    master = create_ipfs_node(
        role_str="master",
        node_id=node_id,
        cluster_id=cluster_id
    )

    # Create a new cluster
    cluster_id = master["cluster_coordinator"].cluster_id
    logger.info(f"Creating cluster with ID: {cluster_id}")
    master["cluster_coordinator"].create_cluster(cluster_id)

    # Log master node info
    logger.info(f"Master node created with ID: {master['node_id']}")
    logger.info(f"Cluster ID: {cluster_id}")

    # Start simulating some cluster activity
    def activity_loop():
        """Simulate cluster activity."""
        while True:
            try:
                # Log status every minute
                time.sleep(60)

                # Get cluster status
                status = master["cluster_coordinator"].get_cluster_status()
                logger.info(f"Cluster status: {status['node_role']} - {len(status.get('peers', []))} peers")

                # Get health status
                health = master["cluster_monitor"].get_cluster_health()
                logger.info(f"Cluster health: {health['status']} with {len(health.get('issues', []))} issues")

            except Exception as e:
                logger.error(f"Error in activity loop: {e}")

    # Start activity thread
    activity_thread = threading.Thread(
        target=activity_loop,
        daemon=True,
        name="master-activity"
    )
    activity_thread.start()

    return master, cluster_id

def run_worker_node(cluster_id, master_address, node_id=None):
    """Run a worker node and join an existing cluster."""
    # Create node components
    logger.info("Creating worker node...")
    worker = create_ipfs_node(
        role_str="worker",
        node_id=node_id,
        cluster_id=cluster_id
    )

    # Join the cluster
    logger.info(f"Joining cluster {cluster_id} via master at {master_address}")
    worker["cluster_coordinator"].join_cluster(cluster_id, master_address)

    # Log worker node info
    logger.info(f"Worker node created with ID: {worker['node_id']}")

    return worker

def run_leecher_node(cluster_id, master_address, node_id=None):
    """Run a leecher node and join an existing cluster."""
    # Create node components
    logger.info("Creating leecher node...")
    leecher = create_ipfs_node(
        role_str="leecher",
        node_id=node_id,
        cluster_id=cluster_id
    )

    # Join the cluster
    logger.info(f"Joining cluster {cluster_id} via master at {master_address}")
    leecher["cluster_coordinator"].join_cluster(cluster_id, master_address)

    # Log leecher node info
    logger.info(f"Leecher node created with ID: {leecher['node_id']}")

    return leecher

def main():
    """Run the example."""
    parser = argparse.ArgumentParser(
        description="Example demonstrating IPFS Kit cluster management capabilities"
    )
    parser.add_argument(
        "--role",
        choices=["master", "worker", "leecher"],
        default="master",
        help="Role for this node"
    )
    parser.add_argument(
        "--cluster",
        help="Cluster ID to join (generated for master if not provided)"
    )
    parser.add_argument(
        "--master",
        help="Master node address for worker/leecher nodes"
    )
    parser.add_argument(
        "--node-id",
        help="Node ID (generated if not provided)"
    )
    args = parser.parse_args()

    if args.role == "master":
        # Create master node and cluster
        master, cluster_id = run_master_node(
            cluster_id=args.cluster,
            node_id=args.node_id
        )

        # Keep the program running
        try:
            print(f"Master node running with ID: {master['node_id']}")
            print(f"Cluster ID: {cluster_id}")
            print(f"Press Ctrl+C to exit")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")

    elif args.role == "worker":
        # Check required arguments
        if not args.master:
            parser.error("--master is required for worker nodes")
        if not args.cluster:
            parser.error("--cluster is required for worker nodes")

        # Create worker node
        worker = run_worker_node(
            cluster_id=args.cluster,
            master_address=args.master,
            node_id=args.node_id
        )

        # Keep the program running
        try:
            print(f"Worker node running with ID: {worker['node_id']}")
            print(f"Press Ctrl+C to exit")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")

    elif args.role == "leecher":
        # Check required arguments
        if not args.master:
            parser.error("--master is required for leecher nodes")
        if not args.cluster:
            parser.error("--cluster is required for leecher nodes")

        # Create leecher node
        leecher = run_leecher_node(
            cluster_id=args.cluster,
            master_address=args.master,
            node_id=args.node_id
        )

        # Keep the program running
        try:
            print(f"Leecher node running with ID: {leecher['node_id']}")
            print(f"Press Ctrl+C to exit")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")

if __name__ == "__main__":
    main()

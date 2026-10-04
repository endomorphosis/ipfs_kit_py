#!/usr/bin/env python3
"""
PRACTICAL CLUSTER SETUP SCRIPT
==============================

This script demonstrates how to use the enhanced daemon manager with cluster capabilities
in a real-world scenario. It shows how to:

1. Start a master node with full privileges
2. Start worker nodes that can receive replication
3. Start leecher nodes with read-only access
4. Demonstrate automatic leader election and failover
5. Show replication management in action
6. Use indexing services for embeddings, peer lists, and knowledge graphs

Usage Examples:
  # Start a master node
  python practical_cluster_setup.py --role master --node-id master-1 --start-daemon --start-cluster

  # Start a worker node
  python practical_cluster_setup.py --role worker --node-id worker-1 --start-daemon --start-cluster

  # Start a leecher node
  python practical_cluster_setup.py --role leecher --node-id leecher-1 --start-daemon --start-cluster

  # Monitor cluster status
  python practical_cluster_setup.py --action cluster-status --node-id monitor
"""

import os
import sys
import json
import logging
import anyio
import argparse
import time
import signal
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import from ipfs_kit_py.cluster
from ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster import (
    EnhancedDaemonManager,
    NodeRole,
    PeerInfo,
    LeaderElection,
    ReplicationManager,
    IndexingService
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cluster_setup.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("cluster-setup")

class ClusterNode:
    """Represents a single node in the cluster"""
    
    def __init__(self, node_id: str, role: NodeRole, daemon_type: str = "ipfs", 
                 mcp_port: int = 9998, api_port: int = 5001):
        self.node_id = node_id
        self.role = role
        self.daemon_type = daemon_type
        self.mcp_port = mcp_port
        self.api_port = api_port
        
        # Initialize daemon manager
        self.manager = EnhancedDaemonManager(
            node_id=node_id,
            node_role=role,
            daemon_type=daemon_type,
            debug=True,
            api_port=api_port
        )
        self.manager.mcp_server_port = mcp_port
        
        # Track if services are running
        self.daemon_running = False
        self.cluster_running = False
        
        logger.info(f"🏗 Created cluster node: {node_id} (role: {role.value})")
    
    def start_daemon(self) -> bool:
        """Start the underlying daemon (IPFS, etc.)"""
        logger.info(f"🚀 Starting {self.daemon_type} daemon for node {self.node_id}")
        
        try:
            success = self.manager.start()
            if success:
                self.daemon_running = True
                logger.info(f"✅ Daemon started for node {self.node_id}")
            else:
                logger.error(f"❌ Failed to start daemon for node {self.node_id}")
            return success
        except Exception as e:
            logger.error(f"❌ Exception starting daemon for {self.node_id}: {e}")
            return False
    
    def start_cluster_services(self):
        """Start cluster services (leader election, replication, indexing)"""
        logger.info(f"🔄 Starting cluster services for node {self.node_id}")
        
        try:
            self.manager.start_cluster_services()
            self.cluster_running = True
            logger.info(f"✅ Cluster services started for node {self.node_id}")
        except Exception as e:
            logger.error(f"❌ Failed to start cluster services for {self.node_id}: {e}")
    
    def stop_all_services(self):
        """Stop all services"""
        logger.info(f"🔄 Stopping all services for node {self.node_id}")
        
        if self.cluster_running:
            self.manager.stop_cluster_services()
            self.cluster_running = False
        
        if self.daemon_running:
            self.manager.stop()
            self.daemon_running = False
        
        logger.info(f"✅ All services stopped for node {self.node_id}")
    
    def add_peer(self, peer_node: 'ClusterNode'):
        """Add another node as a peer"""
        peer_info = PeerInfo(
            id=peer_node.node_id,
            role=peer_node.role,
            address="127.0.0.1",
            port=peer_node.mcp_port,
            is_healthy=True,
            capabilities={
                "daemon_type": peer_node.daemon_type,
                "api_port": peer_node.api_port,
                "can_replicate": peer_node.manager.replication_manager.can_receive_replication(),
                "can_index": peer_node.manager.indexing_service.can_modify_index()
            }
        )
        
        self.manager.add_peer(peer_info)
        logger.info(f"➕ Added peer {peer_node.node_id} to {self.node_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive node status"""
        return {
            "node_id": self.node_id,
            "role": self.role.value,
            "daemon_running": self.daemon_running,
            "cluster_running": self.cluster_running,
            "daemon_type": self.daemon_type,
            "ports": {
                "mcp": self.mcp_port,
                "api": self.api_port
            },
            "cluster_status": self.manager.get_cluster_status() if self.cluster_running else None
        }

class ClusterManager:
    """Manages multiple cluster nodes"""
    
    def __init__(self):
        self.nodes = {}
        self.shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"🔄 Received signal {signum}, initiating shutdown...")
        self.shutdown_requested = True
    
    def add_node(self, node: ClusterNode):
        """Add a node to the cluster"""
        self.nodes[node.node_id] = node
        
        # Add this node as a peer to all existing nodes
        for existing_node_id, existing_node in self.nodes.items():
            if existing_node_id != node.node_id:
                existing_node.add_peer(node)
                node.add_peer(existing_node)
        
        logger.info(f"➕ Added node {node.node_id} to cluster manager")
    
    def start_node(self, node_id: str, start_daemon: bool = True, start_cluster: bool = True) -> bool:
        """Start services for a specific node"""
        if node_id not in self.nodes:
            logger.error(f"❌ Node {node_id} not found")
            return False
        
        node = self.nodes[node_id]
        
        success = True
        if start_daemon:
            success = node.start_daemon()
        
        if success and start_cluster:
            node.start_cluster_services()
        
        return success
    
    def stop_node(self, node_id: str):
        """Stop services for a specific node"""
        if node_id in self.nodes:
            self.nodes[node_id].stop_all_services()
            logger.info(f"✅ Stopped node {node_id}")
    
    def stop_all_nodes(self):
        """Stop all nodes in the cluster"""
        logger.info("🔄 Stopping all cluster nodes...")
        for node_id in self.nodes:
            self.stop_node(node_id)
        logger.info("✅ All nodes stopped")
    
    def get_cluster_overview(self) -> Dict[str, Any]:
        """Get overview of the entire cluster"""
        overview = {
            "total_nodes": len(self.nodes),
            "nodes_by_role": {},
            "nodes": {},
            "cluster_health": {}
        }
        
        # Count nodes by role
        for node in self.nodes.values():
            role = node.role.value
            if role not in overview["nodes_by_role"]:
                overview["nodes_by_role"][role] = 0
            overview["nodes_by_role"][role] += 1
        
        # Get status for each node
        for node_id, node in self.nodes.items():
            overview["nodes"][node_id] = node.get_status()
        
        # Analyze cluster health
        running_nodes = sum(1 for node in self.nodes.values() if node.daemon_running)
        cluster_nodes = sum(1 for node in self.nodes.values() if node.cluster_running)
        
        overview["cluster_health"] = {
            "nodes_with_daemon": running_nodes,
            "nodes_with_cluster": cluster_nodes,
            "health_percentage": (running_nodes / len(self.nodes) * 100) if self.nodes else 0
        }
        
        return overview
    
    async def demonstrate_cluster_capabilities(self):
        """Demonstrate the cluster's capabilities"""
        logger.info("🎯 === DEMONSTRATING CLUSTER CAPABILITIES ===")
        
        # Find master nodes for demonstrations
        master_nodes = [node for node in self.nodes.values() if node.role == NodeRole.MASTER]
        
        if not master_nodes:
            logger.warning("⚠ No master nodes available for demonstration")
            return
        
        master_node = master_nodes[0]
        
        # 1. Demonstrate leader election
        logger.info("🗳 Testing leader election...")
        leader = master_node.manager.leader_election.elect_leader()
        if leader:
            logger.info(f"✅ Leader elected: {leader.id} (role: {leader.role.value})")
        
        # 2. Demonstrate replication
        logger.info("🔄 Testing content replication...")
        test_cid = "QmPracticalTest123456789abcdef"
        
        # Get eligible peers for replication
        eligible_peers = [
            peer for peer in master_node.manager.peers.values()
            if peer.role in [NodeRole.MASTER, NodeRole.WORKER] and peer.is_healthy
        ]
        
        if eligible_peers:
            result = await master_node.manager.replication_manager.replicate_content(
                cid=test_cid,
                target_peers=eligible_peers,
                priority=1
            )
            
            if result["success"]:
                logger.info(f"✅ Replicated content to {result['target_count']} peers")
            else:
                logger.error(f"❌ Replication failed: {result.get('message', 'Unknown error')}")
        
        # 3. Demonstrate indexing
        logger.info("📊 Testing indexing services...")
        
        # Add some test data to different indexes
        test_data = {
            "embeddings": {
                "practical_doc": {
                    "vector": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "content": "This is a practical demonstration document",
                    "metadata": {"source": "demo", "timestamp": time.time()}
                }
            },
            "peer_lists": {
                "production_cluster": {
                    "peers": [node.node_id for node in self.nodes.values()],
                    "region": "local",
                    "capabilities": ["storage", "retrieval", "indexing"]
                }
            },
            "knowledge_graph": {
                "cluster_entity": {
                    "type": "cluster",
                    "name": "IPFS Demo Cluster",
                    "nodes": len(self.nodes),
                    "connections": ["storage_network", "replication_network"]
                }
            }
        }
        
        for index_type, entries in test_data.items():
            for key, data in entries.items():
                result = await master_node.manager.indexing_service.add_index_data(
                    index_type=index_type,
                    key=key,
                    data=data
                )
                
                if result["success"]:
                    logger.info(f"✅ Added {key} to {index_type} index")
                else:
                    logger.warning(f"⚠ Failed to add {key}: {result['message']}")
        
        # Test reading from different node types
        for node_id, node in self.nodes.items():
            if node.cluster_running:
                result = await node.manager.indexing_service.get_index_data("embeddings")
                if result["success"]:
                    count = result.get("total_entries", 0)
                    logger.info(f"📖 Node {node_id} ({node.role.value}) can read {count} embeddings")
        
        logger.info("✅ Cluster capabilities demonstration complete")

def create_sample_cluster() -> ClusterManager:
    """Create a sample cluster for demonstration"""
    logger.info("🏗 Creating sample cluster...")
    
    cluster_manager = ClusterManager()
    
    # Create nodes with different roles and ports
    nodes_config = [
        {"id": "master-primary", "role": NodeRole.MASTER, "mcp_port": 9998, "api_port": 5001},
        {"id": "master-secondary", "role": NodeRole.MASTER, "mcp_port": 9999, "api_port": 5002},
        {"id": "worker-alpha", "role": NodeRole.WORKER, "mcp_port": 10000, "api_port": 5003},
        {"id": "worker-beta", "role": NodeRole.WORKER, "mcp_port": 10001, "api_port": 5004},
        {"id": "leecher-gamma", "role": NodeRole.LEECHER, "mcp_port": 10002, "api_port": 5005},
    ]
    
    for config in nodes_config:
        node = ClusterNode(
            node_id=config["id"],
            role=config["role"],
            daemon_type="ipfs",
            mcp_port=config["mcp_port"],
            api_port=config["api_port"]
        )
        cluster_manager.add_node(node)
    
    logger.info(f"✅ Sample cluster created with {len(nodes_config)} nodes")
    return cluster_manager

async def main():
    """Main function for the practical cluster setup"""
    parser = argparse.ArgumentParser(
        description="Practical Cluster Setup with Enhanced Daemon Manager",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Node configuration
    parser.add_argument("--node-id", default=f"node_{int(time.time())}", 
                       help="Unique identifier for this node")
    parser.add_argument("--role", choices=["master", "worker", "leecher"], default="worker",
                       help="Role of this node in the cluster")
    parser.add_argument("--daemon-type", choices=["ipfs", "aria2", "lotus"], default="ipfs",
                       help="Type of daemon to manage")
    
    # Ports
    parser.add_argument("--mcp-port", type=int, default=9998,
                       help="Port for MCP server")
    parser.add_argument("--api-port", type=int, default=5001,
                       help="Port for daemon API")
    
    # Actions
    parser.add_argument("--action", choices=["start", "stop", "status", "demo", "cluster-status"],
                       default="start", help="Action to perform")
    parser.add_argument("--start-daemon", action="store_true",
                       help="Start the underlying daemon")
    parser.add_argument("--start-cluster", action="store_true",
                       help="Start cluster services")
    parser.add_argument("--demo", action="store_true",
                       help="Run demonstration of cluster capabilities")
    
    # Configuration
    parser.add_argument("--config-dir", help="Configuration directory")
    parser.add_argument("--log-dir", help="Log directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Convert role string to enum
    node_role = NodeRole(args.role)
    
    try:
        if args.action == "demo":
            # Run full demonstration
            logger.info("🎯 Starting comprehensive cluster demonstration...")
            
            cluster_manager = create_sample_cluster()
            
            # Start all nodes
            for node_id in cluster_manager.nodes:
                logger.info(f"🚀 Starting node {node_id}...")
                cluster_manager.start_node(node_id, start_daemon=False, start_cluster=True)
            
            # Wait for initialization
            await anyio.sleep(2)
            
            # Run demonstrations
            await cluster_manager.demonstrate_cluster_capabilities()
            
            # Show cluster overview
            overview = cluster_manager.get_cluster_overview()
            logger.info("📊 CLUSTER OVERVIEW:")
            logger.info(json.dumps(overview, indent=2))
            
            # Cleanup
            cluster_manager.stop_all_nodes()
            
        elif args.action == "start":
            # Start a single node
            logger.info(f"🚀 Starting single node: {args.node_id} (role: {args.role})")
            
            node = ClusterNode(
                node_id=args.node_id,
                role=node_role,
                daemon_type=args.daemon_type,
                mcp_port=args.mcp_port,
                api_port=args.api_port
            )
            
            # Configure daemon manager
            if args.config_dir:
                node.manager.config_dir = args.config_dir
            if args.log_dir:
                node.manager.log_dir = args.log_dir
            
            # Start services
            success = True
            if args.start_daemon:
                success = node.start_daemon()
            
            if success and args.start_cluster:
                node.start_cluster_services()
                
                # Keep running and monitoring
                logger.info("🔄 Node running. Press Ctrl+C to stop...")
                try:
                    while True:
                        await anyio.sleep(10)
                        
                        # Periodic status log
                        status = node.get_status()
                        logger.debug(f"Node status: {json.dumps(status, indent=2)}")
                        
                except KeyboardInterrupt:
                    logger.info("🔄 Shutdown requested...")
                    node.stop_all_services()
            
        elif args.action == "status":
            # Show status (placeholder - would connect to running node)
            logger.info(f"📊 Status for node {args.node_id} would be shown here")
            logger.info("(In a real implementation, this would connect to the running node)")
            
        elif args.action == "cluster-status":
            # Show cluster status (placeholder)
            logger.info("📊 Cluster status would be shown here")
            logger.info("(In a real implementation, this would query all cluster nodes)")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("🔄 Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        if args.debug:
            import traceback
            logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    import sys
    anyio.run(main)

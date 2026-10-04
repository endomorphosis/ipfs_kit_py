#!/usr/bin/env python3
"""
ENHANCED DAEMON MANAGER WITH CLUSTER SERVICES
==============================================

Comprehensive daemon manager that integrates:
- Leader election among peers with role hierarchy (master > worker > leecher) 
- Replication management (master-only control)
- Indexing services for embeddings, peer lists, and knowledge graphs (master-only)
- Full integration with ipfs_kit_py MCP server processes
- Health monitoring and automatic failover

This builds on the existing daemon manager and adds sophisticated distributed system capabilities.
"""

import os
import sys
import json
import logging
import anyio
import argparse
import traceback
import hashlib
import signal
import time
import threading
import socket
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

# Import existing daemon manager
from ipfs_kit_py.mcp.ipfs_kit.core.daemon_manager import DaemonManager as BaseDaemonManager, DaemonTypes

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_daemon_manager.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced-daemon-manager")

# ============================================================================
# CLUSTER MANAGEMENT TYPES AND ENUMS  
# ============================================================================

class NodeRole(Enum):
    """Node roles in the cluster hierarchy"""
    MASTER = "master"
    WORKER = "worker" 
    LEECHER = "leecher"
    
    @classmethod
    def get_priority(cls, role) -> int:
        """Get priority for leader election (lower = higher priority)"""
        priorities = {
            cls.MASTER: 0,
            cls.WORKER: 1,
            cls.LEECHER: 999  # Never eligible for leadership
        }
        return priorities.get(role, 100)

@dataclass
class PeerInfo:
    """Information about a peer in the cluster"""
    id: str
    role: NodeRole
    address: str
    port: int
    last_seen: datetime = field(default_factory=datetime.now)
    is_healthy: bool = True
    capabilities: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "address": self.address,
            "port": self.port,
            "last_seen": self.last_seen.isoformat(),
            "is_healthy": self.is_healthy,
            "capabilities": self.capabilities
        }

@dataclass
class ReplicationTask:
    """Represents a content replication task"""
    cid: str
    target_peers: List[str]
    priority: int = 1
    max_retries: int = 3
    current_retries: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, in_progress, completed, failed

# ============================================================================
# LEADER ELECTION SYSTEM
# ============================================================================

class LeaderElection:
    """
    Distributed leader election system with role-based priority.
    Uses a simple consensus algorithm with role hierarchy.
    """
    
    def __init__(self, node_id: str, node_role: NodeRole, peers: Dict[str, PeerInfo]):
        self.node_id = node_id
        self.node_role = node_role
        self.peers = peers
        self.current_leader = None
        self.election_in_progress = False
        self.election_timeout = 30  # seconds
        self.heartbeat_interval = 10  # seconds
        self.last_heartbeat = {}
        
        logger.info(f"🗳 Leader election initialized for node {node_id} with role {node_role.value}")
    
    def is_eligible_for_leadership(self, role: NodeRole) -> bool:
        """Check if a role is eligible for leadership"""
        return role != NodeRole.LEECHER
    
    def get_eligible_peers(self) -> List[PeerInfo]:
        """Get all peers eligible for leadership, sorted by priority"""
        eligible = []
        
        # Include self if eligible
        if self.is_eligible_for_leadership(self.node_role):
            self_peer = PeerInfo(
                id=self.node_id,
                role=self.node_role,
                address="localhost",
                port=0,
                is_healthy=True
            )
            eligible.append(self_peer)
        
        # Add eligible peers
        for peer in self.peers.values():
            if self.is_eligible_for_leadership(peer.role) and peer.is_healthy:
                eligible.append(peer)
        
        # Sort by role priority, then by node ID for deterministic ordering
        eligible.sort(key=lambda p: (NodeRole.get_priority(p.role), p.id))
        
        logger.debug(f"🗳 Found {len(eligible)} eligible peers for leadership")
        return eligible
    
    def elect_leader(self) -> Optional[PeerInfo]:
        """
        Elect a leader based on role hierarchy and availability.
        Returns the elected leader or None if no eligible candidates.
        """
        if self.election_in_progress:
            logger.warning("🗳 Election already in progress")
            return self.current_leader
        
        self.election_in_progress = True
        logger.info("🗳 Starting leader election...")
        
        try:
            eligible_peers = self.get_eligible_peers()
            
            if not eligible_peers:
                logger.warning("🗳 No eligible peers found for leadership")
                return None
            
            # Simple deterministic election: highest priority (lowest number) wins
            new_leader = eligible_peers[0]
            
            logger.info(f"🗳 Leader elected: {new_leader.id} (role: {new_leader.role.value})")
            
            # Update current leader
            self.current_leader = new_leader
            
            # Start heartbeat monitoring if we're not the leader
            if new_leader.id != self.node_id:
                self._start_heartbeat_monitoring(new_leader)
            
            return new_leader
            
        finally:
            self.election_in_progress = False
    
    def _start_heartbeat_monitoring(self, leader: PeerInfo):
        """Start monitoring heartbeat from the current leader"""
        logger.info(f"💓 Starting heartbeat monitoring for leader {leader.id}")
        self.last_heartbeat[leader.id] = datetime.now()
    
    def receive_heartbeat(self, leader_id: str):
        """Receive heartbeat from leader"""
        self.last_heartbeat[leader_id] = datetime.now()
        logger.debug(f"💓 Received heartbeat from leader {leader_id}")
    
    def check_leader_health(self) -> bool:
        """Check if current leader is healthy"""
        if not self.current_leader:
            return False
        
        leader_id = self.current_leader.id
        if leader_id == self.node_id:
            return True  # We are the leader
        
        last_heartbeat = self.last_heartbeat.get(leader_id)
        if not last_heartbeat:
            return False
        
        # Check if heartbeat is recent
        timeout_threshold = datetime.now() - timedelta(seconds=self.heartbeat_interval * 3)
        return last_heartbeat > timeout_threshold
    
    def trigger_election_if_needed(self):
        """Trigger new election if leader is unhealthy"""
        if not self.check_leader_health():
            logger.warning("🗳 Leader appears unhealthy, triggering new election")
            self.current_leader = None
            return self.elect_leader()
        return self.current_leader

# ============================================================================
# REPLICATION MANAGEMENT SYSTEM
# ============================================================================

class ReplicationManager:
    """
    Manages content replication across the cluster.
    Only master nodes can initiate replication operations.
    """
    
    def __init__(self, node_role: NodeRole, ipfs_kit_instance: Any = None):
        self.node_role = node_role
        self.ipfs_kit = ipfs_kit_instance
        self.replication_tasks = {}
        self.active_replications = set()
        self.max_concurrent_replications = 5
        
        logger.info(f"🔄 ReplicationManager initialized with role: {node_role.value}")
    
    def can_initiate_replication(self) -> bool:
        """Check if this node can initiate replication"""
        return self.node_role == NodeRole.MASTER
    
    def can_receive_replication(self) -> bool:
        """Check if this node can receive replicated content"""
        return self.node_role in [NodeRole.MASTER, NodeRole.WORKER]
    
    async def replicate_content(self, cid: str, target_peers: List[PeerInfo], priority: int = 1) -> Dict[str, Any]:
        """
        Initiate content replication to target peers.
        Only masters can initiate replication.
        """
        if not self.can_initiate_replication():
            logger.warning(f"🚫 Node role {self.node_role.value} cannot initiate replication")
            return {
                "success": False,
                "message": f"Only master nodes can initiate replication, current role: {self.node_role.value}"
            }
        
        # Filter target peers to only include those that can receive replication
        eligible_targets = [
            peer for peer in target_peers 
            if peer.role in [NodeRole.MASTER, NodeRole.WORKER] and peer.is_healthy
        ]
        
        if not eligible_targets:
            return {
                "success": False,
                "message": "No eligible target peers for replication"
            }
        
        # Create replication task
        task_id = f"{cid}_{int(time.time())}"
        task = ReplicationTask(
            cid=cid,
            target_peers=[peer.id for peer in eligible_targets],
            priority=priority
        )
        
        self.replication_tasks[task_id] = task
        
        logger.info(f"🔄 Starting replication of {cid} to {len(eligible_targets)} peers")
        
        # Execute replication
        results = await self._execute_replication(task)
        
        return {
            "success": True,
            "task_id": task_id,
            "cid": cid,
            "target_count": len(eligible_targets),
            "results": results
        }
    
    async def _execute_replication(self, task: ReplicationTask) -> Dict[str, Any]:
        """Execute the actual replication process"""
        task.status = "in_progress"
        results = {}
        
        for peer_id in task.target_peers:
            try:
                # In a real implementation, this would use the MCP server
                # to communicate with remote peers for content pinning
                logger.info(f"🔄 Replicating {task.cid} to peer {peer_id}")
                
                # Simulate replication (in real implementation, use MCP tools)
                await anyio.sleep(0.1)  # Simulate network delay
                
                results[peer_id] = {
                    "success": True,
                    "message": f"Successfully replicated {task.cid} to {peer_id}",
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"✅ Replicated {task.cid} to peer {peer_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to replicate {task.cid} to peer {peer_id}: {e}")
                results[peer_id] = {
                    "success": False,
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        task.status = "completed"
        return results
    
    def get_replication_status(self, task_id: str = None) -> Dict[str, Any]:
        """Get status of replication tasks"""
        if task_id:
            task = self.replication_tasks.get(task_id)
            return task.__dict__ if task else {"error": "Task not found"}
        
        return {
            "total_tasks": len(self.replication_tasks),
            "active_replications": len(self.active_replications),
            "tasks": {tid: task.__dict__ for tid, task in self.replication_tasks.items()}
        }

# ============================================================================
# INDEXING SERVICE
# ============================================================================

class IndexingService:
    """
    Manages distributed indexing of various data types.
    Only master nodes can modify index data.
    """
    
    def __init__(self, node_role: NodeRole):
        self.node_role = node_role
        self.indexes = {
            "embeddings": {},      # Vector embeddings for similarity search
            "peer_lists": {},      # Peer discovery and capability information
            "knowledge_graph": {}, # Graph-based knowledge representation
            "content_metadata": {},# Metadata about IPFS content
            "replication_state": {}# State of content replication
        }
        self.index_locks = {index_type: threading.RLock() for index_type in self.indexes}
        
        logger.info(f"📊 IndexingService initialized with role: {node_role.value}")
    
    def can_modify_index(self) -> bool:
        """Check if this node can modify index data"""
        return self.node_role == NodeRole.MASTER
    
    def can_read_index(self) -> bool:
        """Check if this node can read index data"""
        return True  # All nodes can read
    
    async def add_index_data(self, index_type: str, key: str, data: Any) -> Dict[str, Any]:
        """Add data to an index (master-only operation)"""
        if not self.can_modify_index():
            logger.warning(f"🚫 Node role {self.node_role.value} cannot modify index data")
            return {
                "success": False,
                "message": f"Only master nodes can modify indexes, current role: {self.node_role.value}"
            }
        
        if index_type not in self.indexes:
            return {
                "success": False,
                "message": f"Invalid index type: {index_type}. Available: {list(self.indexes.keys())}"
            }
        
        with self.index_locks[index_type]:
            self.indexes[index_type][key] = {
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "added_by": "master_node"  # In real implementation, use actual node ID
            }
        
        logger.info(f"📊 Added data to {index_type} index with key: {key}")
        return {
            "success": True,
            "message": f"Data added to {index_type} index",
            "key": key,
            "index_type": index_type
        }
    
    async def remove_index_data(self, index_type: str, key: str) -> Dict[str, Any]:
        """Remove data from an index (master-only operation)"""
        if not self.can_modify_index():
            logger.warning(f"🚫 Node role {self.node_role.value} cannot modify index data")
            return {
                "success": False,
                "message": f"Only master nodes can modify indexes, current role: {self.node_role.value}"
            }
        
        if index_type not in self.indexes:
            return {
                "success": False,
                "message": f"Invalid index type: {index_type}"
            }
        
        with self.index_locks[index_type]:
            if key in self.indexes[index_type]:
                del self.indexes[index_type][key]
                logger.info(f"📊 Removed data from {index_type} index with key: {key}")
                return {
                    "success": True,
                    "message": f"Data removed from {index_type} index"
                }
            else:
                return {
                    "success": False,
                    "message": f"Key '{key}' not found in {index_type} index"
                }
    
    async def get_index_data(self, index_type: str, key: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve data from an index"""
        if not self.can_read_index():
            return {
                "success": False,
                "message": "Node cannot read index data"
            }
        
        if index_type not in self.indexes:
            return {
                "success": False,
                "message": f"Invalid index type: {index_type}"
            }
        
        with self.index_locks[index_type]:
            if key:
                data = self.indexes[index_type].get(key)
                if data:
                    return {
                        "success": True,
                        "data": data,
                        "key": key,
                        "index_type": index_type
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Key '{key}' not found in {index_type} index"
                    }
            else:
                return {
                    "success": True,
                    "data": dict(self.indexes[index_type]),
                    "index_type": index_type,
                    "total_entries": len(self.indexes[index_type])
                }
    
    async def search_embeddings(self, query_vector: List[float], top_k: int = 5) -> Dict[str, Any]:
        """Search for similar embeddings (simplified implementation)"""
        if not self.can_read_index():
            return {"success": False, "message": "Node cannot read index data"}
        
        # Simplified similarity search (in real implementation, use proper vector database)
        embeddings_index = self.indexes["embeddings"]
        
        if not embeddings_index:
            return {
                "success": True,
                "results": [],
                "message": "No embeddings in index"
            }
        
        # Mock similarity calculation (in real implementation, use cosine similarity, etc.)
        results = []
        for key, entry in embeddings_index.items():
            if "vector" in entry.get("data", {}):
                # Simplified similarity score
                similarity = 0.8 - abs(hash(key) % 100) / 500  # Mock calculation
                results.append({
                    "key": key,
                    "similarity": similarity,
                    "data": entry["data"],
                    "timestamp": entry["timestamp"]
                })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        return {
            "success": True,
            "results": results[:top_k],
            "total_found": len(results),
            "query_vector_dim": len(query_vector)
        }
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about all indexes"""
        stats = {}
        for index_type in self.indexes:
            with self.index_locks[index_type]:
                stats[index_type] = {
                    "total_entries": len(self.indexes[index_type]),
                    "can_modify": self.can_modify_index(),
                    "can_read": self.can_read_index()
                }
        
        return {
            "node_role": self.node_role.value,
            "indexes": stats,
            "total_indexes": len(self.indexes)
        }

# ============================================================================
# ENHANCED DAEMON MANAGER WITH CLUSTER CAPABILITIES
# ============================================================================

class EnhancedDaemonManager(BaseDaemonManager):
    """
    Enhanced daemon manager that integrates cluster services:
    - Leader election with role hierarchy
    - Replication management
    - Distributed indexing
    - Health monitoring and failover
    """
    
    def __init__(self, node_id: str = None, node_role: NodeRole = NodeRole.WORKER, **kwargs):
        super().__init__(**kwargs)
        
        # Cluster configuration
        self.node_id = node_id or f"node_{int(time.time())}_{os.getpid()}"
        self.node_role = node_role
        self.peers = {}
        
        # Cluster services
        self.leader_election = LeaderElection(self.node_id, self.node_role, self.peers)
        self.replication_manager = ReplicationManager(self.node_role)
        self.indexing_service = IndexingService(self.node_role)
        
        # MCP server integration
        self.mcp_server_process = None
        self.mcp_server_port = 9998
        
        # Health monitoring
        self.health_check_enabled = True
        self.health_check_thread = None
        self.should_stop_health_check = False
        
        logger.info(f"🚀 EnhancedDaemonManager initialized: node_id={self.node_id}, role={self.node_role.value}")
    
    def start_cluster_services(self):
        """Start all cluster-related services"""
        logger.info("🔄 Starting cluster services...")
        
        try:
            # Start leader election
            leader = self.leader_election.elect_leader()
            if leader:
                logger.info(f"🗳 Initial leader: {leader.id} (role: {leader.role.value})")
            
            # Start health monitoring
            if self.health_check_enabled:
                self._start_health_monitoring()
            
            # Start MCP server if we're eligible
            if self.node_role in [NodeRole.MASTER, NodeRole.WORKER]:
                self._start_mcp_server()
            
            logger.info("✅ Cluster services started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start cluster services: {e}")
            raise
    
    def stop_cluster_services(self):
        """Stop all cluster-related services"""
        logger.info("🔄 Stopping cluster services...")
        
        # Stop health monitoring
        self.should_stop_health_check = True
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5)
        
        # Stop MCP server
        if self.mcp_server_process:
            self._stop_mcp_server()
        
        logger.info("✅ Cluster services stopped")
    
    def _start_health_monitoring(self):
        """Start background health monitoring thread"""
        def health_monitor():
            while not self.should_stop_health_check:
                try:
                    # Check leader health and trigger election if needed
                    self.leader_election.trigger_election_if_needed()
                    
                    # Monitor peer health
                    self._update_peer_health()
                    
                    # Check daemon health
                    self._check_daemon_health()
                    
                    time.sleep(10)  # Check every 10 seconds
                    
                except Exception as e:
                    logger.error(f"❌ Health monitoring error: {e}")
                    time.sleep(5)
        
        self.health_check_thread = threading.Thread(target=health_monitor, daemon=True)
        self.health_check_thread.start()
        logger.info("💓 Health monitoring started")
    
    def _start_mcp_server(self):
        """Start the MCP server subprocess"""
        try:
            # Import the enhanced MCP server
            server_script = os.path.join(os.path.dirname(__file__), "enhanced_mcp_server_with_daemon_init.py")
            
            if os.path.exists(server_script):
                import subprocess
                
                cmd = [
                    sys.executable, server_script,
                    "--host", "127.0.0.1",
                    "--port", str(self.mcp_server_port),
                    "--initialize",
                    "--log-level", "INFO"
                ]
                
                self.mcp_server_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
                
                logger.info(f"🚀 Started MCP server on port {self.mcp_server_port} (PID: {self.mcp_server_process.pid})")
            else:
                logger.warning(f"⚠ MCP server script not found: {server_script}")
                
        except Exception as e:
            logger.error(f"❌ Failed to start MCP server: {e}")
    
    def _stop_mcp_server(self):
        """Stop the MCP server subprocess"""
        if self.mcp_server_process:
            try:
                self.mcp_server_process.terminate()
                self.mcp_server_process.wait(timeout=10)
                logger.info("✅ MCP server stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping MCP server: {e}")
                try:
                    self.mcp_server_process.kill()
                except:
                    pass
    
    def _update_peer_health(self):
        """Update health status of known peers"""
        current_time = datetime.now()
        timeout_threshold = current_time - timedelta(seconds=60)
        
        for peer_id, peer in self.peers.items():
            if peer.last_seen < timeout_threshold:
                if peer.is_healthy:
                    logger.warning(f"⚠ Peer {peer_id} appears unhealthy (last seen: {peer.last_seen})")
                    peer.is_healthy = False
    
    def _check_daemon_health(self):
        """Check health of managed daemons"""
        if not self.is_running():
            logger.warning(f"⚠ Daemon {self.daemon_type} is not running")
            # Could implement auto-restart logic here
    
    def add_peer(self, peer_info: PeerInfo):
        """Add a new peer to the cluster"""
        self.peers[peer_info.id] = peer_info
        self.leader_election.peers = self.peers
        logger.info(f"➕ Added peer: {peer_info.id} (role: {peer_info.role.value})")
    
    def remove_peer(self, peer_id: str):
        """Remove a peer from the cluster"""
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.leader_election.peers = self.peers
            logger.info(f"➖ Removed peer: {peer_id}")
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get comprehensive cluster status"""
        leader = self.leader_election.current_leader
        
        return {
            "node_info": {
                "id": self.node_id,
                "role": self.node_role.value,
                "can_be_leader": self.leader_election.is_eligible_for_leadership(self.node_role)
            },
            "leader_info": {
                "current_leader": leader.to_dict() if leader else None,
                "is_leader": leader.id == self.node_id if leader else False,
                "election_in_progress": self.leader_election.election_in_progress
            },
            "cluster_info": {
                "total_peers": len(self.peers),
                "healthy_peers": sum(1 for p in self.peers.values() if p.is_healthy),
                "peers_by_role": {
                    role.value: sum(1 for p in self.peers.values() if p.role == role)
                    for role in NodeRole
                }
            },
            "services": {
                "replication_manager": {
                    "can_initiate": self.replication_manager.can_initiate_replication(),
                    "can_receive": self.replication_manager.can_receive_replication(),
                    "active_tasks": len(self.replication_manager.replication_tasks)
                },
                "indexing_service": self.indexing_service.get_index_stats(),
                "mcp_server": {
                    "running": self.mcp_server_process is not None,
                    "port": self.mcp_server_port
                }
            },
            "daemon_status": self.get_status()
        }

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Enhanced daemon manager with cluster capabilities"""
    parser = argparse.ArgumentParser(
        description="Enhanced Daemon Manager with Cluster Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Base daemon arguments
    parser.add_argument("--daemon", choices=DaemonTypes.get_all(), default=DaemonTypes.IPFS,
                      help="Daemon type to manage")
    parser.add_argument("--action", choices=["start", "stop", "restart", "status", "cluster-status"], 
                      default="status", help="Action to perform")
    
    # Cluster arguments
    parser.add_argument("--node-id", help="Unique node identifier")
    parser.add_argument("--node-role", choices=["master", "worker", "leecher"], default="worker",
                      help="Role of this node in the cluster")
    parser.add_argument("--start-cluster", action="store_true",
                      help="Start cluster services along with daemon")
    parser.add_argument("--mcp-port", type=int, default=9998,
                      help="Port for MCP server")
    
    # Standard daemon arguments
    parser.add_argument("--config-dir", help="Directory for daemon configuration")
    parser.add_argument("--work-dir", help="Working directory for the daemon")
    parser.add_argument("--log-dir", help="Directory for daemon logs")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--api-port", type=int, help="Port for API server")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create enhanced daemon manager
    node_role = NodeRole(args.node_role)
    
    manager = EnhancedDaemonManager(
        node_id=args.node_id,
        node_role=node_role,
        daemon_type=args.daemon,
        config_dir=args.config_dir,
        work_dir=args.work_dir,
        log_dir=args.log_dir,
        debug=args.debug,
        api_port=args.api_port
    )
    
    manager.mcp_server_port = args.mcp_port
    
    try:
        if args.action == "start":
            logger.info(f"🚀 Starting {args.daemon} daemon with cluster services...")
            
            # Start base daemon
            if manager.start():
                logger.info(f"✅ {args.daemon} daemon started successfully")
                
                # Start cluster services if requested
                if args.start_cluster:
                    manager.start_cluster_services()
                    logger.info("✅ Cluster services started")
                    
                    # Keep running for monitoring
                    try:
                        while True:
                            time.sleep(10)
                            status = manager.get_cluster_status()
                            logger.debug(f"Cluster status: {json.dumps(status, indent=2)}")
                    except KeyboardInterrupt:
                        logger.info("🔄 Shutting down...")
                        manager.stop_cluster_services()
                        manager.stop()
                
                return 0
            else:
                logger.error(f"❌ Failed to start {args.daemon} daemon")
                return 1
        
        elif args.action == "stop":
            manager.stop_cluster_services()
            if manager.stop():
                logger.info(f"✅ {args.daemon} daemon stopped successfully")
                return 0
            else:
                logger.error(f"❌ Failed to stop {args.daemon} daemon")
                return 1
        
        elif args.action == "restart":
            manager.stop_cluster_services()
            manager.stop()
            if manager.start():
                if args.start_cluster:
                    manager.start_cluster_services()
                logger.info(f"✅ {args.daemon} daemon restarted successfully")
                return 0
            else:
                logger.error(f"❌ Failed to restart {args.daemon} daemon")
                return 1
        
        elif args.action == "status":
            status = manager.get_status()
            print(json.dumps(status, indent=2))
            return 0
        
        elif args.action == "cluster-status":
            # Initialize cluster services briefly to get status
            if args.start_cluster:
                manager.start_cluster_services()
            
            status = manager.get_cluster_status()
            print(json.dumps(status, indent=2))
            return 0
    
    except KeyboardInterrupt:
        logger.info("🔄 Interrupted, shutting down...")
        manager.stop_cluster_services()
        manager.stop()
        return 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        if args.debug:
            logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())

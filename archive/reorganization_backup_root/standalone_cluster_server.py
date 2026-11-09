#!/usr/bin/env python3
"""
Standalone IPFS MCP server with cluster capabilities for containerized deployment.
"""

import asyncio
import os
import sys
import signal
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClusterMCPServer:
    """Standalone MCP server with cluster capabilities."""
    
    def __init__(self):
        self.app = FastAPI(title="IPFS MCP Cluster Server")
        self.node_id = os.getenv('NODE_ID', 'ipfs-mcp-node')
        self.node_role = os.getenv('NODE_ROLE', 'worker')
        self.server_host = os.getenv('SERVER_HOST', '0.0.0.0')
        self.server_port = int(os.getenv('SERVER_PORT', '9998'))
        self.cluster_peers = os.getenv('CLUSTER_PEERS', '').split(',') if os.getenv('CLUSTER_PEERS') else []
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
        # Cluster state
        self.peers = {}
        self.current_leader = None
        self.is_healthy = True
        
        # Configure logging level
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            
        logger.info(f"Initializing cluster server: {self.node_id} ({self.node_role}) on {self.server_host}:{self.server_port}")
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {
                "status": "healthy" if self.is_healthy else "unhealthy",
                "node_id": self.node_id,
                "node_role": self.node_role,
                "timestamp": asyncio.get_event_loop().time()
            }
        
        @self.app.get("/readiness")
        async def readiness():
            """Kubernetes readiness probe."""
            return {
                "ready": self.is_healthy,
                "node_id": self.node_id,
                "cluster_peers": len(self.cluster_peers)
            }
        
        @self.app.get("/cluster/status")
        async def cluster_status():
            """Get cluster status."""
            return {
                "node_id": self.node_id,
                "node_role": self.node_role,
                "peers": list(self.peers.keys()),
                "peer_count": len(self.peers),
                "current_leader": self.current_leader,
                "cluster_peers": self.cluster_peers
            }
        
        @self.app.get("/cluster/leader")
        async def get_leader():
            """Get current cluster leader."""
            # Simple leader election based on role priority
            leader = self._elect_leader()
            return {
                "leader": leader,
                "election_timestamp": asyncio.get_event_loop().time()
            }
        
        @self.app.post("/cluster/peers")
        async def update_peers(peers_data: dict):
            """Update cluster peer list."""
            try:
                if isinstance(peers_data, list):
                    peers_list = peers_data
                else:
                    peers_list = peers_data.get('peers', [])
                
                # Update peer list
                self.peers = {}
                for peer in peers_list:
                    if isinstance(peer, dict) and 'id' in peer:
                        self.peers[peer['id']] = peer
                
                logger.info(f"Updated peer list: {list(self.peers.keys())}")
                return {
                    "success": True,
                    "peer_count": len(self.peers),
                    "peers": list(self.peers.keys())
                }
            except Exception as e:
                logger.error(f"Failed to update peers: {e}")
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/replication/status")
        async def replication_status():
            """Get replication status."""
            return {
                "node_id": self.node_id,
                "can_initiate": self.node_role == "master",
                "can_receive": self.node_role in ["master", "worker"],
                "active_replications": 0
            }
        
        @self.app.post("/replication/replicate")
        async def replicate_content(request_data: dict):
            """Replicate content to target peers."""
            if self.node_role != "master":
                raise HTTPException(status_code=403, detail="Only master nodes can initiate replication")
            
            cid = request_data.get('cid')
            target_peers = request_data.get('target_peers', [])
            
            if not cid:
                raise HTTPException(status_code=400, detail="CID is required")
            
            # Simulate replication
            logger.info(f"Replicating CID {cid} to peers: {target_peers}")
            
            return {
                "success": True,
                "cid": cid,
                "target_peers": target_peers,
                "replication_id": f"repl_{asyncio.get_event_loop().time()}"
            }
        
        @self.app.get("/indexing/stats")
        async def indexing_stats():
            """Get indexing statistics."""
            return {
                "node_id": self.node_id,
                "can_write": self.node_role == "master",
                "can_read": True,
                "index_count": 0,
                "embeddings_count": 0
            }
        
        @self.app.post("/indexing/data")
        async def add_index_data(request_data: dict):
            """Add index data (master only)."""
            if self.node_role != "master":
                raise HTTPException(status_code=403, detail="Only master nodes can write index data")
            
            index_type = request_data.get('index_type')
            key = request_data.get('key')
            data = request_data.get('data')
            
            if not all([index_type, key, data]):
                raise HTTPException(status_code=400, detail="index_type, key, and data are required")
            
            logger.info(f"Adding index data: {index_type}/{key}")
            
            return {
                "success": True,
                "index_type": index_type,
                "key": key,
                "timestamp": asyncio.get_event_loop().time()
            }
        
        @self.app.get("/indexing/search/{index_type}")
        async def search_index(index_type: str, query_data: dict):
            """Search index data."""
            logger.info(f"Searching index: {index_type}")
            
            return {
                "success": True,
                "index_type": index_type,
                "results": [],
                "result_count": 0
            }
    
    def _elect_leader(self):
        """Simple leader election based on role priority."""
        # Add self to peers for election
        self_peer = {
            "id": self.node_id,
            "role": self.node_role,
            "address": self.server_host,
            "port": self.server_port
        }
        
        all_peers = list(self.peers.values()) + [self_peer]
        
        # Role priority: master > worker > leecher
        role_priority = {"master": 3, "worker": 2, "leecher": 1}
        
        # Sort by role priority (desc) then by node_id (asc) for deterministic election
        eligible_peers = sorted(
            all_peers,
            key=lambda p: (role_priority.get(p.get('role', 'leecher'), 0), p['id']),
            reverse=True
        )
        
        if eligible_peers:
            leader = eligible_peers[0]
            self.current_leader = leader['id']
            logger.info(f"Elected leader: {leader['id']} ({leader.get('role', 'unknown')})")
            return leader
        
        return None
    
    async def start(self):
        """Start the cluster server."""
        logger.info(f"Starting cluster server on {self.server_host}:{self.server_port}")
        
        # Initialize cluster state
        self.is_healthy = True
        
        # Parse cluster peers
        for peer in self.cluster_peers:
            if peer and ':' in peer:
                host, port = peer.rsplit(':', 1)
                peer_id = f"peer-{host}-{port}"
                self.peers[peer_id] = {
                    "id": peer_id,
                    "role": "worker",  # Default role
                    "address": host,
                    "port": int(port)
                }
        
        logger.info(f"Initialized with {len(self.peers)} cluster peers")
        
        # Start the server
        config = uvicorn.Config(
            self.app,
            host=self.server_host,
            port=self.server_port,
            log_level="debug" if self.debug else "info",
            access_log=self.debug
        )
        
        server = uvicorn.Server(config)
        await server.serve()

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

async def main():
    """Main function."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start server
    server = ClusterMCPServer()
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)

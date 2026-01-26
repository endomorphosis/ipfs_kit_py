#!/usr/bin/env python3
"""
Enhanced MCP Server with Environment-Based Configuration
========================================================

Enhanced version of the MCP server that supports configuration via environment
variables for containerized deployments.
"""

import os
import sys
import argparse
import anyio
import logging
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_daemon_manager_with_cluster import EnhancedDaemonManager, NodeRole
from enhanced_mcp_server_with_config import create_mcp_server

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContainerizedMCPServer:
    """MCP Server optimized for containerized deployments"""
    
    def __init__(self):
        self.config = self._load_config()
        self.daemon_manager = None
        self.server = None
    
    def _load_config(self):
        """Load configuration from environment variables with fallbacks"""
        return {
            # Node configuration
            'node_id': os.getenv('NODE_ID', 'ipfs-mcp-node'),
            'node_role': os.getenv('NODE_ROLE', 'worker'),
            'daemon_type': os.getenv('DAEMON_TYPE', 'ipfs'),
            
            # Server configuration
            'host': os.getenv('SERVER_HOST', '0.0.0.0'),
            'port': int(os.getenv('SERVER_PORT', '9998')),
            'workers': int(os.getenv('SERVER_WORKERS', '1')),
            'debug': os.getenv('DEBUG', 'false').lower() == 'true',
            
            # Cluster configuration
            'cluster_peers': os.getenv('CLUSTER_PEERS', '').split(',') if os.getenv('CLUSTER_PEERS') else [],
            'cluster_secret': os.getenv('CLUSTER_SECRET', 'default-cluster-secret'),
            'enable_discovery': os.getenv('ENABLE_DISCOVERY', 'true').lower() == 'true',
            
            # Storage configuration
            'data_dir': os.getenv('DATA_DIR', '/app/data'),
            'ipfs_data_dir': os.getenv('IPFS_DATA_DIR', '/app/ipfs_data'),
            'log_dir': os.getenv('LOG_DIR', '/app/logs'),
            
            # Performance configuration
            'max_connections': int(os.getenv('MAX_CONNECTIONS', '100')),
            'request_timeout': int(os.getenv('REQUEST_TIMEOUT', '30')),
            'keepalive_timeout': int(os.getenv('KEEPALIVE_TIMEOUT', '5')),
            
            # Health check configuration
            'health_check_interval': int(os.getenv('HEALTH_CHECK_INTERVAL', '30')),
            'heartbeat_interval': int(os.getenv('HEARTBEAT_INTERVAL', '10')),
            
            # Feature flags
            'enable_replication': os.getenv('ENABLE_REPLICATION', 'true').lower() == 'true',
            'enable_indexing': os.getenv('ENABLE_INDEXING', 'true').lower() == 'true',
            'enable_vfs': os.getenv('ENABLE_VFS', 'true').lower() == 'true',
            'enable_metrics': os.getenv('ENABLE_METRICS', 'false').lower() == 'true',
        }
    
    def _validate_config(self):
        """Validate configuration values"""
        errors = []
        
        # Validate node role
        try:
            NodeRole(self.config['node_role'])
        except ValueError:
            errors.append(f"Invalid node role: {self.config['node_role']}")
        
        # Validate port range
        if not (1 <= self.config['port'] <= 65535):
            errors.append(f"Invalid port: {self.config['port']}")
        
        # Validate directories exist or can be created
        for dir_key in ['data_dir', 'ipfs_data_dir', 'log_dir']:
            dir_path = self.config[dir_key]
            try:
                os.makedirs(dir_path, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create {dir_key} directory {dir_path}: {e}")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def _setup_directories(self):
        """Ensure required directories exist"""
        dirs = [
            self.config['data_dir'],
            self.config['ipfs_data_dir'],
            self.config['log_dir'],
        ]
        
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Ensured directory exists: {dir_path}")
    
    def _create_daemon_manager(self):
        """Create and configure the daemon manager"""
        try:
            node_role = NodeRole(self.config['node_role'])
            
            self.daemon_manager = EnhancedDaemonManager(
                node_id=self.config['node_id'],
                node_role=node_role,
                daemon_type=self.config['daemon_type']
            )
            
            # Configure cluster peers
            if self.config['cluster_peers']:
                logger.info(f"Configuring cluster peers: {self.config['cluster_peers']}")
                # In a real implementation, parse peer URLs and add them
                # For now, we'll add this as metadata
                self.daemon_manager._cluster_peers = self.config['cluster_peers']
            
            logger.info(f"Created daemon manager for {self.config['node_id']} ({self.config['node_role']})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create daemon manager: {e}")
            return False
    
    async def _wait_for_dependencies(self):
        """Wait for external dependencies to be ready"""
        if self.config['cluster_peers']:
            import httpx
            
            logger.info("Waiting for cluster peers to be ready...")
            max_wait = 300  # 5 minutes
            start_time = anyio.current_time()
            
            while (anyio.current_time() - start_time) < max_wait:
                ready_peers = []
                
                async with httpx.AsyncClient() as client:
                    for peer in self.config['cluster_peers']:
                        if not peer.strip():
                            continue
                            
                        try:
                            peer_url = f"http://{peer}/health"
                            response = await client.get(peer_url, timeout=5)
                            if response.status_code == 200:
                                ready_peers.append(peer)
                        except Exception:
                            pass
                
                if len(ready_peers) >= len(self.config['cluster_peers']) // 2:
                    logger.info(f"Sufficient peers ready: {ready_peers}")
                    return True
                
                logger.info(f"Waiting for peers... Ready: {len(ready_peers)}/{len(self.config['cluster_peers'])}")
                await anyio.sleep(10)
            
            logger.warning("Timeout waiting for cluster peers, proceeding anyway...")
        
        return True
    
    async def start(self):
        """Start the MCP server"""
        try:
            logger.info(f"Starting containerized MCP server...")
            logger.info(f"Configuration: {self.config}")
            
            # Validate configuration
            self._validate_config()
            
            # Setup directories
            self._setup_directories()
            
            # Create daemon manager
            if not self._create_daemon_manager():
                raise RuntimeError("Failed to create daemon manager")
            
            # Wait for dependencies if in cluster mode
            if self.config['cluster_peers']:
                await self._wait_for_dependencies()
            
            # Create and configure the MCP server
            self.server = create_mcp_server(
                daemon_manager=self.daemon_manager,
                host=self.config['host'],
                port=self.config['port'],
                debug=self.config['debug']
            )
            
            # Add health check endpoint
            @self.server.app.get("/health")
            async def health_check():
                """Kubernetes-compatible health check endpoint"""
                try:
                    status = {
                        "status": "healthy",
                        "node_id": self.config['node_id'],
                        "node_role": self.config['node_role'],
                        "timestamp": anyio.current_time(),
                        "cluster_peers": len(self.config['cluster_peers']),
                        "services": {
                            "daemon_manager": bool(self.daemon_manager),
                            "replication": self.config['enable_replication'],
                            "indexing": self.config['enable_indexing'],
                            "vfs": self.config['enable_vfs']
                        }
                    }
                    
                    if self.daemon_manager:
                        try:
                            cluster_status = self.daemon_manager.get_cluster_status()
                            status["cluster_info"] = cluster_status.get("cluster_info", {})
                        except Exception as e:
                            logger.warning(f"Failed to get cluster status: {e}")
                    
                    return status
                    
                except Exception as e:
                    logger.error(f"Health check failed: {e}")
                    return {"status": "unhealthy", "error": str(e)}, 500
            
            # Add readiness check endpoint
            @self.server.app.get("/ready")
            async def readiness_check():
                """Kubernetes-compatible readiness check endpoint"""
                try:
                    # Check if all essential services are ready
                    ready = (
                        self.daemon_manager is not None and
                        (not self.config['cluster_peers'] or len(self.config['cluster_peers']) > 0)
                    )
                    
                    if ready:
                        return {"status": "ready", "node_id": self.config['node_id']}
                    else:
                        return {"status": "not_ready", "node_id": self.config['node_id']}, 503
                        
                except Exception as e:
                    logger.error(f"Readiness check failed: {e}")
                    return {"status": "not_ready", "error": str(e)}, 503
            
            # Start the server
            logger.info(f"Starting server on {self.config['host']}:{self.config['port']}")
            await self.server.start()
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
    
    async def stop(self):
        """Stop the MCP server"""
        try:
            logger.info("Stopping MCP server...")
            
            if self.server:
                await self.server.stop()
            
            if self.daemon_manager:
                # Cleanup daemon manager resources
                pass
            
            logger.info("MCP server stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping server: {e}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Containerized IPFS MCP Server')
    
    parser.add_argument('--host', default=os.getenv('SERVER_HOST', '0.0.0.0'),
                       help='Server host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=int(os.getenv('SERVER_PORT', '9998')),
                       help='Server port (default: 9998)')
    parser.add_argument('--node-id', default=os.getenv('NODE_ID', 'ipfs-mcp-node'),
                       help='Node ID (default: ipfs-mcp-node)')
    parser.add_argument('--role', default=os.getenv('NODE_ROLE', 'worker'),
                       choices=['master', 'worker', 'leecher'],
                       help='Node role (default: worker)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--initialize', action='store_true',
                       help='Initialize cluster on startup')
    
    return parser.parse_args()


async def main():
    """Main entry point"""
    try:
        args = parse_args()
        
        # Override config with command line arguments
        if args.host != '0.0.0.0':
            os.environ['SERVER_HOST'] = args.host
        if args.port != 9998:
            os.environ['SERVER_PORT'] = str(args.port)
        if args.node_id != 'ipfs-mcp-node':
            os.environ['NODE_ID'] = args.node_id
        if args.role != 'worker':
            os.environ['NODE_ROLE'] = args.role
        if args.debug:
            os.environ['DEBUG'] = 'true'
        
        # Create and start server
        server = ContainerizedMCPServer()
        
        # Handle graceful shutdown
        import signal
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            try:
                anyio.from_thread.run(server.stop)
            except RuntimeError:
                anyio.run(server.stop)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Start server
        await server.start()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)

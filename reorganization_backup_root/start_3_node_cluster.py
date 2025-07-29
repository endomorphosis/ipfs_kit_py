#!/usr/bin/env python3
"""
Start a 3-node cluster locally without Docker for testing cluster functionality.
"""

import asyncio
import subprocess
import sys
import time
import os
import signal
import logging
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalClusterManager:
    def __init__(self):
        self.processes = []
        self.master_port = 8998
        self.worker1_port = 8999
        self.worker2_port = 9000
        
    async def start_node(self, node_id, role, port, peers=[]):
        """Start a single node with specified configuration."""
        env = os.environ.copy()
        env.update({
            'NODE_ID': node_id,
            'NODE_ROLE': role,
            'SERVER_HOST': '127.0.0.1',
            'SERVER_PORT': str(port),
            'CLUSTER_PEERS': ','.join(peers) if peers else '',
            'LOG_LEVEL': 'INFO',
            'DEBUG': 'true',
            'ENABLE_REPLICATION': 'true',
            'ENABLE_INDEXING': 'true',
            'ENABLE_VFS': 'true'
        })
        
        logger.info(f"Starting {role} node '{node_id}' on port {port}")
        
        process = subprocess.Popen(
            [sys.executable, 'standalone_cluster_server.py'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.processes.append({
            'process': process,
            'node_id': node_id,
            'role': role,
            'port': port
        })
        
        return process
    
    async def wait_for_health(self, port, max_retries=10):
        """Wait for a node to become healthy."""
        url = f"http://127.0.0.1:{port}/health"
        
        for i in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Node on port {port} is healthy")
                        return True
            except Exception as e:
                logger.debug(f"Health check attempt {i+1}/{max_retries} failed for port {port}: {e}")
                await asyncio.sleep(2)
        
        logger.error(f"Node on port {port} failed to become healthy")
        return False
    
    async def start_cluster(self):
        """Start the complete 3-node cluster."""
        logger.info("Starting 3-node IPFS MCP cluster...")
        
        # Define cluster peers for each node
        peers_master = [f"127.0.0.1:{self.worker1_port}", f"127.0.0.1:{self.worker2_port}"]
        peers_worker1 = [f"127.0.0.1:{self.master_port}", f"127.0.0.1:{self.worker2_port}"]
        peers_worker2 = [f"127.0.0.1:{self.master_port}", f"127.0.0.1:{self.worker1_port}"]
        
        # Start master node
        await self.start_node("master-1", "master", self.master_port, peers_master)
        await asyncio.sleep(3)  # Give master time to initialize
        
        # Start worker nodes
        await self.start_node("worker-1", "worker", self.worker1_port, peers_worker1)
        await asyncio.sleep(2)
        await self.start_node("worker-2", "worker", self.worker2_port, peers_worker2)
        
        # Wait for all nodes to become healthy
        logger.info("Waiting for all nodes to become healthy...")
        await asyncio.sleep(5)  # Initial startup time
        
        health_results = await asyncio.gather(
            self.wait_for_health(self.master_port),
            self.wait_for_health(self.worker1_port),
            self.wait_for_health(self.worker2_port),
            return_exceptions=True
        )
        
        healthy_nodes = sum(1 for result in health_results if result is True)
        logger.info(f"Cluster startup complete: {healthy_nodes}/3 nodes healthy")
        
        return healthy_nodes == 3
    
    async def test_cluster_functionality(self):
        """Test basic cluster functionality."""
        logger.info("Testing cluster functionality...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Test health endpoints
                logger.info("Testing health endpoints...")
                for port in [self.master_port, self.worker1_port, self.worker2_port]:
                    response = await client.get(f"http://127.0.0.1:{port}/health")
                    logger.info(f"Port {port} health: {response.status_code}")
                
                # Test cluster status on master
                logger.info("Testing cluster status...")
                try:
                    response = await client.get(f"http://127.0.0.1:{self.master_port}/cluster/status")
                    if response.status_code == 200:
                        status = response.json()
                        logger.info(f"Cluster status: {status}")
                    else:
                        logger.warning(f"Cluster status returned {response.status_code}")
                except Exception as e:
                    logger.warning(f"Cluster status endpoint not available: {e}")
                
                # Test leader election
                logger.info("Testing leader election...")
                try:
                    response = await client.get(f"http://127.0.0.1:{self.master_port}/cluster/leader")
                    if response.status_code == 200:
                        leader = response.json()
                        logger.info(f"Current leader: {leader}")
                    else:
                        logger.warning(f"Leader election returned {response.status_code}")
                except Exception as e:
                    logger.warning(f"Leader election endpoint not available: {e}")
                
                logger.info("✅ Basic cluster functionality test completed")
                return True
                
        except Exception as e:
            logger.error(f"Cluster functionality test failed: {e}")
            return False
    
    async def show_cluster_logs(self, duration=10):
        """Show logs from all nodes for debugging."""
        logger.info(f"Showing cluster logs for {duration} seconds...")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            for node_info in self.processes:
                process = node_info['process']
                node_id = node_info['node_id']
                
                # Read available stdout
                try:
                    stdout_data = process.stdout.read(1024)
                    if stdout_data:
                        logger.info(f"[{node_id}] STDOUT: {stdout_data.strip()}")
                except:
                    pass
                
                # Read available stderr
                try:
                    stderr_data = process.stderr.read(1024)
                    if stderr_data:
                        logger.info(f"[{node_id}] STDERR: {stderr_data.strip()}")
                except:
                    pass
            
            await asyncio.sleep(1)
    
    def stop_cluster(self):
        """Stop all cluster nodes."""
        logger.info("Stopping cluster...")
        
        for node_info in self.processes:
            process = node_info['process']
            node_id = node_info['node_id']
            
            logger.info(f"Stopping {node_id}...")
            try:
                process.terminate()
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {node_id}...")
                process.kill()
                process.wait()
            except Exception as e:
                logger.error(f"Error stopping {node_id}: {e}")
        
        self.processes.clear()
        logger.info("Cluster stopped")

async def main():
    """Main function to run the cluster test."""
    cluster = LocalClusterManager()
    
    try:
        # Start the cluster
        success = await cluster.start_cluster()
        if not success:
            logger.error("Failed to start cluster")
            return False
        
        logger.info("✅ Cluster started successfully!")
        
        # Test functionality
        await cluster.test_cluster_functionality()
        
        # Keep cluster running for manual testing
        logger.info("Cluster is running. You can now test it manually:")
        logger.info(f"  Master node:  http://127.0.0.1:{cluster.master_port}/health")
        logger.info(f"  Worker 1:     http://127.0.0.1:{cluster.worker1_port}/health")
        logger.info(f"  Worker 2:     http://127.0.0.1:{cluster.worker2_port}/health")
        logger.info("")
        logger.info("Press Ctrl+C to stop the cluster")
        
        # Wait for interruption
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        
        return True
        
    except Exception as e:
        logger.error(f"Cluster test failed: {e}")
        return False
    
    finally:
        cluster.stop_cluster()

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)

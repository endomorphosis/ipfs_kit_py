#!/usr/bin/env python3
"""
Multi-Region High Availability MCP Server Example

This script demonstrates how to set up and test a multi-region HA deployment
of the MCP server with automatic failover capabilities. It creates multiple 
MCP server instances across different "regions" (simulated on localhost) and
tests failover scenarios.

Usage:
    python ha_multi_region_example.py [--redis-url REDIS_URL]
"""

import os
import sys
import json
import time
import uuid
import signal
import logging
import argparse
import tempfile
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ha-multi-region-example")

# Try importing required modules
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp not available. Install with: pip install aiohttp")

SCRIPT_DIR = Path(__file__).parent.resolve()

def create_ha_config(temp_dir: str, local_node_id: str) -> str:
    """
    Create a High Availability configuration file for multiple regions.
    
    Args:
        temp_dir: Directory to store the configuration
        local_node_id: ID for the local node
        
    Returns:
        Path to the created configuration file
    """
    # Define ports for different nodes across regions
    ports = {
        "us-west": {
            "primary": 8001,
            "secondary": 8002,
            "read_replica": 8003
        },
        "us-east": {
            "primary": 8011,
            "secondary": 8012,
            "read_replica": 8013
        },
        "eu-west": {
            "primary": 8021,
            "secondary": 8022
        }
    }
    
    # Create nodes configuration
    nodes = []
    for region, region_ports in ports.items():
        for role, port in region_ports.items():
            node_id = f"{region}-{role}-{uuid.uuid4()}"
            if port == 8001:  # This will be our local node (us-west primary)
                node_id = local_node_id
            
            nodes.append({
                "id": node_id,
                "host": "127.0.0.1",
                "port": port,
                "role": role,
                "region": region,
                "zone": f"{region}-{role}-zone",
                "api_endpoint": "/api",
                "admin_endpoint": "/admin",
                "metrics_endpoint": "/metrics",
                "max_connections": 1000,
                "max_memory_gb": 4.0,
                "cpu_cores": 2
            })
    
    # Create HA configuration
    ha_config = {
        "ha_config": {
            "id": str(uuid.uuid4()),
            "name": "Multi-Region HA Example",
            "description": "Example multi-region HA setup for MCP Server",
            "active": True,
            "failover_strategy": "automatic",
            "replication_mode": "asynchronous",
            "consistency_level": "eventual",
            "heartbeat_interval_ms": 2000,  # Faster for demo purposes
            "health_check_interval_ms": 5000,  # Faster for demo purposes
            "failover_timeout_ms": 10000,  # Faster for demo purposes
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
        "nodes": nodes
    }
    
    # Write configuration to file
    config_path = os.path.join(temp_dir, "ha_config.json")
    with open(config_path, 'w') as f:
        json.dump(ha_config, f, indent=2)
    
    logger.info(f"Created HA configuration file at {config_path}")
    return config_path

class MCPServerInstance:
    """Class representing a running MCP server instance."""
    
    def __init__(self, node_id: str, region: str, role: str, 
                 port: int, config_path: str, redis_url: Optional[str] = None):
        """
        Initialize a server instance.
        
        Args:
            node_id: Unique identifier for this node
            region: Region identifier (e.g., us-west)
            role: Node role (e.g., primary, secondary)
            port: Port to run the server on
            config_path: Path to the HA configuration file
            redis_url: Optional Redis URL for state coordination
        """
        self.node_id = node_id
        self.region = region
        self.role = role
        self.port = port
        self.config_path = config_path
        self.redis_url = redis_url
        self.process = None
        self.log_path = f"mcp_server_{region}_{role}_{port}.log"
        self.health_url = f"http://127.0.0.1:{port}/api/v0/ha/status"
    
    async def start(self) -> bool:
        """Start the MCP server instance."""
        if self.process:
            logger.warning(f"Server on port {self.port} is already running")
            return True
        
        logger.info(f"Starting MCP server on port {self.port} (Region: {self.region}, Role: {self.role})")
        
        try:
            # Create command with environment variables
            enhanced_script = os.path.join(SCRIPT_DIR, "enhanced_mcp_server.py")
            if not os.path.exists(enhanced_script):
                enhanced_script = os.path.join(SCRIPT_DIR, "direct_mcp_server.py")
                if not os.path.exists(enhanced_script):
                    logger.error("Could not find MCP server script")
                    return False
            
            env = os.environ.copy()
            env["MCP_HA_NODE_ID"] = self.node_id
            env["MCP_HA_CONFIG_PATH"] = self.config_path
            env["PORT"] = str(self.port)
            if self.redis_url:
                env["MCP_HA_REDIS_URL"] = self.redis_url
            
            # Start the server process
            with open(self.log_path, "w") as log_file:
                self.process = subprocess.Popen(
                    [sys.executable, enhanced_script],
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )
            
            logger.info(f"Started server on port {self.port} with PID {self.process.pid}")
            
            # Wait for server to initialize (quick health check)
            if not await self.wait_for_ready(timeout=20):
                logger.error(f"Server on port {self.port} did not initialize properly")
                await self.stop()
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to start server on port {self.port}: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the MCP server instance."""
        if not self.process:
            logger.warning(f"Server on port {self.port} is not running")
            return True
        
        logger.info(f"Stopping MCP server on port {self.port} (PID: {self.process.pid})")
        
        try:
            # Try graceful shutdown first
            self.process.terminate()
            
            # Wait for process to terminate
            try:
                self.process.wait(timeout=5)
                logger.info(f"Server on port {self.port} terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                logger.warning(f"Server on port {self.port} did not terminate, forcing kill")
                self.process.kill()
                self.process.wait(timeout=2)
            
            self.process = None
            return True
        
        except Exception as e:
            logger.error(f"Failed to stop server on port {self.port}: {e}")
            return False
    
    async def wait_for_ready(self, timeout: int = 10) -> bool:
        """
        Wait for the server to be ready.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            True if the server is ready, False otherwise
        """
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not available, cannot check server readiness")
            # Sleep a bit to give the server time to start
            await asyncio.sleep(5)
            return True
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.health_url, timeout=2) as response:
                        if response.status == 200:
                            logger.info(f"Server on port {self.port} is ready")
                            return True
            except aiohttp.ClientConnectorError:
                pass  # Server not ready yet
            except asyncio.TimeoutError:
                pass  # Server not responding yet
            except Exception as e:
                logger.warning(f"Error checking server health: {e}")
            
            # Try again after a short delay
            await asyncio.sleep(1)
        
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the server instance.
        
        Returns:
            Status information or empty dict if unreachable
        """
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not available, cannot get server status")
            return {}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.health_url, timeout=2) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Server on port {self.port} returned status {response.status}")
                        return {}
        except Exception as e:
            logger.debug(f"Error getting status for server on port {self.port}: {e}")
            return {}
    
    def is_running(self) -> bool:
        """Check if the server process is running."""
        if not self.process:
            return False
        
        # Check if the process is still running
        return self.process.poll() is None

class MultiRegionHAExample:
    """Example of multi-region HA setup for MCP server."""
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the example.
        
        Args:
            redis_url: Optional Redis URL for state coordination
        """
        self.redis_url = redis_url
        self.temp_dir = None  # Will be set in setup()
        self.servers: Dict[str, MCPServerInstance] = {}  # name -> instance
        self.primary_region = "us-west"
        self.standby_regions = ["us-east", "eu-west"]
        self.config_path = None  # Will be set in setup()
        self.local_node_id = f"local-node-{uuid.uuid4()}"
    
    async def setup(self) -> bool:
        """
        Set up the multi-region environment.
        
        Returns:
            True if setup was successful, False otherwise
        """
        try:
            # Create temporary directory for configuration and data
            self.temp_dir = tempfile.mkdtemp(prefix="mcp_ha_example_")
            logger.info(f"Created temporary directory: {self.temp_dir}")
            
            # Create HA configuration
            self.config_path = create_ha_config(self.temp_dir, self.local_node_id)
            
            # Parse the config to get node details
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Create server instances based on config
            for node in config["nodes"]:
                # Parse node details
                node_id = node["id"]
                region = node["region"]
                role = node["role"]
                port = node["port"]
                
                # Create a distinct name for this server
                server_name = f"{region}-{role}"
                
                # Create server instance
                server = MCPServerInstance(
                    node_id=node_id,
                    region=region,
                    role=role,
                    port=port,
                    config_path=self.config_path,
                    redis_url=self.redis_url
                )
                
                self.servers[server_name] = server
            
            logger.info(f"Set up {len(self.servers)} server instances")
            return True
        
        except Exception as e:
            logger.error(f"Error during setup: {e}")
            return False
    
    async def start_servers(self, region: Optional[str] = None) -> bool:
        """
        Start server instances, optionally filtered by region.
        
        Args:
            region: Optional region to filter by
            
        Returns:
            True if all servers were started successfully, False otherwise
        """
        servers_to_start = []
        
        for name, server in self.servers.items():
            if region is None or server.region == region:
                servers_to_start.append(server)
        
        logger.info(f"Starting {len(servers_to_start)} server instances" + 
                   (f" in region {region}" if region else ""))
        
        # Start servers in parallel
        start_results = await asyncio.gather(
            *[server.start() for server in servers_to_start],
            return_exceptions=True
        )
        
        # Check if all servers started successfully
        success = all(result is True for result in start_results)
        if not success:
            logger.error("Not all servers started successfully")
        
        return success
    
    async def stop_servers(self, region: Optional[str] = None) -> bool:
        """
        Stop server instances, optionally filtered by region.
        
        Args:
            region: Optional region to filter by
            
        Returns:
            True if all servers were stopped successfully, False otherwise
        """
        servers_to_stop = []
        
        for name, server in self.servers.items():
            if region is None or server.region == region:
                servers_to_stop.append(server)
        
        logger.info(f"Stopping {len(servers_to_stop)} server instances" + 
                   (f" in region {region}" if region else ""))
        
        # Stop servers in parallel
        stop_results = await asyncio.gather(
            *[server.stop() for server in servers_to_stop],
            return_exceptions=True
        )
        
        # Check if all servers stopped successfully
        success = all(result is True for result in stop_results)
        if not success:
            logger.error("Not all servers stopped successfully")
        
        return success
    
    async def get_cluster_state(self) -> Dict[str, Any]:
        """
        Get the current state of the HA cluster.
        
        Returns:
            Cluster state information or empty dict if unreachable
        """
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not available, cannot get cluster state")
            return {}
        
        # Try to get cluster state from primary region's primary node
        primary_server = self.servers.get(f"{self.primary_region}-primary")
        if not primary_server:
            logger.error(f"Primary server for region {self.primary_region} not found")
            return {}
        
        try:
            cluster_state_url = f"http://127.0.0.1:{primary_server.port}/api/v0/ha/cluster/state"
            async with aiohttp.ClientSession() as session:
                async with session.get(cluster_state_url, timeout=5) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Failed to get cluster state: {response.status}")
                        return {}
        except Exception as e:
            logger.warning(f"Error getting cluster state: {e}")
            
            # If primary region fails, try standby regions
            for region in self.standby_regions:
                standby_server = self.servers.get(f"{region}-primary")
                if not standby_server:
                    continue
                
                try:
                    cluster_state_url = f"http://127.0.0.1:{standby_server.port}/api/v0/ha/cluster/state"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(cluster_state_url, timeout=5) as response:
                            if response.status == 200:
                                return await response.json()
                except Exception:
                    pass  # Try next region
            
            # If all regions fail, return empty dict
            return {}
    
    async def trigger_region_failure(self, region: str) -> bool:
        """
        Simulate a region failure by stopping all servers in the region.
        
        Args:
            region: Region to simulate failure for
            
        Returns:
            True if the region was stopped successfully, False otherwise
        """
        logger.info(f"Simulating failure of region {region}")
        
        # Stop all servers in the region
        success = await self.stop_servers(region)
        
        if success:
            logger.info(f"Region {region} is now offline")
        else:
            logger.error(f"Failed to stop all servers in region {region}")
        
        return success
    
    async def monitor_failover(self, timeout: int = 120) -> bool:
        """
        Monitor the cluster for failover events.
        
        Args:
            timeout: Maximum time to wait for failover in seconds
            
        Returns:
            True if failover was detected, False otherwise
        """
        logger.info(f"Monitoring for failover events (timeout: {timeout}s)")
        
        start_time = time.time()
        initial_state = await self.get_cluster_state()
        
        if not initial_state:
            logger.error("Failed to get initial cluster state")
            return False
        
        # Extract active regions from initial state
        active_regions = initial_state.get("active_regions", [])
        logger.info(f"Initial active regions: {active_regions}")
        
        while time.time() - start_time < timeout:
            # Get current state
            current_state = await self.get_cluster_state()
            if not current_state:
                logger.warning("Failed to get current cluster state, retrying...")
                await asyncio.sleep(5)
                continue
            
            # Extract active regions from current state
            current_active_regions = current_state.get("active_regions", [])
            
            # Check if active regions have changed
            if current_active_regions and current_active_regions != active_regions:
                logger.info(f"Failover detected! Active regions changed from {active_regions} to {current_active_regions}")
                return True
            
            # Check every 5 seconds
            await asyncio.sleep(5)
        
        logger.warning(f"No failover detected within {timeout} seconds")
        return False
    
    async def check_all_server_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Check the status of all server instances.
        
        Returns:
            Dictionary mapping server names to their status
        """
        logger.info("Checking status of all server instances")
        
        result = {}
        for name, server in self.servers.items():
            # Check if server is running
            is_running = server.is_running()
            
            # Get server status if running
            status = await server.get_status() if is_running else {}
            
            result[name] = {
                "running": is_running,
                "status": status
            }
        
        return result
    
    async def run_failover_test(self) -> bool:
        """
        Run a test to demonstrate automatic failover.
        
        Returns:
            True if the test was successful, False otherwise
        """
        logger.info("Running automatic failover test")
        
        try:
            # Start all servers
            logger.info("Starting all servers")
            if not await self.start_servers():
                logger.error("Failed to start servers")
                return False
            
            # Wait for cluster to stabilize
            logger.info("Waiting for cluster to stabilize (30s)")
            await asyncio.sleep(30)
            
            # Check initial cluster state
            initial_state = await self.get_cluster_state()
            if not initial_state:
                logger.error("Failed to get initial cluster state")
                return False
            
            logger.info(f"Initial active regions: {initial_state.get('active_regions', [])}")
            
            # Start monitoring for failover in the background
            monitor_task = asyncio.create_task(self.monitor_failover(timeout=120))
            
            # Simulate failure of primary region
            logger.info(f"Simulating failure of primary region: {self.primary_region}")
            await self.trigger_region_failure(self.primary_region)
            
            # Wait for failover to be detected
            failover_detected = await monitor_task
            
            if failover_detected:
                logger.info("Failover test succeeded!")
                
                # Get final cluster state
                final_state = await self.get_cluster_state()
                if final_state:
                    logger.info(f"Final active regions: {final_state.get('active_regions', [])}")
                
                return True
            else:
                logger.error("Failover test failed: No failover detected")
                return False
        
        except Exception as e:
            logger.error(f"Error running failover test: {e}")
            return False
        finally:
            # Ensure all servers are stopped
            await self.stop_servers()
    
    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")
        
        # Clean up temporary directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Removed temporary directory: {self.temp_dir}")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Multi-Region HA Example for MCP Server")
    parser.add_argument("--redis-url", help="Redis URL for distributed state (e.g., redis://localhost:6379/0)")
    args = parser.parse_args()
    
    # Initialize the example
    example = MultiRegionHAExample(redis_url=args.redis_url)
    
    try:
        # Set up the environment
        logger.info("Setting up multi-region environment")
        if not await example.setup():
            logger.error("Failed to set up environment")
            return 1
        
        # Run the failover test
        logger.info("Starting failover test")
        success = await example.run_failover_test()
        
        if success:
            logger.info("Failover test completed successfully!")
            return 0
        else:
            logger.error("Failover test failed")
            return 1
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 130
    finally:
        # Clean up
        example.cleanup()

if __name__ == "__main__":
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *args: sys.exit(130))
    
    # Run the example
    sys.exit(asyncio.run(main()))
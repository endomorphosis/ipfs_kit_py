"""
High Availability Integration Module for MCP Server.

This module integrates the High Availability Architecture components
with the MCP server, providing multi-region deployment, automatic failover,
load balancing, and replication and consistency features.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import aiohttp
from fastapi import FastAPI
from pydantic import BaseModel

from ipfs_kit_py.mcp.ha.service import HighAvailabilityService
from ipfs_kit_py.mcp.ha.replication.consistency import (
    ConsistencyService,
    ReplicationConfig,
    ConsistencyModel,
    ReplicationStrategy,
    ConflictResolutionStrategy
)
from ipfs_kit_py.mcp.ha.replication.router import register_with_app

# Configure logging
logger = logging.getLogger(__name__)


class HAConfig(BaseModel):
    """Configuration for High Availability."""

    enabled: bool = True
    cluster_hosts: str = ""  # Comma-separated list of hosts to connect to
    region: Optional[str] = None  # Geographic region
    zone: Optional[str] = None  # Availability zone
    config_path: Optional[str] = None  # Path to configuration file
    
    # Replication configuration
    enable_replication: bool = True
    consistency_model: str = "eventual"  # strong, eventual, causal
    replication_strategy: str = "asynchronous"  # synchronous, asynchronous, quorum
    conflict_resolution: str = "vector_clock"  # last_write_wins, vector_clock, custom
    sync_interval: int = 30  # Seconds between synchronization
    quorum_size: int = 2  # Number of replicas needed for quorum write
    read_repair: bool = True  # Fix inconsistencies on read
    gossip_enabled: bool = True  # Use gossip protocol for replication
    
    # Advanced options
    enable_load_balancing: bool = True  # Enable load balancing
    enable_multi_region: bool = False  # Enable multi-region deployment


class HighAvailabilityIntegration:
    """
    Integration of High Availability features with MCP server.

    This class integrates the High Availability Architecture components
    with the MCP server, providing multi-region deployment, automatic failover,
    load balancing, and replication and consistency features.
    """

    def __init__(self, app: FastAPI, config: Optional[HAConfig] = None):
        """
        Initialize High Availability integration.

        Args:
            app: FastAPI application
            config: High Availability configuration
        """
        self.app = app
        self.config = config or HAConfig()
        self.ha_service = None
        self.consistency_service = None
        self.http_session = None
        self.initialized = False
        
        # Set up environment variables from config
        if self.config.region:
            os.environ["MCP_REGION"] = self.config.region
        
        if self.config.zone:
            os.environ["MCP_ZONE"] = self.config.zone
        
        if self.config.cluster_hosts:
            os.environ["MCP_CLUSTER_HOSTS"] = self.config.cluster_hosts

    async def start(self):
        """Initialize and start High Availability services."""
        if self.initialized or not self.config.enabled:
            return
        
        logger.info("Starting High Availability integration")
        
        # Create HTTP session for all components
        self.http_session = aiohttp.ClientSession()
        
        # Initialize HA service
        self.ha_service = HighAvailabilityService(
            app=self.app,
            config_path=self.config.config_path
        )
        
        # Start HA service
        await self.ha_service.start()
        
        # Wait for HA service to initialize and join/create cluster
        await asyncio.sleep(2)
        
        # Initialize replication if enabled
        if self.config.enable_replication:
            await self._init_replication()
        
        # Initialize load balancing if enabled
        if self.config.enable_load_balancing:
            await self._init_load_balancing()
        
        # Initialize multi-region support if enabled
        if self.config.enable_multi_region:
            await self._init_multi_region()
        
        # Register role change handler to coordinate failover
        self.ha_service.register_role_change_callback(self._handle_role_change)
        
        # Register node status change handler
        self.ha_service.register_node_status_callback(self._handle_node_status_change)
        
        # Register failover handler
        self.ha_service.register_failover_callback(self._handle_failover)
        
        self.initialized = True
        logger.info("High Availability integration started successfully")

    async def stop(self):
        """Stop High Availability services."""
        if not self.initialized:
            return
        
        logger.info("Stopping High Availability integration")
        
        # Stop consistency service if initialized
        if self.consistency_service:
            await self.consistency_service.stop()
        
        # Stop HA service
        if self.ha_service:
            await self.ha_service.stop()
        
        # Close HTTP session
        if self.http_session:
            await self.http_session.close()
        
        self.initialized = False
        logger.info("High Availability integration stopped")

    async def _init_replication(self):
        """Initialize data replication and consistency."""
        logger.info("Initializing data replication and consistency")
        
        # Get node ID from HA service
        node_id = self.ha_service.node_id
        
        # Create replication config
        try:
            # Convert string values to enum values
            consistency_model = ConsistencyModel(self.config.consistency_model)
            replication_strategy = ReplicationStrategy(self.config.replication_strategy)
            conflict_resolution = ConflictResolutionStrategy(self.config.conflict_resolution)
            
            replication_config = ReplicationConfig(
                consistency_model=consistency_model,
                replication_strategy=replication_strategy,
                conflict_resolution=conflict_resolution,
                sync_interval=self.config.sync_interval,
                quorum_size=self.config.quorum_size,
                read_repair=self.config.read_repair,
                gossip_enabled=self.config.gossip_enabled
            )
        except ValueError as e:
            logger.error(f"Invalid replication configuration: {e}")
            logger.warning("Using default replication configuration")
            replication_config = ReplicationConfig()
        
        # Create consistency service
        self.consistency_service = ConsistencyService(
            node_id=node_id,
            config=replication_config,
            http_session=self.http_session
        )
        
        # Register with app
        register_with_app(self.app, self.consistency_service)
        
        # Start consistency service
        await self.consistency_service.start()
        
        # Update known nodes from HA service
        if self.ha_service.cluster_state:
            nodes = {
                node_id: {
                    "ip_address": node.ip_address,
                    "port": node.port,
                    "status": node.status
                }
                for node_id, node in self.ha_service.cluster_state.nodes.items()
            }
            self.consistency_service.update_nodes(nodes)
        
        logger.info("Data replication and consistency initialized")

    async def _init_load_balancing(self):
        """Initialize load balancing functionality."""
        logger.info("Initializing load balancing")
        
        # Add load balancing endpoints to app
        
        @self.app.get("/api/v0/ha/load")
        async def get_load():
            """Get load information for all nodes."""
            if not self.ha_service or not self.ha_service.cluster_state:
                return {"success": False, "error": "HA service not initialized"}
            
            nodes_load = {}
            for node_id, node in self.ha_service.cluster_state.nodes.items():
                if node.status == "active":
                    nodes_load[node_id] = {
                        "cpu": node.load.get("cpu", 0),
                        "memory": node.load.get("memory", 0),
                        "disk": node.load.get("disk", 0),
                        "role": node.role,
                        "region": node.region,
                        "zone": node.zone
                    }
            
            return {
                "success": True,
                "nodes": nodes_load,
                "timestamp": self.ha_service.cluster_state.version.timestamp
            }
        
        @self.app.get("/api/v0/ha/redirect")
        async def get_redirect(operation: Optional[str] = None):
            """Get optimal node for a specific operation."""
            if not self.ha_service or not self.ha_service.cluster_state:
                return {"success": False, "error": "HA service not initialized"}
            
            # Default to primary node for write operations
            if operation and operation.startswith("write"):
                primary_id = self.ha_service.cluster_state.primary_node_id
                if primary_id in self.ha_service.cluster_state.nodes:
                    primary = self.ha_service.cluster_state.nodes[primary_id]
                    return {
                        "success": True,
                        "node_id": primary_id,
                        "address": f"{primary.ip_address}:{primary.port}",
                        "reason": "primary_node"
                    }
            
            # For read operations, find node with lowest load
            active_nodes = {
                node_id: node
                for node_id, node in self.ha_service.cluster_state.nodes.items()
                if node.status == "active"
            }
            
            if not active_nodes:
                return {"success": False, "error": "No active nodes available"}
            
            # Find node with lowest CPU and memory load
            lowest_load_node_id = None
            lowest_load_value = float('inf')
            
            for node_id, node in active_nodes.items():
                cpu_load = node.load.get("cpu", 50)
                memory_load = node.load.get("memory", 50)
                combined_load = cpu_load * 0.6 + memory_load * 0.4  # Weight CPU more
                
                if combined_load < lowest_load_value:
                    lowest_load_value = combined_load
                    lowest_load_node_id = node_id
            
            if lowest_load_node_id:
                node = active_nodes[lowest_load_node_id]
                return {
                    "success": True,
                    "node_id": lowest_load_node_id,
                    "address": f"{node.ip_address}:{node.port}",
                    "reason": "lowest_load"
                }
            
            # Fallback to any active node
            node_id = next(iter(active_nodes.keys()))
            node = active_nodes[node_id]
            return {
                "success": True,
                "node_id": node_id,
                "address": f"{node.ip_address}:{node.port}",
                "reason": "fallback"
            }
        
        logger.info("Load balancing initialized")

    async def _init_multi_region(self):
        """Initialize multi-region deployment features."""
        logger.info("Initializing multi-region deployment features")
        
        # Add multi-region endpoints to app
        
        @self.app.get("/api/v0/ha/regions")
        async def get_regions():
            """Get information about all regions."""
            if not self.ha_service or not self.ha_service.cluster_state:
                return {"success": False, "error": "HA service not initialized"}
            
            # Group nodes by region
            regions = {}
            for node_id, node in self.ha_service.cluster_state.nodes.items():
                region = node.region or "default"
                if region not in regions:
                    regions[region] = {
                        "nodes": [],
                        "active_nodes": 0,
                        "has_primary": False
                    }
                
                regions[region]["nodes"].append({
                    "node_id": node_id,
                    "status": node.status,
                    "role": node.role,
                    "zone": node.zone
                })
                
                if node.status == "active":
                    regions[region]["active_nodes"] += 1
                
                if node.role == "primary":
                    regions[region]["has_primary"] = True
            
            return {
                "success": True,
                "regions": regions,
                "timestamp": self.ha_service.cluster_state.version.timestamp
            }
        
        @self.app.get("/api/v0/ha/region_redirect")
        async def get_region_redirect(region: Optional[str] = None):
            """Get optimal node in a specific region."""
            if not self.ha_service or not self.ha_service.cluster_state:
                return {"success": False, "error": "HA service not initialized"}
            
            # If no region specified, use current region
            if not region:
                region = os.environ.get("MCP_REGION", "default")
            
            # Find active nodes in the specified region
            region_nodes = {
                node_id: node
                for node_id, node in self.ha_service.cluster_state.nodes.items()
                if (node.region or "default") == region and node.status == "active"
            }
            
            if not region_nodes:
                return {"success": False, "error": f"No active nodes in region {region}"}
            
            # Find node with lowest load in the region
            lowest_load_node_id = None
            lowest_load_value = float('inf')
            
            for node_id, node in region_nodes.items():
                cpu_load = node.load.get("cpu", 50)
                memory_load = node.load.get("memory", 50)
                combined_load = cpu_load * 0.6 + memory_load * 0.4
                
                if combined_load < lowest_load_value:
                    lowest_load_value = combined_load
                    lowest_load_node_id = node_id
            
            if lowest_load_node_id:
                node = region_nodes[lowest_load_node_id]
                return {
                    "success": True,
                    "node_id": lowest_load_node_id,
                    "address": f"{node.ip_address}:{node.port}",
                    "region": region,
                    "reason": "lowest_load_in_region"
                }
            
            # Fallback to any active node in the region
            node_id = next(iter(region_nodes.keys()))
            node = region_nodes[node_id]
            return {
                "success": True,
                "node_id": node_id,
                "address": f"{node.ip_address}:{node.port}",
                "region": region,
                "reason": "fallback_in_region"
            }
        
        logger.info("Multi-region deployment features initialized")

    def _handle_role_change(self, new_role: str):
        """
        Handle role changes in the HA cluster.

        Args:
            new_role: New role for this node
        """
        logger.info(f"Node role changed to: {new_role}")
        
        # If we become primary, we need to take over primary responsibilities
        if new_role == "primary":
            logger.info("This node is now the primary node")
            
            # Trigger any primary-specific initialization
            asyncio.create_task(self._on_become_primary())
        
        # If we become secondary, we can shed primary responsibilities
        elif new_role == "secondary":
            logger.info("This node is now a secondary node")
            
            # Handle stepping down from primary role
            asyncio.create_task(self._on_become_secondary())

    async def _on_become_primary(self):
        """Handle becoming the primary node."""
        # Update consistency service config if needed
        if self.consistency_service:
            # In the primary role, we might want to use stronger consistency
            # depending on the application requirements
            logger.info("Adjusting consistency settings for primary role")

    async def _on_become_secondary(self):
        """Handle becoming a secondary node."""
        # Update consistency service config if needed
        if self.consistency_service:
            # In the secondary role, we might use eventual consistency
            # for better performance
            logger.info("Adjusting consistency settings for secondary role")

    def _handle_node_status_change(self, node_id: str, new_status: str):
        """
        Handle node status changes in the HA cluster.

        Args:
            node_id: Node identifier
            new_status: New status for the node
        """
        logger.info(f"Node {node_id} status changed to: {new_status}")
        
        # Update consistency service's known nodes
        if self.consistency_service and self.ha_service.cluster_state:
            nodes = {
                n_id: {
                    "ip_address": node.ip_address,
                    "port": node.port,
                    "status": node.status
                }
                for n_id, node in self.ha_service.cluster_state.nodes.items()
            }
            self.consistency_service.update_nodes(nodes)

    def _handle_failover(self, event):
        """
        Handle failover events in the HA cluster.

        Args:
            event: Failover event
        """
        logger.info(f"Failover event: {event.reason}")
        logger.info(f"Primary node changed from {event.old_primary} to {event.new_primary}")
        
        # If we're involved in the failover, take appropriate action
        if event.new_primary == self.ha_service.node_id:
            logger.info("This node is the new primary after failover")
            asyncio.create_task(self._on_become_primary())
        
        elif event.old_primary == self.ha_service.node_id:
            logger.info("This node is no longer the primary after failover")
            asyncio.create_task(self._on_become_secondary())

    def is_primary(self) -> bool:
        """
        Check if this node is the primary.

        Returns:
            True if this node is the primary
        """
        if not self.ha_service:
            return False
        
        return self.ha_service.is_primary()

    def get_status(self) -> Dict[str, Any]:
        """
        Get HA integration status.

        Returns:
            Dictionary with status information
        """
        status = {
            "enabled": self.config.enabled,
            "initialized": self.initialized,
            "ha_service": self.ha_service is not None,
            "consistency_service": self.consistency_service is not None,
            "replication_enabled": self.config.enable_replication,
            "load_balancing_enabled": self.config.enable_load_balancing,
            "multi_region_enabled": self.config.enable_multi_region,
        }
        
        # Add cluster info if available
        if self.ha_service:
            status.update(self.ha_service.get_cluster_info())
        
        # Add consistency info if available
        if self.consistency_service:
            status["consistency"] = self.consistency_service.get_consistency_status()
        
        return status


async def setup_ha(app: FastAPI, config: Optional[Dict[str, Any]] = None) -> HighAvailabilityIntegration:
    """
    Set up High Availability features for the MCP server.

    Args:
        app: FastAPI application
        config: Configuration dictionary

    Returns:
        HighAvailabilityIntegration instance
    """
    # Convert config dict to HAConfig
    ha_config = HAConfig(**(config or {}))
    
    # Create integration
    ha_integration = HighAvailabilityIntegration(app, ha_config)
    
    # Start integration
    await ha_integration.start()
    
    # Store in app state for access in API endpoints
    app.state.ha_integration = ha_integration
    
    # Set up shutdown hook
    @app.on_event("shutdown")
    async def shutdown_ha():
        await ha_integration.stop()
    
    return ha_integration
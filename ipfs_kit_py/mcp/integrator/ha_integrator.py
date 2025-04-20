"""
MCP Server High Availability Integration Module

This module integrates the High Availability components with the MCP server,
providing API endpoints and services for managing multi-region deployments,
automatic failover, load balancing, and replication.

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).
"""

import os
import sys
import json
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-ha-integration")

# Try importing HA components
try:
    from ipfs_kit_py.mcp.enterprise.high_availability import (
        HACluster, LoadBalancer, 
        HAConfig, RegionConfig, NodeConfig,
        NodeRole, NodeStatus, RegionStatus,
        FailoverStrategy, ReplicationMode, ConsistencyLevel
    )
    HAS_HA_COMPONENTS = True
except ImportError:
    logger.warning("High Availability components not available. Install with pip install ipfs-kit-py[enterprise]")
    HAS_HA_COMPONENTS = False

# Try importing FastAPI components
try:
    from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    logger.warning("FastAPI not available. Install with pip install fastapi")
    HAS_FASTAPI = False

# ----- Pydantic Models for API -----

if HAS_FASTAPI:
    class NodeStateResponse(BaseModel):
        """Node state response model for API."""
        node_id: str
        status: str
        last_heartbeat: str
        uptime_seconds: int
        current_connections: int
        cpu_usage_percent: float
        memory_usage_gb: float
        io_read_mbps: float
        io_write_mbps: float
        network_in_mbps: float
        network_out_mbps: float
        error_count: int
        warning_count: int
        custom_metrics: Dict[str, Any] = {}

    class RegionStateResponse(BaseModel):
        """Region state response model for API."""
        region_id: str
        status: str
        nodes: List[str]
        primary: bool
        failover_priority: int

    class ClusterStateResponse(BaseModel):
        """Cluster state response model for API."""
        node_states: Dict[str, NodeStateResponse]
        region_states: Dict[str, str]
        primary_region: str
        active_regions: List[str]
        standby_regions: List[str]
        local_node_id: str
        local_node_is_primary: bool
        local_region_is_active: bool
        timestamp: str

    class FailoverRequest(BaseModel):
        """Failover request model for API."""
        from_region_id: str
        to_region_id: str
        reason: Optional[str] = None

    class FailoverResponse(BaseModel):
        """Failover response model for API."""
        success: bool
        message: str
        from_region_id: str
        to_region_id: str
        timestamp: str

    class HAStatusResponse(BaseModel):
        """HA status response model for API."""
        enabled: bool
        initialized: bool
        config_path: Optional[str] = None
        local_node_id: Optional[str] = None
        cluster_id: Optional[str] = None
        cluster_name: Optional[str] = None
        redis_url: Optional[str] = None
        error: Optional[str] = None


class HAIntegration:
    """
    High Availability integration for the MCP server.
    
    This class manages the integration between the High Availability
    components and the MCP server, including initialization, configuration,
    and API endpoints.
    """
    
    def __init__(self, config_path: Optional[str] = None, node_id: Optional[str] = None, 
                 redis_url: Optional[str] = None):
        """
        Initialize the HA integration.
        
        Args:
            config_path: Path to the HA configuration file
            node_id: ID of the local node
            redis_url: URL of the Redis server for distributed state
        """
        self.config_path = config_path
        self.node_id = node_id
        self.redis_url = redis_url
        
        # Internal state
        self.initialized = False
        self.enabled = HAS_HA_COMPONENTS
        self.ha_cluster = None
        self.load_balancer = None
        self.api_router = None
        self.status_task = None
        self.error = None
        
        # Try to load configuration from environment if not provided
        if not self.config_path:
            self.config_path = os.environ.get("MCP_HA_CONFIG_PATH")
        
        if not self.node_id:
            self.node_id = os.environ.get("MCP_HA_NODE_ID")
        
        if not self.redis_url:
            self.redis_url = os.environ.get("MCP_HA_REDIS_URL")
        
        logger.info(f"Initialized HA integration (enabled: {self.enabled})")
    
    async def initialize(self) -> bool:
        """
        Initialize the HA integration.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if not self.enabled:
            logger.warning("HA integration is disabled. Cannot initialize")
            return False
        
        if self.initialized:
            logger.warning("HA integration is already initialized")
            return True
        
        try:
            # Check configuration
            if not self.config_path or not os.path.exists(self.config_path):
                raise ValueError(f"HA configuration file not found: {self.config_path}")
            
            if not self.node_id:
                raise ValueError("Node ID is required for HA initialization")
            
            # Initialize HA cluster
            self.ha_cluster = HACluster(self.config_path, self.node_id, self.redis_url)
            
            # Start the cluster
            await self.ha_cluster.start()
            
            # Initialize load balancer
            self.load_balancer = LoadBalancer(self.ha_cluster)
            
            # Initialize API router if FastAPI is available
            if HAS_FASTAPI:
                self.api_router = self._create_api_router()
            
            # Start status monitoring task
            self.status_task = asyncio.create_task(self._monitor_status())
            
            self.initialized = True
            logger.info("HA integration initialized successfully")
            return True
        
        except Exception as e:
            self.error = str(e)
            logger.error(f"Error initializing HA integration: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """
        Shutdown the HA integration.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        if not self.initialized:
            logger.warning("HA integration is not initialized. Nothing to shutdown")
            return True
        
        try:
            # Cancel status monitoring task
            if self.status_task:
                self.status_task.cancel()
                try:
                    await self.status_task
                except asyncio.CancelledError:
                    pass
            
            # Stop the HA cluster
            if self.ha_cluster:
                await self.ha_cluster.stop()
            
            self.initialized = False
            logger.info("HA integration shutdown successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error shutting down HA integration: {e}")
            return False
    
    async def _monitor_status(self):
        """Monitor the status of the HA cluster."""
        while True:
            try:
                # Get cluster state
                if self.ha_cluster:
                    node_states = self.ha_cluster.get_all_node_states()
                    region_states = self.ha_cluster.get_all_region_states()
                    
                    # Log current status
                    healthy_nodes = sum(1 for state in node_states.values() 
                                    if state.status == NodeStatus.HEALTHY)
                    active_regions = sum(1 for status in region_states.values() 
                                      if status == RegionStatus.ACTIVE)
                    
                    logger.debug(f"HA Status: {healthy_nodes}/{len(node_states)} healthy nodes, "
                              f"{active_regions}/{len(region_states)} active regions")
            
            except Exception as e:
                logger.error(f"Error monitoring HA status: {e}")
            
            # Wait before next check
            await asyncio.sleep(60)  # Check every minute
    
    def _create_api_router(self) -> APIRouter:
        """
        Create an API router for HA endpoints.
        
        Returns:
            FastAPI router with HA endpoints
        """
        if not HAS_FASTAPI:
            logger.error("Cannot create API router without FastAPI")
            return None
        
        router = APIRouter(
            prefix="/api/v0/ha",
            tags=["High Availability"]
        )
        
        @router.get("/status", response_model=HAStatusResponse)
        async def get_ha_status():
            """Get the status of the High Availability system."""
            # Check if HA is initialized
            if not self.initialized:
                return HAStatusResponse(
                    enabled=self.enabled,
                    initialized=self.initialized,
                    error=self.error
                )
            
            # Get status from initialized cluster
            try:
                ha_config = self.ha_cluster.ha_config
                return HAStatusResponse(
                    enabled=self.enabled,
                    initialized=self.initialized,
                    config_path=self.config_path,
                    local_node_id=self.node_id,
                    cluster_id=ha_config.id,
                    cluster_name=ha_config.name,
                    redis_url=self.redis_url,
                    error=None
                )
            except Exception as e:
                return HAStatusResponse(
                    enabled=self.enabled,
                    initialized=self.initialized,
                    error=str(e)
                )
        
        @router.get("/cluster/state", response_model=ClusterStateResponse)
        async def get_cluster_state():
            """Get the current state of the HA cluster."""
            # Check if HA is initialized
            if not self.initialized or not self.ha_cluster:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA system is not initialized"
                )
            
            # Get cluster state
            try:
                node_states = self.ha_cluster.get_all_node_states()
                region_states = self.ha_cluster.get_all_region_states()
                
                # Convert to response models
                node_state_responses = {}
                for node_id, state in node_states.items():
                    node_state_responses[node_id] = NodeStateResponse(
                        node_id=state.node_id,
                        status=state.status.value,
                        last_heartbeat=state.last_heartbeat,
                        uptime_seconds=state.uptime_seconds,
                        current_connections=state.current_connections,
                        cpu_usage_percent=state.cpu_usage_percent,
                        memory_usage_gb=state.memory_usage_gb,
                        io_read_mbps=state.io_read_mbps,
                        io_write_mbps=state.io_write_mbps,
                        network_in_mbps=state.network_in_mbps,
                        network_out_mbps=state.network_out_mbps,
                        error_count=state.error_count,
                        warning_count=state.warning_count,
                        custom_metrics=state.custom_metrics
                    )
                
                # Get primary region
                primary_region = None
                for region in self.ha_cluster.ha_config.regions:
                    if region.primary:
                        primary_region = region.id
                        break
                
                # Get active and standby regions
                active_regions = []
                standby_regions = []
                for region_id, status in region_states.items():
                    if status == RegionStatus.ACTIVE:
                        active_regions.append(region_id)
                    elif status == RegionStatus.STANDBY:
                        standby_regions.append(region_id)
                
                # Create response
                return ClusterStateResponse(
                    node_states=node_state_responses,
                    region_states={r: s.value for r, s in region_states.items()},
                    primary_region=primary_region,
                    active_regions=active_regions,
                    standby_regions=standby_regions,
                    local_node_id=self.node_id,
                    local_node_is_primary=self.ha_cluster.is_local_node_primary(),
                    local_region_is_active=self.ha_cluster.is_local_region_active(),
                    timestamp=datetime.utcnow().isoformat()
                )
            
            except Exception as e:
                logger.error(f"Error getting cluster state: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error getting cluster state: {str(e)}"
                )
        
        @router.get("/nodes/{node_id}/state", response_model=NodeStateResponse)
        async def get_node_state(node_id: str = Path(..., description="ID of the node")):
            """Get the state of a specific node."""
            # Check if HA is initialized
            if not self.initialized or not self.ha_cluster:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA system is not initialized"
                )
            
            # Get node state
            try:
                state = self.ha_cluster.get_node_state(node_id)
                if not state:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Node {node_id} not found"
                    )
                
                # Convert to response model
                return NodeStateResponse(
                    node_id=state.node_id,
                    status=state.status.value,
                    last_heartbeat=state.last_heartbeat,
                    uptime_seconds=state.uptime_seconds,
                    current_connections=state.current_connections,
                    cpu_usage_percent=state.cpu_usage_percent,
                    memory_usage_gb=state.memory_usage_gb,
                    io_read_mbps=state.io_read_mbps,
                    io_write_mbps=state.io_write_mbps,
                    network_in_mbps=state.network_in_mbps,
                    network_out_mbps=state.network_out_mbps,
                    error_count=state.error_count,
                    warning_count=state.warning_count,
                    custom_metrics=state.custom_metrics
                )
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting node state: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error getting node state: {str(e)}"
                )
        
        @router.put("/nodes/{node_id}/state", response_model=NodeStateResponse)
        async def update_node_state(
            node_id: str = Path(..., description="ID of the node"),
            state: NodeStateResponse = None
        ):
            """Update the state of a specific node (used for node-to-node communication)."""
            # Check if HA is initialized
            if not self.initialized or not self.ha_cluster:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA system is not initialized"
                )
            
            # Only allow updating state of non-local nodes
            if node_id == self.node_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot update state of local node through API"
                )
            
            # Update node state (in a real implementation, this would validate the sender)
            # For security reasons, this endpoint should require authentication
            return state
        
        @router.post("/failover", response_model=FailoverResponse)
        async def initiate_failover(request: FailoverRequest):
            """Manually initiate a failover between regions."""
            # Check if HA is initialized
            if not self.initialized or not self.ha_cluster:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA system is not initialized"
                )
            
            # Initiate failover
            try:
                success = await self.ha_cluster.initiate_manual_failover(
                    request.from_region_id, request.to_region_id
                )
                
                if success:
                    return FailoverResponse(
                        success=True,
                        message=f"Failover from {request.from_region_id} to {request.to_region_id} initiated successfully",
                        from_region_id=request.from_region_id,
                        to_region_id=request.to_region_id,
                        timestamp=datetime.utcnow().isoformat()
                    )
                else:
                    return FailoverResponse(
                        success=False,
                        message="Failover initiation failed",
                        from_region_id=request.from_region_id,
                        to_region_id=request.to_region_id,
                        timestamp=datetime.utcnow().isoformat()
                    )
            
            except Exception as e:
                logger.error(f"Error initiating failover: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error initiating failover: {str(e)}"
                )
        
        @router.get("/regions/{region_id}/state")
        async def get_region_state(region_id: str = Path(..., description="ID of the region")):
            """Get the state of a specific region."""
            # Check if HA is initialized
            if not self.initialized or not self.ha_cluster:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA system is not initialized"
                )
            
            # Get region state
            try:
                state = self.ha_cluster.get_region_state(region_id)
                region_config = self.ha_cluster.ha_config.get_region_by_id(region_id)
                
                if not state or not region_config:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Region {region_id} not found"
                    )
                
                # Get nodes in this region
                nodes_in_region = []
                for node_id, node_config in self.ha_cluster.node_configs.items():
                    if node_config.region == region_id:
                        nodes_in_region.append(node_id)
                
                # Create response
                return {
                    "region_id": region_id,
                    "status": state.value,
                    "nodes": nodes_in_region,
                    "primary": region_config.primary,
                    "failover_priority": region_config.failover_priority,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting region state: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error getting region state: {str(e)}"
                )
        
        @router.post("/events/failover")
        async def receive_failover_event(event: dict):
            """Receive a failover event from another node (used for node-to-node communication)."""
            # Check if HA is initialized
            if not self.initialized or not self.ha_cluster:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA system is not initialized"
                )
            
            # Log the event
            logger.info(f"Received failover event: {event}")
            
            # In a real implementation, this would update the local state
            # For security reasons, this endpoint should require authentication
            return {"status": "received"}
        
        @router.get("/next-node")
        async def get_next_node(
            region_id: Optional[str] = Query(None, description="ID of the region to select from"),
            only_healthy: bool = Query(True, description="Whether to only return healthy nodes"),
            node_type: Optional[str] = Query(None, description="Type of node to select")
        ):
            """Get the next node to route a request to based on load balancing."""
            # Check if HA is initialized
            if not self.initialized or not self.ha_cluster or not self.load_balancer:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA system is not initialized"
                )
            
            # Convert node_type string to enum if provided
            node_role = None
            if node_type:
                try:
                    node_role = NodeRole(node_type)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid node type: {node_type}"
                    )
            
            # Get next node
            try:
                node = self.load_balancer.get_next_node(
                    region_id=region_id,
                    only_healthy=only_healthy,
                    node_type=node_role
                )
                
                if not node:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="No suitable node found"
                    )
                
                # Return node details
                return {
                    "node_id": node.id,
                    "host": node.host,
                    "port": node.port,
                    "role": node.role.value,
                    "region": node.region,
                    "zone": node.zone,
                    "api_url": node.api_url
                }
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting next node: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error getting next node: {str(e)}"
                )
        
        return router
    
    def get_api_router(self) -> Optional[APIRouter]:
        """
        Get the API router for HA endpoints.
        
        Returns:
            The API router or None if not initialized
        """
        return self.api_router
    
    def get_next_node(self, region_id: Optional[str] = None, 
                      only_healthy: bool = True, 
                      node_type: Optional[NodeRole] = None) -> Optional[NodeConfig]:
        """
        Get the next node to route a request to based on load balancing.
        
        Args:
            region_id: Optional ID of the region to select from
            only_healthy: Whether to only return healthy nodes
            node_type: Optional type of node to select
            
        Returns:
            Node configuration or None if no suitable node was found
        """
        if not self.initialized or not self.load_balancer:
            logger.warning("HA system is not initialized. Cannot get next node")
            return None
        
        try:
            return self.load_balancer.get_next_node(
                region_id=region_id,
                only_healthy=only_healthy,
                node_type=node_type
            )
        except Exception as e:
            logger.error(f"Error getting next node: {e}")
            return None
    
    def is_active(self) -> bool:
        """
        Check if the local node is in an active region.
        
        Returns:
            True if the local node is in an active region, False otherwise
        """
        if not self.initialized or not self.ha_cluster:
            return False
        
        return self.ha_cluster.is_local_region_active()
    
    def is_primary(self) -> bool:
        """
        Check if the local node is a primary node.
        
        Returns:
            True if the local node is a primary node, False otherwise
        """
        if not self.initialized or not self.ha_cluster:
            return False
        
        return self.ha_cluster.is_local_node_primary()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the HA system.
        
        Returns:
            Dictionary with status information
        """
        status = {
            "enabled": self.enabled,
            "initialized": self.initialized,
            "config_path": self.config_path,
            "node_id": self.node_id,
            "redis_url": self.redis_url,
            "error": self.error
        }
        
        if self.initialized and self.ha_cluster:
            # Add cluster information
            cluster_config = self.ha_cluster.ha_config
            status.update({
                "cluster_id": cluster_config.id,
                "cluster_name": cluster_config.name,
                "failover_strategy": cluster_config.failover_strategy.value,
                "replication_mode": cluster_config.replication_mode.value,
                "consistency_level": cluster_config.consistency_level.value,
                "is_active": self.is_active(),
                "is_primary": self.is_primary()
            })
        
        return status


# Singleton instance
_ha_integration_instance = None

def get_ha_integration() -> HAIntegration:
    """
    Get the singleton HA integration instance.
    
    Returns:
        The HAIntegration instance
    """
    global _ha_integration_instance
    if _ha_integration_instance is None:
        _ha_integration_instance = HAIntegration()
    return _ha_integration_instance
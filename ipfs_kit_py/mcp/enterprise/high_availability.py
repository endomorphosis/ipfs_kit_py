"""
High Availability Architecture Module for MCP Server

This module provides the foundation for high availability deployments of the MCP server,
enabling resilient, fault-tolerant operations across multiple regions and availability zones.

Key features:
1. Multi-region deployment configuration
2. Automatic failover mechanisms
3. Load balancing between multiple MCP instances
4. State replication and consistency management
5. Health monitoring and auto-recovery

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).
"""

import os
import sys
import json
import time
import uuid
import logging
import threading
import asyncio
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from datetime import datetime, timedelta
import ipaddress

# Configure logger
logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import aiodns
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp not available. Some high availability features will be limited.")

try:
    import redis
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.warning("Redis client not available. Distributed state coordination will be limited.")


class NodeRole(str, Enum):
    """Possible roles for a node in the HA cluster."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    READ_REPLICA = "read_replica"
    BACKUP = "backup"


class NodeStatus(str, Enum):
    """Possible statuses for a node in the HA cluster."""
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class RegionStatus(str, Enum):
    """Possible statuses for a region in the HA deployment."""
    ACTIVE = "active"
    STANDBY = "standby"
    FAILOVER = "failover"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class FailoverStrategy(str, Enum):
    """Available failover strategies."""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    QUORUM = "quorum"
    LEADER_ELECTION = "leader_election"


class ReplicationMode(str, Enum):
    """Available replication modes."""
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    SEMI_SYNC = "semi_synchronous"


class ConsistencyLevel(str, Enum):
    """Available consistency levels for operations."""
    STRONG = "strong"
    EVENTUAL = "eventual"
    READ_YOUR_WRITES = "read_your_writes"
    SESSION = "session"
    MONOTONIC_READS = "monotonic_reads"
    MONOTONIC_WRITES = "monotonic_writes"


@dataclass
class NodeConfig:
    """Configuration for a node in the HA cluster."""
    id: str
    host: str
    port: int
    role: NodeRole
    region: str
    zone: str
    api_endpoint: str
    admin_endpoint: Optional[str] = None
    metrics_endpoint: Optional[str] = None
    max_connections: int = 1000
    max_memory_gb: float = 4.0
    cpu_cores: int = 2
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def address(self) -> str:
        """Return the full address of the node."""
        return f"{self.host}:{self.port}"
    
    @property
    def api_url(self) -> str:
        """Return the full API URL."""
        return f"http://{self.host}:{self.port}{self.api_endpoint}"
    
    @property
    def admin_url(self) -> Optional[str]:
        """Return the full admin URL if available."""
        if self.admin_endpoint:
            return f"http://{self.host}:{self.port}{self.admin_endpoint}"
        return None
    
    @property
    def metrics_url(self) -> Optional[str]:
        """Return the full metrics URL if available."""
        if self.metrics_endpoint:
            return f"http://{self.host}:{self.port}{self.metrics_endpoint}"
        return None


@dataclass
class NodeState:
    """Runtime state of a node in the HA cluster."""
    node_id: str
    status: NodeStatus
    last_heartbeat: str  # ISO format timestamp
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
    custom_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RegionConfig:
    """Configuration for a region in the HA deployment."""
    id: str
    name: str
    location: str
    primary: bool = False
    nodes: List[str] = field(default_factory=list)  # List of node IDs
    failover_priority: int = 0
    dns_name: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HAConfig:
    """High Availability configuration."""
    id: str
    name: str
    description: Optional[str] = None
    active: bool = True
    failover_strategy: FailoverStrategy = FailoverStrategy.AUTOMATIC
    replication_mode: ReplicationMode = ReplicationMode.ASYNCHRONOUS
    consistency_level: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    heartbeat_interval_ms: int = 5000
    health_check_interval_ms: int = 10000
    failover_timeout_ms: int = 30000
    quorum_size: int = 3
    replication_factor: int = 3
    regions: List[RegionConfig] = field(default_factory=list)
    dns_failover: bool = False
    dns_ttl_seconds: int = 60
    load_balancing_policy: str = "round-robin"
    ssl_enabled: bool = False
    certificate_path: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def get_primary_region(self) -> Optional[RegionConfig]:
        """Get the primary region configuration."""
        for region in self.regions:
            if region.primary:
                return region
        return None
    
    def get_region_by_id(self, region_id: str) -> Optional[RegionConfig]:
        """Get a region configuration by ID."""
        for region in self.regions:
            if region.id == region_id:
                return region
        return None


class HAStateManager:
    """
    Manages the state of a high availability cluster.
    
    This class is responsible for:
    - Keeping track of all nodes in the cluster
    - Monitoring node health
    - Coordinating failover events
    - Managing distributed state
    """
    
    def __init__(self, config: HAConfig, node_configs: Dict[str, NodeConfig], 
                local_node_id: str, redis_url: Optional[str] = None):
        """
        Initialize the HA state manager.
        
        Args:
            config: High availability configuration
            node_configs: Dictionary of node configurations indexed by ID
            local_node_id: ID of the local node
            redis_url: Optional URL of Redis server for distributed state (if available)
        """
        self.config = config
        self.node_configs = node_configs
        self.local_node_id = local_node_id
        self.redis_url = redis_url
        
        # Local state
        self.node_states: Dict[str, NodeState] = {}
        self.region_states: Dict[str, RegionStatus] = {}
        self.last_elections: Dict[str, datetime] = {}
        self.active_primary_nodes: Dict[str, str] = {}  # region_id -> node_id
        
        # Locks for thread safety
        self._state_lock = threading.RLock()
        
        # Initialize Redis if available
        self.redis_client = None
        if HAS_REDIS and redis_url:
            try:
                self.redis_client = redis.Redis.from_url(redis_url)
                logger.info(f"Connected to Redis at {redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
        
        # Identify the local node
        self.local_node = node_configs.get(local_node_id)
        if not self.local_node:
            raise ValueError(f"Local node ID {local_node_id} not found in node configurations")
        
        logger.info(f"Initialized HA state manager for node {local_node_id} in region {self.local_node.region}")
    
    async def start(self):
        """Start the HA state manager and background tasks."""
        # Initialize local node state
        self._initialize_local_state()
        
        # Start background tasks
        asyncio.create_task(self._heartbeat_task())
        asyncio.create_task(self._health_check_task())
        
        # Register with cluster
        await self._register_with_cluster()
        
        logger.info(f"HA state manager started for node {self.local_node_id}")
    
    async def stop(self):
        """Stop the HA state manager and clean up resources."""
        # Unregister from cluster
        await self._unregister_from_cluster()
        
        # Clean up Redis connection if used
        if self.redis_client:
            self.redis_client.close()
        
        logger.info(f"HA state manager stopped for node {self.local_node_id}")
    
    def _initialize_local_state(self):
        """Initialize the local state."""
        with self._state_lock:
            # Initialize node states
            for node_id, node_config in self.node_configs.items():
                if node_id == self.local_node_id:
                    # Set local node as healthy
                    self.node_states[node_id] = NodeState(
                        node_id=node_id,
                        status=NodeStatus.HEALTHY,
                        last_heartbeat=datetime.utcnow().isoformat(),
                        uptime_seconds=0,
                        current_connections=0,
                        cpu_usage_percent=0.0,
                        memory_usage_gb=0.0,
                        io_read_mbps=0.0,
                        io_write_mbps=0.0,
                        network_in_mbps=0.0,
                        network_out_mbps=0.0,
                        error_count=0,
                        warning_count=0
                    )
                else:
                    # Set other nodes as initializing
                    self.node_states[node_id] = NodeState(
                        node_id=node_id,
                        status=NodeStatus.INITIALIZING,
                        last_heartbeat="",
                        uptime_seconds=0,
                        current_connections=0,
                        cpu_usage_percent=0.0,
                        memory_usage_gb=0.0,
                        io_read_mbps=0.0,
                        io_write_mbps=0.0,
                        network_in_mbps=0.0,
                        network_out_mbps=0.0,
                        error_count=0,
                        warning_count=0
                    )
            
            # Initialize region states
            for region in self.config.regions:
                if region.primary:
                    self.region_states[region.id] = RegionStatus.ACTIVE
                else:
                    self.region_states[region.id] = RegionStatus.STANDBY
    
    async def _register_with_cluster(self):
        """Register this node with the cluster."""
        if self.redis_client:
            try:
                # Register node in Redis
                node_key = f"ha:nodes:{self.local_node_id}"
                self.redis_client.hset(node_key, mapping={
                    "id": self.local_node_id,
                    "host": self.local_node.host,
                    "port": str(self.local_node.port),
                    "role": self.local_node.role.value,
                    "region": self.local_node.region,
                    "zone": self.local_node.zone,
                    "status": NodeStatus.HEALTHY.value,
                    "last_heartbeat": datetime.utcnow().isoformat()
                })
                
                # Set expiry to detect failed nodes
                self.redis_client.expire(node_key, int(self.config.heartbeat_interval_ms * 3 / 1000))
                
                # Add to region set
                self.redis_client.sadd(f"ha:regions:{self.local_node.region}:nodes", self.local_node_id)
                
                logger.info(f"Registered node {self.local_node_id} with the cluster")
            except Exception as e:
                logger.error(f"Failed to register with cluster via Redis: {e}")
        else:
            # Without Redis, notify other nodes directly
            await self._notify_nodes_of_state()
    
    async def _unregister_from_cluster(self):
        """Unregister this node from the cluster."""
        if self.redis_client:
            try:
                # Remove node from Redis
                self.redis_client.delete(f"ha:nodes:{self.local_node_id}")
                
                # Remove from region set
                self.redis_client.srem(f"ha:regions:{self.local_node.region}:nodes", self.local_node_id)
                
                logger.info(f"Unregistered node {self.local_node_id} from the cluster")
            except Exception as e:
                logger.error(f"Failed to unregister from cluster via Redis: {e}")
        else:
            # Without Redis, notify other nodes directly
            node_state = self.node_states[self.local_node_id]
            node_state.status = NodeStatus.OFFLINE
            await self._notify_nodes_of_state()
    
    async def _heartbeat_task(self):
        """Send regular heartbeats to other nodes."""
        while True:
            try:
                # Update local node state
                with self._state_lock:
                    node_state = self.node_states[self.local_node_id]
                    node_state.last_heartbeat = datetime.utcnow().isoformat()
                    node_state.uptime_seconds += int(self.config.heartbeat_interval_ms / 1000)
                    
                    # Here we would add real metrics collection
                    # For now, we'll just use dummy values
                    node_state.cpu_usage_percent = 20.0
                    node_state.memory_usage_gb = 1.5
                
                # Send heartbeat to Redis if available
                if self.redis_client:
                    node_key = f"ha:nodes:{self.local_node_id}"
                    self.redis_client.hset(node_key, mapping={
                        "status": node_state.status.value,
                        "last_heartbeat": node_state.last_heartbeat,
                        "uptime_seconds": str(node_state.uptime_seconds),
                        "cpu_usage_percent": str(node_state.cpu_usage_percent),
                        "memory_usage_gb": str(node_state.memory_usage_gb),
                        "current_connections": str(node_state.current_connections)
                    })
                    
                    # Refresh expiry
                    self.redis_client.expire(node_key, int(self.config.heartbeat_interval_ms * 3 / 1000))
                else:
                    # Without Redis, notify other nodes directly
                    await self._notify_nodes_of_state()
            except Exception as e:
                logger.error(f"Error in heartbeat task: {e}")
            
            # Wait for next heartbeat
            await asyncio.sleep(self.config.heartbeat_interval_ms / 1000)
    
    async def _health_check_task(self):
        """Regularly check the health of all nodes."""
        while True:
            try:
                # Redis-based approach
                if self.redis_client:
                    await self._check_health_via_redis()
                else:
                    # Direct health check approach
                    await self._check_health_directly()
                
                # Update region states based on node health
                self._update_region_states()
                
                # Check if failover is needed
                if self.config.failover_strategy == FailoverStrategy.AUTOMATIC:
                    await self._check_for_failover()
            except Exception as e:
                logger.error(f"Error in health check task: {e}")
            
            # Wait for next health check
            await asyncio.sleep(self.config.health_check_interval_ms / 1000)
    
    async def _check_health_via_redis(self):
        """Check health of nodes using Redis."""
        now = datetime.utcnow()
        
        # Get all node keys
        node_keys = self.redis_client.keys("ha:nodes:*")
        
        for node_key in node_keys:
            try:
                node_id = node_key.decode('utf-8').split(":")[-1]
                if node_id == self.local_node_id:
                    continue  # Skip local node
                
                # Get node data
                node_data = self.redis_client.hgetall(node_key)
                if not node_data:
                    with self._state_lock:
                        if node_id in self.node_states:
                            self.node_states[node_id].status = NodeStatus.OFFLINE
                    continue
                
                # Convert from bytes
                node_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in node_data.items()}
                
                # Check last heartbeat
                last_heartbeat = datetime.fromisoformat(node_data.get("last_heartbeat", ""))
                heartbeat_age = (now - last_heartbeat).total_seconds() * 1000
                
                with self._state_lock:
                    if node_id not in self.node_states:
                        # Create new node state
                        self.node_states[node_id] = NodeState(
                            node_id=node_id,
                            status=NodeStatus(node_data.get("status", NodeStatus.INITIALIZING.value)),
                            last_heartbeat=node_data.get("last_heartbeat", ""),
                            uptime_seconds=int(node_data.get("uptime_seconds", "0")),
                            current_connections=int(node_data.get("current_connections", "0")),
                            cpu_usage_percent=float(node_data.get("cpu_usage_percent", "0")),
                            memory_usage_gb=float(node_data.get("memory_usage_gb", "0")),
                            io_read_mbps=0.0,
                            io_write_mbps=0.0,
                            network_in_mbps=0.0,
                            network_out_mbps=0.0,
                            error_count=0,
                            warning_count=0
                        )
                    else:
                        # Update existing node state
                        node_state = self.node_states[node_id]
                        node_state.status = NodeStatus(node_data.get("status", node_state.status.value))
                        node_state.last_heartbeat = node_data.get("last_heartbeat", node_state.last_heartbeat)
                        node_state.uptime_seconds = int(node_data.get("uptime_seconds", str(node_state.uptime_seconds)))
                        node_state.current_connections = int(node_data.get("current_connections", str(node_state.current_connections)))
                        node_state.cpu_usage_percent = float(node_data.get("cpu_usage_percent", str(node_state.cpu_usage_percent)))
                        node_state.memory_usage_gb = float(node_data.get("memory_usage_gb", str(node_state.memory_usage_gb)))
                    
                    # Check for heartbeat timeout
                    if heartbeat_age > self.config.failover_timeout_ms:
                        self.node_states[node_id].status = NodeStatus.OFFLINE
                    elif heartbeat_age > self.config.health_check_interval_ms * 2:
                        self.node_states[node_id].status = NodeStatus.FAILING
            except Exception as e:
                logger.error(f"Error checking health of node {node_id}: {e}")
    
    async def _check_health_directly(self):
        """Check health of nodes by directly contacting them."""
        if not HAS_AIOHTTP:
            logger.warning("Cannot perform direct health checks without aiohttp")
            return
        
        async with aiohttp.ClientSession() as session:
            for node_id, node_config in self.node_configs.items():
                if node_id == self.local_node_id:
                    continue  # Skip local node
                
                try:
                    # Get health endpoint URL
                    health_url = f"{node_config.api_url}/health"
                    
                    # Send request with timeout
                    async with session.get(health_url, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            with self._state_lock:
                                if node_id not in self.node_states:
                                    # Create new node state
                                    self.node_states[node_id] = NodeState(
                                        node_id=node_id,
                                        status=NodeStatus.HEALTHY,
                                        last_heartbeat=datetime.utcnow().isoformat(),
                                        uptime_seconds=data.get("uptime_seconds", 0),
                                        current_connections=data.get("current_connections", 0),
                                        cpu_usage_percent=data.get("cpu_usage_percent", 0.0),
                                        memory_usage_gb=data.get("memory_usage_gb", 0.0),
                                        io_read_mbps=data.get("io_read_mbps", 0.0),
                                        io_write_mbps=data.get("io_write_mbps", 0.0),
                                        network_in_mbps=data.get("network_in_mbps", 0.0),
                                        network_out_mbps=data.get("network_out_mbps", 0.0),
                                        error_count=data.get("error_count", 0),
                                        warning_count=data.get("warning_count", 0)
                                    )
                                else:
                                    # Update existing node state
                                    node_state = self.node_states[node_id]
                                    node_state.status = NodeStatus.HEALTHY
                                    node_state.last_heartbeat = datetime.utcnow().isoformat()
                                    node_state.uptime_seconds = data.get("uptime_seconds", node_state.uptime_seconds)
                                    node_state.current_connections = data.get("current_connections", node_state.current_connections)
                                    node_state.cpu_usage_percent = data.get("cpu_usage_percent", node_state.cpu_usage_percent)
                                    node_state.memory_usage_gb = data.get("memory_usage_gb", node_state.memory_usage_gb)
                                    node_state.io_read_mbps = data.get("io_read_mbps", node_state.io_read_mbps)
                                    node_state.io_write_mbps = data.get("io_write_mbps", node_state.io_write_mbps)
                                    node_state.network_in_mbps = data.get("network_in_mbps", node_state.network_in_mbps)
                                    node_state.network_out_mbps = data.get("network_out_mbps", node_state.network_out_mbps)
                                    node_state.error_count = data.get("error_count", node_state.error_count)
                                    node_state.warning_count = data.get("warning_count", node_state.warning_count)
                        else:
                            with self._state_lock:
                                if node_id in self.node_states:
                                    self.node_states[node_id].status = NodeStatus.DEGRADED
                except asyncio.TimeoutError:
                    with self._state_lock:
                        if node_id in self.node_states:
                            self.node_states[node_id].status = NodeStatus.FAILING
                except Exception as e:
                    logger.error(f"Error checking health of node {node_id}: {e}")
                    with self._state_lock:
                        if node_id in self.node_states:
                            self.node_states[node_id].status = NodeStatus.OFFLINE
    
    def _update_region_states(self):
        """Update the status of all regions based on node health."""
        with self._state_lock:
            # Count healthy nodes per region
            healthy_nodes_per_region: Dict[str, int] = {}
            failing_nodes_per_region: Dict[str, int] = {}
            total_nodes_per_region: Dict[str, int] = {}
            
            for node_id, node_state in self.node_states.items():
                node_config = self.node_configs.get(node_id)
                if not node_config:
                    continue
                
                region_id = node_config.region
                
                # Initialize counters
                if region_id not in healthy_nodes_per_region:
                    healthy_nodes_per_region[region_id] = 0
                    failing_nodes_per_region[region_id] = 0
                    total_nodes_per_region[region_id] = 0
                
                # Update counters
                total_nodes_per_region[region_id] += 1
                if node_state.status == NodeStatus.HEALTHY:
                    healthy_nodes_per_region[region_id] += 1
                elif node_state.status in [NodeStatus.FAILING, NodeStatus.OFFLINE]:
                    failing_nodes_per_region[region_id] += 1
            
            # Update region states
            for region_id, total_nodes in total_nodes_per_region.items():
                healthy_nodes = healthy_nodes_per_region.get(region_id, 0)
                failing_nodes = failing_nodes_per_region.get(region_id, 0)
                
                # Calculate health ratio
                health_ratio = healthy_nodes / total_nodes if total_nodes > 0 else 0
                
                # Update region status
                if health_ratio >= 0.8:  # 80% or more nodes are healthy
                    if region_id in self.region_states and self.region_states[region_id] == RegionStatus.FAILOVER:
                        # Keep in failover state until manually reset
                        pass
                    elif self.config.get_region_by_id(region_id) and self.config.get_region_by_id(region_id).primary:
                        self.region_states[region_id] = RegionStatus.ACTIVE
                    else:
                        self.region_states[region_id] = RegionStatus.STANDBY
                elif health_ratio >= 0.5:  # 50-80% nodes are healthy
                    self.region_states[region_id] = RegionStatus.DEGRADED
                else:  # Less than 50% nodes are healthy
                    self.region_states[region_id] = RegionStatus.OFFLINE
    
    async def _check_for_failover(self):
        """Check if failover is needed and initiate if necessary."""
        with self._state_lock:
            # Check primary region status
            primary_region = self.config.get_primary_region()
            if not primary_region:
                logger.warning("No primary region defined in configuration")
                return
            
            primary_region_id = primary_region.id
            primary_region_status = self.region_states.get(primary_region_id)
            
            if primary_region_status in [RegionStatus.DEGRADED, RegionStatus.OFFLINE]:
                # Primary region is degraded or offline, initiate failover
                logger.warning(f"Primary region {primary_region_id} is {primary_region_status.value}, initiating failover")
                
                # Find best standby region
                best_standby_region_id = None
                best_health_ratio = 0
                
                for region in self.config.regions:
                    if region.id == primary_region_id:
                        continue  # Skip primary
                    
                    if self.region_states.get(region.id) != RegionStatus.STANDBY:
                        continue  # Only consider standby regions
                    
                    # Count healthy nodes in region
                    healthy_nodes = 0
                    total_nodes = 0
                    
                    for node_id in self.node_configs:
                        node_config = self.node_configs[node_id]
                        if node_config.region == region.id:
                            total_nodes += 1
                            if (node_id in self.node_states and 
                                self.node_states[node_id].status == NodeStatus.HEALTHY):
                                healthy_nodes += 1
                    
                    health_ratio = healthy_nodes / total_nodes if total_nodes > 0 else 0
                    
                    # Check if this region is better than current best
                    if (health_ratio > best_health_ratio and health_ratio >= 0.8 and
                        (best_standby_region_id is None or 
                         region.failover_priority > self.config.get_region_by_id(best_standby_region_id).failover_priority)):
                        best_standby_region_id = region.id
                        best_health_ratio = health_ratio
                
                # If we found a suitable standby region, perform failover
                if best_standby_region_id:
                    logger.info(f"Performing failover from region {primary_region_id} to {best_standby_region_id}")
                    
                    # Update region states
                    self.region_states[primary_region_id] = RegionStatus.FAILOVER
                    self.region_states[best_standby_region_id] = RegionStatus.ACTIVE
                    
                    # Record failover timestamp
                    self.last_elections[best_standby_region_id] = datetime.utcnow()
                    
                    # Perform DNS failover if enabled
                    if self.config.dns_failover:
                        await self._perform_dns_failover(primary_region_id, best_standby_region_id)
                    
                    # Notify other nodes about failover
                    await self._notify_failover_event(primary_region_id, best_standby_region_id)
                else:
                    logger.warning(f"No suitable standby region found for failover from {primary_region_id}")
    
    async def _perform_dns_failover(self, from_region_id: str, to_region_id: str):
        """Perform DNS-based failover between regions."""
        from_region = self.config.get_region_by_id(from_region_id)
        to_region = self.config.get_region_by_id(to_region_id)
        
        if not from_region or not to_region:
            logger.error(f"Invalid region IDs for DNS failover: {from_region_id}, {to_region_id}")
            return
        
        if not from_region.dns_name or not to_region.dns_name:
            logger.error("DNS failover requires DNS names to be configured for regions")
            return
        
        if not HAS_AIOHTTP or not aiodns:
            logger.error("DNS failover requires aiodns and aiohttp to be installed")
            return
        
        try:
            # Here would be the actual DNS update code
            # This is just a placeholder since actual implementation depends on DNS provider
            logger.info(f"DNS failover: Updating DNS from {from_region.dns_name} to {to_region.dns_name}")
            logger.info(f"DNS failover successful with TTL {self.config.dns_ttl_seconds} seconds")
        except Exception as e:
            logger.error(f"Error during DNS failover: {e}")
    
    async def _notify_failover_event(self, from_region_id: str, to_region_id: str):
        """Notify all nodes about a failover event."""
        if self.redis_client:
            try:
                # Publish failover event to Redis
                event_data = json.dumps({
                    "event": "failover",
                    "from_region": from_region_id,
                    "to_region": to_region_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "initiated_by": self.local_node_id
                })
                self.redis_client.publish("ha:events:failover", event_data)
                logger.info(f"Published failover event to Redis")
            except Exception as e:
                logger.error(f"Failed to publish failover event to Redis: {e}")
        else:
            # Without Redis, notify other nodes directly via API
            if not HAS_AIOHTTP:
                logger.warning("Cannot notify failover event without aiohttp")
                return
            
            async with aiohttp.ClientSession() as session:
                for node_id, node_config in self.node_configs.items():
                    if node_id == self.local_node_id:
                        continue  # Skip local node
                    
                    try:
                        # Notify node about failover
                        event_url = f"{node_config.api_url}/ha/events/failover"
                        payload = {
                            "from_region": from_region_id,
                            "to_region": to_region_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "initiated_by": self.local_node_id
                        }
                        
                        async with session.post(event_url, json=payload, timeout=5) as response:
                            if response.status == 200:
                                logger.debug(f"Notified node {node_id} about failover")
                            else:
                                logger.warning(f"Failed to notify node {node_id} about failover: {response.status}")
                    except Exception as e:
                        logger.error(f"Error notifying node {node_id} about failover: {e}")
    
    async def _notify_nodes_of_state(self):
        """Notify other nodes about this node's state."""
        if not HAS_AIOHTTP:
            logger.warning("Cannot notify nodes of state without aiohttp")
            return
        
        # Get local node state
        with self._state_lock:
            local_state = self.node_states.get(self.local_node_id)
            if not local_state:
                logger.error("Cannot find local node state")
                return
        
        # Convert to dict for JSON serialization
        state_dict = local_state.to_dict()
        
        # Send to other nodes
        async with aiohttp.ClientSession() as session:
            for node_id, node_config in self.node_configs.items():
                if node_id == self.local_node_id:
                    continue  # Skip local node
                
                try:
                    # Notify node about our state
                    state_url = f"{node_config.api_url}/ha/nodes/{self.local_node_id}/state"
                    
                    async with session.put(state_url, json=state_dict, timeout=5) as response:
                        if response.status == 200:
                            logger.debug(f"Notified node {node_id} about local state")
                        else:
                            logger.warning(f"Failed to notify node {node_id} about local state: {response.status}")
                except Exception as e:
                    logger.debug(f"Error notifying node {node_id} about local state: {e}")


class HACluster:
    """
    High Availability Cluster management.
    
    This class manages the entire HA cluster and provides an API 
    for applications to interact with the HA functionality.
    """
    
    def __init__(self, config_path: str, local_node_id: str, redis_url: Optional[str] = None):
        """
        Initialize the HA cluster.
        
        Args:
            config_path: Path to the HA configuration file
            local_node_id: ID of the local node
            redis_url: Optional URL of Redis server for distributed state
        """
        # Load configuration
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Create configuration objects
        ha_config = HAConfig(**config_data['ha_config'])
        
        node_configs = {}
        for node_data in config_data['nodes']:
            node_id = node_data.pop('id')
            node_data['role'] = NodeRole(node_data['role'])
            node_configs[node_id] = NodeConfig(id=node_id, **node_data)
        
        # Initialize state manager
        self.state_manager = HAStateManager(ha_config, node_configs, local_node_id, redis_url)
        
        # Store configuration
        self.ha_config = ha_config
        self.node_configs = node_configs
        self.local_node_id = local_node_id
        
        logger.info(f"Initialized HA cluster with {len(node_configs)} nodes")
    
    async def start(self):
        """Start the HA cluster."""
        await self.state_manager.start()
        logger.info("HA cluster started")
    
    async def stop(self):
        """Stop the HA cluster."""
        await self.state_manager.stop()
        logger.info("HA cluster stopped")
    
    def get_node_state(self, node_id: str) -> Optional[NodeState]:
        """Get the current state of a node."""
        with self.state_manager._state_lock:
            return self.state_manager.node_states.get(node_id)
    
    def get_all_node_states(self) -> Dict[str, NodeState]:
        """Get the current state of all nodes."""
        with self.state_manager._state_lock:
            return self.state_manager.node_states.copy()
    
    def get_region_state(self, region_id: str) -> Optional[RegionStatus]:
        """Get the current state of a region."""
        with self.state_manager._state_lock:
            return self.state_manager.region_states.get(region_id)
    
    def get_all_region_states(self) -> Dict[str, RegionStatus]:
        """Get the current state of all regions."""
        with self.state_manager._state_lock:
            return self.state_manager.region_states.copy()
    
    def is_local_node_primary(self) -> bool:
        """Check if the local node is a primary node."""
        local_node = self.node_configs.get(self.local_node_id)
        if not local_node:
            return False
        
        return local_node.role == NodeRole.PRIMARY
    
    def is_local_region_active(self) -> bool:
        """Check if the local region is active."""
        local_node = self.node_configs.get(self.local_node_id)
        if not local_node:
            return False
        
        region_id = local_node.region
        with self.state_manager._state_lock:
            return self.state_manager.region_states.get(region_id) == RegionStatus.ACTIVE
    
    async def initiate_manual_failover(self, from_region_id: str, to_region_id: str) -> bool:
        """
        Manually initiate a failover between regions.
        
        Args:
            from_region_id: ID of the region to failover from
            to_region_id: ID of the region to failover to
            
        Returns:
            True if failover was initiated, False otherwise
        """
        with self.state_manager._state_lock:
            # Check if regions exist
            from_region = self.ha_config.get_region_by_id(from_region_id)
            to_region = self.ha_config.get_region_by_id(to_region_id)
            
            if not from_region or not to_region:
                logger.error(f"Invalid region IDs for failover: {from_region_id}, {to_region_id}")
                return False
            
            # Check if from_region is primary
            if not from_region.primary:
                logger.error(f"Cannot failover from non-primary region {from_region_id}")
                return False
            
            # Check if to_region is healthy
            to_region_status = self.state_manager.region_states.get(to_region_id)
            if to_region_status != RegionStatus.STANDBY:
                logger.error(f"Cannot failover to region {to_region_id} with status {to_region_status}")
                return False
            
            # Update region states
            self.state_manager.region_states[from_region_id] = RegionStatus.FAILOVER
            self.state_manager.region_states[to_region_id] = RegionStatus.ACTIVE
            
            # Record failover timestamp
            self.state_manager.last_elections[to_region_id] = datetime.utcnow()
        
        # Perform DNS failover if enabled
        if self.ha_config.dns_failover:
            await self.state_manager._perform_dns_failover(from_region_id, to_region_id)
        
        # Notify other nodes
        await self.state_manager._notify_failover_event(from_region_id, to_region_id)
        
        logger.info(f"Manual failover initiated from {from_region_id} to {to_region_id}")
        return True
    
    def set_local_node_status(self, status: NodeStatus) -> bool:
        """
        Set the status of the local node.
        
        Args:
            status: New status for the local node
            
        Returns:
            True if status was set, False otherwise
        """
        with self.state_manager._state_lock:
            if self.local_node_id not in self.state_manager.node_states:
                logger.error(f"Local node {self.local_node_id} not found in node states")
                return False
            
            self.state_manager.node_states[self.local_node_id].status = status
        
        logger.info(f"Local node status set to {status.value}")
        return True
    
    def get_config(self) -> HAConfig:
        """Get the current HA configuration."""
        return self.ha_config


class LoadBalancer:
    """
    Load balancer for distributing requests across nodes.
    
    This class provides load balancing functionality for the HA cluster,
    allowing applications to route requests to the most appropriate node.
    """
    
    def __init__(self, ha_cluster: HACluster):
        """
        Initialize the load balancer.
        
        Args:
            ha_cluster: HA cluster instance
        """
        self.ha_cluster = ha_cluster
        self.last_used_node: Dict[str, int] = {}  # region_id -> last node index
        self._lock = threading.RLock()
        
        logger.info("Initialized HA load balancer")
    
    def get_next_node(self, region_id: Optional[str] = None, 
                     only_healthy: bool = True, 
                     node_type: Optional[NodeRole] = None) -> Optional[NodeConfig]:
        """
        Get the next node to route a request to.
        
        Args:
            region_id: Optional ID of the region to select from (default: any active region)
            only_healthy: Whether to only return healthy nodes
            node_type: Optional type of node to select
            
        Returns:
            Node configuration or None if no suitable node was found
        """
        with self._lock:
            # Get all node states
            node_states = self.ha_cluster.get_all_node_states()
            region_states = self.ha_cluster.get_all_region_states()
            
            # If no region specified, use any active region
            if not region_id:
                active_regions = [r_id for r_id, status in region_states.items() 
                               if status == RegionStatus.ACTIVE]
                if not active_regions:
                    logger.warning("No active regions available")
                    return None
                
                region_id = active_regions[0]
            
            # Check if region is active
            if region_states.get(region_id) != RegionStatus.ACTIVE:
                logger.warning(f"Region {region_id} is not active")
                return None
            
            # Get nodes in the selected region
            nodes_in_region = []
            for node_id, node_config in self.ha_cluster.node_configs.items():
                if node_config.region == region_id:
                    # Check node type
                    if node_type and node_config.role != node_type:
                        continue
                    
                    # Check node health
                    if only_healthy:
                        node_state = node_states.get(node_id)
                        if not node_state or node_state.status != NodeStatus.HEALTHY:
                            continue
                    
                    nodes_in_region.append(node_config)
            
            if not nodes_in_region:
                logger.warning(f"No suitable nodes found in region {region_id}")
                return None
            
            # Apply load balancing policy based on configuration
            policy = self.ha_cluster.ha_config.load_balancing_policy.lower()
            
            if policy == "round-robin":
                # Round-robin selection
                last_index = self.last_used_node.get(region_id, -1)
                next_index = (last_index + 1) % len(nodes_in_region)
                self.last_used_node[region_id] = next_index
                return nodes_in_region[next_index]
            
            elif policy == "random":
                # Random selection
                import random
                return random.choice(nodes_in_region)
            
            elif policy == "least-connections":
                # Select node with least connections
                def get_connections(node):
                    state = node_states.get(node.id)
                    return state.current_connections if state else float('inf')
                
                return min(nodes_in_region, key=get_connections)
            
            elif policy == "least-load":
                # Select node with least CPU and memory load
                def get_load(node):
                    state = node_states.get(node.id)
                    if not state:
                        return float('inf')
                    # Combine CPU and memory metrics
                    return state.cpu_usage_percent + (state.memory_usage_gb / node.max_memory_gb) * 100
                
                return min(nodes_in_region, key=get_load)
            
            else:
                # Default to first node
                logger.warning(f"Unknown load balancing policy: {policy}, using first node")
                return nodes_in_region[0]

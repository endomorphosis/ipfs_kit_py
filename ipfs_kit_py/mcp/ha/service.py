"""
High Availability Service for MCP server.

This module implements the core High Availability functionality
as specified in the MCP roadmap for Phase 2: Enterprise Features (Q4 2025).
"""

import asyncio
import json
import logging
import os
import signal
import socket
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import aiohttp
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Define the key data models for HA
class NodeInfo(BaseModel):
    """Information about a node in the cluster."""

    node_id: str = Field(..., description="Unique node identifier")
    hostname: str = Field(..., description="Hostname of the node")
    ip_address: str = Field(..., description="IP address of the node")
    port: int = Field(..., description="Port number")
    region: Optional[str] = Field(None, description="Geographic region")
    zone: Optional[str] = Field(None, description="Availability zone")
    role: str = Field("worker", description="Node role: primary, secondary, worker")
    status: str = Field("starting", description="Node status: starting, active, degraded, failed")
    capabilities: List[str] = Field(default_factory=list, description="Node capabilities")
    start_time: float = Field(default_factory=time.time, description="Node start time")
    last_heartbeat: float = Field(default_factory=time.time, description="Last heartbeat time")
    load: Dict[str, float] = Field(default_factory=dict, description="Load statistics")


class ServiceInfo(BaseModel):
    """Information about a service in the cluster."""

    service_id: str = Field(..., description="Unique service identifier")
    name: str = Field(..., description="Service name")
    status: str = Field(
        "starting", description="Service status: starting, active, degraded, failed"
    )
    node_id: str = Field(..., description="Node hosting this service")
    endpoints: List[str] = Field(default_factory=list, description="Service endpoints")
    health_check: str = Field(..., description="Health check endpoint")
    last_check: float = Field(default_factory=time.time, description="Last health check time")


class ClusterConfig(BaseModel):
    """Configuration for the HA cluster."""

    cluster_id: str = Field(..., description="Unique cluster identifier")
    cluster_name: str = Field(..., description="Cluster name")
    primary_selection: str = Field(
        "auto", description="Primary selection mode: auto, manual, failover"
    )
    heartbeat_interval: int = Field(10, description="Heartbeat interval in seconds")
    failover_timeout: int = Field(30, description="Failover timeout in seconds")
    quorum_size: int = Field(2, description="Minimum nodes for quorum")
    replication_factor: int = Field(2, description="Replication factor for data")


class FailoverEvent(BaseModel):
    """Failover event information."""

    event_id: str = Field(..., description="Event identifier")
    timestamp: float = Field(default_factory=time.time, description="Event timestamp")
    old_primary: str = Field(..., description="Previous primary node")
    new_primary: str = Field(..., description="New primary node")
    reason: str = Field(..., description="Reason for failover")
    detected_by: str = Field(..., description="Node that detected failure")
    recovery_time: Optional[float] = Field(None, description="Time taken for failover")


class StateVersion(BaseModel):
    """Version information for cluster state."""

    version: int = Field(1, description="State version number")
    timestamp: float = Field(default_factory=time.time, description="Last update timestamp")
    updated_by: str = Field(..., description="Node that updated state")


class ClusterState(BaseModel):
    """Cluster state information."""

    version: StateVersion = Field(..., description="State version")
    nodes: Dict[str, NodeInfo] = Field(default_factory=dict, description="Active nodes")
    services: Dict[str, ServiceInfo] = Field(default_factory=dict, description="Active services")
    config: ClusterConfig = Field(..., description="Cluster configuration")
    primary_node_id: Optional[str] = Field(None, description="Current primary node")
    failover_history: List[FailoverEvent] = Field(
        default_factory=list, description="Failover history"
    )


class HighAvailabilityService:
    """
    Service for managing high availability features in MCP server.

    This service implements the High Availability Architecture requirements
    from the MCP roadmap, including multi-region deployment, automatic failover,
    load balancing, and replication and consistency.
    """

    def __init__(self, app: Optional[FastAPI] = None, config_path: Optional[str] = None):
        """
        Initialize the high availability service.

        Args:
            app: FastAPI application
            config_path: Path to configuration file
        """
        self.app = app
        self.config_path = config_path or "/tmp/ipfs_kit/mcp/ha/config.json"

        # Generate node ID using hostname and a random component for uniqueness
        hostname = socket.gethostname()
        random_part = uuid.uuid4().hex[:8]
        self.node_id = f"{hostname}_{random_part}"

        # Node info
        self.node_info = self._create_node_info()

        # Cluster state
        self.cluster_state: Optional[ClusterState] = None

        # State lock for thread safety
        self.state_lock = asyncio.Lock()

        # Election lock for leader election
        self.election_lock = asyncio.Lock()

        # Initialization flag
        self.initialized = False

        # Tasks
        self.heartbeat_task = None
        self.health_check_task = None
        self.state_sync_task = None
        self.failover_monitor_task = None

        # Persistent state file
        self.state_file = "/tmp/ipfs_kit/mcp/ha/cluster_state.json"

        # HTTP session for communication
        self.http_session: Optional[aiohttp.ClientSession] = None

        # Service registry
        self.local_services: Dict[str, ServiceInfo] = {}

        # Callbacks
        self.role_change_callbacks: List[Callable[[str], Any]] = []
        self.node_status_callbacks: List[Callable[[str, str], Any]] = []
        self.failover_callbacks: List[Callable[[FailoverEvent], Any]] = []

        # Register with FastAPI app if provided
        if app:
            self.register_with_app(app)

    def _create_node_info(self) -> NodeInfo:
        """
        Create information for this node.

        Returns:
            NodeInfo object for this node
        """
        # Get IP address
        ip_address = self._get_ip_address()

        # Get region and zone from environment variables if available
        region = os.environ.get("MCP_REGION")
        zone = os.environ.get("MCP_ZONE")

        # Determine port
        port = int(os.environ.get("MCP_PORT", "8000"))

        # Create node info
        return NodeInfo(
            node_id=self.node_id,
            hostname=socket.gethostname(),
            ip_address=ip_address,
            port=port,
            region=region,
            zone=zone,
            role="worker",  # Start as worker, will be updated during election
            status="starting",
            capabilities=["storage", "api", "routing"],
            start_time=time.time(),
            last_heartbeat=time.time(),
        )

    def _get_ip_address(self) -> str:
        """
        Get the IP address of this node.

        Returns:
            IP address as string
        """
        try:
            # Try to get the IP address that would be used to connect to the Internet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            # Fallback to hostname resolution
            return socket.gethostbyname(socket.gethostname())

    def register_with_app(self, app: FastAPI):
        """
        Register handlers with a FastAPI application.

        Args:
            app: FastAPI application
        """
        self.app = app

        # Add health check endpoint
        @app.get("/api/v0/ha/health")
        async def health_check():
            return {
                "status": "healthy",
                "node_id": self.node_id,
                "role": self.node_info.role,
                "timestamp": time.time(),
            }

        # Add status endpoint
        @app.get("/api/v0/ha/status")
        async def ha_status():
            return {
                "status": self.node_info.status,
                "node_id": self.node_id,
                "role": self.node_info.role,
                "cluster_id": self.cluster_state.config.cluster_id if self.cluster_state else None,
                "primary_node": self.cluster_state.primary_node_id if self.cluster_state else None,
                "is_primary": self.node_info.role == "primary",
                "node_count": len(self.cluster_state.nodes) if self.cluster_state else 0,
                "service_count": len(self.cluster_state.services) if self.cluster_state else 0,
                "uptime": time.time() - self.node_info.start_time,
            }

        # Add cluster info endpoint
        @app.get("/api/v0/ha/cluster")
        async def cluster_info():
            if not self.cluster_state:
                return {"status": "initializing", "node_id": self.node_id}

            return {
                "cluster_id": self.cluster_state.config.cluster_id,
                "cluster_name": self.cluster_state.config.cluster_name,
                "primary_node": self.cluster_state.primary_node_id,
                "nodes": {
                    node_id: {
                        "hostname": node.hostname,
                        "ip_address": node.ip_address,
                        "port": node.port,
                        "region": node.region,
                        "zone": node.zone,
                        "role": node.role,
                        "status": node.status,
                        "last_heartbeat": node.last_heartbeat,
                    }
                    for node_id, node in self.cluster_state.nodes.items()
                },
                "services": {
                    service_id: {
                        "name": service.name,
                        "status": service.status,
                        "node_id": service.node_id,
                        "endpoints": service.endpoints,
                    }
                    for service_id, service in self.cluster_state.services.items()
                },
                "version": self.cluster_state.version.dict(),
            }

        # Add join endpoint for new nodes
        @app.post("/api/v0/ha/join")
        async def join_request(node: NodeInfo, background_tasks: BackgroundTasks):
            if not self.cluster_state:
                return {"status": "error", "message": "Cluster not initialized"}

            # Only the primary can accept join requests
            if self.node_info.role != "primary":
                return {
                    "status": "redirect",
                    "primary_node": self.cluster_state.primary_node_id,
                    "message": "Please join through the primary node",
                }

            # Add node to cluster
            async with self.state_lock:
                if node.node_id in self.cluster_state.nodes:
                    # Update existing node
                    existing_node = self.cluster_state.nodes[node.node_id]
                    existing_node.ip_address = node.ip_address
                    existing_node.port = node.port
                    existing_node.status = "active"
                    existing_node.last_heartbeat = time.time()
                    existing_node.capabilities = node.capabilities
                else:
                    # Add new node
                    node.role = "worker"  # Force role to worker for new nodes
                    node.status = "active"
                    node.last_heartbeat = time.time()
                    self.cluster_state.nodes[node.node_id] = node

                # Update version
                self.cluster_state.version.version += 1
                self.cluster_state.version.timestamp = time.time()
                self.cluster_state.version.updated_by = self.node_id

            # Schedule state update to propagate to all nodes
            background_tasks.add_task(self._propagate_state_update)

            return {
                "status": "success",
                "message": "Node joined successfully",
                "cluster_id": self.cluster_state.config.cluster_id,
                "cluster_state": self.cluster_state.dict(),
            }

        # Add heartbeat endpoint
        @app.post("/api/v0/ha/heartbeat")
        async def heartbeat(
            node_id: str
            status: Optional[str] = None,
            load: Optional[Dict[str, float]] = None,
        ):
            if not self.cluster_state or node_id not in self.cluster_state.nodes:
                return {"status": "error", "message": "Node not in cluster"}

            # Update node heartbeat
            async with self.state_lock:
                node = self.cluster_state.nodes[node_id]
                node.last_heartbeat = time.time()

                if status:
                    # If status was downgraded, log it
                    if status in ["degraded", "failed"] and node.status != status:
                        logger.warning(f"Node {node_id} status changed to {status}")

                    node.status = status

                if load:
                    node.load = load

            return {"status": "success", "timestamp": time.time()}

        # Add state sync endpoint
        @app.post("/api/v0/ha/sync")
        async def sync_state(state: ClusterState, background_tasks: BackgroundTasks):
            if not self.cluster_state:
                # Initialize from received state
                self.cluster_state = state
                return {"status": "success", "message": "State initialized"}

            # Only accept newer versions
            if state.version.version <= self.cluster_state.version.version:
                return {
                    "status": "rejected",
                    "message": "Local state is newer",
                    "local_version": self.cluster_state.version.version,
                    "received_version": state.version.version,
                }

            # Apply the new state
            async with self.state_lock:
                old_role = (
                    self.node_info.role if self.node_id in self.cluster_state.nodes else "unknown"
                )
                old_primary = self.cluster_state.primary_node_id

                # Update cluster state
                self.cluster_state = state

                # Update our node info in the state
                if self.node_id in self.cluster_state.nodes:
                    # Preserve our role and status
                    new_role = self.cluster_state.nodes[self.node_id].role
                    self.cluster_state.nodes[self.node_id] = self.node_info
                    self.node_info.role = new_role
                    self.node_info.last_heartbeat = time.time()
                else:
                    # We're not in the state, add ourselves
                    self.cluster_state.nodes[self.node_id] = self.node_info

            # Check for role changes
            new_role = self.node_info.role
            if old_role != new_role:
                await self._handle_role_change(old_role, new_role)

            # Check for primary node changes
            if old_primary != self.cluster_state.primary_node_id:
                logger.info(
                    f"Primary node changed from {old_primary} to {self.cluster_state.primary_node_id}"
                )

            # Save state to persistent storage
            background_tasks.add_task(self._save_state)

            return {"status": "success", "message": "State synchronized"}

        # Add failover endpoint
        @app.post("/api/v0/ha/failover")
        async def trigger_failover(
            forced: bool = False,
            target_node: Optional[str] = None,
            reason: str = "Manual failover",
        ):
            if not self.cluster_state:
                return {"status": "error", "message": "Cluster not initialized"}

            # Only the primary can trigger an orderly failover
            if not forced and self.node_info.role != "primary":
                return {
                    "status": "error",
                    "message": "Only the primary node can trigger a normal failover",
                }

            result = await self._perform_failover(forced, target_node, reason)
            return result

    async def start(self):
        """Start the high availability service."""
        if self.initialized:
            return

        logger.info(f"Starting high availability service on node {self.node_id}")

        # Create data directories
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

        # Create HTTP session
        self.http_session = aiohttp.ClientSession()

        # Initialize our node
        self.node_info.status = "active"

        # Load or initialize cluster state
        await self._load_or_init_state()

        # Start tasks
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        self.state_sync_task = asyncio.create_task(self._state_sync_loop())
        self.failover_monitor_task = asyncio.create_task(self._failover_monitor_loop())

        # Set up signal handlers for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._setup_signal_handler(sig)

        self.initialized = True
        logger.info(f"High availability service started on node {self.node_id}")

    def _setup_signal_handler(self, sig):
        """
        Set up a signal handler for graceful shutdown.

        Args:
            sig: Signal to handle
        """

        def handler():
            asyncio.create_task(self.stop())

        try:
            # Get the running event loop
            loop = asyncio.get_running_loop()
            # Add signal handler to the loop
            loop.add_signal_handler(sig, handler)
        except (NotImplementedError, RuntimeError):
            # Fallback for systems that don't support add_signal_handler
            signal.signal(sig, lambda s, f: asyncio.create_task(self.stop()))

    async def stop(self):
        """Stop the high availability service."""
        if not self.initialized:
            return

        logger.info(f"Stopping high availability service on node {self.node_id}")

        # Cancel tasks
        for task in [
            self.heartbeat_task,
            self.health_check_task,
            self.state_sync_task,
            self.failover_monitor_task,
        ]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # If we're the primary, try to hand off
        if self.node_info.role == "primary":
            await self._hand_off_primary_role()

        # Update node status to indicate shutdown
        self.node_info.status = "shutdown"
        if self.cluster_state and self.node_id in self.cluster_state.nodes:
            async with self.state_lock:
                self.cluster_state.nodes[self.node_id].status = "shutdown"

                # Update version
                self.cluster_state.version.version += 1
                self.cluster_state.version.timestamp = time.time()
                self.cluster_state.version.updated_by = self.node_id

            # Propagate state update
            await self._propagate_state_update()

        # Save final state
        await self._save_state()

        # Close HTTP session
        if self.http_session:
            await self.http_session.close()
            self.http_session = None

        self.initialized = False
        logger.info(f"High availability service stopped on node {self.node_id}")

    async def _load_or_init_state(self):
        """Load existing state or initialize a new cluster."""
        # Try to load state from file
        try:
            state_loaded = await self._load_state()
            if state_loaded:
                logger.info(f"Loaded cluster state from {self.state_file}")

                # Add ourselves to the node list if not present
                if self.node_id not in self.cluster_state.nodes:
                    self.cluster_state.nodes[self.node_id] = self.node_info

                    # Update version
                    self.cluster_state.version.version += 1
                    self.cluster_state.version.timestamp = time.time()
                    self.cluster_state.version.updated_by = self.node_id

                return
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")

        # Try to join an existing cluster
        try:
            joined = await self._join_existing_cluster()
            if joined:
                logger.info("Joined existing cluster")
                return
        except Exception as e:
            logger.warning(f"Failed to join existing cluster: {e}")

        # Initialize a new cluster if we couldn't load or join
        await self._init_new_cluster()

    async def _load_state(self) -> bool:
        """
        Load cluster state from persistent storage.

        Returns:
            True if state was loaded successfully
        """
        if not os.path.exists(self.state_file):
            return False

        try:
            import aiofiles

            async with aiofiles.open(self.state_file, "r") as f:
                data = await f.read()
                state_dict = json.loads(data)

                # Convert dict to ClusterState
                self.cluster_state = ClusterState(**state_dict)

                # Update our node in the state
                if self.node_id in self.cluster_state.nodes:
                    # Keep the role from the saved state
                    self.node_info.role = self.cluster_state.nodes[self.node_id].role
                    self.cluster_state.nodes[self.node_id] = self.node_info

                return True
        except Exception as e:
            logger.error(f"Error loading state file: {e}")
            return False

    async def _save_state(self):
        """Save cluster state to persistent storage."""
        if not self.cluster_state:
            return

        try:
            import aiofiles

            async with aiofiles.open(self.state_file, "w") as f:
                state_json = json.dumps(self.cluster_state.dict(), indent=2)
                await f.write(state_json)
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    async def _join_existing_cluster(self) -> bool:
        """
        Attempt to join an existing cluster.

        Returns:
            True if successfully joined a cluster
        """
        # Get cluster coordinator nodes from environment
        coordinator_hosts = os.environ.get("MCP_CLUSTER_HOSTS", "").split(",")
        if not coordinator_hosts or coordinator_hosts[0] == "":
            return False

        # Try to join the cluster through each coordinator
        for host in coordinator_hosts:
            try:
                # Clean up the host string
                host = host.strip()
                if not host:
                    continue

                # Add default port if not specified
                if ":" not in host:
                    host = f"{host}:8000"

                # Get cluster info
                async with self.http_session.get(f"http://{host}/api/v0/ha/cluster") as response:
                    if response.status != 200:
                        continue

                    cluster_info = await response.json()

                    # If the node is still initializing, skip it
                    if cluster_info.get("status") == "initializing":
                        continue

                    # Get the primary node
                    primary_node_id = cluster_info.get("primary_node")
                    if not primary_node_id:
                        continue

                    # Find the primary node address
                    nodes = cluster_info.get("nodes", {})
                    if primary_node_id not in nodes:
                        continue

                    primary_node = nodes[primary_node_id]
                    primary_address = f"{primary_node['ip_address']}:{primary_node['port']}"

                    # Join through the primary node
                    return await self._join_through_primary(primary_address)
            except Exception as e:
                logger.warning(f"Failed to join through coordinator {host}: {e}")

        return False

    async def _join_through_primary(self, primary_address: str) -> bool:
        """
        Join a cluster through its primary node.

        Args:
            primary_address: Primary node's address (ip:port)

        Returns:
            True if successfully joined
        """
        try:
            # Send join request
            async with self.http_session.post(
                f"http://{primary_address}/api/v0/ha/join", json=self.node_info.dict()
            ) as response:
                data = await response.json()

                if data.get("status") == "success":
                    # Get full cluster state
                    self.cluster_state = ClusterState(**data.get("cluster_state"))

                    # Ensure our node is in the state
                    if self.node_id not in self.cluster_state.nodes:
                        self.cluster_state.nodes[self.node_id] = self.node_info

                    # Update our role
                    self.node_info.role = self.cluster_state.nodes[self.node_id].role

                    # Save state
                    await self._save_state()

                    return True
                elif data.get("status") == "redirect":
                    # We got redirected to another node
                    new_primary = data.get("primary_node")
                    if new_primary in self.cluster_state.nodes:
                        node = self.cluster_state.nodes[new_primary]
                        primary_address = f"{node.ip_address}:{node.port}"
                        return await self._join_through_primary(primary_address)

                return False
        except Exception as e:
            logger.error(f"Error joining through primary {primary_address}: {e}")
            return False

    async def _init_new_cluster(self):
        """Initialize a new cluster."""
        logger.info("Initializing new cluster")

        # Load config if available
        config = await self._load_config()

        # Generate cluster ID
        cluster_id = f"mcp_cluster_{uuid.uuid4().hex[:8]}"

        # Create cluster state
        state_version = StateVersion(version=1, timestamp=time.time(), updated_by=self.node_id)

        cluster_config = config or ClusterConfig(
            cluster_id=cluster_id,
            cluster_name="MCP Cluster",
            primary_selection="auto",
            heartbeat_interval=10,
            failover_timeout=30,
            quorum_size=1,  # Start with quorum of 1 since we're alone
            replication_factor=1,  # Start with replication of 1
        )

        # Set ourselves as the primary node initially
        self.node_info.role = "primary"

        self.cluster_state = ClusterState(
            version=state_version,
            nodes={self.node_id: self.node_info},
            services={},
            config=cluster_config,
            primary_node_id=self.node_id,
        )

        # Save initial state
        await self._save_state()

        logger.info(f"Initialized new cluster {cluster_id} with this node as primary")

    async def _load_config(self) -> Optional[ClusterConfig]:
        """
        Load cluster configuration from file.

        Returns:
            ClusterConfig object or None if not found
        """
        if not os.path.exists(self.config_path):
            return None

        try:
            import aiofiles

            async with aiofiles.open(self.config_path, "r") as f:
                data = await f.read()
                config_dict = json.loads(data)
                return ClusterConfig(**config_dict)
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            return None

    async def _heartbeat_loop(self):
        """Send heartbeat periodically to keep node active in the cluster."""
        while True:
            try:
                if self.cluster_state:
                    # Skip if we're the only node
                    if len(self.cluster_state.nodes) > 1:
                        # Update our load metrics
                        self.node_info.load = await self._get_load_metrics()

                        # If we're the primary, update the state directly
                        if self.node_info.role == "primary":
                            async with self.state_lock:
                                self.cluster_state.nodes[self.node_id].last_heartbeat = time.time()
                                self.cluster_state.nodes[self.node_id].load = self.node_info.load
                        else:
                            # Send heartbeat to primary
                            primary_node = self._get_primary_node()
                            if primary_node:
                                try:
                                    primary_address = (
                                        f"{primary_node.ip_address}:{primary_node.port}"
                                    )
                                    async with self.http_session.post(
                                        f"http://{primary_address}/api/v0/ha/heartbeat",
                                        params={
                                            "node_id": self.node_id,
                                            "status": self.node_info.status,
                                        },
                                        json=self.node_info.load,
                                    ) as response:
                                        if response.status != 200:
                                            logger.warning(
                                                f"Failed to send heartbeat: {response.status}"
                                            )
                                except Exception as e:
                                    logger.warning(f"Error sending heartbeat: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

            # Sleep for heartbeat interval
            interval = self.cluster_state.config.heartbeat_interval if self.cluster_state else 10
            await asyncio.sleep(interval)

    async def _get_load_metrics(self) -> Dict[str, float]:
        """
        Get load metrics for this node.

        Returns:
            Dictionary of load metrics
        """
        try:
            import psutil

            # Get CPU and memory metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Get disk metrics for root path
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent

            return {
                "cpu": cpu_percent,
                "memory": memory_percent,
                "disk": disk_percent,
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.error(f"Error getting load metrics: {e}")
            return {"cpu": 0.0, "memory": 0.0, "disk": 0.0, "timestamp": time.time()}

    def _get_primary_node(self) -> Optional[NodeInfo]:
        """
        Get the current primary node info.

        Returns:
            NodeInfo for the primary node or None if not found
        """
        if not self.cluster_state or not self.cluster_state.primary_node_id:
            return None

        primary_id = self.cluster_state.primary_node_id
        return self.cluster_state.nodes.get(primary_id)

    async def _health_check_loop(self):
        """Perform health checks for all nodes and services."""
        while True:
            try:
                if self.cluster_state and self.node_info.role == "primary":
                    await self._check_node_health()
                    await self._check_service_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

            # Sleep for a portion of the heartbeat interval
            interval = (
                self.cluster_state.config.heartbeat_interval if self.cluster_state else 10
            ) / 2
            await asyncio.sleep(interval)

    async def _check_node_health(self):
        """Check health of all nodes in the cluster."""
        if not self.cluster_state:
            return

        current_time = time.time()
        failover_timeout = self.cluster_state.config.failover_timeout

        async with self.state_lock:
            state_updated = False

            # Check each node
            for node_id, node in list(self.cluster_state.nodes.items()):
                # Skip ourselves
                if node_id == self.node_id:
                    continue

                # Check last heartbeat
                time_since_heartbeat = current_time - node.last_heartbeat

                if time_since_heartbeat > failover_timeout:
                    if node.status != "failed":
                        logger.warning(
                            f"Node {node_id} marked as failed (no heartbeat for {time_since_heartbeat:.1f}s)"
                        )
                        node.status = "failed"
                        state_updated = True

                        # Call status change callbacks
                        for callback in self.node_status_callbacks:
                            try:
                                callback(node_id, "failed")
                            except Exception as e:
                                logger.error(f"Error in node status callback: {e}")
                elif time_since_heartbeat > failover_timeout / 2:
                    if node.status == "active":
                        logger.warning(
                            f"Node {node_id} marked as degraded (slow heartbeat: {time_since_heartbeat:.1f}s)"
                        )
                        node.status = "degraded"
                        state_updated = True

                        # Call status change callbacks
                        for callback in self.node_status_callbacks:
                            try:
                                callback(node_id, "degraded")
                            except Exception as e:
                                logger.error(f"Error in node status callback: {e}")

            if state_updated:
                # Update version
                self.cluster_state.version.version += 1
                self.cluster_state.version.timestamp = time.time()
                self.cluster_state.version.updated_by = self.node_id

                # Save and propagate state update
                await self._save_state()
                await self._propagate_state_update()

    async def _check_service_health(self):
        """Check health of all services in the cluster."""
        if not self.cluster_state:
            return

        # As the primary, check all services
        async with self.state_lock:
            state_updated = False

            # Check each service
            for service_id, service in list(self.cluster_state.services.items()):
                # Check if service's node is healthy
                node_id = service.node_id
                if node_id not in self.cluster_state.nodes:
                    # Node doesn't exist, mark service as failed
                    if service.status != "failed":
                        service.status = "failed"
                        state_updated = True
                    continue

                node = self.cluster_state.nodes[node_id]
                if node.status in ["failed", "shutdown"]:
                    # Node is unhealthy, mark service as failed
                    if service.status != "failed":
                        service.status = "failed"
                        state_updated = True
                    continue

                # For services running on this node, we can update directly
                if node_id == self.node_id and service_id in self.local_services:
                    # Use the local service status
                    local_status = self.local_services[service_id].status
                    if service.status != local_status:
                        service.status = local_status
                        state_updated = True
                else:
                    # For remote services, we could check them via HTTP if they have a health check endpoint
                    if service.health_check and node.status == "active":
                        try:
                            # Construct the health check URL
                            service_url = (
                                f"http://{node.ip_address}:{node.port}{service.health_check}"
                            )

                            # Perform health check
                            async with self.http_session.get(service_url, timeout=5) as response:
                                if response.status != 200:
                                    if service.status != "degraded":
                                        service.status = "degraded"
                                        state_updated = True
                                else:
                                    # Service is healthy
                                    if service.status != "active":
                                        service.status = "active"
                                        state_updated = True
                        except Exception as e:
                            logger.warning(f"Error checking service {service_id} health: {e}")
                            if service.status != "degraded":
                                service.status = "degraded"
                                state_updated = True

            if state_updated:
                # Update version
                self.cluster_state.version.version += 1
                self.cluster_state.version.timestamp = time.time()
                self.cluster_state.version.updated_by = self.node_id

                # Save and propagate state update
                await self._save_state()
                await self._propagate_state_update()

    async def _state_sync_loop(self):
        """Synchronize cluster state periodically with other nodes."""
        while True:
            try:
                if self.cluster_state and len(self.cluster_state.nodes) > 1:
                    # If we're the primary, propagate our state to others
                    if self.node_info.role == "primary":
                        await self._propagate_state_update()
                    else:
                        # If we're not the primary, sync from the primary
                        await self._sync_from_primary()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in state sync loop: {e}")

            # Sleep for a sync interval (use a fraction of heartbeat interval)
            interval = (
                self.cluster_state.config.heartbeat_interval if self.cluster_state else 10
            ) * 2
            await asyncio.sleep(interval)

    async def _propagate_state_update(self):
        """Propagate state updates to all active nodes in the cluster."""
        if not self.cluster_state:
            return

        # Only the primary should propagate state updates
        if self.node_info.role != "primary":
            return

        # Get local copy of state to avoid holding lock during HTTP requests
        async with self.state_lock:
            state = self.cluster_state

        # Send state to all active nodes except ourselves
        for node_id, node in state.nodes.items():
            if node_id == self.node_id or node.status in ["failed", "shutdown"]:
                continue

            try:
                # Send state update
                node_address = f"{node.ip_address}:{node.port}"
                async with self.http_session.post(
                    f"http://{node_address}/api/v0/ha/sync", json=state.dict()
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to sync state to node {node_id}: {response.status}")
            except Exception as e:
                logger.warning(f"Error syncing state to node {node_id}: {e}")

    async def _sync_from_primary(self):
        """Synchronize state from the primary node."""
        if not self.cluster_state:
            return

        # Get the primary node
        primary_node = self._get_primary_node()
        if not primary_node or primary_node.node_id == self.node_id:
            return

        try:
            # Get state from primary
            primary_address = f"{primary_node.ip_address}:{primary_node.port}"
            async with self.http_session.get(
                f"http://{primary_address}/api/v0/ha/cluster"
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to get state from primary: {response.status}")
                    return

                data = await response.json()

                # If we get a newer version, synchronize
                current_version = self.cluster_state.version.version
                remote_version = data.get("version", {}).get("version", 0)

                if remote_version > current_version:
                    # Get full state and synchronize
                    async with self.http_session.post(
                        f"http://{primary_address}/api/v0/ha/sync",
                        json=self.cluster_state.dict(),
                    ) as sync_response:
                        if sync_response.status != 200:
                            logger.warning(f"Failed to sync with primary: {sync_response.status}")
        except Exception as e:
            logger.warning(f"Error syncing from primary: {e}")

    async def _failover_monitor_loop(self):
        """Monitor for primary node failures and trigger failover if needed."""
        while True:
            try:
                if self.cluster_state and self.node_info.role != "primary":
                    # Check if primary node is healthy
                    primary_node_id = self.cluster_state.primary_node_id

                    if primary_node_id and primary_node_id in self.cluster_state.nodes:
                        primary_node = self.cluster_state.nodes[primary_node_id]

                        # Check if primary is failed or shutdown
                        if primary_node.status in ["failed", "shutdown"]:
                            logger.warning(
                                f"Primary node {primary_node_id} is {primary_node.status}, initiating failover"
                            )

                            # Attempt to elect a new primary
                            await self._elect_new_primary(
                                f"Primary node {primary_node_id} is {primary_node.status}"
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in failover monitor loop: {e}")

            # Sleep for a failover check interval
            interval = (
                self.cluster_state.config.heartbeat_interval if self.cluster_state else 10
            ) / 2
            await asyncio.sleep(interval)

    async def _elect_new_primary(self, reason: str):
        """
        Elect a new primary node.

        Args:
            reason: Reason for election
        """
        if not self.cluster_state:
            return

        # Only perform election if not already in progress
        async with self.election_lock:
            # Check if primary has already changed
            if self.node_info.role == "primary":
                return

            # Get active nodes
            active_nodes = {}
            for node_id, node in self.cluster_state.nodes.items():
                if node.status == "active" and node_id != self.cluster_state.primary_node_id:
                    active_nodes[node_id] = node

            # Need at least quorum_size nodes for election
            if len(active_nodes) < self.cluster_state.config.quorum_size:
                logger.warning(
                    f"Not enough active nodes for election: {len(active_nodes)} < {self.cluster_state.config.quorum_size}"
                )
                return

            # Determine election strategy
            strategy = self.cluster_state.config.primary_selection

            # Select new primary
            new_primary_id = None

            if strategy == "manual":
                # In manual mode, we don't automatically elect a new primary
                logger.warning("Manual primary selection mode, not electing new primary")
                return

            # Choose based on lowest load, highest uptime
            candidates = []
            for node_id, node in active_nodes.items():
                # Calculate a score based on load and uptime
                uptime = time.time() - node.start_time
                cpu_load = node.load.get("cpu", 50) if node.load else 50

                # Higher score is better
                score = uptime / 3600 - cpu_load / 10

                candidates.append((node_id, score))

            # Sort by score (highest first)
            candidates.sort(key=lambda x: x[1], reverse=True)

            if candidates:
                new_primary_id = candidates[0][0]

            # If we still don't have a primary, use ourselves
            if not new_primary_id:
                new_primary_id = self.node_id

            # Perform the failover
            if new_primary_id:
                start_time = time.time()

                # Create failover event
                event_id = f"failover_{uuid.uuid4().hex[:8]}"
                old_primary_id = self.cluster_state.primary_node_id

                event = FailoverEvent(
                    event_id=event_id,
                    timestamp=start_time,
                    old_primary=old_primary_id,
                    new_primary=new_primary_id,
                    reason=reason,
                    detected_by=self.node_id,
                )

                # Update cluster state with new primary
                async with self.state_lock:
                    # Update primary node
                    self.cluster_state.primary_node_id = new_primary_id

                    # Update node roles
                    for node_id, node in self.cluster_state.nodes.items():
                        if node_id == new_primary_id:
                            node.role = "primary"
                        elif node.role == "primary":
                            node.role = "secondary"

                    # Add failover event
                    event.recovery_time = time.time() - start_time
                    self.cluster_state.failover_history.append(event)

                    # Update version
                    self.cluster_state.version.version += 1
                    self.cluster_state.version.timestamp = time.time()
                    self.cluster_state.version.updated_by = self.node_id

                # Update our role if we're the new primary
                if new_primary_id == self.node_id:
                    old_role = self.node_info.role
                    self.node_info.role = "primary"

                    # Handle role change
                    await self._handle_role_change(old_role, "primary")

                    logger.info(f"This node elected as new primary after failover: {event_id}")
                else:
                    logger.info(
                        f"Node {new_primary_id} elected as new primary after failover: {event_id}"
                    )

                # Save and propagate state update
                await self._save_state()
                await self._propagate_state_update()

                # Call failover callbacks
                for callback in self.failover_callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error in failover callback: {e}")

    async def _handle_role_change(self, old_role: str, new_role: str):
        """
        Handle role change for this node.

        Args:
            old_role: Previous role
            new_role: New role
        """
        logger.info(f"Node role changed from {old_role} to {new_role}")

        # Call role change callbacks
        for callback in self.role_change_callbacks:
            try:
                callback(new_role)
            except Exception as e:
                logger.error(f"Error in role change callback: {e}")

    async def _perform_failover(
        self, forced: bool, target_node: Optional[str], reason: str
    ) -> Dict[str, Any]:
        """
        Perform a manual failover to a new primary node.

        Args:
            forced: Whether this is a forced failover
            target_node: Target node to become primary, or None for automatic selection
            reason: Reason for failover

        Returns:
            Dictionary with failover result
        """
        if not self.cluster_state:
            return {"status": "error", "message": "Cluster not initialized"}

        # For non-forced failover, only the primary can initiate
        if not forced and self.node_info.role != "primary":
            return {
                "status": "error",
                "message": "Only the primary node can trigger a normal failover",
            }

        # Validate target node if specified
        if target_node and target_node not in self.cluster_state.nodes:
            return {
                "status": "error",
                "message": f"Target node {target_node} not found in cluster",
            }

        if target_node and self.cluster_state.nodes[target_node].status != "active":
            return {
                "status": "error",
                "message": f"Target node {target_node} is not active",
            }

        # Start failover process
        start_time = time.time()
        old_primary = self.cluster_state.primary_node_id

        # If target node is not specified, select one based on rules
        new_primary = target_node
        if not new_primary:
            # Find active nodes
            active_nodes = [
                node_id
                for node_id, node in self.cluster_state.nodes.items()
                if node.status == "active" and node_id != old_primary
            ]

            if active_nodes:
                # Choose first active node
                new_primary = active_nodes[0]
            else:
                return {
                    "status": "error",
                    "message": "No active nodes available for failover",
                }

        # Create failover event
        event_id = f"failover_{uuid.uuid4().hex[:8]}"
        event = FailoverEvent(
            event_id=event_id,
            timestamp=start_time,
            old_primary=old_primary,
            new_primary=new_primary,
            reason=reason,
            detected_by=self.node_id,
        )

        # Update cluster state
        async with self.state_lock:
            # Update primary node
            self.cluster_state.primary_node_id = new_primary

            # Update node roles
            for node_id, node in self.cluster_state.nodes.items():
                if node_id == new_primary:
                    node.role = "primary"
                elif node.role == "primary":
                    node.role = "secondary"

            # Add failover event
            event.recovery_time = time.time() - start_time
            self.cluster_state.failover_history.append(event)

            # Update version
            self.cluster_state.version.version += 1
            self.cluster_state.version.timestamp = time.time()
            self.cluster_state.version.updated_by = self.node_id

        # Update our role if needed
        if self.node_id == new_primary:
            old_role = self.node_info.role
            self.node_info.role = "primary"
            await self._handle_role_change(old_role, "primary")
        elif self.node_id == old_primary:
            old_role = self.node_info.role
            self.node_info.role = "secondary"
            await self._handle_role_change(old_role, "secondary")

        # Save and propagate state update
        await self._save_state()
        await self._propagate_state_update()

        # Call failover callbacks
        for callback in self.failover_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in failover callback: {e}")

        return {
            "status": "success",
            "message": f"Failover completed successfully to node {new_primary}",
            "event_id": event_id,
            "old_primary": old_primary,
            "new_primary": new_primary,
            "recovery_time": event.recovery_time,
        }

    async def _hand_off_primary_role(self):
        """Attempt to hand off primary role to another node during shutdown."""
        if not self.cluster_state or self.node_info.role != "primary":
            return

        # Find active nodes other than ourselves
        active_nodes = [
            node_id
            for node_id, node in self.cluster_state.nodes.items()
            if node.status == "active" and node_id != self.node_id
        ]

        if not active_nodes:
            logger.warning("No active nodes to hand off primary role to during shutdown")
            return

        # Select a new primary
        new_primary = active_nodes[0]

        # Perform failover
        result = await self._perform_failover(
            forced=True,
            target_node=new_primary,
            reason="Orderly shutdown of primary node",
        )

        if result.get("status") == "success":
            logger.info(f"Successfully handed off primary role to {new_primary}")
        else:
            logger.warning(f"Failed to hand off primary role: {result.get('message')}")

    def register_role_change_callback(self, callback: Callable[[str], Any]):
        """
        Register a callback for role changes.

        Args:
            callback: Function to call when role changes
        """
        self.role_change_callbacks.append(callback)

    def register_node_status_callback(self, callback: Callable[[str, str], Any]):
        """
        Register a callback for node status changes.

        Args:
            callback: Function to call when node status changes
        """
        self.node_status_callbacks.append(callback)

    def register_failover_callback(self, callback: Callable[[FailoverEvent], Any]):
        """
        Register a callback for failover events.

        Args:
            callback: Function to call when failover occurs
        """
        self.failover_callbacks.append(callback)

    def is_primary(self) -> bool:
        """
        Check if this node is the primary.

        Returns:
            True if this node is the primary
        """
        return self.node_info.role == "primary"

    def get_cluster_info(self) -> Dict[str, Any]:
        """
        Get information about the cluster.

        Returns:
            Dictionary with cluster information
        """
        if not self.cluster_state:
            return {"status": "initializing", "node_id": self.node_id}

        return {
            "cluster_id": self.cluster_state.config.cluster_id,
            "cluster_name": self.cluster_state.config.cluster_name,
            "primary_node": self.cluster_state.primary_node_id,
            "nodes": len(self.cluster_state.nodes),
            "services": len(self.cluster_state.services),
            "is_primary": self.node_info.role == "primary",
            "state_version": self.cluster_state.version.version,
            "node_role": self.node_info.role,
            "node_status": self.node_info.status,
        }

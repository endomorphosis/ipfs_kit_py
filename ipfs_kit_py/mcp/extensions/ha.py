"""
High Availability Architecture extension for MCP server.

This module implements enterprise-grade high availability features as specified
in the MCP roadmap Phase 2: Enterprise Features (Q4 2025).

Features:
- Multi-region deployment
- Automatic failover
- Load balancing
- Replication and consistency
"""

import os
import time
import json
import logging
import asyncio
import random
import socket
import uuid
import aiohttp
from enum import Enum
from typing import Dict, Any, Optional
from fastapi import (
from pydantic import BaseModel

APIRouter,
    HTTPException)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
CONFIG_FILE = "ha_config.json"
NODES_FILE = "ha_nodes.json"
REGIONS_FILE = "ha_regions.json"
EVENTS_FILE = "ha_events.json"

# Directory for high availability files
HA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ha_data")
os.makedirs(HA_DIR, exist_ok=True)

# Full paths
CONFIG_PATH = os.path.join(HA_DIR, CONFIG_FILE)
NODES_PATH = os.path.join(HA_DIR, NODES_FILE)
REGIONS_PATH = os.path.join(HA_DIR, REGIONS_FILE)
EVENTS_PATH = os.path.join(HA_DIR, EVENTS_FILE)

# Storage backend attributes - will be populated from the MCP server
storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "huggingface": {"available": False, "simulation": True},
    "s3": {"available": False, "simulation": True},
    "filecoin": {"available": False, "simulation": True},
    "storacha": {"available": False, "simulation": True},
    "lassie": {"available": False, "simulation": True},
}


# Node status enum
class NodeStatus(str, Enum):
    """Node status values."""
    ACTIVE = "active"
    STANDBY = "standby"
    UNAVAILABLE = "unavailable"
    STARTING = "starting"
    STOPPING = "stopping"
    MAINTENANCE = "maintenance"
    FAILED = "failed"


# Event type enum
class EventType(str, Enum):
    """High availability event types."""
    NODE_JOINED = "node_joined"
    NODE_LEFT = "node_left"
    LEADER_ELECTED = "leader_elected"
    FAILOVER_STARTED = "failover_started"
    FAILOVER_COMPLETED = "failover_completed"
    REGION_ADDED = "region_added"
    REGION_REMOVED = "region_removed"
    CONFIG_CHANGED = "config_changed"
    STATUS_CHANGED = "status_changed"
    HEARTBEAT_MISSING = "heartbeat_missing"
    HEARTBEAT_RESTORED = "heartbeat_restored"
    ERROR = "error"


# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "node_id": str(uuid.uuid4()),
    "node_name": f"node-{socket.gethostname()}",
    "region": "default",
    "role": "auto",  # auto, primary, replica, monitor
    "discovery": {
        "enabled": True,
        "method": "config",  # config, dns, multicast
        "interval_seconds": 30,
        "timeout_seconds": 10,
    },
    "heartbeat": {
        "interval_seconds": 5,
        "timeout_seconds": 15,
        "required_successful": 3,
    },
    "failover": {
        "enabled": True,
        "automatic": True,
        "timeout_seconds": 60,
        "max_failures": 3,
        "cooldown_seconds": 300,
    },
    "load_balancing": {
        "enabled": True,
        "method": "round_robin",  # round_robin, weighted, least_connections
        "weights": {},
    },
    "replication": {
        "enabled": True,
        "sync_interval_seconds": 300,
        "consistency_mode": "eventual",  # strict, eventual, quorum
        "max_lag_seconds": 60,
    },
    "health_check": {
        "enabled": True,
        "interval_seconds": 15,
        "timeout_seconds": 5,
        "endpoints": ["/api/v0/health"],
    },
    "regions": [{"id": "default", "name": "Default Region", "priority": 100}],
    "api": {"port": 9997, "protocol": "http"},
}


# Default node information
def create_default_node():
    """Create default node information."""
    return {
        "id": DEFAULT_CONFIG["node_id"],
        "name": DEFAULT_CONFIG["node_name"],
        "region": DEFAULT_CONFIG["region"],
        "role": DEFAULT_CONFIG["role"],
        "status": NodeStatus.STARTING,
        "api_url": f"{DEFAULT_CONFIG['api']['protocol']}://{socket.gethostname()}:{DEFAULT_CONFIG['api']['port']}",
        "version": "1.0.0",
        "heartbeat": {"last_seen": time.time(), "consecutive_failures": 0},
        "stats": {
            "uptime_seconds": 0,
            "start_time": time.time(),
            "load_average": 0.0,
            "memory_usage_percent": 0.0,
            "disk_usage_percent": 0.0,
        },
        "metadata": {},
    }


# Runtime data
config = DEFAULT_CONFIG.copy()
this_node = create_default_node()
known_nodes = {this_node["id"]: this_node}
regions = {region["id"]: region for region in DEFAULT_CONFIG["regions"]}
events = []
ha_status = {
    "initialized": False,
    "leader_id": None,
    "leader_region": None,
    "active_nodes": 0,
    "total_nodes": 0,
    "quorum": False,
    "last_failover": 0,
    "global_status": "initializing",
}
is_leader = False
http_session = None


# Data models
class HAStatus(BaseModel):
    """High availability status model."""
    enabled: bool
    initialized: bool
    leader_id: Optional[str]
    leader_name: Optional[str]
    leader_region: Optional[str]
    active_nodes: int
    total_nodes: int
    quorum: bool
    last_failover: float
    global_status: str
    this_node_id: str
    this_node_role: str
    this_node_status: str
    this_node_region: str


class HAConfig(BaseModel):
    """High availability configuration model."""
    enabled: bool
    node_name: str
    region: str
    role: str
    heartbeat_interval: int
    failover_enabled: bool
    failover_automatic: bool
    replication_enabled: bool
    replication_consistency: str
    load_balancing_enabled: bool
    load_balancing_method: str


class NodeInfo(BaseModel):
    """Node information model."""
    id: str
    name: str
    region: str
    role: str
    status: str
    api_url: str
    version: str
    last_seen: float
    uptime_seconds: int
    is_leader: bool


class RegionInfo(BaseModel):
    """Region information model."""
    id: str
    name: str
    priority: int
    nodes: int
    active_nodes: int
    has_leader: bool


class HAEvent(BaseModel):
    """High availability event model."""
    id: str
    event_type: str
    timestamp: float
    node_id: Optional[str] = None
    region_id: Optional[str] = None
    details: Dict[str, Any] = {}


class FailoverRequest(BaseModel):
    """Failover request model."""
    target_node_id: Optional[str] = None
    target_region_id: Optional[str] = None
    reason: str
    force: bool = False


class RegionConfig(BaseModel):
    """Region configuration model."""
    id: str
    name: str
    priority: int = 100


# Initialization functions
def initialize_config():
    """Initialize configuration from file or defaults."""
    global config, this_node
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                stored_config = json.load(f)

            # Update config with stored values but keep node_id
            node_id = config["node_id"]
            config.update(stored_config)
            config["node_id"] = node_id

            logger.info(f"Loaded HA configuration from {CONFIG_PATH}")
        else:
            # Generate a new configuration
            config = DEFAULT_CONFIG.copy()
            config["node_id"] = str(uuid.uuid4())
            config["node_name"] = f"node-{socket.gethostname()}-{config['node_id'][:8]}"

            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)

            logger.info(f"Created default HA configuration in {CONFIG_PATH}")

        # Update this node info based on config
        this_node["id"] = config["node_id"]
        this_node["name"] = config["node_name"]
        this_node["region"] = config["region"]
        this_node["role"] = config["role"]
        this_node["api_url"] = (
            f"{config['api']['protocol']}://{socket.gethostname()}:{config['api']['port']}"
        )

    except Exception as e:
        logger.error(f"Error initializing HA configuration: {e}")
        # Use defaults


def initialize_nodes():
    """Initialize nodes data from file."""
    global known_nodes, this_node
    try:
        if os.path.exists(NODES_PATH):
            with open(NODES_PATH, "r") as f:
                nodes_data = json.load(f)

            # Filter out old nodes (last seen > 24 hours ago)
            cutoff_time = time.time() - 86400
            known_nodes = {
                node_id: node
                for node_id, node in nodes_data.items()
                if node.get("heartbeat", {}).get("last_seen", 0) > cutoff_time
            }

            # Add or update this node
            known_nodes[this_node["id"]] = this_node

            logger.info(f"Loaded {len(known_nodes)} nodes from {NODES_PATH}")
        else:
            # Start with just this node
            known_nodes = {this_node["id"]: this_node}

            with open(NODES_PATH, "w") as f:
                json.dump(known_nodes, f, indent=2)

            logger.info(f"Created nodes data with this node in {NODES_PATH}")
    except Exception as e:
        logger.error(f"Error initializing nodes data: {e}")
        # Use defaults with just this node
        known_nodes = {this_node["id"]: this_node}


def initialize_regions():
    """Initialize regions data from file."""
    global regions
    try:
        if os.path.exists(REGIONS_PATH):
            with open(REGIONS_PATH, "r") as f:
                regions = json.load(f)

            logger.info(f"Loaded {len(regions)} regions from {REGIONS_PATH}")
        else:
            # Use default regions from config
            regions = {region["id"]: region for region in config["regions"]}

            with open(REGIONS_PATH, "w") as f:
                json.dump(regions, f, indent=2)

            logger.info(f"Created regions data with {len(regions)} regions in {REGIONS_PATH}")
    except Exception as e:
        logger.error(f"Error initializing regions data: {e}")
        # Use defaults
        regions = {region["id"]: region for region in config["regions"]}


def initialize_events():
    """Initialize events data from file."""
    global events
    try:
        if os.path.exists(EVENTS_PATH):
            with open(EVENTS_PATH, "r") as f:
                events_data = json.load(f)

            # Keep only recent events (last 24 hours)
            cutoff_time = time.time() - 86400
            events = [event for event in events_data if event.get("timestamp", 0) > cutoff_time]

            logger.info(f"Loaded {len(events)} recent events from {EVENTS_PATH}")
        else:
            # Start with empty events list
            events = []

            with open(EVENTS_PATH, "w") as f:
                json.dump(events, f, indent=2)

            logger.info(f"Created empty events list in {EVENTS_PATH}")
    except Exception as e:
        logger.error(f"Error initializing events data: {e}")
        # Use empty list
        events = []


def initialize_http_session():
    """Initialize HTTP session for inter-node communication."""
    global http_session
    try:
        if http_session is None:
            http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=config["discovery"]["timeout_seconds"])
            )
        logger.info("Initialized HTTP session for HA communication")
    except Exception as e:
        logger.error(f"Error initializing HTTP session: {e}")


# Save functions
def save_config():
    """Save configuration to file."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving HA configuration: {e}")


def save_nodes():
    """Save nodes data to file."""
    try:
        with open(NODES_PATH, "w") as f:
            json.dump(known_nodes, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving nodes data: {e}")


def save_regions():
    """Save regions data to file."""
    try:
        with open(REGIONS_PATH, "w") as f:
            json.dump(regions, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving regions data: {e}")


def save_events():
    """Save events data to file."""
    try:
        # Keep only recent events when saving
        cutoff_time = time.time() - 86400  # 24 hours
        recent_events = [event for event in events if event.get("timestamp", 0) > cutoff_time]

        with open(EVENTS_PATH, "w") as f:
            json.dump(recent_events, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving events data: {e}")


# Helper functions
def add_event(
    event_type: EventType
    node_id: str = None,
    region_id: str = None,
    details: Dict = None,
):
    """Add a high availability event to the event log."""
    event_id = f"evt_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    event = {
        "id": event_id,
        "event_type": event_type,
        "timestamp": time.time(),
        "node_id": node_id,
        "region_id": region_id,
        "details": details or {},
    }

    events.append(event)

    # Keep events list from growing too large
    if len(events) > 1000:
        # Remove oldest events
        events.sort(key=lambda e: e.get("timestamp", 0))
        events[:] = events[-1000:]

    # Periodic save
    if random.random() < 0.1:  # ~10% chance of saving on each event
        save_events()

    return event


def update_node_status(node_id: str, status: NodeStatus, details: Dict = None):
    """Update a node's status and add an event."""
    if node_id in known_nodes:
        old_status = known_nodes[node_id].get("status")
        known_nodes[node_id]["status"] = status

        # Add event if status changed
        if old_status != status:
            add_event(
                EventType.STATUS_CHANGED,
                node_id=node_id,
                details={
                    "old_status": old_status,
                    "new_status": status,
                    **(details or {}),
                },
            )

        # Save nodes data
        save_nodes()
        return True
    return False


def update_ha_status():
    """Update the high availability status."""
    global ha_status, is_leader

    # Count active nodes
    active_nodes = sum(
        1 for node in known_nodes.values() if node.get("status") == NodeStatus.ACTIVE
    )

    # Update status
    ha_status["active_nodes"] = active_nodes
    ha_status["total_nodes"] = len(known_nodes)
    ha_status["initialized"] = True

    # Calculate quorum (majority of total nodes)
    ha_status["quorum"] = active_nodes > len(known_nodes) / 2

    # Determine leader
    if not ha_status["leader_id"] or ha_status["leader_id"] not in known_nodes:
        elect_leader()

    # Update global status
    if not config["enabled"]:
        ha_status["global_status"] = "disabled"
    elif active_nodes == 0:
        ha_status["global_status"] = "unavailable"
    elif not ha_status["quorum"]:
        ha_status["global_status"] = "degraded"
    elif ha_status["leader_id"] is None:
        ha_status["global_status"] = "leaderless"
    else:
        ha_status["global_status"] = "healthy"

    # Update is_leader flag
    is_leader = ha_status["leader_id"] == this_node["id"]

    return ha_status


def elect_leader():
    """Elect a leader node."""
    global ha_status

    # Only elect a leader if HA is enabled
    if not config["enabled"]:
        ha_status["leader_id"] = None
        ha_status["leader_region"] = None
        return

    # Get active nodes
    active_nodes = [
        node for node in known_nodes.values() if node.get("status") == NodeStatus.ACTIVE
    ]

    if not active_nodes:
        ha_status["leader_id"] = None
        ha_status["leader_region"] = None
        return

    # Sort regions by priority
    sorted_regions = sorted(
        regions.values(),
        key=lambda r: r.get("priority", 100),
        reverse=True,  # Higher priority first
    )

    # First, try to find a node in highest priority region
    for region in sorted_regions:
        region_id = region["id"]
        region_nodes = [node for node in active_nodes if node.get("region") == region_id]

        if region_nodes:
            # Sort nodes by predetermined criteria
            sorted_nodes = sorted(
                region_nodes,
                key=lambda n: (
                    # Prefer nodes with role 'primary'
                    0 if n.get("role") == "primary" else 1,
                    # Then by uptime (higher uptime first)
                    -n.get("stats", {}).get("uptime_seconds", 0),
                    # Finally by ID for consistency
                    n.get("id", ""),
                ),
            )

            # Select the first node as leader
            leader_node = sorted_nodes[0]
            old_leader_id = ha_status["leader_id"]
            ha_status["leader_id"] = leader_node["id"]
            ha_status["leader_region"] = region_id

            # Add leader election event
            if old_leader_id != leader_node["id"]:
                add_event(
                    EventType.LEADER_ELECTED,
                    node_id=leader_node["id"],
                    region_id=region_id,
                    details={
                        "previous_leader": old_leader_id,
                        "election_reason": "normal_election",
                    },
                )

            return

    # If we reach here, no suitable leader found
    ha_status["leader_id"] = None
    ha_status["leader_region"] = None


async def check_node_health(node_id: str, node_info: Dict) -> bool:
    """Check if a node is healthy by making a health check request."""
    if not config["health_check"]["enabled"]:
        return True

    if node_id == this_node["id"]:
        # This node is always considered healthy from its own perspective
        return True

    api_url = node_info.get("api_url")
    if not api_url:
        return False

    # Try each health endpoint
    for endpoint in config["health_check"]["endpoints"]:
        health_url = f"{api_url}{endpoint}"

        try:
            async with http_session.get(
                health_url, timeout=config["health_check"]["timeout_seconds"]
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status", "").lower() in ["healthy", "ok", "active"]:
                        return True
        except Exception as e:
            logger.debug(f"Health check failed for node {node_id} at {health_url}: {e}")

    return False


async def send_heartbeat(node_id: str, node_info: Dict) -> bool:
    """Send a heartbeat to another node."""
    if node_id == this_node["id"]:
        # No need to send heartbeat to self
        return True

    api_url = node_info.get("api_url")
    if not api_url:
        return False

    heartbeat_url = f"{api_url}/api/v0/ha/heartbeat"
    heartbeat_data = {
        "node_id": this_node["id"],
        "timestamp": time.time(),
        "status": this_node["status"],
        "is_leader": is_leader,
    }

    try:
        async with http_session.post(
            heartbeat_url,
            json=heartbeat_data,
            timeout=config["heartbeat"]["timeout_seconds"],
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("success", False)
    except Exception as e:
        logger.debug(f"Failed to send heartbeat to node {node_id}: {e}")

    return False


async def discover_nodes():
    """Discover other nodes in the HA cluster."""
    if not config["discovery"]["enabled"] or not config["enabled"]:
        return

    method = config["discovery"]["method"]

    if method == "config":
        # Simply use the nodes already in configuration
        # This is mostly for testing or static clusters
        return

    elif method == "dns":
        # DNS-based discovery would use DNS SRV records
        # Not implemented in this basic version
        pass

    elif method == "multicast":
        # Multicast discovery would use UDP multicasting
        # Not implemented in this basic version
        pass

    # In a complete implementation, this would dynamically update known_nodes
    # based on the chosen discovery method


async def heartbeat_check():
    """Check for missing heartbeats and update node status."""
    now = time.time()

    for node_id, node in known_nodes.items():
        if node_id == this_node["id"]:
            # Skip self
            continue

        last_seen = node.get("heartbeat", {}).get("last_seen", 0)
        consecutive_failures = node.get("heartbeat", {}).get("consecutive_failures", 0)

        # Check if heartbeat is overdue
        if now - last_seen > config["heartbeat"]["timeout_seconds"]:
            # Increment failure count
            node["heartbeat"]["consecutive_failures"] = consecutive_failures + 1

            # If too many failures, mark node as unavailable
            if (
                node["heartbeat"]["consecutive_failures"]
                >= config["heartbeat"]["required_successful"]
            ):
                if node["status"] != NodeStatus.UNAVAILABLE:
                    update_node_status(
                        node_id,
                        NodeStatus.UNAVAILABLE,
                        details={"reason": "heartbeat_missing"},
                    )

                    # Add heartbeat missing event
                    add_event(
                        EventType.HEARTBEAT_MISSING,
                        node_id=node_id,
                        details={
                            "last_seen": last_seen,
                            "seconds_since": now - last_seen,
                        },
                    )

        # Check if health check is needed
        if (
            node["status"] == NodeStatus.UNAVAILABLE and random.random() < 0.2
        ):  # ~20% chance each round
            # Perform a health check to see if node has recovered
            is_healthy = await check_node_health(node_id, node)

            if is_healthy:
                # Node has recovered
                update_node_status(
                    node_id,
                    NodeStatus.ACTIVE,
                    details={"reason": "health_check_success"},
                )

                # Reset failure count
                node["heartbeat"]["consecutive_failures"] = 0

                # Add heartbeat restored event
                add_event(
                    EventType.HEARTBEAT_RESTORED,
                    node_id=node_id,
                    details={"recovery_method": "health_check"},
                )


async def handle_failover():
    """Handle automatic failover if leader node is unavailable."""
    if not config["failover"]["enabled"] or not config["failover"]["automatic"]:
        return

    leader_id = ha_status["leader_id"]

    # If no leader, attempt election
    if not leader_id:
        elect_leader()
        return

    # If this node is the leader, nothing to do
    if leader_id == this_node["id"]:
        return

    # Check if leader is unavailable
    if leader_id in known_nodes:
        leader_node = known_nodes[leader_id]

        if leader_node["status"] != NodeStatus.ACTIVE:
            # Leader is not active, check how long it's been since last failover
            now = time.time()
            time_since_failover = now - ha_status["last_failover"]

            if time_since_failover > config["failover"]["cooldown_seconds"]:
                await perform_failover(
                    reason="automatic_leader_unavailable",
                    target_node_id = None,  # Election will choose new leader
                )


async def perform_failover(reason: str, target_node_id: str = None, force: bool = False):
    """Perform a failover to a new leader node."""
    # Update failover timestamp
    ha_status["last_failover"] = time.time()

    # Add failover started event
    add_event(
        EventType.FAILOVER_STARTED,
        node_id=this_node["id"],
        details={
            "reason": reason,
            "target_node": target_node_id,
            "force": force,
            "old_leader": ha_status["leader_id"],
        },
    )

    # If target node specified, set as leader
    if target_node_id and (target_node_id in known_nodes):
        target_node = known_nodes[target_node_id]

        # Only use target if it's active or we're forcing
        if force or target_node["status"] == NodeStatus.ACTIVE:
            ha_status["leader_id"] = target_node_id
            ha_status["leader_region"] = target_node["region"]

            # Add leader elected event
            add_event(
                EventType.LEADER_ELECTED,
                node_id=target_node_id,
                region_id=target_node["region"],
                details={
                    "previous_leader": ha_status["leader_id"],
                    "election_reason": "manual_failover",
                },
            )
    else:
        # Otherwise run normal election
        elect_leader()

    # Add failover completed event
    add_event(
        EventType.FAILOVER_COMPLETED,
        node_id=this_node["id"],
        details={
            "new_leader": ha_status["leader_id"],
            "success": ha_status["leader_id"] is not None,
        },
    )

    # Return success if a leader was elected
    return ha_status["leader_id"] is not None


async def update_node_stats():
    """Update this node's statistics."""
    # Update basic stats
    this_node["stats"]["uptime_seconds"] = int(time.time() - this_node["stats"]["start_time"])

    # In a real implementation, these would use real system metrics
    this_node["stats"]["load_average"] = random.uniform(0.1, 1.0)
    this_node["stats"]["memory_usage_percent"] = random.uniform(20.0, 60.0)
    this_node["stats"]["disk_usage_percent"] = random.uniform(10.0, 70.0)

    # Update heartbeat
    this_node["heartbeat"]["last_seen"] = time.time()
    this_node["heartbeat"]["consecutive_failures"] = 0

    # Save nodes periodically
    if random.random() < 0.1:  # ~10% chance each update
        save_nodes()


async def check_replication_status():
    """Check replication status across the cluster."""
    if not config["replication"]["enabled"]:
        return

    # In a real implementation, this would check replication lag and consistency
    # across nodes, potentially triggering resynchronization if needed
    pass


# Background tasks
async def ha_background_task():
    """Main background task for high availability system."""
    while config["enabled"]:
        try:
            # Update this node's statistics
            await update_node_stats()

            # Update HA status
            update_ha_status()

            # Check for missing heartbeats
            await heartbeat_check()

            # Handle automatic failover
            await handle_failover()

            # Discover new nodes
            await discover_nodes()

            # Check replication status
            await check_replication_status()

            # Wait for next iteration
            await asyncio.sleep(config["heartbeat"]["interval_seconds"])
        except Exception as e:
            logger.error(f"Error in HA background task: {e}")
            await asyncio.sleep(config["heartbeat"]["interval_seconds"])


async def close_http_session():
    """Close the HTTP session."""
    global http_session
    if http_session:
        await http_session.close()
        http_session = None


# Create router
def create_ha_router(api_prefix: str) -> APIRouter:
    """Create FastAPI router for high availability endpoints."""
    router = APIRouter(prefix=f"{api_prefix}/ha", tags=["high_availability"])

    @router.get("/status")
    async def get_ha_status():
        """Get high availability status."""
        # Update HA status
        update_ha_status()

        # Get leader name if available
        leader_name = None
        if ha_status["leader_id"] and ha_status["leader_id"] in known_nodes:
            leader_name = known_nodes[ha_status["leader_id"]].get("name")

        status = HAStatus(
            enabled=config["enabled"],
            initialized=ha_status["initialized"],
            leader_id=ha_status["leader_id"],
            leader_name=leader_name,
            leader_region=ha_status["leader_region"],
            active_nodes=ha_status["active_nodes"],
            total_nodes=ha_status["total_nodes"],
            quorum=ha_status["quorum"],
            last_failover=ha_status["last_failover"],
            global_status=ha_status["global_status"],
            this_node_id=this_node["id"],
            this_node_role=this_node["role"],
            this_node_status=this_node["status"],
            this_node_region=this_node["region"],
        )

        return {"success": True, "status": status.dict()}

    @router.get("/config")
    async def get_ha_config():
        """Get high availability configuration."""
        ha_config = HAConfig(
            enabled=config["enabled"],
            node_name=config["node_name"],
            region=config["region"],
            role=config["role"],
            heartbeat_interval=config["heartbeat"]["interval_seconds"],
            failover_enabled=config["failover"]["enabled"],
            failover_automatic=config["failover"]["automatic"],
            replication_enabled=config["replication"]["enabled"],
            replication_consistency=config["replication"]["consistency_mode"],
            load_balancing_enabled=config["load_balancing"]["enabled"],
            load_balancing_method=config["load_balancing"]["method"],
        )

        return {"success": True, "config": ha_config.dict(), "full_config": config}

    @router.put("/config")
    async def update_ha_config(updated_config: HAConfig):
        """Update high availability configuration."""
        # Update config
        config["enabled"] = updated_config.enabled
        config["node_name"] = updated_config.node_name
        config["region"] = updated_config.region
        config["role"] = updated_config.role
        config["heartbeat"]["interval_seconds"] = updated_config.heartbeat_interval
        config["failover"]["enabled"] = updated_config.failover_enabled
        config["failover"]["automatic"] = updated_config.failover_automatic
        config["replication"]["enabled"] = updated_config.replication_enabled
        config["replication"]["consistency_mode"] = updated_config.replication_consistency
        config["load_balancing"]["enabled"] = updated_config.load_balancing_enabled
        config["load_balancing"]["method"] = updated_config.load_balancing_method

        # Update this node
        this_node["name"] = updated_config.node_name
        this_node["region"] = updated_config.region
        this_node["role"] = updated_config.role

        # Save changes
        save_config()
        save_nodes()

        # Add config changed event
        add_event(
            EventType.CONFIG_CHANGED,
            node_id=this_node["id"],
            details={"updated_fields": list(updated_config.dict().keys())},
        )

        return {"success": True, "message": "Configuration updated successfully"}

    @router.post("/heartbeat")
    async def receive_heartbeat(heartbeat: Dict[str, Any]):
        """Receive a heartbeat from another node."""
        node_id = heartbeat.get("node_id")
        timestamp = heartbeat.get("timestamp")
        status = heartbeat.get("status")

        if not node_id or not timestamp:
            return {"success": False, "error": "Invalid heartbeat data"}

        # If we don't know this node, add it to known_nodes
        if node_id not in known_nodes:
            # This would be expanded in a real implementation to request
            # full node info, but for simplicity we'll just create a basic entry
            known_nodes[node_id] = {
                "id": node_id,
                "name": f"node-{node_id[:8]}",
                "region": "unknown",
                "role": "unknown",
                "status": status or NodeStatus.ACTIVE,
                "api_url": None,  # Would need to be provided in a real system
                "version": "unknown",
                "heartbeat": {"last_seen": timestamp, "consecutive_failures": 0},
                "stats": {
                    "uptime_seconds": 0,
                    "start_time": time.time(),
                    "load_average": 0.0,
                    "memory_usage_percent": 0.0,
                    "disk_usage_percent": 0.0,
                },
                "metadata": {},
            }

            # Add node joined event
            add_event(EventType.NODE_JOINED, node_id=node_id, details={"timestamp": timestamp})
        else:
            # Update existing node
            known_nodes[node_id]["heartbeat"]["last_seen"] = timestamp
            known_nodes[node_id]["heartbeat"]["consecutive_failures"] = 0

            # Update status if provided
            if status:
                known_nodes[node_id]["status"] = status

        # Save nodes periodically
        if random.random() < 0.1:  # ~10% chance each heartbeat
            save_nodes()

        return {
            "success": True,
            "node_id": this_node["id"],
            "timestamp": time.time(),
            "status": this_node["status"],
            "is_leader": is_leader,
        }

    @router.get("/nodes")
    async def list_nodes():
        """List all known nodes in the HA cluster."""
        node_list = []

        for node_id, node in known_nodes.items():
            node_info = NodeInfo(
                id=node_id,
                name=node.get("name", f"node-{node_id[:8]}"),
                region=node.get("region", "unknown"),
                role=node.get("role", "unknown"),
                status=node.get("status", NodeStatus.UNAVAILABLE),
                api_url=node.get("api_url", ""),
                version=node.get("version", "unknown"),
                last_seen=node.get("heartbeat", {}).get("last_seen", 0),
                uptime_seconds=node.get("stats", {}).get("uptime_seconds", 0),
                is_leader=(node_id == ha_status["leader_id"]),
            )

            node_list.append(node_info.dict())

        return {"success": True, "nodes": node_list}

    @router.get("/regions")
    async def list_regions():
        """List all regions in the HA cluster."""
        region_list = []

        for region_id, region in regions.items():
            # Count nodes in this region
            region_nodes = [
                node for node in known_nodes.values() if node.get("region") == region_id
            ]
            active_nodes = [
                node for node in region_nodes if node.get("status") == NodeStatus.ACTIVE
            ]

            region_info = RegionInfo(
                id=region_id,
                name=region.get("name", region_id),
                priority=region.get("priority", 100),
                nodes=len(region_nodes),
                active_nodes=len(active_nodes),
                has_leader=(region_id == ha_status["leader_region"]),
            )

            region_list.append(region_info.dict())

        return {"success": True, "regions": region_list}

    @router.post("/regions")
    async def create_region(region: RegionConfig):
        """Create or update a region."""
        # Add or update region
        regions[region.id] = {
            "id": region.id,
            "name": region.name,
            "priority": region.priority,
        }

        # Save regions
        save_regions()

        # Add region added event
        add_event(
            EventType.REGION_ADDED,
            region_id=region.id,
            details={"name": region.name, "priority": region.priority},
        )

        return {"success": True, "message": f"Region {region.id} created successfully"}

    @router.delete("/regions/{region_id}")
    async def delete_region(region_id: str):
        """Delete a region."""
        if region_id not in regions:
            raise HTTPException(status_code=404, detail=f"Region {region_id} not found")

        # Don't allow deleting region that has nodes
        region_nodes = [node for node in known_nodes.values() if node.get("region") == region_id]
        if region_nodes:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete region {region_id} with {len(region_nodes)} nodes",
            )

        # Don't allow deleting the last region
        if len(regions) <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last region")

        # Don't allow deleting region that has the leader
        if region_id == ha_status["leader_region"]:
            raise HTTPException(status_code=400, detail="Cannot delete region that has the leader")

        # Delete region
        del regions[region_id]

        # Save regions
        save_regions()

        # Add region removed event
        add_event(EventType.REGION_REMOVED, region_id=region_id)

        return {"success": True, "message": f"Region {region_id} deleted successfully"}

    @router.get("/events")
    async def list_events(limit: int = 100, offset: int = 0, event_type: Optional[str] = None):
        """List high availability events."""
        # Filter events by type if specified
        filtered_events = events
        if event_type:
            filtered_events = [event for event in events if event.get("event_type") == event_type]

        # Sort by timestamp (newest first)
        sorted_events = sorted(filtered_events, key=lambda e: e.get("timestamp", 0), reverse=True)

        # Apply pagination
        paginated = sorted_events[offset : offset + limit]

        return {
            "success": True,
            "events": paginated,
            "total": len(filtered_events),
            "offset": offset,
            "limit": limit,
        }

    @router.post("/failover")
    async def request_failover(request: FailoverRequest):
        """Request a manual failover to a different node."""
        # Check if failover is enabled
        if not config["failover"]["enabled"]:
            return {"success": False, "error": "Failover is disabled"}

        # Perform failover
        success = await perform_failover(
            reason=request.reason,
            target_node_id=request.target_node_id,
            force=request.force,
        )

        if success:
            return {
                "success": True,
                "message": "Failover completed successfully",
                "new_leader_id": ha_status["leader_id"],
            }
        else:
            return {
                "success": False,
                "error": "Failover failed - no suitable leader found",
            }

    @router.post("/enable")
    async def enable_ha():
        """Enable high availability."""
        if config["enabled"]:
            return {"success": True, "message": "High availability is already enabled"}

        # Enable HA
        config["enabled"] = True

        # Update this node status
        this_node["status"] = NodeStatus.ACTIVE

        # Save config
        save_config()

        # Add event
        add_event(EventType.CONFIG_CHANGED, node_id=this_node["id"], details={"enabled": True})

        return {"success": True, "message": "High availability enabled successfully"}

    @router.post("/disable")
    async def disable_ha():
        """Disable high availability."""
        if not config["enabled"]:
            return {"success": True, "message": "High availability is already disabled"}

        # Disable HA
        config["enabled"] = False

        # Update this node status
        this_node["status"] = NodeStatus.STANDBY

        # Save config
        save_config()

        # Add event
        add_event(
            EventType.CONFIG_CHANGED,
            node_id=this_node["id"],
            details={"enabled": False},
        )

        return {"success": True, "message": "High availability disabled successfully"}

    @router.post("/maintenance")
    async def enter_maintenance():
        """Put this node into maintenance mode."""
        if this_node["status"] == NodeStatus.MAINTENANCE:
            return {"success": True, "message": "Node is already in maintenance mode"}

        # If this node is the leader, trigger failover
        if ha_status["leader_id"] == this_node["id"]:
            await perform_failover(reason="maintenance_mode", target_node_id = None)

        # Update status
        old_status = this_node["status"]
        this_node["status"] = NodeStatus.MAINTENANCE

        # Add event
        add_event(
            EventType.STATUS_CHANGED,
            node_id=this_node["id"],
            details={
                "old_status": old_status,
                "new_status": NodeStatus.MAINTENANCE,
                "reason": "manual_maintenance",
            },
        )

        # Save nodes
        save_nodes()

        return {
            "success": True,
            "message": "Node entered maintenance mode successfully",
        }

    @router.post("/activate")
    async def activate_node():
        """Activate this node for normal operation."""
        if this_node["status"] == NodeStatus.ACTIVE:
            return {"success": True, "message": "Node is already active"}

        # Update status
        old_status = this_node["status"]
        this_node["status"] = NodeStatus.ACTIVE

        # Add event
        add_event(
            EventType.STATUS_CHANGED,
            node_id=this_node["id"],
            details={
                "old_status": old_status,
                "new_status": NodeStatus.ACTIVE,
                "reason": "manual_activation",
            },
        )

        # Save nodes
        save_nodes()

        return {"success": True, "message": "Node activated successfully"}

    return router


# Start background tasks
def start_background_tasks(app):
    """Start background tasks for the high availability extension."""
    @app.on_event("startup")
    async def startup_event():
        # Initialize HTTP session
        initialize_http_session()

        # Set node status to active
        this_node["status"] = NodeStatus.ACTIVE
        save_nodes()

        # Add node joined event
        add_event(EventType.NODE_JOINED, node_id=this_node["id"], details={"startup": True})

        # Start main background task
        asyncio.create_task(ha_background_task())

    @app.on_event("shutdown")
    async def shutdown_event():
        # Update node status
        this_node["status"] = NodeStatus.STOPPING
        save_nodes()

        # Add node left event
        add_event(EventType.NODE_LEFT, node_id=this_node["id"], details={"shutdown": True})

        # Close HTTP session
        await close_http_session()

        # Save all data
        save_config()
        save_nodes()
        save_regions()
        save_events()


# Update storage backends status
def update_ha_storage_status(storage_backends_info: Dict[str, Any]) -> None:
    """Update the reference to storage backends status."""
    global storage_backends
    storage_backends = storage_backends_info


# Initialize
def initialize():
    """Initialize the high availability system."""
    initialize_config()
    initialize_nodes()
    initialize_regions()
    initialize_events()
    logger.info("High availability system initialized")


# Call initialization
initialize()

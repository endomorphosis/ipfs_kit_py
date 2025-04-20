"""
Data Replication and Consistency Module for MCP High Availability Architecture.

This module implements the data replication and consistency mechanisms
for the High Availability architecture as specified in the MCP roadmap Phase 3: Enterprise Features.

Features:
- Replication strategies (synchronous, asynchronous, quorum-based)
- Consistency models (strong, eventual, causal)
- Conflict detection and resolution
- Data versioning and vector clocks
- Optimized data synchronization
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)


class ConsistencyModel(str, Enum):
    """Consistency model for data replication."""

    STRONG = "strong"  # Synchronous replication with strong consistency
    EVENTUAL = "eventual"  # Asynchronous replication with eventual consistency
    CAUSAL = "causal"  # Causal consistency with vector clocks


class ReplicationStrategy(str, Enum):
    """Replication strategy."""

    SYNCHRONOUS = "synchronous"  # Wait for all replicas to acknowledge
    ASYNCHRONOUS = "asynchronous"  # Don't wait for acknowledgements
    QUORUM = "quorum"  # Wait for quorum of replicas to acknowledge


class ConflictResolutionStrategy(str, Enum):
    """Strategy for resolving conflicts."""

    LAST_WRITE_WINS = "last_write_wins"  # Use timestamp to determine winner
    VECTOR_CLOCK = "vector_clock"  # Use vector clocks to determine causality
    CUSTOM = "custom"  # Use custom conflict resolution function


class VectorClock(BaseModel):
    """Vector clock for tracking causality."""

    node_counters: Dict[str, int] = Field(default_factory=dict)
    last_updated: float = Field(default_factory=time.time)

    def increment(self, node_id: str) -> None:
        """
        Increment the counter for a node.

        Args:
            node_id: Node identifier
        """
        self.node_counters[node_id] = self.node_counters.get(node_id, 0) + 1
        self.last_updated = time.time()

    def merge(self, other: "VectorClock") -> None:
        """
        Merge with another vector clock.

        Args:
            other: Vector clock to merge with
        """
        for node_id, counter in other.node_counters.items():
            self.node_counters[node_id] = max(self.node_counters.get(node_id, 0), counter)
        self.last_updated = time.time()

    def compare(self, other: "VectorClock") -> int:
        """
        Compare with another vector clock.

        Returns:
            -1 if self < other (happened before)
            0 if self and other are concurrent
            1 if self > other (happened after)
        """
        less_than = False
        greater_than = False

        # Check all counters in both clocks
        all_nodes = set(self.node_counters.keys()) | set(other.node_counters.keys())

        for node_id in all_nodes:
            self_count = self.node_counters.get(node_id, 0)
            other_count = other.node_counters.get(node_id, 0)

            if self_count < other_count:
                less_than = True
            elif self_count > other_count:
                greater_than = True

            # If we have both, it's a conflict
            if less_than and greater_than:
                return 0  # Concurrent

        if less_than and not greater_than:
            return -1  # Happened before
        if greater_than and not less_than:
            return 1  # Happened after
        return 0  # Equal or concurrent


class DataVersion(BaseModel):
    """Version information for replicated data."""

    version_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    node_id: str
    vector_clock: VectorClock
    is_deleted: bool = False
    content_hash: Optional[str] = None


class ReplicatedData(BaseModel):
    """Data to be replicated across nodes."""

    key: str
    value: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: DataVersion
    content_type: str = "application/json"
    ttl: Optional[int] = None  # Time to live in seconds
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)


class SyncRecord(BaseModel):
    """Record of synchronization between nodes."""

    source_node: str
    target_node: str
    timestamp: float = Field(default_factory=time.time)
    keys_sent: List[str] = Field(default_factory=list)
    keys_received: List[str] = Field(default_factory=list)
    success: bool = True
    error_message: Optional[str] = None
    sync_duration: float = 0


class ConsistencyStatus(BaseModel):
    """Status of consistency across the cluster."""

    fully_consistent_keys: int = 0
    partially_consistent_keys: int = 0
    inconsistent_keys: int = 0
    key_status: Dict[str, str] = Field(default_factory=dict)
    last_check: float = Field(default_factory=time.time)
    node_health: Dict[str, bool] = Field(default_factory=dict)


class ReplicationConfig(BaseModel):
    """Configuration for replication."""

    consistency_model: ConsistencyModel = ConsistencyModel.EVENTUAL
    replication_strategy: ReplicationStrategy = ReplicationStrategy.ASYNCHRONOUS
    conflict_resolution: ConflictResolutionStrategy = ConflictResolutionStrategy.VECTOR_CLOCK
    sync_interval: int = 30  # Seconds between synchronization
    quorum_size: int = 2  # Number of replicas needed for quorum write
    read_repair: bool = True  # Fix inconsistencies on read
    gossip_enabled: bool = True  # Use gossip protocol for replication
    max_sync_batch: int = 1000  # Maximum batch size for sync
    priority_keys: List[str] = Field(default_factory=list)  # Keys to prioritize


class ConsistencyService:
    """
    Service for managing data replication and consistency in the MCP High Availability cluster.

    This service implements various consistency models and replication strategies to ensure
    data remains consistent across multiple nodes in the cluster, even in the presence of
    network partitions and node failures.
    """

    def __init__(
        self,
        node_id: str,
        config: Optional[ReplicationConfig] = None,
        http_session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Initialize consistency service.

        Args:
            node_id: Identifier of this node
            config: Replication configuration
            http_session: HTTP session for communication with other nodes
        """
        self.node_id = node_id
        self.config = config or ReplicationConfig()
        self.http_session = http_session
        self.data_store: Dict[str, ReplicatedData] = {}
        self.pending_updates: Dict[str, List[ReplicatedData]] = {}
        self.sync_history: List[SyncRecord] = []
        self.consistency_status = ConsistencyStatus()
        
        # Node information
        self.known_nodes: Dict[str, Dict[str, Any]] = {}
        
        # Locks for thread safety
        self.data_lock = asyncio.Lock()
        self.sync_lock = asyncio.Lock()
        
        # Tasks
        self.sync_task = None
        self.consistency_check_task = None
        
        # Initialization flag
        self.initialized = False

    async def start(self) -> None:
        """Start the consistency service."""
        if self.initialized:
            return

        logger.info(f"Starting consistency service on node {self.node_id}")
        
        # Create HTTP session if not provided
        if not self.http_session:
            self.http_session = aiohttp.ClientSession()
        
        # Start background tasks
        self.sync_task = asyncio.create_task(self._sync_loop())
        self.consistency_check_task = asyncio.create_task(self._consistency_check_loop())
        
        self.initialized = True
        logger.info(f"Consistency service started on node {self.node_id}")

    async def stop(self) -> None:
        """Stop the consistency service."""
        if not self.initialized:
            return

        logger.info(f"Stopping consistency service on node {self.node_id}")
        
        # Cancel tasks
        for task in [self.sync_task, self.consistency_check_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close HTTP session if we created it
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        
        self.initialized = False
        logger.info(f"Consistency service stopped on node {self.node_id}")

    async def set(
        self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Set a value with replication.

        Args:
            key: Key to store
            value: Value to store
            metadata: Additional metadata

        Returns:
            Result dictionary with operation status
        """
        if not self.initialized:
            return {"success": False, "error": "Service not initialized"}

        start_time = time.time()
        metadata = metadata or {}
        vector_clock = None
        
        # Generate content hash
        content_hash = self._calculate_hash(value)
        
        async with self.data_lock:
            # Check if we already have this key
            if key in self.data_store:
                # Update existing key
                existing_data = self.data_store[key]
                vector_clock = VectorClock(node_counters=dict(existing_data.version.vector_clock.node_counters))
                vector_clock.increment(self.node_id)
            else:
                # New key
                vector_clock = VectorClock(node_counters={self.node_id: 1})
            
            # Create version info
            version = DataVersion(
                node_id=self.node_id,
                vector_clock=vector_clock,
                content_hash=content_hash
            )
            
            # Create replicated data
            data = ReplicatedData(
                key=key,
                value=value,
                metadata=metadata,
                version=version,
                content_type="application/json" if isinstance(value, (dict, list)) else "text/plain"
            )
            
            # Store locally
            self.data_store[key] = data
            
            # Handle replication based on strategy
            success = True
            error = None
            
            if self.config.replication_strategy == ReplicationStrategy.SYNCHRONOUS:
                try:
                    # Replicate to all known nodes synchronously
                    replication_result = await self._replicate_to_nodes(key, data)
                    success = replication_result["success"]
                    if not success:
                        error = replication_result.get("error")
                except Exception as e:
                    success = False
                    error = str(e)
            
            elif self.config.replication_strategy == ReplicationStrategy.QUORUM:
                try:
                    # Replicate to enough nodes for quorum
                    replication_result = await self._replicate_to_quorum(key, data)
                    success = replication_result["success"]
                    if not success:
                        error = replication_result.get("error")
                except Exception as e:
                    success = False
                    error = str(e)
            
            elif self.config.replication_strategy == ReplicationStrategy.ASYNCHRONOUS:
                # Schedule asynchronous replication
                if key not in self.pending_updates:
                    self.pending_updates[key] = []
                self.pending_updates[key].append(data)
        
        return {
            "success": success,
            "key": key,
            "version_id": version.version_id,
            "timestamp": version.timestamp,
            "node_id": self.node_id,
            "duration": time.time() - start_time,
            "error": error
        }

    async def get(self, key: str) -> Dict[str, Any]:
        """
        Get a value with consistency guarantees.

        Args:
            key: Key to retrieve

        Returns:
            Result dictionary with value and metadata
        """
        if not self.initialized:
            return {"success": False, "error": "Service not initialized"}

        start_time = time.time()
        
        async with self.data_lock:
            # Check if we have the key locally
            if key not in self.data_store:
                # Key not found locally
                if self.config.consistency_model == ConsistencyModel.STRONG:
                    # For strong consistency, we need to check other nodes
                    try:
                        # Try to get from other nodes
                        remote_data = await self._get_from_nodes(key)
                        if remote_data:
                            # Store locally
                            self.data_store[key] = remote_data
                            
                            # Update access time
                            remote_data.last_accessed = time.time()
                            
                            return {
                                "success": True,
                                "key": key,
                                "value": remote_data.value,
                                "metadata": remote_data.metadata,
                                "version": remote_data.version.dict(),
                                "source": "remote",
                                "duration": time.time() - start_time
                            }
                    except Exception as e:
                        return {
                            "success": False,
                            "key": key,
                            "error": str(e),
                            "duration": time.time() - start_time
                        }
                
                # Key not found anywhere
                return {
                    "success": False,
                    "key": key,
                    "error": "Key not found",
                    "duration": time.time() - start_time
                }
            
            # Key found locally
            data = self.data_store[key]
            
            # Update access time
            data.last_accessed = time.time()
            
            # For strong consistency or read-repair, check for newer versions on other nodes
            if (
                self.config.consistency_model == ConsistencyModel.STRONG
                or self.config.read_repair
            ):
                asyncio.create_task(self._check_read_repair(key, data))
            
            return {
                "success": True,
                "key": key,
                "value": data.value,
                "metadata": data.metadata,
                "version": data.version.dict(),
                "source": "local",
                "duration": time.time() - start_time
            }

    async def delete(self, key: str) -> Dict[str, Any]:
        """
        Delete a value with replication.

        Args:
            key: Key to delete

        Returns:
            Result dictionary with operation status
        """
        if not self.initialized:
            return {"success": False, "error": "Service not initialized"}

        start_time = time.time()
        
        async with self.data_lock:
            # Check if we have the key
            if key not in self.data_store:
                return {
                    "success": False,
                    "key": key,
                    "error": "Key not found",
                    "duration": time.time() - start_time
                }
            
            # Get existing data
            existing_data = self.data_store[key]
            
            # Create new version with deletion flag
            vector_clock = VectorClock(node_counters=dict(existing_data.version.vector_clock.node_counters))
            vector_clock.increment(self.node_id)
            
            version = DataVersion(
                node_id=self.node_id,
                vector_clock=vector_clock,
                is_deleted=True
            )
            
            # Update data with deletion marker
            data = ReplicatedData(
                key=key,
                value=None,
                metadata=existing_data.metadata,
                version=version,
                content_type=existing_data.content_type
            )
            
            # Store deletion marker
            self.data_store[key] = data
            
            # Handle replication based on strategy
            success = True
            error = None
            
            if self.config.replication_strategy == ReplicationStrategy.SYNCHRONOUS:
                try:
                    # Replicate to all known nodes synchronously
                    replication_result = await self._replicate_to_nodes(key, data)
                    success = replication_result["success"]
                    if not success:
                        error = replication_result.get("error")
                except Exception as e:
                    success = False
                    error = str(e)
            
            elif self.config.replication_strategy == ReplicationStrategy.QUORUM:
                try:
                    # Replicate to enough nodes for quorum
                    replication_result = await self._replicate_to_quorum(key, data)
                    success = replication_result["success"]
                    if not success:
                        error = replication_result.get("error")
                except Exception as e:
                    success = False
                    error = str(e)
            
            elif self.config.replication_strategy == ReplicationStrategy.ASYNCHRONOUS:
                # Schedule asynchronous replication
                if key not in self.pending_updates:
                    self.pending_updates[key] = []
                self.pending_updates[key].append(data)
        
        return {
            "success": success,
            "key": key,
            "action": "delete",
            "version_id": version.version_id if success else None,
            "timestamp": version.timestamp if success else time.time(),
            "node_id": self.node_id,
            "duration": time.time() - start_time,
            "error": error
        }

    async def list_keys(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        List available keys.

        Args:
            prefix: Optional prefix to filter keys

        Returns:
            Dictionary with list of keys
        """
        if not self.initialized:
            return {"success": False, "error": "Service not initialized"}

        async with self.data_lock:
            # Get all non-deleted keys
            all_keys = [
                key
                for key, data in self.data_store.items()
                if not data.version.is_deleted and (prefix is None or key.startswith(prefix))
            ]
            
            return {
                "success": True,
                "keys": all_keys,
                "count": len(all_keys),
                "timestamp": time.time()
            }

    def update_nodes(self, nodes: Dict[str, Dict[str, Any]]) -> None:
        """
        Update known nodes information.

        Args:
            nodes: Dictionary of node information keyed by node ID
        """
        # Update known nodes
        self.known_nodes = nodes.copy()

    async def _sync_loop(self) -> None:
        """Periodically synchronize data with other nodes."""
        while True:
            try:
                if len(self.known_nodes) > 1:  # Only sync if there are other nodes
                    await self._synchronize_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
            
            # Sleep for sync interval
            interval = self.config.sync_interval
            await asyncio.sleep(interval)

    async def _consistency_check_loop(self) -> None:
        """Periodically check consistency status."""
        while True:
            try:
                if len(self.known_nodes) > 1:  # Only check if there are other nodes
                    await self._check_consistency()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in consistency check loop: {e}")
            
            # Sleep for a longer interval than sync
            interval = self.config.sync_interval * 3
            await asyncio.sleep(interval)

    async def _synchronize_data(self) -> None:
        """Synchronize data with other nodes."""
        # Skip if synchronization is already in progress
        if self.sync_lock.locked():
            return
        
        async with self.sync_lock:
            # Get active nodes
            active_nodes = {
                node_id: info
                for node_id, info in self.known_nodes.items()
                if info.get("status") == "active" and node_id != self.node_id
            }
            
            if not active_nodes:
                return
            
            # Process pending updates first if any
            if self.pending_updates:
                await self._process_pending_updates()
            
            # Use different synchronization approaches based on node count
            if len(active_nodes) <= 3:
                # Direct sync with all nodes
                for node_id, node_info in active_nodes.items():
                    await self._sync_with_node(node_id, node_info)
            else:
                # Gossip protocol: sync with a subset of nodes
                await self._gossip_sync(active_nodes)

    async def _process_pending_updates(self) -> None:
        """Process pending asynchronous updates."""
        if not self.pending_updates:
            return
        
        async with self.data_lock:
            # Get a copy of pending updates
            updates = self.pending_updates.copy()
            self.pending_updates = {}
        
        # Replicate each pending update
        for key, data_list in updates.items():
            for data in data_list:
                try:
                    # Use the most recent update
                    if self.config.replication_strategy == ReplicationStrategy.QUORUM:
                        await self._replicate_to_quorum(key, data)
                    else:
                        await self._replicate_to_nodes(key, data)
                except Exception as e:
                    logger.error(f"Error replicating pending update for key {key}: {e}")
                    # Put back in pending updates
                    async with self.data_lock:
                        if key not in self.pending_updates:
                            self.pending_updates[key] = []
                        self.pending_updates[key].append(data)

    async def _sync_with_node(self, node_id: str, node_info: Dict[str, Any]) -> None:
        """
        Synchronize data with a specific node.

        Args:
            node_id: Node identifier
            node_info: Node information
        """
        if not self.http_session:
            return
        
        # Skip inactive nodes
        if node_info.get("status") != "active":
            return
        
        start_time = time.time()
        sync_record = SyncRecord(
            source_node=self.node_id,
            target_node=node_id,
            timestamp=start_time
        )
        
        try:
            # Get node address
            node_address = f"{node_info['ip_address']}:{node_info['port']}"
            
            # First, get keys from remote node
            async with self.http_session.get(
                f"http://{node_address}/api/v0/ha/replication/keys"
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get keys from node {node_id}: {response.status}")
                
                remote_keys_data = await response.json()
                remote_keys = remote_keys_data.get("keys", [])
            
            # Get our keys
            async with self.data_lock:
                local_keys = [
                    key for key, data in self.data_store.items()
                ]
            
            # Determine keys to sync in both directions
            keys_to_pull = [key for key in remote_keys if key not in local_keys]
            keys_to_check = [key for key in remote_keys if key in local_keys]
            keys_to_push = [key for key in local_keys if key not in remote_keys]
            
            # Pull missing keys
            if keys_to_pull:
                await self._pull_keys_from_node(node_id, node_address, keys_to_pull, sync_record)
            
            # Check potentially conflicting keys
            if keys_to_check:
                await self._check_conflicting_keys(node_id, node_address, keys_to_check, sync_record)
            
            # Push missing keys
            if keys_to_push:
                await self._push_keys_to_node(node_id, node_address, keys_to_push, sync_record)
            
            # Update sync record
            sync_record.success = True
            sync_record.sync_duration = time.time() - start_time
            
        except Exception as e:
            logger.error(f"Error syncing with node {node_id}: {e}")
            sync_record.success = False
            sync_record.error_message = str(e)
            sync_record.sync_duration = time.time() - start_time
        
        # Add sync record to history
        self.sync_history.append(sync_record)
        if len(self.sync_history) > 100:
            self.sync_history = self.sync_history[-100:]

    async def _pull_keys_from_node(
        self, node_id: str, node_address: str, keys: List[str], sync_record: SyncRecord
    ) -> None:
        """
        Pull keys from another node.

        Args:
            node_id: Node identifier
            node_address: Node address (ip:port)
            keys: Keys to pull
            sync_record: Sync record to update
        """
        if not keys:
            return
        
        # Split into batches to avoid too large requests
        batch_size = min(self.config.max_sync_batch, 100)
        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]
            
            try:
                # Get data for keys
                async with self.http_session.post(
                    f"http://{node_address}/api/v0/ha/replication/get_batch",
                    json={"keys": batch_keys}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to pull keys from node {node_id}: {response.status}")
                        continue
                    
                    batch_data = await response.json()
                    items = batch_data.get("items", [])
                    
                    # Process received items
                    for item in items:
                        if item.get("success"):
                            key = item.get("key")
                            value = item.get("value")
                            metadata = item.get("metadata", {})
                            version_data = item.get("version", {})
                            
                            # Create version
                            vector_clock_data = version_data.get("vector_clock", {})
                            vector_clock = VectorClock(
                                node_counters=vector_clock_data.get("node_counters", {}),
                                last_updated=vector_clock_data.get("last_updated", time.time())
                            )
                            
                            version = DataVersion(
                                version_id=version_data.get("version_id", str(uuid.uuid4())),
                                timestamp=version_data.get("timestamp", time.time()),
                                node_id=version_data.get("node_id", node_id),
                                vector_clock=vector_clock,
                                is_deleted=version_data.get("is_deleted", False),
                                content_hash=version_data.get("content_hash")
                            )
                            
                            # Create replicated data
                            data = ReplicatedData(
                                key=key,
                                value=value,
                                metadata=metadata,
                                version=version,
                                content_type=item.get("content_type", "application/json"),
                                created_at=item.get("created_at", time.time()),
                                last_accessed=time.time()
                            )
                            
                            # Store or update
                            async with self.data_lock:
                                # Check if we already have this key
                                if key in self.data_store:
                                    # Compare versions
                                    existing_data = self.data_store[key]
                                    comparison = existing_data.version.vector_clock.compare(vector_clock)
                                    
                                    if comparison < 0:
                                        # Remote version is newer
                                        self.data_store[key] = data
                                        sync_record.keys_received.append(key)
                                    elif comparison == 0:
                                        # Potential conflict, resolve
                                        resolved_data = await self._resolve_conflict(existing_data, data)
                                        self.data_store[key] = resolved_data
                                        sync_record.keys_received.append(key)
                                else:
                                    # New key
                                    self.data_store[key] = data
                                    sync_record.keys_received.append(key)
            
            except Exception as e:
                logger.error(f"Error pulling batch of keys from node {node_id}: {e}")

    async def _check_conflicting_keys(
        self, node_id: str, node_address: str, keys: List[str], sync_record: SyncRecord
    ) -> None:
        """
        Check for conflicts on keys that exist on both nodes.

        Args:
            node_id: Node identifier
            node_address: Node address (ip:port)
            keys: Keys to check
            sync_record: Sync record to update
        """
        if not keys:
            return
        
        # Get our versions
        local_versions = {}
        async with self.data_lock:
            for key in keys:
                if key in self.data_store:
                    data = self.data_store[key]
                    local_versions[key] = {
                        "version_id": data.version.version_id,
                        "timestamp": data.version.timestamp,
                        "node_id": data.version.node_id,
                        "vector_clock": data.version.vector_clock.dict(),
                        "is_deleted": data.version.is_deleted,
                        "content_hash": data.version.content_hash
                    }
        
        # Split into batches
        batch_size = min(self.config.max_sync_batch, 100)
        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]
            batch_versions = {k: local_versions[k] for k in batch_keys if k in local_versions}
            
            try:
                # Compare versions
                async with self.http_session.post(
                    f"http://{node_address}/api/v0/ha/replication/compare_versions",
                    json={"versions": batch_versions}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to compare versions with node {node_id}: {response.status}")
                        continue
                    
                    comparison_result = await response.json()
                    
                    # Process keys where remote version is different
                    remote_newer = comparison_result.get("remote_newer", [])
                    conflict_keys = comparison_result.get("conflicts", [])
                    local_newer = comparison_result.get("local_newer", [])
                    
                    # Pull remote newer versions
                    if remote_newer:
                        await self._pull_keys_from_node(node_id, node_address, remote_newer, sync_record)
                    
                    # Resolve conflicts
                    if conflict_keys:
                        await self._resolve_conflicting_keys(node_id, node_address, conflict_keys, sync_record)
                    
                    # Push local newer versions
                    if local_newer:
                        await self._push_keys_to_node(node_id, node_address, local_newer, sync_record)
            
            except Exception as e:
                logger.error(f"Error checking conflicting keys with node {node_id}: {e}")

    async def _push_keys_to_node(
        self, node_id: str, node_address: str, keys: List[str], sync_record: SyncRecord
    ) -> None:
        """
        Push keys to another node.

        Args:
            node_id: Node identifier
            node_address: Node address (ip:port)
            keys: Keys to push
            sync_record: Sync record to update
        """
        if not keys:
            return
        
        # Get our data
        data_to_push = []
        async with self.data_lock:
            for key in keys:
                if key in self.data_store:
                    data = self.data_store[key]
                    data_to_push.append({
                        "key": key,
                        "value": data.value,
                        "metadata": data.metadata,
                        "version": data.version.dict(),
                        "content_type": data.content_type,
                        "created_at": data.created_at
                    })
        
        # Split into batches
        batch_size = min(self.config.max_sync_batch, 50)
        for i in range(0, len(data_to_push), batch_size):
            batch_data = data_to_push[i:i + batch_size]
            
            try:
                # Push data
                async with self.http_session.post(
                    f"http://{node_address}/api/v0/ha/replication/set_batch",
                    json={"items": batch_data}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to push keys to node {node_id}: {response.status}")
                        continue
                    
                    result = await response.json()
                    
                    # Update sync record
                    accepted_keys = result.get("accepted_keys", [])
                    for key in accepted_keys:
                        if key not in sync_record.keys_sent:
                            sync_record.keys_sent.append(key)
            
            except Exception as e:
                logger.error(f"Error pushing batch of keys to node {node_id}: {e}")

    async def _resolve_conflicting_keys(
        self, node_id: str, node_address: str, keys: List[str], sync_record: SyncRecord
    ) -> None:
        """
        Resolve conflicts on specific keys.

        Args:
            node_id: Node identifier
            node_address: Node address (ip:port)
            keys: Keys with conflicts
            sync_record: Sync record to update
        """
        if not keys:
            return
        
        # Pull conflicting keys to get remote version
        await self._pull_keys_from_node(node_id, node_address, keys, sync_record)

    async def _resolve_conflict(
        self, local_data: ReplicatedData, remote_data: ReplicatedData
    ) -> ReplicatedData:
        """
        Resolve a conflict between two versions of the same key.

        Args:
            local_data: Local version
            remote_data: Remote version

        Returns:
            Resolved data
        """
        # Use configured conflict resolution strategy
        strategy = self.config.conflict_resolution
        
        if strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            # Compare timestamps
            if remote_data.version.timestamp > local_data.version.timestamp:
                return remote_data
            else:
                return local_data
        
        elif strategy == ConflictResolutionStrategy.VECTOR_CLOCK:
            # Vector clocks should be concurrent if we got here
            # In case of ties, we choose based on additional rules:
            
            # 1. If one is deleted and the other is not, prefer the non-deleted one
            if local_data.version.is_deleted and not remote_data.version.is_deleted:
                return remote_data
            elif not local_data.version.is_deleted and remote_data.version.is_deleted:
                return local_data
            
            # 2. If both are deleted or both are not deleted, use timestamp
            if remote_data.version.timestamp > local_data.version.timestamp:
                return remote_data
            else:
                return local_data
        
        # Add more sophisticated conflict resolution strategies as needed
        
        # Default: keep the remote version
        return remote_data

    async def _gossip_sync(self, active_nodes: Dict[str, Dict[str, Any]]) -> None:
        """
        Perform gossip-based synchronization with a subset of nodes.

        Args:
            active_nodes: Dictionary of active nodes keyed by node ID
        """
        if not active_nodes:
            return
        
        # Select a subset of nodes for this round
        import random
        node_ids = list(active_nodes.keys())
        
        # The number of nodes to gossip with is logarithmic in network size
        gossip_count = min(3, max(1, int(1 + math.log2(len(node_ids)))))
        selected_nodes = random.sample(node_ids, min(gossip_count, len(node_ids)))
        
        # Sync with selected nodes
        for node_id in selected_nodes:
            node_info = active_nodes[node_id]
            await self._sync_with_node(node_id, node_info)

    async def _check_read_repair(self, key: str, local_data: ReplicatedData) -> None:
        """
        Check if a read value needs repair from other nodes.

        Args:
            key: Key to check
            local_data: Local data
        """
        if not self.http_session or not self.known_nodes:
            return
        
        # Get active nodes
        active_nodes = {
            node_id: info
            for node_id, info in self.known_nodes.items()
            if info.get("status") == "active" and node_id != self.node_id
        }
        
        if not active_nodes:
            return
        
        # Select a random node to check
        import random
        node_id = random.choice(list(active_nodes.keys()))
        node_info = active_nodes[node_id]
        node_address = f"{node_info['ip_address']}:{node_info['port']}"
        
        try:
            # Get version info for this key
            async with self.http_session.get(
                f"http://{node_address}/api/v0/ha/replication/version",
                params={"key": key}
            ) as response:
                if response.status != 200:
                    return
                
                version_info = await response.json()
                
                if not version_info.get("success"):
                    return
                
                # Extract vector clock
                remote_version = version_info.get("version", {})
                vector_clock_data = remote_version.get("vector_clock", {})
                vector_clock = VectorClock(
                    node_counters=vector_clock_data.get("node_counters", {}),
                    last_updated=vector_clock_data.get("last_updated", time.time())
                )
                
                # Compare with local version
                comparison = local_data.version.vector_clock.compare(vector_clock)
                
                if comparison < 0:
                    # Remote version is newer, get it
                    logger.debug(f"Read repair: Getting newer version of key {key} from node {node_id}")
                    
                    # Pull this key
                    sync_record = SyncRecord(
                        source_node=self.node_id,
                        target_node=node_id,
                        timestamp=time.time()
                    )
                    await self._pull_keys_from_node(node_id, node_address, [key], sync_record)
        
        except Exception as e:
            logger.debug(f"Error in read repair for key {key}: {e}")

    async def _get_from_nodes(self, key: str) -> Optional[ReplicatedData]:
        """
        Try to get a key from other nodes.

        Args:
            key: Key to get

        Returns:
            ReplicatedData object or None if not found
        """
        if not self.http_session or not self.known_nodes:
            return None
        
        # Get active nodes
        active_nodes = {
            node_id: info
            for node_id, info in self.known_nodes.items()
            if info.get("status") == "active" and node_id != self.node_id
        }
        
        if not active_nodes:
            return None
        
        # Try each node
        for node_id, node_info in active_nodes.items():
            node_address = f"{node_info['ip_address']}:{node_info['port']}"
            
            try:
                # Get key from node
                async with self.http_session.get(
                    f"http://{node_address}/api/v0/ha/replication/get",
                    params={"key": key}
                ) as response:
                    if response.status != 200:
                        continue
                    
                    data = await response.json()
                    
                    if not data.get("success"):
                        continue
                    
                    # Extract data
                    value = data.get("value")
                    metadata = data.get("metadata", {})
                    version_data = data.get("version", {})
                    
                    # Create version
                    vector_clock_data = version_data.get("vector_clock", {})
                    vector_clock = VectorClock(
                        node_counters=vector_clock_data.get("node_counters", {}),
                        last_updated=vector_clock_data.get("last_updated", time.time())
                    )
                    
                    version = DataVersion(
                        version_id=version_data.get("version_id", str(uuid.uuid4())),
                        timestamp=version_data.get("timestamp", time.time()),
                        node_id=version_data.get("node_id", node_id),
                        vector_clock=vector_clock,
                        is_deleted=version_data.get("is_deleted", False),
                        content_hash=version_data.get("content_hash")
                    )
                    
                    # Create replicated data
                    return ReplicatedData(
                        key=key,
                        value=value,
                        metadata=metadata,
                        version=version,
                        content_type=data.get("content_type", "application/json"),
                        created_at=data.get("created_at", time.time()),
                        last_accessed=time.time()
                    )
            
            except Exception as e:
                logger.debug(f"Error getting key {key} from node {node_id}: {e}")
        
        return None

    async def _replicate_to_nodes(self, key: str, data: ReplicatedData) -> Dict[str, Any]:
        """
        Replicate a key to all nodes synchronously.

        Args:
            key: Key to replicate
            data: Data to replicate

        Returns:
            Result dictionary
        """
        if not self.http_session or not self.known_nodes:
            return {"success": False, "error": "No HTTP session or known nodes"}
        
        # Get active nodes
        active_nodes = {
            node_id: info
            for node_id, info in self.known_nodes.items()
            if info.get("status") == "active" and node_id != self.node_id
        }
        
        if not active_nodes:
            return {"success": True, "message": "No active nodes to replicate to"}
        
        # Track results
        success_count = 0
        error_messages = []
        
        # Send to each node
        for node_id, node_info in active_nodes.items():
            node_address = f"{node_info['ip_address']}:{node_info['port']}"
            
            try:
                # Send data
                async with self.http_session.post(
                    f"http://{node_address}/api/v0/ha/replication/set",
                    json={
                        "key": key,
                        "value": data.value,
                        "metadata": data.metadata,
                        "version": data.version.dict(),
                        "content_type": data.content_type,
                        "created_at": data.created_at
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success"):
                            success_count += 1
                        else:
                            error_messages.append(f"Node {node_id}: {result.get('error', 'Unknown error')}")
                    else:
                        error_messages.append(f"Node {node_id}: HTTP {response.status}")
            
            except Exception as e:
                error_messages.append(f"Node {node_id}: {str(e)}")
        
        # Success if at least one node succeeded
        if success_count > 0:
            return {
                "success": True,
                "key": key,
                "replicated_count": success_count,
                "total_nodes": len(active_nodes),
                "errors": error_messages if error_messages else None
            }
        else:
            return {
                "success": False,
                "key": key,
                "error": "Failed to replicate to any node",
                "error_details": error_messages
            }

    async def _replicate_to_quorum(self, key: str, data: ReplicatedData) -> Dict[str, Any]:
        """
        Replicate a key to a quorum of nodes.

        Args:
            key: Key to replicate
            data: Data to replicate

        Returns:
            Result dictionary
        """
        if not self.http_session or not self.known_nodes:
            return {"success": False, "error": "No HTTP session or known nodes"}
        
        # Get active nodes
        active_nodes = {
            node_id: info
            for node_id, info in self.known_nodes.items()
            if info.get("status") == "active" and node_id != self.node_id
        }
        
        if not active_nodes:
            return {"success": True, "message": "No active nodes to replicate to"}
        
        # Calculate quorum size (including this node)
        total_nodes = len(active_nodes) + 1
        quorum_size = min(self.config.quorum_size, total_nodes)
        
        # If we're the only node, we already have quorum
        if quorum_size <= 1:
            return {"success": True, "key": key, "replicated_count": 1, "total_nodes": 1}
        
        # We need quorum_size - 1 more nodes to acknowledge
        min_acks = quorum_size - 1
        
        # Track results
        success_count = 0
        error_messages = []
        
        # Send to each node
        for node_id, node_info in active_nodes.items():
            # If we already have enough acks, we can stop
            if success_count >= min_acks:
                break
            
            node_address = f"{node_info['ip_address']}:{node_info['port']}"
            
            try:
                # Send data
                async with self.http_session.post(
                    f"http://{node_address}/api/v0/ha/replication/set",
                    json={
                        "key": key,
                        "value": data.value,
                        "metadata": data.metadata,
                        "version": data.version.dict(),
                        "content_type": data.content_type,
                        "created_at": data.created_at
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success"):
                            success_count += 1
                        else:
                            error_messages.append(f"Node {node_id}: {result.get('error', 'Unknown error')}")
                    else:
                        error_messages.append(f"Node {node_id}: HTTP {response.status}")
            
            except Exception as e:
                error_messages.append(f"Node {node_id}: {str(e)}")
        
        # Success if we reached quorum
        if success_count >= min_acks:
            return {
                "success": True,
                "key": key,
                "replicated_count": success_count + 1,  # +1 for this node
                "quorum_size": quorum_size,
                "total_nodes": total_nodes,
                "errors": error_messages if error_messages else None
            }
        else:
            return {
                "success": False,
                "key": key,
                "error": f"Failed to reach quorum ({success_count + 1}/{quorum_size})",
                "error_details": error_messages
            }

    async def _check_consistency(self) -> None:
        """Check consistency of data across nodes."""
        if not self.http_session or not self.known_nodes:
            return
        
        # Get active nodes
        active_nodes = {
            node_id: info
            for node_id, info in self.known_nodes.items()
            if info.get("status") == "active" and node_id != self.node_id
        }
        
        if not active_nodes:
            return
        
        # Initialize status
        status = ConsistencyStatus(
            node_health={node_id: True for node_id in active_nodes}
        )
        
        # Get our keys
        async with self.data_lock:
            local_keys = set(self.data_store.keys())
        
        # Check each node
        for node_id, node_info in active_nodes.items():
            node_address = f"{node_info['ip_address']}:{node_info['port']}"
            
            try:
                # Get keys from this node
                async with self.http_session.get(
                    f"http://{node_address}/api/v0/ha/replication/keys"
                ) as response:
                    if response.status != 200:
                        status.node_health[node_id] = False
                        continue
                    
                    keys_data = await response.json()
                    remote_keys = set(keys_data.get("keys", []))
                    
                    # Compare key sets
                    common_keys = local_keys.intersection(remote_keys)
                    only_local = local_keys - remote_keys
                    only_remote = remote_keys - local_keys
                    
                    # Check versions of common keys
                    consistent_keys = 0
                    inconsistent_keys = 0
                    
                    if common_keys:
                        # Get local versions of common keys
                        local_versions = {}
                        async with self.data_lock:
                            for key in common_keys:
                                if key in self.data_store:
                                    data = self.data_store[key]
                                    local_versions[key] = {
                                        "version_id": data.version.version_id,
                                        "timestamp": data.version.timestamp,
                                        "node_id": data.version.node_id,
                                        "vector_clock": data.version.vector_clock.dict(),
                                        "is_deleted": data.version.is_deleted,
                                        "content_hash": data.version.content_hash
                                    }
                        
                        # Compare versions
                        async with self.http_session.post(
                            f"http://{node_address}/api/v0/ha/replication/compare_versions",
                            json={"versions": local_versions}
                        ) as compare_response:
                            if compare_response.status == 200:
                                comparison = await compare_response.json()
                                
                                # Check results
                                remote_newer = set(comparison.get("remote_newer", []))
                                local_newer = set(comparison.get("local_newer", []))
                                conflict_keys = set(comparison.get("conflicts", []))
                                consistent = common_keys - remote_newer - local_newer - conflict_keys
                                
                                # Update counts
                                consistent_keys = len(consistent)
                                inconsistent_keys = len(common_keys) - consistent_keys
                                
                                # Update key status
                                for key in consistent:
                                    status.key_status[key] = "consistent"
                                
                                for key in remote_newer:
                                    status.key_status[key] = "remote_newer"
                                
                                for key in local_newer:
                                    status.key_status[key] = "local_newer"
                                
                                for key in conflict_keys:
                                    status.key_status[key] = "conflict"
                    
                    # Update counts
                    status.fully_consistent_keys += consistent_keys
                    status.inconsistent_keys += inconsistent_keys
                    status.partially_consistent_keys += len(only_local) + len(only_remote)
                    
                    # Update key status for keys only on one side
                    for key in only_local:
                        status.key_status[key] = "only_local"
                    
                    for key in only_remote:
                        status.key_status[key] = "only_remote"
            
            except Exception as e:
                logger.error(f"Error checking consistency with node {node_id}: {e}")
                status.node_health[node_id] = False
        
        # Update consistency status
        status.last_check = time.time()
        self.consistency_status = status

    def _calculate_hash(self, value: Any) -> str:
        """
        Calculate hash for a value.

        Args:
            value: Value to hash

        Returns:
            Hash string
        """
        try:
            if isinstance(value, (dict, list)):
                # Convert to sorted JSON string
                json_str = json.dumps(value, sort_keys=True)
                return hashlib.sha256(json_str.encode()).hexdigest()
            elif isinstance(value, str):
                return hashlib.sha256(value.encode()).hexdigest()
            elif isinstance(value, bytes):
                return hashlib.sha256(value).hexdigest()
            else:
                # Convert to string
                return hashlib.sha256(str(value).encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash: {e}")
            return ""

    def get_consistency_status(self) -> Dict[str, Any]:
        """
        Get current consistency status.

        Returns:
            Dictionary with consistency information
        """
        status = self.consistency_status
        
        return {
            "node_id": self.node_id,
            "fully_consistent_keys": status.fully_consistent_keys,
            "partially_consistent_keys": status.partially_consistent_keys,
            "inconsistent_keys": status.inconsistent_keys,
            "key_count": len(self.data_store),
            "last_check": status.last_check,
            "healthy_nodes": sum(1 for healthy in status.node_health.values() if healthy),
            "total_nodes": len(status.node_health),
            "consistency_model": self.config.consistency_model,
            "replication_strategy": self.config.replication_strategy
        }
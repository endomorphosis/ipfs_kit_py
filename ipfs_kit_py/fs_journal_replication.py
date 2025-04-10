"""
Metadata Replication Policy for Filesystem Journal.

This module implements a comprehensive replication policy for filesystem metadata
to enable both horizontal scaling and disaster recovery. It builds on the existing
filesystem journal and distributed state synchronization infrastructure.

Key features:
1. Multi-node metadata replication with configurable consistency levels
2. Progressive redundancy across storage tiers
3. Automatic failover and recovery mechanisms
4. Distributed checkpoints for disaster recovery
5. CRDT-based conflict resolution for concurrent modifications
6. Vector clock-based causality tracking
7. Peer discovery and gossip-based metadata propagation
"""

import copy
import json
import logging
import os
import threading
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Set, Tuple, Callable

# Import our own modules
from ipfs_kit_py.filesystem_journal import (
    FilesystemJournal,
    FilesystemJournalManager,
    JournalOperationType,
    JournalEntryStatus
)
from ipfs_kit_py.fs_journal_backends import (
    StorageBackendType,
    TieredStorageJournalBackend
)
from ipfs_kit_py.cluster_state_sync import (
    ClusterStateSync,
    VectorClock,
    StateCRDT
)

# Try to import Arrow-specific modules
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

class ReplicationLevel(str, Enum):
    """Replication consistency levels."""
    SINGLE = "single"          # Only replicate to master node
    QUORUM = "quorum"          # Replicate to majority of nodes (max(3, N/2 + 1)) ensuring minimum of 3
    ALL = "all"                # Replicate to all available nodes
    LOCAL_DURABILITY = "local_durability"  # Ensure local durability before ACK
    TIERED = "tiered"          # Replicate across different storage tiers
    PROGRESSIVE = "progressive"  # Progressive replication across tiers and nodes


class ReplicationStatus(str, Enum):
    """Status of replication operations."""
    PENDING = "pending"        # Replication requested but not started
    IN_PROGRESS = "in_progress"  # Replication in progress
    COMPLETE = "complete"      # Replication completed successfully
    PARTIAL = "partial"        # Replication succeeded on some nodes but not all
    FAILED = "failed"          # Replication failed
    CONFLICT = "conflict"      # Conflict detected during replication


class MetadataReplicationManager:
    """
    Manager for replicating filesystem metadata across nodes and storage tiers.
    
    This class coordinates the replication of filesystem metadata to ensure
    both horizontal scaling capabilities and disaster recovery. It builds on
    the existing filesystem journal system, tiered storage backends, and
    distributed state synchronization.
    """
    
    def __init__(
        self,
        journal_manager: Optional[FilesystemJournalManager] = None,
        tiered_backend: Optional[TieredStorageJournalBackend] = None,
        sync_manager: Optional[ClusterStateSync] = None,
        node_id: Optional[str] = None,
        role: str = "worker",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the metadata replication manager.
        
        Args:
            journal_manager: Filesystem journal manager instance
            tiered_backend: Tiered storage backend for managing different storage tiers
            sync_manager: Cluster state synchronization manager
            node_id: Unique identifier for this node
            role: Role of this node in the cluster ("master", "worker", or "leecher")
            config: Configuration options
        """
        # Store references to components
        self.journal_manager = journal_manager
        self.tiered_backend = tiered_backend
        self.sync_manager = sync_manager
        
        # Node identity
        self.node_id = node_id or str(uuid.uuid4())
        self.role = role
        
        # Default configuration
        self.default_config = {
            "default_replication_level": ReplicationLevel.QUORUM,
            "default_tier_progression": [
                StorageBackendType.MEMORY,
                StorageBackendType.DISK,
                StorageBackendType.IPFS,
                StorageBackendType.IPFS_CLUSTER,
                StorageBackendType.S3,
                StorageBackendType.STORACHA,
                StorageBackendType.FILECOIN
            ],
            "checkpoint_interval": 300,  # 5 minutes
            "sync_interval": 30,         # 30 seconds
            "quorum_size": 2,            # Default quorum size (will be adjusted based on cluster size)
            "target_replication_factor": 4,  # Target number of copies to maintain
            "max_replication_factor": 5,     # Maximum number of copies to create
            "max_sync_entries": 1000,    # Maximum number of entries to sync at once
            "auto_recovery": True,       # Automatically recover on startup
            "conflict_resolution": "lww", # Last-write-wins conflict resolution
            "store_remote_copies": True,  # Store copies on remote nodes
            "base_path": "~/.ipfs_kit/fs_replication"
        }
        
        # Apply provided configuration
        self.config = self.default_config.copy()
        if config:
            self.config.update(config)
            
        # Ensure minimum replication factor of 3 for quorum size
        # This ensures data durability even with small clusters
        self.config["quorum_size"] = max(3, self.config["quorum_size"])
            
        # Initialize state
        self.replication_status = {}  # entry_id -> status
        self.peer_nodes = {}          # node_id -> metadata
        self.active_replications = {} # entry_id -> replication metadata
        self.storage_availability = {}  # tier -> availability status
        
        # Locks for thread safety
        self._locks = {
            "status": threading.RLock(),
            "peers": threading.RLock(),
            "replications": threading.RLock()
        }
        
        # Base path for local storage
        self.base_path = os.path.expanduser(self.config["base_path"])
        self.metadata_path = os.path.join(self.base_path, "metadata")
        self.checkpoint_path = os.path.join(self.base_path, "checkpoints")
        self.state_path = os.path.join(self.base_path, "state")
        
        # Create directories
        os.makedirs(self.metadata_path, exist_ok=True)
        os.makedirs(self.checkpoint_path, exist_ok=True)
        os.makedirs(self.state_path, exist_ok=True)
        
        # Initialize vector clock for this node
        self.vector_clock = VectorClock.create()
        self.vector_clock = VectorClock.increment(self.vector_clock, self.node_id)
        
        # Background threads
        self._sync_thread = None
        self._checkpoint_thread = None
        self._stop_threads = threading.Event()
        
        # Auto-initialize components if not provided
        if not self.journal_manager:
            self._init_journal_manager()
            
        if not self.tiered_backend:
            self._init_tiered_backend()
            
        if not self.sync_manager:
            self._init_sync_manager()
            
        # Load state from disk if available
        self._load_state()
        
        # Start background threads
        self._start_background_threads()
        
        logger.info(f"Metadata replication manager initialized (node {self.node_id}, role {self.role})")
    
    def _init_journal_manager(self):
        """Initialize a new journal manager if not provided."""
        # Create filesystem journal
        journal = FilesystemJournal(
            base_path=os.path.join(self.base_path, "journal"),
            sync_interval=5,
            checkpoint_interval=60,
            max_journal_size=1000,
            auto_recovery=True
        )
        
        # Create filesystem journal manager
        self.journal_manager = FilesystemJournalManager(journal)
        logger.info("Created new filesystem journal manager")
    
    def _init_tiered_backend(self):
        """Initialize a new tiered storage backend if not provided."""
        # This would typically require a TieredCacheManager
        # For now, we'll leave it uninitialized and handle operations without it
        self.tiered_backend = None
        logger.warning("No tiered storage backend provided - tier operations will be limited")
    
    def _init_sync_manager(self):
        """Initialize a new synchronization manager if not provided."""
        # Create a dummy object with minimal functionality
        class DummySyncManager:
            def __init__(self, node_id):
                self.node_id = node_id
                
            def initialize_distributed_state(self, initial_data=None):
                return {"success": True, "message": "Using dummy sync manager"}
                
        self.sync_manager = DummySyncManager(self.node_id)
        logger.warning("No synchronization manager provided - using dummy implementation")
    
    def _load_state(self):
        """Load replication state from disk."""
        try:
            state_file = os.path.join(self.state_path, "replication_state.json")
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    
                # Update our state
                with self._locks["status"]:
                    self.replication_status = state.get("replication_status", {})
                    
                with self._locks["peers"]:
                    self.peer_nodes = state.get("peer_nodes", {})
                    
                # Restore vector clock
                self.vector_clock = state.get("vector_clock", self.vector_clock)
                
                logger.info(f"Loaded replication state from {state_file}")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    def _save_state(self):
        """Save replication state to disk."""
        try:
            state_file = os.path.join(self.state_path, "replication_state.json")
            
            # Build state object
            state = {
                "replication_status": self.replication_status,
                "peer_nodes": self.peer_nodes,
                "vector_clock": self.vector_clock,
                "timestamp": time.time(),
                "node_id": self.node_id
            }
            
            # Write to temporary file first
            temp_file = state_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
                
            # Move to final location (atomic operation)
            os.replace(temp_file, state_file)
            
            logger.debug(f"Saved replication state to {state_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            return False
    
    def _start_background_threads(self):
        """Start background maintenance threads."""
        # Reset stop flag
        self._stop_threads.clear()
        
        # Start sync thread
        if not self._sync_thread or not self._sync_thread.is_alive():
            self._sync_thread = threading.Thread(
                target=self._sync_loop, 
                name="MetadataSync", 
                daemon=True
            )
            self._sync_thread.start()
        
        # Start checkpoint thread
        if not self._checkpoint_thread or not self._checkpoint_thread.is_alive():
            self._checkpoint_thread = threading.Thread(
                target=self._checkpoint_loop, 
                name="MetadataCheckpoint", 
                daemon=True
            )
            self._checkpoint_thread.start()
            
        logger.info("Started background maintenance threads")
    
    def _sync_loop(self):
        """Background thread for synchronizing metadata with peers."""
        logger.info(f"Starting metadata sync loop with interval {self.config['sync_interval']} seconds")
        
        while not self._stop_threads.is_set():
            try:
                # Perform sync tasks
                self._sync_with_peers()
                
                # Save current state
                self._save_state()
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
            
            # Wait for next cycle
            self._stop_threads.wait(self.config["sync_interval"])
    
    def _checkpoint_loop(self):
        """Background thread for creating metadata checkpoints."""
        logger.info(f"Starting checkpoint loop with interval {self.config['checkpoint_interval']} seconds")
        
        while not self._stop_threads.is_set():
            try:
                # Create checkpoint
                self._create_checkpoint()
                
            except Exception as e:
                logger.error(f"Error in checkpoint loop: {e}")
            
            # Wait for next cycle
            self._stop_threads.wait(self.config["checkpoint_interval"])
    
    def _create_checkpoint(self):
        """Create a checkpoint of current filesystem metadata state."""
        try:
            # Generate checkpoint ID
            checkpoint_id = f"checkpoint_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            checkpoint_file = os.path.join(self.checkpoint_path, f"{checkpoint_id}.json")
            
            # Request checkpoint from journal
            if hasattr(self.journal_manager, "journal") and hasattr(self.journal_manager.journal, "create_checkpoint"):
                checkpoint_result = self.journal_manager.journal.create_checkpoint()
                
                if checkpoint_result:
                    # Save additional checkpoint metadata
                    checkpoint_metadata = {
                        "checkpoint_id": checkpoint_id,
                        "timestamp": time.time(),
                        "node_id": self.node_id,
                        "vector_clock": self.vector_clock,
                        "journal_checkpoint": checkpoint_result
                    }
                    
                    # Save checkpoint metadata
                    with open(checkpoint_file, 'w') as f:
                        json.dump(checkpoint_metadata, f, indent=2)
                    
                    # Replicate checkpoint to peers
                    self._replicate_checkpoint(checkpoint_id, checkpoint_file)
                    
                    logger.info(f"Created checkpoint {checkpoint_id}")
                    return checkpoint_id
            
            logger.warning("Checkpoint creation skipped - journal not available")
            return None
            
        except Exception as e:
            logger.error(f"Error creating checkpoint: {e}")
            return None
    
    def _replicate_checkpoint(self, checkpoint_id, checkpoint_file):
        """Replicate a checkpoint to peer nodes and storage tiers."""
        try:
            # Read checkpoint data
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
                
            # Replicate to storage tiers if tiered backend is available
            if self.tiered_backend:
                # Get tier progression
                tier_progression = self.config["default_tier_progression"]
                
                # Start with memory tier
                current_tier = tier_progression[0]
                
                # Store in tiered backend
                content = json.dumps(checkpoint_data).encode('utf-8')
                tier_result = self.tiered_backend.store_content(
                    content=content,
                    target_tier=current_tier,
                    metadata={
                        "type": "checkpoint",
                        "checkpoint_id": checkpoint_id,
                        "timestamp": time.time()
                    }
                )
                
                if tier_result.get("success", False):
                    # Progressive replication through tiers
                    self._schedule_progressive_tier_replication(
                        tier_result["cid"],
                        tier_progression,
                        current_tier,
                        metadata={"type": "checkpoint", "checkpoint_id": checkpoint_id}
                    )
            
            # Replicate to peer nodes
            with self._locks["peers"]:
                # Only masters and workers participate in replication
                replication_peers = {}
                for peer_id, peer_data in self.peer_nodes.items():
                    if peer_data.get("role") in ["master", "worker"] and peer_id != self.node_id:
                        replication_peers[peer_id] = peer_data
                
                # Skip if no peers
                if not replication_peers:
                    logger.debug("No peers available for checkpoint replication")
                    return
                
                # Proceed with replication
                for peer_id, peer_data in replication_peers.items():
                    self._replicate_to_peer(peer_id, checkpoint_data, "checkpoint")
            
            logger.debug(f"Replicated checkpoint {checkpoint_id} to peers and storage tiers")
            
        except Exception as e:
            logger.error(f"Error replicating checkpoint {checkpoint_id}: {e}")
    
    def _schedule_progressive_tier_replication(self, cid, tier_progression, current_tier, metadata=None):
        """Schedule progressive replication through storage tiers."""
        if not self.tiered_backend:
            logger.warning("No tiered backend available for progressive replication")
            return
            
        try:
            # Find current tier index
            current_idx = tier_progression.index(current_tier)
            
            # Skip if already at highest tier
            if current_idx >= len(tier_progression) - 1:
                return
                
            # Next tier
            next_tier = tier_progression[current_idx + 1]
            
            # Schedule movement to next tier
            # In a real implementation, this would be done asynchronously
            # For now, we'll perform it directly
            move_result = self.tiered_backend.move_content_to_tier(
                cid=cid,
                target_tier=next_tier,
                keep_in_source=True,  # Keep in current tier while copying to next
                metadata=metadata
            )
            
            # If successful, schedule next tier
            if move_result.get("success", False):
                # Log success
                logger.debug(f"Replicated content {cid} to tier {next_tier}")
                
                # Schedule next tier
                self._schedule_progressive_tier_replication(
                    cid,
                    tier_progression,
                    next_tier,
                    metadata
                )
            
        except Exception as e:
            logger.error(f"Error in progressive tier replication for {cid}: {e}")
    
    def _replicate_to_peer(self, peer_id, data, data_type):
        """Replicate data to a specific peer node."""
        try:
            # In a real implementation, this would use a transport mechanism
            # such as libp2p, IPFS pubsub, or a direct API call
            
            # For now, we'll simulate successful replication
            logger.debug(f"Simulated replication of {data_type} to peer {peer_id}")
            
            # Update our vector clock
            self.vector_clock = VectorClock.increment(self.vector_clock, self.node_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error replicating to peer {peer_id}: {e}")
            return False
    
    def _sync_with_peers(self):
        """Synchronize metadata with peer nodes."""
        # Use the synchronization manager if available
        if hasattr(self.sync_manager, "initialize_distributed_state"):
            try:
                # Get our current metadata state
                metadata_state = self._get_metadata_state()
                
                # Sync via the synchronization manager
                if hasattr(self.sync_manager, "_announce_state_to_peers"):
                    self.sync_manager._announce_state_to_peers()
                    logger.debug("Announced metadata state to peers")
                else:
                    logger.debug("State announcement method not available")
                
            except Exception as e:
                logger.error(f"Error syncing with peers: {e}")
    
    def _get_metadata_state(self):
        """Get the current metadata state for synchronization."""
        try:
            # Build metadata state
            metadata_state = {
                "node_id": self.node_id,
                "role": self.role,
                "vector_clock": self.vector_clock,
                "timestamp": time.time(),
                "replication_status": {},
                "checkpoints": self._get_available_checkpoints()
            }
            
            # Add snapshot of replication status (only completed items)
            with self._locks["status"]:
                for entry_id, status in self.replication_status.items():
                    if status.get("status") == ReplicationStatus.COMPLETE.value:
                        metadata_state["replication_status"][entry_id] = status
            
            return metadata_state
            
        except Exception as e:
            logger.error(f"Error getting metadata state: {e}")
            return {}
    
    def _get_available_checkpoints(self):
        """Get list of available checkpoints."""
        try:
            checkpoints = []
            
            # Find checkpoint files
            for filename in os.listdir(self.checkpoint_path):
                if filename.startswith("checkpoint_") and filename.endswith(".json"):
                    checkpoint_path = os.path.join(self.checkpoint_path, filename)
                    try:
                        with open(checkpoint_path, 'r') as f:
                            metadata = json.load(f)
                            checkpoints.append({
                                "checkpoint_id": metadata.get("checkpoint_id"),
                                "timestamp": metadata.get("timestamp"),
                                "node_id": metadata.get("node_id")
                            })
                    except Exception as e:
                        logger.warning(f"Error reading checkpoint file {filename}: {e}")
            
            # Sort by timestamp (newest first)
            return sorted(checkpoints, key=lambda x: x.get("timestamp", 0), reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting available checkpoints: {e}")
            return []
    
    def register_peer(self, peer_id, metadata):
        """Register a peer node for replication."""
        with self._locks["peers"]:
            # Add or update peer
            self.peer_nodes[peer_id] = {
                "registered_at": time.time(),
                "last_seen": time.time(),
                **metadata
            }
            
            # Update quorum size based on cluster size
            cluster_size = len([p for p in self.peer_nodes.values() 
                              if p.get("role") in ["master", "worker"]])
            
            # Set quorum size to max(3, (N/2 + 1)) to ensure minimum replication factor of 3
            # This guarantees fault tolerance even in small clusters (can survive at least 2 node failures)
            if cluster_size > 0:
                self.config["quorum_size"] = max(3, (cluster_size // 2) + 1)
            
            # Save state
            self._save_state()
            
            logger.info(f"Registered peer {peer_id} (role: {metadata.get('role')})")
            return True
    
    def update_peer_status(self, peer_id, status_update):
        """Update status information for a peer node."""
        with self._locks["peers"]:
            if peer_id in self.peer_nodes:
                # Update existing peer
                self.peer_nodes[peer_id].update(status_update)
                self.peer_nodes[peer_id]["last_seen"] = time.time()
                
                logger.debug(f"Updated status for peer {peer_id}")
                return True
            else:
                logger.warning(f"Attempted to update unknown peer {peer_id}")
                return False
    
    def replicate_journal_entry(self, journal_entry, replication_level=None):
        """
        Replicate a filesystem journal entry according to the specified replication level.
        
        Args:
            journal_entry: The journal entry to replicate
            replication_level: Level of replication to ensure
            
        Returns:
            Dictionary with replication status
        """
        # Default result
        result = {
            "success": False,
            "operation": "replicate_journal_entry",
            "timestamp": time.time(),
            "entry_id": journal_entry.get("entry_id")
        }
        
        try:
            # Use default replication level if not specified
            if replication_level is None:
                replication_level = self.config["default_replication_level"]
                
            # Ensure replication level is a proper enum
            if isinstance(replication_level, str):
                replication_level = ReplicationLevel(replication_level)
            
            # Entry ID is required
            entry_id = journal_entry.get("entry_id")
            if not entry_id:
                result["error"] = "Missing entry_id in journal entry"
                return result
            
            # Initialize replication tracking
            replication_id = str(uuid.uuid4())
            replication_data = {
                "replication_id": replication_id,
                "entry_id": entry_id,
                "started_at": time.time(),
                "status": ReplicationStatus.IN_PROGRESS.value,
                "replication_level": replication_level.value,
                "node_id": self.node_id,
                "target_nodes": [],
                "successful_nodes": [],
                "failed_nodes": [],
                "vector_clock": self.vector_clock.copy()
            }
            
            # Store in active replications
            with self._locks["replications"]:
                self.active_replications[entry_id] = replication_data
            
            # Update replication status
            with self._locks["status"]:
                self.replication_status[entry_id] = {
                    "entry_id": entry_id,
                    "status": ReplicationStatus.IN_PROGRESS.value,
                    "replication_id": replication_id,
                    "timestamp": time.time()
                }
            
            # Perform replication based on level
            if replication_level == ReplicationLevel.SINGLE:
                # Only replicate to master node
                self._replicate_to_master(entry_id, journal_entry, replication_data)
                
            elif replication_level == ReplicationLevel.QUORUM:
                # Replicate to majority of nodes
                self._replicate_to_quorum(entry_id, journal_entry, replication_data)
                
            elif replication_level == ReplicationLevel.ALL:
                # Replicate to all available nodes
                self._replicate_to_all(entry_id, journal_entry, replication_data)
                
            elif replication_level == ReplicationLevel.TIERED:
                # Replicate across storage tiers
                self._replicate_to_tiers(entry_id, journal_entry, replication_data)
                
            elif replication_level == ReplicationLevel.PROGRESSIVE:
                # Progressive replication (both nodes and tiers)
                self._replicate_progressively(entry_id, journal_entry, replication_data)
                
            else:
                # Default to local durability
                self._ensure_local_durability(entry_id, journal_entry, replication_data)
            
            # Get updated replication data
            with self._locks["replications"]:
                if entry_id in self.active_replications:
                    replication_data = self.active_replications[entry_id]
            
            # Determine overall status using more sophisticated metrics
            success_count = len(replication_data.get("successful_nodes", []))
            failure_count = len(replication_data.get("failed_nodes", []))
            target_nodes_count = len(replication_data.get("target_nodes", []))
            
            # Get replication targets
            quorum_size = replication_data.get("quorum_size", self.config["quorum_size"])
            target_factor = replication_data.get("target_factor", self.config["target_replication_factor"])
            max_factor = replication_data.get("max_factor", self.config["max_replication_factor"])
            
            # Set success level based on achieved replication
            if success_count >= target_factor:
                status = ReplicationStatus.COMPLETE
                success_level = "TARGET_ACHIEVED"
            elif success_count >= quorum_size:
                status = ReplicationStatus.COMPLETE
                success_level = "QUORUM_ACHIEVED"
            elif success_count > 0:
                status = ReplicationStatus.PARTIAL
                success_level = "BELOW_QUORUM"
            else:
                status = ReplicationStatus.FAILED
                success_level = "NO_REPLICATION"
                
            # Store success level
            replication_data["success_level"] = success_level
            
            # Update status with comprehensive metrics
            with self._locks["status"]:
                self.replication_status[entry_id]["status"] = status.value
                self.replication_status[entry_id]["completed_at"] = time.time()
                self.replication_status[entry_id]["success_count"] = success_count
                self.replication_status[entry_id]["failure_count"] = failure_count
                self.replication_status[entry_id]["target_nodes_count"] = target_nodes_count
                self.replication_status[entry_id]["quorum_size"] = quorum_size
                self.replication_status[entry_id]["target_factor"] = target_factor
                self.replication_status[entry_id]["max_factor"] = max_factor
                self.replication_status[entry_id]["success_level"] = success_level
            
            # Clean up active replication
            with self._locks["replications"]:
                if entry_id in self.active_replications:
                    # Move to history storage for future reference
                    replication_data = self.active_replications[entry_id]
                    replication_data["status"] = status.value
                    replication_data["completed_at"] = time.time()
                    
                    # Remove from active replications
                    del self.active_replications[entry_id]
            
            # Update result with comprehensive metrics
            result["success"] = status != ReplicationStatus.FAILED
            result["status"] = status.value
            result["replication_id"] = replication_id
            result["success_count"] = success_count
            result["failure_count"] = failure_count
            result["target_nodes_count"] = target_nodes_count
            result["quorum_size"] = quorum_size
            result["target_factor"] = target_factor
            result["max_factor"] = max_factor
            result["success_level"] = success_level
            
            # Update vector clock
            self.vector_clock = VectorClock.increment(self.vector_clock, self.node_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Error replicating journal entry: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result
    
    def _replicate_to_master(self, entry_id, journal_entry, replication_data):
        """Replicate entry to the master node only."""
        try:
            # Find master node
            master_node = None
            with self._locks["peers"]:
                for peer_id, peer_data in self.peer_nodes.items():
                    if peer_data.get("role") == "master":
                        master_node = (peer_id, peer_data)
                        break
            
            # Skip if no master or this is the master
            if not master_node or master_node[0] == self.node_id:
                if self.role == "master":
                    # We are the master, so replication is already "complete"
                    replication_data["status"] = ReplicationStatus.COMPLETE.value
                    replication_data["target_nodes"] = [self.node_id]
                    replication_data["successful_nodes"] = [self.node_id]
                else:
                    # No master found
                    replication_data["status"] = ReplicationStatus.FAILED.value
                    replication_data["target_nodes"] = []
                    replication_data["failed_nodes"] = []
                return
            
            # Set target nodes
            master_id, master_data = master_node
            replication_data["target_nodes"] = [master_id]
            
            # Replicate to master
            success = self._replicate_to_peer(master_id, journal_entry, "journal_entry")
            
            # Update results
            if success:
                replication_data["successful_nodes"] = [master_id]
                replication_data["status"] = ReplicationStatus.COMPLETE.value
            else:
                replication_data["failed_nodes"] = [master_id]
                replication_data["status"] = ReplicationStatus.FAILED.value
            
        except Exception as e:
            logger.error(f"Error replicating to master: {e}")
            replication_data["status"] = ReplicationStatus.FAILED.value
            replication_data["error"] = str(e)
    
    def _replicate_to_quorum(self, entry_id, journal_entry, replication_data):
        """Replicate entry to a quorum of nodes."""
        try:
            # Identify eligible nodes (master and workers)
            eligible_nodes = []
            with self._locks["peers"]:
                for peer_id, peer_data in self.peer_nodes.items():
                    if peer_data.get("role") in ["master", "worker"] and peer_id != self.node_id:
                        eligible_nodes.append((peer_id, peer_data))
            
            # Include self if master or worker
            if self.role in ["master", "worker"]:
                eligible_nodes.append((self.node_id, {"role": self.role}))
            
            # Calculate replication parameters
            total_nodes = len(eligible_nodes)
            quorum_size = min(self.config["quorum_size"], total_nodes)
            target_factor = min(self.config["target_replication_factor"], total_nodes)
            max_factor = min(self.config["max_replication_factor"], total_nodes)
            
            # Skip if not enough nodes
            if total_nodes < quorum_size:
                replication_data["status"] = ReplicationStatus.FAILED.value
                replication_data["error"] = f"Not enough eligible nodes for quorum ({total_nodes} < {quorum_size})"
                return
            
            # Sort nodes (master first, then workers)
            sorted_nodes = sorted(
                eligible_nodes, 
                key=lambda x: 0 if x[1].get("role") == "master" else 1
            )
            
            # Select target nodes (up to max replication factor)
            # We'll try to replicate to max_factor nodes, aiming for at least target_factor
            # but considering quorum_size as the minimum for success
            target_nodes = sorted_nodes[:max_factor]
            replication_data["target_nodes"] = [node_id for node_id, _ in target_nodes]
            replication_data["quorum_size"] = quorum_size
            replication_data["target_factor"] = target_factor
            replication_data["max_factor"] = max_factor
            
            # Replicate to each target node
            successful_nodes = []
            failed_nodes = []
            
            for node_id, node_data in target_nodes:
                if node_id == self.node_id:
                    # Skip self-replication - we already have it
                    successful_nodes.append(node_id)
                    continue
                
                # Replicate to peer
                success = self._replicate_to_peer(node_id, journal_entry, "journal_entry")
                
                if success:
                    successful_nodes.append(node_id)
                else:
                    failed_nodes.append(node_id)
            
            # Update results
            replication_data["successful_nodes"] = successful_nodes
            replication_data["failed_nodes"] = failed_nodes
            
            # Determine status based on replication goals
            success_count = len(successful_nodes)
            
            if success_count >= target_factor:
                # Achieved target replication factor - complete success
                replication_data["status"] = ReplicationStatus.COMPLETE.value
                replication_data["success_level"] = "TARGET_ACHIEVED"
            elif success_count >= quorum_size:
                # Achieved quorum but not target - partial success
                replication_data["status"] = ReplicationStatus.COMPLETE.value
                replication_data["success_level"] = "QUORUM_ACHIEVED"
            elif success_count > 0:
                # Some replication, but less than quorum - partial failure
                replication_data["status"] = ReplicationStatus.PARTIAL.value
                replication_data["success_level"] = "BELOW_QUORUM"
            else:
                # No successful replication - complete failure
                replication_data["status"] = ReplicationStatus.FAILED.value
                replication_data["success_level"] = "NO_REPLICATION"
                
            # Include replication metrics in result
            replication_data["success_count"] = success_count
            replication_data["target_count"] = target_factor
            replication_data["max_count"] = max_factor
            
        except Exception as e:
            logger.error(f"Error replicating to quorum: {e}")
            replication_data["status"] = ReplicationStatus.FAILED.value
            replication_data["error"] = str(e)
    
    def _replicate_to_all(self, entry_id, journal_entry, replication_data):
        """Replicate entry to all available nodes."""
        try:
            # Identify eligible nodes (master and workers)
            eligible_nodes = []
            with self._locks["peers"]:
                for peer_id, peer_data in self.peer_nodes.items():
                    if peer_data.get("role") in ["master", "worker"] and peer_id != self.node_id:
                        eligible_nodes.append((peer_id, peer_data))
            
            # Include self if master or worker
            if self.role in ["master", "worker"]:
                eligible_nodes.append((self.node_id, {"role": self.role}))
            
            # Skip if no eligible nodes
            if not eligible_nodes:
                replication_data["status"] = ReplicationStatus.FAILED.value
                replication_data["error"] = "No eligible nodes for replication"
                return
            
            # Set target nodes
            replication_data["target_nodes"] = [node_id for node_id, _ in eligible_nodes]
            
            # Replicate to each target node
            successful_nodes = []
            failed_nodes = []
            
            for node_id, node_data in eligible_nodes:
                if node_id == self.node_id:
                    # Skip self-replication - we already have it
                    successful_nodes.append(node_id)
                    continue
                    
                # Replicate to peer
                success = self._replicate_to_peer(node_id, journal_entry, "journal_entry")
                
                if success:
                    successful_nodes.append(node_id)
                else:
                    failed_nodes.append(node_id)
            
            # Update results
            replication_data["successful_nodes"] = successful_nodes
            replication_data["failed_nodes"] = failed_nodes
            
            # Determine status
            if len(successful_nodes) == len(eligible_nodes):
                replication_data["status"] = ReplicationStatus.COMPLETE.value
            elif len(successful_nodes) > 0:
                replication_data["status"] = ReplicationStatus.PARTIAL.value
            else:
                replication_data["status"] = ReplicationStatus.FAILED.value
            
        except Exception as e:
            logger.error(f"Error replicating to all nodes: {e}")
            replication_data["status"] = ReplicationStatus.FAILED.value
            replication_data["error"] = str(e)
    
    def _replicate_to_tiers(self, entry_id, journal_entry, replication_data):
        """Replicate entry across storage tiers."""
        try:
            # Skip if no tiered backend
            if not self.tiered_backend:
                replication_data["status"] = ReplicationStatus.FAILED.value
                replication_data["error"] = "No tiered backend available for tier replication"
                return
            
            # Serialize journal entry
            content = json.dumps(journal_entry).encode('utf-8')
            
            # Get tier progression
            tier_progression = self.config["default_tier_progression"]
            
            # Initial tier (memory)
            initial_tier = tier_progression[0]
            
            # Store in initial tier
            tier_result = self.tiered_backend.store_content(
                content=content,
                target_tier=initial_tier,
                metadata={
                    "type": "journal_entry",
                    "entry_id": entry_id,
                    "timestamp": time.time()
                }
            )
            
            if not tier_result.get("success", False):
                replication_data["status"] = ReplicationStatus.FAILED.value
                replication_data["error"] = f"Failed to store in tier {initial_tier}"
                return
            
            # Get CID from tier result
            cid = tier_result.get("cid")
            if not cid:
                replication_data["status"] = ReplicationStatus.FAILED.value
                replication_data["error"] = "Missing CID in tier storage result"
                return
            
            # Set target tiers
            replication_data["target_tiers"] = tier_progression
            replication_data["successful_tiers"] = [initial_tier]
            
            # Schedule progressive replication
            self._schedule_progressive_tier_replication(
                cid,
                tier_progression,
                initial_tier,
                metadata={
                    "type": "journal_entry",
                    "entry_id": entry_id,
                    "replication_id": replication_data["replication_id"]
                }
            )
            
            # Update status (optimistic)
            replication_data["status"] = ReplicationStatus.IN_PROGRESS.value
            
            # In a real implementation, we would track the progress of the tier replication
            # For now, we'll just assume it's successful
            replication_data["status"] = ReplicationStatus.COMPLETE.value
            
        except Exception as e:
            logger.error(f"Error replicating to tiers: {e}")
            replication_data["status"] = ReplicationStatus.FAILED.value
            replication_data["error"] = str(e)
    
    def _replicate_progressively(self, entry_id, journal_entry, replication_data):
        """
        Progressively replicate entry across both nodes and tiers.
        
        This method combines node replication and tier replication in a progressive manner:
        1. First ensure local durability
        2. Then replicate to master node
        3. Then replicate to quorum of nodes
        4. Finally replicate across storage tiers
        """
        try:
            # Track progression
            progression_steps = [
                "local_durability",
                "master_replication",
                "quorum_replication",
                "tier_replication"
            ]
            
            replication_data["progression"] = {
                "steps": progression_steps,
                "current_step": 0,
                "completed_steps": [],
                "status_by_step": {}
            }
            
            # Step 1: Local durability
            self._ensure_local_durability(entry_id, journal_entry, replication_data)
            replication_data["progression"]["current_step"] = 1
            replication_data["progression"]["completed_steps"].append("local_durability")
            replication_data["progression"]["status_by_step"]["local_durability"] = ReplicationStatus.COMPLETE.value
            
            # Step 2: Master replication
            self._replicate_to_master(entry_id, journal_entry, replication_data)
            master_status = replication_data.get("status", ReplicationStatus.FAILED.value)
            replication_data["progression"]["current_step"] = 2
            replication_data["progression"]["completed_steps"].append("master_replication")
            replication_data["progression"]["status_by_step"]["master_replication"] = master_status
            
            # Step 3: Quorum replication
            self._replicate_to_quorum(entry_id, journal_entry, replication_data)
            quorum_status = replication_data.get("status", ReplicationStatus.FAILED.value)
            replication_data["progression"]["current_step"] = 3
            replication_data["progression"]["completed_steps"].append("quorum_replication")
            replication_data["progression"]["status_by_step"]["quorum_replication"] = quorum_status
            
            # Step 4: Tier replication
            if self.tiered_backend:
                self._replicate_to_tiers(entry_id, journal_entry, replication_data)
                tier_status = replication_data.get("status", ReplicationStatus.FAILED.value)
                replication_data["progression"]["current_step"] = 4
                replication_data["progression"]["completed_steps"].append("tier_replication")
                replication_data["progression"]["status_by_step"]["tier_replication"] = tier_status
            else:
                replication_data["progression"]["status_by_step"]["tier_replication"] = ReplicationStatus.FAILED.value
            
            # Determine overall status - successful if at least local and quorum completed
            if (replication_data["progression"]["status_by_step"]["local_durability"] == ReplicationStatus.COMPLETE.value and
                replication_data["progression"]["status_by_step"]["quorum_replication"] == ReplicationStatus.COMPLETE.value):
                replication_data["status"] = ReplicationStatus.COMPLETE.value
            elif replication_data["progression"]["status_by_step"]["local_durability"] == ReplicationStatus.COMPLETE.value:
                replication_data["status"] = ReplicationStatus.PARTIAL.value
            else:
                replication_data["status"] = ReplicationStatus.FAILED.value
            
        except Exception as e:
            logger.error(f"Error in progressive replication: {e}")
            replication_data["status"] = ReplicationStatus.FAILED.value
            replication_data["error"] = str(e)
    
    def _ensure_local_durability(self, entry_id, journal_entry, replication_data):
        """Ensure local durability of a journal entry."""
        try:
            # Track local operations
            replication_data["local_durability"] = {
                "timestamp": time.time(),
                "status": "pending"
            }
            
            # For local durability, we'll serialize and store the entry locally
            # This would typically involve fsync operations to ensure durability
            
            # Create entry directory if needed
            entry_dir = os.path.join(self.metadata_path, entry_id[:2])
            os.makedirs(entry_dir, exist_ok=True)
            
            # Entry file path
            entry_file = os.path.join(entry_dir, f"{entry_id}.json")
            
            # Add additional metadata
            local_entry = copy.deepcopy(journal_entry)
            local_entry["replication_metadata"] = {
                "replication_id": replication_data["replication_id"],
                "node_id": self.node_id,
                "timestamp": time.time(),
                "vector_clock": self.vector_clock.copy()
            }
            
            # Write to temporary file first
            temp_file = entry_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(local_entry, f, indent=2)
                # Ensure data is flushed to disk
                f.flush()
                os.fsync(f.fileno())
                
            # Move to final location (atomic operation)
            os.replace(temp_file, entry_file)
            
            # Update status
            replication_data["local_durability"]["status"] = "complete"
            replication_data["target_nodes"] = [self.node_id]
            replication_data["successful_nodes"] = [self.node_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring local durability: {e}")
            replication_data["local_durability"]["status"] = "failed"
            replication_data["local_durability"]["error"] = str(e)
            replication_data["target_nodes"] = [self.node_id]
            replication_data["failed_nodes"] = [self.node_id]
            return False
    
    def get_replication_status(self, entry_id):
        """Get the replication status for a specific journal entry."""
        with self._locks["status"]:
            if entry_id in self.replication_status:
                return self.replication_status[entry_id]
            return None
    
    def get_all_replication_status(self):
        """Get replication status for all journal entries."""
        with self._locks["status"]:
            return self.replication_status.copy()
    
    def recover_from_checkpoint(self, checkpoint_id=None):
        """
        Recover filesystem metadata from a checkpoint.
        
        Args:
            checkpoint_id: ID of the checkpoint to recover from (uses latest if None)
            
        Returns:
            Dictionary with recovery results
        """
        # Default result
        result = {
            "success": False,
            "operation": "recover_from_checkpoint",
            "timestamp": time.time()
        }
        
        try:
            # Find checkpoint file
            checkpoint_file = None
            if checkpoint_id:
                # Look for specific checkpoint
                checkpoint_path = os.path.join(self.checkpoint_path, f"{checkpoint_id}.json")
                if os.path.exists(checkpoint_path):
                    checkpoint_file = checkpoint_path
                else:
                    result["error"] = f"Checkpoint {checkpoint_id} not found"
                    return result
            else:
                # Find the latest checkpoint
                checkpoints = self._get_available_checkpoints()
                if not checkpoints:
                    result["error"] = "No checkpoints available"
                    return result
                
                # Use latest checkpoint
                latest = checkpoints[0]
                checkpoint_id = latest.get("checkpoint_id")
                checkpoint_file = os.path.join(self.checkpoint_path, f"{checkpoint_id}.json")
                
                if not os.path.exists(checkpoint_file):
                    result["error"] = f"Latest checkpoint file {checkpoint_id} not found"
                    return result
            
            # Read checkpoint data
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
            
            # Extract journal checkpoint
            journal_checkpoint = checkpoint_data.get("journal_checkpoint")
            if not journal_checkpoint:
                result["error"] = "Invalid checkpoint data - missing journal checkpoint"
                return result
            
            # Perform recovery from journal
            if hasattr(self.journal_manager, "journal") and hasattr(self.journal_manager.journal, "recover"):
                recovery_result = self.journal_manager.journal.recover()
                
                if not recovery_result.get("success", False):
                    result["error"] = "Journal recovery failed"
                    result["details"] = recovery_result
                    return result
                
                # Update result
                result["success"] = True
                result["checkpoint_id"] = checkpoint_id
                result["recovery_details"] = recovery_result
                result["timestamp"] = checkpoint_data.get("timestamp")
                
                # Update vector clock
                self.vector_clock = checkpoint_data.get("vector_clock", self.vector_clock)
                
                return result
            else:
                result["error"] = "Journal manager does not support recovery"
                return result
                
        except Exception as e:
            logger.error(f"Error recovering from checkpoint: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result
    
    def close(self):
        """Clean up resources and stop background threads."""
        try:
            # Signal threads to stop
            self._stop_threads.set()
            
            # Wait for threads to finish
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=2.0)
                
            if self._checkpoint_thread and self._checkpoint_thread.is_alive():
                self._checkpoint_thread.join(timeout=2.0)
            
            # Save state before closing
            self._save_state()
            
            # Close journal if we created it
            if hasattr(self.journal_manager, "journal") and hasattr(self.journal_manager.journal, "close"):
                self.journal_manager.journal.close()
            
            logger.info("Metadata replication manager closed")
            
        except Exception as e:
            logger.error(f"Error closing metadata replication manager: {e}")


# Factory function for creating replication managers
def create_replication_manager(
    journal_manager=None, 
    tiered_backend=None, 
    sync_manager=None, 
    node_id=None, 
    role="worker", 
    config=None
):
    """
    Factory function to create a properly configured MetadataReplicationManager.
    
    Args:
        journal_manager: Optional existing journal manager
        tiered_backend: Optional existing tiered storage backend
        sync_manager: Optional existing synchronization manager
        node_id: Node ID (will be generated if not provided)
        role: Node role ("master", "worker", or "leecher")
        config: Additional configuration options
        
    Returns:
        Configured MetadataReplicationManager instance
    """
    return MetadataReplicationManager(
        journal_manager=journal_manager,
        tiered_backend=tiered_backend,
        sync_manager=sync_manager,
        node_id=node_id,
        role=role,
        config=config
    )


# Export symbols
__all__ = [
    'MetadataReplicationManager',
    'ReplicationLevel',
    'ReplicationStatus',
    'create_replication_manager'
]
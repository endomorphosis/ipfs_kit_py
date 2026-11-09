"""
Distributed state synchronization for IPFS cluster nodes (Phase 3B).

This module implements distributed state synchronization using:
- Conflict-free replicated data types (CRDT) for distributed state
- Automatic state reconciliation
- Causality tracking with vector clocks
- Gossip-based state propagation
- Eventually consistent distributed state
- Partial state updates and differential sync
"""

import copy
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

import jsonpatch

# Configure logger
logger = logging.getLogger(__name__)


class VectorClock:
    """Implementation of vector clocks for tracking causality across distributed nodes."""

    @staticmethod
    def create() -> Dict[str, int]:
        """Create a new empty vector clock.

        Returns:
            Dictionary with node IDs as keys and counters as values
        """
        return {}

    @staticmethod
    def increment(vector_clock: Dict[str, int], node_id: str) -> Dict[str, int]:
        """Increment the counter for a node in a vector clock.

        Args:
            vector_clock: Existing vector clock
            node_id: ID of the node to increment counter for

        Returns:
            Updated vector clock
        """
        result = vector_clock.copy()
        result[node_id] = result.get(node_id, 0) + 1
        return result

    @staticmethod
    def merge(clock1: Dict[str, int], clock2: Dict[str, int]) -> Dict[str, int]:
        """Merge two vector clocks by taking the maximum of each entry.

        Args:
            clock1: First vector clock
            clock2: Second vector clock

        Returns:
            Merged vector clock
        """
        result = clock1.copy()
        for node_id, counter in clock2.items():
            result[node_id] = max(result.get(node_id, 0), counter)
        return result

    @staticmethod
    def compare(clock1: Dict[str, int], clock2: Dict[str, int]) -> Dict[str, Any]:
        """Compare two vector clocks to determine their causality relationship.

        Args:
            clock1: First vector clock
            clock2: Second vector clock

        Returns:
            Dictionary with relationship information
        """
        clock1_before_clock2 = True
        clock2_before_clock1 = True

        # Check entries in clock1
        for node_id, counter in clock1.items():
            if node_id in clock2:
                if counter > clock2[node_id]:
                    clock1_before_clock2 = False
                if counter < clock2[node_id]:
                    clock2_before_clock1 = False
            else:
                clock2_before_clock1 = False

        # Check entries in clock2 but not in clock1
        for node_id in clock2:
            if node_id not in clock1:
                clock1_before_clock2 = False

        # Determine relationship
        if clock1_before_clock2 and not clock2_before_clock1:
            return {"relationship": "before", "description": "First happens before second"}
        elif clock2_before_clock1 and not clock1_before_clock2:
            return {"relationship": "after", "description": "First happens after second"}
        elif not clock1_before_clock2 and not clock2_before_clock1:
            return {"relationship": "concurrent", "description": "First and second are concurrent"}
        else:
            return {"relationship": "equal", "description": "First and second are equal"}


class StateCRDT:
    """CRDT implementation for distributed state with automatic conflict resolution."""

    def __init__(self, node_id: str, consensus_algorithm: str = "lww"):
        """Initialize the CRDT system.

        Args:
            node_id: Unique identifier for this node
            consensus_algorithm: Conflict resolution algorithm to use
        """
        self.node_id = node_id
        self.consensus_algorithm = consensus_algorithm
        self.state = {}
        self.vector_clock = VectorClock.create()
        self.update_log = []
        self.sequence_number = 0
        self.locks = {"state": threading.RLock(), "update_log": threading.RLock()}

    def initialize(self, initial_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Initialize the distributed state with initial data.

        Args:
            initial_data: Initial state data

        Returns:
            Result of the initialization
        """
        result = {"success": True, "operation": "initialize", "timestamp": time.time()}

        try:
            with self.locks["state"]:
                # Initialize state with data or empty dict
                self.state = initial_data or {}

                # Initialize vector clock with first update
                self.vector_clock = VectorClock.increment(VectorClock.create(), self.node_id)

                # Create first entry in update log
                initial_update = {
                    "node_id": self.node_id,
                    "timestamp": time.time(),
                    "vector_clock": self.vector_clock.copy(),
                    "sequence_number": 0,
                    "type": "initialize",
                    "data": self.state.copy(),
                }

                with self.locks["update_log"]:
                    self.update_log = [initial_update]
                    self.sequence_number = 1

                # Return initialization status
                result.update(
                    {
                        "state_id": str(uuid.uuid4()),
                        "initial_data": self.state,
                        "vector_clock": self.vector_clock,
                    }
                )

                return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to initialize state: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error initializing state: {e}")
            return result

    def get_state_update(self, peer_id: str, last_sequence: int = None) -> Dict[str, Any]:
        """Get updates for peer synchronization.

        Args:
            peer_id: ID of the peer requesting updates
            last_sequence: Last sequence number the peer has

        Returns:
            Dictionary with update information
        """
        result = {"success": True, "operation": "get_state_update", "timestamp": time.time()}

        try:
            with self.locks["update_log"]:
                # If peer has no sequence number, send full state
                if last_sequence is None:
                    result.update(
                        {
                            "sequence_number": self.sequence_number - 1,
                            "updates": self.state,
                            "update_type": "full",
                            "vector_clock": self.vector_clock,
                            "node_id": self.node_id,
                        }
                    )
                    return result

                # If peer is up to date, send empty update
                if last_sequence >= self.sequence_number - 1:
                    result.update(
                        {
                            "sequence_number": self.sequence_number - 1,
                            "updates": [],
                            "update_type": "no_changes",
                            "vector_clock": self.vector_clock,
                        }
                    )
                    return result

                # Get all updates after last_sequence
                relevant_updates = []
                for update in self.update_log:
                    if update["sequence_number"] > last_sequence:
                        relevant_updates.append(update)

                # Create updates array
                updates = []
                for update in relevant_updates:
                    if update["type"] == "patch":
                        updates.extend(update["patch"])

                # Return updates
                result.update(
                    {
                        "sequence_number": self.sequence_number - 1,
                        "updates": updates,
                        "update_type": "partial",
                        "vector_clock": self.vector_clock,
                        "update_count": len(updates),
                    }
                )

                return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to get state update: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error getting state update: {e}")
            return result

    def apply_updates(
        self, updates: List[Dict[str, Any]], vector_clock: Dict[str, int], sequence_number: int
    ) -> Dict[str, Any]:
        """Apply updates from another node to the local state.

        Args:
            updates: List of updates to apply
            vector_clock: Vector clock from the sending node
            sequence_number: Sequence number of the update

        Returns:
            Result of applying the updates
        """
        result = {"success": True, "operation": "apply_updates", "timestamp": time.time()}

        try:
            # Check if we've already applied this update
            if sequence_number < self.sequence_number:
                result.update(
                    {
                        "success": True,
                        "applied_count": 0,
                        "new_sequence_number": self.sequence_number,
                        "new_vector_clock": self.vector_clock,
                        "message": "Updates already applied",
                    }
                )
                return result

            # Apply the patches
            with self.locks["state"]:
                # Create a working copy of the state
                new_state = copy.deepcopy(self.state)

                # Apply each update
                for update in updates:
                    self._apply_patch_operation(new_state, update)

                # Detect conflicts
                conflict_detection = self.detect_conflicts(updates)

                # If conflicts exist, resolve them
                if conflict_detection["has_conflict"]:
                    for conflict in conflict_detection["conflicts"]:
                        if self.consensus_algorithm == "lww":
                            resolution = self.resolve_conflict_lww(conflict)
                            if resolution["resolved"]:
                                # Apply the winner
                                path_parts = conflict["path"].lstrip("/").split("/")
                                self._set_nested_value(
                                    new_state, path_parts, resolution["winner"]["value"]
                                )
                        else:
                            # Default to last-write-wins
                            resolution = self.resolve_conflict_lww(conflict)
                            if resolution["resolved"]:
                                # Apply the winner
                                path_parts = conflict["path"].lstrip("/").split("/")
                                self._set_nested_value(
                                    new_state, path_parts, resolution["winner"]["value"]
                                )

                # Update state and vector clock
                self.state = new_state
                self.vector_clock = VectorClock.merge(self.vector_clock, vector_clock)

                # Increment sequence number and vector clock for this node
                self.sequence_number = sequence_number + 1
                self.vector_clock = VectorClock.increment(self.vector_clock, self.node_id)

                # Add to update log
                update_entry = {
                    "node_id": self.node_id,
                    "timestamp": time.time(),
                    "vector_clock": self.vector_clock.copy(),
                    "sequence_number": sequence_number,
                    "type": "patch",
                    "patch": updates,
                    "received_from": "sync",
                }

                with self.locks["update_log"]:
                    self.update_log.append(update_entry)

                    # Trim update log if it's getting too long
                    if len(self.update_log) > 1000:
                        self.update_log = self.update_log[-1000:]

                # Return result
                result.update(
                    {
                        "applied_count": len(updates),
                        "new_sequence_number": self.sequence_number,
                        "new_vector_clock": self.vector_clock,
                    }
                )

                return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to apply updates: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error applying updates: {e}")
            return result

    def _apply_patch_operation(self, state: Dict[str, Any], operation: Dict[str, Any]) -> None:
        """Apply a single patch operation to the state.

        Args:
            state: State dictionary to modify
            operation: Operation to apply
        """
        op = operation["op"]
        path = operation["path"]

        # Convert path to parts
        path_parts = path.lstrip("/").split("/")

        if op == "add" or op == "replace":
            value = operation["value"]
            self._set_nested_value(state, path_parts, value)
        elif op == "remove":
            self._remove_nested_value(state, path_parts)
        elif op == "copy":
            from_path = operation["from"].lstrip("/").split("/")
            value = self._get_nested_value(state, from_path)
            self._set_nested_value(state, path_parts, value)
        elif op == "move":
            from_path = operation["from"].lstrip("/").split("/")
            value = self._get_nested_value(state, from_path)
            self._remove_nested_value(state, from_path)
            self._set_nested_value(state, path_parts, value)
        elif op == "test":
            # Test operation - used for validating patches
            value = operation["value"]
            current = self._get_nested_value(state, path_parts)
            if current != value:
                raise ValueError(f"Test operation failed: expected {value}, got {current}")

    def _get_nested_value(self, obj: Dict[str, Any], path_parts: List[str]) -> Any:
        """Get a nested value from a dictionary by path parts.

        Args:
            obj: Dictionary to get value from
            path_parts: Path to the value as list of parts

        Returns:
            Value at the specified path
        """
        if not path_parts:
            return obj

        current = obj
        for i, part in enumerate(path_parts):
            if isinstance(current, dict):
                # Handle numeric keys for dict
                if part.isdigit():
                    part = int(part) if isinstance(current, list) else part
                if part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Path '{'/'.join(path_parts[:i+1])}' does not exist")
            elif isinstance(current, list):
                # Handle array indices
                if part.isdigit():
                    idx = int(part)
                    if idx < len(current):
                        current = current[idx]
                    else:
                        raise IndexError(
                            f"Index {idx} out of range for array of length {len(current)}"
                        )
                else:
                    raise ValueError(f"Expected integer index for array, got '{part}'")
            else:
                raise ValueError(
                    f"Cannot get nested value from non-container type: {type(current)}"
                )

        return current

    def _set_nested_value(self, obj: Dict[str, Any], path_parts: List[str], value: Any) -> None:
        """Set a nested value in a dictionary by path parts.

        Args:
            obj: Dictionary to set value in
            path_parts: Path to the value as list of parts
            value: Value to set
        """
        if not path_parts:
            # Can't set the root object directly
            raise ValueError("Cannot set root object")

        # Handle the last part separately
        *parent_parts, last_part = path_parts

        # Navigate to the parent object
        parent = obj

        for i, part in enumerate(parent_parts):
            next_part = parent_parts[i + 1] if i + 1 < len(parent_parts) else last_part

            # Check if we need to create non-existent parent objects
            if part not in parent:
                # If next part is a number, create a list, otherwise a dict
                parent[part] = [] if next_part.isdigit() else {}

            parent = parent[part]

        # Convert the last part to an integer if parent is a list
        if isinstance(parent, list):
            if last_part == "-":
                # Append to the array
                parent.append(value)
            else:
                # Set by index
                idx = int(last_part)
                # Expand the list if needed
                while len(parent) <= idx:
                    parent.append(None)
                parent[idx] = value
        else:
            # Set in dictionary
            parent[last_part] = value

    def _remove_nested_value(self, obj: Dict[str, Any], path_parts: List[str]) -> None:
        """Remove a nested value from a dictionary by path parts.

        Args:
            obj: Dictionary to remove value from
            path_parts: Path to the value as list of parts
        """
        if not path_parts:
            # Can't remove the root object
            raise ValueError("Cannot remove root object")

        # Handle the last part separately
        *parent_parts, last_part = path_parts

        # Navigate to the parent object
        parent = obj
        for part in parent_parts:
            if part in parent:
                parent = parent[part]
            else:
                # Path doesn't exist, nothing to remove
                return

        # Remove from the parent
        if isinstance(parent, dict) and last_part in parent:
            del parent[last_part]
        elif isinstance(parent, list) and last_part.isdigit():
            idx = int(last_part)
            if idx < len(parent):
                del parent[idx]

    def create_patch(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
        """Create a JSON patch between old and new states.

        Args:
            old_state: Original state
            new_state: New state

        Returns:
            Dictionary with patch information
        """
        result = {"success": True, "operation": "create_patch", "timestamp": time.time()}

        try:
            # Generate JSON patch
            patch = jsonpatch.make_patch(old_state, new_state)
            patch_list = patch.patch

            with self.locks["state"]:
                # Update vector clock
                self.vector_clock = VectorClock.increment(self.vector_clock, self.node_id)

                # Record in update log
                update_entry = {
                    "node_id": self.node_id,
                    "timestamp": time.time(),
                    "vector_clock": self.vector_clock.copy(),
                    "sequence_number": self.sequence_number,
                    "type": "patch",
                    "patch": patch_list,
                }

                with self.locks["update_log"]:
                    self.update_log.append(update_entry)
                    self.sequence_number += 1

                # Update local state if we're generating the patch
                self.state = new_state

                # Return patch info
                result.update(
                    {
                        "patch": patch_list,
                        "from_version": self.sequence_number - 1,
                        "to_version": self.sequence_number,
                        "vector_clock": self.vector_clock,
                    }
                )

                return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to create patch: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error creating patch: {e}")
            return result

    def apply_patch(
        self,
        current_state: Dict[str, Any],
        patch: List[Dict[str, Any]],
        from_version: int = None,
        to_version: int = None,
    ) -> Dict[str, Any]:
        """Apply a JSON patch to a state.

        Args:
            current_state: State to apply patch to
            patch: Patch operations to apply
            from_version: Source version number
            to_version: Target version number

        Returns:
            Dictionary with result of applying the patch
        """
        result = {"success": True, "operation": "apply_patch", "timestamp": time.time()}

        try:
            # Create a copy of the state to modify
            result_state = copy.deepcopy(current_state)

            # Apply each operation in the patch
            for op in patch:
                self._apply_patch_operation(result_state, op)

            # Update our state if versions match our expected sequence
            if (
                from_version is not None
                and to_version is not None
                and from_version == self.sequence_number - 1
            ):
                with self.locks["state"]:
                    self.state = result_state
                    self.sequence_number = to_version

                    # Update vector clock
                    self.vector_clock = VectorClock.increment(self.vector_clock, self.node_id)

                    # Record in update log
                    update_entry = {
                        "node_id": self.node_id,
                        "timestamp": time.time(),
                        "vector_clock": self.vector_clock.copy(),
                        "sequence_number": self.sequence_number - 1,
                        "type": "patch",
                        "patch": patch,
                        "applied_by": "apply_patch",
                    }

                    with self.locks["update_log"]:
                        self.update_log.append(update_entry)

            # Return result
            result.update(
                {
                    "result": result_state,
                    "applied_operations": len(patch),
                    "from_version": from_version,
                    "to_version": to_version,
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to apply patch: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error applying patch: {e}")
            return result

    def detect_conflicts(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect conflicts in updates.

        Args:
            updates: List of update operations to check

        Returns:
            Dictionary with conflict information
        """
        result = {
            "success": True,
            "operation": "detect_conflicts",
            "timestamp": time.time(),
            "has_conflict": False,
            "conflicts": [],
        }

        try:
            # Group updates by path
            updates_by_path = {}
            for update in updates:
                path = update["path"]
                if path not in updates_by_path:
                    updates_by_path[path] = []
                updates_by_path[path].append(update)

            # Check for multiple updates to the same path
            for path, path_updates in updates_by_path.items():
                if len(path_updates) > 1:
                    # Check if operations are different
                    ops = set(u["op"] for u in path_updates)
                    if len(ops) > 1 or "remove" in ops:
                        # We have a conflict
                        result["has_conflict"] = True
                        result["conflicts"].append(
                            {"path": path, "updates": path_updates, "concurrent": True}
                        )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to detect conflicts: {str(e)}",
                    "error_type": type(e).__name__,
                    "has_conflict": False,
                }
            )
            logger.error(f"Error detecting conflicts: {e}")
            return result

    def resolve_conflict_lww(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a conflict using last-write-wins strategy.

        Args:
            conflict: Conflict information

        Returns:
            Dictionary with resolution information
        """
        result = {
            "success": True,
            "operation": "resolve_conflict_lww",
            "timestamp": time.time(),
            "resolved": False,
        }

        try:
            # Get all updates in the conflict
            updates = conflict["updates"]
            if not updates:
                result.update({"error": "No updates in conflict", "resolved": False})
                return result

            # Find the update with the latest timestamp
            winner = max(updates, key=lambda u: u.get("timestamp", 0))

            # Return the winner
            result.update({"resolved": True, "winner": winner, "strategy": "last_write_wins"})

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to resolve conflict: {str(e)}",
                    "error_type": type(e).__name__,
                    "resolved": False,
                }
            )
            logger.error(f"Error resolving conflict: {e}")
            return result

    def resolve_conflict_custom(
        self, conflict: Dict[str, Any], merge_func: Callable[[List[Dict[str, Any]]], Any]
    ) -> Dict[str, Any]:
        """Resolve a conflict using a custom merge function.

        Args:
            conflict: Conflict information
            merge_func: Function to merge conflicting updates

        Returns:
            Dictionary with resolution information
        """
        result = {
            "success": True,
            "operation": "resolve_conflict_custom",
            "timestamp": time.time(),
            "resolved": False,
        }

        try:
            # Get all updates in the conflict
            updates = conflict["updates"]
            if not updates:
                result.update({"error": "No updates in conflict", "resolved": False})
                return result

            # Use merge function to resolve
            merged_value = merge_func(updates)

            # Find the latest timestamp among updates
            latest_timestamp = max(u.get("timestamp", 0) for u in updates)

            # Combine vector clocks from all updates
            combined_vector_clock = {}
            for update in updates:
                if "vector_clock" in update:
                    combined_vector_clock = VectorClock.merge(
                        combined_vector_clock, update["vector_clock"]
                    )

            # Create a new merged update
            merged_update = {
                "path": conflict["path"],
                "value": merged_value,
                "timestamp": latest_timestamp,
                "node_id": "merged",
                "vector_clock": combined_vector_clock,
                "op": "replace",
            }

            # Return the merged result
            result.update(
                {"resolved": True, "merged_value": merged_update, "strategy": "custom_merge"}
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to resolve conflict with custom function: {str(e)}",
                    "error_type": type(e).__name__,
                    "resolved": False,
                }
            )
            logger.error(f"Error resolving conflict with custom function: {e}")
            return result


class ClusterStateSync:
    """Manages distributed state synchronization across a cluster of nodes."""

    def __init__(self, ipfs_kit_instance):
        """Initialize the state synchronization manager.

        Args:
            ipfs_kit_instance: Reference to the parent ipfs_kit instance
        """
        self.kit = ipfs_kit_instance

        # Get node ID from parent instance
        self.node_id = (
            getattr(self.kit, "peer_id", None)
            or getattr(self.kit, "node_id", None)
            or str(uuid.uuid4())
        )

        # Create CRDT instance
        self.state_crdt = StateCRDT(self.node_id, consensus_algorithm="lww")

        # Configuration
        self.config = {
            "sync_interval": 30,  # Sync every 30 seconds
            "partial_updates": True,  # Use partial updates when possible
            "gossip_topic": None,  # Will be set during setup
            "subscription_id": None,  # Will be set during setup
            "auto_sync": True,  # Enable automatic sync
        }

        # Update config from parent instance metadata
        if hasattr(self.kit, "metadata") and self.kit.metadata:
            if "sync" in self.kit.metadata:
                self.config.update(self.kit.metadata["sync"])

        # Initialize state tracking
        self.initialized = False
        self.sync_thread = None
        self.stop_sync = threading.Event()

        # Initialize gossip state
        self.gossip_setup_complete = False

    def initialize_distributed_state(self, initial_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Initialize the distributed state with initial data.

        Args:
            initial_data: Initial state data

        Returns:
            Result of the initialization
        """
        result = {
            "success": True,
            "operation": "initialize_distributed_state",
            "timestamp": time.time(),
        }

        try:
            # Initialize CRDT
            crdt_result = self.state_crdt.initialize(initial_data)
            if not crdt_result["success"]:
                result.update(
                    {"success": False, "error": "Failed to initialize CRDT", "details": crdt_result}
                )
                return result

            # Set up gossip protocol for state propagation
            if not self.gossip_setup_complete:
                gossip_result = self.setup_gossip_protocol()
                if not gossip_result["success"]:
                    logger.warning(
                        f"Failed to set up gossip protocol: {gossip_result.get('error')}"
                    )
                    # Continue anyway, we can set up gossip later

            # Start automatic sync if enabled
            if self.config["auto_sync"] and not self.sync_thread:
                self.start_automatic_sync()

            # Mark as initialized
            self.initialized = True

            # Return initialization info
            result.update(
                {
                    "state_id": crdt_result["state_id"],
                    "initial_data": crdt_result["initial_data"],
                    "vector_clock": crdt_result["vector_clock"],
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to initialize distributed state: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error initializing distributed state: {e}")
            return result

    def setup_gossip_protocol(self) -> Dict[str, Any]:
        """Set up gossip protocol for state propagation.

        Returns:
            Result of the setup
        """
        result = {"success": True, "operation": "setup_gossip_protocol", "timestamp": time.time()}

        try:
            # Determine gossip topic
            cluster_name = getattr(self.kit, "cluster_name", "ipfs-cluster")
            if hasattr(self.kit, "metadata") and self.kit.metadata:
                if "cluster_name" in self.kit.metadata:
                    cluster_name = self.kit.metadata["cluster_name"]

            gossip_topic = f"{cluster_name}/state"
            self.config["gossip_topic"] = gossip_topic

            # Subscribe to the gossip topic
            if hasattr(self.kit, "ipfs") and hasattr(self.kit.ipfs, "pubsub_subscribe"):
                subscription_result = self.kit.ipfs.pubsub_subscribe(
                    topic=gossip_topic, handler=self.handle_gossip_message
                )

                if not subscription_result.get("success", False):
                    result.update(
                        {
                            "success": False,
                            "error": f"Failed to subscribe to gossip topic: {subscription_result.get('error')}",
                            "details": subscription_result,
                        }
                    )
                    return result

                self.config["subscription_id"] = subscription_result.get("subscription_id")
            else:
                # Fallback if IPFS pubsub not available
                logger.warning("IPFS pubsub not available, gossip sync will be limited")
                self.config["subscription_id"] = str(uuid.uuid4())

            # Mark gossip as set up
            self.gossip_setup_complete = True

            # Return gossip info
            result.update(
                {"gossip_topic": gossip_topic, "subscription_id": self.config["subscription_id"]}
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to setup gossip protocol: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error setting up gossip protocol: {e}")
            return result

    def start_automatic_sync(self) -> Dict[str, Any]:
        """Start automatic state synchronization.

        Returns:
            Result of starting the sync
        """
        result = {"success": True, "operation": "start_automatic_sync", "timestamp": time.time()}

        try:
            # Check if already running
            if self.sync_thread and self.sync_thread.is_alive():
                result.update(
                    {
                        "message": "Automatic sync already running",
                        "thread_id": self.sync_thread.ident,
                    }
                )
                return result

            # Reset stop event
            self.stop_sync.clear()

            # Start sync thread
            self.sync_thread = threading.Thread(target=self._automatic_sync_worker, daemon=True)
            self.sync_thread.start()

            # Return thread info
            result.update(
                {"thread_id": self.sync_thread.ident, "sync_interval": self.config["sync_interval"]}
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to start automatic sync: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error starting automatic sync: {e}")
            return result

    def stop_automatic_sync(self) -> Dict[str, Any]:
        """Stop automatic state synchronization.

        Returns:
            Result of stopping the sync
        """
        result = {"success": True, "operation": "stop_automatic_sync", "timestamp": time.time()}

        try:
            # Check if running
            if not self.sync_thread or not self.sync_thread.is_alive():
                result.update({"message": "Automatic sync not running"})
                return result

            # Signal stop
            self.stop_sync.set()

            # Wait for thread to stop (with timeout)
            self.sync_thread.join(timeout=5.0)

            # Check if actually stopped
            if self.sync_thread.is_alive():
                result.update(
                    {
                        "success": False,
                        "error": "Failed to stop sync thread within timeout",
                        "thread_id": self.sync_thread.ident,
                    }
                )
                return result

            # Reset thread reference
            self.sync_thread = None

            # Return success
            result.update({"message": "Automatic sync stopped"})

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to stop automatic sync: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error stopping automatic sync: {e}")
            return result

    def _automatic_sync_worker(self) -> None:
        """Worker thread for automatic state synchronization."""
        logger.info(
            f"Starting automatic sync worker with interval {self.config['sync_interval']} seconds"
        )

        while not self.stop_sync.is_set():
            try:
                # Announce our state to peers
                self._announce_state_to_peers()

                # Sleep for the sync interval
                self.stop_sync.wait(timeout=self.config["sync_interval"])
            except Exception as e:
                logger.error(f"Error in automatic sync worker: {e}")
                # Sleep to avoid tight loop on repeated errors
                time.sleep(5)

    def _announce_state_to_peers(self) -> Dict[str, Any]:
        """Announce local state to peers via gossip.

        Returns:
            Result of the announcement
        """
        result = {"success": True, "operation": "announce_state", "timestamp": time.time()}

        try:
            # Skip if not set up
            if not self.initialized or not self.gossip_setup_complete:
                result.update(
                    {"success": False, "message": "State sync not initialized or gossip not set up"}
                )
                return result

            # Create update message
            update_data = {
                "sequence": self.state_crdt.sequence_number - 1,
                "node_id": self.node_id,
                "timestamp": time.time(),
                "vector_clock": self.state_crdt.vector_clock,
                "has_updates": True,
                "action": "announce",
            }

            # Publish to gossip topic
            publish_result = self.publish_state_update(update_data)
            if not publish_result["success"]:
                result.update(
                    {
                        "success": False,
                        "error": f"Failed to publish state update: {publish_result.get('error')}",
                        "details": publish_result,
                    }
                )
                return result

            # Return publish info
            result.update(
                {
                    "announced_sequence": update_data["sequence"],
                    "recipients": publish_result.get("recipients", 0),
                    "update_id": publish_result.get("update_id"),
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to announce state: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error announcing state: {e}")
            return result

    def get_state_update_for_sync(self, node_id: str, last_sequence: int = None) -> Dict[str, Any]:
        """Get state updates for synchronizing with another node.

        Args:
            node_id: ID of the node requesting updates
            last_sequence: Last sequence number the node has

        Returns:
            Dictionary with update information
        """
        result = {
            "success": True,
            "operation": "get_state_update_for_sync",
            "timestamp": time.time(),
        }

        try:
            # Skip if not initialized
            if not self.initialized:
                result.update(
                    {
                        "success": False,
                        "error": "State sync not initialized",
                        "message": "Initialize state sync before requesting updates",
                    }
                )
                return result

            # Get updates from CRDT
            crdt_result = self.state_crdt.get_state_update(node_id, last_sequence)
            if not crdt_result["success"]:
                result.update(
                    {
                        "success": False,
                        "error": "Failed to get state update from CRDT",
                        "details": crdt_result,
                    }
                )
                return result

            # Return updates
            result.update(
                {
                    "sequence_number": crdt_result["sequence_number"],
                    "updates": crdt_result["updates"],
                    "update_type": crdt_result["update_type"],
                    "vector_clock": crdt_result["vector_clock"],
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to get state update for sync: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error getting state update for sync: {e}")
            return result

    def apply_state_updates(
        self, updates: List[Dict[str, Any]], vector_clock: Dict[str, int], sequence_number: int
    ) -> Dict[str, Any]:
        """Apply state updates from another node.

        Args:
            updates: List of updates to apply
            vector_clock: Vector clock from the sending node
            sequence_number: Sequence number of the update

        Returns:
            Result of applying the updates
        """
        result = {"success": True, "operation": "apply_state_updates", "timestamp": time.time()}

        try:
            # Skip if not initialized
            if not self.initialized:
                result.update(
                    {
                        "success": False,
                        "error": "State sync not initialized",
                        "message": "Initialize state sync before applying updates",
                    }
                )
                return result

            # Apply updates to CRDT
            crdt_result = self.state_crdt.apply_updates(updates, vector_clock, sequence_number)
            if not crdt_result["success"]:
                result.update(
                    {
                        "success": False,
                        "error": "Failed to apply updates to CRDT",
                        "details": crdt_result,
                    }
                )
                return result

            # Return update results
            result.update(
                {
                    "applied_count": crdt_result["applied_count"],
                    "new_sequence_number": crdt_result["new_sequence_number"],
                    "new_vector_clock": crdt_result["new_vector_clock"],
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to apply state updates: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error applying state updates: {e}")
            return result

    def publish_state_update(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish a state update to the gossip topic.

        Args:
            update_data: Update data to publish

        Returns:
            Result of the publication
        """
        result = {"success": True, "operation": "publish_state_update", "timestamp": time.time()}

        try:
            # Skip if gossip not set up
            if not self.gossip_setup_complete:
                result.update(
                    {
                        "success": False,
                        "error": "Gossip protocol not set up",
                        "message": "Set up gossip protocol before publishing updates",
                    }
                )
                return result

            # Generate update ID
            update_id = str(uuid.uuid4())
            update_data["update_id"] = update_id

            # Serialize update data
            message = json.dumps(update_data)

            # Publish to gossip topic
            if hasattr(self.kit, "ipfs") and hasattr(self.kit.ipfs, "pubsub_publish"):
                publish_result = self.kit.ipfs.pubsub_publish(
                    topic=self.config["gossip_topic"], message=message
                )

                if not publish_result.get("success", False):
                    result.update(
                        {
                            "success": False,
                            "error": f"Failed to publish to gossip topic: {publish_result.get('error')}",
                            "details": publish_result,
                        }
                    )
                    return result

                # Return publish info
                result.update(
                    {
                        "topic": self.config["gossip_topic"],
                        "recipients": publish_result.get("recipients", 0),
                        "update_id": update_id,
                        "update_size": len(message),
                    }
                )
            else:
                # Fallback if pubsub not available
                logger.warning("IPFS pubsub not available, update not published")
                result.update(
                    {
                        "topic": self.config["gossip_topic"],
                        "recipients": 0,
                        "update_id": update_id,
                        "update_size": len(message),
                        "message": "IPFS pubsub not available, update not published",
                    }
                )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to publish state update: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error publishing state update: {e}")
            return result

    def handle_gossip_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a gossip message with a state update.

        Args:
            message: Gossip message to handle

        Returns:
            Result of handling the message
        """
        result = {"success": True, "operation": "handle_gossip_message", "timestamp": time.time()}

        try:
            # Skip if not initialized
            if not self.initialized:
                result.update(
                    {
                        "success": False,
                        "error": "State sync not initialized",
                        "message": "Initialize state sync before handling gossip messages",
                    }
                )
                return result

            # Extract message data
            try:
                message_data = json.loads(message["data"])
            except (json.JSONDecodeError, KeyError) as e:
                result.update(
                    {
                        "success": False,
                        "error": f"Invalid gossip message: {str(e)}",
                        "action": "ignored",
                        "reason": "invalid_message",
                    }
                )
                return result

            # Skip messages from self
            if message_data.get("node_id") == self.node_id:
                result.update({"action": "ignored", "reason": "self_message"})
                return result

            # Check message type
            if message_data.get("action") == "announce":
                # Handle state announcement
                return self._handle_state_announcement(message_data)
            elif "updates" in message_data:
                # Handle update message
                return self._handle_update_message(message_data)
            else:
                # Unknown message type
                result.update({"action": "ignored", "reason": "unknown_message_type"})
                return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to handle gossip message: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error handling gossip message: {e}")
            return result

    def _handle_state_announcement(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a state announcement from another node.

        Args:
            announcement: State announcement data

        Returns:
            Result of handling the announcement
        """
        result = {
            "success": True,
            "operation": "handle_state_announcement",
            "timestamp": time.time(),
        }

        try:
            # Extract announcement data
            peer_sequence = announcement.get("sequence")
            peer_id = announcement.get("node_id")

            # Compare with our sequence
            our_sequence = self.state_crdt.sequence_number - 1

            # If peer is ahead, request updates
            if peer_sequence > our_sequence:
                # Request updates directly if possible
                if hasattr(self.kit, "request_state_updates_from_peer"):
                    request_result = self.kit.request_state_updates_from_peer(
                        peer_id=peer_id, our_sequence=our_sequence
                    )

                    result.update(
                        {
                            "action": "requested_updates",
                            "peer_sequence": peer_sequence,
                            "our_sequence": our_sequence,
                            "peer_id": peer_id,
                            "request_result": request_result,
                        }
                    )
                else:
                    # Otherwise, announce our state to trigger updates
                    announce_result = self._announce_state_to_peers()

                    result.update(
                        {
                            "action": "announced_our_state",
                            "peer_sequence": peer_sequence,
                            "our_sequence": our_sequence,
                            "peer_id": peer_id,
                            "announce_result": announce_result,
                        }
                    )
            else:
                # We're up to date or ahead
                result.update(
                    {
                        "action": "ignored",
                        "reason": "already_up_to_date",
                        "peer_sequence": peer_sequence,
                        "our_sequence": our_sequence,
                    }
                )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to handle state announcement: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error handling state announcement: {e}")
            return result

    def _handle_update_message(self, update_message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a state update message from another node.

        Args:
            update_message: State update data

        Returns:
            Result of handling the update
        """
        result = {"success": True, "operation": "handle_update_message", "timestamp": time.time()}

        try:
            # Extract update data
            updates = update_message.get("updates", [])
            sequence = update_message.get("sequence")
            vector_clock = update_message.get("vector_clock", {})

            # Check if we already have this update
            our_sequence = self.state_crdt.sequence_number - 1
            if sequence <= our_sequence:
                result.update(
                    {
                        "action": "ignored",
                        "reason": "already_applied",
                        "update_sequence": sequence,
                        "our_sequence": our_sequence,
                    }
                )
                return result

            # Apply the updates
            apply_result = self.apply_state_updates(
                updates=updates, vector_clock=vector_clock, sequence_number=sequence
            )

            if not apply_result["success"]:
                result.update(
                    {"success": False, "error": "Failed to apply updates", "details": apply_result}
                )
                return result

            # Return update info
            result.update(
                {
                    "action": "applied",
                    "sequence": sequence,
                    "update_count": len(updates),
                    "new_sequence": apply_result["new_sequence_number"],
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to handle update message: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error handling update message: {e}")
            return result

    def create_state_patch(
        self, old_state: Dict[str, Any], new_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a patch between old and new states.

        Args:
            old_state: Original state
            new_state: New state

        Returns:
            Dictionary with patch information
        """
        result = {"success": True, "operation": "create_state_patch", "timestamp": time.time()}

        try:
            # Skip if not initialized
            if not self.initialized:
                result.update(
                    {
                        "success": False,
                        "error": "State sync not initialized",
                        "message": "Initialize state sync before creating patches",
                    }
                )
                return result

            # Create patch using CRDT
            crdt_result = self.state_crdt.create_patch(old_state, new_state)
            if not crdt_result["success"]:
                result.update(
                    {"success": False, "error": "Failed to create patch", "details": crdt_result}
                )
                return result

            # Return patch info
            result.update(
                {
                    "patch": crdt_result["patch"],
                    "from_version": crdt_result["from_version"],
                    "to_version": crdt_result["to_version"],
                    "vector_clock": crdt_result["vector_clock"],
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to create state patch: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error creating state patch: {e}")
            return result

    def apply_state_patch(
        self,
        current_state: Dict[str, Any],
        patch: List[Dict[str, Any]],
        from_version: int = None,
        to_version: int = None,
    ) -> Dict[str, Any]:
        """Apply a patch to a state.

        Args:
            current_state: State to apply patch to
            patch: Patch operations to apply
            from_version: Source version number
            to_version: Target version number

        Returns:
            Dictionary with result of applying the patch
        """
        result = {"success": True, "operation": "apply_state_patch", "timestamp": time.time()}

        try:
            # Skip if not initialized
            if not self.initialized:
                result.update(
                    {
                        "success": False,
                        "error": "State sync not initialized",
                        "message": "Initialize state sync before applying patches",
                    }
                )
                return result

            # Apply patch using CRDT
            crdt_result = self.state_crdt.apply_patch(
                current_state, patch, from_version, to_version
            )

            if not crdt_result["success"]:
                result.update(
                    {"success": False, "error": "Failed to apply patch", "details": crdt_result}
                )
                return result

            # Return result
            result.update(
                {
                    "result": crdt_result["result"],
                    "applied_operations": crdt_result["applied_operations"],
                    "from_version": crdt_result["from_version"],
                    "to_version": crdt_result["to_version"],
                }
            )

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to apply state patch: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error applying state patch: {e}")
            return result

    def detect_conflicts(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect conflicts in updates.

        Args:
            updates: List of update operations to check

        Returns:
            Dictionary with conflict information
        """
        # Forward to CRDT implementation
        return self.state_crdt.detect_conflicts(updates)

    def resolve_conflict_lww(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a conflict using last-write-wins strategy.

        Args:
            conflict: Conflict information

        Returns:
            Dictionary with resolution information
        """
        # Forward to CRDT implementation
        return self.state_crdt.resolve_conflict_lww(conflict)

    def resolve_conflict_custom(
        self, conflict: Dict[str, Any], merge_func: Callable[[List[Dict[str, Any]]], Any]
    ) -> Dict[str, Any]:
        """Resolve a conflict using a custom merge function.

        Args:
            conflict: Conflict information
            merge_func: Function to merge conflicting updates

        Returns:
            Dictionary with resolution information
        """
        # Forward to CRDT implementation
        return self.state_crdt.resolve_conflict_custom(conflict, merge_func)

    def compare_vector_clocks(
        self, clock1: Dict[str, int], clock2: Dict[str, int]
    ) -> Dict[str, Any]:
        """Compare two vector clocks to determine their causality relationship.

        Args:
            clock1: First vector clock
            clock2: Second vector clock

        Returns:
            Dictionary with relationship information
        """
        # Forward to VectorClock implementation
        return VectorClock.compare(clock1, clock2)

    def increment_vector_clock(self, vector_clock: Dict[str, int], node_id: str) -> Dict[str, int]:
        """Increment the counter for a node in a vector clock.

        Args:
            vector_clock: Existing vector clock
            node_id: ID of the node to increment counter for

        Returns:
            Updated vector clock
        """
        # Forward to VectorClock implementation
        return VectorClock.increment(vector_clock, node_id)

    def merge_vector_clocks(self, clock1: Dict[str, int], clock2: Dict[str, int]) -> Dict[str, int]:
        """Merge two vector clocks by taking the maximum of each entry.

        Args:
            clock1: First vector clock
            clock2: Second vector clock

        Returns:
            Merged vector clock
        """
        # Forward to VectorClock implementation
        return VectorClock.merge(clock1, clock2)

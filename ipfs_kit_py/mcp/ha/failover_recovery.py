"""
High Availability Failover Recovery for MCP Server.

This module provides failover recovery capabilities for the MCP high availability
cluster, implementing robust recovery procedures after a primary node failure.
"""

import asyncio
import logging
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple

# Configure logging
logger = logging.getLogger(__name__)


class RecoveryState(str, Enum):
    """States in the failover recovery process."""
    
    IDLE = "idle"                      # No recovery in progress
    PREPARING = "preparing"            # Preparing for recovery
    ELECTING = "electing"              # Electing new primary
    TRANSITIONING = "transitioning"    # Transitioning to new primary
    RECONCILING = "reconciling"        # Reconciling data after failover
    VERIFYING = "verifying"            # Verifying recovery success
    COMPLETED = "completed"            # Recovery completed successfully
    FAILED = "failed"                  # Recovery failed
    REVERTING = "reverting"            # Reverting to original state


class RecoveryStrategy(str, Enum):
    """Strategies for handling failover recovery."""
    
    ELECT_NEW_PRIMARY = "elect_new_primary"    # Elect a new primary node
    PROMOTE_SECONDARY = "promote_secondary"    # Promote a specific secondary
    WAIT_FOR_PRIMARY = "wait_for_primary"      # Wait for primary to recover
    MANUAL = "manual"                          # Wait for manual intervention


class FailoverRecovery:
    """
    Failover recovery manager for MCP high availability.
    
    This component handles the recovery process after a node failure has been
    detected, including electing a new primary, transitioning state, and
    ensuring data consistency after failover.
    """
    
    def __init__(
        self,
        node_id: str,
        strategy: RecoveryStrategy = RecoveryStrategy.ELECT_NEW_PRIMARY,
        election_timeout_seconds: float = 15.0,
        reconciliation_timeout_seconds: float = 60.0,
        min_nodes_for_election: int = 2,
        auto_recover_primary: bool = True
    ):
        """
        Initialize the failover recovery manager.
        
        Args:
            node_id: ID of this node
            strategy: Recovery strategy to use
            election_timeout_seconds: Seconds to wait for election to complete
            reconciliation_timeout_seconds: Seconds to wait for data reconciliation
            min_nodes_for_election: Minimum number of nodes needed for election
            auto_recover_primary: Whether to automatically recover primary when it returns
        """
        self.node_id = node_id
        self.strategy = strategy
        self.election_timeout = election_timeout_seconds
        self.reconciliation_timeout = reconciliation_timeout_seconds
        self.min_nodes_for_election = min_nodes_for_election
        self.auto_recover_primary = auto_recover_primary
        
        # Internal state
        self.current_state = RecoveryState.IDLE
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.node_metrics: Dict[str, Dict[str, Any]] = {}
        self.primary_node_id: Optional[str] = None
        self.old_primary_node_id: Optional[str] = None
        self.recovery_id: Optional[str] = None
        self.recovery_start_time: float = 0
        self.preferred_secondary: Optional[str] = None
        self.recovery_details: Dict[str, Any] = {}
        self.last_recovery_time: float = 0
        
        # Recovery history
        self.recovery_history: List[Dict[str, Any]] = []
        
        # State lock for concurrency
        self._lock = asyncio.Lock()
        
        # Callbacks
        self._state_change_callbacks: List[Callable[[RecoveryState, RecoveryState], Awaitable[None]]] = []
        self._recovery_start_callbacks: List[Callable[[str, str], Awaitable[None]]] = []
        self._recovery_complete_callbacks: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        self._primary_change_callbacks: List[Callable[[str, str], Awaitable[None]]] = []
    
    async def update_nodes(self, nodes: Dict[str, Dict[str, Any]]):
        """
        Update known nodes in the cluster.
        
        Args:
            nodes: Dictionary of node_id -> node_info
        """
        async with self._lock:
            self.nodes = nodes
    
    async def update_node_metrics(self, node_id: str, metrics: Dict[str, Any]):
        """
        Update metrics for a node.
        
        Args:
            node_id: ID of the node
            metrics: Dictionary of metrics
        """
        async with self._lock:
            self.node_metrics[node_id] = metrics
    
    def set_primary(self, primary_node_id: str):
        """
        Set the primary node ID.
        
        Args:
            primary_node_id: ID of the primary node
        """
        old_primary = self.primary_node_id
        self.primary_node_id = primary_node_id
        
        if old_primary != primary_node_id:
            logger.info(f"Primary node changed from {old_primary} to {primary_node_id}")
            # Schedule primary change callbacks
            for callback in self._primary_change_callbacks:
                asyncio.create_task(callback(old_primary, primary_node_id))
    
    async def start_recovery(self, failed_node_id: str) -> bool:
        """
        Start the recovery process for a failed node.
        
        Args:
            failed_node_id: ID of the failed node
            
        Returns:
            True if recovery started, False otherwise
        """
        async with self._lock:
            # Check if recovery is already in progress
            if self.current_state != RecoveryState.IDLE:
                logger.warning(f"Cannot start recovery: already in {self.current_state} state")
                return False
            
            # Check if failed node is the primary
            if failed_node_id != self.primary_node_id:
                logger.warning(f"Node {failed_node_id} is not the primary, no failover needed")
                return False
            
            # Generate recovery ID
            self.recovery_id = str(uuid.uuid4())
            self.recovery_start_time = time.time()
            self.old_primary_node_id = failed_node_id
            
            # Initialize recovery details
            self.recovery_details = {
                "recovery_id": self.recovery_id,
                "start_time": self.recovery_start_time,
                "failed_node": failed_node_id,
                "strategy": self.strategy,
                "initiated_by": self.node_id
            }
            
            # Update state
            await self._update_state(RecoveryState.PREPARING)
            
            # Notify start callbacks
            for callback in self._recovery_start_callbacks:
                asyncio.create_task(callback(self.recovery_id, failed_node_id))
            
            # Start recovery process based on strategy
            asyncio.create_task(self._run_recovery_process())
            
            logger.info(f"Started recovery process {self.recovery_id} for failed primary {failed_node_id}")
            return True
    
    async def trigger_manual_recovery(self, new_primary_id: str) -> bool:
        """
        Trigger a manual recovery process with specified new primary.
        
        Args:
            new_primary_id: ID of node to make the new primary
            
        Returns:
            True if recovery started, False otherwise
        """
        async with self._lock:
            # Can only start in IDLE state
            if self.current_state != RecoveryState.IDLE:
                logger.warning(f"Cannot start manual recovery: already in {self.current_state} state")
                return False
            
            # Check if specified node exists
            if new_primary_id not in self.nodes:
                logger.error(f"Cannot use {new_primary_id} as new primary: node not found")
                return False
            
            # Set preferred secondary for election
            self.preferred_secondary = new_primary_id
            
            # Force strategy to manual
            original_strategy = self.strategy
            self.strategy = RecoveryStrategy.MANUAL
            
            # Start recovery process
            success = await self.start_recovery(self.primary_node_id)
            
            # Restore original strategy for future recoveries
            self.strategy = original_strategy
            
            return success
    
    def register_state_change_callback(
        self, callback: Callable[[RecoveryState, RecoveryState], Awaitable[None]]
    ):
        """
        Register a callback to be called when recovery state changes.
        
        Args:
            callback: Async callback function(old_state, new_state)
        """
        self._state_change_callbacks.append(callback)
    
    def register_recovery_start_callback(
        self, callback: Callable[[str, str], Awaitable[None]]
    ):
        """
        Register a callback to be called when recovery starts.
        
        Args:
            callback: Async callback function(recovery_id, failed_node_id)
        """
        self._recovery_start_callbacks.append(callback)
    
    def register_recovery_complete_callback(
        self, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """
        Register a callback to be called when recovery completes.
        
        Args:
            callback: Async callback function(recovery_result)
        """
        self._recovery_complete_callbacks.append(callback)
    
    def register_primary_change_callback(
        self, callback: Callable[[str, str], Awaitable[None]]
    ):
        """
        Register a callback to be called when primary changes.
        
        Args:
            callback: Async callback function(old_primary, new_primary)
        """
        self._primary_change_callbacks.append(callback)
    
    async def node_recovered(self, node_id: str):
        """
        Handle recovery of a previously failed node.
        
        Args:
            node_id: ID of recovered node
        """
        async with self._lock:
            # Check if this is the old primary node
            if (
                self.auto_recover_primary and
                node_id == self.old_primary_node_id and
                self.current_state == RecoveryState.IDLE and
                node_id != self.primary_node_id  # Don't restore if already primary
            ):
                logger.info(f"Old primary node {node_id} has recovered, considering restoration")
                
                # Give the node some time to stabilize before making a decision
                asyncio.create_task(self._evaluate_primary_restoration(node_id))
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the recovery manager.
        
        Returns:
            Dictionary with current status
        """
        return {
            "state": self.current_state,
            "recovery_id": self.recovery_id,
            "primary_node_id": self.primary_node_id,
            "old_primary_node_id": self.old_primary_node_id,
            "strategy": self.strategy,
            "auto_recover_primary": self.auto_recover_primary,
            "recovery_details": self.recovery_details,
            "last_recovery_time": self.last_recovery_time
        }
    
    def get_recovery_history(self) -> List[Dict[str, Any]]:
        """
        Get recovery history.
        
        Returns:
            List of recovery events
        """
        return self.recovery_history
    
    async def _update_state(self, new_state: RecoveryState):
        """
        Update the current recovery state and notify callbacks.
        
        Args:
            new_state: New state to transition to
        """
        if self.current_state == new_state:
            return
        
        old_state = self.current_state
        self.current_state = new_state
        logger.info(f"Recovery state changed: {old_state} -> {new_state}")
        
        # Update recovery details
        self.recovery_details[f"{new_state}_time"] = time.time()
        
        # Add to history
        self._add_to_history(
            f"State changed to {new_state}",
            old_state=old_state,
            new_state=new_state
        )
        
        # Notify callbacks
        for callback in self._state_change_callbacks:
            asyncio.create_task(callback(old_state, new_state))
    
    def _add_to_history(self, event: str, **details):
        """
        Add entry to recovery history.
        
        Args:
            event: Description of the event
            **details: Additional details
        """
        entry = {
            "recovery_id": self.recovery_id,
            "time": time.time(),
            "state": self.current_state,
            "event": event,
            "details": details
        }
        self.recovery_history.append(entry)
        
        # Keep history to a reasonable size (last 100 entries)
        if len(self.recovery_history) > 100:
            self.recovery_history = self.recovery_history[-100:]
    
    async def _run_recovery_process(self):
        """Run the complete recovery process."""
        start_time = time.time()
        
        try:
            # 1. Preparing phase: Validate conditions for recovery
            await self._update_state(RecoveryState.PREPARING)
            can_recover = await self._prepare_recovery()
            
            if not can_recover:
                logger.error("Cannot proceed with recovery, conditions not met")
                self._add_to_history("Recovery preparation failed")
                await self._update_state(RecoveryState.FAILED)
                
                # Report failure
                self._report_recovery_completion(False, "preparation_failed")
                return
            
            # 2. Electing phase: Elect new primary
            await self._update_state(RecoveryState.ELECTING)
            new_primary = await self._elect_new_primary()
            
            if not new_primary:
                logger.error("Failed to elect new primary")
                self._add_to_history("Election failed")
                await self._update_state(RecoveryState.FAILED)
                
                # Report failure
                self._report_recovery_completion(False, "election_failed")
                return
            
            # 3. Transitioning phase: Transition to new primary
            await self._update_state(RecoveryState.TRANSITIONING)
            transition_success = await self._transition_to_new_primary(new_primary)
            
            if not transition_success:
                logger.error(f"Failed to transition to new primary {new_primary}")
                self._add_to_history("Transition failed", new_primary=new_primary)
                await self._update_state(RecoveryState.FAILED)
                
                # Report failure
                self._report_recovery_completion(False, "transition_failed")
                return
            
            # 4. Reconciling phase: Ensure data consistency
            await self._update_state(RecoveryState.RECONCILING)
            reconciliation_result = await self._reconcile_data(new_primary)
            
            # 5. Verifying phase: Verify recovery success
            await self._update_state(RecoveryState.VERIFYING)
            verification_result = await self._verify_recovery(new_primary)
            
            if not verification_result.get("success", False):
                logger.error(f"Recovery verification failed: {verification_result.get('reason')}")
                self._add_to_history("Verification failed", result=verification_result)
                
                # Check if we should revert
                if verification_result.get("recoverable", False):
                    logger.warning("Attempting to revert to previous state")
                    await self._update_state(RecoveryState.REVERTING)
                    revert_success = await self._revert_recovery()
                    
                    if revert_success:
                        logger.info("Successfully reverted to previous state")
                        self._add_to_history("Reverted successfully")
                    else:
                        logger.error("Failed to revert to previous state")
                        self._add_to_history("Revert failed")
                
                await self._update_state(RecoveryState.FAILED)
                
                # Report failure
                self._report_recovery_completion(False, "verification_failed")
                return
            
            # 6. Completed phase: Finalize recovery
            await self._update_state(RecoveryState.COMPLETED)
            
            # Calculate duration
            duration_seconds = time.time() - start_time
            
            # Update details
            self.recovery_details.update({
                "duration_seconds": duration_seconds,
                "new_primary": new_primary,
                "reconciliation_result": reconciliation_result,
                "verification_result": verification_result,
                "success": True
            })
            
            logger.info(
                f"Recovery completed successfully in {duration_seconds:.2f}s: "
                f"{self.old_primary_node_id} -> {new_primary}"
            )
            
            self._add_to_history(
                "Recovery completed successfully", 
                duration=duration_seconds,
                new_primary=new_primary
            )
            
            # Update last recovery time
            self.last_recovery_time = time.time()
            
            # Report success
            self._report_recovery_completion(True)
            
            # Return to idle state
            await self._update_state(RecoveryState.IDLE)
        
        except Exception as e:
            logger.exception(f"Error during recovery process: {e}")
            
            # Add to history
            self._add_to_history("Recovery failed with exception", error=str(e))
            
            # Update recovery details
            self.recovery_details.update({
                "error": str(e),
                "duration_seconds": time.time() - start_time,
                "success": False
            })
            
            # Update state
            await self._update_state(RecoveryState.FAILED)
            
            # Report failure
            self._report_recovery_completion(False, f"exception: {e}")
            
            # Return to idle state after a delay
            await asyncio.sleep(5)
            await self._update_state(RecoveryState.IDLE)
    
    def _report_recovery_completion(self, success: bool, failure_reason: str = None):
        """
        Report recovery completion to registered callbacks.
        
        Args:
            success: Whether recovery succeeded
            failure_reason: Reason for failure if not successful
        """
        result = dict(self.recovery_details)
        result.update({
            "success": success,
            "failure_reason": failure_reason,
            "completion_time": time.time()
        })
        
        # Call completion callbacks
        for callback in self._recovery_complete_callbacks:
            asyncio.create_task(callback(result))
    
    async def _prepare_recovery(self) -> bool:
        """
        Prepare for recovery by validating conditions.
        
        Returns:
            True if recovery can proceed, False otherwise
        """
        logger.info("Preparing for recovery process")
        
        # Check if there are enough active nodes
        active_nodes = 0
        for node_id, node in self.nodes.items():
            # Skip the failed primary
            if node_id == self.old_primary_node_id:
                continue
            
            # Count active nodes
            if node.get("status", "inactive") == "active":
                active_nodes += 1
        
        # Check if we meet minimum node requirement
        if active_nodes < self.min_nodes_for_election:
            logger.error(
                f"Not enough active nodes for recovery: "
                f"{active_nodes} < {self.min_nodes_for_election}"
            )
            self._add_to_history(
                "Preparation failed: not enough active nodes",
                active_nodes=active_nodes,
                required=self.min_nodes_for_election
            )
            return False
        
        # Strategy-specific preparation
        if self.strategy == RecoveryStrategy.WAIT_FOR_PRIMARY:
            # Check if we're still within wait timeout
            if not hasattr(self, "_wait_until"):
                # Set wait timeout (5 minutes by default)
                wait_timeout = getattr(self, "wait_for_primary_timeout", 300)
                self._wait_until = time.time() + wait_timeout
                
                logger.info(
                    f"Using WAIT_FOR_PRIMARY strategy, will wait until "
                    f"{time.ctime(self._wait_until)}"
                )
            
            # Check if wait has expired
            if time.time() > self._wait_until:
                logger.warning(
                    "Wait for primary expired, falling back to ELECT_NEW_PRIMARY"
                )
                self.strategy = RecoveryStrategy.ELECT_NEW_PRIMARY
            else:
                logger.error(
                    "WAIT_FOR_PRIMARY strategy is active but primary has not recovered"
                )
                self._add_to_history(
                    "Preparation failed: waiting for primary", 
                    wait_until=self._wait_until
                )
                return False
        
        logger.info("Recovery preparation successful")
        self._add_to_history("Preparation completed successfully")
        return True
    
    async def _elect_new_primary(self) -> Optional[str]:
        """
        Elect a new primary node.
        
        Returns:
            ID of new primary node, or None if election failed
        """
        logger.info("Starting election for new primary node")
        
        # Check for manual strategy first
        if self.strategy == RecoveryStrategy.MANUAL:
            if self.preferred_secondary:
                logger.info(f"Using manually specified node as primary: {self.preferred_secondary}")
                return self.preferred_secondary
            else:
                logger.error("Manual strategy but no preferred secondary specified")
                return None
        
        # Check for promote secondary strategy
        if self.strategy == RecoveryStrategy.PROMOTE_SECONDARY:
            if self.preferred_secondary:
                logger.info(f"Promoting preferred secondary to primary: {self.preferred_secondary}")
                return self.preferred_secondary
            else:
                logger.warning("No preferred secondary, falling back to election")
                # Fall through to election
        
        # Find healthy and eligible nodes
        eligible_nodes = {}
        
        for node_id, node in self.nodes.items():
            # Skip failed primary
            if node_id == self.old_primary_node_id:
                continue
            
            # Check if node is active
            if node.get("status", "inactive") != "active":
                continue
            
            # Check node health if metrics exist
            if node_id in self.node_metrics:
                metrics = self.node_metrics[node_id]
                
                # Skip unhealthy nodes
                if not self._is_node_healthy(node_id, metrics):
                    logger.info(f"Node {node_id} is not healthy enough for primary role")
                    continue
                
                # Calculate node score based on metrics
                score = self._calculate_node_score(node_id, metrics)
                eligible_nodes[node_id] = score
            else:
                # No metrics, use default score
                eligible_nodes[node_id] = 50.0
        
        # Check if we have any eligible nodes
        if not eligible_nodes:
            logger.error("No eligible nodes found for election")
            return None
        
        # Select node with highest score
        sorted_nodes = sorted(eligible_nodes.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_nodes[0][0]
        winner_score = sorted_nodes[0][1]
        
        logger.info(
            f"Elected node {winner} as new primary with score {winner_score:.1f} "
            f"(out of {len(eligible_nodes)} eligible nodes)"
        )
        
        self._add_to_history(
            "Elected new primary", 
            new_primary=winner,
            score=winner_score,
            eligible_count=len(eligible_nodes)
        )
        
        return winner
    
    def _is_node_healthy(self, node_id: str, metrics: Dict[str, Any]) -> bool:
        """
        Check if a node is healthy enough to become primary.
        
        Args:
            node_id: Node ID
            metrics: Node metrics
            
        Returns:
            True if node is healthy, False otherwise
        """
        # Check critical health metrics
        cpu_load = metrics.get("cpu_load", 0)
        memory_used = metrics.get("memory_used_percent", 0)
        error_rate = metrics.get("error_rate", 0)
        
        # Node must have reasonable resource availability
        return (
            cpu_load < 80 and
            memory_used < 80 and
            error_rate < 5
        )
    
    def _calculate_node_score(self, node_id: str, metrics: Dict[str, Any]) -> float:
        """
        Calculate score for node election.
        
        Args:
            node_id: Node ID
            metrics: Node metrics
            
        Returns:
            Node score (higher is better)
        """
        # Base score starts at 50
        score = 50.0
        
        # Resource availability increases score
        cpu_available = 100 - metrics.get("cpu_load", 0)
        memory_available = 100 - metrics.get("memory_used_percent", 0)
        score += (cpu_available * 0.3) + (memory_available * 0.2)
        
        # Performance metrics
        response_time = metrics.get("response_time_ms", 100)
        if response_time > 0:
            # Lower response time is better
            response_score = min(20, 2000 / response_time)
            score += response_score
        
        # Capacity metrics
        compute_capacity = metrics.get("compute_capacity", 1.0)
        network_capacity = metrics.get("network_capacity", 1.0)
        storage_capacity = metrics.get("storage_capacity", 1.0)
        
        # Higher capacity is better
        score += (compute_capacity * 5) + (network_capacity * 3) + (storage_capacity * 2)
        
        # Error metrics reduce score
        error_rate = metrics.get("error_rate", 0)
        recent_errors = metrics.get("recent_errors", 0)
        score -= (error_rate * 5) + (recent_errors * 2)
        
        # Bonus for secondary nodes (they're warmed up)
        if metrics.get("role") == "secondary":
            score += 10
        
        # Prefer current region
        if self.nodes.get(node_id, {}).get("region") == self.nodes.get(self.node_id, {}).get("region"):
            score += 15
        
        return max(0, score)
    
    async def _transition_to_new_primary(self, new_primary: str) -> bool:
        """
        Transition to new primary node.
        
        Args:
            new_primary: ID of new primary node
            
        Returns:
            True if transition successful, False otherwise
        """
        logger.info(f"Transitioning to new primary node: {new_primary}")
        
        # Update primary node
        old_primary = self.primary_node_id
        self.set_primary(new_primary)
        
        # In a real implementation, we would coordinate with other nodes
        # to ensure they all recognize the new primary
        
        self._add_to_history(
            "Transitioned to new primary", 
            old_primary=old_primary,
            new_primary=new_primary
        )
        
        return True
    
    async def _reconcile_data(self, new_primary: str) -> Dict[str, Any]:
        """
        Reconcile data after failover.
        
        Args:
            new_primary: ID of new primary node
            
        Returns:
            Dictionary with reconciliation results
        """
        logger.info(f"Reconciling data after transition to new primary {new_primary}")
        
        # In a real implementation, we would ensure data consistency across nodes
        # This might involve:
        # - Replicating missing data to the new primary
        # - Ensuring all nodes have consistent data
        # - Handling any conflicts that arose during the primary failure
        
        # For this example, we'll simulate successful reconciliation
        await asyncio.sleep(0.5)  # Simulate work
        
        reconciliation_result = {
            "success": True,
            "items_reconciled": 0,
            "conflicts_resolved": 0,
            "data_loss": False
        }
        
        self._add_to_history(
            "Completed data reconciliation", 
            result=reconciliation_result
        )
        
        return reconciliation_result
    
    async def _verify_recovery(self, new_primary: str) -> Dict[str, Any]:
        """
        Verify recovery success.
        
        Args:
            new_primary: ID of new primary node
            
        Returns:
            Dictionary with verification results
        """
        logger.info(f"Verifying recovery to new primary {new_primary}")
        
        # In a real implementation, we would verify that:
        # - The new primary is functioning correctly
        # - Data is consistent and accessible
        # - The cluster is stable
        
        # For this example, we'll simulate successful verification
        await asyncio.sleep(0.5)  # Simulate work
        
        verification_result = {
            "success": True,
            "primary_reachable": True,
            "data_accessible": True,
            "services_operational": True
        }
        
        self._add_to_history(
            "Completed recovery verification", 
            result=verification_result
        )
        
        return verification_result
    
    async def _revert_recovery(self) -> bool:
        """
        Revert a failed recovery to previous state.
        
        Returns:
            True if revert successful, False otherwise
        """
        logger.info("Attempting to revert recovery")
        
        # In a real implementation, we would restore the previous state
        # This might involve:
        # - Restoring the previous primary (if available)
        # - Rolling back any data changes made during recovery
        
        # For this example, we'll simulate successful revert
        await asyncio.sleep(0.5)  # Simulate work
        
        self._add_to_history("Reverted recovery")
        
        return True
    
    async def _evaluate_primary_restoration(self, node_id: str):
        """
        Evaluate whether to restore a recovered primary node.
        
        Args:
            node_id: ID of recovered node
        """
        logger.info(f"Evaluating restoration of recovered primary node {node_id}")
        
        # Wait for node to stabilize
        await asyncio.sleep(60)
        
        async with self._lock:
            # Check if circumstances still make sense for restoration
            if (
                self.current_state != RecoveryState.IDLE or
                node_id != self.old_primary_node_id or
                node_id == self.primary_node_id
            ):
                logger.info(f"Conditions changed, not restoring node {node_id} as primary")
                return
            
            # Check node health
            if node_id in self.node_metrics:
                metrics = self.node_metrics[node_id]
                if not self._is_node_healthy(node_id, metrics):
                    logger.info(f"Node {node_id} is not healthy enough to restore as primary")
                    return
                
                # Node appears healthy, trigger manual recovery to restore it
                logger.info(f"Restoring recovered node {node_id} as primary")
                await self.trigger_manual_recovery(node_id)
            else:
                logger.info(f"No metrics for node {node_id}, cannot evaluate for restoration")


async def setup_failover_recovery(
    node_id: str,
    strategy: RecoveryStrategy = RecoveryStrategy.ELECT_NEW_PRIMARY,
    config: Optional[Dict[str, Any]] = None
) -> FailoverRecovery:
    """
    Set up a failover recovery manager.
    
    Args:
        node_id: ID of this node
        strategy: Recovery strategy to use
        config: Additional configuration
        
    Returns:
        Initialized FailoverRecovery
    """
    # Create configuration dict from config
    kwargs = {}
    if config:
        for key, value in config.items():
            if key in (
                "election_timeout_seconds",
                "reconciliation_timeout_seconds",
                "min_nodes_for_election",
                "auto_recover_primary"
            ):
                kwargs[key] = value
    
    # Create recovery manager
    recovery = FailoverRecovery(
        node_id=node_id,
        strategy=strategy,
        **kwargs
    )
    
    return recovery
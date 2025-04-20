"""
High Availability Failover Detection for MCP Server.

This module provides failover detection capabilities for the MCP high availability
cluster, implementing smart failure detection using various strategies.
"""

import asyncio
import logging
import time
import math
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Callable, Awaitable

# Configure logging
logger = logging.getLogger(__name__)


class FailureDetectionStrategy(str, Enum):
    """Strategies for detecting node failures."""
    
    HEARTBEAT = "heartbeat"                 # Regular heartbeat monitoring
    GOSSIP = "gossip"                       # Gossip-based failure detection
    ADAPTIVE_TIMEOUT = "adaptive_timeout"   # Adaptive timeout based on network conditions
    CONSENSUS = "consensus"                 # Consensus-based failure detection
    MULTI_POINT = "multi_point"             # Detection from multiple observation points
    HYBRID = "hybrid"                       # Combination of multiple strategies


class FailoverDetector:
    """
    Enhanced failover detection for MCP high availability.
    
    This component implements advanced failure detection with support for multiple
    detection strategies to minimize false positives while quickly identifying
    actual failures.
    """
    
    def __init__(
        self,
        node_id: str,
        strategy: FailureDetectionStrategy = FailureDetectionStrategy.HYBRID,
        heartbeat_interval_seconds: float = 2.0,
        heartbeat_timeout_seconds: float = 10.0,
        adaptive_timeout_min_seconds: float = 5.0,
        adaptive_timeout_max_seconds: float = 30.0,
        consecutive_heartbeat_misses: int = 3,
        max_response_time_ms: float = 5000,
        consensus_threshold: float = 0.66,  # 66% of nodes must agree
        multi_point_threshold: int = 2      # Must be detected from at least 2 points
    ):
        """
        Initialize the failover detector.
        
        Args:
            node_id: ID of this node
            strategy: Detection strategy to use
            heartbeat_interval_seconds: Seconds between heartbeat checks
            heartbeat_timeout_seconds: Seconds to wait before marking a node as suspected
            adaptive_timeout_min_seconds: Minimum timeout for adaptive strategy
            adaptive_timeout_max_seconds: Maximum timeout for adaptive strategy
            consecutive_heartbeat_misses: Number of consecutive misses before suspecting a node
            max_response_time_ms: Maximum response time before suspecting a node
            consensus_threshold: Portion of nodes that must agree for consensus
            multi_point_threshold: Number of observation points required for multi-point
        """
        self.node_id = node_id
        self.strategy = strategy
        self.heartbeat_interval = heartbeat_interval_seconds
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self.adaptive_timeout_min = adaptive_timeout_min_seconds
        self.adaptive_timeout_max = adaptive_timeout_max_seconds
        self.consecutive_heartbeat_misses = consecutive_heartbeat_misses
        self.max_response_time_ms = max_response_time_ms
        self.consensus_threshold = consensus_threshold
        self.multi_point_threshold = multi_point_threshold
        
        # Internal state
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.suspected_nodes: Set[str] = set()
        self.confirmed_failed_nodes: Set[str] = set()
        
        # Last heartbeat tracking
        self.last_heartbeat: Dict[str, float] = {}
        self.missed_heartbeats: Dict[str, int] = {}
        
        # Response time tracking for adaptive timeout
        self.response_times: Dict[str, List[float]] = {}
        self.adaptive_timeouts: Dict[str, float] = {}
        
        # Network topology for multi-point detection
        self.observation_points: List[str] = []
        self.node_status_by_observer: Dict[str, Dict[str, bool]] = {}
        
        # For consensus detection
        self.node_votes: Dict[str, Dict[str, bool]] = {}
        
        # State locks for thread safety
        self._lock = asyncio.Lock()
        
        # Background tasks
        self._tasks: List[asyncio.Task] = []
        
        # Callbacks
        self._node_suspected_callbacks: List[Callable[[str], Awaitable[None]]] = []
        self._node_confirmed_callbacks: List[Callable[[str], Awaitable[None]]] = []
        self._node_recovered_callbacks: List[Callable[[str], Awaitable[None]]] = []
    
    async def start(self):
        """Start the failover detector and its background tasks."""
        logger.info(f"Starting failover detector with {self.strategy} strategy")
        
        # Start heartbeat monitoring (always active regardless of strategy)
        self._tasks.append(
            asyncio.create_task(self._heartbeat_monitoring_task())
        )
        
        # Start strategy-specific tasks
        if self.strategy in (FailureDetectionStrategy.GOSSIP, FailureDetectionStrategy.HYBRID):
            self._tasks.append(
                asyncio.create_task(self._gossip_monitoring_task())
            )
        
        if self.strategy in (FailureDetectionStrategy.ADAPTIVE_TIMEOUT, FailureDetectionStrategy.HYBRID):
            self._tasks.append(
                asyncio.create_task(self._adaptive_timeout_task())
            )
        
        if self.strategy in (FailureDetectionStrategy.MULTI_POINT, FailureDetectionStrategy.HYBRID):
            self._tasks.append(
                asyncio.create_task(self._multi_point_detection_task())
            )
        
        if self.strategy in (FailureDetectionStrategy.CONSENSUS, FailureDetectionStrategy.HYBRID):
            self._tasks.append(
                asyncio.create_task(self._consensus_detection_task())
            )
        
        logger.info(f"Failover detector started with {len(self._tasks)} monitoring tasks")
    
    async def stop(self):
        """Stop the failover detector and its background tasks."""
        logger.info("Stopping failover detector")
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks = []
        logger.info("Failover detector stopped")
    
    async def update_nodes(self, nodes: Dict[str, Dict[str, Any]]):
        """
        Update known nodes in the cluster.
        
        Args:
            nodes: Dictionary of node_id -> node_info
        """
        async with self._lock:
            self.nodes = nodes
            
            # Initialize tracking for new nodes
            current_time = time.time()
            for node_id in nodes:
                if node_id not in self.last_heartbeat:
                    self.last_heartbeat[node_id] = current_time
                
                if node_id not in self.missed_heartbeats:
                    self.missed_heartbeats[node_id] = 0
                
                if node_id not in self.response_times:
                    self.response_times[node_id] = []
                
                if node_id not in self.adaptive_timeouts:
                    self.adaptive_timeouts[node_id] = self.heartbeat_timeout
            
            # Remove tracking for nodes that no longer exist
            for node_id in list(self.last_heartbeat.keys()):
                if node_id not in nodes:
                    self.last_heartbeat.pop(node_id, None)
                    self.missed_heartbeats.pop(node_id, None)
                    self.response_times.pop(node_id, None)
                    self.adaptive_timeouts.pop(node_id, None)
                    self.suspected_nodes.discard(node_id)
                    self.confirmed_failed_nodes.discard(node_id)
    
    async def record_heartbeat(self, node_id: str):
        """
        Record a heartbeat from a node.
        
        Args:
            node_id: ID of the node that sent the heartbeat
        """
        async with self._lock:
            current_time = time.time()
            
            # Record heartbeat time
            self.last_heartbeat[node_id] = current_time
            
            # Reset missed heartbeats counter
            self.missed_heartbeats[node_id] = 0
            
            # If node was previously suspected, check if it's recovered
            if node_id in self.suspected_nodes:
                logger.info(f"Node {node_id} is responding to heartbeats again")
                self.suspected_nodes.remove(node_id)
                
                # Notify of recovery
                for callback in self._node_recovered_callbacks:
                    asyncio.create_task(callback(node_id))
            
            # If node was previously confirmed as failed, reintegrate it
            if node_id in self.confirmed_failed_nodes:
                logger.info(f"Node {node_id} has recovered from confirmed failure")
                self.confirmed_failed_nodes.remove(node_id)
                
                # Notify of recovery
                for callback in self._node_recovered_callbacks:
                    asyncio.create_task(callback(node_id))
    
    async def record_response_time(self, node_id: str, response_time_ms: float):
        """
        Record a response time measurement for a node.
        
        Args:
            node_id: ID of the node
            response_time_ms: Response time in milliseconds
        """
        async with self._lock:
            if node_id not in self.response_times:
                self.response_times[node_id] = []
            
            # Add response time to history (keeping recent entries)
            self.response_times[node_id].append(response_time_ms)
            if len(self.response_times[node_id]) > 20:
                self.response_times[node_id].pop(0)
            
            # For adaptive timeouts, update timeout based on response times
            if self.strategy in (FailureDetectionStrategy.ADAPTIVE_TIMEOUT, FailureDetectionStrategy.HYBRID):
                self._update_adaptive_timeout(node_id)
    
    def register_node_suspected_callback(self, callback: Callable[[str], Awaitable[None]]):
        """
        Register callback for when a node is suspected failed.
        
        Args:
            callback: Async function that takes node_id as argument
        """
        self._node_suspected_callbacks.append(callback)
    
    def register_node_confirmed_callback(self, callback: Callable[[str], Awaitable[None]]):
        """
        Register callback for when a node is confirmed failed.
        
        Args:
            callback: Async function that takes node_id as argument
        """
        self._node_confirmed_callbacks.append(callback)
    
    def register_node_recovered_callback(self, callback: Callable[[str], Awaitable[None]]):
        """
        Register callback for when a node recovers.
        
        Args:
            callback: Async function that takes node_id as argument
        """
        self._node_recovered_callbacks.append(callback)
    
    async def confirm_node_failure(self, node_id: str) -> Dict[str, Any]:
        """
        Run comprehensive checks to confirm node failure.
        
        Args:
            node_id: ID of node to check
        
        Returns:
            Dictionary with confirmation results
        """
        logger.info(f"Running comprehensive failure checks for node {node_id}")
        
        # Strategies to use based on configured detection strategy
        use_heartbeat = True  # Always use heartbeat
        use_adaptive = self.strategy in (FailureDetectionStrategy.ADAPTIVE_TIMEOUT, FailureDetectionStrategy.HYBRID)
        use_consensus = self.strategy in (FailureDetectionStrategy.CONSENSUS, FailureDetectionStrategy.HYBRID)
        use_multi_point = self.strategy in (FailureDetectionStrategy.MULTI_POINT, FailureDetectionStrategy.HYBRID)
        use_gossip = self.strategy in (FailureDetectionStrategy.GOSSIP, FailureDetectionStrategy.HYBRID)
        
        # Run individual checks and track results
        results = {}
        confirmed_count = 0
        total_checks = 0
        
        # Heartbeat check
        if use_heartbeat:
            heartbeat_result = await self._check_heartbeats(node_id)
            results["heartbeat"] = heartbeat_result
            if heartbeat_result.get("confirmed", False):
                confirmed_count += 1
            total_checks += 1
        
        # Adaptive timeout check (combines with heartbeat)
        if use_adaptive:
            adaptive_result = await self._check_adaptive_timeout(node_id)
            results["adaptive"] = adaptive_result
            if adaptive_result.get("confirmed", False):
                confirmed_count += 1
            total_checks += 1
        
        # Consensus check
        if use_consensus:
            consensus_result = await self._check_consensus(node_id)
            results["consensus"] = consensus_result
            if consensus_result.get("confirmed", False):
                confirmed_count += 1
            total_checks += 1
        
        # Multi-point check
        if use_multi_point:
            multi_point_result = await self._check_multi_point(node_id)
            results["multi_point"] = multi_point_result
            if multi_point_result.get("confirmed", False):
                confirmed_count += 1
            total_checks += 1
        
        # Gossip check
        if use_gossip:
            gossip_result = await self._check_gossip(node_id)
            results["gossip"] = gossip_result
            if gossip_result.get("confirmed", False):
                confirmed_count += 1
            total_checks += 1
        
        # Determine overall confirmation
        overall_confirmed = False
        
        if self.strategy == FailureDetectionStrategy.HYBRID:
            # For hybrid, majority of methods must confirm failure
            overall_confirmed = confirmed_count > total_checks / 2
        else:
            # For individual strategies, use their result
            strategy_key = self.strategy.value
            if strategy_key in results:
                overall_confirmed = results[strategy_key].get("confirmed", False)
            else:
                # Fallback to heartbeat if strategy not implemented
                overall_confirmed = results.get("heartbeat", {}).get("confirmed", False)
        
        # Update internal state
        async with self._lock:
            if overall_confirmed and node_id not in self.confirmed_failed_nodes:
                self.confirmed_failed_nodes.add(node_id)
                
                # Notify of confirmation
                for callback in self._node_confirmed_callbacks:
                    asyncio.create_task(callback(node_id))
        
        # Build comprehensive result
        confirmation_result = {
            "node_id": node_id,
            "confirmed": overall_confirmed,
            "confirmed_count": confirmed_count,
            "total_checks": total_checks,
            "strategies_used": list(results.keys()),
            "strategy_results": results
        }
        
        logger.info(
            f"Node {node_id} failure confirmation: {overall_confirmed} "
            f"({confirmed_count}/{total_checks} strategies confirm)"
        )
        
        return confirmation_result
    
    def _update_adaptive_timeout(self, node_id: str):
        """
        Update adaptive timeout for a node based on response times.
        
        Args:
            node_id: Node ID to update timeout for
        """
        if node_id not in self.response_times or len(self.response_times[node_id]) < 5:
            # Not enough data, use default timeout
            self.adaptive_timeouts[node_id] = self.heartbeat_timeout
            return
        
        # Calculate mean and standard deviation
        times = self.response_times[node_id]
        mean = sum(times) / len(times)
        variance = sum((t - mean) ** 2 for t in times) / len(times)
        std_dev = math.sqrt(variance)
        
        # Set timeout to mean + 3 * std_dev (99.7% of normal responses)
        # Convert from ms to seconds
        timeout = (mean + 3 * std_dev) / 1000
        
        # Ensure timeout is within configured bounds
        timeout = max(self.adaptive_timeout_min, min(self.adaptive_timeout_max, timeout))
        
        # Update timeout
        self.adaptive_timeouts[node_id] = timeout
    
    async def _heartbeat_monitoring_task(self):
        """Background task for monitoring node heartbeats."""
        logger.info("Starting heartbeat monitoring task")
        
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                
                current_time = time.time()
                
                async with self._lock:
                    # Check for missing heartbeats
                    for node_id, last_time in list(self.last_heartbeat.items()):
                        # Skip nodes that are already suspected or confirmed
                        if (node_id in self.suspected_nodes or 
                            node_id in self.confirmed_failed_nodes):
                            continue
                        
                        # Get appropriate timeout for this node
                        if node_id in self.adaptive_timeouts:
                            timeout = self.adaptive_timeouts[node_id]
                        else:
                            timeout = self.heartbeat_timeout
                        
                        # Check if heartbeat timeout exceeded
                        time_since_heartbeat = current_time - last_time
                        if time_since_heartbeat > timeout:
                            # Increment missed heartbeats counter
                            self.missed_heartbeats[node_id] = self.missed_heartbeats.get(node_id, 0) + 1
                            
                            # Check if we've missed enough consecutive heartbeats
                            if self.missed_heartbeats[node_id] >= self.consecutive_heartbeat_misses:
                                # Mark as suspected
                                self.suspected_nodes.add(node_id)
                                logger.warning(
                                    f"Node {node_id} suspected failed: "
                                    f"missed {self.missed_heartbeats[node_id]} heartbeats "
                                    f"(last heartbeat {time_since_heartbeat:.1f}s ago)"
                                )
                                
                                # Notify callbacks
                                for callback in self._node_suspected_callbacks:
                                    asyncio.create_task(callback(node_id))
                        else:
                            # Heartbeat is within timeout, reset missed counter
                            self.missed_heartbeats[node_id] = 0
        
        except asyncio.CancelledError:
            logger.info("Heartbeat monitoring task cancelled")
            raise
        
        except Exception as e:
            logger.exception(f"Error in heartbeat monitoring task: {e}")
            # Try to restart
            await asyncio.sleep(1)
            asyncio.create_task(self._heartbeat_monitoring_task())
    
    async def _adaptive_timeout_task(self):
        """Background task for adapting timeouts based on network conditions."""
        logger.info("Starting adaptive timeout task")
        
        try:
            while True:
                await asyncio.sleep(30)  # Update every 30 seconds
                
                async with self._lock:
                    # Update adaptive timeouts for all nodes
                    for node_id in list(self.response_times.keys()):
                        self._update_adaptive_timeout(node_id)
        
        except asyncio.CancelledError:
            logger.info("Adaptive timeout task cancelled")
            raise
        
        except Exception as e:
            logger.exception(f"Error in adaptive timeout task: {e}")
            # Try to restart
            await asyncio.sleep(1)
            asyncio.create_task(self._adaptive_timeout_task())
    
    async def _gossip_monitoring_task(self):
        """Background task for gossip-based failure detection."""
        logger.info("Starting gossip monitoring task")
        
        try:
            while True:
                await asyncio.sleep(5)  # Gossip every 5 seconds
                
                # In a real implementation, we would exchange failure suspicions
                # with other nodes. For this example, this is a placeholder.
                pass
        
        except asyncio.CancelledError:
            logger.info("Gossip monitoring task cancelled")
            raise
        
        except Exception as e:
            logger.exception(f"Error in gossip monitoring task: {e}")
            # Try to restart
            await asyncio.sleep(1)
            asyncio.create_task(self._gossip_monitoring_task())
    
    async def _multi_point_detection_task(self):
        """Background task for multi-point failure detection."""
        logger.info("Starting multi-point detection task")
        
        try:
            while True:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # In a real implementation, we would collect failure reports
                # from multiple network vantage points. For this example, 
                # this is a placeholder.
                pass
        
        except asyncio.CancelledError:
            logger.info("Multi-point detection task cancelled")
            raise
        
        except Exception as e:
            logger.exception(f"Error in multi-point detection task: {e}")
            # Try to restart
            await asyncio.sleep(1)
            asyncio.create_task(self._multi_point_detection_task())
    
    async def _consensus_detection_task(self):
        """Background task for consensus-based failure detection."""
        logger.info("Starting consensus detection task")
        
        try:
            while True:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # In a real implementation, we would collect and process votes
                # from other nodes to reach consensus. For this example,
                # this is a placeholder.
                pass
        
        except asyncio.CancelledError:
            logger.info("Consensus detection task cancelled")
            raise
        
        except Exception as e:
            logger.exception(f"Error in consensus detection task: {e}")
            # Try to restart
            await asyncio.sleep(1)
            asyncio.create_task(self._consensus_detection_task())
    
    async def _check_heartbeats(self, node_id: str) -> Dict[str, Any]:
        """
        Check heartbeat status for a node.
        
        Args:
            node_id: Node ID to check
            
        Returns:
            Dictionary with check results
        """
        async with self._lock:
            if node_id not in self.last_heartbeat:
                return {"confirmed": True, "reason": "node_unknown"}
            
            current_time = time.time()
            last_time = self.last_heartbeat[node_id]
            time_since_heartbeat = current_time - last_time
            missed = self.missed_heartbeats.get(node_id, 0)
            
            # Check if we've missed enough consecutive heartbeats
            # and if the time since last heartbeat exceeds timeout
            timeout = self.adaptive_timeouts.get(node_id, self.heartbeat_timeout)
            confirmed = (
                missed >= self.consecutive_heartbeat_misses and
                time_since_heartbeat > timeout * 1.5  # Extra margin
            )
            
            return {
                "confirmed": confirmed,
                "missed_heartbeats": missed,
                "time_since_heartbeat": time_since_heartbeat,
                "timeout": timeout,
                "required_misses": self.consecutive_heartbeat_misses
            }
    
    async def _check_adaptive_timeout(self, node_id: str) -> Dict[str, Any]:
        """
        Check adaptive timeout status for a node.
        
        Args:
            node_id: Node ID to check
            
        Returns:
            Dictionary with check results
        """
        async with self._lock:
            if node_id not in self.response_times:
                return {"confirmed": False, "reason": "no_response_data"}
            
            # Get recent response times
            response_times = self.response_times[node_id]
            
            # Check for consistently high response times
            if len(response_times) >= 3:
                # Check if recent response times are consistently high
                high_response_count = sum(1 for t in response_times[-3:] 
                                         if t > self.max_response_time_ms)
                
                confirmed = high_response_count >= 2  # At least 2 out of 3 are high
                
                return {
                    "confirmed": confirmed,
                    "high_response_count": high_response_count,
                    "recent_response_times": response_times[-3:],
                    "max_allowed": self.max_response_time_ms
                }
            
            return {"confirmed": False, "reason": "insufficient_data"}
    
    async def _check_consensus(self, node_id: str) -> Dict[str, Any]:
        """
        Check consensus status for a node.
        
        Args:
            node_id: Node ID to check
            
        Returns:
            Dictionary with check results
        """
        # In a real implementation, we would collect votes from other nodes
        # and determine if there's consensus that the node has failed.
        # For this example, we'll simulate it.
        
        # Count total nodes (excluding self and the node being checked)
        total_nodes = len(self.nodes) - (1 if self.node_id in self.nodes else 0) - (1 if node_id in self.nodes else 0)
        
        if total_nodes < 2:
            return {"confirmed": False, "reason": "not_enough_nodes"}
        
        # Simulate votes from other nodes (in reality, these would be collected)
        # Higher chance of failure vote if node is already suspected
        failure_votes = 0
        if node_id in self.suspected_nodes:
            # If we suspect it, simulate that most other nodes do too
            failure_votes = int(total_nodes * 0.8)
        else:
            # Otherwise, assume fewer nodes suspect it
            failure_votes = int(total_nodes * 0.2)
        
        consensus_reached = (failure_votes / total_nodes) >= self.consensus_threshold
        
        return {
            "confirmed": consensus_reached,
            "failure_votes": failure_votes,
            "total_nodes": total_nodes,
            "vote_ratio": failure_votes / total_nodes if total_nodes > 0 else 0,
            "threshold": self.consensus_threshold
        }
    
    async def _check_multi_point(self, node_id: str) -> Dict[str, Any]:
        """
        Check multi-point status for a node.
        
        Args:
            node_id: Node ID to check
            
        Returns:
            Dictionary with check results
        """
        # In a real implementation, we would collect failure reports from
        # multiple network vantage points. For this example, we'll simulate it.
        
        # Start with our own observation (1 point if we suspect the node)
        points_reporting_failure = 1 if node_id in self.suspected_nodes else 0
        
        # Simulate reports from other observation points
        # More likely to report failure if node is already suspected
        if node_id in self.suspected_nodes:
            # If we suspect it, simulate that some other points do too
            points_reporting_failure += 2
        else:
            # Otherwise, assume fewer points observe failure
            points_reporting_failure += 0
        
        confirmed = points_reporting_failure >= self.multi_point_threshold
        
        return {
            "confirmed": confirmed,
            "points_reporting_failure": points_reporting_failure,
            "threshold": self.multi_point_threshold
        }
    
    async def _check_gossip(self, node_id: str) -> Dict[str, Any]:
        """
        Check gossip status for a node.
        
        Args:
            node_id: Node ID to check
            
        Returns:
            Dictionary with check results
        """
        # In a real implementation, we would use gossiped information about
        # node health. For this example, we'll simulate it based on suspicion.
        
        # Simplistic simulation based on whether node is already suspected
        if node_id in self.suspected_nodes:
            gossip_agreement = 0.8  # 80% agreement if already suspected
        else:
            gossip_agreement = 0.2  # 20% agreement otherwise
        
        confirmed = gossip_agreement >= 0.7  # Threshold for gossip confirmation
        
        return {
            "confirmed": confirmed,
            "gossip_agreement": gossip_agreement,
            "threshold": 0.7
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the failover detector.
        
        Returns:
            Dictionary with current status
        """
        return {
            "strategy": self.strategy,
            "node_count": len(self.nodes),
            "suspected_nodes": list(self.suspected_nodes),
            "confirmed_failed_nodes": list(self.confirmed_failed_nodes),
            "heartbeat_interval": self.heartbeat_interval,
            "adaptive_timeouts": self.adaptive_timeouts
        }
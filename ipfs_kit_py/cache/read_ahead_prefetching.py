"""
Read-ahead prefetching implementation for ParquetCIDCache.

This module provides advanced prefetching capabilities that intelligently
load content before it's explicitly requested, reducing perceived latency.
"""

import os
import time
import logging
import threading
import queue
from typing import Dict, List, Set, Tuple, Optional, Any, Callable, Union
import numpy as np
from collections import defaultdict, deque

# Optional imports with fallbacks
try:
    import networkx as nx
    HAVE_NETWORKX = True
except ImportError:
    HAVE_NETWORKX = False

logger = logging.getLogger(__name__)

class AccessPattern:
    """Tracks temporal and spatial access patterns for content prefetching."""

    def __init__(self, max_history: int = 1000, decay_factor: float = 0.9):
        """Initialize the access pattern tracker.

        Args:
            max_history: Maximum number of access events to store
            decay_factor: Factor to apply to older access events (0.0-1.0)
        """
        self.max_history = max_history
        self.decay_factor = decay_factor
        self.access_history = deque(maxlen=max_history)
        self.sequential_patterns = defaultdict(lambda: defaultdict(int))
        self.temporal_patterns = {}
        self.last_updated = time.time()
        self._lock = threading.RLock()

    def record_access(self, cid: str, context: Optional[Dict[str, Any]] = None):
        """Record a content access with optional context information.

        Args:
            cid: The content identifier that was accessed
            context: Optional context information (path, query, etc.)
        """
        timestamp = time.time()
        with self._lock:
            # Add to global access history
            self.access_history.append((cid, timestamp, context))

            # Update sequential patterns if we have history
            if len(self.access_history) >= 2:
                prev_cid, _, _ = self.access_history[-2]
                self.sequential_patterns[prev_cid][cid] += 1

            # Update temporal patterns for this CID
            if cid not in self.temporal_patterns:
                self.temporal_patterns[cid] = {
                    'first_seen': timestamp,
                    'last_seen': timestamp,
                    'access_count': 1,
                    'access_times': [timestamp],
                    'intervals': []
                }
            else:
                pattern = self.temporal_patterns[cid]
                pattern['last_seen'] = timestamp
                pattern['access_count'] += 1
                pattern['access_times'].append(timestamp)

                # Calculate interval from previous access
                if len(pattern['access_times']) >= 2:
                    interval = timestamp - pattern['access_times'][-2]
                    pattern['intervals'].append(interval)

                # Keep only recent access times to limit memory usage
                if len(pattern['access_times']) > 100:
                    pattern['access_times'] = pattern['access_times'][-100:]
                if len(pattern['intervals']) > 100:
                    pattern['intervals'] = pattern['intervals'][-100:]

    def get_sequential_candidates(self, cid: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Get most likely next CIDs based on sequential access patterns.

        Args:
            cid: The content identifier to get predictions for
            limit: Maximum number of candidates to return

        Returns:
            List of (cid, probability) tuples ordered by probability
        """
        with self._lock:
            if cid not in self.sequential_patterns:
                return []

            # Get all next CIDs and their frequencies
            next_cids = self.sequential_patterns[cid]
            if not next_cids:
                return []

            # Calculate total transitions from this CID
            total_transitions = sum(next_cids.values())

            # Calculate probabilities and sort by descending probability
            candidates = [(next_cid, count / total_transitions)
                          for next_cid, count in next_cids.items()]
            candidates.sort(key=lambda x: x[1], reverse=True)

            return candidates[:limit]

    def get_temporal_candidates(self, window_size: float = 60.0, limit: int = 5) -> List[Tuple[str, float]]:
        """Get CIDs that are likely to be accessed soon based on temporal patterns.

        Args:
            window_size: Time window to look ahead (seconds)
            limit: Maximum number of candidates to return

        Returns:
            List of (cid, probability) tuples ordered by probability
        """
        now = time.time()
        candidates = []

        with self._lock:
            for cid, pattern in self.temporal_patterns.items():
                # Skip if never accessed or only accessed once
                if len(pattern.get('intervals', [])) < 2:
                    continue

                # Calculate average and std dev of intervals
                intervals = np.array(pattern['intervals'])
                avg_interval = np.mean(intervals)
                std_interval = np.std(intervals)

                # Skip if too erratic (high std dev) or too infrequent
                if std_interval > avg_interval * 2 or avg_interval > window_size * 10:
                    continue

                # Calculate time since last access
                time_since_last = now - pattern['last_seen']

                # Calculate how close we are to the next predicted access
                # 1.0 means now, 0.0 means far in the future
                next_access_time = pattern['last_seen'] + avg_interval
                if now >= next_access_time:
                    # Already past the predicted time
                    proximity = 1.0
                else:
                    # Calculate proximity score (1.0 = close, 0.0 = far)
                    time_to_next = next_access_time - now
                    if time_to_next <= window_size:
                        proximity = 1.0 - (time_to_next / window_size)
                    else:
                        proximity = 0.0

                # Calculate confidence based on regularity and sample size
                confidence = min(1.0, len(intervals) / 10.0) * (1.0 - min(1.0, std_interval / avg_interval))

                # Final score is the product of proximity and confidence
                score = proximity * confidence

                if score > 0.1:  # Only consider scores above a threshold
                    candidates.append((cid, score))

            # Sort by descending score
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[:limit]

    def build_access_graph(self) -> Optional[Any]:
        """Build a directed graph of access patterns for visualization and analysis.

        Returns:
            NetworkX DiGraph if networkx is available, else None
        """
        if not HAVE_NETWORKX:
            logger.warning("NetworkX is not available. Cannot build access graph.")
            return None

        graph = nx.DiGraph()

        with self._lock:
            # Add nodes for all CIDs with temporal data
            for cid, pattern in self.temporal_patterns.items():
                graph.add_node(cid,
                              access_count=pattern['access_count'],
                              first_seen=pattern['first_seen'],
                              last_seen=pattern['last_seen'])

            # Add edges for sequential transitions
            for from_cid, transitions in self.sequential_patterns.items():
                for to_cid, count in transitions.items():
                    graph.add_edge(from_cid, to_cid,
                                 count=count,
                                 weight=count)

        return graph

class PrefetchStrategy:
    """Base class for prefetching strategies."""

    def __init__(self, name: str):
        """Initialize the prefetch strategy.

        Args:
            name: Name of the strategy for identification
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    def get_prefetch_candidates(self,
                                cid: str,
                                access_pattern: AccessPattern,
                                limit: int = 5) -> List[Tuple[str, float]]:
        """Get candidates to prefetch based on the strategy.

        Args:
            cid: Current CID being accessed
            access_pattern: Access pattern tracker
            limit: Maximum number of candidates to return

        Returns:
            List of (cid, score) tuples ordered by prefetch priority

        Note:
            Scores should be in the range 0.0-1.0, where 1.0 indicates
            highest confidence that the content should be prefetched.
        """
        raise NotImplementedError("Subclasses must implement get_prefetch_candidates")

class SequentialPrefetchStrategy(PrefetchStrategy):
    """Prefetches content based on sequential access patterns."""

    def __init__(self, prefetch_count: int = 2):
        """Initialize the sequential prefetch strategy.

        Args:
            prefetch_count: Number of next items to prefetch
        """
        super().__init__("sequential")
        self.prefetch_count = prefetch_count

    def get_prefetch_candidates(self,
                               cid: str,
                               access_pattern: AccessPattern,
                               limit: int = 5) -> List[Tuple[str, float]]:
        """Get candidates to prefetch based on sequential patterns.

        Args:
            cid: Current CID being accessed
            access_pattern: Access pattern tracker
            limit: Maximum number of candidates to return

        Returns:
            List of (cid, score) tuples ordered by prefetch priority
        """
        return access_pattern.get_sequential_candidates(cid, limit=limit)

class TemporalPrefetchStrategy(PrefetchStrategy):
    """Prefetches content based on temporal access patterns."""

    def __init__(self, window_size: float = 60.0):
        """Initialize the temporal prefetch strategy.

        Args:
            window_size: Time window to look ahead (seconds)
        """
        super().__init__("temporal")
        self.window_size = window_size

    def get_prefetch_candidates(self,
                               cid: str,
                               access_pattern: AccessPattern,
                               limit: int = 5) -> List[Tuple[str, float]]:
        """Get candidates to prefetch based on temporal patterns.

        Args:
            cid: Current CID being accessed
            access_pattern: Access pattern tracker
            limit: Maximum number of candidates to return

        Returns:
            List of (cid, score) tuples ordered by prefetch priority
        """
        return access_pattern.get_temporal_candidates(
            window_size=self.window_size, limit=limit)

class HybridPrefetchStrategy(PrefetchStrategy):
    """Combines multiple prefetch strategies with weighted scoring."""

    def __init__(self, strategies: Dict[PrefetchStrategy, float]):
        """Initialize the hybrid prefetch strategy.

        Args:
            strategies: Dictionary mapping strategies to their weights
        """
        super().__init__("hybrid")
        self.strategies = strategies

        # Normalize weights to sum to 1.0
        total_weight = sum(strategies.values())
        if total_weight > 0:
            self.strategies = {s: w/total_weight for s, w in strategies.items()}

    def get_prefetch_candidates(self,
                               cid: str,
                               access_pattern: AccessPattern,
                               limit: int = 5) -> List[Tuple[str, float]]:
        """Get candidates to prefetch using weighted scoring from multiple strategies.

        Args:
            cid: Current CID being accessed
            access_pattern: Access pattern tracker
            limit: Maximum number of candidates to return

        Returns:
            List of (cid, score) tuples ordered by prefetch priority
        """
        # Gather candidates from all strategies
        all_candidates = {}
        for strategy, weight in self.strategies.items():
            candidates = strategy.get_prefetch_candidates(
                cid, access_pattern, limit=limit*2)  # Get more candidates to allow for overlap

            for candidate_cid, score in candidates:
                weighted_score = score * weight
                if candidate_cid in all_candidates:
                    all_candidates[candidate_cid] += weighted_score
                else:
                    all_candidates[candidate_cid] = weighted_score

        # Convert to list and sort by score
        candidates_list = [(cid, score) for cid, score in all_candidates.items()]
        candidates_list.sort(key=lambda x: x[1], reverse=True)

        return candidates_list[:limit]

class ContentAwarePrefetchStrategy(PrefetchStrategy):
    """Prefetches content based on content relationships and metadata."""

    def __init__(self, content_relationship_fn: Callable[[str], List[Tuple[str, float]]]):
        """Initialize the content-aware prefetch strategy.

        Args:
            content_relationship_fn: Function that returns related content
                given a CID, with scores
        """
        super().__init__("content_aware")
        self.content_relationship_fn = content_relationship_fn

    def get_prefetch_candidates(self,
                               cid: str,
                               access_pattern: AccessPattern,
                               limit: int = 5) -> List[Tuple[str, float]]:
        """Get candidates to prefetch based on content relationships.

        Args:
            cid: Current CID being accessed
            access_pattern: Access pattern tracker
            limit: Maximum number of candidates to return

        Returns:
            List of (cid, score) tuples ordered by prefetch priority
        """
        try:
            related_content = self.content_relationship_fn(cid)
            return related_content[:limit]
        except Exception as e:
            self.logger.warning(f"Error getting content relationships: {e}")
            return []

class ReadAheadPrefetchManager:
    """Manager for read-ahead prefetching operations."""

    def __init__(self,
                 fetch_fn: Callable[[str], Any],
                 max_prefetch_workers: int = 2,
                 max_prefetch_queue: int = 20,
                 max_memory_usage: int = 1024 * 1024 * 100,  # 100MB
                 enable_metrics: bool = True,
                 prefetch_threshold: float = 0.3):
        """Initialize the read-ahead prefetch manager.

        Args:
            fetch_fn: Function to fetch content given a CID
            max_prefetch_workers: Maximum number of worker threads
            max_prefetch_queue: Maximum size of prefetch queue
            max_memory_usage: Maximum memory to use for prefetching (bytes)
            enable_metrics: Whether to collect metrics
            prefetch_threshold: Minimum score to trigger prefetching (0.0-1.0)
        """
        self.fetch_fn = fetch_fn
        self.max_prefetch_workers = max_prefetch_workers
        self.max_prefetch_queue = max_prefetch_queue
        self.max_memory_usage = max_memory_usage
        self.enable_metrics = enable_metrics
        self.prefetch_threshold = prefetch_threshold

        # Create access pattern tracker
        self.access_pattern = AccessPattern()

        # Set up prefetch strategies
        self.strategies = {
            'sequential': SequentialPrefetchStrategy(),
            'temporal': TemporalPrefetchStrategy(),
            'hybrid': HybridPrefetchStrategy({
                SequentialPrefetchStrategy(): 0.7,
                TemporalPrefetchStrategy(): 0.3
            })
        }

        # Default strategy
        self.current_strategy = 'hybrid'

        # Prefetch queue and thread pool
        self.prefetch_queue = queue.PriorityQueue(maxsize=max_prefetch_queue)
        self.prefetch_workers = []
        self.prefetch_active = set()
        self.prefetch_completed = {}
        self.current_memory_usage = 0
        self.running = True
        self._lock = threading.RLock()

        # Metrics
        self.metrics = {
            'prefetch_requested': 0,
            'prefetch_completed': 0,
            'prefetch_hits': 0,
            'prefetch_misses': 0,
            'prefetch_canceled': 0,
            'memory_usage': 0,
            'queue_sizes': [],
            'strategy_successes': defaultdict(int)
        }

        # Start worker threads
        self._start_workers()

    def _start_workers(self):
        """Start prefetch worker threads."""
        for i in range(self.max_prefetch_workers):
            worker = threading.Thread(
                target=self._prefetch_worker,
                name=f"prefetch-worker-{i}",
                daemon=True
            )
            worker.start()
            self.prefetch_workers.append(worker)

    def _prefetch_worker(self):
        """Worker thread that processes prefetch requests."""
        while self.running:
            try:
                # Get the next prefetch request (highest priority first)
                # Timeout allows workers to check running flag periodically
                try:
                    priority, request_time, cid, source_strategy = self.prefetch_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Skip if this was already prefetched or is currently being fetched
                with self._lock:
                    if cid in self.prefetch_completed or cid in self.prefetch_active:
                        self.prefetch_queue.task_done()
                        continue

                    # Mark as being fetched
                    self.prefetch_active.add(cid)

                try:
                    # Fetch the content
                    result = self.fetch_fn(cid)

                    # Update metrics and track completion
                    with self._lock:
                        self.prefetch_active.remove(cid)

                        # Get size (if available)
                        size = getattr(result, 'nbytes', None)
                        if size is None and hasattr(result, '__len__'):
                            try:
                                size = len(result)
                            except:
                                size = 1024  # Default size estimate
                        else:
                            size = 1024  # Default size estimate

                        self.prefetch_completed[cid] = {
                            'timestamp': time.time(),
                            'strategy': source_strategy,
                            'size': size
                        }

                        # Update memory usage tracking
                        self.current_memory_usage += size

                        # Collect metrics
                        if self.enable_metrics:
                            self.metrics['prefetch_completed'] += 1
                            self.metrics['memory_usage'] = self.current_memory_usage
                            self.metrics['strategy_successes'][source_strategy] += 1

                    # Clean up older prefetched content if over memory limit
                    self._cleanup_if_needed()

                except Exception as e:
                    logger.warning(f"Error prefetching {cid}: {e}")

                    with self._lock:
                        if cid in self.prefetch_active:
                            self.prefetch_active.remove(cid)

                            if self.enable_metrics:
                                self.metrics['prefetch_canceled'] += 1

                finally:
                    # Mark task as done
                    self.prefetch_queue.task_done()

            except Exception as e:
                logger.error(f"Unexpected error in prefetch worker: {e}")

    def _cleanup_if_needed(self):
        """Clean up older prefetched content if over memory limit."""
        with self._lock:
            if self.current_memory_usage <= self.max_memory_usage:
                return

            # Get entries sorted by timestamp (oldest first)
            entries = [(cid, info) for cid, info in self.prefetch_completed.items()]
            entries.sort(key=lambda x: x[1]['timestamp'])

            # Remove oldest entries until under limit
            removed = 0
            for cid, info in entries:
                self.current_memory_usage -= info['size']
                del self.prefetch_completed[cid]
                removed += 1

                if self.current_memory_usage <= self.max_memory_usage:
                    break

            logger.debug(f"Cleaned up {removed} prefetched entries to free memory")

    def record_access(self, cid: str, context: Optional[Dict[str, Any]] = None):
        """Record a content access and trigger prefetching.

        Args:
            cid: The content identifier that was accessed
            context: Optional context information (path, query, etc.)
        """
        # Record the access pattern
        self.access_pattern.record_access(cid, context)

        # Check if this was a prefetch hit
        was_prefetch_hit = False
        with self._lock:
            if cid in self.prefetch_completed:
                was_prefetch_hit = True
                strategy = self.prefetch_completed[cid]['strategy']

                if self.enable_metrics:
                    self.metrics['prefetch_hits'] += 1
                    self.metrics['strategy_successes'][strategy] += 1

                # Remove from prefetch completed as it's now explicitly requested
                del self.prefetch_completed[cid]
            elif self.enable_metrics:
                self.metrics['prefetch_misses'] += 1

        # Trigger prefetch for content likely to be accessed next
        self._trigger_prefetch(cid)

        return was_prefetch_hit

    def _trigger_prefetch(self, cid: str):
        """Trigger prefetching for content likely to be accessed next.

        Args:
            cid: Current CID being accessed
        """
        # Skip if queue is full
        if self.prefetch_queue.full():
            return

        # Get the current strategy
        strategy = self.strategies[self.current_strategy]

        # Get prefetch candidates
        candidates = strategy.get_prefetch_candidates(
            cid, self.access_pattern, limit=self.max_prefetch_queue)

        # Filter out already fetched or active prefetches and by threshold
        with self._lock:
            filtered_candidates = [
                (c_cid, score) for c_cid, score in candidates
                if (score >= self.prefetch_threshold and
                    c_cid not in self.prefetch_active and
                    c_cid not in self.prefetch_completed)
            ]

            if self.enable_metrics:
                self.metrics['prefetch_requested'] += len(filtered_candidates)
                self.metrics['queue_sizes'].append(self.prefetch_queue.qsize())
                if len(self.metrics['queue_sizes']) > 100:
                    self.metrics['queue_sizes'] = self.metrics['queue_sizes'][-100:]

        # Add candidates to prefetch queue (negative score for priority)
        for c_cid, score in filtered_candidates:
            try:
                # Queue format: (priority, timestamp, cid, strategy)
                # Lower priority number = higher priority
                self.prefetch_queue.put_nowait(
                    (-score, time.time(), c_cid, self.current_strategy))
            except queue.Full:
                # Queue is full now
                break

    def check_prefetched(self, cid: str) -> bool:
        """Check if content has been prefetched.

        Args:
            cid: Content identifier to check

        Returns:
            True if content has been prefetched, False otherwise
        """
        with self._lock:
            return cid in self.prefetch_completed

    def set_strategy(self, strategy_name: str) -> bool:
        """Set the current prefetch strategy.

        Args:
            strategy_name: Name of the strategy to use

        Returns:
            True if strategy was set, False if not found
        """
        if strategy_name in self.strategies:
            self.current_strategy = strategy_name
            return True
        return False

    def add_custom_strategy(self, name: str, strategy: PrefetchStrategy) -> None:
        """Add a custom prefetch strategy.

        Args:
            name: Name to identify the strategy
            strategy: PrefetchStrategy instance
        """
        self.strategies[name] = strategy

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics about prefetch operations.

        Returns:
            Dictionary of metrics
        """
        with self._lock:
            # Calculate hit rate
            total_requests = self.metrics['prefetch_hits'] + self.metrics['prefetch_misses']
            hit_rate = self.metrics['prefetch_hits'] / total_requests if total_requests > 0 else 0

            # Calculate average queue size
            avg_queue_size = sum(self.metrics['queue_sizes']) / len(self.metrics['queue_sizes']) if self.metrics['queue_sizes'] else 0

            # Add calculated metrics
            metrics = dict(self.metrics)
            metrics['hit_rate'] = hit_rate
            metrics['avg_queue_size'] = avg_queue_size
            metrics['active_prefetch_count'] = len(self.prefetch_active)
            metrics['completed_prefetch_count'] = len(self.prefetch_completed)
            metrics['current_strategy'] = self.current_strategy

            return metrics

    def shutdown(self):
        """Shutdown the prefetch manager and worker threads."""
        self.running = False

        # Wait for workers to finish
        for worker in self.prefetch_workers:
            if worker.is_alive():
                worker.join(timeout=0.5)

        # Clear queues and prefetch records
        with self._lock:
            while not self.prefetch_queue.empty():
                try:
                    self.prefetch_queue.get_nowait()
                    self.prefetch_queue.task_done()
                except queue.Empty:
                    break

            self.prefetch_active.clear()
            self.prefetch_completed.clear()


from typing import Any, Dict, List, Optional, Set, Tuple, Union
import os
import time
import logging
import threading
import collections
import concurrent.futures
from collections import defaultdict
import json

# Import from new location instead of using global module
from ipfs_kit_py.tiered_cache_manager import TieredCacheManager
# Allow imports from tiered_cache for backward compatibility
import ipfs_kit_py.tiered_cache as tiered_cache

logger = logging.getLogger(__name__)

class PredictiveCacheManager:
    """Intelligent cache manager with predictive capabilities.
    
    This class implements advanced predictive caching behavior for enhanced performance:
    1. Access pattern analysis and prediction
    2. Content relationship awareness
    3. Dynamic workload adaptation
    4. Custom cache policies
    5. Time-based and frequency-based cache invalidation
    """
    
    def __init__(self, 
                tiered_cache,  # Type: TieredCacheManager - imported by annotation-only to avoid circular imports
                config: Optional[Dict[str, Any]] = None):
        """Initialize the predictive cache manager.
        
        Args:
            tiered_cache: Reference to the TieredCacheManager instance
            config: Configuration dictionary for predictive behaviors
        """
        self.tiered_cache = tiered_cache
        
        # Import anyio if available for enhanced async operations
        try:
            import anyio
            self.has_async = True
            self.anyio = anyio
        except ImportError:
            self.has_async = False
        
        # Default configuration
        default_config = {
            "pattern_tracking_enabled": True,          # Track access patterns
            "relationship_tracking_enabled": True,     # Track content relationships
            "workload_adaptation_enabled": True,       # Adapt to different workloads
            "prefetching_enabled": True,               # Enable prefetching
            "max_prefetch_items": 20,                  # Maximum items to prefetch at once
            "max_relationship_distance": 3,            # Maximum relationship distance to track
            "prefetch_threshold": 0.7,                 # Prefetch when probability exceeds this
            "prediction_window": 5,                    # Number of recent accesses used for prediction
            "pattern_memory_size": 1000,               # Number of access patterns to remember
            "relationship_memory_size": 5000,          # Number of relationships to track
            "time_based_invalidation_enabled": True,   # Enable time-based invalidation
            "frequency_invalidation_enabled": True,    # Enable frequency-based invalidation
            "max_age_seconds": 86400 * 7,              # Maximum age for cached items (7 days)
            "min_access_frequency": 0.1,               # Minimum access frequency (per day)
            "thread_pool_size": 4,                     # Number of threads for background operations
            "model_snapshot_interval": 3600,           # How often to save the model (seconds)
            "model_storage_path": None,                # Where to store model snapshots
            "async_prefetch_enabled": True,            # Use async prefetching when possible
            "multi_tier_prefetching": True,            # Prefetch across multiple tiers
        }
        
        # Merge provided config with defaults
        self.config = default_config.copy()
        if config:
            self.config.update(config)
            
        # Initialize model storage path if not specified
        if not self.config["model_storage_path"]:
            # Default to a subdirectory of the tiered cache's parquet directory
            if hasattr(tiered_cache, "parquet_cache") and tiered_cache.parquet_cache:
                self.config["model_storage_path"] = os.path.join(
                    tiered_cache.parquet_cache.directory, "predictive_models"
                )
            else:
                self.config["model_storage_path"] = os.path.join(
                    os.path.expanduser("~/.ipfs_cache"), "predictive_models"
                )
        
        # Create model storage directory if it doesn't exist
        os.makedirs(self.config["model_storage_path"], exist_ok=True)
        
        # Initialize access pattern tracking
        self.access_patterns = collections.deque(maxlen=self.config["pattern_memory_size"])
        self.access_history = collections.deque(maxlen=self.config["prediction_window"] * 100)
        
        # Sequence prediction model (Markov chain for simplicity)
        self.transition_probabilities = {}  # {item: {next_item: probability}}
        
        # Content relationship graph
        self.relationship_graph = {}  # {cid: {related_cid: relevance_score}}
        
        # Workload profiles
        self.workload_profiles = {
            "sequential_scan": {"pattern": "sequential", "prefetch_size": 10, "prefetch_ahead": True},
            "random_access": {"pattern": "random", "prefetch_size": 2, "prefetch_ahead": False},
            "clustering": {"pattern": "cluster", "prefetch_size": 5, "prefetch_related": True},
            "temporal_locality": {"pattern": "temporal", "prefetch_recent": True},
        }
        
        # Current detected workload
        self.current_workload = "random_access"  # Default assumption
        
        # Statistics and metrics
        self.metrics = {
            "pattern_predictions": 0,
            "successful_predictions": 0,
            "prefetch_operations": 0,
            "prefetch_hits": 0,
            "relationship_discoveries": 0,
            "workload_switches": 0,
            "invalidations": {"time_based": 0, "frequency_based": 0},
        }
        
        # Thread pool for background operations
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config["thread_pool_size"],
            thread_name_prefix="PredictiveCache"
        )
        
        # Last model snapshot time
        self.last_snapshot_time = time.time()
        
        # Load existing models if available
        self._load_models()
        
        logger.info(
            f"Initialized PredictiveCacheManager with "
            f"pattern_tracking={self.config['pattern_tracking_enabled']}, "
            f"relationship_tracking={self.config['relationship_tracking_enabled']}, "
            f"prefetching={self.config['prefetching_enabled']}"
        )
    
    def record_access(self, cid: str) -> None:
        """Record access to a CID for pattern analysis.
        
        Args:
            cid: The content identifier that was accessed
        """
        if not self.config["pattern_tracking_enabled"]:
            return
            
        # Record in access history
        current_time = time.time()
        self.access_history.append((cid, current_time))
        
        # Update transition probabilities for sequence prediction
        if len(self.access_history) >= 2:
            # Get previous access
            prev_cid, _ = self.access_history[-2]
            
            # Update transition count
            if prev_cid not in self.transition_probabilities:
                self.transition_probabilities[prev_cid] = {}
                
            if cid not in self.transition_probabilities[prev_cid]:
                self.transition_probabilities[prev_cid][cid] = 0
                
            self.transition_probabilities[prev_cid][cid] += 1
            
            # Calculate recent access pattern - look at window_size most recent accesses
            window_size = self.config["prediction_window"]
            if len(self.access_history) >= window_size + 1:
                recent_cids = [item[0] for item in list(self.access_history)[-window_size-1:-1]]
                next_cid = cid
                
                # Record this pattern
                self.access_patterns.append((tuple(recent_cids), next_cid))
        
        # Check if it's time for a model snapshot
        if (current_time - self.last_snapshot_time) > self.config["model_snapshot_interval"]:
            self._save_models()
            self.last_snapshot_time = current_time
        
        # Update workload detection
        self._update_workload_detection()
        
        # Perform prefetching if enabled
        if self.config["prefetching_enabled"]:
            self._prefetch_content(cid)
    
    def record_related_content(self, cid: str, related_cids: List[Tuple[str, float]]) -> None:
        """Record relationship between content items.
        
        Args:
            cid: Base content identifier
            related_cids: List of (related_cid, relevance_score) tuples
        """
        if not self.config["relationship_tracking_enabled"]:
            return
            
        # Initialize relationship entry if it doesn't exist
        if cid not in self.relationship_graph:
            self.relationship_graph[cid] = {}
            
        # Add or update relationships
        for related_cid, relevance_score in related_cids:
            self.relationship_graph[cid][related_cid] = relevance_score
            
            # Create reverse relationship with lower score
            if related_cid not in self.relationship_graph:
                self.relationship_graph[related_cid] = {}
                
            reverse_score = relevance_score * 0.8  # Slightly reduce for reverse direction
            self.relationship_graph[related_cid][cid] = reverse_score
            
            # Track metric
            self.metrics["relationship_discoveries"] += 1
        
        # Limit memory usage by pruning lowest-scoring relationships if needed
        self._prune_relationships()
    
    def invalidate_stale_content(self) -> List[str]:
        """Invalidate content based on time and frequency thresholds.
        
        Returns:
            List of CIDs that were invalidated
        """
        invalidated_cids = []
        current_time = time.time()
        
        # Get all CIDs from the cache
        all_cids = self.tiered_cache.get_all_cids()
        
        # Get metadata for all CIDs
        batch_metadata = self.tiered_cache.batch_get_metadata(all_cids)
        
        # Check each CID against invalidation criteria
        for cid, metadata in batch_metadata.items():
            if metadata is None:
                continue
                
            # Skip if neither invalidation method is enabled
            if not (self.config["time_based_invalidation_enabled"] or 
                   self.config["frequency_invalidation_enabled"]):
                continue
            
            should_invalidate = False
            
            # Time-based invalidation
            if self.config["time_based_invalidation_enabled"]:
                last_access = metadata.get("last_access", 0)
                if isinstance(last_access, (int, float)):
                    age_seconds = current_time - last_access
                    max_age = self.config["max_age_seconds"]
                    
                    if age_seconds > max_age:
                        should_invalidate = True
                        self.metrics["invalidations"]["time_based"] += 1
            
            # Frequency-based invalidation
            if self.config["frequency_invalidation_enabled"] and not should_invalidate:
                added_time = metadata.get("added_time", current_time)
                access_count = metadata.get("access_count", 1)
                
                if isinstance(added_time, (int, float)) and isinstance(access_count, (int, float)):
                    # Calculate accesses per day
                    days_since_added = max(1, (current_time - added_time) / 86400)
                    frequency = access_count / days_since_added
                    
                    if frequency < self.config["min_access_frequency"]:
                        should_invalidate = True
                        self.metrics["invalidations"]["frequency_based"] += 1
            
            # Invalidate if either condition is met
            if should_invalidate:
                # Remove from all cache tiers
                self.tiered_cache.batch_delete([cid])
                invalidated_cids.append(cid)
        
        return invalidated_cids
    
    def predict_next_access(self, cid: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Predict the next content items likely to be accessed.
        
        Args:
            cid: Current content identifier
            limit: Maximum number of predictions to return
        
        Returns:
            List of (predicted_cid, probability) tuples
        """
        predictions = []
        
        # Use Markov chain transition probabilities
        if cid in self.transition_probabilities:
            transitions = self.transition_probabilities[cid]
            
            # Calculate total transitions
            total_transitions = sum(transitions.values())
            
            if total_transitions > 0:
                # Calculate probabilities
                probabilities = {
                    next_cid: count / total_transitions 
                    for next_cid, count in transitions.items()
                }
                
                # Sort by probability (descending)
                sorted_predictions = sorted(
                    probabilities.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )
                
                # Take top predictions up to limit
                predictions = sorted_predictions[:limit]
                
                # Update metrics
                self.metrics["pattern_predictions"] += 1
                
        # Add relationship-based predictions if enabled
        if self.config["relationship_tracking_enabled"] and cid in self.relationship_graph:
            relationships = self.relationship_graph[cid]
            
            # Sort by relevance score
            sorted_relationships = sorted(
                relationships.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Add relationship predictions with adjusted probability
            for related_cid, relevance in sorted_relationships[:limit]:
                # Skip if already in pattern-based predictions
                if any(pred[0] == related_cid for pred in predictions):
                    continue
                    
                # Add with adjusted probability (relationships are less predictive than sequences)
                predictions.append((related_cid, relevance * 0.7))
            
            # Re-sort combined predictions
            predictions = sorted(
                predictions,
                key=lambda x: x[1],
                reverse=True
            )[:limit]
        
        return predictions
    
    def predict_next_accesses(self, cid: str, limit: int = 3) -> List[str]:
        """Get multiple CIDs likely to be accessed next.
        
        This is a compatibility wrapper around predict_next_access that returns
        just the CIDs without probability scores.
        
        Args:
            cid: Current content identifier
            limit: Maximum number of predictions to return
            
        Returns:
            List of predicted CIDs
        """
        try:
            # Call the existing method which returns (cid, probability) tuples
            predictions = self.predict_next_access(cid, limit=limit)
            
            # Extract just the CIDs and limit to the requested number
            return [pred[0] for pred in predictions[:limit]]
        except Exception as e:
            logger.error(f"Error identifying prefetch candidates: {e}")
            return []
    
    def _ensure_async_environment(self) -> bool:
        """Checks if we're in an environment where async operations can be performed.
        
        This method is used to check if we can perform async operations in the 
        prefetching system. With anyio, the event loop management is mostly automatic.
        
        Returns:
            True if async operations are available, False otherwise
        """
        if not self.has_async:
            return False  # Anyio not available
        
        # In anyio, there's no need to explicitly create or manage event loops
        # as it handles that automatically based on the backend being used
        return True
    
    def _prefetch_content(self, cid: str) -> None:
        """Prefetch content likely to be accessed next.
        
        Args:
            cid: Current content identifier
        """
        if not self.config["prefetching_enabled"]:
            return
        
        # Get current workload profile
        workload = self.workload_profiles[self.current_workload]
        prefetch_size = workload["prefetch_size"]
        
        # Get predictions
        predictions = self.predict_next_access(cid, limit=prefetch_size * 2)
        
        # Filter by threshold
        predictions = [
            (pred_cid, prob) for pred_cid, prob in predictions
            if prob >= self.config["prefetch_threshold"]
        ]
        
        # Limit to prefetch size
        predictions = predictions[:prefetch_size]
        
        if not predictions:
            return
            
        # Get list of CIDs to prefetch
        prefetch_cids = [pred[0] for pred in predictions]
        
        # Schedule prefetching in background thread
        self.metrics["prefetch_operations"] += 1
        self.thread_pool.submit(self._perform_prefetch, prefetch_cids)
    
    def _perform_prefetch(self, cids: List[str]) -> None:
        """Perform actual prefetching of content in background.
        
        Args:
            cids: List of CIDs to prefetch
        """
        # Check which CIDs are not already in cache
        present_cids = []
        missing_cids = []
        
        for cid in cids:
            if self.tiered_cache.get_metadata(cid) is not None:
                present_cids.append(cid)
            else:
                missing_cids.append(cid)
        
        # For CIDs already in cache, update their metadata
        if present_cids:
            for cid in present_cids:
                # Track predictive hit
                self.metrics["prefetch_hits"] += 1
                self.metrics["successful_predictions"] += 1
                
                try:
                    # Update metadata to indicate prefetch hit
                    current_metadata = self.tiered_cache.get_metadata(cid) or {}
                    current_metadata["prefetch_hit"] = True
                    current_metadata["prefetch_time"] = time.time()
                    
                    # Track in properties for analytics
                    if "properties" not in current_metadata:
                        current_metadata["properties"] = {}
                    
                    if "prefetch_hits" not in current_metadata["properties"]:
                        current_metadata["properties"]["prefetch_hits"] = 0
                        
                    current_metadata["properties"]["prefetch_hits"] += 1
                    
                    # Update the metadata
                    self.tiered_cache.update_metadata(cid, current_metadata)
                    
                except Exception as e:
                    logger.warning(f"Error updating metadata for prefetch hit {cid}: {e}")
        
        # For missing CIDs, we would need to fetch them from the underlying storage
        # This would be implemented by the caller of the cache system, as this class
        # only manages the cache itself, not the content retrieval
    
    def _update_workload_detection(self) -> None:
        """Detect the current workload pattern and update the workload profile."""
        if not self.config["workload_adaptation_enabled"]:
            return
            
        # Need at least a few accesses to detect a pattern
        if len(self.access_history) < 10:
            return
            
        # Get recent accesses (last 10)
        recent_accesses = list(self.access_history)[-10:]
        cids = [access[0] for access in recent_accesses]
        
        # Check for sequential pattern
        is_sequential = self._is_sequential_pattern(cids)
        
        # Check for temporal locality
        is_temporal = self._is_temporal_locality(recent_accesses)
        
        # Check for clustered access
        is_clustered = self._is_clustered_access(cids)
        
        # Determine the dominant pattern
        if is_sequential:
            new_workload = "sequential_scan"
        elif is_clustered:
            new_workload = "clustering"
        elif is_temporal:
            new_workload = "temporal_locality"
        else:
            new_workload = "random_access"
            
        # Only switch if workload changes
        if new_workload != self.current_workload:
            logger.info(f"Workload changed from {self.current_workload} to {new_workload}")
            self.current_workload = new_workload
            self.metrics["workload_switches"] += 1
    
    def _is_sequential_pattern(self, cids: List[str]) -> bool:
        """Check if access pattern is sequential.
        
        In IPFS, true sequentiality is hard to detect with CIDs,
        but we can detect if the same CIDs are accessed in the same order repeatedly.
        
        Args:
            cids: List of recently accessed CIDs
        
        Returns:
            True if the pattern appears sequential
        """
        # With only CIDs, true sequentiality is hard to detect
        # Look for repeated patterns instead
        
        if len(cids) < 5:
            return False
            
        # Check if the access sequence appears in our tracked patterns
        pattern_matches = 0
        total_patterns = 0
        
        for i in range(len(cids) - 4):
            pattern = tuple(cids[i:i+4])
            next_cid = cids[i+4] if i+4 < len(cids) else None
            
            if next_cid and (pattern, next_cid) in self.access_patterns:
                pattern_matches += 1
                
            total_patterns += 1
            
        # If a significant portion of patterns match known patterns, consider it sequential
        return pattern_matches / max(1, total_patterns) > 0.6
    
    def _is_temporal_locality(self, recent_accesses: List[Tuple[str, float]]) -> bool:
        """Check if access pattern shows temporal locality.
        
        Args:
            recent_accesses: List of (cid, timestamp) tuples
        
        Returns:
            True if the pattern shows strong temporal locality
        """
        # Check if the same items are accessed repeatedly within a short time window
        unique_cids = set(access[0] for access in recent_accesses)
        
        # If fewer unique items than accesses, there's some temporal locality
        return len(unique_cids) < len(recent_accesses) * 0.7
    
    def _is_clustered_access(self, cids: List[str]) -> bool:
        """Check if access pattern shows clustering (related content access).
        
        Args:
            cids: List of recently accessed CIDs
        
        Returns:
            True if the pattern shows related content access
        """
        if not self.config["relationship_tracking_enabled"]:
            return False
            
        # Count how many accesses involve related content
        related_accesses = 0
        
        for i in range(len(cids) - 1):
            current_cid = cids[i]
            next_cid = cids[i+1]
            
            # Check if next item is related to current
            if (current_cid in self.relationship_graph and 
                next_cid in self.relationship_graph[current_cid]):
                related_accesses += 1
                
        # If a significant portion of accesses involve related content, consider it clustered
        return related_accesses / max(1, len(cids) - 1) > 0.4
    
    def _prune_relationships(self) -> None:
        """Prune relationship graph to stay within memory limits."""
        max_relationships = self.config["relationship_memory_size"]
        
        # Count total relationships
        total_relationships = sum(len(rels) for rels in self.relationship_graph.values())
        
        if total_relationships <= max_relationships:
            return
            
        # Need to prune - calculate how many to remove
        to_remove = total_relationships - max_relationships
        
        # Flatten relationship graph for sorting
        flat_relationships = []
        for cid, related in self.relationship_graph.items():
            for related_cid, score in related.items():
                flat_relationships.append((cid, related_cid, score))
                
        # Sort by score (ascending)
        flat_relationships.sort(key=lambda x: x[2])
        
        # Remove weakest relationships
        for cid, related_cid, _ in flat_relationships[:to_remove]:
            if cid in self.relationship_graph and related_cid in self.relationship_graph[cid]:
                del self.relationship_graph[cid][related_cid]
                
            # If a node has no relationships left, remove it completely
            if cid in self.relationship_graph and not self.relationship_graph[cid]:
                del self.relationship_graph[cid]
    
    def _save_models(self) -> None:
        """Save predictive models to disk."""
        model_path = self.config["model_storage_path"]
        
        try:
            # Save transition probabilities
            with open(os.path.join(model_path, "transitions.json"), 'w') as f:
                # Convert keys to strings for JSON serialization
                serializable_transitions = {}
                for key, value in self.transition_probabilities.items():
                    serializable_transitions[key] = {k: v for k, v in value.items()}
                    
                json.dump(serializable_transitions, f)
                
            # Save relationship graph
            with open(os.path.join(model_path, "relationships.json"), 'w') as f:
                json.dump(self.relationship_graph, f)
                
            # Save metrics
            with open(os.path.join(model_path, "metrics.json"), 'w') as f:
                serializable_metrics = {
                    k: (v if not isinstance(v, dict) else dict(v))
                    for k, v in self.metrics.items()
                }
                json.dump(serializable_metrics, f)
                
            # Save model metadata
            with open(os.path.join(model_path, "metadata.json"), 'w') as f:
                metadata = {
                    "timestamp": time.time(),
                    "version": "1.0",
                    "config": self.config,
                    "current_workload": self.current_workload,
                }
                json.dump(metadata, f)
                
            logger.debug("Saved predictive cache models to disk")
            
        except Exception as e:
            logger.error(f"Error saving predictive cache models: {e}")
    
    def _load_models(self) -> None:
        """Load predictive models from disk."""
        model_path = self.config["model_storage_path"]
        
        # Skip if no model files exist
        if not os.path.exists(os.path.join(model_path, "transitions.json")):
            return
            
        try:
            # Load transition probabilities
            with open(os.path.join(model_path, "transitions.json"), 'r') as f:
                self.transition_probabilities = json.load(f)
                
            # Load relationship graph
            with open(os.path.join(model_path, "relationships.json"), 'r') as f:
                self.relationship_graph = json.load(f)
                
            # Load metrics
            with open(os.path.join(model_path, "metrics.json"), 'r') as f:
                loaded_metrics = json.load(f)
                # Update metrics but preserve structure
                for k, v in loaded_metrics.items():
                    if k in self.metrics:
                        if isinstance(self.metrics[k], dict) and isinstance(v, dict):
                            self.metrics[k].update(v)
                        else:
                            self.metrics[k] = v
                
            # Load model metadata
            with open(os.path.join(model_path, "metadata.json"), 'r') as f:
                metadata = json.load(f)
                self.current_workload = metadata.get("current_workload", "random_access")
                
            logger.info("Loaded predictive cache models from disk")
            
        except Exception as e:
            logger.error(f"Error loading predictive cache models: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics about the predictive cache performance.
        
        Returns:
            Dictionary with performance metrics
        """
        # Calculate derived metrics
        prediction_accuracy = 0
        if self.metrics["pattern_predictions"] > 0:
            prediction_accuracy = (
                self.metrics["successful_predictions"] / 
                self.metrics["pattern_predictions"]
            )
            
        prefetch_hit_rate = 0
        if self.metrics["prefetch_operations"] > 0:
            prefetch_hit_rate = (
                self.metrics["prefetch_hits"] / 
                self.metrics["prefetch_operations"]
            )
            
        # Gather current state information
        workload_info = self.workload_profiles[self.current_workload].copy()
        workload_info["name"] = self.current_workload
        
        return {
            "pattern_predictions": self.metrics["pattern_predictions"],
            "successful_predictions": self.metrics["successful_predictions"],
            "prediction_accuracy": prediction_accuracy,
            "prefetch_operations": self.metrics["prefetch_operations"],
            "prefetch_hits": self.metrics["prefetch_hits"],
            "prefetch_hit_rate": prefetch_hit_rate,
            "relationship_discoveries": self.metrics["relationship_discoveries"],
            "relationships_tracked": sum(len(rels) for rels in self.relationship_graph.values()),
            "workload_switches": self.metrics["workload_switches"],
            "current_workload": workload_info,
            "invalidations": dict(self.metrics["invalidations"]),
            "transition_model_size": len(self.transition_probabilities),
            "access_history_size": len(self.access_history),
            "access_pattern_size": len(self.access_patterns),
            "read_ahead_metrics": self.read_ahead_metrics if hasattr(self, "read_ahead_metrics") else {},
        }
    
    def setup_read_ahead_prefetching(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Set up advanced read-ahead prefetching capabilities.
        
        This implements advanced read-ahead prefetching strategies for optimized content access:
        1. Content-aware prefetching based on semantic relationships
        2. Streaming prefetch for sequential data
        3. Latency-optimized prefetching based on network conditions
        4. Multi-tier adaptive prefetching
        
        Args:
            config: Optional configuration for read-ahead behavior
        """
        # Default read-ahead configuration
        default_read_ahead_config = {
            "enabled": True,
            "sequential_chunk_size": 5,  # Number of items to prefetch in sequential mode
            "random_sample_size": 2,     # Number of items to prefetch in random mode
            "semantic_depth": 2,         # How deep to follow semantic relationships
            "network_latency_threshold": 100,  # ms threshold for network optimization
            "streaming_buffer_size": 10 * 1024 * 1024,  # 10MB buffer for streaming
            "streaming_threshold": 50 * 1024 * 1024,    # 50MB threshold for streaming mode
            "max_parallel_prefetch": 5,  # Maximum parallel prefetch operations
            "content_type_specific": {   # Type-specific prefetch configurations
                "video": {"sequential": True, "chunk_size": 10},
                "dataset": {"semantic": True, "depth": 3},
                "model": {"relationship_priority": True}
            },
            "tier_specific": {           # Tier-specific prefetch configurations
                "memory": {"priority": 1, "max_size": 10 * 1024 * 1024},
                "disk": {"priority": 2, "max_size": 100 * 1024 * 1024},
                "network": {"priority": 3, "max_size": None}
            }
        }
        
        # Merge with provided config
        self.read_ahead_config = default_read_ahead_config.copy()
        if config:
            # Deep merge for nested dictionaries
            for key, value in config.items():
                if (key in self.read_ahead_config and 
                    isinstance(self.read_ahead_config[key], dict) and 
                    isinstance(value, dict)):
                    self.read_ahead_config[key].update(value)
                else:
                    self.read_ahead_config[key] = value
        
        # Initialize metrics for read-ahead operations
        self.read_ahead_metrics = {
            "sequential_prefetches": 0,
            "semantic_prefetches": 0,
            "streaming_operations": 0,
            "network_optimized_fetches": 0,
            "prefetch_bytes_total": 0,
            "content_type_prefetches": defaultdict(int),
            "tier_prefetches": defaultdict(int),
            "latency_savings_ms": 0,
            "successful_predictions": 0,
            "total_predictions": 0,
        }
        
        # Add to existing workload profiles
        self.workload_profiles["sequential_scan"]["read_ahead"] = {
            "mode": "sequential",
            "chunk_size": self.read_ahead_config["sequential_chunk_size"]
        }
        self.workload_profiles["random_access"]["read_ahead"] = {
            "mode": "random",
            "sample_size": self.read_ahead_config["random_sample_size"]
        }
        self.workload_profiles["clustering"]["read_ahead"] = {
            "mode": "semantic",
            "depth": self.read_ahead_config["semantic_depth"]
        }
        self.workload_profiles["temporal_locality"]["read_ahead"] = {
            "mode": "frequency_based",
            "recency_weight": 0.7
        }
        
        logger.info(f"Set up read-ahead prefetching with {len(self.read_ahead_config['content_type_specific'])} content type strategies")
    
    def prefetch_content_stream(self, cid: str, stream_size: int, chunk_size: int = None) -> bool:
        """Set up streaming prefetch for large content.
        
        This method optimizes access to large content by setting up a streaming
        prefetch operation that retrieves content in chunks ahead of consumption.
        
        Args:
            cid: Content identifier for the stream
            stream_size: Total size of the content in bytes
            chunk_size: Optional custom chunk size in bytes
            
        Returns:
            True if streaming prefetch was set up, False otherwise
        """
        if not hasattr(self, "read_ahead_config"):
            self.setup_read_ahead_prefetching()
            
        if not self.read_ahead_config["enabled"]:
            return False
            
        # Only use streaming for large content
        if stream_size < self.read_ahead_config["streaming_threshold"]:
            return False
            
        # Determine appropriate chunk size
        if chunk_size is None:
            chunk_size = min(
                self.read_ahead_config["streaming_buffer_size"],
                stream_size // 10  # Default to 10 chunks
            )
            
        # Calculate number of chunks
        num_chunks = (stream_size + chunk_size - 1) // chunk_size  # Ceiling division
        
        # For streaming content, we would typically use byte ranges
        # This is a simplified implementation that would need to be adapted
        # to the actual content retrieval mechanism
        
        # Launch prefetch operation in background using anyio for improved concurrency
        if self.has_async and self.tiered_cache.config.get("async_prefetch_enabled", True):
            # Use anyio instead of asyncio
            if self._ensure_async_environment():
                self.anyio.create_task(self._async_perform_stream_prefetch(cid, stream_size, chunk_size, num_chunks))
                logger.debug(f"Started async prefetch for {cid} with {num_chunks} chunks")
        else:
            # Fallback to thread pool for older Python versions
            self.thread_pool.submit(
                self._perform_stream_prefetch, 
                cid, 
                stream_size, 
                chunk_size,
                num_chunks
            )
        
        # Update metrics
        self.read_ahead_metrics["streaming_operations"] += 1
        
        return True
        
    def _perform_stream_prefetch(self, cid: str, total_size: int, chunk_size: int, num_chunks: int) -> None:
        """Perform streaming prefetch in background.
        
        Args:
            cid: Content identifier
            total_size: Total content size
            chunk_size: Size of each chunk
            num_chunks: Number of chunks to prefetch
        """
        # Track starting time for latency optimization
        start_time = time.time()
        
        # Prefetch buffer to track chunks
        prefetch_buffer = {}
        chunk_times = []
        
        # Prefetch chunks sequentially
        for chunk_idx in range(num_chunks):
            chunk_start = chunk_idx * chunk_size
            chunk_end = min(chunk_start + chunk_size, total_size)
            
            # Track chunk retrieval time
            chunk_fetch_start = time.time()
            
            try:
                # In a real implementation, this would be a byte range request to the content retriever
                # For now, simulate the operation
                time.sleep(0.01)  # Simulate retrieval latency
                
                # Record timing
                chunk_time = time.time() - chunk_fetch_start
                chunk_times.append(chunk_time)
                
                # Store chunk metadata in buffer
                prefetch_buffer[chunk_idx] = {
                    "range": (chunk_start, chunk_end),
                    "size": chunk_end - chunk_start,
                    "retrieval_time": chunk_time
                }
                
                # Update metrics
                chunk_size = chunk_end - chunk_start
                self.read_ahead_metrics["prefetch_bytes_total"] += chunk_size
                
            except Exception as e:
                logger.error(f"Error prefetching chunk {chunk_idx} for {cid}: {e}")
                break
        
        # Calculate efficiency metrics if we have timing data
        if chunk_times:
            avg_chunk_time = sum(chunk_times) / len(chunk_times)
            sequential_time = sum(chunk_times)
            
            # Estimate latency savings (sequential vs. parallel)
            estimated_savings = sequential_time * 0.6 * 1000  # 60% savings in ms
            if hasattr(self, "read_ahead_metrics"):
                self.read_ahead_metrics["latency_savings_ms"] += estimated_savings
        
        # Log completion
        total_time = time.time() - start_time
        logger.debug(f"Completed stream prefetch for {cid}: {len(prefetch_buffer)}/{num_chunks} chunks in {total_time:.2f}s")
    
    async def _async_perform_stream_prefetch(self, cid: str, total_size: int, chunk_size: int, num_chunks: int) -> None:
        """Perform streaming prefetch using asynchronous I/O for higher throughput.
        
        This implements a more efficient streaming prefetch using anyio for concurrent
        chunk retrieval, providing better throughput and resource utilization than
        the thread-based approach.
        
        Args:
            cid: Content identifier
            total_size: Total content size
            chunk_size: Size of each chunk
            num_chunks: Number of chunks to prefetch
        """
        # Track starting time for metrics
        start_time = time.time()
        
        # Create semaphore to limit concurrent retrievals
        max_concurrent = min(
            self.read_ahead_config.get("max_parallel_prefetch", 5),
            num_chunks
        )
        semaphore = self.anyio.Semaphore(max_concurrent)
        
        # Create prefetch buffer
        prefetch_buffer = {}
        chunk_times = []
        
        # Create tasks for chunk retrieval
        async def fetch_chunk(chunk_idx):
            chunk_start = chunk_idx * chunk_size
            chunk_end = min(chunk_start + chunk_size, total_size)
            
            # Use semaphore to limit concurrency
            async with semaphore:
                chunk_fetch_start = time.time()
                
                try:
                    # In a real implementation, this would be an async byte range request
                    # For now, simulate with a small delay
                    await self.anyio.sleep(0.005)  # Simulate async I/O
                    
                    # Record timing
                    chunk_time = time.time() - chunk_fetch_start
                    chunk_times.append(chunk_time)
                    
                    # Store chunk metadata
                    prefetch_buffer[chunk_idx] = {
                        "range": (chunk_start, chunk_end),
                        "size": chunk_end - chunk_start,
                        "retrieval_time": chunk_time
                    }
                    
                    # Update metrics
                    chunk_size = chunk_end - chunk_start
                    self.read_ahead_metrics["prefetch_bytes_total"] += chunk_size
                    
                    return True
                except Exception as e:
                    logger.error(f"Async error prefetching chunk {chunk_idx} for {cid}: {e}")
                    return False
        
        # Create and gather all tasks using anyio task group
        results = []
        
        async with self.anyio.create_task_group() as tg:
            # Create a task for each chunk
            tasks = []
            for i in range(num_chunks):
                task = tg.start_soon(fetch_chunk, i)
                tasks.append(task)
        
        # Calculate metrics
        successful_chunks = sum(1 for r in results if r is True)
        
        # Calculate latency savings (more accurate with async)
        if chunk_times:
            avg_chunk_time = sum(chunk_times) / len(chunk_times)
            
            # In the concurrent case, the savings are greater since multiple chunks retrieved simultaneously
            sequential_time = sum(chunk_times)
            parallel_time = max(chunk_times) * (1 + 0.1 * len(chunk_times))  # Estimate with overhead
            
            estimated_savings = (sequential_time - parallel_time) * 1000  # in ms
            self.read_ahead_metrics["latency_savings_ms"] += estimated_savings
        
        # Log completion
        total_time = time.time() - start_time
        logger.debug(
            f"Completed async stream prefetch for {cid}: {successful_chunks}/{num_chunks} "
            f"chunks in {total_time:.2f}s with {max_concurrent} concurrent streams"
        )
    
    def optimize_network_prefetch(self, network_latency_ms: float) -> None:
        """Optimize prefetching based on network conditions.
        
        Args:
            network_latency_ms: Current network latency in milliseconds
        """
        if not hasattr(self, "read_ahead_config"):
            self.setup_read_ahead_prefetching()
            
        # Only adjust if enabled
        if not self.read_ahead_config["enabled"]:
            return
            
        # Adjust prefetch strategies based on network latency
        if network_latency_ms > self.read_ahead_config["network_latency_threshold"]:
            # High latency: prefetch more to avoid delays
            self.read_ahead_config["sequential_chunk_size"] = min(10, self.read_ahead_config["sequential_chunk_size"] * 2)
            self.read_ahead_config["random_sample_size"] = min(5, self.read_ahead_config["random_sample_size"] + 1)
            
            # Update workload profiles
            self.workload_profiles["sequential_scan"]["read_ahead"]["chunk_size"] = self.read_ahead_config["sequential_chunk_size"]
            self.workload_profiles["random_access"]["read_ahead"]["sample_size"] = self.read_ahead_config["random_sample_size"]
            
            logger.debug(f"Increased prefetch sizes due to high network latency ({network_latency_ms}ms)")
            self.read_ahead_metrics["network_optimized_fetches"] += 1
        else:
            # Low latency: reduce prefetch to avoid wasting bandwidth
            self.read_ahead_config["sequential_chunk_size"] = max(2, int(self.read_ahead_config["sequential_chunk_size"] * 0.75))
            self.read_ahead_config["random_sample_size"] = max(1, self.read_ahead_config["random_sample_size"] - 1)
            
            # Update workload profiles
            self.workload_profiles["sequential_scan"]["read_ahead"]["chunk_size"] = self.read_ahead_config["sequential_chunk_size"]
            self.workload_profiles["random_access"]["read_ahead"]["sample_size"] = self.read_ahead_config["random_sample_size"]
            
            logger.debug(f"Decreased prefetch sizes due to good network latency ({network_latency_ms}ms)")
    
    def prefetch_semantic_content(self, cid: str, content_type: str = None, depth: int = None) -> List[str]:
        """Prefetch content based on semantic relationships.
        
        Args:
            cid: Base content identifier
            content_type: Optional content type for type-specific strategies
            depth: How many relationship levels to follow
            
        Returns:
            List of CIDs that were prefetched
        """
        if not hasattr(self, "read_ahead_config"):
            self.setup_read_ahead_prefetching()
            
        if not self.read_ahead_config["enabled"]:
            return []
            
        # Use type-specific configuration if available
        if content_type and content_type in self.read_ahead_config["content_type_specific"]:
            type_config = self.read_ahead_config["content_type_specific"][content_type]
            if not type_config.get("semantic", True):
                return []  # Skip if semantic prefetch disabled for this type
                
            # Use type-specific depth if not explicitly provided
            if depth is None and "depth" in type_config:
                depth = type_config["depth"]
                
        # Use default depth if still not set
        if depth is None:
            depth = self.read_ahead_config["semantic_depth"]
            
        # Get related content from relationship graph (up to specified depth)
        prefetched_cids = []
        current_level = [cid]
        seen_cids = {cid}
        
        for level in range(depth):
            next_level = []
            
            for current_cid in current_level:
                # Get direct relationships
                if current_cid in self.relationship_graph:
                    # Sort by relevance
                    sorted_relationships = sorted(
                        self.relationship_graph[current_cid].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )
                    
                    # Take top related items
                    for related_cid, relevance in sorted_relationships:
                        if related_cid not in seen_cids:
                            # Skip if relevance too low for deeper levels
                            if level > 0 and relevance < 0.3:
                                continue
                                
                            # Add to prefetch queue
                            next_level.append(related_cid)
                            prefetched_cids.append(related_cid)
                            seen_cids.add(related_cid)
                            
                            # Limit total items per level
                            if len(next_level) >= 10:
                                break
            
            current_level = next_level
            if not current_level:
                break  # No more items to explore
        
        # Initiate prefetch in background if we found related content
        if prefetched_cids:
            # Update metrics
            self.read_ahead_metrics["semantic_prefetches"] += 1
            self.read_ahead_metrics["content_type_prefetches"][content_type or "unknown"] += 1
            
            # Start prefetch in background
            self.thread_pool.submit(self._perform_prefetch, prefetched_cids)
        
        return prefetched_cids
    
    def shutdown(self) -> None:
        """Shut down the predictive cache manager."""
        # Save models before shutting down
        self._save_models()
        
        # Shut down thread pool
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=False)

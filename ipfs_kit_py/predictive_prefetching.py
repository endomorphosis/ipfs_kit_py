"""
Optimized Predictive Prefetching Module for IPFS Content.

This module implements enhanced predictive algorithms for optimizing content 
access patterns in IPFS-based distributed storage. It provides sophisticated
prefetching strategies based on:

1. Access pattern analysis with Markov models
2. Content relationships (graph-based)
3. Semantic analysis of content types
4. Machine learning prediction models
5. Context-aware workload detection
"""

import time
import logging
import collections
import threading
import concurrent.futures
import os
import json
import math
import random
from typing import Dict, List, Optional, Tuple, Any, Set, Deque, Union
from collections import defaultdict

# Optional integration with more advanced models
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import anyio
    HAS_ASYNCIO = True
except ImportError:
    HAS_ASYNCIO = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

# Initialize logger
logger = logging.getLogger(__name__)


class MarkovPrefetchModel:
    """Advanced Markov Chain model for content access prediction.
    
    This implementation uses a higher-order Markov model that considers
    longer sequences of access patterns for more accurate prediction.
    """
    
    def __init__(self, order: int = 2, decay_factor: float = 0.9, max_memory: int = 10000):
        """Initialize the Markov prefetch model.
        
        Args:
            order: Order of the Markov model (1 = first-order, 2 = second-order, etc.)
            decay_factor: Weight for time decay (older transitions get lower weight)
            max_memory: Maximum number of transitions to remember
        """
        self.order = order
        self.decay_factor = decay_factor
        self.max_memory = max_memory
        
        # Transition matrices for different orders
        self.transitions = {}
        for i in range(1, order + 1):
            self.transitions[i] = defaultdict(lambda: defaultdict(float))
        
        # Access history
        self.history = collections.deque(maxlen=order * 100)
        
        # Timestamp of transitions for time-decay
        self.transition_times = {}
        
        # Performance metrics
        self.metrics = {
            "predictions": 0,
            "hits": 0,
            "sequence_counts": defaultdict(int)
        }
    
    def record_access(self, cid: str) -> None:
        """Record a content access to the model.
        
        Args:
            cid: Content identifier that was accessed
        """
        current_time = time.time()
        
        # Add to history
        self.history.append((cid, current_time))
        
        # Update transition matrices for each order
        for i in range(1, self.order + 1):
            if len(self.history) >= i + 1:
                # Extract the previous sequence of length i
                prev_sequence = tuple(item[0] for item in list(self.history)[-i-1:-1])
                
                # Get the next item
                next_item = cid
                
                # Update transition count with time decay
                if prev_sequence not in self.transition_times:
                    self.transition_times[prev_sequence] = {}
                
                self.transition_times[prev_sequence][next_item] = current_time
                
                # Record sequence 
                self.metrics["sequence_counts"][prev_sequence] += 1
                
                # Update transition probability
                self.transitions[i][prev_sequence][next_item] += 1
        
        # Prune transitions if needed
        if len(self.transition_times) > self.max_memory:
            self._prune_transitions()
    
    def predict_next(self, cid: str, max_predictions: int = 5) -> List[Tuple[str, float]]:
        """Predict the next content likely to be accessed.
        
        Args:
            cid: Current content identifier
            max_predictions: Maximum number of predictions to return
            
        Returns:
            List of (content_id, probability) tuples sorted by probability
        """
        self.metrics["predictions"] += 1
        combined_predictions = {}
        
        # Consider recent history to create context
        if len(self.history) >= self.order:
            # Build current sequence for each order
            for i in range(1, self.order + 1):
                # Create sequence ending with current CID
                # For higher orders, we look at the pattern before current CID
                if len(self.history) >= i:
                    # Create sequence from history
                    sequence = tuple(item[0] for item in list(self.history)[-i:])
                    if i > 1:
                        # For higher orders, we want sequence that ends with current CID
                        # If current CID is not last in history, we add it
                        if sequence[-1] != cid:
                            sequence = sequence[1:] + (cid,)
                    else:
                        # For order 1, we just need the current CID
                        sequence = (cid,)
                    
                    # Check for transitions from this sequence
                    if sequence in self.transitions[i]:
                        transitions = self.transitions[i][sequence]
                        
                        # Calculate total count
                        total = sum(transitions.values())
                        
                        # Calculate probabilities with time decay
                        current_time = time.time()
                        
                        for next_cid, count in transitions.items():
                            # Apply time decay based on transition time
                            time_factor = 1.0
                            if sequence in self.transition_times and next_cid in self.transition_times[sequence]:
                                time_diff = current_time - self.transition_times[sequence][next_cid]
                                time_factor = math.exp(-time_diff / (3600 * 24))  # Daily decay
                            
                            # Calculate probability
                            probability = (count / total) * time_factor
                            
                            # Weight by order (higher orders get more weight)
                            order_weight = i / self.order
                            
                            # Update combined predictions
                            if next_cid not in combined_predictions:
                                combined_predictions[next_cid] = 0
                            
                            # Add weighted probability
                            combined_predictions[next_cid] += probability * order_weight
        
        # Convert to list and sort by probability
        predictions = [(cid, prob) for cid, prob in combined_predictions.items()]
        predictions.sort(key=lambda x: x[1], reverse=True)
        
        # Return top predictions
        return predictions[:max_predictions]
    
    def _prune_transitions(self) -> None:
        """Prune the transition matrices to stay within memory limits."""
        # Find oldest transitions
        flat_transitions = []
        
        for sequence, transitions in self.transition_times.items():
            for next_item, timestamp in transitions.items():
                flat_transitions.append((sequence, next_item, timestamp))
        
        # Sort by timestamp (oldest first)
        flat_transitions.sort(key=lambda x: x[2])
        
        # Remove oldest transitions until within memory limit
        to_remove = len(flat_transitions) - self.max_memory
        
        for sequence, next_item, _ in flat_transitions[:to_remove]:
            # Determine order of this sequence
            order = len(sequence)
            
            # Remove from transition matrices
            if order <= self.order:
                if sequence in self.transitions[order] and next_item in self.transitions[order][sequence]:
                    del self.transitions[order][sequence][next_item]
                
                # Remove from timestamps
                if sequence in self.transition_times and next_item in self.transition_times[sequence]:
                    del self.transition_times[sequence][next_item]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the model."""
        stats = {
            "order": self.order,
            "history_length": len(self.history),
            "transitions": sum(len(trans) for trans in self.transitions.values()),
            "predictions": self.metrics["predictions"],
            "hits": self.metrics["hits"],
            "accuracy": 0,
            "most_common_sequences": []
        }
        
        # Calculate accuracy
        if stats["predictions"] > 0:
            stats["accuracy"] = stats["hits"] / stats["predictions"]
        
        # Get most common sequences
        most_common = sorted(
            self.metrics["sequence_counts"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        stats["most_common_sequences"] = most_common
        
        return stats


class GraphRelationshipModel:
    """Graph-based relationship model for content relationship analysis.
    
    This model uses graph theory to track and analyze relationships between
    content items, enabling semantic prefetching based on content relationships.
    """
    
    def __init__(self, decay_factor: float = 0.1, max_edges: int = 10000):
        """Initialize the graph relationship model.
        
        Args:
            decay_factor: Factor for edge weight decay over time
            max_edges: Maximum number of edges to track
        """
        self.decay_factor = decay_factor
        self.max_edges = max_edges
        
        # Initialize relationship graph
        if HAS_NETWORKX:
            # Use NetworkX for efficient graph operations
            self.graph = nx.Graph()
            self.using_networkx = True
        else:
            # Fallback to dictionary-based implementation
            self.graph = defaultdict(dict)
            self.using_networkx = False
        
        # Edge metadata for tracking timestamps
        self.edge_metadata = {}
        
        # Performance metrics
        self.metrics = {
            "nodes": 0,
            "edges": 0,
            "queries": 0,
            "communities": 0
        }
    
    def add_relationship(self, source_cid: str, target_cid: str, 
                         weight: float = 1.0, metadata: Optional[Dict] = None) -> None:
        """Add or update a relationship between content items.
        
        Args:
            source_cid: Source content identifier
            target_cid: Target content identifier
            weight: Relationship strength
            metadata: Additional relationship metadata
        """
        if source_cid == target_cid:
            return  # Skip self-relationships
        
        current_time = time.time()
        
        if metadata is None:
            metadata = {}
        
        # Add timestamp to metadata
        metadata["timestamp"] = current_time
        
        # Update the graph
        if self.using_networkx:
            # Add nodes if they don't exist
            if not self.graph.has_node(source_cid):
                self.graph.add_node(source_cid)
                self.metrics["nodes"] += 1
                
            if not self.graph.has_node(target_cid):
                self.graph.add_node(target_cid)
                self.metrics["nodes"] += 1
            
            # Add or update edge
            if self.graph.has_edge(source_cid, target_cid):
                # Update existing edge
                current_weight = self.graph[source_cid][target_cid]["weight"]
                # Blend weights with decay on old value
                new_weight = (current_weight * (1 - self.decay_factor)) + (weight * self.decay_factor)
                self.graph[source_cid][target_cid]["weight"] = new_weight
                
                # Update metadata
                for key, value in metadata.items():
                    self.graph[source_cid][target_cid][key] = value
            else:
                # Add new edge
                self.graph.add_edge(source_cid, target_cid, weight=weight, **metadata)
                self.metrics["edges"] += 1
        else:
            # Dictionary-based implementation
            # Add nodes if they don't exist
            if source_cid not in self.graph:
                self.graph[source_cid] = {}
                self.metrics["nodes"] += 1
                
            if target_cid not in self.graph:
                self.graph[target_cid] = {}
                self.metrics["nodes"] += 1
            
            # Add or update edge (bidirectional)
            self._update_edge(source_cid, target_cid, weight, metadata)
            self._update_edge(target_cid, source_cid, weight, metadata)
            
            # Track edge metadata
            edge_key = self._get_edge_key(source_cid, target_cid)
            self.edge_metadata[edge_key] = metadata.copy()
            self.edge_metadata[edge_key]["weight"] = weight
        
        # Prune graph if needed
        if self.metrics["edges"] > self.max_edges:
            self._prune_graph()
    
    def _update_edge(self, source: str, target: str, weight: float, metadata: Dict) -> None:
        """Update an edge in the dictionary-based graph implementation."""
        if target in self.graph[source]:
            # Update existing edge
            current_weight = self.graph[source][target].get("weight", 0)
            # Blend weights with decay
            new_weight = (current_weight * (1 - self.decay_factor)) + (weight * self.decay_factor)
            self.graph[source][target]["weight"] = new_weight
            
            # Update metadata
            for key, value in metadata.items():
                self.graph[source][target][key] = value
        else:
            # Add new edge
            self.graph[source][target] = {"weight": weight, **metadata}
            self.metrics["edges"] += 1
    
    def _get_edge_key(self, source: str, target: str) -> str:
        """Get canonical edge key (order-independent)."""
        return "|".join(sorted([source, target]))
    
    def get_related_content(self, cid: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Get content related to the given CID.
        
        Args:
            cid: Content identifier
            limit: Maximum number of results
            
        Returns:
            List of (content_id, relatedness_score) tuples
        """
        self.metrics["queries"] += 1
        
        if self.using_networkx:
            if not self.graph.has_node(cid):
                return []
            
            # Get neighbors with weights
            neighbors = []
            for neighbor, edge_data in self.graph[cid].items():
                neighbors.append((neighbor, edge_data["weight"]))
            
            # Sort by weight
            neighbors.sort(key=lambda x: x[1], reverse=True)
            
            return neighbors[:limit]
        else:
            if cid not in self.graph:
                return []
            
            # Get neighbors with weights
            neighbors = []
            for neighbor, edge_data in self.graph[cid].items():
                neighbors.append((neighbor, edge_data["weight"]))
            
            # Sort by weight
            neighbors.sort(key=lambda x: x[1], reverse=True)
            
            return neighbors[:limit]
    
    def get_community(self, cid: str, max_distance: int = 2) -> List[Tuple[str, float]]:
        """Get the community of related content within a certain distance.
        
        Uses breadth-first search to find related content up to a specified
        distance in the relationship graph.
        
        Args:
            cid: Content identifier
            max_distance: Maximum graph distance to explore
            
        Returns:
            List of (content_id, relevance_score) tuples
        """
        if self.using_networkx:
            if not self.graph.has_node(cid):
                return []
            
            # Use NetworkX for efficient breadth-first search
            community = []
            
            # Get nodes at increasing distances
            for distance in range(1, max_distance + 1):
                # Find nodes at exactly this distance
                nodes_at_distance = nx.single_source_shortest_path_length(self.graph, cid, cutoff=distance)
                
                # Filter to just the ones exactly at this distance
                exact_distance_nodes = [(node, 1.0 / distance) for node, d in nodes_at_distance.items() 
                                       if d == distance]
                
                community.extend(exact_distance_nodes)
            
            # Sort by descending relevance
            community.sort(key=lambda x: x[1], reverse=True)
            
            return community
        else:
            if cid not in self.graph:
                return []
            
            # Custom BFS implementation
            visited = {cid: 0}  # node -> distance
            queue = collections.deque([(cid, 0)])  # (node, distance)
            community = []
            
            while queue:
                node, distance = queue.popleft()
                
                if distance > 0:  # Don't include starting node
                    # Add to community with distance-based score
                    community.append((node, 1.0 / distance))
                
                if distance < max_distance:
                    # Explore neighbors
                    for neighbor in self.graph[node]:
                        if neighbor not in visited:
                            visited[neighbor] = distance + 1
                            queue.append((neighbor, distance + 1))
            
            # Sort by descending relevance
            community.sort(key=lambda x: x[1], reverse=True)
            
            return community
    
    def _prune_graph(self) -> None:
        """Prune the graph to stay within memory limits."""
        # Find edges with lowest weights or oldest timestamps
        if self.using_networkx:
            # Get all edges with data
            edges = [(u, v, data) for u, v, data in self.graph.edges(data=True)]
            
            # Sort by weight (ascending) and timestamp (oldest first)
            edges.sort(key=lambda x: (x[2]["weight"], x[2].get("timestamp", 0)))
            
            # Remove oldest/weakest edges until within limit
            to_remove = len(edges) - self.max_edges
            for u, v, _ in edges[:to_remove]:
                self.graph.remove_edge(u, v)
                self.metrics["edges"] -= 1
            
            # Remove orphaned nodes
            for node in list(self.graph.nodes()):
                if self.graph.degree(node) == 0:
                    self.graph.remove_node(node)
                    self.metrics["nodes"] -= 1
        else:
            # Collect all edges with metadata
            edges = []
            for source in self.graph:
                for target in self.graph[source]:
                    edge_key = self._get_edge_key(source, target)
                    if edge_key in self.edge_metadata:
                        edges.append((source, target, self.edge_metadata[edge_key]))
            
            # Sort by weight (ascending) and timestamp (oldest first)
            edges.sort(key=lambda x: (x[2]["weight"], x[2].get("timestamp", 0)))
            
            # Remove oldest/weakest edges until within limit
            edges_to_remove = set()
            to_remove = len(edges) - self.max_edges
            for source, target, _ in edges[:to_remove]:
                edge_key = self._get_edge_key(source, target)
                edges_to_remove.add(edge_key)
            
            # Actually remove the edges
            for edge_key in edges_to_remove:
                source, target = edge_key.split("|")
                if target in self.graph[source]:
                    del self.graph[source][target]
                if source in self.graph[target]:
                    del self.graph[target][source]
                if edge_key in self.edge_metadata:
                    del self.edge_metadata[edge_key]
                
                self.metrics["edges"] -= 1
            
            # Remove orphaned nodes
            for node in list(self.graph.keys()):
                if not self.graph[node]:
                    del self.graph[node]
                    self.metrics["nodes"] -= 1
    
    def detect_communities(self, min_size: int = 3) -> List[List[str]]:
        """Detect communities in the relationship graph.
        
        Args:
            min_size: Minimum community size to return
            
        Returns:
            List of communities (each a list of CIDs)
        """
        if not self.using_networkx:
            logger.warning("Community detection requires NetworkX; unavailable in fallback mode")
            return []
        
        # Ensure graph has at least a few nodes
        if len(self.graph) < min_size:
            return []
        
        try:
            # Use NetworkX's community detection
            communities = list(nx.algorithms.community.greedy_modularity_communities(self.graph))
            
            # Filter by minimum size
            communities = [list(c) for c in communities if len(c) >= min_size]
            
            self.metrics["communities"] = len(communities)
            
            return communities
        except Exception as e:
            logger.error(f"Error in community detection: {e}")
            return []


class ContentTypeAnalyzer:
    """Analyzes content types for type-specific prefetching strategies.
    
    Different content types (e.g., video, datasets, models) have different
    access patterns. This class analyzes content types to enable type-specific
    prefetching strategies.
    """
    
    def __init__(self):
        """Initialize the content type analyzer."""
        # Content type definitions with access pattern characteristics
        self.type_patterns = {
            "video": {
                "sequential": True,
                "chunk_size": 5,
                "prefetch_ahead": True,
                "extension_patterns": [".mp4", ".avi", ".mkv", ".mov"],
                "mimetype_patterns": ["video/"],
            },
            "audio": {
                "sequential": True,
                "chunk_size": 3,
                "prefetch_ahead": True,
                "extension_patterns": [".mp3", ".wav", ".ogg", ".flac"],
                "mimetype_patterns": ["audio/"],
            },
            "image": {
                "sequential": False,
                "related_content": True,
                "extension_patterns": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
                "mimetype_patterns": ["image/"],
            },
            "document": {
                "partial_sequential": True,
                "related_content": True,
                "extension_patterns": [".pdf", ".doc", ".docx", ".md", ".txt"],
                "mimetype_patterns": ["application/pdf", "text/"],
            },
            "dataset": {
                "chunked_access": True,
                "high_reuse": True,
                "related_content": True,
                "extension_patterns": [".csv", ".parquet", ".json", ".jsonl"],
                "mimetype_patterns": ["text/csv", "application/json"],
            },
            "code": {
                "high_reuse": True,
                "related_content": True,
                "extension_patterns": [".py", ".js", ".go", ".rs", ".cpp", ".h"],
                "mimetype_patterns": ["text/plain", "text/x-python", "text/javascript"],
            },
            "model": {
                "high_reuse": True,
                "all_or_nothing": True,
                "extension_patterns": [".pth", ".h5", ".pb", ".onnx", ".pt"],
                "mimetype_patterns": ["application/octet-stream"],
            },
        }
        
        # Access pattern statistics by type
        self.type_stats = {ctype: {
            "access_count": 0,
            "sequential_score": 0.0,
            "reuse_score": 0.0,
            "avg_chunk_size": 0.0,
        } for ctype in self.type_patterns}
    
    def detect_content_type(self, metadata: Dict[str, Any]) -> str:
        """Detect content type from metadata.
        
        Args:
            metadata: Content metadata dictionary
            
        Returns:
            Detected content type
        """
        # Try filename-based detection
        filename = metadata.get("filename", "")
        if filename:
            extension = os.path.splitext(filename.lower())[1]
            for ctype, patterns in self.type_patterns.items():
                if extension in patterns["extension_patterns"]:
                    return ctype
        
        # Try mimetype-based detection
        mimetype = metadata.get("mimetype", "")
        if mimetype:
            for ctype, patterns in self.type_patterns.items():
                for pattern in patterns["mimetype_patterns"]:
                    if mimetype.startswith(pattern):
                        return ctype
        
        # Default to generic
        return "generic"
    
    def get_prefetch_strategy(self, content_type: str) -> Dict[str, Any]:
        """Get type-specific prefetch strategy.
        
        Args:
            content_type: Content type
            
        Returns:
            Dictionary with prefetch strategy parameters
        """
        # Get base strategy from type patterns
        if content_type in self.type_patterns:
            strategy = self.type_patterns[content_type].copy()
            
            # Enhance with learned parameters from stats
            if content_type in self.type_stats:
                stats = self.type_stats[content_type]
                
                # Adjust chunk size based on statistics
                if "chunk_size" in strategy and stats["avg_chunk_size"] > 0:
                    strategy["chunk_size"] = max(strategy["chunk_size"], 
                                                round(stats["avg_chunk_size"]))
                
                # Adjust sequential preference based on statistics
                if stats["sequential_score"] > 0:
                    strategy["sequential_probability"] = stats["sequential_score"]
            
            return strategy
        
        # Default strategy
        return {
            "sequential": False,
            "chunk_size": 1,
            "prefetch_ahead": False,
            "related_content": False,
        }
    
    def update_stats(self, content_type: str, access_pattern: Dict[str, Any]) -> None:
        """Update statistics for a content type based on observed access pattern.
        
        Args:
            content_type: Content type
            access_pattern: Dictionary with access pattern information
        """
        if content_type not in self.type_stats:
            self.type_stats[content_type] = {
                "access_count": 0,
                "sequential_score": 0.0,
                "reuse_score": 0.0,
                "avg_chunk_size": 0.0,
            }
        
        stats = self.type_stats[content_type]
        stats["access_count"] += 1
        
        # Update sequential score
        if "sequential_score" in access_pattern:
            # Blend new score with existing (more weight to new observations)
            new_seq_score = access_pattern["sequential_score"]
            old_seq_score = stats["sequential_score"]
            stats["sequential_score"] = (old_seq_score * 0.9) + (new_seq_score * 0.1)
        
        # Update reuse score
        if "reuse_score" in access_pattern:
            new_reuse_score = access_pattern["reuse_score"]
            old_reuse_score = stats["reuse_score"]
            stats["reuse_score"] = (old_reuse_score * 0.9) + (new_reuse_score * 0.1)
        
        # Update average chunk size
        if "chunk_size" in access_pattern:
            new_chunk_size = access_pattern["chunk_size"]
            old_avg = stats["avg_chunk_size"]
            if old_avg == 0:
                stats["avg_chunk_size"] = new_chunk_size
            else:
                stats["avg_chunk_size"] = (old_avg * 0.9) + (new_chunk_size * 0.1)


class PredictivePrefetchingEngine:
    """Advanced predictive prefetching engine using multiple prediction models.
    
    This engine combines multiple prediction models and strategies to provide
    highly accurate prefetching recommendations based on content access patterns,
    relationships, and type-specific strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the predictive prefetching engine.
        
        Args:
            config: Configuration dictionary
        """
        # Default configuration
        default_config = {
            "max_prefetch_items": 10,             # Maximum items to prefetch at once
            "prefetch_threshold": 0.3,            # Minimum probability threshold for prefetching
            "markov_enabled": True,               # Enable Markov model
            "markov_order": 2,                    # Order of Markov model
            "graph_enabled": True,                # Enable graph-based model
            "content_type_enabled": True,         # Enable content-type specific strategies
            "combined_model_weights": {           # Weights for combining model predictions
                "markov": 0.6,                    # Weight for Markov model
                "graph": 0.3,                     # Weight for graph model
                "content_type": 0.1,              # Weight for content-type model
            },
            "model_storage_path": None,           # Path for storing model data
            "auto_save_interval": 3600,           # Seconds between auto-save
            "thread_pool_size": 2,                # Thread pool size for background operations
        }
        
        # Merge with provided config
        self.config = default_config.copy()
        if config:
            self.config.update(config)
            
        # Initialize models
        self.markov_model = MarkovPrefetchModel(
            order=self.config["markov_order"]
        ) if self.config["markov_enabled"] else None
        
        self.graph_model = GraphRelationshipModel() if self.config["graph_enabled"] else None
        
        self.content_analyzer = ContentTypeAnalyzer() if self.config["content_type_enabled"] else None
        
        # Access history for global pattern analysis
        self.access_history = collections.deque(maxlen=1000)
        
        # Content metadata cache
        self.content_metadata = {}
        
        # Performance metrics
        self.metrics = {
            "prefetch_operations": 0,
            "prefetch_hits": 0,
            "model_predictions": {
                "markov": 0,
                "graph": 0,
                "content_type": 0,
                "combined": 0,
            },
            "model_hits": {
                "markov": 0,
                "graph": 0,
                "content_type": 0,
                "combined": 0,
            },
        }
        
        # Last save time
        self.last_save_time = time.time()
        
        # Thread pool for background operations
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config["thread_pool_size"]
        )
        
        # Load saved models if available
        self._load_models()
    
    def record_access(self, cid: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a content access event.
        
        Args:
            cid: Content identifier
            metadata: Optional content metadata
        """
        current_time = time.time()
        
        # Store metadata if provided
        if metadata:
            self.content_metadata[cid] = metadata
        
        # Add to history
        self.access_history.append((cid, current_time))
        
        # Update Markov model
        if self.markov_model:
            self.markov_model.record_access(cid)
        
        # Update graph relationships based on access patterns
        if self.graph_model and len(self.access_history) >= 2:
            # Get previous access
            prev_cid, prev_time = self.access_history[-2]
            
            # Calculate time-based relationship strength
            time_diff = current_time - prev_time
            # Stronger relationship for items accessed closer together
            relationship_strength = max(0.1, min(1.0, 1.0 / (1.0 + time_diff/10.0)))
            
            # Add relationship
            self.graph_model.add_relationship(
                prev_cid, 
                cid, 
                weight=relationship_strength,
                metadata={"access_time": current_time, "time_diff": time_diff}
            )
        
        # Update content type statistics
        if self.content_analyzer and metadata:
            content_type = self.content_analyzer.detect_content_type(metadata)
            
            # Create access pattern information
            access_pattern = {"sequential_score": 0.0, "reuse_score": 0.0}
            
            # Calculate sequential score by looking at recent history
            if len(self.access_history) >= 3:
                # Check if recent accesses follow a pattern (like incrementing IDs)
                # This is a simple heuristic - in practice would be more sophisticated
                recent_cids = [access[0] for access in list(self.access_history)[-3:]]
                if self._is_sequential_pattern(recent_cids):
                    access_pattern["sequential_score"] = 0.8
            
            # Update type statistics
            self.content_analyzer.update_stats(content_type, access_pattern)
        
        # Auto-save models if needed
        if (current_time - self.last_save_time) > self.config["auto_save_interval"]:
            self.thread_pool.submit(self._save_models)
            self.last_save_time = current_time
    
    def predict_next_access(self, cid: str, max_items: int = None) -> List[Tuple[str, float]]:
        """Predict next content items likely to be accessed.
        
        Args:
            cid: Current content identifier
            max_items: Maximum number of predictions to return
            
        Returns:
            List of (content_id, probability) tuples
        """
        if max_items is None:
            max_items = self.config["max_prefetch_items"]
        
        self.metrics["prefetch_operations"] += 1
        
        # Get predictions from each model
        markov_predictions = []
        graph_predictions = []
        content_type_predictions = []
        
        # Get Markov model predictions
        if self.markov_model:
            markov_predictions = self.markov_model.predict_next(cid, max_items)
            self.metrics["model_predictions"]["markov"] += 1
        
        # Get graph model predictions
        if self.graph_model:
            graph_predictions = self.graph_model.get_related_content(cid, max_items)
            self.metrics["model_predictions"]["graph"] += 1
        
        # Get content-type specific predictions
        if self.content_analyzer and cid in self.content_metadata:
            metadata = self.content_metadata[cid]
            content_type = self.content_analyzer.detect_content_type(metadata)
            
            # Get type-specific strategy
            strategy = self.content_analyzer.get_prefetch_strategy(content_type)
            
            # Apply type-specific predictions
            # For sequential content, predict next in sequence
            if strategy.get("sequential", False) and len(self.access_history) >= 2:
                # Simplified sequential prediction - in practice would be more sophisticated
                chunk_size = strategy.get("chunk_size", 1)
                
                # Find position in recent history
                recent_cids = [access[0] for access in self.access_history]
                if cid in recent_cids:
                    pos = recent_cids.index(cid)
                    if pos + 1 < len(recent_cids):
                        # Predict next items in sequence
                        next_items = recent_cids[pos+1:pos+1+chunk_size]
                        content_type_predictions = [(item, 0.9 - 0.1*i) for i, item in enumerate(next_items)]
                        self.metrics["model_predictions"]["content_type"] += 1
        
        # Combine predictions with weighted scoring
        combined_predictions = {}
        weights = self.config["combined_model_weights"]
        
        # Add Markov predictions
        for cid, probability in markov_predictions:
            if cid not in combined_predictions:
                combined_predictions[cid] = 0
            combined_predictions[cid] += probability * weights["markov"]
        
        # Add graph predictions
        for cid, probability in graph_predictions:
            if cid not in combined_predictions:
                combined_predictions[cid] = 0
            combined_predictions[cid] += probability * weights["graph"]
        
        # Add content-type predictions
        for cid, probability in content_type_predictions:
            if cid not in combined_predictions:
                combined_predictions[cid] = 0
            combined_predictions[cid] += probability * weights["content_type"]
        
        # Convert to list and sort by probability
        predictions = [(cid, probability) for cid, probability in combined_predictions.items()]
        predictions.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by threshold
        predictions = [(cid, prob) for cid, prob in predictions if prob >= self.config["prefetch_threshold"]]
        
        # Limit number of predictions
        predictions = predictions[:max_items]
        
        if predictions:
            self.metrics["model_predictions"]["combined"] += 1
            
        return predictions
    
    def record_prefetch_hit(self, cid: str, predicted_by: List[str]) -> None:
        """Record a successful prefetch hit for model evaluation.
        
        Args:
            cid: Content identifier that was successfully prefetched
            predicted_by: List of models that predicted this content
        """
        self.metrics["prefetch_hits"] += 1
        
        for model in predicted_by:
            if model in self.metrics["model_hits"]:
                self.metrics["model_hits"][model] += 1
    
    def add_relationship(self, source_cid: str, target_cid: str, 
                         relationship_type: str, strength: float = 1.0,
                         metadata: Optional[Dict] = None) -> None:
        """Add an explicit relationship between content items.
        
        Args:
            source_cid: Source content identifier
            target_cid: Target content identifier
            relationship_type: Type of relationship
            strength: Relationship strength
            metadata: Additional relationship metadata
        """
        if not self.graph_model:
            return
        
        if metadata is None:
            metadata = {}
        
        # Add relationship type to metadata
        metadata["relationship_type"] = relationship_type
        
        # Add relationship to graph model
        self.graph_model.add_relationship(source_cid, target_cid, strength, metadata)
    
    def get_prefetch_candidates(self, cid: str, metadata: Optional[Dict] = None) -> List[str]:
        """Get content candidates for prefetching.
        
        Args:
            cid: Current content identifier
            metadata: Optional content metadata
            
        Returns:
            List of content identifiers to prefetch
        """
        # Update metadata if provided
        if metadata and cid not in self.content_metadata:
            self.content_metadata[cid] = metadata
            
            # Record access (if not already recorded)
            self.record_access(cid, metadata)
        
        # Get predictions
        predictions = self.predict_next_access(cid)
        
        # Extract CIDs from predictions
        candidates = [pred[0] for pred in predictions]
        
        return candidates
    
    def _is_sequential_pattern(self, cids: List[str]) -> bool:
        """Check if a sequence of CIDs follows a sequential pattern.
        
        This is a simplified check that looks for common patterns in
        sequential access like numbered files.
        
        Args:
            cids: List of content identifiers
            
        Returns:
            True if pattern appears sequential
        """
        if len(cids) < 2:
            return False
        
        # Check for common numeric patterns in filenames
        if all(cid in self.content_metadata for cid in cids):
            filenames = []
            for cid in cids:
                metadata = self.content_metadata[cid]
                filename = metadata.get("filename", "")
                if filename:
                    filenames.append(filename)
            
            if len(filenames) >= 2:
                # Check for numeric sequence in filenames
                numeric_parts = []
                for filename in filenames:
                    # Extract numeric part
                    import re
                    numbers = re.findall(r'\d+', filename)
                    if numbers:
                        numeric_parts.append(int(numbers[-1]))  # Use last number in filename
                
                if len(numeric_parts) >= 2:
                    # Check if numbers form a sequence
                    diffs = [numeric_parts[i+1] - numeric_parts[i] for i in range(len(numeric_parts)-1)]
                    # If all differences are the same and non-zero, it's a sequence
                    return len(set(diffs)) == 1 and diffs[0] != 0
        
        # If metadata approach didn't work, try CID analysis
        # Check if the same CIDs appear in access history in same order multiple times
        cid_history = [access[0] for access in self.access_history]
        pattern = tuple(cids)
        pattern_count = 0
        
        for i in range(len(cid_history) - len(pattern) + 1):
            if tuple(cid_history[i:i+len(pattern)]) == pattern:
                pattern_count += 1
        
        # If pattern appears multiple times, consider it sequential
        return pattern_count >= 2
    
    def _load_models(self) -> None:
        """Load saved models from disk."""
        if not self.config["model_storage_path"]:
            return
        
        path = self.config["model_storage_path"]
        os.makedirs(path, exist_ok=True)
        
        try:
            # Load metadata
            metadata_path = os.path.join(path, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    
                    # Check version compatibility
                    version = metadata.get("version", "0.0")
                    if version != "1.0":
                        logger.warning(f"Model version mismatch: {version} (expected 1.0)")
            
            # Load content metadata
            content_metadata_path = os.path.join(path, "content_metadata.json")
            if os.path.exists(content_metadata_path):
                with open(content_metadata_path, 'r') as f:
                    self.content_metadata = json.load(f)
            
            # TODO: Load more model-specific data
            logger.info("Loaded prediction models")
            
        except Exception as e:
            logger.error(f"Error loading prediction models: {e}")
    
    def _save_models(self) -> None:
        """Save models to disk."""
        if not self.config["model_storage_path"]:
            return
        
        path = self.config["model_storage_path"]
        os.makedirs(path, exist_ok=True)
        
        try:
            # Save metadata
            metadata_path = os.path.join(path, "metadata.json")
            with open(metadata_path, 'w') as f:
                metadata = {
                    "version": "1.0",
                    "timestamp": time.time(),
                    "config": self.config,
                    "metrics": self.metrics
                }
                json.dump(metadata, f)
            
            # Save content metadata
            content_metadata_path = os.path.join(path, "content_metadata.json")
            with open(content_metadata_path, 'w') as f:
                json.dump(self.content_metadata, f)
            
            # TODO: Save more model-specific data
            logger.info("Saved prediction models")
            
        except Exception as e:
            logger.error(f"Error saving prediction models: {e}")
    
    def shutdown(self) -> None:
        """Clean up resources and save models."""
        # Save models
        self._save_models()
        
        # Shut down thread pool
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=False)


def create_prefetching_engine(config: Optional[Dict[str, Any]] = None) -> PredictivePrefetchingEngine:
    """Create and configure a predictive prefetching engine.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured PredictivePrefetchingEngine instance
    """
    # Default configuration
    default_config = {
        "markov_enabled": True,
        "graph_enabled": True,
        "content_type_enabled": True,
        "max_prefetch_items": 10,
        "prefetch_threshold": 0.3,
    }
    
    # Merge with provided config
    final_config = default_config.copy()
    if config:
        final_config.update(config)
    
    # Create engine
    engine = PredictivePrefetchingEngine(final_config)
    
    return engine


def get_prefetch_candidates(engine: PredictivePrefetchingEngine, 
                           cid: str, 
                           metadata: Optional[Dict] = None,
                           max_items: int = 5) -> List[str]:
    """Convenience function to get prefetch candidates for a content item.
    
    Args:
        engine: Predictive prefetching engine
        cid: Content identifier
        metadata: Optional content metadata
        max_items: Maximum number of candidates to return
        
    Returns:
        List of content identifiers to prefetch
    """
    # Record access with metadata if provided
    if metadata:
        engine.record_access(cid, metadata)
    
    # Get predictions
    predictions = engine.predict_next_access(cid, max_items)
    
    # Extract CIDs from predictions
    candidates = [pred[0] for pred in predictions]
    
    return candidates
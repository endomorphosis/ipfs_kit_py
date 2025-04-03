"""
Semantic Cache for similar query results.

This module provides a semantic caching system that can identify similar queries
based on their embedding vectors and reuse search results appropriately. This
significantly improves performance for repeated or similar searches.

Key features:
1. Vector-based similarity matching for queries
2. Tiered caching with both exact and approximate matches
3. Time-based and capacity-based eviction policies
4. Configurable similarity thresholds
5. Support for partial result reuse
6. Persistence options for cache state
"""

import hashlib
import json
import logging
import os
import pickle
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

# Configure logger
logger = logging.getLogger(__name__)


class QueryVector:
    """
    Represents a query and its embedding vector for semantic comparison.
    """

    def __init__(
        self,
        query_text: Optional[str],
        query_vector: List[float],
        metadata_filters: Optional[List[Tuple[str, str, Any]]] = None,
        entity_types: Optional[List[str]] = None,
    ):
        """
        Initialize a query vector.

        Args:
            query_text: Original query text (can be None for vector-only queries)
            query_vector: Embedding vector representation of the query
            metadata_filters: Optional metadata filters used with the query
            entity_types: Optional entity types filter
        """
        self.query_text = query_text
        self.query_vector = query_vector
        self.metadata_filters = metadata_filters or []
        self.entity_types = entity_types or []
        self.vector_dim = len(query_vector) if query_vector else 0

        # Generate unique hash for exact matching
        self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate a unique hash for this query vector and its parameters."""
        # Use all query components to ensure uniqueness
        components = [
            str(self.query_text),
            str(self.query_vector),
            str(sorted(self.metadata_filters) if self.metadata_filters else []),
            str(sorted(self.entity_types) if self.entity_types else []),
        ]

        combined = "||".join(components)
        return hashlib.sha256(combined.encode()).hexdigest()

    def similarity(self, other: "QueryVector") -> float:
        """
        Calculate semantic similarity with another query vector.

        Args:
            other: Another QueryVector to compare with

        Returns:
            Similarity score between 0 and 1
        """
        # Check for exact match first (fastest)
        if self.hash == other.hash:
            return 1.0

        # Check if dimensions match
        if len(self.query_vector) != len(other.query_vector):
            return 0.0

        # Check if filters match (binary similarity component)
        filter_match = self._filter_similarity(other)

        # Calculate vector similarity (cosine similarity)
        vector_similarity = self._cosine_similarity(self.query_vector, other.query_vector)

        # Combine both components (give more weight to vector similarity)
        # 70% vector similarity, 30% filter match
        return 0.7 * vector_similarity + 0.3 * filter_match

    def _filter_similarity(self, other: "QueryVector") -> float:
        """Calculate similarity between filter sets."""
        # Check entity types overlap
        entity_match = 1.0
        if self.entity_types and other.entity_types:
            self_set = set(self.entity_types)
            other_set = set(other.entity_types)
            if not self_set.intersection(other_set):
                # No overlap in entity types means no similarity
                return 0.0

            if self_set != other_set:
                # Partial overlap
                entity_match = len(self_set.intersection(other_set)) / len(
                    self_set.union(other_set)
                )

        # Check metadata filters compatibility
        if not self.metadata_filters and not other.metadata_filters:
            filter_match = 1.0  # Both have no filters = perfect match
        elif not self.metadata_filters or not other.metadata_filters:
            filter_match = 0.5  # One has filters, other doesn't = partial match
        else:
            # Both have filters, calculate Jaccard similarity
            self_filters = set(tuple(f) for f in self.metadata_filters)
            other_filters = set(tuple(f) for f in other.metadata_filters)

            # Calculate intersection size
            intersection = len(self_filters.intersection(other_filters))
            union = len(self_filters.union(other_filters))

            filter_match = intersection / union if union > 0 else 1.0

        # Combine entity and filter match (equal weight)
        return (entity_match + filter_match) / 2

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)

        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)

        # Avoid division by zero
        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for serialization."""
        return {
            "query_text": self.query_text,
            "query_vector": self.query_vector,
            "metadata_filters": self.metadata_filters,
            "entity_types": self.entity_types,
            "hash": self.hash,
            "vector_dim": self.vector_dim,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueryVector":
        """Create a QueryVector from a dictionary."""
        query = cls(
            query_text=data["query_text"],
            query_vector=data["query_vector"],
            metadata_filters=data["metadata_filters"],
            entity_types=data["entity_types"],
        )
        # Ensure hash is preserved
        assert query.hash == data["hash"], "Hash mismatch during deserialization"
        return query


class CacheEntry:
    """
    Represents a cached result with metadata.
    """

    def __init__(
        self,
        query_vector: QueryVector,
        results: List[Dict[str, Any]],
        created_at: float = None,
        last_accessed: float = None,
        access_count: int = 0,
        ttl: int = 3600,
    ):  # Default TTL: 1 hour
        """
        Initialize a cache entry.

        Args:
            query_vector: The query vector associated with this result
            results: The search results to cache
            created_at: Timestamp of creation (defaults to now)
            last_accessed: Timestamp of last access (defaults to now)
            access_count: Number of times this entry has been accessed
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        self.query_vector = query_vector
        self.results = results
        self.created_at = created_at or time.time()
        self.last_accessed = last_accessed or time.time()
        self.access_count = access_count
        self.ttl = ttl

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > (self.created_at + self.ttl)

    def access(self) -> None:
        """Update last access time and count."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for serialization."""
        return {
            "query_vector": self.query_vector.to_dict(),
            "results": self.results,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create a CacheEntry from a dictionary."""
        return cls(
            query_vector=QueryVector.from_dict(data["query_vector"]),
            results=data["results"],
            created_at=data["created_at"],
            last_accessed=data["last_accessed"],
            access_count=data["access_count"],
            ttl=data["ttl"],
        )


class SemanticCache:
    """
    Cache for storing and retrieving search results based on semantic similarity.

    This cache intelligently reuses search results for semantically similar queries,
    improving performance and reducing redundant computation.
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        similarity_threshold: float = 0.85,
        max_size: int = 1000,
        ttl: int = 3600,
        persistence_enabled: bool = True,
        persistence_interval: int = 300,
    ):
        """
        Initialize the semantic cache.

        Args:
            cache_dir: Directory for cache persistence (if None, uses ~/.ipfs_cache/semantic)
            embedding_fn: Function to generate embeddings from text (needed for text queries)
            similarity_threshold: Minimum similarity score to consider a cache hit
            max_size: Maximum number of entries to keep in cache
            ttl: Default time-to-live for cache entries in seconds
            persistence_enabled: Whether to persist cache to disk
            persistence_interval: How often to persist cache (seconds)
        """
        # Cache directory setup
        if cache_dir is None:
            home_dir = str(Path.home())
            self.cache_dir = os.path.join(home_dir, ".ipfs_cache", "semantic")
        else:
            self.cache_dir = os.path.expanduser(cache_dir)

        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)

        # Cache parameters
        self.embedding_fn = embedding_fn
        self.similarity_threshold = similarity_threshold
        self.max_size = max_size
        self.default_ttl = ttl

        # Cache storage
        self.exact_cache = OrderedDict()  # Hash-based exact match cache (O(1) lookup)
        self.vector_cache = []  # List of entries for vector similarity search

        # Lock for thread safety
        self._lock = threading.RLock()

        # Persistence settings
        self.persistence_enabled = persistence_enabled
        self.persistence_interval = persistence_interval
        self.persistence_path = os.path.join(self.cache_dir, "semantic_cache.pkl")

        # Load existing cache if available
        self._load_cache()

        # Set up periodic persistence if enabled
        if persistence_enabled and persistence_interval > 0:
            self._setup_persistence_timer()

    def _setup_persistence_timer(self) -> None:
        """Set up timer for periodic cache persistence."""

        def persist_and_reschedule():
            """Persist cache and reschedule next persistence."""
            self.persist()

            # Reschedule if still enabled
            if self.persistence_enabled:
                threading.Timer(self.persistence_interval, persist_and_reschedule).start()

        # Start the timer
        threading.Timer(self.persistence_interval, persist_and_reschedule).start()

    def _load_cache(self) -> None:
        """Load cache from persistent storage."""
        if not os.path.exists(self.persistence_path):
            return

        try:
            with open(self.persistence_path, "rb") as f:
                cache_data = pickle.load(f)

            # Validate and load the cache data
            if not isinstance(cache_data, dict):
                logger.warning("Invalid cache data format, ignoring")
                return

            exact_entries = cache_data.get("exact_cache", {})
            vector_entries = cache_data.get("vector_cache", [])

            # Clear current cache
            with self._lock:
                self.exact_cache.clear()
                self.vector_cache.clear()

                # Load exact cache entries
                for hash_key, entry_dict in exact_entries.items():
                    try:
                        entry = CacheEntry.from_dict(entry_dict)
                        if not entry.is_expired():
                            self.exact_cache[hash_key] = entry
                    except Exception as e:
                        logger.warning(f"Error loading cache entry: {e}")

                # Load vector cache entries
                for entry_dict in vector_entries:
                    try:
                        entry = CacheEntry.from_dict(entry_dict)
                        if not entry.is_expired():
                            self.vector_cache.append(entry)
                    except Exception as e:
                        logger.warning(f"Error loading cache entry: {e}")

            logger.info(
                f"Loaded {len(self.exact_cache)} exact and {len(self.vector_cache)} vector cache entries"
            )

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")

    def persist(self) -> bool:
        """
        Persist the cache to disk.

        Returns:
            True if successful, False otherwise
        """
        if not self.persistence_enabled:
            return False

        try:
            # Prepare serializable cache data
            with self._lock:
                # Convert exact_cache OrderedDict to dictionary
                exact_cache_dict = {}
                for hash_key, entry in self.exact_cache.items():
                    exact_cache_dict[hash_key] = entry.to_dict()

                # Convert vector_cache entries to dictionaries
                vector_cache_list = [entry.to_dict() for entry in self.vector_cache]

                cache_data = {
                    "exact_cache": exact_cache_dict,
                    "vector_cache": vector_cache_list,
                    "timestamp": time.time(),
                }

            # Write to temporary file first
            temp_path = f"{self.persistence_path}.tmp"
            with open(temp_path, "wb") as f:
                pickle.dump(cache_data, f)

            # Rename to final path (atomic operation)
            os.replace(temp_path, self.persistence_path)

            logger.debug(
                f"Cache persisted with {len(self.exact_cache)} exact and {len(self.vector_cache)} vector entries"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to persist cache: {e}")
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self.exact_cache.clear()
            self.vector_cache.clear()
            logger.info("Cache cleared")

    def _evict_if_needed(self) -> None:
        """Evict entries if cache is over capacity."""
        with self._lock:
            total_entries = len(self.exact_cache) + len(self.vector_cache)

            if total_entries <= self.max_size:
                return

            # Calculate how many entries to evict
            to_evict = total_entries - self.max_size

            logger.debug(f"Cache over capacity, evicting {to_evict} entries")

            # Strategy: evict expired entries first, then least recently used
            # First, evict expired entries from exact cache
            expired_keys = [k for k, v in self.exact_cache.items() if v.is_expired()]
            for key in expired_keys:
                del self.exact_cache[key]
                to_evict -= 1

            if to_evict <= 0:
                return

            # Next, evict expired entries from vector cache
            self.vector_cache = [entry for entry in self.vector_cache if not entry.is_expired()]
            to_evict = total_entries - self.max_size - (len(expired_keys))

            if to_evict <= 0:
                return

            # If we still need to evict, use LRU strategy on exact cache
            while to_evict > 0 and self.exact_cache:
                # OrderedDict maintains insertion order, so first item is oldest
                self.exact_cache.popitem(last=False)
                to_evict -= 1

            if to_evict <= 0:
                return

            # Finally, evict from vector cache based on last accessed time
            if to_evict > 0 and self.vector_cache:
                # Sort by last_accessed (oldest first)
                self.vector_cache.sort(key=lambda entry: entry.last_accessed)

                # Remove oldest entries
                self.vector_cache = self.vector_cache[to_evict:]

    def put(
        self,
        query_text: Optional[str],
        query_vector: Optional[List[float]],
        results: List[Dict[str, Any]],
        metadata_filters: Optional[List[Tuple[str, str, Any]]] = None,
        entity_types: Optional[List[str]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Store search results in the cache.

        Args:
            query_text: Original query text (can be None for vector-only queries)
            query_vector: Query embedding vector (required)
            results: Search results to cache
            metadata_filters: Metadata filters used with the query
            entity_types: Entity types filters used with the query
            ttl: Time-to-live for this entry (uses default if None)

        Returns:
            True if stored successfully, False otherwise
        """
        # Handle vector generation if needed
        if query_vector is None:
            if query_text is None or not self.embedding_fn:
                logger.warning("Cannot cache: no query vector and no way to generate one")
                return False

            try:
                query_vector = self.embedding_fn(query_text)
            except Exception as e:
                logger.error(f"Failed to generate embedding for cache: {e}")
                return False

        # Create query vector and cache entry
        query_vec = QueryVector(
            query_text=query_text,
            query_vector=query_vector,
            metadata_filters=metadata_filters,
            entity_types=entity_types,
        )

        entry = CacheEntry(query_vector=query_vec, results=results, ttl=ttl or self.default_ttl)

        # Store in cache
        with self._lock:
            # Store in exact cache by hash
            self.exact_cache[query_vec.hash] = entry

            # Also store in vector cache for similarity search
            self.vector_cache.append(entry)

            # Evict if over capacity
            self._evict_if_needed()

        logger.debug(f"Cached results for query: {query_text or 'vector-only'}")
        return True

    def get(
        self,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        metadata_filters: Optional[List[Tuple[str, str, Any]]] = None,
        entity_types: Optional[List[str]] = None,
        similarity_threshold: Optional[float] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve results from cache based on query similarity.

        Args:
            query_text: Query text to search for
            query_vector: Query vector to search for
            metadata_filters: Metadata filters for the query
            entity_types: Entity types filter
            similarity_threshold: Override default similarity threshold

        Returns:
            Cached results if found with sufficient similarity, None otherwise
        """
        # Use provided threshold or default
        threshold = similarity_threshold or self.similarity_threshold

        # Handle vector generation if needed
        if query_vector is None:
            if query_text is None or not self.embedding_fn:
                logger.warning("Cannot search cache: no query vector and no way to generate one")
                return None

            try:
                query_vector = self.embedding_fn(query_text)
            except Exception as e:
                logger.error(f"Failed to generate embedding for cache lookup: {e}")
                return None

        # Create query vector for lookup
        query_vec = QueryVector(
            query_text=query_text,
            query_vector=query_vector,
            metadata_filters=metadata_filters,
            entity_types=entity_types,
        )

        with self._lock:
            # Try exact match first (by hash)
            if query_vec.hash in self.exact_cache:
                entry = self.exact_cache[query_vec.hash]

                # Check if expired
                if entry.is_expired():
                    # Remove from cache
                    del self.exact_cache[query_vec.hash]
                    self.vector_cache = [
                        e for e in self.vector_cache if e.query_vector.hash != query_vec.hash
                    ]
                    return None

                # Update access stats
                entry.access()

                # Move to end of OrderedDict to mark as recently used
                self.exact_cache.move_to_end(query_vec.hash)

                logger.debug(f"Exact cache hit for query: {query_text or 'vector-only'}")
                return entry.results

            # Try semantic match
            best_match = None
            best_similarity = 0.0

            for entry in self.vector_cache:
                # Skip expired entries
                if entry.is_expired():
                    continue

                # Calculate similarity
                similarity = query_vec.similarity(entry.query_vector)

                # Update best match if better
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = entry

            # Check if best match exceeds threshold
            if best_match and best_similarity >= threshold:
                # Update access stats
                best_match.access()

                logger.debug(
                    f"Semantic cache hit (similarity: {best_similarity:.4f}) for query: {query_text or 'vector-only'}"
                )
                return best_match.results

        # No match found
        logger.debug(f"Cache miss for query: {query_text or 'vector-only'}")
        return None

    def contains(
        self,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        metadata_filters: Optional[List[Tuple[str, str, Any]]] = None,
        entity_types: Optional[List[str]] = None,
        similarity_threshold: Optional[float] = None,
    ) -> bool:
        """
        Check if a similar query is in the cache.

        Args:
            query_text: Query text to check
            query_vector: Query vector to check
            metadata_filters: Metadata filters for the query
            entity_types: Entity types filter
            similarity_threshold: Override default similarity threshold

        Returns:
            True if a similar query is in the cache, False otherwise
        """
        results = self.get(
            query_text=query_text,
            query_vector=query_vector,
            metadata_filters=metadata_filters,
            entity_types=entity_types,
            similarity_threshold=similarity_threshold,
        )

        return results is not None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            exact_count = len(self.exact_cache)
            vector_count = len(self.vector_cache)

            # Count expired entries
            exact_expired = sum(1 for entry in self.exact_cache.values() if entry.is_expired())
            vector_expired = sum(1 for entry in self.vector_cache if entry.is_expired())

            # Calculate memory usage (approximate)
            import sys

            exact_size = sys.getsizeof(self.exact_cache)
            vector_size = sys.getsizeof(self.vector_cache)

            for entry in self.exact_cache.values():
                exact_size += sys.getsizeof(entry.results) + sys.getsizeof(
                    entry.query_vector.query_vector
                )

            for entry in self.vector_cache:
                vector_size += sys.getsizeof(entry.results) + sys.getsizeof(
                    entry.query_vector.query_vector
                )

            return {
                "exact_cache_entries": exact_count,
                "exact_cache_expired": exact_expired,
                "vector_cache_entries": vector_count,
                "vector_cache_expired": vector_expired,
                "total_entries": exact_count + vector_count,
                "approx_memory_usage_bytes": exact_size + vector_size,
                "similarity_threshold": self.similarity_threshold,
                "max_size": self.max_size,
                "default_ttl": self.default_ttl,
                "persistence_enabled": self.persistence_enabled,
                "persistence_path": self.persistence_path,
            }

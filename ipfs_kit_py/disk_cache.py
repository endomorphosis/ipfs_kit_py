
import os
import time
import json
import logging
import hashlib
import math
import threading
import shutil
from typing import Dict, Any, Optional, Tuple, List, Union

from .api_stability import experimental_api, beta_api, stable_api

logger = logging.getLogger(__name__)

class DiskCache:
    """Disk-based persistent cache for IPFS content.

    This cache stores content on disk with proper indexing and size management.
    It uses a simple directory structure with content-addressed files.
    """

    def __init__(self, directory: str = "~/.ipfs_cache", size_limit: int = 1 * 1024 * 1024 * 1024):
        """Initialize the disk cache.

        Args:
            directory: Directory to store cached files
            size_limit: Maximum size of the cache in bytes (default: 1GB)
        """
        self.directory = os.path.expanduser(directory)
        self.size_limit = size_limit
        self.index_file = os.path.join(self.directory, "cache_index.json")
        self.metadata_dir = os.path.join(self.directory, "metadata")
        self.index = {}
        self.current_size = 0
        self._metadata = {}  # Internal metadata storage

        # Create cache directories if they don't exist
        os.makedirs(self.directory, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)

        # Load existing index
        self._load_index()

        # Verify cache integrity
        self._verify_cache()
        
    @property
    def metadata(self):
        """Access to the metadata dictionary.
        
        Returns:
            Dict containing metadata for all cache entries
        """
        return self._metadata
        
    @property
    def index_path(self):
        """Path to the index file.
        
        Returns:
            String path to the index file
        """
        return self.index_file

    def _load_index(self) -> None:
        """Load the cache index from disk."""
        try:
            if os.path.exists(self.index_file):
                import json

                with open(self.index_file, "r") as f:
                    data = json.load(f)
                    # Validate index data to ensure it's a dict of dict entries
                    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                        self.index = data
                        logger.debug(f"Loaded cache index with {len(self.index)} entries")
                    else:
                        logger.warning(f"Invalid cache index format - creating new index")
                        self.index = {}
            else:
                self.index = {}
                logger.debug("No existing cache index found, creating new one")
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
            self.index = {}

    def _save_index(self) -> None:
        """Save the cache index to disk."""
        try:
            import json

            with open(self.index_file, "w") as f:
                json.dump(self.index, f)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")

    def _verify_cache(self) -> None:
        """Verify cache integrity and recalculate size."""
        valid_entries = {}
        calculated_size = 0

        # If index is empty or has no entries yet, just return
        if not self.index:
            return

        for key, entry in self.index.items():
            # Skip entries without a filename (shouldn't happen but check to be safe)
            if "filename" not in entry:
                logger.warning(f"Cache entry {key} missing filename field")
                continue

            file_path = os.path.join(self.directory, entry["filename"])
            if os.path.exists(file_path):
                # Update file size in case it changed
                actual_size = os.path.getsize(file_path)
                entry["size"] = actual_size
                valid_entries[key] = entry
                calculated_size += actual_size
            else:
                logger.warning(f"Cache entry {key} points to missing file {entry['filename']}")

        # Update index and size
        self.index = valid_entries
        self.current_size = calculated_size

        logger.debug(
            f"Cache verification complete: {len(self.index)} valid entries, {self.current_size} bytes"
        )

    def _get_cache_path(self, key: str) -> str:
        """Get the path to the cached file for a key."""
        if key not in self.index:
            return None

        filename = self.index[key]["filename"]
        return os.path.join(self.directory, filename)

    def _get_metadata_path(self, key: str) -> str:
        """Get the path to the metadata file for a key."""
        return os.path.join(self.metadata_dir, f"{key.replace('/', '_')}.json")

    def get(self, key: str) -> Optional[bytes]:
        """Get content from the cache.

        Args:
            key: CID or identifier of the content

        Returns:
            Content if found, None otherwise
        """
        if key not in self.index:
            return None

        entry = self.index[key]
        file_path = os.path.join(self.directory, entry["filename"])

        try:
            # Check if file still exists
            if not os.path.exists(file_path):
                logger.warning(f"Cache entry exists but file missing: {file_path}")
                del self.index[key]
                self._save_index()
                return None

            # Update access time
            entry["last_access"] = time.time()
            entry["access_count"] = entry.get("access_count", 0) + 1

            # Read the file
            with open(file_path, "rb") as f:
                content = f.read()

            # Update index
            self._save_index()

            return content

        except Exception as e:
            logger.error(f"Error reading from disk cache: {e}")
            return None

    def put(self, key: str, value: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store content in the cache.

        Args:
            key: CID or identifier of the content
            value: Content to store
            metadata: Additional metadata to store with the content

        Returns:
            True if stored successfully, False otherwise
        """
        if not isinstance(value, bytes):
            logger.warning(f"Cache only accepts bytes, got {type(value)}")
            return False

        value_size = len(value)

        # Don't cache items larger than the max cache size
        if value_size > self.size_limit:
            logger.warning(f"Item size ({value_size}) exceeds cache capacity ({self.size_limit})")
            return False

        # Make room if needed
        if self.current_size + value_size > self.size_limit:
            self._make_room(value_size)

        # Generate a filename based on the key
        filename = f"{key.replace('/', '_')}.bin"
        if len(filename) > 255:  # Avoid filename length issues
            filename = f"{key[:10]}_{uuid.uuid4()}_{key[-10:]}.bin"

        file_path = os.path.join(self.directory, filename)
        metadata_path = self._get_metadata_path(key)

        try:
            # Write the file
            with open(file_path, "wb") as f:
                f.write(value)

            # Update index
            current_time = time.time()
            self.index[key] = {
                "filename": filename,
                "size": value_size,
                "added": current_time,
                "last_access": current_time,
                "access_count": 1,
                "metadata": metadata or {},
            }
            
            # Update in-memory metadata for tests
            self._metadata[key] = metadata or {}

            # Save metadata to separate file for better access
            if metadata:
                try:
                    import json

                    with open(metadata_path, "w") as f:
                        json.dump(metadata, f)
                except Exception as e:
                    logger.error(f"Error saving metadata for {key}: {e}")

            # Update current size
            self.current_size += value_size

            # Save index
            self._save_index()

            return True

        except Exception as e:
            logger.error(f"Error writing to disk cache: {e}")
            # Clean up partial file if it exists
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return False

    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a cached item.

        Args:
            key: CID or identifier of the content

        Returns:
            Metadata dictionary if found, None otherwise
        """
        if key not in self.index:
            return None
            
        # First check in-memory metadata
        if key in self._metadata:
            return self._metadata[key]

        # Try to get metadata from separate file next
        metadata_path = self._get_metadata_path(key)
        if os.path.exists(metadata_path):
            try:
                import json

                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    # Cache in memory for next time
                    self._metadata[key] = metadata
                    return metadata
            except Exception as e:
                logger.error(f"Error reading metadata from file for {key}: {e}")

        # Fall back to metadata stored in index
        metadata = self.index[key].get("metadata", {})
        # Cache in memory for next time
        self._metadata[key] = metadata
        return metadata

    def _make_room(self, required_size: int) -> None:
        """Make room in the cache by evicting entries.

        Args:
            required_size: Size of the item that needs space
        """
        # If the cache is empty or we need more space than the entire cache,
        # just clear everything
        if not self.index or required_size > self.size_limit:
            self.clear()
            return

        # Calculate how much space we need to free
        space_to_free = self.current_size + required_size - self.size_limit

        # Sort entries by heat score (combination of recency and frequency)
        def heat_score(entry):
            age = time.time() - entry["added"]
            recency = 1.0 / (1.0 + (time.time() - entry["last_access"]) / 86400)  # Decay over days
            frequency = entry.get("access_count", 1)
            return (
                frequency * recency / math.sqrt(1 + age / 86400)
            )  # Decrease score with age (sqrt to make it less aggressive)

        sorted_entries = sorted(
            [(k, v) for k, v in self.index.items()], key=lambda x: heat_score(x[1])
        )

        # Evict entries until we have enough space
        freed_space = 0
        evicted_count = 0

        for key, entry in sorted_entries:
            if freed_space >= space_to_free:
                break

            # Delete the file
            file_path = os.path.join(self.directory, entry["filename"])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing cache file {file_path}: {e}")

            # Delete metadata file if it exists
            metadata_path = self._get_metadata_path(key)
            try:
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
            except Exception as e:
                logger.error(f"Error removing metadata file {metadata_path}: {e}")

            # Update tracking
            freed_space += entry["size"]
            self.current_size -= entry["size"]
            evicted_count += 1

            # Remove from index
            del self.index[key]

        logger.debug(
            f"Made room in cache by evicting {evicted_count} entries, freed {freed_space} bytes"
        )

        # Save updated index
        self._save_index()

    def contains(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: CID or identifier of the content

        Returns:
            True if the key exists, False otherwise
        """
        if key not in self.index:
            return False

        # Verify the file actually exists
        file_path = os.path.join(self.directory, self.index[key]["filename"])
        return os.path.exists(file_path)

    def clear(self) -> None:
        """Clear the cache completely."""
        # Delete all cache files
        for entry in self.index.values():
            file_path = os.path.join(self.directory, entry["filename"])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing cache file {file_path}: {e}")

        # Delete all metadata files
        for key in self.index:
            metadata_path = self._get_metadata_path(key)
            try:
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
            except Exception as e:
                logger.error(f"Error removing metadata file {metadata_path}: {e}")

        # Reset index and size
        self.index = {}
        self.current_size = 0

        # Save empty index
        self._save_index()

        logger.debug("Cache cleared completely")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        # Count by file type
        type_counts = {}
        for entry in self.index.values():
            file_type = entry.get("metadata", {}).get("mimetype", "unknown")
            if file_type not in type_counts:
                type_counts[file_type] = 0
            type_counts[file_type] += 1

        # Get age distribution
        current_time = time.time()
        age_distribution = {
            "under_1hour": 0,
            "1hour_to_1day": 0,
            "1day_to_1week": 0,
            "over_1week": 0,
        }

        for entry in self.index.values():
            age = current_time - entry["added"]
            if age < 3600:  # 1 hour
                age_distribution["under_1hour"] += 1
            elif age < 86400:  # 1 day
                age_distribution["1hour_to_1day"] += 1
            elif age < 604800:  # 1 week
                age_distribution["1day_to_1week"] += 1
            else:
                age_distribution["over_1week"] += 1

        return {
            "size_limit": self.size_limit,
            "current_size": self.current_size,
            "utilization": self.current_size / self.size_limit if self.size_limit > 0 else 0,
            "entry_count": len(self.index),
            "by_type": type_counts,
            "age_distribution": age_distribution,
            "directory": self.directory,
        }


    @experimental_api(since="0.19.0")
    def async_batch_get_metadata(self, cids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Async version of batch_get_metadata.
        
        Asynchronously retrieve metadata for multiple CIDs in a batch operation for improved efficiency.
        This method builds on the batch_get_metadata functionality but is non-blocking.
        
        Args:
            cids: List of CIDs to retrieve metadata for
            
        Returns:
            Dictionary mapping CIDs to their metadata
        """
        if not self.has_asyncio:
            # Fallback to synchronous version through thread pool if asyncio not available
            future = self.thread_pool.submit(self.batch_get_metadata, cids)
            return future.result()
            
        async def _async_impl():
            # This implementation delegates to the batch version but in a non-blocking way
            return self.batch_get_metadata(cids)
            
        # If we're called from an async context, return awaitable
        if self.loop and self.loop.is_running():
            return anyio.create_task(_async_impl())
            
        # If we're called from a synchronous context but asyncio is available,
        # run the async function to completion
        try:
            loop = anyio.get_event_loop()
            return loop.run_until_complete(_async_impl())
        except RuntimeError:
            # No event loop in this thread, create one temporarily
            loop = anyio.new_event_loop()
            anyio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_async_impl())
            finally:
                loop.close()
                
    @experimental_api(since="0.19.0")
    def async_batch_put_metadata(self, metadata_dict: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Async version of batch_put_metadata.
        
        Asynchronously store metadata for multiple CIDs in a batch operation for improved efficiency.
        
        Args:
            metadata_dict: Dictionary mapping CIDs to their metadata
            
        Returns:
            Dictionary mapping CIDs to success status
        """
        if not self.has_asyncio:
            # Fallback to synchronous version through thread pool if asyncio not available
            future = self.thread_pool.submit(self.batch_put_metadata, metadata_dict)
            return future.result()
            
        async def _async_impl():
            # This implementation delegates to the batch version but in a non-blocking way
            return self.batch_put_metadata(metadata_dict)
            
        # If we're called from an async context, return awaitable
        if self.loop and self.loop.is_running():
            return anyio.create_task(_async_impl())
            
        # If we're called from a synchronous context but asyncio is available,
        # run the async function to completion
        try:
            loop = anyio.get_event_loop()
            return loop.run_until_complete(_async_impl())
        except RuntimeError:
            # No event loop in this thread, create one temporarily
            loop = anyio.new_event_loop()
            anyio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_async_impl())
            finally:
                loop.close()
    
    @beta_api(since="0.19.0")
    def optimize_compression_settings(self, adaptive: bool = True) -> Dict[str, Any]:
        """Optimize compression settings based on data characteristics and available resources.
        
        This method analyzes the existing data, system resources, and access patterns to 
        determine the optimal compression settings for the Parquet files. It can significantly
        improve both storage efficiency and access performance.
        
        Args:
            adaptive: If True, uses system resource information to adapt settings
            
        Returns:
            Dictionary with optimization results
        """
        result = {
            "success": False,
            "operation": "optimize_compression_settings",
            "timestamp": time.time()
        }
        
        try:
            # Get current partition information
            total_rows = 0
            total_size = 0
            for partition_id, info in self.partitions.items():
                total_rows += info.get("rows", 0) or 0
                total_size += info.get("size", 0) or 0
                
            # Skip if we don't have enough data
            if total_rows < 1000:
                result["success"] = True
                result["skipped"] = True
                result["reason"] = f"Not enough data ({total_rows} rows)"
                return result
                
            # Get system resource information if adaptive
            if adaptive:
                try:
                    import psutil
                    # Check available system memory and CPU
                    mem = psutil.virtual_memory()
                    cpu_count = psutil.cpu_count(logical=False) or 1
                    
                    # Determine if we're on a resource-constrained device
                    is_constrained = mem.total < 4 * 1024 * 1024 * 1024 or cpu_count < 2
                    
                    # Select strategy based on resources
                    if is_constrained:
                        strategy = "speed"  # Optimize for speed on constrained devices
                    else:
                        strategy = "balanced"  # Use balanced approach on well-equipped systems
                    
                    # Adjust compression level based on CPU cores
                    compression_level = min(5, max(1, cpu_count - 1))
                    
                    # Calculate dictionary size based on available memory
                    dict_size = min(2 * 1024 * 1024, mem.total // 200)  # Use at most 0.5% of memory
                    
                except ImportError:
                    # Fall back to balanced approach if psutil not available
                    strategy = "balanced"
                    compression_level = 3
                    dict_size = 1024 * 1024
            else:
                # Use current settings if not adaptive
                strategy = self.compression_optimization
                compression_level = 3
                dict_size = 1024 * 1024
            
            # Create new compression config
            new_config = {
                "compression": "zstd",
                "compression_level": compression_level,
                "use_dictionary": True,
                "dictionary_pagesize_limit": dict_size,
                "data_page_size": 2 * 1024 * 1024,
                "use_byte_stream_split": True if strategy != "speed" else False,
                "column_encoding": {},
                "stats": {
                    "total_rows": total_rows,
                    "total_size": total_size,
                    "strategy": strategy,
                    "adaptive": adaptive
                }
            }
            
            # Analyze column characteristics if we have in-memory data
            if self.in_memory_batch:
                table = pa.Table.from_batches([self.in_memory_batch])
                # Get optimized encodings for each column
                for i, field in enumerate(table.schema):
                    col_name = field.name
                    col = table.column(i)
                    
                    if pa.types.is_string(field.type):
                        # String columns: check cardinality
                        try:
                            distinct_count = len(set(col.to_pandas()))
                            total_count = len(col)
                            cardinality_ratio = distinct_count / total_count if total_count > 0 else 1.0
                            
                            # Low cardinality: use dictionary encoding
                            if cardinality_ratio < 0.3:
                                new_config["column_encoding"][col_name] = {
                                    "use_dictionary": True,
                                    "encoding": "PLAIN_DICTIONARY"
                                }
                            # High cardinality: use plain encoding
                            else:
                                new_config["column_encoding"][col_name] = {
                                    "use_dictionary": False,
                                    "encoding": "PLAIN"
                                }
                        except Exception as e:
                            # Default to dictionary encoding on error
                            logger.warning(f"Error analyzing column {col_name}: {e}")
                            new_config["column_encoding"][col_name] = {
                                "use_dictionary": True,
                                "encoding": "PLAIN_DICTIONARY"
                            }
                    
                    elif pa.types.is_integer(field.type) or pa.types.is_floating(field.type):
                        # Numeric columns: use byte_stream_split for better compression
                        new_config["column_encoding"][col_name] = {
                            "use_dictionary": False,
                            "encoding": "BYTE_STREAM_SPLIT" if strategy != "speed" else "PLAIN"
                        }
                    
                    elif pa.types.is_boolean(field.type):
                        # Boolean columns: always use run-length encoding
                        new_config["column_encoding"][col_name] = {
                            "use_dictionary": False,
                            "encoding": "RLE"
                        }
                    
                    elif pa.types.is_timestamp(field.type):
                        # Timestamp columns: use dictionary for better compression if low cardinality
                        try:
                            distinct_count = len(set(col.to_pandas()))
                            total_count = len(col)
                            cardinality_ratio = distinct_count / total_count if total_count > 0 else 1.0
                            
                            if cardinality_ratio < 0.1:  # Very low cardinality
                                new_config["column_encoding"][col_name] = {
                                    "use_dictionary": True,
                                    "encoding": "PLAIN_DICTIONARY"
                                }
                            else:
                                # Otherwise use delta encoding for timestamps
                                new_config["column_encoding"][col_name] = {
                                    "use_dictionary": False,
                                    "encoding": "DELTA_BINARY_PACKED"
                                }
                        except Exception as e:
                            # Default to delta encoding on error
                            logger.warning(f"Error analyzing column {col_name}: {e}")
                            new_config["column_encoding"][col_name] = {
                                "use_dictionary": False,
                                "encoding": "DELTA_BINARY_PACKED"
                            }
            
            # Update the default compression config
            self.default_compression_config = new_config
            
            # Set success and return results
            result["success"] = True
            result["optimized_config"] = new_config
            result["data_analyzed"] = bool(self.in_memory_batch)
            
            logger.info(f"Optimized compression settings: {strategy} strategy with level {compression_level}")
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error optimizing compression settings: {e}")
        
        return result
    
    @experimental_api(since="0.19.0")
    async def async_optimize_compression_settings(self, adaptive: bool = True) -> Dict[str, Any]:
        """Async version of optimize_compression_settings.
        
        Args:
            adaptive: If True, uses system resource information to adapt settings
            
        Returns:
            Dictionary with optimization results
        """
        if not self.has_asyncio:
            # Fallback to synchronous version through thread pool if asyncio not available
            future = self.thread_pool.submit(self.optimize_compression_settings, adaptive)
            return future.result()
            
        # If asyncio is available, run in executor to avoid blocking
        loop = anyio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, 
            lambda: self.optimize_compression_settings(adaptive)
        )
    
    @beta_api(since="0.19.0")
    def optimize_batch_operations(self, content_type_aware: bool = True) -> Dict[str, Any]:
        """Optimize batch operations for different content types.
        
        This method configures batch operations to be optimized for different content types,
        enabling more efficient processing based on the characteristics of the data.
        
        Args:
            content_type_aware: Whether to enable content type-specific optimizations
            
        Returns:
            Dictionary with optimization results
        """
        result = {
            "success": False,
            "operation": "optimize_batch_operations",
            "timestamp": time.time(),
            "optimizations": {}
        }
        
        try:
            # Initialize content type registry if not already done
            if not hasattr(self, "content_type_registry"):
                self.content_type_registry = {}
                
            # Content type-specific optimizations
            optimizations = {
                # Image data
                "image": {
                    "batch_size": 20,          # Process fewer images at once due to size
                    "prefetch_strategy": "metadata_first",  # First fetch metadata, then content
                    "compression": "snappy",   # Fast compression for binary data
                    "chunk_size": 1024 * 1024  # 1MB chunks
                },
                
                # Text data
                "text": {
                    "batch_size": 100,         # Can process more text files at once
                    "prefetch_strategy": "content_first",  # Fetch content directly
                    "compression": "zstd",     # Better compression for text
                    "chunk_size": 256 * 1024   # 256KB chunks
                },
                
                # JSON data
                "json": {
                    "batch_size": 50,          # Moderate batch size
                    "prefetch_strategy": "metadata_first",  # Fetch metadata before content
                    "compression": "zstd",     # Good compression for structured text
                    "chunk_size": 512 * 1024   # 512KB chunks
                },
                
                # Video data
                "video": {
                    "batch_size": 5,           # Very small batch size due to large files
                    "prefetch_strategy": "sequential_chunks",  # Fetch in sequential chunks
                    "compression": "snappy",   # Fast compression for binary data
                    "chunk_size": 4 * 1024 * 1024  # 4MB chunks
                },
                
                # Audio data
                "audio": {
                    "batch_size": 10,          # Small batch size for audio files
                    "prefetch_strategy": "sequential_chunks",  # Fetch in sequential chunks
                    "compression": "snappy",   # Fast compression for binary data
                    "chunk_size": 2 * 1024 * 1024  # 2MB chunks
                },
                
                # Default for unknown types
                "default": {
                    "batch_size": 30,          # Moderate batch size
                    "prefetch_strategy": "content_first",  # Direct content fetch
                    "compression": "zstd",     # Good general-purpose compression
                    "chunk_size": 1024 * 1024  # 1MB chunks
                }
            }
            
            # Register content type patterns if content_type_aware
            if content_type_aware:
                # Update/initialize the content type patterns
                content_type_patterns = {
                    # Image formats
                    "image": [
                        r"image/.*",
                        r".*\.(jpg|jpeg|png|gif|bmp|webp|tiff|svg)$"
                    ],
                    
                    # Text formats
                    "text": [
                        r"text/.*",
                        r".*\.(txt|md|rst|log|csv|tsv)$"
                    ],
                    
                    # JSON formats
                    "json": [
                        r"application/json",
                        r".*\.(json|jsonl|geojson)$"
                    ],
                    
                    # Video formats
                    "video": [
                        r"video/.*",
                        r".*\.(mp4|mkv|avi|mov|webm|flv)$"
                    ],
                    
                    # Audio formats
                    "audio": [
                        r"audio/.*",
                        r".*\.(mp3|wav|ogg|flac|aac)$"
                    ]
                }
                
                # Register patterns for content type detection
                self.content_type_registry = {
                    "patterns": content_type_patterns,
                    "optimizations": optimizations
                }
                
                # Function to determine content type from metadata
                def detect_content_type(metadata):
                    """Detect content type from metadata."""
                    if not metadata:
                        return "default"
                        
                    # Try MIME type first
                    mimetype = metadata.get("mimetype", "")
                    if mimetype:
                        for type_name, patterns in content_type_patterns.items():
                            for pattern in patterns:
                                if re.match(pattern, mimetype):
                                    return type_name
                    
                    # Try filename/extension next
                    filename = metadata.get("filename", "")
                    if filename:
                        for type_name, patterns in content_type_patterns.items():
                            for pattern in patterns:
                                if re.match(pattern, filename):
                                    return type_name
                    
                    # Default if no match
                    return "default"
                
                # Register the detection function
                self.detect_content_type = detect_content_type
                
                # Create a helper function for batch operations
                def optimize_batch(items, metadata_dict=None):
                    """Split a batch into optimized sub-batches by content type."""
                    if not metadata_dict or not content_type_aware:
                        return {"default": items}
                        
                    # Group items by detected content type
                    batches = {}
                    for item in items:
                        metadata = metadata_dict.get(item, {})
                        content_type = detect_content_type(metadata)
                        
                        if content_type not in batches:
                            batches[content_type] = []
                            
                        batches[content_type].append(item)
                        
                    return batches
                
                # Register the batch optimization function
                self.optimize_batch = optimize_batch
                
                # Update result with content type information
                result["content_type_patterns"] = content_type_patterns
            
            # Store the optimizations
            self.batch_optimizations = optimizations
            
            # Register success
            result["success"] = True
            result["optimizations"] = optimizations
            result["content_type_aware"] = content_type_aware
            
            logger.info(f"Batch operations optimized with content-type awareness: {content_type_aware}")
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error optimizing batch operations: {e}")
        
        return result
    
    @experimental_api(since="0.19.0")
    async def async_optimize_batch_operations(self, content_type_aware: bool = True) -> Dict[str, Any]:
        """Async version of optimize_batch_operations.
        
        Args:
            content_type_aware: Whether to enable content type-specific optimizations
            
        Returns:
            Dictionary with optimization results
        """
        if not self.has_asyncio:
            # Fallback to synchronous version through thread pool if asyncio not available
            future = self.thread_pool.submit(self.optimize_batch_operations, content_type_aware)
            return future.result()
            
        # If asyncio is available, run in executor to avoid blocking
        loop = anyio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, 
            lambda: self.optimize_batch_operations(content_type_aware)
        )
    
    @beta_api(since="0.19.0")
    def batch_prefetch(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Prefetch multiple CIDs in a batch operation for improved efficiency.
        
        This method implements content type-specific batch prefetching optimizations,
        grouping content by type and applying optimized strategies for each. This
        significantly improves performance compared to individual prefetch operations.
        
        Args:
            cids: List of CIDs to prefetch
            metadata: Optional metadata for each CID to optimize prefetching strategy
            
        Returns:
            Dictionary with prefetch operation results
        """
        # Basic validation
        if not cids:
            return {"success": False, "error": "No CIDs provided"}
            
        # Initialize result
        result = {
            "success": True,
            "operation": "batch_prefetch",
            "timestamp": time.time(),
            "total_cids": len(cids),
            "prefetched": 0,
            "skipped": 0,
            "failed": 0,
            "content_types": {},
            "results": {}
        }
        
        try:
            # Determine if we have content type awareness
            has_content_types = (hasattr(self, "content_type_registry") and 
                                self.content_type_registry and 
                                hasattr(self, "detect_content_type") and
                                hasattr(self, "optimize_batch"))
                                
            # Get metadata for CIDs if not provided and we have a metadata cache
            if metadata is None and self.in_memory_batch is not None:
                # Try to extract metadata from in-memory batch
                try:
                    metadata = {}
                    table = pa.Table.from_batches([self.in_memory_batch])
                    cid_index = table.schema.get_field_index('cid')
                    
                    if cid_index >= 0:
                        # Extract CIDs and build a lookup
                        cid_array = table.column(cid_index).to_pylist()
                        
                        # Build metadata dict for each CID
                        for i, row in enumerate(table.to_pylist()):
                            cid = row.get('cid')
                            if cid in cids:
                                metadata[cid] = row
                except Exception as e:
                    logger.warning(f"Failed to extract metadata from in-memory batch: {e}")
                    metadata = {}
            
            # Group CIDs by content type if we have type awareness
            if has_content_types and metadata:
                # Use optimize_batch to group by content type
                batches = self.optimize_batch(cids, metadata)
            else:
                # Use a single default batch if no content type awareness
                batches = {"default": cids}
            
            # Process each content type batch
            for content_type, batch_cids in batches.items():
                if not batch_cids:
                    continue
                    
                # Get optimization settings for this content type
                batch_settings = (self.batch_optimizations.get(content_type, {}) 
                                if hasattr(self, "batch_optimizations") else {})
                                
                # Default settings if not found
                prefetch_strategy = batch_settings.get("prefetch_strategy", "content_first")
                chunk_size = batch_settings.get("chunk_size", 1024 * 1024)  # 1MB default
                
                # Track stats for this content type
                type_stats = {
                    "count": len(batch_cids),
                    "prefetched": 0,
                    "skipped": 0,
                    "failed": 0,
                    "strategy": prefetch_strategy
                }
                
                # Apply the appropriate prefetch strategy for this content type
                if prefetch_strategy == "metadata_first":
                    # Fetch metadata first, then content
                    # This is good for content where metadata processing might filter out content
                    for cid in batch_cids:
                        try:
                            # Check if already in cache
                            if self.memory_cache.contains(cid):
                                type_stats["skipped"] += 1
                                result["skipped"] += 1
                                result["results"][cid] = {"status": "skipped", "reason": "already_in_memory"}
                                continue
                                
                            # Prefetch the content
                            prefetch_result = self.prefetch(cid)
                            result["results"][cid] = prefetch_result
                            
                            if prefetch_result.get("success", False):
                                type_stats["prefetched"] += 1
                                result["prefetched"] += 1
                            else:
                                type_stats["failed"] += 1
                                result["failed"] += 1
                                
                        except Exception as e:
                            type_stats["failed"] += 1
                            result["failed"] += 1
                            result["results"][cid] = {
                                "status": "error", 
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                            
                elif prefetch_strategy == "content_first":
                    # Directly fetch content - simpler approach
                    for cid in batch_cids:
                        try:
                            # Check if already in cache
                            if self.memory_cache.contains(cid):
                                type_stats["skipped"] += 1
                                result["skipped"] += 1
                                result["results"][cid] = {"status": "skipped", "reason": "already_in_memory"}
                                continue
                                
                            # Prefetch the content
                            prefetch_result = self.prefetch(cid)
                            result["results"][cid] = prefetch_result
                            
                            if prefetch_result.get("success", False):
                                type_stats["prefetched"] += 1
                                result["prefetched"] += 1
                            else:
                                type_stats["failed"] += 1
                                result["failed"] += 1
                                
                        except Exception as e:
                            type_stats["failed"] += 1
                            result["failed"] += 1
                            result["results"][cid] = {
                                "status": "error", 
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                
                elif prefetch_strategy == "sequential_chunks":
                    # For content like video/audio that benefits from sequential chunk access
                    # This would be more useful with proper implementation of chunk-based fetching
                    # For now, similar to content_first but could be enhanced in the future
                    for cid in batch_cids:
                        try:
                            # Check if already in cache
                            if self.memory_cache.contains(cid):
                                type_stats["skipped"] += 1
                                result["skipped"] += 1
                                result["results"][cid] = {"status": "skipped", "reason": "already_in_memory"}
                                continue
                                
                            # Prefetch the content
                            prefetch_result = self.prefetch(cid)
                            result["results"][cid] = prefetch_result
                            
                            if prefetch_result.get("success", False):
                                type_stats["prefetched"] += 1
                                result["prefetched"] += 1
                            else:
                                type_stats["failed"] += 1
                                result["failed"] += 1
                                
                        except Exception as e:
                            type_stats["failed"] += 1
                            result["failed"] += 1
                            result["results"][cid] = {
                                "status": "error", 
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                
                # Record stats for this content type
                result["content_types"][content_type] = type_stats
            
            # Log summary
            logger.info(
                f"Batch prefetch completed: {result['prefetched']} prefetched, "
                f"{result['skipped']} skipped, {result['failed']} failed"
            )
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error in batch prefetch: {e}")
            
        return result
    
    @experimental_api(since="0.19.0")
    async def async_batch_prefetch(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async version of batch_prefetch.
        
        Asynchronously prefetch multiple CIDs with content-type optimizations and parallel processing.
        
        Args:
            cids: List of CIDs to prefetch
            metadata: Optional metadata for each CID to optimize prefetching strategy
            
        Returns:
            Dictionary with prefetch operation results
        """
        if not self.has_asyncio:
            # Fallback to synchronous version through thread pool if asyncio not available
            future = self.thread_pool.submit(self.batch_prefetch, cids, metadata)
            return future.result()
            
        # If asyncio is available, use parallel processing
        try:
            # Determine if we have content type awareness
            has_content_types = (hasattr(self, "content_type_registry") and 
                                self.content_type_registry and 
                                hasattr(self, "detect_content_type") and
                                hasattr(self, "optimize_batch"))
                                
            # Initialize result structure
            result = {
                "success": True,
                "operation": "async_batch_prefetch",
                "timestamp": time.time(),
                "total_cids": len(cids),
                "prefetched": 0,
                "skipped": 0,
                "failed": 0,
                "content_types": {},
                "results": {}
            }
            
            # Get or create metadata dict
            if metadata is None and self.in_memory_batch is not None:
                try:
                    metadata = {}
                    table = pa.Table.from_batches([self.in_memory_batch])
                    for row in table.to_pylist():
                        cid = row.get('cid')
                        if cid and cid in cids:
                            metadata[cid] = row
                except Exception as e:
                    logger.warning(f"Failed to extract metadata from in-memory batch: {e}")
                    metadata = {}
            
            # Group by content type if possible
            if has_content_types and metadata:
                # Use optimize_batch to group by content type
                batches = self.optimize_batch(cids, metadata)
            else:
                # Use a single default batch if no content type awareness
                batches = {"default": cids}
                
            # Process each content type in parallel
            async def process_content_type(content_type, batch_cids):
                if not batch_cids:
                    return content_type, {}
                    
                # Get optimization settings for this content type
                batch_settings = (self.batch_optimizations.get(content_type, {}) 
                                if hasattr(self, "batch_optimizations") else {})
                                
                # Default settings if not found
                prefetch_strategy = batch_settings.get("prefetch_strategy", "content_first")
                max_concurrent = batch_settings.get("batch_size", 20)
                
                # Stats for this type
                type_stats = {
                    "count": len(batch_cids),
                    "prefetched": 0,
                    "skipped": 0,
                    "failed": 0,
                    "strategy": prefetch_strategy
                }
                
                # Create a semaphore to limit concurrency
                semaphore = anyio.Semaphore(max_concurrent)
                
                # Create a function to process each CID
                async def process_cid(cid):
                    async with semaphore:
                        # Run prefetch in thread pool to avoid blocking
                        loop = anyio.get_event_loop()
                        return await loop.run_in_executor(
                            self.thread_pool,
                            lambda: self.prefetch(cid)
                        )
                
                # Process all CIDs concurrently with controlled parallelism
                tasks = []
                for cid in batch_cids:
                    if self.memory_cache.contains(cid):
                        # Skip if already in memory
                        type_stats["skipped"] += 1
                        result["results"][cid] = {"status": "skipped", "reason": "already_in_memory"}
                    else:
                        # Create task for this CID
                        tasks.append(process_cid(cid))
                
                # Wait for all tasks to complete
                if tasks:
                    results = await anyio.gather(*tasks, return_exceptions=True)
                    
                    # Process results
                    for i, prefetch_result in enumerate(results):
                        cid = batch_cids[i]
                        
                        # Skip if we already marked it as skipped
                        if cid in result["results"] and result["results"][cid].get("status") == "skipped":
                            continue
                            
                        if isinstance(prefetch_result, Exception):
                            # Handle exception
                            type_stats["failed"] += 1
                            result["results"][cid] = {
                                "status": "error",
                                "error": str(prefetch_result),
                                "error_type": type(prefetch_result).__name__
                            }
                        else:
                            # Store result
                            result["results"][cid] = prefetch_result
                            
                            if prefetch_result.get("success", False):
                                type_stats["prefetched"] += 1
                            else:
                                type_stats["failed"] += 1
                
                return content_type, type_stats
            
            # Process all content types in parallel
            tasks = []
            for content_type, batch_cids in batches.items():
                tasks.append(process_content_type(content_type, batch_cids))
                
            # Wait for all content types to complete
            content_type_results = await anyio.gather(*tasks)
            
            # Process results
            for content_type, type_stats in content_type_results:
                if type_stats:  # Skip empty results
                    result["content_types"][content_type] = type_stats
                    result["prefetched"] += type_stats.get("prefetched", 0)
                    result["skipped"] += type_stats.get("skipped", 0)
                    result["failed"] += type_stats.get("failed", 0)
            
            # Log summary
            logger.info(
                f"Async batch prefetch completed: {result['prefetched']} prefetched, "
                f"{result['skipped']} skipped, {result['failed']} failed"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in async batch prefetch: {e}")
            return {
                "success": False,
                "operation": "async_batch_prefetch",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__
            }

    @beta_api(since="0.19.0")
    def enhance_c_data_interface(self, memory_limit_mb: Optional[int] = None, auto_adjust: bool = True) -> Dict[str, Any]:
        """Enhance the C Data Interface with advanced zero-copy optimizations.
        
        This method configures and optimizes the Arrow C Data Interface for efficient
        zero-copy data sharing between processes. It can significantly improve performance
        when multiple processes need to access the same metadata.
        
        Args:
            memory_limit_mb: Memory limit for Plasma store in MB, or None for auto-detection
            auto_adjust: Whether to automatically adjust memory limits based on system resources
            
        Returns:
            Dictionary with configuration results
        """
        result = {
            "success": False,
            "operation": "enhance_c_data_interface",
            "timestamp": time.time()
        }
        
        try:
            # Check if PyArrow Plasma is available
            if not self.has_plasma:
                result["error"] = "PyArrow Plasma not available. Install with: pip install ipfs_kit_py[arrow]"
                return result
                
            # Enable C Data Interface if it wasn't already
            old_status = self.enable_c_data_interface
            self.enable_c_data_interface = True
            result["previous_status"] = old_status
            
            # Auto-detect memory limits if not specified
            if memory_limit_mb is None and auto_adjust:
                try:
                    import psutil
                    # Get total memory and use 10% for Plasma store (capped at 1GB)
                    total_mem_mb = psutil.virtual_memory().total / (1024 * 1024)
                    memory_limit_mb = min(int(total_mem_mb * 0.1), 1024)  # 10% of RAM, max 1GB
                    result["auto_detected_memory_mb"] = memory_limit_mb
                except ImportError:
                    # Default to 256MB if psutil not available
                    memory_limit_mb = 256
                    result["default_memory_mb"] = memory_limit_mb
            elif memory_limit_mb is None:
                # Default if not auto-adjusting
                memory_limit_mb = 256
                    
            # Start or restart Plasma store with configured memory
            plasma_result = self._start_plasma_store(memory_limit_mb=memory_limit_mb)
            result["plasma_store"] = plasma_result
            
            if not plasma_result.get("success", False):
                result["error"] = plasma_result.get("error", "Failed to start Plasma store")
                return result
                
            # Configure automatic object cleanup
            if not hasattr(self, "_plasma_cleanup_interval"):
                self._plasma_cleanup_interval = 300  # 5 minutes default
                
            if not hasattr(self, "_plasma_cleanup_timer"):
                # Start cleanup timer
                import threading
                self._plasma_cleanup_timer = threading.Timer(
                    self._plasma_cleanup_interval, 
                    self._plasma_cleanup_task
                )
                self._plasma_cleanup_timer.daemon = True
                self._plasma_cleanup_timer.start()
                result["cleanup_scheduled"] = True
                
            # Initialize object tracking for efficient management
            if not hasattr(self, "_plasma_objects"):
                self._plasma_objects = {}
                
            # Export current data to C Data Interface
            export_result = self._export_to_c_data_interface_enhanced()
            result["export_result"] = export_result
            
            # Set overall success based on export
            result["success"] = export_result.get("success", False)
            result["handle"] = self.get_c_data_interface() if result["success"] else None
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error enhancing C Data Interface: {e}")
            
        return result
    
    @beta_api(since="0.19.0")
    def _export_to_c_data_interface_enhanced(self) -> Dict[str, Any]:
        """Enhanced export of data to Arrow C Data Interface for zero-copy access.
        
        This method creates a shared memory representation of the metadata index 
        that can be efficiently accessed by other processes without copying the data.
        It includes optimizations for different data types and access patterns.
        
        Returns:
            Dictionary with export results and performance metrics
        """
        result = {
            "success": False,
            "operation": "_export_to_c_data_interface_enhanced",
            "timestamp": time.time()
        }
        
        try:
            if not self.has_plasma:
                result["error"] = "PyArrow Plasma not available"
                return result
                
            # Connect to plasma store if not already connected
            if self.plasma_client is None:
                socket_path = os.environ.get("PLASMA_STORE_SOCKET")
                if not socket_path:
                    socket_path = os.path.join(self.directory, "plasma.sock")
                    
                # Create a standardized path for socket to ensure consistent connections
                socket_path = os.path.abspath(os.path.expanduser(socket_path))
                
                try:
                    self.plasma_client = self.plasma.connect(socket_path)
                    result["plasma_socket"] = socket_path
                except Exception as e:
                    # Try to start the Plasma store if connection failed
                    start_result = self._start_plasma_store()
                    if start_result.get("success", False):
                        socket_path = start_result.get("socket_path")
                        try:
                            self.plasma_client = self.plasma.connect(socket_path)
                            result["plasma_socket"] = socket_path
                            result["plasma_started"] = True
                        except Exception as inner_e:
                            result["error"] = f"Failed to connect to Plasma store after starting: {inner_e}"
                            return result
                    else:
                        result["error"] = f"Failed to connect to Plasma store: {e}"
                        return result
            
            # Export current data based on what's available
            start_time = time.time()
            
            # Determine what data to export
            if self.in_memory_batch is not None:
                # Export in-memory batch for the fastest access
                table = pa.Table.from_batches([self.in_memory_batch])
                object_size = table.nbytes
                
                # Generate a unique object ID
                object_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_{time.time()}".encode()).digest()[:20])
                
                # Check if we need to allocate more space
                if object_size > 100 * 1024 * 1024:  # Object > 100MB
                    # For very large objects, split into chunks to avoid memory issues
                    chunk_size = 50 * 1024 * 1024  # 50MB chunks
                    num_chunks = (object_size + chunk_size - 1) // chunk_size
                    result["chunked"] = True
                    result["num_chunks"] = num_chunks
                    
                    # Create object reference list
                    chunk_ids = []
                    
                    # Split table into chunks
                    for i in range(0, table.num_rows, table.num_rows // num_chunks + 1):
                        end_idx = min(i + (table.num_rows // num_chunks + 1), table.num_rows)
                        chunk_table = table.slice(i, end_idx - i)
                        
                        # Create and seal chunk in Plasma
                        chunk_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_{time.time()}_{i}".encode()).digest()[:20])
                        try:
                            buffer = self.plasma_client.create(chunk_id, chunk_table.nbytes)
                            stream_writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), chunk_table.schema)
                            stream_writer.write_table(chunk_table)
                            stream_writer.close()
                            self.plasma_client.seal(chunk_id)
                            chunk_ids.append(chunk_id.binary().hex())
                            
                            # Track the object for cleanup
                            self._plasma_objects[chunk_id.binary().hex()] = {
                                "timestamp": time.time(),
                                "size": chunk_table.nbytes,
                                "rows": chunk_table.num_rows,
                                "type": "chunk",
                                "chunk_index": i // (table.num_rows // num_chunks + 1)
                            }
                            
                        except Exception as e:
                            result["error"] = f"Failed to create chunk {i}: {e}"
                            # Try to clean up already created chunks
                            for chunk_id_hex in chunk_ids:
                                try:
                                    self.plasma_client.delete(self.plasma.ObjectID(bytes.fromhex(chunk_id_hex)))
                                except:
                                    pass
                            return result
                            
                    # Create a reference object that contains the list of chunk IDs
                    ref_object_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_ref_{time.time()}".encode()).digest()[:20])
                    ref_obj = {
                        "type": "chunked_table",
                        "num_chunks": num_chunks,
                        "chunk_ids": chunk_ids,
                        "total_rows": table.num_rows,
                        "schema_json": table.schema.to_string(),
                        "timestamp": time.time()
                    }
                    
                    # Serialize and store reference object
                    ref_json = json.dumps(ref_obj).encode('utf-8')
                    try:
                        buffer = self.plasma_client.create(ref_object_id, len(ref_json))
                        buffer.write(ref_json)
                        self.plasma_client.seal(ref_object_id)
                        
                        # Set reference as the main object
                        self.current_object_id = ref_object_id
                        
                        # Track the reference object
                        self._plasma_objects[ref_object_id.binary().hex()] = {
                            "timestamp": time.time(),
                            "size": len(ref_json),
                            "type": "chunked_reference",
                            "num_chunks": num_chunks,
                            "total_rows": table.num_rows
                        }
                        
                        # Update handle information
                        self.c_data_interface_handle = {
                            'object_id': ref_object_id.binary().hex(),
                            'plasma_socket': result["plasma_socket"],
                            'schema_json': table.schema.to_string(),
                            'num_rows': table.num_rows,
                            'chunked': True,
                            'num_chunks': num_chunks,
                            'timestamp': time.time()
                        }
                        
                    except Exception as e:
                        result["error"] = f"Failed to create reference object: {e}"
                        # Try to clean up chunks
                        for chunk_id_hex in chunk_ids:
                            try:
                                self.plasma_client.delete(self.plasma.ObjectID(bytes.fromhex(chunk_id_hex)))
                            except:
                                pass
                        return result
                    
                else:
                    # For smaller objects, store as a single object
                    try:
                        buffer = self.plasma_client.create(object_id, object_size)
                        stream_writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), table.schema)
                        stream_writer.write_table(table)
                        stream_writer.close()
                        self.plasma_client.seal(object_id)
                        
                        # Set as current object
                        self.current_object_id = object_id
                        
                        # Track the object
                        self._plasma_objects[object_id.binary().hex()] = {
                            "timestamp": time.time(),
                            "size": object_size,
                            "rows": table.num_rows,
                            "type": "single_table"
                        }
                        
                        # Update handle information
                        self.c_data_interface_handle = {
                            'object_id': object_id.binary().hex(),
                            'plasma_socket': result["plasma_socket"],
                            'schema_json': table.schema.to_string(),
                            'num_rows': table.num_rows,
                            'chunked': False,
                            'timestamp': time.time()
                        }
                        
                    except Exception as e:
                        result["error"] = f"Failed to create Plasma object: {e}"
                        return result
                
                # Write C Data Interface metadata to disk for other processes
                cdi_path = os.path.join(self.directory, 'c_data_interface.json')
                with open(cdi_path, 'w') as f:
                    json.dump(self.c_data_interface_handle, f)
                
                # Set success and performance metrics
                result["success"] = True
                result["duration_ms"] = (time.time() - start_time) * 1000
                result["object_size"] = object_size
                result["num_rows"] = table.num_rows
                result["metadata_path"] = cdi_path
                
            else:
                # No data to export
                result["success"] = False
                result["error"] = "No data to export"
                
            return result
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error in enhanced C Data Interface export: {e}")
            return result
    
    @beta_api(since="0.19.0")
    def _plasma_cleanup_task(self) -> None:
        """Cleanup task for managing Plasma objects.
        
        This method runs periodically to clean up stale objects in the Plasma store,
        preventing memory leaks and ensuring efficient resource utilization.
        """
        try:
            if not self.has_plasma or not hasattr(self, "_plasma_objects") or not self.plasma_client:
                return
                
            now = time.time()
            objects_to_remove = []
            
            # Find objects older than 30 minutes
            for obj_id, info in self._plasma_objects.items():
                # Skip current object
                if hasattr(self, "current_object_id") and self.current_object_id and \
                   obj_id == self.current_object_id.binary().hex():
                    continue
                    
                # Check age - expire objects older than 30 minutes
                if now - info.get("timestamp", 0) > 1800:  # 30 minutes
                    objects_to_remove.append(obj_id)
            
            # Remove expired objects
            for obj_id in objects_to_remove:
                try:
                    self.plasma_client.delete(self.plasma.ObjectID(bytes.fromhex(obj_id)))
                    del self._plasma_objects[obj_id]
                    logger.debug(f"Removed stale Plasma object: {obj_id}")
                except Exception as e:
                    logger.warning(f"Failed to remove Plasma object {obj_id}: {e}")
                    
            # Schedule next cleanup
            import threading
            self._plasma_cleanup_timer = threading.Timer(
                self._plasma_cleanup_interval, 
                self._plasma_cleanup_task
            )
            self._plasma_cleanup_timer.daemon = True
            self._plasma_cleanup_timer.start()
            
        except Exception as e:
            logger.error(f"Error in Plasma cleanup task: {e}")
            
    @experimental_api(since="0.19.0")
    def batch_get_metadata_zero_copy(self, cids: List[str]) -> Dict[str, Any]:
        """Get metadata for multiple CIDs using zero-copy access.
        
        This method efficiently retrieves metadata for multiple CIDs using
        the Arrow C Data Interface for zero-copy access between processes.
        It significantly improves performance for batch operations.
        
        Args:
            cids: List of CIDs to retrieve metadata for
            
        Returns:
            Dictionary with results and metadata
        """
        result = {
            "success": False,
            "operation": "batch_get_metadata_zero_copy",
            "timestamp": time.time(),
            "results": {}
        }
        
        try:
            # Validate that C Data Interface is enabled and available
            if not self.has_plasma or not self.enable_c_data_interface:
                # Fall back to regular batch operation
                regular_result = self.batch_get_metadata(cids)
                result["success"] = True
                result["results"] = regular_result
                result["fallback"] = "regular_batch"
                return result
                
            # Ensure we have a valid C Data Interface handle
            if not self.c_data_interface_handle:
                # Try to export data first
                export_result = self.enhance_c_data_interface()
                if not export_result.get("success", False):
                    # Fall back to regular batch operation
                    regular_result = self.batch_get_metadata(cids)
                    result["success"] = True
                    result["results"] = regular_result
                    result["fallback"] = "regular_batch_after_export_failure"
                    return result
            
            # Get handle info
            handle = self.c_data_interface_handle
            is_chunked = handle.get("chunked", False)
            
            # Create results dictionary
            metadata_dict = {}
            
            if is_chunked:
                # Process chunked data
                ref_object_id = self.plasma.ObjectID(bytes.fromhex(handle["object_id"]))
                
                # Get reference object
                ref_buffer = self.plasma_client.get(ref_object_id)
                ref_data = json.loads(ref_buffer.to_pybytes().decode('utf-8'))
                
                # Load each chunk and search for the CIDs
                remaining_cids = set(cids)
                
                for chunk_id_hex in ref_data["chunk_ids"]:
                    # Skip if we've found all CIDs
                    if not remaining_cids:
                        break
                        
                    # Load chunk
                    chunk_id = self.plasma.ObjectID(bytes.fromhex(chunk_id_hex))
                    chunk_buffer = self.plasma_client.get(chunk_id)
                    
                    # Read table from buffer
                    reader = pa.RecordBatchStreamReader(chunk_buffer)
                    chunk_table = reader.read_all()
                    
                    # Convert to pandas for easier filtering (could be optimized further)
                    df = chunk_table.to_pandas()
                    
                    # Filter for the CIDs we're looking for
                    found_cids = list(set(df['cid']) & remaining_cids)
                    
                    # Extract metadata for found CIDs
                    if found_cids:
                        for cid in found_cids:
                            row = df[df['cid'] == cid].iloc[0].to_dict()
                            metadata_dict[cid] = row
                            remaining_cids.remove(cid)
                
            else:
                # Single-object case
                object_id = self.plasma.ObjectID(bytes.fromhex(handle["object_id"]))
                
                # Get the object
                buffer = self.plasma_client.get(object_id)
                
                # Read table from buffer
                reader = pa.RecordBatchStreamReader(buffer)
                table = reader.read_all()
                
                # Convert to pandas for easier filtering (could be optimized further)
                df = table.to_pandas()
                
                # Filter for the CIDs we're looking for
                df_filtered = df[df['cid'].isin(cids)]
                
                # Extract metadata for found CIDs
                for _, row in df_filtered.iterrows():
                    metadata_dict[row['cid']] = row.to_dict()
            
            # Set result
            result["success"] = True
            result["results"] = metadata_dict
            result["found_count"] = len(metadata_dict)
            result["missing_count"] = len(cids) - len(metadata_dict)
            
            # List missing CIDs if any
            if result["missing_count"] > 0:
                result["missing_cids"] = list(set(cids) - set(metadata_dict.keys()))
            
            return result
            
        except Exception as e:
            # Fall back to regular batch operation on error
            try:
                regular_result = self.batch_get_metadata(cids)
                result["success"] = True
                result["results"] = regular_result
                result["fallback"] = "regular_batch_after_error"
                result["error"] = str(e)
                logger.warning(f"Zero-copy batch get failed, falling back to regular: {e}")
                return result
            except Exception as inner_e:
                result["success"] = False
                result["error"] = f"Zero-copy failed: {e}, fallback failed: {inner_e}"
                result["error_type"] = type(e).__name__
                logger.error(f"Error in batch_get_metadata_zero_copy: {e}")
                return result
    
    @experimental_api(since="0.19.0")
    async def async_batch_get_metadata_zero_copy(self, cids: List[str]) -> Dict[str, Any]:
        """Async version of batch_get_metadata_zero_copy.
        
        Args:
            cids: List of CIDs to retrieve metadata for
            
        Returns:
            Dictionary with results and metadata
        """
        if not self.has_asyncio:
            # Fallback to synchronous version through thread pool if asyncio not available
            future = self.thread_pool.submit(self.batch_get_metadata_zero_copy, cids)
            return future.result()
            
        # If asyncio is available, run in executor to avoid blocking
        loop = anyio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, 
            lambda: self.batch_get_metadata_zero_copy(cids)
        )
        
    @experimental_api(since="0.19.0")
    def batch_put_metadata_zero_copy(self, metadata_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Store metadata for multiple CIDs using zero-copy access with Arrow C Data Interface.
        
        This method efficiently updates metadata for multiple CIDs using shared memory
        and the Arrow C Data Interface. It's designed for high-throughput batch operations
        when multiple metadata records need to be updated quickly with minimum overhead.
        
        Args:
            metadata_dict: Dictionary mapping CIDs to their metadata
            
        Returns:
            Dictionary with operation results
        """
        result = {
            "success": False,
            "operation": "batch_put_metadata_zero_copy",
            "timestamp": time.time(),
            "results": {}
        }
        
        try:
            # Validate that C Data Interface is enabled and available
            if not self.has_plasma or not self.enable_c_data_interface:
                # Fall back to regular batch operation
                regular_result = self.batch_put_metadata(metadata_dict)
                result["success"] = True
                result["results"] = regular_result
                result["fallback"] = "regular_batch"
                return result
                
            # Ensure we have a valid C Data Interface handle
            if not self.c_data_interface_handle:
                # Try to export data first
                export_result = self.enhance_c_data_interface()
                if not export_result.get("success", False):
                    # Fall back to regular batch operation
                    regular_result = self.batch_put_metadata(metadata_dict)
                    result["success"] = True
                    result["results"] = regular_result
                    result["fallback"] = "regular_batch_after_export_failure"
                    return result
            
            # Initialize results for each CID
            for cid in metadata_dict:
                result["results"][cid] = False
                
            # Get handle info
            handle = self.c_data_interface_handle
            is_chunked = handle.get("chunked", False)
            current_time_ms = int(time.time() * 1000)
            
            # Prepare all the records to be added or updated
            all_records = []
            for cid, metadata in metadata_dict.items():
                record = {
                    'cid': cid,
                    'size_bytes': metadata.get('size_bytes', 0),
                    'mimetype': metadata.get('mimetype', ''),
                    'filename': metadata.get('filename', ''),
                    'extension': metadata.get('extension', ''),
                    'storage_tier': metadata.get('storage_tier', 'unknown'),
                    'is_pinned': metadata.get('is_pinned', False),
                    'local_path': metadata.get('local_path', ''),
                    'added_timestamp': metadata.get('added_timestamp', current_time_ms),
                    'last_accessed': current_time_ms,
                    'access_count': metadata.get('access_count', 1),
                    'heat_score': metadata.get('heat_score', 0.0),
                    'source': metadata.get('source', 'unknown'),
                    'source_details': metadata.get('source_details', ''),
                    'multihash_type': metadata.get('multihash_type', ''),
                    'cid_version': metadata.get('cid_version', 1),
                    'valid': metadata.get('valid', True),
                    'validation_timestamp': current_time_ms,
                    'properties': metadata.get('properties', {})
                }
                all_records.append(record)
            
            # Set of CIDs we need to update
            cids_to_update = set(metadata_dict.keys())
            remaining_cids = set(cids_to_update)
            
            # Start timing for performance metrics
            start_time = time.time()
            
            if is_chunked:
                # Process chunked data
                ref_object_id = self.plasma.ObjectID(bytes.fromhex(handle["object_id"]))
                
                # Get reference object
                ref_buffer = self.plasma_client.get(ref_object_id)
                ref_data = json.loads(ref_buffer.to_pybytes().decode('utf-8'))
                
                # Load each chunk and update the relevant CIDs
                modified_chunks = []
                
                for chunk_idx, chunk_id_hex in enumerate(ref_data["chunk_ids"]):
                    # Skip if we've found all CIDs
                    if not remaining_cids:
                        break
                        
                    # Load chunk
                    chunk_id = self.plasma.ObjectID(bytes.fromhex(chunk_id_hex))
                    chunk_buffer = self.plasma_client.get(chunk_id)
                    
                    # Read table from buffer
                    reader = pa.RecordBatchStreamReader(chunk_buffer)
                    chunk_table = reader.read_all()
                    
                    # Convert to pandas for easier filtering and modification
                    df = chunk_table.to_pandas()
                    
                    # Find overlapping CIDs in this chunk
                    chunk_cids = set(df['cid']) & remaining_cids
                    
                    if chunk_cids:
                        # There are CIDs in this chunk that need to be updated
                        # Remove existing rows for these CIDs
                        df = df[~df['cid'].isin(chunk_cids)]
                        
                        # Add new records for these CIDs
                        new_records = [r for r in all_records if r['cid'] in chunk_cids]
                        if new_records:
                            new_df = pd.DataFrame(new_records)
                            updated_df = pd.concat([df, new_df], ignore_index=True)
                        else:
                            updated_df = df
                        
                        # Convert back to Arrow table
                        updated_table = pa.Table.from_pandas(updated_df, schema=self.schema)
                        
                        # Create new chunk in plasma store
                        new_chunk_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_chunk_{chunk_idx}_{time.time()}".encode()).digest()[:20])
                        object_size = updated_table.nbytes + 4096  # Add some buffer
                        
                        # Store updated chunk
                        buffer = self.plasma_client.create(new_chunk_id, object_size)
                        stream_writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), updated_table.schema)
                        stream_writer.write_table(updated_table)
                        stream_writer.close()
                        self.plasma_client.seal(new_chunk_id)
                        
                        # Track the object
                        self._plasma_objects[new_chunk_id.binary().hex()] = {
                            "timestamp": time.time(),
                            "size": object_size,
                            "rows": updated_table.num_rows,
                            "type": "chunk"
                        }
                        
                        # Update reference to use new chunk
                        modified_chunks.append((chunk_idx, new_chunk_id.binary().hex()))
                        
                        # Mark these CIDs as processed
                        for cid in chunk_cids:
                            result["results"][cid] = True
                            remaining_cids.remove(cid)
                
                # If we have any modified chunks, update the reference object
                if modified_chunks:
                    new_chunk_ids = ref_data["chunk_ids"].copy()
                    for chunk_idx, new_chunk_id_hex in modified_chunks:
                        new_chunk_ids[chunk_idx] = new_chunk_id_hex
                    
                    # Create new reference object
                    new_ref_object_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_ref_{time.time()}".encode()).digest()[:20])
                    new_ref_obj = {
                        "type": "chunked_table",
                        "num_chunks": ref_data["num_chunks"],
                        "chunk_ids": new_chunk_ids,
                        "total_rows": ref_data["total_rows"],
                        "schema_json": self.schema.to_string(),
                        "timestamp": time.time()
                    }
                    
                    # Serialize and store new reference object
                    new_ref_json = json.dumps(new_ref_obj).encode('utf-8')
                    buffer = self.plasma_client.create(new_ref_object_id, len(new_ref_json))
                    buffer.write(new_ref_json)
                    self.plasma_client.seal(new_ref_object_id)
                    
                    # Update the current object ID
                    self.current_object_id = new_ref_object_id
                    
                    # Track the reference object
                    self._plasma_objects[new_ref_object_id.binary().hex()] = {
                        "timestamp": time.time(),
                        "size": len(new_ref_json),
                        "type": "chunked_reference",
                        "num_chunks": ref_data["num_chunks"],
                        "total_rows": ref_data["total_rows"]
                    }
                    
                    # Update handle information
                    self.c_data_interface_handle = {
                        'object_id': new_ref_object_id.binary().hex(),
                        'plasma_socket': handle["plasma_socket"],
                        'schema_json': self.schema.to_string(),
                        'num_rows': ref_data["total_rows"],
                        'chunked': True,
                        'num_chunks': ref_data["num_chunks"],
                        'timestamp': time.time()
                    }
                    
                    # Write C Data Interface metadata to disk for other processes
                    cdi_path = os.path.join(self.directory, 'c_data_interface.json')
                    with open(cdi_path, 'w') as f:
                        json.dump(self.c_data_interface_handle, f)
            
            else:
                # Single-object case
                object_id = self.plasma.ObjectID(bytes.fromhex(handle["object_id"]))
                
                # Get the object
                buffer = self.plasma_client.get(object_id)
                
                # Read table from buffer
                reader = pa.RecordBatchStreamReader(buffer)
                table = reader.read_all()
                
                # Convert to pandas for easier modification
                df = table.to_pandas()
                
                # Remove existing rows for CIDs we're updating
                df = df[~df['cid'].isin(remaining_cids)]
                
                # Add new records
                new_df = pd.DataFrame(all_records)
                updated_df = pd.concat([df, new_df], ignore_index=True)
                
                # Convert back to Arrow table
                updated_table = pa.Table.from_pandas(updated_df, schema=self.schema)
                
                # Create new object in plasma store
                new_object_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_table_{time.time()}".encode()).digest()[:20])
                object_size = updated_table.nbytes + 4096  # Add some buffer
                
                # Store updated table
                buffer = self.plasma_client.create(new_object_id, object_size)
                stream_writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), updated_table.schema)
                stream_writer.write_table(updated_table)
                stream_writer.close()
                self.plasma_client.seal(new_object_id)
                
                # Track the object
                self._plasma_objects[new_object_id.binary().hex()] = {
                    "timestamp": time.time(),
                    "size": object_size,
                    "rows": updated_table.num_rows,
                    "type": "single_table"
                }
                
                # Update the current object ID
                self.current_object_id = new_object_id
                
                # Update handle information
                self.c_data_interface_handle = {
                    'object_id': new_object_id.binary().hex(),
                    'plasma_socket': handle["plasma_socket"],
                    'schema_json': self.schema.to_string(),
                    'num_rows': updated_table.num_rows,
                    'chunked': False,
                    'timestamp': time.time()
                }
                
                # Write C Data Interface metadata to disk for other processes
                cdi_path = os.path.join(self.directory, 'c_data_interface.json')
                with open(cdi_path, 'w') as f:
                    json.dump(self.c_data_interface_handle, f)
                
                # Mark all CIDs as successfully processed
                for cid in metadata_dict:
                    result["results"][cid] = True
                    remaining_cids.discard(cid)
            
            # If there are any remaining CIDs that weren't found in existing chunks
            # Create a new chunk for them
            if remaining_cids and is_chunked:
                # Create records for remaining CIDs
                remaining_records = [r for r in all_records if r['cid'] in remaining_cids]
                
                # Convert to Arrow table
                remaining_df = pd.DataFrame(remaining_records)
                remaining_table = pa.Table.from_pandas(remaining_df, schema=self.schema)
                
                # Create new chunk in plasma store
                new_chunk_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_chunk_new_{time.time()}".encode()).digest()[:20])
                object_size = remaining_table.nbytes + 4096  # Add some buffer
                
                # Store new chunk
                buffer = self.plasma_client.create(new_chunk_id, object_size)
                stream_writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), remaining_table.schema)
                stream_writer.write_table(remaining_table)
                stream_writer.close()
                self.plasma_client.seal(new_chunk_id)
                
                # Track the object
                self._plasma_objects[new_chunk_id.binary().hex()] = {
                    "timestamp": time.time(),
                    "size": object_size,
                    "rows": remaining_table.num_rows,
                    "type": "chunk"
                }
                
                # Get reference data
                ref_object_id = self.plasma.ObjectID(bytes.fromhex(handle["object_id"]))
                ref_buffer = self.plasma_client.get(ref_object_id)
                ref_data = json.loads(ref_buffer.to_pybytes().decode('utf-8'))
                
                # Add new chunk to the reference
                new_chunk_ids = ref_data["chunk_ids"] + [new_chunk_id.binary().hex()]
                new_num_chunks = len(new_chunk_ids)
                new_total_rows = ref_data["total_rows"] + remaining_table.num_rows
                
                # Create new reference object
                new_ref_object_id = self.plasma.ObjectID(hashlib.md5(f"{self.directory}_ref_{time.time()}".encode()).digest()[:20])
                new_ref_obj = {
                    "type": "chunked_table",
                    "num_chunks": new_num_chunks,
                    "chunk_ids": new_chunk_ids,
                    "total_rows": new_total_rows,
                    "schema_json": self.schema.to_string(),
                    "timestamp": time.time()
                }
                
                # Serialize and store new reference object
                new_ref_json = json.dumps(new_ref_obj).encode('utf-8')
                buffer = self.plasma_client.create(new_ref_object_id, len(new_ref_json))
                buffer.write(new_ref_json)
                self.plasma_client.seal(new_ref_object_id)
                
                # Update the current object ID
                self.current_object_id = new_ref_object_id
                
                # Track the reference object
                self._plasma_objects[new_ref_object_id.binary().hex()] = {
                    "timestamp": time.time(),
                    "size": len(new_ref_json),
                    "type": "chunked_reference",
                    "num_chunks": new_num_chunks,
                    "total_rows": new_total_rows
                }
                
                # Update handle information
                self.c_data_interface_handle = {
                    'object_id': new_ref_object_id.binary().hex(),
                    'plasma_socket': handle["plasma_socket"],
                    'schema_json': self.schema.to_string(),
                    'num_rows': new_total_rows,
                    'chunked': True,
                    'num_chunks': new_num_chunks,
                    'timestamp': time.time()
                }
                
                # Write C Data Interface metadata to disk for other processes
                cdi_path = os.path.join(self.directory, 'c_data_interface.json')
                with open(cdi_path, 'w') as f:
                    json.dump(self.c_data_interface_handle, f)
                
                # Mark all remaining CIDs as successfully processed
                for cid in remaining_cids:
                    result["results"][cid] = True
            
            # Also update the in-memory batch to keep it consistent
            self._update_in_memory_batch_from_metadata_dict(metadata_dict)
            
            # Set overall success status and performance metrics
            result["success"] = all(result["results"].values())
            result["duration_ms"] = (time.time() - start_time) * 1000
            result["total_records"] = len(metadata_dict)
            result["processed_records"] = sum(1 for v in result["results"].values() if v)
            
            # Schedule plasma cleanup to prevent memory leaks
            self._schedule_plasma_cleanup()
            
            return result
            
        except Exception as e:
            # Fall back to regular batch operation on error
            try:
                regular_result = self.batch_put_metadata(metadata_dict)
                result["success"] = True
                result["results"] = regular_result
                result["fallback"] = "regular_batch_after_error"
                result["error"] = str(e)
                logger.warning(f"Zero-copy batch put failed, falling back to regular: {e}")
                return result
            except Exception as inner_e:
                result["success"] = False
                result["error"] = f"Zero-copy failed: {e}, fallback failed: {inner_e}"
                result["error_type"] = type(e).__name__
                logger.error(f"Error in batch_put_metadata_zero_copy: {e}")
                return result
    
    def _update_in_memory_batch_from_metadata_dict(self, metadata_dict: Dict[str, Dict[str, Any]]) -> None:
        """Update the in-memory batch with new metadata.
        
        Args:
            metadata_dict: Dictionary mapping CIDs to their metadata
        """
        try:
            if self.in_memory_batch is None:
                # Create arrays for a new record batch
                arrays = []
                
                # For each field, create an array with values from all records
                current_time_ms = int(time.time() * 1000)
                
                for field in self.schema:
                    field_name = field.name
                    field_values = []
                    
                    for cid, metadata in metadata_dict.items():
                        if field_name == 'cid':
                            field_values.append(cid)
                        elif field_name in metadata:
                            value = metadata[field_name]
                            
                            # Convert timestamp values to proper format
                            if field.type == pa.timestamp('ms') and not isinstance(value, (int, float)):
                                value = current_time_ms
                                
                            field_values.append(value)
                        else:
                            field_values.append(None)
                    
                    arrays.append(pa.array(field_values, type=field.type))
                
                # Create a new batch with all records
                self.in_memory_batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
                
            else:
                # We have an existing batch that needs to be updated
                table = pa.Table.from_batches([self.in_memory_batch])
                
                # Get the set of CIDs to update
                cids_to_update = set(metadata_dict.keys())
                
                # Remove existing records for those CIDs
                mask = pc.is_in(pc.field('cid'), pa.array(list(cids_to_update)))
                inverse_mask = pc.invert(mask)
                remaining_records = table.filter(inverse_mask)
                
                # Create arrays for the new records
                arrays = []
                current_time_ms = int(time.time() * 1000)
                
                for field in self.schema:
                    field_name = field.name
                    field_values = []
                    
                    for cid, metadata in metadata_dict.items():
                        if field_name == 'cid':
                            field_values.append(cid)
                        elif field_name in metadata:
                            value = metadata[field_name]
                            
                            # Convert timestamp values to proper format
                            if field.type == pa.timestamp('ms') and not isinstance(value, (int, float)):
                                value = current_time_ms
                                
                            field_values.append(value)
                        else:
                            field_values.append(None)
                    
                    arrays.append(pa.array(field_values, type=field.type))
                
                # Create a new batch with the updated records
                new_batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
                
                # Combine with remaining records
                if remaining_records.num_rows > 0:
                    combined_table = pa.concat_tables([remaining_records, pa.Table.from_batches([new_batch])])
                    self.in_memory_batch = combined_table.to_batches()[0]
                else:
                    self.in_memory_batch = new_batch
            
            # Check if we need to rotate partition
            if self.in_memory_batch.num_rows >= self.max_partition_rows:
                self._write_current_partition()
                self.current_partition_id += 1
                self.in_memory_batch = None
            
            self.modified_since_sync = True
                
        except Exception as e:
            logger.error(f"Error updating in-memory batch: {e}")
    
    def _schedule_plasma_cleanup(self) -> None:
        """Schedule a plasma cleanup task to run periodically."""
        if not hasattr(self, "_plasma_cleanup_interval"):
            # Default cleanup interval is 5 minutes
            self._plasma_cleanup_interval = 300
        
        if not hasattr(self, "_plasma_cleanup_timer") or not self._plasma_cleanup_timer.is_alive():
            import threading
            self._plasma_cleanup_timer = threading.Timer(
                self._plasma_cleanup_interval, 
                self._plasma_cleanup_task
            )
            self._plasma_cleanup_timer.daemon = True
            self._plasma_cleanup_timer.start()
            
    @beta_api(since="0.19.0")
    def _get_default_partitioning_config(self) -> Dict[str, Any]:
        """Get default configuration for advanced partitioning strategies.
        
        Returns:
            Default configuration dictionary for all partitioning strategies
        """
        return {
            "time_partitioning": {
                "interval": "day",
                "column": "added_timestamp",
                "format": "%Y-%m-%d",
                "max_partitions": 90,
            },
            "content_type_partitioning": {
                "column": "mimetype",
                "default_partition": "unknown",
                "max_types": 20,
                "group_similar": True,
            },
            "size_partitioning": {
                "column": "size_bytes",
                "boundaries": [10240, 102400, 1048576, 10485760],
                "labels": ["tiny", "small", "medium", "large", "xlarge"]
            },
            "access_pattern_partitioning": {
                "column": "heat_score",
                "boundaries": [0.1, 0.5, 0.9],
                "labels": ["cold", "warm", "hot", "critical"]
            },
            "hybrid_partitioning": {
                "primary": "time",
                "secondary": "content_type"
            }
        }
        
    @beta_api(since="0.19.0")
    def _get_default_probabilistic_config(self) -> Dict[str, Any]:
        """Get default configuration for probabilistic data structures.
        
        Returns:
            Default configuration dictionary for probabilistic data structures
        """
        return {
            "enable_probabilistic": True,
            "bloom_filter": {
                "enabled": True,
                "capacity": 10000,
                "error_rate": 0.01,
                "per_partition": True,
                "serialize": True
            },
            "hyperloglog": {
                "enabled": True,
                "precision": 14,
                "per_column": ["mimetype", "storage_tier"],
                "serialize": True
            },
            "count_min_sketch": {
                "enabled": True,
                "width": 2048,
                "depth": 5,
                "track_columns": ["mimetype", "storage_tier"],
                "serialize": True
            },
            "minhash": {
                "enabled": False,
                "num_hashes": 128,
                "similarity_threshold": 0.7,
                "serialize": True
            }
        }
        """Get default configuration for probabilistic data structures.
        
        Returns:
            Default configuration dictionary for probabilistic data structures
        """
        return {
            "enable_probabilistic": True,
            "bloom_filter": {
                "enabled": True,
                "capacity": 10000,
                "error_rate": 0.01,
                "per_partition": True,
                "serialize": True
            },
            "hyperloglog": {
                "enabled": True,
                "precision": 14,
                "per_column": ["mimetype", "storage_tier"],
                "serialize": True
            },
            "count_min_sketch": {
                "enabled": True,
                "width": 2048,
                "depth": 5,
                "track_columns": ["mimetype", "storage_tier"],
                "serialize": True
            },
            "minhash": {
                "enabled": False,
                "num_hashes": 128,
                "similarity_threshold": 0.7,
                "serialize": True
            }
        }
        
    def _get_probabilistic_data_path(self, structure_type: str, identifier: str) -> str:
        """Get path for serialized probabilistic data structure.
        
        Args:
            structure_type: Type of structure ("bloom", "hll", "cms", "minhash")
            identifier: Identifier for the specific structure instance
            
        Returns:
            Path to the serialized data file
        """
        # Create directory if needed
        prob_dir = os.path.join(self.directory, "probabilistic")
        os.makedirs(prob_dir, exist_ok=True)
        
        # Create type-specific directory
        type_dir = os.path.join(prob_dir, structure_type)
        os.makedirs(type_dir, exist_ok=True)
        
        # Return path with sanitized identifier
        safe_id = "".join(c if c.isalnum() else "_" for c in identifier)
        return os.path.join(type_dir, f"{safe_id}.bin")
        
    @beta_api(since="0.19.0")
    def _get_default_probabilistic_config(self) -> Dict[str, Any]:
        """Get default configuration for probabilistic data structures.
        
        Returns:
            Dictionary with default configuration for probabilistic data structures
        """
        return {
            "enable_bloom_filters": True,
            "enable_hyperloglog": True,
            "enable_count_min_sketch": True, 
            "enable_minhash": False,
            "bloom_filter": {
                "capacity": 100000,
                "error_rate": 0.01,
                "serialize": True,
                "create_per_partition": True
            },
            "hyperloglog": {
                "precision": 14,
                "serialize": True,
                "track_fields": ["mimetype", "extension", "cid_version", "multihash_type"]
            },
            "count_min_sketch": {
                "width": 2048,
                "depth": 5,
                "serialize": True,
                "track_metrics": ["mimetype", "source", "size_category", "access_frequency"]
            },
            "minhash": {
                "num_hashes": 128,
                "serialize": True,
                "similarity_threshold": 0.8
            }
        }

    def _load_probabilistic_data_structures(self) -> None:
        """Load previously serialized probabilistic data structures."""
        # Don't attempt to load if not enabled
        if not self.enable_probabilistic:
            return
            
        try:
            # Create base directory if it doesn't exist
            prob_dir = os.path.join(self.directory, "probabilistic")
            os.makedirs(prob_dir, exist_ok=True)
            
            # Load Bloom filters
            if self.bloom_enabled:
                bloom_dir = os.path.join(prob_dir, "bloom")
                if os.path.exists(bloom_dir):
                    for filename in os.listdir(bloom_dir):
                        if not filename.endswith(".bin"):
                            continue
                        
                        try:
                            partition_id = filename.split(".")[0]
                            with open(os.path.join(bloom_dir, filename), "rb") as f:
                                filter_data = f.read()
                                self.bloom_filters[partition_id] = BloomFilter.deserialize(filter_data)
                                logger.debug(f"Loaded Bloom filter for partition {partition_id}")
                        except Exception as e:
                            logger.error(f"Error loading Bloom filter {filename}: {e}")
                            
            # Load HyperLogLog counters
            if self.hll_enabled:
                hll_dir = os.path.join(prob_dir, "hll")
                if os.path.exists(hll_dir):
                    for filename in os.listdir(hll_dir):
                        if not filename.endswith(".bin"):
                            continue
                        
                        try:
                            counter_id = filename.split(".")[0]
                            with open(os.path.join(hll_dir, filename), "rb") as f:
                                hll_data = f.read()
                                self.hyperloglog_counters[counter_id] = HyperLogLog.deserialize(hll_data)
                                logger.debug(f"Loaded HyperLogLog counter for {counter_id}")
                        except Exception as e:
                            logger.error(f"Error loading HyperLogLog counter {filename}: {e}")
            
            # Load Count-Min Sketches
            if self.cms_enabled:
                cms_dir = os.path.join(prob_dir, "cms")
                if os.path.exists(cms_dir):
                    for filename in os.listdir(cms_dir):
                        if not filename.endswith(".bin"):
                            continue
                        
                        try:
                            sketch_id = filename.split(".")[0]
                            with open(os.path.join(cms_dir, filename), "rb") as f:
                                cms_data = f.read()
                                self.count_min_sketches[sketch_id] = CountMinSketch.deserialize(cms_data)
                                logger.debug(f"Loaded Count-Min Sketch for {sketch_id}")
                        except Exception as e:
                            logger.error(f"Error loading Count-Min Sketch {filename}: {e}")
            
            # Load MinHash signatures
            if self.minhash_enabled:
                minhash_dir = os.path.join(prob_dir, "minhash")
                if os.path.exists(minhash_dir):
                    for filename in os.listdir(minhash_dir):
                        if not filename.endswith(".bin"):
                            continue
                        
                        try:
                            signature_id = filename.split(".")[0]
                            with open(os.path.join(minhash_dir, filename), "rb") as f:
                                minhash_data = f.read()
                                self.minhash_signatures[signature_id] = MinHash.deserialize(minhash_data)
                                logger.debug(f"Loaded MinHash signature for {signature_id}")
                        except Exception as e:
                            logger.error(f"Error loading MinHash signature {filename}: {e}")
                            
        except Exception as e:
            logger.error(f"Error loading probabilistic data structures: {e}")
    
    def _save_probabilistic_data_structure(self, structure_type: str, identifier: str, 
                                          data_structure: Any) -> bool:
        """Save a probabilistic data structure to disk.
        
        Args:
            structure_type: Type of structure ("bloom", "hll", "cms", "minhash")
            identifier: Identifier for the specific structure instance
            data_structure: The data structure instance to serialize
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Don't save if serialization not enabled for this type
        if not self.enable_probabilistic:
            return False
            
        # Check type-specific serialization config
        if structure_type == "bloom" and not self.bloom_config.get("serialize", True):
            return False
        elif structure_type == "hll" and not self.hll_config.get("serialize", True):
            return False
        elif structure_type == "cms" and not self.cms_config.get("serialize", True):
            return False
        elif structure_type == "minhash" and not self.minhash_config.get("serialize", True):
            return False
            
        try:
            # Get path for this data structure
            path = self._get_probabilistic_data_path(structure_type, identifier)
            
            # Serialize the data structure
            serialized_data = data_structure.serialize()
            
            # Save to disk
            with open(path, "wb") as f:
                f.write(serialized_data)
                
            return True
            
        except Exception as e:
            logger.error(f"Error saving {structure_type} {identifier}: {e}")
            return False
    
    def _update_bloom_filters(self, cid: str) -> None:
        """Update Bloom filters with a new CID.
        
        This method updates both the global Bloom filter and any partition-specific
        filters to include the new CID, enabling fast negative lookups in the future.
        
        Args:
            cid: Content identifier to add to Bloom filters
        """
        try:
            # Create global Bloom filter if it doesn't exist
            if "global" not in self.bloom_filters:
                capacity = self.bloom_config.get("capacity", 10000)
                error_rate = self.bloom_config.get("error_rate", 0.01)
                
                # Create a new BloomFilter with specified capacity and error rate
                from ipfs_kit_py.cache.probabilistic_data_structures import BloomFilter
                self.bloom_filters["global"] = BloomFilter(capacity, error_rate)
                logger.debug(f"Created global Bloom filter with capacity {capacity} and error rate {error_rate}")
            
            # Add CID to global Bloom filter
            self.bloom_filters["global"].add(cid)
            
            # Update partition-specific filter if enabled
            if self.bloom_config.get("per_partition", True):
                # Determine which partition this CID belongs to
                partition_id = self.current_partition_id
                
                # Create partition filter if it doesn't exist
                if partition_id not in self.bloom_filters:
                    capacity = self.bloom_config.get("capacity", 10000)
                    error_rate = self.bloom_config.get("error_rate", 0.01)
                    
                    # Create a new BloomFilter with specified capacity and error rate
                    from ipfs_kit_py.cache.probabilistic_data_structures import BloomFilter
                    self.bloom_filters[partition_id] = BloomFilter(capacity, error_rate)
                    logger.debug(f"Created Bloom filter for partition {partition_id}")
                
                # Add CID to partition filter
                self.bloom_filters[partition_id].add(cid)
            
            # Occasionally save the updated filters (5% chance)
            if random.random() < 0.05:
                # Save global filter
                self._save_probabilistic_data_structure("bloom", "global", self.bloom_filters["global"])
                
                # Save partition filter
                if self.bloom_config.get("per_partition", True) and partition_id in self.bloom_filters:
                    self._save_probabilistic_data_structure(
                        "bloom", f"partition_{partition_id}", self.bloom_filters[partition_id]
                    )
            
        except Exception as e:
            logger.warning(f"Failed to update Bloom filters for CID {cid}: {e}")
    
    def _update_frequency_statistics(self, key: str, action: str) -> None:
        """Update frequency statistics using Count-Min Sketch.
        
        This method tracks frequency of occurrences for different keys using the
        Count-Min Sketch data structure, enabling efficient frequency estimation
        with bounded error and constant space.
        
        Args:
            key: The key to update statistics for (e.g., "mimetype:image/jpeg")
            action: The action being performed ("add", "access", "delete")
        """
        if not self.cms_enabled or not self.count_min_sketches:
            return
            
        try:
            # For column-specific keys, extract the column name
            column = key.split(":", 1)[0] if ":" in key else "default"
            
            # If we don't have a sketch for this column yet, create one
            if column not in self.count_min_sketches:
                # Initialize with configuration parameters
                width = self.cms_config.get("width", 2048)
                depth = self.cms_config.get("depth", 5)
                
                # Create new Count-Min Sketch
                from ipfs_kit_py.cache.probabilistic_data_structures import CountMinSketch
                self.count_min_sketches[column] = CountMinSketch(width, depth)
                logger.debug(f"Created Count-Min Sketch for column {column}")
            
            # Update the sketch based on the action
            if action == "add":
                # New item added
                self.count_min_sketches[column].add(key)
            elif action == "access":
                # Existing item accessed
                self.count_min_sketches[column].add(key)
            elif action == "delete":
                # Item deleted (no direct way to remove from CMS, but we can track deletions)
                deletion_key = f"{key}:deleted"
                self.count_min_sketches[column].add(deletion_key)
            
            # Save the sketch occasionally
            if random.random() < 0.01:  # 1% chance
                self._save_probabilistic_data_structure(
                    "count_min_sketch", column, self.count_min_sketches[column]
                )
                
        except Exception as e:
            logger.warning(f"Failed to update frequency statistics for {key}: {e}")
    
    def _update_cardinality_statistics(self, field_name: str, field_value: Any, cid: str) -> None:
        """Update cardinality statistics using HyperLogLog.
        
        This method tracks the approximate number of distinct values for fields using
        the HyperLogLog algorithm, enabling memory-efficient cardinality estimation.
        
        Args:
            field_name: Name of the field to track (e.g., "mimetype")
            field_value: Value of the field (e.g., "image/jpeg")
            cid: Content identifier associated with this value
        """
        if not self.hll_enabled:
            return
            
        try:
            # Create a combined key for this field value
            key = f"{field_name}:{field_value}"
            
            # Initialize HLL counter for this field if it doesn't exist
            if field_name not in self.hyperloglog_counters:
                # Get precision from config (higher = more accurate but uses more memory)
                precision = self.hll_config.get("precision", 14)
                
                # Create a new HyperLogLog counter with specified precision
                from ipfs_kit_py.cache.probabilistic_data_structures import HyperLogLog
                self.hyperloglog_counters[field_name] = HyperLogLog(precision)
                logger.debug(f"Created HyperLogLog counter for field {field_name} with precision {precision}")
            
            # Add CID to the HLL counter for this field
            self.hyperloglog_counters[field_name].add(cid)
            
            # Save the counter occasionally
            if random.random() < 0.02:  # 2% chance
                self._save_probabilistic_data_structure(
                    "hyperloglog", field_name, self.hyperloglog_counters[field_name]
                )
                
        except Exception as e:
            logger.warning(f"Failed to update cardinality statistics for {field_name}: {e}")
            
    def _save_probabilistic_data_structures(self) -> None:
        """Save all probabilistic data structures to disk.
        
        This method persists all active probabilistic data structures to disk for
        recovery after restart. It is called periodically and during clean shutdown.
        """
        try:
            # Save Bloom filters
            if self.bloom_enabled and self.bloom_filters:
                # Save global filter if it exists
                if "global" in self.bloom_filters:
                    self._save_probabilistic_data_structure("bloom", "global", self.bloom_filters["global"])
                
                # Save partition filters
                if self.bloom_config.get("per_partition", True):
                    for partition_id, bloom_filter in self.bloom_filters.items():
                        if partition_id != "global":  # Skip global filter, already saved
                            self._save_probabilistic_data_structure(
                                "bloom", f"partition_{partition_id}", bloom_filter
                            )
            
            # Save HyperLogLog counters
            if self.hll_enabled and self.hyperloglog_counters:
                for column, counter in self.hyperloglog_counters.items():
                    self._save_probabilistic_data_structure("hyperloglog", column, counter)
            
            # Save Count-Min Sketches
            if self.cms_enabled and self.count_min_sketches:
                for column, sketch in self.count_min_sketches.items():
                    self._save_probabilistic_data_structure("count_min_sketch", column, sketch)
            
            # Save MinHash signatures
            if self.minhash_enabled and self.minhash_signatures:
                self._save_probabilistic_data_structure("minhash", "signatures", self.minhash_signatures)
                
            logger.info("Successfully saved all probabilistic data structures")
            
        except Exception as e:
            logger.error(f"Failed to save probabilistic data structures: {e}")
            
    def find_similar_content(self, cid: str, threshold: float = None) -> List[Dict[str, Any]]:
        """Find content similar to a given CID using MinHash signatures.
        
        This method uses MinHash signatures to efficiently estimate Jaccard similarity
        between content items, enabling fast similarity search without comparing
        entire content.
        
        Args:
            cid: Content identifier to find similar content for
            threshold: Similarity threshold (0.0-1.0), defaults to value in config
            
        Returns:
            List of similar content items with similarity scores
        """
        if not self.minhash_enabled or not self.minhash_signatures:
            return []
            
        # Use default threshold from config if not specified
        if threshold is None:
            threshold = self.minhash_config.get("similarity_threshold", 0.7)
            
        try:
            # Get the MinHash signature for this CID
            signature = self.minhash_signatures.get(cid)
            if not signature:
                logger.warning(f"No MinHash signature found for CID {cid}")
                return []
                
            # Find similar signatures
            similar_items = []
            
            # MinHash comparison for each known signature
            for other_cid, other_signature in self.minhash_signatures.items():
                if other_cid == cid:
                    continue  # Skip self-comparison
                    
                # Calculate Jaccard similarity using MinHash
                from ipfs_kit_py.cache.probabilistic_data_structures import MinHash
                similarity = MinHash.estimate_similarity(signature, other_signature)
                
                # Add to results if above threshold
                if similarity >= threshold:
                    similar_items.append({
                        "cid": other_cid,
                        "similarity": similarity
                    })
            
            # Sort by similarity (descending)
            similar_items.sort(key=lambda x: x["similarity"], reverse=True)
            
            return similar_items
            
        except Exception as e:
            logger.error(f"Error finding similar content for CID {cid}: {e}")
            return []
    
    def _estimate_result_cardinality(self, query_filters: List[Tuple[str, str, Any]]) -> Dict[str, Any]:
        """Estimate the cardinality of a query result using HyperLogLog.
        
        This method uses the HyperLogLog counters to estimate how many records
        will match a given query, enabling query optimization with minimal overhead.
        
        Args:
            query_filters: List of filter conditions in format (field, op, value)
            
        Returns:
            Dictionary with cardinality estimation and confidence metrics
        """
        if not self.hll_enabled or not self.hyperloglog_counters:
            return {"estimate": None, "confidence": None}
            
        try:
            estimates = []
            
            # Analyze each filter condition
            for field, op, value in query_filters:
                # Only equality filters can use HLL cardinality estimation
                if op == "==" and field in self.hyperloglog_counters:
                    # Get HLL counter for this field
                    counter = self.hyperloglog_counters[field]
                    
                    # Get estimated count of distinct values
                    total_distinct = counter.count()
                    
                    # Add this condition's estimate
                    estimates.append({
                        "field": field,
                        "value": value,
                        "estimate": total_distinct,
                        "confidence": 1.04 / math.sqrt(2 ** counter.precision)  # Standard HLL error formula
                    })
            
            # If we couldn't make any estimates, return None
            if not estimates:
                return {"estimate": None, "confidence": None}
                
            # Combine estimates (simplified approach - in practice would need more sophisticated cardinality modeling)
            final_estimate = min(e["estimate"] for e in estimates)
            
            return {
                "estimate": final_estimate,
                "confidence": min(e["confidence"] for e in estimates),
                "conditions_analyzed": len(estimates),
                "total_conditions": len(query_filters)
            }
            
        except Exception as e:
            logger.error(f"Error estimating query cardinality: {e}")
            return {"estimate": None, "confidence": None, "error": str(e)}
        
    @beta_api(since="0.19.0")
    def _get_current_time_partition(self) -> str:
        """Get the current time partition string based on configuration.
        
        Returns:
            Time partition string (e.g., "2023-04-05" for day partitioning)
        """
        config = self.advanced_partitioning_config["time_partitioning"]
        interval = config.get("interval", "day")
        fmt = config.get("format", "%Y-%m-%d")
        
        now = datetime.datetime.now()
        
        if interval == "hour":
            partition_dt = now.replace(minute=0, second=0, microsecond=0)
        elif interval == "day":
            partition_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif interval == "week":
            # Start of the week (Monday)
            partition_dt = now - datetime.timedelta(days=now.weekday())
            partition_dt = partition_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif interval == "month":
            partition_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif interval == "year":
            partition_dt = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Default to day if invalid interval
            partition_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
        return partition_dt.strftime(fmt)
        
    @beta_api(since="0.19.0")
    def _get_partition_path_for_record(self, record: Dict[str, Any]) -> str:
        """Determine the appropriate partition path for a record based on partitioning strategy.
        
        Args:
            record: Record with metadata to store
            
        Returns:
            Path string for the appropriate partition
        """
        if self.partitioning_strategy == "default":
            # Default sequential partitioning
            return self._get_partition_path(self.current_partition_id)
            
        elif self.partitioning_strategy == "time":
            # Time-based partitioning
            config = self.advanced_partitioning_config["time_partitioning"]
            column = config.get("column", "added_timestamp")
            fmt = config.get("format", "%Y-%m-%d")
            
            # Get timestamp value from record
            timestamp_value = record.get(column)
            if timestamp_value is None:
                # Default to current partition if no timestamp
                return os.path.join(self.directory, f"time_{self.current_time_partition}.parquet")
                
            # Convert timestamp to datetime
            if isinstance(timestamp_value, (int, float)):
                # Assume milliseconds since epoch
                dt = datetime.datetime.fromtimestamp(timestamp_value / 1000)
            elif isinstance(timestamp_value, datetime.datetime):
                dt = timestamp_value
            else:
                # Default to current partition if invalid format
                return os.path.join(self.directory, f"time_{self.current_time_partition}.parquet")
                
            # Format according to interval
            time_key = dt.strftime(fmt)
            return os.path.join(self.directory, f"time_{time_key}.parquet")
            
        elif self.partitioning_strategy == "content_type":
            # Content-type based partitioning
            config = self.advanced_partitioning_config["content_type_partitioning"]
            column = config.get("column", "mimetype")
            default_partition = config.get("default_partition", "unknown")
            group_similar = config.get("group_similar", True)
            
            # Get content type from record
            content_type = record.get(column, default_partition)
            
            if not content_type or content_type == "":
                content_type = default_partition
                
            # Normalize content type if grouping similar types
            if group_similar:
                content_type = self._normalize_content_type(content_type)
                
            return os.path.join(self.directory, f"type_{content_type}.parquet")
            
        elif self.partitioning_strategy == "size":
            # Size-based partitioning
            config = self.advanced_partitioning_config["size_partitioning"]
            column = config.get("column", "size_bytes")
            boundaries = config.get("boundaries", [10240, 102400, 1048576, 10485760])
            labels = config.get("labels", ["tiny", "small", "medium", "large", "xlarge"])
            
            # Get size from record
            size = record.get(column, 0)
            if not isinstance(size, (int, float)):
                size = 0
                
            # Determine size category
            category_index = 0
            for i, boundary in enumerate(boundaries):
                if size >= boundary:
                    category_index = i + 1
                else:
                    break
                    
            # Get appropriate label
            if category_index < len(labels):
                size_label = labels[category_index]
            else:
                size_label = labels[-1]  # Use last label if beyond all boundaries
                
            return os.path.join(self.directory, f"size_{size_label}.parquet")
            
        elif self.partitioning_strategy == "access_pattern":
            # Access pattern partitioning
            config = self.advanced_partitioning_config["access_pattern_partitioning"]
            column = config.get("column", "heat_score")
            boundaries = config.get("boundaries", [0.1, 0.5, 0.9])
            labels = config.get("labels", ["cold", "warm", "hot", "critical"])
            
            # Get heat score from record
            heat_score = record.get(column, 0.0)
            if not isinstance(heat_score, (int, float)):
                heat_score = 0.0
                
            # Determine heat category
            category_index = 0
            for i, boundary in enumerate(boundaries):
                if heat_score >= boundary:
                    category_index = i + 1
                else:
                    break
                    
            # Get appropriate label
            if category_index < len(labels):
                heat_label = labels[category_index]
            else:
                heat_label = labels[-1]  # Use last label if beyond all boundaries
                
            return os.path.join(self.directory, f"access_{heat_label}.parquet")
            
        elif self.partitioning_strategy == "hybrid":
            # Hybrid partitioning (hierarchical)
            config = self.advanced_partitioning_config["hybrid_partitioning"]
            primary = config.get("primary", "time")
            secondary = config.get("secondary", "content_type")
            
            # Temporarily switch to primary strategy to get primary path
            original_strategy = self.partitioning_strategy
            self.partitioning_strategy = primary
            primary_path = self._get_partition_path_for_record(record)
            
            # Extract the primary part (filename without extension)
            primary_key = os.path.splitext(os.path.basename(primary_path))[0]
            
            # Temporarily switch to secondary strategy to get secondary path
            self.partitioning_strategy = secondary
            secondary_path = self._get_partition_path_for_record(record)
            
            # Extract the secondary part
            secondary_key = os.path.splitext(os.path.basename(secondary_path))[0]
            
            # Restore original strategy
            self.partitioning_strategy = original_strategy
            
            # Combine primary and secondary
            return os.path.join(self.directory, f"{primary_key}_{secondary_key}.parquet")
            
        else:
            # Unknown strategy, fall back to default
            return self._get_partition_path(self.current_partition_id)
    
    @beta_api(since="0.19.0")
    def _normalize_content_type(self, content_type: str) -> str:
        """Normalize content type for grouping similar types.
        
        Args:
            content_type: Original content type (MIME type)
            
        Returns:
            Normalized content type category
        """
        if not content_type or content_type == "":
            return "unknown"
            
        # Extract major type
        major_type = content_type.split('/')[0].lower()
        
        # Group similar types
        if major_type in ('image', 'video', 'audio', 'text', 'application'):
            # For common major types, use the major type
            return major_type
            
        # For subtypes of application, extract more specific categories
        if '/' in content_type:
            subtype = content_type.split('/')[1].lower()
            
            # PDF files
            if 'pdf' in subtype:
                return 'document_pdf'
                
            # Office documents
            if any(x in subtype for x in ['word', 'excel', 'powerpoint', 'msword', 'spreadsheet', 'presentation']):
                return 'document_office'
                
            # Web content
            if any(x in subtype for x in ['html', 'xml', 'json', 'javascript', 'css']):
                return 'document_web'
                
            # Archives
            if any(x in subtype for x in ['zip', 'tar', 'gzip', 'compressed', 'archive']):
                return 'archive'
                
            # Executables
            if any(x in subtype for x in ['executable', 'x-msdownload', 'x-msdos-program']):
                return 'executable'
                
        # Default to the original type if no specific category applies
        return 'other'
        
    @beta_api(since="0.19.0")
    def _update_partitioning(self) -> None:
        """Update partitioning information based on current strategy.
        
        This method is called periodically to update partition information,
        especially for time-based partitioning where the current partition
        may change based on the current time.
        """
        if self.partitioning_strategy == "time":
            # Update current time partition
            new_time_partition = self._get_current_time_partition()
            
            if new_time_partition != self.current_time_partition:
                logger.info(f"Time partition changed from {self.current_time_partition} to {new_time_partition}")
                
                # Flush current in-memory batch before switching partitions
                if self.modified_since_sync and self.in_memory_batch is not None:
                    self._write_current_partition()
                    
                # Update current time partition
                self.current_time_partition = new_time_partition
                self.in_memory_batch = None
                
                # Clean up old partitions if needed
                self._cleanup_old_time_partitions()
        
    @beta_api(since="0.19.0")
    def _cleanup_old_time_partitions(self) -> None:
        """Clean up old time partitions according to retention policy.
        
        This maintains the configured maximum number of time partitions,
        removing the oldest partitions when the limit is exceeded.
        """
        if self.partitioning_strategy != "time":
            return
            
        config = self.advanced_partitioning_config["time_partitioning"]
        max_partitions = config.get("max_partitions", 90)
        
        # Find all time partitions
        time_pattern = re.compile(r'time_(.+)\.parquet$')
        time_partitions = []
        
        for filename in os.listdir(self.directory):
            match = time_pattern.match(filename)
            if match:
                time_key = match.group(1)
                filepath = os.path.join(self.directory, filename)
                stat = os.stat(filepath)
                
                time_partitions.append({
                    'key': time_key,
                    'path': filepath,
                    'mtime': stat.st_mtime,
                    'size': stat.st_size
                })
                
        # If we have more than the max, sort by time key and remove oldest
        if len(time_partitions) > max_partitions:
            # Sort by key (works well for time-based format strings)
            time_partitions.sort(key=lambda x: x['key'])
            
            # Remove oldest partitions
            partitions_to_remove = time_partitions[:-max_partitions]
            
            for partition in partitions_to_remove:
                try:
                    logger.info(f"Removing old time partition: {partition['path']}")
                    os.remove(partition['path'])
                except Exception as e:
                    logger.warning(f"Failed to remove old partition {partition['path']}: {e}")
        time_partitions = []
        
        for filename in os.listdir(self.directory):
            match = time_pattern.match(filename)
            if match:
                time_key = match.group(1)
                filepath = os.path.join(self.directory, filename)
                stat = os.stat(filepath)
                
                time_partitions.append({
                    'key': time_key,
                    'path': filepath,
                    'mtime': stat.st_mtime,
                    'size': stat.st_size
                })
                
        # If we have more than the max, sort by time key and remove oldest
        if len(time_partitions) > max_partitions:
            # Sort by key (works well for time-based format strings)
            time_partitions.sort(key=lambda x: x['key'])
            
            # Remove oldest partitions
            partitions_to_remove = time_partitions[:-max_partitions]
            
            for partition in partitions_to_remove:
                try:
                    logger.info(f"Removing old time partition: {partition['path']}")
                    os.remove(partition['path'])
                except Exception as e:
                    logger.warning(f"Failed to remove old partition {partition['path']}: {e}")
                    
    @beta_api(since="0.19.0")
    def partition_by_time(self, column: str = "added_timestamp", interval: str = "day", 
                        max_partitions: int = 90, format: str = "%Y-%m-%d") -> Dict[str, Any]:
        """Switch to time-based partitioning strategy.
        
        This allows organizing data by temporal patterns, which is particularly
        effective for time-series data or datasets with natural time-based access
        patterns.
        
        Args:
            column: Column to partition by (must be a timestamp column)
            interval: Time interval for partitioning ("hour", "day", "week", "month", "year")
            max_partitions: Maximum number of partitions to keep (oldest are pruned)
            format: Datetime format string for partition naming
            
        Returns:
            Status dictionary
        """
        result = {
            "success": False,
            "operation": "partition_by_time",
            "timestamp": time.time()
        }
        
        try:
            # Update configuration
            self.partitioning_strategy = "time"
            self.advanced_partitioning_config["time_partitioning"] = {
                "interval": interval,
                "column": column,
                "format": format,
                "max_partitions": max_partitions
            }
            
            # Update current time partition
            self.current_time_partition = self._get_current_time_partition()
            
            # Flush current in-memory batch if needed
            if self.modified_since_sync and self.in_memory_batch is not None:
                self._write_current_partition()
                self.in_memory_batch = None
                
            # Since we've switched partitioning strategy, we need to refresh partition info
            self.partitions = self._discover_partitions()
            
            # Set success and include configuration in result
            result["success"] = True
            result["config"] = self.advanced_partitioning_config["time_partitioning"]
            result["current_partition"] = self.current_time_partition
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error switching to time-based partitioning: {e}")
            
        return result
        
    @beta_api(since="0.19.0")
    def partition_by_content_type(self, column: str = "mimetype", 
                                default_partition: str = "unknown",
                                max_types: int = 20,
                                group_similar: bool = True) -> Dict[str, Any]:
        """Switch to content-type based partitioning strategy.
        
        This organizes data by content type, which is useful for workloads that
        have distinct access patterns for different content types.
        
        Args:
            column: Column to partition by (content type/MIME type)
            default_partition: Default partition for items without a content type
            max_types: Maximum number of content type partitions
            group_similar: Whether to group similar content types together
            
        Returns:
            Status dictionary
        """
        result = {
            "success": False,
            "operation": "partition_by_content_type",
            "timestamp": time.time()
        }
        
        try:
            # Update configuration
            self.partitioning_strategy = "content_type"
            self.advanced_partitioning_config["content_type_partitioning"] = {
                "column": column,
                "default_partition": default_partition,
                "max_types": max_types,
                "group_similar": group_similar
            }
            
            # Flush current in-memory batch if needed
            if self.modified_since_sync and self.in_memory_batch is not None:
                self._write_current_partition()
                self.in_memory_batch = None
                
            # Since we've switched partitioning strategy, we need to refresh partition info
            self.partitions = self._discover_partitions()
            
            # Set success and include configuration in result
            result["success"] = True
            result["config"] = self.advanced_partitioning_config["content_type_partitioning"]
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error switching to content-type partitioning: {e}")
            
        return result
        
    @beta_api(since="0.19.0")
    def partition_by_size(self, column: str = "size_bytes",
                        boundaries: List[int] = None,
                        labels: List[str] = None) -> Dict[str, Any]:
        """Switch to size-based partitioning strategy.
        
        This groups content based on size, which helps optimize storage and retrieval
        for different content sizes.
        
        Args:
            column: Column to partition by (size in bytes)
            boundaries: Size boundaries in bytes (default: [10KB, 100KB, 1MB, 10MB])
            labels: Labels for each size range
            
        Returns:
            Status dictionary
        """
        result = {
            "success": False,
            "operation": "partition_by_size",
            "timestamp": time.time()
        }
        
        try:
            # Set default boundaries and labels if not provided
            if boundaries is None:
                boundaries = [10240, 102400, 1048576, 10485760]
                
            if labels is None:
                labels = ["tiny", "small", "medium", "large", "xlarge"]
                
            # Ensure we have one more label than boundaries
            if len(labels) != len(boundaries) + 1:
                raise ValueError(f"Need {len(boundaries) + 1} labels for {len(boundaries)} boundaries")
                
            # Update configuration
            self.partitioning_strategy = "size"
            self.advanced_partitioning_config["size_partitioning"] = {
                "column": column,
                "boundaries": boundaries,
                "labels": labels
            }
            
            # Flush current in-memory batch if needed
            if self.modified_since_sync and self.in_memory_batch is not None:
                self._write_current_partition()
                self.in_memory_batch = None
                
            # Since we've switched partitioning strategy, we need to refresh partition info
            self.partitions = self._discover_partitions()
            
            # Set success and include configuration in result
            result["success"] = True
            result["config"] = self.advanced_partitioning_config["size_partitioning"]
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error switching to size-based partitioning: {e}")
            
        return result
        
    @beta_api(since="0.19.0")
    def partition_by_access_pattern(self, column: str = "heat_score",
                                  boundaries: List[float] = None,
                                  labels: List[str] = None) -> Dict[str, Any]:
        """Switch to access pattern partitioning strategy.
        
        This groups content based on access patterns, which helps optimize
        for frequent vs. infrequent access patterns.
        
        Args:
            column: Column to partition by (heat score or access frequency)
            boundaries: Score boundaries (default: [0.1, 0.5, 0.9])
            labels: Labels for each access pattern range
            
        Returns:
            Status dictionary
        """
        result = {
            "success": False,
            "operation": "partition_by_access_pattern",
            "timestamp": time.time()
        }
        
        try:
            # Set default boundaries and labels if not provided
            if boundaries is None:
                boundaries = [0.1, 0.5, 0.9]
                
            if labels is None:
                labels = ["cold", "warm", "hot", "critical"]
                
            # Ensure we have one more label than boundaries
            if len(labels) != len(boundaries) + 1:
                raise ValueError(f"Need {len(boundaries) + 1} labels for {len(boundaries)} boundaries")
                
            # Update configuration
            self.partitioning_strategy = "access_pattern"
            self.advanced_partitioning_config["access_pattern_partitioning"] = {
                "column": column,
                "boundaries": boundaries,
                "labels": labels
            }
            
            # Flush current in-memory batch if needed
            if self.modified_since_sync and self.in_memory_batch is not None:
                self._write_current_partition()
                self.in_memory_batch = None
                
            # Since we've switched partitioning strategy, we need to refresh partition info
            self.partitions = self._discover_partitions()
            
            # Set success and include configuration in result
            result["success"] = True
            result["config"] = self.advanced_partitioning_config["access_pattern_partitioning"]
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error switching to access pattern partitioning: {e}")
            
        return result
        
    @beta_api(since="0.19.0")
    def partition_hybrid(self, primary: str = "time", secondary: str = "content_type") -> Dict[str, Any]:
        """Switch to hybrid partitioning strategy.
        
        This combines multiple partitioning strategies in a hierarchical manner,
        allowing for more complex organization of data.
        
        Args:
            primary: Primary partitioning strategy
            secondary: Secondary partitioning strategy
            
        Returns:
            Status dictionary
        """
        result = {
            "success": False,
            "operation": "partition_hybrid",
            "timestamp": time.time()
        }
        
        try:
            # Validate strategies
            valid_strategies = ["time", "content_type", "size", "access_pattern"]
            if primary not in valid_strategies or secondary not in valid_strategies:
                raise ValueError(f"Both primary and secondary strategies must be one of: {valid_strategies}")
                
            if primary == secondary:
                raise ValueError(f"Primary and secondary strategies must be different")
                
            # Update configuration
            self.partitioning_strategy = "hybrid"
            self.advanced_partitioning_config["hybrid_partitioning"] = {
                "primary": primary,
                "secondary": secondary
            }
            
            # Flush current in-memory batch if needed
            if self.modified_since_sync and self.in_memory_batch is not None:
                self._write_current_partition()
                self.in_memory_batch = None
                
            # Since we've switched partitioning strategy, we need to refresh partition info
            self.partitions = self._discover_partitions()
            
            # Set success and include configuration in result
            result["success"] = True
            result["config"] = self.advanced_partitioning_config["hybrid_partitioning"]
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error switching to hybrid partitioning: {e}")
            
        return result
        
    @experimental_api(since="0.19.0")
    async def async_batch_put_metadata_zero_copy(self, metadata_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Async version of batch_put_metadata_zero_copy.
        
        This method provides a non-blocking way to update metadata for multiple CIDs using
        shared memory and the Arrow C Data Interface, ideal for high-throughput asynchronous
        workflows.
        
        Args:
            metadata_dict: Dictionary mapping CIDs to their metadata
            
        Returns:
            Dictionary with operation results
        """
        if not self.has_asyncio:
            # Fallback to synchronous version through thread pool if asyncio not available
            future = self.thread_pool.submit(self.batch_put_metadata_zero_copy, metadata_dict)
            return future.result()
            
        # If asyncio is available, run in executor to avoid blocking
        loop = anyio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, 
            lambda: self.batch_put_metadata_zero_copy(metadata_dict)
        )

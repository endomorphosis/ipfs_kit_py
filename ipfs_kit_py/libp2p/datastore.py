"""
Persistent Datastore module for IPFS Kit libp2p.

This module provides a disk-persistent datastore for the libp2p Kademlia DHT,
extending the in-memory DHTDatastore with persistence capabilities. It ensures
that DHT data survives node restarts and allows for larger datasets than
would fit in memory alone.

The implementation includes:
1. Transaction-safe file operations for crash resilience
2. Efficient index and journal structure for quick lookups
3. LRU-based eviction policy for memory management
4. Automatic background synchronization
5. Heat-based prioritization for frequently accessed data

Usage:
    from ipfs_kit_py.libp2p.datastore import PersistentDHTDatastore
    
    # Create a persistent datastore
    datastore = PersistentDHTDatastore(
        path="/path/to/datastore",
        max_items=10000,
        sync_interval=300  # 5 minutes
    )
    
    # Use like regular DHTDatastore
    datastore.put("key1", b"value1", publisher="peer1")
    value = datastore.get("key1")
    providers = datastore.get_providers("key1")
"""

import os
import json
import time
import shutil
import logging
import threading
import anyio
from typing import Dict, List, Set, Optional, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor

# Configure logger
logger = logging.getLogger(__name__)

class PersistentDHTDatastore:
    """
    Disk-persistent datastore for the libp2p Kademlia DHT.
    
    This class extends the functionality of the in-memory DHTDatastore with
    persistent storage capabilities, allowing DHT data to survive across
    restarts while maintaining compatibility with the original interface.
    
    The implementation uses a combination of in-memory caching for performance
    and disk storage for persistence, with automatic synchronization between
    the two.
    """
    
    def __init__(self, 
                 path: str = None, 
                 max_items: int = 1000,
                 max_age: int = 86400,
                 sync_interval: int = 300,
                 flush_threshold: int = 50):
        """
        Initialize a new persistent DHT datastore.
        
        Args:
            path: Directory path for persistent storage
            max_items: Maximum items to keep in memory
            max_age: Maximum age of items in seconds (default: 24 hours)
            sync_interval: How often to sync to disk in seconds (default: 5 minutes)
            flush_threshold: Number of changes before automatic flush
        """
        # Initialize storage parameters
        self.max_items = max_items
        self.max_age = max_age
        self.sync_interval = sync_interval
        self.flush_threshold = flush_threshold
        
        # Set up storage path
        if path is None:
            # Default to ~/.ipfs_kit/datastore
            home_dir = os.path.expanduser("~")
            self.storage_path = os.path.join(home_dir, ".ipfs_kit", "datastore")
        else:
            self.storage_path = os.path.expanduser(path)
            
        # Create directory if needed
        os.makedirs(self.storage_path, exist_ok=True)
        os.makedirs(os.path.join(self.storage_path, "data"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_path, "temp"), exist_ok=True)
        
        # In-memory caches
        self.data: Dict[str, Dict[str, Any]] = {}
        self.providers: Dict[str, Set[str]] = {}
        
        # Transaction state
        self.changes_since_flush = 0
        self._pending_writes: Dict[str, Dict[str, Any]] = {}
        self._locks = {
            "data": threading.RLock(),
            "index": threading.RLock(),
            "sync": threading.RLock()
        }
        
        # For background operations
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._sync_task = None
        self._running = False
        
        # Metadata
        self.stats = {
            "total_items": 0,
            "total_providers": 0,
            "get_operations": 0,
            "put_operations": 0,
            "hits": 0,
            "misses": 0,
            "last_sync": 0,
            "total_syncs": 0,
            "flush_operations": 0,
            "load_operations": 0
        }
        
        # Check for existing data and load if available
        self._load_from_disk()
        
        # Start background sync
        self._start_sync_task()

    def put(self, key: str, value: bytes, publisher: str = None) -> bool:
        """
        Store a value in the datastore.
        
        Args:
            key: The key to store the value under
            value: The value to store
            publisher: Optional ID of the peer that published the value
            
        Returns:
            True if the value was stored, False otherwise
        """
        try:
            with self._locks["data"]:
                # Track operation
                self.stats["put_operations"] += 1
                
                # Create item metadata
                now = time.time()
                item = {
                    "value": value,
                    "timestamp": now,
                    "expires": now + self.max_age,
                    "publisher": publisher,
                    "access_count": 0,
                    "last_access": now
                }
                
                # Check if we're at capacity and this is a new key
                if (len(self.data) >= self.max_items and key not in self.data):
                    # Remove the oldest item
                    self._evict_one()
                
                # Store the value and update stats
                self.data[key] = item
                self.stats["total_items"] = len(self.data)
                
                # Track publisher if provided
                if publisher:
                    self._add_provider(key, publisher)
                
                # Mark for writing to disk
                self._pending_writes[key] = item
                self.changes_since_flush += 1
                
                # Auto-flush if threshold reached
                if self.changes_since_flush >= self.flush_threshold:
                    self._executor.submit(self._flush_to_disk)
                
                return True
                
        except Exception as e:
            logger.error(f"Error in datastore put: {e}")
            return False

    def get(self, key: str) -> Optional[bytes]:
        """
        Retrieve a value from the datastore.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The value, or None if not found or expired
        """
        try:
            with self._locks["data"]:
                # Track operation
                self.stats["get_operations"] += 1
                
                # Check if key exists in memory
                item = self.data.get(key)
                if item is None:
                    # Check if it exists on disk but not in memory
                    disk_item = self._load_item_from_disk(key)
                    if disk_item is None:
                        self.stats["misses"] += 1
                        return None
                    else:
                        # Add to memory cache
                        item = disk_item
                        self.data[key] = item
                
                # Check if the item has expired
                if item["expires"] < time.time():
                    # Remove expired item
                    del self.data[key]
                    self._pending_writes[key] = None  # Mark for deletion
                    self.changes_since_flush += 1
                    self.stats["total_items"] = len(self.data)
                    self.stats["misses"] += 1
                    return None
                
                # Update access statistics
                item["access_count"] += 1
                item["last_access"] = time.time()
                
                # Return value and count hit
                self.stats["hits"] += 1
                return item["value"]
                
        except Exception as e:
            logger.error(f"Error in datastore get: {e}")
            return None

    def has(self, key: str) -> bool:
        """
        Check if a key exists in the datastore.
        
        Args:
            key: The key to check
            
        Returns:
            True if the key exists and has not expired, False otherwise
        """
        try:
            with self._locks["data"]:
                # Check if key exists in memory
                item = self.data.get(key)
                if item is None:
                    # Check if it exists on disk but not in memory
                    disk_item = self._load_item_from_disk(key)
                    if disk_item is None:
                        return False
                    else:
                        # Add to memory cache
                        item = disk_item
                        self.data[key] = item
                
                # Check if the item has expired
                if item["expires"] < time.time():
                    # Remove expired item
                    del self.data[key]
                    self._pending_writes[key] = None  # Mark for deletion
                    self.changes_since_flush += 1
                    self.stats["total_items"] = len(self.data)
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error in datastore has: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a key from the datastore.
        
        Args:
            key: The key to delete
            
        Returns:
            True if the key was deleted, False otherwise
        """
        try:
            with self._locks["data"]:
                # Check if key exists
                if key not in self.data:
                    # Check if it exists on disk
                    item_path = os.path.join(self.storage_path, "data", f"{key}.json")
                    if not os.path.exists(item_path):
                        return False
                
                # Remove from memory
                if key in self.data:
                    del self.data[key]
                    
                # Remove from providers
                if key in self.providers:
                    del self.providers[key]
                    self.stats["total_providers"] = sum(len(providers) for providers in self.providers.values())
                
                # Mark for deletion on disk
                self._pending_writes[key] = None
                self.changes_since_flush += 1
                self.stats["total_items"] = len(self.data)
                
                # Auto-flush if threshold reached
                if self.changes_since_flush >= self.flush_threshold:
                    self._executor.submit(self._flush_to_disk)
                
                return True
                
        except Exception as e:
            logger.error(f"Error in datastore delete: {e}")
            return False

    def get_providers(self, key: str) -> List[str]:
        """
        Get the providers for a key.
        
        Args:
            key: The key to get providers for
            
        Returns:
            A list of provider peer IDs
        """
        try:
            with self._locks["data"]:
                # Check if key exists in memory providers
                providers = list(self.providers.get(key, set()))
                
                # If no providers in memory, check disk
                if not providers:
                    # Check if providers exist on disk
                    disk_providers = self._load_providers_from_disk(key)
                    if disk_providers:
                        self.providers[key] = set(disk_providers)
                        providers = disk_providers
                
                # Also check data store publisher
                item = self.data.get(key)
                if item is None:
                    # Try loading from disk
                    item = self._load_item_from_disk(key)
                    
                if item is not None:
                    # Check if not expired
                    if item["expires"] >= time.time():
                        publisher = item.get("publisher")
                        if publisher and publisher not in providers:
                            providers.append(publisher)
                
                return providers
                
        except Exception as e:
            logger.error(f"Error in get_providers: {e}")
            return []

    def add_provider(self, key: str, provider: str) -> bool:
        """
        Add a provider for a key.
        
        Args:
            key: The key the provider can provide
            provider: The provider's peer ID
            
        Returns:
            True if the provider was added, False otherwise
        """
        try:
            with self._locks["data"]:
                # Add to providers dictionary
                self._add_provider(key, provider)
                
                # Mark for writing to disk
                self.changes_since_flush += 1
                
                # Auto-flush if threshold reached
                if self.changes_since_flush >= self.flush_threshold:
                    self._executor.submit(self._flush_to_disk)
                
                return True
                
        except Exception as e:
            logger.error(f"Error in add_provider: {e}")
            return False
    
    def _add_provider(self, key: str, provider: str) -> None:
        """Internal method to add a provider to the in-memory store."""
        if key not in self.providers:
            self.providers[key] = set()
        
        # Add provider to set
        self.providers[key].add(provider)
        
        # Update stats
        self.stats["total_providers"] = sum(len(providers) for providers in self.providers.values())

    def remove_provider(self, key: str, provider: str) -> bool:
        """
        Remove a provider for a key.
        
        Args:
            key: The key the provider was providing
            provider: The provider's peer ID
            
        Returns:
            True if the provider was removed, False otherwise
        """
        try:
            with self._locks["data"]:
                # Check if key exists in providers
                if key not in self.providers:
                    return False
                
                # Check if provider exists
                if provider not in self.providers[key]:
                    return False
                
                # Remove provider
                self.providers[key].remove(provider)
                
                # If no more providers, remove key
                if not self.providers[key]:
                    del self.providers[key]
                
                # Update stats
                self.stats["total_providers"] = sum(len(providers) for providers in self.providers.values())
                
                # Mark for writing to disk
                self.changes_since_flush += 1
                
                # Auto-flush if threshold reached
                if self.changes_since_flush >= self.flush_threshold:
                    self._executor.submit(self._flush_to_disk)
                
                return True
                
        except Exception as e:
            logger.error(f"Error in remove_provider: {e}")
            return False

    def expire_old_data(self) -> int:
        """
        Remove expired data from the datastore.
        
        Returns:
            The number of items removed
        """
        try:
            with self._locks["data"]:
                now = time.time()
                expired_keys = [key for key, item in self.data.items() if item["expires"] < now]
                
                # Remove expired items
                for key in expired_keys:
                    del self.data[key]
                    self._pending_writes[key] = None  # Mark for deletion
                
                self.changes_since_flush += len(expired_keys)
                self.stats["total_items"] = len(self.data)
                
                # Auto-flush if threshold reached
                if self.changes_since_flush >= self.flush_threshold:
                    self._executor.submit(self._flush_to_disk)
                
                return len(expired_keys)
                
        except Exception as e:
            logger.error(f"Error in expire_old_data: {e}")
            return 0
    
    def _evict_one(self) -> bool:
        """
        Evict an item from memory using a heat-based approach.
        
        Returns:
            True if an item was evicted, False otherwise
        """
        if not self.data:
            return False
            
        # Find the "coldest" item based on access count, recency, and age
        now = time.time()
        
        min_score = float('inf')
        evict_key = None
        
        for key, item in self.data.items():
            # Skip items that have pending writes
            if key in self._pending_writes:
                continue
                
            # Calculate heat score
            access_count = item.get("access_count", 0)
            time_since_last_access = now - item.get("last_access", 0)
            
            # Items with zero access are the coldest
            if access_count == 0:
                score = 0
            else:
                # Normalize factors
                recency = 1.0 / (1.0 + time_since_last_access / 3600)  # Hours
                frequency = min(1.0, access_count / 10.0)  # Cap at 10 accesses
                
                # Combined score (higher means hotter)
                score = (recency * 0.6) + (frequency * 0.4)
            
            # Find item with lowest score
            if score < min_score:
                min_score = score
                evict_key = key
        
        # If we found an item to evict
        if evict_key:
            # Item should already be synchronized to disk
            del self.data[evict_key]
            return True
            
        return False

    def _start_sync_task(self) -> None:
        """Start the background synchronization task."""
        if self._running:
            return
            
        self._running = True
        
        def run_sync_loop():
            while self._running:
                try:
                    # Perform synchronization
                    if self.changes_since_flush > 0:
                        self._flush_to_disk()
                        
                    # Sleep until next sync
                    time.sleep(self.sync_interval)
                except Exception as e:
                    logger.error(f"Error in sync task: {e}")
                    # Sleep before retry
                    time.sleep(10)
        
        # Start thread
        self._sync_task = threading.Thread(target=run_sync_loop, daemon=True)
        self._sync_task.start()
        logger.info("Started datastore sync task")

    def stop(self) -> None:
        """Stop the datastore and ensure data is synchronized."""
        with self._locks["sync"]:
            if not self._running:
                return
                
            self._running = False
            
            # Ensure data is flushed
            try:
                self._flush_to_disk()
            except Exception as e:
                logger.error(f"Error flushing data during stop: {e}")
            
            # Shutdown executor
            self._executor.shutdown(wait=True)
            
            logger.info("Datastore stopped")

    def _flush_to_disk(self) -> bool:
        """
        Flush pending changes to disk.
        
        Returns:
            True if successful, False otherwise
        """
        with self._locks["sync"]:
            try:
                # Track operation
                self.stats["flush_operations"] += 1
                
                # Make a copy of pending writes
                with self._locks["data"]:
                    pending = self._pending_writes.copy()
                    self._pending_writes.clear()
                    self.changes_since_flush = 0
                
                # Process each pending write
                for key, item in pending.items():
                    if item is None:
                        # This is a deletion
                        self._delete_item_on_disk(key)
                    else:
                        # This is an update/insert
                        self._write_item_to_disk(key, item)
                
                # Also sync providers
                self._write_providers_index()
                
                # Update stats
                self.stats["last_sync"] = time.time()
                self.stats["total_syncs"] += 1
                
                return True
                
            except Exception as e:
                logger.error(f"Error flushing to disk: {e}")
                return False

    def _write_item_to_disk(self, key: str, item: Dict[str, Any]) -> bool:
        """
        Write an item to disk with transaction safety.
        
        Args:
            key: The key for the item
            item: The item to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare paths
            data_dir = os.path.join(self.storage_path, "data")
            temp_dir = os.path.join(self.storage_path, "temp")
            
            # Create a safe filename
            safe_key = self._safe_filename(key)
            
            # Temporary file
            temp_path = os.path.join(temp_dir, f"{safe_key}.json.tmp")
            
            # Final path
            final_path = os.path.join(data_dir, f"{safe_key}.json")
            
            # Prepare data for saving
            serializable_item = item.copy()
            
            # Convert bytes to base64 for JSON serialization
            if isinstance(serializable_item.get("value"), bytes):
                import base64
                serializable_item["value"] = base64.b64encode(serializable_item["value"]).decode('ascii')
                serializable_item["encoding"] = "base64"
            
            # Write to temporary file first
            with open(temp_path, 'w') as f:
                json.dump(serializable_item, f)
            
            # Move to final location (atomic on most filesystems)
            shutil.move(temp_path, final_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing item to disk: {e}")
            return False

    def _delete_item_on_disk(self, key: str) -> bool:
        """
        Delete an item from disk.
        
        Args:
            key: The key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare paths
            data_dir = os.path.join(self.storage_path, "data")
            
            # Create a safe filename
            safe_key = self._safe_filename(key)
            
            # Final path
            final_path = os.path.join(data_dir, f"{safe_key}.json")
            
            # Delete if exists
            if os.path.exists(final_path):
                os.remove(final_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting item from disk: {e}")
            return False

    def _load_item_from_disk(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Load an item from disk.
        
        Args:
            key: The key to load
            
        Returns:
            The item or None if not found
        """
        try:
            # Prepare paths
            data_dir = os.path.join(self.storage_path, "data")
            
            # Create a safe filename
            safe_key = self._safe_filename(key)
            
            # Final path
            final_path = os.path.join(data_dir, f"{safe_key}.json")
            
            # Check if file exists
            if not os.path.exists(final_path):
                return None
            
            # Read file
            with open(final_path, 'r') as f:
                item = json.load(f)
            
            # Convert value back from base64 if necessary
            if item.get("encoding") == "base64" and isinstance(item.get("value"), str):
                import base64
                item["value"] = base64.b64decode(item["value"])
            
            return item
            
        except Exception as e:
            logger.error(f"Error loading item from disk: {e}")
            return None

    def _write_providers_index(self) -> bool:
        """
        Write provider information to disk.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._locks["data"]:
                # Prepare paths
                data_dir = os.path.join(self.storage_path, "data")
                temp_dir = os.path.join(self.storage_path, "temp")
                
                # Temporary file
                temp_path = os.path.join(temp_dir, "providers.json.tmp")
                
                # Final path
                final_path = os.path.join(data_dir, "providers.json")
                
                # Convert providers to serializable format
                serializable_providers = {}
                for key, providers_set in self.providers.items():
                    serializable_providers[key] = list(providers_set)
                
                # Write to temporary file first
                with open(temp_path, 'w') as f:
                    json.dump(serializable_providers, f)
                
                # Move to final location (atomic on most filesystems)
                shutil.move(temp_path, final_path)
                
                return True
                
        except Exception as e:
            logger.error(f"Error writing providers index: {e}")
            return False

    def _load_providers_from_disk(self, key: str = None) -> Union[Dict[str, List[str]], List[str], None]:
        """
        Load providers from disk.
        
        Args:
            key: Specific key to load providers for, or None for all
            
        Returns:
            Providers dictionary, provider list for key, or None if not found
        """
        try:
            # Prepare paths
            data_dir = os.path.join(self.storage_path, "data")
            
            # Final path
            final_path = os.path.join(data_dir, "providers.json")
            
            # Check if file exists
            if not os.path.exists(final_path):
                return {} if key is None else []
            
            # Read file
            with open(final_path, 'r') as f:
                providers_dict = json.load(f)
            
            # Return specific key or all
            if key is not None:
                return providers_dict.get(key, [])
            else:
                return providers_dict
                
        except Exception as e:
            logger.error(f"Error loading providers from disk: {e}")
            return {} if key is None else []

    def _load_from_disk(self) -> bool:
        """
        Load data from disk for initialization.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Track operation
            self.stats["load_operations"] += 1
            
            # First, check if we have data
            data_dir = os.path.join(self.storage_path, "data")
            
            # Load providers
            providers_dict = self._load_providers_from_disk()
            
            # Convert to internal format
            for key, providers_list in providers_dict.items():
                self.providers[key] = set(providers_list)
            
            # Update stats
            self.stats["total_providers"] = sum(len(providers) for providers in self.providers.values())
            
            # Load most recently accessed items up to max_items
            # This is more efficient than loading everything, especially for large datastores
            data_files = []
            for filename in os.listdir(data_dir):
                if filename.endswith('.json') and filename != 'providers.json':
                    file_path = os.path.join(data_dir, filename)
                    # Get last modified time as access time approximation
                    mtime = os.path.getmtime(file_path)
                    data_files.append((filename, mtime))
            
            # Sort by last modified time (most recent first)
            data_files.sort(key=lambda x: x[1], reverse=True)
            
            # Load up to max_items
            loaded_count = 0
            for filename, _ in data_files:
                if loaded_count >= self.max_items:
                    break
                    
                key = filename[:-5]  # Remove .json
                
                # Skip providers.json
                if key == 'providers':
                    continue
                    
                try:
                    # Extract original key
                    original_key = self._unsafe_key(key)
                    
                    # Load item
                    item = self._load_item_from_disk(original_key)
                    if item:
                        # Skip expired items
                        if item["expires"] < time.time():
                            continue
                            
                        # Add to memory
                        self.data[original_key] = item
                        loaded_count += 1
                except Exception as e:
                    logger.warning(f"Error loading item {key}: {e}")
            
            # Update stats
            self.stats["total_items"] = len(self.data)
            
            logger.info(f"Loaded {loaded_count} items and {self.stats['total_providers']} providers from disk")
            return True
            
        except Exception as e:
            logger.error(f"Error loading from disk: {e}")
            return False

    def _safe_filename(self, key: str) -> str:
        """Convert a key to a safe filename."""
        import re
        import hashlib
        
        # If key contains problematic characters, hash it
        if re.search(r'[^a-zA-Z0-9_.-]', key):
            return hashlib.sha256(key.encode()).hexdigest()
        
        return key

    def _unsafe_key(self, filename: str) -> str:
        """
        Convert a filename back to a key.
        
        This is a best-effort operation. If the filename was a hash,
        we can't recover the original key.
        """
        import re
        
        # Check if filename is a SHA-256 hash (hex, 64 chars)
        if re.match(r'^[a-f0-9]{64}$', filename):
            # This is a hash, we can't recover the original key
            return filename
        
        return filename

    def get_stats(self) -> Dict[str, Any]:
        """
        Get datastore statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._locks["data"]:
            stats_copy = self.stats.copy()
            stats_copy["hit_rate"] = (
                stats_copy["hits"] / (stats_copy["hits"] + stats_copy["misses"]) 
                if (stats_copy["hits"] + stats_copy["misses"]) > 0 else 0
            )
            return stats_copy

    async def async_get(self, key: str) -> Optional[bytes]:
        """
        Asynchronous version of get.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The value, or None if not found or expired
        """
        loop = anyio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get, key)

    async def async_put(self, key: str, value: bytes, publisher: str = None) -> bool:
        """
        Asynchronous version of put.
        
        Args:
            key: The key to store the value under
            value: The value to store
            publisher: Optional ID of the peer that published the value
            
        Returns:
            True if the value was stored, False otherwise
        """
        loop = anyio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: self.put(key, value, publisher)
        )

    async def async_flush(self) -> bool:
        """
        Asynchronous flush operation.
        
        Returns:
            True if successful, False otherwise
        """
        loop = anyio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._flush_to_disk)
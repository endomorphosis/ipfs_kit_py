"""
Filesystem Journal Backend Integrations for IPFS Kit.

This module provides backend integrations for the filesystem journal,
enabling it to work with multiple storage backends like memory cache,
disk cache, IPFS, IPFS cluster, S3, Storacha, Filecoin, HuggingFace,
and other backends through a unified interface.

This integration enables:
1. Tracking operations across multiple tiers in the storage hierarchy
2. Ensuring atomic operations with transaction safety
3. Providing consistent recovery mechanisms across backends
4. Supporting migration between storage tiers
"""

import os
import json
import time
import logging
import tempfile
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple, Set

from ipfs_kit_py.filesystem_journal import (
    FilesystemJournal,
    FilesystemJournalManager,
    JournalOperationType,
    JournalEntryStatus
)

# Check for Arrow availability
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

class StorageBackendType:
    """Enum-like class for storage backend types."""
    MEMORY = "memory"
    DISK = "disk"
    IPFS = "ipfs"
    IPFS_CLUSTER = "ipfs_cluster"
    S3 = "s3"
    STORACHA = "storacha"
    FILECOIN = "filecoin"
    HUGGINGFACE = "huggingface"
    LASSIE = "lassie"
    PARQUET = "parquet"
    ARROW = "arrow"

class TieredStorageJournalBackend:
    """
    Backend integration for tiered storage systems.

    This class extends the standard filesystem journal to work with
    tiered storage backends, tracking content movement between tiers,
    ensuring atomic operations, and supporting recovery across tiers.
    """

    def __init__(
        self,
        tiered_cache_manager,
        journal: Optional[FilesystemJournal] = None,
        wal = None,
        journal_base_path: str = "~/.ipfs_kit/tiered_journal",
        auto_recovery: bool = True,
        sync_interval: int = 5,
        checkpoint_interval: int = 60,
        max_journal_size: int = 1000
    ):
        """
        Initialize the tiered storage backend.

        Args:
            tiered_cache_manager: TieredCacheManager instance
            journal: Optional existing FilesystemJournal instance
            wal: Optional WAL instance for additional safety
            journal_base_path: Base directory for journal storage
            auto_recovery: Whether to automatically recover on startup
            sync_interval: Interval in seconds for syncing journal to disk
            checkpoint_interval: Interval in seconds for creating checkpoints
            max_journal_size: Maximum journal entries before checkpoint
        """
        self.tiered_cache = tiered_cache_manager
        self.wal = wal

        # Use provided journal or create a new one
        self.journal = journal
        if self.journal is None:
            self.journal = FilesystemJournal(
                base_path=journal_base_path,
                sync_interval=sync_interval,
                checkpoint_interval=checkpoint_interval,
                max_journal_size=max_journal_size,
                auto_recovery=auto_recovery,
                wal=wal
            )

        # Additional state for tiered backend tracking
        self.content_locations = {}  # CID -> {tier, timestamp, metadata}
        self.tier_stats = {
            StorageBackendType.MEMORY: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.DISK: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.IPFS: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.IPFS_CLUSTER: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.S3: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.STORACHA: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.FILECOIN: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.HUGGINGFACE: {"operations": 0, "bytes_stored": 0, "items": 0},
            StorageBackendType.LASSIE: {"operations": 0, "bytes_stored": 0, "items": 0}
        }

        # Load state from journal if auto_recovery is enabled
        if auto_recovery:
            self._recover_tier_state()

        logger.info(f"Tiered storage journal backend initialized")

    def _recover_tier_state(self) -> None:
        """Recover tier state from journal."""
        # Get the current filesystem state from the journal
        fs_state = self.journal.get_fs_state()

        # Process all paths to recover tier information
        for path, state in fs_state.items():
            # Extract CID and tier info
            if state.get("type") == "file" and "cid" in state:
                cid = state["cid"]
                metadata = state.get("metadata", {})

                # Check for tier info in metadata
                tier = metadata.get("storage_tier", "unknown")
                if tier != "unknown":
                    # Recover the tier location
                    self.content_locations[cid] = {
                        "tier": tier,
                        "timestamp": state.get("modified_at", time.time()),
                        "path": path,
                        "metadata": metadata
                    }

                    # Update tier stats
                    if tier in self.tier_stats:
                        self.tier_stats[tier]["items"] += 1
                        self.tier_stats[tier]["bytes_stored"] += state.get("size", 0)

        logger.info(f"Recovered tier state from journal: {len(self.content_locations)} content items")

    def store_content(
        self,
        content: bytes,
        cid: Optional[str] = None,
        target_tier: str = StorageBackendType.MEMORY,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store content in the specified tier with journaling.

        Args:
            content: Content bytes to store
            cid: Optional existing CID (will be calculated if not provided)
            target_tier: Target storage tier (from StorageBackendType)
            metadata: Optional metadata for the content

        Returns:
            Result dictionary
        """
        # Begin transaction to ensure atomic operations
        transaction_id = self.journal.begin_transaction()

        try:
            # Prepare result and metadata
            if metadata is None:
                metadata = {}

            # Add storage tier to metadata
            metadata["storage_tier"] = target_tier

            # Add journal entry
            entry = self.journal.add_journal_entry(
                operation_type=JournalOperationType.CREATE,
                path=f"cid://{cid or 'pending'}",
                data={
                    "is_directory": False,
                    "size": len(content),
                    "target_tier": target_tier,
                    "metadata": metadata
                }
            )

            # Integrate with WAL if available
            if self.wal:
                wal_result = self.wal.add_operation(
                    operation_type="store",
                    backend=target_tier,
                    parameters={
                        "size": len(content),
                        "journal_entry_id": entry["entry_id"]
                    }
                )

                # Link the WAL operation ID
                entry["data"]["wal_operation_id"] = wal_result.get("operation_id")

            # Perform actual storage operation with tiered cache
            result = self.tiered_cache.put(cid or str(uuid.uuid4()), content, metadata)

            # Update journal entry with CID if one was generated
            if "cid" in result and not cid:
                cid = result["cid"]
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.PENDING,
                    result={"cid": cid}
                )

                # Update path in entry to include actual CID
                self.journal.add_journal_entry(
                    operation_type=JournalOperationType.RENAME,
                    path=f"cid://pending",
                    data={"new_path": f"cid://{cid}"}
                )

            # Update our content location tracking
            self.content_locations[cid] = {
                "tier": target_tier,
                "timestamp": time.time(),
                "path": f"cid://{cid}",
                "metadata": metadata
            }

            # Update tier stats
            if target_tier in self.tier_stats:
                self.tier_stats[target_tier]["operations"] += 1
                self.tier_stats[target_tier]["bytes_stored"] += len(content)
                self.tier_stats[target_tier]["items"] += 1

            # Mark entry as completed
            self.journal.update_entry_status(
                entry_id=entry["entry_id"],
                status=JournalEntryStatus.COMPLETED,
                result=result
            )

            # Commit the transaction
            self.journal.commit_transaction()

            return {
                "success": True,
                "cid": cid,
                "tier": target_tier,
                "size": len(content),
                "transaction_id": transaction_id,
                "entry_id": entry["entry_id"],
                "timestamp": time.time()
            }

        except Exception as e:
            # Rollback transaction on error
            self.journal.rollback_transaction()

            logger.error(f"Error storing content in tier {target_tier}: {e}")
            return {
                "success": False,
                "tier": target_tier,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def retrieve_content(self, cid: str) -> Dict[str, Any]:
        """
        Retrieve content by CID with journaling.

        Args:
            cid: Content ID to retrieve

        Returns:
            Result dictionary with content and metadata
        """
        try:
            # Add journal entry
            entry = self.journal.add_journal_entry(
                operation_type=JournalOperationType.METADATA,
                path=f"cid://{cid}",
                data={"operation": "retrieve"}
            )

            # Retrieve content from tiered cache
            content = self.tiered_cache.get(cid)

            # Get content location and tier if available
            location_info = self.content_locations.get(cid, {"tier": "unknown"})
            tier = location_info.get("tier", "unknown")

            if content is not None:
                result = {
                    "success": True,
                    "cid": cid,
                    "content": content,
                    "size": len(content),
                    "tier": tier,
                    "timestamp": time.time()
                }

                # Update tier stats
                if tier in self.tier_stats:
                    self.tier_stats[tier]["operations"] += 1

                # Update journal entry
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result={"size": len(content), "tier": tier}
                )

                return result
            else:
                # Content not found
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.FAILED,
                    result={"error": "Content not found"}
                )

                return {
                    "success": False,
                    "cid": cid,
                    "error": "Content not found"
                }

        except Exception as e:
            logger.error(f"Error retrieving content {cid}: {e}")
            return {
                "success": False,
                "cid": cid,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def move_content_to_tier(
        self,
        cid: str,
        target_tier: str,
        keep_in_source: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Move content between tiers with journaling.

        Args:
            cid: Content ID to move
            target_tier: Target storage tier (from StorageBackendType)
            keep_in_source: Whether to keep content in source tier
            metadata: Optional metadata updates

        Returns:
            Result dictionary
        """
        # Begin transaction to ensure atomic operations
        transaction_id = self.journal.begin_transaction()

        try:
            # Start with an empty metadata dict if none provided
            if metadata is None:
                metadata = {}

            # Get current location information
            source_info = self.content_locations.get(cid, {"tier": "unknown"})
            source_tier = source_info.get("tier", "unknown")

            # Add journal entry
            entry = self.journal.add_journal_entry(
                operation_type=JournalOperationType.METADATA,
                path=f"cid://{cid}",
                data={
                    "operation": "move_tier",
                    "source_tier": source_tier,
                    "target_tier": target_tier,
                    "keep_in_source": keep_in_source,
                    "metadata": metadata
                }
            )

            # Retrieve content from current tier
            content = self.tiered_cache.get(cid)

            if content is None:
                # Content not found
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.FAILED,
                    result={"error": "Content not found"}
                )

                # Rollback transaction
                self.journal.rollback_transaction()

                return {
                    "success": False,
                    "cid": cid,
                    "error": "Content not found"
                }

            # Prepare metadata for target tier
            tier_metadata = source_info.get("metadata", {}).copy()
            tier_metadata.update(metadata)
            tier_metadata["storage_tier"] = target_tier
            tier_metadata["previous_tier"] = source_tier
            tier_metadata["moved_timestamp"] = time.time()

            # Store in target tier
            if target_tier in [StorageBackendType.MEMORY, StorageBackendType.DISK]:
                # For memory and disk tiers, we use the TieredCacheManager
                logger.info(f"Moving content {cid} to tier {target_tier} using TieredCacheManager")

                # The TieredCacheManager.put method will handle tier placement
                # Based on size and access patterns
                put_result = self.tiered_cache.put(cid, content, tier_metadata)

                # Manual promotion to ensure content is in specified tier
                # This is necessary because TieredCacheManager might choose a different tier
                if target_tier == StorageBackendType.MEMORY:
                    if hasattr(self.tiered_cache, "memory_cache"):
                        self.tiered_cache.memory_cache.put(cid, content)
                        logger.info(f"Explicitly promoted content {cid} to memory cache")

            elif target_tier == StorageBackendType.IPFS:
                # Store in IPFS
                logger.info(f"Moving content {cid} to IPFS tier")

                # Use TieredCacheManager.put with IPFS tier metadata
                put_result = self.tiered_cache.put(cid, content, tier_metadata)

                # Try to pin the content to ensure it stays in IPFS
                if hasattr(self.tiered_cache, "ipfs_pin") and callable(self.tiered_cache.ipfs_pin):
                    pin_result = self.tiered_cache.ipfs_pin(cid)
                    logger.info(f"Pinned content {cid} in IPFS: {pin_result}")

            elif target_tier == StorageBackendType.IPFS_CLUSTER:
                # Store in IPFS Cluster
                logger.info(f"Moving content {cid} to IPFS Cluster tier")

                # TODO: Implement IPFS Cluster specific storage logic
                # This would typically involve pinning the content to the cluster

                # Use regular TieredCacheManager.put as fallback
                put_result = self.tiered_cache.put(cid, content, tier_metadata)

                # Try to pin to cluster if method exists
                if hasattr(self.tiered_cache, "cluster_pin") and callable(self.tiered_cache.cluster_pin):
                    cluster_result = self.tiered_cache.cluster_pin(cid)
                    logger.info(f"Pinned content {cid} to IPFS Cluster: {cluster_result}")

            elif target_tier == StorageBackendType.S3:
                # Store in S3
                logger.info(f"Moving content {cid} to S3 tier")

                # Try to use a specialized S3 storage method if available
                s3_result = None

                if hasattr(self.tiered_cache, "s3_put") and callable(self.tiered_cache.s3_put):
                    s3_result = self.tiered_cache.s3_put(cid, content, tier_metadata)
                    logger.info(f"Stored content {cid} in S3 using s3_put: {s3_result}")
                else:
                    # Use general put method with S3 tier metadata
                    put_result = self.tiered_cache.put(cid, content, tier_metadata)
                    s3_result = put_result

            elif target_tier == StorageBackendType.STORACHA:
                # Store in Storacha/Web3.Storage
                logger.info(f"Moving content {cid} to Storacha tier")

                # Try to use specialized Storacha storage method if available
                storacha_result = None

                if hasattr(self.tiered_cache, "storacha_put") and callable(self.tiered_cache.storacha_put):
                    storacha_result = self.tiered_cache.storacha_put(cid, content, tier_metadata)
                    logger.info(f"Stored content {cid} in Storacha using storacha_put: {storacha_result}")
                else:
                    # Use general put method with Storacha tier metadata
                    put_result = self.tiered_cache.put(cid, content, tier_metadata)
                    storacha_result = put_result

            elif target_tier == StorageBackendType.FILECOIN:
                # Store in Filecoin
                logger.info(f"Moving content {cid} to Filecoin tier")

                # Try to use specialized Filecoin storage method if available
                filecoin_result = None

                if hasattr(self.tiered_cache, "filecoin_put") and callable(self.tiered_cache.filecoin_put):
                    filecoin_result = self.tiered_cache.filecoin_put(cid, content, tier_metadata)
                    logger.info(f"Stored content {cid} in Filecoin using filecoin_put: {filecoin_result}")
                else:
                    # Use general put method with Filecoin tier metadata
                    put_result = self.tiered_cache.put(cid, content, tier_metadata)
                    filecoin_result = put_result

            elif target_tier == StorageBackendType.HUGGINGFACE:
                # Store in HuggingFace Hub
                logger.info(f"Moving content {cid} to HuggingFace tier")

                # Try to use specialized HuggingFace storage method if available
                hf_result = None

                if hasattr(self.tiered_cache, "huggingface_put") and callable(self.tiered_cache.huggingface_put):
                    hf_result = self.tiered_cache.huggingface_put(cid, content, tier_metadata)
                    logger.info(f"Stored content {cid} in HuggingFace using huggingface_put: {hf_result}")
                else:
                    # Use general put method with HuggingFace tier metadata
                    put_result = self.tiered_cache.put(cid, content, tier_metadata)
                    hf_result = put_result

            else:
                # Default case - use general put method
                logger.info(f"Moving content {cid} to tier {target_tier} using general put method")
                put_result = self.tiered_cache.put(cid, content, tier_metadata)

            # Remove from source tier if needed
            if not keep_in_source and source_tier != "unknown" and source_tier != target_tier:
                logger.info(f"Removing content {cid} from source tier {source_tier}")

                # Update the journal entry for the removal
                self.journal.add_journal_entry(
                    operation_type=JournalOperationType.DELETE,
                    path=f"tier://{source_tier}/{cid}",
                    data={"cid": cid, "tier": source_tier}
                )

                # Tier-specific removal logic
                if source_tier == StorageBackendType.MEMORY:
                    # Remove from memory cache
                    if hasattr(self.tiered_cache, "memory_cache"):
                        memory_cache = self.tiered_cache.memory_cache
                        if hasattr(memory_cache, "evict"):
                            memory_cache.evict(cid)
                        # Alternative method names that might exist
                        elif hasattr(memory_cache, "remove"):
                            memory_cache.remove(cid)
                        elif hasattr(memory_cache, "delete"):
                            memory_cache.delete(cid)

                elif source_tier == StorageBackendType.DISK:
                    # Remove from disk cache
                    if hasattr(self.tiered_cache, "disk_cache"):
                        disk_cache = self.tiered_cache.disk_cache
                        if hasattr(disk_cache, "remove"):
                            disk_cache.remove(cid)
                        # Alternative method names
                        elif hasattr(disk_cache, "delete"):
                            disk_cache.delete(cid)
                        elif hasattr(disk_cache, "evict"):
                            disk_cache.evict(cid)

                elif source_tier == StorageBackendType.IPFS:
                    # Unpin from IPFS
                    if hasattr(self.tiered_cache, "ipfs_unpin") and callable(self.tiered_cache.ipfs_unpin):
                        unpin_result = self.tiered_cache.ipfs_unpin(cid)
                        logger.info(f"Unpinned content {cid} from IPFS: {unpin_result}")

                elif source_tier == StorageBackendType.IPFS_CLUSTER:
                    # Unpin from IPFS Cluster
                    if hasattr(self.tiered_cache, "cluster_unpin") and callable(self.tiered_cache.cluster_unpin):
                        cluster_result = self.tiered_cache.cluster_unpin(cid)
                        logger.info(f"Unpinned content {cid} from IPFS Cluster: {cluster_result}")

                elif source_tier == StorageBackendType.S3:
                    # Remove from S3
                    if hasattr(self.tiered_cache, "s3_delete") and callable(self.tiered_cache.s3_delete):
                        s3_result = self.tiered_cache.s3_delete(cid)
                        logger.info(f"Removed content {cid} from S3: {s3_result}")

                elif source_tier == StorageBackendType.STORACHA:
                    # Remove from Storacha
                    if hasattr(self.tiered_cache, "storacha_delete") and callable(self.tiered_cache.storacha_delete):
                        storacha_result = self.tiered_cache.storacha_delete(cid)
                        logger.info(f"Removed content {cid} from Storacha: {storacha_result}")

                # Update tier stats
                if source_tier in self.tier_stats:
                    self.tier_stats[source_tier]["items"] = max(0, self.tier_stats[source_tier]["items"] - 1)
                    content_size = source_info.get("metadata", {}).get("size", 0)
                    self.tier_stats[source_tier]["bytes_stored"] = max(
                        0, self.tier_stats[source_tier]["bytes_stored"] - content_size
                    )

            # Update content location tracking
            self.content_locations[cid] = {
                "tier": target_tier,
                "timestamp": time.time(),
                "path": f"cid://{cid}",
                "metadata": tier_metadata
            }

            # Update tier stats
            if target_tier in self.tier_stats:
                self.tier_stats[target_tier]["operations"] += 1
                self.tier_stats[target_tier]["items"] += 1
                self.tier_stats[target_tier]["bytes_stored"] += len(content)

            # Mark journal entry as completed
            self.journal.update_entry_status(
                entry_id=entry["entry_id"],
                status=JournalEntryStatus.COMPLETED,
                result={
                    "source_tier": source_tier,
                    "target_tier": target_tier,
                    "size": len(content)
                }
            )

            # Commit the transaction
            self.journal.commit_transaction()

            return {
                "success": True,
                "cid": cid,
                "source_tier": source_tier,
                "target_tier": target_tier,
                "size": len(content),
                "transaction_id": transaction_id,
                "entry_id": entry["entry_id"],
                "timestamp": time.time()
            }

        except Exception as e:
            # Rollback transaction on error
            self.journal.rollback_transaction()

            logger.error(f"Error moving content {cid} to tier {target_tier}: {e}")
            return {
                "success": False,
                "cid": cid,
                "target_tier": target_tier,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def get_content_location(self, cid: str) -> Dict[str, Any]:
        """
        Get the current location and metadata for content.

        Args:
            cid: Content ID to query

        Returns:
            Dictionary with location information
        """
        try:
            # Check our content location tracking
            if cid in self.content_locations:
                location_info = self.content_locations[cid].copy()
                location_info["success"] = True
                location_info["cid"] = cid

                # Add quick access check
                location_info["available"] = self.tiered_cache.get(cid) is not None

                return location_info

            # If we don't have it in our tracking, try to find it
            content = self.tiered_cache.get(cid)
            if content is not None:
                # We found the content, but didn't have tracking info
                # Create a new location record based on where we found it
                if hasattr(self.tiered_cache, "memory_cache") and self.tiered_cache.memory_cache.contains(cid):
                    tier = StorageBackendType.MEMORY
                elif hasattr(self.tiered_cache, "disk_cache") and self.tiered_cache.disk_cache.contains(cid):
                    tier = StorageBackendType.DISK
                else:
                    # Default to unknown tier
                    tier = "unknown"

                # Create new tracking entry
                self.content_locations[cid] = {
                    "tier": tier,
                    "timestamp": time.time(),
                    "path": f"cid://{cid}",
                    "metadata": {
                        "storage_tier": tier,
                        "size": len(content)
                    }
                }

                # Update tier stats
                if tier in self.tier_stats:
                    self.tier_stats[tier]["items"] += 1
                    self.tier_stats[tier]["bytes_stored"] += len(content)

                location_info = self.content_locations[cid].copy()
                location_info["success"] = True
                location_info["cid"] = cid
                location_info["available"] = True

                return location_info

            # Content not found
            return {
                "success": False,
                "cid": cid,
                "error": "Content not found"
            }

        except Exception as e:
            logger.error(f"Error getting location for content {cid}: {e}")
            return {
                "success": False,
                "cid": cid,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def get_tier_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all storage tiers.

        Returns:
            Dictionary with tier statistics
        """
        return self.tier_stats.copy()

class TieredJournalManagerFactory:
    """
    Factory for creating and configuring tiered journal managers.

    This factory provides convenient methods for creating and initializing
    the appropriate journal backend for different storage configurations.
    """

    @staticmethod
    def create_for_tiered_cache(
        tiered_cache_manager,
        wal=None,
        journal_base_path: str = "~/.ipfs_kit/tiered_journal",
        auto_recovery: bool = True,
        **kwargs
    ) -> TieredStorageJournalBackend:
        """
        Create a journal backend integrated with a TieredCacheManager.

        Args:
            tiered_cache_manager: TieredCacheManager instance
            wal: Optional WAL instance
            journal_base_path: Base directory for journal storage
            auto_recovery: Whether to automatically recover on startup
            **kwargs: Additional configuration options

        Returns:
            Configured TieredStorageJournalBackend instance
        """
        return TieredStorageJournalBackend(
            tiered_cache_manager=tiered_cache_manager,
            wal=wal,
            journal_base_path=journal_base_path,
            auto_recovery=auto_recovery,
            **kwargs
        )

    @staticmethod
    def create_from_high_level_api(
        api_instance,
        wal=None,
        journal_base_path: str = "~/.ipfs_kit/tiered_journal",
        auto_recovery: bool = True,
        **kwargs
    ) -> TieredStorageJournalBackend:
        """
        Create a journal backend integrated with a high-level API instance.

        Args:
            api_instance: High-level API instance
            wal: Optional WAL instance
            journal_base_path: Base directory for journal storage
            auto_recovery: Whether to automatically recover on startup
            **kwargs: Additional configuration options

        Returns:
            Configured TieredStorageJournalBackend instance
        """
        # Extract tiered cache from API instance
        tiered_cache = None

        # Try different attribute paths
        try:
            if api_instance.tiered_cache is not None:
                tiered_cache = api_instance.tiered_cache
            elif api_instance.cache is not None:
                tiered_cache = api_instance.cache
            elif hasattr(api_instance, "fs_api") and api_instance.fs_api.cache is not None:
                tiered_cache = api_instance.fs_api.cache
        except (AttributeError, TypeError):
            # Handle case where attributes don't exist
            pass

        # If no tiered cache found, raise error
        if tiered_cache is None:
            raise ValueError("Could not find TieredCacheManager in API instance")

        return TieredStorageJournalBackend(
            tiered_cache_manager=tiered_cache,
            wal=wal,
            journal_base_path=journal_base_path,
            auto_recovery=auto_recovery,
            **kwargs
        )


# Export key classes
__all__ = [
    'StorageBackendType',
    'TieredStorageJournalBackend',
    'TieredJournalManagerFactory'
]
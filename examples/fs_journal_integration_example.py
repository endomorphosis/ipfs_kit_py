"""
Filesystem Journal Integration with Tiered Storage Example.

This example demonstrates how to use the filesystem journal 
with various storage backends, enabling transaction safety across storage tiers.

Key features demonstrated:
1. Integration with TieredCacheManager
2. Content movement between storage tiers with journal tracking
3. Transaction safety and rollback
4. Recovery from journal

Usage:
$ python -m examples.fs_journal_integration_example
"""

import os
import time
import tempfile
import logging
import random

from ipfs_kit_py.tiered_cache import TieredCacheManager
from ipfs_kit_py.fs_journal_backends import (
    StorageBackendType,
    TieredStorageJournalBackend,
    TieredJournalManagerFactory
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fs_journal_example")

def run_example():
    """Run the filesystem journal integration example."""
    logger.info("Starting filesystem journal integration example")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Set up paths
        cache_dir = os.path.join(temp_dir, "cache")
        journal_dir = os.path.join(temp_dir, "journal")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Create tiered cache manager
        cache_config = {
            'memory_cache_size': 10 * 1024 * 1024,  # 10MB for testing
            'local_cache_size': 20 * 1024 * 1024,  # 20MB for testing
            'local_cache_path': cache_dir,
        }
        tiered_cache = TieredCacheManager(config=cache_config)
        
        # Create journal backend
        journal_backend = TieredJournalManagerFactory.create_for_tiered_cache(
            tiered_cache_manager=tiered_cache,
            journal_base_path=journal_dir,
            auto_recovery=True
        )
        
        # 1. Store content in different tiers
        logger.info("1. Storing content in different tiers")
        
        # Create some test content
        content1 = b"Test content 1 - small size for memory tier" * 10  # ~450 bytes
        content2 = b"Test content 2 - medium size for disk tier" * 1000  # ~45KB
        content3 = os.urandom(1024 * 1024)  # 1MB random data for IPFS tier
        
        # Store in memory tier
        logger.info("Storing content1 in memory tier")
        result1 = journal_backend.store_content(
            content=content1,
            target_tier=StorageBackendType.MEMORY,
            metadata={"description": "Small content for memory tier"}
        )
        cid1 = result1["cid"]
        logger.info(f"Stored content1 with CID: {cid1}")
        
        # Store in disk tier
        logger.info("Storing content2 in disk tier")
        result2 = journal_backend.store_content(
            content=content2,
            target_tier=StorageBackendType.DISK,
            metadata={"description": "Medium content for disk tier"}
        )
        cid2 = result2["cid"]
        logger.info(f"Stored content2 with CID: {cid2}")
        
        # Store in IPFS tier (if available)
        try:
            logger.info("Storing content3 in IPFS tier")
            result3 = journal_backend.store_content(
                content=content3,
                target_tier=StorageBackendType.IPFS,
                metadata={"description": "Large content for IPFS tier"}
            )
            cid3 = result3["cid"]
            logger.info(f"Stored content3 with CID: {cid3}")
            ipfs_available = True
        except Exception as e:
            logger.warning(f"IPFS tier not available: {e}")
            cid3 = None
            ipfs_available = False
        
        # 2. Retrieve content from different tiers
        logger.info("\n2. Retrieving content from different tiers")
        
        # Retrieve from memory tier
        logger.info(f"Retrieving content with CID: {cid1}")
        retrieve_result1 = journal_backend.retrieve_content(cid1)
        if retrieve_result1["success"]:
            logger.info(f"Retrieved content with CID {cid1} from {retrieve_result1['tier']} tier")
            logger.info(f"Content size: {len(retrieve_result1['content'])} bytes")
        else:
            logger.error(f"Failed to retrieve content with CID {cid1}: {retrieve_result1.get('error')}")
        
        # Retrieve from disk tier
        logger.info(f"Retrieving content with CID: {cid2}")
        retrieve_result2 = journal_backend.retrieve_content(cid2)
        if retrieve_result2["success"]:
            logger.info(f"Retrieved content with CID {cid2} from {retrieve_result2['tier']} tier")
            logger.info(f"Content size: {len(retrieve_result2['content'])} bytes")
        else:
            logger.error(f"Failed to retrieve content with CID {cid2}: {retrieve_result2.get('error')}")
        
        # Retrieve from IPFS tier if available
        if ipfs_available and cid3:
            logger.info(f"Retrieving content with CID: {cid3}")
            retrieve_result3 = journal_backend.retrieve_content(cid3)
            if retrieve_result3["success"]:
                logger.info(f"Retrieved content with CID {cid3} from {retrieve_result3['tier']} tier")
                logger.info(f"Content size: {len(retrieve_result3['content'])} bytes")
            else:
                logger.error(f"Failed to retrieve content with CID {cid3}: {retrieve_result3.get('error')}")
        
        # 3. Move content between tiers
        logger.info("\n3. Moving content between tiers")
        
        # Move content1 from memory to disk
        logger.info(f"Moving content with CID {cid1} from memory to disk tier")
        move_result1 = journal_backend.move_content_to_tier(
            cid=cid1,
            target_tier=StorageBackendType.DISK,
            keep_in_source=False  # Remove from source tier
        )
        if move_result1["success"]:
            logger.info(f"Moved content from {move_result1['source_tier']} to {move_result1['target_tier']}")
        else:
            logger.error(f"Failed to move content: {move_result1.get('error')}")
        
        # Move content2 from disk to memory
        logger.info(f"Moving content with CID {cid2} from disk to memory tier")
        move_result2 = journal_backend.move_content_to_tier(
            cid=cid2,
            target_tier=StorageBackendType.MEMORY,
            keep_in_source=True  # Keep in source tier (replicate)
        )
        if move_result2["success"]:
            logger.info(f"Moved content from {move_result2['source_tier']} to {move_result2['target_tier']}")
            logger.info(f"Keeping content in source tier: {move_result2['source_tier']}")
        else:
            logger.error(f"Failed to move content: {move_result2.get('error')}")
        
        # 4. Get content locations and tier stats
        logger.info("\n4. Getting content locations and tier stats")
        
        # Get content location for cid1
        location1 = journal_backend.get_content_location(cid1)
        logger.info(f"Content with CID {cid1} is in tier: {location1.get('tier')}")
        
        # Get content location for cid2
        location2 = journal_backend.get_content_location(cid2)
        logger.info(f"Content with CID {cid2} is in tier: {location2.get('tier')}")
        
        # Get tier stats
        tier_stats = journal_backend.get_tier_stats()
        logger.info("Tier statistics:")
        for tier, stats in tier_stats.items():
            if stats["items"] > 0:
                logger.info(f"  {tier}: {stats['items']} items, {stats['bytes_stored']} bytes stored, {stats['operations']} operations")
        
        # 5. Demonstrate transaction safety with rollback
        logger.info("\n5. Demonstrating transaction safety with rollback")
        
        # Create a storage operation that will fail
        try:
            logger.info("Attempting to store with an invalid tier (should trigger rollback)")
            result_fail = journal_backend.store_content(
                content=b"This should fail",
                target_tier="invalid_tier",
                metadata={"description": "This should fail"}
            )
            logger.info(f"Result: {result_fail}")
        except Exception as e:
            logger.info(f"Got expected error: {e}")
            logger.info("Transaction should have been rolled back")
        
        # 6. Create a checkpoint and demonstrate recovery
        logger.info("\n6. Creating checkpoint and demonstrating recovery")
        
        # Create a checkpoint by closing the journal (forces checkpoint)
        journal_backend.journal.create_checkpoint()
        logger.info("Created checkpoint")
        
        # Create a new journal backend with auto-recovery enabled
        logger.info("Creating new journal backend with auto-recovery")
        new_backend = TieredJournalManagerFactory.create_for_tiered_cache(
            tiered_cache_manager=tiered_cache,
            journal_base_path=journal_dir,
            auto_recovery=True
        )
        
        # Verify recovery
        location1_after = new_backend.get_content_location(cid1)
        if location1_after["success"]:
            logger.info(f"Recovered location for CID {cid1}: {location1_after.get('tier')}")
        else:
            logger.warning(f"Failed to recover location for CID {cid1}")
        
        # Check tier stats after recovery
        recovered_stats = new_backend.get_tier_stats()
        logger.info("Tier statistics after recovery:")
        for tier, stats in recovered_stats.items():
            if stats["items"] > 0:
                logger.info(f"  {tier}: {stats['items']} items, {stats['bytes_stored']} bytes stored")
        
        logger.info("\nFilesystem journal integration example completed")

if __name__ == "__main__":
    try:
        run_example()
    except Exception as e:
        logger.exception(f"Exception in example: {e}")
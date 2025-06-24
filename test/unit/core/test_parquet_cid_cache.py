#!/usr/bin/env python
"""
Test script for ParquetCIDCache and multiformats CID generation.

This script tests the functionality we've implemented:
1. Creating valid CIDs using multiformats
2. Storing and retrieving metadata in ParquetCIDCache
3. Checking if CIDs exist in the cache
4. Updating access statistics
"""

import os
import time
import logging
import json
from ipfs_kit_py.ipfs_multiformats import create_cid_from_bytes
from ipfs_kit_py.cache.schema_column_optimization import ParquetCIDCache

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_multiformats_cid():
    """Test creating valid CIDs using multiformats."""
    logger.info("Testing multiformats CID generation...")

    # Test with different content
    test_contents = [
        b"test content 1",
        b"test content 2",
        b"a" * 1000,  # Larger content
        b"binary content with \x00\x01\x02\x03"  # Binary content
    ]

    for content in test_contents:
        cid = create_cid_from_bytes(content)
        logger.info(f"Content ({len(content)} bytes): {content[:20]}...")
        logger.info(f"  Generated CID: {cid}")

        # Verify CID format (should start with 'b' for CIDv1 base32)
        assert cid.startswith("b"), f"Invalid CID format: {cid}"

        # Generate again to verify deterministic behavior
        cid2 = create_cid_from_bytes(content)
        assert cid == cid2, f"CID generation is not deterministic: {cid} != {cid2}"

    logger.info("Multiformats CID generation test passed!")
    return True

def test_parquet_cid_cache():
    """Test ParquetCIDCache functionality."""
    logger.info("Testing ParquetCIDCache...")

    # Create a test cache directory
    cache_dir = "/tmp/test_parquet_cid_cache"
    os.makedirs(cache_dir, exist_ok=True)

    # Initialize ParquetCIDCache
    cache = ParquetCIDCache(cache_dir)

    # Test storing and retrieving metadata
    test_cid = create_cid_from_bytes(b"test content for cache")
    test_metadata = {
        "size": 1024,
        "timestamp": time.time(),
        "filename": "test_file.txt",
        "content_type": "text/plain",
        "pinned": False
    }

    # Store metadata
    result = cache.put(test_cid, test_metadata)
    assert result, "Failed to store metadata"
    logger.info(f"Stored metadata for CID: {test_cid}")

    # Check if CID exists in cache
    exists = cache.exists(test_cid)
    assert exists, f"CID {test_cid} should exist in cache"
    logger.info(f"CID exists in cache: {exists}")

    # Retrieve metadata
    retrieved_metadata = cache.get(test_cid)
    assert retrieved_metadata, f"Failed to retrieve metadata for CID {test_cid}"
    assert retrieved_metadata["size"] == test_metadata["size"], "Metadata size mismatch"
    assert retrieved_metadata["filename"] == test_metadata["filename"], "Metadata filename mismatch"
    logger.info(f"Retrieved metadata: {retrieved_metadata}")

    # Test updating access stats
    cache._update_access_stats(test_cid)
    updated_metadata = cache.get(test_cid)
    assert "access_count" in updated_metadata, "Access count not updated"
    assert updated_metadata["access_count"] > 0, "Access count should be greater than 0"
    assert "heat_score" in updated_metadata, "Heat score not updated"
    logger.info(f"Updated access stats: count={updated_metadata['access_count']}, heat={updated_metadata['heat_score']:.2f}")

    # Update the pin status
    updated_metadata["pinned"] = True
    cache.put(test_cid, updated_metadata)

    # Retrieve again to verify update
    retrieved_again = cache.get(test_cid)
    assert retrieved_again["pinned"] == True, "Pin status not updated"
    logger.info(f"Updated pin status: {retrieved_again['pinned']}")

    # Test querying
    query_result = cache.query(filters={"pinned": True})
    assert test_cid in query_result, "Query should return our CID"
    logger.info(f"Query returned {len(query_result)} results")

    # Test stats
    stats = cache.stats()
    assert stats["record_count"] > 0, "Stats should show records"
    logger.info(f"Cache stats: {stats}")

    # Test getting all CIDs
    all_cids = cache.get_all_cids()
    assert test_cid in all_cids, "All CIDs should include our test CID"
    logger.info(f"All CIDs: {all_cids}")

    # Test clearing the cache
    clear_result = cache.clear()
    assert clear_result, "Failed to clear cache"

    # Verify cache is empty
    all_cids_after_clear = cache.get_all_cids()
    assert len(all_cids_after_clear) == 0, "Cache should be empty after clearing"
    logger.info("Cache cleared successfully")

    logger.info("ParquetCIDCache test passed!")
    return True

if __name__ == "__main__":
    logger.info("Starting tests...")

    # Run tests
    test_multiformats_cid()
    test_parquet_cid_cache()

    logger.info("All tests passed successfully!")

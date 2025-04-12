"""
Example demonstrating the AsyncParquetCIDCache functionality.

This script shows how to use the AsyncParquetCIDCache to perform non-blocking
cache operations using anyio. It demonstrates basic operations, batch processing,
and typical usage patterns in an asyncio-based application.
"""

import anyio
import time
import os
import logging
import json
import uuid
from typing import Dict, List, Optional, Any

import pyarrow as pa
import numpy as np

from ipfs_kit_py.cache import AsyncParquetCIDCache, AsyncOperationManager
from ipfs_kit_py.ipfs_kit import IPFSKit

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('async_cache_example')

# Function to create a dummy ParquetCIDCache for demonstration
def create_dummy_cache():
    """Create a simple mock cache for demonstration purposes."""
    class DummyParquetCIDCache:
        def __init__(self):
            self.storage = {}
            self.memory_cache = {}
        
        def _get_from_disk(self, cid, columns=None, filters=None):
            """Simulate disk read with delay."""
            time.sleep(0.05)  # Simulate disk I/O delay
            if cid in self.storage:
                # Return the full table or filter columns if specified
                table = self.storage[cid]
                if columns is not None:
                    present_columns = [c for c in columns if c in table.column_names]
                    if present_columns:
                        return table.select(present_columns)
                return table
            return None
        
        def _put_to_disk(self, cid, table, metadata=None):
            """Simulate disk write with delay."""
            time.sleep(0.07)  # Simulate disk I/O delay
            self.storage[cid] = table
            return True
        
        def _delete_from_disk(self, cid):
            """Simulate disk delete with delay."""
            time.sleep(0.03)  # Simulate disk I/O delay
            if cid in self.storage:
                del self.storage[cid]
                return True
            return False
        
        def _contains_in_disk(self, cid):
            """Check if CID exists in storage."""
            time.sleep(0.01)  # Small delay
            return cid in self.storage
        
        def _get_metadata(self, cid):
            """Get metadata for a CID."""
            time.sleep(0.02)  # Small delay
            if cid in self.storage:
                return {"created_at": time.time() - 3600}  # Mock metadata
            return None
        
        def _update_metadata(self, cid, metadata, merge=True):
            """Update metadata for a CID."""
            time.sleep(0.02)  # Small delay
            return cid in self.storage
        
        def _query(self, filters, columns=None, limit=None):
            """Perform a query operation."""
            time.sleep(0.1)  # More complex operation
            results = []
            for cid, table in self.storage.items():
                results.append(table)
            
            if results:
                result = pa.concat_tables(results)
                if limit is not None and limit < result.num_rows:
                    result = result.slice(0, limit)
                return result
            return pa.table([])
    
    return DummyParquetCIDCache()

# Create test Arrow tables
def create_test_table(num_rows=100, prefix="test"):
    """Create a test Arrow table with random data."""
    ids = [f"{prefix}-{i}" for i in range(num_rows)]
    values = np.random.rand(num_rows).tolist()
    timestamps = [time.time() - i * 60 for i in range(num_rows)]
    
    return pa.table({
        'id': pa.array(ids, type=pa.string()),
        'value': pa.array(values, type=pa.float64()),
        'timestamp': pa.array(timestamps, type=pa.float64())
    })

# Example 1: Basic async operations
async def example_basic_operations():
    """Demonstrate basic async cache operations."""
    logger.info("Starting Example 1: Basic Async Operations")
    
    # Create an async manager with custom settings
    async_manager = AsyncOperationManager(
        max_workers=4,
        io_workers=2,
        compute_workers=2,
        enable_stats=True
    )
    
    # Create an async cache
    cache = AsyncParquetCIDCache(
        cache_instance=create_dummy_cache(),
        async_manager=async_manager
    )
    
    # Generate some test data
    table = create_test_table(num_rows=100)
    cid = f"example-{uuid.uuid4()}"
    
    # Basic operations
    logger.info(f"Putting data for CID: {cid}")
    start_time = time.time()
    put_result = await cache.put(cid, table, {"description": "Test data"})
    put_time = time.time() - start_time
    logger.info(f"Put result: {put_result}, took {put_time:.4f} seconds")
    
    logger.info(f"Getting data for CID: {cid}")
    start_time = time.time()
    get_result = await cache.get(cid)
    get_time = time.time() - start_time
    if get_result is not None:
        logger.info(f"Got data with {get_result.num_rows} rows, took {get_time:.4f} seconds")
    else:
        logger.error("Failed to get data")
    
    # Check if CID exists
    logger.info(f"Checking if CID exists: {cid}")
    contains_result = await cache.contains(cid)
    logger.info(f"Contains result: {contains_result}")
    
    # Get metadata
    logger.info(f"Getting metadata for CID: {cid}")
    metadata = await cache.get_metadata(cid)
    logger.info(f"Metadata: {metadata}")
    
    # Delete the CID
    logger.info(f"Deleting CID: {cid}")
    delete_result = await cache.delete(cid)
    logger.info(f"Delete result: {delete_result}")
    
    # Get operation statistics
    stats = await cache.stats()
    logger.info(f"Operation statistics: {json.dumps(stats, indent=2)}")
    
    # Clean up
    await cache.close()
    logger.info("Example 1 completed")

# Example 2: Batch operations
async def example_batch_operations():
    """Demonstrate batch async operations."""
    logger.info("Starting Example 2: Batch Operations")
    
    # Create an async cache
    cache = AsyncParquetCIDCache(create_dummy_cache())
    
    # Create multiple tables
    num_items = 10
    items = []
    cids = []
    
    for i in range(num_items):
        cid = f"batch-{uuid.uuid4()}"
        table = create_test_table(num_rows=50, prefix=f"batch-{i}")
        items.append({
            "cid": cid,
            "table": table,
            "metadata": {"batch_id": i, "description": f"Batch item {i}"}
        })
        cids.append(cid)
    
    # Batch put operation
    logger.info(f"Putting {num_items} items in batch")
    start_time = time.time()
    batch_put_results = await cache.batch_put(items)
    batch_put_time = time.time() - start_time
    logger.info(f"Batch put completed in {batch_put_time:.4f} seconds")
    logger.info(f"Success rate: {sum(1 for r in batch_put_results if r)/len(batch_put_results):.2%}")
    
    # Individual puts for comparison
    logger.info("Putting same number of items individually for comparison")
    start_time = time.time()
    individual_results = []
    for item in items:
        result = await cache.put(
            item["cid"], 
            item["table"], 
            item.get("metadata")
        )
        individual_results.append(result)
    individual_put_time = time.time() - start_time
    logger.info(f"Individual puts completed in {individual_put_time:.4f} seconds")
    
    # Speed comparison
    speedup = individual_put_time / batch_put_time
    logger.info(f"Batch operations are {speedup:.2f}x faster than individual operations")
    
    # Batch get
    get_items = [{"cid": cid} for cid in cids]
    logger.info(f"Getting {num_items} items in batch")
    start_time = time.time()
    batch_get_results = await cache.batch_get(get_items)
    batch_get_time = time.time() - start_time
    logger.info(f"Batch get completed in {batch_get_time:.4f} seconds")
    logger.info(f"Retrieved {sum(1 for r in batch_get_results if r is not None)} items")
    
    # Batch delete
    logger.info(f"Deleting {num_items} items in batch")
    batch_delete_results = await cache.batch_delete(cids)
    logger.info(f"Deleted {sum(1 for r in batch_delete_results if r)} items")
    
    # Get statistics
    stats = await cache.stats()
    logger.info(f"Batch statistics: {stats.get('batch_sizes', [])}")
    
    # Clean up
    await cache.close()
    logger.info("Example 2 completed")

# Example 3: Real-world usage with IPFS Kit
async def example_real_world_integration():
    """Demonstrate integration with IPFS Kit in a real-world scenario."""
    logger.info("Starting Example 3: Real-world Integration")
    
    try:
        # Initialize IPFS Kit
        ipfs = IPFSKit()
        
        # Create a real cache instance (if available in your environment)
        # For demonstration, we'll use the dummy cache
        cache = AsyncParquetCIDCache(create_dummy_cache())
        
        # Simulate content processing workflow
        
        # 1. Create some test content
        test_content = b"Hello Async IPFS World!" * 1000  # ~24KB
        
        # 2. Add to IPFS (using synchronous API for simplicity)
        add_result = ipfs.ipfs_add(test_content)
        if not add_result.get("success", False):
            logger.error("Failed to add content to IPFS")
            return
        
        cid = add_result.get("cid")
        logger.info(f"Added content to IPFS with CID: {cid}")
        
        # 3. Create Arrow table with metadata about the content
        table = pa.table({
            'cid': [cid],
            'size': [len(test_content)],
            'created_at': [time.time()],
            'content_type': ['text/plain'],
            'description': ['Test content for async example']
        })
        
        # 4. Store in cache asynchronously
        await cache.put(cid, table, {
            "description": "IPFS content metadata",
            "origin": "async_example.py"
        })
        logger.info(f"Stored metadata in cache for CID: {cid}")
        
        # 5. Simulate multiple concurrent operations
        async def process_content(content_cid):
            """Process content with simulated async operations."""
            # Get metadata from cache
            metadata_table = await cache.get(content_cid)
            if metadata_table is None:
                logger.error(f"No metadata found for CID: {content_cid}")
                return False
            
            # Simulate content processing
            await anyio.sleep(0.2)  # Simulate processing time
            
            # Update metadata with processing result
            size = metadata_table['size'][0].as_py()
            
            # Create new table with additional information
            new_table = pa.table({
                'cid': [content_cid],
                'size': [size],
                'created_at': [metadata_table['created_at'][0].as_py()],
                'content_type': [metadata_table['content_type'][0].as_py()],
                'description': [metadata_table['description'][0].as_py()],
                'processed_at': [time.time()],
                'processing_status': ['completed']
            })
            
            # Update the cache
            await cache.put(content_cid, new_table, {
                "description": "Updated after processing",
                "origin": "async_example.py"
            })
            
            return True
        
        # 6. Run multiple concurrent operations
        tasks = []
        for i in range(5):  # Simulate 5 concurrent processing operations
            tasks.append(process_content(cid))
        
        results = await anyio.gather(*tasks)
        logger.info(f"Processed content {sum(results)}/{len(results)} times successfully")
        
        # 7. Final metadata retrieval
        final_metadata = await cache.get(cid)
        if final_metadata is not None:
            logger.info(f"Final metadata: processing_status={final_metadata['processing_status'][0].as_py()}")
            logger.info(f"Final metadata table has {len(final_metadata.column_names)} columns")
        
        # 8. Get cache statistics
        stats = await cache.stats()
        logger.info(f"Cache hit rate: {stats.get('memory_hits', 0)}/{stats.get('total_operations', 0)}")
        
        # Clean up
        await cache.close()
        logger.info("Example 3 completed")
        
    except Exception as e:
        logger.exception(f"Error in real-world example: {str(e)}")

# Main function to run all examples
async def main():
    """Run all async cache examples."""
    logger.info("Starting async cache examples")
    
    # Run examples
    await example_basic_operations()
    
    logger.info("---------------------------------------")
    
    await example_batch_operations()
    
    logger.info("---------------------------------------")
    
    await example_real_world_integration()
    
    logger.info("All examples completed")

# Run the main function
if __name__ == "__main__":
    anyio.run(main())

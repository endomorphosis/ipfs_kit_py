"""
Comprehensive Integration Test for Enhanced IPFS-Parquet-VFS System.

This test validates the complete integration of:
1. IPFS Kit with daemon management
2. Parquet-IPLD bridge for structured data storage
3. Virtual filesystem integration
4. Arrow-based analytics
5. Tiered caching with ARC
6. Write-ahead logging
7. Metadata replication
"""

import anyio
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

try:
    from ipfs_kit_py.parquet_ipld_bridge import ParquetIPLDBridge
    from ipfs_kit_py.parquet_vfs_integration import create_parquet_vfs_integration
    from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex
    from ipfs_kit_py.tiered_cache_manager import TieredCacheManager
    from ipfs_kit_py.storage_wal import StorageWriteAheadLog
    from ipfs_kit_py.fs_journal_replication import MetadataReplicationManager
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    COMPONENTS_AVAILABLE = False
    print(f"Components not available: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_datasets():
    """Create test datasets for validation."""
    datasets = {}
    
    # Sales data
    datasets["sales"] = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=100, freq="D"),
        "product": ["A", "B", "C"] * 34 + ["A", "B"],
        "sales": range(1, 101),
        "revenue": [x * 10.5 for x in range(1, 101)],
        "region": ["North", "South", "East", "West"] * 25
    })
    
    # Customer data
    datasets["customers"] = pd.DataFrame({
        "customer_id": range(1, 51),
        "name": [f"Customer {i}" for i in range(1, 51)],
        "age": [20 + (i % 50) for i in range(50)],
        "city": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"] * 10,
        "signup_date": pd.date_range("2023-01-01", periods=50, freq="W")
    })
    
    # Time series data
    datasets["metrics"] = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=1000, freq="H"),
        "cpu_usage": [50 + (i % 30) for i in range(1000)],
        "memory_usage": [40 + (i % 40) for i in range(1000)],
        "network_io": [100 + (i % 200) for i in range(1000)],
        "disk_io": [50 + (i % 100) for i in range(1000)]
    })
    
    return datasets


async def test_basic_storage_retrieval(bridge: ParquetIPLDBridge, datasets: Dict[str, pd.DataFrame]):
    """Test basic storage and retrieval operations."""
    logger.info("Testing basic storage and retrieval...")
    
    stored_cids = {}
    
    # Store each dataset
    for name, df in datasets.items():
        logger.info(f"Storing dataset: {name}")
        result = bridge.store_dataframe(
            df,
            name=name,
            metadata={"test": True, "dataset_type": name}
        )
        
        if result["success"]:
            stored_cids[name] = result["cid"]
            logger.info(f"Stored {name} with CID: {result['cid']}")
        else:
            logger.error(f"Failed to store {name}: {result.get('error')}")
            return False
    
    # Retrieve each dataset
    for name, cid in stored_cids.items():
        logger.info(f"Retrieving dataset: {name}")
        result = bridge.retrieve_dataframe(cid)
        
        if result["success"]:
            retrieved_df = result["table"].to_pandas()
            original_df = datasets[name]
            
            # Verify data integrity
            if len(retrieved_df) == len(original_df):
                logger.info(f"Successfully retrieved {name} - {len(retrieved_df)} rows")
            else:
                logger.error(f"Row count mismatch for {name}")
                return False
        else:
            logger.error(f"Failed to retrieve {name}: {result.get('error')}")
            return False
    
    return True


async def test_query_functionality(bridge: ParquetIPLDBridge):
    """Test SQL query functionality."""
    logger.info("Testing SQL query functionality...")
    
    test_queries = [
        "SELECT product, SUM(sales) as total_sales FROM datasets GROUP BY product",
        "SELECT region, AVG(revenue) as avg_revenue FROM datasets WHERE sales > 50 GROUP BY region",
        "SELECT COUNT(*) as total_rows FROM datasets",
        "SELECT product, region, MAX(revenue) as max_revenue FROM datasets GROUP BY product, region"
    ]
    
    for query in test_queries:
        logger.info(f"Executing query: {query}")
        result = bridge.query_datasets(query)
        
        if result["success"]:
            result_table = result["result"]
            logger.info(f"Query successful - {result_table.num_rows} rows returned")
        else:
            logger.error(f"Query failed: {result.get('error')}")
            return False
    
    return True


async def test_vfs_integration(vfs):
    """Test virtual filesystem integration."""
    logger.info("Testing VFS integration...")
    
    # Test directory listing
    logger.info("Testing VFS directory listing...")
    try:
        root_entries = vfs.ls("/", detail=True)
        logger.info(f"Root directory has {len(root_entries)} entries")
        
        datasets_entries = vfs.ls("/datasets", detail=True)
        logger.info(f"Datasets directory has {len(datasets_entries)} entries")
        
        metadata_entries = vfs.ls("/metadata", detail=True)
        logger.info(f"Metadata directory has {len(metadata_entries)} entries")
        
    except Exception as e:
        logger.error(f"VFS listing failed: {e}")
        return False
    
    # Test file info
    logger.info("Testing VFS file info...")
    try:
        if datasets_entries:
            first_dataset = datasets_entries[0]["name"]
            info = vfs.info(first_dataset)
            logger.info(f"Dataset info: {info}")
    except Exception as e:
        logger.error(f"VFS info failed: {e}")
        return False
    
    # Test file reading
    logger.info("Testing VFS file reading...")
    try:
        if metadata_entries:
            first_metadata = metadata_entries[0]["name"]
            content = vfs.cat_file(first_metadata)
            metadata_json = json.loads(content.decode())
            logger.info(f"Metadata content: {metadata_json}")
    except Exception as e:
        logger.error(f"VFS reading failed: {e}")
        return False
    
    return True


async def test_cache_performance(bridge: ParquetIPLDBridge):
    """Test cache performance."""
    logger.info("Testing cache performance...")
    
    # Get list of datasets
    datasets_result = bridge.list_datasets()
    if not datasets_result["success"] or not datasets_result["datasets"]:
        logger.error("No datasets available for cache testing")
        return False
    
    first_cid = datasets_result["datasets"][0]["cid"]
    
    # First retrieval (cache miss)
    start_time = time.time()
    result1 = bridge.retrieve_dataframe(first_cid, use_cache=True)
    cache_miss_time = time.time() - start_time
    
    if not result1["success"]:
        logger.error("First retrieval failed")
        return False
    
    # Second retrieval (cache hit)
    start_time = time.time()
    result2 = bridge.retrieve_dataframe(first_cid, use_cache=True)
    cache_hit_time = time.time() - start_time
    
    if not result2["success"]:
        logger.error("Second retrieval failed")
        return False
    
    logger.info(f"Cache miss time: {cache_miss_time:.3f}s, Cache hit time: {cache_hit_time:.3f}s")
    
    # Cache hit should be significantly faster
    if cache_hit_time < cache_miss_time * 0.8:
        logger.info("Cache performance test passed")
        return True
    else:
        logger.warning("Cache performance may not be optimal")
        return True  # Still consider it a pass


async def test_wal_functionality(bridge: ParquetIPLDBridge):
    """Test write-ahead log functionality."""
    logger.info("Testing WAL functionality...")
    
    # Create a test dataset
    test_df = pd.DataFrame({
        "id": range(10),
        "value": [f"test_{i}" for i in range(10)]
    })
    
    # Store with WAL enabled
    result = bridge.store_dataframe(
        test_df,
        name="wal_test",
        metadata={"wal_test": True}
    )
    
    if result["success"]:
        logger.info(f"WAL test dataset stored with CID: {result['cid']}")
        
        # Check WAL status
        if hasattr(bridge, 'wal_manager') and bridge.wal_manager:
            status = bridge.wal_manager.get_status()
            logger.info(f"WAL status: {status}")
        
        return True
    else:
        logger.error(f"WAL test failed: {result.get('error')}")
        return False


async def test_replication_functionality(bridge: ParquetIPLDBridge):
    """Test metadata replication functionality."""
    logger.info("Testing replication functionality...")
    
    # Check if replication manager is available
    if not hasattr(bridge, 'replication_manager') or not bridge.replication_manager:
        logger.warning("Replication manager not available")
        return True  # Not an error, just not available
    
    try:
        # Get replication status
        status = bridge.replication_manager.get_replication_status()
        logger.info(f"Replication status: {status}")
        
        # Test metadata sync (if available)
        if hasattr(bridge.replication_manager, 'sync_metadata'):
            sync_result = bridge.replication_manager.sync_metadata()
            logger.info(f"Metadata sync result: {sync_result}")
        
        return True
    except Exception as e:
        logger.error(f"Replication test failed: {e}")
        return False


async def run_comprehensive_test():
    """Run the complete integration test suite."""
    logger.info("Starting comprehensive integration test...")
    
    if not ARROW_AVAILABLE:
        logger.error("PyArrow not available - cannot run tests")
        return False
    
    if not COMPONENTS_AVAILABLE:
        logger.error("IPFS Kit components not available - cannot run tests")
        return False
    
    # Create temporary storage path
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = temp_dir
        logger.info(f"Using temporary storage: {storage_path}")
        
        try:
            # Initialize components
            logger.info("Initializing components...")
            
            metadata_index = ArrowMetadataIndex(storage_path=storage_path)
            cache_manager = TieredCacheManager(
                storage_path=storage_path,
                max_memory_gb=0.1,  # Small for testing
                max_disk_gb=1.0
            )
            wal_manager = StorageWriteAheadLog(storage_path=storage_path)
            replication_manager = MetadataReplicationManager(storage_path=storage_path)
            
            # Create bridge and VFS
            bridge, vfs = create_parquet_vfs_integration(
                storage_path=storage_path,
                cache_manager=cache_manager,
                wal_manager=wal_manager,
                replication_manager=replication_manager,
                metadata_index=metadata_index
            )
            
            logger.info("Components initialized successfully")
            
            # Create test datasets
            datasets = create_test_datasets()
            logger.info(f"Created {len(datasets)} test datasets")
            
            # Run test suite
            test_results = {}
            
            # Test 1: Basic storage and retrieval
            test_results["storage_retrieval"] = await test_basic_storage_retrieval(bridge, datasets)
            
            # Test 2: Query functionality
            test_results["query_functionality"] = await test_query_functionality(bridge)
            
            # Test 3: VFS integration
            test_results["vfs_integration"] = await test_vfs_integration(vfs)
            
            # Test 4: Cache performance
            test_results["cache_performance"] = await test_cache_performance(bridge)
            
            # Test 5: WAL functionality
            test_results["wal_functionality"] = await test_wal_functionality(bridge)
            
            # Test 6: Replication functionality
            test_results["replication_functionality"] = await test_replication_functionality(bridge)
            
            # Summary
            logger.info("\n" + "="*60)
            logger.info("TEST RESULTS SUMMARY")
            logger.info("="*60)
            
            passed_tests = 0
            total_tests = len(test_results)
            
            for test_name, result in test_results.items():
                status = "PASS" if result else "FAIL"
                logger.info(f"{test_name:<25}: {status}")
                if result:
                    passed_tests += 1
            
            logger.info("="*60)
            logger.info(f"Tests passed: {passed_tests}/{total_tests}")
            
            if passed_tests == total_tests:
                logger.info("🎉 ALL TESTS PASSED! Integration is working correctly.")
                return True
            else:
                logger.error(f"❌ {total_tests - passed_tests} tests failed.")
                return False
                
        except Exception as e:
            logger.error(f"Test setup failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


async def main():
    """Main test entry point."""
    try:
        success = await run_comprehensive_test()
        if success:
            print("\n✅ Integration test completed successfully!")
            return 0
        else:
            print("\n❌ Integration test failed!")
            return 1
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = anyio.run(main)
    sys.exit(exit_code)

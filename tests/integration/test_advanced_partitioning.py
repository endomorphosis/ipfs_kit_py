"""
Tests for advanced partitioning strategies module.

This module contains tests for all partitioning strategies:
- Time-based partitioning
- Size-based partitioning 
- Content-type based partitioning
- Hash-based partitioning
- Dynamic partition management
"""

import os
import time
import uuid
import random
import tempfile
import shutil
import unittest
from datetime import datetime, timedelta
from typing import Dict, List, Any, Union

import pyarrow as pa
import pyarrow.parquet as pq

try:
    from ipfs_kit_py.cache.advanced_partitioning_strategies import (
        PartitioningStrategy,
        PartitionInfo,
        TimeBasedPartitionStrategy,
        SizeBasedPartitionStrategy,
        ContentTypePartitionStrategy,
        HashBasedPartitionStrategy,
        DynamicPartitionManager,
        AdvancedPartitionManager
    )
    HAVE_PARTITIONING = True
except ImportError:
    HAVE_PARTITIONING = False


@unittest.skipIf(not HAVE_PARTITIONING, "Advanced partitioning module not available")
class PartitionInfoTest(unittest.TestCase):
    """Test the PartitionInfo class."""
    
    def test_partition_info_creation(self):
        """Test creation of a PartitionInfo object."""
        partition = PartitionInfo(
            partition_id="test_id",
            path="/test/path",
            strategy=PartitioningStrategy.TIME_BASED,
            created_at=1000000,
            last_modified=1000100,
            record_count=100,
            size_bytes=1024,
            metadata={"test": "metadata"},
            statistics={"avg_size": 10.24}
        )
        
        self.assertEqual(partition.partition_id, "test_id")
        self.assertEqual(partition.path, "/test/path")
        self.assertEqual(partition.strategy, PartitioningStrategy.TIME_BASED)
        self.assertEqual(partition.created_at, 1000000)
        self.assertEqual(partition.last_modified, 1000100)
        self.assertEqual(partition.record_count, 100)
        self.assertEqual(partition.size_bytes, 1024)
        self.assertEqual(partition.metadata, {"test": "metadata"})
        self.assertEqual(partition.statistics, {"avg_size": 10.24})
    
    def test_get_age_days(self):
        """Test the get_age_days method."""
        now = time.time()
        one_day_ago = now - 24 * 3600
        
        partition = PartitionInfo(
            partition_id="test_id",
            path="/test/path",
            strategy=PartitioningStrategy.TIME_BASED,
            created_at=one_day_ago,
            last_modified=now,
            record_count=100,
            size_bytes=1024,
            metadata={},
            statistics={}
        )
        
        # Should be approximately 1 day
        self.assertAlmostEqual(partition.get_age_days(), 1.0, delta=0.01)
    
    def test_get_activity_score(self):
        """Test the get_activity_score method."""
        now = time.time()
        
        # Recent partition (created just now)
        recent_partition = PartitionInfo(
            partition_id="recent",
            path="/test/recent",
            strategy=PartitioningStrategy.TIME_BASED,
            created_at=now,
            last_modified=now,
            record_count=100,
            size_bytes=1024 * 100,  # 100KB
            metadata={},
            statistics={}
        )
        
        # Old partition (created 90 days ago)
        old_partition = PartitionInfo(
            partition_id="old",
            path="/test/old",
            strategy=PartitioningStrategy.TIME_BASED,
            created_at=now - 90 * 24 * 3600,
            last_modified=now - 90 * 24 * 3600,
            record_count=100,
            size_bytes=1024 * 100,  # 100KB
            metadata={},
            statistics={}
        )
        
        # Recent partition should have higher activity score
        self.assertGreater(recent_partition.get_activity_score(), old_partition.get_activity_score())
    
    def test_to_dict_from_dict(self):
        """Test conversion to and from dictionary."""
        original = PartitionInfo(
            partition_id="test_id",
            path="/test/path",
            strategy=PartitioningStrategy.HASH_BASED,
            created_at=1000000,
            last_modified=1000100,
            record_count=100,
            size_bytes=1024,
            metadata={"test": "metadata"},
            statistics={"avg_size": 10.24}
        )
        
        # Convert to dict and back
        data = original.to_dict()
        restored = PartitionInfo.from_dict(data)
        
        # Check all fields match
        self.assertEqual(restored.partition_id, original.partition_id)
        self.assertEqual(restored.path, original.path)
        self.assertEqual(restored.strategy, original.strategy)
        self.assertEqual(restored.created_at, original.created_at)
        self.assertEqual(restored.last_modified, original.last_modified)
        self.assertEqual(restored.record_count, original.record_count)
        self.assertEqual(restored.size_bytes, original.size_bytes)
        self.assertEqual(restored.metadata, original.metadata)
        self.assertEqual(restored.statistics, original.statistics)


@unittest.skipIf(not HAVE_PARTITIONING, "Advanced partitioning module not available")
class TimeBasedPartitionStrategyTest(unittest.TestCase):
    """Test the TimeBasedPartitionStrategy class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.strategy = TimeBasedPartitionStrategy(
            timestamp_column="timestamp",
            period="daily",
            base_path=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)
    
    def test_get_partition_path(self):
        """Test partition path generation for timestamps."""
        # Test with datetime
        dt = datetime(2023, 5, 15, 12, 30, 45)
        path = self.strategy.get_partition_path(dt)
        self.assertEqual(os.path.basename(path), "2023-05-15")
        
        # Test with timestamp (float)
        ts = dt.timestamp()
        path = self.strategy.get_partition_path(ts)
        self.assertEqual(os.path.basename(path), "2023-05-15")
    
    def test_partition_record(self):
        """Test record partitioning."""
        # Record with timestamp
        record = {
            "cid": "QmTest",
            "timestamp": datetime(2023, 5, 15, 12, 30, 45).timestamp()
        }
        path = self.strategy.partition_record(record)
        self.assertEqual(os.path.basename(path), "2023-05-15")
        
        # Record without timestamp should use current time
        record = {"cid": "QmTest"}
        path = self.strategy.partition_record(record)
        expected_date = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(os.path.basename(path), expected_date)
    
    def test_different_periods(self):
        """Test different time periods."""
        dt = datetime(2023, 5, 15, 12, 30, 45)
        ts = dt.timestamp()
        
        # Hourly
        hourly = TimeBasedPartitionStrategy(period="hourly", base_path=self.temp_dir)
        path = hourly.get_partition_path(ts)
        self.assertEqual(os.path.basename(path), "2023-05-15-12")
        
        # Daily
        daily = TimeBasedPartitionStrategy(period="daily", base_path=self.temp_dir)
        path = daily.get_partition_path(ts)
        self.assertEqual(os.path.basename(path), "2023-05-15")
        
        # Weekly
        weekly = TimeBasedPartitionStrategy(period="weekly", base_path=self.temp_dir)
        path = weekly.get_partition_path(ts)
        # Week 20 in 2023
        self.assertEqual(os.path.basename(path), "2023-W20")
        
        # Monthly
        monthly = TimeBasedPartitionStrategy(period="monthly", base_path=self.temp_dir)
        path = monthly.get_partition_path(ts)
        self.assertEqual(os.path.basename(path), "2023-05")
        
        # Quarterly
        quarterly = TimeBasedPartitionStrategy(period="quarterly", base_path=self.temp_dir)
        path = quarterly.get_partition_path(ts)
        # Q2 for May
        self.assertEqual(os.path.basename(path), "2023-Q2")
        
        # Yearly
        yearly = TimeBasedPartitionStrategy(period="yearly", base_path=self.temp_dir)
        path = yearly.get_partition_path(ts)
        self.assertEqual(os.path.basename(path), "2023")
    
    def test_get_activity_timeframe(self):
        """Test getting activity timeframe."""
        # Get partitions for last 7 days
        active_partitions = self.strategy.get_activity_timeframe(timeframe_days=7)
        
        # Should have 7 partitions (one for each day)
        self.assertEqual(len(active_partitions), 8)  # Including today (0 days ago)
        
        # Check all partitions are in correct format
        for path in active_partitions:
            self.assertTrue(os.path.basename(path).startswith("202"))  # Year should start with 202x
            
    def test_create_partition_schema(self):
        """Test creating partition schema."""
        schema = self.strategy.create_partition_schema()
        self.assertIsInstance(schema, pa.Schema)
        
        # Get field names from the schema
        field_names = [field.name for field in schema]
        
        # Check that the expected fields are present
        self.assertIn("year", field_names)
        self.assertIn("month", field_names)
        self.assertIn("day", field_names)


@unittest.skipIf(not HAVE_PARTITIONING, "Advanced partitioning module not available")
class SizeBasedPartitionStrategyTest(unittest.TestCase):
    """Test the SizeBasedPartitionStrategy class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.strategy = SizeBasedPartitionStrategy(
            target_size_mb=10,  # Small value for testing
            max_size_mb=20,
            base_path=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialize_partition(self):
        """Test initializing a new partition."""
        # Should not have a current partition initially
        self.assertIsNone(self.strategy.current_partition_id)
        
        # Initialize partition
        partition_id = self.strategy.initialize_partition()
        
        # Should now have a current partition
        self.assertIsNotNone(self.strategy.current_partition_id)
        self.assertEqual(self.strategy.current_partition_id, partition_id)
        self.assertEqual(self.strategy.current_partition_size, 0)
    
    def test_get_partition_path(self):
        """Test getting the partition path."""
        # Initialize partition
        partition_id = self.strategy.initialize_partition()
        
        # Get path
        path = self.strategy.get_partition_path()
        
        # Should end with the partition ID
        self.assertTrue(path.endswith(partition_id))
    
    def test_should_rotate_partition(self):
        """Test partition rotation logic."""
        # Initialize partition
        self.strategy.initialize_partition()
        
        # Should not rotate for small records
        self.assertFalse(self.strategy.should_rotate_partition(1024))  # 1KB
        
        # Add enough data to reach target size
        self.strategy.add_record_size(10 * 1024 * 1024)  # 10MB
        
        # Should now rotate for any new record
        self.assertTrue(self.strategy.should_rotate_partition(1024))
        
        # Should definitely rotate for large records that exceed max size
        self.strategy.initialize_partition()  # Reset partition
        self.assertTrue(self.strategy.should_rotate_partition(25 * 1024 * 1024))  # 25MB > max 20MB
    
    def test_partition_record(self):
        """Test record partitioning."""
        # First record - creates partition
        record1 = {"cid": "QmTest1", "size": 5 * 1024 * 1024}  # 5MB
        path1 = self.strategy.partition_record(record1, record_size=record1["size"])
        partition1 = self.strategy.current_partition_id
        
        # Second record - same partition
        record2 = {"cid": "QmTest2", "size": 3 * 1024 * 1024}  # 3MB
        path2 = self.strategy.partition_record(record2, record_size=record2["size"])
        
        # Should be in same partition
        self.assertEqual(path1, path2)
        self.assertEqual(self.strategy.current_partition_id, partition1)
        
        # Large record that causes rotation
        record3 = {"cid": "QmTest3", "size": 15 * 1024 * 1024}  # 15MB
        path3 = self.strategy.partition_record(record3, record_size=record3["size"])
        
        # Should be in a new partition
        self.assertNotEqual(path3, path1)
        self.assertNotEqual(self.strategy.current_partition_id, partition1)


@unittest.skipIf(not HAVE_PARTITIONING, "Advanced partitioning module not available")
class ContentTypePartitionStrategyTest(unittest.TestCase):
    """Test the ContentTypePartitionStrategy class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.strategy = ContentTypePartitionStrategy(
            content_type_column="mime_type",
            use_groups=True,
            base_path=self.temp_dir
        )
        
        # Without groups
        self.strategy_no_groups = ContentTypePartitionStrategy(
            content_type_column="mime_type",
            use_groups=False,
            base_path=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)
    
    def test_get_content_group(self):
        """Test content type group detection."""
        # Test exact match
        self.assertEqual(self.strategy.get_content_group("image/jpeg"), "image")
        self.assertEqual(self.strategy.get_content_group("video/mp4"), "video")
        
        # Test main type match (no exact match)
        self.assertEqual(self.strategy.get_content_group("image/custom"), "image")
        
        # Test unknown type
        self.assertEqual(self.strategy.get_content_group("unknown/type"), "other")
        
        # Test with groups disabled
        self.assertEqual(self.strategy_no_groups.get_content_group("image/jpeg"), "image_jpeg")
    
    def test_normalize_content_type(self):
        """Test content type normalization."""
        # Test simple type
        self.assertEqual(self.strategy._normalize_content_type("image/jpeg"), "image_jpeg")
        
        # Test with special characters
        self.assertEqual(self.strategy._normalize_content_type("application/x+test"), "application_x_test")
        
        # Test with empty type
        self.assertEqual(self.strategy._normalize_content_type(""), "unknown")
        self.assertEqual(self.strategy._normalize_content_type(None), "unknown")
    
    def test_get_partition_path(self):
        """Test partition path generation."""
        # Test with groups enabled
        path = self.strategy.get_partition_path("image/jpeg")
        self.assertEqual(os.path.basename(path), "image")
        
        # Test with groups disabled
        path = self.strategy_no_groups.get_partition_path("image/jpeg")
        self.assertEqual(os.path.basename(path), "image_jpeg")
    
    def test_partition_record(self):
        """Test record partitioning."""
        # Test with groups enabled
        record = {"cid": "QmTest", "mime_type": "image/jpeg"}
        path = self.strategy.partition_record(record)
        self.assertEqual(os.path.basename(path), "image")
        
        # Test with groups disabled
        path = self.strategy_no_groups.partition_record(record)
        self.assertEqual(os.path.basename(path), "image_jpeg")
        
        # Test with missing content type
        record = {"cid": "QmTest"}
        path = self.strategy.partition_record(record)
        self.assertEqual(os.path.basename(path), "other")
    
    def test_create_partition_schema(self):
        """Test creating partition schema."""
        schema = self.strategy.create_partition_schema()
        self.assertIsInstance(schema, pa.Schema)
        
        # Get field names from the schema correctly
        field_names = [field.name for field in schema]
        
        # Check content_type field is present
        self.assertEqual(len(field_names), 1)
        self.assertEqual(field_names[0], "content_type")


@unittest.skipIf(not HAVE_PARTITIONING, "Advanced partitioning module not available")
class HashBasedPartitionStrategyTest(unittest.TestCase):
    """Test the HashBasedPartitionStrategy class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Default hash-based partitioning with 16 partitions
        self.strategy = HashBasedPartitionStrategy(
            key_column="cid",
            num_partitions=16,
            hash_algorithm="md5",
            base_path=self.temp_dir
        )
        
        # With 8 partitions
        self.strategy_8 = HashBasedPartitionStrategy(
            key_column="cid",
            num_partitions=8,
            hash_algorithm="md5",
            base_path=self.temp_dir
        )
        
        # With 15 partitions (not power of 2, should be adjusted)
        self.strategy_15 = HashBasedPartitionStrategy(
            key_column="cid",
            num_partitions=15,
            hash_algorithm="md5",
            base_path=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)
    
    def test_num_partitions_power_of_two(self):
        """Test that num_partitions is adjusted to power of 2."""
        # 16 is already a power of 2
        self.assertEqual(self.strategy.num_partitions, 16)
        
        # 8 is already a power of 2
        self.assertEqual(self.strategy_8.num_partitions, 8)
        
        # 15 should be adjusted to 16
        self.assertEqual(self.strategy_15.num_partitions, 16)
    
    def test_compute_hash(self):
        """Test hash computation."""
        # Same key should always hash to same value
        key = "QmTestCID"
        hash1 = self.strategy.compute_hash(key)
        hash2 = self.strategy.compute_hash(key)
        self.assertEqual(hash1, hash2)
        
        # Different keys should hash to different values
        key2 = "QmAnotherCID"
        hash3 = self.strategy.compute_hash(key2)
        self.assertNotEqual(hash1, hash3)
    
    def test_get_partition_number(self):
        """Test partition number computation."""
        # Partition number should be consistent for same key
        key = "QmTestCID"
        partition1 = self.strategy.get_partition_number(key)
        partition2 = self.strategy.get_partition_number(key)
        self.assertEqual(partition1, partition2)
        
        # Partition number should be between 0 and num_partitions-1
        self.assertGreaterEqual(partition1, 0)
        self.assertLess(partition1, self.strategy.num_partitions)
        
        # Different number of partitions should give different partition numbers
        partition_16 = self.strategy.get_partition_number(key)
        partition_8 = self.strategy_8.get_partition_number(key)
        # The partition numbers might be the same by chance, but the important thing
        # is that they're both within their respective ranges
        self.assertLess(partition_8, 8)
    
    def test_get_partition_path(self):
        """Test partition path generation."""
        key = "QmTestCID"
        
        # Path should be consistent for same key
        path1 = self.strategy.get_partition_path(key)
        path2 = self.strategy.get_partition_path(key)
        self.assertEqual(path1, path2)
        
        # Different keys should (likely) have different paths
        path3 = self.strategy.get_partition_path("QmAnotherCID")
        # There's a small chance they hash to the same partition by chance
        # So we can't assert they're different
    
    def test_partition_record(self):
        """Test record partitioning."""
        # With key column
        record = {"cid": "QmTestCID"}
        path = self.strategy.partition_record(record)
        
        # Path should match the one computed directly from key
        expected_path = self.strategy.get_partition_path("QmTestCID")
        self.assertEqual(path, expected_path)
        
        # Without key column
        record = {"other_field": "value"}
        path = self.strategy.partition_record(record)
        # Should still work with a random key
    
    def test_get_all_partition_paths(self):
        """Test getting all partition paths."""
        paths = self.strategy.get_all_partition_paths()
        
        # Should have num_partitions paths
        self.assertEqual(len(paths), self.strategy.num_partitions)
        
        # Check format of paths
        for path in paths:
            self.assertTrue(os.path.basename(path).startswith("0"))  # Hex format
            
        # Test with 8 partitions
        paths_8 = self.strategy_8.get_all_partition_paths()
        self.assertEqual(len(paths_8), 8)


@unittest.skipIf(not HAVE_PARTITIONING, "Advanced partitioning module not available")
class DynamicPartitionManagerTest(unittest.TestCase):
    """Test the DynamicPartitionManager class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = DynamicPartitionManager(
            base_path=self.temp_dir,
            default_strategy=PartitioningStrategy.HASH_BASED,
            auto_rebalance=True
        )
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test manager initialization."""
        # Should have empty partitions initially
        self.assertEqual(len(self.manager.partitions), 0)
        
        # Should have strategy implementations
        self.assertIsInstance(self.manager.time_strategy, TimeBasedPartitionStrategy)
        self.assertIsInstance(self.manager.size_strategy, SizeBasedPartitionStrategy)
        self.assertIsInstance(self.manager.content_strategy, ContentTypePartitionStrategy)
        self.assertIsInstance(self.manager.hash_strategy, HashBasedPartitionStrategy)
    
    def test_register_partition(self):
        """Test partition registration."""
        # Register a partition
        partition_id = self.manager.register_partition(
            partition_path="/test/path",
            strategy=PartitioningStrategy.TIME_BASED,
            record_count=100,
            size_bytes=1024,
            metadata={"test": "metadata"}
        )
        
        # Should have a partition now
        self.assertEqual(len(self.manager.partitions), 1)
        self.assertIn(partition_id, self.manager.partitions)
        
        # Check partition info
        partition = self.manager.partitions[partition_id]
        self.assertEqual(partition.path, "/test/path")
        self.assertEqual(partition.strategy, PartitioningStrategy.TIME_BASED)
        self.assertEqual(partition.record_count, 100)
        self.assertEqual(partition.size_bytes, 1024)
        self.assertEqual(partition.metadata, {"test": "metadata"})
    
    def test_update_partition_stats(self):
        """Test updating partition statistics."""
        # Register a partition
        partition_id = self.manager.register_partition(
            partition_path="/test/path",
            strategy=PartitioningStrategy.TIME_BASED,
            record_count=100,
            size_bytes=1024
        )
        
        # Update the statistics
        self.manager.update_partition_stats(
            partition_id=partition_id,
            record_count=200,
            size_bytes=2048,
            statistics={"avg_size": 10.24}
        )
        
        # Check updated partition info
        partition = self.manager.partitions[partition_id]
        self.assertEqual(partition.record_count, 200)
        self.assertEqual(partition.size_bytes, 2048)
        self.assertEqual(partition.statistics, {"avg_size": 10.24})
    
    def test_get_partitions_by_strategy(self):
        """Test retrieving partitions by strategy."""
        # Register partitions with different strategies
        p1 = self.manager.register_partition(
            partition_path="/test/time",
            strategy=PartitioningStrategy.TIME_BASED
        )
        
        p2 = self.manager.register_partition(
            partition_path="/test/hash",
            strategy=PartitioningStrategy.HASH_BASED
        )
        
        p3 = self.manager.register_partition(
            partition_path="/test/time2",
            strategy=PartitioningStrategy.TIME_BASED
        )
        
        # Get time-based partitions
        time_partitions = self.manager.get_partitions_by_strategy(PartitioningStrategy.TIME_BASED)
        self.assertEqual(len(time_partitions), 2)
        self.assertIn(self.manager.partitions[p1], time_partitions)
        self.assertIn(self.manager.partitions[p3], time_partitions)
        
        # Get hash-based partitions
        hash_partitions = self.manager.get_partitions_by_strategy(PartitioningStrategy.HASH_BASED)
        self.assertEqual(len(hash_partitions), 1)
        self.assertIn(self.manager.partitions[p2], hash_partitions)
    
    def test_update_workload_stats(self):
        """Test updating workload statistics."""
        # Initial stats should be zeros
        self.assertEqual(self.manager.workload_stats["temporal_access_score"], 0.0)
        
        # Update stats
        self.manager.update_workload_stats(
            temporal_access_score=0.8,
            content_type_score=0.6,
            size_variance_score=0.4,
            access_distribution_score=0.2,
            total_records=1000
        )
        
        # Check updated stats
        self.assertEqual(self.manager.workload_stats["temporal_access_score"], 0.8)
        self.assertEqual(self.manager.workload_stats["content_type_score"], 0.6)
        self.assertEqual(self.manager.workload_stats["size_variance_score"], 0.4)
        self.assertEqual(self.manager.workload_stats["access_distribution_score"], 0.2)
        self.assertEqual(self.manager.workload_stats["total_records"], 1000)
    
    def test_get_strategy_for_record(self):
        """Test strategy selection for a record."""
        # Default strategy with no stats
        record = {"cid": "QmTest"}
        strategy = self.manager.get_strategy_for_record(record)
        self.assertEqual(strategy, self.manager.default_strategy)
        
        # Temporal pattern
        self.manager.update_workload_stats(temporal_access_score=0.9)
        record = {"cid": "QmTest", "timestamp": time.time()}
        strategy = self.manager.get_strategy_for_record(record)
        self.assertEqual(strategy, PartitioningStrategy.TIME_BASED)
        
        # Content-type pattern
        self.manager.update_workload_stats(
            temporal_access_score=0.1,
            content_type_score=0.9
        )
        record = {"cid": "QmTest", "mime_type": "image/jpeg"}
        strategy = self.manager.get_strategy_for_record(record)
        self.assertEqual(strategy, PartitioningStrategy.CONTENT_TYPE)
    
    def test_get_partition_for_record(self):
        """Test getting partition for a record."""
        # Record with timestamp (time-based partition)
        self.manager.update_workload_stats(temporal_access_score=0.9)
        record = {"cid": "QmTest", "timestamp": time.time()}
        path = self.manager.get_partition_for_record(record)
        self.assertTrue(path.startswith(os.path.join(self.temp_dir, "time")))
        
        # Record with content type (content-type partition)
        self.manager.update_workload_stats(
            temporal_access_score=0.1,
            content_type_score=0.9
        )
        record = {"cid": "QmTest", "mime_type": "image/jpeg"}
        path = self.manager.get_partition_for_record(record)
        self.assertTrue(path.startswith(os.path.join(self.temp_dir, "content")))
    
    def test_get_optimal_strategy(self):
        """Test getting the optimal strategy."""
        # Default with no stats - will return highest score
        strategy = self.manager.get_optimal_strategy()
        
        # Update stats and check optimal strategy
        self.manager.update_workload_stats(
            temporal_access_score=0.9,
            content_type_score=0.1,
            size_variance_score=0.1,
            access_distribution_score=0.1
        )
        strategy = self.manager.get_optimal_strategy()
        self.assertEqual(strategy, PartitioningStrategy.TIME_BASED)
        
        # Change optimal strategy
        self.manager.update_workload_stats(
            temporal_access_score=0.1,
            content_type_score=0.9,
            size_variance_score=0.1,
            access_distribution_score=0.1
        )
        strategy = self.manager.get_optimal_strategy()
        self.assertEqual(strategy, PartitioningStrategy.CONTENT_TYPE)


@unittest.skipIf(not HAVE_PARTITIONING, "Advanced partitioning module not available")
class AdvancedPartitionManagerTest(unittest.TestCase):
    """Test the AdvancedPartitionManager class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)
    
    def test_init_with_different_strategies(self):
        """Test initialization with different strategies."""
        # Time-based
        time_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="time_based",
            config={"period": "daily"}
        )
        self.assertEqual(time_manager.strategy, PartitioningStrategy.TIME_BASED)
        self.assertIsInstance(time_manager.strategy_impl, TimeBasedPartitionStrategy)
        
        # Size-based
        size_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="size_based",
            config={"target_size_mb": 100}
        )
        self.assertEqual(size_manager.strategy, PartitioningStrategy.SIZE_BASED)
        self.assertIsInstance(size_manager.strategy_impl, SizeBasedPartitionStrategy)
        
        # Content-type
        content_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="content_type",
            config={"use_groups": True}
        )
        self.assertEqual(content_manager.strategy, PartitioningStrategy.CONTENT_TYPE)
        self.assertIsInstance(content_manager.strategy_impl, ContentTypePartitionStrategy)
        
        # Hash-based
        hash_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="hash_based",
            config={"num_partitions": 32}
        )
        self.assertEqual(hash_manager.strategy, PartitioningStrategy.HASH_BASED)
        self.assertIsInstance(hash_manager.strategy_impl, HashBasedPartitionStrategy)
        
        # Dynamic
        dynamic_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="dynamic",
            config={"default_strategy": "hash_based"}
        )
        self.assertEqual(dynamic_manager.strategy, PartitioningStrategy.DYNAMIC)
        self.assertIsInstance(dynamic_manager.strategy_impl, DynamicPartitionManager)
    
    def test_get_partition_path(self):
        """Test getting partition path for a record."""
        # Create manager with hash strategy
        manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="hash_based"
        )
        
        # Get path for a record
        record = {"cid": "QmTest"}
        path = manager.get_partition_path(record)
        
        # Should get a path
        self.assertIsInstance(path, str)
        self.assertTrue(path.startswith(self.temp_dir))
    
    def test_register_access(self):
        """Test registering access patterns."""
        # Only works with dynamic strategy
        manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="dynamic"
        )
        
        # Register an access
        record = {
            "cid": "QmTest",
            "mime_type": "image/jpeg",
            "timestamp": time.time()
        }
        manager.register_access(record, operation="read", size=1024)
        
        # Should have registered the access
        self.assertEqual(len(manager.strategy_impl.workload_stats["recent_access_patterns"]), 1)
        
        # Recent access should have the correct fields
        access = manager.strategy_impl.workload_stats["recent_access_patterns"][0]
        self.assertEqual(access["key"], "QmTest")
        self.assertEqual(access["content_type"], "image/jpeg")
        self.assertEqual(access["operation"], "read")
        self.assertEqual(access["size"], 1024)
    
    def test_analyze_workload(self):
        """Test workload analysis."""
        # Only works with dynamic strategy
        manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="dynamic"
        )
        
        # Register several accesses
        for i in range(10):
            record = {
                "cid": f"QmTest{i}",
                "mime_type": "image/jpeg" if i < 7 else "video/mp4",
                "timestamp": time.time() - i * 3600  # Each an hour apart
            }
            manager.register_access(record, operation="read", size=1024)
        
        # Analyze workload
        manager.analyze_workload(days=1)
        
        # Should have analyzed and updated scores
        # Content type score should be high (7/10 are image/jpeg)
        self.assertGreater(
            manager.strategy_impl.workload_stats["content_type_score"], 0.5
        )
    
    def test_get_partition_statistics(self):
        """Test getting partition statistics."""
        # Create different managers
        time_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="time_based"
        )
        
        hash_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="hash_based"
        )
        
        dynamic_manager = AdvancedPartitionManager(
            base_path=self.temp_dir,
            strategy="dynamic"
        )
        
        # Get statistics
        time_stats = time_manager.get_partition_statistics()
        hash_stats = hash_manager.get_partition_statistics()
        dynamic_stats = dynamic_manager.get_partition_statistics()
        
        # Check statistics fields
        self.assertEqual(time_stats["strategy"], "time_based")
        self.assertEqual(hash_stats["strategy"], "hash_based")
        self.assertEqual(dynamic_stats["strategy"], "dynamic")
        
        self.assertIn("period", time_stats)
        self.assertIn("num_partitions", hash_stats)
        self.assertIn("workload_stats", dynamic_stats)


if __name__ == "__main__":
    unittest.main()
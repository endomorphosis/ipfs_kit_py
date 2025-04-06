"""Unit tests for Schema and Column Optimization module."""

import unittest
import tempfile
import os
import shutil
import random
import time
from unittest.mock import patch, MagicMock

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc

from ipfs_kit_py.cache.schema_column_optimization import (
    WorkloadType,
    ColumnStatistics,
    SchemaProfiler,
    SchemaOptimizer,
    SchemaEvolutionManager,
    ParquetCIDCache,
    SchemaColumnOptimizationManager,
    create_example_data
)


class TestSchemaProfiler(unittest.TestCase):
    """Test the SchemaProfiler class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.profiler = SchemaProfiler()
        
        # Create test dataset with random data
        self.table = create_example_data(size=200)
        self.dataset_path = os.path.join(self.temp_dir, "test_dataset")
        os.makedirs(self.dataset_path, exist_ok=True)
        pq.write_table(self.table, os.path.join(self.dataset_path, "test.parquet"))
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_analyze_dataset(self):
        """Test analyzing a dataset for column statistics."""
        # Analyze the dataset
        stats = self.profiler.analyze_dataset(self.dataset_path)
        
        # Check that we have statistics for each column
        self.assertEqual(len(stats), len(self.table.column_names))
        
        # Check specific column statistics
        cid_stats = stats.get("cid")
        self.assertIsNotNone(cid_stats)
        self.assertEqual(cid_stats.column_name, "cid")
        self.assertEqual(cid_stats.data_type, "string")
        
        size_stats = stats.get("size_bytes")
        self.assertIsNotNone(size_stats)
        self.assertEqual(size_stats.column_name, "size_bytes")
        self.assertEqual(size_stats.data_type, "int64")
        
        # Check numerical statistics
        self.assertIsNotNone(size_stats.min_value)
        self.assertIsNotNone(size_stats.max_value)
        
        # Check for string length stats
        self.assertIsNotNone(cid_stats.min_value)  # Min length
        self.assertIsNotNone(cid_stats.max_value)  # Max length
    
    def test_track_query(self):
        """Test tracking query information."""
        # Track a simple query
        self.profiler.track_query({
            "operation": "read",
            "columns": ["cid", "size_bytes", "content_type"],
            "filters": ["cid"],
            "projections": ["cid", "size_bytes"],
            "timestamp": time.time()
        })
        
        # Check that column stats were updated
        self.assertIn("cid", self.profiler.column_stats)
        cid_stats = self.profiler.column_stats["cid"]
        self.assertEqual(cid_stats.access_count, 1)
        self.assertIsNotNone(cid_stats.last_accessed)
        self.assertEqual(cid_stats.access_pattern["filter"], 1)
        
        # Track another query
        self.profiler.track_query({
            "operation": "read",
            "columns": ["cid", "content_type"],
            "projections": ["content_type"],
            "timestamp": time.time()
        })
        
        # Check that the cid stats were updated
        self.assertEqual(cid_stats.access_count, 2)
        
        # Check query history
        self.assertEqual(len(self.profiler.query_history), 2)
    
    def test_workload_type_detection(self):
        """Test detection of workload types."""
        # Simulate read-heavy workload
        for _ in range(100):
            self.profiler.track_query({
                "operation": "read",
                "columns": ["cid", "size_bytes"],
                "filters": ["cid"],
                "timestamp": time.time()
            })
        
        # Force update of workload type
        self.profiler._update_workload_type()
        
        # Should detect READ_HEAVY workload
        self.assertEqual(self.profiler.workload_type, WorkloadType.READ_HEAVY)
        
        # Clear query history
        self.profiler.query_history = []
        
        # Simulate write-heavy workload
        for _ in range(100):
            self.profiler.track_query({
                "operation": "write",
                "columns": ["cid", "size_bytes", "content_type"],
                "timestamp": time.time()
            })
        
        # Force update of workload type
        self.profiler._update_workload_type()
        
        # Should detect WRITE_HEAVY workload
        self.assertEqual(self.profiler.workload_type, WorkloadType.WRITE_HEAVY)
        
        # Clear query history
        self.profiler.query_history = []
        
        # Simulate analytical workload
        for _ in range(100):
            self.profiler.track_query({
                "operation": "read",
                "columns": ["content_type", "size_bytes", "storage_backend"],
                "group_by": ["content_type", "storage_backend"],
                "projections": ["content_type", "storage_backend", "size_bytes"],
                "timestamp": time.time()
            })
        
        # Force update of workload type
        self.profiler._update_workload_type()
        
        # Should detect ANALYTICAL workload
        self.assertEqual(self.profiler.workload_type, WorkloadType.ANALYTICAL)
    
    def test_identify_unused_columns(self):
        """Test identification of unused columns."""
        # Analyze the dataset first
        self.profiler.analyze_dataset(self.dataset_path)
        
        # Initially all columns should be unused (no queries tracked)
        unused = self.profiler.identify_unused_columns()
        self.assertEqual(len(unused), len(self.table.column_names))
        
        # Track a query using some columns
        self.profiler.track_query({
            "operation": "read",
            "columns": ["cid", "size_bytes"],
            "filters": ["cid"],
            "timestamp": time.time()
        })
        
        # Get unused columns
        unused = self.profiler.identify_unused_columns()
        
        # cid and size_bytes should not be in unused columns
        self.assertNotIn("cid", unused)
        self.assertNotIn("size_bytes", unused)
        
        # Other columns should still be in unused
        self.assertIn("content_type", unused)
        self.assertIn("pinned", unused)
    
    def test_identify_index_candidates(self):
        """Test identification of index candidates."""
        # Track queries with filter conditions
        for _ in range(10):
            self.profiler.track_query({
                "operation": "read",
                "columns": ["cid", "content_type", "size_bytes"],
                "filters": ["content_type"],  # Filter by content_type
                "timestamp": time.time()
            })
        
        # content_type should be an index candidate
        candidates = self.profiler.identify_index_candidates()
        
        # Convert to dict for easier checking
        candidate_dict = dict(candidates)
        
        # content_type should be a candidate with high score
        self.assertIn("content_type", candidate_dict)
        self.assertGreater(candidate_dict["content_type"], 0)
        
        # Add more filter patterns on size_bytes
        for _ in range(20):
            self.profiler.track_query({
                "operation": "read",
                "columns": ["cid", "size_bytes"],
                "filters": ["size_bytes"],  # Filter by size_bytes
                "timestamp": time.time()
            })
        
        # Get updated candidates
        candidates = self.profiler.identify_index_candidates()
        candidate_dict = dict(candidates)
        
        # size_bytes should now be a higher priority candidate
        self.assertIn("size_bytes", candidate_dict)
        self.assertGreater(candidate_dict["size_bytes"], candidate_dict["content_type"])
        
        # First candidate should be size_bytes (highest score)
        self.assertEqual(candidates[0][0], "size_bytes")


class TestSchemaOptimizer(unittest.TestCase):
    """Test the SchemaOptimizer class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.profiler = SchemaProfiler()
        self.optimizer = SchemaOptimizer(self.profiler)
        
        # Create schema to optimize
        self.schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("pinned", pa.bool_()),
            pa.field("content_type", pa.string()),
            pa.field("added_timestamp", pa.float64()),
            pa.field("rarely_used", pa.string()),
            pa.field("never_used", pa.string())
        ])
        
        # Simulate access patterns
        for _ in range(10):
            self.profiler.track_query({
                "operation": "read",
                "columns": ["cid", "size_bytes", "content_type"],
                "filters": ["cid"],
                "timestamp": time.time()
            })
        
        # Rarely used column accessed only once
        self.profiler.track_query({
            "operation": "read",
            "columns": ["rarely_used"],
            "timestamp": time.time()
        })
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_optimize_schema(self):
        """Test optimizing a schema based on workload."""
        # Optimize for READ_HEAVY workload
        self.profiler.workload_type = WorkloadType.READ_HEAVY
        optimized_schema = self.optimizer.optimize_schema(self.schema)
        
        # Check that schema was optimized
        self.assertIsNotNone(optimized_schema)
        
        # Original schema has 7 fields
        self.assertEqual(len(self.schema), 7)
        
        # Optimize for ANALYTICAL workload
        self.profiler.workload_type = WorkloadType.ANALYTICAL
        optimized_schema = self.optimizer.optimize_schema(self.schema)
        
        # Check optimized field metadata
        for field in optimized_schema:
            # Check that field has optimization metadata
            self.assertIn(b"optimized_for", field.metadata)
            self.assertEqual(field.metadata[b"optimized_for"], b"analytical")
            
            # String fields in analytical workloads should have dictionary encoding
            if pa.types.is_string(field.type):
                if self.profiler.column_stats.get(field.name, None) and \
                   self.profiler.column_stats[field.name].distinct_count > 0 and \
                   self.profiler.column_stats[field.name].distinct_count < 1000:
                    self.assertIn(b"encoding", field.metadata)
                    self.assertEqual(field.metadata[b"encoding"], b"dictionary")
    
    def test_generate_pruned_schema(self):
        """Test generating a pruned schema that removes rarely used columns."""
        # Generate pruned schema with threshold
        pruned_schema = self.optimizer.generate_pruned_schema(self.schema, usage_threshold=0.5)
        
        # Check that rarely and never used columns are pruned
        self.assertNotIn("rarely_used", pruned_schema.names)
        self.assertNotIn("never_used", pruned_schema.names)
        
        # But frequently used columns are kept
        self.assertIn("cid", pruned_schema.names)
        self.assertIn("size_bytes", pruned_schema.names)
        self.assertIn("content_type", pruned_schema.names)
    
    def test_is_critical_field(self):
        """Test detection of critical fields."""
        # These fields should be critical even if unused
        critical_fields = ["cid", "id", "key", "hash"]
        
        for field in critical_fields:
            self.assertTrue(
                self.optimizer._is_critical_field(field, self.schema),
                f"Field {field} should be considered critical"
            )
        
        # Non-critical fields
        non_critical = ["content_type", "rarely_used"]
        for field in non_critical:
            self.assertFalse(
                self.optimizer._is_critical_field(field, self.schema),
                f"Field {field} should not be considered critical"
            )
    
    def test_create_index(self):
        """Test creation of specialized indexes."""
        # Create a dataset for indexing
        table = create_example_data(size=200)
        dataset_path = os.path.join(self.temp_dir, "index_test")
        os.makedirs(dataset_path, exist_ok=True)
        pq.write_table(table, os.path.join(dataset_path, "data.parquet"))
        
        # Create a B-tree index
        index_path = self.optimizer.create_index(dataset_path, "content_type", "btree")
        
        # Check that index was created
        self.assertTrue(os.path.exists(index_path))
        
        # Index should be a Parquet file
        table = pq.read_table(index_path)
        
        # Should contain content_type and cid columns
        self.assertIn("content_type", table.column_names)
        self.assertIn("cid", table.column_names)
        
        # Create a hash index
        hash_path = self.optimizer.create_index(dataset_path, "pinned", "hash")
        
        # Check that index was created
        self.assertTrue(os.path.exists(hash_path))
        
        # Hash index should be a JSON file
        with open(hash_path, 'r') as f:
            import json
            hash_data = json.load(f)
            
        # Should be a list of entries with values and CIDs
        self.assertTrue(isinstance(hash_data, list))
        self.assertGreater(len(hash_data), 0)
        self.assertIn("value", hash_data[0])
        self.assertIn("cids", hash_data[0])


class TestSchemaEvolutionManager(unittest.TestCase):
    """Test the SchemaEvolutionManager class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SchemaEvolutionManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_register_schema(self):
        """Test registering schema versions."""
        # Create initial schema
        initial_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("content_type", pa.string())
        ])
        
        # Register initial schema
        version = self.manager.register_schema(initial_schema, "Initial schema")
        
        # Should be version 1
        self.assertEqual(version, 1)
        
        # Current version should be updated
        self.assertEqual(self.manager.current_version, 1)
        
        # Version file should exist
        version_path = os.path.join(self.manager.versions_dir, f"schema_v{version}.json")
        self.assertTrue(os.path.exists(version_path))
        
        # Register same schema again - should not increment version
        version = self.manager.register_schema(initial_schema, "Same schema")
        self.assertEqual(version, 1)
        
        # Register evolved schema
        evolved_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("content_type", pa.string()),
            pa.field("pinned", pa.bool_())  # New field
        ])
        
        # Register evolved schema
        version = self.manager.register_schema(evolved_schema, "Added pinned field")
        
        # Should be version 2
        self.assertEqual(version, 2)
    
    def test_get_schema(self):
        """Test retrieving schema by version."""
        # Register a schema
        initial_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64())
        ])
        version = self.manager.register_schema(initial_schema, "Initial schema")
        
        # Get the schema back
        retrieved_schema = self.manager.get_schema(version)
        
        # Should be equivalent to initial schema
        self.assertEqual(len(retrieved_schema), len(initial_schema))
        self.assertEqual(retrieved_schema.names, initial_schema.names)
        for i, field in enumerate(retrieved_schema):
            self.assertEqual(field.name, initial_schema[i].name)
            self.assertEqual(str(field.type), str(initial_schema[i].type))
    
    def test_compatibility_view(self):
        """Test creating compatibility view between schema versions."""
        # Register initial schema (v1)
        v1_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("content_type", pa.string())
        ])
        v1 = self.manager.register_schema(v1_schema, "Initial schema")
        
        # Register evolved schema (v2)
        v2_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            # content_type removed
            pa.field("pinned", pa.bool_()),  # New field
            pa.field("replication", pa.int32())  # New field
        ])
        v2 = self.manager.register_schema(v2_schema, "Evolved schema")
        
        # Create compatibility view
        compatibility = self.manager.create_compatibility_view(v1_schema, v2)
        
        # Check compatibility info
        self.assertFalse(compatibility["fully_compatible"])
        self.assertEqual(compatibility["current_version"], 2)
        self.assertEqual(compatibility["target_version"], 2)
        
        # Check added/removed fields
        self.assertEqual(len(compatibility["added_fields"]), 0)  # No added fields in current v1 schema
        self.assertEqual(len(compatibility["removed_fields"]), 2)  # content_type removed, and 2 new fields in v2
        self.assertIn("pinned", compatibility["removed_fields"])
        self.assertIn("replication", compatibility["removed_fields"])
        
        # Check transformations
        self.assertEqual(len(compatibility["transformations"]), 2)
        
        # Should have provide_default transformations for new fields
        for transform in compatibility["transformations"]:
            self.assertEqual(transform["type"], "provide_default")
    
    def test_apply_transformations(self):
        """Test applying compatibility transformations to data."""
        # Register initial schema (v1)
        v1_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64())
        ])
        v1 = self.manager.register_schema(v1_schema, "Initial schema")
        
        # Register evolved schema (v2)
        v2_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("pinned", pa.bool_())  # New field
        ])
        v2 = self.manager.register_schema(v2_schema, "Evolved schema")
        
        # Create v1 data
        v1_data = pa.Table.from_arrays([
            pa.array(["Qm123", "Qm456"]),
            pa.array([1000, 2000])
        ], schema=v1_schema)
        
        # Create compatibility view
        compatibility = self.manager.create_compatibility_view(v1_schema, v2)
        
        # Apply transformations
        transformed_data = self.manager.apply_compatibility_transformations(v1_data, compatibility)
        
        # Check transformed data
        self.assertEqual(transformed_data.num_columns, 3)  # Should have new column
        self.assertEqual(transformed_data.num_rows, 2)
        self.assertIn("pinned", transformed_data.column_names)
        
        # New column should be all nulls
        self.assertTrue(pc.all(pc.is_null(transformed_data["pinned"])).as_py())


class TestParquetCIDCache(unittest.TestCase):
    """Test the ParquetCIDCache mock implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ParquetCIDCache(self.temp_dir)
        
        # Create test data
        self.table = create_example_data(size=100)
        pq.write_table(self.table, os.path.join(self.temp_dir, "data.parquet"))
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_optimize_schema(self):
        """Test schema optimization in cache."""
        # Should have parquet files
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "data.parquet")))
        
        # Optimize schema
        result = self.cache.optimize_schema()
        
        # Should succeed
        self.assertTrue(result)
        
        # Should be marked as optimized
        self.assertTrue(self.cache.optimized)
        
        # Should have created schema versions directory
        versions_dir = os.path.join(self.temp_dir, "_schema_versions")
        self.assertTrue(os.path.exists(versions_dir))
        
        # Should have at least one schema version
        version_files = [f for f in os.listdir(versions_dir) 
                         if f.startswith("schema_v") and f.endswith(".json")]
        self.assertGreater(len(version_files), 0)
    
    def test_apply_schema_to_new_data(self):
        """Test applying optimized schema to new data."""
        # Optimize schema first
        self.cache.optimize_schema()
        
        # Create new data with different schema
        new_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("extra_field", pa.string())  # Extra field not in optimized schema
        ])
        
        new_data = pa.Table.from_arrays([
            pa.array(["Qm123", "Qm456"]),
            pa.array([1000, 2000]),
            pa.array(["extra1", "extra2"])
        ], schema=new_schema)
        
        # Apply optimized schema
        transformed_data = self.cache.apply_schema_to_new_data(new_data)
        
        # Should have compatible schema
        self.assertNotEqual(transformed_data.schema, new_schema)


class TestSchemaColumnOptimizationManager(unittest.TestCase):
    """Test the SchemaColumnOptimizationManager class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test dataset
        self.table = create_example_data(size=100)
        os.makedirs(os.path.join(self.temp_dir, "data"), exist_ok=True)
        pq.write_table(self.table, os.path.join(self.temp_dir, "data", "test.parquet"))
        
        # Create manager
        self.manager = SchemaColumnOptimizationManager(os.path.join(self.temp_dir, "data"))
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_track_query(self):
        """Test tracking queries in the manager."""
        # Track a query
        self.manager.track_query({
            "operation": "read",
            "columns": ["cid", "content_type"],
            "filters": ["cid"],
            "timestamp": time.time()
        })
        
        # Should be tracked in profiler
        self.assertEqual(len(self.manager.profiler.query_history), 1)
        self.assertEqual(self.manager.query_count, 1)
        
        # Track many queries to trigger optimization
        original_interval = self.manager.optimization_interval
        self.manager.optimization_interval = 0  # Force immediate optimization
        
        # Mock optimize_schema to verify it's called
        with patch.object(self.manager, 'optimize_schema') as mock_optimize:
            # Track enough queries to trigger optimization
            for _ in range(100):
                self.manager.track_query({
                    "operation": "read",
                    "columns": ["cid"],
                    "timestamp": time.time()
                })
            
            # Should have called optimize_schema
            mock_optimize.assert_called_once()
    
    def test_optimize_schema(self):
        """Test schema optimization through manager."""
        # Track some queries to establish patterns
        for _ in range(50):
            self.manager.track_query({
                "operation": "read",
                "columns": ["cid", "size_bytes"],
                "filters": ["cid"],
                "timestamp": time.time()
            })
        
        # Run optimization
        result = self.manager.optimize_schema()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertGreater(result["schema_version"], 0)
        self.assertEqual(result["workload_type"], self.manager.profiler.workload_type.value)
        
        # Check schema dir was created
        versions_dir = os.path.join(self.temp_dir, "data", "_schema_versions")
        self.assertTrue(os.path.exists(versions_dir))
    
    def test_get_schema_info(self):
        """Test getting schema information."""
        # Get initial schema info
        info = self.manager.get_schema_info()
        
        # Should have basic information
        self.assertIn("dataset_path", info)
        self.assertIn("workload_type", info)
        
        # Track some queries to establish patterns
        for _ in range(20):
            self.manager.track_query({
                "operation": "read",
                "columns": ["cid", "content_type"],
                "timestamp": time.time()
            })
        
        # Get updated schema info
        info = self.manager.get_schema_info()
        
        # Should have access frequency information
        self.assertIn("most_accessed_columns", info)
        self.assertEqual(len(info["most_accessed_columns"]), min(5, len(self.manager.profiler.column_stats)))
    
    def test_apply_optimized_schema(self):
        """Test applying optimized schema to data."""
        # Optimize schema first
        self.manager.optimize_schema()
        
        # Create test data
        test_data = pa.Table.from_arrays([
            pa.array(["Qm123", "Qm456"]),
            pa.array([1000, 2000]),
            pa.array([True, False])
        ], names=["cid", "size_bytes", "pinned"])
        
        # Apply optimized schema
        result = self.manager.apply_optimized_schema(test_data)
        
        # Should return a table
        self.assertIsInstance(result, pa.Table)
        
        # Should have same number of rows
        self.assertEqual(result.num_rows, test_data.num_rows)
        
        # Test with original=True
        original_result = self.manager.apply_optimized_schema(test_data, original=True)
        
        # Should return the original table unchanged
        self.assertEqual(original_result, test_data)


if __name__ == '__main__':
    unittest.main()
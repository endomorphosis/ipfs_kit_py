#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the Parallel Query Execution module.

These tests verify the functionality of the parallel query execution
system, including query building, execution, optimization, and caching.
"""

import os
import tempfile
import time
import unittest
import uuid
import shutil
from typing import List, Dict, Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from unittest.mock import patch, MagicMock

from ipfs_kit_py.cache.parallel_query_execution import (
    ParallelQueryManager,
    Query,
    QueryType,
    QueryPredicate,
    QueryAggregation,
    ThreadPoolManager,
    QueryCacheManager,
    QueryPlanner,
    PartitionExecutor
)


class TestQueryPredicate(unittest.TestCase):
    """Test the QueryPredicate class."""

    def test_init(self):
        """Test initialization of QueryPredicate."""
        predicate = QueryPredicate("field", "==", "value")
        self.assertEqual(predicate.field, "field")
        self.assertEqual(predicate.operator, "==")
        self.assertEqual(predicate.value, "value")
    
    def test_to_arrow_expression(self):
        """Test conversion to PyArrow expression."""
        # Test equality predicate
        eq_predicate = QueryPredicate("field", "==", "value")
        expr = eq_predicate.to_arrow_expression()
        self.assertTrue(isinstance(expr, pa.compute.Expression))
        
        # Test numeric comparison predicate
        gt_predicate = QueryPredicate("numeric_field", ">", 100)
        expr = gt_predicate.to_arrow_expression()
        self.assertTrue(isinstance(expr, pa.compute.Expression))
        
        # Test IN predicate
        in_predicate = QueryPredicate("category", "in", ["A", "B", "C"])
        expr = in_predicate.to_arrow_expression()
        self.assertTrue(isinstance(expr, pa.compute.Expression))
    
    def test_serialize_deserialize(self):
        """Test serialization and deserialization of predicates."""
        original = QueryPredicate("field", "!=", 42)
        serialized = original.serialize()
        
        # Check that it's a dict with expected keys
        self.assertTrue(isinstance(serialized, dict))
        self.assertIn("field", serialized)
        self.assertIn("operator", serialized)
        self.assertIn("value", serialized)
        
        # Deserialize and verify
        deserialized = QueryPredicate.deserialize(serialized)
        self.assertEqual(deserialized.field, original.field)
        self.assertEqual(deserialized.operator, original.operator)
        self.assertEqual(deserialized.value, original.value)


class TestQueryAggregation(unittest.TestCase):
    """Test the QueryAggregation class."""

    def test_init(self):
        """Test initialization of QueryAggregation."""
        agg = QueryAggregation("field", "sum", "total")
        self.assertEqual(agg.field, "field")
        self.assertEqual(agg.function, "sum")
        self.assertEqual(agg.alias, "total")
    
    def test_apply(self):
        """Test application of aggregation function to data."""
        # Create test data
        data = pa.table({
            'numeric': pa.array([1, 2, 3, 4, 5]),
            'category': pa.array(['A', 'A', 'B', 'B', 'C'])
        })
        
        # Test sum aggregation
        sum_agg = QueryAggregation("numeric", "sum", "total")
        result = sum_agg.apply(data)
        self.assertEqual(result, 15)  # 1+2+3+4+5 = 15
        
        # Test mean aggregation
        mean_agg = QueryAggregation("numeric", "mean", "avg")
        result = mean_agg.apply(data)
        self.assertEqual(result, 3.0)  # (1+2+3+4+5)/5 = 3.0
        
        # Test min aggregation
        min_agg = QueryAggregation("numeric", "min", "minimum")
        result = min_agg.apply(data)
        self.assertEqual(result, 1)
        
        # Test max aggregation
        max_agg = QueryAggregation("numeric", "max", "maximum")
        result = max_agg.apply(data)
        self.assertEqual(result, 5)
        
        # Test count aggregation
        count_agg = QueryAggregation("numeric", "count", "count")
        result = count_agg.apply(data)
        self.assertEqual(result, 5)


class TestQuery(unittest.TestCase):
    """Test the Query class."""

    def test_init(self):
        """Test Query initialization."""
        query = Query(
            query_type=QueryType.SIMPLE_LOOKUP,
            predicates=[QueryPredicate("id", "==", 42)],
            projections=["id", "name", "value"],
            limit=10
        )
        
        self.assertEqual(query.query_type, QueryType.SIMPLE_LOOKUP)
        self.assertEqual(len(query.predicates), 1)
        self.assertEqual(query.predicates[0].field, "id")
        self.assertEqual(query.projections, ["id", "name", "value"])
        self.assertEqual(query.limit, 10)
    
    def test_hash_for_caching(self):
        """Test generation of hash key for caching."""
        query1 = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[
                QueryPredicate("score", ">", 90),
                QueryPredicate("category", "==", "A")
            ],
            projections=["id", "name", "score"],
            limit=100
        )
        
        query2 = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[
                QueryPredicate("score", ">", 90),
                QueryPredicate("category", "==", "A")
            ],
            projections=["id", "name", "score"],
            limit=100
        )
        
        # Same queries should have same hash
        self.assertEqual(query1.hash_for_caching(), query2.hash_for_caching())
        
        # Change a predicate, hash should differ
        query3 = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[
                QueryPredicate("score", ">", 95),  # Changed threshold
                QueryPredicate("category", "==", "A")
            ],
            projections=["id", "name", "score"],
            limit=100
        )
        self.assertNotEqual(query1.hash_for_caching(), query3.hash_for_caching())
        
        # Change projection order, hash should differ
        query4 = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[
                QueryPredicate("score", ">", 90),
                QueryPredicate("category", "==", "A")
            ],
            projections=["name", "id", "score"],  # Changed order
            limit=100
        )
        self.assertNotEqual(query1.hash_for_caching(), query4.hash_for_caching())


class TestQueryCacheManager(unittest.TestCase):
    """Test the QueryCacheManager class."""

    def setUp(self):
        """Set up tests."""
        self.cache_manager = QueryCacheManager(max_cache_entries=5)
        self.test_query = Query(
            query_type=QueryType.SIMPLE_LOOKUP,
            predicates=[QueryPredicate("id", "==", 42)],
            projections=["id", "name", "value"]
        )
        self.test_result = pa.table({
            'id': pa.array([42]),
            'name': pa.array(['test']),
            'value': pa.array([100])
        })
    
    def test_put_get(self):
        """Test putting and getting from cache."""
        query_hash = self.test_query.hash_for_caching()
        
        # Put into cache
        self.cache_manager.put(self.test_query, self.test_result)
        
        # Get from cache
        result = self.cache_manager.get(self.test_query)
        self.assertIsNotNone(result)
        
        # Verify the result is the same
        self.assertEqual(result.num_rows, self.test_result.num_rows)
        self.assertEqual(result.num_columns, self.test_result.num_columns)
        self.assertEqual(result.column_names, self.test_result.column_names)
    
    def test_max_entries(self):
        """Test that cache respects max_entries limit."""
        # Add more entries than the limit
        for i in range(10):
            query = Query(
                query_type=QueryType.SIMPLE_LOOKUP,
                predicates=[QueryPredicate("id", "==", i)],
                projections=["id", "value"]
            )
            result = pa.table({
                'id': pa.array([i]),
                'value': pa.array([i * 10])
            })
            self.cache_manager.put(query, result)
        
        # Cache should only have max_cache_entries items
        stats = self.cache_manager.get_statistics()
        self.assertLessEqual(stats.get('current_size', 0), self.cache_manager.max_cache_entries)
        
        # First queries should be evicted
        early_query = Query(
            query_type=QueryType.SIMPLE_LOOKUP,
            predicates=[QueryPredicate("id", "==", 0)],
            projections=["id", "value"]
        )
        self.assertIsNone(self.cache_manager.get(early_query))
        
        # Latest queries should still be in cache
        late_query = Query(
            query_type=QueryType.SIMPLE_LOOKUP,
            predicates=[QueryPredicate("id", "==", 9)],
            projections=["id", "value"]
        )
        self.assertIsNotNone(self.cache_manager.get(late_query))


class TestThreadPoolManager(unittest.TestCase):
    """Test the ThreadPoolManager class."""

    def test_thread_allocation(self):
        """Test thread allocation based on resource requirements."""
        # Create a ThreadPoolManager with 8 max workers
        thread_manager = ThreadPoolManager(max_workers=8)
        
        # For a single task with high priority, it should allocate all threads
        allocations = thread_manager.allocate_threads(
            num_tasks=1,
            priority="high",
            resource_requirement="high"
        )
        self.assertEqual(allocations[0], 8)  # All threads to one task
        
        # For multiple tasks, it should distribute threads
        allocations = thread_manager.allocate_threads(
            num_tasks=4,
            priority="medium",
            resource_requirement="medium"
        )
        self.assertEqual(len(allocations), 4)
        self.assertEqual(sum(allocations), 8)  # Total should equal max workers
        
        # For many low-resource tasks, it may allocate 1 thread per task
        allocations = thread_manager.allocate_threads(
            num_tasks=10,
            priority="low",
            resource_requirement="low"
        )
        self.assertEqual(len(allocations), 10)
        self.assertEqual(sum(allocations), 8)  # Total limited by max workers
        self.assertEqual(allocations.count(1), 8)  # 8 tasks get 1 thread
        self.assertEqual(allocations.count(0), 2)  # 2 tasks get no threads (will run sequentially)


class TestPartitionExecutor(unittest.TestCase):
    """Test the PartitionExecutor class."""
    
    def setUp(self):
        """Set up test data."""
        # Create a temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        
        # Create test data
        df = pd.DataFrame({
            'id': range(100),
            'category': ['A', 'B', 'C', 'D', 'E'] * 20,
            'value': np.random.randint(1, 1000, size=100)
        })
        
        # Save as parquet
        self.test_file = os.path.join(self.test_dir, 'test_data.parquet')
        df.to_parquet(self.test_file)
        
        # Create partition executor
        self.executor = PartitionExecutor(num_threads=2)
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.test_dir)
    
    def test_execute_query(self):
        """Test executing a query on a partition."""
        query = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[QueryPredicate("value", ">", 500)],
            projections=["id", "category", "value"]
        )
        
        # Execute query
        result = self.executor.execute_query(query, self.test_file)
        
        # Check result
        self.assertIsInstance(result, pa.Table)
        self.assertEqual(result.column_names, ["id", "category", "value"])
        
        # Convert to pandas for easier validation
        result_df = result.to_pandas()
        
        # All values should be > 500
        self.assertTrue((result_df['value'] > 500).all())
    
    def test_execute_aggregate_query(self):
        """Test executing an aggregate query."""
        query = Query(
            query_type=QueryType.AGGREGATE,
            predicates=[],
            projections=["category"],
            group_by=["category"],
            aggregations=[
                QueryAggregation("value", "mean", "avg_value"),
                QueryAggregation("id", "count", "count")
            ]
        )
        
        # Execute query
        result = self.executor.execute_query(query, self.test_file)
        
        # Check result
        self.assertIsInstance(result, pa.Table)
        self.assertIn("category", result.column_names)
        self.assertIn("avg_value", result.column_names)
        self.assertIn("count", result.column_names)
        
        # Convert to pandas for easier validation
        result_df = result.to_pandas()
        
        # There should be an entry for each category
        self.assertEqual(len(result_df), 5)  # A, B, C, D, E
        
        # Each category should have 20 items
        self.assertTrue((result_df['count'] == 20).all())


class TestQueryPlanner(unittest.TestCase):
    """Test the QueryPlanner class."""
    
    def setUp(self):
        """Set up test data."""
        self.planner = QueryPlanner()
        
        # Create a simple query
        self.test_query = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[
                QueryPredicate("category", "==", "A"),
                QueryPredicate("value", ">", 500)
            ],
            projections=["id", "category", "value", "extra_field"]
        )
        
        # Create partition metadata for testing
        self.partition_metadata = [
            {"path": "/path/to/partition1.parquet", "categories": ["A", "B"], "min_value": 100, "max_value": 600},
            {"path": "/path/to/partition2.parquet", "categories": ["C", "D"], "min_value": 200, "max_value": 700},
            {"path": "/path/to/partition3.parquet", "categories": ["A", "E"], "min_value": 300, "max_value": 800},
            {"path": "/path/to/partition4.parquet", "categories": ["B", "C"], "min_value": 400, "max_value": 900}
        ]
    
    def test_optimize_query(self):
        """Test query optimization."""
        # Create a plan with all optimizations enabled
        original_query = self.test_query
        optimized_query = self.planner.optimize_query(original_query, self.partition_metadata)
        
        # The optimized query should still have the same predicates
        self.assertEqual(len(optimized_query.predicates), len(original_query.predicates))
        
        # Check that the query plan includes partitions to process
        query_plan = self.planner.get_last_query_plan()
        self.assertIn("partitions_to_process", query_plan)
        
        # Only partitions with category "A" should be included
        self.assertEqual(len(query_plan["partitions_to_process"]), 2)  # partition1 and partition3
        paths = [p["path"] for p in query_plan["partitions_to_process"]]
        self.assertIn("/path/to/partition1.parquet", paths)
        self.assertIn("/path/to/partition3.parquet", paths)
    
    def test_predicate_pushdown(self):
        """Test predicate pushdown optimization."""
        # Force predicate pushdown only
        self.planner.enable_predicate_pushdown(True)
        self.planner.enable_projection_pruning(False)
        self.planner.enable_partition_pruning(False)
        
        optimized_query = self.planner.optimize_query(self.test_query, [])
        
        # The predicates should be in the optimized query
        self.assertEqual(len(optimized_query.predicates), len(self.test_query.predicates))
        
        query_plan = self.planner.get_last_query_plan()
        self.assertTrue(query_plan["predicate_pushdown"])
    
    def test_projection_pruning(self):
        """Test projection pruning optimization."""
        # Force projection pruning only
        self.planner.enable_predicate_pushdown(False)
        self.planner.enable_projection_pruning(True)
        self.planner.enable_partition_pruning(False)
        
        # Create a list of available columns
        available_columns = ["id", "category", "value", "timestamp", "extra_field"]
        
        # Mock metadata to include column info
        metadata = [{"path": "/path/to/mock.parquet", "columns": available_columns}]
        
        # Create a query with a subset of columns
        query = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[QueryPredicate("category", "==", "A")],
            projections=["id", "category", "value"]  # Not requesting extra_field
        )
        
        optimized_query = self.planner.optimize_query(query, metadata)
        
        # The optimized query's projections should only include the requested columns
        self.assertEqual(set(optimized_query.projections), set(["id", "category", "value"]))
        
        query_plan = self.planner.get_last_query_plan()
        self.assertTrue(query_plan["projection_pruning"])
        self.assertGreater(query_plan["columns_pruned"], 0)  # Some columns should be pruned


class TestParallelQueryManager(unittest.TestCase):
    """Test the ParallelQueryManager class."""
    
    def setUp(self):
        """Set up test data."""
        # Create a temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        
        # Create several test partition files
        self.partition_files = []
        for i in range(3):
            # Create test data with some patterns
            df = pd.DataFrame({
                'id': range(i*100, (i+1)*100),
                'category': ['A', 'B', 'C', 'D', 'E'] * 20,
                'value': np.random.randint(1, 1000, size=100)
            })
            
            # Add some patterns for easier testing
            if i == 0:
                df.loc[df['category'] == 'A', 'value'] = 999  # All category A in first partition has value 999
            
            # Save as parquet
            partition_path = os.path.join(self.test_dir, f'partition_{i}.parquet')
            df.to_parquet(partition_path)
            self.partition_files.append(partition_path)
        
        # Create the manager
        self.thread_pool_manager = ThreadPoolManager(max_workers=4)
        self.query_cache_manager = QueryCacheManager(max_cache_entries=10)
        self.manager = ParallelQueryManager(
            thread_pool_manager=self.thread_pool_manager,
            query_cache_manager=self.query_cache_manager
        )
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.test_dir)
    
    def test_execute_simple_query(self):
        """Test executing a simple query."""
        query = Query(
            query_type=QueryType.SIMPLE_LOOKUP,
            predicates=[QueryPredicate("category", "==", "A")],
            projections=["id", "category", "value"]
        )
        
        # Execute query
        result = self.manager.execute_query(query, self.partition_files)
        
        # Check result
        self.assertIsInstance(result, pa.Table)
        self.assertEqual(result.column_names, ["id", "category", "value"])
        
        # Convert to pandas for easier validation
        result_df = result.to_pandas()
        
        # All results should have category A
        self.assertTrue((result_df['category'] == 'A').all())
        
        # There should be 60 results (20 per partition)
        self.assertEqual(len(result_df), 60)
    
    def test_execute_aggregate_query(self):
        """Test executing an aggregate query."""
        query = Query(
            query_type=QueryType.AGGREGATE,
            predicates=[],
            projections=["category"],
            group_by=["category"],
            aggregations=[
                QueryAggregation("value", "mean", "avg_value"),
                QueryAggregation("id", "count", "count")
            ]
        )
        
        # Execute query
        result = self.manager.execute_query(query, self.partition_files)
        
        # Check result
        self.assertIsInstance(result, pa.Table)
        
        # Convert to pandas for easier validation
        result_df = result.to_pandas()
        
        # There should be 5 groups (A, B, C, D, E)
        self.assertEqual(len(result_df), 5)
        
        # Each category should have 60 items (20 per partition x 3 partitions)
        self.assertTrue((result_df['count'] == 60).all())
    
    def test_query_caching(self):
        """Test that query results are cached."""
        # Create a query
        query = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[QueryPredicate("value", ">", 500)],
            projections=["id", "category", "value"]
        )
        
        # Execute query the first time (should cache the result)
        result1 = self.manager.execute_query(query, self.partition_files)
        
        # Check cache statistics
        cache_stats = self.manager.query_cache_manager.get_statistics()
        self.assertEqual(cache_stats['hits'], 0)
        self.assertEqual(cache_stats['misses'], 1)
        
        # Execute the same query again (should use cache)
        result2 = self.manager.execute_query(query, self.partition_files)
        
        # Check updated cache statistics
        cache_stats = self.manager.query_cache_manager.get_statistics()
        self.assertEqual(cache_stats['hits'], 1)
        self.assertEqual(cache_stats['misses'], 1)
        
        # Results should be identical
        self.assertEqual(result1.num_rows, result2.num_rows)
        self.assertEqual(result1.column_names, result2.column_names)
    
    def test_parallel_execution(self):
        """Test parallel execution of queries."""
        # Create a query that benefits from parallelization
        query = Query(
            query_type=QueryType.RANGE_SCAN,
            predicates=[QueryPredicate("value", ">", 100)],
            projections=["id", "category", "value"]
        )
        
        # Patch the executor's execute_query method to track calls
        original_execute = PartitionExecutor.execute_query
        call_count = [0]
        
        def mock_execute(self, *args, **kwargs):
            call_count[0] += 1
            return original_execute(self, *args, **kwargs)
        
        # Apply the patch
        with patch.object(PartitionExecutor, 'execute_query', mock_execute):
            # Execute the query
            result = self.manager.execute_query(query, self.partition_files)
            
            # Check the results
            self.assertIsInstance(result, pa.Table)
            
            # The executor should be called once per partition
            self.assertEqual(call_count[0], len(self.partition_files))


if __name__ == '__main__':
    unittest.main()
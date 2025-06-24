"""
Parallel Query Execution module for ParquetCIDCache.

This module implements parallel query execution capabilities for ParquetCIDCache:
- Multi-threaded query execution for complex analytical operations
- Partition-parallel scanning for large datasets
- Worker pools for compute-intensive operations
- Thread allocation optimization based on query complexity
- Query planning for efficient execution paths

These optimizations significantly improve query performance on large datasets,
especially for complex analytical operations across multiple partitions.
"""

import os
import time
import logging
import json
import uuid
import math
import threading
import queue
import concurrent.futures
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable
from dataclasses import dataclass
from functools import partial

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
import pyarrow.dataset as ds
from pyarrow.dataset import dataset

# Configure logging
logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Enum representing different types of queries."""
    SIMPLE_LOOKUP = "simple_lookup"  # Point lookups by key/CID
    RANGE_SCAN = "range_scan"        # Range-based scans
    AGGREGATE = "aggregate"          # Aggregation queries
    JOIN = "join"                    # Join operations
    GROUP_BY = "group_by"            # Group by operations
    COMPLEX_ANALYTICAL = "complex_analytical"  # Complex analytical queries


@dataclass
class QueryPredicate:
    """Represents a filter predicate for a query."""
    column: str
    op: str  # ==, !=, >, >=, <, <=, in, contains, between, is_null, etc.
    value: Any

    def to_arrow_expression(self) -> pc.Expression:
        """Convert to PyArrow expression."""
        field_ref = pc.field(self.column)

        if self.op == "==":
            return pc.equal(field_ref, pa.scalar(self.value))
        elif self.op == "!=":
            return pc.not_equal(field_ref, pa.scalar(self.value))
        elif self.op == ">":
            return pc.greater(field_ref, pa.scalar(self.value))
        elif self.op == ">=":
            return pc.greater_equal(field_ref, pa.scalar(self.value))
        elif self.op == "<":
            return pc.less(field_ref, pa.scalar(self.value))
        elif self.op == "<=":
            return pc.less_equal(field_ref, pa.scalar(self.value))
        elif self.op == "in":
            if not isinstance(self.value, (list, tuple)):
                value_list = [self.value]
            else:
                value_list = self.value
            return pc.is_in(field_ref, pa.array(value_list))
        elif self.op == "contains":
            return pc.match_substring(field_ref, self.value)
        elif self.op == "between":
            if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
                raise ValueError("Between requires a list/tuple of two values: [min, max]")
            return pc.and_(
                pc.greater_equal(field_ref, pa.scalar(self.value[0])),
                pc.less_equal(field_ref, pa.scalar(self.value[1]))
            )
        elif self.op == "is_null":
            return pc.is_null(field_ref)
        elif self.op == "is_not_null":
            return pc.is_valid(field_ref)
        elif self.op == "starts_with":
            return pc.starts_with(field_ref, self.value)
        elif self.op == "ends_with":
            return pc.ends_with(field_ref, self.value)
        else:
            raise ValueError(f"Unsupported operator: {self.op}")


@dataclass
class QueryAggregation:
    """Represents an aggregation operation."""
    column: str
    operation: str  # sum, min, max, mean, count, count_distinct, etc.
    alias: Optional[str] = None

    def get_alias(self) -> str:
        """Get the alias for the aggregation result."""
        if self.alias:
            return self.alias
        return f"{self.operation}_{self.column}"

    def compute(self, table: pa.Table) -> pa.Scalar:
        """Compute the aggregation on the given table."""
        if not self.column in table.column_names and self.operation != "count":
            raise ValueError(f"Column '{self.column}' not found in table")

        if self.operation == "sum":
            return pc.sum(table[self.column])
        elif self.operation == "min":
            return pc.min(table[self.column])
        elif self.operation == "max":
            return pc.max(table[self.column])
        elif self.operation == "mean":
            return pc.mean(table[self.column])
        elif self.operation == "count":
            if self.column == "*":
                return pa.scalar(table.num_rows)
            else:
                return pc.count(table[self.column])
        elif self.operation == "count_distinct":
            # First compute unique values, then count them
            unique = pc.unique(table[self.column])
            return pa.scalar(len(unique))
        elif self.operation == "stddev":
            return pc.stddev(table[self.column])
        elif self.operation == "variance":
            return pc.variance(table[self.column])
        else:
            raise ValueError(f"Unsupported aggregation operation: {self.operation}")


@dataclass
class Query:
    """Represents a query to be executed."""
    predicates: Optional[List[QueryPredicate]] = None
    projection: Optional[List[str]] = None  # Columns to return
    aggregations: Optional[List[QueryAggregation]] = None
    group_by: Optional[List[str]] = None
    order_by: Optional[List[Tuple[str, str]]] = None  # List of (column, direction)
    limit: Optional[int] = None
    query_id: str = None  # Unique identifier for the query
    estimated_complexity: float = 1.0  # Estimated complexity score (higher = more complex)

    def __post_init__(self):
        """Initialize additional attributes after creation."""
        if self.query_id is None:
            self.query_id = str(uuid.uuid4())

        # Calculate estimated complexity if not provided
        if self.estimated_complexity == 1.0:
            self.estimated_complexity = self._calculate_complexity()

    def _calculate_complexity(self) -> float:
        """Calculate the estimated complexity of this query."""
        complexity = 1.0

        # Predicates increase complexity
        if self.predicates:
            complexity += 0.2 * len(self.predicates)

        # Group by operations significantly increase complexity
        if self.group_by:
            complexity += 1.0 * len(self.group_by)

        # Aggregations increase complexity
        if self.aggregations:
            complexity += 0.5 * len(self.aggregations)

        # Ordering increases complexity slightly
        if self.order_by:
            complexity += 0.1 * len(self.order_by)

        return complexity

    def build_arrow_expression(self) -> Optional[pc.Expression]:
        """Build a PyArrow filter expression from predicates."""
        if not self.predicates:
            return None

        # Start with the first predicate
        expression = self.predicates[0].to_arrow_expression()

        # Combine all predicates with AND
        for predicate in self.predicates[1:]:
            expression = pc.and_(expression, predicate.to_arrow_expression())

        return expression

    def get_query_type(self) -> QueryType:
        """Determine the type of this query based on its characteristics."""
        # Check for simple point lookup (single CID equality)
        if (self.predicates and len(self.predicates) == 1 and
                self.predicates[0].column == "cid" and self.predicates[0].op == "=="):
            return QueryType.SIMPLE_LOOKUP

        # Check for aggregations with group by
        if self.aggregations and self.group_by:
            return QueryType.GROUP_BY

        # Check for aggregations without group by
        if self.aggregations and not self.group_by:
            return QueryType.AGGREGATE

        # Check for complex analytical query
        if ((self.predicates and len(self.predicates) > 3) or
                (self.aggregations and len(self.aggregations) > 2) or
                (self.group_by and len(self.group_by) > 1)):
            return QueryType.COMPLEX_ANALYTICAL

        # Default to range scan
        return QueryType.RANGE_SCAN


class QueryExecutionStatistics:
    """Collects and reports statistics about query execution."""

    def __init__(self):
        """Initialize query statistics collection."""
        self.query_count = 0
        self.total_execution_time = 0.0
        self.query_times = {}  # query_id -> execution time
        self.query_rows_processed = {}  # query_id -> rows processed
        self.thread_utilization = {}  # query_id -> thread count
        self.query_types = {}  # query_id -> query type

    def record_query_start(self, query_id: str, query_type: QueryType):
        """Record the start of a query execution."""
        self.query_count += 1
        self.query_types[query_id] = query_type
        return time.time()

    def record_query_end(self, query_id: str, start_time: float, rows_processed: int, threads_used: int):
        """Record the end of a query execution."""
        end_time = time.time()
        execution_time = end_time - start_time

        self.query_times[query_id] = execution_time
        self.total_execution_time += execution_time
        self.query_rows_processed[query_id] = rows_processed
        self.thread_utilization[query_id] = threads_used

    def get_avg_execution_time(self) -> float:
        """Get the average execution time across all queries."""
        if self.query_count == 0:
            return 0.0
        return self.total_execution_time / self.query_count

    def get_query_statistics(self, query_id: str) -> Dict[str, Any]:
        """Get statistics for a specific query."""
        if query_id not in self.query_times:
            return {}

        return {
            "execution_time": self.query_times.get(query_id, 0.0),
            "rows_processed": self.query_rows_processed.get(query_id, 0),
            "threads_used": self.thread_utilization.get(query_id, 0),
            "query_type": self.query_types.get(query_id, "unknown").value,
            "throughput": self.query_rows_processed.get(query_id, 0) /
                          max(0.001, self.query_times.get(query_id, 0.001))  # rows/second
        }

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics for all queries."""
        if self.query_count == 0:
            return {"query_count": 0}

        # Count queries by type
        type_counts = {}
        for query_type in self.query_types.values():
            type_name = query_type.value
            if type_name not in type_counts:
                type_counts[type_name] = 0
            type_counts[type_name] += 1

        # Calculate aggregate statistics
        total_rows = sum(self.query_rows_processed.values())
        total_threads = sum(self.thread_utilization.values())

        return {
            "query_count": self.query_count,
            "total_execution_time": self.total_execution_time,
            "avg_execution_time": self.get_avg_execution_time(),
            "total_rows_processed": total_rows,
            "avg_rows_per_query": total_rows / self.query_count if self.query_count > 0 else 0,
            "avg_threads_per_query": total_threads / self.query_count if self.query_count > 0 else 0,
            "query_types": type_counts,
            "throughput": total_rows / max(0.001, self.total_execution_time)  # rows/second
        }


class PartitionExecutor:
    """Handles the execution of a query against a single partition."""

    def __init__(self, partition_path: str):
        """Initialize with a partition path."""
        self.partition_path = partition_path

    def execute(self, query: Query) -> pa.Table:
        """Execute the query on this partition.

        Args:
            query: The query to execute

        Returns:
            PyArrow table with query results
        """
        try:
            # Check if partition exists
            if not os.path.exists(self.partition_path):
                logger.warning(f"Partition not found: {self.partition_path}")
                return pa.Table.from_arrays([], schema=pa.schema([]))

            # Create dataset from partition
            ds = dataset(self.partition_path, format="parquet")

            # Build filter expression
            filter_expr = query.build_arrow_expression()

            # Execute the query
            result = ds.to_table(
                columns=query.projection,
                filter=filter_expr
            )

            # Apply aggregations if specified
            if query.aggregations and not query.group_by:
                # Without group by, we compute aggregate values directly
                agg_results = {}
                for agg in query.aggregations:
                    agg_results[agg.get_alias()] = agg.compute(result).as_py()

                # Convert to a single-row table
                agg_arrays = []
                agg_fields = []
                for alias, value in agg_results.items():
                    agg_arrays.append(pa.array([value]))
                    agg_fields.append(pa.field(alias, pa.from_numpy_dtype(type(value))))

                result = pa.Table.from_arrays(agg_arrays, schema=pa.schema(agg_fields))

            # Apply group by and aggregations if specified
            elif query.aggregations and query.group_by:
                # This is more complex and requires more operations
                # First, we need to group the data
                result = self._apply_group_by_aggregations(result, query)

            # Apply sorting if specified
            if query.order_by:
                sort_keys = [(col, order == "desc") for col, order in query.order_by]
                indices = pc.sort_indices(result, sort_keys=sort_keys)
                result = result.take(indices)

            # Apply limit if specified
            if query.limit and query.limit < result.num_rows:
                result = result.slice(0, query.limit)

            return result

        except Exception as e:
            logger.error(f"Error executing query on partition {self.partition_path}: {str(e)}")
            # Return empty table with appropriate schema
            if query.projection:
                fields = [pa.field(col, pa.string()) for col in query.projection]
                return pa.Table.from_arrays([], schema=pa.schema(fields))
            else:
                return pa.Table.from_arrays([], schema=pa.schema([]))

    def _apply_group_by_aggregations(self, table: pa.Table, query: Query) -> pa.Table:
        """Apply group by and aggregations to a table.

        This is a simplified implementation. For a full implementation, consider
        using a more sophisticated approach with PyArrow compute functions.

        Args:
            table: Input table
            query: Query with group by and aggregations

        Returns:
            Table with group by and aggregations applied
        """
        # Check if table is empty
        if table.num_rows == 0:
            # Return empty table with appropriate schema
            fields = []

            # Add group by columns
            for col in query.group_by:
                fields.append(pa.field(col, pa.string()))

            # Add aggregation columns
            for agg in query.aggregations:
                fields.append(pa.field(agg.get_alias(), pa.float64()))

            return pa.Table.from_arrays([], schema=pa.schema(fields))

        # Convert to pandas for easier group by operations
        # For very large datasets, this could be inefficient
        import pandas as pd
        df = table.to_pandas()

        # Apply group by and aggregations
        agg_dict = {}
        for agg in query.aggregations:
            if agg.operation == "count" and agg.column == "*":
                # Special case for count(*)
                agg_dict[agg.get_alias()] = "size"
            else:
                agg_dict[agg.column] = {agg.get_alias(): agg.operation}

        # Group by and aggregate
        grouped = df.groupby(query.group_by).agg(agg_dict)

        # Reset index to make group by columns regular columns
        result_df = grouped.reset_index()

        # Convert back to PyArrow Table
        return pa.Table.from_pandas(result_df)


class QueryPlanner:
    """Plans and optimizes query execution across partitions."""

    def __init__(self, max_threads: int = None):
        """Initialize the query planner.

        Args:
            max_threads: Maximum number of threads to use (defaults to CPU count)
        """
        if max_threads is None:
            import multiprocessing
            max_threads = max(1, multiprocessing.cpu_count())

        self.max_threads = max_threads
        self.statistics = QueryExecutionStatistics()

    def plan_query(self, query: Query, partition_paths: List[str]) -> Dict[str, Any]:
        """Plan how to execute a query across partitions.

        Args:
            query: The query to execute
            partition_paths: List of partition paths to query

        Returns:
            Dictionary with query plan details
        """
        # Determine query type
        query_type = query.get_query_type()

        # Determine execution strategy
        if query_type == QueryType.SIMPLE_LOOKUP:
            strategy = "lookup"
        elif query_type in (QueryType.AGGREGATE, QueryType.GROUP_BY, QueryType.COMPLEX_ANALYTICAL):
            strategy = "parallel"
        else:
            strategy = "partition_scan"

        # Determine how many threads to use based on query complexity and available partitions
        if strategy == "lookup":
            # For lookups, we use few threads - often just 1
            # However, if we need to check many partitions, we'll use more
            threads_to_use = min(
                self.max_threads,
                max(1, min(4, len(partition_paths)))
            )
        elif strategy == "parallel":
            # For complex queries, scale threads with complexity and partitions
            complexity_factor = min(1.0, query.estimated_complexity / 5.0)

            threads_to_use = min(
                self.max_threads,
                max(1, int(self.max_threads * complexity_factor)),
                len(partition_paths)  # No need for more threads than partitions
            )
        else:  # partition_scan
            # Use threads based on the number of partitions but cap at a reasonable number
            threads_to_use = min(
                self.max_threads,
                max(1, min(self.max_threads // 2, len(partition_paths)))
            )

        # Create the query plan
        plan = {
            "query_id": query.query_id,
            "query_type": query_type.value,
            "execution_strategy": strategy,
            "threads_to_use": threads_to_use,
            "partitions_to_query": len(partition_paths),
            "estimated_complexity": query.estimated_complexity
        }

        return plan

    def execute_query(self, query: Query, partition_paths: List[str]) -> Dict[str, Any]:
        """Execute a query across multiple partitions.

        Args:
            query: The query to execute
            partition_paths: List of partition paths to query

        Returns:
            Dictionary with query results and execution statistics
        """
        # Plan the query
        plan = self.plan_query(query, partition_paths)
        threads_to_use = plan["threads_to_use"]

        # Record query start
        start_time = self.statistics.record_query_start(
            query.query_id,
            query.get_query_type()
        )

        # Prepare partition executors
        executors = [PartitionExecutor(path) for path in partition_paths]

        # Execute the query based on the strategy
        execution_strategy = plan["execution_strategy"]

        if execution_strategy == "lookup" and len(partition_paths) == 1:
            # For single-partition lookups, just execute directly
            result_table = executors[0].execute(query)
            rows_processed = result_table.num_rows

        elif execution_strategy == "lookup":
            # For lookups across multiple partitions, search in parallel until found
            result_table, rows_processed = self._execute_lookup(
                query, executors, threads_to_use
            )

        else:  # "parallel" or "partition_scan"
            # For parallel execution, query all partitions in parallel
            result_table, rows_processed = self._execute_parallel(
                query, executors, threads_to_use
            )

        # Record query end
        self.statistics.record_query_end(
            query.query_id,
            start_time,
            rows_processed,
            threads_to_use
        )

        # Get query statistics
        query_stats = self.statistics.get_query_statistics(query.query_id)

        # Convert table to pandas for easier processing if requested
        result_format = "arrow"  # Default to arrow
        result_data = result_table

        # Return final results with statistics
        return {
            "query_id": query.query_id,
            "execution_time": query_stats["execution_time"],
            "rows_processed": rows_processed,
            "threads_used": threads_to_use,
            "results": result_data,
            "statistics": query_stats,
            "result_format": result_format
        }

    def _execute_lookup(self, query: Query, executors: List[PartitionExecutor],
                        threads_to_use: int) -> Tuple[pa.Table, int]:
        """Execute a lookup query, stopping when the target is found.

        Args:
            query: The query to execute
            executors: List of partition executors
            threads_to_use: Number of threads to use

        Returns:
            Tuple of (result table, rows processed)
        """
        # For lookup queries, we can stop once we find a match
        result_queue = queue.Queue()
        rows_processed = 0

        def process_partition(executor):
            """Process a single partition and add results to queue."""
            nonlocal rows_processed

            result = executor.execute(query)
            rows_processed += result.num_rows

            if result.num_rows > 0:
                result_queue.put(result)
                return True  # Found a match
            return False  # No match

        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads_to_use) as executor:
            # Submit tasks
            futures = [executor.submit(process_partition, exec) for exec in executors]

            # Wait for the first match or all to complete
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    # Found a match, cancel remaining tasks
                    for f in futures:
                        f.cancel()
                    break

        # Get the result from the queue if available
        if not result_queue.empty():
            result_table = result_queue.get()
        else:
            # No results found, return empty table with appropriate schema
            if query.projection:
                fields = [pa.field(col, pa.string()) for col in query.projection]
                result_table = pa.Table.from_arrays([], schema=pa.schema(fields))
            else:
                result_table = pa.Table.from_arrays([], schema=pa.schema([]))

        return result_table, rows_processed

    def _execute_parallel(self, query: Query, executors: List[PartitionExecutor],
                         threads_to_use: int) -> Tuple[pa.Table, int]:
        """Execute a query in parallel across all partitions.

        Args:
            query: The query to execute
            executors: List of partition executors
            threads_to_use: Number of threads to use

        Returns:
            Tuple of (result table, rows processed)
        """
        # For parallel queries, we process all partitions
        result_tables = []
        rows_processed = 0

        def process_partition(executor):
            """Process a single partition and return results."""
            nonlocal rows_processed

            result = executor.execute(query)
            rows_processed += result.num_rows
            return result

        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads_to_use) as executor:
            # Submit tasks
            futures = [executor.submit(process_partition, exec) for exec in executors]

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result.num_rows > 0:
                    result_tables.append(result)

        # Combine results based on query type
        if query.get_query_type() in (QueryType.AGGREGATE, QueryType.GROUP_BY):
            # For aggregations, we need to combine the partial results
            combined_table = self._combine_aggregations(result_tables, query)
        else:
            # For other queries, we can just concatenate the results
            if result_tables:
                combined_table = pa.concat_tables(result_tables)

                # Apply global sorting if needed
                if query.order_by:
                    sort_keys = [(col, order == "desc") for col, order in query.order_by]
                    indices = pc.sort_indices(combined_table, sort_keys=sort_keys)
                    combined_table = combined_table.take(indices)

                # Apply global limit if needed
                if query.limit and query.limit < combined_table.num_rows:
                    combined_table = combined_table.slice(0, query.limit)
            else:
                # No results, return empty table with appropriate schema
                if query.projection:
                    fields = [pa.field(col, pa.string()) for col in query.projection]
                    combined_table = pa.Table.from_arrays([], schema=pa.schema(fields))
                else:
                    combined_table = pa.Table.from_arrays([], schema=pa.schema([]))

        return combined_table, rows_processed

    def _combine_aggregations(self, result_tables: List[pa.Table], query: Query) -> pa.Table:
        """Combine aggregation results from multiple partitions.

        Args:
            result_tables: List of tables with partial aggregation results
            query: The original query

        Returns:
            Combined table with final aggregation results
        """
        if not result_tables:
            # Return empty table with appropriate schema
            fields = []

            # Add group by columns if present
            if query.group_by:
                for col in query.group_by:
                    fields.append(pa.field(col, pa.string()))

            # Add aggregation columns
            for agg in query.aggregations:
                fields.append(pa.field(agg.get_alias(), pa.float64()))

            return pa.Table.from_arrays([], schema=pa.schema(fields))

        # Handle different aggregation types differently
        if query.group_by:
            # For group by queries, we need to combine by group
            return self._combine_group_by_aggregations(result_tables, query)
        else:
            # For simple aggregations without group by, combine the partial results
            return self._combine_simple_aggregations(result_tables, query)

    def _combine_simple_aggregations(self, result_tables: List[pa.Table], query: Query) -> pa.Table:
        """Combine simple aggregation results (without group by).

        Args:
            result_tables: List of tables with partial aggregation results
            query: The original query

        Returns:
            Combined table with final aggregation results
        """
        # Each table should have one row with aggregation results
        combined_results = {}

        for agg in query.aggregations:
            alias = agg.get_alias()

            # Initialize result based on aggregation type
            if agg.operation in ("sum", "count", "count_distinct"):
                # These can be summed across partitions
                combined_value = 0

                for table in result_tables:
                    if alias in table.column_names:
                        combined_value += table[alias][0].as_py()

            elif agg.operation == "min":
                # Take the minimum value across partitions
                values = [table[alias][0].as_py() for table in result_tables
                          if alias in table.column_names]
                combined_value = min(values) if values else None

            elif agg.operation == "max":
                # Take the maximum value across partitions
                values = [table[alias][0].as_py() for table in result_tables
                          if alias in table.column_names]
                combined_value = max(values) if values else None

            elif agg.operation == "mean":
                # Calculate weighted mean based on count
                total_sum = 0
                total_count = 0

                for table in result_tables:
                    if alias in table.column_names:
                        # We need the count for weighted average
                        # Assuming each partition also has a count aggregation
                        count_alias = f"count_{agg.column}"
                        if count_alias in table.column_names:
                            count = table[count_alias][0].as_py()
                        else:
                            # Fall back to assuming each partition has same count
                            count = 1

                        value = table[alias][0].as_py()
                        total_sum += value * count
                        total_count += count

                combined_value = total_sum / total_count if total_count > 0 else None

            else:
                # For other aggregation types, just take the first value for now
                # This is not correct for all types but serves as a placeholder
                combined_value = result_tables[0][alias][0].as_py() if result_tables else None

            combined_results[alias] = combined_value

        # Convert to a single-row table
        agg_arrays = []
        agg_fields = []
        for alias, value in combined_results.items():
            agg_arrays.append(pa.array([value]))
            agg_fields.append(pa.field(alias, pa.from_numpy_dtype(type(value))))

        return pa.Table.from_arrays(agg_arrays, schema=pa.schema(agg_fields))

    def _combine_group_by_aggregations(self, result_tables: List[pa.Table], query: Query) -> pa.Table:
        """Combine group by aggregation results.

        Args:
            result_tables: List of tables with partial aggregation results
            query: The original query

        Returns:
            Combined table with final aggregation results
        """
        # Convert to pandas for easier group by operations
        import pandas as pd
        combined_df = pd.concat([table.to_pandas() for table in result_tables])

        # Re-apply the group by operation to combine results
        agg_dict = {}
        for agg in query.aggregations:
            alias = agg.get_alias()

            if agg.operation in ("sum", "count"):
                agg_dict[alias] = "sum"
            elif agg.operation == "min":
                agg_dict[alias] = "min"
            elif agg.operation == "max":
                agg_dict[alias] = "max"
            elif agg.operation == "mean":
                # Need to recalculate mean from original data
                # This is not correct but we'll use mean as a placeholder
                agg_dict[alias] = "mean"
            else:
                # For other aggregation types, just use first
                agg_dict[alias] = "first"

        # Group by and aggregate
        result_df = combined_df.groupby(query.group_by).agg(agg_dict).reset_index()

        # Convert back to PyArrow Table
        return pa.Table.from_pandas(result_df)


class ParallelQueryManager:
    """High-level manager for parallel query execution."""

    def __init__(self,
                 max_threads: int = None,
                 work_dir: str = None):
        """Initialize the parallel query manager.

        Args:
            max_threads: Maximum number of threads to use (None = CPU count)
            work_dir: Working directory for temporary files
        """
        # Set default max threads if not provided
        if max_threads is None:
            import multiprocessing
            max_threads = max(1, multiprocessing.cpu_count())

        self.max_threads = max_threads
        self.work_dir = work_dir or os.path.expanduser("~/.ipfs_kit/query_cache")
        os.makedirs(self.work_dir, exist_ok=True)

        # Initialize query planner
        self.query_planner = QueryPlanner(max_threads=max_threads)

        # Initialize query cache
        self.query_cache = {}

        # Initialize statistics
        self.statistics = self.query_planner.statistics

    def execute_query(self,
                     query: Union[Query, Dict[str, Any]],
                     partition_paths: List[str],
                     use_cache: bool = True) -> Dict[str, Any]:
        """Execute a query across multiple partitions.

        Args:
            query: Either a Query object or a dictionary representation
            partition_paths: List of partition paths to query
            use_cache: Whether to use query caching

        Returns:
            Dictionary with query results and execution statistics
        """
        # Convert dict to Query object if needed
        if isinstance(query, dict):
            query = self._dict_to_query(query)

        # Check cache if enabled
        cache_key = self._get_cache_key(query, partition_paths)
        if use_cache and cache_key in self.query_cache:
            cached_result = self.query_cache[cache_key]

            # Add a note that this is a cached result
            cached_result["cached"] = True
            return cached_result

        # Execute the query
        result = self.query_planner.execute_query(query, partition_paths)

        # Cache the result if enabled
        if use_cache:
            self.query_cache[cache_key] = result.copy()

        return result

    def _dict_to_query(self, query_dict: Dict[str, Any]) -> Query:
        """Convert a dictionary to a Query object.

        Args:
            query_dict: Dictionary representation of a query

        Returns:
            Query object
        """
        # Convert predicates
        predicates = None
        if "predicates" in query_dict:
            predicates = []
            for pred_dict in query_dict["predicates"]:
                predicates.append(QueryPredicate(
                    column=pred_dict["column"],
                    op=pred_dict["op"],
                    value=pred_dict["value"]
                ))

        # Convert aggregations
        aggregations = None
        if "aggregations" in query_dict:
            aggregations = []
            for agg_dict in query_dict["aggregations"]:
                aggregations.append(QueryAggregation(
                    column=agg_dict["column"],
                    operation=agg_dict["operation"],
                    alias=agg_dict.get("alias")
                ))

        # Create the Query object
        return Query(
            predicates=predicates,
            projection=query_dict.get("projection"),
            aggregations=aggregations,
            group_by=query_dict.get("group_by"),
            order_by=query_dict.get("order_by"),
            limit=query_dict.get("limit"),
            query_id=query_dict.get("query_id"),
            estimated_complexity=query_dict.get("estimated_complexity", 1.0)
        )

    def _get_cache_key(self, query: Query, partition_paths: List[str]) -> str:
        """Generate a cache key for a query.

        Args:
            query: The query to execute
            partition_paths: List of partition paths to query

        Returns:
            Cache key as string
        """
        # Convert query to a JSON-serializable dictionary
        query_dict = {
            "predicates": [{"column": p.column, "op": p.op, "value": str(p.value)}
                          for p in (query.predicates or [])],
            "projection": query.projection,
            "aggregations": [{"column": a.column, "operation": a.operation, "alias": a.alias}
                            for a in (query.aggregations or [])],
            "group_by": query.group_by,
            "order_by": query.order_by,
            "limit": query.limit
        }

        # Hash the query dictionary and partition paths
        import hashlib
        key_string = json.dumps(query_dict) + ":" + json.dumps(sorted(partition_paths))
        return hashlib.md5(key_string.encode()).hexdigest()

    def create_query(self,
                    predicates: List[Dict[str, Any]] = None,
                    projection: List[str] = None,
                    aggregations: List[Dict[str, Any]] = None,
                    group_by: List[str] = None,
                    order_by: List[Tuple[str, str]] = None,
                    limit: int = None) -> Query:
        """Create a Query object from parameters.

        This is a convenience method for creating a Query object without
        directly instantiating the Query class.

        Args:
            predicates: List of predicate dictionaries with column, op, and value
            projection: List of columns to return
            aggregations: List of aggregation dictionaries with column, operation, and alias
            group_by: List of columns to group by
            order_by: List of (column, direction) tuples for sorting
            limit: Maximum number of rows to return

        Returns:
            Query object
        """
        # Convert predicates
        query_predicates = None
        if predicates:
            query_predicates = []
            for pred_dict in predicates:
                query_predicates.append(QueryPredicate(
                    column=pred_dict["column"],
                    op=pred_dict["op"],
                    value=pred_dict["value"]
                ))

        # Convert aggregations
        query_aggregations = None
        if aggregations:
            query_aggregations = []
            for agg_dict in aggregations:
                query_aggregations.append(QueryAggregation(
                    column=agg_dict["column"],
                    operation=agg_dict["operation"],
                    alias=agg_dict.get("alias")
                ))

        # Create the Query object
        return Query(
            predicates=query_predicates,
            projection=projection,
            aggregations=query_aggregations,
            group_by=group_by,
            order_by=order_by,
            limit=limit
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get query execution statistics.

        Returns:
            Dictionary with query execution statistics
        """
        return self.statistics.get_summary_statistics()

    def clear_cache(self):
        """Clear the query cache."""
        self.query_cache = {}


class ThreadPoolManager:
    """Manages thread pools for query execution."""

    def __init__(self,
                 min_threads: int = 2,
                 max_threads: int = None,
                 thread_ttl: float = 60.0):
        """Initialize the thread pool manager.

        Args:
            min_threads: Minimum number of threads in the pool
            max_threads: Maximum number of threads (None = CPU count)
            thread_ttl: Time to live for idle threads (seconds)
        """
        # Set default max threads if not provided
        if max_threads is None:
            import multiprocessing
            max_threads = max(1, multiprocessing.cpu_count())

        self.min_threads = min_threads
        self.max_threads = max_threads
        self.thread_ttl = thread_ttl

        # Thread pool for each priority level
        self.pools = {}

        # Initialize thread pools
        self._init_pools()

    def _init_pools(self):
        """Initialize thread pools for each priority level."""
        # Create pools for different priority levels
        self.pools["high"] = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_threads,
            thread_name_prefix="high_priority"
        )

        self.pools["medium"] = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(self.min_threads, self.max_threads // 2),
            thread_name_prefix="medium_priority"
        )

        self.pools["low"] = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.min_threads,
            thread_name_prefix="low_priority"
        )

    def get_pool(self, priority: str = "medium") -> concurrent.futures.ThreadPoolExecutor:
        """Get the thread pool for a specific priority level.

        Args:
            priority: Thread pool priority ("high", "medium", or "low")

        Returns:
            ThreadPoolExecutor for the specified priority
        """
        if priority not in self.pools:
            # Default to medium priority if invalid
            priority = "medium"

        return self.pools[priority]

    def submit(self, fn, *args, priority: str = "medium", **kwargs):
        """Submit a function to be executed in the thread pool.

        Args:
            fn: Function to execute
            *args: Positional arguments for the function
            priority: Thread pool priority ("high", "medium", or "low")
            **kwargs: Keyword arguments for the function

        Returns:
            Future object representing the execution of the function
        """
        pool = self.get_pool(priority)
        return pool.submit(fn, *args, **kwargs)

    def map(self, fn, iterable, priority: str = "medium", timeout=None, chunksize=1):
        """Map a function over an iterable using the thread pool.

        Args:
            fn: Function to apply to each element
            iterable: Iterable of items to process
            priority: Thread pool priority ("high", "medium", or "low")
            timeout: Maximum time to wait for results (None = unlimited)
            chunksize: Number of items to process per task

        Returns:
            Iterator of results
        """
        pool = self.get_pool(priority)
        return pool.map(fn, iterable, timeout=timeout, chunksize=chunksize)

    def shutdown(self, wait: bool = True):
        """Shut down all thread pools.

        Args:
            wait: Whether to wait for threads to finish before shutting down
        """
        for pool in self.pools.values():
            pool.shutdown(wait=wait)


class QueryCacheManager:
    """Manages query result caching."""

    def __init__(self,
                 max_cache_size: int = 100,
                 cache_ttl: float = 300.0,
                 work_dir: str = None):
        """Initialize the query cache manager.

        Args:
            max_cache_size: Maximum number of queries to cache
            cache_ttl: Time to live for cached queries (seconds)
            work_dir: Working directory for temporary files
        """
        self.max_cache_size = max_cache_size
        self.cache_ttl = cache_ttl
        self.work_dir = work_dir or os.path.expanduser("~/.ipfs_kit/query_cache")
        os.makedirs(self.work_dir, exist_ok=True)

        # Initialize cache
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_hits = {}

        # Start cache expiration thread
        self._start_expiration_thread()

    def _start_expiration_thread(self):
        """Start a thread to expire old cache entries."""
        def expire_old_entries():
            while True:
                try:
                    current_time = time.time()
                    expired_keys = []

                    # Find expired entries
                    for key, timestamp in self.cache_timestamps.items():
                        if current_time - timestamp > self.cache_ttl:
                            expired_keys.append(key)

                    # Remove expired entries
                    for key in expired_keys:
                        del self.cache[key]
                        del self.cache_timestamps[key]
                        if key in self.cache_hits:
                            del self.cache_hits[key]

                    # Sleep for a while
                    time.sleep(60)  # Check every minute

                except Exception as e:
                    logger.error(f"Error in cache expiration thread: {str(e)}")
                    time.sleep(60)

        # Start the thread
        thread = threading.Thread(target=expire_old_entries, daemon=True)
        thread.start()

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if key in self.cache:
            # Update timestamp and hit count
            self.cache_timestamps[key] = time.time()
            self.cache_hits[key] = self.cache_hits.get(key, 0) + 1

            return self.cache[key]

        return None

    def put(self, key: str, value: Any):
        """Put a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        # Check if we need to evict an entry
        if len(self.cache) >= self.max_cache_size:
            self._evict_entry()

        # Add the new entry
        self.cache[key] = value
        self.cache_timestamps[key] = time.time()
        self.cache_hits[key] = 0

    def _evict_entry(self):
        """Evict an entry from the cache based on LRU and hit count."""
        if not self.cache:
            return

        # Sort by (hit count / age) to prioritize frequently used entries
        current_time = time.time()
        scores = {}

        for key in self.cache.keys():
            age = current_time - self.cache_timestamps[key]
            hits = self.cache_hits.get(key, 0)

            # Score formula: higher hit count and newer entries have higher scores
            if age > 0:
                scores[key] = (hits + 1) / age
            else:
                scores[key] = hits + 1

        # Evict the entry with the lowest score
        evict_key = min(scores.keys(), key=lambda k: scores[k])

        del self.cache[evict_key]
        del self.cache_timestamps[evict_key]
        if evict_key in self.cache_hits:
            del self.cache_hits[evict_key]

    def clear(self):
        """Clear the cache."""
        self.cache.clear()
        self.cache_timestamps.clear()
        self.cache_hits.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "size": len(self.cache),
            "max_size": self.max_cache_size,
            "ttl": self.cache_ttl,
            "hit_count": sum(self.cache_hits.values()),
            "oldest_entry_age": max([time.time() - t for t in self.cache_timestamps.values()], default=0),
            "newest_entry_age": min([time.time() - t for t in self.cache_timestamps.values()], default=0),
            "most_hit_count": max(self.cache_hits.values(), default=0)
        }

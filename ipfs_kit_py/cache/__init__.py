"""
Cache modules for IPFS Kit to improve performance and reduce redundant operations.

This package provides various caching mechanisms designed for different use cases:

1. Semantic Cache: For caching semantically similar search queries and results
2. Tiered Cache: For efficiently managing content across memory and disk
3. Content Cache: For caching IPFS content with CID-based retrieval
4. Batch Operations: For optimizing bulk operations with batching, coalescing, and deduplication
5. Zero-Copy Interface: For sharing data between processes without copying, using Arrow C Data Interface
6. Async Operations: For non-blocking cache operations with asyncio support and thread pool management
7. Intelligent Cache: For predictive cache management using machine learning and access pattern analysis
8. Read-Ahead Prefetching: For proactively loading content before it's explicitly requested
9. Compression and Encoding: For optimizing data storage with efficient compression and encoding strategies
10. Schema and Column Optimization: For workload-based schema optimization, column pruning, and indexing
11. Advanced Partitioning Strategies: For intelligent data distribution across multiple partitions
12. Parallel Query Execution: For multi-threaded query execution with query planning and optimization
13. Probabilistic Data Structures: For memory-efficient operations on large datasets with controllable error rates

These caching mechanisms can significantly improve performance, especially
for repeated operations or operations with similar patterns of access.
"""

from .semantic_cache import CacheEntry, QueryVector, SemanticCache
from .batch_operations import BatchOperationManager
from .zero_copy_interface import ZeroCopyManager, ZeroCopyTable
from .async_operations import AsyncOperationManager, AsyncParquetCIDCache, async_cache_get_or_create
from .intelligent_cache import (
    AccessPattern, 
    PredictiveModel, 
    IntelligentCacheManager, 
    IntelligentCacheStrategyProvider
)
from .read_ahead_prefetching import (
    AccessPattern as PrefetchAccessPattern,
    PrefetchStrategy,
    SequentialPrefetchStrategy,
    TemporalPrefetchStrategy,
    HybridPrefetchStrategy,
    ContentAwarePrefetchStrategy,
    ReadAheadPrefetchManager
)
from .compression_encoding import (
    CompressionProfile,
    EncodingOptimizer,
    ColumnAnalyzer,
    CompressionProfileSelector,
    ParquetCompressionManager,
    compression_profiles,
    parquet_compression
)

# Import schema and column optimization
try:
    from .schema_column_optimization import (
        WorkloadType,
        ColumnStatistics,
        SchemaProfiler,
        SchemaOptimizer,
        SchemaEvolutionManager,
        ParquetCIDCache,
        SchemaColumnOptimizationManager
    )
except ImportError:
    # Fallback when module not available
    WorkloadType = None
    ColumnStatistics = None
    SchemaProfiler = None
    SchemaOptimizer = None
    SchemaEvolutionManager = None
    ParquetCIDCache = None  # Mock implementation in schema_column_optimization.py
    SchemaColumnOptimizationManager = None

# Import advanced partitioning strategies
try:
    from .advanced_partitioning_strategies import (
        PartitioningStrategy,
        PartitionInfo,
        TimeBasedPartitionStrategy,
        SizeBasedPartitionStrategy,
        ContentTypePartitionStrategy,
        HashBasedPartitionStrategy,
        DynamicPartitionManager,
        AdvancedPartitionManager,
        # Aliases for backward compatibility
        TimePartitioning,
        SizePartitioning,
        ContentTypePartitioning,
        HashPartitioning
    )
except ImportError:
    # Fallback when module not available
    PartitioningStrategy = None
    PartitionInfo = None
    TimeBasedPartitionStrategy = None
    SizeBasedPartitionStrategy = None
    ContentTypePartitionStrategy = None
    HashBasedPartitionStrategy = None
    DynamicPartitionManager = None
    AdvancedPartitionManager = None
    TimePartitioning = None
    SizePartitioning = None
    ContentTypePartitioning = None
    HashPartitioning = None

# Import parallel query execution
try:
    from .parallel_query_execution import (
        ParallelQueryManager,
        Query,
        QueryType,
        QueryPredicate,
        QueryAggregation,
        QueryPlanner,
        PartitionExecutor,
        ThreadPoolManager,
        QueryCacheManager,
        QueryExecutionStatistics
    )
except ImportError:
    # Fallback when module not available
    ParallelQueryManager = None
    Query = None
    QueryType = None
    QueryPredicate = None
    QueryAggregation = None
    QueryPlanner = None
    PartitionExecutor = None
    ThreadPoolManager = None
    QueryCacheManager = None
    QueryExecutionStatistics = None

# Import probabilistic data structures
try:
    from .probabilistic_data_structures import (
        BloomFilter,
        HyperLogLog,
        CountMinSketch,
        CuckooFilter,
        MinHash,
        TopK,
        ProbabilisticDataStructureManager,
        HashFunction
    )
except ImportError:
    # Fallback when module not available
    BloomFilter = None
    HyperLogLog = None
    CountMinSketch = None
    CuckooFilter = None
    MinHash = None
    TopK = None
    ProbabilisticDataStructureManager = None
    HashFunction = None

__all__ = [
    'CacheEntry', 
    'QueryVector', 
    'SemanticCache', 
    'BatchOperationManager',
    'ZeroCopyManager',
    'ZeroCopyTable',
    'AsyncOperationManager',
    'AsyncParquetCIDCache',
    'async_cache_get_or_create',
    'AccessPattern',
    'PredictiveModel',
    'IntelligentCacheManager',
    'IntelligentCacheStrategyProvider',
    'PrefetchAccessPattern',
    'PrefetchStrategy',
    'SequentialPrefetchStrategy',
    'TemporalPrefetchStrategy',
    'HybridPrefetchStrategy',
    'ContentAwarePrefetchStrategy',
    'ReadAheadPrefetchManager',
    'CompressionProfile',
    'EncodingOptimizer',
    'ColumnAnalyzer',
    'CompressionProfileSelector',
    'ParquetCompressionManager',
    'compression_profiles',
    'parquet_compression',
    # Schema and column optimization
    'WorkloadType',
    'ColumnStatistics',
    'SchemaProfiler',
    'SchemaOptimizer',
    'SchemaEvolutionManager',
    'ParquetCIDCache',
    'SchemaColumnOptimizationManager',
    # Advanced partitioning strategies
    'PartitioningStrategy',
    'PartitionInfo',
    'TimeBasedPartitionStrategy',
    'SizeBasedPartitionStrategy',
    'ContentTypePartitionStrategy',
    'HashBasedPartitionStrategy',
    'DynamicPartitionManager',
    'AdvancedPartitionManager',
    'TimePartitioning',
    'SizePartitioning',
    'ContentTypePartitioning',
    'HashPartitioning',
    # Parallel query execution
    'ParallelQueryManager',
    'Query',
    'QueryType',
    'QueryPredicate',
    'QueryAggregation',
    'QueryPlanner',
    'PartitionExecutor',
    'ThreadPoolManager',
    'QueryCacheManager',
    'QueryExecutionStatistics',
    # Probabilistic data structures
    'BloomFilter',
    'HyperLogLog',
    'CountMinSketch',
    'CuckooFilter',
    'MinHash',
    'TopK',
    'ProbabilisticDataStructureManager',
    'HashFunction'
]

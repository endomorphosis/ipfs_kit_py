"""
Tiered Cache System for IPFS - Backward Compatibility Module.

This module provides backward compatibility for the tiered caching system 
which has been split into separate files. It re-exports the core classes
from their new locations.
"""

import logging
import warnings

# Import classes from their new locations
from .arc_cache import ARCache
from .disk_cache import DiskCache
from .tiered_cache_manager import TieredCacheManager

# Import probabilistic data structures from the new location
try:
    from .cache.probabilistic_data_structures import (
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

# Import advanced partitioning strategies
try:
    from .cache.advanced_partitioning_strategies import (
        PartitioningStrategy,
        PartitionInfo,
        TimeBasedPartitionStrategy,
        SizeBasedPartitionStrategy,
        ContentTypePartitionStrategy,
        HashBasedPartitionStrategy,
        DynamicPartitionManager,
        AdvancedPartitionManager
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

# Import schema column optimization
try:
    from .cache.schema_column_optimization import (
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
    ParquetCIDCache = None
    SchemaColumnOptimizationManager = None

# Setup logging
logger = logging.getLogger(__name__)

# Show deprecation warning
warnings.warn(
    "The tiered_cache module has been split into separate files. "
    "Please update your imports to use the new locations: "
    "arc_cache.py, disk_cache.py, tiered_cache_manager.py, "
    "and the cache/ directory for specialized components.",
    DeprecationWarning,
    stacklevel=2
)

# List all exported symbols
__all__ = [
    'ARCache',
    'DiskCache',
    'TieredCacheManager',
    # Probabilistic data structures
    'BloomFilter',
    'HyperLogLog',
    'CountMinSketch',
    'CuckooFilter',
    'MinHash',
    'TopK',
    'ProbabilisticDataStructureManager',
    'HashFunction',
    # Advanced partitioning
    'PartitioningStrategy',
    'PartitionInfo',
    'TimeBasedPartitionStrategy',
    'SizeBasedPartitionStrategy',
    'ContentTypePartitionStrategy',
    'HashBasedPartitionStrategy',
    'DynamicPartitionManager',
    'AdvancedPartitionManager',
    # Schema optimization
    'WorkloadType',
    'ColumnStatistics',
    'SchemaProfiler',
    'SchemaOptimizer',
    'SchemaEvolutionManager',
    'ParquetCIDCache',
    'SchemaColumnOptimizationManager'
]
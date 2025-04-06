# Changelog

All notable changes to the `ipfs_kit_py` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- WebRTC streaming for media content from IPFS
- Real-time WebSocket notification system
- Integration between WebRTC and notification systems
- Unified dashboard example with WebRTC streaming and notifications
- Comprehensive documentation for streaming capabilities
- New notification types for WebRTC events
- WebRTC performance benchmarking system:
  - Added `WebRTCBenchmark` class for detailed performance analysis
  - Added benchmarking for connection establishment, network conditions, and media quality
  - Added network performance metrics (RTT, jitter, packet loss, bandwidth)
  - Added media quality metrics (resolution, frame rate, bitrate, quality score)
  - Added frame-level timing for end-to-end latency analysis
  - Added comprehensive report generation in JSON format
  - Added regression testing capabilities for comparing benchmark results
  - Added integration with WebRTCStreamingManager via WebRTCStreamingManagerBenchmarkIntegration
  - Added visualization support for benchmark results
  - Added example in `examples/webrtc_benchmark_example.py`
  - Added unit tests in `test/test_webrtc_benchmark.py`
  - Added CI/CD integration for automated benchmarking
  - Added baseline performance tracking and regression detection
  - Added configurable threshold system for performance validation
  - Added GitHub Actions workflow in `.github/workflows/webrtc_benchmark.yml`
  - Added benchmark command-line tool in `bin/webrtc_benchmark_ci.py`
- Schema and Column Optimization for ParquetCIDCache:
  - Added `SchemaProfiler` for analyzing column usage and workload type detection
  - Added `SchemaOptimizer` for creating optimized schemas with column pruning
  - Added `SchemaEvolutionManager` for backwards compatibility with schema versioning
  - Added specialized indexes for frequently queried columns (B-tree, hash, bloom filter)
  - Added column-level statistics collection for optimization decisions
  - Added workload type detection (READ_HEAVY, WRITE_HEAVY, ANALYTICAL, etc.)
  - Added automated optimization via `SchemaColumnOptimizationManager`
  - Added comprehensive example in `examples/schema_column_optimization_example.py`
- Advanced Partitioning Strategies for ParquetCIDCache:
  - Added `TimeBasedPartitionStrategy` for temporal access patterns (hourly, daily, weekly, monthly, quarterly, yearly)
  - Added `SizeBasedPartitionStrategy` to balance partition sizes with automatic rotation
  - Added `ContentTypePartitionStrategy` for content-type specific workload optimization
  - Added `HashBasedPartitionStrategy` for even distribution of records across partitions
  - Added `DynamicPartitionManager` for intelligent strategy selection based on workload analysis
  - Added `AdvancedPartitionManager` high-level interface for unified partitioning management
  - Added comprehensive example in `examples/advanced_partitioning_example.py`
  - Added detailed performance benchmarking of different partitioning strategies
  - Added visualization capabilities for partition distribution and metrics
- Parallel Query Execution for efficient analytical operations:
  - Added `ParallelQueryManager` for multi-threaded query processing across partitions
  - Added `QueryType` enumeration for different query patterns (SIMPLE_LOOKUP, RANGE_SCAN, AGGREGATE, COMPLEX)
  - Added `QueryPredicate` for filter conditions with PyArrow expression conversion
  - Added `QueryAggregation` for computation operations (sum, avg, min, max, count, etc.)
  - Added `Query` class for representing complete queries with predicates, projections, and aggregations
  - Added `QueryPlanner` for optimization with predicate pushdown, projection pruning, and partition pruning
  - Added `PartitionExecutor` for efficient processing of individual partition files
  - Added intelligent thread allocation via `ThreadPoolManager` based on query complexity
  - Added `QueryCacheManager` for caching query results with intelligent invalidation
  - Added comprehensive example in `examples/parallel_query_execution_example.py`
  - Added benchmarking capabilities for comparing parallel vs sequential performance
  - Added visualization of query execution plans and thread utilization
- Probabilistic Data Structures for memory-efficient operations:
  - Added `BloomFilter` for space-efficient set membership testing with controllable false positive rates
  - Added `HyperLogLog` for cardinality estimation (counting unique elements) with minimal memory
  - Added `CountMinSketch` for frequency estimation of elements in a data stream with sublinear space
  - Added `CuckooFilter` for membership testing with deletion support, an improvement over Bloom filters
  - Added `MinHash` for quickly estimating Jaccard similarity between sets using hash-based sampling
  - Added `TopK` for tracking most frequent elements in a data stream using limited memory
  - Added `HashFunction` enumeration for selecting different hash algorithms
  - Added `ProbabilisticDataStructureManager` for creating and managing multiple probabilistic data structures
  - Added comprehensive example in `examples/probabilistic_data_structures_example.py`
  - Added performance comparisons with exact data structures
  - Added memory-accuracy tradeoff visualizations
  - Added IPFS use cases including content availability checking, unique peer tracking, and content similarity detection

### Improved
- Comprehensive documentation for all performance optimization components
- Added detailed documentation for Probabilistic Data Structures in `docs/probabilistic_data_structures.md`
- Updated documentation index to include Probabilistic Data Structures
- Enhanced examples README with detailed descriptions of performance optimization examples
- Completed all items in the Performance Optimization Roadmap
- Improved FSSpec integration in high_level_api.py with proper filesystem initialization and error handling

## [0.1.1] - 2025-04-03

### Added
- PyTorch integration in AI/ML module with comprehensive model management capabilities
- Support for PyTorch model saving and loading with IPFS
- TorchScript tracing and optimization
- PyTorch DataLoader integration with IPFS datasets
- Mixed precision inference optimization
- ONNX export functionality
- Unit tests for PyTorch integration

## [0.1.0] - 2025-04-02

### Added
- Comprehensive performance metrics system
- Benchmarking framework with command-line interface
- Performance visualization capabilities
- System resource monitoring integration
- Performance documentation and examples
- High-level API (`IPFSSimpleAPI`) for simplified interactions
- Role-based architecture (master/worker/leecher)
- Tiered storage system with Adaptive Replacement Cache (ARC)
- FSSpec integration for filesystem-like IPFS access
- Arrow-based metadata indexing
- Direct P2P communication via libp2p
- Cluster management capabilities
- IPLD-based knowledge graph
- AI/ML integration tools
- REST API server using FastAPI
- Command-line interface (CLI)
- Comprehensive testing framework
- Documentation for all major components

### Fixed
- PyArrow schema type mismatches in test suite
- FSSpec integration with proper AbstractFileSystem inheritance
- Class name collisions between components
- Test isolation for consistent results
- Parameter validation for robust error handling
- Performance bottlenecks in content retrieval
- Cache eviction strategies for optimal performance

### Changed
- Migrated to modern packaging with pyproject.toml
- Optimized cache performance with memory-mapped files
- Improved error reporting with standardized result dictionaries
- Enhanced cluster state synchronization with CRDT-based approach
- Reorganized API structure for improved discoverability

[Unreleased]: https://github.com/endomorphosis/ipfs_kit_py/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/endomorphosis/ipfs_kit_py/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/endomorphosis/ipfs_kit_py/releases/tag/v0.1.0
# IPFS Kit Benchmark Framework

This guide explains how to use the new benchmark framework to profile and optimize performance of the ipfs_kit_py library.

## Introduction

The `benchmark_framework.py` module provides a comprehensive solution for systematically analyzing performance across different operations, access patterns, and configurations. It complements the existing performance profiling tools by offering:

1. More detailed metrics collection and analysis
2. Sophisticated testing of cache efficiency with different access patterns
3. Comparison of high-level and low-level API overhead
4. Analysis of file size impact on performance
5. Intelligent optimization recommendations based on observed behavior

## Quick Start

To run all benchmark tests with the example script:

```bash
python examples/benchmark_framework_example.py
```

This will run a comprehensive set of benchmarks and produce both a console summary and a detailed JSON report with optimization recommendations.

## Benchmark Modes

The framework supports different benchmark modes for targeted analysis:

```bash
# Run a comprehensive benchmark of all operations
python examples/benchmark_framework_example.py --mode comprehensive

# Focus on a specific operation type
python examples/benchmark_framework_example.py --mode focused --focus add

# Analyze cache efficiency with different access patterns
python examples/benchmark_framework_example.py --mode cache

# Compare high-level and low-level API overhead
python examples/benchmark_framework_example.py --mode api

# Analyze how performance scales with file size
python examples/benchmark_framework_example.py --mode filesize
```

## Understanding Benchmark Results

### Performance Metrics

For each operation, the framework collects:

- **Mean execution time**: Average time in seconds
- **Standard deviation**: Variation in execution time
- **Min/max times**: Fastest and slowest iterations
- **Throughput**: Data transfer rate for applicable operations
- **System metrics**: CPU, memory, and I/O usage during benchmarks

### Cache Efficiency Analysis

The cache benchmarks analyze how different access patterns affect performance:

```
Cache Efficiency Comparison:
Sequential Access:
  Mean execution time: 0.0120s
  Cache hit rate: 5.00%

Random Access:
  Mean execution time: 0.0095s
  Cache hit rate: 60.00%

Repeated Access:
  Mean execution time: 0.0015s
  Cache hit rate: 95.00%
```

This example reveals that the cache is highly optimized for repeated access patterns but performs poorly with sequential access. Applications should structure their access patterns accordingly for optimal performance.

### API Overhead Analysis

The API benchmarks compare high-level (user-friendly) and low-level (performance-optimized) APIs:

```
API Overhead Analysis:
ADD operation:
  High-level API: 0.0520s
  Low-level API: 0.0480s
  Overhead: 8.33%
  ✅ Minimal overhead - high-level API is well-optimized for add operations.

GET operation:
  High-level API: 0.0950s
  Low-level API: 0.0450s
  Overhead: 111.11%
  ⚠️ High overhead detected! Consider using low-level API for get operations in performance-critical code.
```

This shows that while the high-level API is efficient for add operations, it introduces significant overhead for get operations. Performance-critical applications should consider using the low-level API directly for get operations.

### File Size Impact Analysis

The file size benchmarks show how performance scales with increasing file sizes:

```
File Size Impact Analysis:
File Size (KB) | Add Time (s) | Get Time (s) | Add Throughput (MB/s) | Get Throughput (MB/s)
-----------------------------------------------------------------------------------------
           1.0 |      0.0212 |      0.0190 |                 0.05 |                 0.05
          10.0 |      0.0523 |      0.0380 |                 0.19 |                 0.26
         100.0 |      0.1233 |      0.0620 |                 0.81 |                 1.61
        1000.0 |      0.3455 |      0.0950 |                 2.90 |                10.53
       10000.0 |      3.2123 |      0.2560 |                 3.11 |                39.06

Scaling Behavior:
File size increase factor: 10000.0x
Add time increase factor: 151.5x
Get time increase factor: 13.5x
Add operations scale superlinearly with file size - potential performance bottleneck for large files.
Get operations scale sublinearly with file size - good performance scaling!
```

This reveals that add operations don't scale as efficiently as get operations with increasing file sizes. The recommendation would be to optimize large file uploads, potentially by implementing chunking strategies.

## Customizing Benchmarks

### Using the BenchmarkSuite Class

You can create custom benchmarks by directly using the `BenchmarkSuite` class:

```python
from ipfs_kit_py.benchmark_framework import BenchmarkSuite

# Create a benchmark suite with custom parameters
benchmark_suite = BenchmarkSuite(
    output_dir="custom_results",
    file_sizes=[1024, 10*1024*1024],  # 1KB and 10MB
    iterations=10,
    cleanup=True,
    system_metrics=True
)

# Run specific benchmark types
add_results = benchmark_suite.run_add_benchmarks()
cache_results = benchmark_suite.run_cache_benchmarks()

# Or run all benchmarks
all_results = benchmark_suite.run_all()

# Process results
print(f"Add operation mean time: {add_results['high_level_add']['mean']:.4f}s")
print(f"Cache hit rate for repeated access: {cache_results['repeated_access']['cache_hit_rate']:.2%}")
```

### Creating Custom Benchmark Functions

You can also create entirely custom benchmark functions:

```python
from ipfs_kit_py.benchmark_framework import BenchmarkSuite, BenchmarkContext

def custom_operation_benchmark(kit, api, fs):
    """Custom benchmark for a specific operation sequence."""
    results = {}
    
    # Operation to benchmark
    def my_operation():
        # Add content
        content = b"test content" * 1000
        cid = kit.ipfs_add(content)["Hash"]
        
        # Process it in some way
        metadata = kit.ipfs_object_stat(cid)
        
        # Retrieve content
        retrieved = kit.ipfs_cat(cid)
        
        return len(retrieved)
    
    # Run the benchmark with the BenchmarkContext
    with BenchmarkContext() as ctx:
        for i in range(5):  # 5 iterations
            result = my_operation()
            ctx.record_iteration(result)
    
    # Store and return results
    results["my_custom_operation"] = ctx.get_stats()
    return results

# Use the custom benchmark
benchmark_suite = BenchmarkSuite()
results = benchmark_suite.run_custom_benchmark(custom_operation_benchmark)
```

## Comparison with existing performance_profiling.py

The new benchmark framework complements the existing `performance_profiling.py` tool:

| Feature | benchmark_framework.py | performance_profiling.py |
|---------|------------------------|--------------------------|
| Approach | Modular, class-based API with context managers | Script-based with function calls |
| Focus | Detailed analysis of specific performance aspects | General profiling and bottleneck identification |
| Output | Structured results with detailed metrics and optimization recommendations | Summary reports with key metrics |
| Cache Analysis | In-depth analysis of different access patterns | Basic cache hit/miss rates |
| File Size Impact | Comprehensive scaling analysis | Basic performance by file size |
| API Comparison | Detailed overhead analysis with recommendations | Basic timing comparison |
| System Metrics | Optional collection of CPU, memory, disk I/O | Not included |
| Customization | Highly extensible with custom benchmark functions | Limited to built-in tests |

## Best Practices

1. **Run benchmarks in a controlled environment**:
   - Minimize background processes
   - Ensure consistent hardware/software environment
   - Run multiple iterations for statistical significance

2. **Use appropriate file sizes**:
   - Match file sizes to your actual workload
   - Include both small and large files to test scaling
   - Test edge cases (very small and very large files)

3. **Test realistic access patterns**:
   - Consider your application's actual access patterns
   - Test worst-case scenarios
   - Benchmark critical code paths specifically

4. **Follow optimization recommendations**:
   - Implement recommendations one at a time
   - Re-run benchmarks after each change
   - Prioritize optimizations with highest impact

5. **Maintain performance baselines**:
   - Save benchmark results for comparison
   - Track performance changes over time
   - Set performance budgets for critical operations

## Conclusion

The benchmark framework provides a powerful tool for understanding and optimizing the performance of the ipfs_kit_py library. By systematically analyzing different aspects of performance and implementing the suggested optimizations, you can achieve significant performance improvements tailored to your specific workload patterns.

For additional performance information, see also the companion document [PERFORMANCE_PROFILING.md](PERFORMANCE_PROFILING.md).
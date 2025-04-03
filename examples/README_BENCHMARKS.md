# IPFS Kit Benchmarking Suite

This directory contains tools and examples for performance benchmarking and optimization of the ipfs_kit_py library.

## Available Benchmarking Tools

The project offers two complementary approaches to performance profiling:

1. **Performance Profiling** (`performance_profiling.py`): The original profiling tool that provides basic profiling capabilities and general optimization recommendations.

2. **Benchmark Framework** (`benchmark_framework.py` and `benchmark_framework_example.py`): A comprehensive benchmarking system with detailed metrics collection, sophisticated analysis, and targeted optimization recommendations.

## Quick Start Guide

### Running Basic Performance Profiling

For quick performance assessment:

```bash
python examples/performance_profiling.py
```

This will run a standard set of performance tests and generate a summary report.

### Running the Benchmark Framework

For detailed performance analysis:

```bash
python examples/benchmark_framework_example.py
```

This provides comprehensive metrics across different operations, access patterns, and file sizes.

### Focused Benchmarks

For targeted testing:

```bash
# Test cache efficiency
python examples/benchmark_framework_example.py --mode cache

# Analyze API overhead
python examples/benchmark_framework_example.py --mode api

# Test specific operations
python examples/benchmark_framework_example.py --mode focused --focus add

# Analyze file size impact
python examples/benchmark_framework_example.py --mode filesize
```

## Documentation

For detailed explanations and guides, refer to:

- [PERFORMANCE_PROFILING.md](PERFORMANCE_PROFILING.md): Guide for using the original performance profiling tools
- [BENCHMARK_FRAMEWORK.md](BENCHMARK_FRAMEWORK.md): Comprehensive guide for the new benchmark framework

## Recommended Performance Testing Workflow

1. **Initial Assessment**: Run the comprehensive benchmark to identify bottlenecks
   ```bash
   python examples/benchmark_framework_example.py
   ```

2. **Focused Analysis**: Run targeted benchmarks for problem areas
   ```bash
   python examples/benchmark_framework_example.py --mode focused --focus [problem_area]
   ```

3. **Implement Optimizations**: Based on the recommendations from the benchmark reports

4. **Verify Improvements**: Re-run benchmarks to confirm performance gains
   ```bash
   python examples/benchmark_framework_example.py
   ```

5. **Establish Baseline**: Save benchmark results as a baseline for future comparison

## Best Practices

- Run benchmarks in a controlled environment to get consistent results
- Use realistic data sizes and access patterns for your specific application
- Run multiple iterations (at least 5-10) for statistical significance
- Implement one optimization at a time and verify its impact
- Maintain a performance baseline to track changes over time

## Customizing Benchmarks

For advanced users who want to create custom benchmarks, refer to the examples in `benchmark_framework_example.py` and the detailed guide in [BENCHMARK_FRAMEWORK.md](BENCHMARK_FRAMEWORK.md).

## Questions and Issues

For questions or issues with benchmarking, please refer to the project's main documentation or open an issue on the project repository.
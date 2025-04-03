# Performance Metrics and Benchmarking Guide

This guide explains how to use the performance measurement capabilities in ipfs_kit_py to track, analyze, and optimize your IPFS operations.

## Table of Contents

1. [Overview](#overview)
2. [Performance Metrics API](#performance-metrics-api)
   - [Initialization](#initialization)
   - [Context Managers](#context-managers)
   - [Decorators](#decorators)
   - [Manual Tracking](#manual-tracking)
   - [Correlation Tracking](#correlation-tracking)
   - [Metrics Analysis](#metrics-analysis)
   - [Report Generation](#report-generation)
3. [Comprehensive Benchmarking](#comprehensive-benchmarking)
   - [Using the Benchmark Module](#using-the-benchmark-module)
   - [Command-line Interface](#command-line-interface)
   - [Custom Benchmarks](#custom-benchmarks)
4. [FSSpec Performance Analysis](#fsspec-performance-analysis)
   - [Enabling Metrics](#enabling-metrics)
   - [Access Patterns](#access-patterns)
   - [Cache Analysis](#cache-analysis)
5. [AI/ML Performance Visualization](#aiml-performance-visualization)
   - [Training Metrics Visualization](#training-metrics-visualization)
   - [Inference Performance Analysis](#inference-performance-analysis)
   - [Worker Utilization Visualization](#worker-utilization-visualization)
   - [Comprehensive Dashboards](#comprehensive-dashboards)
6. [Performance Optimization](#performance-optimization)
   - [Identifying Bottlenecks](#identifying-bottlenecks)
   - [Optimizing Caching](#optimizing-caching)
   - [Scaling with Parallelism](#scaling-with-parallelism)

## Overview

The ipfs_kit_py library includes comprehensive performance monitoring tools that help you:

- Track operation latency, bandwidth usage, and cache efficiency
- Measure system resource utilization (CPU, memory, disk, network)
- Calculate throughput and error rates
- Correlate related operations for tracing
- Generate detailed reports for analysis
- Benchmark different aspects of the system

These tools enable you to identify performance bottlenecks, optimize caching strategies, and ensure your IPFS applications are running efficiently.

## Performance Metrics API

### Initialization

The `PerformanceMetrics` class in `ipfs_kit_py.performance_metrics` provides the core functionality:

```python
from ipfs_kit_py.performance_metrics import PerformanceMetrics

# Basic initialization
metrics = PerformanceMetrics()

# Advanced configuration
metrics = PerformanceMetrics(
    max_history=1000,              # Number of data points to retain
    metrics_dir="~/metrics",       # Directory to store metrics logs
    collection_interval=300,       # How often to log (seconds)
    enable_logging=True,           # Whether to enable file logging
    track_system_resources=True,   # Track CPU, memory, disk usage
    retention_days=7               # How long to keep metric logs
)
```

### Context Managers

The easiest way to profile operations is using the `track_operation` context manager:

```python
# Measure a specific operation
with metrics.track_operation("add_file") as tracking:
    # Operation code here
    result = kit.ipfs_add_file(path)
    
    # You can add custom data to the tracking context
    tracking["file_size"] = os.path.getsize(path)
    tracking["successful"] = result.get("success", False)
```

Alternatively, use the `ProfilingContext` class for more control:

```python
from ipfs_kit_py.performance_metrics import ProfilingContext

# Profile a section of code
with ProfilingContext(metrics, "complex_operation") as profile:
    # Operation code here
    # Errors are automatically recorded
```

### Decorators

For profiling entire functions, use the `profile` decorator:

```python
from ipfs_kit_py.performance_metrics import profile

@profile(metrics, name="add_large_file")
def process_large_file(path):
    # Function implementation
    # Performance metrics are automatically collected
    return result
```

### Manual Tracking

You can also track operations manually:

```python
# Start timing manually
start_time = time.time()

# Perform operation
result = kit.ipfs_add_file(path)

# Record the timing
elapsed = time.time() - start_time
metrics.record_operation_time("add_file", elapsed)

# Track bandwidth usage
file_size = os.path.getsize(path)
metrics.record_bandwidth_usage("outbound", file_size, source="add_file")

# Track cache accesses
metrics.record_cache_access("hit", tier="memory")  # For cache hits
metrics.record_cache_access("miss")                # For cache misses
```

### Correlation Tracking

To correlate related operations (e.g., for tracing requests):

```python
# Generate a correlation ID for a request
correlation_id = str(uuid.uuid4())

# Set as default for subsequent operations
metrics.set_correlation_id(correlation_id)

# Use in individual operations
with metrics.track_operation("operation1", correlation_id=correlation_id):
    # First operation
    
with metrics.track_operation("operation2", correlation_id=correlation_id):
    # Second operation
    
# Later, analyze all operations for this correlation ID
operations = metrics.get_correlated_operations(correlation_id)
```

### Metrics Analysis

Get statistics for operations:

```python
# Get statistics for a specific operation
stats = metrics.get_operation_stats("add_file")
print(f"Average latency: {stats['avg']:.3f}s")
print(f"95th percentile: {stats['p95']:.3f}s")

# Get current throughput
throughput = metrics.get_current_throughput()
print(f"Operations/second: {throughput['operations_per_second']:.2f}")
print(f"Bandwidth: {throughput['bytes_per_second']/1024:.2f} KB/s")

# Get system resource utilization
system = metrics.get_system_utilization()
print(f"CPU usage: {system['cpu']['percent']:.1f}%")
print(f"Memory usage: {system['memory']['percent']:.1f}%")

# Get error statistics
errors = metrics.get_error_stats()
print(f"Total errors: {errors['count']}")
```

For comprehensive analysis, use the `analyze_metrics` method:

```python
# Get complete analysis with insights and recommendations
analysis = metrics.analyze_metrics()

# Check insights
print(f"Slowest operation: {analysis['summary']['slowest_operation']['operation']}")
print(f"Cache efficiency: {analysis['summary']['cache_efficiency']}")

# Review recommendations
for rec in analysis["recommendations"]:
    print(f"{rec['severity'].upper()}: {rec['message']}")
    print(f"  {rec['details']}")
```

### Report Generation

Generate formatted reports for easier analysis:

```python
# Generate a plain text report
text_report = metrics.generate_report(output_format="text")
print(text_report)

# Generate a Markdown report
md_report = metrics.generate_report(output_format="markdown")
with open("performance_report.md", "w") as f:
    f.write(md_report)

# Generate a JSON report
json_report = metrics.generate_report(output_format="json")
with open("performance_report.json", "w") as f:
    f.write(json_report)
```

## Comprehensive Benchmarking

The `benchmark.py` module provides structured benchmarking for different aspects of the system.

### Using the Benchmark Module

```python
from ipfs_kit_py.benchmark import IPFSKitBenchmark

# Create a benchmark instance
benchmark = IPFSKitBenchmark(
    metrics_dir="~/benchmark_results",  # Where to store results
    role="leecher",                     # IPFS node role
    parallelism=2,                      # Number of parallel operations
    iterations=5,                       # Number of iterations per test
    warmup=1                            # Warmup iterations
)

# Run specific benchmarks
core_results = benchmark.benchmark_core_operations()
cache_results = benchmark.benchmark_caching()
fsspec_results = benchmark.benchmark_fsspec_operations()
parallel_results = benchmark.benchmark_parallel_operations()

# Or run all benchmarks
all_results = benchmark.run_all_benchmarks()

# Save results to a file
benchmark.save_results("benchmark_results.json")
```

### Command-line Interface

You can also run benchmarks from the command line:

```bash
# Run all benchmarks
python -m ipfs_kit_py.benchmark

# Run with specific options
python -m ipfs_kit_py.benchmark --metrics-dir ~/benchmarks --role worker --parallelism 4 --iterations 10

# Run specific benchmark
python -m ipfs_kit_py.benchmark --benchmark caching
```

Available options:

- `--metrics-dir`: Directory to store metrics and results
- `--role`: IPFS node role (master, worker, leecher)
- `--daemon-port`: IPFS daemon API port
- `--parallelism`: Number of parallel operations
- `--iterations`: Number of iterations for each benchmark
- `--warmup`: Number of warmup iterations before timing
- `--benchmark`: Which benchmark to run (all, core, caching, fsspec, parallel)

### Custom Benchmarks

You can create custom benchmarks by extending the IPFSKitBenchmark class:

```python
from ipfs_kit_py.benchmark import IPFSKitBenchmark

class CustomBenchmark(IPFSKitBenchmark):
    def benchmark_custom_operation(self):
        """Run a custom benchmark."""
        logger.info("Starting custom benchmark...")
        
        # Create test files
        files = self._create_test_files()
        results = {}
        
        try:
            # Your benchmark code here
            for name, (path, content) in files.items():
                with ProfilingContext(self.metrics, f"custom_op_{name}", self.correlation_id):
                    # Operation to benchmark
                    result = self.kit.some_operation(path)
                    
                    # Record results
                    results[name] = {
                        "result": result,
                        "size": len(content)
                    }
                    
                    # Get statistics
                    stats = self.metrics.get_operation_stats(f"custom_op_{name}")
                    results[name].update(stats)
        
        finally:
            # Clean up
            self._cleanup_test_files(files)
        
        # Add to overall results
        self.results["benchmarks"]["custom_operation"] = results
        
        return results
```

## FSSpec Performance Analysis

The FSSpec integration includes built-in performance metrics to analyze caching efficiency and operation latency.

### Enabling Metrics

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Create kit instance
kit = ipfs_kit()

# Get filesystem with metrics enabled
fs = kit.get_filesystem(enable_metrics=True)

# Use the filesystem
content = fs.cat("QmExampleCID")

# Get performance metrics
metrics = fs.get_performance_metrics()
```

### Access Patterns

The `fsspec_benchmark.py` example demonstrates how to analyze different access patterns:

```python
# Run sequential access pattern
sequential_metrics = run_access_pattern_benchmark(fs, cids, "sequential", iterations=5)

# Run random access pattern
random_metrics = run_access_pattern_benchmark(fs, cids, "random", iterations=5)

# Run repeated access pattern (hot spot)
repeated_metrics = run_access_pattern_benchmark(fs, cids, "repeated", iterations=5)
```

### Cache Analysis

Analyze cache performance metrics:

```python
# Get cache statistics
cache_stats = fs.get_performance_metrics()["cache"]

print(f"Total accesses: {cache_stats['total']}")
print(f"Memory hits: {cache_stats['memory_hits']} ({cache_stats['memory_hit_rate']:.2%})")
print(f"Disk hits: {cache_stats['disk_hits']} ({cache_stats['disk_hit_rate']:.2%})")
print(f"Misses: {cache_stats['misses']} ({cache_stats['miss_rate']:.2%})")
print(f"Overall hit rate: {cache_stats['overall_hit_rate']:.2%}")

# For specific tiers
for tier, stats in cache_stats["tiers"].items():
    hits = stats.get("hits", 0)
    misses = stats.get("misses", 0)
    total = hits + misses
    if total > 0:
        hit_rate = hits / total
        print(f"Tier {tier}: {hit_rate:.2%} hit rate")
```

## AI/ML Performance Visualization

IPFS Kit includes comprehensive visualization tools for AI/ML performance metrics through the `ai_ml_visualization` module, which provides both interactive and static visualizations.

### Training Metrics Visualization

Visualize training metrics like loss, accuracy, and learning rate over epochs:

```python
from ipfs_kit_py.ai_ml_metrics import AIMLMetricsCollector
from ipfs_kit_py.ai_ml_visualization import create_visualization

# Create metrics collector
metrics = AIMLMetricsCollector()

# Record training metrics in your training loop
with metrics.track_training_epoch("my_model", epoch=0, num_samples=1000):
    # Record metrics during training
    metrics.record_metric("my_model/epoch/0/train_loss", 1.5)
    metrics.record_metric("my_model/epoch/0/val_loss", 1.7)
    metrics.record_metric("my_model/epoch/0/train_acc", 0.6)
    metrics.record_metric("my_model/epoch/0/val_acc", 0.55)

# Create visualization instance
viz = create_visualization(metrics, theme="light", interactive=True)

# Generate visualization for training metrics
viz.plot_training_metrics(model_id="my_model", show_plot=True)
```

This generates visualizations showing training/validation loss and accuracy curves, learning rate schedules, and epoch timing, giving you insights into model convergence and potential issues like overfitting.

### Inference Performance Analysis

Visualize inference latency distributions and other performance metrics:

```python
# Track inference performance
for batch_size in [1, 2, 4, 8, 16]:
    with metrics.track_inference("my_model", batch_size=batch_size):
        # Run inference here
        # ...
        # Record memory usage
        metrics.record_metric("my_model/inference/memory_mb", 1200)

# Generate inference latency visualization
viz.plot_inference_latency(model_id="my_model", show_plot=True)
```

This generates visualizations showing:
- Latency distributions across different batch sizes
- Memory usage during inference
- Throughput measurements (samples/second)
- Comparison of latency across model versions

### Worker Utilization Visualization

For distributed training, visualize worker utilization metrics:

```python
# Record worker utilization metrics
for worker_id in ["worker-1", "worker-2", "worker-3"]:
    metrics.record_metric(f"workers/{worker_id}/utilization", 0.75)
    metrics.record_metric(f"workers/{worker_id}/memory_mb", 2500)
    metrics.record_metric(f"workers/{worker_id}/active_tasks", 5)

# Generate worker utilization visualization
viz.plot_worker_utilization(show_plot=True)
```

This visualization helps identify:
- Imbalanced worker load distribution
- Resource utilization patterns
- Idle workers or bottlenecks
- Potential scaling opportunities

### Comprehensive Dashboards

Generate a comprehensive dashboard combining multiple visualizations:

```python
# Generate a dashboard with all metrics
viz.plot_comprehensive_dashboard(figsize=(15, 12), show_plot=True)

# Generate an HTML report with all visualizations and metrics
report_path = "performance_report.html"
viz.generate_html_report(report_path)

# Export all visualizations to various formats
exported_files = viz.export_visualizations(
    export_dir="./visualization_exports",
    formats=["png", "svg", "html", "json"]
)
```

The comprehensive dashboard provides:
- Training progress overview
- Inference performance summary
- Resource utilization visualization
- Dataset loading performance
- System-wide performance metrics
- Interactive controls (with Plotly)

For more detailed information and advanced usage, see:
- [AI/ML Visualization Guide](ai_ml_visualization.md)
- Example: `examples/ai_ml_visualization_example.py`

## Performance Optimization

### Identifying Bottlenecks

Use the metrics analysis to identify bottlenecks:

```python
# Run a benchmark or collect metrics during operation
analysis = metrics.analyze_metrics()

# Check for slow operations
if "slowest_operation" in analysis["summary"]:
    slowest = analysis["summary"]["slowest_operation"]
    print(f"Bottleneck identified: {slowest['operation']} - {slowest['avg_seconds']:.3f}s")

# Check for resource constraints
if "system_utilization" in analysis:
    system = analysis["system_utilization"]
    if system["cpu_percent"] > 80:
        print("CPU is a bottleneck - consider scaling horizontally")
    if system["memory_percent"] > 80:
        print("Memory is constrained - consider increasing cache size")
    if system["disk_percent"] > 80:
        print("Disk space is limited - clean up unused content")
        
# Check for cache efficiency
if "cache_efficiency" in analysis["summary"]:
    efficiency = analysis["summary"]["cache_efficiency"]
    if efficiency == "poor":
        print("Cache hit rate is low - adjust cache parameters and access patterns")
```

### Optimizing Caching

Adjust cache parameters based on your access patterns:

```python
# Get filesystem with optimized cache settings
fs = kit.get_filesystem(
    cache_config={
        'memory_cache_size': 500 * 1024 * 1024,  # 500MB memory cache
        'local_cache_size': 5 * 1024 * 1024 * 1024,  # 5GB disk cache
        'local_cache_path': '/tmp/ipfs_cache',
        'max_item_size': 100 * 1024 * 1024,  # Cache files up to 100MB in memory
        'min_access_count': 2  # Only cache items accessed at least twice
    },
    use_mmap=True  # Use memory mapping for large files
)
```

Tips for optimizing cache performance:

1. **Adjust tier sizes**: Allocate more memory to the cache if you frequently access the same content
2. **Fine-tune max_item_size**: Smaller values keep more items in memory, larger values optimize for fewer large items
3. **Use pin functionality**: Pin important content to ensure it stays in the local node
4. **Consider access patterns**: Sequential access benefits from prefetching, random access benefits from larger caches
5. **Monitor heat scores**: Heat scores help identify content that should be promoted to faster tiers

### Scaling with Parallelism

For high-throughput operations, use parallel processing:

```python
import concurrent.futures

# Use ThreadPoolExecutor for I/O-bound operations
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    # Submit multiple retrieval operations
    futures = {
        executor.submit(kit.ipfs_cat, cid): cid
        for cid in cids_to_retrieve
    }
    
    # Process results as they complete
    for future in concurrent.futures.as_completed(futures):
        cid = futures[future]
        try:
            data = future.result()
            # Process data
        except Exception as e:
            print(f"Error retrieving {cid}: {e}")
```

Benchmark parallel performance to find the optimal level of parallelism:

```python
# Run parallel operations benchmark
parallel_results = benchmark.benchmark_parallel_operations()

# Analyze results to find optimal parallelism
for workers, results in parallel_results["parallel_cat"].items():
    print(f"Workers: {workers}")
    print(f"  Requests per second: {results.get('requests_per_second', 0):.2f}")
    print(f"  Average latency: {results.get('avg', 0):.3f}s")
```
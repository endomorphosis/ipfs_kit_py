#!/usr/bin/env python3
"""
IPFS Kit Performance Profiling Examples

This file contains two different approaches to performance profiling in IPFS Kit:

1. Built-in metrics API: Demonstrates how to use the performance metrics system 
   to profile and analyze IPFS operations in your application.

2. Advanced profiling tools: Shows how to use the comprehensive profiling and 
   optimization tools to benchmark, improve, and compare performance.

See also:
- examples/performance_profiling.py - Detailed benchmarking tool
- examples/performance_optimizations.py - Automatic optimization tool 
- examples/compare_profiles.py - Performance comparison tool
- examples/PERFORMANCE_PROFILING.md - Documentation
"""

import os
import sys
import time
import uuid
import tempfile
import logging
from contextlib import contextmanager

# Add the parent directory to the path to import ipfs_kit_py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.performance_metrics import PerformanceMetrics, ProfilingContext, profile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create metrics instance
metrics = PerformanceMetrics(
    metrics_dir=os.path.expanduser("~/ipfs_metrics"),
    enable_logging=True,
    track_system_resources=True
)

# Create IPFS Kit instance
kit = ipfs_kit()

# Example 1: Using context managers for profiling
def example_context_manager():
    """Demonstrate profiling with context managers."""
    logger.info("Example 1: Profiling with context managers")
    
    # Create a test file
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(b"Hello, IPFS! " * 1000)
        temp_path = temp.name
    
    try:
        # Using track_operation context manager
        with metrics.track_operation("add_file") as tracking:
            # Add the file to IPFS
            result = kit.ipfs_add_file(temp_path)
            
            if result and "Hash" in result:
                cid = result["Hash"]
                # You can add custom data to the tracking context
                tracking["file_size"] = os.path.getsize(temp_path)
                tracking["cid"] = cid
                logger.info(f"Added file with CID: {cid}")
            else:
                logger.error("Failed to add file")
                return
        
        # Using ProfilingContext class
        with ProfilingContext(metrics, "retrieve_file") as profile:
            # Retrieve the file content
            content = kit.ipfs_cat(cid)
            logger.info(f"Retrieved {len(content)} bytes")
        
        # Print operation statistics
        add_stats = metrics.get_operation_stats("add_file")
        retrieve_stats = metrics.get_operation_stats("retrieve_file")
        
        logger.info(f"Add operation took {add_stats['avg']:.4f}s")
        logger.info(f"Retrieve operation took {retrieve_stats['avg']:.4f}s")
        
    finally:
        # Clean up test file
        os.unlink(temp_path)

# Example 2: Using decorators for profiling
@profile(metrics, name="process_files")
def process_files(count=3, size=1024):
    """Process multiple files with performance tracking."""
    logger.info(f"Processing {count} files of size {size} bytes")
    
    # Create multiple files and add to IPFS
    cids = []
    for i in range(count):
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(os.urandom(size))
            temp_path = temp.name
            
        try:
            # Add file to IPFS (also being tracked by decorator)
            result = kit.ipfs_add_file(temp_path)
            if result and "Hash" in result:
                cids.append(result["Hash"])
            
            # Clean up
            os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Error processing file {i}: {e}")
            
    return cids

# Example 3: Correlation tracking for related operations
def example_correlation_tracking():
    """Demonstrate correlation tracking for related operations."""
    logger.info("Example 3: Correlation tracking")
    
    # Generate a correlation ID for this sequence of operations
    correlation_id = str(uuid.uuid4())
    logger.info(f"Using correlation ID: {correlation_id}")
    
    # Create a test file
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(b"Correlation test " * 100)
        temp_path = temp.name
    
    try:
        # Add the file to IPFS with correlation tracking
        with metrics.track_operation("add_correlated", correlation_id=correlation_id) as tracking:
            result = kit.ipfs_add_file(temp_path)
            if result and "Hash" in result:
                cid = result["Hash"]
                tracking["cid"] = cid
            else:
                logger.error("Failed to add file")
                return
        
        # Pin the file with the same correlation ID
        with metrics.track_operation("pin_correlated", correlation_id=correlation_id):
            kit.ipfs_pin_add(cid)
            
        # Retrieve the file with the same correlation ID
        with metrics.track_operation("cat_correlated", correlation_id=correlation_id):
            content = kit.ipfs_cat(cid)
            
        # Get all operations for this correlation ID
        operations = metrics.get_correlated_operations(correlation_id)
        
        logger.info(f"Correlated operations: {len(operations)}")
        for op in operations:
            logger.info(f"  {op['operation']}: {op.get('elapsed', 0):.4f}s")
            
    finally:
        # Clean up test file
        os.unlink(temp_path)

# Example 4: Manual tracking
def example_manual_tracking():
    """Demonstrate manual performance tracking."""
    logger.info("Example 4: Manual performance tracking")
    
    # Create a test file
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        data = os.urandom(10 * 1024)  # 10KB
        temp.write(data)
        temp_path = temp.name
        file_size = len(data)
    
    try:
        # Manually time the operation
        start_time = time.time()
        
        # Add file to IPFS
        result = kit.ipfs_add_file(temp_path)
        
        # Calculate elapsed time
        elapsed = time.time() - start_time
        
        # Manually record metrics
        metrics.record_operation_time("manual_add", elapsed)
        
        # Record bandwidth usage
        metrics.record_bandwidth_usage("outbound", file_size, source="ipfs_add")
        
        # Get statistics
        stats = metrics.get_operation_stats("manual_add")
        logger.info(f"Manual tracking: Operation took {elapsed:.4f}s")
        
        if result and "Hash" in result:
            cid = result["Hash"]
            
            # Test cache behavior
            # First access (miss)
            start = time.time()
            content1 = kit.ipfs_cat(cid)
            time1 = time.time() - start
            metrics.record_cache_access("miss")
            
            # Second access (should be a hit)
            start = time.time()
            content2 = kit.ipfs_cat(cid)
            time2 = time.time() - start
            metrics.record_cache_access("hit", tier="memory")
            
            logger.info(f"First access (miss): {time1:.4f}s")
            logger.info(f"Second access (hit): {time2:.4f}s")
            logger.info(f"Speedup: {time1/time2:.1f}x")
            
    finally:
        # Clean up test file
        os.unlink(temp_path)

# Example 5: Analyzing metrics
def example_metrics_analysis():
    """Demonstrate metrics analysis capabilities."""
    logger.info("Example 5: Metrics analysis")
    
    # Run some operations to generate metrics
    for i in range(5):
        with metrics.track_operation("analysis_test"):
            # Simulate varying workloads
            time.sleep(0.01 * (i + 1))
    
    # Generate comprehensive analysis
    analysis = metrics.analyze_metrics()
    
    # Print key insights
    if "summary" in analysis:
        logger.info("Performance summary:")
        for key, value in analysis["summary"].items():
            if isinstance(value, dict):
                logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {key}: {value}")
    
    # Print recommendations
    if "recommendations" in analysis:
        logger.info("Recommendations:")
        for rec in analysis["recommendations"]:
            logger.info(f"  {rec['severity'].upper()}: {rec['message']}")
            logger.info(f"  {rec['details']}")
    
    # Generate a report
    report = metrics.generate_report(output_format="markdown")
    report_path = os.path.expanduser("~/ipfs_performance_report.md")
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Performance report written to {report_path}")

def main():
    """Run all examples."""
    try:
        # Example 1: Context managers
        example_context_manager()
        
        # Example 2: Decorators
        cids = process_files(count=3, size=1024 * 10)  # 10KB files
        logger.info(f"Processed {len(cids)} files")
        logger.info(f"Process files operation statistics: {metrics.get_operation_stats('process_files')}")
        
        # Example 3: Correlation tracking
        example_correlation_tracking()
        
        # Example 4: Manual tracking
        example_manual_tracking()
        
        # Example 5: Metrics analysis
        example_metrics_analysis()
        
        # Shutdown metrics handler
        metrics.shutdown()
        
        logger.info("All examples completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
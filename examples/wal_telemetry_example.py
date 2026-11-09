# examples/wal_telemetry_example.py

"""
Example demonstrating the use of the WAL Telemetry system for monitoring
and analyzing performance metrics from the Write-Ahead Log.

This example demonstrates:
1. Setting up the telemetry system with a WAL instance
2. Generating test operations to collect telemetry data
3. Retrieving and analyzing real-time metrics
4. Generating performance reports with visualizations
5. Using different aggregation methods for metrics analysis
"""

import os
import time
import random
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import IPFS Kit components with error handling
try:
    from ipfs_kit_py.storage_wal import (
        StorageWriteAheadLog,
        BackendHealthMonitor,
        OperationType,
        OperationStatus,
        BackendType
    )
    from ipfs_kit_py.wal_telemetry import (
        WALTelemetry,
        TelemetryMetricType,
        TelemetryAggregation
    )
    WAL_AVAILABLE = True
except ImportError:
    logger.error("WAL system not available. Make sure ipfs_kit_py is installed.")
    WAL_AVAILABLE = False

def generate_test_operations(wal, count=50, operation_types=None, backends=None, error_rate=0.1):
    """
    Generate test operations to collect telemetry data.
    
    Args:
        wal: StorageWriteAheadLog instance
        count: Number of operations to generate
        operation_types: List of operation types to use (None for default)
        backends: List of backends to use (None for default)
        error_rate: Probability of operation failure (0.0 - 1.0)
        
    Returns:
        List of operation IDs
    """
    if operation_types is None:
        operation_types = [
            OperationType.ADD.value,
            OperationType.GET.value,
            OperationType.PIN.value,
            OperationType.UNPIN.value
        ]
        
    if backends is None:
        backends = [
            BackendType.IPFS.value,
            BackendType.S3.value,
            BackendType.STORACHA.value
        ]
    
    operation_ids = []
    for i in range(count):
        # Select random operation type and backend
        op_type = random.choice(operation_types)
        backend = random.choice(backends)
        
        # Create sample parameters
        if op_type == OperationType.ADD.value:
            parameters = {"path": f"/tmp/file{i}.txt", "size": random.randint(1024, 1024*1024)}
        elif op_type == OperationType.GET.value:
            parameters = {"cid": f"Qm{''.join([random.choice('abcdef0123456789') for _ in range(44)])}", "timeout": 30}
        elif op_type == OperationType.PIN.value:
            parameters = {"cid": f"Qm{''.join([random.choice('abcdef0123456789') for _ in range(44)])}", "recursive": True}
        elif op_type == OperationType.UNPIN.value:
            parameters = {"cid": f"Qm{''.join([random.choice('abcdef0123456789') for _ in range(44)])}", "recursive": True}
        else:
            parameters = {"operation": op_type}
        
        # Intentionally fail some operations based on error_rate
        if random.random() < error_rate:
            # For testing, we can modify mock handler behavior via custom parameter
            parameters["__test_fail"] = True
        
        # Add operation to WAL
        result = wal.add_operation(
            operation_type=op_type,
            backend=backend,
            parameters=parameters
        )
        
        if result.get("success", False):
            operation_ids.append(result["operation_id"])
            logger.info(f"Added operation: {result['operation_id']} ({op_type} on {backend})")
        else:
            logger.error(f"Failed to add operation: {result.get('error', 'Unknown error')}")
    
    return operation_ids

def display_real_time_metrics(metrics):
    """Display real-time metrics in a readable format."""
    print("\n=== Real-Time Metrics ===")
    
    # Display latency metrics
    if metrics.get("latency"):
        print("\nLatency Metrics:")
        for key, latency_data in metrics["latency"].items():
            op_type, backend = key.split(":")
            print(f"  {op_type} on {backend}:")
            print(f"    Mean: {latency_data['mean']:.4f}s")
            print(f"    Median: {latency_data['median']:.4f}s")
            print(f"    Min: {latency_data['min']:.4f}s")
            print(f"    Max: {latency_data['max']:.4f}s")
            print(f"    95th Percentile: {latency_data['percentile_95']:.4f}s")
            print(f"    Sample Count: {latency_data['count']}")
    
    # Display success rate metrics
    if metrics.get("success_rate"):
        print("\nSuccess Rate Metrics:")
        for key, rate in metrics["success_rate"].items():
            op_type, backend = key.split(":")
            print(f"  {op_type} on {backend}: {rate * 100:.2f}%")
    
    # Display error rate metrics
    if metrics.get("error_rate"):
        print("\nError Rate Metrics:")
        for key, rate in metrics["error_rate"].items():
            op_type, backend = key.split(":")
            print(f"  {op_type} on {backend}: {rate * 100:.2f}%")
    
    # Display throughput metrics
    if metrics.get("throughput"):
        print("\nThroughput Metrics:")
        for key, throughput in metrics["throughput"].items():
            if ":" in key:
                op_type, backend = key.split(":")
                print(f"  {op_type} on {backend}: {throughput:.2f} ops/min")
            else:
                print(f"  {key}: {throughput:.2f} ops/min")
    
    # Display status distribution
    if metrics.get("status_distribution"):
        print("\nOperation Status Distribution:")
        for key, status_counts in metrics["status_distribution"].items():
            op_type, backend = key.split(":")
            print(f"  {op_type} on {backend}:")
            for status, count in status_counts.items():
                print(f"    {status}: {count}")

def run_telemetry_example():
    """Run the WAL telemetry example."""
    if not WAL_AVAILABLE:
        logger.error("WAL system not available. Example cannot run.")
        return
    
    # Create directories for data and reports
    os.makedirs("~/.ipfs_kit/wal", exist_ok=True)
    os.makedirs("~/.ipfs_kit/telemetry", exist_ok=True)
    report_path = os.path.join(os.getcwd(), "telemetry_report")
    os.makedirs(report_path, exist_ok=True)
    
    # Create health monitor for backend status tracking
    logger.info("Creating health monitor...")
    health_monitor = BackendHealthMonitor(
        check_interval=5,
        history_size=10,
        status_change_callback=lambda backend, old, new: 
            logger.info(f"Backend {backend} status changed from {old} to {new}")
    )
    
    # Create WAL instance
    logger.info("Creating WAL instance...")
    wal = StorageWriteAheadLog(
        base_path=os.path.expanduser("~/.ipfs_kit/wal"),
        partition_size=100,
        health_monitor=health_monitor
    )
    
    # Create telemetry instance
    logger.info("Setting up telemetry system...")
    telemetry = WALTelemetry(
        wal=wal,
        metrics_path=os.path.expanduser("~/.ipfs_kit/telemetry"),
        sampling_interval=5,
        enable_detailed_timing=True,
        operation_hooks=True  # Install hooks for automatic metrics collection
    )
    
    # Generate test operations
    logger.info("Generating test operations...")
    operation_ids = generate_test_operations(
        wal=wal,
        count=50,
        error_rate=0.15  # 15% failure rate for testing
    )
    
    # Wait for operations to complete
    logger.info("Waiting for operations to complete...")
    for i in range(3):
        logger.info(f"Processing cycle {i+1}...")
        # Let operations process
        time.sleep(5)
        
        # Get current statistics
        stats = wal.get_statistics()
        logger.info(f"Current stats: {stats}")
    
    # Get and display real-time metrics
    logger.info("Retrieving real-time metrics...")
    real_time_metrics = telemetry.get_real_time_metrics()
    display_real_time_metrics(real_time_metrics)
    
    # Generate a performance report
    logger.info("Generating performance report...")
    time_now = time.time()
    time_range = (time_now - 3600, time_now)  # Last hour
    
    report_result = telemetry.create_performance_report(
        output_path=report_path,
        time_range=time_range
    )
    
    if report_result.get("success", False):
        logger.info(f"Performance report generated at: {report_result['report_path']}")
    else:
        logger.error(f"Failed to generate report: {report_result.get('error', 'Unknown error')}")
    
    # Query specific metrics with different aggregations
    logger.info("\nQuerying metrics with different aggregations...")
    
    # Get average latency by operation type
    avg_latency = telemetry.get_metrics(
        metric_type=TelemetryMetricType.OPERATION_LATENCY,
        time_range=time_range,
        aggregation=TelemetryAggregation.AVERAGE
    )
    
    print("\n=== Average Latency by Operation Type ===")
    try:
        for op_type, backends in avg_latency.get("metrics", {}).items():
            print(f"\nOperation Type: {op_type}")
            for backend, latency in backends.items():
                print(f"  Backend: {backend}, Average Latency: {latency:.4f}s")
    except (KeyError, ValueError, TypeError) as e:
        print(f"Error displaying latency metrics: {e}")
        
    # Get maximum success rate
    success_rate = telemetry.get_metrics(
        metric_type=TelemetryMetricType.SUCCESS_RATE,
        time_range=time_range,
        aggregation=TelemetryAggregation.MAXIMUM
    )
    
    print("\n=== Maximum Success Rate ===")
    try:
        for category, rate in success_rate.get("metrics", {}).get("success_rate", {}).items():
            print(f"  {category}: {rate * 100:.2f}%")
    except (KeyError, ValueError, TypeError) as e:
        print(f"Error displaying success rate metrics: {e}")
        
    # Get throughput rate
    throughput = telemetry.get_metrics(
        metric_type=TelemetryMetricType.THROUGHPUT,
        time_range=time_range,
        aggregation=TelemetryAggregation.AVERAGE
    )
    
    print("\n=== Average Throughput ===")
    try:
        for category, rate in throughput.get("metrics", {}).items():
            print(f"  {category}: {rate:.2f} ops/min")
    except (KeyError, ValueError, TypeError) as e:
        print(f"Error displaying throughput metrics: {e}")
    
    # Visualize specific metrics
    logger.info("\nGenerating specific metric visualizations...")
    
    # Visualize latency for a specific operation type
    telemetry.visualize_metrics(
        metric_type=TelemetryMetricType.OPERATION_LATENCY,
        output_path=os.path.join(report_path, "add_operation_latency.png"),
        operation_type=OperationType.ADD.value,
        time_range=time_range
    )
    
    # Visualize health for a specific backend
    telemetry.visualize_metrics(
        metric_type=TelemetryMetricType.BACKEND_HEALTH,
        output_path=os.path.join(report_path, "ipfs_health.png"),
        backend=BackendType.IPFS.value,
        time_range=time_range
    )
    
    # Clean up
    logger.info("Cleaning up resources...")
    telemetry.close()
    wal.close()
    health_monitor.close()
    
    logger.info("Telemetry example completed.")
    logger.info(f"Performance report and visualizations saved to: {report_path}")

if __name__ == "__main__":
    run_telemetry_example()
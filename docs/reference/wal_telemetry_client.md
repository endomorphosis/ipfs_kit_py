# WAL Telemetry Client

The WAL Telemetry Client provides a convenient Python client for accessing the WAL telemetry API. This client makes it easy to retrieve metrics, generate reports, and visualize performance data from the WAL system.

## Features

- **Metric Retrieval**: Access telemetry metrics with filtering by type, operation, backend, and time range
- **Real-time Monitoring**: Get up-to-the-moment metrics about system performance
- **Report Generation**: Create comprehensive performance reports for analysis
- **Visualization**: Generate charts and graphs for different metric types
- **Time Series Analysis**: Analyze metrics over time to identify trends and patterns
- **Configuration Management**: View and update telemetry system configuration
- **Connection Pooling**: Efficient reuse of HTTP connections for better performance
- **Error Handling**: Comprehensive error handling with informative messages

## Installation

The WAL Telemetry Client is included as part of the ipfs_kit_py package. No separate installation is required.

## Basic Usage

```python
from ipfs_kit_py.wal_telemetry_client import WALTelemetryClient, TelemetryMetricType

# Create client
client = WALTelemetryClient(base_url="http://localhost:8000")

# Get real-time metrics
metrics = client.get_realtime_metrics()
print(f"Current operation latency: {metrics['operation_latency']['average']} ms")
print(f"Success rate: {metrics['success_rate']['value'] * 100:.2f}%")

# Get specific metrics with filtering
latency_metrics = client.get_metrics(
    metric_type=TelemetryMetricType.OPERATION_LATENCY,
    operation_type="append"
)

# Generate performance report
report = client.generate_report(open_browser=True)

# Get visualization
client.get_visualization(
    metric_type=TelemetryMetricType.THROUGHPUT,
    open_browser=True
)
```

## API Reference

### Initialization

```python
client = WALTelemetryClient(
    base_url="http://localhost:8000",  # Base URL for API server
    api_key=None,                      # Optional API key for authentication
    timeout=30,                        # Timeout in seconds for requests
    verify_ssl=True                    # Whether to verify SSL certificates
)
```

### Core Methods

#### Get Metrics

Retrieve telemetry metrics with optional filtering.

```python
metrics = client.get_metrics(
    metric_type="operation_latency",  # Type of metrics to retrieve
    operation_type="append",          # Filter by operation type
    backend="json",                   # Filter by backend type
    status="success",                 # Filter by operation status
    time_range=(start_time, end_time), # Tuple of (start_time, end_time)
    aggregation="average"             # Type of aggregation to apply
)
```

#### Get Real-time Metrics

Get the latest real-time metrics.

```python
metrics = client.get_realtime_metrics()
```

#### Generate Report

Generate a comprehensive performance report.

```python
report = client.generate_report(
    start_time=None,     # Start time for time range (Unix timestamp)
    end_time=None,       # End time for time range (Unix timestamp)
    open_browser=False   # Whether to open the report in a browser
)
```

#### Get Report File

Retrieve a file from a generated report.

```python
file = client.get_report_file(
    report_id="report_123",  # ID of the report from generate_report()
    file_name="index.html",  # Name of the file to retrieve
    save_path="report.html"  # Path to save the file (optional)
)
```

#### Get Visualization

Generate a visualization for a specific metric type.

```python
viz = client.get_visualization(
    metric_type=TelemetryMetricType.OPERATION_LATENCY,  # Type of metrics to visualize
    operation_type="append",                            # Filter by operation type
    backend="json",                                     # Filter by backend type
    status="success",                                   # Filter by operation status
    time_range=(start_time, end_time),                  # Tuple of (start_time, end_time)
    width=12,                                           # Chart width in inches
    height=8,                                           # Chart height in inches
    save_path="latency.png",                            # Path to save the visualization
    open_browser=False                                  # Whether to open in browser
)
```

#### Get Configuration

Get the current telemetry configuration.

```python
config = client.get_config()
```

#### Update Configuration

Update the telemetry configuration.

```python
result = client.update_config(
    enabled=True,                     # Whether telemetry is enabled
    metrics_path="/path/to/metrics",  # Path for metrics storage
    retention_days=30,                # Number of days to retain metrics
    sampling_interval=60,             # Interval between samples in seconds
    enable_detailed_timing=True,      # Whether to collect detailed timing
    operation_hooks=True              # Whether to install operation hooks
)
```

### Advanced Methods

#### Get Metrics Over Time

Get metrics for multiple time periods to create a time series.

```python
time_series = client.get_metrics_over_time(
    metric_type=TelemetryMetricType.OPERATION_LATENCY,  # Type of metrics to retrieve
    operation_type="append",                            # Filter by operation type
    backend="json",                                     # Filter by backend type
    status="success",                                   # Filter by operation status
    start_time=None,                                    # Start time (defaults to 24h ago)
    end_time=None,                                      # End time (defaults to now)
    interval="hour"                                     # Time interval ('hour', 'day', 'week')
)
```

#### Monitor Real-time Metrics

Continuously monitor real-time metrics with a callback function.

```python
def print_metrics(metrics, iteration):
    """Print metrics as they arrive."""
    print(f"Iteration {iteration}: Latency = {metrics['operation_latency']['average']} ms")

# Monitor for 60 seconds with updates every 5 seconds
client.monitor_realtime(
    callback=print_metrics,
    interval=5,
    duration=60
)
```

## Metric Types

The `TelemetryMetricType` enum provides the following metric types:

- `OPERATION_COUNT`: Count of operations by type
- `OPERATION_LATENCY`: Latency of operations in milliseconds
- `SUCCESS_RATE`: Rate of successful operations (0-1)
- `ERROR_RATE`: Rate of failed operations (0-1)
- `BACKEND_HEALTH`: Health status of backends
- `THROUGHPUT`: Operations per second
- `QUEUE_SIZE`: Number of operations in queue
- `RETRY_COUNT`: Number of retry attempts

## Aggregation Types

The `TelemetryAggregation` enum provides the following aggregation methods:

- `SUM`: Sum of all values
- `AVERAGE`: Average value
- `MINIMUM`: Minimum value
- `MAXIMUM`: Maximum value
- `PERCENTILE_95`: 95th percentile
- `PERCENTILE_99`: 99th percentile
- `COUNT`: Count of values
- `RATE`: Rate of values per second

## Error Handling

The client includes comprehensive error handling. All methods will raise exceptions if the API returns an error or if the request fails. To handle errors:

```python
from ipfs_kit_py.wal_telemetry_client import WALTelemetryClient
import requests

client = WALTelemetryClient(base_url="http://localhost:8000")

try:
    metrics = client.get_realtime_metrics()
    # Process metrics...
except requests.RequestException as e:
    # Handle network-related errors
    print(f"Network error: {e}")
except ValueError as e:
    # Handle API errors
    print(f"API error: {e}")
except Exception as e:
    # Handle other errors
    print(f"Error: {e}")
```

## Example: Dashboard Integration

For an advanced example of using the telemetry client with a dashboard interface, see the `wal_telemetry_client_example.py` file in the examples directory. This example shows how to:

1. Set up real-time monitoring
2. Generate performance visualizations
3. Analyze time series data
4. Create comprehensive reports
5. Set up an alerting system for metrics that exceed thresholds

## Environment Variables

The client supports the following environment variables:

- `WAL_TELEMETRY_API_URL`: Base URL for the API (default: http://localhost:8000)
- `WAL_TELEMETRY_API_KEY`: API key for authentication
- `WAL_TELEMETRY_TIMEOUT`: Request timeout in seconds (default: 30)
- `WAL_TELEMETRY_VERIFY_SSL`: Whether to verify SSL certificates (default: 1)

## Thread Safety

The WAL Telemetry Client is thread-safe, and multiple threads can use the same client instance concurrently. The client uses a connection pool to efficiently reuse HTTP connections.
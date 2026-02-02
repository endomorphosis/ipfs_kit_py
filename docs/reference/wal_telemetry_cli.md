# WAL Telemetry CLI

The WAL Telemetry CLI provides a command-line interface for accessing telemetry metrics, generating reports, and visualizing performance data from the WAL system.

## Installation

The WAL Telemetry CLI is included as part of the ipfs_kit_py package. No separate installation is required. The CLI executable is available at `bin/telemetry` after installing the package.

## Basic Usage

```bash
# Get telemetry metrics
telemetry metrics

# Watch metrics in real-time
telemetry metrics --watch

# Generate a performance report
telemetry report --browser

# Generate a visualization for a specific metric
telemetry viz --type operation_latency --browser

# Get current configuration
telemetry config

# Analyze time series data
telemetry analyze --type success_rate --days 7
```

## Command Reference

### Global Options

These options apply to all commands:

- `--url`: API base URL (default: http://localhost:8000)
- `--key`: API key for authentication
- `--timeout`: Request timeout in seconds (default: 30)
- `--no-verify`: Disable SSL verification

### Metrics Command

Retrieve telemetry metrics with optional filtering:

```bash
telemetry metrics [OPTIONS]
```

Options:
- `--watch`, `-w`: Watch metrics in real-time
- `--interval`, `-i`: Update interval in seconds for watch mode (default: 2)
- `--count`, `-n`: Number of updates for watch mode (default: infinite)
- `--type`, `-t`: Type of metrics to retrieve (e.g., "operation_latency")
- `--operation`, `-o`: Filter by operation type (e.g., "append")
- `--backend`, `-b`: Filter by backend type (e.g., "json")
- `--status`, `-s`: Filter by operation status (e.g., "success")
- `--since`: Get metrics since time (e.g., "10m", "2h", "1d", or "YYYY-MM-DD HH:MM:SS")
- `--aggregation`, `-a`: Type of aggregation to apply (e.g., "average")
- `--filter`, `-f`: Filter metrics by name (e.g., "operation_latency" "success_rate")

Examples:
```bash
# Watch metrics in real-time with updates every 5 seconds
telemetry metrics --watch --interval 5

# Get operation latency metrics for the last hour
telemetry metrics --type operation_latency --since 1h

# Get metrics for append operations with average aggregation
telemetry metrics --operation append --aggregation average
```

### Report Command

Generate a comprehensive performance report:

```bash
telemetry report [OPTIONS]
```

Options:
- `--browser`, `-b`: Open report in browser
- `--output`, `-o`: Save report to file
- `--since`: Include data since time (e.g., "10m", "2h", "1d", or "YYYY-MM-DD HH:MM:SS")

Examples:
```bash
# Generate a report and open in browser
telemetry report --browser

# Save report to file
telemetry report --output ~/reports/telemetry_report.html

# Generate a report for the last 24 hours
telemetry report --since 24h
```

### Visualization Command

Generate visualizations for specific metrics:

```bash
telemetry viz --type METRIC_TYPE [OPTIONS]
```

Options:
- `--type`, `-t`: Type of metrics to visualize (**required**)
- `--operation`, `-o`: Filter by operation type
- `--backend`, `-b`: Filter by backend type
- `--status`, `-s`: Filter by operation status
- `--since`: Include data since time
- `--width`: Chart width in inches (default: 12)
- `--height`: Chart height in inches (default: 8)
- `--output`, `-o`: Save visualization to file
- `--browser`, `-b`: Open visualization in browser

Examples:
```bash
# Generate a throughput visualization and open in browser
telemetry viz --type throughput --browser

# Generate a latency visualization for the last 3 days
telemetry viz --type operation_latency --since 3d --output latency.png

# Generate a success rate visualization for append operations
telemetry viz --type success_rate --operation append --browser
```

### Config Command

Get or update telemetry configuration:

```bash
telemetry config [OPTIONS]
```

Options:
- `--update`, `-u`: Update configuration
- `--enabled`: Whether telemetry is enabled (true/false)
- `--metrics-path`: Directory for telemetry metrics storage
- `--retention-days`: Number of days to retain metrics
- `--sampling-interval`: Interval in seconds between metric samples
- `--detailed-timing`: Whether to collect detailed timing data (true/false)
- `--operation-hooks`: Whether to install operation hooks (true/false)

Examples:
```bash
# Get current configuration
telemetry config

# Enable telemetry
telemetry config --update --enabled true

# Update retention period
telemetry config --update --retention-days 7

# Update sampling interval
telemetry config --update --sampling-interval 30
```

### Analyze Command

Analyze time series data for specific metrics:

```bash
telemetry analyze --type METRIC_TYPE [OPTIONS]
```

Options:
- `--type`, `-t`: Type of metrics to analyze (**required**)
- `--operation`, `-o`: Filter by operation type
- `--days`, `-d`: Number of days to analyze (default: 1)
- `--interval`, `-i`: Time interval for analysis ("hour", "day", "week"; default: "hour")

Examples:
```bash
# Analyze operation latency over the past day
telemetry analyze --type operation_latency

# Analyze success rate for append operations over the past week
telemetry analyze --type success_rate --operation append --days 7

# Analyze throughput with daily intervals
telemetry analyze --type throughput --interval day --days 14
```

## Metric Types

The following metric types are available:

- `operation_count`: Count of operations by type
- `operation_latency`: Latency of operations in milliseconds
- `success_rate`: Rate of successful operations (0-1)
- `error_rate`: Rate of failed operations (0-1)
- `backend_health`: Health status of backends
- `throughput`: Operations per second
- `queue_size`: Number of operations in queue
- `retry_count`: Number of retry attempts

## Aggregation Types

The following aggregation methods are available:

- `sum`: Sum of all values
- `average`: Average value
- `minimum`: Minimum value
- `maximum`: Maximum value
- `percentile_95`: 95th percentile
- `percentile_99`: 99th percentile
- `count`: Count of values
- `rate`: Rate of values per second

## Environment Variables

The CLI supports the following environment variables:

- `WAL_TELEMETRY_API_URL`: Base URL for the API (default: http://localhost:8000)
- `WAL_TELEMETRY_API_KEY`: API key for authentication
- `WAL_TELEMETRY_TIMEOUT`: Request timeout in seconds (default: 30)
- `WAL_TELEMETRY_VERIFY_SSL`: Whether to verify SSL certificates (1 for true, 0 for false)

## Examples

### Real-time Monitoring

```bash
# Watch metrics in real-time
telemetry metrics --watch

# Watch specific metrics with 3-second updates
telemetry metrics --watch --filter operation_latency success_rate error_rate --interval 3
```

### Performance Analysis

```bash
# Analyze operation latency over time
telemetry analyze --type operation_latency --days 7

# Generate a visualization for the analysis
telemetry viz --type operation_latency --since 7d --browser

# Generate a comprehensive report
telemetry report --since 7d --browser
```

### Configuration Management

```bash
# Check current configuration
telemetry config

# Update sampling interval
telemetry config --update --sampling-interval 15

# Enable detailed timing
telemetry config --update --detailed-timing true
```

## Troubleshooting

### Common Issues

#### Connection Errors

If you see connection errors, check that:
- The API server is running
- The correct base URL is specified
- Network connectivity is available

Example:
```bash
# Specify a different API URL
telemetry --url http://alternate-server:8000 metrics
```

#### No Metrics Available

If no metrics are displayed, check that:
- Telemetry is enabled in the WAL configuration
- Operations have been performed to generate metrics
- The correct filters are specified

Example:
```bash
# Enable telemetry
telemetry config --update --enabled true

# Generate some operations and check again
telemetry metrics
```

#### SSL Certificate Verification Issues

If you encounter SSL certificate verification issues:

```bash
# Disable SSL verification
telemetry --no-verify metrics
```

Or set the environment variable:
```bash
export WAL_TELEMETRY_VERIFY_SSL=0
telemetry metrics
```
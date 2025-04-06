# WAL Telemetry API

The IPFS Kit Write-Ahead Log (WAL) system includes comprehensive telemetry capabilities that are accessible through a REST API. This document describes the telemetry API endpoints and their usage.

## Overview

The WAL telemetry system collects, stores, analyzes, and visualizes performance metrics for the WAL system, providing insights into operation latency, throughput, success rates, and backend health. The telemetry API provides RESTful endpoints for accessing these metrics and generating visualizations and reports.

## Endpoints

All endpoints are available under the `/api/v0/wal/telemetry` path.

### Get Telemetry Metrics

`GET /api/v0/wal/telemetry/metrics`

Retrieves telemetry metrics with optional filtering.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `metric_type` | string | Type of metrics to retrieve (operation_count, operation_latency, etc.) |
| `operation_type` | string | Filter by operation type (add, get, pin, etc.) |
| `backend` | string | Filter by backend type (ipfs, s3, storacha, etc.) |
| `status` | string | Filter by operation status (pending, completed, failed, etc.) |
| `start_time` | float | Start time for time range filter (Unix timestamp) |
| `end_time` | float | End time for time range filter (Unix timestamp) |
| `aggregation` | string | Type of aggregation to apply (sum, average, minimum, maximum, etc.) |

#### Response

```json
{
  "success": true,
  "operation": "get_telemetry",
  "timestamp": 1714953237.4568963,
  "metrics": {
    "operation_latency": {
      "add": {
        "ipfs": [
          {
            "timestamp": 1714953230.5,
            "mean": 0.85,
            "median": 0.82,
            "min": 0.5,
            "max": 1.2,
            "percentile_95": 1.1,
            "percentile_99": 1.2
          }
        ]
      }
    }
  },
  "metric_type": "operation_latency",
  "aggregation": "average"
}
```

### Get Real-time Telemetry

`GET /api/v0/wal/telemetry/realtime`

Retrieves real-time telemetry metrics with the most recent data.

#### Response

```json
{
  "success": true,
  "operation": "get_realtime_telemetry",
  "timestamp": 1714953237.4568963,
  "latency": {
    "add:ipfs": {
      "mean": 0.85,
      "median": 0.82,
      "min": 0.5,
      "max": 1.2,
      "percentile_95": 1.1,
      "count": 15
    }
  },
  "success_rate": {
    "add:ipfs": 0.9
  },
  "error_rate": {
    "add:ipfs": 0.1
  },
  "throughput": {
    "overall": 12.5
  },
  "status_distribution": {
    "add:ipfs": {
      "pending": 2,
      "processing": 1,
      "completed": 18,
      "failed": 2
    }
  }
}
```

### Generate Telemetry Report

`POST /api/v0/wal/telemetry/report`

Generates a comprehensive telemetry report with charts and visualizations.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_time` | float | Start time for time range filter (Unix timestamp) |
| `end_time` | float | End time for time range filter (Unix timestamp) |

#### Response

```json
{
  "success": true,
  "operation": "generate_telemetry_report",
  "timestamp": 1714953237.4568963,
  "report_path": "/home/user/.ipfs_kit/reports/report_1714953237_12345",
  "report_url": "http://localhost:8000/api/v0/wal/telemetry/reports/report_1714953237_12345/report.html",
  "message": "Report generation started in the background"
}
```

### Get Report File

`GET /api/v0/wal/telemetry/reports/{report_id}/{file_name}`

Retrieves a file from a previously generated telemetry report.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `report_id` | string | ID of the report |
| `file_name` | string | Name of the file to retrieve |

#### Response

The requested file is returned with the appropriate content type.

### Generate Visualization

`GET /api/v0/wal/telemetry/visualization/{metric_type}`

Generates a visualization of telemetry metrics with optional filtering.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `metric_type` | string | Type of metrics to visualize |
| `operation_type` | string | Filter by operation type |
| `backend` | string | Filter by backend type |
| `status` | string | Filter by operation status |
| `start_time` | float | Start time for time range filter (Unix timestamp) |
| `end_time` | float | End time for time range filter (Unix timestamp) |
| `width` | int | Chart width in inches (default: 12) |
| `height` | int | Chart height in inches (default: 8) |

#### Response

A PNG image of the visualization.

### Get Telemetry Configuration

`GET /api/v0/wal/telemetry/config`

Retrieves the current telemetry configuration.

#### Response

```json
{
  "success": true,
  "operation": "get_telemetry_config",
  "timestamp": 1714953237.4568963,
  "config": {
    "metrics_path": "~/.ipfs_kit/telemetry",
    "retention_days": 30,
    "sampling_interval": 60,
    "enable_detailed_timing": true,
    "operation_hooks": true
  }
}
```

### Update Telemetry Configuration

`POST /api/v0/wal/telemetry/config`

Updates telemetry configuration parameters.

#### Request Body

```json
{
  "enabled": true,
  "metrics_path": "~/.ipfs_kit/telemetry",
  "retention_days": 30,
  "sampling_interval": 60,
  "enable_detailed_timing": true,
  "operation_hooks": true
}
```

#### Response

```json
{
  "success": true,
  "operation": "update_telemetry_config",
  "timestamp": 1714953237.4568963,
  "config": {
    "metrics_path": "~/.ipfs_kit/telemetry",
    "retention_days": 30,
    "sampling_interval": 60,
    "enable_detailed_timing": true,
    "operation_hooks": true
  },
  "warning": "The following settings cannot be updated without restarting: metrics_path, operation_hooks"
}
```

## Metric Types

The telemetry system collects and provides the following types of metrics:

| Metric Type | Description |
|-------------|-------------|
| `operation_count` | Number of operations |
| `operation_latency` | Time between operation start and completion |
| `success_rate` | Proportion of operations that complete successfully |
| `error_rate` | Proportion of operations that fail |
| `backend_health` | Health status of storage backends |
| `throughput` | Number of operations processed per minute |
| `queue_size` | Size of the operation queue |
| `retry_count` | Number of retry attempts for operations |

## Aggregation Methods

The telemetry API supports the following aggregation methods:

| Aggregation | Description |
|-------------|-------------|
| `sum` | Sum of all values |
| `average` | Average of all values |
| `minimum` | Minimum value |
| `maximum` | Maximum value |
| `percentile_95` | 95th percentile value |
| `percentile_99` | 99th percentile value |
| `count` | Number of values |
| `rate` | Rate of values per second |

## Example Usage

Here's an example of using the telemetry API with Python:

```python
import requests
import time

# Get real-time telemetry
response = requests.get("http://localhost:8000/api/v0/wal/telemetry/realtime")
if response.status_code == 200:
    data = response.json()
    print(f"Latency metrics: {data.get('latency', {})}")
    print(f"Success rate: {data.get('success_rate', {})}")
    print(f"Error rate: {data.get('error_rate', {})}")
    print(f"Throughput: {data.get('throughput', {})}")

# Get filtered telemetry metrics
response = requests.get(
    "http://localhost:8000/api/v0/wal/telemetry/metrics",
    params={
        "metric_type": "operation_latency",
        "aggregation": "average"
    }
)
if response.status_code == 200:
    data = response.json()
    print(f"Filtered metrics: {data.get('metrics', {})}")

# Generate telemetry report
end_time = time.time()
start_time = end_time - 3600  # Last hour
response = requests.post(
    "http://localhost:8000/api/v0/wal/telemetry/report",
    data={
        "start_time": start_time,
        "end_time": end_time
    }
)
if response.status_code == 200:
    data = response.json()
    report_url = data.get("report_url")
    print(f"Report URL: {report_url}")
```

For a complete example, see the `examples/wal_telemetry_api_example.py` file in the IPFS Kit repository.

## Environment Variables

The telemetry system can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `IPFS_KIT_TELEMETRY_PATH` | Directory for telemetry metrics storage | `~/.ipfs_kit/telemetry` |
| `IPFS_KIT_TELEMETRY_RETENTION` | Number of days to retain metrics | `30` |
| `IPFS_KIT_TELEMETRY_INTERVAL` | Interval in seconds between metric samples | `60` |
| `IPFS_KIT_TELEMETRY_DETAILED` | Whether to collect detailed timing data | `true` |
| `IPFS_KIT_TELEMETRY_HOOKS` | Whether to install operation hooks | `true` |

## Integration with WAL System

The telemetry system is integrated with the WAL system through operation hooks, allowing it to automatically collect metrics as operations are processed. The following hooks are installed:

1. **Operation Start Hook**: Records the start of an operation when it is added to the WAL
2. **Status Change Hook**: Records status changes for operations (pending, processing, completed, failed)
3. **Backend Health Change Hook**: Records changes in backend health status

These hooks enable comprehensive monitoring of WAL operations without requiring explicit instrumentation in application code.

## Performance Impact

The telemetry system is designed to have minimal impact on WAL performance while still providing comprehensive metrics. Key performance considerations include:

1. **Async Metric Processing**: Metrics are processed asynchronously to avoid blocking WAL operations
2. **Efficient Storage**: Metrics are stored using Apache Arrow for efficient memory usage and disk IO
3. **Configurable Sampling**: The sampling interval is configurable to balance metric granularity and system load
4. **Retention Policy**: Old metrics are automatically cleaned up based on the configured retention period

For performance-critical deployments, the telemetry system can be configured with a longer sampling interval or disabled entirely.
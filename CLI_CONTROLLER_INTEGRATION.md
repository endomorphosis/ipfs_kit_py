# MCP Server CLI Controller Integration

This document describes the integration of the CLI functionality into the MCP (Model-Controller-Persistence) server for the ipfs_kit_py project.

## Overview

The CLI Controller provides an HTTP API interface to all the CLI tool functionality of ipfs_kit_py. This allows users to execute CLI commands through the MCP server's REST API, enabling remote management and automation of IPFS operations.

## Features

The CLI Controller provides the following features:

- **Command Execution**: Execute any supported CLI command remotely
- **Content Management**: Add, retrieve, pin, and unpin content
- **Peer Management**: Connect to peers and list connected peers
- **Filesystem Operations**: Check if files exist, list directory contents
- **WAL Integration**: Manage and monitor the Write-Ahead Log (WAL) system
- **Version Information**: Get version details for the system components

## Endpoints

The CLI Controller exposes the following endpoints:

### Core Commands

- `POST /cli/execute` - Execute a CLI command with arguments
- `GET /cli/version` - Get version information

### Content Management

- `POST /cli/add` - Add content to IPFS
- `GET /cli/cat/{cid}` - Retrieve content by CID
- `POST /cli/pin/{cid}` - Pin content to local node
- `POST /cli/unpin/{cid}` - Unpin content from local node
- `GET /cli/pins` - List pinned content

### IPNS Operations

- `POST /cli/publish/{cid}` - Publish CID to IPNS
- `GET /cli/resolve/{name}` - Resolve IPNS name to CID

### Network Operations

- `POST /cli/connect/{peer}` - Connect to a peer
- `GET /cli/peers` - List connected peers
- `GET /cli/network/info` - Get network configuration information
- `POST /cli/network/config` - Update network configuration
- `GET /cli/network/bootstrap/list` - List bootstrap nodes
- `POST /cli/network/bootstrap/add` - Add bootstrap node
- `POST /cli/network/bootstrap/remove` - Remove bootstrap node
- `POST /cli/network/bootstrap/reset` - Reset to default bootstrap nodes
- `GET /cli/network/addresses` - Get node addresses

### Credential Management

- `POST /cli/credential/add` - Add new service credentials
- `POST /cli/credential/remove` - Remove credentials
- `GET /cli/credential/list` - List available credentials

### Cluster Management

- `POST /cli/cluster/create` - Create a new IPFS cluster
- `POST /cli/cluster/join` - Join an existing cluster
- `POST /cli/cluster/leave` - Leave current cluster
- `GET /cli/cluster/peers` - List peers in the cluster
- `GET /cli/cluster/status` - Get cluster status
- `POST /cli/cluster/set-role` - Change node role in cluster
- `POST /cli/cluster/pin` - Pin content across cluster
- `POST /cli/cluster/unpin` - Unpin content across cluster
- `GET /cli/cluster/ls-pins` - List pins in the cluster

### Plugin Management

- `GET /cli/plugin/list` - List available plugins
- `POST /cli/plugin/enable` - Enable a plugin
- `POST /cli/plugin/disable` - Disable a plugin
- `POST /cli/plugin/register` - Register a new plugin

### Resource Management

- `GET /cli/resource/status` - Get resource usage status
- `POST /cli/resource/configure` - Configure resource management
- `GET /cli/resource/monitor` - Monitor resource usage
- `GET /cli/resource/allocate` - Get resource allocation recommendations

### Health Monitoring

- `GET /cli/health/check` - Run health check diagnostics
- `GET /cli/health/metrics` - Get system health metrics
- `POST /cli/health/monitor` - Enable continuous monitoring
- `GET /cli/health/diagnostic` - Run diagnostic tools

### Filesystem Operations

- `GET /cli/exists/{path}` - Check if a path exists
- `GET /cli/ls/{path}` - List contents of a directory
- `GET /cli/filesystem/tiered-cache/stats` - Get cache statistics
- `POST /cli/filesystem/tiered-cache/clear` - Clear cache contents
- `GET /cli/filesystem/journal-status` - Get journal status

### WebRTC Operations

- `GET /cli/webrtc/check-deps` - Check WebRTC dependencies
- `POST /cli/webrtc/stream` - Start WebRTC streaming
- `POST /cli/webrtc/multi-peer` - Create multi-peer WebRTC session
- `GET /cli/webrtc/status` - Get WebRTC stream status
- `GET /cli/webrtc/benchmark` - Run WebRTC benchmark

### SDK Generation

- `POST /cli/generate-sdk` - Generate client SDK for the API

### WAL Integration (When Available)

- `GET /cli/wal/status` - Get WAL status information
- `GET /cli/wal/list/{operation_type}` - List WAL operations by type
- `GET /cli/wal/show/{operation_id}` - Show details for a specific WAL operation
- `POST /cli/wal/retry/{operation_id}` - Retry a failed WAL operation
- `POST /cli/wal/cleanup` - Clean up old WAL operations
- `GET /cli/wal/metrics` - Get WAL metrics and performance statistics

### WAL Telemetry

- `POST /cli/telemetry/init` - Initialize WAL telemetry system
- `GET /cli/telemetry/metrics` - Get WAL telemetry metrics
  - Query parameters: `metric_type`, `aggregation`, `interval`, `operation`, `backend`, `since`, `watch`, `watch_interval`
- `POST /cli/telemetry/report` - Generate a telemetry report
  - Request body: `output`, `report_type`, `time_range`, `include_visualizations`, `open_browser`
- `GET /cli/telemetry/analyze/{metric_type}` - Analyze metrics for a specific type
  - Path parameter: `metric_type` (one of `operation_latency`, `success_rate`, `error_rate`, `throughput`, `queue_size`)
  - Query parameters: `operation`, `backend`, `days`, `output`

#### Prometheus Integration

- `POST /cli/telemetry/prometheus/start` - Start Prometheus metrics exporter
  - Request body: `port`, `address`, `metrics_path`
- `POST /cli/telemetry/prometheus/stop` - Stop Prometheus metrics exporter

#### Grafana Integration

- `POST /cli/telemetry/grafana/generate` - Generate a Grafana dashboard for WAL telemetry
  - Request body: `output`, `dashboard_title`, `prometheus_datasource`

#### Distributed Tracing

- `POST /cli/telemetry/tracing/init` - Initialize the distributed tracing system
  - Request body: `exporter_type`, `endpoint`, `service_name`
- `POST /cli/telemetry/tracing/start` - Start a new trace session
  - Request body: `session_name`, `correlate_with`
- `POST /cli/telemetry/tracing/stop/{session_name}` - Stop an active trace session
  - Path parameter: `session_name`
- `GET /cli/telemetry/tracing/export` - Export trace results
  - Query parameters: `output`, `format`, `session_name`
- `GET /cli/telemetry/tracing/visualize` - Generate a visualization for traces
  - Query parameters: `output`, `session_name`, `format`

## Usage Examples

### Python Client

```python
import requests
import json

# Base URL for MCP server
BASE_URL = "http://localhost:8000/api/v0/mcp"

# Execute a CLI command
response = requests.post(
    f"{BASE_URL}/cli/execute",
    json={
        "command": "add",
        "args": ["Hello, IPFS!"],
        "params": {"filename": "hello.txt"}
    }
)
result = response.json()
print(f"Add result: {result}")

# Get content
cid = result["result"]["Hash"]
response = requests.get(f"{BASE_URL}/cli/cat/{cid}")
content = response.content.decode('utf-8')
print(f"Retrieved content: {content}")

# Pin content
response = requests.post(f"{BASE_URL}/cli/pin/{cid}")
print(f"Pin result: {response.json()}")

# List pins
response = requests.get(f"{BASE_URL}/cli/pins")
pins = response.json()
print(f"Pins: {pins}")
```

### WAL Telemetry Examples

```python
import requests
import json

# Base URL for MCP server
BASE_URL = "http://localhost:8000/api/v0/mcp"

# Initialize telemetry system
response = requests.post(
    f"{BASE_URL}/cli/telemetry/init",
    json={
        "enabled": True,
        "aggregation_interval": 60,
        "max_history": 1000,
        "log_level": "INFO"
    }
)
print(f"Initialize telemetry result: {response.json()}")

# Get telemetry metrics
response = requests.get(
    f"{BASE_URL}/cli/telemetry/metrics",
    params={
        "metric_type": "operation_latency",
        "aggregation": "average",
        "since": "1h"
    }
)
metrics = response.json()
print(f"Metrics: {json.dumps(metrics, indent=2)}")

# Generate a telemetry report
response = requests.post(
    f"{BASE_URL}/cli/telemetry/report",
    json={
        "output": "/tmp/telemetry_report.html",
        "report_type": "detailed",
        "time_range": "day",
        "include_visualizations": True
    }
)
print(f"Report generation result: {response.json()}")

# Start Prometheus exporter
response = requests.post(
    f"{BASE_URL}/cli/telemetry/prometheus/start",
    json={
        "port": 9095,
        "address": "0.0.0.0",
        "metrics_path": "/metrics"
    }
)
print(f"Prometheus exporter start result: {response.json()}")

# Initialize distributed tracing
response = requests.post(
    f"{BASE_URL}/cli/telemetry/tracing/init",
    json={
        "exporter_type": "jaeger",
        "endpoint": "http://jaeger:14268/api/traces",
        "service_name": "ipfs-kit-wal"
    }
)
print(f"Tracing initialization result: {response.json()}")

# Start a tracing session
response = requests.post(
    f"{BASE_URL}/cli/telemetry/tracing/start",
    json={
        "session_name": "file-upload-trace"
    }
)
print(f"Trace session start result: {response.json()}")
```

### cURL Commands

```bash
# Add content
curl -X POST "http://localhost:8000/api/v0/mcp/cli/add" \
     -H "Content-Type: application/json" \
     -d '{"content": "Hello, IPFS!", "filename": "hello.txt"}'

# Get content
curl -X GET "http://localhost:8000/api/v0/mcp/cli/cat/QmXyz123"

# Get version information
curl -X GET "http://localhost:8000/api/v0/mcp/cli/version"

# Execute arbitrary command
curl -X POST "http://localhost:8000/api/v0/mcp/cli/execute" \
     -H "Content-Type: application/json" \
     -d '{"command": "pin", "args": ["QmXyz123"]}'
```

## Implementation Details

The CLI Controller is implemented in the `ipfs_kit_py/mcp/controllers/cli_controller.py` file and uses the following components:

1. **IPFSSimpleAPI**: From the high-level API to execute commands
2. **WAL Integration**: For WAL-related commands (when available)
3. **FastAPI Router**: To register HTTP endpoints
4. **IPFSModel**: For access to core IPFS functionality

The controller is registered with the MCP server in the `_init_components` method of the `MCPServer` class, making it available through the MCP server's API.

### Route Registration Pattern

Following the pattern established in the IPFS controller fixes, the CLI Controller should implement flexible route registration that supports both traditional path formats and simplified API paths. This approach ensures backward compatibility while providing a more intuitive API.

Here's how the route registration pattern should be applied:

```python
def register_routes(self, router: APIRouter):
    # Register original paths with traditional naming convention
    router.add_api_route(
        "/cli/command/execute",
        self.execute_command,
        methods=["POST"],
        response_model=CommandResponse
    )
    
    # Add simplified alias paths for the same endpoints
    router.add_api_route(
        "/cli/command",
        self.execute_command,
        methods=["POST"],
        response_model=CommandResponse,
        summary="Execute CLI command (alias)",
        description="Alias for /cli/command/execute"
    )
    
    # Register both formats for other endpoints
    router.add_api_route(
        "/cli/pin/add",
        self.pin_content,
        methods=["POST"]
    )
    
    # Alias for simplified API
    router.add_api_route(
        "/cli/pin",
        self.pin_content,
        methods=["POST"]
    )
    
    # And so on for other endpoints...
```

This pattern ensures that both traditional CLI-like paths (`/cli/pin/add`) and simplified REST-like paths (`/cli/pin`) work for the same functionality.

## Error Handling

The CLI Controller includes comprehensive error handling:

- All operations return a standard response format with success/error information
- Detailed error messages are provided for debugging
- Proper HTTP status codes for different error types
- Logging of all operations for troubleshooting

## Security Considerations

When exposing this API:

- Consider adding authentication to protect sensitive operations
- Use HTTPS to secure API traffic
- Implement rate limiting to prevent abuse
- Consider access control for different command types

## Testing

The CLI Controller integration can be tested with the included test script:

```bash
python test_mcp_cli.py
```

This will verify that the CLI Controller is properly registered with the MCP server and list all available routes.
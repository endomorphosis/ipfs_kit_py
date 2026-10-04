# Standalone gRPC Routing Server

This directory contains a standalone implementation of the gRPC routing server that provides optimized data routing capabilities without complex dependencies.

## Overview

The standalone gRPC server implements all the functionality defined in the routing service protocol buffer definition, including:

- **SelectBackend**: Choose the optimal backend for storing or retrieving content
- **RecordOutcome**: Record the results of a routing decision for continuous optimization
- **GetInsights**: Get analytics and insights about routing decisions
- **StreamMetrics**: Stream real-time metrics about the routing system

This standalone implementation is designed to work independently without requiring the full routing infrastructure, making it easier to deploy and test.

## Prerequisites

- Python 3.8+
- Required packages:
  - `grpcio`
  - `grpcio-tools`
  - `protobuf`

## Getting Started

### 1. Install Dependencies

```bash
pip install grpcio grpcio-tools protobuf
```

### 2. Generate gRPC Code

Before running the server, you need to generate the Python code from the protobuf definitions:

```bash
python bin/generate_grpc_code.py
```

### 3. Start the Server

```bash
python bin/run_standalone_grpc_server.py --host 0.0.0.0 --port 50051
```

#### Server Options

- `--host`: Host address to bind to (default: 0.0.0.0)
- `--port`: Port to listen on (default: 50051)
- `--workers`: Maximum number of worker threads (default: 10)
- `--use-ssl`: Use SSL/TLS for secure connections
- `--ssl-cert`: Path to SSL certificate file (required if --use-ssl is specified)
- `--ssl-key`: Path to SSL key file (required if --use-ssl is specified)
- `--log-level`: Logging level (default: INFO)

### 4. Test the Server

Use the test client to verify that the server is working correctly:

```bash
python bin/test_standalone_grpc_client.py --host localhost --port 50051
```

## Implementation Details

### SimpleRoutingManager

The standalone server uses a `SimpleRoutingManager` class that provides an in-memory implementation of the routing functionality:

- Manages backend selection based on content characteristics
- Records routing outcomes to improve future decisions
- Collects and aggregates metrics and insights
- Simulates real-world routing conditions

### SimpleRoutingDatabase

The server uses an in-memory database to store:
- Backend metrics and scores
- Routing history and outcomes
- Success rates and latency statistics

## API Documentation

### SelectBackend

Select the optimal backend for content storage or retrieval.

**Request Parameters:**
- `content_hash`: Optional content hash
- `content_type`: Content MIME type
- `content_size`: Content size in bytes
- `metadata`: Additional metadata
- `strategy`: Routing strategy
- `priority`: Routing priority
- `available_backends`: Available backends
- `client_location`: Client location

**Response:**
- `backend_id`: Selected backend
- `score`: Backend score
- `factor_scores`: Score breakdown by factor
- `alternatives`: Alternative backends

### RecordOutcome

Record the outcome of a routing decision.

**Request Parameters:**
- `backend_id`: Backend that was used
- `success`: Whether the operation was successful
- `content_hash`: Content hash
- `content_type`: Content MIME type
- `content_size`: Content size in bytes
- `duration_ms`: Operation duration in milliseconds
- `error`: Error message (if not successful)

**Response:**
- `success`: Whether the outcome was recorded
- `message`: Status message

### GetInsights

Get insights about routing decisions.

**Request Parameters:**
- `time_window_hours`: Optional time window in hours (default: 24)

**Response:**
- `factor_weights`: Factor weights
- `backend_scores`: Backend scores
- `backend_success_rates`: Success rates by backend
- `content_type_distribution`: Content type distribution
- `backend_usage_stats`: Backend usage statistics
- `latency_stats`: Latency statistics

### StreamMetrics

Stream routing metrics updates.

**Request Parameters:**
- `update_interval_seconds`: Update interval in seconds
- `metrics_types`: Types of metrics to stream
- `include_backends`: Whether to include backend metrics
- `include_content_types`: Whether to include content type metrics

**Response Stream:**
- `metrics`: Current metrics values
- `status`: System status

## Using with Other Languages

The gRPC interface can be used from any language that supports gRPC. To generate client code for other languages, use the protobuf definition in `ipfs_kit_py/routing/protos/routing.proto`.

### Example: Generate JavaScript Client

```bash
# Install required tools
npm install -g grpc-tools

# Generate JavaScript client code
grpc_tools_node_protoc --js_out=import_style=commonjs,binary:./js_client --grpc_out=grpc_js:./js_client --proto_path=./ipfs_kit_py/routing/protos routing.proto
```

## Troubleshooting

### Common Issues

1. **Import errors related to generated code**: Make sure you've run the code generation script.
2. **Server not starting**: Check for port conflicts or permission issues.

### Logs

Increase the log level for more detailed information:

```bash
python bin/run_standalone_grpc_server.py --log-level DEBUG
```
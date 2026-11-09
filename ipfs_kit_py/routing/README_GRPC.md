# gRPC Routing Service for IPFS Kit

This directory contains the gRPC implementation for the optimized data routing service in IPFS Kit. The gRPC interface provides a high-performance, language-independent way to access routing functionality from different applications and programming languages.

## Overview

The routing service provides intelligent content routing between different backend storage systems, optimizing for performance, cost, and reliability. The gRPC interface exposes the following operations:

- **SelectBackend**: Choose the optimal backend for storing or retrieving content
- **RecordOutcome**: Record the results of a routing decision for continuous optimization
- **GetInsights**: Get analytics and insights about routing decisions
- **StreamMetrics**: Stream real-time metrics about the routing system

## Prerequisites

- Python 3.8+
- `grpcio` and `grpcio-tools` packages
- JWT libraries for authentication (if using auth)

## Getting Started

### 1. Generate gRPC Code

Before using the gRPC server, you need to generate the Python code from the protobuf definitions:

```bash
python bin/generate_grpc_code.py
```

This will create the necessary modules in `ipfs_kit_py/routing/grpc/`.

### 2. Set Up Authentication (Optional)

If you want to use authentication, set up initial users:

```bash
# Initialize with a default admin user
python bin/manage_users.py init --users-file config/users.json

# Add more users
python bin/manage_users.py add --username service1 --role service --api-key --users-file config/users.json

# List users
python bin/manage_users.py list --users-file config/users.json
```

### 3. Start the gRPC Server

Start the server with the following command:

```bash
python bin/run_grpc_server.py --host 0.0.0.0 --port 50051
```

#### Server Options

- `--host`: Host address to bind to (default: 0.0.0.0)
- `--port`: Port to listen on (default: 50051)
- `--workers`: Maximum number of worker threads (default: 10)
- `--use-ssl`: Use SSL/TLS for secure connections
- `--ssl-cert`: Path to SSL certificate file (required if --use-ssl is specified)
- `--ssl-key`: Path to SSL key file (required if --use-ssl is specified)
- `--enable-auth`: Enable authentication and authorization
- `--jwt-secret`: JWT secret for authentication (required if --enable-auth is specified)
- `--users-file`: Path to users configuration file (optional, for authentication)
- `--log-level`: Logging level (default: INFO)

### 4. Test the gRPC Server

Use the test client to verify that the server is working correctly:

```bash
python bin/test_grpc_client.py --host localhost --port 50051
```

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
- `request_id`: Unique request ID
- `timestamp`: Request timestamp

**Response:**
- `backend_id`: Selected backend
- `score`: Backend score
- `factor_scores`: Score breakdown by factor
- `alternatives`: Alternative backends
- `request_id`: Original request ID
- `timestamp`: Response timestamp

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
- `timestamp`: Timestamp

**Response:**
- `success`: Whether the outcome was recorded
- `message`: Status message
- `timestamp`: Response timestamp

### GetInsights

Get insights about routing decisions.

**Request Parameters:**
- `backend_id`: Optional focus on specific backend
- `content_type`: Optional focus on specific content type
- `time_window_hours`: Optional time window in hours (default: 24)

**Response:**
- `factor_weights`: Factor weights
- `backend_scores`: Backend scores
- `backend_success_rates`: Success rates by backend
- `content_type_distribution`: Content type distribution
- `backend_usage_stats`: Backend usage statistics
- `latency_stats`: Latency statistics
- `timestamp`: Response timestamp

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
- `timestamp`: Update timestamp

## Using with Other Languages

The gRPC interface can be used from any language that supports gRPC. To generate client code for other languages, use the protobuf definition in `ipfs_kit_py/routing/protos/routing.proto`.

### Example: Generate JavaScript Client

```bash
# Install required tools
npm install -g grpc-tools

# Generate JavaScript client code
grpc_tools_node_protoc --js_out=import_style=commonjs,binary:./js_client --grpc_out=grpc_js:./js_client --proto_path=./ipfs_kit_py/routing/protos routing.proto
```

## Authentication

The gRPC server supports the following authentication methods:

1. **JWT Tokens**: Send the token in the `Authorization` header with the format `Bearer <token>`
2. **API Keys**: Send the API key in the `x-api-key` header
3. **Basic Auth**: Send username and password using HTTP Basic authentication

### Client Authentication Example (Python)

```python
import grpc
from ipfs_kit_py.routing.grpc_auth import secure_channel_credentials

# Create secure channel with JWT token
channel = grpc.secure_channel(
    "localhost:50051",
    secure_channel_credentials(jwt_token="your-jwt-token")
)

# Create secure channel with API key
channel = grpc.secure_channel(
    "localhost:50051",
    secure_channel_credentials(api_key="your-api-key")
)

# Create secure channel with Basic auth
channel = grpc.secure_channel(
    "localhost:50051",
    secure_channel_credentials(username="your-username", password="your-password")
)
```

## Troubleshooting

### Common Issues

1. **Import errors related to generated code**: Make sure you've run the code generation script.
2. **Authentication failures**: Check that the users file exists and contains the user you're trying to authenticate as.
3. **Server not starting**: Check for port conflicts or permission issues.

### Logs

The server logs can help diagnose issues. Increase the log level for more detailed information:

```bash
python bin/run_grpc_server.py --log-level DEBUG
```
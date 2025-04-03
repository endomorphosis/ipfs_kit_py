# API Reference

This document provides a complete reference for the IPFS Kit API, including both the High-Level API (`IPFSSimpleAPI`) and the REST API server.

## High-Level API Reference

The `IPFSSimpleAPI` class provides a simplified, user-friendly interface for common IPFS operations.

### Initialization

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize with default settings
api = IPFSSimpleAPI()

# Initialize with specific role and config file
api = IPFSSimpleAPI(config_path="~/.ipfs_kit/config.yaml", role="worker")

# Initialize with inline configuration
api = IPFSSimpleAPI(
    role="master",
    resources={"max_memory": "2GB", "max_storage": "100GB"},
    cache={"memory_size": "500MB", "disk_size": "5GB"},
    timeouts={"api": 60, "gateway": 120}
)
```

### Content Operations

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `add(content, pin=True, wrap_with_directory=False, **kwargs)` | Add content to IPFS | `content`: File path, string, or bytes<br>`pin`: Whether to pin the content<br>`wrap_with_directory`: Whether to wrap in a directory<br>`**kwargs`: Additional IPFS add options | Dictionary with keys:<br>- `success`: Boolean<br>- `cid`: Content identifier<br>- Other add-specific metadata |
| `get(cid, **kwargs)` | Retrieve content from IPFS | `cid`: Content identifier<br>`**kwargs`: Additional get options | Bytes containing the content |
| `pin(cid, recursive=True, **kwargs)` | Pin content to local node | `cid`: Content identifier<br>`recursive`: Whether to pin recursively<br>`**kwargs`: Additional pin options | Dictionary with keys:<br>- `success`: Boolean<br>- Operation metadata |
| `unpin(cid, recursive=True, **kwargs)` | Unpin content from local node | `cid`: Content identifier<br>`recursive`: Whether to unpin recursively<br>`**kwargs`: Additional unpin options | Dictionary with keys:<br>- `success`: Boolean<br>- Operation metadata |
| `list_pins(type="all", quiet=False, **kwargs)` | List pinned content | `type`: Pin type ("all", "recursive", "direct", "indirect")<br>`quiet`: Return only CIDs if True<br>`**kwargs`: Additional ls options | Dictionary with keys:<br>- `success`: Boolean<br>- `pins`: List or dict of pins |

### Filesystem-like Operations

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `open(cid, mode="rb")` | Open content as file-like object | `cid`: Content identifier<br>`mode`: File mode (only "rb" supported) | File-like object |
| `read(cid)` | Read entire content | `cid`: Content identifier | Bytes containing the content |
| `exists(cid)` | Check if content exists | `cid`: Content identifier | Boolean indicating existence |
| `ls(cid, detail=True, **kwargs)` | List directory contents | `cid`: Directory CID<br>`detail`: Return detailed information<br>`**kwargs`: Additional ls options | List of dictionaries with file information |

### IPNS Operations

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `publish(cid, key="self", lifetime="24h", ttl="1h", **kwargs)` | Publish content to IPNS | `cid`: Content identifier<br>`key`: IPNS key name<br>`lifetime`: IPNS record lifetime<br>`ttl`: IPNS record caching time<br>`**kwargs`: Additional publish options | Dictionary with keys:<br>- `success`: Boolean<br>- `ipns_name`: IPNS identifier<br>- Publication metadata |
| `resolve(ipns_name, recursive=True, **kwargs)` | Resolve IPNS name to CID | `ipns_name`: IPNS identifier<br>`recursive`: Resolve recursively<br>`**kwargs`: Additional resolve options | Dictionary with keys:<br>- `success`: Boolean<br>- `resolved_cid`: Resolved content identifier<br>- Resolution metadata |

### Peer Operations

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `connect(peer_addr)` | Connect to a peer | `peer_addr`: Peer multiaddress | Dictionary with keys:<br>- `success`: Boolean<br>- Connection metadata |
| `peers(verbose=False, latency=False, direction=False, **kwargs)` | List connected peers | `verbose`: Include detailed information<br>`latency`: Include latency information<br>`direction`: Include connection direction<br>`**kwargs`: Additional options | Dictionary with keys:<br>- `success`: Boolean<br>- `peers`: List of peer information<br>- `count`: Number of peers |

### Cluster Operations (Master/Worker Only)

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `cluster_add(content, replication_factor=1, name=None, **kwargs)` | Add content to cluster | `content`: File path, string, or bytes<br>`replication_factor`: Desired replication factor<br>`name`: Optional content name<br>`**kwargs`: Additional cluster add options | Dictionary with keys:<br>- `success`: Boolean<br>- `cid`: Content identifier<br>- Cluster-specific metadata |
| `cluster_pin(cid, replication_factor=1, name=None, **kwargs)` | Pin content to cluster | `cid`: Content identifier<br>`replication_factor`: Desired replication factor<br>`name`: Optional name<br>`**kwargs`: Additional cluster pin options | Dictionary with keys:<br>- `success`: Boolean<br>- `cid`: Content identifier<br>- Cluster-specific metadata |
| `cluster_status(cid=None, **kwargs)` | Get pin status in cluster | `cid`: Optional content identifier (all pins if None)<br>`**kwargs`: Additional status options | Dictionary with keys:<br>- `success`: Boolean<br>- `status`: Status information for pin(s) |
| `cluster_peers(**kwargs)` | List cluster peers | `**kwargs`: Additional peer list options | Dictionary with keys:<br>- `success`: Boolean<br>- `peers`: List of peer information |

### AI/ML Operations (Requires ai_ml extra)

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `ai_model_add(model, metadata, **kwargs)` | Add model to registry | `model`: ML model instance<br>`metadata`: Model metadata<br>`**kwargs`: Additional options | Dictionary with keys:<br>- `success`: Boolean<br>- `cid`: Model CID<br>- Model-specific metadata |
| `ai_model_get(model_cid, **kwargs)` | Get model from registry | `model_cid`: Model CID<br>`**kwargs`: Additional options | Dictionary with keys:<br>- `success`: Boolean<br>- `model`: ML model instance<br>- `metadata`: Model metadata |
| `ai_dataset_add(dataset, metadata, **kwargs)` | Add dataset to registry | `dataset`: Dataset object/dataframe<br>`metadata`: Dataset metadata<br>`**kwargs`: Additional options | Dictionary with keys:<br>- `success`: Boolean<br>- `cid`: Dataset CID<br>- Dataset-specific metadata |
| `ai_dataset_get(dataset_cid, **kwargs)` | Get dataset from registry | `dataset_cid`: Dataset CID<br>`**kwargs`: Additional options | Dictionary with keys:<br>- `success`: Boolean<br>- `dataset`: Dataset object<br>- `metadata`: Dataset metadata |
| `ai_metrics_visualize(model_id, metrics_type="all", theme="light", interactive=True, output_file=None)` | Generate metrics visualizations | `model_id`: Model identifier<br>`metrics_type`: Type of metrics<br>`theme`: Visualization theme<br>`interactive`: Use interactive charts<br>`output_file`: Output file path | Dictionary with keys:<br>- `success`: Boolean<br>- Visualization-specific metadata |

### Plugin System

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `register_extension(name, func)` | Register a custom extension | `name`: Extension name<br>`func`: Extension function | None |
| `call_extension(name, *args, **kwargs)` | Call an extension | `name`: Extension name<br>`*args`: Positional arguments<br>`**kwargs`: Keyword arguments | Return value of the extension function |

### SDK Generation

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `generate_sdk(language, output_dir="./sdk", **kwargs)` | Generate client SDK | `language`: Target language ("python", "javascript", "rust")<br>`output_dir`: Output directory<br>`**kwargs`: Additional options | Dictionary with keys:<br>- `success`: Boolean<br>- `language`: Target language<br>- `output_path`: Output directory path<br>- `files_generated`: List of generated files |

### Configuration Management

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `save_config(file_path)` | Save current configuration | `file_path`: Output file path | Dictionary with keys:<br>- `success`: Boolean<br>- `file_path`: Saved configuration path |

### Method Call Interface

The `IPFSSimpleAPI` class also implements a callable interface that allows dynamic method invocation:

```python
# Normal method call
result = api.add("example.txt")

# Callable interface
result = api("add", "example.txt")

# Extension call
result = api("StatisticsPlugin.get_stats")
```

## REST API Reference

The REST API server provides HTTP endpoints for interacting with IPFS Kit remotely. The API follows a consistent structure with all responses including a `success` flag.

### Server Configuration

```python
from ipfs_kit_py.api import run_server

# Start API server with default settings
run_server()

# Start with custom settings
run_server(
    host="0.0.0.0",             # Listen on all interfaces
    port=8000,                  # Port to listen on
    reload=True,                # Enable auto-reload for development
    workers=4,                  # Number of worker processes
    config_path="config.yaml",  # Load configuration from file
    log_level="info",           # Logging level
    auth_enabled=True,          # Enable authentication
    cors_origins=["*"]          # CORS allowed origins
)
```

### Base Endpoints

| Endpoint | Method | Description | Request Format | Response Format |
|----------|--------|-------------|----------------|-----------------|
| `/health` | GET | Health check | None | `{"status": "ok", "version": "x.y.z"}` |
| `/api/:method_name` | POST | Generic method caller | JSON with `args` and `kwargs` | Method-specific response with `success` flag |
| `/api/v0/openapi.json` | GET | OpenAPI schema | None | OpenAPI schema document |
| `/api/v0/docs` | GET | Interactive API docs | None | Swagger UI |
| `/api/v0/graphql` | POST | GraphQL endpoint | GraphQL query | GraphQL response |
| `/api/v0/graphql/playground` | GET | GraphQL IDE | None | GraphQL Playground UI |

### Content Endpoints

| Endpoint | Method | Description | Request Format | Response Format |
|----------|--------|-------------|----------------|-----------------|
| `/api/v0/add` | POST | Add content to IPFS | Multipart form with `file` and optional parameters | `{"success": true, "cid": "Qm...", "name": "filename", "size": 1234}` |
| `/api/v0/cat` | GET | Retrieve content | Query param: `arg` (CID) | Raw file content with appropriate Content-Type |
| `/api/v0/ls` | GET | List directory contents | Query param: `arg` (CID) | `{"success": true, "entries": [...]}` |

### Pin Management Endpoints

| Endpoint | Method | Description | Request Format | Response Format |
|----------|--------|-------------|----------------|-----------------|
| `/api/v0/pin/add` | POST | Pin content | JSON with `cid` and optional parameters | `{"success": true, "pins": ["Qm..."]}` |
| `/api/v0/pin/rm` | POST | Unpin content | JSON with `cid` and optional parameters | `{"success": true, "pins": ["Qm..."]}` |
| `/api/v0/pin/ls` | GET | List pinned content | Query params: `type`, `quiet` (optional) | `{"success": true, "pins": {...}}` |

### IPNS Endpoints

| Endpoint | Method | Description | Request Format | Response Format |
|----------|--------|-------------|----------------|-----------------|
| `/api/v0/name/publish` | POST | Publish to IPNS | JSON with `path` and optional parameters | `{"success": true, "name": "k2...", "value": "/ipfs/Qm..."}` |
| `/api/v0/name/resolve` | GET | Resolve IPNS name | Query param: `arg` (IPNS name) | `{"success": true, "path": "/ipfs/Qm..."}` |

### Peer Management Endpoints

| Endpoint | Method | Description | Request Format | Response Format |
|----------|--------|-------------|----------------|-----------------|
| `/api/v0/id` | GET | Get node identity | None | `{"success": true, "id": "Qm...", "addresses": [...]}` |
| `/api/v0/swarm/peers` | GET | List connected peers | Optional query parameters | `{"success": true, "peers": [...], "count": 42}` |
| `/api/v0/swarm/connect` | POST | Connect to peer | JSON with `addr` (multiaddress) | `{"success": true, "added": ["/ip4/..."]}` |

### Cluster Endpoints (Master/Worker Only)

| Endpoint | Method | Description | Request Format | Response Format |
|----------|--------|-------------|----------------|-----------------|
| `/api/v0/cluster/pins` | GET | List cluster pins | Optional query parameters | `{"success": true, "pins": [...]}` |
| `/api/v0/cluster/pin/add` | POST | Pin to cluster | JSON with `cid` and optional parameters | `{"success": true, "cid": "Qm...", "peers": [...]}` |
| `/api/v0/cluster/status` | GET | Get pin status | Query param: `arg` (CID, optional) | `{"success": true, "status": {...}}` |
| `/api/v0/cluster/peers` | GET | List cluster peers | None | `{"success": true, "peers": [...], "count": 5}` |

### AI/ML Endpoints (Requires ai_ml extra)

| Endpoint | Method | Description | Request Format | Response Format |
|----------|--------|-------------|----------------|-----------------|
| `/api/v0/ai/model/add` | POST | Add model | Multipart form with model file and metadata | `{"success": true, "cid": "Qm...", "metadata": {...}}` |
| `/api/v0/ai/model/get` | GET | Get model | Query param: `cid` | Model file with appropriate Content-Type |
| `/api/v0/ai/model/list` | GET | List models | Optional query parameters | `{"success": true, "models": [...]}` |
| `/api/v0/ai/dataset/add` | POST | Add dataset | Multipart form with dataset file and metadata | `{"success": true, "cid": "Qm...", "metadata": {...}}` |
| `/api/v0/ai/dataset/get` | GET | Get dataset | Query param: `cid` | Dataset file with appropriate Content-Type |
| `/api/v0/ai/metrics` | GET | Get metrics | Query params for model ID and metrics type | `{"success": true, "metrics": {...}}` |

### Error Handling

All API endpoints follow a consistent error response format:

```json
{
  "success": false,
  "error": "Detailed error message",
  "error_type": "ErrorClassName",
  "status_code": 400  // HTTP status code
}
```

Error types include:

| Error Type | HTTP Status | Description |
|------------|-------------|-------------|
| `IPFSConnectionError` | 503 | IPFS daemon connection issues |
| `IPFSTimeoutError` | 504 | IPFS operation timed out |
| `IPFSContentNotFoundError` | 404 | Content not found in IPFS |
| `IPFSValidationError` | 400 | Input validation failed |
| `IPFSConfigurationError` | 500 | Configuration issue |
| `IPFSPinningError` | 400 | Error during pinning operation |
| `IPFSError` | 400 | Generic IPFS error |
| `ValidationError` | 422 | Request validation failed |
| `AuthenticationError` | 401 | Authentication failed |
| `UnexpectedError` | 500 | Unexpected server error |

### Client Libraries

The API server is compatible with various HTTP client libraries:

#### Python

```python
import requests

# Add content
with open("example.txt", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v0/add",
        files={"file": f},
        data={"pin": "true"}
    )
result = response.json()
cid = result["cid"]

# Get content
response = requests.get(f"http://localhost:8000/api/v0/cat?arg={cid}")
content = response.content
```

#### JavaScript

```javascript
// Add content using fetch API
const formData = new FormData();
formData.append('file', new Blob(['Hello IPFS'], { type: 'text/plain' }), 'example.txt');
formData.append('pin', 'true');

fetch('http://localhost:8000/api/v0/add', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(result => {
  const cid = result.cid;
  console.log(`Added with CID: ${cid}`);
  
  // Get content
  return fetch(`http://localhost:8000/api/v0/cat?arg=${cid}`);
})
.then(response => response.text())
.then(content => {
  console.log(`Content: ${content}`);
});
```

#### cURL

```bash
# Add content
curl -X POST -F "file=@example.txt" -F "pin=true" http://localhost:8000/api/v0/add

# Get content
curl http://localhost:8000/api/v0/cat?arg=QmCID

# List pins
curl http://localhost:8000/api/v0/pin/ls
```

### WebSocket Support

The API server also supports WebSocket connections for real-time updates and subscriptions. WebSocket endpoints follow the same structure as REST endpoints but with persistent connections.

#### Subscription Endpoints

| Endpoint | Description | Subscription Format | Message Format |
|----------|-------------|---------------------|----------------|
| `/ws/v0/pubsub/:topic` | Subscribe to IPFS pubsub topics | None | `{"topic": "topic-name", "data": "base64-encoded-data", "from": "peer-id"}` |
| `/ws/v0/events` | Subscribe to system events | `{"events": ["pin", "unpin", "add"]}` | `{"event": "event-name", "data": {...}}` |

#### Example WebSocket Client

```javascript
// JavaScript WebSocket client
const ws = new WebSocket('ws://localhost:8000/ws/v0/pubsub/my-topic');

ws.onopen = () => {
  console.log('Connected to pubsub topic');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(`Received message: ${atob(message.data)}`);
};

// Publish to the topic
fetch('http://localhost:8000/api/v0/pubsub/pub', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    topic: 'my-topic',
    data: btoa('Hello WebSocket')
  })
});
```

## OpenAPI Schema

The REST API provides an OpenAPI schema at the `/api/v0/openapi.json` endpoint. This schema can be used with tools like Swagger UI, Postman, or code generators to create client libraries.

Access the interactive API documentation at `/api/v0/docs` when the server is running.

## GraphQL API

For more flexible querying, the API server also provides a GraphQL endpoint at `/api/v0/graphql`. This enables clients to request exactly the data they need in a single query.

Access the GraphQL Playground IDE at `/api/v0/graphql/playground` when the server is running.

### Example GraphQL Queries

```graphql
# Get node information and pins in one query
query {
  node {
    id
    version
    addresses
  }
  pins {
    cid
    type
    size
  }
}

# Add content and pin it in one mutation
mutation {
  add(content: "Hello GraphQL") {
    cid
    size
    pin {
      success
    }
  }
}
```

## Authentication

The API server supports several authentication methods:

1. **API Key**: Set `X-API-Key` header or `api_key` query parameter
2. **Bearer Token**: Set `Authorization: Bearer <token>` header
3. **Basic Auth**: Set `Authorization: Basic <base64-encoded-credentials>` header

Enable authentication by setting `auth_enabled=True` when starting the server and configuring authorized credentials in the configuration file.

### Example Authentication Configuration

```yaml
auth:
  enabled: true
  methods:
    - type: api_key
      keys:
        - key: your-api-key-here
          name: admin
          permissions: ["*"]
        - key: read-only-key
          name: reader
          permissions: ["cat", "ls", "get"]
    - type: bearer_token
      tokens:
        - token: your-token-here
          name: service-account
          permissions: ["*"]
    - type: basic_auth
      users:
        - username: admin
          password_hash: bcrypt-hashed-password
          permissions: ["*"]
```

## Rate Limiting

The API server supports rate limiting to prevent abuse. Rate limits can be configured globally or per endpoint.

### Example Rate Limit Configuration

```yaml
rate_limits:
  enabled: true
  default:
    requests: 100
    period: 60  # seconds
  endpoints:
    "/api/v0/add":
      requests: 20
      period: 60
    "/api/v0/cat":
      requests: 50
      period: 60
```

## Monitoring

The API server exports Prometheus metrics at the `/metrics` endpoint for monitoring server performance and usage.

Key metrics include:
- Request counts and latencies by endpoint
- Error rates by type
- Active connections
- Resource usage (memory, CPU)
- IPFS operation statistics

This enables integration with monitoring tools like Prometheus and Grafana for comprehensive observability.
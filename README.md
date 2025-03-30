# IPFS Kit

IPFS Kit is a comprehensive Python toolkit for working with IPFS (InterPlanetary File System) technologies. It provides a unified interface for IPFS operations, cluster management, tiered storage, and AI/ML integration.

This library installs and configures IPFS services through Kubo and IPFS Cluster based on the contents in the config file. It supports different node roles (master, worker, or leecher) and allows IPFS content to be accessed through multiple backends, including local IPFS node, IPFS Cluster, Storacha (previously Web3.Storage), and S3-compatible storage.

## Features

- **High-Level API**: Simplified interface with declarative configuration and plugin architecture
- **Role-based Architecture**: Configure nodes as master, worker, or leecher based on their purpose and resources
- **Tiered Storage**: Intelligently manage content across multiple storage backends with Adaptive Replacement Cache
- **Standard Filesystem Interface**: Use the FSSpec integration for filesystem-like access to IPFS content
- **Metadata Indexing**: Efficient Arrow-based metadata index with distributed synchronization for content discovery and search
- **Direct P2P Communication**: Establish direct peer connections using libp2p without requiring a full IPFS daemon
- **Advanced Cluster Management**: Sophisticated cluster coordination with role-based architecture, dynamic adaptation, and health monitoring
- **Web3.Storage Integration**: Access content through Storacha (Web3.Storage) as a fallback
- **S3 Compatibility**: Store and retrieve content using S3-compatible storage services
- **Comprehensive Error Handling**: Standardized error handling with detailed result dictionaries
- **High Performance**: Memory-mapped access to large files and optimized Unix socket support for low-latency local communications (2-3x faster than HTTP)
- **Arrow-Based Cluster State**: Zero-copy IPC for efficient state sharing across processes
- **Cross-Language Interoperability**: Share cluster state with C++, Rust, and other languages
- **Distributed Task Management**: Coordinate computational tasks across a cluster of nodes
- **AI/ML Integration**: Store, manage, and distribute ML models and datasets with content addressing
- **SDK Generation**: Generate SDKs for Python, JavaScript, and Rust for cross-language development

## Installation

### From PyPI (Recommended)

You can install IPFS Kit directly from PyPI with optional dependency groups:

```bash
# Basic installation with core functionality
pip install ipfs_kit_py

# With filesystem support (fsspec integration)
pip install ipfs_kit_py[fsspec]

# With Arrow integration for high-performance data operations
pip install ipfs_kit_py[arrow]

# With AI/ML support for model and dataset management
pip install ipfs_kit_py[ai_ml]

# With API server support (FastAPI-based HTTP server)
pip install ipfs_kit_py[api]

# Development installation with testing tools
pip install ipfs_kit_py[dev]

# Full installation with all dependencies
pip install ipfs_kit_py[full]
```

### From Source

For the latest development version or to contribute:

```bash
# Clone the repository
git clone https://github.com/endomorphosis/ipfs_kit_py
cd ipfs_kit_py

# Install in development mode with selected extras
pip install -e ".[fsspec,arrow]"

# Or install all dependencies for development
pip install -e ".[full,dev]"
```

### Docker Installation

For containerized deployment:

```bash
# Build the Docker image
docker build -t ipfs-kit-py .

# Run in master mode
docker run -d --name ipfs-master -p 5001:5001 -p 8080:8080 -v ipfs-data:/data ipfs-kit-py master

# Run in worker mode connected to master
docker run -d --name ipfs-worker --link ipfs-master -v ipfs-worker-data:/data ipfs-kit-py worker --master=ipfs-master:9096

# Run in leecher mode
docker run -d --name ipfs-leecher -p 5002:5001 -p 8081:8080 -v ipfs-leecher-data:/data ipfs-kit-py leecher
```

## Command-line Interface

IPFS Kit includes a comprehensive command-line interface for accessing all core functionality:

```bash
# Basic usage
ipfs-kit add example.txt              # Add a file to IPFS
ipfs-kit get QmCID                    # Get content from IPFS
ipfs-kit ls QmCID                     # List directory contents
ipfs-kit pin QmCID                    # Pin content to local node

# Core IPFS operations
ipfs-kit add --pin --wrap-with-directory file  # Add file with options
ipfs-kit get QmCID --output output.txt         # Save content to file
ipfs-kit cat QmCID                             # Display content to console
ipfs-kit list-pins                             # List pinned content
ipfs-kit unpin QmCID                           # Remove pin from local node
ipfs-kit stat QmCID                            # Display object stats

# Node and peer operations
ipfs-kit id                            # Show node identity information
ipfs-kit peers                         # List connected peers
ipfs-kit connect /ip4/1.2.3.4/tcp/4001 # Connect to a specific peer
ipfs-kit bootstrap list                # Show bootstrap peers
ipfs-kit bootstrap add /ip4/1.2.3.4    # Add bootstrap peer

# IPNS operations
ipfs-kit name publish QmCID           # Publish content to IPNS
ipfs-kit name resolve name            # Resolve IPNS name to CID
ipfs-kit key list                     # List IPNS keys
ipfs-kit key gen keyname              # Generate a new IPNS key

# Cluster operations (master/worker roles only)
ipfs-kit cluster-pin QmCID            # Pin content to cluster
ipfs-kit cluster-status QmCID         # Check pin status in cluster
ipfs-kit cluster-peers                # List cluster peers
ipfs-kit cluster-add example.txt      # Add file to cluster with replication

# Formatting options
ipfs-kit --format json ls QmCID       # Get results in JSON format
ipfs-kit --format yaml add file.txt   # Get results in YAML format

# Advanced settings
ipfs-kit --config path/to/config.yaml cmd  # Use custom configuration
ipfs-kit --timeout 60 get QmLargeFile      # Set longer timeout for large files
ipfs-kit --role worker add file.txt        # Explicitly set node role
```

### Global Command Options

| Option | Description |
|--------|-------------|
| `--help`, `-h` | Show help message |
| `--format` | Output format (json, yaml, table, text) |
| `--verbose`, `-v` | Enable verbose output |
| `--quiet`, `-q` | Suppress output |
| `--config` | Path to configuration file |
| `--timeout` | Operation timeout in seconds |
| `--role` | Node role (master, worker, leecher) |
| `--api-url` | Custom API URL |

### Environment Variables

The CLI respects the following environment variables:

- `IPFS_KIT_CONFIG`: Path to configuration file
- `IPFS_KIT_ROLE`: Node role (master, worker, leecher)
- `IPFS_KIT_API_URL`: Custom API URL
- `IPFS_KIT_TIMEOUT`: Default timeout in seconds
- `IPFS_KIT_FORMAT`: Default output format

## Quick Start

### Core API

```python
# Basic usage with core API
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with default settings
kit = ipfs_kit()

# Add a file to IPFS
result = kit.ipfs_add_file("example.txt")
cid = result.get("Hash")
print(f"Added file with CID: {cid}")

# Read content
content = kit.ipfs_cat(cid)
print(f"Content: {content}")

# Using the filesystem interface (requires fsspec)
fs = kit.get_filesystem()
with fs.open(cid, "rb") as f:
    data = f.read()
    print(f"Read {len(data)} bytes using filesystem interface")
```

### High-Level API

The High-Level API provides a simplified, user-friendly interface to IPFS operations with declarative configuration and built-in error handling.

```python
# Simplified usage with High-Level API
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize with declarative configuration
api = IPFSSimpleAPI(
    config_path="config.yaml",  # Optional: Load from YAML/JSON config
    role="worker",              # Override config settings
    timeouts={"api": 30}        # Custom timeout settings
)

# Content operations
# ------------------

# Add content with simplified API
result = api.add("example.txt")
cid = result["cid"]
print(f"Added file with CID: {cid}")

# Add content from string or bytes
result = api.add("Hello, IPFS!")   # Add string content
result = api.add(b"Binary data")   # Add binary content

# Get content - returns bytes
content = api.get(cid)
print(f"Content: {content}")

# File-like operations
# -------------------

# Use simplified filesystem methods
files = api.ls(cid)
print(f"Directory contents: {files}")

# Check if content exists
if api.exists(cid):
    print(f"Content {cid} exists in IPFS")

# Open files directly with context manager
with api.open(cid) as f:
    data = f.read()
    print(f"Read {len(data)} bytes")

# Read content directly
content = api.read(cid)

# Content management
# -----------------

# Pin content to local node
api.pin(cid)

# List pinned content
pins = api.list_pins()
print(f"Pinned content: {pins}")

# Unpin content
api.unpin(cid)

# IPNS operations
# --------------

# Publish content to IPNS
result = api.publish(cid, key="self")
ipns_name = result["Name"]
print(f"Published to IPNS: {ipns_name}")

# Resolve IPNS name to CID
resolved = api.resolve(ipns_name)
print(f"Resolved to: {resolved['Path']}")

# Peer operations
# -------------

# Connect to a peer
api.connect("/ip4/1.2.3.4/tcp/4001/p2p/QmPeerID")

# List connected peers
peers = api.peers()
print(f"Connected to {len(peers['Peers'])} peers")

# Cluster operations
# ----------------

# Only available in master or worker roles
if api.config.get("role") != "leecher":
    # Add content to cluster with replication
    result = api.cluster_add("example.txt", replication_factor=3)
    
    # Pin content to cluster
    api.cluster_pin(cid, replication_factor=3)
    
    # Check pin status in cluster
    status = api.cluster_status(cid)
    
    # List cluster peers
    cluster_peers = api.cluster_peers()

# Method call syntax options
# ------------------------

# Use direct method calls
api.add("example.txt")

# Or use the callable interface with method name string
api("add", "example.txt")

# Call plugin methods via extension syntax
api.call_extension("MyPlugin.custom_operation", arg1, arg2=value)

# Or use the shorthand callable syntax
api("MyPlugin.custom_operation", arg1, arg2=value)
```

#### Configuration Management

The High-Level API supports flexible configuration options:

```python
# Load from standard locations (tries in order):
# ./ipfs_config.yaml, ./ipfs_config.json, ~/.ipfs_kit/config.yaml, etc.
api = IPFSSimpleAPI()

# Load from specific file
api = IPFSSimpleAPI(config_path="/path/to/config.yaml")

# Override with parameters
api = IPFSSimpleAPI(
    role="worker",
    resources={"max_memory": "2GB", "max_storage": "100GB"},
    cache={"memory_size": "500MB", "disk_size": "5GB"},
    timeouts={"api": 60, "gateway": 120}
)

# Save current configuration to file
api.save_config("~/.ipfs_kit/my_config.yaml")
```

Sample configuration file (YAML):

```yaml
# Node role
role: worker

# Resource limits
resources:
  max_memory: 2GB
  max_storage: 100GB

# Cache settings
cache:
  memory_size: 500MB
  disk_size: 5GB
  disk_path: ~/.ipfs_kit/cache

# Timeouts
timeouts:
  api: 60
  gateway: 120
  peer_connect: 30

# Logging
logging:
  level: INFO
  file: ~/.ipfs_kit/logs/ipfs.log

# Plugins
plugins:
  - name: MetricsPlugin
    path: ipfs_kit_py.plugins.metrics
    enabled: true
    config:
      interval: 60
  - name: CustomPlugin
    path: my_package.plugins
    enabled: true
    config:
      setting1: value1
```

### API Server

IPFS Kit includes a FastAPI-based HTTP server that exposes all functionality via a RESTful API:

```python
# Start API server
from ipfs_kit_py.api import run_server

# Run on localhost:8000
run_server(host="127.0.0.1", port=8000)

# Advanced configuration
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

The API server provides:

- **OpenAPI Documentation**: Interactive Swagger UI at `/docs`
- **Authentication**: Optional token-based auth
- **CORS Support**: Cross-Origin Resource Sharing configuration
- **Health Checks**: Basic health monitoring endpoint at `/health`
- **Metrics**: Prometheus-compatible metrics at `/metrics`
- **API Versioning**: Support for multiple API versions

#### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v0/add` | POST | Add content to IPFS |
| `/api/v0/cat` | GET | Retrieve content by CID |
| `/api/v0/ls` | GET | List directory contents |
| `/api/v0/pin/add` | POST | Pin content to local node |
| `/api/v0/pin/rm` | POST | Unpin content |
| `/api/v0/pin/ls` | GET | List pinned content |
| `/api/v0/swarm/peers` | GET | List connected peers |
| `/api/v0/swarm/connect` | POST | Connect to a peer |
| `/api/v0/name/publish` | POST | Publish content to IPNS |
| `/api/v0/name/resolve` | GET | Resolve IPNS name to CID |
| `/api/v0/cluster/pins` | GET | List cluster pins |
| `/api/v0/cluster/pin/add` | POST | Pin content to cluster |
| `/api/v0/cluster/status` | GET | Get cluster pin status |

#### Client Connection Example

```python
import requests
import json

# Connect to API server
api_url = "http://localhost:8000"

# Add content to IPFS
with open("example.txt", "rb") as f:
    response = requests.post(
        f"{api_url}/api/v0/add",
        files={"file": f}
    )
result = response.json()
cid = result["Hash"]
print(f"Added content with CID: {cid}")

# Get content from IPFS
response = requests.get(
    f"{api_url}/api/v0/cat",
    params={"arg": cid}
)
content = response.content
print(f"Retrieved content: {content}")

# List directory contents
response = requests.get(
    f"{api_url}/api/v0/ls",
    params={"arg": cid}
)
files = response.json()
print(f"Directory contents: {json.dumps(files, indent=2)}")
```

For more examples, see the `examples/` directory.

## Advanced Features

### High-Level API with Plugin Architecture

The High-Level API provides a simplified interface to IPFS Kit with a powerful plugin system for extensibility:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI, PluginBase

# Create custom plugin
class MyPlugin(PluginBase):
    """Custom plugin with additional functionality."""
    
    def __init__(self, ipfs_kit, config=None):
        """Initialize plugin with configuration."""
        super().__init__(ipfs_kit, config)
        # Plugin-specific initialization
        self.custom_setting = config.get("setting", "default")
        self.counter = 0
    
    def custom_operation(self, param1, param2=None):
        """Perform custom operation."""
        # Access IPFS Kit through self.ipfs_kit
        result = self.ipfs_kit.ipfs_add("Custom operation result")
        self.counter += 1
        
        return {
            "success": True,
            "operation": "custom_operation",
            "param1": param1,
            "param2": param2,
            "counter": self.counter,
            "setting": self.custom_setting,
            "result_cid": result.get("Hash")
        }
    
    def advanced_operation(self, content, options=None):
        """More complex operation example."""
        options = options or {}
        
        # Process content using IPFS Kit capabilities
        if isinstance(content, str):
            # Add string content
            add_result = self.ipfs_kit.ipfs_add(content.encode('utf-8'))
        else:
            # Assume it's a file path
            add_result = self.ipfs_kit.ipfs_add_file(content)
            
        cid = add_result.get("Hash")
        
        # Pin if requested
        if options.get("pin", True):
            self.ipfs_kit.ipfs_pin_add(cid)
            
        # Publish to IPNS if requested
        ipns_result = None
        if options.get("publish"):
            ipns_result = self.ipfs_kit.ipfs_name_publish(
                cid, 
                key=options.get("key", "self")
            )
            
        return {
            "success": True,
            "operation": "advanced_operation",
            "cid": cid,
            "size": add_result.get("Size"),
            "pinned": options.get("pin", True),
            "ipns_name": ipns_result.get("Name") if ipns_result else None
        }

# Initialize API with plugin
api = IPFSSimpleAPI(plugins=[
    {
        "name": "MyPlugin",
        "path": "__main__",  # Current module
        "enabled": True,
        "config": {"setting": "custom_value"}
    }
])

# Call plugin methods
result = api.call_extension("MyPlugin.custom_operation", "test", param2="value")
# Or using the shorthand syntax
result = api("MyPlugin.custom_operation", "test", param2="value")

# Use more complex plugin operation
result = api("MyPlugin.advanced_operation", 
             "Important content to store", 
             {"pin": True, "publish": True})
```

#### Creating Reusable Plugins

Plugins can be developed as separate modules for reusability:

```python
# In my_plugins/content_processor.py
from ipfs_kit_py.high_level_api import PluginBase
import hashlib
import json

class ContentProcessorPlugin(PluginBase):
    """Plugin for advanced content processing."""
    
    def process_json(self, data, index=True):
        """Process and store JSON data with optional indexing."""
        # Convert to string if it's a dict
        if isinstance(data, dict):
            content = json.dumps(data)
        else:
            content = data
            
        # Add to IPFS
        result = self.ipfs_kit.ipfs_add(content.encode('utf-8'))
        cid = result.get("Hash")
        
        # Index the content if requested
        if index and hasattr(self.ipfs_kit, 'update_index'):
            # Calculate content hash for deduplication
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # Update index with metadata
            self.ipfs_kit.update_index(cid, {
                "content_type": "application/json",
                "content_hash": content_hash,
                "indexed_at": self.get_timestamp(),
                "size_bytes": len(content)
            })
            
        return {
            "success": True,
            "cid": cid,
            "indexed": index
        }
    
    def get_timestamp(self):
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()
```

Using the plugin:

```python
# Register the plugin
api = IPFSSimpleAPI(plugins=[
    {
        "name": "ContentProcessorPlugin",
        "path": "my_plugins.content_processor",
        "enabled": True
    }
])

# Process JSON data
data = {
    "name": "Example Dataset",
    "items": [1, 2, 3, 4, 5],
    "metadata": {
        "created_by": "user123",
        "version": "1.0"
    }
}

result = api("ContentProcessorPlugin.process_json", data)
print(f"Stored JSON with CID: {result['cid']}")
```

#### Plugin Discovery and Registration

The High-Level API can automatically discover and register plugins:

```python
# Auto-discover plugins in specified packages
api = IPFSSimpleAPI(
    discover_plugins=True,
    plugin_packages=["my_plugins", "ipfs_kit_py.plugins"]
)

# List available plugins
plugins = api.list_plugins()
for plugin in plugins:
    print(f"Plugin: {plugin['name']}")
    print(f"  Status: {'Enabled' if plugin['enabled'] else 'Disabled'}")
    print(f"  Methods: {', '.join(plugin['methods'])}")
    
# Enable/disable plugins at runtime
api.enable_plugin("MetricsPlugin")
api.disable_plugin("ContentProcessorPlugin")

# Register a plugin dynamically
api.register_plugin(
    name="DynamicPlugin",
    plugin_class=DynamicPlugin,
    config={"setting": "value"}
)
```

### Multi-Language SDK Generation

IPFS Kit can automatically generate client SDKs for multiple programming languages, making it easy to integrate with IPFS from any environment:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

# Generate Python SDK
result = api.generate_sdk("python", "/path/to/output")
print(f"Generated Python SDK with {len(result['files_generated'])} files")

# Generate JavaScript SDK
result = api.generate_sdk("javascript", "/path/to/output")
print(f"Generated JavaScript SDK with {len(result['files_generated'])} files")

# Generate Rust SDK
result = api.generate_sdk("rust", "/path/to/output")
print(f"Generated Rust SDK with {len(result['files_generated'])} files")
```

The SDK generation process automatically:

1. Creates appropriate project structure for each language
2. Generates client code with all available methods
3. Maps Python methods to idiomatic patterns in each language
4. Creates package configuration (setup.py, package.json, Cargo.toml)
5. Generates comprehensive documentation
6. Configures appropriate error handling for each language

#### Python SDK Usage Example

```python
from ipfs_kit_sdk import IPFSClient

# Initialize client with configuration
client = IPFSClient(api_url="http://localhost:8000")

# Add content to IPFS
result = client.add("Hello, IPFS!")
print(f"Added content with CID: {result['cid']}")

# Get content from IPFS
content = client.get(result['cid'])
print(f"Retrieved content: {content}")
```

#### JavaScript SDK Usage Example

```javascript
const { IPFSClient } = require('ipfs-kit-sdk');

// Initialize client
const client = new IPFSClient({
  apiUrl: 'http://localhost:8000'
});

// Add content to IPFS
async function addContent() {
  try {
    const result = await client.add("Hello, IPFS!");
    console.log(`Added content with CID: ${result.cid}`);
    
    // Get content from IPFS
    const content = await client.get(result.cid);
    console.log(`Retrieved content: ${content}`);
  } catch (error) {
    console.error(error);
  }
}

addContent();
```

#### Rust SDK Usage Example

```rust
use ipfs_kit_sdk::{Config, IPFSClient};
use anyhow::Result;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize client
    let config = Config {
        api_url: "http://localhost:8000".to_string(),
        ..Default::default()
    };
    let client = IPFSClient::with_config(config)?;
    
    // Add content to IPFS
    let content = "Hello, IPFS!";
    let result = client.add(content).await?;
    let cid = result["cid"].as_str().unwrap();
    println!("Added content with CID: {}", cid);
    
    // Get content from IPFS
    let retrieved = client.get(cid).await?;
    println!("Retrieved content: {}", retrieved);
    
    Ok(())
}
```

### Role-Based Architecture

IPFS Kit implements a specialized role-based architecture for distributed content management:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Master node - coordinates the entire content ecosystem
master = ipfs_kit(
    role="master",
    resources={"max_memory": "4GB", "max_storage": "500GB"},
    metadata={"cluster_name": "production", "organization": "example"}
)

# Worker node - focuses on processing power
worker = ipfs_kit(
    role="worker",
    resources={"max_memory": "2GB", "max_storage": "100GB"},
    metadata={"master_address": "/ip4/192.168.1.100/tcp/9096"}
)

# Leecher node - lightweight consumer
leecher = ipfs_kit(
    role="leecher",
    resources={"max_memory": "500MB", "max_storage": "10GB"},
    metadata={"offline_mode": True}
)
```

Each role has specialized optimizations:

**Master Node**:
- Full IPFS Cluster service for orchestration
- Complete DHT server mode for content routing
- Comprehensive content indexing
- Coordinates task distribution to workers

**Worker Node**:
- IPFS Cluster follower for distributed pinning
- Optimized for processing tasks
- Balanced storage and computation resources
- Can perform specialized tasks like embedding generation

**Leecher Node**:
- Minimal resource utilization
- Efficient client-only DHT mode
- Local caching for recently accessed content
- Optimized for bandwidth conservation

### Tiered Caching System

The library implements a high-performance multi-tier caching system using an Adaptive Replacement Cache (ARC) algorithm:

```python
from ipfs_kit_py.tiered_cache import TieredCacheManager

# Create a cache with custom configuration
cache = TieredCacheManager({
    'memory_cache_size': 500 * 1024 * 1024,  # 500MB memory cache
    'local_cache_size': 5 * 1024 * 1024 * 1024,  # 5GB disk cache
    'local_cache_path': '/tmp/ipfs_cache',
    'max_item_size': 100 * 1024 * 1024,  # 100MB max memory item size
    'min_access_count': 2  # Promote to memory after 2 accesses
})

# Store content in cache
cache.put("key1", b"content data", metadata={"source": "example"})

# Retrieve content (automatically handles tier selection)
content = cache.get("key1")
```

### FSSpec Filesystem Interface

IPFS Kit provides a high-performance FSSpec-compatible filesystem interface for IPFS content, allowing seamless integration with data science tools:

```python
import fsspec
import pandas as pd
from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem

# Basic usage with the fsspec registry
with fsspec.open("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", "r") as f:
    content = f.read()

# Use with pandas, pyarrow and other data tools
df = pd.read_csv("ipfs://QmCSVbfpQL6BjGog5c85xwsJ8arFiBg9ACdHF6RbqXegcV")

# Advanced configuration with performance optimizations
fs = IPFSFileSystem(
    # Enable Unix socket support for 2-3x faster local communication
    socket_path="/var/run/ipfs/api",  # Will be auto-detected if not specified
    
    # Configure multi-tier caching
    cache_config={
        'memory_cache_size': 500 * 1024 * 1024,  # 500MB memory cache
        'local_cache_size': 5 * 1024 * 1024 * 1024,  # 5GB disk cache
        'local_cache_path': '/tmp/ipfs_cache',
        'max_item_size': 100 * 1024 * 1024,  # Only cache files up to 100MB in memory
    },
    
    # Use memory mapping for large files
    use_mmap=True,
    
    # Configure which IPFS gateways to use as fallbacks
    gateway_urls=[
        "https://ipfs.io/ipfs/{cid}",
        "https://dweb.link/ipfs/{cid}",
        "https://cloudflare-ipfs.com/ipfs/{cid}"
    ],
    
    # Enable performance metrics collection
    metrics_config={
        'collection_interval': 60,
        'track_bandwidth': True,
        'track_latency': True
    }
)

# Standard filesystem operations
files = fs.ls("ipfs://QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn")
info = fs.info("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
content = fs.cat("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")

# Performance analysis
connection_report = fs.metrics.generate_connection_report()
print(connection_report)  # Detailed comparison of Unix socket vs HTTP performance

# Get performance recommendations
metrics = fs.metrics.analyze_metrics()
for recommendation in metrics["recommendations"]:
    print(f"Recommendation: {recommendation}")
```

The FSSpec integration provides:
- **Standard Filesystem Interface**: Familiar API for file operations
- **High-Performance Access**: Unix socket support for 2-3x faster local communication
- **Multi-tier Caching**: Adaptive Replacement Cache for optimal performance
- **Memory-Mapped Files**: Efficient access to large files
- **Gateway Fallback**: Automatic fallback to HTTP gateways
- **Performance Metrics**: Comprehensive performance tracking and analysis
- **Data Science Integration**: Seamless integration with pandas, pyarrow, and other tools

### Direct P2P Communication

IPFS Kit supports direct peer-to-peer communication using libp2p, enabling content exchange without requiring a full IPFS daemon:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.libp2p_peer import IPFSLibP2PPeer
from ipfs_kit_py.libp2p.ipfs_kit_integration import apply_ipfs_kit_integration

# Apply the integration to the IPFSKit class
apply_ipfs_kit_integration()

# Create an IPFSKit instance with libp2p enabled
kit = ipfs_kit()
fs = kit.get_filesystem(use_libp2p=True)

# Add content to IPFS
result = kit.ipfs_add_string("Hello, IPFS with direct P2P support!")
cid = result["Hash"]

# Retrieve content - this will automatically use libp2p if needed
content = fs.cat(cid)

# Or use the libp2p peer directly for more control
peer = IPFSLibP2PPeer(
    role="worker",
    listen_addrs=["/ip4/0.0.0.0/tcp/4001", "/ip4/0.0.0.0/udp/4001/quic"]
)

# Connect to another peer
peer.connect_peer("/ip4/192.168.1.100/tcp/4001/p2p/QmPeerID")

# Request content directly from connected peers
content = peer.request_content("QmContentCID")

# Announce available content to the network
peer.announce_content("QmLocalCID", metadata={"size": 1024})

# Start peer discovery
peer.start_discovery()
```

The enhanced direct P2P communication system provides:
- **Advanced DHT Discovery**: Improved peer discovery with k-bucket optimization for efficient routing
- **Provider Reputation Tracking**: Tracks reliability and performance of content providers
- **Intelligent Content Routing**: Uses network metrics to find optimal content providers
- **Cache Integration**: Seamlessly handles cache misses by retrieving directly from peers
- **Adaptive Backoff**: Implements backoff strategies for unreliable peers
- **Peer Discovery**: Find peers via DHT, mDNS, bootstrap nodes, and rendezvous points
- **Protocol Negotiation**: Dynamically negotiate communication protocols
- **NAT Traversal**: Reliable connectivity across network boundaries
- **PubSub Messaging**: Topic-based publish/subscribe for distributed coordination

For detailed documentation, see the [libp2p package README](ipfs_kit_py/libp2p/README.md).

### Advanced Cluster Management

IPFS Kit includes sophisticated cluster management capabilities that enable coordination across multiple nodes with different roles:

```python
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.cluster.role_manager import NodeRole, RoleManager
from ipfs_kit_py.cluster.distributed_coordination import ClusterCoordinator, MembershipManager
from ipfs_kit_py.cluster.monitoring import ClusterMonitor, MetricsCollector

# Create a master node and establish a cluster
def create_master_node():
    # Initialize components
    kit = IPFSKit(role="master")
    
    # Create role manager with dynamic role switching
    role_manager = RoleManager(
        initial_role="master",
        auto_detect=True,
        role_switching_enabled=True
    )
    
    # Set up monitoring
    metrics_collector = MetricsCollector(node_id="master-1")
    cluster_monitor = ClusterMonitor(
        node_id="master-1",
        metrics_collector=metrics_collector,
        alert_callback=lambda source, alert: print(f"ALERT: {alert['message']}")
    )
    
    # Create a new cluster
    cluster_coordinator = ClusterCoordinator(
        cluster_id="production-cluster",
        node_id="master-1",
        is_master=True
    )
    cluster_coordinator.create_cluster()
    
    return {
        "kit": kit,
        "role_manager": role_manager,
        "cluster_coordinator": cluster_coordinator,
        "cluster_monitor": cluster_monitor
    }

# Add a worker node to the cluster
def add_worker_node(cluster_id, master_address):
    # Initialize components
    kit = IPFSKit(role="worker")
    
    # Create role manager optimized for worker operations
    role_manager = RoleManager(
        initial_role="worker",
        auto_detect=True
    )
    
    # Join existing cluster
    cluster_coordinator = ClusterCoordinator(
        cluster_id=cluster_id,
        node_id="worker-1",
        is_master=False
    )
    cluster_coordinator.join_cluster(
        cluster_id=cluster_id,
        master_address=master_address
    )
    
    return {
        "kit": kit,
        "role_manager": role_manager,
        "cluster_coordinator": cluster_coordinator
    }

# Submit and track a task in the cluster
def run_distributed_task(master, task_data):
    # Submit task to the cluster
    task_id = master["cluster_coordinator"].submit_task(task_data)
    print(f"Submitted task with ID: {task_id}")
    
    # Monitor task progress
    status = master["cluster_coordinator"].get_task_status(task_id)
    print(f"Task status: {status['status']}")
    
    # Check cluster health
    health = master["cluster_monitor"].get_cluster_health()
    print(f"Cluster health: {health['status']}")
    
    return task_id
```

The cluster management system provides:

- **Role-Based Architecture**: 
  - **Master Nodes**: Orchestrate the entire content ecosystem and cluster operations
  - **Worker Nodes**: Process individual content items with optimized resource allocation
  - **Leecher Nodes**: Consume network resources with minimal contribution
  - **Gateway Nodes**: Provide HTTP gateway access with optimized serving capabilities
  - **Observer Nodes**: Monitor cluster health without participating in content processing

- **Dynamic Resource Adaptation**:
  - **Resource Trend Tracking**: Monitor resource usage patterns over time
  - **Smart Role Switching**: Automatically change roles based on available resources
  - **Fine-grained Adaptations**: Adjust parameters without requiring full role changes
  - **Role-Specific Optimizations**: Automatically optimize for each role's responsibilities

- **Distributed Coordination**:
  - **Membership Management**: Track which nodes are part of the cluster
  - **Leader Election**: Consensus-based selection of master nodes
  - **Task Distribution**: Intelligently assign tasks across worker nodes
  - **Peer Discovery**: Find and connect to other cluster nodes
  - **Task Handlers**: Register specialized handlers for different task types
  - **Configuration Consensus**: Propose and vote on configuration changes
  - **Comprehensive Metrics**: Detailed metrics collection and analysis

- **Health Monitoring**:
  - **Comprehensive Metrics**: Track performance and resource utilization
  - **Alert Generation**: Identify and report issues in real-time
  - **Health Checks**: Regular verification of node and cluster status
  - **Performance Analysis**: Detailed metrics for optimization

For full documentation, see the [cluster management README](ipfs_kit_py/cluster/README.md) and explore the examples at:
- [examples/cluster_management_example.py](examples/cluster_management_example.py): Basic cluster setup and usage
- [examples/cluster_advanced_example.py](examples/cluster_advanced_example.py): Advanced features including task handlers, configuration consensus, and detailed metrics

### Using Advanced Cluster Management Features

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize a master node
master = ipfs_kit(
    role="master",
    metadata={"enable_cluster_management": True}
)

# Register a task handler for specific task types
master.register_task_handler(
    task_type="image_processing",
    handler_func=lambda payload: {"success": True, "processed": True, "metadata": payload}
)

# Submit a task to the cluster
task_result = master.submit_cluster_task(
    task_type="image_processing",
    payload={"image_path": "path/to/image.jpg", "operations": ["resize", "optimize"]}
)
task_id = task_result.get("task_id")

# Check task status
status = master.get_task_status(task_id)
print(f"Task status: {status.get('status')}")

# Propose a configuration change to the cluster
config_result = master.propose_config_change(
    key="max_tasks_per_node",
    value=10
)
print(f"Configuration proposal: {config_result.get('success', False)}")

# Get comprehensive cluster metrics
metrics = master.get_cluster_metrics(include_history=True)
print(f"Cluster has {len(metrics.get('member_metrics', {})) + 1} nodes")
print(f"CPU utilization: {metrics.get('node_metrics', {}).get('cpu_percent', 'N/A')}%")
```

The tiered caching system provides:
- **Multi-tier Architecture**: Hierarchical caching with memory, disk, and memory-mapped tiers
- **Full Adaptive Replacement Cache (ARC)**: Advanced implementation with ghost lists for superior hit rates
- **Role-Optimized Caching**: Specialized cache configurations for master, worker, and leecher nodes
- **Zero-copy Access**: Memory-mapped file support for large content
- **Advanced Heat Scoring**: Sophisticated algorithm combining recency, frequency, and usage patterns
- **Ghost List Management**: Tracking of evicted items for smarter cache admission decisions
- **Automatic Adaptivity**: Self-tuning 'p' parameter that balances between recency and frequency based on workload
- **Rich Performance Metrics**: Comprehensive statistics for monitoring and optimizing cache performance

For detailed documentation, see [Tiered Cache System](docs/tiered_cache.md).

### Arrow-Based Metadata Index

IPFS Kit includes a powerful metadata indexing system built on Apache Arrow for efficient querying and discovery of IPFS content:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with metadata index enabled
kit = ipfs_kit(
    metadata={"enable_metadata_index": True}
)

# Get the metadata index
index = kit.get_metadata_index()

# Add a record to the index
record = {
    "cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx",
    "size_bytes": 1024,
    "mime_type": "text/plain",
    "filename": "example.txt",
    "metadata": {
        "title": "Example Document",
        "description": "This is a test document",
        "creator": "IPFS Kit"
    },
    "storage_locations": {
        "ipfs": {"pinned": True, "local": True},
        "ipfs_cluster": {"pinned": True, "replication_factor": 3},
        "s3": [{"provider": "aws", "region": "us-east-1", "bucket": "mybucket", "key": "example.txt"}]
    }
}
index.add_record(record)

# Query the index
results = index.query([
    ("mime_type", "==", "text/plain"),
    ("size_bytes", "<", 10000)
])

# Convert to pandas DataFrame
import pandas as pd
df = results.to_pandas()
print(df.head())

# Search for specific content
locations = index.find_content_locations(cid="QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
print(f"Found content in {len(locations['locations'])} locations")

# Synchronize with peers (master and worker nodes only)
if kit.role in ("master", "worker"):
    kit.sync_metadata_index()
    
    # Publish index to IPFS DAG for discovery
    result = kit.publish_metadata_index()
    print(f"Published index with DAG CID: {result.get('dag_cid')}")
```

The metadata index provides:

- **Efficient Columnar Storage**: Uses Apache Arrow for high-performance storage and querying
- **Parquet Persistence**: Durable storage using the Parquet file format
- **Distributed Synchronization**: Automatically share metadata between nodes using IPFS pubsub
- **Comprehensive Schema**: Rich metadata schema for detailed content tracking
- **Multi-location Tracking**: Track content across different storage systems (IPFS, S3, Filecoin, etc.)
- **PubSub Communication**: Real-time updates using IPFS pubsub
- **Content Discovery**: Find available storage locations for content retrieval
- **DAG-based Publishing**: Make metadata discoverable via IPLD DAGs
- **Zero-copy Access**: Efficiently share index data with other processes using Arrow C Data Interface
- **Role-based Synchronization**: Master and worker nodes participate in index distribution while leechers only consume

For detailed documentation, see [Metadata Index](docs/metadata_index.md).

### AI/ML Integration with IPFSDataLoader

IPFS Kit provides sophisticated tools for machine learning workflows with content-addressed storage:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with AI/ML integration enabled
kit = ipfs_kit(
    metadata={"enable_ai_ml": True}
)

# Get a data loader for ML workloads
loader = kit.get_data_loader(
    batch_size=64,
    shuffle=True,
    prefetch=4
)

# Load a dataset by CID
result = loader.load_dataset("QmDatasetCID")

# Iterate through batches
for batch in loader:
    # Each batch contains multiple samples
    for sample in batch:
        features = sample["features"]
        labels = sample["labels"]
        # Process the sample...

# Integration with PyTorch
torch_loader = loader.to_pytorch()
for features, labels in torch_loader:
    # Train model with PyTorch...

# Integration with TensorFlow
tf_dataset = loader.to_tensorflow()
for features, labels in tf_dataset.take(5):
    # Train model with TensorFlow...

# Clean up resources when done
loader.close()
```

The AI/ML integration features include:

- **Efficient DataLoader**: Optimized for machine learning workloads with batching and prefetching
- **ML Framework Integration**: Seamless integration with PyTorch and TensorFlow
- **Background Prefetching**: Asynchronous loading of batches for maximum throughput
- **Model Registry**: Content-addressed storage for ML models with versioning
- **Dataset Management**: Distributed dataset storage with content addressing
- **Distributed Training**: Coordinate training across multiple nodes in a cluster
- **Content Deduplication**: Efficient storage with automatic content deduplication

For detailed documentation, see [IPFS DataLoader](docs/ipfs_dataloader.md).

### Arrow-Based Cluster State Management

The library uses Apache Arrow for efficient, zero-copy cluster state management across processes:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py import cluster_state_helpers

# Master node creates and manages the cluster state
master_kit = ipfs_kit(role="master")

# Create a task
task_result = master_kit('create_task', 
                        task_type="model_training", 
                        parameters={"model": "resnet50", "epochs": 10})
task_id = task_result["task_id"]

# Check task status
status = master_kit('get_task_status', task_id=task_id)
print(f"Task status: {status['status']}")

# Access from external process
# Other Python processes can access the cluster state:
state_path = cluster_state_helpers.get_state_path_from_metadata()
cluster_info = cluster_state_helpers.get_cluster_status_summary(state_path)
print(f"Cluster has {cluster_info['nodes']['total']} nodes and {cluster_info['tasks']['total']} tasks")

# Find nodes with GPUs
gpu_nodes = cluster_state_helpers.find_nodes_with_gpu(state_path)
for node in gpu_nodes:
    print(f"Node {node['id']} has {node['resources']['gpu_count']} GPUs available")
```

#### Comprehensive Helper Functions

The `cluster_state_helpers.py` module provides a rich set of functions for querying and analyzing the cluster state:

##### Node Management
```python
# Find nodes by role
worker_nodes = cluster_state_helpers.find_nodes_by_role(state_path, "worker")

# Find nodes with specific capabilities
gpu_nodes = cluster_state_helpers.find_nodes_with_gpu(state_path)

# Get resource utilization metrics
for node in worker_nodes:
    node_id = node["id"]
    util = cluster_state_helpers.get_node_resource_utilization(state_path, node_id)
    print(f"Node {node_id} CPU utilization: {util['cpu_utilization']:.1%}")
```

##### Task Management
```python
# Find tasks by status
pending_tasks = cluster_state_helpers.find_tasks_by_status(state_path, "pending")

# Find tasks by resource requirements
gpu_tasks = cluster_state_helpers.find_tasks_by_resource_requirements(
    state_path, gpu_cores=1, memory_mb=4096
)

# Estimate task completion time
for task in pending_tasks:
    etc = cluster_state_helpers.estimate_time_to_completion(state_path, task["id"])
    print(f"Task {task['id']} estimated completion time: {etc:.1f} seconds")

# Find optimal node for a task
for task in pending_tasks:
    best_node = cluster_state_helpers.find_available_node_for_task(state_path, task["id"])
    if best_node:
        print(f"Best node for task {task['id']}: {best_node['id']}")
```

##### Content Management
```python
# Find orphaned content
orphaned = cluster_state_helpers.find_orphaned_content(state_path)
print(f"Found {len(orphaned)} orphaned content items")

# Map content to provider nodes
availability = cluster_state_helpers.get_content_availability_map(state_path)
for cid, providers in availability.items():
    print(f"Content {cid} available on {len(providers)} nodes")
```

##### Cluster Analysis
```python
# Get complete cluster summary
summary = cluster_state_helpers.get_cluster_status_summary(state_path)
print(f"Cluster CPU cores: {summary['resources']['cpu_cores']}")
print(f"Cluster GPU cores: {summary['resources']['gpu_cores']['total']}")
print(f"Available memory: {summary['resources']['memory_gb']['available']:.1f} GB")

# Analyze task execution performance
metrics = cluster_state_helpers.get_task_execution_metrics(state_path)
print(f"Task completion rate: {metrics['completion_rate']:.1%}")
print(f"Average execution time: {metrics['average_execution_time']:.1f} seconds")

# Export state for external analysis
cluster_state_helpers.export_state_to_json(state_path, "/tmp/cluster_state.json")
```

### Cross-Language Integration

The Arrow C Data Interface enables seamless interoperability with other languages without data copying:

```cpp
// C++ example using Arrow
#include <arrow/api.h>
#include <arrow/io/api.h>
#include <arrow/ipc/api.h>
#include <arrow/plasma/client.h>
#include <iostream>
#include <fstream>
#include <string>

using namespace arrow;

int main() {
    // Load state metadata from JSON file
    std::string metadata_path = "/path/to/cluster_state/state_metadata.json";
    std::ifstream metadata_file(metadata_path);
    if (!metadata_file) {
        std::cerr << "Could not open metadata file" << std::endl;
        return 1;
    }
    
    // Extract socket path and object ID from metadata
    // Connect to Plasma store
    std::shared_ptr<plasma::PlasmaClient> client = std::make_shared<plasma::PlasmaClient>();
    plasma::Status connect_status = client->Connect(socket_path);
    
    // Get the object buffer
    std::shared_ptr<Buffer> buffer;
    client->Get(&object_id, 1, -1, &buffer);
    
    // Create Arrow reader and get record batch
    auto buffer_reader = std::make_shared<io::BufferReader>(buffer);
    std::shared_ptr<ipc::RecordBatchReader> reader;
    ipc::RecordBatchReader::Open(buffer_reader, &reader);
    std::shared_ptr<RecordBatch> batch;
    reader->ReadNext(&batch);
    
    // Access node information
    auto nodes_array = std::static_pointer_cast<ListArray>(batch->column(3));
    int64_t num_nodes = nodes_array->length();
    std::cout << "Number of nodes: " << num_nodes << std::endl;
}
```

For complete documentation, see the [cluster state helpers documentation](docs/cluster_state_helpers.md).


# IPFS Huggingface Bridge:

for huggingface transformers python library visit:
https://github.com/endomorphosis/ipfs_transformers/

for huggingface datasets python library visit:
https://github.com/endomorphosis/ipfs_datasets/

for faiss KNN index python library visit:
https://github.com/endomorphosis/ipfs_faiss

for transformers.js visit:                          
https://github.com/endomorphosis/ipfs_transformers_js

for orbitdb_kit nodejs library visit:
https://github.com/endomorphosis/orbitdb_kit/

for ipfs_kit python library visit:
https://github.com/endomorphosis/ipfs_kit/

for ipfs_kit nodejs library visit:
https://github.com/endomorphosis/ipfs_kit_js/

for python model manager library visit: 
https://github.com/endomorphosis/ipfs_model_manager/

for nodejs model manager library visit: 
https://github.com/endomorphosis/ipfs_model_manager_js/

for nodejs ipfs huggingface scraper with pinning services visit:
https://github.com/endomorphosis/ipfs_huggingface_scraper/

for ipfs agents visit:
https://github.com/endomorphosis/ipfs_agents/

for ipfs accelerate visit:
https://github.com/endomorphosis/ipfs_accelerate/

# For Developers

## Building and Distribution

IPFS Kit follows modern Python packaging practices using `setuptools` and `pyproject.toml`. You can build the package using:

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the package
twine check dist/*

# Upload to TestPyPI (for testing)
twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Upload to PyPI (for real)
twine upload dist/*
```

## Development Environment

Setup a development environment:

```bash
# Clone the repository
git clone https://github.com/endomorphosis/ipfs_kit_py
cd ipfs_kit_py

# Create a virtual environment (optional)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[full]"

# Install development dependencies
pip install -r requirements.txt
```

## Running Tests

```bash
# Run all tests
python -m test.test

# Run a specific test
python -m test.test_ipfs_kit
python -m test.test_high_level_api
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

Author - Benjamin Barber  
QA - Kevin De Haan

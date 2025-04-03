# High-Level API (`IPFSSimpleAPI`)

The `IPFSSimpleAPI` class, found in `ipfs_kit_py/high_level_api.py`, provides a user-friendly, simplified interface for common IPFS operations. It abstracts away the complexity of the underlying components, making it the recommended entry point for most users.

## Key Features

-   **Simplified Interface:** Intuitive methods for common tasks like `add`, `get`, `pin`, `publish`, etc.
-   **Declarative Configuration:** Configure behavior using Python dictionaries, YAML files, JSON files, or environment variables
-   **Automatic Component Management:** Auto-initializes and manages underlying components based on configuration
-   **Built-in Error Handling:** Provides consistent error reporting with proper exception handling
-   **Plugin Architecture:** Extend functionality with custom plugins
-   **Multi-language SDK Generation:** Generate client SDKs for Python, JavaScript, and Rust
-   **File-like Interface:** Access IPFS content with familiar filesystem operations

## Initialization

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize with default settings (usually leecher role, default paths)
api = IPFSSimpleAPI()

# Initialize with specific role and config file
api = IPFSSimpleAPI(role="worker", config_path="~/.ipfs_kit/worker_config.yaml")

# Initialize with inline configuration overrides
api = IPFSSimpleAPI(
    role="master",
    timeouts={"api": 60, "gateway": 180},
    cache={"memory_size": "1GB"}
)

# Initialize with plugins
from my_plugins import MyCustomPlugin # Assuming you have a plugin
api = IPFSSimpleAPI(
    plugins=[
        {"name": "MyCustomPlugin", "plugin_class": MyCustomPlugin, "config": {"key": "value"}}
    ]
)
```

## Configuration System

The `IPFSSimpleAPI` uses a layered configuration system with multiple sources:

1.  **Defaults:** Built-in default configuration values
2.  **Config File:** YAML or JSON file from `config_path` or standard locations
3.  **Environment Variables:** Variables like `IPFS_KIT_ROLE` and `IPFS_KIT_API_URL`
4.  **Initialization Arguments:** Keyword arguments passed during initialization (override all other sources)

### Configuration File Example (YAML)

```yaml
# Node role (master, worker, leecher)
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
  use_mmap: true

# Connection timeouts
timeouts:
  api: 60
  gateway: 120
  peer_connect: 30

# Logging
logging:
  level: INFO
  file: ~/.ipfs_kit/logs/ipfs.log

# IPFS daemon settings 
ipfs_path: ~/.ipfs
socket_path: /var/run/ipfs/api.sock

# Plugins
plugins:
  - name: MetricsPlugin
    path: ipfs_kit_py.plugins.metrics
    enabled: true
    config:
      interval: 60
```

### Accessing Configuration

You can access the merged configuration via the `config` attribute:

```python
# Check current role
role = api.config.get("role")
print(f"Running in {role} mode")

# Check API timeout
timeout = api.config.get("timeouts", {}).get("api", 30)
print(f"API timeout: {timeout} seconds")

# Save current configuration
api.save_config("~/.ipfs_kit/my_config.yaml")
```

## Core Operations

The High-Level API provides an intuitive interface for common operations, grouped by category:

### Content Operations

```python
# Add content to IPFS
# ==================

# Add file from path
result = api.add("my_document.txt")
cid = result["cid"]
print(f"Added file with CID: {cid}")

# Add string content
text_result = api.add("Hello, IPFS!")
text_cid = text_result["cid"]

# Add binary content
binary_result = api.add(b"\x00\x01\x02\x03")
binary_cid = binary_result["cid"]

# Add with options
result = api.add("large_file.zip", 
                 pin=True,              # Pin content (default: True)
                 wrap_with_directory=True,  # Wrap with directory
                 chunker="size-1048576",    # Use larger chunks (1MB)
                 hash="sha2-512")           # Use SHA-512 hash

# Get content from IPFS
# ===================

# Get content (returns bytes)
content = api.get(cid)
print(f"Retrieved {len(content)} bytes")

# Convert bytes to string if needed
if isinstance(content, bytes):
    text_content = content.decode('utf-8')
    print(f"Content: {text_content}")
```

### Filesystem-like Operations

```python
# Open and read file (file-like API)
# =================================

# Open with context manager
with api.open(cid, mode="rb") as f:
    # Read first 1KB
    first_kb = f.read(1024)
    print(f"First 1KB: {first_kb}")
    
    # Read next 1KB
    next_kb = f.read(1024)
    
    # Seek to beginning and read all
    f.seek(0)
    all_data = f.read()

# Read entire file content directly
full_content = api.read(cid)

# Check if content exists
# =====================

if api.exists(cid):
    print(f"Content {cid} exists in IPFS")
else:
    print(f"Content {cid} does not exist or is not reachable")

# List directory contents
# =====================

# Simple listing (CID must be a directory)
files = api.ls(cid)
print(f"Directory contains {len(files)} files/directories")

# Detailed listing
files = api.ls(cid, detail=True)  
for file in files:
    print(f"Type: {file['type']}, Name: {file['name']}, Size: {file.get('size', 'N/A')}")
```

### Pinning Operations

```python
# Pin content locally
# =================

# Pin content to local node
api.pin(cid)

# Pin with options
api.pin(cid, recursive=True)  # Pin recursively (default)

# List pins
# ========

# Get all pins
pins = api.list_pins()
print(f"Number of pins: {len(pins.get('Keys', {}))}")

# Get pins of specific type
recursive_pins = api.list_pins(type="recursive")
direct_pins = api.list_pins(type="direct")
indirect_pins = api.list_pins(type="indirect")

# List only CIDs
simple_pins = api.list_pins(quiet=True)

# Unpin content
# ===========

# Unpin from local node
api.unpin(cid)

# Unpin with options
api.unpin(cid, recursive=True)  # Unpin recursively (default)
```

### IPNS Operations

```python
# Publish content to IPNS
# =====================

# Publish using default key ("self")
publish_result = api.publish(cid)
ipns_name = publish_result["ipns_name"]
print(f"Published to IPNS: {ipns_name}")

# Publish with custom key and options
publish_result = api.publish(
    cid,
    key="my-custom-key",  # Use custom key (must exist)
    lifetime="48h",       # Record valid for 48 hours
    ttl="2h"              # Cache for 2 hours
)

# Resolve IPNS name to CID
# ======================

# Resolve IPNS name
resolved = api.resolve(ipns_name)
resolved_cid = resolved["resolved_cid"]
print(f"Resolved {ipns_name} to {resolved_cid}")

# Resolve with options
resolved = api.resolve(
    ipns_name,
    recursive=True,   # Resolve recursively (default)
    timeout=60        # Longer timeout for resolution
)
```

### Peer Operations

```python
# Connect to peers
# ==============

# Connect to a peer by multiaddress
api.connect("/ip4/1.2.3.4/tcp/4001/p2p/QmPeerID")

# Get connected peers
# =================

# List connected peers
peers_result = api.peers()
peer_count = peers_result.get("count", 0)
print(f"Connected to {peer_count} peers")

# Get detailed peer information
peers_result = api.peers(verbose=True, latency=True, direction=True)
for peer in peers_result.get("peers", []):
    print(f"Peer: {peer.get('peer')}")
    print(f"  Latency: {peer.get('latency', 'unknown')}")
    print(f"  Direction: {peer.get('direction', 'unknown')}")
```

### Cluster Operations (Master/Worker Only)

```python
# These operations are only available in master or worker roles
if api.config.get("role") != "leecher":
    try:
        # Add content to cluster (with replication)
        # =====================================
        
        cluster_add_result = api.cluster_add(
            "important_file.dat",
            replication_factor=3,  # Replicate across 3 nodes
            name="Important Document"  # Optional name
        )
        cluster_cid = cluster_add_result.get("cid")
        
        # Pin existing content to cluster
        # ============================
        
        api.cluster_pin(
            cid,
            replication_factor=3,
            name="Existing Content"
        )
        
        # Check pin status in cluster
        # =========================
        
        # Check specific CID status
        status = api.cluster_status(cid)
        print(f"Status for {cid}: {status.get('status')}")
        
        # Check all pins status
        all_status = api.cluster_status()
        for pin_cid, pin_info in all_status.get("pins", {}).items():
            print(f"CID: {pin_cid}, Status: {pin_info.get('status')}")
            
        # List cluster peers
        # ===============
        
        cluster_peers = api.cluster_peers()
        for peer in cluster_peers.get("peers", []):
            print(f"Peer: {peer.get('id')}")
            print(f"  Addresses: {peer.get('addresses')}")
            
    except Exception as e:
        print(f"Cluster operation failed: {e}")
```

### AI/ML Operations

```python
# These operations are only available if ai_ml_integration is imported
try:
    # Add a machine learning model to the registry
    # ========================================
    
    # Create or load a model
    from sklearn.ensemble import RandomForestClassifier
    model = RandomForestClassifier()
    model.fit([[0, 0], [1, 1]], [0, 1])  # Simple dummy training
    
    # Add to registry with metadata
    model_result = api.ai_model_add(
        model,
        metadata={
            "name": "Simple Classifier",
            "version": "1.0.0",
            "framework": "scikit-learn",
            "accuracy": 0.95,
            "created_by": "user123"
        }
    )
    model_cid = model_result.get("cid")
    print(f"Model saved with CID: {model_cid}")
    
    # Get a model from the registry
    # ==========================
    
    model_get_result = api.ai_model_get(model_cid)
    loaded_model = model_get_result.get("model")
    model_metadata = model_get_result.get("metadata")
    
    # Make a prediction with the loaded model
    prediction = loaded_model.predict([[2, 2]])
    print(f"Prediction: {prediction}")
    
    # Add a dataset to the registry
    # ==========================
    
    import pandas as pd
    dataset = pd.DataFrame({
        'feature1': [1, 2, 3, 4, 5],
        'feature2': [5, 4, 3, 2, 1],
        'target': [0, 0, 1, 1, 0]
    })
    
    dataset_result = api.ai_dataset_add(
        dataset,
        metadata={
            "name": "Sample Dataset",
            "version": "1.0.0",
            "rows": len(dataset),
            "columns": list(dataset.columns),
            "description": "A simple example dataset"
        }
    )
    dataset_cid = dataset_result.get("cid")
    print(f"Dataset saved with CID: {dataset_cid}")
    
    # Get a dataset from the registry
    # ===========================
    
    dataset_get_result = api.ai_dataset_get(dataset_cid)
    loaded_dataset = dataset_get_result.get("dataset")
    dataset_metadata = dataset_get_result.get("metadata")
    
    # Use the loaded dataset
    print(f"Loaded dataset with {len(loaded_dataset)} rows")
    
except ImportError:
    print("AI/ML integration not available")
```

## Plugin Architecture

The `IPFSSimpleAPI` can be extended with plugins that add custom functionality. Plugins are Python classes that inherit from `PluginBase` and register their methods with the API.

### Developing a Plugin

```python
from ipfs_kit_py.high_level_api import PluginBase

class StatisticsPlugin(PluginBase):
    """Plugin for collecting IPFS statistics."""
    
    plugin_name = "Statistics"  # Optional name (defaults to class name)
    
    def __init__(self, ipfs_kit, config=None):
        """Initialize the plugin."""
        super().__init__(ipfs_kit, config)
        # Plugin-specific initialization
        self.stats = {"operations": {}}
        self.config = config or {}
        self.collection_interval = self.config.get("collection_interval", 60)
    
    def get_node_stats(self):
        """Get current node statistics."""
        # Access the underlying ipfs_kit instance
        node_info = self.ipfs_kit.ipfs_id()
        repo_stats = self.ipfs_kit.ipfs_repo_stat()
        
        # Compile statistics
        stats = {
            "node_id": node_info.get("ID"),
            "repo_size": repo_stats.get("RepoSize"),
            "num_objects": repo_stats.get("NumObjects"),
            "version": node_info.get("AgentVersion"),
            "collection_time": time.time()
        }
        
        return {
            "success": True,
            "stats": stats
        }
    
    def track_operation(self, operation_name, duration=None, metadata=None):
        """Track an operation for statistics."""
        if operation_name not in self.stats["operations"]:
            self.stats["operations"][operation_name] = {
                "count": 0,
                "total_duration": 0,
                "min_duration": float('inf'),
                "max_duration": 0
            }
            
        op_stats = self.stats["operations"][operation_name]
        op_stats["count"] += 1
        
        if duration is not None:
            op_stats["total_duration"] += duration
            op_stats["min_duration"] = min(op_stats["min_duration"], duration)
            op_stats["max_duration"] = max(op_stats["max_duration"], duration)
            
        return {
            "success": True,
            "operation": operation_name,
            "stats": op_stats
        }
    
    def reset_stats(self):
        """Reset all statistics."""
        old_stats = self.stats.copy()
        self.stats = {"operations": {}}
        
        return {
            "success": True,
            "previous_stats": old_stats
        }
```

### Using a Plugin

```python
from my_plugins import StatisticsPlugin

# Method 1: Register during initialization
api = IPFSSimpleAPI(plugins=[
    {"plugin_class": StatisticsPlugin, "config": {"collection_interval": 30}}
])

# Method 2: Register after initialization
stats_plugin = StatisticsPlugin(api.kit, {"collection_interval": 30})
api.register_extension("Statistics.get_node_stats", stats_plugin.get_node_stats)
api.register_extension("Statistics.track_operation", stats_plugin.track_operation)
api.register_extension("Statistics.reset_stats", stats_plugin.reset_stats)

# Call plugin methods
node_stats = api("Statistics.get_node_stats")
print(f"Node ID: {node_stats['stats']['node_id']}")
print(f"Repo size: {node_stats['stats']['repo_size']}")

# Track an operation
api("Statistics.track_operation", "add_file", duration=0.5)

# Alternative method call syntax
api.call_extension("Statistics.track_operation", "get_file", duration=0.2)

# Reset statistics
api("Statistics.reset_stats")
```

## SDK Generation

The `IPFSSimpleAPI` can generate client SDKs for different languages, making it easy to integrate with other systems.

```python
# Generate Python SDK
python_sdk = api.generate_sdk("python", output_dir="./sdk")
print(f"Python SDK generated in {python_sdk['output_path']}")
print(f"Files generated: {python_sdk['files_generated']}")

# Generate JavaScript SDK
js_sdk = api.generate_sdk("javascript", output_dir="./sdk")
print(f"JavaScript SDK generated in {js_sdk['output_path']}")

# Generate Rust SDK
rust_sdk = api.generate_sdk("rust", output_dir="./sdk")
print(f"Rust SDK generated in {rust_sdk['output_path']}")
```

### Using Generated SDKs

#### Python SDK

```python
from ipfs_kit_sdk import IPFSClient

# Initialize client
client = IPFSClient(api_url="http://localhost:8000")

# Add content
result = client.add("Hello from Python SDK!")
cid = result["cid"]

# Get content
content = client.get(cid)
print(f"Retrieved: {content}")
```

#### JavaScript SDK

```javascript
const { IPFSClient } = require('ipfs-kit-sdk');

// Initialize client
const client = new IPFSClient({
  apiUrl: "http://localhost:8000"
});

// Add content
async function addAndRetrieve() {
  const result = await client.add("Hello from JavaScript SDK!");
  const cid = result.cid;
  console.log(`Added with CID: ${cid}`);
  
  // Get content
  const content = await client.get(cid);
  console.log(`Retrieved: ${content}`);
}

addAndRetrieve();
```

#### Rust SDK

```rust
use ipfs_kit_sdk::IPFSClient;
use anyhow::Result;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize client
    let client = IPFSClient::new()?;
    
    // Add content
    let result = client.add("Hello from Rust SDK!").await?;
    let cid = result["cid"].as_str().unwrap();
    println!("Added with CID: {}", cid);
    
    // Get content
    let content = client.get(cid).await?;
    println!("Retrieved: {}", content);
    
    Ok(())
}
```

## Method Call Interface

The `IPFSSimpleAPI` supports both direct method calls and a callable interface for dynamic method invocation:

```python
# Method 1: Direct method call
result1 = api.add("example.txt")

# Method 2: Callable interface
result2 = api("add", "example.txt")

# Method 3: Extension call
result3 = api("Statistics.get_node_stats")
```

This callable interface is particularly useful for:

1. **Configuration-driven workflows**: Method names can be stored in configuration
2. **Dynamic execution**: Method choice can be determined at runtime
3. **Plugin integration**: Consistent interface for both core and plugin methods
4. **Remote API clients**: Simplifies remote method invocation

## Relationships and Integration

The `IPFSSimpleAPI` integrates with other components in the IPFS Kit ecosystem:

1. **Core `ipfs_kit`**: Manages an instance internally for low-level operations
2. **FSSpec Interface**: Provides filesystem-like access to IPFS content
3. **Plugins**: Extends functionality through the plugin system
4. **Configuration**: Centralizes configuration across components

You can access these components directly when needed:

```python
# Access underlying ipfs_kit instance
kit_instance = api.kit

# Access filesystem interface
fs_interface = api.fs

# Access plugins
plugin = api.plugins.get("Statistics")

# Access configuration
config = api.config
```

## Best Practices

1. **Use the High-Level API as your primary interface** - It provides the most user-friendly experience
2. **Leverage configuration files** - Store environment-specific settings in YAML/JSON
3. **Use context managers for file operations** - Ensures proper resource cleanup
4. **Handle errors with try/except** - The API raises exceptions for error conditions
5. **Consider role-based configurations** - Create separate configs for master/worker/leecher
6. **Use plugins for custom functionality** - Keeps code organized and modular
7. **Monitor performance through the API** - Track operations and resource usage

## Complete Examples

### Data Analysis Pipeline

```python
import pandas as pd
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize API
api = IPFSSimpleAPI(role="worker")

# Add dataset to IPFS
dataset_path = "raw_data.csv"
add_result = api.add(dataset_path, wrap_with_directory=True)
dataset_cid = add_result["cid"]

# Process dataset
df = pd.read_csv(dataset_path)
processed_df = df.dropna().sort_values('important_column')

# Save processed data to temporary file
processed_path = "processed_data.csv"
processed_df.to_csv(processed_path, index=False)

# Add processed data to IPFS
processed_result = api.add(processed_path)
processed_cid = processed_result["cid"]

# Pin both datasets for persistence
api.pin(dataset_cid)
api.pin(processed_cid)

# Create a directory linking both datasets
import json
manifest = {
    "raw_data_cid": dataset_cid,
    "processed_data_cid": processed_cid,
    "processing_timestamp": pd.Timestamp.now().isoformat(),
    "record_count": len(processed_df)
}

with open("manifest.json", "w") as f:
    json.dump(manifest, f)

manifest_result = api.add("manifest.json")
manifest_cid = manifest_result["cid"]

# Publish to IPNS for easy access
publish_result = api.publish(manifest_cid)
ipns_name = publish_result["ipns_name"]

print(f"Data pipeline complete:")
print(f"- Raw data: ipfs://{dataset_cid}")
print(f"- Processed data: ipfs://{processed_cid}")
print(f"- Manifest: ipfs://{manifest_cid}")
print(f"- IPNS address: ipns://{ipns_name}")
```

### Content Sharing App

```python
import os
import time
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

class SimpleContentSharing:
    def __init__(self):
        self.api = IPFSSimpleAPI(
            role="leecher",
            cache={
                "memory_size": "200MB",
                "disk_size": "1GB"
            }
        )
        
    def share_file(self, file_path):
        """Share a file and return its CID."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        print(f"Sharing file: {file_path}")
        start_time = time.time()
        
        result = self.api.add(file_path, pin=True)
        
        if result.get("success", False) or "cid" in result:
            cid = result.get("cid") or result.get("Hash")
            duration = time.time() - start_time
            size = os.path.getsize(file_path)
            
            print(f"File shared successfully in {duration:.2f} seconds")
            print(f"CID: {cid}")
            print(f"Size: {size / 1024:.2f} KB")
            
            # Create shareable links
            http_link = f"https://ipfs.io/ipfs/{cid}"
            ipfs_link = f"ipfs://{cid}"
            
            print(f"HTTP Gateway link: {http_link}")
            print(f"IPFS link: {ipfs_link}")
            
            return cid
        else:
            error = result.get("error", "Unknown error")
            print(f"Failed to share file: {error}")
            return None
            
    def download_file(self, cid, output_path):
        """Download content from IPFS and save to a file."""
        print(f"Downloading content with CID: {cid}")
        start_time = time.time()
        
        try:
            # Get content
            content = self.api.get(cid)
            
            # Save to file
            with open(output_path, 'wb') as f:
                f.write(content)
                
            duration = time.time() - start_time
            size = len(content)
            
            print(f"Download complete in {duration:.2f} seconds")
            print(f"Saved to: {output_path}")
            print(f"Size: {size / 1024:.2f} KB")
            
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False
            
    def list_directory(self, dir_cid):
        """List contents of a directory CID."""
        print(f"Listing directory with CID: {dir_cid}")
        
        try:
            files = self.api.ls(dir_cid, detail=True)
            
            print(f"Directory contains {len(files)} items:")
            for i, file in enumerate(files):
                file_type = file.get('type', 'unknown')
                name = file.get('name', f'item-{i}')
                size = file.get('size', 'unknown size')
                
                print(f"- [{file_type}] {name} ({size} bytes)")
                
            return files
        except Exception as e:
            print(f"Failed to list directory: {e}")
            return []

# Usage example
if __name__ == "__main__":
    app = SimpleContentSharing()
    
    # Share a file
    shared_cid = app.share_file("example.jpg")
    
    # Download a file
    if shared_cid:
        app.download_file(shared_cid, "downloaded_example.jpg")
        
    # List a directory (if the CID is a directory)
    # app.list_directory(dir_cid)
```

## Troubleshooting

### Common Issues and Solutions

1. **Connection Issues**

   ```
   Error: IPFS daemon connection failed
   ```

   - Ensure IPFS daemon is running (`ipfs daemon`)
   - Check API port availability (default: 5001)
   - Verify API listening address in IPFS config

2. **Authentication Issues**

   ```
   Error: Permission denied when accessing IPFS API
   ```

   - Check API authentication settings
   - Verify correct credentials (if enabled)

3. **Content Not Found**

   ```
   Error: Could not find content with CID QmXYZ...
   ```

   - Check if content is pinned locally (`api.list_pins()`)
   - Try finding content via public gateways
   - Ensure CID format is correct

4. **Role-Based Features**

   ```
   Error: Cluster operations not available in leecher role
   ```

   - Verify current role (`print(api.config.get("role"))`)
   - Initialize with correct role for required features

5. **Missing Dependencies**

   ```
   ImportError: No module named 'fsspec'
   ```

   - Install with required dependencies: `pip install ipfs_kit_py[fsspec]`
   - For AI/ML features: `pip install ipfs_kit_py[ai_ml]`

### Debugging

For advanced debugging, you can enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Create API with debug logging
api = IPFSSimpleAPI(
    logging={"level": "DEBUG"}
)
```

This will show detailed information about API calls, configuration, and components initialization.
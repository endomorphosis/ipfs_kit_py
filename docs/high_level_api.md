# High-Level API (`IPFSSimpleAPI`)

The `IPFSSimpleAPI` class, found in `ipfs_kit_py/high_level_api.py`, provides a user-friendly, simplified interface for common IPFS Kit operations. It aims to abstract away some of the underlying complexity of the core `ipfs_kit` class and its components.

## Key Features

-   **Simplified Interface:** Offers direct methods for common tasks like `add`, `get`, `pin`, `publish`, etc.
-   **Declarative Configuration:** Easily configure behavior using Python dictionaries, YAML files, or environment variables.
-   **Automatic Component Management:** Handles the initialization and management of the underlying `ipfs_kit` instance and its components based on configuration.
-   **Built-in Error Handling:** Provides consistent error reporting, often raising exceptions for failures.
-   **Plugin Architecture:** Extensible via a plugin system to add custom functionality.
-   **SDK Generation:** Can generate client SDKs for other languages.

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

The API automatically loads configuration from standard locations or the specified `config_path`, then applies any keyword arguments as overrides.

## Common Operations

The `IPFSSimpleAPI` provides direct methods for most common IPFS and cluster operations.

```python
# --- Content Operations ---
# Add file, string, or bytes
cid = api.add("my_document.txt")["cid"]
cid_str = api.add("Some text content")["cid"]
cid_bytes = api.add(b"\x00\x01\x02")["cid"]

# Get content (returns bytes)
content = api.get(cid)

# --- Filesystem-like Operations ---
# List directory contents (requires CID of a directory)
# Note: Use detail=True for more info like size/type
dir_contents = api.ls("QmDirectoryCID")

# Check existence
is_present = api.exists(cid)

# Open file (returns a file-like object)
with api.open(cid, mode="rb") as f:
    data = f.read(1024) # Read first 1KB

# Read entire file content directly
full_content = api.read(cid)

# --- Pinning ---
# Pin to local node
api.pin(cid)

# List local pins
pins = api.list_pins()

# Unpin from local node
api.unpin(cid)

# --- IPNS ---
# Publish CID to IPNS (uses 'self' key by default)
publish_result = api.publish(cid)
ipns_name = publish_result["ipns_name"]

# Resolve IPNS name
resolve_result = api.resolve(ipns_name)
resolved_cid = resolve_result["resolved_cid"]

# --- Peer Operations ---
# List connected peers
peers_result = api.peers()

# Connect to a peer
api.connect("/ip4/1.2.3.4/tcp/4001/p2p/QmPeerID")

# --- Cluster Operations (Master/Worker Roles) ---
try:
    # Add file to cluster (pins across nodes)
    cluster_add_result = api.cluster_add("important_data.csv", replication_factor=3)

    # Pin existing CID to cluster
    api.cluster_pin(cid, replication_factor=3)

    # Check cluster pin status
    status = api.cluster_status(cid)

    # List cluster peers
    cluster_peers = api.cluster_peers()
except (AttributeError, PermissionError) as e:
    print(f"Cluster operation failed (likely wrong role): {e}")

```

## Configuration

The `IPFSSimpleAPI` uses a layered configuration system:

1.  **Defaults:** Built-in default values.
2.  **Config File:** Loads from YAML or JSON specified by `config_path` or found in standard locations (`./ipfs_config.yaml`, `~/.ipfs_kit/config.yaml`, etc.).
3.  **Environment Variables:** Variables like `IPFS_KIT_ROLE`, `IPFS_KIT_API_URL`.
4.  **Initialization Arguments:** Keyword arguments passed to `IPFSSimpleAPI()` override all other sources.

You can access the final merged configuration via `api.config`.

```python
# Access configuration
current_role = api.config.get("role")
api_timeout = api.config.get("timeouts", {}).get("api")

# Save current effective configuration (if save_config is implemented)
# api.save_config("effective_config.yaml")
```

## Plugin System

Extend the API's functionality with custom plugins.

```python
from ipfs_kit_py.high_level_api import PluginBase

# Define a simple plugin
class HelloWorldPlugin(PluginBase):
    plugin_name = "HelloWorld" # Unique name for the plugin

    def greet(self, name="World"):
        # self.ipfs_kit gives access to the underlying ipfs_kit instance
        node_id_result = self.ipfs_kit.ipfs_id()
        node_id = node_id_result.get("ID", "Unknown")
        message = f"Hello, {name}! from node {node_id}"
        # Plugins should typically return a dictionary
        return {"success": True, "message": message}

# Register plugin during initialization
api = IPFSSimpleAPI(plugins=[{"plugin_class": HelloWorldPlugin}])

# Call the plugin method using the callable interface
result = api("HelloWorld.greet", name="IPFS User")
print(result["message"])

# Or using call_extension
result = api.call_extension("HelloWorld.greet", name="Developer")
print(result["message"])
```

Plugins can be registered via the `plugins` argument during initialization or dynamically using `api.register_plugin()`. They can be discovered automatically if placed in packages specified in the configuration.

## SDK Generation

Generate client SDKs for easy interaction from other languages.

```python
# Generate SDKs (requires relevant language tools/libraries to be installed)
try:
    py_sdk_result = api.generate_sdk("python", output_dir="./sdk/python")
    js_sdk_result = api.generate_sdk("javascript", output_dir="./sdk/js")
    # rust_sdk_result = api.generate_sdk("rust", output_dir="./sdk/rust") # If implemented

    print(f"Python SDK generated: {py_sdk_result.get('success')}")
    print(f"JavaScript SDK generated: {js_sdk_result.get('success')}")

except NotImplementedError as e:
    print(f"SDK generation failed: {e}")
except Exception as e:
    print(f"An error occurred during SDK generation: {e}")
```

This feature simplifies building applications that interact with IPFS Kit across different technology stacks.

## Relationship to Core `ipfs_kit`

The `IPFSSimpleAPI` acts as a facade over the core `ipfs_kit` class. It manages an instance of `ipfs_kit` internally (`api.kit`) and delegates most operations to it, adding a layer of simplification, configuration management, and plugin handling. For advanced use cases or direct access to specific components (like `ipfs_cluster_service`), you might interact with `api.kit` directly.

# Role-Based Component Disabling Implementation

## Summary

Successfully implemented role-based component disabling for the IPFS Kit MCP server. When running in leecher role, the following components are automatically disabled:

- **ipfs_cluster** - IPFS Cluster service
- **ipfs_cluster_follow** - IPFS Cluster Follow service  
- **lotus** - Lotus (Filecoin) integration
- **synapse** - Synapse storage integration

## Implementation Details

### 1. CLI Layer (`ipfs_kit_py/cli.py`)

Modified `start_role_mcp_server()` function to:
- Define disabled components list for leecher role
- Pass `disabled_components` parameter to MCP server constructor
- Log which components are being disabled

```python
def start_role_mcp_server(args, role="leecher", **kwargs):
    # Define components to disable for leecher role
    disabled_components = []
    if role == "leecher":
        disabled_components = ["ipfs_cluster", "ipfs_cluster_follow", "lotus", "synapse"]
        print(f"Leecher role: Disabling components: {', '.join(disabled_components)}")
```

### 2. MCP Server Layer (`mcp/ipfs_kit/modular_enhanced_mcp_server.py`)

Enhanced `ModularEnhancedMCPServer` constructor to:
- Accept `disabled_components` parameter
- Pass disabled components to SetupManager
- Pass disabled components to IPFSClient initialization
- Disable component status flags in COMPONENTS dict

```python
def __init__(self, host: str = "127.0.0.1", port: int = 8765, role: str = "leecher", debug: bool = False, disabled_components: List[str] = None):
    self.disabled_components = disabled_components or []
    
    # Log disabled components
    if self.disabled_components:
        logger.info(f"Disabled components for {role} role: {', '.join(self.disabled_components)}")
    
    # Pass to setup manager and IPFS client
    setup_manager = SetupManager(disabled_components=self.disabled_components)
    self.ipfs_client = IPFSClient(role=self.role, disabled_components=self.disabled_components)
```

### 3. Setup Manager Layer (`mcp/ipfs_kit/setup.py`)

Updated `SetupManager` to:
- Accept `disabled_components` parameter
- Skip cluster service initialization when disabled
- Log when services are skipped

```python
def run_setup(self):
    self.install_ipfs()
    self.install_lassie()
    self.configure_ipfs()
    
    # Only start cluster services if not disabled
    if "ipfs_cluster" not in self.disabled_components:
        self.start_ipfs_cluster_service()
    else:
        logger.info("Skipping IPFS Cluster service - disabled for this role")
        
    if "ipfs_cluster_follow" not in self.disabled_components:
        self.start_ipfs_cluster_follow()
    else:
        logger.info("Skipping IPFS Cluster Follow service - disabled for this role")
```

### 4. High-Level API Layer (`ipfs_kit_py/high_level_api.py`)

Modified `IPFSSimpleAPI` constructor to:
- Accept `disabled_components` parameter
- Pass disabled components to ipfs_kit via metadata
- Store disabled components list

```python
def __init__(self, config_path: Optional[str] = None, **kwargs):
    role = kwargs.get("role", self.config.get("role", "leecher"))
    disabled_components = kwargs.get("disabled_components", [])
    
    # Pass to ipfs_kit via metadata
    metadata = self.config.get("metadata", {})
    metadata["role"] = role
    metadata["disabled_components"] = disabled_components
    
    self.kit = ipfs_kit(resources=resources, metadata=metadata)
```

### 5. Core IPFS Kit Layer (`ipfs_kit_py/ipfs_kit.py`)

Enhanced the `ipfs_kit` class constructor to:
- Check for disabled components in metadata
- Conditionally initialize components based on disabled list
- Set disabled components to None and log the disabling

```python
# For leecher role
if self.role == "leecher":
    disabled_components = metadata.get("disabled_components", [])
    
    # Initialize Synapse storage if not disabled
    if HAS_SYNAPSE and "synapse" not in disabled_components:
        self.synapse_storage = synapse_storage(resources=resources, metadata=metadata)
        self.logger.info("Initialized Synapse storage for Filecoin PDP integration")
    else:
        self.synapse_storage = None
        if "synapse" in disabled_components:
            self.logger.info("Synapse storage disabled for leecher role")
    
    # Initialize Lotus Kit if not disabled        
    if HAS_LOTUS and "lotus" not in disabled_components:
        self.lotus_kit = lotus_kit(resources=resources, metadata=lotus_metadata)
        self.logger.info("Initialized Lotus Kit for Filecoin integration")
    else:
        self.lotus_kit = None
        if "lotus" in disabled_components:
            self.logger.info("Lotus Kit disabled for leecher role")
```

## Usage

### Command Line
```bash
# Run MCP server in leecher role (components disabled)
python -m ipfs_kit_py.cli mcp leecher --debug

# Run MCP server in other roles (components enabled)
python -m ipfs_kit_py.cli mcp master --debug
python -m ipfs_kit_py.cli mcp worker --debug
```

### Programmatic
```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Create API with disabled components
api = IPFSSimpleAPI(
    role='leecher', 
    disabled_components=['lotus', 'synapse', 'ipfs_cluster', 'ipfs_cluster_follow']
)

# Check component status
print(f"Lotus enabled: {api.kit.lotus_kit is not None}")
print(f"Synapse enabled: {api.kit.synapse_storage is not None}")
```

## Log Messages

When components are disabled, you'll see messages like:
```
INFO - Disabled components for leecher role: ipfs_cluster, ipfs_cluster_follow, lotus, synapse
INFO - Skipping IPFS Cluster service - disabled for this role
INFO - Skipping IPFS Cluster Follow service - disabled for this role  
INFO - Synapse storage disabled for leecher role
INFO - Lotus Kit disabled for leecher role
```

## Testing

A comprehensive test script is available at `test_role_component_disabling.py` that demonstrates:
- Component disabling for leecher role
- Normal component initialization for other roles
- Status verification for all components

## Benefits

1. **Resource Efficiency**: Leecher nodes don't initialize unnecessary services
2. **Clean Architecture**: Role-specific behavior is clearly defined
3. **Flexible Configuration**: Easy to extend for other roles or components
4. **Comprehensive Logging**: Clear visibility into what components are disabled
5. **Backward Compatibility**: Existing functionality remains unchanged

The implementation successfully ensures that when the MCP server runs in leecher role, the specified components (ipfs_cluster, ipfs_cluster_follow, lotus, synapse) are completely disabled at all layers of the system.

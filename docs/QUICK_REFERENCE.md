# IPFS Kit Python - Quick Reference

Fast reference guide for common operations and commands.

## Installation

```bash
# Install from PyPI (when available)
pip install ipfs_kit_py

# Install from source
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
pip install -e .

# Install with extras
pip install ipfs_kit_py[full]  # All features
pip install ipfs_kit_py[ai_ml]  # AI/ML features
pip install ipfs_kit_py[fsspec]  # FSSpec support
```

## Python API Quick Start

### Basic IPFS Operations

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize
api = IPFSSimpleAPI()

# Add content
result = api.add("myfile.txt")
cid = result['cid']
print(f"Added: {cid}")

# Get content
content = api.get(cid)

# Pin content
api.pin(cid)

# List pins
pins = api.list_pins()

# Read content
data = api.read(cid)

# Check if exists
exists = api.exists(cid)
```

### Cluster Operations

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize with cluster role
api = IPFSSimpleAPI(role="master")

# Add to cluster
result = api.cluster_add("myfile.txt", replication_factor=2)

# Pin to cluster
api.cluster_pin(cid, replication_factor=2)

# Check cluster status
status = api.cluster_status(cid)

# List cluster peers
peers = api.cluster_peers()
```

### IPNS Operations

```python
# Publish to IPNS
result = api.publish(cid, key="mykey", lifetime="24h")
ipns_name = result['ipns_name']

# Resolve IPNS name
resolved = api.resolve(ipns_name)
```

## Command-Line Interface

### MCP Server Commands

```bash
# Start MCP server and dashboard
ipfs-kit mcp start
ipfs-kit mcp start --port 8004 --foreground

# Check server status
ipfs-kit mcp status

# Stop server
ipfs-kit mcp stop

# Check for deprecations
ipfs-kit mcp deprecations --json
```

### Configuration

```bash
# Default data directory
~/.ipfs_kit/

# Configuration structure
~/.ipfs_kit/
├── config.yaml          # Main configuration
├── backend_configs/     # Backend configurations
│   ├── ipfs.json
│   ├── s3.json
│   └── ...
└── credentials/         # Secure credentials
```

## Common Workflows

### Adding and Pinning Content

```python
# Add file and pin
api = IPFSSimpleAPI()
result = api.add("myfile.txt", pin=True)
cid = result['cid']

# Add directory recursively
result = api.add("mydir/", recursive=True)

# Add with wrap directory
result = api.add("myfile.txt", wrap_with_directory=True)
```

### Working with Directories

```python
# List directory contents
contents = api.ls(directory_cid, detail=True)
for item in contents:
    print(f"{item['name']}: {item['cid']}")

# Get specific file from directory
file_cid = contents[0]['cid']
data = api.get(file_cid)
```

### Cluster Deployment

```bash
# Quick 3-node cluster setup
python tools/start_3_node_cluster.py

# Verify cluster health
curl http://localhost:8998/health   # Master
curl http://localhost:8999/health   # Worker 1
curl http://localhost:9000/health   # Worker 2
```

### Using with AI/ML

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

# Add model to registry
result = api.ai_model_add(
    model=my_model,
    metadata={"name": "my-model", "version": "1.0"}
)

# Add dataset
result = api.ai_dataset_add(
    dataset=my_dataframe,
    metadata={"name": "training-data"}
)

# Visualize metrics
api.ai_metrics_visualize(
    model_id="my-model",
    metrics_type="all",
    interactive=True
)
```

## Environment Variables

```bash
# IPFS configuration
export IPFS_PATH=/path/to/.ipfs
export IPFS_KIT_CLUSTER_MODE=true

# MCP server
export IPFS_KIT_MCP_PORT=8004
export IPFS_KIT_DATA_DIR=~/.ipfs_kit

# Auto-healing
export IPFS_KIT_AUTO_HEAL=true
export GITHUB_TOKEN=your_token

# Logging
export LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## Configuration File Example

```yaml
# ~/.ipfs_kit/config.yaml
role: master  # master, worker, leecher

ipfs:
  api_host: 127.0.0.1
  api_port: 5001
  gateway_port: 8080

cluster:
  enabled: true
  replication_factor: 2

cache:
  memory_size: 500MB
  disk_size: 5GB
  
timeouts:
  api: 60
  gateway: 120

resources:
  max_memory: 2GB
  max_storage: 100GB
```

## Common Issues & Solutions

### Connection Issues

```bash
# Check if IPFS daemon is running
ipfs id

# Start IPFS daemon
ipfs daemon

# Check API endpoint
curl http://127.0.0.1:5001/api/v0/id
```

### Python Import Errors

```python
# Ensure package is installed
import ipfs_kit_py
print(ipfs_kit_py.__version__)

# Check for required dependencies
pip install -r requirements.txt
```

### Cluster Issues

```bash
# Check cluster status
ipfs-cluster-ctl status

# Verify peers
ipfs-cluster-ctl peers ls

# Check logs
tail -f ~/.ipfs-cluster/cluster.log
```

## Getting Help

```bash
# CLI help
ipfs-kit --help
ipfs-kit mcp --help

# Python API help
python -c "from ipfs_kit_py.high_level_api import IPFSSimpleAPI; help(IPFSSimpleAPI)"

# Documentation
# See docs/README.md for complete documentation index
```

## Version Information

```bash
# Check version
ipfs-kit --version

# Python version required
python --version  # 3.12+ required
```

## Related Documentation

- **[Installation Guide](installation_guide.md)** - Detailed installation instructions
- **[API Reference](api/api_reference.md)** - Complete API documentation
- **[CLI Reference](api/cli_reference.md)** - Full CLI command reference
- **[Configuration Guide](guides/)** - Configuration options and examples
- **[Cluster Guide](operations/cluster_management.md)** - Cluster setup and management
- **[Auto-Healing](features/auto-healing/AUTO_HEALING.md)** - Auto-healing system documentation

---

**Note:** This is a quick reference. For detailed documentation, see the [complete documentation index](README.md).

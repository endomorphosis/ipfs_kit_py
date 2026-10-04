# IPFS Kit Servers

This directory contains various MCP server implementations for development and testing purposes.

Production MCP runtime is the unified server:
- `ipfs_kit_py.mcp.servers.unified_mcp_server`

## Server Types

### Development/Testing Servers (in this directory)
- `enhanced_mcp_server_with_config.py` - Enhanced server with configuration management
- `enhanced_mcp_server_with_daemon_init.py` - Server with daemon initialization
- `enhanced_mcp_server_with_full_config.py` - Server with complete configuration system
- `final_mcp_server_enhanced.py` - Final enhanced server implementation
- `streamlined_mcp_server.py` - Streamlined server version
- `containerized_mcp_server.py` - Docker-ready containerized server

These are legacy/development surfaces and are not canonical production runtime.

### Production Servers (root level)
- `../standalone_cluster_server.py` - **Primary production cluster server**
- `../start_3_node_cluster.py` - **Production cluster launcher**
- `../main.py` - **Main application entry point**

For MCP-specific production runtime, prefer unified server import path above.

## Usage

### For Development
Use the servers in this directory for development, testing, and experimentation.

### For Production
Use the servers at the root level for production deployments:

```bash
# Start production cluster
python start_3_node_cluster.py

# Or run standalone server
python standalone_cluster_server.py

# Or use main entry point
python main.py
```

## Server Selection Guide

- **New MCP Development**: Use unified server (`ipfs_kit_py.mcp.servers.unified_mcp_server`)
- **Container Deployment**: Use unified server wiring in container startup
- **Production Cluster**: Use `../standalone_cluster_server.py`
- **Testing**: Use compatibility/legacy servers only for adapter tests

See `docs/MCP_SERVER_MIGRATION_GUIDE.md` for deprecation policy and migration steps.

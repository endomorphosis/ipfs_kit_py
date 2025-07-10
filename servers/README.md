# IPFS Kit Servers

This directory contains various MCP server implementations for development and testing purposes.

## Server Types

### Development/Testing Servers (in this directory)
- `enhanced_mcp_server_with_config.py` - Enhanced server with configuration management
- `enhanced_mcp_server_with_daemon_init.py` - Server with daemon initialization
- `enhanced_mcp_server_with_full_config.py` - Server with complete configuration system
- `final_mcp_server_enhanced.py` - Final enhanced server implementation
- `streamlined_mcp_server.py` - Streamlined server version
- `containerized_mcp_server.py` - Docker-ready containerized server

### Production Servers (root level)
- `../standalone_cluster_server.py` - **Primary production cluster server**
- `../start_3_node_cluster.py` - **Production cluster launcher**
- `../main.py` - **Main application entry point**

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

- **New Development**: Start with `enhanced_mcp_server_with_full_config.py`
- **Container Deployment**: Use `containerized_mcp_server.py`
- **Production Cluster**: Use `../standalone_cluster_server.py`
- **Testing**: Use `streamlined_mcp_server.py`

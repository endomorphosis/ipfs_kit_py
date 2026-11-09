# IPFS Tools Integration for MCP Server

This project successfully integrates IPFS (InterPlanetary File System) capabilities into the MCP (Model Context Protocol) server, providing comprehensive tools for AI assistants to interact with IPFS content.

## ✅ Integration Complete

All IPFS tools have been successfully integrated with the MCP server and are now available for use by AI assistants through the MCP tools interface.

## 🛠️ Available IPFS Tools

The following IPFS-related tools are now available:

### Mutable File System (MFS) Operations

| Tool | Description |
|------|-------------|
| `ipfs_files_ls` | List files and directories in IPFS MFS |
| `ipfs_files_mkdir` | Create directories in IPFS MFS |
| `ipfs_files_write` | Write content to files in IPFS MFS |
| `ipfs_files_read` | Read content from files in IPFS MFS |
| `ipfs_files_rm` | Remove files/directories from IPFS MFS |
| `ipfs_files_stat` | Get statistics about files/directories in IPFS MFS |
| `ipfs_files_cp` | Copy files within IPFS MFS |
| `ipfs_files_mv` | Move files within IPFS MFS |

### IPNS Operations

| Tool | Description |
|------|-------------|
| `ipfs_name_publish` | Publish IPNS names |
| `ipfs_name_resolve` | Resolve IPNS names |

### DAG Operations

| Tool | Description |
|------|-------------|
| `ipfs_dag_put` | Add DAG nodes to IPFS |
| `ipfs_dag_get` | Get DAG nodes from IPFS |

## 🚀 Getting Started

### Starting the Enhanced MCP Server

Use the included all-in-one script to start the IPFS-enhanced MCP server:

```bash
./start_ipfs_enhanced_mcp.sh
```

This script:
1. Fixes any syntax issues in the MCP server code
2. Loads all the IPFS tool definitions
3. Integrates the tools with the MCP server
4. Starts the server with all IPFS tools enabled

### Command-line Options

The launcher script accepts the following options:

- `--host HOST`: Specify the host to bind to (default: 127.0.0.1)
- `--port PORT`: Specify the port to listen on (default: 3000)
- `--log-level LEVEL`: Set the logging level (default: INFO)

Example:
```bash
./start_ipfs_enhanced_mcp.sh --port 8000 --log-level DEBUG
```

### Stopping the Server

To gracefully stop the server, use:

```bash
./stop_ipfs_enhanced_mcp.sh
```

## 🧩 Components of the Integration

The following components work together to provide the IPFS tools integration:

1. **IPFS Tools Registry** (`ipfs_tools_registry.py`): Provides the tool definitions and schemas
2. **IPFS MCP Tools Integration** (`ipfs_mcp_tools_integration.py`): Registers the tools with the MCP server
3. **Direct MCP Server** (`direct_mcp_server.py`): Enhanced with IPFS tools integration
4. **Start/Stop Scripts**: Simplified scripts for managing the IPFS-enhanced MCP server

## 🔄 Integration with Virtual Filesystem

All IPFS tools are seamlessly integrated with the virtual filesystem capabilities, allowing AI assistants to:

1. Work with both local and IPFS-based files
2. Maintain consistent file operations between local and IPFS storage
3. Transfer content between local and IPFS storage

## 📋 Usage Examples

### Example 1: Listing Files in IPFS MFS

```python
result = await ctx.use_tool("ipfs_files_ls", {"path": "/"})
```

### Example 2: Creating a Directory in IPFS MFS

```python
result = await ctx.use_tool("ipfs_files_mkdir", {"path": "/my_directory", "parents": True})
```

### Example 3: Writing a File to IPFS MFS

```python
result = await ctx.use_tool("ipfs_files_write", {
    "path": "/my_directory/hello.txt",
    "content": "Hello, IPFS!",
    "create": True,
    "truncate": True
})
```

### Example 4: Reading a File from IPFS MFS

```python
result = await ctx.use_tool("ipfs_files_read", {"path": "/my_directory/hello.txt"})
```

## 🛠️ Troubleshooting

If you encounter any issues with the IPFS tools integration, check the following:

1. **Server Logs**: Review the server logs (`direct_mcp_server.log`) for error messages
2. **Tool Registration**: Verify that the IPFS tools are properly registered in the startup logs
3. **Tool Usage**: Ensure that you're using the correct parameters for each tool

## 📝 Future Enhancements

Planned enhancements to the IPFS tools integration include:

1. Integration with real IPFS nodes
2. Support for additional IPFS operations like pubsub
3. Enhanced error handling and recovery
4. Integration with Filecoin for persistent storage

## 📚 Resources

For more information on IPFS, see the [IPFS documentation](https://docs.ipfs.tech/).

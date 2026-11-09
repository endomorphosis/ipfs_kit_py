# IPFS MCP Integration

This integration adds comprehensive IPFS (InterPlanetary File System) capabilities to the MCP (Model Context Protocol) server. It provides a wide range of IPFS file operations through the MCP tools interface, allowing AI assistants to directly interact with IPFS content.

## Overview

The IPFS MCP Integration brings together the power of IPFS with the flexibility of the Model Context Protocol. By exposing IPFS operations as MCP tools, this integration enables:

- Direct IPFS file system operations from AI assistants
- Seamless handling of content addressing
- Full support for IPFS Mutable File System (MFS) operations
- IPNS name publication and resolution
- DAG (Directed Acyclic Graph) operations for structured content

## Components

The integration consists of several key components:

1. **Server Syntax Fix** (`complete_server_fix.py`): Repairs syntax issues in the MCP server code to ensure proper operation.

2. **IPFS Tools Enhancement** (`enhance_ipfs_mcp_tools.py`): Defines the full range of IPFS tools that will be exposed to AI assistants through the MCP interface. This includes MFS operations, IPNS operations, and DAG operations.

3. **IPFS Tools Loader** (`load_ipfs_mcp_tools.py`): Creates the necessary tool registry and integration code to load the IPFS tools into the MCP server environment.

4. **MCP Server Patch** (`patch_direct_mcp_server.py`): Modifies the direct MCP server to integrate and register the IPFS tools during startup.

5. **All-in-One Launcher** (`start_ipfs_enhanced_mcp.sh`): Combines all the above components into a single script that fixes, enhances, and launches the IPFS-enabled MCP server.

## Getting Started

### Prerequisites

- Python 3.8+
- IPFS daemon running locally (optional, mock implementations are provided)
- MCP server code base

### Quick Start

Simply run the all-in-one script to start the IPFS-enhanced MCP server:

```bash
./start_ipfs_enhanced_mcp.sh
```

This will:
1. Fix any syntax issues in the MCP server code
2. Load the IPFS tool definitions
3. Patch the direct MCP server
4. Start the server with all IPFS tools enabled

### Command-line Options

The launcher script accepts the following options:

- `--host HOST`: Specify the host to bind to (default: 127.0.0.1)
- `--port PORT`: Specify the port to listen on (default: 3000)
- `--log-level LEVEL`: Set the logging level (default: INFO)

Example:
```bash
./start_ipfs_enhanced_mcp.sh --port 8000 --log-level DEBUG
```

## Available IPFS Tools

The integration provides the following IPFS-related tools:

### Mutable File System (MFS) Operations

| Tool | Description | Parameters |
|------|-------------|------------|
| `ipfs_files_ls` | List files in IPFS MFS | `path`, `long` |
| `ipfs_files_mkdir` | Create directories in IPFS MFS | `path`, `parents` |
| `ipfs_files_write` | Write data to a file in IPFS MFS | `path`, `content`, `create`, `truncate` |
| `ipfs_files_read` | Read a file from IPFS MFS | `path`, `offset`, `count` |
| `ipfs_files_rm` | Remove files/directories from IPFS MFS | `path`, `recursive`, `force` |
| `ipfs_files_stat` | Get file/directory information | `path`, `with_local`, `size` |
| `ipfs_files_cp` | Copy files within IPFS MFS | `source`, `dest` |
| `ipfs_files_mv` | Move files within IPFS MFS | `source`, `dest` |

### IPNS Operations

| Tool | Description | Parameters |
|------|-------------|------------|
| `ipfs_name_publish` | Publish IPNS names | `path`, `resolve`, `lifetime` |
| `ipfs_name_resolve` | Resolve IPNS names | `name`, `recursive`, `nocache` |

### DAG Operations

| Tool | Description | Parameters |
|------|-------------|------------|
| `ipfs_dag_put` | Add a DAG node to IPFS | `data`, `format`, `input_codec`, `pin` |
| `ipfs_dag_get` | Get a DAG node from IPFS | `cid`, `path` |

## Usage Examples

### Listing Files in MFS

```python
result = await context.use_tool("ipfs_files_ls", {"path": "/", "long": True})
print(result)
```

### Writing to MFS

```python
result = await context.use_tool("ipfs_files_write", {
    "path": "/hello.txt",
    "content": "Hello, IPFS!",
    "create": True,
    "truncate": True
})
print(result)
```

### Publishing to IPNS

```python
result = await context.use_tool("ipfs_name_publish", {
    "path": "/ipfs/QmXarR6rgkQ2fDSHjSY5nM2kuCXKYGViky5nohtwgF65Ec",
    "resolve": True,
    "lifetime": "24h"
})
print(result)
```

## Architecture

The IPFS MCP integration is designed with a layered architecture:

1. **Tool Definitions Layer**: Defines the schema and parameters for each IPFS operation.
2. **Integration Layer**: Connects the tool definitions to the MCP server framework.
3. **Implementation Layer**: Currently provides mock implementations, but can be extended to connect to a real IPFS node.

## Extending the Integration

To extend this integration with real IPFS functionality:

1. Edit the `ipfs_mcp_tools_integration.py` file
2. Replace the mock implementation functions with actual calls to IPFS API
3. Add any additional IPFS tools by adding them to `enhance_ipfs_mcp_tools.py`

## Troubleshooting

### Common Issues

- **Server fails to start**: Make sure all the required files are in place and have executable permissions.
- **Tool registration fails**: Check the server logs for detailed error messages. Ensure the IPFS tool registry is properly created.
- **IPFS tools not appearing**: Verify that the patch was successfully applied to the direct MCP server.

### Logs

The MCP server logs can be found in `direct_mcp_server.log`. Set the log level to DEBUG for more detailed information:

```bash
./start_ipfs_enhanced_mcp.sh --log-level DEBUG
```

## Future Enhancements

Planned future enhancements include:

- Real IPFS node integration for full IPFS functionality
- Support for IPFS pubsub operations
- Integration with Filecoin for persistent storage
- Support for IPLD data structures
- Improved error handling and recovery mechanisms

## License

This project is licensed under the same terms as the ipfs_kit_py project.

## Contributors

- IPFS Kit Team

## Acknowledgments

- IPFS Project
- MCP Development Team
- Claude AI Assistance

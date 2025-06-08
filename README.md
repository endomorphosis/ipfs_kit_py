# IPFS Kit Python - Production Ready MCP Server

[![Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/your-repo/ipfs_kit_py)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-orange)](https://modelcontextprotocol.io/)
[![Files Organized](https://img.shields.io/badge/Files-88%25%20Reduced-green)](./FINAL_PRODUCTION_STATUS.md)

**IPFS Kit** is a comprehensive, production-ready Python toolkit for working with IPFS (InterPlanetary File System) technologies. It provides a unified Model Context Protocol (MCP) server for IPFS operations, cluster management, tiered storage, and AI/ML integration.

> 🎉 **Now Production Ready!** This project has been transformed from 700+ cluttered files to a clean, organized structure with comprehensive documentation. See [FINAL_PRODUCTION_STATUS.md](./FINAL_PRODUCTION_STATUS.md) for complete details.

## 🚀 Quick Start

### Production MCP Server

Start the production MCP server in seconds:

```bash
# Direct execution
python3 final_mcp_server_enhanced.py --host 0.0.0.0 --port 9998

# Docker deployment
docker-compose up -d

# Development mode with debug logging
python3 final_mcp_server_enhanced.py --debug
```

### Installation

```bash
# Development installation
git clone https://github.com/your-repo/ipfs_kit_py.git
cd ipfs_kit_py
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Package installation (when published)
pip install ipfs_kit_py[full]
```

## 🌟 Key Features

### Production MCP Server
- **FastAPI-based REST API** with comprehensive IPFS operations
- **JSON-RPC 2.0 protocol** support for Model Context Protocol compatibility
- **Mock IPFS implementation** for reliable testing and development
- **Health monitoring** with `/health` endpoint and metrics
- **Comprehensive logging** with structured output and debug modes
- **Docker deployment** with optimized containers and compose configuration

### IPFS Operations
- **Content Management**: Add, retrieve, pin, and list IPFS content
- **Mock Storage**: Realistic IPFS behavior for testing without requiring IPFS daemon
- **CID Generation**: Proper content addressing with SHA-256 based CIDs
- **Error Handling**: Robust error handling with detailed error messages

### Developer Experience
- **Command-line Interface**: Easy-to-use CLI with configurable options
- **Auto-generated Documentation**: Interactive API docs at `/docs` endpoint
- **Validation Tools**: Built-in server validation and testing utilities
- **Hot Reload**: Development mode with automatic code reloading

## 📋 API Endpoints

The MCP server provides the following endpoints:

### Health & Status
- `GET /health` - Health check and server status
- `GET /metrics` - Server metrics and statistics
- `GET /docs` - Interactive API documentation

### JSON-RPC Interface
- `POST /jsonrpc` - MCP protocol endpoint for tool execution

### IPFS Operations (via JSON-RPC)
- `ipfs_add` - Add content to IPFS storage
- `ipfs_cat` - Retrieve content by CID
- `ipfs_pin_add` - Pin content for persistence
- `ipfs_pin_ls` - List pinned content
- `ipfs_refs` - List references and links

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)
```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Manual Docker Build
```bash
# Build the image
docker build -t ipfs-kit-mcp .

# Run the container
docker run -p 9998:9998 ipfs-kit-mcp
```

## 🔧 Configuration

### Environment Variables
- `IPFS_KIT_HOST` - Server host (default: 127.0.0.1)
- `IPFS_KIT_PORT` - Server port (default: 9998)
- `IPFS_KIT_DEBUG` - Enable debug mode (default: false)
- `PYTHONUNBUFFERED` - Ensure unbuffered output for Docker

### Command Line Options
```bash
python3 final_mcp_server_enhanced.py --help
```

Options:
- `--host HOST` - Host to bind to (default: 127.0.0.1)
- `--port PORT` - Port to bind to (default: 9998)
- `--debug` - Enable debug mode with detailed logging

## Examples

For practical examples of using IPFS Kit, see the [examples directory](../examples/README.md), which includes:

- Basic usage examples
- FSSpec integration examples
- Cluster management examples
- Performance profiling examples
- Filesystem journal examples
- Journal monitoring and visualization examples
- AI/ML integration examples
- AI/ML visualization examples
- Data science workflow examples
- High-level API usage examples
- Tiered cache performance examples
- Probabilistic data structures examples
- Practical integration examples

## Contributing to Documentation

We welcome contributions to improve the documentation! If you find errors, have suggestions, or want to add examples, please submit a pull request or open an issue.

When contributing to documentation:

1. Follow the existing style and formatting
2. Provide practical examples where appropriate
3. Explain concepts clearly with diagrams when appropriate
4. Link related documentation
5. Test examples before submitting

## Getting Help

If you need help with IPFS Kit:

- Check the [README.md](../README.md) for quick start guides
- Search the documentation for specific topics
- Look at the examples in the [examples directory](../examples/)
- Open an issue on GitHub if you find a bug or have a feature request
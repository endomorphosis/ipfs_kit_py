# Agent Integration Guide

> Auto-generated guide for programming agents

This document provides structured information for programming agents to effectively interact with IPFS Kit Python.

## Project Structure

```
ipfs_kit_py/
├── core/           # Core IPFS functionality
├── mcp/            # Model Context Protocol server
├── cluster/        # Cluster management
├── dashboard/      # Web dashboard
├── cli/            # Command-line interface
└── tests/          # Test suite
```

## Key Entry Points

### Main Classes
- `ipfs_kit_py.ipfs_kit.IPFSKit`: Primary interface for IPFS operations
- `ipfs_kit_py.bucket_manager.BucketManager`: Manage storage buckets

### MCP Server
- Entry: `ipfs_kit_py/mcp/`
- Dashboard: `consolidated_mcp_dashboard.py`

### CLI
- Entry: `ipfs_kit_py.cli`
- Command: `ipfs-kit`

## Common Operations

### Initialize IPFS Kit
```python
from ipfs_kit_py import IPFSKit

kit = IPFSKit()
# Ready to use
```

### Start MCP Server
```bash
ipfs-kit mcp start --port 8004
```

### Run Tests
```bash
pytest tests/
```

## Configuration

Configuration files are located in:
- `~/.ipfs_kit/` - User configuration
- `config/` - Default configuration templates

## Documentation Resources

- **API Reference**: See `docs/api_reference.md`
- **Module Structure**: See `docs/api_generated/module_structure.md`
- **Examples**: See `examples/` directory
- **Tests**: See `tests/` for usage patterns

## Build and Test Commands

```bash
# Install dependencies
pip install -e .

# Run tests
pytest tests/

# Run linter
black --check .
isort --check .

# Build documentation
cd docs && make html
```

## Environment Variables

Key environment variables:
- `IPFS_KIT_HOME`: Base directory for IPFS Kit data
- `MCP_PORT`: MCP server port (default: 8004)
- `MCP_API_TOKEN`: API authentication token

## Error Handling

Most operations return standard Python exceptions. Check module docstrings for specific exception types.

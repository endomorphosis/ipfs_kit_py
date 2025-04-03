# IPFS Kit Documentation

Welcome to the IPFS Kit documentation. This guide provides comprehensive information about IPFS Kit, a powerful Python toolkit for working with the InterPlanetary File System (IPFS) and related distributed technologies.

## Overview

IPFS Kit is a comprehensive toolkit for IPFS with tiered storage, advanced networking, and knowledge graph capabilities. It offers:

- **Role-based Architecture**: Master, worker, and leecher node roles for distributed operations
- **Multi-tier Storage**: Adaptive cache system for optimal content placement and retrieval
- **Content Routing**: Efficient mechanisms for locating and retrieving content
- **FSSpec Integration**: Standard filesystem interface for data science workflows
- **Knowledge Graph**: IPLD-based graph database with vector search capabilities
- **AI/ML Integration**: Connectors for machine learning frameworks and GraphRAG
- **High Performance**: Memory-mapped access and Arrow C Data Interface for low-latency operations

## Documentation Sections

### Core Concepts and Usage

- [Installation Guide](installation.md) - How to install IPFS Kit
- [Quick Start Guide](quickstart.md) - Get up and running quickly
- [Command Line Interface](cli.md) - Using the CLI tools
- [API Reference](api_reference.md) - Python API documentation
- [Role-Based Architecture](roles.md) - Understanding master, worker, and leecher nodes

### Storage and Performance

- [Tiered Storage System](tiered_cache.md) - Multi-tiered caching architecture
- [FSSpec Integration](fsspec_integration.md) - Using IPFS Kit with data science tools
- [Arrow Metadata Index](metadata_index.md) - High-performance metadata indexing

### Advanced Features

- [Knowledge Graph](knowledge_graph.md) - IPLD-based knowledge representation
- [libp2p Integration](libp2p_integration.md) - Direct peer-to-peer communication
- [Cluster State](cluster_state_helpers.md) - Distributed state management

### Deployment and Operations

- [PyPI Release Guide](pypi_release.md) - Publishing to PyPI
- [Containerization and Deployment](containerization.md) - Docker and Kubernetes deployment
- [CI/CD Pipeline](ci_cd_pipeline.md) - Continuous integration and deployment

### Examples

- [Data Science Examples](examples/data_science_examples.md) - Working with scientific data
- [High-Level API Examples](examples/high_level_api_example.md) - Simplified API usage
- [Knowledge Graph Examples](examples/knowledge_graph_example.md) - Building and querying graphs
- [Cluster Management Examples](examples/cluster_management_example.md) - Managing distributed clusters

## Getting Started

To get started with IPFS Kit, first install the package:

```bash
pip install ipfs_kit_py
```

Then initialize an IPFS Kit instance:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with default configuration (leecher role)
kit = ipfs_kit()

# Add content to IPFS
result = kit.ipfs_add("Hello, IPFS!")
print(f"Content added with CID: {result['cid']}")

# Retrieve content
content = kit.ipfs_cat(result['cid'])
print(f"Retrieved content: {content}")
```

For more complex setups, see the [Quick Start Guide](quickstart.md) or explore specific topics in the documentation sections above.

## Support and Community

- [GitHub Repository](https://github.com/yourusername/ipfs_kit_py)
- [Issue Tracker](https://github.com/yourusername/ipfs_kit_py/issues)
- [Contributing Guidelines](contributing.md)

## License

IPFS Kit is licensed under [MIT License](https://opensource.org/licenses/MIT).
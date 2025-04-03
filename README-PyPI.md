# IPFS Kit

IPFS Kit is a comprehensive Python toolkit for working with IPFS (InterPlanetary File System) technologies. It provides a unified interface for IPFS operations, cluster management, tiered storage, and AI/ML integration.

## Key Features

- **High-Level API**: Simplified interface (`IPFSSimpleAPI`) with declarative configuration
- **Role-based Architecture**: Configure nodes as master, worker, or leecher, each optimized for specific tasks
- **Tiered Storage & Caching**: Intelligently manage content across multiple backends with a high-performance Adaptive Replacement Cache (ARC) system
- **Standard Filesystem Interface**: FSSpec integration for familiar filesystem-like access to IPFS content
- **Metadata Indexing**: Efficient Arrow-based metadata index for fast content discovery
- **Direct P2P Communication**: Establish direct peer connections using libp2p
- **Advanced Cluster Management**: Sophisticated cluster coordination including leader election, task distribution, and state synchronization
- **AI/ML Integration**: Tools for efficient batch loading from IPFS into PyTorch/TensorFlow
- **Comprehensive Error Handling**: Standardized error classes and detailed result dictionaries
- **High Performance**: Optimized for speed with features like memory-mapped file access

## Installation

```bash
# Basic installation with core functionality
pip install ipfs_kit_py

# With filesystem support (fsspec integration)
pip install ipfs_kit_py[fsspec]

# With Arrow integration for high-performance data operations
pip install ipfs_kit_py[arrow]

# With AI/ML support for model and dataset management
pip install ipfs_kit_py[ai_ml]

# With API server support (FastAPI-based HTTP server)
pip install ipfs_kit_py[api]

# With performance metrics and visualization
pip install ipfs_kit_py[performance]

# Development installation with testing tools
pip install ipfs_kit_py[dev]

# Full installation with all dependencies
pip install ipfs_kit_py[full]
```

## Quick Start

```python
# Basic usage with core API
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with default settings (leecher role)
kit = ipfs_kit()

# Add a file to IPFS
result = kit.ipfs_add("example.txt")
cid = result.get("Hash")
if cid:
    print(f"Added file with CID: {cid}")

    # Read content
    content_result = kit.ipfs_cat(cid)
    if content_result.get("success"):
        print(f"Content: {content_result.get('data')}")

    # Using the filesystem interface (requires fsspec extra)
    fs = kit.get_filesystem()
    if fs:
        with fs.open(f"ipfs://{cid}", "rb") as f:
            data = f.read()
            print(f"Read {len(data)} bytes using filesystem interface")
```

For more examples and comprehensive documentation, visit the [GitHub repository](https://github.com/endomorphosis/ipfs_kit_py/).

## Documentation

Detailed documentation is available at:
- [GitHub Repository](https://github.com/endomorphosis/ipfs_kit_py/)
- [README](https://github.com/endomorphosis/ipfs_kit_py/blob/main/README.md)
- [Documentation](https://github.com/endomorphosis/ipfs_kit_py/tree/main/docs)

## License

This project is licensed under the GNU Affero General Public License v3 or later (AGPLv3+).
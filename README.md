# IPFS Kit Python

[![Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/endomorphosis/ipfs_kit_py)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Version 0.3.0](https://img.shields.io/badge/Version-0.3.0-green)](./pyproject.toml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](./LICENSE)

**IPFS Kit Python** is a comprehensive Python toolkit for IPFS (InterPlanetary File System) operations with advanced cluster management, MCP (Model Context Protocol) server integration, and AI/ML capabilities.

## ✨ Key Features

- **🌐 High-Level IPFS API** - Simplified Python interface for IPFS operations
- **🔄 Cluster Management** - Multi-node cluster with leader election and role hierarchy
- **🤖 MCP Server Integration** - Full Model Context Protocol server support
- **📊 Advanced Caching** - Multi-tier caching with tiered storage
- **🔐 Security** - Credential management and secure configuration
- **🚀 Performance** - Async/await support, prefetching, and optimization
- **🔧 Auto-Healing** - Automated error detection and recovery
- **🐳 Container Ready** - Docker and Kubernetes deployment support
- **📈 Observability** - Comprehensive logging, metrics, and monitoring
- **🧠 AI/ML Integration** - LangChain, LlamaIndex, and transformers support

## 🚀 Quick Start

### Installation

```bash
# Install with core features
pip install ipfs_kit_py

# Install with all features
pip install ipfs_kit_py[full]

# Install for development
pip install -e .[dev]
```

### Basic Usage

```python
from ipfs_kit_py import IPFSKit

# Initialize
kit = IPFSKit()

# Add content
cid = kit.add_file("myfile.txt")
print(f"Added: {cid}")

# Get content
content = kit.cat(cid)

# Pin content
kit.pin(cid)

# List pins
pins = kit.list_pins()
```

### CLI Usage

```bash
# Start IPFS daemon
ipfs-kit daemon start

# Add file
ipfs-kit add myfile.txt

# Get file
ipfs-kit cat <CID>

# Pin management
ipfs-kit pin add <CID>
ipfs-kit pin ls

# Cluster operations
ipfs-kit cluster start
ipfs-kit cluster status
```

## 📖 Documentation

### Getting Started
- **[Installation Guide](docs/installation_guide.md)** - Detailed installation instructions
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Common commands and patterns
- **[Documentation Index](docs/README.md)** - Complete documentation navigation

### Core Documentation
- **[API Reference](docs/api/api_reference.md)** - Complete API documentation
- **[CLI Reference](docs/api/cli_reference.md)** - Command-line interface guide
- **[Core Concepts](docs/api/core_concepts.md)** - Architecture and concepts

### Features
- **[Pin Management](docs/features/pin-management/)** - Content pinning and replication
- **[Auto-Healing](docs/features/auto-healing/)** - Automated error recovery
- **[MCP Server](docs/features/mcp/)** - Model Context Protocol features
- **[Dashboard](docs/features/dashboard/)** - Web-based management interface

### Integration
- **[Integration Overview](docs/integration/INTEGRATION_OVERVIEW.md)** - Third-party integrations
- **[AI/ML Integration](docs/integration/ai-ml/)** - Machine learning features
- **[LangChain](docs/integration/langchain_integration.md)** - LangChain integration
- **[IPFS Datasets](docs/integration/IPFS_DATASETS_INTEGRATION.md)** - Dataset management

### Deployment
- **[Docker Deployment](docs/containerization.md)** - Container deployment
- **[CI/CD](docs/deployment/ci-cd/)** - Continuous integration
- **[Cluster Setup](docs/operations/cluster_management.md)** - Multi-node clusters

## 🏗️ Architecture

IPFS Kit Python is built on a modular architecture:

```
┌─────────────────────────────────────────┐
│           High-Level API                │
├─────────────────────────────────────────┤
│  Pin Mgmt  │  VFS  │  Cache  │  Index  │
├─────────────────────────────────────────┤
│      Cluster Management Layer           │
├─────────────────────────────────────────┤
│         IPFS Core Operations            │
├─────────────────────────────────────────┤
│  Kubo │ Lassie │ Lotus │ Storage Backends│
└─────────────────────────────────────────┘
```

Key Components:
- **High-Level API** - Simplified Python interface
- **Cluster Management** - Multi-node coordination
- **Storage Backends** - Pluggable storage systems
- **Caching Layer** - Multi-tier content caching
- **Metadata Index** - Fast content lookup

## 🔧 Configuration

### Basic Configuration

```python
from ipfs_kit_py import IPFSKit

kit = IPFSKit(
    ipfs_path="/path/to/.ipfs",
    cluster_mode=True,
    cache_enabled=True
)
```

### Environment Variables

```bash
# IPFS Configuration
export IPFS_PATH=/path/to/.ipfs
export IPFS_KIT_CLUSTER_MODE=true

# Auto-Healing
export IPFS_KIT_AUTO_HEAL=true
export GITHUB_TOKEN=your_token

# Logging
export LOG_LEVEL=INFO
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/unit/
pytest tests/integration/

# Run with coverage
pytest --cov=ipfs_kit_py --cov-report=html
```

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Repository:** https://github.com/endomorphosis/ipfs_kit_py
- **Documentation:** [docs/](docs/)
- **Issues:** https://github.com/endomorphosis/ipfs_kit_py/issues
- **PyPI:** (coming soon)

## 🙏 Acknowledgments

Built with:
- [IPFS/Kubo](https://github.com/ipfs/kubo) - InterPlanetary File System
- [py-libp2p](https://github.com/libp2p/py-libp2p) - LibP2P networking
- [PyArrow](https://arrow.apache.org/docs/python/) - Columnar data processing
- [FastAPI](https://fastapi.tiangolo.com/) - API framework

## 📊 Project Status

- ✅ Core IPFS operations
- ✅ Cluster management
- ✅ MCP server integration
- ✅ Docker/Kubernetes support
- ✅ Auto-healing system
- ✅ AI/ML integrations
- 🚧 Additional storage backends
- 📋 PyPI package release

---

**Version:** 0.3.0  
**Python:** 3.12+  
**Status:** Production Ready

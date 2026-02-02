# IPFS Kit Python

[![Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/endomorphosis/ipfs_kit_py)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Version 0.3.0](https://img.shields.io/badge/Version-0.3.0-green)](./pyproject.toml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](./LICENSE)

**IPFS Kit Python** is a comprehensive, production-ready Python toolkit for building distributed storage applications on IPFS. It provides high-level APIs, advanced cluster management, AI/ML integration, and seamless MCP (Model Context Protocol) server support for modern decentralized applications.

## 🎯 What Can You Do With This?

### For Developers
- **Build Decentralized Apps**: High-level Python API for IPFS without complexity
- **Scale with Clusters**: Multi-node cluster management with automatic replication
- **Integrate AI Models**: Store and retrieve ML models/datasets on IPFS
- **Create Storage Services**: Production-ready foundation for IPFS-based services

### For Data Scientists
- **Distributed Datasets**: Store and share large datasets across IPFS network
- **Model Versioning**: Track and distribute ML models with content addressing
- **Reproducible Research**: Immutable data storage with cryptographic verification
- **Collaborative Workflows**: Share data and models via IPFS with team members

### For DevOps/SRE
- **High Availability**: Multi-node clusters with leader election and failover
- **Observability**: Built-in metrics, logging, and monitoring
- **Container Native**: Docker and Kubernetes ready deployment
- **Auto-Healing**: Automatic error detection and recovery system

## ✨ Key Features

### Core IPFS Operations
- **🌐 High-Level API**: Simplified Python interface wrapping IPFS complexity
- **📦 Content Management**: Add, get, pin, and manage content with ease
- **🔗 IPNS Support**: Mutable pointers to immutable IPFS content
- **📊 Directory Operations**: Work with IPFS directories and file structures
- **🔍 Content Discovery**: Find and retrieve content across the IPFS network

### Advanced Cluster Management
- **🔄 Multi-Node Clusters**: Deploy 3+ node clusters with role hierarchy
- **👑 Leader Election**: Automatic leader selection and failover
- **🎭 Role-Based**: Master, Worker, and Leecher role management
- **📈 Auto-Scaling**: Automatically replicate content based on demand
- **🔗 Peer Management**: Dynamic peer discovery and connection handling
- **💾 Distributed Storage**: Spread content across multiple nodes

### AI/ML Integration
- **🤖 Model Registry**: Store and version ML models on IPFS
- **📊 Dataset Management**: Manage large datasets with IPFS chunking
- **�� Framework Support**: LangChain, LlamaIndex, Transformers integration
- **📉 Metrics Tracking**: Model performance metrics and visualization
- **🧮 Distributed Training**: Share training data across nodes
- **🎯 Vector Search**: GraphRAG and knowledge graph integration

### MCP Server
- **🌟 Production Ready**: Full-featured MCP server implementation
- **🛠️ Tool Integration**: Expose IPFS operations as MCP tools
- **🔌 Plugin System**: Extensible architecture for custom tools
- **📡 Real-Time**: WebSocket support for streaming operations
- **🎨 Dashboard**: Web-based management and monitoring interface
- **🔐 Secure**: Built-in authentication and authorization

### Storage & Performance
- **📦 Tiered Storage**: Multi-tier caching (memory, SSD, network)
- **⚡ High Performance**: Async/await throughout for concurrency
- **🔄 Write-Ahead Log**: Crash recovery and data consistency
- **🗜️ Compression**: Automatic compression for large files
- **📊 Metadata Index**: Fast content lookup and search
- **🚀 Prefetching**: Predictive content loading for speed

### Operations & Monitoring
- **🔍 Observability**: Prometheus metrics, structured logging, tracing
- **🏥 Health Checks**: Built-in health endpoints for monitoring
- **🔧 Auto-Healing**: Detect and fix common errors automatically
- **📈 Performance Metrics**: Real-time performance tracking
- **🎛️ Configuration**: Flexible YAML/JSON configuration
- **🔔 Alerting**: Integration with monitoring systems

### Deployment & Integration
- **🐳 Docker Ready**: Multi-arch Docker images (AMD64, ARM64)
- **☸️ Kubernetes**: Helm charts and operator support
- **🔄 CI/CD**: GitHub Actions workflows included
- **🌐 Cloud Native**: Deploy on any cloud provider
- **🔌 Extensible**: Plugin system for custom functionality
- **📚 Well Documented**: Comprehensive guides and examples

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Applications Layer                       │
│   (Your App, CLI, Web Dashboard, API Services)               │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    High-Level API                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │  IPFS    │  │ Cluster  │  │  AI/ML   │  │   MCP      │ │
│  │  Ops     │  │  Mgmt    │  │  Tools   │  │  Server    │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   Core Services Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Tiered   │  │  WAL &   │  │ Metadata │  │   Pin      │ │
│  │  Cache   │  │ Journal  │  │  Index   │  │  Manager   │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    IPFS Daemon Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │   Kubo   │  │  Cluster │  │  Lotus   │  │  Lassie    │ │
│  │  (IPFS)  │  │ Service  │  │(Filecoin)│  │ (Retrieval)│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Installation

```bash
# Install core features
pip install ipfs_kit_py

# Install with AI/ML support
pip install ipfs_kit_py[ai_ml]

# Install with all features
pip install ipfs_kit_py[full]

# Development installation
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
pip install -e .[dev]
```

### Basic Usage

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize
api = IPFSSimpleAPI()

# Add content
result = api.add("Hello, IPFS!")
cid = result['cid']
print(f"Content added: {cid}")

# Retrieve content
content = api.get(cid)
print(f"Retrieved: {content}")

# Pin content for persistence
api.pin(cid)

# List all pins
pins = api.list_pins()
```

### Cluster Operations

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize as cluster master
api = IPFSSimpleAPI(role="master")

# Add content to cluster (distributed across nodes)
result = api.cluster_add("large_file.dat", replication_factor=3)

# Check replication status
status = api.cluster_status(result['cid'])
print(f"Replicated on {len(status['peers'])} nodes")

# List cluster peers
peers = api.cluster_peers()
```

### AI/ML Integration

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
import pandas as pd

api = IPFSSimpleAPI()

# Store dataset
df = pd.read_csv("training_data.csv")
result = api.ai_dataset_add(
    dataset=df,
    metadata={
        "name": "customer_data_v1",
        "version": "1.0",
        "description": "Customer behavior dataset"
    }
)

# Retrieve dataset later
dataset_cid = result['cid']
loaded_df = api.ai_dataset_get(dataset_cid)
```

### CLI Usage

```bash
# Start MCP server with dashboard
ipfs-kit mcp start --port 8004

# Check server status
ipfs-kit mcp status

# View deprecation warnings
ipfs-kit mcp deprecations

# Start 3-node cluster
python tools/start_3_node_cluster.py
```

## 📚 Documentation

Comprehensive documentation available in [docs/](docs/):

- **[Installation Guide](docs/installation_guide.md)** - Setup and requirements
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Common operations
- **[API Reference](docs/api/api_reference.md)** - Complete API docs
- **[Cluster Guide](docs/operations/cluster_management.md)** - Cluster setup
- **[AI/ML Integration](docs/integration/ai-ml/)** - Machine learning features
- **[MCP Server](docs/features/mcp/)** - MCP server documentation
- **[Examples](examples/)** - Code examples and tutorials

## 🎓 Use Cases & Examples

### 1. Decentralized Application Storage
```python
# Store application data immutably
api = IPFSSimpleAPI()
user_data = {"user_id": 123, "preferences": {...}}
cid = api.add(json.dumps(user_data))['cid']

# Share CID with users - data is permanently accessible
return f"ipfs://{cid}"
```

### 2. ML Model Distribution
```python
# Publish trained model
model_path = "model.h5"
result = api.ai_model_add(
    model=load_model(model_path),
    metadata={"architecture": "ResNet50", "accuracy": 0.95}
)

# Others can load your model
model = api.ai_model_get(result['cid'])
```

### 3. Content Distribution Network
```python
# Deploy content across cluster
api = IPFSSimpleAPI(role="master")
for file in website_files:
    api.cluster_add(file, replication_factor=5)

# Content automatically available on all nodes
```

### 4. Data Backup & Archival
```python
# Backup with verification
result = api.add("important_data.zip", pin=True)
cid = result['cid']

# Later verification
assert api.exists(cid), "Backup lost!"
restored_data = api.get(cid)
```

## 🔧 Configuration

### Basic Configuration

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI(
    role="master",  # master, worker, or leecher
    resources={
        "max_memory": "2GB",
        "max_storage": "100GB"
    },
    cache={
        "memory_size": "500MB",
        "disk_size": "5GB"
    },
    timeouts={
        "api": 60,
        "gateway": 120
    }
)
```

### Environment Variables

```bash
# IPFS configuration
export IPFS_PATH=/path/to/.ipfs
export IPFS_KIT_CLUSTER_MODE=true

# MCP server
export IPFS_KIT_MCP_PORT=8004
export IPFS_KIT_DATA_DIR=~/.ipfs_kit

# Performance tuning
export IPFS_KIT_CACHE_SIZE=1GB
export IPFS_KIT_MAX_CONNECTIONS=50
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

# Run cluster tests
pytest tests/test_cluster_startup.py -v
```

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📋 Requirements

- **Python:** 3.12+ required
- **System:** Linux (primary), macOS (supported), Windows (experimental)
- **Memory:** 4GB minimum, 8GB recommended for clusters
- **Storage:** 10GB minimum, 50GB+ recommended for production
- **Network:** Internet access for IPFS network connectivity

## 🗺️ Roadmap

- [ ] Enhanced GraphRAG integration
- [ ] S3-compatible gateway
- [ ] WebAssembly support
- [ ] Mobile SDK (iOS/Android)
- [ ] Enhanced analytics dashboard
- [ ] Multi-region cluster support

## 📜 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with:
- [IPFS/Kubo](https://github.com/ipfs/kubo) - InterPlanetary File System
- [IPFS Cluster](https://github.com/ipfs-cluster/ipfs-cluster) - Cluster orchestration
- [py-libp2p](https://github.com/libp2p/py-libp2p) - LibP2P networking
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework

## 📞 Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/endomorphosis/ipfs_kit_py/issues)
- **Discussions:** [GitHub Discussions](https://github.com/endomorphosis/ipfs_kit_py/discussions)

## 📊 Project Status

- ✅ Core IPFS operations - Production ready
- ✅ Cluster management - Production ready
- ✅ MCP server - Production ready
- ✅ AI/ML integration - Beta
- ✅ Auto-healing - Beta
- 🚧 GraphRAG - In development
- 📋 S3 Gateway - Planned

---

**Version:** 0.3.0  
**Status:** Production Ready  
**Maintained by:** Benjamin Barber ([@endomorphosis](https://github.com/endomorphosis))

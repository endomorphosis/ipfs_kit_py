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
│                     Applications Layer                      │
│   (Your App, CLI, Web Dashboard, API Services)              │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    High-Level API                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐   │
│  │  IPFS    │  │ Cluster  │  │  AI/ML   │  │   MCP      │   │
│  │  Ops     │  │  Mgmt    │  │  Tools   │  │  Server    │   │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   Core Services Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐   │
│  │ Tiered   │  │  WAL &   │  │ Metadata │  │   Pin      │   │
│  │  Cache   │  │ Journal  │  │  Index   │  │  Manager   │   │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    IPFS Daemon Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐   │
│  │   Kubo   │  │  Cluster │  │  Lotus   │  │  Lassie    │   │
│  │  (IPFS)  │  │ Service  │  │(Filecoin)│  │ (Retrieval)│   │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 🗄️ Storage Architecture & Backends

### Multi-Backend Storage System

IPFS Kit supports **6 integrated storage backends** for maximum flexibility and redundancy:

1. **IPFS/Kubo** - Decentralized content-addressed storage
2. **Filecoin/Lotus** - Long-term archival with economic incentives
3. **S3-Compatible** - AWS S3, MinIO, and other S3-compatible services
4. **Storacha (Web3.Storage)** - Web3 storage built on IPFS + Filecoin
5. **HuggingFace** - ML model and dataset storage
6. **Lassie** - High-performance IPFS retrieval client

### Multi-Tier Storage Strategy

```
┌─────────────────────────────────────────────────────────────┐
│  Tier 1: Memory Cache (100MB default)                       │
│  • Fastest access (microseconds)                            │
│  • Hot content, recently accessed                           │
│  • ARC algorithm (Adaptive Replacement Cache)               │
└────────────────────────┬────────────────────────────────────┘
                         │ Auto-promotion/demotion
┌────────────────────────▼────────────────────────────────────┐
│  Tier 2: Disk Cache (1GB+ default)                          │
│  • Fast persistent storage (milliseconds)                   │
│  • Warm content, frequently accessed                        │
│  • Heat-based eviction, zero-copy mmap                      │
└────────────────────────┬────────────────────────────────────┘
                         │ Overflow & long-term
┌────────────────────────▼────────────────────────────────────┐
│  Tier 3: IPFS Network                                        │
│  • Distributed content-addressed storage                    │
│  • Peer discovery, automatic replication                    │
│  • DHT-based content routing                                │
└────────────────────────┬────────────────────────────────────┘
                         │ Backup & durability
┌────────────────────────▼────────────────────────────────────┐
│  Tier 4: Cloud Backends (S3, Storacha, Filecoin)            │
│  • Long-term archival, geographical distribution            │
│  • Economic persistence, compliance storage                 │
│  • Cross-region replication                                 │
└─────────────────────────────────────────────────────────────┘
```

### Storage Backend Configuration

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize with multiple backends
api = IPFSSimpleAPI(
    storage_backends={
        'ipfs': {'enabled': True},
        'filecoin': {
            'enabled': True,
            'lotus_path': '/path/to/lotus'
        },
        's3': {
            'enabled': True,
            'bucket': 'my-ipfs-backup',
            'region': 'us-west-2'
        },
        'storacha': {
            'enabled': True,
            'token': 'your_token',
            'space': 'your_space_did'
        }
    }
)

# Content automatically distributed across backends
cid = api.add("important_data.txt", backends=['ipfs', 'filecoin', 's3'])
```

**See Also:** [Storage Backends Documentation](docs/reference/storage_backends.md)

## 🔄 Replica Management

### Replication Strategies

IPFS Kit provides sophisticated replica management for high availability and data durability:

**Cluster-Based Replication:**
```python
# Set replication factor for automatic distribution
api = IPFSSimpleAPI(role="master")

# Add content with 3 replicas across cluster
result = api.cluster_add(
    "dataset.tar.gz",
    replication_factor=3,  # Distribute to 3 nodes
    replication_policy="distributed"  # Strategy: distributed, local-first, geo-aware
)

# Check replication status
status = api.cluster_status(result['cid'])
print(f"Replicas: {len(status['peers'])} nodes")
print(f"Locations: {status['peer_locations']}")
```

**Pin Management with Replication:**
```python
# Pin with min/max replica constraints
api.pin_add(
    cid,
    replication_min=2,  # Minimum 2 copies
    replication_max=5,  # Maximum 5 copies
    replication_priority="high"  # Auto-repair if below min
)

# Monitor replica health
health = api.get_replication_health(cid)
# Returns: {'total': 3, 'healthy': 3, 'degraded': 0, 'locations': [...]}
```

**Replication Policies:**
- **Distributed**: Spread replicas across maximum geographic/network distance
- **Local-First**: Keep replicas in nearby nodes first, then expand
- **Geo-Aware**: Place replicas in specific regions or datacenters
- **Cost-Optimized**: Balance between redundancy and storage costs
- **Latency-Optimized**: Replicate to nodes with best access patterns

**Automatic Repair:**
```python
# Enable auto-repair for critical content
api.enable_auto_repair(
    cid,
    check_interval=3600,  # Check every hour
    repair_threshold=2,   # Repair if below 2 replicas
    target_replicas=3     # Maintain 3 replicas
)
```

**See Also:** [Cluster Management](docs/operations/cluster_management.md), [Pin Management](docs/features/pin-management/)

## 💾 Multi-Tier Caching System

### Advanced Caching with ARC Algorithm

IPFS Kit implements a sophisticated **Adaptive Replacement Cache (ARC)** with multiple tiers:

**Cache Tiers:**

1. **Memory Cache (T1/T2)**
   - ARC algorithm balances recency vs frequency
   - Configurable size (default: 100MB)
   - Submillisecond access times
   - Automatic size-based decisions

2. **Disk Cache**
   - Persistent across restarts
   - Heat-based eviction (access patterns + recency)
   - Memory-mapped for zero-copy access
   - Configurable size (default: 1GB+)

3. **Network Cache**
   - IPFS network acts as distributed cache
   - Content-addressed retrieval
   - Peer caching benefits

### Cache Configuration

```python
from ipfs_kit_py.tiered_cache import TieredCacheManager

# Custom cache configuration
cache = TieredCacheManager(
    config={
        'memory_cache_size': 500 * 1024 * 1024,  # 500MB
        'disk_cache_size': 10 * 1024 * 1024 * 1024,  # 10GB
        'disk_cache_path': '/fast/ssd/cache',
        'enable_mmap': True,  # Zero-copy for large files
        'eviction_policy': 'heat',  # heat, lru, lfu
        'promotion_threshold': 3,  # Access count for promotion
    }
)

# Cache operations (automatic tier selection)
cache.put(cid, content)  # Intelligent tier placement
content = cache.get(cid)  # Fastest available tier

# Cache statistics
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Memory: {stats['memory_usage']}, Disk: {stats['disk_usage']}")
```

### Cache Policies

**Heat Scoring** - Combines multiple factors:
- Access frequency (recent access count)
- Recency (time since last access)
- Content size (smaller = higher priority)
- Access pattern (sequential vs random)

**Automatic Optimization:**
- Content promoted from disk → memory on repeated access
- Large files use memory-mapped I/O (no duplication)
- Rarely accessed content demoted to network tier
- Cache pre-warming for predictable workloads

**See Also:** [Tiered Cache Documentation](docs/reference/tiered_cache.md)

## 📁 VFS Buckets & Virtual Filesystem

### Virtual Filesystem (VFS) Operations

IPFS Kit provides a **POSIX-like virtual filesystem** on top of IPFS, enabling familiar file operations:

```python
from ipfs_kit_py.vfs_manager import get_global_vfs_manager

vfs = get_global_vfs_manager()

# File operations (like regular filesystem)
vfs.mkdir("/data/projects")
vfs.write("/data/projects/notes.txt", "Project notes...")
content = vfs.read("/data/projects/notes.txt")

# Directory operations
files = vfs.ls("/data/projects")
vfs.mv("/data/projects/old", "/data/archive/old")
vfs.rm("/data/temp/cache.db")

# Batch operations
vfs.copy_recursive("/data/input", "/data/processed")
```

### VFS Buckets

**Buckets** are isolated namespaces within the VFS for organizing content:

```python
# Create and manage buckets
vfs.create_bucket("ml-models", quota="10GB", policy="hot")
vfs.create_bucket("datasets", quota="100GB", policy="warm")
vfs.create_bucket("archive", quota="1TB", policy="cold")

# Bucket operations
vfs.write("/ml-models/resnet50.h5", model_data)
vfs.set_bucket_policy("ml-models", {
    'replication': 3,
    'cache_priority': 'high',
    'backup_schedule': 'daily'
})

# List buckets and usage
buckets = vfs.list_buckets()
for bucket in buckets:
    print(f"{bucket['name']}: {bucket['used']}/{bucket['quota']}")
```

### VFS Features

**Journaling & Change Tracking:**
```python
# Filesystem journal tracks all changes
journal = vfs.get_journal(since="2024-01-01")
for entry in journal:
    print(f"{entry['timestamp']}: {entry['operation']} {entry['path']}")

# Replicate changes to other nodes
vfs.replicate_journal(target_node="node2.example.com")
```

**Metadata & Indexing:**
```python
# Automatic metadata extraction and indexing
vfs.write("/docs/paper.pdf", pdf_data, 
    metadata={'author': 'Smith', 'year': 2024})

# Enhanced pin index for fast lookup
results = vfs.search(query="machine learning", content_type="pdf")
```

**See Also:** [VFS Management](docs/features/vfs/), [Filesystem Journal](docs/filesystem_journal.md)

## 🧠 GraphRAG & Knowledge Graphs

### Intelligent Search with GraphRAG

IPFS Kit integrates **GraphRAG** (Graph-based Retrieval Augmented Generation) for semantic search and knowledge management:

**Automatic Content Indexing:**
```python
# All VFS operations auto-index content
vfs.write("/docs/research.md", markdown_content)
# → Automatic entity extraction, relationship mapping, graph building

# Search across indexed content
results = api.search_text("quantum computing applications")
results = api.search_graph("quantum computing", max_depth=2)
results = api.search_vector("semantic similarity query", threshold=0.7)
```

### Knowledge Graph Features

**Entity Recognition:**
- Automatic extraction of people, places, organizations, concepts
- Relationship mapping between entities
- RDF triple store for structured knowledge
- Graph analytics (centrality, importance scoring)

**Search Methods:**

1. **Text Search** - Full-text with relevance scoring
2. **Graph Search** - Traverse knowledge graph connections
3. **Vector Search** - Semantic similarity using embeddings
4. **SPARQL Queries** - Structured RDF queries
5. **Hybrid Search** - Combine multiple methods

```python
# Hybrid search combines all methods
results = api.search_hybrid(
    query="AI model deployment",
    search_types=["text", "graph", "vector"],
    limit=20,
    min_score=0.6
)

# SPARQL for structured queries
results = api.search_sparql("""
    SELECT ?model ?accuracy ?dataset
    WHERE {
        ?model rdf:type :MLModel .
        ?model :accuracy ?accuracy .
        ?model :trainedOn ?dataset .
        FILTER (?accuracy > 0.95)
    }
""")
```

**Graph Analytics:**
```python
# Analyze knowledge graph
stats = api.search_stats()
print(f"Entities: {stats['entity_count']}")
print(f"Relationships: {stats['relation_count']}")
print(f"Indexed documents: {stats['document_count']}")

# Find important entities
important = api.get_top_entities(limit=10, metric="centrality")
```

**See Also:** [GraphRAG Documentation](docs/features/graphrag/), [Knowledge Graph](docs/knowledge_graph.md)

## 🔐 Configuration & Secrets Management

### Secure Credential Management

IPFS Kit provides a **unified credential manager** for securely storing API keys, tokens, and credentials:

```python
from ipfs_kit_py.credential_manager import CredentialManager

cred_manager = CredentialManager()

# Add credentials for different services
cred_manager.add_s3_credentials(
    name="production",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="secret...",
    region_name="us-west-2"
)

cred_manager.add_storacha_credentials(
    name="default",
    api_token="your_token",
    space_did="did:web:..."
)

cred_manager.add_filecoin_credentials(
    name="mainnet",
    api_key="fil_api_key"
)

# Retrieve credentials securely
s3_creds = cred_manager.get_s3_credentials("production")
storacha_token = cred_manager.get_storacha_credentials()
```

### Configuration Management

**YAML Configuration:**
```yaml
# ~/.ipfs_kit/config.yaml
storage:
  backends:
    ipfs:
      enabled: true
      api_addr: "/ip4/127.0.0.1/tcp/5001"
    
    filecoin:
      enabled: true
      lotus_path: "/path/to/lotus"
    
    s3:
      enabled: true
      credential_name: "production"
      bucket: "ipfs-backup"
      region: "us-west-2"
    
    storacha:
      enabled: true
      credential_name: "default"

cache:
  memory_size: 500MB
  disk_size: 10GB
  disk_path: "/fast/ssd/cache"

cluster:
  role: "master"
  replication_factor: 3
  peers:
    - "/ip4/10.0.0.2/tcp/9096"
    - "/ip4/10.0.0.3/tcp/9096"

vfs:
  buckets:
    ml-models:
      quota: 10GB
      policy: hot
      replication: 3
    datasets:
      quota: 100GB
      policy: warm
      replication: 2
```

### Environment Variables

```bash
# Credentials
export IPFS_KIT_S3_ACCESS_KEY="AKIA..."
export IPFS_KIT_S3_SECRET_KEY="secret..."
export W3_STORE_TOKEN="storacha_token"
export FILECOIN_API_KEY="fil_api_key"

# Configuration
export IPFS_PATH="/custom/ipfs/path"
export IPFS_KIT_CONFIG="/custom/config.yaml"
export IPFS_KIT_CACHE_DIR="/fast/ssd/cache"

# Feature flags
export IPFS_KIT_ENABLE_GRAPHRAG="true"
export IPFS_KIT_ENABLE_AUTO_HEALING="true"
```

### Security Best Practices

**Credential Storage:**
- Store credentials in `~/.ipfs_kit/credentials.json` with `chmod 600`
- Never commit credentials to version control
- Use environment variables in CI/CD
- Consider system keyring integration for production

**Configuration Security:**
- Separate configs for dev/staging/prod
- Use secrets management services (AWS Secrets Manager, Vault)
- Rotate credentials regularly
- Audit access logs

**See Also:** [Credential Management](docs/credential_management.md), [Secure Credentials Guide](docs/guides/SECURE_CREDENTIALS_GUIDE.md)

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

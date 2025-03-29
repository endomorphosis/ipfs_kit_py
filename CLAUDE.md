# CLAUDE.md - ipfs_kit_py Developer Guide

## Table of Contents
1. [Development Environment](#development-environment)
2. [Current Codebase Analysis](#current-codebase-analysis)
3. [Development Roadmap](#development-roadmap)
4. [Technical Implementation Plan](#technical-implementation-plan)
5. [Advanced Features](#advanced-features)
6. [Technology Selection Guidelines](#technology-selection-guidelines)

## Development Environment

### Build & Test Commands
- **Install**: `pip install -e .`
- **Build**: `python setup.py build`
- **Run all tests**: `python -m test.test`
- **Run single test**: `python -m test.test_ipfs_kit` or `python -m test.test_storacha_kit`
- **Run API server**: `uvicorn ipfs_kit_py.api:app --reload --port 8000`
- **Generate AST**: `python -m astroid ipfs_kit_py > ast_analysis.json`
- **Check for duplications**: `pylint --disable=all --enable=duplicate-code ipfs_kit_py`

### Development Guidelines
- **Test-First Development**: All new features must first be developed in the test/ folder
- **Feature Isolation**: Do not modify code outside of test/ until fully debugged
- **API Exposure**: All functionality should be exposed via FastAPI endpoints
- **Performance Focus**: Use memory-mapped structures and Arrow C Data Interface for low-latency IPC
- **Code Analysis**: Maintain an abstract syntax tree (AST) of the project to identify and prevent code duplication
- **DRY Principle**: Use the AST to enforce Don't Repeat Yourself by detecting similar code structures

### Required Dependencies
- Python >=3.8
- requests, multiformats, boto3

### Code Style Guidelines
- **Imports**: Standard library first, third-party next
- **Formatting**: 4-space indentation
- **Classes**: Initialize with `__init__(self, resources=None, metadata=None)`, end with `return None`
- **Naming**: snake_case for methods/variables, PascalCase for classes
- **Method Structure**: Methods typically accept `self, resources, metadata` parameters
- **Error Handling**: Use try/except blocks with results dictionary for error collection
- **Subprocess Pattern**: Use subprocess.run() with captured output for system commands
- **Testing Style**: Test classes follow `test_*` naming pattern with `init` and `test` methods

## Current Codebase Analysis

### Core Architecture
The ipfs_kit_py module implements a layered architecture with several key components:

1. **ipfs_kit**: Main orchestrator class providing a unified interface
2. **ipfs_py**: Handles low-level IPFS (Kubo) daemon operations with UnixFS integration
3. **storacha_kit**: Provides Web3.Storage integration
4. **s3_kit**: Manages S3-compatible storage operations
5. **ipfs_multiformats_py**: Handles CID creation and multihash operations

### Class Hierarchy
```
┌───────────────────────────────────────────────────────────┐
│                        ipfs_kit                           │
└───────────┬──────────┬──────────┬───────────┬─────────────┘
            │          │          │           │
            ▼          ▼          ▼           ▼
┌──────────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐
│   ipfs_py    │ │  ipget  │ │ s3_kit  │ │ storacha_kit  │
└──────────────┘ └─────────┘ └─────────┘ └───────────────┘
       │
       │
       ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│ ipfs_cluster_service │◄───┤ Based on role (master only) │
└──────────────────────┘    └─────────────────────────────┘
       │
       │
       ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│   ipfs_cluster_ctl   │◄───┤ Based on role (master only) │
└──────────────────────┘    └─────────────────────────────┘
       │
       │
       ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│ ipfs_cluster_follow  │◄───┤ Based on role (worker only) │
└──────────────────────┘    └─────────────────────────────┘
```

### Key Design Patterns
- **Role-based architecture**: Three roles - "master", "worker", "leecher"
- **Facade pattern**: ipfs_kit provides unified interface to underlying components
- **Delegation**: Components handle specific responsibilities
- **Error aggregation**: Results dictionaries collect operation outcomes

### API Integration Points
- **IPFS HTTP API**: REST interface (localhost:5001/api/v0) for core IPFS operations
- **IPFS Cluster API**: REST interface (localhost:9094/api/v0) for cluster coordination
- **IPFS Cluster Proxy**: Proxied IPFS API (localhost:9095/api/v0)
- **IPFS Gateway**: Content retrieval via HTTP (localhost:8080/ipfs/[cid])
- **IPFS Socket Interface**: Unix socket for high-performance local communication (/ip4/127.0.0.1/tcp/4001)

These APIs enable creating "swarms of swarms" by allowing distributed clusters to communicate across networks and coordinate content pinning, replication, and routing across organizational boundaries. The socket interface provides lower-latency communication for high-performance local operations.

### Areas for Improvement
- **Code Structure**: Reduce duplication, improve cohesion, follow single responsibility principle
- **Error Handling**: Standardize approach, preserve stack traces, create error hierarchies
- **Documentation**: Add docstrings, type annotations, parameter validation
- **Testing**: Separate test code from implementation, increase unit test coverage
- **Code Quality**: Address redundant imports, string concatenation, security risks in subprocess calls
- **Code Duplication**: Use AST analysis to identify similar code patterns across modules
- **Refactoring**: Extract common patterns into reusable abstractions guided by AST similarity detection

## Development Roadmap

### 1. Tiered Storage with Adaptive Replacement Cache
- Implement fsspec filesystem interface for unified access to all storage backends
- Develop adaptive replacement cache (ARC) with data "heat" tracking
- Hierarchical eviction strategy prioritizing:
  1. Local cache (fastest, limited capacity)
  2. IPFS node cache (fast, larger capacity)
  3. IPFS cluster (distributed redundancy)
  4. S3 storage (reliable, moderate cost)
  5. Storacha (durable, potentially higher latency)
  6. Filecoin (highest durability, lowest cost, highest latency)
- Performance metrics collection and bandwidth optimization
- Implement libp2p_py for direct peer connections to share IPFS CIDs

### 2. High-Performance Metadata Management
- Apache Arrow-based routing index for metadata
- Parquet-based persistence for durability
- Columnar structure for efficient queries
- Memory-mapped files for near-instant startup
- Delta updates to minimize write amplification
- Partitioning for parallel processing
- Distributed index synchronization

### 3. IPLD-Based Knowledge Graph and Vector Storage
- Store embedding vectors in IPLD structures
- Implement knowledge graph components:
  - Entities as IPLD nodes with CIDs as identifiers
  - Relationships as IPLD links between nodes
  - Attributes as node properties
- GraphRAG search capabilities:
  - Hybrid vector + graph traversal retrieval
  - Semantic similarity via embedding vectors
  - Graph relationship traversal
  - Weighted path scoring
- Specialized IPLD schemas for vector data types
- Efficient nearest-neighbor search over IPLD-stored vectors
- Memory-mapped vector indexes for fast similarity search

## Technical Implementation Plan

### New Dependencies
```
fsspec>=2023.3.0
pyarrow>=12.0.0
lru-dict>=1.2.0
cachetools>=5.3.0
filecoin-api-client>=0.9.0
multiaddr>=0.0.9
base58>=2.1.1
eth-account>=0.8.0
web3>=6.5.0
fastapi>=0.100.0  # For API server
uvicorn>=0.22.0   # ASGI server for FastAPI
pydantic>=2.0.0   # For data validation
faiss-cpu>=1.7.4  # For vector search
networkx>=3.0     # For knowledge graph operations
multiprocessing>=0.70.14  # For parallel processing
mmap-backed-array>=0.7.0  # For shared memory arrays
astroid>=2.15.0   # For AST generation and code analysis
pylint>=2.17.0    # For code quality checks with AST support
libp2p-py>=0.2.0  # For direct peer-to-peer connections
```

### New Classes

#### FSSpecIPFSFileSystem
```python
class FSSpecIPFSFileSystem(AbstractFileSystem):
    """FSSpec-compatible filesystem interface with ARC caching."""
    
    def __init__(self, ipfs_path=None, cache_size=1024, cache_ttl=3600, use_mmap=True, **kwargs):
        # Initialization with ARC cache configuration
        # use_mmap enables memory-mapped files for low-latency access
        
    def _open(self, path, mode="rb", **kwargs):
        # Open file with tiered access strategy
        
    def ls(self, path, detail=True, **kwargs):
        # List objects with metadata
        
    def to_arrow_dataset(self, path_or_paths, **kwargs):
        # Convert IPFS directory contents to Arrow dataset
```

#### IPFSLibp2pPeer
```python
class IPFSLibp2pPeer:
    """Direct peer-to-peer connection interface with libp2p_py."""
    
    def __init__(self, host_id=None, bootstrap_peers=None, listen_addr="/ip4/0.0.0.0/tcp/0"):
        # Initialize libp2p node with host identity
        # Connect to bootstrap peers if provided
        
    def connect_peer(self, peer_id, addrs=None):
        # Establish direct connection to a peer
        
    def broadcast_cid(self, cid, metadata=None):
        # Announce availability of a CID to connected peers
        
    def request_content(self, cid, timeout=60):
        # Request content by CID from connected peers
        
    def start_discovery(self, rendezvous_string="ipfs-discovery"):
        # Start mDNS and DHT-based peer discovery
        
    def register_protocol_handler(self, protocol_id, handler_func):
        # Register custom protocol handler for specialized peer interactions
```

#### IPFSAPIServer
```python
class IPFSAPIServer:
    """FastAPI server exposing IPFS operations as REST endpoints."""
    
    def __init__(self, filesystem, host="0.0.0.0", port=8000):
        # Initialize FastAPI app with filesystem reference
        
    def setup_routes(self):
        # Configure API endpoints
        
    def start(self, debug=False):
        # Launch the server with uvicorn
```

#### IPFSMultiprocessManager
```python
class IPFSMultiprocessManager:
    """Manages multiprocessing workers for IPFS operations."""
    
    def __init__(self, num_workers=None, shared_mem_size=1024*1024*100):
        # Initialize worker pool and shared memory
        
    def create_shared_array(self, shape, dtype):
        # Create mmap-backed array for data sharing between processes
        
    def run_parallel(self, func, items):
        # Distribute work across processes with shared memory IPC
```

#### IPFSArrowIndex
```python
class IPFSArrowIndex:
    """Arrow-based routing index for IPFS metadata."""
    
    def __init__(self, index_path=None, schema=None):
        # Initialize with schema definition
        
    def create_schema(self):
        # Define Arrow schema for metadata
        
    def load(self, path=None):
        # Load index from Parquet
```

#### IPLDVectorStore
```python
class IPLDVectorStore:
    """IPLD-based vector storage for embeddings."""
    
    def __init__(self, dimension=768, metric="cosine"):
        # Initialize vector store with dimension and similarity metric
        
    def add_vectors(self, vectors, metadata=None):
        # Store vectors in IPLD format
        
    def search(self, query_vector, top_k=10):
        # Perform vector similarity search
        
    def export_to_ipld(self):
        # Export vector index as IPLD structure
```

#### IPLDKnowledgeGraph
```python
class IPLDKnowledgeGraph:
    """Knowledge graph using IPLD for storage."""
    
    def __init__(self):
        # Initialize graph store
        
    def add_entity(self, entity_data):
        # Add entity node to graph
        
    def add_relationship(self, source_cid, target_cid, relationship_type):
        # Add relationship between entities
        
    def query(self, start_entity, relationship_path):
        # Query graph following relationship paths
        
    def vector_augmented_query(self, query_vector, relationship_constraints):
        # GraphRAG query combining vector similarity and graph traversal
```

### Implementation Phases

#### Phase 1: FSSpec Filesystem Interface (3 weeks)
- FSSpec adapter implementation
- Adaptive replacement cache
- Integration with existing IPFS methods
- Performance optimization
- FastAPI server exposure for RESTful access
- Test-driven development in test/ folder only until features are fully debugged
- Multiprocessing implementation with memory queues (mmap or Arrow C Data Interface) for low-latency IPC
- AST-based code analysis to detect and prevent duplication across components

#### Phase 2: Arrow-based Metadata Index (4 weeks)
- Schema design
- Parquet persistence
- Query mechanisms
- Performance benchmarking

#### Phase 3: Storage Tier Integration (5 weeks)
- S3, Storacha, and Filecoin integration
- Deal management
- Cost optimization
- Error handling

#### Phase 4: IPLD Vector and Graph Storage (6 weeks)
- IPLD schemas for vector data
- Knowledge graph implementation
- GraphRAG search capabilities
- Vector indexes

#### Phase 5: Integration and Optimization (3 weeks)
- Component integration
- End-to-end workflows
- Performance optimization
- Documentation
- Comprehensive AST analysis of entire codebase
- Final refactoring of duplicative patterns

### Estimated Effort

| Phase | Duration | Effort (person-days) |
|-------|----------|----------------------|
| FSSpec Filesystem Interface | 3 weeks | 30 person-days |
| Arrow-based Metadata Index | 4 weeks | 40 person-days |
| Storage Tier Integration | 5 weeks | 50 person-days |
| IPLD Vector and Graph Storage | 6 weeks | 60 person-days |
| Integration and Optimization | 3 weeks | 45 person-days |
| **Total** | **21 weeks** | **225 person-days** |

## Advanced Features

### GraphRAG Search with IPLD

The IPLD-based GraphRAG system combines vector similarity search with knowledge graph traversal:

1. **Vector Component**:
   - Store document/chunk embeddings in IPLD structures
   - Implement approximate nearest neighbor search
   - Use FAISS or similar libraries with IPLD persistence

2. **Knowledge Graph Component**:
   - Entities represented as IPLD nodes with CIDs
   - Relationships as typed links between nodes
   - Properties stored as node attributes
   - Graph schema defined via IPLD schemas

3. **Hybrid Search Process**:
   - Convert query to embedding vector
   - Find similar vectors via ANN search
   - Expand results through graph relationships
   - Apply path-based relevance scoring
   - Rank by combined vector similarity and graph relevance

4. **IPLD Schema for Vectors**:
```json
{
  "type": "struct",
  "fields": {
    "dimension": {"type": "int"},
    "metric": {"type": "string"},
    "vectors": {
      "type": "list",
      "valueType": {
        "type": "struct",
        "fields": {
          "id": {"type": "string"},
          "values": {"type": "list", "valueType": "float"},
          "metadata": {"type": "map", "keyType": "string", "valueType": "any"}
        }
      }
    }
  }
}
```

5. **IPLD Schema for Knowledge Graph Nodes**:
```json
{
  "type": "struct",
  "fields": {
    "id": {"type": "string"},
    "type": {"type": "string"},
    "properties": {"type": "map", "keyType": "string", "valueType": "any"},
    "relationships": {
      "type": "list",
      "valueType": {
        "type": "struct",
        "fields": {
          "type": {"type": "string"},
          "target": {"type": "link"},
          "properties": {"type": "map", "keyType": "string", "valueType": "any"}
        }
      }
    }
  }
}
```

## Technology Selection Guidelines

### Choosing the Right Technology

| Use case | Best choice |
|----------|-------------|
| Large binary or tabular data | mmap or Arrow |
| Cross-language IPC (no overhead) | Arrow C Data Interface |
| Multiple processes, same machine | mmap / Arrow |
| Flexible, decoupled architecture | Queues / Message Passing |
| Network-distributed components | gRPC / HTTP |
| Peer-to-peer communication | libp2p_py |
| Decentralized content routing | libp2p_py + DHT |
| Self-organizing networks | libp2p_py |
| Content-addressed data transfer | libp2p_py + IPLD |
| Direct CID sharing between peers | libp2p_py + custom protocols |
| Vector similarity search | FAISS + Arrow |
| Graph data and traversals | IPLD + custom indexing |
| Hybrid search (vectors + graphs) | GraphRAG with IPLD storage |
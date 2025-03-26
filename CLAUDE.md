# CLAUDE.md - Guidelines for ipfs_kit_py

## Build & Test Commands
- Install: `pip install -e .`
- Build: `python setup.py build`
- Run all tests: `python -m test.test`
- Run single test: `python -m test.test_ipfs_kit` or `python -m test.test_storacha_kit`

## Code Style Guidelines
- **Imports**: Standard library first, third-party next
- **Formatting**: 4-space indentation
- **Classes**: Initialize with `__init__(self, resources=None, metadata=None)`, end with `return None`
- **Naming**: snake_case for methods/variables, PascalCase for classes
- **Method Structure**: Methods typically accept `self, resources, metadata` parameters
- **Error Handling**: Use try/except blocks with results dictionary for error collection
- **Subprocess Pattern**: Use subprocess.run() with captured output for system commands
- **Testing Style**: Test classes follow `test_*` naming pattern with `init` and `test` methods

## Required Dependencies
- Python >=3.8
- requests, multiformats, boto3

## Code Review Report

### Architecture Overview
- Python wrapper around IPFS and IPFS Cluster tools
- Role-based design with three roles: "master", "worker", "leecher"
- Core components: ipfs_kit (facade), ipfs (core operations), storacha_kit (storage integration)
- Extensive use of subprocess to call CLI tools

### Strengths
- Comprehensive coverage of IPFS functionality
- Flexible role-based architecture supporting different node types
- Integration with both IPFS Cluster and Web3.Storage/Storacha
- Multiplatform support (Windows, Linux, macOS)

### Areas for Improvement
- **Code Structure**: Reduce duplication, improve class cohesion, follow single responsibility principle
- **Error Handling**: Standardize approach, preserve stack traces, create error hierarchies
- **Documentation**: Add docstrings, type annotations, parameter validation
- **Testing**: Separate test code from implementation, increase unit test coverage
- **Code Quality**: Address redundant imports, string concatenation, security risks in subprocess calls

## Abstract Syntax Tree Analysis

The ipfs_kit_py module implements a layered architecture with several key components:

### Core Components

1. **ipfs_kit**: Main orchestrator class that provides a unified interface for all IPFS operations
2. **ipfs_py**: Handles low-level IPFS daemon operations and file management
3. **storacha_kit**: Provides integration with Web3.Storage services
4. **s3_kit**: Manages AWS S3 compatible storage operations
5. **ipfs_multiformats_py**: Handles CID (Content Identifier) creation and multihash operations

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

## Development Plan

### Filesystem Interface with Adaptive Caching
- Implement fsspec filesystem interface for unified access to all storage backends
- Develop adaptive replacement cache (ARC) mechanism with data "heat" tracking
- Intelligent caching decisions based on:
  - Access frequency and recency ("hotness" of data)
  - Retrieval latency from different backends
  - Storage/egress costs across backends
  - Available local storage capacity
- Hierarchical eviction strategy prioritizing:
  1. Local cache (fastest, but limited capacity)
  2. IPFS node cache (fast, larger capacity)
  3. IPFS cluster (distributed, good redundancy)
  4. S3 storage (reliable, moderate cost)
  5. Storacha (durable, potentially higher latency)
  6. Filecoin (highest durability, lowest cost, highest latency)
- Performance metrics collection for data-driven caching decisions
- Bandwidth optimization for edge client delivery

### High-Performance Routing Index with Apache Arrow
- Use Apache Arrow for in-memory representation of routing metadata:
  - IPFS pinsets and pin metadata
  - UnixFS data structures
  - IPLD DAG (Directed Acyclic Graph) structure
  - File access patterns and heat metrics
- Implement Parquet-based persistence for durability and quick restoration
- Design for scale to handle millions of files in pinsets with minimal latency
- Columnar structure to efficiently query and update specific metadata attributes
- Memory-mapped files for near-instant startup with large datasets
- Delta updates to minimize write amplification
- Partitioning strategy for parallel processing of routing decisions
- Distributed index synchronization across cluster nodes

## Implementation Plan

### 1. Required New Dependencies

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
```

### 2. New Classes to be Created

#### FSSpecIPFSFileSystem
```python
class FSSpecIPFSFileSystem(AbstractFileSystem):
    """FSSpec-compatible filesystem interface for IPFS with ARC cache."""
    
    def __init__(self, ipfs_path=None, cache_size=1024, cache_ttl=3600, **kwargs):
        """Initialize the IPFS filesystem with adaptive replacement cache."""
        
    def _open(self, path, mode="rb", **kwargs):
        """Open a file on the IPFS filesystem."""
        
    def ls(self, path, detail=True, **kwargs):
        """List objects under path."""
        
    # Additional methods for file operations, pinning, etc.
```

#### IPFSArrowIndex
```python
class IPFSArrowIndex:
    """Apache Arrow-based routing index for efficient IPFS metadata."""
    
    def __init__(self, index_path=None, schema=None):
        """Initialize the Arrow-based index."""
        
    def create_schema(self):
        """Create the Arrow schema for the index."""
        
    def load(self, path=None):
        """Load an existing index from disk."""
        
    # Additional methods for CRUD operations, query, and optimization
```

#### FilecoinStorage
```python
class FilecoinStorage:
    """Interface for interacting with Filecoin as a storage tier."""
    
    def __init__(self, api_endpoint=None, wallet_address=None, **kwargs):
        """Initialize the Filecoin storage interface."""
        
    def store(self, cid, duration=None, verified=False, **kwargs):
        """Store a CID on Filecoin network."""
        
    def retrieve(self, cid, output_path=None, **kwargs):
        """Retrieve data from Filecoin network."""
        
    # Additional methods for deal management, status checking, etc.
```

#### IPFSTieredStorage
```python
class IPFSTieredStorage:
    """Manager for tiered storage across IPFS and Filecoin."""
    
    def __init__(self, config=None):
        """Initialize the tiered storage manager."""
        
    def store(self, path, tier='ipfs', **kwargs):
        """Store data in specified storage tier."""
        
    def retrieve(self, cid, output_path=None, **kwargs):
        """Retrieve data from any available tier."""
        
    # Additional methods for migration, policy definition, etc.
```

### 3. Implementation Phases

#### Phase 1: FSSpec Filesystem Interface (3 weeks)
- Basic FSSpec adapter implementation
- Adaptive replacement cache integration
- Integration with existing IPFS methods
- Performance optimization
- Documentation and testing

#### Phase 2: Apache Arrow-based Routing Index (4 weeks)
- Schema design for metadata
- Basic index implementation
- File persistence layer
- Query and filter mechanisms
- Integration with IPFS methods
- Performance benchmarking
- Documentation and testing

#### Phase 3: Filecoin Storage Tier (5 weeks)
- Filecoin API client integration
- Basic storage and retrieval functionality
- Deal management implementation
- Cost estimation and reporting
- Error handling and recovery mechanisms
- Documentation and testing

#### Phase 4: Integration Phase (3 weeks)
- Tiered storage policy implementation
- Integration of all components
- API consistency review
- End-to-end workflow testing
- Performance optimization
- Comprehensive documentation

### 4. Testing Approach

- Unit tests for each new component
- Integration tests with existing functionality
- Performance benchmarks under various conditions
- Edge case testing for large files/directories
- Stress testing with millions of entries
- Recovery and error handling tests
- Policy enforcement validation

### 5. Estimated Effort

| Phase | Duration | Effort (person-days) |
|-------|----------|----------------------|
| FSSpec Filesystem Interface | 3 weeks | 30 person-days |
| Apache Arrow-based Index | 4 weeks | 40 person-days |
| Filecoin Storage Tier | 5 weeks | 50 person-days |
| Integration Phase | 3 weeks | 45 person-days |
| **Total** | **15 weeks** | **165 person-days** |


### 6. Future Project Spec: High-Performance IPC and Data Layer using Arrow + IPLD-style Keys + C Data Interface

Overview

We are building a high-throughput, low-latency interprocess communication (IPC) and data storage layer for structured data exchange between components. This layer will:

Use Apache Arrow for efficient, in-memory, columnar data representation.

Address all data blocks and batches with IPLD-style content hashes (CIDs).

Share data across processes using the Arrow C Data Interface (zero-copy IPC).

Support optional serialization to Parquet and IPFS-compatible CAR files for long-term persistence and external sharing.

Objectives

Establish a shared-memory, zero-copy IPC mechanism for structured data exchange.

Design content-addressed data batch management using hash-based identifiers (IPLD-style).

Enable downstream consumers to retrieve data by CID and verify integrity.

Ensure data can be exported easily to both Parquet and IPFS-compatible CAR formats.

Maintain language-agnostic compatibility (via Arrow's C Data Interface).

System Components

1. Producer Processes

Create Arrow Tables or RecordBatches

Assign a stable content identifier (CID) to each batch:

Compute CID as SHA-256 over deterministic Arrow serialization (e.g. IPC format or sliced buffer)

CID schema: multihash + codec (compatible with IPLD)

Publish RecordBatch metadata + CID into a shared registry/index

Share the batch itself via Arrow C Data Interface (e.g. via shared memory or Arrow Flight)

2. Consumer Processes

Subscribe to new CIDs via registry or message bus

Request and import Arrow RecordBatches via C Data Interface

Optionally verify content integrity by re-hashing and comparing to CID

Use Arrow-native tooling for analytics, transformation, or further routing

3. Data Registry (CID Index)

Maps CIDs to metadata including:

Schema (optional)

Memory location or buffer reference (e.g. shared memory key or flight descriptor)

Creation timestamp, tags, provenance (optional)

Simple key-value store interface (can be in-memory, RocksDB, or a lightweight JSON file store for prototyping)

4. Exporters

Export RecordBatches by CID to:

Parquet files (for analytics or archive)

CAR files (for IPFS/network distribution)

Exporters must:

Rehydrate data by CID

Canonically serialize

Retain CID linkage in metadata (e.g. include CID in filename or CAR header)

Functional Requirements

python, nodejs, client js

Non-Functional Requirements

High-throughput: system must support thousands of messages/sec between processes

Zero-copy: avoid serialization overhead for local transfers

Extensible: support different storage backends (RAM, mmap, disk)

Language-agnostic: C Data Interface should support at least Python, C++, and Rust

Deliverables

CID hashing module for Arrow batches (Python + C++)

Shared-memory registry with simple CID → metadata lookup

IPC transport using Arrow C Data Interface

CLI or REST interface to export CID → Parquet or CAR

Documentation and test suite

Optional Extensions

DAG linking (e.g., link batches via IPLD-like graphs)

Access control or signing for secure sharing

Integration with IPFS nodes (publish CARs or CIDs to IPFS)

Real-time streaming ingestion (Flight SQL, Arrow Streaming)

Tools & Dependencies

Apache Arrow

Multiformats / Multihash

Flatbuffers (if needed for custom serialization)

Optional: IPFS toolchain (go-car, py-ipfs-car)

Getting Started

Prototype a single-producer, single-consumer setup over shared memory.

Validate zero-copy data movement using pyarrow + C Data Interface.

Build CID index and verifier.

Implement Parquet and CAR export.

Iterate on multi-process coordination and scaling.

Let me know if you'd like an architecture diagram or technical API spec added to this.
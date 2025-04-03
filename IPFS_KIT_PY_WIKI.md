# IPFS Kit Python (ipfs_kit_py)

## Overview

IPFS Kit Python (`ipfs_kit_py`) is a comprehensive Python toolkit for working with IPFS (InterPlanetary File System) technologies, providing a unified interface for IPFS operations, cluster management, tiered storage, and advanced AI/ML integration. It serves as the foundational layer in the IPFS HuggingFace Bridge MLOps platform, enabling content-addressed storage and distribution for machine learning workflows.

As a core component of the larger IPFS HuggingFace Bridge MLOps toolkit, `ipfs_kit_py` provides the critical infrastructure layer that connects decentralized storage systems (IPFS/Filecoin) with Hugging Face's ecosystem of models, datasets, and ML tools. This integration enables powerful workflows that were previously impossible with traditional centralized architectures.

## Architectural Distinction and Value

IPFS Kit Python represents a fundamental rethinking of how machine learning systems handle content. While traditional MLOps platforms rely on centralized storage systems (like S3, HDFS, or NAS), `ipfs_kit_py` implements a **decentralized content-addressed approach** that solves several critical challenges in ML workflows:

1. **Content Integrity**: Traditional systems can't verify that the model you retrieve is exactly the one you stored - content can be changed or corrupted without detection. IPFS Kit's content addressing makes every reference self-verifying through cryptographic hashing.

2. **Dependency Coordination**: ML systems often struggle with "dependency hell" when model weights or datasets change. IPFS Kit makes content immutable and permanent by design, so references never break or change unexpectedly.

3. **Distributed Access Patterns**: Centralized storage becomes a bottleneck for distributed training. IPFS Kit's peer-to-peer architecture allows workers to retrieve chunks directly from each other rather than all hitting the same central server.

4. **Offline Capabilities**: Traditional systems require continuous connection to central storage. IPFS Kit's leecher nodes can operate offline once content is cached, perfect for edge deployment or unreliable connectivity.

The architecture provides a **content backbone** that handles:

- **Immutable Model Storage**: Each version gets a unique, cryptographically-derived identifier
- **Verifiable Dataset Management**: Ensure all workers use identical training data
- **Provenance Tracking**: Complete lineage of content derivation through immutable references
- **Decentralized Distribution**: Models flow efficiently through peer-to-peer connections
- **Heterogeneous Environment Support**: Consistent content access from cloud to edge

## Core Architecture

IPFS Kit implements a specialized role-based architecture with three distinct node types:

- **Master Node**: 
  - Orchestrates the entire content ecosystem
  - Aggregates and arranges content into coherent collections
  - Coordinates task distribution across worker nodes
  - Manages metadata indexes and content routing tables
  - Runs IPFS Cluster in "master" mode

- **Worker Node**: 
  - Processes individual content items 
  - Executes specific computational tasks assigned by the master
  - Specializes in content transformation and feature extraction
  - Handles CPU/GPU-intensive operations
  - Participates in the IPFS Cluster as a processing-focused node

- **Leecher Node**: 
  - Primarily consumes network resources
  - Acts as an edge device (laptops, phones, IoT devices)
  - Retrieves and utilizes content without significant contribution
  - Maintains minimal local cache for recently accessed content

## Key Features

### 1. Multi-Tier Content Storage

IPFS Kit implements a sophisticated tiered storage system:

- **Memory Tier**: Adaptive Replacement Cache (ARC) with heat scoring
- **Disk Tier**: Persistent local storage with efficient indexing
- **IPFS Local Node**: Content pinned to local IPFS node
- **IPFS Cluster**: Distributed content across cluster nodes
- **External Storage**: S3, Storacha/Web3.Storage, HuggingFace Hub
- **Filecoin**: Long-term archival storage

This architecture enables intelligent content placement based on access patterns, importance, and resource constraints.

### 2. Arrow-based Metadata Index

IPFS Kit includes a high-performance metadata indexing system built on Apache Arrow:

- **Columnar Storage**: Efficient data representation and query performance
- **Zero-copy IPC**: Share index data across processes without duplication
- **Rich Query Capabilities**: Complex filtering and search operations
- **Distributed Synchronization**: Index sharing between nodes
- **Content Location Tracking**: Find content across multiple storage backends

### 3. FSSpec Integration

IPFS Kit provides a standard filesystem interface to content-addressed storage:

- **File-like Access**: Standard open, read, write operations
- **Integration with Data Science Tools**: Works with Pandas, PyArrow, Dask
- **Performance Optimizations**: Memory mapping, connection pooling
- **Content Deduplication**: Automatic deduplication through content addressing

### 4. High-Level API

The `IPFSSimpleAPI` provides a simplified, user-friendly interface:

- **Intuitive Methods**: `add`, `get`, `pin`, `publish`, etc.
- **Declarative Configuration**: Using YAML, JSON, or environment variables
- **Automatic Component Management**: Handles initialization and coordination
- **Plugin Architecture**: Extensible through custom plugins
- **Multi-language SDK Generation**: For Python, JavaScript, and Rust

### 5. AI/ML Integration

IPFS Kit provides comprehensive AI/ML capabilities:

- **Model Registry**: Version-controlled storage for ML models
- **Dataset Management**: Efficient storage and distribution of datasets
- **LangChain & LlamaIndex Integration**: Content-addressed vector stores
- **Framework Support**: PyTorch, TensorFlow, Hugging Face integrations
- **Distributed Training**: Coordinate training across worker nodes
- **GraphRAG Capabilities**: Perform graph-enhanced retrieval augmented generation directly on IPFS/Filecoin network data, combining vector similarity with knowledge graph traversal

## Architectural Comparisons to Traditional Systems

### IPFS Kit vs. Traditional Object Storage (S3, GCS, Azure Blob)

| IPFS Kit Architecture | Traditional Object Storage |
|-------------|-------------------|
| Content-addressed (CIDs derived from content) | Location-addressed (user-defined keys/paths) |
| Content is immutable by design | Content can be overwritten in place |
| Automatic data verification on retrieval | No built-in verification mechanism |
| Peer-to-peer distribution | Client-server model only |
| Multi-tier caching with ARC | Simple caching, not content-aware |
| Built-in deduplication at block level | No automatic deduplication |
| Supports offline operation | Requires continuous connectivity |
| Multi-protocol access (HTTP, libp2p, websocket) | HTTP/S only |

Object storage systems like S3 were not built with machine learning workflows in mind. While they provide high durability, they lack critical features for ML like content immutability, efficient peer-to-peer distribution, and auto-verified retrieval that are fundamental to IPFS Kit's design.

### IPFS Kit vs. Traditional ML Model Registries

| IPFS Kit Architecture | Traditional ML Model Registry |
|-------------|----------------------------------|
| Cryptographic model identification | Sequential or user-provided versioning |
| Verification built into retrieval | No verification of model integrity |
| Distributed storage and retrieval | Centralized storage |
| Automatic format detection and conversion | Manual format management |
| Flexible metadata indexing with Arrow | Fixed schema databases |
| Tiered storage for performance | Single-tier storage |
| Peer-to-peer model distribution | Client-server distribution only |

Traditional model registries like MLflow track models but don't guarantee that what you retrieve is actually what was stored. They typically use database sequences for versioning rather than cryptographic content addressing, which leaves them vulnerable to content corruption or tampering.

### IPFS Kit vs. Centralized Vector Databases

As a key component of the IPFS HuggingFace Bridge ecosystem, `ipfs_kit_py` delivers significant architectural advantages over centralized vector databases, especially for RAG and GraphRAG workflows:

| IPFS Kit Architecture | Centralized Vector Databases |
|-------------|---------------------|
| Content-addressed vectors | Sequential or custom IDs |
| Distributed index with peer synchronization | Centralized index |
| Supports heterogeneous nodes (master/worker/leecher) | Uniform node requirements |
| Arrow-based metadata for zero-copy access | Custom formats, often requiring copies |
| Natural multi-tenancy through content addressing | Complex ACL mechanisms needed |
| Self-verifying embeddings | No verification mechanism |
| Peer-to-peer vector sharing | Client-server architecture |
| GraphRAG on IPFS/Filecoin network data | No built-in graph capabilities |
| Direct integration with HuggingFace models | Separate systems requiring integration |
| Built-in content provenance tracking | No cryptographic provenance |

Centralized vector databases require all nodes to use the same central store, creating bottlenecks for distributed retrieval and indexing. The IPFS HuggingFace Bridge architecture allows nodes to share vectors directly, verify their integrity automatically, and perform sophisticated GraphRAG operations directly on the decentralized network data.

## System Architecture Implementation 

### ML Workflow Architecture Example

This diagram illustrates how the IPFS Kit architecture fundamentally transforms ML workflows by using content addressing and peer-to-peer distribution:

```
┌───────────────────────┐     ┌────────────────────┐     ┌───────────────────┐
│                       │     │                    │     │                   │
│   Data Science Team   │     │   MLOps Platform   │     │   Deployment      │
│                       │     │                    │     │   Environment     │
│  ┌─────────────────┐  │     │ ┌────────────────┐ │     │ ┌─────────────┐  │
│  │ Data Processing │  │     │ │Master Node     │ │     │ │Edge Device 1│  │
│  │ - Data cleaning │  │     │ │                │ │     │ │(Leecher)    │  │
│  │ - Feature eng.  │──┼─────┼─┼→ CID based     │ │     │ │             │  │
│  │ - Validation    │  │     │ │  immutable     │ │     │ │Cached model │  │
│  └─────────────────┘  │     │ │  versioning    │ │     │ │verification │  │
│                       │     │ │                │ │     │ └──────┬──────┘  │
│  ┌─────────────────┐  │     │ │Arrow metadata  │ │     │        │         │
│  │ Model Training  │  │     │ │index           │ │     │        │         │
│  │ - Training      │  │     │ │                │◄┼─────┼────────┘         │
│  │ - Validation    │──┼─────┼─┼→ UnixFS DAG    │ │     │ ┌─────────────┐  │
│  │ - Publishing    │  │     │ │  content       │ │     │ │Edge Device 2│  │
│  └─────────────────┘  │     │ └────┬───────────┘ │     │ │(Leecher)    │  │
│                       │     │      │             │     │ │             │  │
└───────────────────────┘     │      │             │     │ │P2P content  │  │
                              │      │             │     │ │sharing      │  │
┌───────────────────────┐     │      │             │     │ └──────┬──────┘  │
│                       │     │      │             │     │        │         │
│  ML Engineering Team  │     │      │             │     │        │         │
│                       │     │      │             │     │        │         │
│  ┌─────────────────┐  │     │      │             │     │ ┌─────────────┐  │
│  │ Model Tuning    │  │     │      ▼             │     │ │Edge Device 3│  │
│  │                 │  │     │ ┌────────────────┐ │     │ │(Leecher)    │  │
│  │ - Fine-tuning   │──┼─────┼─┼→Worker Node 1  │ │     │ │             │◄─┼────┐
│  │ - Optimization  │  │     │ │                │ │     │ │Offline      │  │    │
│  └─────────────────┘  │     │ │Computational   │ │     │ │operation    │  │    │
│                       │     │ │tasks           │ │     │ └─────────────┘  │    │
│  ┌─────────────────┐  │     │ │                │ │     │                   │    │
│  │ Inference       │  │     │ │Zero-copy Arrow │ │     └───────────────────┘    │
│  │ Optimization    │  │     │ │C Data Interface│ │                              │
│  │                 │  │     │ └───────┬────────┘ │                              │
│  │ - Quantization  │──┼─────┼─────────┘          │                              │
│  │ - Pruning       │  │     │                    │                              │
│  └─────────────────┘  │     │ ┌────────────────┐ │                              │
│                       │     │ │Worker Node 2   │ │                              │
└───────────────────────┘     │ │                │ │                              │
                              │ │P2P content     │─┼──────────────────────────────┘
                              │ │distribution    │ │
                              │ │                │ │
                              │ │ARC tiered      │ │
                              │ │caching         │ │
                              │ └────────────────┘ │
                              │                    │
                              └────────────────────┘
```

Key architectural features illustrated:
1. **Content addressing** - All data flows are based on content-derived identifiers
2. **Peer-to-peer distribution** - Devices can retrieve content from any node with the content
3. **Role-based nodes** - Specialization based on node capabilities and responsibilities
4. **Zero-copy data access** - Arrow C Data Interface enables efficient processing
5. **Offline capability** - Edge devices can operate without constant connectivity
6. **Tiered caching** - Adaptive caching policy optimizes content storage

### Implementation Details: Metadata Synchronization Between Nodes

The following code demonstrates how nodes synchronize their metadata indexes in a distributed manner:

```python
class MetadataSyncHandler:
    """Handles synchronization of metadata between nodes in the network."""
    
    def __init__(self, ipfs_client, metadata_index, role="leecher"):
        self.ipfs = ipfs_client
        self.index = metadata_index
        self.role = role
        self.running = False
        self.pubsub_topics = {
            "announce": "/ipfs-metadata/announce/v1",
            "request": "/ipfs-metadata/request/v1",
            "response": "/ipfs-metadata/response/v1"
        }
        
    def start(self, sync_interval=300):
        """Start the sync handler with the specified interval."""
        if self.running:
            return
            
        self.running = True
        self.sync_interval = sync_interval
        
        # Subscribe to topics based on role
        if self.role in ("master", "worker"):
            # These nodes respond to requests
            self._subscribe_to_request_topic()
            
        if self.role != "master":
            # These nodes receive announcements
            self._subscribe_to_announce_topic()
            
        # All nodes can receive responses
        self._subscribe_to_response_topic()
        
        # Masters periodically announce their index
        if self.role == "master":
            self._start_announcement_thread()
            
    def _subscribe_to_request_topic(self):
        """Subscribe to metadata request topic."""
        def handle_request(msg):
            # Parse request
            request = json.loads(msg["data"])
            requester = msg["from"]
            
            # Only respond to specific requests
            if request["type"] == "partition_request":
                partition_id = request["partition_id"]
                self._send_partition(requester, partition_id)
                
        self.ipfs.pubsub_subscribe(
            self.pubsub_topics["request"],
            handle_request
        )
        
    def _send_partition(self, peer_id, partition_id):
        """Send a partition to a specific peer."""
        # Get partition data
        partition_path = self.index.get_partition_path(partition_id)
        
        if not os.path.exists(partition_path):
            return
            
        # Add partition file to IPFS
        result = self.ipfs.ipfs_add_file(partition_path)
        partition_cid = result["Hash"]
        
        # Send response with CID reference
        response = {
            "type": "partition_response",
            "partition_id": partition_id,
            "partition_cid": partition_cid,
            "node_id": self.ipfs.ipfs_id()["ID"],
            "timestamp": time.time()
        }
        
        # Publish to response topic
        self.ipfs.pubsub_publish(
            self.pubsub_topics["response"],
            json.dumps(response)
        )
```

This architectural pattern enables efficient, decentralized metadata synchronization without centralized coordination.

## Core Technical Implementation Details

### 1. Adaptive Replacement Cache (ARC) Implementation

The tiered storage system implements a sophisticated Adaptive Replacement Cache that outperforms traditional LRU (Least Recently Used) caches:

```python
class ARCache:
    """Adaptive Replacement Cache implementation optimized for ML workloads."""
    
    def __init__(self, maxsize=100 * 1024 * 1024):  # Default 100MB
        # T1: Recent cache, T2: Frequent cache (physical caches)
        self.T1 = OrderedDict()  # Recently used items
        self.T2 = OrderedDict()  # Frequently used items
        
        # B1, B2: Ghost caches tracking recently evicted items
        self.B1 = OrderedDict()  # Recently evicted from T1
        self.B2 = OrderedDict()  # Recently evicted from T2
        
        # Cache size limits
        self.maxsize = maxsize
        self.p = 0  # Target size for T1
        self.current_size = 0
```

This implementation:
- Maintains four separate caches (T1, T2, B1, B2)
- Dynamically adjusts allocation between recency (T1) and frequency (T2)
- Tracks "ghost entries" of recently evicted items
- Adapts automatically to changing access patterns in ML workflows

### 2. Arrow-based Metadata Indexing

The metadata index uses Apache Arrow for zero-copy access and efficient querying:

```python
def create_metadata_schema():
    """Create Arrow schema for IPFS content metadata."""
    return pa.schema([
        # Content identifiers
        pa.field('cid', pa.string()),
        pa.field('cid_version', pa.int8()),
        pa.field('multihash_type', pa.string()),
        
        # Basic metadata
        pa.field('size_bytes', pa.int64()),
        pa.field('blocks', pa.int32()),
        pa.field('links', pa.int32()),
        pa.field('mime_type', pa.string()),
        
        # Storage status
        pa.field('local', pa.bool_()),
        pa.field('pinned', pa.bool_()),
        pa.field('pin_types', pa.list_(pa.string())),
        pa.field('replication', pa.int16()),
        
        # Access patterns for cache optimization
        pa.field('created_at', pa.timestamp('ms')),
        pa.field('last_accessed', pa.timestamp('ms')),
        pa.field('access_count', pa.int32()),
        
        # Storage locations
        pa.field('storage_locations', pa.struct([...]))
    ])
```

This implementation provides:
- Columnar storage for efficient filtering and query operations
- Zero-copy access through memory mapping and Arrow C Data Interface
- Distributed index synchronization via IPFS pubsub
- Efficient serialization to Parquet for persistence

### 3. Role-Based Node Architecture

The implementation distinguishes between different node types:

```python
def configure_node_by_role(role):
    """Configure node behavior based on its role in the network."""
    if role == "master":
        # Master nodes focus on coordination and metadata management
        config = {
            "maintain_full_index": True,
            "accept_sync_requests": True,
            "publish_index": True,
            "store_all_blocks": False,
            "prefetch_popular_content": True,
            "relay_enabled": True
        }
    elif role == "worker":
        # Workers focus on processing and serving content
        config = {
            "maintain_full_index": False,
            "accept_sync_requests": True,
            "publish_index": False,
            "store_all_blocks": False,
            "prefetch_popular_content": False,
            "relay_enabled": True
        }
    elif role == "leecher":
        # Leechers optimize for consumption with minimal contribution
        config = {
            "maintain_full_index": False,
            "accept_sync_requests": False,
            "publish_index": False,
            "store_all_blocks": False,
            "prefetch_popular_content": False,
            "relay_enabled": False
        }
    
    return config
```

This differentiated behavior allows nodes to specialize based on their capabilities and role in the network.

### 4. FSSpec Integration for Data Science

The FSSpec integration enables standard filesystem operations on content-addressed data:

```python
class IPFSFileSystem(AbstractFileSystem):
    """FSSpec-compatible filesystem interface for IPFS content."""
    
    protocol = "ipfs"
    
    def __init__(self, ipfs_path=None, socket_path=None, use_mmap=True):
        super().__init__()
        self.ipfs_path = ipfs_path
        self.socket_path = socket_path
        self.use_mmap = use_mmap
        
    def _open(self, path, mode="rb", **kwargs):
        """Open an IPFS file with optimized performance."""
        cid = self._path_to_cid(path)
        
        # Check cache first
        content = self.cache.get(cid)
        if content is not None:
            return IPFSMemoryFile(self, path, content, mode)
        
        # Fetch through fastest available interface
        content = self._fetch_from_ipfs(cid)
        self.cache.put(cid, content)
        
        # Use memory mapping for large files
        if self.use_mmap and len(content) > 10 * 1024 * 1024:
            return IPFSMemoryMappedFile(self, path, content, mode)
        else:
            return IPFSMemoryFile(self, path, content, mode)
```

This implementation allows ML frameworks to work with IPFS content through standard file-like interfaces.

## Real-world System Architecture Benefits

### 1. Reproducibility Through Immutability

A critical challenge in ML systems is exact reproducibility. Traditional systems allow files to be modified in place, leading to situations where the same path or model ID refers to different content over time. This introduces silent failures in ML pipelines.

IPFS Kit's architecture provides:

- **Perfect Reproducibility**: When a model is referenced by CID, it can never refer to different content
- **Automatic Verification**: Content retrieved is automatically verified against its cryptographic hash
- **Fine-grained Versioning**: Even minor model updates generate distinct CIDs
- **Elimination of Race Conditions**: No risk of content changing during distributed training

Example scenario: A data scientist references a baseline model. Six months later, they can retrieve exactly the same model with the same weights, guaranteed, even if the "latest" version has been updated hundreds of times.

### 2. Scaling Data Distribution for Large Models

Traditional architectures struggle when distributing large models (100GB+) to many worker nodes simultaneously:

| Traditional Approach | IPFS Kit Approach |
|---------------------|-------------------|
| Central server becomes bottleneck | Content retrieved in parallel from multiple peers |
| Network congestion at central point | Load distributed across network |
| Sequential distribution to workers | Workers retrieve chunks simultaneously |
| Redundant transfers of identical content | Content automatically deduplicated |
| Server capacity limits throughput | System scales with number of nodes |

This architecture significantly reduces time to start distributed training jobs by eliminating the central bottleneck in model distribution.

### 3. Offline-Capable Edge Deployment

ML deployments at the edge (IoT devices, remote locations, mobile) face connectivity challenges. The leecher node design in IPFS Kit solves this with:

- **Full Offline Operation**: Once content is cached, no further connectivity needed
- **Partial Updates**: Only modified portions of models need transfer
- **Peer-to-peer Updates**: Edge devices can update from any available source
- **Prioritized Caching**: Most important components remain cached
- **Guaranteed Consistency**: CIDs ensure the right version is always used

For example, an ML model deployed to hundreds of edge devices can be updated efficiently by having devices share updates directly with nearby peers, without all devices connecting to a central server.

## Current Status and Architectural Advantages

IPFS Kit Python has been implemented with a carefully designed architecture that solves several key challenges in distributed ML systems:

### 1. Content-Based Architecture vs. Location-Based Architecture

Unlike traditional systems that rely on location-based addressing (URLs, paths, etc.), IPFS Kit's content-based architecture provides:

- **Immutable References**: CIDs can never refer to different content, eliminating "dependency hell"
- **Self-Verifying Retrieval**: Content integrity is automatically verified via hash comparison
- **Location Independence**: Content can be retrieved from any node that has it, not just from specific servers
- **Natural Deduplication**: Identical content (even when stored through different paths) is automatically deduplicated

This architecture is fundamentally different from traditional object storage or file servers, where content can change while references remain the same.

### 2. Implemented Components

The current implementation includes all core components:

✅ Role-based Node Architecture  
✅ Tiered Storage with Adaptive Replacement Cache  
✅ Apache Arrow Metadata Index  
✅ FSSpec Filesystem Integration  
✅ Cluster Management and Synchronization  
✅ High-Level API with SDK Generation  
✅ AI Framework Integration  

### 3. Performance Characteristics

The architecture has been designed for ML workloads with specific performance considerations:

- **Hierarchical Caching**: Optimized for ML's "train once, infer many times" patterns
- **Heat Scoring Algorithm**: Dynamically promotes/demotes content based on usage patterns
- **Parallel Content Retrieval**: Multiple chunks retrieved concurrently from diverse nodes
- **Zero-copy Semantics**: Memory-mapped files and Arrow C Data Interface minimize data copying
- **Off-Path Retrieval**: Content can be fetched from any available source, not just original provider

### GraphRAG on IPFS/Filecoin Network Data

As part of the IPFS HuggingFace Bridge ecosystem, `ipfs_kit_py` provides specialized support for performing Graph-enhanced Retrieval Augmented Generation (GraphRAG) directly on IPFS/Filecoin network data:

```python
class IPLDGraphRAG:
    """GraphRAG implementation for content-addressed knowledge graphs."""
    
    def __init__(self, ipfs_client, embedding_model=None):
        self.ipfs = ipfs_client
        self.embedding_model = embedding_model
        self.graph_db = IPLDGraphDB(ipfs_client)
        self.vector_index = IPFSVectorIndex(ipfs_client)
        
    def add_document(self, document, metadata=None):
        """Process a document for GraphRAG, storing both vector embeddings and graph relationships."""
        # Generate embedding
        embedding = self._get_embedding(document)
        
        # Add to vector index
        vector_id = self.vector_index.add_vector(embedding, metadata={
            "text": document,
            "metadata": metadata or {}
        })
        
        # Extract entities and concepts
        entities = self._extract_entities(document)
        
        # Create document node
        doc_id = f"doc_{uuid.uuid4()}"
        self.graph_db.add_entity(
            entity_id=doc_id,
            properties={
                "type": "document",
                "text": document,
                "metadata": metadata or {},
                "vector_id": vector_id
            },
            vector=embedding
        )
        
        # Link entities to document
        for entity in entities:
            entity_id = f"entity_{slugify(entity['name'])}"
            if not self.graph_db.get_entity(entity_id):
                self.graph_db.add_entity(
                    entity_id=entity_id,
                    properties={
                        "type": "entity",
                        "name": entity["name"],
                        "category": entity["category"]
                    }
                )
            
            # Create relationship
            self.graph_db.add_relationship(
                from_entity=doc_id,
                to_entity=entity_id,
                relationship_type="mentions",
                properties={"confidence": entity["confidence"]}
            )
        
        return doc_id
    
    def query(self, query_text, k=10, hop_count=2, include_embeddings=False):
        """
        Perform hybrid graph and vector search to retrieve relevant content.
        
        Args:
            query_text: Text query to search for
            k: Number of results to return
            hop_count: Number of graph hops to explore
            include_embeddings: Whether to include embeddings in results
        
        Returns:
            List of results with both vector and graph relevance
        """
        # Generate query embedding
        query_embedding = self._get_embedding(query_text)
        
        # Perform hybrid search
        results = self.graph_db.graph_vector_search(
            query_vector=query_embedding,
            hop_count=hop_count,
            top_k=k * 2  # Get more results to filter
        )
        
        # Enhance results with full document text
        enhanced_results = []
        for result in results[:k]:
            entity = self.graph_db.get_entity(result["entity_id"])
            
            if entity["properties"]["type"] == "document":
                doc_data = {
                    "id": result["entity_id"],
                    "text": entity["properties"]["text"],
                    "metadata": entity["properties"].get("metadata", {}),
                    "score": result["score"],
                    "source": "graph_vector_search",
                    "path": result["path"],
                }
                
                if include_embeddings and "vector" in entity:
                    doc_data["embedding"] = entity["vector"]
                    
                enhanced_results.append(doc_data)
        
        return enhanced_results
```

This implementation enables several unique capabilities within the IPFS HuggingFace Bridge ecosystem:

1. **Content-addressed knowledge graphs**: Graph structure is stored directly on IPFS/Filecoin, making it verifiable and immutable
2. **Decentralized vector search**: Embedding vectors stored in IPFS/Filecoin with efficient nearest-neighbor search
3. **Hybrid retrieval**: Combines vector similarity with graph traversal for more context-aware results
4. **Distributed knowledge bases**: Knowledge graphs can be shared and synchronized across nodes
5. **Verifiable provenance**: All relationships maintain cryptographic links to original source content

## Architectural Summary and Key Innovations

The `ipfs_kit_py` system architecture represents a fundamental rethinking of content management for ML workloads with several key architectural innovations:

1. **Content-Addressed Architecture**: The entire system is built around cryptographic content addressing rather than location-based addressing, providing immutable references, built-in deduplication, and automatic verification.

2. **Role-Based Node Specialization**: The master/worker/leecher architecture optimizes resource utilization across heterogeneous environments, allowing specialized behavior based on node capabilities and responsibilities.

3. **Multi-Tier Adaptive Caching**: The Adaptive Replacement Cache implementation with ghost lists and heat-based promotion achieves significantly better cache hit rates than traditional LRU caches for ML workloads.

4. **Distributed Metadata Synchronization**: The pubsub-based metadata synchronization design enables decentralized content discovery without centralized coordination or bottlenecks.

5. **Arrow-Based Zero-Copy Data Access**: The Apache Arrow implementation with C Data Interface provides efficient cross-process and cross-language data sharing without data duplication.

6. **FSSpec Integration for ML Ecosystems**: The FSSpec implementation bridges the gap between content addressing and traditional file APIs, enabling seamless integration with data science tools.

7. **IPFS HuggingFace Bridge Integration**: As a core component of the IPFS HuggingFace Bridge MLOps toolkit, it enables seamless workflows between decentralized storage and the Hugging Face model ecosystem.

These architectural choices specifically address the most critical challenges in modern ML workflows: reproducibility, efficient distribution of large models, heterogeneous deployment environments, and collaborative development. The design prioritizes the unique access patterns of ML workloads, with their train-once, infer-many-times nature and need for perfect reproducibility.

By rethinking content management from first principles with cryptographic content addressing at its core, `ipfs_kit_py` provides a more resilient, scalable, and verifiable foundation for ML infrastructure than traditional centralized approaches.

Within the larger IPFS HuggingFace Bridge MLOps ecosystem, `ipfs_kit_py` serves as the critical connective tissue that enables decentralized workflows spanning from data ingest through model training and deployment to inference and GraphRAG applications. This bridge between the content-addressed world of IPFS/Filecoin and the ML capabilities of the Hugging Face ecosystem creates a synergy that preserves the best attributes of both systems—the verifiability and peer-to-peer distribution of IPFS combined with the state-of-the-art ML capabilities of Hugging Face.
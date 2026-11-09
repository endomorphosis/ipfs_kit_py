# IPLD Knowledge Graph

IPFS Kit includes comprehensive functionality for building, querying, and utilizing knowledge graphs based on IPLD (InterPlanetary Linked Data), enabling sophisticated representation of relationships between content-addressed data.

This functionality is part of Phase 4A (Metadata and Indexing) in the development roadmap and provides graph-based knowledge representation with content addressing, versioning, and efficient query capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Architecture](#architecture)
4. [Enabling Knowledge Graph Features](#enabling-knowledge-graph-features)
5. [Basic Usage](#basic-usage)
   - [Managing Entities](#managing-entities)
   - [Managing Relationships](#managing-relationships)
   - [Querying the Graph](#querying-the-graph)
6. [Advanced Features](#advanced-features)
   - [Vector Search](#vector-search)
   - [GraphRAG (Graph Retrieval Augmented Generation)](#graphrag-graph-retrieval-augmented-generation)
   - [Version History and Change Tracking](#version-history-and-change-tracking)
   - [Subgraph Export and Import](#subgraph-export-and-import)
7. [Implementation Details](#implementation-details)
   - [IPLD Schema Design](#ipld-schema-design)
   - [Storage Patterns](#storage-patterns)
   - [Indexing Strategy](#indexing-strategy)
   - [NetworkX Integration](#networkx-integration)
8. [Performance Considerations](#performance-considerations)
   - [Scaling Knowledge Graphs](#scaling-knowledge-graphs)
   - [Vector Operations](#vector-operations)
   - [Query Optimization](#query-optimization)
   - [Benchmarks](#benchmarks)
   - [Monitoring and Optimization](#monitoring-and-optimization)
9. [GraphRAG Algorithm Details](#graphrag-algorithm-details)
   - [Algorithm Implementation](#algorithm-implementation)
   - [Relevance Scoring Formula](#relevance-scoring-formula)
   - [GraphRAG vs. Traditional RAG](#graphrag-vs-traditional-rag)
   - [Optimizations](#optimizations)
   - [Example GraphRAG Result](#example-graphrag-result)
10. [Integration with Other Components](#integration-with-other-components)
11. [Example Use Cases](#example-use-cases)
   - [Building a Research Paper Knowledge Graph](#building-a-research-paper-knowledge-graph)
   - [Implementing a GraphRAG System for AI](#implementing-a-graphrag-system-for-ai)
   - [Implementing a GraphRAG System for Technical Documentation](#implementing-a-graphrag-system-for-technical-documentation)
12. [Future Enhancements](#future-enhancements)

## Overview

The IPLD Knowledge Graph system in IPFS Kit provides a powerful way to create, manage, and query graph-based knowledge representations where both the entities (nodes) and relationships (edges) are stored as content-addressed IPLD objects. This enables several key capabilities:

- **Content-Addressed Knowledge**: All knowledge graph components are addressable by CID, enabling verification and distributed access
- **Relationship Modeling**: Express complex relationships between data items with typed, directed connections
- **Graph Queries**: Navigate relationships, find paths between entities, and discover connections
- **Hybrid Search**: Combine traditional graph traversal with vector similarity search (GraphRAG)
- **Versioning**: Track changes to the knowledge graph over time with full history
- **Distributed Knowledge**: Share and merge knowledge graph components across systems

The core components are found in `ipfs_kit_py/ipld_knowledge_graph.py`:

- **`IPLDGraphDB`**: Main component that manages the storage and retrieval of graph entities and relationships using IPFS DAGs
- **`KnowledgeGraphQuery`**: High-level interface for querying the graph (finding related entities, traversing paths, etc.)
- **`GraphRAG`**: Integrates the knowledge graph with vector embeddings for Retrieval-Augmented Generation, combining semantic similarity with graph structure

## Core Components

### IPLDGraphDB

The main knowledge graph database that handles entity and relationship management:

```python
class IPLDGraphDB:
    """IPLD-based knowledge graph database with vector capabilities."""
    
    def __init__(self, ipfs_client, base_path="~/.ipfs_graph", schema_version="1.0.0"):
        """Initialize the IPLD-based graph database."""
        # ...
```

Key methods:
- `add_entity()`: Add a node to the graph with properties and optional vector embedding
- `update_entity()`: Update an existing entity's properties or vector
- `add_relationship()`: Create a typed connection between entities
- `get_entity()`, `get_relationship()`: Retrieve graph components by ID
- `query_entities()`, `query_related()`: Find entities matching criteria or related to a given entity
- `path_between()`: Find paths between entities in the graph
- `vector_search()`, `graph_vector_search()`: Find similar entities by vector, optionally with graph traversal
- `export_subgraph()`, `import_subgraph()`: Share portions of the knowledge graph

### KnowledgeGraphQuery

A higher-level query interface on top of IPLDGraphDB:

```python
class KnowledgeGraphQuery:
    """Query interface for the IPLD knowledge graph."""
    
    def __init__(self, graph_db):
        """Initialize the query interface."""
        # ...
```

Key methods:
- `find_entities()`: Search for entities by type and properties
- `find_related()`: Discover entities related to a specified entity
- `find_paths()`: Find paths between two entities in the graph
- `hybrid_search()`: Combine text search, vector search, and graph traversal
- `get_knowledge_cards()`: Generate rich information cards for entities with their connections

### GraphRAG

Implements Retrieval-Augmented Generation using the knowledge graph:

```python
class GraphRAG:
    """Graph-based Retrieval Augmented Generation using IPLD Knowledge Graph."""
    
    def __init__(self, graph_db, embedding_model=None):
        """Initialize the GraphRAG system."""
        # ...
```

Key methods:
- `generate_embedding()`: Create vector embeddings from text (requires embedding model)
- `retrieve()`: Find relevant information in the graph based on text or vector query
- `format_context_for_llm()`: Format retrieved context for use with language models
- `generate_llm_prompt()`: Create a complete prompt with knowledge graph context

## Architecture

The IPLD Knowledge Graph is designed with a layered architecture:

```
┌──────────────────────────────────────────┐
│              GraphRAG                    │ ← High-level RAG Interface
└────────────────────┬─────────────────────┘
                    │
┌──────────────────────────────────────────┐
│          KnowledgeGraphQuery             │ ← Query Interface
└────────────────────┬─────────────────────┘
                    │
┌──────────────────────────────────────────┐
│             IPLDGraphDB                  │ ← Graph Database
└────────────────────┬─────────────────────┘
                    │
┌──────────────────────────────────────────┐
│             IPFS / IPLD                  │ ← Content-Addressed Storage
└──────────────────────────────────────────┘
```

The implementation leverages several key technologies:
- **IPLD** for content-addressable linked data structures
- **NetworkX** for efficient in-memory graph operations
- **FAISS** (optional) for vector similarity search
- **Content-addressed storage** via IPFS for persistence

## Enabling Knowledge Graph Features

Initialize `ipfs_kit` with `enable_knowledge_graph=True` in the metadata:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

kit = ipfs_kit(metadata={"enable_knowledge_graph": True})

# Access components (if initialization was successful)
if hasattr(kit, 'knowledge_graph'):
    print("Knowledge Graph DB is available.")
if hasattr(kit, 'graph_query'):
    print("Graph Query interface is available.")
if hasattr(kit, 'graph_rag'):
    print("Graph RAG component is available.")

# You might need to interact directly with the components:
kg_db = kit.knowledge_graph
query_interface = kit.graph_query
```

## Basic Usage

### Managing Entities

Entities (nodes) represent distinct objects or concepts in your knowledge domain:

```python
# Add an entity with properties
result = kg_db.add_entity(
    entity_id="document_123",  # Unique identifier 
    entity_type="document",    # Type of entity
    properties={               # Arbitrary properties
        "title": "IPFS: Content Addressed Filesystem",
        "author": "Protocol Labs",
        "year": 2021,
        "url": "https://example.com/ipfs-paper",
        "topics": ["distributed systems", "content addressing", "p2p"]
    },
    vector=[0.1, 0.2, 0.3, ...]  # Optional embedding vector
)

if result["success"]:
    print(f"Added entity with CID: {result['cid']}")
    
# Get an entity
entity = kg_db.get_entity("document_123")
if entity:
    print(f"Title: {entity['properties']['title']}")
    
# Update an entity
update_result = kg_db.update_entity(
    entity_id="document_123",
    properties={
        "citation_count": 42,  # Add new property
        "tags": ["distributed-systems", "content-addressing"]  # Add another property
    }
)
```

### Managing Relationships

Relationships (edges) define the connections between entities:

```python
# Add a relationship between entities
result = kg_db.add_relationship(
    from_entity="document_123",    # Source entity ID
    to_entity="concept_456",       # Target entity ID
    relationship_type="describes", # Type of relationship
    properties={                   # Optional relationship properties
        "relevance": 0.95,
        "section": "Introduction"
    }
)

if result["success"]:
    print(f"Added relationship: {result['relationship_id']}")
```

### Querying the Graph

Basic query operations to find entities and their relationships:

```python
# Find entities by type
research_papers = kg_db.query_entities(
    entity_type="document",
    properties={"type": "research-paper"},
    limit=10
)

# Find entities related to a specific entity
related_concepts = kg_db.query_related(
    entity_id="document_123",
    relationship_type="describes",
    direction="outgoing"  # Can be "outgoing", "incoming", or "both"
)

# Find paths between entities
paths = kg_db.path_between(
    source_id="author_789",
    target_id="concept_456", 
    max_depth=3,  # Maximum number of hops
    relationship_types=["authored", "describes"]  # Optional filter for relationship types
)

for path in paths:
    print("Path found:")
    for step in path:
        entity_id, relationship_id = step
        print(f"  {entity_id} {'via ' + relationship_id if relationship_id else ''}")
```

## Advanced Features

### Vector Search

Find entities by vector similarity:

```python
# Vector similarity search
similar_entities = kg_db.vector_search(
    query_vector=[0.1, 0.2, 0.3, ...],  # Vector to compare against 
    top_k=5  # Number of results to return
)

for result in similar_entities:
    entity = kg_db.get_entity(result["entity_id"])
    print(f"Entity: {entity['properties'].get('title', result['entity_id'])}")
    print(f"Similarity score: {result['score']:.4f}")
```

### GraphRAG (Graph Retrieval Augmented Generation)

GraphRAG combines vector similarity with graph traversal for enhanced information retrieval. This is particularly useful for providing contextually relevant information to large language models:

```python
# First, we need to ensure the GraphRAG component is available (requires embedding model)
from sentence_transformers import SentenceTransformer

# Create an embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize GraphRAG with the graph and embedding model
graph_rag = GraphRAG(kg_db, embedding_model)

# Retrieve context based on a text query
context = graph_rag.retrieve(
    query_text="How does content addressing work in IPFS?",
    entity_types=["document", "concept"],  # Optional filter by entity types
    top_k=5,  # Number of direct matches to consider
    hop_count=1  # How many steps to explore from matching entities
)

# Format the context for inclusion in an LLM prompt
formatted_context = graph_rag.format_context_for_llm(
    context,
    format_type="markdown"  # Can be "text", "json", or "markdown"
)

# Generate a complete prompt for an LLM
prompt = graph_rag.generate_llm_prompt(
    user_query="Explain content addressing in IPFS",
    context=context,
    prompt_template="""Answer the following question based on the provided knowledge graph context.

Context:
{context}

Question: {question}

Answer:"""
)

# Now you can send this prompt to your LLM of choice
```

### Version History and Change Tracking

The knowledge graph tracks changes, enabling version history:

```python
# Get version history for the entire graph
history = kg_db.get_version_history(limit=20)

for change in history:
    print(f"{change['timestamp']}: {change['operation']} - {change.get('entity_id', change.get('relationship_id'))}")
    
# Get version history for a specific entity
entity_history = kg_db.get_version_history(entity_id="document_123")
```

### Subgraph Export and Import

Share portions of your knowledge graph:

```python
# Export a subgraph starting from certain entities
subgraph = kg_db.export_subgraph(
    entity_ids=["document_123", "concept_456"],
    include_relationships=True,
    max_hops=2  # Include entities up to 2 hops away
)

# Save to file
with open("research_subgraph.json", "w") as f:
    json.dump(subgraph, f)
    
# Later, import into another graph
with open("research_subgraph.json", "r") as f:
    imported_subgraph = json.load(f)
    
new_graph_db = IPLDGraphDB(ipfs_client)
import_result = new_graph_db.import_subgraph(
    imported_subgraph,
    merge_strategy="update"  # Can be "update", "replace", or "skip"
)

print(f"Imported {import_result['entities_added']} entities and {import_result['relationships_added']} relationships")
```

## Implementation Details

### IPLD Schema Design

The knowledge graph uses the following IPLD schemas:

#### Entity Schema
```json
{
  "type": "struct",
  "fields": {
    "id": {"type": "string"},
    "type": {"type": "string"},
    "created_at": {"type": "float"},
    "updated_at": {"type": "float"},
    "properties": {"type": "map", "keyType": "string", "valueType": "any"},
    "relationships": {"type": "list", "valueType": "link"},
    "vector": {"type": "list", "valueType": "float", "optional": true}
  }
}
```

#### Relationship Schema
```json
{
  "type": "struct",
  "fields": {
    "id": {"type": "string"},
    "from": {"type": "string"},
    "to": {"type": "string"},
    "type": {"type": "string"},
    "created_at": {"type": "float"},
    "properties": {"type": "map", "keyType": "string", "valueType": "any"}
  }
}
```

#### Root Schema
```json
{
  "type": "struct",
  "fields": {
    "schema_version": {"type": "string"},
    "created_at": {"type": "float"},
    "updated_at": {"type": "float"},
    "entity_count": {"type": "int"},
    "relationship_count": {"type": "int"},
    "entities_index_cid": {"type": "link", "optional": true},
    "relationships_index_cid": {"type": "link", "optional": true},
    "vector_index_cid": {"type": "link", "optional": true},
    "change_log_cid": {"type": "link", "optional": true}
  }
}
```

### Storage Patterns

The knowledge graph uses several storage patterns to balance performance and flexibility:

1. **Content-Addressed Entities**: Each entity is stored as a separate IPLD object identified by CID
2. **Content-Addressed Relationships**: Each relationship is stored as a separate IPLD object identified by CID
3. **In-Memory Indexes**: Efficient in-memory indexes for entities and relationships during operation
4. **Periodic Persistence**: In-memory state is periodically persisted to IPFS to ensure durability
5. **Memory-Mapped Access**: When possible, memory mapping is used for efficient access to large indexes
6. **Lazy Loading**: Entity data is loaded on-demand to minimize memory usage
7. **Vector Storage**: Entity vectors are stored alongside entities but can be separated for large collections

### Indexing Strategy

The knowledge graph maintains several indexes for efficient operation:

1. **Entity Index**: Maps entity IDs to their CIDs and metadata
2. **Relationship Index**: Maps relationship IDs to their CIDs
3. **Entity Relationships Index**: For each entity, tracks its relationships
4. **Vector Index**: Maps vector IDs to entity IDs and stores the vectors themselves
5. **NetworkX Graph**: In-memory graph representation for efficient traversal and path finding

### NetworkX Integration

The implementation uses NetworkX for efficient in-memory graph operations:

```python
# The graph is accessible directly if needed for advanced operations
nx_graph = kg_db.graph

# Calculate graph metrics
density = nx.density(nx_graph)
avg_clustering = nx.average_clustering(nx_graph)
connected_components = nx.number_connected_components(nx_graph.to_undirected())

# Find central nodes
betweenness = nx.betweenness_centrality(nx_graph)
most_central = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:5]
```

## Performance Considerations

### Scaling Knowledge Graphs

The IPLD Knowledge Graph is designed to handle large-scale knowledge bases efficiently. Here are key considerations for optimal performance:

#### Entity and Relationship Management

1. **Entity ID Design**: 
   - Choose entity IDs that are meaningful, stable, and unique
   - Consider namespace prefixes for different entity types (e.g., `doc:`, `person:`, `concept:`)
   - Avoid excessively long IDs which increase storage requirements
   - Example pattern: `{type}:{uuid}` or `{type}:{slug}`

2. **Batch Operations**:
   - Use batch imports when adding multiple entities or relationships
   - The `add_entities_batch()` method is 5-10x faster than individual adds:
   ```python
   entities = [
       {"id": "doc1", "type": "document", "properties": {...}},
       {"id": "doc2", "type": "document", "properties": {...}},
       # ...
   ]
   kg_db.add_entities_batch(entities)
   ```

3. **Relationship Management**:
   - Limit relationship types to a well-defined taxonomy (ideally <100 types)
   - Use bidirectional indexing for frequently traversed relationships
   - Consider materializing common traversal paths for performance-critical queries

#### Vector Operations

1. **Vector Dimensionality**:
   - Keep embedding dimensions reasonable (128-768) for efficient similarity search
   - Benchmark dimensions vs. quality for your specific use case
   - Consider dimension reduction techniques for very large graphs:
   ```python
   from sklearn.decomposition import PCA
   
   # Reduce high-dimensional embeddings
   pca = PCA(n_components=128)
   reduced_vectors = pca.fit_transform(original_vectors)
   ```

2. **Vector Index Types**:
   - For small graphs (<10K entities): Use in-memory flat index (default)
   - For medium graphs (10K-100K): Use HNSW index with `M=16, ef_construction=200`
    - For large graphs (>100K): Use a dedicated vector store backend with quantization
   ```python
   # Configure HNSW index for medium-sized graphs
   kg_db.configure_vector_index(
       index_type="hnsw",
       M=16,                # Number of connections per layer
       ef_construction=200, # Build-time accuracy vs. speed tradeoff
       ef=50                # Query-time accuracy vs. speed tradeoff
   )
   ```

3. **Vector Batching**:
   - Use batch queries when performing multiple vector searches
   - Combine multiple query vectors in a single operation when possible

#### Query Optimization

1. **GraphRAG Tuning**:
   - Start with `hop_count=1` and only increase if needed
   - Each additional hop exponentially increases traversal complexity
   - Use path type filtering to limit relationship traversal:
   ```python
   results = graph_rag.retrieve(
       query_text="content addressing",
       hop_count=1,
       path_types=["DISCUSSES", "MENTIONS", "RELATES_TO"]  # Limit to semantic relationships
   )
   ```

2. **Traversal Optimization**:
   - Set appropriate depth limits (typically 2-3 maximum)
   - Use directional traversal when possible (`direction="outgoing"`)
   - Apply entity type filters to narrow the traversal space
   ```python
   paths = kg_db.path_between(
       source_id="author123",
       target_id="concept456",
       max_depth=3,
       relationship_types=["AUTHORED", "CONTAINS", "DISCUSSES"],
       entity_types=["Document", "Concept"]  # Only traverse through these types
   )
   ```

3. **Memory vs. Storage Tradeoffs**:
   - For frequently accessed entities, increase cache size:
   ```python
   kg_db.configure_cache(max_entities=10000, max_relationships=50000)
   ```
   - For large but infrequently modified graphs, use `persistence_mode="batch"`:
   ```python
   kg_db = IPLDGraphDB(ipfs_client, persistence_mode="batch", batch_interval=300)
   ```

### Benchmarks

Typical performance metrics for different graph sizes on recommended hardware (8 cores, 32GB RAM):

| Operation | Small Graph (<10K entities) | Medium Graph (10K-100K) | Large Graph (>100K) |
|-----------|-----------------------------|--------------------------|--------------------|
| Entity add | <10ms | 10-50ms | 50-200ms |
| Batch add (100) | <100ms | 100-500ms | 500-2000ms |
| Entity retrieval | <5ms | 5-20ms | 20-100ms |
| Vector search (top 10) | <20ms | 20-100ms | 100-500ms |
| GraphRAG (hop=1) | <50ms | 50-200ms | 200-1000ms |
| GraphRAG (hop=2) | <200ms | 200-1000ms | 1-5s |
| Path query (depth=2) | <100ms | 100-500ms | 0.5-2s |
| Path query (depth=3) | <300ms | 300-2000ms | 2-10s |

### Monitoring and Optimization

The knowledge graph provides built-in monitoring:

```python
# Get performance metrics
metrics = kg_db.get_performance_metrics()

print(f"Vector search average latency: {metrics['vector_search']['mean_latency_ms']}ms")
print(f"Graph traversal average latency: {metrics['graph_traversal']['mean_latency_ms']}ms")
print(f"Cache hit rate: {metrics['cache']['hit_rate'] * 100:.1f}%")

# Optimize the graph structure based on access patterns
kg_db.optimize()
```

For detailed profiling, you can enable the performance tracking mode:

```python
kg_db.enable_performance_tracking(
    sample_rate=0.1,  # Track 10% of operations
    detailed=True,    # Include detailed breakdowns
    log_slow=True,    # Log operations taking >100ms
    slow_threshold=100  # Threshold in milliseconds
)
```

### Performance Visualization

You can visualize the knowledge graph performance metrics using the visualization capabilities in the `ai_ml_visualization` module:

```python
from ipfs_kit_py.ai_ml_metrics import AIMLMetricsCollector
from ipfs_kit_py.ai_ml_visualization import create_visualization

# Create a metrics collector
metrics = AIMLMetricsCollector()

# Configure knowledge graph to use metrics
kg_db = kit.knowledge_graph
kg_db.set_metrics_collector(metrics)

# Perform some operations
results = kg_db.vector_search(query_vector=[0.1, 0.2, 0.3], top_k=10)
graph_results = kg_db.graph_vector_search(query_vector=[0.1, 0.2, 0.3], hop_count=2)

# Create visualization
viz = create_visualization(metrics, interactive=True)

# Visualize knowledge graph performance
viz.plot_graph_operations(
    figsize=(12, 8),
    show_plot=True
)

# Visualize GraphRAG performance
viz.plot_graph_rag_metrics(
    figsize=(10, 6),
    show_plot=True
)

# Create a comprehensive dashboard
viz.plot_comprehensive_dashboard(
    output_file="knowledge_graph_metrics.html"
)
```

This visualization provides insights into:
- Vector search performance vs. graph hop count
- Query latency by operation type
- Cache hit/miss rates for entities and relationships
- GraphRAG path exploration efficiency
- Memory usage across different graph sizes

For more details, see the [AI/ML Visualization Guide](integration/ai-ml/ai_ml_visualization.md).

## Integration with Other Components

The IPLD Knowledge Graph integrates with other IPFS Kit components:

### Arrow Metadata Index

For projects using both the Knowledge Graph and the Arrow Metadata Index:

```python
from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex

# First, retrieve entities using the Arrow Metadata Index
metadata_index = ArrowMetadataIndex(ipfs_client)
records = metadata_index.query([
    ("mime_type", "==", "application/pdf"),
    ("tags", "contains", "research")
])

# Then, integrate these with the knowledge graph
for record in records:
    # Add as an entity
    kg_db.add_entity(
        entity_id=record["cid"],
        entity_type="document",
        properties={
            "title": record.get("title", "Untitled"),
            "mime_type": record.get("mime_type"),
            "size_bytes": record.get("size_bytes"),
            "tags": record.get("tags", [])
        }
    )
```

### FSSpec Interface

The Knowledge Graph can be integrated with the FSSpec filesystem interface:

```python
from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem

# Initialize filesystem
fs = IPFSFileSystem()

# Read a file's content
with fs.open(f"ipfs://{document_cid}", "r") as f:
    content = f.read()
    
# Process and add to knowledge graph
entity_id = f"doc_{document_cid}"
kg_db.add_entity(
    entity_id=entity_id,
    entity_type="document",
    properties={
        "content": content[:1000],  # First 1000 chars as preview
        "cid": document_cid,
        "size": len(content)
    }
)
```

## Example Use Cases

### Building a Research Paper Knowledge Graph

This example demonstrates how to build a comprehensive research paper knowledge graph that connects papers, authors, concepts, and citations:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.ipld_knowledge_graph import IPLDGraphDB
import json

# Initialize IPFS kit with knowledge graph support
kit = ipfs_kit(metadata={"enable_knowledge_graph": True})
kg = kit.knowledge_graph

# Define entity types and relationship types for schema consistency
ENTITY_TYPES = {
    "PAPER": "research_paper",
    "AUTHOR": "person",
    "CONCEPT": "concept",
    "VENUE": "publication_venue"
}

RELATIONSHIP_TYPES = {
    "AUTHORED": "authored",
    "DISCUSSES": "discusses",
    "CITES": "cites",
    "PUBLISHED_IN": "published_in",
    "RELATED_TO": "related_to"
}

# Helper function to create paper entities with consistent schema
def add_research_paper(kg, paper_id, title, authors, year, abstract, doi=None, url=None, venues=None, keywords=None):
    """Add a research paper with consistent schema."""
    properties = {
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract,
    }
    
    # Add optional properties if provided
    if doi:
        properties["doi"] = doi
    if url:
        properties["url"] = url
    if venues:
        properties["venues"] = venues
    if keywords:
        properties["keywords"] = keywords
        
    result = kg.add_entity(
        entity_id=f"paper:{paper_id}",
        entity_type=ENTITY_TYPES["PAPER"],
        properties=properties
    )
    
    return result

# Helper function for adding authors with consistent schema
def add_author(kg, author_id, name, affiliation=None, email=None, orcid=None):
    """Add an author with consistent schema."""
    properties = {
        "name": name,
    }
    
    if affiliation:
        properties["affiliation"] = affiliation
    if email:
        properties["email"] = email
    if orcid:
        properties["orcid"] = orcid
        
    result = kg.add_entity(
        entity_id=f"author:{author_id}",
        entity_type=ENTITY_TYPES["AUTHOR"],
        properties=properties
    )
    
    return result

# Helper function to connect paper with authors
def connect_paper_to_authors(kg, paper_id, author_ids, contribution_types=None):
    """Create relationships between paper and its authors."""
    if contribution_types is None:
        contribution_types = ["author"] * len(author_ids)
        
    for i, author_id in enumerate(author_ids):
        props = {"order": i + 1, "contribution_type": contribution_types[i]}
        
        kg.add_relationship(
            from_entity=f"author:{author_id}",
            to_entity=f"paper:{paper_id}",
            relationship_type=RELATIONSHIP_TYPES["AUTHORED"],
            properties=props
        )

# Add research papers
add_research_paper(
    kg,
    paper_id="ipfs2014",
    title="IPFS - Content Addressed, Versioned, P2P File System",
    authors=["Juan Benet"],
    year=2014,
    abstract="IPFS is a peer-to-peer distributed file system that seeks to connect all computing devices with the same system of files. IPFS combines good ideas from Git, BitTorrent, Kademlia, SFS, and the Web. The result is a single BitTorrent swarm, exchanging git objects. IPFS provides an interface as simple as HTTP, but instead of location addressing it uses content addressing.",
    doi="10.48550/arXiv.1407.3561",
    keywords=["content addressing", "distributed systems", "p2p", "DHT"]
)

add_research_paper(
    kg,
    paper_id="filecoin2017",
    title="Filecoin: A Decentralized Storage Network",
    authors=["Protocol Labs"],
    year=2017,
    abstract="Filecoin is a distributed electronic currency similar to Bitcoin. Unlike Bitcoin, Filecoin's miners provide useful services: they rent their unused hard-drive space to others. Filecoin is built upon a data structure called the InterPlanetary Linked Data (IPLD) which connects and links different blocks on top of IPFS.",
    url="https://filecoin.io/filecoin.pdf",
    keywords=["blockchain", "storage", "incentives", "crypto-economics"]
)

add_research_paper(
    kg, 
    paper_id="merkledag2021",
    title="MerkleDAG: A Content-Addressable Graph Structure for IPFS",
    authors=["Alice Johnson", "Bob Smith"],
    year=2021,
    abstract="This paper explores the MerkleDAG data structure that underlies IPFS, analyzing its performance characteristics and security properties in distributed systems.",
    keywords=["merkle trees", "content addressing", "distributed data structures"]
)

# Add authors
add_author(
    kg,
    author_id="juan_benet",
    name="Juan Benet",
    affiliation="Protocol Labs",
    orcid="0000-0002-1111-2222"
)

add_author(
    kg,
    author_id="alice_johnson",
    name="Alice Johnson",
    affiliation="University of Distributed Systems",
    email="alice@example.edu"
)

add_author(
    kg,
    author_id="bob_smith",
    name="Bob Smith",
    affiliation="Decentralized Research Institute",
    email="bob@example.edu"
)

# Connect papers to authors
connect_paper_to_authors(kg, "ipfs2014", ["juan_benet"])
connect_paper_to_authors(kg, "merkledag2021", ["alice_johnson", "bob_smith"], 
                        ["corresponding author", "author"])

# Add key concepts
for concept_info in [
    {"id": "content_addressing", "name": "Content Addressing", 
     "description": "A technique to store and retrieve data based on its content rather than its location."},
    {"id": "dht", "name": "Distributed Hash Table", 
     "description": "A distributed system that provides a lookup service similar to a hash table."},
    {"id": "merkle_dag", "name": "MerkleDAG", 
     "description": "A directed acyclic graph where each node is identified by the hash of its contents."},
    {"id": "p2p", "name": "Peer-to-Peer Networking", 
     "description": "A distributed application architecture that partitions tasks between peers."}
]:
    kg.add_entity(
        entity_id=f"concept:{concept_info['id']}",
        entity_type=ENTITY_TYPES["CONCEPT"],
        properties={
            "name": concept_info["name"],
            "description": concept_info["description"]
        }
    )

# Add publication venues
for venue_info in [
    {"id": "arxiv", "name": "arXiv", "type": "preprint server"},
    {"id": "ieee_dsc", "name": "IEEE Distributed Systems Conference", "type": "conference"}
]:
    kg.add_entity(
        entity_id=f"venue:{venue_info['id']}",
        entity_type=ENTITY_TYPES["VENUE"],
        properties={
            "name": venue_info["name"],
            "venue_type": venue_info["type"]
        }
    )

# Connect papers to venues
kg.add_relationship(
    from_entity="paper:ipfs2014",
    to_entity="venue:arxiv",
    relationship_type=RELATIONSHIP_TYPES["PUBLISHED_IN"]
)

kg.add_relationship(
    from_entity="paper:merkledag2021",
    to_entity="venue:ieee_dsc",
    relationship_type=RELATIONSHIP_TYPES["PUBLISHED_IN"]
)

# Connect papers to concepts they discuss
concept_relationships = [
    ("paper:ipfs2014", "concept:content_addressing", "primary"),
    ("paper:ipfs2014", "concept:dht", "secondary"),
    ("paper:ipfs2014", "concept:p2p", "primary"),
    ("paper:filecoin2017", "concept:content_addressing", "secondary"),
    ("paper:merkledag2021", "concept:merkle_dag", "primary"),
    ("paper:merkledag2021", "concept:content_addressing", "primary")
]

for paper_id, concept_id, centrality in concept_relationships:
    kg.add_relationship(
        from_entity=paper_id,
        to_entity=concept_id,
        relationship_type=RELATIONSHIP_TYPES["DISCUSSES"],
        properties={"centrality": centrality}
    )

# Add citation relationships
kg.add_relationship(
    from_entity="paper:filecoin2017",
    to_entity="paper:ipfs2014",
    relationship_type=RELATIONSHIP_TYPES["CITES"],
    properties={"context": "foundation technology"}
)

kg.add_relationship(
    from_entity="paper:merkledag2021",
    to_entity="paper:ipfs2014",
    relationship_type=RELATIONSHIP_TYPES["CITES"],
    properties={"context": "original description"}
)

# Demonstrate different query patterns
print("\n=== KNOWLEDGE GRAPH QUERIES ===")

# 1. Find papers discussing a specific concept
papers_discussing_content_addressing = kg.query_related(
    entity_id="concept:content_addressing",
    relationship_type=RELATIONSHIP_TYPES["DISCUSSES"],
    direction="incoming"
)
print("\nPapers discussing Content Addressing:")
for paper in papers_discussing_content_addressing:
    paper_entity = kg.get_entity(paper["entity_id"])
    centrality = paper.get("properties", {}).get("centrality", "mentioned")
    print(f"- {paper_entity['properties']['title']} ({centrality} topic)")

# 2. Find authors' papers
papers_by_author = kg.query_related(
    entity_id="author:juan_benet",
    relationship_type=RELATIONSHIP_TYPES["AUTHORED"],
    direction="outgoing"
)
print("\nPapers by Juan Benet:")
for paper in papers_by_author:
    paper_entity = kg.get_entity(paper["entity_id"])
    print(f"- {paper_entity['properties']['title']} ({paper_entity['properties']['year']})")

# 3. Find paths between authors and concepts (research interests)
paths = kg.path_between(
    source_id="author:alice_johnson", 
    target_id="concept:content_addressing",
    max_depth=4
)
print("\nPath from Alice Johnson to Content Addressing:")
for path in paths:
    path_str = ""
    for i, item in enumerate(path):
        if i % 2 == 0:  # Entity
            entity = kg.get_entity(item)
            name = entity["properties"].get("name", entity["properties"].get("title", item))
            path_str += name
        else:  # Relationship
            path_str += f" --[{item}]--> "
    print(f"Path: {path_str}")

# 4. Find papers published in specific venues
papers_in_arxiv = kg.query_related(
    entity_id="venue:arxiv",
    relationship_type=RELATIONSHIP_TYPES["PUBLISHED_IN"],
    direction="incoming"
)
print("\nPapers published in arXiv:")
for paper in papers_in_arxiv:
    paper_entity = kg.get_entity(paper["entity_id"])
    print(f"- {paper_entity['properties']['title']}")

# 5. Citation analysis - find what papers cite a given paper
citations = kg.query_related(
    entity_id="paper:ipfs2014",
    relationship_type=RELATIONSHIP_TYPES["CITES"],
    direction="incoming"
)
print("\nPapers citing IPFS paper:")
for paper in citations:
    paper_entity = kg.get_entity(paper["entity_id"])
    context = paper.get("properties", {}).get("context", "general reference")
    print(f"- {paper_entity['properties']['title']} (context: {context})")

# Visualize a subgraph (pseudocode - actual implementation would use a visualization library)
print("\nExporting subgraph for visualization...")
subgraph = kg.export_subgraph(
    entity_ids=["paper:ipfs2014", "concept:content_addressing"],
    include_relationships=True,
    max_hops=2
)

# Save to file for external visualization
with open("research_graph.json", "w") as f:
    json.dump(subgraph, f, indent=2)
print("Subgraph exported to research_graph.json")
```

The resulting knowledge graph enables sophisticated queries across research papers, authors, concepts, and publication venues:

1. **Domain Expertise Mapping**: Find which authors are experts in specific concepts based on their publication history
2. **Citation Networks**: Analyze how papers influence each other through citation patterns
3. **Research Topic Evolution**: Track how concepts evolve and connect across different papers over time
4. **Collaboration Networks**: Discover collaboration patterns between researchers

### Implementing a GraphRAG System for AI

This example demonstrates how to implement a sophisticated GraphRAG system for AI applications that handles both retrieval and generation:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.ipld_knowledge_graph import IPLDGraphDB, GraphRAG
from sentence_transformers import SentenceTransformer
import json
import time
import requests

# Initialize IPFS kit with knowledge graph support
kit = ipfs_kit(metadata={"enable_knowledge_graph": True})
kg = kit.knowledge_graph

# Initialize embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize GraphRAG
graph_rag = GraphRAG(kg, embedding_model)

# Configuration for LLM access
LLM_API_URL = "https://your-llm-api-endpoint.com/generate"
LLM_API_KEY = "your_api_key"  # In production, retrieve from secure storage

# Helper function to call LLM API
def call_llm(prompt, max_tokens=500, temperature=0.7):
    """Call external LLM API with the given prompt."""
    try:
        response = requests.post(
            LLM_API_URL,
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["text"]
    except Exception as e:
        print(f"Error calling LLM API: {e}")
        return "Sorry, I encountered an error generating a response."

# Create a GraphRAG assistant for answering questions
def answer_question(question, hop_count=2, top_k=8):
    """Generate an answer to a question using GraphRAG and an LLM."""
    start_time = time.time()
    
    # Phase 1: Retrieve relevant context from the knowledge graph
    context = graph_rag.retrieve(
        query_text=question,
        hop_count=hop_count,
        top_k=top_k
    )
    
    retrieval_time = time.time() - start_time
    print(f"Retrieved {len(context['entities'])} entities in {retrieval_time:.2f}s")
    
    # Phase 2: Format the context for the LLM
    formatted_context = graph_rag.format_context_for_llm(
        context,
        format_type="markdown"
    )
    
    # Phase 3: Generate a prompt with structured instructions
    prompt = graph_rag.generate_llm_prompt(
        user_query=question,
        context=context,
        prompt_template="""You are a knowledgeable assistant with expertise in distributed systems, IPFS, and content-addressed storage. 
Answer the following question based on the provided knowledge graph context.

The context information contains entities and relationships from a knowledge graph. Some items are directly related to the question, while others were found through relationship traversal. Pay attention to the relationship paths to understand how different pieces of information are connected.

Use information from multiple sources when applicable to provide a comprehensive answer. Cite specific documents or concepts from the context when appropriate.

Context:
{context}

Question: {question}

Answer:"""
    )
    
    # Phase 4: Generate an answer using the LLM
    response = call_llm(prompt, max_tokens=800)
    
    # Phase 5: Add citations to the response
    entity_ids = [entity_id for entity_id in context["entities"]]
    citation_info = {}
    
    # Collect citation information for all mentioned entities
    for entity_id in entity_ids:
        entity = kg.get_entity(entity_id)
        if not entity:
            continue
            
        if entity["type"] == "research_paper":
            citation_info[entity_id] = {
                "title": entity["properties"].get("title", "Unknown"),
                "authors": entity["properties"].get("authors", ["Unknown"]),
                "year": entity["properties"].get("year", "Unknown"),
                "doi": entity["properties"].get("doi", "")
            }
        elif entity["type"] in ["documentation", "section"]:
            citation_info[entity_id] = {
                "title": entity["properties"].get("title", "Unknown"),
                "path": entity["properties"].get("path", ""),
                "type": "Documentation"
            }
        elif entity["type"] == "concept":
            citation_info[entity_id] = {
                "name": entity["properties"].get("name", "Unknown"),
                "type": "Concept"
            }
    
    # Add citations to the response
    if citation_info:
        response += "\n\nSources:\n"
        for entity_id, citation in citation_info.items():
            if "authors" in citation:  # Research paper
                authors = ", ".join(citation["authors"]) if isinstance(citation["authors"], list) else citation["authors"]
                response += f"- {authors} ({citation['year']}). {citation['title']}. {citation['doi']}\n"
            elif citation.get("type") == "Documentation":
                response += f"- Documentation: {citation['title']} ({citation.get('path', '')})\n"
            elif citation.get("type") == "Concept":
                response += f"- Concept: {citation['name']}\n"
    
    # Calculate total time
    total_time = time.time() - start_time
    
    return {
        "question": question,
        "answer": response,
        "context_items": len(context["entities"]),
        "retrieved_paths": [result["path"] for result in context["results"]],
        "retrieval_time": retrieval_time,
        "total_time": total_time,
        "sources": list(citation_info.keys())
    }

# Example usage
questions = [
    "How does content addressing in IPFS relate to data deduplication?",
    "What's the relationship between IPFS and IPLD?",
    "How does the MerkleDAG structure ensure data integrity in IPFS?"
]

for question in questions:
    print(f"\n\nQUESTION: {question}")
    result = answer_question(question)
    print("\nANSWER:")
    print(result["answer"])
    print(f"\nRetrieved {result['context_items']} items in {result['retrieval_time']:.2f}s")
    print(f"Total processing time: {result['total_time']:.2f}s")
    print("\n" + "-"*80)

# Advanced usage: Multi-hop traversal analysis
def analyze_traversal_effectiveness(question, hop_counts=[0, 1, 2, 3]):
    """Analyze the effectiveness of different hop counts for a question."""
    results = {}
    
    for hops in hop_counts:
        context = graph_rag.retrieve(
            query_text=question,
            hop_count=hops,
            top_k=10
        )
        
        # Analyze retrieved entities
        direct_hits = 0
        indirect_hits = 0
        
        for result in context["results"]:
            if result["distance"] == 0:
                direct_hits += 1
            else:
                indirect_hits += 1
                
        # Score relevance (this would typically involve human evaluation)
        # Here we use a simple heuristic based on vector similarity
        relevance_scores = [r["score"] for r in context["results"]]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        
        results[hops] = {
            "entity_count": len(context["entities"]),
            "direct_hits": direct_hits,
            "indirect_hits": indirect_hits,
            "avg_relevance": avg_relevance,
            "unique_paths": len(set(tuple(r["path"]) for r in context["results"]))
        }
    
    return results

# Run traversal analysis on a complex question
complex_question = "How do IPFS content addressing and UnixFS work together to enable file versioning?"
analysis = analyze_traversal_effectiveness(complex_question)

print("\nTRAVERSAL ANALYSIS:")
print(f"Question: {complex_question}")
print("\nEffectiveness by hop count:")
for hops, metrics in analysis.items():
    print(f"Hop count {hops}:")
    print(f"  - Total entities: {metrics['entity_count']}")
    print(f"  - Direct vector matches: {metrics['direct_hits']}")
    print(f"  - Graph-traversal discoveries: {metrics['indirect_hits']}")
    print(f"  - Unique reasoning paths: {metrics['unique_paths']}")
    print(f"  - Average relevance score: {metrics['avg_relevance']:.4f}")
    print()
```

This AI-focused GraphRAG implementation provides several advanced capabilities:

1. **Contextual Understanding**: Uses graph traversal to provide rich context that pure vector similarity might miss
2. **Reasoning Path Transparency**: Explains how each piece of information relates to the query
3. **Source Attribution**: Provides detailed citation information for all sources used
4. **Performance Measurement**: Tracks and analyzes both retrieval and generation timing
5. **Traversal Analysis**: Quantifies the value added by graph traversal vs. direct vector matches
6. **Template-Based Prompting**: Uses structured templates to guide the LLM's reasoning process

The system can be extended with:

- **User Feedback Loop**: Incorporate user ratings to improve traversal algorithms
- **Dynamic Hop Adjustment**: Automatically tune hop count based on query complexity
- **Prompt Engineering**: Optimize prompts based on retrieval results
- **Multi-Turn Dialogue**: Maintain conversational context across multiple questions
- **Knowledge Graph Expansion**: Add newly generated knowledge back to the graph

### Implementing a GraphRAG System for Technical Documentation

This example demonstrates how to build a GraphRAG system for technical documentation that leverages both semantic embeddings and graph structure:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.ipld_knowledge_graph import IPLDGraphDB
import os
import glob
import json
import markdown
import re
from sentence_transformers import SentenceTransformer
from bs4 import BeautifulSoup

# Initialize IPFS kit with knowledge graph support
kit = ipfs_kit(metadata={"enable_knowledge_graph": True})
kg = kit.knowledge_graph

# Initialize embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim embeddings

# Define entity and relationship types
ENTITY_TYPES = {
    "DOCUMENT": "documentation",
    "SECTION": "section",
    "CONCEPT": "concept",
    "CODE_EXAMPLE": "code_example",
    "API": "api_reference"
}

RELATIONSHIP_TYPES = {
    "CONTAINS": "contains",
    "REFERENCES": "references",
    "RELATED_TO": "related_to",
    "IMPLEMENTS": "implements",
    "EXPLAINS": "explains"
}

# Helper function to process markdown files
def process_markdown_file(file_path):
    """Process a markdown file into document, sections, and concepts."""
    with open(file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Extract metadata from frontmatter if present
    metadata = {}
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n', md_content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        for line in frontmatter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()
        # Remove frontmatter from content
        md_content = re.sub(r'^---\n.*?\n---\n', '', md_content, flags=re.DOTALL)
    
    # Get document title from first heading or filename
    title_match = re.search(r'^# (.*?)$', md_content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)
    else:
        title = os.path.splitext(os.path.basename(file_path))[0].replace('_', ' ').title()
    
    # Convert markdown to HTML for easier parsing
    html_content = markdown.markdown(md_content)
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Create document entity
    doc_id = os.path.splitext(os.path.basename(file_path))[0]
    doc_entity = {
        "id": f"doc:{doc_id}",
        "type": ENTITY_TYPES["DOCUMENT"],
        "properties": {
            "title": title,
            "path": file_path,
            "updated_at": os.path.getmtime(file_path),
            "word_count": len(md_content.split()),
            **metadata  # Include any metadata from frontmatter
        }
    }
    
    # Generate document embedding from full content
    doc_embedding = embedding_model.encode(md_content)
    doc_entity["vector"] = doc_embedding.tolist()
    
    # Add document to knowledge graph
    kg.add_entity(
        entity_id=doc_entity["id"],
        entity_type=doc_entity["type"],
        properties=doc_entity["properties"],
        vector=doc_entity["vector"]
    )
    
    # Process sections (h2 headings)
    sections = []
    section_tags = soup.find_all(['h2'])
    
    for i, section_tag in enumerate(section_tags):
        section_title = section_tag.text
        section_id = f"{doc_id}_section_{i}"
        
        # Get section content (everything until next h2 or end)
        section_content = []
        current = section_tag.next_sibling
        while current and (not current.name or current.name != 'h2'):
            if current.string:
                section_content.append(current.string)
            current = current.next_sibling
        
        section_text = ' '.join([str(c).strip() for c in section_content if str(c).strip()])
        
        # Create section entity
        section_entity = {
            "id": f"section:{section_id}",
            "type": ENTITY_TYPES["SECTION"],
            "properties": {
                "title": section_title,
                "content": section_text[:1000],  # First 1000 chars as preview
                "order": i,
                "word_count": len(section_text.split())
            }
        }
        
        # Generate section embedding
        if section_text:
            section_embedding = embedding_model.encode(section_text)
            section_entity["vector"] = section_embedding.tolist()
        
        # Add section to knowledge graph
        kg.add_entity(
            entity_id=section_entity["id"],
            entity_type=section_entity["type"],
            properties=section_entity["properties"],
            vector=section_entity.get("vector")
        )
        
        # Connect section to document
        kg.add_relationship(
            from_entity=doc_entity["id"],
            to_entity=section_entity["id"],
            relationship_type=RELATIONSHIP_TYPES["CONTAINS"],
            properties={"order": i}
        )
        
        sections.append(section_entity)
        
        # Extract code examples from section
        code_blocks = re.findall(r'```(\w*)\n(.*?)```', section_text, re.DOTALL)
        for j, (lang, code) in enumerate(code_blocks):
            code_id = f"{section_id}_code_{j}"
            
            # Create code example entity
            code_entity = {
                "id": f"code:{code_id}",
                "type": ENTITY_TYPES["CODE_EXAMPLE"],
                "properties": {
                    "language": lang if lang else "text",
                    "code": code,
                    "line_count": len(code.split('\n'))
                }
            }
            
            # Add code example to knowledge graph
            kg.add_entity(
                entity_id=code_entity["id"],
                entity_type=code_entity["type"],
                properties=code_entity["properties"]
            )
            
            # Connect code example to section
            kg.add_relationship(
                from_entity=section_entity["id"],
                to_entity=code_entity["id"],
                relationship_type=RELATIONSHIP_TYPES["CONTAINS"],
                properties={"order": j}
            )
    
    # Extract potential concepts (based on bold text or links)
    concepts = set()
    for bold in soup.find_all(['strong', 'b']):
        concept = bold.text.strip()
        if len(concept.split()) <= 5 and len(concept) > 3:  # Simple heuristic for concept names
            concepts.add(concept)
    
    for link in soup.find_all('a'):
        concept = link.text.strip()
        if len(concept.split()) <= 5 and len(concept) > 3:
            concepts.add(concept)
    
    # Add concepts and connect to document
    for concept in concepts:
        concept_id = re.sub(r'[^a-z0-9]', '_', concept.lower())
        
        # Check if concept already exists
        existing_concept = kg.get_entity(f"concept:{concept_id}")
        if not existing_concept:
            # Create new concept
            kg.add_entity(
                entity_id=f"concept:{concept_id}",
                entity_type=ENTITY_TYPES["CONCEPT"],
                properties={
                    "name": concept,
                    "occurrences": 1
                }
            )
        else:
            # Update occurrence count
            occurrences = existing_concept["properties"].get("occurrences", 0) + 1
            kg.update_entity(
                entity_id=f"concept:{concept_id}",
                properties={"occurrences": occurrences}
            )
        
        # Connect document to concept
        kg.add_relationship(
            from_entity=doc_entity["id"],
            to_entity=f"concept:{concept_id}",
            relationship_type=RELATIONSHIP_TYPES["REFERENCES"]
        )
    
    return doc_entity, sections

# Helper function to find related documents for a given entity
def find_related_documents(entity_id, max_hops=2):
    """Find documents related to an entity through graph traversal."""
    related_docs = kg.graph_vector_search(
        entity_id=entity_id,
        hop_count=max_hops,
        top_k=5
    )
    
    result = []
    for item in related_docs:
        entity = kg.get_entity(item["entity_id"])
        if entity and entity["type"] == ENTITY_TYPES["DOCUMENT"]:
            result.append({
                "id": entity["id"],
                "title": entity["properties"].get("title", "Untitled"),
                "score": item["score"],
                "path": item.get("path", [])
            })
    
    return result

# Process a directory of markdown documentation
docs_dir = "./docs"  # Change to your documentation directory
markdown_files = glob.glob(os.path.join(docs_dir, "**/*.md"), recursive=True)

print(f"Processing {len(markdown_files)} documentation files...")
for file_path in markdown_files:
    doc_entity, sections = process_markdown_file(file_path)
    print(f"Added {doc_entity['properties']['title']} with {len(sections)} sections")

# Connect related documents based on content similarity
print("\nConnecting related documents...")

# Get all document entities
doc_entities = kg.query_entities(entity_type=ENTITY_TYPES["DOCUMENT"])

# Find relationships between documents using vector similarity
for i, doc1 in enumerate(doc_entities):
    doc1_entity = kg.get_entity(doc1["id"])
    if not doc1_entity or "vector" not in doc1_entity:
        continue
        
    # Find similar documents
    similar_docs = kg.vector_search(
        vector=doc1_entity["vector"],
        entity_type=ENTITY_TYPES["DOCUMENT"],
        top_k=6  # +1 because it will find itself
    )
    
    # Connect to related documents (excluding self)
    for sim_doc in similar_docs:
        if sim_doc["entity_id"] == doc1["id"]:
            continue  # Skip self
            
        if sim_doc["score"] > 0.7:  # Only connect if similarity is high enough
            kg.add_relationship(
                from_entity=doc1["id"],
                to_entity=sim_doc["entity_id"],
                relationship_type=RELATIONSHIP_TYPES["RELATED_TO"],
                properties={"similarity": round(sim_doc["score"], 3)}
            )

# Now implement the GraphRAG query functionality
def documentation_rag(query_text, hop_count=1, top_k=5):
    """Perform GraphRAG query on documentation knowledge graph."""
    # Step 1: Convert query to embedding vector
    query_vector = embedding_model.encode(query_text)
    
    # Step 2: Perform GraphRAG search
    results = kg.graph_vector_search(
        query_vector=query_vector.tolist(),
        hop_count=hop_count,
        top_k=top_k
    )
    
    # Step 3: Format results
    formatted_results = []
    for result in results:
        entity = kg.get_entity(result["entity_id"])
        if not entity:
            continue
            
        item = {
            "id": entity["id"],
            "type": entity["type"],
            "title": entity["properties"].get("title", entity["id"]),
            "score": result["score"],
            "distance": result["distance"]
        }
        
        # Add type-specific information
        if entity["type"] == ENTITY_TYPES["DOCUMENT"]:
            item["path"] = entity["properties"].get("path")
            item["word_count"] = entity["properties"].get("word_count")
            
        elif entity["type"] == ENTITY_TYPES["SECTION"]:
            item["content"] = entity["properties"].get("content")
            # Get parent document
            parent_docs = kg.query_related(
                entity_id=entity["id"],
                relationship_type=RELATIONSHIP_TYPES["CONTAINS"],
                direction="incoming"
            )
            if parent_docs:
                parent = kg.get_entity(parent_docs[0]["entity_id"])
                item["document"] = {
                    "id": parent["id"],
                    "title": parent["properties"].get("title")
                }
                
        elif entity["type"] == ENTITY_TYPES["CODE_EXAMPLE"]:
            item["language"] = entity["properties"].get("language")
            item["code"] = entity["properties"].get("code")
            
        # Add path information
        if "path" in result:
            path_info = []
            for i in range(0, len(result["path"]), 2):
                entity_id = result["path"][i]
                rel_type = result["path"][i+1] if i+1 < len(result["path"]) else None
                
                node = kg.get_entity(entity_id)
                node_name = (node["properties"].get("title") or 
                             node["properties"].get("name") or 
                             entity_id) if node else entity_id
                
                path_info.append({"entity": node_name, "relationship": rel_type})
                
            item["path_info"] = path_info
            
        formatted_results.append(item)
    
    return formatted_results

# Example RAG query
print("\n=== GraphRAG Query Example ===")
user_query = "How does content addressing work in IPFS?"
print(f"Query: {user_query}")

results = documentation_rag(user_query, hop_count=2, top_k=5)
print(f"\nFound {len(results)} relevant items:")

for i, result in enumerate(results):
    print(f"\n{i+1}. {result['title']} ({result['type']})")
    print(f"   Score: {result['score']:.2f}, Distance: {result['distance']}")
    
    if result['type'] == ENTITY_TYPES["SECTION"]:
        print(f"   From document: {result.get('document', {}).get('title', 'Unknown')}")
        print(f"   Content snippet: {result.get('content', '')[:150]}...")
        
    elif result['type'] == ENTITY_TYPES["CODE_EXAMPLE"]:
        print(f"   Language: {result.get('language', 'unknown')}")
        print(f"   Code snippet: {result.get('code', '')[:150]}...")
        
    # Show path information if available
    if "path_info" in result and result["distance"] > 0:
        path_str = " → ".join([f"{p['entity']}" for p in result["path_info"]])
        print(f"   Connection path: {path_str}")

# Format for LLM context
def format_results_for_llm(results, max_length=4000):
    """Format GraphRAG results as context for an LLM."""
    context = "Here is relevant information from the documentation:\n\n"
    
    for i, result in enumerate(results):
        section = f"[{i+1}] "
        
        if result['type'] == ENTITY_TYPES["DOCUMENT"]:
            section += f"Document: {result['title']}\n"
            
        elif result['type'] == ENTITY_TYPES["SECTION"]:
            section += f"Section: {result['title']}\n"
            section += f"From document: {result.get('document', {}).get('title', 'Unknown')}\n"
            section += f"Content: {result.get('content', '')}\n"
            
        elif result['type'] == ENTITY_TYPES["CODE_EXAMPLE"]:
            section += f"Code Example ({result.get('language', 'unknown')}):\n"
            section += "```\n"
            section += f"{result.get('code', '')}\n"
            section += "```\n"
            
        elif result['type'] == ENTITY_TYPES["CONCEPT"]:
            section += f"Concept: {result['title']}\n"
            
        # Add connection information for non-direct matches
        if result.get('distance', 0) > 0 and "path_info" in result:
            path_str = " → ".join([f"{p['entity']}" for p in result["path_info"]])
            section += f"Related via: {path_str}\n"
            
        section += "\n"
        
        # Check if adding this section would exceed max length
        if len(context) + len(section) > max_length:
            context += "[Additional relevant information truncated due to length constraints]"
            break
            
        context += section
    
    return context

# Example formatting for LLM
llm_context = format_results_for_llm(results)
print("\n=== Formatted Context for LLM ===")
print(llm_context[:500] + "...")  # Show first 500 chars

# Example LLM prompt template
def create_llm_prompt(query, context):
    """Create a complete prompt for an LLM with GraphRAG context."""
    return f"""You are a technical documentation assistant for IPFS Kit. 
Answer the following question based on the provided context information.
If the information isn't in the context, acknowledge that and provide general information if possible.

Context:
{context}

Question: {query}

Answer:"""

# Final LLM prompt (would be sent to an actual LLM in production)
final_prompt = create_llm_prompt(user_query, llm_context)
print("\n=== Final LLM Prompt ===")
print(final_prompt[:300] + "...")  # Show first 300 chars of prompt
```

This GraphRAG implementation for technical documentation offers several key advantages:

1. **Document Hierarchy Awareness**: Understands the structure of documentation (documents containing sections containing code examples)
2. **Bidirectional Context**: Can find relevant information both through direct semantic similarity and through graph relationships
3. **Path Explanation**: Provides transparent reasoning paths showing how each result connects to the query
4. **Mixed Result Types**: Can return different types of content (documents, sections, code examples) based on relevance
5. **Self-Organizing Knowledge**: Automatically connects related documents based on content similarity

For production use, this system can be integrated with:
- **DocumentGPT interfaces**: Create a documentation chat assistant that answers user questions
- **Developer tools**: Integrate with IDEs to provide context-aware documentation
- **Technical support systems**: Help support personnel quickly locate relevant documentation

### Implementing a GraphRAG System for AI
kg = IPLDGraphDB(ipfs_client)

# Set up an embedding model (e.g., using sentence-transformers)
from sentence_transformers import SentenceTransformer
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize GraphRAG component
rag = GraphRAG(kg, embedding_model)

# Process a user question
user_question = "How does content addressing work with IPLD?"

# Retrieve context from the knowledge graph
context = rag.retrieve(
    query_text=user_question,
    entity_types=["research_paper", "concept", "documentation"],
    top_k=5,
    hop_count=1
)

# Format context for an LLM
formatted_context = rag.format_context_for_llm(context, format_type="text")

# Generate a prompt
prompt = rag.generate_llm_prompt(
    user_query=user_question,
    context=context
)

# Send to LLM (placeholder - replace with actual LLM integration)
llm_response = some_llm_api.generate(prompt)

# Augment response with citations
entity_ids = [entity_id for entity_id in context["entities"]]
citation_info = {}

for entity_id in entity_ids:
    entity = kg.get_entity(entity_id)
    if entity and entity.get("type") == "research_paper":
        citation_info[entity_id] = {
            "title": entity["properties"].get("title", "Unknown"),
            "authors": entity["properties"].get("authors", ["Unknown"]),
            "year": entity["properties"].get("year", "Unknown"),
            "doi": entity["properties"].get("doi", "")
        }

# Format final response with citations
final_response = f"""
{llm_response}

Sources:
"""

for entity_id, citation in citation_info.items():
    authors = ", ".join(citation["authors"])
    final_response += f"- {authors} ({citation['year']}). {citation['title']}. {citation['doi']}\n"

print(final_response)
```

## Future Enhancements

Planned enhancements for the IPLD Knowledge Graph system:

1. **Distributed Collaborative Editing**: Multi-user editing with conflict resolution
2. **Schema Enforcement**: Type checking and validation for entities and relationships
3. **Enhanced Query Language**: Graph-specific query language for complex patterns
4. **Visualization Tools**: Interactive visualization of knowledge graph structures
5. **Federated Queries**: Query across multiple knowledge graphs
6. **Temporal Queries**: Time-based queries and historical graph states
7. **Advanced Vector Index**: Integration with HNSW and other advanced vector indexing methods
8. **Cross-Language Access**: Access the knowledge graph from multiple programming languages
9. **Enhanced LLM Integration**: More sophisticated query generation and parsing
10. **Ontology and Reasoning**: Add support for ontologies and logical inference

## GraphRAG Algorithm Details

The GraphRAG implementation in IPFS Kit provides a sophisticated combination of vector similarity search and graph traversal to enhance retrieval for LLMs:

### Algorithm Implementation

The core GraphRAG algorithm is implemented as follows:

```python
def graph_vector_search(self, query_vector, hop_count=2, top_k=10, path_types=None):
    """Combined graph and vector search (GraphRAG).
    
    Args:
        query_vector: The query embedding vector
        hop_count: Maximum number of hops to explore
        top_k: Number of results to return
        path_types: Optional list of relationship types to follow
        
    Returns:
        List of results with combined scores
    """
    # 1. First perform vector search to find entry points
    vector_results = self.vector_search(query_vector, top_k=top_k)
    
    # 2. Initialize expanded results
    expanded_results = {}
    
    # 3. For each vector result, explore the graph neighborhood
    for result in vector_results:
        entity_id = result["entity_id"]
        similarity_score = result["score"]
        
        # Add initial result to expanded results
        expanded_results[entity_id] = {
            "entity_id": entity_id,
            "score": similarity_score,  # Initial score is just vector similarity
            "path": [entity_id],        # Path starts with just this entity
            "distance": 0,              # No hops yet
            "origin_similarity": similarity_score  # Track original similarity
        }
        
        # 4. Explore neighborhood for each vector search result
        self._explore_neighborhood(
            entity_id=entity_id,
            results=expanded_results,
            max_hops=hop_count,
            current_hop=0,
            origin_score=similarity_score,
            path=[entity_id],
            path_types=path_types
        )
    
    # 5. Sort by score and return top results
    sorted_results = sorted(
        expanded_results.values(),
        key=lambda x: x["score"],
        reverse=True
    )
    
    return sorted_results[:top_k]
```

The neighborhood exploration recursively traverses the graph:

```python
def _explore_neighborhood(self, entity_id, results, max_hops, current_hop, origin_score, path, path_types=None):
    """Recursively explore entity neighborhood for graph search."""
    if current_hop >= max_hops:
        return
        
    # Get related entities
    related = self.query_related(entity_id, direction="both")
    
    for rel in related:
        neighbor_id = rel["entity_id"]
        rel_type = rel["relationship_type"]
        
        # Skip if already in path (avoid cycles) or relationship type filtered out
        if neighbor_id in path or (path_types and rel_type not in path_types):
            continue
            
        # Calculate score decay based on distance
        # We use exponential decay based on hop distance
        hop_penalty = 0.7 ** (current_hop + 1)  # Score decays by factor for each hop
        neighbor_score = origin_score * hop_penalty
        
        new_path = path + [rel_type, neighbor_id]
        
        # Add or update in results
        if neighbor_id not in results or neighbor_score > results[neighbor_id]["score"]:
            results[neighbor_id] = {
                "entity_id": neighbor_id,
                "score": neighbor_score,
                "path": new_path,
                "distance": current_hop + 1,
                "origin_similarity": origin_score
            }
                
        # Continue exploration
        self._explore_neighborhood(
            neighbor_id,
            results,
            max_hops,
            current_hop + 1,
            origin_score,
            new_path,
            path_types
        )
```

### Relevance Scoring Formula

The relevance score for each entity combines:

1. **Vector similarity score**: Semantic relevance from embedding comparison
2. **Graph distance**: Number of hops from an entry point
3. **Path weighting**: Different relationship types can have different weights

The scoring formula uses exponential decay:

```
final_score = vector_similarity * (decay_factor ^ distance)
```

Where:
- `vector_similarity` is the cosine similarity between query and entity vectors
- `decay_factor` is typically 0.7 (configurable)
- `distance` is the number of hops from the entry point

### GraphRAG vs. Traditional RAG

GraphRAG offers several advantages over traditional vector-only RAG systems:

| Feature | Traditional RAG | GraphRAG |
|---------|----------------|----------|
| Context discovery | Vector similarity only | Vector + graph traversal |
| Knowledge structure | Flat vector space | Explicit relationships |
| Reasoning capability | Limited to pre-encoded vectors | Can follow logical paths |
| Context scope | Direct matches | Direct + related entities |
| Information retrieval | Limited to indexed chunks | Can discover related information |
| Explanation capability | Black box similarity | Transparent relationship paths |

### Optimizations

The IPFS Kit implementation includes several optimizations:

1. **Memoization**: Caching of intermediate results to avoid redundant traversals
2. **Prioritized Exploration**: More promising paths are explored first based on score
3. **Early Stopping**: Traversal stops when the score falls below a threshold
4. **Cycle Detection**: Prevents infinite loops in graph traversal
5. **Parallel Processing**: Optional parallelized graph exploration for large graphs
6. **Batched Vector Retrieval**: Efficient batch processing of vector similarity

### Example GraphRAG Result

The GraphRAG search returns results with detailed path information:

```json
[
    {
        "entity_id": "doc123",
        "score": 0.92,
        "path": ["doc123"],
        "distance": 0,
        "origin_similarity": 0.92
    },
    {
        "entity_id": "topic456",
        "score": 0.68,
        "path": ["doc123", "DISCUSSES", "topic456"],
        "distance": 1,
        "origin_similarity": 0.92
    },
    {
        "entity_id": "doc789",
        "score": 0.45,
        "path": ["doc123", "DISCUSSES", "topic456", "APPEARS_IN", "doc789"],
        "distance": 2,
        "origin_similarity": 0.92
    }
]
```

This structured result provides:
- Transparent reasoning paths showing how entities connect
- Both direct matches and contextually related information
- Ability to explain why each result was included
- Full provenance for LLM context generation
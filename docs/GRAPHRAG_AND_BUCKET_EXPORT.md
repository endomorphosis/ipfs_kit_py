# GraphRAG Improvements & Bucket Metadata Export/Import

This document provides comprehensive documentation for the improved GraphRAG system and the new bucket metadata export/import functionality.

## Table of Contents

1. [GraphRAG Improvements](#graphrag-improvements)
2. [Bucket Metadata Export/Import](#bucket-metadata-exportimport)
3. [Usage Examples](#usage-examples)
4. [API Reference](#api-reference)

---

## GraphRAG Improvements

### Overview

The GraphRAG (Graph-based Retrieval Augmented Generation) system has been significantly enhanced with advanced features for content indexing, search, and knowledge graph management.

### New Features

#### 1. Embedding Caching

**Problem**: Generating embeddings is computationally expensive and slow for repeated content.

**Solution**: Persistent embedding cache using pickle format, providing 100x speedup for repeated content.

```python
from ipfs_kit_py.graphrag import GraphRAGSearchEngine

# Enable caching (default: True)
engine = GraphRAGSearchEngine(enable_caching=True)

# First indexing generates embedding
await engine.index_content("QmTest", "/file", "content")  # Slow

# Repeated indexing uses cache
await engine.index_content("QmTest2", "/file2", "content")  # Fast!

# Check cache statistics
stats = engine.get_stats()
print(f"Cache hit rate: {stats['stats']['cache']['hit_rate']:.2%}")
```

#### 2. Advanced Entity Extraction with spaCy

**Enhancement**: Uses spaCy NLP when available for better entity extraction, with regex fallback.

**Extracted Entities**:
- **CIDs**: IPFS content identifiers
- **Paths**: File system paths
- **Keywords**: Important terms
- **Persons**: People names (with spaCy)
- **Organizations**: Companies, institutions (with spaCy)
- **Locations**: Places, countries (with spaCy)

```python
content = """
John Smith from Microsoft visited the IPFS project at
/home/documents/proposal.pdf referenced as QmTest123.
"""

entities = await engine.extract_entities(content)

print(entities["entities"])
# {
#   "cids": ["QmTest123"],
#   "paths": ["/home/documents/proposal.pdf"],
#   "persons": ["John Smith"],
#   "organizations": ["Microsoft", "IPFS"],
#   "keywords": [...],
#   "locations": []
# }
```

**Installation** (optional):
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

#### 3. Bulk Indexing Operations

**Problem**: Indexing large datasets one-by-one is inefficient.

**Solution**: Bulk indexing API that batches database operations and optimizes performance.

```python
# Prepare batch of items
items = [
    {"cid": "Qm1", "path": "/doc1.txt", "content": "Document 1 content..."},
    {"cid": "Qm2", "path": "/doc2.txt", "content": "Document 2 content..."},
    {"cid": "Qm3", "path": "/doc3.txt", "content": "Document 3 content..."},
    # ... hundreds or thousands more
]

# Bulk index
result = await engine.bulk_index_content(items)

print(f"Indexed {result['indexed_count']} out of {result['total_items']} items")
print(f"Errors: {len(result['errors'])}")
```

#### 4. Version Tracking

**Enhancement**: Automatic versioning of content updates with history preservation.

**Features**:
- Version numbers tracked in `content_index` table
- Old versions saved to `content_versions` table
- Query version history

```python
# First index
await engine.index_content("Qm1", "/doc", "Version 1 content")
# Creates version 1

# Update content
await engine.index_content("Qm1", "/doc", "Version 2 content")
# Creates version 2, saves version 1 to history

# Check version stats
stats = engine.get_stats()
print(f"Average version: {stats['stats']['version_stats']['avg_version']}")
print(f"Max version: {stats['stats']['version_stats']['max_version']}")
```

#### 5. Relationship Confidence Scores

**Enhancement**: Relationships now include confidence scores (0.0 to 1.0).

```python
# Add relationship with confidence
await engine.add_relationship(
    source_cid="Qm1",
    target_cid="Qm2",
    relationship_type="similar_to",
    confidence=0.85  # 85% confidence
)

# Check relationship statistics
stats = engine.get_stats()
print(stats['stats']['avg_confidence_by_type'])
# {"references": 1.0, "similar_to": 0.85}
```

#### 6. Automatic Relationship Inference

**Feature**: Automatically discover relationships based on content similarity.

**Algorithm**:
1. Calculate embeddings for all content
2. Compute cosine similarity between all pairs
3. Create "similar_to" relationships above threshold
4. Store with similarity score as confidence

```python
# Index content
await engine.index_content("Qm1", "/ml1", "machine learning deep learning")
await engine.index_content("Qm2", "/ml2", "neural networks deep learning")
await engine.index_content("Qm3", "/web", "web development JavaScript")

# Infer relationships
result = await engine.infer_relationships(threshold=0.7)

print(f"Inferred {result['inferred_count']} new relationships")
# Qm1 and Qm2 will be linked (similar content)
# Qm3 won't be linked (different content)
```

#### 7. Graph Analytics

**Feature**: Comprehensive graph analysis including centrality measures and community detection.

**Available Metrics**:
- **Degree Centrality**: Most connected nodes
- **Betweenness Centrality**: Bridge nodes connecting communities
- **Communities**: Detected communities using greedy modularity
- **Strongly Connected Components**: Mutually reachable node groups

```python
# Perform analysis
analysis = engine.analyze_graph()

print(f"Total nodes: {analysis['stats']['nodes']}")
print(f"Total edges: {analysis['stats']['edges']}")
print(f"Graph density: {analysis['stats']['density']:.3f}")

# Top nodes by degree
for node in analysis['top_nodes_by_degree'][:5]:
    print(f"  {node['cid']}: {node['centrality']:.3f}")

# Communities
print(f"Found {analysis['communities']['count']} communities")
print(f"Largest community: {analysis['communities']['largest_community']} nodes")
```

#### 8. Improved Hybrid Search

**Enhancement**: True hybrid search combining multiple methods with configurable weights.

**Methods Combined**:
- **Vector Search**: Semantic similarity using embeddings
- **Graph Search**: Knowledge graph traversal
- **Text Search**: SQL-based keyword matching

```python
# Hybrid search with custom weights
results = await engine.hybrid_search(
    query="machine learning tutorial",
    limit=10,
    weights={
        'vector': 0.5,  # 50% weight on semantic similarity
        'graph': 0.3,   # 30% weight on graph relationships
        'text': 0.2     # 20% weight on keyword matching
    }
)

for result in results['results']:
    print(f"{result['cid']}: score={result['score']:.3f}, sources={result['sources']}")
    # Example: QmABC: score=0.827, sources=['vector', 'graph', 'text']
```

#### 9. Comprehensive Statistics

**Enhancement**: Extended statistics including cache metrics, relationship analytics, and version tracking.

```python
stats = engine.get_stats()

# Document statistics
print(f"Total documents: {stats['stats']['document_count']}")
print(f"Total relationships: {stats['stats']['relationship_count']}")

# Relationship types
for rel_type, count in stats['stats']['relationship_types'].items():
    avg_conf = stats['stats']['avg_confidence_by_type'][rel_type]
    print(f"  {rel_type}: {count} relationships, avg confidence: {avg_conf:.2f}")

# Cache statistics
cache = stats['stats']['cache']
print(f"Cache enabled: {cache['enabled']}")
print(f"Cache size: {cache['size']} embeddings")
print(f"Cache hit rate: {cache['hit_rate']:.2%}")

# Version statistics
print(f"Average version: {stats['stats']['version_stats']['avg_version']:.1f}")
print(f"Maximum version: {stats['stats']['version_stats']['max_version']}")

# Graph statistics
print(f"Graph nodes: {stats['stats']['knowledge_graph']['nodes']}")
print(f"Graph edges: {stats['stats']['knowledge_graph']['edges']}")
print(f"Graph density: {stats['stats']['knowledge_graph']['density']:.3f}")
```

---

## Bucket Metadata Export/Import

### Overview

The bucket metadata export/import system allows you to share bucket configurations and data via IPFS CIDs, enabling:
- **Sharing**: Give someone a CID to replicate your bucket
- **Backup**: Export bucket metadata for disaster recovery
- **Migration**: Move buckets between systems
- **Collaboration**: Share bucket structures with team members

### Architecture

**Metadata Format**:
```json
{
  "version": "1.0",
  "exported_at": 1234567890.0,
  "bucket_info": {
    "name": "my-bucket",
    "type": "general",
    "vfs_structure": "unixfs",
    "created_at": "2024-01-01T00:00:00Z",
    "root_cid": "QmRootCID",
    "metadata": {}
  },
  "files": {
    "file_count": 100,
    "total_size": 1048576,
    "files": [
      {"path": "doc1.txt", "size": 1024, "modified": 1234567890.0},
      ...
    ]
  },
  "knowledge_graph": {...},
  "vector_index": {...},
  "statistics": {...}
}
```

### Exporting Buckets

#### Basic Export

```python
from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter

# Initialize exporter with IPFS client
exporter = BucketMetadataExporter(ipfs_client=ipfs)

# Export bucket metadata
result = await exporter.export_bucket_metadata(
    bucket=my_bucket,
    include_files=True,
    include_knowledge_graph=True,
    include_vector_index=True,
    format="json"  # or "cbor"
)

if result["success"]:
    print(f"Metadata CID: {result['metadata_cid']}")
    print(f"Export size: {result['size_bytes']} bytes")
    print(f"Format: {result['format']}")
    
    # Share this CID with others!
    share_cid = result['metadata_cid']
```

#### Export Options

```python
# Minimal export (just configuration)
result = await exporter.export_bucket_metadata(
    bucket=my_bucket,
    include_files=False,
    include_knowledge_graph=False,
    include_vector_index=False
)

# Full export with CBOR format (smaller size)
result = await exporter.export_bucket_metadata(
    bucket=my_bucket,
    include_files=True,
    include_knowledge_graph=True,
    include_vector_index=True,
    format="cbor"  # Requires: pip install cbor2
)
```

#### Export Without IPFS Client

If no IPFS client is available, metadata is saved to a local file:

```python
exporter = BucketMetadataExporter()  # No IPFS client

result = await exporter.export_bucket_metadata(my_bucket)

print(f"Saved to: {result['export_path']}")
# You can manually upload this file to IPFS later
```

### Importing Buckets

#### Basic Import

```python
from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter

# Initialize importer
importer = BucketMetadataImporter(
    ipfs_client=ipfs,
    bucket_manager=bucket_mgr
)

# Import bucket from CID
result = await importer.import_bucket_metadata(
    metadata_cid="QmMetadataCID",
    new_bucket_name="imported-bucket",  # Optional: rename on import
    fetch_files=False  # Don't fetch actual files yet
)

if result["success"]:
    print(f"Imported bucket: {result['bucket_name']}")
    print(f"Imported {result['imported_files']} file references")
```

#### Import with File Fetching

```python
# Import and fetch actual files from IPFS
result = await importer.import_bucket_metadata(
    metadata_cid="QmMetadataCID",
    new_bucket_name="imported-bucket",
    fetch_files=True  # Fetch files from IPFS
)

print(f"Files fetched: {result['files_fetched']}")
```

#### Import Validation

The importer automatically validates metadata structure:

```python
# Invalid metadata will be rejected
result = await importer.import_bucket_metadata("QmInvalidCID")

if not result["success"]:
    print(f"Import failed: {result['error']}")
    # Example: "Invalid metadata structure"
```

### Use Cases

#### 1. Sharing Research Data

```python
# Researcher A exports bucket
exporter = BucketMetadataExporter(ipfs_client=ipfs_a)
result = await exporter.export_bucket_metadata(research_bucket)
metadata_cid = result['metadata_cid']

# Share CID via email, paper, or chat
print(f"Share this CID: {metadata_cid}")

# Researcher B imports bucket
importer = BucketMetadataImporter(ipfs_client=ipfs_b, bucket_manager=mgr_b)
await importer.import_bucket_metadata(
    metadata_cid=metadata_cid,
    new_bucket_name="research-data",
    fetch_files=True
)
```

#### 2. Backup and Recovery

```python
# Regular backup
async def backup_all_buckets():
    exporter = BucketMetadataExporter(ipfs_client=ipfs)
    backup_cids = {}
    
    for bucket_name, bucket in bucket_manager.buckets.items():
        result = await exporter.export_bucket_metadata(bucket)
        backup_cids[bucket_name] = result['metadata_cid']
    
    # Save CIDs to safe location
    with open('bucket_backups.json', 'w') as f:
        json.dump(backup_cids, f)

# Recovery
async def restore_from_backup():
    with open('bucket_backups.json', 'r') as f:
        backup_cids = json.load(f)
    
    importer = BucketMetadataImporter(ipfs_client=ipfs, bucket_manager=mgr)
    
    for bucket_name, cid in backup_cids.items():
        await importer.import_bucket_metadata(
            metadata_cid=cid,
            new_bucket_name=bucket_name,
            fetch_files=True
        )
```

#### 3. Collaborative Projects

```python
# Team lead creates project bucket
project_bucket = await bucket_manager.create_bucket("project-x")
# ... populate with files ...

# Export for team
exporter = BucketMetadataExporter(ipfs_client=ipfs)
result = await exporter.export_bucket_metadata(project_bucket)

# Share CID with team via Slack/Email
team_metadata_cid = result['metadata_cid']

# Team members import
importer = BucketMetadataImporter(ipfs_client=their_ipfs, bucket_manager=their_mgr)
await importer.import_bucket_metadata(
    metadata_cid=team_metadata_cid,
    new_bucket_name="project-x-local"
)
```

---

## API Reference

### GraphRAGSearchEngine

#### Constructor

```python
GraphRAGSearchEngine(
    workspace_dir: Optional[str] = None,
    enable_caching: bool = True
)
```

**Parameters**:
- `workspace_dir`: Directory for database and cache (default: `~/.ipfs_mcp_search`)
- `enable_caching`: Enable embedding cache (default: `True`)

#### Methods

##### `async index_content(cid, path, content, **kwargs)`

Index content with versioning and caching.

**Returns**: `{"success": bool, "cid": str, "version": int}`

##### `async bulk_index_content(items)`

Bulk index multiple content items.

**Parameters**:
- `items`: List of dicts with `cid`, `path`, `content` keys

**Returns**: `{"success": bool, "indexed_count": int, "errors": list}`

##### `async extract_entities(content)`

Extract entities from content using NLP.

**Returns**: `{"success": bool, "entities": dict}`

##### `async add_relationship(source_cid, target_cid, relationship_type, confidence)`

Add relationship with confidence score.

**Returns**: `{"success": bool, "relationship": dict}`

##### `async infer_relationships(threshold)`

Infer relationships based on similarity.

**Parameters**:
- `threshold`: Similarity threshold 0.0-1.0 (default: 0.7)

**Returns**: `{"success": bool, "inferred_count": int}`

##### `analyze_graph()`

Perform graph analytics.

**Returns**: `{"success": bool, "stats": dict, "top_nodes_by_degree": list, ...}`

##### `async hybrid_search(query, limit, weights)`

Multi-method hybrid search.

**Parameters**:
- `query`: Search query string
- `limit`: Maximum results (default: 10)
- `weights`: Dict with `vector`, `graph`, `text` weights

**Returns**: `{"success": bool, "results": list}`

##### `get_stats()`

Get comprehensive statistics.

**Returns**: `{"success": bool, "stats": dict}`

### BucketMetadataExporter

#### Constructor

```python
BucketMetadataExporter(ipfs_client=None)
```

#### Methods

##### `async export_bucket_metadata(bucket, include_files, include_knowledge_graph, include_vector_index, format)`

Export bucket metadata.

**Parameters**:
- `bucket`: BucketVFS instance
- `include_files`: Include file manifest (default: True)
- `include_knowledge_graph`: Include KG data (default: True)
- `include_vector_index`: Include vector index (default: True)
- `format`: "json" or "cbor" (default: "json")

**Returns**: `{"success": bool, "metadata_cid": str, "size_bytes": int, ...}`

### BucketMetadataImporter

#### Constructor

```python
BucketMetadataImporter(ipfs_client=None, bucket_manager=None)
```

#### Methods

##### `async import_bucket_metadata(metadata_cid, new_bucket_name, fetch_files)`

Import bucket from metadata CID.

**Parameters**:
- `metadata_cid`: IPFS CID of metadata
- `new_bucket_name`: Optional new name (default: original name)
- `fetch_files`: Fetch actual files (default: False)

**Returns**: `{"success": bool, "bucket_name": str, "imported_files": int, ...}`

---

## Dependencies

### Required
- `sqlite3` (built-in)
- `networkx` (for graph operations)

### Optional
- `sentence-transformers` (for embeddings)
- `scikit-learn` (for similarity calculations)
- `spacy` (for advanced entity extraction)
- `rdflib` (for SPARQL queries)
- `cbor2` (for CBOR format support)

### Installation

```bash
# Core dependencies
pip install networkx

# Optional for full features
pip install sentence-transformers scikit-learn spacy rdflib cbor2

# Download spaCy model
python -m spacy download en_core_web_sm
```

---

## Performance Tips

1. **Enable Caching**: Always enable embedding cache for repeated content
2. **Bulk Operations**: Use `bulk_index_content()` for large datasets
3. **Periodic Inference**: Run `infer_relationships()` after bulk indexing
4. **CBOR Format**: Use CBOR for smaller export sizes
5. **Selective Exports**: Only include necessary components in exports
6. **Database Indexes**: Built-in SQL indexes optimize queries

---

## Troubleshooting

### Slow Indexing

**Problem**: Indexing is very slow.

**Solutions**:
1. Enable caching: `GraphRAGSearchEngine(enable_caching=True)`
2. Use bulk operations: `bulk_index_content(items)`
3. Install sentence-transformers model locally

### Missing Entities

**Problem**: Entity extraction missing persons/organizations.

**Solutions**:
1. Install spaCy: `pip install spacy`
2. Download model: `python -m spacy download en_core_web_sm`
3. Verify model loads: Check logs for spaCy initialization

### Import Fails

**Problem**: Bucket import fails with validation error.

**Solutions**:
1. Check metadata CID is correct
2. Verify IPFS client connection
3. Check metadata format version compatibility
4. Ensure bucket_manager is initialized

---

## License

AGPL-3.0 - See LICENSE file for details.

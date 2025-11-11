# Enhanced MCP Server with GraphRAG Integration

## Overview

The enhanced MCP server now provides advanced search and knowledge management capabilities by integrating GraphRAG (Graph-based Retrieval Augmented Generation) with IPFS VFS/MFS operations. This creates a powerful system for content-addressed data with intelligent search and discovery.

## New Capabilities

### 🔍 Advanced Search Features

1. **Text Search** - Traditional full-text search with relevance scoring
2. **Graph Search** - Knowledge graph traversal for semantic connections
3. **Vector Search** - Semantic similarity using embeddings (optional)
4. **SPARQL Queries** - RDF-based structured queries
5. **Hybrid Search** - Combines multiple search methods for best results

### 📁 Auto-Indexing VFS Operations

All VFS/MFS operations now automatically index content for search:

- **Content Writing** - Files written to MFS are automatically indexed
- **Content Reading** - Accessed content is indexed if not already present
- **Metadata Extraction** - Automatic entity and relationship extraction
- **Knowledge Graph Building** - Entities and relationships form a searchable graph

### 🧠 Knowledge Management

- **Entity Recognition** - Automatic extraction of people, places, organizations
- **Relationship Mapping** - Semantic connections between entities
- **RDF Triple Store** - Structured knowledge representation
- **Graph Analytics** - Centrality and importance scoring

## New MCP Tools

### Search Tools

1. **`search_text`** - Full-text search across indexed content
   ```json
   {
     "query": "search terms",
     "limit": 10,
     "content_types": ["markdown", "text"]
   }
   ```

2. **`search_graph`** - Knowledge graph traversal search
   ```json
   {
     "query": "concept to explore",
     "max_depth": 2,
     "min_score": 0.1
   }
   ```

3. **`search_vector`** - Semantic similarity search (requires sentence-transformers)
   ```json
   {
     "query": "semantic query",
     "limit": 10,
     "threshold": 0.7
   }
   ```

4. **`search_sparql`** - SPARQL queries on RDF data
   ```json
   {
     "query": "SELECT ?subject ?predicate ?object WHERE { ?subject ?predicate ?object }"
   }
   ```

5. **`search_hybrid`** - Multi-method search combination
   ```json
   {
     "query": "comprehensive search",
     "search_types": ["text", "graph", "vector"],
     "limit": 10
   }
   ```

6. **`search_index_content`** - Manually index content
   ```json
   {
     "cid": "content_id",
     "path": "/path/to/content",
     "content": "text content",
     "content_type": "markdown",
     "metadata": {"key": "value"}
   }
   ```

7. **`search_stats`** - Get search index statistics
   ```json
   {}
   ```

## Usage Examples

### Basic Content Indexing

```python
# Index content with metadata
result = await call_tool("search_index_content", {
    "cid": "bafybei...",
    "path": "/docs/whitepaper.md",
    "content": "IPFS is a distributed file system...",
    "content_type": "markdown",
    "metadata": {
        "type": "documentation",
        "topic": "ipfs",
        "author": "Protocol Labs"
    }
})
```

### Multi-Method Search

```python
# Hybrid search combining text and graph methods
result = await call_tool("search_hybrid", {
    "query": "distributed consensus algorithms",
    "search_types": ["text", "graph"],
    "limit": 5
})

# Results include individual method results plus combined ranking
```

### VFS Operations with Auto-Indexing

```python
# Write to MFS - automatically indexed
await call_tool("ipfs_files_write", {
    "path": "/research/new_paper.md",
    "content": "# Blockchain Consensus\n\nThis paper discusses...",
    "create": True
})

# Content is now searchable
search_result = await call_tool("search_text", {
    "query": "blockchain consensus"
})
```

### Knowledge Graph Exploration

```python
# Search through entity relationships
result = await call_tool("search_graph", {
    "query": "IPFS",
    "max_depth": 3
})

# Returns connected concepts and their relationships
```

### SPARQL Queries

```python
# Query the RDF knowledge base
result = await call_tool("search_sparql", {
    "query": """
        SELECT ?entity ?type ?description WHERE {
            ?entity rdf:type ?type .
            ?entity rdfs:label ?description .
            FILTER(regex(?description, "distributed", "i"))
        }
    """
})
```

## Configuration

### Dependencies

**Required:**
- `numpy` - Numerical operations
- `networkx` - Graph algorithms
- `rdflib` - RDF/SPARQL support

**Optional (for vector search):**
- `sentence-transformers` - Semantic embeddings
- `scikit-learn` - ML utilities

### Database Schema

The system uses SQLite with three main tables:

1. **content_index** - Stores indexed content and metadata
2. **content_relationships** - Entity relationships 
3. **entities** - Extracted named entities

### Performance Considerations

- **Indexing**: Content is indexed on first access/write
- **Memory**: Knowledge graphs kept in memory for fast traversal
- **Storage**: SQLite database grows with indexed content
- **Search**: Hybrid search provides best accuracy but higher latency

## Integration with Existing IPFS Tools

All existing IPFS tools continue to work unchanged. The enhancement adds:

1. **Transparent Indexing** - Content accessed via VFS/MFS tools is automatically indexed
2. **Metadata Preservation** - IPFS metadata is preserved and enhanced
3. **CID Tracking** - Content addressable identifiers are maintained
4. **Backward Compatibility** - All existing functionality remains intact

## Monitoring and Analytics

Use `search_stats` to monitor:

- Total indexed content count
- Available search capabilities  
- Knowledge graph size (nodes/edges)
- RDF triple count
- Entity type distribution
- Content type breakdown

## Troubleshooting

### Vector Search Unavailable
If vector search shows as unavailable:
```bash
pip install sentence-transformers
```

### Graph Search Slow
For large knowledge graphs, consider:
- Reducing `max_depth` in graph searches
- Using more specific queries
- Implementing graph pruning

### Database Size Growth
Monitor database size with `search_stats`. Consider:
- Periodic content cleanup
- Selective indexing based on content type
- Database optimization/reindexing

## Advanced Features

### Custom Entity Recognition
The system can be extended with custom entity recognition patterns by modifying the `GraphRAGSearchEngine._extract_entities()` method.

### Search Result Ranking
Hybrid search combines results using:
- Relevance scores from text search
- Importance scores from graph centrality  
- Similarity scores from vector search
- Weighted combination based on search type performance

### Knowledge Graph Algorithms
The system uses NetworkX for:
- PageRank centrality for entity importance
- Shortest path algorithms for relationship discovery
- Community detection for topic clustering
- Graph traversal for multi-hop reasoning

## Future Enhancements

Planned improvements include:
- **Temporal Indexing** - Time-based content versioning
- **Multi-Language Support** - Polyglot content handling
- **Distributed Search** - Federated search across IPFS nodes
- **Machine Learning Integration** - Automated content classification
- **Real-time Updates** - Live index updates as content changes

---

*Enhanced MCP Server v2.3.0 with GraphRAG Integration*  
*Total Tools: 57 (including 7 new search tools)*

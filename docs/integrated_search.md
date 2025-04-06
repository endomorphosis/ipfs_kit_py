# Integrated Search: Arrow Metadata Index with GraphRAG

This document outlines the integration between the Arrow Metadata Index and the GraphRAG system in ipfs_kit_py, providing a powerful hybrid search capability that combines the strengths of both components.

## Overview

The integration creates a unified search interface that leverages:

1. **Arrow Metadata Index**: Efficient columnar storage and filtering of content metadata
2. **GraphRAG System**: Vector similarity search and graph traversal for semantic relationships

By combining these capabilities, we enable sophisticated search patterns that can filter by metadata before performing semantic search, or enhance vector search results with rich metadata context.

## Key Components

### MetadataEnhancedGraphRAG

The main integration class that combines both systems:

```python
class MetadataEnhancedGraphRAG:
    """GraphRAG system enhanced with Arrow metadata index capabilities.
    
    This class integrates the Arrow metadata index with the IPLD Knowledge Graph
    to provide a unified search experience that combines the strengths of both
    systems: efficient metadata filtering and vector similarity search.
    """
    
    def __init__(self, 
                 ipfs_client, 
                 graph_db=None,
                 metadata_index=None):
        """Initialize the enhanced GraphRAG system.
        
        Args:
            ipfs_client: The IPFS client instance
            graph_db: Optional existing IPLD Knowledge Graph instance
            metadata_index: Optional existing Arrow metadata index instance
        """
        self.ipfs = ipfs_client
        
        # Initialize or use provided components
        self.graph_db = graph_db or IPLDGraphDB(ipfs_client)
        
        if metadata_index is not None:
            self.metadata_index = metadata_index
        elif hasattr(ipfs_client, "metadata_index") and ipfs_client.metadata_index is not None:
            self.metadata_index = ipfs_client.metadata_index
        else:
            # Create a new metadata index if none exists
            self.metadata_index = IPFSArrowIndex(role=ipfs_client.role)
    
    def hybrid_search(self, 
                     query_text=None, 
                     query_vector=None,
                     metadata_filters=None, 
                     entity_types=None,
                     hop_count=1,
                     top_k=10):
        """Perform a hybrid search combining metadata filtering and vector similarity.
        
        This method supports multiple search strategies:
        1. Metadata-first: Filter content by metadata, then perform vector search
        2. Vector-first: Perform vector search, then filter by metadata
        3. Pure hybrid: Execute both searches and merge results
        
        Args:
            query_text: Text query (will be converted to vector if query_vector not provided)
            query_vector: Vector representation for similarity search
            metadata_filters: List of filters for Arrow index in format [(field, op, value),...]
            entity_types: List of entity types to include in results
            hop_count: Number of graph traversal hops for related entities
            top_k: Maximum number of results to return
            
        Returns:
            List of search results with combined scores
        """
        # Strategy determination based on inputs
        if metadata_filters and not (query_text or query_vector):
            # Metadata-only search
            return self._metadata_only_search(metadata_filters, top_k)
            
        elif (query_text or query_vector) and not metadata_filters:
            # Vector-only search
            return self._vector_only_search(query_text, query_vector, entity_types, hop_count, top_k)
            
        else:
            # Hybrid search combining both approaches
            return self._combined_search(query_text, query_vector, metadata_filters, entity_types, hop_count, top_k)
    
    def _metadata_only_search(self, metadata_filters, top_k):
        """Execute a search using only metadata filters."""
        # Query the Arrow index with filters
        filtered_table = self.metadata_index.query(metadata_filters)
        
        # Convert to result format
        results = []
        for row in filtered_table.to_pylist()[:top_k]:
            # Check if this entity exists in the knowledge graph
            entity_id = row.get("cid")
            entity = self.graph_db.get_entity(entity_id)
            
            result = {
                "id": entity_id,
                "score": 1.0,  # No relevance score for metadata-only search
                "metadata": row,
                "properties": entity["properties"] if entity else {},
                "source": "metadata"
            }
            results.append(result)
            
        return results
    
    def _vector_only_search(self, query_text, query_vector, entity_types, hop_count, top_k):
        """Execute a search using only vector similarity."""
        # Convert text to vector if needed
        if query_text and not query_vector:
            query_vector = self.graph_db.generate_embedding(query_text)
            
        # Perform graph vector search
        results = self.graph_db.graph_vector_search(
            query_vector=query_vector,
            hop_count=hop_count,
            top_k=top_k
        )
        
        # Filter by entity type if specified
        if entity_types:
            filtered_results = []
            for result in results:
                entity = self.graph_db.get_entity(result["entity_id"])
                if entity and entity.get("properties", {}).get("type") in entity_types:
                    filtered_results.append(result)
            results = filtered_results[:top_k]
            
        # Enhance with metadata if available
        enhanced_results = []
        for result in results:
            entity_id = result["entity_id"]
            metadata = self._get_metadata_for_entity(entity_id)
            
            enhanced_result = {
                "id": entity_id,
                "score": result["score"],
                "metadata": metadata if metadata else {},
                "properties": self.graph_db.get_entity(entity_id)["properties"],
                "path": result.get("path", []),
                "distance": result.get("distance", 0),
                "source": "vector"
            }
            enhanced_results.append(enhanced_result)
            
        return enhanced_results
    
    def _combined_search(self, query_text, query_vector, metadata_filters, entity_types, hop_count, top_k):
        """Execute a hybrid search combining metadata filtering and vector similarity."""
        # Strategy: Filter by metadata first, then rank by vector similarity
        
        # 1. Get candidate set from metadata filtering
        filtered_table = self.metadata_index.query(metadata_filters)
        candidate_cids = [row["cid"] for row in filtered_table.to_pylist()]
        
        # Short circuit if no candidates match metadata filters
        if not candidate_cids:
            return []
            
        # 2. Convert text to vector if needed
        if query_text and not query_vector:
            query_vector = self.graph_db.generate_embedding(query_text)
            
        # 3. For each candidate, compute vector similarity and add to results
        results = []
        for cid in candidate_cids:
            # Check if entity exists in graph
            entity = self.graph_db.get_entity(cid)
            if not entity:
                continue
                
            # Check entity type filter
            if entity_types and entity.get("properties", {}).get("type") not in entity_types:
                continue
                
            # Get vector and compute similarity
            vector = entity.get("vector")
            if vector is not None:
                similarity = self.graph_db.compute_similarity(query_vector, vector)
                
                # Find related entities through graph traversal
                related_entities = self.graph_db.find_related_entities(
                    cid, max_hops=hop_count, include_properties=True
                )
                
                # Get metadata for this entity
                metadata = self._get_metadata_for_entity(cid)
                
                results.append({
                    "id": cid,
                    "score": similarity,
                    "metadata": metadata if metadata else {},
                    "properties": entity["properties"],
                    "related_entities": related_entities,
                    "source": "combined"
                })
                
        # Sort by similarity score and return top results
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        return sorted_results[:top_k]
    
    def _get_metadata_for_entity(self, entity_id):
        """Retrieve metadata for an entity from the Arrow index."""
        try:
            # Check if the entity exists in the metadata index
            metadata_record = self.metadata_index.get_by_cid(entity_id)
            return metadata_record
        except Exception:
            return None
    
    def index_entity(self, 
                    entity_id, 
                    properties, 
                    vector=None, 
                    relationships=None, 
                    metadata=None):
        """Index an entity in both the knowledge graph and metadata index.
        
        This method ensures that entities are properly indexed in both systems,
        maintaining consistency between the knowledge graph and metadata index.
        
        Args:
            entity_id: Unique identifier for the entity
            properties: Dictionary of entity properties
            vector: Optional embedding vector for similarity search
            relationships: Optional list of relationships to other entities
            metadata: Optional additional metadata for the Arrow index
        
        Returns:
            Dictionary with indexing results for both systems
        """
        result = {
            "success": False,
            "graph_result": None,
            "metadata_result": None
        }
        
        # 1. Add to knowledge graph
        graph_result = self.graph_db.add_entity(
            entity_id=entity_id,
            properties=properties,
            vector=vector
        )
        result["graph_result"] = graph_result
        
        # 2. Add relationships if provided
        if relationships:
            for rel in relationships:
                self.graph_db.add_relationship(
                    from_entity=entity_id,
                    to_entity=rel["target"],
                    relationship_type=rel["type"],
                    properties=rel.get("properties", {})
                )
        
        # 3. Prepare metadata record
        if metadata is None:
            metadata = {}
            
        # Extract basic metadata from properties
        metadata_record = {
            "cid": entity_id,
            "size_bytes": metadata.get("size_bytes", 0),
            "mime_type": metadata.get("mime_type", "application/json"),
            "added_timestamp": metadata.get("added_timestamp", int(time.time() * 1000)),
            "tags": metadata.get("tags", []) + [properties.get("type", "entity")],
            "properties": {}
        }
        
        # Add embedding metadata if vector is provided
        if vector is not None:
            metadata_record["embedding_available"] = True
            metadata_record["embedding_dimensions"] = len(vector)
            metadata_record["embedding_type"] = "float32"
        
        # 4. Add to metadata index
        metadata_result = self.metadata_index.add_record(metadata_record)
        result["metadata_result"] = metadata_result
        
        # 5. Set overall success based on both operations
        result["success"] = (graph_result is not None and 
                           metadata_result.get("success", False))
        
        return result
    
    def generate_llm_context(self, query, search_results, format_type="text"):
        """Generate formatted context for LLM consumption based on search results.
        
        Args:
            query: Original query string
            search_results: Results from hybrid_search
            format_type: Output format ("text", "json", or "markdown")
            
        Returns:
            Formatted context string ready for LLM prompt
        """
        # Use the GraphRAG's context generation with enhanced metadata
        enhanced_results = []
        
        for result in search_results:
            # Combine metadata and properties for richer context
            combined_properties = {**result.get("properties", {})}
            
            # Add metadata fields that aren't in properties
            metadata = result.get("metadata", {})
            for key, value in metadata.items():
                if key not in combined_properties and key not in ("cid", "size_bytes"):
                    combined_properties[key] = value
            
            # Create enhanced result object
            enhanced_result = {
                "entity_id": result["id"],
                "score": result["score"],
                "properties": combined_properties,
                "source": result.get("source", "unknown")
            }
            
            # Add path and distance if available (from graph traversal)
            if "path" in result:
                enhanced_result["path"] = result["path"]
            if "distance" in result:
                enhanced_result["distance"] = result["distance"]
                
            enhanced_results.append(enhanced_result)
            
        # Call the original GraphRAG context generation with enhanced results
        return self.graph_db.generate_llm_prompt(query, enhanced_results, format_type)
```

## Integration Example

Here's an example of how to use the integrated search:

```python
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.integrated_search import MetadataEnhancedGraphRAG

# Initialize IPFS Kit
kit = IPFSKit(role="worker")

# Create integrated search component
enhanced_rag = MetadataEnhancedGraphRAG(ipfs_client=kit)

# Example 1: Metadata-filtered semantic search
results = enhanced_rag.hybrid_search(
    query_text="machine learning model for image classification",
    metadata_filters=[
        ("mime_type", "==", "application/x-pytorch"),
        ("tags", "contains", "computer-vision"),
        ("added_timestamp", ">", 1577836800000)  # After Jan 1, 2020
    ],
    top_k=5
)

# Example 2: Use results with an LLM
context = enhanced_rag.generate_llm_context(
    query="Find image classification models that use transformers",
    search_results=results,
    format_type="markdown"
)

# This context can now be used in an LLM prompt
llm_prompt = f"""Answer the question based on the provided information:

Question: Find image classification models that use transformers

Context:
{context}

Answer:"""

# Example 3: Index a new model with metadata
enhanced_rag.index_entity(
    entity_id="QmModelCID123",
    properties={
        "type": "model",
        "name": "EfficientNetV2",
        "task": "image-classification",
        "framework": "pytorch",
        "architecture": "convolutional",
        "description": "Efficient convolutional neural network for image classification"
    },
    vector=[0.1, 0.2, 0.3, ...],  # Embedding vector
    metadata={
        "mime_type": "application/x-pytorch",
        "size_bytes": 45678912,
        "tags": ["computer-vision", "classification", "efficient"],
        "added_timestamp": time.time() * 1000
    }
)
```

## Benefits of Integration

1. **Efficient Pre-filtering**: Use metadata filters to narrow search space before vector operations
2. **Rich Context**: Combine structured metadata with semantic knowledge for better results
3. **Flexible Search Patterns**: Support for metadata-only, vector-only, or hybrid search
4. **Enhanced LLM Context**: Generate more informative prompts with combined metadata
5. **Unified Indexing**: Single interface to index content in both systems
6. **Cross-component Optimization**: Leverage the strengths of both systems

## Implementation Considerations

1. **Component Initialization**: Handle flexible initialization with existing or new components
2. **Error Handling**: Graceful degradation when components are missing or errors occur
3. **Performance Optimization**: Use Arrow's filtering capabilities before expensive vector operations
4. **Scoring Normalization**: Combine metadata relevance and vector similarity in meaningful scores
5. **Extensibility**: Ensure the design allows for additional search strategies

## Future Enhancements

1. **Weighted Scoring**: Allow configuration of weights between metadata and vector scores
2. **Query Optimization**: Automatically determine most efficient search strategy
3. **Distributed Index**: Enhance with distributed capabilities for large-scale deployments
4. **Caching Layer**: Add result caching for frequently accessed queries
5. **Feedback Integration**: Incorporate user feedback to improve search rankings

## AIMLSearchConnector

The `AIMLSearchConnector` class provides a focused interface for searching specifically for AI/ML assets (models and datasets) stored and indexed within IPFS Kit. It leverages the underlying `MetadataEnhancedGraphRAG` or directly the `ArrowMetadataIndex` and `ModelRegistry`/`DatasetManager`.

**Key Features:**

*   **Targeted Search**: Methods like `search_models` and `search_datasets` with parameters relevant to AI/ML (framework, task, format, tags).
*   **Retriever Creation**: Can generate Langchain or LlamaIndex compatible retrievers based on search results, facilitating integration into RAG pipelines focused on AI assets.
*   **Abstraction**: Simplifies searching for AI/ML assets compared to using the generic `hybrid_search`.

**Usage Example:**

```python
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.integrated_search import AIMLSearchConnector

kit = IPFSKit(role="worker")
search_connector = AIMLSearchConnector(ipfs_client=kit)

# Search for PyTorch image classification models
model_results = search_connector.search_models(
    query_text="image classification",
    framework="pytorch",
    tags=["cnn"],
    min_accuracy=0.9
)
print(f"Found {len(model_results)} models.")

# Search for Parquet datasets related to finance
dataset_results = search_connector.search_datasets(
    query_text="financial timeseries",
    format="parquet",
    min_rows=100000
)
print(f"Found {len(dataset_results)} datasets.")

# Create a Langchain retriever for relevant models
langchain_retriever = search_connector.create_langchain_retriever(
    query_text="transformer models for NLP",
    asset_type="model",
    search_kwargs={"k": 3} # Retrieve top 3
)
# Use retriever in a Langchain chain...
```

## Distributed Query Optimizer

For large clusters or complex search queries, the `DistributedQueryOptimizer` aims to improve performance by distributing parts of the search query across multiple worker nodes.

**Key Features:**

*   **Query Analysis**: Determines if a query (especially metadata filters) can be parallelized.
*   **Worker Selection**: Identifies available worker nodes capable of handling query shards.
*   **Query Distribution**: Splits the query or search space and sends shards to workers.
*   **Result Aggregation**: Combines results received from workers into a final ranked list.
*   **Load Balancing**: Distributes query load across the cluster.

**Usage (Conceptual):**

The optimizer might be used internally by `MetadataEnhancedGraphRAG` or `AIMLSearchConnector` when cluster mode is active, or potentially invoked directly for complex queries.

```python
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.integrated_search import DistributedQueryOptimizer, MetadataEnhancedGraphRAG

kit = IPFSKit(role="master") # Assume running on coordinator
enhanced_rag = MetadataEnhancedGraphRAG(ipfs_client=kit)
optimizer = DistributedQueryOptimizer(ipfs_client=kit) # Needs access to cluster info

query_params = {
    "query_text": "find relevant documents",
    "metadata_filters": [("year", ">", 2020), ("tags", "contains", "ipfs")],
    "top_k": 50
}

if optimizer.is_query_distributable(query_params):
    print("Query is distributable. Executing via optimizer...")
    results = optimizer.distribute_query(query_params, enhanced_rag)
else:
    print("Query not suitable for distribution. Executing locally...")
    results = enhanced_rag.hybrid_search(**query_params)

# Process results...
```

**Considerations:**

*   Adds complexity and network overhead.
*   Most effective for queries with highly parallelizable filters over large datasets/metadata indices.
*   Requires a properly configured cluster with available workers.

## Search Benchmarking

The `SearchBenchmark` class provides tools to evaluate the performance of different search strategies within IPFS Kit.

**Key Features:**

*   **Targeted Benchmarks**: Methods to specifically benchmark metadata search, vector search, and hybrid search.
*   **Realistic Queries**: Uses predefined or custom query sets relevant to the indexed data.
*   **Performance Metrics**: Measures latency, throughput, and potentially relevance (if ground truth is available).
*   **Configuration Comparison**: Allows comparing performance across different index settings or query parameters.
*   **Reporting**: Generates reports summarizing benchmark results.

**Usage Example:**

```python
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.integrated_search import SearchBenchmark, AIMLSearchConnector

kit = IPFSKit(role="worker")
search_connector = AIMLSearchConnector(ipfs_client=kit) # Needed if benchmarking connector methods
benchmark = SearchBenchmark(ipfs_client=kit, search_connector=search_connector)

# Define test cases for hybrid search
hybrid_test_cases = [
    {"query_text": "IPFS concepts", "metadata_filters": [("type", "==", "documentation")]},
    {"query_text": "image models", "metadata_filters": [("framework", "==", "pytorch")]},
]

# Run benchmarks
metadata_results = benchmark.benchmark_metadata_search(num_runs=20)
vector_results = benchmark.benchmark_vector_search(num_runs=50)
hybrid_results = benchmark.benchmark_hybrid_search(test_cases=hybrid_test_cases, num_runs=10)

# Run full suite
full_results = benchmark.run_full_benchmark_suite(save_results=True, output_dir="./search_benchmarks")

# Generate report
report = benchmark.generate_benchmark_report(results=full_results, format="markdown")
print(report)
```

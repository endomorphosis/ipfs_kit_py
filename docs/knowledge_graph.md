# IPLD Knowledge Graph

IPFS Kit includes functionality for building and querying knowledge graphs based on IPLD (InterPlanetary Linked Data), allowing you to represent relationships between IPFS objects.

## Overview

The core components are found in `ipfs_kit_py/ipld_knowledge_graph.py`:

-   **`IPLDGraphDB`**: Manages the storage and retrieval of graph entities (nodes) and relationships (edges) using IPFS DAGs.
-   **`KnowledgeGraphQuery`**: Provides a high-level interface for querying the graph (e.g., finding related entities, traversing paths).
-   **`GraphRAG`**: Integrates the knowledge graph with Retrieval-Augmented Generation (RAG) techniques, potentially using vector embeddings for semantic search within the graph.

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
# kg_db = kit.knowledge_graph
# query_interface = kit.graph_query
```

## Core Concepts

-   **Entities (Nodes):** Represent distinct objects or concepts, typically identified by an IPFS CID or another unique identifier. Entities have properties (metadata).
-   **Relationships (Edges):** Define connections between entities, often with a specific type or label (e.g., "cites", "derivedFrom", "contains"). Relationships can also have properties.
-   **IPLD Storage:** Both entities and relationships are stored as IPLD objects (DAG-JSON or DAG-CBOR) on IPFS, ensuring content-addressability and verifiability. The graph structure itself is built by linking these IPLD objects.

## Usage Examples

```python
# Assuming 'kit' is initialized with knowledge graph enabled
kg_db = kit.knowledge_graph
query_interface = kit.graph_query
graph_rag = kit.graph_rag # May be None if embedding model not configured

try:
    # --- Adding Entities ---
    entity1_props = {"name": "Dataset A", "type": "dataset", "format": "csv"}
    add_entity1_res = kg_db.add_entity(entity_id="QmDatasetA", properties=entity1_props)
    entity1_cid = add_entity1_res.get("cid")

    entity2_props = {"name": "Model Trained on A", "type": "model", "framework": "pytorch"}
    add_entity2_res = kg_db.add_entity(entity_id="QmModelA", properties=entity2_props)
    entity2_cid = add_entity2_res.get("cid")

    entity3_props = {"name": "Research Paper", "type": "publication", "doi": "10.1234/paper"}
    add_entity3_res = kg_db.add_entity(entity_id="QmPaper1", properties=entity3_props)
    entity3_cid = add_entity3_res.get("cid")

    print(f"Added entities: {entity1_cid}, {entity2_cid}, {entity3_cid}")

    # --- Adding Relationships ---
    # Model was trained on Dataset A
    kg_db.add_relationship(
        subject_id="QmModelA",
        predicate="trainedOn",
        object_id="QmDatasetA",
        properties={"timestamp": time.time()}
    )
    # Paper cites Dataset A
    kg_db.add_relationship(
        subject_id="QmPaper1",
        predicate="cites",
        object_id="QmDatasetA"
    )
    # Paper describes Model A
    kg_db.add_relationship(
        subject_id="QmPaper1",
        predicate="describes",
        object_id="QmModelA"
    )
    print("Added relationships.")

    # --- Querying ---
    # Get an entity's details
    entity_details = kg_db.get_entity("QmDatasetA")
    if entity_details:
        print(f"\nDetails for QmDatasetA: {entity_details.get('properties')}")

    # Find entities related to the paper
    related_res = query_interface.find_related("QmPaper1")
    if related_res.get("success"):
        print("\nEntities related to QmPaper1:")
        for rel in related_res.get("relationships", []):
            print(f"- {rel.get('predicate')} -> {rel.get('object_id') or rel.get('subject_id')}") # Show the other entity

    # Find path between dataset and model
    path_res = query_interface.find_paths("QmDatasetA", "QmModelA", max_depth=3)
    if path_res.get("success") and path_res.get("paths"):
        print(f"\nPath found between Dataset A and Model A: {path_res['paths'][0]}")

    # --- RAG / Semantic Search (if enabled) ---
    if graph_rag:
        # Find entities semantically similar to a query
        search_res = graph_rag.retrieve("machine learning models for image classification", top_k=3)
        if search_res.get("success"):
            print("\nSemantic search results:")
            for node in search_res.get("nodes", []):
                print(f"- ID: {node.get('id')}, Score: {node.get('score')}, Properties: {node.get('properties')}")

except AttributeError as e:
     print(f"Knowledge graph component or method not available: {e}")
except Exception as e:
     print(f"An error occurred: {e}")

```

## Key Concepts & Implementation

-   **Entity/Relationship Storage:** Each entity and relationship is typically stored as a separate IPLD object. The graph structure emerges from links within these objects.
-   **Indexing:** Efficient querying often relies on internal indexes (potentially maintained within the `IPLDGraphDB` or using the separate `ArrowMetadataIndex`) to quickly find entities or relationships based on properties or connections.
-   **Query Engine:** The `KnowledgeGraphQuery` class implements graph traversal algorithms (like Breadth-First Search or Depth-First Search) to find paths and related entities.
-   **Vector Embeddings (GraphRAG):** The `GraphRAG` component can generate vector embeddings for entity properties (e.g., names, descriptions) and use a vector database (like FAISS, potentially integrated with IPFS storage) to perform semantic similarity searches over the graph nodes.

This knowledge graph functionality allows for rich representation and exploration of interconnected data stored on IPFS.

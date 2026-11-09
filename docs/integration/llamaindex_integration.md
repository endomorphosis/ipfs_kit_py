# LlamaIndex Integration with IPFS Kit

`ipfs-kit-py` integrates with the LlamaIndex framework, enabling the creation of powerful indexing and query applications for data stored on IPFS. This allows developers to build retrieval-augmented generation (RAG) systems and knowledge applications directly on top of decentralized, content-addressed data. The core functionality is provided by the `LlamaIndexIntegration` class within `ai_ml_integration.py`.

## Overview

This integration connects LlamaIndex's data structures (Documents, Nodes, Indices, Query Engines) with IPFS storage.

**Key Features:**

*   **IPFS Document Loader/Reader**: Load data directly from IPFS CIDs or paths into LlamaIndex `Document` objects.
*   **IPFS Index Persistence**: Store and load various LlamaIndex index types (e.g., `VectorStoreIndex`, `SummaryIndex`, `KeywordTableIndex`) to/from IPFS.
*   **Content-Addressed Indices**: Indices stored on IPFS are immutable and verifiable via their CIDs.
*   **Decentralized Knowledge Bases**: Build and share knowledge bases where the underlying index data resides on IPFS.

## Implementation (`LlamaIndexIntegration`)

The `LlamaIndexIntegration` class facilitates the use of IPFS with LlamaIndex:

*   **Initialization**: Takes an `ipfs-kit-py` client instance.
*   **Document Loading**: `load_documents(cid_or_path)` fetches content from IPFS and prepares it for LlamaIndex (similar to the Langchain integration, likely producing LlamaIndex `Document` objects).
*   **Index Creation**: `create_index(documents, service_context=None)` builds a LlamaIndex index (typically a `VectorStoreIndex` if embeddings are involved) from the loaded documents.
*   **Index Storage**: `store_index(index, name, version)` serializes a LlamaIndex index object and stores its components (vectors, metadata, etc.) on IPFS, associating it with a name and version.
*   **Index Loading**: `load_index(name, version)` retrieves a previously stored index from IPFS by its name and version and reconstructs the LlamaIndex index object.

## Configuration

Similar to the Langchain integration, specific configuration within `ipfs-kit-py` is usually minimal. However, LlamaIndex itself often requires configuration, especially for embedding models or LLMs used in query engines. This is typically handled via LlamaIndex's `ServiceContext` or environment variables (e.g., `OPENAI_API_KEY`).

## Usage Example

```python
import logging
import os
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
# Assuming LlamaIndex and necessary dependencies (like openai) are installed
# pip install llama-index openai

logging.basicConfig(level=logging.INFO)

# --- Setup ---
# Ensure IPFS daemon is running or API is configured
# Ensure OPENAI_API_KEY environment variable is set for embeddings/LLM
try:
    kit = IPFSSimpleAPI() # Assumes default IPFS connection works
    llama_integration = kit.ai_llama_index # Access via high-level API attribute
    if not llama_integration:
         # Fallback if direct attribute access isn't the way
         from ipfs_kit_py.ai_ml_integration import LlamaIndexIntegration
         llama_integration = LlamaIndexIntegration(ipfs_client=kit)

except Exception as e:
    logging.error(f"Failed to initialize IPFS Kit or LlamaIndexIntegration: {e}")
    exit()

# --- 1. Add and Load Documents ---
# Re-use the document adding logic from Langchain example or assume doc_cid exists
doc_cid = "Qm..." # Replace with actual CID from previous step or a known CID
if not doc_cid or doc_cid == "Qm...":
     try:
        doc_content = "IPFS is a distributed system for storing and accessing files, websites, applications, and data."
        add_result = kit.add_bytes(doc_content.encode())
        doc_cid = add_result.get('Hash') if isinstance(add_result, dict) else None
        if not doc_cid: raise ValueError("Failed to add dummy document.")
        logging.info(f"Using dummy document CID: {doc_cid}")
     except Exception as add_e:
        logging.error(f"Failed to add dummy document for LlamaIndex example: {add_e}")
        exit()

try:
    # Load documents using the integration
    logging.info(f"Loading documents from CID: {doc_cid}")
    # Note: The exact return type might differ slightly from Langchain's loader
    documents = llama_integration.load_documents(cid_or_path=doc_cid)
    # Assuming it returns a list of LlamaIndex Document objects
    logging.info(f"Loaded {len(documents)} document(s). Content snippet: '{documents[0].get_content()[:50]}...'")

except Exception as e:
    logging.error(f"Error loading documents: {e}")
    exit()

# --- 2. Create IPFS Index ---
try:
    logging.info("Creating LlamaIndex Index (VectorStoreIndex)...")
    # LlamaIndex often uses a ServiceContext for configuration (LLM, embeddings)
    # By default, it might try to use OpenAI if available
    from llama_index import ServiceContext #, VectorStoreIndex (might be created internally)
    # service_context = ServiceContext.from_defaults(chunk_size=512) # Example customization

    # The integration method likely handles index creation internally
    index_result = llama_integration.create_index(
        documents=documents,
        # service_context=service_context # Optional: pass custom context
    )

    if not index_result.get("success"):
         logging.error(f"Failed to create index: {index_result.get('error')}")
         exit()

    index = index_result.get("index") # Get the LlamaIndex Index object
    index_cid = index_result.get("cid") # CID where the index data is stored on IPFS
    logging.info(f"LlamaIndex Index created. Storage CID: {index_cid}")

    # --- 3. Create Query Engine and Query ---
    logging.info("Creating query engine...")
    query_engine = index.as_query_engine()
    logging.info("Query engine created.")

    query = "What is IPFS?"
    logging.info(f"Querying index: '{query}'")
    response = query_engine.query(query)
    logging.info(f"Query response: {response}")

except Exception as e:
    logging.error(f"Error creating index or querying: {e}")
    exit()

# --- 4. Store and Load the Index ---
try:
    index_name = "ipfs_knowledge_index"
    index_version = "1.0.0"

    logging.info(f"Storing index '{index_name}' v{index_version} to IPFS...")
    # Note: Storing might re-save the index data if not already done during creation
    store_result = llama_integration.store_index(
        index=index,
        name=index_name,
        version=index_version,
        metadata={"description": "Index for IPFS documents"}
    )

    if not store_result.get("success"):
        logging.error(f"Failed to store index: {store_result.get('error')}")
        exit()

    stored_index_cid = store_result.get("cid") # May differ from creation CID if re-saved
    logging.info(f"Index stored successfully. Storage CID: {stored_index_cid}")

    # Load the index back from IPFS
    logging.info(f"Loading index '{index_name}' v{index_version} from IPFS...")
    load_result = llama_integration.load_index(
        name=index_name,
        version=index_version
        # service_context=service_context # Pass context if needed for loading
    )

    if not load_result.get("success"):
        logging.error(f"Failed to load index: {load_result.get('error')}")
        exit()

    loaded_index = load_result.get("index")
    logging.info("Index loaded successfully.")

    # Verify the loaded index works
    loaded_query_engine = loaded_index.as_query_engine()
    response_loaded = loaded_query_engine.query(query)
    logging.info(f"Loaded index query response: {response_loaded}")
    # Note: Comparing LlamaIndex responses directly can be tricky due to potential variations
    # assert str(response) == str(response_loaded)

except Exception as e:
    logging.error(f"Error storing or loading the index: {e}")

logging.info("LlamaIndex integration example finished.")
```

## Benefits

*   **Decentralized RAG**: Build Retrieval-Augmented Generation systems where the knowledge base (index) is stored decentrally on IPFS.
*   **Verifiable Knowledge**: Content-addressing ensures the integrity of the index data. Users can verify they are querying the correct version of the knowledge base.
*   **Persistent Indices**: Indices stored on IPFS are durable and can be easily shared or loaded by different applications or users.
*   **Collaboration**: Teams can collaborate on building and maintaining knowledge bases stored on IPFS.

## Considerations

*   **IPFS Node**: Requires a running IPFS node.
*   **Performance**: Index loading and query times depend on IPFS retrieval speed, index size, and network conditions. Caching helps, but it might be slower than purely local or specialized database solutions for very low-latency requirements.
*   **Index Size**: Large LlamaIndex indices can consume significant storage space on IPFS.
*   **Embedding/LLM Costs**: Relies on external services (like OpenAI) for embeddings and query processing, incurring potential costs and requiring API key management.
*   **Serialization**: Ensuring LlamaIndex objects (especially complex indices or those with custom components) can be reliably serialized to and deserialized from IPFS is crucial.

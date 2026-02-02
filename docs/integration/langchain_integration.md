# Langchain Integration with IPFS Kit

`ipfs-kit-py` provides seamless integration with the Langchain framework, enabling developers to build LLM applications that leverage the benefits of content-addressed storage via IPFS. This includes storing documents, vector embeddings, and entire chains on IPFS for persistence, versioning, and decentralized distribution. The core functionality is provided by the `LangchainIntegration` class within `ai_ml_integration.py`.

## Overview

The integration bridges Langchain's components (Document Loaders, Vector Stores, Retrievers, Chains) with IPFS storage capabilities.

**Key Features:**

*   **IPFS Document Loader**: Load documents directly from IPFS CIDs or paths.
*   **IPFS Vector Store**: Store and retrieve vector embeddings using IPFS as the backend. This allows for decentralized and verifiable vector databases.
*   **IPFS Retriever**: A Langchain retriever implementation that fetches relevant documents or vectors from the IPFS Vector Store.
*   **Chain Persistence**: Save and load entire Langchain chains (including prompts, models, and logic) to/from IPFS, enabling versioning and sharing.

## Implementation (`LangchainIntegration`)

The `LangchainIntegration` class acts as a factory and manager for IPFS-backed Langchain components:

*   **Initialization**: Takes an `ipfs-kit-py` client instance.
*   **Document Loading**: `load_documents(cid_or_path)` fetches content from IPFS and converts it into Langchain `Document` objects.
*   **Vector Store Creation**: `create_vector_store(documents, embedding_model)` takes loaded documents, generates embeddings using a specified model (e.g., OpenAI, HuggingFace), and stores them in an IPFS-backed structure. It returns a Langchain `VectorStore` compatible object (`IPFSVectorStore`).
*   **Chain Storage**: `store_chain(chain, name, version)` serializes a Langchain chain object and stores it on IPFS, associating it with a name and version.
*   **Chain Loading**: `load_chain(name, version)` retrieves a previously stored chain from IPFS by its name and version and deserializes it back into a usable Langchain chain object.

## Configuration

Langchain integration typically doesn't require specific configuration within `ipfs-kit-py` itself, beyond ensuring the core IPFS client and AI/ML integration are set up. However, you'll need API keys or configurations for the embedding models or LLMs used within Langchain (e.g., OpenAI API key set as an environment variable).

## Usage Example

```python
import logging
import os
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
# Assuming Langchain and necessary dependencies (like openai, tiktoken) are installed
# pip install langchain openai tiktoken

logging.basicConfig(level=logging.INFO)

# --- Setup ---
# Ensure IPFS daemon is running or API is configured
# Ensure OPENAI_API_KEY environment variable is set for embeddings/LLM
try:
    kit = IPFSSimpleAPI() # Assumes default IPFS connection works
    langchain_integration = kit.ai_langchain # Access via high-level API attribute
    if not langchain_integration:
         # Fallback if direct attribute access isn't the way
         from ipfs_kit_py.ai_ml_integration import LangchainIntegration
         langchain_integration = LangchainIntegration(ipfs_client=kit)

except Exception as e:
    logging.error(f"Failed to initialize IPFS Kit or LangchainIntegration: {e}")
    exit()

# --- 1. Add and Load Documents ---
# Assume we have a document stored on IPFS
try:
    # Add a dummy text file to IPFS first
    doc_content = "IPFS stands for InterPlanetary File System. It is a peer-to-peer hypermedia protocol designed to make the web faster, safer, and more open."
    add_result = kit.add_bytes(doc_content.encode())
    doc_cid = add_result.get('Hash') if isinstance(add_result, dict) else None

    if not doc_cid:
        logging.error("Failed to add dummy document to IPFS.")
        exit()
    logging.info(f"Dummy document added to IPFS with CID: {doc_cid}")

    # Load documents using the integration
    logging.info(f"Loading documents from CID: {doc_cid}")
    documents = langchain_integration.load_documents(cid_or_path=doc_cid)
    logging.info(f"Loaded {len(documents)} document(s). Content snippet: '{documents[0].page_content[:50]}...'")

except Exception as e:
    logging.error(f"Error loading documents: {e}")
    exit()

# --- 2. Create IPFS Vector Store ---
try:
    logging.info("Creating IPFS Vector Store...")
    # Requires an embedding model. Using OpenAI here.
    from langchain.embeddings import OpenAIEmbeddings
    embeddings = OpenAIEmbeddings() # Assumes OPENAI_API_KEY is set

    vector_store_result = langchain_integration.create_vector_store(
        documents=documents,
        embedding_model=embeddings,
        collection_name="ipfs_docs_example" # Optional name for the collection
    )

    if not vector_store_result.get("success"):
         logging.error(f"Failed to create vector store: {vector_store_result.get('error')}")
         exit()

    vector_store = vector_store_result.get("vector_store") # Get the VectorStore object
    vector_store_cid = vector_store_result.get("cid") # CID of the stored vector index
    logging.info(f"IPFS Vector Store created. Index CID: {vector_store_cid}")

    # Test similarity search
    query = "What is IPFS?"
    search_results = vector_store.similarity_search(query, k=1)
    logging.info(f"Similarity search for '{query}': Found {len(search_results)} result(s).")
    if search_results:
        logging.info(f"  Top result: '{search_results[0].page_content[:100]}...'")

except Exception as e:
    logging.error(f"Error creating or searching vector store: {e}")
    exit()


# --- 3. Create and Use a Chain ---
try:
    logging.info("Creating a RetrievalQA chain...")
    from langchain.chains import RetrievalQA
    from langchain.llms import OpenAI

    # Create a retriever from the IPFS vector store
    retriever = vector_store.as_retriever()

    # Create the QA chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=OpenAI(), # Assumes OPENAI_API_KEY is set
        chain_type="stuff",
        retriever=retriever
    )
    logging.info("RetrievalQA chain created.")

    # Run the chain
    response = qa_chain.run(query)
    logging.info(f"Chain response for '{query}': {response}")

except Exception as e:
    logging.error(f"Error creating or running the chain: {e}")
    exit()

# --- 4. Store and Load the Chain ---
try:
    chain_name = "ipfs_qa_chain"
    chain_version = "1.0.0"

    logging.info(f"Storing chain '{chain_name}' v{chain_version} to IPFS...")
    store_result = langchain_integration.store_chain(
        chain=qa_chain,
        name=chain_name,
        version=chain_version,
        metadata={"description": "QA chain for IPFS documents"}
    )

    if not store_result.get("success"):
        logging.error(f"Failed to store chain: {store_result.get('error')}")
        exit()

    chain_cid = store_result.get("cid")
    logging.info(f"Chain stored successfully. CID: {chain_cid}")

    # Load the chain back from IPFS
    logging.info(f"Loading chain '{chain_name}' v{chain_version} from IPFS...")
    load_result = langchain_integration.load_chain(
        name=chain_name,
        version=chain_version
    )

    if not load_result.get("success"):
        logging.error(f"Failed to load chain: {load_result.get('error')}")
        exit()

    loaded_chain = load_result.get("chain")
    logging.info("Chain loaded successfully.")

    # Verify the loaded chain works
    response_loaded = loaded_chain.run(query)
    logging.info(f"Loaded chain response for '{query}': {response_loaded}")
    assert response == response_loaded

except Exception as e:
    logging.error(f"Error storing or loading the chain: {e}")

logging.info("Langchain integration example finished.")

```

## Benefits

*   **Decentralization**: Store and share Langchain components (documents, vectors, chains) without relying on centralized servers.
*   **Verifiability**: Content-addressing ensures the integrity and provenance of stored artifacts.
*   **Persistence**: Chains and vector stores saved on IPFS are persistent and resilient.
*   **Versioning**: Easily manage different versions of chains or vector stores using IPFS CIDs or the naming system provided.
*   **Interoperability**: Enables sharing and collaboration on Langchain applications within the IPFS ecosystem.

## Considerations

*   **IPFS Node Availability**: An accessible IPFS node (local daemon or remote API) is required.
*   **Performance**: Retrieval times from IPFS depend on network conditions and content availability (pinning). Caching within `ipfs-kit-py` helps mitigate this.
*   **Embedding Model Costs**: Using embedding models like OpenAI incurs costs and requires API key management.
*   **Scalability**: For very large vector stores, consider the performance implications of storing and querying embeddings via IPFS compared to specialized vector databases. The implementation might involve sharding or indexing strategies.

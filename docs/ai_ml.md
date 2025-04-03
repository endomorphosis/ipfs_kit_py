# AI/ML Integration

IPFS Kit provides sophisticated features specifically designed to support Machine Learning workflows, leveraging content-addressing for reproducibility, distribution, and efficient data handling. The IPFS-based approach offers several unique advantages for ML workflows including content deduplication, immutable versioning, and distributed data access.

## Overview

The core AI/ML components are found in `ipfs_kit_py/ai_ml_integration.py` and include:

-   **`ModelRegistry`**: Store, version, and retrieve ML models using IPFS CIDs with automatic framework detection
-   **`DatasetManager`**: Manage ML datasets with versioning, metadata tracking, and format detection
-   **`IPFSDataLoader`**: High-performance data loader with background prefetching and framework adapters ([See Separate Docs](ipfs_dataloader.md))
-   **`LangchainIntegration` / `LlamaIndexIntegration`**: Bridge IPFS content with popular LLM frameworks
-   **`DistributedTraining`**: Coordinate ML training tasks across IPFS Kit clusters with result aggregation

## Benefits for ML Workflows

IPFS provides several advantages for machine learning workflows:

1. **Immutable Versioning**: Every model and dataset version has a unique CID, ensuring reproducibility
2. **Content Deduplication**: Duplicate data is automatically deduplicated, saving storage space
3. **Distributed Access**: Models and datasets can be accessed from any node in the network
4. **Collaborative Development**: Multiple teams can share and build upon the same models and datasets
5. **Verifiable Integrity**: Content addressing ensures data hasn't been altered
6. **Resilient Storage**: Content can be pinned across multiple nodes for high availability

## Enabling AI/ML Features

Initialize `ipfs_kit` with `enable_ai_ml=True` in the metadata:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

kit = ipfs_kit(metadata={"enable_ai_ml": True})

# Access components (if initialization was successful)
if hasattr(kit, 'model_registry'):
    print("Model Registry is available.")
if hasattr(kit, 'dataset_manager'):
    print("Dataset Manager is available.")
if hasattr(kit, 'ipfs_dataloader'):
    print("IPFS DataLoader is available.")
if hasattr(kit, 'langchain_integration'):
    print("Langchain Integration is available.")
if hasattr(kit, 'llama_index_integration'):
    print("LlamaIndex Integration is available.")
if hasattr(kit, 'distributed_training'):
    print("Distributed Training is available.")
```

### Optional Dependencies

The AI/ML integration supports various ML frameworks, but they need to be installed separately:

- **scikit-learn**: For traditional ML algorithms (`pip install scikit-learn`)
- **PyTorch**: For deep learning models (`pip install torch`)
- **TensorFlow**: For deep learning models (`pip install tensorflow`)
- **Langchain**: For LLM integration (`pip install langchain`)
- **LlamaIndex**: For LLM indexing (`pip install llama-index`)

IPFS Kit will detect available frameworks at runtime and adapt functionality accordingly.

## Model Registry

The `ModelRegistry` component provides a comprehensive system for storing, versioning, and retrieving machine learning models using IPFS content addressing. It handles automatic framework detection, serialization, and metadata management.

### Key Features

- **Multi-Framework Support**: Automatic detection and handling of scikit-learn, PyTorch, and TensorFlow models
- **Versioning**: Track model versions with semver-compatible versioning
- **Framework-Specific Serialization**: Optimal storage format for each framework (pickle, PT, SavedModel, etc.)
- **Metadata Indexing**: Store and query models by framework, tags, metrics, etc.
- **Content-Addressing**: Models are identified by their content hash (CID), ensuring integrity

### Basic Usage

```python
# Assuming 'kit' is initialized with AI/ML enabled

# --- Storing a Model ---
# Example with a PyTorch model
import torch
import torch.nn as nn

# Create a simple model
model = nn.Sequential(
    nn.Linear(10, 50),
    nn.ReLU(),
    nn.Linear(50, 1)
)

model_metadata = {
    "name": "SimpleRegressor",
    "version": "1.0.0",
    "description": "Basic regression model for demonstration",
    "input_shape": [10],
    "output_shape": [1],
    "tags": ["regression", "demo"],
    "metrics": {
        "mse": 0.23,
        "r2": 0.85
    }
}

store_result = kit.model_registry.add_model(
    model=model,  # Can pass the model object directly
    model_name="SimpleRegressor",
    version="1.0.0",
    # Framework auto-detected as "pytorch"
    metadata=model_metadata
)

if store_result.get("success"):
    model_cid = store_result.get("cid")
    print(f"Stored model with CID: {model_cid}")
else:
    print(f"Failed to store model: {store_result.get('error')}")

# --- Retrieving a Model ---
# Retrieve by name and version
loaded_model, model_info = kit.model_registry.get_model(
    model_name="SimpleRegressor",
    version="1.0.0"  # Optional - gets latest version if omitted
)

# Model is already loaded and ready to use
predictions = loaded_model(torch.randn(5, 10))  # Example inference
print(f"Model predictions shape: {predictions.shape}")
print(f"Model metadata: {model_info}")

# --- Creating a New Version ---
# Fine-tune the model
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
# ... training code ...

# Save the updated model as a new version
store_result = kit.model_registry.add_model(
    model=model,
    model_name="SimpleRegressor",
    version="1.1.0",  # Increment version
    metadata={
        **model_metadata,  # Keep previous metadata
        "metrics": {  # Update metrics
            "mse": 0.18,  # Improved performance
            "r2": 0.89
        },
        "training_steps": 1000
    }
)

# --- Listing Models ---
list_result = kit.model_registry.list_models()
if list_result.get("success"):
    print("\nAvailable Models:")
    for model_name, versions in list_result.get("models", {}).items():
        print(f"Model: {model_name}")
        for v in versions:
            print(f"  - v{v['version']} ({v['framework']}) - CID: {v['cid']}")
            if 'metrics' in v['metadata']:
                metrics = v['metadata']['metrics']
                print(f"    Metrics: {', '.join([f'{k}={v}' for k, v in metrics.items()])}")
```

### Framework-Specific Storage

The `ModelRegistry` uses different storage methods depending on the model framework:

| Framework | Storage Format | File Extensions |
|-----------|---------------|----------------|
| PyTorch | Native serialization + TorchScript (when possible) | `.pt`, `.script.pt` |
| TensorFlow | SavedModel directory + H5 (for Keras) | `saved_model/`, `.h5` |
| scikit-learn | Pickle | `.pkl` |
| Others | Pickle (fallback) | `.pkl` |

For each model, a metadata file is also stored alongside the model files, containing all the information about the model, its version, and custom metadata.

## Dataset Manager

The `DatasetManager` component provides tools for managing machine learning datasets on IPFS, with versioning, format detection, and metadata tracking.

### Key Features

- **Format Detection**: Automatically detect dataset formats (CSV, Parquet, images, etc.)
- **Statistics Generation**: Compute and store dataset statistics for quick reference
- **Versioning**: Track dataset versions with metadata
- **Efficient Retrieval**: Get datasets with automatic local caching
- **Content Verification**: Ensure dataset integrity through content addressing

### Basic Usage

```python
# Assuming 'kit' is initialized with AI/ML enabled

# --- Creating and Storing a Dataset ---
import pandas as pd
import numpy as np

# Create a simple dataset
data = {
    'feature1': np.random.randn(1000),
    'feature2': np.random.randn(1000),
    'feature3': np.random.randn(1000),
    'target': np.random.randint(0, 2, 1000)  # Binary classification
}
df = pd.DataFrame(data)

# Save to a temporary CSV file
dataset_path = "/tmp/example_dataset.csv"
df.to_csv(dataset_path, index=False)

# Add dataset to IPFS with metadata
dataset_metadata = {
    "name": "ExampleDataset",
    "description": "Synthetic dataset for binary classification",
    "version": "1.0.0",
    "features": ["feature1", "feature2", "feature3"],
    "target": "target",
    "task_type": "classification",
    "tags": ["synthetic", "binary", "demo"]
}

add_result = kit.dataset_manager.add_dataset(
    dataset_path=dataset_path,
    dataset_name="ExampleDataset",
    version="1.0.0",
    # Format auto-detected as "csv"
    metadata=dataset_metadata
)

if add_result.get("success"):
    dataset_cid = add_result.get("cid")
    print(f"Added dataset with CID: {dataset_cid}")
    
    # Dataset statistics are automatically computed
    stats = add_result.get("stats")
    print(f"Dataset stats: {stats}")
else:
    print(f"Failed to add dataset: {add_result.get('error')}")

# --- Retrieving a Dataset ---
get_result = kit.dataset_manager.get_dataset(
    dataset_name="ExampleDataset",
    version="1.0.0",  # Optional - gets latest version if omitted
    output_path="/tmp/retrieved_dataset"  # Optional - uses temp dir if omitted
)

if get_result.get("success"):
    dataset_path = get_result.get("local_path")
    dataset_metadata = get_result.get("metadata")
    
    # Load the dataset using pandas
    retrieved_df = pd.read_csv(f"{dataset_path}/example_dataset.csv")
    print(f"Retrieved dataset with {len(retrieved_df)} rows and {len(retrieved_df.columns)} columns")
    print(f"Dataset metadata: {dataset_metadata}")
else:
    print(f"Failed to retrieve dataset: {get_result.get('error')}")

# --- Creating a New Version ---
# Add some derived features
df['feature4'] = df['feature1'] * df['feature2']
df['feature5'] = np.log(np.abs(df['feature3']) + 1)

# Save updated dataset
updated_path = "/tmp/example_dataset_v2.csv"
df.to_csv(updated_path, index=False)

# Add as a new version
add_result = kit.dataset_manager.add_dataset(
    dataset_path=updated_path,
    dataset_name="ExampleDataset",
    version="2.0.0",  # Increment version
    metadata={
        **dataset_metadata,  # Keep previous metadata
        "version": "2.0.0",
        "features": ["feature1", "feature2", "feature3", "feature4", "feature5"],
        "changes": "Added derived features: feature4 and feature5"
    }
)

# --- Listing Datasets ---
list_result = kit.dataset_manager.list_datasets()
if list_result.get("success"):
    print("\nAvailable Datasets:")
    for dataset_name, versions in list_result.get("datasets", {}).items():
        print(f"Dataset: {dataset_name}")
        for v in versions:
            print(f"  - v{v['version']} ({v['format']}) - CID: {v['cid']}")
            if 'size_bytes' in v['stats']:
                size_mb = v['stats']['size_bytes'] / (1024 * 1024)
                print(f"    Size: {size_mb:.2f} MB, Rows: {v['stats'].get('num_rows')}")
```

### Supported Dataset Formats

The `DatasetManager` can handle various dataset formats:

| Format | Description | Auto-detection |
|--------|-------------|---------------|
| CSV | Comma-separated values | `.csv` extension |
| TSV | Tab-separated values | `.tsv` extension |
| Parquet | Apache Parquet files | `.parquet` extension |
| JSON | JSON files or JSON Lines | `.json`, `.jsonl` extensions |
| Images | Image files in a directory | Directory containing `.jpg`, `.png`, etc. |
| TFRecord | TensorFlow record files | `.tfrecord` extension |
| HDF5 | Hierarchical Data Format | `.h5`, `.hdf5` extensions |
| Arrow | Apache Arrow files | `.arrow`, `.feather` extensions |
| Text | Plain text files | `.txt` extension |

For each format, appropriate statistics are generated. For tabular data, this includes column information, row counts, and basic statistics; for image data, it includes counts and size information.

## IPFS DataLoader

The `IPFSDataLoader` provides an efficient way to load data from IPFS datasets for training ML models. It includes features like background prefetching, batching, shuffling, and framework integration.

```python
# Assuming 'kit' is initialized with AI/ML enabled and dataset_cid is available

# --- Basic Usage ---
# Create a data loader
data_loader = kit.ipfs_dataloader(
    batch_size=32,
    shuffle=True,
    prefetch=2  # Number of batches to prefetch in background
)

# Load a dataset by CID
load_result = data_loader.load_dataset(dataset_cid)
if load_result.get("success"):
    print(f"Loaded dataset with {load_result.get('total_samples')} samples")
    
    # Iterate through batches
    for batch_idx, batch in enumerate(data_loader):
        # Each batch is a list of samples
        print(f"Batch {batch_idx}: {len(batch)} samples")
        
        # Process batch...
        # (in a real scenario, this would feed into your model)
        
        # Break after a few batches for this example
        if batch_idx >= 2:
            break
else:
    print(f"Failed to load dataset: {load_result.get('error')}")

# --- PyTorch Integration ---
# Convert to PyTorch DataLoader
if hasattr(data_loader, 'to_pytorch'):
    try:
        pytorch_loader = data_loader.to_pytorch()
        
        # Now use it like a regular PyTorch DataLoader
        for batch_idx, (features, labels) in enumerate(pytorch_loader):
            print(f"PyTorch batch {batch_idx}: features shape {features.shape}, labels shape {labels.shape}")
            
            # Your training code would go here...
            
            if batch_idx >= 2:
                break
    except Exception as e:
        print(f"PyTorch integration error: {e}")

# --- TensorFlow Integration ---
# Convert to TensorFlow Dataset
if hasattr(data_loader, 'to_tensorflow'):
    try:
        tf_dataset = data_loader.to_tensorflow()
        
        # Now use it like a regular TensorFlow Dataset
        for batch_idx, (features, labels) in enumerate(tf_dataset.take(3)):
            print(f"TensorFlow batch {batch_idx}: features shape {features.shape}, labels shape {labels.shape}")
            
            # Your training code would go here...
    except Exception as e:
        print(f"TensorFlow integration error: {e}")

# Clean up resources when done
data_loader.close()
```

For more details about the `IPFSDataLoader`, see the dedicated documentation: [IPFS DataLoader Docs](ipfs_dataloader.md).

## Langchain Integration

The `LangchainIntegration` component provides tools to bridge IPFS content with the Langchain framework for Large Language Model (LLM) applications.

### Key Features

- **Document Loading**: Load IPFS content as Langchain Document objects
- **Vector Storage**: Store embeddings and document vectors on IPFS
- **Content Persistence**: Use IPFS for durable content storage
- **Distributed Content Access**: Access documents across the network

### Basic Usage

```python
# Assuming 'kit' is initialized with AI/ML enabled 
# and Langchain is installed

# --- Check Availability ---
availability = kit.langchain_integration.check_availability()
if not availability.get("langchain_available"):
    print("Langchain not available. Install with: pip install langchain")
    # Exit early if not available
    raise ImportError("Langchain required for this example")

# --- Loading Documents from IPFS ---
# This can be a CID or a local path with IPFS content
ipfs_content_path = "QmYourDocumentDirectoryCID"

# Create a document loader
document_loader = kit.langchain_integration.create_document_loader(ipfs_content_path)

# Load documents
documents = document_loader.load()
print(f"Loaded {len(documents)} documents from IPFS")

# --- Creating a Vector Store ---
# You'll need an embedding function from Langchain
from langchain.embeddings import OpenAIEmbeddings  # Example - requires API key
embedding_function = OpenAIEmbeddings()

# Create a vector store backed by IPFS
vector_store = kit.langchain_integration.create_ipfs_vectorstore(embedding_function)

# Add documents to the vector store
vector_store.add_texts(
    texts=[doc.page_content for doc in documents],
    metadatas=[doc.metadata for doc in documents]
)

# The vector store is now persisted on IPFS with CID
print(f"Vector store persisted to IPFS with CID: {vector_store.cid}")

# --- Searching the Vector Store ---
query = "What is IPFS content addressing?"
search_results = vector_store.similarity_search(query, k=3)

print("Search results:")
for i, doc in enumerate(search_results):
    print(f"Result {i+1}:")
    print(f"Content: {doc.page_content[:100]}...")
    print(f"Source: {doc.metadata.get('source')}")
    print()

# --- Loading an Existing Vector Store ---
# If you have a CID from a previously saved vector store
existing_store = kit.langchain_integration.IPFSVectorStore.from_ipfs(
    kit.ipfs,
    "QmExistingVectorStoreCID",
    embedding_function
)

# Now you can use it for searches
results = existing_store.similarity_search("content addressing", k=2)
```

## LlamaIndex Integration

The `LlamaIndexIntegration` component provides tools to bridge IPFS content with the LlamaIndex framework for building and querying knowledge bases with Large Language Models.

### Key Features

- **Document Reading**: Read IPFS content as LlamaIndex Document objects
- **Index Storage**: Store LlamaIndex indexes on IPFS
- **Distributed Access**: Share indexes and knowledge bases via IPFS
- **Content Persistence**: Ensure durability of indexes and documents

### Basic Usage

```python
# Assuming 'kit' is initialized with AI/ML enabled 
# and LlamaIndex is installed

# --- Check Availability ---
availability = kit.llama_index_integration.check_availability()
if not availability.get("llama_index_available"):
    print("LlamaIndex not available. Install with: pip install llama-index")
    # Exit early if not available
    raise ImportError("LlamaIndex required for this example")

# --- Loading Documents from IPFS ---
# This can be a CID or a local path
ipfs_content_path = "QmYourDocumentDirectoryCID"

# Create a document reader
document_reader = kit.llama_index_integration.create_ipfs_document_reader(ipfs_content_path)

# Load documents
documents = document_reader.load_data()
print(f"Loaded {len(documents)} documents from IPFS")

# --- Creating an Index ---
# You'll need LlamaIndex components
from llama_index.core import Settings, VectorStoreIndex
from llama_index.llms import OpenAI  # Example - requires API key

# Configure LlamaIndex
Settings.llm = OpenAI()

# Create IPFS storage context
storage_context = kit.llama_index_integration.create_ipfs_storage_context()

# Build index
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context
)

# Index is now stored on IPFS
print("Index stored on IPFS")

# --- Querying the Index ---
query_engine = index.as_query_engine()
response = query_engine.query("What is IPFS content addressing?")

print("Query Response:")
print(response.response)
print(f"Source documents: {len(response.source_nodes)}")
```

## Distributed Training

The `DistributedTraining` component enables distributed machine learning training across an IPFS Kit cluster by leveraging the cluster's role-based architecture (master/worker nodes).

### Key Features

- **Task Distribution**: Split and distribute training tasks across worker nodes
- **Resource Optimization**: Assign tasks based on worker capabilities
- **Result Aggregation**: Combine results from distributed training
- **Model Averaging**: Aggregate model parameters from multiple workers
- **Training Coordination**: Synchronize training across workers

### Architecture

The distributed training system uses a master-worker architecture:

1. **Master Node**:
   - Prepares training tasks and splits datasets
   - Distributes tasks to worker nodes
   - Monitors training progress
   - Aggregates results from workers
   - Registers final models in the ModelRegistry

2. **Worker Nodes**:
   - Receive training tasks from master
   - Load models and datasets from IPFS
   - Execute training on local resources
   - Upload trained models back to IPFS
   - Report results to master

### Basic Usage

```python
# --- Master Node ---
# Assuming 'kit_master' is initialized with role='master' and cluster management enabled

# --- Prepare a Distributed Training Task ---
# This example uses PyTorch, but the principle applies to other frameworks
model_name = "DistributedMLP"
dataset_name = "ExampleDataset"

# Define hyperparameters and training configuration
training_config = {
    "framework": "pytorch",
    "epochs": 5,
    "batch_size": 32,
    "learning_rate": 0.001,
    "optimizer": "adam",
    "loss": "cross_entropy",
    "metrics": ["accuracy"],
    "device": "cuda" # Workers with GPUs will use them
}

# Prepare the distributed task
task_result = kit_master.distributed_training.prepare_distributed_task(
    model_name=model_name,
    dataset_name=dataset_name,
    training_config=training_config,
    num_workers=3  # Number of workers to distribute to
)

if task_result.get("success"):
    task_id = task_result.get("task_id")
    print(f"Distributed training task created with ID: {task_id}")
    print(f"Task distributed to {task_result.get('num_workers')} workers")
    
    # Training is now happening on worker nodes...
    # In a real scenario, you would wait for completion
    
    # --- Aggregate Results (after workers complete) ---
    # In a real scenario, this would be called after workers finish
    aggregate_result = kit_master.distributed_training.aggregate_training_results(task_id)
    
    if aggregate_result.get("success"):
        final_model_cid = aggregate_result.get("best_model_cid")
        print(f"Aggregated model stored with CID: {final_model_cid}")
        print(f"Metrics from workers: {aggregate_result.get('worker_metrics')}")
    else:
        print(f"Failed to aggregate results: {aggregate_result.get('error')}")
else:
    print(f"Failed to prepare distributed task: {task_result.get('error')}")

# --- Worker Node (for reference) ---
# Worker nodes receive tasks from the master node automatically
# and execute them using the worker's resources

# The worker execution looks something like this (simplified):
def execute_training_worker(task_config_cid):
    # Get task configuration from IPFS
    task_config = kit_worker.ipfs.cat(task_config_cid)
    
    # Load model and dataset
    model = kit_worker.model_registry.get_model(task_config["model_name"])
    dataset = kit_worker.dataset_manager.get_dataset(task_config["dataset_name"])
    
    # Create data loader
    dataloader = kit_worker.ipfs_dataloader(
        task_config["dataset_cid"],
        batch_size=task_config["training_config"]["batch_size"]
    )
    
    # Train the model
    for epoch in range(task_config["training_config"]["epochs"]):
        for batch in dataloader:
            # Training steps...
            pass
    
    # Save trained model to IPFS
    result = kit_worker.model_registry.add_model(
        model,
        task_config["model_name"],
        version=f"worker-{kit_worker.get_node_id()}"
    )
    
    # Report result to master
    return {
        "task_id": task_config["task_id"],
        "worker_id": kit_worker.get_node_id(),
        "model_cid": result["cid"],
        "metrics": {"accuracy": 0.92}  # Example metrics
    }
```

### Aggregation Methods

The distributed training system supports different methods for aggregating results from workers:

1. **Best Model Selection**: Choose the model with the best performance metrics
2. **Model Averaging**: Average model parameters across workers (for compatible models)
3. **Ensembling**: Create an ensemble of models from different workers
4. **Incremental Learning**: Apply updates sequentially from each worker

The default method is Best Model Selection, but this can be configured in the training parameters.

## Integration with Knowledge Graphs

For advanced scenarios, the AI/ML components can be combined with the IPLD Knowledge Graph system from IPFS Kit to create powerful knowledge management systems with AI capabilities.

```python
# Assuming 'kit' has both AI/ML and Knowledge Graph components enabled

# Create a knowledge graph
graph = kit.ipld_knowledge_graph()

# Add documents from IPFS to knowledge graph with AI-generated features
document_cid = "QmYourDocumentCID"
document = kit.ipfs.cat(document_cid)

# Process with AI to extract entities and relationships
entities = kit.ai_ml_integration.extract_entities(document)
for entity in entities:
    # Add to knowledge graph
    graph.add_entity(entity["id"], entity["properties"])

# Link entities with relationships
for entity in entities:
    for relation in entity.get("relations", []):
        graph.add_relationship(
            entity["id"],
            relation["target"],
            relation["type"],
            relation["properties"]
        )

# Generate embeddings for entities
embeddings = kit.ai_ml_integration.generate_embeddings(
    [entity["properties"]["text"] for entity in entities]
)

# Store embeddings in knowledge graph
for i, entity in enumerate(entities):
    graph.update_entity(entity["id"], {"embedding": embeddings[i]})

# Now you can perform hybrid search using both graph traversal and vector similarity
results = graph.graph_vector_search(
    query_vector=kit.ai_ml_integration.generate_embeddings(["query text"])[0],
    hop_count=2,
    top_k=5
)

print("Search results:")
for result in results:
    print(f"Entity: {result['entity_id']}, Score: {result['score']}")
    print(f"Path: {' -> '.join(result['path'])}")
```

This integration demonstrates the power of combining IPFS content addressing, knowledge graphs, and AI/ML capabilities into a unified system.

## Best Practices and Optimization

### Performance Optimization

1. **Caching**: Use tiered caching for frequently accessed models and datasets
   ```python
   kit = ipfs_kit(metadata={
       "enable_ai_ml": True,
       "cache_config": {
           "memory_cache_size": 1024 * 1024 * 1024,  # 1GB
           "disk_cache_path": "/path/to/cache"
       }
   })
   ```

2. **Prefetching**: Increase the prefetch value for datasets to reduce waiting
   ```python
   loader = kit.ipfs_dataloader(prefetch=5)  # Prefetch 5 batches
   ```

3. **Compression**: Enable compression for large models and datasets
   ```python
   kit.model_registry.add_model(model, compression="zstd")
   ```

4. **Pinning Strategy**: Pin frequently used models and datasets on local nodes
   ```python
   kit.ipfs.pin_add(model_cid)
   ```

### Distributed Workflow Tips

1. **Data Sharding**: For large datasets, shard data and distribute across workers
   ```python
   shards = kit.dataset_manager.create_shards(dataset_cid, num_shards=10)
   ```

2. **Checkpoint Frequency**: Store frequent checkpoints during distributed training
   ```python
   # In training loop
   if step % 100 == 0:
       checkpoint_cid = kit.model_registry.add_checkpoint(model)
   ```

3. **Worker Selection**: Choose workers with appropriate resources for tasks
   ```python
   gpu_workers = kit.cluster_manager.get_workers(resources={"gpu": True})
   ```

4. **Fallback Strategies**: Implement fallback for worker failures
   ```python
   kit.distributed_training.prepare_distributed_task(
       model_name="MyModel",
       fallback_strategy="reassign",  # Reassign tasks from failed workers
       max_retries=3
   )
   ```

### Content Organization

1. **Tagging System**: Use consistent tags for models and datasets
   ```python
   kit.model_registry.add_model(model, metadata={
       "tags": ["vision", "classification", "resnet"]
   })
   ```

2. **Version Strategy**: Use semantic versioning for models and datasets
   ```python
   # Major updates (incompatible changes)
   kit.model_registry.add_model(model, version="2.0.0")
   
   # Minor updates (new features, backwards compatible)
   kit.model_registry.add_model(model, version="1.1.0")
   
   # Patch updates (bug fixes, performance improvements)
   kit.model_registry.add_model(model, version="1.0.1")
   ```

3. **Consistent Metadata**: Use standardized metadata fields across models
   ```python
   standard_fields = [
       "description", "input_shape", "output_shape", 
       "framework", "tags", "metrics", "training_dataset"
   ]
   ```

## Limitations and Considerations

1. **Large Model Support**: Models exceeding several GB may require special handling with chunking
2. **Framework Dependencies**: Each ML framework must be installed separately
3. **Distributed Training Overhead**: Communication between nodes adds overhead for small models
4. **Storage Requirements**: Content-addressed storage can consume more space due to versioning
5. **LLM API Dependencies**: Langchain/LlamaIndex integrations often require external API keys

## Related Documentation

- [IPFS DataLoader Documentation](ipfs_dataloader.md) - Detailed guide for the data loading component
- [Cluster Management](cluster_management.md) - Information about the cluster architecture used by distributed training
- [Knowledge Graph](knowledge_graph.md) - Documentation for the IPLD knowledge graph system that can be integrated with AI/ML
- [Tiered Cache System](tiered_cache.md) - Details about the caching system used by AI/ML components

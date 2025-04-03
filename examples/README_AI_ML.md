# IPFS Kit AI/ML Integration Examples

This directory contains examples demonstrating the integration of IPFS Kit with AI and machine learning workflows.

## High-Level API AI/ML Example

The `high_level_api_ai_ml_example.py` script showcases how to use the IPFS Kit high-level API for a variety of AI/ML tasks. The example demonstrates:

1. **Dataset Management**: Upload, register, and track ML datasets in IPFS
2. **Model Registry**: Store, version, and retrieve ML models with metadata
3. **LangChain Integration**: Connect LangChain with IPFS for document loading and vector stores
4. **LlamaIndex Integration**: Use LlamaIndex with IPFS for document indexing and retrieval
5. **Distributed Training**: Run model training across multiple nodes in an IPFS cluster
6. **Model Deployment**: Deploy models to inference endpoints
7. **Vector Search**: Perform semantic search using vector embeddings
8. **Knowledge Graph**: Create and query knowledge graphs stored in IPFS

## Running the Examples

To run the AI/ML examples:

```bash
# Make sure you're in the root directory of the project
cd ipfs_kit_py

# Install required dependencies
pip install -e .

# Run the high-level API AI/ML example
python examples/high_level_api_ai_ml_example.py
```

## Optional Dependencies

The examples will work with basic functionality even without additional packages, but for full functionality, install:

```bash
pip install langchain llama-index torch tensorflow scikit-learn faiss-cpu
```

## Example Workflows

### Dataset Management Workflow

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

# Add dataset to IPFS
dataset_result = api.add("path/to/dataset.csv")
dataset_cid = dataset_result["cid"]

# Register dataset with metadata
metadata = {
    "name": "Example Dataset",
    "description": "A dataset for classification",
    "features": ["feature1", "feature2", "feature3"],
    "target": "target",
    "rows": 1000,
    "columns": 4
}
register_result = api.ai_register_dataset(dataset_cid, metadata)

# Create data loader
loader_result = api.ai_data_loader(dataset_cid, batch_size=32, shuffle=True)
```

### Model Registry Workflow

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

# Add model to IPFS
model_result = api.add("path/to/model.pkl")
model_cid = model_result["cid"]

# Register model with metadata
metadata = {
    "name": "Example Model",
    "version": "1.0.0",
    "framework": "scikit-learn",
    "metrics": {
        "accuracy": 0.85,
        "f1_score": 0.83
    }
}
register_result = api.ai_register_model(model_cid, metadata)

# List models
models_result = api.ai_list_models()
```

### Distributed Training Workflow

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

# Define training task
training_task = {
    "task_type": "model_training",
    "model_type": "neural_network",
    "hyperparameters": {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 10
    },
    "dataset_cid": "QmExampleDatasetCID",
    "framework": "pytorch"
}

# Submit training job
submit_result = api.ai_distributed_training_submit_job(
    training_task=training_task,
    worker_count=3,
    priority=2
)

# Get job status
job_id = submit_result["job_id"]
status_result = api.ai_distributed_training_get_status(job_id)

# Aggregate results
aggregate_result = api.ai_distributed_training_aggregate_results(job_id)
```

### Knowledge Graph Workflow

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

# Create knowledge graph
graph_result = api.ai_create_knowledge_graph(
    entities_cid="QmEntitiesCID",
    relationships_cid="QmRelationshipsCID",
    graph_name="Example Graph"
)

# Query the graph
query_result = api.ai_query_knowledge_graph(
    graph_cid=graph_result["graph_cid"],
    query="MATCH (p:Person)-[r:WORKS_FOR]->(c:Company) RETURN p, r, c",
    query_type="cypher"
)
```

## Integration with AI Frameworks

These examples showcase IPFS Kit's integration with popular AI frameworks:

1. **PyTorch**: Load datasets and models directly from IPFS
2. **TensorFlow**: Integrate IPFS content with TensorFlow datasets
3. **Langchain**: Create document loaders and vector stores backed by IPFS
4. **LlamaIndex**: Build indexes from IPFS-stored documents
5. **Scikit-learn**: Store and load scikit-learn models with versioning

## Benefits of IPFS for AI/ML

- **Content Addressing**: Models and datasets are uniquely identified by their content hash
- **Deduplication**: Identical data is stored only once, saving storage space
- **Versioning**: Natural versioning of models and datasets through content addressing
- **Distribution**: Peer-to-peer distribution of large models and datasets
- **Persistence**: Pinning ensures important models and datasets remain available
- **Metadata**: Rich metadata for models and datasets stored on IPFS
- **Immutability**: Content cannot be modified, ensuring reproducibility

## Additional Resources

- [AI/ML Integration Documentation](../docs/ai_ml_integration.md)
- [High-Level API Documentation](../docs/high_level_api.md)
- [Performance Metrics](../docs/performance_metrics.md)
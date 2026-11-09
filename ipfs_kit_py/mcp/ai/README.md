# AI/ML Integration Package for MCP Server

This package implements AI/ML capabilities for the MCP server as described in Phase 2 of the MCP Roadmap (Q4 2025).

## Overview

The AI/ML integration package provides comprehensive machine learning capabilities including model management, dataset handling, distributed training, and framework integrations. These components enable efficient ML workflows from data preparation to model deployment.

## Components

### Implemented

- **AI/ML Integrator**: The core integration point that coordinates all AI/ML components and provides a unified API interface.
- **Dataset Manager**: Comprehensive dataset management with version control, metadata tracking, and dataset lineage.
- **Async Streaming**: Asynchronous streaming capabilities for efficient data transfer in ML workflows.

### In Progress

- **Model Registry**: Version-controlled model storage with metadata management and performance tracking.
- **Distributed Training**: Job orchestration for model training across multiple nodes with hyperparameter optimization.
- **Framework Integration**: Integrations with popular ML frameworks like LangChain, LlamaIndex, and HuggingFace.

## Usage

### Dataset Management

```python
from ipfs_kit_py.mcp.ai.dataset_manager import get_instance as get_dataset_manager

# Get dataset manager instance
dataset_manager = get_dataset_manager()

# Create a new dataset
dataset = dataset_manager.create_dataset(
    name="my-dataset",
    description="Sample dataset for image classification",
    domain="computer_vision",
    tags=["images", "classification"]
)

# Add a version to the dataset
version = dataset_manager.create_dataset_version(
    dataset_id=dataset.id,
    description="Initial version",
    version="1.0.0",
    files=[
        {
            "name": "train.csv",
            "path": "/path/to/train.csv",
            "format": "csv",
            "split": "train",
            "size_bytes": 1024000
        }
    ],
    schema={"features": ["image_path", "label"]}
)

# List all datasets
datasets = dataset_manager.list_datasets()
```

### AI/ML Integration

```python
from ipfs_kit_py.mcp.ai.ai_ml_integrator import get_instance as get_ai_ml_integrator

# Get integrator instance
integrator = get_ai_ml_integrator()

# Initialize components
integrator.initialize()

# Register with MCP server
integrator.register_with_server(mcp_server, prefix="/ai")
```

## API Endpoints

Once registered with an MCP server, the following endpoints become available:

### Dataset Endpoints

- `GET /ai/datasets` - List available datasets
- `GET /ai/datasets/{dataset_id}` - Get dataset details
- `POST /ai/datasets` - Create a new dataset
- `GET /ai/datasets/{dataset_id}/versions` - List dataset versions
- `POST /ai/datasets/{dataset_id}/versions` - Create a new dataset version

### Model Endpoints (Coming Soon)

- `GET /ai/models` - List available models
- `GET /ai/models/{model_id}` - Get model details
- `POST /ai/models` - Create a new model
- `GET /ai/models/{model_id}/versions` - List model versions
- `POST /ai/models/{model_id}/versions` - Create a new model version

### Training Endpoints (Coming Soon)

- `GET /ai/jobs` - List training jobs
- `POST /ai/jobs` - Create a new training job
- `GET /ai/jobs/{job_id}` - Get job details
- `POST /ai/jobs/{job_id}/start` - Start a training job
- `POST /ai/jobs/{job_id}/stop` - Stop a training job

## Future Development

The following features are planned for future development:

1. **Model Registry Completion**:
   - Model versioning and lineage tracking
   - Performance metrics storage
   - Artifact management
   - Deployment configuration

2. **Distributed Training Implementation**:
   - Job queuing and scheduling
   - Resource allocation
   - Checkpointing and resumption
   - Multi-node coordination

3. **Framework Integrations**:
   - LangChain integration for LLM workflows
   - LlamaIndex integration for data indexing
   - HuggingFace integration for model hosting
   - PyTorch/TensorFlow integration

4. **Advanced Features**:
   - Automated ML (AutoML)
   - Feature store integration
   - Experiment tracking
   - Model explainability

## Requirements

- Python 3.9+
- FastAPI (for API endpoints)
- Pydantic (for data validation)
- Optional: PyTorch/TensorFlow (for model training)
- Optional: Sentence Transformers (for vector embeddings)
- Optional: LangChain/LlamaIndex (for LLM workflows)

## Contributing

Contributions are welcome! Please see the main project documentation for contribution guidelines.

# AI/ML Integration for MCP Server

This directory contains the AI/ML integration components for the MCP Server, which provide comprehensive machine learning lifecycle management capabilities.

## Overview

The MCP AI/ML integration provides a complete ecosystem for managing machine learning workflows:

1. **Model Registry** - Version-controlled storage for ML models with metadata tracking
2. **Dataset Management** - Versioning, preprocessing, and quality metrics for ML datasets
3. **Distributed Training** - Orchestration for model training across multiple nodes
4. **Framework Integration** - Seamless connectivity with popular AI tools and services

These components work together to provide a comprehensive platform for machine learning operations (MLOps) that integrates with the distributed storage capabilities of the IPFS Kit Python library.

## Components

### Model Registry (`model_registry.py`)

The Model Registry provides:
- Model versioning with metadata tracking
- Multiple storage backends (File System, S3, IPFS)
- Performance metrics tracking
- Artifact management
- Model lineage tracking
- Framework-agnostic design
- Custom metadata and tagging system

Example usage can be found in `examples/model_registry_example.py`.

### Dataset Management (`dataset_manager.py`)

The Dataset Management system offers:
- Version-controlled dataset storage
- Dataset preprocessing pipelines
- Data quality metrics and validation
- Dataset lineage tracking
- Multiple storage backends (File System, S3, IPFS)
- Support for various data formats (CSV, JSON, Image, Text, etc.)
- Split management (train/validation/test)

Example usage can be found in `examples/dataset_manager_example.py`.

### Distributed Training (`distributed_training.py`)

The Distributed Training system provides:
- Training job orchestration
- Multi-node training support
- Hyperparameter optimization
- Model checkpointing and resumption
- Training metrics collection and monitoring
- Support for various ML frameworks (PyTorch, TensorFlow, etc.)
- Integration with model registry and dataset management

Example usage can be found in `examples/distributed_training_example.py`.

### Framework Integration (`framework_integration.py`)

The Framework Integration module offers:
- LangChain integration for LLM workflows and agents
- LlamaIndex integration for data indexing and retrieval
- HuggingFace integration for model hosting and inference
- Custom model serving for specialized deployments
- Model endpoint management with monitoring
- Framework-agnostic design with flexible configuration
- Integration with model registry and dataset manager

## Getting Started

### Prerequisites

The AI/ML integration has the following core dependencies:
- Python 3.8+
- IPFS Kit Python Library

Each component may have additional optional dependencies:
- Model Registry: None
- Dataset Management: `pandas`, `PIL`, `pyarrow`
- Distributed Training: `numpy`, `ray`, `torch`, `tensorflow`
- Framework Integration: `langchain`, `llama-index`, `huggingface-hub`, `transformers`

### Installation

The AI/ML components are included with the IPFS Kit Python Library. You can install optional dependencies based on your needs:

```bash
# Install basic IPFS Kit
pip install ipfs-kit-py

# Install with ML capabilities
pip install ipfs-kit-py[ml]

# Install with all AI/ML dependencies
pip install ipfs-kit-py[ml-full]
```

### Basic Usage

Here's a simple example of using the model registry to store a model:

```python
from ipfs_kit_py.mcp.ai.model_registry import ModelRegistry, Model, ModelVersion, ModelFramework

# Create a model registry
registry = ModelRegistry()

# Create a model
model = Model(
    id="my-model",
    name="My Model",
    description="A sample model",
    framework=ModelFramework.PYTORCH
)
registry.save_model(model)

# Create a version for the model
version = ModelVersion(
    id="v1",
    model_id=model.id,
    version="1.0.0",
    description="Initial version"
)
registry.save_model_version(version)

# Store model files
registry.add_model_file(model.id, version.id, "model.pt", "path/to/model.pt")
```

## Integration with MCP Server

The AI/ML components can be integrated with the MCP Server to provide a complete solution for distributed AI/ML workflows. The MCP Server provides REST API endpoints for interacting with the AI/ML components.

## Documentation

For detailed documentation on each component, refer to the docstrings in the respective module files:
- Model Registry: `model_registry.py`
- Dataset Management: `dataset_manager.py`
- Distributed Training: `distributed_training.py`
- Framework Integration: `framework_integration.py`

## Contributing

Contributions to the AI/ML integration are welcome. Please follow the project's contributing guidelines and ensure that all tests pass before submitting a pull request.

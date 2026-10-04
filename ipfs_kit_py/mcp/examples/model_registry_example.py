#!/usr/bin/env python3
"""
Model Registry Example for MCP Server

This example demonstrates how to use the Model Registry module to manage
machine learning models, their versions, and artifacts. It shows the core
functionality of the registry:

1. Creating and managing models
2. Versioning models and tracking lineage
3. Storing and retrieving model artifacts
4. Tracking model performance metrics

Usage:
  python model_registry_example.py [--ipfs] [--s3]
"""

import os
import sys
import tempfile
import argparse
import logging
import json
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("model-registry-example")

# Import model registry components
try:
    from ipfs_kit_py.mcp.ai.model_registry import (
        ModelRegistry,
        Model,
        ModelVersion,
        ModelMetrics,
        ModelArtifact,
        ModelFramework,
        ModelStatus,
        ArtifactType,
        JSONFileMetadataStore,
        FileSystemModelStorage,
        IPFSModelStorage,
        S3ModelStorage
    )
except ImportError:
    logger.error("Failed to import model registry modules. Make sure ipfs_kit_py is installed")
    sys.exit(1)

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def create_dummy_model_files(base_dir: str) -> Dict[str, str]:
    """Create dummy model files for the example."""
    # Create temporary files
    files = {}
    
    # Model weights file (random numpy array)
    weights_path = os.path.join(base_dir, "model_weights.npy")
    weights = np.random.randn(10, 10).astype(np.float32)
    np.save(weights_path, weights)
    files["weights"] = weights_path
    
    # Model config file (JSON)
    config_path = os.path.join(base_dir, "config.json")
    config = {
        "layers": [10, 20, 10],
        "activation": "relu",
        "dropout": 0.2,
        "learning_rate": 0.001
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    files["config"] = config_path
    
    # Model documentation (Markdown)
    docs_path = os.path.join(base_dir, "documentation.md")
    with open(docs_path, "w") as f:
        f.write("# Example Model\n\n")
        f.write("This is a dummy model for demonstration purposes.\n\n")
        f.write("## Architecture\n\n")
        f.write("- Input dimension: 10\n")
        f.write("- Hidden layers: 20 units\n")
        f.write("- Output dimension: 10\n")
        f.write("- Activation function: ReLU\n")
        f.write("- Dropout rate: 0.2\n")
    files["docs"] = docs_path
    
    # Sample data
    sample_path = os.path.join(base_dir, "sample_data.npy")
    sample_data = np.random.randn(5, 10).astype(np.float32)
    np.save(sample_path, sample_data)
    files["sample"] = sample_path
    
    logger.info(f"Created dummy model files in {base_dir}")
    return files

def demonstrate_basic_usage(registry_dir: str, storage_type: str = "fs"):
    """Demonstrate basic model registry usage."""
    logger.info("=== Basic Model Registry Usage Demonstration ===")
    
    # Set up model registry
    if storage_type == "ipfs":
        try:
            # Try to import ipfs_client
            from ipfs_kit_py.ipfs_client import IPFSClient
            ipfs_client = IPFSClient()
            model_storage = IPFSModelStorage(ipfs_client)
            logger.info("Using IPFS storage backend")
        except ImportError:
            logger.warning("IPFS client not available, falling back to file system storage")
            storage_type = "fs"
    
    if storage_type == "s3":
        try:
            # This is just for demonstration - in a real app, you would use actual credentials
            bucket_name = "example-models"
            model_storage = S3ModelStorage(bucket_name)
            logger.info(f"Using S3 storage backend with bucket: {bucket_name}")
        except Exception as e:
            logger.warning(f"S3 storage setup failed: {e}, falling back to file system storage")
            storage_type = "fs"
    
    if storage_type == "fs":
        storage_dir = os.path.join(registry_dir, "storage")
        model_storage = FileSystemModelStorage(storage_dir)
        logger.info(f"Using file system storage backend at: {storage_dir}")
    
    # Set up metadata store
    metadata_dir = os.path.join(registry_dir, "metadata")
    metadata_store = JSONFileMetadataStore(metadata_dir)
    
    # Create model registry
    registry = ModelRegistry(
        metadata_store=metadata_store,
        model_storage=model_storage
    )
    logger.info("Model registry initialized")
    
    # --------------------------
    # Step 1: Create a model
    # --------------------------
    model = registry.create_model(
        name="Example Neural Network",
        description="A simple neural network for demonstration purposes",
        owner="MCP Team",
        team="AI Research",
        project="Model Registry Demo",
        task_type="classification",
        tags=["demo", "neural-network", "pytorch"]
    )
    logger.info(f"Created model: {model.id} - {model.name}")
    
    # --------------------------
    # Step 2: Create a model version
    # --------------------------
    version = registry.create_model_version(
        model_id=model.id,
        version="v1",
        name="Initial version",
        description="First version of the example neural network",
        framework=ModelFramework.PYTORCH,
        framework_version="2.0.0",
        tags=["initial", "baseline"]
    )
    logger.info(f"Created model version: {version.id} - {version.version}")
    
    # --------------------------
    # Step 3: Add model artifacts
    # --------------------------
    # Create temporary directory for dummy files
    temp_dir = tempfile.mkdtemp()
    try:
        # Create dummy model files
        files = create_dummy_model_files(temp_dir)
        
        # Add model weights
        weights_artifact = registry.add_model_artifact(
            model_id=model.id,
            version_id=version.id,
            file_path=files["weights"],
            artifact_type=ArtifactType.MODEL_WEIGHTS,
            name="model_weights.npy",
            description="Neural network weights"
        )
        logger.info(f"Added weights artifact: {weights_artifact.id}")
        
        # Add model config
        config_artifact = registry.add_model_artifact(
            model_id=model.id,
            version_id=version.id,
            file_path=files["config"],
            artifact_type=ArtifactType.CONFIG,
            name="config.json",
            description="Model configuration"
        )
        logger.info(f"Added config artifact: {config_artifact.id}")
        
        # Add documentation
        docs_artifact = registry.add_model_artifact(
            model_id=model.id,
            version_id=version.id,
            file_path=files["docs"],
            artifact_type=ArtifactType.DOCUMENTATION,
            name="documentation.md",
            description="Model documentation"
        )
        logger.info(f"Added documentation artifact: {docs_artifact.id}")
        
        # Add sample data
        sample_artifact = registry.add_model_artifact(
            model_id=model.id,
            version_id=version.id,
            file_path=files["sample"],
            artifact_type=ArtifactType.SAMPLE_DATA,
            name="sample_data.npy",
            description="Sample input data"
        )
        logger.info(f"Added sample data artifact: {sample_artifact.id}")
    finally:
        # Clean up temporary files
        shutil.rmtree(temp_dir)
    
    # --------------------------
    # Step 4: Update model with metrics
    # --------------------------
    metrics = ModelMetrics(
        accuracy=0.92,
        precision=0.89,
        recall=0.94,
        f1_score=0.91,
        auc_roc=0.95,
        inference_time_ms=15.3,
        evaluation_dataset="mnist_test",
        evaluation_dataset_version="1.0",
        evaluation_split="test",
        evaluation_timestamp=datetime.utcnow().isoformat()
    )
    
    updated_version = registry.update_model_version(
        model_id=model.id,
        version_id=version.id,
        metrics=metrics,
        status=ModelStatus.STAGING  # Move from DRAFT to STAGING
    )
    logger.info(f"Updated model version with metrics: {updated_version.id}")
    logger.info(f"  Accuracy: {updated_version.metrics.accuracy}")
    logger.info(f"  Status: {updated_version.status}")
    
    # --------------------------
    # Step 5: Create a second version
    # --------------------------
    version2 = registry.create_model_version(
        model_id=model.id,
        version="v2",
        name="Improved version",
        description="Improved version with better accuracy",
        framework=ModelFramework.PYTORCH,
        framework_version="2.0.0",
        parent_version=version.id,  # Track lineage
        tags=["improved", "tuned"]
    )
    logger.info(f"Created second model version: {version2.id} - {version2.version}")
    logger.info(f"  Parent version: {version2.parent_version}")
    
    # --------------------------
    # Step 6: List models and versions
    # --------------------------
    models = registry.list_models()
    logger.info(f"Models in registry: {len(models)}")
    for m in models:
        logger.info(f"  {m.id} - {m.name}")
        
        # List versions for this model
        versions = registry.list_model_versions(m.id)
        logger.info(f"  Versions: {len(versions)}")
        for v in versions:
            logger.info(f"    {v.id} - {v.version} - {v.status}")
            logger.info(f"    Artifacts: {len(v.artifacts)}")
    
    # --------------------------
    # Step 7: Promote v1 to production
    # --------------------------
    registry.update_model_version(
        model_id=model.id,
        version_id=version.id,
        status=ModelStatus.PRODUCTION
    )
    logger.info(f"Promoted version {version.id} to PRODUCTION")
    
    # Verify that model.production_version was updated
    updated_model = registry.get_model(model.id)
    logger.info(f"Model production version: {updated_model.production_version}")
    
    # --------------------------
    # Step 8: Download and use an artifact
    # --------------------------
    # Get the weights artifact
    weights_artifact = None
    for artifact in updated_version.artifacts:
        if artifact.type == ArtifactType.MODEL_WEIGHTS:
            weights_artifact = artifact
            break
    
    if weights_artifact:
        # Get the content of the artifact
        artifact_content = registry.get_artifact_content(
            model_id=model.id,
            version_id=version.id,
            artifact_id=weights_artifact.id
        )
        
        # Save to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".npy")
        try:
            # Write the content to the file
            temp_file.write(artifact_content.read())
            temp_file.close()
            
            # Load the weights
            loaded_weights = np.load(temp_file.name)
            logger.info(f"Successfully loaded weights from artifact:")
            logger.info(f"  Shape: {loaded_weights.shape}")
            logger.info(f"  Type: {loaded_weights.dtype}")
        finally:
            # Clean up
            os.unlink(temp_file.name)
    
    logger.info("\nBasic Model Registry demonstration completed successfully!")


def demonstrate_advanced_usage(registry_dir: str):
    """Demonstrate more advanced model registry usage."""
    logger.info("\n=== Advanced Model Registry Usage Demonstration ===")
    
    # Set up model registry with file system storage
    storage_dir = os.path.join(registry_dir, "storage")
    metadata_dir = os.path.join(registry_dir, "metadata")
    
    model_storage = FileSystemModelStorage(storage_dir)
    metadata_store = JSONFileMetadataStore(metadata_dir)
    
    registry = ModelRegistry(
        metadata_store=metadata_store,
        model_storage=model_storage
    )
    
    # --------------------------
    # Create multiple models for different tasks
    # --------------------------
    # Create an NLP model
    nlp_model = registry.create_model(
        name="Text Classification Model",
        description="A model for classifying text into predefined categories",
        task_type="text-classification",
        tags=["nlp", "classification", "transformer"]
    )
    
    # Create a computer vision model
    cv_model = registry.create_model(
        name="Image Segmentation Model",
        description="A model for segmenting images into different objects",
        task_type="image-segmentation",
        tags=["computer-vision", "segmentation", "cnn"]
    )
    
    # Create a time series model
    ts_model = registry.create_model(
        name="Time Series Forecasting Model",
        description="A model for forecasting time series data",
        task_type="forecasting",
        tags=["time-series", "forecasting", "lstm"]
    )
    
    logger.info("Created multiple models for different tasks:")
    logger.info(f"  NLP Model: {nlp_model.id} - {nlp_model.name}")
    logger.info(f"  CV Model: {cv_model.id} - {cv_model.name}")
    logger.info(f"  TS Model: {ts_model.id} - {ts_model.name}")
    
    # --------------------------
    # Create multiple versions with different frameworks
    # --------------------------
    # Create a PyTorch version of the NLP model
    nlp_v1 = registry.create_model_version(
        model_id=nlp_model.id,
        version="v1",
        name="PyTorch Implementation",
        framework=ModelFramework.PYTORCH,
        framework_version="2.0.0"
    )
    
    # Create a TensorFlow version of the NLP model
    nlp_v2 = registry.create_model_version(
        model_id=nlp_model.id,
        version="v2",
        name="TensorFlow Implementation",
        framework=ModelFramework.TENSORFLOW,
        framework_version="2.10.0"
    )
    
    # Create an ONNX version exported from the PyTorch version
    nlp_v3 = registry.create_model_version(
        model_id=nlp_model.id,
        version="v3",
        name="ONNX Export",
        framework=ModelFramework.ONNX,
        framework_version="1.12.0",
        parent_version=nlp_v1.id  # Track lineage from PyTorch version
    )
    
    logger.info(f"Created multiple versions of the NLP model with different frameworks:")
    logger.info(f"  v1: {nlp_v1.id} - {nlp_v1.framework}")
    logger.info(f"  v2: {nlp_v2.id} - {nlp_v2.framework}")
    logger.info(f"  v3: {nlp_v3.id} - {nlp_v3.framework} (derived from v1)")
    
    # --------------------------
    # Add metrics for comparing versions
    # --------------------------
    # Metrics for PyTorch version
    registry.update_model_version(
        model_id=nlp_model.id,
        version_id=nlp_v1.id,
        metrics=ModelMetrics(
            accuracy=0.91,
            f1_score=0.90,
            inference_time_ms=25.3,
            memory_usage_mb=850
        )
    )
    
    # Metrics for TensorFlow version
    registry.update_model_version(
        model_id=nlp_model.id,
        version_id=nlp_v2.id,
        metrics=ModelMetrics(
            accuracy=0.92,
            f1_score=0.91,
            inference_time_ms=28.7,
            memory_usage_mb=950
        )
    )
    
    # Metrics for ONNX version
    registry.update_model_version(
        model_id=nlp_model.id,
        version_id=nlp_v3.id,
        metrics=ModelMetrics(
            accuracy=0.91,  # Same as PyTorch since it's exported from it
            f1_score=0.90,
            inference_time_ms=12.1,  # Faster inference
            memory_usage_mb=580  # Lower memory usage
        )
    )
    
    logger.info("Added performance metrics for all NLP model versions")
    
    # --------------------------
    # Compare model versions
    # --------------------------
    logger.info("\nComparing NLP model versions:")
    versions = registry.list_model_versions(nlp_model.id)
    
    # Create a comparison table
    logger.info("Framework    | Accuracy | F1 Score | Inference Time | Memory Usage")
    logger.info("-------------|----------|----------|----------------|-------------")
    for v in versions:
        metrics = v.metrics
        if metrics:
            logger.info(f"{v.framework.value:<13} | {metrics.accuracy:.2f}     | {metrics.f1_score:.2f}     | {metrics.inference_time_ms:>14.1f}ms | {metrics.memory_usage_mb:>11}MB")
    
    # --------------------------
    # Search and filter models
    # --------------------------
    logger.info("\nSearching and filtering models:")
    
    # Get all models with a specific tag
    cv_models = registry.list_models(filters={"task_type": "image-segmentation"})
    logger.info(f"Found {len(cv_models)} computer vision models")
    
    # Get all versions with specific framework
    pytorch_versions = registry.list_model_versions(
        nlp_model.id,
        filters={"framework": ModelFramework.PYTORCH}
    )
    logger.info(f"Found {len(pytorch_versions)} PyTorch versions of the NLP model")
    
    # --------------------------
    # Promote the best version to production
    # --------------------------
    # Find the version with the best inference time
    best_version = None
    best_inference_time = float('inf')
    
    for v in versions:
        metrics = v.metrics
        if metrics and metrics.inference_time_ms < best_inference_time:
            best_inference_time = metrics.inference_time_ms
            best_version = v
    
    if best_version:
        # Promote to production
        registry.update_model_version(
            model_id=nlp_model.id,
            version_id=best_version.id,
            status=ModelStatus.PRODUCTION
        )
        logger.info(f"Promoted {best_version.framework} version (v{best_version.version}) to production")
        logger.info(f"  This version has the best inference time: {best_inference_time:.1f}ms")
    
    logger.info("\nAdvanced Model Registry demonstration completed successfully!")


def run_examples():
    """Run all the examples."""
    parser = argparse.ArgumentParser(description="Model Registry Examples")
    parser.add_argument("--ipfs", action="store_true", help="Use IPFS storage backend")
    parser.add_argument("--s3", action="store_true", help="Use S3 storage backend")
    args = parser.parse_args()
    
    # Create a temporary directory for the example
    registry_dir = tempfile.mkdtemp()
    try:
        logger.info(f"Using temporary directory: {registry_dir}")
        
        # Determine storage type
        storage_type = "fs"  # Default to file system
        if args.ipfs:
            storage_type = "ipfs"
        elif args.s3:
            storage_type = "s3"
        
        # Run the examples
        demonstrate_basic_usage(registry_dir, storage_type)
        demonstrate_advanced_usage(registry_dir)
        
        logger.info("\nModel Registry examples completed successfully!")
    finally:
        # Clean up
        logger.info(f"Cleaning up: {registry_dir}")
        shutil.rmtree(registry_dir)


if __name__ == "__main__":
    run_examples()

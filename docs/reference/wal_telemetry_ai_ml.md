# WAL Telemetry AI/ML Integration

This documentation explains how to use the WAL (Write-Ahead Log) telemetry system with AI/ML operations in IPFS Kit.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Key Features](#key-features)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Telemetry Categories](#telemetry-categories)
- [Prometheus Integration](#prometheus-integration)
- [Distributed Tracing](#distributed-tracing)
- [Use Cases](#use-cases)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The WAL telemetry AI/ML integration extends the core WAL telemetry system with specialized metrics collection, distributed tracing, and visualization capabilities for AI/ML operations. It provides comprehensive monitoring of model loading, inference, training, and distributed operations within IPFS Kit.

This integration enables:
- Detailed tracking of model operations with latency, throughput, and memory metrics
- Training progress monitoring with loss, learning rate, and gradient tracking
- Dataset loading and preprocessing performance measurements
- Distributed training coordination and worker utilization insights
- Advanced tracing for tracking operations across system boundaries

The system integrates with both the base WAL telemetry system and the existing AI/ML metrics module to provide a comprehensive observability solution.

## Installation

The WAL telemetry AI/ML integration is included in the IPFS Kit package. To use it, you need to ensure you have the following optional dependencies installed:

```bash
# Basic telemetry dependencies
pip install prometheus-client opentelemetry-api opentelemetry-sdk

# AI/ML visualization dependencies (optional)
pip install matplotlib plotly

# Metrics server dependencies (optional)
pip install fastapi uvicorn
```

## Key Features

### 1. Model Performance Tracking

- **Model Loading**: Track model loading times, sizes, and framework information
- **Model Initialization**: Monitor device placement and initialization overhead
- **Inference**: Measure inference latency, throughput, and memory usage
- **Batch Processing**: Evaluate performance across different batch sizes

### 2. Training Metrics Collection

- **Epoch Tracking**: Measure epoch duration and samples processed per second
- **Loss Monitoring**: Track loss values and convergence rates over time
- **Hyperparameter Tracking**: Record learning rates and gradient norms
- **Resource Utilization**: Monitor GPU/CPU utilization during training

### 3. Dataset Operations

- **Loading Performance**: Measure dataset loading times by format and size
- **Preprocessing**: Track data transformation and normalization overhead
- **Caching Efficiency**: Monitor hitting by datasource with IPFS Kit

### 4. Distributed Training Insights

- **Coordination Overhead**: Measure time spent on worker coordination
- **Task Distribution**: Track task allocation and execution times
- **Worker Utilization**: Monitor worker load balance and resource utilization
- **Result Aggregation**: Measure time spent aggregating results from workers

### 5. Observability Integration

- **Prometheus Integration**: Export AI/ML metrics to Prometheus for dashboarding
- **Distributed Tracing**: Track operations across system boundaries with OpenTelemetry
- **Visualization**: Generate reports and visualizations for AI/ML metrics
- **Context Propagation**: Pass context between components for tracing continuity

## Getting Started

### Basic Setup

To enable WAL telemetry with AI/ML extensions in your application:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.wal_telemetry_api import extend_high_level_api
from ipfs_kit_py.wal_telemetry_ai_ml import extend_high_level_api_with_aiml_telemetry

# Create high-level API instance
api = IPFSSimpleAPI(role="master")

# Extend with WAL telemetry capabilities
api = extend_high_level_api(api)

# Initialize WAL telemetry
api.wal_telemetry(
    enabled=True,
    aggregation_interval=30,  # Aggregate metrics every 30 seconds
    max_history_entries=100   # Keep the last 100 history entries
)

# Extend with AI/ML telemetry capabilities
api = extend_high_level_api_with_aiml_telemetry(api)

# Initialize AI/ML telemetry
api.wal_aiml_telemetry()
```

### Tracking Model Operations

```python
# Track model loading operation
with api.wal_track_model_operation(
    operation_type="model_load",
    model_id="my_model",
    framework="pytorch",
    model_size=50 * 1024 * 1024  # 50MB
):
    # Load your model here
    model = load_model("path/to/model")

# Track model initialization
with api.wal_track_model_operation(
    operation_type="model_init",
    model_id="my_model",
    device="cuda"
):
    # Initialize model on device
    model.to(device)
```

### Tracking Inference

```python
# Track model inference
with api.wal_track_inference(
    model_id="my_model",
    batch_size=32,
    input_type="image"
):
    # Run inference
    outputs = model(inputs)
```

### Tracking Training

```python
# Track training epoch
for epoch in range(num_epochs):
    with api.wal_track_training_epoch(
        model_id="my_model",
        epoch=epoch,
        num_samples=len(train_loader.dataset)
    ):
        # Train for one epoch
        train_one_epoch(model, train_loader, optimizer)
    
    # Record training statistics
    api.wal_record_training_stats(
        model_id="my_model",
        epoch=epoch,
        loss=epoch_loss,
        learning_rate=current_lr,
        gradient_norm=compute_grad_norm(model)
    )
```

### Tracking Dataset Operations

```python
# Track dataset loading
with api.wal_track_dataset_operation(
    operation_type="dataset_load",
    dataset_id="imagenet",
    format="tfrecord",
    dataset_size=150 * 1024 * 1024 * 1024  # 150GB
):
    # Load your dataset
    dataset = load_dataset("path/to/dataset")

# Track dataset preprocessing
with api.wal_track_dataset_operation(
    operation_type="dataset_preprocess",
    dataset_id="imagenet",
    operation="normalize"
):
    # Preprocess the dataset
    preprocessed_dataset = preprocess(dataset)
```

### Tracking Distributed Training

```python
# Track worker coordination
with api.wal_track_distributed_operation(
    operation_type="worker_coordination",
    task_id="training_task_1",
    num_workers=8
):
    # Coordinate workers
    workers = initialize_workers()

# Record worker utilization
for worker_id, utilization in worker_stats.items():
    api.wal_record_worker_utilization(
        worker_id=worker_id,
        utilization=utilization  # 0.0-1.0
    )
```

### Getting Metrics Reports

```python
# Get AI/ML metrics data
metrics_data = api.wal_get_ai_ml_metrics()

# Generate a formatted report
report_result = api.wal_generate_metrics_report(format="markdown")
if report_result["success"]:
    print(report_result["report"])
```

## API Reference

### High-Level API Extension

After calling `extend_high_level_api_with_aiml_telemetry(api)`, the following methods are added to the API:

| Method | Description |
|--------|-------------|
| `api.wal_aiml_telemetry()` | Initialize AI/ML telemetry |
| `api.wal_track_model_operation()` | Track model-related operations |
| `api.wal_track_inference()` | Track inference operations |
| `api.wal_track_training_epoch()` | Track training epoch operations |
| `api.wal_record_training_stats()` | Record training statistics |
| `api.wal_track_dataset_operation()` | Track dataset operations |
| `api.wal_track_distributed_operation()` | Track distributed training operations |
| `api.wal_record_worker_utilization()` | Record worker utilization |
| `api.wal_get_ai_ml_metrics()` | Get AI/ML metrics data |
| `api.wal_generate_metrics_report()` | Generate a formatted metrics report |

### WALTelemetryAIMLExtension Class

The `WALTelemetryAIMLExtension` class provides the core functionality for the AI/ML telemetry integration. It can be instantiated directly if you need more control:

```python
from ipfs_kit_py.wal_telemetry_ai_ml import extend_wal_telemetry

# Create the extension with a base WAL telemetry extension
aiml_extension = extend_wal_telemetry(base_extension)

# Initialize the extension
aiml_extension.initialize()
```

## Telemetry Categories

The WAL telemetry AI/ML integration organizes operations into the following categories:

### 1. Model Operations

| Operation Type | Description |
|----------------|-------------|
| `model_load` | Loading a model from storage |
| `model_init` | Initializing a model on a device |
| `model_save` | Saving a model to storage |

### 2. Inference Operations

| Operation Type | Description |
|----------------|-------------|
| `inference` | Single inference operation |
| `batch_inference` | Batch inference operation |
| `embeddings_generation` | Generating embeddings from inputs |

### 3. Training Operations

| Operation Type | Description |
|----------------|-------------|
| `training_epoch` | Full training epoch |
| `optimizer_step` | Optimizer update step |
| `gradient_update` | Gradient computation and update |

### 4. Dataset Operations

| Operation Type | Description |
|----------------|-------------|
| `dataset_load` | Loading a dataset from storage |
| `dataset_preprocess` | Preprocessing a dataset |
| `dataset_transform` | Applying transformations to a dataset |

### 5. Distributed Operations

| Operation Type | Description |
|----------------|-------------|
| `worker_coordination` | Coordinating worker nodes |
| `result_aggregation` | Aggregating results from workers |
| `task_distribution` | Distributing tasks to workers |

## Prometheus Integration

The WAL telemetry AI/ML integration provides Prometheus metrics for all tracked operations. The following metrics are available:

### Model Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `ipfs_aiml_model_load_seconds` | Histogram | Time taken to load models |
| `ipfs_aiml_model_size_bytes` | Gauge | Size of models in bytes |

### Inference Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `ipfs_aiml_inference_seconds` | Histogram | Inference latency in seconds |
| `ipfs_aiml_inference_throughput` | Gauge | Inference throughput (items/second) |
| `ipfs_aiml_inference_memory_bytes` | Gauge | Memory usage during inference |

### Training Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `ipfs_aiml_training_epoch_seconds` | Histogram | Training epoch time in seconds |
| `ipfs_aiml_training_samples_per_second` | Gauge | Training throughput (samples/second) |
| `ipfs_aiml_training_loss` | Gauge | Training loss value |

### Dataset Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `ipfs_aiml_dataset_load_seconds` | Histogram | Dataset loading time in seconds |
| `ipfs_aiml_dataset_size_bytes` | Gauge | Dataset size in bytes |

### Distributed Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `ipfs_aiml_coordination_overhead_seconds` | Histogram | Coordination overhead in distributed training |
| `ipfs_aiml_worker_utilization_ratio` | Gauge | Worker utilization ratio (0.0-1.0) |

### Operation Counter

| Metric Name | Type | Description |
|-------------|------|-------------|
| `ipfs_aiml_operations_total` | Counter | Total number of AI/ML operations |

## Distributed Tracing

The WAL telemetry AI/ML integration leverages the OpenTelemetry distributed tracing capabilities of the base WAL telemetry system. All tracking methods create spans with appropriate attributes for tracing AI/ML operations.

### Span Attributes

Each span created by the WAL telemetry AI/ML integration includes the following attributes:

#### Common Attributes

| Attribute | Description |
|-----------|-------------|
| `operation.type` | Type of operation being performed |
| `operation.category` | Category of the operation |

#### Model Operation Attributes

| Attribute | Description |
|-----------|-------------|
| `model.id` | Identifier for the model |
| `framework` | ML framework being used |
| `device` | Device being used (for initialization) |

#### Inference Attributes

| Attribute | Description |
|-----------|-------------|
| `model.id` | Identifier for the model |
| `batch.size` | Size of the inference batch |
| `input_type` | Type of input data |

#### Training Attributes

| Attribute | Description |
|-----------|-------------|
| `model.id` | Identifier for the model |
| `epoch` | Current epoch number |
| `num_samples` | Number of samples in the epoch |
| `loss` | Loss value (for training stats) |
| `learning_rate` | Learning rate (for training stats) |
| `gradient_norm` | Gradient norm (for training stats) |

#### Dataset Attributes

| Attribute | Description |
|-----------|-------------|
| `dataset.id` | Identifier for the dataset |
| `format` | Format of the dataset |
| `operation` | Operation being performed on the dataset |

#### Distributed Attributes

| Attribute | Description |
|-----------|-------------|
| `task.id` | Identifier for the training task |
| `num_workers` | Number of workers participating |
| `worker.id` | Identifier for the worker (for utilization) |
| `utilization` | Worker utilization ratio (for utilization) |

### Context Propagation

The WAL telemetry AI/ML integration supports context propagation across service boundaries using the same mechanisms as the base WAL telemetry system:

```python
# Extract tracing context from incoming request
context = api.wal_extract_tracing_context(request_headers)

# Create a span with the extracted context
with api.wal_create_span(name="operation", context=context):
    # Perform operation
    pass

# Inject tracing context into outgoing request
headers = {}
api.wal_inject_tracing_context(headers)
```

## Use Cases

### 1. Model Performance Optimization

Track model loading, initialization, and inference performance to identify bottlenecks and optimize critical paths:

```python
# Track model loading performance
with api.wal_track_model_operation(
    operation_type="model_load",
    model_id="my_model",
    framework="pytorch",
    model_size=model_size
):
    model = load_model("path/to/model")

# Benchmark inference performance across batch sizes
for batch_size in [1, 2, 4, 8, 16, 32]:
    with api.wal_track_inference(
        model_id="my_model",
        batch_size=batch_size,
        track_memory=True
    ):
        outputs = model(generate_batch(batch_size))
```

### 2. Training Progress Monitoring

Track training progress and performance metrics to optimize hyperparameters and detect issues early:

```python
# Track training epochs and collect metrics
for epoch in range(num_epochs):
    with api.wal_track_training_epoch(
        model_id="my_model",
        epoch=epoch,
        num_samples=len(train_loader.dataset)
    ):
        # Train for one epoch
        epoch_loss, epoch_accuracy = train_one_epoch(model, train_loader, optimizer)
    
    # Record training statistics
    api.wal_record_training_stats(
        model_id="my_model",
        epoch=epoch,
        loss=epoch_loss,
        learning_rate=scheduler.get_last_lr()[0],
        gradient_norm=compute_grad_norm(model)
    )
    
    # Get training metrics report for monitoring
    report = api.wal_generate_metrics_report(format="markdown")
    print(report["report"])
```

### 3. Distributed Training Optimization

Monitor distributed training coordination overhead and worker utilization to optimize cluster utilization:

```python
# Track distributed training task
with api.wal_track_distributed_operation(
    operation_type="worker_coordination",
    task_id=f"training_task_{task_id}",
    num_workers=len(workers)
):
    # Set up distributed training
    workers = initialize_workers()

# Track task distribution
with api.wal_track_distributed_operation(
    operation_type="task_distribution",
    task_id=f"training_task_{task_id}",
    num_workers=len(workers)
):
    # Distribute tasks to workers
    distribute_tasks(workers, tasks)

# Monitor worker utilization
for worker_id, worker in workers.items():
    api.wal_record_worker_utilization(
        worker_id=worker_id,
        utilization=worker.get_utilization()
    )

# Track result aggregation
with api.wal_track_distributed_operation(
    operation_type="result_aggregation",
    task_id=f"training_task_{task_id}",
    num_workers=len(workers)
):
    # Aggregate results from workers
    results = aggregate_results(workers)
```

### 4. Dataset Performance Analysis

Track dataset loading and preprocessing performance to optimize data pipelines:

```python
# Track dataset loading from IPFS
with api.wal_track_dataset_operation(
    operation_type="dataset_load",
    dataset_id="imagenet",
    format="tfrecord",
    dataset_size=dataset_size
):
    # Load dataset from IPFS
    dataset = load_dataset_from_ipfs("Qm...")

# Track multiple preprocessing steps
for operation in ["resize", "normalize", "augment"]:
    with api.wal_track_dataset_operation(
        operation_type="dataset_preprocess",
        dataset_id="imagenet",
        operation=operation
    ):
        # Apply preprocessing operation
        dataset = apply_preprocessing(dataset, operation)
```

### 5. End-to-End AI Pipeline Monitoring

Track the complete AI pipeline from data loading to model training and inference:

```python
# Track dataset loading
with api.wal_track_dataset_operation(
    operation_type="dataset_load",
    dataset_id="my_dataset",
    format="parquet",
    dataset_size=dataset_size
):
    dataset = load_dataset("path/to/dataset")

# Track model loading
with api.wal_track_model_operation(
    operation_type="model_load",
    model_id="my_model",
    framework="pytorch",
    model_size=model_size
):
    model = load_model("path/to/model")

# Track training
for epoch in range(num_epochs):
    with api.wal_track_training_epoch(
        model_id="my_model",
        epoch=epoch,
        num_samples=len(dataset)
    ):
        train_one_epoch(model, dataset)

# Track inference
with api.wal_track_inference(
    model_id="my_model",
    batch_size=32
):
    predictions = model(test_data)

# Generate comprehensive report
report = api.wal_generate_metrics_report(format="markdown")
print(report["report"])
```

## Examples

A complete example demonstrating the WAL telemetry AI/ML integration is available in the `examples` directory:

- [wal_telemetry_ai_ml_example.py](../examples/wal_telemetry_ai_ml_example.py): Demonstrates how to use the WAL telemetry AI/ML integration with a FastAPI server for metrics visualization.

To run the example:

```bash
# Run the simulation and print metrics report
python -m examples.wal_telemetry_ai_ml_example

# Run with metrics server for visualization
python -m examples.wal_telemetry_ai_ml_example --server --port 8000

# Customize the simulation
python -m examples.wal_telemetry_ai_ml_example --models 5 --inferences 20 --epochs 10
```

## Best Practices

### 1. Categorize Operations Consistently

Use consistent operation types for better metrics aggregation:

```python
# Good: Use consistent operation types
with api.wal_track_model_operation(operation_type="model_load", ...):
    # Load model
    
# Avoid: Using inconsistent operation types
with api.wal_track_model_operation(operation_type="loading_model", ...):
    # Load model
```

### 2. Include Model and Operation Context

Always include relevant context in tracking calls:

```python
# Good: Include framework and size for model operations
with api.wal_track_model_operation(
    operation_type="model_load",
    model_id="my_model",
    framework="pytorch",
    model_size=model_size
):
    # Load model
    
# Good: Include batch size and input type for inference
with api.wal_track_inference(
    model_id="my_model",
    batch_size=32,
    input_type="image"
):
    # Run inference
```

### 3. Implement Proper Error Handling

Ensure tracking blocks properly handle errors:

```python
try:
    with api.wal_track_model_operation(operation_type="model_load", ...):
        # Load model
        model = load_model("path/to/model")
except Exception as e:
    # Handle error
    logger.error(f"Failed to load model: {e}")
    # The tracking span will automatically record the exception
```

### 4. Optimize for Performance

Be mindful of the overhead introduced by tracking:

- Track high-level operations rather than very fine-grained operations
- Use sampling for high-frequency operations
- Consider disabling tracking in performance-critical sections

```python
# Good: Track high-level operations
with api.wal_track_training_epoch(...):
    # Train for one epoch
    
# Avoid: Tracking every batch (too granular)
for batch in train_loader:
    with api.wal_track_operation(...):  # Too much overhead
        # Process single batch
```

### 5. Enable FastAPI Integration for Visualization

Set up a FastAPI server with metrics endpoints for easy visualization:

```python
from fastapi import FastAPI
app = FastAPI()

# Add metrics endpoint to FastAPI app
api.wal_add_metrics_endpoint(app)

# Add custom endpoint for AI/ML metrics report
@app.get("/aiml-report")
async def aiml_report():
    report_result = api.wal_generate_metrics_report(format="markdown")
    if report_result["success"]:
        return {"report": report_result["report"]}
    else:
        return {"error": report_result["error"]}
```

## Troubleshooting

### Common Issues

#### 1. Telemetry Not Initialized

**Symptom**: `"Base WAL telemetry extension not initialized"` error when calling AI/ML telemetry methods.

**Solution**: Ensure you've initialized WAL telemetry before extending with AI/ML capabilities:

```python
# Initialize base WAL telemetry first
api.wal_telemetry(enabled=True)

# Then extend with AI/ML telemetry
api = extend_high_level_api_with_aiml_telemetry(api)
api.wal_aiml_telemetry()
```

#### 2. Missing Optional Dependencies

**Symptom**: `ImportError` when using visualization features.

**Solution**: Install the optional dependencies:

```bash
pip install prometheus-client opentelemetry-api opentelemetry-sdk matplotlib plotly
```

#### 3. Prometheus Metrics Not Registered

**Symptom**: AI/ML metrics not appearing in Prometheus endpoint.

**Solution**: Ensure Prometheus integration is properly initialized:

```python
# Initialize Prometheus integration
api.wal_prometheus(
    enabled=True,
    port=9090
)

# Then initialize AI/ML telemetry
api.wal_aiml_telemetry()
```

#### 4. High Telemetry Overhead

**Symptom**: Performance degradation when tracking many operations.

**Solution**: Reduce tracking granularity and use sampling:

```python
# Use sampling for high-frequency operations
if random.random() < 0.1:  # 10% sampling
    with api.wal_track_inference(...):
        # Run inference
else:
    # Run inference without tracking
    run_inference()
```

### Logging and Debugging

Enable debug logging to troubleshoot telemetry issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("ipfs_kit_py.wal_telemetry_ai_ml").setLevel(logging.DEBUG)
```

### Getting Help

If you encounter issues not covered in this documentation, please:

1. Check the [GitHub repository](https://github.com/your-repo/ipfs_kit_py) for known issues
2. Review the example applications in the `examples` directory
3. Open an issue on GitHub with a detailed description of your problem

## Additional Resources

- [WAL Telemetry API Documentation](./wal_telemetry_api.md): Documentation for the base WAL telemetry system
- [AI/ML Metrics Documentation](./ai_ml_metrics.md): Documentation for the AI/ML metrics system
- [High-Level API Documentation](./high_level_api.md): Documentation for the high-level API
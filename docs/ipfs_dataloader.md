# IPFS DataLoader for Machine Learning

The IPFSDataLoader provides a high-performance data loading mechanism for machine learning workloads using IPFS content-addressed storage. It enables efficient batch-based data loading with background prefetching and integrates seamlessly with popular ML frameworks like PyTorch and TensorFlow.

## Features

- **Efficient Batch Loading**: Organize data into batches with configurable batch size
- **Background Prefetching**: Asynchronously load batches in the background for better performance
- **Dataset Shuffling**: Randomize sample order during training
- **Streaming Iterator Interface**: Standard Python iterator interface for easy integration
- **PyTorch Integration**: Direct conversion to PyTorch DataLoader
- **TensorFlow Integration**: Direct conversion to TensorFlow Dataset
- **Resource Management**: Proper cleanup for threads and queues
- **Content-Addressed Storage**: Leverage IPFS content addressing for dataset distribution
- **Role-Based Architecture**: Compatible with master/worker/leecher node roles

## Getting Started

### Installation

Make sure you have the AI/ML dependencies installed:

```bash
pip install ipfs_kit_py[ai_ml]
```

Or for a full installation with all dependencies:

```bash
pip install ipfs_kit_py[full]
```

### Basic Usage

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize IPFS Kit with AI/ML integration enabled
kit = ipfs_kit(
    metadata={"enable_ai_ml": True}
)

# Get a data loader
loader = kit.get_data_loader(
    batch_size=32,  # Number of samples per batch
    shuffle=True,   # Shuffle samples during iteration
    prefetch=2      # Number of batches to prefetch
)

# Load a dataset by CID
result = loader.load_dataset("QmYourDatasetCID")
if result["success"]:
    print(f"Loaded dataset with {loader.total_samples} samples")
else:
    print(f"Failed to load dataset: {result.get('error')}")
    
# Iterate through batches
for batch in loader:
    # Process each batch
    for sample in batch:
        # Process each sample
        features = sample["features"]
        labels = sample["labels"]
        # Your processing code here...

# Clean up resources when done
loader.close()
```

## Dataset Format

The IPFSDataLoader supports two dataset formats stored in IPFS:

### 1. CID-Referenced Samples

A dataset with a list of CIDs pointing to individual samples:

```json
{
    "name": "example_dataset",
    "description": "Example dataset with CID-referenced samples",
    "version": "1.0.0",
    "created_at": 1648720000,
    "samples": [
        "QmSample1CID",
        "QmSample2CID",
        "QmSample3CID",
        "..."
    ]
}
```

Each referenced sample can be in any format, but typically uses a structure like:

```json
{
    "features": [0.1, 0.2, 0.3, ...],
    "labels": 1
}
```

### 2. Embedded Samples

A dataset with samples directly embedded in the dataset object:

```json
{
    "name": "example_embedded_dataset",
    "description": "Example dataset with embedded samples",
    "version": "1.0.0",
    "created_at": 1648720000,
    "data": [
        {"features": [0.1, 0.2, 0.3], "labels": 0},
        {"features": [0.4, 0.5, 0.6], "labels": 1},
        {"features": [0.7, 0.8, 0.9], "labels": 0},
        "..."
    ]
}
```

## Framework Integration

### PyTorch Integration

Convert the IPFSDataLoader directly to a PyTorch DataLoader:

```python
# Create a loader
loader = kit.get_data_loader(batch_size=32)
loader.load_dataset("QmYourDatasetCID")

# Convert to PyTorch DataLoader
pytorch_loader = loader.to_pytorch()

# Use in PyTorch training loop
import torch

model = torch.nn.Linear(input_dim, output_dim)
criterion = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

for epoch in range(num_epochs):
    for features, labels in pytorch_loader:
        # Forward pass
        outputs = model(features)
        loss = criterion(outputs, labels)
        
        # Backward and optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
```

### TensorFlow Integration

Convert the IPFSDataLoader directly to a TensorFlow Dataset:

```python
# Create a loader
loader = kit.get_data_loader(batch_size=32)
loader.load_dataset("QmYourDatasetCID")

# Convert to TensorFlow Dataset
tf_dataset = loader.to_tensorflow()

# Use in TensorFlow training
import tensorflow as tf

model = tf.keras.Sequential([
    tf.keras.layers.Dense(128, activation='relu', input_shape=(input_dim,)),
    tf.keras.layers.Dense(output_dim, activation='softmax')
])

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Train using the dataset
model.fit(tf_dataset, epochs=num_epochs)
```

## Advanced Usage

### Creating and Uploading Datasets

You can create and upload datasets to IPFS using the following pattern:

```python
import json
import numpy as np
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize kit
kit = ipfs_kit()

# Create a dataset with sample references
def create_reference_dataset(num_samples=100):
    # First create samples
    sample_cids = []
    
    for i in range(num_samples):
        # Create a sample with random features
        sample = {
            "features": np.random.rand(10).tolist(),
            "labels": np.random.randint(0, 2)
        }
        
        # Add to IPFS
        result = kit.ipfs.dag_put(sample)
        if result["success"]:
            sample_cid = result["cid"]
            sample_cids.append(sample_cid)
    
    # Create dataset metadata
    dataset = {
        "name": "random_dataset",
        "description": "Randomly generated dataset for testing",
        "version": "1.0.0",
        "created_at": time.time(),
        "samples": sample_cids
    }
    
    # Add dataset to IPFS
    result = kit.ipfs.dag_put(dataset)
    if result["success"]:
        dataset_cid = result["cid"]
        print(f"Created dataset with CID: {dataset_cid}")
        return dataset_cid
    else:
        print(f"Failed to create dataset: {result.get('error')}")
        return None
```

### Handling Large Datasets

For large datasets, implement pagination and partial loading:

```python
# Load a large dataset in chunks
def process_large_dataset(dataset_cid, chunk_size=1000):
    # Initialize kit and data loader
    kit = ipfs_kit()
    loader = kit.get_data_loader(batch_size=32)
    
    # Get dataset metadata
    result = kit.ipfs.dag_get(dataset_cid)
    if not result["success"]:
        print(f"Failed to get dataset: {result.get('error')}")
        return
        
    metadata = result["object"]
    total_samples = len(metadata.get("samples", []))
    
    # Process in chunks
    for chunk_start in range(0, total_samples, chunk_size):
        chunk_end = min(chunk_start + chunk_size, total_samples)
        print(f"Processing samples {chunk_start} to {chunk_end-1}")
        
        # Create a temporary dataset with just this chunk
        chunk_dataset = {
            "name": metadata.get("name", "unknown") + f"_chunk_{chunk_start}",
            "samples": metadata["samples"][chunk_start:chunk_end]
        }
        
        # Add chunk dataset to IPFS
        chunk_result = kit.ipfs.dag_put(chunk_dataset)
        if not chunk_result["success"]:
            print(f"Failed to create chunk dataset: {chunk_result.get('error')}")
            continue
            
        chunk_cid = chunk_result["cid"]
        
        # Load this chunk
        loader.load_dataset(chunk_cid)
        
        # Process the chunk
        for batch in loader:
            # Your processing code here
            pass
```

### Distributed Training Configuration

Configure for distributed training across a cluster:

```python
# Master node: Create and distribute dataset
def master_distribute_dataset(dataset_cid):
    kit = ipfs_kit(role="master")
    
    # Make sure dataset is pinned
    kit.ipfs.pin_add(dataset_cid)
    
    # Create training task for worker nodes
    task_config = {
        "operation": "training",
        "dataset_cid": dataset_cid,
        "hyperparameters": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 5
        }
    }
    
    # Publish task to workers
    kit.ipfs.pubsub_publish(
        topic="training_tasks",
        message=json.dumps(task_config)
    )
    
    return "Task published to workers"

# Worker node: Receive dataset and train
def worker_train(pubsub_message):
    kit = ipfs_kit(role="worker")
    
    # Parse task configuration
    task = json.loads(pubsub_message["data"])
    dataset_cid = task["dataset_cid"]
    hyperparams = task["hyperparameters"]
    
    # Get data loader with batch size from task
    loader = kit.get_data_loader(
        batch_size=hyperparams["batch_size"],
        shuffle=True
    )
    
    # Load dataset
    loader.load_dataset(dataset_cid)
    
    # Create PyTorch loader
    pytorch_loader = loader.to_pytorch()
    
    # Train model (simplified)
    # ... your training code ...
    
    # Save and publish model back to master
    # ... your model saving code ...
```

## Performance Considerations

### Memory Usage

- **Prefetch Queue**: Adjust `prefetch` parameter based on your system's memory constraints
- **Batch Size**: Larger batch sizes increase memory usage but may improve throughput
- **Memory Management**: Call `loader.close()` when done to release resources

### Threading

The data loader uses background threads for prefetching:

- Threads are daemon threads and will exit when the main program terminates
- Each loader manages its own thread pool
- Thread safety is ensured for all public methods

### Optimizing Performance

- **Locality**: Position worker nodes close to storage nodes for faster content access
- **Caching**: Content is automatically cached for repeated access
- **Batch Size Tuning**: Experiment with batch sizes to find the optimal value for your workload
- **Prefetch Depth**: Increase prefetch for high-latency networks, decrease for memory-constrained environments

## Implementation Details

### Prefetching Mechanism

The data loader uses a producer-consumer pattern for prefetching:

1. A background thread produces batches by fetching samples from IPFS
2. Batches are placed in a queue with configurable capacity
3. The main iterator consumes batches from the queue

This approach allows network I/O to happen in parallel with computation, improving overall throughput.

### Error Handling

The data loader implements robust error handling:

- Network errors during sample retrieval are logged but don't stop the entire batch
- Missing samples are skipped with a warning
- Invalid dataset formats produce clear error messages
- Resource cleanup is guaranteed even in error scenarios

### Thread Management

Background threads are properly managed:

- Threads are stopped cleanly when `close()` is called
- An event-based signaling system is used to terminate threads
- Queue timeouts prevent deadlocks

## API Reference

### `IPFSDataLoader`

```python
class IPFSDataLoader:
    """IPFS-based data loader for ML frameworks."""
    
    def __init__(self, ipfs_client, batch_size=32, shuffle=True, prefetch=2):
        """
        Initialize data loader for machine learning workloads.
        
        Args:
            ipfs_client: IPFS client for content access
            batch_size: Number of samples per batch
            shuffle: Whether to shuffle the dataset
            prefetch: Number of batches to prefetch
        """
        
    def load_dataset(self, dataset_cid):
        """
        Load dataset metadata from IPFS.
        
        Args:
            dataset_cid: Content identifier for the dataset
            
        Returns:
            Result dictionary with success/failure status
        """
        
    def __iter__(self):
        """Iterator interface for dataset."""
        
    def __next__(self):
        """Get next batch from dataset."""
        
    def __len__(self):
        """Number of batches in dataset."""
        
    def to_pytorch(self):
        """
        Convert to PyTorch DataLoader.
        
        Returns:
            PyTorch DataLoader or None if PyTorch not available
        """
        
    def to_tensorflow(self):
        """
        Convert to TensorFlow Dataset.
        
        Returns:
            TensorFlow Dataset or None if TensorFlow not available
        """
        
    def close(self):
        """Clean up resources used by the data loader."""
```

### Main IPFS Kit Interface

```python
def get_data_loader(self, batch_size=32, shuffle=True, prefetch=2):
    """
    Get a data loader for machine learning workloads.
    
    Args:
        batch_size: Number of samples per batch
        shuffle: Whether to shuffle the dataset
        prefetch: Number of batches to prefetch
        
    Returns:
        IPFSDataLoader instance or None if AI/ML integration is not available
    """
```

## Conclusion

The IPFSDataLoader provides a powerful interface for loading and processing machine learning datasets from IPFS, with built-in support for batching, prefetching, and ML framework integration. By leveraging IPFS's content-addressed storage model, it enables efficient distribution and sharing of ML datasets across a network of nodes.
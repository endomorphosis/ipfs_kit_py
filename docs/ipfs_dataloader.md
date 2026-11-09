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

The IPFSDataLoader supports multiple dataset formats stored in IPFS:

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

### 3. Multi-Modal Data

For handling multiple data modalities (images, text, audio, etc.):

```json
{
    "name": "multi_modal_dataset",
    "description": "Dataset combining images, text, and tabular data",
    "version": "1.0.0",
    "created_at": 1648720000,
    "samples": [
        {
            "id": "sample001",
            "image_cid": "QmImageCID1",
            "text": "Sample text description for image 1",
            "tabular_features": [0.1, 0.2, 0.3],
            "label": 1
        },
        {
            "id": "sample002",
            "image_cid": "QmImageCID2",
            "text": "Sample text description for image 2",
            "tabular_features": [0.4, 0.5, 0.6],
            "label": 0
        },
        "..."
    ]
}
```

You can process multi-modal data with specialized helper methods:

```python
# Load multi-modal dataset
loader.load_dataset("QmMultiModalDatasetCID")

# Process multi-modal data with framework-specific helpers
for batch in loader:
    for sample in batch:
        # Load image data (automatically fetches the CID reference)
        image_tensor = loader.fetch_image(sample["image_cid"], transform_to_tensor=True)
        
        # Process text (can apply tokenization if required)
        text_tokens = loader.process_text(sample["text"], tokenizer=my_tokenizer)
        
        # Process tabular features
        features = torch.tensor(sample["tabular_features"])
        
        # Process combined data
        outputs = multimodal_model(image_tensor, text_tokens, features)
```

### 4. Sharded Datasets

For large datasets, you can use a sharded structure:

```json
{
    "name": "sharded_dataset",
    "description": "Large dataset split into multiple shards",
    "version": "1.0.0",
    "created_at": 1648720000,
    "shard_count": 10,
    "samples_per_shard": 1000,
    "total_samples": 10000,
    "shards": [
        "QmShard1CID",
        "QmShard2CID",
        "QmShard3CID",
        "..."
    ]
}
```

Each shard contains a subset of samples:

```json
{
    "shard_id": 1,
    "sample_start_idx": 0,
    "sample_end_idx": 999,
    "samples": [
        {"features": [0.1, 0.2, 0.3], "labels": 0},
        {"features": [0.4, 0.5, 0.6], "labels": 1},
        "..."
    ]
}
```

Processing shards can be done sequentially or in parallel:

```python
# Sequential shard processing
for shard_cid in dataset_metadata["shards"]:
    # Load just this shard
    loader.load_dataset(shard_cid)
    
    # Process all batches in the shard
    for batch in loader:
        # Process batch
        pass
        
    # Clear this shard before loading the next
    loader.clear()
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

The TensorFlow conversion performs these operations:
1. Creates a TensorFlow Dataset using `tf.data.Dataset.from_generator`
2. Applies appropriate transformations (`batch`, `prefetch`, etc.)
3. Sets data types and shapes based on the first batch
4. Optimizes the pipeline for performance using TensorFlow's internal optimizations

Sample implementation pattern:

```python
def to_tensorflow(self):
    """Convert to TensorFlow Dataset."""
    if not TF_AVAILABLE:
        return {
            "success": False,
            "error": "TensorFlow is not available. Please install with 'pip install tensorflow'",
            "simulation_note": "This is a simulated error, no Dataset was created"
        }
        
    try:
        import tensorflow as tf
        
        # Define generator function
        def generator():
            for batch in self:
                for sample in batch:
                    # Extract features and labels
                    if "features" in sample and "labels" in sample:
                        yield (sample["features"], sample["labels"])
                    else:
                        yield sample
        
        # Infer output types and shapes by examining first element
        if self.total_samples > 0:
            first_batch = next(iter(self))
            first_sample = first_batch[0]
            
            if "features" in first_sample and "labels" in first_sample:
                output_types = (tf.float32, tf.int32)
                output_shapes = (
                    tf.TensorShape([len(first_sample["features"])]), 
                    tf.TensorShape([])
                )
            else:
                # Default to flexible types
                output_types = tf.float32
                output_shapes = tf.TensorShape([None])
        else:
            # Default if dataset is empty
            output_types = tf.float32
            output_shapes = tf.TensorShape([None])
        
        # Create dataset
        dataset = tf.data.Dataset.from_generator(
            generator,
            output_types=output_types,
            output_shapes=output_shapes
        )
        
        # Apply batching
        dataset = dataset.batch(self.batch_size)
        
        # Apply prefetching (TF's own prefetching)
        dataset = dataset.prefetch(tf.data.experimental.AUTOTUNE)
        
        return dataset
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to convert to TensorFlow Dataset"
        }
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

#### Basic Master-Worker Approach

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

#### Integration with PyTorch Distributed Data Parallel (DDP)

For faster multi-GPU or multi-node training, integrate with PyTorch's DDP:

```python
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler

def run_training(rank, world_size, dataset_cid):
    # Initialize distributed process group
    dist.init_process_group(
        backend="nccl", 
        init_method="tcp://localhost:12355",
        world_size=world_size,
        rank=rank
    )
    
    # Set up IPFS Kit
    kit = ipfs_kit(role="worker")
    
    # Get data loader
    loader = kit.get_data_loader(
        batch_size=32,
        shuffle=False  # We'll use DistributedSampler for shuffling
    )
    
    # Load dataset
    loader.load_dataset(dataset_cid)
    
    # Get PyTorch loader
    pytorch_dataset = loader.to_pytorch_dataset()  # Get dataset, not DataLoader
    
    # Create distributed sampler
    sampler = DistributedSampler(
        pytorch_dataset,
        num_replicas=world_size,
        rank=rank
    )
    
    # Create distributed loader
    pytorch_loader = torch.utils.data.DataLoader(
        pytorch_dataset,
        batch_size=32,
        sampler=sampler,
        num_workers=4,
        pin_memory=True
    )
    
    # Create model and move to GPU
    model = YourModel().to(rank)
    
    # Wrap model with DDP
    ddp_model = DDP(model, device_ids=[rank])
    
    # Training loop
    for epoch in range(10):
        # Set epoch for sampler
        sampler.set_epoch(epoch)
        
        for batch in pytorch_loader:
            # Training step
            # ...

# Start distributed training
def start_distributed_training(dataset_cid, num_gpus=torch.cuda.device_count()):
    # Use multiprocessing to start processes
    mp.spawn(
        run_training,
        args=(num_gpus, dataset_cid),
        nprocs=num_gpus,
        join=True
    )
```

#### Integration with Horovod for TensorFlow

For distributed training with TensorFlow and Horovod:

```python
import tensorflow as tf
import horovod.tensorflow as hvd

def run_horovod_training(dataset_cid):
    # Initialize Horovod
    hvd.init()
    
    # Set up IPFS Kit
    kit = ipfs_kit(role="worker")
    
    # Get data loader
    loader = kit.get_data_loader(
        batch_size=32,
        shuffle=False  # Handled by Horovod
    )
    
    # Load dataset
    loader.load_dataset(dataset_cid)
    
    # Get TensorFlow dataset
    tf_dataset = loader.to_tensorflow()
    
    # Partition dataset among workers
    tf_dataset = tf_dataset.shard(
        num_shards=hvd.size(),
        index=hvd.rank()
    )
    
    # Shuffle with seed based on epoch
    tf_dataset = tf_dataset.shuffle(10000)
    
    # Batch and prefetch
    tf_dataset = tf_dataset.batch(32).prefetch(tf.data.experimental.AUTOTUNE)
    
    # Set up model
    model = tf.keras.Sequential([
        # ...
    ])
    
    # Horovod distributed optimizer
    optimizer = tf.keras.optimizers.Adam(0.001 * hvd.size())
    optimizer = hvd.DistributedOptimizer(optimizer)
    
    # Compile model
    model.compile(
        optimizer=optimizer,
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy'],
        experimental_run_tf_function=False
    )
    
    # Callbacks
    callbacks = [
        hvd.callbacks.BroadcastGlobalVariablesCallback(0),
        hvd.callbacks.MetricAverageCallback(),
    ]
    
    # Train model
    model.fit(
        tf_dataset, 
        epochs=10,
        callbacks=callbacks, 
        verbose=1 if hvd.rank() == 0 else 0
    )
    
    # Save model on rank 0
    if hvd.rank() == 0:
        # Save model to IPFS
        # ...
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

### Performance Visualization

You can visualize the performance characteristics of the data loader using the visualization capabilities in the `ai_ml_visualization` module:

```python
from ipfs_kit_py.ai_ml_metrics import AIMLMetricsCollector
from ipfs_kit_py.ai_ml_visualization import create_visualization

# Create a metrics collector to track data loading performance
metrics = AIMLMetricsCollector()

# Configure data loader to use metrics
loader = kit.get_data_loader(
    batch_size=32, 
    shuffle=True,
    prefetch=2,
    metrics=metrics
)

# Load and process dataset
loader.load_dataset("QmYourDatasetCID")
for batch_idx, batch in enumerate(loader):
    # Process batch...
    pass

# Create visualization
viz = create_visualization(metrics, interactive=True)

# Visualize dataset loading performance
viz.plot_dataset_load_times(
    figsize=(10, 6),
    show_plot=True
)

# Generate a comprehensive dashboard including dataset metrics
viz.plot_comprehensive_dashboard(
    output_file="dataloader_performance.html"
)
```

This visualization provides insights into:
- Batch loading times
- Prefetch queue utilization
- Cache hit/miss rates
- Network vs. computation time
- Throughput measurements

For more details, see the [AI/ML Visualization Guide](integration/ai-ml/ai_ml_visualization.md).

## Implementation Details

### Prefetching Mechanism

The data loader uses a producer-consumer pattern for prefetching:

1. A background thread produces batches by fetching samples from IPFS
2. Batches are placed in a queue with configurable capacity
3. The main iterator consumes batches from the queue

This approach allows network I/O to happen in parallel with computation, improving overall throughput.

### Multimodal Data Handling

The IPFSDataLoader provides specialized methods for handling different data modalities:

#### Image Handling

```python
def fetch_image(self, image_cid, transform_to_tensor=False, image_transforms=None):
    """
    Fetch an image from IPFS and optionally convert to a tensor.
    
    Args:
        image_cid: CID of the image in IPFS
        transform_to_tensor: Whether to convert to a tensor (requires PyTorch)
        image_transforms: Optional transforms to apply (torchvision.transforms)
        
    Returns:
        PIL Image or tensor depending on transform_to_tensor
    """
    # Fetch image data from IPFS
    image_data = self.ipfs.cat(image_cid)
    
    # Convert to PIL Image
    from PIL import Image
    import io
    image = Image.open(io.BytesIO(image_data))
    
    # Apply transforms if requested
    if transform_to_tensor:
        if image_transforms is not None:
            # Apply custom transforms
            return image_transforms(image)
        else:
            # Default transformation to tensor
            import torch
            from torchvision import transforms
            to_tensor = transforms.ToTensor()
            return to_tensor(image)
    
    return image
```

#### Text Processing

```python
def process_text(self, text, tokenizer=None, max_length=None):
    """
    Process text data, optionally applying tokenization.
    
    Args:
        text: Text string to process
        tokenizer: Optional tokenizer to apply (e.g., from transformers)
        max_length: Maximum sequence length for tokenization
        
    Returns:
        Processed text (tokenized if tokenizer provided)
    """
    if tokenizer is None:
        return text
        
    # Apply tokenizer
    tokenizer_kwargs = {}
    if max_length is not None:
        tokenizer_kwargs["max_length"] = max_length
        tokenizer_kwargs["truncation"] = True
        
    return tokenizer(text, return_tensors="pt", **tokenizer_kwargs)
```

#### Audio Processing

```python
def process_audio(self, audio_cid, sample_rate=None, transform_to_tensor=False):
    """
    Process audio data from IPFS.
    
    Args:
        audio_cid: CID of the audio file
        sample_rate: Target sample rate (None for no resampling)
        transform_to_tensor: Whether to convert to tensor
        
    Returns:
        Audio data in the requested format
    """
    # Fetch audio data
    audio_data = self.ipfs.cat(audio_cid)
    
    # Process with torchaudio
    if transform_to_tensor:
        import io
        import torchaudio
        
        audio_file = io.BytesIO(audio_data)
        waveform, original_sample_rate = torchaudio.load(audio_file)
        
        # Resample if needed
        if sample_rate is not None and sample_rate != original_sample_rate:
            resampler = torchaudio.transforms.Resample(
                orig_freq=original_sample_rate,
                new_freq=sample_rate
            )
            waveform = resampler(waveform)
            
        return waveform
    
    # Return raw bytes if no tensor conversion
    return audio_data
```

### Caching Mechanisms

The data loader implements multiple levels of caching:

1. **Memory Cache**: Recently accessed samples are kept in memory
2. **Batch Cache**: Prefetched batches are stored in the queue
3. **Disk Cache**: Large datasets can optionally be cached on disk
4. **Node Cache**: Uses IPFS node's internal caching for CID resolution

This multi-level caching strategy ensures optimal performance for various dataset sizes and access patterns.

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
    
    def __init__(self, ipfs_client, batch_size=32, shuffle=True, prefetch=2, metrics=None):
        """
        Initialize data loader for machine learning workloads.
        
        Args:
            ipfs_client: IPFS client for content access
            batch_size: Number of samples per batch
            shuffle: Whether to shuffle the dataset
            prefetch: Number of batches to prefetch
            metrics: Optional metrics collector for performance monitoring
        """
        
    def load_dataset(self, dataset_cid):
        """
        Load dataset metadata from IPFS.
        
        Args:
            dataset_cid: Content identifier for the dataset
            
        Returns:
            Result dictionary with success/failure status
        """
        
    def load_embedded_dataset(self, data_array):
        """
        Load an already-retrieved array of data samples.
        
        Args:
            data_array: List of data samples to use
            
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
            PyTorch DataLoader or error dictionary if PyTorch not available
        """
        
    def to_pytorch_dataset(self):
        """
        Convert to PyTorch IterableDataset (without creating a DataLoader).
        
        Returns:
            PyTorch IterableDataset or error dictionary if PyTorch not available
        """
        
    def to_tensorflow(self):
        """
        Convert to TensorFlow Dataset.
        
        Returns:
            TensorFlow Dataset or error dictionary if TensorFlow not available
        """
        
    def fetch_image(self, image_cid, transform_to_tensor=False, image_transforms=None):
        """
        Fetch an image from IPFS and optionally convert to a tensor.
        
        Args:
            image_cid: CID of the image in IPFS
            transform_to_tensor: Whether to convert to a tensor (requires PyTorch)
            image_transforms: Optional transforms to apply (torchvision.transforms)
            
        Returns:
            PIL Image or tensor depending on transform_to_tensor
        """
        
    def process_text(self, text, tokenizer=None, max_length=None):
        """
        Process text data, optionally applying tokenization.
        
        Args:
            text: Text string to process
            tokenizer: Optional tokenizer to apply (e.g., from transformers)
            max_length: Maximum sequence length for tokenization
            
        Returns:
            Processed text (tokenized if tokenizer provided)
        """
        
    def process_audio(self, audio_cid, sample_rate=None, transform_to_tensor=False):
        """
        Process audio data from IPFS.
        
        Args:
            audio_cid: CID of the audio file
            sample_rate: Target sample rate (None for no resampling)
            transform_to_tensor: Whether to convert to tensor
            
        Returns:
            Audio data in the requested format
        """
        
    def clear(self):
        """
        Clear the current dataset from memory without stopping prefetching threads.
        Useful when processing multiple datasets sequentially.
        """
        
    def get_performance_metrics(self):
        """
        Get performance metrics for this data loader.
        
        Returns:
            Dictionary with performance metrics (if metrics collector was provided)
        """
        
    def close(self):
        """Clean up resources used by the data loader."""
```

### Main IPFS Kit Interface

```python
def get_data_loader(self, batch_size=32, shuffle=True, prefetch=2, metrics=None):
    """
    Get a data loader for machine learning workloads.
    
    Args:
        batch_size: Number of samples per batch
        shuffle: Whether to shuffle the dataset
        prefetch: Number of batches to prefetch
        metrics: Optional metrics collector for performance monitoring
        
    Returns:
        IPFSDataLoader instance or None if AI/ML integration is not available
    """
```

### AI/ML Metrics Collector

```python
class AIMLMetricsCollector:
    """
    Collects and analyzes metrics for AI/ML operations.
    
    This class can be used to monitor and analyze performance of data loaders,
    model training, and other AI/ML operations.
    """
    
    def __init__(self, enable_detailed_tracking=True):
        """
        Initialize the metrics collector.
        
        Args:
            enable_detailed_tracking: Whether to collect detailed metrics (may impact performance)
        """
        
    def start_operation(self, operation_name):
        """
        Start timing an operation.
        
        Args:
            operation_name: Name of the operation to time
            
        Returns:
            Operation ID for use with end_operation
        """
        
    def end_operation(self, operation_id, metadata=None):
        """
        End timing an operation and record its duration.
        
        Args:
            operation_id: ID returned by start_operation
            metadata: Optional metadata to associate with this operation
        """
        
    def record_metric(self, metric_name, value, metadata=None):
        """
        Record a single metric value.
        
        Args:
            metric_name: Name of the metric
            value: Value of the metric
            metadata: Optional metadata to associate with this metric
        """
        
    def get_metrics(self):
        """
        Get all collected metrics.
        
        Returns:
            Dictionary with all collected metrics
        """
        
    def get_summary(self):
        """
        Get a summary of collected metrics.
        
        Returns:
            Dictionary with summary statistics for each metric
        """
```

## Best Practices

### Dataset Organization

- **Structure Hierarchically**: Organize large datasets into hierarchical structures
- **Use CID References**: For large samples, store by CID rather than embedding
- **Include Metadata**: Add descriptive metadata to make datasets self-documenting
- **Version Explicitly**: Include version numbers in dataset metadata
- **Maintain Provenance**: Document data sources in metadata

### Efficient Data Loading

- **Choose Batch Size Wisely**: 
  - Smaller batches increase overhead but use less memory
  - Larger batches may cause memory issues but reduce overhead
  - Test with your specific data to find the optimal value

- **Prefetch Tuning**:
  - For computation-heavy processing, increase prefetch to ensure pipeline stays full
  - For memory-constrained environments, reduce prefetch to control memory usage
  - Rule of thumb: Set prefetch to cover the typical processing time of one batch

- **Resource Management**:
  - Always call `loader.close()` when done to properly release resources
  - Use context managers when available to ensure proper cleanup
  - For sequential processing of multiple datasets, use `loader.clear()` between datasets

### Framework Integration

- **Framework-Specific Optimization**:
  - When using PyTorch, prefer `to_pytorch()` over manual iteration
  - With TensorFlow, let TF's own prefetching system handle optimizations
  - Use distributed samplers for multi-GPU/machine training

- **Multimodal Processing**:
  - Use specialized helpers for each modality: `fetch_image()`, `process_text()`, etc.
  - Pre-process and cache transformed data when possible
  - For uniform batches, process all samples of the same modality together for efficiency

### IPFS Integration

- **Pinning Strategy**:
  - Pin high-value datasets on multiple nodes for reliability
  - Use explicit IPFS garbage collection to manage storage
  - Consider using IPFS Cluster for managed replication

- **Locality Optimization**:
  - Co-locate worker nodes with storage nodes when possible
  - For single-node use, enable Unix socket communication for better performance
  - Use the `role` parameter to optimize for your node's responsibilities

- **Error Handling**:
  - Check `result["success"]` for all operations
  - Implement retry logic for transient failures
  - Use the metrics collector to identify bottlenecks

### Example Best Practice Implementation

```python
import contextlib

@contextlib.contextmanager
def ipfs_data_loader(kit, batch_size=32, shuffle=True, prefetch=2):
    """Context manager for proper resource handling with IPFSDataLoader."""
    # Create loader
    loader = kit.get_data_loader(
        batch_size=batch_size,
        shuffle=shuffle,
        prefetch=prefetch
    )
    
    try:
        # Yield the loader for use
        yield loader
    finally:
        # Ensure resources are properly cleaned up
        loader.close()

# Usage
with ipfs_data_loader(kit, batch_size=64) as loader:
    # Load dataset
    result = loader.load_dataset("QmYourDatasetCID")
    if not result["success"]:
        print(f"Error loading dataset: {result.get('error')}")
    else:
        # Process dataset
        for batch in loader:
            # Your processing code
            pass
```

## Conclusion

The IPFSDataLoader provides a powerful interface for loading and processing machine learning datasets from IPFS, with built-in support for batching, prefetching, and ML framework integration. By leveraging IPFS's content-addressed storage model, it enables efficient distribution and sharing of ML datasets across a network of nodes, while the multimodal data support, advanced caching mechanisms, and framework integrations make it suitable for a wide range of machine learning workloads.
# IPFS Kit Examples

This directory contains example scripts demonstrating the usage of various IPFS Kit features.

> 📚 **New Documentation Available!** 
> 
> A comprehensive documentation index is now available in the [`docs/README.md`](../docs/README.md) file.
> It provides a structured overview of all documentation including core concepts, high-level API,
> distributed systems, storage backends, AI/ML integration, and more.

## Running Examples

To run these examples, you need to have the IPFS Kit package installed or in your Python path. 
You should also have an IPFS daemon running unless otherwise noted.

```bash
# Start IPFS daemon in the background
ipfs daemon &

# Run an example
python -m examples.fsspec_example
python -m examples.data_science_examples
```

## Available Examples

### `fsspec_example.py`

Demonstrates the FSSpec integration which provides a filesystem-like interface to IPFS content. 
This example shows how to:

- Create a filesystem interface
- Add files and directories to IPFS
- List directory contents
- Read file contents using file-like objects
- Verify the caching mechanism with performance measurements

**Prerequisites**: Requires the `fsspec` package to be installed.

```bash
pip install fsspec
```

### `cluster_state_example.py`

Demonstrates the Arrow-based cluster state management system for distributed coordination.
This example shows how to:

- Set up a master node with cluster state
- Create and manage tasks
- Access the cluster state from an external process
- Query and analyze the cluster state with helper functions

The example has two modes:
1. `master`: Run a master node that creates and manages the cluster state
2. `external`: Run an external process that accesses the cluster state

**Usage**:
```bash
# Run master node (in one terminal)
python -m examples.cluster_state_example master

# Run external access (in another terminal)
python -m examples.cluster_state_example external
```

**Prerequisites**: Requires the `pyarrow` package (and optionally `pandas`) to be installed.

```bash
pip install pyarrow pandas
```

### `data_science_examples.py`

Shows how to integrate IPFS with popular data science libraries through the FSSpec interface. 
This comprehensive example demonstrates:

- Reading and writing various data formats (CSV, Parquet, Feather, JSON)
- Working with pandas DataFrames
- Using PyArrow for efficient data processing
- Creating machine learning models with scikit-learn
- Visualizing data with matplotlib/seaborn
- Parallel processing with Dask
- Running complete data science workflows

**Prerequisites**: The example uses a variety of data science libraries. Install them as needed:

```bash
pip install pandas pyarrow scikit-learn matplotlib seaborn dask
```

#### Data Science Integration Features

The `ipfs_kit_py` library provides seamless integration with data science tools through its FSSpec-compatible filesystem implementation. This allows you to work with content-addressed data using familiar interfaces with advantages including:

- **Immutable Datasets**: Perfect data versioning with IPFS CIDs
- **Deduplication**: Efficiently share and store dataset versions 
- **Distributed Access**: Access the same data across different environments
- **Multi-tier Caching**: Optimized access to frequently used data with memory/disk caching
- **Memory-mapped Access**: Efficient handling of large datasets
- **Gateway Fallback**: Flexible access even when local daemon is unavailable
- **Collaborative Workflows**: Share datasets and models with consistent references

### `performance_profiling.py`

Provides comprehensive performance profiling and benchmarking tools for IPFS Kit operations. 
This example shows how to:

- Profile and benchmark key IPFS operations (add, get, pin, etc.)
- Measure and analyze cache performance
- Collect detailed metrics on API operations
- Generate performance reports with optimization recommendations

For more details, see the [Performance Profiling Guide](PERFORMANCE_PROFILING.md).

### `performance_optimizations.py`

Implements automatic optimizations based on profiling results. This example shows how to:

- Analyze profiling results to identify optimization opportunities
- Implement caching for high-level API methods
- Optimize the tiered cache configuration
- Implement chunked uploads for large files

### `high_level_api_example.py`

Demonstrates the simplified API interface (`IPFSSimpleAPI`) with examples of:

- Content operations (add, get, pin)
- File-like operations (open, read, ls)
- IPNS operations (publish, resolve)
- Cluster operations (cluster_add, cluster_pin, cluster_status)
- Configuration management and customization
- Plugin architecture and extensions

### `ai_ml_integration_example.py`

Demonstrates the AI/ML integration capabilities of IPFS Kit. This comprehensive example shows how to:

- Store and retrieve machine learning models with the ModelRegistry
- Manage ML datasets with versioning and distribution
- Use the IPFSDataLoader for efficient data loading and batch processing
- Integrate with PyTorch and TensorFlow frameworks
- Leverage LangChain integration for LLM applications
- Set up distributed training with the master/worker architecture

The example includes several modules that demonstrate different aspects of AI/ML integration:

1. Model Registry - storing and retrieving ML models (scikit-learn, PyTorch)
2. Dataset Management - handling versioned ML datasets
3. IPFS DataLoader - efficient data loading for training
4. Framework Integration - working with PyTorch and TensorFlow
5. LangChain Integration - using IPFS with LangChain for LLM applications
6. Distributed Training - setting up distributed ML workflows

**Prerequisites**: Depending on which parts of the example you want to run, you may need:

```bash
# Basic requirements
pip install scikit-learn pandas numpy

# For PyTorch integration
pip install torch

# For TensorFlow integration
pip install tensorflow

# For LangChain integration
pip install langchain faiss-cpu openai
# Also needs: export OPENAI_API_KEY="your-api-key"
```

### `ai_ml_visualization_example.py`

Demonstrates the visualization capabilities for AI/ML metrics in IPFS Kit. This example shows how to:

- Generate synthetic AI/ML metrics data for demonstration
- Create interactive (Plotly) and static (Matplotlib) visualizations
- Visualize different types of ML metrics:
  - Training metrics (loss curves, accuracy, learning rates)
  - Inference latency distributions
  - Worker utilization in distributed training
  - Dataset loading performance
- Generate comprehensive dashboards combining multiple visualizations
- Export visualizations to various formats (PNG, SVG, HTML, JSON)
- Create HTML reports with CSS styling for sharing results

The example automatically generates realistic synthetic metrics data that mimics common patterns in ML workflows, making it useful for demonstration and testing purposes without requiring actual training runs.

**Usage**:
```bash
# Run the visualization example
python -m examples.ai_ml_visualization_example
```

**Prerequisites**: For full visualization capabilities, you need:
```bash
# For interactive and static visualizations
pip install matplotlib plotly pandas numpy

# Optional - for additional features
pip install seaborn kaleido
```

When visualization libraries are not available, the example will demonstrate graceful degradation with text-based output.

### Real-time Streaming and Notifications

The IPFS Kit now supports real-time streaming capabilities with WebRTC and WebSocket notifications.

#### `websocket_streaming_example.py`

Demonstrates bidirectional streaming of content via WebSockets. This example shows how to:

- Stream content FROM IPFS sources using chunked transfer encoding
- Stream content TO IPFS without loading entire files into memory
- Support HTTP Range requests for media seeking
- Implement bidirectional streaming for real-time applications
- Handle progress monitoring for large transfers

**Usage**:
```bash
# Run the WebSocket streaming example
python -m examples.websocket_streaming_example
```

**Prerequisites**: Requires `aiohttp` package for WebSocket support.

```bash
pip install aiohttp
```

#### `webrtc_streaming_example.py`

Demonstrates WebRTC-based media streaming directly from IPFS content. This example shows how to:

- Set up WebRTC streaming from IPFS content
- Establish peer-to-peer media connections
- Stream video content with low latency
- Support multiple stream qualities
- Implement signaling over WebSockets
- Handle ICE candidate exchange for NAT traversal

**Usage**:
```bash
# Run the WebRTC streaming example server
python -m examples.webrtc_streaming_example server

# In another terminal or browser, run the client
python -m examples.webrtc_streaming_example client
```

**Prerequisites**: Requires WebRTC dependencies.

```bash
pip install aiortc av websockets
```

#### `notification_client_example.py`

Demonstrates the real-time notification system via WebSockets. This example shows how to:

- Connect to the notification WebSocket endpoint
- Subscribe to different notification types
- Receive real-time updates about system events
- Filter notifications by specific criteria
- Implement custom notification handlers
- Process various notification types:
  - Content events (added, retrieved, removed)
  - Peer events (connected, disconnected)
  - WebRTC events (stream started/ended, connection changes)
  - System events (metrics, warnings, errors)

**Usage**:
```bash
# Run the notification client example
python -m examples.notification_client_example
```

**Prerequisites**: Requires `websockets` package.

```bash
pip install websockets
```

#### `unified_dashboard_example.py`

A comprehensive example that combines WebRTC streaming with WebSocket notifications in a unified dashboard. This example shows how to:

- Create a complete monitoring dashboard for IPFS Kit
- Stream media content from IPFS via WebRTC
- Receive and display real-time system notifications
- Visualize streaming statistics and performance metrics
- Track WebRTC connection status
- Filter and search through notifications
- Customize the dashboard appearance

**Usage**:
```bash
# Run the unified dashboard example
python -m examples.unified_dashboard_example [--api-url API_URL] [--cid CID]
```

**Prerequisites**: Requires UI dependencies in addition to WebRTC and WebSocket packages.

```bash
pip install ipfs_kit_py[webrtc,ui]
```

### Write-Ahead Log (WAL) Examples

The IPFS Kit includes a robust Write-Ahead Log (WAL) system for fault-tolerant operations. These examples demonstrate the various interfaces to the WAL system.

#### `wal_cli_example.py`

Demonstrates the standalone WAL command-line interface. This example shows how to:

- Use the `wal-cli` command for managing WAL operations
- Check WAL status and statistics
- List pending operations
- Show details of specific operations
- Wait for operations to complete
- Clean up old operations
- Monitor backend health

**Usage**:
```bash
# Run the WAL CLI example
python -m examples.wal_cli_example

# You can also run the WAL CLI directly
python -m ipfs_kit_py.wal_cli status
python -m ipfs_kit_py.wal_cli list pending
python -m ipfs_kit_py.wal_cli health
```

#### `wal_cli_integration_example.py`

Demonstrates the integrated WAL CLI commands within the main IPFS Kit CLI. This example shows how to:

- Use WAL commands integrated with the main CLI
- Add content through the WAL system
- Check WAL status and statistics
- List and monitor operations
- View backend health information
- Process pending operations
- Get WAL metrics and configuration

**Usage**:
```bash
# Run the WAL CLI integration example
python -m examples.wal_cli_integration_example

# You can also use the WAL commands directly with the main CLI
python -m ipfs_kit_py.cli wal status
python -m ipfs_kit_py.cli wal list pending
python -m ipfs_kit_py.cli wal health
python -m ipfs_kit_py.cli wal process
```

#### `wal_api_example.py`

Demonstrates the WAL REST API interface. This example shows how to:

- Use the WAL HTTP API endpoints
- Add content through the WAL system
- Check WAL status and retrieve operation details
- List operations of different statuses
- Monitor backend health
- Get WAL metrics and configuration
- Retry failed operations

**Usage**:
```bash
# Run the WAL API example
python -m examples.wal_api_example
```

#### `wal_visualization_example.py`

Demonstrates visualization of WAL operations and metrics. This example shows how to:

- Visualize WAL operation flow
- Monitor backend health over time
- Track operation latency and success rates
- Generate dashboards for WAL monitoring
- Create reports of WAL performance

**Usage**:
```bash
# Run the WAL visualization example
python -m examples.wal_visualization_example
```

**Prerequisites**: Visualization requires matplotlib and pandas.
```bash
pip install matplotlib pandas
```

### Performance Optimization Examples

#### `probabilistic_data_structures_example.py`

Demonstrates the probabilistic data structures implemented in the IPFS Kit library. These structures provide memory-efficient approximations for common operations like membership testing, cardinality estimation, and frequency counting. This comprehensive example shows:

- **Bloom Filter**: Space-efficient membership testing with configurable false positive rates
- **HyperLogLog**: Cardinality estimation using minimal memory
- **Count-Min Sketch**: Frequency estimation for streaming data
- **Cuckoo Filter**: Membership testing with deletion support
- **MinHash**: Document similarity estimation
- **TopK**: Identifying most frequent items

The example includes detailed benchmarks comparing these structures to exact implementations, showing the memory/accuracy tradeoffs, and providing visualization of their performance characteristics. It also demonstrates practical applications in IPFS Kit:

- Using Bloom filters for fast CID availability checking
- Using HyperLogLog for unique peer tracking
- Using Count-Min Sketch for content popularity monitoring
- Using MinHash for content similarity detection

**Usage**:
```bash
# Run all examples
python -m examples.probabilistic_data_structures_example

# Run specific examples
python -m examples.probabilistic_data_structures_example bloom hll cms cuckoo minhash topk ipfs
```

**Prerequisites**: Requires `matplotlib` and `numpy` for visualizations.

```bash
pip install matplotlib numpy
```

#### `probabilistic_data_structures_integration_example.py`

Demonstrates practical integration of probabilistic data structures with IPFS Kit in real-world scenarios. This example showcases how probabilistic structures can be used to solve actual challenges in distributed content systems while dramatically reducing memory requirements. The example focuses on three main integration scenarios:

1. **Content Tracking System**: Processes simulated streams of content accesses using probabilistic structures, demonstrating memory efficiency compared to exact implementations
2. **Tiered Cache Integration**: Shows how to enhance the tiered cache system with probabilistic structures to make intelligent caching decisions
3. **IPFS Content Analytics Dashboard**: Builds a complete dashboard that uses probabilistic structures to provide insights with minimal overhead

Key features demonstrated:
- Tracking content popularity across millions of unique CIDs with minimal memory
- Implementing real-world access patterns using Zipfian distribution with temporal locality
- Memory usage visualization comparing probabilistic vs. exact data structures
- Integration with the IPFS Kit tiered cache system
- Configurable accuracy vs. memory tradeoffs
- Implementation of a complete analytics system using the `ProbabilisticDataStructureManager`

**Usage**:
```bash
# Run the integration example
python -m examples.probabilistic_data_structures_integration_example
```

**Prerequisites**: Requires `matplotlib`, `numpy`, and `pandas` for visualizations and data handling.

```bash
pip install matplotlib numpy pandas
```

### Additional Examples

- `libp2p_example.py`: Direct peer-to-peer communication
- `cluster_advanced_example.py`: Advanced cluster management features
- `tiered_cache_example.py`: Multi-tier caching system
- `cluster_management_example.py`: Cluster management and monitoring
- `cluster_state_helpers_example.py`: Using Arrow-based cluster state helpers
- `simple_test.py`: Basic IPFS operations for testing

## Documentation References

For complete documentation on all IPFS Kit features:

1. Start with the [Documentation Index](../docs/README.md)
2. Review the [Core Concepts](../docs/core_concepts.md) document
3. Read the [High-Level API](../docs/high_level_api.md) documentation
4. Explore feature-specific guides like [Tiered Cache](../docs/tiered_cache.md)

## Adding More Examples

Feel free to add more examples to this directory to demonstrate other features of IPFS Kit.
Make sure each example:

1. Has a descriptive name
2. Contains clear documentation in the script
3. Is mentioned in this README
4. Includes proper error handling and cleanup
5. Lists any additional dependencies needed
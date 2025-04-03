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
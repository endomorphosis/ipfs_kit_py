# IPFS Kit Examples

This directory contains example scripts demonstrating the usage of various IPFS Kit features.

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

## Adding More Examples

Feel free to add more examples to this directory to demonstrate other features of IPFS Kit.
Make sure each example:

1. Has a descriptive name
2. Contains clear documentation in the script
3. Is mentioned in this README
4. Includes proper error handling and cleanup
5. Lists any additional dependencies needed
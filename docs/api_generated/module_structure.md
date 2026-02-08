# IPFS Kit Python - Module Structure

> Auto-generated documentation - Last updated: 2025-10-29T04:09:56.898549

This document provides an overview of the module structure and available components in IPFS Kit Python.

## Package Overview

### __init__.py

#### `__init__.py`

IPFS Kit - Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration.

This package provides comprehensive IPFS functionality including:

🌐 **IPFS Operations**: Core IPFS daemon, cluster management, and content operations
🔗 **Filecoin Integration**: Lotus daemon and miner for Filecoin network interaction  
📦 **High-Performance Retrieval**: Lassie client for fast IPFS content retrieval
☁️ **Web3 Storage**: Storacha/Web3.Storage integration for decentralized storage
🤖 **AI/ML Integration**: Machine learning pipeline support with transformers
📡 **MCP Server**: Model Context Protocol server for AI assistant integration

## Just-in-Time (JIT) Import System

This package uses an integrated JIT import system for optimal performance:
- **Fast Startup**: Heavy dependencies loaded only when needed
- **Smart Caching**: Module imports cached for subsequent use
- **Feature Detection**: Graceful fallbacks for missing dependencies
- **Shared State**: Consistent import behavior across CLI, daemon, and MCP server

```python
# Core JIT system is automatically available
from ipfs_kit_py.core import jit_manager

# Check feature availability (fast)
if jit_manager.check_feature('enhanced_features'):
    # Modules loaded on-demand
    enhanced_index = jit_manager.get_module('enhanced_pin_index')

# Use decorators for automatic feature handling
from ipfs_kit_py.core import require_feature, optional_feature

@require_feature('daemon')
def start_daemon():
    # Only runs if daemon components are available
    pass

@optional_feature('analytics', fallback_result={})
def get_analytics():
    # Returns {} if analytics not available
    return complex_analytics()
```

## Automatic Binary Installation

The package automatically downloads and installs required binaries when imported:

- **IPFS**: ipfs, ipfs-cluster-service, ipfs-cluster-ctl, ipfs-cluster-follow
- **Lotus**: lotus, lotus-miner  
- **Lassie**: lassie
- **Storacha**: Python and NPM dependencies

## Quick Start

```python
# Import triggers automatic binary installation and JIT system initialization
from ipfs_kit_py import install_ipfs, install_lotus, install_lassie, install_storacha

# Check installation status
from ipfs_kit_py import (
    INSTALL_IPFS_AVAILABLE,
    INSTALL_LOTUS_AVAILABLE, 
    INSTALL_LASSIE_AVAILABLE,
    INSTALL_STORACHA_AVAILABLE
)

# Use installers directly
ipfs_installer = install_ipfs()
ipfs_installer.install_ipfs_daemon()

# Or use the MCP server for IPFS operations
# Start server: python final_mcp_server_enhanced.py --host 0.0.0.0 --port 9998
```

## MCP Server Integration

The package includes a production-ready MCP server with JIT optimization:

```bash
python final_mcp_server_enhanced.py --host 0.0.0.0 --port 9998
```

For detailed documentation, see: https://github.com/endomorphosis/ipfs_kit_py

**Classes:**
- `MockJITManager`
- `SimpleTransformers`: Simplified transformers integration with JIT loading.

**Functions:**
- `download_binaries()`: Download platform-specific binaries and install dependencies for IPFS, Lotus, Lassie, and Storacha.
- `get_wal_components()`: Get WAL components, loading them lazily if needed.
- `get_wal_integration()`: Get WAL integration with lazy loading.
- `get_wal_enabled_api()`: Get WAL-enabled API with lazy loading.
- `get_register_wal_api()`: Get WAL API registration with lazy loading.
- `get_ipfs_py()`
- `get_ipfs_cluster_ctl()`
- `get_ipfs_cluster_follow()`
- `get_ipfs_cluster_service()`
- `get_ipfs_kit()`
- `get_ipfs_multiformats_py()`
- `get_ipfs_singleton()`: Get the IPFS singleton, loading it lazily if needed.
- `get_error_module()`: Get error module with lazy loading.
- `get_ipfs_filesystem()`: Lazy import of IPFSFileSystem.
- `get_cli_main()`: Lazy import of CLI main function.
- `get_api_app()`: Lazy import of API app.

### advanced_filecoin_client.py

#### `advanced_filecoin_client.py`

Advanced Filecoin Client Library for MCP

This module implements the client library for interacting with the advanced Filecoin
features mentioned in the MCP roadmap:
1. Network Analytics & Metrics
2. Intelligent Miner Selection & Management
3. Enhanced Storage Operations
4. Content Health & Reliability
5. Blockchain Integration

This library can be used with either the mock server for development and testing,
or with actual Filecoin services in production.

**Classes:**
- `AdvancedFilecoinClient`: Client for interacting with advanced Filecoin features.

### ai_ml_integration.py

#### `ai_ml_integration.py`

**Classes:**
- `MockAwareJSONEncoder`: JSON encoder that handles MagicMock objects by replacing them with placeholders.
- `nullcontext`: Context manager that does nothing.
- `AIMLIntegration`: Mock class for AI/ML integration.
- `ModelRegistry`: Full implementation of model registry for IPFS Kit.
- `DatasetManager`: Full implementation of dataset manager for IPFS Kit.
- `LangchainIntegration`: Integration class for Langchain with IPFS.
- `LlamaIndexIntegration`: Integration class for LlamaIndex with IPFS.
- `IPFSDataLoader`: IPFS data loader class for machine learning datasets.
- `DistributedTraining`: Infrastructure for distributed model training with IPFS.
- `TensorflowIntegration`: Integration class for TensorFlow with IPFS.
- `PyTorchIntegration`: Integration class for PyTorch with IPFS.
- `StoreModelRequest`: Request model for storing ML models.
- `StoreModelResponse`: Response model for model storage operations.
- `LoadModelRequest`: Request model for loading ML models.
- `LoadModelResponse`: Response model for model loading operations (error case).
- `ListModelsResponse`: Response model for listing models.
- `ShareModelRequest`: Request model for sharing ML models.
- `ShareModelResponse`: Response model for model sharing operations.
- `UpdateModelMetadataRequest`: Request model for updating model metadata.
- `UpdateModelMetadataResponse`: Response model for metadata update operations.
- `DeleteModelRequest`: Request model for deleting models.
- `DeleteModelResponse`: Response model for model deletion operations.
- `GetModelCIDRequest`: Request model for retrieving model CIDs.
- `GetModelCIDResponse`: Response model for CID retrieval operations.
- `LoadDatasetRequest`: Request model for loading a dataset from the registry.
- `LoadDatasetResponse`: Response model for dataset loading operations.
- `GetDatasetCIDRequest`: Request model for retrieving dataset CIDs.
- `GetDatasetCIDResponse`: Response model for dataset CID retrieval operations.
- `DeleteDatasetRequest`: Request model for deleting datasets.
- `DeleteDatasetResponse`: Response model for dataset deletion operations.
- `ShareDatasetRequest`: Request model for sharing datasets.
- `ShareDatasetResponse`: Response model for dataset sharing operations.
- `ListDatasetsResponse`: Response model for listing datasets from the registry.
- `IPFSDataLoaderRequest`: Request model for loading a dataset via IPFSDataLoader.
- `IPFSDataLoaderResponse`: Response model for IPFSDataLoader operations.
- `ClearResponse`: Response model for clearing IPFSDataLoader cache.
- `ToTensorflowResponse`: Response model for converting IPFSDataLoader to TensorFlow dataset.
- `ToPytorchResponse`: Response model for converting IPFSDataLoader to PyTorch DataLoader.
- `CloseResponse`: Response model for closing IPFSDataLoader and releasing resources.
- `CreateVectorStoreRequest`: Request model for creating vector stores.
- `CreateVectorStoreResponse`: Response model for vector store creation operations.
- `EmbeddedDatasetRequest`: Request model for loading an embedded dataset.
- `EmbeddedDatasetResponse`: Response model for embedded dataset loading operations.
- `PerformanceMetrics`: Model for performance metrics from the data loader.
- `StoreDatasetRequest`: Request model for storing datasets.
- `StoreDatasetResponse`: Response model for dataset storage operations.
- `DatasetLoadRequest`: Request model for loading a dataset by name/version or CID.
- `DatasetLoadResponse`: Response model for dataset loading operations.
- `ListDatasetsResponse`: Response model for listing datasets.
- `GetDatasetCIDRequest`: Request model for retrieving dataset CIDs.
- `GetDatasetCIDResponse`: Response model for dataset CID retrieval operations.
- `ShareDatasetRequest`: Request model for sharing datasets.
- `ShareDatasetResponse`: Response model for dataset sharing operations.
- `DeleteDatasetRequest`: Request model for deleting datasets.
- `DeleteDatasetResponse`: Response model for dataset deletion operations.
- `TrainTestSplitRequest`: Request model for creating train/test splits.
- `TrainTestSplitResponse`: Response model for train/test split operations.
- `IPFSDataLoaderConfig`: Configuration model for IPFSDataLoader class.
- `BaseModel`: Dummy BaseModel when Pydantic is not available.
- `ModelMetadata`: Metadata for machine learning models.
- `ModelMetadata`: Metadata for machine learning models.
- `MockSafeEncoder`
- `CheckAvailabilityResponse`: Response model for dependency availability check.
- `LoadDocumentsRequest`: Request model for loading documents from IPFS or local path.
- `LoadDocumentsResponse`: Response model for document loading operation.
- `MockEmbeddingFunction`
- `CreateIPFSVectorStoreRequest`: Request model for creating an IPFS-backed vector store.
- `CreateIPFSVectorStoreResponse`: Response model for IPFS vector store creation operations.
- `IPFSVectorStore`
- `CreateDocumentLoaderRequest`: Request model for creating a document loader.
- `CreateDocumentLoaderResponse`: Response model for document loader creation operations.
- `IPFSDocumentLoader`
- `StoreChainRequest`: Request model for storing a Langchain chain in IPFS.
- `StoreChainResponse`: Response model for chain storage operations.
- `LoadChainRequest`: Request model for loading a Langchain chain from IPFS.
- `LoadChainResponse`: Response model for chain loading operations.
- `LlamaIndexAvailabilityResponse`: Response model for LlamaIndex dependency availability check.
- `LoadLlamaIndexDocumentsRequest`: Request model for loading documents from IPFS or local path.
- `LoadLlamaIndexDocumentsResponse`: Response model for document loading operation.
- `CreateDocumentReaderRequest`: Request model for creating an IPFS document reader.
- `CreateDocumentReaderResponse`: Response model for document reader creation.
- `IPFSDocumentReader`
- `IPFSVectorIndex`
- `IPFSQueryEngine`
- `CreateIndexRequest`: Request model for creating an index from documents.
- `CreateIndexResponse`: Response model for index creation operation.
- `StoreIndexRequest`: Request model for storing a LlamaIndex index in IPFS.
- `StoreIndexResponse`: Response model for index storage operations.
- `LoadIndexRequest`: Request model for loading a LlamaIndex index from IPFS.
- `LoadIndexResponse`: Response model for index loading operations.
- `LoadDatasetRequest`: Request model for loading a dataset from IPFS.
- `LoadDatasetResponse`: Response model for dataset loading operation.
- `LoadEmbeddedDatasetRequest`: Request model for the load_embedded_dataset method.
- `LoadEmbeddedDatasetResponse`: Response model for the load_embedded_dataset method.
- `FetchImageRequest`: Request model for the fetch_image method.
- `FetchImageErrorResponse`: Error response model for the fetch_image method.
- `ProcessTextRequest`: Request model for the process_text method.
- `ProcessTextErrorResponse`: Error response model for the process_text method.
- `ProcessAudioRequest`: Request model for the process_audio method.
- `ProcessAudioErrorResponse`: Error response model for the process_audio method.
- `ClearResponse`: Response model for the clear method.
- `ToPytorchResponse`: Response model for the to_pytorch method when PyTorch is not available.
- `ToPytorchDatasetResponse`: Response model for the to_pytorch_dataset method when PyTorch is not available.
- `ToTensorflowResponse`: Response model for the to_tensorflow method when TensorFlow is not available.
- `PerformanceMetricsResponse`: Response model for the get_performance_metrics method.
- `CloseResponse`: Response model for the close method.
- `LoadModelRequest`: Request model for the load_model method.
- `LoadModelResponse`: Success response model for the load_model method.
- `LoadModelErrorResponse`: Error response model for the load_model method.
- `ExportSavedModelRequest`: Request model for the export_saved_model method.
- `ExportSavedModelResponse`: Success response model for the export_saved_model method.
- `ExportSavedModelErrorResponse`: Error response model for the export_saved_model method.
- `CreateDataLoaderRequest`: Request model for the create_data_loader method.
- `CreateDataLoaderErrorResponse`: Error response model for the create_data_loader method.
- `OptimizeForInferenceRequest`: Request model for the optimize_for_inference method.
- `OptimizeForInferenceResponse`: Success response model for the optimize_for_inference method.
- `OptimizeForInferenceErrorResponse`: Error response model for the optimize_for_inference method.
- `SaveModelRequest`: Request model for the save_model method.
- `SaveModelResponse`: Success response model for the save_model method.
- `SaveModelErrorResponse`: Error response model for the save_model method.
- `Config`
- `MockSafeEncoder`
- `IPFSIterableDataset`
- `IPFSIterableDataset`
- `IPFSRetriever`
- `SimpleDataset`
- `DictDataset`
- `MetricsCallback`
- `SimpleListDataset`

**Functions:**
- `ipfs_data_loader_context()`: Context manager for the IPFSDataLoader to ensure proper resource cleanup.

### ai_ml_metrics.py

#### `ai_ml_metrics.py`

Performance metrics for AI/ML operations with IPFS.

This module extends the core performance metrics system with AI/ML specific metrics tracking
capabilities, focusing on model loading times, inference latency, training throughput,
dataset loading performance, and distributed training coordination overhead.

Key features:
1. Model metrics: loading time, size, initialization overhead
2. Inference metrics: latency, throughput, memory usage
3. Training metrics: epochs, samples/second, convergence rate
4. Dataset metrics: loading time, preprocessing overhead
5. Distributed metrics: coordination overhead, worker utilization

These metrics help optimize AI/ML workloads on IPFS by identifying bottlenecks
and providing insights for tuning the system.

**Classes:**
- `AIMLMetrics`: Extended metrics tracking for AI/ML operations with IPFS.
- `AIMLMetricsCollector`: Collects and analyzes metrics for AI/ML workloads using IPFS.

### ai_ml_visualization.py

#### `ai_ml_visualization.py`

Visualization utilities for AI/ML metrics in IPFS Kit.

This module provides visualization tools for AI/ML metrics collected by the
ai_ml_metrics module. It supports both interactive and static visualizations,
with a focus on training convergence, inference performance, and distributed
training metrics.

Key features:
1. Training metrics visualization (loss curves, accuracy, learning rate)
2. Inference performance visualization (latency distributions, throughput)
3. Distributed training visualizations (worker utilization, coordination overhead)
4. Model and dataset comparison tools
5. Export to various formats (PNG, SVG, HTML, notebook widgets)

**Classes:**
- `AIMLVisualization`: Visualization tools for AI/ML metrics.

**Functions:**
- `create_visualization()`: Factory function to create a visualization instance.

### api.py

#### `api.py`

FastAPI server for IPFS Kit.

This module provides a RESTful API server built with FastAPI that exposes
the High-Level API for IPFS Kit over HTTP, enabling remote access to IPFS
functionality with consistent endpoint structure and response formats.

Key features:
1. RESTful API with standardized endpoints
2. OpenAPI documentation with Swagger UI
3. Support for file uploads and downloads
4. Consistent error handling
5. CORS support for web applications
6. Authentication (optional)
7. Configurable via environment variables or config file
8. Metrics and health monitoring
9. API versioning

The API follows REST conventions with resources organized by function:
- /api/v0/add - Add content to IPFS
- /api/v0/cat - Retrieve content by CID
- /api/v0/pin/* - Pin management endpoints
- /api/v0/swarm/* - Peer management endpoints
- /api/v0/name/* - IPNS management endpoints
- /api/v0/cluster/* - Cluster management endpoints
- /api/v0/ai/* - AI/ML integration endpoints

Error Handling:
All endpoints follow a consistent error handling pattern with standardized response format:
{
    "success": false,
    "error": "Description of the error",
    "error_type": "ErrorClassName",
    "status_code": 400  // HTTP status code
}

Error responses are categorized into:
- IPFS errors (400): Issues with IPFS operations
- Validation errors (400): Invalid input parameters
- Authorization errors (401/403): Permission issues
- Server errors (500): Unexpected exceptions

The API includes special test endpoints for validating error handling behavior:
- /api/error_method - Returns a standard IPFS error
- /api/unexpected_error - Returns a standard unexpected error

All endpoints return consistent JSON responses with a 'success' flag.

**Classes:**
- `DummyFastAPI`
- `DummyRouter`
- `Response`
- `HTTPException`
- `APIRequest`: API request model.
- `ErrorResponse`: Error response model.
- `APIRequest`: API request model.
- `ErrorResponse`: Error response model.
- `BaseModel`
- `UploadFile`
- `APIRouter`
- `WebSocketState`

**Functions:**
- `run_server()`: Run the IPFS Kit API server.

### api_anyio.py

#### `api_anyio.py`

FastAPI server for IPFS Kit with anyio support.

This module provides a RESTful API server built with FastAPI that exposes
the High-Level API for IPFS Kit over HTTP, enabling remote access to IPFS
functionality with consistent endpoint structure and response formats.

This version uses anyio for async operations, allowing for backend-agnostic
concurrency that works with different async backends (async-io, trio, etc.).

Key features:
1. RESTful API with standardized endpoints
2. OpenAPI documentation with Swagger UI
3. Support for file uploads and downloads
4. Consistent error handling
5. CORS support for web applications
6. Authentication (optional)
7. Configurable via environment variables or config file
8. Metrics and health monitoring
9. API versioning
10. Anyio-based async operations for backend flexibility

The API follows REST conventions with resources organized by function:
- /api/v0/add - Add content to IPFS
- /api/v0/cat - Retrieve content by CID
- /api/v0/pin/* - Pin management endpoints
- /api/v0/swarm/* - Peer management endpoints
- /api/v0/name/* - IPNS management endpoints
- /api/v0/cluster/* - Cluster management endpoints
- /api/v0/ai/* - AI/ML integration endpoints

Error Handling:
All endpoints follow a consistent error handling pattern with standardized response format:
{
    "success": false,
    "error": "Description of the error",
    "error_type": "ErrorClassName",
    "status_code": 400  // HTTP status code
}

Error responses are categorized into:
- IPFS errors (400): Issues with IPFS operations
- Validation errors (400): Invalid input parameters
- Authorization errors (401/403): Permission issues
- Server errors (500): Unexpected exceptions

The API includes special test endpoints for validating error handling behavior:
- /api/error_method - Returns a standard IPFS error
- /api/unexpected_error - Returns a standard unexpected error

All endpoints return consistent JSON responses with a 'success' flag.

**Classes:**
- `DummyFastAPI`
- `DummyRouter`
- `Response`
- `HTTPException`
- `APIRequest`: API request model.
- `ErrorResponse`: Error response model.
- `APIRequest`: API request model.
- `ErrorResponse`: Error response model.
- `IPFSResponse`: Standard response model for IPFS operations.
- `AddResponse`: Response model for add operation.
- `PinResponse`: Response model for pin operations.
- `SwarmPeersResponse`: Response model for swarm peers operation.
- `VersionResponse`: Response model for version information.
- `IPNSPublishResponse`: Response model for IPNS publish operation.
- `IPNSResolveResponse`: Response model for IPNS resolve operation.
- `KeyResponse`: Response model for key operations.
- `ClusterPinResponse`: Response model for cluster pin operations.
- `ClusterStatusResponse`: Response model for cluster status operations.
- `ModelMetadata`: Model metadata for AI/ML models.
- `ModelResponse`: Response model for AI/ML model operations.
- `DatasetMetadata`: Metadata for AI/ML datasets.
- `DatasetResponse`: Response model for AI/ML dataset operations.
- `IPFSResponse`
- `AddResponse`
- `PinResponse`
- `SwarmPeersResponse`
- `VersionResponse`
- `IPNSPublishResponse`
- `IPNSResolveResponse`
- `KeyResponse`
- `ClusterPinResponse`
- `ClusterStatusResponse`
- `ModelMetadata`
- `ModelResponse`
- `DatasetMetadata`
- `DatasetResponse`
- `BaseModel`
- `UploadFile`
- `APIRouter`
- `RateLimitMiddleware`
- `WebSocketState`

### api_stability.py

#### `api_stability.py`

API Stability Utilities for IPFS Kit.

This module provides decorators and utilities for managing API stability
and version compatibility throughout the IPFS Kit Python codebase.

Usage:
    @stable_api(since="0.1.0")
    def stable_method(param1, param2=None):
        '''This method is stable and won't break compatibility within a major version.'''
        pass

    @beta_api(since="0.1.0")
    def beta_method(param1, param2=None):
        '''This method is nearly stable but may still change in minor versions.'''
        pass

    @experimental_api(since="0.1.0")
    def experimental_method(param1, param2=None):
        '''This method is experimental and may change at any time.'''
        pass

    @deprecated(since="0.1.0", removed_in="1.0.0", alternative="new_method")
    def old_method():
        '''This method is deprecated and will be removed in a future version.'''
        warnings.warn("Use new_method instead", DeprecationWarning, stacklevel=2)
        pass

**Classes:**
- `APIStability`: API stability levels for IPFS Kit.

**Functions:**
- `stable_api()`: Mark a function or method as a stable API with compatibility guarantees.
- `beta_api()`: Mark a function or method as a beta API that is almost stable.
- `experimental_api()`: Mark a function or method as an experimental API with no stability guarantees.
- `deprecated()`: Mark a function or method as deprecated.
- `get_api_stability()`: Get the stability level of an API function or method.
- `is_stable_api()`: Check if a function or method is a stable API.
- `is_beta_api()`: Check if a function or method is a beta API.
- `is_experimental_api()`: Check if a function or method is an experimental API.
- `is_deprecated_api()`: Check if a function or method is a deprecated API.
- `get_api_registry()`: Get the complete API registry.
- `get_stability_metrics()`: Get metrics on API stability.
- `generate_api_stability_report()`: Generate a comprehensive report on API stability.
- `print_api_stability_report()`: Print a formatted API stability report to the console.
- `list_api_by_stability()`: List all APIs with the specified stability level.
- `generate_markdown_api_docs()`: Generate Markdown documentation of all APIs organized by stability level.

### arc_cache.py

#### `arc_cache.py`

Adaptive Replacement Cache (ARC) for IPFS content.

This module implements an Adaptive Replacement Cache that balances between 
recency and frequency of access for optimal caching performance.

**Classes:**
- `ARCache`: Adaptive Replacement Cache for memory-based caching of IPFS content.
- `BloomFilter`: Bloom filter for fast set membership tests with tunable false positive rate.
- `HyperLogLog`: HyperLogLog implementation for efficient cardinality estimation.
- `CountMinSketch`: Count-Min Sketch for frequency estimation in data streams.
- `MinHash`: MinHash implementation for estimating similarity between sets.
- `ParquetCIDCache`: Parquet-based CID cache for IPFS content with advanced partitioning strategies.

### arc_cache_anyio.py

#### `arc_cache_anyio.py`

**Classes:**
- `ARCacheAnyIO`: AnyIO-compatible extension for ARCache.

### aria2_kit.py

#### `aria2_kit.py`

Aria2 integration for ipfs_kit_py.

This module provides integration with Aria2, a high-speed download utility with
multi-connection/multi-source capabilities, extending the ipfs_kit_py ecosystem
with advanced download functionality.

**Classes:**
- `aria2_kit`: Interface to Aria2 for high-speed, multi-source downloads.

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### arrow_ipc_daemon_interface.py

#### `arrow_ipc_daemon_interface.py`

Arrow IPC Daemon Interface

This module provides zero-copy data access from the IPFS-Kit daemon using Apache Arrow IPC.
It enables efficient transfer of pin index data, metrics, and other structured data without
database lock conflicts or serialization overhead.

Key Features:
- Zero-copy data transfer using Arrow IPC
- Integration with existing daemon client
- Support for both CLI and MCP server access
- Efficient columnar data format
- Memory mapping for large datasets

**Classes:**
- `ArrowIPCDaemonInterface`: Arrow IPC interface for zero-copy data access from IPFS-Kit daemon.

**Functions:**
- `get_global_arrow_ipc_interface()`: Get or create the global Arrow IPC daemon interface.
- `get_pin_index_zero_copy_sync()`: Synchronous wrapper for CLI use.
- `get_metrics_zero_copy_sync()`: Synchronous wrapper for CLI use.

### arrow_metadata_index.py

#### `arrow_metadata_index.py`

Arrow-based metadata index for IPFS content.

This module implements the Arrow-based metadata index (Phase 4A Milestone 4.1), providing:
- Efficient metadata storage using Apache Arrow columnar format
- Parquet persistence for durability
- Fast querying capabilities
- Distributed index synchronization
- Zero-copy access via Arrow C Data Interface

**Classes:**
- `ArrowMetadataIndex`: Apache Arrow-based metadata index for IPFS content.

**Functions:**
- `create_metadata_from_ipfs_file()`: Create metadata record from an IPFS file.
- `find_ai_ml_resources()`: Find AI/ML resources (models, datasets) using the Arrow metadata index.
- `find_similar_models()`: Find models similar to a reference model using the metadata index.
- `find_datasets_for_task()`: Find datasets suitable for a specific machine learning task.

### arrow_metadata_index_anyio.py

#### `arrow_metadata_index_anyio.py`

Arrow-based metadata index for IPFS content with AnyIO support.

This module provides asynchronous versions of the Arrow-based metadata index functions,
supporting both async-io and trio via AnyIO. It wraps the synchronous ArrowMetadataIndex
methods with async equivalents for better performance in async contexts.

**Classes:**
- `ArrowMetadataIndexAnyIO`: AnyIO-compatible Arrow-based metadata index for IPFS content.

### backend_cli.py

#### `backend_cli.py`

Backend CLI handlers for IPFS Kit.

Provides CLI commands for managing backend configurations and pin mappings.

**Classes:**
- `Args`

### backend_manager.py

#### `backend_manager.py`

**Classes:**
- `BackendManager`

### backend_policies.py

#### `backend_policies.py`

Backend Policy Models for IPFS Kit Storage System

This module defines policy data structures that can be applied to storage backends
to manage quotas, replication, retention, and cache policies.

**Classes:**
- `QuotaUnit`: Units for quota specifications.
- `ReplicationStrategy`: Replication strategies for content.
- `RetentionAction`: Actions to take when retention period expires.
- `CacheEvictionPolicy`: Cache eviction policies.
- `StorageQuotaPolicy`: Storage quota policy for a backend.
- `TrafficQuotaPolicy`: Traffic quota policy for a backend.
- `ReplicationPolicy`: Replication policy for content.
- `RetentionPolicy`: Retention policy for content.
- `CachePolicy`: Cache policy for a backend.
- `BackendPolicySet`: Complete policy set for a storage backend.
- `PolicyViolation`: Represents a policy violation event.

**Functions:**
- `convert_size_to_bytes()`: Convert size with unit to bytes.
- `format_bytes()`: Format bytes to human readable string.

### backend_schemas.py

#### `backend_schemas.py`

Backend Configuration Schemas

This file defines the configuration schemas for each supported backend.
These schemas are used to dynamically generate configuration forms in the dashboard.

### backends

#### `backends/filesystem_backend.py`

Filesystem Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for filesystem storage (including SSHFS).

**Classes:**
- `FilesystemBackendAdapter`: Filesystem backend adapter implementing the isomorphic interface.

#### `backends/base_adapter.py`

Base Backend Adapter for IPFS Kit

Defines the isomorphic interface that all backend adapters must implement.
This ensures consistent method names and signatures across different filesystem backends.

**Classes:**
- `BackendAdapter`: Abstract base class for all backend adapters.

#### `backends/ipfs_backend.py`

IPFS Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for IPFS storage.

**Classes:**
- `IPFSBackendAdapter`: IPFS backend adapter implementing the isomorphic interface.

#### `backends/s3_backend.py`

S3 Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for S3-compatible storage.

**Classes:**
- `S3BackendAdapter`: S3 backend adapter implementing the isomorphic interface.

#### `backends/__init__.py`

IPFS Kit Storage Backends

This package contains storage backend implementations for IPFS Kit.
Each backend provides a standardized interface for different storage systems.

**Functions:**
- `get_backend_adapter()`: Factory function to get the appropriate backend adapter.
- `list_supported_backends()`: List all supported backend types.

### benchmark.py

#### `benchmark.py`

IPFS Kit Performance Benchmarking Tool

This module provides comprehensive benchmarking capabilities for the ipfs_kit_py
library, enabling detailed performance analysis of various operations and components.

**Classes:**
- `IPFSKitBenchmark`: Comprehensive benchmark tool for IPFS Kit operations.

**Functions:**
- `main()`: Main function for running the benchmark script.

### benchmark_framework.py

#### `benchmark_framework.py`

Comprehensive Benchmark Framework for ipfs_kit_py

This module provides a structured, configurable framework for benchmarking
all aspects of the ipfs_kit_py library, including file operations, content
addressing, caching efficiency, and networking performance.

Key features:
- Configurable benchmark scenarios
- Detailed performance metrics collection
- Comparative analysis between configurations
- Visualization of performance data
- Optimization recommendations

**Classes:**
- `BenchmarkContext`: Context manager for benchmarking operations with detailed metrics.
- `BenchmarkSuite`: Comprehensive benchmark suite for ipfs_kit_py.

**Functions:**
- `main()`: Run the benchmark framework from the command line.

### benchmark_prefetching.py

#### `benchmark_prefetching.py`

Performance Benchmarking Tool for IPFS Prefetching.

This module provides tools for benchmarking and analyzing the performance
of different prefetching strategies in the ipfs_kit_py library.

**Classes:**
- `PrefetchBenchmark`: Benchmarking tool for prefetching strategies.

**Functions:**
- `run_benchmark()`: Run a complete prefetching benchmark.

### bucket_dashboard.py

#### `bucket_dashboard.py`

Comprehensive Bucket Dashboard

Enhanced dashboard with full comprehensive MCP server feature integration,
providing complete feature parity with the original comprehensive dashboard.
Includes 86+ handlers covering system, MCP, backend, bucket, VFS, pin, service, 
config, log, peer, and analytics functionality.

**Classes:**
- `BucketDashboard`

### bucket_manager.py

#### `bucket_manager.py`

**Classes:**
- `BucketManager`

### bucket_vfs_api.py

#### `bucket_vfs_api.py`

Enhanced Dashboard API with Multi-Bucket VFS Support

This module extends the existing dashboard API to include comprehensive
bucket virtual filesystem management with S3-like semantics, IPLD
compatibility, and cross-platform data export capabilities.

**Classes:**
- `BucketVFSEndpoints`: API endpoints for bucket virtual filesystem management.
- `CreateBucketRequest`: Request model for creating a bucket.
- `AddFileRequest`: Request model for adding a file to a bucket.
- `CrossBucketQueryRequest`: Request model for cross-bucket SQL queries.

**Functions:**
- `get_bucket_vfs_endpoints()`: Get or create global bucket VFS endpoints instance.
- `get_bucket_vfs_router()`: Get FastAPI router for bucket VFS endpoints.

### bucket_vfs_cli.py

#### `bucket_vfs_cli.py`

Bucket VFS CLI Integration for IPFS Kit.

This module provides CLI commands for managing multi-bucket virtual filesystems
with S3-like semantics, IPLD compatibility, and cross-platform data export.

**Functions:**
- `colorize()`: Simple colorization for output.
- `print_success()`: Print success message.
- `print_error()`: Print error message.
- `print_info()`: Print info message.
- `print_warning()`: Print warning message.
- `register_bucket_commands()`: Register bucket VFS commands with the CLI.
- `handle_bucket_command()`: Handle bucket commands.

### bucket_vfs_manager.py

#### `bucket_vfs_manager.py`

Multi-Bucket Virtual Filesystem Manager for IPFS-Kit

This module implements a comprehensive multi-bucket virtual filesystem architecture
where each bucket contains:
- UnixFS structure for file organization
- Knowledge graph in IPLD format
- Vector index with IPLD compatibility
- Automatic export to Parquet/Arrow for DuckDB and cross-language support

The system provides S3-like bucket semantics with IPFS content addressing,
ensuring data is both traversable in IPFS and portable across different tools.

**Classes:**
- `BucketType`: Types of bucket virtual filesystems.
- `VFSStructureType`: Types of virtual filesystem structures.
- `BucketVFSManager`: Manager for multi-bucket virtual filesystems with IPLD compatibility.
- `BucketVFS`: Individual bucket virtual filesystem implementation.

**Functions:**
- `get_global_bucket_manager()`: Get or create global bucket VFS manager instance.

### cache

#### `cache/intelligent_cache.py`

Intelligent cache management with predictive eviction and dynamic tiering.

This module implements advanced caching strategies that go beyond traditional LRU/ARC
approaches, using machine learning and statistical techniques to predict content access
patterns and optimize cache management decisions.

**Classes:**
- `AccessPattern`: Represents a tracked access pattern for a content item.
- `PredictiveModel`: Machine learning model for predicting cache access patterns.
- `IntelligentCacheManager`: Manager for intelligent cache operations with predictive eviction.
- `IntelligentCacheStrategyProvider`: Provider for different intelligent caching strategies.

#### `cache/schema_column_optimization.py`

Schema and Column Optimization module for ParquetCIDCache.

This module implements optimization techniques for ParquetCIDCache schemas and columns:
- Workload-based schema optimization
- Column pruning for unused or rarely accessed fields
- Specialized indexes for frequently queried columns
- Schema evolution for backward compatibility
- Statistical metadata collection for schema optimization

These optimizations improve query performance, reduce storage requirements,
and enhance the overall efficiency of the ParquetCIDCache system.

**Classes:**
- `WorkloadType`: Enum representing different types of workloads.
- `ColumnStatistics`: Statistics for a single column in the schema.
- `SchemaProfiler`: Analyzes and profiles schema to identify optimization opportunities.
- `SchemaOptimizer`: Optimizer for Parquet schemas based on workload characteristics.
- `SchemaEvolutionManager`: Manages schema evolution for backward compatibility.
- `ParquetCIDCache`: Mock ParquetCIDCache class for integration purpose.
- `SchemaColumnOptimizationManager`: High-level manager for schema and column optimization.

**Functions:**
- `create_example_data()`: Create example data for demonstration purposes.

#### `cache/batch_operations.py`

Batch operations for ParquetCIDCache in tiered storage system.

This module provides efficient batch processing capability for the ParquetCIDCache,
implementing the first phase of performance optimizations from the performance
optimization roadmap.

**Classes:**
- `BatchOperationManager`: Manager for batch operations in ParquetCIDCache.

#### `cache/advanced_partitioning_strategies.py`

Advanced Partitioning Strategies for ParquetCIDCache.

This module implements sophisticated partitioning strategies for the ParquetCIDCache:
- Time-based partitioning for temporal access patterns
- Size-based partitioning to balance partition sizes
- Content-type based partitioning for workload specialization
- Hash-based partitioning for even distribution
- Dynamic partition management with adaptive strategies

These partitioning strategies help optimize data organization, query performance,
and resource utilization in the ParquetCIDCache system.

**Classes:**
- `PartitioningStrategy`: Enum representing different partitioning strategies.
- `PartitionInfo`: Information about a partition.
- `TimeBasedPartitionStrategy`: Partitions data based on time periods.
- `SizeBasedPartitionStrategy`: Partitions data to maintain balanced partition sizes.
- `ContentTypePartitionStrategy`: Partitions data based on content MIME type.
- `HashBasedPartitionStrategy`: Partitions data based on hash of a key for even distribution.
- `DynamicPartitionManager`: Manages partitioning strategies dynamically based on data characteristics.
- `AdvancedPartitionManager`: High-level manager for advanced partitioning strategies.

#### `cache/compression_encoding.py`

Compression and encoding optimizations for ParquetCIDCache.

This module provides advanced compression and encoding strategies
for optimizing metadata storage in ParquetCIDCache.

**Classes:**
- `CompressionProfile`: Profile for optimizing compression and encoding settings.
- `EncodingOptimizer`: Optimizer for specialized encodings and compression.
- `ColumnAnalyzer`: Analyzer for column data characteristics to inform encoding choices.
- `CompressionProfileSelector`: Selector for optimal compression profiles based on data characteristics.
- `ParquetCompressionManager`: Manager for optimizing Parquet compression and encoding.

#### `cache/semantic_cache.py`

Semantic Cache for similar query results.

This module provides a semantic caching system that can identify similar queries
based on their embedding vectors and reuse search results appropriately. This
significantly improves performance for repeated or similar searches.

Key features:
1. Vector-based similarity matching for queries
2. Tiered caching with both exact and approximate matches
3. Time-based and capacity-based eviction policies
4. Configurable similarity thresholds
5. Support for partial result reuse
6. Persistence options for cache state

**Classes:**
- `QueryVector`: Represents a query and its embedding vector for semantic comparison.
- `CacheEntry`: Represents a cached result with metadata.
- `SemanticCache`: Cache for storing and retrieving search results based on semantic similarity.

#### `cache/parquet_prefetch_integration.py`

Integration of read-ahead prefetching with ParquetCIDCache.

This module provides integration between the ParquetCIDCache and
the read-ahead prefetching system, enabling efficient prefetching
of content based on access patterns.

**Classes:**
- `PrefetchingParquetCIDCache`: ParquetCIDCache with integrated read-ahead prefetching capabilities.
- `ParquetCIDCacheFactory`: Factory for creating ParquetCIDCache instances with read-ahead prefetching.

#### `cache/probabilistic_data_structures.py`

Probabilistic data structures for memory-efficient operations on large datasets.

This module provides several memory-efficient data structures that provide approximate
answers with high accuracy:

1. BloomFilter: Space-efficient probabilistic data structure for set membership testing
   with no false negatives (but possible false positives)

2. HyperLogLog: Algorithm for cardinality estimation (counting unique elements)
   with minimal memory requirements

3. CountMinSketch: Probabilistic data structure for frequency estimation of elements
   in a data stream with sublinear space complexity

4. CuckooFilter: Space-efficient alternative to Bloom filters with support for deletion
   and better false positive rates at high occupancy

5. MinHash: Technique for quickly estimating similarity between sets
   using hash-based sampling

These data structures are particularly useful for large datasets where exact structures
would be too memory-intensive, but approximate answers are acceptable.

**Classes:**
- `HashFunction`: Hash function options for probabilistic data structures.
- `BloomFilter`: Space-efficient probabilistic data structure for set membership testing.
- `HyperLogLog`: Probabilistic algorithm for cardinality estimation.
- `CountMinSketch`: Probabilistic data structure for frequency estimation in data streams.
- `CuckooFilter`: Space-efficient probabilistic data structure for set membership testing with deletion support.
- `MinHash`: Technique for quickly estimating the Jaccard similarity between sets.
- `TopK`: Data structure for tracking top-k frequent elements in a data stream.
- `ProbabilisticDataStructureManager`: Manager class for creating and managing probabilistic data structures.
- `bitarray`: Simple fallback implementation when bitarray is not available.
- `MMH3Fallback`

#### `cache/zero_copy_interface.py`

Zero-copy access interface for ParquetCIDCache using Arrow C Data Interface.

This module implements efficient cross-process data sharing capabilities
for the ParquetCIDCache using Apache Arrow's C Data Interface and shared
memory, enabling zero-copy access to cache data from multiple processes.

**Classes:**
- `ZeroCopyManager`: Manager for zero-copy data sharing using Arrow C Data Interface.
- `ZeroCopyTable`: Wrapper for a shared Arrow table with zero-copy access.

#### `cache/async_operations_anyio.py`

Asynchronous operations for ParquetCIDCache using anyio.

This module provides asynchronous versions of ParquetCIDCache operations for improved
concurrency and responsiveness. It implements non-blocking I/O for Parquet operations
and maintains compatibility with any async backend (async-io, trio, etc.) through anyio.

**Classes:**
- `AsyncOperationManager`: Manager for asynchronous operations in ParquetCIDCache.
- `AsyncParquetCIDCache`: Async-compatible wrapper for ParquetCIDCache.

#### `cache/parallel_query_execution.py`

Parallel Query Execution module for ParquetCIDCache.

This module implements parallel query execution capabilities for ParquetCIDCache:
- Multi-threaded query execution for complex analytical operations
- Partition-parallel scanning for large datasets
- Worker pools for compute-intensive operations
- Thread allocation optimization based on query complexity
- Query planning for efficient execution paths

These optimizations significantly improve query performance on large datasets,
especially for complex analytical operations across multiple partitions.

**Classes:**
- `QueryType`: Enum representing different types of queries.
- `QueryPredicate`: Represents a filter predicate for a query.
- `QueryAggregation`: Represents an aggregation operation.
- `Query`: Represents a query to be executed.
- `QueryExecutionStatistics`: Collects and reports statistics about query execution.
- `PartitionExecutor`: Handles the execution of a query against a single partition.
- `QueryPlanner`: Plans and optimizes query execution across partitions.
- `ParallelQueryManager`: High-level manager for parallel query execution.
- `ThreadPoolManager`: Manages thread pools for query execution.
- `QueryCacheManager`: Manages query result caching.

#### `cache/read_ahead_prefetching.py`

Read-ahead prefetching implementation for ParquetCIDCache.

This module provides advanced prefetching capabilities that intelligently
load content before it's explicitly requested, reducing perceived latency.

**Classes:**
- `AccessPattern`: Tracks temporal and spatial access patterns for content prefetching.
- `PrefetchStrategy`: Base class for prefetching strategies.
- `SequentialPrefetchStrategy`: Prefetches content based on sequential access patterns.
- `TemporalPrefetchStrategy`: Prefetches content based on temporal access patterns.
- `HybridPrefetchStrategy`: Combines multiple prefetch strategies with weighted scoring.
- `ContentAwarePrefetchStrategy`: Prefetches content based on content relationships and metadata.
- `ReadAheadPrefetchManager`: Manager for read-ahead prefetching operations.

#### `cache/async_operations.py`

Asynchronous operations for ParquetCIDCache.

This module provides asynchronous versions of ParquetCIDCache operations for improved
concurrency and responsiveness. It implements non-blocking I/O for Parquet operations
and maintains compatibility with async-io-based applications.

**Classes:**
- `AsyncOperationManager`: Manager for asynchronous operations in ParquetCIDCache.
- `AsyncParquetCIDCache`: Async-compatible wrapper for ParquetCIDCache.

#### `cache/__init__.py`

Cache modules for IPFS Kit to improve performance and reduce redundant operations.

This package provides various caching mechanisms designed for different use cases:

1. Semantic Cache: For caching semantically similar search queries and results
2. Tiered Cache: For efficiently managing content across memory and disk
3. Content Cache: For caching IPFS content with CID-based retrieval
4. Batch Operations: For optimizing bulk operations with batching, coalescing, and deduplication
5. Zero-Copy Interface: For sharing data between processes without copying, using Arrow C Data Interface
6. Async Operations: For non-blocking cache operations with async-io support and thread pool management
7. Intelligent Cache: For predictive cache management using machine learning and access pattern analysis
8. Read-Ahead Prefetching: For proactively loading content before it's explicitly requested
9. Compression and Encoding: For optimizing data storage with efficient compression and encoding strategies
10. Schema and Column Optimization: For workload-based schema optimization, column pruning, and indexing
11. Advanced Partitioning Strategies: For intelligent data distribution across multiple partitions
12. Parallel Query Execution: For multi-threaded query execution with query planning and optimization
13. Probabilistic Data Structures: For memory-efficient operations on large datasets with controllable error rates

These caching mechanisms can significantly improve performance, especially
for repeated operations or operations with similar patterns of access.

### car_wal_manager.py

#### `car_wal_manager.py`

CAR-based WAL Manager using dag-cbor and multiformats

This replaces the Parquet-based WAL system with CAR (Content Addressable Archive) files
using IPLD and DAG-CBOR encoding for better IPFS integration.

**Classes:**
- `CARWALManager`: CAR-based Write-Ahead Log Manager

**Functions:**
- `get_car_wal_manager()`: Get global CAR WAL manager instance.

### clean_bucket_cli.py

#### `clean_bucket_cli.py`

Clean Bucket CLI for IPFS Kit.

This provides a simplified, working CLI for bucket operations using BucketVFSManager.

**Functions:**
- `create_parser()`: Create the argument parser for bucket operations.
- `sync_main()`: Synchronous entry point.

### cli.py

#### `cli.py`

IPFS-Kit CLI for the unified MCP dashboard.

Usage:
  python -m ipfs_kit_py.cli mcp start [--port 8004] [--foreground] [--server-path FILE]
  python -m ipfs_kit_py.cli mcp stop  [--port 8004]
  python -m ipfs_kit_py.cli mcp status [--port 8004]

**Classes:**
- `FastCLI`

**Functions:**
- `sync_main()`

### cli_commands.py

#### `cli_commands.py`

This module contains the implementation of the CLI commands.

### cli_old.py

#### `cli_old.py`

Command-line interface for IPFS Kit.

This module provides a command-line interface for interacting with IPFS Kit.

**Functions:**
- `main()`: Main function for the CLI.
- `colorize()`: Colorize text for terminal output.
- `setup_logging()`: Set up logging configuration.
- `parse_key_value()`: Parse a key=value string into a dictionary, with value type conversion.
- `handle_version_command()`: Handle the 'version' command with platform information.
- `parse_args()`: Parse command-line arguments.
- `handle_version_command()`: Handle the 'version' command to show version information.
- `handle_get_command()`: Handle the 'get' command with output file support.
- `handle_state_command()`: Handle the 'state' command to show program state information.
- `format_output()`: Format output according to specified format.
- `parse_kwargs()`: Parse command-specific keyword arguments from command-line arguments.
- `run_command()`: Run the specified command.
- `start_modular_mcp_server()`: Start the modular MCP server.
- `start_role_mcp_server()`: Start the MCP server with a specific role configuration.
- `main()`: Main entry point.
- `add_parallel_query_commands()`: Add commands for parallel query execution.
- `add_dashboard_commands()`: Add commands for unified dashboard operations.
- `add_schema_commands()`: Add commands for schema and column optimization.
- `handle_version_command()`: Handle the 'version' command with platform information.

### cli_secure_config.py

#### `cli_secure_config.py`

CLI commands for secure configuration management.

Provides command-line interface for:
- Enabling/disabling encryption
- Migrating plain configs to encrypted format
- Key rotation
- Encryption status checking

**Functions:**
- `cmd_status()`: Show encryption status.
- `cmd_migrate()`: Migrate config file to encrypted format.
- `cmd_migrate_all()`: Migrate all config files to encrypted format.
- `cmd_rotate_key()`: Rotate encryption key.
- `cmd_encrypt()`: Encrypt a specific config file.
- `cmd_decrypt()`: Decrypt and display a config file.
- `main()`: Main CLI entry point.

### cluster

#### `cluster/utils.py`

Utility functions for IPFS Kit cluster management.

**Functions:**
- `get_gpu_info()`: Get information about available GPUs.

#### `cluster/monitoring.py`

Monitoring and metrics collection for IPFS Kit clusters.

This module provides components for monitoring cluster health, collecting metrics,
and visualizing cluster performance.

**Classes:**
- `MetricsCollector`: Collects and stores metrics about cluster operation.
- `ClusterMonitor`: Monitors the health and performance of the IPFS cluster.

#### `cluster/distributed_coordination.py`

Distributed coordination mechanisms for IPFS Kit cluster management.

This module implements distributed coordination mechanisms for IPFS Kit clusters,
including member management, leader election, and consensus protocols.

**Classes:**
- `MembershipManager`: Manages cluster membership, tracking which peers are part of the cluster.
- `ClusterCoordinator`: Coordinates distributed operations across cluster nodes.

#### `cluster/role_manager.py`

Role-based architecture implementation for IPFS Kit cluster nodes.

This module defines the core role-based architecture components, including:
- Node roles (master, worker, leecher)
- Role-specific capabilities and optimizations
- Dynamic role detection and switching based on resources
- Secure authentication for cluster nodes

**Classes:**
- `NodeRole`: Enum defining the possible roles for a node in the cluster.
- `RoleManager`: Manages node roles in the IPFS cluster.

**Functions:**
- `detect_host_capabilities()`: Utility function to detect the capabilities of the host machine.

#### `cluster/cluster_manager.py`

Cluster Manager for IPFS Kit.

This module integrates all cluster management components into a unified interface,
providing a single point of access for role management, distributed coordination,
and monitoring capabilities.

**Classes:**
- `ClusterManager`: Unified manager for IPFS cluster operations.

#### `cluster/__init__.py`

Cluster Management Package for IPFS Kit.

This package provides advanced cluster management capabilities for IPFS Kit,
enabling efficient coordination and task distribution across nodes with different
roles (master, worker, leecher). It implements Phase 3B of the development roadmap.

Components:
- role_manager: Handles node role detection, switching, and optimization
- distributed_coordination: Manages cluster membership, leader election, and consensus
- monitoring: Provides health monitoring, metrics collection, and visualization
- cluster_manager: Integrates all components into a unified management system

### cluster_authentication.py

#### `cluster_authentication.py`

IPFS cluster authentication and security module for secure cluster communications.

This module provides secure authentication mechanisms for IPFS cluster nodes, including:
- X.509 certificate management for TLS connections
- UCAN-based capability delegation
- Role-based access control
- Authentication token management

The module supports the role-based architecture with different security profiles for
master, worker, and leecher nodes. Master nodes maintain the Certificate Authority (CA)
and issue certificates to worker nodes. All inter-node communications are encrypted
with TLS to prevent eavesdropping and authenticated to prevent malicious nodes from
joining the cluster.

**Classes:**
- `AuthenticationError`: Base class for authentication-related errors.
- `CertificateError`: Error related to certificate operations.
- `UCANError`: Error related to UCAN operations.
- `AccessDeniedError`: Error when access is denied due to insufficient permissions.
- `TokenError`: Error related to authentication token operations.
- `ClusterAuthManager`: Manages authentication and security for IPFS cluster nodes.

### cluster_coordinator.py

#### `cluster_coordinator.py`

**Classes:**
- `NodeRole`: Enumeration of node roles in the cluster.
- `NodeStatus`: Enumeration of node statuses in the cluster.
- `TaskStatus`: Enumeration of task statuses.
- `NodeResources`: Class for tracking a node's resources.
- `NodeInfo`: Class for tracking information about a node in the cluster.
- `Task`: Class representing a task in the distributed task system.
- `ClusterCoordinator`: Class for coordinating nodes and tasks in a distributed cluster.

### cluster_dynamic_roles.py

#### `cluster_dynamic_roles.py`

Dynamic role switching for IPFS cluster nodes based on available resources (Phase 3B).

This module implements the ability for nodes to dynamically change their roles based on:
- Available resources (memory, disk, CPU, bandwidth)
- Network conditions
- Workload changes
- Environmental factors
- User preferences

Three primary roles are supported:
- master: Orchestration, content management, cluster coordination
- worker: Processing, content pinning, task execution
- leecher: Lightweight consumption with minimal resource contribution

The module provides both automatic resource-based role optimization and
user-controlled role transitions with appropriate validation.

**Classes:**
- `ClusterDynamicRoles`: Implements dynamic role switching for IPFS cluster nodes based on resources.

### cluster_management.py

#### `cluster_management.py`

Cluster management module for integrating ClusterCoordinator with IPFSLibp2pPeer.

This module provides a high-level interface for cluster management functionality,
integrating the ClusterCoordinator (responsible for task distribution and node management)
with IPFSLibp2pPeer (responsible for direct peer-to-peer communication) to create
a complete distributed coordination system.

**Classes:**
- `ClusterManager`: High-level manager integrating ClusterCoordinator and IPFSLibp2pPeer.
- `ArrowClusterState`

### cluster_monitoring.py

#### `cluster_monitoring.py`

Monitoring and management module for IPFS cluster.

This module implements the monitoring and management capabilities (Phase 3B Milestone 3.6), including:
- Cluster management dashboard
- Health monitoring and alerts
- Performance visualization
- Configuration management tools
- Resource tracking
- Automated recovery procedures

The monitoring system collects metrics from all cluster nodes, analyzes them for threshold
violations, generates alerts, and takes automated recovery actions when necessary.

**Classes:**
- `ClusterMonitoring`: Handles monitoring and management of IPFS cluster nodes.
- `ClusterDashboard`: Provides a web dashboard for monitoring and managing IPFS cluster.

### cluster_state.py

#### `cluster_state.py`

Arrow-based cluster state management for IPFS distributed coordination.

This module provides a shared, persistent, and efficient state store for
cluster management using Apache Arrow and its Plasma shared memory system.
The state store enables zero-copy IPC across processes and languages,
making it ideal for distributed coordination.

**Classes:**
- `ClusterStateInterface`: Abstract base class for cluster state management implementations.
- `ArrowClusterState`: Arrow-based cluster state with shared memory access.

**Functions:**
- `create_test_task_data()`: Create a task data dictionary with proper field types for tests.
- `create_cluster_state_schema()`: Create Arrow schema for cluster state.

### cluster_state_anyio.py

#### `cluster_state_anyio.py`

AnyIO-compatible implementation of Arrow-based cluster state management.

This module provides asynchronous versions of the ArrowClusterState operations,
supporting both async-io and trio via AnyIO. It wraps the synchronous methods
with async equivalents for better performance in async contexts.

**Classes:**
- `ArrowClusterStateAnyIO`: AnyIO-compatible cluster state management system.

### cluster_state_helpers.py

#### `cluster_state_helpers.py`

Helper functions for accessing and querying the Arrow-based cluster state.

This module provides high-level functions for common patterns when working
with the cluster state from external processes.

**Functions:**
- `get_state_path_from_metadata()`: Find cluster state path from standard locations.
- `connect_to_state_store()`: Load metadata from the cluster state directory.
- `get_cluster_state()`: Get the current cluster state as an Arrow table from parquet file.
- `get_cluster_state_as_dict()`: Get the current cluster state as a dictionary.
- `get_cluster_metadata()`: Get basic cluster metadata.
- `get_all_nodes()`: Get all nodes in the cluster.
- `get_node_by_id()`: Get a specific node by ID.
- `find_nodes_by_role()`: Find all nodes with a specific role.
- `find_nodes_by_capability()`: Find all nodes with a specific capability.
- `find_nodes_with_gpu()`: Find all nodes with available GPUs.
- `get_all_tasks()`: Get all tasks in the cluster.
- `get_task_by_id()`: Get a specific task by ID.
- `find_tasks_by_status()`: Find all tasks with a specific status.
- `find_tasks_by_type()`: Find all tasks of a specific type.
- `find_tasks_by_node()`: Find all tasks assigned to a specific node.
- `get_all_content()`: Get all content items in the cluster.
- `find_content_by_cid()`: Find a content item by CID.
- `find_content_by_provider()`: Find all content items available from a specific provider.
- `get_cluster_status_summary()`: Get a summary of cluster status with key metrics.
- `get_cluster_state_as_pandas()`: Get the cluster state as pandas DataFrames.
- `find_tasks_by_resource_requirements()`: Find tasks that require specific resources.
- `find_available_node_for_task()`: Find a suitable node that can execute a specific task based on its resource requirements.
- `get_task_execution_metrics()`: Generate metrics about task execution in the cluster.
- `find_orphaned_content()`: Find content items that have no active references from tasks.
- `get_network_topology()`: Get the network topology of the cluster.
- `export_state_to_json()`: Export the cluster state to a JSON file for external analysis.
- `estimate_time_to_completion()`: Estimate the time to completion for a given task based on historical data.

### cluster_state_sync.py

#### `cluster_state_sync.py`

Distributed state synchronization for IPFS cluster nodes (Phase 3B).

This module implements distributed state synchronization using:
- Conflict-free replicated data types (CRDT) for distributed state
- Automatic state reconciliation
- Causality tracking with vector clocks
- Gossip-based state propagation
- Eventually consistent distributed state
- Partial state updates and differential sync

**Classes:**
- `VectorClock`: Implementation of vector clocks for tracking causality across distributed nodes.
- `StateCRDT`: CRDT implementation for distributed state with automatic conflict resolution.
- `ClusterStateSync`: Manages distributed state synchronization across a cluster of nodes.

### compat.py

#### `compat.py`

IPFS Kit Compatibility Layer for gRPC Deprecation

This module provides backwards compatibility during the gRPC deprecation transition.

**Classes:**
- `DeprecationWarning`: Custom deprecation warning for gRPC components.

**Functions:**
- `grpc_deprecation_warning()`: Issue deprecation warning for gRPC components.
- `get_routing_client()`: Get routing client with deprecation warning.
- `get_routing_server()`: Get routing server with deprecation warning.

### config.py

#### `config.py`

**Functions:**
- `get_config()`: Reads the main configuration file.
- `save_config()`: Saves the main configuration file.
- `get_config_as_json()`: Returns the configuration as a JSON string for the dashboard.
- `save_config_from_json()`: Saves the configuration from a JSON string from the dashboard.

### config_manager.py

#### `config_manager.py`

**Classes:**
- `ConfigManager`: Manages reading and writing of YAML configuration files.

### config_synapse_sdk.py

#### `config_synapse_sdk.py`

Synapse SDK configuration module for ipfs_kit_py.

This module handles configuration management for the Synapse SDK integration,
including network settings, wallet management, payment configuration, and
storage preferences.

Usage:
    from config_synapse_sdk import config_synapse_sdk
    
    config = config_synapse_sdk(metadata={
        "network": "calibration",
        "private_key": "0x...",
        "auto_approve": True
    })
    
    config.setup_configuration()
    settings = config.get_configuration()

**Classes:**
- `SynapseConfigurationError`: Error in Synapse SDK configuration.
- `config_synapse_sdk`: Class for managing Synapse SDK configuration.

**Functions:**
- `main()`: Main function for testing configuration module.

### content_aware_prefetch.py

#### `content_aware_prefetch.py`

Content-aware prefetching system for IPFS content.

This module implements sophisticated type-specific prefetching strategies for different
content types to optimize access patterns based on content characteristics.

**Classes:**
- `ContentTypeAnalyzer`: Analyzes content types for sophisticated type-specific prefetching strategies.
- `ContentAwarePrefetchManager`: Manages content-aware prefetching based on content type analysis.

**Functions:**
- `create_content_aware_prefetch_manager()`: Create and configure a content-aware prefetch manager.

### content_manager.py

#### `content_manager.py`

**Classes:**
- `ContentManager`

### core

#### `core/__init__.py`

IPFS-Kit Core Module with Integrated JIT Import Management

This core module provides the foundational import management system for the entire
ipfs_kit_py package, enabling fast startup times and lazy loading of heavy dependencies.

The JIT (Just-in-Time) import system is integrated at the package core level to:
- Minimize startup time by deferring heavy imports
- Provide consistent import patterns across CLI, MCP server, and daemon
- Enable graceful fallbacks for missing dependencies
- Monitor import performance and provide metrics

Usage:
    # Import the core JIT system
    from ipfs_kit_py.core import jit_manager
    
    # Check feature availability (fast)
    if jit_manager.is_available('enhanced_features'):
        # Load modules only when needed
        enhanced_index = jit_manager.get_module('enhanced_pin_index')
    
    # Use decorators for automatic JIT loading
    from ipfs_kit_py.core import lazy_import
    
    @lazy_import('enhanced_features')
    def get_enhanced_pin_manager():
        from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
        return get_global_enhanced_pin_index()

**Classes:**
- `CoreJITManager`: Core JIT manager that integrates deeply with the package infrastructure.

**Functions:**
- `require_feature()`: Decorator that ensures a feature is available before executing a function.
- `optional_feature()`: Decorator that gracefully handles missing features by returning a fallback.
- `core_lazy_import()`: Core-level lazy import decorator that defers module loading until first use.
- `jit_import()`: Core JIT import function with simplified interface.
- `jit_import_from()`: Core JIT import from function with simplified interface.
- `lazy_import()`: Core lazy import decorator.
- `get_jit_imports()`: Get the JIT imports instance.

### credential_manager.py

#### `credential_manager.py`

Credential Manager for ipfs_kit_py.

This module provides secure credential management for various storage backends
including IPFS, IPFS Cluster, S3, Storacha, and Filecoin.

**Classes:**
- `CredentialManager`: Manages credentials for different storage backends.

### daemon_cli.py

#### `daemon_cli.py`

CLI commands for the Enhanced Intelligent Daemon Manager.

This provides CLI integration for the metadata-driven daemon operations.

**Functions:**
- `daemon()`: Enhanced intelligent daemon management commands.
- `start()`: Start the enhanced intelligent daemon.
- `stop()`: Stop the intelligent daemon.
- `status()`: Show daemon status and metadata insights.
- `insights()`: Show metadata insights and operational intelligence.
- `health()`: Check overall system health based on metadata.
- `sync()`: Force synchronization of dirty backends.

### daemon_config_manager.py

#### `daemon_config_manager.py`

IPFS Kit Daemon Configuration Manager

This module provides comprehensive daemon configuration management for IPFS Kit,
including IPFS, Lotus, and other related daemons. It handles configuration
validation, daemon startup/shutdown, and health monitoring.

**Classes:**
- `DaemonConfigManager`: Comprehensive daemon configuration manager for IPFS Kit.

**Functions:**
- `check_daemon_configuration()`: Standalone function to check daemon configuration.
- `configure_daemon()`: Standalone function to configure a daemon.
- `start_daemon()`: Standalone function to start a daemon.
- `is_daemon_running()`: Standalone function to check if daemon is running.

### direct_mcp_server.py

#### `direct_mcp_server.py`

This module serves as the primary entry point for the MCP server as mentioned in the roadmap.
It implements a FastAPI server with endpoints for all MCP components including storage backends,
authentication, and now AI/ML capabilities.

Updated with AI/ML integration based on MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).

**Functions:**
- `create_app()`: Create and configure the FastAPI application.
- `parse_args()`: Parse command line arguments.
- `main()`: Run the MCP server.

### disk_cache.py

#### `disk_cache.py`

**Classes:**
- `DiskCache`: Disk-based persistent cache for IPFS content.

### disk_cache_anyio.py

#### `disk_cache_anyio.py`

**Classes:**
- `DiskCacheAnyIO`: Disk-based persistent cache for IPFS content with AnyIO support.

### enhanced_backend_manager.py

#### `enhanced_backend_manager.py`

Enhanced Backend Manager for IPFS Kit Storage System

This module extends the basic backend manager to include comprehensive
policy management and enhanced backend representation for the MCP dashboard.

**Classes:**
- `EnhancedBackendManager`: Enhanced backend manager with comprehensive policy support.

### enhanced_bucket_index.py

#### `enhanced_bucket_index.py`

Enhanced Bucket Index System for Virtual Filesystem Discovery

Provides quick discovery and analytics for virtual filesystems stored in ~/.ipfs_kit/
Similar architecture to the pin index for consistent performance and usability.

**Classes:**
- `BucketMetadata`: Metadata for a virtual filesystem bucket.
- `EnhancedBucketIndex`: Enhanced bucket index system for virtual filesystem discovery.

**Functions:**
- `format_size()`: Format size in bytes to human-readable format.

### enhanced_bucket_index_fixed.py

#### `enhanced_bucket_index_fixed.py`

Enhanced Bucket Index System for Virtual Filesystem Discovery

Provides quick discovery and analytics for virtual filesystems stored in ~/.ipfs_kit/
Similar architecture to the pin index for consistent performance and usability.

**Classes:**
- `BucketMetadata`: Metadata for a virtual filesystem bucket.
- `EnhancedBucketIndex`: Enhanced bucket index system for virtual filesystem discovery.

**Functions:**
- `format_size()`: Format size in bytes to human-readable format.

### enhanced_daemon_manager.py

#### `enhanced_daemon_manager.py`

**Classes:**
- `EnhancedDaemonManager`

### enhanced_fsspec.py

#### `enhanced_fsspec.py`

Enhanced FSSpec implementation with multiple storage backend support.

This module extends the IPFS FSSpec interface to support multiple storage backends
including IPFS, Filecoin (via Lotus), Storacha, and Synapse SDK.

**Classes:**
- `IPFSFileSystem`: Enhanced FSSpec-compatible filesystem supporting multiple storage backends.

**Functions:**
- `create_synapse_filesystem()`: Create a Synapse SDK filesystem instance.
- `create_ipfs_filesystem()`: Create an IPFS filesystem instance.
- `create_filecoin_filesystem()`: Create a Filecoin filesystem instance.
- `create_storacha_filesystem()`: Create a Storacha filesystem instance.

### enhanced_mcp_server.py

#### `enhanced_mcp_server.py`

Enhanced MCP Server with Service Management

This module provides an enhanced MCP server that supports service management,
monitoring, and uses the metadata-first approach.

**Classes:**
- `EnhancedMCPServer`: Enhanced MCP Server with service management capabilities.

### enhanced_mcp_server_real.py

#### `enhanced_mcp_server_real.py`

Enhanced MCP server implementation with real storage backends.

This script improves on the previous MCP server by properly integrating
with real storage backends where possible, with graceful fallback to mock mode.

**Functions:**
- `source_credentials()`: Source credentials from mcp_credentials.sh script.
- `check_ipfs_daemon()`: Check if IPFS daemon is running.
- `start_ipfs_daemon()`: Start the IPFS daemon if not running.
- `run_ipfs_command()`: Run an IPFS command and return the result.
- `check_cloud_provider()`: Check if a cloud provider is available by running a test command.
- `setup_extensions()`: Set up storage backend extensions with proper fallbacks.
- `add_fallback_implementations()`: Add fallback implementations for all storage backends.
- `enhance_backend_implementations()`: Enhance the existing backend implementations.

### enhanced_pin_api.py

#### `enhanced_pin_api.py`

Enhanced Pin Metadata API for IPFS Kit

This module provides FastAPI endpoints for the enhanced pin metadata index
that integrates with ipfs_kit_py's virtual filesystem and storage management.

Endpoints:
- GET /api/v0/enhanced-pins/status - Get index status and capabilities
- GET /api/v0/enhanced-pins/metrics - Get comprehensive metrics  
- GET /api/v0/enhanced-pins/vfs - Get VFS analytics
- GET /api/v0/enhanced-pins/pins - List pins with details
- GET /api/v0/enhanced-pins/track/{cid} - Track specific pin
- GET /api/v0/enhanced-pins/analytics - Get storage analytics
- POST /api/v0/enhanced-pins/record - Record pin access

**Classes:**
- `PinAccessRequest`
- `PinDetailsResponse`

**Functions:**
- `get_enhanced_pin_index()`: Get or create the global enhanced pin index.

### enhanced_storacha_kit.py

#### `enhanced_storacha_kit.py`

Enhanced Storacha Kit for IPFS Kit.

This module provides comprehensive integration with Storacha (formerly Web3.Storage)
with robust endpoint management, connection handling, and fallback mechanisms.

**Classes:**
- `IPFSValidationError`: Error when input validation fails.
- `IPFSContentNotFoundError`: Content with specified CID not found.
- `IPFSConnectionError`: Error when connecting to services.
- `IPFSError`: Base class for all IPFS-related exceptions.
- `IPFSTimeoutError`: Timeout when communicating with services.
- `StorachaConnectionError`: Error when connecting to Storacha services.
- `StorachaAuthenticationError`: Error with Storacha authentication.
- `StorachaAPIError`: Error with Storacha API.
- `storacha_kit`

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### enhanced_vfs_extractor.py

#### `enhanced_vfs_extractor.py`

Enhanced IPFS VFS Extractor with CLI Integration

Integrates with ipfs_kit_py CLI to consult pin metadata index and use
multiprocessing for optimized parallel downloads from fastest backends.

**Classes:**
- `EnhancedIPFSVFSExtractor`: Enhanced VFS extractor with CLI integration and backend optimization.

**Functions:**
- `main()`: Enhanced CLI interface with ipfs_kit_py integration.

### error.py

#### `error.py`

Error handling for IPFS Kit.

This module defines the error hierarchy for IPFS Kit operations
and provides utility functions for error handling.

**Classes:**
- `IPFSError`: Base class for all IPFS-related exceptions.
- `IPFSConnectionError`: Error when connecting to IPFS daemon.
- `IPFSTimeoutError`: Timeout when communicating with IPFS daemon.
- `IPFSContentNotFoundError`: Content with specified CID not found.
- `IPFSValidationError`: Input validation failed.
- `IPFSConfigurationError`: IPFS configuration is invalid or missing.
- `IPFSPinningError`: Error during content pinning/unpinning.

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle exceptions and update result dictionary.
- `perform_with_retry()`: Perform operation with exponential backoff retry.

### filecoin_storage.py

#### `filecoin_storage.py`

Filecoin Storage API integration for direct interaction with Filecoin storage providers.

This module provides a simplified interface for storing and retrieving data using
Filecoin storage providers, with support for automated miner selection and deal management.

**Classes:**
- `FilecoinValidationError`: Error when input validation fails.
- `FilecoinContentNotFoundError`: Content with specified CID not found.
- `FilecoinConnectionError`: Error when connecting to Filecoin services.
- `FilecoinError`: Base class for all Filecoin-related exceptions.
- `FilecoinTimeoutError`: Timeout when communicating with Filecoin services.
- `filecoin_storage`: Class for interacting with Filecoin storage providers.

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle error and update result dict.

### filesystem_journal.py

#### `filesystem_journal.py`

Filesystem Journal for IPFS Kit.

This module implements a filesystem journal to ensure data consistency and
recovery for the virtual filesystem in case of unexpected shutdowns or power outages.
It works alongside the Write-Ahead Log (WAL) but focuses specifically on the
filesystem metadata and structure.

Key features:
1. Transaction-based journaling of filesystem operations
2. Atomic operation support through write-ahead journaling
3. Automatic recovery on startup
4. Periodic checkpointing
5. Multi-tier storage integration

**Classes:**
- `JournalOperationType`: Types of filesystem operations tracked in the journal.
- `JournalEntryStatus`: Status values for journal entries.
- `FilesystemJournal`: Transaction-based filesystem journal for the IPFS virtual filesystem.
- `FilesystemJournalManager`: Manager for integrating the FilesystemJournal with a filesystem implementation.

### fixed_get_filesystem.py

#### `fixed_get_filesystem.py`

**Functions:**
- `placeholder_function()`: Placeholder function

### fixed_high_level_api.py

#### `fixed_high_level_api.py`

**Functions:**
- `placeholder_function()`: Placeholder function

### fs_journal_backends.py

#### `fs_journal_backends.py`

Filesystem Journal Backend Integrations for IPFS Kit.

This module provides backend integrations for the filesystem journal,
enabling it to work with multiple storage backends like memory cache,
disk cache, IPFS, IPFS cluster, S3, Storacha, Filecoin, HuggingFace,
and other backends through a unified interface.

This integration enables:
1. Tracking operations across multiple tiers in the storage hierarchy
2. Ensuring atomic operations with transaction safety
3. Providing consistent recovery mechanisms across backends
4. Supporting migration between storage tiers

**Classes:**
- `StorageBackendType`: Enum-like class for storage backend types.
- `TieredStorageJournalBackend`: Backend integration for tiered storage systems.
- `TieredJournalManagerFactory`: Factory for creating and configuring tiered journal managers.

### fs_journal_cli.py

#### `fs_journal_cli.py`

Command-line interface for Filesystem Journal functionality.

This module adds filesystem journal commands to the IPFS Kit CLI.

**Functions:**
- `register_fs_journal_commands()`: Register filesystem journal commands with the CLI.
- `handle_fs_journal_enable()`: Handle the 'fs-journal enable' command.
- `handle_fs_journal_status()`: Handle the 'fs-journal status' command.
- `handle_fs_journal_list()`: Handle the 'fs-journal list' command.
- `handle_fs_journal_checkpoint()`: Handle the 'fs-journal checkpoint' command.
- `handle_fs_journal_recover()`: Handle the 'fs-journal recover' command.
- `handle_fs_journal_mount()`: Handle the 'fs-journal mount' command.
- `handle_fs_journal_mkdir()`: Handle the 'fs-journal mkdir' command.
- `handle_fs_journal_write()`: Handle the 'fs-journal write' command.
- `handle_fs_journal_read()`: Handle the 'fs-journal read' command.
- `handle_fs_journal_rm()`: Handle the 'fs-journal rm' command.
- `handle_fs_journal_mv()`: Handle the 'fs-journal mv' command.
- `handle_fs_journal_ls()`: Handle the 'fs-journal ls' command.
- `handle_fs_journal_export()`: Handle the 'fs-journal export' command.

### fs_journal_integration.py

#### `fs_journal_integration.py`

Filesystem Journal Integration for IPFS Kit.

This module integrates the Filesystem Journal with the IPFS Kit high-level API,
enabling robust journaling of filesystem operations to ensure data consistency
and recovery in case of unexpected shutdowns.

**Classes:**
- `IPFSFilesystemInterface`: Adapter class that provides the filesystem interface expected by FilesystemJournalManager.
- `FilesystemJournalIntegration`: Integrates the FilesystemJournal with IPFS Kit's high-level API,

**Functions:**
- `enable_filesystem_journaling()`: Enable filesystem journaling for an existing API instance.

### fs_journal_monitor.py

#### `fs_journal_monitor.py`

Filesystem Journal Monitoring and Visualization for IPFS Kit.

This module provides monitoring and visualization tools for the filesystem journal,
enabling tracking of journal operations, storage tier migrations, and recovery status.
It helps administrators and developers understand the health, performance and usage
patterns of the filesystem journal and tiered storage backends.

Key features:
1. Journal operation monitoring and statistics
2. Tiered storage migration visualization
3. Recovery performance tracking
4. Health and performance dashboards
5. Alert generation for potential issues

**Classes:**
- `JournalHealthMonitor`: Monitors the health and performance of the filesystem journal.
- `JournalVisualization`: Visualization tools for the filesystem journal.

**Functions:**
- `main()`: Command-line interface for journal visualization.

### fs_journal_replication.py

#### `fs_journal_replication.py`

Metadata Replication Policy for Filesystem Journal.

This module implements a comprehensive replication policy for filesystem metadata
to enable both horizontal scaling and disaster recovery. It builds on the existing
filesystem journal and distributed state synchronization infrastructure.

Key features:
1. Multi-node metadata replication with configurable consistency levels
2. Progressive redundancy across storage tiers
3. Automatic failover and recovery mechanisms
4. Distributed checkpoints for disaster recovery
5. CRDT-based conflict resolution for concurrent modifications
6. Vector clock-based causality tracking
7. Peer discovery and gossip-based metadata propagation

**Classes:**
- `ReplicationLevel`: Replication consistency levels.
- `ReplicationStatus`: Status of replication operations.
- `MetadataReplicationManager`: Manager for replicating filesystem metadata across nodes and storage tiers.
- `DummySyncManager`

**Functions:**
- `create_replication_manager()`: Factory function to create a properly configured MetadataReplicationManager.

### ftp_kit.py

#### `ftp_kit.py`

FTP Kit for IPFS-Kit Virtual Filesystem

This module provides FTP/FTPS-based storage backend for IPFS-Kit VFS,
enabling remote file storage and retrieval via FTP protocol with optional TLS encryption.

Key Features:
- FTP and FTPS (FTP over TLS) support
- Passive and active FTP modes
- Directory creation and management
- Bucket-based file organization
- Connection pooling and retry logic
- VFS integration for content-addressed storage

**Classes:**
- `FTPKit`: FTP storage backend for IPFS-Kit virtual filesystem.

**Functions:**
- `log_operation()`: Log FTP operation with structured details.
- `validate_ftp_config()`: Validate FTP configuration.
- `test_ftp_connection()`: Test FTP connection with given configuration.

### gdrive_kit.py

#### `gdrive_kit.py`

Google Drive Kit for IPFS Kit.

This module provides comprehensive integration with Google Drive API
with robust authentication, file management, and introspection capabilities.

**Classes:**
- `IPFSValidationError`: Error when input validation fails.
- `IPFSContentNotFoundError`: Content with specified CID not found.
- `IPFSConnectionError`: Error when connecting to services.
- `IPFSError`: Base class for all IPFS-related exceptions.
- `IPFSTimeoutError`: Timeout when communicating with services.
- `GDriveConnectionError`: Error when connecting to Google Drive services.
- `GDriveAuthenticationError`: Error with Google Drive authentication.
- `GDriveAPIError`: Error with Google Drive API.
- `GDriveQuotaError`: Error when Google Drive quota is exceeded.
- `gdrive_kit`

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### git_vfs_translation.py

#### `git_vfs_translation.py`

Git VFS Translation Layer for IPFS-Kit

This module provides a translation layer between Git repositories and IPFS-Kit's
virtual filesystem, allowing seamless integration between Git metadata and VFS
content-addressed storage.

Key Features:
- Analyze .git repository metadata 
- Map Git commits to VFS versions
- Translate Git tree objects to VFS buckets
- Convert Git file tracking to VFS file metadata
- Maintain dual representation (Git + VFS)
- Support for GitHub/HuggingFace repository integration

**Classes:**
- `GitVFSTranslationLayer`: Translation layer between Git repositories and VFS content-addressed storage.

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.

### git_vfs_translator.py

#### `git_vfs_translator.py`

Git VFS Translation Layer for IPFS-Kit

This module provides a translation layer between Git metadata and IPFS-Kit's virtual filesystem.
It handles the mapping between Git's line-based diff system and IPFS-Kit's content-addressed
block storage, maintaining additional VFS metadata alongside Git's native metadata.

Key Features:
- Maps Git commits to VFS snapshots
- Converts Git diff metadata to VFS block change metadata
- Maintains .ipfs_kit folder structure within Git repositories
- Handles HEAD tracking and filesystem mount points
- Preserves VFS metadata during Git operations
- Supports bidirectional translation (Git ↔ VFS)

**Classes:**
- `VFSFileMetadata`: Extended VFS metadata for files beyond Git's tracking.
- `VFSSnapshot`: VFS representation of a Git commit.
- `GitVFSTranslator`: Translation layer between Git repositories and IPFS-Kit VFS.

### github_kit.py

#### `github_kit.py`

GitHub Kit - Interface to GitHub repositories as virtual filesystem buckets

This module treats GitHub repositories as buckets in the virtual filesystem,
with the username serving as the peerID for local "forks" of content.
Provides seamless integration between GitHub repos and IPFS-Kit's VFS.

Key Concepts:
- GitHub repos = VFS buckets
- Username = peerID for local content forks  
- Dataset/ML model repos labeled appropriately in VFS
- Seamless transition between GitHub and local IPFS storage
- Git VFS translation layer for metadata mapping

**Classes:**
- `GitHubKit`: GitHub repository interface for IPFS-Kit virtual filesystem.

### graphql_schema.py

#### `graphql_schema.py`

GraphQL schema for IPFS Kit.

This module defines the GraphQL schema and resolvers for the IPFS Kit API,
enabling flexible client-side querying capabilities.

Key features:
1. Unified GraphQL schema for all IPFS Kit operations
2. Type-safe queries with introspection
3. Efficient data fetching with field selection
4. Complex nested queries and relationships
5. Mutations for content management operations
6. Subscriptions for real-time updates (if supported)

**Classes:**
- `IPFSMetadata`: Metadata for IPFS content.
- `PinInfo`: Information about a pinned CID.
- `IPFSContent`: Representation of IPFS content.
- `DirectoryItem`: An item in a directory listing.
- `PeerInfo`: Information about a connected peer.
- `ClusterPeerInfo`: Information about a cluster peer.
- `ClusterPinStatus`: Status of a pin in the cluster.
- `IPNSInfo`: Information about an IPNS name.
- `KeyInfo`: Information about a key.
- `AIModel`: Information about an AI model.
- `AIDataset`: Information about an AI dataset.
- `Query`: Root query type for IPFS operations.
- `AddContentMutation`: Mutation to add content to IPFS.
- `PinContentMutation`: Mutation to pin content in IPFS.
- `UnpinContentMutation`: Mutation to unpin content in IPFS.
- `PublishIPNSMutation`: Mutation to publish a name to IPNS.
- `GenerateKeyMutation`: Mutation to generate a new key.
- `ClusterPinMutation`: Mutation to pin content across the IPFS cluster.
- `Mutation`: Root mutation type for IPFS operations.
- `ObjectType`
- `Mutation`
- `Field`
- `ID`
- `String`
- `Int`
- `Float`
- `Boolean`
- `GrapheneList`
- `Schema`
- `Arguments`
- `Arguments`
- `Arguments`
- `Arguments`
- `Arguments`
- `Arguments`

**Functions:**
- `check_graphql_availability()`: Check if GraphQL is available and return status.

### graphrag.py

#### `graphrag.py`

GraphRAG Search Engine for IPFS Kit.

This module provides advanced search capabilities for VFS/MFS content
using GraphRAG, vector search, and SPARQL queries.

**Classes:**
- `GraphRAGSearchEngine`: Advanced search engine with GraphRAG, vector search, and SPARQL.

### health_manager.py

#### `health_manager.py`

**Classes:**
- `HealthManager`

### hierarchical_storage_methods.py

#### `hierarchical_storage_methods.py`

Hierarchical storage management methods to be added to IPFSFileSystem.

These methods implement tiered storage management, content integrity verification,
replication policies, and tier health monitoring.

Includes comprehensive integration with all storage backends:
- Memory and Disk (fastest tiers)
- IPFS and IPFS Cluster (distributed content-addressed storage)
- S3 (cloud object storage)
- Storacha (Web3.Storage)
- Filecoin (long-term decentralized storage)
- HuggingFace Hub (ML model repository)
- Lassie (Filecoin retriever)
- Parquet (columnar file format)
- Arrow (memory-efficient data sharing)

**Functions:**

### high_level_api

#### `high_level_api/libp2p_integration.py`

LibP2P integration for the high-level API.

This module extends the IPFSSimpleAPI with libp2p capabilities when available.

#### `high_level_api/libp2p_integration_anyio.py`

LibP2P integration for the high-level API with AnyIO support.

This module extends the IPFSSimpleAPI with libp2p capabilities when available,
using AnyIO for backend-agnostic async operations.

**Functions:**
- `extend_high_level_api_class_anyio()`: Extend the IPFSSimpleAPI class with libp2p peer discovery functionality using AnyIO.
- `apply_high_level_api_integration()`: Apply the High-Level API integration using dependency injection with AnyIO support.

#### `high_level_api/webrtc_benchmark_helpers.py`

WebRTC Benchmark Helper Functions for High-Level API

This module provides helper functions for the IPFSSimpleAPI class to handle
WebRTC benchmarking operations through the CLI.

**Classes:**
- `WebRTCBenchmarkIntegration`: Integration helpers for WebRTC benchmarking with IPFSSimpleAPI.

#### `high_level_api/webrtc_benchmark_helpers_anyio.py`

WebRTC Benchmark Helper Functions for High-Level API with AnyIO

This module provides helper functions for the IPFSSimpleAPI class to handle
WebRTC benchmarking operations through the CLI, using AnyIO for backend-agnostic
async operations.

**Classes:**
- `WebRTCBenchmarkIntegrationAnyIO`: Integration helpers for WebRTC benchmarking with IPFSSimpleAPI using AnyIO.

#### `high_level_api/__init__.py`

High-level API helper modules for IPFS Kit

**Classes:**
- `IPFSSimpleAPI`: Functional stub implementation of IPFSSimpleAPI.
- `IPFSSimpleAPI`: Functional stub implementation of IPFSSimpleAPI.

### high_level_api.py

#### `high_level_api.py`

High-Level API for IPFS Kit.

This module provides a simplified, user-friendly API for common IPFS operations,
with declarative configuration and plugin architecture for extensibility.

Key features:
1. Simplified API: High-level methods for common operations
2. Declarative Configuration: YAML/JSON configuration support
3. Plugin Architecture: Extensible design for custom functionality
4. Multi-language Support: Generates SDKs for Python, JavaScript, and Rust
5. Unified Interface: Consistent interface across all components

This high-level API serves as the main entry point for most users,
abstracting away the complexity of the underlying components.

API Stability:
The API is divided into stability levels that indicate compatibility guarantees:
- @stable_api: Methods won't change within the same major version
- @beta_api: Methods are nearly stable but may change in minor versions
- @experimental_api: Methods may change at any time

See docs/api_stability.md for more details on API versioning and stability.

**Classes:**
- `IPFSSimpleAPI`: Simplified high-level API for IPFS operations.
- `PluginBase`: Base class for plugins.
- `IPFSClient`: Client for interacting with IPFS Kit.
- `PluginBase`: Base class for plugins.
- `MockIPFSFileSystem`
- `NoopMetrics`
- `IPFSConfigurationError`
- `IPFSError`
- `IPFSValidationError`

**Functions:**
- `get_benchmark_helper()`: Get appropriate WebRTC benchmark helper based on current async backend.

### high_level_api_fixed.py

#### `high_level_api_fixed.py`

**Functions:**
- `placeholder_function()`: Placeholder function

### high_level_api_improved.py

#### `high_level_api_improved.py`

High-level API for IPFS Kit.

This module provides a high-level API for interacting with IPFS through
a simplified interface focused on common operations and use cases.
It includes methods for content management, filesystem access, AI/ML integration,
role-based operations, and ecosystem connectivity.

**Classes:**
- `IPFSSimpleAPI`: High-level API for IPFS operations.
- `MockIPFSFileSystem`

### high_level_api_updated.py

#### `high_level_api_updated.py`

High-Level API for IPFS Kit.

This module provides a simplified, user-friendly API for common IPFS operations,
with declarative configuration and plugin architecture for extensibility.

Key features:
1. Simplified API: High-level methods for common operations
2. Declarative Configuration: YAML/JSON configuration support
3. Plugin Architecture: Extensible design for custom functionality
4. Multi-language Support: Generates SDKs for Python, JavaScript, and Rust
5. Unified Interface: Consistent interface across all components

This high-level API serves as the main entry point for most users,
abstracting away the complexity of the underlying components.

API Stability:
The API is divided into stability levels that indicate compatibility guarantees:
- @stable_api: Methods won't change within the same major version
- @beta_api: Methods are nearly stable but may change in minor versions
- @experimental_api: Methods may change at any time

See docs/api_stability.md for more details on API versioning and stability.

**Classes:**
- `IPFSSimpleAPI`: Simplified high-level API for IPFS operations.
- `PluginBase`: Base class for plugins.
- `IPFSClient`: Client for interacting with IPFS Kit.
- `PluginBase`: Base class for plugins.

### huggingface_kit.py

#### `huggingface_kit.py`

Hugging Face Hub integration for ipfs_kit_py.

This module provides integration with the Hugging Face Hub for model and dataset access,
extending the ipfs_kit_py ecosystem with a new storage backend. It allows for seamless
authentication, content retrieval, and caching across Hugging Face repositories.

Enhanced with Git VFS translation layer for metadata mapping between HuggingFace's
Git-based repository structure and IPFS-Kit's content-addressed virtual filesystem.

**Classes:**
- `huggingface_kit`: Interface to Hugging Face Hub for model and dataset management.

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### install_ipfs.py

#### `install_ipfs.py`

**Classes:**
- `install_ipfs`
- `MockMultiformats`

### install_lassie.py

#### `install_lassie.py`

Lassie installation script for ipfs_kit_py.

This script handles the installation of Lassie dependencies and binaries for the ipfs_kit_py package.
It provides a comprehensive, class-based implementation for installing and configuring Lassie binaries
on multiple platforms.

Usage:
    As a module: from install_lassie import install_lassie
                 installer = install_lassie(resources=None, metadata={"force": True})
                 installer.install_lassie_daemon()
                 installer.config_lassie()

    As a script: python install_lassie.py [--version VERSION] [--force] [--bin-dir PATH]

**Classes:**
- `install_lassie`: Class for installing and configuring Lassie components.

**Functions:**
- `main()`: Main function for command-line usage.

### install_lotus.py

#### `install_lotus.py`

Lotus installation script for ipfs_kit_py.

This script handles the installation of Lotus dependencies and binaries for the ipfs_kit_py package.
It provides a comprehensive, class-based implementation for installing and configuring Lotus binaries
on multiple platforms.

Usage:
    As a module: from install_lotus import install_lotus
                 installer = install_lotus(resources=None, metadata={"role": "master"})
                 installer.install_lotus_daemon()
                 installer.config_lotus()

    As a script: python install_lotus.py [--version VERSION] [--force] [--bin-dir PATH]

**Classes:**
- `install_lotus`: Class for installing and configuring Lotus components.

**Functions:**
- `main()`: Main function for command-line usage.

### install_storacha.py

#### `install_storacha.py`

Storacha installation script for ipfs_kit_py.

This script handles the installation of Storacha/Web3.Storage dependencies and CLI tools
for the ipfs_kit_py package. It provides a comprehensive, class-based implementation for 
installing and configuring Storacha components on multiple platforms.

Usage:
    As a module: from install_storacha import install_storacha
                 installer = install_storacha(resources=None, metadata={"force": True})
                 installer.install_storacha_dependencies()
                 installer.install_w3_cli()

    As a script: python install_storacha.py [--force] [--verbose]

**Classes:**
- `install_storacha`: Class for installing and configuring Storacha components.

**Functions:**
- `main()`: Main function to parse arguments and install dependencies.

### install_synapse_sdk.py

#### `install_synapse_sdk.py`

Synapse SDK installation script for ipfs_kit_py.

This script handles the installation of Synapse SDK dependencies and Node.js runtime
for the ipfs_kit_py package. It provides a comprehensive, class-based implementation for 
installing and configuring Synapse SDK components on multiple platforms.

Usage:
    As a module: from install_synapse_sdk import install_synapse_sdk
                 installer = install_synapse_sdk(resources=None, metadata={"force": True})
                 installer.install_synapse_sdk_dependencies()
                 installer.config_synapse_sdk()

    As a script: python install_synapse_sdk.py [--force] [--verbose] [--node-version VERSION]

**Classes:**
- `install_synapse_sdk`: Class for installing and configuring Synapse SDK components.

**Functions:**
- `main()`: Main function for command-line usage.

### integrated_search.py

#### `integrated_search.py`

Integrated search combining Arrow metadata index with GraphRAG capabilities.

This module provides the integration between the Arrow metadata index and the
GraphRAG system, offering a unified search interface that combines the strengths
of both components. It also provides integration with AI/ML components like
Langchain and LlamaIndex.

**Classes:**
- `MetadataEnhancedGraphRAG`: GraphRAG system enhanced with Arrow metadata index capabilities.
- `AIMLSearchConnector`: Connects the hybrid search capabilities with AI/ML frameworks.
- `DistributedQueryOptimizer`: Distributed query optimization for integrated search.
- `SearchBenchmark`: Performance benchmarking tools for integrated search functionality.

### intelligent_daemon_manager.py

#### `intelligent_daemon_manager.py`

Intelligent Daemon Manager for IPFS Kit

This module provides a metadata-driven, efficient daemon management system that:
1. Uses metadata from ~/.ipfs_kit/ to make intelligent decisions
2. Monitors backend health using the backend_index instead of polling all backends
3. Provides backend-specific functions with isomorphic method names
4. Handles pin syncing, bucket backups, and metadata index backups per backend
5. Uses threading for efficient operations

**Classes:**
- `BackendHealthStatus`: Health status for a single backend.
- `DaemonTask`: Represents a task for the daemon to execute.
- `IntelligentDaemonManager`: Intelligent daemon manager that uses metadata to optimize backend operations.

**Functions:**
- `get_daemon_manager()`: Get singleton instance of the intelligent daemon manager.

### ipfs

#### `ipfs/ipfs_py.py`

IPFS module reference implementation to resolve dependency issues.

This module creates a direct reference to the ipfs_py class to ensure
it's properly accessible by the IPFS backend implementation.

**Classes:**
- `ipfs_py`: Reference implementation of ipfs_py client for the IPFS backend.

#### `ipfs/__init__.py`

IPFS module for ipfs_kit_py.

This module provides access to the ipfs_py client implementation.

**Classes:**
- `ipfs_py`

### ipfs_backend.py

#### `ipfs_backend.py`

IPFS Backend Module

This module provides a unified interface for interacting with different IPFS implementations.

**Classes:**
- `IPFSBackendError`: Custom exception for IPFS backend errors.
- `MockIPFS`: Mock IPFS client for testing purposes.
- `IPFSBackend`: Interface for interacting with different IPFS implementations.

**Functions:**
- `get_instance()`: Get the IPFS backend instance.

### ipfs_client.py

#### `ipfs_client.py`

IPFS client implementation for the MCP server.

This module provides the ipfs_py class that was missing from ipfs_kit_py.ipfs.ipfs_py
as mentioned in the MCP roadmap. This is a simplified implementation that includes
the essential functionality needed by the IPFS backend.

**Classes:**
- `ipfs_py`: IPFS client implementation that provides an interface to interact with an IPFS node.

### ipfs_cluster_api.py

#### `ipfs_cluster_api.py`

IPFS Cluster REST API client for both cluster service and cluster follow.
Implements the REST API as documented at https://ipfscluster.io/documentation/reference/api/

**Classes:**
- `IPFSClusterAPIClient`: REST API client for IPFS Cluster service.
- `IPFSClusterFollowAPIClient`: REST API client for IPFS Cluster Follow service.
- `IPFSClusterCTLWrapper`: Wrapper for ipfs-cluster-ctl command line tool.
- `IPFSClusterFollowCTLWrapper`: Wrapper for ipfs-cluster-follow command line tool.

### ipfs_cluster_ctl.py

#### `ipfs_cluster_ctl.py`

**Classes:**
- `ipfs_cluster_ctl`

### ipfs_cluster_daemon_manager.py

#### `ipfs_cluster_daemon_manager.py`

Enhanced IPFS Cluster Daemon Manager

This module provides comprehensive management for IPFS Cluster services including:
- IPFS Cluster Service daemon management
- IPFS Cluster Follow daemon management
- Health monitoring and API checks
- Port conflict resolution
- Configuration management
- Automatic recovery and healing

**Classes:**
- `IPFSClusterConfig`: Configuration management for IPFS Cluster.
- `IPFSClusterDaemonManager`: Enhanced daemon manager for IPFS Cluster services.
- `IPFSClusterAPIClient`
- `IPFSClusterCTLWrapper`

### ipfs_cluster_follow.py

#### `ipfs_cluster_follow.py`

**Classes:**
- `ipfs_cluster_follow`
- `IPFSClusterFollow`: Enhanced IPFS Cluster Follow manager with configuration support.
- `IPFSClusterFollowAPIClient`
- `IPFSClusterFollowCTLWrapper`

### ipfs_cluster_follow_daemon_manager.py

#### `ipfs_cluster_follow_daemon_manager.py`

Enhanced IPFS Cluster Follow Daemon Manager

This module provides comprehensive management for IPFS Cluster Follow services including:
- IPFS Cluster Follow daemon management
- Health monitoring and API checks
- Port conflict resolution
- Configuration management
- Automatic recovery and healing
- Worker/follower node functionality
- Bootstrap peer connection management

**Classes:**
- `IPFSClusterFollowConfig`: Configuration management for IPFS Cluster Follow.
- `IPFSClusterFollowDaemonManager`: Enhanced daemon manager for IPFS Cluster Follow services.
- `IPFSClusterFollowAPIClient`
- `IPFSClusterFollowCTLWrapper`

### ipfs_cluster_service.py

#### `ipfs_cluster_service.py`

**Classes:**
- `ipfs_cluster_service`

### ipfs_daemon_manager.py

#### `ipfs_daemon_manager.py`

IPFS Daemon Manager

A comprehensive daemon manager for IPFS that handles:
- Starting and stopping daemons
- API responsiveness checking  
- Port cleanup and process management
- Lock file management
- Intelligent restart logic

Usage:
    from ipfs_kit_py.ipfs_daemon_manager import IPFSDaemonManager
    
    manager = IPFSDaemonManager()
    
    # Start daemon (will clean ports, remove stale locks, etc.)
    result = manager.start_daemon()
    
    # Stop daemon
    result = manager.stop_daemon()
    
    # Check if daemon is healthy and responsive
    is_healthy = manager.is_daemon_healthy()
    
    # Force restart if unresponsive
    result = manager.restart_daemon(force=True)

**Classes:**
- `IPFSConfig`: IPFS configuration settings
- `IPFSDaemonManager`: Comprehensive IPFS daemon manager with intelligent lifecycle management.

**Functions:**
- `main()`: CLI interface for IPFS daemon management.

### ipfs_fsspec.py

#### `ipfs_fsspec.py`

FSSpec implementation for IPFS.

This module provides an FSSpec interface for IPFS, allowing interaction with
IPFS content as a filesystem. It integrates with the ipfs_kit_py library's
core IPFS client and tiered caching mechanisms.

**Classes:**
- `PerformanceMetrics`: Track and report performance metrics for IPFS operations.
- `IPFSFSSpecFileSystem`: FSSpec-compatible filesystem for IPFS.
- `IPFSFSSpecFile`: FSSpec-compatible file-like object for IPFS content.

**Functions:**
- `IPFSFileSystem()`: Convenience alias for IPFSFSSpecFileSystem with smart parameter detection.
- `get_filesystem()`: Get an IPFS filesystem instance.

### ipfs_kit.py

#### `ipfs_kit.py`

**Classes:**
- `ipfs_kit`: Main orchestrator class for IPFS Kit.

**Functions:**
- `auto_retry_on_daemon_failure()`: Decorator that automatically retries operations when they fail due to a daemon not running.

### ipfs_kit_extensions.py

#### `ipfs_kit_extensions.py`

Extension methods for IPFS Kit to provide cluster management functionality.

This module extends the ipfs_kit class with methods for cluster management,
task handling, configuration management, and metrics collection.

**Classes:**
- `IPFSError`: Base class for IPFS errors.
- `IPFSValidationError`: Error raised when validation fails.

**Functions:**
- `register_task_handler()`: Register a handler function for a specific task type.
- `propose_config_change()`: Propose a configuration change to the cluster.
- `get_cluster_metrics()`: Get comprehensive metrics about the cluster.
- `extend_ipfs_kit()`: Extend the ipfs_kit class with cluster management methods.

### ipfs_multiformats.py

#### `ipfs_multiformats.py`

IPFS multiformats handling module for working with CIDs, multihashes, and multiaddresses.

This module provides functionality for:
1. Parsing and validating multiaddresses
2. Converting between multiaddress formats
3. Manipulating multiaddress components
4. Basic CID operations for IPFS content identifiers
5. Multihash encoding and decoding

Implements the specifications defined at:
- https://multiformats.io/
- https://github.com/multiformats/multiaddr
- https://github.com/multiformats/multihash
- https://github.com/multiformats/cid

Multiaddresses are a self-describing format for network addresses with a protocol
prefix and values, like: /ip4/127.0.0.1/tcp/4001/p2p/QmNodeID

**Classes:**
- `MultiaddrParseError`: Raised when a multiaddress cannot be parsed.
- `MultiaddrValidationError`: Raised when a multiaddress is invalid for a specific context.
- `CIDFormatError`: Raised when a CID is in an invalid format.
- `ipfs_multiformats_py`: IPFS multiformats handler for CIDs, multihashes, and multiaddresses.
- `MockBase58`

**Functions:**
- `parse_multiaddr()`: Parse a multiaddress string into components.
- `multiaddr_to_string()`: Convert multiaddress components back to a string.
- `get_protocol_value()`: Extract the value for a specific protocol from multiaddress components.
- `add_protocol()`: Add a protocol to multiaddress components.
- `replace_protocol()`: Replace a protocol's value in multiaddress components.
- `remove_protocol()`: Remove a protocol from multiaddress components.
- `is_valid_multiaddr()`: Validate a multiaddress string for a specific context.
- `decode_multihash()`: Decode a multihash byte sequence into components.
- `create_cid_from_bytes()`: Create a valid CID from raw bytes content.
- `is_valid_cid()`: Check if a string is a valid CID.

### ipget.py

#### `ipget.py`

**Classes:**
- `ipget`

### ipld

#### `ipld/car.py`

Handler for CAR (Content Addressable aRchive) files.

This module provides a wrapper around the py-ipld-car library,
enabling encoding and decoding of CAR files for IPFS.

**Classes:**
- `IPLDCarHandler`: Handler for CAR file operations.

#### `ipld/unixfs.py`

Handler for UnixFS file format.

This module provides a wrapper around the py-ipld-unixfs library,
enabling file chunking and manipulation in the UnixFS format used by IPFS.

**Classes:**
- `IPLDUnixFSHandler`: Handler for UnixFS operations.

#### `ipld/__init__.py`

IPLD (InterPlanetary Linked Data) utilities for IPFS Kit.

This module integrates the py-ipld libraries into IPFS Kit, providing 
functionality for working with:
- CAR files (Content Addressable aRchives)
- DAG-PB (Protobuf Directed Acyclic Graph format)
- UnixFS (File system representation in IPFS)

These components enable low-level manipulation of IPFS data structures,
providing developers with direct access to IPFS content addressing and
graph-based data models.

#### `ipld/dag_pb.py`

Handler for DAG-PB (Protobuf DAG) format.

This module provides a wrapper around the py-ipld-dag-pb library,
enabling encoding and decoding of the DAG-PB format used in IPFS.

**Classes:**
- `IPLDDagPbHandler`: Handler for DAG-PB format operations.

### ipld_extension.py

#### `ipld_extension.py`

IPLD extension for IPFS Kit.

This module extends the IPFS functionality with IPLD-specific operations
including CAR file handling, DAG-PB operations, and UnixFS manipulation.
It provides a higher-level interface to the core IPLD libraries.

**Classes:**
- `IPLDExtension`: Extension for IPFS Kit that provides IPLD-specific functionality.

### ipld_knowledge_graph.py

#### `ipld_knowledge_graph.py`

IPLD Knowledge Graph Implementation.

This module implements a knowledge graph system built on InterPlanetary Linked Data (IPLD),
providing graph traversal capabilities, versioning, and efficient indexing for graph queries.
It enables sophisticated knowledge representation with content-addressed links between entities,
and supports hybrid vector-graph search for advanced use cases like GraphRAG.

Note: Advanced vector storage and specialized embedding operations are handled by
`ipfs_datasets_py.vector_stores` and `ipfs_datasets_py.embeddings`.
This module provides basic vector operations for knowledge graph integration.

Key features:
- Entity and relationship management with IPLD schemas
- Graph traversal and query capabilities
- Basic vector embedding integration
- Hybrid graph-vector search (GraphRAG)
- Versioning and change tracking
- Efficient indexing for graph queries

**Classes:**
- `IPLDGraphDB`: IPLD-based knowledge graph database with vector capabilities.
- `KnowledgeGraphQuery`: Query interface for the IPLD knowledge graph.
- `GraphRAG`: Graph-based Retrieval Augmented Generation using IPLD Knowledge Graph.

### jit_imports.py

#### `jit_imports.py`

Centralized Just-in-Time (JIT) Import Management System for IPFS-Kit

This module provides a centralized system for managing imports across the IPFS-Kit package,
enabling fast startup times by loading heavy dependencies only when needed.

Features:
- Lazy loading of heavy modules (pandas, numpy, duckdb, etc.)
- Feature detection with caching
- Smart dependency resolution
- Shared import state across CLI, MCP server, and daemon
- Performance monitoring and metrics
- Graceful fallbacks for missing dependencies

Usage:
    from ipfs_kit_py.jit_imports import JITImports
    
    jit = JITImports()
    
    # Check if feature is available (fast)
    if jit.is_available('enhanced_features'):
        # Load modules only when needed
        enhanced_pin_index = jit.import_module('enhanced_pin_index')
        bucket_index = jit.import_module('enhanced_bucket_index')

**Classes:**
- `ImportMetrics`: Metrics for tracking import performance.
- `FeatureDefinition`: Definition of a feature and its dependencies.
- `JITImports`: Centralized Just-in-Time import management system.

**Functions:**
- `get_jit_imports()`: Get or create the global JIT imports instance.
- `jit_import()`: Convenience function for JIT importing.
- `jit_import_from()`: Convenience function for JIT importing specific items.
- `is_feature_available()`: Convenience function for checking feature availability.
- `lazy_import()`: Decorator for lazy importing within a function.
- `check_daemon_available()`: Legacy compatibility function.
- `check_enhanced_features_available()`: Legacy compatibility function.
- `check_wal_available()`: Legacy compatibility function.
- `check_bucket_index_available()`: Legacy compatibility function.
- `check_bucket_vfs_available()`: Legacy compatibility function.
- `check_mcp_server_available()`: Legacy compatibility function.

### lassie_kit.py

#### `lassie_kit.py`

**Classes:**
- `LassieValidationError`: Error when input validation fails.
- `LassieContentNotFoundError`: Content with specified CID not found.
- `LassieConnectionError`: Error when connecting to Lassie services.
- `LassieError`: Base class for all Lassie-related exceptions.
- `LassieTimeoutError`: Timeout when communicating with Lassie services.
- `lassie_kit`

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### libp2p

#### `libp2p/noise_protocol.py`

Noise Protocol Framework implementation for libp2p secure transport.

This module provides an implementation of the Noise Protocol Framework for libp2p,
offering a modern, secure alternative to existing security transports. It implements
the XX handshake pattern, which provides mutual authentication and is well-suited
for peer-to-peer communications.

References:
- Noise Protocol Framework: http://noiseprotocol.org/
- libp2p Noise spec: https://github.com/libp2p/specs/tree/master/noise

Requirements:
- cryptography: For cryptographic operations

**Classes:**
- `NoiseError`: Base exception for Noise protocol errors.
- `HandshakeError`: Error during Noise handshake.
- `DecryptionError`: Error during decryption.
- `NoiseState`: State management for Noise Protocol sessions.
- `NoiseProtocol`: Noise Protocol Framework implementation for libp2p.

**Functions:**
- `is_noise_available()`: Check if Noise protocol support is available.

#### `libp2p/high_level_api_integration.py`

IPFS Kit High-Level API LibP2P Integration

This module implements the integration between the IPFS Kit High-Level API
and the enhanced libp2p discovery mechanism, allowing direct P2P content retrieval
and peer discovery through the simplified high-level API interface.

The integration uses dependency injection to avoid circular imports, where the
high-level API class is passed as a parameter rather than being imported directly.
This module adds methods like discover_peers, connect_to_peer, and request_content_from_peer
to the high-level API class.

**Functions:**
- `extend_high_level_api_class()`: Extend the IPFSSimpleAPI class with libp2p peer discovery functionality.
- `apply_high_level_api_integration()`: Apply the High-Level API integration using dependency injection.

#### `libp2p/gossipsub_protocol.py`

Enhanced GossipSub protocol implementation for IPFS Kit.

This module implements advanced GossipSub protocol functionality for the libp2p peer,
providing more robust and flexible publish-subscribe messaging.

Key features:
- Comprehensive topic management
- Support for both sync and async PubSub APIs
- Peer tracking for topic subscriptions 
- Message validation and filtering
- Resource-aware message propagation
- Heartbeat and health monitoring
- Resilient error handling and recovery patterns

**Classes:**
- `GossipSubMessage`: Representation of a GossipSub message.
- `GossipSubTopic`: Representation of a GossipSub topic.
- `GossipSubProtocol`: Enhanced implementation of the GossipSub protocol.

**Functions:**
- `add_gossipsub_methods()`: Add GossipSub protocol methods to the IPFSLibp2pPeer class.
- `add_enhanced_dht_discovery_methods()`: Add enhanced DHT discovery methods to the IPFSLibp2pPeer class.
- `enhance_libp2p_peer()`: Add all enhanced protocol methods to the IPFSLibp2pPeer class.

#### `libp2p/p2p_integration.py`

IPFS LibP2P Enhanced Integration Module

This module provides integration between the IPFSKit, IPFSFileSystem and
enhanced libp2p discovery mechanisms. It enables more efficient peer
discovery and content routing for direct P2P content retrieval without
relying on the IPFS daemon.

Key features:
- Advanced DHT-based peer discovery with k-bucket optimization
- Provider reputation tracking with adaptive backoff strategies
- Intelligent content routing based on network metrics and availability
- Cache miss handling for seamless integration with the tiered cache system

The module uses dependency injection to avoid circular imports, where the
IPFSKit instance or class is passed as a parameter rather than importing it directly.

**Classes:**
- `LibP2PIntegration`: Integration layer between libp2p peer discovery and the filesystem cache.

**Functions:**
- `extend_tiered_cache_manager()`: Extend a TieredCacheManager with libp2p integration for cache misses.
- `register_libp2p_with_ipfs_kit()`: Register a libp2p peer with an IPFSKit instance.

#### `libp2p/enhanced_content_routing.py`

Enhanced content routing implementation for IPFS libp2p.

This module provides enhanced content routing capabilities on top of 
the standard libp2p content routing.

**Classes:**
- `EnhancedContentRouter`: Enhanced content router that adds additional capabilities to the standard

#### `libp2p/typing.py`

Type definitions for libp2p.

This module provides type definitions used in libp2p interfaces.
It serves as a bridge between standard Python typing and libp2p-specific types.

**Classes:**
- `INetwork`: Interface for libp2p network operations.
- `IStream`: Interface for libp2p stream operations.
- `IHost`: Interface for libp2p host operations.
- `IPubSub`: Interface for libp2p pubsub operations.
- `IDHT`: Interface for libp2p DHT operations.

#### `libp2p/datastore.py`

Persistent Datastore module for IPFS Kit libp2p.

This module provides a disk-persistent datastore for the libp2p Kademlia DHT,
extending the in-memory DHTDatastore with persistence capabilities. It ensures
that DHT data survives node restarts and allows for larger datasets than
would fit in memory alone.

The implementation includes:
1. Transaction-safe file operations for crash resilience
2. Efficient index and journal structure for quick lookups
3. LRU-based eviction policy for memory management
4. Automatic background synchronization
5. Heat-based prioritization for frequently accessed data

Usage:
    from ipfs_kit_py.libp2p.datastore import PersistentDHTDatastore
    
    # Create a persistent datastore
    datastore = PersistentDHTDatastore(
        path="/path/to/datastore",
        max_items=10000,
        sync_interval=300  # 5 minutes
    )
    
    # Use like regular DHTDatastore
    datastore.put("key1", b"value1", publisher="peer1")
    value = datastore.get("key1")
    providers = datastore.get_providers("key1")

**Classes:**
- `PersistentDHTDatastore`: Disk-persistent datastore for the libp2p Kademlia DHT.

#### `libp2p/autonat.py`

AutoNAT protocol implementation for automatic NAT detection and traversal.

This module implements the AutoNAT protocol from libp2p, which helps peers
determine if they are behind a NAT and discover their public IP address.
It does this by periodically asking other peers to dial back and confirm
connectivity.

References:
- https://github.com/libp2p/specs/blob/master/autonat/README.md

**Classes:**
- `AutoNATError`: Base exception for AutoNAT errors.
- `AutoNAT`: AutoNAT protocol implementation for automatic NAT detection and traversal.

**Functions:**
- `is_autonat_available()`: Check if AutoNAT support is available.

#### `libp2p/protocol_extensions.py`

Protocol Extensions for libp2p Integration with MCP Server.

This module provides advanced protocol extensions for libp2p, including:
1. Enhanced content discovery mechanisms
2. Direct file transfer protocols
3. Custom MCP-specific protocols for efficient communication
4. Metrics collection for protocol usage

**Classes:**
- `ProtocolMetrics`: Track metrics for protocol usage.
- `MCPSyncProtocolHandler`: Handler for the MCP Sync protocol.
- `DirectTransferProtocolHandler`: Handler for the Direct Transfer protocol.
- `EnhancedDiscoveryProtocolHandler`: Handler for the Enhanced Discovery protocol.

**Functions:**
- `apply_protocol_extensions()`: Apply all protocol extensions to a libp2p peer.
- `get_protocol_metrics()`: Get protocol metrics from a peer.
- `reset_protocol_metrics()`: Reset protocol metrics on a peer.

#### `libp2p/webtransport.py`

WebTransport protocol implementation for libp2p.

This module implements WebTransport as a transport for libp2p, providing a modern
HTTP/3-based alternative to WebRTC for browser-to-node and node-to-node communication.
WebTransport offers lower latency than WebSockets and better API design than WebRTC.

References:
- WebTransport spec: https://w3c.github.io/webtransport/
- HTTP/3 spec: https://quicwg.org/base-drafts/draft-ietf-quic-http.html
- libp2p transport spec: https://github.com/libp2p/specs/tree/master/webtransport

Requirements:
- aioquic: For QUIC and HTTP/3 implementation

**Classes:**
- `WebTransportStream`: Stream implementation based on WebTransport bidirectional stream.
- `WebTransportConnection`: Raw connection implementation based on WebTransport.
- `WebTransportProtocolHandler`: QUIC protocol handler for WebTransport connections.
- `WebTransportSessionInfo`: Information about a WebTransport session.
- `WebTransport`: WebTransport implementation for libp2p.

**Functions:**
- `is_webtransport_available()`: Check if WebTransport support is available.

#### `libp2p/enhanced_dht_discovery.py`

Enhanced DHT-based discovery implementation for IPFS Kit.

This module implements an improved DHT-based discovery system that builds on
the existing implementation in libp2p_peer.py, focusing on more efficient
routing algorithms, better content provider tracking, and integration with
the role-based architecture.

**Classes:**
- `EnhancedDHTDiscovery`: Enhanced DHT-based discovery implementation for libp2p peers.
- `ContentRoutingManager`: Manages intelligent content routing based on peer statistics.

**Functions:**
- `get_enhanced_dht_discovery()`: Get the EnhancedDHTDiscovery class.

#### `libp2p/dag_exchange.py`

DAG Exchange protocol implementation for libp2p.

This module implements the DAG exchange protocol (GraphSync) for libp2p, enabling
efficient exchange of IPLD-based content between peers with partial and selective
querying capabilities.

References:
- GraphSync spec: https://github.com/ipfs/specs/blob/master/GRAPHSYNC.md
- IPLD specs: https://github.com/ipld/specs

**Classes:**
- `MessageType`: GraphSync message types.
- `ResponseCode`: GraphSync response codes.
- `DAGExchangeError`: Base exception for DAG Exchange errors.
- `RequestNotFoundError`: Request not found error.
- `InvalidRequestError`: Invalid request error.
- `RequestOptions`: Options for a DAG exchange request.
- `Request`: DAG exchange request.
- `Response`: DAG exchange response.
- `DAGExchange`: DAG Exchange protocol implementation for libp2p.

**Functions:**
- `make_simple_selector()`: Create a simple selector that selects only the root block.
- `make_all_selector()`: Create a selector that recursively selects all blocks.
- `make_path_selector()`: Create a selector that follows a specific path.
- `make_field_selector()`: Create a selector that selects a specific field.
- `make_limit_depth_selector()`: Create a selector that limits recursion depth.
- `is_dag_exchange_available()`: Check if DAG Exchange support is available.

#### `libp2p/recursive_routing.py`

Recursive and Delegated Content Routing implementation for IPFS Kit.

This module enhances the content routing capabilities of the libp2p implementation
by providing recursive content lookup and delegated routing through trusted nodes.
These features improve content discoverability in the network while reducing the load
on resource-constrained devices.

**Classes:**
- `RecursiveContentRouter`: Recursive content router that implements advanced lookup strategies.
- `DelegatedContentRouter`: Delegated content router that offloads lookup to trusted nodes.
- `ProviderRecordManager`: Advanced provider record manager for maintaining content provider information.
- `ContentRoutingSystem`: Comprehensive content routing system that integrates multiple routing strategies.

**Functions:**
- `enhance_with_recursive_routing()`: Enhance a libp2p peer instance with recursive routing capabilities.

#### `libp2p/protocol_integration.py`

Protocol integration module for IPFS Kit libp2p.

This module ensures that the IPFSLibp2pPeer class is enhanced with all available
protocol implementations, including:
1. GossipSub protocol for efficient publish/subscribe messaging
2. Enhanced DHT discovery methods for better peer and content discovery
3. Enhanced protocol negotiation with semantic versioning and capabilities
4. Recursive and delegated routing for content discovery
5. Integrated networking with multiple transport support

It provides a simple integration point for applying these protocol extensions,
creating a cohesive libp2p stack that works well with IPFS Kit.

Usage:
    from ipfs_kit_py.libp2p.protocol_integration import apply_protocol_extensions
    
    # Apply to the class
    IPFSLibp2pPeer = apply_protocol_extensions(IPFSLibp2pPeer)
    
    # Or apply at runtime to an instance
    peer = IPFSLibp2pPeer(...)
    apply_protocol_extensions_to_instance(peer)

**Classes:**
- `EnhancedKademliaPeer`

**Functions:**
- `apply_protocol_extensions()`: Apply protocol extensions to the IPFSLibp2pPeer class.
- `apply_protocol_extensions_to_instance()`: Apply protocol extensions to an existing IPFSLibp2pPeer instance.
- `apply_enhanced_negotiation()`: Apply enhanced protocol negotiation to the IPFSLibp2pPeer class.
- `add_enhanced_negotiation_methods()`: Add enhanced protocol negotiation methods to the peer class.
- `apply_kademlia_extensions()`: Apply Kademlia DHT extensions to the IPFSLibp2pPeer class.
- `add_kademlia_methods()`: Add Kademlia DHT methods to the peer class.
- `is_component_available()`: Check if a specific component is available.
- `get_available_extensions()`: Get a dictionary of available protocol extensions.

#### `libp2p/webrtc_transport.py`

WebRTC transport for libp2p offering browser-to-node communication capabilities.

This module implements WebRTC as a transport for libp2p, enabling direct peer-to-peer
connections between browsers and nodes or between nodes. It handles the WebRTC
protocol including offer/answer exchange, ICE candidate negotiation, and data
channel establishment.

Requirements:
- aiortc: WebRTC implementation for Python
- cryptography: For secure communication

**Classes:**
- `WebRTCStream`: Stream implementation based on WebRTC data channel.
- `WebRTCRawConnection`: Raw connection implementation based on WebRTC.
- `WebRTCConnection`: Network connection implementation based on WebRTC.
- `WebRTCTransport`: WebRTC transport implementation for libp2p.

**Functions:**
- `is_webrtc_available()`: Check if WebRTC support is available.

#### `libp2p/enhanced_protocol_negotiation.py`

Enhanced protocol negotiation system for libp2p.

This module implements a more robust protocol negotiation system that supports:
1. Semantic versioning with proper compatibility checking
2. Protocol capabilities discovery and negotiation
3. Fallback mechanisms for compatibility with older versions
4. Efficient handshaking with reduced round trips
5. Protocol feature detection

The module extends the basic multiselect protocol with these additional features
while maintaining backward compatibility with standard libp2p implementations.

Usage:
    from ipfs_kit_py.libp2p.enhanced_protocol_negotiation import EnhancedMultiselect
    
    # Server-side usage
    multiselect = EnhancedMultiselect(handlers={"/my-protocol/1.0.0": my_handler})
    
    # Client-side usage
    client = EnhancedMultiselectClient()
    protocol = await client.select_one_of(["/my-protocol/1.0.0"], communicator)

**Classes:**
- `ProtocolMeta`: Metadata for a protocol including version information and capabilities.
- `EnhancedMultiselect`: Enhanced multiselect implementation with advanced protocol negotiation features.
- `EnhancedMultiselectClient`: Enhanced multiselect client implementation with advanced protocol negotiation features.
- `IMultiselectMuxer`
- `IMultiselectClient`
- `IMultiselectCommunicator`
- `Multiselect`
- `MultiselectClient`
- `MultiselectError`
- `MultiselectClientError`
- `MultiselectCommunicatorError`

**Functions:**
- `parse_protocol_id()`: Parse a protocol ID into base name and version.
- `is_version_compatible()`: Check if two versions are compatible (same major version).
- `enhance_protocol_negotiation()`: Enhance a protocol handler with metadata and capabilities.

#### `libp2p/crypto_compat.py`

Compatibility module for libp2p cryptography operations.

This module provides compatibility functions for working with libp2p's 
cryptography components, particularly when there are differences between
the expected and actual API of the libp2p package.

**Classes:**
- `MockPrivateKey`: Mock implementation of a PrivateKey for compatibility.
- `MockPublicKey`: Mock implementation of a PublicKey for compatibility.
- `MockKeyPair`: Mock implementation of a libp2p KeyPair.

**Functions:**
- `serialize_private_key()`: Serialize a private key to bytes format.
- `generate_key_pair()`: Generate a new key pair for use with libp2p.
- `load_private_key()`: Load a private key from serialized data.
- `create_key_pair()`: Create a KeyPair from private and optional public key.

#### `libp2p/libp2p_mocks.py`

libp2p mock implementations for testing.

This module provides mock implementations of the libp2p functionality for testing.
It can be used to enable tests that require libp2p without having the actual
dependency installed.

Usage:
    from ipfs_kit_py.libp2p.libp2p_mocks import apply_libp2p_mocks
    apply_libp2p_mocks()  # This will apply mocks to necessary modules

**Classes:**
- `MockPeerID`
- `MockPrivateKey`
- `MockPublicKey`
- `MockKeyPair`
- `MockPeerInfo`
- `MockLibP2PError`: Mock base class for all libp2p-related errors.
- `MockIPFSLibp2pPeer`: Complete mock implementation of IPFSLibp2pPeer for testing.

**Functions:**
- `apply_libp2p_mocks()`: Apply mocks to the ipfs_kit_py.libp2p_peer module for testing.
- `patch_mcp_command_handlers()`: Patch the MCP command handlers to support libp2p commands and other required methods.

#### `libp2p/peer_manager.py`

Unified LibP2P Peer Manager for IPFS Kit.

This module provides comprehensive peer discovery, management, and remote data access
capabilities using the ipfs_kit_py libp2p stack. It serves as the canonical source
for all peer-related operations across the system.

**Classes:**
- `Libp2pPeerManager`: Unified LibP2P Peer Manager for IPFS Kit.

**Functions:**
- `get_peer_manager()`: Get or create the global peer manager instance.

#### `libp2p/anyio_compat.py`

AnyIO compatibility module to provide missing StreamReader and StreamWriter classes.

This module adds backward compatibility for code expecting anyio.StreamReader
and anyio.StreamWriter attributes that may not be present in newer anyio versions.
It also provides task group compatibility across different anyio versions.

**Classes:**
- `StreamReader`: Protocol for stream reading operations.
- `StreamWriter`: Protocol for stream writing operations.

**Functions:**
- `create_task_group()`: Create a task group compatible with current anyio version.

#### `libp2p/__init__.py`

libp2p package for ipfs_kit_py.

This package provides enhanced libp2p functionality for the ipfs_kit_py project,
including advanced peer discovery, content routing, and direct peer-to-peer
communication without requiring the full IPFS daemon.

Components:
- enhanced_dht_discovery: Advanced DHT-based peer discovery with k-bucket optimization
- recursive_routing: Recursive and delegated content routing mechanisms
- gossipsub_protocol: Advanced publish-subscribe messaging with GossipSub protocol
- content_routing: Intelligent content routing based on peer statistics
- p2p_integration: Integration with IPFSKit and IPFSFileSystem
- ipfs_kit_integration: Extend IPFSKit with libp2p functionality
- high_level_api_integration: Extend IPFSSimpleAPI with peer discovery

The package uses lazy loading and dependency injection to prevent circular imports
and provides graceful degradation when dependencies are not available.

**Classes:**
- `IPFSLibp2pPeer`
- `DummyFuncReg`

**Functions:**
- `check_dependencies()`: Check if all required libp2p dependencies are installed.
- `install_dependencies()`: Attempt to install required dependencies for libp2p functionality.
- `patch_stream_read_until()`: Patch the Stream class with a read_until method if it's missing.
- `apply_protocol_extensions()`: Apply protocol extensions to IPFSLibp2pPeer class.
- `apply_protocol_extensions_to_instance()`: Apply protocol extensions to IPFSLibp2pPeer instance.
- `get_enhanced_dht_discovery()`: Get the EnhancedDHTDiscovery class for DHT-based peer discovery.
- `get_content_routing_manager()`: Get the ContentRoutingManager class for intelligent content routing.
- `get_recursive_content_router()`: Get the RecursiveContentRouter class for advanced recursive content routing.
- `get_delegated_content_router()`: Get the DelegatedContentRouter class for delegated content routing.
- `get_provider_record_manager()`: Get the ProviderRecordManager class for advanced provider tracking.
- `get_content_routing_system()`: Get the ContentRoutingSystem class for unified routing management.
- `get_libp2p_integration()`: Get the LibP2PIntegration class for filesystem cache integration.
- `register_libp2p_with_ipfs_kit()`: Register libp2p with an IPFSKit instance for direct peer-to-peer content exchange.
- `apply_ipfs_kit_integration()`: Apply libp2p integration to the IPFSKit class by extending its functionality.
- `apply_high_level_api_integration()`: Apply libp2p integration to the high-level API class.
- `get_enhanced_protocol_negotiation()`: Get the enhanced protocol negotiation components.
- `apply_enhanced_protocol_negotiation()`: Apply enhanced protocol negotiation to a class or instance.
- `setup_advanced_routing()`: Set up advanced routing components for an IPFSKit instance.
- `compatible_new_host()`: Compatibility wrapper for the libp2p.new_host function to handle API differences.

#### `libp2p/hooks.py`

Import hooks for IPFS Kit libp2p.

This module contains hooks that are executed when the libp2p_peer module is imported.
The hooks apply protocol extensions to the IPFSLibp2pPeer class automatically.

**Functions:**
- `apply_hooks()`: Apply import hooks to the IPFSLibp2pPeer class.

#### `libp2p/protocol_adapters.py`

LibP2P Protocol Adapters for IPFS Kit and MCP Server.

This module provides protocol adapters that bridge between the IPFS Kit
high-level API and the underlying libp2p protocols. These adapters handle
protocol negotiation, message formatting, and stream management.

**Classes:**
- `ProtocolAdapter`: Base class for protocol adapters.
- `BitswapAdapter`: Adapter for the Bitswap protocol.
- `DHTAdapter`: Adapter for the DHT protocol.
- `IdentifyAdapter`: Adapter for the Identify protocol.
- `PingAdapter`: Adapter for the Ping protocol.

**Functions:**
- `apply_protocol_adapters()`: Apply all protocol adapters to a libp2p peer.

#### `libp2p/ipfs_kit_integration.py`

IPFS Kit LibP2P Integration

This module implements the integration between IPFSKit and the enhanced
libp2p discovery mechanism, allowing direct P2P content retrieval when
content is not found in the local cache or IPFS daemon.

The integration uses dependency injection to avoid circular imports, where the
IPFSKit class is passed as a parameter rather than being imported directly.
This allows the libp2p functionality to be seamlessly integrated without
creating import cycles.

**Functions:**
- `extend_ipfs_kit_class()`: Extend the IPFSKit class with libp2p miss handler functionality.
- `apply_ipfs_kit_integration()`: Apply the IPFSKit integration using dependency injection.

#### `libp2p/network/exceptions.py`

Network exceptions for libp2p.

**Classes:**
- `SwarmException`: Base exception for swarm errors.

#### `libp2p/network/__init__.py`

Network module for libp2p.

This module provides network-related components for the libp2p networking stack,
including interfaces and implementations for network operations.

#### `libp2p/tools/constants.py`

Constants for libp2p compatibility.

This module provides constants that may be missing from the current libp2p version.

#### `libp2p/kademlia/network.py`

Kademlia network implementation for libp2p.

This module implements a Kademlia Distributed Hash Table (DHT) for content
routing in libp2p. The implementation provides the core functionality needed 
for finding content providers and announcing content availability.

Key features:
- Content provider announcement
- Provider discovery
- Peer discovery
- Content value storage and retrieval
- Integration with the libp2p network stack

**Classes:**
- `Provider`: Provider information for a key.
- `KademliaServer`: Kademlia DHT server implementation.
- `FallbackBase58`

**Functions:**
- `normalize_id_to_bytes()`: Normalize an ID to bytes consistently.
- `calculate_xor_distance()`: Calculate the XOR distance between two IDs consistently.

#### `libp2p/kademlia/__init__.py`

Kademlia implementation for libp2p.

This module provides a Kademlia DHT implementation for libp2p,
based on the Kademlia paper and the libp2p implementation.

**Classes:**
- `KademliaBucket`: A k-bucket in the Kademlia routing table.
- `KademliaRoutingTable`: Kademlia routing table implementation with tree-based optimization.
- `DHTDatastore`: Storage for the Kademlia DHT.
- `KademliaNode`: Kademlia DHT node implementation.

#### `libp2p/network/stream/exceptions.py`

Stream exceptions for libp2p.

**Classes:**
- `StreamError`: Base exception for stream errors.

#### `libp2p/network/stream/net_stream_interface.py`

Network stream interface for libp2p.

This module provides interfaces and implementations for working with
network streams in the libp2p networking stack.

**Classes:**
- `INetStream`: Interface for network streams.
- `NetStream`: Default implementation of a network stream.
- `StreamError`: Error related to stream operations.
- `StreamHandler`: Handler for stream protocol handlers.
- `StreamReader`: Protocol for stream reading operations.
- `StreamWriter`: Protocol for stream writing operations.

#### `libp2p/network/stream/__init__.py`

Stream module for libp2p.

This module provides interfaces and implementations for working with
network streams in the libp2p networking stack.

**Classes:**
- `INetStream`: Placeholder INetStream interface for compatibility.
- `NetStream`: Placeholder NetStream implementation for compatibility.
- `StreamError`: Error related to stream operations.
- `StreamHandler`: Placeholder StreamHandler implementation for compatibility.

#### `libp2p/tools/pubsub/utils.py`

PubSub utilities for libp2p compatibility.

This module provides pubsub utilities that may be missing from the current libp2p version.

**Functions:**
- `create_pubsub()`: Create a pubsub instance with the given router type.

#### `libp2p/tools/constants/__init__.py`

Constants for libp2p tools.

This module provides constants used by various libp2p components.

#### `libp2p/kademlia/network/network.py`

Kademlia network implementation.

This module provides the core implementation of the Kademlia distributed
hash table (DHT) network operations.

**Classes:**
- `KademliaNetwork`: Implementation of the Kademlia distributed hash table (DHT) network.
- `KademliaServer`: Server implementation for the Kademlia DHT.

#### `libp2p/kademlia/network/__init__.py`

Kademlia network module for libp2p integration.

This module provides implementation and interfaces for the Kademlia
distributed hash table (DHT) network operations.

**Classes:**
- `KademliaNetwork`: Placeholder KademliaNetwork class for compatibility.
- `KademliaServer`: Placeholder KademliaServer class for compatibility.
- `Provider`: Placeholder Provider class for compatibility.
- `Provider`: Basic Provider class for Kademlia network operations.
- `Provider`: Fallback Provider class for compatibility.

### libp2p_peer.py

#### `libp2p_peer.py`

IPFS LibP2P peer implementation for direct peer-to-peer communication.

This module provides direct peer-to-peer communication functionality using libp2p,
enabling content retrieval, peer discovery, and protocol negotiation without
requiring the full IPFS daemon. The implementation is based on the libp2p reference
documentation and the python-peer example in libp2p-universal-connectivity.

Key features:
- Direct peer connections using libp2p
- Content discovery via DHT and mDNS
- NAT traversal through hole punching and relays
- Protocol negotiation for various content exchange patterns
- Integration with the role-based architecture (master/worker/leecher)

This implementation uses anyio for backend-agnostic async operations.

**Classes:**
- `LibP2PError`: Base class for all libp2p-related errors.
- `IPFSLibp2pPeer`: Direct peer-to-peer connection interface for IPFS content exchange.
- `DummyPubsubUtils`
- `DummyPubsubUtils`
- `StreamError`: Error in stream operations.
- `INetStream`: Minimal stream interface fallback.
- `PubsubUtils`

**Functions:**
- `publish_to_topic()`: Publish data to a GossipSub topic.
- `subscribe_to_topic()`: Subscribe to a GossipSub topic with a handler function.
- `unsubscribe_from_topic()`: Unsubscribe from a GossipSub topic.
- `get_topic_peers()`: Get peers subscribed to a topic.
- `list_topics()`: List all topics we're subscribed to.
- `integrate_enhanced_dht_discovery()`: Integrate the enhanced DHT discovery system with this peer.
- `find_providers_enhanced()`: Find providers for content using the enhanced discovery system.
- `extract_peer_id_from_multiaddr()`: Extract peer ID from a multiaddress string.
- `start()`: Start the libp2p peer if it's not already running.

### log_manager.py

#### `log_manager.py`

**Classes:**
- `LogManager`

### lotus_daemon.py

#### `lotus_daemon.py`

**Classes:**
- `lotus_daemon`: Manages Lotus daemon processes across different platforms.

### lotus_kit.py

#### `lotus_kit.py`

**Classes:**
- `LotusValidationError`: Error when input validation fails.
- `LotusContentNotFoundError`: Content with specified CID not found.
- `LotusConnectionError`: Error when connecting to Lotus services.
- `LotusError`: Base class for all Lotus-related exceptions.
- `LotusTimeoutError`: Timeout when communicating with Lotus services.
- `lotus_kit`

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### mcp

#### `mcp/sse_cors_fix.py`

MCP Server SSE and CORS Fix

This module patches the MCP server to properly handle SSE (Server-Sent Events)
and CORS (Cross-Origin Resource Sharing) issues.

**Functions:**
- `patch_fastapi_app()`: Patch a FastAPI app to handle SSE and CORS correctly.
- `add_sse_endpoint()`: Add a test SSE endpoint to the FastAPI app.
- `patch_mcp_server_for_sse()`: Patch the MCP server to handle SSE correctly.

#### `mcp/main_dashboard.py`

Comprehensive MCP Dashboard - Full Feature Integration

This is the most comprehensive dashboard implementation that includes EVERY feature
from the previous MCP server dashboard and integrates all new MCP interfaces.

Features Included:
- Complete backend health monitoring and management
- Full peer management with connectivity control
- Service monitoring (IPFS, Lotus, Cluster, Lassie)
- Bucket management with upload/download capabilities
- VFS browsing and file management
- Configuration widgets for all components
- Real-time metrics and performance monitoring
- Log streaming and analysis
- PIN management with conflict-free operations
- MCP server control and monitoring
- ~/.ipfs_kit/ data visualization
- Cross-backend queries and analytics
- CAR file generation and management
- WebSocket real-time updates
- Mobile-responsive UI

**Classes:**
- `ComprehensiveMCPDashboard`: The most comprehensive dashboard with ALL features from previous dashboards

#### `mcp/refactoring_summary.py`

Refactoring Summary and Results

This script summarizes the successful refactoring of the unified MCP dashboard
from a monolithic structure to a clean, modular architecture.

**Functions:**
- `main()`

#### `mcp/demo_refactored_dashboard.py`

Demo script to showcase the refactored MCP dashboard

This demonstrates the benefits of the new modular structure:
- Separated HTML, CSS, and JavaScript
- Template-based rendering
- Static file serving
- Better maintainability

**Functions:**
- `main()`

#### `mcp/refactored_unified_dashboard.py`

Refactored Unified MCP Dashboard - Separated Components

This refactored implementation provides:
- Separated HTML, CSS, and JavaScript files
- Clean template-based rendering
- Maintained functionality with better organization
- Proper static file serving

**Classes:**
- `RefactoredUnifiedMCPDashboard`: Refactored Unified MCP Server + Dashboard on single port (8004).
- `UnifiedBucketInterface`
- `EnhancedBucketIndex`

**Functions:**
- `main()`: Main entry point.

#### `mcp/websocket.py`

MCP WebSocket Module for real-time communication.

This module provides WebSocket-like capabilities for the MCP server via JSON-RPC polling,
enabling:
1. Event notifications
2. Subscription-based updates
3. Bidirectional communication
4. Automatic connection recovery

Note: This module has been refactored to use JSON-RPC instead of WebSocket connections.

**Classes:**
- `MessageType`: Types of WebSocket messages (maintained for compatibility).
- `WebSocketManager`: WebSocket-compatible manager that uses JSON-RPC event system.
- `WSClient`: Information about a connected WebSocket client (compatibility class).
- `WSMessage`: WebSocket message (compatibility class).
- `WebSocketServer`: WebSocket server for MCP integration (now using JSON-RPC backend).

#### `mcp/direct_mcp_server.py`

MCP Server FastAPI Implementation.

This module serves as the primary entry point for the MCP server as mentioned in the roadmap.
It implements a FastAPI server with endpoints for all MCP components including storage backends,
migration, search, and streaming functionality.

Enhanced with:
- Advanced Authentication & Authorization (Phase 1, Q3 2025)
- Enhanced Metrics & Monitoring (Phase 1, Q3 2025)
- Advanced IPFS Operations (Phase 1, Q3 2025)

**Classes:**
- `MockUser`

**Functions:**
- `main()`: Run the MCP server.

#### `mcp/webrtc.py`

MCP WebRTC Module for peer-to-peer data transfer.

This module provides WebRTC signaling capabilities for the MCP server, enabling:
1. Peer-to-peer connection establishment
2. Room-based peer discovery
3. Direct data channel communication
4. Efficient binary data transfer

**Classes:**
- `SignalType`: Types of WebRTC signaling messages.
- `Peer`: Information about a WebRTC peer.
- `Room`: Information about a WebRTC signaling room.
- `SignalMessage`: WebRTC signaling message.
- `WebRTCSignalingServer`: WebRTC signaling server for peer-to-peer connections.
- `WebRTCSignalingHandler`: Handler for WebRTC signaling in MCP server.

#### `mcp/server.py`

MCP Server

This module provides the Multi-Content Protocol (MCP) server implementation.

**Classes:**
- `MCPServer`: Multi-Content Protocol (MCP) Server

#### `mcp/jsonrpc_methods.py`

JSON-RPC Methods for MCP Server.

This module provides JSON-RPC method implementations that replace
WebSocket functionality, including event management, subscriptions,
and WebRTC signaling.

**Classes:**
- `JSONRPCEventMethods`: JSON-RPC methods for event management (replacing WebSocket /ws endpoint).
- `JSONRPCWebRTCMethods`: JSON-RPC methods for WebRTC signaling (replacing WebSocket /webrtc/signal endpoint).

**Functions:**
- `get_jsonrpc_event_methods()`: Get the global JSON-RPC event methods instance.
- `get_jsonrpc_webrtc_methods()`: Get the global JSON-RPC WebRTC methods instance.
- `register_jsonrpc_methods()`: Register all JSON-RPC methods with a dispatcher.

#### `mcp/integrator.py`

MCP Feature Integration Module

This module integrates the implemented roadmap features with the MCP server:
- Advanced IPFS Operations
- Enhanced Metrics & Monitoring
- Optimized Data Routing
- Advanced Authentication & Authorization

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `MCPFeatureIntegration`: Integrates roadmap features with the MCP server.
- `MetricsMiddleware`

**Functions:**
- `get_integrator()`: Get or create the MCP feature integrator.

#### `mcp/monitoring.py`

MCP Monitoring Module for system metrics and performance tracking.

This module provides comprehensive monitoring capabilities for the MCP server, including:
1. Performance metrics collection and analysis
2. Backend status monitoring
3. Usage statistics tracking
4. Health checks and alerting
5. Prometheus metrics exposure

**Classes:**
- `MetricType`: Types of metrics collected.
- `MetricUnit`: Units for metrics.
- `MetricTag`: Tags for categorizing metrics.
- `Metric`: Definition of a metric.
- `MetricSample`: Individual metric sample.
- `MetricSeries`: Time series of metric samples.
- `MetricsRegistry`: Registry for collecting and retrieving metrics.
- `SystemMonitor`: Monitor for system metrics.
- `BackendMonitor`: Monitor for backend metrics.
- `APIMonitor`: Monitor for API metrics.
- `MigrationMonitor`: Monitor for migration metrics.
- `StreamingMonitor`: Monitor for streaming metrics.
- `SearchMonitor`: Monitor for search metrics.
- `MonitoringManager`: Manager for all monitoring components.

#### `mcp/mcp_error_handling.py`

MCP Error Handling System.

This module provides standardized error handling functionality for the MCP server,
including consistent error responses, error codes, and error tracking.

**Classes:**
- `ErrorSeverity`: Severity levels for MCP errors.
- `ErrorCategory`: Categories of MCP errors.
- `MCPError`: Base exception class for MCP server errors.
- `AuthenticationError`: Error raised when authentication fails.
- `InvalidCredentialsError`: Error raised when credentials are invalid.
- `TokenExpiredError`: Error raised when an authentication token has expired.
- `AuthorizationError`: Error raised when a user is not authorized to perform an action.
- `InsufficientPermissionsError`: Error raised when a user has insufficient permissions.
- `ValidationError`: Error raised when input validation fails.
- `MissingParameterError`: Error raised when a required parameter is missing.
- `InvalidParameterError`: Error raised when a parameter is invalid.
- `ResourceError`: Error raised when a resource operation fails.
- `ResourceNotFoundError`: Error raised when a resource is not found.
- `ResourceAlreadyExistsError`: Error raised when a resource already exists.
- `StorageError`: Error raised when a storage operation fails.
- `StorageBackendUnavailableError`: Error raised when a storage backend is unavailable.
- `ContentNotFoundError`: Error raised when content is not found in storage.
- `NetworkError`: Error raised when a network operation fails.
- `ConnectionError`: Error raised when a connection fails.
- `TimeoutError`: Error raised when a network operation times out.
- `MigrationError`: Error raised when a migration operation fails.
- `SystemError`: Error raised when a system operation fails.
- `ConfigurationError`: Error raised when there is a configuration issue.

**Functions:**
- `handle_exception()`: Convert an exception to a standardized error response.
- `convert_legacy_error()`: Convert a legacy error format to the standardized format.

#### `mcp/run_enhanced_server.py`

Enhanced MCP Server Startup Script

This script starts the Enhanced MCP Server that mirrors CLI functionality
while adapting to the MCP protocol requirements.

#### `mcp/enhanced_server.py`

Enhanced MCP Server - Refactored to mirror CLI functionality

This module provides a comprehensive MCP server that mirrors the CLI command structure
while adapting to the MCP protocol. It maintains the CLI's extensive feature set while
providing efficient metadata reading and allowing the daemon to manage synchronization.

**Classes:**
- `MCPCommandRequest`: Request structure for MCP commands - mirrors CLI argument structure.
- `MCPCommandResponse`: Response structure for MCP commands.
- `EnhancedMCPServer`: Enhanced MCP Server that mirrors CLI functionality while optimizing for MCP protocol.
- `MetadataReader`: Efficient reader for ~/.ipfs_kit/ metadata directory.
- `DaemonConnector`: Connector to communicate with IPFS-Kit daemon for synchronization.
- `BaseCommandHandler`: Base class for command handlers.
- `DaemonCommandHandler`: Handler for daemon operations - mirrors CLI daemon commands.
- `PinCommandHandler`: Handler for PIN operations - mirrors CLI pin commands.
- `BackendCommandHandler`: Handler for backend operations - mirrors CLI backend commands.
- `BucketCommandHandler`: Handler for bucket operations - mirrors CLI bucket commands.
- `LogCommandHandler`: Handler for logging operations - mirrors CLI log commands.
- `ServiceCommandHandler`: Handler for service operations - mirrors CLI service commands.
- `MCPCommandHandler`: Handler for MCP operations - mirrors CLI MCP commands.
- `HealthCommandHandler`: Handler for health check operations.
- `StatusCommandHandler`: Handler for status operations.
- `VersionCommandHandler`: Handler for version operations.
- `ConfigCommandHandler`: Handler for configuration operations.
- `MetricsCommandHandler`: Handler for metrics operations.

#### `mcp/optimized_routing.py`

MCP Server Integration for Optimized Data Routing

This module provides a compatibility layer between the MCP server and the
core ipfs_kit_py routing module. It allows the MCP server to use the optimized
data routing functionality while maintaining separation of concerns.

**Classes:**
- `RoutingIntegration`: Integration between MCP server and optimized data routing system.

**Functions:**
- `add_routing_middleware()`: Add routing middleware to FastAPI application.

#### `mcp/metadata_first_tools.py`

Metadata-First MCP Tools for IPFS Kit Python

This module implements MCP tools that prioritize checking metadata in ~/.ipfs_kit/
before making calls to the ipfs_kit_py library, improving performance and providing
a caching layer for file operations.

**Classes:**
- `MetadataFirstTools`: Tools that check metadata first, then fall back to library calls.

**Functions:**
- `get_metadata_tools()`: Get or create the global metadata tools instance.

#### `mcp/run_mcp_server_initializer.py`

MCP Server Initializer for run_mcp_server.

This module patches the run_mcp_server to initialize the IPFS model with extensions.

**Functions:**
- `patch_run_mcp_server()`: Patch the run_mcp_server module to initialize IPFS model extensions.
- `initialize_mcp_server()`: Initialize MCP server with all required extensions.

#### `mcp/search.py`

MCP Search Module for content indexing and retrieval.

This module provides comprehensive search capabilities for MCP content, including:
1. Content indexing with metadata extraction
2. Full-text search using SQLite FTS5
3. Vector search using FAISS
4. Hybrid search combining text and vector search results

**Classes:**
- `SearchIndexType`: Types of search indices.
- `ContentType`: Supported content types for indexing.
- `SearchIndex`: Base class for search indices.
- `TextSearchIndex`: Text-based search index using SQLite FTS5.
- `VectorSearchIndex`: Vector-based search index using FAISS.
- `HybridSearchIndex`: Hybrid search combining text and vector search.
- `MCP_Search`: MCP Search Manager for content indexing and retrieval.

**Functions:**
- `detect_content_type()`: Detect the type of content for indexing.
- `extract_text()`: Extract searchable text from content.

#### `mcp/storage_types.py`

Storage Types Module

This module defines storage backend types and related enumerations.

**Classes:**
- `StorageBackendType`: Storage backend type enumeration
- `StorageOperation`: Enumeration of storage operations.
- `StorageStatus`: Enumeration of storage operation statuses.

#### `mcp/server_bridge.py`

MCP Server implementation for fastapi.

This module provides the MCP Server implementation that can be used with FastAPI.

**Classes:**
- `MCPServer`: MCP Server implementation for FastAPI.

#### `mcp/jsonrpc_event_manager.py`

JSON-RPC Event Manager for MCP Server.

This module provides event management functionality via JSON-RPC calls,
replacing WebSocket-based real-time communication with polling-based
event retrieval while maintaining all existing functionality.

**Classes:**
- `EventType`: Types of events that can be managed.
- `EventCategory`: Categories of events to subscribe to.
- `Event`: Represents an event in the system.
- `ClientSession`: Information about a client session.
- `JSONRPCEventManager`: Event manager that provides WebSocket-like functionality via JSON-RPC polling.

**Functions:**
- `get_jsonrpc_event_manager()`: Get the global JSON-RPC event manager instance.
- `initialize_jsonrpc_event_manager()`: Initialize the global JSON-RPC event manager with custom settings.

#### `mcp/async_streaming.py`

Asynchronous Streaming Module for MCP Server

This module provides asynchronous streaming capabilities for efficient
transfer of large content using async-io.

**Classes:**
- `AsyncStreamManager`: Manager for asynchronous streaming operations.
- `AsyncChunkedFileReader`: Asynchronous chunked file reader.
- `AsyncChunkedFileWriter`: Asynchronous chunked file writer.

#### `mcp/server_anyio.py`

MCP Server AnyIO Module

This module provides the AnyIO-compatible Multi-Content Protocol (MCP) server implementation.

**Classes:**
- `MCPServer`: AnyIO-compatible Multi-Content Protocol (MCP) Server

#### `mcp/mcp_manager.py`

MCP Manager

This module provides high-level management of MCP servers and dashboard.

**Classes:**
- `MCPManager`: High-level manager for MCP server and dashboard operations.

#### `mcp/__init__.py`

MCP (Model-Controller-Persistence) Server for IPFS Kit.

This module provides a structured server implementation that:
1. Separates data models from controller logic
2. Provides consistent persistence patterns
3. Facilitates test-driven development through clean interfaces

The MCP pattern is particularly useful for IPFS Kit as it allows:
- Isolated testing of IPFS operations
- Mock implementations of network dependencies
- Clear boundaries between components

#### `mcp/routing_integration.py`

MCP server integration for optimized routing

This file provides integration between the MCP server and the optimized data routing system.

**Classes:**
- `RoutingManager`: Manager class that integrates the adaptive routing optimizer with the MCP server.

**Functions:**
- `create_routing_manager()`: Create a routing manager.

#### `mcp/rbac.py`

**Functions:**
- `get_current_user_role()`: Placeholder function to determine the current user's role from request headers.
- `has_permission()`: Checks if a given role has the required permission.

#### `mcp/streaming.py`

MCP Streaming Module for efficient transfer of large content.

This module provides basic streaming types and constants used by both
synchronous and asynchronous streaming implementations.

**Classes:**
- `StreamStatus`: Status of a stream operation.
- `StreamDirection`: Direction of a stream operation.
- `StreamType`: Type of streaming operation.
- `StreamProgress`: Progress information for a stream operation.
- `StreamOperation`: Information about a streaming operation.

#### `mcp/ipfs_extensions.py`

IPFS Extensions for MCP

This module provides IPFS methods for MCP tools.

**Functions:**
- `initialize_ipfs_model()`: Initialize IPFS model.
- `ensure_ipfs_model()`: Ensure IPFS model is initialized.

#### `mcp/ai/dataset_manager.py`

Dataset Manager Module for AI/ML Components in MCP Server

This module provides dataset management capabilities for AI/ML components, including:
1. Dataset versioning
2. Dataset metadata tracking
3. Schema validation
4. Transformation pipelines

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).

**Classes:**
- `DatasetFormat`: Dataset format types.
- `DatasetDomain`: Dataset domain types.
- `DatasetSplit`: Dataset split types.
- `DatasetFile`: Information about a file in a dataset.
- `DatasetVersion`: Dataset version information.
- `Dataset`: Dataset information.
- `DatasetManager`: Manager for dataset operations.
- `MockConfig`
- `MockMetricsCollector`
- `MockHealthCheck`

**Functions:**
- `get_instance()`: Get the singleton instance.

#### `mcp/ai/utils.py`

Utility functions for AI/ML components in MCP

This module provides utility functions for initializing and
integrating all AI/ML components using the centralized
configuration system.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Functions:**
- `initialize_all_components()`: Initialize all AI/ML components using the shared configuration.
- `initialize_model_registry()`: Initialize the Model Registry component with configuration.
- `initialize_dataset_manager()`: Initialize the Dataset Manager component with configuration.
- `initialize_distributed_training()`: Initialize the Distributed Training component with configuration.
- `initialize_framework_integration()`: Initialize the Framework Integration component with configuration.
- `initialize_ai_ml_integrator()`: Initialize the AI/ML Integrator component with configuration.
- `setup_logging()`: Set up logging for AI/ML components based on configuration.
- `check_dependencies()`: Check for the presence of optional dependencies.

#### `mcp/ai/monitoring.py`

AI/ML Monitoring Module for MCP Server

This module provides monitoring capabilities for AI/ML components, including:
1. Performance metrics collection
2. Health check management
3. Prometheus integration
4. Custom metrics dashboards

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).

**Classes:**
- `MetricsCollector`: Collects metrics from AI/ML components.
- `HealthCheck`: Health check management for AI/ML components.
- `PerformanceTimer`: Timer for measuring operation performance.

**Functions:**
- `get_metrics_collector()`: Get the metrics collector instance.
- `get_health_check()`: Get the singleton health check instance.
- `measure_time()`: Decorator for measuring function execution time.
- `timer()`: Context manager for measuring operation execution time.
- `log_metrics()`: Log all collected metrics.
- `log_health()`: Log health check results.

#### `mcp/ai/dataset_manager_router.py`

Dataset Manager Router for MCP Server

This module provides FastAPI routes for the dataset management capabilities,
exposing a RESTful API for working with datasets.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Functions:**
- `create_dataset_manager_router()`: Create a FastAPI router for the dataset manager.

#### `mcp/ai/distributed_training.py`

Distributed Training for MCP Server

This module provides training job orchestration and management capabilities
for distributed machine learning workflows within the IPFS Kit ecosystem.

Key features:
- Training job orchestration
- Multi-node training support
- Hyperparameter optimization
- Model checkpointing and resumption

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Classes:**
- `TrainingJob`: Represents a machine learning training job with its configuration and state.
- `DistributedTraining`: Manager for distributed training jobs.

**Functions:**
- `get_instance()`: Get or create the singleton instance of the DistributedTraining.

#### `mcp/ai/model_registry.py`

Model Registry for MCP Server

This module provides version-controlled model storage and management capabilities
for machine learning models within the IPFS Kit ecosystem.

Key features:
- Version-controlled model storage
- Model metadata management
- Model performance tracking
- Deployment configuration management

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Classes:**
- `ModelVersion`: Represents a single version of a model with its metadata and metrics.
- `Model`: Represents a machine learning model with its versions and metadata.
- `ModelRegistry`: Registry for managing machine learning models.

**Functions:**
- `get_instance()`: Get or create the singleton instance of the ModelRegistry.

#### `mcp/ai/api_router.py`

AI/ML API Router for MCP Server

This module provides the main FastAPI router for all AI/ML components,
integrating various sub-components like model registry and dataset manager.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Functions:**
- `create_ai_api_router()`: Create the main AI/ML API router.

#### `mcp/ai/ai_ml_integrator.py`

AI/ML Integrator Module for MCP Server

This module provides integration of AI/ML capabilities with the MCP server, including:
1. API Registration and routing
2. Component coordination
3. Authentication and authorization
4. Monitoring and diagnostics

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).

**Classes:**
- `Dataset`: Dataset information for API.
- `DatasetVersion`: Dataset version information for API.
- `CreateDatasetRequest`: Request to create a dataset.
- `CreateDatasetVersionRequest`: Request to create a dataset version.
- `ErrorResponse`: API error response.
- `AIML_Integrator`: AI/ML Integration Manager
- `MockConfig`
- `MockMetricsCollector`
- `MockHealthCheck`
- `MockDatasetManager`

**Functions:**
- `get_instance()`: Get the singleton instance.

#### `mcp/ai/framework_integration.py`

AI Framework Integration Module for MCP Server

This module provides integration with popular AI frameworks and libraries,
enabling seamless use of external AI tools and services with the MCP server
infrastructure. It complements the model_registry, dataset_manager, and
distributed_training modules for complete ML lifecycle management.

Key integrations:
1. LangChain for LLM workflows and agents
2. LlamaIndex for data indexing and retrieval
3. HuggingFace for model hosting and inference
4. Custom model serving for specialized deployments

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).

**Classes:**
- `FrameworkType`: Enum for supported AI frameworks.
- `EndpointType`: Enum for types of model endpoints.
- `InferenceType`: Enum for types of inference tasks.
- `FrameworkConfig`: Base configuration for framework integrations.
- `LangChainConfig`: Configuration for LangChain integration.
- `LlamaIndexConfig`: Configuration for LlamaIndex integration.
- `HuggingFaceConfig`: Configuration for HuggingFace integration.
- `CustomFrameworkConfig`: Configuration for custom framework integration.
- `ModelEndpoint`: A deployed model endpoint for inference.
- `FrameworkIntegrationBase`: Base class for framework integrations.
- `LangChainIntegration`: LangChain framework integration.
- `LlamaIndexIntegration`: LlamaIndex framework integration.
- `HuggingFaceIntegration`: HuggingFace framework integration.
- `CustomFrameworkIntegration`: Custom framework integration.
- `ModelEndpointManager`: Manager for model endpoints.
- `FrameworkIntegrationManager`: Manager for framework integrations.

**Functions:**
- `get_instance()`: Get or create the singleton instance of the FrameworkIntegrationManager.

#### `mcp/ai/config.py`

AI/ML Configuration Module for MCP Server

This module provides configuration management for AI/ML components, including:
1. Framework-specific settings
2. Storage paths
3. Environment-based configuration
4. Secure credential handling

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).

**Classes:**
- `AIMLConfig`: Configuration manager for AI/ML components.

**Functions:**
- `get_instance()`: Get or create the singleton configuration instance.

#### `mcp/ai/__init__.py`

AI/ML Package for MCP Server

This package provides AI/ML capabilities for the MCP server, including:
1. Model Registry - Version-controlled model storage and metadata
2. Dataset Manager - Version-controlled dataset storage and processing
3. Distributed Training - Training job orchestration and monitoring
4. Framework Integration - Integration with ML frameworks like LangChain, etc.

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).

#### `mcp/ai/model_registry_router.py`

Model Registry Router for MCP Server

This module provides FastAPI routes for the model registry capabilities,
exposing a RESTful API for working with machine learning models.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Functions:**
- `create_model_registry_router()`: Create a FastAPI router for the model registry.

#### `mcp/dashboard/refactored_unified_mcp_dashboard.py`

Refactored Unified MCP Server + Dashboard - Single Port Integration

This refactored implementation combines:
- MCP server functionality on one port
- Beautiful responsive dashboard with separated JS/CSS/HTML
- Direct MCP command integration (no WebSockets)
- Modern aesthetic design with proper file organization
- Complete IPFS Kit integration

Usage: ipfs-kit mcp start
Port: 8004 (single port for both MCP and dashboard)

**Classes:**
- `RefactoredUnifiedMCPDashboard`: Refactored Unified MCP Server + Dashboard on single port (8004).
- `UnifiedBucketInterface`
- `EnhancedBucketIndex`

**Functions:**
- `main()`: Main entry point for the refactored unified MCP dashboard.

#### `mcp/dashboard/consolidated_server.py`

Consolidated MCP-first FastAPI Dashboard

Single-file FastAPI app providing:
 - JSON-RPC style tool endpoints (under /mcp)
 - REST mirrors for key domain objects (buckets, backends, pins, files, metrics)
 - Realtime WebSocket + SSE logs
 - Self-rendered HTML UI (progressively enhanced)

NOTE: Large HTML template content was previously (accidentally) embedded inside this
module docstring causing the original import section to be lost and producing a
cascade of "name is not defined" errors. This docstring has been reduced and the
imports + helpers restored below.

**Classes:**
- `InMemoryLogHandler`
- `ConsolidatedMCPDashboard`

**Functions:**
- `create_default_backends()`: Create default backend configurations for testing and demonstration.
- `ensure_paths()`

#### `mcp/dashboard/simple_working_mcp_dashboard.py`

Simple Working MCP Dashboard with Bucket VFS Operations
=======================================================

A minimal working MCP server with bucket virtual filesystem operations
that can be used with `ipfs-kit mcp start` command.

**Classes:**
- `ConsolidatedMCPDashboard`: Simple working MCP Dashboard with bucket VFS operations.

**Functions:**
- `main()`: Main entry point.

#### `mcp/dashboard/consolidated_mcp_dashboard.py`

Consolidated MCP-first FastAPI Dashboard

Single-file FastAPI app providing:
 - JSON-RPC style tool endpoints (under /mcp)
 - REST mirrors for key domain objects (buckets, backends, pins, files, metrics)
 - Realtime WebSocket + SSE logs
 - Self-rendered HTML UI (progressively enhanced)

NOTE: Large HTML template content was previously (accidentally) embedded inside this
module docstring causing the original import section to be lost and producing a
cascade of "name is not defined" errors. This docstring has been reduced and the
imports + helpers restored below.

**Classes:**
- `InMemoryLogHandler`
- `ConsolidatedMCPDashboard`

**Functions:**
- `create_default_backends()`: Create default backend configurations for testing and demonstration.
- `create_default_buckets()`: Create default bucket configurations for first-time setup.
- `ensure_paths()`

#### `mcp/examples/storacha_connection_example.py`

Example demonstrating the enhanced StorachaConnectionManager.

This example shows how to use the new connection manager with its reliability features.

**Functions:**
- `load_api_key()`: Load Storacha API key from a configuration file or environment variable.
- `simulate_various_scenarios()`: Simulate various scenarios to demonstrate connection manager features.
- `print_connection_status()`: Print the current status of the connection manager.
- `main()`: Main function to demonstrate the StorachaConnectionManager.

#### `mcp/examples/high_availability_example.py`

High Availability Architecture Example for MCP Server

This example demonstrates how to set up and use the High Availability module
to create a fault-tolerant, multi-region deployment of the MCP server.

Key features demonstrated:
1. Multi-region configuration
2. Node health monitoring
3. Automatic failover between regions
4. Load balancing between nodes
5. Manual operations like triggering failover

Usage:
  python high_availability_example.py [--redis-url REDIS_URL]

**Functions:**
- `create_example_config()`: Create an example HA configuration file.

#### `mcp/examples/distributed_training_example.py`

Distributed Training Example for MCP Server

This example demonstrates how to use the Distributed Training module to train
machine learning models across multiple nodes. It shows the core functionality
of the module:

1. Creating and submitting training jobs
2. Monitoring job progress and metrics
3. Working with hyperparameter optimization
4. Managing model checkpoints
5. Integration with model registry and dataset manager

Usage:
  python distributed_training_example.py [--ray] [--torch-dist]

**Classes:**
- `SimpleModel`

**Functions:**
- `create_simple_pytorch_model()`: Create a simple PyTorch model and save it to a file.
- `create_training_script()`: Create a simple training script.
- `create_mock_dataset()`: Create a mock dataset for training.
- `demonstrate_basic_job_submission()`: Demonstrate basic training job submission and monitoring.
- `demonstrate_hyperparameter_tuning()`: Demonstrate hyperparameter tuning with Ray Tune.
- `demonstrate_distributed_training()`: Demonstrate multi-node distributed training.
- `demonstrate_model_registry_integration()`: Demonstrate integration with model registry.
- `main()`: Run the distributed training examples.

#### `mcp/examples/lifecycle_example.py`

Data Lifecycle Management Example for MCP Server

This example demonstrates how to use the lifecycle management module to implement
policy-based data retention, automated archiving, data classification,
compliance enforcement, and cost optimization strategies.

Key features demonstrated:
1. Creating and managing retention policies
2. Data classification based on content and metadata
3. Automated archiving of infrequently accessed data
4. Compliance monitoring and enforcement
5. Cost optimization through tiered storage

Usage:
  python lifecycle_example.py [--storage-path STORAGE_PATH] [--metadata-path METADATA_PATH]

**Functions:**
- `demonstrate_rule_creation()`: Demonstrate creating various rules for lifecycle management.
- `demonstrate_content_lifecycle()`: Demonstrate content lifecycle management.
- `main()`: Run the lifecycle management example.

#### `mcp/examples/api_key_cache_example.py`

Enhanced API Key Cache Example

This example demonstrates how to use the enhanced API key caching system
to improve performance for API key validation in MCP Server.

Key features demonstrated:
1. Setting up the enhanced API key cache
2. Patching the auth service for seamless integration
3. Using the cache in FastAPI endpoints
4. Cache monitoring and performance analysis
5. Different integration approaches

Usage:
  python api_key_cache_example.py

**Classes:**
- `MockAuthService`: Mock authentication service for demonstration purposes.

**Functions:**
- `create_fastapi_app()`: Create a FastAPI application with API key caching.
- `run_fastapi_example()`: Run a FastAPI server with API key caching.

#### `mcp/examples/monitoring_example.py`

Monitoring Example for MCP Server.

This script demonstrates how to use the MCP monitoring functionality,
including Prometheus metrics export, health checks, and metrics collection.

**Functions:**
- `setup_api()`: Set up a FastAPI application with monitoring functionality.
- `register_components_for_health_checks()`: Register example components for health checking.
- `check_api_health()`: Example health check function for the API component.
- `check_database_health()`: Example health check function for the database component.
- `check_storage_health()`: Example health check function for the storage component.
- `check_ipfs_health()`: Example health check function for the IPFS component.
- `register_custom_metrics_collectors()`: Register custom metrics collectors.
- `collect_custom_metrics()`: Example custom metrics collector function.

#### `mcp/examples/filecoin_connection_example.py`

Example demonstrating the enhanced FilecoinConnectionManager.

This example shows how to use the new connection manager with its reliability features.

**Functions:**
- `load_token()`: Load Filecoin API token from a configuration file or environment variable.
- `pretty_print_json()`: Print JSON data with proper formatting.
- `simulate_various_scenarios()`: Simulate various scenarios to demonstrate connection manager features.
- `print_connection_status()`: Print the current status of the connection manager.
- `main()`: Main function to demonstrate the FilecoinConnectionManager.

#### `mcp/examples/error_handling_example.py`

Example of how to use the MCP error handling system.

This module demonstrates the proper usage of the standardized error handling
system in an MCP controller implementation.

**Classes:**
- `ExampleController`: Example controller showcasing standardized error handling.
- `MockBackend`

**Functions:**
- `api_example()`: Example of how to use the error handling in an API endpoint.

#### `mcp/examples/optimized_routing_example.py`

Example usage of the Optimized Data Routing module

This example demonstrates how to:
1. Create an OptimizedRouter instance
2. Register storage backends with metrics
3. Create routing policies for different use cases
4. Make routing decisions for content
5. Analyze backend performance and connectivity

**Functions:**
- `initialize_router_with_backends()`: Initialize a router and register some backends.
- `create_routing_policies()`: Create various routing policies for different use cases.
- `make_routing_decisions()`: Demonstrate making routing decisions for different content types.
- `analyze_backend_performance()`: Analyze backend performance and connectivity.
- `main()`: Main function to demonstrate the Optimized Router.

#### `mcp/examples/rbac_example.py`

Role-Based Access Control (RBAC) Example for MCP Server

This example demonstrates how to use the RBAC system to implement
role-based access control in an MCP server application.

Key features demonstrated:
1. Creating and managing roles
2. Defining permissions
3. Creating access policies
4. Checking permissions
5. Integration with FastAPI

Usage:
  python rbac_example.py [--server]

**Functions:**
- `create_example_configuration()`: Create example RBAC configuration files.
- `create_fastapi_app()`: Create a FastAPI application with RBAC integration.
- `run_fastapi_example()`: Run the FastAPI example server.

#### `mcp/examples/optimized_monitoring_example.py`

Optimized Monitoring Example for MCP Server.

This script demonstrates how to use the optimized metrics collector to address
memory usage issues when tracking many metrics. It shows the memory efficiency
features and adaptive collection capabilities.

**Functions:**
- `setup_api()`: Set up a FastAPI application with optimized monitoring functionality.
- `register_components_for_health_checks()`: Register example components for health checking.
- `check_api_health()`: Example health check function for the API component.
- `check_database_health()`: Example health check function for the database component.
- `check_storage_health()`: Example health check function for the storage component.
- `check_ipfs_health()`: Example health check function for the IPFS component.
- `register_custom_metrics_collectors()`: Register custom metrics collectors.
- `collect_custom_metrics()`: Example custom metrics collector function.
- `collect_network_traffic_metrics()`: Simulated network traffic metrics collector.
- `collect_database_metrics()`: Simulated database performance metrics collector.
- `collect_user_activity_metrics()`: Simulated user activity metrics collector.
- `collect_content_storage_metrics()`: Simulated content storage metrics collector.

#### `mcp/examples/advanced_ipfs_operations.py`

Example script showing how to integrate the advanced IPFS operations with the MCP server.

This demonstrates how to use the DHT, DAG, and IPNS operations through the MCP API.

**Functions:**
- `setup_api()`: Set up a FastAPI application with IPFS advanced operations.

#### `mcp/examples/oauth_enhanced_security_example.py`

OAuth Enhanced Security Example

This example demonstrates how to use the enhanced security features for OAuth
integration in the MCP server, showing how to mitigate common OAuth vulnerabilities
and implement best practices for secure OAuth authentication.

Key features demonstrated:
1. PKCE implementation for secure authorization code flow
2. Token binding to prevent token theft and misuse
3. Advanced threat detection for common OAuth attacks
4. Certificate validation for OAuth providers
5. Dynamic security policies based on risk assessment

Usage:
  python oauth_enhanced_security_example.py

**Classes:**
- `MemoryStorage`: Simple in-memory storage for example purposes.

**Functions:**
- `create_fastapi_app()`: Create a FastAPI application demonstrating OAuth security integration.
- `run_fastapi_example()`: Run the FastAPI example server.

#### `mcp/examples/framework_integration_example.py`

Framework Integration Example

This example demonstrates how to use the framework_integration module to integrate
various AI frameworks with the MCP server infrastructure.

It shows how to:
1. Configure and initialize LangChain for LLM workflows
2. Set up LlamaIndex for document indexing and retrieval
3. Use HuggingFace for model hosting and inference
4. Create and manage model endpoints

This example requires the following packages:
- langchain
- llama-index
- huggingface_hub
- transformers
- torch

You can install these with:
pip install langchain llama-index huggingface_hub transformers torch

**Functions:**
- `setup_example_data()`: Set up example data for the demo.
- `demo_langchain_integration()`: Demonstrate LangChain integration.
- `demo_llama_index_integration()`: Demonstrate LlamaIndex integration.
- `demo_huggingface_integration()`: Demonstrate HuggingFace integration.
- `demo_endpoint_management()`: Demonstrate model endpoint management.
- `demo_comprehensive_integration()`: Demonstrate comprehensive integration with all frameworks and the model registry.
- `main()`: Main function to run the example.

#### `mcp/examples/encryption_example.py`

End-to-End Encryption Example for MCP Server

This example demonstrates how to use the encryption module to securely
encrypt data and files, manage encryption keys, and implement policies
for different types of content.

Key features demonstrated:
1. Key generation and management
2. Data encryption and decryption
3. File encryption and decryption
4. Policy-based encryption
5. Integration with storage backends

Usage:
  python encryption_example.py [--config CONFIG_PATH] [--storage-path STORAGE_PATH]

**Functions:**
- `demonstrate_key_management()`: Demonstrate key management features.
- `demonstrate_encryption()`: Demonstrate encryption and decryption features.
- `demonstrate_encryption_policies()`: Demonstrate encryption policies.
- `demonstrate_file_encryption()`: Demonstrate file encryption and decryption.
- `demonstrate_backend_integration()`: Demonstrate integration with storage backends.
- `main()`: Main function.

#### `mcp/examples/migration_example.py`

Cross-Backend Data Migration Example for MCP Server

This example demonstrates how to use the migration module to move data between
different storage backends with advanced features like policy-based migration,
validation, and priority-based queuing.

Key features demonstrated:
1. Setting up multiple storage backends
2. Creating and managing migration tasks
3. Performing different migration types (copy, move, sync)
4. Validation and verification of migrated data
5. Monitoring migration progress
6. Policy-based migration decisions

Usage:
  python migration_example.py [--data-dir DATA_DIR]

**Classes:**
- `MockStorageBackend`: Simple mock storage backend for demonstration.
- `MigrationPolicyEngine`: Policy engine for making migration decisions.
- `MigrationDashboard`: Simple text-based dashboard for monitoring migration.

**Functions:**
- `populate_backends()`: Populate backends with sample data.
- `apply_migration_policies()`: Apply migration policies to all content.
- `demonstrate_manual_migrations()`: Demonstrate manual migration task creation and monitoring.
- `main()`: Run the migration management example.

#### `mcp/examples/model_registry_example.py`

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

**Functions:**
- `create_dummy_model_files()`: Create dummy model files for the example.
- `demonstrate_basic_usage()`: Demonstrate basic model registry usage.
- `demonstrate_advanced_usage()`: Demonstrate more advanced model registry usage.
- `run_examples()`: Run all the examples.

#### `mcp/models/storage_bridge.py`

Storage Bridge Model for MCP Server.

This module provides a bridge for cross-backend storage operations, enabling
content transfer, replication, verification, and migration between different
storage backends.

**Classes:**
- `StorageBridgeModel`: Model for cross-backend storage operations.

#### `mcp/models/migration.py`

Migration models for MCP server.

This module defines the data models for the cross-backend migration functionality
as specified in the MCP roadmap Q2 2025 priorities.

**Classes:**
- `MigrationPolicy`: Migration policy definition.
- `MigrationRequest`: Migration request definition.
- `MigrationBatchRequest`: Batch migration request definition.
- `MigrationStatus`: Migration status information.
- `MigrationEstimate`: Migration cost and resource estimation.
- `MigrationSummary`: Summary of migration operations.
- `BackendMigrationCapabilities`: Capabilities of a backend for migration operations.

#### `mcp/models/ipfs_model_initializer.py`

IPFS Model Initializer for MCP server.

This module initializes the IPFSModel with extensions to support MCP server tools.

**Functions:**
- `initialize_ipfs_model()`: Initialize the IPFSModel class with extensions.

#### `mcp/models/ipfs_model.py`

IPFS Model for MCP server.

This module provides the IPFS model for interacting with the IPFS daemon
through the MCP server.

**Classes:**
- `IPFSModel`: IPFS Model for MCP server.

#### `mcp/models/mcp_discovery_model.py`

MCP Discovery Model for automatic MCP server discovery and collaboration.

This model enables MCP servers to discover each other, advertise capabilities,
and collaborate on handling requests. It works via multiple transport layers:
- Direct libp2p peer discovery (DHT, mDNS)
- WebSocket-based discovery for NAT traversal
- Optional manual configuration

Discovered servers can be queried for capabilities and used to offload requests.

**Classes:**
- `MCPServerRole`: MCP server roles for the discovery protocol.
- `MCPMessageType`: Message types for MCP server communication.
- `MCPServerCapabilities`: Standard capability flags for MCP servers.
- `MCPFeatureSet`: Represents a set of features that an MCP server supports.
- `MCPServerInfo`: Information about an MCP server for discovery and coordination.
- `MCPDiscoveryModel`: Model for MCP server discovery and collaboration.

#### `mcp/models/ipfs_model_anyio.py`

IPFS Model for the MCP server.

This model encapsulates IPFS operations and provides a clean interface
for the controller to interact with the IPFS functionality.

**Classes:**
- `AsyncEventLoopHandler`: Handler for properly managing async-io operations in different contexts.
- `IPFSModelAnyIO`: AnyIO compatible IPFS Model implementation.

#### `mcp/models/aria2_model.py`

Aria2 model for MCP server.

This module provides a model for interacting with Aria2 through the MCP server.

**Classes:**
- `Aria2Model`: Model for Aria2 operations in MCP server.

#### `mcp/models/ipfs_model_register.py`

**Functions:**
- `add_content()`: Add content to IPFS.
- `cat()`: Retrieve content from IPFS by CID.
- `pin_add()`: Pin a CID to IPFS.
- `pin_rm()`: Unpin a CID from IPFS.
- `pin_ls()`: List pinned CIDs.

#### `mcp/models/storage_manager.py`

Storage Manager Model for MCP Server.

This model manages storage backends and operations for the MCP server.

**Classes:**
- `StorageManager`: Storage Manager for MCP Server.

#### `mcp/models/ipfs_model_extensions.py`

IPFS Model Extensions for MCP server.

This module provides the missing IPFS model methods needed for the MCP server tools.

**Functions:**
- `add_ipfs_model_extensions()`: Add extension methods to the IPFSModel class.

#### `mcp/models/libp2p_model.py`

LibP2P Model Module

This module provides the LibP2P model functionality for the MCP server.

**Classes:**
- `LibP2PModel`: Model for LibP2P operations.

#### `mcp/models/__init__.py`

Import bridge for MCP models module.
Redirects imports to the new mcp_server structure.

#### `mcp/models/ipfs_model_fix.py`

IPFS Model Fix module.

This module provides a direct fix for the IPFS model to implement the required methods.

**Functions:**
- `fix_ipfs_model()`: Fix the IPFSModel by directly adding the required methods.
- `apply_fixes()`: Apply all fixes to make MCP tools work.

#### `mcp/controllers/credential_controller.py`

Credential Controller for the MCP server.

This controller handles HTTP requests related to credential management for
various storage services like IPFS, S3, Storacha, and Filecoin.

**Classes:**
- `CredentialBaseRequest`: import sys
- `GenericCredentialRequest`: Generic request model for credential operations.
- `S3CredentialRequest`: Request model for S3 credentials.
- `StorachaCredentialRequest`: Request model for Storacha/W3 credentials.
- `FilecoinCredentialRequest`: Request model for Filecoin credentials.
- `IPFSCredentialRequest`: Request model for IPFS credentials.
- `CredentialResponse`: Response model for credential operations.
- `CredentialInfoResponse`: Response model for credential information.
- `CredentialController`: Controller for credential management operations.

#### `mcp/controllers/storage_manager_controller_anyio.py`

Storage Manager Controller AnyIO Module

This module provides AnyIO-compatible storage manager controller functionality.

**Classes:**
- `ReplicationPolicyRequest`: Request model for storage replication policies.
- `ReplicationPolicyResponse`: Response model for storage replication policies.
- `StorageStatsRequest`: Request model for storage statistics.
- `StorageStatsResponse`: Response model for storage statistics.
- `StorageBackendRequest`: Request model for storage backend operations.
- `StorageBackendResponse`: Response model for storage backend operations.
- `StorageManagerControllerAnyIO`: Storage manager controller with AnyIO support.

#### `mcp/controllers/libp2p_controller.py`

LibP2P Controller Module

This module provides the LibP2P controller functionality for the MCP server.

**Classes:**
- `LibP2PController`: Controller for LibP2P operations.

#### `mcp/controllers/fs_journal_controller_anyio.py`

**Classes:**
- `EnableJournalingRequest`
- `MountRequest`
- `MkdirRequest`
- `WriteRequest`
- `ReadRequest`
- `RemoveRequest`
- `MoveRequest`
- `ListDirectoryRequest`
- `ExportRequest`
- `TransactionListRequest`
- `TransactionRequest`: Request model for creating a journal transaction.
- `RecoverRequest`
- `JournalMonitorRequest`
- `JournalVisualizationRequest`
- `JournalDashboardRequest`
- `FsJournalControllerAnyIO`: Controller for Filesystem Journal operations with AnyIO support.
- `APIRouter`
- `HTTPException`
- `BaseModel`
- `JournalOperationType`
- `JournalEntryStatus`

#### `mcp/controllers/distributed_controller_anyio.py`

Distributed Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to distributed operations and
provides cluster-wide coordination, peer discovery, and state synchronization.
This implementation uses AnyIO for backend-agnostic async operations.

**Classes:**
- `DistributedResponse`: import sys
- `PeerDiscoveryRequest`: Request model for peer discovery.
- `PeerDiscoveryResponse`: Response model for peer discovery.
- `ClusterCacheRequest`: Request model for cluster-wide cache operations.
- `ClusterCacheResponse`: Response model for cluster-wide cache operations.
- `ClusterStateRequest`: Request model for cluster state operations.
- `StateSyncRequest`: Request model for state synchronization.
- `ClusterStateResponse`: Response model for cluster state operations.
- `NodeRegistrationRequest`: Request model for node registration.
- `NodeRegistrationResponse`: Response model for node registration.
- `DistributedTaskRequest`: Request model for distributed task operations.
- `DistributedTaskResponse`: Response model for distributed task operations.
- `DistributedControllerAnyIO`: Controller for distributed operations using AnyIO.

#### `mcp/controllers/mcp_discovery_controller.py`

MCP Discovery Controller for the MCP server.

This controller exposes MCP server discovery API endpoints allowing servers to discover
each other, share capabilities, and collaborate on handling requests.

**Classes:**
- `MCPDiscoveryResponse`: import sys
- `ServerInfoResponse`: Response model for server info.
- `ServerListResponse`: Response model for server list.
- `AnnounceRequest`: Request model for announcing a server.
- `RegisterServerRequest`: Request model for registering a server.
- `UpdateServerRequest`: Request model for updating server properties.
- `DiscoverServersRequest`: Request model for discovering servers.
- `DispatchTaskRequest`: Request model for dispatching tasks.
- `MCPDiscoveryController`: Controller for MCP server discovery.

#### `mcp/controllers/aria2_controller.py`

Aria2 controller for MCP server.

This module provides a FastAPI controller for Aria2 operations through the MCP server.

**Classes:**
- `URIListModel`: import sys
- `DownloadIDModel`: Model for download ID.
- `DaemonOptionsModel`: Model for daemon options.
- `MetalinkFileModel`: Model for metalink file creation.
- `Aria2Controller`: Controller for Aria2 operations in MCP server.

#### `mcp/controllers/webrtc_controller_anyio.py`

WebRTC Controller AnyIO Module

This module provides AnyIO-compatible WebRTC controller functionality.

**Classes:**
- `ResourceStatsResponse`: Response model for resource statistics.
- `StreamRequest`: Request model for WebRTC streaming operations.
- `StreamResponse`: Response model for WebRTC streaming operations.
- `WebRTCConnectionRequest`: Request model for WebRTC connection operations.
- `WebRTCConnectionResponse`: Response model for WebRTC connection operations.
- `WebRTCStatsRequest`: Request model for WebRTC statistics.
- `WebRTCStatsResponse`: Response model for WebRTC statistics.
- `WebRTCControllerAnyIO`: WebRTC controller with AnyIO support.

#### `mcp/controllers/webrtc_controller.py`

WebRTC Controller for the MCP server (AnyIO Version).

This controller handles HTTP requests related to WebRTC operations and
delegates the business logic to the IPFS model. It uses AnyIO for async operations.

**Classes:**
- `WebRTCResponse`: import sys
- `ResourceStatsResponse`: Response model for resource statistics.
- `StreamRequest`: Request model for starting a WebRTC stream.
- `StreamResponse`: Response model for starting a WebRTC stream.
- `ConnectionResponse`: Response model for WebRTC connection operations.
- `ConnectionsListResponse`: Response model for listing WebRTC connections.
- `ConnectionStatsResponse`: Response model for WebRTC connection statistics.
- `DependencyResponse`: Response model for WebRTC dependency check.
- `BenchmarkRequest`: Request model for running a WebRTC benchmark.
- `BenchmarkResponse`: Response model for WebRTC benchmark results.
- `QualityRequest`: Request model for changing WebRTC quality.
- `WebRTCController`: Controller for WebRTC operations (AnyIO version).
- `BaseModel`

#### `mcp/controllers/credential_controller_anyio.py`

Credential Controller for the MCP server using AnyIO.

This controller handles HTTP requests related to credential management for
various storage services like IPFS, S3, Storacha, and Filecoin.

This implementation uses AnyIO for backend-agnostic async operations.

**Classes:**
- `CredentialControllerAnyIO`: Controller for credential management operations using AnyIO.

#### `mcp/controllers/filecoin_controller.py`

Filecoin Controller for MCP Server.

This controller handles Filecoin-related operations for the MCP server.

**Classes:**
- `FilecoinController`: Filecoin Controller for MCP Server.

#### `mcp/controllers/libp2p_controller_anyio.py`

LibP2P Controller AnyIO Module

This module provides the AnyIO-compatible LibP2P controller functionality.

**Classes:**
- `LibP2PControllerAnyIO`: AnyIO-compatible controller for LibP2P operations.

#### `mcp/controllers/ipfs_controller_anyio.py`

IPFS Controller AnyIO Module

This module provides AnyIO-compatible IPFS controller functionality.

**Classes:**
- `ReadFileRequest`: Request model for reading file operations.
- `WriteFileRequest`: Request model for writing file operations.
- `RemoveFileRequest`: Request model for removing file operations.
- `CopyFileRequest`: Request model for copying file operations.
- `MoveFileRequest`: Request model for moving file operations.
- `FlushFilesRequest`: Request model for flushing files operations.
- `MakeDirRequest`: Request model for making directory operations.
- `StreamRequest`: Request model for streaming operations.
- `IPFSOperationRequest`: Request model for IPFS operations.
- `ResourceStatsResponse`: Response model for resource statistics.
- `ReplicationPolicyResponse`: Response model for replication policy information.
- `IPFSControllerAnyIO`: AnyIO-compatible controller for IPFS operations.

#### `mcp/controllers/peer_websocket_controller.py`

Peer WebSocket Controller for the MCP server.

This controller handles WebSocket peer discovery, allowing peers to find each other
through WebSocket connections even in environments with NAT or firewalls.

**Classes:**
- `PeerWebSocketResponse`: Base response model for peer WebSocket operations.
- `StartServerRequest`: Request model for starting a peer WebSocket server.
- `StartServerResponse`: Response model for starting a peer WebSocket server.
- `ConnectToServerRequest`: Request model for connecting to a peer WebSocket server.
- `ConnectToServerResponse`: Response model for connecting to a peer WebSocket server.
- `DiscoveredPeersResponse`: Response model for listing discovered peers.
- `PeerWebSocketController`: Controller for peer WebSocket discovery.

#### `mcp/controllers/webrtc_video_controller.py`

WebRTC Video Player Controller for the MCP Server.

This module provides endpoints for the WebRTC video player page
which includes random seek functionality.

**Classes:**
- `WebRTCVideoPlayerController`: Controller for the WebRTC video player.

**Functions:**
- `create_webrtc_video_player_router()`: Create a FastAPI router with WebRTC video player endpoints.

#### `mcp/controllers/aria2_controller_anyio.py`

**Classes:**
- `Aria2ControllerAnyIO`: Controller for Aria2 operations in MCP server with AnyIO support.
- `APIRouter`
- `HTTPException`
- `BaseModel`
- `Aria2Model`
- `Aria2Controller`
- `URIListModel`
- `DownloadIDModel`
- `DaemonOptionsModel`
- `MetalinkFileModel`

#### `mcp/controllers/peer_websocket_controller_anyio.py`

Peer WebSocket Controller for the MCP server using AnyIO.

This controller handles WebSocket peer discovery, allowing peers to find each other
through WebSocket connections even in environments with NAT or firewalls.

This implementation uses AnyIO for backend-agnostic async operations.

**Classes:**
- `PeerWebSocketResponse`: Base response model for peer WebSocket operations.
- `StartServerRequest`: Request model for starting a peer WebSocket server.
- `StartServerResponse`: Response model for starting a peer WebSocket server.
- `ConnectToServerRequest`: Request model for connecting to a peer WebSocket server.
- `ConnectToServerResponse`: Response model for connecting to a peer WebSocket server.
- `DiscoveredPeersResponse`: Response model for listing discovered peers.
- `PeerWebSocketControllerAnyIO`: Controller for peer WebSocket discovery using AnyIO.
- `PeerInfo`
- `PeerWebSocketServer`
- `PeerWebSocketClient`
- `PeerRole`
- `MessageType`

#### `mcp/controllers/migration_controller.py`

Enhanced Migration Controller for MCP Server.

This controller implements the Cross-Backend Data Migration functionality
as specified in the MCP roadmap Q2 2025 priorities:
- Seamless content transfer between storage systems
- Migration policy management and execution
- Cost-optimized storage placement

This is an enhanced implementation that builds upon the migration_extension.py
to provide deeper integration with the MCP architecture.

**Classes:**
- `MigrationController`: Controller for managing cross-backend migrations.

#### `mcp/controllers/protected_api_controller.py`

Protected API endpoints for MCP server.

This controller demonstrates how to use the authentication and authorization
middleware to create protected API endpoints with different security requirements.

**Classes:**
- `ProtectedAPIController`: Controller for protected API endpoints.

#### `mcp/controllers/mcp_discovery_controller_anyio.py`

**Classes:**
- `MCPDiscoveryResponse`: Base response model for MCP discovery operations.
- `ServerInfoResponse`: Response model for server info.
- `ServerListResponse`: Response model for server list.
- `AnnounceRequest`: Request model for announcing a server.
- `RegisterServerRequest`: Request model for registering a server.
- `UpdateServerRequest`: Request model for updating server properties.
- `DiscoverServersRequest`: Request model for discovering servers.
- `DispatchTaskRequest`: Request model for dispatching tasks.
- `MCPDiscoveryControllerAnyIO`: Controller for MCP server discovery with AnyIO support.
- `APIRouter`
- `HTTPException`
- `BaseModel`
- `MCPServerRole`
- `MCPMessageType`
- `MCPServerCapabilities`
- `MCPFeatureSet`
- `MCPServerInfo`
- `MCPDiscoveryModel`

#### `mcp/controllers/ipfs_controller.py`

IPFS Controller for the MCP server.

This controller provides an interface to the IPFS functionality through the MCP API.

**Classes:**
- `PeerAddressRequest`: Request model for a peer address.
- `SwarmPeersResponse`: Response model for swarm peers request.
- `SwarmConnectResponse`: Response model for swarm connect request.
- `SwarmDisconnectResponse`: Response model for swarm disconnect request.
- `ContentRequest`: Request model for adding content.
- `CIDRequest`: Request model for operations using a CID.
- `OperationResponse`: Base response model for operations.
- `AddContentResponse`: Response model for adding content.
- `GetContentResponse`: Response model for getting content.
- `PinResponse`: Response model for pin operations.
- `FilesLsRequest`: Request model for listing files in MFS.
- `FilesMkdirRequest`: Request model for creating a directory in MFS.
- `FilesStatRequest`: Request model for getting file stats in MFS.
- `FilesWriteRequest`: Request model for writing to a file in MFS.
- `FilesReadRequest`: Request model for reading a file from MFS.
- `FilesRmRequest`: Request model for removing a file/directory from MFS.
- `ListPinsResponse`: Response model for listing pins.
- `ReplicationStatusResponse`: Response model for replication status.
- `MakeDirRequest`: Request model for creating a directory in MFS.
- `StatsResponse`: Response model for operation statistics.
- `DaemonStatusRequest`: Request model for checking daemon status.
- `DaemonStatusResponse`: Response model for daemon status checks.
- `DAGPutRequest`: Request model for putting a DAG node.
- `DAGPutResponse`: Response model for putting a DAG node.
- `DAGGetResponse`: Response model for getting a DAG node.
- `DAGResolveResponse`: Response model for resolving a DAG path.
- `BlockPutRequest`: Request model for putting a block.
- `BlockPutResponse`: Response model for putting a block.
- `BlockGetResponse`: Response model for getting a block.
- `BlockStatResponse`: Response model for block statistics.
- `DHTFindPeerRequest`: Request model for finding a peer using DHT.
- `DHTFindPeerResponse`: Response model for finding a peer using DHT.
- `DHTFindProvsRequest`: Request model for finding providers for a CID using DHT.
- `DHTFindProvsResponse`: Response model for finding providers for a CID using DHT.
- `NodeIDResponse`: Response model for node ID information.
- `GetTarResponse`: Response model for getting content as TAR archive.
- `FileUploadForm`: Form model for file uploads.
- `IPFSController`: Controller for IPFS operations.
- `Config`

#### `mcp/controllers/fs_journal_controller.py`

REST API controller for Filesystem Journal functionality.

This module provides API endpoints for interacting with the Filesystem Journal
through the MCP server.

**Classes:**
- `FileSystemOperationRequest`: Base model for file system operations.
- `FileSystemOperationResponse`: Base model for file system operation responses.
- `FsJournalController`: Controller for Filesystem Journal operations.
- `APIRouter`
- `BaseModel`

#### `mcp/controllers/__init__.py`

Controllers package for the MCP server.

#### `mcp/controllers/cli_controller.py`

CLI Controller for the MCP server.

This controller provides an interface to the CLI functionality through the MCP API.

**Classes:**
- `FormatType`: Output format types.
- `CliCommandRequest`: Request model for executing CLI commands.
- `CliCommandResponse`: Response model for CLI command execution.
- `CliVersionResponse`: Response model for CLI version information.
- `CliWalStatusResponse`: Response model for WAL status information.
- `CliController`: Controller for CLI operations.
- `IPFSSimpleAPI`
- `BaseModel`
- `APIRouter`
- `HTTPException`
- `Response`

#### `mcp/controllers/storage_manager_controller.py`

Storage Manager Controller for MCP Server.

This controller provides a unified interface for managing multiple storage backends
and their integration with the MCP server.

**Classes:**
- `OperationResponse`: Base response model for operations.
- `ReplicationPolicyRequest`: Request model for applying replication policies to content.
- `ReplicationPolicyResponse`: Response model for replication policy application.
- `BackendStatusResponse`: Response model for backend status information.
- `AllBackendsStatusResponse`: Response model for status of all storage backends.
- `StorageTransferRequest`: Request model for transferring content between storage backends.
- `StorageTransferResponse`: Response model for content transfer operations.
- `ContentMigrationRequest`: Request model for migrating content between storage backends.
- `ContentMigrationResponse`: Response model for content migration operations.
- `StorageManagerController`: Controller for storage manager operations.

#### `mcp/controllers/webrtc_video_controller_anyio.py`

WebRTC Video Player Controller for the MCP Server (AnyIO version).

This module provides endpoints for the WebRTC video player page
which includes random seek functionality.

This version uses AnyIO for backend-agnostic async operations.

**Classes:**
- `WebRTCVideoPlayerControllerAnyIO`: Controller for the WebRTC video player (AnyIO version).

**Functions:**
- `create_webrtc_video_player_router()`: Create a FastAPI router with WebRTC video player endpoints.

#### `mcp/controllers/distributed_controller.py`

Distributed Controller for the MCP server.

This controller handles HTTP requests related to distributed operations and
provides cluster-wide coordination, peer discovery, and state synchronization.

**Classes:**
- `DistributedResponse`: Base response model for distributed operations.
- `PeerDiscoveryRequest`: Request model for peer discovery.
- `PeerDiscoveryResponse`: Response model for peer discovery.
- `ClusterCacheRequest`: Request model for cluster-wide cache operations.
- `ClusterCacheResponse`: Response model for cluster-wide cache operations.
- `ClusterStateRequest`: Request model for cluster state operations.
- `StateSyncRequest`: Request model for state synchronization.
- `ClusterStateResponse`: Response model for cluster state operations.
- `NodeRegistrationRequest`: Request model for node registration.
- `NodeRegistrationResponse`: Response model for node registration.
- `DistributedTaskRequest`: Request model for distributed task operations.
- `DistributedTaskResponse`: Response model for distributed task operations.
- `DistributedController`: Controller for distributed operations.

#### `mcp/utils/enhanced_cache.py`

Enhanced Caching System for MCP Server

This module provides an optimized caching system for the MCP server,
addressing the caching improvements mentioned in the MCP roadmap.

Features:
- Multi-level caching (memory, shared memory, distributed)
- Configurable TTL and eviction policies
- Memory usage optimization with size limits
- Thread-safe operations
- Performance metrics tracking
- Automatic pruning of expired entries

**Classes:**
- `CacheMetrics`: Track cache performance metrics.
- `LRUCache`: Memory-efficient LRU (Least Recently Used) cache implementation.
- `TTLCache`: Time-based cache with automatic expiration of items.
- `MultiLevelCache`: Multi-level caching system with tiered storage.

**Functions:**
- `cached()`: Create a cached version of a function.

#### `mcp/utils/file_watcher.py`

File watching utility for MCP server.

This module provides functionality to watch for file changes
and automatically restart the MCP server when changes are detected.

**Classes:**
- `MCPFileHandler`: File system event handler for MCP server files.
- `MCPFileWatcher`: File watcher for MCP server.
- `ErrorCaptureHandler`

#### `mcp/utils/text_extraction.py`

Text extraction utilities for MCP search functionality.

This module provides utilities to extract text from various file formats
to enable better search indexing and content discovery.

**Functions:**
- `extract_text()`: Extract text from various file formats for search indexing.
- `extract_text_from_json()`: Extract text from JSON data, recursively processing structures.
- `extract_text_from_pdf()`: Extract text from PDF data.
- `extract_text_from_docx()`: Extract text from DOCX data.
- `extract_text_from_image()`: Extract text from image data using OCR.
- `extract_text_from_html()`: Extract text from HTML, removing tags.
- `extract_text_from_xml()`: Extract text from XML, removing tags.
- `is_likely_text()`: Check if data is likely to be text based on byte patterns.

#### `mcp/utils/standardized_error_handling.py`

Standardized error handling for MCP storage backends.

This module provides consistent error handling across all storage backends
to improve troubleshooting and user experience.

**Functions:**
- `get_error_category()`: Determine the error category based on error message patterns.
- `get_context_from_exception()`: Extract context information from an exception.
- `create_enhanced_error_response()`: Create an enhanced error response with troubleshooting information.
- `handle_backend_errors()`: Decorator for handling backend operation errors consistently.
- `handle_backend_errors_async()`: Decorator for handling async backend operation errors consistently.
- `graceful_degradation()`: Decorator for implementing graceful degradation when services are unavailable.
- `graceful_degradation_async()`: Decorator for implementing graceful degradation for async functions when services are unavailable.

#### `mcp/utils/__init__.py`

Utility modules for the MCP server.

This package contains various utility modules that provide common functionality
for the MCP server components.

#### `mcp/utils/method_normalizer.py`

Method Normalizer Module

This module provides utilities for normalizing method interfaces across different
implementations of IPFS clients.

**Classes:**
- `IPFSMethodAdapter`: Adapter for normalizing IPFS method interfaces.
- `NormalizedIPFS`: A normalized interface for IPFS operations.

**Functions:**
- `normalize_instance()`: Create a normalized IPFS interface for any IPFS implementation.

#### `mcp/streaming/webrtc_signaling.py`

WebRTC signaling implementation for MCP server.

This module implements the WebRTC signaling capabilities mentioned in the roadmap,
providing peer-to-peer connection establishment and room-based peer discovery.

**Classes:**
- `PeerConnection`: Information about a peer connection.
- `Room`: WebRTC signaling room.
- `SignalingServer`: WebRTC signaling server implementation.

#### `mcp/streaming/file_streaming.py`

File streaming implementation for MCP server.

This module implements the optimized file streaming capabilities
mentioned in the roadmap, including chunked processing, memory-optimized
streaming downloads, and background pinning operations.

**Classes:**
- `ChunkInfo`: Information about a file chunk.
- `ProgressInfo`: Information about upload/download progress.
- `ProgressTracker`: Track progress of streaming operations.
- `ChunkedFileUploader`: Chunked file uploader for efficient large file uploads.
- `StreamingDownloader`: Streaming downloader for memory-efficient downloads.
- `BackgroundPinningManager`: Manager for background pinning operations.

#### `mcp/streaming/websocket_notifications.py`

WebSocket notifications implementation for MCP server.

This module implements the WebSocket integration mentioned in the roadmap,
providing real-time event notifications to clients.

**Classes:**
- `EventType`: Types of events for WebSocket notifications.
- `WebSocketClient`: Represents a connected WebSocket client.
- `WebSocketManager`: Manager for WebSocket connections and notifications.

**Functions:**
- `get_ws_manager()`: Get the WebSocket manager singleton instance.

#### `mcp/streaming/websocket_server.py`

WebSocket server implementation for MCP server.

This module provides a concrete server implementation for the WebSocket
notifications system, addressing the WebSocket Integration requirements
in the MCP roadmap, particularly the 'Connection management with automatic recovery' component.

**Classes:**
- `WebSocketServer`: WebSocket server for the MCP system.

**Functions:**
- `get_ws_server()`: Get the global WebSocket server instance.

#### `mcp/streaming/ipfs_streaming.py`

IPFS streaming operations utility.

This module provides utilities for streaming operations with IPFS,
implementing efficient chunked uploads and downloads.

**Classes:**
- `StreamingUploader`: Handles chunked uploads to IPFS.
- `StreamingDownloader`: Handles memory-optimized streaming downloads from IPFS.
- `BackgroundPinningManager`: Manages background pinning operations.

**Functions:**
- `create_background_operation()`: Create a record for a background operation.

#### `mcp/streaming/__init__.py`

MCP Streaming Module for efficient transfer of large content.

This module provides basic streaming types and constants used by both
synchronous and asynchronous streaming implementations.

**Classes:**
- `StreamStatus`: Status of a stream operation.
- `StreamDirection`: Direction of a stream operation.
- `StreamType`: Type of streaming operation.
- `StreamProgress`: Progress information for a stream operation.
- `StreamOperation`: Information about a streaming operation.

#### `mcp/extensions/metrics.py`

Metrics extension for the MCP server.

This extension provides Prometheus metrics reporting for MCP.

**Functions:**
- `create_metrics_router()`: Create a FastAPI router with metrics and monitoring endpoints.
- `create_health_router()`: Create a FastAPI router with enhanced health check endpoints.
- `update_metrics_status()`: Update storage_backends with monitoring system status.

#### `mcp/extensions/udm.py`

Unified Data Management extension for MCP server.

This module provides a single interface for all storage operations across backends
as specified in the MCP roadmap Q2 2025 priorities.

Features:
- Single interface for all storage operations
- Content addressing across backends
- Metadata synchronization and consistency

**Classes:**
- `StoreRequest`: Store content request model.
- `ContentInfo`: Content information model.
- `ContentQuery`: Content query parameters.

**Functions:**
- `initialize_content_registry()`: Initialize content registry from file or create empty.
- `initialize_metadata_registry()`: Initialize metadata registry from file or create empty.
- `initialize_content_map()`: Initialize content map from file or create empty.
- `save_content_registry()`: Save content registry to file.
- `save_metadata_registry()`: Save metadata registry to file.
- `save_content_map()`: Save content map to file.
- `create_content_id()`: Create a content ID from binary content.
- `get_backend_module()`: Get the backend module for a specific backend.
- `get_available_backends()`: Get list of available backends.
- `map_backend_cid()`: Map a backend-specific CID to the unified CID.
- `get_unified_cid_from_backend()`: Get the unified CID for a backend-specific CID.
- `get_backend_cid()`: Get the backend-specific CID for a unified CID.
- `filter_content_by_query()`: Filter content registry based on query parameters.
- `create_udm_router()`: Create FastAPI router for unified data management.
- `update_udm_status()`: Update the reference to storage backends status.
- `initialize()`: Initialize the unified data management system.

#### `mcp/extensions/migration.py`

Migration extension for MCP server.

This module provides functionality for Cross-Backend Data Migration as specified
in the MCP roadmap Q2 2025 priorities.

Features:
- Seamless content transfer between storage systems
- Migration policy management and execution
- Cost-optimized storage placement

**Classes:**
- `MigrationPolicy`: Migration policy definition.
- `MigrationRequest`: Migration request definition.
- `MigrationStatus`: Migration status information.

**Functions:**
- `get_backend_module()`: Get the backend module by name.
- `create_migration_router()`: Create FastAPI router for migration endpoints.
- `update_migration_status()`: Update the reference to storage backends status.

#### `mcp/extensions/websocket.py`

WebSocket extension for MCP server.

This extension integrates WebSocket functionality for real-time event streaming
and notifications into the MCP server.

**Functions:**
- `create_websocket_extension_router()`: Create a FastAPI router for WebSocket endpoints.
- `update_websocket_status()`: Update storage_backends with WebSocket status.
- `register_app_websocket_routes()`: Register WebSocket routes directly with the FastAPI app.
- `setup_mcp_event_hooks()`: Set up event hooks for MCP server operations.

#### `mcp/extensions/enhanced_lassie.py`

Enhanced endpoints for Lassie integration in the MCP server.

This module adds robust Lassie integration to the MCP server with improved
error handling, fallback mechanisms, and support for well-known CIDs.

**Functions:**
- `create_lassie_router()`: Create a FastAPI router with Lassie endpoints.
- `update_lassie_status()`: Update storage_backends dictionary with actual Lassie status.

#### `mcp/extensions/webrtc.py`

WebRTC extension for the MCP server.

This extension provides WebRTC functionality for peer-to-peer communication, including:
- Signaling for WebRTC peer connection establishment
- Room-based peer discovery
- Direct data channel communication
- Efficient binary data transfer

**Classes:**
- `WebRTCSignalingManager`: Manager for WebRTC signaling operations.

**Functions:**
- `get_signaling_manager()`: Get or create the WebRTC signaling manager.
- `create_webrtc_router()`: Create a FastAPI router for WebRTC endpoints.
- `create_webrtc_extension_router()`: Create a FastAPI router for WebRTC extension endpoints.
- `update_webrtc_status()`: Update storage_backends with WebRTC status.
- `on_startup()`: Initialize the WebRTC extension on server startup.
- `on_shutdown()`: Clean up the WebRTC extension on server shutdown.

#### `mcp/extensions/advanced_ipfs_router.py`

Advanced IPFS Operations Router for MCP Server.

This module provides API endpoints for the enhanced IPFS functionality,
including connection pooling, DHT operations, IPNS key management,
and comprehensive DAG manipulation.

**Classes:**
- `DHTProvideRequest`: Request model for providing content in DHT.
- `DHTFindProvidersRequest`: Request model for finding providers in DHT.
- `DHTFindPeerRequest`: Request model for finding a peer in DHT.
- `DHTQueryRequest`: Request model for querying the DHT.
- `DHTDiscoverPeersRequest`: Request model for discovering peers in the network.
- `CreateKeyRequest`: Request model for creating an IPNS key.
- `ImportKeyRequest`: Request model for importing an IPNS key.
- `ExportKeyRequest`: Request model for exporting an IPNS key.
- `RenameKeyRequest`: Request model for renaming an IPNS key.
- `RemoveKeyRequest`: Request model for removing an IPNS key.
- `RotateKeyRequest`: Request model for rotating an IPNS key.
- `PublishRequest`: Request model for publishing an IPNS name.
- `ResolveRequest`: Request model for resolving an IPNS name.
- `RepublishRequest`: Request model for republishing an IPNS record.
- `DAGPutRequest`: Request model for storing a DAG node.
- `DAGGetRequest`: Request model for retrieving a DAG node.
- `DAGResolveRequest`: Request model for resolving an IPLD path.
- `DAGUpdateNodeRequest`: Request model for updating a DAG node.
- `DAGAddLinkRequest`: Request model for adding a link to a DAG node.
- `DAGRemoveLinkRequest`: Request model for removing a link from a DAG node.
- `BaseResponse`: Base response model for all operations.
- `AdvancedIPFSRouter`: Router for advanced IPFS operations.

**Functions:**
- `create_router()`: Create and configure an APIRouter for advanced IPFS operations.

#### `mcp/extensions/s3.py`

S3 extension integration with enhanced local storage.

This module integrates the enhanced S3 storage backend with the MCP server.

**Functions:**
- `create_s3_router()`: Create a FastAPI router with S3 endpoints.
- `update_s3_status()`: Update storage_backends dictionary with actual S3 status.

#### `mcp/extensions/auth.py`

Authentication and Authorization Extension for MCP Server

This extension integrates authentication and authorization features with the MCP server,
providing user management, API key generation, and role-based access control.

**Functions:**
- `require_permission()`: Factory for dependency to require specific permission.
- `create_auth_router()`: Create a FastAPI router with authentication endpoints.
- `update_auth_status()`: Update storage_backends with auth manager status.

#### `mcp/extensions/filecoin.py`

Enhanced endpoints for Filecoin integration in the MCP server.

This module adds Filecoin integration to the MCP server
replacing the simulation with actual functionality.

#### `mcp/extensions/filecoin_connection.py`

Filecoin API Connection Manager

This module provides improved connection handling for Filecoin API interactions,
implementing robust error handling, retry logic, and automatic endpoint failover.

**Classes:**
- `FilecoinApiError`: Exception raised for Filecoin API errors.
- `FilecoinConnectionManager`: Connection manager for Filecoin API with enhanced reliability features.

#### `mcp/extensions/huggingface.py`

Enhanced endpoints for HuggingFace integration in the robust MCP server.

This module adds HuggingFace integration to the existing robust MCP server,
replacing the simulation with actual functionality.

**Functions:**
- `create_huggingface_router()`: Create a FastAPI router with HuggingFace endpoints.
- `update_huggingface_status()`: Update storage_backends dictionary with actual HuggingFace status.

#### `mcp/extensions/ipfs_advanced_init.py`

Advanced IPFS Operations Integration for MCP Server.

This module initializes and integrates the enhanced IPFS operations
with the MCP server, providing connection pooling, DHT operations,
IPNS key management, and DAG operations.

**Functions:**
- `init_advanced_ipfs()`: Initialize and integrate advanced IPFS operations with the MCP server.
- `shutdown_advanced_ipfs()`: Shutdown advanced IPFS operations.

#### `mcp/extensions/advanced_filecoin_mcp.py`

Advanced Filecoin MCP Integration

This module integrates the advanced Filecoin features with the MCP storage manager.
It enhances the standard Filecoin backend with additional capabilities including:

1. Network Analytics & Metrics
2. Intelligent Miner Selection & Management
3. Enhanced Storage Operations
4. Content Health & Reliability
5. Blockchain Integration

This implementation fulfills the requirements specified in the MCP roadmap
under the "Advanced Filecoin Integration" section.

**Classes:**
- `AdvancedFilecoinMCP`: Integration layer between MCP and advanced Filecoin features.

**Functions:**
- `create_advanced_filecoin_mcp()`: Create and configure an advanced Filecoin MCP integration.

#### `mcp/extensions/s3_connection.py`

S3 API Connection Manager

This module provides improved connection handling for S3-compatible storage services,
implementing robust error handling, retry logic, and automatic endpoint failover.

**Classes:**
- `S3ApiError`: Exception raised for S3 API errors.
- `S3ConnectionManager`: Connection manager for S3-compatible APIs with enhanced reliability features.

#### `mcp/extensions/routing.py`

Enhanced routing extension for the MCP server.

This module adds advanced routing capabilities to the MCP server
including distributed route discovery and content routing.

#### `mcp/extensions/ipfs_advanced.py`

Advanced IPFS Operations Extension

This module extends the basic IPFS backend with advanced operations:
- DAG manipulation (get, put, resolve, stat)
- Object manipulation (new, patch, stat)
- Names/IPNS functionality with key management
- Enhanced DHT operations
- Swarm and peer management

This implements the "Advanced IPFS Operations" feature from the MCP Roadmap Phase 1.

**Classes:**
- `IPFSAdvancedOperations`: Advanced IPFS operations implementation.

**Functions:**
- `get_instance()`: Get or create a singleton instance of the advanced operations module.

#### `mcp/extensions/enhanced_ipfs.py`

Enhanced IPFS operations extension for MCP server.

This module adds additional IPFS operations that are currently missing from
the MCP server, including DHT, object, and DAG manipulation commands.

**Functions:**
- `create_ipfs_router()`: Create a FastAPI router with enhanced IPFS endpoints.
- `run_ipfs_command()`: Run an IPFS command and return the result.

#### `mcp/extensions/search.py`

Search extension for MCP server.

This extension integrates the search functionality from mcp_search.py
into the MCP server, providing content indexing, metadata search, and
vector search capabilities.

**Functions:**
- `get_search_service()`: Get or initialize the search service.
- `create_search_router_wrapper()`: Create a FastAPI router for search endpoints.
- `update_search_status()`: Update storage_backends with search status.
- `on_startup()`: Initialize the search extension on server startup.
- `on_shutdown()`: Clean up the search extension on server shutdown.

#### `mcp/extensions/lassie.py`

Enhanced endpoints for Lassie integration in the MCP server.

This module adds robust Lassie integration to the MCP server with improved
error handling, fallback mechanisms, and support for well-known CIDs.

**Functions:**
- `create_lassie_router()`: Create a FastAPI router with Lassie endpoints.
- `update_lassie_status()`: Update storage_backends dictionary with actual Lassie status.

#### `mcp/extensions/advanced_ipfs_operations.py`

Advanced IPFS Operations Extension for MCP Server.

This extension integrates enhanced IPFS operations with the MCP server,
providing improved connection pooling, DHT operations, IPNS with advanced
key management, and comprehensive DAG manipulation.

**Classes:**
- `AdvancedIPFSOperations`: Provides enhanced IPFS functionality for the MCP server.

**Functions:**
- `get_instance()`: Get or create singleton instance of AdvancedIPFSOperations.

#### `mcp/extensions/enhanced_filecoin.py`

Enhanced Filecoin integration for MCP server.

This module provides a real (non-mocked) integration with Filecoin
by using the Lotus gateway to connect to the Filecoin network.

**Classes:**
- `EnhancedFilecoinGateway`: Enhanced Filecoin gateway client for real network integration.

**Functions:**
- `create_filecoin_router()`: Create a FastAPI router with Filecoin endpoints.
- `update_filecoin_status()`: Update storage_backends dictionary with actual Filecoin status.

#### `mcp/extensions/__init__.py`

MCP extensions integration module.

This module provides unified access to all MCP extensions and handles
updating storage backends status information.

**Functions:**
- `create_extension_routers()`: Create FastAPI routers for all available extensions.
- `update_storage_backends()`: Update storage_backends with status from all extensions.

#### `mcp/extensions/ipfs_advanced_router.py`

Advanced IPFS Operations API router.

This module provides FastAPI routes for the advanced IPFS operations including:
- DAG (Directed Acyclic Graph) operations
- Object manipulation
- IPNS and key management
- Swarm and network management

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `StatusResponse`: Standard response model with operation status.
- `DagGetRequest`: Request model for DAG get operation.
- `DagPutRequest`: Request model for DAG put operation.
- `DagResolveRequest`: Request model for DAG resolve operation.
- `ObjectNewRequest`: Request model for object new operation.
- `ObjectPutRequest`: Request model for object put operation.
- `ObjectPatchAddLinkRequest`: Request model for object patch add-link operation.
- `ObjectPatchRmLinkRequest`: Request model for object patch rm-link operation.
- `ObjectPatchSetDataRequest`: Request model for object patch set-data operation.
- `NamePublishRequest`: Request model for name publish operation.
- `NameResolveRequest`: Request model for name resolve operation.
- `KeyGenRequest`: Request model for key gen operation.
- `KeyRenameRequest`: Request model for key rename operation.
- `KeyImportRequest`: Request model for key import operation.
- `SwarmConnectRequest`: Request model for swarm connect operation.
- `BootstrapAddRequest`: Request model for bootstrap add operation.

#### `mcp/extensions/ipfs_advanced_integration.py`

Advanced IPFS Integration for MCP

This module integrates the advanced IPFS operations into the MCP server framework.
It provides FastAPI route handlers and necessary glue code.

**Functions:**
- `get_advanced_ipfs()`: Get or create an instance of the AdvancedIPFSOperations class.
- `register_advanced_ipfs_routes()`: Register the advanced IPFS routes with the FastAPI application.

#### `mcp/extensions/streaming.py`

Streaming extension for MCP server.

This extension integrates the streaming functionality from mcp_streaming.py
into the MCP server, providing optimized file streaming capabilities.

**Functions:**
- `get_streaming_ops()`: Get or initialize the streaming operations.
- `create_streaming_router_wrapper()`: Create a FastAPI router for streaming endpoints.
- `update_streaming_status()`: Update storage_backends with streaming status.
- `on_startup()`: Initialize the streaming extension on server startup.
- `on_shutdown()`: Clean up the streaming extension on server shutdown.

#### `mcp/extensions/storacha_connection.py`

Storacha API Connection Manager

This module provides improved connection handling for the Storacha API,
implementing robust error handling, retry logic, and automatic endpoint failover.

**Classes:**
- `StorachaApiError`: Exception raised for Storacha API errors.
- `StorachaConnectionManager`: Connection manager for Storacha API with enhanced reliability features.

#### `mcp/extensions/ipfs_integrator.py`

Integration module for enhanced IPFS operations.

This module integrates the enhanced IPFS operations into the main MCP server.

**Functions:**
- `integrate_enhanced_ipfs()`: Integrate enhanced IPFS operations into the main server.

#### `mcp/extensions/storacha.py`

Enhanced endpoints for Storacha integration in the MCP server.

This module adds Storacha integration to the MCP server using the W3 Blob Protocol,
with proper implementation for the new endpoint structure.

**Functions:**
- `create_storacha_router()`: Create a FastAPI router with Storacha endpoints.
- `update_storacha_status()`: Update storage_backends dictionary with actual Storacha status.

#### `mcp/monitoring/metrics.py`

Enhanced Metrics & Monitoring Module

This module implements a comprehensive metrics collection, monitoring,
and reporting system for the MCP server, featuring:

- Prometheus integration
- Custom metrics tracking
- Runtime performance monitoring
- Backend-specific metrics
- Health check endpoints

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `MetricType`: Types of metrics supported by the monitoring system.
- `MetricLabel`: Common metric labels used across the system.
- `MCPMetrics`: Enhanced metrics and monitoring system for the MCP server.

**Functions:**
- `get_instance()`: Get or create a singleton instance of the metrics system.

#### `mcp/monitoring/metrics_optimized.py`

Memory-Optimized Metrics & Monitoring Module

This module implements a memory-efficient metrics collection, monitoring,
and reporting system for the MCP server, addressing the memory usage issue
highlighted in the MCP Status document.

Key optimizations:
- Circular buffer time series with configurable retention
- Reservoir sampling for histogram/summary metrics
- Efficient label storage mechanism
- Optional downsampling for high-frequency metrics
- Memory usage tracking and aggressive pruning

**Classes:**
- `MetricType`: Types of metrics supported by the monitoring system.
- `MetricLabel`: Common metric labels used across the system.
- `LabelKey`: Memory-efficient immutable label key
- `CircularBuffer`: Memory-efficient circular buffer for time series data.
- `ReservoirSample`: Reservoir sampling implementation for maintaining a representative
- `MCPMetricsOptimized`: Memory-optimized metrics and monitoring system for the MCP server.

**Functions:**
- `get_instance()`: Get or create a singleton instance of the metrics system.

#### `mcp/monitoring/metrics_router.py`

Metrics and Monitoring API Router

This module provides FastAPI routes for the enhanced monitoring system including:
- Prometheus metrics endpoint
- Health check endpoints
- Monitoring dashboard API

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `HealthStatus`: Health status response model.
- `MetricDataPoint`: Model for a metric data point.
- `MetricSeries`: Model for a time series of metric data points.
- `BackendHealth`: Model for backend health status.

**Functions:**
- `register_default_health_checks()`: Register default health checks with the metrics system.

#### `mcp/monitoring/health_checker.py`

Health Checker for MCP Server.

This module provides health check functionality for the MCP server,
allowing for monitoring of component health and system status.

**Classes:**
- `HealthStatus`: Enum representing the health status of a component.
- `ComponentHealth`: Represents the health status of a component.
- `HealthChecker`: Health checker for the MCP server.

**Functions:**
- `get_health_checker()`: Get or create the default health checker.
- `check_component_health()`: Update the health status of a component using the default health checker.
- `register_component()`: Register a component with the default health checker.

#### `mcp/monitoring/ipfs_prometheus.py`

Prometheus Integration for IPFS Operations.

This module provides Prometheus metrics collection and export capabilities
for the advanced IPFS operations, enabling comprehensive monitoring and
performance analytics.

**Classes:**
- `IPFSMetrics`: Prometheus metrics for IPFS operations.
- `PrometheusExporter`: Prometheus metrics exporter for IPFS operations.

**Functions:**
- `get_metrics_instance()`: Get or create a singleton metrics instance.
- `get_exporter_instance()`: Get or create a singleton exporter instance.

#### `mcp/monitoring/ipfs_monitoring.py`

IPFS Monitoring Integration.

This module integrates the advanced IPFS operations with Prometheus metrics
and provides health check endpoints for monitoring system status.

**Classes:**
- `HealthCheckResponse`: Response model for health check endpoint.
- `MetricsResponse`: Response model for metrics endpoint.
- `IPFSMonitoringIntegration`: Integration of IPFS operations with monitoring systems.
- `IPFSMonitoringRouter`: FastAPI router for IPFS monitoring endpoints.
- `IPFSMonitoringMiddleware`

**Functions:**
- `create_monitoring_router()`: Create a FastAPI router with IPFS monitoring endpoints.
- `init_ipfs_monitoring()`: Initialize IPFS monitoring for a FastAPI app.

#### `mcp/monitoring/health_check.py`

Health check API for MCP server.

This module provides health check endpoints to monitor the status
of the MCP server and its components.

**Classes:**
- `HealthCheckAPI`: Health check API for the MCP server.

#### `mcp/monitoring/migration_monitor.py`

Migration Monitoring Integration

This module integrates the MCP Migration Controller with the monitoring system,
providing real-time metrics and alerts for migration operations.

**Classes:**
- `MigrationMonitor`: Provides monitoring capabilities for the Migration Controller.

#### `mcp/monitoring/metrics_optimizer.py`

Metrics Optimizer for MCP Server.

This module provides utilities to optimize the MCP metrics collection system,
helping to address high memory usage when tracking many metrics. It provides
tools for analyzing memory usage, upgrading to the optimized metrics collector,
and configuring memory-efficient collection policies.

**Classes:**
- `MetricsMemoryAnalyzer`: Analyzer for metrics collection memory usage.

**Functions:**
- `analyze_metrics_memory_usage()`: Analyze metrics collection memory usage over a period of time.
- `upgrade_to_optimized_metrics()`: Upgrade the default metrics collector to the optimized version.
- `register_optimized_collector_with_fastapi()`: Register optimization endpoints with a FastAPI application.
- `main()`: CLI interface for metrics optimization.

#### `mcp/monitoring/alerts.py`

Alerting System for MCP Server

This module provides an alerting and notification system:
- Configurable alert rules based on metrics
- Multiple notification channels (email, webhook, etc.)
- Alert aggregation and deduplication
- Alert history and tracking

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `AlertSeverity`: Alert severity levels.
- `AlertState`: Alert states.
- `NotificationChannel`: Notification channel types.
- `AlertRule`: Alert rule definition.
- `Alert`: Alert instance.
- `NotificationConfig`: Configuration for a notification channel.
- `AlertManager`: Alert manager for MCP Server.

**Functions:**
- `setup_alert_manager()`: Set up alert manager for MCP server.

#### `mcp/monitoring/health.py`

Health Check System for MCP Server

This module provides health check capabilities for MCP components and backends
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Key features:
- Configurable health checks for all components
- Comprehensive system health monitoring
- Backend connectivity and status checks
- Health check aggregation and reporting
- Integration with the alerting system

**Classes:**
- `HealthStatus`: Health status levels.
- `HealthCheck`: Definition of a health check.
- `HealthCheckResult`: Result of a health check execution.
- `HealthCheckManager`: Manager for health checks.

**Functions:**
- `get_instance()`: Get or create the singleton health check manager instance.

#### `mcp/monitoring/prometheus_exporter.py`

Prometheus Exporter for MCP Server.

This module provides a Prometheus exporter for exposing MCP metrics to Prometheus.

**Classes:**
- `PrometheusExporter`: Prometheus exporter for MCP metrics.
- `DummyMetric`

#### `mcp/monitoring/api.py`

Monitoring API Routes for MCP Server

This module provides FastAPI routes for the enhanced monitoring system
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Features:
- Metrics endpoints (JSON and Prometheus formats)
- Health check API
- Alerting system API
- Monitoring dashboards integration

**Classes:**
- `MonitoringAPIService`: Service class providing monitoring API endpoints.

**Functions:**
- `create_monitoring_api()`: Create the monitoring API service.

#### `mcp/monitoring/optimized_metrics.py`

Optimized Metrics Collector for MCP Server.

This module provides an optimized version of the metrics collector that
addresses high memory usage when tracking many metrics. It extends the
functionality of the standard metrics collector with memory efficiency features.

**Classes:**
- `OptimizedMetricsCollector`: Optimized version of the MetricsCollector with memory usage improvements.

**Functions:**
- `get_optimized_metrics_collector()`: Get or create the default optimized metrics collector.
- `replace_default_collector_with_optimized()`: Replace the default metrics collector with the optimized version.

#### `mcp/monitoring/prometheus.py`

Prometheus Integration for MCP Server

This module provides integration with Prometheus monitoring system:
- Prometheus metrics exposition format
- Push gateway support
- Custom metrics registration
- Helper functions for instrumentation

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `PrometheusExporter`: Export MCP metrics to Prometheus.
- `PrometheusMiddleware`: FastAPI middleware for Prometheus metrics.
- `MetricsMiddleware`

**Functions:**
- `setup_prometheus()`: Set up Prometheus integration for MCP server.

#### `mcp/monitoring/__init__.py`

Monitoring Integration Module

This module provides a unified interface for integrating all monitoring components:
- Metrics collection and management
- Prometheus integration
- Alerting system
- Dashboard configurations
- Health checks and status endpoints

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `MonitoringService`: Central monitoring service that integrates all monitoring components.

**Functions:**
- `setup_monitoring()`: Set up the monitoring system for MCP.

#### `mcp/monitoring/metrics_collector.py`

Metrics Collector for MCP Server.

This module provides a central collector for various metrics throughout the system,
integrating with Prometheus for exporting metrics and providing APIs for components
to report their metrics.

**Classes:**
- `MetricsCollector`: Central collector for MCP metrics.

**Functions:**
- `get_metrics_collector()`: Get or create the default metrics collector.
- `collect_metrics()`: Collect metrics using the default metrics collector.
- `register_collector()`: Register a metrics collector function with the default metrics collector.

#### `mcp/services/comprehensive_service_manager.py`

Comprehensive Service Manager for IPFS Kit MCP Server

This module provides proper service management functionality for the MCP server's
services tab, replacing the incorrect "cars", "docker", "kubectl" services with
actual storage and daemon services that ipfs_kit_py manages.

**Classes:**
- `MockDaemonManager`: Mock daemon manager for testing purposes.
- `ServiceType`: Types of services managed by IPFS Kit.
- `ServiceStatus`: Service status states.
- `ServiceAction`: Available actions for services.
- `ComprehensiveServiceManager`: Manages all services for IPFS Kit including daemons, storage backends, and credentialed services.

#### `mcp/enterprise/encryption.py`

End-to-End Encryption Module for MCP Server

This module provides comprehensive encryption capabilities for the MCP server,
enabling secure storage and transmission of sensitive data across the network.

Key features:
1. End-to-end encryption of data
2. Secure key management
3. Integration with storage backends
4. Compliance audit logging
5. Zero-knowledge architecture options

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `EncryptionAlgorithm`: Supported encryption algorithms.
- `KeyType`: Types of encryption keys.
- `KeyStorageType`: Types of key storage.
- `EncryptionScope`: Scopes for encryption policies.
- `EncryptionKey`: Represents an encryption key.
- `EncryptedData`: Represents encrypted data with metadata.
- `EncryptionPolicy`: Defines an encryption policy for specific data types or scopes.
- `KeyManager`: Manages encryption keys securely.
- `EncryptionManager`: Manages encryption and decryption operations.
- `BackendEncryptionHandler`: Handles encryption for storage backends.

#### `mcp/enterprise/lifecycle.py`

Data Lifecycle Management Module for MCP Server

This module provides comprehensive data lifecycle management capabilities for the MCP server,
enabling policy-based data retention, automated archiving, data classification,
compliance enforcement, and cost optimization strategies.

Key features:
1. Policy-based data retention
2. Automated archiving of infrequently accessed data
3. Data classification based on content type and metadata
4. Compliance enforcement for regulations (GDPR, CCPA, etc.)
5. Cost optimization strategies for storage

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `RetentionPolicy`: Types of retention policies for data.
- `DataClassification`: Classification levels for data.
- `ArchiveStrategy`: Strategies for data archiving.
- `ComplianceRegulation`: Common compliance regulations.
- `CostOptimizationStrategy`: Strategies for cost optimization.
- `RetentionAction`: Actions to take when retention period expires.
- `DataLifecycleState`: Possible states in the data lifecycle.
- `RetentionRule`: Rule for data retention.
- `ClassificationRule`: Rule for data classification.
- `ArchiveRule`: Rule for data archiving.
- `ComplianceRule`: Rule for compliance enforcement.
- `CostOptimizationRule`: Rule for cost optimization.
- `AccessLogEntry`: Entry in the access log.
- `DataLifecycleMetadata`: Metadata for data lifecycle management.
- `LifecycleManager`: Manager for data lifecycle.

#### `mcp/enterprise/integration.py`

Enterprise Features Integration Module for MCP Server.

This module integrates Phase 3 Enterprise Features with the MCP server,
including High Availability Architecture, Advanced Security, and
Data Lifecycle Management components.

**Classes:**
- `EnterpriseFeatures`: Enterprise Features Integration for MCP Server.

#### `mcp/enterprise/data_lifecycle.py`

Data Lifecycle Management Module for MCP Server

This module provides comprehensive data lifecycle management capabilities for the MCP server,
enabling policy-based data retention, archiving, classification, and compliance enforcement.

Key features:
1. Policy-based data retention
2. Automated archiving
3. Data classification and tagging
4. Compliance enforcement
5. Cost optimization strategies

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `RetentionAction`: Actions to take when retention policy is applied.
- `RetentionTrigger`: Events that trigger retention policy evaluation.
- `DataClassification`: Classification levels for data.
- `ComplianceRegime`: Regulatory compliance regimes.
- `ArchiveStorage`: Types of archive storage.
- `StorageTier`: Storage tiers with different cost and performance characteristics.
- `AnalyticsType`: Types of analytics that can be performed on data usage patterns.
- `RetentionPolicy`: Policy defining how long data should be retained and what to do with it.
- `ArchivePolicy`: Policy defining how and where data should be archived.
- `ClassificationRule`: Rule for automatic data classification.
- `CompliancePolicy`: Policy defining compliance requirements for data.
- `CostOptimizationPolicy`: Policy defining cost optimization strategies for data storage.
- `DataLifecycleEvent`: Record of a data lifecycle event for auditing purposes.
- `DataLifecycleManager`: Manager for data lifecycle policies and operations.

#### `mcp/enterprise/zero_trust.py`

Zero-Trust Security Module for MCP Server

This module implements a comprehensive zero-trust security architecture for the MCP server,
providing robust security controls based on the principle of "never trust, always verify".

Key features:
1. Identity-based access control with continuous verification
2. Micro-segmentation of network resources
3. Least privilege access enforcement
4. Continuous monitoring and validation
5. Dynamic policy enforcement

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `AuthenticationMethod`: Authentication methods supported by the zero-trust system.
- `AccessDecision`: Possible access decisions.
- `RiskLevel`: Risk levels for access requests.
- `NetworkSegment`: Network segment types.
- `ResourceType`: Types of resources protected by the zero-trust system.
- `SecurityContext`: Security context for an authentication/authorization request.
- `AccessPolicy`: Policy defining access rules for resources.
- `NetworkPolicy`: Policy defining network access rules.
- `ZeroTrustController`: Controller for zero-trust security architecture.

#### `mcp/enterprise/high_availability.py`

High Availability Architecture Module for MCP Server

This module provides the foundation for high availability deployments of the MCP server,
enabling resilient, fault-tolerant operations across multiple regions and availability zones.

Key features:
1. Multi-region deployment configuration
2. Automatic failover mechanisms
3. Load balancing between multiple MCP instances
4. State replication and consistency management
5. Health monitoring and auto-recovery

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `NodeRole`: Possible roles for a node in the HA cluster.
- `NodeStatus`: Possible statuses for a node in the HA cluster.
- `RegionStatus`: Possible statuses for a region in the HA deployment.
- `FailoverStrategy`: Available failover strategies.
- `ReplicationMode`: Available replication modes.
- `ConsistencyLevel`: Available consistency levels for operations.
- `NodeConfig`: Configuration for a node in the HA cluster.
- `NodeState`: Runtime state of a node in the HA cluster.
- `RegionConfig`: Configuration for a region in the HA deployment.
- `HAConfig`: High Availability configuration.
- `HAStateManager`: Manages the state of a high availability cluster.
- `HACluster`: High Availability Cluster management.
- `LoadBalancer`: Load balancer for distributing requests across nodes.

#### `mcp/server/__init__.py`

Bridge module for server package.
This file was created by the import_fixer.py script.

#### `mcp/storage_manager/storage_base_bridge.py`

Bridge module for storage manager base classes.

This module provides direct access to storage base classes without circular imports.

**Classes:**
- `BackendStorage`: Abstract base class for all storage backends.

#### `mcp/storage_manager/migration.py`

Data Migration Module for MCP Storage Manager.

This module provides functionality for migrating data between different storage backends
with advanced features like validation, scheduling, and policy-based migration.

**Classes:**
- `MigrationType`: Types of migration operations.
- `ValidationLevel`: Levels of validation for migrated data.
- `MigrationStatus`: Possible statuses for migration operations.
- `MigrationPriority`: Priority levels for migration tasks.
- `MigrationResult`: Result of a migration operation.
- `MigrationTask`: Task for migrating data between backends.
- `MigrationManager`: Manager for data migration between backends.

**Functions:**
- `calculate_content_hash()`: Calculate SHA-256 hash of content.
- `create_migration_manager()`: Create a migration manager.

#### `mcp/storage_manager/monitoring.py`

Monitoring system for storage backends.

This module implements the monitoring system for tracking health,
performance, and reliability of storage backends.

**Classes:**
- `BackendStatus`: Status of a storage backend.
- `OperationType`: Types of operations for performance tracking.
- `MonitoringSystem`: Monitoring system for storage backends.

#### `mcp/storage_manager/backend_manager.py`

Simple Backend Manager for MCP Server.

This module provides a minimal backend manager that can work with the existing
storage backends and provides the interface expected by the MCP server.

**Classes:**
- `BackendManager`: Simple backend manager that coordinates storage backends.
- `LocalFileBackend`: Local file backend that manages files in ~/.ipfs_kit/uploads/

#### `mcp/storage_manager/storage_types.py`

Storage types for the unified storage manager.

This module defines the core types used in the unified storage system,
including backend types and content references.

**Classes:**
- `StorageBackendType`: Enum for supported storage backend types.
- `ContentReference`: Reference to content across multiple storage backends.

#### `mcp/storage_manager/router_integration.py`

Storage Manager Router Integration

This module integrates the advanced content router with the UnifiedStorageManager
to enable intelligent content-aware backend selection.

**Classes:**
- `RouterIntegration`: Integration between the storage manager and content router.

**Functions:**
- `create_router_integration()`: Create a router integration instance.
- `patch_storage_manager()`: Patch the UnifiedStorageManager to use the router integration.

#### `mcp/storage_manager/backend_base.py`

Base class definition for storage backends.

This module defines the abstract interface that all storage backends must implement.

**Classes:**
- `BackendStorage`: Abstract base class for storage backends.

#### `mcp/storage_manager/manager.py`

Unified Storage Manager implementation.

This module implements the UnifiedStorageManager class that coordinates
operations across all storage backends and provides a unified interface
for storage operations regardless of the underlying technology.

**Classes:**
- `UnifiedStorageManager`: Unified Storage Manager for coordinating storage operations across backends.

#### `mcp/fs/fs_ipfs_bridge.py`

Filesystem IPFS Bridge Module

This module provides integration between the virtual filesystem and IPFS operations.
It ensures that all IPFS operations are properly tracked in the filesystem journal
and that the virtual filesystem stays in sync with the actual IPFS content.

**Classes:**
- `IPFSFSBridge`: Bridge between IPFS and the virtual filesystem.

**Functions:**
- `create_fs_ipfs_bridge()`: Create and integrate an IPFS-FS bridge with an MCP server.

#### `mcp/fs/fs_journal.py`

Filesystem Journal Module

This module provides virtual filesystem and journaling capabilities for IPFS Kit.
It tracks all filesystem operations and provides a virtual filesystem layer that
can be integrated with IPFS operations.

**Classes:**
- `FSOperationType`: Types of filesystem operations that can be tracked.
- `FSOperation`: Represents a filesystem operation for journaling purposes.
- `FSJournal`: A journal that records filesystem operations for tracking and auditing.
- `VirtualFile`: Represents a file in the virtual filesystem.
- `VirtualDirectory`: Represents a directory in the virtual filesystem.
- `VirtualFS`: A virtual filesystem that can be used to track and manipulate files
- `FSController`: Controller for virtual filesystem operations.

**Functions:**
- `integrate_fs_with_mcp()`: Integrate filesystem journal functionality with an MCP server.

#### `mcp/routing/adaptive_optimizer.py`

Adaptive Optimizer for MCP Routing

This module provides an adaptive optimization system that combines multiple
routing factors to make intelligent routing decisions for content across
different storage backends.

Key features:
1. Multi-factor optimization based on content, network, geography, and cost
2. Adaptive weights that learn from past routing outcomes
3. Content-aware backend selection
4. Performance and cost analytics
5. Comprehensive routing insights

**Classes:**
- `OptimizationFactor`: Factors that influence routing optimization decisions.
- `OptimizationWeights`: Weights for different optimization factors.
- `RouteOptimizationResult`: Result of a route optimization decision.
- `LearningSystem`: Learning system that adjusts optimization weights based on outcomes.
- `AdaptiveOptimizer`: Adaptive optimizer that combines multiple routing factors to make

**Functions:**
- `create_adaptive_optimizer()`: Create an adaptive optimizer instance.

#### `mcp/routing/observability.py`

Observability module for the MCP Optimized Data Routing system.

This module provides metrics, logging, and tracing capabilities to monitor 
the performance and behavior of the routing optimization system.

**Classes:**
- `MetricType`: Types of metrics collected by the observability system.
- `RoutingMetrics`: Collects and exposes metrics for the routing system.
- `RoutingTracer`: Traces routing decisions for debugging and analysis.
- `RoutingObservability`: Main observability class for the routing system.

#### `mcp/routing/integration.py`

MCP Server Integration for Optimized Data Routing.

This module provides the integration between the MCP server and the
optimized data routing system, allowing intelligent backend selection
for storage operations.

**Classes:**
- `MCPRoutingIntegration`: Integrates the optimized routing system with the MCP server.

**Functions:**
- `initialize_mcp_routing()`: Initialize the MCP routing integration.
- `get_mcp_routing()`: Get the global MCP routing integration instance.
- `select_backend()`: Select the optimal backend for an operation.
- `example_usage()`: Example usage of the MCP routing integration.

#### `mcp/routing/bandwidth_aware_router.py`

Bandwidth and Latency Analysis Module for Optimized Data Routing

This module analyzes and tracks bandwidth and latency metrics for storage backends:
- Real-time bandwidth measurement for backend selection
- Latency tracking and prediction
- Connection quality monitoring
- Adaptive routing based on network conditions
- Performance history and trends analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `NetworkMetricType`: Types of network metrics tracked.
- `NetworkQualityLevel`: Network quality classification.
- `MetricSample`: A single sample of a network metric.
- `MetricTimeSeries`: Time series of network metric samples.
- `BackendNetworkMetrics`: Network metrics for a specific backend.
- `NetworkAnalyzer`: Analyzes network metrics for storage backends.

**Functions:**
- `percentile()`: Calculate percentile of a list of values.
- `create_network_analyzer()`: Create a network analyzer.

#### `mcp/routing/cost_optimizer.py`

Cost-Based Routing Module for MCP Server

This module enhances the Optimized Data Routing feature with cost optimization:
- Cost prediction and modeling for different backends
- Budget-aware storage allocation
- Cost-optimized backend selection
- Usage-based pricing analysis
- Cost/performance trade-off optimization

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `CostModelType`: Types of cost models for storage backends.
- `CostComponent`: Cost components for storage backends.
- `StorageCost`: Storage cost for a specific backend.
- `UsageEstimate`: Estimated usage for cost calculation.
- `CostEstimate`: Cost estimate for a specific backend.
- `CostOptimizer`: Cost optimization for storage backend selection.

**Functions:**
- `get_cost_optimizer()`: Get or create the default cost optimizer instance.

#### `mcp/routing/optimized_router.py`

Optimized Data Routing Module for MCP Server

This module provides intelligent routing of data operations across different storage backends.
It implements content-aware backend selection, cost-based routing algorithms, geographic
optimization, and bandwidth/latency-based routing decisions.

Key features:
1. Content-aware backend selection based on file type, size, and access patterns
2. Cost-based routing algorithms to optimize for storage and retrieval costs
3. Geographic optimization to reduce latency and improve compliance
4. Bandwidth and latency analysis for adaptive routing decisions
5. Performance metrics collection and analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `ContentType`: Enum for content types with different routing strategies.
- `RoutingStrategy`: Enum for data routing strategies.
- `StorageClass`: Enum for storage classes with different cost and performance profiles.
- `GeographicRegion`: Enum for geographic regions for content placement.
- `ComplianceType`: Enum for compliance types affecting routing decisions.
- `BackendMetrics`: Performance and cost metrics for a storage backend.
- `RoutingPolicy`: Policy configuration for data routing decisions.
- `RoutingDecision`: Result of a routing decision for content placement or retrieval.
- `RouterGeolocation`: Helper class for geographic lookups and distance calculations.
- `ConnectivityAnalyzer`: Analyzes network connectivity to different backends to optimize routing.
- `ContentAnalyzer`: Analyzes content to determine optimal routing.
- `RouterMetricsCollector`: Collects and analyzes metrics for routing decisions.
- `OptimizedRouter`: Core router for optimizing data placement and retrieval across backends.

#### `mcp/routing/simple_router.py`

Simple Routing Implementation for MCP Server

This is a simplified version of the Optimized Router that is fully functional.
It implements the core routing functionality with a focus on simplicity and reliability.

Key features:
1. Content-aware backend selection based on file type and size
2. Cost-based and performance-based routing strategies
3. Support for routing policies with backend preferences
4. Metrics collection for routing decisions

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `ContentType`: Enum for content types with different routing strategies.
- `RoutingStrategy`: Enum for data routing strategies.
- `BackendMetrics`: Performance and cost metrics for a storage backend.
- `RoutingPolicy`: Policy configuration for data routing decisions.
- `RoutingDecision`: Result of a routing decision for content placement or retrieval.
- `ContentAnalyzer`: Analyzes content to determine optimal routing.
- `RouterMetricsCollector`: Collects and analyzes metrics for routing decisions.
- `SimpleRouter`: Simple router for optimizing data placement and retrieval across backends.

#### `mcp/routing/geographic_router.py`

Geographic Optimization Module for MCP Server

This module enhances the Optimized Data Routing feature with geographic awareness:
- Region-based routing decisions
- Latency optimization based on geographic proximity
- Multi-region replication recommendations
- Network topology awareness
- Geographic data distribution analytics

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `GeoCoordinates`: Geographic coordinates (latitude/longitude).
- `GeoRegion`: Geographic region information.
- `GeographicRouter`: Geographic routing optimization for the MCP server.

**Functions:**
- `get_geographic_router()`: Get or create the default geographic router instance.

#### `mcp/routing/performance_optimization.py`

Routing Performance Optimization

This module provides performance optimizations for the routing system, including:
- Decision caching
- Content signature calculation
- Batch processing
- Memory optimization
- Connection pooling

**Classes:**
- `RoutingDecisionCache`: Cache for routing decisions to avoid recomputation for similar content.
- `ContentSignatureCalculator`: Efficient content signature calculator with caching.
- `BatchProcessor`: Batch processor for routing operations.
- `ConnectionPool`: Connection pool for backend connections.
- `RoutingPerformanceMetrics`: Performance metrics for the routing system.

**Functions:**
- `optimize_routing_function()`: Decorator to optimize a routing function with caching.
- `measure_routing_performance()`: Decorator to measure routing performance.

#### `mcp/routing/data_router.py`

Optimized Data Routing Module

This module implements intelligent routing of data between storage backends:
- Content-aware backend selection based on data characteristics
- Cost-based routing algorithms to optimize for price vs performance
- Geographic routing for edge-optimized content delivery
- Bandwidth and latency analysis for network-aware decisions

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `RoutingStrategy`: Strategies for routing data between backends.
- `RoutingPriority`: Priority levels for routing decisions.
- `ContentCategory`: Categories for different types of content.
- `BackendMetrics`: Performance and cost metrics for a storage backend.
- `RoutingRule`: Rule for routing content to specific backends.
- `ContentAnalyzer`: Analyzes content to determine its characteristics.
- `GeographicRouter`: Routes content based on geographic location.
- `CostOptimizer`: Optimizes content routing based on cost.
- `PerformanceOptimizer`: Optimizes content routing based on performance.
- `DataRouter`: Main data routing system that selects optimal storage backends.

**Functions:**
- `validate_routing_rule()`: Validate a routing rule configuration.
- `create_data_router()`: Create a data router instance.

#### `mcp/routing/cost_router.py`

Cost-Based Routing Module for Optimized Data Routing

This module enhances the data routing system with cost optimization capabilities:
- Cost-based routing algorithms to optimize for price vs performance
- Storage cost modeling for different backend providers
- Retrieval cost estimation and optimization
- Budget-aware routing decisions
- Cost prediction and analysis tools

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `CostOptimizationStrategy`: Strategy for cost optimization.
- `StorageCostModel`: Cost model for a storage backend.
- `CostEstimate`: Cost estimate for a storage operation.
- `BudgetConstraint`: Budget constraint for routing decisions.
- `CostRouter`: Router that optimizes backend selection based on cost factors.

**Functions:**
- `create_cost_router()`: Create a cost router.

#### `mcp/routing/router.py`

Core Router Implementation for Optimized Data Routing.

This module provides the main DataRouter class and supporting classes for
making intelligent routing decisions for data across different storage backends.

**Classes:**
- `BackendType`: Types of storage backends.
- `ContentType`: Types of content for routing decisions.
- `OperationType`: Types of operations for routing decisions.
- `RouteMetrics`: Metrics used for routing decisions.
- `RoutingContext`: Context for routing decisions.
- `RoutingDecision`: Result of a routing decision.
- `RoutingStrategy`: Abstract base class for routing strategies.
- `DataRouter`: Main router class for making intelligent routing decisions.

#### `mcp/routing/enhanced_routing_manager.py`

Enhanced Routing Manager with Performance Optimizations

This module provides an enhanced version of the routing manager that incorporates
performance optimizations for improved efficiency, lower latency, and reduced
resource consumption.

**Classes:**
- `EnhancedRoutingManager`: Enhanced routing manager with performance optimizations.

**Functions:**
- `get_enhanced_routing_manager()`: Get the singleton enhanced routing manager instance.

#### `mcp/routing/routing_manager.py`

Optimized Data Routing Manager for MCP

This module serves as the main entry point for the optimized data routing system,
integrating all components and providing a clean interface for the MCP server.

It implements the "Optimized Data Routing" component from the MCP roadmap:
- Content-aware backend selection
- Cost-based routing algorithms
- Geographic optimization
- Bandwidth and latency analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `RoutingManagerSettings`: Settings for the Routing Manager.
- `MetricsCollector`: Collects and aggregates metrics for routing optimization.
- `RoutingManager`: Central manager for the optimized data routing system.

**Functions:**
- `get_routing_manager()`: Get the singleton routing manager instance.
- `register_routing_manager()`: Register the routing manager with a FastAPI app.

#### `mcp/routing/__init__.py`

Routing package for MCP Server.

This package provides optimized routing functionality across storage backends.

#### `mcp/routing/router_api.py`

Enhanced Router API Module for MCP

This module provides enhanced API endpoints for the optimized data routing system.
It integrates the adaptive optimizer to provide intelligent routing decisions based on:
- Network conditions (bandwidth, latency, reliability)
- Content characteristics (size, type, access patterns)
- Cost considerations (storage, retrieval, bandwidth)
- Geographic awareness (client location, region optimization)

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `ClientInfo`: Client information for routing decisions.
- `RoutingRequest`: Request for routing optimization.
- `RoutingResponse`: Response for routing optimization.
- `MetricsUpdateRequest`: Request to update backend metrics.
- `NetworkMetricsResponse`: Response with network metrics.
- `InsightsResponse`: Response with routing insights.

#### `mcp/auth/audit.py`

Audit logging module for the MCP auth system.

This module provides utilities for audit logging operations in the auth system,
tracking authentication and authorization events for security purposes.

**Classes:**
- `AuditEventType`: Enum defining the types of audit events that can be logged.
- `AuditLogEntry`: Class representing a single audit log entry.
- `AuditLogger`: Advanced audit logging system for tracking authentication and authorization events.

**Functions:**
- `get_audit_logger()`: Get the audit logger instance.
- `log_auth_event()`: Log an authentication or authorization event.
- `configure_audit_logger()`: Configure the audit logger with specific settings.
- `get_instance()`: Get a singleton instance of the audit logger.

#### `mcp/auth/rbac_router.py`

RBAC API Router for MCP Server

This module provides API endpoints for the Role-Based Access Control system:
- Role management
- Permission management
- Authorization checks
- Backend-specific authorization

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `PermissionInfo`: Basic permission information.
- `PermissionDetail`: Detailed permission information.
- `RoleInfo`: Basic role information.
- `RoleDetail`: Detailed role information.
- `PermissionCreateRequest`: Request to create a new permission.
- `PermissionUpdateRequest`: Request to update a permission.
- `RoleCreateRequest`: Request to create a new role.
- `RoleUpdateRequest`: Request to update a role.
- `AuthorizationCheckRequest`: Request to check authorization for a specific action.
- `PermissionCheckRequest`: Request to check if user has a specific permission.
- `BackendPermissionsResult`: Result of a backend permissions check.

**Functions:**
- `create_rbac_api_router()`: Create an API router for RBAC functions.

#### `mcp/auth/enhanced_integration.py`

Advanced Authentication & Authorization Integration Module

This module integrates all the advanced authentication and authorization components:
- Role-Based Access Control (RBAC)
- Backend-specific authorization
- API key management
- OAuth integration
- Comprehensive audit logging

Part of the MCP Roadmap Phase 1: Advanced Authentication & Authorization.

**Classes:**
- `AdvancedAuthSystem`: Advanced Authentication & Authorization System for the MCP server.

**Functions:**
- `get_auth_system()`: Get the singleton advanced auth system instance.
- `initialize_auth_system()`: Initialize the advanced authentication system.

#### `mcp/auth/auth_service_extension.py`

Authentication Service Extensions for API Key Caching

This module adds API key caching capabilities to the authentication service,
addressing the "API key validation could benefit from caching improvements"
issue mentioned in the MCP roadmap.

**Classes:**
- `AuthServiceApiKeyExtension`: Extension for authentication service to improve API key handling.

**Functions:**
- `extend_auth_service()`: Extend an existing authentication service with API key caching capabilities.

#### `mcp/auth/mcp_auth_integration.py`

MCP Authentication & Authorization Integration Module

This module provides a simple API for integrating the Advanced Authentication & Authorization
system with the MCP server. It handles setting up all components of the auth system:

1. User authentication (username/password, tokens)
2. Role-based access control (RBAC)
3. API key management
4. OAuth integration
5. Backend-specific authorization
6. Audit logging

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `MCPAuthIntegrator`: Helper class for integrating Advanced Authentication & Authorization with MCP server.

**Functions:**
- `get_mcp_auth()`: Get the MCP auth integrator instance.

#### `mcp/auth/api_key_middleware.py`

API Key Authentication Middleware with Caching

This module provides FastAPI middleware for efficient API key authentication
using the optimized caching system. It addresses the performance issue
mentioned in the MCP roadmap regarding API key validation caching.

**Classes:**
- `ApiKeyMiddleware`: FastAPI middleware for API key authentication with caching support.
- `ApiKeyStats`: API key cache statistics model.
- `ApiKeyAdminEndpoints`: Admin endpoints for API key cache management.

#### `mcp/auth/backend_authorization_integration.py`

Backend Authorization Integration

This module provides a comprehensive backend authorization system that integrates with RBAC,
allowing fine-grained control over which users and API keys can access different storage backends.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `BackendPermission`: Permission configuration for a specific backend.
- `BackendAuthorizationManager`: Backend Authorization Manager for MCP server.

**Functions:**
- `get_backend_auth_manager()`: Get the singleton backend authorization manager instance.

#### `mcp/auth/api_key_enhanced.py`

Enhanced API Key Management System

This module provides a comprehensive API key management system for the MCP server.
It supports features such as:
- Scoped API keys with specific permissions
- Auto-expiring keys
- Per-backend authorization
- Rate limiting
- Usage tracking and auditing

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements - "Advanced Authentication & Authorization".

**Classes:**
- `APIKey`: API key class with enhanced features.
- `APIKeyStore`: Storage backend for API keys.
- `RateLimiter`: Rate limiter for API keys.
- `EnhancedAPIKeyManager`: Enhanced API key manager with advanced features.

#### `mcp/auth/enhanced_api_key_cache.py`

Enhanced API Key Cache for MCP Server.

This module provides an improved caching mechanism for API keys with:
1. Multi-level cache hierarchy (memory, shared memory, distributed)
2. Intelligent cache eviction policies based on usage patterns
3. Cache priming/warming for frequently used keys
4. Advanced metrics and telemetry
5. Improved performance under high concurrency
6. Enhanced thread and process safety
7. Bloom filter for ultra-fast negative lookups (NEW)
8. Bulk prefetching mechanism (NEW)
9. Advanced cache analytics (NEW)

**Classes:**
- `ScalableBloomFilter`

#### `mcp/auth/backend_middleware.py`

Backend Authorization Middleware

This middleware enforces permissions for access to different storage backends,
integrating with the backend authorization system to control access based on
user roles and API keys.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `BackendAuthorizationMiddleware`: Middleware for enforcing backend authorization policies.

#### `mcp/auth/integration.py`

OAuth Integration Module for MCP Server.

This module integrates the enhanced OAuth security with the MCP authentication service.
It provides a cleaner API for OAuth operations and implements security best practices.

**Classes:**
- `OAuthIntegrationManager`: Manages OAuth provider integration and authentication flows.

#### `mcp/auth/audit_logging.py`

Audit Logging for IPFS Kit MCP Server.

This module provides comprehensive audit logging capabilities for tracking
authentication, authorization, and other security-related events in the system.
Features include:
- Structured logging of security events
- Event categorization
- User action tracking
- Compliance-oriented logging format

**Classes:**
- `AuditSeverity`: Severity levels for audit events.
- `AuditEventType`: Types of audit events.
- `AuditEvent`: Represents an audit event in the system.
- `AuditLogger`: Handles audit logging for the system.

#### `mcp/auth/integration_advanced.py`

Authentication & Authorization Integration Module

This module provides a centralized integration point for all advanced authentication
and authorization components described in the MCP roadmap.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Functions:**
- `setup_auth_routes()`: Set up all authentication and authorization routes.
- `create_auth_integration()`: Create and return an integration function for the MCP server.

#### `mcp/auth/enhanced_backend_middleware.py`

Backend Authorization Middleware

This module implements middleware for enforcing per-backend authorization policies.
It intercepts requests to storage backends and verifies that the authenticated user
has the required permissions for the requested operation.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements - "Advanced Authentication & Authorization".

**Classes:**
- `BackendAuthorizationMiddleware`: Middleware for enforcing per-backend authorization policies.

**Functions:**
- `check_backend_permission()`: Check if current user has permission for a backend operation.
- `require_backend_permission()`: Dependency to require backend permission.

#### `mcp/auth/oauth_persistence.py`

OAuth Persistence Extensions for MCP Server

This module extends the persistence system to support OAuth functionality:
- OAuth provider configuration storage
- User OAuth connection management 
- Token and state management

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `OAuthStore`: Persistent storage for OAuth-related data.

**Functions:**
- `get_oauth_store()`: Get the OAuth store singleton instance.
- `extend_persistence_manager()`: Extend the persistence manager with OAuth methods.

#### `mcp/auth/rbac_enhanced.py`

Enhanced Role-Based Access Control (RBAC) for IPFS Kit MCP Server.

This module provides comprehensive RBAC capabilities for the MCP server, including:
- Fine-grained permission management
- Per-backend authorization
- Role hierarchy
- Permission inheritance
- Dynamic permission checks
- Integration with authentication mechanisms

**Classes:**
- `ResourceType`: Enum representing different resource types in the system.
- `Permission`: Represents a permission in the system.
- `Action`: Standard actions that can be performed on resources.
- `Role`: Represents a role with a set of permissions.
- `RoleManager`: Manages roles and their permissions.
- `BackendAuthorization`: Handles per-backend authorization for storage backends.
- `ApiKey`: Represents an API key for authentication.
- `ApiKeyManager`: Manages API keys for authentication.
- `AuthenticationMethod`: Supported authentication methods.
- `User`: Represents a user in the system.
- `AuthorizationResult`: Represents the result of an authorization check.
- `RequestAuthenticator`: Authenticates requests and extracts user information.
- `RBACService`: Main service class for Role-Based Access Control.
- `MockRequest`

**Functions:**
- `get_backend_permission()`: Generate a permission for a specific backend and action.
- `require_permission()`: Decorator to require a permission for a function.
- `example_usage()`: Example usage of the RBAC system.

#### `mcp/auth/oauth_integration_enhanced.py`

Enhanced OAuth Integration Module

This module provides comprehensive OAuth 2.0 integration for the MCP server.
It supports multiple OAuth providers (GitHub, Google, etc.) and handles the
authentication flow, token exchange, and user profile retrieval.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements - "Advanced Authentication & Authorization".

**Classes:**
- `OAuthEnhancedManager`: Enhanced OAuth Manager for handling multiple providers.

#### `mcp/auth/oauth_router.py`

OAuth API Router for MCP Server

This module provides REST API endpoints for OAuth operations:
- Provider management
- OAuth login flows
- User account connections

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `OAuthProviderInfo`: OAuth provider information.
- `OAuthProviderConfig`: OAuth provider configuration.
- `OAuthConnectionInfo`: OAuth connection information.
- `OAuthAuthUrlResponse`: Response model for OAuth authorization URL.
- `OAuthCallbackResponse`: Response model for OAuth callback.

#### `mcp/auth/service.py`

Authentication Service for MCP server.

This module implements the core authentication functionality
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `AuthenticationService`: Service providing authentication and user management functionality.

**Functions:**
- `get_instance()`: Get the singleton instance of the authentication service.

#### `mcp/auth/auth_middleware.py`

Authentication and Authorization Middleware for MCP server.

This middleware integrates the RBAC, backend authorization, and audit logging systems
with FastAPI to provide comprehensive authentication and authorization for MCP API requests.

Features:
- Authentication middleware for JWT, API key, and OAuth token validation
- Authorization middleware for RBAC and backend-specific permissions
- Automatic audit logging of all authentication and authorization events
- Configuration options for different authorization levels

**Classes:**
- `AuthLevel`: Authorization levels for API endpoints.
- `AuthMiddleware`: Middleware for authentication and authorization in MCP server.

**Functions:**
- `require_permission()`: FastAPI dependency factory for requiring a specific permission.
- `require_backend_access()`: FastAPI dependency factory for requiring backend access.

#### `mcp/auth/integrate_auth.py`

Integrate Authentication & Authorization with MCP Server.

This script adds the advanced authentication and authorization middleware
to the MCP server as specified in the MCP roadmap for Phase 1 (Q3 2025).

Features added:
- Authentication middleware for JWT, API key, and session validation
- Role-based access control (RBAC) for API endpoints
- Per-backend authorization checks
- Comprehensive audit logging

#### `mcp/auth/middleware.py`

Authentication and Authorization middleware for MCP server.

This module provides FastAPI middleware for implementing authentication
and authorization as specified in the MCP roadmap.

**Classes:**
- `AuthMiddleware`: Middleware for handling authentication and authorization.

**Functions:**
- `get_current_user()`: FastAPI dependency to get the current authenticated user.
- `get_current_user_optional()`: FastAPI dependency to get the current user if authenticated.
- `require_permission()`: FastAPI dependency to require a specific permission.
- `require_role()`: FastAPI dependency to require a specific role.
- `get_auth_context()`: FastAPI dependency to get the complete auth context.

#### `mcp/auth/auth_integration.py`

Authentication & Authorization Integration Module

This module provides comprehensive integration of all authentication and authorization
components with the MCP server. It serves as the main entry point for the auth system.

Features:
- Complete RBAC implementation
- Per-backend authorization
- API key management
- OAuth integration
- Comprehensive audit logging

This module satisfies the requirements outlined in the MCP Server Development Roadmap
under "Advanced Authentication & Authorization" (Phase 1, Q3 2025).

**Classes:**
- `AuthSystem`: Main authentication system integration class.

**Functions:**
- `get_auth_system()`: Get the auth system instance.
- `audit_login_attempt()`: Log a login attempt.
- `audit_permission_check()`: Log a permission check.
- `audit_backend_access()`: Log a backend access attempt.
- `audit_user_change()`: Log a user account change.
- `audit_system_event()`: Log a system event.
- `audit_data_event()`: Log a data operation event.

#### `mcp/auth/oauth_enhanced_security.py`

OAuth Enhanced Security Module for MCP Server

This module provides additional security hardening measures for the OAuth system:

1. PKCE (Proof Key for Code Exchange) - Protects authorization code flow from code interception
2. Token Binding - Binds tokens to specific client fingerprints to prevent token theft
3. Advanced Threat Protection - Detects and prevents common OAuth attack patterns
4. Certificate Chain Validation - Ensures connections to OAuth providers are secure
5. Dynamic Security Policy - Adjusts security requirements based on risk assessment

These enhancements address the OAuth security hardening item identified in the MCP roadmap.

**Classes:**
- `PKCEManager`: PKCE (Proof Key for Code Exchange) implementation for OAuth 2.0 authorization code flow.
- `TokenBindingManager`: Token binding implementation that binds tokens to specific clients.
- `CertificateValidator`: Enhanced certificate validation for OAuth provider connections.
- `OAuthThreatDetector`: Advanced OAuth threat detection and protection.
- `DynamicSecurityPolicy`: Dynamic security policy manager for OAuth operations.
- `SecureOAuthManager`: Enhanced OAuth integration manager with security hardening.

#### `mcp/auth/audit_extensions.py`

Audit Extensions for MCP Server

This module extends the basic audit logging functionality with advanced features:
- Log event categorization and filtering
- Log export and retention policies
- Security alerting integration
- Log integrity verification

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `AuditExtensions`: Extensions to the core AuditLogger for enhanced security monitoring.

**Functions:**
- `get_audit_extensions()`: Get the singleton audit extensions instance.
- `extend_audit_logger()`: Extend the audit logger with advanced features.

#### `mcp/auth/api_key_cache.py`

API Key Cache Module for MCP Server Authentication

This module implements an efficient caching mechanism for API keys
to reduce database load and improve response times for API-based authentication.

Features:
- In-memory LRU cache for fast validation
- Optional distributed cache using Redis
- Automatic expiration and TTL management
- Thread-safe implementation
- Cache invalidation hooks

**Classes:**
- `ApiKeyCache`: Memory-efficient cache for API key validation.
- `ApiKeyValidator`: High-performance API key validator with caching.

**Functions:**
- `create_redis_client()`: Create a Redis client if configured.

#### `mcp/auth/patch_mcp_server.py`

MCP Server Integration Patch for Advanced Authentication

This patch updates the MCP server to fully integrate the advanced authentication
and authorization components, including OAuth, API key management, and enhanced audit logging.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Functions:**
- `patch_mcp_server()`: Patch the MCP server with advanced authentication and authorization components.
- `check_auth_configuration()`: Check if advanced authentication configuration is present.

#### `mcp/auth/api_endpoints.py`

Authentication and Authorization API Endpoints for IPFS Kit MCP Server.

This module provides API handlers for auth-related operations such as:
- User management
- Role management
- Permission management
- API key management
- OAuth integration

**Classes:**
- `AuthHandler`: Handles authentication and authorization API endpoints.

**Functions:**
- `register_auth_endpoints()`: Register auth endpoints with a web framework.

#### `mcp/auth/oauth_integration.py`

OAuth Integration for IPFS Kit MCP Server.

This module provides OAuth 2.0 integration for authentication, allowing users to
authenticate using various OAuth providers (Google, GitHub, etc.).

**Classes:**
- `OAuthProvider`: Supported OAuth providers.
- `OAuthConfig`: Configuration for an OAuth provider.
- `OAuthToken`: OAuth token information.
- `OAuthUserInfo`: User information from an OAuth provider.
- `OAuthStateManager`: Manages OAuth state for CSRF protection.
- `OAuthManager`: Manages OAuth integrations.
- `OAuthUserManager`: Manages users authenticated through OAuth.

**Functions:**
- `example_oauth_flow()`: Example of the OAuth flow.

#### `mcp/auth/server_integration.py`

MCP Server Authentication Integration

This module provides integration between the authentication/authorization system
and the MCP server. It adds middleware and request handlers to enforce access
control across the server's API endpoints.

**Classes:**
- `AuthMiddleware`: Authentication and authorization middleware for the MCP server.
- `AuthorizationHandler`: Handler for enforcing authorization on MCP server endpoints.
- `MCPAuthIntegration`: Provides integration between the MCP server and authentication system.
- `MockMCPServer`

**Functions:**
- `example_usage()`: Example of integrating authentication with the MCP server.

#### `mcp/auth/api_key_cache_integration.py`

API Key Cache Integration for MCP Server.

This module provides integration between the enhanced API key cache and
the MCP server's authentication system. It implements the high-performance
API key validation improvements mentioned in the MCP roadmap.

**Classes:**
- `ApiKeyCacheService`: Service for high-performance API key validation with caching.

**Functions:**
- `require_api_key()`: Decorator for API key validation with caching.
- `get_api_key_cache_service()`: Get or create a shared API key cache service.
- `create_api_key_validation_middleware()`: Create FastAPI middleware for API key validation.
- `patch_auth_service()`: Patch the authentication service to use the enhanced API key cache.

#### `mcp/auth/apikey_router.py`

**Classes:**
- `APIKeyRouter`

#### `mcp/auth/integrate_auth_with_mcp.py`

MCP Authentication & Authorization Integration Script

This script helps integrate the Advanced Authentication & Authorization system
with the main MCP server. It creates a backup of the original server file and
applies the necessary changes to enable auth functionality.

Usage:
    python integrate_auth_with_mcp.py [--backup] [--server-path PATH]

**Functions:**
- `create_backup()`: Create a backup of the original server file.
- `modify_server_file()`: Modify the server file to integrate the auth system.
- `main()`: Main function.

#### `mcp/auth/auth_system_integration.py`

Advanced Authentication & Authorization System Integration

This module provides a comprehensive integration of all authentication and
authorization components for the MCP server, fulfilling the requirements in the
MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

Features:
- Role-based access control
- Per-backend authorization
- API key management
- OAuth integration
- Comprehensive audit logging

**Classes:**
- `AuthSystem`: Comprehensive authentication and authorization system for MCP.

**Functions:**
- `get_auth_system()`: Get the singleton auth system instance.

#### `mcp/auth/persistence.py`

Persistence stores for authentication and authorization data.

This module provides persistent storage for users, roles, permissions,
API keys, and sessions as part of the Advanced Authentication & Authorization
system specified in the MCP roadmap.

**Classes:**
- `BaseStore`: Base class for all persistence stores.
- `UserStore`: Store for user data.
- `RoleStore`: Store for role data.
- `PermissionStore`: Store for permission data.
- `ApiKeyStore`: Store for API key data.
- `SessionStore`: Store for session data.

#### `mcp/auth/verify_auth_system.py`

Authentication & Authorization Verification Script

This script tests the core components of the Advanced Authentication & Authorization system
to verify proper functionality and integration with the MCP server.

Usage:
    python verify_auth_system.py [--url URL] [--output FILE] [--debug]

**Classes:**
- `AuthVerifier`: Authentication system verification tool.

#### `mcp/auth/api_key_cache_router.py`

API Key Cache Management Router

This module provides API endpoints for managing the API key cache,
allowing administrators to view cache statistics, clear the cache,
and invalidate specific cache entries.

**Functions:**
- `create_api_key_cache_router()`: Create a router for API key cache management.

#### `mcp/auth/backend_authorization.py`

Backend Authorization module for MCP server.

This module implements per-backend authorization capabilities
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Key features:
- Role-based access control for backends
- Per-backend authorization policies
- Fine-grained permission checking for storage operations
- Integration with audit logging system

**Classes:**
- `Operation`: Storage operation types.
- `BackendAuthorizationManager`: Manager for backend-specific authorization rules.

**Functions:**
- `get_instance()`: Get or create the singleton backend authorization manager instance.

#### `mcp/auth/router.py`

Authentication API Routes

Implements FastAPI routes for authentication and authorization:
- User management endpoints
- Login and token endpoints
- API key management
- Permission validation
- OAuth integration

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `AuthMiddleware`

**Functions:**
- `register_auth_middleware()`: Register authentication middleware with the FastAPI app.

#### `mcp/auth/config.py`

Advanced Authentication & Authorization Configuration

This module provides configuration helpers for the advanced authentication
and authorization system implemented as part of the MCP roadmap Phase 1.

**Functions:**
- `generate_default_config()`: Generate default configuration for the authentication system.
- `load_config()`: Load configuration from file or generate default.
- `save_config()`: Save configuration to file.
- `get_config_value()`: Get a configuration value by dot-separated key path.
- `setup_auth_dirs()`: Create necessary directories for authentication system.
- `print_env_setup_instructions()`: Print instructions for setting up environment variables.

#### `mcp/auth/__init__.py`

Authentication and Authorization module for IPFS Kit MCP Server.

This module provides a comprehensive authentication and authorization system
for the MCP server, including:
- Role-based access control (RBAC)
- Per-backend authorization
- API key management
- OAuth integration
- Audit logging

**Functions:**
- `initialize()`: Initialize the authentication and authorization system.
- `get_rbac_service()`: Get the global RBAC service instance.
- `get_oauth_manager()`: Get the global OAuth manager instance.
- `get_audit_logger()`: Get the global audit logger instance.
- `get_auth_handler()`: Get the global auth handler instance.

#### `mcp/auth/security_integration.py`

Security Dashboard Router Integration for MCP Server

This module integrates the security dashboard with the MCP server:
- Initializes the security analyzer 
- Registers the security dashboard routes

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Functions:**
- `setup_security_dashboard()`: Set up the security dashboard with the FastAPI application.

#### `mcp/auth/models.py`

Authentication and Authorization Models for MCP Server

Defines core authentication and authorization models:
- Permission/scope definitions
- User and role models
- Token models

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `Permission`: Available permission scopes in the MCP system.
- `Role`: User roles in the MCP system.
- `UserBase`: Base model for user data.
- `UserCreate`: Model for creating a new user.
- `UserUpdate`: Model for updating a user.
- `User`: Complete user model.
- `TokenData`: Data contained in authentication tokens.
- `TokenResponse`: Response model for token generation.
- `APIKeyBase`: Base model for API keys.
- `APIKeyCreate`: Model for creating a new API key.
- `APIKey`: Complete API key model.
- `Session`: Session model for user authentication.
- `LoginRequest`: Request model for user login.
- `RegisterRequest`: Request model for user registration.
- `RefreshTokenRequest`: Request model for refreshing an access token.
- `APIKeyResponse`: Response model for API key creation.
- `OAuthProvider`: Supported OAuth providers.
- `BackendPermission`: Backend-specific permission model.
- `PermissionModel`: Permission model for storing permission data.
- `RoleModel`: Role model for storing role data.
- `OAuthConnection`: OAuth connection model.
- `Config`
- `Config`
- `Config`
- `Config`
- `Config`
- `Config`
- `Config`

**Functions:**
- `has_permission()`: Check if a role has a specific permission.
- `get_role_permissions()`: Get all permissions for a role.
- `has_backend_permission()`: Check if a role has permission to access a specific backend.

#### `mcp/auth/oauth_manager.py`

OAuth Provider Manager for MCP Server

This module provides comprehensive OAuth integration for the MCP server as specified
in the MCP roadmap for Advanced Authentication & Authorization (Phase 1: Q3 2025).

Features:
- Configurable OAuth provider management
- Support for multiple OAuth providers (GitHub, Google, Microsoft, etc.)
- User account linking with OAuth identities
- Secure token exchange and user info retrieval
- Persistent provider configuration storage

**Classes:**
- `OAuthProviderConfig`: Configuration for an OAuth provider.
- `OAuthManager`: Manager for OAuth provider configurations and operations.
- `Config`: Pydantic model configuration.

**Functions:**
- `get_oauth_manager()`: Get or create the OAuth manager singleton instance.

#### `mcp/auth/rbac.py`

Role-Based Access Control (RBAC) Module for MCP Server

This module implements comprehensive role-based access control for the MCP server:
- Role and permission management
- Resource-based access controls
- Backend-specific authorization
- Policy enforcement

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `PermissionEffect`: Effect of a permission evaluation.
- `ResourceType`: Resource types that can be protected with access controls.
- `ActionType`: Action types that can be performed on resources.
- `Permission`: Permission definition for role-based access control.
- `Role`: Role definition for role-based access control.
- `RBACStore`: Storage backend for RBAC data.
- `RBACManager`: Role-Based Access Control Manager.

**Functions:**
- `get_instance()`: Get or create a singleton instance of the RBAC manager.

#### `mcp/auth/oauth_integration_service.py`

Authentication Service OAuth Integration

This module updates the AuthenticationService class to use the OAuth manager
for improved OAuth provider handling as specified in the MCP roadmap.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Functions:**
- `patch_authentication_service()`: Patch the AuthenticationService with improved OAuth methods.

#### `mcp/auth/oauth_security.py`

OAuth Security Enhancements for MCP Authentication Service.

This module implements enhanced security measures for OAuth integration
as specified in the MCP roadmap for Advanced Authentication & Authorization.

**Classes:**
- `OAuthStateData`: Data stored in the state parameter for CSRF protection.
- `OAuthProviderConfig`: Configuration for an OAuth provider.
- `OAuthSecurityManager`: Manages security aspects of OAuth integration.

**Functions:**
- `build_oauth_callback_url()`: Build a standardized OAuth callback URL.

#### `mcp/search/search.py`

Search infrastructure for MCP server.

This module implements content indexing, metadata search, and vector search
capabilities for the MCP server, enabling efficient discovery of IPFS content.

**Classes:**
- `ContentMetadata`: Metadata for indexed content.
- `SearchQuery`: Search query parameters.
- `VectorQuery`: Vector search query.
- `ContentSearchService`: Service for content indexing and search.

**Functions:**
- `create_search_router()`: Create a FastAPI router with search endpoints.

#### `mcp/search/mcp_search.py`

Search module for MCP server.

This module implements the search functionality mentioned in the roadmap,
including content indexing, text search, and vector search capabilities.

**Classes:**
- `SearchEngine`: Search engine for IPFS content.

#### `mcp/search/__init__.py`

Search module for MCP server.

This module implements the search capabilities mentioned in the roadmap:
- Content indexing with automated metadata extraction
- Full-text search with SQLite FTS5
- Vector search with FAISS 
- Hybrid search combining text and vector search

#### `mcp/ha/integration.py`

High Availability Integration Module for MCP Server.

This module integrates the High Availability Architecture components
with the MCP server, providing multi-region deployment, automatic failover,
load balancing, and replication and consistency features.

**Classes:**
- `HAConfig`: Configuration for High Availability.
- `HighAvailabilityIntegration`: Integration of High Availability features with MCP server.

#### `mcp/ha/failover_recovery.py`

High Availability Failover Recovery for MCP Server.

This module provides failover recovery capabilities for the MCP high availability
cluster, implementing robust recovery procedures after a primary node failure.

**Classes:**
- `RecoveryState`: States in the failover recovery process.
- `RecoveryStrategy`: Strategies for handling failover recovery.
- `FailoverRecovery`: Failover recovery manager for MCP high availability.

#### `mcp/ha/failover_detection.py`

High Availability Failover Detection for MCP Server.

This module provides failover detection capabilities for the MCP high availability
cluster, implementing smart failure detection using various strategies.

**Classes:**
- `FailureDetectionStrategy`: Strategies for detecting node failures.
- `FailoverDetector`: Enhanced failover detection for MCP high availability.

#### `mcp/persistence/policy_store.py`

Policy store for migration operations in MCP server.

This module provides persistent storage for migration policies
as specified in the MCP roadmap Q2 2025 priorities.

**Classes:**
- `PolicyStore`: Persistence store for migration policies.

#### `mcp/persistence/cache_manager.py`

Cache Manager for the MCP server.

This module provides a caching layer for operation results
with support for persistence across restarts.

**Classes:**
- `MCPCacheManager`: Cache Manager for the MCP server.

#### `mcp/persistence/migration_store.py`

Migration persistence store for MCP server.

This module provides persistent storage for migration operations
as specified in the MCP roadmap Q2 2025 priorities.

**Classes:**
- `MigrationStore`: Persistence store for migration operations.

#### `mcp/persistence/__init__.py`

Persistence components for the MCP server.

The persistence layer handles data storage and retrieval
for the MCP server, including caching and persistence of operation results.

#### `mcp/migration/migration_controller.py`

Migration Controller Framework for MCP server.

This module implements the policy-based migration controller mentioned in the roadmap,
which enables content migration between different storage backends.

**Classes:**
- `MigrationStatus`: Migration task status.
- `MigrationPriority`: Migration task priority.
- `MigrationPolicy`: Configuration for automated content migration between backends.
- `MigrationTask`: Task for migrating content between storage backends.
- `MigrationController`: Controller for managing content migration between storage backends.

**Functions:**
- `main()`: Command-line interface for migration controller.

#### `mcp/migration/__init__.py`

Migration module for MCP server.

This module implements the cross-backend migration functionality
mentioned in the roadmap, enabling content migration between
different storage backends.

#### `mcp/integrator/ha_integrator.py`

MCP Server High Availability Integration Module

This module integrates the High Availability components with the MCP server,
providing API endpoints and services for managing multi-region deployments,
automatic failover, load balancing, and replication.

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `HAIntegration`: High Availability integration for the MCP server.
- `NodeStateResponse`: Node state response model for API.
- `RegionStateResponse`: Region state response model for API.
- `ClusterStateResponse`: Cluster state response model for API.
- `FailoverRequest`: Failover request model for API.
- `FailoverResponse`: Failover response model for API.
- `HAStatusResponse`: HA status response model for API.

**Functions:**
- `get_ha_integration()`: Get the singleton HA integration instance.

#### `mcp/integrator/ai_ml_integrator.py`

MCP Server AI/ML Integration

This module integrates the AI/ML components with the MCP server.
It provides middleware and route handlers for the AI/ML functionality.

**Functions:**
- `integrate_ai_ml_with_mcp_server()`: Integrates AI/ML components with the MCP server.

#### `mcp/integrator/__init__.py`

MCP Server Integrator Package

This package contains modules for integrating various components with the MCP server.

#### `mcp/ai/dataset_management/integration.py`

Dataset Management Integration Module

This module provides functions to integrate the Dataset Management system with the MCP server.
It handles initialization, server configuration, and connecting the dataset manager
to the storage backends.

Usage:
    In the MCP server startup code:
    ```python
    from ipfs_kit_py.mcp.ai.dataset_management.integration import setup_dataset_management
    
    # During server initialization
    await setup_dataset_management(app, backend_manager)
    ```

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Functions:**
- `get_dataset_management_status()`: Get the status of the Dataset Management system.

#### `mcp/ai/dataset_management/manager.py`

MCP Dataset Management

This module implements a comprehensive dataset management system with:
- Version-controlled dataset storage
- Dataset preprocessing pipelines
- Data quality metrics
- Dataset lineage tracking

The system supports various types of datasets including:
- Tabular data (CSV, TSV, JSON)
- Image data
- Text data
- Audio data
- Video data
- Time series data
- Graph data
- Mixed data types

Datasets are stored across backend storage systems while metadata and versioning
information is managed in a database for efficient querying and retrieval.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Classes:**
- `DatasetFormat`: Supported dataset formats.
- `DatasetType`: Types of datasets.
- `DatasetStatus`: Status of a dataset version.
- `DataLicense`: Common data licenses.
- `DataQualityMetrics`: Dataset quality metrics.
- `DataSource`: Source information for a dataset.
- `PreprocessingStep`: Dataset preprocessing step.
- `Schema`: Dataset schema information.
- `DatasetMetadata`: Additional dataset metadata.
- `DataLineage`: Dataset lineage information.
- `DatasetVersion`: A specific version of a dataset.
- `Dataset`: A dataset in the registry with multiple versions.
- `DatasetStore`: Storage interface for datasets.
- `DatasetManager`: Dataset Manager for handling datasets and their versions.

#### `mcp/ai/dataset_management/router.py`

Dataset Management API Router

This module provides FastAPI routes for the Dataset Management system, enabling:
- Dataset creation and versioning
- Metadata management
- Quality metrics tracking
- Schema management
- Lineage tracking
- Dataset file storage and retrieval

These endpoints integrate with the MCP server to provide comprehensive
dataset management capabilities as part of the AI/ML integration features.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Classes:**
- `DataSourceCreate`: Data source creation request.
- `DatasetCreate`: Dataset creation request.
- `DatasetUpdate`: Dataset update request.
- `VersionUpdate`: Version update request.
- `QualityMetricsUpdate`: Quality metrics update request.
- `SchemaUpdate`: Schema update request.
- `LineageUpdate`: Lineage update request.
- `PreprocessingStepCreate`: Preprocessing step creation request.
- `User`

**Functions:**
- `initialize_dataset_manager()`: Initialize the dataset manager.

#### `mcp/ai/dataset_management/__init__.py`

MCP Dataset Management Package

This package implements a comprehensive dataset management system with:
- Version-controlled dataset storage
- Dataset preprocessing pipelines
- Data quality metrics
- Dataset lineage tracking

The system supports various types of datasets and integrates with
the storage backends provided by the MCP server.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

#### `mcp/ai/model_registry/integration.py`

Model Registry Integration Module

This module provides functions to integrate the Model Registry with the MCP server.
It handles initialization, server configuration, and connecting the registry
to the storage backends.

Usage:
    In the MCP server startup code:
    ```python
    from ipfs_kit_py.mcp.ai.model_registry.integration import setup_model_registry
    
    # During server initialization
    await setup_model_registry(app, backend_manager)
    ```

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Functions:**
- `get_model_registry_status()`: Get the status of the Model Registry.

#### `mcp/ai/model_registry/handler.py`

Model Registry Client Handler

This module provides a high-level client interface for interacting with the Model Registry.
It simplifies common operations and provides a more Pythonic interface compared to
directly calling API endpoints.

Usage example:
```python
from ipfs_kit_py.mcp.ai.model_registry.handler import ModelRegistryClient

# Create client
client = ModelRegistryClient(api_url="http://localhost:5000")

# Authenticate (if using authentication)
client.authenticate(token="your_token")

# Create a model
model = await client.create_model(
    name="My Model",
    description="My model description",
    model_type="classification"
)

# Upload a version
version = await client.upload_model_version(
    model_id=model["id"],
    version="1.0.0",
    model_path="path/to/model.pt",
    format="pytorch",
    framework="pytorch"
)

print(f"Model {model['name']} version {version['version']} uploaded!")
```

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Classes:**
- `ModelRegistryClient`: Client for interacting with the Model Registry API.

#### `mcp/ai/model_registry/registry.py`

MCP Model Registry

This module implements a model registry for machine learning models with:
- Version-controlled model storage
- Comprehensive metadata management
- Model performance tracking
- Deployment configuration management

The registry supports various model formats and frameworks including:
- PyTorch
- TensorFlow
- ONNX
- HuggingFace Transformers
- Custom models

Models are stored across backend storage systems while metadata and versioning
information is managed in a database for efficient querying and retrieval.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Classes:**
- `ModelFormat`: Supported model formats in the registry.
- `ModelFramework`: Common ML frameworks supported by the registry.
- `ModelType`: Types of machine learning models supported.
- `ModelStatus`: Status of a model version in the registry.
- `ModelMetrics`: Model performance metrics.
- `ModelDependency`: Model dependency information.
- `ModelDeploymentConfig`: Model deployment configuration.
- `ModelVersion`: A specific version of a model in the registry.
- `Model`: A model in the registry with multiple versions.
- `ModelRegistryStore`: Storage interface for the model registry.
- `ModelRegistry`: Model Registry for managing ML models and their versions.

#### `mcp/ai/model_registry/router.py`

Model Registry API Router

This module provides FastAPI routes for the Model Registry, enabling:
- Model management (CRUD operations)
- Version management
- Model data storage and retrieval
- Performance metrics tracking
- Deployment configuration management

These endpoints integrate with the MCP server to provide a comprehensive
model registry as part of the AI/ML integration features.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

**Classes:**
- `ModelCreate`: Model creation request.
- `ModelUpdate`: Model update request.
- `VersionUpdate`: Version update request.
- `MetricsUpdate`: Metrics update request.
- `DeploymentConfigUpdate`: Deployment configuration update request.
- `DependencyCreate`: Dependency create request.
- `User`

**Functions:**
- `initialize_model_registry()`: Initialize the model registry.

#### `mcp/ai/model_registry/__init__.py`

MCP Model Registry Package

This package implements a comprehensive model registry for machine learning models with:
- Version-controlled model storage
- Model metadata management
- Model performance tracking
- Deployment configuration management

The registry supports various model formats and frameworks and integrates with
the storage backends provided by the MCP server.

Part of the MCP Roadmap Phase 2: AI/ML Integration.

#### `mcp/ai/model_registry/examples/example_model_registry.py`

Model Registry Usage Example

This script demonstrates how to use the Model Registry client to:
1. Create and manage models
2. Upload model versions
3. Track performance metrics
4. Configure deployment settings
5. Compare model versions

This example provides a practical guide for working with the Model Registry.

Usage:
    python example_model_registry.py

**Functions:**
- `create_sample_model_file()`: Create a sample model file of the specified size.
- `generate_metrics()`: Generate random performance metrics for demo purposes.
- `generate_deployment_config()`: Generate sample deployment configuration.

#### `mcp/models/storage/huggingface_model.py`

HuggingFace storage model implementation for IPFS Kit.

This module provides integration with the HuggingFace Hub for storing and retrieving data.

**Classes:**
- `HuggingFaceModel`: HuggingFace storage model implementation.

#### `mcp/models/storage/ftp_model.py`

FTP Storage Backend Model for MCP Integration

This module defines the FTP storage backend model structure for Model Context Protocol (MCP) integration,
providing schema definitions and validation for FTP storage backend configurations.

**Classes:**
- `FTPConnectionConfig`: FTP connection configuration parameters
- `FTPStorageMetadata`: FTP storage backend metadata structure for MCP
- `FTPOperationResult`: Result structure for FTP operations
- `FTPHealthStatus`: FTP backend health status information
- `FTPModel`: Complete FTP storage backend model for MCP integration
- `Config`
- `Config`
- `Config`
- `Config`
- `Config`

#### `mcp/models/storage/filecoin_data_models.py`

Filecoin Data Models

This module provides data models for Filecoin operations.

**Classes:**
- `TipsetKeyModel`: Tipset key model for Filecoin operations.
- `FilecoinDeal`: Model for Filecoin storage deals.
- `FilecoinTipset`: Model for Filecoin tipsets.

#### `mcp/models/storage/storacha_model.py`

Storacha (Web3.Storage) Model for MCP Server.

This module provides the business logic for Storacha (Web3.Storage) operations in the MCP server.
It integrates with the enhanced StorachaConnectionManager for reliable API communication.

**Classes:**
- `StorachaModel`: Model for Storacha (Web3.Storage) operations.

#### `mcp/models/storage/s3_model.py`

S3 Model for MCP Server.

This module provides the business logic for S3 operations in the MCP server.
It relies on the s3_kit module for underlying functionality.

**Classes:**
- `S3Model`: Model for S3 operations.

#### `mcp/models/storage/ipfs_model.py`

IPFS Storage Model for MCP server.

This module provides the IPFS implementation of the BaseStorageModel
interface for the MCP server.

**Classes:**
- `IPFSModel`: IPFS storage model for MCP server.

#### `mcp/models/storage/filecoin_model_anyio.py`

Filecoin Model AnyIO Module

This module provides the AnyIO-compatible Filecoin model functionality.

**Classes:**
- `FilecoinModelAnyIO`: AnyIO-compatible model for Filecoin operations.

#### `mcp/models/storage/sshfs_model.py`

SSHFS Model for MCP Storage Manager.

This model provides an interface between the MCP storage manager
and the SSHFS backend implementation.

**Classes:**
- `SSHFSModel`: SSHFS storage model for MCP integration.

#### `mcp/models/storage/ipfs_model_anyio.py`

IPFS Storage Model with AnyIO support for MCP server.

This module provides the asynchronous IPFS implementation of the BaseStorageModel
interface for the MCP server.

**Classes:**
- `IPFSModelAnyIO`: Asynchronous IPFS storage model for MCP server.

#### `mcp/models/storage/lassie_model.py`

Lassie Model for MCP Server.

This module provides the business logic for Lassie operations in the MCP server.
It relies on the lassie_kit module for underlying functionality.

**Classes:**
- `LassieModel`: Model for Lassie operations.

#### `mcp/models/storage/base_storage_model.py`

BaseStorageModel module for MCP server.

This module provides the base class for all storage backend models in the MCP server.
It defines a standard interface and common functionality for all storage backends,
ensuring consistent behavior and error handling across different implementations.

**Classes:**
- `BaseStorageModel`: Base model for storage backend operations.

#### `mcp/models/storage/__init__.py`

Storage backend models for MCP server.

This package provides models for different storage backends:
- S3 (AWS S3 and compatible services)
- Hugging Face Hub (model and dataset repository)
- Storacha (Web3.Storage)
- Filecoin (Lotus API integration)
- Lassie (Filecoin/IPFS content retrieval)

These models implement the business logic for storage operations
and follow a common interface pattern.

**Classes:**
- `BaseStorageModel`: Base model for storage backend operations.

#### `mcp/models/storage/filecoin_model.py`

Filecoin Model Module

This module provides the Filecoin model functionality for the MCP server.

**Classes:**
- `FilecoinModel`: Model for Filecoin operations.

#### `mcp/controllers/api/auth_router.py`

Authentication API router for MCP server.

This module provides REST API endpoints for authentication and authorization
as specified in the MCP roadmap.

**Functions:**
- `create_auth_router()`: Create a FastAPI router for authentication endpoints.

#### `mcp/controllers/api/migration_router.py`

Migration API router for MCP server.

This module provides REST API endpoints for the cross-backend migration functionality
as specified in the MCP roadmap Q2 2025 priorities.

#### `mcp/controllers/storage/s3_storage_controller.py`

Storage Controller for the MCP server.

**Classes:**
- `S3StorageController`: Controller for s3 storage controller operations.

#### `mcp/controllers/storage/huggingface_controller.py`

Hugging Face Controller for the MCP server.

This controller handles HTTP requests related to Hugging Face Hub operations and
delegates the business logic to the Hugging Face model.

**Classes:**
- `HuggingFaceRequest`: Base request model for Hugging Face operations.
- `DownloadRequest`: Request model for downloading from Hugging Face Hub.
- `UploadRequest`: Request model for uploading to Hugging Face Hub.
- `DeleteRequest`: Request model for deleting from Hugging Face Hub.
- `HuggingFaceResponse`: Base response model for Hugging Face operations.
- `HuggingFaceController`: Controller for Hugging Face operations.

#### `mcp/controllers/storage/storacha_controller.py`

Storacha (Web3.Storage) Controller for the MCP server.

This controller handles HTTP requests related to Storacha (Web3.Storage) operations and
delegates the business logic to the Storacha model.

**Classes:**
- `StorachaSpaceCreationRequest`: Request model for Storacha space creation.
- `StorachaSetSpaceRequest`: Request model for setting the current Storacha space.
- `StorachaUploadRequest`: Request model for Storacha upload operations.
- `StorachaUploadCarRequest`: Request model for Storacha CAR upload operations.
- `StorachaDeleteRequest`: Request model for Storacha delete operations.
- `IPFSStorachaRequest`: Request model for IPFS to Storacha operations.
- `StorachaIPFSRequest`: Request model for Storacha to IPFS operations.
- `OperationResponse`: Base response model for operations.
- `StorachaSpaceCreationResponse`: Response model for Storacha space creation.
- `StorachaListSpacesResponse`: Response model for listing Storacha spaces.
- `StorachaSetSpaceResponse`: Response model for setting the current Storacha space.
- `StorachaUploadResponse`: Response model for Storacha upload operations.
- `StorachaUploadCarResponse`: Response model for Storacha CAR upload operations.
- `StorachaListUploadsResponse`: Response model for listing Storacha uploads.
- `StorachaDeleteResponse`: Response model for Storacha delete operations.
- `IPFSStorachaResponse`: Response model for IPFS to Storacha operations.
- `StorachaIPFSResponse`: Response model for Storacha to IPFS operations.
- `StorachaStatusResponse`: Response model for Storacha status.
- `StorachaController`: Controller for Storacha (Web3.Storage) operations.

#### `mcp/controllers/storage/ipfs_storage_controller.py`

Storage Controller for the MCP server.

**Classes:**
- `IpfsStorageController`: Controller for ipfs storage controller operations.

#### `mcp/controllers/storage/s3_controller_anyio.py`

S3 Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to S3 operations and
delegates the business logic to the S3 model, with support for both async-io
and trio via the AnyIO library.

**Classes:**
- `S3ControllerAnyIO`: Controller for S3 operations with AnyIO support.

#### `mcp/controllers/storage/s3_controller.py`

S3 Controller for the MCP server.

This controller handles HTTP requests related to S3 operations and
delegates the business logic to the S3 model.

**Classes:**
- `S3CredentialsRequest`: Request model for S3 credentials.
- `S3UploadRequest`: Request model for S3 upload operations.
- `S3DownloadRequest`: Request model for S3 download operations.
- `S3ListRequest`: Request model for S3 list operations.
- `S3DeleteRequest`: Request model for S3 delete operations.
- `IPFSS3Request`: Request model for IPFS to S3 operations.
- `S3IPFSRequest`: Request model for S3 to IPFS operations.
- `OperationResponse`: Base response model for operations.
- `S3UploadResponse`: Response model for S3 upload operations.
- `S3DownloadResponse`: Response model for S3 download operations.
- `S3ListResponse`: Response model for S3 list operations.
- `S3DeleteResponse`: Response model for S3 delete operations.
- `IPFSS3Response`: Response model for IPFS to S3 operations.
- `S3IPFSResponse`: Response model for S3 to IPFS operations.
- `S3Controller`: Controller for S3 operations.

#### `mcp/controllers/storage/filecoin_controller.py`

Filecoin Controller Module

This module provides the Filecoin controller functionality for the MCP server.

**Classes:**
- `WalletRequest`: Request model for wallet operations.
- `DealRequest`: Request model for deal operations.
- `RetrieveRequest`: Request model for data retrieval.
- `IPFSToFilecoinRequest`: Request model for IPFS to Filecoin operations.
- `FilecoinToIPFSRequest`: Request model for Filecoin to IPFS operations.
- `ImportFileRequest`: Request model for file import operations.
- `MinerInfoRequest`: Request model for miner info operations.
- `TipsetKeyModel`: Tipset key model for Filecoin operations.
- `WalletRequest`: Request model for wallet operations.
- `DealRequest`: Request model for deal operations.
- `RetrieveRequest`: Request model for content retrieval.
- `IPFSToFilecoinRequest`: Request model for transferring content from IPFS to Filecoin.
- `FilecoinToIPFSRequest`: Request model for transferring content from Filecoin to IPFS.
- `ImportFileRequest`: Request model for importing a file.
- `MinerInfoRequest`: Request model for miner information.
- `FilecoinDealRequest`: Request model for Filecoin storage deals.
- `FilecoinDealStatus`: Status model for Filecoin storage deals.
- `GetTipsetRequest`: Request model for retrieving a Filecoin tipset.
- `FilecoinController`: Controller for Filecoin operations.

#### `mcp/controllers/storage/storacha_controller_anyio.py`

Storacha (Web3.Storage) Controller AnyIO Implementation for the MCP server.

This module provides asynchronous versions of the Storacha controller operations
using AnyIO for compatibility with both async-io and trio async frameworks.

**Classes:**
- `StorachaControllerAnyIO`: AnyIO-compatible controller for Storacha (Web3.Storage) operations.

#### `mcp/controllers/storage/huggingface_controller_anyio.py`

Hugging Face Controller for the MCP server (AnyIO version).

This controller handles HTTP requests related to Hugging Face Hub operations and
delegates the business logic to the Hugging Face model using AnyIO for async operations.

**Classes:**
- `HuggingFaceRequest`: Base request model for Hugging Face operations.
- `HuggingFaceRepoCreationRequest`: Request model for creating a repository on Hugging Face Hub.
- `DownloadRequest`: Request model for downloading from Hugging Face Hub.
- `UploadRequest`: Request model for uploading to Hugging Face Hub.
- `DeleteRequest`: Request model for deleting from Hugging Face Hub.
- `HuggingFaceResponse`: Base response model for Hugging Face operations.
- `HuggingFaceController`: Controller for Hugging Face operations.

#### `mcp/controllers/storage/file_storage_controller.py`

FileStorageController implementation for the MCP Server.

Handles file storage controller operations.

**Classes:**
- `FileStorageController`: Controller for file storage controller operations.

#### `mcp/controllers/storage/filecoin_controller_anyio.py`

**Classes:**
- `FilecoinControllerAnyIO`: Controller for Filecoin operations with AnyIO support.

#### `mcp/controllers/storage/lassie_controller.py`

Lassie Controller for the MCP server.

This controller handles HTTP requests related to Lassie operations and
delegates the business logic to the Lassie model. Lassie is a tool for
retrieving content from the Filecoin/IPFS networks.

**Classes:**
- `FetchCIDRequest`: Request model for Lassie CID fetch operations.
- `FetchRequest`: Request model for Lassie fetch operations.
- `StatusRequest`: Request model for Lassie status operations.
- `LassieResponse`: Base response model for Lassie operations.
- `FetchResponse`: Response model for Lassie fetch operations.
- `StatusResponse`: Response model for Lassie status operations.
- `LassieController`: Controller for Lassie operations.

#### `mcp/controllers/storage/__init__.py`

Storage backend controllers for MCP server.

This package provides controllers for different storage backends:
- S3 (AWS S3 and compatible services)
- Hugging Face Hub (model and dataset repository)
- Storacha (Web3.Storage)
- Filecoin (Lotus API integration)
- Lassie (Filecoin/IPFS content retrieval)

These controllers handle HTTP requests related to storage operations
and delegate the business logic to the corresponding storage models.

#### `mcp/controllers/ipfs/dag_controller.py`

DAG Controller for the MCP server.

This controller provides an interface to the DAG functionality of IPFS through the MCP API.

**Classes:**
- `DAGController`: Controller for DAG operations.

#### `mcp/controllers/ipfs/ipns_controller.py`

IPNS Controller for the MCP server.

This controller provides an interface to the IPNS functionality of IPFS through the MCP API.

**Classes:**
- `IPNSController`: Controller for IPNS operations.

#### `mcp/controllers/ipfs/dht_controller.py`

DHT Controller for the MCP server.

This controller provides an interface to the DHT functionality of IPFS through the MCP API.

**Classes:**
- `DHTController`: Controller for DHT operations.

#### `mcp/controllers/ipfs/router.py`

IPFS Router for the MCP server.

This module provides a FastAPI router for all IPFS advanced operations controllers.

**Functions:**
- `create_ipfs_router()`: Create a FastAPI router for advanced IPFS operations.
- `register_with_app()`: Register the IPFS router with a FastAPI app.
- `register_with_mcp()`: Register the IPFS router with an MCP server.

#### `mcp/controllers/ipfs/__init__.py`

IPFS Controllers Package for the MCP server.

This package provides controllers for advanced IPFS operations through the MCP API.

#### `mcp/monitoring/alerts/manager.py`

Alert Management System for MCP Server

This module provides alerting capabilities for metric thresholds and health checks
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Key features:
- Configurable alert rules for metrics
- Multiple notification channels (email, webhook, syslog)
- Alert status tracking and history
- Alert suppression and grouping

**Classes:**
- `AlertSeverity`: Alert severity levels.
- `AlertState`: Alert states.
- `NotificationType`: Types of alert notifications.
- `AlertRule`: Definition of an alert rule.
- `Alert`: An instance of a triggered alert.
- `NotificationManager`: Manager for alert notifications.
- `AlertManager`: Manager for alert rules and instances.

**Functions:**
- `get_instance()`: Get or create the singleton alert manager instance.

#### `mcp/enterprise/security/vulnerability_scanner.py`

Vulnerability Scanning Module for MCP Server

This module implements a comprehensive vulnerability scanning system for the MCP server,
providing automated detection of security weaknesses, compliance gaps, and configuration issues.

Key features:
1. Automated vulnerability detection and assessment
2. System configuration scanning
3. Dependency security analysis
4. Compliance validation
5. Remediation recommendations

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `VulnerabilityLevel`: Severity levels for vulnerabilities.
- `VulnerabilityCategory`: Categories of vulnerabilities.
- `Vulnerability`: Representation of a detected vulnerability.
- `ScanPolicy`: Policy defining what and how to scan.
- `ScanResult`: Results of a vulnerability scan.
- `VulnerabilityScanner`: Manager for vulnerability scanning.

#### `mcp/enterprise/security/__init__.py`

Enterprise Security Module for MCP Server

This module provides advanced security features for the MCP server, including:
- End-to-end encryption
- Secure key management
- Cryptographic operations
- Security policy enforcement

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).

**Classes:**
- `SecurityFeature`: Supported security features.
- `SecurityLevel`: Security levels for the MCP server.
- `SecurityManager`: Main class for managing security features in the MCP server.

**Functions:**
- `get_security_manager()`: Get the singleton instance of the security manager.

#### `mcp/storage_manager/router/performance_tracker.py`

Performance Tracking for Storage Backend Selection

This module implements performance tracking and analysis for selecting
the optimal storage backend based on observed performance metrics.

**Classes:**
- `BackendPerformanceTracker`: Tracks performance metrics for each backend.

**Functions:**
- `get_instance()`: Get or create the singleton performance tracker instance.

#### `mcp/storage_manager/router/cost_optimizer.py`

Cost Optimization for Storage Backend Selection

This module implements cost analysis and optimization for selecting
the most cost-effective storage backend for different operations.

**Classes:**
- `CostOptimizer`: Cost optimization for storage backends.

**Functions:**
- `get_instance()`: Get or create the singleton cost optimizer instance.

#### `mcp/storage_manager/router/balanced.py`

Advanced Balanced Router for Optimized Data Routing

This module implements a sophisticated content router that combines
multiple routing strategies to make intelligent decisions about which
backend to use for different types of content and operations.

**Classes:**
- `BalancedRouter`: Advanced balanced router that combines multiple routing strategies.

**Functions:**
- `get_balanced_instance()`: Get or create the singleton balanced router instance.

#### `mcp/storage_manager/router/__init__.py`

Optimized Data Routing for MCP Storage Manager

This module implements intelligent content-aware routing algorithms
for selecting the optimal storage backend for different types of content
and operations.

As specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `RoutingStrategy`: Available routing strategies for backend selection.
- `RouterMetrics`: Collector for routing performance metrics.
- `ContentRouter`: Base content router for optimized backend selection.

**Functions:**
- `get_instance()`: Get or create the singleton content router instance.

#### `mcp/storage_manager/router/content_analyzer.py`

Content Type Analyzer for Optimized Data Routing

This module analyzes content types and characteristics to make 
intelligent routing decisions for different kinds of content.

**Classes:**
- `ContentTypeAnalyzer`: Analyzes content to determine optimal storage strategies.

**Functions:**
- `get_instance()`: Get or create the singleton content type analyzer instance.

#### `mcp/storage_manager/monitoring/performance_monitor.py`

Performance monitoring utilities for IPFS backend.

This module implements performance monitoring capabilities for the IPFS backend,
addressing the 'Test performance monitoring after fix' item in the MCP roadmap.

**Classes:**
- `OperationType`: Constants for different operation types.
- `IPFSPerformanceMonitor`: Monitors and tracks performance metrics for IPFS operations.
- `PerformanceTracker`: Decorator and context manager for tracking IPFS operation performance.

#### `mcp/storage_manager/monitoring/__init__.py`

Monitoring package for MCP storage manager.

This package provides monitoring utilities for the MCP storage backends,
addressing the performance monitoring requirements in the MCP roadmap.

#### `mcp/storage_manager/metadata/ipfs_metadata.py`

IPFS metadata manager for MCP.

This module implements enhanced metadata handling for IPFS content,
addressing the metadata integration requirements in the MCP roadmap.

**Classes:**
- `IPFSMetadataManager`: Manages metadata storage and retrieval for IPFS content.

#### `mcp/storage_manager/backends/ipfs_advanced_backend.py`

Advanced IPFS Backend Extensions

This module extends the core IPFSBackend with advanced IPFS operations:
- DHT operations for enhanced network participation
- Object and DAG manipulation operations
- Advanced IPNS functionality with key management
- MFS (Mutable File System) operations
- Swarm and diagnostic operations

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `IPFSAdvancedBackend`: Extended IPFS backend implementation with advanced operations.

#### `mcp/storage_manager/backends/lassie_backend.py`

Lassie backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Lassie,
a robust content fetching library for IPFS/Filecoin, providing
efficient content retrieval from the distributed web.

**Classes:**
- `LassieBackend`: Lassie backend implementation for content retrieval from IPFS/Filecoin.

#### `mcp/storage_manager/backends/filecoin_backend.py`

Filecoin backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Filecoin,
allowing the Unified Storage Manager to interact with the Filecoin network.

**Classes:**
- `FilecoinBackend`: Filecoin backend implementation.

#### `mcp/storage_manager/backends/storacha_backend.py`

Storacha backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Storacha (Web3.Storage),
providing high-performance access to decentralized storage via the W3 Blob Protocol
with enhanced reliability, caching, and migration capabilities.

**Classes:**
- `StorachaConnectionManager`: Manages connections to Storacha API endpoints with failover capabilities.
- `StorachaBackend`: Storacha backend implementation for Web3.Storage with enhanced capabilities.

#### `mcp/storage_manager/backends/ipfs_backend.py`

IPFS backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for IPFS to support
content storage and retrieval through the IPFS network.

**Classes:**
- `IPFSBackend`: IPFS backend implementation.
- `MockIPFSPy`: Mock implementation of ipfs_py for when the real one can't be imported.

#### `mcp/storage_manager/backends/s3_backend.py`

S3 backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Amazon S3 and S3-compatible
storage services with enhanced performance, caching, and migration capabilities.

**Classes:**
- `S3ConnectionPool`: Manages a pool of S3 clients for improved performance.
- `S3Backend`: S3 backend implementation for Amazon S3 and compatible services with enhanced features.

#### `mcp/storage_manager/backends/huggingface_backend.py`

HuggingFace backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for HuggingFace Hub,
providing access to models, datasets, and other assets from the HuggingFace ecosystem.

**Classes:**
- `HuggingFaceBackend`: HuggingFace Hub backend implementation for the unified storage manager.

#### `mcp/storage_manager/backends/ipfs_bridge.py`

Bridge module for ipfs_py class from ipfs_kit_py.ipfs module.

This module provides a direct implementation of ipfs_py to avoid circular imports
and makes it available for the MCP storage manager IPFS backend.

**Classes:**
- `ipfs_py`: IPFS Python interface for interacting with the IPFS daemon.
- `IPFSError`: Base class for IPFS errors.
- `IPFSValidationError`: Error for validation failures.
- `IPFSConnectionError`: Error for connection failures.
- `IPFSTimeoutError`: Error for timeout failures.
- `IPFSContentNotFoundError`: Error for content not found failures.
- `IPFSPinningError`: Error for pinning failures.
- `IPFSConfigurationError`: Error for configuration failures.

**Functions:**
- `is_valid_cid()`: Validate that a string is a properly formatted IPFS CID.
- `validate_command_args()`: Validate command arguments for security.

#### `mcp/storage_manager/backends/__init__.py`

Storage backend implementations.

This package contains implementations of various storage backends used by the MCP server.

#### `mcp/storage_manager/backends/ipfs_advanced_router.py`

Advanced IPFS Operations Router

This module provides comprehensive IPFS functionality beyond basic operations:
- DHT operations for enhanced network participation
- Object and DAG manipulation endpoints
- Advanced IPNS functionality with key management
- Extended filesystem operations

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `DHTProvideRequest`: Request to provide content to the DHT.
- `DHTFindPeerRequest`: Request to find a peer in the DHT.
- `DHTFindProvsRequest`: Request to find providers for a CID in the DHT.
- `ObjectPatchRequest`: Request to patch an IPFS object.
- `DAGPutRequest`: Request to put a DAG node.
- `NamePublishRequest`: Request to publish an IPNS name.
- `KeygenRequest`: Request to generate a new key.

**Functions:**
- `create_advanced_ipfs_router()`: Create and configure the advanced IPFS router.

#### `mcp/storage_manager/backends/ipfs_advanced_integration.py`

Advanced IPFS Operations Integration Module

This module integrates the advanced IPFS operations into the MCP server:
- Registers the advanced IPFS backend as the default IPFS implementation
- Sets up all the advanced API endpoints
- Provides utilities for working with advanced IPFS features

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Functions:**
- `setup_advanced_ipfs_operations()`: Set up advanced IPFS operations in the MCP server.

#### `mcp/routing/examples/basic_routing.py`

Basic Routing Example

This example demonstrates how to use the Optimized Data Routing system
to intelligently select storage backends for different types of content
and operations.

**Functions:**
- `initialize_routing_system()`: Initialize the routing system with example configuration.
- `demonstrate_content_based_routing()`: Demonstrate content-based routing for different file types.
- `demonstrate_cost_based_routing()`: Demonstrate cost-based routing for different operation types and sizes.
- `demonstrate_performance_based_routing()`: Demonstrate performance-based routing using metrics.
- `demonstrate_geographic_routing()`: Demonstrate geographic routing for users in different regions.
- `demonstrate_composite_routing()`: Demonstrate composite routing that considers all factors.
- `main()`: Run the example application.

#### `mcp/routing/examples/multimedia_storage_app.py`

Advanced Example: Multimedia Storage Application

This example demonstrates how to use the Optimized Data Routing system in a
real-world multimedia storage application that handles various types of media
files with different storage requirements.

The application simulates:
1. User uploads of different media types
2. Intelligent backend selection based on content
3. Performance monitoring and adaptation
4. Cost optimization for different user tiers
5. Geographic routing for global users

**Classes:**
- `User`: User model for the multimedia application.
- `MediaFile`: Media file model.
- `MediaStorage`: Multimedia storage application that uses intelligent routing

**Functions:**
- `run_simulation()`: Run a simulation of the multimedia storage application.

#### `mcp/routing/algorithms/geographic.py`

Geographic Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on geographic location to minimize latency and comply with data residency requirements.

**Classes:**
- `GeographicRouter`: Routing strategy that selects backends based on geographic considerations.

#### `mcp/routing/algorithms/composite.py`

Composite Routing Strategy.

This module provides a composite routing strategy that combines multiple
other strategies with configurable weights to make balanced routing decisions.

**Classes:**
- `CompositeRouter`: Combines multiple routing strategies with weighted scoring.

#### `mcp/routing/algorithms/content_aware.py`

Content-Aware Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on the type and characteristics of the content being stored or retrieved.

**Classes:**
- `ContentAwareRouter`: Routing strategy that selects backends based on content characteristics.

#### `mcp/routing/algorithms/cost_based.py`

Cost-Based Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on cost metrics such as storage cost, retrieval cost, and operation cost.

**Classes:**
- `CostBasedRouter`: Routing strategy that selects backends based on cost considerations.

#### `mcp/routing/algorithms/performance.py`

Performance-Based Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on performance metrics such as latency, throughput, and availability.

**Classes:**
- `PerformanceRouter`: Routing strategy that selects backends based on performance metrics.

#### `mcp/routing/algorithms/__init__.py`

Routing Algorithms for Optimized Data Routing.

This module provides various routing strategies for selecting the optimal
storage backend based on different criteria such as content type, cost,
geographic location, and performance metrics.

#### `mcp/auth/examples/mcp_server_auth_example.py`

MCP Server with Advanced Authentication & Authorization Example

This module demonstrates how to integrate the Advanced Authentication & Authorization system
with the MCP server. It shows the key integration points and configuration options.

This is a simplified version of the main server to focus on auth integration.

**Functions:**
- `main()`: Run the MCP server.

#### `mcp/ha/replication/consistency.py`

Data Replication and Consistency Module for MCP High Availability Architecture.

This module implements the data replication and consistency mechanisms
for the High Availability architecture as specified in the MCP roadmap Phase 3: Enterprise Features.

Features:
- Replication strategies (synchronous, asynchronous, quorum-based)
- Consistency models (strong, eventual, causal)
- Conflict detection and resolution
- Data versioning and vector clocks
- Optimized data synchronization

**Classes:**
- `ConsistencyModel`: Consistency model for data replication.
- `ReplicationStrategy`: Replication strategy.
- `ConflictResolutionStrategy`: Strategy for resolving conflicts.
- `VectorClock`: Vector clock for tracking causality.
- `DataVersion`: Version information for replicated data.
- `ReplicatedData`: Data to be replicated across nodes.
- `SyncRecord`: Record of synchronization between nodes.
- `ConsistencyStatus`: Status of consistency across the cluster.
- `ReplicationConfig`: Configuration for replication.
- `ConsistencyService`: Service for managing data replication and consistency in the MCP High Availability cluster.

#### `mcp/ha/replication/router.py`

API Router for Replication and Consistency in MCP High Availability Architecture.

This module provides REST API endpoints for the data replication and consistency
functionality, allowing nodes to synchronize data across the cluster.

**Classes:**
- `KeyItem`: Key item for batch operations.
- `KeysRequest`: Request for batch key operations.
- `VersionInfo`: Version information for a key.
- `VersionsRequest`: Request for comparing versions.
- `SetRequest`: Request for setting a key.
- `BatchSetRequest`: Request for setting multiple keys.
- `ConfigModel`: Configuration for replication.

**Functions:**
- `get_consistency_service()`: Get consistency service from request.
- `register_with_app()`: Register replication router with FastAPI app.

#### `mcp/security/encryption/core.py`

End-to-End Encryption Module for MCP Security.

This module provides end-to-end encryption capabilities for the MCP server
as specified in Phase 3: Enterprise Features of the MCP roadmap.

Features:
- End-to-end encryption for stored content
- Secure key management
- Content encryption/decryption
- Key rotation
- Encrypted streaming

**Classes:**
- `EncryptionAlgorithm`: Encryption algorithms supported.
- `KeyType`: Key types.
- `EncryptionKey`: Encryption key information.
- `EncryptedData`: Encrypted data container.
- `EndToEndEncryptionError`: Base exception for encryption errors.
- `KeyManagementError`: Exception for key management errors.
- `EncryptionError`: Exception for encryption errors.
- `DecryptionError`: Exception for decryption errors.
- `KeyStoreError`: Exception for key store errors.
- `EndToEndEncryption`: End-to-End Encryption service for MCP.
- `Fernet`

**Functions:**
- `create_password_derived_key()`: Create a key derived from a password.

### mcp.py

#### `mcp.py`

**Classes:**
- `Message`
- `MCP`
- `Server`

### mcp_client.py

#### `mcp_client.py`

**Classes:**
- `MCPClient`

### mcp_error_handling.py

#### `mcp_error_handling.py`

Standard error handling for MCP controllers.

This module provides standardized error handling for MCP controllers.

**Functions:**
- `raise_http_exception()`: Raise a standardized HTTP exception.

### mcp_extensions.py

#### `mcp_extensions.py`

MCP Extensions Module

This module provides extensions for the MCP server to integrate with various storage backends.
It's used by the enhanced_mcp_server_real.py script to add real storage backend implementations.

**Functions:**
- `update_storage_backends()`: Update the storage backends status with real implementations.
- `create_extension_routers()`: Create and return FastAPI routers for storage backend extensions.

### mcp_metadata_wrapper.py

#### `mcp_metadata_wrapper.py`

MCP Tools Metadata-First Wrapper

This module wraps MCP tools to check ~/.ipfs_kit/ metadata first
before making calls to the ipfs_kit_py library.

**Classes:**
- `MetadataFirstMCP`: Wrapper for MCP tools that checks local metadata before library calls.
- `EnhancedMCPTools`: Enhanced MCP tools that use metadata-first approach.

**Functions:**
- `get_mcp_wrapper()`: Get the global MCP metadata wrapper instance.
- `with_metadata_check()`: Convenience decorator for metadata checking.
- `get_enhanced_mcp_tools()`: Get the global enhanced MCP tools instance.
- `get_metadata_first_mcp()`: Get the global metadata-first MCP instance.
- `metadata_first_decorator()`: Convenience decorator for metadata-first operations.
- `wrap_mcp_tool()`: Convenience function to wrap MCP tools.
- `list_backends()`: Example: List backends with metadata-first approach.
- `get_backend_status()`: Example: Get backend status with metadata-first approach.

### mcp_search.py

#### `mcp_search.py`

MCP Search module - Backward compatibility module.

This module provides backward compatibility for code using the old import path.
The actual implementation has been moved to ipfs_kit_py.mcp.search module.

### mcp_server

#### `mcp_server/server.py`

Refactored MCP Server - Aligned with CLI codebase

This is the main MCP server implementation that mirrors the CLI functionality
while adapting to the MCP protocol. It efficiently reads metadata from ~/.ipfs_kit/
and delegates to the intelligent daemon for backend synchronization.

**Classes:**
- `MCPServerConfig`: Configuration for the MCP Server.
- `MCPServer`: Refactored MCP Server aligned with CLI codebase
- `types`
- `Server`
- `Tool`
- `TextContent`
- `MockTransport`
- `MCPStatusHandler`

**Functions:**
- `find_random_port()`: Finds a random available port.

#### `mcp_server/__init__.py`

MCP Server - Refactored to align with CLI codebase

This module provides the Model Context Protocol (MCP) server implementation that
mirrors the CLI functionality while adapting to the MCP protocol requirements.

The refactored MCP server:
1. Uses similar codebase structure to the CLI
2. Leverages metadata from ~/.ipfs_kit/ efficiently  
3. Integrates with the intelligent daemon for backend synchronization
4. Provides all CLI features through MCP protocol
5. Maintains compatibility with existing MCP clients

#### `mcp_server/models/mcp_config_manager.py`

MCP Configuration Manager

Manages configuration for the MCP server by reading from ~/.ipfs_kit/ files.
This is a lightweight config manager focused on atomic operations.

**Classes:**
- `MCPConfigManager`: Configuration manager for MCP server that reads from ~/.ipfs_kit/ files.

**Functions:**
- `get_mcp_config_manager()`: Get MCP configuration manager instance.

#### `mcp_server/models/mcp_metadata_manager.py`

MCP Metadata Manager - Efficient metadata reading from ~/.ipfs_kit/

This module provides efficient access to IPFS Kit metadata stored in ~/.ipfs_kit/
for the MCP server. It mirrors the CLI's approach to metadata management while
optimizing for MCP protocol usage patterns.

**Classes:**
- `BackendMetadata`: Metadata for a single backend.
- `PinMetadata`: Metadata for a pinned content item.
- `BucketMetadata`: Metadata for a bucket.
- `MCPMetadataManager`: Efficient metadata manager for MCP server that reads from ~/.ipfs_kit/

#### `mcp_server/models/__init__.py`

MCP Server Models - Data models and metadata management

This package contains models for the MCP server:
- MCPMetadataManager: Efficient metadata reading from ~/.ipfs_kit/

#### `mcp_server/controllers/mcp_backend_controller.py`

MCP Backend Controller - Mirrors CLI backend commands

This controller provides MCP tools that mirror the CLI backend commands,
allowing MCP clients to manage backends with the same functionality as
the command line interface.

**Classes:**
- `MCPBackendController`: MCP Backend Controller that mirrors CLI backend commands

#### `mcp_server/controllers/mcp_vfs_controller.py`

MCP VFS Controller - Mirrors CLI VFS commands

This controller provides MCP tools that mirror the CLI VFS (Virtual File System)
commands, allowing MCP clients to manage VFS operations with the same functionality
as the command line interface.

**Classes:**
- `MCPVFSController`: MCP VFS Controller that mirrors CLI VFS commands

#### `mcp_server/controllers/mcp_storage_controller.py`

MCP Storage Controller - Mirrors CLI storage commands

This controller provides MCP tools that mirror the CLI storage commands,
allowing MCP clients to manage storage operations with the same functionality
as the command line interface.

**Classes:**
- `MCPStorageController`: MCP Storage Controller that mirrors CLI storage commands

#### `mcp_server/controllers/mcp_cli_controller.py`

MCP CLI Controller - Mirrors CLI pin and bucket commands

This controller provides MCP tools that mirror the CLI pin and bucket commands,
allowing MCP clients to manage pins and buckets with the same functionality
as the command line interface.

**Classes:**
- `MCPCLIController`: MCP CLI Controller that mirrors CLI pin and bucket commands

#### `mcp_server/controllers/mcp_daemon_controller.py`

MCP Daemon Controller - Mirrors CLI daemon commands

This controller provides MCP tools that mirror the CLI daemon commands,
allowing MCP clients to manage daemon services with the same functionality
as the command line interface.

**Classes:**
- `MCPDaemonController`: MCP Daemon Controller that mirrors CLI daemon commands

#### `mcp_server/controllers/__init__.py`

MCP Server Controllers - Mirrors CLI command structure

This package contains controllers that provide MCP tools mirroring the CLI commands:
- MCPBackendController: Backend management tools
- MCPDaemonController: Daemon management tools  
- MCPStorageController: Storage operation tools
- MCPVFSController: Virtual File System tools
- MCPCLIController: Pin and bucket management tools

#### `mcp_server/services/mcp_daemon_service.py`

MCP Daemon Service - Lightweight Interface

This service provides a lightweight interface to interact with the daemon
WITHOUT starting or managing it. It performs atomic operations and reads
daemon status from ~/.ipfs_kit/ files.

The daemon itself is managed separately via 'ipfs-kit daemon' commands.

**Classes:**
- `DaemonStatus`: Daemon status information read from files.
- `MCPDaemonService`: Lightweight daemon interface for MCP server.

#### `mcp_server/services/__init__.py`

MCP Server Services - Backend integration services

This package contains services for the MCP server:
- MCPDaemonService: Integration with intelligent daemon manager

#### `mcp_server/services/mcp_daemon_service_old.py`

MCP Daemon Service - Integration with Intelligent Daemon Manager

This service provides MCP server integration with the intelligent daemon manager,
allowing the MCP server to leverage the daemon for backend synchronization and
metadata management while preserving CLI behavior patterns.

**Classes:**
- `DaemonStatus`: Status information for the daemon service.
- `MCPDaemonService`: MCP Daemon Service that integrates with Intelligent Daemon Manager

### metadata_manager.py

#### `metadata_manager.py`

Metadata Manager for IPFS Kit

This module manages metadata and configuration in the ~/.ipfs_kit/ directory
as specified in the requirements. It provides a centralized way to manage
service configurations, monitoring data, and other metadata.

**Classes:**
- `MetadataManager`: Manages metadata and configuration in the ~/.ipfs_kit/ directory.

**Functions:**
- `get_metadata_manager()`: Get the global metadata manager instance.

### metadata_sync_handler.py

#### `metadata_sync_handler.py`

IPFS metadata index synchronization handler.

This module provides handlers for metadata index synchronization using IPFS pubsub.
It manages subscription to relevant topics and routes messages to the appropriate
handlers in the ArrowMetadataIndex.

**Classes:**
- `MetadataSyncHandler`: Handler for metadata index synchronization using IPFS pubsub.

### metrics_manager.py

#### `metrics_manager.py`

**Classes:**
- `MetricsManager`

### mfs_enhanced.py

#### `mfs_enhanced.py`

Enhanced MFS (Mutable File System) operations for IPFS.

This module extends the basic MFS operations with advanced features such as:
1. Directory synchronization between local and IPFS MFS
2. Automatic content type detection
3. Transaction support for atomic operations 
4. Path utilities for MFS manipulation
5. Content monitoring and change tracking

**Classes:**
- `MFSTransaction`: Transaction support for atomic MFS operations.
- `DirectorySynchronizer`: Synchronizes content between a local directory and IPFS MFS.
- `ContentTypeDetector`: Detects content types for files in MFS.
- `PathUtils`: Utilities for working with MFS paths.
- `MFSChangeWatcher`: Watches for changes in MFS directories and files.

**Functions:**
- `compute_file_hash()`: Compute a hash for file content.
- `create_empty_directory_structure()`: Create a directory structure in MFS.
- `copy_content_batch()`: Perform a batch of copy operations in MFS.
- `move_content_batch()`: Perform a batch of move operations in MFS.
- `create_file_with_type()`: Create a file in MFS with specified content type.

### mfs_enhanced_resumable.py

#### `mfs_enhanced_resumable.py`

Enhanced MFS resumable operations for IPFS.

This module provides functionality for resumable file operations in the IPFS
Mutable File System, allowing read and write operations to be paused and resumed.
It implements a comprehensive permissions system to control access to files and
directories based on user identity, groups, and access control lists (ACLs).

Key features:
- Resumable file operations with chunked transfer
- Adaptive chunk sizing for optimal performance
- Parallel transfers for improved throughput
- UNIX-like permission model (read/write/execute)
- User and group-based access control
- Access Control Lists (ACLs) for fine-grained permissions
- Permission inheritance from parent directories
- Configurable permission enforcement

**Classes:**
- `FileChunk`: Represents a chunk of a file for resumable operations.
- `ResumableFileState`: Manages state for resumable file operations.
- `ResumableFileOperations`: Provides resumable file operations for IPFS MFS with permission management.
- `ResumableReadStream`: Provides a file-like object for resumable reading from IPFS MFS.
- `ResumableWriteStream`: Provides a file-like object for resumable writing to IPFS MFS.

### mfs_permissions.py

#### `mfs_permissions.py`

Permissions management for IPFS MFS operations.

This module provides a permission management system for controlling access
to files and directories in the IPFS Mutable File System (MFS). It implements
UNIX-like permissions with users, groups, and access control lists (ACLs).

**Classes:**
- `Permission`: Basic UNIX-style permissions.
- `FileType`: MFS file types.
- `UserPermission`: Permission for a specific user.
- `GroupPermission`: Permission for a specific group.
- `ACLEntry`: Access Control List entry for granular permissions.
- `FilePermissions`: Complete permissions for a file or directory.
- `PermissionManager`: Manages file and directory permissions for MFS.
- `AccessDeniedException`: Exception raised when a user does not have permission for an operation.

### migration_tools

#### `migration_tools/storacha_to_s3.py`

Migration tool for transferring content from Storacha to S3.

**Classes:**
- `storacha_to_s3`: Migration tool to transfer content from Storacha to S3.

#### `migration_tools/migration_cli.py`

Migration CLI - Command line interface for the MCP Migration Controller.

This tool provides command-line access to the Migration Controller for managing
cross-backend data migrations in the MCP system.

**Functions:**
- `format_size()`: Format byte size into human-readable string.
- `format_time()`: Format timestamp into human-readable string.
- `format_duration()`: Format duration between two timestamps.
- `print_task_details()`: Print detailed information about a migration task.
- `list_tasks_cmd()`: Handle the list tasks command.
- `get_task_cmd()`: Handle the get task command.
- `create_task_cmd()`: Handle the create task command.
- `cancel_task_cmd()`: Handle the cancel task command.
- `list_policies_cmd()`: Handle the list policies command.
- `add_policy_cmd()`: Handle the add policy command.
- `remove_policy_cmd()`: Handle the remove policy command.
- `apply_policy_cmd()`: Handle the apply policy command.
- `analyze_cost_cmd()`: Handle the analyze cost command.
- `get_stats_cmd()`: Handle the get statistics command.
- `find_optimal_backend_cmd()`: Handle the find optimal backend command.
- `main()`: Main entry point for the migration CLI.

#### `migration_tools/ipfs_to_s3.py`

Migration tool for transferring content from IPFS to S3.

**Classes:**
- `ipfs_to_s3`: Migration tool to transfer content from IPFS to S3.

#### `migration_tools/storacha_to_ipfs.py`

Migration tool for transferring content from Storacha to IPFS.

**Classes:**
- `storacha_to_ipfs`: Migration tool to transfer content from Storacha to IPFS.

#### `migration_tools/s3_to_storacha.py`

Migration tool for transferring content from S3 to Storacha/Web3.Storage.

This module provides utilities to migrate content from S3-compatible storage
to Storacha (Web3.Storage) for content-addressed storage.

**Classes:**
- `s3_to_storacha`: Migration tool to transfer content from S3 to Storacha.

#### `migration_tools/ipfs_to_storacha.py`

Migration tool for transferring content from IPFS to Storacha.

**Classes:**
- `ipfs_to_storacha`: Migration tool to transfer content from IPFS to Storacha.

#### `migration_tools/migration_controller.py`

Migration Controller for MCP server.

This module provides a unified interface for managing data migrations between
different storage backends in the MCP system. It implements advanced features like:
- Cross-backend data migration with policy-based management
- Cost-optimized storage placement
- Batch migration operations with monitoring and reporting
- Migration scheduling and prioritization
- Automatic verification and integrity checking

**Classes:**
- `MigrationPriority`: Priority levels for migrations.
- `MigrationStatus`: Status values for migration operations.
- `MigrationPolicy`: Defines policies for data migration between backends.
- `MigrationTask`: Represents a single migration task between backends.
- `MigrationController`: Controller for managing migrations between different storage backends.

#### `migration_tools/__init__.py`

Migration tools for transferring content between different storage backends.

This module provides utilities for migrating content between different storage
backends such as IPFS, S3, and Storacha (Web3.Storage).

Available migration tools:
- s3_to_storacha: Migrate content from S3 to Storacha/Web3.Storage
- storacha_to_s3: Migrate content from Storacha/Web3.Storage to S3
- ipfs_to_storacha: Migrate content from IPFS to Storacha/Web3.Storage
- storacha_to_ipfs: Migrate content from Storacha/Web3.Storage to IPFS
- s3_to_ipfs: Migrate content from S3 to IPFS
- ipfs_to_s3: Migrate content from IPFS to S3

Advanced migration management:
- migration_controller: Unified controller for cross-backend migrations
- migration_cli: Command-line interface for migration management

#### `migration_tools/s3_to_ipfs.py`

Migration tool for transferring content from S3 to IPFS.

**Classes:**
- `s3_to_ipfs`: Migration tool to transfer content from S3 to IPFS.

### modern_hybrid_mcp_dashboard.py

#### `modern_hybrid_mcp_dashboard.py`

Modern Hybrid MCP Dashboard - Merging Old & New Architectures

This implementation combines:
- Light initialization (no heavy imports)
- Bucket-based virtual filesystem
- ~/.ipfs_kit/ state management
- JSON RPC MCP protocol
- Refactored modular templates
- All original MCP functionality restored

**Classes:**
- `McpRequest`: MCP protocol request format.
- `McpResponse`: MCP protocol response format.
- `ModernHybridMCPDashboard`: Modern Hybrid MCP Dashboard combining:

**Functions:**
- `main()`: Main entry point for standalone usage.

### observability_api.py

#### `observability_api.py`

Observability API for IPFS Kit

This module provides a FastAPI router for accessing observability features
in IPFS Kit, including metrics, logging, and tracing.

Features:
- Metrics collection and retrieval
- Log level management and log searching
- Distributed tracing configuration
- Health checks and status monitoring

### openapi_schema.py

#### `openapi_schema.py`

OpenAPI schema for the IPFS Kit API.

This module defines the OpenAPI schema for the REST API server,
providing a structured definition of all available endpoints,
request and response formats, and data models.

**Functions:**
- `get_openapi_schema()`: Returns the OpenAPI schema for the REST API server.

### parquet_car_bridge.py

#### `parquet_car_bridge.py`

Parquet to CAR Archive Bridge for IPFS Kit.

This module provides functionality to convert between Parquet files and IPLD CAR archives,
enabling columnar data to be content-addressed and shared through IPFS networks.

Features:
1. Convert Parquet files to IPLD CAR archives
2. Convert CAR archives back to Parquet files
3. Maintain metadata and schema information
4. Support for partitioned datasets
5. Integration with vector indices and knowledge graphs
6. Dashboard API endpoints for monitoring and querying

**Classes:**
- `ParquetCARBridge`: Bridge for converting between Parquet files and IPLD CAR archives.

### parquet_data_reader.py

#### `parquet_data_reader.py`

Parquet Data Access Layer for IPFS-Kit CLI

This module provides content-addressed, lock-free access to IPFS-Kit data
stored in Parquet format. Designed to avoid database lock conflicts while
providing real-time access to pins, WAL operations, and FS journal data.

**Classes:**
- `ParquetDataReader`: Lock-free data access using Parquet files as the source of truth.

**Functions:**
- `get_parquet_reader()`: Get global Parquet data reader instance.

### parquet_ipld_bridge.py

#### `parquet_ipld_bridge.py`

Complete Parquet-IPLD Bridge Implementation (Protobuf-Conflict-Free)

This is a fully working implementation of the Parquet-IPLD bridge that avoids
all protobuf conflicts while providing complete functionality.

**Classes:**
- `IPFSError`: Custom IPFS error.
- `MockIPLDExtension`: Mock IPLD extension to avoid protobuf conflicts.
- `MockTieredCacheManager`: Mock cache manager.
- `MockStorageWriteAheadLog`: Mock WAL manager.
- `MockMetadataReplicationManager`: Mock replication manager.
- `MockArrowMetadataIndex`: Mock metadata index.
- `ParquetIPLDBridge`: Protobuf-Safe Parquet-IPLD Bridge.

**Functions:**
- `create_result_dict()`: Create standardized result dictionary.
- `handle_error()`: Handle and log errors consistently.

### parquet_ipld_bridge_backup.py

#### `parquet_ipld_bridge_backup.py`

Parquet-IPLD Bridge for IPFS Kit.

This module implements a bridge between Apache Parquet/Arrow storage and IPLD 
content addressing, enabling Parquet datasets to be stored and retrieved as 
IPLD-addressable content within the tiered storage hierarchy.

Key features:
1. Parquet datasets as IPLD-addressable content
2. Content-addressed Parquet partitions
3. Integration with existing tiered cache and VFS
4. Arrow-optimized data pipelines
5. Metadata indexing with fast queries
6. Replication and WAL integration

This bridge enables efficient storage of structured data (DataFrames, tables)
while maintaining IPFS content addressing and distributed storage benefits.

**Classes:**
- `ParquetIPLDBridge`: Bridge between Parquet/Arrow storage and IPLD content addressing.
- `IPFSError`
- `IPLDExtension`
- `TieredCacheManager`
- `StorageWriteAheadLog`
- `MetadataReplicationManager`
- `ArrowMetadataIndex`

### parquet_ipld_bridge_safe.py

#### `parquet_ipld_bridge_safe.py`

Complete Parquet-IPLD Bridge Implementation (Protobuf-Conflict-Free)

This is a fully working implementation of the Parquet-IPLD bridge that avoids
all protobuf conflicts while providing complete functionality.

**Classes:**
- `IPFSError`: Custom IPFS error.
- `MockIPLDExtension`: Mock IPLD extension to avoid protobuf conflicts.
- `MockTieredCacheManager`: Mock cache manager.
- `MockStorageWriteAheadLog`: Mock WAL manager.
- `MockMetadataReplicationManager`: Mock replication manager.
- `MockArrowMetadataIndex`: Mock metadata index.
- `ParquetIPLDBridge`: Protobuf-Safe Parquet-IPLD Bridge.

**Functions:**
- `create_result_dict()`: Create standardized result dictionary.
- `handle_error()`: Handle and log errors consistently.

### parquet_manager.py

#### `parquet_manager.py`

**Classes:**
- `ParquetManager`

### parquet_vfs_integration.py

#### `parquet_vfs_integration.py`

Parquet VFS Integration for IPFS Kit.

This module integrates the Parquet-IPLD bridge with the Virtual File System,
enabling structured data to be accessed through filesystem operations while
maintaining all the benefits of content addressing, caching, and replication.

Features:
1. Mount Parquet datasets as virtual filesystems
2. SQL query interface through VFS paths
3. Automatic integration with tiered caching
4. Write-ahead logging for dataset operations
5. Metadata replication across storage tiers
6. Arrow-optimized data pipelines

**Classes:**
- `ParquetVirtualFileSystem`: Virtual filesystem interface for Parquet-IPLD bridge.
- `ParquetVFSFile`: File-like object for Parquet VFS operations.

**Functions:**
- `create_parquet_vfs_integration()`: Create integrated Parquet-IPLD bridge and VFS.
- `store_dataframe_to_ipfs()`: Convenience function to store a DataFrame to IPFS via Parquet.
- `retrieve_dataframe_from_ipfs()`: Convenience function to retrieve a DataFrame from IPFS.
- `mount_parquet_vfs()`: Mount Parquet VFS at specified mount point.

### peer_manager.py

#### `peer_manager.py`

**Classes:**
- `PeerManager`

### peer_websocket.py

#### `peer_websocket.py`

WebSocket-based peer discovery for IPFS Kit.

This module enables finding and connecting to IPFS peers using WebSockets.
It provides both server and client functionality:
1. Server: Advertises local peer information over WebSockets
2. Client: Discovers and connects to remote peers over WebSockets

This enables easier NAT traversal and peer discovery compared to traditional
IPFS peer discovery methods, especially in environments where direct connections
are difficult due to firewalls or NAT.

**Classes:**
- `MessageType`: Types of peer discovery messages.
- `PeerRole`: Peer roles in the network.
- `PeerInfo`: Information about a peer in the network.
- `PeerWebSocketServer`: WebSocket server for peer discovery.
- `PeerWebSocketClient`: WebSocket client for peer discovery.

**Functions:**
- `register_peer_websocket()`: Register peer WebSocket endpoint with FastAPI.
- `create_peer_info_from_ipfs_kit()`: Create a PeerInfo object from an IPFS Kit instance.

### peer_websocket_anyio.py

#### `peer_websocket_anyio.py`

WebSocket-based peer discovery for IPFS Kit.

This module enables finding and connecting to IPFS peers using WebSockets.
It provides both server and client functionality:
1. Server: Advertises local peer information over WebSockets
2. Client: Discovers and connects to remote peers over WebSockets

This enables easier NAT traversal and peer discovery compared to traditional
IPFS peer discovery methods, especially in environments where direct connections
are difficult due to firewalls or NAT.

This implementation uses anyio for backend-agnostic async operations.

**Classes:**
- `MessageType`: Types of peer discovery messages.
- `PeerRole`: Peer roles in the network.
- `PeerInfo`: Information about a peer in the network.
- `PeerWebSocketServer`: WebSocket server for peer discovery.
- `PeerWebSocketClient`: WebSocket client for peer discovery.

**Functions:**
- `register_peer_websocket()`: Register peer WebSocket endpoint with FastAPI.
- `create_peer_info_from_ipfs_kit()`: Create a PeerInfo object from an IPFS Kit instance.

### performance_metrics.py

#### `performance_metrics.py`

Performance metrics tracking and profiling for IPFS operations.

This module provides comprehensive utilities for tracking, profiling, and analyzing
performance metrics like latency, bandwidth usage, cache efficiency, and resource
utilization for IPFS operations.

**Classes:**
- `PerformanceMetrics`: Tracks and analyzes performance metrics for IPFS operations.
- `ProfilingContext`: Context manager for profiling sections of code.

**Functions:**
- `profile()`: Decorator for profiling functions.

### pin_manager.py

#### `pin_manager.py`

**Classes:**
- `PinManager`

### pin_metadata_index.py

#### `pin_metadata_index.py`

Pin Metadata Index for IPFS Kit - Parquet-based IPLD-Compatible Storage

This module provides a unified pin metadata index with IPLD/CAR export capabilities.
Uses DuckDB + Parquet for efficient analytical queries and IPFS-compatible storage.

Key Features:
- DuckDB-powered analytical queries for traffic metrics
- Parquet columnar storage with IPLD/CAR export capability
- Virtual filesystem integration for seamless CLI/API access
- Background synchronization with filesystem journal
- Multi-tier storage tracking and analytics
- Export to IPFS CAR files via IPLD

Usage:
    from ipfs_kit_py.pin_metadata_index import get_global_pin_metadata_index
    
    # Get the global index (integrates with filesystem)
    index = get_global_pin_metadata_index()
    
    # Access from CLI, API, or dashboard
    metrics = index.get_comprehensive_metrics()
    pin_info = index.get_pin_details(cid)
    
    # Export to IPLD/CAR
    car_file = index.export_to_car('pins_backup.car')

**Classes:**
- `EnhancedPinMetadata`: Enhanced pin metadata with virtual filesystem integration.
- `ComprehensiveTrafficMetrics`: Comprehensive traffic metrics with VFS and storage tier analytics.
- `PinMetadataIndex`: Pin metadata index with virtual filesystem integration.

**Functions:**
- `get_global_pin_metadata_index()`: Get or create the global enhanced pin metadata index.
- `get_cli_pin_metrics()`: Get pin metrics for CLI usage.

### pin_wal.py

#### `pin_wal.py`

Enhanced Pin Write-Ahead Log (WAL) system with CAR format support.

This module provides a specialized WAL for pin operations using CAR files
instead of JSON files for better IPFS integration and performance.

**Classes:**
- `PinOperationType`: Types of pin operations supported by the WAL.
- `PinOperationStatus`: Status values for pin operations in the WAL.
- `EnhancedPinWAL`: Enhanced Write-Ahead Log for pin operations using CAR format.

**Functions:**
- `get_global_pin_wal()`: Get or create the global Enhanced Pin WAL instance.

### pins.py

#### `pins.py`

Enhanced Pin Metadata Index for IPFS Kit - Parquet-based Virtual Filesystem Integration

This module provides a unified pin metadata index that integrates with ipfs_kit_py's
virtual filesystem, storage backends, and hierarchical storage management. It uses
DuckDB + Parquet for efficient analytical queries and storage.

Key Features:
- Integration with IPFSFileSystem and hierarchical storage
- DuckDB-powered analytical queries for traffic metrics
- Parquet columnar storage for efficiency
- Virtual filesystem integration for seamless CLI/API access
- Background synchronization with filesystem journal
- Multi-tier storage tracking and analytics

Usage:
    from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
    
    # Get the global index (integrates with filesystem)
    index = get_global_enhanced_pin_index()
    
    # Access from CLI, API, or dashboard
    metrics = index.get_comprehensive_metrics()
    pin_info = index.get_pin_details(cid)

**Classes:**
- `EnhancedPinMetadata`: Enhanced pin metadata with virtual filesystem integration.
- `ComprehensiveTrafficMetrics`: Comprehensive traffic metrics with VFS and storage tier analytics.
- `EnhancedPinMetadataIndex`: Enhanced pin metadata index with virtual filesystem integration.

**Functions:**
- `get_global_enhanced_pin_index()`: Get or create the global enhanced pin metadata index.
- `get_cli_pin_metrics()`: Get pin metrics for CLI usage.

### predictive_cache_manager.py

#### `predictive_cache_manager.py`

**Classes:**
- `PredictiveCacheManager`: Intelligent cache manager with predictive capabilities.

### predictive_prefetching.py

#### `predictive_prefetching.py`

Optimized Predictive Prefetching Module for IPFS Content.

This module implements enhanced predictive algorithms for optimizing content 
access patterns in IPFS-based distributed storage. It provides sophisticated
prefetching strategies based on:

1. Access pattern analysis with Markov models
2. Content relationships (graph-based)
3. Semantic analysis of content types
4. Machine learning prediction models
5. Context-aware workload detection

**Classes:**
- `MarkovPrefetchModel`: Advanced Markov Chain model for content access prediction.
- `GraphRelationshipModel`: Graph-based relationship model for content relationship analysis.
- `ContentTypeAnalyzer`: Analyzes content types for type-specific prefetching strategies.
- `PredictivePrefetchingEngine`: Advanced predictive prefetching engine using multiple prediction models.

**Functions:**
- `create_prefetching_engine()`: Create and configure a predictive prefetching engine.
- `get_prefetch_candidates()`: Convenience function to get prefetch candidates for a content item.

### program_state.py

#### `program_state.py`

IPFS Kit Program State Storage

This module provides a lightweight program state storage system using Parquet and DuckDB.
It stores essential system state that can be quickly accessed without importing heavy
dependencies or invoking storage backends.

Features:
- Fast read/write access to program state
- No heavy dependencies required for reading
- Separate from logs and config
- Thread-safe operations
- Automatic state updates from daemon
- CLI and MCP server can read without backend invocation

State Categories:
- System: Basic system information (bandwidth, peers, version)
- Files: File listings and metadata
- Storage: Storage backend status and metrics
- Network: Network connectivity and peer information
- Performance: System performance metrics

**Classes:**
- `SystemState`: System-level state information
- `FileState`: File system state information
- `StorageState`: Storage backend state information
- `NetworkState`: Network connectivity state information
- `ProgramStateManager`: Lightweight program state manager using SQLite for fast access.
- `FastStateReader`: Minimal dependency reader for program state.

**Functions:**
- `get_program_state_manager()`: Get the global program state manager instance
- `get_fast_state_reader()`: Get a fast state reader for minimal dependency access

### prometheus_exporter.py

#### `prometheus_exporter.py`

Prometheus metrics exporter for IPFS Kit.

This module provides a comprehensive Prometheus metrics exporter for IPFS Kit that exposes
various performance metrics from the PerformanceMetrics class in a format
that can be scraped by Prometheus.

The exporter integrates with the existing performance_metrics module and
exposes metrics via a dedicated HTTP endpoint that follows the Prometheus
exposition format. It includes specialized metrics for IPFS operations,
content management, and distributed state.

**Classes:**
- `IPFSMetricsCollector`: IPFS-specific metrics collector that provides additional metrics
- `PrometheusExporter`: Exports IPFS Kit metrics in Prometheus format.
- `Counter`
- `Gauge`
- `Histogram`
- `Summary`
- `Info`
- `CollectorRegistry`
- `GaugeMetricFamily`
- `CounterMetricFamily`

**Functions:**
- `add_prometheus_metrics_endpoint()`: Add a Prometheus metrics endpoint to a FastAPI application.

### resource_cli_fast.py

#### `resource_cli_fast.py`

Resource Tracking CLI - Fast Index Integration

This module provides CLI commands for monitoring bandwidth and storage consumption
across remote filesystem backends using the fast index system.

**Functions:**
- `register_resource_commands()`: Register resource tracking commands with the CLI parser.

### resource_management.py

#### `resource_management.py`

Resource management module for optimizing thread and memory usage in IPFS Kit.

This module provides sophisticated resource monitoring and management capabilities
to optimize performance in resource-constrained environments while maximizing
throughput when resources are abundant.

**Classes:**
- `ResourceMonitor`: Monitors system resources and provides adaptive resource management.
- `AdaptiveThreadPool`: Thread pool that adapts to system resource conditions.
- `ResourceAdapter`: Adapter to apply resource-aware settings to other components.

### resource_manager.py

#### `resource_manager.py`

**Classes:**
- `ResourceManager`

### resource_tracker.py

#### `resource_tracker.py`

Resource Tracker - Bandwidth and Storage Monitoring for Remote Filesystem Backends

This module provides comprehensive tracking of resource consumption across all
remote filesystem backends using the fast index system. It monitors:
- Bandwidth usage (upload/download)
- Storage consumption
- Operation costs
- Performance metrics

Storage Location: ~/.ipfs_kit/resource_tracking/
Index Database: ~/.ipfs_kit/resource_tracking/resource_tracker.db (SQLite)
Metrics Data: ~/.ipfs_kit/resource_tracking/metrics/ (partitioned by date/backend)

Dependencies: Only built-in Python modules + sqlite3

**Classes:**
- `ResourceType`: Types of resources being tracked.
- `BackendType`: Supported backend types.
- `ResourceMetric`: Represents a single resource measurement.
- `FastResourceTracker`: Ultra-fast resource tracker using SQLite index.

**Functions:**
- `get_resource_tracker()`: Get the global resource tracker instance.
- `track_bandwidth_upload()`: Track bandwidth upload usage.
- `track_bandwidth_download()`: Track bandwidth download usage.
- `track_storage_usage()`: Track storage usage.
- `track_api_call()`: Track API call usage.

### resource_tracking_decorators.py

#### `resource_tracking_decorators.py`

Resource Tracking Decorators and Context Managers

This module provides decorators and context managers to automatically track
resource consumption for backend operations without modifying existing code.

**Classes:**
- `ResourceTrackingDecorator`: Decorator for automatic resource tracking in backend methods.
- `OperationTracker`: Helper class for tracking resources within an operation.

**Functions:**
- `track_operation()`: Context manager for tracking complex operations.
- `track_upload()`: Decorator for tracking upload operations.
- `track_download()`: Decorator for tracking download operations.
- `track_api()`: Decorator for tracking API calls.
- `track_storage()`: Decorator for tracking storage operations.

### routing

#### `routing/adaptive_optimizer.py`

Adaptive Optimizer for MCP Routing

This module provides an adaptive optimization system that combines multiple
routing factors to make intelligent routing decisions for content across
different storage backends.

Key features:
1. Multi-factor optimization based on content, network, geography, and cost
2. Adaptive weights that learn from past routing outcomes
3. Content-aware backend selection
4. Performance and cost analytics
5. Comprehensive routing insights

**Classes:**
- `OptimizationFactor`: Factors that influence routing optimization decisions.
- `OptimizationWeights`: Weights for different optimization factors.
- `RouteOptimizationResult`: Result of a route optimization decision.
- `LearningSystem`: Learning system that adjusts optimization weights based on outcomes.
- `AdaptiveOptimizer`: Adaptive optimizer that combines multiple routing factors to make

**Functions:**
- `create_adaptive_optimizer()`: Create an adaptive optimizer instance.

#### `routing/grpc_client.py`

gRPC Routing Service - DEPRECATED

This module has been deprecated due to protobuf version conflicts.
Use the HTTP API server instead: ipfs_kit_py.routing.http_server

For migration information, see: GRPC_DEPRECATION_NOTICE.md

**Classes:**
- `GRPCServer`
- `RoutingServiceServicer`
- `DeprecatedGRPCComponent`

**Functions:**

#### `routing/config_manager.py`

Configuration Management for the Routing System

This module handles loading, saving, and validating configurations
for the optimized data routing system.

**Classes:**
- `RoutingConfigManager`: Manager for routing system configuration.

**Functions:**
- `get_data_dir()`: Get the data directory for routing data.
- `get_cache_dir()`: Get the cache directory for routing.

#### `routing/optimized_router.py`

Optimized Data Routing Module for MCP Server

This module provides intelligent routing of data operations across different storage backends.
It implements content-aware backend selection, cost-based routing algorithms, geographic
optimization, and bandwidth/latency-based routing decisions.

Key features:
1. Content-aware backend selection based on file type, size, and access patterns
2. Cost-based routing algorithms to optimize for storage and retrieval costs
3. Geographic optimization to reduce latency and improve compliance
4. Bandwidth and latency analysis for adaptive routing decisions
5. Performance metrics collection and analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.

**Classes:**
- `ContentType`: Enum for content types with different routing strategies.
- `RoutingStrategy`: Enum for data routing strategies.
- `StorageClass`: Enum for storage classes with different cost and performance profiles.
- `GeographicRegion`: Enum for geographic regions for content placement.
- `ComplianceType`: Enum for compliance types affecting routing decisions.
- `BackendMetrics`: Performance and cost metrics for a storage backend.
- `RoutingPolicy`: Policy configuration for data routing decisions.
- `RoutingDecision`: Result of a routing decision for content placement or retrieval.
- `RouterGeolocation`: Helper class for geographic lookups and distance calculations.
- `ConnectivityAnalyzer`: Analyzes network connectivity to different backends to optimize routing.
- `ContentAnalyzer`: Analyzes content to determine optimal routing.
- `RouterMetricsCollector`: Collects and analyzes metrics for routing decisions.
- `OptimizedRouter`: Core router for optimizing data placement and retrieval across backends.

#### `routing/grpc_auth.py`

gRPC Routing Service - DEPRECATED

This module has been deprecated due to protobuf version conflicts.
Use the HTTP API server instead: ipfs_kit_py.routing.http_server

For migration information, see: GRPC_DEPRECATION_NOTICE.md

**Classes:**
- `GRPCServer`
- `RoutingServiceServicer`
- `DeprecatedGRPCComponent`

**Functions:**

#### `routing/arrow_ipc.py`

Apache Arrow IPC Implementation for Optimized Data Routing

This module provides integration between the optimized data routing system
and Apache Arrow for high-performance, language-independent data exchange.

**Classes:**
- `ArrowRoutingInterface`: Apache Arrow interface for optimized data routing.
- `ArrowIPCServer`: Apache Arrow IPC server for routing functionality.
- `ArrowIPCClient`: Apache Arrow IPC client for routing functionality.

#### `routing/grpc_server.py`

gRPC Routing Service - DEPRECATED

This module has been deprecated due to protobuf version conflicts.
Use the HTTP API server instead: ipfs_kit_py.routing.http_server

For migration information, see: GRPC_DEPRECATION_NOTICE.md

**Classes:**
- `GRPCServer`
- `RoutingServiceServicer`
- `DeprecatedGRPCComponent`

**Functions:**

#### `routing/data_router.py`

Optimized Data Routing Module

This module implements intelligent routing of data between storage backends:
- Content-aware backend selection based on data characteristics
- Cost-based routing algorithms to optimize for price vs performance
- Geographic routing for edge-optimized content delivery
- Bandwidth and latency analysis for network-aware decisions

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

**Classes:**
- `RoutingStrategy`: Strategies for routing data between backends.
- `RoutingPriority`: Priority levels for routing decisions.
- `ContentCategory`: Categories for different types of content.
- `BackendMetrics`: Performance and cost metrics for a storage backend.
- `RoutingRule`: Rule for routing content to specific backends.
- `ContentAnalyzer`: Analyzes content to determine its characteristics.
- `GeographicRouter`: Routes content based on geographic location.
- `CostOptimizer`: Optimizes content routing based on cost.
- `PerformanceOptimizer`: Optimizes content routing based on performance.
- `DataRouter`: Main data routing system that selects optimal storage backends.

**Functions:**
- `validate_routing_rule()`: Validate a routing rule configuration.
- `create_data_router()`: Create a data router instance.

#### `routing/http_server.py`

HTTP Routing API Server - Replacement for Deprecated gRPC Service

This HTTP REST API provides all routing functionality previously available
through gRPC, without protobuf dependencies or version conflicts.

**Classes:**
- `HTTPRoutingServer`: HTTP API server providing routing functionality without gRPC/protobuf.

#### `routing/standalone_grpc_server.py`

gRPC Routing Service - DEPRECATED

This module has been deprecated due to protobuf version conflicts.
Use the HTTP API server instead: ipfs_kit_py.routing.http_server

For migration information, see: GRPC_DEPRECATION_NOTICE.md

**Classes:**
- `GRPCServer`
- `RoutingServiceServicer`
- `DeprecatedGRPCComponent`

**Functions:**

#### `routing/router.py`

Core Router Implementation for Optimized Data Routing.

This module provides the main DataRouter class and supporting classes for
making intelligent routing decisions for data across different storage backends.

**Classes:**
- `BackendType`: Types of storage backends.
- `ContentType`: Types of content for routing decisions.
- `OperationType`: Types of operations for routing decisions.
- `RouteMetrics`: Metrics used for routing decisions.
- `RoutingContext`: Context for routing decisions.
- `RoutingDecision`: Result of a routing decision.
- `RoutingStrategy`: Abstract base class for routing strategies.
- `DataRouter`: Main router class for making intelligent routing decisions.

#### `routing/routing_manager.py`

Optimized Data Routing Manager for IPFS Kit

This module serves as the main entry point for the optimized data routing system,
integrating all components and providing a clean interface for routing data between
different storage backends.

It implements the "Optimized Data Routing" component:
- Content-aware backend selection
- Cost-based routing algorithms
- Geographic optimization
- Bandwidth and latency analysis

**Classes:**
- `RoutingManagerSettings`: Settings for the Routing Manager.
- `MetricsCollector`: Collects and aggregates metrics for routing optimization.
- `RoutingManager`: Central manager for the optimized data routing system.

**Functions:**
- `get_routing_manager()`: Get the singleton routing manager instance.
- `register_routing_manager()`: Register the routing manager with a FastAPI app.

#### `routing/__init__.py`

IPFS Kit Optimized Data Routing Module

This module provides optimized data routing capabilities for efficient content placement,
retrieval, and management across multiple storage backends.

Core features:
- Content-aware backend selection
- Cost-based routing algorithms
- Geographic optimization 
- Bandwidth and latency analysis
- Metrics collection and analysis
- Dashboard for monitoring and managing routing

This module can be used independently or integrated with the MCP server.

#### `routing/metrics_collector.py`

Metrics Collection and Analysis for Routing System

This module provides metrics collection, storage, and analysis capabilities
for the optimized data routing system, tracking performance, success rates,
and other key metrics to inform routing decisions.

**Classes:**
- `RoutingMetricsDatabase`: SQLite database for storing routing metrics.
- `RoutingMetricsCollector`: Collector for routing metrics.

#### `routing/dashboard/__init__.py`

Routing Dashboard Entry Point

This module provides a simplified interface for creating and running
the routing dashboard as a standalone application.

**Classes:**
- `DashboardSettings`: Settings for the routing dashboard.

**Functions:**
- `create_dashboard_app()`: Create the routing dashboard FastAPI application.
- `run_dashboard()`: Run the routing dashboard (blocking).

#### `routing/grpc/routing_pb2_grpc.py`

Client and server classes corresponding to protobuf-defined services.

**Classes:**
- `RoutingServiceStub`: Routing service definition
- `RoutingServiceServicer`: Routing service definition
- `RoutingService`: Routing service definition

**Functions:**
- `add_RoutingServiceServicer_to_server()`

#### `routing/grpc/routing_pb2.py`

Generated protocol buffer code.

#### `routing/grpc/__init__.py`

gRPC protobuf modules deprecated - use HTTP API

#### `routing/algorithms/geographic.py`

Geographic Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on geographic location to minimize latency and comply with data residency requirements.

**Classes:**
- `GeographicRouter`: Routing strategy that selects backends based on geographic considerations.

#### `routing/algorithms/composite.py`

Composite Routing Strategy.

This module provides a composite routing strategy that combines multiple
other strategies with configurable weights to make balanced routing decisions.

**Classes:**
- `CompositeRouter`: Combines multiple routing strategies with weighted scoring.

#### `routing/algorithms/content_aware.py`

Content-Aware Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on the type and characteristics of the content being stored or retrieved.

**Classes:**
- `ContentAwareRouter`: Routing strategy that selects backends based on content characteristics.

#### `routing/algorithms/cost_based.py`

Cost-Based Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on cost metrics such as storage cost, retrieval cost, and operation cost.

**Classes:**
- `CostBasedRouter`: Routing strategy that selects backends based on cost considerations.

#### `routing/algorithms/performance.py`

Performance-Based Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on performance metrics such as latency, throughput, and availability.

**Classes:**
- `PerformanceRouter`: Routing strategy that selects backends based on performance metrics.

#### `routing/algorithms/__init__.py`

Routing Algorithms for Optimized Data Routing.

This module provides various routing strategies for selecting the optimal
storage backend based on different criteria such as content type, cost,
geographic location, and performance metrics.

#### `routing/grpc_deprecated_backup/routing_pb2_grpc.py`

Client and server classes corresponding to protobuf-defined services.

**Classes:**
- `RoutingServiceStub`: Routing service definition
- `RoutingServiceServicer`: Routing service definition
- `RoutingService`: Routing service definition

**Functions:**
- `add_RoutingServiceServicer_to_server()`

#### `routing/grpc_deprecated_backup/routing_pb2.py`

Generated protocol buffer code.

#### `routing/grpc_deprecated_backup/__init__.py`

gRPC interface for optimized data routing.

### run_mcp_server_real_storage.py

#### `run_mcp_server_real_storage.py`

MCP server implementation with real (non-simulated) storage backends.

This server integrates with actual storage services rather than using simulations,
providing full functionality for all storage backends:
- Hugging Face
- Storacha
- Filecoin
- Lassie
- S3

**Functions:**
- `create_app()`: Create and configure the FastAPI app with MCP server.
- `write_pid()`: Write the current process ID to a file.

### s3_kit.py

#### `s3_kit.py`

**Classes:**
- `s3_kit`

### secure_config.py

#### `secure_config.py`

Secure Configuration Storage Module

Provides encrypted storage for sensitive configuration data (credentials, API keys, etc.)
using Fernet symmetric encryption from the cryptography library.

Features:
- Automatic encryption/decryption of sensitive fields
- Secure key management in ~/.ipfs_kit/.keyring/
- Backward compatibility with plain JSON
- Key rotation support
- Automatic migration from plain to encrypted format
- File permissions management (0o600)

Usage:
    from ipfs_kit_py.secure_config import SecureConfigManager
    
    manager = SecureConfigManager()
    
    # Save encrypted config
    config = {
        "backends": {
            "s3_main": {
                "config": {
                    "access_key": "AKIA...",
                    "secret_key": "secret123"
                }
            }
        }
    }
    manager.save_config("backends.json", config)
    
    # Load and decrypt config
    loaded_config = manager.load_config("backends.json")

**Classes:**
- `SecureConfigManager`: Manager for secure configuration storage with encryption.

**Functions:**
- `save_secure_config()`: Save configuration with encryption (convenience function).
- `load_secure_config()`: Load configuration with decryption (convenience function).

### service_manager.py

#### `service_manager.py`

**Classes:**
- `ServiceManager`

### service_registry.py

#### `service_registry.py`

Service Registry for IPFS Kit

This module provides a centralized registry for managing storage and infrastructure services.
It replaces the incorrect services mentioned in the issue (cars, docker, kubectl) with
proper storage services like IPFS, S3, Storacha, etc.

**Classes:**
- `ServiceType`: Types of services supported by IPFS Kit.
- `ServiceStatus`: Service status states.
- `ServiceInterface`: Protocol defining the interface all services must implement.
- `BaseService`: Base class for all services.
- `StorageServiceMixin`: Mixin for storage services.
- `NetworkServiceMixin`: Mixin for network services.
- `IPFSService`: IPFS storage service.
- `IPFSClusterService`: IPFS Cluster service.
- `S3Service`: S3 storage service.
- `StorachaService`: Storacha (Web3.Storage) service.
- `HuggingFaceService`: HuggingFace Hub service.
- `ServiceRegistry`: Registry for managing all services.

**Functions:**
- `get_service_registry()`: Get the global service registry instance.

### services

#### `services/state_service.py`

StateService - Shared lightweight service for MCP/CLI parity

Provides a unified, light-initialization API to read/write program and daemon
state from the IPFS Kit data directory (default: ~/.ipfs_kit). Avoids heavy
imports and focuses on file-based state and simple system introspection so it
can be safely used by both the CLI and the MCP server tools.

**Classes:**
- `StateService`

### simple_bucket_cli.py

#### `simple_bucket_cli.py`

Simple Bucket CLI handlers.
Uses the SimpleBucketManager for clean VFS index-based operations.

**Functions:**
- `print_bucket_table()`: Print buckets in a formatted table.
- `print_files_table()`: Print files in a formatted table.

### simple_bucket_manager.py

#### `simple_bucket_manager.py`

Simplified Bucket Manager for IPFS Kit.

This implements the correct bucket architecture:
- Buckets are just VFS indexes (parquet files)
- File additions append to VFS index with CID and metadata
- File contents go to WAL as parquet files named by CID
- No complex folder structures

**Classes:**
- `SimpleBucketManager`: Simplified bucket manager following the correct architecture.

**Functions:**
- `get_simple_bucket_manager()`: Get global simple bucket manager instance.

### simple_pin_cli.py

#### `simple_pin_cli.py`

Simplified PIN CLI handlers.

This implements PIN CLI commands using the simplified PIN manager
that follows the correct architecture (like bucket system).

**Functions:**
- `print_pin_table()`: Print pins in a formatted table.
- `print_pending_operations_table()`: Print pending operations in a formatted table.

### simple_pin_manager.py

#### `simple_pin_manager.py`

Simplified PIN Manager for IPFS Kit.

This implements the correct PIN architecture matching the bucket system:
- PIN operations append to VFS index (parquet files)
- File additions store content in CAR WAL using CAR format
- CID calculation using ipfs_multiformats.py BEFORE metadata addition
- Simple append-only operations using CAR WAL manager

**Classes:**
- `SimplePinManager`: Simplified PIN manager following the correct architecture with CAR WAL.

**Functions:**
- `get_simple_pin_manager()`: Get global simple PIN manager instance.

### simulated_api.py

#### `simulated_api.py`

Simplified high_level_api module containing just the essential IPFSSimpleAPI class.
This is a temporary fix to allow the MCP server to run.

**Classes:**
- `IPFSSimpleAPI`: Simplified version of IPFSSimpleAPI for MCP server compatibility.

### sshfs_backend.py

#### `sshfs_backend.py`

SSHFS Storage Backend for IPFS-Kit

This module implements an SSHFS (SSH Filesystem) storage backend that allows
IPFS-Kit to use remote SSH/SCP servers as storage destinations. It provides
seamless integration with SSH-accessible systems, supporting both key-based
and password authentication.

Features:
- SSH key-based and password authentication
- Automatic connection pooling and retry logic
- Parallel file operations
- Directory synchronization
- Remote path mapping and management
- Connection health monitoring
- Bandwidth throttling support

**Classes:**
- `StorageBackend`: Base storage backend class.
- `SSHFSConfig`: Configuration for SSHFS backend.
- `SSHFSFileInfo`: Information about a file on the SSHFS backend.
- `SSHFSConnection`: Manages a single SSH connection with SCP capabilities.
- `SSHFSConnectionPool`: Pool of SSH connections for efficient resource management.
- `SSHFSBackend`: SSHFS storage backend implementation.

**Functions:**
- `create_sshfs_backend()`: Create and return an SSHFS backend instance.

### sshfs_kit.py

#### `sshfs_kit.py`

SSHFS Kit - SSH/SCP storage backend for IPFS-Kit

This module provides SSHFS (SSH Filesystem) support as a storage backend,
allowing file storage and retrieval over SSH/SCP protocols with virtual
filesystem integration.

Key Features:
- SSH key-based authentication
- SCP file transfer operations
- Remote directory management
- Integration with VFS buckets
- Support for both file paths and CID storage

**Classes:**
- `SSHFSKit`: SSHFS storage backend for IPFS-Kit virtual filesystem.

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `create_sshfs_kit()`: Create an SSHFSKit instance from configuration.

### state_cli.py

#### `state_cli.py`

IPFS Kit Program State CLI

A lightweight CLI tool for accessing program state without heavy dependencies.
This tool can quickly retrieve system status, file counts, bandwidth info, etc.
from the program state storage.

Usage:
    ipfs-kit-state --summary                    # Show overall state summary
    ipfs-kit-state --system                     # Show system metrics
    ipfs-kit-state --files                      # Show file statistics  
    ipfs-kit-state --storage                    # Show storage backend status
    ipfs-kit-state --network                    # Show network status
    ipfs-kit-state --get key                    # Get specific state value
    ipfs-kit-state --json                       # Output in JSON format

**Functions:**
- `print_summary()`: Print state summary
- `print_detailed_state()`: Print detailed state for a specific category
- `main()`

### state_cli_lightweight.py

#### `state_cli_lightweight.py`

Lightweight entry point for IPFS Kit state commands only.
This avoids importing the heavy CLI module and dependencies.

**Functions:**
- `handle_state_command_lightweight()`: Handle state command without importing heavy dependencies.
- `format_output_lightweight()`: Format output for state commands.
- `main()`: Main entry point for lightweight state CLI.

### storacha_kit.py

#### `storacha_kit.py`

Enhanced Storacha Kit for IPFS Kit.

This module provides comprehensive integration with Storacha (formerly Web3.Storage)
with robust endpoint management, connection handling, and fallback mechanisms.

**Classes:**
- `IPFSValidationError`: Error when input validation fails.
- `IPFSContentNotFoundError`: Content with specified CID not found.
- `IPFSConnectionError`: Error when connecting to services.
- `IPFSError`: Base class for all IPFS-related exceptions.
- `IPFSTimeoutError`: Timeout when communicating with services.
- `StorachaConnectionError`: Error when connecting to Storacha services.
- `StorachaAuthenticationError`: Error with Storacha authentication.
- `StorachaAPIError`: Error with Storacha API.
- `storacha_kit`

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### storage_backends_api.py

#### `storage_backends_api.py`

Storage Backends API for IPFS Kit

This module provides a FastAPI router for managing and interacting with
various storage backends in IPFS Kit.

Available storage backends:
- IPFS (default) - InterPlanetary File System
- S3 - Amazon S3 and compatible object storage
- Storacha - Formerly Web3.Storage
- HuggingFace - AI model and dataset storage
- Filecoin - Decentralized storage network
- Lassie - Retrieval client for IPFS/Filecoin

### storage_wal.py

#### `storage_wal.py`

**Classes:**
- `OperationType`: Types of operations that can be stored in the WAL.
- `OperationStatus`: Status values for WAL operations.
- `BackendType`: Types of storage backends.
- `StorageWriteAheadLog`: Write-ahead log for IPFS storage operations.
- `BackendHealthMonitor`: Monitor health of storage backends.

### streaming_security.py

#### `streaming_security.py`

Streaming Security module for IPFS Kit.

This module provides security mechanisms for WebRTC and WebSocket streaming, 
including authentication, authorization, encryption, and secure signaling.

Key features:
1. Authentication: User-based authentication for streaming connections
2. Authorization: Content-specific access control
3. Token-based Security: JWT-based authentication for streaming
4. Encryption: Content encryption for sensitive media
5. Secure Signaling: Protection for WebRTC signaling
6. Audit Logging: Comprehensive logging of streaming access
7. Rate Limiting: Prevention of abuse through rate limiting
8. SOP/CORS Protection: Security for browser-based clients

**Classes:**
- `SecurityLevel`: Security levels for different types of content.
- `AuthType`: Authentication types for streaming connections.
- `StreamingSecurityManager`: Central manager for all streaming security features.
- `WebRTCContentSecurity`: Security utilities for WebRTC content streaming.
- `SecurityMiddleware`: FastAPI middleware for streaming security.
- `TokenSecurity`: Token-based security for FastAPI endpoints.

### streaming_security_integration.py

#### `streaming_security_integration.py`

Streaming Security Integration for IPFS Kit.

This module integrates the streaming security features with the existing WebRTC streaming 
and WebSocket notification systems, providing a secure streaming solution.

Key integrations:
1. Secure WebRTC Streaming: Authentication and access control for WebRTC streams
2. Secure WebSocket Notifications: Protected real-time notifications
3. Security Middleware: FastAPI middleware for security headers and rate limiting
4. Token Authentication: JWT-based authentication for API endpoints
5. Authorization Framework: Content-specific access control

**Classes:**
- `SecureIPFSMediaStreamTrack`: MediaStreamTrack that securely sources content from IPFS with encryption support.
- `SecureStreamingIntegration`: FastAPI integration for secure streaming.

**Functions:**
- `filter_notification_types_by_role()`: Filter notification types based on user role and permissions.
- `filter_notification_types_for_anonymous()`: Filter notification types for anonymous users.
- `sanitize_notification_data()`: Remove sensitive information from notification data.

### synapse_kit.py

#### `synapse_kit.py`

Synapse Kit for IPFS Kit.

This module provides comprehensive integration with Synapse SDK for Filecoin
with robust connection handling, dependency management, and service control.

**Classes:**
- `SynapseError`: Base class for Synapse-related exceptions.
- `SynapseConnectionError`: Error when connecting to Synapse services.
- `SynapseInstallationError`: Error during Synapse installation.
- `SynapseConfigurationError`: Error with Synapse configuration.
- `synapse_kit`

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle errors in a standardized way.

### synapse_storage.py

#### `synapse_storage.py`

Synapse SDK storage interface for ipfs_kit_py.

This module provides the main storage interface for the Synapse SDK integration,
enabling decentralized storage operations on Filecoin with Proof of Data Possession (PDP).

The module includes:
- Core storage operations (upload/download)
- Payment management and automation
- Provider selection and management
- PDP verification and monitoring
- Integration with existing IPFS Kit patterns

Usage:
    from synapse_storage import synapse_storage
    
    storage = synapse_storage(metadata={
        "network": "calibration",
        "private_key": "0x...",
        "auto_approve": True
    })
    
    # Store data
    result = await storage.synapse_store_data(data)
    
    # Retrieve data
    data = await storage.synapse_retrieve_data(result["commp"])

**Classes:**
- `SynapseError`: Base class for Synapse SDK related exceptions.
- `SynapseConnectionError`: Error connecting to Synapse services.
- `SynapsePaymentError`: Error with payment operations.
- `SynapsePDPError`: Error with PDP operations.
- `SynapseConfigurationError`: Error with Synapse configuration.
- `JavaScriptBridge`: Bridge for communicating with JavaScript Synapse SDK wrapper.
- `synapse_storage`: Main storage interface for Synapse SDK integration.

**Functions:**
- `create_result_dict()`: Create a standardized result dictionary.
- `handle_error()`: Handle error and update result dict.

### tiered_cache.py

#### `tiered_cache.py`

Tiered Cache System for IPFS - Backward Compatibility Module.

This module provides backward compatibility for the tiered caching system 
which has been split into separate files. It re-exports the core classes
from their new locations.

### tiered_cache_manager.py

#### `tiered_cache_manager.py`

**Classes:**
- `TieredCacheManager`: Manages hierarchical caching with Adaptive Replacement policy.

### tiered_storage_integration.py

#### `tiered_storage_integration.py`

Tiered Storage Integration Module.

This module integrates the TieredCacheManager with various storage backends:
- S3
- Storacha
- Filecoin
- HuggingFace
- Lassie
- IPFS

It provides a unified interface to move content between storage tiers seamlessly,
leveraging the MCP storage models for backend operations.

**Classes:**
- `TieredStorageIntegrator`: Integrates TieredCacheManager with backend storage models.

**Functions:**
- `move_content_between_tiers()`: Move content between storage tiers using a functional API.

### tools

#### `tools/check_api_compatibility.py`

Check API compatibility between IPFS Kit versions.

This tool compares the current API with a previous version to detect potential
breaking changes and compatibility issues. It analyzes method signatures, 
return types, and parameter changes to identify changes that might affect users.

Usage:
    python -m ipfs_kit_py.tools.check_api_compatibility --previous=0.1.0 --current=HEAD
    python -m ipfs_kit_py.tools.check_api_compatibility --generate-report

**Functions:**
- `get_methods_from_module()`: Extract methods from a module with their signatures.
- `get_all_modules()`: Get all IPFS Kit modules.
- `extract_current_api()`: Extract API information from the current codebase.
- `checkout_version()`: Checkout a specific version using git.
- `extract_api_from_version()`: Extract API information from a specific version.
- `compare_apis()`: Compare two API versions to detect breaking changes.
- `generate_compatibility_report()`: Generate a markdown compatibility report.
- `main()`: Main entry point for the script.

#### `tools/protobuf_compat.py`

Protobuf compatibility layer.

This module provides compatibility wrappers for different versions of the protobuf library.
It handles API differences between older and newer versions of protobuf, particularly
around MessageFactory which changed significantly between versions.

**Classes:**
- `CompatMessageFactory`: Compatibility wrapper for MessageFactory.

**Functions:**
- `get_compatible_message_factory()`: Get a MessageFactory instance that works across protobuf versions.
- `monkey_patch_message_factory()`: Monkey patch the protobuf MessageFactory to ensure compatibility.

#### `tools/__init__.py`

API Stability and Compatibility Tools.

This package contains tools for checking API stability, versioning, and
compatibility between different versions of IPFS Kit.

Submodules:
- check_api_compatibility: Tools for verifying API compatibility between versions
- protobuf_compat: Compatibility layer for different versions of protobuf

### transformers_integration.py

#### `transformers_integration.py`

Integration module for ipfs_transformers_py functionality.

**Classes:**
- `TransformersIntegration`: Bridge class to provide ipfs_transformers functionality.

### unified_bucket_cli.py

#### `unified_bucket_cli.py`

CLI Commands for Unified Bucket-Based Interface

Provides CLI access to the unified bucket interface for managing
content-addressed pins across multiple filesystem backends with
VFS and pin metadata indices.

**Classes:**
- `UnifiedBucketCLI`: CLI interface for unified bucket management.

### unified_bucket_interface.py

#### `unified_bucket_interface.py`

Unified Bucket-Based Interface for Multiple Filesystem Backends

This module provides a unified bucket-based interface for all filesystem backends
(Parquet, Arrow, SSHFS, FTP, Google Drive, S3) where content-addressed "pins" 
are stored in buckets and composed into a virtual filesystem in the .ipfs_kit folder.

Key Features:
- Subfolder mapping per bucket in ~/.ipfs_kit/buckets/<backend>/<bucket_name>/
- VFS and pin metadata indices maintained for each subfolder
- Content-addressed pin storage with bucket organization
- Cross-backend VFS composition and querying

**Classes:**
- `BackendType`: Supported filesystem backend types.
- `PinStatus`: Status of content-addressed pins.
- `UnifiedBucketInterface`: Unified bucket-based interface for multiple filesystem backends.

**Functions:**
- `get_global_unified_bucket_interface()`: Get or create global unified bucket interface instance.

### validation.py

#### `validation.py`

Parameter validation module for IPFS Kit.

This module provides utilities for validating parameters in IPFS Kit functions.

**Classes:**
- `IPFSValidationError`: Exception raised for parameter validation errors.

**Functions:**
- `validate_parameters()`: Validate parameters against specification.
- `validate_cid()`: Validate CID format.
- `is_valid_cid()`: Check if a CID is valid without raising exceptions.
- `validate_multiaddr()`: Validate multiaddress format.
- `validate_timeout()`: Validate timeout value.
- `validate_path()`: Validate file or directory path.
- `is_safe_path()`: Check if a path is safe to access without raising exceptions.
- `validate_required_parameter()`: Validate that a required parameter is present and not None.
- `validate_parameter_type()`: Validate that a parameter has the expected type.
- `validate_command_args()`: Validate command arguments for security issues.
- `is_safe_command_arg()`: Check if a command argument is safe to use without raising exceptions.
- `validate_binary_path()`: Validate and normalize binary path.
- `validate_ipfs_path()`: Validate and normalize IPFS path.
- `validate_role()`: Validate node role.
- `validate_role_permission()`: Validate if a role has permission for an operation.
- `validate_role_permissions()`: Validate if a role has permission for an operation.
- `validate_resources()`: Validate and normalize resource constraints.

### vfs_bucket_manager.py

#### `vfs_bucket_manager.py`

VFS-Based Bucket Manager

This module implements the new bucket architecture where:
- Each bucket is a VFS index directory
- Central bucket registry tracks all buckets
- Bucket configurations stored in YAML files
- No redundant bucket directory structure

**Classes:**
- `VFSBucketManager`: Manages buckets using VFS indices directly.

### vfs_manager.py

#### `vfs_manager.py`

VFS (Virtual File System) Manager for IPFS Kit

This module provides comprehensive VFS management functionality that is shared
between the CLI, MCP server, and other components. It consolidates all VFS
operations, index management, analytics, and filesystem operations.

Key Features:
- Unified VFS operations for all IPFS-Kit components
- Index management and synchronization
- Performance monitoring and analytics
- Filesystem change tracking and journaling
- Cache management and optimization

**Classes:**
- `VFSManager`: Comprehensive VFS Manager for IPFS Kit.

**Functions:**
- `get_global_vfs_manager()`: Get or create the global VFS Manager instance.
- `execute_vfs_operation_sync()`: Execute a VFS operation synchronously for CLI use.
- `get_vfs_statistics_sync()`: Get VFS statistics synchronously for CLI use.

### vfs_version_cli.py

#### `vfs_version_cli.py`

CLI interface for VFS version tracking system.

Provides Git-like commands for managing filesystem versions:
- vfs init: Initialize version tracking
- vfs status: Show current filesystem status
- vfs commit: Create version snapshot
- vfs log: Show version history
- vfs checkout: Checkout specific version
- vfs diff: Show changes between versions

**Classes:**
- `VFSVersionCLI`: CLI interface for VFS version tracking.

**Functions:**
- `create_result_dict()`
- `create_vfs_version_parser()`: Create VFS version tracking CLI parser.

### vfs_version_tracker.py

#### `vfs_version_tracker.py`

VFS Version Tracking System with IPFS CID-based Versioning.

This module implements Git-like version tracking for the virtual filesystem using
IPFS content addressing. Features include:

1. ~/.ipfs_kit/ folder for VFS index storage in Parquet format
2. IPFS CID-based filesystem hashing using ipfs_multiformats_py
3. CAR file generation for version snapshots
4. Version chain linking using IPFS CIDs
5. Content-addressable storage for all files and metadata

**Classes:**
- `VFSVersionTracker`: Git-like version tracking system for virtual filesystems using IPFS CIDs.

**Functions:**
- `get_global_vfs_tracker()`: Get or create global VFS version tracker instance.

### wal.py

#### `wal.py`

Write-Ahead Log (WAL) system for IPFS Kit.

This module provides a Write-Ahead Log implementation for ensuring data consistency
and crash recovery for IPFS operations. It tracks and persists operations to be
performed against backend storage systems, ensuring that operations can be
recovered and completed even in the event of a crash or failure.

Key features:
1. Atomic operation logging and replay
2. Multi-backend support (IPFS, S3, etc.)
3. Operation status tracking
4. Sequential execution guarantee
5. Crash recovery and resume

**Classes:**
- `OperationType`: Types of operations supported by the WAL.
- `OperationStatus`: Status values for operations in the WAL.
- `BackendType`: Backend storage types supported by the WAL.
- `WAL`: Base Write-Ahead Log implementation.

### wal_api.py

#### `wal_api.py`

FastAPI extension for the Write-Ahead Log (WAL) system.

This module adds WAL-specific endpoints to the IPFS Kit FastAPI server, providing:
1. WAL operation management (list, status, retry, etc.)
2. WAL health monitoring
3. WAL configuration
4. WAL statistics and metrics

These endpoints enable management and monitoring of the WAL system through the REST API.

**Classes:**
- `WALOperationModel`: Model for WAL operation.
- `WALOperationListResponse`: Response model for operation list.
- `WALOperationStatusResponse`: Response model for operation status.
- `WALMetricsResponse`: Response model for WAL metrics.
- `WALRetryResponse`: Response model for retry operation.
- `WALConfigModel`: Model for WAL configuration.
- `WALConfigResponse`: Response model for WAL configuration.
- `WALTelemetryConfigModel`: Model for WAL telemetry configuration.
- `WALTelemetryResponse`: Response model for telemetry metrics.
- `WALRealtimeTelemetryResponse`: Response model for real-time telemetry metrics.
- `WALTelemetryReportResponse`: Response model for telemetry report generation.
- `OperationRequest`: Model for operation creation request.
- `StatusUpdateRequest`: Model for operation status update request.
- `OperationResponse`: Model for operation response.
- `OperationsResponse`: Model for multiple operations response.
- `TelemetryResponse`: Model for telemetry response.
- `WALEnabledAPI`
- `BaseModel`
- `APIRouter`
- `TelemetryMetricType`
- `TelemetryAggregation`
- `BaseModel`
- `APIRouter`

**Functions:**
- `register_wal_api()`: Register the WAL API with the FastAPI application.
- `create_api_router()`: Create an API router for the WAL system.
- `create_api_app()`: Create a FastAPI app for the WAL API.
- `start_api_server_thread()`: Start the FastAPI server in a background thread.

### wal_api_anyio.py

#### `wal_api_anyio.py`

FastAPI extension for the Write-Ahead Log (WAL) system using AnyIO.

This module adds WAL-specific endpoints to the IPFS Kit FastAPI server, providing:
1. WAL operation management (list, status, retry, etc.)
2. WAL health monitoring
3. WAL configuration
4. WAL statistics and metrics

These endpoints enable management and monitoring of the WAL system through the REST API.

**Classes:**
- `WALOperationModel`: Model for WAL operation.
- `WALOperationListResponse`: Response model for operation list.
- `WALOperationStatusResponse`: Response model for operation status.
- `WALMetricsResponse`: Response model for WAL metrics.
- `WALRetryResponse`: Response model for retry operation.
- `WALOperationListResponse`: Response model for operation list.
- `WALOperationStatusResponse`: Response model for operation status.
- `WALMetricsResponse`: Response model for WAL metrics.
- `WALRetryResponse`: Response model for retry operation.
- `WALConfigModel`: Model for WAL configuration.
- `WALConfigResponse`: Response model for WAL configuration.
- `WALTelemetryConfigModel`: Model for WAL telemetry configuration.
- `WALTelemetryResponse`: Response model for telemetry metrics.
- `WALRealtimeTelemetryResponse`: Response model for real-time telemetry metrics.
- `WALTelemetryReportResponse`: Response model for telemetry report generation.
- `WALEnabledAPI`
- `BaseModel`
- `APIRouter`
- `TelemetryMetricType`
- `TelemetryAggregation`

**Functions:**
- `register_wal_api()`: Register the WAL API with the FastAPI application.
- `create_standalone_wal_api()`: Create and run a standalone WAL API server with AnyIO support.

### wal_api_extension.py

#### `wal_api_extension.py`

**Classes:**
- `WALEnabledAPI`: Extension of the high-level API with Write-Ahead Log (WAL) integration.

### wal_cli.py

#### `wal_cli.py`

**Classes:**
- `WALCommandLine`: Command line interface for WAL management.

**Functions:**
- `main()`: Main entry point for WAL CLI.

### wal_cli_integration.py

#### `wal_cli_integration.py`

Integration module for WAL CLI with the main IPFS Kit CLI.

This module provides functions to integrate the WAL commands
with the main CLI interface.

**Functions:**
- `register_wal_commands()`: Register WAL-related commands with the CLI parser.
- `parse_wal_kwargs()`: Parse WAL command-specific keyword arguments from command-line arguments.
- `handle_wal_command()`: Handle WAL command execution.

### wal_cli_integration_anyio.py

#### `wal_cli_integration_anyio.py`

Integration module for WAL CLI with the main IPFS Kit CLI using AnyIO.

This module provides functions to integrate the WAL commands
with the main CLI interface, with support for AnyIO backend-agnostic
async operations.

**Functions:**
- `register_wal_commands()`: Register WAL-related commands with the CLI parser.
- `parse_wal_kwargs()`: Parse WAL command-specific keyword arguments from command-line arguments.
- `handle_wal_command()`: Handle WAL command execution - synchronous wrapper for the async function.

### wal_integration.py

#### `wal_integration.py`

**Classes:**
- `WALIntegration`: Integration for the Write-Ahead Log (WAL) system with the high-level API.

**Functions:**
- `with_wal()`: Decorator factory for WAL integration.

### wal_pin_manager.py

#### `wal_pin_manager.py`

Write-Ahead Log (WAL) Manager for IPFS-Kit Pin Operations

This module manages pending pin operations that will be processed by the daemon
and replicated across virtual filesystem backends.

**Classes:**
- `WALPinManager`: Manages write-ahead log for pin operations.

**Functions:**
- `get_wal_pin_manager()`: Get global WAL pin manager instance.

### wal_telemetry.py

#### `wal_telemetry.py`

Telemetry module for the Write-Ahead Log (WAL) system.

This module provides comprehensive telemetry for the WAL system, including:
1. Performance metrics collection and analysis
2. Operation timing and latency tracking
3. Backend health statistics
4. Throughput monitoring
5. Error rate analysis
6. Visualization utilities

The telemetry system integrates with the WAL's core components to provide
real-time and historical insights into system performance.

**Classes:**
- `TelemetryMetricType`: Types of metrics collected by the telemetry system.
- `TelemetryAggregation`: Types of aggregation for telemetry metrics.
- `WALTelemetry`: Telemetry system for the IPFS Kit Write-Ahead Log.
- `OperationType`
- `OperationStatus`
- `BackendType`

### wal_telemetry_ai_ml.py

#### `wal_telemetry_ai_ml.py`

WAL Telemetry integration for AI/ML operations in IPFS Kit.

This module extends the WAL telemetry system to provide specialized monitoring
and tracing for AI/ML operations. It includes metrics for model loading times,
inference latency, training throughput, and distributed training coordination.

Key features:
1. WAL telemetry integration with AIMLMetrics for comprehensive monitoring
2. Specialized Prometheus metrics for AI/ML operations
3. Distributed tracing support for model training and inference
4. Integration with the high-level API for ease of use
5. Context propagation for tracking AI/ML operations across services

**Classes:**
- `WALTelemetryAIMLExtension`: WAL Telemetry extension for AI/ML operations in IPFS Kit.

**Functions:**
- `extend_wal_telemetry()`: Extend WAL telemetry with AI/ML capabilities.
- `extend_high_level_api_with_aiml_telemetry()`: Extend the high-level API with AI/ML telemetry capabilities.

### wal_telemetry_ai_ml_anyio.py

#### `wal_telemetry_ai_ml_anyio.py`

WAL Telemetry integration for AI/ML operations in IPFS Kit with AnyIO support.

This module extends the WAL telemetry system to provide specialized monitoring
and tracing for AI/ML operations. It includes metrics for model loading times,
inference latency, training throughput, and distributed training coordination.
It has been updated to support AnyIO for async backend flexibility.

Key features:
1. WAL telemetry integration with AIMLMetrics for comprehensive monitoring
2. Specialized Prometheus metrics for AI/ML operations
3. Distributed tracing support for model training and inference
4. Integration with the high-level API for ease of use
5. Context propagation for tracking AI/ML operations across services
6. AnyIO support for backend-agnostic async operations

**Classes:**
- `WALTelemetryAIMLExtensionAnyIO`: WAL Telemetry extension for AI/ML operations in IPFS Kit with AnyIO support.

**Functions:**
- `extend_wal_telemetry()`: Extend WAL telemetry with AI/ML capabilities, selecting the appropriate
- `extend_high_level_api_with_aiml_telemetry()`: Extend the high-level API with AI/ML telemetry capabilities,

### wal_telemetry_api.py

#### `wal_telemetry_api.py`

High-level API integration for the WAL telemetry system.

This module provides integration between the high-level API and the WAL telemetry
system, including both Prometheus metrics and distributed tracing capabilities.

**Classes:**
- `WALTelemetryAPIExtension`: Extension for integrating WAL telemetry with the high-level API.

**Functions:**
- `extend_high_level_api()`: Extend the high-level API with WAL telemetry capabilities.

### wal_telemetry_api_anyio.py

#### `wal_telemetry_api_anyio.py`

High-level API integration for the WAL telemetry system with AnyIO support.

This module provides integration between the high-level API and the WAL telemetry
system, including both Prometheus metrics and distributed tracing capabilities.
It uses AnyIO for async/await patterns to support multiple backends (async-io, trio).

**Classes:**
- `WALTelemetryAPIExtensionAnyIO`: Extension for integrating WAL telemetry with the high-level API using AnyIO.

**Functions:**
- `extend_high_level_api()`: Extend the high-level API with WAL telemetry capabilities.
- `get_api_extension()`: Get the WAL telemetry API extension instance from an API instance.

### wal_telemetry_cli.py

#### `wal_telemetry_cli.py`

Command-line interface for WAL telemetry metrics.

This module provides a command-line interface for accessing telemetry metrics,
generating reports, and visualizing performance data from the WAL system.

**Classes:**
- `Colors`: ANSI color codes for terminal output.

**Functions:**
- `format_metric_value()`: Format metric value for display based on metric type.
- `create_table()`: Create a formatted ASCII table.
- `print_metrics_table()`: Print metrics in a formatted table.
- `format_timestamp()`: Format Unix timestamp as human-readable string.
- `watch_metrics()`: Watch metrics in real-time with periodic updates.
- `handle_metrics_command()`: Handle 'metrics' command.
- `handle_report_command()`: Handle 'report' command.
- `handle_viz_command()`: Handle 'viz' command.
- `handle_config_command()`: Handle 'config' command.
- `handle_analyze_command()`: Handle 'analyze' command.
- `register_wal_telemetry_commands()`: Register WAL Telemetry-related commands with the CLI parser.
- `main()`: Main entry point for the CLI.

### wal_telemetry_cli_anyio.py

#### `wal_telemetry_cli_anyio.py`

Command-line interface for WAL telemetry metrics with AnyIO support.

This module provides a command-line interface for accessing telemetry metrics,
generating reports, and visualizing performance data from the WAL system,
with support for different async backends through AnyIO.

**Classes:**
- `Colors`: ANSI color codes for terminal output.

**Functions:**
- `format_metric_value()`: Format metric value for display based on metric type.
- `create_table()`: Create a formatted ASCII table.
- `print_metrics_table()`: Print metrics in a formatted table.
- `format_timestamp()`: Format Unix timestamp as human-readable string.
- `watch_metrics()`: Watch metrics in real-time with periodic updates.
- `handle_metrics_command()`: Handle 'metrics' command.
- `handle_report_command()`: Handle 'report' command.
- `handle_viz_command()`: Handle 'viz' command.
- `handle_config_command()`: Handle 'config' command.
- `handle_analyze_command()`: Handle 'analyze' command.
- `register_wal_telemetry_commands()`: Register WAL Telemetry-related commands with the CLI parser.
- `main()`: Main entry point for the CLI.

### wal_telemetry_client.py

#### `wal_telemetry_client.py`

Client for the WAL telemetry API.

This module provides a client for accessing the WAL telemetry API, providing
programmatic access to telemetry metrics, reports, and visualizations.

**Classes:**
- `TelemetryMetricType`: Types of metrics collected by the telemetry system.
- `TelemetryAggregation`: Types of aggregation for telemetry metrics.
- `WALTelemetryClient`: Client for accessing the WAL telemetry API.

### wal_telemetry_client_anyio.py

#### `wal_telemetry_client_anyio.py`

Client for the WAL telemetry API with AnyIO support.

This module provides a client for accessing the WAL telemetry API, providing
programmatic access to telemetry metrics, reports, and visualizations with
support for different async backends through AnyIO.

**Classes:**
- `TelemetryMetricType`: Types of metrics collected by the telemetry system.
- `TelemetryAggregation`: Types of aggregation for telemetry metrics.
- `WALTelemetryClientAnyIO`: Client for accessing the WAL telemetry API with AnyIO support.

**Functions:**
- `get_telemetry_client()`: Create a telemetry client based on the current context.

### wal_telemetry_prometheus.py

#### `wal_telemetry_prometheus.py`

Prometheus integration for WAL telemetry.

This module provides Prometheus integration for the WAL telemetry system,
allowing WAL performance metrics to be exposed in Prometheus format
for monitoring with Prometheus, Grafana, and other observability tools.

**Classes:**
- `WALTelemetryCollector`: Prometheus collector for WAL telemetry metrics.
- `WALTelemetryPrometheusExporter`: Prometheus exporter for WAL telemetry.
- `Counter`
- `Gauge`
- `Histogram`
- `Summary`
- `CollectorRegistry`
- `GaugeMetricFamily`
- `CounterMetricFamily`

**Functions:**
- `add_wal_metrics_endpoint()`: Add a WAL telemetry metrics endpoint to a FastAPI application.

### wal_telemetry_prometheus_anyio.py

#### `wal_telemetry_prometheus_anyio.py`

Prometheus integration for WAL telemetry with AnyIO support.

This module provides Prometheus integration for the WAL telemetry system with
AnyIO support, allowing WAL performance metrics to be exposed in Prometheus
format for monitoring with Prometheus, Grafana, and other observability tools
while working with any async backend.

**Classes:**
- `WALTelemetryCollector`: Prometheus collector for WAL telemetry metrics.
- `WALTelemetryPrometheusExporterAnyIO`: Prometheus exporter for WAL telemetry with AnyIO support.
- `Counter`
- `Gauge`
- `Histogram`
- `Summary`
- `CollectorRegistry`
- `GaugeMetricFamily`
- `CounterMetricFamily`

**Functions:**
- `add_wal_metrics_endpoint()`: Add a WAL telemetry metrics endpoint to a FastAPI application.
- `get_prometheus_exporter()`: Get the appropriate Prometheus exporter based on context.

### wal_telemetry_tracing.py

#### `wal_telemetry_tracing.py`

Distributed tracing module for the Write-Ahead Log (WAL) telemetry system.

This module provides distributed tracing capabilities for the WAL system, enabling
tracking of operations across different components and services. It includes:

1. OpenTelemetry integration for standardized tracing
2. Trace context propagation between components
3. Span creation and management for WAL operations
4. Automatic correlation with WAL telemetry metrics
5. Export capabilities to various tracing backends (Jaeger, Zipkin, etc.)

The tracing system integrates with the WAL telemetry to provide a comprehensive
view of system performance and behavior across distributed components.

**Classes:**
- `TracingExporterType`: Types of tracing exporters supported.
- `WALTracingContext`: Context manager for WAL operation tracing spans.
- `WALTracing`: Distributed tracing for the IPFS Kit Write-Ahead Log system.
- `MinimalSpan`: Minimal span implementation when OpenTelemetry is not available.
- `MinimalContext`: Minimal context implementation when OpenTelemetry is not available.
- `MinimalPropagator`: Minimal propagator implementation when OpenTelemetry is not available.
- `MinimalTracer`: Minimal tracer implementation when OpenTelemetry is not available.
- `OperationType`
- `OperationStatus`
- `BackendType`
- `Span`
- `StatusCode`
- `Status`

**Functions:**
- `add_tracing_middleware()`: Add tracing middleware to a FastAPI application.
- `trace_http_request()`: Trace an HTTP request with OpenTelemetry.

### wal_telemetry_tracing_anyio.py

#### `wal_telemetry_tracing_anyio.py`

AnyIO-compatible distributed tracing module for the Write-Ahead Log (WAL) telemetry system.

This module provides distributed tracing capabilities for the WAL system, enabling
tracking of operations across different components and services, with support for 
both async-io and trio backends through AnyIO. It includes:

1. OpenTelemetry integration for standardized tracing
2. Trace context propagation between components
3. Span creation and management for WAL operations
4. Automatic correlation with WAL telemetry metrics
5. Export capabilities to various tracing backends (Jaeger, Zipkin, etc.)
6. AnyIO compatibility for backend-agnostic async operations

The tracing system integrates with the WAL telemetry to provide a comprehensive
view of system performance and behavior across distributed components.

**Classes:**
- `TracingExporterType`: Types of tracing exporters supported.
- `WALTracingContext`: Context manager for WAL operation tracing spans.
- `WALTracingAnyIO`: AnyIO-compatible distributed tracing for the IPFS Kit Write-Ahead Log system.
- `OperationType`
- `OperationStatus`
- `BackendType`
- `Span`
- `StatusCode`
- `Status`

### wal_visualization.py

#### `wal_visualization.py`

**Classes:**
- `WALVisualization`: Visualization tools for the WAL system.

**Functions:**
- `main()`: Main function to run the visualization tool standalone.

### wal_visualization_anyio.py

#### `wal_visualization_anyio.py`

**Classes:**
- `WALVisualizationAnyIO`: Visualization tools for the WAL system with AnyIO support.

**Functions:**
- `main()`: Main function to run the visualization tool standalone.

### wal_websocket.py

#### `wal_websocket.py`

WebSocket interface for the Write-Ahead Log (WAL) system.

This module provides real-time monitoring and streaming of WAL operations through WebSockets,
allowing clients to:
1. Subscribe to operation status updates
2. Monitor backend health changes
3. Get real-time metrics about the WAL system
4. Receive notifications about specific operations

Using WebSockets enables responsive, efficient monitoring without constant polling.

**Classes:**
- `SubscriptionType`: Types of WebSocket subscriptions.
- `WALConnectionManager`: Manages WebSocket connections for the WAL system.
- `WALWebSocketHandler`: Handles WebSocket connections and events for the WAL system.
- `WebSocketState`

**Functions:**
- `register_wal_websocket()`: Register the WAL WebSocket with the FastAPI application.

### wal_websocket_anyio.py

#### `wal_websocket_anyio.py`

WebSocket interface for the Write-Ahead Log (WAL) system using anyio.

This module provides real-time monitoring and streaming of WAL operations through WebSockets,
allowing clients to:
1. Subscribe to operation status updates
2. Monitor backend health changes
3. Get real-time metrics about the WAL system
4. Receive notifications about specific operations

Using WebSockets enables responsive, efficient monitoring without constant polling.
The anyio implementation provides backend flexibility and improved resource management.

**Classes:**
- `SubscriptionType`: Types of WebSocket subscriptions.
- `WALConnectionManager`: Manages WebSocket connections for the WAL system.
- `WALWebSocketHandler`: Handles WebSocket connections and events for the WAL system.
- `WebSocketState`

**Functions:**
- `register_wal_websocket()`: Register the WAL WebSocket with the FastAPI application.

### webrtc_api.py

#### `webrtc_api.py`

WebRTC API for IPFS Kit

This module provides a FastAPI router for WebRTC streaming and signaling
in IPFS Kit, enabling real-time peer-to-peer content streaming.

Features:
- WebRTC signaling (offer/answer)
- Direct peer connections
- Content streaming
- Stream recording

**Classes:**
- `WebRTCOffer`: WebRTC offer model
- `WebRTCAnswer`: WebRTC answer model
- `WebRTCICECandidate`: WebRTC ICE candidate model

### webrtc_benchmark.py

#### `webrtc_benchmark.py`

WebRTC Performance Benchmarking for IPFS Kit.

This module provides comprehensive benchmarking capabilities for WebRTC 
connections, enabling detailed performance analysis of streaming from IPFS content.

Key features:
1. Connection Metrics: Detailed timing for ICE, DTLS, etc.
2. Media Performance: Frame rates, resolution, bitrate analysis
3. Network Analysis: RTT, jitter, packet loss statistics
4. Resource Utilization: CPU, memory, bandwidth tracking
5. Quality Scoring: Quantitative measures of streaming quality
6. Report Generation: Comprehensive performance reports
7. Regression Testing: Comparison between benchmark runs

This module can be used standalone or integrated with WebRTCStreamingManager.

**Classes:**
- `WebRTCFrameStat`: Statistics for a single frame's processing and delivery.
- `WebRTCBenchmark`: Comprehensive benchmarking system for WebRTC streaming performance.
- `WebRTCStreamingManagerBenchmarkIntegration`: Helper class to integrate WebRTCBenchmark with WebRTCStreamingManager.
- `FrameTracker`

**Functions:**
- `create_frame_stat()`: Create a new frame statistic object with the given parameters.
- `track_frame_timing()`: Context manager for tracking frame timing.

### webrtc_cli.py

#### `webrtc_cli.py`

Command-line interface for WebRTC streaming and benchmarking.

This module provides commands for WebRTC-related operations including:
- Streaming content over WebRTC
- Conducting performance benchmarks
- Managing streaming connections
- Configuring WebRTC settings

**Classes:**
- `Colors`: ANSI color codes for terminal output.
- `SimpleAPI`

**Functions:**
- `create_table()`: Create a formatted ASCII table.
- `handle_stream_content_command()`: Handle the 'stream' command to stream IPFS content over WebRTC.
- `handle_benchmark_command()`: Handle the 'benchmark' command to run WebRTC performance benchmarks.
- `handle_connections_command()`: Handle the 'connections' command to manage WebRTC connections.
- `handle_check_dependencies_command()`: Check WebRTC dependencies and display status.
- `register_webrtc_commands()`: Register WebRTC-related commands with the CLI parser.
- `main()`: Main entry point for the CLI when run standalone.

### webrtc_multi_peer.py

#### `webrtc_multi_peer.py`

WebRTC Multi-Peer Streaming for IPFS Kit.

This module extends the WebRTC streaming capabilities to support multiple peer connections,
enabling group streaming sessions, broadcasting, and mesh networking for IPFS content.

Key features:
1. Group Streaming: Stream to multiple receivers simultaneously
2. Broadcasting: Efficiently distribute media streams to many viewers
3. Mesh Networking: Peer-to-peer media distribution network
4. SFU-like Functionality: Selective forwarding for efficient multi-party streaming
5. Dynamic Peer Management: Add/remove peers during active sessions
6. Bandwidth Optimization: Intelligent stream routing and quality adaptation
7. Session Management: Create, join, and manage streaming sessions
8. Room-based Model: Group peers by room/channel for organization

This module builds on the core WebRTC streaming functionality and integrates with
the notification system for signaling and session coordination.

**Classes:**
- `PeerRole`: Roles that peers can have in a streaming session.
- `StreamingSession`: Manages a multi-peer streaming session with multiple participants.
- `SessionManager`: Manages multiple streaming sessions and provides discovery services.

### webrtc_multi_peer_integration.py

#### `webrtc_multi_peer_integration.py`

WebRTC Multi-Peer Integration for IPFS Kit.

This module provides integration between the WebRTC multi-peer streaming functionality
and the rest of the IPFS Kit, including API endpoints, high-level interfaces,
and seamless access to IPFS content for streaming.

Key features:
1. API Integration: FastAPI endpoints for WebRTC multi-peer streaming
2. Session Discovery: API endpoints for discovering and joining streaming sessions
3. High-Level Interface: Simplified interface for common multi-peer streaming operations
4. IPFS Integration: Direct streaming of IPFS content in multi-peer sessions
5. Client Libraries: JavaScript client libraries for browser integration
6. Security Integration: Integration with streaming security features
7. Statistics Collection: Session and peer performance metrics
8. Media Processing: Optional video/audio processing capabilities

This module serves as the integration point between the multi-peer streaming system,
the IPFS Kit API, and client applications.

**Classes:**
- `SessionOptions`: Options for creating a new streaming session.
- `PeerInfo`: Information about a peer joining a session.
- `TrackInfo`: Information about a media track to add to a session.
- `SessionResponse`: Response model for session operations.
- `SessionListResponse`: Response model for listing available sessions.
- `SessionInfoResponse`: Response model for detailed session information.
- `MultiPeerStreamingIntegration`: Integration class for WebRTC multi-peer streaming functionality.
- `BaseModel`: Fallback BaseModel when Pydantic is not available.

**Functions:**
- `extend_simple_api()`: Extend the IPFSSimpleAPI with multi-peer streaming capabilities.
- `get_javascript_client()`: Get the JavaScript client for browser integration.

### webrtc_streaming.py

#### `webrtc_streaming.py`

WebRTC streaming functionality for IPFS content.

This module provides WebRTC streaming capabilities for IPFS content,
enabling real-time media streaming from IPFS to browsers or other clients.

The module includes functionality for:
- Establishing WebRTC connections with clients
- Streaming IPFS content over WebRTC
- Managing media tracks
- Handling signaling protocols
- Dynamic bitrate adaptation

This implementation properly handles optional dependencies to ensure the 
module can be imported even if WebRTC dependencies are not installed.

**Classes:**
- `AnyIOEventLoopHandler`: Helper class to manage event loop interaction with AnyIO compatibility.
- `AdaptiveBitrateController`: Adaptive bitrate controller for WebRTC streams.
- `MockMediaStreamTrack`
- `MockVideoStreamTrack`
- `MockAudioStreamTrack`
- `MockRTCPeerConnection`
- `IPFSMediaStreamTrack`: Media stream track that sources content from IPFS with optimized streaming.
- `WebRTCStreamingManager`: Manager for WebRTC streaming connections.
- `IPFSMediaStreamTrack`: Stub implementation of IPFSMediaStreamTrack.
- `WebRTCStreamingManager`: Stub implementation of WebRTCStreamingManager.

**Functions:**
- `check_webrtc_dependencies()`: Check the status of WebRTC dependencies and return a detailed report.

### websocket_notifications.py

#### `websocket_notifications.py`

WebSocket Notifications for IPFS Kit.

This module provides a real-time notification system for IPFS Kit using WebSockets.
It enables clients to subscribe to various event types and receive notifications
when those events occur, providing real-time visibility into IPFS operations.

Key features:
1. Event Subscriptions: Subscribe to specific event types
2. Filtered Notifications: Receive only events matching specific criteria
3. Multiple Channels: Different notification categories (content, peers, pins, etc.)
4. Lightweight Protocol: Simple JSON-based messaging protocol
5. Persistent Connections: Long-lived WebSocket connections for real-time updates
6. Broadcast Support: Send notifications to multiple clients
7. System Metrics: Real-time performance and health metrics

**Classes:**
- `NotificationType`: Types of notifications that can be sent or subscribed to.
- `NotificationManager`: Manages WebSocket subscriptions and notifications.
- `WebSocketState`

### websocket_notifications_anyio.py

#### `websocket_notifications_anyio.py`

WebSocket Notifications for IPFS Kit using anyio.

This module provides a real-time notification system for IPFS Kit using WebSockets,
implemented with anyio for backend-agnostic async operations. It enables clients to 
subscribe to various event types and receive notifications when those events occur,
providing real-time visibility into IPFS operations.

Key features:
1. Event Subscriptions: Subscribe to specific event types
2. Filtered Notifications: Receive only events matching specific criteria
3. Multiple Channels: Different notification categories (content, peers, pins, etc.)
4. Lightweight Protocol: Simple JSON-based messaging protocol
5. Persistent Connections: Long-lived WebSocket connections for real-time updates
6. Broadcast Support: Send notifications to multiple clients
7. System Metrics: Real-time performance and health metrics
8. Backend Agnostic: Works with async-io, trio, or any other anyio-compatible backend

**Classes:**
- `NotificationType`: Types of notifications that can be sent or subscribed to.
- `NotificationManager`: Manages WebSocket subscriptions and notifications.
- `MockWebSocket`
- `WebSocketState`

**Functions:**
- `register_notification_websocket()`: Register notification WebSocket endpoint with FastAPI.


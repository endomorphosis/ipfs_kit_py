# IPFS Kit Documentation

Welcome to the IPFS Kit documentation! This guide will help you navigate the comprehensive documentation available for the IPFS Kit Python library.

## Getting Started

IPFS Kit is a comprehensive Python toolkit for working with IPFS (InterPlanetary File System) technologies. It provides a unified interface for IPFS operations, cluster management, tiered storage, and AI/ML integration.

### Installation

```bash
# Basic installation with core functionality
pip install ipfs_kit_py

# With filesystem support (fsspec integration)
pip install ipfs_kit_py[fsspec]

# With full functionality
pip install ipfs_kit_py[full]
```

For more installation options, see the [README.md](../README.md#installation).

## Documentation Structure

The documentation is organized into several key sections:

### Core Documentation

1. [**Core Concepts**](core_concepts.md) - Fundamental concepts and architecture of IPFS Kit
   - Node Roles (Master/Worker/Leecher)
   - Content Addressing
   - Component Relationships
   - Deployment Patterns

2. [**High-Level API**](high_level_api.md) - Simplified interface for common operations
   - IPFSSimpleAPI Usage
   - Declarative Configuration
   - Plugin Architecture
   - SDK Generation

### Storage and Access

3. [**Tiered Cache System**](tiered_cache.md) - High-performance multi-tier caching
   - Adaptive Replacement Cache (ARC)
   - Cache Tiers (Memory, Disk, IPFS)
   - Heat Scoring Algorithm
   - Cache Migration

4. [**Probabilistic Data Structures**](probabilistic_data_structures.md) - Memory-efficient approximation algorithms
   - Bloom Filter for Membership Testing
   - HyperLogLog for Cardinality Estimation
   - Count-Min Sketch for Frequency Estimation
   - Cuckoo Filters with Deletion Support
   - MinHash for Similarity Detection
   - TopK for Popular Item Tracking
   - Memory/Accuracy Tradeoffs
   - Practical Integration Examples

5. [**FSSpec Filesystem Interface**](fsspec_integration.md) - Standard filesystem interface
   - File-like Operations
   - Integration with Data Science Tools
   - Performance Optimizations
   - Gateway Support

6. [**Storage Backends**](storage_backends.md) - External storage integrations
   - Storacha/Web3.Storage Integration
   - S3-Compatible Storage
   - Multi-backend Content Management
   - Backend Selection Strategies

### Distributed Systems

6. [**Cluster Management**](cluster_management.md) - Advanced cluster coordination
   - Cluster Setup and Configuration
   - Task Distribution
   - State Synchronization
   - Health Monitoring
   - Security Features

7. [**Cluster State Helpers**](cluster_state_helpers.md) - Arrow-based cluster state
   - Zero-copy State Management
   - External Process Access
   - Multi-language Interoperability
   - Distributed State Synchronization

8. [**Direct P2P Communication**](libp2p_integration.md) - LibP2P integration
   - Direct Peer Connections
   - NAT Traversal
   - Content Discovery
   - Peer Management

### Data Management

9. [**Metadata Index**](metadata_index.md) - Arrow-based metadata indexing
   - Content Discovery
   - Distributed Indexing
   - Query Capabilities
   - Multi-location Tracking

10. [**IPLD Knowledge Graph**](knowledge_graph.md) - Semantic relationships
    - Graph Data Modeling
    - Entity Relationships
    - Graph Traversal
    - Content Organization

### AI and ML Integration

11. [**AI/ML Integration Guide**](ai_ml_integration_guide.md) - Comprehensive guide to AI/ML components
    - Architecture Overview
    - Component Interaction Patterns
    - Integration Flow
    - Best Practices
    - Complete End-to-End Examples

12. [**AI/ML Visualization**](ai_ml_visualization.md) - Metrics visualization and reporting
    - Training Metrics Visualization
    - Inference Performance Analysis
    - Worker Utilization Visualization
    - Comprehensive Dashboards
    - HTML Report Generation
    - Export Capabilities
    - Integration with Data Science Workflows

13. [**AI/ML Integration**](ai_ml_integration.md) - Integration with AI frameworks
    - Model Registry
    - Dataset Management
    - LangChain & LlamaIndex Integration
    - Framework Integrations (PyTorch, TensorFlow)
    - AI Safety and Compliance
    - Distributed Training
    - Generative Multimodal Workflows
    - Real-world Case Studies

14. [**IPFS DataLoader**](ipfs_dataloader.md) - Efficient data loading for ML
    - Batch Loading
    - Framework Integration
    - Dataset Versioning
    - Distributed Training Support

15. [**Performance Metrics**](performance_metrics.md) - Comprehensive performance measurement
    - Benchmarking Tools
    - Performance Profiling
    - Optimization Strategies
    - Comparison Tools

## Reference Documentation

IPFS Kit includes comprehensive reference documentation for the underlying technologies:

- [IPFS Documentation](ipfs-docs/docs/concepts/README.md) - Core IPFS concepts and operations
- [IPFS Cluster Documentation](ipfs_cluster/content/documentation/README.md) - IPFS Cluster reference
- [LibP2P Documentation](libp2p_docs/content/concepts/README.md) - LibP2P networking stack
- [FSSpec Documentation](filesystem_spec/docs/source/index.rst) - Filesystem specification reference
- [Storacha Specifications](storacha_specs/Readme.md) - Web3.Storage protocols

## Examples

For practical examples of using IPFS Kit, see the [examples directory](../examples/README.md), which includes:

- Basic usage examples
- FSSpec integration examples
- Cluster management examples
- Performance profiling examples
- AI/ML integration examples
- AI/ML visualization examples
- Data science workflow examples
- High-level API usage examples
- Tiered cache performance examples
- Probabilistic data structures examples
- Practical integration examples

## Contributing to Documentation

We welcome contributions to improve the documentation! If you find errors, have suggestions, or want to add examples, please submit a pull request or open an issue.

When contributing to documentation:

1. Follow the existing style and formatting
2. Provide practical examples where appropriate
3. Explain concepts clearly with diagrams when appropriate
4. Link related documentation
5. Test examples before submitting

## Getting Help

If you need help with IPFS Kit:

- Check the [README.md](../README.md) for quick start guides
- Search the documentation for specific topics
- Look at the examples in the [examples directory](../examples/)
- Open an issue on GitHub if you find a bug or have a feature request
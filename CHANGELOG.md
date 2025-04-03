# Changelog

All notable changes to the `ipfs_kit_py` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-04-02

### Added
- Comprehensive performance metrics system
- Benchmarking framework with command-line interface
- Performance visualization capabilities
- System resource monitoring integration
- Performance documentation and examples
- High-level API (`IPFSSimpleAPI`) for simplified interactions
- Role-based architecture (master/worker/leecher)
- Tiered storage system with Adaptive Replacement Cache (ARC)
- FSSpec integration for filesystem-like IPFS access
- Arrow-based metadata indexing
- Direct P2P communication via libp2p
- Cluster management capabilities
- IPLD-based knowledge graph
- AI/ML integration tools
- REST API server using FastAPI
- Command-line interface (CLI)
- Comprehensive testing framework
- Documentation for all major components

### Fixed
- PyArrow schema type mismatches in test suite
- FSSpec integration with proper AbstractFileSystem inheritance
- Class name collisions between components
- Test isolation for consistent results
- Parameter validation for robust error handling
- Performance bottlenecks in content retrieval
- Cache eviction strategies for optimal performance

### Changed
- Migrated to modern packaging with pyproject.toml
- Optimized cache performance with memory-mapped files
- Improved error reporting with standardized result dictionaries
- Enhanced cluster state synchronization with CRDT-based approach
- Reorganized API structure for improved discoverability

[Unreleased]: https://github.com/endomorphosis/ipfs_kit_py/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/endomorphosis/ipfs_kit_py/releases/tag/v0.1.0
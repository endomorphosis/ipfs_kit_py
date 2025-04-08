# Release v0.2.0

This release adds WebRTC streaming capabilities, performance optimizations, and several advanced features for improved data handling.

## Key Features

### WebRTC Streaming
- WebRTC streaming for media content from IPFS
- Real-time WebSocket notification system
- Performance benchmarking system for WebRTC streaming

### Advanced Performance Optimizations
- Schema and column optimization for ParquetCIDCache
- Advanced partitioning strategies
- Parallel query execution for analytical operations
- Probabilistic data structures (BloomFilter, HyperLogLog, CountMinSketch, etc.)

### Improved Documentation and Stability
- Comprehensive documentation for all new features
- Fixed syntax errors in test files for better stability
- Improved FSSpec integration in high_level_api.py

## Bug Fixes
- Proper handling of optional dependencies like pandas in ai_ml_integration.py
- Added conditional imports and fallback implementations for when pandas is not available
- Fixed syntax errors in test files for better test suite stability
- Fixed indentation issues in several test files
- Updated test decorators for consistent test execution

## Installation

### Using with pip
```bash
pip install ipfs_kit_py==0.2.0
```

### Using with Docker
```bash
docker pull ghcr.io/endomorphosis/ipfs_kit_py:0.2.0
```

See [CHANGELOG.md](https://github.com/endomorphosis/ipfs_kit_py/blob/main/CHANGELOG.md) for complete details on all changes.
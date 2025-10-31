# Known Issues and Limitations

This document lists known issues, limitations, and important considerations when using ipfs_kit_py.

## Installation and Dependencies

### Optional Dependencies
- **Issue**: The package has many optional dependencies that are not installed by default.
- **Impact**: Features may not work without the appropriate extras installed.
- **Workaround**: Install specific extras as needed:
  ```bash
  pip install ipfs_kit_py[fsspec]  # For filesystem interface
  pip install ipfs_kit_py[arrow]   # For high-performance data operations
  pip install ipfs_kit_py[ai_ml]   # For AI/ML support
  pip install ipfs_kit_py[full]    # For all features
  ```
- **Status**: By design - allows minimal installation for users who don't need all features

### Binary Downloads
- **Issue**: First-time initialization downloads platform-specific binaries (Kubo, IPFS Cluster, etc.).
- **Impact**: Initial startup may be slow depending on network speed.
- **Workaround**: Pre-download binaries or set `auto_download_binaries=False` in metadata.
- **Status**: By design - ensures correct binaries for your platform

### Base58 Version Conflict
- **Issue**: Some systems may have incompatible base58 versions (requires >=2.1.1).
- **Impact**: Import errors or functionality issues.
- **Workaround**: Upgrade base58: `pip install --upgrade base58`
- **Status**: Known dependency conflict in some environments

## API and Functionality

### Return Value Inconsistencies
- **Issue**: Some methods return different key names in result dictionaries (e.g., "Hash" vs "cid").
- **Impact**: Code may need to check for multiple possible key names.
- **Workaround**: Use `.get()` with defaults: `result.get("cid") or result.get("Hash")`
- **Status**: Historical inconsistency from underlying IPFS API - documented in examples

### Timeout Defaults
- **Issue**: Default timeouts may be too short for large files or slow networks.
- **Impact**: Operations may timeout unexpectedly.
- **Workaround**: Configure longer timeouts in config file or pass `timeout` parameter.
- **Status**: By design - defaults favor responsiveness over handling edge cases

### File Handle Modes
- **Issue**: The `open()` method only supports read-binary mode ("rb").
- **Impact**: Cannot use other modes like "r", "w", or "a".
- **Workaround**: Use `add()` for writing, `get()` or `read()` for reading text.
- **Status**: By design - IPFS is immutable, write operations create new content

## Platform-Specific Issues

### Windows Path Handling
- **Issue**: Windows paths with backslashes may not work correctly in some contexts.
- **Impact**: File operations may fail on Windows.
- **Workaround**: Use forward slashes or `pathlib.Path` objects.
- **Status**: Known limitation - use Path objects for cross-platform compatibility

### ARM64 Support
- **Issue**: Some binary components may have limited ARM64 support.
- **Impact**: May not work on ARM64 systems (Apple Silicon, ARM servers).
- **Workaround**: Check ARM64_RUNNER_SETUP.md for platform-specific guidance.
- **Status**: Under active development

## Cluster Operations

### Cluster-Only Methods
- **Issue**: Cluster methods (`cluster_add`, `cluster_pin`, etc.) only work in master/worker roles.
- **Impact**: Methods will fail or return errors in leecher role.
- **Workaround**: Check role before calling cluster methods or configure node as worker/master.
- **Status**: By design - leecher nodes don't participate in cluster operations

### Replication Factor Limits
- **Issue**: Replication factor cannot exceed the number of available cluster peers.
- **Impact**: High replication factors may be silently reduced.
- **Workaround**: Monitor actual replication with `cluster_status()`.
- **Status**: IPFS Cluster limitation

## Performance Considerations

### First-Call Latency
- **Issue**: First API call may be slower due to initialization overhead.
- **Impact**: Initial operations take longer than subsequent ones.
- **Workaround**: Perform a warmup call during initialization.
- **Status**: By design - lazy initialization for faster startup

### Large File Handling
- **Issue**: Adding very large files (>1GB) may consume significant memory.
- **Impact**: High memory usage, potential OOM errors.
- **Workaround**: Use chunked uploads or increase available memory.
- **Status**: Under optimization - chunked upload support being improved

### Cache Memory Usage
- **Issue**: The tiered cache can consume significant memory with default settings.
- **Impact**: High memory usage on systems with limited RAM.
- **Workaround**: Configure smaller cache sizes in config: `cache.memory_size: 100MB`
- **Status**: By design - defaults favor performance over memory efficiency

## Documentation

### Example File Accuracy
- **Issue**: Some example files may reference features that require optional dependencies.
- **Impact**: Examples may not run without additional package installations.
- **Workaround**: Read example comments to identify required extras.
- **Status**: Examples updated to include dependency information in comments

### API Documentation Completeness
- **Issue**: Some newer API methods may not be fully documented.
- **Impact**: Users may not discover all available features.
- **Workaround**: Check source code docstrings for undocumented methods.
- **Status**: Ongoing - documentation being continuously improved

## Testing

### External Service Dependencies
- **Issue**: Some tests require running IPFS daemon or cluster services.
- **Impact**: 45+ tests are skipped in default test runs.
- **Workaround**: Run IPFS services locally for comprehensive testing.
- **Status**: By design - tests marked as skipped when services unavailable

### Platform-Specific Tests
- **Issue**: Some tests only run on specific platforms (Linux, macOS, Windows).
- **Impact**: Test coverage varies by platform.
- **Workaround**: Run tests on target platform for platform-specific validation.
- **Status**: By design - platform-specific features have platform-specific tests

## WebRTC and Streaming

### WebRTC Dependencies
- **Issue**: WebRTC functionality requires aiortc and related packages.
- **Impact**: WebRTC features not available without `webrtc` extra.
- **Workaround**: Install with: `pip install ipfs_kit_py[webrtc]`
- **Status**: By design - WebRTC is optional feature

### Streaming Buffer Limits
- **Issue**: Default buffer sizes may not be optimal for all network conditions.
- **Impact**: Streaming may stutter or underflow in poor network conditions.
- **Workaround**: Adjust buffer_size and prefetch_threshold parameters.
- **Status**: Tunable - see WebRTC streaming examples for configuration

## Reporting Issues

If you encounter issues not listed here:

1. Check if it's related to an optional dependency and install required extras
2. Check GitHub Issues: https://github.com/endomorphosis/ipfs_kit_py/issues
3. Verify you're using the latest version: `pip install --upgrade ipfs_kit_py`
4. Review relevant documentation in `docs/` directory
5. Open a new issue with:
   - Python version
   - Platform (OS and architecture)
   - Installed extras (`pip show ipfs_kit_py`)
   - Minimal reproduction example
   - Error messages and stack traces

## Version-Specific Notes

### v0.2.0 (Current)
- Requires Python >=3.12
- Major refactoring of async architecture
- New high-level API methods
- See CHANGELOG.md for full release notes

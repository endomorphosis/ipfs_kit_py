# Changelog

All notable changes to IPFS Kit Python will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Enhanced MCP server with improved storage backend integration
- Fixed libp2p model and IPFS name resolution handling
- Added comprehensive test suite for storage backends

### Changed
- Reorganized project structure for better development experience
- Improved error handling in daemon management
- Enhanced WebRTC integration

### Fixed
- IPFS name resolve method now properly handles bytes responses
- LibP2P additional fixes for better protocol compatibility
- MCP API and controller fixes for more robust operation

## [0.2.0] - 2024-04-08

### Added
- Storage backends integration (S3, Hugging Face, Storacha, Filecoin, Lassie)
- WebRTC streaming capabilities
- Improved libp2p peer-to-peer functionality
- Enhanced IPFS cluster integration
- Multi-daemon support with automatic management

### Changed
- Updated High-Level API with more comprehensive methods
- Improved anyio support for better async/await patterns
- Enhanced error handling and reporting
- Better Lotus integration with simulation mode fallback

### Fixed
- Various stability issues in MCP server
- Improved daemon management reliability
- Fixed edge cases in content addressing

## [0.1.0] - 2024-03-24

### Added
- Initial release with basic IPFS functionality
- High-level API for IPFS operations
- Basic MCP (Model-Controller-Persistence) architecture
- Filesystem integration with fsspec
- Basic content discovery and retrieval
- Simple CLI interface

[Unreleased]: https://github.com/endomorphosis/ipfs_kit_py/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/endomorphosis/ipfs_kit_py/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/endomorphosis/ipfs_kit_py/releases/tag/v0.1.0
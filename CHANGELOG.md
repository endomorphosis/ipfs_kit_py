# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Refactored JSON-RPC dispatcher in `consolidated_mcp_dashboard.py` into domain-specific handlers (system/services, backends, buckets, pins, files, IPFS, CARs, state, logs/server). No API changes; behavior verified by Playwright E2E (13/13 passing).

- Tool Runner polish: persist last-selected tool in localStorage, Reset button to restore defaults from hints, and Copy cURL to clipboard.

### Added
- Beta Tool Runner accessibility and UX improvements:
	- ARIA roles/labels, live result region, and validation with `aria-invalid`.
	- Error summary region announced via `role=alert` and focus management.
	- Keyboard shortcut: Ctrl/Cmd+Enter to run.
	- Responsive layout for narrow screens.
	- Opt-in Playwright tests (enable with `BETA_UI=1`) for a11y and confirmation flows.
 - MCP Dashboard status endpoint now includes `counts.requests` (lifetime HTTP request counter) and `security.auth_enabled` flag.
 - Lightweight HTTP middleware added to increment an in-memory request counter; covered by unit tests (`test_status_request_count.py`).
## [3.1.0] - 2025-07-29 - Three-Tier Policy System Release

### 🎯 Major Feature: Comprehensive Three-Tier Policy System

This release introduces a complete **three-tier policy management system** providing fine-grained control over data replication, caching, and storage quotas across all backends.

### ✨ Added

#### **Three-Tier Policy Architecture**
- **[Policy System Documentation](./POLICY_SYSTEM_DOCUMENTATION.md)**: Complete system documentation with examples
- **[CLI Policy Usage Guide](./CLI_POLICY_USAGE_GUIDE.md)**: Comprehensive CLI command reference
- **Global Pinset Policies**: System-wide defaults via `ipfs-kit config pinset-policy`
- **Bucket-Level Policies**: Per-bucket overrides via `ipfs-kit bucket policy`
- **Backend-Specific Quotas**: Hard limits and retention via `ipfs-kit backend <name> configure`

#### **Policy Management Features**
- **Replication Strategies**: Single, multi-backend, tiered, and adaptive replication
- **Cache Policies**: LRU, LFU, FIFO, MRU, adaptive, and tiered caching with memory limits
- **Performance Tiers**: Speed-optimized, balanced, and persistence-optimized configurations
- **Auto-Tiering**: Hot/warm/cold data movement based on access patterns
- **Geographic Distribution**: Local, regional, and global distribution strategies
- **Failover Management**: Immediate, delayed, and manual failover strategies
- **Backend Weighting**: Load balancing across preferred backends

#### **Backend Quota & Retention System**
- **Filecoin/Lotus**: Deal-based retention, auto-renewal, redundancy levels (high persistence, low speed)
- **Arrow**: Memory quotas, spill-to-disk, session-based retention (high speed, low persistence)
- **Parquet**: Storage quotas, auto-compaction, access-based retention (balanced characteristics)
- **S3**: Account quotas, lifecycle policies, cost optimization (moderate speed, high persistence)
- **GitHub**: Repository/LFS quotas, branch protection, collaboration controls
- **HuggingFace**: Hub storage quotas, model versioning, cache retention policies
- **Google Drive**: Storage quotas, version limits, auto-trash, sharing controls
- **Storacha**: Filecoin-backed quotas, deal duration, Web3 storage economics
- **Synapse**: Research data quotas, provenance tracking, DOI minting
- **SSHFS**: Remote filesystem quotas, network resilience, auto-reconnection
- **FTP**: Server quotas, bandwidth limits, legacy protocol compatibility

#### **Policy Inheritance & Validation**
- **Hierarchical Inheritance**: Global → Bucket → Backend policy flow
- **Conflict Resolution**: Automatic resolution with clear precedence rules
- **Policy Validation**: Comprehensive validation with detailed error reporting
- **Configuration Simulation**: Test policy changes before applying
- **Template System**: Pre-defined templates for common use cases
- **Policy Analytics**: Usage statistics and effectiveness monitoring

### 🛠️ Enhanced

#### **CLI Command Extensions**
- **Global Policy Commands**: Complete `config pinset-policy` command suite
- **Bucket Policy Commands**: Full `bucket policy` management with templates
- **Backend Configuration**: Enhanced `backend <name> configure` for all backends
- **Status and Monitoring**: Comprehensive status, validation, and analytics commands
- **Export/Import**: Configuration backup, export, and import functionality

#### **Backend Configurations**
- **All 11 backends** now have comprehensive quota and retention settings
- **Performance characteristics** matched to appropriate default policies
- **Backend-specific features** like Git LFS, Filecoin deals, S3 lifecycle policies
- **Network resilience** for remote backends (SSHFS, FTP)
- **Collaboration controls** for social backends (GitHub, HuggingFace, Drive)

### 📚 Documentation Updates

#### **New Documentation Files**
- **[POLICY_SYSTEM_DOCUMENTATION.md](./POLICY_SYSTEM_DOCUMENTATION.md)**: Complete policy system guide
- **[CLI_POLICY_USAGE_GUIDE.md](./CLI_POLICY_USAGE_GUIDE.md)**: Comprehensive CLI reference
- **Updated README.md**: Added policy system overview and configuration examples

#### **Enhanced Existing Documentation**
- **README.md**: Updated with three-tier policy system overview
- **Configuration examples**: Updated with policy system integration
- **API Reference**: Added policy management CLI commands
- **Quick Start**: Enhanced with policy configuration examples

### 🎯 System Benefits

#### **Data Management**
- **Prevent Storage Overflow**: Backend quotas prevent unexpected storage limits
- **Preserve Data**: Intelligent retention policies prevent accidental data loss
- **Optimize Performance**: Backend characteristics drive optimal data placement
- **Cost Control**: Automatic tiering and lifecycle management reduce storage costs

#### **Operational Excellence**
- **Policy Inheritance**: Hierarchical policies reduce configuration complexity
- **Automated Management**: Auto-tiering and cleanup reduce manual intervention
- **Comprehensive Monitoring**: Policy effectiveness and quota usage analytics
- **Easy Migration**: Template system and policy copying simplify deployment

#### **Multi-Backend Intelligence**
- **Backend Characteristics**: Speed vs persistence matching for optimal placement
- **Automatic Failover**: Geographic distribution and failover strategies
- **Load Balancing**: Backend weighting for optimal resource utilization
- **Unified Interface**: Single CLI for managing all backend policies

## [3.0.0] - 2025-07-10 - Production Ready MCP Release

### 🎉 Major Release: Production Ready MCP Server Integration

This is a major release marking the transition to **production readiness** with comprehensive MCP server integration, multi-backend storage, and advanced cluster management capabilities.

### ✨ Added

#### **Production MCP Integration**
- **[MCP Development Status Documentation](./MCP_DEVELOPMENT_STATUS.md)**: Comprehensive status and roadmap reference
- **Production Cluster**: 3-node cluster (Master:8998, Worker1:8999, Worker2:9000) validated and operational
- **Multi-Backend Storage**: IPFS, Filecoin, S3, Storacha, HuggingFace, Lassie integration (100% complete)
- **Real-Time Communication**: WebSocket and WebRTC streaming operations
- **Search Integration**: Full-text and vector search with FAISS and sentence-transformers
- **Advanced Filecoin**: Network analytics, miner selection, deal management

#### **Server Architecture**
- **Production Servers**: `standalone_cluster_server.py`, `start_3_node_cluster.py` at root level
- **Development Servers**: Enhanced variants in `servers/` directory with specialized configurations
- **Unified Storage Manager**: Abstract interface for seamless multi-backend operations
- **Migration Controller**: Policy-based data migration between storage systems
- **Performance Monitoring**: Prometheus metrics and comprehensive health endpoints

#### **Documentation & Organization**
- **Project Structure Reorganization**: Maintainer-friendly file organization
- **Enhanced Documentation**: Production deployment guides and API references
- **Testing Infrastructure**: Comprehensive test suite with integration and performance testing
- **Development Workflow**: Clear guidelines for contribution and feature development

#### Cluster Management
- **Leader Election System**: Hierarchical leader election with role priority (Master → Worker → Leecher)
- **Replication Management**: Master-only replication initiation with distributed content management
- **Indexing Services**: Master-only write operations with distributed read access
- **Role-Based Access Control**: Enforced permissions based on node roles
- **Health Monitoring**: Comprehensive cluster health checks and status reporting

#### Container & Orchestration
- **Standalone Cluster Server**: `standalone_cluster_server.py` for containerized deployment
- **3-Node Cluster Launcher**: `start_3_node_cluster.py` for local testing
- **Docker Support**: Multi-stage Dockerfile with development and production builds
- **Docker Compose**: 3-node cluster configuration with automated testing
- **Kubernetes Manifests**: Production-ready StatefulSets, Services, and ConfigMaps
- **Health Probes**: Kubernetes-native health and readiness endpoints

#### API Enhancements
- **Cluster Endpoints**: `/cluster/status`, `/cluster/leader`, `/cluster/peers`
- **Replication API**: `/replication/status`, `/replication/replicate`
- **Indexing API**: `/indexing/stats`, `/indexing/data`, `/indexing/search`
- **VFS Operations**: Virtual filesystem integration through ipfs_fsspec
- **Environment Configuration**: Complete environment variable support

#### Testing & Validation
- **Comprehensive Test Suite**: `comprehensive_cluster_demonstration.py`
- **Cluster Test Results**: Detailed validation documentation
- **Performance Testing**: Load testing and benchmarking
- **CI/CD Integration**: GitHub Actions workflows
- **Production Validation**: 100% test success rate with performance metrics

#### Documentation
- **Complete API Reference**: Comprehensive REST API documentation
- **Getting Started Guide**: Step-by-step setup tutorial
- **Architecture Overview**: System design and component documentation
- **Deployment Guide**: Docker and Kubernetes deployment instructions
- **Test Results**: Detailed validation and performance metrics

### 🔧 Changed
- **Enhanced Daemon Manager**: `enhanced_daemon_manager_with_cluster.py` with cluster capabilities
- **VFS Integration**: Improved `ipfs_fsspec.py` with cluster-aware operations
- **Performance**: Optimized to ~10 seconds startup for 3-node cluster with 49+ RPS throughput
- **Security**: Role-based API access enforcement and container security hardening

### 📊 Performance Metrics
- **Startup Time**: 10 seconds for full 3-node cluster
- **API Latency**: <50ms for most endpoints
- **Throughput**: 49+ RPS sustained load
- **Resource Usage**: 512Mi-2Gi memory, 250m-1000m CPU per node

### 🔒 Security
- **Role-Based Access Control**: Enforced at API level
- **Container Security**: Non-root containers with security hardening
- **Network Isolation**: Kubernetes network policies support

### 🚀 Breaking Changes
1. **Server Entry Point**: Use `standalone_cluster_server.py` instead of legacy servers
2. **Environment Variables**: New configuration system requires environment setup
3. **Container Image**: New multi-stage Docker build process
4. **Kubernetes**: New StatefulSet-based deployment model

### 📚 Documentation
- **[Getting Started](./docs/GETTING_STARTED.md)**: Complete setup tutorial
- **[API Reference](./docs/API_REFERENCE.md)**: Comprehensive API documentation
- **[Architecture](./docs/ARCHITECTURE.md)**: System design documentation
- **[Deployment Guide](./CLUSTER_DEPLOYMENT_GUIDE.md)**: Container deployment guide
- **[Test Results](./CLUSTER_TEST_RESULTS.md)**: Validation documentation

## [0.3.0] - 2025-07-03 - Production Ready Release

### 🎉 Production Ready Status Achieved
- **✅ 100% Test Coverage**: All 9 comprehensive tests passing
- **✅ Complete Integration**: All four installer systems working perfectly
- **✅ MCP Server Production Ready**: 49+ RPS performance with full functionality
- **✅ Documentation Complete**: All documentation updated and accurate
- **✅ Docker Deployment Ready**: Production-grade container configuration

### Added
- 🎉 **Complete Storacha Integration**: Added `install_storacha` installer for Web3.Storage dependencies
- 🔧 **Four-Installer System**: Now supports IPFS, Lotus, Lassie, and Storacha automatic installation
- 📦 **Auto-Download Enhancement**: Storacha dependencies automatically installed on package import
- 🌐 **Web3.Storage Support**: Python and NPM dependencies for Storacha/Web3.Storage integration
- 📚 **Comprehensive Documentation**: Added detailed installer documentation and usage examples
- ✅ **Full Test Coverage**: All four installers tested and verified working
- 🎯 **Production Status Document**: Complete validation and readiness documentation

### Changed
- 🔄 **Enhanced Auto-Download Logic**: Updated to include Storacha installation marker file checks
- 📈 **Improved Package Exports**: Added `install_storacha` and `INSTALL_STORACHA_AVAILABLE` to package exports
- 🔧 **Updated Installation Process**: Now installs Python packages (requests, urllib3) and NPM packages (w3cli)
- 📊 **Performance Optimization**: Achieved 49+ requests per second with 100% reliability

### Fixed
- 🐛 **Installation Reliability**: Improved error handling and logging for all installers
- 🔍 **Verification System**: Added proper verification methods for Storacha dependencies
- 📁 **Marker File System**: Created installation marker files for tracking installation status
- 🔄 **Lotus Daemon Integration**: Fixed daemon startup and simulation mode fallback
- 📚 **Documentation Accuracy**: All documentation now reflects current functionality

### Technical Validation
- **Test Results**: 9/9 tests passing (100% success rate)
- **Components Tested**: Installer imports, binary availability, instantiation, core imports, availability flags, MCP server integration, documentation accuracy, no critical warnings, Lotus daemon functionality
- **Performance**: 49+ requests per second, <20ms response time, production-grade stability
- **Platform Support**: Linux, macOS, Windows with automatic binary installation

## [Unreleased]

### Added
- 🎉 **Complete Storacha Integration**: Added `install_storacha` installer for Web3.Storage dependencies
- 🔧 **Four-Installer System**: Now supports IPFS, Lotus, Lassie, and Storacha automatic installation
- 📦 **Auto-Download Enhancement**: Storacha dependencies automatically installed on package import
- 🌐 **Web3.Storage Support**: Python and NPM dependencies for Storacha/Web3.Storage integration
- 📚 **Comprehensive Documentation**: Added detailed installer documentation and usage examples
- ✅ **Full Test Coverage**: All four installers tested and verified working

### Changed
- 🔄 **Enhanced Auto-Download Logic**: Updated to include Storacha installation marker file checks
- 📈 **Improved Package Exports**: Added `install_storacha` and `INSTALL_STORACHA_AVAILABLE` to package exports
- 🔧 **Updated Installation Process**: Now installs Python packages (requests, urllib3) and NPM packages (w3cli)

### Fixed
- 🐛 **Installation Reliability**: Improved error handling and logging for all installers
- 🔍 **Verification System**: Added proper verification methods for Storacha dependencies
- 📁 **Marker File System**: Created installation marker files for tracking installation status

## [0.2.0] - 2025-07-03

### Added
- 🌐 **IPFS Installer**: Automatic installation of IPFS (Kubo) binaries
- 🔗 **Lotus Installer**: Automatic installation of Lotus daemon and miner
- 📦 **Lassie Installer**: Automatic installation of Lassie retrieval client
- 🤖 **MCP Server**: Production-ready Model Context Protocol server
- 🔧 **Auto-Download System**: Automatic binary installation on package import
- 📊 **Performance Metrics**: 49+ requests per second with 100% test success rate
- 🐳 **Docker Support**: Complete Docker deployment configuration
- 📚 **Comprehensive Documentation**: Complete API documentation and usage examples

### Technical Details
- **Architecture**: Multi-platform binary installation (Linux, macOS, Windows)
- **Dependencies**: Smart dependency detection and installation
- **Logging**: Comprehensive logging for installation progress and errors
- **Testing**: 100% test coverage with comprehensive validation suite
- **API**: FastAPI-based REST API with JSON-RPC 2.0 MCP support

## [0.1.0] - 2025-06-01

### Added
- 🎯 **Initial Release**: Core IPFS toolkit functionality
- 🔧 **Basic Installation**: Manual binary installation scripts
- 📦 **Package Structure**: Initial Python package organization
- 🧪 **Test Framework**: Basic testing infrastructure

---

## Migration Guide

### From 0.1.x to 0.2.x

1. **Auto-Installation**: Binaries are now automatically installed on import
2. **New Installers**: Use the new installer classes for manual installation
3. **Updated API**: Some API endpoints have changed for better MCP compatibility

### From 0.2.x to Latest

1. **Storacha Integration**: New `install_storacha` installer available
2. **Enhanced Auto-Download**: Now includes Storacha dependencies
3. **Updated Documentation**: See new installer documentation

## Support

For issues, questions, or contributions:
- 🐛 **GitHub Issues**: [Report bugs](https://github.com/endomorphosis/ipfs_kit_py/issues)
- 📧 **Email**: starworks5@gmail.com
- 📚 **Documentation**: Check the `docs/` directory

## Contributors

- **Benjamin Barber** - *Initial work and maintenance* - starworks5@gmail.com

## License

This project is licensed under the AGPL-3.0-or-later License - see the [LICENSE](LICENSE) file for details.

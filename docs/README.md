# IPFS Kit Python Documentation

Welcome to the comprehensive documentation for IPFS Kit Python - a production-ready Python toolkit for IPFS operations with advanced cluster management and MCP server integration.

## �� Documentation Structure

### Quick Start Guides

- **[Installation Guide](installation_guide.md)** - Get started with IPFS Kit Python
- **[Quick Reference](QUICK_REFERENCE.md)** - Common commands and operations
- **[Validation Quick Start](VALIDATION_QUICK_START.md)** - Validate your installation

### Core Documentation

#### API & Reference
- **[API Reference](api/api_reference.md)** - Complete API documentation
- **[CLI Reference](api/cli_reference.md)** - Command-line interface guide
- **[Core Concepts](api/core_concepts.md)** - Understanding IPFS Kit architecture
- **[High-Level API](api/high_level_api.md)** - Simplified API for common operations

#### Features
- **[Pin Management](features/pin-management/)** - Content pinning and replication
  - [Pin Management Guide](features/pin-management/PIN_MANAGEMENT_GUIDE.md)
  - [Quick Start](features/pin-management/PIN_QUICK_START.md)
  - [Filecoin Integration](features/pin-management/FILECOIN_PIN_USER_GUIDE.md)
- **[Auto-Healing](features/auto-healing/)** - Automated error detection and fixing
  - [Auto-Healing Guide](features/auto-healing/AUTO_HEALING.md)
  - [Quick Start](features/auto-healing/AUTO_HEALING_QUICKSTART.md)
  - [MCP Auto-Healing](features/auto-healing/MCP_AUTO_HEALING.md)
- **[MCP Server](features/mcp/)** - Model Context Protocol server features
- **[Dashboard](features/dashboard/)** - Web-based monitoring and management

#### Integration
- **[Integration Overview](integration/INTEGRATION_OVERVIEW.md)** - Third-party integration guide
- **[Integration Quick Start](integration/INTEGRATION_QUICK_START.md)** - Getting started with integrations
- **[Integration Cheat Sheet](integration/INTEGRATION_CHEAT_SHEET.md)** - Quick reference
- **[AI/ML Integration](integration/ai-ml/)** - Machine learning and AI features
  - AI/ML Integration, Metrics, Visualization
  - Distributed Training Support
- **Other Integrations**
  - [LangChain](integration/langchain_integration.md)
  - [LlamaIndex](integration/llamaindex_integration.md)
  - [FSSpec](integration/fsspec_integration.md)
  - [IPLD](integration/ipld_integration.md)
  - [LibP2P](integration/libp2p_integration.md)
  - [IPFS Datasets](integration/IPFS_DATASETS_INTEGRATION.md)

#### Operations & Management
- **[Cluster Management](operations/cluster_management.md)** - Multi-node cluster operations
- **[Cluster Monitoring](operations/cluster_monitoring.md)** - Monitoring cluster health
- **[Observability](operations/observability.md)** - Logging, metrics, and tracing
- **[Performance Metrics](operations/performance_metrics.md)** - Performance monitoring
- **[Resource Management](operations/resource_management.md)** - Resource allocation and limits

#### Deployment
- **[Containerization](containerization.md)** - Docker and container deployment
- **[CI/CD](deployment/ci-cd/)** - Continuous integration and deployment
  - [CI/CD Automation](deployment/ci-cd/CI_CD_AUTOMATION_SUMMARY.md)
  - [Quick Reference](deployment/ci-cd/CI_CD_AUTOMATION_QUICK_REFERENCE.md)
- **[Docker Deployment](deployment/docker/)** - Docker-specific guides
- **[ARM64 Support](deployment/arm64/)** - ARM64 architecture deployment
- **[Multi-Architecture](deployment/multi-arch/)** - Multi-arch build and deployment

#### Technical Reference
- **[Storage Backends](reference/storage_backends.md)** - Available storage backend options
- **[Metadata Index](reference/metadata_index.md)** - Metadata indexing system
- **[Write-Ahead Log](reference/write_ahead_log.md)** - WAL implementation details
- **[Tiered Cache](reference/tiered_cache.md)** - Multi-tier caching system
- **[Streaming Guide](reference/streaming_guide.md)** - Streaming data operations
- **[Telemetry](reference/)** - WAL telemetry and monitoring

#### Architecture
- **[Architecture Overview](architecture/)** - System architecture documentation
- **[MCP Integration](architecture/MCP_INTEGRATION_ARCHITECTURE.md)** - MCP architecture
- **[Backend Architecture](architecture/BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md)** - Backend design
- **[Filesystem Backend](architecture/FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md)** - Filesystem backend

#### Development
- **[Testing Guide](development/testing_guide.md)** - How to test your code
- **[Async Architecture](development/async_architecture.md)** - Async/await patterns

### Additional Resources

#### Guides
- **[User Guides](guides/)** - Step-by-step guides for common tasks
  - [CLI Policy Usage](guides/CLI_POLICY_USAGE_GUIDE.md)
  - [Cluster Deployment](guides/CLUSTER_DEPLOYMENT_GUIDE.md)
  - [Secure Credentials](guides/SECURE_CREDENTIALS_GUIDE.md)

#### Testing Documentation
- **[Testing](testing/)** - Test documentation and reports
  - [Test Documentation](testing/100_PERCENT_COVERAGE_INITIATIVE.md)
  - [Test Health Matrix](testing/TEST_HEALTH_MATRIX.md)

#### Advanced Topics
- **[Filesystem Journal](filesystem_journal.md)** - Filesystem journaling
- **[Metadata Replication](metadata_replication.md)** - Cross-node metadata sync
- **[Knowledge Graph](knowledge_graph.md)** - GraphRAG integration
- **[Advanced Prefetching](advanced_prefetching.md)** - Predictive content loading
- **[Probabilistic Data Structures](probabilistic_data_structures.md)** - Bloom filters, etc.

### External Documentation
- **[IPFS Docs](ipfs-docs/)** - Official IPFS documentation references
- **[LibP2P Integration](libp2p_integration/)** - LibP2P networking
- **[IPLD Specifications](py-ipld-*)** - IPLD codec implementations

### Archived Documentation
- **[ARCHIVE](ARCHIVE/)** - Historical documentation and status reports
  - Implementation summaries
  - Status reports
  - Fix documentation
  - Test reports

## 🔍 Finding Documentation

### By Topic

**Getting Started**
→ [Installation Guide](installation_guide.md) → [Quick Reference](QUICK_REFERENCE.md)

**Using the API**
→ [API Reference](api/api_reference.md) → [Core Concepts](api/core_concepts.md) → [Examples](../examples/)

**Deploying**
→ [Containerization](containerization.md) → [CI/CD](deployment/ci-cd/) → [Docker](deployment/docker/)

**Integrating**
→ [Integration Overview](integration/INTEGRATION_OVERVIEW.md) → [Quick Start](integration/INTEGRATION_QUICK_START.md)

**Operating**
→ [Cluster Management](operations/cluster_management.md) → [Monitoring](operations/cluster_monitoring.md)

**Troubleshooting**
→ [Auto-Healing](features/auto-healing/AUTO_HEALING.md) → [Testing Guide](development/testing_guide.md)

### By Role

**Developers**
- [API Reference](api/), [Testing Guide](development/testing_guide.md), [Examples](../examples/)

**Operators**
- [Operations](operations/), [Monitoring](operations/cluster_monitoring.md), [Deployment](deployment/)

**Integrators**
- [Integration](integration/), [API Reference](api/), [Examples](../examples/)

**Contributors**
- [Development](development/), [Testing](testing/), [Architecture](architecture/)

## 📖 Documentation Conventions

### Status Badges
- ✅ **Production Ready** - Fully tested and production-ready
- 🚧 **In Progress** - Under active development
- 📋 **Planned** - Planned for future release
- 🗄️ **Archived** - Historical documentation

### File Organization
- `UPPERCASE.md` - Major documentation files
- `lowercase.md` - Technical references
- Subdirectories organized by category

### Links
- Relative links used throughout
- All links verified during documentation updates

## 🤝 Contributing to Documentation

Found an issue or want to improve the docs?

1. **Report Issues** - Open an issue describing the problem
2. **Submit PR** - Fix typos, broken links, or outdated information
3. **Add Examples** - Share your use cases and examples
4. **Improve Clarity** - Help make docs more accessible

## 📝 License

This documentation is part of IPFS Kit Python and is licensed under AGPL-3.0.

---

**Need help?** Check the [Quick Reference](QUICK_REFERENCE.md) or open an issue on GitHub.

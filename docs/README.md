# IPFS Kit Python - Complete Documentation

Welcome to the comprehensive documentation for **IPFS Kit Python**. This guide will help you find exactly what you need, whether you're just getting started or building advanced distributed systems.

## 🎯 Start Here

**New to IPFS Kit?** Follow this path:
1. [Installation Guide](installation_guide.md) - Get everything set up (10 minutes)
2. [Quick Reference](QUICK_REFERENCE.md) - Learn basic operations (5 minutes)
3. [API Reference](api/api_reference.md) - Explore the full API (30 minutes)
4. [Examples](../examples/) - See code in action

**Building something specific?** Jump to:
- [Cluster Setup](#cluster--distributed-storage) - Multi-node deployments
- [AI/ML Integration](#aiml-features) - Machine learning workloads
- [MCP Server](#mcp-server--tools) - Model Context Protocol
- [Production Deployment](#deployment--operations) - Docker, Kubernetes, CI/CD

## 📚 Documentation Map

### Getting Started (For Everyone)

**[Installation Guide](installation_guide.md)** - *Start here if you're new*
- System requirements and dependencies
- Installation methods (pip, source, Docker)
- Initial configuration
- Verification steps
- **Answers:** "How do I install?" "What do I need?"

**[Quick Reference](QUICK_REFERENCE.md)** - *Your cheat sheet*
- Common operations with examples
- CLI commands
- Python API quick start
- Troubleshooting tips
- **Answers:** "How do I...?" "What's the command for...?"

**[Validation Quick Start](VALIDATION_QUICK_START.md)** - *Verify your setup*
- Test installation
- Run example operations
- Check cluster connectivity
- **Answers:** "Is it working?" "How do I test?"

### Core APIs (For Developers)

**[API Reference](api/api_reference.md)** - *Complete API documentation*
- All classes and methods
- Parameter descriptions
- Return value documentation
- Usage examples
- **Answers:** "What methods are available?" "How do I use X?"

**[CLI Reference](api/cli_reference.md)** - *Command-line interface*
- All CLI commands
- Options and flags
- Examples for each command
- **Answers:** "What CLI commands exist?" "How do I use ipfs-kit?"

**[Core Concepts](api/core_concepts.md)** - *Understanding the architecture*
- System design overview
- Key abstractions
- Data flow
- Component interactions
- **Answers:** "How does it work?" "What's the architecture?"

**[High-Level API](api/high_level_api.md)** - *Simplified interface*
- Easy-to-use wrappers
- Common patterns
- Best practices
- **Answers:** "What's the easiest way?" "Are there shortcuts?"

### Features (Capabilities You Can Use)

#### Content Management & Storage

**[Pin Management](features/pin-management/)** - *Keep content available*
- [Pin Management Guide](features/pin-management/PIN_MANAGEMENT_GUIDE.md) - Complete guide
- [Quick Start](features/pin-management/PIN_QUICK_START.md) - Get started fast
- [Filecoin Integration](features/pin-management/FILECOIN_PIN_USER_GUIDE.md) - Filecoin pinning
- [Dashboard Features](features/pin-management/PIN_DASHBOARD_FEATURES.md) - Web interface
- **Answers:** "How do I keep content?" "What's pinning?" "How does replication work?"

#### Advanced Features

**[Auto-Healing](features/auto-healing/)** - *Automatic error recovery*
- [Auto-Healing Guide](features/auto-healing/AUTO_HEALING.md) - System overview
- [Quick Start](features/auto-healing/AUTO_HEALING_QUICKSTART.md) - Setup in 5 minutes
- [MCP Auto-Healing](features/auto-healing/MCP_AUTO_HEALING.md) - MCP integration
- **Answers:** "Can it fix itself?" "How does error recovery work?"

**[MCP Server](features/mcp/)** - *Model Context Protocol server*
- MCP tool integration
- Server configuration
- Custom tools development
- **Answers:** "What's MCP?" "How do I use it with AI?"

**[Dashboard](features/dashboard/)** - *Web-based management*
- Dashboard setup
- Monitoring and metrics
- Configuration management
- **Answers:** "Is there a GUI?" "How do I monitor?"

**[VFS (Virtual File System)](features/vfs/)** - *Advanced file operations*
- [VFS Management](features/vfs/VFS_MANAGEMENT_CONSOLIDATION.md)
- Virtual filesystem operations
- **Answers:** "Can I mount IPFS?" "File system integration?"

**[GraphRAG](features/graphrag/)** - *Knowledge graphs & RAG*
- [GraphRAG Documentation](features/graphrag/ENHANCED_GRAPHRAG_MCP_DOCUMENTATION.md)
- [VFS Integration](features/graphrag/VFS_BUCKET_GRAPHRAG_INTEGRATION.md)
- **Answers:** "What's GraphRAG?" "How do I use vector search?"

### Integration (Connect with Other Tools)

**[Integration Overview](integration/INTEGRATION_OVERVIEW.md)** - *Third-party integrations*
- Available integrations
- Integration patterns
- Best practices
- **Answers:** "What can I integrate?" "How do integrations work?"

**[Integration Quick Start](integration/INTEGRATION_QUICK_START.md)** - *Get started with integrations*

**[Integration Cheat Sheet](integration/INTEGRATION_CHEAT_SHEET.md)** - *Quick reference*

#### AI/ML Features

**[AI/ML Integration](integration/ai-ml/)** - *Machine learning support*
- [AI/ML Integration Guide](integration/ai-ml/ai_ml_integration.md) - Overview
- [Distributed Training](integration/ai-ml/ai_ml_distributed_training.md) - Train models
- [Metrics & Visualization](integration/ai-ml/ai_ml_metrics.md) - Track performance
- **Answers:** "Can I store models?" "How do I track metrics?"

#### Framework Integration

**[LangChain](integration/langchain_integration.md)** - *LangChain framework*
- LangChain document loaders
- IPFS-backed chains
- **Answers:** "Does it work with LangChain?"

**[LlamaIndex](integration/llamaindex_integration.md)** - *LlamaIndex framework*
- Index storage on IPFS
- Query engines
- **Answers:** "Does it work with LlamaIndex?"

#### Protocol Integration

**[IPFS Datasets](integration/IPFS_DATASETS_INTEGRATION.md)** - *Dataset management*
- Large dataset handling
- Chunking and reassembly
- **Answers:** "How do I store big datasets?"

**[FSSpec](integration/fsspec_integration.md)** - *Filesystem specification*
- Filesystem abstraction
- Pandas integration
- **Answers:** "Can I use it like a filesystem?"

**[IPLD](integration/ipld_integration.md)** - *IPLD data structures*
- IPLD DAGs
- Custom codecs
- **Answers:** "What's IPLD?" "How do I work with DAGs?"

**[LibP2P](integration/libp2p_integration.md)** - *P2P networking*
- [Implementation Plan](integration/LIBP2P_IMPLEMENTATION_PLAN.md)
- Peer discovery
- Network configuration
- **Answers:** "How does P2P work?" "Can I customize networking?"

### Cluster & Distributed Storage

**[Cluster Management](operations/cluster_management.md)** - *Multi-node setup*
- Cluster architecture
- Node roles (master/worker/leecher)
- Leader election
- Scaling strategies
- **Answers:** "How do I set up a cluster?" "What's leader election?"

**[Cluster Monitoring](operations/cluster_monitoring.md)** - *Health & metrics*
- Health checks
- Performance monitoring
- Alert configuration
- **Answers:** "How do I monitor my cluster?" "Is it healthy?"

**[Cluster State](operations/cluster_state.md)** - *State management*
- State synchronization
- Consistency guarantees
- **Answers:** "How is state managed?" "What about consistency?"

**[Cluster Authentication](operations/cluster_authentication.md)** - *Security*
- Authentication setup
- Authorization policies
- **Answers:** "How do I secure my cluster?"

### Deployment & Operations

**[Containerization](containerization.md)** - *Docker & containers*
- Docker images
- Container configuration
- **Answers:** "How do I use Docker?" "Is there an image?"

**[CI/CD Automation](deployment/ci-cd/)** - *Continuous deployment*
- [CI/CD Summary](deployment/ci-cd/CI_CD_AUTOMATION_SUMMARY.md)
- [Quick Reference](deployment/ci-cd/CI_CD_AUTOMATION_QUICK_REFERENCE.md)
- [Integration Plan](deployment/ci-cd/CI_CD_AUTOMATION_INTEGRATION_PLAN.md)
- [GitHub Runner Setup](deployment/ci-cd/GITHUB_RUNNER_SETUP.md)
- [GitHub API Caching](deployment/ci-cd/GITHUB_API_CACHING.md)
- **Answers:** "How do I automate deployment?" "CI/CD setup?"

**[Docker Deployment](deployment/docker/)** - *Docker-specific*

**[ARM64 Support](deployment/arm64/)** - *ARM architecture*
- ARM64 builds
- Raspberry Pi deployment
- **Answers:** "Does it run on ARM?" "Raspberry Pi support?"

**[Multi-Architecture](deployment/multi-arch/)** - *Multi-platform*

**[Observability](operations/observability.md)** - *Monitoring & logging*
- Logging configuration
- Metrics collection
- Tracing setup
- **Answers:** "How do I debug?" "Where are the logs?"

**[Performance Metrics](operations/performance_metrics.md)** - *Performance tuning*
- [Metrics Optimization](operations/METRICS_COMMAND_OPTIMIZATION.md)
- Performance benchmarks
- Optimization tips
- **Answers:** "How fast is it?" "How do I optimize?"

**[Resource Management](operations/resource_management.md)** - *Resource limits*
- Memory management
- Disk usage
- Network bandwidth
- **Answers:** "How much memory does it use?" "Can I limit resources?"

### Technical Reference

**[Architecture](architecture/)** - *System design*
- [MCP Integration Architecture](architecture/MCP_INTEGRATION_ARCHITECTURE.md)
- [Backend Architecture](architecture/BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md)
- [Filesystem Backend](architecture/FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md)
- [Refactored Architecture](architecture/REFACTORED_ARCHITECTURE_README.md)
- **Answers:** "How is it designed?" "What's the architecture?"

**[Storage Backends](reference/storage_backends.md)** - *Storage options*
- [Enhanced Analytics](reference/ENHANCED_STORAGE_BACKEND_ANALYTICS.md)
- Available backends
- Performance characteristics
- **Answers:** "Where is data stored?" "What backends exist?"

**[Metadata Index](reference/metadata_index.md)** - *Fast lookups*
- Index structure
- Query performance
- **Answers:** "How does search work?" "Index internals?"

**[Write-Ahead Log](reference/write_ahead_log.md)** - *Data consistency*
- WAL design
- Recovery procedures
- **Answers:** "How is data protected?" "What about crashes?"

**[Tiered Cache](reference/tiered_cache.md)** - *Caching strategy*
- Cache layers
- Eviction policies
- **Answers:** "How does caching work?" "Cache configuration?"

**[Protobuf](reference/PROTOBUF_ANALYSIS_AND_SOLUTION.md)** - *Protocol buffers*

**[Telemetry](reference/wal_telemetry_api.md)** - *System telemetry*

### Development (For Contributors)

**[Testing Guide](development/testing_guide.md)** - *Running tests*
- Test suite organization
- Writing tests
- CI integration
- **Answers:** "How do I test?" "Where are the tests?"

**[Async Architecture](development/async_architecture.md)** - *Async patterns*
- Async/await usage
- Concurrency patterns
- **Answers:** "How does async work?" "Concurrency model?"

**[API Stability](api_stability.md)** - *API versioning*
- Stability guarantees
- Breaking changes
- **Answers:** "Will APIs change?" "Backwards compatibility?"

### Guides & Tutorials

**[User Guides](guides/)** - *Step-by-step tutorials*
- [CLI Policy Usage](guides/CLI_POLICY_USAGE_GUIDE.md)
- [Cluster Deployment](guides/CLUSTER_DEPLOYMENT_GUIDE.md)
- [Secure Credentials](guides/SECURE_CREDENTIALS_GUIDE.md)
- [Config Fix Reference](guides/CONFIG_SAVE_FIX_REFERENCE.md)
- [Multiprocessing](guides/MULTIPROCESSING_ENHANCEMENTS_README.md)
- [Auto Update](guides/auto_update_install.md)
- **Answers:** Step-by-step "how to" guides

**[Documentation Guide](guides/DOCUMENTATION_GUIDE.md)** - *Writing docs*

**[Reorganization Guide](guides/REORGANIZATION_GUIDE.md)** - *Project structure*

### Additional Topics

**[Filesystem Journal](filesystem_journal.md)** - *Filesystem journaling*

**[Knowledge Graph](knowledge_graph.md)** - *Knowledge graph integration*

**[IPFS Dataloader](ipfs_dataloader.md)** - *Data loading utilities*

**[Metadata Replication](metadata_replication.md)** - *Cross-node replication*

**[Advanced Prefetching](advanced_prefetching.md)** - *Predictive loading*

**[Probabilistic Data Structures](probabilistic_data_structures.md)** - *Bloom filters, etc.*

**[Lotus Daemon Management](lotus_daemon_management.md)** - *Filecoin Lotus*

**[Simplified Bucket Architecture](simplified_bucket_architecture.md)** - *Bucket design*

**[Credential Management](credential_management.md)** - *Secrets handling*

**[Extensions](extensions.md)** - *Plugin system*

**[Integrated Search](integrated_search.md)** - *Search capabilities*

**[Documentation Plan](documentation_plan.md)** - *Doc strategy*

**[Performance Optimization](performance_optimization_roadmap.md)** - *Optimization roadmap*

**[Telemetry API](telemetry_api.md)** - *Telemetry endpoints*

**[PyPI Release](pypi_release.md)** - *Package release*

**[Index](index.md)** - *Documentation index*

### Historical & Archive

**[Testing](testing/)** - *Test documentation*
- [100% Coverage Initiative](testing/100_PERCENT_COVERAGE_INITIATIVE.md)
- [Test Health Matrix](testing/TEST_HEALTH_MATRIX.md)
- Test reports and summaries

**[ARCHIVE](ARCHIVE/)** - *Historical documentation*
- Previous implementations
- Old status reports
- Deprecated features
- Migration guides

## 🗺️ Learning Paths

### Path 1: Quick Start (30 minutes)
1. [Installation Guide](installation_guide.md)
2. [Quick Reference](QUICK_REFERENCE.md) - basic operations
3. [Examples](../examples/) - run sample code
4. [API Reference](api/api_reference.md) - explore methods

### Path 2: Cluster Deployment (2 hours)
1. [Installation Guide](installation_guide.md)
2. [Cluster Management](operations/cluster_management.md)
3. [Cluster Monitoring](operations/cluster_monitoring.md)
4. [Observability](operations/observability.md)
5. [Deployment Guides](deployment/)

### Path 3: AI/ML Integration (1 hour)
1. [Quick Reference](QUICK_REFERENCE.md)
2. [AI/ML Integration](integration/ai-ml/ai_ml_integration.md)
3. [LangChain Integration](integration/langchain_integration.md)
4. [LlamaIndex Integration](integration/llamaindex_integration.md)
5. [Examples](../examples/) - ML examples

### Path 4: Production Deployment (3 hours)
1. [Installation Guide](installation_guide.md)
2. [Containerization](containerization.md)
3. [CI/CD Automation](deployment/ci-cd/)
4. [Observability](operations/observability.md)
5. [Performance Metrics](operations/performance_metrics.md)
6. [Auto-Healing](features/auto-healing/)

### Path 5: Advanced Development (4+ hours)
1. [Core Concepts](api/core_concepts.md)
2. [Architecture](architecture/)
3. [Storage Backends](reference/storage_backends.md)
4. [Async Architecture](development/async_architecture.md)
5. [Testing Guide](development/testing_guide.md)
6. Source code exploration

## 🔍 Finding What You Need

### By Question Type

**"How do I install/setup?"**
→ [Installation Guide](installation_guide.md)

**"How do I use X feature?"**
→ [Quick Reference](QUICK_REFERENCE.md) → [API Reference](api/api_reference.md)

**"How does X work internally?"**
→ [Core Concepts](api/core_concepts.md) → [Architecture](architecture/)

**"How do I deploy to production?"**
→ [Containerization](containerization.md) → [CI/CD](deployment/ci-cd/)

**"How do I integrate with Y?"**
→ [Integration Overview](integration/INTEGRATION_OVERVIEW.md) → Specific integration

**"What can I build with this?"**
→ [Examples](../examples/) → [Use Cases in main README](../README.md)

**"Something's not working"**
→ [Auto-Healing](features/auto-healing/) → [Observability](operations/observability.md)

**"How do I contribute?"**
→ [Testing Guide](development/testing_guide.md) → [GitHub](https://github.com/endomorphosis/ipfs_kit_py)

### By Role

**Application Developers**
- [API Reference](api/api_reference.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [Integration](integration/)
- [Examples](../examples/)

**Data Scientists**
- [AI/ML Integration](integration/ai-ml/)
- [IPFS Datasets](integration/IPFS_DATASETS_INTEGRATION.md)
- [LangChain](integration/langchain_integration.md)
- [LlamaIndex](integration/llamaindex_integration.md)

**DevOps/SRE**
- [Cluster Management](operations/cluster_management.md)
- [Deployment](deployment/)
- [Observability](operations/observability.md)
- [Auto-Healing](features/auto-healing/)

**System Architects**
- [Architecture](architecture/)
- [Core Concepts](api/core_concepts.md)
- [Storage Backends](reference/storage_backends.md)
- [Performance](operations/performance_metrics.md)

**Contributors**
- [Testing Guide](development/testing_guide.md)
- [API Stability](api_stability.md)
- [Development](development/)
- [GitHub](https://github.com/endomorphosis/ipfs_kit_py)

## 📖 Documentation Conventions

### File Naming
- `UPPERCASE.md` - Major guides and documentation
- `lowercase.md` - Technical references and specifications

### Sections
Each document includes:
- **Overview** - What it covers
- **Prerequisites** - What you need first
- **Examples** - Code samples
- **Reference** - Detailed information
- **See Also** - Related documents

### Status Indicators
- ✅ **Production Ready** - Stable and tested
- 🚧 **Beta** - Usable but evolving
- 📋 **Planned** - Future feature
- 🗄️ **Archived** - Historical reference

## 🤝 Contributing to Documentation

Found an issue or want to help?

1. **Report Issues** - Open an issue for errors or confusion
2. **Suggest Improvements** - PRs welcome for clarity, examples, fixes
3. **Add Examples** - Share your use cases
4. **Fill Gaps** - Help document undocumented features

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## 📝 Version & Updates

- **Version:** 0.3.0
- **Last Updated:** February 2, 2026
- **Python:** 3.12+ required

## 🔗 Quick Links

- **[Main README](../README.md)** - Project overview
- **[GitHub Repository](https://github.com/endomorphosis/ipfs_kit_py)**
- **[Issue Tracker](https://github.com/endomorphosis/ipfs_kit_py/issues)**
- **[Examples](../examples/)** - Code examples

---

**Need help?** Start with the [Quick Reference](QUICK_REFERENCE.md) or open an [issue](https://github.com/endomorphosis/ipfs_kit_py/issues).

**Can't find something?** Use GitHub's search or open a [discussion](https://github.com/endomorphosis/ipfs_kit_py/discussions).

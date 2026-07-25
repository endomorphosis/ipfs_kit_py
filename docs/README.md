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
- [MCP Server](#features-capabilities-you-can-use) - Model Context Protocol
- [Production Deployment](#deployment--operations) - Docker, Kubernetes, CI/CD

## 📚 Documentation Map

### Repository Data

**[Data Directory](../data/README.md)** - *Maintained configuration, sample, and validation data*
- [Configuration files](../data/configs/README.md)
- [Sample data](../data/samples/README.md)
- [Test and analysis results](../data/results/README.md)

### Getting Started (For Everyone)

**[Installation Guide](installation_guide.md)** - *Start here if you're new*
- System requirements and dependencies
- [Configuration Requirements](../config/requirements.txt) - WebRTC monitoring and async runtime dependencies
- Installation methods (pip, source, Docker)
- Initial configuration
- Verification steps
- **Answers:** "How do I install?" "What do I need?"

**[Installer Documentation](INSTALLER_DOCUMENTATION.md)** - *Install optional IPFS Kit dependencies*
- Installer entry points exposed by the package
- Optional dependency and external-daemon considerations
- CI and system-safety notes before downloading binaries

**[Submodule-Scope Release Checklist](RELEASE_CHECKLIST_SUBMODULE_SCOPE.md)** - *Prepare submodule-scoped VFS integration releases and merges*
- Scope and runtime policy checks
- Required test evidence
- Metadata, sync, conflict-policy, and sign-off checks

**[Quick Reference](QUICK_REFERENCE.md)** - *Your cheat sheet*
- Common operations with examples
- CLI commands
- Python API quick start
- Troubleshooting tips
- **Answers:** "How do I...?" "What's the command for...?"

**[Validation Quick Start](guides/VALIDATION_QUICK_START.md)** - *Verify your setup*
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

**[Agent Integration Guide](api_generated/AGENT_GUIDE.md)** - *Programming-agent quick reference*
- Project entry points and common operations
- Configuration, testing, and development commands
- Links to generated module and example references

### Features (Capabilities You Can Use)

#### Content Management & Storage

**[Storage Backends](reference/storage_backends.md)** - *Multi-backend storage system*
- [Enhanced Analytics](reference/ENHANCED_STORAGE_BACKEND_ANALYTICS.md)
- 6 integrated backends: IPFS, Filecoin, S3, Storacha, HuggingFace, Lassie
- Multi-tier storage strategy (memory → disk → network → cloud)
- Automatic content distribution across backends
- **Answers:** "What storage backends are available?" "How do I use S3/Filecoin?" "Multi-backend setup?"

**[Tiered Cache](reference/tiered_cache.md)** - *Advanced multi-tier caching*
- ARC (Adaptive Replacement Cache) algorithm
- Memory cache (100MB default) + Disk cache (1GB+ default)
- Heat-based eviction and automatic tier promotion
- Zero-copy memory-mapped access for large files
- **Answers:** "How does caching work?" "Cache configuration?" "Performance optimization?"

**[Replica Management](operations/cluster_management.md)** - *Content replication strategies*
- Cluster-based replication with configurable factors
- Replication policies: distributed, local-first, geo-aware, cost-optimized
- Automatic repair and health monitoring
- Min/max replica constraints with auto-repair
- **Answers:** "How do replicas work?" "Replication strategies?" "High availability setup?"

**[Pin Management](features/pin-management/PIN_MANAGEMENT_GUIDE.md)** - *Keep content available*
- [Pin Management Guide](features/pin-management/PIN_MANAGEMENT_GUIDE.md) - Complete guide
- [Quick Start](features/pin-management/PIN_QUICK_START.md) - Get started fast
- [Implementation Summary](features/pin-management/PIN_IMPLEMENTATION_README.md) - Dashboard implementation, MCP tools, and rollout status
- [Filecoin Integration](features/pin-management/FILECOIN_PIN_USER_GUIDE.md) - Filecoin pinning
- [Filecoin Pin Configuration](features/pin-management/FILECOIN_PIN_CONFIGURATION.md) - Configuration examples for Filecoin-backed pinning
- [Dashboard Features](features/pin-management/PIN_DASHBOARD_FEATURES.md) - Web interface
- [Visual Guide](features/pin-management/PIN_VISUAL_GUIDE.md) - Dashboard mockups, flows, and interaction states
- **Answers:** "How do I keep content?" "What's pinning?" "How does replication work?"

#### Advanced Features

**[Auto-Healing](features/auto-healing/AUTO_HEALING.md)** - *Automatic error recovery*
- [Auto-Healing Guide](features/auto-healing/AUTO_HEALING.md) - System overview
- [Quick Start](features/auto-healing/AUTO_HEALING_QUICKSTART.md) - Setup in 5 minutes
- [Implementation Summary](features/auto-healing/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md) - Workflow automation architecture and validation
- [Workflow Quick Start](../AUTO_HEALING_QUICK_START.md) - Recover from failed GitHub Actions workflows
- [Workflow Examples](features/auto-healing/AUTO_HEALING_EXAMPLES.md) - Real-world auto-healing scenarios
- [MCP Auto-Healing](features/auto-healing/MCP_AUTO_HEALING.md) - MCP integration
- [GitHub Copilot Auto-Healing Guide](features/copilot/COPILOT_AUTO_HEALING_GUIDE.md) - Configure and operate Copilot-powered workflow recovery
- [GitHub Copilot Auto-Healing Implementation Summary](features/copilot/COPILOT_AUTO_HEALING_IMPLEMENTATION_SUMMARY.md) - Implementation, validation, architecture, and deployment summary
- **Answers:** "Can it fix itself?" "How does error recovery work?"

**[MCP Server](features/mcp/MCP_DASHBOARD_VALIDATION_REPORT.md)** - *Model Context Protocol server*
- MCP tool integration
- Server configuration
- Custom tools development
- **Answers:** "What's MCP?" "How do I use it with AI?"

**[Dashboard](features/dashboard/DASHBOARD_CLARIFICATION.md)** - *Web-based management*
- Dashboard setup
- Monitoring and metrics
- Configuration management
- **Answers:** "Is there a GUI?" "How do I monitor?"

**[VFS (Virtual File System)](features/vfs/VFS_MANAGEMENT_CONSOLIDATION.md)** - *POSIX-like virtual filesystem on IPFS*
- [VFS Management](features/vfs/VFS_MANAGEMENT_CONSOLIDATION.md) - Complete VFS system
- [VFS Contract Specification](VFS_CONTRACT_SPEC.md) - Canonical request, response, and synchronization contracts
- [Filesystem Journal](filesystem_journal.md) - Change tracking and journaling
- POSIX-like operations: mkdir, ls, mv, rm, cp
- VFS buckets with quotas and policies
- Automatic metadata extraction and indexing
- Journal replication across nodes
- **Answers:** "How do I use IPFS like a filesystem?" "What are VFS buckets?" "Filesystem operations?"

**[GraphRAG](features/graphrag/ENHANCED_GRAPHRAG_MCP_DOCUMENTATION.md)** - *Knowledge graphs & intelligent search*
- [GraphRAG Documentation](features/graphrag/ENHANCED_GRAPHRAG_MCP_DOCUMENTATION.md) - Complete guide
- [VFS Integration](features/graphrag/VFS_BUCKET_GRAPHRAG_INTEGRATION.md) - Auto-indexing
- [GraphRAG & Bucket Metadata Export](GRAPHRAG_AND_BUCKET_EXPORT.md) - GraphRAG improvements and bucket metadata export/import
- [Knowledge Graph](knowledge_graph.md) - Graph-based knowledge management
- Automatic entity extraction and relationship mapping
- 5 search methods: text, graph, vector, SPARQL, hybrid
- RDF triple store for structured knowledge
- Graph analytics (centrality, importance scoring)
- **Answers:** "What's GraphRAG?" "How do I search semantically?" "Knowledge graph setup?" "Vector search?"

**[P2P Workflow Guide](features/P2P_WORKFLOW_GUIDE.md)** - *Distributed workflow coordination*
- [P2P Workflow Quick Reference](features/P2P_WORKFLOW_QUICK_REF.md) - CLI, Python API, MCP tools, and common patterns
- Peer coordination, workflow assignment, tagging, and status management
- **Answers:** "How do I submit a distributed workflow?" "How are workflows assigned to peers?"

### Integration (Connect with Other Tools)

**[Integration Overview](integration/INTEGRATION_OVERVIEW.md)** - *Third-party integrations*
- Available integrations
- Integration patterns
- Best practices
- **Answers:** "What can I integrate?" "How do integrations work?"

**[Integration Quick Start](integration/INTEGRATION_QUICK_START.md)** - *Get started with integrations*

**[Integration Cheat Sheet](integration/INTEGRATION_CHEAT_SHEET.md)** - *Quick reference*

#### AI/ML Features

**[AI/ML Integration](integration/ai-ml/ai_ml_integration.md)** - *Machine learning support*
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

**[CI/CD Automation](deployment/ci-cd/CI_CD.md)** - *Continuous deployment*
- [CI/CD Summary](deployment/ci-cd/CI_CD_AUTOMATION_SUMMARY.md)
- [CI/CD Automation Completion](deployment/ci-cd/CI_CD_AUTOMATION_COMPLETION.md) - Project completion report and implementation roadmap
- [CI/CD Automation Phase 1 Complete](deployment/ci-cd/CI_CD_AUTOMATION_PHASE1_COMPLETE.md) - Phase 1 implementation summary and automation capabilities
- [CI/CD Automation Validation Complete](deployment/ci-cd/CI_CD_AUTOMATION_VALIDATION_COMPLETE.md) - Validation results and resolved automation issues
- [Complete Auto-Healing Implementation Summary](deployment/ci-cd/COMPLETE_AUTO_HEALING_SUMMARY.md) - Comprehensive auto-healing architecture, coverage, and usage
- [Final Auto-Healing Implementation Summary](deployment/ci-cd/FINAL_AUTO_HEALING_SUMMARY.md) - Final implementation status, caching configuration, and operational details
- [Quick Reference](deployment/ci-cd/CI_CD_AUTOMATION_QUICK_REFERENCE.md)
- [CI/CD Workflow Validation Guide](ci-cd/CI_CD_VALIDATION_GUIDE.md) - Validate workflows and CI scripts locally
- [AMD64 Workflow Implementation Summary](ci-cd/amd64/AMD64_WORKFLOW_IMPLEMENTATION_SUMMARY.md) - Self-hosted AMD64 workflow implementation and validation coverage
- [CI/CD Verification Report](ci-cd/CI_CD_VERIFICATION_REPORT.md) - Recorded workflow validation results and maintenance findings
- [GitHub Workflow Fixes Summary](ci-cd/WORKFLOW_FIXES_SUMMARY.md) - Summary of CI configuration and workflow corrections
- [GitHub Workflow Test Fixes](ci-cd/WORKFLOW_TEST_FIXES.md) - Diagnose and address broken workflow test imports, dependencies, and CI exclusions
- [GitHub Actions Runner Quick Start](ci-cd/START_RUNNER_HERE.md) - Start here when setting up a self-hosted runner
- [GitHub Actions Runner Quick Start](ci-cd/RUNNER_QUICK_START.md) - Set up and verify a self-hosted runner in five minutes
- [Set Up Your GitHub Actions Runner](ci-cd/SETUP_RUNNER_NOW.md) - Quick self-hosted runner setup
- [GitHub Actions Runner Scripts Guide](ci-cd/RUNNER_SCRIPTS_GUIDE.md) - Manage, monitor, restart, and remove self-hosted runners
- [GitHub Actions Runner Setup (Complete)](ci-cd/GITHUB_RUNNER_SETUP_COMPLETE.md) - Verified self-hosted runner configuration and operations
- [Integration Plan](deployment/ci-cd/CI_CD_AUTOMATION_INTEGRATION_PLAN.md)
- [GitHub Runner Setup](deployment/ci-cd/GITHUB_RUNNER_SETUP.md)
- [GitHub API Caching](deployment/ci-cd/GITHUB_API_CACHING.md)
- [GitHub Actions Auto-Healing Scripts](../.github/scripts/README.md) - Analyze workflow failures and generate fix proposals
- [GitHub Actions Auto-Healing Workflows](../.github/workflows/AUTO_HEAL_README.md) - Configure and troubleshoot automatic workflow failure recovery
- **Answers:** "How do I automate deployment?" "CI/CD setup?"

**[Docker Deployment](deployment/docker/DOCKER_QUICK_START.md)** - *Docker-specific*
- [Docker Architecture Tests](deployment/docker/DOCKER_ARCH_TESTS.md) - Multi-architecture Docker test workflow and validation
- [Docker Testing Summary](deployment/docker/DOCKER_TESTING_SUMMARY.md) - Container test results and GitHub Actions runner setup
- [Docker Dependency Pre-installation Test Results](deployment/docker/DOCKER_TEST_RESULTS.md) - Verification of pre-installed Lotus dependencies and runtime detection

**[Tailwind CSS Production Build](deployment/TAILWIND_BUILD.md)** - *Build the dashboard stylesheet locally*
- Run the production, development, or watch-mode CSS build
- Review Tailwind content paths, custom styles, and safelisted classes
- **Answers:** "How do I build the dashboard CSS?" "How is Tailwind deployed?"

**[ARM64 Support](deployment/arm64/ARM64_BUILD_FROM_SOURCE.md)** - *ARM architecture*
- ARM64 builds
- Raspberry Pi deployment
- **Answers:** "Does it run on ARM?" "Raspberry Pi support?"

**[Multi-Architecture](deployment/multi-arch/MULTI_ARCH_SUPPORT.md)** - *Multi-platform*
- [Multi-Architecture Runner Setup](deployment/multi-arch/MULTI_ARCH_RUNNER_SETUP.md) - Configure optional ARM64 self-hosted runners and QEMU-based testing
- [Multi-Architecture CI/CD Fix](deployment/multi-arch/MULTI_ARCH_CI_FIX.md) - Dependency, package-manager lock, and cross-architecture CI guidance
- [Multi-Architecture Implementation Summary](deployment/multi-arch/MULTI_ARCH_IMPLEMENTATION_SUMMARY.md) - CI/CD, Docker, package, and architecture-test implementation details

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

**[Architecture](architecture/ARCHITECTURE_MODULE_ORGANIZATION.md)** - *System design*
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

**[Final Test Coverage Report](TEST_COVERAGE_FINAL.md)** - *Final roadmap-feature test results and module coverage*

**[Test Coverage Extension](TEST_COVERAGE_EXTENSION.md)** - *Extended coverage details and follow-up work*
- Coverage additions for S3 Gateway, WASM, analytics, and multi-region features
- Known API mismatches and optional dependency considerations
- Recommended next steps for completing the coverage improvements

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

**[AnyIO Migration Guide](ANYIO_MIGRATION.md)** - *Migrating asynchronous code and tests from `asyncio` to AnyIO*

**[Complete AnyIO Migration Summary](COMPLETE_ANYIO_MIGRATION_SUMMARY.md)** - *Migration results, test coverage, and implementation details*

**[Comprehensive Columnar IPLD Implementation](implementation/COMPREHENSIVE_COLUMNAR_IPLD_IMPLEMENTATION_COMPLETE.md)** - *Columnar IPLD storage, Parquet-CAR conversion, peer distribution, and dashboard integration*

**[Comprehensive Dashboard Enhancement](implementation/COMPREHENSIVE_DASHBOARD_ENHANCEMENT_COMPLETE.md)** - *Comprehensive monitoring, VFS observability, vector and knowledge-base analytics, configuration management, and real-time dashboard capabilities*

**[Comprehensive Error Fixes](implementation/COMPREHENSIVE_ERROR_FIXES_COMPLETE.md)** - *Import compatibility, daemon management, filesystem access, libp2p fallbacks, and resilient error handling*

**[Comprehensive Logging System](implementation/COMPREHENSIVE_LOGGING_IMPLEMENTATION.md)** - *Backend log collection, aggregation, API access, rotation, and dashboard observability*

**[Comprehensive IPFS Kit Improvements](implementation/COMPREHENSIVE_IMPROVEMENTS_COMPLETE.md)** - *Enhanced cluster daemon management, health monitoring, LibP2P recovery, dashboard APIs, and integration testing*

**[CI/CD Workflows Completion Summary](implementation/COMPLETION_SUMMARY.txt)** - *CI/CD workflow validation results, tooling, and continuous-monitoring coverage*

**[Apache Arrow IPC Zero-Copy Implementation](implementation/ARROW_IPC_ZERO_COPY_IMPLEMENTATION.md)** - *Zero-copy daemon access, fallback behavior, and validation*

**[Bucket VFS CLI and MCP Interface Implementation](implementation/BUCKET_VFS_INTERFACES_COMPLETE.md)** - *CLI and MCP interfaces for multi-bucket virtual filesystem operations*

**[Circular Import Fixes](implementation/CIRCULAR_IMPORT_FIXES_COMPLETE.md)** - *Resolved import-cycle, compatibility-alias, and optional pubsub dependency issues*

**[Cluster Configuration Implementation](implementation/CLUSTER_CONFIG_IMPLEMENTATION_COMPLETE.md)** - *Cluster Service and Cluster Follow configuration APIs, MCP tools, dashboard access, and deployment examples*

**[Cluster Follow Enhancement](implementation/CLUSTER_FOLLOW_ENHANCEMENT_COMPLETE.md)** - *Enhanced Cluster Follow daemon management, worker/follower synchronization, health monitoring, and Kubernetes deployment support*

**[Reorganization Guide](guides/REORGANIZATION_GUIDE.md)** - *Project structure*

### Configuration & Secrets Management

**[Credential Management](credential_management.md)** - *Secure secrets storage*
- Unified credential manager for all services
- S3, Storacha, Filecoin, HuggingFace credentials
- Secure storage with proper permissions
- Environment variable support
- Multiple named credential sets per service
- **Answers:** "How do I store API keys?" "Credential management?" "Secrets security?"

**[Configuration](index.md)** - *System configuration*
- YAML/JSON configuration files
- Environment variable override
- Storage backend configuration
- Cache settings and policies
- Cluster configuration
- VFS bucket policies
- Feature flags and toggles
- **Answers:** "How do I configure the system?" "Config file format?" "Environment variables?"

**[Secure Credentials Guide](guides/SECURE_CREDENTIALS_GUIDE.md)** - *Security best practices*
- Credential storage security
- File permissions and access control
- CI/CD secrets management
- Production security practices
- Credential rotation strategies
- **Answers:** "How do I secure credentials?" "Production security?" "Best practices?"

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

**[Workflow Failure Auto-Fix Summary](fixes/AUTOFIX_WORKFLOW_FIX_SUMMARY.md)** - *Root cause, fixes, validation, and operation flow for workflow failure auto-healing*

**[Syntax Error Fix Status](fixes/SYNTAX_ERROR_FIX_STATUS.md)** - *Status, verification results, and follow-up options for the Lotus Kit syntax-error investigation*

**[Backend Integration Fix](fixes/BACKEND_INTEGRATION_FIX.md)** - *Backend-compatible service configuration formats and dashboard integration flow*

**[Peer Manager Fix Summary](fixes/PEER_MANAGER_FIX_SUMMARY.md)** - *Multihash compatibility, thread-safe peer-manager singleton behavior, and MCP peer-management handlers*

**[MCP Dashboard Fix Summary](fixes/MCP_DASHBOARD_FIX_SUMMARY.md)** - *MCP dashboard fallback-resource fixes, verification, and production configuration details*

**[Configuration Form Field Handlers Fix](fixes/CONFIG_FORM_FIELDS_FIX.md)** - *Complete service configuration form fields, field types, and context-sensitive hints*

**[Service Configuration Form Fix](fixes/CONFIG_FORM_FIX_SUMMARY.md)** - *Correct the dashboard service-configuration payload and capture textarea fields*

**[Backend Configuration Modal Fix](fixes/BACKEND_MODAL_FIX_SUMMARY.md)** - *Backend configuration modal button wiring, MCP tool integration, and end-to-end validation*

**[Configuration Save and Persistence Fix](fixes/CONFIGURATION_FIX_DOCUMENTATION.md)** - *Detailed dashboard configuration persistence, service application, API, and validation documentation*

**[Dashboard Configuration Fix Quick Start](fixes/CONFIGURATION_FIX_README.md)** - *Quick verification, testing, and troubleshooting for dashboard configuration loading and persistence*

**[Dashboard Configuration Form Pre-fill Fix](fixes/DASHBOARD_CONFIG_FIX.md)** - *Technical details for loading saved dashboard credentials into service configuration forms*

**[Lotus Dependencies Docker Pre-installation Fix](fixes/LOTUS_DEPS_DOCKER_FIX.md)** - *Pre-install Lotus and OpenCL dependencies in Docker images and detect them across supported architectures*

**[100% Coverage Roadmap](100_PERCENT_COVERAGE_ROADMAP.md)** - *Test coverage plan and progress*

**[Test Coverage Improvements](TEST_COVERAGE_IMPROVEMENTS.md)** - *GraphRAG and bucket metadata export/import coverage improvements*

**[Path to 100% Test Coverage](PATH_TO_100_PERCENT_COVERAGE.md)** - *Detailed test coverage progress report and remaining work*

**[Phase 5 Final Report](PHASE5_FINAL_REPORT.md)** - *Final report on Phase 5 test coverage improvements*

**[Phase 6 Complete Coverage Report](PHASE6_COMPLETE_COVERAGE_REPORT.md)** - *Complete Phase 6 test coverage achievement by module and test category*

**[Phase 6 Testing Guide](PHASE6_TESTING_GUIDE.md)** - *How to run, maintain, and extend the Phase 6 test suite*

**[Phase 6 Final Summary](PHASE6_FINAL_SUMMARY.md)** - *Final inventory of the Phase 6 test suite, coverage targets, and maintenance guidance*

**[Final Test Coverage Report](FINAL_TEST_COVERAGE_REPORT.md)** - *Final test results and coverage by feature*

**[Performance Optimization](performance_optimization_roadmap.md)** - *Optimization roadmap*

**[Telemetry API](telemetry_api.md)** - *Telemetry endpoints*

**[PyPI Release](pypi_release.md)** - *Package release*

**[Index](index.md)** - *Documentation index*

### Historical & Archive

**[Testing](testing/BACKEND_TESTING_PROJECT_SUMMARY.md)** - *Test documentation*
- [100% Coverage Initiative](testing/100_PERCENT_COVERAGE_INITIATIVE.md)
- [Test Health Matrix](testing/TEST_HEALTH_MATRIX.md)
- Test reports and summaries

**[Complete PR Summary](COMPLETE_PR_SUMMARY.md)** - *Implementation, test coverage, and deployment summary for the completed roadmap feature work*

**[Final Comprehensive PR Summary](FINAL_COMPREHENSIVE_PR_SUMMARY.md)** - *Detailed implementation, testing, documentation, and roadmap coverage summary*

**[Final Test Coverage Report](FINAL_TEST_COVERAGE_REPORT.md)** - *Detailed final test statistics and feature coverage*

**[ARCHIVE](ARCHIVE/summaries/README.md)** - *Historical documentation*
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
5. [Deployment Guides](deployment/READY_TO_TEST_DOCKER.md)

### Path 3: AI/ML Integration (1 hour)
1. [Quick Reference](QUICK_REFERENCE.md)
2. [AI/ML Integration](integration/ai-ml/ai_ml_integration.md)
3. [LangChain Integration](integration/langchain_integration.md)
4. [LlamaIndex Integration](integration/llamaindex_integration.md)
5. [Examples](../examples/) - ML examples

### Path 4: Production Deployment (3 hours)
1. [Installation Guide](installation_guide.md)
2. [Containerization](containerization.md)
3. [CI/CD Automation](deployment/ci-cd/CI_CD.md)
4. [Observability](operations/observability.md)
5. [Performance Metrics](operations/performance_metrics.md)
6. [Auto-Healing](features/auto-healing/AUTO_HEALING.md)

### Path 5: Advanced Development (4+ hours)
1. [Core Concepts](api/core_concepts.md)
2. [Architecture](architecture/ARCHITECTURE_MODULE_ORGANIZATION.md)
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
→ [Core Concepts](api/core_concepts.md) → [Architecture](architecture/ARCHITECTURE_MODULE_ORGANIZATION.md)

**"How do I deploy to production?"**
→ [Containerization](containerization.md) → [CI/CD](deployment/ci-cd/CI_CD.md)

**"How do I integrate with Y?"**
→ [Integration Overview](integration/INTEGRATION_OVERVIEW.md) → Specific integration

**"What can I build with this?"**
→ [Examples](../examples/) → [Use Cases in main README](../README.md)

**"Something's not working"**
→ [Auto-Healing](features/auto-healing/AUTO_HEALING.md) → [Observability](operations/observability.md)

**"How do I contribute?"**
→ [Testing Guide](development/testing_guide.md) → [GitHub](https://github.com/endomorphosis/ipfs_kit_py)

### By Role

**Application Developers**
- [API Reference](api/api_reference.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [Integration](integration/INTEGRATION_OVERVIEW.md)
- [Examples](../examples/)

**Data Scientists**
- [AI/ML Integration](integration/ai-ml/ai_ml_integration.md)
- [IPFS Datasets](integration/IPFS_DATASETS_INTEGRATION.md)
- [LangChain](integration/langchain_integration.md)
- [LlamaIndex](integration/llamaindex_integration.md)

**DevOps/SRE**
- [Cluster Management](operations/cluster_management.md)
- [Deployment](deployment/READY_TO_TEST_DOCKER.md)
- [Observability](operations/observability.md)
- [Auto-Healing](features/auto-healing/AUTO_HEALING.md)

**System Architects**
- [Architecture](architecture/ARCHITECTURE_MODULE_ORGANIZATION.md)
- [Core Concepts](api/core_concepts.md)
- [Storage Backends](reference/storage_backends.md)
- [Performance](operations/performance_metrics.md)

**Contributors**
- [Testing Guide](development/testing_guide.md)
- [API Stability](api_stability.md)
- [Development](development/testing_guide.md)
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

See the [Documentation Guide](guides/DOCUMENTATION_GUIDE.md) for contribution guidelines.

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

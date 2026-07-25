# IPFS Kit Documentation

> **Status**: ✅ **Production Ready** - Comprehensive documentation for production deployment  
> **Quick Reference**: See **[MCP Development Status](ARCHIVE/status-reports/MCP_DEVELOPMENT_STATUS.md)** for current implementation status  
> **Getting Started**: Use `python start_3_node_cluster.py` for immediate deployment

Welcome to the IPFS Kit documentation. This guide provides comprehensive information about IPFS Kit, a production-ready Python toolkit for distributed storage with advanced MCP server integration.

## Overview

IPFS Kit is a comprehensive, production-ready toolkit providing:

- **Production MCP Server**: Multi-backend storage with real-time communication
- **3-Node Cluster Architecture**: Validated distributed deployment (Master:8998, Worker1:8999, Worker2:9000)
- **Multi-Backend Integration**: IPFS, Filecoin, S3, Storacha, HuggingFace, Lassie (6 backends operational)
- **Advanced Features**: WebSocket/WebRTC streaming, search integration, performance monitoring
- **Enterprise Ready**: Role-based access, health monitoring, comprehensive API documentation

## 🚀 Quick Start

### Production Deployment
```bash
# Clone and start 3-node cluster
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
python start_3_node_cluster.py

# Verify cluster health
curl http://localhost:8998/health
```

### Development Environment
```bash
# Enhanced development server
python servers/enhanced_mcp_server_with_full_config.py

# API documentation
# Visit http://localhost:PORT/docs
```

## 📚 Documentation Sections

### **Essential Guides**

- **[MCP Development Status](ARCHIVE/status-reports/MCP_DEVELOPMENT_STATUS.md)** - **Primary reference for current implementation**
- **[Production Readiness Summary](project/FINAL_PROJECT_COMPLETION.md)** - Deployment validation and operational readiness
- **[Getting Started Guide](guides/README.md)** - Quick setup and deployment instructions
- **[Installation Guide](installation_guide.md)** - Comprehensive installation and setup
- **[Project Structure](DOCUMENTATION_INDEX.md)** - File organization and navigation guide

### **Architecture & Implementation**

- **[Architecture Overview](architecture/REFACTORED_ARCHITECTURE_README.md)** - System design and component interaction
- **[API Reference](api/api_reference.md)** - Complete REST API documentation
- **[Core Concepts](api/core_concepts.md)** - Fundamental principles and implementation
- **[Storage Backends](reference/storage_backends.md)** - Multi-backend integration details
- **[MCP Roadmap](ROADMAP_FEATURES.md)** - Detailed technical development roadmap

### **Operations & Development**

- **[Testing Guide](development/testing_guide.md)** - Comprehensive testing infrastructure and validation
- **[Test Coverage Improvements](TEST_COVERAGE_IMPROVEMENTS.md)** - GraphRAG and bucket metadata export/import coverage improvements
- **[Test Coverage Phase 3](TEST_COVERAGE_PHASE3.md)** - Deep coverage analysis and targeted tests for S3 Gateway, WASM, GraphRAG, and analytics
- **[Final Test Coverage Report](TEST_COVERAGE_FINAL.md)** - Final roadmap-feature test results and module coverage
- **[Test Coverage Extension](TEST_COVERAGE_EXTENSION.md)** - Extended coverage details and follow-up work
- **[100% Coverage Roadmap](100_PERCENT_COVERAGE_ROADMAP.md)** - Test coverage plan and progress
- **[Final Test Coverage Report](FINAL_TEST_COVERAGE_REPORT.md)** - Final test results and coverage by feature
- **[Phase 6 Testing Guide](PHASE6_TESTING_GUIDE.md)** - How to run, maintain, and extend the Phase 6 test suite
- **[Phase 6 Final Summary](PHASE6_FINAL_SUMMARY.md)** - Final Phase 6 test-suite inventory, coverage targets, and maintenance guidance
- **[Server Selection Guide](../servers/README.md)** - Production vs. development server guidance
- **[Deployment Guide](guides/CLUSTER_DEPLOYMENT_GUIDE.md)** - Production cluster deployment instructions
- **[Tailwind CSS Production Build](deployment/TAILWIND_BUILD.md)** - Build and maintain the dashboard stylesheet locally
- **[Performance Monitoring](operations/performance_metrics.md)** - Metrics, monitoring, and optimization

### **Advanced Features**

- **[Authentication Extension](operations/cluster_authentication.md)** - Security and access control
- **[AI/ML Integration](integration/ai-ml/ai_ml_integration.md)** - Machine learning and dataset management
- **[Streaming Guide](reference/streaming_guide.md)** - WebSocket and WebRTC real-time communication
- **[Migration Guide](MCP_SERVER_MIGRATION_GUIDE.md)** - Data routing and backend migration
- **[VFS Contract Specification](VFS_CONTRACT_SPEC.md)** - Canonical VFS request, response, and sync contracts
- **[AnyIO Migration Guide](ANYIO_MIGRATION.md)** - Migrating asynchronous code and tests from `asyncio` to AnyIO
- **[Complete AnyIO Migration Summary](COMPLETE_ANYIO_MIGRATION_SUMMARY.md)** - Migration results, test coverage, and implementation details
- [Knowledge Graph](knowledge_graph.md) - IPLD-based knowledge representation
- [libp2p Integration](integration/libp2p_integration.md) - Direct peer-to-peer communication
- [Cluster State](operations/cluster_state_helpers.md) - Distributed state management
- [Metadata Replication](metadata_replication.md) - Fault-tolerant metadata backup

### **Reference Materials**

- **[Changelog](../CHANGELOG.md)** - Version history and feature updates
- **[Complete PR Summary](COMPLETE_PR_SUMMARY.md)** - Implementation, test coverage, and deployment summary for the completed roadmap feature work
- **[Final Comprehensive PR Summary](FINAL_COMPREHENSIVE_PR_SUMMARY.md)** - Detailed implementation, testing, documentation, and roadmap coverage summary
- **[Final Test Coverage Report](FINAL_TEST_COVERAGE_REPORT.md)** - Detailed final test statistics and feature coverage
- **[Submodule-Scope Release Checklist](RELEASE_CHECKLIST_SUBMODULE_SCOPE.md)** - Release and merge checks for submodule-scoped VFS integration work
- **[Contributing Guide](../README.md#-contributing)** - Development workflow and contribution guidelines
- **[Configuration Requirements](../config/requirements.txt)** - WebRTC monitoring and async runtime dependencies
- **[Release Notes](../CHANGELOG.md)** - Detailed release information and breaking changes
- [PyPI Release Guide](pypi_release.md) - Publishing to PyPI
- [Containerization and Deployment](containerization.md) - Docker and Kubernetes deployment
- [CI/CD Pipeline](deployment/ci-cd/ci_cd_pipeline.md) - Continuous integration and deployment
- [AMD64 Workflow Implementation Summary](ci-cd/amd64/AMD64_WORKFLOW_IMPLEMENTATION_SUMMARY.md) - Self-hosted AMD64 workflow implementation and validation coverage
- [Set Up Your GitHub Actions Runner](ci-cd/SETUP_RUNNER_NOW.md) - Quick self-hosted runner setup
- [GitHub Actions Runner Setup (Complete)](ci-cd/GITHUB_RUNNER_SETUP_COMPLETE.md) - Verified self-hosted runner configuration and operations
- [GitHub Actions Runner Scripts Guide](ci-cd/RUNNER_SCRIPTS_GUIDE.md) - Manage, monitor, restart, and remove self-hosted runners
- [CI/CD Verification Report](ci-cd/CI_CD_VERIFICATION_REPORT.md) - Workflow validation results and maintenance findings
- [GitHub Workflow Fixes Summary](ci-cd/WORKFLOW_FIXES_SUMMARY.md) - Summary of CI configuration and workflow corrections
- [GitHub Workflow Test Fixes](ci-cd/WORKFLOW_TEST_FIXES.md) - Diagnose and address broken workflow test imports, dependencies, and CI exclusions
- [GitHub Actions Runner Quick Start](ci-cd/START_RUNNER_HERE.md) - Start here when setting up a self-hosted runner
- [GitHub Actions Runners Status Report](ci-cd/GITHUB_RUNNERS_STATUS_REPORT.md) - Current runner services, startup configuration, and ARM64 CI/CD health
- [Auto-Healing Workflows Quick Start](../AUTO_HEALING_QUICK_START.md) - Get started with automatic workflow failure recovery
- [Security Scanning Workflow](../.github/workflows/security.yml) - Dependency, code, and container security scans
- [GitHub Actions Auto-Healing Scripts](../.github/scripts/README.md) - Analyze workflow failures and generate fix proposals
- [GitHub Actions Auto-Healing Workflows](../.github/workflows/AUTO_HEAL_README.md) - Configure and troubleshoot automatic workflow failure recovery
- [GitHub Actions Workflow Syntax Guidelines](../.github/WORKFLOW_SYNTAX_GUIDELINES.md) - Avoid JavaScript and YAML interpolation syntax errors in workflow scripts
- [CI/CD Issue Template](../.github/ISSUE_TEMPLATE/ci_cd_issue.md) - Report CI/CD workflow failures
- [GitHub Copilot Instructions](../.github/copilot-instructions.md) - Guidance for automatically diagnosing and fixing failed workflows

## 🏗️ **Current Implementation Status**

### ✅ **Production Ready Components**
- **3-Node Cluster**: Master/Worker architecture operational
- **Multi-Backend Storage**: 6 storage systems integrated
- **MCP Server**: Comprehensive RESTful API with WebSocket/WebRTC
- **Search Integration**: Full-text and vector search operational
- **Performance Monitoring**: Prometheus metrics and health endpoints

### 🔄 **Active Development** 
- **Enhanced Authentication**: Role-based access control (Q3 2025)
- **AI/ML Integration**: Model registry and training orchestration (Q4 2025)
- **Enterprise Features**: High availability and security enhancements (Q1 2026)

### 📋 **Planned Enhancements**
- **Edge Computing**: Mesh networking and IoT integration
- **Decentralized Governance**: Community-driven storage policies
- **Quantum Resistance**: Post-quantum cryptography implementation

## 🛠️ **Development Workflow**

1. **Start Development**: Use `servers/enhanced_mcp_server_with_full_config.py`
2. **Test Implementation**: Run `python tests/test_all_mcp_tools.py`
3. **Validate Structure**: Use `python tools/verify_enhanced_organization.py`
4. **Production Deploy**: Use `python start_3_node_cluster.py`

## 🚀 **Getting Started (Production)**

To get started with the production-ready IPFS Kit:

```bash
# Clone and deploy 3-node cluster
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
python start_3_node_cluster.py

# Verify cluster health
curl http://localhost:8998/health  # Master
curl http://localhost:8999/health  # Worker 1
curl http://localhost:9000/health  # Worker 2

# Access API documentation
# Visit http://localhost:8998/docs
```

For development and testing:

```python
# Enhanced development server
python servers/enhanced_mcp_server_with_full_config.py

# Or lightweight testing
python servers/streamlined_mcp_server.py
```

## 📞 **Support & Resources**

- **Primary Documentation**: [MCP Development Status](ARCHIVE/status-reports/MCP_DEVELOPMENT_STATUS.md)
- **API Documentation**: Available at `/docs` endpoint on any running server
- **Issue Tracking**: GitHub issues with detailed reproduction steps
- **Development Chat**: Reference documentation and roadmap for guidance

---

**For the most current implementation status, deployment instructions, and development guidance, always refer to the [MCP Development Status Document](ARCHIVE/status-reports/MCP_DEVELOPMENT_STATUS.md) as the authoritative source.**
